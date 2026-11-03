# -*- coding: utf-8 -*-
"""Study 3: gate-drive supply (TPS7A1601 at 11 V -> four DRV8300D).

  input    VBAT -> 10 ohm -> GVDD_IN, 4.7 uF 50 V X7R 0805 (2 uF left at 17 V)
  LDO      TPS7A1601 DRB (SON-8 3 x 3), 1.193 V x (1 + 82k/10k) = 10.97 V.
           Macro-model: a current-source pass element driven by the error
           (output resistance 0.2 ohm) through a 5 us lag (the TPS7A16 is a
           5 uA-IQ part with a slow loop: the caps carry every gate pulse),
           clamped to its 101 mA minimum current limit and to dropout
           (500 mV max at 100 mA -> 5 ohm).
  rail     10 uF 0603 25 V X5R at the LDO (4 uF left at 11 V) and one at each
           driver (4 uF each), 3 nH / 30 mOhm of trace between.
  load     per DRV8300: 1.4 mA quiescent (max), 105-220 uA bootstrap leakage
           while switching; per PWM cycle a low-side gate charge (45 nC to
           11 V: 41 nC at 10 V + ~4 nC/V) drawn in ~60 ns, and the bootstrap
           refill of the high side's 45 nC through the bootstrap diode
           (0.7 V + 15 ohm) into 1 uF 25 V 0402 X5R (0.4 uF at 11 V).  All
           four ESCs switching in phase at 50 % duty (worst case for ripple).

Also computed (closed form, from the DRV8300 datasheet):
  * LDO dissipation and junction temperature at 17.4 V in, board at 100 C
  * bootstrap droop during the longest high-side on-time (100 % duty: each
    high side is on for 120 electrical degrees of 6-step) and the lowest
    eRPM before VBST falls to the BSTUV threshold
  * behaviour on a sagging 3S / 2S pack (dropout)

Outputs: gate_supply.png, results.txt.  Run: python3 run.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('gate_supply')

VSET = 1.193 * (1 + 82 / 10)          # 10.98 V
QG11 = 45e-9                          # gate charge to 11 V
CBST = 0.4e-6                         # 1 uF 25 V 0402 X5R at 11 V
IQ = {'typ': 0.825e-3, 'max': 1.4e-3}
ILBS_TRAN = {'typ': 105e-6, 'max': 220e-6}     # per switching phase
ILBS_DC = {'typ': 85e-6, 'max': 150e-6}        # high side held on
VBOOT = {'typ': 0.7, 'max': 0.85}              # at 100 uA
VBSTUV_F = {'typ': 4.0, 'max': 4.5}            # falling threshold
VGVDDUV_F = {'typ': 4.35, 'max': 4.4}
R_IN = 10.0
POLE_PAIRS = 7                                 # XING2 1404: 12N14P


def load_current(f, corner='max'):
    """Average GVDD current for one DRV8300 with one phase PWM'd
    (complementary: one high-side and one low-side turn-on per cycle) and
    one low side held on."""
    return IQ[corner] + 2 * QG11 * f + ILBS_TRAN[corner] + ILBS_DC[corner]


def netlist(f, vbat=17.4):
    T = 1 / f
    ton = T / 2
    # sw of each ESC's PWM'd phase: 0 V (low side / diode) or vbat (high side on)
    dead = 1.155e-6
    sw = 'pulse(0 %g %g 20n 20n %g %g)' % (vbat, dead, ton - 20e-9, T)
    # low-side gate charge: 45 nC in 60 ns at LS turn-on (one dead time after HS off)
    tls = dead + ton + dead
    ils = 'pulse(0 %g %g 5n 5n 50n %g)' % (QG11 / 55e-9, tls, T)
    # high-side gate charge from the bootstrap cap at HS turn-on
    ihs = 'pulse(0 %g %g 5n 5n 50n %g)' % (QG11 / 55e-9, dead, T)
    drivers = []
    for k in range(4):
        drivers.append(f"""* driver {k}
Lt{k} gv gt{k} 3n
Rt{k} gt{k} gd{k} 30m
Cd{k} gd{k} 0 4u
Iq{k} gd{k} 0 {IQ['max'] + ILBS_TRAN['max']:g}
Ils{k} gd{k} 0 {ils}
Vsw{k} sw{k} 0 {sw}
Db{k} gd{k} bst{k} DBST
Cb{k} bst{k} sw{k} {CBST:g}
Ihs{k} bst{k} sw{k} {ihs}
Ilk{k} bst{k} sw{k} {ILBS_DC['max']:g}
""")
    return f"""* gate-drive supply, PWM {f/1e3:g} kHz, VBAT {vbat}
.model DBST D (is=1.2e-10 n=2 rs=15)
VB vbat 0 {vbat}
Rin vbat vin {R_IN}
Cin vin 0 2u
* TPS7A1601 macro-model
Bx x 0 V = ({VSET:.4f} - V(gv)) / 0.2
Rx x xl 1k
Cx xl 0 5n
Bpass vin gv I = min(min(max(V(xl), 0), 0.101), max(V(vin) - V(gv), 0) / 5)
Cout gv 0 4u
{''.join(drivers)}
.ic v(gv)={VSET:.3f} {' '.join('v(gd%d)=%.3f v(bst%d)=10.2' % (k, VSET, k) for k in range(4))} v(vin)={vbat - 0.25}
.options reltol=1e-4
.control
tran 10n 1.5m 0 20n uic
{S.control_save(['v(gv)', 'v(gd0)', 'v(vin)', 'v(bst0)', 'v(sw0)', 'i(vb)'], 'gs_%d.dat' % (f / 1e3))}
.endc
.end
"""


def main():
    lines = []
    res = {}
    for f in (24e3, 48e3):
        S.ngspice(netlist(f), OUT, 'gs_%d' % (f / 1e3))
        d = S.wrdata(os.path.join(OUT, 'gs_%d.dat' % (f / 1e3)))
        m = d['time'] > 1.0e-3
        res[f] = d
        gd = d['v(gd0)'][m]
        gv = d['v(gv)'][m]
        iin = -d['i(vb)'][m]
        vb = (d['v(bst0)'] - d['v(sw0)'])[m]
        lines.append('PWM %2d kHz (sim): GVDD at a driver %.3f..%.3f V (%.0f mV p-p), LDO output %.0f mV p-p, '
                     'LDO input current %.1f mA avg, bootstrap %.2f..%.2f V' % (
                         f / 1e3, gd.min(), gd.max(), (gd.max() - gd.min()) * 1e3,
                         (gv.max() - gv.min()) * 1e3, iin.mean() * 1e3, vb.min(), vb.max()))
        res[(f, 'iin')] = iin.mean()

    # ---- LDO dissipation and Tj
    lines.append('\nLDO dissipation (4 drivers, max currents), VIN 17.4 V; board at 100 C:')
    rows = []
    for f in (24e3, 48e3):
        for corner in ('typ', 'max'):
            I = 4 * load_current(f, corner)
            vin = 17.4 - I * R_IN
            p = (vin - VSET) * I
            rows.append([int(f / 1e3), corner, I * 1e3, I ** 2 * R_IN * 1e3, p * 1e3,
                         100 + p * 11.3, 100 + p * 44.5, 50 + p * 44.5])
    lines.append(S.table(rows, ['f kHz', 'corner', 'I_GVDD mA', 'P(10R) mW', 'P_LDO mW',
                                'Tj (board 100 C, RthJB 11.3)', 'Tj (100 C + RthJA 44.5)', 'Tj (50 C amb, RthJA)']))
    lines.append('Limits: TJ 125 C operating (150 C abs), thermal shutdown 170 C; current limit 101 mA min.')

    # ---- bootstrap droop
    lines.append('\nBootstrap at 100 % duty (high side held on for 120 electrical degrees):')
    rows = []
    for corner in ('typ', 'max'):
        v0 = VSET - VBOOT[corner]
        # charge sharing with the gate at turn-on: solve v = v0 - Qg(v)/C, Qg ~ 4.1 nC/V above the plateau
        v = v0
        for _ in range(20):
            qg = 16e-9 + max(v - 3.5, 0) * 4.0e-9
            v = v0 - qg / CBST
        slope = (ILBS_DC[corner] + 0.1e-6) / CBST
        tmax = (v - VBSTUV_F[corner]) / slope
        erpm = 20.0 / tmax                       # ton = (1/3) x 60 / eRPM
        rows.append([corner, v0, v, slope, tmax * 1e3, erpm, erpm / POLE_PAIRS])
    lines.append(S.table(rows, ['corner', 'VBST before', 'after turn-on', 'droop V/s', 'time to BSTUV ms',
                                'min eRPM', 'min mech. RPM']))
    droop_rows = rows

    # ---- dropout on a sagging pack
    lines.append('\nSagging pack (GVDD = VBAT - I x 10 ohm - dropout (5 ohm x I max); bootstrap after turn-on):')
    rows = []
    I = 4 * load_current(48e3, 'max')
    for name, vb in (('4S HV full', 17.4), ('4S 3.5 V/cell sag', 14.0), ('3S full', 12.6),
                     ('3S 3.3 V/cell', 9.9), ('3S 3.0 V/cell sag', 9.0), ('2S full', 8.4),
                     ('2S 3.3 V/cell', 6.6), ('2S 3.0 V/cell sag', 6.0), ('2S 2.8 V/cell', 5.6)):
        gv = min(VSET, vb - I * R_IN - I * 5.0)
        vbst = gv - VBOOT['max'] - (16e-9 + max(gv - 4.4, 0) * 4e-9) / CBST
        ok = 'OK' if (gv > VGVDDUV_F['max'] and vbst > VBSTUV_F['max']) else (
            'BSTUV risk' if gv > VGVDDUV_F['max'] else 'GVDD UVLO')
        rows.append([name, vb, gv, vbst, ok])
    lines.append(S.table(rows, ['pack', 'VBAT', 'GVDD', 'VBST after HS turn-on (worst)', 'status']))
    # minimum VBAT for worst-case BSTUV
    vbs = np.linspace(4, 18, 1401)
    gvs = np.minimum(VSET, vbs - I * (R_IN + 5))
    vbst = gvs - VBOOT['max'] - (16e-9 + np.maximum(gvs - 4.4, 0) * 4e-9) / CBST
    vmin = vbs[np.argmax(vbst > VBSTUV_F['max'])]
    vmin_t = vbs[np.argmax(gvs - VBOOT['typ'] - (16e-9 + np.maximum(gvs - 4.4, 0) * 4e-9) / CBST > VBSTUV_F['typ'])]
    lines.append('Lowest VBAT keeping VBST above BSTUV after a turn-on: %.2f V worst case, %.2f V typical '
                 '(%.2f / %.2f V per cell on 2S).' % (vmin, vmin_t, vmin / 2, vmin_t / 2))
    txt = '\n'.join(lines)
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)

    plt = S.style()
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    a = ax[0]
    for f in (24e3, 48e3):
        d = res[f]
        m = (d['time'] > 1.3e-3) & (d['time'] < 1.3e-3 + 2 / 24e3)
        a.plot((d['time'][m] - 1.3e-3) * 1e6, d['v(gd0)'][m], label='GVDD at a driver, %d kHz' % (f / 1e3))
        a.plot((d['time'][m] - 1.3e-3) * 1e6, d['v(gv)'][m], ls='--', lw=0.8, label='LDO output, %d kHz' % (f / 1e3))
    a.set_xlabel('us'); a.set_ylabel('V'); a.legend(fontsize=7)
    a.set_title('GVDD ripple, 4 ESCs switching in phase, 50 % duty')
    a = ax[1]
    t = np.linspace(0, 40e-3, 400)
    for r, ls in zip(droop_rows, ('-', '--')):
        corner, v0, v1, slope = r[0], r[1], r[2], r[3]
        a.plot(t * 1e3, np.maximum(v1 - slope * t, 0), ls=ls, label='VBST-SH, %s leakage' % corner)
        a.axhline(VBSTUV_F[corner], color='C3', ls=ls, lw=0.8)
    a.set_xlabel('high-side on-time (ms)'); a.set_ylabel('V')
    a.set_title('Bootstrap droop at 100 % duty (red: BSTUV falling typ/max)', fontsize=9)
    # a 120-degree on-time of t ms happens at 20 / t thousand eRPM
    a2 = a.secondary_xaxis('top', functions=(lambda x: 20.0 / np.maximum(x, 1e-3),
                                              lambda e: 20.0 / np.maximum(e, 1e-3)))
    a2.set_xlabel('eRPM at which a 120-degree on-time lasts this long (x1000)')
    a2.set_ticks([0.5, 0.75, 1, 1.5, 2, 3, 5])
    a.legend(fontsize=7)
    a = ax[2]
    a.plot(vbs, gvs, label='GVDD (48 kHz load, max currents)')
    a.plot(vbs, vbst, label='VBST after high-side turn-on (worst)')
    a.axhline(VBSTUV_F['max'], color='C3', lw=0.8, label='BSTUV falling max 4.5 V')
    a.axhline(VGVDDUV_F['max'], color='C1', lw=0.8, ls='--', label='GVDD UVLO falling max 4.4 V')
    for v, lab in ((6.0, '2S sag'), (9.0, '3S sag'), (12.6, '3S full'), (17.4, '4S HV')):
        a.axvline(v, color='0.6', lw=0.6); a.text(v, 1.0, lab, rotation=90, fontsize=7)
    a.set_xlim(4, 18); a.set_ylim(0, 12); a.set_xlabel('VBAT (V)'); a.set_ylabel('V'); a.legend(fontsize=7)
    a.set_title('Dropout on a sagging pack')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'gate_supply.png'))


if __name__ == '__main__':
    main()
