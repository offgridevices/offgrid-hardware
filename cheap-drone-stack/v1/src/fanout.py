# -*- coding: utf-8 -*-
"""Connect surface-mount pads to an inner plane with one via each.

Freerouting routes pad to pad; it does not drop a via from a ground pad into
the ground plane.  This does, before autorouting: for every SMD pad on a
plane net it tries positions just outside the pad (outward from the part
first), keeps the first that clears every other net's copper, and joins it
to the pad with a short stub.  Exposed pads get a grid of vias inside them.
"""
import math
import pcbnew
from shapely.geometry import Point, Polygon, box
from shapely.strtree import STRtree
from shapely.ops import unary_union

MM = pcbnew.FromMM
def mm(v): return v / 1e6

def pad_poly(pad, layer):
    sp = pad.GetEffectivePolygon(layer)
    polys = []
    for i in range(sp.OutlineCount()):
        ol = sp.Outline(i)
        pts = [(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]
        if len(pts) >= 3:
            polys.append(Polygon(pts))
    return unary_union(polys) if polys else None

class Obstacles:
    """Copper on each layer, tagged with its net, for clearance checks."""
    def __init__(self, board, layers):
        self.items = {l: [] for l in layers}
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                for l in layers:
                    if pad.IsOnLayer(l):
                        g = pad_poly(pad, l)
                        if g is not None:
                            self.items[l].append((g, pad.GetNetname()))
                if pad.GetDrillSize().x > 0:          # holes cut every layer
                    p = pad.GetPosition(); r = mm(pad.GetDrillSize().x) / 2
                    for l in layers:
                        self.items[l].append((Point(mm(p.x), mm(p.y)).buffer(r), '__hole__'))
        self.vias = []
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                self.vias.append((mm(p.x), mm(p.y)))
                g = Point(mm(p.x), mm(p.y)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2)
                for l in layers:
                    self.items[l].append((g, t.GetNetname()))
            else:
                if t.GetLayer() in layers:
                    s, e = t.GetStart(), t.GetEnd()
                    from shapely.geometry import LineString
                    g = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2)
                    self.items[t.GetLayer()].append((g, t.GetNetname()))
        self.keepouts = []
        for z in board.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowVias():
                ol = z.Outline().Outline(0)
                self.keepouts.append(Polygon([(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]))
        self._index()

    def _index(self):
        self.trees = {l: STRtree([g for g, _ in v]) for l, v in self.items.items()}

    def add(self, geom, net, layers):
        for l in layers:
            self.items[l].append((geom, net))
        self._index()

    def via_room(self, x, y, pitch):
        """No other via (any net) closer than `pitch`, centre to centre:
        same-net vias are otherwise free to overlap, and their holes may not."""
        return all((x - vx) ** 2 + (y - vy) ** 2 >= pitch ** 2 for vx, vy in self.vias)

    def clear(self, geom, net, layers, clearance):
        g = geom.buffer(clearance)
        for l in layers:
            for i in self.trees[l].query(g):
                og, onet = self.items[l][i]
                if onet != net and og.intersects(g):
                    return False
        for k in self.keepouts:
            if k.intersects(geom):
                return False
        return True

def fanout(board, nets, bounds, via_d=0.5, via_drill=0.25, clearance=0.15,
           ep_min_area=2.0, stub_w=0.25, skip=()):
    """nets: set of net names to take into the planes.  bounds: (x0,y0,x1,y1)
    in board mm inside which vias may go (board edge minus clearance)."""
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu,
                          pcbnew.In4_Cu, pcbnew.B_Cu) if board.IsLayerEnabled(l)]
    obs = Obstacles(board, layers)
    rv = via_d / 2
    placed, failed = 0, []
    for fp in board.GetFootprints():
        fc = fp.GetPosition(); fcx, fcy = mm(fc.x), mm(fc.y)
        if fp.GetReference() in skip:
            continue
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net not in nets or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            pg = pad_poly(pad, layer)
            px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
            if pg.area >= ep_min_area:
                # exposed / thermal pad: grid of vias inside it
                minx, miny, maxx, maxy = pg.bounds
                n = 0
                pitch = 1.0
                nx = max(1, int((maxx - minx - via_d) / pitch) + 1)
                ny = max(1, int((maxy - miny - via_d) / pitch) + 1)
                ox = (maxx + minx) / 2 - (nx - 1) * pitch / 2
                oy = (maxy + miny) / 2 - (ny - 1) * pitch / 2
                for i in range(nx):
                    for j in range(ny):
                        x, y = ox + i * pitch, oy + j * pitch
                        vg = Point(x, y).buffer(rv)
                        if pg.buffer(-0.05).contains(vg) and obs.clear(vg, net, layers, clearance) \
                                and obs.via_room(x, y, via_d + 0.15):
                            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                            v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(pad.GetNet())
                            board.Add(v); obs.add(vg, net, layers); obs.vias.append((x, y)); n += 1
                placed += n
                if n == 0:
                    failed.append((fp.GetReference(), pad.GetNumber()))
                continue
            # ordinary pad: candidates outward from the part first
            ang0 = math.atan2(py - fcy, px - fcx) if (abs(px - fcx) + abs(py - fcy)) > 0.05 else 0.0
            minx, miny, maxx, maxy = pg.bounds
            reach = max(maxx - minx, maxy - miny) / 2
            done = False
            for dist in [reach + rv + clearance + d for d in (0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3)]:
                for k in range(0, 24):
                    a = ang0 + (math.pi / 12) * ((k + 1) // 2) * (1 if k % 2 else -1)
                    x, y = px + dist * math.cos(a), py + dist * math.sin(a)
                    if not (bounds[0] + rv < x < bounds[2] - rv and bounds[1] + rv < y < bounds[3] - rv):
                        continue
                    vg = Point(x, y).buffer(rv)
                    from shapely.geometry import LineString
                    sg = LineString([(px, py), (x, y)]).buffer(stub_w / 2)
                    if not obs.via_room(x, y, via_d + 0.15):
                        continue
                    if not obs.clear(vg, net, layers, clearance):
                        continue
                    if not obs.clear(sg, net, [layer], clearance):
                        continue
                    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(pad.GetNet())
                    board.Add(v)
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
                    t.SetWidth(MM(stub_w)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                    board.Add(t)
                    obs.add(vg, net, layers); obs.add(sg, net, [layer]); obs.vias.append((x, y))
                    placed += 1; done = True
                    break
                if done:
                    break
            if not done:
                # no room for a via: join the pad to the nearest pad of the
                # same net on the same layer (its decoupling capacitor)
                from shapely.geometry import LineString
                best = None
                for ofp in board.GetFootprints():
                    for op in ofp.Pads():
                        if op.GetNetname() != net or op == pad or not op.IsOnLayer(layer) or ofp == fp:
                            continue
                        ox, oy = mm(op.GetPosition().x), mm(op.GetPosition().y)
                        d = math.hypot(ox - px, oy - py)
                        if d < 3.0 and (best is None or d < best[0]):
                            best = (d, ox, oy)
                if best:
                    _, ox, oy = best
                    sg = LineString([(px, py), (ox, oy)]).buffer(0.1)
                    if obs.clear(sg, net, [layer], clearance):
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(ox), MM(oy)))
                        t.SetWidth(MM(0.2)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                        board.Add(t); obs.add(sg, net, [layer]); done = True
            if not done:
                failed.append((fp.GetReference(), pad.GetNumber()))
    return placed, failed
