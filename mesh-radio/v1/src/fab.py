# -*- coding: utf-8 -*-
"""Everything a board house needs, from one finished .kicad_pcb.

  <name>-gerbers.zip      copper (all layers), mask, paste, silk, outline +
                          Excellon drills (upload this for the bare board,
                          JLCPCB or PCBWay)
  <name>-bom-jlcpcb.csv   Comment, Designator, Footprint, LCSC Part #
  <name>-cpl-jlcpcb.csv   Designator, Mid X, Mid Y, Layer, Rotation
  <name>-bom-pcbway.csv   PCBWay's assembly BOM columns (MPN, maker, DigiKey
                          and LCSC numbers)
  <name>-netlist.csv      every pad and its net, for checking against circuit.py
  <name>-assembly.pdf     parts outlines and references, top then bottom
  images/<name>-top.png / -bottom.png / -iso.png   rendered views
  ../mechanical/<name>-step.zip                    3D model of the assembled board

Adapted from Ridge 3 Lite's src/fab.py.  What differs here:
  * the parts the assembler does not place are in parts.PARTS with
    assembled=False (the test pads, the expansion header J7, fitted only
    when needed), not in a separate parts.PADS: they are on the board and
    in the netlist, but not in the BOM or CPL;
  * the M2 mounting hole (H1, board.build()) is a footprint that is not in
    circuit.py: it is board-only, and not assembled either;
  * the 3D models of this board's own footprints are named
    ${KIPRJMOD}/og.3dshapes/...; the renders and the STEP set KIPRJMOD to
    this revision's folder (models=), so a board anywhere (a work folder,
    out/) gets its models.

Pick-and-place coordinates are the Gerbers' own (KiCad absolute, y up), so
the two line up without any origin setting.  Rotation: 0 degrees is the
footprint's native orientation; the footprints come from JLCPCB's own
library entry for each part (src/footprints.py), or are KiCad's chip
footprints, so no per-part correction is needed (a part whose JLCPCB entry
is turned round carries jlc_rot in parts.py).  Two footprints are drawn in
footprints.py from the maker's drawing (the QPA9510's QFN-16 and the
Coilcraft 0908SQ): check them in JLCPCB's placement preview.  Bottom parts
are given as seen from the bottom, which is 180 - (angle seen from the
top).
"""
import csv, os, re, subprocess, zipfile, collections
import pcbnew
import parts, circuit, pcb

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)          # this revision's folder: og.pretty, og.3dshapes
LAYERS = ['F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask', 'Edge.Cuts']
# footprints board.build() adds that are not parts of the circuit
BOARD_ONLY = {'H%d' % (k + 1) for k in range(len(pcb.HOLES))}


def copper_layers(board):
    n = pcbnew.LoadBoard(board).GetCopperLayerCount()
    return ['F.Cu'] + ['In%d.Cu' % i for i in range(1, n - 1)] + ['B.Cu']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('failed: %s\n%s\n%s' % (' '.join(cmd), r.stdout, r.stderr))
    return r.stdout


def _models(models):
    """kicad-cli's define for this board's own 3D models (og.3dshapes)."""
    return ['-D', 'KIPRJMOD=%s' % os.path.abspath(models)]


def assembled(p):
    """Does the assembler place this part (a parts.PARTS entry)?"""
    return p.get('assembled', True) and not p.get('dnp')


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


def _assembled(b):
    """(footprint, part-dict) for every part the assembler places."""
    comps = {c.ref: c for c in circuit.build()}
    out = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref in BOARD_ONLY:
            continue
        c = comps.get(ref)
        if c is None:
            raise SystemExit('footprint %s is not in circuit.py' % ref)
        p = parts.PARTS[c.part]
        if assembled(p):
            out.append((fp, p))
    if len(out) != sum(1 for c in comps.values() if assembled(parts.PARTS[c.part])):
        raise SystemExit('board and circuit.py disagree on the assembled parts')
    return out


def _natural(ref):
    return tuple((0, int(t)) if t.isdigit() else (1, t) for t in re.findall(r'\d+|\D+', ref))


def _mount(fp):
    """PCBWay's assembly type: SMD, THT, or both (the USB-C's shell legs)."""
    smd = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in fp.Pads())
    tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads())
    return 'SMD+THT' if smd and tht else 'THT' if tht else 'SMD'


def bom_cpl(board, out_dir, name):
    b = pcbnew.LoadBoard(board)
    asm = _assembled(b)
    for fp, p in asm:
        if not p.get('lcsc'):
            raise SystemExit('%s (%s) is assembled but has no LCSC number' % (fp.GetReference(), p['mpn']))
    groups = collections.OrderedDict()
    for fp, p in sorted(asm, key=lambda a: (a[1]['lcsc'], _natural(a[0].GetReference()))):
        groups.setdefault(p['lcsc'], (p, []))[1].append(fp)
    fpname = lambda p: p['fp'].split(':')[1]
    refs = lambda fps: ','.join(sorted((fp.GetReference() for fp in fps), key=_natural))
    with open(os.path.join(out_dir, '%s-bom-jlcpcb.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for lcsc, (p, fps) in groups.items():
            w.writerow([p['value'], refs(fps), fpname(p), lcsc])
    with open(os.path.join(out_dir, '%s-bom-pcbway.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Item #', 'Designator', 'Qty', 'Manufacturer', 'Manufacturer Part Number', 'Description',
                    'Value', 'Package/Footprint', 'Type', 'DigiKey Part #', 'LCSC Part #', 'Side'])
        for i, (lcsc, (p, fps)) in enumerate(groups.items(), 1):
            sides = sorted(set('Bottom' if fp.IsFlipped() else 'Top' for fp in fps))
            w.writerow([i, refs(fps), len(fps), p.get('maker', ''), p['mpn'], p['desc'], p['value'],
                        fpname(p), _mount(fps[0]), p.get('digikey', ''), lcsc, '+'.join(sides)])
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


def check_netlist(board):
    """The routed board must carry exactly circuit.py's connections."""
    b = pcbnew.LoadBoard(board)
    want = {}
    for c in circuit.build():
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
    # numbers, the mounting hole's ground ring); only flag real disagreements
    bad = [x for x in bad if x[1] is not None]
    return sorted(bad, key=lambda x: (_natural(x[0][0]), x[0][1]))


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


def _compact_png(path):
    """Re-save a render as a 256-colour PNG (alpha kept): a third of the size,
    no visible change at this resolution.  The images are committed."""
    from PIL import Image
    im = Image.open(path).convert('RGBA')
    im.quantize(256, method=Image.Quantize.FASTOCTREE).save(path, optimize=True)


def renders(board, out_dir, name, models=V1):
    """Top and bottom (the board is 58 x 25.4 mm: a wide frame) and an
    isometric view, in the stackup's colours (black mask, white silk)."""
    outs = []
    for side in ('top', 'bottom'):
        o = os.path.join(out_dir, '%s-%s.png' % (name, side))
        run(['kicad-cli', 'pcb', 'render'] + _models(models) +
            ['--side', side, '--width', '2400', '--height', '1200', '--zoom', '1.6',
             '--quality', 'high', '--use-board-stackup-colors', '--output', o, board])
        _compact_png(o)
        outs.append(o)
    o = os.path.join(out_dir, '%s-iso.png' % name)
    run(['kicad-cli', 'pcb', 'render'] + _models(models) +
        ['--width', '2000', '--height', '1400', '--quality', 'high', '--use-board-stackup-colors',
         '--rotate', '-45,0,-30', '--zoom', '1.3', '--output', o, board])
    _compact_png(o)
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
    # the board is long and narrow: top above bottom
    top, bot = ims[0], ims[1].transpose(Image.FLIP_LEFT_RIGHT)
    im = Image.new('RGB', (max(top.width, bot.width), top.height + bot.height + 60), 'white')
    im.paste(top, (0, 0)); im.paste(bot, (0, top.height + 60))
    im.save(out_png)
    return out_png


def step(board, out_path, models=V1):
    """STEP of the assembled board, zipped (every CAD tool reads the STEP
    inside).  Parts the assembler does not place have no 3D model."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    raw = out_path if out_path.endswith('.step') else out_path + '.step'
    run(['kicad-cli', 'pcb', 'export', 'step'] + _models(models) +
        ['--subst-models', '--force', '--output', raw, board])
    zp = raw[:-5] + '-step.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(raw, os.path.basename(raw))
    os.remove(raw)
    return zp


FP_LIB_TABLE = """(fp_lib_table
  (version 7)
  (lib (name "og")(type "KiCad")(uri "${KIPRJMOD}/og.pretty")(options "")(descr "Mesh Radio footprints"))
)
"""


def install(src_pcb, dest_dir, name):
    """Copy a finished board into its folder in the repo, with its project
    (KiCad 10 keeps the design rules and net classes in the .kicad_pro),
    rules and a footprint table that finds og.pretty (its 3D models already
    point at og.3dshapes beside it)."""
    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.splitext(src_pcb)[0]
    dst = os.path.join(dest_dir, name + '.kicad_pcb')
    if not os.path.exists(base + '.kicad_pro'):
        raise SystemExit('%s has no .kicad_pro: its rules and net classes would be lost' % src_pcb)
    shutil.copy(src_pcb, dst)
    pcb.copy_project(src_pcb, dst)
    if os.path.exists(base + '.kicad_dru'):
        shutil.copy(base + '.kicad_dru', os.path.join(dest_dir, name + '.kicad_dru'))
    open(os.path.join(dest_dir, 'fp-lib-table'), 'w').write(FP_LIB_TABLE)
    refresh_models(dst)
    return dst


def refresh_models(path):
    """Give every footprint on the board its og.pretty footprint's 3D
    models (copper untouched): a board routed before a model was added
    still gets it."""
    lib = os.path.join(V1, 'og.pretty')
    b = pcbnew.LoadBoard(path)
    for fp in b.GetFootprints():
        src = pcbnew.FootprintLoad(lib, fp.GetFPID().GetLibItemName().wx_str())
        if src is None:
            continue
        fp.Models().clear()
        for m in src.Models():
            fp.Models().append(m)
    pcb.save_board(b, path)


def produce(board, name, v1_dir, pictures=True, models=V1):
    """All outputs for one installed board.  Returns a summary dict.
    Writes <board folder>/production, <board folder>/images and
    <v1_dir>/mechanical.  pictures=False leaves out the renders, the
    silkscreen preview and the STEP (slow, and not what the fab is sent):
    CI's fab-file check."""
    d = os.path.dirname(os.path.abspath(board))
    prod = os.path.join(d, 'production')
    img = os.path.join(d, 'images')
    os.makedirs(prod, exist_ok=True); os.makedirs(img, exist_ok=True)
    zp, files = gerbers(board, prod, name)
    n_parts, n_lines, n_bottom = bom_cpl(board, prod, name)
    n_pads = netlist(board, prod, name)
    pdf = assembly_pdf(board, prod, name)
    pics, stp = [], None
    if pictures:
        pics = renders(board, img, name, models)
        silk = silk_from_gerbers(os.path.join(prod, 'gerbers'), os.path.join(img, name + '-silkscreen-from-gerbers.png'), name)
        if silk:
            pics.append(silk)
        stp = step(board, os.path.join(v1_dir, 'mechanical', name + '.step'), models)
    return dict(zip=zp, gerber_files=files, parts=n_parts, bom_lines=n_lines, bottom_parts=n_bottom,
                pads=n_pads, pdf=pdf, images=pics, step=stp)
