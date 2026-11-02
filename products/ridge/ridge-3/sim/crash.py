# -*- coding: utf-8 -*-
"""A crash: a motor jammed at full throttle on 6S, and what it does to the ESC.

From ridge-3/:

    sim/.venv/bin/python sim/crash.py [--variant=NAME]

writes CRASH.md and crash.json to sim/results/crash/ (a variant's to
sim/results/crash/NAME/).  It reads the ESC's board, and the hot start
(below) from the found.json that `stress.py --variant=NAME` writes to
sim/results/variants/NAME/ (rev2's without --variant).

The current.  A prop that hits something stops the rotor in a few
milliseconds; the ESC goes on applying its duty to a motor with no back-EMF,
so the phase current is the duty times the pack voltage over the loop's
resistance (the winding, two FETs, the shunt, the copper, the pack): about
150 A on a full 6S pack.  What brings it down is AM32 (src/main.c at the
target's commit, read for this):

  * its current limit: a loop at about 1 kHz on the battery current its
    shunt reads, averaged over the last 50 readings, against the limit
    (data.AM32).  It is a PD loop (Kp 400, Kd 1000 on 10 mA counts) whose
    output may move the duty by at most 10 of 2000 counts a step (0.5 %);
  * the back-EMF timeout: no zero-cross for 22.5 ms (TMR6 count 45000 at
    2 MHz) forces a commutation and drops to the startup clamp (minimum duty
    + 400 of 2000, about 21 %), which the duty ramps down to at 2 % per ms;
  * the stuck-rotor cut after 11 such timeouts (about 248 ms) at high
    throttle (bemf_timeout 10 in main.c, a variable, not a setting); runs
    with the cut after 3 (a change to the target) stand beside them.
The jam is taken as instant and the forced commutations as leaving the
current in the same low-side FET: both on the hot side.

The DRV8320H's own overcurrent monitor (hardware variant, TI SLVSDJ3D
8.3.6.4): when a conducting FET's monitored voltage passes the level its VDS
pin sets for 4 us, all six FETs go off for 4 ms, then it retries.  AM32 is
not told (nFAULT is not connected); it sees only the lower average current.
The monitor does not measure the FET alone: the low side is measured from
SHx to SLx and the high side from VDRAIN to SHx, so the copper between those
pins and the FET adds to it (sense_copper(): dcflow.py on the board, with
only that phase's current flowing).  As built the VDS pin is open: 0.6 V, a
typical value with no limits in the datasheet, so a run with no trip at all
is kept as the bound.  The next step down (75k to AGND) is 0.26 V.

What it heats.  The always-on low-side FET carries the whole current, and
its source copper funnels it to the shunt (stress.py finds 59 % of one FET's
current in one 0.30 mm via).  That net's copper is solved here as a heat
network: the same cells, lands and barrels as dcflow.py's electrical one,
each edge's heat conductance from its electrical one (copper's k rho), each
cell's heat capacity from its volume, Joule heat from the solved current
with copper's resistivity rising with temperature.  Against each layer's
copper lies FR-4 out to half the dielectric to the next layer, which takes
heat through its thickness; copper of other nets beyond that (planes, the
heatsink under the board) and the air take none, so the temperatures here
lean high.

The FETs' junctions: their single-pulse ZthJC (data.FET) convolved with
their loss at maximum RDS(on) at that temperature (the datasheet's curve,
carried on in a straight line past its end).  The low-side FET's case is the
phase net's copper under its drain, solved the same way with the FET's whole
loss put into it; the high side's case stays at the start temperature (its
drain is on the battery plane).

The hot start is the hottest FET of the hard 3-minute flight on a 50 C day
(stress.py's found.json for this design or variant).

Limits: FR-4 starts to decompose and lift pads around 288 C (the solder-float
test temperature); copper melts at 1085 C.
"""
import os, sys, json, time
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(RIDGE, 'src'))
import copper, dcflow, data
from thermal import K_FR4_Z, RC_FR4

RESULTS = os.path.join(HERE, 'results')
OUT = os.path.join(RESULTS, 'crash')       # the report, committed
K_CU, RC_CU = 390.0, 3.45e6          # copper: W/m K, J/m3 K
KRHO_SOLDER = 58.0 * dcflow.RHO_SOLDER
T_LIFT, T_MELT = 288.0, 1085.0
FR4_SLICES = (0.15, 0.35, 0.5)       # the FR-4 against a layer's copper, as fractions of its half
DT = 20e-6                           # s, the time step
EVERY = 5                            # steps per step of the copper's heat (its own times are milliseconds)

# AM32's reaction (see the docstring)
T_BEMF = 22.5e-3                     # s without a zero-cross before it forces a commutation
RAMP = 0.02 / 1e-3                   # duty per second toward the startup clamp (2 %/ms)
D_STARTUP = 0.21                     # the startup clamp: minimum duty + 400 of 2000
D_MIN = D_STARTUP - 0.20             # its minimum duty, below which the current loop cannot go
N_CUT = 11                           # back-EMF timeouts to the stuck-rotor cut at high throttle
                                     # (bemf_timeout 10, a variable in main.c, not a setting)
N_CUT_SHORT = 3                      # the same with bemf_timeout 2: a change to the target
T_PID, N_AVG = 1e-3, 50              # the current loop's period and the readings it averages
PID_KP, PID_KD, PID_MAX = 400, 1000, 10 / 2000.0

# the DRV8320H's VDS overcurrent monitor (hardware variant)
OCP = {'none (a bound)': None, 'open, 0.6 V (as built)': 0.60, '75k to AGND, 0.26 V': 0.26}
T_RETRY = 4e-3                       # s all FETs stay off after a trip
T_SEEN = 8e-6                        # ASSUMPTION: an on-time shorter than tDRIVE (4 us, the monitor's
                                     # blanking) plus the 4 us deglitch does not trip it
R_MOTOR = data.MOTOR['r']            # ohm, the winding as the loop sees it
R_SHUNT = data.SHUNT['r']
R_COPPER = 3e-3                      # ohm, the rest of the loop's copper and wires


def rds_max(T):
    """The FET's maximum RDS(on) at T: the datasheet's curve, carried on in a
    straight line past its ends."""
    F = data.FET
    t, r = (np.array(x, float) for x in zip(*F['rds_ratio']))
    if T > t[-1]:
        return F['rds25_max'] * float(r[-1] + (r[-1] - r[-2]) / (t[-1] - t[-2]) * (T - t[-1]))
    return F['rds25_max'] * float(np.interp(T, t, r))


def rds_typ(T):
    return rds_max(T) * data.FET['rds25_typ'] / data.FET['rds25_max']


def cu(T):
    """Copper's resistance at T over its value at 20 C."""
    return dcflow.rho(T) / dcflow.rho(20.0)


def zth(tp):
    """The FET's single-pulse ZthJC (K/W) at pulse length tp (s), log-log."""
    t, z = zip(*data.FET['zth'])
    tp = np.clip(tp, t[0], 1e3)
    out = np.exp(np.interp(np.log(tp), np.log(t), np.log(z)))
    return np.where(tp > t[-1], data.FET['rth_ch_c'], out)


def sense_parts(c, n, y):
    """Copper (ohm at 20 C) that the driver's VDS monitors measure in series
    with channel n's phase-y FETs, with only that phase's current flowing:
    SLx below the low side's source ('src'), its drain below SHx ('drain'),
    the high side's drain below VDRAIN ('vdrain'), SHx below its source
    ('hs_src')."""
    q, gd, pad = 'Q%d%s' % (n, y), 'U_GD%d' % n, 'P_M%d%s' % (n, y)
    ph = 'M%d_%s' % (n, y)
    out = {}
    v = dcflow.solve(c, 'M%d_SRC' % n, {q + 'L': 1.0, 'R_SH%d' % n: -1.0, gd: 0.0}, T=20.0).term_v
    out['src'] = v[q + 'L'] - v[gd]
    v = dcflow.solve(c, ph, {pad: 1.0, q + 'L': -1.0, gd: 0.0}, T=20.0).term_v
    out['drain'] = v[gd] - v[q + 'L']
    v = dcflow.solve(c, 'VBAT', {'P_BAT+': 1.0, q + 'H': -1.0, gd: 0.0}, T=20.0).term_v
    out['vdrain'] = v[gd] - v[q + 'H']
    v = dcflow.solve(c, ph, {q + 'H': 1.0, pad: -1.0, gd: 0.0}, T=20.0).term_v
    out['hs_src'] = v[q + 'H'] - v[gd]
    return out


def sense_copper(c, n, y):
    """sense_parts summed: (low side, high side)."""
    p = sense_parts(c, n, y)
    return p['src'] + p['drain'], p['vdrain'] + p['hs_src']


def trip_current(vth, T, r_cu20, rds=rds_max):
    """The current at which a FET at T trips a monitor at vth volts, with
    r_cu20 ohm of copper (at 20 C, taken at T) in what it measures."""
    return vth / (rds(T) + r_cu20 * cu(T))


def pid_step(err, last):
    """The duty AM32's current loop takes off in one step, for an error of
    err amps (last step's: last)."""
    d = (PID_KP * 100 * err + PID_KD * 100 * (err - last)) / 1e4      # counts of 2000
    return float(np.clip(d / 2000.0, -PID_MAX, PID_MAX))


def thermal_network(c, s):
    """The net's copper as a heat network, from its electrical one, with the
    FR-4 against it: (K, C, kind) with K the conductance matrix (W/K), C the
    heat capacities (J/K), and for each node what it stands for."""
    info = s.info
    a, b, g = info['edges']
    n = info['n']
    krho = K_CU * dcflow.rho(info['T'])
    gth = g * krho
    # the solder joints at the terminals
    term_nodes = set(info['terms'].values())
    is_term = np.array([x in term_nodes for x in a]) | np.array([x in term_nodes for x in b])
    gth[is_term] = g[is_term] * KRHO_SOLDER
    # the FR-4 either side of each layer's copper, out to half the dielectric
    # to the next layer (the other half is that layer's; whatever copper of
    # other nets lies there would take more), in slices thin to thick, each
    # cell its own column; the mask and air outside the outer layers take nothing
    ids = info['ids']
    A = (c.res * 1e-3) ** 2
    fa, fb, fg, fc = [], [], [], []
    m_all = n
    for li in range(ids.shape[0]):
        cells = ids[li][ids[li] >= 0]
        for gap in (li - 1, li):
            if not 0 <= gap < len(c.diel):
                continue
            half = c.diel[gap] * 1e-3 / 2
            prev, prev_t = cells, 0.0
            for f in FR4_SLICES:
                th = f * half
                new = np.arange(m_all, m_all + cells.size)
                m_all += cells.size
                fa.append(prev); fb.append(new)
                fg.append(np.full(cells.size, K_FR4_Z * A / ((prev_t + th) / 2)))
                fc.append(np.full(cells.size, RC_FR4 * A * th))
                prev, prev_t = new, th
    a2 = np.concatenate([a] + fa)
    b2 = np.concatenate([b] + fb)
    g2 = np.concatenate([gth] + fg)
    K = sp.coo_matrix((np.concatenate([g2, g2, -g2, -g2]),
                       (np.concatenate([a2, b2, a2, b2]), np.concatenate([a2, b2, b2, a2]))),
                      shape=(m_all, m_all)).tocsr()
    C = np.zeros(m_all)
    C[n:] = np.concatenate(fc) if fc else []
    for li in range(ids.shape[0]):
        m = ids[li] >= 0
        C[ids[li][m]] = (c.res * 1e-3) ** 2 * c.t[li] * 1e-3 * RC_CU
    # barrels: each segment's plating volume, half to each end
    kind = np.full(m_all, 'cell', dtype=object)
    kind[n:] = 'FR-4'
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


class Heat:
    """A net's copper as a heat network (thermal_network), stepped by
    backward Euler: Joule heat from a current in the unit solution s's
    pattern (edge currents times scale), plus heat put in at a part's
    terminal."""

    def __init__(self, c, s, T0, dt, scale=1.0):
        info = s.info
        self.a, self.b, self.g = info['edges']
        self.rho_ref = dcflow.rho(info['T'])
        K, C, self.kind = thermal_network(c, s)
        self.c_dt = C / dt
        self.lu = spla.splu((sp.diags(self.c_dt) + K).tocsc())
        self.i_unit = s.edge_i * scale
        self.terms = info['terms']
        self.T = np.full(len(C), T0)

    def step(self, I2, heat=None):
        """One step with I2 the mean square of the current over it."""
        a, b = self.a, self.b
        g = self.g * self.rho_ref / dcflow.rho(0.5 * (self.T[a] + self.T[b]))   # hotter copper conducts less
        P = I2 * self.i_unit ** 2 / (2 * g)
        n = len(self.T)
        q = np.bincount(a, P, n) + np.bincount(b, P, n)
        for part, w in (heat or {}).items():
            q[self.terms[part]] += w
        self.T = self.lu.solve(self.c_dt * self.T + q)
        return self.T


def funnel(c, s):
    """The via of the unit solution s that carries the largest share of the
    current: (hole index, share, its nodes, a mask of the edges inside it)."""
    hi, share = max(dcflow.barrel_currents(c, s), key=lambda x: x[1])
    a, b, _ = s.info['edges']
    nodes = [nd for h, nn in s.info['barrels'] if h == hi for _, nd in nn]
    return hi, share, nodes, np.isin(a, nodes) & np.isin(b, nodes)


def crash(c, src, ph, fet, sense, T0, vth, share_scale=1.0, n_cut=N_CUT):
    """One jammed-rotor run from start temperature T0 with the VDS monitor
    at vth volts (None: never trips).  src, ph: unit solutions of the low-side
    FET's source net (to the shunt) and phase net (motor pad to its drain).
    share_scale < 1 spreads the funnel via's share as if more vias stood
    beside it (its edges carry that fraction of their current; the rest is
    taken to find paths as short).  n_cut: back-EMF timeouts before AM32's
    stuck-rotor cut."""
    t_cut = n_cut * T_BEMF
    V, r_pack, limit = data.BATTERY['vfull'], data.BATTERY['r'], data.AM32['current_limit']
    times = np.arange(0, t_cut + 2e-3, DT)
    N = len(times)
    Z = zth(np.arange(N) * DT + 1e-7)
    _, share, via_nodes, in_via = funnel(c, src)
    hs = Heat(c, src, T0, DT * EVERY, np.where(in_via, share_scale, 1.0))
    hp = Heat(c, ph, T0, DT * EVERY)
    i2, p_fet = 0.0, 0.0
    case_node = ph.info['terms'][fet + 'L']
    r_ls, r_hs = sense[0] * cu(T0), sense[1] * cu(T0)
    P_ls, P_hs, dP_ls, dP_hs = np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)
    I, TJ = np.zeros(N), np.zeros(N)
    tj_ls = tj_hs = t_case = T0
    adj, d_bemf, err_last = 1.0, None, 0.0
    readings, acc, n_acc, next_pid = [], 0.0, 0, T_PID
    off_until, trips, first = -1, 0, None
    peak = dict(via=T0, case=T0, ls=T0, hs=T0, over=0.0)
    for k, t in enumerate(times):
        # AM32: its current loop on the averaged battery current, then the
        # back-EMF timeout's clamp
        if t >= next_pid:
            next_pid += T_PID
            readings.append(acc / max(n_acc, 1))
            acc, n_acc = 0.0, 0
            err = sum(readings[-N_AVG:]) / N_AVG - limit         # the buffer starts empty: zeros
            adj = min(1.0, max(D_MIN, adj - pid_step(err, err_last)))
            err_last = err
        D = adj
        if t >= T_BEMF:
            d_bemf = D if d_bemf is None else d_bemf
            D = min(D, max(D_STARTUP, d_bemf - RAMP * (t - T_BEMF)))
        i = 0.0 if t >= t_cut else D * V / (
            R_MOTOR + rds_max(tj_ls) + rds_max(tj_hs) + R_SHUNT + R_COPPER + D * D * r_pack)
        # the driver's monitor
        if k < off_until:
            i = 0.0
        elif vth is not None and i > 0:
            v_ls = i * (rds_max(tj_ls) + r_ls)
            v_hs = i * (rds_max(tj_hs) + r_hs) if D / data.AM32['f_min'] >= T_SEEN else 0.0
            if max(v_ls, v_hs) > vth:
                trips += 1
                off_until = k + 1 + int(round(T_RETRY / DT))   # this step on (the deglitch), then off
                if first is None:
                    first = (t, i, 'low' if v_ls >= v_hs else 'high')
        I[k] = i
        acc += D * i
        n_acc += 1
        P_ls[k] = i * i * rds_max(tj_ls)
        P_hs[k] = D * i * i * rds_max(tj_hs)
        dP_ls[k] = P_ls[k] - (P_ls[k - 1] if k else 0.0)
        dP_hs[k] = P_hs[k] - (P_hs[k - 1] if k else 0.0)
        rev = Z[k::-1]
        tj_ls = t_case + float(np.dot(dP_ls[:k + 1], rev))
        tj_hs = T0 + float(np.dot(dP_hs[:k + 1], rev))
        i2 += i * i / EVERY
        p_fet += P_ls[k] / EVERY
        if (k + 1) % EVERY == 0:
            Ts = hs.step(i2)
            t_case = float(hp.step(i2, {fet + 'L': p_fet})[case_node])
            i2, p_fet = 0.0, 0.0
            pv = float(Ts[via_nodes].max())
            peak['via'] = max(peak['via'], pv)
            peak['over'] += DT * EVERY if pv > T_LIFT else 0.0
            peak['case'] = max(peak['case'], t_case)
        peak['ls'] = max(peak['ls'], tj_ls)
        TJ[k] = tj_ls
        peak['hs'] = max(peak['hs'], tj_hs)
    on = I > 0
    return dict(peak, i_max=float(I.max()), i_via=float(I.max() * share * share_scale), trips=trips,
                first=first, on_first_ms=float(on[times < T_BEMF].mean()),
                i_held=float(np.median(I[(times > t_cut - 20e-3) & (times < t_cut)])),
                over_rating=float(np.sum(TJ > data.FET['tch_max']) * DT))


def deg(T):
    """A temperature for the report: past 300 C the part is gone and the
    model's numbers (straight-line RDS(on), no melting) mean nothing."""
    return '%.0f C' % T if T < 300 else 'over 300 C'


def hot_start():
    """The hottest FET of the hard 3-minute flight on a 50 C day, from
    stress.py's numbers for this variant (or for the design)."""
    for name in (VARIANT, data.design_name()):
        p = os.path.join(RESULTS, 'variants', name or '', 'found.json')
        if name and os.path.exists(p):
            return float(json.load(open(p))['found']['flight']['fet']), name
    raise SystemExit('no sim/results/variants/%s/found.json: run stress.py --variant=%s first' % (
        VARIANT or data.design_name(), VARIANT or data.design_name()))


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
    frac, n, y, src = worst
    fet = 'Q%d%s' % (n, y)
    ph = dcflow.solve(c, 'M%d_%s' % (n, y), {'P_M%d%s' % (n, y): 1.0, fet + 'L': -1.0}, T=20.0)
    sense = sense_copper(c, n, y)
    T_hot, hot_from = hot_start()
    hi = funnel(c, src)[0]
    lines = ['# Ridge 3 ESC: a motor jammed at full throttle', '',
             'Generated by `sim/crash.py` on %s.  %s, 6S full (%.1f V), FET %s, AM32 current limit %.0f A.  '
             'The worst low-side FET for its source copper is %sL: %.0f %% of its current goes through one '
             '%.2f mm via.  The hot start is the hottest FET of the hard 3-minute flight on a 50 C day '
             '(`stress.py`, %s): %.0f C.' % (
                 time.strftime('%Y-%m-%d'), VARIANT or data.design_name(), data.BATTERY['vfull'],
                 data.FET['part'], data.AM32['current_limit'], fet, 100 * frac, c.holes[hi]['d'],
                 hot_from, T_hot), '',
             '## What the driver\'s overcurrent monitor trips at', '',
             'The DRV8320H measures each FET with board copper in series: on %s, %.2f mOhm for the low side '
             '(SLx below its source, its drain below SHx) and %.2f mOhm for the high side (its drain below '
             'VDRAIN, SHx below its source), at 20 C with only this phase\'s current flowing.  Trip current, '
             'low side, FET and copper at the temperature given:' % (fet, sense[0] * 1e3, sense[1] * 1e3), '',
             '| FET at | 0.6 V (as built), max / typical RDS(on) | 0.26 V (75k), max / typical RDS(on) |',
             '|---|---|---|']
    for T in (25.0, 100.0, T_hot, 150.0):
        lines.append('| %.0f C | %.0f / %.0f A | %.0f / %.0f A |' % (
            T, trip_current(0.6, T, sense[0]), trip_current(0.6, T, sense[0], rds_typ),
            trip_current(0.26, T, sense[0]), trip_current(0.26, T, sense[0], rds_typ)))
    lines += ['', '## The crash', '',
              'AM32 as it ships cuts a stalled motor after %d back-EMF timeouts (%.0f ms); the rows marked %d '
              'are the same with its `bemf_timeout` at %d, a change to the target (%.0f ms).' % (
                  N_CUT, N_CUT * T_BEMF * 1e3, N_CUT_SHORT, N_CUT_SHORT - 1, N_CUT_SHORT * T_BEMF * 1e3), '',
              '| Start | DRV8320H VDS pin | AM32 cuts after | Via share | Trips | Peak phase current | Current '
              'held until the cut | Hottest via copper | Time above 288 C | Low-side FET case (drain copper) | '
              'Hottest FET junction, low / high side | Low side above its rating |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|']
    runs = {}
    cases = [(name, vth, scale, label, n_cut) for name, vth in OCP.items()
             for scale, label in ((1.0, 'as built'), (0.5, 'half (about twice the vias)'))
             for n_cut in (N_CUT, N_CUT_SHORT)
             if (vth is None and n_cut == N_CUT) or (vth is not None and scale == 1.0)]
    for start, T0 in (('cold board (25 C)', 25.0), ('hot board (%.0f C)' % T_hot, T_hot)):
        for ocp_name, vth, scale, label, n_cut in cases:
            r = crash(c, src, ph, fet, sense, T0, vth, scale, n_cut)
            runs[(T0, ocp_name, scale, n_cut)] = r
            trips = ('none' if not r['trips'] else '%d, first at %.2f ms (%s side, %.0f A)' % (
                r['trips'], r['first'][0] * 1e3, r['first'][2], r['first'][1]))
            lines.append('| ' + ' | '.join([
                start, ocp_name, '%d (%.0f ms)' % (n_cut, n_cut * T_BEMF * 1e3), label, trips,
                '%.0f A' % r['i_max'], '%.0f A' % r['i_held'],
                deg(r['via']), '%.1f ms' % (r['over'] * 1e3), deg(r['case']),
                '%s / %s' % (deg(r['ls']), deg(r['hs'])), '%.0f ms' % (r['over_rating'] * 1e3)]) + ' |')
            print(lines[-1], flush=True)
    lines += ['', 'A trip lets the current flow for one 20 us step (the 4 us deglitch, rounded up), then '
              'holds every FET off for 4 ms.  The copper gives heat to the FR-4 against it and to nothing '
              'else (not the planes of other nets, not the heatsink): real temperatures are lower.  The '
              'low-side FET\'s case is its drain copper with all of the FET\'s heat in it and none leaving '
              'through its source.  Limits: pads lift and FR-4 '
              'decomposes from about 288 C; SAC305 solder melts at 217 C; copper melts at 1085 C; the FET\'s '
              'junction is rated %.0f C.'
              % data.FET['tch_max'], '', '---', 'Run time %.0f s.' % (time.time() - t0)]
    open(os.path.join(OUT, 'CRASH.md'), 'w').write('\n'.join(lines) + '\n')
    json.dump({'%s|%s|%s|%s' % k: v for k, v in runs.items()}, open(os.path.join(OUT, 'crash.json'), 'w'),
              indent=1, default=str)
    print('\n'.join(lines))


VARIANT = None

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument('--variant', choices=list(data.VARIANTS), metavar='NAME',
                    help='rev 2 with one change: %s' % ', '.join(data.VARIANTS))
    VARIANT = ap.parse_args().variant
    if VARIANT:
        data.variant(VARIANT)
        OUT = os.path.join(OUT, VARIANT)
    run()
