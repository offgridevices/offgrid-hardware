# -*- coding: utf-8 -*-
"""Study 5: charging from a 6 V 1 W panel through the linear charger's
VINDPM (P5), and the charge path's control (P7 / X5).

The panel (12 cells, 7.2 V open circuit, 0.185 A short circuit at full
sun, Vmp ~6 V / Imp ~0.167 A, -2.2 mV/C per cell) feeds the solar input
through its 1 m lead, the RB060MM, TVS2200 and TPS259470A (UV 3.55 V, OV
9.96 V) into VIN_CHG.  The BQ25185 holds VIN at VINDPM = VBAT + 330 mV
(VBAT > 3.5 V) or 3.6 V, so the panel is pulled down to about
VINDPM + 0.3 V (diode) instead of its maximum-power point: the study
reports how much of the panel's MPP power reaches the cell.  Cell at 3.0 V
(precharge and fast-charge sides of VLOWV 2.9-3.1 V) and 4.1 V, 100 mOhm;
sun 100 / 50 / 20 %; panel at 25 C and 60 C (the sealed box).  System load
on 3V3 13 mA (listening).  Run 40 ms, averaged over the last 10 ms.

Also the charge path with the charger told NOT to charge (/CE high or the
NTC out of window, P7): with the LM66100 as drawn (CE = GND) VSYS is wired
to the cell, so the cell keeps charging from SYS; with CE = VSYS it does not.
Same with USB (5 V, 1 m cable) at a 3.7 V cell, charging enabled: the
as-drawn path charges above the 500 mA ISET.

Pass criteria, fixed before running:
  P5  the cell charges from the 6 V panel at both cell voltages, and the
      panel is never pulled into the eFuse's UVLO (input stays on);
      harvest = cell charge power / panel MPP power is reported (no limit:
      a linear charger with fixed VINDPM, by design)
  P7  with charging disabled the cell current is <= 1 mA into the cell
  X5  with USB the charge current stays at ISET (497 mA +-10 %)

Outputs: results.txt, stress.json, solar.png.   Run: python3 run.py
"""
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import board as B
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('solar')
TSTOP = 40e-3
PANEL = dict(voc=7.2, isc=0.185, ncell=12)
LMN = {'gnd': 'LM66100 CE=GND (drawn)', 'vout': 'LM66100 CE=VSYS', 'diode': 'Schottky instead'}


def panel_iv(v, isc, temp):
    """The same single-diode equation as powerlib.panel (series R ignored)."""
    vt = 8.617e-5 * (273.15 + temp)
    nvt = 1.3 * vt * PANEL['ncell']
    voc = PANEL['voc'] - 0.0022 * PANEL['ncell'] * (temp - 25)
    i0 = PANEL['isc'] / (math.exp(voc / nvt) - 1)
    return isc - i0 * (np.exp(v / nvt) - 1) - v / (300.0 * PANEL['ncell'])


def mpp(isc, temp):
    v = np.linspace(0, 8, 4000)
    p = v * panel_iv(v, isc, temp)
    k = int(np.argmax(p))
    return v[k], p[k]


TEMPS = [-40, -20, 0, 25, 60, 85]


def charge_ok(ta):
    """Charging is allowed only inside the firmware window 0-45 C (/CE), itself inside the NTC's 0-60 C
    (TS); the cell is at ambient.  At 0 C and below the TS cold limit stops it as well."""
    return 0 < ta < 45


def cfg(ocv, sun=1.0, temp=25.0, lm='gnd', ce=1, usb=None, solar=True, lowv=None, ta=25.0):
    # lowv = 1: the cell is below the part's VLOWV (2.9-3.1 V), so it gets the 20 % precharge current
    # temp = panel cell temperature, ta = ambient (board, cell)
    c = B.default_cfg()
    c['temp'] = ta
    c['cell'].update(ocv=ocv, rint=0.10)
    c['lm'] = lm
    c['usb'] = usb
    if solar:
        c['solar'] = dict(voc=PANEL['voc'], isc=PANEL['isc'] * sun, ncell=PANEL['ncell'], temp_c=temp)
    c['chg'] = dict(ce=ce, ts=1 if 0 < ta < 60 else 0)
    if lowv:
        c['chg']['ichg'] = c['chg']['iprech'] = 0.0994
    c['pa']['on'] = False
    c['tstop'] = TSTOP
    c['tmax'] = 5e-6
    c['save'] = ['i(vpvam)', 'v(pv_p)', 'v(fs_ena)'] if solar else []
    return c


def run(args):
    name, c, meta = args
    S.ngspice(B.build(c, name + '.raw'), OUT, name)
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    os.remove(os.path.join(OUT, name + '.raw'))
    t = r['time']
    m = t > TSTOP - 10e-3
    a = lambda k: float(np.mean(r[k][m]))
    res = dict(name=name, ichg_cell=-a('i(vbt_am)'), vin=a('v(vin_chg)'), vsys=a('v(vsys)'), bat=a('v(bat_p)'),
               ich=a('v(ch_ichg)'), iin=a('v(ch_iin)'), ilm=a('v(pblm_i)'), vdpm=0.0)
    res.update(meta)
    if c['solar']:
        res['ipv'] = a('i(vpvam)')
        res['vpv'] = a('v(pv_p)')
        res['ppv'] = res['ipv'] * res['vpv']
        res['ena_min'] = float(r['v(fs_ena)'][t > 10e-3].min())
        vmp, pmp = mpp(PANEL['isc'] * meta['sun'], meta['temp'])
        res['pmpp'] = pmp
        res['harvest'] = res['ichg_cell'] * res['bat'] / pmp if pmp > 0 else 0
    keep = np.unique(np.searchsorted(t, np.linspace(0, TSTOP, 1500))).clip(0, len(t) - 1)
    np.savez(os.path.join(OUT, name + '.npz'), t=t[keep], vin=r['v(vin_chg)'][keep], icell=-r['i(vbt_am)'][keep],
             vsys=r['v(vsys)'][keep])
    return res


def main():
    jobs = []
    for ta in TEMPS:
        ok = charge_ok(ta)
        for ocv, lowv, lab in ((3.0, 0, '3.0 V'), (4.1, 0, '4.1 V')):
            for sun in (1.0, 0.2):
                for lm in ('gnd', 'diode'):
                    tp = ta + 25 * sun               # panel cells above ambient in sun (NOCT-like)
                    n = 'pv_%d_%g_%g_%s' % (ta, ocv, sun * 100, lm)
                    jobs.append((n, cfg(ocv, sun, tp, lm, lowv=lowv, ce=1 if ok else 0, ta=ta),
                                 dict(cell=lab, sun=sun, temp=tp, ta=ta, lm=lm, kind='solar', ce=1 if ok else 0)))
        for lm in ('gnd', 'vout', 'diode'):
            jobs.append(('usb_%d_%s' % (ta, lm), cfg(3.7, lm=lm, ce=1 if ok else 0, usb=5.0, solar=False, ta=ta),
                         dict(cell='3.7 V', sun=0, temp=ta, ta=ta, lm=lm, kind='USB', ce=1 if ok else 0)))
    for lm in ('gnd', 'vout', 'diode'):
        jobs.append(('pvce_%s' % lm, cfg(3.7, 1.0, 50.0, lm, ce=0),
                     dict(cell='3.7 V', sun=1.0, temp=50.0, ta=25.0, lm=lm, kind='solar, /CE high at 25 C', ce=0)))
        jobs.append(('usbce_%s' % lm, cfg(3.7, lm=lm, ce=0, usb=5.0, solar=False),
                     dict(cell='3.7 V', sun=0, temp=25.0, ta=25.0, lm=lm, kind='USB, /CE high at 25 C', ce=0)))
        jobs.append(('usb41_%s' % lm, cfg(4.15, lm=lm, ce=1, usb=5.0, solar=False),
                     dict(cell='4.15 V', sun=0, temp=25.0, ta=25.0, lm=lm, kind='USB, 4.15 V cell, 25 C', ce=1)))
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(run, jobs))
    R = dict((r['name'], r) for r in res)

    L = ['Study 5: 6 V 1 W panel through VINDPM (P5); charge-path control (P7, X5); ambient -40 .. 85 C.',
         'Panel 12 cells, 7.2 V Voc, 0.185 A Isc at full sun, cells at ambient + 25 C x sun; cell 100 mOhm at 25 C;',
         '3V3 load 13 mA.  Last 10 ms of 40 ms averaged.  Charging is allowed only between 0 and 45 C (firmware /CE',
         'inside the NTC window): at 25 C the criterion is P5 (the cell charges); at -40 / -20 / 0 / 60 / 85 C it is',
         'P7 (<= 1 mA into the cell).  The BQ25185 thermal regulation (TREG 100 C, 68.3 C/W) is in the model.', '']
    rows = []
    for r in res:
        if r['kind'] != 'solar':
            continue
        if r['ce']:
            ok = r['ichg_cell'] > 0.005 and r['ena_min'] > 0.5
        else:
            ok = r['ichg_cell'] <= 1e-3
        r['verdict'] = 'PASS' if ok else 'FAIL'
        rows.append([r['cell'], '%d %%' % (r['sun'] * 100), '%d C' % r['ta'], 'P5' if r['ce'] else 'P7', LMN[r['lm']],
                     r['vpv'], r['ipv'] * 1e3, r['ppv'] * 1e3, r['pmpp'] * 1e3, r['vin'], r['vsys'], r['ichg_cell'] * 1e3,
                     r['harvest'] * 100, r['verdict']])
    L.append(S.table(rows, ['cell', 'sun', 'ambient', 'rule', 'BAT_P-VSYS path', 'Vpanel', 'Ipanel mA', 'Ppanel mW', 'MPP mW', 'VIN_CHG',
                            'VSYS', 'into cell mA', 'harvest %', 'verdict']))
    L.append('  harvest = cell charge power / panel MPP power.  The 3V3 load (13 mA) comes out of the panel first.')
    L.append('')
    rows = []
    for r in res:
        if r['kind'] == 'solar':
            continue
        if r['ce'] == 0:
            ok = r['ichg_cell'] <= 1e-3
            crit = 'P7: <= 1 mA into the cell'
        else:
            ok = r['ichg_cell'] <= 0.547 and (r['ichg_cell'] >= 0.447 or r['bat'] > 4.1 or r['ich'] > 0)
            crit = 'X5: <= ISET 497 mA +10 %, via the charger'
        r['verdict'] = 'PASS' if ok else 'FAIL'
        rows.append([r['kind'], '%d C' % r['ta'], r['cell'], LMN[r['lm']], r['vsys'], r['bat'],
                     r['ich'] * 1e3, r['ilm'] * 1e3, r['ichg_cell'] * 1e3, crit, r['verdict']])
    L.append(S.table(rows, ['case', 'ambient', 'cell', 'BAT_P-VSYS path', 'VSYS', 'BAT_P', 'charger BAT mA', 'LM66100 mA (BAT->SYS)',
                            'into cell mA', 'criterion', 'verdict']))
    L.append('  As drawn the LM66100 (CE = GND) is a closed switch between BAT_P and VSYS: SYS (regulated to 4.5 V, or')
    L.append('  pulled down by the cell) charges the cell directly, outside the charger\'s ISET, CV, /CE and TS control;')
    L.append('  only the BQ29700 (OVP 4.275 V after 1.25 s, OCC 4 A) still limits it.  With CE = VSYS the LM66100 only')
    L.append('  turns off once VSYS is 35 mV (0-80 mV) above the cell, i.e. above ~0.44 A reverse; a weak source (the')
    L.append('  panel) never gets there, so the cell still charges through it.  A Schottky in its place always blocks.')
    L.append('')
    L.append('Verdict per ambient (solar rows: worst of the 3.0 / 4.1 V cell, 100 / 20 % sun; USB row: 3.7 V cell):')
    vrows = []
    for lm in ('gnd', 'vout', 'diode'):
        row = [LMN[lm]]
        for ta in TEMPS:
            vs = [r['verdict'] for r in res if r.get('ta') == ta and r['lm'] == lm and r['name'].startswith('pv_%d_' % ta)]
            vu = R['usb_%d_%s' % (ta, lm)]['verdict']
            row.append('solar %s / USB %s' % ('FAIL' if 'FAIL' in vs else ('PASS' if vs else '-'), vu))
        vrows.append(row)
    L.append(S.table(vrows, ['BAT_P-VSYS path'] + ['%d C' % t for t in TEMPS]))
    S.write_results(HERE, L)

    st = []
    w = max([r for r in res if r['kind'] == 'solar'], key=lambda x: (x['vin'] - x['bat']) * x['iin'])
    pch = (w['vin'] - w['bat']) * w['iin']
    st.append(S.stress('BQ25185', 'U (charger)', 'dissipation, 6 V panel', pch, 'W', 1.1, 'derate',
                       w['name'] + ' (vs (125-60) C / 68.3 C/W = 0.95 W at 60 C ambient; 1.1 W shown as TJ 135 C)'))
    pusb = max((R['usb_25_diode']['vin'] - R['usb_25_diode']['bat']) * R['usb_25_diode']['iin'], 0)
    st.append(S.stress('BQ25185', 'U (charger)', 'dissipation, USB charging 3.7 V cell (CE=VSYS)', pusb, 'W', 0.95, 'derate',
                       '(125 - 60 C) / 68.3 C/W JEDEC'))
    st.append(S.stress('BQ25185', 'U (charger)', 'IN current (ILIM 1.05 A, max 1.1 A)', 1.1, 'A', 1.1, 'absmax',
                       'input current limit sits at the 1.1 A abs-max DC input current'))
    sol12 = (9.96 * 1.012 - 3.0) * 0.33
    st.append(S.stress('BQ25185', 'U (charger)', 'dissipation, 12 V panel at ~10 V (just under solar OV), 3.0 V cell',
                       sol12, 'W', 0.95, 'derate', 'Isc 0.33 A; thermal regulation (TREG 100 C) would cut it back'))
    S.write_stress(HERE, st)

    plt = S.style()
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    a = ax[0]
    v = np.linspace(0, 7.6, 400)
    for temp, ls in ((25.0, '-'), (60.0, '--')):
        for sun, c in ((1.0, 'C0'), (0.5, 'C1'), (0.2, 'C2')):
            i = np.clip(panel_iv(v, PANEL['isc'] * sun, temp), 0, None)
            a.plot(v, v * i * 1e3, c + ls, lw=1, label='%d %% sun, %d C' % (sun * 100, temp))
    for r in res:
        if r['kind'] == 'solar' and r['lm'] == 'diode' and r['ta'] == 25:
            a.plot(r['vpv'], r['ppv'] * 1e3, 'ko' if r['cell'] == '4.1 V' else 'k^', ms=4)
    a.set_xlabel('panel V')
    a.set_ylabel('panel power mW')
    a.set_title('panel P-V and the operating points (o: 4.1 V cell, ^: 3.0 V)')
    a.legend(fontsize=6)
    a = ax[1]
    for n, lab in (('usbce_gnd', 'USB, /CE high, as drawn'), ('usbce_diode', 'USB, /CE high, Schottky'),
                   ('usb_25_gnd', 'USB charging 25 C, as drawn'), ('usb_25_diode', 'USB charging 25 C, Schottky'),
                   ('usb_85_gnd', 'USB, 85 C (NTC hot), as drawn'), ('pvce_gnd', 'panel, /CE high, as drawn')):
        d = np.load(os.path.join(OUT, n + '.npz'))
        a.plot(d['t'] * 1e3, d['icell'] * 1e3, label=lab)
    a.set_xlabel('ms')
    a.set_ylabel('current into the cell mA')
    a.set_title('charge-path control')
    a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'solar.png'))


if __name__ == '__main__':
    main()
