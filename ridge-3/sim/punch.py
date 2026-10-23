# -*- coding: utf-8 -*-
"""A full-throttle punch from hover: the phase current it peaks at, what the
DRV8320H's overcurrent monitor makes of it, and the switching edges at it.

From ridge-3/:

    sim/.venv/bin/python sim/punch.py

writes PUNCH.md and punch.json to sim/results/punch/; its SPICE netlists
and runs stay in sim/out/punch/spice/.  It reads the ESC's board, the
OptiMOS 6 SPICE model (spice.py) and the hot FET temperature from
sim/results/variants/rev2/found.json, which `stress.py --variant=rev2`
writes.

The current.  Each motor as its DC equivalent: the duty times the bus
voltage drives the phase current against the back-EMF and the loop's
resistance (the winding, two FETs at maximum RDS(on), the shunt, the copper),
and the current's torque turns the rotor and prop against the prop's load.
Back-EMF constant and prop load are fitted to the maker's load test at full
throttle (data.MOTOR: 24 V, 27.4 A, 48120 rpm); the start is hover, the
rpm from the 30 % row scaled to the thrust hover needs.  The four motors punch
together and share the pack's resistance.  AM32 moves the duty toward full at
most 16 % per ms (max ramp 160, the high-rpm rate; src/main.c) and its current
limit acts as in crash.py.  The rotor's and prop's inertia is not published:
ASSUMPTION 1.5-4e-6 kg m2 (a 1507 bell of about 6 g at 9 mm and a 3-inch
three-blade prop of about 4 g); the heavier it is, the higher the peak.

The monitor.  crash.py's trip currents with the copper in what the driver
measures (crash.sense_copper); on the high side the four motors' current in
the shared battery plane adds to it during a punch, solved here.

The edges.  spice.half_bridge at the punch's peak current, for the IDRIVE the
design has (60 / 120 mA) and the next step down (30 / 60 mA), at 3, 5 and
8 nH of commutation loop: SHx below ground against the DRV8320H's -7 V
(200 ns) absolute maximum.
"""
import os, sys, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'src'))
import copper, dcflow, data, spice, crash

OUT = os.path.join(HERE, 'results', 'punch')           # the report, committed
WORK = os.path.join(HERE, 'out', 'punch', 'spice')       # the SPICE runs
RAMP_HIGH = 0.16 / 1e-3              # duty per second: AM32's high-rpm ramp at max ramp 160
INERTIA = (1.5e-6, 2.5e-6, 4e-6)     # kg m2, rotor and prop: ASSUMPTION (see the docstring)
DT = 20e-6


def fit():
    """(Ke V s/rad, prop torque coefficient N m s2, hover rad/s) from the load test."""
    M = data.MOTOR
    th, ib, g = zip(*M['load'])
    w100 = 48120 * 2 * np.pi / 60
    ke = (M['vtest'] - ib[-1] * M['r']) / w100
    kp = ke * ib[-1] / w100 ** 2
    w30 = 19539 * 2 * np.pi / 60
    need = M['auw'] / 4 / data.AIR.get('rho', 1.0)
    return ke, kp, w30 * (need / g[0]) ** 0.5


def punch(J, V=None, T_fet=25.0, t_end=60e-3):
    """Phase current per motor (A) against time for a punch from hover at
    t = 0, all four motors; returns (times, current, duty)."""
    V = data.BATTERY['vfull'] if V is None else V
    ke, kp, w = fit()
    r_pack = data.BATTERY['r']
    R = data.MOTOR['r'] + 2 * crash.rds_max(T_fet) + crash.R_SHUNT + crash.R_COPPER
    limit = data.AM32['current_limit']
    # hover: the duty that holds w against the prop
    i = kp * w * w / ke
    D = (ke * w + i * R) / (V - 4 * r_pack * i)
    hover_ib = D * i
    readings, acc, n_acc, next_pid, adj, err_last = [hover_ib] * crash.N_AVG, 0.0, 0, crash.T_PID, 1.0, 0.0
    times = np.arange(0, t_end, DT)
    I, Ds = np.zeros(len(times)), np.zeros(len(times))
    for k, t in enumerate(times):
        if t >= next_pid:
            next_pid += crash.T_PID
            readings.append(acc / max(n_acc, 1))
            acc, n_acc = 0.0, 0
            err = sum(readings[-crash.N_AVG:]) / crash.N_AVG - limit
            adj = min(1.0, max(crash.D_MIN, adj - crash.pid_step(err, err_last)))
            err_last = err
        D = min(adj, D + RAMP_HIGH * DT)
        # the bus sags under all four: solve i with V_bus = V - 4 r_pack D i
        i = (D * V - ke * w) / (R + 4 * r_pack * D * D)
        w += (ke * i - kp * w * w) / J * DT
        I[k], Ds[k] = i, D
        acc += D * i
        n_acc += 1
    return times, I, Ds


def vbat_copper(c):
    """The battery plane's share of what each high-side monitor measures
    while all four motors draw the same current: max over channels and
    phases of V(VDRAIN) - V(drain) per amp per motor (ohm, 20 C)."""
    worst = 0.0
    for y in 'ABC':
        cur = {'P_BAT+': 4.0}
        cur.update({'Q%d%sH' % (n, y): -1.0 for n in (1, 2, 3, 4)})
        cur.update({'U_GD%d' % n: 0.0 for n in (1, 2, 3, 4)})
        v = dcflow.solve(c, 'VBAT', cur, T=20.0).term_v
        worst = max(worst, max(v['U_GD%d' % n] - v['Q%d%sH' % (n, y)] for n in (1, 2, 3, 4)))
    return worst


def run():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    spice.WORK = WORK
    os.makedirs(spice.WORK, exist_ok=True)
    data.variant('rev2')
    ke, kp, w_h = fit()
    lines = ['# Ridge 3 ESC: a full-throttle punch from hover', '',
             'Generated by `sim/punch.py` on %s.  rev2 on a full 6S pack (%.1f V, %.0f mOhm), all four motors '
             'together; motor fitted to the maker\'s load test: back-EMF %.2f mV per rad/s, hover at %.0f rpm.  '
             'AM32 ramps the duty at 16 %% per ms; its current limit is %.0f A (battery side, 50 ms average).'
             % (time.strftime('%Y-%m-%d'), data.BATTERY['vfull'], data.BATTERY['r'] * 1e3, ke * 1e3,
                w_h * 60 / 2 / np.pi, data.AM32['current_limit']), '',
             '## The current', '',
             '| Rotor and prop inertia | Peak phase current per motor | At | Battery current, 4 motors |',
             '|---|---|---|---|']
    peaks = []
    for J in INERTIA:
        t, I, D = punch(J)
        k = int(np.argmax(I))
        peaks.append(float(I[k]))
        lines.append('| %.1f x 10<sup>-6</sup> kg m<sup>2</sup> | %.0f A | %.1f ms | %.0f A |' % (
            J * 1e6, I[k], t[k] * 1e3, 4 * D[k] * I[k]))
    lines += ['', 'With a LiHV pack full (26.1 V) the peaks are %.0f-%.0f A.' % tuple(
        max(punch(J, V=26.1)[1]) for J in (INERTIA[0], INERTIA[-1]))]
    i_lo, i_hi = min(peaks), max(peaks)
    # the monitor
    c = copper.extract('esc')
    parts = {(n, y): crash.sense_parts(c, n, y) for n in (1, 2, 3, 4) for y in 'ABC'}
    worst = max(parts, key=lambda ny: parts[ny]['src'] + parts[ny]['drain'])
    ls = parts[worst]['src'] + parts[worst]['drain']
    hs_own = max(p['vdrain'] + p['hs_src'] for p in parts.values())
    vb = vbat_copper(c)
    hs = max(p['hs_src'] for p in parts.values()) + vb       # all four motors' current in the plane
    flight = json.load(open(os.path.join(HERE, 'results', 'variants', 'rev2', 'found.json')))['found']['flight']['fet']
    lines += ['', '## What the driver\'s overcurrent monitor trips at', '',
              'Copper in what it measures (20 C): low side %.2f mOhm (channel %d phase %s, the most); high side '
              'up to %.2f mOhm with only its own phase\'s current, and %.2f mOhm when all four motors draw the '
              'same current through the battery plane, as in a punch.  A trip turns that motor\'s FETs off for 4 ms; AM32 is not '
              'told.  The hot FET is the hard 3-minute flight\'s hottest on a 50 C day (%.0f C).'
              % (ls * 1e3, worst[0], worst[1], hs_own * 1e3, hs * 1e3, flight), '',
              '| FET at | VDS pin | Low side trips at (max / typical RDS(on)) | High side, punch (max / typical) '
              '| Punch peak %.0f-%.0f A |' % (i_lo, i_hi), '|---|---|---|---|---|']
    for T in (25.0, flight):
        for name, vth in (('open, 0.6 V (as built)', 0.6), ('75k to AGND, 0.26 V', 0.26)):
            ls_max, ls_typ = crash.trip_current(vth, T, ls), crash.trip_current(vth, T, ls, crash.rds_typ)
            hs_max, hs_typ = crash.trip_current(vth, T, hs), crash.trip_current(vth, T, hs, crash.rds_typ)
            low = min(ls_max, hs_max)
            verdict = ('trips' if low < i_lo else 'may trip' if low < i_hi else
                       'margin %.0f %%' % (100 * (low / i_hi - 1)))
            lines.append('| %.0f C | %s | %.0f / %.0f A | %.0f / %.0f A | %s |' % (
                T, name, ls_max, ls_typ, hs_max, hs_typ, verdict))
    # the edges at the punch's current
    lines += ['', '## Switching edges at the punch\'s current', '',
              'One half-bridge (`spice.half_bridge`, the setup of STRESS.md section 3) switching the motor '
              'current at full voltage.  The DRV8320H\'s SHx pin may go to -7 V for 200 ns (absolute maximum).', '',
              '| IDRIVE (source / sink) | Current | FET | Loop | SHx lowest | High-side FET peak | Low-side FET peak |',
              '|---|---|---|---|---|---|---|']
    runs, keys = [], []
    for name in ('rev2', 'idrive30'):
        data.variant(name)
        for I in (30.0, round(i_hi)):
            for T in (25, 150):
                for L in (3e-9, 5e-9, 8e-9):
                    keys.append((name, data.BRIDGE['ipu'], data.BRIDGE['ipd'], I, T, L))
                    runs.append(dict(data.BRIDGE, I=I, T=T, Lloop=L, lm=data.BODY_DIODE, tag='punch_%s' % name))
    data.variant('rev2')
    res = spice.half_bridges(runs)
    found = []
    for (name, ipu, ipd, I, T, L), r in zip(keys, res):
        found.append(dict(variant=name, I=I, T=T, L=L, sh_min=r['sh_min'], hs=r['vds_hs_peak'],
                          ls=r['vds_ls_peak'], gear=r['gear'], gmin=r['gmin']))
        lines.append('| %.0f / %.0f mA | %.0f A | %d C | %.0f nH | %.1f V%s | %.1f V | %.1f V |' % (
            ipu * 1e3, ipd * 1e3, I, T, L * 1e9, r['sh_min'], ' (past -7 V)' if r['sh_min'] < -7 else '',
            r['vds_hs_peak'], r['vds_ls_peak']))
    lines += ['', '---', 'Run time %.0f s.' % (time.time() - t0)]
    open(os.path.join(OUT, 'PUNCH.md'), 'w').write('\n'.join(lines) + '\n')
    json.dump(dict(peaks=peaks, edges=found), open(os.path.join(OUT, 'punch.json'), 'w'), indent=1)
    print('\n'.join(lines))


if __name__ == '__main__':
    import argparse
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                            allow_abbrev=False).parse_args()
    run()
