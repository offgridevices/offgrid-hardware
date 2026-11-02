#!/bin/sh
# Canary v1 CI: every gate, from the committed routed board (the design of
# record; Freerouting is not bit-for-bit repeatable, so routing is not re-run).
# Runs inside the kicad/kicad:10.0.6 image (as root) or anywhere tools/kd works.
set -eu
cd "$(dirname "$0")/.."
SIMAVR_REV=5b08da60497f7564f50941f74a549fe2851db030

echo "== schematic: regenerate, ERC, netlist = circuit.py"
python3 src/schematic.py
mkdir -p out
tools/kd kicad-cli sch erc --exit-code-violations -o out/erc.rpt canary.kicad_sch
tools/kd kicad-cli sch export netlist -o out/canary.net canary.kicad_sch
python3 src/check_netlist.py out/canary.net

echo "== board: DRC (all severities, schematic parity) must be empty"
tools/kd kicad-cli pcb drc --refill-zones --schematic-parity --severity-all -o out/drc.rpt canary.kicad_pcb
python3 - <<'PY'
import re, sys
v = re.findall(r'^\[(\w+)\]', open('out/drc.rpt').read(), re.M)
print('DRC items:', len(v), sorted(set(v)))
sys.exit(1 if v else 0)
PY
echo "== copper geometry: no corner sharper than 45 deg, power tracks wide enough (IPC-2221)"
tools/kd python3 src/check_geometry.py canary.kicad_pcb

echo "== fab outputs, pin map; committed files must equal the build"
python3 src/fab.py --no-renders
git diff --stat --exit-code -- canary.kicad_sch production/canary-gerbers.zip \
  production/canary-bom-pcbway.csv production/canary-cpl.csv production/canary-netlist.csv \
  production/canary.hex

echo "== simulations"
if [ ! -f /opt/simavr/simavr/obj-x86_64-linux-gnu/libsimavr.a ]; then
  git clone -q https://github.com/buserror/simavr /opt/simavr
  git -C /opt/simavr checkout -q "$SIMAVR_REV"
  make -s -C /opt/simavr build-simavr > /dev/null
fi
mkdir -p /opt/simavr-inc && ln -sfn /opt/simavr/simavr/sim /opt/simavr-inc/simavr
gcc -O2 -I/opt/simavr-inc -I/opt/simavr/simavr/obj-x86_64-linux-gnu -o sim/hil/harness sim/hil/harness.c \
  /opt/simavr/simavr/obj-x86_64-linux-gnu/libsimavr.a -lelf -lm
python3 sim/hil/scenarios.py
echo "== web bench: the page's JS detector = the firmware's, second by second"
(cd sim/hil/out && node ../../../web/test/port_vs_firmware.js *_uart.log)
python3 sim/spice/run.py
python3 sim/analysis/analysis.py > /dev/null
echo "== all Canary v1 gates passed"
