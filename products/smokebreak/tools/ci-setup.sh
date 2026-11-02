#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the Python packages tools/Dockerfile installs that the gates use.
set -eu
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git > /dev/null
pip3 install --break-system-packages -q numpy shapely Pillow matplotlib uharfbuzz fonttools pytest
