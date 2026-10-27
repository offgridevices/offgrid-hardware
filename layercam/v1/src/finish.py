# -*- coding: utf-8 -*-
"""Finish the connections Freerouting leaves unrouted.

Ported from SmokeBreak (smokebreak/v1/src/finish.py, dedangle.py): a grid
maze router with vias, then rip-up and re-route for what it cannot reach,
then the routers' dangling stubs taken off.  KiCad's DRC checks the result
afterwards (pipeline.py); this router is never trusted alone.

  router    0.05 mm cells on the signal layers (main board: F, In2, B; In1,
            In3 and In4 are planes).  Every other net's copper, inflated by
            the clearance plus half the track width, is an obstacle (cell
            centres tested exactly against the shapes); a via may go where
            a via fits, never in an SMD pad.  A* from one copper island of
            the net to another, bends and vias cost extra.  Each net at its
            class's width (board.POWER, DIFF, RF_W), never thinner.
  repair    an open net may run through other signal nets' unlocked copper
            at a price; those nets are torn up (locally first, whole if
            that fails) and routed again, kept only if nothing ends up
            worse (repair_tx), then random orders (repair_orders).  Locked
            copper (the coupled pairs, the antenna feed, the plane fan-out)
            and the plane nets are never touched or routed.
  planes    the plane nets join through their fills (In1 / In4 ground, In3
            0.9 V and 3.3 V).  Signal vias can wall a neck of a plane shut;
            vias in such a neck are taken out, the neck is barred to vias,
            and their nets routed again (plane_repair).
  dedangle  dangling unlocked tracks and vias are removed one at a time,
            each kept out only if no connection is lost (docs/lessons.md:
            "Dangling is not always a stub").

    python3 finish.py BOARD.kicad_pcb        finishes in place (main board)
"""
import heapq
import math
import os
import random
import sys
import time

import numpy as np
import pcbnew
import shapely
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcb
import board

RES = 0.05                     # mm per cell
FINE = 0.025                   # mm per cell for a last try in a small window
MARGIN = 0.012                 # mm on top of every clearance (cell-to-cell chords)
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
VIA_D, VIA_DRILL = 0.45, 0.2   # set from pcb.VIA by configure()
HOLE_TO_HOLE = 0.25            # the board's hole-to-hole minimum
PTH_CLEAR = 0.3                # track to a component hole (the rules ask 0.28)
VIA_COST, BEND = 30.0, 2.0
SOFT_STEP, SOFT_VIA = 8.0, 60.0  # per cell through another net's rippable copper; a via in it
TURN = (0.0, BEND, 3 * BEND, 15 * BEND, 1e9)      # 0, 45, 90, 135, 180 degrees
H_WEIGHT = 1.15                # A* heuristic weight (a little greedy)
BUDGET = 2_500_000             # cells expanded per search
WINDOW = 3.0                   # mm round the two islands for the first search
SOFT_IDS = None                # region_reroute: only these tracks and vias are soft
FORCE_RES = 0.025              # ... at this resolution
FORCE_WINDOW = None            # (x0, y0, x1, y1): every search in this window only (region_reroute)
NOVIA = []                     # shapely shapes (board mm) barred to new vias (plane necks)
EDGE_RULE = 'edge clearance'   # the edge band rule area: drawn from pcb.edge_band instead
VERBOSE = False
TIME_LIMIT = int(os.environ.get('FINISH_TIME', 3600))   # s for the rip-up stages
# runs side by side on one board differ by this: the open nets' order and
# the stages' order (0: as written below)
SEED = int(os.environ.get('FINISH_SEED', 0))
DEBUG_SAVE = None               # a path: region_reroute saves its last failed state there
# the main board's In3 carries the 3.3 V fill round the 0.9 V core plane: a
# connection with no way on F, In2 or B may hop through it.  Its 3.3 V fill
# re-pours round the track; the 0.9 V plane is never crossed.  Each cell
# there costs IN3_STEP more, so it is used only where nothing else goes.
IN3 = os.environ.get('FINISH_IN3', '1') != '0'
POUR_THROUGH = {pcbnew.In3_Cu: {'VCC_3V3'}}
IN3_STEP = 3.0
IN3_KEEP = 0.2                  # mm more between a track and the 0.9 V plane's outline


def configure():
    global VIA_D, VIA_DRILL, ROUTE_LAYERS
    VIA_D, VIA_DRILL = pcb.VIA
    ROUTE_LAYERS = ([pcbnew.F_Cu, pcbnew.In2_Cu] + ([pcbnew.In3_Cu] if IN3 else []) + [pcbnew.B_Cu]
                    if pcb.LAYERS == 6 else [pcbnew.F_Cu, pcbnew.B_Cu])


# ---------------------------------------------------------------- net rules
def rules():
    """(widths, protect, planes): each net's track width (its class: never
    thinner), the nets never torn up or routed (planes, pairs, RF), and the
    plane nets."""
    bd = pcb.BOARD
    widths = dict(board.POWER.get(bd, {}))
    protect = set(board.PLANE_NETS.get(bd, ()))
    for nets, w, gap in board.DIFF.get(bd, {}).values():
        protect |= set(nets)
        for n in nets:
            widths[n] = w
    if bd == 'main':
        for n in ('ANT_FEED', 'ANT'):
            widths[n] = board.RF_W
            protect.add(n)
    return widths, protect, set(board.PLANE_NETS.get(bd, ()))


def width_of(widths, net):
    return widths.get(net, pcb.TRACK)


# ---------------------------------------------------------------- geometry
_PADG = {}


def _pad_geom(pad, layer):
    k = (pad.m_Uuid.AsString(), layer)
    g = _PADG.get(k)
    if g is None:
        ps = pcbnew.SHAPE_POLY_SET()
        pad.TransformShapeToPolygon(ps, layer, 0, 1000, pcbnew.ERROR_OUTSIDE)
        polys = []
        for i in range(ps.OutlineCount()):
            ol = ps.Outline(i)
            pts = [pcb.xy(ol.CPoint(q)) for q in range(ol.PointCount())]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
        g = unary_union(polys) if polys else Polygon()
        _PADG[k] = g
    return g


def _via_r(v):
    return v.GetWidth(pcbnew.F_Cu) / 2e6


def _track_line(t):
    return LineString([pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())])


def _geom_of(item, layers=None):
    """{layer: [shapely geometry]} for a pad, track or via (route layers)."""
    layers = ROUTE_LAYERS if layers is None else layers
    out = {}
    cls = item.GetClass()
    if cls == 'PAD':
        for l in layers:
            if item.IsOnLayer(l):
                g = _pad_geom(item, l)
                if not g.is_empty:
                    out[l] = [g]
    elif cls == 'PCB_VIA':
        g = Point(pcb.xy(item.GetPosition())).buffer(_via_r(item), 12)
        out = {l: [g] for l in layers}
    elif cls in ('PCB_TRACK', 'PCB_ARC'):
        if item.GetLayer() in layers:
            out[item.GetLayer()] = [_track_line(item).buffer(item.GetWidth() / 2e6, 8)]
    return out


def _uid(item):
    return item.m_Uuid.AsString()


# ---------------------------------------------------------------- the grid
class Grid:
    """Obstacle masks over a window (x0, y0, x1, y1) in board mm: block[l]
    (a track centre may not enter), vblock (a via centre may not), and the
    rippable copper of `soft_nets` as sblock / vsoft."""

    def __init__(self, b, net, tw, window, soft_nets=(), clear=None, res=None):
        self.res = res or RES
        self.b, self.net, self.tw = b, net, tw
        self.cl = pcb.CLEAR if clear is None else clear
        x0, y0, x1, y1 = window
        x0 = math.floor(x0 / self.res) * self.res
        y0 = math.floor(y0 / self.res) * self.res
        self.x0, self.y0 = x0, y0
        self.W = int(math.ceil((x1 - x0) / self.res)) + 1
        self.H = int(math.ceil((y1 - y0) / self.res)) + 1
        self.window = (x0, y0, x0 + (self.W - 1) * self.res, y0 + (self.H - 1) * self.res)
        self.soft_nets = set(soft_nets)
        self.layers = list(ROUTE_LAYERS)
        self._build()

    def xy(self, i, j):
        return (self.x0 + i * self.res, self.y0 + j * self.res)

    def mask(self):
        return np.zeros((self.H, self.W), bool)

    def fill(self, m, g, inside=False):
        """Set the cells whose centres lie in g (on its edge too, unless
        inside)."""
        if g.is_empty:
            return
        a, c, e, f = g.bounds
        i0 = max(0, int(math.ceil((a - self.x0) / self.res - 1e-9)))
        i1 = min(self.W - 1, int(math.floor((e - self.x0) / self.res + 1e-9)))
        j0 = max(0, int(math.ceil((c - self.y0) / self.res - 1e-9)))
        j1 = min(self.H - 1, int(math.floor((f - self.y0) / self.res + 1e-9)))
        if i1 < i0 or j1 < j0:
            return
        X, Y = np.meshgrid(self.x0 + np.arange(i0, i1 + 1) * self.res, self.y0 + np.arange(j0, j1 + 1) * self.res)
        hit = shapely.contains_xy(g, X, Y) if inside else shapely.intersects_xy(g, X, Y)
        m[j0:j1 + 1, i0:i1 + 1] |= hit

    def near(self, bb, pad=1.5):
        x0, y0, x1, y1 = self.window
        return not (bb[2] < x0 - pad or bb[0] > x1 + pad or bb[3] < y0 - pad or bb[1] > y1 + pad)

    def _build(self):
        b, net, tw, cl = self.b, self.net, self.tw, self.cl
        vd = VIA_D
        M = MARGIN
        L = self.layers
        self.block = {l: self.mask() for l in L}
        self.sblock = {l: self.mask() for l in L}
        vb = self.mask()
        vs = self.mask()
        self.soft = {l: [] for l in L}         # (geometry, net)
        ti, vi = cl + tw / 2 + M, cl + vd / 2 + M
        wx0, wy0, wx1, wy1 = self.window
        for fp in b.GetFootprints():
            bb = fp.GetBoundingBox()
            if not self.near((*pcb.xy(bb.GetOrigin()), *pcb.xy(bb.GetEnd()))):
                continue
            for pad in fp.Pads():
                mine = pad.GetNetname() == net and net
                smd = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN)
                for l in L:
                    if not pad.IsOnLayer(l):
                        continue
                    g = _pad_geom(pad, l)
                    if g.is_empty or not self.near(g.bounds):
                        continue
                    if not mine:
                        self.fill(self.block[l], g.buffer(ti, 6))
                        self.fill(vb, g.buffer(vi, 6))
                    elif smd:
                        # no via in a pad (it would need filling and capping)
                        self.fill(vb, g.buffer(vd / 2 + 0.03, 6))
                if pad.GetDrillSize().x > 0:
                    p = Point(pcb.xy(pad.GetPosition()))
                    r = max(pad.GetDrillSize().x, pad.GetDrillSize().y) / 2e6
                    if not self.near(p.buffer(r).bounds):
                        continue
                    if not mine:
                        for l in L:
                            self.fill(self.block[l], p.buffer(r + PTH_CLEAR + tw / 2 + M, 8))
                    self.fill(vb, p.buffer(r + HOLE_TO_HOLE + VIA_DRILL / 2 + M, 8))
        for t in b.GetTracks():
            tn = t.GetNetname()
            soft = tn in self.soft_nets and tn != net and not t.IsLocked() and \
                (SOFT_IDS is None or _uid(t) in SOFT_IDS)
            if t.GetClass() == 'PCB_VIA':
                p = pcb.xy(t.GetPosition())
                r = _via_r(t)
                if not self.near((p[0] - r, p[1] - r, p[0] + r, p[1] + r)):
                    continue
                g = Point(p).buffer(r, 12)
                if tn == net and net:
                    self.fill(vb, Point(p).buffer(t.GetDrillValue() / 2e6 + HOLE_TO_HOLE + VIA_DRILL / 2 + M, 8))
                    continue
                if soft:
                    for l in L:
                        self.soft[l].append((g, tn))
                        self.fill(self.sblock[l], g.buffer(ti, 6))
                    self.fill(vs, g.buffer(vi, 6))
                    # a hole stays a hole: hole-to-hole even through soft copper
                    self.fill(vb, Point(p).buffer(t.GetDrillValue() / 2e6 + HOLE_TO_HOLE + VIA_DRILL / 2, 8))
                else:
                    for l in L:
                        self.fill(self.block[l], g.buffer(ti, 6))
                    self.fill(vb, g.buffer(vi, 6))
            elif t.GetLayer() in L:
                if tn == net and net:
                    continue
                ln = _track_line(t)
                if not self.near(ln.bounds):
                    continue
                w = t.GetWidth() / 2e6
                if soft:
                    g = ln.buffer(w, 6)
                    self.soft[t.GetLayer()].append((g, tn))
                    self.fill(self.sblock[t.GetLayer()], ln.buffer(w + ti, 6))
                    self.fill(vs, ln.buffer(w + vi, 6))
                else:
                    self.fill(self.block[t.GetLayer()], ln.buffer(w + ti, 6))
                    self.fill(vb, ln.buffer(w + vi, 6))
        for z in b.Zones():
            zl = [l for l in L if z.GetLayerSet().Contains(l)]
            if not zl:
                continue
            if z.GetIsRuleArea():
                if z.GetZoneName() == EDGE_RULE:
                    continue
                g = _poly_set(z.Outline())
                if z.GetDoNotAllowTracks():
                    for l in zl:
                        self.fill(self.block[l], g.buffer(tw / 2 + M, 6))
                if z.GetDoNotAllowVias():
                    self.fill(vb, g.buffer(vd / 2 + M, 6))
                continue
            zn = z.GetNetname()
            for l in zl:
                if l in POUR_THROUGH and zn not in POUR_THROUGH[l] and zn != net:
                    # a plane the hop must go round: its outline, filled or not
                    self.fill(self.block[l], _poly_set(z.Outline()).buffer(ti + IN3_KEEP, 6))
            if not z.IsFilled():
                continue
            for l in zl:
                if zn in POUR_THROUGH.get(l, ()):
                    continue
                g = _poly_set(z.GetFilledPolysList(l))
                if g.is_empty or (z.GetNetname() == net and net):
                    continue
                self.fill(self.block[l], g.buffer(ti, 6))
                self.fill(vb, g.buffer(vi, 6))
        # the board edge and its cut-outs, the fab's band inside them
        for m, r in [(self.block[l], tw / 2) for l in L] + [(vb, vd / 2)]:
            m |= ~self._inside(r)
        for g in NOVIA:
            self.fill(vb, g)
        self.vblock = vb
        self.vsoft = vs

    _INSIDE = {}

    def _inside(self, r):
        k = (self.window, self.W, self.H, self.res, round(r, 4), pcb.BOARD)
        m = Grid._INSIDE.get(k)
        if m is None:
            allowed = pcb.board_polygon().buffer(-(pcb.EDGE_BAND + r + MARGIN))
            m = self.mask()
            self.fill(m, allowed, inside=True)
            Grid._INSIDE[k] = m
        return m


def _poly_set(ps):
    polys = []
    for k in range(ps.OutlineCount()):
        ol = ps.Outline(k)
        ext = [pcb.xy(ol.CPoint(q)) for q in range(ol.PointCount())]
        holes = []
        for h in range(ps.HoleCount(k)):
            hh = ps.Hole(k, h)
            holes.append([pcb.xy(hh.CPoint(q)) for q in range(hh.PointCount())])
        if len(ext) >= 3:
            polys.append(Polygon(ext, [h for h in holes if len(h) >= 3]).buffer(0))
    return unary_union(polys) if polys else Polygon()


# ---------------------------------------------------------------- A*
_MOVES = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def _astar(G, src, dst, budget, ex=None, vex=None, free=None):
    """ex: per layer, extra cost of entering each cell (soft copper,
    congestion history); vex: extra cost of a via at each cell."""
    L = len(G.layers)
    W, H = G.W, G.H
    N = W * H
    if free is None:
        free = [~G.block[l] | src[k] | dst[k] for k, l in enumerate(G.layers)]
    pas = [f.ravel().tobytes() for f in free]
    dstb = [dst[k].ravel().tobytes() for k in range(L)]
    vok = (~G.vblock).ravel().tobytes()
    exl = [e.ravel().tolist() for e in ex] if ex is not None else None
    vx = vex.ravel().tolist() if vex is not None else None
    anyd = np.logical_or.reduce(dst)
    if not anyd.any():
        return None, 0
    h = (ndimage.distance_transform_edt(~anyd) * H_WEIGHT).ravel().tolist()
    moves = [(k, di, dj, di + dj * W, 1.4142 if di and dj else 1.0) for k, (di, dj) in enumerate(_MOVES)]
    lx = [IN3_STEP if l == pcbnew.In3_Cu else 0.0 for l in G.layers]
    INF = float('inf')
    g = {}
    closed = bytearray(L * N)
    came = {}
    pq = []
    for k in range(L):
        for p in np.flatnonzero(src[k].ravel()).tolist():
            s = k * N + p
            g[s] = 0.0
            pq.append((h[p], 0.0, s, -1, 8))
    heapq.heapify(pq)
    push, pop = heapq.heappush, heapq.heappop
    n = 0
    found = None
    while pq and n < budget:
        f, c, s, prev, d = pop(pq)
        if closed[s]:
            continue
        closed[s] = 1
        came[s] = prev
        n += 1
        li, p = divmod(s, N)
        if dstb[li][p]:
            found = s
            break
        i = p % W
        j = p // W
        P = pas[li]
        E = exl[li] if exl is not None else None
        base = li * N
        for k, di, dj, dp, step in moves:
            ni = i + di
            nj = j + dj
            if ni < 0 or ni >= W or nj < 0 or nj >= H:
                continue
            q = p + dp
            if not P[q] or closed[base + q]:
                continue
            if di and dj and not (P[p + di] or P[p + dj * W]):
                continue                       # no squeezing between two blocked cells
            nc = c + step * (1.0 + lx[li])
            if d < 8:
                t = k - d if k >= d else d - k
                nc += TURN[t if t <= 4 else 8 - t]
            if E is not None:
                nc += E[q] * step
            ns = base + q
            if nc < g.get(ns, INF):
                g[ns] = nc
                push(pq, (nc + h[q], nc, ns, s, k))
        if vok[p]:
            for lj in range(L):
                if lj == li or not pas[lj][p]:
                    continue
                ns = lj * N + p
                if closed[ns]:
                    continue
                nc = c + VIA_COST + (vx[p] if vx is not None else 0)
                if nc < g.get(ns, INF):
                    g[ns] = nc
                    push(pq, (nc + h[p], nc, ns, s, 8))
    if found is None:
        return None, n
    path = []
    s = found
    while s != -1:
        li, p = divmod(s, N)
        path.append((li, p % W, p // W))
        s = came[s]
    path.reverse()
    return path, n


def _mask_of(G, items, inset=0.0):
    """Per layer, the cells inside the island's copper (shrunk by inset)."""
    out = []
    for l in G.layers:
        m = G.mask()
        for g in items.get(l, []):
            if G.near(g.bounds, 0):
                G.fill(m, g.buffer(-inset, 6) if inset else g, inside=True)
        out.append(m)
    return out


def _bounds(items):
    bs = [g.bounds for gl in items.values() for g in gl]
    return (min(x[0] for x in bs), min(x[1] for x in bs), max(x[2] for x in bs), max(x[3] for x in bs))


class History:
    """PathFinder's congestion history over the whole board: extra cost per
    cell and layer where nets have fought over copper, and the present
    price of crossing another net's copper (pres)."""

    def __init__(self, layers, res=None):
        self.res = res or RES
        x0, y0, x1, y1 = pcb.board_polygon().bounds
        self.x0, self.y0 = math.floor(x0 / self.res) * self.res, math.floor(y0 / self.res) * self.res
        self.W = int(math.ceil((x1 - self.x0) / self.res)) + 2
        self.H = int(math.ceil((y1 - self.y0) / self.res)) + 2
        self.h = [np.zeros((self.H, self.W), np.float32) for _ in layers]
        self.pres = 1.0

    def window(self, G):
        i0 = int(round((G.x0 - self.x0) / self.res))
        j0 = int(round((G.y0 - self.y0) / self.res))
        out = []
        for a in self.h:
            m = np.zeros((G.H, G.W), np.float32)
            si, sj = max(0, -i0), max(0, -j0)
            ei, ej = min(G.W, self.W - i0), min(G.H, self.H - j0)
            if ei > si and ej > sj:
                m[sj:ej, si:ei] = a[j0 + sj:j0 + ej, i0 + si:i0 + ei]
            out.append(m)
        return out

    def add(self, G, cells, inc):
        i0 = int(round((G.x0 - self.x0) / self.res))
        j0 = int(round((G.y0 - self.y0) / self.res))
        for li, i, j in cells:
            I, J = i + i0, j + j0
            if 0 <= I < self.W and 0 <= J < self.H:
                self.h[li][max(0, J - 2):J + 3, max(0, I - 2):I + 3] += inc


def route_connection(b, net, a_items, b_items, track_w, soft_nets=None, victims_out=None, window=WINDOW,
                     hist=None):
    """Route from copper island A to island B of `net` ({layer: [geometry]}).
    Returns the new tracks and vias, or None."""
    full = pcb.board_polygon().bounds
    tries = [full]
    fine = []
    if window is not None:
        # first a window round the gap between the islands (their nearest
        # points), then round both islands, then the whole board
        from shapely.ops import nearest_points
        ua = unary_union([g for gs in a_items.values() for g in gs])
        ub = unary_union([g for gs in b_items.values() for g in gs])
        pa, pb = nearest_points(ua, ub)
        ba, bb = _bounds(a_items), _bounds(b_items)
        boxes = [(min(pa.x, pb.x), min(pa.y, pb.y), max(pa.x, pb.x), max(pa.y, pb.y), window + 1.0),
                 (min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3]), window)]
        area = (full[2] - full[0]) * (full[3] - full[1])
        tries = []
        for x0, y0, x1, y1, m in boxes:
            w = (max(full[0], x0 - m), max(full[1], y0 - m), min(full[2], x1 + m), min(full[3], y1 + m))
            if (w[2] - w[0]) * (w[3] - w[1]) < 0.7 * area and w not in tries:
                tries.append(w)
        if tries and FINE:
            # a finer grid finds the gaps the coarse one rounds shut
            fine = [(tries[0], FINE)]
        tries.append(full)
    if FORCE_WINDOW is not None:
        tries, fine = [], [(FORCE_WINDOW, FORCE_RES)]
    for win, res in [(w, RES) for w in tries] + fine:
        t0 = time.time()
        G = Grid(b, net, track_w, win, soft_nets=soft_nets or (), res=res)
        # a track may start or end in its island's copper, but only where it
        # keeps clear of other copper, or lies wholly inside the island's
        free = [~G.block[l] | a | c for l, a, c in zip(G.layers, _mask_of(G, a_items, track_w / 2 + MARGIN),
                                                         _mask_of(G, b_items, track_w / 2 + MARGIN))]
        src = [m & f for m, f in zip(_mask_of(G, a_items), free)]
        dst = [m & f for m, f in zip(_mask_of(G, b_items), free)]
        if not any(m.any() for m in src) or not any(m.any() for m in dst):
            continue
        t1 = time.time()
        ex = vex = None
        pres = hist.pres if hist is not None else 1.0
        if soft_nets or hist is not None:
            ex = [G.sblock[l].astype(np.float32) * (SOFT_STEP * pres) for l in G.layers]
            vex = G.vsoft.astype(np.float32) * (SOFT_VIA * pres)
            if hist is not None and G.res == hist.res:
                hw = hist.window(G)
                for k in range(len(ex)):
                    ex[k] += hw[k]
                vex += np.maximum.reduce(hw) * 4
        path, n = _astar(G, src, dst, BUDGET, ex, vex, free)
        if VERBOSE:
            print('      grid %dx%d %.1fs, search %d cells %.1fs %s' % (G.W, G.H, t1 - t0, n, time.time() - t1,
                                                                         'found' if path else 'none'), flush=True)
        if path:
            if hist is not None and G.res == hist.res:
                hot = [(li, i, j) for li, i, j in path if G.sblock[G.layers[li]][j, i] or G.vsoft[j, i]]
                hist.hot = getattr(hist, 'hot', []) + [(G, hot)]
            return _emit(b, G, net, path, track_w, victims_out)
    return None


def _emit(b, G, net, path, tw, victims_out):
    layers = G.layers
    if victims_out is not None:
        for (li, i, j) in path:
            l = layers[li]
            if G.sblock[l][j, i] or G.vsoft[j, i]:
                pt = Point(G.xy(i, j))
                for geom, n in G.soft[l]:
                    if n not in victims_out and geom.distance(pt) < G.cl + max(tw / 2, VIA_D / 2) + 0.07:
                        victims_out.add(n)
    netinfo = b.FindNet(net)
    new = []

    def flush(run):
        if len(run) < 2:
            return
        pts = [run[0]]
        for a, c, e in zip(run, run[1:], run[2:]):
            if (c[1] - a[1], c[2] - a[2]) != (e[1] - c[1], e[2] - c[2]):
                pts.append(c)
        pts.append(run[-1])
        l = layers[run[0][0]]
        for p, q in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcb.P(*G.xy(p[1], p[2])))
            t.SetEnd(pcb.P(*G.xy(q[1], q[2])))
            t.SetWidth(pcb.MM(tw))
            t.SetLayer(l)
            t.SetNet(netinfo)
            b.Add(t)
            new.append(t)

    run = [path[0]]
    for p in path[1:]:
        if p[0] != run[-1][0]:
            flush(run)
            if (p[1], p[2]) != (run[-1][1], run[-1][2]):
                raise RuntimeError('layer change off a cell')
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcb.P(*G.xy(p[1], p[2])))
            v.SetWidth(pcb.MM(VIA_D))
            v.SetDrill(pcb.MM(VIA_DRILL))
            v.SetNet(netinfo)
            b.Add(v)
            new.append(v)
            run = [p]
        else:
            run.append(p)
    flush(run)
    return new


# ---------------------------------------------------------------- islands
def net_items(b, net):
    out = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
    return out + [t for t in b.GetTracks() if t.GetNetname() == net]


def _net_components(b, net):
    """The net's copper in touching islands (pads, tracks, vias on the
    route layers; its fills join what they touch).  [{layer: [geoms]}]"""
    items = [_geom_of(it) for it in net_items(b, net)]
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsFilled():
            continue
        for l in ROUTE_LAYERS:
            if z.GetLayerSet().Contains(l):
                g = _poly_set(z.GetFilledPolysList(l))
                for gg in getattr(g, 'geoms', [g]):
                    if not gg.is_empty:
                        items.append({l: [gg]})
    items = [it for it in items if it]
    n = len(items)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for l in ROUTE_LAYERS:
        geoms, owner = [], []
        for k, it in enumerate(items):
            for g in it.get(l, []):
                geoms.append(g)
                owner.append(k)
        if len(geoms) < 2:
            continue
        tree = STRtree(geoms)
        a, c = tree.query(geoms, predicate='intersects')
        for x, y in zip(a.tolist(), c.tolist()):
            if owner[x] != owner[y]:
                ra, rb = find(owner[x]), find(owner[y])
                if ra != rb:
                    parent[ra] = rb
    comps = {}
    for k in range(n):
        c = comps.setdefault(find(k), {})
        for l, gs in items[k].items():
            c.setdefault(l, []).extend(gs)
    return list(comps.values())


def _dist(a, b):
    d = 1e9
    for l in a:
        if l in b:
            d = min(d, unary_union(a[l]).distance(unary_union(b[l])))
    if d == 1e9:
        d = unary_union([g for gs in a.values() for g in gs]).distance(
            unary_union([g for gs in b.values() for g in gs]))
    return d


def _touch(a, b):
    return any(x.intersects(y) for l in a if l in b for x in a[l] for y in b[l])


def signal_nets(b, skip=()):
    nets = set(p.GetNetname() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname())
    return sorted(nets - set(skip))


def unrouted_nets(b, skip=()):
    """Nets (not in skip) whose copper is still in more than one piece."""
    return [n for n in signal_nets(b, skip) if len(_net_components(b, n)) > 1]


def mst_length(b, net):
    pts = [pcb.xy(p.GetPosition()) for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
    if len(pts) < 2:
        return 0.0
    used, rest, tot = [pts[0]], pts[1:], 0.0
    while rest:
        d, k = min((min(math.hypot(a[0] - c[0], a[1] - c[1]) for a in used), i) for i, c in enumerate(rest))
        tot += d
        used.append(rest.pop(k))
    return tot


def route_net(b, net, track_w, soft_nets=None, victims_out=None, partners=3, hist=None):
    """Join every island of `net`, the nearest pair first (an island walled
    in from its nearest neighbour tries the next ones).  Returns the
    number of islands left over."""
    for _ in range(40):
        comps = _net_components(b, net)
        if len(comps) <= 1:
            return 0
        pairs = sorted((_dist(comps[i], comps[j]), i, j) for i in range(len(comps)) for j in range(i + 1, len(comps)))
        done = False
        tried = 0
        for d, i, j in pairs:
            if tried >= partners:
                break
            tried += 1
            if route_connection(b, net, comps[i], comps[j], track_w, soft_nets=soft_nets, victims_out=victims_out,
                                hist=hist):
                done = True
                break
        if not done:
            return len(comps) - 1
    return len(_net_components(b, net)) - 1


# ---------------------------------------------------------------- rip-up and repair
def rip_up(b, net, removed=None):
    n = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() == net and not t.IsLocked():
            if removed is not None:
                removed.append(t)
            pcb.remove(b, t)
            n += 1
    return n


def _snapshot(b):
    return set(_uid(t) for t in b.GetTracks())


def _rollback(b, before, removed):
    for t in list(b.GetTracks()):
        if _uid(t) not in before:
            pcb.remove(b, t)
    have = _snapshot(b)
    for t in removed:
        if _uid(t) in before and _uid(t) not in have:
            b.Add(t)
            have.add(_uid(t))


def _geom_all(item):
    """_geom_of, with a via on every copper layer (it is drilled through)."""
    if item.GetClass() == 'PCB_VIA':
        g = Point(pcb.xy(item.GetPosition())).buffer(_via_r(item), 12)
        return {l: [g] for l in pcb.cu_layers()}
    return _geom_of(item)


def _in_the_way(b, new, nets):
    """Unlocked tracks and vias of `nets` that break clearance to `new`."""
    mine = {}
    for t in new:
        for l, gs in _geom_all(t).items():
            mine.setdefault(l, []).extend(gs)
    trees = {l: STRtree(gs) for l, gs in mine.items()}
    out = []
    for t in b.GetTracks():
        if t.GetNetname() not in nets or t.IsLocked():
            continue
        for l, gs in _geom_all(t).items():
            if l in trees and any(len(trees[l].query(g, predicate='dwithin', distance=pcb.CLEAR - 1e-4)) for g in gs):
                out.append(t)
                break
    return out


def _drop_floating(b, net):
    """Remove the net's unlocked track pieces that no longer reach a pad.
    Returns what was removed."""
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
    tracks = [t for t in b.GetTracks() if t.GetNetname() == net]
    items = [(None, _geom_all(p)) for p in pads] + [(t, _geom_all(t)) for t in tracks]
    n = len(items)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            gi, gj = items[i][1], items[j][1]
            if any(x.intersects(y) for l in gi if l in gj for x in gi[l] for y in gj[l]):
                parent[find(i)] = find(j)
    roots = set(find(i) for i in range(len(pads)))
    out = []
    for i in range(len(pads), n):
        t = items[i][0]
        if find(i) not in roots and not t.IsLocked():
            out.append(t)
            pcb.remove(b, t)
    return out


def repair_tx(b, nets, protect, widths, max_rounds=80, max_victims=6, log=print):
    """Rip-up and re-route, one transaction at a time.  An open net may be
    routed through other (unprotected) nets' unlocked copper; first only
    the pieces its new path runs into are taken out and those nets joined
    again round it; if that fails they are torn up whole and routed after
    it.  Either attempt is kept only if the open net is joined and no torn
    net has more islands than before, else everything is put back.
    Locked copper is never touched.  Returns the nets still open."""
    protect = set(protect)

    def islands(n):
        return len(_net_components(b, n))
    queue = list(nets)
    tried = set()
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        w = width_of(widths, net)
        if route_net(b, net, w) == 0:
            log('   repair %-14s routed' % net)
            continue
        if net in tried:
            continue
        tried.add(net)
        before = _snapshot(b)
        removed = []
        soft = set(t.GetNetname() for t in b.GetTracks() if not t.IsLocked()) - protect - {net}
        victims = set()
        if route_net(b, net, w, soft_nets=soft, victims_out=victims) or not victims or len(victims) > max_victims:
            _rollback(b, before, removed)
            log('   repair %-14s no path (%d nets in the way)' % (net, len(victims)))
            continue
        score0 = {}
        _rollback(b, before, removed)               # islands before, measured without the new path
        score0 = {v: islands(v) for v in victims}
        route_net(b, net, w, soft_nets=soft, victims_out=set())
        new = [t for t in b.GetTracks() if _uid(t) not in before]
        for t in _in_the_way(b, new, victims):
            removed.append(t)
            pcb.remove(b, t)
        for v in victims:
            removed.extend(_drop_floating(b, v))
        ok = islands(net) == 1
        for v in sorted(victims):
            if not ok:
                break
            route_net(b, v, width_of(widths, v))
            if islands(v) > score0[v]:
                ok = False
        if ok:
            log('   repair %-14s routed, patched %s' % (net, sorted(victims)))
            continue
        _rollback(b, before, removed)
        before = _snapshot(b)
        removed = []
        rip_up(b, net, removed)
        for v in victims:
            rip_up(b, v, removed)
        ok = route_net(b, net, w) == 0
        for v in sorted(victims):
            if not ok:
                break
            route_net(b, v, width_of(widths, v))
            if islands(v) > score0[v]:
                ok = False
        if ok:
            log('   repair %-14s routed, re-routed %s' % (net, sorted(victims)))
        else:
            _rollback(b, before, removed)
            log('   repair %-14s rolled back (nets in the way %s)' % (net, sorted(victims)))
    return [n for n in nets if islands(n) > 1]


def repair_orders(b, nets, protect, widths, tries=24, max_victims=10, seed=1, passes=2, log=print):
    """Rip-up and re-route in random orders, one jam at a time: the open
    net and the nets in its way are torn up and routed again in up to
    `tries` seeded random orders; the first order in which the net joins
    and no torn-up net has more islands than before is kept.  Locked
    copper is never touched.  Returns the nets still open."""
    rnd = random.Random(seed)
    protect = set(protect)

    def islands(n):
        return len(_net_components(b, n))

    def attempt(net):
        if islands(net) <= 1:
            return True
        before = _snapshot(b)
        soft = set(t.GetNetname() for t in b.GetTracks() if not t.IsLocked()) - protect - {net}
        victims = set()
        route_net(b, net, width_of(widths, net), soft_nets=soft, victims_out=victims)
        _rollback(b, before, [])
        group = {net} | (victims - protect)
        if len(group) > max_victims + 1:
            log('   orders %-14s %d nets in the way, too many' % (net, len(group) - 1))
            return False
        base = {n: islands(n) for n in group}
        for k in range(tries):
            before = _snapshot(b)
            removed = []
            for n in group:
                rip_up(b, n, removed)
            order = sorted(group - {net})
            rnd.shuffle(order)
            order = [net] + order if k % 2 == 0 else order[:len(order) // 2] + [net] + order[len(order) // 2:]
            for n in order:
                route_net(b, n, width_of(widths, n))
            now = {n: islands(n) for n in group}
            if now[net] == 1 and all(now[n] <= base[n] for n in group):
                log('   orders %-14s routed on try %d, re-routed %s' % (net, k, sorted(group - {net})))
                return True
            _rollback(b, before, removed)
        log('   orders %-14s no order worked (%d tries, nets %s)' % (net, tries, sorted(group)))
        return False

    todo = list(nets)
    for _ in range(passes):
        todo = [n for n in todo if not attempt(n)]
        if not todo:
            break
    return [n for n in nets if islands(n) > 1]


HIST_INC = 4.0                 # congestion history added round a fought-over cell


def negotiate(b, net, protect, widths, budget=60, reach=0.0, log=print):
    """Rip-up and re-route with congestion history (after PathFinder): the
    open net may run through any unprotected net's unlocked copper; what it
    runs into is taken out, those nets go on the queue to be joined again
    the same way, and every fight raises the price of crossing and the
    history cost where it happened, so the nets spread out.  Kept only if
    the queue empties within `budget` routes, the net is joined and no
    net touched has more islands than before; else everything is put
    back.  Locked copper and protected nets are never touched."""
    protect = set(protect)

    def islands(n):
        return len(_net_components(b, n))
    if islands(net) <= 1:
        return True
    before = _snapshot(b)
    removed = []
    base = {net: islands(net)}
    H = History(ROUTE_LAYERS)
    queue = [net]
    steps = 0
    ok = False
    while steps < budget:
        if not queue:
            ok = all(islands(n) <= base[n] for n in base) and islands(net) <= 1
            break
        n = queue.pop(0)
        if islands(n) <= 1:
            continue
        steps += 1
        soft = set(t.GetNetname() for t in b.GetTracks() if not t.IsLocked()) - protect - {n}
        H.hot = []
        mark = _snapshot(b)
        left = route_net(b, n, width_of(widths, n), soft_nets=soft, victims_out=set(), hist=H)
        for G, cells in H.hot:
            H.add(G, cells, HIST_INC)
        H.pres = 1.0 + 0.3 * steps
        new = [t for t in b.GetTracks() if _uid(t) not in mark]
        clash = _in_the_way(b, new, soft)
        vict = set(t.GetNetname() for t in clash)
        if clash and reach:
            # the victims' copper near the clash goes too, so they can find
            # a new way out there rather than squeeze back along the old
            zone = unary_union([g for t in clash for gs in _geom_all(t).values() for g in gs]).buffer(reach)
            ids = set(_uid(t) for t in clash)
            for t in b.GetTracks():
                if t.GetNetname() in vict and not t.IsLocked() and _uid(t) not in ids and \
                        any(g.intersects(zone) for gs in _geom_all(t).values() for g in gs):
                    clash.append(t)
                    ids.add(_uid(t))
        if VERBOSE:
            log('      step %d %-12s left %d, %d new, hits %s' % (steps, n, left, len(new), sorted(vict)))
        if left and not new:
            if n != net and islands(n) <= base[n]:
                continue                       # open before, and no worse: let it be
            break                              # no way at all, not even through other nets
        for v in vict:
            if v not in base:
                base[v] = islands(v)
        for t in clash:
            removed.append(t)
            pcb.remove(b, t)
        for v in sorted(vict):
            removed.extend(_drop_floating(b, v))
            if v not in queue:
                queue.append(v)
        if left and n not in queue and (n == net or islands(n) > base[n]):
            queue.append(n)
    if ok:
        log('   negotiate %-12s routed in %d routes, nets moved: %s' % (net, steps, sorted(set(base) - {net})))
        return True
    _rollback(b, before, removed)
    log('   negotiate %-12s gave up after %d routes (%s)' % (net, steps, ' '.join(sorted(base))))
    return False


def _clip_out(b, region, nets, removed):
    """Take every unlocked track and via of `nets` out of `region` (a
    shapely polygon, board mm): a track crossing its edge is cut back to
    it.  Returns the nets touched."""
    hit = set()
    for t in list(b.GetTracks()):
        n = t.GetNetname()
        if n not in nets or t.IsLocked():
            continue
        if t.GetClass() == 'PCB_VIA':
            if region.intersects(Point(pcb.xy(t.GetPosition())).buffer(_via_r(t))):
                removed.append(t)
                pcb.remove(b, t)
                hit.add(n)
            continue
        ln = _track_line(t)
        if not ln.intersects(region):
            continue
        hit.add(n)
        outside = ln.difference(region)
        pieces = [g for g in getattr(outside, 'geoms', [outside]) if not g.is_empty and g.length > 0.02]
        removed.append(t)
        pcb.remove(b, t)
        for g in pieces:
            c = list(g.coords)
            nt = pcbnew.PCB_TRACK(b)
            nt.SetStart(pcb.P(*c[0]))
            nt.SetEnd(pcb.P(*c[-1]))
            nt.SetWidth(t.GetWidth())
            nt.SetLayer(t.GetLayer())
            nt.SetNet(t.GetNet())
            b.Add(nt)
    return hit


def region_reroute(b, net, protect, widths, margin=1.2, iters=24, log=print):
    """PathFinder in a box round the open net's gap: every unlocked signal
    net's copper inside it is taken out (tracks cut back to its edge) and
    all those nets are routed again inside it together, over and over,
    each pass with a higher price for crossing another net's copper and
    a growing history cost where they fought, until a pass ends with no
    two nets crossing.  Kept only if then the open net is joined and no
    net has more islands than before; else everything is put back."""
    global FORCE_WINDOW, SOFT_IDS
    from shapely.ops import nearest_points
    comps = _net_components(b, net)
    if len(comps) <= 1:
        return True
    pairs = sorted((_dist(comps[i], comps[j]), i, j) for i in range(len(comps)) for j in range(i + 1, len(comps)))
    _, i, j = pairs[0]
    ua = unary_union([g for gs in comps[i].values() for g in gs])
    ub = unary_union([g for gs in comps[j].values() for g in gs])
    pa, pb = nearest_points(ua, ub)
    x0, y0 = min(pa.x, pb.x) - margin, min(pa.y, pb.y) - margin
    x1, y1 = max(pa.x, pb.x) + margin, max(pa.y, pb.y) + margin
    region = box(x0, y0, x1, y1)
    unlocked = set(t.GetNetname() for t in b.GetTracks() if not t.IsLocked()) - set(protect)
    before = _snapshot(b)
    removed = []
    group = sorted(_clip_out(b, region, unlocked - {net}, removed) | {net})
    # islands each net had before the rip: none may end with more
    _rollback(b, before, removed)
    base = {n: len(_net_components(b, n)) for n in group}
    before = _snapshot(b)
    removed = []
    _clip_out(b, region, set(group), removed)
    order = [net] + [n for n in group if n != net]
    H = History(ROUTE_LAYERS, FORCE_RES)
    mine = {n: [] for n in group}
    win = (x0 - 0.3, y0 - 0.3, x1 + 0.3, y1 + 0.3)
    ok = False
    saved = FORCE_WINDOW
    FORCE_WINDOW = win
    try:
        for it in range(iters):
            H.pres = 1.0 + 1.5 * it
            for n in order:
                have = _snapshot(b)
                for t in mine[n]:
                    if _uid(t) in have:
                        pcb.remove(b, t)
                mark = _snapshot(b)
                H.hot = []
                SOFT_IDS = set(_uid(t) for m, ts in mine.items() if m != n for t in ts)
                route_net(b, n, width_of(widths, n), soft_nets=set(group) - {n}, hist=H, partners=6)
                for G, cells in H.hot:
                    H.add(G, cells, HIST_INC)
                mine[n] = [t for t in b.GetTracks() if _uid(t) not in mark]
            # legal when no net's new copper crosses another's
            clash = 0
            for n in group:
                if mine[n]:
                    clash += len(_in_the_way(b, mine[n], set(group) - {n}))
            now = {n: len(_net_components(b, n)) for n in group}
            if VERBOSE:
                log('      region %s pass %d: %d clashes, open %s' % (net, it, clash,
                                                                       [n for n in group if now[n] > base[n]]))
            if clash == 0:
                ok = now[net] == 1 and all(now[n] <= base[n] for n in group)
                if ok or it > iters // 2:
                    break
    finally:
        FORCE_WINDOW = saved
        SOFT_IDS = None
    if ok:
        log('   region %-14s routed (%d passes), %d nets re-routed in %.1f x %.1f mm'
            % (net, it + 1, len(group) - 1, x1 - x0, y1 - y0))
        return True
    if DEBUG_SAVE:
        pcbnew.SaveBoard(DEBUG_SAVE, b)
    _rollback(b, before, removed)
    log('   region %-14s failed (%d nets in %.1f x %.1f mm)' % (net, len(group), x1 - x0, y1 - y0))
    return False


# ---------------------------------------------------------------- planes
def _fill(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())


def plane_groups(b, net):
    """The net's pads grouped by what KiCad connects (after a fill): one
    group means the plane joins them all."""
    b.BuildConnectivity()
    c = b.GetConnectivity()
    pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
    seen = {}
    groups = []
    for p in pads:
        u = _uid(p)
        if u in seen:
            continue
        g = len(groups)
        groups.append([p])
        seen[u] = g
        for it in c.GetConnectedItems(p):
            if it.GetClass() == 'PAD' and it.GetNetname() == net:
                k = _uid(it)
                if k not in seen:
                    seen[k] = g
                    groups[g].append(it)
    return groups


def _group_fill(b, net, group):
    """The plane fills (all layers) KiCad joins to a pad group."""
    b.BuildConnectivity()
    c = b.GetConnectivity()
    ids = set()
    for p in group:
        ids |= {_uid(it) for it in c.GetConnectedItems(p)}
        ids.add(_uid(p))
    pts = []
    for t in b.GetTracks():
        if t.GetNetname() == net and t.GetClass() == 'PCB_VIA' and _uid(t) in ids:
            pts.append(Point(pcb.xy(t.GetPosition())))
    for p in group:
        if p.GetDrillSize().x > 0:
            pts.append(Point(pcb.xy(p.GetPosition())))
    out = {}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net:
            continue
        for l in z.GetLayerSet().Seq():
            g = _poly_set(z.GetFilledPolysList(l))
            for gg in getattr(g, 'geoms', [g]):
                if any(gg.intersects(q) for q in pts):
                    out.setdefault(l, []).append(gg)
    return out


def plane_repair(b, planes, protect, widths, rounds=4, log=print):
    """Re-open plane necks walled shut by signal vias: for each plane net
    whose pads fall in more than one group, the area near two of its
    groups' fills on one layer is barred to vias (NOVIA), every unlocked
    signal via in it is taken out with its net's copper there, and those
    nets are routed again.  Returns the plane nets still split."""
    left = []
    for r in range(rounds):
        _fill(b)
        split = {n: plane_groups(b, n) for n in planes}
        split = {n: g for n, g in split.items() if len(g) > 1}
        left = sorted(split)
        if not split:
            return []
        hit = set()
        for net, groups in split.items():
            fills = [_group_fill(b, net, g) for g in groups]
            # the necks: within reach of the main group's fill and another's
            main = max(range(len(groups)), key=lambda k: len(groups[k]))
            for k, f in enumerate(fills):
                if k == main:
                    continue
                for l, gs in f.items():
                    other = fills[main].get(l)
                    if not other:
                        continue
                    reach = VIA_D / 2 + 0.2 + 0.35
                    neck = unary_union(gs).buffer(reach).intersection(unary_union(other).buffer(reach))
                    if neck.is_empty:
                        continue
                    neck = neck.buffer(0.1)
                    NOVIA.append(neck)
                    log('   plane %s: %d pads cut off on %s; neck of %.2f mm2 barred to vias'
                        % (net, len(groups[k]), b.GetLayerName(l), neck.area))
                    for t in list(b.GetTracks()):
                        if t.GetClass() == 'PCB_VIA' and not t.IsLocked() and t.GetNetname() not in protect \
                                and neck.intersects(Point(pcb.xy(t.GetPosition())).buffer(_via_r(t) + 0.2)):
                            hit.add(t.GetNetname())
                            pcb.remove(b, t)
        if not hit:
            log('   planes still split, no signal via to move: %s' % left)
            return left
        for n in sorted(hit):
            _drop_floating(b, n)
        _fill(b)
        for n in sorted(hit):
            if route_net(b, n, width_of(widths, n)):
                ok = negotiate(b, n, protect, widths, budget=60, log=log)
                log('   plane repair: %s %s' % (n, 'routed' if ok else 'STILL OPEN'))
    _fill(b)
    return sorted(n for n in planes if len(plane_groups(b, n)) > 1)


# ---------------------------------------------------------------- dangling ends
def _unconnected(b):
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(False)


def _via_dangling(c, v):
    """A via joined to fewer than two things (track ends on it, pads it
    stands in, fills of its net)."""
    p = v.GetPosition()
    r = v.GetWidth(pcbnew.F_Cu) / 2
    n = 0
    for it in c.GetConnectedItems(v):
        if it.GetClass() in ('PCB_TRACK', 'PCB_ARC'):
            for q in (it.GetStart(), it.GetEnd()):
                if (q.x - p.x) ** 2 + (q.y - p.y) ** 2 <= r * r:
                    n += 1
                    break
        elif it.GetClass() == 'PAD':
            if it.HitTest(p):
                n += 1
        elif it.GetClass() == 'ZONE':
            n += 1
    return n < 2


def dedangle(b, log=print, rounds=30):
    """Take off unlocked tracks and vias KiCad calls dangling, one at a
    time, each only if no connection is lost.  Returns what is left."""
    _fill(b)
    base = _unconnected(b)
    removed = 0
    left = []
    for r in range(rounds):
        b.BuildConnectivity()
        c = b.GetConnectivity()
        cand = []
        for t in b.GetTracks():
            if t.IsLocked():
                continue
            if t.GetClass() == 'PCB_VIA':
                if _via_dangling(c, t):
                    cand.append(t)
            elif c.TestTrackEndpointDangling(t, True):
                cand.append(t)
        if not cand:
            return removed, []
        progress = False
        left = []
        for t in cand:
            pcb.remove(b, t)
            if _unconnected(b) <= base:
                removed += 1
                progress = True
            else:
                b.Add(t)
                left.append(t)
        if not progress:
            break
    b.BuildConnectivity()
    c = b.GetConnectivity()
    left = [t for t in b.GetTracks() if not t.IsLocked() and
            (_via_dangling(c, t) if t.GetClass() == 'PCB_VIA' else c.TestTrackEndpointDangling(t, True))]
    for t in left:
        log('   dangling, but a join: %s %s at %s' % (t.GetClass(), t.GetNetname(), pcb.xy(t.GetPosition())))
    return removed, left


# ---------------------------------------------------------------- KiCad's view
def kicad_open(b, planes):
    """Unconnected count over the signal nets, as KiCad sees it."""
    zero = b.FindNet(0)
    saved = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() in planes:
                saved.append((p, p.GetNet()))
    for t in b.GetTracks():
        if t.GetNetname() in planes:
            saved.append((t, t.GetNet()))
    for it, _ in saved:
        it.SetNet(zero)
    n = _unconnected(b)
    for it, net in saved:
        it.SetNet(net)
    b.BuildConnectivity()
    return n


def kicad_pairs(b):
    """(net, item, item) for every unconnected pair KiCad's ratsnest has,
    found by asking each net's pads and tracks which cluster they are in."""
    b.BuildConnectivity()
    c = b.GetConnectivity()
    out = []
    for net in signal_nets(b):
        items = net_items(b, net)
        seen = {}
        clusters = []
        for it in items:
            if _uid(it) in seen:
                continue
            k = len(clusters)
            clusters.append(it)
            seen[_uid(it)] = k
            for o in c.GetConnectedItems(it):
                seen.setdefault(_uid(o), k)
        for k in range(1, len(clusters)):
            out.append((net, clusters[0], clusters[k]))
    return out


# ---------------------------------------------------------------- the whole finish
def finish(path, log=print):
    """Finish a Freerouting result in place.  Returns the signal nets still
    open (KiCad's count) and the plane nets still split."""
    t0 = time.time()
    configure()
    del NOVIA[:]
    widths, protect, planes = rules()
    moved, dropped = pcb.tidy_tracks(path)
    dup = pcb.dedupe_vias(path)
    log('  tidy: %d ends joined, %d segments and %d duplicate vias dropped' % (moved, dropped, dup))
    b = pcbnew.LoadBoard(path)
    # the escape stubs and vias laid at placement were locked only so that
    # Freerouting keeps them: from here they may be torn up and moved like
    # any route (three neighbouring escapes can jam the pin between them),
    # and one the route did not use comes off with the dangling stubs
    for t in b.GetTracks():
        if t.IsLocked() and t.GetNetname() not in protect:
            t.SetLocked(False)
    _fill(b)
    open_ = unrouted_nets(b, planes)
    log('  open nets: %d %s' % (len(open_), ' '.join(open_)))
    open_.sort(key=lambda n: mst_length(b, n))
    rnd = random.Random(SEED)
    if SEED:
        rnd.shuffle(open_)
    for net in open_:
        left = route_net(b, net, width_of(widths, net))
        log('   maze   %-14s %s' % (net, 'routed' if not left else '%d islands left' % (left + 1)))
    left = unrouted_nets(b, planes)
    log('  after the maze router: %d open (%.0f s)' % (len(left), time.time() - t0))
    # the jams: rip-up with history, then PathFinder in a box round each,
    # then rip-up again with more patience; each stage only while time is left
    stages = [('negotiate', dict(budget=40)), ('region', dict(margin=1.5)), ('region', dict(margin=3.0)),
              ('negotiate', dict(budget=120, reach=0.8))]
    if SEED % 3 == 1:
        stages = [stages[3], stages[2], stages[0], stages[1]]
    elif SEED % 3 == 2:
        stages = [stages[2], stages[3], stages[1], stages[0]]
    for kind, kw in stages:
        if not left or time.time() - t0 > TIME_LIMIT:
            break
        for net in (rnd.sample(left, len(left)) if SEED else list(left)):
            if time.time() - t0 > TIME_LIMIT:
                log('  out of time (%d s)' % TIME_LIMIT)
                break
            if kind == 'negotiate':
                negotiate(b, net, protect, widths, log=log, **kw)
            else:
                region_reroute(b, net, protect, widths, log=log, **kw)
        left = unrouted_nets(b, planes)
        log('  after %s %s: %d open %s (%.0f s)' % (kind, kw, len(left), ' '.join(left), time.time() - t0))
    split = plane_repair(b, planes, protect, widths, log=log)
    log('  planes: %s (%.0f s)' % ('every plane net joined' if not split else 'STILL SPLIT %s' % split,
                                  time.time() - t0))
    # KiCad's own connectivity: geometry that touches is not always joined
    for k in range(3):
        pairs = [p for p in kicad_pairs(b) if p[0] not in protect]
        if not pairs:
            break
        for net, a, c in pairs:
            res = route_connection(b, net, _geom_of(a), _geom_of(c), width_of(widths, net))
            log('   kicad  %-14s %s' % (net, 'joined' if res else 'NO PATH'))
    n, dl = dedangle(b, log=log)
    log('  %d dangling stubs removed%s' % (n, ', %d left' % len(dl) if dl else ''))
    pcbnew.SaveBoard(path, b)
    unc = kicad_open(b, planes)
    log('  finish: %d signal connections open, planes %s (%.0f s)'
        % (unc, 'joined' if not split else 'split: %s' % split, time.time() - t0))
    return unc, split


if __name__ == '__main__':
    pcb.configure(os.environ.get('BOARD', 'main'))
    finish(sys.argv[1])
