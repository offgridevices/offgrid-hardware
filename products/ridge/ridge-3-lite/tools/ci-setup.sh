#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the Python packages tools/Dockerfile installs that make.py and verify.py
# use (KiKit is only for the panel, which --fab-only skips).
set -eu
# Pinned at the versions that last rebuilt the committed files exactly
# (2026-11-02; Pillow is the image's own Debian package), so a new release
# cannot move an output unseen.
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git > /dev/null
pip3 install --break-system-packages -q numpy==2.5.4 shapely==2.2.0 Pillow==11.1.0 matplotlib==3.11.2 \
  pypdf==6.21.4 uharfbuzz==0.57.0 fonttools==4.68.0 pymupdf==2.1 scipy==1.18.1
