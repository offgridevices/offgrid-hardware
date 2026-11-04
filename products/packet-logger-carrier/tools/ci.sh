#!/bin/sh
# Packet Logger Carrier CI: every gate in src/make.py (route, DRC, netlist,
# silkscreen, wordmark, KiCad emit, layer check, Gerber emit and verify;
# any failing gate exits non-zero), then the rebuilt Gerbers and drill files
# must be byte-identical to the committed zip: a script change without
# regenerated outputs, or outputs no script produces, fails here.  KiCad's
# own DRC is skipped: make.py looks for kicad-cli at its macOS path only and
# prints that it skipped.
set -eu
cd "$(dirname "$0")/.."

echo "== build and verify (src/make.py)"
(cd src && python3 make.py)

echo "== committed Gerbers match the generator"
python3 - <<'PY'
import sys, zipfile
a = zipfile.ZipFile('packet-logger-carrier-gerbers.zip')
b = zipfile.ZipFile('src/out/packet-logger-carrier-gerbers.zip')
na, nb = sorted(a.namelist()), sorted(b.namelist())
bad = sorted(set(na) ^ set(nb)) + [n for n in na if n in nb and a.read(n) != b.read(n)]
if bad:
    print('::error::Committed packet-logger-carrier-gerbers.zip does not match what src/make.py '
          'produces. Rebuild and commit the outputs. Differs:', ', '.join(bad))
    sys.exit(1)
print('Gerbers and drill files are byte-identical to the generator\'s output.')
PY
