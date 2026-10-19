# -*- coding: utf-8 -*-
"""Study 3: short circuits (X2) and the cell protector's trip timing (X5).

A short (10 mOhm + 5 nH, or through the expansion header: + 30 mOhm and
10 nH of trace) is applied at 5 ms and removed at 65 ms; the run ends at
110 ms.  The whole power path is in the netlist (sim/board.py), with a
fresh cell (4.2 V, 50 mOhm: the largest fault current) and a half-worn one
(3.7 V, 150 mOhm).  Shorted nets: 3V3 (at the buck), the expansion header's
3V3 pin, VSYS_SW (after the TPS22965), VPA (PA enabled, no RF), PA_IN
(the TPS2121 output), BAT_P (the battery terminals on the board side of
the reverse FET), and with USB present 3V3 and BAT_P.

The protector's trip timing is checked separately: a current step on
BAT_P (electronic load) at 2-20 A, BQ29700 thresholds at typ; min / max
bands from the datasheet tolerances (OCD 100 +-15 mV / 20 ms +-20 %, SCD
500 +-100 mV / 250 us +-50 %) over 22 mOhm +-1 % + RSS(on) 2.2-2.75 mOhm.

Pass criteria (X2 / X5), fixed before running:
  every pass element stays inside its pulse / continuous rating for the
  duration of the fault (LM66100 2.5 A <= 120 ms pulsed; TPS22965 8 A
  < 300 us, 6 A continuous; CSD25485F5 31 A <= 100 us, 3.2-5.3 A
  continuous; TPS2121 internally limited 4.5 A; TPS62840 1.4 A peak limit;
  TPS63810 internally limited)
  the fault current is limited, the faulted rail is cut within its
  protection's time, and the board runs again after the short is removed
  (3V3 back above 3.0 V) - or the reason it does not is stated
  OCD trips between 3.4 and 4.7 A, SCD at 16-24 A, both with the
  datasheet delays

Outputs: results.txt, stress.json, shorts.png.   Run: python3 run.py
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import board as B
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('shorts')
T_ON, T_OFF, TSTOP = 5e-3, 65e-3, 110e-3
OPTS = ['.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200',
        '.option method=trap reltol=3e-3 abstol=1e-8 vntol=1e-5 itl4=300',
        '.option method=gear reltol=5e-3 abstol=1e-7 vntol=1e-4 itl4=500 gmin=1e-10']


def short(node, r=0.010, l=5e-9):
    return ('* short %s -> GND from %g to %g s\n' % (node, T_ON, T_OFF) +
            'Vshc shc 0 pwl(0 0 %g 0 %g 1 %g 1 %g 0)\n' % (T_ON, T_ON + 1e-7, T_OFF, T_OFF + 1e-7) +
            'Ssh %s sh1 shc 0 SWI\nRsh sh1 sh2 %g\nLsh sh2 shx %g\nVsham shx 0 0\n' % (node, r, l))


TEMPS = [-40, -20, 0, 25, 60, 85]


def cfg(node, ocv=4.2, rint=0.05, usb=None, pa=False, r=0.010, l=5e-9, lm='gnd', temp=25.0):
    c = B.default_cfg()
    c['temp'] = temp
    # the run stops when the protector trips: what follows (release and hiccup with the board
    # load collapsing) is slow to simulate and is a bench item (see results.txt)
    c['stop_on'] = ['v(pbocd) > 0.5']
    c['cell'].update(ocv=ocv, rint=rint)
    c['usb'] = usb
    c['lm'] = lm
    c['pa'].update(vset=2.7, inom=1.0, t_rf=10.0, burst=0.0, on=pa)
    c['extra'] = short(node, r, l)
    c['tstop'] = TSTOP
    c['tmax'] = 5e-6
    c['save'] = ['i(vsham)', 'v(sr_ib)', 'v(batt_plus)', 'v(bat_p_c)']
    return c


def run(args):
    name, c = args
    stopped = None
    for o in OPTS:
        c['opt'] = o
        try:
            S.ngspice(B.build(c, name + '.raw'), OUT, name)
            stopped = None
            break
        except S.TimestepError as e:
            stopped = e.t
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    os.remove(os.path.join(OUT, name + '.raw'))
    t = r['time']
    on = (t > T_ON) & (t < T_OFF)
    after = t > TSTOP - 10e-3
    if not after.any():
        after = t >= t[-1]
    ish = r['i(vsham)']
    isw = (r['v(vsys)'] - r['v(vsys_sw)']) / 0.018
    icell = r['i(vbt_am)']
    ocd_t = t[np.argmax(r['v(pbocd)'] > 0.5)] - T_ON if r['v(pbocd)'].max() > 0.5 else None
    flow = on & (t > T_ON + 0.5e-3)
    if ocd_t is not None:
        flow &= t < T_ON + ocd_t - 50e-6
    if not flow.any():
        flow = on
    dt = np.diff(t, prepend=t[0])

    def dur(a, lim):   # total time above lim during the short
        m = on & (np.abs(a) > lim)
        return float(dt[m].sum())

    pfet = np.abs((r['v(batt_plus)'] - r['v(bat_p_c)']) * icell)

    res = dict(name=name, ish_pk=np.abs(ish[on]).max(), ish_avg=np.abs(ish[flow]).mean(),
               icell_pk=np.abs(icell[on]).max(), icell_avg=np.abs(icell[flow]).mean(),
               ilm_pk=np.abs(r['v(pblm_i)'][on]).max(), ilm_t25=dur(r['v(pblm_i)'], 2.5),
               isw_pk=np.abs(isw[on]).max(), isw_t8=dur(isw, 8.0), isw_t6=dur(isw, 6.0),
               ib_pk=r['v(sr_ib)'][on].max(), imux_pk=max(r['v(mx_i1)'][on].max(), r['v(mx_i2)'][on].max()),
               ibb_pk=r['v(bb_iin)'][on].max(), isup_pk=r['v(ch_isup)'][on].max(), iin_pk=r['v(ch_iin)'][on].max(),
               ocd=r['v(pbocd)'].max() > 0.5, ocd_t=ocd_t, scd=False,
               v3_end=r['v(3v3)'][after].mean(), vsys_end=r['v(vsys)'][after].mean(),
               bat_end=r['v(bat_p)'][after].mean(), vm_pk=r['v(prot_vm,cell_minus)'][on].max(),
               stopped=stopped, pfet_pk=float(pfet[on].max()), efet=float((pfet * dt)[on].sum()),
               pfet_avg=float(pfet[flow].mean()),
               ilm_avg=float(np.abs(r['v(pblm_i)'][flow]).mean()),
               isw_avg=float(np.abs(isw[flow]).mean()), temp=c['temp'])
    keep = np.unique(np.searchsorted(t, np.linspace(0, TSTOP, 4000))).clip(0, len(t) - 1)
    np.savez(os.path.join(OUT, name + '.npz'), t=t[keep], ish=ish[keep], icell=icell[keep], v3=r['v(3v3)'][keep],
             vsys=r['v(vsys)'][keep], bat=r['v(bat_p)'][keep], ilm=r['v(pblm_i)'][keep], isw=isw[keep])
    return res


def trip_cfg(iload):
    c = B.default_cfg()
    c['cell'].update(ocv=4.2, rint=0.02)
    c['pa']['on'] = False
    c['extra'] = 'Iel BAT_P 0 pwl(0 0 %g 0 %g %g)\n' % (2e-3, 2e-3 + 1e-6, iload)
    c['tstop'] = 40e-3
    c['tmax'] = 2e-6
    return c


def trip_run(iload):
    name = 'trip_%g' % iload
    c = trip_cfg(iload)
    c['opt'] = OPTS[0]
    try:
        S.ngspice(B.build(c, name + '.raw'), OUT, name)
    except S.TimestepError:
        pass
    r = S.rawread(os.path.join(OUT, name + '.raw'))
    os.remove(os.path.join(OUT, name + '.raw'))
    t = r['time']
    tr = t[np.argmax(r['v(pbocd)'] > 0.5)] - 2e-3 if r['v(pbocd)'].max() > 0.5 else None
    return iload, tr, float(r['v(prot_vm,cell_minus)'][np.searchsorted(t, 3e-3)])


def main():
    base = [
        ('3v3_fresh', ('3V3',), {}),
        ('hdr3v3_fresh', ('3V3',), dict(r=0.040, l=15e-9)),
        ('vsyssw_fresh', ('VSYS_SW',), {}),
        ('vsyssw_mid', ('VSYS_SW',), dict(ocv=3.7, rint=0.15)),
        ('vpa_fresh', ('VPA',), dict(pa=True)),
        ('pain_fresh', ('PA_IN',), dict(pa=True)),
        ('batp_fresh', ('BAT_P',), {}),
        ('batp_mid', ('BAT_P',), dict(ocv=3.7, rint=0.15)),
        ('batp_worn', ('BAT_P',), dict(ocv=3.7, rint=0.30)),
        ('3v3_usb', ('3V3',), dict(usb=5.0)),
        ('batp_usb_drawn', ('BAT_P',), dict(usb=5.0)),
        ('batp_usb_fix', ('BAT_P',), dict(usb=5.0, lm='diode')),
    ]
    cases = [('%s_%d' % (n, ta), cfg(*a, temp=float(ta), **kw)) for ta in TEMPS for n, a, kw in base]
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(run, cases))
        trips = list(ex.map(trip_run, [2.0, 3.0, 3.5, 4.0, 4.5, 5.0, 8.0, 12.0, 16.0, 19.0, 21.0, 24.0]))

    L = ['Study 3: shorts (X2) and cell-protector trip timing (X5).  Short 10 mOhm + 5 nH (header: 40 mOhm + 15 nH)',
         'from 5 ms to 65 ms, run to 110 ms.  Fresh cell = 4.2 V / 50 mOhm, mid = 3.7 V / 150 mOhm, worn = 3.7 V / 300 mOhm.',
         '']
    rows = []
    for r in res:
        f = []
        if r['ilm_t25'] > 10e-6:
            f.append('LM66100 %.1f A (> 2.5 A) for %.1f ms' % (r['ilm_avg'], r['ilm_t25'] * 1e3))
        if r['isw_avg'] > 6.0 and r['isw_t6'] > 300e-6:
            f.append('TPS22965 %.1f A for %.1f ms' % (r['isw_avg'], r['isw_t6'] * 1e3))
        if r['efet'] > 0.01 and r['pfet_avg'] > 1.4:
            f.append('rev FET in linear mode: %.1f W, %.0f mJ' % (r['pfet_avg'], r['efet'] * 1e3))
        if r['stopped'] is not None:
            f.append('solver stopped %.1f ms' % (r['stopped'] * 1e3))
        recov = r['v3_end'] > 3.0 and not r['ocd']
        r['verdict'] = 'FAIL' if f else ('PASS' if recov else 'MARGINAL')
        if r['ocd']:
            f.append('cell cut off by the protector; restart after the short: bench (release rule below)')
        elif not recov:
            f.append('no restart on its own (3V3 %.2f V)' % r['v3_end'])
        rows.append([r['name'], r['ish_pk'], r['ish_avg'], r['icell_pk'], r['ilm_pk'], r['isw_pk'], r['pfet_avg'],
                     r['efet'] * 1e3, r['ib_pk'], r['imux_pk'],
                     r['ibb_pk'], r['isup_pk'], 'OCD/SCD %.2f ms' % (r['ocd_t'] * 1e3) if r['ocd'] else 'no trip',
                     r['v3_end'], r['verdict'], ', '.join(f) or '-'])
    L.append(S.table(rows, ['case_T', 'Ishort pk', 'Ishort avg', 'Icell pk', 'LM66100 pk', 'TPS22965 pk', 'rev FET W avg',
                            'rev FET mJ', 'buck out pk',
                            'mux pk', 'BB in pk', 'BATFET pk', 'protector', '3V3 at end', 'verdict', 'notes']))
    L.append('  Peaks under 10 us are the board capacitors discharging into the short (ESR-limited) and are not failed.')
    L.append('  "avg" columns are over the time the short current flows (until the protector trips).')
    L.append('')
    V_ = dict((r['name'], r['verdict']) for r in res)
    L.append('Verdict per case and ambient:')
    L.append(S.table([[n] + [V_['%s_%d' % (n, ta)] for ta in TEMPS] for n, _, _ in base], ['case'] + ['%d C' % t for t in TEMPS]))
    L.append('')
    L.append('OCD / SCD trip currents over temperature (thresholds 85-115 mV / 400-600 mV hold over -40..85 C;')
    L.append('RSS(on) 2.2-2.75 mOhm x (1 + 0.004 (T - 25)), 22 mOhm +-1 %):')
    orow = []
    for ta in TEMPS:
        k = 1 + 0.004 * (ta - 25)
        rlo, rhi = 0.022 * 0.99 + 0.0022 * k, 0.022 * 1.01 + 0.00275 * k
        orow.append(['%d C' % ta, 0.085 / rhi, 0.115 / rlo, 0.4 / rhi, 0.6 / rlo])
    L.append(S.table(orow, ['ambient', 'OCD min A', 'OCD max A', 'SCD min A', 'SCD max A']))
    L.append('  A short on BAT_P also takes away the BQ29700\'s supply (its BAT pin is on BAT_P through 330 R), so')
    L.append('  its FETs open in ~0.3 ms whatever the current; it then re-trips on V- and stays off (release rule below).')
    L.append('')
    L.append('Protector trip vs. load current (typical thresholds, simulated) and datasheet bands:')
    rsum = (0.022, 0.022 + 0.00275)
    trows = []
    for il, tr, vm in trips:
        vlo, vhi = il * 0.022 * 0.99 + il * 0.0022, il * 0.022 * 1.01 + il * 0.00275
        band = 'none'
        if vhi > 0.085:
            band = 'OCD 16-24 ms' if vlo > 0.115 else 'OCD maybe (16-24 ms)'
        if vhi > 0.4:
            band = 'SCD 125-375 us' if vlo > 0.6 else 'SCD maybe (125-375 us), else OCD'
        trows.append([il, vm * 1e3, '%.3f ms' % (tr * 1e3) if tr is not None else 'no trip', band])
    L.append(S.table(trows, ['load A', 'V- - VSS mV at 1 ms', 'trip (typ, sim)', 'datasheet band']))
    L.append('  OCD trips for %.2f-%.2f A (85-115 mV over 22.0-24.75 mOhm); SCD for %.1f-%.1f A (400-600 mV).' % (
        0.085 / (0.022 * 1.01 + 0.00275), 0.115 / (0.022 * 0.99 + 0.0022), 0.4 / (0.022 * 1.01 + 0.00275),
        0.6 / (0.022 * 0.99 + 0.0022)))
    L.append('  Release after OCD / SCD needs BAT - V- > 1 V (checked after the 8 ms recovery delay): the BQ29700 sinks')
    L.append('  8-24 uA from V- to VSS.  Once the cell is cut off, the board\'s supply (BAT_P to GND) collapses, its')
    L.append('  regulators fall into UVLO and its load drops; the protector releases only if the board then draws less')
    L.append('  than the 8-24 uA sink at ~1 V.  With the short still present it re-trips (hiccup, ~28 ms period); with')
    L.append('  it removed the board restarts - IF the collapsed board draws < 8 uA at 1 V.  The leakage of the parts on')
    L.append('  BAT_P (charger IQ_BAT 4-5 uA, TPS2121 standby up to 25 uA per input, the 1 M / 1.5 M divider, eFuse')
    L.append('  reverse leakage) is of that order, so restart on the cell alone is NOT guaranteed: bench check.  USB,')
    L.append('  solar or drone power always restarts it (a charger pulls V- below VSS).')
    S.write_results(HERE, L)

    st = []
    rf = [r for r in res if r['name'] == 'batp_fresh_-40'][0] if False else max(res, key=lambda x: x['icell_pk'])
    st.append(S.stress('R22m 1206 1 W', 'R (sense)', 'energy in a battery short (SCD)', rf['icell_pk'] ** 2 * 0.022, 'W', 1.0,
                       'pulse', 'peak power for <= 375 us'))
    w = max(res, key=lambda x: x['ilm_avg'] if x['ilm_t25'] > 10e-6 else 0)
    st.append(S.stress('LM66100', 'U (cell-to-SYS)', 'current through a VSYS_SW short until OCD (%.0f ms)' % (w['ilm_t25'] * 1e3),
                       w['ilm_avg'], 'A', 2.5, 'absmax', w['name'] + ' (2.5 A pulsed <= 120 ms)'))
    w = max(res, key=lambda x: x['isw_avg'] if x['isw_t6'] > 10e-6 else 0)
    st.append(S.stress('TPS22965', 'U (main switch)', 'current through a VSYS_SW short until OCD', w['isw_avg'], 'A', 6.0,
                       'absmax', w['name'] + ' (6 A continuous, 8 A < 300 us)'))
    w = max(res, key=lambda x: x['pfet_avg'] if x['efet'] > 0.01 else 0)
    st.append(S.stress('CSD25485F5', 'Q (reverse FET)', 'dissipation in linear mode, VSYS_SW short until OCD', w['pfet_avg'], 'W',
                       0.5, 'derate', w['name'] + ' (%.0f mJ over 20 ms; SOA not published for 20 ms)' % (w['efet'] * 1e3)))
    w = max(res, key=lambda x: x['ib_pk'])
    st.append(S.stress('L2u2 DFE201610E', 'L (3.3 V buck)', 'current, 3V3 short', 1.4 + 3.3 / 2.2e-6 * 50e-9, 'A', 1.9,
                       'derate', 'ILIMF 1.4 A max + 50 ns x VIN/L overshoot vs Isat 1.9 A'))
    S.write_stress(HERE, st)

    plt = S.style()
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for n in ('3v3_fresh_25', 'vsyssw_fresh_25', 'batp_fresh_25', 'batp_worn_-40', 'pain_fresh_25'):
        d = np.load(os.path.join(OUT, n + '.npz'))
        ax[0].plot(d['t'] * 1e3, d['icell'], label=n)
        ax[1].plot(d['t'] * 1e3, d['v3'], label=n)
    ax[0].set_ylabel('cell current A')
    ax[1].set_ylabel('3V3 V')
    for a in ax[:2]:
        a.set_xlabel('ms')
        a.axvspan(T_ON * 1e3, T_OFF * 1e3, color='0.9')
        a.legend(fontsize=7)
    a = ax[2]
    il = np.linspace(2, 30, 300)
    a.fill_between(il, 16, 24, where=(il * 0.02475 > 0.085), color='C1', alpha=0.2, label='OCD band 16-24 ms')
    a.fill_between(il, 0.125, 0.375, where=(il * 0.02475 > 0.4), color='C3', alpha=0.2, label='SCD band 125-375 us')
    xs = [x for x, tr, _ in trips if tr is not None]
    ys = [tr * 1e3 for x, tr, _ in trips if tr is not None]
    a.plot(xs, ys, 'ko', label='simulated (typ)')
    for lab, ia in (('1 W burst', 1.2), ('3 W fresh cell', 2.8), ('3 W, 3.3 V cell', 3.9)):
        a.axvline(ia, color='0.5', lw=0.6, ls=':')
        a.text(ia, 30, lab, rotation=90, fontsize=7, va='top')
    a.set_yscale('log')
    a.set_xlabel('cell current A')
    a.set_ylabel('trip time ms')
    a.set_title('BQ29700 trip time')
    a.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'shorts.png'))


if __name__ == '__main__':
    main()
