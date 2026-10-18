# -*- coding: utf-8 -*-
"""Print Hub v1: how hot the board gets inside its closed case.

    tools/kd python3 sim/thermal/board_heat.py              (from print-hub/v1; ~1-2 min)
    tools/kd python3 sim/thermal/board_heat.py --cell 0.3   (finer grid, slower)

Writes sim/thermal/board_heat.md and the temperature maps
sim/thermal/board_heat_<case>.png; exits 1 if any part is over its limit.

The solver is thermal.py, copied unchanged from ridge3-lite/v1/sim/thermal
(validated there against Toshiba's measured test boards; its README lists
every material constant and source).  It reads the routed board itself: the
copper of all four layers, every via, every pad.  This file adds what is
particular to this board:

  heat sources  every part that makes heat, at its own pads, with the power
                computed from the same datasheet numbers as power_budget.py
                (and growing with temperature where the part's resistance does)
  copper heat   the DC current of every power path solved on the real copper:
                charger -> buck, buck -> each port switch, each switch -> shunt
                -> USB-A, and every port's return through the ground planes
  the case      the PETG case as two more layers of the network, a lid node
                and a floor node over every board cell (enclose()).  The air
                between board and case is millimetres thin, too thin to
                convect (Rayleigh number under 1708), so it only conducts:
                h = k_air / gap, with the gaps the case model exports
                (mechanical/enclosure/case_gaps.json: the lid steps down to
                0.6 mm over the parts, the floor sits 1 mm under the board).
                Board and case also radiate to each other (emissivity 0.9
                each, 0.82 between parallel faces).  The plastic conducts
                sideways (badly: the case is far from one temperature) and
                through its thickness to its outer faces, which lose heat by
                natural convection and radiation: the lid face up, the floor
                face down (the case stands on its feet), the side walls
                shared out over the board's edge cells.  The side vents are
                given no credit.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(V1, 'src'))
sys.path.insert(0, os.path.join(V1, 'sim'))

import thermal as th                     # noqa: E402
import power_budget as pb                # noqa: E402  (the same datasheet numbers)
import circuit, parts, pcb               # noqa: E402

BOARD = os.path.join(V1, 'print-hub.kicad_pcb')
CASE_GAPS = os.path.join(V1, 'mechanical', 'enclosure', 'case_gaps.json')   # written by enclosure.py
OUT = os.path.join(HERE, 'board_heat.md')

# ---------------------------------------------------------------- the case
# mechanical/enclosure/enclosure.py: the board + 2 mm PETG walls and 0.3 mm
# fit each side (the front wall stands 1.4 mm further back), 18 mm tall
CASE_W, CASE_D, CASE_H = (pcb.W + 4.6) * 1e-3, (pcb.H + 3.2) * 1e-3, 18.0e-3
WALL_T, K_PETG = 2.0e-3, 0.20            # m, W/mK (PETG 0.19-0.24)
GAP_TOP = 8.4e-3                         # board top -> lid ceiling (LID_CEILING_Z 10 - board 1.6)
GAP_BOT = 4.0e-3                         # board bottom -> floor (3 mm pins + 1 mm clearance)
FLOOR_UNDER = 6.0e-3                     # the base's outer floor face below the board's bottom face
EPS_CASE = 0.9                           # PETG, any colour, in the infrared
EPS_PAIR = 1.0 / (1 / 0.9 + 1 / EPS_CASE - 1)     # board <-> wall, parallel faces
PETG_MAX = 65.0                          # C: PETG softens near 75-80 C (HDT 0.45 MPa ~70 C)

# ---------------------------------------------------------------- parts
# junction -> pads thermal resistance, K/W (datasheets), and limits, C
RTH_SW, TMAX_SW = 7.6, 125.0             # TPS25200 WSON: theta_JC(bot) 7.6 to the thermal pad; TSD at 135 min
RTH_BUCK, TMAX_BUCK = 4.0, 125.0         # SY8368A QFN3x3: theta_JC 4; recommended operating max 125
RTH_LDO = 50.0                           # AP2112K SOT-23-5: theta_JA 184 total; ~50 to the leads (estimate)
RTH_L = 30.0                             # winding -> pads of the moulded inductor (estimate: the
                                         # maker's 40 K rise at ~8 A rated current on its test board)
CORE_LOSS = 0.05                         # W, FXL0630 at 800 kHz, 0.7 A ripple (maker's curve, estimate)
R_CONTACT = 0.030                        # ohm per USB-A contact, end of life (USB 2.0 spec, 30 mOhm max)
ESP_W = 3.3 * 0.12                       # W, module average with Wi-Fi associated and serving the page
I_3V3 = 0.14                             # A, average 3.3 V load (module + 5 amplifiers + pull-ups)
LED_W = 0.01                             # W per WS2812B-2020: ~1 mA driver + one colour at 0x20 of 0xff (firmware)
VF_OR = 0.40                             # V, B5819W at ~0.2 A
X5R_MAX, X7R_MAX = 85.0, 125.0           # C, ceramic capacitor ratings
CONN_MAX = 85.0                          # C, USB-A / USB-C receptacles (makers' operating range)
LED_MAX, ESP_MAX = 85.0, 85.0            # C, WS2812B-2020 / ESP32-S3-WROOM-1-N8 operating range


def ron_sw(tj):
    """TPS25200 on-resistance: 60 mOhm typical at 25 C rising to the
    datasheet's 90 mOhm maximum at 125 C (linear between)."""
    return pb.RON_SW_TYP + (pb.RON_SW_MAX - pb.RON_SW_TYP) * max(0.0, tj - 25.0) / 100.0


CASES = {
    # in the corner of the printer cabinet: fan, light, two air filters
    'everyday': dict(room=25.0, ports=[0.45, 0.50, 0.50, 0.50, 0.0], clamp=False,
                     desc='everyday: fan 0.45 A, light 0.5 A, two filters 0.5 A each; room 25 C'),
    'everyday-hot': dict(room=35.0, ports=[0.45, 0.50, 0.50, 0.50, 0.0], clamp=False,
                         desc='the same in a hot room: 35 C'),
    # the most the firmware allows: 3 A in total, the two ports next to the
    # buck at their 1.5 A limit, the rail at its highest corner (the
    # switches' output clamp adds 0.12 W each), a hot room
    'max': dict(room=35.0, ports=[1.5, 1.5, 0.0, 0.0, 0.0], clamp=True,
                desc='most allowed: 3 A (ports 1 and 2, next to the buck, at their 1.5 A limit), '
                     'rail at its highest corner; room 35 C'),
}
# the thermal protection's check: rooms past 35 C at 3 A, where the firmware
# has to turn the ports down; what the thermistor reads when the first part
# reaches its limit sets the firmware's thresholds
HOT_ROOMS = (35.0, 40.0, 45.0, 50.0)


def buck_loss(iout, tj):
    vin, vout = 9.0, 5.16
    d = vout / vin
    k = 1 + 0.004 * (tj - 25)                       # MOSFET on-resistance tempco
    p_cond = iout ** 2 * (d * pb.RDS_HI + (1 - d) * pb.RDS_LO) * k
    p_sw = 0.5 * vin * iout * pb.T_SW * pb.FSW
    return p_cond + p_sw + 0.02                     # + gate drive and quiescent


def topology(case):
    comps = circuit.build()
    ports = case['ports']
    itot = sum(ports)
    i_in = (5.16 * itot + buck_loss(itot, 80) + 0.38) / 9.0      # charger current at 9 V
    i_logic = I_3V3 + 6 * LED_W / 4.7
    E = []

    def el(name, ref, pads=None, rth=None, kind='', tmax=None, P=0.0):
        E.append(dict(name=name, ref=ref, pads=pads, rth=rth, kind=kind, tmax=tmax, P=P))

    el('buck U2', 'U2', None, RTH_BUCK, 'reg', TMAX_BUCK, lambda tj: buck_loss(itot, tj))
    el('inductor L1', 'L1', None, RTH_L, 'ind', 125.0,
       lambda t: itot ** 2 * pb.DCR * (1 + 0.00393 * (t - 20)) + CORE_LOSS)
    el('3.3 V LDO U4', 'U4', None, RTH_LDO, 'reg', 125.0, (5.16 - VF_OR - 3.3) * I_3V3)
    el('OR diode D2', 'D2', None, None, 'diode', 125.0, VF_OR * i_logic)
    el('ESP32 module U5', 'U5', None, None, 'mcu', ESP_MAX, ESP_W)
    el('PD sink U1', 'U1', None, None, 'ic', 85.0, 9.0 * 0.002)
    el('LED status', 'LED1', None, None, 'led', LED_MAX, LED_W)
    el('thermistor', [c.ref for c in comps if c.part == 'NTC10K'][0], None, None, 'sensor', None, 0.0)
    for n in range(1, 6):
        i = ports[n - 1]
        clamp = 0.08 * i if case['clamp'] else 0.0
        el('port %d switch' % n, 'U%d01' % n, ['7'], RTH_SW, 'ic', TMAX_SW,
           (lambda i, c: (lambda tj: i ** 2 * ron_sw(tj) + c))(i, clamp))
        el('port %d shunt' % n, 'R%d04' % n, None, None, 'shunt', 125.0, i ** 2 * pb.R_SHUNT)
        el('port %d amplifier' % n, 'U%d02' % n, None, None, 'ic', 125.0, 3.3 * 100e-6)
        el('port %d USB-A' % n, 'J%d01' % n, ['1', '4'], None, 'conn', CONN_MAX, 2 * i ** 2 * R_CONTACT)
        el('port %d LED' % n, 'LED%d01' % n, None, None, 'led', LED_MAX, LED_W)
    # parts that make no heat of their own but have a temperature limit
    for c in comps:
        if c.ref[0] == 'C':
            rating = parts.PARTS[c.part]['value'] + ' ' + parts.PARTS[c.part].get('desc', '')
            el('cap %s (%s)' % (c.ref, 'X5R' if 'X5R' in rating else 'X7R/C0G'), c.ref, None, None, 'cap',
               X5R_MAX if 'X5R' in rating else X7R_MAX, 0.0)
    for ref in ('J1', 'J2'):
        el('USB-C %s' % ref, ref, None, None, 'conn', CONN_MAX, 0.0)

    # DC current on the real copper: (net) [(ref, pads, amps)], amps sum to zero
    sw_pads = lambda n: ('U%d01' % n, ['1'])
    joule = [
        [('J1', ['A4B9', 'B4A9'], i_in), ('U2', ['4', '5', '6'], -i_in)],
        [('U2', ['2'], itot), ('L1', ['1'], -itot)],
        [('L1', ['2'], itot)] + [('U%d01' % n, ['6'], -ports[n - 1]) for n in range(1, 6) if ports[n - 1]],
        # returns: every port's ground into the planes; the charger's share
        # leaves through POWER IN, the rest through the buck's low side
        [('J%d01' % n, ['4', 'SH1', 'SH2'], ports[n - 1]) for n in range(1, 6) if ports[n - 1]]
        + [('J1', ['A1B12', 'B1A12'], -i_in), ('U2', ['1', '3', '10'], -(itot - i_in))],
    ]
    for n in range(1, 6):
        if ports[n - 1]:
            joule.append([(sw_pads(n)[0], sw_pads(n)[1], ports[n - 1]), ('R%d04' % n, ['1'], -ports[n - 1])])
            joule.append([('R%d04' % n, ['2'], ports[n - 1]), ('J%d01' % n, ['1'], -ports[n - 1])])
    return dict(elements=E, wires=[], profile='print-hub'), [(1.0, j) for j in joule]


K_AIR = 0.028                            # W/mK, air at ~50 C
RC_PETG = 1270 * 1300.0                  # J/m3K
MARGIN = 2.3e-3                          # m, case outline beyond the board edge (wall + fit)
H_RAD_GAP = 4 * EPS_PAIR * th.SIGMA * 343.0 ** 3   # board <-> case radiation, linearised at 70 C


def case_gaps(model, path=CASE_GAPS):
    """Per-cell air gaps above and below the board (m) and the lid's
    thickness, from the enclosure model's own export: at any point the gap
    is the largest of the default and every rectangle that holds it."""
    import json
    global CASE_W, CASE_D, CASE_H
    c = json.load(open(path))
    CASE_W, CASE_D, CASE_H = [v * 1e-3 for v in c['outside_mm']]
    g = model.g
    jj, ii = model.cpos
    x = g.x0 + (ii + 0.5) * g.d - pcb.CX
    y = g.y0 + (jj + 0.5) * g.d - pcb.CY
    out = []
    for side in ('top', 'bottom'):
        gap = np.full(model.nc, c[side + '_default_mm'])
        for r in c[side]:
            m = (x >= r['x0']) & (x <= r['x1']) & (y >= r['y0']) & (y <= r['y1'])
            gap[m] = np.maximum(gap[m], r['gap_mm'])
        out.append(gap * 1e-3)
    # the lid is solid from its top face down to its underside (printed at
    # 100 % infill); the floor is solid from FLOOR_UNDER below the board
    lid_t = c['wall_mm'] * 1e-3 + (GAP_TOP - out[0]).clip(0)
    floor_t = (FLOOR_UNDER - out[1]).clip(c['wall_mm'] * 1e-3)
    return out[0], out[1], lid_t, floor_t, c


def enclose(model, gap_top, gap_bot, lid_t, floor_t=WALL_T):
    """Add the case to the board's network: a lid node and a floor node over
    every board cell.  Each is joined to the board face below / above it
    across its air gap (conduction, the gap being too thin to convect, and
    radiation), to its neighbours through the plastic (PETG conducts
    sideways ~2000 times worse than the board's copper planes, so the case
    is far from one temperature), and to the room through its own thickness
    and its outer face (boundary()).  Cells on the board's edge carry the
    side walls and the case's margin beyond the board.  gap_top, gap_bot,
    lid_t: per cell (m), or numbers."""
    g, nc, nL = model.g, model.nc, model.nL
    d = g.d * 1e-3
    A = d * d * model.fb
    gap_top, gap_bot, lid_t, floor_t = [np.broadcast_to(np.asarray(x, float), (nc,)).copy()
                                        for x in (gap_top, gap_bot, lid_t, floor_t)]
    N0 = model.N
    lid, flo = N0 + np.arange(nc), N0 + nc + np.arange(nc)
    r, c, v = [], [], []

    def link(a, b, gv):
        r.append(np.asarray(a)); c.append(np.asarray(b)); v.append(np.asarray(gv, float))
    link(np.arange(nc) * nL, lid, A * (K_AIR / gap_top + H_RAD_GAP))
    link(np.arange(nc) * nL + nL - 1, flo, A * (K_AIR / gap_bot + H_RAD_GAP))
    cid = model.cid
    for ia, ib in ((cid[:, :-1], cid[:, 1:]), (cid[:-1, :], cid[1:, :])):
        m = (ia >= 0) & (ib >= 0)
        a_, b_ = ia[m], ib[m]
        link(lid[a_], lid[b_], K_PETG * 0.5 * (lid_t[a_] + lid_t[b_]))
        link(flo[a_], flo[b_], K_PETG * 0.5 * (floor_t[a_] + floor_t[b_]))
    N = N0 + 2 * nc
    G = th.sp.coo_matrix((np.concatenate(v), (np.concatenate(r), np.concatenate(c))), shape=(N, N))
    G = G + G.T
    lap = th.sp.diags(np.asarray(G.sum(1)).ravel()) - G
    model.G = (th.sp.block_diag([model.G, th.sp.csc_matrix((2 * nc, 2 * nc))]) + lap).tocsc()
    model.C = np.concatenate([model.C, A * RC_PETG * lid_t, A * RC_PETG * floor_t])
    model.N = N
    # open edges per cell: the side wall (half to the lid, half to the floor)
    # and the case's margin beyond the board
    act = cid >= 0
    pad = np.pad(act, 1)
    edges = (~pad[:-2, 1:-1]).astype(int) + (~pad[2:, 1:-1]) + (~pad[1:-1, :-2]) + (~pad[1:-1, 2:])
    ne = edges[act]
    extra = ne * d * (CASE_H / 2 + MARGIN)
    model.faces = [dict(idx=lid, area=A + extra, t=lid_t, up=True, name='lid'),
                   dict(idx=flo, area=A + extra, t=floor_t, up=False, name='floor')]
    model.case = dict(lid=lid, floor=flo)
    model.L_case = (CASE_W * CASE_D) / (2 * (CASE_W + CASE_D))


class CaseSolver(th.Solver):
    """Boundary: the case's outer faces to the room (dv.Ta): natural
    convection (lid face up, floor face down: the case stands on feet) and
    radiation, in series with the plastic's own thickness."""

    def boundary(self, T, dv):
        m = self.m
        out_idx, out_G = [], []
        TaK = dv.Ta + 273.15
        for fc in m.faces:
            Ts = T[fc['idx']]
            hn = th.h_plate_natural(Ts - dv.Ta, dv.Ta, m.L_case, up=fc['up'])
            TsK = Ts + 273.15
            hr = EPS_CASE * th.SIGMA * (TsK ** 2 + TaK ** 2) * (TsK + TaK)
            out_idx.append(fc['idx']); out_G.append(fc['area'] / (fc['t'] / K_PETG + 1.0 / (hn + hr)))
        return np.concatenate(out_idx), np.concatenate(out_G)


def h_vertical(dT, Ta, L):
    """Vertical plate, Churchill-Chu laminar (Incropera eq. 9.27)."""
    nu, k, a, pr = th.air(Ta + 273.15 + dT / 2)
    Ra = th.G0 / (Ta + 273.15 + dT / 2) * max(dT, 1e-3) * L ** 3 / (nu * a)
    return (0.68 + 0.670 * Ra ** 0.25 / (1 + (0.492 / pr) ** (9 / 16.)) ** (4 / 9.)) * k / L


def run(model, topo, joule, case):
    s = CaseSolver(model)
    dv = th.Drive(dict(Ta=case['room'], v_top=0.0, v_bot=0.0, v_wire=0.0, turb=1.0, solar=0.0,
                       power={e['name']: e['P'] for e in topo['elements']}, wire_current={}, wire_far={},
                       joule=joule, label=case['desc']))
    T, pw = s.steady(dv, verbose=False)
    rows, lay, _ = th.summarize(model, T, topo)
    lid, flo = T[model.case['lid']], T[model.case['floor']]
    return dict(T=T, pw=pw, P=sum(pw.values()), wall_in=float(max(lid.max(), flo.max())),
                lid=(float(lid.mean()), float(lid.max())), floor=(float(flo.mean()), float(flo.max())),
                rows=rows, layers=lay, balance=s.balance)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cell', type=float, default=0.4)
    ap.add_argument('--board', default=BOARD)
    ap.add_argument('--no-plots', action='store_true')
    ap.add_argument('--gap-top', type=float, default=GAP_TOP * 1e3, help='air above the board, mm')
    ap.add_argument('--gap-bot', type=float, default=GAP_BOT * 1e3, help='air below the board, mm')
    ap.add_argument('--quick', action='store_true', help='the max case only, no hot-room sweep')
    ap.add_argument('--uniform', action='store_true', help='ignore case_gaps.json: a plain box (--gap-top, --gap-bot)')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)
    P = th.Params
    P.cell_mm = a.cell
    P.ss = max(2, int(round(a.cell / 0.025 / 2)) * 2)
    g = th.load_kicad(a.board, P)
    out = ['# Print Hub v1: board temperatures in the closed case\n',
           'Written by `sim/thermal/board_heat.py` from the routed board (`print-hub.kicad_pcb`): '
           'all four copper layers, every via and pad, %.1f mm grid. ' % a.cell +
           'The board is in the closed PETG case: conduction across the air gaps above and below it, radiation '
           'to the walls, the walls cooling by natural convection and radiation from the top and sides only '
           '(no credit for the floor or the vents). Limits are each part\'s rated maximum.\n']
    bad = []
    model = None
    for name, case in (CASES.items() if not a.quick else [('max', CASES['max'])]):
        topo, joule = topology(case)
        if model is None:                   # the same parts and pads every case: one network
            model = th.Model(g, topo, P)
            if os.path.exists(CASE_GAPS) and not a.uniform:
                gt, gb, lt, ft, c = case_gaps(model)
                enclose(model, gt, gb, lt, ft)
                how = ('the case from mechanical/enclosure/case_gaps.json: outside %.1f x %.1f x %.1f mm on %.0f mm '
                       'feet; air above the board %.1f-%.1f mm (the lid steps down over the low parts), below it '
                       '%.1f-%.1f mm' % (tuple(c['outside_mm']) + (c['feet_mm'], gt.min() * 1e3, gt.max() * 1e3,
                                                                   gb.min() * 1e3, gb.max() * 1e3)))
            else:
                enclose(model, a.gap_top * 1e-3, a.gap_bot * 1e-3, WALL_T)
                how = 'a plain box: %.1f mm of air above the board, %.1f mm below' % (a.gap_top, a.gap_bot)
            out.insert(2, 'Case: %s.\n' % how)
            print('  ' + how)
        model.topo = topo
        print('\n== %s' % case['desc'])
        r = run(model, topo, joule, case)
        rows = sorted([x for x in r['rows'] if x['T_limit']], key=lambda x: x['T_limit'] - x['T_j'])
        ntc = [x['T_j'] for x in r['rows'] if x['kind'] == 'sensor'][0]
        groups = {}
        for k, v in r['pw'].items():
            key = k.split(' ')[0] + (' ' + k.split(' ')[-1] if k.startswith('port') else '')
            groups[key] = groups.get(key, 0.0) + v
        out.append('\n## %s\n' % case['desc'])
        out.append('Heat in the case: **%.2f W** (%s). Lid %.1f C on average, %.1f C at its hottest; floor %.1f / '
                   '%.1f C (PETG limit %g C). The thermistor reads %.1f C. Energy balance error %.1e W.\n' % (
                       r['P'], ', '.join('%s %.2f W' % (k, v) for k, v in sorted(groups.items(), key=lambda x: -x[1]) if v > 0.005),
                       r['lid'][0], r['lid'][1], r['floor'][0], r['floor'][1], PETG_MAX, ntc, r['balance']['error']))
        out.append('| part | temperature (C) | limit (C) | margin (K) |\n|---|---|---|---|')
        for k, x in enumerate(rows):
            m = x['T_limit'] - x['T_j']
            if m < 0:
                bad.append('%s: %s %.0f C over %g C' % (name, x['name'], x['T_j'], x['T_limit']))
            if k < 14:
                out.append('| %s | %.1f | %g | %+.0f |' % (x['name'], x['T_j'], x['T_limit'], m))
        out.append('\nBoard copper: ' + ', '.join('%s %.1f-%.1f C' % (k, lo, hi) for k, (lo, hi) in r['layers'].items()) + '.')
        if r['wall_in'] > PETG_MAX:
            bad.append('%s: case wall %.0f C over %g C' % (name, r['wall_in'], PETG_MAX))
        hot = sorted(r['rows'], key=lambda x: -x['T_j'])[:4]
        print('  heat %.2f W, case %.1f C at its hottest, thermistor %.1f C; hottest: %s' % (
            r['P'], r['wall_in'], ntc, ', '.join('%s %.1f' % (x['name'], x['T_j']) for x in hot)))
        print('  smallest margins: ' + ', '.join('%s %.0f/%g' % (x['name'], x['T_j'], x['T_limit']) for x in rows[:5]))
        if not a.no_plots:
            th.plot_maps(model, r['T'], topo, r['rows'], os.path.join(HERE, 'board_heat_%s' % name),
                         'Print Hub v1  %s' % case['desc'])
            os.remove(os.path.join(HERE, 'board_heat_%s_layers.png' % name))
            out.append('\n![%s](board_heat_%s_top_bottom.png)\n' % (name, name))
    # hotter rooms: the board alone would pass its limits; what the thermistor
    # reads then is where the firmware must already have turned the ports down
    if a.quick:
        return 1 if bad else 0
    out.append('\n## Hotter rooms: where the thermal protection takes over\n')
    out.append('No turning down in these runs: they show what the thermistor reads when the first part reaches its '
               'limit, which sets the firmware\'s thresholds (`firmware/lib/hub/src/hub.h`).\n')
    out.append('| room (C) | load | heat (W) | thermistor (C) | first part to its limit | its margin (K) | '
               'thermistor reading at that part\'s limit (C) |\n|---|---|---|---|---|---|---|')
    trip = []
    for room in HOT_ROOMS:
        for load, ports in (('3 A', [1.5, 1.5, 0, 0, 0]), ('1.5 A', [1.5, 0, 0, 0, 0]), ('none', [0] * 5)):
            case = dict(room=room, ports=ports, clamp=True, desc='%s, %g C' % (load, room))
            topo, joule = topology(case)
            model.topo = topo
            r = run(model, topo, joule, case)
            ntc = [x['T_j'] for x in r['rows'] if x['kind'] == 'sensor'][0]
            rows = sorted([x for x in r['rows'] if x['T_limit']], key=lambda x: x['T_limit'] - x['T_j'])
            first = rows[0]
            m = first['T_limit'] - first['T_j']
            trip.append(ntc + m)            # the parts' rise over the thermistor holds as the room warms
            print('  room %g, %s: heat %.2f W, thermistor %.1f C, %s %.1f/%g' % (
                room, load, r['P'], ntc, first['name'], first['T_j'], first['T_limit']))
            out.append('| %g | %s | %.2f | %.1f | %s | %+.1f | %.1f |' % (room, load, r['P'], ntc, first['name'], m, ntc + m))
    out.append('\nThe lowest thermistor reading at which some part reaches its limit: **%.1f C**. '
               'The firmware switches every port off at a lower reading (TRIP_C) and starts turning them down '
               'well before (DERATE_C).\n' % min(trip))
    out.append('\n## Result\n')
    out.append('**%s**' % ('every part inside its limit, with the margins above' if not bad else
                           'OVER LIMIT: ' + '; '.join(bad)))
    open(OUT, 'w').write('\n'.join(out) + '\n')
    print('\n'.join(bad) or 'all parts inside their limits')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
