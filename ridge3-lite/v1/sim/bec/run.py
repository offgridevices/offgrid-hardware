# -*- coding: utf-8 -*-
"""Study 4: 5 V BEC, TI LMR36506R5 (fixed 5 V, RT to GND = 2.2 MHz),
10 uH Sunlord SWPA4030S100MT, 2 x 22 uF 25 V 0805 out, 4.7 uF 50 V in.

TI publishes only an encrypted PSpice model for this part (it does not run
in ngspice), so:

  * ripple, peak current, on-time and output-capacitance checks are closed
    form from the datasheet (SNVSBB6C), at the worst corner: L -20 %,
    fSW 2.1-2.3 MHz (fOSC_2p2MHz min/max), VIN 17.4 V;
  * an ideal-switch ngspice model (the datasheet's RDS(on) maxima, the
    inductor's DCR, fixed duty from steady state) shows the inductor
    current and output ripple at 17.4 V / 0.6 A;
  * the loss model P = Irms^2 (D Rhs + (1-D) Rls) + Vin I tsw f +
    Vin^2 Csw f + Pfix is fitted to efficiency points read off TI's
    Fig 6-3 (400 kHz) and Fig 6-4 (1 MHz), 5 V fixed, 25 C, and then
    evaluated at 2.2 MHz with RDS(on) raised for a hot die.  Points read
    off a log-axis plot are good to about +-1 % efficiency, so the result
    is given as a range.
  * junction temperature: board at 100 C, PsiJB 25.9 C/W (datasheet 6.4).

Outputs: bec.png, results.txt.  Run: python3 run.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('bec')

VOUT = 5.0
L_NOM, L_TOL = 10e-6, 0.20
DCR = 0.130                         # parts.py: SWPA4030S100MT 130 mOhm
ISAT = 2.4                          # parts.py description (verify on Sunlord's sheet)
F = {'min': 2.1e6, 'typ': 2.2e6, 'max': 2.3e6}
TON_MIN = 80e-9                     # max over temperature
TOFF_MIN = 77e-9
ISC = (0.87, 1.0, 1.11)             # high-side current limit min/typ/max, 0.6 A version
RHS = (0.56, 0.92)                  # typ (25 C) / max
RLS = (0.28, 0.46)
PSI_JB = 25.9

# TI efficiency points (5 V fixed, auto mode, 25 C), read off Fig 6-3/6-4:
# (VIN, f, IOUT, efficiency, inductor DCR on TI's board)
TI_PTS = [(12, 0.4e6, 0.35, 0.935, 0.0684), (12, 0.4e6, 0.6, 0.925, 0.0684),
          (24, 0.4e6, 0.35, 0.905, 0.0684), (24, 0.4e6, 0.6, 0.910, 0.0684),
          (12, 1.0e6, 0.35, 0.925, 0.0997), (12, 1.0e6, 0.6, 0.915, 0.0997),
          (24, 1.0e6, 0.35, 0.895, 0.0997), (24, 1.0e6, 0.6, 0.895, 0.0997)]


def ripple(vin, f, L, iout=0.6):
    d = VOUT / vin
    return (vin - VOUT) * d / (L * f)


def ploss_ic(p, vin, f, iout, L, rhs, rls):
    tsw, csw, pfix = p
    d = VOUT / vin
    di = ripple(vin, f, L)
    irms2 = iout ** 2 + di ** 2 / 12
    return irms2 * (d * rhs + (1 - d) * rls) + vin * iout * tsw * f + vin ** 2 * csw * f + pfix


def fit():
    """Linear least squares: the loss model is linear in (tsw, Csw, Pfix)."""
    A, y = [], []
    for vin, f, i, eta, dcr in TI_PTS:
        L = {0.4e6: 47e-6, 1.0e6: 22e-6}[f]
        pl_meas = VOUT * i * (1 / eta - 1)
        irms2 = i ** 2 + ripple(vin, f, L) ** 2 / 12
        known = irms2 * (VOUT / vin * RHS[0] + (1 - VOUT / vin) * RLS[0]) + irms2 * dcr
        A.append([vin * i * f, vin ** 2 * f, 1.0])
        y.append(pl_meas - known)
    A, y = np.array(A), np.array(y)
    scale = np.array([1e-9, 1e-12, 1e-3])
    x = np.linalg.lstsq(A * scale, y, rcond=None)[0] * scale
    return x, A @ x - y


def netlist(vin, iout, L, f):
    # steady-state duty with the switch and inductor resistances
    d = VOUT / vin
    for _ in range(20):
        d = (VOUT + iout * (DCR * 1.3 + RLS[1] * (1 - d) + RHS[1] * d)) / vin
    T = 1 / f
    return f"""* LMR36506 ideal-switch model, VIN {vin}, {iout} A, L {L*1e6:g} uH, {f/1e6:g} MHz
VIN vin 0 {vin}
Cin vin 0 2u
Vg g 0 pulse(0 1 0 2n 2n {d*T - 2e-9:g} {T:g})
Shs vin sw g 0 SH
Bgn gn 0 V = 1 - V(g)
Sls sw 0 gn 0 SL
.model SH SW (ron={RHS[1]} roff=1meg vt=0.5)
.model SL SW (ron={RLS[1]} roff=1meg vt=0.5)
Dls 0 sw DSCH
.model DSCH D (is=1e-6 n=1.2)
L1 sw l1 {L:g} ic={iout}
Rdcr l1 out {DCR * 1.3:g}
Cout out o1 26u
Resr o1 0 3m
Rload out 0 {VOUT / iout:g}
.ic v(out)={VOUT}
.control
tran 1n 400u 0 2n uic
{S.control_save(['v(out)', 'v(sw)', 'l1#branch'], 'bec_%g_%g.dat' % (vin, iout))}
.endc
.end
"""


def main():
    lines = []
    Lmin = L_NOM * (1 - L_TOL)
    # ---------------------------------------------------------- ripple, peak, timing
    rows = []
    for vin in (6.0, 9.0, 12.6, 17.4):
        for fn in ('min', 'typ'):
            for L, ln in ((Lmin, '8 (-20 %)'), (L_NOM, '10')):
                di = ripple(vin, F[fn], L)
                rows.append([vin, '%.2f' % (F[fn] / 1e6), ln, di, di / 0.6 * 100, 0.35 + di / 2, 0.6 + di / 2])
    lines.append('Inductor ripple and peak current (2.2 MHz setting):')
    lines.append(S.table(rows, ['VIN', 'f MHz', 'L uH', 'dI p-p A', 'K % of 0.6 A', 'Ipk @0.35 A', 'Ipk @0.6 A']))
    pk = 0.6 + ripple(17.4, F['min'], Lmin) / 2
    lines.append('Worst peak at 0.6 A: %.3f A vs high-side limit ISC %.2f A min (margin %.0f %%), '
                 'inductor Isat %.1f A (parts.py; verify).' % (pk, ISC[0], (ISC[0] / pk - 1) * 100, ISAT))
    ton = VOUT / 17.4 / F['max']
    lines.append('Minimum on-time: at 17.4 V and 2.3 MHz D/f = %.0f ns vs tON-MIN 80 ns max (margin %.0f ns); '
                 'pulse skipping/foldback would start above VIN = %.1f V.' % (
                     ton * 1e9, (ton - TON_MIN) * 1e9, VOUT / (TON_MIN * F['max'])))
    dmax = 1 - TOFF_MIN * F['max']
    lines.append('Maximum duty at 2.3 MHz (tOFF-MIN 77 ns): %.2f -> needs VIN >= %.2f V before frequency '
                 'foldback (dropout mode) takes over; the 5 V rail holds down to ~5.3-5.5 V in.' % (
                     dmax, VOUT / dmax))
    lmin_sub = 1.5 * VOUT / F['min']
    lines.append('Subharmonic limit L >= 1.5 x VOUT / fSW = %.1f uH (have %.0f uH, %.0f uH at -20 %%).' % (
        lmin_sub * 1e6, L_NOM * 1e6, Lmin * 1e6))
    lines.append('Minimum ripple rule (>= 10 %% of 0.6 A = 60 mA): %.0f mA at 12.6 V, %.0f mA at 6 V (typ L, f).' % (
        ripple(12.6, F['typ'], L_NOM) * 1e3, ripple(6.0, F['typ'], L_NOM) * 1e3))
    lines.append('Output capacitance: 2 x 22 uF rated (TI Table 8-1, 5 V at 1 MHz: nominal 2 x 22 uF, minimum '
                 '1 x 22 uF rated); ~13 uF each left at 5 V bias.  Ripple ~ dI/(8 f C) + dI ESR = %.1f mV.' % (
                     (ripple(17.4, F['min'], Lmin) / (8 * F['min'] * 26e-6) + ripple(17.4, F['min'], Lmin) * 3e-3) * 1e3))
    lines.append('At 1 MHz with the same 10 uH (8 uH worst): ripple %.2f A p-p, peak %.3f A at 0.6 A vs ISC 0.87 A '
                 'min; L >= %.1f uH for subharmonic stability.' % (
                     ripple(17.4, 0.93e6, Lmin), 0.6 + ripple(17.4, 0.93e6, Lmin) / 2, 1.5 * VOUT / 0.93e6 * 1e6))

    # ---------------------------------------------------------- losses
    p, resid = fit()
    lines.append('\nLoss-model fit to TI curves: tsw %.1f ns, Csw %.0f pF, Pfix %.0f mW; residuals %s mW.' % (
        p[0] * 1e9, p[1] * 1e12, p[2] * 1e3, ', '.join('%+.0f' % (r * 1e3) for r in resid)))
    rows = []
    for f in (1.0e6, 2.2e6):
        for iout in (0.35, 0.6):
            for vin in (12.6, 17.4):
                L = L_NOM
                hot = 1.45            # RDS(on) at Tj ~110-120 C vs 25 C (typical silicon)
                pic = ploss_ic(p, vin, f, iout, L, RHS[0] * hot, RLS[0] * hot)
                pic_max = ploss_ic(p, vin, f, iout, L, RHS[1], RLS[1]) + 0.03
                irms2 = iout ** 2 + ripple(vin, f, L) ** 2 / 12
                pl = irms2 * DCR * 1.3
                eta = VOUT * iout / (VOUT * iout + pic + pl)
                rows.append(['%.1f' % (f / 1e6), iout, vin, pic * 1e3, pic_max * 1e3, pl * 1e3, eta * 100,
                             100 + pic * PSI_JB, 100 + pic_max * PSI_JB])
    lines.append(S.table(rows, ['f MHz', 'IOUT', 'VIN', 'P_IC mW (hot typ)', 'P_IC mW (RDS max +30 mW)',
                                'P_L mW', 'eff %', 'Tj C (board 100)', 'Tj C (worst)']))
    lines.append('Limits: TJ 150 C (operating range; lifetime derated above 125 C); thermal shutdown 158 C min.')

    # ---------------------------------------------------------- switching sim
    sims = {}
    for vin, iout, L in ((17.4, 0.6, Lmin), (17.4, 0.35, Lmin), (9.0, 0.6, Lmin)):
        name = 'bec_%g_%g' % (vin, iout)
        S.ngspice(netlist(vin, iout, L, F['min']), OUT, name)
        d = S.wrdata(os.path.join(OUT, name + '.dat'))
        m = d['time'] > 300e-6
        il = d['l1#branch'][m]
        vo = d['v(out)'][m]
        sims[(vin, iout)] = d
        lines.append('sim VIN %.1f V, %.2f A, L 8 uH, 2.1 MHz: IL %.3f..%.3f A (%.0f mA p-p), VOUT ripple %.1f mV p-p' % (
            vin, iout, il.min(), il.max(), (il.max() - il.min()) * 1e3, (vo.max() - vo.min()) * 1e3))
    txt = '\n'.join(lines)
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)

    plt = S.style()
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    a = ax[0]
    for (vin, iout), d in sims.items():
        m = (d['time'] > 398e-6)
        a.plot((d['time'][m] - 398e-6) * 1e9, d['l1#branch'][m], label='IL, %.1f V in, %.2f A' % (vin, iout))
    a.axhline(ISC[0], color='C3', lw=0.8); a.text(5, ISC[0] + 0.01, 'ISC min 0.87 A', color='C3', fontsize=7)
    a.set_xlabel('ns'); a.set_ylabel('A'); a.set_ylim(0, 1.0); a.legend(fontsize=7)
    a.set_title('inductor current, 8 uH (-20 %), 2.1 MHz')
    a = ax[1]
    vins = np.linspace(6, 30, 200)
    a2 = a.twinx()
    for f, c in ((2.2e6, 'C0'), (1.0e6, 'C1')):
        a.plot(vins, 0.6 + ripple(vins, f * 0.955, Lmin) / 2, c, label='peak IL at 0.6 A, %.1f MHz, 8 uH' % (f / 1e6))
        a2.plot(vins, VOUT / vins / (f * 1.045) * 1e9, c, ls='--', label='on-time, %.1f MHz (+4.5 %%)' % (f / 1e6))
    a.axhline(ISC[0], color='C3', lw=0.8, label='ISC min 0.87 A')
    a2.axhline(TON_MIN * 1e9, color='C2', lw=0.8, ls=':', label='tON-MIN 80 ns max')
    a.axvline(17.4, color='0.6', lw=0.6)
    a.set_ylim(0.5, 1.0); a2.set_ylim(0, 400)
    a.set_xlabel('VIN (V)'); a.set_ylabel('A (solid)'); a2.set_ylabel('ns (dashed)')
    a.legend(fontsize=6, loc='upper left'); a2.legend(fontsize=6, loc='upper right')
    a.set_title('peak current and on-time vs VIN')
    a = ax[2]
    rr = np.array([[float(r[0]), r[1], r[2], r[3], r[6]] for r in rows])
    for f, c in ((1.0, 'C1'), (2.2, 'C0')):
        for vin, ls in ((12.6, '--'), (17.4, '-')):
            m = (rr[:, 0] == f) & (rr[:, 2] == vin)
            a.plot(rr[m, 1], rr[m, 3], c + 'o' + ls, label='P_IC, %.1f MHz, %.1f V' % (f, vin))
    a.set_xlabel('IOUT (A)'); a.set_ylabel('mW'); a.legend(fontsize=7)
    a.set_title('IC dissipation (fitted to TI curves, hot RDS)')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'bec.png'))


if __name__ == '__main__':
    main()
