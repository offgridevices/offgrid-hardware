#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the Python packages tools/Dockerfile installs that make.py and verify.py
# use (KiKit is only for the panel, which --fab-only skips).
set -eu
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git > /dev/null
pip3 install --break-system-packages -q numpy shapely Pillow matplotlib pypdf \
  uharfbuzz fonttools pymupdf scipy
