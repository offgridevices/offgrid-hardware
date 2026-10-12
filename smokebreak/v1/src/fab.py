"""SmokeBreak v1: everything PCBWay needs, from the finished board.

    python3 fab.py            ../smokebreak.kicad_pcb -> ../fab/

  smokebreak-gerbers.zip       copper (6), mask, paste, silk, outline, drills (PTH + NPTH)
  smokebreak-bom-pcbway.csv    PCBWay's assembly BOM: designators, qty, manufacturer + MPN,
                               LCSC number, package, SMD/THT, notes
  smokebreak-cpl.csv           pick and place (top side, SMD only; through-hole parts are
                               hand-soldered and left out)
  smokebreak-netlist.csv       every pad and its net (checked against circuit.py here)
  smokebreak.step              the assembled board in 3D
  ../images/board-*.png        renders

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
OUT = os.path.join(B.V1, 'fab')
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
    g = os.path.join(OUT, 'gerbers')
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


def renders():
    os.makedirs(IMG, exist_ok=True)
    for side, extra in (('top', []), ('bottom', [])):
        run(['kicad-cli', 'pcb', 'render', '--side', side, '--width', '2400', '--height', '1400', '--zoom', '1.5',
             '--quality', 'high', '--background', 'opaque', '-o', os.path.join(IMG, f'board-{side}.png'), BOARD] + extra)
    run(['kicad-cli', 'pcb', 'render', '--side', 'top', '--rotate', '-35,0,25', '--width', '2400', '--height', '1500',
         '--zoom', '1.3', '--quality', 'high', '--background', 'opaque', '-o', os.path.join(IMG, 'board-iso.png'), BOARD])


def step():
    # kicad-cli exits non-zero when a part has no STEP model (it writes the
    # board without that part); the file is still good for the case design
    out = os.path.join(OUT, f'{NAME}.step')
    r = subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '--force', '-o', out, BOARD],
                       capture_output=True, text=True)
    if not os.path.exists(out):
        raise SystemExit('STEP export failed\n' + r.stdout + r.stderr)


if __name__ == '__main__':
    import sys
    os.makedirs(OUT, exist_ok=True)
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
    if bad:
        raise SystemExit(1)
