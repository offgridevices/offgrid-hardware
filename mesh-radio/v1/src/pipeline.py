# -*- coding: utf-8 -*-
"""Route and finish the placed board, to a DRC-clean .kicad_pcb.

  1. board.build()          parts, the RF lines (locked), the ground plane (In1), rules
  2. plane_fanout()         every ground pad takes its via into the planes; every
                            inner ball of a ball-grid chip its via in the ball
  3. Freerouting            every other signal and supply (rounds)
  4. finish (finish.py)     the maze router and rip-up repair for what is left
  5. ground poured on the routing layers, stitched to the planes; the RF lines keep
     their 0.25 mm coplanar gap to it (board.RULES)
  6. KiCad DRC              must be 0 errors / 0 warnings / 0 unconnected

    kd python3 src/pipeline.py WORKDIR [--passes N] [--from-routed]

Adapted from Ridge 3 Lite's pipeline: a solid ground plane on In1, routing
on the five other layers (ground-filled after), and the RF lines kept clear
of other copper.
"""
import os, sys, shutil
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, route, finish, board, circuit

PLANES = ['GND']
EDGE = 0.3                      # mm of bare board along the outline (board setup's edge clearance)


def log(s):
    print(s, flush=True)


def plane_fanout(path):
    """Every ground pad gets its via into the planes before routing (Freerouting
    routes pad to pad; it does not drop a pad into a plane): in the pad
    itself where it is wide enough (filled and capped, POFV), otherwise just
    outside it on a stub; exposed pads get a grid."""
    import fanout
    b = pcbnew.LoadBoard(path)
    if ROUTE_IN1:
        rf_reference_keepouts(b)
    ball_escapes(b)
    outer_escapes(b)
    join_pads(b)
    # no via within POFV's 0.45 mm of a part's drilled hole (the plug pegs,
    # the header pins): a ring round each, for the fan-out only
    tmp = []
    rv = board.VIA_SIG[1] / 2
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            q = p.GetPosition()
            r = max(p.GetDrillSize().x, p.GetDrillSize().y) / 2e6 + 0.46 + rv - board.VIA_SIG[0] / 2
            tmp.append(pcb.rule_area(b, pcb.circle_poly(q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, r), board.CU,
                                     tracks=False, vias=True, pads=False, pours=False, name='hole ring'))
    ex, ey = pcb.HX - 0.45, pcb.HY - 0.45
    inpad = dict(d=board.VIA_SIG[0], drill=board.VIA_SIG[1], cl=0.13, hole_cl=0.2, hole_gap=0.25, min_pad=0.38)
    n, failed = fanout.fanout(b, set(PLANES), (-ex + pcb.CX, -ey + pcb.CY, ex + pcb.CX, ey + pcb.CY),
                              via_d=board.VIA_SIG[0], via_drill=board.VIA_SIG[1], clearance=0.13,
                              stub_w=0.2, ep_pitch=1.0, share=0.6, inpad=inpad, ep_join=0.2, ep_min_area=0.8)
    for z in tmp:
        pcb.remove(b, z)
    for t in b.GetTracks():
        if t.GetNetname() in PLANES:
            t.SetLocked(True)
    b.Save(path)
    log('plane fan-out: %d vias, %d ground pads with no via of their own %s' % (n, len(failed), failed[:12]))
    return failed


def rf_reference_keepouts(b, margin=0.6, log=log):
    """With In1 routed (ROUTE_IN1): In1 stays solid ground under every RF
    line (the line, its coplanar gap and `margin` beyond), where it is the
    line's reference: rule areas on In1 with no track of any net (vias may
    pierce it), the chips at the lines' ends cut out."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    gl = pcb.layer_id(pcb.INNER['gnd'])
    band = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' or t.GetLayer() != pcbnew.F_Cu:
            continue
        if t.GetNetname() in board.RF_NETS + board.RF_EXTRA:
            s_, e_ = t.GetStart(), t.GetEnd()
            band.append(LineString([(s_.x / 1e6, s_.y / 1e6), (e_.x / 1e6, e_.y / 1e6)])
                        .buffer(t.GetWidth() / 2e6 + board.RF_GAP + margin))
    # not under the chips the lines start and end at: their balls' and
    # paddles' own vias stand there (the nRF52840's DEC3 ball, the LNA's)
    from shapely.geometry import box as _box
    chips = []
    for fp in b.GetFootprints():
        r_ = fp.GetReference()
        if r_[0] == 'U' or r_.startswith('Q'):
            cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
            if cy.OutlineCount():
                bb = cy.BBox()
                chips.append(_box(bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6))
    k = 0
    for q in _simple(unary_union(band).difference(unary_union(chips))):
        if q.area < 0.02:
            continue
        pts = [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
        # tracks only: a track there cuts a slot in the line's return path;
        # a via just pierces it (and the RF parts' ground vias belong there)
        pcb.rule_area(b, pts, [gl], tracks=True, vias=False, pads=False, pours=False, name='RF reference: In1 solid')
        k += 1
    log('RF reference: %d areas on In1 kept solid' % k)
    return k


def join_pads(b, reach=1.6, log=log):
    """A part's neighbouring pads of one supply or signal net (a power
    FET's drain pins, a regulator's paired inputs) joined on their own
    layer before routing, as a designer would: Freerouting left most of
    these clusters unjoined (12 of the 72 gaps after the first round were
    the CSD25310Q2's own BAT_P pins).  For each part and net, a minimum
    spanning tree of its pads, edges up to `reach` mm, each a track as wide
    as the narrower pad (at most the net's class width) that clears every
    other net by 0.12 mm.  Ground (the planes) and RF nets are left out."""
    import fanout
    from shapely.geometry import LineString
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    obs = fanout.Obstacles(b, layers)
    want = {n: board.HEAVY_ROUTE_W for n in board.HEAVY}
    want.update({n: board.POWER_ROUTE_W for n in board.POWER})
    skip = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA)
    n_ = 0
    for fp in b.GetFootprints():
        groups = {}
        for p in fp.Pads():
            net = p.GetNetname()
            if not net or net in skip or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            L = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            groups.setdefault((net, L), []).append(p)
        for (net, L), ps in groups.items():
            if len(ps) < 2:
                continue
            xy = [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6) for p in ps]
            sz = [min(p.GetSize().x, p.GetSize().y) / 1e6 for p in ps]
            # Prim's tree over the pads
            inn, edges = {0}, []
            while len(inn) < len(ps):
                best = min(((i, j) for i in inn for j in range(len(ps)) if j not in inn),
                           key=lambda e: (xy[e[0]][0] - xy[e[1]][0]) ** 2 + (xy[e[0]][1] - xy[e[1]][1]) ** 2)
                inn.add(best[1]); edges.append(best)
            for i, j in edges:
                (x0, y0), (x1, y1) = xy[i], xy[j]
                if (x1 - x0) ** 2 + (y1 - y0) ** 2 > reach ** 2:
                    continue
                w = min(sz[i], sz[j], want.get(net, board.SIG if net != '3V3' else 0.15))
                g = LineString([(x0, y0), (x1, y1)]).buffer(w / 2)
                if not obs.clear(g, net, [L], 0.12):
                    continue
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pcbnew.VECTOR2I(int(x0 * 1e6), int(y0 * 1e6)))
                t.SetEnd(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
                t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(L); t.SetNet(ps[i].GetNet()); t.SetLocked(True)
                b.Add(t)
                obs.add(g, net, [L])
                n_ += 1
    log('pad joins: %d tracks between a part\'s own pads of one net' % n_)
    return n_


def outer_escapes(b, refs=('NRF52840',), log=log):
    """The nRF52840's outer ball ring: a dog-bone each, a short F.Cu stub
    straight out across the clear ring round the chip (layout.NRF_RING) to
    a via, near and far vias alternating so inner-layer tracks from the
    inner balls' vias pass between them.  Freerouting left most of these
    balls unconnected with the ring empty beside them."""
    import fanout
    pins = []
    for fp in b.GetFootprints():
        if not fp.GetValue().startswith(refs):
            continue
        pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
        bbs = [p.GetBoundingBox() for p in pads]
        L_, T_ = min(q.GetLeft() for q in bbs), min(q.GetTop() for q in bbs)
        R_, B_ = max(q.GetRight() for q in bbs), max(q.GetBottom() for q in bbs)
        c = fp.GetPosition()
        for p, bb in zip(pads, bbs):
            net = p.GetNetname()
            if not net or net in PLANES or net in board.RF_NETS + board.RF_EXTRA:
                continue
            if min(bb.GetLeft() - L_, R_ - bb.GetRight(), bb.GetTop() - T_, B_ - bb.GetBottom()) / 1e6 >= 0.05:
                continue
            q = p.GetPosition()
            dx, dy = q.x - c.x, q.y - c.y
            face = ('x', dx > 0) if abs(dx) >= abs(dy) else ('y', dy > 0)
            along = q.y if face[0] == 'x' else q.x
            pins.append((face, along, fp.GetReference(), p.GetNumber()))
    pins.sort()
    n, failed = fanout.dogbones(b, [(r_, num) for _, _, r_, num in pins], via_d=board.VIA_SIG[0],
                                via_drill=board.VIA_SIG[1], width=board.SIG,
                                cl=0.1, hole_gap=0.2)
    log('outer ball escapes: %d dog-bones, %d balls without one %s' % (n, len(failed), failed[:12]))
    return failed


def ball_escapes(b, via=None, clearance=0.1, hole_gap=0.2, log=log):
    """Every inner ball of a ball-grid chip (the nRF52840's inner ring, the
    0.4 mm wafer-scale parts) gets its via in the ball itself: a track
    cannot leave it between the outer balls, and the routers only drop vias
    beside pads.  Board vias of VIA_PAD size (filled and capped; JLCPCB
    fills via-in-pad free on 6 layers), each checked against every other
    net's copper on all layers; ground balls' vias go into the planes.
    Runs before the ground fan-out, whose larger vias would otherwise crowd
    the ball field.  Skipped: exposed pads, and an inner ball beside an
    outer ball of its own net (they join on the surface).  Returns the
    balls left without one."""
    import fanout
    from shapely.geometry import Point
    d, drill = via or board.VIA_PAD
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    obs = fanout.Obstacles(b, layers)
    left, n = [], 0
    for fp in b.GetFootprints():
        if fp.GetReference()[0] != 'U' and not fp.GetReference().startswith('Q'):
            continue
        pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
        if len(pads) < 4:
            continue
        bbs = [p.GetBoundingBox() for p in pads]
        L_, T_ = min(q.GetLeft() for q in bbs), min(q.GetTop() for q in bbs)
        R_, B_ = max(q.GetRight() for q in bbs), max(q.GetBottom() for q in bbs)
        side = pcbnew.F_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Cu
        # a wafer-scale part (every pad a small round ball; not the nRF52840,
        # whose outer ring has its dog-bones): its outer supply balls get a
        # via too (the TPS63810's VPA balls and the TPS22950's BAT_P were left
        # unreachable after routing: 1 Nov); every via's hole keeps 0.2 mm
        # from other nets' copper (vias in neighbouring 0.4 mm balls did not)
        wafer = not fp.GetValue().startswith('NRF52840') and all(
            q.GetWidth() / 1e6 <= 0.36 and q.GetHeight() / 1e6 <= 0.36
            and abs(q.GetWidth() - q.GetHeight()) / 1e6 < 0.06 for q in bbs)
        for p, bb in zip(pads, bbs):
            net = p.GetNetname()
            if not net or net in board.RF_NETS + board.RF_EXTRA:
                continue
            w, h = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
            if w * h > 0.8:                     # an exposed pad
                continue
            edge = min(bb.GetLeft() - L_, R_ - bb.GetRight(), bb.GetTop() - T_, B_ - bb.GetBottom()) / 1e6
            outer = edge < 0.05
            if outer and not (wafer and net in SUPPLY):
                continue                        # outer row: leaves on its own layer
            q = p.GetPosition()
            twin = [o for o, ob in zip(pads, bbs) if o is not p and o.GetNetname() == net
                    and min(ob.GetLeft() - L_, R_ - ob.GetRight(), ob.GetTop() - T_, B_ - ob.GetBottom()) / 1e6 < 0.05
                    and (o.GetPosition() - q).EuclideanNorm() / 1e6 < 0.6]
            if twin and not outer:              # joins its outer neighbour on the surface
                continue
            x, y = q.x / 1e6, q.y / 1e6
            g = Point(x, y).buffer(d / 2, 16)
            # and its hole keeps the fab's 0.2 mm from every other net's copper
            ok = (obs.hole_room(x, y, drill / 2, hole_gap) and obs.clear(g, net, layers, clearance)
                  and obs.clear(Point(x, y).buffer(drill / 2, 16), net, layers, 0.2))
            if not ok:
                left.append((fp.GetReference(), p.GetNumber(), net)); continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(q); v.SetWidth(pcbnew.FromMM(d)); v.SetDrill(pcbnew.FromMM(drill))
            v.SetNet(p.GetNet()); v.SetLocked(True)
            b.Add(v)
            obs.add(g, net, layers); obs.holes.append((x, y, drill / 2))
            n += 1
    log('ball escapes: %d vias in inner balls, %d balls without one %s' % (n, len(left), left[:12]))
    return left


def fill(path):
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(path)


def _simple(g):
    """Polygons with holes split into polygons without (a DSN keepout is a
    plain outline)."""
    from shapely.geometry import Polygon, LineString
    from shapely.ops import split
    out = []
    todo = [q for q in getattr(g, 'geoms', [g]) if isinstance(q, Polygon) and not q.is_empty]
    while todo:
        q = todo.pop()
        if q.area < 1e-4:
            continue
        if not q.interiors:
            out.append(q)
            continue
        cx = q.interiors[0].centroid.x
        (x0, y0, x1, y1) = q.bounds
        todo += list(split(q, LineString([(cx, y0 - 1), (cx, y1 + 1)])).geoms)
    return out


def routing_keepouts(b):
    """Rule areas added only to the copy of the board handed to Freerouting:

      - the RF lines' coplanar ground strip on F.Cu (the line's gap plus
        room for the ground pour beside it): no tracks or vias of other
        nets, so the pour after routing runs along every RF line; other
        nets' pins keep a 0.7 mm way out through it;
      - a strip along the outline (Freerouting keeps only its own
        clearance from it).

    The ground plane is a power layer with its plane zone kept (Freerouting
    routes nothing on it; its vias pass through) and every other pour is
    removed (Freerouting reads a zone as its outline, overlapping the pads
    inside it)."""
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    import fanout
    band, holes = [], []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition()
            holes.append(Point(q.x / 1e6, q.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6 + 0.12))
            continue
        if t.GetLayer() != pcbnew.F_Cu:
            continue
        s_, e_ = t.GetStart(), t.GetEnd()
        line = LineString([(s_.x / 1e6, s_.y / 1e6), (e_.x / 1e6, e_.y / 1e6)])
        if t.GetNetname() in board.RF_NETS + board.RF_EXTRA:
            band.append(line.buffer(t.GetWidth() / 2e6 + board.RF_GAP + 0.3))
        holes.append(line.buffer(t.GetWidth() / 2e6 + 0.12))
    rf = set(board.RF_NETS + board.RF_EXTRA + ['GND'])
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                g = fanout.pad_poly(p, pcbnew.F_Cu)
                if g is not None:
                    # another net's pin keeps a way out (0.7 mm round it): a
                    # chip's supply or control pin beside an RF line would
                    # otherwise be walled in (30 were, with 0.12)
                    holes.append(g.buffer(0.12 if p.GetNetname() in rf or not p.GetNetname() else 0.7))
    keep = unary_union(band).difference(unary_union(holes))
    k = 0
    for q in _simple(keep):
        if q.area < 0.02:
            continue
        pts = [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
        pcb.rule_area(b, pts, [pcbnew.F_Cu], tracks=True, vias=True, pads=False, pours=False, name='RF ground strip')
        k += 1
    gl = pcb.layer_id(pcb.INNER['gnd'])
    for z in list(b.Zones()):
        # the ground plane stays: exported as a plane, Freerouting routes
        # nothing on it and joins ground pads through it (without it, In1
        # was "a power layer with no plane, treated as a signal layer" and
        # took signals)
        if not z.GetIsRuleArea() and (ROUTE_IN1 or not (z.GetNetname() == 'GND' and z.GetLayerSet().Contains(gl))):
            pcb.remove(b, z)
    for gl in ([] if ROUTE_IN1 else [pcb.INNER['gnd']]) + ([pcb.INNER['gnd2']] if 'gnd2' in pcb.INNER else []):
        b.SetLayerType(pcb.layer_id(gl), pcbnew.LT_POWER)
    hx, hy, w = pcb.HX, pcb.HY, EDGE
    for x0, y0, x1, y1 in ((-hx, -hy, hx, -hy + w), (-hx, hy - w, hx, hy), (-hx, -hy, -hx + w, hy),
                           (hx - w, -hy, hx, hy)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], board.CU, tracks=True, vias=True,
                      pads=False, pours=False, name='edge keepout')
    return k


def setup_routers():
    finish.ROUTE_LAYERS = ([pcbnew.F_Cu] + ([pcb.layer_id(pcb.INNER['gnd'])] if ROUTE_IN1 else [])
                           + [pcb.layer_id(n) for n in pcb.INNER['sig']] + [pcbnew.B_Cu])
    # 0.025 mm cells (the SX1262's and the chips' 0.5 mm pitch), searched in
    # a window round each connection first
    finish.SIG_W, finish.SIG_CL = board.SIG, board.SIG   # the board's default net class
    finish.RES = 0.025
    finish.WINDOW = 3.0
    finish.COARSE = 0.05
    finish.VIA_D, finish.VIA_DRILL = board.VIA_SIG
    # a via keeps JLCPCB's 0.2 mm hole-to-copper at the 0.1 mm clearance, with
    # 0.01 mm for the 0.025 mm grid (at 0.1 its tracks came 0.195 mm from holes)
    finish.VIA_RING = 0.11
    # Freerouting too: the locked vias (the ball escapes, 0.3/0.15 mm) go out
    # with that ring (at their own, its tracks sat 0.175 mm from their holes)
    route.VIA_RING = 0.11
    finish.POFV_GAP = None
    route.VIA_IN_PAD = board.VIA_SIG
    route.PRE_EXPORT = routing_keepouts
    route.EXTRA = []
    # ground is the plane; the RF lines are drawn already (locked)
    route.DROP_NETS = tuple(PLANES) + tuple(board.RF_NETS) + tuple(board.RF_EXTRA)
    route.AUTOROUTE = dict(via_costs=int(os.environ.get('FR_VIA_COSTS', 40)), plane_via_costs=5,
                           start_ripup_costs=int(os.environ.get('FR_RIPUP_COSTS', 100)), fanout=False,
                           directions={'F.Cu': 'horizontal', 'In1.Cu': 'vertical', 'In2.Cu': 'vertical',
                                       'In3.Cu': 'horizontal', 'In4.Cu': 'vertical', 'B.Cu': 'horizontal'})


def widths(comps):
    """net -> track width for the maze router: the net class widths."""
    out = {}
    for n in set(v for c in comps for v in c.pins.values() if v):
        if n in board.HEAVY:
            out[n] = board.HEAVY_ROUTE_W
        elif n in board.POWER:
            out[n] = board.POWER_ROUTE_W
        elif n in board.RAIL:
            out[n] = 0.15
        elif n in board.RF_NETS:
            out[n] = board.RF_W
    return out


def clearances(comps):
    """Router clearances: the net class clearances (everything here is
    below 25 V; IPC-2221B B4 allows 0.1 mm)."""
    nets = set(n for c in comps for n in c.pins.values() if n)
    cl = {n: finish.SIG_CL for n in nets}
    for n in nets:
        if n in board.POWER:
            cl[n] = 0.12
    return cl


def write_rules(path):
    pcb.write_rules(path, board.RULES)


def finish_stage(routed, fin, work):
    """The routing's leftovers, the ground pour and DRC.  Returns the DRC result."""
    comps = circuit.build()
    w, cl = widths(comps), clearances(comps)
    setup_routers()
    b = pcbnew.LoadBoard(routed)
    k = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in PLANES and not t.IsLocked():
            pcb.remove(b, t); k += 1
    if k:
        b.Save(routed)
        log('removed %d router-made ground tracks and vias' % k)
    fixed = os.path.join(work, 'fixed.kicad_pcb')
    shutil.copy(routed, fixed); pcb.copy_project(routed, fixed)
    fab_fixups(fixed)
    pcb.copy_project(fixed, fin)
    finish.finish_board(fixed, fin, os.path.join(work, 'fin.json'), rules=w, clmap=cl, skip=PLANES)
    write_rules(fin)
    pcb.tidy_tracks(fin)
    return finish_rest(fin, work, w, cl)


SUPPLY = set(board.HEAVY + board.POWER + board.RAIL)


# the via-hole checks aim this far beyond the fab's 0.2 mm (a nudge aimed
# at 0.199 landed at 0.1989, which KiCad's DRC refuses)
HOLE_MARGIN = 0.003


def nudge_via(b, v, obs, layers, gap=0.2):
    """Move via `v` (and the ends of its tracks) the least distance, up to
    0.15 mm, that gives its hole `gap` to every other net's copper, keeps
    its copper and its moved tracks at the fab's 0.09 mm, and keeps the
    hole-to-hole spacing (obs.hole_room).  True if it moved."""
    import math
    from shapely.geometry import Point, LineString
    q = v.GetPosition(); x0, y0 = q.x / 1e6, q.y / 1e6
    r, rh = v.GetWidth(pcbnew.F_Cu) / 2e6, v.GetDrillValue() / 2e6
    net = v.GetNetname()
    ends = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net
            and (t.GetStart() == q or t.GetEnd() == q)]
    cl = board.FAB_MIN + 0.002
    others = [h for h in obs.holes if abs(h[0] - x0) > 1e-6 or abs(h[1] - y0) > 1e-6]
    saved = obs.holes
    try:
        obs.holes = others
        for k10 in range(1, 16):
            d = k10 / 100.0
            for k in range(16):
                a = 2 * math.pi * k / 16
                x, y = x0 + d * math.cos(a), y0 + d * math.sin(a)
                if not (obs.clear(Point(x, y).buffer(rh, 16), net, layers, gap + HOLE_MARGIN)
                        and obs.clear(Point(x, y).buffer(r, 16), net, layers, cl)
                        and obs.hole_room(x, y, rh, 0.45)):
                    continue
                ok = True
                for t in ends:
                    far = t.GetEnd() if t.GetStart() == q else t.GetStart()
                    g = LineString([(x, y), (far.x / 1e6, far.y / 1e6)]).buffer(t.GetWidth() / 2e6, 8)
                    if not obs.clear(g, net, [t.GetLayer()], cl):
                        ok = False; break
                if not ok:
                    continue
                p = pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6)))
                for t in ends:
                    if t.GetStart() == q:
                        t.SetStart(p)
                    if t.GetEnd() == q:
                        t.SetEnd(p)
                v.SetPosition(p)
                # later nudges in this pass see the hole and its copper where they now are
                saved[:] = others + [(x, y, rh)]
                obs.add(Point(x, y).buffer(r, 16), net, layers)
                for t in ends:
                    a_, e_ = t.GetStart(), t.GetEnd()
                    obs.add(LineString([(a_.x / 1e6, a_.y / 1e6), (e_.x / 1e6, e_.y / 1e6)]).buffer(t.GetWidth() / 2e6, 8),
                            net, [t.GetLayer()])
                return True
        return False
    finally:
        obs.holes = saved


def shrink_via(b, v, obs, layers, gap=0.2):
    """Give via `v` the board's in-pad via size (board.VIA_PAD) if its hole
    then clears `gap` where it is or after a nudge; else put it back."""
    from shapely.geometry import Point
    w, d = v.GetWidth(pcbnew.F_Cu), v.GetDrillValue()
    v.SetWidth(pcb.MM(board.VIA_PAD[0])); v.SetDrill(pcb.MM(board.VIA_PAD[1]))
    q = v.GetPosition()
    if obs.clear(Point(q.x / 1e6, q.y / 1e6).buffer(board.VIA_PAD[1] / 2, 16), v.GetNetname(), layers, gap + HOLE_MARGIN):
        return True
    if nudge_via(b, v, obs, layers, gap):
        return True
    v.SetWidth(w); v.SetDrill(d)
    return False


def in_pad(b, v):
    """True if via `v` sits in a pad of its own net."""
    q = v.GetPosition()
    return any(p.GetNetname() == v.GetNetname() and p.HitTest(q) for fp in b.GetFootprints() for p in fp.Pads())


def rip_near(b, v, gap=0.2):
    """Take out the other nets' tracks and vias whose copper comes within
    `gap` of via `v`'s hole (planes and RF lines excepted).  Returns how many."""
    from shapely.geometry import Point
    q = v.GetPosition()
    hole = Point(q.x / 1e6, q.y / 1e6).buffer(v.GetDrillValue() / 2e6, 16)
    keep = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA) | {v.GetNetname()}
    n = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in keep or t.IsLocked():
            continue
        g = finish._geom_of(t)
        if g and any(x.distance(hole) < gap + HOLE_MARGIN for gs in g.values() for x in gs):
            pcb.remove(b, t); n += 1
    return n


def fix_via_holes(b, skip=(), gap=0.2, passes=6, fixed=()):
    """Every via (not of the nets in `skip`) whose hole comes within `gap`
    of another net's copper: nudged (nudge_via), else given the board's
    0.3/0.15 size (shrink_via), else, in a pad or locked, the other nets'
    track pieces near it go (rip_near), else it goes.  Returns the counts
    (nudged, shrunk, track pieces out, vias out)."""
    import fanout
    from shapely.geometry import Point
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    nv = nn = ns = nt = 0
    for _ in range(passes):
        obs = fanout.Obstacles(b, layers)
        bad = []
        for v in b.GetTracks():
            if v.GetClass() != 'PCB_VIA' or v.GetNetname() in skip:
                continue
            q = v.GetPosition()
            hole = Point(q.x / 1e6, q.y / 1e6).buffer(v.GetDrillValue() / 2e6, 16)
            if not obs.clear(hole, v.GetNetname(), layers, gap + HOLE_MARGIN):
                bad.append(v)
        if not bad:
            break
        # a plane's own stitching vias first (they go freely), signals before supplies
        bad.sort(key=lambda v: (v.GetNetname() not in PLANES, v.GetNetname() in SUPPLY, v.IsLocked()))
        for v in bad[: max(1, len(bad) // 2)]:
            if v not in list(b.GetTracks()):
                continue
            # first a nudge: the smallest move (up to 0.15 mm) that clears it, its
            # tracks' ends following (0.19 mm is the usual miss)
            if v.GetNetname() in fixed:
                # an RF line's via stays where it is: the tracks near it go
                nt += rip_near(b, v, gap)
            elif nudge_via(b, v, obs, layers, gap):
                nn += 1
            elif v.GetDrillValue() > pcb.MM(board.VIA_PAD[1]) and shrink_via(b, v, obs, layers, gap):
                # the board's in-pad via size (0.3/0.15 mm, already on it):
                # its hole edge 0.025 mm further in, nudged again if need be
                ns += 1
            elif v.IsLocked() or in_pad(b, v):
                # a via in a chip's pad (the ball escapes) stays: the other
                # nets' track pieces too close to its hole go instead (with
                # 0.3/0.15 vias at 0.1 mm, a track can sit 0.175 mm from the
                # hole); the maze routes them again around it
                nt += rip_near(b, v, gap)
            else:
                pcb.remove(b, v); nv += 1
    return nn, ns, nt, nv


def rip_near_pth(b, gap=0.28):
    """Take out the other nets' unlocked tracks within `gap` (JLCPCB's
    plated hole to track, pcb.RULES) of a plated component hole.  Returns how many."""
    from shapely.geometry import Point, LineString
    keep = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA)
    holes = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetDrillSize().x > 0:
                hs = p.GetEffectiveHoleShape(); sg = hs.GetSeg()
                g = (LineString([(sg.A.x / 1e6, sg.A.y / 1e6), (sg.B.x / 1e6, sg.B.y / 1e6)]) if sg.A != sg.B
                     else Point(sg.A.x / 1e6, sg.A.y / 1e6)).buffer(hs.GetWidth() / 2e6, 16)
                holes.append((g, p.GetNetname()))
    n = 0
    for t in list(b.GetTracks()):
        if t.GetClass() != 'PCB_TRACK' or t.GetNetname() in keep or t.IsLocked():
            continue
        g = finish._geom_of(t)
        if g and any(h.distance(x) < gap + HOLE_MARGIN for h, hn in holes if hn != t.GetNetname()
                     for gs in g.values() for x in gs):
            pcb.remove(b, t); n += 1
    return n


def hole_pass(path, log=log):
    """Before the clean-up: fix_via_holes over every via but the RF lines'
    (the ground pour's stitching vias too), then a maze pass for anything
    it opened is left to the caller."""
    b = pcbnew.LoadBoard(path)
    r = fix_via_holes(b, fixed=set(board.RF_NETS) | set(board.RF_EXTRA))
    k = rip_near_pth(b)
    pcb.save_board(b, path)
    log('hole pass: %d vias nudged, %d made 0.3/0.15 mm, %d track pieces and %d vias taken out' % r
        + ', %d track pieces too near plated holes taken out' % k)
    return r[:2] + (r[2] + k, r[3])


def fab_fixups(path, log=log):
    """Before the maze router: take out what the fab's limits forbid, for
    the maze to route again (all from the 1 Nov 62 mm run's DRC):
      - tracks narrower than the fab's 0.09 mm (Freerouting necks its
        tracks down to 0.075 mm at small pins) are widened to it;
      - a via whose hole comes within 0.2 mm of another net's copper (the
        neighbouring one of two such vias goes, a signal's before a supply's);
      - tracks and vias inside an unplated hole's keepout (board.npth_keepouts)."""
    import fanout
    from shapely.geometry import Point
    b = pcbnew.LoadBoard(path)
    if not any(z.GetIsRuleArea() and z.GetZoneName() == 'unplated hole keepout' for z in b.Zones()):
        board.npth_keepouts(b)
    keep = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA)
    # the fab's limits on this board (a board routed before they were set)
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = pcb.MM(board.FAB_MIN); ds.m_MinClearance = pcb.MM(board.FAB_MIN)
    # the routers keep 0.1 mm (the DRC allows 0.09: board.RULES); a board built
    # with 0.09 here had router vias with holes 0.19 mm from copper
    ds.m_NetSettings.GetDefaultNetclass().SetClearance(pcb.MM(board.SIG))
    # Freerouting's necks (0.075 mm at small pins) widened to the fab's 0.09
    thin = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetWidth() < pcbnew.FromMM(board.FAB_MIN) - 500]
    for t in thin:
        t.SetWidth(pcbnew.FromMM(board.FAB_MIN))
    # vias whose holes are too close to other copper
    nn, ns, nt, nv = fix_via_holes(b, keep)
    nt += rip_near_pth(b)
    # copper in the unplated-hole keepouts
    rings = []
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetZoneName() == 'unplated hole keepout':
            ol = z.Outline().Outline(0)
            from shapely.geometry import Polygon
            rings.append(Polygon([(ol.CPoint(i).x / 1e6, ol.CPoint(i).y / 1e6) for i in range(ol.PointCount())]))
    ne = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in keep:
            continue
        g = finish._geom_of(t)
        if g and any(r.intersects(x) for r in rings for gs in g.values() for x in gs):
            pcb.remove(b, t); ne += 1
    pcb.save_board(b, path)
    log('fab fixups: %d thin tracks widened, %d vias nudged clear, %d made the 0.3/0.15 mm size, %d track pieces '
        'too near in-pad via holes, %d vias with close holes and %d pieces in unplated-hole keepouts taken out'
        % (len(thin), nn, ns, nt, nv, ne))


def finish_rest(fin, work, w=None, cl=None):
    """After the maze router: the supply nets still in pieces get local
    pours that join them (island_pours); the signal nets still open get
    the rip-up repair, small nets first, a few tries each; then the tail."""
    if w is None:
        comps = circuit.build()
        w, cl = widths(comps), clearances(comps)
        setup_routers()
    b = pcbnew.LoadBoard(fin)
    left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
    log('after the maze router: %d nets open %s' % (len(left), left))
    if left:
        # a lone pad cut off from its net: a via of its own (in the pad, else a
        # dog-bone), then the maze router once more for just those nets
        if escape_lone_pads(fin, left):
            nets_all = set(n_ for c in circuit.build() for n_ in c.pins.values() if n_)
            finish.finish_board(fin, fin, os.path.join(work, 'fin_lone.json'), rules=w, clmap=cl,
                                skip=tuple(nets_all - set(left)))
            write_rules(fin)
            pcb.tidy_tracks(fin)
            b = pcbnew.LoadBoard(fin)
            left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
            log('after the lone-pad vias: %d nets open %s' % (len(left), left))
    sup = [x for x in left if x in SUPPLY]
    if sup:
        island_pours(fin, sup)
        b = pcbnew.LoadBoard(fin)
        left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
        log('after the supply pours: %d nets open %s' % (len(left), left))
    sig = sorted([x for x in left if x not in SUPPLY], key=lambda n_: len(finish._net_components(b, n_)))
    if sig:
        protect = PLANES + list(board.RF_NETS) + sorted(SUPPLY)
        rest = finish.repair_orders(b, sig, protect=protect, widths=w, clmap=cl, log=log,
                                    tries=int(os.environ.get('REPAIR_TRIES', 4)), max_victims=6)
        b.Save(fin)
        left = [x for x in left if x in SUPPLY] + list(rest)
    if left:
        b = pcbnew.LoadBoard(fin)
        for n_ in list(left):
            corridor_repair(b, n_, w, cl)
        b.Save(fin)
        left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
    log('nets left after repair: %s' % (left,))
    return finish_tail(fin, work, w, cl)


def corridor_repair(b, net, widths, clmap, widths_try=(1.0, 1.8, 2.6), log=log):
    """Clear every other net's unlocked copper (tracks and vias; never
    ground, RF or locked escapes) in a corridor between the net's two
    nearest islands, route the net first, then route every cleared net
    again; kept only if every cleared net ends in no more pieces than
    before, otherwise everything is put back.  Wider corridors on failure."""
    from shapely.geometry import LineString
    from shapely.ops import nearest_points, unary_union
    keep = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA)
    W = lambda n_: (widths or {}).get(n_, board.SIG)
    for cw in widths_try:
        comps = finish._net_components(b, net)
        if len(comps) <= 1:
            return True
        shapes = [unary_union([g for gs in c.values() for g in gs]) for c in comps]
        best = min(((shapes[i].distance(shapes[j]), i, j) for i in range(len(shapes))
                    for j in range(i + 1, len(shapes))))
        pa, pb = nearest_points(shapes[best[1]], shapes[best[2]])
        corr = LineString([pa, pb]).buffer(cw)
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        removed, victims = [], set()
        for t in list(b.GetTracks()):
            n_ = t.GetNetname()
            if n_ == net or n_ in keep or t.IsLocked():
                continue
            if finish._geom_of(t) and any(g.intersects(corr) for gs in finish._geom_of(t).values() for g in gs):
                victims.add(n_); removed.append(t); pcb.remove(b, t)
        base = {n_: len(finish._net_components(b, n_)) for n_ in victims}
        # (base counted after the cut: a victim must end no worse than it was
        # before the cut, i.e. back to its count with the copper in place)
        orig = {}
        for t in removed:
            b.Add(t)
        orig = {n_: len(finish._net_components(b, n_)) for n_ in victims}
        for t in removed:
            pcb.remove(b, t)
        finish.route_net(b, net, track_w=W(net), clmap=clmap, lock=False)
        ok = len(finish._net_components(b, net)) < len(comps)
        if ok:
            for n_ in sorted(victims, key=lambda v: -W(v)):
                finish.route_net(b, n_, track_w=W(n_), clmap=clmap, lock=False)
            ok = all(len(finish._net_components(b, n_)) <= orig[n_] for n_ in victims)
        if ok:
            log('   corridor %-12s %.1f mm: joined, re-routed %s' % (net, cw, sorted(victims)))
            continue
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() not in before:
                pcb.remove(b, t)
        for t in removed:
            b.Add(t)
    left = len(finish._net_components(b, net))
    if left > 1:
        log('   corridor %-12s still in %d pieces' % (net, left))
    return left <= 1


def escape_lone_pads(path, nets, log=log):
    """For each open net, every island that is only outer-layer copper (a
    pad, or a part's few pads, cut off) gets a via: in the pad itself where
    it clears every other net on every layer (filled, VIA_PAD), else a
    dog-bone beside it.  Returns how many were added."""
    import fanout
    from shapely.geometry import Point
    from shapely.ops import unary_union
    b = pcbnew.LoadBoard(path)
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    n_ = 0
    for net in nets:
        for comp in finish._net_components(b, net):
            if set(comp) - {pcbnew.F_Cu, pcbnew.B_Cu}:
                continue
            shape = unary_union([g for gs in comp.values() for g in gs]).buffer(0.01)
            pins = [(fp, p) for fp in b.GetFootprints() for p in fp.Pads()
                    if p.GetNetname() == net and shape.contains(Point(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))]
            obs = fanout.Obstacles(b, layers)
            d_, dr_ = board.VIA_PAD
            done = False
            for fp, p in pins:
                x, y = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
                g = Point(x, y).buffer(d_ / 2, 16)
                if obs.hole_room(x, y, dr_ / 2, 0.2) and obs.clear(g, net, layers, 0.1):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(p.GetPosition())
                    v.SetWidth(pcbnew.FromMM(d_)); v.SetDrill(pcbnew.FromMM(dr_)); v.SetNet(p.GetNet())
                    b.Add(v); done = True
                    log('   lone pad %-12s via in %s %s' % (net, fp.GetReference(), p.GetNumber()))
                    break
            if not done and pins:
                d_, dr_ = board.VIA_SIG
                k, _ = fanout.dogbones(b, [(fp.GetReference(), p.GetNumber()) for fp, p in pins[:3]],
                                       via_d=d_, via_drill=dr_, width=0.12, cl=0.1, hole_gap=0.2)
                done = bool(k)
                log('   lone pad %-12s %s' % (net, 'dog-bone at ' + pins[0][0].GetReference() if k else 'no room for a via'))
            n_ += done
    b.Save(path)
    return n_


def island_pours(path, nets, margin=0.6, log=log):
    """Join a supply net's copper islands with pours of that net: for each
    layer (inner signal layers, then the outer ones), a zone over the net's
    islands' convex hull (plus `margin`), above the ground fill's priority;
    kept where it reduces the islands, removed where it does not.  A pour
    flows round obstacles a track cannot pass; on supply nets that is the
    normal way to carry current anyway."""
    import fanout
    from shapely.geometry import box, Point
    from shapely.ops import unary_union
    b = pcbnew.LoadBoard(path)
    inside = box(pcb.CX - pcb.HX + 0.4, pcb.CY - pcb.HY + 0.4, pcb.CX + pcb.HX - 0.4, pcb.CY + pcb.HY - 0.4)
    order = [pcb.layer_id(n) for n in pcb.INNER['sig'][::-1]] + [pcbnew.B_Cu, pcbnew.F_Cu]
    if ROUTE_IN1:
        order.insert(len(pcb.INNER['sig']), pcb.layer_id(pcb.INNER['gnd']))
    filler = pcbnew.ZONE_FILLER(b)
    kept = 0
    for net in nets:
        n0 = len(finish._net_components(b, net))
        if n0 <= 1:
            continue
        # an island only on an outer layer (a lone pad) cannot meet an inner
        # pour: give one of its pads a dog-bone via first
        comps_ = finish._net_components(b, net)
        for comp in comps_:
            if set(comp) - {pcbnew.F_Cu, pcbnew.B_Cu}:
                continue
            shape = unary_union([g for gs in comp.values() for g in gs])
            pins = [(fp.GetReference(), p.GetNumber()) for fp in b.GetFootprints() for p in fp.Pads()
                    if p.GetNetname() == net and shape.buffer(0.01).contains(
                        Point(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))]
            if pins:
                # a filled via in the pad itself (as the ball escapes), else a dog-bone
                d_, dr_ = board.VIA_PAD
                layers = [l for l in b.GetEnabledLayers().CuStack()]
                obs = fanout.Obstacles(b, layers)
                done = False
                for ref_, num in pins[:3]:
                    pad = [q for q in b.FindFootprintByReference(ref_).Pads() if q.GetNumber() == num][0]
                    x, y = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
                    g = Point(x, y).buffer(d_ / 2, 16)
                    if obs.hole_room(x, y, dr_ / 2, 0.2) and obs.clear(g, net, layers, 0.1):
                        v = pcbnew.PCB_VIA(b); v.SetPosition(pad.GetPosition())
                        v.SetWidth(pcbnew.FromMM(d_)); v.SetDrill(pcbnew.FromMM(dr_)); v.SetNet(pad.GetNet())
                        b.Add(v); done = True
                        log('   pour %-12s via in pad %s %s' % (net, ref_, num))
                        break
                if not done:
                    d_, dr_ = board.VIA_SIG
                    placed_, _ = fanout.dogbones(b, pins[:3], via_d=d_, via_drill=dr_, width=0.2, cl=0.12, hole_gap=0.2)
                    if placed_:
                        log('   pour %-12s dog-bone via for a lone pad of %s' % (net, pins[0][0]))
        geo = []
        for comp in finish._net_components(b, net):
            for gs in comp.values():
                geo += gs
        hull = unary_union(geo).convex_hull.buffer(margin).intersection(inside)
        if hull.is_empty or hull.geom_type != 'Polygon':
            continue
        pts = [(x - pcb.CX, y - pcb.CY) for x, y in list(hull.exterior.coords)[:-1]]
        for L in order:
            z = pcb.zone(b, net, L, pts, clearance=0.15, min_width=0.2, priority=5, thermal=False,
                         name=net + ' join')
            filler.Fill([z])
            n1 = len(finish._net_components(b, net))
            if n1 < n0:
                kept += 1
                log('   pour %-12s on %-6s islands %d -> %d' % (net, b.GetLayerName(L), n0, n1))
                n0 = n1
                if n0 <= 1:
                    break
            else:
                pcb.remove(b, z)
    b.Save(path)
    log('supply pours: %d kept' % kept)
    return kept


def fatten(path, log=log, neck=0.45):
    """Widen the heavy-current and power tracks the routers laid thin
    (board.HEAVY_ROUTE_W / POWER_ROUTE_W) wherever there is room: each
    segment longer than 2 x `neck` is split so its ends (where it meets a
    fine-pitch pin) can stay thin while its middle widens; each piece takes
    the widest of the target width down to its own that clears every other
    net by its class clearance and keeps 0.35 mm from the board edge."""
    import fanout
    from shapely.geometry import LineString, box
    b = pcbnew.LoadBoard(path)
    want = {n: (board.HEAVY_W, 0.1) for n in board.HEAVY}
    want.update({n: (board.POWER_W, 0.12) for n in board.POWER})
    # split
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_VIA' or t.GetNetname() not in want or t.IsLocked():
            continue
        # copies: GetStart()/GetEnd() hand back the track's own points, so
        # e_ would follow t.SetEnd(p1) and the last piece would end at p1
        # (2 Nov: every split power track lost its far end, 110 opens)
        s_ = pcbnew.VECTOR2I(t.GetStart().x, t.GetStart().y)
        e_ = pcbnew.VECTOR2I(t.GetEnd().x, t.GetEnd().y)
        L = (e_ - s_).EuclideanNorm() / 1e6
        if L <= 2 * neck + 0.2:
            continue
        f1, f2 = neck / L, 1 - neck / L
        p1 = pcbnew.VECTOR2I(int(s_.x + (e_.x - s_.x) * f1), int(s_.y + (e_.y - s_.y) * f1))
        p2 = pcbnew.VECTOR2I(int(s_.x + (e_.x - s_.x) * f2), int(s_.y + (e_.y - s_.y) * f2))
        t.SetEnd(p1)
        for a, c in ((p1, p2), (p2, e_)):
            u = pcbnew.PCB_TRACK(b)
            u.SetStart(a); u.SetEnd(c); u.SetWidth(t.GetWidth()); u.SetLayer(t.GetLayer()); u.SetNet(t.GetNet())
            b.Add(u)
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    obs = fanout.Obstacles(b, layers)
    obs.keepouts = []                          # vias only; tracks may cross those
    # the fab's 0.2 mm from every other net's via hole (0.01 mm to spare)
    from shapely.geometry import Point
    vh = [(Point(v.GetPosition().x / 1e6, v.GetPosition().y / 1e6), v.GetDrillValue() / 2e6, v.GetNetname())
          for v in b.GetTracks() if v.GetClass() == 'PCB_VIA']
    # and 0.29 mm from other nets' plated component holes (pcb.RULES: 0.28)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetDrillSize().x > 0:
                hs = p.GetEffectiveHoleShape(); sg = hs.GetSeg()
                vh.append(((LineString([(sg.A.x / 1e6, sg.A.y / 1e6), (sg.B.x / 1e6, sg.B.y / 1e6)]) if sg.A != sg.B
                            else Point(sg.A.x / 1e6, sg.A.y / 1e6)), hs.GetWidth() / 2e6 + 0.08, p.GetNetname()))
    holes_ok = lambda g, net: all(g.distance(c) >= r + 0.21 for c, r, n in vh if n != net)
    # and stays out of the track keepouts (the RF reference areas on In1)
    from shapely.geometry import Polygon
    tko = {}
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            ol = z.Outline().Outline(0)
            P = Polygon([(ol.CPoint(j).x / 1e6, ol.CPoint(j).y / 1e6) for j in range(ol.PointCount())]).buffer(0)
            for l in z.GetLayerSet().CuStack():
                tko.setdefault(l, []).append(P)
    ko_ok = lambda g, l: not any(P.intersects(g) for P in tko.get(l, []))
    inside = box(pcb.CX - pcb.HX + 0.35, pcb.CY - pcb.HY + 0.35, pcb.CX + pcb.HX - 0.35, pcb.CY + pcb.HY - 0.35)
    n = k = 0
    for t in list(b.GetTracks()):
        net = t.GetNetname()
        if t.GetClass() == 'PCB_VIA' or net not in want or t.IsLocked():
            continue
        k += 1
        tw, tcl = want[net]
        cur = t.GetWidth() / 1e6
        s_, e_ = t.GetStart(), t.GetEnd()
        line = LineString([(s_.x / 1e6, s_.y / 1e6), (e_.x / 1e6, e_.y / 1e6)])
        w_ = tw
        while w_ > cur + 1e-6:
            g = line.buffer(w_ / 2)
            if inside.contains(g) and obs.clear(g, net, [t.GetLayer()], tcl) and holes_ok(g, net) \
                    and ko_ok(g, t.GetLayer()):
                t.SetWidth(pcbnew.FromMM(w_))
                obs.add(g, net, [t.GetLayer()])
                n += 1
                break
            w_ = round(w_ - 0.05, 3)
    b.Save(path)
    log('fatten: %d of %d power track pieces widened' % (n, k))


def finish_tail(fin, work, w, cl):
    """Ground pour and stitching, the last maze pass, clean-up, POFV
    spacing, stackup and DRC."""
    import stitch, cleanup, pofv
    shutil.copy(fin, os.path.join(work, 'tail_in.kicad_pcb')); pcb.copy_project(fin, os.path.join(work, 'tail_in.kicad_pcb'))

    def opens(step):
        # KiCad's own count after each step (2 Nov: the supply nets came out
        # of the tail open, whole going in)
        write_rules(fin)
        _, _, u = pcb.drc(fin, os.path.join(work, 'tail_%s.json' % step))
        nets = Counter(x['items'][0]['description'].split('[')[1].split(']')[0] for x in u if '[' in x['items'][0]['description'])
        log('tail, after %s: %d unconnected %s' % (step, len(u), dict(nets)))
    opens('repair')
    pcb.tidy_tracks(fin)
    opens('tidy')
    fatten(fin)
    opens('fatten')
    # the ground pour on every routing layer but the plane's own (In1 has
    # the 'GND plane' zone: a second one there is a DRC error)
    plane = pcb.layer_id(pcb.INNER['gnd'])
    pcb.pour_ground(fin, [l for l in finish.ROUTE_LAYERS if l != plane], clearance=0.15)
    b = pcbnew.LoadBoard(fin)
    stitch.stitch_ground(b, pitch=1.0, via=board.VIA_SIG, clearance=0.13, log=log)
    b.Save(fin)
    opens('pour and stitch')
    finish.finish_board(fin, fin, os.path.join(work, 'fin2.json'), rules=w, clmap=cl)
    opens('maze')
    return finish_clean(fin, work, w, cl)


def finish_clean(fin, work, w=None, cl=None):
    """The hole pass, clean-up, POFV spacing, stackup and DRC."""
    import cleanup, pofv
    if w is None:
        comps = circuit.build()
        w, cl = widths(comps), clearances(comps)
        setup_routers()
    # the fattened tracks and the stitching vias against the fab's 0.2 mm
    # hole-to-copper; a maze pass for what that opened
    if any(hole_pass(fin)[2:]):
        # (the pours are there: the maze and the DRC refill them)
        write_rules(fin)
        finish.finish_board(fin, fin, os.path.join(work, 'fin3.json'), rules=w, clmap=cl)
        write_rules(fin)
    cleanup.clean(fin, board.RULES, log=log)
    dj = os.path.join(work, 'pofv_drc.json')
    e, wn, u = pcb.drc(fin, dj)
    if any(v['type'] == 'hole_to_hole' for v in e):
        pofv.nudge_vias(fin, dj, clearances=cl, log=log)
    pcb.set_stackup(fin, inner_oz=0.5)
    e, wn, u = pcb.drc(fin, os.path.join(work, 'fin_drc.json'))
    log('DRC: %d errors %s, %d warnings %s, %d unconnected'
        % (len(e), dict(Counter(v['type'] for v in e)), len(wn), dict(Counter(v['type'] for v in wn)), len(u)))
    return e, wn, u


def gnd_island_vias(path, log=log):
    """A piece of a ground fill with no ground via in it (cut off from the
    plane, e.g. round one pad) gets one: the first spot on a 0.1 mm grid
    inside it where a board.VIA_SIG via clears everything.  Returns how many."""
    import fanout
    from shapely.geometry import Point, Polygon
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    layers = [l for l in b.GetEnabledLayers().CuStack()]
    obs = fanout.Obstacles(b, layers)
    vias = [Point(v.GetPosition().x / 1e6, v.GetPosition().y / 1e6) for v in b.GetTracks()
            if v.GetClass() == 'PCB_VIA' and v.GetNetname() in PLANES]
    d, dr = board.VIA_SIG
    k = 0
    for z in list(b.Zones()):
        if z.GetIsRuleArea() or z.GetNetname() not in PLANES or z.GetZoneName() == 'GND plane':
            continue
        for l in z.GetLayerSet().CuStack():
            fp_ = z.GetFilledPolysList(l)
            for i in range(fp_.OutlineCount()):
                ol = fp_.Outline(i)
                P = Polygon([(ol.CPoint(j).x / 1e6, ol.CPoint(j).y / 1e6) for j in range(ol.PointCount())]).buffer(0)
                if P.is_empty or any(P.contains(v) for v in vias):
                    continue
                core = P.buffer(-d / 2)
                if core.is_empty:
                    continue
                x0, y0, x1, y1 = core.bounds
                done = False
                yy = y0
                while yy <= y1 and not done:
                    xx = x0
                    while xx <= x1 and not done:
                        q = Point(xx, yy)
                        if (core.contains(q) and obs.clear(q.buffer(d / 2, 16), z.GetNetname(), layers, board.SIG)
                                and obs.clear(q.buffer(dr / 2, 16), z.GetNetname(), layers, 0.2 + HOLE_MARGIN)
                                and obs.hole_room(xx, yy, dr / 2, 0.45)):
                            v = pcbnew.PCB_VIA(b)
                            v.SetPosition(pcbnew.VECTOR2I(int(round(xx * 1e6)), int(round(yy * 1e6))))
                            v.SetWidth(pcb.MM(d)); v.SetDrill(pcb.MM(dr)); v.SetNet(z.GetNet())
                            b.Add(v)
                            obs.add(q.buffer(d / 2, 16), z.GetNetname(), layers); obs.holes.append((xx, yy, dr / 2))
                            vias.append(q); k += 1; done = True
                        xx += 0.1
                    yy += 0.1
    pcb.save_board(b, path)
    log('ground islands: %d vias added' % k)
    return k


def endgame(fin, work, rounds=3):
    """The last few problems of a finished board: the tracks in each
    clearance error go, ground-fill islands get a via, the open nets are
    routed by negotiated congestion (finish.pathfinder: crossings priced up
    each iteration until none is left), then the hole pass, clean-up and
    DRC.  A round is kept only if the DRC total falls."""
    import cleanup
    comps = circuit.build()
    w, cl = widths(comps), clearances(comps)
    setup_routers()
    keep = set(PLANES) | set(board.RF_NETS) | set(board.RF_EXTRA)
    write_rules(fin)       # a copied board has no .kicad_dru: KiCad's defaults would flag the 0.09 mm gaps
    e, wn, u = pcb.drc(fin, os.path.join(work, 'end0.json'))
    best = len(e) + len(wn) + len(u)
    log('endgame start: %d errors, %d warnings, %d unconnected' % (len(e), len(wn), len(u)))
    for r in range(rounds):
        if not best:
            break
        bak = os.path.join(work, 'end_bak.kicad_pcb')
        shutil.copy(fin, bak)
        b = pcbnew.LoadBoard(fin)
        bad = set(i['uuid'] for v in e if v['type'] in ('clearance', 'hole_clearance', 'items_not_allowed')
                  for i in v['items'])
        nt = 0
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in bad and t.GetNetname() not in keep and not t.IsLocked() \
                    and not (t.GetClass() == 'PCB_VIA' and in_pad(b, t)):
                pcb.remove(b, t); nt += 1
        left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
        log('endgame round %d: %d pieces in errors out, %d nets open %s' % (r + 1, nt, len(left), left))
        if left and os.environ.get('ENDGAME', 'pathfinder') == 'orders':
            # rip-up in random orders with a big budget, the escapes' locked copper too
            rest = finish.repair_orders(b, left, protect=sorted(keep), widths=w, clmap=cl, log=log,
                                        tries=int(os.environ.get('REPAIR_TRIES', 40)), max_victims=10,
                                        keep_locked=False)
            log('  orders: open %s' % (rest,))
        elif left:
            open_, over = finish.pathfinder(b, left, protect=sorted(keep), widths=w, clmap=cl,
                                            max_iters=int(os.environ.get('PF_ITERS', 60)), log=log)
            log('  pathfinder: open %s, overlapping %s' % (open_, over))
            if open_ or over:
                # overlapping copper is illegal: those nets are torn up and routed with no crossing
                for n_ in over:
                    finish.rip_up(b, n_)
                rest = finish.cluster_endgame(b, sorted(set(open_) | set(over)), protect=sorted(keep), widths=w,
                                              clmap=cl, log=log)
                log('  cluster endgame: open %s' % (rest,))
        pcb.save_board(b, fin)
        write_rules(fin)
        gnd_island_vias(fin)
        hole_pass(fin)
        write_rules(fin)
        cleanup.clean(fin, board.RULES, log=log)
        pcb.set_stackup(fin, inner_oz=0.5)
        e2, wn2, u2 = pcb.drc(fin, os.path.join(work, 'end%d.json' % (r + 1)))
        tot = len(e2) + len(wn2) + len(u2)
        log('endgame round %d DRC: %d errors %s, %d warnings, %d unconnected'
            % (r + 1, len(e2), dict(Counter(v['type'] for v in e2)), len(wn2), len(u2)))
        if tot < best:
            best, e, wn, u = tot, e2, wn2, u2
        else:
            shutil.copy(bak, fin)
            log('  round not kept')
            break
    log('DRC: %d errors %s, %d warnings %s, %d unconnected'
        % (len(e), dict(Counter(v['type'] for v in e)), len(wn), dict(Counter(v['type'] for v in wn)), len(u)))
    return e, wn, u


def local_repair(b, nets, w, cl, protect, margin=1.2, tries=8, seed=1, log=log):
    """The last few open nets, each a short gap boxed in by its neighbours'
    copper: every unlocked track and via of another net (not `protect`)
    within `margin` mm of the gap is torn out, and the open net and the
    torn nets are routed again (their islands joined, locally) in up to
    `tries` orders; an order is kept only if every net ends with no more
    islands than before, else everything is put back.  Returns nets open."""
    import random
    from shapely.geometry import Point, LineString
    from shapely.ops import nearest_points, unary_union
    rnd = random.Random(seed)
    protect = set(protect)
    isl = lambda n: len(finish._net_components(b, n))
    for net in nets:
        if finish.route_net(b, net, track_w=w.get(net, finish.SIG_W), clmap=cl, lock=False) == 0:
            log('   local %-12s routed as it stands' % net)
            continue
        comps = finish._net_components(b, net)
        if len(comps) <= 1:
            continue
        # the closest pair of islands, and the gap's midpoint
        best = None
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                ga = unary_union([g for gl in comps[i].values() for g in gl])
                gb = unary_union([g for gl in comps[j].values() for g in gl])
                d = ga.distance(gb)
                if best is None or d < best[0]:
                    best = (d, nearest_points(ga, gb))
        d, (pa, pb) = best
        zone = Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2).buffer(d / 2 + margin)
        victims = []
        for t in b.GetTracks():
            n_ = t.GetNetname()
            if n_ == net or n_ in protect or t.IsLocked():
                continue
            if t.GetClass() == 'PCB_VIA':
                q = t.GetPosition(); g = Point(finish.mm(q.x), finish.mm(q.y)).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6)
            else:
                s_, e_ = t.GetStart(), t.GetEnd()
                g = LineString([(finish.mm(s_.x), finish.mm(s_.y)), (finish.mm(e_.x), finish.mm(e_.y))])
            if g.intersects(zone):
                victims.append(t)
        group = sorted(set(t.GetNetname() for t in victims))
        base = {n_: isl(n_) for n_ in group}
        done = False
        for k in range(tries):
            before = set(t.m_Uuid.AsString() for t in b.GetTracks())
            for t in victims:
                pcb.remove(b, t)
            order = group[:]; rnd.shuffle(order)
            order = [net] + order if k % 2 == 0 else order + [net]
            for n_ in order:
                finish.route_net(b, n_, track_w=w.get(n_, finish.SIG_W), clmap=cl, lock=False)
            now = {n_: isl(n_) for n_ in group}
            if isl(net) == 1 and all(now[n_] <= base[n_] for n_ in group):
                log('   local %-12s gap %.2f mm, routed on try %d, re-laid %s' % (net, d, k, group))
                done = True
                break
            for t in list(b.GetTracks()):
                if t.m_Uuid.AsString() not in before:
                    pcb.remove(b, t)
            for t in victims:
                b.Add(t)
        if not done:
            log('   local %-12s gap %.2f mm, no order worked (%d tries, nets %s)' % (net, d, tries, group))
            done = spare_ground_vias(b, net, zone, w, cl, isl, log)
    return [x for x in finish.unrouted_nets(b) if x in set(nets)]


def spare_ground_vias(b, net, zone, w, cl, isl, log=log):
    """Ground vias in the gap `zone` that are spare (taken out, ground
    has no more islands: the pads they serve reach the plane another way)
    come out, nearest the gap first, until `net` routes; if it never does
    they all go back.  (3 Nov: the GPS port ESD array's ground-pin via
    stood on the LoRa PA supply pin's only way out.)"""
    from shapely.geometry import Point
    c = zone.centroid
    vias = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND':
            q = t.GetPosition(); p_ = Point(finish.mm(q.x), finish.mm(q.y))
            if zone.contains(p_):
                vias.append((p_.distance(c), t))
    base = isl('GND')
    gone = []
    for _, v in sorted(vias, key=lambda x: x[0]):
        pcb.remove(b, v)
        if isl('GND') > base:
            b.Add(v); continue
        gone.append(v)
        pre = set(t.m_Uuid.AsString() for t in b.GetTracks())
        if finish.route_net(b, net, track_w=w.get(net, finish.SIG_W), clmap=cl, lock=False) == 0:
            q = v.GetPosition()
            log('   local %-12s routed with %d spare ground via(s) out (last at %.2f, %.2f)'
                % (net, len(gone), finish.mm(q.x) - pcb.CX, finish.mm(q.y) - pcb.CY))
            return True
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() not in pre:
                pcb.remove(b, t)
    for v in gone:
        b.Add(v)
    log('   local %-12s no spare ground via made room (%d tried)' % (net, len(vias)))
    return False


ROUND_PASSES = int(os.environ.get('ROUND_PASSES', 5))   # Freerouting passes per saved round
# In1 carries signals too, except under the RF lines and the antenna
# (rf_reference_keepouts): 20 Oct trial, first routing round, 59 open
# signal connections with it against 84 without
ROUTE_IN1 = bool(int(os.environ.get('ROUTE_IN1', 1)))


def run(work, passes=40, from_routed=False):
    os.makedirs(work, exist_ok=True)
    placed = os.path.join(work, 'placed.kicad_pcb')
    routed = os.path.join(work, 'routed.kicad_pcb')
    fin = os.path.join(work, 'fin.kicad_pcb')
    if not from_routed:
        # a resumed run keeps its placed board (and the rounds routed on it)
        if not os.path.exists(placed + '.done'):
            board.build(placed)
            plane_fanout(placed)
            fill(placed)
            open(placed + '.done', 'w').close()
        setup_routers()
        # every stage's board file gets the project (KiCad 10 keeps the
        # rules and net classes there): without it KiCad, the DSN export
        # and the DRC fall back to KiCad's defaults
        pcb.copy_project(placed, routed)
        n = route.route_resumable(placed, routed, passes=ROUND_PASSES, rounds=max(1, passes // ROUND_PASSES), log=log)
        log('Freerouting: %d connections left, %d duplicate vias removed' % (n, pcb.dedupe_vias(routed)))
        write_rules(routed)
    finish_stage(routed, fin, work)
    return fin


if __name__ == '__main__':
    work = sys.argv[1]
    passes = int(sys.argv[sys.argv.index('--passes') + 1]) if '--passes' in sys.argv else 40
    if '--endgame' in sys.argv:
        endgame(os.path.join(work, 'fin.kicad_pcb'), work)
    elif '--from-tail' in sys.argv:
        # the tail again from its saved input (tail_in.kicad_pcb)
        fin = os.path.join(work, 'fin.kicad_pcb'); ti = os.path.join(work, 'tail_in.kicad_pcb')
        shutil.copy(ti, fin); pcb.copy_project(ti, fin)
        comps = circuit.build()
        setup_routers()
        finish_tail(fin, work, widths(comps), clearances(comps))
    elif '--from-clean' in sys.argv:
        # a finished board from the hole pass on (a run that died in the clean-up)
        finish_clean(os.path.join(work, 'fin.kicad_pcb'), work)
    elif '--local-repair' in sys.argv:
        # the tail's input again, its last open nets repaired locally, then the tail
        fin = os.path.join(work, 'fin.kicad_pcb'); ti = os.path.join(work, 'tail_in.kicad_pcb')
        shutil.copy(ti, fin); pcb.copy_project(ti, fin)
        comps = circuit.build(); w, cl = widths(comps), clearances(comps)
        setup_routers()
        b = pcbnew.LoadBoard(fin)
        gone = finish.drop_area_vias(b)
        if gone: log('took out vias where only another net may stand: %s' % (gone,))
        left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
        log('local repair of %s' % (left,))
        rest = local_repair(b, left, w, cl, protect=PLANES + list(board.RF_NETS) + list(board.RF_EXTRA),
                            margin=float(os.environ.get('LOCAL_MARGIN', 1.2)))
        log('after the local repair: open %s' % (rest,))
        b.Save(fin)
        write_rules(fin)
        finish_tail(fin, work, w, cl)
    elif '--from-fin' in sys.argv:
        # the maze router's result as it stands: the supply pours, repair and tail only
        finish_rest(os.path.join(work, 'fin.kicad_pcb'), work)
    else:
        run(work, passes, '--from-routed' in sys.argv)
