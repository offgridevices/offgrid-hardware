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
                                via_drill=board.VIA_SIG[1], width=finish.SIG_W if finish.SIG_W <= 0.1 else 0.1,
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
        for p, bb in zip(pads, bbs):
            net = p.GetNetname()
            if not net or net in board.RF_NETS + board.RF_EXTRA:
                continue
            w, h = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
            if w * h > 0.8:                     # an exposed pad
                continue
            edge = min(bb.GetLeft() - L_, R_ - bb.GetRight(), bb.GetTop() - T_, B_ - bb.GetBottom()) / 1e6
            if edge < 0.05:                     # outer row: leaves on its own layer
                continue
            q = p.GetPosition()
            twin = [o for o, ob in zip(pads, bbs) if o is not p and o.GetNetname() == net
                    and min(ob.GetLeft() - L_, R_ - ob.GetRight(), ob.GetTop() - T_, B_ - ob.GetBottom()) / 1e6 < 0.05
                    and (o.GetPosition() - q).EuclideanNorm() / 1e6 < 0.6]
            if twin:                            # joins its outer neighbour on the surface
                continue
            x, y = q.x / 1e6, q.y / 1e6
            g = Point(x, y).buffer(d / 2, 16)
            ok = obs.hole_room(x, y, drill / 2, hole_gap) and obs.clear(g, net, layers, clearance)
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
    # a via keeps JLCPCB's 0.2 mm hole-to-copper at the 0.1 mm clearance
    finish.VIA_RING = 0.1
    finish.POFV_GAP = None
    route.VIA_IN_PAD = board.VIA_SIG
    route.PRE_EXPORT = routing_keepouts
    route.EXTRA = []
    # ground is the plane; the RF lines are drawn already (locked)
    route.DROP_NETS = tuple(PLANES) + tuple(board.RF_NETS) + tuple(board.RF_EXTRA)
    route.AUTOROUTE = dict(via_costs=40, plane_via_costs=5, start_ripup_costs=100, fanout=False,
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
    pcb.copy_project(routed, fin)
    finish.finish_board(routed, fin, os.path.join(work, 'fin.json'), rules=w, clmap=cl, skip=PLANES)
    write_rules(fin)
    pcb.tidy_tracks(fin)
    b = pcbnew.LoadBoard(fin)
    protect = PLANES + list(board.RF_NETS)
    left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
    log('after the maze router: %d nets open %s' % (len(left), left[:12]))
    if left:
        left = finish.repair_orders(b, left, protect=protect, widths=w, clmap=cl, log=log,
                                    tries=int(os.environ.get('REPAIR_TRIES', 40)))
        b.Save(fin)
    log('signals left after repair: %s' % (left,))
    return finish_tail(fin, work, w, cl)


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
        s_, e_ = t.GetStart(), t.GetEnd()
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
            if inside.contains(g) and obs.clear(g, net, [t.GetLayer()], tcl):
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
    pcb.tidy_tracks(fin)
    fatten(fin)
    write_rules(fin)
    pcb.pour_ground(fin, list(finish.ROUTE_LAYERS), clearance=0.15)
    b = pcbnew.LoadBoard(fin)
    stitch.stitch_ground(b, pitch=1.0, via=board.VIA_SIG, clearance=0.13, log=log)
    b.Save(fin)
    write_rules(fin)
    finish.finish_board(fin, fin, os.path.join(work, 'fin2.json'), rules=w, clmap=cl)
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
    run(work, passes, '--from-routed' in sys.argv)
