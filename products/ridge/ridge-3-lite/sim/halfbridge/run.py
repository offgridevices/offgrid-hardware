# -*- coding: utf-8 -*-
"""Study 1: one phase leg switching (DRV8300D + 2 x TPN2R304PL).

What is modelled (one leg of one ESC, the high side PWM'd with the phase
current flowing out of the switch node, AM32 complementary PWM):

  supply   17.4 V (4S HV full) through 10 nH / 10 mOhm to the board's VBAT
           plane, 470 uF electrolytic (40 mOhm, 7 nH + 8 nH of pad/trace).
  caps     this leg's 4.7 uF 50 V X7R 0805 (1.75 uF left at 17 V, 4 mOhm,
           0.4 nH ESL) in the switching loop; the ESC's other two bridge
           caps (2 x 1.75 uF) 1 nH further away.  Caps return to SRC (the
           bridge side of the shunt), as circuit.py wires them.
  loop     L_loop (swept 1 / 2 / 4 nH) of PCB in the commutation loop, half
           at the high-side drain and half at the low-side source, plus
           the FET package (0.15 nH drain, 0.25 nH source each).
  shunt    0.5 mOhm + 0.3 nH, SRC to GND.  The DRV8300 low-side driver is
           referenced to GND, so the low-side gate loop returns through
           half of L_loop and the shunt.
  driver   DRV8300D output stage from SLVSFG5D 7.5: pull-up limited to
           0.75 A peak and 0.6 V drop at 100 mA (6 ohm), pull-down 1.5 A
           peak and 0.15 V at 100 mA (1.5 ohm), modelled as tanh-limited
           current sources; bootstrap diode 0.7 V at 100 uA and 15 ohm
           dynamic resistance (2.3 V at 100 mA); bootstrap cap 1 uF 25 V
           0402 X5R as 0.4 uF at 11 V; GVDD 11 V with 4 uF local.
  gate     R_ext (circuit.py: 4.7 ohm, swept 0 / 2.2 / 4.7 / 10 / 22; and
           asymmetric high/low values in options.py) + 3 nH of gate trace +
           the FET's internal rg 0.7 ohm.  The loss table uses the
           recommended 22 ohm high side / 10 ohm low side (GATE below).
  timing   AM32 DEAD_TIME 60 at 64 MHz = 0.94 us, plus the DRV8300's own
           215 ns = 1.155 us between one gate going low and the other going
           high (the brief's assumption; it is the conservative reading for
           dead-time loss).
  load     an ideal current source (15 or 30 A) from the switch node back
           to SRC: the motor winding plus the other phase's low side.
           Negative values (options.py) are braking: current into the
           switch node, so the low side hard-switches at its turn-on.

FET: ../models/tpn2r304pl.lib (fitted to the datasheet, see fet_model/).

Outputs: halfbridge.png, rg_sweep.png, loop_sweep.png, losses.png,
results.txt and ../losses.csv (per motor, for the thermal model).
Run: python3 run.py, then python3 options.py (the damping options study).
"""
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = S.scratch('halfbridge')
LIB = os.path.join(S.MODELS, 'tpn2r304pl.lib')

VBUS = 17.4
GVDD = 11.0
DEAD = 0.94e-6 + 0.215e-6
T_LOFF = 0.3e-6                 # low side commanded off
T_HON = T_LOFF + DEAD           # high side commanded on
TON = 1.5e-6
T_HOFF = T_HON + TON
T_LON = T_HOFF + DEAD
T_END = T_LON + 0.4e-6
TR = 5e-9                       # logic edge at the driver's output stage


def netlist(I=15.0, rg=4.7, lloop=2e-9, temp=25, name='hb', tt=1.5e-9, snub=None):
    # temp 151 = a minimum-Vth part at 150 C (fet_model: TPN2R304PL_150Cmin)
    fet = 'TPN2R304PL_150Cmin' if temp == 151 else 'TPN2R304PL_%dC' % temp
    tsim = 150 if temp == 151 else temp
    ch = 'pwl(0 0 %g 0 %g 1 %g 1 %g 0)' % (T_HON, T_HON + TR, T_HOFF, T_HOFF + TR)
    cl = 'pwl(0 1 %g 1 %g 0 %g 0 %g 1)' % (T_LOFF, T_LOFF + TR, T_LON, T_LON + TR)
    rgh, rgl = rg if isinstance(rg, tuple) else (rg, rg)
    rghx, rglx = max(rgh, 1e-3), max(rgl, 1e-3)
    return f"""* half bridge leg: I={I} A, Rg={rg} ohm, Lloop={lloop*1e9:g} nH, Tj={temp} C
.include {LIB}
.model DBST D (is=1.2e-10 n=2 rs=15 cjo=20p)
* supply, electrolytic, plane
VBAT vsrc 0 {VBUS}
Rfeed vsrc vf1 10m
Lfeed vf1 vp 10n
Lel vp el1 15n
Rel el1 el2 40m
Cel el2 0 470u
* other two bridge caps of this ESC
Lc2 vp c2a 1n
Rc2 c2a c2b 2m
Lc2e c2b c2c 0.2n
Cc2 c2c srcn 3.5u
* this leg's cap (in the switching loop)
Rc1 vp c1a 4m
Lc1 c1a c1b 0.4n
Cc1 c1b srcn 1.75u
* commutation loop and FETs
Lp1 vp dh0 {lloop/2:g}
Vih dh0 dh 0
XH dh gh sw {fet} RG=0.7 TT={tt:g}
Vil sw dl 0
XL dl gl sl {fet} RG=0.7 TT={tt:g}
Lp2 sl srcn {lloop/2:g}
{snubber(snub)}
* shunt to ground
Rsh srcn sh1 0.5m
Lsh sh1 0 0.3n
* load: motor current out of the switch node, back to SRC
Iload sw srcn {I}
* gate drive supply and bootstrap
VGV gv0 0 {GVDD}
Rgv gv0 gvdd 0.2
Cgv gvdd 0 4u
Dbst gvdd bst DBST
Cbst bst sw 0.4u
* DRV8300 outputs: tanh-limited source/sink, 50 pF on each pin
Vch ch 0 {ch}
Vcl cl 0 {cl}
Bhu bst ghd I = V(ch) * 0.75 * tanh(V(bst,ghd) / 4.5)
Bhd ghd sw  I = (1 - V(ch)) * 1.5 * tanh(V(ghd,sw) / 2.25)
Chd ghd sw 50p
Blu gvdd gld I = V(cl) * 0.75 * tanh(V(gvdd,gld) / 4.5)
Bld gld 0   I = (1 - V(cl)) * 1.5 * tanh(V(gld) / 2.25)
Cld gld 0 50p
* gate resistors and traces
Rgh ghd gh1 {rghx}
Lgh gh1 gh 3n
Rgl gld gl1 {rglx}
Lgl gl1 gl 3n
.ic v(bst)=10.3 v(gld)=11 v(gl)=11
.options reltol=1e-4 abstol=1e-9 vntol=1e-5 itl4=200 rshunt=1e9
.temp {tsim}
.control
tran 0.05n {T_END:g} 0 0.25n
{S.control_save(['v(sw)', 'v(dh)', 'v(srcn)', 'v(xh.di)', 'v(xh.si)', 'v(xh.gi)', 'v(xl.di)', 'v(xl.si)', 'v(xl.gi)', 'v(ghd)', 'v(gld)', 'v(bst)', 'v(vp)', 'i(vih)', 'i(vil)'], name + '.dat')}
.endc
.end
"""


def snubber(snub):
    """Optional damping parts.  Old form (R, C[, 'low'|'high'|'both']): RC
    snubber across a FET at its pins (0.3 nH of ESL).  New form: a tuple of
    items, each one of
      ('low', R, C)  RC from the switch node to the low-side source pin
      ('dc', R, C)   RC damper VBAT to SRC where the bridge cap sits:
                     0.4 nH ESL + 0.6 nH for two 0.5 mm vias
      ('cgsl', C)    capacitor across the low side's gate and source pins
    """
    if not snub:
        return ''
    if not isinstance(snub[0], tuple):
        R, C = snub[:2]
        where = snub[2] if len(snub) > 2 else 'both'
        hs = f'Rsn1 dh sn1 {R:g}\nLsn1 sn1 sn2 0.3n\nCsn1 sn2 sw {C:g}\n'
        ls = f'Rsn2 sw sn3 {R:g}\nLsn2 sn3 sn4 0.3n\nCsn2 sn4 sl {C:g}'
        return {'both': hs + ls, 'low': ls, 'high': hs}[where]
    out = []
    for k, it in enumerate(snub):
        if it[0] == 'low':
            out.append(f'Rx{k} sw x{k}a {it[1]:g}\nLx{k} x{k}a x{k}b 0.3n\nCx{k} x{k}b sl {it[2]:g}')
        elif it[0] == 'dc':
            out.append(f'Rx{k} vp x{k}a {it[1]:g}\nLx{k} x{k}a x{k}b 1.0n\nCx{k} x{k}b srcn {it[2]:g}')
        elif it[0] == 'cgsl':
            out.append(f'Lx{k} gl x{k}a 0.3n\nCx{k} x{k}a sl {it[1]:g}')
        else:
            raise ValueError(it)
    return '\n'.join(out)


def tag(rg, snub):
    """File-name tag for a gate-resistor / damping configuration."""
    t = ('rg%g-%g' % rg) if isinstance(rg, tuple) else 'rg%g' % rg
    if snub and isinstance(snub[0], tuple):
        t += '_' + '_'.join(it[0] + '-'.join('%g' % (v * 1e9 if v < 1e-6 else v) for v in it[1:]) for it in snub)
    elif snub:
        t += '_sn%g_%g%s' % (snub[0], snub[1] * 1e9, snub[2] if len(snub) > 2 else '')
    return t


def simulate(args):
    I, rg, lloop, temp = args[:4]
    tt = args[4] if len(args) > 4 else 1.5e-9
    snub = args[5] if len(args) > 5 else None
    if isinstance(rg, tuple) or (snub and isinstance(snub[0], tuple)):
        name = 'hb_I%g_L%g_T%d_tt%g_%s' % (I, lloop * 1e9, temp, tt * 1e9, tag(rg, snub))
    else:
        name = 'hb_I%g_rg%g_L%g_T%d_tt%g' % (I, rg, lloop * 1e9, temp, tt * 1e9)
        if snub:
            name += '_sn%g_%g%s' % (snub[0], snub[1] * 1e9, snub[2] if len(snub) > 2 else '')
    path = os.path.join(OUT, name + '.dat')
    base = netlist(I, rg, lloop, temp, name, tt, snub)
    stamp = os.path.join(OUT, name + '.base')
    fresh = (os.path.exists(path) and os.path.exists(stamp) and open(stamp).read() == base
             and os.path.getmtime(LIB) < os.path.getmtime(path))
    if not fresh:
        # ngspice's timestep control occasionally gives up on an edge; the
        # same circuit with slightly different tolerances or maximum step
        # then runs.  The ladder is fixed, so results are reproducible.
        ladder = [('', ''), ('reltol=1e-4', 'reltol=1e-3'), ('0 0.25n\n', '0 0.1n\n'),
                  ('abstol=1e-9', 'abstol=1e-6'), ('0 0.25n\n', '0 0.15n\n')]
        for k, (a, b) in enumerate(ladder):
            try:
                S.ngspice(base.replace(a, b) if a else base, OUT, name, timeout=1800)
                break
            except RuntimeError:
                if k == len(ladder) - 1:
                    raise
        with open(stamp, 'w') as f:
            f.write(base)
    d = S.wrdata(path)
    return args, analyze(d, I)


def analyze(d, I):
    t = d['time']
    vds_h = d['v(xh.di)'] - d['v(xh.si)']
    vds_l = d['v(xl.di)'] - d['v(xl.si)']
    vgs_h = d['v(xh.gi)'] - d['v(xh.si)']
    vgs_l = d['v(xl.gi)'] - d['v(xl.si)']
    ih, il = d['i(vih)'], d['i(vil)']
    sw = d['v(sw)']
    ph, pl = vds_h * ih, vds_l * il
    p = ph + pl
    r = {}

    def win(a, b):
        return (t >= a) & (t <= b)

    # ---- high-side turn-on (sw rises; low-side body diode recovers)
    w = win(T_HON, T_HON + 700e-9)
    tw, sww = t[w], sw[w]
    lo, hi = -0.5, VBUS
    t10 = tw[np.argmax(sww > lo + 0.1 * (hi - lo))]
    t90 = tw[np.argmax(sww > lo + 0.9 * (hi - lo))]
    r['dvdt_rise'] = 0.8 * (hi - lo) / (t90 - t10) / 1e9          # V/ns, 10-90 %
    ok = np.diff(tw) > 0
    dv = np.diff(sww)[ok] / np.diff(tw)[ok]
    r['dvdt_rise_pk'] = float(np.max(dv)) / 1e9
    r['vds_l_pk'] = float(np.max(vds_l[w]))                        # low-side overshoot
    r['vgs_l_bump'] = float(np.max(vgs_l[w]))                      # Miller bump on the off low side
    r['vgs_l_min_on'] = float(np.min(vgs_l[w]))
    r['gld_min'] = float(np.min(d['v(gld)'][win(T_LOFF, T_END)]))  # GLx pin vs GND
    r['vgs_h_pk'] = float(np.max(vgs_h[w]))                        # high-side gate overshoot
    r['ih_pk'] = float(np.max(ih[w]))                              # incl. reverse recovery
    r['t_rise'] = t90 - t10
    # ---- high-side turn-off (sw falls; current to the low-side diode)
    w2 = win(T_HOFF, T_HOFF + 700e-9)
    tw2, sw2 = t[w2], sw[w2]
    t90f = tw2[np.argmax(sw2 < lo + 0.9 * (hi - lo))]
    t10f = tw2[np.argmax(sw2 < lo + 0.1 * (hi - lo))]
    r['dvdt_fall'] = 0.8 * (hi - lo) / max(t10f - t90f, 1e-12) / 1e9
    ok2 = np.diff(tw2) > 0
    r['dvdt_fall_pk'] = float(-np.min(np.diff(sw2)[ok2] / np.diff(tw2)[ok2])) / 1e9
    r['vds_h_pk'] = float(np.max(vds_h[w2]))                       # high-side overshoot
    r['vgs_l_bump_off'] = float(np.max(vgs_l[w2]))                 # low side, sw falling (negative dv/dt)
    r['vgs_l_min_off'] = float(np.min(vgs_l[w2]))
    r['vgs_h_min'] = float(np.min(vgs_h[win(T_HOFF, T_LON)]))
    r['gh_sh_min'] = float(np.min((d['v(ghd)'] - sw)[win(T_HOFF, T_LON)]))
    r['sw_min'] = float(np.min(sw))
    r['vds_l_pk_all'] = float(np.max(vds_l))
    r['vds_h_pk_all'] = float(np.max(vds_h))
    r['vp_pk'] = float(np.max(d['v(vp)']))
    # ---- low-side turn-on: hard-switched when the phase current is negative
    # (braking / regen: current into the switch node, high-side diode conducting)
    w3 = win(T_LON, T_END)
    r['vds_h_pk_lon'] = float(np.max(vds_h[w3]))
    r['vgs_h_bump_lon'] = float(np.max(vgs_h[w3]))
    r['gh_sh_min_lon'] = float(np.min((d['v(ghd)'] - sw)[w3]))
    tw3, sw3 = t[w3], sw[w3]
    hi3 = VBUS + 0.5
    if sw3[0] > 0.9 * hi3:
        a90 = tw3[np.argmax(sw3 < 0.9 * hi3)]
        a10 = tw3[np.argmax(sw3 < 0.1 * hi3)]
        r['dvdt_lon'] = 0.8 * hi3 / max(a10 - a90, 1e-12) / 1e9
    else:
        r['dvdt_lon'] = 0.0
    # ---- switching energy: die power in a window around each edge, minus
    # the conduction that would flow anyway (diode before / channel after)
    def esw(a, b, rising):
        m = win(a, b)
        tt, pp = t[m], p[m]
        e = np.trapezoid(pp, tt)
        # baseline: mean power in the 20 ns before a and the last 20 ns of the window
        pre = np.mean(p[win(a - 25e-9, a - 5e-9)])
        post = np.mean(p[win(b - 20e-9, b)])
        if rising:
            tm = tt[np.argmax(sw[m] > VBUS / 2)]
        else:
            tm = tt[np.argmax(sw[m] < VBUS / 2)]
        base = pre * (tm - a) + post * (b - tm)
        return e - base
    r['eon'] = esw(T_HON, T_HON + 700e-9, True)
    r['eoff'] = esw(T_HOFF, T_HOFF + 700e-9, False)
    # braking (I < 0): the hard edge is the low side's turn-on (sw falls, the
    # high side's diode recovers); its energy and the high side's peak
    # forward current (Coss charge + any Miller-induced shoot-through)
    if I < 0:
        r['elon'] = esw(T_LON, T_END - 5e-9, False)
        r['ih_pk_lon'] = float(np.max(ih[win(T_LON, T_END)]))
    else:
        r['elon'] = 0.0
        r['ih_pk_lon'] = 0.0
    # diode conduction voltage during dead time (for the loss model)
    wd = win(T_LOFF + 300e-9, T_HON)
    r['vf_dead'] = float(-np.mean(sw[wd]))
    # the arrays, for plots
    r['_t'] = t; r['_sw'] = sw; r['_vgs_h'] = vgs_h; r['_vgs_l'] = vgs_l
    r['_vds_h'] = vds_h; r['_vds_l'] = vds_l; r['_ih'] = ih; r['_il'] = il
    return r


# ---------------------------------------------------------------- losses
RDS_MAX = 2.3e-3
RDS_FACTOR = {25: 1.0, 100: 1.35, 150: 1.70}     # Fig 8.9


def vf_diode(I, temp):
    """Body-diode forward voltage (Fig 8.6 fit: 0.69 V at 1 A, 74 mV/decade,
    0.5 mOhm), less 2 mV/C above 25 C."""
    I = np.maximum(I, 1e-3)
    return 0.69 + 0.032 * np.log(I) * 1.0 + 0.5e-3 * I - 0.002 * (temp - 25)


def loss_table(E, fpwm_list=(24e3, 48e3), temps=(25, 100, 150)):
    """Per motor, 6-step trapezoidal, complementary PWM, worst case of PWM
    at every cycle (as at part throttle).  At any time one phase is PWM'd
    (high side hard-switched, low side synchronous), one phase's low side
    is on for the whole 60 degree sector, and one floats.  Phase current I
    flows through two FETs at all times:

      Pcond = I^2 RDS (2 - 2 tdead f)   (high/low of the PWM leg + the static low side)
      Pdead = Vf(I) I 2 tdead f          (low-side body diode, both dead times)
      Psw   = (Eon(I) + Eoff(I)) f       (from the simulation, incl. Qrr and Coss)
      Pshunt = I^2 0.5 mOhm D            (shunt carries the current only while the high side is on;
                                          D = 1 taken, worst case)
      Psnub = C VBUS^2 f                 (recommended sw-to-SRC RC snubber, if fitted: its resistor
                                          takes C V^2 per PWM cycle on the PWM'd leg)
    RDS is the datasheet maximum (2.3 mOhm at 25 C) x the Fig 8.9 factor."""
    rows = []
    Is = np.arange(0, 31, 1.0)
    for f in fpwm_list:
        for T in temps:
            R = RDS_MAX * RDS_FACTOR[T]
            Ii, eon, eoff = E[T]
            for I in Is:
                pc = I ** 2 * R * (2 - 2 * DEAD * f)
                pd = vf_diode(I, T) * I * 2 * DEAD * f if I > 0 else 0.0
                ps = (np.interp(I, Ii, eon) + np.interp(I, Ii, eoff)) * f
                psh = I ** 2 * 0.5e-3
                psn = 0.0                       # no snubber in the recommended configuration
                rows.append((f, T, I, pc, ps, pd, pc + ps + pd, psh, psn, pc + ps + pd + psh + psn))
    return rows


SNUB = (1.0, 4.7e-9, 'low')     # the switch-node snubber tried first (see options.py)
GATE = (22, 10)                 # recommended gate resistors (high, low), options.py; no snubber
TT0 = 1.5e-9


def key(I, rg, L, T, tt=TT0, snub=None):
    return (I, rg, L, T, tt, snub)


def main():
    jobs = set()
    for rg in (0, 2.2, 4.7, 10, 22):                      # gate resistor sweep, 2 nH
        for I in (15, 30):
            for T in (25, 150):
                jobs.add(key(I, rg, 2e-9, T))
    for L in (1e-9, 2e-9, 4e-9):                           # loop sweep, as drawn and with snubber
        for I in (15, 30):
            for T in (25, 150):
                jobs.add(key(I, 4.7, L, T))
                jobs.add(key(I, 4.7, L, T, snub=SNUB))
    for tt in (0.0, 0.5e-9, 3e-9):                         # body-diode recovery sensitivity
        jobs.add(key(30, 4.7, 2e-9, 25, tt))
    jobs.add(key(15, 4.7, 2e-9, 25, 0.0))
    for I in (0.5, 5, 10):                                 # snubber at light load (dV/dt, Miller)
        for T in (25, 150):
            jobs.add(key(I, 4.7, 2e-9, T, snub=SNUB))
    for I in (0.5, 5, 10, 15, 20, 25, 30):                 # energies for the loss table
        for T in (25, 100, 150):
            jobs.add(key(I, 4.7, 2e-9, T))
            jobs.add(key(I, GATE, 2e-9, T))
    jobs = sorted(jobs, key=str)
    with Pool(4) as pool:
        res = dict(pool.map(simulate, jobs))

    hdr = ['Rg', 'Lloop', 'I', 'Tj', 'tt ns', 'snubber', 'dV/dt rise', 'pk', 'fall', 'pk',
           'VDS_H pk', 'VDS_L pk', 'VGS_L bump', 'VGS_L min', 'GL pin min', 'VGS_H pk', 'Eon uJ', 'Eoff uJ']
    rows = []
    for k in sorted(res, key=lambda k: (k[5] is not None, isinstance(k[1], tuple), k[3], k[2], str(k[1]), k[0], k[4])):
        I, rg, L, T, tt, sn = k
        r = res[k]
        rows.append(['%g/%g' % rg if isinstance(rg, tuple) else rg, '%g nH' % (L * 1e9), I, T, tt * 1e9, '%g/%gn' % (sn[0], sn[1] * 1e9) if sn else '-',
                     r['dvdt_rise'], r['dvdt_rise_pk'], r['dvdt_fall'], r['dvdt_fall_pk'],
                     r['vds_h_pk_all'], r['vds_l_pk_all'], r['vgs_l_bump'],
                     min(r['vgs_l_min_on'], r['vgs_l_min_off']), r['gld_min'], r['vgs_h_pk'],
                     r['eon'] * 1e6, r['eoff'] * 1e6])
    lines = ['All runs: VBUS 17.4 V, GVDD 11 V, dead time 1.155 us.  dV/dt in V/ns (10-90 % average, and peak).\n'
             'VDS = die drain-source (inside the package inductance), the voltage the 40 V rating applies to.\n'
             'VGS = die gate-source.  Lloop = PCB part of the commutation loop; the packages add 0.8 nH and\n'
             'the bridge cap 0.4 nH, so total loop = Lloop + 1.2 nH.\n'
             'Limits: VDS 40 V (V(BR)DSS is only ~40-42 V typ, Fig 8.7, so anything above 40 V is avalanche);\n'
             'DRV8300D SHx slew 2 V/ns (recommended max); GLx -5 V and GHx-SHx -5 V for 500 ns; VGS +-20 V.\n'
             'Snubber column: R/C fitted from the switch node to SRC (across the low side) of the leg.\n',
             S.table(rows, hdr)]

    E = {}
    for T in (25, 100, 150):
        pts = sorted((k[0], r['eon'], r['eoff']) for k, r in res.items()
                     if k[1] == GATE and k[2] == 2e-9 and k[3] == T and k[4] == TT0 and k[5] is None)
        Ii = np.array([0.0] + [p[0] for p in pts])
        eon = np.array([max(pts[0][1], 0)] + [max(p[1], 0) for p in pts])
        eoff = np.array([max(pts[0][2], 0)] + [max(p[2], 0) for p in pts])
        E[T] = (Ii, eon, eoff)
    lt = loss_table(E)
    csv = os.path.join(HERE, '..', 'losses.csv')
    with open(csv, 'w') as f:
        f.write('# Per-motor (one ESC, 6 FETs) power-stage loss: 6-step trapezoidal, complementary PWM,\n'
                '# PWM switching every cycle (worst case; at 100 % duty there is no switching loss).\n'
                '# Generated by sim/halfbridge/run.py.  VBUS 17.4 V, gate resistors 22 ohm high side / 10 ohm low side\n'
                '# (the recommended configuration, sim/halfbridge/options.py), Lloop 2 nH, dead time 1.155 us/edge.\n'
                '# RDS(on) = datasheet max 2.3 mOhm x Fig 8.9 factor (1.00/1.35/1.70 at Tj 25/100/150 C).\n'
                '# ptotal_w = pcond + psw + pdead: heat in the six FETs (two conduct at any time).\n'
                '# pshunt_w: the 0.5 mOhm shunt (D = 1).  psnub_w: 0 (no snubber; column kept for compatibility).\n'
                '# pboard_w = ptotal + pshunt + psnub.\n'
                '# Four motors: multiply by 4.  Losses are per ESC regardless of which phase is PWM-ed.\n'
                'fpwm_hz,tj_c,phase_current_a,pcond_w,psw_w,pdead_w,ptotal_w,pshunt_w,psnub_w,pboard_w\n')
        for row in lt:
            f.write('%d,%d,%.1f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n' % row)
    summ = [r for r in lt if r[2] in (5, 10, 15, 20, 25, 30)]
    lines.append('\nPer-motor loss (W), gates 22 / 10 ohm (recommended), 2 nH:\n' + S.table(
        [[int(r[0] / 1e3), r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]] for r in summ],
        ['f kHz', 'Tj', 'I', 'Pcond', 'Psw', 'Pdead', 'Ptotal FETs', 'Pshunt', 'Psnub']))
    lines.append('\nSwitching energy per edge vs current (gates 22 / 10 ohm, 2 nH), uJ on/off:\n' + S.table(
        [[T] + ['%.2f/%.2f' % (a * 1e6, b * 1e6) for a, b in zip(E[T][1], E[T][2])] for T in E],
        ['Tj'] + ['%g A' % i for i in E[25][0]]))
    vf = sorted((k[3], r['vf_dead']) for k, r in res.items()
                if k[0] == 15 and k[1] == 4.7 and k[2] == 2e-9 and k[4] == TT0 and k[5] is None)
    lines.append('\nBody diode drop during dead time at 15 A (sim): %s' % ', '.join('%d C %.2f V' % v for v in vf))
    txt = '\n'.join(lines)
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)
    plots(res, lt)


def plots(res, lt):
    plt = S.style()
    fig, ax = plt.subplots(3, 2, figsize=(12, 9), sharex='col')
    for col, (t0, title) in enumerate(((T_HON, 'high side turn-on (sw rising)'),
                                       (T_HOFF, 'high side turn-off (sw falling)'))):
        def cut(r):
            m = (r['_t'] > t0 - 30e-9) & (r['_t'] < t0 + 150e-9)
            return m, (r['_t'][m] - t0) * 1e9
        for rgk, ls, lab in ((4.7, '-', 'as drawn 4.7/4.7'), (GATE, '--', 'recommended 22/10')):
            r = res[key(30, rgk, 2e-9, 25)]
            m, tn = cut(r)
            ax[0, col].plot(tn, r['_vds_h'][m], 'C0', ls=ls, label='VDS high, ' + lab)
            ax[0, col].plot(tn, r['_vds_l'][m], 'C1', ls=ls, label='VDS low, ' + lab)
            ax[1, col].plot(tn, r['_vgs_h'][m], 'C0', ls=ls, label='VGS high, ' + lab)
            ax[1, col].plot(tn, r['_vgs_l'][m], 'C1', ls=ls, label='VGS low, ' + lab)
            ax[2, col].plot(tn, r['_ih'][m], 'C0', ls=ls, label='I high, ' + lab)
            ax[2, col].plot(tn, r['_il'][m], 'C1', ls=ls, label='I low, ' + lab)
        r = res[key(30, 4.7, 2e-9, 150)]
        m, tn = cut(r)
        ax[1, col].plot(tn, r['_vgs_l'][m], 'C3', lw=0.8, label='VGS low, as drawn, 150 C')
        ax[0, col].axhline(40, color='C3', lw=0.8)
        ax[0, col].text(tn[0], 41, '40 V VDSS', color='C3', fontsize=7)
        ax[1, col].axhline(0.7, color='C3', lw=0.8, ls=':')
        ax[0, col].set_title('30 A, Lloop 2 nH, 25 C: ' + title)
        ax[0, col].set_ylabel('V (die)'); ax[1, col].set_ylabel('V (die)'); ax[2, col].set_ylabel('A')
        ax[2, col].set_xlabel('ns')
        for a in ax[:, col]:
            a.legend(fontsize=6, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'halfbridge.png'))

    fig, ax = plt.subplots(1, 5, figsize=(19, 3.8))
    rgs = [0, 2.2, 4.7, 10, 22]
    for I, mk in ((15, 'o'), (30, 's')):
        for T, ls in ((25, '-'), (150, '--')):
            rr = [res[key(I, rg, 2e-9, T)] for rg in rgs]
            lab = '%d A, %d C' % (I, T)
            ax[0].plot(rgs, [x['dvdt_rise'] for x in rr], mk + ls, label=lab)
            ax[1].plot(rgs, [max(x['vds_l_pk_all'], x['vds_h_pk_all']) for x in rr], mk + ls, label=lab)
            ax[2].plot(rgs, [x['vgs_l_bump'] for x in rr], mk + ls, label=lab)
            ax[3].plot(rgs, [(x['eon'] + x['eoff']) * 1e6 for x in rr], mk + ls, label=lab)
            ax[4].plot(rgs, [x['gld_min'] for x in rr], mk + ls, label=lab)
    ax[4].axhline(-5, color='C3', lw=0.8)
    ax[4].set_title('DRV8300 GLx pin minimum vs GND (V)\nabs max -5 V for 500 ns (no clamp modelled)', fontsize=8)
    ax[0].axhline(2, color='C3', lw=0.8)
    ax[0].set_title('sw dV/dt rising, 10-90 % (V/ns)\nred: DRV8300D 2 V/ns', fontsize=8)
    ax[1].axhline(40, color='C3', lw=0.8); ax[1].set_title('peak die VDS, worse FET (V), 2 nH', fontsize=8)
    ax[2].axhline(0.7, color='C3', lw=0.8, ls=':'); ax[2].axhline(1.0, color='C3', lw=0.8)
    ax[2].set_title('low-side die VGS bump at sw rise (V)\nVth min-part @150 C ~0.7-1.0 V', fontsize=8)
    ax[3].set_title('Eon + Eoff per PWM cycle (uJ)', fontsize=8)
    for a in ax:
        a.set_xlabel('external gate resistor (ohm)'); a.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'rg_sweep.png'))

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    Ls = [1, 2, 4]
    for k, (sn, title) in enumerate(((None, 'as drawn (no snubber)'), (SNUB, '+ 1 ohm/4.7 nF sw-to-SRC snubber'))):
        for I, mk in ((15, 'o'), (30, 's')):
            for T, ls in ((25, '-'), (150, '--')):
                rr = [res[key(I, 4.7, L * 1e-9, T, snub=sn)] for L in Ls]
                ax[k].plot(Ls, [x['vds_l_pk_all'] for x in rr], 'C1' + mk + ls, label='low %d A %d C' % (I, T))
                ax[k].plot(Ls, [x['vds_h_pk_all'] for x in rr], 'C0' + mk + ls, label='high %d A %d C' % (I, T))
        ax[k].axhline(40, color='C3', lw=0.8)
        ax[k].set_title('peak die VDS vs loop L, Rg 4.7: ' + title, fontsize=8)
        ax[k].set_xlabel('Lloop, PCB (nH; + 1.2 nH package/ESL)'); ax[k].legend(fontsize=6, ncol=2)
    ax[0].set_ylabel('V')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'loop_sweep.png'))

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for k, f in enumerate((24e3, 48e3)):
        for T, c in ((25, 'C0'), (100, 'C1'), (150, 'C3')):
            rr = np.array([x for x in lt if x[0] == f and x[1] == T])
            ax[k].plot(rr[:, 2], rr[:, 6], c, label='FETs total, Tj %d C' % T)
            ax[k].plot(rr[:, 2], rr[:, 3], c, ls='--', lw=0.8, label='conduction, %d C' % T)
            if T == 150:
                ax[k].plot(rr[:, 2], rr[:, 4], 'C2', ls=':', label='switching, 150 C')
                ax[k].plot(rr[:, 2], rr[:, 5], 'C4', ls=':', label='dead-time diode, 150 C')
        ax[k].axvline(15.8, color='0.5', lw=0.6)
        ax[k].text(16.2, 0.2, '15.8 A\n(iFlight 60 s max)', fontsize=7)
        ax[k].set_title('loss per motor (6 FETs), PWM %d kHz' % (f / 1e3))
        ax[k].set_xlabel('phase current (A)'); ax[k].legend(fontsize=6)
    ax[0].set_ylabel('W')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'losses.png'))


if __name__ == '__main__':
    main()
