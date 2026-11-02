#!/bin/sh
# Ridge 3 CI: the flight controller and the 4-in-1 ESC.  The routed copper
# is the design of record, so routing is not re-run; everything after it
# is: every gate, the fab files and both 3 x 2 panels, which must equal the
# committed ones.  --fab-only leaves out the renders and the STEP models:
# they need KiCad's 3D-model package, which the bare image does not carry.
# Runs in the image tools/ci.json names (in it on 4 cores make.py
# --fab-only took about 5 minutes and verify.py 1), or locally with the
# image tools/Dockerfile builds.
set -eu
cd "$(dirname "$0")/.."

# circuit.py's own checks, KiCad DRC (0 / 0 / 0), nets equal to circuit.py,
# BOM and CPL equal to the placed parts, the ESC's heatsink made from this
# board, and the panels: DRC six times the board's, and every copy's
# Gerbers, BOM and CPL equal to the board's.
echo "== both boards and panels (src/make.py --fab-only)"
python3 src/make.py --fab-only

# stable.py puts the committed bytes back where only KiCad's stamps (time,
# build) differ, so a change left here is a real one: a source changed
# without its outputs, or outputs no source produces.
echo "== committed outputs match the build"
git rev-parse --git-dir > /dev/null   # no repository: fail, never pass unchecked
if [ -n "$(git status --porcelain -- .)" ]; then
  git status --porcelain -- .
  echo "::error::Ridge 3 outputs differ from what src/make.py produces. Rebuild with python3.12 src/make.py and commit the outputs."
  exit 1
fi
echo "Every Ridge 3 output is byte-identical to the build's."

# Pin maps, the firmware's scale factors, the power arithmetic, the boards'
# DRC and silkscreen.  The firmware sources, the datasheets and the brand
# art are not here, so the checks that need them SKIP.  It rewrites
# VERIFICATION.md, so it runs after the comparison.
echo "== design checks (src/verify.py)"
python3 src/verify.py
