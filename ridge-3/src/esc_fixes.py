# -*- coding: utf-8 -*-
"""The ESC's last connection, finished by written-down edits.

After Freerouting and the finisher, one connection was left open:
M1_GLC, U_GD1 pin 9 (LO3) to the gate of motor 1's FET C.  Both ends were
sealed:

  * pin end: pin 9 sits in a pocket on B.Cu between a GND plane via, pin
    10's escape via and motor 2's back-EMF resistor.  The one spot in that
    pocket with room for a via was under motor 1's VCC run on top.
  * FET end: FET C's gate via was boxed in on In2 and In3 by motor 2's MCU
    escapes (motor 2's MCU sits right behind motor 1's offset FET C).

The edits, applied by pipeline.run('esc') in this order:

  1. pin_escape(): take up those three M1_VCC top segments, put a
     0.35 / 0.2 via in the pocket with a B.Cu stub from pin 9, route M1_VCC
     again round it
  2. (pipeline) finish.repair_tx with up to 14 nets torn up: joins +3V3
  3. fet_end(): take out one M2_NEUTRAL via beside the gate, route M1_GLC
     (In2, then F.Cu into the gate via, 8 mm), route M2_NEUTRAL again

Every step is deterministic: the same routed board gives the same result.
Each is checked by the DRC that follows it in the pipeline, not assumed.
"""
import math
import pcbnew
import pcb, finish, fanout

# motor 1's VCC run on top, over the only via spot beside U_GD1 pin 9
VCC_OVER_PIN9 = [((0.07, 6.61), (1.98, 6.61)), ((1.98, 6.61), (2.35, 6.97)), ((2.35, 6.97), (2.35, 8.49))]
# motor 2's M2_NEUTRAL via that fences FET C's gate via on the inner layers
NEUTRAL_VIA = (4.1, 9.6)


def _xy(p):
    return (p.x / 1e6 - pcb.CX, p.y / 1e6 - pcb.CY)


def _near(a, b, tol=0.011):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def pin_escape(path, via_sig, widths, clmap, log=print):
    """Edit 1.  Returns M1_GLC's islands left (1: the FET end is still
    sealed, which fet_end() opens), or None if the copper it expects is not
    there (a different routing): then nothing is changed."""
    b = pcbnew.LoadBoard(path)
    net = 'M1_GLC'
    pad = next(p for p in b.FindFootprintByReference('U_GD1').Pads() if p.GetNumber() == '9')
    q = pad.GetPosition(); px, py = q.x / 1e6, q.y / 1e6
    ripped = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_VIA' or t.GetNetname() != 'M1_VCC' or t.GetLayer() != pcbnew.F_Cu:
            continue
        s, e = _xy(t.GetStart()), _xy(t.GetEnd())
        if any((_near(s, a) and _near(e, c)) or (_near(s, c) and _near(e, a)) for a, c in VCC_OVER_PIN9):
            pcb.remove(b, t); ripped += 1
    if ripped != len(VCC_OVER_PIN9):
        log('esc_fixes.pin_escape: M1_VCC run not where it was (%d of 3 found): not applied' % ripped)
        return None
    from shapely.geometry import Point, LineString
    layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    saved = fanout.Obstacles.NET_CL, fanout.Obstacles.MARGIN
    fanout.Obstacles.NET_CL = {n: c for n, c in clmap.items() if c > 0.1}
    fanout.Obstacles.MARGIN = 0.005
    obs = fanout.Obstacles(b, layers)
    d, dr = via_sig
    best = None
    for i in range(0, 41):
        for j in range(-15, 16):
            vx, vy = px + 0.35 + i * 0.01, py + j * 0.01
            if not obs.clear(Point(vx, vy).buffer(d / 2), net, layers, 0.1) or not obs.hole_room(vx, vy, dr / 2, 0.45):
                continue
            if not obs.clear(LineString([(px, py), (vx, vy)]).buffer(0.1), net, [pcbnew.B_Cu], 0.1):
                continue
            cost = abs(vy - py) + 0.2 * (vx - px)
            if best is None or cost < best[0]:
                best = (cost, vx, vy)
    fanout.Obstacles.NET_CL, fanout.Obstacles.MARGIN = saved
    if not best:
        log('esc_fixes.pin_escape: no via spot beside U_GD1 pin 9: not applied')
        return None
    _, vx, vy = best
    v = pcb.via(b, vx - pcb.CX, vy - pcb.CY, net, d=d, drill=dr); v.SetLocked(True)
    t = pcbnew.PCB_TRACK(b); t.SetStart(q); t.SetEnd(v.GetPosition()); t.SetWidth(pcbnew.FromMM(0.2))
    t.SetLayer(pcbnew.B_Cu); t.SetNet(pad.GetNet()); t.SetLocked(True); b.Add(t)
    left = {}
    for n in ('M1_VCC', net):
        left[n] = finish.route_net(b, n, track_w=widths.get(n, 0.1), clmap=clmap)
    b.Save(path)
    log('esc_fixes.pin_escape: via at (%.2f, %.2f), islands left %s' % (vx - pcb.CX, vy - pcb.CY, left))
    return left[net]


def fet_end(path, widths, clmap, log=print):
    """Edit 3.  Returns the islands left on M1_GLC and M2_NEUTRAL, or None
    if the via it expects is not there: then nothing is changed."""
    # route with 0.4 mm to the board edge: the finisher's grid rounds its
    # 0.3 mm edge margin a little short on the inner layers
    gi = finish.Grid.__init__

    def grid_init(self, *a, **k):
        k['edge'] = max(k.get('edge', 0.3), 0.4)
        gi(self, *a, **k)
    finish.Grid.__init__ = grid_init
    try:
        b = pcbnew.LoadBoard(path)
        via = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'M2_NEUTRAL'
               and _near(_xy(t.GetPosition()), NEUTRAL_VIA)]
        if len(via) != 1:
            log('esc_fixes.fet_end: M2_NEUTRAL via not where it was: not applied')
            return None
        pcb.remove(b, via[0])
        a = finish.route_net(b, 'M1_GLC', track_w=widths.get('M1_GLC', 0.1), clmap=clmap)
        r = finish.route_net(b, 'M2_NEUTRAL', track_w=widths.get('M2_NEUTRAL', 0.1), clmap=clmap)
        b.Save(path)
    finally:
        finish.Grid.__init__ = gi
    log('esc_fixes.fet_end: M1_GLC %d, M2_NEUTRAL %d islands left' % (a, r))
    return a, r
