# -*- coding: utf-8 -*-
"""Re-tune the 5th-order elliptic harmonic filter (LPF1) for parts that survive 3 W.

Why (results.txt, studies 2 and 7): with the part models, the drawn filter's
notches sit at ~1.70 and ~2.43 GHz instead of 1.83 / 2.75 GHz (inductor
self-capacitance and capacitor ESL), and its 0402/0603 wire-wound inductors
dissipate 1.3-4x the heat of their rated current at 3 W.

Same topology and part count (3 shunt C, two series L||C traps).  Series
inductors are chosen among Murata LQW2BAN 0805 wire-wound parts stocked at
DigiKey (3.2 / 3.6 / 6.8 nH, 2-3.8 A, Q 75-95, SRF 6-14 GHz); capacitors
are Murata GQM 0603 250 V.  The search evaluates the WHOLE transmit chain
exactly as run.py does (PA source model, switch, LFCN model, traces, ESD
shunt) and maximises the worst harmonic margin at 35 dBm / 6 dBi over
n = 2..8 (the LFCN data stop at 7 GHz, so 9f and 10f are not used), at the
inductor tolerance corners, with in-band loss and PA-load return loss as
penalties.  Capacitors are then snapped to 0.1 pF.

    tools/kd python3 sim/rf/design_lpf.py      # ~10 min; prints the best designs
"""
import itertools
import os
import sys

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rflib as R     # noqa: E402
import rfboard as B   # noqa: E402
import run            # noqa: E402

LQW2BAN = {'LQW2BAN3N2J00L': 3.2, 'LQW2BAN3N6J00L': 3.6, 'LQW2BAN6N8J00L': 6.8}
NS = (2, 3, 4, 5, 6, 7, 8)
PA = run.PA(3.6)
RS = run.refs_between


def overrides(caps, l2, l4, ls=(1.0, 1.0)):
    def cap(v):
        return dict(mpn='GQM1875C2EXXXBB12D', kind='C', value='%.4fpF' % v, desc='0603')

    def ind(mpn, v):
        return dict(mpn=mpn, kind='L', value='%.4fnH' % v, desc='0805')
    k = lambda r: B.parts.PARTS[B.BY_REF[r].part]['kind']
    ov = {RS('PA_M2', 'GND')[0]: cap(caps[0]), RS('PA_M3', 'GND')[0]: cap(caps[2]), RS('PA_TX', 'GND')[0]: cap(caps[4])}
    for r in RS('PA_M2', 'PA_M3'):
        ov[r] = ind(l2, LQW2BAN[l2] * ls[0]) if k(r) == 'L' else cap(caps[1])
    for r in RS('PA_M3', 'PA_TX'):
        ov[r] = ind(l4, LQW2BAN[l4] * ls[1]) if k(r) == 'L' else cap(caps[3])
    # the output-match 3.6 nH is also changed to LQW2BAN3N6J00L (run.py fix list)
    ov[RS('PA_OUT', 'PA_M1')[0]] = ind('LQW2BAN3N6J00L', 3.6)
    return ov


def evaluate(caps, l2, l4, corners=((1, 1), (0.95, 0.95), (1.05, 1.05))):
    worst, loss, rl = 99.0, 0.0, 99.0
    per_n = {n: 99.0 for n in NS}
    for ls in corners:
        b = B.Board(overrides=overrides(caps, l2, l4, ls))
        S = b.tx_out(with_pa=False).sparams(run.FB, ['PA_M2', 'ANT'])[0]
        il = -R.db20(S[:, 1, 0])
        loss, rl = max(loss, il.max()), min(rl, R.rl_db(S[:, 0, 0]).min())
        rej = run.harmonic_rejection(b, PA)
        lv = run.harm_levels(rej, 35.0, float(il.min()))
        m = run.harm_margins(lv, 35.0, 6.0)
        for n in NS:
            per_n[n] = min(per_n[n], float(min(m[n]['fcc'][0], m[n]['ham'][0])))
    return min(per_n.values()), loss, rl, per_n


def cost(x, l2, l4):
    caps = np.exp(x)
    if np.any(caps < 0.1) or np.any(caps > 8):
        return 1e3
    w, loss, rl, _ = evaluate(caps, l2, l4)
    return -min(w, 15) + 100 * max(0, loss - 1.15) + 2 * max(0, 18 - rl)


def cost2(x, l2, l4):
    """2f-5f (where the data are) must keep >= 8 dB; then maximise the worst of all."""
    caps = np.exp(x)
    if np.any(caps < 0.1) or np.any(caps > 8):
        return 1e3
    w, loss, rl, pn = evaluate(caps, l2, l4)
    lo = min(pn[n] for n in (2, 3, 4, 5))
    return -min(w, 15) + 3 * max(0, 8 - lo) + 100 * max(0, loss - 1.15) + 2 * max(0, 18 - rl)


def main():
    res = []
    starts = {('LQW2BAN6N8J00L', 'LQW2BAN6N8J00L'): [2.6, 0.9, 4.3, 0.6, 1.8],
              ('LQW2BAN3N2J00L', 'LQW2BAN3N6J00L'): [1.7, 1.9, 0.6, 0.2, 1.1],
              ('LQW2BAN3N6J00L', 'LQW2BAN6N8J00L'): [1.9, 1.9, 4.4, 0.3, 3.8]}
    combos = [('LQW2BAN3N2J00L', 'LQW2BAN3N2J00L'), ('LQW2BAN3N2J00L', 'LQW2BAN3N6J00L'), ('LQW2BAN3N6J00L', 'LQW2BAN3N2J00L'),
              ('LQW2BAN3N6J00L', 'LQW2BAN3N6J00L'), ('LQW2BAN3N2J00L', 'LQW2BAN6N8J00L')]
    starts[('LQW2BAN3N2J00L', 'LQW2BAN3N2J00L')] = [1.9, 3.6, 1.3, 1.3, 0.9]
    starts[('LQW2BAN3N2J00L', 'LQW2BAN6N8J00L')] = [0.9, 1.9, 2.2, 0.3, 1.0]
    for l2, l4 in combos:
        L2, L4 = LQW2BAN[l2] * 1e-9, LQW2BAN[l4] * 1e-9
        x0 = starts.get((l2, l4), [3.0, 1e12 / ((2 * np.pi * 1.75e9) ** 2 * L2), 4.0, 1e12 / ((2 * np.pi * 2.6e9) ** 2 * L4), 2.5])
        r = minimize(cost2, np.log(x0), args=(l2, l4), method='Nelder-Mead',
                     options=dict(maxiter=400, xatol=1e-3, fatol=1e-2))
        caps = np.maximum(np.round(np.exp(r.x), 1), 0.2)
        w, loss, rl, per_n = evaluate(caps, l2, l4)
        res.append((w, l2, l4, caps, loss, rl, per_n))
        print('%s %s caps %s pF  loss %.2f dB  PA RL %.1f dB  worst margin %.1f  %s' % (
            l2, l4, caps, loss, rl, w, ' '.join('%df %.1f' % kv for kv in per_n.items())), flush=True)
    res.sort(key=lambda t: -t[0])
    print('\nbest:')
    for t in res[:3]:
        print(t)


if __name__ == '__main__':
    main()
