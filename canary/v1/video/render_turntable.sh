#!/bin/sh
# 240 high-quality KiCad 3D frames, one full turn (1.5 degrees per frame),
# transparent background; video/make_video.py composites and slows them.
cd "$(dirname "$0")/.."
mkdir -p video/out/tt
seq 0 239 | xargs -P 4 -I{} sh -c '
  f=$(printf "video/out/tt/t%03d.png" {}); [ -s "$f" ] && exit 0
  z=$(python3 -c "print(30 + {} * 1.5)")
  tools/kd kicad-cli pcb render --quality high --use-board-stackup-colors --perspective \
    --rotate "-55,0,$z" --zoom 1.0 --pan "0,0.6,0" --background transparent \
    -w 1920 -h 1080 -o "$f" canary.kicad_pcb > /dev/null 2>&1'
ls video/out/tt/t*.png | wc -l
