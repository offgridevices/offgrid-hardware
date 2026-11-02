#!/bin/sh
# Print Hub CI.  The routed board is the design of record: the artwork is
# rebuilt from src/, then every gate and the fab files, which must equal the
# committed ones.  Then the design checks, the power-chain analysis, and the
# firmware's and the host tool's tests.  Runs in the image tools/ci.json
# names, in CI or locally with tools/ci/local.sh <this folder>.
set -eu
cd "$(dirname "$0")/.."

echo "== artwork and fab files (src/make.py): circuit gates, KiCad DRC 0 / 0 / 0, nets, Gerbers, BOM, CPL"
python3 src/make.py --artwork --fab-only

echo "== committed fab files match the build"
python3 tools/check_outputs.py

echo "== power-chain analysis (sim/power_budget.py)"
python3 sim/power_budget.py

echo "== design checks (src/verify.py): pin map and scaling against the circuit, LED chain, port parts, simulation verdicts"
python3 src/verify.py

echo "== firmware host tests"
make -C firmware/test

echo "== host tool tests (host/printhub.py against a fake board)"
python3 host/test_printhub.py
