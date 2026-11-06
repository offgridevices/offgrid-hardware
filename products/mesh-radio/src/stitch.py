# -*- coding: utf-8 -*-
"""Power via stitching on the routed board: as many vias as fit where the
big currents change layer.

The thermal model (sim/thermal) found the board's copper, not its FETs,
the largest heat source at full throttle: 60 A from the battery pads into
the planes through a dozen vias, and each shunt's return to ground through
two or three.  After routing, this adds a via of the pad's own net on a
grid wherever one clears every other net's copper on all six layers (pads,
tracks, vias, and the power pours of other nets), every hole keeps its
hole-to-hole distance, and no keepout is touched.  The planes and fills are
refilled round the new vias afterwards.

    stitch.stitch(board, [('P_BAT+', None), ('R100', '2'), ...])
"""
import math
import pcbnew
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import fanout

import pcb
CU = list(pcb.CU_IDS)
MM = pcbnew.FromMM
def mm(v): return v / 1e6

# zones every net may cut through: the full planes and the ground fill
SOFT_ZONES = ('GND plane', 'VBAT plane', 'GND fill', 'VBAT fill')


def _zone_polys(b, skip_net):
    """Filled copper of the power pours of other nets, per layer."""
    out = {l: [] for l in CU}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetZoneName() in SOFT_ZONES or z.GetNetname() == skip_net:
            continue
        for l in CU:
            if not z.IsOnLayer(l):
                continue
            fp = z.GetFilledPolysList(l)
            for i in range(fp.OutlineCount()):
                ol = fp.Outline(i)
                pts = [(mm(ol.CPoint(j).x), mm(ol.CPoint(j).y)) for j in range(ol.PointCount())]
                if len(pts) >= 3:
                    out[l].append((Polygon(pts).buffer(0), z.GetNetname()))
    return out


def stitch(b, targets, via=(0.5, 0.25), pitch=0.75, clearance=0.13, hole_gap=0.25, grow=0.4, log=print):
    """targets: [(ref, pad number or None for every pad)].  Vias go on a
    `pitch` grid over each pad grown by `grow` mm (the via may stand just
    outside the pad on its own net's pour or track).  Returns the count."""
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    d, drill = via
    total = 0
    for ref, num in targets:
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            raise SystemExit('stitch: no %s' % ref)
        for pad in fp.Pads():
            if num is not None and pad.GetNumber() != num:
                continue
            net = pad.GetNetname()
            obs = fanout.Obstacles(b, CU)
            for l, polys in _zone_polys(b, net).items():
                for g, n in polys:
                    obs.items[l].append((g, n))
            obs._index()
            layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            area = fanout.pad_poly(pad, layer).buffer(grow)
            x0, y0, x1, y1 = area.bounds
            c = area.centroid
            pts = []
            nx, ny = int((x1 - x0) / pitch) + 1, int((y1 - y0) / pitch) + 1
            for i in range(-nx, nx + 1):
                for j in range(-ny, ny + 1):
                    x, y = c.x + i * pitch, c.y + j * pitch
                    if area.contains(Point(x, y)):
                        pts.append((x, y))
            pts.sort(key=lambda p: (p[0] - c.x) ** 2 + (p[1] - c.y) ** 2)
            n = 0
            for x, y in pts:
                g = Point(x, y).buffer(d / 2, 16)
                if not obs.hole_room(x, y, drill / 2, hole_gap):
                    continue
                if not obs.clear(g, net, CU, clearance):
                    continue
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(d)); v.SetDrill(MM(drill))
                v.SetNet(b.FindNet(net))
                v.SetLocked(True)
                b.Add(v)
                obs.add(g, net, CU)
                obs.holes.append((x, y, drill / 2))
                obs.vias.append((x, y))
                n += 1
            log('  stitch %s.%s (%s): %d vias' % (ref, pad.GetNumber(), net, n))
            total += n
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    return total


def stitch_ground(b, pitch=1.0, via=(0.4, 0.2), clearance=0.13, hole_gap=0.25, log=print):
    """Ground stitching: a via on a `pitch` grid wherever F.Cu or B.Cu is
    poured ground (filled) and the via clears every other net's copper on
    all six layers (pads, tracks, vias, and the other nets' pours), so the
    outer ground pours, the ground pads in them and the In1 plane are one.
    Returns the count."""
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    d, drill = via
    obs = fanout.Obstacles(b, CU)
    gnd = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in CU:
            if not z.IsOnLayer(l):
                continue
            fp_ = z.GetFilledPolysList(l)
            for i in range(fp_.OutlineCount()):
                o = fp_.Outline(i)
                pts = [(mm(o.CPoint(j).x), mm(o.CPoint(j).y)) for j in range(o.PointCount())]
                if len(pts) < 3:
                    continue
                g = Polygon(pts).buffer(0)
                if z.GetNetname() == 'GND':
                    if l in gnd:
                        gnd[l].append(g)
                elif z.GetZoneName() not in ('GND plane', 'VBAT plane'):
                    obs.items[l].append((g, z.GetNetname()))
    obs._index()
    area = unary_union(gnd[pcbnew.F_Cu] + gnd[pcbnew.B_Cu]).buffer(-d / 2 - 0.05)
    x0, y0, x1, y1 = area.bounds
    n = 0
    import shapely
    shapely.prepare(area)
    xs = [x0 + i * pitch for i in range(int((x1 - x0) / pitch) + 2)]
    ys = [y0 + j * pitch for j in range(int((y1 - y0) / pitch) + 2)]
    for x in xs:
        for y in ys:
            if not area.contains(Point(x, y)):
                continue
            g = Point(x, y).buffer(d / 2, 16)
            if not obs.hole_room(x, y, drill / 2, hole_gap) or not obs.clear(g, 'GND', CU, clearance):
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(d)); v.SetDrill(MM(drill))
            v.SetNet(b.FindNet('GND'))
            b.Add(v)
            obs.add(g, 'GND', CU); obs.holes.append((x, y, drill / 2)); obs.vias.append((x, y))
            n += 1
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    log('  ground stitching: %d vias' % n)
    return n


def _polys(z, l):
    fp_ = z.GetFilledPolysList(l)
    out = []
    for i in range(fp_.OutlineCount()):
        o = fp_.Outline(i)
        pts = [(mm(o.CPoint(j).x), mm(o.CPoint(j).y)) for j in range(o.PointCount())]
        if len(pts) >= 3:
            out.append(Polygon(pts).buffer(0))
    return out


def stitch_rf(b, nets, via=(0.4, 0.2), pitch=1.0, clearance=0.13, hole_gap=0.25, log=print):
    """Ground vias along both sides of every RF line on F.Cu, about `pitch`
    apart, as close as the top pour allows (its edge is the line's
    coplanar gap away): they tie the pour's fingers between the lines to
    In1 (until 3 Nov no TX or antenna line had a ground via within 0.6 mm,
    sim/rf R7).  A via goes only where it lies wholly in the top ground
    pour, outside every rule area that forbids vias, and clears every other
    net's copper on all layers.  Returns the count."""
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    d, drill = via
    obs = fanout.Obstacles(b, CU)
    top, novia = [], []
    for z in b.Zones():
        if z.GetIsRuleArea():
            if z.GetDoNotAllowVias():
                o = z.Outline().Outline(0)
                novia.append(Polygon([(mm(o.CPoint(j).x), mm(o.CPoint(j).y))
                                      for j in range(o.PointCount())]).buffer(0))
            continue
        if z.GetNetname() == 'GND':
            if z.IsOnLayer(pcbnew.F_Cu):
                top += _polys(z, pcbnew.F_Cu)
            continue
        if z.GetZoneName() in ('GND plane', 'VBAT plane'):
            continue
        for l in CU:
            if z.IsOnLayer(l):
                obs.items[l].extend((g, z.GetNetname()) for g in _polys(z, l))
    obs._index()
    area = unary_union(top).buffer(-d / 2 - 0.02)
    bad = unary_union(novia).buffer(d / 2) if novia else None
    gv = [(mm(v.GetPosition().x), mm(v.GetPosition().y)) for v in b.GetTracks()
          if v.GetClass() == 'PCB_VIA' and v.GetNetname() == 'GND']
    n = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_VIA' or t.GetLayer() != pcbnew.F_Cu or t.GetNetname() not in nets:
            continue
        ax, ay, bx, by = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y)
        L = math.hypot(bx - ax, by - ay)
        if L < 0.3:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        hw = mm(t.GetWidth()) / 2
        k = max(1, int(L / 0.25))
        for i in range(k + 1):
            px, py = ax + ux * L * i / k, ay + uy * L * i / k
            for sgn in (1, -1):
                for off in (0.475, 0.535, 0.615):      # past the line's edge (0.56-0.7 mm from a 0.17 mm line's centre)
                    x, y = px - uy * sgn * (hw + off), py + ux * sgn * (hw + off)
                    if any((x - vx) ** 2 + (y - vy) ** 2 < (pitch * 0.9) ** 2 for vx, vy in gv):
                        break
                    pt = Point(x, y)
                    if not area.contains(pt) or (bad is not None and bad.contains(pt)):
                        continue
                    g = pt.buffer(d / 2, 16)
                    if not obs.hole_room(x, y, drill / 2, hole_gap) or not obs.clear(g, 'GND', CU, clearance):
                        continue
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    v.SetWidth(MM(d)); v.SetDrill(MM(drill))
                    v.SetNet(b.FindNet('GND'))
                    b.Add(v)
                    obs.add(g, 'GND', CU); obs.holes.append((x, y, drill / 2)); obs.vias.append((x, y))
                    gv.append((x, y))
                    n += 1
                    break
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    log('  RF line stitching: %d ground vias' % n)
    return n
