"""SmokeBreak v1: from the routed board to the finished one.

    python3 final.py ROUTED.kicad_pcb        -> ../smokebreak.kicad_pcb (+ DRC report)

  * ground fill on every signal layer (lowest priority, after routing so the
    router never saw it), tied in with stitching where it is cut off
  * the routers' neck-down slivers widened to the fab minimum
  * the silkscreen art (make.add_art): the words, the arrows and the lockup
  * stackup (6 layers, black mask, white silk, ENIG), DRC rules
  * KiCad DRC: errors and unconnected items are printed; the board is still
    written so it can be looked at
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

import board as B
import make

MIN_TRACK = 0.1


def ground_fill(b):
    full = B.board_poly(0.5)
    for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu):
        z = B.zone(b, 'GND', layer, full, clearance=0.25, min_width=0.25, priority=0, name='GND fill')
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)      # SMD pads solid, hand-soldered pins relieved
    # the USB-C shell pegs sit by the edge, too hemmed in for thermal spokes:
    # solid to ground (PCBWay solders them in the reflow, not by hand)
    for p in b.FindFootprintByReference('J8').Pads():
        if p.GetNetname() == 'GND':
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def pad_xy(b, ref, num):
    p = [p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num][0].GetPosition()
    return pcbnew.ToMM(p.x) - B.OX, pcbnew.ToMM(p.y) - B.OY


def hand_routes(b):
    """The joins the routers cannot see (none on the compact board: every
    power pad sits inside its own copper)."""
    return


def gate_side_vias(b):
    """The controller's SRC and GATE pins sit side by side above Q1's gate
    pad, with the source copper beyond it: SRC drops through a via just under
    its pin and comes up inside the source copper (In2); GATE gets a via on
    its own short drop to Q1, so Q2's gate (at the far corner) can be reached
    on an inner layer."""
    import finish
    u13, u14, q14 = pad_xy(b, 'U1', '13'), pad_xy(b, 'U1', '14'), pad_xy(b, 'Q1', '4')
    vy = (u13[1] + 0.72 + q14[1] - 0.3) / 2              # midway between U1's pad ends and Q1's gate pad
    sv = (u13[0] - 0.2, vy)
    B.track(b, [u13, (u13[0], u13[1] + 1.0), sv], 0.15, pcbnew.F_Cu, 'SRC')    # straight down past BST's pad
    B.via(b, *sv, 'SRC', d=0.45, drill=0.2)
    sv2 = (q14[0] + 1.07, q14[1] - 0.3)                  # inside the source copper, east of Q1's gate
    B.track(b, [sv, (sv[0] + 0.3, sv[1] + 0.7), sv2], 0.15, pcbnew.In2_Cu, 'SRC')   # under GATE's via
    B.via(b, *sv2, 'SRC', d=0.45, drill=0.2)
    B.via(b, u14[0], vy, 'GATE', d=0.45, drill=0.2)
    if not any(t.GetNetname() == 'GATE' and t.GetClass() == 'PCB_TRACK' and t.GetLayer() == pcbnew.F_Cu
               and abs(pcbnew.ToMM(t.GetStart().x) - B.OX - u14[0]) < 0.05 for t in b.GetTracks()):
        B.track(b, [u14, (u14[0], vy), q14], 0.2, pcbnew.F_Cu, 'GATE')


def stitch_ok(x, y):
    """Stitching stays out of the art's fields and the screw keep-outs."""
    from shapely.geometry import Point, Polygon
    import math
    P = Point(x, y)
    if any(Polygon(poly).buffer(0.4).contains(P) for name, poly in make.ART_FIELDS):
        return False
    return all(math.hypot(x - hx, y - hy) > 4.4 for hx, hy in B.HOLES)


_VIN = None


def _in_vin_plane(x, y, m=0.65):
    global _VIN
    from shapely.geometry import Point, Polygon
    if _VIN is None:
        _VIN = Polygon(make.VIN_PLANE)
    return _VIN.buffer(-m).contains(Point(x, y)) if m else _VIN.contains(Point(x, y))


def vin_bridge(b):
    """VIN pads east of the In4 split (over the VOUT plane: R1, the
    controller's VS filter) get a via down into the VIN plane on the nearest
    spot the maze router's grid says is free on every layer."""
    import finish, finish_run
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    if len(finish.islands(b, 'VIN')) <= 1:
        return 'not needed'
    east, pts = {}, []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            q = p.GetPosition()
            x, y = pcbnew.ToMM(q.x) - B.OX, pcbnew.ToMM(q.y) - B.OY
            if p.GetNetname() == 'VIN' and p.GetDrillSize().x == 0 and not _in_vin_plane(x, y, 0):
                pts.append((x, y))
                for l, g in finish._geom_of(p).items():
                    east.setdefault(l, []).extend(g)
    if not pts:
        return 'no VIN pad east of the split'
    px, py = pts[0]
    cl = finish_run.rules()[1]
    x0, y0 = max(0.5, px - 9), max(0.5, py - 9)
    g = finish.Grid(b, finish.ROUTE_LAYERS, 0.2, 0.2, 0.45, clmap=cl,
                    window=(B.OX + x0, B.OY + y0, B.OX + px + 9, B.OY + py + 9))
    g.build('VIN')
    free = []
    for i in range(180):
        for j in range(180):
            x, y = x0 + 0.1 * i, y0 + 0.1 * j
            if not _in_vin_plane(x, y):
                continue
            ci, cj = g.cell(B.OX + x, B.OY + y)
            if 0 <= cj < g.vblock.shape[0] and 0 <= ci < g.vblock.shape[1] and not g.vblock[cj, ci]:
                free.append((x, y))
    free.sort(key=lambda p: (p[0] - px) ** 2 + (p[1] - py) ** 2)
    for x, y in free[:40]:
        v = B.via(b, x, y, 'VIN', d=0.45, drill=0.2)
        res = finish.route_connection(b, 'VIN', east, finish._geom_of(v), track_w=0.2, clmap=cl)
        if res:
            return (round(x, 2), round(y, 2)) + tuple(res)
        B.remove(b, v)
    return None


def stitch(b, pitch=3.0, margin=0.45):
    """Ground stitching vias wherever every ground fill has room for one."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    fills = {}
    for z in b.Zones():
        if z.GetZoneName() == 'GND fill':
            for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu):
                if z.IsOnLayer(l):
                    ps = z.GetFilledPolysList(l)
                    polys = []
                    for k in range(ps.OutlineCount()):
                        o = ps.Outline(k)
                        holes = [[(pcbnew.ToMM(ps.CHole(k, h).CPoint(i).x), pcbnew.ToMM(ps.CHole(k, h).CPoint(i).y))
                                  for i in range(ps.CHole(k, h).PointCount())] for h in range(ps.HoleCount(k))]
                        polys.append(Polygon([(pcbnew.ToMM(o.CPoint(i).x), pcbnew.ToMM(o.CPoint(i).y))
                                              for i in range(o.PointCount())], [h for h in holes if len(h) > 2]))
                    fills[l] = unary_union(polys).buffer(-margin)
    if len(fills) < 4:
        return 0
    holes = [t.GetPosition() for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    holes += [p.GetPosition() for fp in b.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    holes = [(pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)) for q in holes]
    n = 0
    y = 2.0
    while y < B.H - 2:
        x = 2.0
        while x < B.W - 2:
            P = Point(B.OX + x, B.OY + y)
            if stitch_ok(x, y) and all(f.contains(P) for f in fills.values()) and all(
                    (hx - P.x) ** 2 + (hy - P.y) ** 2 > 1.2 ** 2 for hx, hy in holes):
                B.via(b, x, y, 'GND', d=0.5, drill=0.25)
                holes.append((P.x, P.y))
                n += 1
            x += pitch
        y += pitch
    return n


def widen(b):
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK' and t.GetWidth() < pcbnew.FromMM(MIN_TRACK):
            t.SetWidth(pcbnew.FromMM(MIN_TRACK))
            n += 1
    return n


def drc(path):
    out = os.path.join(os.path.dirname(os.path.abspath(path)), 'src', 'out', 'drc-final.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--format', 'json',
                    '-o', out, path], capture_output=True)
    r = json.load(open(out))
    errs = [v for v in r['violations'] if v['severity'] == 'error']
    warns = [v for v in r['violations'] if v['severity'] != 'error']
    return errs, warns, r['unconnected_items']


def seal(b):
    """Fill, stitch, save, stackup, DRC rules, DRC report."""
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    print('stitching vias', stitch(b))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(make.OUT, b)
    B.set_stackup(make.OUT, inner_oz=1.0)
    extra = ''.join('(rule "no other track across the %s copper"\n'
                    '  (condition "A.Type == \'Track\' && A.NetName != \'%s\' && A.intersectsArea(\'%s\')")\n'
                    '  (constraint disallow track))\n' % (zn, net, zn)
                    for zn, net in (('sources', 'SRC'), ('Q1 drain', 'VIN'), ('battery minus', 'BATT_NEG'),
                                    ('battery plus', 'VBAT'), ('fuse load side', 'VIN'), ('Q2 drain', 'VOUT'),
                                    ('Q11 sources', 'GND'), ('shunt GND', 'GND')))
    # the drone-negative strip also hosts C14's and the snubber's short VOUT stubs
    extra += ('(rule "no other track across the drone negative copper"\n'
              '  (condition "A.Type == \'Track\' && A.NetName != \'DRONE_NEG\' && A.NetName != \'VOUT\' '
              '&& A.NetName != \'VOUT_SNUB\' && A.intersectsArea(\'drone negative\')")\n'
              '  (constraint disallow track))\n')
    B.write_rules(make.OUT, extra)
    errs, warns, unc = drc(make.OUT)

    import collections
    print('DRC errors', len(errs), collections.Counter(v['type'] for v in errs))
    print('DRC warnings', len(warns), collections.Counter(v['type'] for v in warns))
    print('unconnected', len(unc))


def tail(b):
    """After the routing: the VIN bridge, the fills, the art, the seal."""
    print('VIN bridge', vin_bridge(b), flush=True)
    ground_fill(b)
    # the routing keep-outs become DRC rules (a rule area would bar the power
    # nets' own tracks too)
    for z in list(b.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName().startswith('keepout '):
            B.remove(b, z)
    placed = make.add_art(b, os.path.join(B.HERE, 'out'))
    for p in placed:
        print('  art', p, flush=True)
    seal(b)


if __name__ == '__main__' and sys.argv[1] == '--fix':
    # a routed, finished board (before the fills): the gate-side vias, the
    # exact-pair finishing again, then the tail
    import finish, finish_run
    finish_run.copy_project(make.OUT, sys.argv[2])      # the net classes live in the project file
    b = pcbnew.LoadBoard(sys.argv[2])
    gate_side_vias(b)
    finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    finish.VIA_D, finish.VIA_DRILL, finish.RES = 0.45, 0.2, 0.025
    tmp = os.path.join(B.HERE, 'out', 'prefill.kicad_pcb')
    b.Save(tmp)
    finish_run.copy_project(make.OUT, tmp)
    w, c = finish_run.rules()
    left = finish.finish_board(tmp, tmp, os.path.join(B.HERE, 'out', 'finish-final.json'), rules=w, clmap=c)
    print('exact-pair finishing left', left, flush=True)
    tail(pcbnew.LoadBoard(tmp))
elif __name__ == '__main__' and sys.argv[1] == '--tail':
    # resume after the exact-pair finishing (out/prefill.kicad_pcb holds it)
    tail(pcbnew.LoadBoard(os.path.join(B.HERE, 'out', 'prefill.kicad_pcb')))
elif __name__ == '__main__':
    src = sys.argv[1]
    b = pcbnew.LoadBoard(src)
    print('widened', widen(b), 'slivers')
    # each FET's three source pins strapped together, then the SRC net
    # (driver sense pin, BST cap, the source copper) joined by the maze router
    for ref in ('Q1', 'Q2'):
        fp = b.FindFootprintByReference(ref)
        src = sorted((p.GetPosition() for p in fp.Pads() if p.GetNetname() == 'SRC'), key=lambda q: (q.x, q.y))
        for a_, c_ in zip(src, src[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(a_); t.SetEnd(c_); t.SetWidth(pcbnew.FromMM(0.6)); t.SetLayer(pcbnew.F_Cu)
            t.SetNet(b.FindNet('SRC')); b.Add(t)
    hand_routes(b)
    # every join is routed before the ground fills exist (to the maze
    # router a fill is solid copper): the gate side again on its own, then the
    # exact pairs KiCad still finds open
    import finish, finish_run
    finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    finish.VIA_D, finish.VIA_DRILL, finish.RES = 0.45, 0.2, 0.025
    import gate_side
    gate_side.reroute(b)
    tmp = os.path.join(B.HERE, 'out', 'prefill.kicad_pcb')
    b.Save(tmp)
    finish_run.copy_project(make.OUT, tmp)
    w, c = finish_run.rules()
    left = finish.finish_board(tmp, tmp, os.path.join(B.HERE, 'out', 'finish-final.json'), rules=w, clmap=c)
    print('exact-pair finishing left', left)
    b = pcbnew.LoadBoard(tmp)
    tail(b)
