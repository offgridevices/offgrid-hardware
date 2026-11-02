#!/bin/sh
# Top and hero stills (transparent, 3840 wide) for the tour, title and order scenes.
cd "$(dirname "$0")/.."
mkdir -p video/out/stills
tools/kd kicad-cli pcb render --quality high --use-board-stackup-colors --side top --zoom 1.0 \
  --background transparent -w 3840 -h 2160 -o video/out/stills/top.png canary.kicad_pcb
tools/kd kicad-cli pcb render --quality high --use-board-stackup-colors --perspective --rotate "-50,0,-28" \
  --zoom 0.92 --pan "0,1.3,0" --background transparent -w 3840 -h 2160 -o video/out/stills/hero.png canary.kicad_pcb
