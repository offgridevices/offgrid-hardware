#!/bin/sh
# Mesh Radio CI.  The routed copper is the design of record (src/pipeline.py
# took several passes and local repairs to finish it, README "How the board
# was routed"), so routing is not re-run.  Everything after it is: the
# artwork (silkscreen, names, logo) from src/, then every gate and the fab
# files, which must equal the committed ones.  Runs in the image
# tools/ci.json names, or locally with tools/ci/local.sh <this folder> from
# the repository root.
set -eu
cd "$(dirname "$0")/.."

echo "== artwork and fab files (src/make.py): circuit gates, KiCad DRC 0 / 0 / 0, nets, Gerbers, BOM, CPL"
python3 src/make.py --artwork --fab-only

echo "== committed fab files match the build"
python3 tools/check_outputs.py
