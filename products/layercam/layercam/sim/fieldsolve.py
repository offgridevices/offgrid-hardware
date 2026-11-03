# -*- coding: utf-8 -*-
"""A small 2D electrostatic field solver for PCB transmission lines.

Finite-volume Laplace solution on a non-uniform rectilinear grid: nodes on
every material and conductor edge, cells graded from 1 um at those edges up
to 40 um.  Each conductor is a set of fixed-potential nodes; the charge on
it is the flux leaving its nodes (Gauss), so the capacitance matrix comes
straight from the solution.  Solving once with the dielectrics and once in
air gives C and C0 per unit length, and with them L = mu0 eps0 C0^-1, the
odd / even mode impedances and the effective permittivities (quasi-TEM).

Used by impedance.py; checked there against two exact results (Cohn's
zero-thickness stripline and Hammerstad-Jensen's microstrip, which is
within 0.2 % of exact for zero thickness).
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

EPS0 = 8.854187817e-12
C_LIGHT = 299792458.0


def axis(features, lo, hi, hmin=0.001, hmax=0.04, growth=1.3):
    """Grid lines (mm): every feature exactly, graded spacing between."""
    f = sorted({round(v, 6) for v in list(features) + [lo, hi] if lo <= v <= hi})
    out = [f[0]]
    for a, b in zip(f[:-1], f[1:]):
        L = b - a
        if L <= 0:
            continue
        # spacing grows from hmin at both ends towards the middle
        left, s, p = [], hmin, a
        while p + s < a + L / 2:
            p += s
            left.append(p)
            s = min(s * growth, hmax)
        right, s, p = [], hmin, b
        while p - s > a + L / 2:
            p -= s
            right.append(p)
            s = min(s * growth, hmax)
        pts = left + right[::-1] + [b]
        out.extend(sorted(pts))
    a = np.array(sorted(set(np.round(out, 7))))
    return a


class Section:
    """A cross-section: x across, y up from the reference plane (y = 0, or
    the bottom of the domain), all in mm."""

    def __init__(self, xs, ys):
        self.xs, self.ys = np.asarray(xs), np.asarray(ys)
        nx, ny = len(self.xs), len(self.ys)
        self.eps = np.ones((nx - 1, ny - 1))
        self.cond = -np.ones((nx, ny), int)       # -1 free, 0 ground, k>0 conductor k
        self.cond[0, :] = self.cond[-1, :] = 0    # box walls at ground
        self.cond[:, 0] = self.cond[:, -1] = 0
        X, Y = np.meshgrid(self.xs, self.ys, indexing='ij')
        self.X, self.Y = X, Y
        cx = (self.xs[:-1] + self.xs[1:]) / 2
        cy = (self.ys[:-1] + self.ys[1:]) / 2
        self.CX, self.CY = np.meshgrid(cx, cy, indexing='ij')

    def set_eps(self, fn):
        """fn(x, y) -> relative permittivity, evaluated at cell centres."""
        self.eps = fn(self.CX, self.CY)

    def add_conductor(self, k, inside):
        """inside(X, Y) -> bool array: the nodes held at conductor k."""
        m = inside(self.X, self.Y)
        self.cond[m] = k

    def _matrix(self, eps):
        xs, ys = self.xs, self.ys
        nx, ny = len(xs), len(ys)
        dx, dy = np.diff(xs), np.diff(ys)
        # edge conductances (per unit eps0) between node (i,j) and its east / north neighbour
        e_pad = np.zeros((nx + 1, ny + 1))
        e_pad[1:-1, 1:-1] = eps
        dyp = np.concatenate([[0], dy, [0]])
        dxp = np.concatenate([[0], dx, [0]])
        # east edge between i and i+1 at row j: cells (i, j-1) and (i, j)
        cE = np.zeros((nx, ny))
        cE[:-1, :] = (e_pad[1:-1, :-1] * dyp[None, :-1] + e_pad[1:-1, 1:] * dyp[None, 1:]) / 2 / dx[:, None]
        cN = np.zeros((nx, ny))
        cN[:, :-1] = (e_pad[:-1, 1:-1] * dxp[:-1, None] + e_pad[1:, 1:-1] * dxp[1:, None]) / 2 / dy[None, :]
        return cE, cN

    def charges(self, eps, volts):
        """Solve with conductor k at volts[k] (ground 0); return charge per
        unit length (C/m) on each conductor 1..n."""
        nx, ny = len(self.xs), len(self.ys)
        cE, cN = self._matrix(eps)
        idx = np.arange(nx * ny).reshape(nx, ny)
        V = np.zeros((nx, ny))
        fixed = self.cond >= 0
        for k, v in volts.items():
            V[self.cond == k] = v
        # assemble the symmetric "Laplacian" from every east and north edge
        ia, ib = idx[:-1, :].ravel(), idx[1:, :].ravel()
        c = cE[:-1, :].ravel()
        rows = np.concatenate([ia, ia, ib, ib]); cols = np.concatenate([ia, ib, ib, ia])
        vals = np.concatenate([c, -c, c, -c])
        ja, jb = idx[:, :-1].ravel(), idx[:, 1:].ravel()
        c2 = cN[:, :-1].ravel()
        rows = np.concatenate([rows, ja, ja, jb, jb]); cols = np.concatenate([cols, ja, jb, jb, ja])
        vals = np.concatenate([vals, c2, -c2, c2, -c2])
        A = sp.csr_matrix((vals, (rows, cols)), shape=(nx * ny, nx * ny))
        f = fixed.ravel()
        free = ~f
        Vf = V.ravel()
        Aff = A[free][:, free]
        b = -A[free][:, f] @ Vf[f]
        Vf = Vf.copy()
        Vf[free] = spla.spsolve(Aff.tocsc(), b)
        # charge: the residual A V at the fixed nodes (= flux out), per conductor
        r = A @ Vf
        q = {}
        for k in volts:
            q[k] = EPS0 * r[self.cond.ravel() == k].sum()
        return q, Vf.reshape(nx, ny)

    def cmatrix(self, ks, eps):
        n = len(ks)
        C = np.zeros((n, n))
        for a, ka in enumerate(ks):
            q, _ = self.charges(eps, {k: (1.0 if k == ka else 0.0) for k in ks})
            for b, kb in enumerate(ks):
                C[b, a] = q[kb]
        return (C + C.T) / 2


def lines(sec, ks):
    """Impedances of the conductors ks in section sec: dict with Z0 (one
    line) or Zodd/Zeven/Zdiff/Zcm (two)."""
    C = sec.cmatrix(ks, sec.eps)
    C0 = sec.cmatrix(ks, np.ones_like(sec.eps))
    Lm = np.linalg.inv(C0) / C_LIGHT ** 2
    if len(ks) == 1:
        z = np.sqrt(Lm[0, 0] / C[0, 0])
        return dict(Z0=z, eeff=C[0, 0] / C0[0, 0])
    Lo, Co, C0o = Lm[0, 0] - Lm[0, 1], C[0, 0] - C[0, 1], C0[0, 0] - C0[0, 1]
    Le, Ce, C0e = Lm[0, 0] + Lm[0, 1], C[0, 0] + C[0, 1], C0[0, 0] + C0[0, 1]
    zo, ze = np.sqrt(Lo / Co), np.sqrt(Le / Ce)
    return dict(Zodd=zo, Zeven=ze, Zdiff=2 * zo, Zcm=ze / 2, eodd=Co / C0o, eeven=Ce / C0e,
                Z0_in_pair=np.sqrt(Lm[0, 0] / C[0, 0]))
