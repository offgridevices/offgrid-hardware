#!/bin/sh
# SmokeBreak CI.  The routed board is the design of record: Freerouting is
# not deterministic and the last joins were finished by script
# (src/touchup.py), so routing is not re-run.  Everything after it is: the
# silkscreen art from src/ (brand.py, art.py, make.art_items), KiCad DRC
# (0 / 0 / 0), the net check against circuit.py, then the Gerbers, BOM, CPL
# and netlist, which must equal the committed ones; then the firmware's
# model tests.  Runs in the image tools/ci.json names, or locally with
# tools/kd tools/ci.sh.
set -eu
cd "$(dirname "$0")/.."

echo "== silkscreen art (src/artwork.py)"
(cd src && python3 artwork.py)

echo "== DRC, net check and production files (src/fab.py)"
(cd src && python3 fab.py --no-3d)

echo "== committed production files match the build"
python3 tools/check_outputs.py

echo "== firmware model tests"
python3 -m pytest -q firmware/tests
