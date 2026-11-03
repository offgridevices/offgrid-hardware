#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh.
#
# requirements.txt lists numpy and Pillow; make.py also needs fontTools (the
# wordmark is built from real Archivo glyph outlines), which the file does
# not list. cadquery is only for emit_step.py, which make.py does not run,
# so it is left out: it is a very large install.
set -eu
pip install -q numpy Pillow fonttools

# wordmark.py reads the brand font from ~/Library/Fonts/, a macOS path. On
# Linux ~ still expands, so the same file placed there works without
# touching the generator. Pinned to a google/fonts commit and checked
# against its hash, so a changed upstream font fails loudly instead of
# quietly moving the silkscreen.
FONT_URL=https://raw.githubusercontent.com/google/fonts/6c70c829f09ea345d3590406693220ea35c6553f/ofl/archivo/Archivo%5Bwdth,wght%5D.ttf
FONT_SHA256=0e094a7d3c7c4c25cf1310c4b30014f1dae9332220b1c2c88f4fa996f0b05053
mkdir -p ~/Library/Fonts
F=~/Library/Fonts/Archivo-VariableFont_wdth,wght.ttf
python3 -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$FONT_URL" "$F"
echo "$FONT_SHA256  $F" | sha256sum -c -
