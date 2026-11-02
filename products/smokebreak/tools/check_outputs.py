"""CI: the production files the build just wrote must equal the committed ones.

    python3 tools/check_outputs.py      (from smokebreak/v1, after src/artwork.py and src/fab.py)

Compares against git HEAD.  The Gerber zip is compared file by file with
the creation-date stamps KiCad writes left out (they change every run); the
BOM, CPL and netlist must be byte-identical.  Exits 1 on a difference."""
import io
import re
import subprocess
import sys
import zipfile

NAME = 'smokebreak'
DATE = re.compile(r'CreationDate|^G04 Created by .* date |^; DRILL file .* date |^%TF\.CreationDate')


def committed(path):
    return subprocess.run(['git', 'show', 'HEAD:./' + path], capture_output=True, check=True).stdout


def lines(b):
    return [l for l in b.decode('utf-8', 'replace').splitlines() if not DATE.search(l)]


bad = []
zp = 'production/%s-gerbers.zip' % NAME
old, new = zipfile.ZipFile(io.BytesIO(committed(zp))), zipfile.ZipFile(zp)
if sorted(old.namelist()) != sorted(new.namelist()):
    bad.append('%s: file list differs: %s vs %s' % (zp, sorted(old.namelist()), sorted(new.namelist())))
for n in old.namelist():
    if n in new.namelist() and lines(old.read(n)) != lines(new.read(n)):
        bad.append('%s: %s differs' % (zp, n))
for p in ['production/%s-%s' % (NAME, f) for f in ('bom-pcbway.csv', 'cpl.csv', 'netlist.csv')]:
    if open(p, 'rb').read() != committed(p):
        bad.append('%s differs' % p)
for b in bad:
    print('::error::' + b)
if bad:
    print('Committed production files do not match what src/ produces. Rebuild (src/artwork.py, src/fab.py) and commit.')
    sys.exit(1)
print('Gerbers, drills, BOM, CPL and netlist match the committed files (date stamps aside).')
