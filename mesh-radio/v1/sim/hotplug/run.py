# -*- coding: utf-8 -*-
"""Study 1: hot plug and over-voltage on the three inputs (X3, with P4-P6).

Each input is plugged in through its cable / lead at t = 20 us (100 ns
contact edge) and run for 12 ms, long enough for the eFuse's 2 V/ms soft
start to finish:
  USB-C: 1 m cable (1 uH, 0.2 ohm) -> TVS2200 + 1 uF -> TPS259470A (UV 4.33 V,
         OV 5.38 V, 1.51 A) -> USB_5V (nRF52840 VBUS, 4.7 uF, 47 k) -> RB060MM
         -> VIN_CHG (1 uF + 10 uF) -> BQ25185 (cell 3.7 V behind it)
  solar: panel (single-diode model) + 1 m lead (1 uH, 0.1 ohm) -> RB060MM ->
         TVS2200 + 1 uF -> TPS259470A (UV 3.55 V, OV 9.96 V, 1.34 A) -> VIN_CHG
  drone: 30 cm JST-GH cable (0.3 uH, 0.05 ohm) -> RB060MM -> TVS2200 + 1 uF ->
         TPS259470A (UV 4.33 V, OV 5.80 V, 1.34 A) -> VIN_CHG
Cases: USB 5 V and 20 V hot plug, USB 5 -> 20 V step while running,
12 V panel (21 V open circuit at 25 C) at 25 C and at -20 / -40 C (Voc rises
2.2 mV/C per cell), 6 V 1 W panel, drone 5 V and 20 V.  The TVS uses its
maximum breakdown (27.6 V) for pin-voltage checks; the cold-panel case also
runs the minimum (24.6 V), which is the one that decides whether it conducts.

Pass criteria (X3), fixed before running:
  eFuse IN <= 28 V abs max; IN slew <= 100 V/us rising, <= 10 V/us falling
  EN/UVLO and OVLO pins <= 6.5 V
  USB_5V (nRF52840 VBUS) <= 5.8 V abs max (5.5 V recommended)
  VIN_CHG (BQ25185 IN) <= 25 V abs max, and the charger never sees more
  than the eFuse's OV cut-off
  20 V on any input: that eFuse never turns on (OV cut-off works)
  TVS2200: no DC conduction above its 18 mA DC breakdown rating
Also: the UVLO threshold's sensitivity to the 4.7 V zener's leakage (EN
divider 1 M on top), and the OV threshold against USB source tolerance.

Outputs: results.txt, stress.json, hotplug.png.   Run: python3 run.py
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import powerlib as P
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('hotplug')

T_PLUG = 20e-6
TSTOP = 12e-3

# eFuse dividers (src/circuit.py inputs())
USB = dict(rt_uv=1e6, rb_uv=383e3, rt_ov=1e6, rb_ov=287e3, rilm=2210)
SOL = dict(rt_uv=1e6, rb_uv=510e3, rt_ov=1e6, rb_ov=137e3, rilm=2490)
DRN = dict(rt_uv=1e6, rb_uv=383e3, rt_ov=1e6, rb_ov=261e3, rilm=2490)


def netlist(case, raw):
    kind = case['kind']
    s = ['* hot plug: %s' % case['name'], P.MODELS]
    tvs = case.get('tvs', 'MAX')
    if kind in ('usb', 'drone'):
        v1 = case['v']
        if case.get('step'):
            t2, v2 = case['step']
            s.append('Vsrc src 0 pwl(0 0 %g 0 %g %g %g %g %g %g)' % (T_PLUG, T_PLUG + 1e-7, v1, t2, v1, t2 + 1e-6, v2))
        else:
            s.append('Vsrc src 0 pwl(0 0 %g 0 %g %g)' % (T_PLUG, T_PLUG + 1e-7, v1))
        cab = (0.2, 1e-6) if kind == 'usb' else (0.05, 0.3e-6)
        s.append(P.rl('cab', 'src', 'conn', *cab))
    else:
        s.append(P.panel('PV', 'pv', '0', case['voc'], case['isc'], case['ncell'], case.get('temp', 25.0)))
        s.append('Vctl ctl 0 pwl(0 0 %g 0 %g 1)' % (T_PLUG, T_PLUG + 1e-7))
        s.append('Splug pv pvs ctl 0 SWI')
        s.append(P.rl('cab', 'pvs', 'conn', 0.1, 1e-6))
    if kind == 'usb':
        s.append(P.rl('tr', 'conn', 'RAW', 0.005, 5e-9))
        s.append(P.tvs2200('tvs', 'RAW', tvs))
        s.append(P.cap('craw', 'RAW', '0', 0.9e-6))
        s.append(P.efuse('FU', 'RAW', 'EOUT', zleak=case.get('zleak', 0.0), **USB))
        s.append(P.cap('c5v', 'EOUT', '0', 2.5e-6) + 'R5vb EOUT 0 47k\n')
        s.append(P.schottky('dusb', 'EOUT', 'VIN_CHG'))
    else:
        s.append(P.rl('tr', 'conn', 'CONN2', 0.005, 5e-9))
        s.append(P.schottky('drev', 'CONN2', 'RAW'))
        s.append(P.tvs2200('tvs', 'RAW', tvs))
        s.append(P.cap('craw', 'RAW', '0', 0.9e-6))
        s.append(P.efuse('FU', 'RAW', 'VIN_CHG', zleak=case.get('zleak', 0.0), **(DRN if kind == 'drone' else SOL)))
        s.append('Rout EOUT 0 1Meg\nVeo EOUT VIN_CHG 0\n')
    s.append(P.cap('cvc1', 'VIN_CHG', '0', 0.9e-6) + P.cap('cvc2', 'VIN_CHG', '0', 8e-6) + 'Rvcl VIN_CHG 0 1Meg\n')
    # charger with a 3.7 V cell behind it and a 50 mA system load
    s.append(P.bq25185('CH', 'VIN_CHG', 'VSYS', 'BAT'))
    s.append('Vcell cellp 0 3.7\nRcell cellp BAT 0.1\n' + P.cap('csys', 'VSYS', '0', 8e-6) + 'Rsys VSYS 0 80\n')
    s.append(P.lm66100('LM', 'BAT', 'VSYS', 'gnd'))
    vec = ['v(raw)', 'v(eout)', 'v(vin_chg)', 'v(fu_en)', 'v(fu_ov)', 'v(fu_i)', 'v(fu_ena)', 'v(ch_iin)',
           'v(conn)', 'v(vsys)']
    s.append('.nodeset v(VSYS)=3.6 v(BAT)=3.7')
    s.append('.option method=gear reltol=1e-3 abstol=1e-9 vntol=1e-5 itl4=200')
    s.append('.tran 1n %g 0 %g' % (TSTOP, case.get('tmax', 0.2e-6)))
    s.append('.control\nset filetype=binary\nrun\nwrite %s %s i(vtvsam)\n.endc\n.end' % (raw, ' '.join(vec)))
    return '\n'.join(s) + '\n'


def run(case):
    name = case['name']
    S.ngspice(netlist(case, name + '.raw'), OUT, name)
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    t = r['time']
    v = r['v(raw)']
    dv = np.diff(v) / np.maximum(np.diff(t), 1e-12)
    m = t[1:] > T_PLUG
    itvs = r['i(vtvsam)']
    late = t > TSTOP - 2e-3
    res = dict(name=name, label=case['label'], raw_max=v.max(), dvr=dv[m].max() / 1e6, dvf=-dv[m].min() / 1e6,
               en_max=r['v(fu_en)'].max(), ov_max=r['v(fu_ov)'].max(), out_max=r['v(eout)'].max(),
               vin_max=r['v(vin_chg)'].max(), out_end=r['v(eout)'][-1], vin_end=r['v(vin_chg)'][-1],
               ena_max=r['v(fu_ena)'].max(), ena_end=r['v(fu_ena)'][-1], i_max=r['v(fu_i)'].max(), iin_end=r['v(ch_iin)'][-1],
               tvs_ipk=itvs.max(), tvs_idc=itvs[late].mean(), raw_end=v[-1],
               tvs_e=np.trapezoid(np.clip(itvs, 0, None) * v, t), kind=case['kind'])
    keep = np.unique(np.concatenate([np.where(t < 200e-6)[0][::2], np.searchsorted(t, np.linspace(0, TSTOP, 3000))]))
    keep = keep[keep < len(t)]
    np.savez(os.path.join(OUT, name + '.npz'), **{k.replace('(', '_').replace(')', ''): a[keep] for k, a in r.items()})
    os.remove(os.path.join(OUT, name + '.raw'))
    return res


def voc_at(voc25, ncell, temp):
    return voc25 - 0.0022 * ncell * (temp - 25)


def main():
    cases = [
        dict(name='usb5', label='USB 5 V hot plug', kind='usb', v=5.0),
        dict(name='usb5p5', label='USB 5.5 V (vSafe5V max) hot plug', kind='usb', v=5.5),
        dict(name='usb20', label='USB 20 V hot plug (fault)', kind='usb', v=20.0),
        dict(name='usb5to20', label='USB 5 V -> 20 V step, 1 us', kind='usb', v=5.0, step=(6e-3, 20.0)),
        dict(name='sol12', label='12 V panel, 21 V Voc, 25 C', kind='solar', voc=21.0, isc=0.33, ncell=36, temp=25),
        dict(name='sol12m20', label='12 V panel at -20 C (TVS min 24.6 V)', kind='solar', voc=21.0, isc=0.33,
             ncell=36, temp=-20, tvs='MIN'),
        dict(name='sol12m40', label='12 V panel at -40 C (TVS min 24.6 V)', kind='solar', voc=21.0, isc=0.33,
             ncell=36, temp=-40, tvs='MIN'),
        dict(name='sol6', label='6 V 1 W panel (7.2 V Voc), 25 C', kind='solar', voc=7.2, isc=0.185, ncell=12, temp=25),
        dict(name='sol6c', label='6 V 1 W panel at -40 C', kind='solar', voc=7.2, isc=0.185, ncell=12, temp=-40),
        dict(name='drn5', label='drone 5 V hot plug', kind='drone', v=5.0),
        dict(name='drn20', label='drone 20 V hot plug (fault)', kind='drone', v=20.0),
    ]
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(run, cases))
    R = dict((r['name'], r) for r in res)

    L = ['Study 1: hot plug and over-voltage (X3).  Limits: eFuse IN 28 V, IN slew 100 V/us up / 10 V/us down,',
         'EN/UVLO and OVLO 6.5 V, nRF52840 VBUS 5.8 V (5.5 V recommended), BQ25185 IN 25 V; 20 V never passes an eFuse;',
         'TVS2200 DC breakdown current <= 18 mA.  TVS at maximum breakdown (27.6 V) unless the case says otherwise.', '']
    rows = []
    for r in res:
        fails = []
        if r['raw_max'] > 28.0:
            fails.append('IN > 28 V')
        if r['dvr'] > 100:
            fails.append('IN rise slew')
        marg = []
        if r['dvf'] > 10:
            fails.append('IN fall slew %.0f V/us' % r['dvf'])
        if max(r['en_max'], r['ov_max']) > 6.5:
            fails.append('EN/OV pin > 6.5 V')
        if r['kind'] == 'usb' and r['out_max'] > 5.8:
            fails.append('VBUS > 5.8 V')
        if r['vin_max'] > 25:
            fails.append('charger IN > 25 V')
        if r['tvs_idc'] > 0.018:
            fails.append('TVS DC %.0f mA' % (r['tvs_idc'] * 1e3))
        hi = ('20' in r['name'] and r['name'] != 'usb5to20') or r['name'].startswith('sol12')
        if hi and max(r['out_max'], r['vin_max']) > 1.0:
            fails.append('eFuse passed the over-voltage')
        if r['name'] == 'usb5to20' and r['ena_end'] > 0.5:
            fails.append('OV did not cut off')
        if r['raw_max'] > 27.0 and not fails:
            marg.append('IN within 1 V of 28 V')
        if r['kind'] == 'usb' and r['out_max'] > 5.5 and not fails:
            marg.append('VBUS above 5.5 V rec.')
        if r['name'] in ('usb5', 'usb5p5', 'drn5', 'sol6', 'sol6c') and r['ena_end'] < 0.5:
            marg.append('input did not switch on')
        r['verdict'] = 'FAIL' if fails else ('MARGINAL' if marg else 'PASS')
        rows.append([r['label'], r['raw_max'], r['dvr'], r['dvf'], r['en_max'], r['ov_max'], r['out_max'], r['vin_max'],
                     'on' if r['ena_end'] > 0.5 else 'off', r['tvs_ipk'], r['tvs_idc'] * 1e3, r['verdict'],
                     ', '.join(fails + marg) or '-'])
    L.append(S.table(rows, ['case', 'IN max V', 'dV/dt up V/us', 'dV/dt down V/us', 'EN max', 'OVLO max',
                            'eFuse OUT max', 'VIN_CHG max', 'eFuse', 'TVS pk A', 'TVS DC mA', 'verdict', 'notes']))
    L.append('  (eFuse OUT = USB_5V for USB; for solar / drone the eFuse output is VIN_CHG.)')
    L.append('')
    # 12 V panel Voc vs temperature against the TVS breakdown
    L.append('12 V panel (36 cells, 21.0 V Voc at 25 C, -2.2 mV/C/cell) against the TVS2200 breakdown 24.6 / 25.9 / 27.6 V:')
    trows = []
    for tc in (25, 0, -10, -20, -30, -40):
        vo = voc_at(21.0, 36, tc)
        trows.append(['%d C' % tc, vo, vo - 0.30, 'conducts' if vo - 0.30 > 24.6 else 'no'])
    L.append(S.table(trows, ['cell temp', 'Voc V', 'after RB060MM V', 'TVS (min VBR)']))
    L.append('  A conducting TVS2200 carries the panel current (Isc 0.33 A) continuously: 8 W against an 18 mA DC rating.')
    L.append('')
    # zener leakage and UVLO / OV thresholds
    L.append('EN/UVLO threshold vs. 4.7 V zener leakage (UDZV4.7B: IR <= 2 uA at 1 V, 25 C; 1 M top resistor):')
    zrows = []
    for nm, d in (('USB', USB), ('solar', SOL), ('drone', DRN)):
        base = 1.20 * (1 + d['rt_uv'] / d['rb_uv'])
        ov = 1.20 * (1 + d['rt_ov'] / d['rb_ov'])
        ovmin = 1.183 * (1 + 0.99 * d['rt_ov'] / (1.01 * d['rb_ov']))
        ovmax = 1.223 * (1 + 1.01 * d['rt_ov'] / (0.99 * d['rb_ov']))
        zrows.append([nm, base, base + 0.1e-6 * d['rt_uv'], base + 1e-6 * d['rt_uv'], base + 2e-6 * d['rt_uv'], ov, ovmin,
                      ovmax])
    L.append(S.table(zrows, ['input', 'UVLO rise V (no leak)', '+0.1 uA', '+1 uA', '+2 uA (datasheet max)',
                             'OV nom V', 'OV min (1 % R)', 'OV max (1 % R)']))
    L.append('  With 2 uA the USB and drone UVLO (6.3 V) sits above their OV cut-off: those inputs would never switch on.')
    L.append('  USB sources may legally sit at up to 5.25 V (USB 2.0) / 5.5 V (Type-C vSafe5V); the USB OV cut-off is')
    L.append('  5.22-5.57 V (comparator and 1 %% resistor tolerance): a 5.25-5.5 V charger can be refused.  Once tripped,')
    L.append('  OVLO only releases below 1.09 V on the pin, i.e. %.2f V on VBUS.' % (1.09 * (1 + USB['rt_ov'] / USB['rb_ov'])))
    L.append('')
    # zener-leak transient check (USB, 1 uA)
    S.write_results(HERE, L)

    st = []
    w = max(res, key=lambda x: x['raw_max'])
    st.append(S.stress('TPS259470A', 'U (eFuse IN)', 'peak input voltage', w['raw_max'], 'V', 28.0, 'absmax', w['label']))
    st.append(S.stress('TPS259470A', 'U (eFuse IN)', 'steady input voltage (20 V fault / 12 V panel)', 21.0, 'V', 23.0,
                       'rec', '23 V recommended maximum'))
    w = max(res, key=lambda x: x['en_max'])
    st.append(S.stress('TPS259470A', 'U (EN/UVLO pin)', 'peak voltage', w['en_max'], 'V', 6.5, 'absmax', w['label']))
    w = max(res, key=lambda x: x['ov_max'])
    st.append(S.stress('TPS259470A', 'U (OVLO pin)', 'peak voltage', w['ov_max'], 'V', 6.5, 'absmax', w['label']))
    st.append(S.stress('C1u25 0603 25 V', 'C (raw inputs)', 'steady voltage, 12 V panel / 20 V fault', 21.0, 'V', 25.0,
                       'derate', 'continuous with a 12 V panel at 25 C (24 V+ cold)'))
    st.append(S.stress('TVS2200', 'D (surge clamp)', 'standoff, 12 V panel at 25 C', 21.0 - 0.3, 'V', 22.0, 'rec',
                       'VRWM 22 V'))
    st.append(S.stress('RB060MM-30', 'D (solar / drone reverse block)', 'reverse voltage, panel reversed (cold)',
                       voc_at(21.0, 36, -40), 'V', 30.0, 'derate', '12 V panel plugged in backwards at -40 C'))
    w = max([r for r in res if r['kind'] == 'usb'], key=lambda x: x['out_max'])
    st.append(S.stress('nRF52840', 'U (VBUS)', 'peak voltage', w['out_max'], 'V', 5.8, 'absmax', w['label']))
    st.append(S.stress('nRF52840', 'U (VBUS)', 'steady voltage at OV max', 1.223 * (1 + 1.01e6 / (0.99 * 287e3)), 'V', 5.5,
                       'rec', 'a source just under the USB OV cut-off'))
    w = max(res, key=lambda x: x['vin_max'])
    st.append(S.stress('BQ25185', 'U (IN)', 'peak voltage', w['vin_max'], 'V', 25.0, 'absmax', w['label']))
    st.append(S.stress('BQ25185', 'U (IN)', 'steady voltage (solar OV cut-off max)', 1.223 * (1 + 1.01e6 / (0.99 * 137e3)),
                       'V', 18.0, 'rec', 'VIN_OP 18 V'))
    st.append(S.stress('C10u25 0805 25 V', 'C (VIN_CHG)', 'steady voltage (solar OV max)', 1.223 * (1 + 1.01e6 / (0.99 * 137e3)),
                       'V', 25.0, 'derate', 'solar eFuse passes up to its OV cut-off'))
    st.append(S.stress('C4u7 0603 10 V', 'C (USB_5V)', 'voltage at OV max', 1.223 * (1 + 1.01e6 / (0.99 * 287e3)), 'V', 10.0,
                       'derate', ''))
    S.write_stress(HERE, st)

    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(16, 8))
    panels = [('usb5', 'USB 5 V hot plug'), ('usb20', 'USB 20 V hot plug'), ('usb5to20', 'USB 5 -> 20 V while on'),
              ('sol12m20', '12 V panel, -20 C, TVS min'), ('sol6', '6 V panel'), ('drn20', 'drone 20 V')]
    for a, (n, title) in zip(ax.flat, panels):
        d = np.load(os.path.join(OUT, n + '.npz'))
        tm = (d['time'] - T_PLUG) * 1e3
        a.plot(tm, d['v_raw'], label='eFuse IN')
        a.plot(tm, d['v_eout'], label='eFuse OUT')
        a.plot(tm, d['v_vin_chg'], label='VIN_CHG')
        a.plot(tm, d['v_fu_en'], label='EN/UVLO')
        a.plot(tm, d['v_fu_ov'], label='OVLO')
        a.axhline(28, color='C3', lw=0.6, ls=':')
        a.axhline(6.5, color='C3', lw=0.6, ls=':')
        a.set_title('%s (%s)' % (title, R[n]['verdict']))
        a.set_xlabel('ms after plug-in')
        a.set_ylabel('V')
        a.set_xscale('symlog', linthresh=0.01)
        a.set_xlim(-0.003, 12)
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'hotplug.png'))


if __name__ == '__main__':
    main()
