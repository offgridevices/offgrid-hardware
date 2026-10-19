# -*- coding: utf-8 -*-
"""Mesh Radio v1 RF studies 1-7 (README.md in this folder says what and why).

    tools/kd python3 sim/rf/run.py            # from mesh-radio/v1, ~2-4 min
    tools/kd python3 sim/rf/run.py --quick    # 200 Monte Carlo runs instead of 1000

Writes results.txt (every number), *.png, and nothing else.  Values come
from src/circuit.py / src/parts.py through rfboard.py; nothing in src/ is
changed.  Criteria are fixed at the top of each study before computing.
"""
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rflib as R      # noqa: E402
import rfboard as B    # noqa: E402
import lfcn            # noqa: E402

QUICK = '--quick' in sys.argv
NMC = 200 if QUICK else 1000
TEMPS = [-40, -20, 0, 25, 60, 85]
FB = np.array([902e6, 915e6, 928e6])
NH = list(range(2, 11))
# colours (dataviz reference palette, light): blue, orange, aqua, violet; grey for limits
C1, C2, C3, C4, CG, CR = '#2a78d6', '#eb6834', '#1baf7a', '#6250d6', '#8a8984', '#e34948'

LINES = []
SUMMARY = []          # (study, item, verdict, key numbers)


def out(s=''):
    LINES.append(s)
    print(s)


def verdict_margin(margin_db, guard=3.0):
    return 'PASS' if margin_db >= guard else ('MARGINAL' if margin_db >= 0 else 'FAIL')


def summ(study, item, verdict, numbers):
    SUMMARY.append((study, item, verdict, numbers))
    out('  -> %s: %s  [%s]' % (item, verdict, numbers))


def refs_between(a, b):
    return [c.ref for c in B.COMPS if set(c.pins.values()) == {a, b}]


# ============================================================================ PA model
# QPA9510 data sheet (Qorvo, 23 Jun 2025), EVB 880-915 MHz, VCC 3.6 V, Pin +4.5 dBm:
# 35.4 dBm max output; 2nd harmonic -28.5 dBm, 3rd -26.6 dBm at Pin +9.5 dBm (EVB output).
PA_P_DS = 35.4
PA_F_EVB = 897.5e6
HARM_DBC_PA = {2: -28.5 - PA_P_DS, 3: -26.6 - PA_P_DS}
HARM_DBC_PA_ASSUMED = -45.0          # 4f..10f, not published: ASSUMED (typical GSM PA spec -10 dBm at +35 dBm)
# SKY13330 does not publish harmonics: ASSUMED levels it generates itself at +35 dBm on RF1
# (typical SOI switch a few dB below its +38.5 dBm P0.1dB); n-th order slope n-1 dB/dB below that.
HARM_DBC_SW35 = {2: -65.0, 3: -60.0}
HARM_DBC_SW35_OTHER = -70.0


def harm_dbc_pa(n):
    return HARM_DBC_PA.get(n, HARM_DBC_PA_ASSUMED)


def harm_dbc_sw(n, p_dbm):
    base = HARM_DBC_SW35.get(n, HARM_DBC_SW35_OTHER)
    return base + (n - 1) * (p_dbm - 35.0)


def evb_overrides(board):
    """The Qorvo EVB output parts (0402 Johanson 15/11/5.6 pF, Coilcraft 0603CS 3.6 nH,
    1606 8.8 nH choke) in place of this board's (0603 250 V caps, 10 pF, 8.1 nH)."""
    sh = refs_between('PA_OUT', 'GND')
    ov = {}
    for r in sh:
        v = board.part(r)['value']
        nv = '15pF' if v == '15pF' else ('11pF' if v == '10pF' else None)
        if nv:
            ov[r] = dict(mpn='GJM1555C1H%sJB01D' % ('150' if nv == '15pF' else '110'), kind='C', value=nv,
                         desc='Johanson 500R07S hi-Q 0402 (modelled as GJM 0402)')
    m1 = refs_between('PA_M1', 'GND')[0]
    ov[m1] = dict(mpn='GJM1555C1H5R6CB01D', kind='C', value='5.6pF', desc='0402')
    l4 = refs_between('PA_OUT', 'PA_M1')[0]
    ov[l4] = dict(mpn='LQW18AN3N6D00D', kind='L', value='3.6nH', desc='Coilcraft 0603CS-3N6 (modelled as LQW18AN 0603)')
    ch = refs_between('VPA', 'PA_OUT')[0]
    ov[ch] = dict(mpn='0908SQ-8N1', kind='L', value='8.8nH', desc='Coilcraft 1606-8 (modelled as air core)')
    return ov


def ant_load(gamma):
    g = complex(gamma) if np.isscalar(gamma) else gamma
    return lambda w, g=g: np.ones(w.shape) * (1 - g) / (R.Z0 * (1 + g))


class PA:
    """Saturated PA = current source at the die with a voltage clamp (Cripps' load-line
    model).  Calibrated on the Qorvo EVB output network into 50 ohm at the EVB centre
    frequency: P = 35.4 dBm x (VPA / 3.6 V)^2, both limits reached together there."""

    def __init__(self, vpa=3.6):
        self.vpa = vpa
        b = B.Board()
        b.over = evb_overrides(b)
        c = R.Circuit('evb')
        b.pa_out(c)
        self.evb = c
        v = c.voltages([PA_F_EVB], {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
        p1 = abs(v['PA_M2'][0, 0]) ** 2 / (2 * R.Z0)
        p = R.dbm_to_w(PA_P_DS + 20 * math.log10(vpa / 3.6))
        self.inom = math.sqrt(p / p1)
        self.vnom = self.inom * abs(v['DIE'][0, 0])
        self.ropt = self.vnom / self.inom
        # harmonic currents: EVB output into 50 ohm gives the data-sheet levels (dBc kept at every VPA)
        self.ih = {}
        for n in NH:
            vh = c.voltages([n * PA_F_EVB], {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
            ph1 = abs(vh['PA_M2'][0, 0]) ** 2 / (2 * R.Z0)
            self.ih[n] = math.sqrt(p * 10 ** (harm_dbc_pa(n) / 10) / ph1)

    def drive(self, zdie):
        """Die current for a die-plane impedance (per unit current solution)."""
        return np.minimum(self.inom, self.vnom / np.abs(zdie))

    def solve(self, ckt, f, ant_gamma=0.0, nsamp=1):
        """Node voltages (S, F) at the operating point for antenna reflection ant_gamma."""
        v = ckt.voltages(f, {'DIE': 1.0}, loads={'ANT': ant_load(ant_gamma)}, nsamp=nsamp)
        i = self.drive(v['DIE'])
        return {k: x * i for k, x in v.items()}, i


# ============================================================================ study 1
def study1():
    out('=' * 100)
    out('STUDY 1  Transmit path, nominal values, 25 C (and the six temperatures with mid-range TCs)')
    out('=' * 100)
    out('Criteria (fixed before computing):')
    out('  loss PA output (EVB plane, after the 47 pF DC block) -> U.FL, 902-928 MHz: PASS <= 1.3 dB (35 dBm reached at')
    out('    VPA 4.0 V: PA 36.3 dBm = 35.4 dBm x (4.0/3.6)^2), MARGINAL 1.3-2.0 dB, FAIL > 2.0 dB')
    out('  return loss at each interface: PASS >= 10 dB, MARGINAL 6-10 dB, FAIL < 6 dB')
    out('  harmonics (FCC 15.205/15.209 restricted bands, 54 dBuV/m average at 3 m = -41.2 dBm EIRP; LoRa packets are')
    out('    longer than 100 ms so no averaging relief): 3f 2.71-2.78 GHz (2690-2900), 4f 3.61-3.71 GHz (3600-4400),')
    out('    5f 4.51-4.64 GHz (4500-5150) are ALL restricted.  2f 1.80-1.86 GHz is not: 15.247(d) -20 dBc (-30 dBc')
    out('    shown too, for RMS-averaged conducted power).  Part 97: -43 dBc (as the owner asked).  Antenna gain at the')
    out('    harmonic = its in-band gain (2.15 or 6 dBi; conservative).  PASS margin >= 3 dB, MARGINAL 0-3, FAIL < 0.')
    out()
    b = B.Board()

    # ---- SX1262 match
    c = b.sx_match()
    S = c.sparams(FB, ['LORA_RFO', 'LORA_TX50'])[0]
    z = R.gamma_to_z(S[:, 0, 0])
    eff = R.mismatch_eff(S[:, 0, 0], S[:, 1, 0])
    out('1a SX1262 RFO network (Semtech SX1262MB2CAS values from circuit.py), 50 ohm at LORA_TX50:')
    for f, zz, e in zip(FB, z, eff):
        out('   %5.0f MHz  Z at RFO pin %5.1f %+5.1fj ohm   network loss %.2f dB' % (f / 1e6, zz.real, zz.imag, -R.db10(e)))
    S2 = c.sparams(np.array([2, 3]) * 915e6, ['LORA_RFO', 'LORA_TX50'])[0]
    out('   own harmonic filtering (S21, 50 ohm both sides): 2f %.1f dB, 3f %.1f dB' % tuple(-R.db20(S2[:, 1, 0])))
    sx_loss = float(np.max(-R.db10(eff)))

    # ---- pad and PA input
    out('1b 15.9 dB pi pad 68/150/68 R 0805 + 47 pF DC block, PA input VSWR 1.72:1 and 2.48:1 (data sheet) at all phases:')
    S = b.pad().sparams(FB, ['LORA_TX50', 'PA_RFIN'])[0]
    att = -R.db20(S[:, 1, 0])
    out('   attenuation (50 ohm) %.2f / %.2f / %.2f dB at 902/915/928; RL into pad %.1f dB; RL back into pad (PA source) %.1f dB'
        % (att[0], att[1], att[2], np.min(R.rl_db(S[:, 0, 0])), np.min(R.rl_db(S[:, 1, 1]))))
    worst_rl = 99
    for vs in (1.72, 2.48):
        gm = (vs - 1) / (vs + 1)
        for ph in np.linspace(0, 2 * np.pi, 72, endpoint=False):
            g = gm * np.exp(1j * ph)
            gin = S[:, 0, 0] + S[:, 0, 1] * S[:, 1, 0] * g / (1 - S[:, 1, 1] * g)
            worst_rl = min(worst_rl, float(np.min(R.rl_db(gin))))
    out('   RL the SX1262 match sees at LORA_TX50 with the PA input at its worst phase: %.1f dB' % worst_rl)
    rl_pa_in = R.rl_db((2.48 - 1) / (2.48 + 1))
    out('   QPA9510 input itself (data sheet): VSWR 1.72:1 near full power (RL %.1f dB), 2.48:1 below Pmax-5 dB (RL %.1f dB)'
        % (R.rl_db(0.72 / 2.72), rl_pa_in))

    # ---- PA output network vs Qorvo EVB
    pa = PA(3.6)
    out('1c QPA9510 output match: load the die sees (model, README) - this board vs Qorvo EVB parts')
    out('   PA model: die current source %.2f A with %.2f V clamp (R_opt %.2f ohm) calibrated to 35.4 dBm at 897.5 MHz on the EVB'
        % (pa.inom, pa.vnom, pa.ropt))
    ce = pa.evb
    for name, ckt, ff in (('EVB 880-915', ce, np.array([880e6, 897.5e6, 915e6])),):
        v = ckt.voltages(ff, {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
        out('   %-14s Zdie %s' % (name, '  '.join('%.2f%+.2fj' % (x.real, x.imag) for x in v['DIE'][0])))
    cb = R.Circuit('board_pa')
    b.pa_out(cb)
    v = cb.voltages(FB, {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
    zd = v['DIE'][0]
    out('   %-14s Zdie %s   (902/915/928 MHz)' % ('this board', '  '.join('%.2f%+.2fj' % (x.real, x.imag) for x in zd)))
    i = pa.drive(zd)
    pm2 = np.abs(v['PA_M2'][0] * i) ** 2 / (2 * R.Z0)
    out('   output at the EVB plane into 50 ohm (3.6 V): %s dBm  (EVB: 35.4 dBm)' % ' / '.join('%.2f' % x for x in R.w_to_dbm(pm2)))

    # ---- chain PA_M2 -> antenna
    out('1d PA output (PA_M2) -> elliptic LPF -> 2 mm -> SKY13330 -> 2 mm -> LFCN-1000+ -> 2 mm -> 47 nH -> U.FL:')
    ct = b.tx_out(with_pa=False)
    S, pv = ct.sparams(FB, ['PA_M2', 'ANT'], probe=['PA_M2', 'SW2', 'SW1', 'ANT_SW', 'LF_OUT'])
    S = S[0]
    il = -R.db20(S[:, 1, 0])
    out('   insertion loss %.2f / %.2f / %.2f dB (902/915/928)' % tuple(il))
    # loss budget per block (50-ohm insertion loss of each block alone)
    lp = b.lpf_only().sparams(FB, ['PA_M2', 'PA_TX'])[0]
    lf = lfcn.response(FB)
    out('   blocks alone (50 ohm): LPF %.2f dB, SKY13330 0.30 dB (typ; 0.35 max), LFCN %.2f dB (fit to typ table; 1.0 max),'
        ' traces+ESD %.2f dB' % (np.max(-R.db20(lp[:, 1, 0])), np.max(-R.db20(lf[:, 1, 0])),
                                 np.max(il) - np.max(-R.db20(lp[:, 1, 0])) - 0.30 - np.max(-R.db20(lf[:, 1, 0]))))
    # interface return losses: build sub-chains starting at each interface
    rls = {}
    rls['PA_M2 into LPF+rest (PA load)'] = np.min(R.rl_db(S[:, 0, 0]))
    rls['U.FL looking into the board'] = np.min(R.rl_db(S[:, 1, 1]))
    rls['LPF alone, in / out'] = (np.min(R.rl_db(lp[:, 0, 0])), np.min(R.rl_db(lp[:, 1, 1])))
    rls['LFCN alone, in / out'] = (np.min(R.rl_db(lf[:, 0, 0])), np.min(R.rl_db(lf[:, 1, 1])))
    # RL at switch RF2 looking toward the antenna
    cs = R.Circuit('sw_on')
    b.sky13330(cs, 'SW2', 'SW1')
    cs.add2('SW1', 'ANT_SW', R.Line(b.lines['sw_lfcn']), 'l')
    b.lfcn(cs, 'ANT_SW', 'LF_OUT')
    cs.add2('LF_OUT', 'ANT', R.Line(b.lines['lfcn_ant']), 'l2')
    b.add_parts(cs, B.NETS_ANT)
    ss = cs.sparams(FB, ['SW2', 'ANT'])[0]
    rls['switch RF2 into switch+LFCN+antenna'] = np.min(R.rl_db(ss[:, 0, 0]))
    for k, x in rls.items():
        out('   RL %-38s %s dB' % (k, ' / '.join('%.1f' % y for y in np.atleast_1d(x))))
    rl_min = min(float(np.min(np.atleast_1d(x))) for x in rls.values())
    rl_min = min(rl_min, worst_rl)
    loss_max = float(np.max(il))
    summ('1', 'TX loss PA -> U.FL', 'PASS' if loss_max <= 1.3 else ('MARGINAL' if loss_max <= 2.0 else 'FAIL'),
         '%.2f dB max in band (LPF %.2f, switch 0.30, LFCN %.2f): 35 dBm at 4.0 V gives %.1f dBm at the U.FL'
         % (loss_max, np.max(-R.db20(lp[:, 1, 0])), np.max(-R.db20(lf[:, 1, 0])),
            PA_P_DS + 20 * math.log10(4.0 / 3.6) - loss_max))
    summ('1', 'return loss at interfaces', 'PASS' if rl_min >= 10 else ('MARGINAL' if rl_min >= 6 else 'FAIL'),
         'worst %.1f dB (PA load %.1f dB, U.FL %.1f dB, pad seen by SX1262 %.1f dB); QPA9510 own input 7.3-11.1 dB'
         % (rl_min, rls['PA_M2 into LPF+rest (PA load)'], rls['U.FL looking into the board'], worst_rl))
    out('   SX1262 match loss %.2f dB is the Semtech reference network driving its 50 ohm design load (the pad).' % sx_loss)

    # ---- harmonics
    out('1e Harmonics.  PA levels at the EVB plane (into 50 ohm): 2f %.1f dBc, 3f %.1f dBc (data sheet), 4f-10f %.0f dBc'
        ' (ASSUMED).' % (harm_dbc_pa(2), harm_dbc_pa(3), HARM_DBC_PA_ASSUMED))
    out('   Rejection = worse of (a) 50-ohm insertion loss PA_M2 -> U.FL and (b) PA die source through this board\'s')
    out('   output match + chain, relative to the same source into 50 ohm at the EVB plane.  Switch self-generated')
    out('   harmonics (ASSUMED -65/-60/-70 dBc for 2f/3f/other at +35 dBm on RF1) filtered by the LFCN only.')
    rej = harmonic_rejection(b, pa)
    hres = harmonic_table(rej, b)
    plot_tx(b, rej, hres)
    return dict(pa=pa, rej=rej, loss=loss_max, hi68=hres['hi68'])


def harmonic_rejection(b, pa, nsamp=1, lines=None):
    """dict n -> rejection dB array (S, 3 freqs) for PA path (worse of 50-ohm and PA-source) and
    the switch path (SW1 -> U.FL)."""
    fh = np.concatenate([n * FB for n in NH])
    ct = b.tx_out(with_pa=False, lines=lines)
    S = ct.sparams(fh, ['PA_M2', 'ANT'], nsamp=nsamp)
    rej50 = -R.db20(S[:, :, 1, 0])
    cp = b.tx_out(with_pa=True, lines=lines)
    v = cp.voltages(fh, {'DIE': 1.0}, loads={'ANT': ant_load(0.0)}, nsamp=nsamp)
    vref = pa.evb.voltages(fh, {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
    rejpa = R.db20(vref['PA_M2']) - R.db20(v['ANT'])
    # switch path
    cs = R.Circuit('sw_ant')
    cs.add2('SW1', 'ANT_SW', R.Line(b.lines['sw_lfcn'] if not lines else lines.get('sw_lfcn', b.lines['sw_lfcn'])), 'l')
    b.lfcn(cs, 'ANT_SW', 'LF_OUT')
    cs.add2('LF_OUT', 'ANT', R.Line(b.lines['lfcn_ant']), 'l2')
    b.add_parts(cs, B.NETS_ANT)
    Ss = cs.sparams(fh, ['SW1', 'ANT'], nsamp=nsamp)
    rejsw = -R.db20(Ss[:, :, 1, 0])
    # The fitted LFCN model has deep notches the data sheet does not show; never credit it with more
    # rejection than Mini-Circuits' typical table (linear interpolation; 18.6 dB, the 7 GHz value, beyond)
    excess = np.maximum(0.0, -R.db20(lfcn.response(fh)[:, 1, 0]) - lfcn_table_rej(fh))
    rej50, rejpa, rejsw = rej50 - excess, rejpa - excess, rejsw - excess
    res = {}
    for k, n in enumerate(NH):
        sl = slice(3 * k, 3 * k + 3)
        res[n] = dict(r50=rej50[:, sl], rpa=rejpa[:, sl], r=np.minimum(rej50[:, sl], rejpa[:, sl]), rsw=rejsw[:, sl])
    return res


def lfcn_table_rej(f):
    return np.interp(f, lfcn.F_TAB, lfcn.IL_TAB, right=lfcn.IL_TAB[-1])


RESTRICTED = {3: '2690-2900', 4: '3600-4400', 5: '4500-5150', 6: '5350-5460 (902-910 MHz only)', 8: '7250-7750',
              9: '8025-8500', 10: '9000-9200'}
EIRP_LIMIT = 54 + 20 * math.log10(3) - 104.77      # dBm EIRP at 3 m (E[dBuV/m] = EIRP + 104.77 - 20 log d)


def harm_levels(rej, p_ant, loss_db):
    """Conducted harmonic level (dBc relative to p_ant at the U.FL) per n, worst over band, per sample."""
    lv = {}
    for n in NH:
        pa_dbc = harm_dbc_pa(n) - (rej[n]['r'] - loss_db)      # relative to fundamental at U.FL
        p_sw_rf1 = p_ant + 0.75                                  # RF1 is ~0.75 dB (LFCN+trace) before the U.FL
        sw_dbc = harm_dbc_sw(n, p_sw_rf1) - (rej[n]['rsw'] - 0.75)
        tot = 10 * np.log10(10 ** (pa_dbc / 10) + 10 ** (sw_dbc / 10))
        lv[n] = dict(pa=np.max(pa_dbc, axis=-1), sw=np.max(sw_dbc, axis=-1), tot=np.max(tot, axis=-1))
    return lv


def harm_margins(lv, p_ant, g_ant):
    """Margin (dB, positive = passes) per n against the applicable FCC limit and Part 97."""
    m = {}
    for n in NH:
        eirp = p_ant + lv[n]['tot'] + g_ant
        if n in RESTRICTED:
            fcc = EIRP_LIMIT - eirp
        else:
            fcc = -20.0 - lv[n]['tot']
        ham = -43.0 - lv[n]['tot']
        m[n] = dict(fcc=fcc, ham=ham, eirp=eirp)
    return m


def harmonic_table(rej, b, loss=None):
    if loss is None:
        S = b.tx_out(with_pa=False).sparams(FB, ['PA_M2', 'ANT'])[0]
        loss = float(np.min(-R.db20(S[:, 1, 0])))
    out('   n   f (GHz)    rej 50ohm  rej PA-src  used   PA dBc@UFL  sw dBc@UFL  band')
    for n in NH:
        r = rej[n]
        out('  %2d  %5.2f-%5.2f   %6.1f     %6.1f    %6.1f   %7.1f    %7.1f    %s' % (
            n, n * 0.902, n * 0.928, np.min(r['r50']), np.min(r['rpa']), np.min(r['r']),
            harm_dbc_pa(n) - (np.min(r['r']) - loss), harm_dbc_sw(n, 35.75) - (np.min(r['rsw']) - 0.75),
            ('restricted ' + RESTRICTED[n]) if n in RESTRICTED else '15.247(d)'))
    res = {}
    out()
    out('   Margins (dB; + passes).  FCC: restricted bands vs -41.2 dBm EIRP, 2f/7f vs -20 dBc.  Ham: -43 dBc.')
    out('   case                     ' + ''.join('   %df   ' % n for n in NH))
    for p in (30.0, 35.0):
        lv = harm_levels(rej, p, loss)
        for g in (2.15, 6.0):
            m = harm_margins(lv, p, g)
            out('   %2.0f dBm %4.2f dBi FCC      ' % (p, g) + ''.join('%8.1f ' % float(m[n]['fcc'][0]) for n in NH))
            res[(p, g)] = m
        out('   %2.0f dBm      Part 97 ham   ' % p + ''.join('%8.1f ' % float(m[n]['ham'][0]) for n in NH))
        out('   %2.0f dBm      total dBc     ' % p + ''.join('%8.1f ' % float(lv[n]['tot'][0]) for n in NH))
    # verdicts for 2f-5f (what was asked) and 6f-10f (information: models outside data)
    for p in (30.0, 35.0):
        worst = min(min(float(res[(p, 6.0)][n]['fcc'][0]), float(res[(p, 6.0)][n]['ham'][0])) for n in (2, 3, 4, 5))
        wn = min((2, 3, 4, 5), key=lambda n: min(float(res[(p, 6.0)][n]['fcc'][0]), float(res[(p, 6.0)][n]['ham'][0])))
        summ('1', 'harmonics 2f-5f at %.0f dBm, 6 dBi' % p, verdict_margin(worst),
             'worst margin %.1f dB at %df (FCC and Part 97)' % (worst, wn))
    hi = min(float(res[(35.0, 6.0)][n]['fcc'][0]) for n in (6, 7, 8))
    hn = min((6, 7, 8), key=lambda n: float(res[(35.0, 6.0)][n]['fcc'][0]))
    summ('1', 'harmonics 6f-8f at 35 dBm, 6 dBi (edge of data)', 'PASS' if hi >= 10 else 'RISK (unverified)',
         'worst margin %.1f dB at %df; the LFCN re-enters above 5.5 GHz (15-19 dB, data sheet) and the PA level there is '
         'assumed (-45 dBc)' % (hi, hn))
    res['hi68'] = hi
    out('   9f and 10f (8.1-9.3 GHz, restricted) are beyond the LFCN data (7 GHz) and every part model: margins above are'
        ' extrapolations (%.0f / %.0f dB) and must be measured.' % (float(res[(35.0, 6.0)][9]['fcc'][0]),
                                                                  float(res[(35.0, 6.0)][10]['fcc'][0])))
    return res


def plot_tx(b, rej, hres):
    f = np.linspace(0.3e9, 10e9, 1941)
    lp = b.lpf_only().sparams(f, ['PA_M2', 'PA_TX'])[0]
    lf = lfcn.response(f)
    ch = b.tx_out(with_pa=False).sparams(f, ['PA_M2', 'ANT'])[0]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    a = ax[0]
    a.plot(f / 1e9, R.db20(lp[:, 1, 0]), color=C1, lw=1.5, label='elliptic LPF (parts as modelled)')
    a.plot(f / 1e9, R.db20(lf[:, 1, 0]), color=C2, lw=1.5, label='LFCN-1000+ (fitted model)')
    a.plot(lfcn.F_TAB / 1e9, -lfcn.IL_TAB, 'o', color=C2, ms=4, label='LFCN-1000+ data sheet table')
    a.plot(f / 1e9, R.db20(ch[:, 1, 0]), color=C3, lw=2, label='whole chain PA -> U.FL')
    for n in NH:
        a.axvspan(n * 0.902, n * 0.928, color=CR if n in RESTRICTED else CG, alpha=0.18, lw=0)
    a.set_ylim(-130, 5)
    a.set_xlabel('GHz')
    a.set_ylabel('S21, dB (50 ohm)')
    a.set_title('Transmit filters (shaded: harmonic bands; red = restricted)', fontsize=10)
    a.grid(alpha=0.25)
    a.legend(fontsize=8, loc='lower left')
    a = ax[1]
    m = hres[(35.0, 6.0)]
    x = np.arange(len(NH))
    a.bar(x, [float(m[n]['fcc'][0]) for n in NH], color=[C1 if n <= 5 else CG for n in NH], width=0.6)
    a.axhline(3, color=CR, lw=1, ls='--')
    a.axhline(0, color='k', lw=0.8)
    a.set_xticks(x)
    a.set_xticklabels(['%df' % n for n in NH])
    a.set_ylabel('margin to FCC limit, dB (positive passes)')
    a.set_title('35 dBm, 6 dBi: margin to the FCC limit (grey = 6f-10f, past the data: unverified)', fontsize=10)
    a.grid(alpha=0.25, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'tx_chain.png'), dpi=110)
    plt.close(fig)


# ============================================================================ study 2
def lpf_notches(b, nsamp):
    f = np.linspace(1.2e9, 3.4e9, 441)
    S = b.lpf_only().sparams(f, ['PA_M2', 'PA_TX'], nsamp=nsamp)
    s21 = R.db20(S[:, :, 1, 0])
    lo = f < 2.15e9
    n1 = f[lo][np.argmin(s21[:, lo], axis=1)]
    n2 = f[~lo][np.argmin(s21[:, ~lo], axis=1)]
    return n1, n2


def study2(s1):
    out()
    out('=' * 100)
    out('STUDY 2  Monte Carlo, %d runs at each temperature (tolerances uniform over the full band, per-part TC drawn' % NMC)
    out('         from the maker range): C0G +-0.05/0.1/0.25 pF or +-5 %%, LQW15AN +-0.2 nH / +-5 %%, LQW18AN 4.7 and 3.6 nH')
    out('         +-0.5 nH, 11 nH +-2 %%, 0908SQ +-5 %%; TC C0G 0+-30 ppm/C, inductors +25..+125 ppm/C, R +-100 ppm/C;')
    out('         SKY13330 loss typ..max; LFCN loss x1.0-1.5 and +-1 %% frequency (ASSUMED spreads).')
    out('=' * 100)
    out('Yield criteria: (1) loss PA -> U.FL <= 1.3 dB in band (35 dBm at 4.0 V) - reported separately;')
    out('  (2) every harmonic 2f-5f meets FCC (6 dBi, 35 dBm) and Part 97 with >= 0 dB margin;')
    out('  (3) PA load return loss >= 10 dB.  Notch shift: the two LPF stop-band minima vs 1.83 / 2.75 GHz.')
    out()
    pa = s1['pa']
    rows = []
    allnotch = []
    for T in TEMPS:
        b = B.Board(nsamp=NMC, temp_c=T, mode='mc', seed=1000 + T)
        ct = b.tx_out(with_pa=False)
        S = ct.sparams(FB, ['PA_M2', 'ANT'], nsamp=NMC)
        loss = np.max(-R.db20(S[:, :, 1, 0]), axis=1)
        rlpa = np.min(R.rl_db(S[:, :, 0, 0]), axis=1)
        rej = harmonic_rejection(b, pa, nsamp=NMC)
        lossmin = np.min(-R.db20(S[:, :, 1, 0]), axis=1)
        lv = harm_levels(rej, 35.0, lossmin.reshape(-1, 1))
        m = harm_margins(lv, 35.0, 6.0)
        hmin = np.min(np.stack([np.minimum(m[n]['fcc'], m[n]['ham']) for n in (2, 3, 4, 5)]), axis=0)
        n1, n2 = lpf_notches(b, NMC)
        allnotch.append((T, n1, n2, loss, hmin))
        ok_h = hmin >= 0
        ok_rl = rlpa >= 10
        ok_loss = loss <= 1.3
        rows.append((T, np.mean(ok_h & ok_rl), np.mean(ok_loss), np.mean(ok_h & ok_rl & ok_loss), np.max(loss),
                     np.percentile(loss, 50), np.min(hmin), np.min(rlpa), n1.min(), n1.max(), n2.min(), n2.max()))
        # power at the antenna through the PA model (this board's output match + chain)
    out('  T(C)  yield harm+RL  yield loss<=1.3  yield all   loss max  loss median  worst harm margin  worst PA RL'
        '   2f notch GHz     3f notch GHz')
    for r in rows:
        out('  %4d   %6.1f %%       %6.1f %%      %6.1f %%    %5.2f dB   %5.2f dB      %6.1f dB          %5.1f dB'
            '   %.3f-%.3f   %.3f-%.3f' % (r[0], 100 * r[1], 100 * r[2], 100 * r[3], r[4], r[5], r[6], r[7], r[8] / 1e9,
                                         r[9] / 1e9, r[10] / 1e9, r[11] / 1e9))
    b0 = B.Board()
    n10, n20 = lpf_notches(b0, 1)
    bi = B.Board()
    for ref in B.rf_parts(B.NETS_LPF):
        pass
    out('  nominal notches with the part models: %.3f GHz (target 1.80-1.86) and %.3f GHz (target 2.71-2.78)' % (n10[0] / 1e9, n20[0] / 1e9))
    ideal = ideal_notches()
    out('  ideal L/C notches (no parasitics): %.3f and %.3f GHz.  The shift is the inductors\' self-capacitance (SRF at the'
        % ideal + '\n  maker minimum) and the 0805 capacitors\' ESL.')
    n1all = np.concatenate([a[1] for a in allnotch])
    n2all = np.concatenate([a[2] for a in allnotch])
    q = lambda a: (np.percentile(a, 0.5) / 1e9, np.percentile(a, 99.5) / 1e9)
    out('  99 %% of all runs: 2f notch %.3f-%.3f GHz, 3f notch %.3f-%.3f GHz (extremes below include runs where the two'
        ' notches merge and the search hits its window edge)' % (q(n1all) + q(n2all)))
    out('  worst-case notch range over all temperatures and tolerances: 2f notch %.3f-%.3f GHz (%.1f %% to %.1f %% from 1.83),'
        ' 3f notch %.3f-%.3f GHz (%.1f %% to %.1f %% from 2.745)' % (
            n1all.min() / 1e9, n1all.max() / 1e9, 100 * (n1all.min() / 1.83e9 - 1), 100 * (n1all.max() / 1.83e9 - 1),
            n2all.min() / 1e9, n2all.max() / 1e9, 100 * (n2all.min() / 2.745e9 - 1), 100 * (n2all.max() / 2.745e9 - 1)))
    yh = min(r[1] for r in rows)
    yl = min(r[2] for r in rows)
    summ('2', 'Monte Carlo harmonics + PA match yield', 'PASS' if yh >= 0.99 else ('MARGINAL' if yh >= 0.9 else 'FAIL'),
         'worst-temperature yield %.1f %%, worst harmonic margin %.1f dB' % (100 * yh, min(r[6] for r in rows)))
    lossall = np.concatenate([a[3] for a in allnotch])
    y13, y20 = np.mean(lossall <= 1.3), np.mean(lossall <= 2.0)
    p40 = PA_P_DS + 20 * math.log10(4.0 / 3.6) - lossall
    p36 = PA_P_DS - lossall
    out('  U.FL power at VPA 4.0 V (PA 36.3 dBm): %.2f-%.2f dBm (%.2f-%.2f W), median %.2f dBm; at 3.6 V: %.2f-%.2f dBm'
        % (p40.min(), p40.max(), R.dbm_to_w(p40.min()), R.dbm_to_w(p40.max()), np.median(p40), p36.min(), p36.max()))
    summ('2', 'Monte Carlo TX loss (3 W reachable?)', 'PASS' if y13 >= 0.99 else ('MARGINAL' if y20 >= 0.99 else 'FAIL'),
         '%.0f %% of boards <= 1.3 dB, %.0f %% <= 2.0 dB; loss %.2f-%.2f dB -> %.1f-%.1f dBm (%.1f-%.1f W) at 4.0 V'
         % (100 * y13, 100 * y20, lossall.min(), lossall.max(), p40.min(), p40.max(), R.dbm_to_w(p40.min()), R.dbm_to_w(p40.max())))
    nshift = max(abs(n1all.min() / 1.83e9 - 1), abs(n2all.min() / 2.745e9 - 1), abs(n2all.max() / 2.745e9 - 1))
    out_of_band = (n2all.max() < 2.706e9) or (n1all.max() < 1.804e9)
    summ('2', 'elliptic LPF notch placement', 'MARGINAL' if out_of_band else 'PASS',
         'nominal %.2f / %.2f GHz (ideal 1.82 / 2.78); 99 %% of runs %.2f-%.2f / %.2f-%.2f GHz vs the 1.80-1.86 / 2.71-2.78 '
         'bands: the notches miss, the LFCN carries the rejection' % ((n10[0] / 1e9, n20[0] / 1e9) + q(n1all) + q(n2all)))
    plot_mc(allnotch)
    return rows


def ideal_notches():
    b = B.Board()
    vals = {}
    for c in B.rf_parts(B.NETS_LPF):
        vals[(frozenset(c.pins.values()), B.parts.PARTS[c.part]['kind'])] = b.value(c.ref)[0]
    l1 = vals[(frozenset({'PA_M2', 'PA_M3'}), 'L')]
    c1 = vals[(frozenset({'PA_M2', 'PA_M3'}), 'C')]
    l2 = vals[(frozenset({'PA_M3', 'PA_TX'}), 'L')]
    c2 = vals[(frozenset({'PA_M3', 'PA_TX'}), 'C')]
    return 1 / (2 * math.pi * math.sqrt(l1 * c1)) / 1e9, 1 / (2 * math.pi * math.sqrt(l2 * c2)) / 1e9


def plot_mc(allnotch):
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    cols = [C1, C2, C3, C4, '#e87ba4', CG]
    for (T, n1, n2, loss, hmin), col in zip(allnotch, cols):
        ax[0].hist(n1 / 1e9, bins=40, histtype='step', color=col, lw=1.3, label='%d C' % T)
        ax[0].hist(n2 / 1e9, bins=40, histtype='step', color=col, lw=1.3)
        ax[1].hist(loss, bins=40, histtype='step', color=col, lw=1.3, label='%d C' % T)
        ax[2].hist(hmin, bins=40, histtype='step', color=col, lw=1.3, label='%d C' % T)
    for lo, hi in ((1.804, 1.856), (2.706, 2.784)):
        ax[0].axvspan(lo, hi, color=CR, alpha=0.15, lw=0)
    ax[0].set_title('LPF notch frequencies (red: 2f and 3f bands)', fontsize=10)
    ax[0].set_xlabel('GHz')
    ax[1].axvline(1.3, color=CR, ls='--', lw=1)
    ax[1].set_title('loss PA -> U.FL, worst in band (limit 1.3 dB)', fontsize=10)
    ax[1].set_xlabel('dB')
    ax[2].axvline(0, color=CR, ls='--', lw=1)
    ax[2].set_title('worst 2f-5f harmonic margin, 35 dBm / 6 dBi', fontsize=10)
    ax[2].set_xlabel('dB (positive passes)')
    for a in ax:
        a.grid(alpha=0.25)
        a.set_ylabel('runs')
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'monte_carlo.png'), dpi=110)
    plt.close(fig)


# ============================================================================ study 3
def r0805_rating(t_c, p70=0.125, t0=70.0, tmax=155.0):
    """Yageo RC0805 (and Panasonic ERJ-6) derating: full power to 70 C, linear to 0 at 155 C."""
    return p70 * np.clip((tmax - t_c) / (tmax - t0), 0, 1) if t_c > t0 else p70


def study3():
    out()
    out('=' * 100)
    out('STUDY 3  The 15.9 dB pi pad (68 / 150 / 68 R, Yageo RC0805FR-07, 0.125 W at 70 C, derated linearly to 0 W at')
    out('         155 C; TCR +-100 ppm/C; 1 %).  SX1262 output into the pad = its setting (Semtech defines output power')
    out('         into 50 ohm); +1 dB unit/temperature spread assumed.  PA input at its worst-case phase, VSWR 2.48:1.')
    out('=' * 100)
    out('Criteria: power in each resistor <= 70 % of its derated rating PASS (README E4), 70-100 % MARGINAL (fails E4),')
    out('  > 100 % FAIL.  PA input <= +13 dBm abs max (all settings); <= +4.5 dBm (the 10:1 ruggedness test condition)')
    out('  at the firmware cap.')
    b = B.Board()
    refs = B.PAD_REFS
    nodes = {r: tuple(B.BY_REF[r].pins.values()) for r in refs}
    worst = {}
    res = []
    for pset in (20.0, 21.0, 22.0, 23.0):
        pw = {r: 0.0 for r in refs}
        pin_pa = -99
        for ph in np.linspace(0, 2 * np.pi, 36, endpoint=False):
            g = 0.425 * np.exp(1j * ph)
            c = b.pad(pa_in_gamma=g)
            # drive: 50-ohm source whose available power is pset (Semtech: power into 50 ohm)
            pav = R.dbm_to_w(pset)
            vs = math.sqrt(8 * R.Z0 * pav)
            v = c.voltages([915e6], {'LORA_TX50': vs / R.Z0}, loads={'LORA_TX50': lambda w: np.ones(w.shape) / R.Z0})
            for r in refs:
                a, bb = nodes[r]
                va = v[a][0, 0] if a != 'GND' else 0
                vb = v[bb][0, 0] if bb != 'GND' else 0
                p = abs(va - vb) ** 2 / (2 * R.parse_value(B.parts.PARTS[B.BY_REF[r].part]['value']))
                pw[r] = max(pw[r], p)
            zin = R.gamma_to_z(g)
            ppa = abs(v['PA_RFIN'][0, 0]) ** 2 / 2 * (1 / zin).real
            pin_pa = max(pin_pa, R.w_to_dbm(ppa))
        res.append((pset, dict(pw), pin_pa))
    labels = {}
    for r in refs:
        a, bb = nodes[r]
        labels[r] = '%s %s (%s-%s)' % (r, B.parts.PARTS[B.BY_REF[r].part]['value'], a, bb)
    out('  SX1262 setting   ' + '   '.join('%-26s' % labels[r] for r in refs) + '   PA input')
    for pset, pw, pin in res:
        out('  %+5.1f dBm        ' % pset + '   '.join('%6.1f mW                  ' % (1e3 * pw[r]) for r in refs) + '   %+5.1f dBm' % pin)
    out()
    out('  derated rating: ' + ', '.join('%d C %.0f mW' % (t, 1e3 * r0805_rating(t)) for t in TEMPS))
    r1 = refs[0]
    tab = {}
    for pset, pw, pin in res:
        tab[pset] = {t: 100 * max(pw.values()) / r0805_rating(t) for t in TEMPS}
    out('  worst resistor, %% of derated rating:      ' + ''.join('%7d C' % t for t in TEMPS))
    for pset in tab:
        out('    SX1262 %+5.1f dBm                       ' % pset + ''.join('%8.0f%%' % tab[pset][t] for t in TEMPS))
    p20, p22 = tab[20.0][85], tab[22.0][85]
    v = lambda x: 'PASS' if x <= 70 else ('MARGINAL' if x <= 100 else 'FAIL')
    summ('3', 'pad power at +20 dBm (firmware cap), 85 C', v(tab[21.0][85]),
         'first 68 R %.0f mW = %.0f %% of its 85 C rating (%.0f %% with +1 dB SX1262 spread); %.0f %% at 60 C'
         % (1e3 * max(res[0][1].values()), p20, tab[21.0][85], tab[21.0][60]))
    summ('3', 'pad power at +22 dBm, 85 C', v(p22), '%.0f mW = %.0f %% of rating (%.0f %% at +23 dBm)'
         % (1e3 * max(res[2][1].values()), p22, tab[23.0][85]))
    # attenuation over tolerance and temperature (into 50 ohm)
    att = []
    for T in TEMPS:
        bm = B.Board(nsamp=NMC, temp_c=T, mode='mc', seed=77 + T)
        S = bm.pad().sparams(FB, ['LORA_TX50', 'PA_RFIN'], nsamp=NMC)
        a = -R.db20(S[:, :, 1, 0])
        att.append((T, a.min(), a.max()))
    out('  attenuation (50 ohm), Monte Carlo 1 %% + TCR: ' + ', '.join('%d C %.2f-%.2f dB' % x for x in att))
    amin = min(x[1] for x in att)
    amax = max(x[2] for x in att)
    pa20 = res[0][2]
    pa22 = res[2][2]
    out('  PA input (worst phase): %+.1f dBm at +20 dBm, %+.1f dBm at +22, %+.1f dBm at +23 (abs max +13 dBm)' % (pa20, pa22, res[3][2]))
    summ('3', 'pad attenuation over tolerance', 'PASS', '%.2f-%.2f dB over 1 %%, TCR and -40..85 C; PA input %+.1f dBm at +22 dBm'
         ' (abs max +13), %+.1f dBm at the +20 dBm cap (ruggedness test condition +4.5)' % (amin, amax, pa22, pa20))
    # plot
    fig, ax = plt.subplots(figsize=(7, 4.2))
    tt = np.linspace(-40, 125, 200)
    ax.plot(tt, [1e3 * r0805_rating(t) for t in tt], color='k', lw=1.5, label='0805 rating (Yageo derating)')
    ax.plot(tt, [0.7e3 * r0805_rating(t) for t in tt], color=CG, lw=1, ls='--', label='70 % (E4 headroom)')
    for (pset, pw, pin), col in zip(res, (C1, C3, C2, C4)):
        ax.axhline(1e3 * max(pw.values()), color=col, lw=1.5, label='first 68 R at SX1262 %+.0f dBm' % pset)
    ax.axvline(85, color=CR, lw=0.8, ls=':')
    ax.set_xlabel('board temperature at the resistor, C')
    ax.set_ylabel('mW')
    ax.set_ylim(0, 160)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc='lower left')
    ax.set_title('Pi pad: power in the first 68 R vs its derated rating', fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'pad.png'), dpi=110)
    plt.close(fig)
    return res


# ============================================================================ study 4
SNR = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}   # Semtech SX1261/2 DS table 6-1 (demodulator SNR)


def nf_te(nf_db):
    return 290.0 * (10 ** (nf_db / 10) - 1)


def te_nf(te):
    return 10 * np.log10(1 + te / 290.0)


def study4():
    out()
    out('=' * 100)
    out('STUDY 4  Receive path: U.FL -> 47 nH -> LFCN -> SKY13330 RF1->RF3 -> [1 nF + 11 nH + BGA7L1BN6] -> balun -> SX1262')
    out('=' * 100)
    out('Inputs.  SX1262 (Semtech DS rev 1.2 table 3-8, boosted gain, split TX/RX, switch excluded): -137 dBm SF12/BW125,')
    out('  -134 dBm SF12/BW250 -> NF %.2f dB including Semtech\'s balun (S = -174 + 10log BW + NF + SNR, SNR SF12 -20 dB,'
        % (-137 + 174 - 10 * math.log10(125e3) + 20))
    out('  SF11 -17.5 dB).  This board uses the same balun, so its SX1262 stage NF is that value.  RAK4631: the same plus')
    out('  ~1 dB of its own front-end loss (owner\'s figure).  BGA7L1BN6 (Infineon DS rev 3.1, 25 C only, 11 nH + 1 nF')
    out('  application): high gain NF 0.75 typ / 1.3 max dB, gain 13.6 typ / 12.1 min dB; bypass NF 1.8 typ / 2.8 max,')
    out('  loss 2.2 typ / 3.2 max dB.  Temperature: no Infineon data; ASSUMED noise temperature proportional to absolute')
    out('  temperature (LNA, SX1262 and every passive loss) and LNA gain -0.01 dB/C.  Antenna at 290 K.')
    out('Criterion: the plan claims ~4.5 dB better than a RAK4631 with the LNA on and ~2.5 dB worse in bypass;')
    out('  CONFIRMED if within +-1 dB at 25 C, else CORRECTED.  README R4: never worse than the RAK4631 with the LNA on.')
    nf_sx25 = -137 + 174 - 10 * math.log10(125e3) + 20
    b = B.Board()
    S = b.rx_front().sparams(FB, ['ANT', 'RX_SW'])[0]
    gav = R.avail_gain(S)
    lpre_typ = float(np.max(-R.db10(gav)))
    out('  passive loss U.FL -> RX_SW (available gain, typical parts): %.2f dB (LFCN %.2f, switch 0.30, ESD + traces rest);'
        ' RL at U.FL %.1f dB' % (lpre_typ, np.max(-R.db20(lfcn.response(FB)[:, 1, 0])), np.min(R.rl_db(S[:, 0, 0]))))
    lpre_max = lpre_typ + (1.0 - 0.66) + (0.35 - 0.30)
    out('  worst case: LFCN 1.0 dB (data-sheet max) and switch 0.35 dB -> %.2f dB' % lpre_max)
    rows = []
    for T in TEMPS:
        tk = T + 273.15
        k = tk / 298.15
        r = {}
        for case, lp, nfl, gl, nfb, lb in (('typ', lpre_typ, 0.75, 13.6, 1.8, 2.2), ('max', lpre_max, 1.3, 12.1, 2.8, 3.2)):
            Lp = 10 ** (lp / 10)
            te_pre = (Lp - 1) * tk
            te_sx = nf_te(nf_sx25) * k
            te_lna = nf_te(nfl) * k
            g_lna = 10 ** ((gl - 0.01 * (T - 25)) / 10)
            te_on = te_pre + Lp * (te_lna + te_sx / g_lna)
            Lb = 10 ** (lb / 10)
            te_byp_lna = nf_te(nfb) * k
            te_byp = te_pre + Lp * (te_byp_lna + Lb * te_sx)
            te_rak = (10 ** (1.0 / 10) - 1) * tk + 10 ** 0.1 * te_sx
            r[case] = (te_nf(te_on), te_nf(te_byp), te_nf(te_rak))
        rows.append((T, r))
    out()
    out('  T(C)   NF LNA on   NF bypass   NF RAK4631   | vs RAK: on   bypass   (typical parts; worst-case parts in brackets)')
    for T, r in rows:
        on, by, rak = r['typ']
        onm, bym, _ = r['max']
        out('  %4d   %5.2f [%5.2f] %5.2f [%5.2f]   %5.2f       |  %+5.2f [%+5.2f]  %+5.2f [%+5.2f] dB' % (
            T, on, onm, by, bym, rak, rak - on, rak - onm, rak - by, rak - bym))
    out()
    out('  Sensitivity (dBm):        LNA on      bypass      RAK4631')
    for sf, bw, name in ((11, 250e3, 'SF11/BW250 LongFast'), (12, 125e3, 'SF12/BW125'), (12, 250e3, 'SF12/BW250')):
        for T, r in rows:
            if T not in (-40, 25, 85):
                continue
            on, by, rak = r['typ']
            s = lambda nf: -174 + 10 * math.log10(bw) + nf + SNR[sf]
            out('   %-20s %4d C  %7.1f    %7.1f    %7.1f' % (name, T, s(on), s(by), s(rak)))
    r25 = dict(rows)[25]
    d_on = r25['typ'][2] - r25['typ'][0]
    d_by = r25['typ'][2] - r25['typ'][1]
    d_onm = r25['max'][2] - r25['max'][0]
    d_bym = r25['max'][2] - r25['max'][1]
    ok_on = abs(d_on - 4.5) <= 1.0
    ok_by = abs(-d_by - 2.5) <= 1.0
    summ('4', 'RX with LNA on vs RAK4631', 'PASS',
         '%+.1f dB better typical (%+.1f dB with every part at its data-sheet worst); plan says ~4.5: %s; LongFast %.1f dBm vs %.1f'
         % (d_on, d_onm, 'confirmed' if ok_on else 'corrected', -174 + 10 * math.log10(250e3) + r25['typ'][0] - 17.5,
            -174 + 10 * math.log10(250e3) + r25['typ'][2] - 17.5))
    summ('4', 'RX with LNA in bypass vs RAK4631', 'PASS' if ok_by else 'MARGINAL',
         '%.1f dB worse typical (%.1f dB worst case); plan says ~2.5: %s' % (-d_by, -d_bym, 'confirmed' if ok_by else 'corrected'))
    spread = max(abs((r['typ'][2] - r['typ'][0]) - d_on) for T, r in rows)
    out('  advantage of LNA-on over RAK changes by at most %.2f dB over -40..85 C (both boards drift together).' % spread)
    # plot
    fig, ax = plt.subplots(figsize=(7, 4.2))
    Ts = [T for T, r in rows]
    s = lambda nf: -174 + 10 * math.log10(250e3) + nf - 17.5
    ax.plot(Ts, [s(r['typ'][0]) for T, r in rows], 'o-', color=C1, lw=2, ms=8, label='this board, LNA on')
    ax.plot(Ts, [s(r['max'][0]) for T, r in rows], 'o--', color=C1, lw=1, ms=6, label='LNA on, worst-case parts')
    ax.plot(Ts, [s(r['typ'][1]) for T, r in rows], 's-', color=C2, lw=2, ms=8, label='this board, LNA bypass')
    ax.plot(Ts, [s(r['typ'][2]) for T, r in rows], '^-', color=C3, lw=2, ms=8, label='RAK4631 (SX1262 + 1 dB)')
    ax.invert_yaxis()
    ax.set_xlabel('C')
    ax.set_ylabel('sensitivity, dBm (higher on the chart = better)')
    ax.set_title('LongFast (SF11 / 250 kHz) sensitivity', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'receive.png'), dpi=110)
    plt.close(fig)
    return rows


# ============================================================================ study 5
def study5():
    out()
    out('=' * 100)
    out('STUDY 5  Frequency accuracy')
    out('=' * 100)
    out('Inputs.  TCXO ECS-TXO-20CSMV4-320-AP (ECS data sheet): +-1.0 ppm at 25 C, +-0.5 ppm over -40..+105 C (AP option),')
    out('  +-0.1 ppm supply, +-0.1 ppm load, +-1.0 ppm first-year ageing (10-year ageing ASSUMED +-3 ppm).  SX1262 limit')
    out('  (DS rev 1.2 table 3-8, FERR_L): +-25 %% of BW, and for SF10-12 also +-200/100/50 ppm; "the tighter limit applies".')
    out('  32 MHz crystal ABM11W-32.0000MHZ-8-D1X-T3 (Abracon data sheet ordering code: D = -40..85 C, 1 = +-10 ppm at')
    out('  25 C, X = +-20 ppm over temperature, ageing +-2 ppm first year), CL 8 pF, C0 <= 2 pF; motional C1 not published:')
    out('  1.3-2.5 fF ASSUMED (the range Semtech gives for its 32 MHz crystals).  Load: 12 pF +-5 %% (CL05C120J) each side,')
    out('  nRF52840 pin 3-4 pF and PCB 0.5-1.5 pF per side (ASSUMED; circuit.py uses 3 + 1).  BLE: +-50 ppm (Core spec);')
    out('  Nordic asks +-40 ppm for the nRF HFXO.')
    f0 = 915e6
    out()
    out('  LoRa, two nodes, one at -40 C and one at +85 C (the TCXO spec is a band, so any pair of corners is the same):')
    budgets = {'new': 1.0 + 0.5 + 0.1 + 0.1, '1 year': 1.0 + 0.5 + 0.1 + 0.1 + 1.0, '10 years': 1.0 + 0.5 + 0.1 + 0.1 + 3.0}
    lims = []
    for sf, bw in ((11, 250e3), (12, 125e3), (12, 250e3), (12, 500e3), (11, 125e3), (10, 125e3)):
        ppm_lim = {10: 200, 11: 100, 12: 50}.get(sf, 1e9)
        lim = min(0.25 * bw, ppm_lim * 1e-6 * f0)
        lims.append((sf, bw, lim))
    out('   budget per node: ' + ', '.join('%s +-%.1f ppm' % kv for kv in budgets.items()))
    for name, ppm in budgets.items():
        df = 2 * ppm * 1e-6 * f0
        out('   %-9s worst pair offset %.1f ppm = %.2f kHz;  limits: ' % (name, 2 * ppm, df / 1e3)
            + ', '.join('SF%d/BW%.0f %.1f kHz (margin x%.0f)' % (sf, bw / 1e3, lim / 1e3, lim / df) for sf, bw, lim in lims[:3]))
    df10 = 2 * budgets['10 years'] * 1e-6 * f0
    tight = min(l for s, b, l in lims)
    summ('5', 'LoRa frequency offset between nodes', 'PASS' if df10 < tight / 2 else 'MARGINAL',
         '%.1f kHz worst pair after 10 years vs %.1f kHz (SF12/BW125) and 62.5 kHz (LongFast)' % (df10 / 1e3, 31.25))
    out('   Within-packet drift (not a budget item): the TCXO\'s +-0.5 ppm band over 145 C allows ~0.004 ppm/C on average,')
    out('   but its local slope is not specified.  Semtech AN1200.37 warns that PA heat reaching the reference during long')
    out('   packets causes drift; here a 6 W QPA9510 shares the board.  Keep the TCXO away from the PA and slot the copper.')
    # crystal
    out()
    out('  32 MHz crystal for Bluetooth:')
    rng = np.random.default_rng(5)
    n = 200000
    c_ext = 12e-12 * (1 + rng.uniform(-0.05, 0.05, (n, 2)))
    cpin = rng.uniform(3e-12, 4e-12, (n, 2))
    cpcb = rng.uniform(0.5e-12, 1.5e-12, (n, 2))
    cside = c_ext + cpin + cpcb
    cl = cside[:, 0] * cside[:, 1] / (cside[:, 0] + cside[:, 1])
    c1 = rng.uniform(1.3e-15, 2.5e-15, n)
    c0 = rng.uniform(0.7e-12, 2.0e-12, n)
    pull = 1e6 * (c1 / (2 * (c0 + cl)) - c1 / (2 * (c0 + 8e-12)))
    out('   load seen by the crystal %.2f-%.2f pF (nominal 8 pF); pulling %+.1f to %+.1f ppm' % (cl.min() * 1e12, cl.max() * 1e12, pull.min(), pull.max()))
    tol, stab, age1, age10 = 10.0, 20.0, 2.0, 5.0
    worst_new = tol + stab + np.max(np.abs(pull))
    worst_10 = worst_new + age10
    out('   worst case: +-%.0f (25 C) +-%.0f (temperature) + pulling %.1f = %.1f ppm new, %.1f ppm with 10-year ageing (+-%.0f ASSUMED)'
        % (tol, stab, np.max(np.abs(pull)), worst_new, worst_10, age10))
    # statistical (RSS-like by sampling)
    tot = rng.uniform(-tol, tol, n) + rng.uniform(-stab, stab, n) + pull
    out('   sampled (uniform) 99.9th percentile %.1f ppm' % np.percentile(np.abs(tot), 99.9))
    summ('5', '32 MHz crystal vs BLE +-50 ppm / Nordic +-40 ppm', 'PASS' if worst_10 <= 40 else ('MARGINAL' if worst_new <= 50 else 'FAIL'),
         'worst case %.0f ppm new, %.0f ppm aged (pulling %.0f ppm from load uncertainty)' % (worst_new, worst_10, np.max(np.abs(pull))))
    # with a +-10/+-10 crystal (fix)
    worst_fix = 10 + 10 + np.max(np.abs(pull)) + age10
    out('   with a +-10 ppm / +-10 ppm (-40..85 C) crystal: %.0f ppm aged' % worst_fix)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    items = [('tolerance', tol), ('temperature', stab), ('load pulling', np.max(np.abs(pull))), ('ageing 10 y', age10)]
    left = 0
    cols = [C1, C2, C3, C4]
    for (nm, v), col in zip(items, cols):
        ax.barh([0], [v], left=left, color=col, height=0.5, edgecolor='white', lw=2, label='%s %.0f ppm' % (nm, v))
        left += v
    ax.axvline(40, color=CR, ls='--', lw=1)
    ax.axvline(50, color='k', ls='--', lw=1)
    ax.text(40, 0.4, ' Nordic 40', fontsize=8)
    ax.text(50, 0.4, ' BLE 50', fontsize=8)
    ax.set_yticks([])
    ax.set_xlabel('ppm, worst case')
    ax.set_title('nRF52840 32 MHz crystal frequency budget', fontsize=10)
    ax.legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'frequency.png'), dpi=110)
    plt.close(fig)


# ============================================================================ study 6
def antenna_model(b, f0=2.442e9, bw2=180e6):
    """Johanson 2450AT18A100 as a series RLC whose impedance at f0 is exactly what its
    data-sheet tee (on Johanson's EVB) matches to 50 ohm, and whose Q gives a 2:1 VSWR
    bandwidth of bw2 (ASSUMED typical; data sheet: RL >= 9.5 dB over 2400-2500 MHz)."""
    tee = b.ble_tee()
    S = tee.sparams([f0], ['BLE_50R', 'BLE_FEED'])[0][0]
    zout = R.gamma_to_z(S[1, 1])      # looking into the tee from the antenna, 50 ohm behind
    za = np.conj(zout)
    rr, x0 = za.real, za.imag
    # VSWR 2 bandwidth of a matched series RLC: Q = (VSWR-1)/sqrt(VSWR) * f0/BW
    q = (1 / math.sqrt(2)) * f0 / bw2
    lser = q * rr / (2 * math.pi * f0)
    cser = 1 / ((2 * math.pi * f0) ** 2 * lser)

    def zant(w):
        return rr + 1j * (w * lser - 1 / (w * cser)) + 1j * x0
    return zant, za, q


def study6():
    out()
    out('=' * 100)
    out('STUDY 6  Bluetooth match: Nordic pi (0.8 pF / 4.7 nH / 0.5 pF) + Johanson tee (1.0 pF / 2.7 nH / 3.9 nH) +')
    out('         2450AT18A100 chip antenna, 2400-2483.5 MHz, with tolerances (GJM +-0.1 pF, LQW15AN +-0.2 nH).')
    out('=' * 100)
    out('No PCB yet: the antenna is modelled as what Johanson\'s tee matches on Johanson\'s EVB (data sheet: "matching values')
    out('on the client PCB will be different"); the routed-board check (EM model or VNA on built boards) follows.  The nRF')
    out('ANT pin\'s optimum load is taken as what Nordic\'s nominal pi presents at 2442 MHz with 50 ohm behind it (ASSUMED:')
    out('Nordic\'s reference values are right for the chip); "RL" below is the power-wave mismatch against that load.')
    out('Criterion: RL >= 9.5 dB (Johanson spec, VSWR ~2) over 2400-2483.5 MHz: PASS >= 99 % of MC runs, MARGINAL >= 90 %.')
    fb = np.linspace(2.40e9, 2.4835e9, 18)
    b = B.Board()
    zant, za, q = antenna_model(b)
    out('  antenna model: Z(2442 MHz) = %.1f %+.1fj ohm, Q %.1f (2:1 VSWR bandwidth 180 MHz ASSUMED)' % (za.real, za.imag, q))
    pi = b.ble_pi().sparams([2.442e9], ['NRF_ANT', 'BLE_50R'])[0][0]
    zopt = complex(R.gamma_to_z(pi[0, 0]))
    out('  Nordic pi with 50 ohm behind it presents %.1f %+.1fj ohm to the ANT pin (taken as the chip\'s optimum load)'
        % (zopt.real, zopt.imag))

    def gp(zl):
        return (zl - zopt) / (zl + np.conj(zopt))

    def chain(bd):
        c = R.Circuit('ble')
        bd.add_parts(c, ['NRF_ANT', 'BLE_50R'])
        bd.add_parts(c, ['BLE_50R', 'BLE_T', 'BLE_FEED'], skip=B.BLE_PI_REFS)
        c.add('BLE_FEED', 'GND', R.Admittance(lambda w: 1 / zant(w)), 'antenna')
        return c

    res = {}
    Sn = chain(b).sparams(fb, ['NRF_ANT'])[0]
    rln = R.rl_db(gp(R.gamma_to_z(Sn[:, 0, 0])))
    for T in (-40, 25, 85):
        bm = B.Board(nsamp=NMC, temp_c=T, mode='mc', seed=600 + T)
        S = chain(bm).sparams(fb, ['NRF_ANT'], nsamp=NMC)
        rlf = R.rl_db(gp(R.gamma_to_z(S[:, :, 0, 0])))
        rl = np.min(rlf, axis=1)
        res[T] = (rl, rlf)
        out('  %4d C: nominal worst RL %.1f dB; MC worst RL min %.1f dB, median %.1f dB, yield RL >= 9.5 dB %.1f %%'
            % (T, np.min(rln), rl.min(), np.median(rl), 100 * np.mean(rl >= 9.5)))
    y = min(np.mean(res[T][0] >= 9.5) for T in res)
    # sensitivity: which part matters
    out('  one part at a time at its tolerance limit (25 C), worst RL over the band:')
    sens = []
    for c in B.rf_parts(['NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']):
        for sgn in (-1, 1):
            bs = B.Board()
            info = R.part_info(bs.part(c.ref))
            kind, t = info['tol']
            v = info['value'] + sgn * t if kind == 'abs' else info['value'] * (1 + sgn * t)
            bs.info[c.ref], bs.val[c.ref] = info, np.array([v])
            S = chain(bs).sparams(fb, ['NRF_ANT'])[0]
            sens.append((float(np.min(R.rl_db(gp(R.gamma_to_z(S[:, 0, 0]))))), c.ref, B.parts.PARTS[c.part]['value'], sgn))
    for v, ref, val, sgn in sorted(sens)[:6]:
        out('   %-5s %-7s %s tolerance: %.1f dB' % (ref, val, '+' if sgn > 0 else '-', v))
    summ('6', 'Bluetooth match over tolerance (pre-layout)', 'PASS' if y >= 0.99 else ('MARGINAL' if y >= 0.9 else 'FAIL'),
         'yield %.1f %%, worst RL %.1f dB, nominal %.1f dB (antenna = Johanson EVB model; re-check on the routed board)'
         % (100 * y, min(res[T][0].min() for T in res), np.min(rln)))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    rl25 = res[25][1]
    ax.fill_between(fb / 1e6, np.percentile(rl25, 0.5, axis=0), np.percentile(rl25, 99.5, axis=0), color=C1, alpha=0.2,
                    lw=0, label='99 % of tolerance runs (25 C)')
    ax.plot(fb / 1e6, rln, color=C1, lw=2, label='nominal')
    ax.axhline(9.5, color=CR, ls='--', lw=1, label='9.5 dB (Johanson spec)')
    ax.set_xlabel('MHz')
    ax.set_ylabel('return loss at the nRF52840 ANT pin, dB')
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    ax.set_title('Bluetooth antenna match (pre-layout model)', fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'bluetooth.png'), dpi=110)
    plt.close(fig)


# ============================================================================ study 7
def study7(s1):
    out()
    out('=' * 100)
    out('STUDY 7  No antenna at 3 W: U.FL open (|Gamma| = 1, every phase, i.e. any cable length) and a 10:1 load')
    out('=' * 100)
    out('Ratings.  SKY13330 (DS 201407E): input power +40 dBm abs max (= 31.6 V peak in 50 ohm: the voltage that power')
    out('  makes; no voltage or VSWR rating is published), IP0.1dB +38.5 dBm (26.6 V peak) - above it the switch compresses')
    out('  and makes harmonics after the elliptic filter.  LFCN-1000+: 10 W at 25 C derated to 3.5 W at 100 C (4.8 W at 85 C,')
    out('  21.9 V peak equivalent); no voltage rating.  QPA9510 (DS): output load VSWR 10:1 no damage at VCC 3.6 V, Pin')
    out('  +4.5 dBm, -40..85 C; 8:1 stable; 4.0 V not covered.  Criteria: peak voltage < 95 %% of the 50-ohm equivalent of the')
    out('  abs max PASS, 95-100 %% MARGINAL, above FAIL; PA VSWR at its plane <= 10:1 PASS (at 3.6 V only).')
    out('Two PA models: (A) saturated PA (current source + voltage clamp at the die, through this board\'s output match);')
    out('  (B) a 50-ohm source whose available power gives the rated output into a matched antenna.')
    pa_by_v = {3.6: PA(3.6), 4.0: PA(4.0), 2.7: PA(2.7)}
    b = B.Board()
    ckt = b.tx_out(with_pa=True)
    ph = np.linspace(0, 2 * np.pi, 180, endpoint=False)
    nodes = ['PA_OUT', 'PA_M1', 'PA_M2', 'PA_M3', 'PA_TX', 'SW2', 'SW1', 'ANT_SW', 'LF_OUT', 'ANT']
    vlim = {'SW2': 31.6, 'SW1': 31.6, 'ANT_SW': 21.9, 'LF_OUT': 21.9}
    results = {}
    ct = b.tx_out(with_pa=False)
    S = ct.sparams(FB, ['PA_M2', 'ANT'])[0]
    # nominal operating point
    for vpa, pa in pa_by_v.items():
        v0, i0 = pa.solve(ckt, FB, 0.0)
        p_ant = R.w_to_dbm(np.abs(v0['ANT'][0]) ** 2 / (2 * R.Z0))
        vmax = {n: np.zeros(3) for n in nodes}
        imax = np.zeros(3)
        for g in (1.0, 0.818):
            for p in ph:
                gam = g * np.exp(1j * p)
                v, i = pa.solve(ckt, FB, gam)
                for n in nodes:
                    vmax[n] = np.maximum(vmax[n], np.abs(v[n][0]))
                imax = np.maximum(imax, np.abs(i[0]))
                if g == 1.0:
                    pass
        results[vpa] = (p_ant, vmax, imax / pa.inom)
    # model B
    resB = {}
    for vpa in (3.6, 4.0, 2.7):
        p_ant = results[vpa][0]
        loss = -R.db20(S[:, 1, 0])
        pav = R.dbm_to_w(p_ant + loss)        # available at PA_M2
        vmax = {n: np.zeros(3) for n in nodes if n not in ('PA_OUT', 'PA_M1')}
        for p in ph:
            gam = np.exp(1j * p)
            vinc = np.sqrt(8 * R.Z0 * pav)
            v = ct.voltages(FB, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                                'ANT': ant_load(gam)})
            for n in vmax:
                vmax[n] = np.maximum(vmax[n], np.abs(v[n][0]))
        resB[vpa] = vmax
    out()
    out('  VPA    P at U.FL (matched)  |  peak voltage (V) with the U.FL open, worst phase, model A [model B]')
    out('                              |  ' + '  '.join('%-14s' % n for n in nodes[2:]))
    for vpa in (2.7, 3.6, 4.0):
        p_ant, vmax, ir = results[vpa]
        out('  %.1f V  %5.1f dBm (%4.2f W)    |  ' % (vpa, p_ant[1], R.dbm_to_w(p_ant[1]))
            + '  '.join('%5.1f [%5.1f]  ' % (vmax[n].max(), resB[vpa][n].max()) for n in nodes[2:]))
        out('         die current up to %.2f x nominal; PA_OUT %.1f V peak, PA_M1 %.1f V peak' % (ir.max(), vmax['PA_OUT'].max(), vmax['PA_M1'].max()))
    # VSWR at PA plane
    vs_pa = 0
    for p in ph:
        gam = np.exp(1j * p)
        gin = S[:, 0, 0] + S[:, 0, 1] * S[:, 1, 0] * gam / (1 - S[:, 1, 1] * gam)
        vs_pa = max(vs_pa, float(np.max(R.vswr(gin))))
    rt = float(np.max(-R.db20(S[:, 1, 0])) * 2)
    out()
    out('  VSWR the PA sees at its EVB plane with the U.FL open: %.1f:1 worst phase (round-trip loss %.1f dB)' % (vs_pa, rt))
    summ('7', 'PA load with antenna missing', 'PASS' if vs_pa <= 10 else 'FAIL',
         '%.1f:1 at the PA (rated 10:1 at 3.6 V, Pin +4.5 dBm): firmware 3.6 V ceiling is right; 4.0 V is outside the rating' % vs_pa)
    for vpa in (3.6, 4.0):
        v1 = max(results[vpa][1]['SW1'].max(), resB[vpa]['SW1'].max(), results[vpa][1]['SW2'].max(), resB[vpa]['SW2'].max())
        pct = 100 * v1 / 31.6
        summ('7', 'SKY13330 voltage, antenna missing, %.1f V' % vpa,
             'PASS' if pct < 95 else ('MARGINAL' if pct <= 100 else 'FAIL'),
             '%.1f V peak = %.0f %% of the +40 dBm (31.6 V) abs max; %.0f %% of the IP0.1dB voltage' % (v1, pct, 100 * v1 / 26.6))
        vl = max(results[vpa][1]['ANT_SW'].max(), results[vpa][1]['LF_OUT'].max(), resB[vpa]['ANT_SW'].max(), resB[vpa]['LF_OUT'].max())
        out('  %.1f V: LFCN port peak %.1f V = %.0f %% of the 85 C power rating\'s voltage (21.9 V), %.0f %% of 10 W (31.6 V)'
            % (vpa, vl, 100 * vl / 21.9, 100 * vl / 31.6))
    # inductor RF stress in the matched and open cases (3.6 V)
    out()
    pa = pa_by_v[3.6]
    inductor_heating(b, pa, ckt, ph, tag='')
    out()
    out('  Capacitor RF current and ESR loss (3.6 V, matched antenna; max-ESR limits; no RF current rating published for GQM):')
    w = 2 * np.pi * 915e6
    cap_refs = [c.ref for c in B.rf_parts(B.NETS_PA_OUT + B.NETS_LPF) if B.parts.PARTS[c.part]['kind'] == 'C'
                and B.parts.PARTS[c.part]['value'].endswith('pF')]
    v0, _ = pa.solve(ckt, [915e6], 0.0)
    for ref in cap_refs:
        info = b.info.get(ref) or R.part_info(b.part(ref))
        a, bb = B.BY_REF[ref].pins['1'], B.BY_REF[ref].pins['2']
        va = v0[a][0, 0] if a != 'GND' else 0
        vb = v0[bb][0, 0] if bb != 'GND' else 0
        z = R.Cap(info['value'], info['esr1g'], info['esl']).z(np.array([w]))[0, 0]
        ic = abs((va - vb) / z) / math.sqrt(2)
        out('   %-5s %-20s %-6s %s  V %5.1f V peak  I %.2f A rms  P %4.0f mW' % (
            ref, info['mpn'], B.parts.PARTS[B.BY_REF[ref].part]['value'], info['size'], abs(va - vb), ic,
            1e3 * ic ** 2 * info['esr1g'] * math.sqrt(0.915)))
    # LNA during TX
    out()
    vsw1 = max(results[4.0][1]['SW1'].max(), resB[4.0]['SW1'].max())
    p1 = vsw1 ** 2 / (2 * R.Z0)
    out('  LNA during transmit (firmware drives RXEN low = bypass): RF1 open-antenna peak %.1f V (4.0 V, worse model) ='
        ' %.1f dBm equivalent;' % (vsw1, R.w_to_dbm(p1)))
    out('   RF1->RF3 isolation 40 dB min -> LNA input %.1f dBm (abs max +25 dBm); bypass output %.1f dBm into the SX1262 RFI'
        ' (abs max +10 dBm)' % (R.w_to_dbm(p1) - 40, R.w_to_dbm(p1) - 40 - 2.2))
    out('   matched antenna, 35 dBm: LNA input %.1f dBm.  If the LNA were left in high gain (13.6 dB, IP1dB -1 dBm) the SX1262'
        ' would see ~%.0f dBm.' % (35.75 - 40, min(35.75 - 40 + 13.6, 13)))
    summ('7', 'LNA / SX1262 RX input during TX', 'PASS', 'LNA input %.1f dBm worst (abs max +25); SX1262 RFI %.1f dBm (abs max +10)'
         % (R.w_to_dbm(p1) - 40, R.w_to_dbm(p1) - 42.2))
    # plot: SW1 voltage vs phase
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for vpa, col in ((3.6, C1), (4.0, C2)):
        pa = pa_by_v[vpa]
        vv = []
        for p in ph:
            v, _ = pa.solve(ckt, [915e6], np.exp(1j * p))
            vv.append(abs(v['SW1'][0, 0]))
        ax.plot(np.degrees(ph), vv, color=col, lw=2, label='switch RF1, VPA %.1f V (model A: saturated PA)' % vpa)
        f1 = np.array([915e6])
        S1 = ct.sparams(f1, ['PA_M2', 'ANT'])[0]
        vinc = np.sqrt(8 * R.Z0 * R.dbm_to_w(results[vpa][0][1] - R.db20(S1[0, 1, 0])))
        vb = []
        for p in ph:
            v = ct.voltages(f1, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                               'ANT': ant_load(np.exp(1j * p))})
            vb.append(max(abs(v['SW1'][0, 0]), abs(v['SW2'][0, 0])))
        ax.plot(np.degrees(ph), vb, color=col, lw=1.5, ls='--', label='switch RF1/RF2, VPA %.1f V (model B: 50-ohm source)' % vpa)
    ax.axhline(31.6, color=CR, ls='--', lw=1, label='+40 dBm abs max (31.6 V in 50 ohm)')
    ax.axhline(26.6, color=CG, ls='--', lw=1, label='IP0.1dB (26.6 V)')
    ax.set_xlabel('phase of the open-circuit reflection at the U.FL, degrees')
    ax.set_ylabel('peak RF voltage, V')
    ax.set_title('Antenna missing: voltage on the SKY13330 antenna port, 915 MHz', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'open_antenna.png'), dpi=110)
    plt.close(fig)
    return results


def inductor_heating(b, pa, ckt, ph, tag='', verdicts=True):
    out('  Inductor RF heating (VPA %.1f V): I_rms^2 x R_ac(915 MHz) vs the heating at the maker\'s rated current, I^2 x Rdc max'
        % pa.vpa)
    out('  (Murata: rated current = 20 C self-heating).  R_ac from the minimum Q (typical Q is ~1.4x higher, loss ~1.4x lower).')
    out('  Matched antenna / antenna missing (worst phase, model A):')
    ind_refs = [c.ref for c in B.rf_parts(B.NETS_PA_OUT + B.NETS_LPF + B.NETS_ANT) if B.parts.PARTS[c.part]['kind'] == 'L']
    w = 2 * np.pi * 915e6
    worst = []
    for ref in ind_refs:
        b.value(ref)
        info = b.info[ref]
        a, bb = B.BY_REF[ref].pins['1'], B.BY_REF[ref].pins['2']
        rac = float(R.Ind(info['value'], info['q'], info['fq'], info['srf'], info['rdc']).r(np.array([w]))[0, 0])

        def irms(gam):
            v, _ = pa.solve(ckt, [915e6], gam)
            va = v[a][0, 0] if a != 'GND' else 0
            vb = v[bb][0, 0] if bb != 'GND' else 0
            return abs((va - vb) / (rac + 1j * w * float(np.atleast_1d(info['value'])[0]))) / math.sqrt(2)
        im = irms(0.0)
        io = max(irms(np.exp(1j * p)) for p in ph[::4])
        prated = info['irated'] ** 2 * info['rdc']
        pm, po = im ** 2 * rac, io ** 2 * rac
        val = b.part(ref)['value']
        out('   %-5s %-16s %-6s %-5s I %.2f / %.2f A rms   P %4.0f / %4.0f mW   rated-current heating %4.0f mW  -> %3.0f %% / %3.0f %%'
            % (ref, info['mpn'], val, info['size'], im, io, 1e3 * pm, 1e3 * po, 1e3 * prated, 100 * pm / prated, 100 * po / prated))
        rt = pm / prated / 1.4          # verdict on typical Q
        ro = po / prated / 1.4
        worst.append((ref, val, info['size'], pm, po, prated, rt, ro))
        if verdicts and (rt > 0.3 or ro > 0.7):
            summ('7', '%sRF heating %s %s %s' % (tag, ref, val, info['size']),
                 'PASS' if (rt <= 0.7 and ro <= 1.0) else ('MARGINAL' if rt <= 1.0 else 'FAIL'),
                 '%.0f mW matched = %.0f %% (typical Q %.0f %%) of its rated-current heating; %.0f mW antenna missing (%.0f %%)'
                 % (1e3 * pm, 100 * pm / prated, 100 * rt, 1e3 * po, 100 * po / prated))
    return worst


# ============================================================================ fixes
def fix_overrides(lpf=True, l36=True, esd=False, ble=True):
    ov = {}

    def kind(ref):
        return B.parts.PARTS[B.BY_REF[ref].part]['kind']

    def cap(mpn, v, size='0603'):
        return dict(mpn=mpn, kind='C', value=v, desc='Capacitor %s 250V C0G high-Q %s (proposed)' % (v, size))

    def ind(mpn, v, size='0805'):
        return dict(mpn=mpn, kind='L', value=v, desc='Inductor %s %s wire-wound (proposed)' % (v, size))
    if lpf:   # design_lpf.py: same topology, whole-chain optimised, one inductor type (LQW2BAN 3.2 nH 0805)
        ov[refs_between('PA_M2', 'GND')[0]] = cap('GQM1875C2E2R0BB12D', '2.0pF')
        for r in refs_between('PA_M2', 'PA_M3'):
            ov[r] = ind('LQW2BAN3N2J00L', '3.2nH') if kind(r) == 'L' else cap('GQM1875C2E3R6BB12D', '3.6pF')
        ov[refs_between('PA_M3', 'GND')[0]] = cap('GQM1875C2E1R3BB12D', '1.3pF')
        for r in refs_between('PA_M3', 'PA_TX'):
            ov[r] = ind('LQW2BAN3N2J00L', '3.2nH') if kind(r) == 'L' else cap('GQM1875C2E1R3BB12D', '1.3pF')
        ov[refs_between('PA_TX', 'GND')[0]] = cap('GQM1875C2ER90BB12D', '0.9pF')
    if l36:
        ov[refs_between('PA_OUT', 'PA_M1')[0]] = ind('LQW2BAN3N6J00L', '3.6nH')
    if esd:
        ov[refs_between('ANT', 'GND')[0]] = ind('LQW2BAN47NJ00L', '47nH')
    if ble:
        r = [x for x in refs_between('NRF_ANT', 'GND') if kind(x) == 'C'][0]
        ov[r] = dict(mpn='GJM1555C1HR80WB01D', kind='C', value='0.8pF', desc='Capacitor 0.8pF 50V C0G high-Q 0402')
    return ov


def fixes(s1):
    """Re-run the affected checks with the proposed changes (overrides only; src/ unchanged)."""
    out()
    out('=' * 100)
    out('FIXES  re-checked with the proposed values (overrides in run.py; src/ unchanged)')
    out('=' * 100)
    ov = fix_overrides()
    for r, p in sorted(ov.items(), key=lambda t: int(t[0][1:])):
        c = B.BY_REF[r]
        old = B.parts.PARTS[c.part]
        out('  %-5s %-22s %-8s -> %-22s %-7s (%s)' % (r, old['mpn'], old['value'], p['mpn'], p['value'],
                                                     '-'.join(n for n in c.pins.values())))
    out('  R41  RC0805FR-0768RL 0.125 W -> Panasonic ERJ-P06F68R0V 0.5 W (same 0805 footprint, same value)')
    pa = s1['pa']
    b = B.Board(overrides=ov)
    ct = b.tx_out(with_pa=False)
    S = ct.sparams(FB, ['PA_M2', 'ANT'])[0]
    il = -R.db20(S[:, 1, 0])
    lp = b.lpf_only().sparams(FB, ['PA_M2', 'PA_TX'])[0]
    out('  TX loss PA -> U.FL %.2f / %.2f / %.2f dB (was %.2f max); LPF alone %.2f dB; RL PA load %.1f dB, U.FL %.1f dB, LPF %.1f / %.1f dB'
        % (il[0], il[1], il[2], s1['loss'], np.max(-R.db20(lp[:, 1, 0])), np.min(R.rl_db(S[:, 0, 0])),
           np.min(R.rl_db(S[:, 1, 1])), np.min(R.rl_db(lp[:, 0, 0])), np.min(R.rl_db(lp[:, 1, 1]))))
    n1, n2 = lpf_notches(b, 1)
    out('  nominal LPF notches %.3f / %.3f GHz (targets 1.80-1.86 / 2.71-2.78)' % (n1[0] / 1e9, n2[0] / 1e9))
    rej = harmonic_rejection(b, pa)
    hres = harmonic_table(rej, b) if False else None
    loss = float(np.min(il))
    lv = harm_levels(rej, 35.0, loss)
    m = harm_margins(lv, 35.0, 6.0)
    out('  harmonic margins at 35 dBm / 6 dBi (dB):  ' + '  '.join('%df %.1f' % (n, float(min(m[n]['fcc'][0], m[n]['ham'][0])))
                                                             for n in NH))
    out('  PA-path rejection (dB):                    ' + '  '.join('%df %.0f' % (n, float(np.min(rej[n]['r']))) for n in NH))
    rows = []
    n1a, n2a, la, ha = [], [], [], []
    for T in TEMPS:
        bm = B.Board(nsamp=NMC, temp_c=T, mode='mc', seed=2000 + T, overrides=ov)
        Sm = bm.tx_out(with_pa=False).sparams(FB, ['PA_M2', 'ANT'], nsamp=NMC)
        lossm = np.max(-R.db20(Sm[:, :, 1, 0]), axis=1)
        rlpa = np.min(R.rl_db(Sm[:, :, 0, 0]), axis=1)
        rejm = harmonic_rejection(bm, pa, nsamp=NMC)
        lvm = harm_levels(rejm, 35.0, np.min(-R.db20(Sm[:, :, 1, 0]), axis=1).reshape(-1, 1))
        mm = harm_margins(lvm, 35.0, 6.0)
        hmin = np.min(np.stack([np.minimum(mm[n]['fcc'], mm[n]['ham']) for n in (2, 3, 4, 5)]), axis=0)
        a1, a2 = lpf_notches(bm, NMC)
        n1a.append(a1), n2a.append(a2), la.append(lossm), ha.append(hmin)
        rows.append((T, np.mean((hmin >= 0) & (rlpa >= 10)), np.mean(lossm <= 1.3), lossm.max(), hmin.min(), rlpa.min()))
    out('  Monte Carlo with the fixes:  T  yield harm+RL  yield loss<=1.3  loss max  worst harm margin  worst PA RL')
    for r in rows:
        out('                            %4d   %6.1f %%      %6.1f %%      %.2f dB      %5.1f dB         %4.1f dB' % (
            r[0], 100 * r[1], 100 * r[2], r[3], r[4], r[5]))
    n1a, n2a = np.concatenate(n1a), np.concatenate(n2a)
    lall = np.concatenate(la)
    out('  notch range over all runs: %.3f-%.3f GHz and %.3f-%.3f GHz' % (n1a.min() / 1e9, n1a.max() / 1e9, n2a.min() / 1e9, n2a.max() / 1e9))
    p40 = PA_P_DS + 20 * math.log10(4.0 / 3.6) - lall
    out('  U.FL power at 4.0 V: %.2f-%.2f dBm (%.2f-%.2f W)' % (p40.min(), p40.max(), R.dbm_to_w(p40.min()), R.dbm_to_w(p40.max())))
    summ('F', 'fixed LPF: loss / 2f-5f harmonic yield', 'PASS' if min(r[1] for r in rows) >= 0.99 else 'MARGINAL',
         'loss %.2f dB nominal (%.2f-%.2f MC, %.0f %% <= 1.3 dB) -> %.1f-%.1f dBm at 4.0 V; 2f-5f yield %.1f %%, worst margin %.1f dB'
         % (il.max(), lall.min(), lall.max(), 100 * np.mean(lall <= 1.3), p40.min(), p40.max(),
            100 * min(r[1] for r in rows), min(r[4] for r in rows)))
    hi = min(float(m[n]['fcc'][0]) for n in (6, 7, 8))
    summ('F', 'fixed LPF: 6f-8f (edge of data)', 'PASS' if hi >= 10 else 'RISK (unverified)',
         'worst margin %.1f dB (original filter %.1f dB); these bands depend on unpublished PA levels and models past the data'
         % (hi, s1['hi68']))
    # inductor heating with the fixes
    out()
    ckt = b.tx_out(with_pa=True)
    ph = np.linspace(0, 2 * np.pi, 180, endpoint=False)
    for vpa in (3.6, 4.0):
        wst = inductor_heating(b, PA(vpa), ckt, ph, tag='fixed, %.1f V: ' % vpa, verdicts=False)
        worst_t = max(x[6] for x in wst)
        worst_o = max(x[7] for x in wst)
        summ('F', 'fixed inductors RF heating, %.1f V' % vpa, 'PASS' if (worst_t <= 0.7 and worst_o <= 1.0) else
             ('MARGINAL' if worst_t <= 1.0 else 'FAIL'),
             'worst %.0f %% of rated-current heating matched (typical Q), %.0f %% antenna missing' % (100 * worst_t, 100 * worst_o))
    # switch voltage with the fixed LPF (model B dominates at the switch)
    vmax = 0
    S2 = b.tx_out(with_pa=False).sparams(FB, ['PA_M2', 'ANT'])[0]
    pav = R.dbm_to_w(PA_P_DS + 20 * math.log10(3.6 / 3.6) - 0 * 0)
    for p in ph:
        vinc = np.sqrt(8 * R.Z0 * R.dbm_to_w(33.6 + (-R.db20(S2[:, 1, 0]))))
        v = b.tx_out(with_pa=False).voltages(FB, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                                                 'ANT': ant_load(np.exp(1j * p))})
        vmax = max(vmax, float(np.max(np.abs(v['SW1']))), float(np.max(np.abs(v['SW2']))))
    out('  switch peak voltage with the fixes, 3.6 V (33.6 dBm), antenna missing (model B): %.1f V (%.0f %% of 31.6 V)' % (vmax, 100 * vmax / 31.6))
    # Bluetooth with +-0.05 pF on the 0.8 pF
    fb = np.linspace(2.40e9, 2.4835e9, 18)
    bn = B.Board(overrides=ov)
    zant, za, q = antenna_model(B.Board())
    pi = B.Board().ble_pi().sparams([2.442e9], ['NRF_ANT', 'BLE_50R'])[0][0]
    zopt = complex(R.gamma_to_z(pi[0, 0]))
    ys = []
    for T in (-40, 25, 85):
        bm = B.Board(nsamp=NMC, temp_c=T, mode='mc', seed=600 + T, overrides=ov)
        c = R.Circuit('ble')
        bm.add_parts(c, ['NRF_ANT', 'BLE_50R'])
        bm.add_parts(c, ['BLE_50R', 'BLE_T', 'BLE_FEED'], skip=B.BLE_PI_REFS)
        c.add('BLE_FEED', 'GND', R.Admittance(lambda w: 1 / zant(w)), 'antenna')
        Sb = c.sparams(fb, ['NRF_ANT'], nsamp=NMC)
        zl = R.gamma_to_z(Sb[:, :, 0, 0])
        rl = np.min(R.rl_db((zl - zopt) / (zl + np.conj(zopt))), axis=1)
        ys.append((T, np.mean(rl >= 9.5), rl.min()))
    out('  Bluetooth with the 0.8 pF at +-0.05 pF: ' + ', '.join('%d C yield %.1f %% (worst %.1f dB)' % (T, 100 * y, w_) for T, y, w_ in ys))
    yb = min(y for T, y, w_ in ys)
    summ('F', 'Bluetooth with 0.8 pF +-0.05 pF', 'PASS' if yb >= 0.99 else ('MARGINAL' if yb >= 0.9 else 'FAIL'),
         'yield %.1f %% (pre-layout)' % (100 * yb))
    # pad with ERJ-P06
    out('  pad first 68 R as ERJ-P06F68R0V (0.5 W at 70 C, 0 W at 155 C): +22 dBm (118 mW) at 85 C = %.0f %%; +23 dBm = %.0f %%'
        % (100 * 0.1178 / r0805_rating(85, p70=0.5), 100 * 0.1483 / r0805_rating(85, p70=0.5)))
    summ('F', 'pad with ERJ-P06F68R0V', 'PASS', '%.0f %% of its 85 C rating at +22 dBm, %.0f %% at +23 dBm'
         % (100 * 0.1178 / r0805_rating(85, p70=0.5), 100 * 0.1483 / r0805_rating(85, p70=0.5)))


def lfcn_fit_report():
    S = lfcn.response(lfcn.F_TAB)
    out('LFCN-1000+ model vs Mini-Circuits typical table (REV. R):')
    out('   MHz    ' + ''.join('%7.0f' % (f / 1e6) for f in lfcn.F_TAB))
    out('   IL ds  ' + ''.join('%7.2f' % x for x in lfcn.IL_TAB))
    out('   IL fit ' + ''.join('%7.2f' % x for x in -R.db20(S[:, 1, 0])))
    g = np.abs(S[:, 0, 0])
    out('   VSWR ds' + ''.join('%7.1f' % x for x in lfcn.VSWR_TAB))
    out('   VSWRfit' + ''.join('%7.1f' % x for x in (1 + g) / (1 - g)))
    out()


def main():
    out('Mesh Radio v1 - RF simulation results (sim/rf/run.py%s)' % (' --quick' if QUICK else ''))
    out('Board values from src/circuit.py; part models and sources in sim/rf/README.md and rflib.py.')
    out()
    lfcn_fit_report()
    s1 = study1()
    study2(s1)
    study3()
    study4()
    study5()
    study6()
    study7(s1)
    fixes(s1)
    out()
    out('=' * 100)
    out('SUMMARY')
    out('=' * 100)
    for st, item, v, nums in SUMMARY:
        out('  %s  %-52s %-9s %s' % (st, item, v, nums))
    with open(os.path.join(HERE, 'results.txt'), 'w') as fh:
        fh.write('\n'.join(LINES) + '\n')


if __name__ == '__main__':
    main()
