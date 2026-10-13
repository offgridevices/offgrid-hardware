# -*- coding: utf-8 -*-
"""Study 2: battery-lead voltage spikes on VBAT.

Circuit (ngspice):
  pack     OVONIC 4S 650 mAh: 17.4 V (4S HV, full; worst case for every
           limit) with 25 mOhm ESR
  lead     XT30 + 2 x ~12.5 cm of 18 AWG: 150 nH (swept 100 / 150) and
           6 mOhm (21 mOhm/m x 0.25 m + XT30)
  pads     470 uF 35 V low-ESR electrolytic at the battery pads: ESR 40 mOhm
           (swept 30 / 60), ESL 8 nH incl. its leads
  board    1 nH of plane (1 ohm across it: HF loss, keeps the solver sane)
           from the pads to the ceramics and the ESCs: 12 bridge caps
           4.7 uF 50 V 0805 + BEC input 4.7 uF + 100 nF, at ~2 uF each
           left at 17 V (DC bias): 26 uF, 0.5 mOhm, 0.05 nH (in parallel)
  TVS      SMF22A: conduction from VBR (26.9 V, the maximum breakdown at
           1 mA: the worst case for what it lets through) with 1.5 ohm
           dynamic resistance, which puts 35.5 V at 5.6 A, the datasheet's
           clamp point (10/1000 us).  400 pF.
  load     the four ESCs as one current source on the plane at the ceramics.

Scenarios
  a  60 A full-throttle load released in 1 us (failsafe / disarm, all four
     ESCs cut together)
  b  regenerative braking: load steps from +60 A to -20/-30/-40 A in 20 us
     (AM32 brake / 3D reversal) and stays reversed for 5 or 20 ms
  c  a and b with the electrolytic missing
  d  battery unplugged (or the XT30 bouncing open) while braking at 20 A:
     only the caps and the TVS can take the current
  e  PWM input ripple: four ESCs chopping in phase at 24 / 48 kHz, at the
     worst-ripple point of a prop load (10.4 A at 83 % duty) and at hover
     (4 A at 50 %), with and without the electrolytic
  f  hot plug: the pack connected to an unpowered board

TVS energy check: the 200 W rating is a 10/1000 us pulse (about 0.29 J);
for other widths the peak-power curve (Fig 1) is taken as P ~ t^-0.5, and
derated linearly to 50 % at 100 C (Fig 2, board temperature).

Outputs: battery.png, results.txt.  Run: python3 run.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('battery')

VPACK = 17.4

LIMITS = [
    ('FET VDS (TPN2R304PL), abs max', 40.0),
    ('470 uF electrolytic, rated', 35.0),
    ('LMR36506 VIN, abs max', 70.0),
    ('TPS7A1601 IN (60 V) / EN tied to IN (40 V abs)', 40.0),
    ('MLCCs on VBAT, rated', 50.0),
    ('DRV8300 SHx / BSTx (110 / 125 V abs)', 110.0),
]


def netlist(name, load, tstop, lbat=150e-9, esr=40e-3, elec=True, tvs='max', bat=True, maxstep=None, plug=False):
    bv = {'max': 26.9, 'min': 24.4, 'none': None}[tvs]
    if bv:
        # breakdown as a smooth knee (softplus, 50 mV wide) at VBR, then the
        # 1.5 ohm dynamic resistance; 400 pF of junction capacitance
        x = '((V(vp) - %g) / 0.05)' % bv
        tv = ('BTVS vp 0 I = 0.05 / 1.5 * (max(%s, 0) + ln(1 + exp(-abs(%s))))\n'
              'CTVS vp 0 400p\n' % (x, x))
    else:
        tv = ''
    el = ('Lel vp e1 8n\nRel e1 e2 %g\nCel e2 0 470u\n' % esr) if elec else ''
    if bat:
        vb = ('pwl(0 0 1u 0 1.05u %g)' % VPACK) if plug else '%g' % VPACK
        src = (f'VB vb 0 {vb}\nRpack vb vsrc 25m\nRlead vsrc l1 6m\nLlead l1 vp {lbat:g}\n')
        ic, uic, vecs = '', '', ['llead#branch']
    else:
        # pack unplugged: no source at all, the caps start charged to VPACK
        src = 'Rleak vp 0 100k\n'
        ic = '.ic v(vp)=%g v(c1)=%g v(c3)=%g v(e2)=%g\n' % (VPACK, VPACK, VPACK, VPACK)
        uic, vecs = ' uic', []
    ms = maxstep or tstop / 20000
    return f"""* battery lead: {name}
{src}{ic}{el}Lpl vp c1 1n
Rpl vp c1 1
Rcer c1 c2 0.5m
Lcer c2 c3 0.05n
Ccer c3 0 26u
{tv}Iload c1 0 {load}
.options reltol=1e-4 itl4=100
.control
tran {ms:g} {tstop:g} 0 {ms:g}{uic}
{S.control_save(['v(vp)', 'v(c3)'] + vecs + (['lel#branch'] if elec else []), name + '.dat')}
.endc
.end
"""


def tvs_current(v, bv):
    """TVS current, the same expression as the netlist's B source."""
    if bv is None:
        return np.zeros_like(v)
    return 0.05 / 1.5 * np.logaddexp(0, (v - bv) / 0.05)


def tvs_allowed(e, ppk, t_c=100.0):
    """Energy check against the peak-power curve: equivalent rectangular
    pulse of width tp = E / Ppk; allowed Ppk(tp) = 200 W (tp / 1 ms)^-0.5
    x derating (linear to 0 at 175 C from 100 % at 25 C)."""
    if ppk <= 0:
        return np.inf, 0.0
    tp = e / ppk
    der = max(0.0, 1 - (t_c - 25) / 150)
    pall = 200.0 * (tp / 1e-3) ** -0.5 * der
    return pall, tp


def run(name, load, tstop, **kw):
    S.ngspice(netlist(name, load, tstop, **kw), OUT, name)
    d = S.wrdata(os.path.join(OUT, name + '.dat'))
    bv = {'max': 26.9, 'min': 24.4, 'none': None}[kw.get('tvs', 'max')]
    d['itvs'] = tvs_current(d['v(vp)'], bv)
    d['ptvs'] = d['itvs'] * d['v(vp)']
    d['etvs'] = np.trapezoid(d['ptvs'], d['time'])
    return d


def main():
    res = {}
    rel = 'pwl(0 60 1m 60 %g 0)' % (1e-3 + 1e-6)
    for lb in (100e-9, 150e-9):
        for esr in (30e-3, 60e-3):
            res[('a', lb, esr, True)] = run('a_L%g_esr%g' % (lb * 1e9, esr * 1e3), rel, 3e-3, lbat=lb, esr=esr)
        res[('a', lb, 0, False)] = run('a_L%g_noelec' % (lb * 1e9), rel, 3e-3, lbat=lb, elec=False)
    for ir in (20, 30, 40):
        for hold in (5e-3, 20e-3):
            brk = 'pwl(0 60 1m 60 %g %g %g %g %g 0)' % (1e-3 + 20e-6, -ir, 1e-3 + hold, -ir, 1e-3 + hold + 20e-6)
            res[('b', ir, hold, True)] = run('b_I%d_t%g' % (ir, hold * 1e3), brk, hold + 4e-3, esr=60e-3)
            res[('b', ir, hold, False)] = run('b_I%d_t%g_noelec' % (ir, hold * 1e3), brk, hold + 4e-3, elec=False)
    # d: pack unplugged (no source), braking pushes 20 A into the board for 5 ms
    brk = 'pwl(0 0 0.5m 0 0.52m -20 5.5m -20 5.52m 0)'
    res[('d', 20, True)] = run('d_open_I20', brk, 8e-3, bat=False, maxstep=0.5e-6)
    res[('d', 20, False)] = run('d_open_I20_noelec', brk, 8e-3, bat=False, elec=False, maxstep=0.5e-6)
    # e: PWM input ripple.  Prop load: motor current ~ Imax d^2, so the
    # ESC's input ripple I d^2 sqrt(d (1 - d)) peaks at d = 0.83 (10.4 A of
    # 15 A); and a 3" hover, ~4 A per motor at ~50 %.  All four in phase
    # (worst case for the voltage ripple; AM32 ESCs free-run, so they drift
    # through every alignment).
    for f in (24e3, 48e3):
        for tag, ipk, duty in (('worst', 10.4, 0.833), ('hover', 4.0, 0.5)):
            per = 1 / f
            pw = 'pulse(0 %g 0.2m 50n 50n %g %g)' % (4 * ipk, per * duty - 50e-9, per)
            for el in (True, False):
                res[('e', f, tag, el)] = run('e_%s_%dk%s' % (tag, f / 1e3, '' if el else '_noelec'), pw, 2.2e-3,
                                             esr=40e-3, elec=el, maxstep=20e-9)
    # f: hot plug: pack connected to an unpowered board (caps empty)
    for el in (True, False):
        res[('f', el)] = run('f_plug%s' % ('' if el else '_noelec'), '0', 0.5e-3, elec=el, plug=True, maxstep=5e-9)

    lines = ['Pack %.1f V (4S HV full), 25 mOhm; lead 6 mOhm.  Peak = highest VBAT at the ceramics.\n' % VPACK]
    rows = []

    def add(label, d, t0=0.0):
        m = d['time'] > t0
        v = d['v(c3)'][m]
        e = float(d['etvs'])
        ppk = float(np.max(d['ptvs']))
        if e < 1e-6:          # TVS not conducting (leakage only)
            rows.append([label, float(np.max(v)), 40 - float(np.max(v)), '0', '-', '-', '-', 'not conducting'])
            return
        pall, tp = tvs_allowed(e, ppk)
        rows.append([label, float(np.max(v)), 40 - float(np.max(v)), '%.3g' % (e * 1e3), '%.0f' % ppk,
                     '%.0f' % pall, '%.0f us' % (tp * 1e6), 'OK' if ppk < pall else 'OVERLOAD (fails)'])
    for lb in (100e-9, 150e-9):
        for esr in (30e-3, 60e-3):
            add('a: 60 A release, %d nH, ESR %d mOhm' % (lb * 1e9, esr * 1e3), res[('a', lb, esr, True)])
        add('c: 60 A release, %d nH, NO electrolytic' % (lb * 1e9), res[('a', lb, 0, False)])
    for ir in (20, 30, 40):
        for hold in (5e-3, 20e-3):
            add('b: brake +60 -> -%d A, %g ms, ESR 60' % (ir, hold * 1e3), res[('b', ir, hold, True)])
            add('c: brake +60 -> -%d A, %g ms, NO elec.' % (ir, hold * 1e3), res[('b', ir, hold, False)])
    add('d: pack OPEN, braking 20 A 5 ms', res[('d', 20, True)])
    add('d: pack OPEN, braking 20 A, NO elec.', res[('d', 20, False)])
    add('f: hot plug, 470 uF', res[('f', True)])
    add('f: hot plug, NO electrolytic', res[('f', False)])
    for f in (24e3, 48e3):
        for tag in ('worst', 'hover'):
            add('e: PWM ripple %s, %d kHz' % (tag, f / 1e3), res[('e', f, tag, True)], 1e-3)
            add('e: PWM ripple %s, %d kHz, NO elec.' % (tag, f / 1e3), res[('e', f, tag, False)], 1e-3)
    lines.append(S.table(rows, ['scenario', 'VBAT pk', 'margin to 40 V', 'E_TVS mJ', 'P_TVS pk W',
                                'P allowed W', 'equiv. width', 'TVS']))
    # ripple details
    lines.append('\nPWM ripple (four ESCs in phase; for heating, independent ESCs add as sqrt(4) = 2x one ESC,\n'
                 'i.e. half the in-phase rms):')
    rr = []
    for f in (24e3, 48e3):
        for tag, ipk, duty in (('worst', 10.4, 0.833), ('hover', 4.0, 0.5)):
            for el in (True, False):
                d = res[('e', f, tag, el)]
                m = d['time'] > 1.2e-3
                v = d['v(c3)'][m]
                ie = np.sqrt(np.mean(d['lel#branch'][m] ** 2)) if el else 0.0
                ib = np.std(d['llead#branch'][m])
                rr.append(['%d kHz' % (f / 1e3), '%s (%g A, %d %%)' % (tag, ipk, duty * 100),
                           '470 uF' if el else 'none', v.max() - v.min(), ie, ie / 2, ie ** 2 * 0.04, ie ** 2 / 4 * 0.04, ib])
    lines.append(S.table(rr, ['PWM', 'per motor', 'electrolytic', 'VBAT p-p', 'I elec rms (in phase)',
                              'I elec rms (indep.)', 'P_ESR W (in phase)', 'P_ESR W (indep.)', 'lead ripple A rms']))
    lines.append('\nLimits: ' + '; '.join('%s %.0f V' % l for l in LIMITS))
    txt = '\n'.join(lines)
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)

    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(15, 7.5))
    a = ax[0, 0]
    for key, lab in (((('a', 150e-9, 30e-3, True)), '470 uF, ESR 30'), ((('a', 150e-9, 60e-3, True)), '470 uF, ESR 60'),
                     ((('a', 150e-9, 0, False)), 'no electrolytic')):
        d = res[key]
        a.plot((d['time'] - 1e-3) * 1e6, d['v(c3)'], label=lab)
    a.set_xlim(-20, 300); a.set_title('a/c: 60 A released in 1 us, 150 nH lead')
    a.set_xlabel('us'); a.set_ylabel('VBAT (V)'); a.legend()
    a = ax[0, 1]
    for key, lab in (((('b', 40, 20e-3, True)), '470 uF'), ((('b', 40, 20e-3, False)), 'no electrolytic')):
        d = res[key]
        a.plot((d['time'] - 1e-3) * 1e3, d['v(c3)'], label=lab)
    a.set_title('b/c: brake, +60 A -> -40 A in 20 us, 20 ms'); a.set_xlabel('ms'); a.legend()
    a = ax[0, 2]
    for key, lab in (((('b', 40, 20e-3, True)), '470 uF'), ((('b', 40, 20e-3, False)), 'no electrolytic')):
        d = res[key]
        a.plot((d['time'] - 1e-3) * 1e6, d['v(c3)'], label=lab)
    a.set_xlim(-10, 150); a.set_title('b/c: zoom on the reversal'); a.set_xlabel('us'); a.legend()
    a = ax[1, 0]
    for key, lab in (((('d', 20, True)), '470 uF'), ((('d', 20, False)), 'no electrolytic')):
        d = res[key]
        a.plot(d['time'] * 1e3, d['v(c3)'], label='VBAT, ' + lab)
    a.axhline(40, color='C3', lw=0.8); a.axhline(35, color='C1', lw=0.8, ls='--')
    a.set_title('d: pack unplugged, braking pushes 20 A in (0.5-5.5 ms)'); a.set_xlabel('ms'); a.set_ylabel('V')
    a.legend(fontsize=7, loc='center left')
    a2 = a.twinx()
    d = res[('d', 20, True)]
    a2.plot(d['time'] * 1e3, d['itvs'], 'C2', lw=0.8, label='TVS current (470 uF)')
    a2.set_ylabel('A'); a2.legend(loc='center right', fontsize=7)
    a = ax[1, 1]
    for key, lab in (((('e', 24e3, 'worst', True)), '470 uF'), ((('e', 24e3, 'worst', False)), 'no electrolytic')):
        d = res[key]
        a.plot((d['time'] - 1.5e-3) * 1e6, d['v(c3)'], label='ripple, ' + lab)
    for key, lab in (((('f', True)), '470 uF'), ((('f', False)), 'no electrolytic')):
        d = res[key]
        a.plot(d['time'] * 1e6, d['v(c3)'], ls='--', label='hot plug, ' + lab)
    a.set_xlim(0, 150); a.set_xlabel('us')
    a.set_title('e: 4 x 10.4 A at 83 %, 24 kHz, in phase; f: hot plug', fontsize=8)
    a.legend(fontsize=7)
    a = ax[1, 2]; a.axis('off')
    a.text(0, 1, '\n'.join('%-40s %5.1f V' % (r[0][:40], r[1]) for r in rows), va='top', family='monospace', fontsize=6.5)
    a.set_title('peak VBAT per scenario (limit: FETs 40 V, electrolytic 35 V)', fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'battery.png'))


if __name__ == '__main__':
    main()
