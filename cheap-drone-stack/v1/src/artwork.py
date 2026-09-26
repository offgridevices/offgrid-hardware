# -*- coding: utf-8 -*-
"""Post-routing finishing: silkscreen labels, orientation arrows, board
name, and removal of the stray track stubs an autorouter leaves behind.

Silkscreen rules followed here: every stroke at least 0.15 mm wide
(JLCPCB and PCBWay both print that), no silk over pads, nothing closer than
0.35 mm to the board edge.  Labels are placed from tables in the board's
layout module, relative to the pad they name.  With brand=True the text is
set in the OffGrid brand styles (brand.py) as filled outlines: labels in
Instrument Sans 500, numerals and codes in JetBrains Mono 500; `size` is
then the capital height in mm."""
import json, subprocess
import pcbnew
import pcb

def hide_fields(b):
    for fp in b.GetFootprints():
        for fld in fp.GetFields():
            if not (fld.IsReference() or fld.IsValue()):
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)

def strip(b):
    """Remove board-level silkscreen (text and drawings, not footprint
    graphics) so the artwork can be laid out again."""
    n = 0
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            pcb.remove(b, d); n += 1
    return n

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
    """Delete track pieces KiCad reports as dangling (open at one end), and
    unlocked vias that join nothing, as many times as it takes: removing one
    stub can expose the next."""
    total = 0
    for _ in range(rounds):
        out = path + '.dangling.json'
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', out, path],
                       capture_output=True)
        ids = set()
        for v in json.load(open(out))['violations']:
            if v['type'] in ('track_dangling', 'via_dangling'):
                ids.update(i['uuid'] for i in v['items'])
        if not ids:
            break
        b = pcbnew.LoadBoard(path)
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in ids and not t.IsLocked():
                pcb.remove(b, t); total += 1
        b.Save(path)
    return total


_SHAPED = {}          # shaped brand text, by (text, size, face)


class SilkPlacer:
    """Places silkscreen text and marks where they touch nothing: no pad
    (exposed copper), no hole, no other silk, and 0.3 mm inside the edge.
    Each item gets a list of candidate spots and takes the first that fits."""
    def __init__(self, b, side='T', pad_clear=0.12, silk_clear=0.15, edge=0.35, bodies=False,
                 brand=False, via_clear=None):
        from shapely.geometry import Polygon, Point, box
        self.b, self.side, self.brand = b, side, brand
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
                    # courtyards carry 0.25 mm of margin round the part
                    self.blocks.append(box(bb.GetLeft() / 1e6 + 0.25, bb.GetTop() / 1e6 + 0.25,
                                           bb.GetRight() / 1e6 - 0.25, bb.GetBottom() / 1e6 - 0.25))
        # vias: tented, but the drill still punches through the ink.  Artwork
        # placed with vias=True keeps clear of them.
        self.vias = []
        if via_clear is not None:
            for t in b.GetTracks():
                if isinstance(t, pcbnew.PCB_VIA):
                    q = t.GetPosition()
                    self.vias.append(Point(q.x / 1e6, q.y / 1e6).buffer(t.GetDrillValue() / 2e6 + via_clear))
        e = pcb.HALF - edge
        self.inside = box(pcb.CX - e, pcb.CY - e, pcb.CX + e, pcb.CY + e)
        self.silk_clear = silk_clear
        self.placed = []

    def _fits(self, g, vias=False, margin=0.0):
        if not self.inside.contains(g):
            return False
        gm = g.buffer(margin, join_style='mitre') if margin else g
        if any(gm.intersects(k) for k in self.blocks):
            return False
        if vias and any(g.intersects(k) for k in self.vias):
            return False
        return not any(g.distance(k) < self.silk_clear for k in self.placed)

    def _brand_geom(self, s, x, y, rot, just, size, face):
        """Brand text as a shapely geometry in KiCad mm (absolute)."""
        import brand
        from shapely import affinity
        key = (repr(s), size, face)
        if key not in _SHAPED:
            if isinstance(s, (list, tuple)):
                _SHAPED[key] = brand.line(s, size)[0]
            else:
                _SHAPED[key] = brand.styled(face, s, size)[0]
        g = brand.place(_SHAPED[key], x, y, anchor={'left': 'l', 'right': 'r'}.get(just, 'c'), rot=rot,
                        mirror=self.side == 'B')
        return affinity.translate(g, pcb.CX, pcb.CY)

    def _add_geom(self, g):
        import brand
        from shapely import affinity
        return brand.add(self.b, affinity.translate(g, -pcb.CX, -pcb.CY), self.layer)

    def geom(self, g, spots, clear=0.0, vias=True, margin=0.4, quiet=False):
        """Place a ready-made shapely geometry (board-centre mm, drawn round
        the origin) at the first (x, y) where it fits; `clear` is extra room
        kept round it for the next items (the mark's clear space)."""
        from shapely import affinity
        best = None
        for x, y in spots:
            h = affinity.translate(g, pcb.CX + x, pcb.CY + y)
            env = h.envelope
            if vias == 'fewest':
                # tented vias under silk are harmless; take the spot where
                # the fewest drills land on the ink, earliest spot on a tie
                if self._fits(env, margin=margin):
                    hits = sum(1 for v in self.vias if h.intersects(v))
                    if best is None or hits < best[0]:
                        best = (hits, x, y, h, env)
                continue
            if self._fits(env, vias=vias, margin=margin):
                best = (0, x, y, h, env)
                break
        if best is None:
            if not quiet:
                print('   silk: no room for artwork')
            return None
        _, x, y, h, env = best
        self._add_geom(h)
        self.placed.append(env.buffer(clear, join_style='mitre') if clear else env)
        return (x, y)

    def _bbox(self, item):
        from shapely.geometry import box
        # text: the strokes themselves, not the (taller) text box
        bb = item.GetEffectiveTextShape().BBox() if hasattr(item, 'GetEffectiveTextShape') else item.GetBoundingBox()
        return box(bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)

    def text(self, s, spots, size=0.8, thick=0.15, face='sans', vias=False):
        """spots: [(x, y, rot, just), ...] in board-centre mm.  With brand
        faces `s` may also be a list of (face, text) runs."""
        best = None
        for sp in spots:
            x, y, rot, just = sp[:4]
            sz = sp[4] if len(sp) > 4 else size
            if self.brand:
                g = self._brand_geom(s, x, y, rot, just, sz, face)
                env = g.envelope
                if vias == 'fewest':
                    if self._fits(env):
                        hits = sum(1 for v in self.vias if g.intersects(v))
                        if best is None or hits < best[0]:
                            best = (hits, x, y, g, env)
                    continue
                if self._fits(env, vias=vias):
                    self._add_geom(g)
                    self.placed.append(env)
                    return (x, y)
                continue
            t = pcb.text(self.b, s, x, y, size=sz, layer=self.layer, rot=rot, thick=thick, just=just)
            g = self._bbox(t)
            if self._fits(g, vias=vias):
                self.placed.append(g)
                return (x, y)
            pcb.remove(self.b, t)
        if best is not None:
            _, x, y, g, env = best
            self._add_geom(g)
            self.placed.append(env)
            return (x, y)
        print('   silk: no room for %r' % (s,))
        return None

    def label(self, ref, s, pad='1', size=0.8, dist=1.0, face='sans', shrink=0.1, smallest=None):
        """Label a pad: straight inboard of it first (rotated along the
        front and rear edges, where the pads stand side by side), at every
        size down to `smallest`; then beside it on every side; then the
        nearest spot within 3 mm."""
        x, y = pad_xy(self.b, ref, pad)
        fp = [f for f in self.b.GetFootprints() if f.GetReference() == ref][0]
        p = [q for q in fp.Pads() if q.GetNumber() == pad][0]
        bb = p.GetBoundingBox()
        hw, hh = bb.GetWidth() / 2e6, bb.GetHeight() / 2e6
        smallest = size - shrink if smallest is None else smallest
        sizes = [round(size - k * 0.1, 2) for k in range(int(round((size - smallest) / 0.1)) + 1)]
        def length(sz):
            if not self.brand:
                return 0.55 * 2
            import brand
            return brand.styled(face, s, sz)[1]
        side = abs(x) >= abs(y)
        interior = max(abs(x), abs(y)) < pcb.HALF - 3.5      # a test point, not an edge pad
        spots = []
        for sz in sizes:
            if interior:
                spots += [(x - hw - 0.35, y, 0, 'right', sz), (x + hw + 0.35, y, 0, 'left', sz)]
                continue
            if side:
                sx = -1 if x > 0 else 1
                first = (x + sx * (hw + 0.35), y, 0, 'left' if sx > 0 else 'right')
            else:
                sy = -1 if y > 0 else 1
                first = (x, y + sy * (hh + 0.35 + length(sz) / 2), 90, None)
            ix, iy, ir, ij = first
            nudges = [(ix, iy + n, ir, ij) if side else (ix + n, iy, ir, ij) for n in (0.15, -0.15, 0.3, -0.3)]
            spots += [sp + (sz,) for sp in [first] + nudges]
        for d in (dist, dist + 0.4, dist + 0.9):
            ring = [(x + hw + d - 0.6, y, 0, 'left'), (x - hw - d + 0.6, y, 0, 'right'),
                    (x, y + hh + d, 0, None), (x, y - hh - d, 0, None),
                    (x, y + hh + d + 0.2, 90, None), (x, y - hh - d - 0.2, 90, None)]
            # the side facing the middle of the board first: labels read
            # inwards; upright before rotated
            ring.sort(key=lambda s: (s[2] != 0, s[0] ** 2 + s[1] ** 2))
            spots += [sp + (sz,) for sz in sizes for sp in ring]
        # last resort: the nearest spot within 3 mm where it fits at all,
        # upright if it can be
        grid = self.grid_spots((x, y), 3.0, 0.1)
        near = [(px, py, rot, None, sizes[-1]) for rot in (0, 90) for px, py in grid]
        return self.text(s, spots + near, size=size, face=face)

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

    def text_near(self, s, prefer, size=0.8, radius=16.0, rot=0, thick=0.15, face='sans', vias=False):
        return self.text(s, [(x, y, rot, None) for x, y in self.grid_spots(prefer, radius)], size=size,
                         thick=thick, face=face, vias=vias)

    def shape_near(self, draw, prefer, radius=16.0):
        return self.shape(draw, self.grid_spots(prefer, radius))

    def label_along(self, ref, s, pad='1', size=1.0, gap=0.35, sizes=None, face='sans'):
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
        spots = [sp + (sz,) for sz in (sizes or (size, size - 0.2, size - 0.3)) for sp in spots]
        return self.text(s, spots, size=size, face=face)
