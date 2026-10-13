# -*- coding: utf-8 -*-
"""A crash: a motor jammed at full throttle on 6S, and what it does to the ESC.

    sim/.venv/bin/python sim/crash.py      writes sim/out/crash/CRASH.md

The current.  A prop that hits something stops the rotor in a few
milliseconds; the ESC goes on applying its duty to a motor with no back-EMF,
so the phase current is the duty times the pack voltage over the loop's
resistance (the winding, two FETs, the shunt, the copper, the pack): about
150 A on a full 6S pack.  What brings it down is AM32 (src/main.c at the
target's commit, read for this):

  * its current limit, a PID on the averaged shunt current at about 1 kHz
    whose output may move the duty by at most 0.5 % per step (about
    0.48 %/ms): 11 % in the first 22.5 ms;
  * the back-EMF timeout: no zero-cross for 22.5 ms (TMR6 count 45000 at
    2 MHz) forces a commutation and drops to the startup clamp (minimum duty
    + 400 of 2000, about 21 %), which the duty ramps down to at 2 % per ms;
  * the stuck-rotor cut after 11 such timeouts (about 248 ms) at high
    throttle.

The DRV8320H's own overcurrent trip (its VDS pin open: 0.6 V across a FET,
so 150-300 A) sits above this current, so it does not act.  The option
simulated next to it is the pin's next step down (75k to AGND: 0.26 V), which
trips after 4 us and retries every 4 ms.

What it heats.  The always-on low-side FET carries the whole current, and
its source copper funnels it to the shunt (stress.py finds 59 % of one FET's
current in one 0.30 mm via).  That net's copper is solved here as a thermal
network: the same cells, lands and barrels as dcflow.py's electrical one,
each edge's heat conductance from its electrical one (copper's k rho), each
cell's heat capacity from its volume, Joule heat from the solved current
with copper's resistivity rising with temperature.  The copper loses no heat
to the FR-4 or to the planes beside it (they would take some within the
crash's tens of milliseconds): the temperatures here are an upper bound.
The FET's junction: its single-pulse ZthJC (data.FET) convolved with its
loss at its maximum RDS(on) at that temperature.

Limits: FR-4 starts to decompose and lift pads around 288 C (the solder-float
test temperature); copper melts at 1085 C.
"""
import os, sys, time
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(RIDGE, 'src'))
import copper, dcflow, data

OUT = os.path.join(HERE, 'out', 'crash')
K_CU, RC_CU = 390.0, 3.45e6          # copper: W/m K, J/m3 K
KRHO_SOLDER = 58.0 * dcflow.RHO_SOLDER
T_LIFT, T_MELT = 288.0, 1085.0

# AM32's reaction (see the docstring)
T_BEMF = 22.5e-3                     # s without a zero-cross before it forces a commutation
PID_SLEW = 0.0048 / 1e-3             # duty per second the current limit can remove (0.48 %/ms)
RAMP = 0.02 / 1e-3                   # duty per second toward the startup clamp (2 %/ms)
D_STARTUP = 0.21                     # the startup clamp: minimum duty + 400 of 2000
T_CUT = 11 * T_BEMF                  # stuck-rotor cut at high throttle
# DRV8320H VDS overcurrent (hardware variant): threshold, deglitch, retry
OCP = {'open (as built)': 0.60, '75k to AGND': 0.26}
R_MOTOR = data.MOTOR['r']            # ohm, the winding as the loop sees it
R_SHUNT = data.SHUNT['r']


def rds_max(T):
    F = data.FET
    t, r = zip(*F['rds_ratio'])
    return F['rds25_max'] * float(np.interp(T, t, r))


def phase_current(t, T_fet, r_pack=None, r_copper=3e-3):
    """Jammed-rotor phase current (A) at time t (s) after the jam, quasi-static
    (the winding's L/R is a fraction of a millisecond)."""
    V = data.BATTERY['vfull']
    r_pack = data.BATTERY['r'] if r_pack is None else r_pack
    if t < T_BEMF:
        D = 1.0 - PID_SLEW * t
    else:
        D0 = 1.0 - PID_SLEW * T_BEMF
        D = max(D_STARTUP, D0 - RAMP * (t - T_BEMF))
    if t >= T_CUT:
        return 0.0
    return D * V / (R_MOTOR + 2 * rds_max(T_fet) + R_SHUNT + r_copper + r_pack)


def zth(tp):
    """The FET's single-pulse ZthJC (K/W) at pulse length tp (s), log-log."""
    t, z = zip(*data.FET['zth'])
    tp = np.clip(tp, t[0], 1e3)
    out = np.exp(np.interp(np.log(tp), np.log(t), np.log(z)))
    return np.where(tp > t[-1], data.FET['rth_ch_c'], out)


def fet_junction(times, T0, ocp_v=None):
    """Junction temperature of the always-on low-side FET (case held at T0):
    superposition of its loss steps through ZthJC.  ocp_v: the driver's VDS
    trip; above it the current is a 4 us pulse every 4 ms, which this treats
    as off.  Returns (Tj array, I array)."""
    Tj = np.full(len(times), T0)
    P = np.zeros(len(times))
    I = np.zeros(len(times))
    for k, t in enumerate(times):
        T = Tj[k - 1] if k else T0
        i = phase_current(t, T)
        if ocp_v is not None and i * rds_max(T) > ocp_v:
            i = 0.0
        I[k] = i
        P[k] = i * i * rds_max(T)
        dP = np.diff(np.concatenate([[0.0], P[:k + 1]]))
        Tj[k] = T0 + float(np.sum(dP * zth(t - times[:k + 1] + 1e-7)))
    return Tj, I


def thermal_network(c, s):
    """The net's copper as a heat network, from its electrical one: (K, C,
    edges, rep) with K the conductance matrix (W/K), C the heat capacities
    (J/K), and for each node the cell or hole it stands for."""
    info = s.info
    a, b, g = info['edges']
    n = info['n']
    ncell = info['ncell']
    krho = K_CU * dcflow.rho(info['T'])
    gth = g * krho
    # the solder joints at the terminals
    term_nodes = set(info['terms'].values())
    is_term = np.array([x in term_nodes for x in a]) | np.array([x in term_nodes for x in b])
    gth[is_term] = g[is_term] * KRHO_SOLDER
    K = sp.coo_matrix((np.concatenate([gth, gth, -gth, -gth]),
                       (np.concatenate([a, b, a, b]), np.concatenate([a, b, b, a]))), shape=(n, n)).tocsr()
    C = np.zeros(n)
    ids = info['ids']
    for li in range(ids.shape[0]):
        m = ids[li] >= 0
        C[ids[li][m]] = (c.res * 1e-3) ** 2 * c.t[li] * 1e-3 * RC_CU
    # barrels: each segment's plating volume, half to each end
    kind = np.full(n, 'cell', dtype=object)
    for hi, nodes in info['barrels']:
        h = c.holes[hi]
        for (l1, n1), (l2, n2) in zip(nodes, nodes[1:]):
            vol = np.pi * h['d'] * 1e-3 * info['plating'] * abs(c.zc[l2] - c.zc[l1]) * 1e-3
            C[n1] += vol * RC_CU / 2
            C[n2] += vol * RC_CU / 2
        for _, nd in nodes:
            kind[nd] = 'via %d' % hi
            C[nd] = max(C[nd], 1e-9)
    # the terminals stand for the parts' pads: the FET's and the shunt's mass
    for part, nd in info['terms'].items():
        C[nd] = data.FET['c_th'] if part.startswith('Q') else 0.02
        kind[nd] = 'part ' + part
    return K, C, kind


def copper_transient(c, s, times, T0, current, share_scale=1.0):
    """Temperatures of the net's copper while current(t) amps flow in the
    unit solution s's pattern.  share_scale < 1 spreads the funnel via's
    share as if more vias stood beside it (its edges carry that fraction of
    their current; the rest is assumed to take paths of equal length)."""
    info = s.info
    a, b, g = info['edges']
    K, C, kind = thermal_network(c, s)
    i_unit = s.edge_i
    # the via that carries the largest share
    worst_hi, worst = None, 0.0
    for hi, frac in dcflow.barrel_currents(c, s):
        if frac > worst:
            worst_hi, worst = hi, frac
    via_nodes = [nd for hi, nodes in info['barrels'] if hi == worst_hi for _, nd in nodes]
    in_via = np.isin(a, via_nodes) & np.isin(b, via_nodes)
    i_unit = np.where(in_via, i_unit * share_scale, i_unit)
    dt = times[1] - times[0]
    A = (sp.diags(C / dt) + K).tocsc()
    lu = spla.splu(A)
    T = np.full(info['n'], T0)
    peak_via, peak_any = T0, T0
    t_over = 0.0
    for t in times:
        I = current(t)
        Tm = 0.5 * (T[a] + T[b])
        gT = g * dcflow.rho(info['T']) / dcflow.rho(Tm)          # hotter copper conducts less
        P = (I * i_unit) ** 2 / gT
        q = np.zeros(info['n'])
        np.add.at(q, a, P / 2)
        np.add.at(q, b, P / 2)
        T = lu.solve(C / dt * T + q)
        pv = float(T[via_nodes].max())
        peak_via = max(peak_via, pv)
        peak_any = max(peak_any, float(T[:info['ncell']].max()))
        if pv > T_LIFT:
            t_over += dt
    return dict(via=worst_hi, share=worst * share_scale, peak_via=peak_via, peak_cell=peak_any,
                t_over_lift=t_over, hole=c.holes[worst_hi])


def run():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    c = copper.extract('esc')
    # the low-side FET whose source copper funnels hardest
    worst = None
    for n in (1, 2, 3, 4):
        for y in 'ABC':
            s = dcflow.solve(c, 'M%d_SRC' % n, {'Q%d%sL' % (n, y): 1.0, 'R_SH%d' % n: -1.0}, T=20.0)
            frac = max(f for _, f in dcflow.barrel_currents(c, s))
            if worst is None or frac > worst[0]:
                worst = (frac, n, y, s)
    frac, n, y, s = worst
    dt = 20e-6
    times = np.arange(0, T_CUT + 2e-3, dt)
    lines = ['# Ridge 3 ESC: a motor jammed at full throttle', '',
             'Generated by `sim/crash.py` on %s.  %s, 6S full (%.1f V), FET %s.  The worst low-side FET for its '
             'source copper is Q%d%sL: %.0f %% of its current goes through one %.2f mm via.' % (
                 time.strftime('%Y-%m-%d'), data.design_name(), data.BATTERY['vfull'], data.FET['part'],
                 n, y, 100 * frac, c.holes[max(dcflow.barrel_currents(c, s), key=lambda x: x[1])[0]]['d']), '']
    rows = []
    for start, T0 in (('cold board (25 C)', 25.0), ('hot board (120 C, hard flying on a 50 C day)', 120.0)):
        for ocp_name, ocp_v in OCP.items():
            Tj, I = fet_junction(times, T0, ocp_v if ocp_v < 0.5 else None)
            curr = lambda t, I=I: float(np.interp(t, times, I))
            for scale, label in ((1.0, 'as built'), (0.5, 'half the share (about twice the vias)'),
                                 (0.33, 'a third of the share')):
                if ocp_v < 0.5 and scale < 1:
                    continue
                cu = copper_transient(c, s, times, T0, curr, share_scale=scale)
                if ocp_v < 0.5:          # the driver trips: microsecond pulses to its threshold every 4 ms
                    trip = ocp_v / rds_max(T0)
                    peak = '%.0f A pulses of a few us every 4 ms' % trip
                    peak_via = '%.0f A pulses' % (trip * cu['share'])
                else:
                    peak, peak_via = '%.0f A' % I.max(), '%.0f A' % (I.max() * cu['share'])
                rows.append([start, ocp_name, label, peak, peak_via,
                             '%.0f C' % cu['peak_via'], '%.1f ms' % (cu['t_over_lift'] * 1e3), '%.0f C' % Tj.max()])
    lines.append('| Start | DRV8320H VDS pin | Via share | Peak phase current | Peak via current | '
                 'Hottest via copper | Time above 288 C | Hottest FET junction |')
    lines.append('|---|---|---|---|---|---|---|---|')
    lines += ['| ' + ' | '.join(r) + ' |' for r in rows]
    lines += ['', 'Copper loses no heat to the FR-4 in this model: real temperatures are lower.  '
              'Limits: pads lift and FR-4 decomposes from about 288 C; copper melts at 1085 C; the FET\'s '
              'junction is rated %.0f C.' % data.FET['tch_max'], '',
              '---', 'Run time %.0f s.' % (time.time() - t0)]
    open(os.path.join(OUT, 'CRASH.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    name = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--variant=')), None)
    if name:
        data.variant(name)
        OUT = os.path.join(OUT, name)
    run()
