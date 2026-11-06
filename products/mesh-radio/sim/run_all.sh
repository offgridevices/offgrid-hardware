#!/bin/sh
# Re-run every power-path simulation study for Mesh Radio v1, in order.
#   needs: ngspice (tested with 44), python3 with numpy and matplotlib
#   or, from products/mesh-radio, inside the pinned toolchain container:  tools/kd sh sim/run_all.sh
#   or with a named container (stop only that one):  docker run --rm --name meshsim-all -u $(id -u):$(id -g) -e HOME=/tmp -v <repo>:/w -w /w/products/mesh-radio/sim ogkicad:10 sh run_all.sh
# Scratch netlists, ngspice logs and decimated waveforms go to sim/out/ (ignored by
# the repository's out/ rule).  Each study writes results.txt, stress.json and its
# plot next to its run.py; derating/ reads the other studies' stress.json, so it
# runs last.  Every study runs at ambient -40, -20, 0, 25, 60 and 85 C; the burst grid
# (360 runs) is the slow part, ~2.5 h of the ~3 h on 4 cores with the routed board's parasitics
# (6 Nov; cached per run in sim/out/burst/).
set -e
cd "$(dirname "$0")"
for study in hotplug reverse shorts burst solar derating; do
    echo "=== $study"
    (cd "$study" && python3 -W ignore run.py > /dev/null)
    echo "    -> $study/results.txt"
done
# The Verdict table in sim/README.md is written from every study's
# results.txt (rf, thermal and extract included), so it cannot drift.
python3 verdict.py
