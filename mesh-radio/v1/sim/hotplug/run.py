# -*- coding: utf-8 -*-
"""Study 1: hot plug and over-voltage on the three inputs (X3, with P4-P6).

The circuit is src/circuit.py as changed on 19 Oct.  Each input is plugged
in through its cable / lead at t = 20 us (100 ns contact edge) and run for
24 ms, long enough for the eFuse's 2 V/ms soft start (USB) and the
MAX17608's 16 ms power-up debounce + 1 ms turn-on (solar, drone) to finish:
  USB-C: 1 m cable (1 uH, 0.2 ohm) -> TVS2200 + 1 uF 50 V + snubber (4.7 uF
         50 V + 1 ohm) -> TPS259470A (UV 4.33 V from 20 k / 7.68 k with a
         5.6 V zener, OV 5.38 V, 1.51 A) -> USB_5V (nRF52840 VBUS, 4.7 uF,
         2.2 k) -> RB060MM -> VIN_CHG (1 uF + 10 uF) -> BQ25185 (cell 3.7 V)
  solar: panel (single-diode model) + 1 m lead (1 uH, 0.1 ohm) -> SMF33CA +
         1 uF 50 V -> MAX17608 (UVLO internal 4.0 V, OV 9.93 V, 0.71 A) -> VIN_CHG
  drone: 30 cm JST-GH cable (0.3 uH, 0.05 ohm) -> the same as solar
Cases: USB 5 / 5.5 / 20 V hot plug, USB 5 -> 20 V step while running,
12 V panel (21 V open circuit at 25 C; Voc rises 2.2 mV/C per cell, the
panel at ambient), 6 V 1 W panel, drone 5 V and 20 V, a 12 V panel
plugged in backwards (-26.1 V source, the cold Voc), drone -20 V.  The
TVS2200 uses its maximum breakdown (27.6 V) for pin-voltage checks; the
SMF33CA its minimum (36.7 V) for the conduction checks, its maximum for
the pin checks.

Pass criteria (X3), fixed before running:
  USB eFuse (TPS259470A) IN <= 28 V abs max (> 27 V MARGINAL); IN slew
  <= 100 V/us rising, <= 10 V/us falling; EN/UVLO and OVLO pins <= 6.5 V
  MAX17608 IN <= 60 V (recommended; 65 V abs max) and >= -60 V; IN slew
  <= 100 V/us; the processor's <name>_OK ADC pin <= 3.6 V (VDD + 0.3)
  USB_5V (nRF52840 VBUS) <= 5.8 V abs max (5.5 V recommended)
  VIN_CHG (BQ25185 IN) <= 25 V abs max, and the charger never sees more
  than the eFuse's OV cut-off
  20 V on any input: that eFuse never turns on (OV cut-off works)
  TVS2200: no DC conduction above its 18 mA DC breakdown rating; SMF33CA:
  no DC conduction (> 1 mA)
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
TSTOP = 24e-3

# eFuse dividers (src/circuit.py inputs())
USB = dict(rt_uv=20e3, rb_uv=7.68e3, rt_ov=1e6, rb_ov=287e3, rilm=2210)
HV = dict(rt_ov=1.5e6, rb_ov=267e3, rset=2100.0)       # MAX17608 on solar and drone


def netlist(case, raw):
    kind = case['kind']
    P.set_temp(case.get('ta', 25.0))
    s = ['* hot plug: %s, %g C' % (case['name'], P.TEMP), P.models()]
    hv = kind != 'usb'
    if kind in ('usb', 'drone', 'solsrc'):
        v1 = case['v']
        if case.get('step'):
            t2, v2 = case['step']
            s.append('Vsrc src 0 pwl(0 0 %g 0 %g %g %g %g %g %g)' % (T_PLUG, T_PLUG + 1e-7, v1, t2, v1, t2 + 1e-6, v2))
        else:
            s.append('Vsrc src 0 pwl(0 0 %g 0 %g %g)' % (T_PLUG, T_PLUG + 1e-7, v1))
        cab = {'usb': (0.2, 1e-6), 'drone': (0.05, 0.3e-6), 'solsrc': (0.1, 1e-6)}[kind]
        s.append(P.rl('cab', 'src', 'conn', *cab))
    else:
        s.append(P.panel('PV', 'pv', '0', case['voc'], case['isc'], case['ncell'], case.get('temp', 25.0)))
        s.append('Vctl ctl 0 pwl(0 0 %g 0 %g 1)' % (T_PLUG, T_PLUG + 1e-7))
        s.append('Splug pv pvs ctl 0 SWI')
        s.append(P.rl('cab', 'pvs', 'conn', 0.1, 1e-6))
    vmax = max(abs(case.get('v', 0.0)), abs(case.get('step', (0, 0))[1]), case.get('voc', 0.0) * 1.25)
    hi = vmax > 10
    s.append(P.rl('tr', 'conn', 'RAW', 0.005, 5e-9))
    s.append(P.cap('craw', 'RAW', '0', 0.55e-6 if hi else 0.9e-6))          # 1 uF 50 V X5R 0603 at 20 / 5 V
    if not hv:
        s.append(P.tvs2200('tvs', 'RAW', case.get('tvs', 'MAX')))
        s.append(P.cap('csnb', 'RAW', 'snb', 2.8e-6 if hi else 4.4e-6) + 'Rsnb snb 0 1\n')   # 4.7 uF 50 V X7R + 1 R
        s.append(P.efuse('FU', 'RAW', 'EOUT', zleak=case.get('zleak', 0.0), cov=100e-12, **USB))
        # USB_5V: 2.2 k bleed; 22 R into the nRF52840 VBUS and 2 x 4.7 uF (since 19 Oct)
        s.append('R5vb EOUT 0 2.2k\nC5vs EOUT 0 1n\nR22v EOUT NVB 22\n' + P.cap('c5v', 'NVB', '0', 5.0e-6))
        s.append(P.schottky('dusb', 'EOUT', 'VIN_CHG'))
        en = 'v(fu_en)'
    else:
        s.append(P.smf33ca('tvs', 'RAW', case.get('tvs', 'MAX')))
        s.append(P.max17608('FU', 'RAW', 'VIN_CHG', ok='OKN', **HV))
        s.append('Rout EOUT 0 1Meg\nVeo EOUT VIN_CHG 0\n')
        en = 'v(okn)'
    s.append(P.cap('cvc1', 'VIN_CHG', '0', 0.9e-6) + 'Rvcl VIN_CHG 0 1Meg\n')     # 1 uF only since 19 Oct
    # charger with a 3.7 V cell behind it and a 50 mA system load
    s.append(P.bq25185('CH', 'VIN_CHG', 'VSYS', 'BAT'))
    s.append('Vcell cellp 0 3.7\nRcell cellp BAT 0.1\n' + P.cap('csys', 'VSYS', '0', 8e-6) + 'Rsys VSYS 0 80\n')
    s.append(P.tps22950('LM', 'BAT', 'BYP') + P.schottky('LMd', 'BYP', 'VSYS') + 'Rbyp BYP 0 10Meg\n')
    vec = ['v(raw)', 'v(eout)', 'v(vin_chg)', en, 'v(fu_ov)', 'v(fu_i)', 'v(fu_ena)', 'v(ch_iin)', 'v(conn)', 'v(vsys)']
    if not hv:
        vec.append('v(nvb)')
    s.append('.nodeset v(VSYS)=3.6 v(BAT)=3.7')
    s.append('.option method=gear reltol=1e-3 abstol=1e-9 vntol=1e-5 itl4=200')
    s.append('.tran 1n %g 0 %g' % (TSTOP, case.get('tmax', 0.2e-6)))
    s.append('.control\nset filetype=binary\nrun\nwrite %s %s i(vtvsam)\n.endc\n.end' % (raw, ' '.join(vec)))
    return '\n'.join(s) + '\n', en


def run(case):
    name = case['name']
    net, en = netlist(case, name + '.raw')
    # retry with the other solver option sets (simlib.OPTS) if a step fails
    opt0 = '.option method=gear reltol=1e-3 abstol=1e-9 vntol=1e-5 itl4=200'
    for o in [opt0] + S.OPTS[1:]:
        try:
            S.ngspice(net.replace(opt0, o), OUT, name)
            break
        except S.TimestepError:
            if o == S.OPTS[-1]:
                raise
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    t = r['time']
    v = r['v(raw)']
    # slew over 50 ns windows (a single solver step across the TVS knee is not a slew rate)
    tg = np.arange(T_PLUG, min(t[-1], T_PLUG + 300e-6), 10e-9)
    vg = np.interp(tg, t, v)
    dv = (vg[5:] - vg[:-5]) / 50e-9
    if 'step' in case:
        tg2 = np.arange(case['step'][0], case['step'][0] + 300e-6, 10e-9)
        vg2 = np.interp(tg2, t, v)
        dv = np.concatenate([dv, (vg2[5:] - vg2[:-5]) / 50e-9])
    m = np.ones(len(dv), bool)
    itvs = r['i(vtvsam)']
    late = t > TSTOP - 2e-3
    res = dict(name=name, base=case['base'], ta=case['ta'], label=case['label'], raw_max=v.max(), dvr=dv[m].max() / 1e6, dvf=-dv[m].min() / 1e6,
               en_max=r[en].max(), ov_max=r['v(fu_ov)'].max(), out_max=r['v(eout)'].max(),
               vbus_max=r['v(nvb)'].max() if 'v(nvb)' in r else 0.0,
               raw_min=v.min(), vin_min=r['v(vin_chg)'].min(),
               vin_max=r['v(vin_chg)'].max(), out_end=r['v(eout)'][-1], vin_end=r['v(vin_chg)'][-1],
               ena_max=r['v(fu_ena)'].max(), ena_end=r['v(fu_ena)'][-1], i_max=r['v(fu_i)'].max(), iin_end=r['v(ch_iin)'][-1],
               tvs_ipk=np.abs(itvs).max(), tvs_idc=np.abs(itvs[late]).mean(), raw_end=v[-1],
               tvs_e=np.trapezoid(np.clip(itvs, 0, None) * v, t), kind=case['kind'])
    keep = np.unique(np.concatenate([np.where(t < 200e-6)[0][::2], np.searchsorted(t, np.linspace(0, TSTOP, 3000))]))
    keep = keep[keep < len(t)]
    np.savez(os.path.join(OUT, name + '.npz'), **{k.replace('(', '_').replace(')', ''): a[keep] for k, a in r.items()})
    os.remove(os.path.join(OUT, name + '.raw'))
    return res


def voc_at(voc25, ncell, temp):
    return voc25 - 0.0022 * ncell * (temp - 25)


TEMPS = [-40, -20, 0, 25, 60, 85]
BASE = [
    dict(base='usb5', label='USB 5 V hot plug', kind='usb', v=5.0),
    dict(base='usb5p5', label='USB 5.5 V (vSafe5V max) hot plug', kind='usb', v=5.5),
    dict(base='usb20', label='USB 20 V hot plug (fault)', kind='usb', v=20.0),
    dict(base='usb5to20', label='USB 5 V -> 20 V step, 1 us', kind='usb', v=5.0, step=(6e-3, 20.0)),
    dict(base='sol12', label='12 V panel (21 V Voc at 25 C), TVS min', kind='solar', voc=21.0, isc=0.33, ncell=36,
         tvs='MIN'),
    dict(base='sol6', label='6 V 1 W panel (7.2 V Voc at 25 C)', kind='solar', voc=7.2, isc=0.185, ncell=12),
    dict(base='drn5', label='drone 5 V hot plug', kind='drone', v=5.0),
    dict(base='drn20', label='drone 20 V hot plug (fault)', kind='drone', v=20.0),
    dict(base='solrev', label='12 V panel reversed (-26.1 V source)', kind='solsrc', v=-26.1, tvs='MIN'),
    dict(base='drnrev', label='drone -20 V (reversed) hot plug', kind='drone', v=-20.0),
]


def leak_op(ta, vin, rbleed=2.2e3, ismul=1.0):
    """USB unplugged, VIN_CHG held up by solar / drone: the USB OR-ing RB060MM is reverse biased and its
    leakage flows into USB_5V (the nRF52840's VBUS, 2.2 k bleed since 19 Oct, ~10 uA of nRF input).  ismul
    scales the diode's leakage (5 = the datasheet maximum).  DC operating point."""
    P.set_temp(ta)
    net = '\n'.join(['* RB060MM leakage into USB_5V, %g C' % ta, P.models(), 'Vin VIN_CHG 0 %g' % vin,
                      'D1 USB_5V VIN_CHG DRB060 area=%g' % ismul, 'Rb USB_5V 0 %g' % rbleed, 'Rnrf USB_5V 0 500k',
                      '.control', 'op', 'print v(usb_5v)', '.endc', '.end'])
    out = S.ngspice(net, OUT, 'leak_%g_%g_%g' % (ta, vin, ismul))
    import re
    m = re.search(r'v\(usb_5v\) = ([0-9.eE+-]+)', out)
    return float(m.group(1))


def main():
    cases = []
    for ta in TEMPS:
        for b in BASE:
            c = dict(b)
            c['name'] = '%s_%d' % (b['base'], ta)
            c['ta'] = float(ta)
            c['temp'] = float(ta)        # panel cells at ambient (the cold-morning worst case)
            cases.append(c)
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(run, cases))
    R = dict((r['name'], r) for r in res)

    L = ['Study 1: hot plug and over-voltage (X3), circuit as changed on 19 Oct.  Limits: USB eFuse IN 28 V abs max,',
         'IN slew 100 V/us up / 10 V/us down, EN/UVLO and OVLO 6.5 V, nRF52840 VBUS 5.8 V (5.5 V recommended); MAX17608',
         'IN -60..60 V, slew 100 V/us, <name>_OK ADC pin 3.6 V; BQ25185 IN 25 V; 20 V never passes an input;',
         'TVS2200 DC breakdown current <= 18 mA, SMF33CA none.', '']
    rows = []
    for r in res:
        fails = []
        marg = []
        usb = r['kind'] == 'usb'
        if usb and r['raw_max'] > 28.0:
            fails.append('IN > 28 V')
        if not usb and (r['raw_max'] > 60.0 or r['raw_min'] < -60.0):
            fails.append('IN outside -60..60 V')
        if r['dvr'] > 100:
            fails.append('IN rise slew')
        if usb and r['dvf'] > 10:
            fails.append('IN fall slew %.0f V/us' % r['dvf'])
        if usb and max(r['en_max'], r['ov_max']) > 6.5:
            fails.append('EN/OV pin > 6.5 V')
        if not usb and r['en_max'] > 3.6:
            fails.append('OK ADC pin %.2f V > 3.6 V' % r['en_max'])
        if usb and r['vbus_max'] > 5.8:
            fails.append('VBUS > 5.8 V')
        if usb and r['out_max'] > 25.0:
            fails.append('USB_5V > 25 V (charger IN via the Schottky)')
        if r['vin_max'] > 25:
            fails.append('charger IN > 25 V')
        if r['vin_min'] < -0.3:
            fails.append('charger IN < -0.3 V')
        if r['tvs_idc'] > (0.018 if usb else 1e-3):
            fails.append('TVS DC %.0f mA' % (r['tvs_idc'] * 1e3))
        hi = r['base'] in ('usb20', 'drn20', 'sol12', 'solrev', 'drnrev')
        if hi and max(r['out_max'], r['vin_max']) > (1.0 if usb else 4.3):
            fails.append('the input passed the over-voltage')
        if r['base'] == 'usb5to20' and r['ena_end'] > 0.5:
            fails.append('OV did not cut off')
        if usb and r['raw_max'] > 27.0 and not fails:
            marg.append('IN within 1 V of 28 V')
        if usb and max(r['en_max'], r['ov_max']) > 0.95 * 6.5 and not fails:
            marg.append('EN/OV pin within 5 %% of 6.5 V')
        if usb and r['vbus_max'] > 5.5 and not fails:
            marg.append('VBUS above 5.5 V rec.')
        if r['base'] in ('usb5', 'usb5p5', 'drn5', 'sol6') and r['ena_end'] < 0.5:
            marg.append('input did not switch on')
        r['verdict'] = 'FAIL' if fails else ('MARGINAL' if marg else 'PASS')
        rows.append([r['label'], '%d C' % r['ta'], r['raw_max'], r['raw_min'], r['dvr'], r['dvf'], r['en_max'], r['ov_max'],
                     r['out_max'], r['vbus_max'], r['vin_max'], 'on' if r['ena_end'] > 0.5 else 'off', r['tvs_ipk'], r['tvs_idc'] * 1e3,
                     r['verdict'], ', '.join(fails + marg) or '-'])
    L.append(S.table(rows, ['case', 'ambient', 'IN max V', 'IN min V', 'dV/dt up V/us', 'dV/dt down V/us', 'EN / OK max',
                            'OVLO max', 'eFuse OUT max', 'nRF VBUS max', 'VIN_CHG max', 'eFuse', 'TVS pk A', 'TVS DC mA',
                            'verdict', 'notes']))
    L.append('  (USB: eFuse OUT = USB_5V, EN = the TPS259470A EN/UVLO pin.  Solar / drone: the MAX17608 output is VIN_CHG,')
    L.append('  "EN / OK" is the processor\'s SOLAR_OK / DRONE_OK ADC pin; the falling-slew limit is the TPS259470A\'s only.)')
    L.append('')
    L.append('Verdict per case and ambient:')
    L.append(S.table([[b['label']] + [R['%s_%d' % (b['base'], ta)]['verdict'] for ta in TEMPS] for b in BASE],
                     ['case'] + ['%d C' % ta for ta in TEMPS]))
    L.append('')
    # 12 V panel Voc vs temperature against the TVS breakdown
    L.append('12 V panel (36 cells, 21.0 V Voc at 25 C, -2.2 mV/C/cell) against the SMF33CA (VBR 36.7 V min, +0.1 %/C)')
    L.append('and the MAX17608 (60 V):')
    trows = []
    for tc in (25, 0, -10, -20, -30, -40):
        vo = voc_at(21.0, 36, tc)
        vbr = 36.7 * (1 + 1e-3 * (tc - 25))
        trows.append(['%d C' % tc, vo, vbr, 'conducts' if vo > vbr else 'no', '%.0f %%' % (100 * vo / 60.0)])
    L.append(S.table(trows, ['cell temp', 'Voc V', 'SMF33CA VBR min', 'TVS', 'of MAX17608 60 V']))
    L.append('')
    # zener leakage and UVLO / OV thresholds (USB only since 19 Oct)
    L.append('USB EN/UVLO threshold vs. the 5.6 V zener\'s leakage at the 1.2 V threshold, 20 k on top since 19 Oct')
    L.append('(UDZV5.6B: IR <= 1 uA at 2.5 V, 25 C; taken as <= 1 uA at 1.2 V too and doubling every 10 C, a generic')
    L.append('junction figure the datasheet does not give).  OV cut-off 5.22-5.57 V; above it USB never switches on.')
    zr = []
    base = 1.20 * (1 + USB['rt_uv'] / USB['rb_uv'])
    for ta in TEMPS:
        lm = 1e-6 * 2 ** ((ta - 25) / 10.0)
        u = base + lm * USB['rt_uv']
        zr.append(['%d C' % ta, base, lm * 1e6, u, 'PASS' if u < 4.75 else 'MARGINAL'])
    L.append(S.table(zr, ['ambient', 'UVLO rise V (no leak)', 'leak max uA', 'UVLO at max leak V', 'verdict']))
    L.append('  This is a bound, not a prediction: the 1 uA is a 2.5 V test limit and a zener this far below its knee')
    L.append('  leaks nA; at the bound USB could be refused at 85 C (UVLO above 4.75 V, or above OV) - MARGINAL, a bench')
    L.append('  check of the USB turn-on at 85 C.  With the old 4.7 V zener')
    L.append('  (2 uA at 1 V) and 1 M on top the same leakage put UVLO at 6.3 V at 25 C: above OV, USB never on.')
    L.append('  USB sources may legally sit at up to 5.25 V (USB 2.0) / 5.5 V (Type-C vSafe5V); the USB OV cut-off is')
    L.append('  5.22-5.57 V (comparator and 1 % resistor tolerance), set by the nRF52840 VBUS 5.5 V recommended maximum:')
    L.append('  a 5.25-5.5 V charger can be refused (MARGINAL by design).  Once tripped, OVLO only releases below')
    L.append('  1.09 V on the pin, i.e. %.2f V on VBUS.' % (1.09 * (1 + USB['rt_ov'] / USB['rb_ov'])))
    L.append('')
    L.append('RB060MM reverse leakage into USB_5V (nRF52840 VBUS, 2.2 k bleed since 19 Oct) with USB unplugged and VIN_CHG')
    L.append('held up by solar or drone power (10.4 V: the MAX17608 OV cut-off maximum; 7.2 V: a 6 V panel the charger')
    L.append('is not loading).  Leakage = the diode fit (IS 2.8 uA at 25 C, EG 0.69 eV, XTI 2), typical, and x5 (the')
    L.append('datasheet maximum, 50 uA at 30 V and 25 C, is ~5x the fit).  Limits: VBUS abs max 5.8 V; VBUS detect 3.4 V.')
    lr = []
    for ta in TEMPS:
        row = ['%d C' % ta]
        for vin, k in ((10.4, 1.0), (7.2, 1.0), (10.4, 5.0)):
            row.append(leak_op(ta, vin, ismul=k))
        v = max(row[1:])
        row.append('FAIL' if v > 5.8 else ('MARGINAL' if v > 3.4 else 'PASS'))
        lr.append(row)
    L.append(S.table(lr, ['ambient', 'USB_5V @ 10.4 V typ', '@ 7.2 V typ', '@ 10.4 V, leak x5', 'verdict']))
    L.append('  Above ~3.4 V the nRF52840 reports USB present (VBUS detect); above 5.8 V VBUS is over its absolute maximum.')
    L.append('')
    # zener-leak transient check (USB, 1 uA)
    S.write_results(HERE, L)

    st = []
    lab = lambda r: '%s, %d C' % (r['label'], r['ta'])
    ru = [r for r in res if r['kind'] == 'usb']
    rh = [r for r in res if r['kind'] != 'usb']
    w = max(ru, key=lambda x: x['raw_max'])
    st.append(S.stress('TPS259470A', 'U (USB eFuse IN)', 'peak input voltage', w['raw_max'], 'V', 28.0, 'absmax', lab(w)))
    st.append(S.stress('TPS259470A', 'U (USB eFuse IN)', 'steady input voltage (20 V fault)', 20.0, 'V', 23.0, 'rec',
                       '23 V recommended maximum'))
    w = max(ru, key=lambda x: x['en_max'])
    st.append(S.stress('TPS259470A', 'U (EN/UVLO pin)', 'peak voltage', w['en_max'], 'V', 6.5, 'absmax', lab(w)))
    w = max(ru, key=lambda x: x['ov_max'])
    st.append(S.stress('TPS259470A', 'U (OVLO pin)', 'peak voltage', w['ov_max'], 'V', 6.5, 'absmax', lab(w)))
    w = max(rh, key=lambda x: x['raw_max'])
    st.append(S.stress('MAX17608', 'U (solar / drone IN)', 'peak input voltage', w['raw_max'], 'V', 65.0, 'absmax', lab(w)))
    st.append(S.stress('MAX17608', 'U (solar / drone IN)', 'steady input voltage, 12 V panel at -40 C (Voc)',
                       voc_at(21.0, 36, -40), 'V', 60.0, 'derate', '60 V operating maximum'))
    w = min(rh, key=lambda x: x['raw_min'])
    st.append(S.stress('MAX17608', 'U (solar / drone IN)', 'reverse input voltage (plug-in ring)', -w['raw_min'], 'V', 70.0,
                       'absmax', lab(w) + ' (IN to GND -70 V abs max; blocks to -60 V)'))
    w = max(rh, key=lambda x: x['en_max'])
    st.append(S.stress('nRF52840', 'U (SOLAR_OK / DRONE_OK ADC pin)', 'peak voltage', w['en_max'], 'V', 3.6, 'absmax', lab(w)))
    st.append(S.stress('C1u50 0603 50 V', 'C (raw inputs)', 'steady voltage, 12 V panel at -40 C', voc_at(21.0, 36, -40), 'V',
                       50.0, 'derate', 'solar / drone input; USB input 20 V fault: 40 %'))
    st.append(S.stress('C4u7_50 1206 50 V', 'C (USB snubber)', 'voltage, 20 V fault', 20.0, 'V', 50.0, 'derate', ''))
    st.append(S.stress('TVS2200', 'D (USB clamp)', 'standoff, 20 V fault', 20.0, 'V', 22.0, 'rec', 'VRWM 22 V'))
    st.append(S.stress('SMF33CA', 'D (solar / drone clamp)', 'standoff, 12 V panel at -40 C (a wrong input, X3)',
                       voc_at(21.0, 36, -40), 'V', 33.0, 'rec', 'VRWM 33 V: no conduction below it'))
    w = max(ru, key=lambda x: x['vbus_max'])
    st.append(S.stress('nRF52840', 'U (VBUS)', 'peak voltage', w['vbus_max'], 'V', 5.8, 'absmax', lab(w)))
    w = max(ru, key=lambda x: x['out_max'])
    st.append(S.stress('RB060MM (USB into charger)', 'D / USB_5V', 'USB_5V peak (eFuse cut-off delay)', w['out_max'], 'V', 30.0,
                       'absmax', lab(w)))
    st.append(S.stress('nRF52840', 'U (VBUS)', 'steady voltage at OV max', 1.223 * (1 + 1.01e6 / (0.99 * 287e3)), 'V', 5.8,
                       'absmax', 'a source just under the USB OV cut-off (5.5 V recommended: the USB 5.5 V case, MARGINAL)'))
    w = max(res, key=lambda x: x['vin_max'])
    st.append(S.stress('BQ25185', 'U (IN)', 'peak voltage', w['vin_max'], 'V', 25.0, 'absmax', lab(w)))
    ovmax = 1.55 * (1 + 1.01 * 1.5e6 / (0.99 * 267e3))
    st.append(S.stress('BQ25185', 'U (IN)', 'steady voltage (MAX17608 OV cut-off max)', ovmax, 'V', 18.0, 'rec', 'VIN_OP 18 V'))
    st.append(S.stress('C10u25 0805 25 V', 'C (VIN_CHG)', 'steady voltage (MAX17608 OV max)', ovmax, 'V', 25.0, 'derate',
                       'solar / drone pass up to their OV cut-off'))
    st.append(S.stress('C4u7 0603 10 V', 'C (nRF VBUS)', 'voltage at OV max', 1.223 * (1 + 1.01e6 / (0.99 * 287e3)), 'V', 10.0,
                       'derate', ''))
    st.append(S.stress('R1R_0805 pulse-proof', 'R (USB snubber)', 'energy, 20 V plug-in (0.5 C V^2)',
                       0.5 * 2.8e-6 * 20.0 ** 2 * 1e3, 'mJ', 10.0, 'info', 'CRCW-HP 0805 single-pulse capability not checked'))
    w = max(ru, key=lambda x: x['en_max'])
    st.append(S.stress('UDZV5.6B', 'D (USB EN clamp)', 'current, 20 V fault', (20.0 - 5.6) / 20e3 * 1e3, 'mA', 35.7, 'derate',
                       '200 mW / 5.6 V'))
    S.write_stress(HERE, st)

    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(16, 8))
    panels = [('usb5_25', 'USB 5 V hot plug, 25 C'), ('usb20_85', 'USB 20 V hot plug, 85 C'),
              ('usb5to20_25', 'USB 5 -> 20 V while on, 25 C'), ('sol12_-40', '12 V panel, -40 C'),
              ('sol6_25', '6 V panel, 25 C'), ('solrev_-40', '12 V panel reversed, -40 C')]
    for a, (n, title) in zip(ax.flat, panels):
        d = np.load(os.path.join(OUT, n + '.npz'))
        tm = (d['time'] - T_PLUG) * 1e3
        a.plot(tm, d['v_raw'], label='eFuse IN')
        a.plot(tm, d['v_eout'], label='eFuse OUT')
        a.plot(tm, d['v_vin_chg'], label='VIN_CHG')
        if 'v_fu_en' in d:
            a.plot(tm, d['v_fu_en'], label='EN/UVLO')
        else:
            a.plot(tm, d['v_okn'], label='OK (ADC)')
        a.plot(tm, d['v_fu_ov'], label='OVLO')
        a.axhline(28, color='C3', lw=0.6, ls=':')
        a.axhline(6.5, color='C3', lw=0.6, ls=':')
        a.set_title('%s (%s)' % (title, R[n]['verdict']))
        a.set_xlabel('ms after plug-in')
        a.set_ylabel('V')
        a.set_xscale('symlog', linthresh=0.01)
        a.set_xlim(-0.003, 24)
        a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'hotplug.png'))


if __name__ == '__main__':
    main()
