# -*- coding: utf-8 -*-
"""Place the small parts (R, C, beads) next to the pins they serve.

Each small part has an anchor: the pad of the IC or connector it belongs
to (layout_*.ANCHOR, or else the first pad of a larger part on its signal
net).  It goes on the side its anchor says (layout_*.SIDE, or else the
anchor's side), at the free spot nearest that pad: rings of growing
radius, the direction pointing away from the anchor part's centre tried
first, both orientations, every courtyard kept CLEAR apart, inside the
board and out of the side's keepouts (layout_*.keepouts).
"""
import math
import pcbnew
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb, parts

SMALL = ('R', 'C', 'L')
CLEAR = 0.15          # courtyard to courtyard, mm


def courtyard(fp, side):
    lay = pcbnew.F_CrtYd if side == 'F' else pcbnew.B_CrtYd
    c = fp.GetCourtyard(lay)
    polys = []
    for i in range(c.OutlineCount()):
        o = c.Outline(i)
        polys.append(Polygon([pcb.xy(o.CPoint(k)) for k in range(o.PointCount())]))
    if not polys:
        bb = fp.GetBoundingBox(False)
        polys = [box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                     bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY)]
    return unary_union(polys)


def is_small(c):
    p = parts.PARTS.get(c.part) or parts.PADS.get(c.part)
    fp = p['fp']
    return c.ref[0] in SMALL and fp.startswith(('Resistor_SMD', 'Capacitor_SMD', 'Inductor_SMD')) \
        and c.part not in ('R39R_1206',)


def place(b, comps, layout, small_height, avoid=None):
    """b: a board with the fixed parts already placed.  Adds and places
    every small part (their footprints already on the board at the origin,
    by pcb.place_components).  Returns the parts it could not place."""
    by_ref = {c.ref: c for c in comps}
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    side_of = {r: ('B' if fps[r].IsFlipped() else 'F') for r in fps}
    small = [c for c in comps if is_small(c) and c.ref not in layout.FIXED]
    fixed = [r for r in fps if r not in {c.ref for c in small}]
    occ = {'F': [], 'B': []}
    for r in fixed:
        fp = fps[r]
        if r.startswith('H'):
            continue                                  # holes: their courtyards are in the keepouts
        occ[side_of[r]].append(courtyard(fp, side_of[r]))
    # vias drawn before placement (the fixed parts' plane vias) block both sides
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            g = Point(pcb.xy(t.GetPosition())).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6 + 0.05)
            occ['F'].append(g); occ['B'].append(g)
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            # drawn tracks (the coupled pairs): no part on top of them
            from shapely.geometry import LineString
            g = LineString([pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())]).buffer(t.GetWidth() / 2e6 + 0.05)
            occ['F' if t.GetLayer() == pcbnew.F_Cu else 'B'].append(g)
    keep = {s: layout.keepouts(s) for s in 'FB'}
    edge = pcb.board_polygon().buffer(-0.35)
    # a pad on a plane net that covers only part of the board (the main
    # board's 0.9 V and 3.3 V share In3) must sit over its own plane, with
    # room for its via beside it
    planes = layout.plane_polys() if hasattr(layout, 'plane_polys') else {}
    planes = {n: g.buffer(-0.6) for n, g in planes.items() if n != 'GND'}
    used = {}                                         # (ref, pad) -> count, to spread caps over pins
    failed = []

    def anchor_pad(c):
        spec = layout.ANCHOR.get(c.note)
        sig = [n for n in c.pins.values() if n and n != 'GND']
        if spec:
            ref, pad = spec
            fp = fps[ref]
            if pad.startswith('*'):
                net = pad[1:] or (sig[0] if sig else None)
                cands = [p for p in fp.Pads() if p.GetNetname() in ([net] if net else sig)]
                cands = cands or list(fp.Pads())
                p = min(cands, key=lambda p: used.get((ref, p.GetNumber()), 0))
            else:
                p = next(p for p in fp.Pads() if p.GetNumber() == pad)
            used[(ref, p.GetNumber())] = used.get((ref, p.GetNumber()), 0) + 1
            return fp, p
        # the first larger part on a signal net
        for net in sig:
            for r, fp in fps.items():
                if r in by_ref and by_ref[r] in small:
                    continue
                for p in fp.Pads():
                    if p.GetNetname() == net:
                        return fp, p
        raise KeyError('no anchor for %s (%s)' % (c.ref, c.note))

    for c in small:
        fp = fps[c.ref]
        afp, apad = anchor_pad(c)
        aside = side_of[afp.GetReference()]
        side = layout.SIDE.get(c.note, aside)
        ax, ay = pcb.xy(apad.GetPosition())
        cx, cy = pcb.xy(afp.GetPosition())
        away = math.atan2(ay - cy, ax - cx) if abs(ax - cx) + abs(ay - cy) > 0.05 else 0.0
        h = small_height(c.part)
        if side != side_of[c.ref]:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            side_of[c.ref] = side
        # the part's own courtyard round its origin, both orientations
        base, ppads = {}, {}
        for rot in (0, 90):
            fp.SetPosition(pcb.P(0, 0)); fp.SetOrientationDegrees(rot)
            base[rot] = courtyard(fp, side)
            ppads[rot] = [(pcb.xy(p.GetPosition()), planes[p.GetNetname()]) for p in fp.Pads()
                          if p.GetNetname() in planes]
        blocked = unary_union(occ[side]).buffer(CLEAR) if occ[side] else Polygon()
        hard = unary_union([g for g, hmax in keep[side] if h > hmax] + (avoid or {}).get(c.ref, []) or [Polygon()])
        region = getattr(layout, 'REGION', {}).get(c.note)
        if region is not None:
            region = region()
        spot = None
        r = 0.0
        while r < 12.0 and not spot:
            n = max(1, int(2 * math.pi * r / 0.3)) if r else 1
            angs = sorted((away + 2 * math.pi * k / n for k in range(n)),
                          key=lambda a: abs(math.atan2(math.sin(a - away), math.cos(a - away))))
            for a in angs:
                x, y = ax + r * math.cos(a), ay + r * math.sin(a)
                for rot in ((0, 90) if abs(math.cos(a)) > 0.7 else (90, 0)):
                    g = affinity.translate(base[rot], x, y)
                    if edge.contains(g) and not g.intersects(blocked) and not g.intersects(hard) \
                            and (region is None or region.contains(g)) \
                            and all(pl.contains(Point(px + x, py + y)) for (px, py), pl in ppads[rot]):
                        spot = (x, y, rot)
                        break
                if spot:
                    break
            r += 0.25
        if not spot:
            failed.append(c.ref)
            continue
        x, y, rot = spot
        fp.SetPosition(pcb.P(x, y)); fp.SetOrientationDegrees(rot)
        occ[side].append(affinity.translate(base[rot], x, y))
        c.side = side
    return failed
