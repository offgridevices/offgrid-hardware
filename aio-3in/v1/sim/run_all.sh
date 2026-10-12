#!/bin/sh
# Re-run every simulation study for the aio-3in v1 board, in order.
#   needs: ngspice (tested with 44), python3 with numpy, scipy, matplotlib
#   (python3 -m pip install --user --break-system-packages numpy scipy matplotlib)
#   or, from aio-3in/v1, inside the toolchain container: tools/kd sh sim/run_all.sh
# Scratch netlists and raw data go to <repo>/out/sim/ (gitignored).  The
# half-bridge study caches its ngspice runs there; the first run takes
# several minutes on 4 cores, later runs seconds.
set -e
cd "$(dirname "$0")"
for study in fet_model halfbridge battery gate_supply bec sense; do
    echo "=== $study"
    (cd "$study" && python3 -W ignore run.py > /dev/null)
    echo "    -> $study/results.txt"
    if [ "$study" = halfbridge ]; then
        (cd halfbridge && python3 -W ignore options.py > /dev/null)
        echo "    -> halfbridge/options.txt"
    fi
done
echo "losses.csv written by halfbridge"
