# -*- coding: utf-8 -*-
"""Study 2: battery plugged in backwards (X1).

The cell (4.2 V, 50 mOhm, 0.1 uH leads) is plugged into the JST at 20 ms (USB, when present, is up) the
wrong way round: pad 1 (BATT_PLUS) gets its minus, pad 2 (CELL_MINUS) its
plus.  The whole board power path (sim/board.py) is in the netlist: the
CSD25485F5 reverse P-FET with its gate 100 k to CELL_MINUS, the BQ29700 +
SSM10N954L protector (CELL_MINUS is its VSS), the LM66100, the BQ25185
(BAT pin), the TPS2121 IN1, VSYS, the 3.3 V buck and its 13 mA load.
Every IC pin on BAT_P / VSYS / MUX_IN1 has a substrate diode to GND, the
BQ29700 its VSS->BAT and V- -> BAT ESD diodes, so pin currents show up.
Run to 2 s, past the BQ29700's slowest timer (OVP 1.25 s).

Cases: no USB; USB present with the LM66100 as drawn (CE = GND) and with
the proposed Schottky in its place ('_fix'); a normal (right-way) plug-in for reference.  Without a cell,
CELL_MINUS has no DC path to GND (the protector FETs are off and the
BQ29700's supply current flows out of VSS), so where it sits before the plug
depends on leakage.  The '_held' cases put 100 k from CELL_MINUS to GND: the
BQ29700 is then powered from BAT_P with its FETs on when the reversed cell
lands, the worst case for the reverse FET.

Pass criteria (X1), fixed before running:
  reverse FET: |VGS| <= 12 V, |VDS| <= 20 V, dissipation <= 0.5 W (min-Cu
    rating, i.e. no thermal damage), drain current <= 3.2 A continuous
  BQ29700: BAT - VSS >= -0.3 V and <= 12 V, V- <= BAT + 0.3 V, V- >= BAT - 28 V;
    ESD-diode current <= 1 mA (no sustained pin conduction)
  no IC pin on BAT_P, VSYS or MUX_IN1 below -0.3 V; substrate-diode current
    <= 1 mA
  cell current after the plug-in transient <= 10 mA (no discharge path)

Outputs: results.txt, stress.json, reverse.png.   Run: python3 run.py
"""
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import board as B
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('reverse')
T_PLUG = 20e-3
TSTOP = 2.0

ESD = """* substrate diodes of the ICs on these nets (pin abs min -0.3 V)
Vesd1 esd1 0 0
Desd1 esd1 MUX_IN1 DESD
Vesd2 esd2 0 0
Desd2 esd2 VSYS DESD
"""


TEMPS = [-40, -20, 0, 25, 60, 85]


def cfg(reverse=True, usb=None, lm='gnd', ocv=4.2, held=False, clamp=False, temp=25.0):
    c = B.default_cfg()
    c['temp'] = temp
    c['cell'].update(ocv=ocv, rint=0.05, reverse=reverse, plug_t=T_PLUG)
    c['usb'] = usb
    c['lm'] = lm
    c['pa']['on'] = False
    c['extra'] = ESD + ('* worst case: CELL_MINUS held near GND before the plug (FET / board leakage), so the\n'
                        '* BQ29700 is powered from BAT_P and its FETs are ON when the reversed cell lands\n'
                        'Rheld CELL_MINUS 0 100k\n' if held else '') + (
        '* proposed: Schottky clamp GND -> BAT_P (RB060MM) so a negative swing goes through it, not IC substrates\n'
        'Dclamp 0 BAT_P DRB060\n' if clamp else '')
    c['tstop'] = TSTOP
    c['tmax'] = 2e-4
    if usb:
        # USB up before the cell: BAT_P held by the charger (and the LM66100 as drawn), the BQ29700 powered from
        # BAT_P with VSS = CELL_MINUS pulled to GND through its own FETs, so the protector is ON before the plug
        vb = 4.43 if lm == 'gnd' else 4.2
        c['nodeset'] = dict(BAT_P=vb, BAT_P_C=vb, MUX_IN1=vb, PROT_BAT=vb, PROT_DOUT=vb, PROT_COUT=vb, PBval=1,
                            CELL_MINUS=0, REV_G=0, VSYS=4.5, VSYS_SW=4.5)
    return c


def run(args):
    name, c = args
    def make(o):
        c['opt'] = o
        net = B.build(c, name + '.raw')
        return re.sub(r'write %s\.raw .*' % name, 'write %s.raw all' % name, net)
    stopped = S.ngspice_retry(make, OUT, name)
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    os.remove(os.path.join(OUT, name + '.raw'))
    t = r['time']
    V = lambda n: r['v(%s)' % n.lower()] if n != '0' else np.zeros_like(t)
    after = t > T_PLUG
    late = t > T_PLUG + 0.1
    icell = r['i(vbt_am)']
    vds = V('BATT_PLUS') - V('BAT_P_C')
    vgs = V('REV_G') - V('BAT_P_C')
    pfet = np.abs(vds * icell)
    vb = V('PROT_BAT') - V('CELL_MINUS')
    vmb = V('PROT_VM') - V('PROT_BAT')
    ibat_pin = (V('BAT_P') - V('PROT_BAT')) / 330.0
    res = dict(
        name=name, vds_min=vds[after].min(), vds_max=vds[after].max(), vgs_min=vgs[after].min(),
        vgs_max=vgs[after].max(), icell_max=np.abs(icell[after]).max(), icell_late=np.abs(icell[late]).max(),
        pfet_max=pfet[after].max(), pfet_late=pfet[late].max(), vb_min=vb[after].min(), vb_max=vb[after].max(),
        vmb_max=vmb[after].max(), vmb_min=vmb[after].min(), ivss_max=np.abs(r['i(vpbamvss)'][after]).max(),
        ivm_max=np.abs(r['i(vpbamvm)'][after]).max(), ibatpin_max=np.abs(ibat_pin[after]).max(),
        iesd_mux=np.abs(r['i(vesd1)'][after]).max(), iesd_sys=np.abs(r['i(vesd2)'][after]).max(),
        iesd_chb=np.abs(r['i(vchesb)'][after]).max(), iesd_chb_late=np.abs(r['i(vchesb)'][late]).max(),
        iesd_mux_late=np.abs(r['i(vesd1)'][late]).max(), bat_p_late=V('BAT_P')[late].mean(),
        bat_p_end=V('BAT_P')[-1],
        bat_p_min=V('BAT_P')[after].min(), bat_p_max=V('BAT_P')[after].max(), vsys_min=V('VSYS')[after].min(),
        vsys_late=V('VSYS')[late].mean(), cm_min=V('CELL_MINUS')[after].min(), cm_max=V('CELL_MINUS')[after].max(),
        bp_min=V('BATT_PLUS')[after].min(), bp_max=V('BATT_PLUS')[after].max(),
        ilm_max=np.abs(r['v(pblm_i)'][after]).max(), v3_late=V('3V3')[late].mean(),
        ocd=r['v(pbocd)'].max() > 0.5, occ=r['v(pbocc)'].max() > 0.5, ovp=r['v(pbovp)'].max() > 0.5,
        uvp=r['v(pbuvp)'].max() > 0.5, stopped=stopped,
    )
    # every node: extreme voltages after the plug
    nets = ('batt_plus', 'cell_minus', 'rev_g', 'bat_p_c', 'bat_p', 'prot_bat', 'prot_vm', 'prot_dout', 'prot_cout',
            'prot_d', 'prot_s2', 'vbat_sense', 'vsys', 'vsys_sw', '3v3', 'mux_in1', 'pa_in', 'vpa', 'vin_chg', 'usb_5v',
            'usb_vbus')
    res['nodes'] = dict((n, (float(r['v(%s)' % n][after].min()), float(r['v(%s)' % n][after].max())))
                        for n in nets if 'v(%s)' % n in r)
    dt = np.diff(t, prepend=t[0])
    neg = after & ((V('BAT_P') < -0.3) | (V('MUX_IN1') < -0.3))
    res['t_neg'] = float(dt[neg].sum())
    res['q_sub'] = float((np.abs(r['i(vesd1)']) * dt)[after].sum() + (np.abs(r['i(vchesb)']) * dt)[after].sum())
    keep = np.unique(np.concatenate([np.searchsorted(t, np.linspace(T_PLUG - 1e-3, T_PLUG + 0.02, 2000)),
                                     np.searchsorted(t, np.linspace(0, TSTOP, 1500))])).clip(0, len(t) - 1)
    np.savez(os.path.join(OUT, name + '.npz'), t=t[keep], icell=icell[keep], vds=vds[keep], vgs=vgs[keep],
             bat_p=V('BAT_P')[keep], cm=V('CELL_MINUS')[keep], vsys=V('VSYS')[keep], pfet=pfet[keep])
    return res


def main():
    base = [('rev_nousb', dict()), ('rev_usb_drawn', dict(usb=5.0, lm='gnd')),
            ('rev_usb_fix', dict(usb=5.0, lm='diode')),
            ('rev_usb_drawn_held', dict(usb=5.0, lm='gnd', held=True)),
            ('rev_usb_fix_held', dict(usb=5.0, lm='diode', held=True)),
            ('rev_usb_fix_held_clamp', dict(usb=5.0, lm='diode', held=True, clamp=True)),
            ('rev_nousb_held', dict(held=True)),
            ('fwd_nousb', dict(reverse=False, held=True))]
    cases = [('%s_%d' % (n, ta), cfg(temp=float(ta), **kw)) for ta in TEMPS for n, kw in base]
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(run, cases))
    L = ['Study 2: battery plugged in backwards (X1).  4.2 V cell, 50 mOhm, plugged at 20 ms, run to 2 s.',
         'Limits: CSD25485F5 |VGS| 12 V, |VDS| 20 V, 0.5 W (min Cu), 3.2 A; BQ29700 BAT-VSS -0.3..12 V, V- <= BAT + 0.3 V;',
         'IC pins >= -0.3 V; pin / substrate-diode current <= 1 mA; cell current after 100 ms <= 10 mA.', '']
    rows = []
    for r in res:
        f = []
        if r['name'].startswith('rev'):
            if max(abs(r['vgs_min']), abs(r['vgs_max'])) > 12:
                f.append('VGS')
            if max(abs(r['vds_min']), abs(r['vds_max'])) > 20:
                f.append('VDS')
            if r['pfet_late'] > 0.5:
                f.append('FET %.1f W' % r['pfet_late'])
            if r['vb_min'] < -0.3 or r['vb_max'] > 12:
                f.append('BQ29700 BAT-VSS %.1f..%.1f V' % (r['vb_min'], r['vb_max']))
            if r['vmb_max'] > 0.3:
                f.append('V- above BAT')
            if max(r['ivss_max'], r['ivm_max'], r['iesd_mux'], r['iesd_sys']) > 1e-3:
                f.append('pin current')
            if r['bat_p_min'] < -0.3 or r['vsys_min'] < -0.3:
                f.append('IC pin < -0.3 V')
            if r['icell_late'] > 10e-3:
                f.append('cell discharging %.2f A' % r['icell_late'])
            if r['t_neg'] > 0:
                f.append('BAT_P below -0.3 V for %.0f us, %.0f uC through substrate diodes' % (r['t_neg'] * 1e6,
                                                                                            r['q_sub'] * 1e6))
        r['verdict'] = 'FAIL' if f else 'PASS'
        r['why'] = ', '.join(f) or '-'
        rows.append([r['name'], r['icell_max'], r['icell_late'], r['vds_min'], r['vgs_min'], r['vgs_max'], r['pfet_late'],
                     r['vb_min'], r['vb_max'], r['vmb_max'], r['bat_p_min'], r['bat_p_max'], r['cm_min'], r['cm_max'],
                     r['ilm_max'], r['verdict'], r['why']])
    L.append(S.table(rows, ['case', 'Icell pk A', 'Icell >100ms A', 'FET VDS min', 'VGS min', 'VGS max', 'FET W >100ms',
                            'BAT-VSS min', 'BAT-VSS max', 'V- - BAT max', 'BAT_P min', 'BAT_P max', 'CELL_MINUS min',
                            'CELL_MINUS max', 'LM66100 |I| A', 'verdict', 'why']))
    L.append('')
    bn = []
    for r in res:
        b0 = r['name'].rsplit('_', 1)[0]
        if b0 not in bn:
            bn.append(b0)
    V_ = dict((r['name'], r['verdict']) for r in res)
    L.append('Verdict per case and ambient:')
    L.append(S.table([[b0] + [V_['%s_%d' % (b0, ta)] for ta in TEMPS] for b0 in bn], ['case'] + ['%d C' % t for t in TEMPS]))
    L.append('  _held: CELL_MINUS held near GND before the plug (protector on), the worst case for the reverse FET;')
    L.append('  _clamp: plus the proposed Schottky clamp from GND to BAT_P.')
    L.append('')
    L.append('Pin currents (peak, A): BQ29700 VSS, V-, BAT (through 330 R); substrate diodes on MUX_IN1, VSYS and the')
    L.append('BQ25185 BAT pin:')
    L.append(S.table([[r['name'], r['ivss_max'], r['ivm_max'], r['ibatpin_max'], r['iesd_mux'], r['iesd_sys'], r['iesd_chb']]
                      for r in res], ['case', 'VSS', 'V-', 'BAT', 'mux IN1 sub', 'VSYS sub', 'BQ25185 BAT sub']))
    L.append('')
    L.append('Protector flags (OCD/SCD, OCC, OVP, UVP) and late VSYS / 3V3:')
    L.append(S.table([[r['name'], r['ocd'], r['occ'], r['ovp'], r['uvp'], r['vsys_late'], r['v3_late']] for r in res],
                     ['case', 'OCD', 'OCC', 'OVP', 'UVP', 'VSYS V', '3V3 V']))
    L.append('')
    L.append('Every node, min / max after the plug (V), 25 C:')
    for r in [x for x in res if x['name'].endswith('_25')]:
        L.append('  %s: ' % r['name'] + ', '.join('%s %.2f/%.2f' % (k, a, b) for k, (a, b) in sorted(r['nodes'].items())))
    S.write_results(HERE, L)

    st = []
    w = max([r for r in res if r['name'].startswith('rev')], key=lambda x: abs(x['vds_min']))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'VDS, reversed cell', abs(w['vds_min']), 'V', 20.0, 'derate', w['name']))
    w = max([r for r in res if r['name'].startswith('rev')], key=lambda x: max(abs(x['vgs_min']), x['vgs_max']))
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'VGS, reversed cell', max(abs(w['vgs_min']), w['vgs_max']), 'V', 12.0,
                       'derate', w['name']))
    w = max([r for r in res if r['name'].startswith('rev')], key=lambda x: x['pfet_late'])
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'dissipation, reversed cell', w['pfet_late'], 'W', 0.5, 'derate',
                       w['name']))
    w = max(res, key=lambda x: x['vb_max'])
    st.append(S.stress('BQ29700', 'U (protector)', 'BAT - VSS', w['vb_max'], 'V', 12.0, 'absmax', w['name']))
    S.write_stress(HERE, st)

    plt = S.style()
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for r in [x for x in res if x['name'].endswith('_25') or x['name'].endswith('_held_-40')]:
        d = np.load(os.path.join(OUT, r['name'] + '.npz'))
        tm = d['t'] * 1e3
        ax[0].plot(tm, d['icell'], label=r['name'])
        ax[1].plot(tm, d['vgs'], label=r['name'] + ' VGS')
        ax[2].plot(tm, d['pfet'], label=r['name'])
    ax[0].set_ylabel('cell current A (out of its + lead)')
    ax[1].set_ylabel('reverse FET VGS V')
    ax[2].set_ylabel('reverse FET dissipation W')
    for a in ax:
        a.set_xlabel('ms')
        a.set_xscale('symlog', linthresh=1.0)
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'reverse.png'))


if __name__ == '__main__':
    main()
