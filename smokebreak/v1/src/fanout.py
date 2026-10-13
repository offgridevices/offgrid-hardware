"""Ground fan-out before autorouting: every top-side ground pad gets its own
short track and via into the In1 ground plane, placed where they clear every
other net's copper.  The router is then left with the signals only.

    fanout_gnd(board, nets=('GND',), via=(0.5, 0.25))  -> (pads done, pads left)
"""
import math

import pcbnew
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

import board as B

mm = lambda v: pcbnew.ToMM(v)


def _poly(sp):
    out = []
    for k in range(sp.OutlineCount()):
        ol = sp.Outline(k)
        pts = [(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]
        if len(pts) > 2:
            out.append(Polygon(pts).buffer(0))
    return out


def _clear(net, classes):
    return classes.get(net, B.CLEAR)


def fanout_gnd(b, nets=('GND',), via=(0.5, 0.25), track=0.25, classes=None, edge=0.5, region=None):
    """region: a polygon (board mm): only pads, and vias, inside it (one
    plane of a split layer)."""
    reg = None
    if region:
        from shapely.geometry import Polygon as _P
        reg = _P([(x + B.OX, y + B.OY) for x, y in region])
    classes = classes or {}
    vd, vdr = via
    # obstacles: every copper item on F.Cu (pads, tracks, zones of other nets),
    # every hole, and the vias we add as we go
    fcu, holes = [], []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                for g in _poly(p.GetEffectivePolygon(pcbnew.F_Cu)):
                    fcu.append((g, p.GetNetname()))
            if p.GetDrillSize().x > 0:
                q = p.GetPosition()
                holes.append(Point(mm(q.x), mm(q.y)).buffer(mm(p.GetDrillSize().x) / 2))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition()
            g = Point(mm(q.x), mm(q.y)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2)
            fcu.append((g, t.GetNetname()))
            holes.append(Point(mm(q.x), mm(q.y)).buffer(mm(t.GetDrillValue()) / 2))
        elif t.GetLayer() == pcbnew.F_Cu:
            s, e = t.GetStart(), t.GetEnd()
            fcu.append((LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2),
                        t.GetNetname()))
    zones = []           # other-net zone outlines on F.Cu and on In2 (a via must not land in them)
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        ol = z.Outline()
        for k in range(ol.OutlineCount()):
            o = ol.Outline(k)
            g = Polygon([(mm(o.CPoint(i).x), mm(o.CPoint(i).y)) for i in range(o.PointCount())])
            if z.GetLayerSet().Contains(pcbnew.F_Cu):
                zones.append((g, z.GetNetname()))
    x0, y0 = B.OX + edge, B.OY + edge
    x1, y1 = B.OX + B.W - edge, B.OY + B.H - edge
    done = left = 0
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        if fp.GetAttributes() & pcbnew.FP_THROUGH_HOLE:
            continue
        c = fp.GetPosition()
        cx, cy = mm(c.x), mm(c.y)
        for p in fp.Pads():
            net = p.GetNetname()
            if net not in nets or not p.IsOnLayer(pcbnew.F_Cu) or p.GetDrillSize().x > 0:
                continue
            q = p.GetPosition()
            px, py = mm(q.x), mm(q.y)
            if reg is not None and not reg.contains(Point(px, py)):
                continue
            pad_g = unary_union(_poly(p.GetEffectivePolygon(pcbnew.F_Cu)))
            # outward first (away from the part's centre), then all round
            a0 = math.atan2(py - cy, px - cx) if (px, py) != (cx, cy) else 0.0
            best = None
            for r in (0.75, 0.95, 1.15, 1.4, 1.7, 2.0, 2.4):
                for d in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8):
                    a = a0 + d * math.pi / 8
                    vx, vy = px + r * math.cos(a), py + r * math.sin(a)
                    if not (x0 < vx < x1 and y0 < vy < y1):
                        continue
                    if reg is not None and not reg.buffer(-0.5).contains(Point(vx, vy)):
                        continue
                    vg = Point(vx, vy).buffer(vd / 2)
                    tg = LineString([(px, py), (vx, vy)]).buffer(track / 2)
                    ok = True
                    for g, n in fcu:
                        if n == net:
                            continue
                        cl = max(_clear(n, classes), _clear(net, classes)) + 0.02
                        if g.distance(vg) < cl or g.distance(tg) < cl:
                            ok = False
                            break
                    if ok and any(h.distance(Point(vx, vy)) < vdr / 2 + 0.25 + 0.0 for h in holes):
                        ok = False
                    if ok and any(g.buffer(0.2).contains(Point(vx, vy)) for g, n in zones if n != net):
                        ok = False
                    if ok and pad_g.contains(Point(vx, vy)):
                        ok = False                      # no via in the pad
                    if ok:
                        best = (vx, vy)
                        break
                if best:
                    break
            if not best:
                left += 1
                continue
            vx, vy = best
            B.track(b, [(px - B.OX, py - B.OY), (vx - B.OX, vy - B.OY)], track, pcbnew.F_Cu, net)
            v = B.via(b, vx - B.OX, vy - B.OY, net, d=vd, drill=vdr)
            fcu.append((Point(vx, vy).buffer(vd / 2), net))
            fcu.append((LineString([(px, py), (vx, vy)]).buffer(track / 2), net))
            holes.append(Point(vx, vy).buffer(vdr / 2))
            done += 1
    return done, left
