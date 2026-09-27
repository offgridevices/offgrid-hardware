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
2. Copper-only footprints generated here: battery, motor and signal solder
   pads, test points, and the M3 mounting hole.

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

def _pad_box(p):
    at = _get(p, 'at'); sz = _get(p, 'size')
    x, y = float(at[1]), float(at[2]); rot = float(at[3]) if len(at) > 3 else 0.0
    w, h = float(sz[1]), float(sz[2])
    if round(rot) % 180 == 90:
        w, h = h, w
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2

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
            if c[3] == 'custom':           # USB-C GND/VBUS: plain rectangles
                pts = _get(_get(_get(c, 'primitives'), 'gr_poly'), 'pts')
                px = [float(q[1]) for q in pts[1:]]; py = [float(q[2]) for q in pts[1:]]
                c = [x for x in c if not (isinstance(x, list) and x[0] == 'primitives')]
                c[3] = 'rect'
                _get(c, 'size')[1:] = ['%.3f' % (max(px) - min(px)), '%.3f' % (max(py) - min(py))]
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

def hole_fp():
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('aio', 'HOLE_M3'))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetLibDescription('3.2 mm non-plated hole: M3, or M2 through a soft-mount grommet')
    p = pcbnew.PAD(fp)
    p.SetNumber(''); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(3.2), MM(3.2))); p.SetDrillSize(pcbnew.VECTOR2I(MM(3.2), MM(3.2)))
    ls = pcbnew.LSET.AllCuMask(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(MM(3.0), 0))
    c.SetLayer(pcbnew.F_CrtYd); c.SetWidth(MM(0.05)); fp.Add(c)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    return fp

def main():
    os.makedirs(LIB, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, '*.kicad_mod')):
        os.remove(f)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW, '*.kicad_mod'))):
        fp = clean_easyeda(path)
        _save(LIB, fp); n += 1
    gen = [
        pad_fp('PAD_BAT', 2.6, 5.0, desc='Battery lead pad, 18 AWG + bulk capacitor leg'),
        pad_fp('PAD_MOTOR', 2.0, 2.3, desc='Motor phase wire pad'),
        pad_fp('PAD_SIG', 1.1, 1.6, desc='Signal / power solder pad'),
        pad_fp('PAD_TP', 0.9, 0.9, shape='circle', desc='Test point'),
        hole_fp(),
    ]
    for fp in gen:
        _save(LIB, fp); n += 1
    print('wrote %d footprints to %s' % (n, LIB))

if __name__ == '__main__':
    main()
