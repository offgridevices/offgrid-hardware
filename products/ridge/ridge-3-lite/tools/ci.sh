#!/bin/sh
# Ridge 3 Lite CI.  The routed copper is the design of record (the last
# connection was finished by hand), so routing is not re-run.  Everything
# after it is: the artwork (silkscreen, logo, flag) from src/, then every
# gate and the fab files, which must equal the committed ones, then the
# design checks.  Runs in the image tools/ci.json names, or locally with
# tools/ci/local.sh <this folder> from the repository root.
set -eu
cd "$(dirname "$0")/.."

echo "== artwork and fab files (src/make.py): circuit gates, KiCad DRC 0 / 0 / 0, nets, Gerbers, BOM, CPL"
python3 src/make.py --artwork --fab-only

echo "== committed fab files match the build"
python3 tools/check_outputs.py

echo "== design checks (src/verify.py): firmware pin maps, parts, fab outputs, simulations' verdicts"
python3 src/verify.py
