# -*- coding: utf-8 -*-
"""Everything a board house needs, from one finished .kicad_pcb.

  <name>-gerbers.zip      copper, mask, paste, silk, outline + Excellon drills
                          (upload this for the bare board, JLCPCB or PCBWay)
  <name>-bom-jlcpcb.csv   Comment, Designator, Footprint, LCSC Part #
  <name>-cpl-jlcpcb.csv   Designator, Mid X, Mid Y, Layer, Rotation
  <name>-bom-pcbway.csv   PCBWay's assembly BOM columns (MPN + LCSC number)
  <name>-netlist.csv      every pad and its net, for checking against circuit.py
  <name>-assembly.pdf     parts outlines and references, top then bottom
  <name>-top.png / -bottom.png   rendered views
  ../mechanical/<name>.step       3D model of the assembled board

Pick-and-place coordinates are the Gerbers' own (KiCad absolute, y up), so
the two line up without any origin setting.  Rotation: 0 degrees is the
footprint's native orientation; every footprint either comes from JLCPCB's
own library entry for its part or is a standard two-terminal chip part, so
no per-part correction is needed.  Bottom parts are given as seen from the
bottom, which is 180 - (angle seen from the top).
"""
import csv, os, subprocess, zipfile, collections
import pcbnew
import parts, circuit

LAYERS = ['F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask', 'Edge.Cuts']


def copper_layers(board):
    n = pcbnew.LoadBoard(board).GetCopperLayerCount()
    return ['F.Cu'] + ['In%d.Cu' % i for i in range(1, n - 1)] + ['B.Cu']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('failed: %s\n%s\n%s' % (' '.join(cmd), r.stdout, r.stderr))
    return r.stdout


def gerbers(board, out_dir, name):
    gdir = os.path.join(out_dir, 'gerbers')
    os.makedirs(gdir, exist_ok=True)
    for f in os.listdir(gdir):
        os.remove(os.path.join(gdir, f))
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', ','.join(copper_layers(board) + LAYERS),
         '--subtract-soldermask',
         '--output', gdir + '/', board])
    run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm',
         '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', '--output', gdir + '/', board])
    zp = os.path.join(out_dir, '%s-gerbers.zip' % name)
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    return zp, sorted(os.listdir(gdir))


def _assembled(b, board_name):
    """(footprint, part-dict) for every part the assembler places."""
    comps = {c.ref: c for c in circuit.build(board_name)}
    out = []
    for fp in b.GetFootprints():
        c = comps.get(fp.GetReference())
        if c is None:
            raise SystemExit('footprint %s is not in circuit.py' % fp.GetReference())
        if c.part in parts.PARTS:
            out.append((fp, parts.PARTS[c.part]))
    if len(out) != sum(1 for c in comps.values() if c.part in parts.PARTS):
        raise SystemExit('board and circuit.py disagree on the assembled parts')
    return out


def _natural(ref):
    import re
    return tuple((0, int(t)) if t.isdigit() else (1, t) for t in re.findall(r'\d+|\D+', ref))


def bom_cpl(board, out_dir, name, board_name):
    b = pcbnew.LoadBoard(board)
    asm = _assembled(b, board_name)
    groups = collections.OrderedDict()
    for fp, p in sorted(asm, key=lambda a: (a[1]['lcsc'], _natural(a[0].GetReference()))):
        groups.setdefault(p['lcsc'], (p, []))[1].append(fp.GetReference())
    fpname = lambda p: p['fp'].split(':')[1]
    with open(os.path.join(out_dir, '%s-bom-jlcpcb.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for lcsc, (p, refs) in groups.items():
            w.writerow([p['value'], ','.join(sorted(refs, key=_natural)), fpname(p), lcsc])
    with open(os.path.join(out_dir, '%s-bom-pcbway.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Item #', 'Designator', 'Qty', 'Manufacturer Part Number', 'Description', 'Value',
                    'Package/Footprint', 'Type', 'LCSC Part #', 'Side'])
        for i, (lcsc, (p, refs)) in enumerate(groups.items(), 1):
            sides = sorted(set('Bottom' if fp.IsFlipped() else 'Top' for fp, q in asm if q['lcsc'] == lcsc))
            w.writerow([i, ','.join(sorted(refs, key=_natural)), len(refs), p['mpn'], p['desc'], p['value'],
                        fpname(p), 'SMD', lcsc, '+'.join(sides)])
    with open(os.path.join(out_dir, '%s-cpl-jlcpcb.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for fp, p in sorted(asm, key=lambda a: _natural(a[0].GetReference())):
            q = fp.GetPosition()
            rot = fp.GetOrientationDegrees()
            bottom = fp.IsFlipped()
            # a part whose JLCPCB library footprint is this board's land
            # pattern turned round (a second source on the same pads)
            off = p.get('jlc_rot', 0)
            if bottom and off:
                raise SystemExit('jlc_rot on a bottom-side part is not worked out: %s' % fp.GetReference())
            rot += off
            if bottom:
                rot = 180 - rot
            rot = round(rot % 360, 2) % 360
            w.writerow([fp.GetReference(), '%.4fmm' % (q.x / 1e6), '%.4fmm' % (-q.y / 1e6),
                        'Bottom' if bottom else 'Top', ('%g' % rot)])
    return len(asm), len(groups), sum(1 for fp, p in asm if fp.IsFlipped())


def netlist(board, out_dir, name):
    b = pcbnew.LoadBoard(board)
    rows = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                rows.append((p.GetNetname(), fp.GetReference(), p.GetNumber()))
    rows.sort(key=lambda r: (r[0], _natural(r[1]), r[2]))
    with open(os.path.join(out_dir, '%s-netlist.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Net', 'Reference', 'Pad'])
        w.writerows(rows)
    return len(rows)


def check_netlist(board, board_name):
    """The routed board must carry exactly circuit.py's connections."""
    b = pcbnew.LoadBoard(board)
    want = {}
    for c in circuit.build(board_name):
        for pad, net in c.pins.items():
            if net:
                want[(c.ref, pad)] = net
    got = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                got[(fp.GetReference(), p.GetNumber())] = p.GetNetname()
    bad = [(k, want.get(k), got.get(k)) for k in set(want) | set(got) if want.get(k) != got.get(k)]
    # footprints may carry extra same-net pads (e.g. repeated exposed-pad
    # numbers); only flag real disagreements
    bad = [x for x in bad if x[1] is not None]
    return bad


def assembly_pdf(board, out_dir, name):
    out = os.path.join(out_dir, '%s-assembly.pdf' % name)
    run(['kicad-cli', 'pcb', 'export', 'pdf', '--layers', 'F.Fab,F.Silkscreen,Edge.Cuts',
         '--mode-single', '--output', out + '.top.pdf', board])
    run(['kicad-cli', 'pcb', 'export', 'pdf', '--layers', 'B.Fab,B.Silkscreen,Edge.Cuts', '--mirror',
         '--mode-single', '--output', out + '.bottom.pdf', board])
    try:
        from pypdf import PdfWriter
        wr = PdfWriter()
        for part in (out + '.top.pdf', out + '.bottom.pdf'):
            wr.append(part)
        wr.write(out)
        for part in (out + '.top.pdf', out + '.bottom.pdf'):
            os.remove(part)
    except ImportError:
        os.rename(out + '.top.pdf', out.replace('.pdf', '-top.pdf'))
        os.rename(out + '.bottom.pdf', out.replace('.pdf', '-bottom.pdf'))
    return out


def renders(board, out_dir, name):
    outs = []
    for side in ('top', 'bottom'):
        o = os.path.join(out_dir, '%s-%s.png' % (name, side))
        run(['kicad-cli', 'pcb', 'render', '--side', side, '--width', '1600', '--height', '1600',
             '--quality', 'high', '--use-board-stackup-colors', '--output', o, board])
        outs.append(o)
    o = os.path.join(out_dir, '%s-iso.png' % name)
    run(['kicad-cli', 'pcb', 'render', '--width', '1600', '--height', '1200', '--quality', 'high',
         '--use-board-stackup-colors', '--rotate', '-45,0,-30', '--zoom', '0.9', '--output', o, board])
    outs.append(o)
    return outs


def silk_from_gerbers(gdir, out_png, name):
    """Both silkscreen layers read back from the Gerbers (not from KiCad):
    what the fab will print, the bottom mirrored to read as seen from
    below.  Needs gerbonara; skipped without it."""
    try:
        import warnings
        from gerbonara import GerberFile
        import pymupdf
        from PIL import Image
    except ImportError:
        return None
    ims = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for suffix in ('F_Silkscreen.gto', 'B_Silkscreen.gbo'):
            g = GerberFile.open(os.path.join(gdir, '%s-%s' % (name, suffix)))
            svg = str(g.to_svg(fg='black', bg='white', margin=1))
            pdf = pymupdf.open('pdf', pymupdf.open(stream=svg.encode(), filetype='svg').convert_to_pdf())
            pix = pdf[0].get_pixmap(dpi=1200)
            ims.append(Image.frombytes('RGB', (pix.width, pix.height), pix.samples))
    top, bot = ims[0], ims[1].transpose(Image.FLIP_LEFT_RIGHT)
    im = Image.new('RGB', (top.width + bot.width + 60, max(top.height, bot.height)), 'white')
    im.paste(top, (0, 0)); im.paste(bot, (top.width + 60, 0))
    im.save(out_png)
    return out_png


def step(board, out_path):
    """STEP of the assembled board, zipped: the raw file is ~18 MB, the zip
    a fifth of that, and every CAD tool reads the STEP inside."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    raw = out_path if out_path.endswith('.step') else out_path + '.step'
    run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '--force', '--output', raw, board])
    zp = raw[:-5] + '-step.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(raw, os.path.basename(raw))
    os.remove(raw)
    return zp


FP_LIB_TABLE = """(fp_lib_table
  (version 7)
  (lib (name "aio")(type "KiCad")(uri "${KIPRJMOD}/../aio.pretty")(options "")(descr "Ridge 3 stack footprints"))
)
"""


def install(src_pcb, dest_dir, name):
    """Copy a finished board into its folder in the repo, with its project,
    rules and a footprint table that finds ../aio.pretty, and point its 3D
    models at ../aio.3dshapes."""
    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.splitext(src_pcb)[0]
    dst = os.path.join(dest_dir, name + '.kicad_pcb')
    txt = open(src_pcb).read().replace('${KIPRJMOD}/aio.3dshapes/', '${KIPRJMOD}/../aio.3dshapes/')
    open(dst, 'w').write(txt)
    for ext in ('.kicad_pro', '.kicad_dru'):
        if os.path.exists(base + ext):
            shutil.copy(base + ext, os.path.join(dest_dir, name + ext))
    open(os.path.join(dest_dir, 'fp-lib-table'), 'w').write(FP_LIB_TABLE)
    return dst


def produce(board, board_name, name, v1_dir):
    """All outputs for one installed board.  Returns a summary dict."""
    d = os.path.dirname(board)
    prod = os.path.join(d, 'production')
    img = os.path.join(d, 'images')
    os.makedirs(prod, exist_ok=True); os.makedirs(img, exist_ok=True)
    zp, files = gerbers(board, prod, name)
    n_parts, n_lines, n_bottom = bom_cpl(board, prod, name, board_name)
    n_pads = netlist(board, prod, name)
    pdf = assembly_pdf(board, prod, name)
    pics = renders(board, img, name)
    silk = silk_from_gerbers(os.path.join(prod, 'gerbers'), os.path.join(img, name + '-silkscreen-from-gerbers.png'), name)
    if silk:
        pics.append(silk)
    stp = step(board, os.path.join(v1_dir, 'mechanical', name + '.step'))
    return dict(zip=zp, gerber_files=files, parts=n_parts, bom_lines=n_lines, bottom_parts=n_bottom,
                pads=n_pads, pdf=pdf, images=pics, step=stp)
