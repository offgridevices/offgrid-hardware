# -*- coding: utf-8 -*-
"""Post-routing finishing: silkscreen labels, orientation arrows, board
name, and removal of the stray track stubs an autorouter leaves behind.

Silkscreen rules followed here: 0.8 mm text with 0.15 mm strokes (JLCPCB
and PCBWay both print that legibly), no silk over pads, nothing closer than
0.3 mm to the board edge.  Labels are placed from tables in the board's
layout module, relative to the pad they name."""
import json, subprocess
import pcbnew
import pcb

def hide_fields(b):
    for fp in b.GetFootprints():
        for fld in fp.GetFields():
            if not (fld.IsReference() or fld.IsValue()):
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)

def pad_xy(b, ref, pad='1'):
    for fp in b.GetFootprints():
        if fp.GetReference() == ref:
            for p in fp.Pads():
                if p.GetNumber() == pad:
                    q = p.GetPosition()
                    return q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY
    raise KeyError(ref)

def label_pads(b, labels, size=0.8, layer=pcbnew.F_SilkS):
    """labels: ref -> (text, dx, dy, justify)   offsets from the pad centre."""
    for ref, (s, dx, dy, just) in labels.items():
        x, y = pad_xy(b, ref)
        pcb.text(b, s, x + dx, y + dy, size=size, layer=layer, just=just)

def arrow(b, x, y, length=4.0, layer=pcbnew.F_SilkS, width=0.2, angle=0, head=0.7):
    """Filled-head arrow centred on (x, y) pointing to -y (the front),
    rotated by `angle` degrees clockwise on screen.  Returns its items."""
    import math
    a = math.radians(angle)
    def R(px, py):
        return (x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a))
    h = length / 2
    items = []
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcb.P(*R(0, h))); s.SetEnd(pcb.P(*R(0, -h + head * 1.3))); s.SetLayer(layer); s.SetWidth(pcb.MM(width))
    b.Add(s); items.append(s)
    items.append(pcb.poly_shape(b, [R(0, -h), R(-head, -h + head * 1.6), R(head, -h + head * 1.6)], layer,
                                fill=True, width=0.1))
    return items

def remove_dangling(path, rounds=5):
    """Delete track pieces KiCad reports as dangling (open at one end), as
    many times as it takes: removing one stub can expose the next."""
    total = 0
    for _ in range(rounds):
        out = path + '.dangling.json'
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', out, path],
                       capture_output=True)
        ids = set()
        for v in json.load(open(out))['violations']:
            if v['type'] == 'track_dangling':
                ids.update(i['uuid'] for i in v['items'])
        if not ids:
            break
        b = pcbnew.LoadBoard(path)
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in ids:
                pcb.remove(b, t); total += 1
        b.Save(path)
    return total


class SilkPlacer:
    """Places silkscreen text and marks where they touch nothing: no pad
    (exposed copper), no hole, no other silk, and 0.3 mm inside the edge.
    Each item gets a list of candidate spots and takes the first that fits."""
    def __init__(self, b, side='T', pad_clear=0.12, silk_clear=0.15, edge=0.35, bodies=False):
        from shapely.geometry import Polygon, Point, box
        self.b, self.side = b, side
        self.layer = pcbnew.F_SilkS if side == 'T' else pcbnew.B_SilkS
        cu = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
        self.blocks = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(cu) or p.GetDrillSize().x > 0:
                    sp = p.GetEffectivePolygon(cu) if p.IsOnLayer(cu) else None
                    if sp is not None and sp.OutlineCount():
                        ol = sp.Outline(0)
                        g = Polygon([(ol.CPoint(i).x / 1e6, ol.CPoint(i).y / 1e6) for i in range(ol.PointCount())])
                        self.blocks.append(g.buffer(pad_clear))
                    if p.GetDrillSize().x > 0:
                        q = p.GetPosition()
                        self.blocks.append(Point(q.x / 1e6, q.y / 1e6).buffer(p.GetDrillSize().x / 2e6 + 0.3))
        if bodies:
            # part bodies too: silk under a component is invisible once it
            # is assembled (courtyards of solder pads / test points excepted)
            crt = pcbnew.F_CrtYd if side == 'T' else pcbnew.B_CrtYd
            for fp in b.GetFootprints():
                if fp.IsFlipped() != (side == 'B') or fp.GetReference().startswith(('P_', 'TP', 'H')):
                    continue
                cy = fp.GetCourtyard(crt)
                if cy.OutlineCount():
                    bb = cy.BBox()
                    self.blocks.append(box(bb.GetLeft() / 1e6 + 0.1, bb.GetTop() / 1e6 + 0.1,
                                           bb.GetRight() / 1e6 - 0.1, bb.GetBottom() / 1e6 - 0.1))
        e = pcb.HALF - edge
        self.inside = box(pcb.CX - e, pcb.CY - e, pcb.CX + e, pcb.CY + e)
        self.silk_clear = silk_clear
        self.placed = []

    def _fits(self, g):
        from shapely.geometry import box
        if not self.inside.contains(g):
            return False
        if any(g.intersects(k) for k in self.blocks):
            return False
        return not any(g.distance(k) < self.silk_clear for k in self.placed)

    def _bbox(self, item):
        from shapely.geometry import box
        # text: the strokes themselves, not the (taller) text box
        bb = item.GetEffectiveTextShape().BBox() if hasattr(item, 'GetEffectiveTextShape') else item.GetBoundingBox()
        return box(bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)

    def text(self, s, spots, size=0.8, thick=0.15):
        """spots: [(x, y, rot, just), ...] in board-centre mm."""
        for sp in spots:
            x, y, rot, just = sp[:4]
            sz = sp[4] if len(sp) > 4 else size
            t = pcb.text(self.b, s, x, y, size=sz, layer=self.layer, rot=rot, thick=thick, just=just)
            g = self._bbox(t)
            if self._fits(g):
                self.placed.append(g)
                return (x, y)
            pcb.remove(self.b, t)
        print('   silk: no room for %r' % s)
        return None

    def label(self, ref, s, pad='1', size=0.8, dist=1.0):
        """Label a pad: try beside it on every side, nearest first."""
        x, y = pad_xy(self.b, ref, pad)
        fp = [f for f in self.b.GetFootprints() if f.GetReference() == ref][0]
        p = [q for q in fp.Pads() if q.GetNumber() == pad][0]
        bb = p.GetBoundingBox()
        hw, hh = bb.GetWidth() / 2e6, bb.GetHeight() / 2e6
        # first choice: straight inboard of the pad, reading along the edge
        # for side pads, rotated to fit the pitch for pads along front/rear
        if abs(x) >= abs(y):
            sx = -1 if x > 0 else 1
            spots = [(x + sx * (hw + 0.35), y, 0, 'left' if sx > 0 else 'right')]
        else:
            sy = -1 if y > 0 else 1
            spots = [(x, y + sy * (hh + 0.35 + 0.55), 90, None)]
        # then nudged a little along the pad row, then a size smaller,
        # before wandering off to another side
        ix, iy, ir, ij = spots[0]
        side = abs(x) >= abs(y)
        nudges = [(ix, iy + n, ir, ij) if side else (ix + n, iy, ir, ij) for n in (0.15, -0.15, 0.3, -0.3)]
        spots = [sp + (sz,) for sz in (size, size - 0.1) for sp in spots + nudges]
        for d in (dist, dist + 0.4, dist + 0.9):
            ring = [(x + hw + d - 0.6, y, 0, 'left'), (x - hw - d + 0.6, y, 0, 'right'),
                    (x, y + hh + d, 0, None), (x, y - hh - d, 0, None),
                    (x, y + hh + d + 0.2, 90, None), (x, y - hh - d - 0.2, 90, None)]
            # the side facing the middle of the board first: labels read inwards
            ring.sort(key=lambda s: (s[0] ** 2 + s[1] ** 2))
            spots += [sp + (size,) for sp in ring]
        return self.text(s, spots, size=size)

    def shape(self, draw, spots):
        """draw(x, y) adds items and returns them; tried at each (x, y)."""
        from shapely.ops import unary_union
        for x, y in spots:
            items = draw(x, y)
            g = unary_union([self._bbox(i) for i in items])
            if self._fits(g):
                self.placed.append(g)
                return (x, y)
            for i in items:
                pcb.remove(self.b, i)
        print('   silk: no room for shape')
        return None

    def grid_spots(self, prefer, radius=16.0, step=0.4):
        """Every grid point of the board, nearest to `prefer` first."""
        px, py = prefer
        pts = []
        n = int(pcb.HALF / step)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = i * step, j * step
                d = (x - px) ** 2 + (y - py) ** 2
                if d <= radius ** 2:
                    pts.append((d, x, y))
        pts.sort()
        return [(x, y) for _, x, y in pts]

    def text_near(self, s, prefer, size=0.8, radius=16.0, rot=0, thick=0.15):
        return self.text(s, [(x, y, rot, None) for x, y in self.grid_spots(prefer, radius)], size=size,
                         thick=thick)

    def shape_near(self, draw, prefer, radius=16.0):
        return self.shape(draw, self.grid_spots(prefer, radius))

    def label_along(self, ref, s, pad='1', size=1.0, gap=0.35):
        """Label beside the pad along its row (edge pads in a row): after
        it first, then before it; unrotated.  Falls back to label()."""
        x, y = pad_xy(self.b, ref, pad)
        fp = [f for f in self.b.GetFootprints() if f.GetReference() == ref][0]
        p = [q for q in fp.Pads() if q.GetNumber() == pad][0]
        bb = p.GetBoundingBox()
        hw, hh = bb.GetWidth() / 2e6, bb.GetHeight() / 2e6
        if abs(y) > abs(x):      # pad on the front or rear edge: row runs along x
            sy = -1 if y > 0 else 1
            spots = [(x + hw + gap, y, 0, 'left'), (x - hw - gap, y, 0, 'right'),
                     (x, y + sy * (hh + gap + size / 2), 0, None)]
        else:                    # left or right edge: row runs along y
            sx = -1 if x > 0 else 1
            spots = [(x, y + hh + gap + size / 2, 0, None), (x, y - hh - gap - size / 2, 0, None),
                     (x + sx * (hw + gap), y, 0, 'left' if sx > 0 else 'right')]
        # a rotated digit reads as a dash: stay upright, shrink before giving up
        spots = [sp + (sz,) for sz in (size, size - 0.2, size - 0.3) for sp in spots]
        return self.text(s, spots, size=size)
