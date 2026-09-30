# -*- coding: utf-8 -*-
"""JLCPCB via-in-pad (POFV) hole spacing for a routed board.

JLCPCB fills and caps via-in-pad holes free on 6-20 layer boards
(jlcpcb.com/news/free-via-in-pad-6-20-layer-pcbs-pofv) and asks that each
such via sit more than 0.45 mm from any other hole.  esc_layout.DRU_EXTRA
makes KiCad's DRC check it (every 0.3 mm-drill via is treated as filled);
Freerouting does not know the rule, so its vias can land too close.

nudge_vias() moves each routed via named in a DRC hole_to_hole violation
to the nearest spot where the via, its hole and the track ends dragged
along with it are legal.  Locked (fan-out / in-pad) vias are never moved.
"""
import json, math
import pcbnew
from shapely.geometry import Point, LineString
import fanout, pcb

GAP_FILLED = 0.46      # hole to hole, mm, when either hole is a filled 0.3 mm via
GAP_PLAIN = 0.26       # otherwise (board rule 0.25)
FILLED_R = 0.145       # a hole radius at or above this is a filled via


def _mm(v):
    return v / 1e6


def nudge_vias(path, drc_json, out=None, clearances=None, steps=26, log=print):
    """Returns the number of vias moved."""
    fanout.Obstacles.NET_CL = {n: c for n, c in (clearances or {}).items() if c > 0.1}
    fanout.Obstacles.MARGIN = 0.01
    b = pcbnew.LoadBoard(path)
    cu = pcb.cu_layers(b)
    byid = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
    targets = {}
    for v in json.load(open(drc_json))['violations']:
        if v['type'] != 'hole_to_hole':
            continue
        vs = [byid.get(i['uuid']) for i in v['items']]
        vs = [t for t in vs if t is not None and t.GetClass() == 'PCB_VIA']
        # move the routed one: small drill first, then an unlocked one
        vs.sort(key=lambda t: (t.GetDrillValue() >= pcbnew.FromMM(0.29), t.IsLocked()))
        if vs and not vs[0].IsLocked():
            targets[vs[0].m_Uuid.AsString()] = vs[0]
    moved = 0
    for via in targets.values():
        P = via.GetPosition(); net = via.GetNetname()
        segs = [t for t in b.GetTracks() if t.GetClass() != 'PCB_VIA' and t.GetNetname() == net
                and (t.GetStart() == P or t.GetEnd() == P)]
        for t in segs + [via]:
            b.Remove(t)
        obs = fanout.Obstacles(b, cu)
        d, r = _mm(via.GetWidth(pcbnew.F_Cu)), _mm(via.GetDrillValue()) / 2
        x0, y0 = _mm(P.x), _mm(P.y)
        best = None
        for k in range(1, steps):
            rad = 0.02 * k
            for a in range(24):
                x, y = x0 + rad * math.cos(a * math.pi / 12), y0 + rad * math.sin(a * math.pi / 12)
                g = Point(x, y).buffer(d / 2)
                if any(kp.intersects(g) for kp in obs.keepouts):
                    continue
                ok = all(math.hypot(x - hx, y - hy) - hr - r >= (GAP_FILLED if (hx, hy, hr) in getattr(obs, 'pad_holes', ()) else GAP_PLAIN)
                         for hx, hy, hr in obs.holes)
                if not ok or not obs.clear(g, net, cu, 0.1):
                    continue
                for t in segs:
                    q = t.GetEnd() if t.GetStart() == P else t.GetStart()
                    sg = LineString([(x, y), (_mm(q.x), _mm(q.y))]).buffer(_mm(t.GetWidth()) / 2)
                    if not obs.clear(sg, net, [t.GetLayer()], 0.1):
                        ok = False
                        break
                if ok:
                    best = (x, y)
                    break
            if best:
                break
        NP = pcbnew.VECTOR2I(pcbnew.FromMM(best[0]), pcbnew.FromMM(best[1])) if best else P
        via.SetPosition(NP)
        b.Add(via)
        for t in segs:
            if t.GetStart() == P:
                t.SetStart(NP)
            if t.GetEnd() == P:
                t.SetEnd(NP)
            b.Add(t)
        log('  pofv: %-12s (%.2f, %.2f) -> %s' % (net, x0, y0, '(%.3f, %.3f)' % best if best else 'NOT MOVED'))
        moved += bool(best)
    b.Save(out or path)
    return moved
