# -*- coding: utf-8 -*-
"""Temperatures of the stack: the FC over the ESC, in air.

Each board is a grid of square cells (h mm) on each of its copper layers.
A layer's cell conducts sideways through its copper (the fraction of the
cell the copper covers, from copper.py) and through its share of the glass
epoxy either side.  Layers conduct to each other through the dielectric and
through every via barrel and plated hole in the cell.  The outer faces lose
heat to the air by convection and to the surroundings by radiation.  The
ESC's top face and the FC's bottom face also exchange heat with each other,
across the air in the gap and by radiation.

Parts that matter get a junction node joined to the copper under their
pads through the junction-to-board resistance their datasheet gives.  Heat
goes in at those nodes (FETs, regulators, drivers, processors) or straight
into the cells under a part's pads (shunts), and into the copper itself
where current flows through it (dcflow.py).

Steady state is one sparse solve.  A transient steps backward Euler with
the losses re-evaluated from the last temperatures (on-resistance and copper
resistance rise with temperature).
"""
import numpy as np
import scipy.sparse as sp

SIGMA = 5.670e-8
K_CU = 390.0          # W/m K
K_FR4_XY = 0.8        # glass epoxy, in plane
K_FR4_Z = 0.3         # glass epoxy, through
K_AIR = 0.028         # at 60 C
K_AL = 167.0          # 6061-T6 aluminium, W/m K
RC_AL = 2.42e6        # 6061: 2700 kg/m3 x 896 J/kg K
RC_CU = 3.45e6        # J/m3 K
RC_FR4 = 2.0e6        # J/m3 K
PLATING = 20e-6       # via barrel wall, m


def air(v, T=50.0):
    """Convection over the stack with the air moving at v m/s (0: still air).

    Forced: a flat plate's laminar mean, h = 0.664 (k/L) Re^0.5 Pr^(1/3) over
    the 36 mm board, times data.AIR['enhance'] for the parts standing on it.
    The gap between the boards sees half the speed.  Still: natural
    convection, and the gap conducts through its air."""
    import data
    k, nu, pr, L = 0.0279, 1.79e-5, 0.71, 0.036       # air near 50 C
    def forced(u):
        return data.AIR['enhance'] * 0.664 * k / L * (u * L / nu) ** 0.5 * pr ** (1 / 3)
    if v <= 0:
        return dict(h_out=data.AIR['h_still'], h_gap=0.0, eps=data.AIR['eps'], still_gap=1.0, v=0.0)
    return dict(h_out=forced(v), h_gap=forced(v / 2), eps=data.AIR['eps'], still_gap=1.0, v=v)


class Grid:
    """One board's thermal grid, coarsened from a copper raster."""

    def __init__(self, c, h=0.25, plating=PLATING):
        f = max(1, int(round(h / c.res)))
        self.c, self.f, self.h = c, f, c.res * f
        ny, nx = c.ny // f, c.nx // f
        self.ny, self.nx, self.L = ny, nx, len(c.layers)
        blk = lambda a: a[..., :ny * f, :nx * f].reshape(a.shape[:-2] + (ny, f, nx, f)).mean(axis=(-3, -1))
        self.cover = blk((c.owner >= 0).astype(float))          # [L, ny, nx]
        self.inside = blk(c.inside.astype(float)) > 0.5
        # via / hole thermal conductance per cell, per dielectric gap
        self.gvia = np.zeros((self.L - 1, ny, nx))
        for hole in c.holes:
            iy, ix = int((hole['y'] - c.y0) / self.h), int((hole['x'] - c.x0) / self.h)
            if not (0 <= iy < ny and 0 <= ix < nx):
                continue
            lay = sorted(hole['layers'])
            for l1, l2 in zip(lay, lay[1:]):
                length = abs(c.zc[l2] - c.zc[l1]) * 1e-3
                d = hole['d'] * 1e-3
                if hole['kind'] == 'pad':        # soldered wire or pin fills it
                    area = np.pi * d * d / 4
                else:
                    area = np.pi * d * plating
                for g in range(l1, l2):
                    self.gvia[g, iy, ix] += K_CU * area / length * (l2 - l1)
        # node index for each (layer, cell) inside the board
        self.ids = -np.ones((self.L, ny, nx), np.int64)
        m = np.broadcast_to(self.inside, (self.L, ny, nx))
        self.n = int(m.sum())
        self.ids[m] = np.arange(self.n)

    def coarse(self, x, y):
        c = self.c
        return int((y - c.y0) / self.h), int((x - c.x0) / self.h)

    def cells(self, fine_idx):
        """Fine flat indices -> unique coarse (iy, ix) with weights (fraction of the pad)."""
        iy, ix = np.divmod(np.asarray(fine_idx), self.c.nx)
        iy, ix = iy // self.f, ix // self.f
        ok = (iy < self.ny) & (ix < self.nx)
        key, w = np.unique(iy[ok] * self.nx + ix[ok], return_counts=True)
        return np.divmod(key, self.nx), w / w.sum()


class Stack:
    """Boards bottom to top, gap in mm between neighbours; assembled network.

    plate (optional): a heatsink under the bottom board, one node per cell of
    that board's grid where plate['mask'] is set.  It conducts sideways
    through its base (k t), takes heat from the board's bottom copper through
    a gap pad over the whole mask (k_pad / t_pad), and loses it from its
    underside to the air (the fins' extra area times their efficiency) and by
    radiation (its emissivity).  The board's bottom face under it no longer
    sees the air."""

    def __init__(self, grids, gaps, air, T_amb, plate=None):
        """air: dict(h_out, h_gap, eps) convection W/m2K on outer faces and in the gaps."""
        self.grids, self.gaps, self.air, self.T_amb = grids, gaps, air, T_amb
        self.off = np.cumsum([0] + [g.n for g in grids])
        self.plate = plate
        self.plate_ids = None
        n = int(self.off[-1])
        if plate is not None:
            g = grids[0]
            m = np.asarray(plate['mask'], bool) & (g.ids[g.L - 1] >= 0)
            self.plate_ids = -np.ones((g.ny, g.nx), np.int64)
            self.plate_ids[m] = n + np.arange(int(m.sum()))
            n += int(m.sum())
        self.n = n
        self.rows, self.cols, self.vals = [], [], []
        self.gamb = np.zeros(self.n)          # conductance to ambient per node
        self.cap = np.zeros(self.n)
        self.junc = {}                         # (board index, ref) -> node
        self._build()

    def _link(self, a, b, g):
        self.rows.append(np.atleast_1d(a)); self.cols.append(np.atleast_1d(b))
        self.vals.append(np.broadcast_to(np.atleast_1d(g), np.atleast_1d(a).shape).astype(float))

    def _build(self):
        air = self.air
        Tm = 273.15 + self.T_amb + 50          # radiation linearised about 50 K above the air
        hr = 4 * SIGMA * Tm ** 3                # black-body linearised, W/m2K
        eps = air['eps']
        for bi, g in enumerate(self.grids):
            o = self.off[bi]
            c = g.c
            A = (g.h * 1e-3) ** 2
            for li in range(g.L):
                ids = g.ids[li]
                # sideways: copper by coverage (harmonic mean across the face) + glass
                tcu = c.t[li] * 1e-3
                share = 0.5 * ((c.diel[li - 1] if li > 0 else 0) + (c.diel[li] if li < g.L - 1 else 0)) * 1e-3
                kc = K_CU * tcu * g.cover[li] + K_FR4_XY * share
                for dy, dx in ((0, 1), (1, 0)):
                    a = ids[:g.ny - dy, :g.nx - dx]; b = ids[dy:, dx:]
                    ok = (a >= 0) & (b >= 0)
                    ka = kc[:g.ny - dy, :g.nx - dx][ok]; kb = kc[dy:, dx:][ok]
                    self._link(o + a[ok], o + b[ok], 2 * ka * kb / (ka + kb))
                self.cap[o + ids[ids >= 0]] += (RC_CU * tcu * g.cover[li][ids >= 0] + RC_FR4 * share) * A
                if li < g.L - 1:
                    b = g.ids[li + 1]
                    ok = (ids >= 0) & (b >= 0)
                    gz = K_FR4_Z * A / (c.diel[li] * 1e-3) + g.gvia[li]
                    self._link(o + ids[ok], o + b[ok], gz[ok])
            # outer faces: bottom face of the lowest board and top face of the highest
            # see the open air (the bottom one not where a heatsink covers it);
            # faces toward a neighbour see the gap.
            for li, facing in ((0, bi + 1 < len(self.grids)), (g.L - 1, bi > 0)):
                ids = g.ids[li]; ok = ids >= 0
                if bi == 0 and li == g.L - 1 and self.plate_ids is not None:
                    ok = ok & (self.plate_ids < 0)
                if not facing:
                    self.gamb[o + ids[ok]] += (air['h_out'] + eps * hr) * A
            if bi + 1 < len(self.grids):
                # gap to the board above: this board's top face (F.Cu side) to its bottom face
                up = self.grids[bi + 1]
                gap = self.gaps[bi] * 1e-3
                side = 36e-3
                F = _view_parallel(side, gap)
                a = g.ids[0]; b = up.ids[up.L - 1]
                ny, nx = min(g.ny, up.ny), min(g.nx, up.nx)
                a, b = a[:ny, :nx], b[:ny, :nx]
                ok = (a >= 0) & (b >= 0)
                h_between = K_AIR / gap * air.get('still_gap', 1.0) + F * hr / (2 / eps - 1)
                self._link(o + a[ok], self.off[bi + 1] + b[ok], h_between * A)
                h_side = air['h_gap'] + (1 - F) * eps * hr
                self.gamb[o + a[a >= 0]] += h_side * A
                self.gamb[self.off[bi + 1] + b[b >= 0]] += h_side * A
        if self.plate_ids is not None:
            self._build_plate(hr)

    def _build_plate(self, hr):
        p, g, air = self.plate, self.grids[0], self.air
        A = (g.h * 1e-3) ** 2
        pid = self.plate_ids
        t = p['t'] * 1e-3
        # sideways through the base
        for dy, dx in ((0, 1), (1, 0)):
            a = pid[:g.ny - dy, :g.nx - dx]; b = pid[dy:, dx:]
            ok = (a >= 0) & (b >= 0)
            self._link(a[ok], b[ok], K_AL * t)
        # the gap pad, from the board's bottom copper to the plate
        bot = g.ids[g.L - 1]
        ok = pid >= 0
        self._link(self.off[0] + bot[ok], pid[ok], p['k_pad'] / (p['t_pad'] * 1e-3) * A)
        # underside to the air: the fins' area times their efficiency, and radiation
        self.gamb[pid[ok]] += (air['h_out'] * p.get('area', 1.0) + p.get('eps', air['eps']) * hr) * A
        # heat capacity: the base and the fins' metal, and the pad
        self.cap[pid[ok]] += (RC_AL * (t + p.get('fin_vol', 0.0) * 1e-3) + p.get('rc_pad', 2.5e6) * p['t_pad'] * 1e-3) * A

    def junction(self, bi, ref, fine_cells, layer, R, C):
        """A part's junction node, R (K/W) to the copper under fine_cells on `layer`."""
        g = self.grids[bi]
        (iy, ix), w = g.cells(fine_cells)
        ids = g.ids[layer, iy, ix]
        keep = ids >= 0
        node = self.n + len(self.junc)
        self.junc[(bi, ref)] = node
        self._extra = getattr(self, '_extra', [])
        self._extra.append((node, self.off[bi] + ids[keep], w[keep] / w[keep].sum() / R, C))
        return node

    def matrix(self):
        n = self.n + len(self.junc)
        rows, cols, vals = list(self.rows), list(self.cols), list(self.vals)
        cap = np.concatenate([self.cap, np.zeros(len(self.junc))])
        gamb = np.concatenate([self.gamb, np.zeros(len(self.junc))])
        for node, cells, g, C in getattr(self, '_extra', []):
            rows.append(np.full(cells.size, node)); cols.append(cells); vals.append(g)
            cap[node] = C
        a = np.concatenate(rows); b = np.concatenate(cols); g = np.concatenate(vals)
        G = sp.coo_matrix((np.concatenate([g, g, -g, -g]),
                           (np.concatenate([a, b, a, b]), np.concatenate([a, b, b, a]))),
                          shape=(n, n)).tocsr()
        G = G + sp.diags(gamb)
        return G, cap, gamb


def _view_parallel(side, gap):
    """View factor between two coaxial parallel squares (Hottel's formula)."""
    X = Y = side / gap
    x1, y1 = np.sqrt(1 + X * X), np.sqrt(1 + Y * Y)
    return 2 / (np.pi * X * Y) * (np.log(np.sqrt(x1 ** 2 * y1 ** 2 / (x1 ** 2 + y1 ** 2 - 1)))
                                  + X * y1 * np.arctan(X / y1) + Y * x1 * np.arctan(Y / x1)
                                  - X * np.arctan(X) - Y * np.arctan(Y))


class Solver:
    def __init__(self, stack):
        self.s = stack
        self.G, self.cap, self.gamb = stack.matrix()
        self._ml = {}

    def _solve(self, A, b, key, x0=None):
        import dcflow
        if key not in self._ml:
            self._ml[key] = dcflow.amg(A.tocsr(), tol=1e-9)
        return self._ml[key](b, x0=x0)

    def steady(self, P):
        return self._solve(self.G, P + self.gamb * self.s.T_amb, 'steady')

    def step(self, T, P, dt):
        A = self.G + sp.diags(self.cap / dt)
        return self._solve(A, P + self.gamb * self.s.T_amb + self.cap / dt * T, ('dt', dt), x0=T)
