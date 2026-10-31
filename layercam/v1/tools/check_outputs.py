"""CI: the fab files make.py just wrote must equal the committed ones.

    python3 tools/check_outputs.py      (from layercam/v1, after make.py)

Compares each board's outputs (main/, ring/, usb/) against git HEAD.  The
Gerber zip is compared file by file with the creation-date stamps KiCad
writes left out (they change every run); the BOM, CPL, netlist and design
rules (.kicad_dru, written from src/pcb.py) must be byte-identical.  Exits
1 on a difference.  The assembly PDF is not compared: it embeds its
creation time and is drawn from the same board file as the Gerbers."""
import io, re, subprocess, sys, zipfile

BOARDS = ('main', 'ring', 'usb')
DATE = re.compile(r'CreationDate|^G04 Created by .* date |^; DRILL file .* date ')


def committed(path):
    return subprocess.run(['git', 'show', 'HEAD:./' + path], capture_output=True, check=True).stdout


def lines(b):
    return [l for l in b.decode('utf-8', 'replace').splitlines() if not DATE.search(l)]


bad = []
for bd in BOARDS:
    name = 'layercam-' + bd
    zp = '%s/production/%s-gerbers.zip' % (bd, name)
    old, new = zipfile.ZipFile(io.BytesIO(committed(zp))), zipfile.ZipFile(zp)
    if sorted(old.namelist()) != sorted(new.namelist()):
        bad.append('%s: file list differs: %s vs %s' % (zp, sorted(old.namelist()), sorted(new.namelist())))
    for n in old.namelist():
        if n in new.namelist() and lines(old.read(n)) != lines(new.read(n)):
            bad.append('%s: %s differs' % (zp, n))
    for p in ['%s/production/%s-%s' % (bd, name, f) for f in ('bom-pcbway.csv', 'cpl.csv', 'netlist.csv')] + ['%s/%s.kicad_dru' % (bd, name)]:
        if open(p, 'rb').read() != committed(p):
            bad.append('%s differs' % p)
for b in bad:
    print('::error::' + b)
if bad:
    print('Committed fab files do not match what src/make.py produces. Rebuild and commit the outputs.')
    sys.exit(1)
print('Gerbers, drills, BOM, CPL, netlist and design rules of all three boards match the committed files '
      '(date stamps aside).')
