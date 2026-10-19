#!/bin/sh
# Re-run every power-path simulation study for Mesh Radio v1, in order.
#   needs: ngspice (tested with 44), python3 with numpy and matplotlib
#   or, from mesh-radio/v1, inside the pinned toolchain container:  tools/kd sh sim/run_all.sh
#   or with a named container (stop only that one):  docker run --rm --name meshsim-all -u $(id -u):$(id -g) -e HOME=/tmp -v <repo>:/w -w /w/mesh-radio/v1/sim ogkicad:10 sh run_all.sh
# Scratch netlists, ngspice logs and decimated waveforms go to sim/out/ (ignored by
# the repository's out/ rule).  Each study writes results.txt, stress.json and its
# plot next to its run.py; derating/ reads the other studies' stress.json, so it
# runs last.  Every study runs at ambient -40, -20, 0, 25, 60 and 85 C; the burst grid
# (360 runs) is the slow part, ~15-30 min on 4 cores (cached per run in sim/out/burst/).
set -e
cd "$(dirname "$0")"
for study in hotplug reverse shorts burst solar derating; do
    echo "=== $study"
    (cd "$study" && python3 -W ignore run.py > /dev/null)
    echo "    -> $study/results.txt"
done
