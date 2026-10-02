# -*- coding: utf-8 -*-
"""Stress simulations of the Ridge 3 stack: the FC on the ESC, hot, 6S, flat out.

    python3 sim/stress.py          writes ../STRESS.md and ../images/stress/*.png
    python3 sim/stress.py --quick  one air speed and temperature, short runs: a
                                   check that the code runs, into sim/out/ only

Runs, in order:

  1. the FET model against its datasheet (spice.py)
  2. the ESC's copper under motor current (dcflow.py, copperloss.py)
  3. the switching edges of one half-bridge (spice.py)
  4. the battery line: hot plug, full-throttle ripple, a throttle chop
  5. the stack lead between the boards
  6. the stack's temperatures: steady limits, bursts and a hot flight (stack.py)

Every number in the report comes from these runs and from data.py.  Nothing
here is a measurement; bring-up on the bench is still the test.
"""
import os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(RIDGE, 'src'))
import copper, dcflow, copperloss, thermal, spice, losses, data, stack, design

QUICK = '--quick' in sys.argv
HOT = 50.0             # the design's hot day: 50 C air around the quad (owner's requirement)
AIRS = (25.0, HOT, 60.0)
OUT = os.path.join(HERE, 'out')
IMG = os.path.join(OUT, 'quick') if QUICK else os.path.join(RIDGE, 'images', 'stress')
REPORT = os.path.join(OUT, 'quick', 'STRESS.md') if QUICK else os.path.join(RIDGE, 'STRESS.md')
CH = (1, 2, 3, 4)
PH = 'ABC'

lines = []
verdicts = []          # (area, check, result, number, limit)
found = {}             # numbers the closing section refers back to
PLOTS = True           # figures for the design the report details (rev 2)


def say(s=''):
    lines.append(s)


def table(head, rows):
    say('| ' + ' | '.join(head) + ' |')
    say('|' + '|'.join('---' for _ in head) + '|')
    for r in rows:
        say('| ' + ' | '.join(str(x) for x in r) + ' |')
    say()


def verdict(area, check, ok, number, limit):
    res = {True: 'PASS', False: 'FAIL'}.get(ok, ok)
    verdicts.append((area, check, res, number, limit))
    return res


def log(*a):
    print('[%s]' % time.strftime('%H:%M:%S'), *a, flush=True)


# =================================================================== 1. FET model
def fet_check():
    log('FET model check')
    F = data.FET
    X = F['tests']
    ciss, crss, coss = spice.capacitances(VDS=X['vds_c'])
    Ts = [25, 50, 75, 100, 125, 150, 175]
    R = [spice.rds_on(T, ID=X['id_r']) for T in Ts]
    qg, qgd = spice.gate_charge(VDD=X['vdd_g'], ID=X['id_g'])
    q0, i0, t0 = spice.recovery_charge(VR=X['vr'])
    fit = data.BODY_DIODE
    if fit:
        q1, i1, t1 = spice.recovery_charge(lm=fit, VR=X['vr'])
    say('## 1. The FET model against its datasheet')
    say()
    say('%s.  Before trusting its switching, each figure the datasheet gives was '
        'simulated in the datasheet\'s own test circuit:' % F['model'])
    say()
    rr = 'as supplied: %.0f nC, %.0f ns' % (q0 * 1e9, t0 * 1e9)
    if fit:
        rr += '; with the recovery diode below: %.0f nC, %.0f ns' % (q1 * 1e9, t1 * 1e9)
    table(['Quantity', 'Datasheet (typ)', 'Model', 'Test'], [
        ['R<sub>DS(on)</sub> at 25 C', '%.1f mOhm (max %.1f)' % (F['rds25_typ'] * 1e3, F['rds25_max'] * 1e3), '%.2f mOhm' % (R[0] * 1e3),
         'V<sub>GS</sub> 10 V, %.0f A' % X['id_r']],
        ['R<sub>DS(on)</sub> at 125 C', '-', '%.2f mOhm (x%.2f)' % (R[4] * 1e3, R[4] / R[0]), 'same'],
        ['C<sub>iss</sub>', '%d pF' % (F['ciss'] * 1e12), '%d pF' % (ciss * 1e12), 'V<sub>DS</sub> %.0f V, 1 MHz' % X['vds_c']],
        ['C<sub>rss</sub>', '%d pF' % (F['crss'] * 1e12), '%d pF' % (crss * 1e12), 'same'],
        ['C<sub>oss</sub>', '%d pF' % (F['coss'] * 1e12), '%d pF' % (coss * 1e12), 'same'],
        ['Q<sub>g</sub> to 10 V', '%.0f nC' % (F['qg'] * 1e9), '%.1f nC' % (qg * 1e9), '%.0f V, %.0f A' % (X['vdd_g'], X['id_g'])],
        ['Q<sub>gd</sub>', '%.1f nC' % (F['qgd'] * 1e9), '%.1f nC' % (qgd * 1e9), 'same'],
        ['Reverse recovery (Q<sub>rr</sub> + Q<sub>oss</sub>)', '%.0f + %.0f nC, t<sub>rr</sub> %.0f ns' % (F['qrr'] * 1e9, F['qoss'] * 1e9, F['trr'] * 1e9),
         rr, 'I<sub>F</sub> 20 A, 100 A/us, %.0f V' % X['vr']],
    ])
    if fit:
        say('The on-resistance, capacitances and gate charge match.  Toshiba\'s body '
            'diode is SPICE\'s basic one, which stores more charge than the datasheet '
            'shows and lets it go all at once (the hardest possible recovery).  The '
            'switching runs below therefore use a charge-control diode (Lauritzen and '
            'Ma) fitted to the datasheet\'s recovery test (lifetime %.0f ns, transit '
            'time %.0f ns), with Toshiba\'s junction capacitance and %.0f V breakdown '
            'kept; the diode as supplied is run too, as the worst case.' % (
                fit[0] * 1e9, fit[1] * 1e9, F['vdss']))
    else:
        say('The switching runs below use the maker\'s model as supplied, its own '
            'body diode included.')
    say()
    return dict(T=Ts, R=R)



def copper_section(esc_ops):
    log('copper')
    c = copper.extract('esc')
    u = copperloss.unit_maps(c, OUT)
    P = u['paths']
    say('## 2. The ESC\'s copper under motor current')
    say()
    say('Every copper cell of the ESC (%.2f mm grid, all six layers, zones, '
        'tracks, pads and via barrels as KiCad fills them) solved for DC current '
        'flow, one net at a time, with the FETs, shunts and battery pads putting '
        'current in and taking it out where their pads are.  The solver was '
        'checked against a copper strip and a ring, whose resistance has a '
        'closed form: both agree to within the grid\'s staircase edges.' % c.res)
    say()
    rows = []
    rho100 = 1 + dcflow.ALPHA * 80
    for n in CH:
        s = P['M%d_SRC' % n]
        ph = [P['M%d_%s' % (n, p)] for p in PH]
        rows.append(['ESC %d' % n,
                     '%.2f / %.2f' % (np.mean([x['R_hs'] for x in ph]) * 1e3, np.mean([x['R_ls'] for x in ph]) * 1e3),
                     '%.1f / %.1f / %.1f' % (s['R_A'] * 1e3, s['R_B'] * 1e3, s['R_C'] * 1e3)])
    say('Resistance of each current path at 20 C (mOhm).  For comparison, one '
        'FET is %.1f mOhm at most (datasheet, 25 C):' % (data.FET['rds25_max'] * 1e3))
    say()
    table(['Channel', 'Phase copper, high side / low side', 'Sense node: low-side FET A / B / C to the shunt'], rows)
    found['r_src'] = np.mean([P['M%d_SRC' % n]['R_' + y] for n in CH for y in PH])
    found['r_planes'] = P['VBAT']['R'] + P['GND']['R']
    say('The battery planes, shared by the four channels, add %.2f mOhm (VBAT) '
        'and %.2f mOhm (GND) for the total battery current.' % (P['VBAT']['R'] * 1e3, P['GND']['R'] * 1e3))
    say()
    # the via each low-side FET's current funnels through
    worst = []
    for n in CH:
        for y in PH:
            s = dcflow.solve(c, 'M%d_SRC' % n, {'Q%d%sL' % (n, y): 1.0, 'R_SH%d' % n: -1.0}, T=20.0)
            bc = max(dcflow.barrel_currents(c, s), key=lambda x: x[1])
            worst.append((bc[1], n, y, c.holes[bc[0]]))
    frac, n, y, h = max(worst, key=lambda x: x[0])
    found['via_worst'] = (frac, 20 * frac)
    say('**Where the sense-node current funnels.**  The via carrying the largest '
        'share of one low-side FET\'s current on its way to the shunt: %.0f %% of '
        'FET Q%d%sL\'s current goes through one %.2f mm via at (%+.1f, %+.1f) mm '
        'from the board centre, so at 20 A per motor that via carries %.0f A.' % (
            100 * frac, n, y, h['d'], h['x'] - (c.x0 + c.nx * c.res / 2), h['y'] - (c.y0 + c.ny * c.res / 2), 20 * frac))
    say()
    rows = []
    for tag, I, D in esc_ops:
        W = copperloss.loss_map(u, {k: I for k in CH}, {k: D for k in CH}) * rho100
        per = [float(W[l].sum()) for l in range(W.shape[0])]
        fet = 4 * 2 * I * I * data.FET['rds25_max'] * 1.5
        rows.append([tag, '%.1f W' % sum(per), ', '.join('%s %.1f' % (c.layers[l], per[l]) for l in range(len(per)) if per[l] > 0.05),
                     '%.1f W' % fet])
    say('Copper loss with all four motors at the same current, copper at 100 C '
        '(resistance x%.2f of 20 C):' % rho100)
    say()
    table(['Operating point', 'Copper loss', 'By layer (W)', 'For scale: FET conduction, 8 FETs at 1.5 x R<sub>max</sub>'], rows)
    return u


# =================================================================== 3. switching
def hb_params(**kw):
    p = dict(data.BRIDGE)
    p.update(kw)
    return p


def switching_section():
    log('switching edges')
    say('## 3. Switching edges: one half-bridge at full voltage')
    say()
    B = data.BRIDGE
    D = data.DRIVER
    if D['kind'] == 'gvdd':
        dead = 'AM32\'s %.0f ns plus the %s\'s %.0f ns' % (data.AM32['dead'] * 1e9, D['part'], D['dead'][1] * 1e9)
        drive = ('the %s as its typical peak currents (%.2f A source, %.2f A sink) behind the %.0f ohm '
                 'gate resistors' % (D['part'], B['ipu'], B['ipd'], B['Rg']))
    else:
        dead = ('%.0f ns: the %s turns a gate on %.0f ns after it sees the other one discharged, '
                'longer than AM32\'s own %.0f ns' % (B['dead'] * 1e9, D['part'], D['dead_add'] * 1e9,
                                                      data.AM32['dead'] * 1e9))
        drive = ('the %s\'s gate current set by its IDRIVE pin (%.0f mA source, %.0f mA sink) straight '
                 'to the gates' % (D['part'], B['ipu'] * 1e3, B['ipd'] * 1e3))
    bulk = ('the %.0f uF external capacitor at the pads' % (B['Cext'] * 1e6) if not data.BULK.get('on_board')
            else 'the ESC\'s own bus capacitors (%s)' % data.BULK['desc'])
    say('One phase leg of the ESC switching the motor current, simulated through '
        'both edges: the low side turns off, dead time (%s), the high side turns '
        'on and the low side\'s body diode recovers, then the high side turns '
        'off.  Battery %.1f V (6S full), %s, the bridge capacitor at its DC-bias '
        'value, the pack %.0f mOhm behind %.0f nH of leads with %s.' % (
            dead, B['V'], drive, B['Rbat'] * 1e3, B['Llead'] * 1e9, bulk))
    say()
    say('The commutation loop\'s inductance (bridge capacitor, high-side FET, '
        'phase vias, low-side FET, sense-node copper, back to the capacitor) is '
        'estimated from the layout: the high-side FET on top and the low-side FET '
        '2.4 mm along on the bottom, with the bridge capacitors beside them, '
        'make a loop about 5 mm long through the 1.6 mm board, 3.3 mm wide: '
        'mu0 x 5 x 1.6 / 3.3 = 3 nH, plus the two FET packages and the '
        'capacitor\'s own inductance, about 5 nH.  That is an estimate, not a '
        'field solution, so 3 and 8 nH are run too.')
    say()
    # every half-bridge run of this section, all at once (spice.half_bridges)
    main = [(diode, T, I, L, lm) for diode, lm, tt in DIODES()
            for T in ((150,) if QUICK else (25, 150)) for I in (10, 20, 30)
            for L in ((5e-9,) if QUICK else (3e-9, 5e-9, 8e-9))
            if not (diode == 'as supplied' and data.BODY_DIODE and (L != 5e-9 or T != 150))]
    buses = (31.3, 35.3)
    fixes = [(tag, kw, I) for tag, kw in (('as designed', {}),) + (
                 (('gate resistors 22 ohm', dict(Rg=22)), ('gate resistors 47 ohm', dict(Rg=47)))
                 if data.DRIVER['kind'] == 'gvdd' else ()) + (
                 ('RC snubber 2.2 ohm + 2.2 nF per FET', dict(snub=(2.2, 2.2e-9))),
                 ('RC snubber 1 ohm + 4.7 nF per FET', dict(snub=(1.0, 4.7e-9))),
                 ('RC snubber 1 ohm + 10 nF per FET', dict(snub=(1.0, 10e-9))),) + idrive_steps()
             for I in (10, 30)]
    runs = spice.half_bridges(
        [hb_params(I=I, T=T, Lloop=L, lm=lm, tag='sw') for diode, T, I, L, lm in main] +
        [hb_params(V=Vb, I=20.0, T=150, Lloop=5e-9, lm=data.BODY_DIODE, tag='regen') for Vb in buses] +
        [hb_params(I=I, T=150, Lloop=5e-9, lm=data.BODY_DIODE, tag='fix', **kw) for tag, kw, I in fixes])
    fixed = runs[len(main) + len(buses):]
    rows = []
    res = {}
    gear = []
    for (diode, T, I, L, lm), r in zip(main, runs):
        if r['gear']:
            gear.append('%s, %d C, %d A, %.0f nH' % (diode, T, I, L * 1e9))
        res[(diode, T, I, L)] = r
        rows.append([diode, T, I, '%.0f' % (L * 1e9), '%.1f' % r['vds_hs_peak'],
                     '%.1f' % r['vds_ls_peak'], '%.1f' % r['sh_min'],
                     '%.1f / %.1f' % (r['slew_rise'], r['slew_fall']),
                     '%.2f' % r['vgs_ls_miller'], '%.0f' % r['irr'],
                     '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6)])
    # the same edges while a throttle chop has lifted the bus (section 4)
    for Vb, r in zip(buses, runs[len(main):]):
        res[('bus %.1f V' % Vb, 150, 20, 5e-9)] = r
        rows.append(['%s, bus at %.1f V (throttle chop)' % (MAIN(), Vb), 150, 20, '5', '%.1f' % r['vds_hs_peak'],
                     '%.1f' % r['vds_ls_peak'], '%.1f' % r['sh_min'],
                     '%.1f / %.1f' % (r['slew_rise'], r['slew_fall']),
                     '%.2f' % r['vgs_ls_miller'], '%.0f' % r['irr'],
                     '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6)])
    table(['Body diode', 'T<sub>j</sub> C', 'I A', 'Loop nH', 'Peak V<sub>DS</sub> high side (turn-off)',
           'Peak V<sub>DS</sub> low side (turn-on)', 'SHx min V', 'SHx slew up / down V/ns',
           'Off gate V<sub>GS</sub> peak V', 'Recovery A', 'E<sub>on</sub> / E<sub>off</sub> uJ'], rows)
    if gear:
        say('ngspice\'s default (trapezoidal) integration stalled on %s; %s solved with Gear\'s '
            'integration instead, the same circuit.' % ('; '.join(gear), 'it was' if len(gear) == 1 else 'they were'))
        say()
    vr = '%.0f V rating' % data.FET['vdss']
    hs = max(v['vds_hs_peak'] for k, v in res.items() if k[0] == MAIN() and k[3] == 5e-9)
    ls = max(v['vds_ls_peak'] for k, v in res.items() if k[0] == MAIN())
    verdict('Voltage', 'High-side FET at turn-off, 30 A, 5 nH loop', hs < 0.9 * data.FET['vdss'] or
            ('MARGINAL' if hs < data.FET['vdss'] else False), '%.1f V' % hs, vr)
    verdict('Voltage', 'Low-side FET after the high side turns on (body-diode recovery)',
            ls < 0.9 * data.FET['vdss'] or ('MARGINAL' if ls < data.FET['vdss'] - 0.5 else False),
            '%.1f V (worst case)' % ls, vr)
    slew = max(v['slew_rise'] for k, v in res.items() if k[0] == MAIN())
    if data.DRIVER.get('slew_max'):
        verdict('Voltage', 'Switch-node slew (%s recommends <= %.0f V/ns)' % (data.DRIVER['part'], data.DRIVER['slew_max']),
                slew <= data.DRIVER['slew_max'] or 'MARGINAL', '%.1f V/ns' % slew, '%.0f V/ns' % data.DRIVER['slew_max'])
    # judged at the loop's estimate (5 nH), as the drain peak is; a run of
    # the 3-8 nH bracket past the limit makes it marginal
    shm = min(v['sh_min'] for v in res.values())
    sh5 = min(v['sh_min'] for k, v in res.items() if k[3] == 5e-9)
    lim = data.DRIVER['sh_min']
    verdict('Voltage', 'SHx below ground at high-side turn-off, 5 nH loop (3-8 nH bracket)',
            shm > lim or ('MARGINAL' if sh5 > lim else False),
            '%.1f V (%.1f V in the bracket)' % (sh5, shm) if shm < sh5 else '%.1f V' % sh5, data.DRIVER['sh_note'])
    found['ls_peak'] = ls
    found['slew'] = slew
    mil = max(v['vgs_ls_miller'] for k, v in res.items() if k[1] == 150 and k[0] == MAIN())
    chop = max(v['vds_hs_peak'] for k, v in res.items() if k[0].startswith('bus'))
    verdict('Voltage', 'High-side FET at turn-off, 20 A, while a throttle chop holds the bus at 31-35 V',
            chop < 0.9 * data.FET['vdss'] or ('MARGINAL' if chop < data.FET['vdss'] - 0.5 else False),
            '%.1f V' % chop, vr)
    found['mil'] = mil
    verdict('Voltage', 'Off FET\'s gate kicked up by the other FET turning on (hot)',
            'MARGINAL' if mil > data.FET['vth_min_hot'] else True,
            '%.2f V' % mil, 'V<sub>th</sub> min %.1f V at 25 C, about %.1f V at 150 C' % (
                data.FET['vth_min'], data.FET['vth_min_hot']))
    # what brings the ringing down
    rows = []
    for (tag, kw, I), r in zip(fixes, fixed):
        if tag == 'as designed':
            found.setdefault('hs30', {})[I] = r['vds_hs_peak']
        extra = 0.0
        if 'snub' in kw:
            extra = 2 * kw['snub'][1] * data.BRIDGE['V'] ** 2 * data.AM32['f_max']   # per switched leg
        rows.append([tag, I, '%.1f' % r['vds_hs_peak'], '%.1f' % r['vds_ls_peak'], '%.1f' % r['sh_min'],
                     '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6),
                     '%.2f W' % extra if extra else '-'])
    say('What brings the peaks down (T<sub>j</sub> 150 C, 5 nH, %s):' % (
        'the recovery-fit diode' if data.BODY_DIODE else 'the maker\'s model'))
    say()
    table(['Change', 'I A', 'High side V', 'Low side V', 'SHx min V', 'E<sub>on</sub> / E<sub>off</sub> uJ',
           'Snubber loss per switched leg at %.0f kHz' % (data.AM32['f_max'] / 1e3)], rows)
    sw = {'V': data.BRIDGE['V'], 'I': [0.0], 'on': [0.0], 'off': [0.0]}
    for I in (10, 20, 30):
        r = res[(MAIN(), 150, I, 5e-9)]
        sw['I'].append(I); sw['on'].append(r['e_on']); sw['off'].append(r['e_off'])
    # beyond 30 A, extrapolate linearly
    sw['I'].append(60); sw['on'].append(2 * sw['on'][-1]); sw['off'].append(2 * sw['off'][-1])
    found['hs_peak'] = hs
    found['sw'] = sw
    plot_edges(res)
    return sw


def idrive_steps():
    """The DRV8320's IDRIVE levels either side of the design's, each with the
    dead time it brings: (label, half-bridge parameters)."""
    D = data.DRIVER
    if D['kind'] == 'gvdd':
        return ()
    lv = D['idrive']
    k = lv.index(D['i_src'])
    return tuple(('IDRIVE %.0f mA (%s edges)' % (lv[j] * 1e3, how), data.idrive(lv[j]))
                 for j, how in ((k - 1, 'slower'), (k + 1, 'faster')) if 0 <= j < len(lv))


def DIODES():
    """The body-diode variants the switching runs use: rev 1's Toshiba model
    with the recovery fit and as supplied; rev 2's Infineon model as is."""
    if data.BODY_DIODE:
        return (('recovery fit', data.BODY_DIODE, None), ('as supplied', None, None))
    return (('maker\'s model', None, None),)


def MAIN():
    return DIODES()[0][0]


def plot_edges(res):
    if not PLOTS:
        return
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    r = res[(MAIN(), 150, 30, 5e-9)]
    w = r['wave']; t = w['time'] * 1e9
    e = [x * 1e9 for x in r['edges']]
    fig, ax = plt.subplots(2, 2, figsize=(12, 7), sharey='row')
    for col, (t0, title) in enumerate(((e[1], 'High side turns on'), (e[2], 'High side turns off'))):
        m = (t > t0 - 20) & (t < t0 + 150)
        a = ax[0, col]
        a.plot(t[m] - t0, (w['v(dH)'] - w['v(sH)'])[m], label='high-side V_DS')
        a.plot(t[m] - t0, (w['v(dL0)'] - w['v(sL)'])[m], label='low-side V_DS')
        a.axhline(data.FET['vdss'], color='r', ls='--', lw=1, label='%.0f V rating' % data.FET['vdss'])
        a.set_title(title + ', 30 A, 25.2 V, 5 nH, T_j 150 C'); a.legend(fontsize=8); a.grid(alpha=.3)
        a = ax[1, col]
        a.plot(t[m] - t0, w['i(vidh)'][m], label='high-side I_D')
        a.plot(t[m] - t0, w['i(vidl)'][m], label='low-side I_D')
        a.set_xlabel('ns'); a.legend(fontsize=8); a.grid(alpha=.3)
    ax[0, 0].set_ylabel('V'); ax[1, 0].set_ylabel('A')
    fig.tight_layout()
    os.makedirs(IMG, exist_ok=True)
    fig.savefig(os.path.join(IMG, 'switching-edges.png'), dpi=110)
    plt.close(fig)
    say('![Switching edges](images/stress/switching-edges.png)')
    say()


# =================================================================== 4. battery line
def pwm_current(I, D, f, t_end, phases, edge=20e-9):
    """PWL of the ESC's battery current: each channel draws I during its duty."""
    T = 1 / f
    pts = sorted({0.0} | {x for k in range(int(t_end * f) + 2) for ph in phases
                          for x in (k * T + ph * T, k * T + ph * T + edge,
                                    k * T + ph * T + D * T, k * T + ph * T + D * T + edge)
                          if 0 <= x <= t_end})
    def at(t):
        tot = 0.0
        for ph in phases:
            x = (t - ph * T) % T
            if x < edge:
                tot += I * x / edge
            elif x < D * T:
                tot += I
            elif x < D * T + edge:
                tot += I * (1 - (x - D * T) / edge)
        return tot
    return [(t, at(t)) for t in pts]


def bus_section():
    log('battery line')
    Bs = data.BUS
    say('## 4. The battery line: plugging in, full throttle, a throttle chop')
    say()
    onb = data.BULK.get('on_board')
    say('The pack (%.1f V, %.0f mOhm) through %.0f nH of leads to the ESC\'s '
        'pads, %s, the ESC\'s bridge capacitors '
        '(%d x %s at %.1f uF each under 25 V bias) and, through the stack lead '
        '(%.0f nH, %.0f mOhm), the FC\'s input: its TVS (SMF33A, breaking down '
        'at %.1f V, the middle of its 36.7-40.6 V range) and ceramics.' % (
            Bs['Vpack'], Bs['Rbat'] * 1e3, Bs['Llead'] * 1e9,
            ('nothing on the leads: the bus capacitance is on the board (%s)' % data.BULK['desc']) if onb
            else 'the external capacitor there (%s)' % data.BULK['desc'],
            12, data.C_BRIDGE['part'], data.C_BRIDGE['c_bias'] * 1e6,
            Bs['Lstack'] * 1e9, Bs['Rstack'] * 1e3, Bs['tvs_bv']))
    say()
    base = dict(Bs, Cext=data.BULK['c'], ESRext=data.BULK['esr'], ESLext=data.BULK['esl'])
    ifc = losses.fc_inputs(**data.FC_LOAD_MAX)[0] / Bs['Vpack']
    noext = dict(base, Cext=0)
    variants = ((('with the board\'s own capacitors', base),) if onb else
                (('with the external capacitor', base), ('without it', noext)))
    rows = []
    worst_plug = {}
    for tag, p in variants:
        for L in (100e-9, 200e-9, 300e-9):
            w = spice.bus(dict(p, Llead=L, plug=True, t_plug=0.1e-6, Ifc=0.0,
                               iesc=[(0, 0), (1, 0)], step=1e-9, maxstep=2e-9, tend=20e-6), 'plug')
            vb, vf = w['v(vb)'].max(), w['v(fc)'].max()
            worst_plug[(tag, L)] = vb
            rows.append(['Plug in a full 6S pack, ' + tag, '%.0f nH' % (L * 1e9), '%.1f V' % vb, '%.1f V' % vf,
                         '%.2f A' % w['i(vtv)'].max()])
    # full throttle: 4 x 30 A at 95 %, PWM in step (worst) and staggered
    f = data.AM32['f_max']
    for tag, phases in (('in step', [0, 0, 0, 0]), ('staggered', [0, .25, .5, .75])):
        iesc = pwm_current(30.0 * 1, 0.95, f, 200e-6, phases)
        for ctag, p in variants:
            w = spice.bus(dict(p, plug=False, Ifc=ifc, iesc=iesc, step=5e-9,
                               maxstep=10e-9, tend=200e-6), 'ripple')
            t = w['time']; m = t > 100e-6
            vpp = w['v(vb)'][m].max() - w['v(vb)'][m].min()
            icap = np.sqrt(np.mean(w['i(vxm)'][m] ** 2)) if 'i(vxm)' in w else float('nan')
            ibr = np.sqrt(np.mean(w['i(vbm)'][m] ** 2))
            rows.append(['4 motors x 30 A, PWM %s, %s' % (tag, ctag), '%.0f nH' % (Bs['Llead'] * 1e9),
                         '%.1f V (%.1f V p-p)' % (w['v(vb)'][m].max(), vpp), '%.1f V' % w['v(fc)'][m].max(),
                         'cap %.1f A rms, bridge caps %.1f A rms' % (icap, ibr) if icap == icap else 'bridge caps %.1f A rms' % ibr])
    # throttle chop: the motors regenerate into the pack
    for Rb in (Bs['Rbat'], 0.06, 0.10):
        for ctag, p in variants:
            iesc = [(0, 80.0), (1e-3, 80.0), (1.2e-3, data.REGEN['i_bus']), (6e-3, data.REGEN['i_bus']), (8e-3, 0.0)]
            w = spice.bus(dict(p, Rbat=Rb, plug=False, Ifc=ifc, iesc=iesc, step=50e-9,
                               maxstep=200e-9, tend=9e-3), 'chop')
            rows.append(['Throttle chop, %.0f A back into a %.0f mOhm pack, %s' % (-data.REGEN['i_bus'], Rb * 1e3, ctag),
                         '%.0f nH' % (Bs['Llead'] * 1e9), '%.1f V' % w['v(vb)'].max(), '%.1f V' % w['v(fc)'].max(),
                         '%.2f A' % w['i(vtv)'].max()])
    table(['Event', 'Leads', 'Peak at the FETs', 'Peak at the FC', 'TVS / capacitor current'], rows)
    grade = lambda v: True if v < 0.9 * data.FET['vdss'] else ('MARGINAL' if v < data.FET['vdss'] else False)
    fr = '%.0f V FETs' % data.FET['vdss']
    vwith = max(v for (tag, L), v in worst_plug.items() if tag != 'without it')
    found['plug'] = vwith
    if onb:
        verdict('Voltage', 'Plugging in a full 6S pack, leads up to 300 nH', grade(vwith), '%.1f V' % vwith, fr)
    else:
        vmax = max(v for (tag, L), v in worst_plug.items() if tag == 'without it')
        verdict('Voltage', 'Plugging in a full 6S pack, external capacitor fitted, leads up to 300 nH',
                grade(vwith), '%.1f V' % vwith, fr)
        verdict('Voltage', 'Plugging in a full 6S pack, external capacitor left off, leads up to 300 nH',
                grade(vmax), '%.1f V' % vmax, fr)
    ripple = max(float(r[4].split('cap ')[1].split(' A')[0]) for r in rows if r[4].startswith('cap '))
    found['ripple'] = ripple
    if data.BULK.get('ripple'):
        verdict('Voltage', 'Ripple current in the external capacitors, 4 x 30 A',
                ripple <= data.BULK['ripple'], '%.1f A rms' % ripple,
                '%.2f A rms (2 x FR-A 100 uF, 100 kHz, 105 C)' % data.BULK['ripple'])
    else:
        # ceramics: the ripple heats each capacitor through its ESR; Murata
        # allows 20 C of self-heating.  Rth 50 K/W for a 1210 soldered to
        # the planes: ASSUMPTION
        n = data.BULK_N
        rise = (ripple / n) ** 2 * data.BULK['esr'] * n * 50.0
        found['ripple_rise'] = rise
        verdict('Voltage', 'Ripple self-heating of the board\'s bus capacitors, 4 x 30 A',
                rise <= 20.0, '%.1f A rms, %.1f C each' % (ripple, rise), '20 C (Murata)')
    say('The ripple current is the pulsed battery current each channel draws '
        'while its high side is on, less what the bridge capacitors supply; four '
        'channels switching in step is the worst case, evenly staggered the best '
        '(the four AM32 processors run their PWM independently, so the real case '
        'drifts between the two).  A throttle chop turns the motors into '
        'generators: at full speed a motor\'s back-EMF is about %.0f V, and the '
        'battery current it can push back peaks at E^2 / (4 V R) = %.0f A when '
        'the duty drops to half of E/V, through its %.0f mOhm; with the wiring\'s '
        'resistance, %.0f A for all four motors is used.  The pack takes that current, so the rise is set by the '
        'pack\'s resistance, which no maker publishes: a new, warm pack is about '
        '25 mOhm with its leads, a tired or cold one 60-100 mOhm.' % (
            REGEN_E, REGEN_E ** 2 / (4 * data.BATTERY['vfull'] * data.MOTOR['r']), data.MOTOR['r'] * 1e3,
            -data.REGEN['i_bus']))
    say()
    return rows


# back-EMF at full speed: the pack voltage less the motor's own drop at full current
REGEN_E = data.MOTOR['vtest'] - data.MOTOR['load'][-1][1] * data.MOTOR['r']


# =================================================================== 5. the stack lead
def lead_section(i_motor=20.0):
    log('stack lead')
    c = copper.extract('esc')
    J = data.STACK_CONN
    L = data.LEAD
    say('## 5. The stack lead, and the FC\'s supply')
    say()
    if L['soldered']:
        say('The FC takes its own power from the ESC through the 8-wire stack lead '
            '(pin 1 VBAT, pin 2 ground): soldered to the ESC\'s pads, and at the FC '
            'a %s, rated %.1f A per contact, %.0f C (%d mOhm per contact assumed, '
            '%d mOhm aged).  The lead feeds only the FC\'s 5 V BEC (and through it '
            'the 3.3 V buck); its pin 4 takes that 3.3 V back to the ESC\'s four MCUs '
            '(%.0f mA).  The 9 V video supply has its own battery pads, wired '
            'to the ESC\'s battery pads, so the video load never passes through '
            'the lead.' % (J['part'], J['i_rated'], J['t_max'], J['r_contact'] * 1e3,
                           J['r_contact_aged'] * 1e3, data.ESC_3V3_LOAD * 1e3))
    else:
        say('The FC takes its power from the ESC through the 8-pin JST-SH lead (pin 1 '
            'VBAT, pin 2 GND), rated %.0f A per contact with AWG 28 wire, %d mOhm per '
            'contact (%d mOhm after the maker\'s environmental tests), and %.0f C '
            'including the contact\'s own heating (JST SH catalogue).  The FC also has '
            'battery pads, which circuit.py says a digital VTX needs.' % (
                J['i_rated'], J['r_contact'] * 1e3, J['r_contact_aged'] * 1e3, J['t_max']))
    say()
    rows = []
    for tag, i5, i9 in (('both rails at their 2 A rating', 2.0, 2.0),
                        ('HD VTX at 1.5 A on 9 V, 1 A on 5 V', 1.0, 1.5),
                        ('analog: 0.5 A on 9 V, 0.5 A on 5 V', 0.5, 0.5)):
        lead, video = losses.fc_inputs(i5, i9)
        cells = []
        for V in (25.2, 21.0, 19.8):
            i = lead / V
            cells.append('%.2f A%s' % (i, ' **over**' if i > J['i_rated'] else ''))
        rows.append([tag, '%.1f W' % (lead + video), '%.1f W' % lead] + cells +
                    (['%.2f A' % (video / 19.8)] if L['split'] else []))
    table(['FC load', 'FC input', 'Through the lead', 'Lead current, full 6S (25.2 V)', 'sagging (21.0 V)',
           'empty (19.8 V)'] + (['Video pads\' wire, empty 6S'] if L['split'] else []), rows)
    lead_max = losses.fc_inputs(2.0, 2.0)[0]
    found['lead'] = lead_max / 19.8
    verdict('Stack lead', 'FC at full load, lead current on an empty 6S pack', lead_max / 19.8 <= J['i_rated'],
            '%.2f A' % (lead_max / 19.8), '%.1f A per contact (%s)' % (J['i_rated'], J['part']))
    I = {n: i_motor for n in CH}
    sg = dcflow.solve(c, 'GND', {**{'R_SH%d' % n: I[n] for n in CH}, 'P_BAT-': -sum(I.values())}, T=60.0)
    if L['kelvin']:
        # the lead's ground (FC_GND) meets the ESC's ground only at its
        # battery pad, where the video pads' wire lands too: the motor
        # current's drop across the planes is outside the loop the two make
        i_loop = 0.0
        found['loop'] = i_loop
        say('**The ground loop.**  The FC\'s ground reaches the ESC by two paths: '
            'the lead\'s ground wire and the video pads\' ground wire.  On the ESC '
            'the lead\'s ground pad is its own net (FC_GND), joined to the ground '
            'plane only at the battery pad, where the video wire lands as well, so '
            'the motor current\'s drop across the ESC\'s planes (%.0f mV at %.0f A '
            'per motor, from the battery pad to the farthest shunt) is not in the '
            'loop and drives no current round it.  The two VBAT inputs are separate '
            'nets on the FC, so there is no battery-side loop.' % (
                max(sg.term_v['R_SH%d' % n] - sg.term_v['P_BAT-'] for n in CH) * 1e3, i_motor))
        say()
        verdict('Stack lead', 'Ground-loop current in the lead\'s GND contact, video pads also wired, %.0f A per motor'
                % i_motor, True, '0 A (the loop does not enclose the planes)', '%.1f A' % J['i_rated'])
        ref = 'P_BAT-'
        v_gnd = 0.0
    else:
        sv = dcflow.solve(c, 'VBAT', {**{'Q%dAH' % n: -I[n] for n in CH}, 'P_BAT+': sum(I.values())}, T=60.0)
        v_gnd = sg.term_v['J_FC'] - sg.term_v['P_BAT-']
        v_bat = sv.term_v['P_BAT+'] - sv.term_v['J_FC']
        rg = dcflow.solve(c, 'GND', {'J_FC': 1.0, 'P_BAT-': -1.0}, T=60.0)
        rv = dcflow.solve(c, 'VBAT', {'P_BAT+': 1.0, 'J_FC': -1.0}, T=60.0)
        r_gnd = rg.term_v['J_FC'] - rg.term_v['P_BAT-']
        r_bat = rv.term_v['P_BAT+'] - rv.term_v['J_FC']
        r_wire = data.STACK_LEAD['length'] * data.STACK_LEAD['r_wire'] + 2 * J['r_contact']
        r_pad = 0.10 * 0.053 + 2e-3          # 10 cm of AWG 22 and its joints: ASSUMPTION
        i_loop = v_gnd / (r_gnd + r_wire + r_pad)
        i_loopv = v_bat / (r_bat + r_wire + r_pad)
        found['loop'] = i_loop
        say('**With the FC\'s battery pads wired to the ESC\'s battery pads as well**, '
            'the lead and the pad wires make a loop, and the motor current\'s drop '
            'across the ESC\'s planes drives current round it.  At %.0f A on every '
            'motor the ESC\'s ground plane at the stack connector sits %.0f mV above '
            'its battery pad (%.2f mOhm between them), and its battery plane %.0f mV '
            'below.  Through the lead (%.0f mOhm per wire, contacts included) and '
            '10 cm of AWG 22 back to the pads, that pushes **%.1f A through the GND '
            'contact** and %.1f A through the VBAT contact, on top of the FC\'s own '
            'current, whatever the FC draws.' % (
                i_motor, v_gnd * 1e3, r_gnd * 1e3, v_bat * 1e3, r_wire * 1e3, i_loop, i_loopv))
        say()
        verdict('Stack lead', 'Ground-loop current in the lead\'s GND contact, FC pads also wired, %.0f A per motor' % i_motor,
                abs(i_loop) <= J['i_rated'], '%.1f A' % i_loop, '%.0f A' % J['i_rated'])
        ref = 'J_FC'
    # ground offsets the signals see
    sg30 = dcflow.solve(c, 'GND', {**{'R_SH%d' % n: 30.0 for n in CH}, 'P_BAT-': -120.0}, T=60.0)
    off = {n: sg30.term_v['U_ESC%d' % n] - sg30.term_v[ref] for n in CH}
    cs = {n: sg30.term_v['U_CS%d' % n] - sg30.term_v[ref] for n in CH}
    found['dshot_offset'] = max(abs(v) for v in off.values())
    err = np.mean(list(cs.values())) / 12.5e-3
    say('Ground offsets at 30 A on every motor: each ESC processor\'s ground '
        'against the lead\'s ground (%s), which the FC\'s DShot signals are '
        'referenced to: %s mV.  DShot is 3.3 V logic with about 1 V '
        'of noise margin, so this is harmless.  The current-sense amplifiers\' '
        'grounds sit %s mV from it.  CUR is the mean of the four '
        'outputs, read against the FC\'s ground at 12.5 mV per amp of battery '
        'current, so the mean offset reads as %+.1f A on the 120 A Betaflight '
        'shows (%.0f %%): a reading error, not a fault.' % (
            'at the battery pad' if ref == 'P_BAT-' else 'at the stack connector',
            ', '.join('%+.0f' % (v * 1e3) for v in off.values()),
            ', '.join('%+.0f' % (v * 1e3) for v in cs.values()), err, 100 * err / 120))
    say()
    # the FC's own supply copper at its full load
    cf = copper.extract('fc')
    rows = []
    for net, (cur, _) in stack.fc_paths().items():
        s = dcflow.solve(cf, net, cur, T=100.0)
        mp = dcflow.maps(cf, s)
        bc = max([a for h, a in dcflow.barrel_currents(cf, s)] or [0.0])
        src = max(cur, key=cur.get)
        drop = max(s.term_v[src] - s.term_v[k] for k in cur)
        jl = [float(mp['J'][l].max()) for l in range(len(cf.layers))]
        lj = int(np.argmax(jl))
        rows.append([net, ', '.join('%s %+.2f A' % (k, v) for k, v in cur.items()), '%.0f mV' % (drop * 1e3),
                     '%.2f W' % s.loss, '%.0f A/mm2 (%s, %.3f mm copper)' % (jl[lj], cf.layers[lj], cf.t[lj]),
                     '%.2f A' % bc])
    say('The FC\'s own supply copper at its full load (copper at 100 C).  The '
        'FC\'s inner layers are 0.5 oz (%.4f mm):' % cf.t[1])
    say()
    table(['Net', 'Where the current goes in and out', 'Largest drop', 'Loss', 'Densest point', 'Most in one via'], rows)
    return dict(i_loop=i_loop, v_gnd=v_gnd)


# =================================================================== 6. heat
def limit_of(name, m, shunt_w=0.0):
    """(limit C, what it is) for a part the stack model follows."""
    board, ref = name.split(' ', 1)
    p = m.parts[name]
    if p.get('kind'):
        diel, t, what = data.CAPS[p['kind']]
        return t, '%s capacitor (%s)' % (diel, what.split(',')[0])
    D = data
    table_ = [('Q', lambda: (D.FET['tch_max'], 'FET channel, abs max')),
              ('U_GD', lambda: (D.DRIVER['tj_max'], '%s junction' % D.DRIVER['part'])),
              ('U_ESC', lambda: (D.MCU_ESC['tj_max'], '%s junction' % D.MCU_ESC['part'])),
              ('U_CS', lambda: (D.CSA['ta_max'], 'INA186 operating')),
              ('U_GVDD', lambda: (D.GATE_LDO['tj_max'], '%s junction' % D.GATE_LDO['part'])),
              ('U_BUCK5', lambda: (D.BUCK5['tj_max'], '%s junction' % D.BUCK5['part'])),
              ('U_BUCK9', lambda: (D.BUCK9['tj_max'], '%s junction' % D.BUCK9['part'])),
              ('U_BUCK3', lambda: (D.V33['tj_max'], '%s junction' % D.V33['part'])),
              ('U_BUCK', lambda: (D.ESC_BUCK['tj_max'], '%s junction' % D.ESC_BUCK['part'])),
              ('U_LDO', lambda: (D.V33['tj_max'], '%s junction' % D.V33['part'])),
              ('U_FC', lambda: (D.MCU_FC['tj_max'], '%s junction' % D.MCU_FC['part'])),
              ('U_IMU', lambda: (D.GYRO['t_max'], '%s operating' % D.GYRO['part'])),
              ('U_FLASH', lambda: (D.FLASH['t_max'], '%s operating' % D.FLASH['part'])),
              ('U_OSD', lambda: (D.OSD['t_max'], '%s operating' % D.OSD['part'])),
              ('U_TSW', lambda: (D.THERMOSTAT['t_max'], '%s operating' % D.THERMOSTAT['part'])),
              ('J_HD', lambda: (D.HD_CONN['t_max'], '%s' % D.HD_CONN['part'])),
              ('J_', lambda: (D.STACK_CONN['t_max'], '%s' % D.STACK_CONN['part'])),
              ('L', lambda: (D.INDUCTORS.get(ref, {}).get('t_max', 125.0), 'inductor')),
              ('R_SH', lambda: (D.SHUNT['t_zero'] - (D.SHUNT['t_zero'] - D.SHUNT['t_full']) * shunt_w / D.SHUNT['p_rated'],
                                'shunt terminal, derated for its power')),
              ('RT', lambda: (125.0, 'NTC thermistor (Murata NCU15, 125 C)')),
              ('D_TVS', lambda: (175.0, 'TVS junction'))]
    for pre, f in table_:
        if ref.startswith(pre):
            return f()
    return None, None


def pwm_f(throttle):
    """AM32's variable PWM: 24 kHz at low speed to 48 kHz at high speed."""
    lo, hi = data.AM32['f_min'], data.AM32['f_max']
    return lo + (hi - lo) * min(1.0, max(0.0, throttle / 100.0))


def operating(throttle, V, sw, fc=None, per_motor=None):
    """Operating point: all motors at a throttle (%), or per_motor {n: throttle}."""
    th = per_motor or {n: throttle for n in CH}
    I, D, Ib = {}, {}, {}
    for n in CH:
        ib, d, i = losses.limited(th[n], V)
        I[n], D[n], Ib[n] = i, d, ib
    op = dict(esc=dict(V=V, f=pwm_f(max(th.values())), dead=data.BRIDGE['dead'],
                       I=I, D=D, sw=sw), Ib=Ib)
    if fc:
        op['fc'] = fc_op(fc, V)
    return op


def fc_op(fc, V):
    lead, video = losses.fc_inputs(fc['i5'], fc['i9'])
    return dict(fc, i_lead=lead / V, i_video=video / V)


def _steady(m, op, iters=4):
    T = None
    for _ in range(iters):
        T = m.solver.steady(m.heat(op, T))
        if np.nanmax(T) > 400:
            break
    return T


def steady(m, op, iters=4):
    """Steady state.  With rev 2's thermostat: if the 9 V BEC's sensor would
    pass its trip point, the thermostat switches the video supply off and on
    and holds it there; the state solved is the one with the sensor at its
    trip point, the video load scaled to the share of the time it is on
    (op['fc']['vtx_on'], changed in place)."""
    T = _steady(m, op, iters)
    th = data.THERMOSTAT
    fc = op.get('fc')
    if not (th and fc and fc['i9'] > 0):
        return T
    name = 'FC ' + th['ref']
    t1 = m.temp(T, name)
    if t1 <= th['trip']:
        fc['vtx_on'] = 1.0
        return T
    V = op['esc']['V'] if 'esc' in op else data.BATTERY['vfull']
    off = dict(op, fc=fc_op(dict(fc, i9=0.0), V))
    T0 = _steady(m, off, iters)
    t0 = m.temp(T0, name)
    if t0 >= th['trip']:
        op['fc'] = dict(off['fc'], vtx_on=0.0)
        return T0
    x = (th['trip'] - t0) / (t1 - t0)
    op['fc'] = dict(fc_op(dict(fc, i9=fc['i9'] * x), V), vtx_on=x)
    return _steady(m, op, iters)


def worst(m, T, op):
    """(margin C, part, temperature, limit, what) for the part closest to its limit."""
    out = []
    for name in m.parts:
        sh = 0.0
        if name.startswith('ESC R_SH') and 'esc' in op:
            n = int(name[-1])
            sh = op['esc']['D'][n] * op['esc']['I'][n] ** 2 * data.SHUNT['r']
        lim, what = limit_of(name, m, sh)
        if lim is None:
            continue
        t = m.temp(T, name)
        out.append((lim - t, name, t, lim, what))
    return sorted(out)


def heat_section(sw):
    log('heat: steady limits')
    say('## 6. Heat: the stack in hot air')
    say()
    say('Both boards as thermal grids (%.1f mm cells on each of the six copper '
        'layers, copper coverage from the boards themselves, every via), the FC '
        '%.0f mm above the ESC, exchanging heat across the gap by conduction and '
        'radiation; outer faces cooled by the air and by radiation.  Heat from '
        'every FET (on-resistance at its own junction temperature, the simulated '
        'switching energies, body-diode dead time), the shunts, the drivers, the '
        'regulators, the processors and the copper itself (section 2, at each '
        'cell\'s temperature).  The FC carries its maximum load in every run: '
        '2 A on 5 V and 2 A on 9 V%s.' % (HEAT_H, data.STACK['gap'],
        ' (where the video supply\'s thermostat cuts the 9 V BEC at %.0f C, the '
        'tables say how much of the time the video stays on)' % data.THERMOSTAT['trip']
        if data.THERMOSTAT else ''))
    say()
    say('Motor current comes from the motor maker\'s thrust-stand table '
        '(%s): battery current against throttle, scaled to the pack voltage; the '
        'phase current is that over the duty; AM32 holds each motor to %.0f A '
        'battery-side.' % (data.MOTOR['part'], data.AM32['current_limit']))
    say()
    fcmax = data.FC_LOAD_MAX
    V = data.BATTERY['vfull']
    rows = []
    results = {}

    def search(m, ok):
        lo, hi, best = 0.0, 100.0, None
        for _ in range(2 if QUICK else 8):
            mid = (lo + hi) / 2
            op = operating(mid, V, sw, fcmax)
            T = steady(m, op)
            if ok(m, T, op):
                lo, best = mid, (mid, op, T)
            else:
                hi = mid
        if best is None:
            op = operating(0.0, V, sw, fcmax)
            best = (0.0, op, steady(m, op))
        return best

    all_ok = lambda m, T, op: worst(m, T, op)[0][0] >= 0
    fet_ok = lambda m, T, op: max(m.temp(T, k) for k in m.parts if k.startswith('ESC Q')) <= 150.0
    for v in ((5.0,) if QUICK else (2.0, 5.0, 10.0)):
        for Ta in ((HOT,) if QUICK else AIRS):
            m = model(v, Ta)
            th, op, T = search(m, all_ok)
            th2, op2, T2 = search(m, fet_ok)
            results[(v, Ta)] = (th, op, T, th2, op2)
            nxt = worst(m, steady(m, operating(min(th + 3, 100), V, sw, fcmax)), op)[0]
            rows.append(['%.0f m/s' % v, '%.0f C' % Ta,
                         '%.0f %% (%.1f A)' % (th, op['Ib'][1]),
                         '%s (%s, %.0f C)' % (nxt[1], nxt[4], nxt[3]),
                         '%.0f %% (%.1f A battery, %.1f A phase)' % (th2, op2['Ib'][1], op2['esc']['I'][1])] +
                        (['%.0f %%' % (100 * op2['fc'].get('vtx_on', 1.0))] if data.THERMOSTAT else []))
            found.setdefault('hold', {})[(v, Ta)] = (th, th2, nxt[1], nxt[4], op2['fc'].get('vtx_on', 1.0))
            log('  air %.0f m/s, %.0f C: %.0f %% all ratings (%s), %.0f %% FETs 150 C' % (v, Ta, th, nxt[1], th2))
    say('**What the stack can hold indefinitely**: the highest throttle on all '
        'four motors that holds, at steady state, (a) every part inside its '
        'rating, and (b) the FETs under 150 C (the power stage survives, even '
        'where smaller parts are out of their ratings).  Bisection to 1 %:')
    say()
    table(['Air over the stack', 'Air temperature', '(a) Every part in its rating: throttle (battery A per motor)',
           'First part past its rating above that', '(b) FETs under 150 C'] +
          (['Video on, at (b)'] if data.THERMOSTAT else []), rows)
    # where the heat comes from, hovering on a hot day
    m = model(5.0, HOT)
    op = operating(HOVER, V, sw, fcmax)
    T = steady(m, op)
    e = op['esc']
    cat = {'FET conduction': 0.0, 'FET switching': 0.0, 'body diode in the dead time': 0.0, 'shunts': 0.0, 'gate drive': 0.0}
    for n in CH:
        Tj = {p + s_: m.temp(T, 'ESC Q%d%s%s' % (n, p, s_)) for p in PH for s_ in 'HL'}
        I, D, f = e['I'][n], e['D'][n], e['f']
        esw = (np.interp(I, sw['I'], sw['on']) + np.interp(I, sw['I'], sw['off'])) * V / sw['V']
        for p in PH:
            cat['FET conduction'] += D / 3 * I * I * losses.rds(Tj[p + 'H']) + (2 - D) / 3 * I * I * losses.rds(Tj[p + 'L'])
            cat['FET switching'] += esw * f / 3
            cat['body diode in the dead time'] += 2 * e['dead'] * f * data.FET['vsd_hot'] * I / 3
        cat['shunts'] += D * I * I * data.SHUNT['r']
        cat['gate drive'] += losses.driver(V, f)
    if data.GATE_LDO:
        cat['gate-drive LDO'] = (V - data.GVDD) * losses.gvdd_current([e['f']] * len(CH))
    Tcu = np.mean([m.temp(T, k) for k in m.parts if k.startswith('ESC Q')])
    for k, w in copperloss.loss_groups(m.units, e['I'], e['D']).items():
        cat['copper: ' + k] = w * (1 + dcflow.ALPHA * (Tcu - 20))
    total = sum(cat.values())
    found['hover_heat'] = (total, cat)
    say('Where the ESC\'s heat comes from while hovering (%.0f %% throttle: %.1f A per '
        'motor from the pack, %.1f A in the motor phases at %.0f %% duty, %.0f kHz PWM) '
        'in %.0f C air, 5 m/s, at the temperatures that reach (copper near %.0f C):' % (
            HOVER, op['Ib'][1], e['I'][1], 100 * e['D'][1], e['f'] / 1e3, HOT, Tcu))
    say()
    table(['Source', 'Watts', 'Share'], [[k, '%.2f' % w, '%.0f %%' % (100 * w / total)]
                                        for k, w in sorted(cat.items(), key=lambda kv: -kv[1])] +
          [['**ESC total**', '**%.1f**' % total, '']])
    say('A BLDC motor takes its phase current only while its bridge is on (the '
        'duty), so at part throttle the current in the FETs and the copper is '
        'the battery current over the duty: at hover, %.1f times it.  '
        'Both FETs in the path conduct all the time (synchronous rectification), '
        'and so does the copper they feed.' % (1 / e['D'][1]))
    say()
    say('For scale: this motor and prop hover a %.0f g quad at about %.0f %% throttle '
        '(%.1f A per motor battery-side) and draw %.1f A per motor at full throttle '
        'on a full pack, which AM32 cuts to %.0f A.' % (
            data.MOTOR['auw'], HOVER, losses.motor(HOVER, V)[0], losses.motor(100, V)[0], data.AM32['current_limit']))
    say()
    return results


HEAT_H = 0.5
_models = {}


def model(v, Ta, gap=None):
    key = (v, Ta, gap)
    if key not in _models:
        _models[key] = stack.StackModel(thermal.air(v), Ta, h=HEAT_H, gap=gap, out=OUT)
    return _models[key]


def run_transient(m, schedule, sw, T0, dt, fc, V, am32=True, watch=()):
    """watch: part names, or {label: [part names]} to follow the hottest of each group."""
    """Step the stack through a throttle schedule [(seconds, throttle), ...].

    With am32, AM32's temperature limit acts on each motor from its sensor
    (rev 1: the processor's own die; rev 2: the FET thermistor beside its
    FETs): above the limit the motor's duty is cut to a quarter, falling to
    nothing 10 C higher (firmware/README.md).  Rev 2's video thermostat
    switches the 9 V load off at its trip point and on again 20 C lower."""
    T = T0.copy()
    groups = watch if isinstance(watch, dict) else {k: [k] for k in watch}
    trace = dict(t=[], throttle=[], cut=[], applied=[], vtx=[], **{k: [] for k in groups})
    t = 0.0
    lim = data.AM32['temp_limit']
    sensor = data.AM32.get('sensor', 'U_ESC')
    tstat = data.THERMOSTAT if fc and fc.get('i9') else None
    vtx = True
    first = {}
    for dur, th in schedule:
        for _ in range(int(round(dur / dt))):
            per = {}
            cut = False
            for n in CH:
                tm = m.temp(T, 'ESC %s%d' % (sensor, n))
                cap = 100.0
                if am32 and tm > lim:
                    cap = max(0.0, 25.0 * (1 - (tm - lim) / 10.0))
                    cut = True
                per[n] = min(th, cap)
            fc_now = fc
            if tstat:
                ts = m.temp(T, 'FC ' + tstat['ref'])
                if vtx and ts >= tstat['trip']:
                    vtx = False
                elif not vtx and ts <= tstat['trip'] - tstat['hyst']:
                    vtx = True
                if not vtx:
                    fc_now = dict(fc, i9=0.0)
            op = operating(th, V, sw, fc_now, per_motor=per)
            T = m.solver.step(T, m.heat(op, T), dt)
            t += dt
            trace['t'].append(t); trace['throttle'].append(th); trace['cut'].append(cut); trace['vtx'].append(vtx)
            trace['applied'].append(min(per.values()))
            for k, names in groups.items():
                trace[k].append(max(m.temp(T, x) for x in names))
            for margin, name, temp, limit, what in worst(m, T, op):
                if margin < 0 and name not in first:
                    first[name] = (t, temp, limit, what)
    return T, trace, first


HOVER = round(losses.hover(data.BATTERY['vfull']), 1)
last_burst = {}     # % throttle for the quad's weight on a full pack


def bursts_section(sw, fcmax):
    log('heat: bursts')
    V = data.BATTERY['vfull']
    say('**Bursts.**  Hovering (%.0f %% throttle) until the stack has settled, '
        'then full throttle, which AM32 holds to %.0f A per motor: the '
        'temperatures while hovering, and how fast the hottest parts climb.' % (
            HOVER, data.AM32['current_limit']))
    say()
    rows = []
    for Ta, v in (((HOT, 5.0),) if QUICK else ((25.0, 5.0), (HOT, 5.0), (HOT, 10.0), (60.0, 5.0))):
        m = model(v, Ta)
        op0 = operating(HOVER, V, sw, fcmax)
        T0 = steady(m, op0)
        fets = [k for k in m.parts if k.startswith('ESC Q')]
        caps = esc_caps(m)
        mcu = ['ESC U_ESC%d' % n for n in CH]
        hot = lambda T, ks: max(m.temp(T, k) for k in ks)
        T, tr, first = run_transient(m, [(3.0 if QUICK else 10.0, 100.0)], sw, T0, 0.25, fcmax, V, am32=False,
                                     watch=fets + mcu + caps)
        if (Ta, v) == (HOT, 5.0):
            last_burst.update({k: tr[k] for k in fets})
        t = np.array(tr['t'])
        fmax = np.max([tr[k] for k in fets], axis=0)
        mmax = np.max([tr[k] for k in mcu], axis=0)
        when = lambda arr, lim: ('%.1f s' % t[np.argmax(arr >= lim)]) if (arr >= lim).any() else '> %.0f s' % t[-1]
        at = lambda arr, s_: ('%.0f C' % np.interp(s_, t, arr)) if np.interp(s_, t, arr) < data.FET['tch_max'] else 'past 175 C'
        rows.append(['%.0f C, %.0f m/s' % (Ta, v),
                     '%.0f / %.0f / %.0f C' % (hot(T0, fets), hot(T0, mcu), hot(T0, caps)),
                     '%s / %s' % (at(fmax, 1.0), at(fmax, 2.0)),
                     when(fmax, 150.0), when(fmax, data.FET['tch_max']), when(mmax, data.AM32['temp_limit'])])
        found.setdefault('bursts', {})[(Ta, v)] = (t[np.argmax(fmax >= data.FET['tch_max'])] if (fmax >= data.FET['tch_max']).any() else None,
                                                   t[np.argmax(mmax >= data.AM32['temp_limit'])] if (mmax >= data.AM32['temp_limit']).any() else None)
    table(['Air', 'Hovering: hottest FET / processor / %s capacitor' % CAP_LABEL[0],
           'Hottest FET after 1 / 2 s of full throttle', 'A FET reaches 150 C', 'A FET reaches its 175 C maximum',
           'A processor reaches AM32\'s %.0f C cut' % data.AM32['temp_limit']], rows)
    # which FET got hottest, and how far it is from a battery pad
    m = model(5.0, HOT)
    ce = m.ce
    name = max((k for k in m.parts if k.startswith('ESC Q')), key=lambda k: max(last_burst.get(k, [0])))
    q = ce.parts[name.split()[1]]
    pad = min(np.hypot(q['x'] - ce.parts[p]['x'], q['y'] - ce.parts[p]['y']) for p in ('P_BAT+', 'P_BAT-'))
    t175, tcut = found['bursts'].get((HOT, 5.0), (None, None))
    sensor = ('each processor\'s own die, a few millimetres from its FETs' if data.AM32.get('sensor', 'U_ESC') == 'U_ESC'
              else 'a thermistor beside each channel\'s FETs')
    say('The hottest FET is %s, %.1f mm from a battery pad.  AM32\'s '
        'temperature limit reads %s%s.  The numbers past 175 C are not '
        'survivable, so they are not shown.' % (
            name.split()[1], pad, sensor,
            (', so in a burst it trips after the FETs are already past their maximum'
             if t175 is not None and (tcut is None or tcut > t175) else '')))
    say()


CAP_LABEL = ['lowest-rated']


BOARD_NAMES = ('ESC', 'FC')


def esc_caps(m):
    """The ESC's capacitors with the lowest temperature rating."""
    caps = [k for k in m.parts if k.startswith('ESC') and m.parts[k].get('kind')]
    low = min(data.CAPS[m.parts[k]['kind']][1] for k in caps)
    CAP_LABEL[0] = '%.0f C' % low
    return [k for k in caps if data.CAPS[m.parts[k]['kind']][1] == low]


def groups_of(m):
    """The parts the flight follows, as the hottest of each kind."""
    g = {
        'ESC FETs (hottest)': [x for x in m.parts if x.startswith('ESC Q')],
        'ESC processors (hottest)': ['ESC U_ESC%d' % n for n in CH],
        'ESC gate drivers (hottest)': ['ESC U_GD%d' % n for n in CH],
        'ESC current amplifiers (hottest)': ['ESC U_CS%d' % n for n in CH],
    }
    for b in BOARD_NAMES:
        caps = [x for x in m.parts if x.startswith(b + ' ') and m.parts[x].get('kind')]
        for diel, lim in sorted({data.CAPS[m.parts[x]['kind']][:2] for x in caps}, key=lambda d: d[1]):
            g['%s capacitors, %s (hottest)' % (b, diel)] = [x for x in caps if data.CAPS[m.parts[x]['kind']][0] == diel]
    g['ESC shunts (hottest)'] = ['ESC R_SH%d' % n for n in CH]
    for label, names in (('ESC stack connector', ['ESC J_FC']), ('FC stack connector', ['FC J_ESC']),
                         ('FC HD video connector', ['FC J_HD']), ('FC gyro', ['FC U_IMU']),
                         ('FC processor', ['FC U_FC']), ('FC OSD', ['FC U_OSD']), ('FC flash', ['FC U_FLASH']),
                         ('FC 9 V buck', ['FC U_BUCK9']), ('FC 5 V buck', ['FC U_BUCK5']),
                         ('FC 3.3 V regulator', ['FC ' + data.V33['ref']])):
        if all(x in m.parts for x in names):
            g[label] = names
    return g


def flight_section(sw, fcmax):
    log('heat: hot flight')
    V = data.BATTERY['vfull']
    Ta, v = HOT, 5.0
    m = model(v, Ta)
    cycle = [(2.0, 100.0), (4.0, 60.0), (14.0, 40.0)]
    sched = cycle * (1 if QUICK else 9)          # three minutes
    Ib = sum(d * losses.limited(th, V)[0] for d, th in cycle) / sum(d for d, _ in cycle)
    say('**A hard flight on a hot day.**  %.0f C air, 5 m/s over the stack, a full '
        'pack, three minutes of 20 s cycles: 2 s full throttle, 4 s at 60 %%, '
        '14 s at 40 %% (on average %.1f A per motor, %.0f A from the pack: a '
        '1300 mAh pack empties in about %.1f minutes at that rate).  Starting '
        'from the air temperature, with AM32\'s temperature limit active.' % (
            HOT, Ib, 4 * Ib, 1.3 / (4 * Ib) * 60))
    say()
    groups = groups_of(m)
    T0 = np.full(m.n, Ta)
    T, tr, first = run_transient(m, sched, sw, T0, 0.5, fcmax, V, am32=True, watch=groups)
    rows = []
    for label, names in groups.items():
        lim, what = limit_of(names[0], m)
        past = [first[x][0] for x in names if x in first]
        rows.append([label, what, '%.0f C' % max(tr[label]), '%.0f C' % lim if lim else '-',
                     '%.0f s' % min(past) if past else '-'])
    table(['Part', 'Limit', 'Peak', 'Rating', 'First past it at'], rows)
    cut = [t for t, c in zip(tr['t'], tr['cut']) if c]
    frac = np.mean(tr['cut'])
    if cut:
        say('AM32\'s temperature limit (%.0f C at its sensor) first cut '
            'power at %.0f s, and was cutting for %.0f %% of the flight: each time, '
            'that motor drops to a quarter of full power or less, which in the air '
            'is a sudden loss of thrust on one corner.  It is what keeps the FETs '
            'below their limit here.' % (data.AM32['temp_limit'], cut[0], 100 * frac))
    else:
        say('AM32\'s temperature limit never cut in.')
    vtx_off = 1 - float(np.mean(tr['vtx'])) if data.THERMOSTAT else 0.0
    if data.THERMOSTAT:
        say('The video supply\'s thermostat %s.' % (
            'switched the video off for %.0f %% of the flight' % (100 * vtx_off) if vtx_off > 0
            else 'never tripped: the video stayed on all flight'))
    say()
    found['flight'] = dict(cut=cut[0] if cut else None, frac=frac, vtx_off=vtx_off,
                           fet=max(tr['ESC FETs (hottest)']), mcu=max(tr['ESC processors (hottest)']),
                           peaks={k: max(v) for k, v in tr.items() if k in groups},
                           first=min(first.items(), key=lambda kv: kv[1][0]) if first else None)
    np.savez(os.path.join(OUT, 'hot-flight-%s.npz' % data.design_name()), T=T,
             **{k: np.asarray(v) for k, v in tr.items()})
    plot_flight(tr, groups, m)
    plot_maps(m, T, 'hot-flight')
    return first, tr


def ground_section(sw):
    log('heat: on the ground')
    V = data.BATTERY['vfull']
    m0 = model(0.0, HOT)
    tau = m0.solver.cap.sum() / m0.solver.gamb.sum()
    say('**Waiting on the ground with the video on.**  Still air, the motors '
        'stopped (the ESC\'s processors and gate drivers on).  The stack\'s '
        'thermal time constant in still air is about %.0f minutes, so it '
        'reaches the steady state below after about %.0f minutes; the second table is '
        'the first minutes.%s' % (tau / 60, 4 * tau / 60, (
            '  The video supply\'s thermostat (%s at the 9 V BEC) switches the '
            'video off at %.0f C and on again at %.0f C: where it trips, the steady '
            'state is that cycle, and the table gives the share of the time the '
            'video is on.' % (data.THERMOSTAT['part'], data.THERMOSTAT['trip'],
                              data.THERMOSTAT['trip'] - data.THERMOSTAT['hyst'])) if data.THERMOSTAT else ''))
    say()
    rows = []
    res = {}
    for Ta in ((HOT,) if QUICK else AIRS):
        for tag, fc in (('both rails at 2 A', data.FC_LOAD_MAX), ('9 V at 1.5 A, 5 V at 1 A', dict(i5=1.0, i9=1.5)),
                        ('9 V at 1 A, 5 V at 0.5 A', dict(i5=0.5, i9=1.0))):
            m = model(0.0, Ta)
            op = operating(0.0, V, sw, fc)
            T = steady(m, op)
            over = [x for x in worst(m, T, op) if x[0] < 0]
            res[(Ta, tag)] = (over, op['fc'].get('vtx_on', 1.0), {k: m.temp(T, k) for k in ('FC U_FC', 'FC U_IMU')})
            # the FC's input over the thermostat's cycle (the video's share of it)
            rows.append(['%.0f C' % Ta, tag, '%.1f W' % losses.fc_power(op['fc']['i5'], op['fc']['i9'])[0]] +
                        (['%.0f %%' % (100 * op['fc'].get('vtx_on', 1.0))] if data.THERMOSTAT else []) +
                        ['%.0f C' % m.temp(T, 'FC U_BUCK9'), '%.0f C' % m.temp(T, 'FC U_IMU'),
                         '%.0f C' % m.temp(T, 'FC U_FC'), '%.0f C' % m.temp(T, 'FC J_ESC'), '%.0f C' % m.temp(T, 'FC J_HD'),
                         '%d; worst %s' % (len(over), ', '.join('%s %.0f C (%.0f)' % (x[1], x[2], x[3]) for x in over[:3]))
                         if over else 'none'])
    table(['Air', 'FC load', 'FC input'] + (['Video on'] if data.THERMOSTAT else []) +
          ['9 V buck', 'Gyro', 'Processor', 'Stack connector', 'HD connector', 'Parts past their rating (rating)'], rows)
    found['ground'] = res
    rows = []
    for Ta in ((HOT,) if QUICK else (25.0, HOT)):
        for tag, fc in (('9 V at 1.5 A, 5 V at 1 A', dict(i5=1.0, i9=1.5)), ('9 V at 1 A, 5 V at 0.5 A', dict(i5=0.5, i9=1.0))):
            m = model(0.0, Ta)
            fcaps = [x for x in m.parts if x.startswith('FC') and m.parts[x].get('kind')]
            low = min(data.CAPS[m.parts[x]['kind']][1] for x in fcaps)
            groups = {'gyro': ['FC U_IMU'], 'processor': ['FC U_FC'], 'buck': ['FC U_BUCK9'],
                      'caps': [x for x in fcaps if data.CAPS[m.parts[x]['kind']][1] == low],
                      'connector': [x for x in ('FC J_ESC', 'ESC J_FC') if x in m.parts], 'hd': ['FC J_HD']}
            T, tr, first = run_transient(m, [(60.0 if QUICK else 600.0, 0.0)], sw, np.full(m.n, Ta), 5.0, fc, V,
                                         am32=False, watch=groups)
            t = np.array(tr['t'])
            when = lambda key, lim: ('%.1f min' % (t[np.argmax(np.array(tr[key]) >= lim)] / 60)
                                     if (np.array(tr[key]) >= lim).any() else '> %.0f min' % (t[-1] / 60))
            off = np.array(tr['vtx']) == False
            rows.append(['%.0f C' % Ta, tag, when('caps', low), when('connector', data.STACK_CONN['t_max']),
                         when('hd', data.HD_CONN['t_max']), when('gyro', data.GYRO['t_max']),
                         when('processor', data.MCU_FC['tj_max'])] +
                        (['%.1f min' % (t[np.argmax(off)] / 60) if off.any() else 'never'] if data.THERMOSTAT else []))
    table(['Air', 'FC load', 'An FC capacitor reaches its %.0f C' % low,
           'The stack connector reaches %.0f C' % data.STACK_CONN['t_max'],
           'The HD connector reaches %.0f C' % data.HD_CONN['t_max'],
           'The gyro reaches %.0f C' % data.GYRO['t_max'], 'The processor reaches %.0f C' % data.MCU_FC['tj_max']] +
          (['The thermostat cuts the video'] if data.THERMOSTAT else []), rows)


# =================================================================== figures
def plot_flight(tr, groups, m):
    if not PLOTS:
        return
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    t = np.array(tr['t'])
    colors = plt.cm.tab20(np.arange(len(groups)) * 2 % 20 / 20 + (np.arange(len(groups)) * 2 >= 20) * 0.05)
    for (label, names), col in zip(groups.items(), colors):
        lim, what = limit_of(names[0], m)
        ax[0].plot(t, tr[label], label='%s (rating %s C)' % (label, '%.0f' % lim if lim else '-'), lw=1.2, color=col)
    ax[0].axhline(85, color='k', ls=':', lw=1)
    ax[0].axhline(105, color='k', ls='--', lw=1)
    ax[0].axhline(175, color='r', ls='--', lw=1)
    ax[0].set_ylabel('C'); ax[0].grid(alpha=.3); ax[0].legend(fontsize=7, ncol=2)
    ax[0].set_title('Hard flight, %.0f C air, 5 m/s over the stack (dotted 85 C, dashed 105 C, red 175 C)' % HOT)
    ax[1].plot(t, tr['throttle'], color='k', lw=1, label='pilot')
    ax[1].plot(t, tr['applied'], color='r', lw=1, label='the most-cut motor')
    cut = np.array(tr['cut'])
    if cut.any():
        ax[1].fill_between(t, 0, 100, where=cut, color='r', alpha=.12, label='AM32 temperature cut')
    ax[1].legend(fontsize=7)
    ax[1].set_ylabel('throttle %'); ax[1].set_xlabel('s'); ax[1].grid(alpha=.3)
    fig.tight_layout()
    os.makedirs(IMG, exist_ok=True)
    fig.savefig(os.path.join(IMG, 'hot-flight.png'), dpi=110)
    plt.close(fig)
    say('![Hot flight](images/stress/hot-flight.png)')
    say()


def plot_maps(m, T, name):
    if not PLOTS:
        return
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 4, figsize=(16, 4.4))
    views = [(m.ge, 0, 0, 'ESC top'), (m.ge, 0, 5, 'ESC bottom'), (m.gf, 1, 5, 'FC bottom'), (m.gf, 1, 0, 'FC top')]
    vmax = max(T[:m.st.off[2]].max(), 60)
    for a, (g, bi, li, title) in zip(ax, views):
        img = np.full((g.ny, g.nx), np.nan)
        ids = g.ids[li]
        img[ids >= 0] = T[m.st.off[bi] + ids[ids >= 0]]
        im = a.imshow(img, cmap='inferno', vmin=m.T_amb, vmax=vmax)
        a.set_title('%s, max %.0f C' % (title, np.nanmax(img))); a.axis('off')
    fig.colorbar(im, ax=ax, fraction=0.02, label='C')
    fig.savefig(os.path.join(IMG, name + '-maps.png'), dpi=100, bbox_inches='tight')
    plt.close(fig)
    say('![Temperatures at the end](images/stress/%s-maps.png)' % name)
    say()


def plot_copper(u):
    if not PLOTS:
        return
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    c = copper.extract('esc')
    W = copperloss.loss_map(u, {n: 20.0 for n in CH}, {n: 0.95 for n in CH})
    fig, ax = plt.subplots(1, 6, figsize=(18, 3.6))
    area = (c.res) ** 2
    vmax = np.percentile(W[W > 0] / area, 99.5)
    for li, a in enumerate(ax):
        img = np.where(c.owner[li] >= 0, W[li] / area, np.nan)
        im = a.imshow(img, cmap='magma', vmin=0, vmax=vmax)
        a.set_title('%s, %.1f W' % (c.layers[li], W[li].sum())); a.axis('off')
    fig.colorbar(im, ax=ax, fraction=0.015, label='W/mm2')
    os.makedirs(IMG, exist_ok=True)
    fig.savefig(os.path.join(IMG, 'esc-copper-loss.png'), dpi=100, bbox_inches='tight')
    plt.close(fig)
    say('![Where the copper heats, 20 A on every motor](images/stress/esc-copper-loss.png)')
    say()


# =================================================================== report
def summary(r2, r1):
    out = ['# Ridge 3 stack: stress simulations', '',
           'Generated by `sim/stress.py` on %s.  The FC on the ESC, a full 6S pack '
           '(25.2 V), hot air (%.0f C is the design\'s hot day), full current.  Rev 2, '
           'the design in this repository, is reported in full; rev 1 (commit %s) '
           'is run through the same simulations for the comparison below.' % (
               time.strftime('%Y-%m-%d'), HOT, design.REV1_COMMIT), '',
           '**What this is not:** a measurement.  These are simulations of the '
           'design files, with the makers\' datasheet figures (`sim/data.py`, each '
           'with its source) and a few stated assumptions.  They say where the '
           'design runs out of margin and roughly by how much.  Bring-up on the '
           'bench is still the test.', '', '## Verdict (rev 2)', '']
    out.append('| Area | Check | Result | Simulated | Limit |')
    out.append('|---|---|---|---|---|')
    order = {'FAIL': 0, 'MARGINAL': 1, 'PASS': 2}
    for a, c, r, n, l in sorted(r2['verdicts'], key=lambda v: order.get(v[2], 3)):
        out.append('| %s | %s | **%s** | %s | %s |' % (a, c, r, n, l) if r != 'PASS' else '| %s | %s | %s | %s | %s |' % (a, c, r, n, l))
    out.append('')
    return out


def compare_section(r1, r2):
    """Rev 2 against rev 1, the same runs."""
    f1, f2 = r1['found'], r2['found']
    out = ['## Rev 2 against rev 1', '',
           'The same simulations on both designs: rev 1\'s boards and circuit from '
           'git (commit %s), rev 2 from the working tree.' % design.REV1_COMMIT, '']
    rows = []
    def row(what, a, b, unit_fmt, better='lower'):
        if a is None or b is None:
            rows.append([what, '-' if a is None else unit_fmt % a, '-' if b is None else unit_fmt % b, ''])
            return
        rows.append([what, unit_fmt % a, unit_fmt % b, ''])
    hold = lambda f, k, i: f.get('hold', {}).get(k, (None,) * 5)[i]
    for (Ta, v) in ((HOT, 5.0), (60.0, 5.0), (HOT, 2.0)):
        row('Throttle held indefinitely with every part in its rating, %.0f C air, %.0f m/s' % (Ta, v),
            hold(f1, (v, Ta), 0), hold(f2, (v, Ta), 0), '%.0f %%')
        row('Throttle held indefinitely with the FETs under 150 C, %.0f C air, %.0f m/s' % (Ta, v),
            hold(f1, (v, Ta), 1), hold(f2, (v, Ta), 1), '%.0f %%')
    b1 = f1.get('bursts', {}).get((HOT, 5.0), (None, None))[0]
    b2 = f2.get('bursts', {}).get((HOT, 5.0), (None, None))[0]
    rows.append(['Full-throttle burst from hover, %.0f C, 5 m/s: a FET reaches 175 C after' % HOT,
                 '%.1f s' % b1 if b1 is not None else 'never (10 s)', '%.1f s' % b2 if b2 is not None else 'never (10 s)', ''])
    fl1, fl2 = f1.get('flight', {}), f2.get('flight', {})
    row('Hard 3-minute flight, %.0f C: hottest FET' % HOT, fl1.get('fet'), fl2.get('fet'), '%.0f C')
    row('Hard 3-minute flight, %.0f C: hottest ESC processor' % HOT, fl1.get('mcu'), fl2.get('mcu'), '%.0f C')
    row('Hard 3-minute flight, %.0f C: share of the flight AM32 cut a motor for heat' % HOT,
        100 * fl1.get('frac', 0), 100 * fl2.get('frac', 0), '%.0f %%')
    for label in ('FC processor', 'FC gyro', 'FC 9 V buck', 'FC 5 V buck', 'FC stack connector'):
        a, b = fl1.get('peaks', {}).get(label), fl2.get('peaks', {}).get(label)
        if a is not None or b is not None:
            row('Hard flight, %.0f C: %s' % (HOT, label), a, b, '%.0f C')
    rows.append(['Hard flight, %.0f C: first part past its rating' % HOT,
                 '%s at %.0f s' % (fl1['first'][0], fl1['first'][1][0]) if fl1.get('first') else 'none',
                 '%s at %.0f s' % (fl2['first'][0], fl2['first'][1][0]) if fl2.get('first') else 'none', ''])
    g = lambda f: f.get('ground', {}).get((HOT, '9 V at 1.5 A, 5 V at 1 A'))
    g1, g2 = g(f1), g(f2)
    if g1 and g2:
        rows.append(['On the ground, %.0f C still air, HD video (9 V 1.5 A, 5 V 1 A): parts past their rating' % HOT,
                     str(len(g1[0])), '%d (video on %.0f %% of the time)' % (len(g2[0]), 100 * g2[1]), ''])
        row('Same: FC processor', g1[2]['FC U_FC'], g2[2]['FC U_FC'], '%.0f C')
    row('ESC heat while hovering, %.0f C' % HOT, f1.get('hover_heat', (None,))[0], f2.get('hover_heat', (None,))[0], '%.1f W')
    row('Sense-node copper, low-side FET to shunt (mean)', f1.get('r_src', 0) * 1e3, f2.get('r_src', 0) * 1e3, '%.2f mOhm')
    row('Battery planes, VBAT + GND', f1.get('r_planes', 0) * 1e3, f2.get('r_planes', 0) * 1e3, '%.2f mOhm')
    rows.append(['FET voltage rating', '%.0f V' % r1['vdss'], '%.0f V' % r2['vdss'], ''])
    row('High-side FET at turn-off, 30 A, 5 nH', f1.get('hs_peak'), f2.get('hs_peak'), '%.1f V')
    row('Low-side FET after the high side turns on (worst case)', f1.get('ls_peak'), f2.get('ls_peak'), '%.1f V')
    row('Plugging in a full 6S pack, leads up to 300 nH', f1.get('plug'), f2.get('plug'), '%.1f V')
    row('Stack lead current, FC at full load, empty 6S', f1.get('lead'), f2.get('lead'), '%.2f A')
    rows.append(['Stack lead contact rating', '%.1f A, %.0f C' % (r1['conn'][0], r1['conn'][1]),
                 '%.1f A, %.0f C' % (r2['conn'][0], r2['conn'][1]), ''])
    row('Ground-loop current in the lead, FC battery pads also wired, 20 A per motor',
        f1.get('loop'), f2.get('loop'), '%.1f A')
    row('Largest ESC processor ground offset against the lead\'s ground, 30 A per motor',
        f1.get('dshot_offset', 0) * 1e3, f2.get('dshot_offset', 0) * 1e3, '%.0f mV')
    out.append('| | Rev 1 | Rev 2 | |')
    out.append('|---|---|---|---|')
    for r in rows:
        out.append('| %s | %s | %s | %s |' % tuple(r))
    out.append('')
    n1 = {k: sum(1 for v in r1['verdicts'] if v[2] == k) for k in ('PASS', 'MARGINAL', 'FAIL')}
    n2 = {k: sum(1 for v in r2['verdicts'] if v[2] == k) for k in ('PASS', 'MARGINAL', 'FAIL')}
    out.append('Verdicts: rev 1 %(PASS)d pass, %(MARGINAL)d marginal, %(FAIL)d fail' % n1 +
               '; rev 2 %(PASS)d pass, %(MARGINAL)d marginal, %(FAIL)d fail.' % n2)
    out.append('')
    return out


def run_design(name, full):
    """Every section for one design; returns its report lines, verdicts and
    the numbers the comparison reads."""
    global PLOTS, HOVER
    data.use(name)
    lines.clear(); verdicts.clear(); found.clear(); _models.clear(); last_burst.clear()
    dcflow.forget()
    PLOTS = full
    HOVER = round(losses.hover(data.BATTERY['vfull']), 1)
    log('==== design', name)
    fet_check()
    esc_ops = [('4 x 10 A, 70 %% duty', 10.0, 0.7), ('4 x 20 A, 95 %% duty', 20.0, 0.95),
               ('4 x 30 A, 97 %% duty', 30.0, 0.97)]
    u = copper_section([(a.replace('%%', '%'), b, c) for a, b, c in esc_ops])
    plot_copper(u)
    sw = switching_section()
    bus_section()
    lead_section()
    dcflow.forget()
    fcmax = data.FC_LOAD_MAX
    results = heat_section(sw)
    bursts_section(sw, fcmax)
    first, tr = flight_section(sw, fcmax)
    ground_section(sw)
    heat_verdicts(results, first)
    out = dict(lines=list(lines), verdicts=list(verdicts), found=dict(found), vdss=data.FET['vdss'],
               conn=(data.STACK_CONN['i_rated'], data.STACK_CONN['t_max']))
    _models.clear()
    dcflow.forget()
    return out


def main():
    t0 = time.time()
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    r1 = run_design('rev1', full=False)
    r2 = run_design('rev2', full=True)
    lines.clear()
    lines.extend(r2['lines'])
    verdicts.clear()
    verdicts.extend(r2['verdicts'])
    found.clear()
    found.update(r2['found'])
    fixes_section()
    limits_section()
    text = '\n'.join(summary(r2, r1) + compare_section(r1, r2) + lines)
    text += '\n---\nRun time %.0f min.\n' % ((time.time() - t0) / 60)
    open(REPORT, 'w').write(text)
    log('wrote', REPORT)


def fixes_section():
    say('## What is still tight')
    say()
    bad = [v for v in verdicts if v[2] != 'PASS']
    if bad:
        say('The checks rev 2 does not pass outright:')
        say()
        for a, c, r, n, l in sorted(bad, key=lambda v: v[2]):
            say('- **%s** (%s): %s; %s, against %s.' % (c, a.lower(), r.lower(), n, l))
        say()
    else:
        say('Every check above passes.')
        say()
    total, cat = found.get('hover_heat', (0, {}))
    if total:
        top = sorted(cat.items(), key=lambda kv: -kv[1])[:3]
        say('Where the ESC\'s heat goes while hovering on a %.0f C day (%.1f W in all): %s.' % (
            HOT, total, ', '.join('%s %.0f %%' % (k, 100 * w / total) for k, w in top)))
        say()


def limits_section():
    say('## What these simulations leave out')
    say()
    for t in (
        'Anything measured.  Every number here is a model of the design files '
        'with the makers\' datasheet figures; the few assumptions are marked in '
        '`sim/data.py` and named where they matter.',
        'The motor, prop and battery are typical parts (a 1507 3100 KV motor on '
        'a 3-inch tri-blade, from its maker\'s thrust table; a 6S pack whose '
        'resistance no maker publishes).  Another motor changes the currents.',
        'Air: the convection over the stack comes from flat-plate correlations '
        'at an assumed air speed, and the gap between the boards from an '
        'assumed 5 mm.  A frame\'s top plate, a VTX above the FC or a camera '
        'in front change it; the air-speed rows show how much it matters.',
        'Heat carried away (or brought in) by the motor wires, the battery '
        'leads, the screws and the grommets, and heat from the VTX itself.',
        'The loop inductance of each half-bridge is estimated from the layout, '
        'not field-solved; the edge results are shown for 3-8 nH.',
        'AC effects in the copper: the switching-frequency part of the battery '
        'current is solved as DC (it has no skin effect at 48 kHz in 35 um '
        'copper, but it may take a slightly different path).',
        'EMI, ESD and radio interference; vibration; solder-joint fatigue from '
        'the heat cycles; the long-term effect of running parts near their '
        'limits.',
        'Firmware behaviour beyond AM32\'s current limit and temperature limit '
        'as the README describes them.'):
        say('- ' + t)
    say()


def heat_verdicts(results, first):
    for (v, Ta), (th, op, T, th2, op2) in sorted(results.items()):
        if v == 5.0:
            verdict('Heat', 'Hover (%.0f %% throttle) held indefinitely with every part in its rating, %.0f C air, 5 m/s' % (HOVER, Ta),
                    th >= HOVER, 'up to %.0f %% throttle' % th, '%.0f %%' % HOVER)
            verdict('Heat', 'Hover held indefinitely with the FETs under 150 C, %.0f C air, 5 m/s' % Ta,
                    th2 >= HOVER, 'up to %.0f %% throttle' % th2, '%.0f %%' % HOVER)
    for (Ta, v), (t175, tcut) in sorted(found.get('bursts', {}).items()):
        if v == 5.0 and Ta in (25.0, HOT):
            verdict('Heat', 'Full-throttle burst from hover (AM32 at 20 A per motor), %.0f C air, 5 m/s' % Ta,
                    t175 is None, 'a FET reaches 175 C after %.1f s; AM32\'s cut after %s' % (
                        t175, '%.1f s' % tcut if tcut is not None else '> 10 s') if t175 is not None else 'no FET reaches 175 C in 10 s',
                    '175 C')
    f = found.get('flight', {})
    verdict('Heat', 'Hard 3-minute flight at %.0f C: AM32 cuts a motor\'s power for heat' % HOT,
            f.get('cut') is None, 'first at %.0f s, %.0f %% of the flight' % (f['cut'], 100 * f['frac'])
            if f.get('cut') is not None else 'never', 'never')
    verdict('Heat', 'Hard 3-minute flight at %.0f C: hottest FET' % HOT, f.get('fet', 0) < 150 or
            ('MARGINAL' if f.get('fet', 0) < data.FET['tch_max'] else False),
            '%.0f C' % f.get('fet', 0), '175 C (150 C design)')
    verdict('Heat', 'Hard 3-minute flight at %.0f C: ESC processors' % HOT, f.get('mcu', 0) <= data.MCU_ESC['tj_max'],
            '%.0f C' % f.get('mcu', 0), '%.0f C junction (%s)' % (data.MCU_ESC['tj_max'], data.MCU_ESC['part']))
    if f.get('first'):
        k, (t, temp, lim, what) = f['first']
        verdict('Heat', 'Hard 3-minute flight at %.0f C: first part past its rating' % HOT, False,
                '%s (%s) at %.0f s' % (k, what, t), '%.0f C' % lim)
    for (Ta, tag), (over, on, _) in sorted(found.get('ground', {}).items()):
        if tag.startswith('9 V at 1.5 A'):
            verdict('Heat', 'On the ground, video on (%s), %.0f C still air' % (tag, Ta), not over,
                    ('%d parts past their rating' % len(over) if over else 'all inside') +
                    (', video on %.0f %% of the time (thermostat)' % (100 * on) if on < 1 else ''), '-')


if __name__ == '__main__':
    main()
