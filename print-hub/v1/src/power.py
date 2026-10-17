# -*- coding: utf-8 -*-
"""The power copper, drawn before routing, and every plane pad's via.

  input     POWER IN's two VBUS contacts -> a bar -> a 9 V pour on F.Cu that
            takes in the TVS, the buck's input capacitors and its IN pins
  CC        each CC contact drops through a via just below the connector
            and goes on to the PD chip on B.Cu (the routers' job)
  LX        the buck's switch node is an inner pad (the octagon between its
            ground pads): it leaves to the left through the 0.75 mm gap
            between them, then a 1.5 mm track to the inductor
  5 V       the inductor's output pad, the four output capacitors and a row
            of vias into In2 (the 5 V plane) share one pour on F.Cu
  fanout    every SMD pad on ground or the 5 V rail gets its own via into
            its plane (In1 ground, In2 5 V): the routers never route these
            two nets, and the pours after routing join the rest

Positions come from the placed pads, so a placement change in layout.py
carries through.
"""
import math
import pcbnew
from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union
import pcb

F, IN1, IN2, BK = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu
VIA_R = pcb.VIA[0] / 2
CLR = 0.2                      # fanout clearance: a little over the 0.15 mm rule

# In2: the 5 V plane (everywhere but the input stage and the logic at the back)
VRAIL_PLANE = [(-pcb.HX + 0.5, -13.2), (-34.0, -13.2), (-34.0, -11.5), (pcb.HX - 0.5, -11.5),
               (pcb.HX - 0.5, pcb.HY - 0.5), (-pcb.HX + 0.5, pcb.HY - 0.5)]


def draw(b):
    pa = lambda ref, n: pcb.pad_at(b, ref, n)
    # ---- input: VBUS stubs, the bar, the 9 V pour
    va, vb = pa('J1', 'A4B9'), pa('J1', 'B4A9')
    bar_y = -23.2
    for (x, y) in (va, vb):
        pcb.track(b, [(x, y), (x, bar_y)], 0.6, F, 'VBUS_IN')
    pcb.track(b, [(min(va[0], vb[0]), bar_y), (max(va[0], vb[0]) + 0.6, bar_y)], 0.8, F, 'VBUS_IN')
    u2 = pcb.xy(b.FindFootprintByReference('U2').GetPosition())
    vin = [(-36.6, bar_y - 0.4), (-30.8, bar_y - 0.4), (-30.8, -15.7), (-35.6, -15.7), (-35.6, -13.3),
           (u2[0] + 1.0, -13.3), (u2[0] + 1.0, -15.7), (-36.6, -15.7)]
    pcb.zone(b, 'VBUS_IN', F, vin, clearance=0.25, thermal=False, priority=2, name='9 V input')
    # ---- CC: a via below each contact, on to B.Cu
    for pad, dx in (('A5', 0.0), ('B5', 0.35)):
        x, y = pa('J1', pad)
        dx = dx if x < -38 else -dx
        pcb.track(b, [(x, y), (x, y + 0.7), (x + dx, y + 1.3)], 0.25, F, b.FindFootprintByReference('J1')
                  .FindPadByNumber(pad).GetNetname())
        pcb.via(b, x + dx, y + 1.3, b.FindFootprintByReference('J1').FindPadByNumber(pad).GetNetname())
    # ---- LX: out of the octagon to the left, then wide to the inductor
    lx = pa('U2', '2')
    ch_y = u2[1] + 0.425                     # the gap between ground pads 1 and 3
    l1 = pa('L1', '1')
    pcb.track(b, [(lx[0], ch_y), (u2[0] - 2.9, ch_y)], 0.4, F, 'BUCK_LX')
    pcb.track(b, [(u2[0] - 2.9, ch_y), (l1[0], l1[1])], 1.5, F, 'BUCK_LX')
    bs = pa('C5', '2')                       # bootstrap capacitor's switch-node end
    pcb.track(b, [bs, (bs[0], ch_y)], 0.4, F, 'BUCK_LX')
    # ground pad 1 (boxed in by the switch node, the bootstrap capacitor
    # and the top pins) takes its via out to the left
    g1 = (u2[0] - 1.5, u2[1] - 0.45)
    gv = (u2[0] - 2.2, u2[1] - 1.0)
    pcb.track(b, [g1, gv], 0.4, F, 'GND')
    pcb.via(b, gv[0], gv[1], 'GND')
    # ILMT (pin 10) to ground: straight up to a via
    i10 = pa('U2', '10')
    pcb.track(b, [i10, (i10[0] - 0.05, i10[1] - 0.95)], 0.25, F, 'GND')
    pcb.via(b, i10[0] - 0.05, i10[1] - 0.95, 'GND')
    # ---- 5 V: the inductor output, the output capacitors, vias into In2
    # (down to the capacitors' 5 V pads: their ground pads stay outside)
    out = pcb.rect(-pcb.HX + 0.4, -17.0, -41.4, -7.9)
    pcb.zone(b, 'VRAIL', F, out, clearance=0.25, thermal=False, priority=2, name='5 V buck output')
    for i in range(7):
        pcb.via(b, -50.6 + i * 1.3, -11.7, 'VRAIL')
    # ---- each port: switch OUT straight down onto the shunt, the shunt's
    # far end to the output capacitor and on to the USB-A's VBUS pin
    for c in b.GetFootprints():
        r = c.GetReference()
        if not (r.startswith('U') and len(r) == 4 and r.endswith('01')):
            continue
        n = r[1]
        out_pad = pa(r, '1')
        sh = 'R%s04' % n                      # the shunt (circuit.py order: ILIM, EN, FLT, shunt)
        assert b.FindFootprintByReference(sh).GetValue() == '20mR', sh
        s1, s2 = pa(sh, '1'), pa(sh, '2')
        cap = 'C%s05' % n                     # port output capacitor
        cp = pa(cap, '1')
        jv = pa('J%s01' % n, '1')
        pcb.track(b, [out_pad, (out_pad[0], out_pad[1] + 0.5), s1], 0.5, F, 'PORT%s_SW' % n)
        mid = (s2[0], cp[1])
        pcb.track(b, [s2, mid, cp], 0.8, F, 'VBUS%s' % n)
        pcb.track(b, [cp, jv], 0.8, F, 'VBUS%s' % n)
    return {('U2', '1'), ('U2', '10')}      # pads joined here: the fanout leaves them


def _pad_poly(p, layer=F):
    sh = p.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
    polys = []
    for i in range(sh.OutlineCount()):
        o = sh.Outline(i)
        polys.append(Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())]))
    return unary_union(polys)


def _zone_poly(z):
    o = z.Outline().Outline(0)
    return Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())])


def fanout(b, nets=('GND', 'VRAIL'), done_pads=()):
    """A via for every SMD pad on `nets`, beside the pad (or shared with a
    neighbouring pad of the same net), joined by a short track.  Returns
    the pads that found no spot."""
    pads, holes = [], []           # every copper pad on F.Cu (THT included); every drilled hole
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(F) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                pads.append((fp, p, _pad_poly(p)))
            if p.GetDrillSize().x > 0:
                holes.append(Point(pcb.xy(p.GetPosition())).buffer(p.GetDrillSize().x / 2e6))
    edge = pcb.board_polygon().buffer(-(0.3 + VIA_R))
    keep = [_zone_poly(z) for z in b.Zones() if z.GetIsRuleArea()]
    vrail = Polygon(VRAIL_PLANE).buffer(-(VIA_R + 0.3))
    crts = {}
    for fp in b.GetFootprints():
        c = fp.GetCourtyard(F)
        if c.OutlineCount():
            o = c.Outline(0)
            crts[fp.GetReference()] = Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())])
    vias, tracks = [], []                     # (geom, net)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            vias.append((Point(pcb.xy(t.GetPosition())), t.GetNetname()))
        elif t.GetLayer() == F:
            tracks.append((LineString([pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())]).buffer(t.GetWidth() / 2e6),
                           t.GetNetname()))
    zones = [(_zone_poly(z), z.GetNetname()) for z in b.Zones()
             if not z.GetIsRuleArea() and z.GetLayer() == F]

    def clear(pt, seg, net, ref, strict):
        v = Point(pt).buffer(VIA_R)
        if not edge.contains(Point(pt)) or any(k.intersects(v) for k in keep):
            return False
        if any(h.distance(v) < 0.3 for h in holes):
            return False
        if net == 'VRAIL' and not vrail.contains(Point(pt)):
            return False
        for fp2, p2, poly in pads:
            if p2.GetNetname() != net and (poly.distance(v) < CLR or poly.distance(seg) < CLR):
                return False
        for g, n in tracks:
            if n != net and (g.distance(v) < CLR or g.distance(seg) < CLR):
                return False
        for g, n in vias:
            if g.distance(Point(pt)) < 2 * VIA_R + max(CLR, 0.3 if n == net else CLR):
                return False
        if strict:
            for r, c in crts.items():
                if r != ref and c.intersects(v):
                    return False
        if (not strict) and any(r != ref and c.buffer(-0.2).contains(Point(pt)) for r, c in crts.items()):
            return False
        return True

    failed = []
    done = 0
    for fp, p, poly in pads:
        net = p.GetNetname()
        if net not in nets or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        if (fp.GetReference(), p.GetNumber()) in done_pads:
            continue
        if any(g.intersects(poly) and n == net for g, n in zones):
            continue                          # in its own net's pour already
        cx, cy = poly.centroid.x, poly.centroid.y
        fx, fy = pcb.xy(fp.GetPosition())
        away = math.atan2(cy - fy, cx - fx) if (abs(cx - fx) + abs(cy - fy)) > 0.05 else -math.pi / 2
        angs = sorted((away + k * math.pi / 8 for k in range(16)),
                      key=lambda a: abs(math.atan2(math.sin(a - away), math.cos(a - away))))
        w = min(0.4, poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
        spot = None
        for strict in (True, False):
            for a in angs:
                # distance from the centre to the pad's edge along a, then out
                ray = LineString([(cx, cy), (cx + 10 * math.cos(a), cy + 10 * math.sin(a))])
                hit = ray.intersection(poly.exterior)
                r0 = Point(cx, cy).distance(hit) if not hit.is_empty else 0.3
                for extra in (0.1, 0.3, 0.5, 0.8, 1.2):
                    r = r0 + VIA_R + extra
                    pt = (cx + r * math.cos(a), cy + r * math.sin(a))
                    seg = LineString([(cx, cy), pt]).buffer(w / 2)
                    seg_out = seg.difference(poly.buffer(0.01))
                    if clear(pt, seg_out if not seg_out.is_empty else Point(pt), net, fp.GetReference(), strict):
                        spot = pt
                        break
                if spot:
                    break
            if spot:
                break
        if not spot:
            failed.append('%s.%s' % (fp.GetReference(), p.GetNumber()))
            continue
        pcb.track(b, [(cx, cy), spot], w, F, net)
        pcb.via(b, spot[0], spot[1], net)
        vias.append((Point(spot), net))
        tracks.append((LineString([(cx, cy), spot]).buffer(w / 2), net))
        done += 1
    return done, failed
