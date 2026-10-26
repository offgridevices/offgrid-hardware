# -*- coding: utf-8 -*-
"""Build ../lc.pretty, the three boards' footprint library.

Two kinds of footprint go in:

1. JLCPCB/EasyEDA footprints for the exact LCSC parts, converted once with
   easyeda2kicad 1.0.1 and kept verbatim in easyeda_raw/ (only their 3D
   model paths were shortened).  They are cleaned here, as for Ridge 3 Lite
   (ridge3-lite/v1/src/footprints.py, where this code comes from):
   - the courtyard is rebuilt as the box round pads + body + 0.10 mm;
   - silkscreen is dropped (the assembly drawing carries the outlines);
   - 3D models point at ../lc.3dshapes (gzip STEP, KiCad reads .stpZ);
   - custom pads that are plain rectangles become rect pads;
   - FIXUPS below.
2. Footprints generated here: the M2 and M1.6 holes and the test pad.

Run with KiCad's Python: it uses pcbnew to read and write footprints so the
output is exactly KiCad's own format.
"""
import os, sys, glob, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lc.pretty'))
RAW = os.path.join(HERE, 'easyeda_raw')
MODELS = os.path.normpath(os.path.join(HERE, '..', 'lc.3dshapes'))

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
#   'model':  a 3D model (in ../lc.3dshapes) for a part EasyEDA has none for
#   'model_offset': move the 3D model (mm, KiCad's 3D axes: +y is up the
#             screen) where EasyEDA's model does not sit on its own land
#   'drop_unnamed': leave out the pads with no number (the module's
#             thermal vias: the board places its own ground vias)
#   'paste_grid': {pad: (n, side)}: the pad's paste as n x n squares of
#             `side` mm instead of one sheet (a large exposed pad: about
#             55 % coverage, so the part neither floats nor voids)
FIXUPS = {
    # the AP6256's EasyEDA land is the AP6212 family's (same 12 x 12, 44
    # pads + three test points); its model is the AP6212's
    # the RV1106's 7 x 7 mm exposed pad: 4 x 4 windows of 1.3 mm (55 %)
    'QFN-128_L12.3-W12.3-P0.35-TL-EP7.0-1': {'paste_grid': {'129': (4, 1.3)}},
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
    cx = FIXUPS.get(name, {}).get('courtyard_x')
    if cx:
        x0, x1 = max(x0, -cx), min(x1, cx)
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        out.append(_line(a[0], a[1], b[0], b[1], 'F.CrtYd', 0.05))
    if model is None and FIXUPS.get(name, {}).get('model'):
        model = ['model', '"ee.3dshapes/%s.wrl"' % FIXUPS[name]['model']]
    if model is not None:
        m = re.search(r'ee\.3dshapes/([^"]+)\.wrl', model[1])
        if m and os.path.exists(os.path.join(MODELS, m.group(1) + '.stpZ')):
            model[1] = '"${KIPRJMOD}/../lc.3dshapes/%s.stpZ"' % m.group(1)
            off = FIXUPS.get(name, {}).get('model_offset')
            if off:
                _get(_get(model, 'offset'), 'xyz')[1:] = ['%.3f' % v for v in off]
            out.append(model)
    open(os.path.join(LIB, name + '.kicad_mod'), 'w').write(_emit(out) + '\n')
    # round-trip through KiCad so the file is in its native format
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID('lc', name))
    for num, (n, side) in FIXUPS.get(name, {}).get('paste_grid', {}).items():
        _paste_grid(fp, num, n, side)
    return fp


def _paste_grid(fp, num, n, side):
    pad = next(p for p in fp.Pads() if p.GetNumber() == num)
    ls = pad.GetLayerSet()
    ls.RemoveLayer(pcbnew.F_Paste)
    pad.SetLayerSet(ls)
    c = pad.GetFPRelativePosition()
    w = pad.GetSize(pcbnew.F_Cu).x / 1e6
    pitch = w / n
    for i in range(n):
        for j in range(n):
            p = pcbnew.PAD(fp)
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
            p.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(int(side * 1e6), int(side * 1e6)))
            pl = pcbnew.LSET()
            pl.AddLayer(pcbnew.F_Paste)
            p.SetLayerSet(pl)
            p.SetFPRelativePosition(pcbnew.VECTOR2I(c.x + int((i - (n - 1) / 2) * pitch * 1e6),
                                                   c.y + int((j - (n - 1) / 2) * pitch * 1e6)))
            fp.Add(p)

def smd_pad_fp(name, d, desc=''):
    """Round SMD test pad on F: a probe or a soldered wire reaches it."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('lc', name))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    p = pcbnew.PAD(fp)
    p.SetNumber('1'); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(d), MM(d)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(d / 2 + 0.1), 0))
    c.SetLayer(pcbnew.F_CrtYd); c.SetWidth(MM(0.05)); fp.Add(c)
    fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
    fp.Reference().SetTextThickness(MM(0.08))
    fp.Value().SetVisible(False)
    return fp


def hole_fp(name, d, keep_f, keep_b, desc):
    """Unplated mounting hole, d mm, with a round courtyard on each side:
    keep_f on F (the back face: screw head or washer), keep_b on B (the
    housing's boss or the lens holder)."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('lc', name))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription(desc)
    p = pcbnew.PAD(fp)
    p.SetNumber(''); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(d), MM(d))); p.SetDrillSize(pcbnew.VECTOR2I(MM(d), MM(d)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    for lay, r in ((pcbnew.F_CrtYd, keep_f), (pcbnew.B_CrtYd, keep_b)):
        c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(r), 0))
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
    for fp in (smd_pad_fp('PAD_TP', 1.0, desc='Test pad, SMD, 1.0 mm'),
               hole_fp('MOUNT_M2', 2.2, 2.1, 2.0, 'M2 screw hole 2.2 mm: head r 2.1 behind, boss r 2.0 in front'),
               hole_fp('MOUNT_M1V6', 1.8, 1.9, 1.0, 'M1.6 screw hole 1.8 mm: washer r 1.9 behind')):
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))


if __name__ == '__main__':
    main()
