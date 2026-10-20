# -*- coding: utf-8 -*-
"""Mesh Radio v1 RF studies 1-8 (README.md in this folder says what and why).

    tools/kd python3 sim/rf/run.py            # from mesh-radio/v1, ~3-6 min
    tools/kd python3 sim/rf/run.py --quick    # 200 Monte Carlo runs instead of 1000

Board as in src/ on 20 Oct: antenna filter LFCG-1000+, missing-antenna ratio detector (printed coupler, BAT68-04W at
each end into 1 nF / 100 k: REFL_DET and FWD_DET).  Study 8 is the detector: the ratio threshold and its margins.

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


def model_pins(ref):
    """The model nodes a part sits between (the ESD shunt's ANT pin is inside the coupled run, ANT_E)."""
    pins = [B.BY_REF[ref].pins['1'], B.BY_REF[ref].pins['2']]
    if ref in [c.ref for c in B.rf_parts(B.NETS_ANT)]:
        pins = ['ANT_E' if p == 'ANT' else p for p in pins]
    return pins


# ============================================================================ antenna filter (FL1)
FLT = B.FL_NAME                          # 'LFCG-1000+'
IS_LFCG = B.FL_PART == 'LFCG1000'


def flt_response(f, k=1.0):
    """S-matrix of the antenna filter model alone (50 ohm)."""
    return lfcn.response(f, p=lfcn.G_FIT if IS_LFCG else None, k=k)


def flt_table_rej(f):
    """Mini-Circuits' typical insertion loss (dB), linear interpolation; LFCN above 7 GHz: its 7 GHz value
    (ASSUMED); LFCG table runs to 10 GHz."""
    if IS_LFCG:
        return np.interp(f, lfcn.G_F_TAB, lfcn.G_IL_TAB, right=lfcn.G_IL_TAB[-1])
    return np.interp(f, lfcn.F_TAB, lfcn.IL_TAB, right=lfcn.IL_TAB[-1])


# LFCG-1000+ (Mini-Circuits data sheet): insertion loss 0.8 typ / 1.8 max dB DC-1000 MHz; RF input 5.5 W at 25 C,
# derated linearly to 1 W at 125 C (passband rating); no pulse or voltage rating.
FLT_IL_MAX = 1.8 if IS_LFCG else 1.0


def flt_rating_w(t_c):
    if IS_LFCG:
        return 5.5 - 4.5 * (t_c - 25.0) / 100.0
    return 10.0 - 6.5 * (t_c - 25.0) / 75.0


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
    G = B.GEOM
    out('1d PA output (PA_M2) -> elliptic LPF -> %.1f mm -> SKY13330 -> %.1f mm -> %s -> %.1f mm -> detector coupler'
        % (b.lines['lpf_sw'], b.lines['sw_lfcn'], FLT, G['flt_cpl']))
    out('   (%.1f mm run, %.2f mm gap, 47 nH ESD shunt %.1f mm before its end) -> %.1f mm -> U.FL (geometry: src/layout.py):'
        % (G['cpl_len'], G['gap'], G['esd_from_end'], G['cpl_ufl']))
    ct = b.tx_out(with_pa=False)
    S, pv = ct.sparams(FB, ['PA_M2', 'ANT'], probe=['PA_M2', 'SW2', 'SW1', 'ANT_SW', 'LF_OUT'])
    S = S[0]
    il = -R.db20(S[:, 1, 0])
    out('   insertion loss %.2f / %.2f / %.2f dB (902/915/928)' % tuple(il))
    # loss budget per block (50-ohm insertion loss of each block alone)
    lp = b.lpf_only().sparams(FB, ['PA_M2', 'PA_TX'])[0]
    lf = flt_response(FB)
    ca = R.Circuit('ant')
    b.ant_section(ca, 'LF_OUT')
    sa = ca.sparams(FB, ['LF_OUT', 'ANT', 'REFL_T'])[0]
    il_ant = float(np.max(-R.db20(sa[:, 1, 0])))
    p_term = float(np.max(np.abs(sa[:, 2, 0]) ** 2))
    out('   blocks alone (50 ohm): LPF %.2f dB, SKY13330 0.30 dB (typ; 0.35 max), %s %.2f dB (fit to typ table; %.1f max),'
        ' antenna section (coupler, ESD, detector, %.1f mm of line) %.2f dB, other traces and mismatch interaction %+.2f dB'
        % (np.max(-R.db20(lp[:, 1, 0])), FLT, np.max(-R.db20(lf[:, 1, 0])), FLT_IL_MAX,
           G['flt_cpl'] + G['cpl_len'] + G['cpl_ufl'], il_ant,
           np.max(il) - np.max(-R.db20(lp[:, 1, 0])) - 0.30 - np.max(-R.db20(lf[:, 1, 0])) - il_ant))
    out('   detector coupler: %.1f dB of the forward wave goes to the 49.9 R (%.1f mW at 35 dBm, matched)'
        % (-R.db10(p_term), 1e3 * R.dbm_to_w(35.0) * p_term))
    # interface return losses: build sub-chains starting at each interface
    rls = {}
    rls['PA_M2 into LPF+rest (PA load)'] = np.min(R.rl_db(S[:, 0, 0]))
    rls['U.FL looking into the board'] = np.min(R.rl_db(S[:, 1, 1]))
    rls['LPF alone, in / out'] = (np.min(R.rl_db(lp[:, 0, 0])), np.min(R.rl_db(lp[:, 1, 1])))
    rls['%s alone, in / out' % FLT] = (np.min(R.rl_db(lf[:, 0, 0])), np.min(R.rl_db(lf[:, 1, 1])))
    rls['antenna section (coupler) in / out'] = (np.min(R.rl_db(sa[:, 0, 0])), np.min(R.rl_db(sa[:, 1, 1])))
    # RL at switch RF2 looking toward the antenna
    cs = b.sw_to_ant()
    b.sky13330(cs, 'SW2', 'SW1')
    ss = cs.sparams(FB, ['SW2', 'ANT'])[0]
    rls['switch RF2 into switch+filter+antenna'] = np.min(R.rl_db(ss[:, 0, 0]))
    for k, x in rls.items():
        out('   RL %-38s %s dB' % (k, ' / '.join('%.1f' % y for y in np.atleast_1d(x))))
    rl_min = min(float(np.min(np.atleast_1d(x))) for x in rls.values())
    rl_min = min(rl_min, worst_rl)
    loss_max = float(np.max(il))
    summ('1', 'TX loss PA -> U.FL', 'PASS' if loss_max <= 1.3 else ('MARGINAL' if loss_max <= 2.0 else 'FAIL'),
         '%.2f dB max in band (LPF %.2f, switch 0.30, LFCG %.2f, coupler section %.2f): 35 dBm at 4.0 V gives %.1f dBm at the'
         ' U.FL; with the LFCG at its 1.8 dB data-sheet max: %.2f dB'
         % (loss_max, np.max(-R.db20(lp[:, 1, 0])), np.max(-R.db20(lf[:, 1, 0])), il_ant,
            PA_P_DS + 20 * math.log10(4.0 / 3.6) - loss_max, loss_max + FLT_IL_MAX - np.max(-R.db20(lf[:, 1, 0]))))
    summ('1', 'return loss at interfaces', 'PASS' if rl_min >= 10 else ('MARGINAL' if rl_min >= 6 else 'FAIL'),
         'worst %.1f dB (PA load %.1f dB, U.FL %.1f dB, pad seen by SX1262 %.1f dB); QPA9510 own input 7.3-11.1 dB'
         % (rl_min, rls['PA_M2 into LPF+rest (PA load)'], rls['U.FL looking into the board'], worst_rl))
    out('   SX1262 match loss %.2f dB is the Semtech reference network driving its 50 ohm design load (the pad).' % sx_loss)

    # ---- harmonics
    out('1e Harmonics.  PA levels at the EVB plane (into 50 ohm): 2f %.1f dBc, 3f %.1f dBc (data sheet), 4f-10f %.0f dBc'
        ' (ASSUMED).' % (harm_dbc_pa(2), harm_dbc_pa(3), HARM_DBC_PA_ASSUMED))
    out('   Rejection used = 50-ohm insertion loss PA_M2 -> U.FL (how the data-sheet harmonics were measured).  Shown')
    out('   for sensitivity only: the PA die as the source through the output match (internal values guessed), which')
    out('   the reflective filters can make 10-35 dB worse above 5 GHz.  Switch self-generated')
    out('   harmonics (ASSUMED -65/-60/-70 dBc for 2f/3f/other at +35 dBm on RF1) filtered by the %s only.' % FLT)
    out('   The %s model is credited with no more rejection than Mini-Circuits\' typical table (to %s GHz).'
        % (FLT, '10' if IS_LFCG else '7'))
    rej = harmonic_rejection(b, pa)
    hres = harmonic_table(rej, b)
    plot_tx(b, rej, hres)
    return dict(pa=pa, rej=rej, loss=loss_max, hi68=hres['hi68'])


def harmonic_rejection(b, pa, nsamp=1, lines=None, pa_src=True):
    """dict n -> rejection dB array (S, 3 freqs) for PA path (worse of 50-ohm and PA-source) and
    the switch path (SW1 -> U.FL)."""
    fh = np.concatenate([n * FB for n in NH])
    ct = b.tx_out(with_pa=False, lines=lines)
    S = ct.sparams(fh, ['PA_M2', 'ANT'], nsamp=nsamp)
    rej50 = -R.db20(S[:, :, 1, 0])
    if pa_src:
        cp = b.tx_out(with_pa=True, lines=lines)
        v = cp.voltages(fh, {'DIE': 1.0}, loads={'ANT': ant_load(0.0)}, nsamp=nsamp)
        vref = pa.evb.voltages(fh, {'DIE': 1.0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0})
        rejpa = R.db20(vref['PA_M2']) - R.db20(v['ANT'])
    else:
        rejpa = rej50 + 0.0
    # switch path
    cs = b.sw_to_ant(lines=lines)
    Ss = cs.sparams(fh, ['SW1', 'ANT'], nsamp=nsamp)
    rejsw = -R.db20(Ss[:, :, 1, 0])
    # The fitted filter model has notches the data sheet does not show: its rejection is replaced by
    # Mini-Circuits' typical table (linear interpolation; LFCN above 7 GHz its 7 GHz value, ASSUMED),
    # keeping the model's phase and mismatch.
    corr = -R.db20(flt_response(fh)[:, 1, 0]) - flt_table_rej(fh)
    rej50, rejpa, rejsw = rej50 - corr, rejpa - corr, rejsw - corr
    res = {}
    for k, n in enumerate(NH):
        sl = slice(3 * k, 3 * k + 3)
        res[n] = dict(r50=rej50[:, sl], rpa=rejpa[:, sl], r=rej50[:, sl], rsw=rejsw[:, sl])
    return res


def lfcn_table_rej(f):
    """LFCN-1000+ table rejection (kept for followup.py)."""
    return np.interp(f, lfcn.F_TAB, lfcn.IL_TAB, right=lfcn.IL_TAB[-1])


def study1f():
    """6f-10f (and 2f-5f) over the routed trace lengths still unknown: the two filters (LPF, LFCG) with the
    switch between them interact through their reflective stop bands."""
    out()
    out('1f Harmonics over layouts: lpf_sw and sw_lfcn (switch to filter) each 1, 2, 3, 5, 8, 12 mm and the filter to')
    out('   coupler line 0.9 (as placed), 3 and 6 mm: 108 layouts, 50-ohm rejection as in 1e.  Worst layout per harmonic.')
    b = B.Board()
    sweep = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0]
    worst = {(p, g): {n: 99.0 for n in NH} for p, g in ((35.0, 6.0), (30.0, 2.15))}
    lossw = 0.0
    for l1 in sweep:
        for l2 in sweep:
            for l3 in (0.9, 3.0, 6.0):
                ln = {'lpf_sw': l1, 'sw_lfcn': l2, 'flt_cpl': l3}
                rej = harmonic_rejection(b, None, lines=ln, pa_src=False)
                S = b.tx_out(with_pa=False, lines=ln).sparams(FB, ['PA_M2', 'ANT'])[0]
                loss = float(np.min(-R.db20(S[:, 1, 0])))
                lossw = max(lossw, float(np.max(-R.db20(S[:, 1, 0]))))
                for (p, g), w in worst.items():
                    m = harm_margins(harm_levels(rej, p, loss), p, g)
                    for n in NH:
                        w[n] = min(w[n], float(min(m[n]['fcc'][0], m[n]['ham'][0])))
    for (p, g), w in worst.items():
        out('   %2.0f dBm %4.2f dBi worst layout ' % (p, g) + ' '.join('%df %6.1f' % (n, w[n]) for n in NH))
    out('   loss PA -> U.FL, worst layout: %.2f dB' % lossw)
    w35 = min(worst[(35.0, 6.0)].values())
    n35 = min(NH, key=lambda n: worst[(35.0, 6.0)][n])
    w30 = min(worst[(30.0, 2.15)].values())
    n30 = min(NH, key=lambda n: worst[(30.0, 2.15)][n])
    summ('1', 'harmonics 2f-10f at 35 dBm, 6 dBi, worst of 108 layouts', verdict_margin(w35),
         'worst %.1f dB at %df (6f-10f rest on the ASSUMED -45 dBc PA level)' % (w35, n35))
    summ('1', 'harmonics 2f-10f, US default 30 dBm, 2.15 dBi, worst layout', verdict_margin(w30),
         'worst %.1f dB at %df' % (w30, n30))
    return worst


RESTRICTED = {3: '2690-2900', 4: '3600-4400', 5: '4500-5150', 6: '5350-5460 (902-910 MHz only)', 8: '7250-7750',
              9: '8025-8500', 10: '9000-9200'}
EIRP_LIMIT = 54 + 20 * math.log10(3) - 104.77      # dBm EIRP at 3 m (E[dBuV/m] = EIRP + 104.77 - 20 log d)


def harm_levels(rej, p_ant, loss_db):
    """Conducted harmonic level (dBc relative to p_ant at the U.FL) per n, worst over band, per sample."""
    lv = {}
    for n in NH:
        pa_dbc = harm_dbc_pa(n) - (rej[n]['r'] - loss_db)      # relative to fundamental at U.FL
        p_sw_rf1 = p_ant + 0.75                                  # RF1 is ~0.75 dB (filter, coupler, traces) before the U.FL
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
    mh = lambda p, g, n: min(float(res[(p, g)][n]['fcc'][0]), float(res[(p, g)][n]['ham'][0]))
    hi = min(mh(35.0, 6.0, n) for n in range(6, 11))
    hn = min(range(6, 11), key=lambda n: mh(35.0, 6.0, n))
    summ('1', 'harmonics 6f-10f at 35 dBm, 6 dBi, layout as placed', verdict_margin(hi),
         'worst margin %.1f dB at %df (PA level there ASSUMED -45 dBc; %s typical table to 10 GHz)' % (hi, hn, FLT))
    res['hi68'] = hi
    return res


def plot_tx(b, rej, hres):
    f = np.linspace(0.3e9, 10e9, 1941)
    lp = b.lpf_only().sparams(f, ['PA_M2', 'PA_TX'])[0]
    lf = flt_response(f)
    ch = b.tx_out(with_pa=False).sparams(f, ['PA_M2', 'ANT'])[0]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    a = ax[0]
    a.plot(f / 1e9, R.db20(lp[:, 1, 0]), color=C1, lw=1.5, label='elliptic LPF (parts as modelled)')
    a.plot(f / 1e9, R.db20(lf[:, 1, 0]), color=C2, lw=1.5, label='%s (fitted model)' % FLT)
    ft, it = (lfcn.G_F_TAB, lfcn.G_IL_TAB) if IS_LFCG else (lfcn.F_TAB, lfcn.IL_TAB)
    a.plot(ft / 1e9, -it, 'o', color=C2, ms=4, label='%s data sheet table' % FLT)
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
    a.set_title('35 dBm, 6 dBi: margin to the FCC limit (grey = 6f-10f: PA level assumed)', fontsize=10)
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
    out('         from the maker range): C0G +-0.05/0.1/0.25 pF or +-5 %, LQW15AN +-0.2 nH / +-5 %, LQW2BAN 0805 +-5 %,')
    out('         0908SQ +-5 %; TC C0G 0+-30 ppm/C, inductors +25..+125 ppm/C, R +-100 ppm/C;')
    out('         SKY13330 loss typ..max; %s loss x1.0-1.5 and +-1 %% frequency (ASSUMED spreads; its data-sheet' % FLT)
    out('         maximum, 1.8 dB, would add ~1.1 dB to every loss below).  Coupler geometry nominal.')
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
         'bands: the notches miss, the %s carries the rejection' % ((n10[0] / 1e9, n20[0] / 1e9) + q(n1all) + q(n2all) + (FLT,)))
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
    out('STUDY 3  The 15.9 dB pi pad (68 / 150 / 68 R 0805, 1 %, TCR +-100 ppm/C): R41 Vishay RCS080568R0FKEA anti-surge')
    out('         0.4 W at 70 C, the other two Yageo RC0805FR-07 0.125 W at 70 C; all derated linearly to 0 W at 155 C.')
    out('         SX1262 output into the pad = its setting (Semtech defines output power')
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
    out('  derated rating of a 0.125 W part: ' + ', '.join('%d C %.0f mW' % (t, 1e3 * r0805_rating(t)) for t in TEMPS))
    r1 = refs[0]
    def p70(r):
        mpn = B.parts.PARTS[B.BY_REF[r].part]['mpn']
        return 0.4 if mpn.startswith('RCS0805') else (0.5 if mpn.startswith('ERJ-P06') else 0.125)
    out('  ratings at 70 C: ' + ', '.join('%s %s %.3f W' % (r, B.parts.PARTS[B.BY_REF[r].part]['mpn'], p70(r)) for r in refs)
        + ' (Vishay RCS e3: LCSC 0.4 W, Vishay 2023 release 0.5 W; 0.4 W used); all derate linearly to 0 W at 155 C')
    tab = {}
    for pset, pw, pin in res:
        tab[pset] = {t: max(100 * pw[r] / r0805_rating(t, p70=p70(r)) for r in refs) for t in TEMPS}
    out('  worst resistor, % of its derated rating:  ' + ''.join('%7d C' % t for t in TEMPS))
    for pset in tab:
        out('    SX1262 %+5.1f dBm                       ' % pset + ''.join('%8.0f%%' % tab[pset][t] for t in TEMPS))
    p20, p22 = tab[20.0][85], tab[22.0][85]
    v = lambda x: 'PASS' if x <= 70 else ('MARGINAL' if x <= 100 else 'FAIL')
    summ('3', 'pad power at +20 dBm (firmware cap), 85 C', v(tab[21.0][85]),
         'worst resistor %.0f %% of its 85 C rating (%.0f %% with +1 dB SX1262 spread); first 68 R takes %.0f mW'
         % (p20, tab[21.0][85], 1e3 * max(res[0][1].values())))
    summ('3', 'pad power at +22 dBm, 85 C', v(p22), 'worst resistor %.0f %% of its rating (%.0f %% at +23 dBm); first 68 R %.0f mW'
         % (p22, tab[23.0][85], 1e3 * max(res[2][1].values())))
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
    ax.plot(tt, [1e3 * r0805_rating(t, p70=0.4) for t in tt], color='k', lw=1.5, label='R41 RCS0805 0.4 W rating')
    ax.plot(tt, [0.7e3 * r0805_rating(t, p70=0.4) for t in tt], color=CG, lw=1, ls='--', label='70 % (E4 headroom)')
    for (pset, pw, pin), col in zip(res, (C1, C3, C2, C4)):
        ax.axhline(1e3 * max(pw.values()), color=col, lw=1.5, label='first 68 R at SX1262 %+.0f dBm' % pset)
    ax.axvline(85, color=CR, lw=0.8, ls=':')
    ax.set_xlabel('board temperature at the resistor, C')
    ax.set_ylabel('mW')
    ax.set_ylim(0, 420)
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
    out('STUDY 4  Receive path: U.FL -> coupler + 47 nH + detector -> %s -> SKY13330 RF1->RF3 -> [1 nF + 11 nH + BGA7L1BN6]' % FLT)
    out('         -> balun -> SX1262')
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
    lflt = float(np.max(-R.db20(flt_response(FB)[:, 1, 0])))
    out('  passive loss U.FL -> RX_SW (available gain, typical parts): %.2f dB (%s %.2f, switch 0.30, coupler + ESD + detector'
        ' + traces the rest); RL at U.FL %.1f dB' % (lpre_typ, FLT, lflt, np.min(R.rl_db(S[:, 0, 0]))))
    lpre_max = lpre_typ + (FLT_IL_MAX - lflt) + (0.35 - 0.30)
    out('  worst case: %s %.1f dB (data-sheet max) and switch 0.35 dB -> %.2f dB' % (FLT, FLT_IL_MAX, lpre_max))
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
    out('         2450AT18A100 chip antenna, 2400-2483.5 MHz, with tolerances (0.8 pF GJM...W +-0.05 pF, other GJM +-0.1 pF,')
    out('         LQW15AN +-0.2 nH).')
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
SW_VMAX = 31.6           # SKY13330 +40 dBm abs max, as the peak voltage it makes in 50 ohm
SW_V01 = 26.6            # SKY13330 IP0.1dB +38.5 dBm, same
OPEN_NODES = ['PA_OUT', 'PA_M1', 'PA_M2', 'PA_M3', 'PA_TX', 'SW2', 'SW1', 'ANT_SW', 'LF_OUT', 'ANT_E', 'ANT']


def flt_vrating(t_c):
    """Peak voltage the filter's power rating makes in 50 ohm (no voltage rating is published)."""
    return math.sqrt(2 * R.Z0 * flt_rating_w(t_c))


def open_stress(b, ckt, ct, ph, vpas=(2.7, 3.6, 4.0)):
    """Peak node voltages with the U.FL open (every phase, 902-928 MHz) for model A (saturated PA at each VPA)
    and model B (50-ohm source; at the same matched power as A, and at 30 dBm, the US cap)."""
    S = ct.sparams(FB, ['PA_M2', 'ANT'])[0]
    loss = -R.db20(S[:, 1, 0])
    resA, resB = {}, {}
    for vpa in vpas:
        pa = PA(vpa)
        v0, _ = pa.solve(ckt, FB, 0.0)
        p_ant = R.w_to_dbm(np.abs(v0['ANT'][0]) ** 2 / (2 * R.Z0))
        vmax = {n: np.zeros(3) for n in OPEN_NODES}
        imax = np.zeros(3)
        for g in (1.0, 0.818):
            for p in ph:
                v, i = pa.solve(ckt, FB, g * np.exp(1j * p))
                for n in OPEN_NODES:
                    vmax[n] = np.maximum(vmax[n], np.abs(v[n][0]))
                imax = np.maximum(imax, np.abs(i[0]))
        resA[vpa] = (p_ant, vmax, imax / pa.inom, pa)
    for key in list(vpas) + ['30dBm']:
        p_ant = np.full(3, 30.0) if key == '30dBm' else resA[key][0]
        pav = R.dbm_to_w(p_ant + loss)
        vmax = {n: np.zeros(3) for n in OPEN_NODES if n not in ('PA_OUT', 'PA_M1')}
        for p in ph:
            vinc = np.sqrt(8 * R.Z0 * pav)
            v = ct.voltages(FB, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                                'ANT': ant_load(np.exp(1j * p))})
            for n in vmax:
                vmax[n] = np.maximum(vmax[n], np.abs(v[n][0]))
        resB[key] = (p_ant, vmax)
    return resA, resB, S


def study7(s1):
    out()
    out('=' * 100)
    out('STUDY 7  No antenna: U.FL open (|Gamma| = 1, every phase, i.e. any cable length) and a 10:1 load, VPA 2.7 / 3.6 / 4.0 V')
    out('=' * 100)
    out('Ratings.  SKY13330 (DS 201407E): input power +40 dBm abs max (= 31.6 V peak in 50 ohm: the voltage that power')
    out('  makes; no voltage or VSWR rating is published), IP0.1dB +38.5 dBm (26.6 V peak) - above it the switch compresses')
    out('  and makes harmonics after the elliptic filter.  %s: %.1f W at 25 C derated linearly to 1 W at 125 C (%.1f W at'
        % (FLT, flt_rating_w(25), flt_rating_w(85)))
    out('  85 C; %.1f / %.1f V peak equivalent at 25 / 85 C); no voltage rating.  QPA9510 (DS): output load VSWR 10:1 no damage'
        % (flt_vrating(25), flt_vrating(85)))
    out('  at VCC 3.6 V, Pin +4.5 dBm, -40..85 C; 8:1 stable; 4.0 V not covered.  Criteria: peak voltage < 95 % of the 50-ohm')
    out('  equivalent of the abs max PASS, 95-100 % MARGINAL, above FAIL; PA VSWR at its plane <= 10:1 PASS (at 3.6 V only).')
    out('Two PA models: (A) saturated PA (current source + voltage clamp at the die, through this board\'s output match);')
    out('  (B) a 50-ohm source whose available power gives model A\'s output into a matched antenna (and, for the US')
    out('  setting, 30 dBm).  The firmware\'s US mode is VPA 2.7 V with the SX1262 drive set for 30 dBm, i.e. between the two.')
    b = B.Board()
    ckt = b.tx_out(with_pa=True)
    ct = b.tx_out(with_pa=False)
    ph = np.linspace(0, 2 * np.pi, 180, endpoint=False)
    resA, resB, S = open_stress(b, ckt, ct, ph)
    nodes = OPEN_NODES
    out()
    out('  VPA    P at U.FL (matched)  |  peak voltage (V) with the U.FL open, worst phase, model A [model B]')
    out('                              |  ' + '  '.join('%-14s' % n for n in nodes[2:]))
    for vpa in (2.7, 3.6, 4.0):
        p_ant, vmax, ir, pa = resA[vpa]
        out('  %.1f V  %5.1f dBm (%4.2f W)    |  ' % (vpa, p_ant[1], R.dbm_to_w(p_ant[1]))
            + '  '.join('%5.1f [%5.1f]  ' % (vmax[n].max(), resB[vpa][1][n].max()) for n in nodes[2:]))
        out('         die current up to %.2f x nominal; PA_OUT %.1f V peak, PA_M1 %.1f V peak' % (ir.max(), vmax['PA_OUT'].max(), vmax['PA_M1'].max()))
    out('  model B at 30 dBm (US cap):  |  ' + '  '.join('      [%5.1f]  ' % resB['30dBm'][1][n].max() for n in nodes[2:]))
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
         '%.1f:1 at the PA, worst phase (rated 10:1 at 3.6 V, Pin +4.5 dBm; 4.0 V not covered); %s'
         % (vs_pa, 'inside the rating' if vs_pa <= 10 else 'the LFCG reflects more than the LFCN did (9.1:1 on 19 Oct): only'
            ' the detector cut-off limits the exposure'))
    sw = {}
    for vpa in (2.7, 3.6, 4.0):
        va = max(resA[vpa][1]['SW1'].max(), resA[vpa][1]['SW2'].max())
        vb = max(resB[vpa][1]['SW1'].max(), resB[vpa][1]['SW2'].max())
        sw[vpa] = (va, vb)
        v1 = max(va, vb)
        pct = 100 * v1 / SW_VMAX
        extra = ''
        if vpa == 2.7:
            vb30 = max(resB['30dBm'][1]['SW1'].max(), resB['30dBm'][1]['SW2'].max())
            # model A is linear in its supply (current and clamp both scale), so at exactly 30 dBm:
            va30 = va * 10 ** ((30.0 - float(resA[vpa][0][1])) / 20)
            sw['30dBm'] = (va30, vb30)
            extra = '; at exactly 30 dBm (US cap): model A %.1f V (%.0f %%), model B %.1f V (%.0f %%)' % (
                va30, 100 * va30 / SW_VMAX, vb30, 100 * vb30 / SW_VMAX)
        summ('7', 'SKY13330 voltage, antenna missing, %.1f V' % vpa,
             'PASS' if pct < 95 else ('MARGINAL' if pct <= 100 else 'FAIL'),
             'model A %.1f V (%.0f %%), model B %.1f V (%.0f %%) peak vs the +40 dBm (31.6 V) abs max; IP0.1dB 26.6 V%s'
             % (va, 100 * va / SW_VMAX, vb, 100 * vb / SW_VMAX, extra))
    for vpa in (2.7, 3.6, 4.0):
        vl = max(resA[vpa][1]['ANT_SW'].max(), resA[vpa][1]['LF_OUT'].max(), resB[vpa][1]['ANT_SW'].max(),
                 resB[vpa][1]['LF_OUT'].max())
        out('  %.1f V: %s port peak %.1f V = %.0f %% of its 25 C power rating\'s voltage (%.1f V), %.0f %% of the 85 C one (%.1f V)'
            % (vpa, FLT, vl, 100 * vl / flt_vrating(25), flt_vrating(25), 100 * vl / flt_vrating(85), flt_vrating(85)))
    # inductor RF stress in the matched and open cases
    heat = {}
    for vpa in (2.7, 3.6, 4.0):
        out()
        wst = inductor_heating(b, resA[vpa][3], ckt, ph, verdicts=False)
        heat[vpa] = wst
        worst_t = max(x[6] for x in wst)
        worst_o = max(x[7] for x in wst)
        if vpa >= 3.6:
            summ('7', 'inductor RF heating (steady), %.1f V' % vpa, 'PASS' if (worst_t <= 0.7 and worst_o <= 1.0) else
                 ('MARGINAL' if worst_t <= 1.0 else 'FAIL'),
                 'worst %.0f %% of rated-current heating matched (typical Q), %.0f %% antenna missing (L15; transient: 7b)'
                 % (100 * worst_t, 100 * worst_o))
    out()
    pa = resA[3.6][3]
    out('  Capacitor RF current and ESR loss (3.6 V, matched antenna; max-ESR limits; no RF current rating published for GQM):')
    w = 2 * np.pi * 915e6
    cap_refs = [c.ref for c in B.rf_parts(B.NETS_PA_OUT + B.NETS_LPF) if B.parts.PARTS[c.part]['kind'] == 'C'
                and B.parts.PARTS[c.part]['value'].endswith('pF')]
    v0, _ = pa.solve(ckt, [915e6], 0.0)
    for ref in cap_refs:
        info = b.info.get(ref) or R.part_info(b.part(ref))
        a, bb = model_pins(ref)
        va = v0[a][0, 0] if a != 'GND' else 0
        vb = v0[bb][0, 0] if bb != 'GND' else 0
        z = R.Cap(info['value'], info['esr1g'], info['esl']).z(np.array([w]))[0, 0]
        ic = abs((va - vb) / z) / math.sqrt(2)
        out('   %-5s %-20s %-6s %s  V %5.1f V peak  I %.2f A rms  P %4.0f mW' % (
            ref, info['mpn'], B.parts.PARTS[B.BY_REF[ref].part]['value'], info['size'], abs(va - vb), ic,
            1e3 * ic ** 2 * info['esr1g'] * math.sqrt(0.915)))
    # LNA during TX
    out()
    vsw1 = max(resA[4.0][1]['SW1'].max(), resB[4.0][1]['SW1'].max())
    p1 = vsw1 ** 2 / (2 * R.Z0)
    out('  LNA during transmit (firmware drives RXEN low = bypass): RF1 open-antenna peak %.1f V (4.0 V, worse model) ='
        ' %.1f dBm equivalent;' % (vsw1, R.w_to_dbm(p1)))
    out('   RF1->RF3 isolation 40 dB min -> LNA input %.1f dBm (abs max +25 dBm); bypass output %.1f dBm into the SX1262 RFI'
        ' (abs max +10 dBm)' % (R.w_to_dbm(p1) - 40, R.w_to_dbm(p1) - 40 - 2.2))
    summ('7', 'LNA / SX1262 RX input during TX', 'PASS', 'LNA input %.1f dBm worst (abs max +25); SX1262 RFI %.1f dBm (abs max +10)'
         % (R.w_to_dbm(p1) - 40, R.w_to_dbm(p1) - 42.2))
    # plot: switch voltage vs phase
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for vpa, col in ((2.7, C3), (3.6, C1), (4.0, C2)):
        pa = resA[vpa][3]
        vv = []
        for p in ph:
            v, _ = pa.solve(ckt, [915e6], np.exp(1j * p))
            vv.append(max(abs(v['SW1'][0, 0]), abs(v['SW2'][0, 0])))
        ax.plot(np.degrees(ph), vv, color=col, lw=2, label='switch RF1/RF2, VPA %.1f V (model A: saturated PA)' % vpa)
        f1 = np.array([915e6])
        S1 = ct.sparams(f1, ['PA_M2', 'ANT'])[0]
        vinc = np.sqrt(8 * R.Z0 * R.dbm_to_w(resA[vpa][0][1] - R.db20(S1[0, 1, 0])))
        vb = []
        for p in ph:
            v = ct.voltages(f1, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                               'ANT': ant_load(np.exp(1j * p))})
            vb.append(max(abs(v['SW1'][0, 0]), abs(v['SW2'][0, 0])))
        ax.plot(np.degrees(ph), vb, color=col, lw=1.5, ls='--', label='switch RF1/RF2, VPA %.1f V (model B: 50-ohm source)' % vpa)
    ax.axhline(SW_VMAX, color=CR, ls='--', lw=1, label='+40 dBm abs max (31.6 V in 50 ohm)')
    ax.axhline(SW_V01, color=CG, ls='--', lw=1, label='IP0.1dB (26.6 V)')
    ax.set_xlabel('phase of the open-circuit reflection at the U.FL, degrees')
    ax.set_ylabel('peak RF voltage, V')
    ax.set_title('Antenna missing: voltage on the SKY13330, 915 MHz', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'open_antenna.png'), dpi=110)
    plt.close(fig)
    heat7b = study7b(b, ckt, resA)
    return dict(resA=resA, resB=resB, sw=sw, heat=heat, heat7b=heat7b, vs_pa=vs_pa)


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
        a, bb = model_pins(ref)
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
        worst.append((ref, val, info['size'], pm, po, prated, rt, ro, info['mpn']))
        if verdicts and (rt > 0.3 or ro > 0.7):
            summ('7', '%sRF heating %s %s %s' % (tag, ref, val, info['size']),
                 'PASS' if (rt <= 0.7 and ro <= 1.0) else ('MARGINAL' if rt <= 1.0 else 'FAIL'),
                 '%.0f mW matched = %.0f %% (typical Q %.0f %%) of its rated-current heating; %.0f mW antenna missing (%.0f %%)'
                 % (1e3 * pm, 100 * pm / prated, 100 * rt, 1e3 * po, 100 * po / prated))
    return worst


# Thermal data (ESTIMATES, makers publish none; followup.py 19 Oct): total part-to-ambient resistance from Murata's
# rated current (20 C rise at I_rated^2 x Rdc max): LQW2BAN3N6J00L 2.0 A, 50 mOhm -> 0.20 W -> 100 K/W;
# LQW15AN47NJ00D 0.21 A, 1.08 Ohm -> 48 mW -> 420 K/W, split part -> pads / pads -> ambient.  Heat capacity from
# volume x 3.4 J/cm3K plus board copper within ~5 mm.
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
        T[i], Bd[i] = tp, tb
    return np.arange(n) * dt, T, Bd


def study7b(b, ckt, resA):
    out()
    out('7b Antenna missing, transient: L15 (3.6 nH output match) and L18 (47 nH ESD shunt), worst phase, model A.')
    out('   Thermal data ESTIMATED (THERM: L15 35 / 65 K/W, 0.016 / 0.25 J/K; L18 200 / 220 K/W, 0.001 / 0.08 J/K).')
    out('   Criterion: part <= 125 C (Murata).  (i) no detector cut-off: 1 s bursts (single, and every 4 s = 25 % duty);')
    out('   (ii) with the firmware cut-off: the amplifier runs %.2f ms into the open, then once per retry (30 s, doubling'
        % (FW['t_sample'] * 1e3))
    out('   to 600 s), each retry at the 1 W setting.')
    ph = np.linspace(0, 2 * np.pi, 90, endpoint=False)
    w = 2 * np.pi * 915e6
    refs = {'L15': refs_between('PA_OUT', 'PA_M1')[0], 'L18': [c.ref for c in B.rf_parts(B.NETS_ANT)][0]}
    res = {}
    for vpa in (2.7, 3.6, 4.0):
        pa = resA[vpa][3]
        for name, ref in refs.items():
            b.value(ref)
            info = b.info[ref]
            a, bb = model_pins(ref)
            rac = float(R.Ind(info['value'], info['q'], info['fq'], info['srf'], info['rdc']).r(np.array([w]))[0, 0])
            L = float(np.atleast_1d(info['value'])[0])

            def p_of(g):
                v, _ = pa.solve(ckt, FB, g)
                va = v[a][0] if a != 'GND' else 0
                vb = v[bb][0] if bb != 'GND' else 0
                i = np.abs((va - vb) / (rac + 1j * w * L)) / math.sqrt(2)
                return float(np.max(i ** 2 * rac))
            res[(vpa, name)] = (p_of(0.0), max(p_of(np.exp(1j * p)) for p in ph), info['mpn'])
    out('   dissipation (W), matched / antenna missing:  ' + '   '.join(
        'VPA %.1f V: L15 %.3f / %.3f, L18 %.3f / %.3f' % (v, res[(v, 'L15')][0], res[(v, 'L15')][1], res[(v, 'L18')][0],
                                                          res[(v, 'L18')][1]) for v in (2.7, 3.6, 4.0)))
    out('   peak part / pad temperature (C), 60 C ambient:   single 1 s burst | 25 % duty | with the 0.75 ms cut-off')
    worst = {}
    curves = {}
    for name in ('L15', 'L18'):
        for vpa in (2.7, 3.6, 4.0):
            pm, po, mpn = res[(vpa, name)]
            th = THERM[mpn]
            _, a1, b1 = thermal(po, th, 60.0)
            t2, a2, b2 = thermal(po, th, 60.0, period=4.0)
            curves[(name, vpa)] = (t2, a2)
            # cut-off: energy P x t_sample into c1 (adiabatic, upper bound); retries far apart
            dcut = po * FW['t_sample'] / th['c1']
            worst[(name, vpa)] = (a1.max(), a2.max(), b2.max(), dcut)
            out('    %s VPA %.1f V, %.2f W:   %5.0f / %4.0f  |  %5.0f / %4.0f  |  +%.2f C per event' % (
                name, vpa, po, a1.max(), b1.max(), a2.max(), b2.max(), dcut))
    for name in ('L15', 'L18'):
        for vpa, label in ((2.7, '1 W setting, VPA 2.7 V'), (3.6, 'VPA 3.6 V'), (4.0, 'VPA 4.0 V')):
            s1, s25, pad, dcut = worst[(name, vpa)]
            summ('7b', '%s antenna missing, %s, 60 C, no cut-off' % (name, label), 'PASS' if s25 <= 125 else 'FAIL',
                 'single 1 s burst %.0f C, 25 %% duty %.0f C (pads %.0f C); limit 125 C; with the 0.75 ms cut-off +%.2f C'
                 % (s1, s25, pad, dcut))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for (name, vpa), col in ((('L15', 4.0), C2), (('L15', 3.6), C1), (('L15', 2.7), C3), (('L18', 4.0), C4)):
        t, T = curves[(name, vpa)]
        k = t >= 280
        ax.plot(t[k] - 280, T[k], color=col, lw=1.5, label='%s, VPA %.1f V, 60 C ambient' % (name, vpa))
    ax.axhline(125, color=CR, ls='--', lw=1, label='125 C part maximum')
    ax.set_xlabel('s (last 20 s of 300 s of 1 s bursts every 4 s, no detector cut-off)')
    ax.set_ylabel('part temperature, C')
    ax.set_title('Antenna missing: inductor temperature, 25 % duty (thermal data estimated)', fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'heating.png'), dpi=110)
    plt.close(fig)
    return worst


# ============================================================================ study 8: missing-antenna detector
def _fw_constants():
    """Detector thresholds from firmware/variant/variant.h (defaults if not found)."""
    fw = dict(v30=0.350, v35=0.730, tc=1.4e-3, t_sample=750e-6, min_dbm=27.0, src='defaults')
    try:
        txt = open(os.path.join(HERE, '..', '..', 'firmware', 'variant', 'variant.h')).read()
    except OSError:
        return fw
    import re
    for key, name, scale in (('ratio', 'OFFGRID_ANT_RATIO_MAX_PCT', 1e-2), ('fwd_min', 'OFFGRID_FWD_MIN_MV', 1e-3),
                             ('v30', 'OFFGRID_REFL_V30_MV', 1e-3), ('v35', 'OFFGRID_REFL_V35_MV', 1e-3),
                             ('tc', 'OFFGRID_REFL_TC_UV_PER_C', 1e-6), ('t_sample', 'OFFGRID_REFL_SAMPLE_US', 1e-6),
                             ('min_dbm', 'OFFGRID_REFL_MIN_DBM', 1.0)):
        m = re.search(r'#define\s+%s\s+([0-9.]+)' % name, txt)
        if m:
            fw[key] = float(m.group(1)) * scale
    fw['src'] = 'firmware/variant/variant.h'
    return fw


FW = _fw_constants()


def fw_threshold(p_dbm, t_c):
    """variant.cpp: V30 (V35/V30)^((P-30)/5) + TC (T - 25); P = the firmware's modelled U.FL power."""
    return FW['v30'] * (FW['v35'] / FW['v30']) ** ((p_dbm - 30.0) / 5.0) + FW['tc'] * (t_c - 25.0)


# Detector diode DC models (SPICE form: IS(T) = IS (T/T0)^(XTI/N) exp(EG/(N Vt) (T/T0 - 1))), plus a reverse leak
# g (S, scaled with IS(T)).
#   BAT68-04W (fitted, the part since 20 Oct): Infineon BAT68 data sheet (2011-06-15), typical IF-VF curves at -40, 25,
#   85 C digitised (12 uA - 2 mA) and fitted with XTI 2: IS 8.6e-10 A, N 0.932, RS 9.2 ohm, EG 0.65 eV (fit within
#   4 mV).  The curves sit at the table's VF maximum (340 mV at 1 mA); the table's typical 318 mV gives IS 2.35e-9.
#   No minimum VF is published: 296 mV (as far below typical as the max is above) ASSUMED -> IS 6.1e-9.  Leak: IR
#   5 nA at 0.5 V / 20 nA at 4 V, 25 C (fig.) -> 6 nS.  EG 0.60 / 0.70 eV as corners.
#   BAT15-02EL (the 19-20 Oct part): IS 1.15e-7, N 1.08 (typical curve), EG 0.55, leak 0.13 uS.
VT25 = 8.617e-5 * 298.15


def _is_from_vf(vf, n, i=1e-3, rs=0.0):
    return i / (math.exp((vf - i * rs) / (n * VT25)) - 1)


D68 = dict(n=0.932, rs=9.2, xti=2.0, eg=0.65)
D15 = dict(n=1.08, rs=6.0, xti=2.0, eg=0.55)
DIODE_SETS = {
    # BAT68-04W: VF at 1 mA 318 typ / 340 max mV (table); 296 mV ASSUMED as the low corner
    'BAT68_04W': {
        'typ':     dict(D68, is25=_is_from_vf(0.318, 0.932, rs=9.2), gleak=6e-9),
        'VF max':  dict(D68, is25=_is_from_vf(0.340, 0.932, rs=9.2), gleak=6e-9),
        'VF min':  dict(D68, is25=_is_from_vf(0.296, 0.932, rs=9.2), gleak=6e-9),
        'EG low':  dict(D68, is25=_is_from_vf(0.318, 0.932, rs=9.2), gleak=6e-9, eg=0.60),
        'EG high': dict(D68, is25=_is_from_vf(0.318, 0.932, rs=9.2), gleak=6e-9, eg=0.70)},
    # BAT15-02EL: VF at 1 mA 0.16 / 0.25 / 0.32 V (min / typ / max); EG not published: 0.55 (0.69 corner)
    'BAT15': {
        'typ':     dict(D15, is25=1.15e-7, gleak=0.13e-6),
        'VF max':  dict(D15, is25=_is_from_vf(0.32, 1.08), gleak=0.13e-6),
        'VF min':  dict(D15, is25=_is_from_vf(0.16, 1.08), gleak=0.13e-6),
        'EG low':  dict(D15, is25=1.15e-7, gleak=0.13e-6, eg=0.50),
        'EG high': dict(D15, is25=1.15e-7, gleak=0.13e-6, eg=0.69)},
}
DIODES = DIODE_SETS[B.DIODE_PART]
for _d in DIODES.values():          # the reverse leak scales with IS
    _d['gleak'] = _d['gleak'] * _d['is25'] / DIODES['typ']['is25']
# (reflected diode, forward diode): the two are separate parts, so they need not match
PAIRS = [('typ', 'typ'), ('VF max', 'VF min'), ('VF min', 'VF max'), ('VF max', 'VF max'), ('VF min', 'VF min'),
         ('EG low', 'EG high'), ('EG high', 'EG low')]
DET_TEMPS = (-40, 0, 25, 60, 85)
DET_POWERS = (27.0, 30.0, 33.0, 35.0, 36.0)


def _det_rc():
    r = [B.parts.PARTS[c.part] for c in B.rf_parts(['REFL_DET'])]
    rl = [R.parse_value(p['value']) for p in r if p['kind'] == 'R'][0]
    cl = [R.parse_value(p['value']) for p in r if p['kind'] == 'C'][0]
    return rl, cl


RL_DET, CL_DET = _det_rc()


def diode_is(d, t_c):
    t = t_c + 273.15
    r = t / 298.15
    return d['is25'] * r ** (d['xti'] / d['n']) * math.exp(d['eg'] / (d['n'] * 8.617e-5 * t) * (r - 1))


def diode_mean_current(va, v, t_c, d):
    """Mean junction current with RF peak va across the junction and DC v on the cathode (anode at DC 0)."""
    from scipy.special import i0e
    nvt = d['n'] * 8.617e-5 * (t_c + 273.15)
    isat = diode_is(d, t_c)
    x = va / nvt
    return isat * (i0e(x) * math.exp(x - v / nvt) - 1) - d['gleak'] * isat / d['is25'] * v


def det_vdc(va, t_c, d=None):
    """Detector DC: mean diode current = V / 100 k (the 1 nF holds the cathode at RF ground)."""
    from scipy.optimize import brentq
    d = d or DIODES['typ']
    if va <= 1e-6:
        return 0.0
    f = lambda v: diode_mean_current(va, v, t_c, d) - v / RL_DET
    return brentq(f, 0.0, va + 0.5)


_VTAB = {}


def det_v(a, t_c, dname):
    """det_vdc for an array of amplitudes, through a table on a log grid (exact to < 0.1 mV)."""
    key = (t_c, dname)
    if key not in _VTAB:
        g = np.logspace(-3, np.log10(6.0), 400)
        _VTAB[key] = (np.log(g), np.array([det_vdc(x, t_c, DIODES[dname]) for x in g]))
    lg, vv = _VTAB[key]
    return np.interp(np.log(np.maximum(a, 1e-3)), lg, vv)


def det_rise(va, t_c, d=None, frac=0.99, r_src=31.0):
    """Time for the detector to reach `frac` of its final value after the RF steps on (1 nF charged through the
    diode; while far below its final value the diode current is limited by the source and RS: at most
    va / (pi r_src) on average), and the 100 k x 1 nF decay constant.  Steps limited to 1 mV."""
    d = d or DIODES['typ']
    vf = det_vdc(va, t_c, d)
    v, t = 0.0, 0.0
    while v < frac * vf and t < 2e-3:
        i = min(diode_mean_current(va, v, t_c, d), max(va - v, 0.0) / (math.pi * r_src)) - v / RL_DET
        dt = min(1e-7, 1e-3 * CL_DET / max(abs(i), 1e-12))
        v += i * dt / CL_DET
        t += dt
    return t, RL_DET * CL_DET


ANTS = (('matched', 0.0), ('VSWR 2', 1.0 / 3.0), ('missing', 1.0))


def det_amplitudes(b, model, p_dbm, gm, cathode='designed', gap=None, nph=48, pa36=None, cj=None):
    """RF peak across the reflected and the forward diode junctions, and at the 49.9 R, for every phase of an
    antenna reflection of magnitude gm and 902/915/928 MHz.  model 'A': saturated PA scaled so a matched antenna
    gets p_dbm at the U.FL; 'B': 50-ohm source, same matched power.  Returns (refl, fwd, v_term) arrays."""
    ph = [0.0] if gm == 0 else np.linspace(0, 2 * np.pi, nph, endpoint=False) + 0.01
    ar, af, vt = [], [], []
    if model == 'A':
        ckt = b.tx_out(with_pa=True, cathode=cathode, gap=gap, cj=cj)
        p36 = pa36 or PA(3.6)
        v0, _ = p36.solve(ckt, [915e6], 0.0)
        p_now = float(R.w_to_dbm(abs(v0['ANT'][0, 0]) ** 2 / (2 * R.Z0)))
        pa = PA(3.6 * 10 ** ((p_dbm - p_now) / 20))
        for p in ph:
            v, _ = pa.solve(ckt, FB, gm * np.exp(1j * p))
            ar.append(np.abs(v['REFL_J'][0] - v['REFL_K'][0]))
            af.append(np.abs(v['FWD_J'][0] - v['FWD_K'][0]))
            vt.append(np.abs(v['REFL_T'][0]))
    else:
        ct = b.tx_out(with_pa=False, cathode=cathode, gap=gap, cj=cj)
        S = ct.sparams(FB, ['PA_M2', 'ANT'])[0]
        pav = R.dbm_to_w(p_dbm - R.db20(S[:, 1, 0]))
        vinc = np.sqrt(8 * R.Z0 * pav)
        for p in ph:
            v = ct.voltages(FB, {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                                'ANT': ant_load(gm * np.exp(1j * p))})
            ar.append(np.abs(v['REFL_J'][0] - v['REFL_K'][0]))
            af.append(np.abs(v['FWD_J'][0] - v['FWD_K'][0]))
            vt.append(np.abs(v['REFL_T'][0]))
    return np.ravel(ar), np.ravel(af), np.ravel(vt)


def det_table(b, powers=DET_POWERS, **kw):
    """{(P, antenna, model): (refl amplitudes, fwd amplitudes, v_term)}."""
    pa36 = kw.pop('pa36', None) or PA(3.6)
    return {(p, name, m): det_amplitudes(b, m, p, gm, pa36=pa36, **kw)
            for p in powers for name, gm in ANTS for m in ('A', 'B')}


def det_readings(tab, pairs=None, temps=DET_TEMPS, dp=0.0):
    """{(P, antenna, T, pair): (Vrefl, Vfwd, ratio) arrays over both PA models, phase and band}.  dp shifts the
    actual power (dB) against the nominal (the ratio needs no power model; dp tests the FWD trust level)."""
    out_ = {}
    k = 10 ** (dp / 20)
    for (p, name, m), (ar, af, vt) in tab.items():
        for t in temps:
            for pr in (pairs or [('typ', 'typ')]):
                vr = det_v(ar * k, t, pr[0])
                vf = det_v(af * k, t, pr[1])
                key = (p, name, t, pr)
                r0 = out_.get(key)
                cur = (vr, vf, vr / np.maximum(vf, 1e-4))
                out_[key] = cur if r0 is None else tuple(np.concatenate([a, c]) for a, c in zip(r0, cur))
    return out_


def ratio_window(rd, powers):
    """Highest VSWR-2 ratio and lowest missing ratio over everything in rd at these powers."""
    hi = max(float(rd[k][2].max()) for k in rd if k[0] in powers and k[1] == 'VSWR 2')
    lo = min(float(rd[k][2].min()) for k in rd if k[0] in powers and k[1] == 'missing')
    return hi, lo


def spice_check(b, cases):
    """Cross-check the averaged diode solve with ngspice (transient, the fitted SPICE diode with RS and CJ) for the
    reflected diode, model B, 915 MHz: the board's network at its anode reduced to its Thevenin equivalent."""
    import re
    import shutil
    import subprocess
    import tempfile
    if not shutil.which('ngspice'):
        out('   ngspice not found: SPICE cross-check skipped')
        return []
    d = DIODES['typ']
    dr = B.DIODE_RF[B.DIODE_PART]
    rows = []
    co = b.tx_out(with_pa=False, cathode='open')
    ct = b.tx_out(with_pa=False)
    S = co.sparams([915e6], ['PA_M2', 'ANT'])[0]
    pav = R.dbm_to_w(np.array([0.0]) - R.db20(S[:, 1, 0]))
    for p_dbm, gm, pick, t_c, label in cases:
        vinc = np.sqrt(8 * R.Z0 * pav * 10 ** (p_dbm / 10))
        phs = np.linspace(0, 2 * np.pi, 72, endpoint=False) + 0.01

        def amp(q):
            v = ct.voltages([915e6], {'PA_M2': vinc / R.Z0}, loads={'PA_M2': lambda w: np.ones(w.shape) / R.Z0,
                                                                     'ANT': ant_load(gm * np.exp(1j * q))})
            return abs(v['REFL_J'][0, 0] - v['REFL_K'][0, 0])
        am = [amp(q) for q in phs]
        gam = gm * np.exp(1j * phs[int(np.argmin(am) if pick == 'min' else np.argmax(am))])
        load = {'PA_M2': lambda w: np.ones(w.shape) / R.Z0, 'ANT': ant_load(gam)}
        voc = complex(co.voltages([915e6], {'PA_M2': vinc / R.Z0}, loads=load)['REFL_A'][0, 0])
        zth = complex(co.voltages([915e6], {'REFL_A': 1.0}, loads=load)['REFL_A'][0, 0])
        w0 = 2 * math.pi * 915e6
        xel = ('L1 x a %.6g' % (zth.imag / w0)) if zth.imag > 0 else ('C1 x a %.6g' % (-1 / (w0 * zth.imag)))
        va = amp(np.angle(gam) if gm else 0.0)
        vpy = det_vdc(va, t_c, d)
        net = '\n'.join([
            '* detector check',
            'V1 s 0 SIN(0 %.6g 915e6)' % abs(voc),
            'R1 s x %.6g' % max(zth.real, 1e-3),
            xel,
            'LS a ai %.4g' % dr['ls'],
            'D1 ai k DET temp=%g' % t_c,
            'RLK ai k %.4g' % (1 / d['gleak']),
            'CL k kc %.6g' % CL_DET,
            'LC kc 0 0.45n',
            'RL k 0 %.6g' % RL_DET,
            '.model DET D(IS=%.4g N=%.4g RS=%.3g CJO=0.75p M=0.3 VJ=0.35 EG=%.3g XTI=%.3g BV=8 IBV=10u)'
            % (d['is25'], d['n'], d['rs'], d['eg'], d['xti']),
            '.ic v(k)=%.5g v(kc)=0' % vpy,
            '.options temp=%g tnom=25' % t_c,
            '.tran 25p 25u 0 25p uic',
            '.meas tran vavg AVG v(k) from=23u to=25u',
            '.end', ''])
        with tempfile.TemporaryDirectory() as td:
            fn = os.path.join(td, 'det.cir')
            open(fn, 'w').write(net)
            r = subprocess.run(['ngspice', '-b', fn], capture_output=True, text=True, timeout=900)
        m = re.search(r'vavg\s*=\s*([-0-9.eE+]+)', r.stdout)
        vsp = float(m.group(1)) if m else float('nan')
        rows.append((label, p_dbm, t_c, va, vpy, vsp))
        out('   %-24s %2.0f dBm %4d C  junction %.3f V peak   averaged model %.3f V   ngspice %.3f V   (diff %+.0f mV)'
            % (label, p_dbm, t_c, va, vpy, vsp, 1e3 * (vsp - vpy)))
    return rows


ADC_FLOOR = 0.020     # V: below ~20 mV (23 LSB at gain 1/6, 12 bit) the nRF52840 SAADC's offset makes a ratio meaningless


def fit_threshold(rd, powers, keys=None):
    """Ratio threshold of the form R(P, T) = exp(a + b (T - 25) + c (P - 30)) centred in the window between the
    highest VSWR-2 ratio and the lowest missing ratio at every (P, T) in rd.  Returns (a, b, c, half-window ln)."""
    cells = sorted({(k[0], k[2]) for k in rd if k[0] in powers})
    lo, hi = {}, {}
    for (p, t) in cells:
        lo[(p, t)] = math.log(max(max(float(rd[k][2].max()) for k in rd if k[0] == p and k[2] == t and k[1] == 'VSWR 2'
                                      and (keys is None or k[3] in keys)), 1e-6))
        hi[(p, t)] = math.log(max(min(float(rd[k][2].min()) for k in rd if k[0] == p and k[2] == t and k[1] == 'missing'
                                      and (keys is None or k[3] in keys)), 1e-6))
    best = None
    for b in np.linspace(-0.03, 0.03, 121):
        for c in np.linspace(-0.3, 0.3, 61):
            l_ = [lo[q] - b * (q[1] - 25) - c * (q[0] - 30) for q in cells]
            h_ = [hi[q] - b * (q[1] - 25) - c * (q[0] - 30) for q in cells]
            half = 0.5 * (min(h_) - max(l_))
            if best is None or half > best[3]:
                best = (0.5 * (min(h_) + max(l_)), b, c, half)
    return best


def thr_fn(fit):
    a, b, c, _ = fit
    return lambda p, t: math.exp(a + b * (t - 25) + c * (p - 30))


def two_rule(rd, powers):
    """Fault if FWD_DET < Fmin(P, T) OR REFL/FWD > R(P, T).  Fmin = 80 % of the lowest forward reading any good
    antenna (matched or VSWR 2) gives at that level and temperature, over every pairing, model, phase; then
    log Fmin fitted as a + b (T-25) + c (P-30) and moved down to stay under every cell.  R fitted (as fit_threshold)
    between the VSWR-2 ratios and the missing ratios NOT already caught by Fmin.  Returns (fmin_fit, r_fit, cells)
    with cells[(P, T)] = (good margin dB, missing margin dB, Fmin, R)."""
    cells = sorted({(k[0], k[2]) for k in rd if k[0] in powers})
    fgood = {q: min(float(rd[k][1].min()) for k in rd if (k[0], k[2]) == q and k[1] in ('matched', 'VSWR 2')) for q in cells}
    X = np.array([[1.0, q[1] - 25.0, q[0] - 30.0] for q in cells])
    y = np.log(np.maximum([0.8 * fgood[q] for q in cells], 1e-6))
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    coef[0] -= max(0.0, float(np.max(X @ coef - y)))
    fmin = lambda p, t: math.exp(coef[0] + coef[1] * (t - 25) + coef[2] * (p - 30))
    rd2 = {}
    for k, (vr, vf, ra) in rd.items():
        if k[1] == 'missing':
            keep = vf >= fmin(k[0], k[2])
            rd2[k] = (vr[keep], vf[keep], ra[keep]) if keep.any() else (np.array([1.0]), np.array([1.0]), np.array([9.0]))
        else:
            rd2[k] = (vr, vf, ra)
    rf = fit_threshold(rd2, powers)
    th = thr_fn(rf)
    out_ = {}
    for q in cells:
        fm, r_ = fmin(*q), th(*q)
        g, m = 99.0, 99.0
        for k in rd:
            if (k[0], k[2]) != q:
                continue
            vr, vf, ra = rd[k]
            if k[1] == 'missing':
                det = np.maximum(np.log(fm / np.maximum(vf, 1e-6)), np.log(np.maximum(ra, 1e-9) / r_))
                m = min(m, float(det.min()) * 8.686)
            else:
                ok = np.minimum(np.log(np.maximum(vf, 1e-6) / fm), np.log(r_ / np.maximum(ra, 1e-9)))
                g = min(g, float(ok.min()) * 8.686)
        out_[q] = (g, m, fm, r_)
    return coef, rf, out_



def study8(s7):
    dp = B.parts.PARTS.get(B.DIODE_PART, {}).get('mpn', B.DIODE_PART)
    out()
    out('=' * 100)
    out('STUDY 8  Missing-antenna ratio detector: coupler (%.1f mm, %.2f mm gap) terminated in 49.9 R at both ends;'
        % (B.GEOM['cpl_len'], B.GEOM['gap']))
    out('         REFL_DET = %s at the U.FL end, FWD_DET = the same at the filter end, each into 1 nF || 100 k;' % dp)
    out('         firmware reads REFL_DET / FWD_DET' + ('   [COMPARISON RUN: RF_DIODE=%s]' % B.DIODE_PART
                                                      if os.environ.get('RF_DIODE') else ''))
    out('=' * 100)
    out('Inputs.  Board: the antenna section of study 1 (coupler from coupler.py\'s field solve) inside the real chain: PA,')
    out('  LPF, switch, %s; both PA models, so the PA\'s own reflection of the returning wave is included.  Antenna at' % FLT)
    out('  the U.FL: matched; VSWR 2 at every phase; missing (open, every phase = any cable length); 902/915/928 MHz.')
    out('  Power = the matched-antenna power at the U.FL: 27 dBm (the firmware\'s lowest checked level), 30 (US; the 1 W')
    out('  probe), 33, 35 and 36 dBm (3.6-4.0 V).  Temperatures -40, 0, 25, 60, 85 C.')
    d = DIODES['typ']
    out('  Diode %s: IS %.2e A (typ), N %.3f, RS %.1f ohm, EG %.2f eV, XTI 2; corners IS %.2e / %.2e A (VF limits at 1 mA),'
        % (dp, d['is25'], d['n'], d['rs'], d['eg'], DIODES['VF max']['is25'], DIODES['VF min']['is25']))
    out('  EG %.2f / %.2f eV; CJ %.2f pF (%.2f max as a corner).  The two diodes are separate parts: unmatched pairings are run'
        % (DIODES['EG low']['eg'], DIODES['EG high']['eg'], 1e12 * B.DIODE_RF[B.DIODE_PART]['cj'],
           1e12 * B.DIODE_RF[B.DIODE_PART]['cj_max']))
    out('  (%d: reflected / forward = %s).  BAT68: IF-VF curves at -40/25/85 C fitted (N 0.932, RS 9.2, EG 0.65, within 4 mV);'
        % (len(PAIRS), ', '.join('%s/%s' % p for p in PAIRS)))
    out('  the table\'s VF 318 typ / 340 max mV at 1 mA set IS; 296 mV ASSUMED as the low corner.  DC: mean diode current over')
    out('  an RF cycle = V / 100 k + leak (checked against ngspice below).  ADC floor: a reading below %.0f mV is not trusted.'
        % (1e3 * ADC_FLOOR))
    out('Criteria: a ratio threshold (fixed, or of the form R25 x exp(b (T-25) + c (P-30)) with the board temperature and the')
    out('  firmware\'s modelled power) must separate every missing case from every VSWR-2 case at every level and temperature,')
    out('  both PA models, every diode pairing: PASS with >= 1 dB of margin each side (and FWD_DET above the ADC floor),')
    out('  MARGINAL if the window is open but narrower, FAIL if it closes.')
    b = B.Board()
    pa36 = PA(3.6)
    tab = det_table(b, pa36=pa36)
    rd = det_readings(tab, pairs=PAIRS)
    typ = {k: v for k, v in rd.items() if k[3] == ('typ', 'typ')}
    out()
    out('  Typical diodes (both models, every phase and band): FWD_DET, REFL_DET (V) and REFL / FWD:')
    out('   P       antenna     T      FWD_DET         REFL_DET        ratio')
    for p in (27.0, 30.0, 35.0):
        for name, gm in ANTS:
            for t in (-40, 25, 85):
                vr, vf, ra = typ[(p, name, t, ('typ', 'typ'))]
                out('   %2.0f dBm  %-9s %4d C   %.3f-%.3f V   %.3f-%.3f V   %.3f-%.3f' % (
                    p, name, t, vf.min(), vf.max(), vr.min(), vr.max(), ra.min(), ra.max()))
    # 1) one fixed ratio
    hi_t, lo_t = ratio_window(typ, DET_POWERS)
    hi_a, lo_a = ratio_window(rd, DET_POWERS)
    out()
    out('  (1) One fixed ratio over 27-36 dBm and -40..85 C: VSWR 2 up to %.3f, missing down to %.3f with typical diodes'
        ' (%+.1f dB); %.3f / %.3f over every pairing (%+.1f dB)' % (hi_t, lo_t, R.db20(lo_t / hi_t), hi_a, lo_a,
                                                                    R.db20(lo_a / hi_a)))
    # 2) compensated threshold, by level: find the lowest level from which it works
    out('  (2) Threshold compensated for temperature and level, fitted over every pairing, from a lowest level up:')
    fits = {}
    for p0 in DET_POWERS:
        pw = tuple(p for p in DET_POWERS if p >= p0)
        f = fit_threshold(rd, pw)
        fmin = min(float(rd[k][1].min()) for k in rd if k[0] == p0)
        fits[p0] = (f, fmin)
        out('      from %2.0f dBm: margin %+5.1f dB each side; R(30 dBm, 25 C) %.3f, %+.2f %%/C, %+.1f %%/dB; FWD_DET >= %.3f V'
            % (p0, 20 * f[3] / math.log(10), math.exp(f[0]), 100 * (math.exp(f[1]) - 1), 100 * (math.exp(f[2]) - 1), fmin))
    ok = [p0 for p0 in DET_POWERS if 20 * fits[p0][0][3] / math.log(10) >= 1.0 and fits[p0][1] >= ADC_FLOOR]
    p_lo = min(ok) if ok else None
    fsel = fits[p_lo][0] if p_lo is not None else fits[max(DET_POWERS)][0]
    th = thr_fn(fsel)
    out('  -> %s' % ('works (>= 1 dB, FWD_DET above the ADC floor) from %.0f dBm up' % p_lo if p_lo is not None else
                     'no level range gives 1 dB of margin with FWD_DET above the ADC floor'))
    # 3) the two-condition rule
    out()
    out('  (3) Two conditions: fault if FWD_DET < Fmin(P, T) (the amplifier is not delivering what the model says - with a')
    out('      saturated PA that is what an open does at some cable lengths) OR REFL/FWD > R(P, T):')
    best2 = None
    for p0 in DET_POWERS:
        pw = tuple(p for p in DET_POWERS if p >= p0)
        cf, rf2, cl = two_rule(rd, pw)
        mg = min(min(g, m) for g, m, _, _ in cl.values())
        flo = min(fm for _, _, fm, _ in cl.values())
        out('      from %2.0f dBm: worst margin %+5.1f dB (good antenna / missing, every pairing); Fmin(30 dBm, 25 C) %.3f V,'
            ' %+.2f %%/C, %+.1f %%/dB (lowest %.3f V); R(30, 25) %.3f, %+.2f %%/C, %+.1f %%/dB'
            % (p0, mg, math.exp(cf[0]), 100 * (math.exp(cf[1]) - 1), 100 * (math.exp(cf[2]) - 1), flo,
               math.exp(rf2[0]), 100 * (math.exp(rf2[1]) - 1), 100 * (math.exp(rf2[2]) - 1)))
        if best2 is None and mg >= 1.0 and flo >= ADC_FLOOR:
            best2 = (p0, cf, rf2, cl)
    if best2:
        p0, cf, rf2, cl = best2
        out('  -> two conditions work (>= 1 dB, Fmin above the ADC floor) from %.0f dBm up.  Per level and temperature'
            ' (margin dB good / missing):' % p0)
        for p in [x for x in DET_POWERS if x >= p0]:
            out('      %2.0f dBm: ' % p + ',  '.join('%d C %+.1f / %+.1f (Fmin %.3f V, R %.3f)' % (
                t, cl[(p, t)][0], cl[(p, t)][1], cl[(p, t)][2], cl[(p, t)][3]) for t in DET_TEMPS))
        summ('8', 'ratio detector (%s), two conditions (FWD_DET low or ratio high)' % dp,
             'PASS' if p0 <= 30.0 else 'MARGINAL',
             'works from %.0f dBm (every pairing, both PA models, -40..85 C), worst margin %+.1f dB; Fmin(30 dBm, 25 C) %.3f V'
             ' %+.2f %%/C %+.1f %%/dB; R(30 dBm, 25 C) %.3f %+.2f %%/C %+.1f %%/dB'
             % (p0, min(min(g, m) for g, m, _, _ in cl.values()), math.exp(cf[0]), 100 * (math.exp(cf[1]) - 1),
                100 * (math.exp(cf[2]) - 1), math.exp(rf2[0]), 100 * (math.exp(rf2[1]) - 1), 100 * (math.exp(rf2[2]) - 1)))
        # the firmware's power model against the real power: +-1 dB (unit gain, loss, supply)
        fm_f = lambda p, t: math.exp(cf[0] + cf[1] * (t - 25) + cf[2] * (p - 30))
        th_f = thr_fn(rf2)
        res_dp = {}
        for dpw in (-1.0, 1.0):
            rdp = det_readings(tab, pairs=PAIRS, dp=dpw)
            g, m = 99.0, 99.0
            for k, (vr, vf, ra) in rdp.items():
                if k[0] < p0:
                    continue
                fm, r_ = fm_f(k[0], k[2]), th_f(k[0], k[2])
                if k[1] == 'missing':
                    m = min(m, 8.686 * float(np.maximum(np.log(fm / np.maximum(vf, 1e-6)),
                                                        np.log(np.maximum(ra, 1e-9) / r_)).min()))
                else:
                    g = min(g, 8.686 * float(np.minimum(np.log(np.maximum(vf, 1e-6) / fm),
                                                        np.log(r_ / np.maximum(ra, 1e-9))).min()))
            res_dp[dpw] = (g, m)
        out('      real power 1 dB below the firmware model: good antenna %+.1f dB, missing %+.1f dB;'
            ' 1 dB above: good %+.1f dB, missing %+.1f dB  (worst over every pairing, model, phase, T)'
            % (res_dp[-1.0] + res_dp[1.0]))
        # the same rule fitted with the 1 dB built in: good antennas at -1 dB, missing at +1 dB
        rdm, rdp_ = det_readings(tab, pairs=PAIRS, dp=-1.0), det_readings(tab, pairs=PAIRS, dp=1.0)
        rdc = {k: (rdp_[k] if k[1] == 'missing' else rdm[k]) for k in rd}
        best3 = None
        for p1 in DET_POWERS:
            pw = tuple(p for p in DET_POWERS if p >= p1)
            c3, r3, cl3 = two_rule(rdc, pw)
            mg3 = min(min(g, m) for g, m, _, _ in cl3.values())
            if best3 is None and mg3 > 0 and min(fm for _, _, fm, _ in cl3.values()) >= ADC_FLOOR:
                best3 = (p1, c3, r3, cl3, mg3)
        if best3:
            p1, c3, r3, cl3, mg3 = best3
            out('  -> fitted with +-1 dB of power error built in (good antennas 1 dB low, missing 1 dB high): works from %.0f dBm,'
                ' worst margin %+.1f dB:' % (p1, mg3))
            out('     Fmin(P, T) = %.3f V x %.4f^(T-25) x %.3f^(P-30);  R(P, T) = %.3f x %.4f^(T-25) x %.3f^(P-30)'
                % (math.exp(c3[0]), math.exp(c3[1]), math.exp(c3[2]), math.exp(r3[0]), math.exp(r3[1]), math.exp(r3[2])))
            for p in [x for x in DET_POWERS if x >= p1]:
                out('      %2.0f dBm: ' % p + ',  '.join('%d C %+.1f / %+.1f (Fmin %.3f V, R %.3f)' % (
                    t, cl3[(p, t)][0], cl3[(p, t)][1], cl3[(p, t)][2], cl3[(p, t)][3]) for t in DET_TEMPS))
            summ('8', 'two conditions, fitted with +-1 dB of power-model error', 'PASS' if (p1 <= 30 and mg3 >= 1) else
                 'MARGINAL',
                 'from %.0f dBm, worst margin %+.1f dB: Fmin %.3f V x %.4f^(T-25) x %.3f^(P-30), R %.3f x %.4f^(T-25) x '
                 '%.3f^(P-30)' % (p1, mg3, math.exp(c3[0]), math.exp(c3[1]), math.exp(c3[2]), math.exp(r3[0]),
                                  math.exp(r3[1]), math.exp(r3[2])))
        else:
            summ('8', 'two conditions, fitted with +-1 dB of power-model error', 'FAIL', 'no level range works')
        summ('8', 'two conditions with +-1 dB between the power model and the real power',
             'PASS' if min(min(v) for v in res_dp.values()) > 0 else 'MARGINAL',
             '-1 dB: good antenna %+.1f, missing %+.1f dB; +1 dB: good %+.1f, missing %+.1f dB (a negative good-antenna'
             ' margin = a false "antenna missing" and a 1 W retry, not a missed fault)' % (res_dp[-1.0] + res_dp[1.0]))
    else:
        summ('8', 'ratio detector (%s), two conditions (FWD_DET low or ratio high)' % dp, 'FAIL', 'no level range works')
    # 4) the firmware as committed: trip if FWD_DET >= FWD_MIN and REFL/FWD > RATIO; while FWD_DET < FWD_MIN, the old
    #    absolute REFL_DET thresholds
    if 'ratio' in FW:
        out()
        out('  (4) The firmware as committed (%s): trip if FWD_DET >= %.0f mV and REFL/FWD > %.2f; while FWD_DET is lower, the'
            % (FW['src'], 1e3 * FW['fwd_min'], FW['ratio']))
        out('      old REFL_DET thresholds (%.0f / %.0f mV, +%.1f mV/C).  Worst margin (dB) per level, every pairing, both models,'
            % (1e3 * FW['v30'], 1e3 * FW['v35'], 1e3 * FW['tc']))
        out('      -40..85 C (good antenna / missing; missing via the ratio or the fallback, whichever applies):')
        fw_g, fw_m = 99.0, 99.0
        for p in (30.0, 33.0, 35.0, 36.0):
            g, m = 99.0, 99.0
            for k, (vr, vf, ra) in rd.items():
                if k[0] != p:
                    continue
                big = vf >= FW['fwd_min']
                rl = 8.686 * np.log(np.maximum(ra, 1e-9) / FW['ratio'])
                fb = 8.686 * np.log(np.maximum(vr, 1e-6) / fw_threshold(p, k[2]))
                mm = np.where(big, rl, fb)
                if k[1] == 'missing':
                    m = min(m, float(mm.min()))
                else:
                    g = min(g, float((-mm).min()))
            fw_g, fw_m = min(fw_g, g), min(fw_m, m)
            out('      %2.0f dBm: good %+6.1f dB, missing %+6.1f dB%s' % (p, g, m, '   <- a missing antenna passes' if m < 0 else ''))
        summ('8', 'detector rule as in firmware %s' % FW['src'].split('/')[-1], 'PASS' if min(fw_g, fw_m) >= 1 else
             ('MARGINAL' if min(fw_g, fw_m) > 0 else 'FAIL'),
             'FWD >= %.0f mV and ratio > %.2f, else the old REFL thresholds: worst good %+.1f dB, missing %+.1f dB (30-36 dBm); '
             'use the two-condition rule (FWD_DET low = fault, not "wait")' % (1e3 * FW['fwd_min'], FW['ratio'], fw_g, fw_m))
    # margins table with the selected threshold
    out()
    out('  Margins with that threshold (dB, + = read correctly; typical pair [worst pairing]):')
    out('   P        T     threshold   VSWR-2 max          missing min         matched max   FWD_DET min (V)')
    rows = []
    for p in DET_POWERS:
        for t in DET_TEMPS:
            tr = th(p, t)
            v2 = float(rd[(p, 'VSWR 2', t, ('typ', 'typ'))][2].max())
            mi = float(rd[(p, 'missing', t, ('typ', 'typ'))][2].min())
            ma = float(rd[(p, 'matched', t, ('typ', 'typ'))][2].max())
            v2w = max(float(rd[(p, 'VSWR 2', t, pr)][2].max()) for pr in PAIRS)
            miw = min(float(rd[(p, 'missing', t, pr)][2].min()) for pr in PAIRS)
            fm = min(float(rd[(p, n_, t, pr)][1].min()) for n_, _ in ANTS for pr in PAIRS)
            rows.append((p, t, tr, R.db20(tr / v2), R.db20(mi / tr), R.db20(tr / v2w), R.db20(miw / tr), fm))
            out('   %2.0f dBm %4d C   %.3f    %.3f (%+5.1f) [%+5.1f]   %.3f (%+5.1f) [%+5.1f]   %.3f        %.3f%s' % (
                p, t, tr, v2, R.db20(tr / v2), R.db20(tr / v2w), mi, R.db20(mi / tr), R.db20(miw / tr), ma, fm,
                '   <- below the ADC floor' if fm < ADC_FLOOR else ''))
    in_rng = [r for r in rows if p_lo is not None and r[0] >= p_lo]
    m_typ = min(min(r[3], r[4]) for r in rows if r[0] >= (p_lo or 99)) if in_rng else min(min(r[3], r[4]) for r in rows)
    m_all = min(min(r[5], r[6]) for r in in_rng) if in_rng else min(min(r[5], r[6]) for r in rows)
    m30 = min(min(r[5], r[6]) for r in rows if r[0] == 30.0)
    f30 = min(r[7] for r in rows if r[0] == 30.0)
    v = 'PASS' if (p_lo is not None and p_lo <= 30.0) else ('MARGINAL' if p_lo is not None else 'FAIL')
    summ('8', 'ratio detector (%s), compensated threshold' % dp, v,
         'works from %s; at the 30 dBm probe worst margin %+.1f dB, FWD_DET >= %.3f V; fixed ratio: %+.1f dB (typical), '
         '%+.1f dB (every pairing)' % ('%.0f dBm' % p_lo if p_lo is not None else 'no level', m30, f30,
                                       R.db20(lo_t / hi_t) / 2, R.db20(lo_a / hi_a) / 2))
    # sensitivity
    out()
    out('  Sensitivity, with that threshold (typical diodes; worst margin dB from %s, VSWR 2 / missing):'
        % ('%.0f dBm' % p_lo if p_lo else '27 dBm'))
    sens = []
    pw = tuple(p for p in DET_POWERS if p >= (p_lo or 27.0))
    for lab, kw in (('coupler gap %.2f mm (etch)' % round(B.GEOM['gap'] - 0.02, 3), dict(gap=round(B.GEOM['gap'] - 0.02, 3))),
                    ('coupler gap %.2f mm (etch)' % round(B.GEOM['gap'] + 0.02, 3), dict(gap=round(B.GEOM['gap'] + 0.02, 3))),
                    ('CJ %.2f pF (data-sheet max)' % (1e12 * B.DIODE_RF[B.DIODE_PART]['cj_max']),
                     dict(cj=B.DIODE_RF[B.DIODE_PART]['cj_max'])),
                    ('REFL_DET 1 nF / 100 k as PLACED (21 mm)', dict(cathode='placed'))):
        tb = det_table(b, pa36=pa36, powers=pw, **kw)
        rdx = det_readings(tb)
        mv2 = min(R.db20(th(k[0], k[2]) / float(v_[2].max())) for k, v_ in rdx.items() if k[1] == 'VSWR 2')
        mmi = min(R.db20(float(v_[2].min()) / th(k[0], k[2])) for k, v_ in rdx.items() if k[1] == 'missing')
        sens.append((lab, mv2, mmi))
        out('   %-42s %+5.1f / %+5.1f%s' % (lab, mv2, mmi, '   <- misread' if min(mv2, mmi) < 0 else ''))
    # timing
    out()
    a_m = float(tab[(30.0, 'missing', 'A')][0].min())
    tr1, tau = det_rise(a_m, -40)
    tr2, _ = det_rise(float(tab[(30.0, 'matched', 'B')][1].min()), -40)
    out('  Timing (30 dBm, -40 C): REFL_DET (missing, worst phase) reaches 99 %% of its final value %.0f us after the RF is at'
        ' full power, FWD_DET %.0f us; decay 100 k x 1 nF = %.0f us.  The %.0f us sample (from startTransmit) needs the RF at'
        % (1e6 * tr1, 1e6 * tr2, 1e6 * tau, 1e6 * FW['t_sample']))
    out('  full power by ~%.0f us.  Read both channels in one SAADC scan so a still-rising level moves both alike.'
        % (1e6 * (FW['t_sample'] - max(tr1, tr2))))
    # stress on the detector parts
    out()
    worst_rev, worst_term = 0.0, 0.0
    for vpa in (2.7, 3.6, 4.0):
        pdbm = float(s7['resA'][vpa][0][1])
        tb = det_table(b, pa36=pa36, powers=(pdbm,))
        rev, term = 0.0, 0.0
        for name, gm in ANTS:
            for m in ('A', 'B'):
                ar, af, vt = tb[(pdbm, name, m)]
                for a in (ar, af):
                    rev = max(rev, float(np.max(det_v(a, 85, 'VF min') + a)))
                term = max(term, float(vt.max()))
        worst_rev, worst_term = max(worst_rev, rev), max(worst_term, term)
        out('  VPA %.1f V (%.1f dBm), every antenna state, both models: diode reverse peak %.2f V, 49.9 R (each) %.0f mW'
            ' (0805 0.5 W: %.0f %% of its 85 C rating)' % (vpa, pdbm, rev, term ** 2 / (2 * 49.9) * 1e3,
                                                           100 * term ** 2 / (2 * 49.9) / r0805_rating(85, p70=0.5)))
    vr_max = {'BAT68_04W': 8.0, 'BAT15': 4.0}.get(B.DIODE_PART, 4.0)
    prt = worst_term ** 2 / (2 * 49.9) / r0805_rating(85, p70=0.5)
    summ('8', 'detector parts, antenna missing, VPA 4.0 V', 'PASS' if (worst_rev <= 0.7 * vr_max and prt <= 0.7) else
         ('MARGINAL' if worst_rev <= 0.95 * vr_max else 'FAIL'),
         '%s reverse peak %.2f V = %.0f %% of %.0f V; 49.9 R %.0f mW = %.0f %% of its 85 C rating (continuous, not just the'
         ' 0.75 ms pulse)' % (dp, worst_rev, 100 * worst_rev / vr_max, vr_max, worst_term ** 2 / 99.8 * 1e3, 100 * prt))
    # SPICE check
    out()
    out('  ngspice cross-check of the reflected detector (model B, 915 MHz, typical diode as a SPICE model with RS, CJ;')
    out('  Thevenin source at the anode from the board model; 25 us transient from the averaged value):')
    sp = spice_check(b, [(30.0, 1.0 / 3.0, 'max', 85, 'VSWR 2 (worst phase)'), (30.0, 1.0, 'min', -40, 'missing (worst phase)'),
                         (35.0, 1.0 / 3.0, 'max', 85, 'VSWR 2 (worst phase)'), (35.0, 1.0, 'min', -40, 'missing (worst phase)'),
                         (35.0, 1.0, 'max', 25, 'missing (best phase)')])
    plot_detector(rd, th)
    return dict(tab=tab, rd=rd, fit=fsel, p_lo=p_lo, rows=rows, sens=sens, spice=sp, fits=fits,
                fixed=(hi_t, lo_t, hi_a, lo_a), rev=worst_rev, term=worst_term, two=best2)


def plot_detector(rd, th):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    cols = {'matched': C3, 'VSWR 2': C1, 'missing': C2}
    for a, t in zip(ax, (-40, 25, 85)):
        for name, gm in ANTS:
            lo = [min(float(rd[(p, name, t, pr)][2].min()) for pr in PAIRS) for p in DET_POWERS]
            hi = [max(float(rd[(p, name, t, pr)][2].max()) for pr in PAIRS) for p in DET_POWERS]
            a.fill_between(DET_POWERS, np.maximum(lo, 1e-4), np.maximum(hi, 1e-4), color=cols[name], alpha=0.35, lw=0,
                           label=name)
        a.plot(DET_POWERS, [th(p, t) for p in DET_POWERS], color='k', lw=1.8, label='ratio threshold')
        a.set_yscale('log')
        a.set_ylim(1e-3, 3)
        a.set_xlabel('power at the U.FL into a matched antenna, dBm')
        a.set_ylabel('REFL_DET / FWD_DET')
        a.set_title('%d C: every phase, band, both PA models, every diode pairing' % t, fontsize=9)
        a.grid(alpha=0.25)
        a.legend(fontsize=7, loc='lower right')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'detector%s.png' % ('_' + B.DIODE_PART if os.environ.get('RF_DIODE') else '')), dpi=110)
    plt.close(fig)


def flt_fit_report():
    out('%s model vs Mini-Circuits typical table:' % FLT)
    if IS_LFCG:
        ft, it = lfcn.G_F_TAB, lfcn.G_IL_TAB
        g = 10 ** (-lfcn.G_RL_TAB / 20)
        vt = (1 + g) / (1 - g)
    else:
        ft, it, vt = lfcn.F_TAB, lfcn.IL_TAB, lfcn.VSWR_TAB
    S = flt_response(ft)
    out('   MHz    ' + ''.join('%7.0f' % (f / 1e6) for f in ft))
    out('   IL ds  ' + ''.join('%7.2f' % x for x in it))
    out('   IL fit ' + ''.join('%7.2f' % x for x in -R.db20(S[:, 1, 0])))
    gg = np.abs(S[:, 0, 0])
    out('   VSWR ds' + ''.join('%7.1f' % min(x, 999) for x in vt))
    out('   VSWRfit' + ''.join('%7.1f' % min(x, 999) for x in (1 + gg) / (1 - gg)))
    out('   (the harmonic studies use the table\'s magnitude and the model\'s phase)')
    out()


def main():
    out('Mesh Radio v1 - RF simulation results (sim/rf/run.py%s)' % (' --quick' if QUICK else ''))
    out('Board values from src/circuit.py; part models and sources in sim/rf/README.md and rflib.py.')
    out('Antenna filter FL1 = %s; missing-antenna detector coupler %.1f mm x %.2f mm gap (src/layout.py).'
        % (FLT, B.GEOM['cpl_len'], B.GEOM['gap']))
    out()
    if os.environ.get('RF_DIODE'):
        # comparison run: the detector study only, with another diode in the same places (results_<diode>.txt)
        b = B.Board()
        ckt = b.tx_out(with_pa=True)
        resA = {}
        for vpa in (2.7, 3.6, 4.0):
            pa = PA(vpa)
            v0, _ = pa.solve(ckt, FB, 0.0)
            resA[vpa] = (R.w_to_dbm(np.abs(v0['ANT'][0]) ** 2 / (2 * R.Z0)), None, None, pa)
        study8(dict(resA=resA))
        with open(os.path.join(HERE, 'results_%s.txt' % B.DIODE_PART), 'w') as fh:
            fh.write('\n'.join(LINES) + '\n')
        return
    flt_fit_report()
    s1 = study1()
    study1f()
    study2(s1)
    study3()
    study4()
    study5()
    study6()
    s7 = study7(s1)
    study8(s7)
    out()
    out('=' * 100)
    out('SUMMARY')
    out('=' * 100)
    for st, item, v, nums in SUMMARY:
        out('  %-2s  %-62s %-9s %s' % (st, item, v, nums))
    with open(os.path.join(HERE, 'results.txt'), 'w') as fh:
        fh.write('\n'.join(LINES) + '\n')


if __name__ == '__main__':
    main()
