#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the Python packages tools/Dockerfile installs that make.py uses (KiKit,
# Freerouting, ngspice and the 3D models are for routing, the panel, the
# simulations and the renders, which --fab-only skips).
set -eu
# Pinned at the versions in tools/Dockerfile's image that built the committed
# files (3 Nov 2026), so a new release cannot move an output unseen.
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git > /dev/null
pip3 install --break-system-packages -q numpy==2.5.4 shapely==2.2.0 Pillow==11.1.0 matplotlib==3.11.2 \
  pypdf==6.21.1 uharfbuzz==0.56.3 fonttools==4.67.0 pymupdf==1.28.2 scipy==1.18.1
