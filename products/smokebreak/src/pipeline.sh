#!/bin/bash
# The whole board, from the circuit to the fab files, in the order it was
# built.  Run from smokebreak/v1/src, in the pinned toolchain (../tools/kd).
# Routing is not deterministic, so a fresh run gives a different (equally
# checked) board; the committed smokebreak.kicad_pcb is the design of record,
# and CI rebuilds from it (artwork.py, fab.py).
#
#   1  placement      spread.py settles place.py's anchors -> place_legal.py
#   2  power copper   make.py: board, planes, pours, fixed vias, keep-outs
#   3  route          Freerouting, two cost variants, the better one kept
#   4  finish         maze router on the coarse, then the fine grid; rip-up repair
#   5  final          gate side, exact-pair finishing, fills, art, stitching, DRC
#   6  touch-up       the last joins (touchup.py), then final.py --tail again
#   7  polish         flagged items out, joined again (twice is usually enough)
#   8  stubs          dedangle.py
#   9  art, fab       artwork.py, fab.py (DRC and net gates, Gerbers, BOM, CPL, STEP, renders)
set -e
cd "$(dirname "$0")"
mkdir -p out
python3 spread.py
python3 make.py
FREEROUTING_TIMEOUT=3600 python3 route_run.py re 25 25 > out/re.txt 2>&1 &
FREEROUTING_TIMEOUT=3600 python3 route_run.py rf 50 25 > out/rf.txt 2>&1 &
wait
best=$(grep -h "unrouted" out/re.txt out/rf.txt | sort -k3 -n | head -1 | cut -d' ' -f1)
echo "routed: $(grep -h unrouted out/re.txt out/rf.txt | tr '\n' ' ') best $best"
rm -rf out/f1 out/f2 out/rep; mkdir -p out/f1 out/f2 out/rep
FINISH_RES=0.1 timeout 2400 python3 finish_run.py out/$best/r.kicad_pcb out/f1/f.kicad_pcb > out/f1/log.txt 2>&1 || true
FINISH_RES=0.05 timeout 2400 python3 finish_run.py out/f1/f.kicad_pcb out/f2/f.kicad_pcb > out/f2/log.txt 2>&1 || true
FINISH_RES=0.05 FINISH_DEEP=20 timeout 2400 python3 repair_run.py out/f2/f.kicad_pcb out/rep/f.kicad_pcb > out/rep/log.txt 2>&1 || true
grep -h "after" out/f1/log.txt out/f2/log.txt out/rep/log.txt
python3 final.py out/rep/f.kicad_pcb
python3 touchup.py
python3 final.py --tail
python3 polish.py
python3 polish.py
python3 dedangle.py
python3 artwork.py --settle
python3 fab.py
