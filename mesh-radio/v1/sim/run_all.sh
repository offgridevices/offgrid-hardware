#!/bin/sh
# Re-run every power-path simulation study for Mesh Radio v1, in order.
#   needs: ngspice (tested with 44), python3 with numpy and matplotlib
#   or, from mesh-radio/v1, inside the pinned toolchain container:  tools/kd sh sim/run_all.sh
# Scratch netlists, ngspice logs and decimated waveforms go to sim/out/ (ignored by
# the repository's out/ rule).  Each study writes results.txt, stress.json and its
# plot next to its run.py; derating/ reads the other studies' stress.json, so it
# runs last.  The burst grid is the slow part (~40-60 min on 4 cores).
set -e
cd "$(dirname "$0")"
for study in hotplug reverse shorts burst solar derating; do
    echo "=== $study"
    (cd "$study" && python3 -W ignore run.py > /dev/null)
    echo "    -> $study/results.txt"
done
