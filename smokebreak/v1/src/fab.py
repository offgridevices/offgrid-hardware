"""SmokeBreak v1: everything PCBWay needs, from the finished board.

    python3 fab.py            ../smokebreak.kicad_pcb -> ../production/, ../mechanical/, ../images/
    python3 fab.py --no-3d    production files and the gates only (what CI runs)

Gates (exit 1 on a failure): KiCad DRC 0 errors / 0 warnings / 0 unconnected,
every pad's net equal to circuit.py.

production/
  smokebreak-gerbers.zip       copper (6), mask, paste, silk, outline, drills (PTH + NPTH)
  smokebreak-bom-pcbway.csv    PCBWay's assembly BOM: designators, qty, manufacturer + MPN,
                               LCSC number, package, SMD/THT, notes
  smokebreak-cpl.csv           pick and place (top side, SMD only; through-hole parts are
                               hand-soldered and left out)
  smokebreak-netlist.csv       every pad and its net (checked against circuit.py here)
mechanical/smokebreak-step.zip the assembled board in 3D (STEP, zipped)
images/board-*.png             renders (256-colour PNG)

Upload the Gerber zip for the bare board, then the BOM and CPL for
assembly.  PCBWay matches parts by manufacturer part number; the LCSC
number is there for the same part from LCSC.
"""
import csv
import os
import re
import shutil
import subprocess
import zipfile

import pcbnew

import board as B
import circuit
import parts

BOARD = os.path.join(B.V1, 'smokebreak.kicad_pcb')
OUT = os.path.join(B.V1, 'production')
MECH = os.path.join(B.V1, 'mechanical')
WORK = os.path.join(B.HERE, 'out', 'fab')
IMG = os.path.join(B.V1, 'images')
NAME = 'smokebreak'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('failed: %s\n%s\n%s' % (' '.join(cmd), r.stdout, r.stderr))
    return r.stdout


def natural(ref):
    return tuple((0, int(t)) if t.isdigit() else (1, t) for t in re.findall(r'\d+|\D+', ref))


def gerbers():
    g = os.path.join(WORK, 'gerbers')
    shutil.rmtree(g, ignore_errors=True)
    os.makedirs(g)
    layers = 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', layers, '--subtract-soldermask',
         '--output', g + '/', BOARD])
    run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm',
         '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', '--output', g + '/', BOARD])
    zp = os.path.join(OUT, f'{NAME}-gerbers.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(g)):
            z.write(os.path.join(g, f), f)
    shutil.rmtree(g)
    return zp


def bom_and_cpl(b):
    groups = {}
    cpl = []
    for fp in sorted(b.GetFootprints(), key=lambda f: natural(f.GetReference())):
        ref = fp.GetReference()
        c = circuit.COMPONENTS[ref]
        p = parts.PARTS[c['part']]
        if p['fit'] == 'none':
            continue
        key = p['mpn']
        groups.setdefault(key, (p, c, []))[2].append(ref)
        if p['fit'] == 'smt':
            q = fp.GetPosition()
            cpl.append([ref, c['value'] or p['mpn'], p['fp'].split(':')[1],
                        f'{pcbnew.ToMM(q.x):.3f}', f'{-pcbnew.ToMM(q.y):.3f}',
                        f'{fp.GetOrientationDegrees() % 360:.1f}', 'Top' if fp.GetLayer() == pcbnew.F_Cu else 'Bottom'])
    # parts that are not on the board but ship with it (the display)
    for ref, c in circuit.COMPONENTS.items():
        p = parts.PARTS[c['part']]
        if p['fit'] == 'off':
            groups.setdefault(p['mpn'], (p, c, []))[2].append(ref)
    rows = []
    order = sorted(groups.values(), key=lambda v: ({'smt': 0, 'tht': 1, 'off': 2}[v[0]['fit']], natural(v[2][0])))
    for i, (p, c, refs) in enumerate(order, 1):
        refs = sorted(refs, key=natural)
        note = {'smt': '', 'tht': 'Through-hole: supplied loose, hand-soldered by OffGrid (do not fit)',
                'off': 'Not on the board: supplied loose (plugs into J7)'}[p['fit']]
        if 'onsign' in p['desc']:
            note = ('LCSC has no stock: please source by MPN (Digi-Key / Mouser), or OffGrid consigns it. '
                    'Do not substitute. ' + note).strip()
        rows.append([i, ','.join(refs), len(refs), p['mfr'], p['mpn'], p['desc'], c['value'] or '',
                     p['fp'].split(':')[1] if p['fp'] else '', 'SMD' if p['fit'] == 'smt' else 'THT' if p['fit'] == 'tht' else '-',
                     p['lcsc'] or '', note])
    with open(os.path.join(OUT, f'{NAME}-bom-pcbway.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Item #', 'Designator', 'Qty', 'Manufacturer', 'Mfg Part #', 'Description', 'Value',
                    'Package/Footprint', 'Type', 'LCSC Part #', 'Your Instructions / Notes'])
        w.writerows(rows)
    with open(os.path.join(OUT, f'{NAME}-cpl.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Value', 'Footprint', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        w.writerows(sorted(cpl, key=lambda r: natural(r[0])))
    return rows, cpl


def netlist(b):
    bad = []
    with open(os.path.join(OUT, f'{NAME}-netlist.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Pad', 'Net'])
        for fp in sorted(b.GetFootprints(), key=lambda f: natural(f.GetReference())):
            ref = fp.GetReference()
            want = circuit.COMPONENTS[ref]['pins']
            for p in sorted(fp.Pads(), key=lambda p: natural(p.GetNumber() or '~')):
                n = p.GetNumber()
                w.writerow([ref, n, p.GetNetname()])
                if n and (want.get(n) or '') != p.GetNetname():
                    bad.append((ref, n, want.get(n), p.GetNetname()))
    return bad


def quantize(path):
    """Renders as 256-colour PNG: about a third of the size, no visible change."""
    from PIL import Image
    Image.open(path).convert('RGB').quantize(256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)


def renders():
    os.makedirs(IMG, exist_ok=True)
    jobs = [('board-top', ['--side', 'top', '--width', '2000', '--height', '1160', '--zoom', '1.5']),
            ('board-bottom', ['--side', 'bottom', '--width', '2000', '--height', '1160', '--zoom', '1.5']),
            ('board-iso', ['--side', 'top', '--rotate', '-35,0,25', '--width', '2000', '--height', '1250', '--zoom', '1.3'])]
    for name, args in jobs:
        out = os.path.join(IMG, name + '.png')
        run(['kicad-cli', 'pcb', 'render'] + args + ['--quality', 'high', '--background', 'opaque', '-o', out, BOARD])
        quantize(out)


def step():
    """The board in 3D for the case design, zipped (a 3D model with no STEP
    makes kicad-cli exit non-zero; it still writes the rest)."""
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(MECH, exist_ok=True)
    out = os.path.join(WORK, f'{NAME}.step')
    r = subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--force', '-o', out, BOARD],
                       capture_output=True, text=True)
    if not os.path.exists(out):
        raise SystemExit('STEP export failed\n' + r.stdout + r.stderr)
    with zipfile.ZipFile(os.path.join(MECH, f'{NAME}-step.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(out, f'{NAME}.step')


def drc():
    """KiCad's DRC with the zones refilled: 0 errors, 0 warnings, 0 unconnected."""
    import json
    os.makedirs(WORK, exist_ok=True)
    out = os.path.join(WORK, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--severity-all', '--format', 'json', '-o', out,
                    BOARD], capture_output=True)
    r = json.load(open(out))
    return len([v for v in r['violations'] if v['severity'] == 'error']), \
        len([v for v in r['violations'] if v['severity'] != 'error']), len(r['unconnected_items'])


if __name__ == '__main__':
    import sys
    os.makedirs(OUT, exist_ok=True)
    e, w, u = drc()
    print(f'DRC      {e} errors, {w} warnings, {u} unconnected')
    b = pcbnew.LoadBoard(BOARD)
    print('gerbers ', gerbers())
    rows, cpl = bom_and_cpl(b)
    print(f'BOM      {len(rows)} lines, CPL {len(cpl)} placements')
    bad = netlist(b)
    print('netlist ', 'matches circuit.py' if not bad else f'{len(bad)} pads differ: {bad[:5]}')
    if '--no-3d' not in sys.argv:
        step()
        renders()
        print('step + renders done')
    if bad or e or w or u:
        raise SystemExit(1)
