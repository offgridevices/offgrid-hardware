# -*- coding: utf-8 -*-
"""Route and finish the placed board, to a DRC-clean .kicad_pcb.

  1. board.build()          parts, the RF lines (locked), In1 ground plane, rules
  2. plane_fanout()         every ground pad takes its via into In1
  3. Freerouting            every other signal and supply (rounds)
  4. finish (finish.py)     the maze router and rip-up repair for what is left
  5. ground poured on F, In2 and B, stitched to In1; the RF lines keep
     their 0.18 mm coplanar gap to it (board.RULES)
  6. KiCad DRC              must be 0 errors / 0 warnings / 0 unconnected

    kd python3 src/pipeline.py WORKDIR [--passes N] [--from-routed]

Adapted from Ridge 3 Lite's pipeline: one plane (GND on In1), three
routing layers (F, In2, B), and the RF lines kept clear of other copper.
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
    """Every ground pad gets its via into In1 before routing (Freerouting
    routes pad to pad; it does not drop a pad into a plane): in the pad
    itself where it is wide enough (filled and capped, POFV), otherwise just
    outside it on a stub; exposed pads get a grid."""
    import fanout
    b = pcbnew.LoadBoard(path)
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

      - the RF lines' coplanar ground strip on F.Cu (the line's 0.18 mm gap
        plus room for the ground pour beside it): no tracks or vias of
        other nets, so the pour after routing runs along every RF line;
      - a strip along the outline (Freerouting keeps only its own
        clearance from it).

    The In1 plane is marked a power layer (Freerouting routes nothing on
    it; its vias pass through) and every pour is removed (Freerouting reads
    a zone as its outline, overlapping the pads inside it)."""
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
        if t.GetNetname() in board.RF_NETS:
            band.append(line.buffer(t.GetWidth() / 2e6 + board.RF_GAP + 0.3))
        holes.append(line.buffer(t.GetWidth() / 2e6 + 0.12))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                g = fanout.pad_poly(p, pcbnew.F_Cu)
                if g is not None:
                    holes.append(g.buffer(0.12))
    keep = unary_union(band).difference(unary_union(holes))
    k = 0
    for q in _simple(keep):
        if q.area < 0.02:
            continue
        pts = [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
        pcb.rule_area(b, pts, [pcbnew.F_Cu], tracks=True, vias=True, pads=False, pours=False, name='RF ground strip')
        k += 1
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            pcb.remove(b, z)
    b.SetLayerType(pcb.layer_id(pcb.INNER['gnd']), pcbnew.LT_POWER)
    hx, hy, w = pcb.HX, pcb.HY, EDGE
    for x0, y0, x1, y1 in ((-hx, -hy, hx, -hy + w), (-hx, hy - w, hx, hy), (-hx, -hy, -hx + w, hy),
                           (hx - w, -hy, hx, hy)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], board.CU, tracks=True, vias=True,
                      pads=False, pours=False, name='edge keepout')
    return k


def setup_routers():
    finish.ROUTE_LAYERS = [pcbnew.F_Cu] + [pcb.layer_id(n) for n in pcb.INNER['sig']] + [pcbnew.B_Cu]
    # 0.025 mm cells (the SX1262's and the chips' 0.5 mm pitch), searched in
    # a window round each connection first
    finish.SIG_W, finish.SIG_CL = 0.1, 0.1         # the board's default net class
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
    route.DROP_NETS = tuple(PLANES) + tuple(board.RF_NETS)
    route.AUTOROUTE = dict(via_costs=40, plane_via_costs=5, start_ripup_costs=100, fanout=False,
                           directions={'F.Cu': 'horizontal', 'In2.Cu': 'vertical', 'B.Cu': 'horizontal'})


def widths(comps):
    """net -> track width for the maze router: the net class widths."""
    out = {}
    for n in set(v for c in comps for v in c.pins.values() if v):
        if n in board.HEAVY:
            out[n] = 0.6
        elif n in board.POWER:
            out[n] = 0.3
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
        left = finish.repair_orders(b, left, protect=protect, widths=w, clmap=cl, log=log)
        b.Save(fin)
    log('signals left after repair: %s' % (left,))
    return finish_tail(fin, work, w, cl)


def finish_tail(fin, work, w, cl):
    """Ground pour and stitching, the last maze pass, clean-up, POFV
    spacing, stackup and DRC."""
    import stitch, cleanup, pofv
    pcb.tidy_tracks(fin)
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


def run(work, passes=40, from_routed=False):
    os.makedirs(work, exist_ok=True)
    placed = os.path.join(work, 'placed.kicad_pcb')
    routed = os.path.join(work, 'routed.kicad_pcb')
    fin = os.path.join(work, 'fin.kicad_pcb')
    if not from_routed:
        board.build(placed)
        plane_fanout(placed)
        fill(placed)
        setup_routers()
        # every stage's board file gets the project (KiCad 10 keeps the
        # rules and net classes there): without it KiCad, the DSN export
        # and the DRC fall back to KiCad's defaults
        pcb.copy_project(placed, routed)
        n = route.route(placed, routed, passes=passes, rounds=2)
        log('Freerouting: %d connections left, %d duplicate vias removed' % (n, pcb.dedupe_vias(routed)))
        write_rules(routed)
    finish_stage(routed, fin, work)
    return fin


if __name__ == '__main__':
    work = sys.argv[1]
    passes = int(sys.argv[sys.argv.index('--passes') + 1]) if '--passes' in sys.argv else 40
    run(work, passes, '--from-routed' in sys.argv)
