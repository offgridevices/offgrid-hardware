# -*- coding: utf-8 -*-
"""Complete the last few connections Freerouting leaves unrouted.

A plain grid maze router: 0.05 mm cells on the two outer copper layers, a
via allowed wherever a via fits.  Every other net's copper is inflated by
(clearance + half the track width) and drawn as an obstacle; the route
must stay clear of it.  One connection at a time, cheapest path by A*,
bends and vias cost extra so paths come out short and tidy.  KiCad's own
DRC checks the result afterwards - this router is never trusted alone.
"""
import heapq, math, os
import numpy as np
import pcbnew
import pcb
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

def MM(v): return pcbnew.FromMM(float(v))
RES = 0.05                      # mm per cell

def mm(v): return v / 1e6

class Grid:
    def __init__(self, board, layers, clearance, track_w, via_d, edge=0.3, clmap=None, soft_nets=None,
                 window=None):
        """window: (x0, y0, x1, y1) mm, the part of the board the grid
        covers (its border is kept free like the board edge); default the
        whole board."""
        bb = board.GetBoardEdgesBoundingBox()
        if window is None:
            window = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
        self.window = window
        self.x0, self.y0 = window[0], window[1]
        self.W = int(math.ceil((window[2] - window[0]) / RES)) + 1
        self.H = int(math.ceil((window[3] - window[1]) / RES)) + 1
        self.board, self.layers = board, layers
        self.cl, self.tw, self.vd, self.edge = clearance, track_w, via_d, edge
        self.clmap = clmap or {}
        self.soft_nets = set(soft_nets or ())

    def px(self, x, y):
        return ((x - self.x0) / RES, (y - self.y0) / RES)

    def cell(self, x, y):
        return (int(round((x - self.x0) / RES)), int(round((y - self.y0) / RES)))

    def xy(self, i, j):
        return (self.x0 + i * RES, self.y0 + j * RES)

    def _draw(self, img, geom):
        d = ImageDraw.Draw(img)
        gs = geom.geoms if hasattr(geom, 'geoms') else [geom]
        for g in gs:
            if g.is_empty:
                continue
            d.polygon([self.px(x, y) for x, y in g.exterior.coords], fill=1)

    def netcl(self, net):
        return self.clmap.get(net, self.cl)

    def copper(self, net_exclude):
        """Per-layer list of (geometry, clearance) of copper not on
        net_exclude, plus geometry of copper on it."""
        other = {l: [] for l in self.layers}; same = {l: [] for l in self.layers}
        self.soft = {l: [] for l in self.layers}
        self.inner_zones = {}
        self.outer_zones = {}
        self.same_via_holes = []
        self.pofv_holes = []
        holes = []
        b = self.board
        wx0, wy0, wx1, wy1 = self.window
        def out(bb):
            # wholly outside the grid (with a margin for clearances)
            return (mm(bb.GetRight()) < wx0 - 1 or mm(bb.GetLeft()) > wx1 + 1 or
                    mm(bb.GetBottom()) < wy0 - 1 or mm(bb.GetTop()) > wy1 + 1)
        for fp in b.GetFootprints():
            if out(fp.GetBoundingBox()):
                continue
            for pad in fp.Pads():
                for l in self.layers:
                    if pad.IsOnLayer(l):
                        sp = pad.GetEffectivePolygon(l)
                        for k in range(sp.OutlineCount()):
                            ol = sp.Outline(k)
                            g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                            if pad.GetNetname() == net_exclude and pad.GetNetname():
                                same[l].append(g)
                            else:
                                other[l].append((g, self.netcl(pad.GetNetname())))
                # unplated holes need their own clearance; a plated hole is
                # inside its pad's copper, already counted above (and a
                # pad of the net being routed must stay reachable)
                if pad.GetDrillSize().x > 0 and pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    p = pad.GetPosition()
                    holes.append(Point(mm(p.x), mm(p.y)).buffer(mm(pad.GetDrillSize().x) / 2))
        for t in b.GetTracks():
            if out(t.GetBoundingBox()):
                continue
            soft = (t.GetNetname() in self.soft_nets and t.GetNetname() != net_exclude and not t.IsLocked())
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                # at least VIA_RING of ring: other copper then keeps the
                # hole-to-copper rule from a thin-ringed via's hole
                r = max(mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2 + VIA_RING)
                g = Point(mm(p.x), mm(p.y)).buffer(r)
                for l in self.layers:
                    if soft:
                        self.soft[l].append((g, self.netcl(t.GetNetname()), t.GetNetname()))
                    elif t.GetNetname() == net_exclude:
                        same[l].append(g)
                    else:
                        other[l].append((g, self.netcl(t.GetNetname())))
                if t.GetNetname() == net_exclude:
                    # a new via of this net must still keep its hole clear of this one's
                    self.same_via_holes.append(Point(mm(p.x), mm(p.y)).buffer(mm(t.GetDrillValue()) / 2))
                if POFV_GAP and mm(t.GetDrillValue()) >= POFV_DRILL - 1e-3:
                    # filled (via-in-pad) vias keep POFV_GAP to every other hole
                    self.pofv_holes.append(Point(mm(p.x), mm(p.y)).buffer(mm(t.GetDrillValue()) / 2))
            elif t.GetLayer() in self.layers:
                s, e = t.GetStart(), t.GetEnd()
                g = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2)
                if soft:
                    self.soft[t.GetLayer()].append((g, self.netcl(t.GetNetname()), t.GetNetname()))
                elif t.GetNetname() == net_exclude:
                    same[t.GetLayer()].append(g)
                else:
                    other[t.GetLayer()].append((g, self.netcl(t.GetNetname())))
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            # (z.GetLayer() is not the zone's layer for every zone: ask the set)
            for l in self.layers:
                if not (z.GetLayerSet().Contains(l) and z.IsFilled()):
                    continue
                fp_ = z.GetFilledPolysList(l)
                for k in range(fp_.OutlineCount()):
                    ol = fp_.Outline(k)
                    g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                    if z.GetNetname() == net_exclude:
                        same[l].append(g)
                    elif l in (pcbnew.F_Cu, pcbnew.B_Cu):
                        # an outer pour keeps tracks out; a via may stand in
                        # it at a price (ZONE_VIA_COST): the fill opens round it
                        self.outer_zones.setdefault(l, []).append((g, self.netcl(z.GetNetname())))
                    else:
                        # an inner-layer pour only keeps tracks out: a via
                        # through it just gets a clearance hole in the fill
                        self.inner_zones.setdefault(l, []).append((g, self.netcl(z.GetNetname())))
        return other, same, holes

    def build(self, net):
        other, same, holes = self.copper(net)
        self.block = {}; self.vblock = None
        M = RES * 1.2                     # grid rounding margin
        mine = self.netcl(net)
        vmask = Image.new('1', (self.W, self.H), 0)
        vzone = Image.new('1', (self.W, self.H), 0)
        for l in self.layers:
            img = Image.new('1', (self.W, self.H), 0)
            for g, c in other[l]:
                c = max(c, mine)
                self._draw(img, g.buffer(c + self.tw / 2 + M, 8)); self._draw(vmask, g.buffer(c + self.vd / 2 + M, 8))
            for g in holes:
                self._draw(img, g.buffer(0.3 + self.tw / 2 + M, 8)); self._draw(vmask, g.buffer(0.3 + self.vd / 2 + M, 8))
            for g, c in self.inner_zones.get(l, []) + self.outer_zones.get(l, []):
                self._draw(img, g.buffer(max(c, mine) + self.tw / 2 + M, 8))
            for g, c in self.outer_zones.get(l, []):
                self._draw(vzone, g.buffer(max(c, mine) + self.vd / 2 + M, 8))
            self.block[l] = np.array(img, dtype=bool)
        for g in self.same_via_holes:
            self._draw(vmask, g.buffer(HOLE_TO_HOLE + VIA_DRILL / 2 + M, 8))
        for g in self.pofv_holes:
            self._draw(vmask, g.buffer(POFV_GAP + VIA_DRILL / 2 + M, 8))
        # inner layers: a via may not hit another net's pad or via there either
        for l in (pcbnew.In1_Cu, pcbnew.In2_Cu):
            pass
        for z in self.board.Zones():
            if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                ol = z.Outline().Outline(0)
                g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                if z.GetDoNotAllowTracks():
                    for l in self.layers:
                        if z.GetLayerSet().Contains(l):
                            img = Image.fromarray(self.block[l]); self._draw(img, g.buffer(self.tw / 2 + M)); self.block[l] = np.array(img, dtype=bool)
                if z.GetDoNotAllowVias():
                    self._draw(vmask, g.buffer(self.vd / 2 + M))
        # board edge: everything outside the outline shrunk by the edge
        # clearance (the outline itself, not the bounding box of the edge
        # graphics, which their line width widens, and with the corner slots)
        e = int(math.ceil((self.edge + self.tw / 2) / RES)); ev = int(math.ceil((self.edge + self.vd / 2) / RES))
        for l in self.layers:
            self.block[l][:e, :] = True; self.block[l][-e:, :] = True
            self.block[l][:, :e] = True; self.block[l][:, -e:] = True
        vb = np.array(vmask, dtype=bool)
        vb[:ev, :] = True; vb[-ev:, :] = True; vb[:, :ev] = True; vb[:, -ev:] = True
        ps = pcbnew.SHAPE_POLY_SET()
        if self.board.GetBoardPolygonOutlines(ps, False) and ps.OutlineCount():
            ol = ps.Outline(0)
            outline = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
            for pad, masks in ((self.tw / 2, [self.block[l] for l in self.layers]), (self.vd / 2, [vb])):
                img = Image.new('1', (self.W, self.H), 0)
                self._draw(img, outline.buffer(-(self.edge + pad + M), 8))
                inside = np.array(img, dtype=bool)
                for m in masks:
                    m |= ~inside
        self.vblock = vb
        # soft (rippable) copper: passable at a price
        self.sblock = {}
        self.sweight = {}
        vs = Image.new('1', (self.W, self.H), 0)
        vw = Image.new('L', (self.W, self.H), 0)
        for l in self.layers:
            img = Image.new('1', (self.W, self.H), 0)
            wimg = Image.new('L', (self.W, self.H), 0)
            # the cost of crossing another net's copper is its weight
            # (SOFT_WEIGHT, x10 in the image); heavier nets drawn last win
            for g, c, n in sorted(self.soft[l], key=lambda t: SOFT_WEIGHT.get(t[2], 1.0)):
                c = max(c, mine)
                wv = int(min(255, round(10 * SOFT_WEIGHT.get(n, 1.0))))
                gt, gv = g.buffer(c + self.tw / 2 + M, 8), g.buffer(c + self.vd / 2 + M, 8)
                self._draw(img, gt); self._draw(vs, gv)
                self._draw_val(wimg, gt, wv); self._draw_val(vw, gv, wv)
            self.sblock[l] = np.array(img, dtype=bool)
            self.sweight[l] = np.array(wimg, dtype=np.float32) / 10.0
        self.vsoft = np.array(vs, dtype=bool)
        self.vweight = np.array(vw, dtype=np.float32) / 10.0
        # vias in other nets' outer pours: passable at ZONE_VIA_COST (in
        # rip_cost units), never a victim
        vz = np.array(vzone, dtype=bool) & ~self.vsoft
        self.vsoft |= vz
        self.vweight[vz] = ZONE_VIA_COST
        return same

    def _draw_val(self, img, geom, val):
        d = ImageDraw.Draw(img)
        gs = geom.geoms if hasattr(geom, 'geoms') else [geom]
        for g in gs:
            if g.is_empty:
                continue
            d.polygon([self.px(x, y) for x, y in g.exterior.coords], fill=val)

# Copper layers the maze router may use.  Boards with an inner signal
# layer (the ESC's In2 is a VBAT ring round a routable centre) add it.
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]

def _same_cells(grid, same, layer):
    img = Image.new('1', (grid.W, grid.H), 0)
    for g in same[layer]:
        grid._draw(img, g)
    return np.array(img, dtype=bool)

# Via the maze router drops (a board may set smaller ones, see esc_layout)
VIA_D, VIA_DRILL = 0.45, 0.25
# Every via is an obstacle with at least this ring (see route.VIA_RING)
VIA_RING = 0.0
HOLE_TO_HOLE = 0.25
# JLCPCB via-in-pad (POFV): the in-pad vias (0.3 mm drill here; every
# 0.3 mm-drill via is treated as one) keep more than 0.45 mm hole to hole
# from any other hole.  None switches this off.
POFV_GAP, POFV_DRILL = 0.46, 0.3


# WINDOW (mm): a search may first stay within this margin of the two
# islands' bounding box, and cover the whole board only if that finds
# nothing.  Off: on the ESC it neither sped the searches up (the expansions
# dominate, not the grid) nor routed as much (local paths block others).
WINDOW = None
# with a WINDOW: a coarser grid tried first in the window (and alone over
# the whole board); RES then serves the window only.  None: RES throughout
COARSE = None
# negotiated congestion: net -> the weight of crossing that net's copper
# (rip_cost x weight); a net torn up again and again grows heavier
SOFT_WEIGHT = {}
# a via in another net's outer-layer pour costs this x rip_cost
ZONE_VIA_COST = 0.5
# signal track width and clearance (JLCPCB multilayer: 0.09 / 0.09 mm)
SIG_W = float(os.environ.get('SIG_W', 0.09))
SIG_CL = float(os.environ.get('SIG_CL', 0.09))
# a net that will not fit at its own width may fall back to SIG_W
WIDTH_FALLBACK = True
# the price (grid cells of detour) of crossing another net's copper once
RIP_COST = float(os.environ.get('RIP_COST', 60))
# search budget (cells) of route_connection's last, whole-board try
LAST_TRY_EXPAND = 50_000_000


def route_connection(board, net, a_items, b_items, clearance=None, track_w=None, via_d=None, via_drill=None,
                     max_expand=None, clmap=None, soft_nets=None, rip_cost=None, victims_out=None):
    """Route from copper island A to island B of `net`.  a_items/b_items are
    lists of shapely geometries per layer: {layer: [geom,...]}.  The search
    budget (cells expanded) scales with the grid's cell count per mm^2."""
    global RES
    if rip_cost is None:
        rip_cost = RIP_COST
    clearance = SIG_CL if clearance is None else clearance
    track_w = SIG_W if track_w is None else track_w
    if max_expand is None:
        max_expand = int(3_000_000 * (0.05 / RES) ** 2)
    bb = board.GetBoardEdgesBoundingBox()
    full = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
    win = full
    if WINDOW is not None:
        bx = [g.bounds for items in (a_items, b_items) for gl in items.values() for g in gl]
        win = (max(full[0], min(b[0] for b in bx) - WINDOW), max(full[1], min(b[1] for b in bx) - WINDOW),
               min(full[2], max(b[2] for b in bx) + WINDOW), min(full[3], max(b[3] for b in bx) + WINDOW))
    # coarse and local first (fast), then fine (0.5 mm-pitch lanes), then
    # the whole board at the coarse grid and last at the fine one (a pin
    # boxed in at the coarse grid that has a way out between pads)
    base = RES
    if COARSE and win != full:
        tries = [(COARSE, win), (base, win), (COARSE, full), (base, full)]
    else:
        tries = [(base, win), (base, full)] if win != full else [(base, full)]
    def budget_of(r, w):
        b = int(max_expand * (base / r) ** 2) if w == win else int(max_expand * (base / r) ** 2 // 2)
        if (r, w) == tries[-1] and _C is not None:
            b = max(b, LAST_TRY_EXPAND)     # the last resort: the C search can afford the whole board
        return b
    # with soft copper, a path that crosses other nets is only kept when no
    # later (wider) try finds one that crosses nothing
    strict = bool(soft_nets) and victims_out is not None
    crossing = None
    try:
        for k, (r, w) in enumerate(tries):
            RES = r
            vic = set() if victims_out is not None else None
            before = set(t.m_Uuid.AsString() for t in board.GetTracks()) if strict else None
            res = _route_in(board, net, a_items, b_items, clearance, track_w, via_d, via_drill,
                            budget_of(r, w), clmap, soft_nets, rip_cost, vic, w)
            if not res:
                continue
            if strict and vic and k < len(tries) - 1:
                if crossing is None:
                    crossing = k
                for t in list(board.GetTracks()):
                    if t.m_Uuid.AsString() not in before:
                        pcb.remove(board, t)
                continue
            if vic:
                victims_out |= vic
            return res
        if crossing is not None:
            r, w = tries[crossing]
            RES = r
            vic = set()
            res = _route_in(board, net, a_items, b_items, clearance, track_w, via_d, via_drill,
                            budget_of(r, w), clmap, soft_nets, rip_cost, vic, w)
            victims_out |= vic
            return res
    finally:
        RES = base
    return None


def _route_in(board, net, a_items, b_items, clearance, track_w, via_d, via_drill, max_expand, clmap, soft_nets,
              rip_cost, victims_out, window):
    via_d = VIA_D if via_d is None else via_d
    via_drill = VIA_DRILL if via_drill is None else via_drill
    layers = list(ROUTE_LAYERS)
    g = Grid(board, layers, clearance, track_w, via_d, clmap=clmap, soft_nets=soft_nets, window=window)
    g.build(net)
    src = {}; dst = {}
    for li, l in enumerate(layers):
        src[li] = _same_cells(g, a_items, l) if l in a_items else np.zeros((g.H, g.W), bool)
        dst[li] = _same_cells(g, b_items, l) if l in b_items else np.zeros((g.H, g.W), bool)
    # targets: cells inside B copper; sources: cells inside A copper (allowed even if blocked)
    tgt = np.argwhere(np.logical_or.reduce([dst[li] for li in range(len(layers))]))
    if len(tgt) == 0:
        return None
    tc = tgt.mean(axis=0)
    H, W = g.H, g.W
    path = _astar_c(g, layers, src, dst, tc, rip_cost, max_expand) if _C is not None else None
    if path is None:
        path = _astar_py(g, layers, src, dst, tc, rip_cost, max_expand)
    if not path:
        return None
    if victims_out is not None:
        # which rippable nets does the copper this path becomes break
        # clearance to?  A track cell against the soft copper of its own
        # layer at the track's clearance; a via (where the path changes
        # layer) against every layer's at the via's
        mine = g.netcl(net)
        vias_at = set((i, j) for (li, i, j), (lp, _, _) in zip(path[1:], path) if li != lp)
        for (li, i, j) in path:
            l = layers[li]
            x, y = g.xy(i, j)
            pt = Point(x, y)
            if g.sblock[l][j, i]:
                for geom, c, n in g.soft[l]:
                    if n not in victims_out and geom.distance(pt) < max(c, mine) + track_w / 2 - 1e-3:
                        victims_out.add(n)
            if (i, j) in vias_at and g.vsoft[j, i]:
                for l2 in layers:
                    for geom, c, n in g.soft[l2]:
                        if n not in victims_out and geom.distance(pt) < max(c, mine) + via_d / 2 - 1e-3:
                            victims_out.add(n)
    # emit copper
    netinfo = board.FindNet(net)
    segs = 0; vias = 0
    run = [path[0]]
    def flush(run):
        nonlocal segs
        if len(run) < 2:
            return
        # simplify collinear points
        pts = [run[0]]
        for a, b2, c2 in zip(run, run[1:], run[2:]):
            if (b2[1] - a[1], b2[2] - a[2]) != (c2[1] - b2[1], c2[2] - b2[2]):
                pts.append(b2)
        pts.append(run[-1])
        l = layers[run[0][0]]
        for p, q in zip(pts, pts[1:]):
            x1, y1 = g.xy(p[1], p[2]); x2, y2 = g.xy(q[1], q[2])
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
            t.SetWidth(MM(track_w)); t.SetLayer(l); t.SetNet(netinfo); board.Add(t); segs += 1
    for p in path[1:]:
        if p[0] != run[-1][0]:
            flush(run)
            x, y = g.xy(p[1], p[2])
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(netinfo); board.Add(v); vias += 1
            run = [p]
        else:
            run.append(p)
    flush(run)
    # the path's end cells count as inside A and B at the grid's
    # resolution; their centres may still stand a few microns outside the
    # real copper (a pad's rounded corner).  Join each end to its copper.
    from shapely.ops import nearest_points
    for cell, items in ((path[0], a_items), (path[-1], b_items)):
        l = layers[cell[0]]
        gs = items.get(l)
        if not gs:
            continue
        x, y = g.xy(cell[1], cell[2])
        pt = Point(x, y)
        G = unary_union(gs)
        inner = G.buffer(-min(track_w / 2, 0.03))
        if inner.is_empty:
            inner = G
        if inner.contains(pt):
            continue
        q = nearest_points(inner, pt)[0]
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(x), MM(y))); t.SetEnd(pcbnew.VECTOR2I(MM(q.x), MM(q.y)))
        t.SetWidth(MM(track_w)); t.SetLayer(l); t.SetNet(netinfo); board.Add(t); segs += 1
    return segs, vias

def islands(board, net):
    """Group a net's copper into connected islands using KiCad's connectivity."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    items = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                items.append(pad)
    for t in board.GetTracks():
        if t.GetNetname() == net:
            items.append(t)
    # union-find on items connected per KiCad
    parent = list(range(len(items)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    idx = {id(x): n for n, x in enumerate(items)}
    for n, it in enumerate(items):
        for c in conn.GetConnectedItems(it) if hasattr(conn, 'GetConnectedItems') else []:
            m = idx.get(id(c))
            if m is not None:
                parent[find(n)] = find(m)
    groups = {}
    for n in range(len(items)):
        groups.setdefault(find(n), []).append(items[n])
    return list(groups.values())

def _geom_of(item):
    """{layer: [shapely geometry]} for a pad, track or via."""
    out = {}
    cls = item.GetClass()
    if cls == 'PAD':
        for l in ROUTE_LAYERS:
            if item.IsOnLayer(l):
                sp = item.GetEffectivePolygon(l)
                for k in range(sp.OutlineCount()):
                    ol = sp.Outline(k)
                    out.setdefault(l, []).append(Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y))
                                                          for q in range(ol.PointCount())]))
    elif cls == 'PCB_VIA':
        p = item.GetPosition()
        g = Point(mm(p.x), mm(p.y)).buffer(mm(item.GetWidth(pcbnew.F_Cu)) / 2)
        out = {l: [g] for l in ROUTE_LAYERS}
    elif cls in ('PCB_TRACK', 'PCB_ARC'):
        s, e = item.GetStart(), item.GetEnd()
        if item.GetLayer() in ROUTE_LAYERS:
            out[item.GetLayer()] = [LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(item.GetWidth()) / 2)]
    return out

def finish_board(pcb_in, pcb_out, drc_json, rules=None, rounds=3, clmap=None, skip=()):
    """Route every connection KiCad's DRC reports as unconnected (but the
    nets in `skip`)."""
    import json, subprocess
    src = pcb_in
    for r in range(rounds):
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json',
                        '-o', drc_json, src], capture_output=True)
        rep = json.load(open(drc_json))
        pairs = rep['unconnected_items']
        if not pairs:
            if src != pcb_out:
                import shutil; shutil.copy(src, pcb_out)
            return 0
        b = pcbnew.LoadBoard(src)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        byid = {}
        for fp in b.GetFootprints():
            for p in fp.Pads():
                byid[p.m_Uuid.AsString()] = p
        for t in b.GetTracks():
            byid[t.m_Uuid.AsString()] = t
        done = 0
        for u in pairs:
            its = [byid.get(i['uuid']) for i in u['items']]
            if None in its:
                continue
            net = its[0].GetNetname()
            if net in skip:
                continue
            wide = (rules or {}).get(net, SIG_W)
            res = route_connection(b, net, _geom_of(its[0]), _geom_of(its[1]), track_w=wide, clmap=clmap)
            print('   finish %-12s %s' % (net, 'routed (%d segments, %d vias)' % res if res else 'NO PATH'))
            done += bool(res)
        b.Save(pcb_out)
        src = pcb_out
        if done == 0:
            break
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json', '-o', drc_json, pcb_out],
                   capture_output=True)
    return len(json.load(open(drc_json))['unconnected_items'])

def _net_components(board, net):
    """Connected copper islands of one net, by geometry (pads, tracks, vias
    that touch).  Returns list of {layer: [geoms]}."""
    items = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                items.append(_geom_of(p))
    for t in board.GetTracks():
        if t.GetNetname() == net:
            items.append(_geom_of(t))
    # filled pours of the net join what they touch
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsFilled():
            continue
        for l in ROUTE_LAYERS:
            if not z.GetLayerSet().Contains(l):
                continue
            fp_ = z.GetFilledPolysList(l)
            for k in range(fp_.OutlineCount()):
                ol = fp_.Outline(k)
                pts = [(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())]
                if len(pts) >= 3:
                    items.append({l: [Polygon(pts).buffer(0)]})
    n = len(items)
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            for l in items[i]:
                if l in items[j] and any(a.intersects(b) for a in items[i][l] for b in items[j][l]):
                    parent[find(i)] = find(j); break
    comps = {}
    for i in range(n):
        c = comps.setdefault(find(i), {})
        for l, gs in items[i].items():
            c.setdefault(l, []).extend(gs)
    return list(comps.values())

def _dist(a, b):
    d = 1e9
    for l in a:
        if l in b:
            for x in a[l]:
                for y in b[l]:
                    d = min(d, x.distance(y))
    if d == 1e9:     # different layers only: distance ignoring layer
        for x in [g for gs in a.values() for g in gs]:
            for y in [g for gs in b.values() for g in gs]:
                d = min(d, x.distance(y))
    return d

def route_taps(board, taps, clmap=None, layers=None, via=None, log=print):
    """Join the low-current pins of supply nets to the rest of their net at
    their own, narrower width, before the autorouter fills the board: a
    feedback divider's top, a converter's bias pin and its capacitor, a
    small regulator's input.  The net's full width is for the paths that
    carry its current; these pins cannot carry it, and a feedback line
    should be thin anyway.  taps: {(ref, pad number): width}.  A tap's
    island is joined to its nearest neighbour until it holds a pour of the
    net or a pad that is not a tap.  Returns the taps left unjoined."""
    global ROUTE_LAYERS, VIA_D, VIA_DRILL
    saved = ROUTE_LAYERS, VIA_D, VIA_DRILL
    if layers:
        ROUTE_LAYERS = list(layers)
    if via:
        VIA_D, VIA_DRILL = via
    left = []
    try:
        pads = {(fp.GetReference(), p.GetNumber()): p for fp in board.GetFootprints() for p in fp.Pads()}
        for key, w in sorted(taps.items()):
            pad = pads[key]
            net = pad.GetNetname()
            trunk = [_geom_of(p) for k, p in pads.items() if p.GetNetname() == net and k not in taps]
            for z in board.Zones():
                if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsFilled():
                    for l in ROUTE_LAYERS:
                        if z.GetLayerSet().Contains(l):
                            fp_ = z.GetFilledPolysList(l)
                            for k in range(fp_.OutlineCount()):
                                ol = fp_.Outline(k)
                                pts = [(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())]
                                if len(pts) >= 3:
                                    trunk.append({l: [Polygon(pts).buffer(0)]})
            for _ in range(8):
                comps = _net_components(board, net)
                mine = [c for c in comps if _touch(c, _geom_of(pad))]
                if not mine or any(_touch(mine[0], t) for t in trunk):
                    break
                others = [c for c in comps if c is not mine[0]]
                if not others:
                    break
                before = set(t.m_Uuid.AsString() for t in board.GetTracks())
                # the nearest island first; if it is walled in, the next ones
                for near in sorted(others, key=lambda c: _dist(mine[0], c))[:4]:
                    res = route_connection(board, net, mine[0], near, track_w=w, clmap=clmap)
                    if res:
                        break
                if not res:
                    left.append(key)
                    break
                for t in board.GetTracks():
                    if t.m_Uuid.AsString() not in before:
                        t.SetLocked(True)
            log('   tap %-10s %s.%s at %.2f mm%s' % (net, key[0], key[1], w, ' NOT JOINED' if key in left else ''))
    finally:
        ROUTE_LAYERS, VIA_D, VIA_DRILL = saved
    return left


def _touch(a, b):
    return any(x.intersects(y) for l in a if l in b for x in a[l] for y in b[l])


PAIR_TRIES = 12


def route_net(board, net, track_w=None, clmap=None, lock=True, soft_nets=None, victims_out=None):
    """Join every island of `net`, nearest pair first.  Returns islands left."""
    track_w = SIG_W if track_w is None else track_w
    for _ in range(40):
        comps = _net_components(board, net)
        if len(comps) <= 1:
            return 0
        pairs = sorted((_dist(comps[i], comps[j]), i, j)
                       for i in range(len(comps)) for j in range(i + 1, len(comps)))
        before = set(t.m_Uuid.AsString() for t in board.GetTracks())
        # nearest pair first; a pair with no path (a pin boxed in on that
        # side) gives way to the next nearest, up to PAIR_TRIES of them
        res = None
        for _d, i, j in pairs[:PAIR_TRIES]:
            res = route_connection(board, net, comps[i], comps[j], track_w=track_w, clmap=clmap,
                                   soft_nets=soft_nets, victims_out=victims_out)
            if res:
                break
        if not res and WIDTH_FALLBACK and track_w > SIG_W + 1e-6:
            # no room at the net's own width: the signal width (a short
            # narrow stretch of a supply or the USB pair is harmless)
            for _d, i, j in pairs[:PAIR_TRIES]:
                res = route_connection(board, net, comps[i], comps[j], track_w=SIG_W, clmap=clmap,
                                       soft_nets=soft_nets, victims_out=victims_out)
                if res:
                    break
        if not res:
            return len(comps) - 1
        if lock:
            for t in board.GetTracks():
                if t.m_Uuid.AsString() not in before:
                    t.SetLocked(True)
    return len(_net_components(board, net)) - 1

def mst_length(board, net):
    pts = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                q = p.GetPosition(); pts.append((q.x / 1e6, q.y / 1e6))
    if len(pts) < 2:
        return 0.0
    used = [pts[0]]; rest = pts[1:]; tot = 0.0
    while rest:
        d, k = min((min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in used), i) for i, b in enumerate(rest))
        tot += d; used.append(rest.pop(k))
    return tot

def route_all(board, skip, widths=None, clmap=None, order=None):
    """Route every net not in `skip`, shortest first.  Returns failed nets."""
    nets = set()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                nets.add(p.GetNetname())
    nets -= set(skip)
    todo = sorted(nets, key=lambda n: mst_length(board, n)) if order is None else order
    failed = []
    for n in todo:
        left = route_net(board, n, track_w=(widths or {}).get(n, SIG_W), clmap=clmap, lock=False)
        if left:
            failed.append(n)
    return failed


def rip_up(board, net):
    n = 0
    for t in list(board.GetTracks()):
        if t.GetNetname() == net and not t.IsLocked():
            pcb.remove(board, t); n += 1
    return n

def route_all_ripup(board, skip, widths=None, clmap=None, max_rounds=400, log=print):
    """Route every net not in `skip`, shortest first.  A net that cannot get
    through may cross other router-made nets at a price; those nets are
    ripped up and queued again.  Tracks made before this call (locked or
    not) are never touched."""
    nets = set()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                nets.add(p.GetNetname())
    nets -= set(skip)
    queue = sorted(nets, key=lambda n: mst_length(board, n))
    mine = set()
    tries = {}
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        tries[net] = tries.get(net, 0) + 1
        w = (widths or {}).get(net, SIG_W)
        # first try without disturbing anyone
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        if left == 0:
            mine.add(net); continue
        victims = set()
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=mine - {net},
                         victims_out=victims)
        if left:
            log('   %s: no path even with rip-up' % net)
            continue
        # rip the victims out and re-queue them; the path we just laid was
        # computed around their copper, so re-route this net cleanly after
        rip_up(board, net)
        for v in victims:
            rip_up(board, v); mine.discard(v)
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        if left == 0:
            mine.add(net)
        else:
            queue.append(net)
        for v in victims:
            if v not in queue:
                queue.append(v)
        log('   %s: ripped up %s' % (net, sorted(victims)))
    failed = [n for n in nets if len(_net_components(board, n)) > 1]
    return failed

def unrouted_nets(board):
    """Nets whose copper is still in more than one piece."""
    nets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    return sorted(n for n in nets if len(_net_components(board, n)) > 1)

def repair(board, nets, protect=(), widths=None, clmap=None, max_rips=4, max_rounds=200, log=print):
    """Finish `nets` by rip-up and re-route.  A blocked net may run through
    the copper of any other signal net that has unlocked tracks (nets in
    `protect` never); those nets are torn up and routed again afterwards.
    A net torn up `max_rips` times becomes fixed, so this cannot cycle."""
    protect = set(protect)
    # pre-routed (locked) signal nets are fair game too; power stays put
    for t in board.GetTracks():
        if t.GetNetname() not in protect:
            t.SetLocked(False)
    rips = {}
    queue = list(nets)
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        w = (widths or {}).get(net, SIG_W)
        if route_net(board, net, track_w=w, clmap=clmap, lock=False) == 0:
            continue
        soft = set(t.GetNetname() for t in board.GetTracks() if not t.IsLocked()) - protect - {net}
        soft = {n for n in soft if rips.get(n, 0) < max_rips}
        victims = set()
        if route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=soft, victims_out=victims):
            log('   repair %-12s no path even through other nets' % net)
            continue
        rip_up(board, net)
        for v in victims:
            rip_up(board, v); rips[v] = rips.get(v, 0) + 1
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        log('   repair %-12s %s, tore up %s' % (net, 'routed' if not left else 'still open', sorted(victims)))
        if left:
            rips[net] = rips.get(net, 0) + 1
            if rips[net] <= max_rips:
                queue.append(net)
        for v in victims:
            if v not in queue:
                queue.append(v)
    return unrouted_nets(board)


def repair_tx(board, nets, protect=(), widths=None, clmap=None, max_rounds=60, max_victims=4, log=print,
              keep_locked=True):
    """Rip-up and re-route, one transaction at a time.  An open net may be
    routed through the copper of other (unprotected) signal nets.  First
    only the pieces of those nets that its new path runs into are taken out
    and each net's ends are joined again round the path; if that fails, the
    nets are torn up whole and routed again after it.  Either attempt is
    kept only if afterwards the open net is joined and every torn-up net
    has no more islands than before; otherwise every track and via is put
    back as it was.  Locked tracks and vias of other nets may be torn up
    too, unless keep_locked.  Returns the nets still open."""
    protect = set(protect)
    if not keep_locked:
        for t in board.GetTracks():
            if t.GetNetname() not in protect:
                t.SetLocked(False)

    def islands(n):
        return len(_net_components(board, n))

    def snapshot():
        return set(t.m_Uuid.AsString() for t in board.GetTracks())

    def rollback(before, removed):
        for t in list(board.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(board, t)
        for t in removed:
            if t.m_Uuid.AsString() in before:
                board.Add(t)

    def rip(n, removed):
        for t in list(board.GetTracks()):
            if t.GetNetname() == n and not t.IsLocked():
                removed.append(t); pcb.remove(board, t)

    queue = list(nets)
    tried = set()
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        w = (widths or {}).get(net, SIG_W)
        if route_net(board, net, track_w=w, clmap=clmap, lock=False) == 0:
            log('   repair %-12s routed' % net)
            continue
        if net in tried:
            continue
        tried.add(net)
        before = snapshot(); removed = []
        soft = set(t.GetNetname() for t in board.GetTracks() if not t.IsLocked()) - protect - {net}
        victims = set()
        if route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=soft, victims_out=victims) \
                or not victims or len(victims) > max_victims:
            rollback(before, removed)
            log('   repair %-12s no path (%d victims)' % (net, len(victims)))
            continue
        score0 = {v: islands(v) for v in victims}
        # local: keep the new path, take out only what it runs into
        new = [t for t in board.GetTracks() if t.m_Uuid.AsString() not in before]
        for t in _in_the_way(board, new, victims, clmap):
            removed.append(t); pcb.remove(board, t)
        for v in victims:
            removed.extend(_drop_floating(board, v))
        ok = True
        for v in sorted(victims):
            route_net(board, v, track_w=(widths or {}).get(v, SIG_W), clmap=clmap, lock=False)
            if islands(v) > score0[v]:
                ok = False
                break
        if ok:
            log('   repair %-12s routed, patched %s' % (net, sorted(victims)))
            continue
        rollback(before, removed)
        # whole: tear the nets up and route them again after this one
        before = snapshot(); removed = []
        rip(net, removed)
        for v in victims:
            rip(v, removed)
        ok = route_net(board, net, track_w=w, clmap=clmap, lock=False) == 0
        for v in sorted(victims):
            route_net(board, v, track_w=(widths or {}).get(v, SIG_W), clmap=clmap, lock=False)
            if islands(v) > score0[v]:
                ok = False
        if ok:
            log('   repair %-12s routed, re-routed %s' % (net, sorted(victims)))
        else:
            rollback(before, removed)
            log('   repair %-12s rolled back (victims %s)' % (net, sorted(victims)))
    return unrouted_nets(board)


def _in_the_way(board, new, nets, clmap=None, clearance=None):
    """Unlocked tracks and vias of `nets` that break clearance to the
    tracks and vias in `new`."""
    clearance = SIG_CL if clearance is None else clearance
    clmap = clmap or {}
    mine = {}
    for t in new:
        for l, gs in _geom_all(t).items():
            mine.setdefault(l, []).extend((g, clmap.get(t.GetNetname(), clearance)) for g in gs)
    out = []
    for t in board.GetTracks():
        if t.GetNetname() not in nets or t.IsLocked():
            continue
        c = clmap.get(t.GetNetname(), clearance)
        if any(g.distance(h) < max(c, ch) - 1e-4
               for l, gs in _geom_all(t).items() for g in gs for h, ch in mine.get(l, [])):
            out.append(t)
    return out


def _geom_all(item):
    """_geom_of, with a via on every copper layer it passes (it is drilled
    through all of them, routed or not)."""
    if item.GetClass() == 'PCB_VIA':
        p = item.GetPosition()
        r = max(mm(item.GetWidth(pcbnew.F_Cu)) / 2, mm(item.GetDrillValue()) / 2 + VIA_RING)
        g = Point(mm(p.x), mm(p.y)).buffer(r)
        return {l: [g] for l in pcb.CU_IDS}
    return _geom_of(item)


def _drop_floating(board, net):
    """Remove the net's unlocked track pieces that no longer reach a pad or
    a pour of the net.  Returns what was removed."""
    items = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                items.append((None, _geom_all(p)))
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsFilled():
            continue
        for l in ROUTE_LAYERS:
            if z.GetLayerSet().Contains(l):
                fp_ = z.GetFilledPolysList(l)
                for k in range(fp_.OutlineCount()):
                    ol = fp_.Outline(k)
                    pts = [(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())]
                    if len(pts) >= 3:
                        items.append((None, {l: [Polygon(pts).buffer(0)]}))
    anchored = len(items)
    for t in board.GetTracks():
        if t.GetNetname() == net:
            items.append((t, _geom_all(t)))
    parent = list(range(len(items)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            gi, gj = items[i][1], items[j][1]
            if any(a.intersects(b) for l in gi if l in gj for a in gi[l] for b in gj[l]):
                parent[find(i)] = find(j)
    roots = set(find(i) for i in range(anchored))
    out = []
    for i in range(anchored, len(items)):
        t = items[i][0]
        if find(i) not in roots and not t.IsLocked():
            out.append(t); pcb.remove(board, t)
    return out


def repair_orders(board, nets, protect=(), widths=None, clmap=None, tries=40, max_victims=10, seed=1,
                  passes=2, log=print, keep_locked=True):
    """Rip-up and re-route in random orders, one jam at a time.  For each
    open net: a 'soft' route (other signal nets may be crossed, at a cost)
    names the nets in its way.  The net and those nets are torn up and
    routed again in up to `tries` random orders (seeded: the same board
    gives the same result); the first order in which the net joins up and
    no torn-up net has more islands than before is kept, otherwise every
    track and via is put back.  Locked copper of other nets may be torn up
    too, unless keep_locked.  Returns the nets still open."""
    import random
    rnd = random.Random(seed)
    protect = set(protect)
    if not keep_locked:
        for t in board.GetTracks():
            if t.GetNetname() not in protect:
                t.SetLocked(False)

    def islands(n):
        return len(_net_components(board, n))

    def snapshot():
        return set(t.m_Uuid.AsString() for t in board.GetTracks())

    def rollback(before, removed):
        for t in list(board.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(board, t)
        for t in removed:
            board.Add(t)

    def rip(n, removed):
        for t in list(board.GetTracks()):
            if t.GetNetname() == n and not t.IsLocked():
                removed.append(t); pcb.remove(board, t)

    def width(n):
        return (widths or {}).get(n, SIG_W)

    def attempt(net):
        if islands(net) <= 1:
            return True
        before = snapshot()
        soft = set(t.GetNetname() for t in board.GetTracks() if not t.IsLocked()) - protect - {net}
        victims = set()
        route_net(board, net, track_w=width(net), clmap=clmap, lock=False, soft_nets=soft, victims_out=victims)
        for t in list(board.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(board, t)
        group = {net} | (victims - protect)
        if len(group) > max_victims + 1:
            log('   orders %-12s %d nets in the way, too many' % (net, len(group) - 1))
            return False
        base = {n: islands(n) for n in group}
        for k in range(tries):
            before = snapshot(); removed = []
            for n in group:
                rip(n, removed)
            order = sorted(group - {net}); rnd.shuffle(order)
            order = [net] + order if k % 2 == 0 else order[:len(order) // 2] + [net] + order[len(order) // 2:]
            for n in order:
                route_net(board, n, track_w=width(n), clmap=clmap, lock=False)
            now = {n: islands(n) for n in group}
            if now[net] == 1 and all(now[n] <= base[n] for n in group):
                log('   orders %-12s routed on try %d, re-routed %s' % (net, k, sorted(group - {net})))
                return True
            rollback(before, removed)
        log('   orders %-12s no order worked (%d tries, nets %s)' % (net, tries, sorted(group)))
        return False

    todo = list(nets)
    for _ in range(passes):
        todo = [n for n in todo if not attempt(n)]
        if not todo:
            break
    return [n for n in unrouted_nets(board) if n in set(nets)]


def negotiate(board, nets, protect=(), widths=None, clmap=None, max_rounds=600, grow=1.0, log=print):
    """Negotiated-congestion rip-up and re-route for the open `nets`.  Each
    open net is routed allowed to cross the other signal nets' unlocked
    copper at a price; the nets it crosses are torn up and queued again.
    Every time a net is torn up its price rises (SOFT_WEIGHT += grow), so
    the contest for the same corridors settles instead of cycling: the
    later routings go round the heavy nets.  Returns the nets still open."""
    from collections import deque
    global SOFT_WEIGHT
    protect = set(protect)
    allnets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    soft = allnets - protect
    # protected nets are routed too; they are only never torn up
    queue = deque(nets)
    tries = {}
    stuck = {}
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.popleft()
        if len(_net_components(board, net)) <= 1:
            continue
        tries[net] = tries.get(net, 0) + 1
        w = (widths or {}).get(net, SIG_W)
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        if left == 0:
            continue
        victims = set()
        before = set(t.m_Uuid.AsString() for t in board.GetTracks())
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=soft - {net},
                         victims_out=victims)
        # whatever was laid crosses the victims.  Local first: take out
        # only the victims' pieces the new copper runs into (and what that
        # leaves floating), then join each victim's ends again round it; a
        # victim that cannot be joined goes back in the queue
        new = [t for t in board.GetTracks() if t.m_Uuid.AsString() not in before]
        for t in _in_the_way(board, new, victims, clmap):
            pcb.remove(board, t)
        for v in victims:
            _drop_floating(board, v)
            SOFT_WEIGHT[v] = SOFT_WEIGHT.get(v, 1.0) + grow
            if route_net(board, v, track_w=(widths or {}).get(v, SIG_W), clmap=clmap, lock=False) and v not in queue:
                queue.append(v)
        if left:
            stuck[net] = stuck.get(net, 0) + 1
            pads = [p for c in _net_components(board, net) for p in _pads_in(board, net, c)][:6]
            log('   %s: %d pieces left (through %s); pads %s' % (net, left + 1, sorted(victims), pads))
            dump = os.environ.get('NEG_DUMP')
            if dump and not victims and stuck[net] == 1:
                board.Save(os.path.join(dump, 'stuck_%s.kicad_pcb' % net.replace('+', 'P')))
            if stuck[net] < 3 and net not in queue:
                queue.append(net)
            continue
        log('   %s: routed through %s  [queue %d]' % (net, sorted(victims), len(queue)))
        dump = os.environ.get('NEG_DUMP')
        if dump and rounds % 25 == 0:
            board.Save(os.path.join(dump, 'checkpoint.kicad_pcb'))
    return sorted(n for n in set(nets) | set(SOFT_WEIGHT) if len(_net_components(board, n)) > 1)


def _astar_py(g, layers, src, dst, tc, rip_cost, max_expand):
    H, W = g.H, g.W
    INF = 1 << 60
    cost = {}
    pq = []
    for li in range(len(layers)):
        for (j, i) in np.argwhere(src[li]):
            k = (li, i, j); cost[k] = 0
            heapq.heappush(pq, (0, 0, k, None, None))
    came = {}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    vcost = 40; bend = 3
    found = None; n = 0
    while pq and n < max_expand:
        f, c, k, prev, pdir = heapq.heappop(pq)
        if k in came:
            continue
        came[k] = (prev, pdir)
        li, i, j = k
        n += 1
        if dst[li][j, i]:
            found = k; break
        blk = g.block[layers[li]]; sb = g.sblock[layers[li]]
        for d in dirs:
            ni, nj = i + d[0], j + d[1]
            if not (0 <= ni < W and 0 <= nj < H):
                continue
            nk = (li, ni, nj)
            if nk in came:
                continue
            free_end = src[li][nj, ni] or dst[li][nj, ni]
            if blk[nj, ni] and not free_end:
                continue
            step = 1.414 if d[0] and d[1] else 1.0
            nc = c + step + (bend if pdir is not None and pdir != d else 0)
            if sb[nj, ni] and not free_end:
                wgt = g.sweight[layers[li]][nj, ni]
                nc += rip_cost * wgt if not sb[j, i] else step * 2 * wgt
            if nc < cost.get(nk, INF):
                cost[nk] = nc
                h = math.hypot(ni - tc[1], nj - tc[0]) * 0.9
                heapq.heappush(pq, (nc + h, nc, nk, k, d))
        # via (through all layers) to any other routing layer
        if not g.vblock[j, i]:
            for lj in range(len(layers)):
                if lj == li:
                    continue
                ok_other = (not g.block[layers[lj]][j, i]) or src[lj][j, i] or dst[lj][j, i]
                if not ok_other:
                    continue
                nk = (lj, i, j)
                if nk in came:
                    continue
                nc = c + vcost + (rip_cost * g.vweight[j, i] if g.vsoft[j, i] else 0)
                if nc < cost.get(nk, INF):
                    cost[nk] = nc
                    h = math.hypot(i - tc[1], j - tc[0]) * 0.9
                    heapq.heappush(pq, (nc + h, nc, nk, k, 'via'))
    if not found:
        return []
    # walk back
    path = []
    k = found
    while k is not None:
        path.append(k)
        k = came[k][0]
    path.reverse()
    return path


def _load_c():
    """Compile astar.c once per source hash (gcc is in the KiCad image)."""
    import ctypes, hashlib, os, subprocess, tempfile
    here = os.path.dirname(os.path.abspath(__file__))
    c = os.path.join(here, 'astar.c')
    try:
        h = hashlib.sha1(open(c, 'rb').read()).hexdigest()[:12]
        so = os.path.join(tempfile.gettempdir(), 'og_astar_%s.so' % h)
        if not os.path.exists(so):
            tmp = so + '.%d' % os.getpid()
            subprocess.run(['gcc', '-O3', '-march=native', '-shared', '-fPIC', '-o', tmp, c, '-lm'], check=True)
            os.replace(tmp, so)
        lib = ctypes.CDLL(so)
    except Exception as e:                      # no compiler: the Python search
        print('finish: C search unavailable (%s), using Python' % e)
        return None
    P = ctypes.c_void_p
    lib.astar.restype = ctypes.c_long
    lib.astar.argtypes = [ctypes.c_int] * 3 + [P] * 8 + [ctypes.c_float] * 5 + [ctypes.c_long, P, ctypes.c_long]
    return lib

_C = _load_c() if os.environ.get('OG_PY_ASTAR') != '1' else None


def _astar_c(g, layers, src, dst, tc, rip_cost, max_expand):
    """The search in C (astar.c).  Returns [(layer index, i, j)], [] if no
    path, None on a C-side failure (the caller falls back to Python)."""
    import ctypes
    L, H, W = len(layers), g.H, g.W
    u8 = lambda a: np.ascontiguousarray(a, dtype=np.uint8)
    f4 = lambda a: np.ascontiguousarray(a, dtype=np.float32)
    block = u8(np.stack([g.block[l] for l in layers]))
    sblock = u8(np.stack([g.sblock[l] for l in layers]))
    sweight = f4(np.stack([g.sweight[l] for l in layers]))
    vblock, vsoft, vweight = u8(g.vblock), u8(g.vsoft), f4(g.vweight)
    srcs, dsts = u8(np.stack([src[li] for li in range(L)])), u8(np.stack([dst[li] for li in range(L)]))
    cap = 4 * (H + W) * L + 100000
    out = np.zeros(cap, dtype=np.int32)
    ptr = lambda a: a.ctypes.data_as(ctypes.c_void_p)
    n = _C.astar(L, H, W, ptr(block), ptr(sblock), ptr(sweight), ptr(vblock), ptr(vsoft), ptr(vweight),
                 ptr(srcs), ptr(dsts), float(rip_cost), 40.0, 3.0, float(tc[1]), float(tc[0]),
                 int(max_expand), ptr(out), cap)
    if n < 0:
        return None
    HW = H * W
    return [(int(k) // HW, int(k) % HW % W, int(k) % HW // W) for k in out[:n]]


def _pads_in(board, net, comp):
    """'REF.pin' of the pads of `net` inside one copper piece."""
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net:
                continue
            g = _geom_of(p)
            if any(l in comp and any(a.intersects(b) for a in gl for b in comp[l]) for l, gl in g.items()):
                out.append('%s.%s' % (fp.GetReference(), p.GetNumber()))
    return out


def pathfinder(board, todo, protect=(), widths=None, clmap=None, max_iters=40, grow=1.0,
               pres_growth=1.35, sweep=0, log=print):
    """Negotiated congestion (PathFinder, McMurchie & Ebeling): no net is
    torn up for another.  Each iteration re-routes every open net and every
    net that overlaps another, letting it cross the other signal nets'
    copper at a price; the copper it crosses stays where it is, both nets
    are marked as overlapping and come round again in the next iteration.
    The price of crossing a net grows with each iteration it spends in an
    overlap (history, SOFT_WEIGHT), and every crossing grows dearer from
    one iteration to the next (pressure, RIP_COST), so the nets spread into
    whatever room the board has until none overlaps.  Returns (nets still
    open, nets still overlapping); when both are empty the copper is legal."""
    global RIP_COST
    base = RIP_COST
    protect = set(protect)
    allnets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    soft = allnets - protect
    over = {}
    reroute = set(todo)
    best = None
    try:
        for it in range(max_iters):
            if not reroute:
                break
            RIP_COST = base * pres_growth ** it
            order = sorted(reroute, key=lambda n: mst_length(board, n))
            for net in order:
                if net not in protect:
                    rip_up(board, net)
                for v in over.pop(net, set()):
                    over.get(v, set()).discard(net)
                victims = set()
                route_net(board, net, track_w=(widths or {}).get(net, SIG_W), clmap=clmap, lock=False,
                          soft_nets=soft - {net}, victims_out=victims)
                for v in victims:
                    over.setdefault(net, set()).add(v)
                    over.setdefault(v, set()).add(net)
            involved = {n for n, s in over.items() if s}
            for n in involved:
                SOFT_WEIGHT[n] = SOFT_WEIGHT.get(n, 1.0) + grow
            opened = [n for n in unrouted_nets(board) if n not in protect]
            pairs = sum(len(s) for s in over.values()) // 2
            log('  pathfinder %2d: %d overlapping pairs over %d nets, %d open %s'
                % (it, pairs, len(involved), len(opened), opened[:8]))
            dump = os.environ.get('NEG_DUMP')
            if dump:
                board.Save(os.path.join(dump, 'pf_%02d.kicad_pcb' % it))
                score = pairs + 3 * len(opened)
                if best is None or score < best:
                    best = score
                    board.Save(os.path.join(dump, 'pf_best.kicad_pcb'))
            reroute = involved | set(opened)
            if sweep and (it + 1) % sweep == 0 and reroute:
                # every `sweep` iterations every signal net goes round: legal
                # nets sitting in a contested lane move aside too
                reroute = set(n for n in soft if any(t.GetNetname() == n and not t.IsLocked()
                                                     for t in board.GetTracks())) | reroute
    finally:
        RIP_COST = base
    return [n for n in unrouted_nets(board) if n not in protect], sorted(n for n, s in over.items() if s)


def reorder_search(board, nets, protect=(), widths=None, clmap=None, tries=24, grow_rounds=6, seed=1,
                   pair_tries=4, log=print):
    """Route a small set of open nets with no crossing at all.
    Each round: a net that cannot be routed even alone has the nets it
    would cross torn up (they join the set); the nets that can be routed
    alone are tried in many orders (the order decides who gets the narrow
    lanes) and the best order's copper is kept.  Returns the nets still
    open."""
    import random
    global PAIR_TRIES
    rnd = random.Random(seed)
    protect = set(protect)
    allnets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    soft = allnets - protect
    w = lambda n: (widths or {}).get(n, SIG_W)
    is_open = lambda n: len(_net_components(board, n)) > 1
    snap = lambda: set(t.m_Uuid.AsString() for t in board.GetTracks())

    def rollback(before):
        for t in list(board.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(board, t)

    saved = PAIR_TRIES
    PAIR_TRIES = pair_tries
    try:
        todo = sorted(n for n in nets if is_open(n))
        for g in range(grow_rounds + 1):
            if not todo:
                return []
            # alone: who fits at all?
            alone, stuck = [], []
            for n in todo:
                before = snap()
                (stuck if route_net(board, n, track_w=w(n), clmap=clmap, lock=False) else alone).append(n)
                rollback(before)
            log('   reorder round %d: %d fit alone, stuck alone %s' % (g, len(alone), stuck))
            extra = set()
            for n in stuck:
                before = snap(); vic = set()
                route_net(board, n, track_w=w(n), clmap=clmap, lock=False, soft_nets=soft - {n}, victims_out=vic)
                rollback(before)
                extra |= vic - protect
            if extra:
                for v in extra:
                    rip_up(board, v)
                log('   reorder: tore up %s to make room' % sorted(extra))
                todo = sorted(set(todo) | extra)
                continue
            # orders of the nets that fit alone
            best = None
            orders = [sorted(alone, key=lambda n: mst_length(board, n))] + \
                     [rnd.sample(alone, len(alone)) for _ in range(tries - 1)]
            for order in orders:
                before = snap()
                fails = [n for n in order if route_net(board, n, track_w=w(n), clmap=clmap, lock=False)]
                if not fails and not stuck:
                    log('   reorder: all %d routed' % len(order))
                    return []
                if best is None or len(fails) < len(best[1]):
                    best = (order, fails)
                rollback(before)
                if not fails:
                    break
            order, fails = best
            for n in order:
                route_net(board, n, track_w=w(n), clmap=clmap, lock=False)
            todo = sorted(n for n in set(todo) if is_open(n))
            log('   reorder: best order leaves %s' % todo)
            if not todo:
                return []
            # the ones left behind: make room for them next round
            extra = set()
            for n in todo:
                before = snap(); vic = set()
                route_net(board, n, track_w=w(n), clmap=clmap, lock=False, soft_nets=soft - {n}, victims_out=vic)
                rollback(before)
                extra |= vic - protect
            for v in extra:
                rip_up(board, v)
            todo = sorted(set(todo) | extra)
        return [n for n in todo if is_open(n)]
    finally:
        PAIR_TRIES = saved


def cluster_endgame(board, nets, protect=(), widths=None, clmap=None, max_cluster=6, samples=150, log=print):
    """The last few open nets: each is grouped with the nets its cheapest
    crossing path runs through, and every order of the group's nets is
    tried with no crossing at all (a random sample for larger groups);
    the first order that routes the whole group is kept.  Returns the nets
    still open."""
    import itertools, random
    rnd = random.Random(1)
    protect = set(protect)
    allnets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    soft = allnets - protect
    w = lambda n: (widths or {}).get(n, SIG_W)
    snap = lambda: set(t.m_Uuid.AsString() for t in board.GetTracks())

    def rollback(before):
        for t in list(board.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(board, t)

    todo = [n for n in nets if len(_net_components(board, n)) > 1]
    groups = []
    for n in todo:
        before = snap(); vic = set()
        route_net(board, n, track_w=w(n), clmap=clmap, lock=False, soft_nets=soft - {n}, victims_out=vic)
        rollback(before)
        # (many-pin nets - the supplies - stay out of the orderings: each
        # try would re-route all of them; the short PathFinder runs move them)
        npads = {}
        for fp in board.GetFootprints():
            for p in fp.Pads():
                npads[p.GetNetname()] = npads.get(p.GetNetname(), 0) + 1
        vic = {v for v in vic if npads.get(v, 0) <= 8}
        g = ({n} | (vic - protect))
        # and the nets whose movable copper crowds this one's pads
        near = set()
        movable_tracks = [(t, t.GetBoundingBox()) for t in board.GetTracks()
                          if t.GetNetname() not in protect and t.GetNetname() != n and not t.IsLocked()]
        reach = pcbnew.FromMM(0.8)
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() != n:
                    continue
                pb = p.GetBoundingBox()
                pb.Inflate(reach)
                pg = None
                for t, tb in movable_tracks:
                    tn = t.GetNetname()
                    if tn in near or not pb.Intersects(tb):
                        continue
                    pg = pg or _geom_all(p)
                    tg = _geom_all(t)
                    if any(a.distance(c) < 0.8 for l in pg if l in tg for a in pg[l] for c in tg[l]):
                        near.add(tn)
        g |= set(sorted(x for x in near if npads.get(x, 0) <= 8)[:3])
        for other in [x for x in groups if x & g]:
            g |= other; groups.remove(other)
        groups.append(g)
    for g in groups:
        g = sorted(g)[:max_cluster] if len(g) > max_cluster else sorted(g)
        movable = [n for n in g if any(t.GetNetname() == n and not t.IsLocked() for t in board.GetTracks())
                   or len(_net_components(board, n)) > 1]
        saved = [t for t in board.GetTracks() if t.GetNetname() in movable and not t.IsLocked()]
        for n in movable:
            rip_up(board, n)
        orders = list(itertools.permutations(movable)) if len(movable) <= 5 else \
            [tuple(rnd.sample(movable, len(movable))) for _ in range(samples)]
        win = None
        global PAIR_TRIES
        saved_tries = PAIR_TRIES
        PAIR_TRIES = 4
        try:
            for order in orders:
                before = snap()
                ok = True
                for n in order:
                    if route_net(board, n, track_w=w(n), clmap=clmap, lock=False):
                        ok = False          # this order fails here: the next one
                        break
                if ok:
                    win = order
                    break
                rollback(before)
        finally:
            PAIR_TRIES = saved_tries
        if win is None:
            for t in saved:
                board.Add(t)
        log('   cluster %s: %s' % (movable, 'routed in order %s' % (win,) if win else 'no order works'))
    return [n for n in set(nets) | set(x for g in groups for x in g) if len(_net_components(board, n)) > 1]
