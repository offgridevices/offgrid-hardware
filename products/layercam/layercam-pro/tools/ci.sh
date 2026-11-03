#!/bin/sh
# LayerCam Pro CI: one board.  The routed board is the design of record
# (Freerouting is not deterministic): the artwork is rebuilt from src/, then
# every gate and the fab files, which must equal the committed ones.  Then
# the design checks (regulators, the sensor's balls by position, the case's
# outline, part heights, the firmware's pin map), the simulations and the
# firmware's host tests.  The case's own checks (enclosure/src/check.py)
# need Prusa's files, which are not committed: they are run by hand.  Runs
# in the image tools/ci.json names, in CI or locally with
# tools/ci/local.sh <this folder>.
set -eu
cd "$(dirname "$0")/.."

echo "== artwork and fab files (src/make.py): circuit gates, DRC 0 / 0 / 0, nets, 45-degree corners, MIPI pair lengths, Gerbers, BOM, CPL"
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
