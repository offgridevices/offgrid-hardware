#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh.
#
# The packages make.py --fab-only and verify.py name, each at a fixed
# version and from pip, not Debian's packages, which move with Debian's
# updates: requirements.txt's pins as a constraint (-c), and the packages
# the build machine takes from Ubuntu's apt at versions with wheels for this
# image's Python 3.13 (requirements.txt says which and why).  Shapely must
# stay at 2.0.7: KiKit builds the panels' outline with it, and with
# Debian's Shapely 2.1 the panel Gerbers come out different from the
# committed ones.  gerbonara goes in without its requirements (a web server
# it does not need here).  tools/Dockerfile installs the same.  A few other
# packages present are Debian's and not pinned (packaging, PyYAML,
# typing-extensions, wxPython); none of them changes an output.
set -eu
cd "$(dirname "$0")/.."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip > /dev/null
pip3 install --break-system-packages -q -c requirements.txt \
  numpy==2.2.4 scipy==1.15.3 shapely==2.0.7 pillow==11.1.0 fonttools==4.46.0 \
  pypdf uharfbuzz pymupdf scikit-image kikit
pip3 install --break-system-packages -q --no-deps gerbonara==1.6.3
