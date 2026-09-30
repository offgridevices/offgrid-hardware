# -*- coding: utf-8 -*-
"""A board's copper as rasters, read from its .kicad_pcb with pcbnew.

For each copper layer, which net owns each cell of a square grid (res mm):
zone fills, tracks, pads and via lands, drawn as KiCad fills them.  Holes
(vias and plated through-hole pads) join the layers they span; the board
file's stackup gives each layer's copper thickness and the dielectric
between layers.  Terminals are a part's pads on one net (a FET's three
source pins, its drain pins and tab), which is where a part puts current
into, or takes it out of, the copper.

The grid is cached per board file and resolution in sim/out/, so the DC
and thermal solvers can be rerun without pcbnew.
"""
import os, re, hashlib, pickle
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
BOARDS = {'fc': os.path.join(RIDGE, 'fc', 'ridge3-fc.kicad_pcb'),
          'esc': os.path.join(RIDGE, 'esc', 'ridge3-esc.kicad_pcb')}
NM = 1e-6          # pcbnew units (nm) to mm


def stackup(path):
    """[(name, kind, thickness mm)] top to bottom, copper and dielectric only."""
    text = open(path).read()
    i = text.index('(stackup')
    out = []
    for m in re.finditer(r'\(layer "([^"]+)"\s*\(type "([^"]+)"\)(.*?)\n\t\t\t\)', text[i:], re.S):
        name, kind, body = m.groups()
        t = re.search(r'\(thickness ([0-9.]+)', body)
        if kind == 'copper' or kind in ('core', 'prepreg'):
            out.append((name, 'copper' if kind == 'copper' else 'dielectric', float(t.group(1))))
        if name == 'B.Cu':
            break
    return out


class Copper:
    """The raster: owner[layer, iy, ix] = net index, or -1 for no copper."""

    def cell(self, x, y):
        return (int((y - self.y0) / self.res), int((x - self.x0) / self.res))

    def xy(self, iy, ix):
        return self.x0 + (ix + 0.5) * self.res, self.y0 + (iy + 0.5) * self.res

    def net(self, name):
        return self.nets.index(name)


def _polys(sp):
    """Fractured polygon set -> list of (n, 2) point arrays in mm."""
    sp = sp.__class__(sp)
    sp.Fracture()
    return [np.array([(p.x * NM, p.y * NM) for p in sp.COutline(i).CPoints()])
            for i in range(sp.OutlineCount())]


def _draw(img, polys, value, x0, y0, res):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for P in polys:
        if len(P) >= 3:
            d.polygon([((x - x0) / res, (y - y0) / res) for x, y in P], fill=value)


def _mask(polys, x0, y0, res, shape):
    from PIL import Image
    img = Image.new('L', (shape[1], shape[0]), 0)
    _draw(img, polys, 1, x0, y0, res)
    return np.array(img, bool)


def extract(board, res=0.05):
    """Read a board (fc or esc, or the path of any .kicad_pcb) into a Copper
    raster, cached in sim/out/."""
    path = BOARDS.get(board, board)
    label = board if board in BOARDS else os.path.splitext(os.path.basename(board))[0]
    key = hashlib.sha1(open(path, 'rb').read() + repr(res).encode()).hexdigest()[:12]
    cache = os.path.join(OUT, 'copper-%s-%s.pkl' % (label, key))
    if os.path.exists(cache):
        c = Copper()
        c.__dict__.update(pickle.load(open(cache, 'rb')))
        return c
    import pcbnew
    from PIL import Image
    b = pcbnew.LoadBoard(path)
    cu = [l for l in b.GetEnabledLayers().CuStack()]
    names = [b.GetLayerName(l) for l in cu]
    st = stackup(path)
    thick = {n: t for n, k, t in st if k == 'copper'}
    # z of each copper layer's mid-plane, from the top surface of F.Cu
    z, zc, diel = 0.0, {}, []
    for n, k, t in st:
        if k == 'copper':
            zc[n] = z + t / 2
        else:
            diel.append(t)
        z += t
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetX() * NM, bb.GetY() * NM
    nx = int(np.ceil(bb.GetWidth() * NM / res))
    ny = int(np.ceil(bb.GetHeight() * NM / res))
    nets = sorted({n for n in (i.GetNetname() for i in
                   list(b.GetTracks()) + list(b.Zones()) + [p for f in b.GetFootprints() for p in f.Pads()])
                   if n})
    index = {n: i for i, n in enumerate(nets)}
    owner = np.full((len(cu), ny, nx), -1, np.int32)
    for li, L in enumerate(cu):
        img = Image.new('I', (nx, ny), -1)
        # zones first, then tracks, pads and vias on top (same net anyway)
        for zn in b.Zones():
            if zn.GetIsRuleArea() or not zn.IsOnLayer(L) or not zn.GetNetname():
                continue
            if zn.HasFilledPolysForLayer(L):
                _draw(img, _polys(zn.GetFilledPolysList(L)), index[zn.GetNetname()], x0, y0, res)
        items = [t for t in b.GetTracks()] + [p for f in b.GetFootprints() for p in f.Pads()]
        for it in items:
            if not it.GetNetname() or not it.IsOnLayer(L):
                continue
            if it.GetClass() == 'PCB_VIA' and not it.FlashLayer(L):
                continue
            if it.GetClass() == 'PAD' and not it.FlashLayer(L):
                continue
            sp = pcbnew.SHAPE_POLY_SET()
            it.TransformShapeToPolygon(sp, L, 0, int(res / 10 / NM), pcbnew.ERROR_INSIDE)
            _draw(img, _polys(sp), index[it.GetNetname()], x0, y0, res)
        owner[li] = np.array(img, np.int32)
    sp = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(sp, True)
    inside = _mask(_polys(sp), x0, y0, res, (ny, nx))
    owner[:, ~inside] = -1

    holes, terminals, partsd = [], {}, {}
    span = lambda item: [i for i, L in enumerate(cu) if item.IsOnLayer(L)]
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            holes.append(dict(x=p.x * NM, y=p.y * NM, d=t.GetDrillValue() * NM, net=t.GetNetname(),
                              layers=span(t), kind='via'))
    for f in b.GetFootprints():
        ref = f.GetReference()
        p = f.GetPosition()
        side = 'bottom' if f.IsFlipped() else 'top'
        partsd[ref] = dict(value=f.GetValue(), x=p.x * NM, y=p.y * NM, side=side,
                           rot=f.GetOrientationDegrees())
        for pad in f.Pads():
            net = pad.GetNetname()
            if not net:
                continue
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetDrillSize().x > 0:
                q = pad.GetPosition()
                holes.append(dict(x=q.x * NM, y=q.y * NM, d=pad.GetDrillSize().x * NM, net=net,
                                  layers=list(range(len(cu))), kind='pad', ref=ref))
            T = terminals.setdefault((ref, net), dict(ref=ref, net=net, cells={}, pads=[]))
            T['pads'].append(pad.GetNumber())
            for li, L in enumerate(cu):
                if not pad.FlashLayer(L):
                    continue
                sp = pcbnew.SHAPE_POLY_SET()
                pad.TransformShapeToPolygon(sp, L, 0, int(res / 10 / NM), pcbnew.ERROR_INSIDE)
                m = _mask(_polys(sp), x0, y0, res, (ny, nx)) & (owner[li] == index[net])
                if m.any():
                    T['cells'][li] = np.union1d(T['cells'].get(li, np.zeros(0, int)),
                                                np.flatnonzero(m))
    c = Copper()
    c.board, c.path, c.res, c.x0, c.y0, c.nx, c.ny = board, path, res, x0, y0, nx, ny
    c.layers, c.nets, c.owner, c.inside = names, nets, owner, inside
    c.t = [thick[n] for n in names]                 # copper thickness, mm
    c.zc = [zc[n] for n in names]                   # copper mid-plane depth, mm
    c.diel = diel                                   # dielectric between layer i and i+1, mm
    c.thickness = z
    c.holes, c.terminals, c.parts = holes, terminals, partsd
    os.makedirs(OUT, exist_ok=True)
    pickle.dump(c.__dict__, open(cache, 'wb'))
    return c


if __name__ == '__main__':
    import sys
    for bd in sys.argv[1:] or ['esc', 'fc']:
        c = extract(bd)
        print('%s: %d x %d cells of %.2f mm, layers %s' % (bd, c.nx, c.ny, c.res, c.layers))
        print('  copper mm', c.t, 'dielectric mm', c.diel, 'total %.3f' % c.thickness)
        for li, n in enumerate(c.layers):
            cov = (c.owner[li] >= 0).sum() / c.inside.sum()
            print('  %-6s %3.0f %% copper' % (n, 100 * cov))
        print('  %d holes, %d terminals' % (len(c.holes), len(c.terminals)))
