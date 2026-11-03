#!/bin/sh
# What CI adds to the bare pinned image (tools/ci.json) before tools/ci.sh:
# the AVR toolchain and libelf for the firmware and the simavr harness,
# ngspice for the SPICE model, Node for the web bench.
set -eu
# Pinned at the versions that last rebuilt the committed files exactly
# (2026-11-02), so a new release
# cannot move an output unseen.
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip git gcc make pkg-config \
  gcc-avr avr-libc libelf-dev ngspice nodejs > /dev/null
pip3 install --break-system-packages -q numpy==2.5.4 matplotlib==3.11.2
