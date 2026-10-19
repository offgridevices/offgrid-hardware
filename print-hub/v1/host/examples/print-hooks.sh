#!/bin/sh
# Call these from the print server's existing "print started" / "print
# finished" automation (the one that starts and stops the camera recording).
#
#   print-hooks.sh start
#   print-hooks.sh end
#
# Port names are whatever you set with `printhub name` (once):
#   printhub name 1 fan
#   printhub name 2 light
#   printhub name 3 filter1
#   printhub name 4 filter2
#   printhub priority fan 1        # the exhaust is kept on longest if power runs short
#
# The off-timers run on the board itself, so they still happen if the server
# reboots after sending them.
set -e
PRINTHUB="${PRINTHUB:-printhub}"

case "$1" in
  start)
    "$PRINTHUB" on fan light filter1 filter2
    ;;
  end)
    "$PRINTHUB" off light after 3m          # light stays on until the recording stops
    "$PRINTHUB" off fan after 15m           # keep exhausting fumes for a while
    "$PRINTHUB" off filter1 filter2 after 30m
    ;;
  *)
    echo "usage: $0 start|end" >&2
    exit 2
    ;;
esac
