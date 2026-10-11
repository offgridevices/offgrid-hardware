#!/bin/bash
# Place -> route (two router cost variants) -> finish (coarse, then fine grid) -> final art + DRC.
set -e
cd "$(dirname "$0")"
# (placement already built: ../smokebreak.kicad_pcb)
FREEROUTING_TIMEOUT=5400 python3 route_run.py ra 25 14 > out/ra.txt 2>&1 &
FREEROUTING_TIMEOUT=5400 python3 route_run.py rb 50 14 > out/rb.txt 2>&1 &
wait
best=$(grep -h "unrouted" out/ra.txt out/rb.txt | sort -k3 -n | head -1 | cut -d' ' -f1)
echo "routed: $(grep -h unrouted out/ra.txt out/rb.txt | tr '\n' ' ') best $best"
rm -rf out/fin out/fin2; mkdir -p out/fin out/fin2
FINISH_RES=0.1 timeout 6000 python3 finish_run.py out/$best/r.kicad_pcb out/fin/f.kicad_pcb > out/fin/log.txt 2>&1 || true
grep -h "after" out/fin/log.txt
FINISH_RES=0.05 timeout 5000 python3 finish_run.py out/fin/f.kicad_pcb out/fin2/f.kicad_pcb > out/fin2/log.txt 2>&1 || true
grep -h "after" out/fin2/log.txt
rm -rf out/rep; mkdir -p out/rep
FINISH_RES=0.05 FINISH_DEEP=20 timeout 6000 python3 repair_run.py out/fin2/f.kicad_pcb out/rep/f.kicad_pcb > out/rep/log.txt 2>&1 || true
grep -h "removed\|after" out/rep/log.txt
python3 final.py out/rep/f.kicad_pcb 2>&1 | grep -v "assert\|Debug\|swig"
