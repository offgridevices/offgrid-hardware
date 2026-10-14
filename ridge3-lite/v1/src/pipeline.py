# -*- coding: utf-8 -*-
"""Place, route and finish the board, from circuit.py to a DRC-clean
.kicad_pcb.  Used by make.py --reroute.

  1. board.build()          parts, power copper, planes, rules
  2. Freerouting            everything else (rounds, tidied between)
  3. finish.finish_board()  in-house maze router for what Freerouting left
  4. finish.repair_tx / repair_orders: rip-up and re-route for the last few
  5. ground fill on the free copper of every layer
  6. KiCad DRC              must be 0 errors / 0 warnings / 0 unconnected

    kd python3 pipeline.py WORKDIR [--passes N]
"""
import os, sys, json, shutil
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, route, finish, board, circuit

PLANES = ['GND', 'VBAT']
# every ground pad takes its own via to the plane before routing (most in
# the pad itself, filled): the pour after routing cannot reach the small
# pads boxed in by tracks
GND_FANOUT_ALL = os.environ.get('GND_FANOUT_ALL', '1') == '1'


def log(s):
    print(s, flush=True)


def plane_fanout(path):
    """Every ground and battery pad gets its via into its plane before
    routing (Freerouting routes pad to pad; it does not drop a pad into a
    plane well): in the pad itself where it is wide enough (filled and
    capped), otherwise just outside it on a stub; exposed pads get a grid."""
    import fanout, layout
    b = pcbnew.LoadBoard(path)
    # the strip beside each gate driver (its bootstrap and gate tracks) is
    # kept free of other parts' plane vias while they are placed
    tmp = []
    for n, rot in layout.CHANNELS.items():
        (x0, y0, x1, y1) = layout.DRIVE_STRIP
        pts = [layout.place(rot, u, layout.drv(y) ) for u, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        tmp.append(pcb.rule_area(b, pts, board.CU, tracks=False, vias=True, pads=False, pours=False,
                                 name='drive strip'))
        if not layout.DRV_TURN:
            u0, r0, u1, r1 = layout.drive_gap()
            if r1 > r0:
                pts = [layout.place(rot, u, r) for u, r in ((u0, r0), (u1, r0), (u1, r1), (u0, r1))]
                tmp.append(pcb.rule_area(b, pts, board.CU, tracks=False, vias=True, pads=False, pours=False,
                                         name='drive gap'))
    # and the lane from each USB-C VBUS contact into the board
    fp = b.FindFootprintByReference('J_USB')
    for p in fp.Pads():
        if p.GetNetname() == 'USB_VBUS':
            q = p.GetPosition(); x, y = q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY
            tmp.append(pcb.rule_area(b, [(x + 0.5, y - 0.35), (x + 3.0, y - 0.35), (x + 3.0, y + 0.35),
                                         (x + 0.5, y + 0.35)], board.CU, tracks=False, vias=True, pads=False,
                                     pours=False, name='vbus lane'))
    e = pcb.HALF - 0.45
    inpad = dict(d=board.VIA_SIG[0], drill=board.VIA_SIG[1], cl=0.13, hole_cl=0.2, hole_gap=0.25, min_pad=0.38)
    # battery pads all take their via here; ground pads only where they are
    # exposed pads (under the chips, out of the pour's reach): the rest join
    # the ground pour after routing, stitched to In1 (finish_stage), so the
    # routing layers are not a forest of plane vias
    n, failed = fanout.fanout(b, {'GND', 'VBAT'}, (-e + pcb.CX, -e + pcb.CY, e + pcb.CX, e + pcb.CY),
                              via_d=board.VIA_SIG[0], via_drill=board.VIA_SIG[1], clearance=0.13,
                              stub_w=0.2, ep_pitch=1.8, share=0.6, inpad=inpad, ep_join=0.2, ep_min_area=0.8,
                              ep_only=() if GND_FANOUT_ALL else {'GND'})
    for z in tmp:
        pcb.remove(b, z)
    # the pads with no room for a via of their own: a track, while the
    # board is still empty, to the nearest via or pour of their net
    failed = connect_stranded(b, failed)
    for t in b.GetTracks():
        if t.GetNetname() in ('GND', 'VBAT'):
            t.SetLocked(True)
    preroute(b)
    b.Save(path)
    log('plane fan-out: %d vias, %d pads with no plane connection %s' % (n, len(failed), failed[:12]))
    return failed


# the nets that lose every fight in the crowded corners (the battery
# divider, the current average and the status LED beside the gyro, channel
# 1's comparator inputs, the USB pair): routed first on the empty board and
# fixed, so the rest goes round them
PRE_ROUTE = ['ADC_VBAT', 'CUR', 'LED0_A', 'M1_CMP_B', 'M1_CMP_C', 'USB_DP', 'USB_DM']


def preroute(b):
    setup_routers()
    comps = circuit.build()
    w, cl = widths(comps), clearances(comps)
    for n in PRE_ROUTE:
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        left = finish.route_net(b, n, track_w=w.get(n, finish.SIG_W), clmap=cl, lock=False)
        for t in b.GetTracks():
            if t.GetNetname() == n and t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
        log('pre-routed %s%s' % (n, '' if not left else ' (%d pieces left)' % (left + 1)))


def connect_stranded(b, pads):
    """Join each (ref, pad) of a plane net to the nearest via or pour of
    its net with the maze router (full board, fine grid).  Returns the pads
    still alone."""
    from shapely.geometry import Point
    setup_routers()
    comps = circuit.build()
    cl = clearances(comps)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    saved = finish.WINDOW, finish.COARSE
    finish.WINDOW = finish.COARSE = None
    # a lane 0.7 mm long in front of every other signal pad (away from its
    # part's centre) stays free: a plane stub must not fence a pin in
    import math
    lanes = []
    for fp in b.GetFootprints():
        c = fp.GetPosition()
        for p in fp.Pads():
            if p.GetNetname() in PLANES or not p.GetNetname() or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            q = p.GetPosition()
            dx, dy = (q.x - c.x) / 1e6, (q.y - c.y) / 1e6
            d = math.hypot(dx, dy)
            if d < 0.05:
                continue
            ux, uy = dx / d, dy / d
            bb = p.GetBoundingBox()
            half = max(bb.GetWidth(), bb.GetHeight()) / 2e6
            hw = min(bb.GetWidth(), bb.GetHeight()) / 2e6 + 0.05
            x0, y0 = q.x / 1e6 + ux * half, q.y / 1e6 + uy * half
            x1, y1 = x0 + ux * 0.7, y0 + uy * 0.7
            nx, ny = -uy * hw, ux * hw
            pts = [(x0 + nx - pcb.CX, y0 + ny - pcb.CY), (x1 + nx - pcb.CX, y1 + ny - pcb.CY),
                   (x1 - nx - pcb.CX, y1 - ny - pcb.CY), (x0 - nx - pcb.CX, y0 - ny - pcb.CY)]
            lay = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            lanes.append(pcb.rule_area(b, pts, [lay], tracks=True, vias=True, pads=False, pours=False,
                                       name='escape lane'))
    left = []
    try:
        for ref, num in pads:
            p = [q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]
            net = p.GetNetname()
            a = finish._geom_of(p)
            targets = {}
            for t in b.GetTracks():
                if t.GetNetname() == net and t.GetClass() == 'PCB_VIA':
                    q = t.GetPosition()
                    g = Point(q.x / 1e6, q.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6)
                    for l in finish.ROUTE_LAYERS:
                        targets.setdefault(l, []).append(g)
            for z in b.Zones():
                if z.GetIsRuleArea() or z.GetNetname() != net:
                    continue
                for l in finish.ROUTE_LAYERS:
                    if z.IsOnLayer(l):
                        fp_ = z.GetFilledPolysList(l)
                        for k in range(fp_.OutlineCount()):
                            ol = fp_.Outline(k)
                            pts = [(ol.CPoint(i).x / 1e6, ol.CPoint(i).y / 1e6) for i in range(ol.PointCount())]
                            if len(pts) >= 3:
                                from shapely.geometry import Polygon
                                targets.setdefault(l, []).append(Polygon(pts).buffer(0))
            ok = False
            for tw in (0.2, 0.15, 0.1):
                if finish._route_in(b, net, a, targets, 0.1, tw, None, None, 60_000_000, cl, None, 60, None, None):
                    ok = True
                    break
            if not ok:
                left.append((ref, num))
    finally:
        finish.WINDOW, finish.COARSE = saved
        for z in lanes:
            pcb.remove(b, z)
    return left


def fill(path):
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(path)


def routing_keepouts(b):
    """Rule areas added only to the copy of the board handed to
    Freerouting.  Freerouting treats every pour as a plane that other nets
    may cross, so it would run signals through the power copper and along
    the ground and battery planes.  This adds: no tracks or vias over any
    power pour (battery, phase and source pours, on their layers); no
    tracks on In1 and In4, the planes (vias pass through); and a 0.3 mm
    strip along the edge (Freerouting keeps only its own clearance from the
    outline)."""
    import fanout, stamp
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pours = []                                 # (net, layer, filled copper)
    for z in list(b.Zones()):
        if z.GetIsRuleArea() or z.GetZoneName() in ('GND plane', 'VBAT plane', 'flag plate'):
            continue
        for l in board.CU:
            if not z.IsOnLayer(l):
                continue
            fp_ = z.GetFilledPolysList(l)
            polys = []
            for i in range(fp_.OutlineCount()):
                o = fp_.Outline(i)
                pts = [(o.CPoint(j).x / 1e6, o.CPoint(j).y / 1e6) for j in range(o.PointCount())]
                if len(pts) >= 3:
                    polys.append(Polygon(pts).buffer(0))
            if polys:
                pours.append((z.GetNetname(), l, unary_union(polys)))
    # a pad of another net among a pour's copper on its own layer keeps a
    # way in: its via may stand in the pad (route.VIA_IN_PAD), so the spot
    # is left open on that layer and, for the via, on every pour layer
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(l):
                    g = fanout.pad_poly(p, l)
                    if g is not None:
                        pads.append((p.GetNetname(), l, g.buffer(0.2)))
    trapped = [(n, g) for n, l, g in pads
               if any(pn != n and pl == l and pg.intersects(g) for pn, pl, pg in pours)]
    # and every pad and via standing in a pour (its own net's included)
    # leaves a hole: an item inside a keepout is a standing violation
    from shapely.geometry import Point
    items = {l: [] for l in board.CU}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in board.CU:
                if p.IsOnLayer(l):
                    g = fanout.pad_poly(p, l)
                    if g is not None:
                        items[l].append(g.buffer(0.12))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition()
            g = Point(q.x / 1e6, q.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6 + 0.12)
            for l in board.CU:
                items[l].append(g)
        elif t.GetLayer() in items:
            s_, e_ = t.GetStart(), t.GetEnd()
            from shapely.geometry import LineString
            items[t.GetLayer()].append(LineString([(s_.x / 1e6, s_.y / 1e6), (e_.x / 1e6, e_.y / 1e6)])
                                       .buffer(t.GetWidth() / 2e6 + 0.12))
    k = 0
    for net, l, cu in pours:
        holes = [g for n, g in trapped if n != net] + [g for g in items[l] if g.intersects(cu)]
        keep = cu.difference(unary_union(holes)) if holes else cu
        for q in stamp._simple(keep):
            if q.area < 0.05:
                continue
            pts = [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
            # an inner pour only keeps tracks out: a via through it just
            # gets a clearance hole in the fill
            pcb.rule_area(b, pts, [l], tracks=True, vias=l in (pcbnew.F_Cu, pcbnew.B_Cu), pads=False,
                          pours=False, name='pour keepout')
            k += 1
    # the pours themselves go: Freerouting reads a zone as its outline,
    # which overlaps the pads of other nets inside it (thousands of
    # standing violations, and pins it cannot reach).  Their copper is
    # kept by the keepouts above, their nets by -inc (route.EXTRA).
    # The planes go too: every via of another net through a plane counts
    # as a violation there, and the router then shuns new vias.  Their
    # nets are left out of the routing and their layers are marked as
    # planes below, so nothing is routed on them either way.
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            pcb.remove(b, z)
    h = pcb.HALF
    # In1 and In4 are planes: marked so (Specctra "power" layers), the
    # router keeps its wires off them and its vias pass through.  (A wire
    # keepout over them instead makes every via a violation.)
    for l in (pcb.layer_id(pcb.INNER['gnd']), pcb.layer_id(pcb.INNER['vbat'])):
        b.SetLayerType(l, pcbnew.LT_POWER)
    w = 0.3
    for x0, y0, x1, y1 in ((-h, -h, h, -h + w), (-h, h - w, h, h), (-h, -h, -h + w, h), (h - w, -h, h, h)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], board.CU, tracks=True, vias=True,
                      pads=False, pours=False, name='edge keepout')
    return k


def setup_routers():
    finish.ROUTE_LAYERS = [pcbnew.F_Cu] + [pcb.layer_id(n) for n in pcb.INNER['sig'] + [pcb.INNER['src']]] + \
        [pcbnew.B_Cu]
    # 0.025 mm cells (0.05 closes 0.5 mm-pitch lanes the rounding margin
    # eats), searched in a window round each connection first
    finish.RES = 0.025
    finish.WINDOW = 3.0
    finish.COARSE = 0.05
    finish.VIA_D, finish.VIA_DRILL = board.VIA_SIG
    # a via keeps JLCPCB's 0.2 mm hole-to-copper at the 0.09 mm clearance:
    # other copper sees it with at least a 0.11 mm ring
    finish.VIA_RING = 0.11
    finish.POFV_GAP = None
    route.VIA_IN_PAD = board.VIA_SIG
    route.PRE_EXPORT = routing_keepouts
    # the power nets are poured, fanned out to the planes and finished by
    # the maze router: Freerouting routes the signals only
    route.EXTRA = ['-inc', 'Power']
    route.DROP_NETS = tuple(PLANES)
    route.AUTOROUTE = dict(via_costs=40, plane_via_costs=5, start_ripup_costs=100, fanout=False,
                           directions={'F.Cu': 'horizontal', 'In2.Cu': 'vertical',
                                       'In3.Cu': 'horizontal', 'B.Cu': 'vertical'})


def widths(comps):
    """net -> track width for the maze router."""
    out = {}
    for n in set(v for c in comps for v in c.pins.values() if v):
        if n in ('VBAT', 'GND') or n.endswith('_SRC'):
            out[n] = 0.3
        # the supplies by their current: 5 V up to 0.6 A, the 3.3 V rails
        # and the gate drive's 11 V at most 0.15 A (1 oz: 0.15 mm carries
        # ~1 A for a 10 K rise)
        elif n == '+5V':
            out[n] = 0.2
        elif n in ('+3V3', '+3V3E', 'GVDD', 'GVDD_IN', '+3V3_GYRO'):
            out[n] = 0.15
        elif '_GH' in n or '_GL' in n or '_BST' in n:
            out[n] = 0.15
    return out


def clearances(comps):
    """Router clearances: the battery, motor phases and source nodes see
    up to 16.8 V plus switching overshoot (sim/halfbridge: 25 V peak), so
    0.12 mm round them, as their net class; the rest is 11 V gate drive
    and logic, 0.1 mm (IPC-2221B B4 allows it below 30 V)."""
    nets = set(n for c in comps for n in c.pins.values() if n)
    cl = {n: finish.SIG_CL for n in nets}
    for n in nets:
        if n in ('VBAT', 'GND') or n.endswith('_SRC') or (n[:1] == 'M' and n[2:3] == '_' and n[3:] in 'ABC'):
            cl[n] = 0.12
    return cl


def finish_stage(routed, fin, work):
    """The routing's leftovers and the board's ground:

      1. the maze router and rip-up repair for the signals Freerouting left
         (ground and battery are not routed as tracks)
      2. ground poured on the free copper of every signal layer, stitched to
         the In1 plane on a grid, so the small parts' ground pads join it
         through the pour
      3. the maze router again for whatever is still apart (a ground pad
         the pour could not reach, a battery pad), then clean-up, POFV hole
         spacing, the stackup and KiCad's DRC

    Returns the DRC result."""
    import stitch
    comps = circuit.build()
    w, cl = widths(comps), clearances(comps)
    setup_routers()
    shutil.copy(os.path.splitext(routed)[0] + '.kicad_dru', os.path.splitext(fin)[0] + '.kicad_dru')
    # whatever plane-net copper the autorouter laid comes out: the planes
    # carry those nets, and the tracks would only block the signal layers
    b = pcbnew.LoadBoard(routed)
    k = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in PLANES and not t.IsLocked():
            pcb.remove(b, t); k += 1
    if k:
        b.Save(routed)
        log('removed %d router-made %s tracks and vias' % (k, '/'.join(PLANES)))
    finish.finish_board(routed, fin, os.path.join(work, 'fin.json'), rules=w, clmap=cl, skip=PLANES)
    pcb.write_rules(fin, pcb.POFV_RULES)
    pcb.tidy_tracks(fin)
    return finish_rest(fin, work, w, cl)


def finish_rest(fin, work, w, cl, negotiate=True):
    """finish_stage from the maze router's result on: repair, ground pour
    and stitching, the last maze pass, clean-up and DRC."""
    import stitch
    protect = PLANES + ['+3V3', '+3V3E', '+5V', 'GVDD', 'BEC_SW']
    b = pcbnew.LoadBoard(fin)
    todo = [x for x in finish.unrouted_nets(b) if x not in PLANES]
    log('after the maze router: %d nets open %s' % (len(todo), todo[:12]))
    if todo and negotiate:
        # locked copper (the power tracks and vias, the plane fan-out) stays
        # the supply nets may move too (only the planes and the buck's
        # switch node stay put), at three times a signal's price
        protect = PLANES + ['BEC_SW']
        for n in ('+3V3', '+3V3E', '+5V', 'GVDD', 'GVDD_IN', '+3V3_GYRO'):
            finish.SOFT_WEIGHT.setdefault(n, 3.0)
        if os.environ.get('NEG_ORDER') == 'rev':
            todo = todo[::-1]
        if os.environ.get('ROUTER', 'pathfinder') == 'pathfinder':
            left, overlapping = finish.pathfinder(b, todo, protect=protect, widths=w, clmap=cl,
                                                  grow=float(os.environ.get('NEG_GROW', 1.0)),
                                                  pres_growth=float(os.environ.get('PF_PRES', 1.35)),
                                                  max_iters=int(os.environ.get('PF_ITERS', 40)),
                                                  sweep=int(os.environ.get('PF_SWEEP', 0)), log=log)
            b.Save(fin)
            best = os.path.join(os.environ['NEG_DUMP'], 'pf_best.kicad_pcb') if os.environ.get('NEG_DUMP') else None
            if best and os.path.exists(best):
                shutil.copy(best, fin)
                # (the net classes live in the project file)
                shutil.copy(os.path.splitext(best)[0] + '.kicad_pro', os.path.splitext(fin)[0] + '.kicad_pro')
            # the overlaps left: as few nets as cover them come up, are routed
            # again with no crossing, and what still cannot go is negotiated
            # refine: clear the overlaps with the fewest nets, try every
            # order of each small fighting group, and send what is still
            # open back through a short PathFinder run; again
            left = None
            for k in range(5):
                b.Save(fin)
                ripped = resolve_overlaps(fin, work)
                b = pcbnew.LoadBoard(fin)
                left = sorted(set(ripped) | set(x for x in finish.unrouted_nets(b) if x not in PLANES))
                log('refine %d: open %s' % (k, left))
                if not left:
                    break
                left = finish.cluster_endgame(b, left, protect=protect, widths=w, clmap=cl, log=log)
                if not left:
                    break
                finish.pathfinder(b, left, protect=protect, widths=w, clmap=cl, max_iters=8, grow=4.0,
                                  pres_growth=1.08, log=log)
        else:
            left = finish.negotiate(b, todo, protect=protect, widths=w, clmap=cl, max_rounds=1500,
                                    grow=float(os.environ.get('NEG_GROW', 1.0)), log=log)
        b.Save(fin)
        log('after negotiation: %d nets open %s' % (len(left), left))
    elif todo:
        finish.repair_tx(b, todo, protect=protect, widths=w, clmap=cl, max_victims=14, max_rounds=80, log=log,
                         keep_locked=True)
        b.Save(fin)
    return finish_tail(fin, work, w, cl, protect)


def resolve_overlaps(fin, work):
    """KiCad's DRC on the routed board: the pairs of signal nets whose
    copper breaks clearance, shorts or crosses.  The nets that cover every
    pair (greedily, the net in most pairs first) are torn up and saved.
    Returns them."""
    import re
    e, wn, u = pcb.drc(fin, os.path.join(work, 'overlap_drc.json'))
    pairs = set()
    for v in e:
        if v['type'] not in ('clearance', 'shorting_items', 'tracks_crossing', 'hole_clearance'):
            continue
        ns = sorted(set(re.findall(r'\[([^\]]+)\]', ' '.join(i['description'] for i in v['items']))))
        ns = [n for n in ns if n not in PLANES and n != '<no net>']
        if len(ns) == 2:
            pairs.add(tuple(ns))
    b = pcbnew.LoadBoard(fin)
    # only nets with copper of the router's own can give way
    movable = set(t.GetNetname() for t in b.GetTracks() if not t.IsLocked())
    stuck = [p for p in pairs if not (set(p) & movable)]
    if stuck:
        log('overlaps between fixed copper only: %s' % stuck)
    pairs = {p for p in pairs if set(p) & movable}
    rip = []
    while pairs:
        n = Counter(x for p in pairs for x in p if x in movable).most_common(1)[0][0]
        rip.append(n)
        pairs = {p for p in pairs if n not in p}
    for n in rip:
        finish.rip_up(b, n)
    b.Save(fin)
    log('overlaps: %d nets torn up to clear them %s' % (len(rip), rip))
    return rip


def finish_tail(fin, work, w, cl, protect):
    """The routed board's last steps: repair what is still open, ground
    pour and stitching, the last maze pass, clean-up, POFV spacing,
    stackup and DRC."""
    import stitch
    pcb.tidy_tracks(fin)
    b = pcbnew.LoadBoard(fin)
    left = [x for x in finish.unrouted_nets(b) if x not in PLANES]
    if left:
        left = finish.repair_orders(b, left, protect=protect, widths=w, clmap=cl, log=log)
        b.Save(fin)
    log('signals left after repair: %s' % (left,))
    pcb.tidy_tracks(fin)
    pcb.write_rules(fin, pcb.POFV_RULES)
    # the ground pour and its stitching
    pcb.pour_ground(fin, list(finish.ROUTE_LAYERS), clearance=0.15)
    b = pcbnew.LoadBoard(fin)
    stitch.stitch_ground(b, log=log)
    b.Save(fin)
    pcb.write_rules(fin, pcb.POFV_RULES)
    # whatever the pour left apart (ground pads cut off by tracks, battery)
    finish.finish_board(fin, fin, os.path.join(work, 'fin2.json'), rules=w, clmap=cl)
    pcb.write_rules(fin, pcb.POFV_RULES)
    import cleanup, pofv
    cleanup.clean(fin, pcb.POFV_RULES, log=log)
    dj = os.path.join(work, 'pofv_drc.json')
    e, wn, u = pcb.drc(fin, dj)
    if any(v['type'] == 'hole_to_hole' for v in e):
        pofv.nudge_vias(fin, dj, clearances=cl, log=log)
    pcb.set_stackup(fin, 1.0)            # 1 oz on every layer, black mask, ENIG
    e, wn, u = pcb.drc(fin, os.path.join(work, 'fin_drc.json'))
    log('DRC: %d errors %s, %d warnings %s, %d unconnected'
        % (len(e), dict(Counter(v['type'] for v in e)), len(wn), dict(Counter(v['type'] for v in wn)), len(u)))
    return e, wn, u


def run(work, passes=40):
    os.makedirs(work, exist_ok=True)
    comps = circuit.build()
    placed = os.path.join(work, 'placed.kicad_pcb')
    routed = os.path.join(work, 'routed.kicad_pcb')
    fin = os.path.join(work, 'fin.kicad_pcb')
    board.build(placed)
    plane_fanout(placed)
    fill(placed)
    setup_routers()
    n = route.route(placed, routed, passes=passes, rounds=2)
    log('Freerouting: %d connections left, %d duplicate vias removed' % (n, pcb.dedupe_vias(routed)))
    pcb.write_rules(routed, pcb.POFV_RULES)
    finish_stage(routed, fin, work)
    return fin


if __name__ == '__main__':
    if sys.argv[1] == 'finish':
        # pipeline.py finish WORK: the finishing stage on WORK/routed.kicad_pcb
        w = sys.argv[2]
        finish_stage(os.path.join(w, 'routed.kicad_pcb'), os.path.join(w, 'fin.kicad_pcb'), w)
        raise SystemExit(0)
    work = sys.argv[1]
    passes = int(sys.argv[sys.argv.index('--passes') + 1]) if '--passes' in sys.argv else 40
    run(work, passes)
