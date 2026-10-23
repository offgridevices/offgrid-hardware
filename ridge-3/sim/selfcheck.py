# -*- coding: utf-8 -*-
"""Checks of the copper solver (dcflow.py) and of how copper.py draws a
board onto its grid, against shapes whose answer is known.  stress.py runs
them with every report and quotes the numbers.

  * a straight strip and a ring (annulus), cells drawn where their centre
    lies inside the shape: the solver's resistance against the closed form
    (the strip's rho L / (w t), the ring's rho ln(r2 / r1) / (2 pi t));
  * a straight track drawn the way copper.py draws a board (PIL's polygon
    fill, which takes in the cells an edge runs along), at ten offsets
    across one cell: how much wider the grid draws it than it is.  The
    board's thin tracks come out wider, so their resistance and current
    density read low; pours millimetres wide barely change.

    sim/.venv/bin/python sim/selfcheck.py
"""
import math
import numpy as np

import copper, dcflow

T_CU = 0.035          # mm: 1 oz, the outer layers of both boards


class Sheet:
    """One layer of copper on a grid, just enough of copper.Copper for
    dcflow: cells where `inside(X, Y)` holds, terminals by cell selection."""
    def __init__(self, bounds, inside, res, tag, pad=0.2):
        x0, y0, x1, y1 = bounds
        self.res = res
        self.x0, self.y0 = x0 - pad, y0 - pad
        self.nx = int(math.ceil((x1 - x0 + 2 * pad) / res))
        self.ny = int(math.ceil((y1 - y0 + 2 * pad) / res))
        iy, ix = np.mgrid[0:self.ny, 0:self.nx]
        self.X, self.Y = self.x0 + (ix + 0.5) * res, self.y0 + (iy + 0.5) * res
        self.mask = inside(self.X, self.Y)
        self.owner = np.where(self.mask, 0, -1)[None].astype(np.int32)
        self.nets, self.layers, self.t, self.zc = ['N'], ['L'], [T_CU], [T_CU / 2]
        self.holes, self.terminals = [], {}
        self.path = 'selfcheck-%s-%g' % (tag, res)

    def net(self, name):
        return 0

    def terminal(self, ref, sel):
        self.terminals[(ref, 'N')] = dict(ref=ref, net='N', cells={0: np.flatnonzero((sel & self.mask).ravel())},
                                          pads=['1'])


def _resistance(c, near, far, I=1.0):
    """Ohms between the cells where near() and far() hold, with 1 A in at
    terminal A and out at B."""
    s = dcflow.solve(c, 'N', {'A': I, 'B': -I}, T=20.0, net_cache={})
    ids, m = s.info['ids'][0], s.info['mask'][0]
    V = np.full(m.shape, np.nan)
    V[m] = s.V[ids[m]]
    v = lambda sel: float(np.nanmean(np.where(sel & m, V, np.nan)))
    return (v(near) - v(far)) / I


def strip(res, w=0.3, length=4.0):
    """Percent error of the solver on a straight strip, between 1 and 3 mm."""
    c = Sheet((0, -w / 2, length, w / 2), lambda X, Y: (np.abs(Y) < w / 2) & (X > 0) & (X < length), res, 'strip')
    c.terminal('A', c.X < 0.15)
    c.terminal('B', c.X > length - 0.15)
    band = lambda u: np.abs(c.X - u) < res * 0.75
    r = _resistance(c, band(1.0), band(3.0))
    exact = dcflow.rho(20.0) * 2.0e-3 / (w * 1e-3 * T_CU * 1e-3)
    return 100 * (r / exact - 1)


def ring(res, a=0.5, b=2.0):
    """Percent error of the solver on a ring, between radii 0.8 and 1.6 mm."""
    c = Sheet((-b, -b, b, b), lambda X, Y: (np.hypot(X, Y) > a) & (np.hypot(X, Y) < b), res, 'ring')
    r = np.hypot(c.X, c.Y)
    c.terminal('A', r < a + 0.1)
    c.terminal('B', r > b - 0.1)
    band = lambda q: np.abs(r - q) < res * 0.75
    rr = _resistance(c, band(0.8), band(1.6))
    exact = dcflow.rho(20.0) * math.log(1.6 / 0.8) / (2 * math.pi * T_CU * 1e-3)
    return 100 * (rr / exact - 1)


def drawn_width(w, res, offsets=10):
    """(least, most) width the grid draws a straight w-mm track at, over
    `offsets` positions across one cell, as copper.py draws a board."""
    out = []
    for k in range(offsets):
        y0 = 1.0 + k * res / offsets
        poly = [(0.5, y0), (2.5, y0), (2.5, y0 + w), (0.5, y0 + w)]
        m = copper._mask([np.array(poly)], 0.0, 0.0, res, (int(4 / res), int(3 / res)))
        out.append(m[:, int(1.5 / res)].sum() * res)
    return min(out), max(out)


def run(res=0.05, widths=(0.1, 0.2, 0.3, 0.5)):
    dcflow.forget()
    return dict(res=res, strip=strip(res), ring=ring(res),
                drawn={w: drawn_width(w, res) for w in widths})


if __name__ == '__main__':
    r = run()
    print('grid %.3f mm: strip %+.2f %%, ring %+.2f %%' % (r['res'], r['strip'], r['ring']))
    for w, (lo, hi) in r['drawn'].items():
        print('  a %.2f mm track is drawn %.2f-%.2f mm wide' % (w, lo, hi))
