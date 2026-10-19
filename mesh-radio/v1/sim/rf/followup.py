# -*- coding: utf-8 -*-
"""Follow-up RF checks on the board as committed in 6cb9185 (the sim/rf fixes are now in src/):

  A. R41 = Vishay RCS080568R0FKEA (anti-surge 0805) against its derating.
  B. Antenna missing: transient heating of L15 (LQW2BAN3N6J00L, output match) and L18
     (LQW15AN47NJ00D, ESD shunt) for a 1 s burst and for 1 s bursts at 25 % duty, 25 and 60 C;
     and a missing-antenna detector (printed coupler + 3 parts) for firmware.
  C. Harmonics 6f-10f: fixes that give positive margin with the same -45 dBc PA assumption,
     worst case over the trace lengths between the filters (reflective stop bands interact),
     and the default US configuration (30 dBm, 2.15 dBi) without a fix.

    tools/kd python3 sim/rf/followup.py     # from mesh-radio/v1, ~1-2 min; writes followup.txt + PNGs
"""
import itertools
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rflib as R     # noqa: E402
import rfboard as B   # noqa: E402
import lfcn           # noqa: E402
import run            # noqa: E402

OUT = []
SUM = []


def out(s=''):
    OUT.append(s)
    print(s)


def summ(item, verdict, nums):
    SUM.append((item, verdict, nums))
    out('  -> %s: %s  [%s]' % (item, verdict, nums))


C1, C2, C3, C4, CG, CR = run.C1, run.C2, run.C3, run.C4, run.CG, run.CR


# ============================================================================ A. R41
def study_r41():
    out('=' * 100)
    out('A. R41 = Vishay RCS080568R0FKEA (RCS e3 anti-surge, 0805, 1 %, +-100 ppm/C)')
    out('=' * 100)
    out('Rating: LCSC lists 0.4 W; DigiKey and Vishay\'s 2023 RCS e3 release give 0.5 W at 70 C; Vishay derates linearly')
    out('to 0 W at 155 C.  The 0.4 W figure is used (conservative).  Powers from study 3 (worst PA-input phase).')
    pw = {20: 0.0743, 21: 0.0936, 22: 0.1178, 23: 0.1483}
    for t in (25, 60, 85):
        rat = run.r0805_rating(t, p70=0.4)
        out('  %3d C rating %.0f mW:  ' % (t, 1e3 * rat) + '  '.join('+%d dBm %.0f %%' % (p, 100 * w / rat) for p, w in pw.items()))
    worst = 100 * pw[23] / run.r0805_rating(85, p70=0.4)
    summ('R41 RCS080568R0FKEA', 'PASS' if worst <= 70 else 'MARGINAL',
         '%.0f %% of its 85 C rating at +22 dBm, %.0f %% at +23 dBm (0.4 W basis); %.0f %% at +20 dBm'
         % (100 * pw[22] / run.r0805_rating(85, p70=0.4), worst, 100 * pw[20] / run.r0805_rating(85, p70=0.4)))


# ============================================================================ B. heating, antenna missing
# Thermal data (ESTIMATES, makers publish none):
#   total part-to-ambient resistance from Murata's rated current (20 C rise at I_rated^2 x Rdc max, on
#   Murata's test board): LQW2BAN3N6J00L 2.0 A, 50 mOhm -> 0.20 W -> 100 K/W; LQW15AN47NJ00D 0.21 A,
#   1.08 Ohm -> 48 mW -> 420 K/W.  Split part -> pads (terminations, solder) / pads -> ambient (board).
#   Heat capacity from volume x 3.4 J/cm3K (alumina core) plus copper: 0805 2.0x1.25x1.5 mm -> 0.016 J/K;
#   0402 1.0x0.5x0.5 mm -> 0.001 J/K.  Board copper + FR-4 within ~5 mm of the part: 0.25 / 0.08 J/K.
THERM = {
    'LQW2BAN3N6J00L': dict(r1=35.0, r2=65.0, c1=0.016, c2=0.25),
    'LQW15AN47NJ00D': dict(r1=200.0, r2=220.0, c1=0.001, c2=0.08),
}


def thermal(p_w, th, t_amb, on=1.0, period=None, t_end=None, dt=1e-3):
    """Two-node RC: part (c1) -r1- pads/board (c2) -r2- ambient.  Returns (t, Tpart, Tpad)."""
    t_end = t_end or (on + 3 if period is None else 300.0)
    n = int(t_end / dt)
    tp, tb = t_amb, t_amb
    T = np.empty(n)
    P = np.empty(n)
    Bd = np.empty(n)
    for i in range(n):
        t = i * dt
        if period is None:
            p = p_w if t < on else 0.0
        else:
            p = p_w if (t % period) < on else 0.0
        q12 = (tp - tb) / th['r1']
        tp += dt * (p - q12) / th['c1']
        tb += dt * (q12 - (tb - t_amb) / th['r2']) / th['c2']
        T[i], Bd[i], P[i] = tp, tb, p
    return np.arange(n) * dt, T, Bd


def study_heating():
    out()
    out('=' * 100)
    out('B. Antenna missing: L15 (3.6 nH output match) and L18 (47 nH ESD shunt), 1 s bursts')
    out('=' * 100)
    out('RF dissipation from run.py\'s saturated-PA model (model A, worst phase of the open, 902-928 MHz); the 50-ohm-source')
    out('model cannot see inside the PA match.  Thermal data are ESTIMATES (see THERM in followup.py): R part->pads / pads->')
    out('ambient, C part / board: L15 35 / 65 K/W, 0.016 / 0.25 J/K; L18 200 / 220 K/W, 0.001 / 0.08 J/K.  Criterion: part')
    out('<= 125 C (Murata operating maximum) PASS; pads (solder joint) must stay below 200 C.  The PA\'s own heat raises the')
    out('local board above ambient; that is not included (the thermal study of the routed board adds it).')
    b = B.Board()
    ckt = b.tx_out(with_pa=True)
    ph = np.linspace(0, 2 * np.pi, 90, endpoint=False)
    w = 2 * np.pi * 915e6
    refs = {'L15': [r for r in run.refs_between('PA_OUT', 'PA_M1')][0], 'L18': run.refs_between('ANT', 'GND')[0]}
    res = {}
    for vpa in (2.7, 3.6, 4.0):
        pa = run.PA(vpa)
        for name, ref in refs.items():
            b.value(ref)
            info = b.info[ref]
            a, bb = B.BY_REF[ref].pins['1'], B.BY_REF[ref].pins['2']
            rac = float(R.Ind(info['value'], info['q'], info['fq'], info['srf'], info['rdc']).r(np.array([w]))[0, 0])
            L = float(np.atleast_1d(info['value'])[0])

            def p_of(g):
                v, _ = pa.solve(ckt, [902e6, 915e6, 928e6], g)
                va = v[a][0] if a != 'GND' else 0
                vb = v[bb][0] if bb != 'GND' else 0
                i = np.abs((va - vb) / (rac + 1j * w * L)) / math.sqrt(2)
                return float(np.max(i ** 2 * rac))
            pm = p_of(0.0)
            po = max(p_of(np.exp(1j * p)) for p in ph)
            res[(vpa, name)] = (pm, po, info['mpn'])
    out('  dissipation (W), matched / antenna missing:')
    for vpa in (2.7, 3.6, 4.0):
        out('   VPA %.1f V:  L15 %.3f / %.3f    L18 %.3f / %.3f' % (vpa, res[(vpa, 'L15')][0], res[(vpa, 'L15')][1],
                                                                 res[(vpa, 'L18')][0], res[(vpa, 'L18')][1]))
    out()
    out('  peak temperatures, part / pads (C):  single 1 s burst | 1 s every 4 s (25 % duty), periodic steady state')
    curves = {}
    worst = {}
    for name in ('L15', 'L18'):
        for vpa in (2.7, 3.6, 4.0):
            pm, po, mpn = res[(vpa, name)]
            th = THERM[mpn]
            for tamb in (25, 60):
                t1, a1, b1 = thermal(po, th, tamb)
                t2, a2, b2 = thermal(po, th, tamb, period=4.0)
                curves[(name, vpa, tamb)] = (t2, a2)
                out('   %s VPA %.1f V  %2d C ambient, %.2f W:   %5.0f / %5.0f   |   %5.0f / %5.0f' % (
                    name, vpa, tamb, po, a1.max(), b1.max(), a2.max(), b2.max()))
                worst[(name, vpa, tamb)] = (a1.max(), a2.max(), b2.max())
    for name in ('L15', 'L18'):
        for vpa, label in ((2.7, '1 W, VPA 2.7 V'), (3.6, '~2.5 W, VPA 3.6 V'), (4.0, '3 W, VPA 4.0 V')):
            s1, s25, pad = worst[(name, vpa, 60)]
            v = 'PASS' if s25 <= 125 else 'FAIL'
            summ('%s antenna missing, %s, 60 C' % (name, label), v,
                 'single 1 s burst %.0f C, 25 %% duty %.0f C (pads %.0f C); limit 125 C' % (s1, s25, pad))
    # sensitivity of the worst case to the thermal estimate
    pm, po, mpn = res[(4.0, 'L15')]
    out('  sensitivity, L15 at 4.0 V, 60 C, 25 % duty: ' + ', '.join(
        'R1 %d / Rtot %d K/W -> %.0f C' % (r1, rt, thermal(po, dict(r1=r1, r2=rt - r1, c1=0.016, c2=0.25), 60, period=4.0)[1].max())
        for r1, rt in ((25, 70), (35, 100), (50, 145))))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for (name, vpa, tamb), col in (((('L15', 4.0, 60)), C2), (('L15', 3.6, 60), C1), (('L15', 2.7, 60), C3), (('L18', 4.0, 60), C4)):
        t, T = curves[(name, vpa, tamb)]
        k = t >= 280
        ax.plot(t[k] - 280, T[k], color=col, lw=1.5, label='%s, VPA %.1f V, 60 C ambient' % (name, vpa))
    ax.axhline(125, color=CR, ls='--', lw=1, label='125 C part maximum')
    ax.set_xlabel('s (last 20 s of 300 s of 1 s bursts every 4 s)')
    ax.set_ylabel('part temperature, C')
    ax.set_title('Antenna missing: inductor temperature, 25 % duty (thermal data estimated)', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'followup_heating.png'), dpi=110)
    plt.close(fig)
    return res


def study_detector():
    out()
    out('  Missing-antenna detector (3 parts + copper), first-order estimate (no EM model of the routed board):')
    out('   a ~10 mm line edge-coupled (0.15 mm gap) to the U.FL feed after the LFCN; coupled-port end ->')
    out('   BAT15-02EL Schottky -> 1 nF to an nRF analog pin; other end -> 49.9 R to ground.  Coupling k~0.15 over')
    out('   beta*l = 0.35 rad: C ~ 20log(k sin(beta l)) ~ -26 dB; directivity of a short microstrip coupler ~10-15 dB.')
    for p in (30.0, 35.0):
        for rl_ant, lab in ((20, 'good antenna (RL 20 dB)'), (10, 'poor antenna (VSWR 2)'), (0, 'antenna missing')):
            refl = p - rl_ant - 26
            leak = p - 26 - 12
            tot = 10 * math.log10(10 ** (refl / 10) + 10 ** (leak / 10))
            out('   %2.0f dBm, %-24s coupled reverse wave %+5.1f dBm' % (p, lab, tot))
    out('   -> >= 8 dB between a missing and a VSWR-2 antenna whatever the cable length (it measures |Gamma|, not the')
    out('      voltage at one point); a detector diode at +0..+10 dBm gives ~0.3-1.5 V.  Firmware: read it ~1 ms after')
    out('      PA_EN in every burst; above threshold drop VPA to 2.7 V and SX1262 drive, flag "no antenna".')


# ============================================================================ C. harmonics 6f-10f
def add_lfcg(ckt, a, b, prefix='FG_'):
    lfcn.add(ckt, a, b, prefix=prefix, p=lfcn.G_FIT)


def lfcg_response(f):
    c = R.Circuit('lfcg')
    add_lfcg(c, 'a', 'b')
    return c.sparams(f, ['a', 'b'])[0]


def chain(b, variant, lines, with_pa):
    """variant: 'base' (as committed), 'a' LFCG instead of the discrete LPF, 'b' LFCG instead of the LFCN,
    'c' LFCG added after the LFCN."""
    c = R.Circuit(variant)
    if with_pa:
        b.pa_out(c)
    if variant == 'a':
        add_lfcg(c, 'PA_M2', 'PA_TX')
    else:
        b.add_parts(c, B.NETS_LPF)
    c.add2('PA_TX', 'SW2', R.Line(lines[0]), 'l1')
    b.sky13330(c, 'SW2', 'SW1')
    c.add2('SW1', 'ANT_SW', R.Line(lines[1]), 'l2')
    if variant == 'b':
        add_lfcg(c, 'ANT_SW', 'LF_OUT')
    else:
        b.lfcn(c, 'ANT_SW', 'LF_OUT')
    if variant == 'c':
        c.add2('LF_OUT', 'G_IN', R.Line(1.0), 'l3a')
        add_lfcg(c, 'G_IN', 'G_OUT')
        c.add2('G_OUT', 'ANT', R.Line(lines[2]), 'l3')
    else:
        c.add2('LF_OUT', 'ANT', R.Line(lines[2]), 'l3')
    b.add_parts(c, B.NETS_ANT)
    return c


def sw_chain(b, variant, lines):
    c = R.Circuit('sw')
    c.add2('SW1', 'ANT_SW', R.Line(lines[1]), 'l2')
    if variant == 'b':
        add_lfcg(c, 'ANT_SW', 'LF_OUT')
    else:
        b.lfcn(c, 'ANT_SW', 'LF_OUT')
    if variant == 'c':
        c.add2('LF_OUT', 'G_IN', R.Line(1.0), 'l3a')
        add_lfcg(c, 'G_IN', 'G_OUT')
        c.add2('G_OUT', 'ANT', R.Line(lines[2]), 'l3')
    else:
        c.add2('LF_OUT', 'ANT', R.Line(lines[2]), 'l3')
    b.add_parts(c, B.NETS_ANT)
    return c


def excess(variant, fh):
    """Model rejection minus the makers' typical table (signed): the LTCC models are given the tables' magnitude
    (LFCN above 7 GHz: its 7 GHz value, 18.6 dB, ASSUMED) and keep their own phase."""
    lf = -R.db20(lfcn.response(fh)[:, 1, 0]) - np.interp(fh, lfcn.F_TAB, lfcn.IL_TAB, right=lfcn.IL_TAB[-1])
    lg = -R.db20(lfcg_response(fh)[:, 1, 0]) - np.interp(fh, lfcn.G_F_TAB, lfcn.G_IL_TAB, right=lfcn.G_IL_TAB[-1])
    ex = (lf if variant in ('base', 'a', 'c') else 0) + (lg if variant in ('a', 'b', 'c') else 0)
    ex_sw = (lf if variant in ('base', 'a', 'c') else 0) + (lg if variant in ('b', 'c') else 0)
    return ex + 0 * fh, ex_sw + 0 * fh


def margins(variant, pa, lines, p_ant, g_ant, use_pa=True):
    b = B.Board()
    fh = np.concatenate([n * run.FB for n in run.NH])
    ct = chain(b, variant, lines, False)
    S = ct.sparams(np.concatenate([run.FB, fh]), ['PA_M2', 'ANT'])[0]
    loss = -R.db20(S[:3, 1, 0])
    rej = -R.db20(S[3:, 1, 0])
    if use_pa:      # sensitivity only: PA die as the source (internal values guessed)
        cp = chain(b, variant, lines, True)
        v = cp.voltages(fh, {'DIE': 1.0}, loads={'ANT': run.ant_load(0.0)})
        vref = pa.evb.voltages(fh, {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
        rej = (R.db20(vref['PA_M2']) - R.db20(v['ANT']))[0]
    Ss = sw_chain(b, variant, lines).sparams(fh, ['SW1', 'ANT'])[0]
    rsw = -R.db20(Ss[:, 1, 0])
    ex, exs = excess(variant, fh)
    rej, rsw = rej - ex, rsw - exs
    rr = {n: dict(r=rej[3 * k:3 * k + 3][None, :], rsw=rsw[3 * k:3 * k + 3][None, :]) for k, n in enumerate(run.NH)}
    lv = run.harm_levels(rr, p_ant, float(loss.min()))
    m = run.harm_margins(lv, p_ant, g_ant)
    return {n: float(min(m[n]['fcc'][0], m[n]['ham'][0])) for n in run.NH}, float(loss.max()), float(R.rl_db(S[:3, 0, 0]).min())


def study_harmonics():
    out()
    out('=' * 100)
    out('C. Harmonics 6f-10f with the PA at -45 dBc above 3f (ASSUMED, as before)')
    out('=' * 100)
    out('Two reflective filters with a switch between them interact: the result depends on the trace lengths.  Every')
    out('variant is evaluated at the nominal 2 mm traces and over a sweep of')
    out('the three inter-block traces (1, 3, 5, 8, 12 mm each, 125 layouts, 50-ohm model): the worst layout is reported.')
    out('Neither LTCC model is credited with more rejection than its maker\'s typical table (LFCN-1000+ to 7 GHz, LFCG-1000+')
    out('to 10 GHz; above the LFCN table its 7 GHz value, 18.6 dB, is assumed).  Margins in dB (positive passes),')
    out('FCC restricted bands at -41.2 dBm EIRP, 2f/7f at -20 dBc, Part 97 at -43 dBc.')
    pa = run.PA(3.6)
    variants = [('base', 'as committed (discrete LPF + LFCN-1000+)'),
                ('a', 'LFCG-1000+ in place of the 7-part discrete LPF'),
                ('b', 'LFCG-1000+ in place of the LFCN-1000+'),
                ('c', 'LFCG-1000+ added after the LFCN-1000+')]
    sweep = [1.0, 3.0, 5.0, 8.0, 12.0]
    rows = {}
    for key, name in variants:
        out()
        out('  %s: %s' % (key, name))
        for p, g in ((35.0, 6.0), (30.0, 2.15)):
            mn, loss, rl = margins(key, pa, (2.0, 2.0, 2.0), p, g, use_pa=False)
            mpa, _, _ = margins(key, pa, (2.0, 2.0, 2.0), p, g, use_pa=True)
            wl = {n: 99.0 for n in run.NH}
            for ls in itertools.product(sweep, sweep, sweep):
                ml, _, _ = margins(key, pa, ls, p, g, use_pa=False)
                for n in run.NH:
                    wl[n] = min(wl[n], ml[n])
            rows[(key, p, g)] = (mn, wl, loss, rl)
            out('   %2.0f dBm %4.2f dBi nominal  ' % (p, g) + ' '.join('%df %6.1f' % (n, mn[n]) for n in run.NH))
            out('   %2.0f dBm %4.2f dBi worst    ' % (p, g) + ' '.join('%df %6.1f' % (n, min(wl[n], mn[n])) for n in run.NH))
            out('   %2.0f dBm %4.2f dBi PA-src   ' % (p, g) + ' '.join('%df %6.1f' % (n, mpa[n]) for n in run.NH)
                + '   (sensitivity, not the verdict)')
        out('   loss PA -> U.FL %.2f dB, PA load RL %.1f dB' % (loss, rl))
    # LFCG power rating: 5.5 W at 25 C, linear to 1 W at 125 C (passband, CW).  A 1 s burst is long against an 0805
    # LTCC's own thermal time constant, so the burst power is compared with the rating at the local board temperature.
    out()
    out('  LFCG-1000+ power: rated 5.5 W at 25 C, derated linearly to 1 W at 125 C (CW, passband).  No pulse rating is')
    out('  published; a 1 s burst is long against the thermal time constant of an 0805 part, so it counts as CW at the')
    out('  local board temperature (the 25 % duty only lowers that temperature).  VPA 2.7 V = the US 1 W setting.')
    rate = lambda t: 5.5 - 4.5 * (t - 25) / 100
    for key, where, pw in (('a', 'at the PA output', {2.7: R.dbm_to_w(31.1), 3.6: R.dbm_to_w(35.4), 4.0: R.dbm_to_w(36.3)}),
                           ('b/c', 'at the antenna side', {2.7: R.dbm_to_w(30.4), 3.6: R.dbm_to_w(34.3), 4.0: R.dbm_to_w(35.2)})):
        out('   %-4s %-20s ' % (key, where) + '  '.join('VPA %.1f V %.2f W: %s' % (v, w, '/'.join('%.0f%%' % (100 * w / rate(t))
                                                                                                   for t in (25, 60, 85)))
                                                         for v, w in pw.items()) + '   (25 / 60 / 85 C)')
    # verdicts
    out()
    for key, name in variants:
        mn, wl, loss, rl = rows[(key, 35.0, 6.0)]
        w35 = min(min(mn[n], wl[n]) for n in run.NH)
        mn3, wl3, _, _ = rows[(key, 30.0, 2.15)]
        w30 = min(min(mn3[n], wl3[n]) for n in run.NH)
        summ('harmonics 2f-10f, %s' % name, 'PASS' if w35 >= 3 else ('MARGINAL' if w35 >= 0 else 'FAIL'),
             'worst over layouts %.1f dB at 35 dBm / 6 dBi, %.1f dB at 30 dBm / 2.15 dBi; loss %.2f dB' % (w35, w30, loss))
    mn3, wl3, _, _ = rows[('base', 30.0, 2.15)]
    w30n = min(mn3[n] for n in run.NH)
    summ('default US setting (30 dBm, 2.15 dBi) as committed', 'PASS' if min(min(mn3[n], wl3[n]) for n in run.NH) >= 3 else
         ('MARGINAL' if w30n >= 0 else 'FAIL'),
         'nominal layout worst %.1f dB%s; worst layout %.1f dB' % (
             w30n, ''.join(' (%df %.1f)' % (n, mn3[n]) for n in run.NH if mn3[n] < 3),
             min(min(mn3[n], wl3[n]) for n in run.NH)))
    # plot
    f = np.linspace(0.3e9, 10e9, 1941)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(f / 1e9, R.db20(lfcn.response(f)[:, 1, 0]), color=C2, lw=1.3, label='LFCN-1000+ model')
    ax.plot(lfcn.F_TAB / 1e9, -lfcn.IL_TAB, 'o', color=C2, ms=4, label='LFCN-1000+ table')
    ax.plot(f / 1e9, R.db20(lfcg_response(f)[:, 1, 0]), color=C1, lw=1.3, label='LFCG-1000+ model')
    ax.plot(lfcn.G_F_TAB / 1e9, -lfcn.G_IL_TAB, 's', color=C1, ms=4, label='LFCG-1000+ table')
    for n in run.NH:
        ax.axvspan(n * 0.902, n * 0.928, color=CR if n in run.RESTRICTED else CG, alpha=0.18, lw=0)
    ax.set_ylim(-80, 5)
    ax.set_xlabel('GHz')
    ax.set_ylabel('S21, dB')
    ax.set_title('LTCC low-pass filters: models and the makers\' tables (shaded: harmonic bands)', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'followup_filters.png'), dpi=110)
    plt.close(fig)
    return rows


def main():
    out('Mesh Radio v1 - RF follow-up (sim/rf/followup.py), board as committed in 6cb9185')
    out()
    study_r41()
    study_heating()
    study_detector()
    study_harmonics()
    out()
    out('=' * 100)
    out('SUMMARY')
    out('=' * 100)
    for item, v, nums in SUM:
        out('  %-62s %-9s %s' % (item, v, nums))
    with open(os.path.join(HERE, 'followup.txt'), 'w') as fh:
        fh.write('\n'.join(OUT) + '\n')


if __name__ == '__main__':
    main()
