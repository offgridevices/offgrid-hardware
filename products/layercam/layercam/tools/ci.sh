#!/bin/sh
# LayerCam CI: three boards (main, LED ring, USB).  The routed boards are
# the design of record (Freerouting is not deterministic): the artwork is
# rebuilt from src/, then every gate and the fab files of all three boards,
# which must equal the committed ones.  Then the design checks (regulators,
# camera cable by position, housing, the firmware's pin map), the
# simulations and the firmware's host tests.  Runs in the image
# tools/ci.json names, or locally with tools/kd tools/ci.sh.
set -eu
cd "$(dirname "$0")/.."

echo "== artwork and fab files (src/make.py): circuit gates, DRC 0 / 0 / 0, nets, 45-degree corners, pair lengths, Gerbers, BOM, CPL"
python3 src/make.py --artwork --fab-only

echo "== committed fab files match the build"
python3 tools/check_outputs.py

echo "== design checks (src/verify.py)"
python3 src/verify.py

echo "== simulations (impedance, power, thermal)"
python3 sim/impedance.py
python3 sim/power_budget.py
python3 sim/thermal.py

echo "== firmware host tests"
(cd firmware && python3 -m unittest)
