# -*- coding: utf-8 -*-
"""Where the motor current heats the ESC's copper, per amp squared.

The ESC drives each motor in six steps.  In each, one phase X is switched
(its high-side FET on for the duty D, its low side for the rest) and one
phase Y is held low; the third floats.  So the copper carries:

  VBAT       battery pad -> X's high-side drain, during D
  phase X    high-side source -> motor pad during D, low-side drain -> pad after
  phase Y    motor pad -> low-side drain, all the step
  SRC        Y's low-side source -> shunt during D; X's low side -> Y's after
  GND        shunt -> battery pad, during D

dcflow solves each of those paths at 1 A (at 20 C); a path carrying I for a
fraction d of the time heats each cell by d I^2 times its 1 A loss.  The
steps are averaged (each phase is X, Y and floating a third of the time
each).  The four channels share VBAT and GND; they are solved together with
their PWM in step, which is the worst case for those planes.

All maps are per fine copper cell (W at 1 A, 20 C), per layer.
"""
import os, hashlib, pickle
import numpy as np
import dcflow

PH = 'ABC'
STEPS = [(x, y) for x in PH for y in PH if x != y]
CH = (1, 2, 3, 4)


def _key(c):
    return hashlib.sha1(open(c.path, 'rb').read() + b'copperloss-v4').hexdigest()[:12]


_loaded = {}


def unit_maps(c, out_dir):
    """dict of 1 A loss maps and path figures for the ESC, cached on disk and
    held once in memory (each map is a full-board float32 array)."""
    cache = os.path.join(out_dir, 'copperloss-%s.pkl' % _key(c))
    if cache in _loaded:
        return _loaded[cache]
    if os.path.exists(cache):
        _loaded[cache] = pickle.load(open(cache, 'rb'))
        return _loaded[cache]
    shape = c.owner.shape
    res = dict(paths={})

    def run(net, cur):
        s = dcflow.solve(c, net, cur, T=20.0)
        m = dcflow.maps(c, s)
        return s, m

    # battery planes, all four channels at 1 A each, averaged over the high-side phase
    for net, pad in (('VBAT', 'P_BAT+'), ('GND', 'P_BAT-')):
        acc = np.zeros(shape); jmax = np.zeros(shape)
        vias = {}
        drops = []
        phases = PH if net == 'VBAT' else 'A'
        for x in phases:
            if net == 'VBAT':
                cur = {'Q%d%sH' % (n, x): -1.0 for n in CH}
                cur[pad] = 4.0
            else:
                cur = {'R_SH%d' % n: 1.0 for n in CH}
                cur[pad] = -4.0
            s, m = run(net, cur)
            acc += m['W'] / len(phases)
            jmax = np.maximum(jmax, m['J'])
            for hi, a in dcflow.barrel_currents(c, s):
                vias[hi] = max(vias.get(hi, 0), a)
            for part, v in s.term_v.items():
                if part != pad and part in cur:
                    drops.append((part, abs(v - s.term_v[pad])))
        res[net] = acc
        res['paths'][net] = dict(J=jmax, vias=vias, drops=drops, R=float(acc.sum()) / 16)
    # per channel: phases and the sense node
    for n in CH:
        for p in PH:
            net = 'M%d_%s' % (n, p)
            s1, m1 = run(net, {'Q%d%sH' % (n, p): 1.0, 'P_M%d%s' % (n, p): -1.0})   # high side on
            s2, m2 = run(net, {'P_M%d%s' % (n, p): 1.0, 'Q%d%sL' % (n, p): -1.0})   # low side on
            res['M%d%s_hs' % (n, p)] = m1['W']
            res['M%d%s_ls' % (n, p)] = m2['W']
            res['paths'][net] = dict(R_hs=s1.loss, R_ls=s2.loss,
                                     vias=dict(dcflow.barrel_currents(c, s2)),
                                     J=np.maximum(m1['J'], m2['J']))
        net = 'M%d_SRC' % n
        for y in PH:
            s, m = run(net, {'Q%d%sL' % (n, y): 1.0, 'R_SH%d' % n: -1.0})
            res['M%d_src_%s' % (n, y)] = m['W']
            res['paths'].setdefault(net, {})['R_' + y] = s.loss
        for x, y in STEPS:
            s, m = run(net, {'Q%d%sL' % (n, y): 1.0, 'Q%d%sL' % (n, x): -1.0})
            res['M%d_fw_%s%s' % (n, x, y)] = m['W']
    for k, v in res.items():
        if isinstance(v, np.ndarray):
            res[k] = v.astype(np.float32)
    os.makedirs(out_dir, exist_ok=True)
    pickle.dump(res, open(cache, 'wb'))
    _loaded[cache] = res
    return res


def coarse(u, f, ny, nx):
    """The maps summed onto a coarser grid (f fine cells a side), for the heat model."""
    out = {}
    for k, v in u.items():
        if isinstance(v, np.ndarray) and v.ndim == 3:
            out[k] = v[:, :ny * f, :nx * f].reshape(v.shape[0], ny, f, nx, f).sum(axis=(2, 4), dtype=np.float64)
    return out


def loss_map(u, I, D):
    """Average copper loss per fine cell (W at 20 C): I[n] phase amps, D[n] duty."""
    W = np.zeros_like(u['VBAT'])
    # shared planes: channels in step (worst case), bus current I*D on average, I while on
    Ieq = np.sqrt(np.mean([D[n] for n in CH])) * np.mean([I[n] for n in CH])
    W += (u['VBAT'] + u['GND']) * Ieq ** 2
    for n in CH:
        i2, d = I[n] ** 2, D[n]
        for p in PH:
            # a third of the time the switched phase X, a third the low phase Y
            W += i2 / 3 * (d * u['M%d%s_hs' % (n, p)] + (1 - d) * u['M%d%s_ls' % (n, p)])
            W += i2 / 3 * u['M%d%s_ls' % (n, p)]
        for x, y in STEPS:
            W += i2 / 6 * (d * u['M%d_src_%s' % (n, y)] + (1 - d) * u['M%d_fw_%s%s' % (n, x, y)])
    return W


def loss_groups(u, I, D):
    """The same loss as loss_map, in watts (20 C) per kind of copper."""
    Ieq2 = np.mean([D[n] for n in CH]) * np.mean([I[n] for n in CH]) ** 2
    out = {'battery plane (VBAT)': float(u['VBAT'].sum()) * Ieq2,
           'ground plane (GND)': float(u['GND'].sum()) * Ieq2, 'phase copper': 0.0, 'sense nodes': 0.0}
    for n in CH:
        i2, d = I[n] ** 2, D[n]
        for p in PH:
            out['phase copper'] += i2 / 3 * (d * u['M%d%s_hs' % (n, p)].sum() + (1 - d) * u['M%d%s_ls' % (n, p)].sum()
                                             + u['M%d%s_ls' % (n, p)].sum())
        for x, y in STEPS:
            out['sense nodes'] += i2 / 6 * (d * u['M%d_src_%s' % (n, y)].sum() + (1 - d) * u['M%d_fw_%s%s' % (n, x, y)].sum())
    return {k: float(v) for k, v in out.items()}
