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
import copper, dcflow, copperloss, thermal, spice, losses, data, stack

QUICK = '--quick' in sys.argv
OUT = os.path.join(HERE, 'out')
IMG = os.path.join(OUT, 'quick') if QUICK else os.path.join(RIDGE, 'images', 'stress')
REPORT = os.path.join(OUT, 'quick', 'STRESS.md') if QUICK else os.path.join(RIDGE, 'STRESS.md')
CH = (1, 2, 3, 4)
PH = 'ABC'

lines = []
verdicts = []          # (area, check, result, number, limit)
found = {}             # numbers the closing section refers back to


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
    ciss, crss, coss = spice.capacitances()
    Ts = [25, 50, 75, 100, 125, 150, 175]
    R = [spice.rds_on(T) for T in Ts]
    qg, qgd = spice.gate_charge()
    q0, i0, t0 = spice.recovery_charge()
    q1, i1, t1 = spice.recovery_charge(lm=data.BODY_DIODE)
    F = data.FET
    say('## 1. The FET model against its datasheet')
    say()
    say('Toshiba publishes a SPICE model of the TPN2R304PL (the "G0" grade, a '
        'BSIM3 model fitted to the on-state curves).  Before trusting its '
        'switching, each figure the datasheet gives was simulated in the '
        'datasheet\'s own test circuit:')
    say()
    table(['Quantity', 'Datasheet (typ)', 'Model', 'Test'], [
        ['R<sub>DS(on)</sub> at 25 C', '%.1f mOhm (max %.1f)' % (F['rds25_typ'] * 1e3, F['rds25_max'] * 1e3), '%.2f mOhm' % (R[0] * 1e3), 'V<sub>GS</sub> 10 V, 40 A'],
        ['R<sub>DS(on)</sub> at 125 C', '-', '%.2f mOhm (x%.2f)' % (R[4] * 1e3, R[4] / R[0]), 'same'],
        ['C<sub>iss</sub>', '%d pF' % (F['ciss'] * 1e12), '%d pF' % (ciss * 1e12), 'V<sub>DS</sub> 20 V, 1 MHz'],
        ['C<sub>rss</sub>', '%d pF' % (F['crss'] * 1e12), '%d pF' % (crss * 1e12), 'same'],
        ['C<sub>oss</sub>', '%d pF' % (F['coss'] * 1e12), '%d pF' % (coss * 1e12), 'same'],
        ['Q<sub>g</sub> to 10 V', '%.0f nC' % (F['qg'] * 1e9), '%.1f nC' % (qg * 1e9), '20 V, 40 A'],
        ['Q<sub>gd</sub>', '%.1f nC' % (F['qgd'] * 1e9), '%.1f nC' % (qgd * 1e9), 'same'],
        ['Reverse recovery (Q<sub>rr</sub> + Q<sub>oss</sub>)', '%.0f + %.0f nC, t<sub>rr</sub> %.0f ns' % (F['qrr'] * 1e9, F['qoss'] * 1e9, F['trr'] * 1e9),
         'as supplied: %.0f nC, %.0f ns; with the recovery diode below: %.0f nC, %.0f ns' % (q0 * 1e9, t0 * 1e9, q1 * 1e9, t1 * 1e9),
         'I<sub>F</sub> 20 A, 100 A/us, 20 V'],
    ])
    say('The on-resistance, capacitances and gate charge match.  Toshiba\'s body '
        'diode is SPICE\'s basic one, which stores more charge than the datasheet '
        'shows and lets it go all at once (the hardest possible recovery).  The '
        'switching runs below therefore use a charge-control diode (Lauritzen and '
        'Ma) fitted to the datasheet\'s recovery test (lifetime %.0f ns, transit '
        'time %.0f ns), with Toshiba\'s junction capacitance and 40 V breakdown '
        'kept; the diode as supplied is run too, as the worst case.' % (
            data.BODY_DIODE[0] * 1e9, data.BODY_DIODE[1] * 1e9))
    say()
    return dict(T=Ts, R=R)


# =================================================================== 2. copper
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
    say('The battery planes, shared by the four channels, add %.2f mOhm (VBAT, In4) '
        'and %.2f mOhm (GND, In1) for the total battery current.' % (P['VBAT']['R'] * 1e3, P['GND']['R'] * 1e3))
    say()
    # the via each low-side FET's current funnels through
    worst = []
    for n in CH:
        for y in PH:
            s = dcflow.solve(c, 'M%d_SRC' % n, {'Q%d%sL' % (n, y): 1.0, 'R_SH%d' % n: -1.0}, T=20.0)
            bc = max(dcflow.barrel_currents(c, s), key=lambda x: x[1])
            worst.append((bc[1], n, y, c.holes[bc[0]]))
    frac, n, y, h = max(worst, key=lambda x: x[0])
    say('**Where the sense-node resistance comes from.**  On the bottom layer the '
        'sense-node pour under each channel\'s low-side FETs is cut into islands '
        'by the bridge capacitors\' battery pads and the low-side gate lines; each '
        'island reaches the inner-layer (In3) strip that runs to the shunt only '
        'through vias.  The worst: %.0f %% of FET Q%d%sL\'s current goes through '
        'one %.2f mm via at (%+.1f, %+.1f) mm from the board centre, so at 20 A '
        'per motor that via carries %.0f A.' % (100 * frac, n, y, h['d'], h['x'] - (c.x0 + c.nx * c.res / 2), h['y'] - (c.y0 + c.ny * c.res / 2), 20 * frac))
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
    say('One phase leg of the ESC switching the motor current, simulated through '
        'both edges: the low side turns off, dead time (AM32\'s %.0f ns plus the '
        'DRV8300\'s %.0f ns), the high side turns on and the low side\'s body '
        'diode recovers, then the high side turns off.  Battery %.1f V (6S full), '
        'the DRV8300 as its typical peak currents (%.2f A source, %.2f A sink) '
        'behind the %.0f ohm gate resistors, the bridge capacitor at its DC-bias '
        'value, the pack %.0f mOhm behind %.0f nH of leads with the %.0f uF '
        'external capacitor at the pads.' % (
            data.AM32['dead'] * 1e9, data.DRV8300['dead'][1] * 1e9, B['V'],
            data.DRV8300['i_source'][1], data.DRV8300['i_sink'][1], B['Rg'],
            B['Rbat'] * 1e3, B['Llead'] * 1e9, B['Cext'] * 1e6))
    say()
    say('The commutation loop\'s inductance (bridge capacitor, high-side FET, '
        'phase vias, low-side FET, sense-node copper, back to the capacitor) is '
        'estimated from the layout: the high-side FET on top and the low-side FET '
        '2.4 mm along on the bottom, with the capacitor 1.7 mm the other way, '
        'make a loop about 5 mm long through the 1.6 mm board, 3.3 mm wide: '
        'mu0 x 5 x 1.6 / 3.3 = 3 nH, plus the two FET packages and the '
        'capacitor\'s own inductance, about 5 nH.  That is an estimate, not a '
        'field solution, so 3 and 8 nH are run too.')
    say()
    rows = []
    res = {}
    for diode, lm, tt in (('recovery fit', data.BODY_DIODE, None), ('as supplied', None, None)):
        for T in ((150,) if QUICK else (25, 150)):
            for I in (10, 20, 30):
                for L in ((5e-9,) if QUICK else (3e-9, 5e-9, 8e-9)):
                    if diode == 'as supplied' and (L != 5e-9 or T != 150):
                        continue
                    r = spice.half_bridge(hb_params(I=I, T=T, Lloop=L, lm=lm, tag='sw'))
                    res[(diode, T, I, L)] = r
                    rows.append([diode, T, I, '%.0f' % (L * 1e9), '%.1f' % r['vds_hs_peak'],
                                 '%.1f' % r['vds_ls_peak'], '%.1f' % r['sh_min'],
                                 '%.1f / %.1f' % (r['slew_rise'], r['slew_fall']),
                                 '%.2f' % r['vgs_ls_miller'], '%.0f' % r['irr'],
                                 '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6)])
    # the same edges while a throttle chop has lifted the bus (section 4)
    for Vb in (31.3, 35.3):
        r = spice.half_bridge(hb_params(V=Vb, I=20.0, T=150, Lloop=5e-9, lm=data.BODY_DIODE, tag='regen'))
        res[('bus %.1f V' % Vb, 150, 20, 5e-9)] = r
        rows.append(['recovery fit, bus at %.1f V (throttle chop)' % Vb, 150, 20, '5', '%.1f' % r['vds_hs_peak'],
                     '%.1f' % r['vds_ls_peak'], '%.1f' % r['sh_min'],
                     '%.1f / %.1f' % (r['slew_rise'], r['slew_fall']),
                     '%.2f' % r['vgs_ls_miller'], '%.0f' % r['irr'],
                     '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6)])
    table(['Body diode', 'T<sub>j</sub> C', 'I A', 'Loop nH', 'Peak V<sub>DS</sub> high side (turn-off)',
           'Peak V<sub>DS</sub> low side (turn-on)', 'SHx min V', 'SHx slew up / down V/ns',
           'Off gate V<sub>GS</sub> peak V', 'Recovery A', 'E<sub>on</sub> / E<sub>off</sub> uJ'], rows)
    hs = max(v['vds_hs_peak'] for k, v in res.items() if k[0] == 'recovery fit' and k[3] == 5e-9)
    ls = min(v['vds_ls_peak'] for k, v in res.items() if k[0] == 'recovery fit')
    verdict('Voltage', 'High-side FET at turn-off, 30 A, 5 nH loop', hs < 0.9 * data.FET['vdss'] or
            ('MARGINAL' if hs < data.FET['vdss'] else False), '%.1f V' % hs, '40 V rating')
    verdict('Voltage', 'Low-side FET after the high side turns on (body-diode recovery)',
            False if ls >= data.FET['vdss'] - 0.5 else True, '%.1f V (every case)' % ls,
            '40 V rating')
    slew = max(v['slew_rise'] for k, v in res.items() if k[0] == 'recovery fit')
    verdict('Voltage', 'Switch-node slew (DRV8300D recommends <= 2 V/ns)', slew <= 2.0 or 'MARGINAL',
            '%.1f V/ns' % slew, '2 V/ns')
    shm = min(v['sh_min'] for v in res.values())
    verdict('Voltage', 'SHx below ground at high-side turn-off', shm > -22,
            '%.1f V' % shm, '-22 V for 2 us (DRV8300)')
    mil = max(v['vgs_ls_miller'] for k, v in res.items() if k[1] == 150 and k[0] == 'recovery fit')
    chop = max(v['vds_hs_peak'] for k, v in res.items() if k[0].startswith('bus'))
    verdict('Voltage', 'High-side FET at turn-off, 20 A, while a throttle chop holds the bus at 31-35 V',
            chop < 0.9 * data.FET['vdss'] or ('MARGINAL' if chop < data.FET['vdss'] - 0.5 else False),
            '%.1f V' % chop, '40 V rating')
    verdict('Voltage', 'Off FET\'s gate kicked up by the other FET turning on (hot)',
            'MARGINAL' if mil > data.FET['vth_min_hot'] else True,
            '%.2f V' % mil, 'V<sub>th</sub> min %.1f V at 25 C, about %.1f V at 150 C' % (
                data.FET['vth_min'], data.FET['vth_min_hot']))
    # what brings the ringing down
    rows = []
    for tag, kw in (('as designed', {}), ('gate resistors 22 ohm', dict(Rg=22)), ('gate resistors 47 ohm', dict(Rg=47)),
                    ('RC snubber 2.2 ohm + 2.2 nF per FET', dict(snub=(2.2, 2.2e-9))),
                    ('RC snubber 1 ohm + 4.7 nF per FET', dict(snub=(1.0, 4.7e-9))),
                    ('RC snubber 1 ohm + 10 nF per FET', dict(snub=(1.0, 10e-9)))):
        for I in (10, 30):
            r = spice.half_bridge(hb_params(I=I, T=150, Lloop=5e-9, lm=data.BODY_DIODE, tag='fix', **kw))
            extra = 0.0
            if 'snub' in kw:
                extra = 2 * kw['snub'][1] * data.BRIDGE['V'] ** 2 * data.AM32['f_max']   # per switched leg
            rows.append([tag, I, '%.1f' % r['vds_hs_peak'], '%.1f' % r['vds_ls_peak'],
                         '%.1f / %.1f' % (r['e_on'] * 1e6, r['e_off'] * 1e6),
                         '%.2f W' % extra if extra else '-'])
    say('What brings the low side\'s peak down (T<sub>j</sub> 150 C, 5 nH, the recovery-fit diode):')
    say()
    table(['Change', 'I A', 'High side V', 'Low side V', 'E<sub>on</sub> / E<sub>off</sub> uJ', 'Snubber loss per switched leg at 48 kHz'], rows)
    sw = {'V': data.BRIDGE['V'], 'I': [0.0], 'on': [0.0], 'off': [0.0]}
    for I in (10, 20, 30):
        r = res[('recovery fit', 150, I, 5e-9)]
        sw['I'].append(I); sw['on'].append(r['e_on']); sw['off'].append(r['e_off'])
    # beyond 30 A, extrapolate linearly
    sw['I'].append(60); sw['on'].append(2 * sw['on'][-1]); sw['off'].append(2 * sw['off'][-1])
    found['hs_peak'] = hs
    found['sw'] = sw
    plot_edges(res)
    return sw


def plot_edges(res):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    r = res[('recovery fit', 150, 30, 5e-9)]
    w = r['wave']; t = w['time'] * 1e9
    e = [x * 1e9 for x in r['edges']]
    fig, ax = plt.subplots(2, 2, figsize=(12, 7), sharey='row')
    for col, (t0, title) in enumerate(((e[1], 'High side turns on'), (e[2], 'High side turns off'))):
        m = (t > t0 - 20) & (t < t0 + 150)
        a = ax[0, col]
        a.plot(t[m] - t0, (w['v(dH)'] - w['v(sH)'])[m], label='high-side V_DS')
        a.plot(t[m] - t0, (w['v(dL0)'] - w['v(sL)'])[m], label='low-side V_DS')
        a.axhline(40, color='r', ls='--', lw=1, label='40 V rating')
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
    say('The pack (%.1f V, %.0f mOhm) through %.0f nH of leads to the ESC\'s '
        'pads, the external capacitor there (%s), the ESC\'s bridge capacitors '
        '(%d x %s at %.1f uF each under 25 V bias) and, through the stack lead '
        '(%.0f nH, %.0f mOhm), the FC\'s input: its TVS (SMF33A, breaking down '
        'at %.1f V, the middle of its 36.7-40.6 V range) and ceramics.' % (
            Bs['Vpack'], Bs['Rbat'] * 1e3, Bs['Llead'] * 1e9, data.EXT_CAP['desc'],
            12, data.C_BRIDGE['part'], data.C_BRIDGE['c_bias'] * 1e6,
            Bs['Lstack'] * 1e9, Bs['Rstack'] * 1e3, Bs['tvs_bv']))
    say()
    base = dict(Bs, Cext=data.EXT_CAP['c'], ESRext=data.EXT_CAP['esr'], ESLext=data.EXT_CAP['esl'])
    ifc = losses.fc_power(**data.FC_LOAD_MAX)[0] / Bs['Vpack']
    noext = dict(base, Cext=0)
    rows = []
    worst_plug = {}
    for tag, p in (('with the external capacitor', base), ('without it', noext)):
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
        for ctag, p in (('with the external capacitor', base), ('without it', noext)):
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
        for ctag, p in (('with the external capacitor', base), ('without it', noext)):
            iesc = [(0, 80.0), (1e-3, 80.0), (1.2e-3, data.REGEN['i_bus']), (6e-3, data.REGEN['i_bus']), (8e-3, 0.0)]
            w = spice.bus(dict(p, Rbat=Rb, plug=False, Ifc=ifc, iesc=iesc, step=50e-9,
                               maxstep=200e-9, tend=9e-3), 'chop')
            rows.append(['Throttle chop, %.0f A back into a %.0f mOhm pack, %s' % (-data.REGEN['i_bus'], Rb * 1e3, ctag),
                         '%.0f nH' % (Bs['Llead'] * 1e9), '%.1f V' % w['v(vb)'].max(), '%.1f V' % w['v(fc)'].max(),
                         '%.2f A' % w['i(vtv)'].max()])
    table(['Event', 'Leads', 'Peak at the FETs', 'Peak at the FC', 'TVS / capacitor current'], rows)
    vmax = max(v for (tag, L), v in worst_plug.items() if tag == 'without it')
    vwith = max(v for (tag, L), v in worst_plug.items() if tag != 'without it')
    grade = lambda v: True if v < 0.9 * data.FET['vdss'] else ('MARGINAL' if v < data.FET['vdss'] else False)
    verdict('Voltage', 'Plugging in a full 6S pack, external capacitor fitted, leads up to 300 nH',
            grade(vwith), '%.1f V' % vwith, '40 V FETs')
    verdict('Voltage', 'Plugging in a full 6S pack, external capacitor left off, leads up to 300 nH',
            grade(vmax), '%.1f V' % vmax, '40 V FETs')
    ripple = max(float(r[4].split('cap ')[1].split(' A')[0]) for r in rows if r[4].startswith('cap '))
    found['ripple'] = ripple
    verdict('Voltage', 'Ripple current in the external capacitors, 4 x 30 A',
            ripple <= data.EXT_CAP['ripple'], '%.1f A rms' % ripple,
            '%.2f A rms (2 x FR-A 100 uF, 100 kHz, 105 C)' % data.EXT_CAP['ripple'])
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
    J = data.JST_SH
    say('## 5. The stack lead, and the FC\'s supply')
    say()
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
        pin, _ = losses.fc_power(i5, i9)
        cells = []
        for V in (25.2, 21.0, 19.8):
            i = pin / V
            cells.append('%.2f A%s' % (i, ' **over**' if i > J['i_rated'] else ''))
        rows.append([tag, '%.1f W' % pin] + cells)
    table(['FC load', 'FC input', 'Lead current, full 6S (25.2 V)', 'sagging (21.0 V)', 'empty (19.8 V)'], rows)
    pin_max, _ = losses.fc_power(2.0, 2.0)
    found['lead'] = pin_max / 19.8
    verdict('Stack lead', 'FC at full load through the lead alone, empty 6S', pin_max / 19.8 <= J['i_rated'],
            '%.2f A' % (pin_max / 19.8), '%.0f A per JST-SH contact' % J['i_rated'])
    # with the FC's own battery pads wired as well: the ESC's planes push motor
    # current round the loop the lead and the pad wires make
    I = {n: i_motor for n in CH}
    sg = dcflow.solve(c, 'GND', {**{'R_SH%d' % n: I[n] for n in CH}, 'P_BAT-': -sum(I.values())}, T=60.0)
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
    # ground offsets the signals see
    sg30 = dcflow.solve(c, 'GND', {**{'R_SH%d' % n: 30.0 for n in CH}, 'P_BAT-': -120.0}, T=60.0)
    off = {n: sg30.term_v['U_ESC%d' % n] - sg30.term_v['J_FC'] for n in CH}
    cs = {n: sg30.term_v['U_CS%d' % n] - sg30.term_v['J_FC'] for n in CH}
    err = np.mean(list(cs.values())) / 12.5e-3
    say('Ground offsets at 30 A on every motor (lead only, no loop): each ESC '
        'processor\'s ground against the stack connector\'s, which the FC\'s DShot '
        'signals are referenced to: %s mV.  DShot is 3.3 V logic with about 1 V '
        'of noise margin, so this is harmless.  The current-sense amplifiers\' '
        'grounds sit %s mV from the connector\'s.  CUR is the mean of the four '
        'outputs, read against the FC\'s ground at 12.5 mV per amp of battery '
        'current, so the mean offset reads as %+.1f A on the 120 A Betaflight '
        'shows (%.0f %%): a reading error, not a fault.' % (
            ', '.join('%+.0f' % (v * 1e3) for v in off.values()),
            ', '.join('%+.0f' % (v * 1e3) for v in cs.values()), err, 100 * err / 120))
    say()
    # the FC's own supply copper at its full load
    cf = copper.extract('fc')
    rows = []
    for net, (cur, ref) in stack.FC_PATHS.items():
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
    table_ = [('Q', data.FET['tch_max'], 'FET channel, abs max'),
              ('U_GD', data.DRV8300['tj_max'], 'DRV8300 junction'),
              ('U_ESC', data.G071['tj_max'], 'STM32G071 junction (suffix 6)'),
              ('U_CS', data.INA186['ta_max'], 'INA186 operating'),
              ('U_GVDD', data.TPS7A16['tj_max'], 'TPS7A16 junction'),
              ('U_BUCK5', data.LMR38020F['tj_max'], 'LMR38020F junction'),
              ('U_BUCK9', data.LM76003['tj_max'], 'LM76003 junction'),
              ('U_BUCK', data.MAX15062['tj_max'], 'MAX15062 junction'),
              ('U_LDO', data.TLV76733['tj_max'], 'TLV76733 junction'),
              ('U_FC', data.G473['tj_max'], 'STM32G473 junction (suffix 6)'),
              ('U_IMU', data.ICM45686['t_max'], 'gyro operating'),
              ('U_FLASH', data.W25Q128['t_max'], 'flash operating'),
              ('U_OSD', data.AT7456E['t_max'], 'OSD operating'),
              ('J_', data.JST_SH['t_max'], 'JST-SH connector'),
              ('L', 125.0, 'inductor'),
              ('R_SH', data.SHUNT['t_zero'] - (data.SHUNT['t_zero'] - data.SHUNT['t_full']) * shunt_w / data.SHUNT['p_rated'],
               'shunt terminal, derated for its power'),
              ('D_TVS', 175.0, 'TVS junction')]
    for pre, t, what in table_:
        if ref.startswith(pre):
            return t, what
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
    op = dict(esc=dict(V=V, f=pwm_f(max(th.values())), dead=data.AM32['dead'] + data.DRV8300['dead'][1],
                       I=I, D=D, sw=sw), Ib=Ib)
    if fc:
        pin, _ = losses.fc_power(fc['i5'], fc['i9'])
        op['fc'] = dict(fc, i_lead=pin / V)
    return op


def steady(m, op, iters=4):
    T = None
    for _ in range(iters):
        T = m.solver.steady(m.heat(op, T))
        if np.nanmax(T) > 400:
            break
    return T


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
        '2 A on 5 V and 2 A on 9 V.' % (HEAT_H, data.STACK['gap']))
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
        for Ta in ((45.0,) if QUICK else (25.0, 45.0, 60.0)):
            m = model(v, Ta)
            th, op, T = search(m, all_ok)
            th2, op2, T2 = search(m, fet_ok)
            results[(v, Ta)] = (th, op, T, th2, op2)
            nxt = worst(m, steady(m, operating(min(th + 3, 100), V, sw, fcmax)), op)[0]
            rows.append(['%.0f m/s' % v, '%.0f C' % Ta,
                         '%.0f %% (%.1f A)' % (th, op['Ib'][1]),
                         '%s (%s, %.0f C)' % (nxt[1], nxt[4], nxt[3]),
                         '%.0f %% (%.1f A battery, %.1f A phase)' % (th2, op2['Ib'][1], op2['esc']['I'][1])])
            log('  air %.0f m/s, %.0f C: %.0f %% all ratings (%s), %.0f %% FETs 150 C' % (v, Ta, th, nxt[1], th2))
    say('**What the stack can hold indefinitely**: the highest throttle on all '
        'four motors that holds, at steady state, (a) every part inside its '
        'rating, and (b) the FETs under 150 C (the power stage survives, even '
        'where smaller parts are out of their ratings).  Bisection to 1 %:')
    say()
    table(['Air over the stack', 'Air temperature', '(a) Every part in its rating: throttle (battery A per motor)',
           'First part past its rating above that', '(b) FETs under 150 C'], rows)
    # where the heat comes from, hovering on a hot day
    m = model(5.0, 45.0)
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
        cat['gate drive'] += 2 * data.FET['qg_11v'] * data.GVDD * f + data.DRV8300['i_q'] * data.GVDD
    cat['gate-drive LDO'] = (V - data.GVDD) * losses.gvdd_current(e['f'])
    Tcu = np.mean([m.temp(T, k) for k in m.parts if k.startswith('ESC Q')])
    for k, w in copperloss.loss_groups(m.units, e['I'], e['D']).items():
        cat['copper: ' + k] = w * (1 + dcflow.ALPHA * (Tcu - 20))
    total = sum(cat.values())
    found['hover_heat'] = (total, cat)
    say('Where the ESC\'s heat comes from while hovering (%.0f %% throttle: %.1f A per '
        'motor from the pack, %.1f A in the motor phases at %.0f %% duty, %.0f kHz PWM) '
        'in 45 C air, 5 m/s, at the temperatures that reach (copper near %.0f C):' % (
            HOVER, op['Ib'][1], e['I'][1], 100 * e['D'][1], e['f'] / 1e3, Tcu))
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

    With am32, each motor's own MCU temperature applies AM32's temperature
    limit: above it the motor's duty is cut to a quarter, falling to nothing
    10 C higher (firmware/README.md)."""
    T = T0.copy()
    groups = watch if isinstance(watch, dict) else {k: [k] for k in watch}
    trace = dict(t=[], throttle=[], cut=[], applied=[], **{k: [] for k in groups})
    t = 0.0
    lim = data.AM32['temp_limit']
    first = {}
    for dur, th in schedule:
        for _ in range(int(round(dur / dt))):
            per = {}
            cut = False
            for n in CH:
                tm = m.temp(T, 'ESC U_ESC%d' % n)
                cap = 100.0
                if am32 and tm > lim:
                    cap = max(0.0, 25.0 * (1 - (tm - lim) / 10.0))
                    cut = True
                per[n] = min(th, cap)
            op = operating(th, V, sw, fc, per_motor=per)
            T = m.solver.step(T, m.heat(op, T), dt)
            t += dt
            trace['t'].append(t); trace['throttle'].append(th); trace['cut'].append(cut)
            trace['applied'].append(min(per.values()))
            for k, names in groups.items():
                trace[k].append(max(m.temp(T, x) for x in names))
            for margin, name, temp, limit, what in worst(m, T, op):
                if margin < 0 and name not in first:
                    first[name] = (t, temp, limit, what)
    return T, trace, first


HOVER = round(losses.hover(data.BATTERY['vfull']), 1)     # % throttle for the quad's weight on a full pack


def bursts_section(sw, fcmax):
    log('heat: bursts')
    V = data.BATTERY['vfull']
    say('**Bursts.**  Hovering (%.0f %% throttle) until the stack has settled, '
        'then full throttle, which AM32 holds to %.0f A per motor: the '
        'temperatures while hovering, and how fast the hottest parts climb.' % (
            HOVER, data.AM32['current_limit']))
    say()
    rows = []
    for Ta, v in (((45.0, 5.0),) if QUICK else ((25.0, 5.0), (45.0, 5.0), (45.0, 10.0), (60.0, 5.0))):
        m = model(v, Ta)
        op0 = operating(HOVER, V, sw, fcmax)
        T0 = steady(m, op0)
        fets = [k for k in m.parts if k.startswith('ESC Q')]
        caps = [k for k in m.parts if m.parts[k].get('kind') == 'C1U_16_0201']
        mcu = ['ESC U_ESC%d' % n for n in CH]
        hot = lambda T, ks: max(m.temp(T, k) for k in ks)
        T, tr, first = run_transient(m, [(3.0 if QUICK else 30.0, 100.0)], sw, T0, 0.25, fcmax, V, am32=False,
                                     watch=fets + mcu + caps)
        t = np.array(tr['t'])
        fmax = np.max([tr[k] for k in fets], axis=0)
        mmax = np.max([tr[k] for k in mcu], axis=0)
        when = lambda arr, lim: ('%.1f s' % t[np.argmax(arr >= lim)]) if (arr >= lim).any() else '> 30 s'
        at = lambda arr, s_: '%.0f' % np.interp(s_, t, arr)
        rows.append(['%.0f C, %.0f m/s' % (Ta, v),
                     '%.0f / %.0f / %.0f C' % (hot(T0, fets), hot(T0, mcu), hot(T0, caps)),
                     '%s / %s / %s C' % (at(fmax, 5), at(fmax, 10), at(fmax, 30)),
                     when(mmax, data.AM32['temp_limit']), when(fmax, 150.0), when(fmax, data.FET['tch_max'])])
    table(['Air', 'Hovering: hottest FET / processor / bootstrap capacitor',
           'Hottest FET after 5 / 10 / 30 s full throttle', 'Processor reaches AM32\'s %.0f C cut' % data.AM32['temp_limit'],
           'A FET reaches 150 C', 'A FET reaches its 175 C maximum'], rows)


def groups_of(m):
    """The parts the flight follows, as the hottest of each kind."""
    kind = lambda k: [x for x in m.parts if m.parts[x].get('kind') == k]
    return {
        'ESC FETs (hottest)': [x for x in m.parts if x.startswith('ESC Q')],
        'ESC processors (hottest)': ['ESC U_ESC%d' % n for n in CH],
        'ESC gate drivers (hottest)': ['ESC U_GD%d' % n for n in CH],
        'ESC bootstrap capacitors, X5R (hottest)': [x for x in kind('C1U_16_0201') if x.startswith('ESC')],
        'ESC bridge capacitors, X7R (hottest)': [x for x in kind('C_BRIDGE') if x.startswith('ESC')],
        'ESC shunts (hottest)': ['ESC R_SH%d' % n for n in CH],
        'ESC stack connector': ['ESC J_FC'],
        'FC stack connector': ['FC J_ESC'],
        'FC gyro': ['FC U_IMU'],
        'FC processor': ['FC U_FC'],
        'FC 9 V buck': ['FC U_BUCK9'],
        'FC 5 V buck': ['FC U_BUCK5'],
    }


def flight_section(sw, fcmax):
    log('heat: hot flight')
    V = data.BATTERY['vfull']
    Ta, v = 45.0, 5.0
    m = model(v, Ta)
    cycle = [(2.0, 100.0), (4.0, 60.0), (14.0, 40.0)]
    sched = cycle * (1 if QUICK else 9)          # three minutes
    Ib = sum(d * losses.limited(th, V)[0] for d, th in cycle) / sum(d for d, _ in cycle)
    say('**A hard flight on a hot day.**  45 C air, 5 m/s over the stack, a full '
        'pack, three minutes of 20 s cycles: 2 s full throttle, 4 s at 60 %%, '
        '14 s at 40 %% (on average %.1f A per motor, %.0f A from the pack: a '
        '1300 mAh pack empties in about %.1f minutes at that rate).  Starting '
        'from the air temperature, with AM32\'s temperature limit active.' % (
            Ib, 4 * Ib, 1.3 / (4 * Ib) * 60))
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
        say('AM32\'s temperature limit (%.0f C at each processor\'s sensor) first cut '
            'power at %.0f s, and was cutting for %.0f %% of the flight: each time, '
            'that motor drops to a quarter of full power or less, which in the air '
            'is a sudden loss of thrust on one corner.  It is what keeps the FETs '
            'below their limit here.' % (data.AM32['temp_limit'], cut[0], 100 * frac))
    else:
        say('AM32\'s temperature limit never cut in.')
    say()
    found['flight'] = dict(cut=cut[0] if cut else None, frac=frac,
                           fet=max(tr['ESC FETs (hottest)']), mcu=max(tr['ESC processors (hottest)']),
                           first=min(first.items(), key=lambda kv: kv[1][0]) if first else None)
    np.savez(os.path.join(OUT, 'hot-flight.npz'), T=T, **{k: np.asarray(v) for k, v in tr.items()})
    plot_flight(tr, groups, m)
    plot_maps(m, T, 'hot-flight')
    return first, tr


def ground_section(sw):
    log('heat: on the ground')
    V = data.BATTERY['vfull']
    m0 = model(0.0, 45.0)
    tau = m0.solver.cap.sum() / m0.solver.gamb.sum()
    say('**Waiting on the ground with the video on.**  Still air, the motors '
        'stopped (the ESC\'s processors and gate supply on).  The stack\'s '
        'thermal time constant in still air is about %.0f minutes, so steady '
        'state (below) comes after a quarter of an hour; the second table is '
        'the first minutes.' % (tau / 60))
    say()
    rows = []
    res = {}
    for Ta in ((45.0,) if QUICK else (25.0, 45.0, 60.0)):
        for tag, fc in (('both rails at 2 A', data.FC_LOAD_MAX), ('9 V at 1.5 A, 5 V at 1 A', dict(i5=1.0, i9=1.5)),
                        ('9 V at 1 A, 5 V at 0.5 A', dict(i5=0.5, i9=1.0))):
            m = model(0.0, Ta)
            op = operating(0.0, V, sw, fc)
            T = steady(m, op)
            over = [x for x in worst(m, T, op) if x[0] < 0]
            res[(Ta, tag)] = over
            rows.append(['%.0f C' % Ta, tag, '%.1f W' % losses.fc_power(fc['i5'], fc['i9'])[0],
                         '%.0f C' % m.temp(T, 'FC U_BUCK9'), '%.0f C' % m.temp(T, 'FC U_IMU'),
                         '%.0f C' % m.temp(T, 'FC U_FC'), '%.0f C' % m.temp(T, 'FC J_ESC'),
                         '%d; worst %s' % (len(over), ', '.join('%s %.0f C (%.0f)' % (x[1], x[2], x[3]) for x in over[:3]))
                         if over else 'none'])
    table(['Air', 'FC load', 'FC input', '9 V buck', 'Gyro', 'Processor', 'Stack connector',
           'Parts past their rating (rating)'], rows)
    found['ground'] = res
    rows = []
    for Ta in ((45.0,) if QUICK else (25.0, 45.0)):
        for tag, fc in (('9 V at 1.5 A, 5 V at 1 A', dict(i5=1.0, i9=1.5)), ('9 V at 1 A, 5 V at 0.5 A', dict(i5=0.5, i9=1.0))):
            m = model(0.0, Ta)
            groups = {'gyro': ['FC U_IMU'], 'processor': ['FC U_FC'], 'buck': ['FC U_BUCK9'],
                      'X5R': [x for x in m.parts if x.startswith('FC') and data.CAPS.get(m.parts[x].get('kind') or '', ('',))[0] == 'X5R'],
                      'connector': ['FC J_ESC', 'ESC J_FC']}
            T, tr, first = run_transient(m, [(60.0 if QUICK else 600.0, 0.0)], sw, np.full(m.n, Ta), 5.0, fc, V,
                                         am32=False, watch=groups)
            t = np.array(tr['t'])
            when = lambda key, lim: ('%.1f min' % (t[np.argmax(np.array(tr[key]) >= lim)] / 60)
                                     if (np.array(tr[key]) >= lim).any() else '> %.0f min' % (t[-1] / 60))
            rows.append(['%.0f C' % Ta, tag, when('X5R', 85.0), when('connector', data.JST_SH['t_max']),
                         when('gyro', data.ICM45686['t_max']), when('processor', data.G473['tj_max'])])
    table(['Air', 'FC load', 'An X5R capacitor reaches 85 C', 'A stack connector reaches 85 C',
           'The gyro reaches 85 C', 'The processor reaches 105 C'], rows)


# =================================================================== figures
def plot_flight(tr, groups, m):
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
    ax[0].set_title('Hard flight, 45 C air, 5 m/s over the stack (dotted 85 C, dashed 105 C, red 175 C)')
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
def summary():
    out = ['# Ridge 3 stack: stress simulations', '',
           'Generated by `sim/stress.py` on %s.  The FC on the ESC, a full 6S pack '
           '(25.2 V), hot air, full current.' % time.strftime('%Y-%m-%d'), '',
           '**What this is not:** a measurement.  These are simulations of the '
           'design files, with the makers\' datasheet figures (`sim/data.py`, each '
           'with its source) and a few stated assumptions.  They say where the '
           'design runs out of margin and roughly by how much.  Bring-up on the '
           'bench is still the test.', '', '## Verdict', '']
    out.append('| Area | Check | Result | Simulated | Limit |')
    out.append('|---|---|---|---|---|')
    order = {'FAIL': 0, 'MARGINAL': 1, 'PASS': 2}
    for a, c, r, n, l in sorted(verdicts, key=lambda v: order.get(v[2], 3)):
        out.append('| %s | %s | **%s** | %s | %s |' % (a, c, r, n, l) if r != 'PASS' else '| %s | %s | %s | %s | %s |' % (a, c, r, n, l))
    out.append('')
    return out


def main():
    t0 = time.time()
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
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
    fixes_section()
    limits_section()
    text = '\n'.join(summary() + lines)
    text += '\n---\nRun time %.0f min.\n' % ((time.time() - t0) / 60)
    open(REPORT, 'w').write(text)
    log('wrote', REPORT)


def fixes_section():
    say('## What would fix it')
    say()
    say('In order of what they buy.  None of these has been simulated as a '
        'changed board yet; each is what the runs above point at.')
    say()
    total, cat = found.get('hover_heat', (0, {}))
    share = lambda key: 100 * sum(w for k, w in cat.items() if key in k) / total if total else 0
    items = [
        ('The ESC\'s sense-node copper.',
         'Each channel\'s low-side FETs reach their shunt through islands of '
         'bottom-layer copper joined to a strip on In3 by single vias: %.1f mOhm '
         'on average, more than the FET itself.  One unbroken pour from the three '
         'low-side sources to the shunt (the bridge capacitors\' battery pads and '
         'the low-side gate lines moved off that strip, the gate lines onto an '
         'inner layer), stitched to In3 with a field of vias under each FET, '
         'takes most of the %.0f %% of the hover heat that is sense-node copper.' % (
             found.get('r_src', 0) * 1e3, share('sense nodes'))),
        ('The battery planes.',
         'All of the battery current crosses one 1 oz plane each way (%.2f mOhm '
         'together), and at %.0f %% of the hover heat.  More copper for VBAT and '
         'GND: a second plane pair where In2/In3 are free, or 2 oz inner layers, '
         'which the README explains the gate routing does not allow today.' % (
             found.get('r_planes', 0) * 1e3, share('plane'))),
        ('The dead time.',
         'AM32\'s DEAD_TIME 40 (625 ns) plus the DRV8300\'s own ~215 ns puts the '
         'current through the low-side body diodes for about 0.84 us of every '
         'edge: %.0f %% of the hover heat.  Shortening it after a scope check of '
         'the gate drive (the firmware README already plans that) cuts it in '
         'proportion.' % share('dead time')),
        ('The switch-node ringing.',
         'At a full 6S pack the switch node rings to the 40 V FETs\' rating when '
         'a high-side FET turns on, and the high-side FET reaches %.0f V at '
         'turn-off at 30 A.  An RC snubber across each FET (1 ohm + 4.7-10 nF, '
         'simulated above) or 60 V FETs (about twice the on-resistance in this '
         'package, the trade the README describes) buy margin; keeping every '
         'bridge capacitor as close to its FETs as now is what keeps it this low.' % found.get('hs_peak', 0)),
        ('Temperature grades.',
         'Suffix-3 STM32s (STM32G071GBU3, STM32G473CEU3: junction to 130 C) if '
         'stock allows; until then set AM32\'s temperature limit below the '
         'suffix-6 parts\' 105 C junction (it is 110 C now).  X7R instead of X5R '
         'for the ESC\'s bootstrap and driver-supply capacitors and the FC\'s '
         'regulator capacitors (X5R is rated to 85 C).'),
        ('The stack lead.',
         'The FC\'s full 30 W does not fit through one 1 A JST-SH contact: '
         '%.1f A on an empty 6S pack.  Budget the FC\'s rails to what the lead '
         'carries (%.0f W on an empty pack), or feed the HD VTX from the '
         'battery directly.  Wiring the FC\'s own battery pads as well creates a '
         'ground loop that puts %.1f A through the lead\'s GND contact at 20 A '
         'per motor.' % (found.get('lead', 0), data.JST_SH['i_rated'] * 19.8, found.get('loop', 0))),
        ('The external capacitor.',
         'The ripple at full throttle, %.0f A rms, is %.0f times what two FR-A '
         '100 uF cans are rated for (%.1f A).  Specify capacitors rated for the '
         'ripple (polymer-hybrid, several in parallel) and always fit them: '
         'without them, plugging in a full pack alone comes close to the FETs\' '
         'rating.' % (found.get('ripple', 0), found.get('ripple', 0) / data.EXT_CAP['ripple'], data.EXT_CAP['ripple'])),
    ]
    for title, text in items:
        say('- **%s** %s' % (title, text))
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
    f = found.get('flight', {})
    verdict('Heat', 'Hard 3-minute flight at 45 C: AM32 cuts a motor\'s power for heat',
            f.get('cut') is None, 'first at %.0f s, %.0f %% of the flight' % (f['cut'], 100 * f['frac'])
            if f.get('cut') is not None else 'never', 'never')
    verdict('Heat', 'Hard 3-minute flight at 45 C: hottest FET', f.get('fet', 0) < 150 or
            ('MARGINAL' if f.get('fet', 0) < data.FET['tch_max'] else False),
            '%.0f C' % f.get('fet', 0), '175 C (150 C design)')
    verdict('Heat', 'Hard 3-minute flight at 45 C: ESC processors', f.get('mcu', 0) <= data.G071['tj_max'],
            '%.0f C' % f.get('mcu', 0), '%.0f C junction (suffix 6)' % data.G071['tj_max'])
    if f.get('first'):
        k, (t, temp, lim, what) = f['first']
        verdict('Heat', 'Hard 3-minute flight at 45 C: first part past its rating', False,
                '%s (%s) at %.0f s' % (k, what, t), '%.0f C' % lim)
    for (Ta, tag), over in sorted(found.get('ground', {}).items()):
        if tag.startswith('9 V at 1.5 A'):
            verdict('Heat', 'On the ground, video on (%s), %.0f C still air' % (tag, Ta), not over,
                    '%d parts past their rating' % len(over) if over else 'all inside', '-')


if __name__ == '__main__':
    main()
