# -*- coding: utf-8 -*-
"""Study 5: sense chains (all linear or piecewise networks, solved directly).

(a) Current, per ESC: 0.5 mOhm HCS1206 shunt -> INA186A3 (100 V/V, VS =
    3.3 V, REF = GND) -> IOUT -> 1.5k / 1k -> 100 nF -> STM32G071 PA5; and
    the four IOUTs -> 10k each -> CUR (62k + 100 nF) -> FC PB1.
    INA186 behaviour: 35 kHz bandwidth (A3, 10 pF), 0.3 V/us slew, output
    swing GND + 1 mV .. VS - 40 mV (more at a 2 mA load), VOS 50 uV max,
    gain error 1 % max (SBOS750 7.5).  The shunt only carries the bridge's
    supply current: the phase current while the high side is on, nothing
    during the complementary off time (the current circulates through the
    two low sides, both on the bridge side of the shunt).  So the amplifier
    sees a pulse train of height I at the PWM duty.
(b) Back-EMF: each phase -> 10k -> CMP_x, 2.2k to GND; 10k from each CMP_x
    to the virtual neutral (PA3).  A 3-phase BLDC (balanced star, trapezoidal
    back-EMF), 6-step drive with complementary PWM on the high phase.  The
    floating phase sits at the star point plus its own back-EMF, clamped by
    its FETs' body diodes to -0.8 V .. VBAT + 0.8 V.  The resistor network is
    solved exactly (nodal analysis), including a Monte Carlo over 1 %
    resistor tolerance for the zero-crossing error.
(c) Battery-voltage dividers: FC 10k / 1k + 100 nF (Betaflight vbat_scale
    110); ESC 100k / 10k, no capacitor (AM32 TARGET_VOLTAGE_DIVIDER 110).

Outputs: sense.png, bemf.png, results.txt.  Run: python3 run.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))

RSH = 0.5e-3
G = 100.0
VS = 3.3
SR = 0.3e6                  # V/s
BW = 35e3
VOS = 50e-6


# ------------------------------------------------------------------ (a)
def ina_chain(I, duty, f, ncyc=40, dt=5e-9):
    """Time-domain INA186 (1st-order 35 kHz, slew-limited, rail-clipped)
    into the 1.5k/1k + 100 nF filter.  Returns t, ideal IOUT, IOUT, ISENSE."""
    T = 1 / f
    t = np.arange(0, ncyc * T, dt)
    vin = np.where((t % T) < duty * T, I * RSH * G, 0.0)
    tau = 1 / (2 * np.pi * BW)
    v = np.zeros_like(t)
    vs = np.zeros_like(t)
    rth, cf = 600.0, 100e-9
    for k in range(1, len(t)):
        target = min(max(vin[k], 0.0), VS - 0.1)
        dv = (target - v[k - 1]) / tau
        dv = max(min(dv, SR), -SR)
        v[k] = v[k - 1] + dv * dt
        vs[k] = vs[k - 1] + ((v[k] * 0.4) - vs[k - 1]) / (rth * cf) * dt
    return t, vin, v, vs


def part_a(lines):
    lines.append('(a) Current sense')
    gain_isense = 50e-3 * 1.0 / 2.5
    lines.append('  ISENSE gain: 0.5 mOhm x 100 = 50 mV/A at IOUT, x 1k/(1.5k + 1k) = %.1f mV/A at PA5 '
                 '(AM32 GEN_64K_G071 MILLIVOLT_PER_AMP 20).' % (gain_isense * 1e3))
    rth = 1.5e3 * 1e3 / 2.5e3
    lines.append('  Filter: Thevenin 1.5k || 1k = %.0f ohm with 100 nF -> fc = %.2f kHz '
                 '(circuit.py says 1.0 kHz: that is 1.5k x 100 nF alone).' % (rth, 1 / (2 * np.pi * rth * 100e-9) / 1e3))
    lines.append('  Full scale: IOUT swings to ~VS - 0.1 V = 3.2 V at the ~1.6 mA the 2.5k + 10k loads draw '
                 '-> %.0f A instantaneous; PA5 then reads %.2f V (ADC never clips).' % (3.2 / 0.05, 3.2 * 0.4))
    lines.append('  1 LSB (12 bit, 3.3 V) = %.2f mV = %.3f A.' % (3.3 / 4096 * 1e3, 3.3 / 4096 / gain_isense))
    # error budget
    off = VOS / RSH
    drift = 0.5e-6 * 75 / RSH
    rows = [['INA186 VOS (50 uV max)', '%.2f A' % off, ''],
            ['VOS drift 0.5 uV/C x 75 C', '%.3f A' % drift, ''],
            ['INA186 gain error', '', '1.0 %'],
            ['gain drift 10 ppm/C x 75 C', '', '0.075 %'],
            ['shunt tolerance', '', '1.0 %'],
            ['shunt TCR 200 ppm/C x 75 C (HCS1206 0.5 mOhm)', '', '1.5 %'],
            ['1.5k / 1k ratio, 1 % parts (0.6 x 2 %)', '', '1.2 %']]
    lines.append(S.table(rows, ['error source', 'offset', 'gain']))
    lines.append('  Worst-case sum: offset %.2f A, gain %.1f %%; RSS gain %.1f %%.  At 15 A: +-%.2f A worst.' % (
        off + drift, 1 + 0.075 + 1 + 1.5 + 1.2, np.sqrt(1 + 0.075 ** 2 + 1 + 1.5 ** 2 + 1.2 ** 2),
        off + drift + 15 * (1 + 0.075 + 1 + 1.5 + 1.2) / 100))
    lines.append('  Negative (regenerative) current reads 0: REF = GND, unidirectional.')
    # pulse response: average reading vs duty
    res = []
    for f in (24e3, 48e3):
        for I in (5, 15, 30):
            for duty in (0.05, 0.1, 0.25, 0.5, 0.9):
                t, vin, v, vs = ina_chain(I, duty, f)
                m = t > t[-1] - 10 / f
                true = I * duty * 20e-3
                rd = np.mean(vs[m])
                res.append((f, I, duty, true, rd, (rd / true - 1) * 100, vs[m].max() - vs[m].min()))
    lines.append('  PWM pulse train through the INA186 (slew 0.3 V/us, 35 kHz) and filter: average at PA5 vs ideal:')
    lines.append(S.table([[int(r[0] / 1e3), r[1], '%d %%' % (r[2] * 100), r[3] * 1e3, r[4] * 1e3, r[5], r[6] * 1e3]
                          for r in res],
                         ['PWM kHz', 'I A', 'duty', 'ideal mV', 'reading mV', 'error %', 'ripple mV p-p']))
    # battery current average
    g_cur = (1 / 10e3) / (4 / 10e3 + 1 / 62e3) * 50e-3
    rth_c = 1 / (4 / 10e3 + 1 / 62e3)
    lines.append('  CUR (FC PB1): 0.25 x 62k / (62k + 2.5k) x 50 mV/A = %.2f mV/A of total battery current '
                 '(ibata_scale 120); Thevenin %.0f ohm x 100 nF -> fc %.0f Hz.' % (
                     g_cur * 1e3, rth_c, 1 / (2 * np.pi * rth_c * 100e-9)))
    # CUR ripple: four channels in phase, 15 A at 50 %, 24 kHz, through the INA model
    out = {}
    for f in (24e3, 48e3):
        t, vin, v, vs = ina_chain(15, 0.5, f, ncyc=60)
        cur = np.zeros_like(t)
        dt = t[1] - t[0]
        for k in range(1, len(t)):
            cur[k] = cur[k - 1] + ((4 * v[k] * g_cur / 50e-3) - cur[k - 1]) / (rth_c * 100e-9) * dt
        m = t > t[-1] - 10 / f
        out[f] = (t, vin, v, vs, cur)
        lines.append('  CUR ripple, 4 x 15 A at 50 %%, %d kHz, in phase: %.2f mV p-p (= %.2f A), mean %.1f mV '
                     '(ideal %.1f mV)' % (f / 1e3, (cur[m].max() - cur[m].min()) * 1e3,
                                          (cur[m].max() - cur[m].min()) / g_cur, cur[m].mean() * 1e3, 30 * g_cur * 1e3))
    return res, out


# ------------------------------------------------------------------ (b)
def network(vph, r=None):
    """Node voltages CMP_A, CMP_B, CMP_C, NEUTRAL for phase voltages vph
    (shape (3, N)).  r = dict of resistor arrays (top, bottom, star)."""
    if r is None:
        r = dict(top=np.full(3, 10e3), bot=np.full(3, 2.2e3), star=np.full(3, 10e3))
    gt, gb, gs = 1 / r['top'], 1 / r['bot'], 1 / r['star']
    Y = np.zeros((4, 4))
    for k in range(3):
        Y[k, k] = gt[k] + gb[k] + gs[k]
        Y[k, 3] = Y[3, k] = -gs[k]
    Y[3, 3] = gs.sum()
    b = np.zeros((4, vph.shape[1]))
    for k in range(3):
        b[k] = gt[k] * vph[k]
    return np.linalg.solve(Y, b)


def trap(theta):
    """Unit trapezoidal back-EMF (flat +-1 for 120 deg, 60-deg ramps)."""
    th = np.mod(theta, 360.0)
    return np.interp(th, [0, 30, 150, 210, 330, 360], [0, 1, 1, -1, -1, 0])


def motor(theta, E, vbat, duty, fpwm, erpm, R=0.1, I=0.0):
    """Terminal voltages for 6-step with complementary PWM on the high phase.
    theta in electrical degrees (array).  Sector k (0-5): high/low/float
    phases from the standard table; PWM state from the time axis."""
    e = np.array([E * trap(theta), E * trap(theta - 120), E * trap(theta - 240)])
    # sector boundaries centred on the BEMF flats: high phase = the one at +E
    table = [(0, 1, 2), (0, 2, 1), (1, 2, 0), (1, 0, 2), (2, 0, 1), (2, 1, 0)]
    sec = (np.floor(np.mod(theta - 30, 360) / 60)).astype(int)
    t = theta / 360.0 / (erpm / 60.0)
    pwm_on = np.mod(t * fpwm, 1.0) < duty
    v = np.zeros_like(e)
    for k in range(len(theta)):
        hi, lo, fl = table[sec[k]]
        vh = vbat if pwm_on[k] else 0.0
        v[hi, k], v[lo, k] = vh, 0.0
        vn = (vh + 0.0) / 2 - (e[hi, k] + e[lo, k]) / 2
        v[fl, k] = min(max(vn + e[fl, k], -0.8), vbat + 0.8)
    return v, e, sec, pwm_on


def part_b(lines):
    lines.append('\n(b) Back-EMF network')
    # effective ratios
    one = network(np.array([[1.0], [0.0], [0.0]]))
    allp = network(np.array([[1.0], [1.0], [1.0]]))
    lines.append('  One phase moving, others at 0: CMP gain %.4f (1/%.3f); NEUTRAL gain %.4f.' % (
        one[0, 0], 1 / one[0, 0], one[3, 0]))
    lines.append('  All three together: CMP gain %.4f (1/%.3f) - the unloaded 2.2/(10 + 2.2) divider.' % (
        allp[0, 0], 1 / allp[0, 0]))
    lines.append('  CMP_x - NEUTRAL = (V_x - mean of the three phases) / 6.545 (one phase moving: %.4f = (2/3)/%.3f).  '
                 'Equivalently, with NEUTRAL held, each phase sees (10k || 2.2k) / (10k + 10k || 2.2k) = 1/%.3f.' % (
                     one[0, 0] - one[3, 0], (2 / 3) / (one[0, 0] - one[3, 0]), 1 + 10 / (1 / (1 / 10 + 1 / 2.2))))
    vbat = 17.4
    erpm = 60000.0
    fpwm = 48e3
    cases = {}
    for name, duty, E in (('mid throttle (50 %)', 0.5, 0.5 * vbat / 2 * 0.95), ('full throttle (98 %)', 0.98, 0.98 * vbat / 2 * 0.93)):
        theta = np.linspace(0, 360, 36001)
        v, e, sec, on = motor(theta, E, vbat, duty, fpwm, erpm)
        n = network(v)
        cases[name] = (theta, v, e, sec, on, n)
        # zero-crossing check: phase A floats in sectors 2 (150-210 deg, crossing at 180)
        # and 5 (330-30 deg, crossing at 0); compare the sign change of
        # CMP_A - NEUTRAL, sampled only while the PWM is on, with the true one
        d = n[0] - n[3]
        errs = []
        for s_, zc in ((2, 180.0), (5, 0.0)):
            idx = np.where((sec == s_) & on)[0]
            th = np.mod(theta[idx] - zc + 180.0, 360.0) - 180.0       # angle relative to the true crossing
            o = np.argsort(th)
            th, dd = th[o], d[idx][o]
            j = np.where(np.sign(dd[:-1]) != np.sign(dd[1:]))[0]
            if len(j):
                k = j[0]
                z = th[k] - dd[k] * (th[k + 1] - th[k]) / (dd[k + 1] - dd[k])
                errs.append(abs(z))
        lines.append('  %s, %d eRPM, %g kHz PWM: CMP max %.2f V, NEUTRAL %.2f..%.2f V, CMP min %.2f V; '
                     'zero-crossing error (PWM-on samples) <= %.2f el. deg (ideal resistors)' % (
                         name, erpm, fpwm / 1e3, n[:3].max(), n[3].min(), n[3].max(), n[:3].min(),
                         max(errs) if errs else float('nan')))
    # worst-case voltages
    vmax = network(np.array([[vbat + 0.8], [vbat], [0.0]]))
    vall = network(np.array([[vbat + 0.8], [vbat + 0.8], [vbat + 0.8]]))
    lines.append('  Static worst: one phase at VBAT + 0.8 V (body diode), one at VBAT: CMP %.2f V.  '
                 'All three at VBAT + 0.8 V (all high sides off, coasting at full speed): CMP %.2f V.' % (
                     vmax[0, 0], vall[0, 0]))
    lines.append('  Limits: VDDA 3.3 V + 0.3 V = 3.6 V for a valid comparison; FT_a pin absolute max VDD + 4 V = 7.3 V.')
    for vs_, lab in ((24.0, 'snubbed switch-node overshoot'), (41.0, 'as-drawn overshoot at 15 A'),
                     (35.5, 'VBAT at the TVS clamp')):
        lines.append('  Transient: phase at %.1f V (%s) -> CMP %.2f V (one phase), %.2f V (all three).' % (
            vs_, lab, network(np.array([[vs_], [0.0], [0.0]]))[0, 0], vs_ / 5.545))
    # Monte Carlo zero-crossing error with 1 % resistors
    rng = np.random.default_rng(1)
    worst = []
    for _ in range(2000):
        r = dict(top=10e3 * (1 + rng.uniform(-0.01, 0.01, 3)), bot=2.2e3 * (1 + rng.uniform(-0.01, 0.01, 3)),
                 star=10e3 * (1 + rng.uniform(-0.01, 0.01, 3)))
        # floating phase A, high B (PWM on, VBAT), low C: comparator offset referred to back-EMF
        vh = vbat
        def diff(ef):
            vn = vh / 2
            return network(np.array([[vn + ef], [vh], [0.0]]), r)
        d0 = diff(0.0)
        d1 = diff(1.0)
        g = (d1[0, 0] - d1[3, 0]) - (d0[0, 0] - d0[3, 0])
        worst.append(abs((d0[0, 0] - d0[3, 0]) / g))
    worst = np.array(worst)
    lines.append('  1 %% resistors (Monte Carlo, 2000 boards): comparator offset referred to the floating '
                 'phase back-EMF: %.0f mV typ (median), %.0f mV at 99 %%, %.0f mV max (at VBAT 17.4 V, PWM on).' % (
                     np.median(worst) * 1e3, np.percentile(worst, 99) * 1e3, worst.max() * 1e3))
    for E, lab in ((0.5, 'startup, E = 0.5 V'), (2.0, 'E = 2 V'), (8.0, 'full speed, E = 8 V')):
        slope = 2 * E / 60.0       # V per electrical degree on the 60-degree ramp
        lines.append('    -> zero-crossing shift at %s: %.1f el. deg typ, %.1f el. deg at 99 %%' % (
            lab, np.median(worst) / slope, np.percentile(worst, 99) / slope))
    return cases


# ------------------------------------------------------------------ (c)
def part_c(lines):
    lines.append('\n(c) Battery-voltage dividers')
    rows = []
    for name, rt, rb, cap in (('FC 10k / 1k (PB2)', 10e3, 1e3, 100e-9), ('ESC 100k / 10k (PA6)', 100e3, 10e3, 0.0)):
        ratio = (rt + rb) / rb
        worst = (rt * 1.01 + rb * 0.99) / (rb * 0.99), (rt * 0.99 + rb * 1.01) / (rb * 1.01)
        rth = rt * rb / (rt + rb)
        rows.append([name, ratio, ratio * 10, 17.4 / ratio, 3.3 * ratio,
                     '%+.1f / %+.1f %%' % ((worst[0] / ratio - 1) * 100, (worst[1] / ratio - 1) * 100),
                     rth, ('%.0f us' % (rth * cap * 1e6)) if cap else 'none', 35.5 / ratio])
    lines.append(S.table(rows, ['divider', 'ratio', 'scale', 'V at 17.4 V', 'full scale V', 'tolerance (1 %)',
                                'source ohm', 'filter tau', 'V at 35.5 V']))
    lines.append('  STM32G071 12-bit ADC max source resistance (DS12232 Table 57): 8.2k at 19.5 cycles, '
                 '15k at 39.5 cycles.  The ESC divider is 9.1k with no capacitor: it needs >= 39.5-cycle sampling, '
                 'or a 10-100 nF capacitor at PA6 (then any sampling time works).')


def main():
    lines = []
    res, out = part_a(lines)
    cases = part_b(lines)
    part_c(lines)
    txt = '\n'.join(lines)
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)

    plt = S.style()
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    a = ax[0]
    t, vin, v, vs, cur = out[24e3]
    m = t > t[-1] - 4 / 24e3
    tt = (t[m] - t[m][0]) * 1e6
    a.plot(tt, vin[m], lw=0.8, label='ideal IOUT (15 A pulses, 50 %)')
    a.plot(tt, v[m], label='INA186 IOUT (35 kHz, 0.3 V/us)')
    a.plot(tt, vs[m], label='PA5 (after 1.5k/1k + 100 nF)')
    a.plot(tt, cur[m], label='CUR at PB1 (4 channels in phase)')
    a.set_xlabel('us'); a.set_ylabel('V'); a.legend(fontsize=7); a.set_title('current sense, 24 kHz')
    a = ax[1]
    rr = np.array(res)
    for f, ls in ((24e3, '-'), (48e3, '--')):
        for I, c in ((5, 'C0'), (15, 'C1'), (30, 'C3')):
            mm = (rr[:, 0] == f) & (rr[:, 1] == I)
            a.plot(rr[mm, 2] * 100, rr[mm, 5], c, ls=ls, marker='o', ms=3, label='%d A, %d kHz' % (I, f / 1e3))
    a.axhline(0, color='0.5', lw=0.6)
    a.set_xlabel('PWM duty (%)'); a.set_ylabel('average reading error (%)'); a.legend(fontsize=6, ncol=2)
    a.set_title('INA186 slew/bandwidth error on the PWM pulse train')
    a = ax[2]
    vb = np.linspace(0, 40, 100)
    a.plot(vb, vb / 11, label='FC PB2 and ESC PA6 (ratio 11)')
    a.axhline(3.3, color='C3', lw=0.8, label='3.3 V ADC full scale')
    a.axvline(17.4, color='0.6', lw=0.6); a.axvline(35.5, color='0.6', lw=0.6, ls=':')
    a.text(17.6, 0.3, '4S HV', fontsize=7); a.text(35.7, 0.3, 'TVS clamp', fontsize=7)
    a.set_xlabel('VBAT (V)'); a.set_ylabel('ADC pin (V)'); a.legend(fontsize=7); a.set_title('battery-voltage dividers')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'sense.png'))

    fig, ax = plt.subplots(2, 2, figsize=(14, 7.5), sharex=True)
    for col, (name, (theta, v, e, sec, on, n)) in enumerate(cases.items()):
        a = ax[0, col]
        for k, ph in enumerate('ABC'):
            a.plot(theta, v[k], lw=0.5, label='phase %s terminal' % ph)
        a.plot(theta, e[0], 'k', lw=1, label='back-EMF A')
        a.set_ylabel('V'); a.set_title('%s: phase voltages' % name); a.legend(fontsize=6, ncol=2)
        a = ax[1, col]
        for k, ph in enumerate('ABC'):
            a.plot(theta, n[k], lw=0.5, label='CMP_%s' % ph)
        a.plot(theta, n[3], 'k', lw=0.8, label='NEUTRAL (PA3)')
        # floating-phase A comparator, PWM-on samples only
        fl = np.array([[(0, 1, 2), (0, 2, 1), (1, 2, 0), (1, 0, 2), (2, 0, 1), (2, 1, 0)][s][2] == 0 for s in sec])
        mm = fl & on
        a.plot(theta[mm], (n[0] - n[3])[mm], '.', ms=1, color='C4', label='CMP_A - NEUTRAL (A floating, PWM on)')
        for z in (0, 180):
            a.axvline(z, color='C3', lw=0.6, ls=':')
        a.axhline(3.6, color='C3', lw=0.8)
        a.text(2, 3.65, 'VDDA + 0.3 V', color='C3', fontsize=7)
        a.set_xlabel('electrical degrees'); a.set_ylabel('V'); a.legend(fontsize=6, ncol=2)
        a.set_title('comparator inputs (red dotted: true back-EMF zero crossings of A)')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'bemf.png'))


if __name__ == '__main__':
    main()
