# -*- coding: utf-8 -*-
"""Mini-Circuits LFCN-1000+ as a lumped 7-section elliptic low-pass model.

Mini-Circuits publishes for this part only a typical table (insertion loss
and VSWR at 15 frequencies, data sheet REV. R, "Typical performance data at
25 C") and graphs; no S-parameter file was found for it.  A cascade
needs phase as well as magnitude, so the filter is modelled as a physical
ladder (shunt C with a common ground inductance, three series parallel-LC
traps, finite Q) whose element values were fitted to that table with
scipy least squares (`python3 lfcn.py --fit` re-runs the fit, ~3 min).

Fit quality (printed by run.py in results.txt): insertion loss within
0.1 dB to 1.3 GHz and within 1 dB from 1.5 to 5.1 GHz; 2.7-3 dB off at
5.5-6 GHz, where the real part re-enters.  The model's stop-band VSWR is
higher (more reflective) than the table's 30-60:1, which makes the
filter-to-filter interaction in study 1 slightly pessimistic.
"""
import sys

import numpy as np

import rflib as R

F_TAB = np.array([50, 500, 1000, 1275, 1500, 2000, 2750, 3250, 4000, 4600, 5125, 5500, 6000, 6500, 7000]) * 1e6
IL_TAB = np.array([0.01, 0.30, 0.80, 3.33, 25.87, 49.50, 39.80, 43.45, 43.25, 43.25, 43.11, 22.76, 15.24, 19.30, 18.56])
VSWR_TAB = np.array([1.01, 1.05, 1.21, 2.23, 17.57, 34.75, 59.91, 51.10, 52.65, 59.91, 41.37, 34.75, 29.46, 62.05, 69.49])

# C1, L2, C2, C3, L4, C4, C5, L6, C6, C7, L_gnd (each shunt C), Q of the inductors
FIT = [4.38387209e-13, 1.10089480e-09, 8.56911372e-13, 1.26596153e-12, 4.25623688e-09, 2.47833158e-12,
       2.79038702e-12, 5.48256696e-09, 1.19473569e-12, 1.66158962e-12, 1.00000000e-09, 1.90432857e+01]


def add(ckt, a, b, prefix='FL_', k=1.0, p=None, rscale=1.0):
    """Insert the filter between nodes a (RF IN) and b (RF OUT).  k scales frequency
    (all L and C divided by k); rscale scales the inductor loss."""
    C1, L2, C2, C3, L4, C4, C5, L6, C6, C7, Le, Q = p if p is not None else FIT
    k = np.asarray(k, dtype=float)
    n1, n2 = prefix + 'n1', prefix + 'n2'
    for node, c in ((a, C1), (n1, C3), (n2, C5), (b, C7)):
        ckt.add(node, 'GND', R.Cap(c / k, 0.05, Le / k), prefix + 'C')
    for x, y, l, c in ((a, n1, L2, C2), (n1, n2, L4, C4), (n2, b, L6, C6)):
        ckt.add(x, y, R.Ind(l / k, Q, 1e9, 0, 0.0, rscale=rscale), prefix + 'L')
        ckt.add(x, y, R.Cap(c / k, 0.05, 0.0), prefix + 'Ct')
    return ckt


def response(f, p=None, k=1.0):
    c = R.Circuit('lfcn')
    add(c, 'a', 'b', p=p, k=k)
    return c.sparams(f, ['a', 'b'])[0]


def fit():
    from scipy.optimize import least_squares

    def resid(lp):
        S = response(F_TAB, p=np.exp(lp))
        il = -R.db20(S[:, 1, 0])
        g = np.abs(S[:, 0, 0])
        vs = (1 + g) / (1 - g)
        r1 = (il - IL_TAB) * np.where(F_TAB < 1.3e9, 6.0, 1.0) / np.where(IL_TAB > 10, 4, 0.5)
        r2 = np.log(vs / VSWR_TAB) * np.where(F_TAB < 1.3e9, 8, 0.5)
        return np.concatenate([r1, r2])

    lo = np.log([0.2e-12, 1e-9, 0.05e-12, 0.2e-12, 1e-9, 0.05e-12, 0.2e-12, 1e-9, 0.05e-12, 0.2e-12, 0.02e-9, 15])
    hi = np.log([10e-12, 30e-9, 3e-12, 15e-12, 30e-9, 3e-12, 15e-12, 30e-9, 3e-12, 10e-12, 1e-9, 200])
    p0 = np.log([2.5e-12, 7e-9, 0.6e-12, 5e-12, 9e-9, 0.4e-12, 5e-12, 7e-9, 0.6e-12, 2.5e-12, 0.25e-9, 40])
    rng = np.random.default_rng(1)
    best = None
    for i in range(40):
        r = least_squares(resid, p0 + (rng.normal(0, 0.3, len(p0)) if i else 0), bounds=(lo, hi))
        if best is None or r.cost < best.cost:
            best = r
    return list(np.exp(best.x))


if __name__ == '__main__':
    if '--fit' in sys.argv:
        print(fit())


# ----------------------------------------------------------------------------- LFCG-1000+
# Mini-Circuits LFCG-1000+ (0805 LTCC, case GE0805C-2), typical table at 25 C from its data sheet:
# frequency (MHz), insertion loss (dB), return loss (dB).  Used by followup.py (6f-10f fix).
G_F_TAB = np.array([10, 100, 1000, 1370, 1450, 1510, 1550, 1750, 1900, 2000, 2500, 3000, 4000, 5000, 6000, 7000,
                    7500, 8000, 9000, 10000]) * 1e6
G_IL_TAB = np.array([0.12, 0.18, 0.74, 3.39, 9.47, 20.39, 31.51, 42.02, 59.59, 52.69, 49.74, 44.29, 38.87, 37.65, 37.95,
                     37.04, 49.61, 48.29, 45.40, 40.34])
G_RL_TAB = np.array([39.37, 30.94, 23.43, 11.65, 7.28, 4.42, 3.12, 1.00, 0.65, 0.53, 0.32, 0.24, 0.14, 0.09, 0.11, 0.24,
                     0.27, 0.29, 0.32, 0.32])
G_FIT = None    # filled from fit_lfcg() output below


def fit_table(ftab, iltab, vswrtab, lo_le=0.02e-9, hi_le=1e-9, seed=1, n=40):
    from scipy.optimize import least_squares

    def resid(lp):
        S = response(ftab, p=np.exp(lp))
        il = -R.db20(S[:, 1, 0])
        g = np.abs(S[:, 0, 0])
        vs = (1 + g) / (1 - g)
        r1 = (il - iltab) * np.where(ftab < 1.3e9, 6.0, 1.0) / np.where(iltab > 10, 4, 0.5)
        r2 = np.log(vs / vswrtab) * np.where(ftab < 1.3e9, 8, 0.3)
        return np.concatenate([r1, r2])

    lo = np.log([0.2e-12, 1e-9, 0.05e-12, 0.2e-12, 1e-9, 0.05e-12, 0.2e-12, 1e-9, 0.05e-12, 0.2e-12, lo_le, 15])
    hi = np.log([10e-12, 30e-9, 3e-12, 15e-12, 30e-9, 3e-12, 15e-12, 30e-9, 3e-12, 10e-12, hi_le, 200])
    p0 = np.log([2.5e-12, 7e-9, 0.6e-12, 5e-12, 9e-9, 0.4e-12, 5e-12, 7e-9, 0.6e-12, 2.5e-12, 0.05e-9, 40])
    rng = np.random.default_rng(seed)
    best = None
    for i in range(n):
        r = least_squares(resid, np.clip(p0 + (rng.normal(0, 0.3, len(p0)) if i else 0), lo + 1e-9, hi - 1e-9),
                          bounds=(lo, hi))
        if best is None or r.cost < best.cost:
            best = r
    return list(np.exp(best.x))


def fit_lfcg():
    g = 10 ** (-G_RL_TAB / 20)
    return fit_table(G_F_TAB, G_IL_TAB, (1 + g) / (1 - g))


if __name__ == '__main__' and '--fit-lfcg' in sys.argv:
    print(fit_lfcg())
