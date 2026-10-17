# -*- coding: utf-8 -*-
"""Ground fill on the outer layers after routing, and stitching vias.

The fills on F.Cu and B.Cu take every bit of free copper; a via every few
millimetres wherever both fills and the In1 plane are ground ties them
together, so no fill is an island and every return path is short.
"""
import pcbnew
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import pcb

F, BK = pcbnew.F_Cu, pcbnew.B_Cu
PITCH = 3.0          # stitching grid, mm


def _filled(z, layer):
    sh = z.GetFilledPolysList(layer)
    polys = []
    for i in range(sh.OutlineCount()):
        o = sh.Outline(i)
        holes = [[pcb.xy(sh.Hole(i, h).CPoint(k)) for k in range(sh.Hole(i, h).PointCount())]
                 for h in range(sh.HoleCount(i))]
        polys.append(Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())], holes))
    return unary_union(polys) if polys else Polygon()


def pour_and_stitch(path):
    b = pcbnew.LoadBoard(path)
    e = 0.5
    full = pcb.rect(-pcb.HX + e, -pcb.HY + e, pcb.HX - e, pcb.HY - e)
    zs = []
    for l in (F, BK):
        z = pcb.zone(b, 'GND', l, full, clearance=0.25, name='GND fill', priority=0)
        # reflowed board: SMD pads solid into the fill, plated holes on spokes
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        zs.append(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # where both outer fills are ground, a stitching via (kept clear of
    # every other via, and of the antenna keepout: that has no copper)
    both = _filled(zs[0], F).intersection(_filled(zs[1], BK)).buffer(-(pcb.VIA[0] / 2 + 0.25))
    keep = unary_union([Polygon([pcb.xy(z.Outline().Outline(0).CPoint(k))
                                 for k in range(z.Outline().Outline(0).PointCount())])
                        for z in b.Zones() if z.GetIsRuleArea()]).buffer(0.5)
    vias = [Point(pcb.xy(t.GetPosition())) for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    holes = [Point(pcb.xy(p.GetPosition())).buffer(p.GetDrillSize().x / 2e6 + 0.5)
             for fp in b.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    n = 0
    y = -pcb.HY + 1.5
    while y < pcb.HY - 1.0:
        x = -pcb.HX + 1.5
        while x < pcb.HX - 1.0:
            q = Point(x, y)
            if both.contains(q) and not keep.contains(q) and all(v.distance(q) > 1.5 for v in vias) \
                    and not any(h.contains(q) for h in holes):
                pcb.via(b, x, y, 'GND')
                vias.append(q)
                n += 1
            x += PITCH
        y += PITCH
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(path)
    return n
