# -*- coding: utf-8 -*-
"""Study 4: transmit bursts from a worn cell (P2, X4).

The QPA9510 draws its burst current from VPA (TPS63810, fed through the
TPS2121 from BAT_P, or from VSYS when the mux falls back).  A burst is:
PA_PWR_EN at 1 ms (mux on, buck-boost soft-starts), PA_EN (APC) at 4 ms
(208 mA quiescent, the 3V3 load steps 13 -> 130 mA for the SX1262 at its
+20 dBm cap, the APC LDO and the nRF52840), RF ramps up in 40 us at 4.2 ms
and lasts 0.3 s in the grid (the cell model is purely resistive, so the
droop is steady after ~5 ms; 0.3 s covers every protector timer: OCD 20 ms
+20 %, UVP 144 ms +20 %).  The showcase runs use a 1.0 s burst (a
LongFast message).

Pass criteria, fixed before running (README):
  P2-a  no reset: 3V3 >= 1.9 V (nRF52840 POF / SX1262 brown-out 1.7-1.8 V
        plus 0.1 V)
  P2-b  no BQ29700 trip (OCD, SCD or UVP) - a trip cuts the cell and the
        board goes dark
  P2-c  PA supply holds: TPS63810 never reaches UVLO (its registers would
        reset to 3.3 V) and VPA >= 95 % of its setting
  info  BQ25185 BUVLO (battery FET off) is reported, not failed: X4 relies
        on the LM66100 to hold VSYS through it
The highest PA level that passes every criterion is the supported transmit
power for that cell.

Outputs: results.txt, stress.json, burst.png, maxpower.png.
Run: python3 run.py   (from mesh-radio/v1: tools/kd python3 sim/burst/run.py)
"""
import copy
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import board as B
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('burst')

OCVS = [4.2, 3.7, 3.3, 3.1]
RINTS = [0.05, 0.15, 0.30]


def run_case(args):
    name, cfg = args
    raw = name + '.raw'
    stopped = None
    for opt in OPTS:
        cfg['opt'] = opt
        try:
            S.ngspice(B.build(cfg, raw), OUT, name)
            stopped = None
            break
        except S.TimestepError as e:
            stopped = e.t
    r = S.rawread(os.path.join(OUT, raw))
    os.remove(os.path.join(OUT, raw))
    pa = cfg['pa']
    t = r['time']
    t_off = pa['t_rf'] + pa['burst']
    w = (t > pa['t_apc']) & (t < t_off)
    ws = (t > pa['t_rf'] + 0.5e-3) & (t < t_off)
    g = lambda k, m=w: r[k][m]
    res = dict(
        name=name,
        bat_min=g('v(bat_p)').min(), vsys_min=g('v(vsys)').min(), v3_min=g('v(3v3)').min(),
        pain_min=g('v(pa_in)').min(), vpa_min=g('v(vpa)', ws).min() if ws.any() else 0.0,
        vpa_max=r['v(vpa)'].max(),
        icell_max=g('i(vbt_am)').max() if cfg['cell']['present'] else 0.0,
        ilm_max=np.abs(g('v(pblm_i)')).max(), ilm_rev=-g('v(pblm_i)').min(), ilm_fwd=g('v(pblm_i)').max(),
        isup_max=g('v(ch_isup)').max(), iin_chg_max=g('v(ch_iin)').max(),
        imux1_max=g('v(mx_i1)').max(), imux2_max=g('v(mx_i2)').max(), ibb_max=g('v(bb_iin)').max(),
        ipa_max=g('v(pa_i)').max(),
        mux_left_in1=bool(((g('v(mx_sel)', ws) < 0.5) | (g('v(mx_sel)', ws) > 1.5)).any()) if ws.any() else False,
        mux_on_in2=bool((g('v(mx_i2)') > 0.05).any()),
        ocd=bool(r['v(pbocd)'].max() > 0.5), uvp=bool(r['v(pbuvp)'].max() > 0.5),
        buvlo=bool(r['v(chbuvf)'].max() > 0.5), bbrst=bool(r['v(bbrst)'].max() > 0.5),
        vm_max=g('v(prot_vm,cell_minus)').max(),
        vset=pa['vset'], stopped=stopped,
    )
    # 1-second-burst average of the cell current (for ratings), from the steady part
    res['icell_avg'] = float(np.mean(r['i(vbt_am)'][ws])) if (cfg['cell']['present'] and ws.any()) else 0.0
    res['ok_a'] = res['v3_min'] >= 1.9
    res['ok_b'] = not (res['ocd'] or res['uvp'])
    res['ok_c'] = (not res['bbrst']) and res['vpa_min'] >= 0.95 * pa['vset']
    res['pass'] = res['ok_a'] and res['ok_b'] and res['ok_c'] and stopped is None
    # decimated waveform for plots
    keep = np.unique(np.searchsorted(t, np.linspace(0, t[-1], 4000)).clip(0, len(t) - 1))
    np.savez(os.path.join(OUT, name + '.npz'), **{k.replace('(', '_').replace(')', '').replace(',', '_'): v[keep]
                                                  for k, v in r.items()})
    return res


OPTS = ['.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200',
        '.option method=trap reltol=3e-3 abstol=1e-8 vntol=1e-5 itl4=300',
        '.option method=gear reltol=5e-3 abstol=1e-7 vntol=1e-4 itl4=500 gmin=1e-10']
PR_FIX = 374.0 / (562 + 374)    # proposed: PR1 bottom 301 k -> 374 k: IN1 priority down to 2.60 V (2.65 V rising)
VARIANTS = {'drawn': dict(lm='gnd', pr=None), 'fixed': dict(lm='diode', pr=PR_FIX)}


def cfg_for(ocv, rint, lvl, burst=0.2, usb=None, lm='gnd', present=True, pr_low=False, pr=None):
    c = B.default_cfg()
    if pr:
        c['mux']['pr_ratio'] = pr
    c['cell'].update(ocv=ocv, rint=rint, present=present)
    _, vset, inom = lvl
    c['pa'].update(vset=vset, inom=inom, burst=burst)
    c['usb'] = usb
    c['lm'] = lm
    c['pr_force_low'] = pr_low
    return c


def why(r):
    w = []
    if r['stopped'] is not None:
        w.append('supply collapse (solver stopped at %.2f ms)' % (r['stopped'] * 1e3))
    if r['ocd']:
        w.append('OCD/SCD trip')
    if r['uvp']:
        w.append('UVP trip')
    if r['bbrst']:
        w.append('TPS63810 UVLO (reset)')
    elif r['vpa_min'] < 0.95 * r['vset']:
        w.append('VPA %.2f V < 95 %%' % r['vpa_min'])
    if r['v3_min'] < 1.9:
        w.append('3V3 %.2f V' % r['v3_min'])
    if r['mux_left_in1']:
        w.append('mux left IN1')
    if r['buvlo']:
        w.append('BUVLO')
    return ', '.join(w) if w else '-'


def main():
    jobs = []
    for vn, v in VARIANTS.items():
        for ocv in OCVS:
            for rint in RINTS:
                for li, lvl in enumerate(B.PA_LEVELS):
                    jobs.append(('g%s_%g_%g_%d' % (vn[0], ocv, rint * 1e3, li), cfg_for(ocv, rint, lvl, **v)))
    P30, P34, P35 = B.PA_LEVELS[0], B.PA_LEVELS[3], B.PA_LEVELS[4]
    special = [
        ('s_fresh_3W_1s', cfg_for(4.2, 0.05, P35, burst=1.0)),
        ('s_fresh_1W_1s', cfg_for(4.2, 0.05, P30, burst=1.0)),
        ('s_mid_3W_1s', cfg_for(3.7, 0.15, P35, burst=1.0)),
        ('s_worn_1W_1s', cfg_for(3.1, 0.30, P30, burst=1.0)),
        ('u_37_150_3W_drawn', cfg_for(3.7, 0.15, P35, usb=5.0, lm='gnd')),
        ('u_37_150_3W_fix', cfg_for(3.7, 0.15, P35, usb=5.0, lm='diode', pr=PR_FIX)),
        ('u_31_300_1W_drawn', cfg_for(3.1, 0.30, P30, usb=5.0, lm='gnd')),
        ('u_31_300_1W_fix', cfg_for(3.1, 0.30, P30, usb=5.0, lm='diode', pr=PR_FIX)),
        ('u_31_300_3W_drawn', cfg_for(3.1, 0.30, P35, usb=5.0, lm='gnd')),
        ('u_31_300_3W_fix', cfg_for(3.1, 0.30, P35, usb=5.0, lm='diode', pr=PR_FIX)),
        ('n_1W_drawn', cfg_for(3.7, 0.15, P30, usb=5.0, lm='gnd', present=False)),
        ('n_1W_fix', cfg_for(3.7, 0.15, P30, usb=5.0, lm='diode', present=False, pr=PR_FIX)),
        ('n_1W_fix_pr', cfg_for(3.7, 0.15, P30, usb=5.0, lm='diode', present=False, pr_low=True)),
        ('n_2W5_fix_pr', cfg_for(3.7, 0.15, P34, usb=5.0, lm='diode', present=False, pr_low=True)),
        ('s_fixed_mid_3W_1s', cfg_for(3.7, 0.15, P35, burst=1.0, lm='diode', pr=PR_FIX)),
        ('s_fixed_worn_1W_1s', cfg_for(3.1, 0.30, P30, burst=1.0, lm='diode', pr=PR_FIX)),
        ('n_2W5_drawn', cfg_for(3.7, 0.15, P34, usb=5.0, lm='gnd', present=False)),
    ]
    jobs += special
    with ProcessPoolExecutor(4) as ex:
        res = dict((r['name'], r) for r in ex.map(run_case, jobs))

    L = ['Study 4: transmit bursts from a worn cell (P2, X4).  Criteria: P2-a 3V3 >= 1.9 V; P2-b no BQ29700 trip;',
         'P2-c TPS63810 never in UVLO and VPA >= 95 % of setting.  BUVLO reported, not failed.',
         'Cell = OCV behind R_int (pure resistance, conservative), + 2 x 20 mOhm leads/JST, + board path.', '']
    maxp = {}
    for vn in VARIANTS:
        rows = []
        for ocv in OCVS:
            for rint in RINTS:
                best = None
                for li, lvl in enumerate(B.PA_LEVELS):
                    r = res['g%s_%g_%g_%d' % (vn[0], ocv, rint * 1e3, li)]
                    rows.append(['%.1f V / %d mOhm' % (ocv, rint * 1e3), lvl[0], r['icell_max'], r['bat_min'],
                                 r['vsys_min'], r['v3_min'], r['pain_min'], r['vpa_min'], 'yes' if r['buvlo'] else 'no',
                                 S.verdict(r['pass']), why(r)])
                    if r['pass']:
                        best = li
                maxp[(vn, ocv, rint)] = best
        L.append('Grid, %s (%s), 0.2 s bursts, battery only:' % (
            vn, 'LM66100 CE = GND, PR1 562 k / 301 k' if vn == 'drawn' else 'Schottky for the LM66100, PR1 562 k / 374 k'))
        L.append(S.table(rows, ['cell', 'PA level', 'Icell max A', 'BAT_P min', 'VSYS min', '3V3 min', 'PA_IN min',
                                'VPA min', 'BUVLO', 'verdict', 'why']))
        L.append('')
    for vn in VARIANTS:
        L.append('Highest PA level that passes, per cell (battery only, %s):' % vn)
        mrows = []
        for ocv in OCVS:
            mrows.append(['%.1f V' % ocv] + [B.PA_LEVELS[maxp[(vn, ocv, r)]][0] if maxp[(vn, ocv, r)] is not None
                                              else 'none' for r in RINTS])
        L.append(S.table(mrows, ['OCV \\ R_int'] + ['%d mOhm' % (r * 1e3) for r in RINTS]))
        L.append('')
    L.append('Showcase 1 s bursts and USB cases:')
    srows = []
    for name, _ in special:
        r = res[name]
        srows.append([name, r['icell_max'], r['bat_min'], r['vsys_min'], r['v3_min'], r['pain_min'], r['vpa_min'],
                      r['ilm_fwd'], r['ilm_rev'], r['isup_max'], r['iin_chg_max'], r['imux2_max'],
                      S.verdict(r['pass']), why(r)])
    L.append(S.table(srows, ['case', 'Icell max', 'BAT_P min', 'VSYS min', '3V3 min', 'PA_IN min', 'VPA min',
                             'LM66100 fwd A', 'LM66100 rev A', 'BATFET A', 'IN A', 'mux IN2 A', 'verdict', 'why']))
    L.append('  u_ = USB present (5 V, 1 m cable) + cell; n_ = no cell, USB only; _drawn = LM66100 CE to GND (as drawn),')
    L.append('  _fix = Schottky (RB060MM) in place of the LM66100 (and, for s_fixed_, PR1 562 k / 374 k); _pr = also PR1')
    L.append('  pulled low by a GPIO FET (mux forced to IN2) when no cell is fitted.')
    S.write_results(HERE, L)

    # ---------------------------------------------------------------- stress for the derating table
    allr = [r for r in res.values()]
    passing = [r for r in allr if r['pass']]
    worst = lambda k, rs: max(rs, key=lambda x: x[k])
    st = []
    rp = worst('icell_max', passing)
    st.append(S.stress('JST-PH 2-pin (battery)', 'J (battery)', 'current, passing burst', rp['icell_avg'], 'A', 2.0,
                       'derate', rp['name']))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'drain current, passing burst', rp['icell_avg'], 'A', 3.2,
                       'derate', rp['name'] + ' (3.2 A min-Cu rating; 5.3 A max-Cu)'))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'power, passing burst', rp['icell_avg'] ** 2 * 0.042, 'W', 0.5,
                       'derate', rp['name'] + ' (42 mOhm max at -4.5 V; 0.5 W min Cu)'))
    st.append(S.stress('SSM10N954L', 'Q (protector)', 'source current, passing burst', rp['icell_avg'], 'A', 13.5,
                       'derate', rp['name']))
    st.append(S.stress('R22m 1206 1 W', 'R (sense)', 'power, passing burst', rp['icell_avg'] ** 2 * 0.022, 'W', 1.0,
                       'derate', rp['name']))
    rm = worst('imux1_max', passing)
    st.append(S.stress('TPS2121', 'U (mux)', 'IN1 current, passing burst', rm['imux1_max'], 'A', 4.5, 'derate', rm['name']))
    rb = worst('ibb_max', passing)
    st.append(S.stress('TPS63810', 'U (buck-boost)', 'input current, passing burst', rb['ibb_max'], 'A', 4.7, 'derate',
                       rb['name'] + ' (vs 5.2 A min switch limit less ripple)'))
    rpa = worst('ipa_max', passing)
    st.append(S.stress('TPS63810', 'U (buck-boost)', 'output current, passing burst', rpa['ipa_max'], 'A', 2.5, 'derate',
                       rpa['name'] + ' (recommended 2.5 A at VO 3.5 V)'))
    st.append(S.stress('QPA9510', 'U (PA)', 'device current, 35 dBm', 2.3, 'A', 2.4, 'absmax',
                       'datasheet 2400 mA abs max; 2.3 A at 4.0 V'))
    st.append(S.stress('QPA9510', 'U (PA)', 'device current, 34 dBm (firmware ceiling)', 2.0, 'A', 2.4, 'derate',
                       '1.7-2.0 A at 3.6 V vs 2400 mA abs max'))
    st.append(S.stress('QPA9510', 'U (PA)', 'device current, 30 dBm (US mode)', 1.0, 'A', 2.4, 'derate', '1.0 A at 2.7 V'))
    # inductor peak at the worst passing point: IL_avg = Iin (boost), ripple D*Vin/(f L), f 2 MHz, L 0.47 uH -20 %
    vin = rb['pain_min']
    vo = rb['vset']
    d = max(0.0, 1 - vin / vo)
    ilpk = rb['ibb_max'] + d * vin / (2e6 * 0.376e-6) / 2
    st.append(S.stress('DFE252012F-R47M', 'L (buck-boost)', 'peak current, passing burst', ilpk, 'A', 6.7, 'derate',
                       rb['name'] + ' (Isat 6.7 A; rated 4.9 A)'))
    st.append(S.stress('C47u 0805 6.3 V', 'C (VPA)', 'voltage', max(r['vpa_max'] for r in allr), 'V', 6.3, 'derate',
                       '35 dBm setting'))
    lmr = max(allr, key=lambda x: x['ilm_max'])
    st.append(S.stress('LM66100', 'U (cell-to-SYS)', 'switch current (any case)', lmr['ilm_max'], 'A', 1.5, 'derate',
                       lmr['name'] + ' (1.5 A continuous, 2.5 A <= 120 ms pulsed)'))
    lmp = max(passing, key=lambda x: x['ilm_max'])
    st.append(S.stress('LM66100', 'U (cell-to-SYS)', 'switch current, passing bursts', lmp['ilm_max'], 'A', 1.5, 'derate',
                       lmp['name']))
    S.write_stress(HERE, st)

    # ---------------------------------------------------------------- plots
    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(16, 8))
    show = [('s_fresh_3W_1s', 'fresh 4.2 V / 50 mOhm, 3 W'), ('s_mid_3W_1s', '3.7 V / 150 mOhm, 3 W, as drawn'),
            ('s_fixed_worn_1W_1s', '3.1 V / 300 mOhm, 1 W, fixed')]
    for j, (n, title) in enumerate(show):
        d = np.load(os.path.join(OUT, n + '.npz'))
        tm = d['time'] * 1e3
        a = ax[0, j]
        for k, lab in (('v_bat_p', 'BAT_P'), ('v_vsys', 'VSYS'), ('v_3v3', '3V3'), ('v_pa_in', 'PA_IN'), ('v_vpa', 'VPA')):
            a.plot(tm, d[k], label=lab, lw=1)
        a.axhline(1.9, color='C3', lw=0.6, ls=':')
        a.set_title(title + ' (%s)' % S.verdict(res[n]['pass']))
        a.set_xlabel('ms')
        a.set_ylabel('V')
        a.set_ylim(0, 4.5)
        a.legend(fontsize=7, loc='lower right')
        a = ax[1, j]
        a.plot(tm, d['i_vbt_am'], label='cell')
        a.plot(tm, d['v_mx_i1'], label='mux IN1')
        a.plot(tm, d['v_mx_i2'], label='mux IN2')
        a.plot(tm, d['v_pblm_i'], label='LM66100')
        a.plot(tm, d['v_pa_i'], label='PA (VPA)')
        a.axhline(4.04, color='C3', lw=0.6, ls=':')
        a.text(tm[-1] * 0.6, 4.1, 'OCD 100 mV / 24.75 mOhm', color='C3', fontsize=7)
        a.set_xlabel('ms')
        a.set_ylabel('A')
        a.legend(fontsize=7, loc='upper right')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'burst.png'))

    fig, ax = plt.subplots(1, 3, figsize=(17, 4.5))
    for q, vn in enumerate(VARIANTS):
        a = ax[q]
        grid = np.full((len(OCVS), len(RINTS)), -1.0)
        for i, ocv in enumerate(OCVS):
            for j, rint in enumerate(RINTS):
                if maxp[(vn, ocv, rint)] is not None:
                    grid[i, j] = maxp[(vn, ocv, rint)]
        a.imshow(grid, cmap='viridis', vmin=-1, vmax=len(B.PA_LEVELS) - 1, aspect='auto')
        for i in range(len(OCVS)):
            for j in range(len(RINTS)):
                k = int(grid[i, j])
                a.text(j, i, B.PA_LEVELS[k][0] if k >= 0 else 'none', ha='center', va='center',
                       color='w' if k < 2 else 'k', fontsize=8)
        a.set_xticks(range(len(RINTS)))
        a.set_xticklabels(['%d mOhm' % (r * 1e3) for r in RINTS])
        a.set_yticks(range(len(OCVS)))
        a.set_yticklabels(['%.1f V' % o for o in OCVS])
        a.grid(False)
        a.set_title('highest passing PA level, battery only, %s' % vn)
    a = ax[2]
    for n, lab in (('n_1W_drawn', 'no cell, 1 W, as drawn'), ('n_1W_fix', 'no cell, 1 W, Schottky'),
                   ('n_1W_fix_pr', 'no cell, 1 W, Schottky + PR1 low')):
        d = np.load(os.path.join(OUT, n + '.npz'))
        a.plot(d['time'] * 1e3, d['v_vpa'], label=lab + ' VPA', lw=1)
    a.set_xlim(0, 30)
    a.set_xlabel('ms')
    a.set_ylabel('V')
    a.set_title('USB only, no cell: VPA through the burst start')
    a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'maxpower.png'))


if __name__ == '__main__':
    main()
