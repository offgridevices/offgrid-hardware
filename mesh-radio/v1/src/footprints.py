# -*- coding: utf-8 -*-
"""Build ../og.pretty, the board's own footprint library.

Three kinds of footprint go in (the same approach as Ridge 3 Lite's
src/footprints.py, which this file is adapted from):

1. JLCPCB/EasyEDA footprints for the exact LCSC parts, converted once with
   easyeda2kicad and kept verbatim in easyeda_raw/.  They are cleaned here:
   - the converter draws each courtyard round the package BODY only, which
     leaves the pads outside it, so KiCad's courtyard checks would pass two
     parts sitting on each other's pads.  The courtyard is rebuilt as the
     box round pads + body + 0.10 mm.
   - silkscreen is dropped.  At this density a component outline on the
     silk is noise that lands on pads; the assembly drawing carries the
     outlines and reference designators instead.  A small pin-1 dot stays
     on the Fab layer, so the assembly drawing still shows which way round
     each part goes.
   - 3D models point at ../og.3dshapes (gzip STEP, KiCad reads .stpZ).
   - custom (polygon) pads that are plain rectangles become rect pads; any
     other polygon (a QFN's chamfered corner pads) stays a polygon, drawn
     with no outline width so the copper is exactly the polygon EasyEDA
     gives.
   - FIXUPS below gives a footprint the name parts.py uses for it, and
     renames pads to the datasheet / circuit.py names.  The raw files stay
     verbatim.
2. KiCad's own library footprints for the chip passives, the test pad and
   the M2 mounting hole: pads and 3D model untouched, silkscreen dropped,
   courtyard rebuilt the same way (0.10 mm, IPC-7351 density level L; the
   library uses level N, 0.25 mm).
3. Footprints drawn here from the maker's land pattern where EasyEDA has
   none or a wrong one: the QPA9510 amplifier (QFN-16 3 x 3), the
   Coilcraft 0908SQ air-core inductor, and the expansion header's two pin
   rows.

Run with KiCad's Python inside the pinned image:
    tools/kd python3 src/footprints.py
It uses pcbnew to write the footprints so each file is in KiCad's own format.
"""
import os, sys, glob, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'og.pretty'))
RAW = os.path.join(HERE, 'easyeda_raw')
MODELS = os.path.normpath(os.path.join(HERE, '..', 'og.3dshapes'))
KISTD = '/usr/share/kicad/footprints'                 # KiCad's library, in the image
KIMOD = os.environ.get('KICAD10_3DMODEL_DIR', '/usr/share/kicad/3dmodels')

MM = pcbnew.FromMM
def _save(lib, fp): pcbnew.FootprintSave(lib, fp)

# --- a minimal s-expression reader/writer, so the EasyEDA files can be
#     edited as data (pcbnew's Remove() leaves the SWIG pad list unusable).
def _parse(s):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    st = [[]]
    for t in toks:
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop(); st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0][0]

def _emit(n, ind=0):
    if not isinstance(n, list):
        return n
    if all(not isinstance(c, list) for c in n):
        return '(' + ' '.join(n) + ')'
    out = '(' + n[0]
    for c in n[1:]:
        if isinstance(c, list):
            out += '\n' + '\t' * (ind + 1) + _emit(c, ind + 1)
        else:
            out += ' ' + c
    return out + '\n' + '\t' * ind + ')'

def _get(n, key):
    for c in n:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None

def _poly_pts(p):
    """(x, y) points of a custom pad's polygon, relative to the pad."""
    pts = _get(_get(_get(p, 'primitives'), 'gr_poly'), 'pts')
    return [(float(q[1]), float(q[2])) for q in pts[1:]]

def _pad_box(p):
    at = _get(p, 'at'); sz = _get(p, 'size')
    x, y = float(at[1]), float(at[2]); rot = float(at[3]) if len(at) > 3 else 0.0
    if p[3] == 'custom':                  # EasyEDA custom pads are never rotated
        pts = _poly_pts(p)
        return (x + min(q[0] for q in pts), y + min(q[1] for q in pts),
                x + max(q[0] for q in pts), y + max(q[1] for q in pts))
    w, h = float(sz[1]), float(sz[2])
    if round(rot) % 180 == 90:
        w, h = h, w
    elif round(rot) % 90:
        # a pad turned 45 degrees (the X2SON's exposed pad): its box is
        # the diagonal both ways
        w = h = (w + h) / 2 ** 0.5
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2

def _area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2

# Per-footprint corrections, applied to the parsed EasyEDA file (keyed by
# the EasyEDA name, which is the raw file's name).
#   'as':     the name the footprint gets in og.pretty (parts.py's 'fp')
#   'rename': {EasyEDA pad name: pad name used here}
#   'resize': {pad name: (w, h)} in the footprint's own axes (rotation 0)
#   'trim':   {pad name: d} shortens a pad by d mm at its +y end
#   'model':  a 3D model (in ../og.3dshapes) for a part EasyEDA has none for
#   'model_offset': (x, y, z) mm for the 3D model (KiCad's 3D axes, y up)
#   'skip':   kept in easyeda_raw/ for the record, not built (reason given)
#
# Every footprint below was checked pad by pad against the parts.py pin
# table and the maker's pin diagram (top view; ball grids by handedness, so
# a bottom-view drawing read the wrong way round would show up):
#   TPS63810YFF, TPS62840YBG: TI's "Top View" ball maps; TPS22916YFP: TI's
#   laser-marking (top) view; SSM10N954L: Toshiba's pin assignment drawing
#   (pads seen through the top, pin 1 dot) and package drawing (1.04 x
#   0.175 mm source lands, 0.25 mm gate balls, rows 0.325 / 0.425 apart);
#   TPS2121RUX: TI's bottom view, mirrored, and TI's land pattern
#   (RUX0012A: 4 x 1.05 x 0.4 mm power pads, 8 x 0.6 x 0.2 mm, rows 2.3 mm
#   apart) - EasyEDA's matches it.
FIXUPS = {
    # Abracon ABS07 32.768 kHz crystal (C276424)
    'OSC-SMD_L3.2-W1.5': {'as': 'ABS07'},
    # Murata DFE201610E (2.0 x 1.6, "0806") 2.2 uH, C337891
    'L0806': {'as': 'L_0806'},
    # Murata DFE252012F (2.5 x 2.0, "1008") 0.47 uH, C703140: EasyEDA files
    # it under the MHCD252012B land, the same 2.5 x 2.0 body
    'IND-SMD_L2.5-W2.0_MHCD252012B-2R2M-A8L': {'as': 'L_1008'},
    # Rohm RB060MM-30 (PMDU = SOD-123FL), C308720: pad 1 = cathode (the band)
    'SOD-123_L2.8-W1.8-LS3.7-RD': {'as': 'SOD-123FL'},
    # Rohm UDZV 4.7 V zener (UMD2 = SOD-323FL), C209560: pad 1 = cathode
    'SOD-323_L1.7-W1.3-LS2.5-RD-1': {'as': 'SOD-323FL'},
    # Toshiba SSM3K56ACT (CST3), C146308: 1 gate, 2 source, 3 drain
    'SOT-883-3_L1.0-W0.6-BR': {'as': 'SOT-883'},
    # TI LM66100DCK, C2869734
    'SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL': {'as': 'SC-70-6'},
    # TI TPS2121RUX, C485916 (2.0 x 2.5 mm VQFN-HR; checked above)
    'VQFN-HR-12_L2.5-W2.0-P0.50-BL': {'as': 'VQFN-12_TPS2121RUX'},
    # TI TPS22916CYFP, C2680319 (checked above)
    'DSBGA-4_L0.8-W0.8-R2-C2-P0.40-BL': {'as': 'DSBGA-4_TPS22916'},
    # ADI MAX17608ATC+T, C2155884 (TDFN-12 3 x 3, 0.5 mm): pads 1-6 along one
    # side and 7-12 back along the other, counter-clockwise from the top as
    # on ADI's "TOP VIEW"; pad 13 = the exposed pad (GND)
    # TI TPS22950YBHR, C3230039 (YBH DSBGA-6, 0.4 mm pitch both ways, as on
    # TI's YBH0006-C02 drawing): pads named by ball, A1 ON, A2 FLT, B1 VIN,
    # B2 VOUT, C1 GND, C2 ILIM
    # TI CSD25310Q2(T), C2871649: EasyEDA files it under CSD17571Q2's land,
    # the same DQK 2 x 2 SON.  Checked against TI's DQK drawing (4210192/B)
    # and the CSD25310Q2 top view: 1, 2, 5, 6 source, 3 gate, 4 drain; pad 7
    # (the large exposed pad, by pins 1 and 6) is source, pad 8 (the small
    # one, by pins 3 and 4) is drain
    'WSON-6_L2.0-W2.0-P0.65-BL_CSD17571Q2': {'as': 'WSON-6_DQK_CSD25310Q2'},
    # Abracon ABM11W 2016 crystal, C5189005: pads 2 and 4 are both the lid
    # (ground).  circuit.py names the ground pin '2' only (the symbol has
    # one ground pin), so pad 4 is numbered 2 as well: both are then the
    # same net and neither is left floating.
    # EasyEDA has no 3D model for it: the same-size 2.0 x 1.6 mm ECS
    # oscillator body stands in (renders and STEP only)
    'CRYSTAL-SMD_4P-L2.0-W1.6-BL_CXAN-211': {'rename': {'4': '2'}, 'model': 'OSC-SMD_4P-L2.0-W1.6-H0.8'},
    # Toshiba SSM10N954L: no 3D model anywhere; a plain box (box3d.py)
    'CSP-10L_SSM10N954L': {'model': 'BOX_TCSPED-302701'},
    # ECS-TXO-20CSMV4 TCXO (C54284784): EasyEDA has no entry for that LCSC
    # number, so the raw file is C19858587's, the same ECS 2.0 x 1.6 mm
    # 4-pad package.  Pads counter-clockwise from 1 at the bottom left.
    #
    # JST S2B-PH-SM4-TB (C295747), the battery plug: pad numbers as
    # EasyEDA gives them.  Checked against JST's PH catalogue ("SMT type,
    # viewed from component side", side entry): EasyEDA pad 1 (at -1.0,
    # -2.93) is JST circuit No.1.  The contact tails (pads 1, 2) are at the
    # back of the housing, toward -y; the mating opening faces +y, the
    # side with the two fitting-nail pads (3, 4), and the body reaches
    # y = +4.37.  So with the opening facing down the page (rotation 0),
    # circuit 1 is the left pad seen from the top.
    #
    # Coilcraft 0908SQ-8N1 (C19191636): EasyEDA's IND-SMD_L2.1-W1.5 puts
    # 0.86 x 1.62 mm pads 1.8 mm apart across a 2.1 x 1.5 mm body, which
    # is not the 0908SQ (coil 1.47 long, 2.13 wide, its wire ends lie on
    # lands 1.12 mm apart).  It is drawn from Coilcraft's land pattern in
    # coilcraft_0908sq_fp() instead.
    'IND-SMD_L2.1-W1.5': {'skip': True},
    # the battery plug's EasyEDA 3D body sits 1.0 mm toward pad 2 and
    # 2.7 mm toward the fitting nails from the pads; moved so its contact
    # tails end on pads 1 and 2 (checked in a render; 3D y is up)
    'CONN-SMD_P2.00_S2B-PH-SM4-TB-LF-SN': {'model_offset': (1.0, -2.7, 0)},
    # Amphenol 12401610E4#2A USB-C (C5119948), checked against Amphenol's
    # customer drawing 12401610 rev C, sheet 2 "Recommended PCB Layout":
    # signal pads 0.30 x 0.70 (EasyEDA draws 0.25), and two locating pegs
    # 7.20 mm apart on the line y = -3.27: a 0.65 mm round hole on the left
    # (EasyEDA has it) and a 0.95 x 0.65 mm slot on the right (EasyEDA
    # leaves it out).  The board edge belongs at y = +5.48: the shell's
    # front sits 0.84 mm past it (layout.py).
    'USB-C-SMD_TYPE-C-24P': {
        'resize': {p: (0.30, 0.70) for p in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'A11', 'A12', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11', 'B12']},
        'add': ['(pad "" np_thru_hole oval (at 3.60 -3.27) (size 0.95 0.65) (drill oval 0.95 0.65) (layers *.Cu *.Mask))'],
        # EasyEDA's 3D body sits 6.3 mm behind the pads; moved so its front
        # is 0.84 mm past the board edge, as on the drawing (3D y is up)
        'model_offset': (0, -6.3, 0),
    },
}

def _fix_pad(name, p):
    fx = FIXUPS.get(name, {})
    num = p[1].strip('"')
    if num in fx.get('rename', {}):
        num = fx['rename'][num]
        p[1] = '"%s"' % num
    if num in fx.get('resize', {}):
        w, h = fx['resize'][num]
        at = _get(p, 'at')
        if len(at) > 3 and round(float(at[3])) % 180 == 90:
            w, h = h, w
        _get(p, 'size')[1:] = ['%.3f' % w, '%.3f' % h]
    if num in fx.get('trim', {}):
        d = fx['trim'][num]
        at, size = _get(p, 'at'), _get(p, 'size')
        if len(at) > 3 and round(float(at[3])) % 180:
            raise ValueError('trim: pad %s of %s is rotated' % (num, name))
        at[2] = '%.4f' % (float(at[2]) - d / 2)
        size[2] = '%.4f' % (float(size[2]) - d)

def _item_box(it):
    xs, ys = [], []
    for k in ('start', 'end', 'center', 'mid'):
        c = _get(it, k)
        if c:
            xs.append(float(c[1])); ys.append(float(c[2]))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None

def _line(x0, y0, x1, y1, layer, w):
    return ['fp_line', ['start', '%.3f' % x0, '%.3f' % y0], ['end', '%.3f' % x1, '%.3f' % y1],
            ['layer', layer], ['width', '%.3f' % w]]

# Pin-1 dot on the Fab layer: a ring of 0.15 mm diameter drawn 0.1 wide,
# so it reads as a 0.25 mm dot on the assembly drawing.
DOT_R, DOT_W = 0.075, 0.10

def _dot_near(x, y, w, h):
    """Where the pin-1 dot goes for a pad at (x, y), w x h: just outside the
    pad, on the side away from the footprint's centre."""
    d = (x * x + y * y) ** 0.5
    ux, uy = (x / d, y / d) if d > 1e-6 else (-1.0, 0.0)
    r = max(w, h) / 2 + 0.2
    return x + ux * r, y + uy * r

def clean_easyeda(path):
    raw = os.path.splitext(os.path.basename(path))[0]
    fx = FIXUPS.get(raw, {})
    name = fx.get('as', raw)
    t = _parse(open(path).read())
    out = ['footprint', '"%s"' % name]
    boxes, model, dots, pin1, plated = [], None, [], None, False
    for c in t[2:]:
        if not isinstance(c, list):
            continue
        k = c[0]
        if k in ('fp_line', 'fp_circle', 'fp_arc', 'fp_poly'):
            lay = _get(c, 'layer')[1].strip('"')
            if lay == 'Cmts.User':
                # EasyEDA's own pin-1 dot (a small circle by the package
                # corner); kept as the Fab marker when there is exactly one
                if k == 'fp_circle':
                    dots.append(c)
                continue
            if lay == 'F.SilkS':
                continue
            if lay == 'F.CrtYd':            # body outline -> fab layer
                _get(c, 'layer')[1] = 'F.Fab'
                w = _get(c, 'width')
                if w: w[1] = '0.100'
            b = _item_box(c)
            if b: boxes.append(b)
            out.append(c)
        elif k == 'pad':
            if c[3] == 'custom':
                pts = _poly_pts(c)
                px = [q[0] for q in pts]; py = [q[1] for q in pts]
                bw, bh = max(px) - min(px), max(py) - min(py)
                if _area(pts) > 0.98 * bw * bh:
                    # a plain rectangle (the eFuse's corner pads)
                    c = [x for x in c if not (isinstance(x, list) and x[0] == 'primitives')]
                    c[3] = 'rect'
                    _get(c, 'size')[1:] = ['%.3f' % bw, '%.3f' % bh]
                    cx, cy = (max(px) + min(px)) / 2, (max(py) + min(py)) / 2
                    if abs(cx) > 0.001 or abs(cy) > 0.001:
                        at = _get(c, 'at')
                        at[1] = '%.3f' % (float(at[1]) + cx); at[2] = '%.3f' % (float(at[2]) + cy)
                else:
                    # chamfered QFN corner pads: keep the polygon, but with
                    # no outline width (EasyEDA's 0.1 mm would grow every
                    # edge by 0.05 mm)
                    _get(_get(_get(c, 'primitives'), 'gr_poly'), 'width')[1] = '0'
            _fix_pad(raw, c)
            if c[1] == '""' and c[2] == 'thru_hole':
                # locating pegs are drawn as plated holes with no copper
                # ring; they are plastic posts, so make them non-plated
                c[2] = 'np_thru_hole'
            if c[2] == 'thru_hole':
                plated = True
            if c[2] != 'np_thru_hole' and c[1] != '""':
                boxes.append(_pad_box(c))
                if c[1].strip('"') in ('1', 'A1') and pin1 is None:
                    pin1 = _pad_box(c)
            out.append(c)
        elif k == 'fp_text':
            if c[1] == 'reference':
                c[2] = 'REF**'
                _get(c, 'at')[1:] = ['0', '0']
                _get(c, 'layer')[1] = 'F.Fab'
                f = _get(_get(c, 'effects'), 'font')
                _get(f, 'size')[1:] = ['0.5', '0.5']; _get(f, 'thickness')[1] = '0.08'
                out.append(c)
            elif c[1] == 'value':
                c[2] = name
                i = c.index(_get(c, 'layer')); c.insert(i + 1, 'hide'); out.append(c)
        elif k == 'model':
            model = c
        elif k == 'attr':
            out.append(c)
        elif k in ('descr', 'property', 'layer'):
            out.append(c)
    for extra in fx.get('add', []):
        out.append(_parse(extra))
    # EasyEDA marks some all-SMD parts (crystals, the CSP FET, an inductor)
    # through-hole, which would leave them out of the placement file; a part
    # with plated legs (the USB-C shell) is through-hole, as KiCad expects
    _get(out, 'attr')[1] = 'through_hole' if plated else 'smd'
    # pin-1 dot: EasyEDA's own, unless it sits by some other pad (the
    # TPS62840's is on ball A2), else one drawn by pad 1 / A1
    dot = None
    if len(dots) == 1:
        dot = float(_get(dots[0], 'center')[1]), float(_get(dots[0], 'center')[2])
        if pin1 is not None:
            near = min(boxes, key=lambda b: ((b[0] + b[2]) / 2 - dot[0]) ** 2 + ((b[1] + b[3]) / 2 - dot[1]) ** 2)
            if near != pin1:
                dot = None
    if dot is not None:
        cx, cy = dot
    elif pin1 is not None:
        x0, y0, x1, y1 = pin1
        cx, cy = _dot_near((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)
    else:
        cx = None
    if cx is not None:
        out.append(['fp_circle', ['center', '%.3f' % cx, '%.3f' % cy], ['end', '%.3f' % (cx + DOT_R), '%.3f' % cy],
                    ['layer', 'F.Fab'], ['width', '%.3f' % DOT_W]])
    x0 = min(b[0] for b in boxes) - 0.10; y0 = min(b[1] for b in boxes) - 0.10
    x1 = max(b[2] for b in boxes) + 0.10; y1 = max(b[3] for b in boxes) + 0.10
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        out.append(_line(a[0], a[1], b[0], b[1], 'F.CrtYd', 0.05))
    if model is None and fx.get('model'):
        model = ['model', '"lib.3dshapes/%s.wrl"' % fx['model']]
    if model is not None:
        m = re.search(r'(?:ee|lib)\.3dshapes/([^"]+)\.wrl', model[1])
        if m and os.path.exists(os.path.join(MODELS, m.group(1) + '.stpZ')):
            model[1] = '"${KIPRJMOD}/og.3dshapes/%s.stpZ"' % m.group(1)
            if fx.get('model_offset'):
                _get(model, 'offset')[1] = ['xyz'] + ['%.3f' % v for v in fx['model_offset']]
            out.append(model)
    open(os.path.join(LIB, name + '.kicad_mod'), 'w').write(_emit(out) + '\n')
    # round-trip through KiCad so the file is in its native format
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID('og', name))
    return fp

def _rect(fp, layer, x0, y0, x1, y1, w):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        a, b = pts[i], pts[(i + 1) % 4]
        s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(int(b[0]), int(b[1])))
        s.SetLayer(layer); s.SetWidth(MM(w))
        fp.Add(s)

def _nm(v):
    return int(round(v * 1e6))

def _dot(fp, x, y):
    c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(pcbnew.VECTOR2I(_nm(x), _nm(y))); c.SetEnd(pcbnew.VECTOR2I(_nm(x + DOT_R), _nm(y)))
    c.SetLayer(pcbnew.F_Fab); c.SetWidth(MM(DOT_W))
    fp.Add(c)

def _smd_pad(fp, num, x, y, w, h, paste=True):
    p = pcbnew.PAD(fp)
    p.SetNumber(num); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetShape(pcbnew.PAD_SHAPE_RECT)
    p.SetSize(pcbnew.VECTOR2I(_nm(w), _nm(h)))
    p.SetPosition(pcbnew.VECTOR2I(_nm(x), _nm(y)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask)
    if paste: ls.AddLayer(pcbnew.F_Paste)
    p.SetLayerSet(ls)
    fp.Add(p)
    return p

def _pth_pad(fp, num, x, y, d, drill, square=False, mask=True):
    p = pcbnew.PAD(fp)
    p.SetNumber(num); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    p.SetShape(pcbnew.PAD_SHAPE_RECT if square else pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(_nm(d), _nm(d))); p.SetDrillSize(pcbnew.VECTOR2I(_nm(drill), _nm(drill)))
    p.SetPosition(pcbnew.VECTOR2I(_nm(x), _nm(y)))
    ls = pcbnew.LSET.AllCuMask()
    if mask:
        ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    return p

def _model(fp, path):
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = path
    fp.Models().append(m)

def _new(name, desc, attr=pcbnew.FP_SMD):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('og', name))
    fp.SetAttributes(attr)
    fp.SetLibDescription(desc)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
    fp.Reference().SetTextThickness(MM(0.08))
    fp.Value().SetText(name); fp.Value().SetLayer(pcbnew.F_Fab); fp.Value().SetVisible(False)
    return fp

def qpa9510_fp():
    """Qorvo QPA9510 power amplifier, QFN-16 3 x 3 mm, 0.5 mm pitch.
    EasyEDA has no entry for C52059849, so this is Qorvo's "PCB Metal Land
    Pattern (Top View)" from the QPA9510 data sheet (June 23, 2025, p.8):
      side pads A 0.64 x 0.28 mm, top/bottom pads B 0.28 x 0.64 mm,
      0.50 mm pitch, outer pads 0.75 mm off the centre line (1.50 typ.
      across), pad centres 1.30 mm from the centre (the 0.55 typ. corner
      step from the last pad to the first pad of the next side; Qorvo's
      0.40 mm terminals reach 1.10-1.50 mm, so each land runs 0.12 mm past
      both ends of the terminal);
      exposed pad C 1.50 mm square (the package paddle is 1.50 mm).
    Qorvo's mask openings are 0.05 mm larger all round (A 0.74 x 0.38, C
    1.60); this board's mask openings equal the pads and the fab sizes them.
    Pin 1 top left, counting counter-clockwise seen from the top (Qorvo's
    "Top View": 1-4 down the left, 5-8 along the bottom, 9-12 up the right,
    13-16 along the top right to left); the paddle is pad 17 (RF/DC ground).

    Ground vias in the paddle: Qorvo asks for "ground via holes ... under
    the backside paddle ... 0.203 to 0.330 mm finished hole, 0.5 to 1.2 mm
    grid".  Nine 0.30 mm holes on a 0.55 mm grid (the grid that keeps
    0.25 mm of laminate between holes) with 0.50 mm lands: board vias, which
    board.py places (PA_VIAS), not footprint pads, so they are drilled,
    filled and capped as vias.  The amplifier dissipates watts while
    transmitting at 3 W; this is its heat path into the ground planes.
    THESE VIAS MUST BE FILLED AND CAPPED (POFV, which this board orders):
    open holes under the paddle wick the solder paste away and leave voids.
    The paste opening is 0.10 mm inside the paddle all round (1.30 mm
    square, 75 %), so the part does not float on the paddle's solder."""
    name = 'QFN-16_3x3_QPA9510'
    fp = _new(name, 'Qorvo QPA9510 QFN-16 3x3 mm 0.5 mm pitch, EP 1.5 mm; Qorvo land pattern; '
                    '9 filled 0.3 mm vias in the EP (board vias, board.py)')
    A, B, P, R = (0.64, 0.28), (0.28, 0.64), 0.50, 1.30
    offs = [-0.75, -0.25, 0.25, 0.75]
    for i, o in enumerate(offs):
        _smd_pad(fp, str(1 + i), -R, o, *A)            # 1-4 left, top to bottom
        _smd_pad(fp, str(5 + i), o, R, *B)             # 5-8 bottom, left to right
        _smd_pad(fp, str(9 + i), R, -o, *A)            # 9-12 right, bottom to top
        _smd_pad(fp, str(13 + i), -o, -R, *B)          # 13-16 top, right to left
    ep = _smd_pad(fp, '17', 0, 0, 1.50, 1.50)
    ep.SetLocalSolderPasteMargin(MM(-0.10))
    # KiCad's standard 3 x 3 mm QFN-16 body (its paddle is 1.7 mm, hidden
    # under the part; renders and STEP only)
    _model(fp, '${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm.step')
    # (the nine paddle vias are board vias, placed by board.py at PA_VIAS:
    # a fab fills and caps vias; holes drawn as footprint pads it may not)
    # body with the pin-1 corner chamfer, as on Qorvo's drawing
    c = 0.40
    pts = [(-1.5 + c, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -1.5 + c)]
    for i in range(len(pts)):
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s.SetStart(pcbnew.VECTOR2I(_nm(a[0]), _nm(a[1]))); s.SetEnd(pcbnew.VECTOR2I(_nm(b[0]), _nm(b[1])))
        s.SetLayer(pcbnew.F_Fab); s.SetWidth(MM(0.1)); fp.Add(s)
    _dot(fp, -1.85, -1.10)
    e = R + 0.32 + 0.10                                 # pad toe 1.62 + 0.10
    _rect(fp, pcbnew.F_CrtYd, -MM(e), -MM(e), MM(e), MM(e), 0.05)
    return fp

def coilcraft_0908sq_fp():
    """Coilcraft 0908SQ air-core inductor (the amplifier's collector choke,
    0908SQ-8N1).  Coilcraft's "Recommended Land Pattern" (Document 617-2,
    rev. 12/21/22) for 0908SQ-8N1: two lands F = 0.64 mm wide, E = 2.8 mm
    long, D = 1.12 mm centre to centre (D is the pitch of the coil's end
    turns, which sit on the lands; it cannot be an edge-to-edge distance,
    as 2 x 0.64 > 1.12).  Body: coil length A 1.473, width B 2.134, height
    C 1.829 mm.  The coil axis runs along x, pad 1 left, pad 2 right."""
    name = 'L_0908SQ'
    fp = _new(name, 'Coilcraft 0908SQ-8N1 square air-core inductor; Coilcraft land: '
                    '2 x 0.64 x 2.8 mm, 1.12 mm pitch')
    F, E, D = 0.64, 2.80, 1.12
    _smd_pad(fp, '1', -D / 2, 0, F, E)
    _smd_pad(fp, '2', D / 2, 0, F, E)
    _model(fp, '${KIPRJMOD}/og.3dshapes/BOX_Coilcraft_0908SQ.stpZ')   # a plain box (box3d.py)
    a, b = 1.473 / 2, 2.134 / 2
    _rect(fp, pcbnew.F_Fab, -MM(a), -MM(b), MM(a), MM(b), 0.1)
    x = max(D / 2 + F / 2, a) + 0.10; y = max(E / 2, b) + 0.10
    _rect(fp, pcbnew.F_CrtYd, -MM(x), -MM(y), MM(x), MM(y), 0.05)
    return fp

def header_rows_fp():
    """Expansion header, not fitted: two single rows of ten 2.54 mm pins,
    20.32 mm apart, one along each long edge of the 25.4 mm board (as the
    Heltec boards carry their pin rows).  Pins 1-10 in the first row
    (y = -10.16, pin 1 at x = 0, numbers rising in +x), pins 11-20 in the
    second (y = +10.16, pin 11 at x = 0).  1.0 mm holes, 1.7 mm pads, the
    first pin of each row square.  Each row has its own courtyard, so
    parts may sit between the rows."""
    name = 'Header_2x1x10_Rows20.32'
    fp = _new(name, 'Two 1x10 rows, 2.54 mm pitch, rows 20.32 mm apart; 1.0 mm drill, 1.7 mm pads',
              attr=pcbnew.FP_THROUGH_HOLE)
    pitch, half, drill, pad = 2.54, 10.16, 1.0, 1.7
    for row, y in ((0, -half), (1, half)):
        for i in range(10):
            _pth_pad(fp, str(row * 10 + i + 1), i * pitch, y, pad, drill, square=(i == 0))
        x0, x1 = -pitch / 2, 9 * pitch + pitch / 2
        _rect(fp, pcbnew.F_Fab, MM(x0), MM(y - 1.27), MM(x1), MM(y + 1.27), 0.1)
        c = pad / 2 + 0.10
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            _rect(fp, lay, MM(-c), MM(y - c), MM(9 * pitch + c), MM(y + c), 0.05)
        _dot(fp, -1.6, y)
    return fp

# --- KiCad library footprints ---------------------------------------------
# name here: (KiCad library, KiCad footprint)
STD = {
    'C_0402': ('Capacitor_SMD', 'C_0402_1005Metric'),
    'C_0603': ('Capacitor_SMD', 'C_0603_1608Metric'),
    'C_0805': ('Capacitor_SMD', 'C_0805_2012Metric'),
    'C_1206': ('Capacitor_SMD', 'C_1206_3216Metric'),
    'R_0402': ('Resistor_SMD', 'R_0402_1005Metric'),
    'R_0603': ('Resistor_SMD', 'R_0603_1608Metric'),
    'R_0805': ('Resistor_SMD', 'R_0805_2012Metric'),
    'R_1206': ('Resistor_SMD', 'R_1206_3216Metric'),
    'L_0402': ('Inductor_SMD', 'L_0402_1005Metric'),
    'L_0603': ('Inductor_SMD', 'L_0603_1608Metric'),
    'L_0805': ('Inductor_SMD', 'L_0805_2012Metric'),
    'TestPoint_Pad_1.0mm': ('TestPoint', 'TestPoint_Pad_D1.0mm'),
    'MountingHole_2.2mm_M2_Pad': ('MountingHole', 'MountingHole_2.2mm_M2_Pad'),
}

def _model_path(fn):
    return fn.replace('${KICAD10_3DMODEL_DIR}', KIMOD)

def std_fp(name, lib, kname):
    fp = pcbnew.FootprintLoad(os.path.join(KISTD, lib + '.pretty'), kname)
    fp.SetFPID(pcbnew.LIB_ID('og', name))
    fp.Value().SetText(name)
    for f in fp.GetFields():
        if f.GetLayer() == pcbnew.F_SilkS:
            f.SetLayer(pcbnew.F_Fab)
    x0 = y0 = 1e12; x1 = y1 = -1e12
    for it in list(fp.GraphicalItems()):
        if it.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS, pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            fp.Remove(it)
        elif it.GetLayer() == pcbnew.F_Fab and it.GetClass() == 'PCB_SHAPE':
            bb = it.GetBoundingBox()
            x0, y0, x1, y1 = min(x0, bb.GetLeft()), min(y0, bb.GetTop()), max(x1, bb.GetRight()), max(y1, bb.GetBottom())
    for pd in fp.Pads():
        bb = pd.GetBoundingBox()
        x0, y0, x1, y1 = min(x0, bb.GetLeft()), min(y0, bb.GetTop()), max(x1, bb.GetRight()), max(y1, bb.GetBottom())
    m = MM(0.1)
    if lib == 'MountingHole':
        # round: the hole's copper ring + 0.10, both sides (it is plated)
        r = max(x1 - x0, y1 - y0) // 2 + m
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
            c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(int(r), 0))
            c.SetLayer(lay); c.SetWidth(MM(0.05)); fp.Add(c)
    else:
        _rect(fp, pcbnew.F_CrtYd, x0 - m, y0 - m, x1 + m, y1 + m, 0.05)
    if lib == 'TestPoint':
        # bare copper, never placed by the assembler
        fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    # The image carries only some of KiCad's 3D models (C_0402/0603/0805,
    # R_0402).  A chip inductor or resistor whose model is missing is drawn
    # with the same-size capacitor's body, so renders are not missing it.
    models = []
    for mdl in fp.Models():
        if not os.path.exists(_model_path(mdl.m_Filename)):
            alt = re.sub(r'(Inductor|Resistor)_SMD\.3dshapes/[LR]_', 'Capacitor_SMD.3dshapes/C_', mdl.m_Filename)
            if os.path.exists(_model_path(alt)):
                mdl.m_Filename = alt
        models.append(mdl)
    fp.Models().clear()
    for mdl in models:
        fp.Models().append(mdl)
    fp.SetLibDescription(fp.GetLibDescription() + ' (KiCad %s:%s; no silkscreen; courtyard 0.10 mm)' % (lib, kname))
    return fp


def main():
    # fixed item IDs: regenerating the library changes only what changed
    pcbnew.KIID.SeedGenerator(1)
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, '*.kicad_mod')):
        os.remove(f)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW, '*.kicad_mod'))):
        raw = os.path.splitext(os.path.basename(path))[0]
        if FIXUPS.get(raw, {}).get('skip'):
            continue
        fp = clean_easyeda(path)
        _save(LIB, fp); n += 1
    gen = [qpa9510_fp(), coilcraft_0908sq_fp(), header_rows_fp()]
    gen += [std_fp(k, *v) for k, v in sorted(STD.items())]
    for fp in gen:
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))

if __name__ == '__main__':
    main()
