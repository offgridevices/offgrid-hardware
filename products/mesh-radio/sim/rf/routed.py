# -*- coding: utf-8 -*-
"""Read the RF geometry off the routed board, for the RF studies.

    tools/kd python3 sim/rf/routed.py      # from products/mesh-radio, ~20 s; writes routed.json and routed.txt

For every RF net (src/board.py RF_NETS + RF_EXTRA) in mesh-radio.kicad_pcb:
  - every track piece: layer, width, length, the part of it outside the net's own pads (the pad is the part's
    node: its body is in the part model), split at every junction and pad, as a line netlist (nodes, edges,
    which pad sits on which node) that rfboard.py builds the networks from;
  - the reference plane under it: the fraction of the line and its 0.12 mm margins that has the layer's
    neighbouring ground (In1 for F.Cu) under it, and which net's copper breaks it where it does not;
  - the coplanar gap, sampled every 0.05 mm on each side: the distance from the line's edge to the first
    copper of another net (0.8 mm ray), the fraction with no copper within 0.8 mm (an open side), and the
    closest approach of each non-ground net;
  - ground vias within 0.6 and 1 mm of it.
Also: each RF shunt part's ground pad (vias in the pad, nearest ground via), the detector diodes' cathode to
their 1 nF along the DC track, and what copper sits in the Bluetooth antenna's ground-free box.
Nothing in the board or src/ is changed.
"""
import heapq
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(V1, 'src'))
import pcbnew                                   # noqa: E402
from shapely.geometry import Polygon, LineString, Point, box   # noqa: E402
from shapely.ops import unary_union             # noqa: E402
import board as BD                              # noqa: E402
import pcb                                      # noqa: E402
import layout                                   # noqa: E402

BOARD = os.environ.get('RF_BOARD', os.path.join(V1, 'mesh-radio.kicad_pcb'))   # (RF_BOARD: a trial board)
CX, CY = pcb.CX, pcb.CY
NETS = BD.RF_NETS + BD.RF_EXTRA
RAY = 0.8          # mm: farther than this the side counts as open (no coplanar ground)
TOL = 0.01         # mm: a point within this of a line lies on it
TXT = []


def out(s=''):
    TXT.append(s)
    print(s)


def mm(v):
    return v / 1e6


def xy(p):
    return (mm(p.x) - CX, mm(p.y) - CY)


def ps_to_shapely(ps):
    polys = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        sh = [xy(o.CPoint(j)) for j in range(o.PointCount())]
        holes = [[xy(ps.Hole(i, h).CPoint(j)) for j in range(ps.Hole(i, h).PointCount())] for h in range(ps.HoleCount(i))]
        if len(sh) >= 3:
            polys.append(Polygon(sh, holes).buffer(0))
    return unary_union(polys)


def main():
    b = pcbnew.LoadBoard(BOARD)
    CU = list(b.GetEnabledLayers().CuStack())
    LN = {l: b.GetLayerName(l) for l in CU}
    LID = {v: k for k, v in LN.items()}
    cop = {l: {} for l in CU}                   # layer -> net -> [shapely]
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in z.GetLayerSet().CuStack():
            if z.HasFilledPolysForLayer(l):
                cop[l].setdefault(z.GetNetname(), []).append(ps_to_shapely(z.GetFilledPolysList(l)))
    segs, vias, allseg = {}, {}, {}
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == 'PCB_VIA':
            x, y = xy(t.GetPosition())
            r = mm(t.GetWidth(pcbnew.F_Cu)) / 2
            for l in CU:
                if t.IsOnLayer(l):
                    cop[l].setdefault(n, []).append(Point(x, y).buffer(r, 16))
            vias.setdefault(n, []).append(dict(x=round(x, 4), y=round(y, 4), d=round(2 * r, 3), drill=round(mm(t.GetDrillValue()), 3),
                                               top=LN[t.TopLayer()], bot=LN[t.BottomLayer()]))
            continue
        l = t.GetLayer()
        w = mm(t.GetWidth())
        a, e = xy(t.GetStart()), xy(t.GetEnd())
        ls = LineString([a, e])
        cop[l].setdefault(n, []).append(ls.buffer(w / 2, 16) if ls.length > 0 else Point(a).buffer(w / 2, 16))
        allseg.setdefault(n, []).append((LN[l], a, e, w))
        if n in NETS:
            segs.setdefault(n, []).append(dict(layer=LN[l], w=round(w, 4), a=a, b=e, locked=bool(t.IsLocked())))
    pads, padpoly = {}, {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            for l in CU:
                if p.IsOnLayer(l) and p.FlashLayer(l):
                    g = ps_to_shapely(p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE))
                    cop[l].setdefault(n, []).append(g)
                    if l == pcbnew.F_Cu:
                        padpoly[(fp.GetReference(), p.GetNumber())] = (n, g)
            if n in NETS or n in ('REFL_DET', 'FWD_DET'):
                pads.setdefault(n, []).append(dict(ref=fp.GetReference(), pin=p.GetNumber(), value=fp.GetValue(),
                                                   xy=[round(v, 4) for v in xy(p.GetPosition())]))
    U = {l: {n: unary_union(g) for n, g in d.items()} for l, d in cop.items()}
    gvias = [(v['x'], v['y']) for v in vias.get('GND', [])]

    # ---------------------------------------------------------------- the line netlist per RF net
    res = dict(board=os.path.relpath(BOARD, V1), nets={}, findings=[])
    OTHER = {}
    for n in NETS:
        ss = segs.get(n, [])
        if not ss:
            continue
        pp = [q for q in pads.get(n, [])]
        pts = [tuple(s['a']) for s in ss] + [tuple(s['b']) for s in ss] + [tuple(q['xy']) for q in pp]
        nodes = []

        def node_of(p):
            for i, q in enumerate(nodes):
                if math.hypot(p[0] - q[0], p[1] - q[1]) <= TOL:
                    return i
            nodes.append(p)
            return len(nodes) - 1
        for p in pts:
            node_of(p)
        edges = []
        for s in ss:
            ln = LineString([s['a'], s['b']])
            on = sorted({ln.project(Point(p)) for p in nodes if ln.distance(Point(p)) <= TOL})
            on = [0.0] + [t for t in on if 1e-6 < t < ln.length - 1e-6] + [ln.length]
            for t0, t1 in zip(on, on[1:]):
                pa, pb = ln.interpolate(t0), ln.interpolate(t1)
                edges.append(dict(layer=s['layer'], w=s['w'], a=node_of((pa.x, pa.y)), b=node_of((pb.x, pb.y)),
                                  geom=LineString([(pa.x, pa.y), (pb.x, pb.y)])))
        # pads: the node at the pad centre (rf_paths draws every line from a pad's centre)
        pad_node = {}
        for q in pp:
            k = node_of(tuple(q['xy']))
            pad_node['%s.%s' % (q['ref'], q['pin'])] = k
        own = unary_union([g for (r_, pn), (nn, g) in padpoly.items() if nn == n])
        l_f = LID['F.Cu']
        for e in edges:
            g = e['geom']
            l = LID[e['layer']]
            e['len'] = round(g.length, 4)
            e['len_out'] = round(g.difference(own).length, 4) if l == l_f else e['len']
            if (l, n) not in OTHER:
                OTHER[(l, n)] = unary_union([gg for nn, gg in U[l].items() if nn != n])
            oth = OTHER[(l, n)]
            i = CU.index(l)
            refs = [CU[j] for j in (i - 1, i + 1) if 0 <= j < len(CU)]
            L = g.length
            e['ref'], e['ref_breaks'] = {}, {}
            if L > 1e-6:
                strip = g.buffer(e['w'] / 2 + 0.12, cap_style=2)
                for r in refs:
                    gg = U[r].get('GND', Polygon())
                    e['ref'][LN[r]] = round(strip.intersection(gg).area / strip.area, 3)
                    miss = strip.difference(gg)
                    if miss.area > 1e-4:
                        brk = {nn: round(x.intersection(miss).area, 4) for nn, x in U[r].items()
                               if nn != 'GND' and x.intersects(miss) and x.intersection(miss).area > 1e-5}
                        brk['(no copper)'] = round(miss.area - sum(brk.values()), 4)
                        e['ref_breaks'][LN[r]] = brk
            (x0, y0), (x1, y1) = g.coords[0], g.coords[-1]
            ux, uy = ((x1 - x0) / L, (y1 - y0) / L) if L > 1e-6 else (1.0, 0.0)
            nx_, ny_ = -uy, ux
            ns = max(2, int(L / 0.05) + 1)
            gaps, close = [], {}
            for k in range(ns):
                f = k / (ns - 1)
                x, y = x0 + f * (x1 - x0), y0 + f * (y1 - y0)
                if l == l_f and own.contains(Point(x, y)):
                    continue                      # inside the part's own pad
                for side in (-1, 1):
                    e0 = (x + side * nx_ * e['w'] / 2, y + side * ny_ * e['w'] / 2)
                    ray = LineString([e0, (e0[0] + side * nx_ * RAY, e0[1] + side * ny_ * RAY)])
                    hit = ray.intersection(oth)
                    if hit.is_empty:
                        gaps.append(None)
                        continue
                    d = Point(e0).distance(hit)
                    gaps.append(round(d, 3))
                    pt = ray.interpolate(d + 0.002)
                    for nn, gg in U[l].items():
                        if nn != n and gg.distance(pt) < 0.003:
                            close[nn] = min(close.get(nn, 9), round(d, 3))
            gl = [x for x in gaps if x is not None]
            e['samples'] = len(gaps)
            e['open_frac'] = round(1 - len(gl) / len(gaps), 3) if gaps else 1.0
            e['gap_min'] = min(gl) if gl else None
            e['gap_median'] = sorted(gl)[len(gl) // 2] if gl else None
            e['below_spec_frac'] = round(sum(1 for x in gl if x < BD.RF_GAP - 0.005) / len(gaps), 3) if gaps else 0.0
            e['closest'] = close
            e['gnd_vias_0p6'] = sum(1 for v in gvias if g.distance(Point(v)) <= 0.6)
            e['gnd_vias_1'] = sum(1 for v in gvias if g.distance(Point(v)) <= 1.0)
            e['xy'] = [[round(x0, 4), round(y0, 4)], [round(x1, 4), round(y1, 4)]]
            del e['geom']
        res['nets'][n] = dict(nodes=[[round(p[0], 4), round(p[1], 4)] for p in nodes], edges=edges, pads=pad_node,
                              vias=vias.get(n, []), length=round(sum(e['len'] for e in edges), 4),
                              layers=sorted({e['layer'] for e in edges}))

    # ---------------------------------------------------------------- shunt parts' ground return
    fg = U[pcbnew.F_Cu].get('GND')
    sh = {}
    for fp in b.GetFootprints():
        nets = {p.GetNetname() for p in fp.Pads()}
        if not (nets & set(NETS + ['REFL_DET', 'FWD_DET'])) or 'GND' not in nets:
            continue
        for p in fp.Pads():
            if p.GetNetname() != 'GND' or not p.IsOnLayer(pcbnew.F_Cu):
                continue
            x, y = xy(p.GetPosition())
            g = padpoly[(fp.GetReference(), p.GetNumber())][1]
            ds = sorted(math.hypot(v[0] - x, v[1] - y) for v in gvias)
            inpad = sum(1 for v in gvias if g.contains(Point(v)))
            edge = min((g.exterior.distance(Point(v)) for v in gvias), default=9) if not inpad else 0.0
            sh.setdefault(fp.GetReference(), []).append(dict(pin=p.GetNumber(), vias_in_pad=inpad, nearest=round(ds[0], 3),
                                                            edge_to_via=round(edge, 3), on_pour=bool(fg is not None and fg.intersects(g)),
                                                            pad=[round(mm(p.GetSize(pcbnew.F_Cu).x), 3), round(mm(p.GetSize(pcbnew.F_Cu).y), 3)]))
    res['shunt_ground'] = sh

    # ---------------------------------------------------------------- detector cathode -> 1 nF along the DC track
    def path_len(net, src, dst):
        """Shortest copper path (tracks, vias joining layers) between two pads of `net`."""
        nd = {}

        def k(p):
            key = (round(p[0], 2), round(p[1], 2))
            nd.setdefault(key, [])
            return key
        for lname, a, e, w in allseg.get(net, []):
            ka, ke = k(a), k(e)
            d = math.hypot(e[0] - a[0], e[1] - a[1])
            nd[ka].append((ke, d))
            nd[ke].append((ka, d))
        keys = list(nd)
        for r_ in (src, dst):
            g = padpoly[r_][1]
            kp = k(xy(next(p for p in b.FindFootprintByReference(r_[0]).Pads() if p.GetNumber() == r_[1]).GetPosition()))
            for q in keys:
                if g.buffer(0.01).contains(Point(q)):
                    nd[kp].append((q, 0.0))
                    nd[q].append((kp, 0.0))
        s0 = k(xy(next(p for p in b.FindFootprintByReference(src[0]).Pads() if p.GetNumber() == src[1]).GetPosition()))
        s1 = k(xy(next(p for p in b.FindFootprintByReference(dst[0]).Pads() if p.GetNumber() == dst[1]).GetPosition()))
        dist, hq = {s0: 0.0}, [(0.0, s0)]
        while hq:
            d, u = heapq.heappop(hq)
            if u == s1:
                return round(d, 3)
            if d > dist.get(u, 1e9):
                continue
            for v, w in nd[u]:
                if d + w < dist.get(v, 1e9):
                    dist[v] = d + w
                    heapq.heappush(hq, (d + w, v))
        return None
    det = {}
    for net in ('REFL_DET', 'FWD_DET'):
        pl = pads.get(net, [])
        dio = [q for q in pl if q['ref'].startswith('D')]
        cap = [q for q in pl if q['ref'].startswith('C')]
        best = None
        for d_ in dio:
            for c_ in cap:
                L = path_len(net, (d_['ref'], d_['pin']), (c_['ref'], c_['pin']))
                if L is not None and (best is None or L < best[0]):
                    best = (L, d_['ref'] + '.' + d_['pin'], c_['ref'] + '.' + c_['pin'])
        layers = sorted({s[0] for s in allseg.get(net, [])})
        det[net] = dict(cathode_to_cap_mm=best[0] if best else None, between=best[1:] if best else None,
                        track_w=sorted({round(s[3], 3) for s in allseg.get(net, [])}), layers=layers,
                        total_mm=round(sum(math.hypot(s[2][0] - s[1][0], s[2][1] - s[1][1]) for s in allseg.get(net, [])), 2),
                        vias=len(vias.get(net, [])))
    res['detector_dc'] = det

    # ---------------------------------------------------------------- Bluetooth antenna box
    x0, y0, x1, y1 = layout.ANT_BOX
    ab = box(x0, y0, x1, y1)
    res['ant_box'] = dict(box=[x0, y0, x1, y1], copper={'%s %s' % (LN[l], n): round(g.intersection(ab).area, 3)
                                                        for l in CU for n, g in U[l].items()
                                                        if g.intersects(ab) and g.intersection(ab).area > 1e-3})
    res['gnd_via_types'] = sorted({(v['d'], v['drill'], v['top'], v['bot']) for v in vias.get('GND', [])})
    json.dump(res, open(os.path.join(os.environ.get('RF_OUT', HERE), 'routed.json'), 'w'), indent=0)
    report(res)
    open(os.path.join(os.environ.get('RF_OUT', HERE), 'routed.txt'), 'w').write('\n'.join(TXT) + '\n')


def report(res):
    out('Mesh Radio v1 - RF lines on the routed board (sim/rf/routed.py, %s)' % res['board'])
    out('Line 0.17 mm on F.Cu over In1 (0.1164 mm); coplanar gap spec %.2f mm (src/board.py RF_GAP).' % BD.RF_GAP)
    out('Per net: length (and outside the parts\' own pads), layers, vias on the net, In1 under the line and 0.12 mm'
        ' beyond its edges, coplanar gap sampled every 0.05 mm each side (open = no copper within %.1f mm), ground vias'
        ' within 0.6 / 1 mm.' % RAY)
    out()
    out('%-11s %7s %7s %-6s %4s %6s %6s %6s %6s %9s  %s' % ('net', 'len', 'outpad', 'layers', 'vias', 'In1min', 'gapmin',
                                                           'open%', '<spec%', 'gndvias', 'closest non-ground copper (mm)'))
    for n, d in res['nets'].items():
        es = d['edges']
        lo = sum(e['len_out'] for e in es)
        ref = min((e['ref'].get('In1.Cu', 1.0) for e in es if e['ref']), default=None)
        gm = min((e['gap_min'] for e in es if e['gap_min'] is not None), default=None)
        ns = sum(e['samples'] for e in es) or 1
        op = sum(e['open_frac'] * e['samples'] for e in es) / ns
        bs = sum(e['below_spec_frac'] * e['samples'] for e in es) / ns
        cl = {}
        for e in es:
            for k, v in e['closest'].items():
                if k != 'GND':
                    cl[k] = min(cl.get(k, 9), v)
        gv = (sum(e['gnd_vias_0p6'] for e in es), sum(e['gnd_vias_1'] for e in es))
        out('%-11s %7.2f %7.2f %-6s %4d %6.3f %6s %6.0f %6.0f %4d/%-4d  %s' % (
            n, d['length'], lo, ','.join(x.replace('.Cu', '') for x in d['layers']), len(d['vias']), ref if ref is not None else -1,
            '%.3f' % gm if gm is not None else '-', 100 * op, 100 * bs, gv[0], gv[1],
            ', '.join('%s %.3f' % kv for kv in sorted(cl.items(), key=lambda kv: kv[1])[:3])))
    out()
    out('Shunt parts\' ground pads (vias in the pad / nearest ground via, mm):')
    out('  ' + '  '.join('%s %s' % (r_, '/'.join(('%d in pad' % q['vias_in_pad']) if q['vias_in_pad'] else ('%.2f' % q['nearest'])
                                                  for q in v)) for r_, v in sorted(res['shunt_ground'].items())))
    out()
    for n, d in res['detector_dc'].items():
        out('%s: diode cathode -> 1 nF %s mm (%s), track %s mm wide; the whole net %.1f mm on %s, %d vias'
            % (n, d['cathode_to_cap_mm'], ' -> '.join(d['between'] or []), '/'.join('%g' % w for w in d['track_w']),
               d['total_mm'], ', '.join(d['layers']), d['vias']))
    out('Bluetooth antenna ground-free box %s: copper inside %s' % (res['ant_box']['box'], res['ant_box']['copper'] or 'none'))
    out('Ground via types (d, drill, from, to): %s' % res['gnd_via_types'])


if __name__ == '__main__':
    main()
