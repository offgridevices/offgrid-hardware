# -*- coding: utf-8 -*-
"""Ground fill on the routed board's free copper, and stitching vias.

Main board: ground on F, In2 and B wherever nothing else is (In1 and In4
are whole ground planes already); a via every 2 mm wherever F and B are
both ground ties all the ground copper together and keeps every return
path short.  USB board: ground on both layers, stitched the same way.
The LED ring has no ground net and gets no fill.
"""
import pcbnew
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
import pcb

PITCH = {'main': 2.0, 'usb': 2.0}


def _filled(z, layer):
    sh = z.GetFilledPolysList(layer)
    polys = []
    for i in range(sh.OutlineCount()):
        o = sh.Outline(i)
        holes = [[pcb.xy(sh.Hole(i, h).CPoint(k)) for k in range(sh.Hole(i, h).PointCount())]
                 for h in range(sh.HoleCount(i))]
        polys.append(Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())], holes))
    return unary_union(polys) if polys else Polygon()


def pour_and_stitch(path, art=()):
    """art: (x0, y0, x1, y1) boxes kept free of stitching vias (silkscreen
    artwork: ink over a via is clipped)."""
    if pcb.BOARD == 'ring':
        return 0
    b = pcbnew.LoadBoard(path)
    x0, y0, x1, y1 = pcb.board_polygon().bounds
    full = pcb.rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
    layers = [pcbnew.F_Cu, pcbnew.B_Cu] + ([pcbnew.In2_Cu] if pcb.LAYERS == 6 else [])
    zs = {}
    for l in layers:
        z = pcb.zone(b, 'GND', l, full, clearance=pcb.CLEAR + 0.05, name='GND fill', priority=0)
        # reflowed board: SMD pads solid into the fill, plated holes on spokes
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        zs[l] = z
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    r = pcb.VIA[0] / 2
    edge = pcb.board_polygon().buffer(-0.6)
    both = _filled(zs[pcbnew.F_Cu], pcbnew.F_Cu).intersection(_filled(zs[pcbnew.B_Cu], pcbnew.B_Cu)) \
        .buffer(-(r + pcb.CLEAR + 0.1))
    keep = [Polygon([pcb.xy(z.Outline().Outline(0).CPoint(k)) for k in range(z.Outline().Outline(0).PointCount())])
            for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() != 'edge clearance']
    keep = unary_union(keep).buffer(0.3) if keep else Polygon()
    vias = [Point(pcb.xy(t.GetPosition())) for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    holes = [Point(pcb.xy(p.GetPosition())).buffer(p.GetDrillSize().x / 2e6 + 0.5)
             for fp in b.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    arts = [box(*a).buffer(0.6) for a in art]
    n = 0
    step = PITCH[pcb.BOARD]
    y = y0 + 1.0
    while y < y1 - 0.5:
        x = x0 + 1.0
        while x < x1 - 0.5:
            q = Point(x, y)
            if both.contains(q) and edge.contains(q) and not keep.contains(q) and not any(a.contains(q) for a in arts) \
                    and all(v.distance(q) > 1.2 for v in vias) and not any(h.contains(q) for h in holes):
                pcb.via(b, x, y, 'GND')
                vias.append(q)
                n += 1
            x += step
        y += step
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    return n
