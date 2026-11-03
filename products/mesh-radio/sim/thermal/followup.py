# -*- coding: utf-8 -*-
"""Mesh Radio v1 thermal follow-up (uses the model in run.py).

  A. Amplifier heat from the QPA9510 data sheet's efficiency (nominal) and
     from the plan's supply currents (pessimistic bound), for 30 / 31.5 /
     33 / 34 / 35 dBm at the U.FL (the PA delivers 1.13 dB more: sim/rf).
  B. The routed 6-layer board (run.py reads its copper) and the fixes still
     open on it; which helps most; the uniform estimate of 19 Oct beside it.
  C. The highest power at the antenna that passes every criterion of run.py
     for one 1 s packet a minute, one 2 s packet a minute and a 25 % storm
     (1 s on, 3 s off), at 25, 45 and 60 C, for seven board options (with
     and without the gap pad at layout.GAP_PAD, and at its old spot).
  D. The charger as built (ISET from circuit.py, NTC TH1 beside the battery
     plug J3) and at higher currents, at 25 and 45 C.

    tools/kd python3 sim/thermal/followup.py      (from products/mesh-radio; NPROC workers)

Writes results_followup.txt and power_table.png next to this file.
"""
import math
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as R          # noqa: E402
import numpy as np       # noqa: E402
import matplotlib        # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

OUT = []


def out(s=''):
    OUT.append(s)
    print(s)


# ---------------------------------------------------------------------------
# A. Amplifier operating points
LOSS_DB = 1.13                      # PA output -> U.FL (sim/rf/results.txt 1d)
# blocks of that loss, in sim/rf's proportions (LPF 0.21, switch 0.30, LFCG-1000+ 0.67, coupler section 0.08)
LOSS_SPLIT = dict(match=0.08, lpf=0.21, switch=0.30, filter=0.67)
ANT_DBM = [30.0, 31.5, 33.0, 34.0, 35.0]
# QPA9510 data sheet 23 Jun 2025, p.4 "PAE vs. Average Output Power", 915 MHz curve,
# VCC = VCC1 = VCC2 = 3.6 V, VAPC1 = VAPC2 = 2.8 V, ICQ 215 mA, 25 C, 50 ohm, GSM bursts
# (p.3 note: Pin +4.5 dBm, duty 37.5 %).  Read off the curve:
PAE_CURVE = [(28.0, 24.5), (29.0, 27.5), (30.0, 31.5), (31.0, 35.5), (32.0, 40.0), (33.0, 45.0), (34.0, 51.0),
             (35.0, 56.0), (35.5, 57.5), (35.7, 57.0)]
VCC_MIN, VCC_MAX = 2.7, 4.0         # data sheet p.2 recommended 2.7 V min; firmware 4.0 V opt-in ceiling
P_EQ_TARGET = 35.0                  # firmware sets VPA so the PA works 35 dBm-equivalent (PAE 56 %)
# pessimistic: the plan's DC power for each antenna level (docs/plan.md; sim/README 32/33 dBm points)
PLAN_DC = [(30.0, 2.7 * 1.0), (32.0, 3.1 * 1.3), (33.0, 3.35 * 1.55), (34.0, 3.6 * 2.0), (35.0, 4.0 * 2.3)]
PLAN_VCC = [(30.0, 2.7), (32.0, 3.1), (33.0, 3.35), (34.0, 3.6), (35.0, 4.0)]


def interp(tab, x):
    xs, ys = zip(*tab)
    return float(np.interp(x, xs, ys))


def pa_point(ant_dbm, mode):
    """(VCC, ICC, P_RF at the PA in W, note)"""
    p_pa_dbm = ant_dbm + LOSS_DB
    p_rf = 10 ** (p_pa_dbm / 10) / 1e3
    if mode == 'nominal':
        # saturated-PA scaling: lowering VCC moves the PAE curve down by 20 log(VCC/3.6) dB
        vcc = 3.6 * 10 ** ((p_pa_dbm - P_EQ_TARGET) / 20)
        vcc = min(max(vcc, VCC_MIN), VCC_MAX)
        p_eq = p_pa_dbm - 20 * math.log10(vcc / 3.6)
        pae = interp(PAE_CURVE, min(p_eq, 35.5)) / 100
        pdc = p_rf / pae
        return vcc, pdc / vcc, p_rf, 'PAE %.0f %% at %.1f dBm-equivalent' % (100 * pae, p_eq)
    pdc = interp(PLAN_DC, ant_dbm)
    vcc = interp(PLAN_VCC, ant_dbm)
    return vcc, pdc / vcc, p_rf, 'plan DC power %.2f W' % pdc


def tx_sources_level(ant_dbm, mode):
    vcc, icc, p_rf, note = pa_point(ant_dbm, mode)
    pdc = vcc * icc
    eta = interp([(2.7, 0.92), (7.2, 0.89), (9.2, 0.87)], pdc)     # TPS63810, as in run.py
    i_in = pdc / eta / R.VBAT_TX
    i_cell = i_in + 0.15
    s = {'U_PA': pdc - p_rf, 'U_BB': pdc * (1 / eta - 1), 'U_MUX': i_in ** 2 * R.R_MUX,
         'Q_REV': i_cell ** 2 * R.R_REVFET, 'Q_PROT': i_cell ** 2 * R.R_PROT, 'R_SENSE': i_cell ** 2 * R.R_SENSE,
         'J_BAT': i_cell ** 2 * R.R_JST, 'L_CHOKE': icc ** 2 * R.R_CHOKE}
    tot = sum(LOSS_SPLIT.values())
    p = p_rf
    for k in ('match', 'lpf', 'switch', 'filter'):
        loss = p * (1 - 10 ** (-LOSS_DB * LOSS_SPLIT[k] / tot / 10))
        s['RF_' + k] = loss
        p -= loss
    s['U_SX'] = 3.3 * 0.102 - 0.100
    s['R_PAD1'], s['R_PAD2'], s['R_PAD3'] = 0.073, 0.021, 0.004
    s['U_BUCK'] = 0.45 * (1 / 0.90 - 1)
    s['U_NRF'] = 0.016
    s['U_APC'] = 0.005
    s['_meta'] = (vcc, icc, p_rf, eta, i_in, note, p)
    return s


# ---------------------------------------------------------------------------
# B. Board options: the routed board (R.PARAMS after R.setup()) and the fixes
# still open on it.  Filled by options() once the board is read.
FIX = {'pa_island': False, 'k_via_fill': 385.0}       # paddle joined to the top pour, copper-filled paddle vias
OPTIONS = []
PAD, OLD_PAD = R.PAD_SINK, R.OLD_PAD_SINK


def options():
    boards = [('6L as built', {}), ('6L + paddle fixes', dict(FIX)), ('6L + paddle fixes + 2 oz outer', dict(R.ALL_FIXES))]
    o = []
    for lab, ch in boards:
        o.append((lab, dict(ch)))
        o.append((lab + ' + pad', dict(ch, sinks=PAD)))
    o.insert(2, ('6L as built + pad at old spot', dict(sinks=OLD_PAD)))
    OPTIONS[:] = o


PATTERNS = [('1 s / min', 1, 59), ('2 s / min', 2, 58), ('25 % storm', 1, 3)]
TAMBS = [25, 45, 60]
MODES = ['nominal', 'pessimistic']


def params(ch):
    p = dict(R.PARAMS)
    p.update(ch)
    return p


def _job(lab, ch, ta):
    cs = R.Case(params(ch), 10.0, ta)
    lm, _ = cs.steady_metrics(R.LISTEN)
    inh = R.inherent_fails(cs, lm)
    cols = [(m, d) for m in MODES for d in ANT_DBM]
    srcs = [tx_sources_level(d, m) for m, d in cols]
    resd = {}
    for pname, ton, toff in PATTERNS:
        rs = cs.periodic_multi([{k: v for k, v in s.items() if not k.startswith('_')} for s in srcs], toff, t_on=ton)
        for (m, d), r in zip(cols, rs):
            tot = ta + r['peak'] + lm
            rows, ov = R.verdict_rows(cs, tot, False, 0.0)
            v = dict(zip(cs.names, tot))
            bad = [x for x in rows if x[2] == 'FAIL' and x[0] not in inh]
            resd[(pname, m, d)] = (R.duty_ok(rows, inh), v['QPA9510 case'], v['QPA9510 Tj'], v['TPS63810 Tj'],
                                   bad[0][0].split(' <=')[0] if bad else '')
    return lab, ta, resd, sorted(inh)


def _probe(lab, ch, probes):
    outv = []
    for ta, pname, ton, toff, d in probes:
        cs = R.Case(params(ch), 10.0, ta)
        lm, _ = cs.steady_metrics(R.LISTEN)
        s = {k: v for k, v in tx_sources_level(d, 'nominal').items() if not k.startswith('_')}
        r = cs.periodic_multi([s], toff, t_on=ton)[0]
        v = dict(zip(cs.names, ta + r['peak'] + lm))
        outv.append((v['QPA9510 case'], v['QPA9510 Tj']))
    return lab, outv


# ---------------------------------------------------------------------------
# D. Charger (as built: the charger at the USB end, TH1 beside J3)
def _charger(ta, h=10.0):
    cs = R.Case(dict(R.PARAMS), h, ta)
    lm, _ = cs.steady_metrics(R.LISTEN)
    o = {}
    for vb in (3.0, 3.7):
        cm, th = cs.steady_metrics(R.chg_sources(vb))
        o[vb] = cm
    return ta, lm, o, cs.names


def ntc_window():
    t_hot = R.ntc_t(0.115 / 38e-6)
    t_hot_lo = R.ntc_t(0.125 / 36.5e-6)        # earliest hot stop over the tolerances (VHOT max, ITSMR min)
    return t_hot, t_hot_lo


# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    R.setup()
    options()
    nproc = R.NPROC
    out('Mesh Radio v1 - thermal follow-up (sim/thermal/followup.py), %s' % time.strftime('%Y-%m-%d'))
    out('Model, criteria and every other source: run.py / results.txt.  h = 10 W/m2K (still air in an enclosure).')
    out('Board: the routed %s (copper, vias and stackup read by run.py); pad = 10 x 10 mm gap pad at layout.GAP_PAD %s'
        % (os.path.relpath(R.BOARD_FILE, R.V1), str(R.GAP_PAD)))
    out()
    out('=' * 100)
    out('A. Amplifier operating points (PA output = antenna + %.1f dB, sim/rf)' % LOSS_DB)
    out('=' * 100)
    out('Nominal: QPA9510 data sheet (23 Jun 2025) p.4 "PAE vs. Average Output Power", 915 MHz, VCC 3.6 V, VAPC 2.8 V,')
    out('  ICQ 215 mA, 25 C, 50 ohm, GSM bursts (p.3: Pin +4.5 dBm, 37.5 % duty).  Read: PAE 31.5 % at 30 dBm, 45 % at')
    out('  33 dBm, 56 % at 35 dBm, peak 57.5 % at 35.5 dBm.  Check against p.3: 35.4 dBm at 1.7 A from 3.6 V = 56.7 %.')
    out('  Current at 3.6 V from the curve (ICC = Pout / (PAE x VCC)): 30 dBm %.2f A, 33 dBm %.2f A, 35 dBm %.2f A.'
        % (1.0 / (0.315 * 3.6), 2.0 / (0.45 * 3.6), 3.162 / (0.56 * 3.6)))
    out('  Firmware lowers VPA at low power (plan: 2.7 V for 1 W).  ASSUMED: a saturated PA keeps its PAE when VCC and')
    out('  the output move together (output ~ VCC^2), so the curve is read at Pout - 20 log(VCC / 3.6 V), with VPA')
    out('  chosen for 35 dBm-equivalent (PAE 56 %%), clamped to %.1f-%.1f V.  PAE at the case temperature (hot) is lower' % (VCC_MIN, VCC_MAX))
    out('  than this 25 C curve; not modelled.')
    out('Pessimistic: the plan\'s supply power for each antenna level (run.py study 1; 32/33 dBm points from sim/README).')
    out()
    out('  %-7s %-8s %-11s | %-5s %-6s %-7s %-7s %-6s %-7s | %s' % ('antenna', 'PA out', 'mode', 'VCC', 'ICC A', 'DC W', 'PA heat',
                                                                  'eta BB', 'all W', 'note'))
    for d in ANT_DBM:
        for m in MODES:
            s = tx_sources_level(d, m)
            vcc, icc, p_rf, eta, i_in, note, p_ant = s['_meta']
            tot = sum(v for k, v in s.items() if not k.startswith('_'))
            out('  %-7.1f %-8.1f %-11s | %-5.2f %-6.2f %-7.2f %-7.2f %-6.2f %-7.2f | %s'
                % (d, d + LOSS_DB, m, vcc, icc, vcc * icc, s['U_PA'], eta, tot, note))
    out('  (ICC stays below the 2400 mA absolute maximum in every row.)')

    # ---- C: the grid
    jobs = [(lab, ch, ta) for lab, ch in OPTIONS for ta in TAMBS]
    with mp.Pool(nproc) as pool:
        got = pool.starmap(_job, jobs)
    print('grid done %.0f s' % (time.time() - t0), file=sys.stderr)
    G = {}
    inh_all = {}
    for lab, ta, resd, inh in got:
        G[(lab, ta)] = resd
        if inh:
            inh_all[ta] = inh

    def best(lab, ta, pname, m):
        ok = [d for d in ANT_DBM if G[(lab, ta)][(pname, m, d)][0]]
        # highest level such that it and every level below it pass
        b = None
        for d in ANT_DBM:
            if G[(lab, ta)][(pname, m, d)][0]:
                b = d
            else:
                break
        return b

    out()
    out('=' * 100)
    out('C. Highest power AT THE ANTENNA (dBm) that passes every criterion: nominal (data-sheet PAE) / pessimistic (plan)')
    out('=' * 100)
    out('   "-" = not even 30 dBm.  Criteria as run.py: QPA9510 case <= 85 C and junction <= 160 C (175 - 15), other')
    out('   junctions <= Tjmax - 15 C, rated parts under their rating, cell area <= 60 C (left out at 60 C ambient, where')
    out('   the box sets it).  No charging.  h = 10 W/m2K.')
    hdr = '  %-34s' % 'board option' + ''.join(' | %-24s' % ('%d C' % ta) for ta in TAMBS)
    out(hdr)
    out('  %-34s' % '' + ''.join(' | %-24s' % '1s/min  2s/min  storm25' for ta in TAMBS))
    table = {}
    for lab, ch in OPTIONS:
        cells = []
        for ta in TAMBS:
            trip = []
            for pname, ton, toff in PATTERNS:
                bn = best(lab, ta, pname, 'nominal')
                bp = best(lab, ta, pname, 'pessimistic')
                table[(lab, ta, pname)] = (bn, bp)
                f = lambda x: '-' if x is None else ('%g' % x)
                trip.append('%s/%s' % (f(bn), f(bp)))
            cells.append(' | %-7s %-7s %-8s' % tuple(trip))
        out('  %-34s' % lab + ''.join(cells))
    for ta, inh in sorted(inh_all.items()):
        out('   left out at %d C (fails while only listening): %s' % (ta, '; '.join(inh)))

    out()
    out('Detail: QPA9510 case / junction and TPS63810 junction peak (C), and the first failing criterion, nominal PAE')
    for lab, ch in OPTIONS:
        for ta in TAMBS:
            for pname, ton, toff in PATTERNS:
                line = []
                for d in ANT_DBM:
                    ok, tc, tj, tb, why = G[(lab, ta)][(pname, 'nominal', d)]
                    line.append('%g:%3.0f/%3.0f/%3.0f%s' % (d, tc, tj, tb, '' if ok else '!' + why.replace(' ', '')[:12]))
                out('  %-30s %2d C %-10s %s' % (lab, ta, pname, '  '.join(line)))
    out('  (pessimistic detail)')
    for lab, ch in OPTIONS:
        for ta in TAMBS:
            for pname, ton, toff in PATTERNS:
                line = []
                for d in ANT_DBM:
                    ok, tc, tj, tb, why = G[(lab, ta)][(pname, 'pessimistic', d)]
                    line.append('%g:%3.0f/%3.0f/%3.0f%s' % (d, tc, tj, tb, '' if ok else '!' + why.replace(' ', '')[:12]))
                out('  %-30s %2d C %-10s %s' % (lab, ta, pname, '  '.join(line)))

    # ---- B: which fix helps most (6 layers)
    out()
    out('=' * 100)
    out('B. Which fix helps most (nominal PAE): QPA9510 case / junction peak, C')
    out('=' * 100)
    probes = [(25, '1 s / min', 1, 59, 34.0), (45, '2 s / min', 2, 58, 33.0), (60, '25 % storm', 1, 3, 30.0)]
    variants = [
        ('6L as built', {}),
        ('uniform 6L estimate of 19 Oct (70/100/50/50/100/70 %, 8 vias/cm2)', dict(R.ESTIMATE)),
        ('as built + paddle joined to the top pour', {'pa_island': False}),
        ('as built + copper-filled paddle vias', {'k_via_fill': 385.0}),
        ('as built + 2 oz outer', {'t_cu': R.OUTER2}),
        ('as built + both paddle fixes (1 oz outer)', dict(FIX)),
        ('as built + both paddle fixes + 2 oz outer', dict(R.ALL_FIXES)),
        ('as built + gap pad (layout.GAP_PAD)', {'sinks': PAD}),
        ('as built + gap pad at its old spot under the PA', {'sinks': OLD_PAD}),
        ('both paddle fixes + 2 oz outer + gap pad', dict(R.ALL_FIXES, sinks=PAD)),
    ]
    with mp.Pool(nproc) as pool:
        pr = pool.starmap(_probe, [(lab, ch, probes) for lab, ch in variants])
    out('  %-58s ' % '' + ''.join('%-24s' % ('%d C %s %g dBm' % (ta, pn, d)) for ta, pn, a, b, d in probes))
    for lab, vals in pr:
        out('  %-58s ' % lab + ''.join('%-24s' % ('%3.0f / %3.0f' % v) for v in vals))
    print('probes done %.0f s' % (time.time() - t0), file=sys.stderr)

    # ---- D: charger
    out()
    out('=' * 100)
    i0 = R.I_CHG
    th1 = R.PLACEMENT[R.ref('NTC10K')]
    j3 = R.PLACEMENT[R.ref('JST_PH2')]
    u4 = R.PLACEMENT[R.ref('BQ25185')]
    out('D. Charger as built: ISET %.0f mA (circuit.py), charger %s at (%.1f, %.1f), NTC TH1 at (%.1f, %.1f) beside J3 (%.1f, %.1f)'
        % (i0 * 1e3, R.ref('BQ25185'), u4[0], u4[1], th1[0], th1[1], j3[0], j3[1]))
    out('=' * 100)
    t_hot, t_hot_lo = ntc_window()
    out('  TS hot stop: NTC at %.1f C typ (as low as %.1f C over the tolerances; verdict uses this); resumes ~5 C lower.  TREG 100 C.  Listening, h = 10,'
        ' the routed board, no transmit.' % (t_hot, t_hot_lo))
    out('  ISET = 300 A.ohm / ICHG (SLUSF65B): 1.00 k -> 300 mA (as built), 750 R -> 400 mA, 604 R -> 497 mA.'
        '  Loss scaled with current from the %.0f mA solution.' % (i0 * 1e3))
    with mp.Pool(min(nproc, 2)) as pool:
        ch_res = pool.map(_charger, [25, 45])
    out('  %-4s %-5s %-7s | %-10s %-8s %-8s %-8s | %s' % ('Ta', 'VBAT', 'ICHG', 'Tj unthr.', 'charge%', 'cell C', 'NTC C', 'verdict'))
    for ta, lm, o, names in ch_res:
        ib = names.index('BQ25185 Tj'); ij = names.index('battery plug J3'); it = names.index('NTC TH1')
        for vb in (3.0, 3.7):
            cm = o[vb]
            for ichg in (i0, 0.400, 0.497):
                k = ichg / R.I_CHG
                base = ta + lm
                tj0 = base[ib] + k * cm[ib]
                frac = 1.0 if tj0 <= 100 else max(0.0, (100 - base[ib]) / (k * cm[ib]))
                cell = base[ij] + frac * k * cm[ij]
                ntc = base[it] + frac * k * cm[it]
                v = []
                v.append('TREG ok' if frac >= 0.999 else 'throttled')
                v.append('NTC trips' if ntc >= t_hot_lo else 'NTC ok')
                v.append('cell > 45' if cell > 45.0 else 'cell ok')
                out('  %-4d %-5.1f %-7s | %-10.0f %-8.0f %-8.0f %-8.0f | %s'
                    % (ta, vb, '%d mA' % round(ichg * 1e3), tj0, 100 * frac, cell, ntc, ', '.join(v)))
    out('  (cell = the board under J3; TH1 reads the board %.1f mm from J3 (%s side), not the cell itself)'
        % (math.hypot(th1[0] - j3[0], th1[1] - j3[1]), 'top' if th1[3] == 'T' else 'bottom'))
    out()
    out('run time %.0f s' % (time.time() - t0))
    open(os.path.join(HERE, 'results_followup.txt'), 'w').write('\n'.join(OUT) + '\n')
    plot_table(table)


def plot_table(table):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axis('off')
    cols = ['%d C\n%s' % (ta, pn) for ta in TAMBS for pn, a, b in PATTERNS]
    rows = [lab for lab, ch in OPTIONS]
    f = lambda x: '-' if x is None else '%g' % x
    cell = [['%s / %s' % (f(table[(lab, ta, pn)][0]), f(table[(lab, ta, pn)][1])) for ta in TAMBS for pn, a, b in PATTERNS]
            for lab in rows]
    t = ax.table(cellText=cell, rowLabels=rows, colLabels=cols, loc='center', cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(7.5)
    t.scale(1, 1.6)
    for (r, c), cl in t.get_celld().items():
        cl.set_edgecolor('#e4e3df')
        if r == 0 or c == -1:
            cl.set_text_props(color='#52514e')
    ax.set_title('Highest dBm at the antenna that passes (data-sheet PAE / plan currents); "-" = not even 30 dBm',
                 fontsize=10, color='#0b0b0b', loc='left')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'power_table.png'), dpi=130)
    plt.close(fig)


if __name__ == '__main__':
    main()
