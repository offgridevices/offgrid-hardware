# -*- coding: utf-8 -*-
"""Build ../aio.pretty, the board's own footprint library.

Two kinds of footprint go in:

1. JLCPCB/EasyEDA footprints for the exact LCSC parts, converted once with
   easyeda2kicad and kept verbatim in easyeda_raw/.  They are cleaned here:
   - the converter draws each courtyard round the package BODY only, which
     leaves the pads outside it, so KiCad's courtyard checks would pass two
     parts sitting on each other's pads.  The courtyard is rebuilt as the
     box round pads + body + 0.10 mm.
   - silkscreen is dropped.  At this density a component outline on the
     silk is noise that lands on pads; the assembly drawing carries the
     outlines and reference designators instead.
   - 3D models point at ../aio.3dshapes (gzip STEP, KiCad reads .stpZ).
   - custom (polygon) pads that are plain rectangles become rect pads; any
     other polygon (a QFN's chamfered corner pads, a FET's drain) stays a
     polygon, drawn with no outline width so the copper is exactly the
     polygon EasyEDA gives.
   - FIXUPS below renames pads to the datasheet / circuit.py names and
     resizes the few exposed pads where the maker's land pattern is larger
     than EasyEDA's.  The raw files stay verbatim.
2. Footprints generated here: battery, motor and signal solder pads, test
   points, the open solder jumper and the M3 mounting hole (copper only),
   plus the Stackpole HCS1206 shunt land (no EasyEDA entry exists for it).

Run with KiCad's Python (python3.12 on Ubuntu): it uses pcbnew to read and
write footprints so the output is exactly KiCad's own format.
"""
import os, sys, glob, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'aio.pretty'))
RAW = os.path.join(HERE, 'easyeda_raw')
MODELS = os.path.normpath(os.path.join(HERE, '..', 'aio.3dshapes'))

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
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2

def _area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2

# Per-footprint corrections, applied to the parsed EasyEDA file.
#   'rename': {EasyEDA pad name: pad name used here}
#   'resize': {pad name: (w, h)} in the footprint's own axes (rotation 0)
#   'trim':   {pad name: d} shortens a pad by d mm at its +y end (the pad
#             keeps its -y end), footprint axes
FIXUPS = {
    # GCT USB4105-GF-A-120: EasyEDA names the doubled contacts 'A1-B12';
    # circuit.py uses 'A1B12' (as the v1 receptacle did).  Shell 1-4.
    # The two outer ground pads' inner ends come 0.18 mm from the 0.65 mm
    # peg holes, under the 0.2 mm the fab keeps between a non-plated hole
    # and copper; 0.04 mm off those ends (the heel, not the toe that carries
    # the fillet) leaves 0.22 mm.
    'USB-C-SMD_MC-311D': dict(rename={'A1-B12': 'A1B12', 'B1-A12': 'B1A12',
                                      'A4-B9': 'A4B9', 'B4-A9': 'B4A9'},
                              trim={'A1B12': 0.04, 'B1A12': 0.04}),
    # TI TPS7A4101 DGN (HVSSOP-8): TI's land (DGN0008B) has a 1.98 x 1.88 mm
    # thermal pad; EasyEDA's is 1.8 x 1.5.  Rows run along x here.
    'MSOP-8_L3.0-W3.0-P0.65-LS5.0-BL-EP': dict(resize={'9': (1.98, 1.88)}),
    # TI LMR38020 DDA (SO-8 PowerPAD): TI's land (DDA0008B) has a
    # 3.4 x 2.71 mm thermal pad; EasyEDA's is 3.3 x 2.4.
    'ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP-1': dict(resize={'9': (3.4, 2.71)}),
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

def clean_easyeda(path):
    name = os.path.splitext(os.path.basename(path))[0]
    t = _parse(open(path).read())
    out = ['footprint', '"%s"' % name]
    boxes, model = [], None
    for c in t[2:]:
        if not isinstance(c, list):
            continue
        k = c[0]
        if k in ('fp_line', 'fp_circle', 'fp_arc', 'fp_poly'):
            lay = _get(c, 'layer')[1]
            if lay in ('F.SilkS', 'Cmts.User'):
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
                    # a plain rectangle (the v1 USB-C's GND/VBUS pads)
                    c = [x for x in c if not (isinstance(x, list) and x[0] == 'primitives')]
                    c[3] = 'rect'
                    _get(c, 'size')[1:] = ['%.3f' % bw, '%.3f' % bh]
                    cx, cy = (max(px) + min(px)) / 2, (max(py) + min(py)) / 2
                    if abs(cx) > 0.001 or abs(cy) > 0.001:
                        at = _get(c, 'at')
                        at[1] = '%.3f' % (float(at[1]) + cx); at[2] = '%.3f' % (float(at[2]) + cy)
                else:
                    # chamfered QFN corner pads, a FET's drain: keep the
                    # polygon, but with no outline width (EasyEDA's 0.1 mm
                    # would grow every edge by 0.05 mm)
                    _get(_get(_get(c, 'primitives'), 'gr_poly'), 'width')[1] = '0'
            _fix_pad(name, c)
            if c[1] == '""' and c[2] == 'thru_hole':
                # locating pegs are drawn as plated holes with no copper
                # ring; they are plastic posts, so make them non-plated
                c[2] = 'np_thru_hole'
            if c[2] != 'np_thru_hole' and c[1] != '""':
                boxes.append(_pad_box(c))
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
                i = c.index(_get(c, 'layer')); c.insert(i + 1, 'hide'); out.append(c)
        elif k == 'model':
            model = c
        elif k in ('descr', 'attr', 'property', 'layer'):
            out.append(c)
    x0 = min(b[0] for b in boxes) - 0.10; y0 = min(b[1] for b in boxes) - 0.10
    x1 = max(b[2] for b in boxes) + 0.10; y1 = max(b[3] for b in boxes) + 0.10
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        out.append(_line(a[0], a[1], b[0], b[1], 'F.CrtYd', 0.05))
    if model is not None:
        m = re.search(r'ee\.3dshapes/([^"]+)\.wrl', model[1])
        if m and os.path.exists(os.path.join(MODELS, m.group(1) + '.stpZ')):
            model[1] = '"${KIPRJMOD}/../aio.3dshapes/%s.stpZ"' % m.group(1)
            out.append(model)
    open(os.path.join(LIB, name + '.kicad_mod'), 'w').write(_emit(out) + '\n')
    # round-trip through KiCad so the file is in its native format
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID('aio', name))
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

def pad_fp(name, w, h, shape='roundrect', paste=False, desc=''):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', name))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    p = pcbnew.PAD(fp)
    p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    if shape == 'circle':
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    else:
        p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT); p.SetRoundRectRadiusRatio(0.2)
    p.SetSize(pcbnew.VECTOR2I(MM(w), MM(h)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask)
    if paste: ls.AddLayer(pcbnew.F_Paste)
    p.SetLayerSet(ls)
    fp.Add(p)
    _rect(fp, pcbnew.F_CrtYd, -MM(w / 2 + 0.1), -MM(h / 2 + 0.1), MM(w / 2 + 0.1), MM(h / 2 + 0.1), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.4), MM(0.4)))
    fp.Reference().SetTextThickness(MM(0.06))
    fp.Value().SetVisible(False)
    return fp

def pth_pad_fp(name, d, drill, desc='', h=None, kelvin=False):
    """Plated through-hole solder pad, round (d) or oval (d wide, h tall).
    The wire goes through the board and the joint wets both sides and the
    barrel, so a crash cannot peel it off the way it lifts a surface pad,
    and the current reaches every copper layer (the inner planes included)
    through the barrel.  kelvin: a small top pad 2 at the -x end, net-tied
    to pad 1 (footprint net-tie group), where a separate net leaves the
    pad's own copper: a tap that carries none of the pad's current."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', name))
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    h = h or d
    p = pcbnew.PAD(fp)
    p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE if h == d else pcbnew.PAD_SHAPE_OVAL)
    p.SetSize(pcbnew.VECTOR2I(MM(d), MM(h))); p.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
    ls = pcbnew.LSET.AllCuMask(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    kx = 0.0
    if kelvin:
        kw, kh, ov = 0.5, 0.6, 0.1
        kx = d / 2 + kw / 2 - ov
        _smd_pad(fp, '2', -kx, 0, kw, kh, paste=False)
        fp.AddNetTiePadGroup('1, 2')
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        if h == d and not kelvin:
            c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
            c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(d / 2 + 0.1), 0))
            c.SetLayer(lay); c.SetWidth(MM(0.05)); fp.Add(c)
        else:
            x0 = -(kx + 0.25 + 0.1) if (kelvin and lay == pcbnew.F_CrtYd) else -(d / 2 + 0.1)
            _rect(fp, lay, MM(x0), -MM(h / 2 + 0.1), MM(d / 2 + 0.1), MM(h / 2 + 0.1), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.4), MM(0.4)))
    fp.Reference().SetTextThickness(MM(0.06))
    fp.Value().SetVisible(False)
    return fp

def hole_fp():
    """Mounting position for the slotted grommet hole.  The hole and its
    slot are cut by the board outline (pcb.outline), so this footprint has
    no pad: it carries the grommet's keepout as a courtyard on both sides
    (so no part lands on the flange) and the hole and slot on the fab
    layer.  Drawn for the top-right corner; placed rotated per corner."""
    import math
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', 'MOUNT_M2_SLOT'))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription('Slotted mounting hole: 3.2 mm hole for an M2 soft-mount grommet, 2.5 mm slot to the '
                         'corner; the board outline cuts it, this marks the grommet keepout')
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(3.0), 0))
        c.SetLayer(lay); c.SetWidth(MM(0.05)); fp.Add(c)
    c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(1.6), 0))
    c.SetLayer(pcbnew.F_Fab); c.SetWidth(MM(0.1)); fp.Add(c)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    return fp

def _nm(v):
    return int(round(v * 1e6))

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

def solder_jumper_fp(name='SJ_OPEN', w=0.8, h=1.2, gap=0.3):
    """Open solder jumper: two pads, `gap` apart, one mask opening over both
    so a blob of solder bridges them.  No paste: it ships open."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', name))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetAllowSolderMaskBridges(True)       # the one opening over both pads is the point
    fp.SetLibDescription('Solder jumper, normally open: 2 pads %.1f x %.1f mm, %.2f mm gap' % (w, h, gap))
    dx = (w + gap) / 2
    _smd_pad(fp, '1', -dx, 0, w, h, paste=False)
    _smd_pad(fp, '2', dx, 0, w, h, paste=False)
    x1, y1 = dx + w / 2 + 0.05, h / 2 + 0.05
    m = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    m.SetStart(pcbnew.VECTOR2I(-MM(x1), -MM(y1))); m.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
    m.SetFilled(True); m.SetLayer(pcbnew.F_Mask); m.SetWidth(0)
    fp.Add(m)
    _rect(fp, pcbnew.F_CrtYd, -MM(x1 + 0.05), -MM(y1 + 0.05), MM(x1 + 0.05), MM(y1 + 0.05), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.4), MM(0.4)))
    fp.Reference().SetTextThickness(MM(0.06))
    fp.Value().SetVisible(False)
    return fp

def shunt_hcs1206_fp():
    """Stackpole HCS1206 metal-element shunt (0.5 mOhm, 2 W): EasyEDA has no
    entry for C346511, so the land is Stackpole's recommended pad layout
    (HCS datasheet p.5, 1206 row): current pads b 1.70 long x c 1.80 wide,
    gap a 1.40 (4.8 x 1.8 mm of copper).  Pad 1 left, pad 2 right.
    Kelvin sense pads 3 (tied to 1) and 4 (tied to 2) leave from the inner
    corner of each current pad, where Stackpole's drawing takes its sense
    traces, 0.25 x 0.5 mm, no paste; footprint net-tie groups 1-3 and 2-4
    let them overlap the current pads.  Courtyard 5.0 x 2.45 mm."""
    name = 'RES-SMD_1206_HCS1206'
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', name))
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetLibDescription('Stackpole HCS1206 current shunt, 3.2 x 1.65 mm; Stackpole land '
                         'a=1.40 b=1.70 c=1.80; Kelvin sense pads 3 (=1) and 4 (=2)')
    b, c, a = 1.70, 1.80, 1.40
    dx = (a + b) / 2
    _smd_pad(fp, '1', -dx, 0, b, c)
    _smd_pad(fp, '2', dx, 0, b, c)
    sw, sh, ov = 0.25, 0.50, 0.05            # sense pad size, overlap into the current pad
    sx, sy = a / 2 + sw / 2, c / 2 + sh / 2 - ov
    _smd_pad(fp, '3', -sx, sy, sw, sh, paste=False)
    _smd_pad(fp, '4', sx, sy, sw, sh, paste=False)
    fp.AddNetTiePadGroup('1, 3')
    fp.AddNetTiePadGroup('2, 4')
    _rect(fp, pcbnew.F_Fab, -MM(1.6), -MM(0.825), MM(1.6), MM(0.825), 0.1)
    x1, y0, y1 = dx + b / 2 + 0.1, -(c / 2 + 0.1), sy + sh / 2 + 0.1
    _rect(fp, pcbnew.F_CrtYd, -MM(x1), MM(y0), MM(x1), MM(y1), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
    fp.Reference().SetTextThickness(MM(0.08))
    fp.Value().SetText(name); fp.Value().SetVisible(False)
    if os.path.exists(os.path.join(MODELS, 'R_1206_3216Metric.stpZ')):
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = '${KIPRJMOD}/../aio.3dshapes/R_1206_3216Metric.stpZ'
        fp.Models().append(m)
    return fp

# EasyEDA's 3D models of these connectors sit off their pads (the JST SH
# models' origin is at pin 1, 2.5 / 3.5 mm along the row; the USB-C's is
# 2.75 mm back), so renders drew the connector bodies over their
# neighbours' pads.  Their land patterns are KiCad's own footprints for the
# same parts, pad for pad, so they take KiCad's models instead, placed by
# that match (official_model).  EasyEDA's other models sit on their body
# outlines to 0.01 mm.
STD_FP = '/usr/share/kicad/footprints'          # as pcb.STD_FP
OFFICIAL_MODELS = {
    'CONN-SMD-6P-P1.00_BM06B-SRSS-TB-LF-SN': 'Connector_JST:JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical',
    'CONN-TH_BM08B-SRSS-TB-LF-SN': 'Connector_JST:JST_SH_BM08B-SRSS-TB_1x08-1MP_P1.00mm_Vertical',
    'CONN-TH_SM08B-SRSS-TB-LF-SN': 'Connector_JST:JST_SH_SM08B-SRSS-TB_1x08-1MP_P1.00mm_Horizontal',
    'USB-C-SMD_MC-311D': 'Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
}


def _official(ref):
    """KiCad's footprint 'lib:name', read as text (loading it through
    pcbnew would draw on the seeded item IDs): its pads {number: [(x, y)]}
    and its models [(file, offset, rotation, scale)]."""
    lib, name = ref.split(':')
    path = os.path.join(STD_FP, lib + '.pretty', name + '.kicad_mod')
    if not os.path.exists(path):
        raise SystemExit('KiCad footprint %s not found' % ref)
    t = _parse(open(path).read())
    pads, models = {}, []
    xyz = lambda n, k: tuple(float(v) for v in _get(_get(n, k), 'xyz')[1:4]) if _get(n, k) else None
    for c in t[2:]:
        if isinstance(c, list) and c[0] == 'pad':
            at = _get(c, 'at')
            pads.setdefault(c[1].strip('"'), []).append((float(at[1]), float(at[2])))
        elif isinstance(c, list) and c[0] == 'model':
            models.append((c[1].strip('"'), xyz(c, 'offset') or (0, 0, 0), xyz(c, 'rotate') or (0, 0, 0),
                           xyz(c, 'scale') or (1, 1, 1)))
    return pads, models


def official_model(fp, ref):
    """Give `fp` the 3D models of KiCad's footprint `ref` ('lib:name') for
    the same part.  The pads both number alike fix where KiCad's footprint
    sits in `fp`: a quarter turn th and a shift t (p -> R(th) p + t, KiCad's
    y-down frame).  Every pad of KiCad's (mounting pads too) must then land
    on a pad of `fp`'s, to 0.025 mm (FIXUPS' trims move a pad's centre by
    0.02 mm): the land patterns are the same."""
    import math
    theirs, kmodels = _official(ref)
    xy = lambda p: (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
    ours = {}
    for p in fp.Pads():
        ours.setdefault(p.GetNumber(), []).append(xy(p))
    common = [n for n in ours if n and len(ours[n]) == 1 and len(theirs.get(n, [])) == 1]
    if len(common) < 2:
        raise SystemExit('%s: fewer than two pads in common with %s' % (fp.GetFPID().GetLibItemName(), ref))
    best = None
    for th in (0, 90, 180, 270):
        c, s = round(math.cos(math.radians(th))), round(math.sin(math.radians(th)))
        turn = lambda q: (q[0] * c + q[1] * s, -q[0] * s + q[1] * c)
        d = [(ours[n][0][0] - turn(theirs[n][0])[0], ours[n][0][1] - turn(theirs[n][0])[1]) for n in common]
        t = (sum(v[0] for v in d) / len(d), sum(v[1] for v in d) / len(d))
        mine = [q for v in ours.values() for q in v]
        err = max(min(math.hypot(turn(q)[0] + t[0] - o[0], turn(q)[1] + t[1] - o[1]) for o in mine)
                  for v in theirs.values() for q in v)
        if best is None or err < best[0]:
            best = (err, th, c, s, t)
    err, th, c, s, t = best
    if err > 0.025:
        raise SystemExit('%s: land pattern differs from %s by %.3f mm' % (fp.GetFPID().GetLibItemName(), ref, err))
    fp.Models().clear()
    for f, off, rot, sc in kmodels:
        n = pcbnew.FP_3DMODEL()
        n.m_Filename = f
        # the model frame has y up; its offset turns and shifts with the
        # footprint, its turn adds th (both counter-clockwise seen from top)
        ox, oy = off[0], -off[1]
        n.m_Offset = pcbnew.VECTOR3D(ox * c + oy * s + t[0], -(-ox * s + oy * c + t[1]), off[2])
        n.m_Rotation = pcbnew.VECTOR3D(rot[0], rot[1], (rot[2] + th) % 360)
        n.m_Scale = pcbnew.VECTOR3D(*sc)
        fp.Models().append(n)
    return th, t


def seat_models():
    """Not all of EasyEDA's models start at the board: some sink into it
    (TSSOP-28 0.55 mm, ESOP-8 0.8 mm) and the 6.5 mm IHLP inductor's hangs
    2.5 mm below its origin, so on the bottom side it pokes through to the
    top in the renders.  KiCad's own conversion of each model (models3d)
    gives its lowest point, and a surface-mount part's model is raised or
    lowered so that point sits on the board.  (A part with plated leads
    keeps its model as it is: the leads go into the board.)  Only the z of
    each model's offset changes in the library files."""
    import tempfile
    import models3d
    b = pcbnew.BOARD()
    names = []
    for i, f in enumerate(sorted(glob.glob(os.path.join(LIB, '*.kicad_mod')))):
        name = os.path.splitext(os.path.basename(f))[0]
        fp = pcbnew.FootprintLoad(LIB, name)
        if not len(fp.Models()):
            continue
        fp.SetPosition(pcbnew.VECTOR2I(MM(20 * (i % 10)), MM(20 * (i // 10))))
        b.Add(fp)
        names.append((name, fp))
    d = tempfile.mkdtemp(prefix='seat-')
    path = os.path.join(d, 'models.kicad_pcb')
    b.Save(path)
    pts = models3d.model_points(path, prjmod=os.path.join(os.path.dirname(LIB), 'fc'))
    moved = []
    for name, fp in names:
        if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads()):
            continue
        zr = models3d.z_range(fp, pts)
        if zr is None or abs(zr[0]) <= 0.02:
            continue
        f = os.path.join(LIB, name + '.kicad_mod')
        txt = open(f).read()
        m = re.search(r'(\(model "[^"]*"\s*\(offset\s*\(xyz )([-\d.e]+) ([-\d.e]+) ([-\d.e]+)\)', txt)
        if not m or len(re.findall(r'\(model ', txt)) != 1:
            raise SystemExit('%s: cannot seat its model' % name)
        z = float(m.group(4)) - zr[0]
        txt = txt[:m.start()] + m.group(1) + '%s %s %s)' % (m.group(2), m.group(3), ('%.4f' % z).rstrip('0').rstrip('.')) \
            + txt[m.end():]
        open(f, 'w').write(txt)
        moved.append('%s %+.2f' % (name, -zr[0]))
    return moved


def main():
    # fixed item IDs: regenerating the library changes only what changed
    pcbnew.KIID.SeedGenerator(1)
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, '*.kicad_mod')):
        os.remove(f)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW, '*.kicad_mod'))):
        fp = clean_easyeda(path)
        name = os.path.splitext(os.path.basename(path))[0]
        if name in OFFICIAL_MODELS:
            th, t = official_model(fp, OFFICIAL_MODELS[name])
            print('%s: KiCad model of %s (turned %d, shifted %.3f, %.3f)' % (name, OFFICIAL_MODELS[name], th, *t))
        _save(LIB, fp); n += 1
    gen = [
        # battery pads: 3.2 mm round a 1.8 mm hole, for up to 14 AWG
        # (1.63 mm) through the board, as large as the corner between the
        # grommet's keep-out, the panel's tab zone and the edge allows; the
        # ground pad's Kelvin tap feeds the stack lead's ground
        # (circuit.esc_power)
        pth_pad_fp('PAD_BAT', 3.2, 1.8, desc='Battery lead pad, plated through-hole, 14-16 AWG'),
        pth_pad_fp('PAD_BAT_K', 3.2, 1.8, kelvin=True,
                   desc='Battery lead pad, plated through-hole, 14-16 AWG, with a Kelvin tap (pad 2)'),
        pad_fp('PAD_MOTOR', 2.0, 2.3, desc='Motor phase wire pad'),
        pad_fp('PAD_SIG', 1.1, 1.6, desc='Signal / power solder pad'),
        pad_fp('PAD_TP', 0.9, 0.9, shape='circle', desc='Test point'),
        hole_fp(),
    ]
    gen += [solder_jumper_fp(), shunt_hcs1206_fp()]
    for fp in gen:
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))
    for s in seat_models():
        print('model seated on the board: %s mm' % s)

if __name__ == '__main__':
    main()
