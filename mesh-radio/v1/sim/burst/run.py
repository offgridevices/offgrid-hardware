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

Each run stops at its first fatal event (TPS63810 reset, OCD/SCD or UVP
trip), so minima reported for a failing run are those up to that moment.

Outputs: results.txt, stress.json, burst.png, maxpower.png.
Run: python3 run.py   (from mesh-radio/v1: tools/kd python3 sim/burst/run.py)
"""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import board as B
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('burst')

OCVS = [4.2, 3.7, 3.3, 3.1]
NUMS = ['bat_min', 'vsys_min', 'v3_min', 'pain_min', 'vpa_min', 'vpa_max', 'icell_max', 'ilm_max', 'ilm_rev', 'ilm_fwd',
        'isup_max', 'iin_chg_max', 'imux1_max', 'imux2_max', 'ibb_max', 'ipa_max', 'vm_max', 'icell_avg', 't_end']
RINTS = [0.05, 0.15, 0.30]


STOP_ON = ['v(bbrst) > 0.5', 'v(pbocd) > 0.5', 'v(pbuvp) > 0.5']


def run_case(args):
    """One burst.  The run stops at the first fatal event (TPS63810 reset,
    BQ29700 OCD/SCD or UVP trip): the verdict is FAIL from there on and the
    chattering that follows a collapsed supply is slow to simulate.  Results
    are cached in sim/out/burst/<name>.json against a hash of the netlist."""
    name, cfg = args
    raw = name + '.raw'
    # with no cell fitted the BQ29700 has nothing to protect (its flags are meaningless): stop on resets only
    cfg['stop_on'] = STOP_ON if cfg['cell']['present'] else STOP_ON[:1]
    cfg['opt'] = OPTS[0]
    key = hashlib.sha1(B.build(cfg, raw).encode()).hexdigest()
    cache = os.path.join(OUT, name + '.json')
    if os.path.exists(cache) and os.path.exists(os.path.join(OUT, name + '.npz')):
        d = json.load(open(cache))
        if d.get('key') == key:
            return d['res']
    stopped = None
    timed_out = False
    for opt in OPTS:
        cfg['opt'] = opt
        try:
            S.ngspice(B.build(cfg, raw), OUT, name, timeout=900)
            stopped = None
            break
        except S.TimestepError as e:
            stopped = e.t
        except subprocess.TimeoutExpired:
            timed_out = True
            break
    if timed_out:
        res = dict(name=name, timed_out=True, stopped=None, pass_=False, vset=cfg['pa']['vset'])
        res.update(dict((k, float('nan')) for k in NUMS))
        res.update(ocd=False, uvp=False, buvlo=False, bbrst=False, mux_left_in1=False, mux_on_in2=False,
                   ok_a=False, ok_b=False, ok_c=False)
        res['pass'] = False
        json.dump(dict(key=key, res=res), open(cache, 'w'))
        return res
    r = S.rawread(os.path.join(OUT, raw))
    os.remove(os.path.join(OUT, raw))
    pa = cfg['pa']
    t = r['time']
    t_off = pa['t_rf'] + pa['burst']
    nb, per = pa.get('n', 1), pa.get('period', 1.0)
    w = np.zeros(len(t), bool)
    ws = np.zeros(len(t), bool)
    busy = np.zeros(len(t), bool)
    for k in range(nb):
        w |= (t > pa['t_apc'] + k * per) & (t < t_off + k * per)
        ws |= (t > pa['t_rf'] + 0.5e-3 + k * per) & (t < t_off + k * per)
        busy |= (t > pa['t_apc'] - 1e-3 + k * per) & (t < t_off + 20e-3 + k * per)
    idle = (t > 2e-3) & ~busy
    if not w.any():           # stopped before the APC came on (start-up collapse)
        w = t > 0
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
        ichg_idle=float((-r['i(vbt_am)'][idle]).max()) if (cfg['cell']['present'] and idle.any()) else 0.0,
        v3_pre=float(r['v(3v3)'][(t > pa['t_en'] - 1e-3) & (t < pa['t_en'])].min()) if cfg.get('sw_on') else 3.3,
        temp=cfg.get('temp', 25.0),
    )
    # 1-second-burst average of the cell current (for ratings), from the steady part
    res['icell_avg'] = float(np.mean(r['i(vbt_am)'][ws])) if (cfg['cell']['present'] and ws.any()) else 0.0
    res['ok_a'] = res['v3_min'] >= 1.9
    if not cfg['cell']['present']:
        res['ocd'] = res['uvp'] = False
    res['ok_b'] = not (res['ocd'] or res['uvp'])
    res['ok_c'] = (not res['bbrst']) and res['vpa_min'] >= 0.95 * pa['vset']
    res['pass'] = bool(res['ok_a'] and res['ok_b'] and res['ok_c'] and stopped is None)
    res['timed_out'] = False
    res['t_end'] = float(t[-1])
    res = dict((k, (bool(v) if isinstance(v, (bool, np.bool_)) else (float(v) if isinstance(v, (float, np.floating)) else v)))
               for k, v in res.items())
    # decimated waveform for plots
    keep = np.unique(np.searchsorted(t, np.linspace(0, t[-1], 4000)).clip(0, len(t) - 1))
    np.savez(os.path.join(OUT, name + '.npz'), **{k.replace('(', '_').replace(')', '').replace(',', '_'): v[keep]
                                                  for k, v in r.items()})
    json.dump(dict(key=key, res=res), open(cache, 'w'))
    return res


OPTS = ['.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200',
        '.option method=trap reltol=3e-3 abstol=1e-8 vntol=1e-5 itl4=300',
        '.option method=gear reltol=5e-3 abstol=1e-7 vntol=1e-4 itl4=500 gmin=1e-10']
PR_FIX = 374.0 / (562 + 374)    # proposed: PR1 bottom 301 k -> 374 k: IN1 priority down to 2.60 V (2.65 V rising)
VARIANTS = {'drawn': dict(lm='gnd', pr=None), 'fixed': dict(lm='diode', pr=PR_FIX)}


TEMPS = [-40, -20, 0, 25, 60, 85]


def cfg_for(ocv, rint, lvl, burst=0.2, usb=None, lm='gnd', present=True, pr_low=False, pr=None, temp=25.0):
    c = B.default_cfg()
    c['temp'] = temp
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
    if r.get('timed_out'):
        return 'solver crawled (supply chattering), stopped after 900 s: counted as FAIL'
    if r['stopped'] is not None:
        w.append('supply collapse (solver stopped at %.2f ms)' % (r['stopped'] * 1e3))
    elif not r['pass'] and r['t_end'] < 0.15:
        w.append('[run ends at the first fatal event, %.1f ms]' % (r['t_end'] * 1e3))
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
    P30, P34, P35 = B.PA_LEVELS[0], B.PA_LEVELS[3], B.PA_LEVELS[4]
    jobs = []
    for ta in TEMPS:
        for vn, v in VARIANTS.items():
            for ocv in OCVS:
                for rint in RINTS:
                    for li, lvl in enumerate(B.PA_LEVELS):
                        jobs.append(('g%s_%d_%g_%g_%d' % (vn[0], ta, ocv, rint * 1e3, li),
                                     cfg_for(ocv, rint, lvl, temp=ta, **v)))
    special = [
        ('s_fresh_3W_1s', cfg_for(4.2, 0.05, P35, burst=1.0)),
        ('s_fresh_1W_1s', cfg_for(4.2, 0.05, P30, burst=1.0)),
        ('s_mid_3W_1s', cfg_for(3.7, 0.15, P35, burst=1.0)),
        ('s_worn_1W_1s', cfg_for(3.1, 0.30, P30, burst=1.0)),
        ('s_fixed_mid_3W_1s', cfg_for(3.7, 0.15, P35, burst=1.0, lm='diode', pr=PR_FIX)),
        ('s_fixed_worn_1W_1s', cfg_for(3.1, 0.30, P30, burst=1.0, lm='diode', pr=PR_FIX)),
        ('u_37_150_3W_drawn', cfg_for(3.7, 0.15, P35, usb=5.0, lm='gnd')),
        ('u_37_150_3W_fix', cfg_for(3.7, 0.15, P35, usb=5.0, lm='diode', pr=PR_FIX)),
        ('u_31_300_1W_drawn', cfg_for(3.1, 0.30, P30, usb=5.0, lm='gnd')),
        ('u_31_300_1W_fix', cfg_for(3.1, 0.30, P30, usb=5.0, lm='diode', pr=PR_FIX)),
        ('u_31_300_3W_drawn', cfg_for(3.1, 0.30, P35, usb=5.0, lm='gnd')),
        ('u_31_300_3W_fix', cfg_for(3.1, 0.30, P35, usb=5.0, lm='diode', pr=PR_FIX)),
        ('n_1W_drawn', cfg_for(3.7, 0.15, P30, usb=5.0, lm='gnd', present=False)),
        ('n_1W_fix', cfg_for(3.7, 0.15, P30, usb=5.0, lm='diode', present=False, pr=PR_FIX)),
        ('n_1W_fix_pr', cfg_for(3.7, 0.15, P30, usb=5.0, lm='diode', present=False, pr_low=True)),
        ('n_2W5_drawn', cfg_for(3.7, 0.15, P34, usb=5.0, lm='gnd', present=False)),
        ('n_2W5_fix_pr', cfg_for(3.7, 0.15, P34, usb=5.0, lm='diode', present=False, pr_low=True)),
    ]
    # cold start: board switched on at -40 C on a cold cell, then the first burst
    cold = []
    for ocv, rint in ((3.7, 0.15), (3.7, 0.30), (4.2, 0.30)):
        for lvl, ln in ((P30, '1W'), (P35, '3W')):
            for vn, v in VARIANTS.items():
                c = cfg_for(ocv, rint, lvl, temp=-40.0, **v)
                c['sw_on'] = 1e-3
                c['pa'].update(t_en=10e-3, t_apc=13e-3, t_rf=13.2e-3)
                cold.append(('c_%g_%d_%s_%s' % (ocv, rint * 1e3, ln, vn), c))
    # hot: 85 C ambient, USB in, NTC out of window (charger TS = hot, so charging must stop), three 1 W bursts
    hot = []
    for vn, v in VARIANTS.items():
        for ocv in (3.7, 4.1):
            c = cfg_for(ocv, 0.15, P30, usb=5.0, temp=85.0, burst=0.3, **v)
            c['pa'].update(n=3, period=0.5)
            c['chg'] = dict(ts=0)
            hot.append(('h_%g_%s' % (ocv, vn), c))
        c = cfg_for(3.7, 0.15, P34, usb=5.0, temp=85.0, burst=0.3, **v)
        c['pa'].update(n=3, period=0.5)
        c['chg'] = dict(ts=0)
        hot.append(('h_3.7_2W5_%s' % vn, c))
    allj = jobs + special + cold + hot
    with ProcessPoolExecutor(4) as ex:
        res = dict((r['name'], r) for r in ex.map(run_case, allj))

    L = ['Study 4: transmit bursts from a worn cell (P2, X4), at ambient -40 / -20 / 0 / 25 / 60 / 85 C.',
         'Criteria: P2-a 3V3 >= 1.9 V; P2-b no BQ29700 trip (OCD/SCD/UVP); P2-c TPS63810 never in UVLO and VPA >= 95 % of',
         'its setting.  BUVLO reported, not failed.  R_int is the 25 C value; it is scaled x9 / x5 / x2 / x1 / x0.8 / x0.75',
         'at -40 / -20 / 0 / 25 / 60 / 85 C (powerlib.rint_k).  Cell = OCV behind R_int (pure resistance), + 2 x 20 mOhm leads.',
         'drawn = LM66100 CE = GND, PR1 562 k / 301 k (as in src/circuit.py); fixed = Schottky RB060MM in place of the',
         'LM66100 and PR1 562 k / 374 k.', '']
    maxp = {}
    for ta in TEMPS:
        for vn in VARIANTS:
            for ocv in OCVS:
                for rint in RINTS:
                    best = None
                    for li in range(len(B.PA_LEVELS)):
                        if res['g%s_%d_%g_%g_%d' % (vn[0], ta, ocv, rint * 1e3, li)]['pass']:
                            best = li
                    maxp[(vn, ta, ocv, rint)] = best
    L.append('Highest PA level that passes, battery only (R_int at 25 C in the header):')
    mrows = []
    for vn in VARIANTS:
        for ta in TEMPS:
            for ocv in OCVS:
                mrows.append([vn, '%d C' % ta, '%.1f V' % ocv] +
                             [B.PA_LEVELS[maxp[(vn, ta, ocv, r)]][0] if maxp[(vn, ta, ocv, r)] is not None else 'none'
                              for r in RINTS])
    L.append(S.table(mrows, ['variant', 'ambient', 'OCV'] + ['%d mOhm' % (r * 1e3) for r in RINTS]))
    L.append('')
    for ta in (25, -20):
        for vn in VARIANTS:
            rows = []
            for ocv in OCVS:
                for rint in RINTS:
                    for li, lvl in enumerate(B.PA_LEVELS):
                        r = res['g%s_%d_%g_%g_%d' % (vn[0], ta, ocv, rint * 1e3, li)]
                        rows.append(['%.1f V / %d mOhm' % (ocv, rint * 1e3), lvl[0], r['icell_max'], r['bat_min'],
                                     r['vsys_min'], r['v3_min'], r['pain_min'], r['vpa_min'],
                                     'yes' if r['buvlo'] else 'no', S.verdict(r['pass']), why(r)])
            L.append('Grid detail, %s, %d C, 0.2 s bursts, battery only:' % (vn, ta))
            L.append(S.table(rows, ['cell (R at 25 C)', 'PA level', 'Icell max A', 'BAT_P min', 'VSYS min', '3V3 min',
                                    'PA_IN min', 'VPA min', 'BUVLO', 'verdict', 'why']))
            L.append('  (every other ambient: sim/out/burst/g<d|f>_<T>_<OCV>_<mOhm>_<level>.json)')
            L.append('')

    def srow(name):
        r = res[name]
        return [name, '%d C' % r['temp'], r['icell_max'], r['bat_min'], r['vsys_min'], r['v3_min'], r['pain_min'],
                r['vpa_min'], r['ilm_fwd'], r['ilm_rev'], r['isup_max'], r['iin_chg_max'], r['imux2_max'],
                r['ichg_idle'] * 1e3, S.verdict(r['pass']), why(r)]
    hdr = ['case', 'ambient', 'Icell max', 'BAT_P min', 'VSYS min', '3V3 min', 'PA_IN min', 'VPA min', 'LM66100 fwd A',
           'LM66100 rev A', 'BATFET A', 'IN A', 'mux IN2 A', 'into cell idle mA', 'verdict', 'why']
    L.append('Showcase 1 s bursts and USB cases (25 C):')
    L.append(S.table([srow(n) for n, _ in special], hdr))
    L.append('  u_ = USB present (5 V, 1 m cable) + cell; n_ = no cell, USB only; _drawn = as drawn; _fix = Schottky in')
    L.append('  place of the LM66100 and PR1 562 k / 374 k; _pr = PR1 pulled low by a GPIO FET (mux forced to IN2)')
    L.append('  when no cell is fitted.  s_fixed_ = the fixed variant.')
    L.append('')
    L.append('Cold start at -40 C: slide switch on at 1 ms, PA enabled at 10 ms, first burst (0.2 s) at 13 ms.')
    L.append('Extra criterion: 3V3 >= 3.0 V before the PA is enabled (the board boots).')
    crows = []
    for n, _ in cold:
        r = res[n]
        ok = r['pass'] and r['v3_pre'] >= 3.0
        r['pass_cold'] = ok
        crows.append(srow(n)[:2] + [r['v3_pre']] + srow(n)[2:-2] + [S.verdict(ok), why(r) if r['v3_pre'] >= 3.0 or
                                                                   not r['pass'] else 'did not boot']
                     )
    L.append(S.table(crows, hdr[:2] + ['3V3 before PA'] + hdr[2:]))
    L.append('  c_<OCV>_<R_int at 25 C, mOhm>_<1W|3W>_<variant>; at -40 C R_int is x9 (150 -> 1.35 Ohm, 300 -> 2.7 Ohm).')
    L.append('')
    L.append('Hot: 85 C ambient, USB in, cell NTC out of the charger window (TS hot: the charger must not charge),')
    L.append('three 0.3 s bursts every 0.5 s.  Extra criterion (P7): <= 1 mA into the cell between bursts.')
    hrows = []
    for n, _ in hot:
        r = res[n]
        ok = r['pass'] and r['ichg_idle'] <= 1e-3
        r['pass_hot'] = ok
        w = why(r)
        if r['ichg_idle'] > 1e-3:
            w = ('cell charged at %.0f mA with charging disabled; ' % (r['ichg_idle'] * 1e3)) + w
        hrows.append(srow(n)[:-2] + [S.verdict(ok), w])
    L.append(S.table(hrows, hdr))
    S.write_results(HERE, L)

    # ---------------------------------------------------------------- stress for the derating table
    allr = [r for r in res.values() if not r.get('timed_out')]
    passing = [r for r in allr if r['pass']]
    worst = lambda k, rs: max(rs, key=lambda x: x[k])
    st = []
    rp = worst('icell_avg', passing)
    st.append(S.stress('JST-PH 2-pin (battery)', 'J (battery)', 'current, passing burst', rp['icell_avg'], 'A', 2.0,
                       'derate', '%s, %d C' % (rp['name'], rp['temp'])))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'drain current, passing burst', rp['icell_avg'], 'A', 3.2,
                       'derate', rp['name'] + ' (3.2 A min-Cu rating; 5.3 A max-Cu)'))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'power, passing burst (42 mOhm x rf at 85 C)',
                       rp['icell_avg'] ** 2 * 0.042 * 1.24, 'W', 0.5, 'derate', rp['name'] + ' (0.5 W min Cu)'))
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
    vin = rb['pain_min']
    vo = rb['vset']
    d = max(0.0, 1 - vin / vo)
    ilpk = rb['ibb_max'] + d * vin / (2e6 * 0.376e-6) / 2
    st.append(S.stress('DFE252012F-R47M', 'L (buck-boost)', 'peak current, passing burst', ilpk, 'A', 6.7, 'derate',
                       rb['name'] + ' (Isat 6.7 A; rated 4.9 A)'))
    st.append(S.stress('C47u 0805 6.3 V', 'C (VPA)', 'voltage', max(r['vpa_max'] for r in allr), 'V', 6.3, 'derate',
                       '35 dBm setting'))
    lmr = max([r for r in allr if r['ilm_max'] == r['ilm_max']], key=lambda x: x['ilm_max'])
    st.append(S.stress('LM66100', 'U (cell-to-SYS)', 'switch current (any case)', lmr['ilm_max'], 'A', 1.5, 'derate',
                       lmr['name'] + ' (1.5 A continuous, 2.5 A <= 120 ms pulsed)'))
    lmp = max(passing, key=lambda x: x['ilm_max'])
    st.append(S.stress('LM66100', 'U (cell-to-SYS)', 'switch current, passing bursts', lmp['ilm_max'], 'A', 1.5, 'derate',
                       lmp['name']))
    S.write_stress(HERE, st)

    # ---------------------------------------------------------------- plots
    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(16, 8))
    show = [('s_fresh_3W_1s', 'fresh 4.2 V / 50 mOhm, 3 W, 25 C'), ('c_3.7_300_1W_drawn', 'cold start -40 C, 3.7 V / 300 mOhm, 1 W, drawn'),
            ('h_3.7_drawn', '85 C, USB, NTC hot, 3 x 1 W, drawn')]
    for j, (n, title) in enumerate(show):
        d = np.load(os.path.join(OUT, n + '.npz'))
        tm = d['time'] * 1e3
        a = ax[0, j]
        for k, lab in (('v_bat_p', 'BAT_P'), ('v_vsys', 'VSYS'), ('v_3v3', '3V3'), ('v_pa_in', 'PA_IN'), ('v_vpa', 'VPA')):
            a.plot(tm, d[k], label=lab, lw=1)
        a.axhline(1.9, color='C3', lw=0.6, ls=':')
        a.set_title(title + ' (%s)' % S.verdict(res[n].get('pass_cold', res[n].get('pass_hot', res[n]['pass']))), fontsize=8)
        a.set_xlabel('ms')
        a.set_ylabel('V')
        a.set_ylim(0, 4.7)
        a.legend(fontsize=7, loc='lower right')
        a = ax[1, j]
        a.plot(tm, d['i_vbt_am'], label='cell (+ = discharge)')
        a.plot(tm, d['v_mx_i1'], label='mux IN1')
        a.plot(tm, d['v_mx_i2'], label='mux IN2')
        a.plot(tm, d['v_pblm_i'], label='LM66100 (BAT->SYS)')
        a.plot(tm, d['v_pa_i'], label='PA (VPA)')
        a.axhline(4.04, color='C3', lw=0.6, ls=':')
        a.set_xlabel('ms')
        a.set_ylabel('A')
        a.legend(fontsize=7, loc='upper right')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'burst.png'))

    fig, ax = plt.subplots(2, len(TEMPS), figsize=(3.2 * len(TEMPS), 6.5))
    for q, vn in enumerate(VARIANTS):
        for j, ta in enumerate(TEMPS):
            a = ax[q, j]
            grid = np.full((len(OCVS), len(RINTS)), -1.0)
            for i, ocv in enumerate(OCVS):
                for k, rint in enumerate(RINTS):
                    if maxp[(vn, ta, ocv, rint)] is not None:
                        grid[i, k] = maxp[(vn, ta, ocv, rint)]
            a.imshow(grid, cmap='viridis', vmin=-1, vmax=len(B.PA_LEVELS) - 1, aspect='auto')
            for i in range(len(OCVS)):
                for k in range(len(RINTS)):
                    lv = int(grid[i, k])
                    a.text(k, i, B.PA_LEVELS[lv][0].split(' (')[0] if lv >= 0 else 'none', ha='center', va='center',
                           color='w' if lv < 2 else 'k', fontsize=7)
            a.set_xticks(range(len(RINTS)))
            a.set_xticklabels(['%d' % (r * 1e3) for r in RINTS], fontsize=7)
            a.set_yticks(range(len(OCVS)))
            a.set_yticklabels(['%.1f V' % o for o in OCVS], fontsize=7)
            a.grid(False)
            a.set_title('%s, %d C' % (vn, ta), fontsize=8)
            if q == 1:
                a.set_xlabel('R_int at 25 C, mOhm', fontsize=7)
    fig.suptitle('highest passing PA level, battery only')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'maxpower.png'))

if __name__ == '__main__':
    main()
