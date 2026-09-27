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
        self.holes = []                       # (x, y, drill radius) of every plated/unplated hole
        self.pad_holes = set()                # the pad holes among them (drilled after the via fill)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                for l in layers:
                    if pad.IsOnLayer(l):
                        g = pad_poly(pad, l)
                        if g is not None:
                            self.items[l].append((g, pad.GetNetname()))
                if pad.GetDrillSize().x > 0:          # holes cut every layer
                    p = pad.GetPosition(); r = mm(pad.GetDrillSize().x) / 2
                    self.holes.append((mm(p.x), mm(p.y), r)); self.pad_holes.add((mm(p.x), mm(p.y), r))
                    for l in layers:
                        self.items[l].append((Point(mm(p.x), mm(p.y)).buffer(r), '__hole__'))
        self.vias = []
        self.netvias = []
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                self.vias.append((mm(p.x), mm(p.y)))
                self.netvias.append((mm(p.x), mm(p.y), t.GetNetname()))
                self.holes.append((mm(p.x), mm(p.y), mm(t.GetDrillValue()) / 2))
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

    # every via is filled and capped: only the holes drilled after the fill
    # (pad holes) need the POFV gap; via to via is the normal hole-to-hole rule
    VIA_GAP = 0.25

    def hole_room(self, x, y, r, gap):
        """No pad hole closer than `gap`, no via hole closer than VIA_GAP
        (or `gap` if smaller), edge to edge."""
        vg = min(gap, self.VIA_GAP)
        return all((x - hx) ** 2 + (y - hy) ** 2 >= ((gap if (hx, hy, hr) in self.pad_holes else vg) + r + hr) ** 2
                   for hx, hy, hr in self.holes)

    def via_room(self, x, y, pitch):
        """No other via (any net) closer than `pitch`, centre to centre:
        same-net vias are otherwise free to overlap, and their holes may not."""
        return all((x - vx) ** 2 + (y - vy) ** 2 >= pitch ** 2 for vx, vy in self.vias)

    # extra clearance to particular nets (e.g. a buck's switch node) and a
    # margin for the polygonal circles shapely draws
    NET_CL = {}
    MARGIN = 0.0

    def clear(self, geom, net, layers, clearance):
        cmax = max([clearance] + list(self.NET_CL.values())) + self.MARGIN
        g = geom.buffer(cmax)
        for l in layers:
            for i in self.trees[l].query(g):
                og, onet = self.items[l][i]
                if onet != net and og.intersects(g):
                    need = max(clearance, self.NET_CL.get(onet, 0.0), self.NET_CL.get(net, 0.0)) + self.MARGIN
                    if need >= cmax or og.distance(geom) < need:
                        return False
        for k in self.keepouts:
            if k.intersects(geom):
                return False
        return True

def inpad_spots(pg, d):
    """Via positions inside a pad: its centre, then along its long axis
    (the via may overhang the pad's short sides a little)."""
    c = pg.centroid
    minx, miny, maxx, maxy = pg.bounds
    out = [(float(c.x), float(c.y))]
    w, h = maxx - minx, maxy - miny
    free = (max(w, h) - d) / 2
    for f in (0.5, 1.0):
        for sgn in (-1, 1):
            if free * f > 0.05:
                out.append((float(c.x) + sgn * free * f, float(c.y)) if w >= h else (float(c.x), float(c.y) + sgn * free * f))
    return out


def fanout(board, nets, bounds, via_d=0.5, via_drill=0.25, clearance=0.15,
           ep_min_area=2.0, stub_w=0.25, skip=(), via_ok=None, ep_pitch=1.0, share=0.0,
           inpad=None, ep_join=0.0, steps=(0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3), far_share=0.0,
           off_drill=None):
    """ep_pitch: via grid pitch inside exposed pads.  share > 0: a pad with a
    same-net via within `share` mm of its edge joins that via with a stub
    instead of taking a via spot of its own.
    inpad: dict(d, drill, cl, hole_cl, hole_gap, min_pad) - put the plane via
    at the pad centre (filled and capped via-in-pad) wherever the pad is at
    least min_pad wide, the via clears other nets by cl (copper) and hole_cl
    (hole edge) on every layer, and its hole is hole_gap from any other hole.
    ep_join > 0: a pin of a part whose exposed pad is on the same net joins
    that pad with a stub this wide (QFN ground pins).
    off_drill: drill of a via placed beside its pad (default via_drill)."""
    """nets: set of net names to take into the planes.  bounds: (x0,y0,x1,y1)
    in board mm inside which vias may go (board edge minus clearance)."""
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu,
                          pcbnew.In4_Cu, pcbnew.B_Cu) if board.IsLayerEnabled(l)]
    obs = Obstacles(board, layers)
    rv = via_d / 2
    placed, failed, ep_failed = 0, [], []
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
                pitch = ep_pitch
                nx = max(1, int((maxx - minx - via_d) / pitch) + 1)
                ny = max(1, int((maxy - miny - via_d) / pitch) + 1)
                ox = (maxx + minx) / 2 - (nx - 1) * pitch / 2
                oy = (maxy + miny) / 2 - (ny - 1) * pitch / 2
                spots = [(ox + i * pitch, oy + j * pitch) for i in range(nx) for j in range(ny)]
                # a pad too small for the grid's outer vias takes one at its centre
                cx0, cy0 = (maxx + minx) / 2, (maxy + miny) / 2
                if len(spots) > 1 and not any(pg.buffer(-0.05).contains(Point(x, y).buffer(rv)) for x, y in spots):
                    spots = [(cx0, cy0)]
                for x, y in spots:
                    if True:
                        vg = Point(x, y).buffer(rv)
                        if pg.buffer(-0.05).contains(vg) and obs.clear(vg, net, layers, clearance) \
                                and obs.via_room(x, y, via_d + 0.15) and (via_ok is None or via_ok(x, y, net)):
                            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                            v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(pad.GetNet())
                            board.Add(v); obs.add(vg, net, layers); obs.vias.append((x, y)); n += 1
                            obs.netvias.append((x, y, net)); obs.holes.append((x, y, via_drill / 2))
                placed += n
                if n == 0:
                    ep_failed.append((fp.GetReference(), pad.GetNumber(), pg, net))
                continue
            # ordinary pad: candidates outward from the part first
            ang0 = math.atan2(py - fcy, px - fcx) if (abs(px - fcx) + abs(py - fcy)) > 0.05 else 0.0
            minx, miny, maxx, maxy = pg.bounds
            reach = max(maxx - minx, maxy - miny) / 2
            done = False
            from shapely.geometry import LineString
            if ep_join > 0:
                for op in fp.Pads():
                    if op.GetNetname() != net or not op.IsOnLayer(layer) or op.GetNumber() == pad.GetNumber():
                        continue
                    eg = pad_poly(op, layer)
                    if eg is None or eg.area < ep_min_area:
                        continue
                    from shapely.ops import nearest_points
                    q = nearest_points(eg, Point(px, py))[0]
                    if Point(px, py).distance(q) > 1.2:
                        continue
                    # run a little into the exposed pad
                    dx, dy = q.x - px, q.y - py; L = math.hypot(dx, dy) or 1.0
                    ex, ey = float(q.x + dx / L * 0.1), float(q.y + dy / L * 0.1)
                    sg = LineString([(px, py), (ex, ey)]).buffer(ep_join / 2)
                    if obs.clear(sg, net, [layer], inpad['cl'] if inpad else clearance):
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(ex), MM(ey)))
                        t.SetWidth(MM(ep_join)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                        board.Add(t); obs.add(sg, net, [layer]); done = True
                        break
                if done:
                    continue
            spot = None
            if inpad and min(maxx - minx, maxy - miny) >= inpad['min_pad']:
                d_in, dr_in = inpad['d'], inpad['drill']
                rr = max(inpad['cl'] + d_in / 2, inpad['hole_cl'] + dr_in / 2)
                for x, y in inpad_spots(pg, d_in):
                    vg = Point(x, y).buffer(d_in / 2)
                    if (bounds[0] + d_in / 2 < x < bounds[2] - d_in / 2 and bounds[1] + d_in / 2 < y < bounds[3] - d_in / 2
                            and obs.clear(vg, net, layers, rr - d_in / 2)
                            and obs.hole_room(x, y, dr_in / 2, inpad['hole_gap'])
                            and (via_ok is None or via_ok(x, y, net))):
                        spot = (x, y)
                        break
            if spot:
                x, y = spot
                if True:
                    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    v.SetWidth(MM(d_in)); v.SetDrill(MM(dr_in)); v.SetNet(pad.GetNet())
                    board.Add(v); obs.add(vg, net, layers); obs.vias.append((x, y))
                    obs.netvias.append((x, y, net)); obs.holes.append((x, y, dr_in / 2))
                    placed += 1
                    continue
            if share > 0:
                from shapely.geometry import LineString
                best = None
                for vx, vy, vn in obs.netvias:
                    if vn != net:
                        continue
                    d = pg.distance(Point(vx, vy))
                    if d <= share + rv and (best is None or d < best[0]):
                        sg = LineString([(px, py), (vx, vy)]).buffer(stub_w / 2)
                        if obs.clear(sg, net, [layer], clearance):
                            best = (d, vx, vy, sg)
                if best:
                    _, vx, vy, sg = best
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                    t.SetWidth(MM(stub_w)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                    board.Add(t); obs.add(sg, net, [layer])
                    continue
            for dist in [reach + rv + clearance + d for d in steps]:
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
                    # filled (via-in-pad) holes nearby keep POFV spacing
                    if inpad and not obs.hole_room(x, y, (off_drill or via_drill) / 2, inpad['hole_gap'] + 0.01):
                        continue
                    if via_ok is not None and not via_ok(x, y, net):
                        continue
                    if not obs.clear(vg, net, layers, clearance):
                        continue
                    if not obs.clear(sg, net, [layer], clearance):
                        continue
                    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    v.SetWidth(MM(via_d)); v.SetDrill(MM(off_drill or via_drill)); v.SetNet(pad.GetNet())
                    board.Add(v)
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
                    t.SetWidth(MM(stub_w)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                    board.Add(t)
                    obs.add(vg, net, layers); obs.add(sg, net, [layer]); obs.vias.append((x, y))
                    obs.netvias.append((x, y, net)); obs.holes.append((x, y, (off_drill or via_drill) / 2))
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
            if not done and far_share > 0:
                # last resort: a straight stub on the pad's layer to the
                # nearest same-net via within far_share
                best = None
                for vx, vy, vn in obs.netvias:
                    if vn != net:
                        continue
                    d = pg.distance(Point(vx, vy))
                    if d <= far_share and (best is None or d < best[0]):
                        sg = LineString([(px, py), (vx, vy)]).buffer(stub_w / 2)
                        if obs.clear(sg, net, [layer], clearance):
                            best = (d, vx, vy, sg)
                if best:
                    _, vx, vy, sg = best
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py))); t.SetEnd(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                    t.SetWidth(MM(stub_w)); t.SetLayer(layer); t.SetNet(pad.GetNet())
                    board.Add(t); obs.add(sg, net, [layer]); done = True
            if not done:
                failed.append((fp.GetReference(), pad.GetNumber()))
    # an exposed pad with no room for a via of its own is still connected
    # by a same-net via inside it (the far side's exposed pad's)
    for ref, num, pg, net in ep_failed:
        if not any(vn == net and pg.buffer(-0.05).contains(Point(vx, vy).buffer(rv)) for vx, vy, vn in obs.netvias):
            failed.append((ref, num))
    return placed, failed


def escape_vias(board, planes, inpad, far=5.0, max_pads=2, skip=(), bounds=None, lock=True, refs=(), force=(),
                only=None, only_pads=None):
    """Signal escapes in the pads themselves (filled and capped via-in-pad).

    For every signal net, a pad of a two-terminal part (resistor, capacitor,
    diode, test pad) gets a via at its centre when every other pad of its net
    is either on the other side of the board or more than `far` mm away: that
    connection has to change layer anyway, and a via in the pad costs no
    board area.  The via clears every other net by inpad['cl'] (copper) and
    inpad['hole_cl'] (hole) on every layer and keeps inpad['hole_gap'] from
    any other hole.  force: (ref, pad number) pairs that get their via
    whatever the distance (a pad boxed in by a bundle it cannot cross).
    only: if given, the parts (refs) to consider, nothing else.
    only_pads: if given, the (ref, pad number) pairs to consider, nothing else.
    Returns the number of vias placed."""
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu,
                          pcbnew.In4_Cu, pcbnew.B_Cu) if board.IsLayerEnabled(l)]
    obs = Obstacles(board, layers)
    pads = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n and n not in planes:
                side = 'T' if pad.IsOnLayer(pcbnew.F_Cu) else 'B'
                q = pad.GetPosition()
                pads.setdefault(n, []).append((fp, pad, side, mm(q.x), mm(q.y)))
    placed = 0
    d_in, dr_in = inpad['d'], inpad['drill']
    rr = max(inpad['cl'] + d_in / 2, inpad['hole_cl'] + dr_in / 2)
    for net, lst in sorted(pads.items()):
        if net in skip or len(lst) < 2:
            continue
        for fp, pad, side, x, y in lst:
            if only is not None and fp.GetReference() not in only:
                continue
            if only_pads is not None and (fp.GetReference(), pad.GetNumber()) not in only_pads:
                continue
            if (fp.GetPadCount() > max_pads and fp.GetReference() not in refs) or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            others = [o for o in lst if o[1] is not pad]
            forced = (fp.GetReference(), pad.GetNumber()) in force
            if not forced and not all(o[2] != side or math.hypot(o[3] - x, o[4] - y) > far for o in others):
                continue
            layer = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
            pg = pad_poly(pad, layer)
            minx, miny, maxx, maxy = pg.bounds
            if min(maxx - minx, maxy - miny) < inpad['min_pad']:
                continue
            spot = None
            for vx, vy in inpad_spots(pg, d_in):
                if bounds and not (bounds[0] + d_in / 2 < vx < bounds[2] - d_in / 2 and bounds[1] + d_in / 2 < vy < bounds[3] - d_in / 2):
                    continue
                vg = Point(vx, vy).buffer(d_in / 2)
                if obs.clear(vg, net, layers, rr - d_in / 2) and obs.hole_room(vx, vy, dr_in / 2, inpad['hole_gap']):
                    spot = (vx, vy)
                    break
            if not spot:
                continue
            vx, vy = spot
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy)))
            v.SetWidth(MM(d_in)); v.SetDrill(MM(dr_in)); v.SetNet(pad.GetNet())
            if lock:
                v.SetLocked(True)
            board.Add(v); obs.add(vg, net, layers); obs.vias.append((vx, vy))
            obs.netvias.append((vx, vy, net)); obs.holes.append((vx, vy, dr_in / 2))
            placed += 1
    return placed


def drop_unused_escapes(path):
    """Remove in-pad escape vias the router never used (KiCad reports them as
    dangling: joined to their own pad only).  Returns how many."""
    import json, subprocess
    out = path + '.esc.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', out, path],
                   capture_output=True)
    ids = set()
    for v in json.load(open(out))['violations']:
        if v['type'] == 'via_dangling':
            ids.update(i['uuid'] for i in v['items'])
    if not ids:
        return 0
    b = pcbnew.LoadBoard(path)
    pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
    n = 0
    import pcb
    for t in list(b.GetTracks()):
        if t.GetClass() != 'PCB_VIA' or t.m_Uuid.AsString() not in ids:
            continue
        q = t.GetPosition()
        if any(p.GetNetname() == t.GetNetname() and p.HitTest(q) for p in pads):
            pcb.remove(b, t); n += 1
    b.Save(path)
    return n


def dogbones(board, pins, via_d=0.35, via_drill=0.2, width=0.2, cl=0.1, hole_gap=0.25, lock=True, inpad=None,
             hole_cl=0.0):
    """A dog-bone escape for each (ref, pad number) of a QFN: a via just
    outside the pad, straight out from the package (or a little to either
    side), joined to the pad by a stub on the pad's layer.  Adjacent
    escapes are staggered (near / far) so traces can still pass.  The via
    clears every other net by `cl` on every layer and keeps `hole_gap` to
    via holes (the POFV gap to pad holes); the stub clears every other net
    on its layer.  inpad=(d, drill): first try a via of that size inside
    the pad itself, at its outer end (filled and capped, POFV); the
    dog-bone is the fallback.  hole_cl: every via's hole also clears other
    nets' copper by this much.  Returns (placed, failed pins)."""
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu,
                          pcbnew.In4_Cu, pcbnew.B_Cu) if board.IsLayerEnabled(l)]
    obs = Obstacles(board, layers)
    from shapely.geometry import LineString
    placed, failed = 0, []
    order = list(pins)                     # the caller's order: earlier pins get the nearer spots
    last = {}
    for ref, num in order:
        fp = board.FindFootprintByReference(ref)
        pad = next(p for p in fp.Pads() if p.GetNumber() == num)
        L = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
        c, q = fp.GetPosition(), pad.GetPosition()
        qx, qy = mm(q.x), mm(q.y)
        dx, dy = qx - mm(c.x), qy - mm(c.y)
        bb = pad.GetBoundingBox()
        if abs(dx) >= abs(dy):
            nx, ny, h = (1 if dx > 0 else -1), 0, mm(bb.GetWidth()) / 2
        else:
            nx, ny, h = 0, (1 if dy > 0 else -1), mm(bb.GetHeight()) / 2
        tx, ty = -ny, nx
        near = h + 0.06 + via_d / 2
        # stagger against the neighbouring pin's escape on the same face
        prev = last.get((ref, nx, ny))
        dists = [near, near + 0.45, near + 0.9]
        if prev is not None and abs(prev[0] - (qx * tx + qy * ty)) < 0.75 and prev[1] == 0:
            dists = [near + 0.45, near + 0.9, near]
        net = pad.GetNetname()
        spot = None
        if inpad:
            d_in, dr_in = inpad
            # towards the pad's outer end, clear of its rounded corners
            pp = pad_poly(pad, L)
            s_ = max(0.0, h - d_in / 2 - 0.08)
            vx, vy = qx + nx * s_, qy + ny * s_
            vg = Point(vx, vy).buffer(d_in / 2)
            if (pp.buffer(0.005).contains(vg) and obs.clear(vg, net, layers, cl)
                    and obs.clear(Point(vx, vy).buffer(dr_in / 2), net, layers, hole_cl)
                    and obs.hole_room(vx, vy, dr_in / 2, hole_gap)):
                v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                v.SetWidth(MM(d_in)); v.SetDrill(MM(dr_in)); v.SetNet(pad.GetNet())
                if lock:
                    v.SetLocked(True)
                board.Add(v)
                obs.add(vg, net, layers); obs.vias.append((vx, vy)); obs.netvias.append((vx, vy, net))
                obs.holes.append((vx, vy, dr_in / 2))
                placed += 1
                continue
        for k, d in enumerate(dists):
            for lat in (0.0, 0.25, -0.25, 0.5, -0.5):
                vx, vy = qx + nx * d + tx * lat, qy + ny * d + ty * lat
                vg = Point(vx, vy).buffer(via_d / 2)
                if not obs.clear(vg, net, layers, cl) or not obs.hole_room(vx, vy, via_drill / 2, hole_gap) \
                        or not obs.clear(Point(vx, vy).buffer(via_drill / 2), net, layers, hole_cl):
                    continue
                # stub: straight out of the pad, then over to the via
                ex, ey = qx + nx * (d - 0.0), qy + ny * (d - 0.0)
                pts = [(qx, qy), (ex, ey)] if lat == 0 else [(qx, qy), (qx + nx * (d - abs(lat)), qy + ny * (d - abs(lat))), (vx, vy)]
                sg = LineString(pts).buffer(width / 2)
                if not obs.clear(sg, net, [L], cl):
                    continue
                spot = (vx, vy, pts, 0 if k == 0 or dists[0] == near else 1)
                break
            if spot:
                break
        if not spot:
            failed.append((ref, num))
            continue
        vx, vy, pts, far_ = spot
        last[(ref, nx, ny)] = (qx * tx + qy * ty, 0 if abs((vx - qx) * nx + (vy - qy) * ny - near) < 1e-6 else 1)
        v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy)))
        v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(pad.GetNet())
        if lock:
            v.SetLocked(True)
        board.Add(v)
        vg = Point(vx, vy).buffer(via_d / 2)
        obs.add(vg, net, layers); obs.vias.append((vx, vy)); obs.netvias.append((vx, vy, net))
        obs.holes.append((vx, vy, via_drill / 2))
        for a, b_ in zip(pts[:-1], pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(MM(b_[0]), MM(b_[1])))
            t.SetWidth(MM(width)); t.SetLayer(L); t.SetNet(pad.GetNet())
            if lock:
                t.SetLocked(True)
            board.Add(t)
            obs.add(LineString([a, b_]).buffer(width / 2), net, [L])
        placed += 1
    return placed, failed
