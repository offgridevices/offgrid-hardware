# -*- coding: utf-8 -*-
"""Build ../ph.pretty, the board's own footprint library.

Two kinds of footprint go in:

1. JLCPCB/EasyEDA footprints for the exact LCSC parts, converted once with
   easyeda2kicad 1.0.1 and kept verbatim in easyeda_raw/ (only their 3D
   model paths were shortened).  They are cleaned here, as for Ridge 3 Lite
   (ridge3-lite/v1/src/footprints.py, where this code comes from):
   - the courtyard is rebuilt as the box round pads + body + 0.10 mm;
   - silkscreen is dropped (the assembly drawing carries the outlines);
   - 3D models point at ../ph.3dshapes (gzip STEP, KiCad reads .stpZ);
   - custom pads that are plain rectangles become rect pads;
   - FIXUPS below.
2. Footprints generated here: the M3 mounting hole and the test pad.

Run with KiCad's Python: it uses pcbnew to read and write footprints so the
output is exactly KiCad's own format.
"""
import os, sys, glob, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'ph.pretty'))
RAW = os.path.join(HERE, 'easyeda_raw')
MODELS = os.path.normpath(os.path.join(HERE, '..', 'ph.3dshapes'))

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
#   'model':  a 3D model (in ../ph.3dshapes) for a part EasyEDA has none for
#   'model_offset': move the 3D model (mm, KiCad's 3D axes: +y is up the
#             screen) where EasyEDA's model does not sit on its own land
#   'drop_unnamed': leave out the pads with no number (the module's
#             thermal vias: the board places its own ground vias)
FIXUPS = {
    # The ESP32-S3 module's EasyEDA land carries twelve unnumbered 0.4 mm
    # plated holes in its ground pad (thermal vias).  Unnumbered, they would
    # come out as unplated holes; the board's own ground vias replace them.
    'WIFIM-SMD_ESP32-S3-WROOM-1-N8': dict(drop_unnamed=True),
    # HRO TYPE-C-31-M-12: EasyEDA's model sits 2.55 mm back from its land
    # (its mouth 2.55 mm behind where the footprint's outline puts it, the
    # SMT legs off the pads).  Only the renders and the STEP see this.
    'USB-C_SMD-TYPE-C-31-M-12_1': dict(model_offset=(0.0, -2.55, 0.0)),
    # Jing Extension 902-131A (C2345): the land matches the maker's drawing
    # (mouth 10.3 mm ahead of the shell legs, 14.1 mm body); EasyEDA's model
    # sits 4.3 mm behind it, over the parts behind the receptacle
    'USB-A-TH__USB-AF-90': dict(model_offset=(0.0, -4.3, 0.0)),
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
            if c[1] == '""' and FIXUPS.get(name, {}).get('drop_unnamed'):
                continue
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
            model[1] = '"${KIPRJMOD}/ph.3dshapes/%s.stpZ"' % m.group(1)
            off = FIXUPS.get(name, {}).get('model_offset')
            if off:
                _get(_get(model, 'offset'), 'xyz')[1:] = ['%.3f' % v for v in off]
            out.append(model)
    open(os.path.join(LIB, name + '.kicad_mod'), 'w').write(_emit(out) + '\n')
    # round-trip through KiCad so the file is in its native format
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID('ph', name))
    return fp

def _rect(fp, layer, x0, y0, x1, y1, w):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        a, b = pts[i], pts[(i + 1) % 4]
        s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))


def pth_pad_fp(name, d, drill, desc=''):
    """Plated test pad, d mm round on both sides: a probe or a soldered
    wire reaches it from either side."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('ph', name))
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    p = pcbnew.PAD(fp)
    p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(d), MM(d))); p.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
    ls = pcbnew.LSET.AllCuMask(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        _rect(fp, lay, -MM(d / 2 + 0.1), -MM(d / 2 + 0.1), MM(d / 2 + 0.1), MM(d / 2 + 0.1), 0.05)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
    fp.Reference().SetTextThickness(MM(0.08))
    fp.Value().SetVisible(False)
    return fp


HOLE_D = 3.2        # M3 clearance
HOLE_KEEP = 3.5     # an M3 pan head (5.5 mm) or a printed boss: no part inside this radius


def hole_fp():
    """Mounting hole for an M3 screw: 3.2 mm unplated, and a round
    courtyard on both sides the size of the screw head and its clearance,
    so no part lands under the head."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('ph', 'MOUNT_M3'))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription('Mounting hole: 3.2 mm unplated, for an M3 screw; courtyard r 3.5 mm')
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


def main():
    # fixed item IDs: regenerating the library changes only what changed
    pcbnew.KIID.SeedGenerator(1)
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, '*.kicad_mod')):
        os.remove(f)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW, '*.kicad_mod'))):
        _save(LIB, clean_easyeda(path)); n += 1
    for fp in (pth_pad_fp('PAD_TP', 1.6, 0.9, desc='Test pad, plated, 1.6 mm'), hole_fp()):
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))


if __name__ == '__main__':
    main()
