# -*- coding: utf-8 -*-
"""Build ../og.pretty, the board's own footprint library.

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
LIB = os.path.normpath(os.path.join(HERE, '..', 'og.pretty'))
RAW = os.path.join(HERE, 'easyeda_raw')
MODELS = os.path.normpath(os.path.join(HERE, '..', 'og.3dshapes'))

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
#   'model':  a 3D model (in ../og.3dshapes) for a part EasyEDA has none for
FIXUPS = {
    # GCT USB4110-GF-A: shell pads 8-11.  The two outer ground pads' inner
    # ends come 0.17 mm from the 0.65 mm peg holes, under the 0.2 mm the
    # fab keeps between a non-plated hole and copper; 0.04 mm off those
    # ends (the heel, not the toe that carries the fillet) leaves 0.21 mm.
    # No EasyEDA model: the USB4105's body (same 8.9 x 7.3 x 3.3 mm shell)
    # stands in for the renders.
    'USB-C-SMD_TYPE-C-16P-USB4110-GF-A': dict(trim={'A1B12': 0.04, 'B1A12': 0.04},
                                              model='USB-3.1-SMD_16P-L8.9-W7.3-H3.3-P0.5'),
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
    if model is None and FIXUPS.get(name, {}).get('model'):
        model = ['model', '"ee.3dshapes/%s.wrl"' % FIXUPS[name]['model']]
    if model is not None:
        m = re.search(r'ee\.3dshapes/([^"]+)\.wrl', model[1])
        if m and os.path.exists(os.path.join(MODELS, m.group(1) + '.stpZ')):
            model[1] = '"${KIPRJMOD}/og.3dshapes/%s.stpZ"' % m.group(1)
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

def pad_fp(name, w, h, shape='roundrect', paste=False, desc=''):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('og', name))
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

def pth_pad_fp(name, w, h, drill, desc=''):
    """Plated through-hole solder pad, w x h mm on every copper layer.
    The wire goes through the board and the joint wets both sides and the
    barrel, so a crash cannot peel it off the way it lifts a surface pad,
    and the current reaches every copper layer (the inner planes
    included) through the barrel.  The pad is long enough for the bulk
    capacitor's leg to be soldered beside the wire."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('og', name))
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    p = pcbnew.PAD(fp)
    p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT); p.SetRoundRectRadiusRatio(0.3)
    p.SetSize(pcbnew.VECTOR2I(MM(w), MM(h))); p.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
    ls = pcbnew.LSET.AllCuMask(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        _rect(fp, lay, -MM(w / 2 + 0.1), -MM(h / 2 + 0.1), MM(w / 2 + 0.1), MM(h / 2 + 0.1), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.4), MM(0.4)))
    fp.Reference().SetTextThickness(MM(0.06))
    fp.Value().SetVisible(False)
    return fp

HOLE_D = 3.2        # M2 soft-mount grommet neck
HOLE_KEEP = 2.8     # grommet flange radius (2.6) + clearance: no part

def hole_fp():
    """Mounting hole for an M2 soft-mount grommet: a 3.2 mm unplated hole,
    and the grommet flange's keepout as a courtyard on both sides, so no
    part lands under the rubber."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('og', 'MOUNT_M2'))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription('Mounting hole: 3.2 mm unplated, for an M2 soft-mount grommet; '
                         'courtyard = grommet flange keepout (r 2.8 mm)')
    p = pcbnew.PAD(fp)
    p.SetNumber(''); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(HOLE_D), MM(HOLE_D))); p.SetDrillSize(pcbnew.VECTOR2I(MM(HOLE_D), MM(HOLE_D)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(HOLE_KEEP), 0))
        c.SetLayer(lay); c.SetWidth(MM(0.05)); fp.Add(c)
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
    fp.SetFPID(pcbnew.LIB_ID('og', name))
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
    fp.SetFPID(pcbnew.LIB_ID('og', name))
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
        m.m_Filename = '${KIPRJMOD}/og.3dshapes/R_1206_3216Metric.stpZ'
        fp.Models().append(m)
    return fp

# High-density chip passives: KiCad's own R/C footprints, pads and 3D model
# untouched, with the courtyard at IPC-7351 density level L (0.1 mm round
# the pads and body, where KiCad's library uses level N, 0.25 mm).  The
# board is packed at that density; JLCPCB places 0201 parts 0.15 mm apart.
DENSE = {'R_0201_0603Metric': 'Resistor_SMD', 'R_0402_1005Metric': 'Resistor_SMD',
         'C_0201_0603Metric': 'Capacitor_SMD', 'C_0402_1005Metric': 'Capacitor_SMD',
         'C_0603_1608Metric': 'Capacitor_SMD'}


def dense_fp(name, lib):
    import pcb
    fp = pcb.load_fp('%s:%s' % (lib, name))
    fp.SetFPID(pcbnew.LIB_ID('og', name + '_L'))
    x0 = y0 = 1e9; x1 = y1 = -1e9
    for it in list(fp.GraphicalItems()):
        if it.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            fp.Remove(it)
        elif it.GetLayer() == pcbnew.F_Fab and it.GetClass() == 'PCB_SHAPE':
            bb = it.GetBoundingBox()
            x0, y0, x1, y1 = min(x0, bb.GetLeft()), min(y0, bb.GetTop()), max(x1, bb.GetRight()), max(y1, bb.GetBottom())
    for pd in fp.Pads():
        bb = pd.GetBoundingBox()
        x0, y0, x1, y1 = min(x0, bb.GetLeft()), min(y0, bb.GetTop()), max(x1, bb.GetRight()), max(y1, bb.GetBottom())
    m = MM(0.1)
    _rect(fp, pcbnew.F_CrtYd, x0 - m, y0 - m, x1 + m, y1 + m, 0.05)
    fp.SetLibDescription(fp.GetLibDescription() + ' (courtyard: IPC-7351 density level L, 0.1 mm)')
    return fp


def main():
    # fixed item IDs: regenerating the library changes only what changed
    pcbnew.KIID.SeedGenerator(1)
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, '*.kicad_mod')):
        os.remove(f)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW, '*.kicad_mod'))):
        fp = clean_easyeda(path)
        _save(LIB, fp); n += 1
    gen = [
        pad_fp('PAD_BAT', 2.8, 3.8, desc='Battery lead pad: 18 AWG lead and the bulk capacitor leg side '
               'by side; vias in the pad (filled) take the current to the inner planes'),
        pad_fp('PAD_MOTOR', 1.6, 2.4, desc='Motor phase wire pad (26-22 AWG)'),
        pad_fp('PAD_SIG', 1.1, 1.1, desc='Signal / power solder pad'),
        # a plated hole: the test point is its own via, so a chip on the
        # far side reaches it with no via of its own, and a pogo pin finds
        # it from either side
        pth_pad_fp('PAD_TP', 0.75, 0.75, 0.35, desc='Test point (SWD probe), plated through'),
        hole_fp(),
    ]
    gen += [shunt_hcs1206_fp()]
    gen += [dense_fp(n, l) for n, l in sorted(DENSE.items())]
    for fp in gen:
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))

if __name__ == '__main__':
    main()
