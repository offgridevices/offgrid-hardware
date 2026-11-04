# -*- coding: utf-8 -*-
"""Place the small parts (R, C, beads) next to the pins they serve.

First in rows: the small parts that serve one edge of a part on their own
face go in a straight row along that edge, each turned the same way (its
pads in line with the pin it serves), evenly spaced (ROW_PITCH steps), in
the order of their pins, on the GRID; a second and third row behind when
the first is full.  A board laid out like this reads as ordered, not as a
scatter of parts.  What does not fit a row (or must sit in a region, or on
the other face) is placed as below, on the same grid.

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
GRID = 0.25           # every small part's centre on this grid, mm
ROW_GAP = 0.35        # the anchor's courtyard to the first row, and row to row, mm
ROW_PITCH = 0.25      # rows' spacings are whole multiples of this
REACH = 2.0           # a row part sits at most this many pitches along the row from its pin


def snap(v, g=GRID):
    return round(round(v / g) * g, 4)


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
        and c.part not in ('R47R_1206',)


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

    # ------------------------------------------------------------- rows
    anchors = {c.ref: anchor_pad(c) for c in small}
    groups, rest = {}, []
    for c in small:
        afp, apad = anchors[c.ref]
        aside = side_of[afp.GetReference()]
        side = layout.SIDE.get(c.note, aside)
        if side != aside or getattr(layout, 'REGION', {}).get(c.note) is not None \
                or c.ref in getattr(layout, 'NO_ROW', ()):
            rest.append(c)
            continue
        bb = courtyard(afp, aside).bounds
        acx, acy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        px, py = pcb.xy(apad.GetPosition())
        # the edge the pin is on: the larger of its offsets, over the part's half-size
        hx, hy = max((bb[2] - bb[0]) / 2, 0.1), max((bb[3] - bb[1]) / 2, 0.1)
        if abs(px - acx) / hx >= abs(py - acy) / hy:
            n = (1 if px > acx else -1, 0)
        else:
            n = (0, 1 if py > acy else -1)
        groups.setdefault((afp.GetReference(), side, n), []).append((c, px, py, bb))

    def legal(fp, side, rot, x, y, c, blocked, hard):
        fp.SetPosition(pcb.P(0, 0)); fp.SetOrientationDegrees(rot)
        g = affinity.translate(courtyard(fp, side), x, y)
        if not edge.contains(g) or g.intersects(blocked) or g.intersects(hard):
            return None
        for p in fp.Pads():
            if p.GetNetname() in planes:
                qx, qy = pcb.xy(p.GetPosition())
                if not planes[p.GetNetname()].contains(Point(qx + x, qy + y)):
                    return None
        return g

    def facing(c, rot, n):
        """rot, or rot + 180 when that turns the part's pad on its anchor's
        net towards the anchor (a series resistor's chip end at the chip)."""
        fp = fps[c.ref]
        net = anchors[c.ref][1].GetNetname()
        fp.SetPosition(pcb.P(0, 0)); fp.SetOrientationDegrees(rot)
        ps = [pcb.xy(p.GetPosition()) for p in fp.Pads() if p.GetNetname() == net]
        if not ps:
            return rot
        d = sum(px * n[0] + py * n[1] for px, py in ps) / len(ps)
        return (rot + 180) % 360 if d > 1e-6 else rot

    def power(net):
        return net == 'GND' or net in planes or net.startswith(('VCC', 'VSYS', 'VBUS', 'VDD', 'VWIFI'))

    def rank(c):
        """Who chooses a row place first: decoupling capacitors (0), then
        series parts on a signal (1: a termination resistor belongs at the
        pin that drives it), then the rest (pull-ups, supply resistors)."""
        if c.ref.startswith('C'):
            return 0
        nets = [x for x in c.pins.values() if x]
        return 1 if nets and not any(power(x) for x in nets) else 2

    for (aref, side, n), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        rot0 = 0 if n[1] == 0 else 90         # pads in line with the pin: the part's length along n
        tang = (lambda px, py: py) if n[1] == 0 else (lambda px, py: px)
        items.sort(key=lambda it: tang(it[1], it[2]))
        bb = items[0][3]
        # the parts' size along the row and across it, at this orientation
        dims = []
        for c, px, py, _ in items:
            fp = fps[c.ref]
            if side != side_of[c.ref]:
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                side_of[c.ref] = side
            fp.SetPosition(pcb.P(0, 0)); fp.SetOrientationDegrees(rot0)
            g = courtyard(fp, side).bounds
            along_n = (g[2] - g[0]) if n[1] == 0 else (g[3] - g[1])
            across = (g[3] - g[1]) if n[1] == 0 else (g[2] - g[0])
            dims.append((along_n, across))
        depth = max(d[0] for d in dims)
        # a part's width apart, plus the anchor's routing channel (the SoC's
        # pins run out between its rows' parts: layout.ROW_CHANNEL)
        chan = getattr(layout, 'ROW_CHANNEL', {}).get(aref, 0.0)
        pitch = math.ceil((max(d[1] for d in dims) + CLEAR + chan) / ROW_PITCH) * ROW_PITCH
        edge_n = bb[2] if n == (1, 0) else bb[0] if n == (-1, 0) else bb[3] if n == (0, 1) else bb[1]
        left = list(items)
        for k in range(3):
            if not left:
                break
            off = edge_n + n[0] * (ROW_GAP + depth / 2 + k * (depth + ROW_GAP)) + n[1] * (
                ROW_GAP + depth / 2 + k * (depth + ROW_GAP))
            off = snap(off)
            # each part at its own pin if that is free, else the nearest free
            # place along the row within REACH pitches (a channel apart from
            # the row's other parts); the decoupling capacitors choose first,
            # then the rest in pin order.  What finds no place within reach
            # goes to the next row out, never far along this one: a part
            # pushed along a crowded row ends up away from its pin.
            nxt = []
            blocked = unary_union(occ[side]).buffer(CLEAR) if occ[side] else Polygon()
            order = sorted(left, key=lambda it: (rank(it[0]), tang(it[1], it[2])))
            steps = int(round(REACH * pitch / GRID))
            for c, px, py, bb_ in order:
                fp = fps[c.ref]
                rot = facing(c, rot0, n)
                hard = unary_union([g for g, hmax in keep[side] if small_height(c.part) > hmax]
                                   + (avoid or {}).get(c.ref, []) or [Polygon()])
                t0 = snap(tang(px, py))
                spot = None
                for dt in [0] + [s_ * j * GRID for j in range(1, steps + 1) for s_ in (1, -1)]:
                    t = t0 + dt
                    x, y = (off, t) if n[1] == 0 else (t, off)
                    g = legal(fp, side, rot, x, y, c, blocked, hard)
                    if g is not None:
                        spot = (x, y, g)
                        break
                if spot is None:
                    nxt.append((c, px, py, bb_))
                    continue
                x, y, g = spot
                fp.SetPosition(pcb.P(x, y)); fp.SetOrientationDegrees(rot)
                occ[side].append(g)
                blocked = blocked.union(g.buffer(CLEAR + chan))
                c.side = side
            nxt.sort(key=lambda it: tang(it[1], it[2]))
            left = nxt
        rest.extend(c for c, *_ in left)

    # ------------------------------------------------------------- the rest
    # the parts held to a region first (the 0.9 V strip, the core band:
    # tight, and theirs), then the others round them
    regions = getattr(layout, 'REGION', {})
    rest.sort(key=lambda c: (regions.get(c.note) is None, [x.ref for x in small].index(c.ref)))
    for c in rest:
        fp = fps[c.ref]
        afp, apad = anchors[c.ref]
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
        anet = apad.GetNetname()
        apads = {}
        for rot in (0, 90, 180, 270):
            fp.SetPosition(pcb.P(0, 0)); fp.SetOrientationDegrees(rot)
            base[rot] = courtyard(fp, side)
            ppads[rot] = [(pcb.xy(p.GetPosition()), planes[p.GetNetname()]) for p in fp.Pads()
                          if p.GetNetname() in planes]
            apads[rot] = [pcb.xy(p.GetPosition()) for p in fp.Pads() if p.GetNetname() == anet]

        def turns(r0, x, y):
            # the axis r0, its pad on the anchor's net nearest the anchor first
            def d(r):
                return min((math.hypot(x + px - ax, y + py - ay) for px, py in apads[r]), default=0.0)
            return sorted((r0, r0 + 180), key=d)
        blocked = unary_union(occ[side]).buffer(CLEAR) if occ[side] else Polygon()
        hard = unary_union([g for g, hmax in keep[side] if h > hmax] + (avoid or {}).get(c.ref, []) or [Polygon()])
        region = getattr(layout, 'REGION', {}).get(c.note)
        if region is not None:
            region = region()
        spot = None
        # on the grid first; off it only where the grid leaves no room (a
        # tight region: the 0.9 V strip, the core band)
        for g_ in (GRID, None):
          r = 0.0
          while r < 20.0 and not spot:
            n = max(1, int(2 * math.pi * r / 0.3)) if r else 1
            angs = sorted((away + 2 * math.pi * k / n for k in range(n)),
                          key=lambda a: abs(math.atan2(math.sin(a - away), math.cos(a - away))))
            for a in angs:
                x, y = ax + r * math.cos(a), ay + r * math.sin(a)
                if g_:
                    x, y = snap(x, g_), snap(y, g_)
                for rot in [r for r0 in ((0, 90) if abs(math.cos(a)) > 0.7 else (90, 0))
                            for r in turns(r0, x, y)]:
                    g = affinity.translate(base[rot], x, y)
                    if edge.contains(g) and not g.intersects(blocked) and not g.intersects(hard) \
                            and (region is None or region.contains(g)) \
                            and all(pl.contains(Point(px + x, py + y)) for (px, py), pl in ppads[rot]):
                        spot = (x, y, rot)
                        break
                if spot:
                    break
            r += 0.25
          if spot:
            break
        if not spot:
            failed.append(c.ref)
            continue
        x, y, rot = spot
        fp.SetPosition(pcb.P(x, y)); fp.SetOrientationDegrees(rot)
        occ[side].append(affinity.translate(base[rot], x, y))
        c.side = side
    # (the parts held to a region stay where the region put them)
    align(b, [c for c in small if c.ref not in failed and getattr(layout, 'REGION', {}).get(c.note) is None],
          fps, side_of, occ, keep, edge, planes, small_height, avoid)
    return failed


ALIGN = 0.6           # parts whose centres are this close across a line are put on one line, mm


def align(b, small, fps, side_of, occ, keep, edge, planes, small_height, avoid):
    """Guides: on each face, small parts whose centres nearly share an x (or
    a y) are moved onto the one line (the group's most common value), each
    move kept only if the part stays legal.  Rows from different groups
    then meet on common lines, as a designer's guides would put them."""
    by_side = {'F': [], 'B': []}
    for c in small:
        by_side[side_of[c.ref]].append(c)
    for side, cs in by_side.items():
        for axis in (0, 1):
            for _ in range(2):
                pos = {c.ref: pcb.xy(fps[c.ref].GetPosition()) for c in cs}
                order = sorted(cs, key=lambda c: pos[c.ref][axis])
                groups, cur = [], []
                for c in order:
                    if cur and pos[c.ref][axis] - pos[cur[0].ref][axis] > ALIGN:
                        groups.append(cur); cur = []
                    cur.append(c)
                if cur:
                    groups.append(cur)
                for grp in groups:
                    vals = [round(pos[c.ref][axis], 3) for c in grp]
                    if len(grp) < 2 or max(vals) - min(vals) < 1e-3:
                        continue
                    target = max(set(vals), key=lambda v: (vals.count(v), -abs(v - sum(vals) / len(vals))))
                    for c in grp:
                        x, y = pos[c.ref]
                        nx, ny = (target, y) if axis == 0 else (x, target)
                        if abs(nx - x) + abs(ny - y) < 1e-4:
                            continue
                        fp = fps[c.ref]
                        rot = fp.GetOrientationDegrees()
                        fp.SetPosition(pcb.P(0, 0))
                        base = courtyard(fp, side)
                        mine = affinity.translate(base, x, y)
                        others = [g for g in occ[side] if not g.equals(mine)]
                        g = affinity.translate(base, nx, ny)
                        hard = unary_union([k for k, hmax in keep[side] if small_height(c.part) > hmax]
                                           + (avoid or {}).get(c.ref, []) or [Polygon()])
                        ok = edge.contains(g) and not g.intersects(hard) and \
                            not any(g.distance(o) < CLEAR for o in others)
                        if ok:
                            for p in fp.Pads():
                                if p.GetNetname() in planes:
                                    qx, qy = pcb.xy(p.GetPosition())
                                    if not planes[p.GetNetname()].contains(Point(qx + nx, qy + ny)):
                                        ok = False
                        if ok:
                            occ[side] = others + [g]
                            fp.SetPosition(pcb.P(nx, ny))
                        else:
                            fp.SetPosition(pcb.P(x, y))
                        fp.SetOrientationDegrees(rot)
