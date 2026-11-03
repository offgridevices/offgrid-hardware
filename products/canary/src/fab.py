"""Fabrication outputs for PCBWay (Gerbers, drill, BOM, CPL, netlist,
assembly drawing, renders) and the gates that check them.

Writes production/:
  canary-gerbers.zip        Gerbers (RS-274X, protel names) + Excellon drill
  canary-bom-pcbway.csv     PCBWay assembly BOM
  canary-cpl.csv            pick and place (top side only)
  canary-netlist.csv        net -> pins, from the board
  canary-assembly.pdf       assembly drawing (fab + silk, references visible)
"""
import csv, os, re, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit

PROD = os.path.join(ROOT, 'production')
OUT = os.path.join(ROOT, 'out')
KD = os.path.join(ROOT, 'tools', 'kd')
PCB = 'canary.kicad_pcb'


def kd(*cmd):
    r = subprocess.run([KD, *cmd], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('FAILED: ' + ' '.join(cmd) + '\n' + r.stdout + r.stderr)
    return r.stdout


def gerbers():
    g = os.path.join(OUT, 'gerbers')
    shutil.rmtree(g, ignore_errors=True)
    os.makedirs(g)
    kd('kicad-cli', 'pcb', 'export', 'gerbers', '--no-protel-ext', '-l',
       'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
       '--subtract-soldermask', '--use-drill-file-origin', '-o', 'out/gerbers/', PCB)
    kd('kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
       '--excellon-units', 'mm', '--generate-map', '--map-format', 'gerberx2', '-o', 'out/gerbers/', PCB)
    files = sorted(os.listdir(g))
    need = ['F_Cu', 'B_Cu', 'F_Mask', 'B_Mask', 'F_Silkscreen', 'B_Silkscreen', 'F_Paste', 'Edge_Cuts']
    for n in need:
        if not any(n in f for f in files):
            raise SystemExit('gerber missing: ' + n)
    if not any(f.endswith('-PTH.drl') for f in files):
        raise SystemExit('PTH drill file missing')
    z = os.path.join(PROD, 'canary-gerbers.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            info = zipfile.ZipInfo(f, date_time=(2026, 10, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            # strip creation dates so rebuilds are byte-identical
            txt = open(os.path.join(g, f), 'rb').read()
            txt = re.sub(rb'\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d([+-]\d\d:?\d\d)?', b'2026-10-14T00:00:00', txt)
            zf.writestr(info, txt)
    return files


def bom_cpl():
    pos = os.path.join(OUT, 'pos.csv')
    kd('kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front',
       '--exclude-dnp', '-o', 'out/pos.csv', PCB)
    rows = list(csv.DictReader(open(pos)))
    placed = {r['Ref']: r for r in rows}
    parts = {p['ref']: p for p in circuit.PARTS}
    # gate: CPL holds exactly the BOM parts
    bom_refs = {r for r, p in parts.items() if p['bom']}
    if set(placed) != bom_refs:
        raise SystemExit(f'CPL/BOM mismatch: only CPL {set(placed) - bom_refs}, only BOM {bom_refs - set(placed)}')
    with open(os.path.join(PROD, 'canary-cpl.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X (mm)', 'Mid Y (mm)', 'Layer', 'Rotation'])
        for ref in sorted(placed, key=_natural):
            r = placed[ref]
            w.writerow([ref, r['PosX'], r['PosY'], 'Top', r['Rot']])
    groups = {}
    for ref in sorted(bom_refs, key=_natural):
        p = parts[ref]
        key = (p['mpn'], p['value'], p['fp'])
        groups.setdefault(key, []).append(ref)
    with open(os.path.join(PROD, 'canary-bom-pcbway.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Item #', 'Designator', 'Qty', 'Manufacturer', 'Mfg Part #', 'Description / Value',
                    'Package/Footprint', 'Type', 'LCSC #', 'Your Instructions / Notes'])
        for i, ((mpn, val, fp), refs) in enumerate(groups.items(), 1):
            p = parts[refs[0]]
            note = ''
            if refs[0] in ('U3', 'U4', 'U5'):
                note = 'Sensirion gas/RH sensor: do not wash, no conformal coat; reflow last if multiple cycles'
            if refs[0] == 'U2':
                note = 'Program with production/canary.hex + fuses (see README)'
            if refs[0] == 'U5':
                note += '; SCD41-D-R1 (other reel size) is the same part'
            if mpn == 'CL21A106KAYNNNE':
                note = 'Alternate: any 10 uF X5R/X7R >= 10 V 0805 (e.g. CL21A106KPFNNNE)'
            if refs[0] == 'BZ1':
                note = 'Pads 3/4 are mechanical: solder all four'
            w.writerow([i, ','.join(refs), len(refs), p['mfr'], mpn, f"{p['desc']} ({val})",
                        fp.split(':')[1], 'SMD', p['lcsc'], note])
    return len(groups), len(bom_refs)


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


def netlist():
    kd('python3', '-c', f'''
import pcbnew, csv
b = pcbnew.LoadBoard("{PCB}")
nets = {{}}
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetCode() > 0 and not p.GetNetname().startswith("unconnected-"):
            nets.setdefault(p.GetNetname(), set()).add(fp.GetReference() + "." + p.GetNumber())
with open("production/canary-netlist.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Net", "Pins"])
    for n in sorted(nets):
        w.writerow([n, " ".join(sorted(nets[n]))])
''')


def schematic_pdf():
    kd('kicad-cli', 'sch', 'export', 'pdf', '-o', 'production/canary-schematic.pdf', 'canary.kicad_sch')


def assembly_pdf():
    kd('kicad-cli', 'pcb', 'export', 'pdf', '--mode-single', '-l', 'F.Fab,F.SilkS,Edge.Cuts',
       '--include-border-title', '-o', 'production/canary-assembly.pdf', PCB)


def renders():
    os.makedirs(os.path.join(ROOT, 'images'), exist_ok=True)
    common = ['--quality', 'high', '--use-board-stackup-colors', '--background', 'opaque', '-w', '1600', '-h', '1100']
    kd('kicad-cli', 'pcb', 'render', '--side', 'top', *common, '-o', 'images/canary-top.png', PCB)
    kd('kicad-cli', 'pcb', 'render', '--side', 'bottom', *common, '-o', 'images/canary-bottom.png', PCB)
    kd('kicad-cli', 'pcb', 'render', '--perspective', '--floor', '--rotate', '-40,0,-25', '--zoom', '1.1',
       *common, '-o', 'images/canary-iso.png', PCB)
    # 256-colour PNGs: a third of the size, no visible change
    for f in ('canary-top.png', 'canary-bottom.png', 'canary-iso.png'):
        p = os.path.join(ROOT, 'images', f)
        subprocess.run(['convert', p, '-colors', '256', 'PNG8:' + p], check=True)


def firmware():
    subprocess.run(['make', '-s', '-C', os.path.join(ROOT, 'firmware')], check=True)
    shutil.copy(os.path.join(ROOT, 'firmware', 'build', 'canary.hex'), os.path.join(PROD, 'canary.hex'))


if __name__ == '__main__':
    os.makedirs(PROD, exist_ok=True)
    files = gerbers()
    print('gerbers:', len(files), 'files')
    print('BOM lines %d, placed parts %d' % bom_cpl())
    netlist()
    assembly_pdf()
    schematic_pdf()
    firmware()
    subprocess.run([sys.executable, os.path.join(HERE, 'check_pins.py')], check=True)
    if '--no-renders' not in sys.argv:
        renders()
    print('fab outputs OK')
