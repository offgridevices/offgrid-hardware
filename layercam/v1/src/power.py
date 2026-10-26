# -*- coding: utf-8 -*-
"""Copper drawn before routing, and every plane pad's via.

  fanout    every SMD pad on a plane net gets its own via into its plane
            (ground: In1 and In4; on the main board 0.9 V and 3.3 V: In3,
            each only where its plane is, layout_main.PLANES), beside the
            pad or shared with a neighbouring pad of the same net, on the
            pad's own side.  The router never routes these nets.
  draw      (main) the camera's MIPI lanes and the USB pair, drawn as
            coupled pairs (pairs.py)

Positions come from the placed pads, so a placement change carries
through.  After print-hub/v1/src/power.py.
"""
import math
import pcbnew
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import pcb

CLR = 0.15                     # fanout clearance: a little over the rules
# a fanout track leaving a fine-pitch pad runs level with its neighbours' ends:
# there it needs only the rules' clearance (a QFN's 0.35 pitch, 0.2 pads)
SEG_CLR = 0.135
WHY = {}                       # debugging: the last reason a spot was refused
import os
DEBUG = [d for d in os.environ.get("FANOUT_DEBUG", "").split(",") if d]


def draw(b):
    if pcb.BOARD == 'usb':
        return draw_usb(b)
    if pcb.BOARD != 'main':
        return set()
    import pairs
    return pairs.draw(b)


def draw_usb(b):
    """The receptacle's two VBUS contacts: each straight down to a via
    behind it, and a bar on B joining the two (the data and CC contacts
    between them leave on F)."""
    va, vb = pcb.pad_at(b, 'J1', 'A4B9'), pcb.pad_at(b, 'J1', 'B4A9')
    yv = va[1] + 1.3
    for (x, y) in (va, vb):
        pcb.track(b, [(x, y), (x, yv)], 0.5, pcbnew.F_Cu, 'VSYS')
        pcb.via(b, x, yv, 'VSYS')
    pcb.track(b, [(min(va[0], vb[0]), yv), (max(va[0], vb[0]), yv)], 0.6, pcbnew.B_Cu, 'VSYS')
    return {('J1', 'A4B9'), ('J1', 'B4A9')}


def _pad_poly(p, layer):
    sh = p.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
    polys = []
    for i in range(sh.OutlineCount()):
        o = sh.Outline(i)
        polys.append(Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())]))
    return unary_union(polys)


def _zone_poly(z):
    o = z.Outline().Outline(0)
    return Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())])


def fanout(b, nets=('GND',), done_pads=(), allowed=None, via=None, inward=(), refs=None):
    """A via for every SMD pad on `nets`.  allowed: net -> polygon the via
    must lie in (a plane's extent).  Returns (count, pads with no spot)."""
    via = via or pcb.VIA
    vr = via[0] / 2
    pads, holes = {'F': [], 'B': []}, []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for side, lay in (('F', pcbnew.F_Cu), ('B', pcbnew.B_Cu)):
                if p.IsOnLayer(lay) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    pads[side].append((fp, p, _pad_poly(p, lay)))
            if p.GetDrillSize().x > 0:
                holes.append(Point(pcb.xy(p.GetPosition())).buffer(p.GetDrillSize().x / 2e6))
    edge = pcb.board_polygon().buffer(-(0.3 + vr))
    keep = [_zone_poly(z) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()
            and z.GetZoneName() != 'edge clearance']
    crts = {'F': {}, 'B': {}}
    for fp in b.GetFootprints():
        for side, lay in (('F', pcbnew.F_CrtYd), ('B', pcbnew.B_CrtYd)):
            c = fp.GetCourtyard(lay)
            if c.OutlineCount():
                o = c.Outline(0)
                crts[side][fp.GetReference()] = Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())])
    vias, tracks = [], {'F': [], 'B': []}
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            vias.append((Point(pcb.xy(t.GetPosition())), t.GetNetname(), t.GetWidth(pcbnew.F_Cu) / 2e6))
        else:
            g = LineString([pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())]).buffer(t.GetWidth() / 2e6)
            if t.GetLayer() == pcbnew.F_Cu:
                tracks['F'].append((g, t.GetNetname()))
            elif t.GetLayer() == pcbnew.B_Cu:
                tracks['B'].append((g, t.GetNetname()))
            else:
                # inner tracks block vias of other nets (a via is on every layer)
                tracks.setdefault('in', []).append((g, t.GetNetname()))
    inner = tracks.get('in', [])

    def clear(pt, seg, net, ref, side, strict):
        v = Point(pt).buffer(vr)
        if not edge.contains(Point(pt)) or any(k.intersects(v) for k in keep):
            WHY[ref] = 'edge/keepout'; return False
        if allowed and net in allowed and not allowed[net].contains(Point(pt).buffer(vr + 0.1)):
            WHY[ref] = 'outside its plane'; return False
        if any(h.distance(v) < 0.25 for h in holes):
            WHY[ref] = 'hole'; return False
        for s in ('F', 'B'):
            for fp2, p2, poly in pads[s]:
                if p2.GetNetname() != net and (poly.distance(v) < CLR or (s == side and poly.distance(seg) < SEG_CLR)):
                    WHY[ref] = 'pad %s.%s' % (fp2.GetReference(), p2.GetNumber()); return False
            for g, n in tracks[s]:
                if n != net and (g.distance(v) < CLR or (s == side and g.distance(seg) < SEG_CLR)):
                    WHY[ref] = 'track ' + n; return False
        for g, n in inner:
            if n != net and g.distance(v) < CLR:
                WHY[ref] = 'inner track ' + n; return False
        for g, n, r in vias:
            if g.distance(Point(pt)) < vr + r + max(CLR, 0.25 if n == net else CLR):
                WHY[ref] = 'via ' + n; return False
        # a via may pass under a part on the other face (it is filled and
        # capped, and that face's pads are checked above); not under one on
        # its own face
        for s in (side,):
            for r, c in crts[s].items():
                if r == ref:
                    continue
                if strict and c.intersects(v):
                    WHY[ref] = 'courtyard ' + r; return False
                if not strict and c.buffer(-0.15).contains(Point(pt)):
                    WHY[ref] = 'inside courtyard ' + r; return False
        return True

    failed = []
    done = 0
    for side in ('F', 'B'):
        lay = pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu
        for fp, p, poly in pads[side]:
            net = p.GetNetname()
            if net not in nets or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if (fp.GetReference(), p.GetNumber()) in done_pads:
                continue
            if refs is not None and fp.GetReference() not in refs:
                continue
            cx, cy = poly.centroid.x, poly.centroid.y
            # a pad that already touches a via of its net needs none
            if any(n == net and g.distance(poly) < 0.01 for g, n, r in vias):
                continue
            fx, fy = pcb.xy(fp.GetPosition())
            away = math.atan2(cy - fy, cx - fx) if (abs(cx - fx) + abs(cy - fy)) > 0.05 else -math.pi / 2
            # a long pad (a QFN's, a connector's) leaves along its length,
            # away from its part: straight out between its neighbours
            bw, bh = poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1]
            if bh > 1.5 * bw:
                away = math.pi / 2 if cy > fy else -math.pi / 2
            elif bw > 1.5 * bh:
                away = 0.0 if cx > fx else math.pi
            if (fp.GetReference(), net) in inward:
                away += math.pi
            angs = sorted((away + k * math.pi / 8 for k in range(16)),
                          key=lambda a: abs(math.atan2(math.sin(a - away), math.cos(a - away))))
            w = min(0.3, poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
            spot = None
            first = None
            for strict in (True, False):
                for a in angs:
                    ray = LineString([(cx, cy), (cx + 10 * math.cos(a), cy + 10 * math.sin(a))])
                    hit = ray.intersection(poly.exterior)
                    r0 = Point(cx, cy).distance(hit) if not hit.is_empty else 0.3
                    for extra in (0.05, 0.15, 0.3, 0.5, 0.8, 1.2, 1.6, 2.0):
                        r = r0 + vr + extra
                        pt = (cx + r * math.cos(a), cy + r * math.sin(a))
                        seg = LineString([(cx, cy), pt]).buffer(w / 2)
                        seg_out = seg.difference(poly.buffer(0.01))
                        if clear(pt, seg_out if not seg_out.is_empty else Point(pt), net, fp.GetReference(), side,
                                 strict):
                            spot = pt
                            break
                        if DEBUG and '%s.%s' % (fp.GetReference(), p.GetNumber()) in DEBUG:
                            print('   ', fp.GetReference(), p.GetNumber(), strict, round(math.degrees(a)), extra,
                                  [round(v, 2) for v in pt], WHY.get(fp.GetReference()))
                        if first is None or (not strict and a == angs[0] and extra == 0.8):
                            first = WHY.get(fp.GetReference())
                    if spot:
                        break
                if spot:
                    break
            if not spot:
                # last resort: a short track on the pad's own face to a
                # nearby via of the same net
                for g, n, r in sorted(vias, key=lambda v: v[0].distance(poly)):
                    if n != net or g.distance(poly) > 2.0:
                        continue
                    line = LineString([(cx, cy), (g.x, g.y)])
                    seg = line.buffer(w / 2)
                    if all(p2.GetNetname() == net or poly2.distance(seg) >= SEG_CLR for _, p2, poly2 in pads[side]) \
                            and all(n2 == net or g2.distance(seg) >= SEG_CLR for g2, n2 in tracks[side]) \
                            and all(n2 == net or g2.distance(line) >= r2 + w / 2 + CLR for g2, n2, r2 in vias):
                        pcb.track(b, [(cx, cy), (g.x, g.y)], w, lay, net)
                        tracks[side].append((seg, net))
                        spot = True
                        break
                if spot:
                    done += 1
                    continue
                failed.append('%s.%s(%s)' % (fp.GetReference(), p.GetNumber(), first or '?'))
                continue
            pcb.track(b, [(cx, cy), spot], w, lay, net)
            pcb.via(b, spot[0], spot[1], net, d=via[0], drill=via[1])
            vias.append((Point(spot), net, vr))
            tracks[side].append((LineString([(cx, cy), spot]).buffer(w / 2), net))
            done += 1
    return done, failed
