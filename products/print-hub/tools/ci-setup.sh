#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the packages tools/Dockerfile installs that the gates use, and a compiler
# for the firmware's host tests.
set -eu
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git g++ make > /dev/null
pip3 install --break-system-packages -q numpy==2.5.4 shapely==2.2.0 Pillow==13.0.0 \
  pypdf==6.21.1 uharfbuzz==0.56.3 fonttools==4.67.0
