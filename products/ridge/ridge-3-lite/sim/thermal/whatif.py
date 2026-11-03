# -*- coding: utf-8 -*-
"""Copper I^2 R breakdown and copper what-ifs on the placed (unrouted) board.

    tools/kd python3 sim/thermal/whatif.py [BOARD] [--only base,a,b,c,d,e] [--air wash,halfwash]

Variants (cumulative where stated):
  base  the board as placed (1 oz on all six layers, JLC-like dielectrics)
  a     + GND fill on F.Cu, In2, In3, B.Cu wherever free (0.2 mm clearance to other
        nets, 0.3 mm to the edge), stitched to In1 with 0.3 mm vias on a 1.41 mm
        grid (1 per 2 mm2) wherever F, In1, In2, In3 and B are all GND there
  b     a + each battery pad with a 3 x 4 array of 0.3 mm vias in the pad and 10
        more in a 1 mm ring of the pad's net around it; R_S1's GND pad with 8 vias
  c     b with 2 oz (70 um) inner layers
  d     b with 2 oz outer layers
  e     b with AM32 temperature derating as a cap: each channel's current
        scaled until its ESC MCU is at or below 100 C (steady, sustained)

Runs full60 at 50 C in the sun (prop wash and h halved), the breakdown of the
copper heat at t = 60 s for the base board, and writes results-placed.md here
plus maps under out/thermal/whatif/."""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thermal as th          # noqa: E402
import cases                  # noqa: E402

BOARD = os.path.join(th.REPO, 'out', 'thermal', 'r3lite', 'r3lite_placed.kicad_pcb')
STACK = [0.1, 0.5, 0.18, 0.5, 0.1]
OUT = os.path.join(th.REPO, 'out', 'thermal', 'whatif')
LOSSES = os.path.join(HERE, '..', 'losses.csv')
DRAIN, SOURCE = cases.DRAIN, cases.SOURCE


# ---------------------------------------------------------------------------
#  geometry edits
# ---------------------------------------------------------------------------
def px(g, x, y):
    return int((y - g.y0) / g.ds), int((x - g.x0) / g.ds)


def grow(mask, mm, ds):
    """Dilate a sub-pixel mask by mm."""
    if not mask.any():
        return mask
    return ndimage.distance_transform_edt(~mask) * ds <= mm


def gnd_fill(g, clear=0.2, edge=0.3, pitch=math.sqrt(2.0)):
    L = {n: k for k, n in enumerate(g.cu_names)}
    b = g.board()
    inside = ndimage.distance_transform_edt(b) * g.ds > edge
    area = {}
    for name in ('F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu'):
        l = L[name]
        other = g.copper(l) & ~g.net_copper('GND', l)
        free = inside & ~grow(other, clear, g.ds)
        g.add_copper(l, 'GND', free)
        area[name] = float(free.sum()) * g.ds ** 2
    # a stitching via needs GND under it on both faces and on the In1 plane; on
    # In2-In4 it joins GND where there is some, else passes an antipad
    need = [L[n] for n in ('F.Cu', 'In1.Cu', 'B.Cu')]
    gnd = [g.net_copper('GND', l) for l in need]
    # where a 0.5 mm via pad fits wholly in GND on all three: erode each GND mask by the pad radius
    ok = np.ones_like(b)
    for m_ in gnd:
        ok &= ndimage.distance_transform_edt(m_) * g.ds > 0.25
    placed = [(v['x'], v['y']) for v in g.vias]
    taken = []
    n = 0
    # candidates on a 0.25 mm grid, accepted greedily at >= pitch from each other
    # (1 per 2 mm2 where the copper allows) and >= 0.45 mm from any existing via
    for y in np.arange(g.y0 + 0.5, g.y0 + g.ny * g.d - 0.5, 0.25):
        for x in np.arange(g.x0 + 0.5, g.x0 + g.nx * g.d - 0.5, 0.25):
            r, c = px(g, x, y)
            if not ok[r, c]:
                continue
            if any((x - a) ** 2 + (y - b_) ** 2 < pitch ** 2 for a, b_ in taken):
                continue
            if any((x - a) ** 2 + (y - b_) ** 2 < 0.45 ** 2 for a, b_ in placed):
                continue
            taken.append((x, y))
            g.vias.append(dict(x=float(x), y=float(y), drill=0.3, top=0, bot=len(g.cu_names) - 1, net='GND',
                               added='stitch'))
            n += 1
    return dict(fill_mm2=area, stitch_vias=n, stitch_area_mm2=round(float(ok.sum()) * g.ds ** 2))


def pad_vias(g, ref, num, inner, ring, ring_mm=1.0):
    """inner: (cols, rows) array of 0.3 mm vias inside the pad; ring: vias in a
    ring_mm-wide pour of the pad's net around it (the pour is added too)."""
    f = g.fp(ref)
    p = [q for q in f['pads'] if q['num'] == num][0]
    l = p['layers'][0]
    pts = np.vstack(p['polys'][l])
    x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    added = 0
    cols, rows = inner
    for i in range(cols):
        for j in range(rows):
            x = x0 + (x1 - x0) * (i + 0.5) / cols
            y = y0 + (y1 - y0) * (j + 0.5) / rows
            g.vias.append(dict(x=x, y=y, drill=0.3, top=0, bot=len(g.cu_names) - 1, net=p['net'], added=ref))
            added += 1
    padmask = g.raster([pts])
    other = g.copper(l) & ~g.net_copper(p['net'], l)
    pour = grow(padmask, ring_mm, g.ds) & ~grow(other, 0.2, g.ds) & g.board()
    g.add_copper(l, p['net'], pour)
    # ring vias on the rectangle 0.55 mm outside the pad, evenly by perimeter
    e = 0.55
    X0, Y0, X1, Y1 = x0 - e, y0 - e, x1 + e, y1 + e
    per = 2 * ((X1 - X0) + (Y1 - Y0))
    cand = []
    for k in range(4 * ring):
        s = per * k / (4 * ring)
        if s < X1 - X0:
            x, y = X0 + s, Y0
        elif s < (X1 - X0) + (Y1 - Y0):
            x, y = X1, Y0 + s - (X1 - X0)
        elif s < 2 * (X1 - X0) + (Y1 - Y0):
            x, y = X1 - (s - (X1 - X0) - (Y1 - Y0)), Y1
        else:
            x, y = X0, Y1 - (s - 2 * (X1 - X0) - (Y1 - Y0))
        r, c = px(g, x, y)
        if 0 <= r < g.H and 0 <= c < g.W and pour[max(r - 6, 0):r + 7, max(c - 6, 0):c + 7].all():
            cand.append((x, y))
    step = max(1, len(cand) // ring) if cand else 1
    for x, y in cand[::step][:ring]:
        g.vias.append(dict(x=x, y=y, drill=0.3, top=0, bot=len(g.cu_names) - 1, net=p['net'], added=ref))
        added += 1
    return added


def build(variant):
    P = th.Params
    P.cell_mm, P.ss = 0.2, 8
    P.stack = STACK
    P.inner_oz = 2.0 if variant == 'c' else 1.0
    P.outer_oz = 2.0 if variant == 'd' else 1.0
    g = th.load_kicad(BOARD, P)
    info = {}
    if variant in 'bcde':
        info['vias_bat+'] = pad_vias(g, 'P_BAT+', '1', (3, 4), 10)
        info['vias_bat-'] = pad_vias(g, 'P_BAT-', '1', (3, 4), 10)
        info['vias_rs1'] = pad_vias(g, 'R_S1', '2', (2, 2), 4, ring_mm=0.8)
    if variant in 'abcde':
        info.update(gnd_fill(g))
    g.name = 'r3lite_' + variant
    topo = cases.topology('aio3', g)
    m = th.Model(g, topo, P)
    print('  variant %s: %s' % (variant, info))
    return g, topo, m, info


# ---------------------------------------------------------------------------
#  analysis
# ---------------------------------------------------------------------------
def via_region(g, v):
    for ref in ('P_BAT+', 'P_BAT-'):
        f = g.fp(ref)
        if math.hypot(v['x'] - f['x'], v['y'] - f['y']) < 3.0:
            return 'battery pad ' + ref[-1]
    for n in range(1, 5):
        f = g.fp('R_S%d' % n)
        if f and any(math.hypot(v['x'] - p['x'], v['y'] - p['y']) < 1.5 for p in f['pads'][:2]):
            return 'shunt R_S%d pads' % n
    for f in g.fps:
        if f['ref'].startswith('Q') and f['bx'] - 0.3 <= v['x'] <= f['bx'] + f['w'] + 0.3 and \
                f['by'] - 0.3 <= v['y'] <= f['by'] + f['h'] + 0.3:
            return 'FET drain-tab vias M%s' % f['ref'][1]
    return 'other vias'


def group(net):
    if net in ('VBAT', 'GND'):
        return net
    if net.endswith('_SRC'):
        return net
    return net[:2] + ' phases'          # M1_A, M1_B, M1_C -> M1 phases


def breakdown(g, m, dv, T):
    """Copper heat at field T, split by net group, layer and via region."""
    nL = m.nL
    alpha = m.P.alpha_cu
    by_net, by_layer, by_via = {}, {}, {}
    cellmap = np.zeros(m.nb)
    net_cell = {}
    for wgt, inj in dv.joule:
        key = tuple((r, tuple(p), round(i, 9)) for r, p, i in inj)
        if m.joule_map(inj) is None:
            continue
        det = m.jdetail[key]
        ip = wgt * det['inplane'] * (1 + alpha * (T[:m.nb] - 20))
        grp = group(det['net'])
        by_net[grp] = by_net.get(grp, 0.0) + ip.sum()
        for l in range(nL):
            by_layer[g.cu_names[l]] = by_layer.get(g.cu_names[l], 0.0) + ip[l::nL].sum()
        cellmap += ip
        nc = net_cell.setdefault(grp, np.zeros(m.nb)); nc += ip
        for vi, (w, a, b) in det['vias'].items():
            q = wgt * w * (1 + alpha * ((T[a] + T[b]) / 2 - 20))
            reg = via_region(g, g.vias[vi])
            by_via[reg] = by_via.get(reg, 0.0) + q
            by_net[grp] += q
            cellmap[a] += q / 2; cellmap[b] += q / 2
            nc[a] += q / 2; nc[b] += q / 2
    # hot spots: heat within 1 mm, all layers
    percell = cellmap.reshape(-1, nL).sum(1)
    grid = np.zeros((g.ny, g.nx))
    grid[m.cpos] = percell
    rr = int(round(1.0 / g.d))
    yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
    disk = (xx ** 2 + yy ** 2 <= rr ** 2).astype(float)
    w1 = ndimage.convolve(grid, disk, mode='constant')
    spots, taken = [], []
    for k in np.argsort(-w1.ravel()):
        j, i = divmod(int(k), g.nx)
        if len(spots) >= 10 or w1[j, i] <= 0:
            break
        x, y = g.x0 + (i + .5) * g.d, g.y0 + (j + .5) * g.d
        if any(math.hypot(x - a, y - b) < 2.0 for a, b in taken):
            continue
        taken.append((x, y))
        near = [c for c in range(m.nc) if (m.cpos[0][c] - j) ** 2 + (m.cpos[1][c] - i) ** 2 <= rr ** 2]
        nets = {n: float(a.reshape(-1, nL)[near].sum()) for n, a in net_cell.items()}
        lay = cellmap.reshape(-1, nL)[near].sum(0)
        refs = sorted(g.fps, key=lambda f: (f['x'] - x) ** 2 + (f['y'] - y) ** 2)[:3]
        spots.append(dict(x=x, y=y, W=float(w1[j, i]), net=max(nets, key=nets.get), layer=g.cu_names[int(np.argmax(lay))],
                          near=' '.join(f['ref'] for f in refs)))
    return by_net, by_layer, by_via, spots


def path_resistances(m):
    out = {}
    for n in range(1, 5):
        def R(inj):
            if m.joule_map(inj) is None:
                return float('nan')
            return m.jdetail[tuple((r, tuple(p), round(i, 9)) for r, p, i in inj)]['R'] * 1e3
        out['M%d' % n] = dict(
            bat_to_HS_drains=R([('P_BAT+', ['1'], 1.0)] + [('Q%d%sH' % (n, ph), DRAIN, -1 / 3.) for ph in 'ABC']),
            LS_sources_to_shunt=R([('R_S%d' % n, ['1'], 1.0)] + [('Q%d%sL' % (n, ph), SOURCE, -1 / 3.) for ph in 'ABC']),
            shunt_to_BAT_minus=R([('R_S%d' % n, ['2'], 1.0), ('P_BAT-', ['1'], -1.0)]),
            phaseA_HS_to_pad=R([('P_M%dA' % n, ['1'], 1.0), ('Q%dAH' % n, SOURCE, -1.0)]),
            phaseA_LS_to_pad=R([('P_M%dA' % n, ['1'], 1.0), ('Q%dAL' % n, DRAIN, -1.0)]))
    return out


def metrics(g, m, topo, T, res):
    rows = res['parts']
    def mx(test):
        v = [r['T_j'] for r in rows if test(r)]
        return max(v) if v else float('nan')
    nL = m.nL
    bat = []
    for ref in ('P_BAT+', 'P_BAT-'):
        f = g.fp(ref)
        cells, areas = m.pad_cells(f, None, nL - 1 if f['side'] else 0)
        bat.append(float(T[cells * nL + (nL - 1 if f['side'] else 0)].max()))
    tr = res.get('transient', {}).get('peak', {})
    return dict(FET=tr.get('FET junction max', mx(lambda r: r['kind'] == 'fet')),
                MCU=tr.get('ESC MCU max', mx(lambda r: r['name'].startswith('U_E'))),
                X5R=mx(lambda r: r['kind'] == 'capX5R'), shunt=mx(lambda r: r['name'].startswith('R_S')),
                batpad=max(bat), board=max(b for a, b in res['layers'].values()),
                copper=res['powers'].get('copper I2R', 0.0), fets_W=sum(v for k, v in res['powers'].items() if k.startswith('Q')))


def derate(g, m, topo, losses, air='halfwash', target=100.0):
    """AM32 temperature derating as a current cap, steady (sustained) full throttle.
    First the common factor k (all four channels equal, as the flight
    controller must fly them) at which the hottest ESC MCU sits at target;
    then each channel refined on its own (damped) so every MCU is at or
    below target.  Duty, motor-can temperature and air speed follow the
    load line for the derated current."""
    env = dict(Ta=50.0, air=air, sun=True)
    s = th.Solver(m)
    mcu = ['U_E%d' % n for n in range(1, 5)]
    cache = {}

    def solve(k, T0=None):
        dv = cases.drive_for('aio3', topo, dict(cases.LOADS['full'], scale=list(k), name='full'), env, losses)
        T, pw = s.steady(dv, T0=T0, verbose=False)
        return T, [float(T[m.junc[u]]) for u in mcu]
    T, Tb = solve([1e-3] * 4)
    # common factor by bisection on the hottest MCU
    lo, hi, Tlo = 0.0, 1.0, T
    pts = []
    T1, M1 = solve([1.0] * 4, T)
    pts.append((1.0, max(M1)))
    if max(M1) <= target:
        kc, Tc, Mc = 1.0, T1, M1
    else:
        kc, Tc, Mc = 0.0, T, Tb
        for it in range(9):
            mid = 0.5 * (lo + hi)
            Tm_, Mm = solve([mid] * 4, Tlo)
            pts.append((mid, max(Mm)))
            print('    common k %.3f: MCU %s' % (mid, np.round(Mm, 1)))
            if max(Mm) <= target:
                lo, Tlo, kc, Tc, Mc = mid, Tm_, mid, Tm_, Mm
            else:
                hi = mid
    # MCU sensitivity to its channel's current near the common point (K per unit k), from the bisection
    pts.sort()
    near = [p_ for p_ in pts if p_[0] >= kc]
    slope = (near[1][1] - near[0][1]) / (near[1][0] - near[0][0]) if len(near) > 1 else 40.0
    slope = max(slope, 10.0)
    common = dict(k=kc, I=15.0 * kc, MCU=Mc, FET=fets(m, topo, Tc), extra=extras(m, topo, Tc), slope=slope)
    # per channel, from the common point: each channel moves by its own MCU's
    # headroom / slope (a quarter of the common slope, since the common slope
    # moved all four), at most 0.08 per step, bounded iterations
    k = np.full(4, kc)
    T, Mt = Tc, list(Mc)
    for it in range(8):
        step = np.clip([(target - 0.2 - t) / (slope / 2.0) for t in Mt], -0.08, 0.08)
        new = np.clip(k + step, max(0.02, kc * 0.5), 1.0)
        if np.allclose(new, k, atol=0.004):
            break
        k = new
        T, Mt = solve(k, T)
        print('    per-channel it %d: k %s MCU %s' % (it, np.round(k, 3), np.round(Mt, 1)))
    for it in range(6):                      # any channel still over: back it off a little, bounded
        over = [n for n in range(4) if Mt[n] > target + 0.3]
        if not over:
            break
        for n in over:
            k[n] = max(0.02, k[n] - 0.03)
        T, Mt = solve(k, T)
    per = dict(k=list(map(float, k)), I=[15.0 * x for x in k], MCU=Mt, FET=fets(m, topo, T), extra=extras(m, topo, T))
    return dict(air=air, MCU_idle=Tb, common=common, per_channel=per)


def fets(m, topo, T):
    rows = th.summarize(m, T, topo)[0]
    return [max(r['T_j'] for r in rows if r['kind'] == 'fet' and r['name'][1] == str(n)) for n in range(1, 5)]


def extras(m, topo, T):
    rows = th.summarize(m, T, topo)[0]
    return dict(X5R=max(r['T_j'] for r in rows if r['kind'] == 'capX5R'),
                shunt=max(r['T_j'] for r in rows if r['name'].startswith('R_S')))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board', nargs='?', default=BOARD)
    ap.add_argument('--only', default='base,a,b,c,d,e')
    ap.add_argument('--air', default='wash,halfwash')
    a = ap.parse_args()
    globals()['BOARD'] = a.board
    sys.stdout.reconfigure(line_buffering=True)
    os.makedirs(OUT, exist_ok=True)
    losses = cases.Losses(LOSSES)
    store = os.path.join(OUT, 'whatif.json')
    R = json.load(open(store)) if os.path.exists(store) else {}
    t0 = time.time()
    for var in a.only.split(','):
        g, topo, m, info = build('b' if var == 'e' else var)
        R.setdefault(var, {})['info'] = info
        R[var]['paths'] = path_resistances(m)
        if var == 'e':
            for air in a.air.split(','):
                R[var]['derate_' + air] = derate(g, m, topo, losses, air=air)
                json.dump(R, open(store, 'w'), indent=1)
            continue
        for air in a.air.split(','):
            name = 'full60-50C-%s-sun' % air
            case = cases.make_case(name, 'aio3', topo, losses)
            res = th.run_case(m, topo, case, os.path.join(OUT, var), plots=True)
            last = th.run_case.last
            R[var][air] = metrics(g, m, topo, last['T'], res)
            if var == 'base' or air == 'wash':
                bn, bl, bv, spots = breakdown(g, m, last['drive'], last['T'])
                R[var]['breakdown_' + air] = dict(net=bn, layer=bl, vias=bv, spots=spots)
            json.dump(R, open(store, 'w'), indent=1)
    write_md(R)
    print('  done in %.0f s' % (time.time() - t0))


def write_md(R):
    L = ['# Thermal what-ifs on the placed board (`out/fan/placed.kicad_pcb`)', '',
         'Generated by `whatif.py`. Board as placed: power pours, planes and fixed vias, no signal routing.',
         'Stackup: 1 oz on all six layers (2 oz where stated), dielectrics 0.1 / 0.5 / 0.18 / 0.5 / 0.1 mm.',
         'Case: full60 (steady hover, then 60 s at 15 A per motor), 50 C ambient, sun. Values are at t = 60 s;',
         '"MCU" is the hottest ESC MCU over the run.', '']
    if 'base' in R and 'breakdown_wash' in R['base']:
        b = R['base']['breakdown_wash']
        tot = sum(b['net'].values())
        L += ['## 1. Copper I^2 R breakdown, base board, full60 50 C wash, t = 60 s', '',
              'Total %.2f W, in-plane plus via barrels, at the local copper temperature.' % tot, '',
              '| Net group | W | share |', '|---|---|---|']
        for k, v in sorted(b['net'].items(), key=lambda x: -x[1]):
            L.append('| %s | %.2f | %.0f %% |' % (k, v, 100 * v / tot))
        L += ['', '| Layer, in-plane | W |', '|---|---|']
        for k, v in b['layer'].items():
            L.append('| %s | %.2f |' % (k, v))
        L += ['', '| Via barrels | W |', '|---|---|']
        for k, v in sorted(b['vias'].items(), key=lambda x: -x[1]):
            L.append('| %s | %.2f |' % (k, v))
        L += ['', 'Top 10 hot spots (copper heat within 1 mm):', '',
              '| # | W | at (mm) | net | layer | near |', '|---|---|---|---|---|---|']
        for i, s in enumerate(b['spots']):
            L.append('| %d | %.2f | %.1f, %.1f | %s | %s | %s |' % (i + 1, s['W'], s['x'], s['y'], s['net'], s['layer'], s['near']))
    L += ['', '## Path resistances (mOhm, 20 C)', '',
          '| variant | channel | battery pad to HS drains | LS sources to shunt | shunt to BAT- | phase A HS to pad | phase A LS to pad |',
          '|---|---|---|---|---|---|---|']
    for var in ('base', 'a', 'b', 'c', 'd'):
        if var in R and 'paths' in R[var]:
            for ch, p in R[var]['paths'].items():
                L.append('| %s | %s | %.3f | %.3f | %.3f | %.3f | %.3f |' % (var, ch, p['bat_to_HS_drains'], p['LS_sources_to_shunt'],
                                                                       p['shunt_to_BAT_minus'], p['phaseA_HS_to_pad'], p['phaseA_LS_to_pad']))
    L += ['', '## 2. What-ifs, full60 50 C sun (limits: FET 175, MCU 105, X5R 85 / 105 derated, shunt 170)', '',
          '| variant | air | FET | MCU | X5R | shunt | battery pad | board max | copper I2R W | FET W |',
          '|---|---|---|---|---|---|---|---|---|---|']
    desc = dict(base='as placed', a='a: GND fill + stitching', b='b: a + battery / R_S1 vias', c='c: b + 2 oz inner',
                d='d: b + 2 oz outer')
    for var in ('base', 'a', 'b', 'c', 'd'):
        for air in ('wash', 'halfwash'):
            if var in R and air in R[var]:
                x = R[var][air]
                L.append('| %s | %s | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.2f | %.2f |' % (
                    desc[var], air, x['FET'], x['MCU'], x['X5R'], x['shunt'], x['batpad'], x['board'], x['copper'], x['fets_W']))
    for var in ('a', 'b', 'c', 'd'):
        if var in R and 'info' in R[var]:
            L.append('')
            L.append('%s: %s' % (desc[var], ', '.join('%s %s' % (k, v if not isinstance(v, dict) else
                                                     ' '.join('%s %.0f mm2' % kv for kv in v.items())) for k, v in R[var]['info'].items())))
    if 'e' in R:
        L += ['', '## e. b + AM32 derating as a current cap (ESC MCU <= 100 C), steady full throttle, 50 C sun', '',
              'Duty, motor-can temperature and air speed follow the load line for the derated current. "common": all',
              'four channels at the same factor, the hottest MCU at 100 C (what the quad can actually fly). "per',
              'channel": each channel derated on its own from there.', '',
              '| air | mode | M1 I/I_full | M2 | M3 | M4 | MCU C (M1-M4) | hottest FET C (M1-M4) | X5R max | shunt max |',
              '|---|---|---|---|---|---|---|---|---|---|']
        for air in ('wash', 'halfwash'):
            d = R['e'].get('derate_' + air)
            if not d:
                continue
            c, p = d['common'], d['per_channel']
            L.append('| %s | common | %.2f | %.2f | %.2f | %.2f | %s | %s | %.0f | %.0f |' % (
                air, c['k'], c['k'], c['k'], c['k'], ' / '.join('%.0f' % t for t in c['MCU']),
                ' / '.join('%.0f' % t for t in c['FET']), c['extra']['X5R'], c['extra']['shunt']))
            L.append('| %s | per channel | %s | %s | %s | %.0f | %.0f |' % (
                air, ' | '.join('%.2f' % x for x in p['k']), ' / '.join('%.0f' % t for t in p['MCU']),
                ' / '.join('%.0f' % t for t in p['FET']), p['extra']['X5R'], p['extra']['shunt']))
            L.append('| %s | motors stopped (no prop wash), sun | | | | | %s | | | |' % (
                air, ' / '.join('%.0f' % t for t in d['MCU_idle'])))
    path = os.path.join(HERE, 'results-placed.md')
    mark = '<!-- hand-written notes below: kept when this file is regenerated -->'
    notes = ''
    if os.path.exists(path) and mark in open(path).read():
        notes = open(path).read().split(mark, 1)[1]
    open(path, 'w').write('\n'.join(L) + '\n\n' + mark + notes)
    print('  wrote results-placed.md')


if __name__ == '__main__':
    main()
