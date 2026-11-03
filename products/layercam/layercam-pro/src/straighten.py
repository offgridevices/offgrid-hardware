# -*- coding: utf-8 -*-
"""Straighten the routers' stair-steps.

The maze router works on a 0.05 mm grid; where it squeezes past a
neighbour it leaves runs of tiny steps (a "staircase") that a designer
would draw as one straight track, or one straight and one 45-degree track.
Each chain of tracks (one net, one layer, one width, joined end to end
with nothing else meeting it: no pad, via or third track at its inner
points) is redrawn, greedily from its start, as the fewest tracks at 0, 45
or 90 degrees that keep the board's clearance to every other net's copper,
holes, keepouts and the board edge.  The chain's two ends never move, so
nothing it joins is lost.  Locked copper (coupled pairs, the antenna
feed) is left alone.  KiCad's DRC checks the board afterwards.

    python3 straighten.py BOARD.kicad_pcb        straightens in place
"""
import math
import os
import sys
from collections import defaultdict

import pcbnew
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcb
from miter import _polys

LAYERS = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)   # In3 tracks hop through a pour: left as routed
EXTRA = 0.01          # mm over the clearance (the shapes' chords)
HOLE_CLEAR = 0.3      # track to a drilled hole
SPAN = 40             # the most points one replacement may skip
EPS = 1e-4            # mm


def _key(v):
    return (v.x, v.y)


def _mm(k):
    return (k[0] / 1e6, k[1] / 1e6)


def _octi(a, b):
    """The octilinear ways from a to b: [[a, b]] if a-b is already at 0, 45
    or 90 degrees, else the two two-track ways (45 first, straight first)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ax_, ay_ = abs(dx), abs(dy)
    if ax_ < EPS or ay_ < EPS or abs(ax_ - ay_) < EPS:
        return [[a, b]]
    m = min(ax_, ay_)
    sx, sy = math.copysign(1, dx), math.copysign(1, dy)
    k1 = (a[0] + sx * m, a[1] + sy * m)
    k2 = (b[0] - sx * m, b[1] - sy * m)
    return [[a, k1, b], [a, k2, b]]


def straighten(path, clearance=None):
    clearance = (pcb.CLEAR if clearance is None else clearance) + EXTRA
    b = pcbnew.LoadBoard(path)
    obst = defaultdict(list)                      # layer -> [(shape, net)]
    same = defaultdict(list)                      # (net, layer) -> pads and vias
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition()
            s = Point(q.x / 1e6, q.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 12)
            for layer in LAYERS:
                obst[layer].append((s, t.GetNetname()))
                same[(t.GetNetname(), layer)].append(s)
        elif t.GetLayer() in LAYERS:
            for s in _polys(t, t.GetLayer()):
                obst[t.GetLayer()].append((s, t.GetNetname()))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for layer in LAYERS:
                if p.IsOnLayer(layer):
                    for s in _polys(p, layer):
                        obst[layer].append((s, p.GetNetname()))
                        same[(p.GetNetname(), layer)].append(s)
            if p.GetDrillSize().x > 0:
                q = p.GetPosition()
                h = Point(q.x / 1e6, q.y / 1e6).buffer(p.GetDrillSize().x / 2e6 + HOLE_CLEAR - clearance, 12)
                for layer in LAYERS:
                    obst[layer].append((h, None))            # every net, its own too
    for z in b.Zones():
        for layer in LAYERS:
            if not z.IsOnLayer(layer):
                continue
            ol = z.Outline()
            ring = lambda o: [(o.CPoint(k).x / 1e6, o.CPoint(k).y / 1e6) for k in range(o.PointCount())]
            for i in range(ol.OutlineCount()):
                poly = Polygon(ring(ol.Outline(i)),
                               [ring(ol.Hole(i, h)) for h in range(ol.HoleCount(i))]).buffer(0)
                if z.GetIsRuleArea():
                    if z.GetDoNotAllowTracks():
                        obst[layer].append((poly, None))
                elif z.GetNetname() != 'GND':                # the ground fill is poured afterwards
                    obst[layer].append((poly, z.GetNetname()))
    trees = {l: (STRtree([s for s, _ in v]), v) for l, v in obst.items()}
    inside = affinity.translate(pcb.board_polygon(), pcb.CX, pcb.CY).buffer(-pcb.EDGE_BAND)

    def clear(pts, w, net, layer):
        g = LineString(pts).buffer(w / 2 + clearance, cap_style=1)
        if not inside.contains(LineString(pts).buffer(w / 2)):
            return False
        tree, items = trees[layer]
        for i in tree.query(g):
            s, n = items[int(i)]
            if n != net and s.intersects(g):
                return False
        return not any(n != net and s.intersects(g) for s, n in fresh[layer])

    # (net, layer) -> node -> [(track, end)].  A node is a cluster of track
    # ends closer than the narrower track's width: the routers often leave
    # ends that join only by their copper overlapping, not at one point.
    graph = defaultdict(lambda: defaultdict(list))
    at = {}                                       # (net, layer) -> node -> centre (mm)
    ends_of = defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK' and t.GetLayer() in LAYERS:
            for k, p in (('s', t.GetStart()), ('e', t.GetEnd())):
                ends_of[(t.GetNetname(), t.GetLayer())].append((t, k, _mm(_key(p))))
    for nl, ends in ends_of.items():
        parent = list(range(len(ends)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        cell = defaultdict(list)
        for i, (t, k, q) in enumerate(ends):
            cell[(int(q[0] // 0.2), int(q[1] // 0.2))].append(i)
        for i, (t, k, q) in enumerate(ends):
            cx, cy = int(q[0] // 0.2), int(q[1] // 0.2)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in cell.get((cx + dx, cy + dy), ()):
                        if j <= i:
                            continue
                        t2, k2, q2 = ends[j]
                        if math.hypot(q[0] - q2[0], q[1] - q2[1]) < 0.9 * min(t.GetWidth(), t2.GetWidth()) / 1e6:
                            parent[find(i)] = find(j)
        cent = defaultdict(list)
        for i, (t, k, q) in enumerate(ends):
            graph[nl][find(i)].append((t, k))
            cent[find(i)].append(q)
        at[nl] = {n: (sum(q[0] for q in v) / len(v), sum(q[1] for q in v) / len(v)) for n, v in cent.items()}
    node_of = {}
    for nl, nodes in graph.items():
        for n, ends in nodes.items():
            for t, k in ends:
                node_of[(id(t), k)] = n
    fresh = defaultdict(list)                     # layer -> [(shape, net)] drawn here

    def internal(t):
        """A track shorter than its width: both its ends in one node (a stair's riser)."""
        return node_of[(id(t), 's')] == node_of[(id(t), 'e')]

    def outer(net, layer, n):
        return [(t, k) for t, k in graph[(net, layer)][n] if not internal(t)]

    def inner(net, layer, n, w):
        """Is node n a plain bend of one chain (two tracks of width w, and
        only risers inside it: no pad, via or third track)?"""
        ends = outer(net, layer, n)
        if len(ends) != 2 or ends[0][0] is ends[1][0] \
                or any(t.IsLocked() or t.GetWidth() != w for t, _ in graph[(net, layer)][n]):
            return False
        P_ = Point(at[(net, layer)][n])
        return not any(s.contains(P_) for s in same[(net, layer)])

    def end_pt(t, k):
        return _mm(_key(t.GetStart() if k == 's' else t.GetEnd()))

    done_tracks = set()
    removed = added = 0
    for (net, layer), pts in list(graph.items()):
        for n0, ends0 in list(pts.items()):
            for t0, e0 in list(ends0):
                if id(t0) in done_tracks or t0.IsLocked() or internal(t0):
                    continue
                w = t0.GetWidth()
                if inner(net, layer, n0, w):
                    continue                      # start chains at their ends only
                # walk the chain from n0
                P, chain_tr, nodes = [end_pt(t0, e0)], [], [n0]
                t, e = t0, e0
                while True:
                    chain_tr.append(t)
                    done_tracks.add(id(t))
                    o_k = 'e' if e == 's' else 's'
                    o = node_of[(id(t), o_k)]
                    nodes.append(o)
                    if not inner(net, layer, o, w):
                        P.append(end_pt(t, o_k))
                        break
                    P.append(at[(net, layer)][o])
                    for t2, _ in pts[o]:                  # the node's risers go with the chain
                        if internal(t2) and id(t2) not in done_tracks:
                            chain_tr.append(t2)
                            done_tracks.add(id(t2))
                    nxt = [(t2, k2) for t2, k2 in outer(net, layer, o) if t2 is not t]
                    if not nxt or id(nxt[0][0]) in done_tracks:
                        P[-1] = end_pt(t, o_k)
                        break
                    t, e = nxt[0]
                if len(chain_tr) < 3 or len(P) < 4:
                    continue
                # other copper of this net touching the chain's middle (a
                # track ending on it, not at a joint): leave such chains be
                wmm = w / 1e6
                old = unary_union([LineString([end_pt(t, 's'), end_pt(t, 'e')]).buffer(wmm / 2)
                                   for t in chain_tr])
                ids = {id(t) for t in chain_tr}
                tee = False
                for n_, ends in pts.items():
                    if n_ in (nodes[0], nodes[-1]):
                        continue
                    if any(id(t) not in ids and old.intersects(Point(end_pt(t, k)).buffer(t.GetWidth() / 2e6))
                           for t, k in ends):
                        tee = True
                        break
                if tee:
                    continue
                for s_ in same[(net, layer)]:
                    if s_.intersects(old) and not (s_.contains(Point(P[0])) or s_.contains(Point(P[-1]))):
                        tee = True
                        break
                if tee:
                    continue
                # greedy: from each kept point, the farthest point reachable
                out = [P[0]]
                i = 0
                while i < len(P) - 1:
                    best = None
                    for j in range(min(len(P) - 1, i + SPAN), i + 1, -1):
                        for way in _octi(P[i], P[j]):
                            # fewer tracks than the run it replaces
                            if len(way) - 1 >= j - i:
                                continue
                            if clear(way, wmm, net, layer):
                                best = (j, way)
                                break
                        if best:
                            break
                    if best:
                        j, way = best
                        out += way[1:]
                    else:
                        # no shortcut: the step as it was, between the
                        # nodes' centres; it must keep the clearance too
                        j = i + 1
                        if not clear([P[i], P[j]], wmm, net, layer):
                            out = None
                            break
                        out.append(P[j])
                    i = j
                if out is None or len(out) >= len(P):
                    continue
                for t in chain_tr:
                    b.Remove(t)
                removed += len(chain_tr)
                V = lambda q: pcbnew.VECTOR2I(int(round(q[0] * 1e6)), int(round(q[1] * 1e6)))
                for a_, c_ in zip(out, out[1:]):
                    if math.hypot(c_[0] - a_[0], c_[1] - a_[1]) < EPS:
                        continue
                    nt = pcbnew.PCB_TRACK(b)
                    nt.SetStart(V(a_)); nt.SetEnd(V(c_))
                    nt.SetWidth(w); nt.SetLayer(layer); nt.SetNet(chain_tr[0].GetNet())
                    b.Add(nt)
                    fresh[layer].append((LineString([a_, c_]).buffer(wmm / 2), net))
                    added += 1
    pcbnew.SaveBoard(path, b)
    return removed, added


if __name__ == '__main__':
    r, a = straighten(sys.argv[1])
    print('straightened: %d tracks became %d' % (r, a))
