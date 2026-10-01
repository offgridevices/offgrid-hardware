# -*- coding: utf-8 -*-
"""DC current flow in a board's copper: voltage, current density and loss.

One net at a time.  Every copper cell of the net is a node.  Neighbouring
cells on a layer are joined by the layer's sheet conductance, t / rho(T):
a square of copper conducts the same whatever its size.  Each hole (via or
plated through-hole pad) is a barrel of plated copper joining the layers it
lands on, one node per layer, tied to the cells inside its drill.  Parts
put current in and take it out at terminals: a node for each part's pads
on the net, joined to every cell under those pads through the solder.

The currents come from the operating point (stress.py): a FET's drain takes
the channel's current out of VBAT, its source puts it into the phase, and so
on.  The solution is exact for the copper as drawn, at DC, for a uniform
copper temperature; switching-frequency currents that close through the
bridge capacitors are not in it.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse import csgraph

RHO20 = 1.724e-8          # copper, ohm m at 20 C (IEC 60028 annealed)
ALPHA = 0.00393           # copper resistance temperature coefficient, 1/K
RHO_SOLDER = 1.32e-7      # SAC305, ohm m
T_SOLDER = 0.075e-3       # solder joint thickness under a pad, m
PLATING = 20e-6           # via barrel plating, m (fab minimum average, see data.py)


def rho(T):
    return RHO20 * (1 + ALPHA * (T - 20.0))


class Solution:
    pass


def network(c, net, T=20.0, plating=PLATING):
    """The conductance network of one net: (G matrix, node info)."""
    k = c.net(net)
    mask = c.owner == k                      # [L, ny, nx]
    L, ny, nx = mask.shape
    ids = -np.ones(mask.shape, np.int64)
    ncell = int(mask.sum())
    ids[mask] = np.arange(ncell)
    r = rho(T)
    rows, cols, vals = [], [], []

    def link(a, b, g):
        rows.append(a); cols.append(b); vals.append(g)

    # in-plane: sheet conductance between neighbours
    for li in range(L):
        g = c.t[li] * 1e-3 / r
        m = mask[li]
        for dy, dx in ((0, 1), (1, 0)):
            both = m[:ny - dy, :nx - dx] & m[dy:, dx:]
            a = ids[li, :ny - dy, :nx - dx][both]
            b = ids[li, dy:, dx:][both]
            link(a, b, np.full(a.size, g))
    n = ncell
    barrels = []                             # (hole index, [(layer, node)])
    land = {}                                # (hole, layer) -> a cell of its land
    for hi, h in enumerate(c.holes):
        if h['net'] != net:
            continue
        iy, ix = c.cell(h['x'], h['y'])
        rad = max(h['d'] / 2, c.res)
        ry = int(np.ceil(rad / c.res))
        yy, xx = np.mgrid[iy - ry:iy + ry + 1, ix - ry:ix + ry + 1]
        cx, cy = c.xy(yy, xx)
        disc = (cx - h['x']) ** 2 + (cy - h['y']) ** 2 <= rad ** 2
        yy, xx = yy[disc], xx[disc]
        nodes = []
        for li in h['layers']:
            cells = ids[li, yy, xx]
            cells = cells[cells >= 0]
            if cells.size:
                link(np.full(cells.size, n), cells, np.full(cells.size, 1e4))
                land[(hi, li)] = int(cells[0])
                nodes.append((li, n))
                n += 1
        # barrel segments between consecutive landed layers
        solid = h['kind'] == 'pad'           # a wire soldered through the hole
        for (l1, a), (l2, b) in zip(nodes, nodes[1:]):
            length = abs(c.zc[l2] - c.zc[l1]) * 1e-3
            g = 1e4 if solid else np.pi * h['d'] * 1e-3 * plating / (r * length)
            link(np.array([a]), np.array([b]), np.array([g]))
        barrels.append((hi, nodes))
    terms = {}
    area = (c.res * 1e-3) ** 2
    gs = area / (RHO_SOLDER * T_SOLDER)
    for key, T_ in c.terminals.items():
        if T_['net'] != net:
            continue
        tn = n
        n += 1
        terms[key[0]] = tn
        for li, cells in T_['cells'].items():
            node = ids[li].ravel()[cells]
            node = node[node >= 0]
            link(np.full(node.size, tn), node, np.full(node.size, gs))
        # a through-hole terminal (wire in a plated hole): into its barrel
        for hi, nodes in barrels:
            h = c.holes[hi]
            if h['kind'] == 'pad' and h.get('ref') == key[0]:
                for li, bn in nodes:
                    link(np.array([tn]), np.array([bn]), np.array([1e4]))
    a = np.concatenate(rows); b = np.concatenate(cols); g = np.concatenate(vals)
    G = sp.coo_matrix((np.concatenate([g, g, -g, -g]),
                       (np.concatenate([a, b, a, b]), np.concatenate([a, b, b, a]))),
                      shape=(n, n)).tocsr()
    info = dict(ids=ids, ncell=ncell, n=n, terms=terms, barrels=barrels, edges=(a, b, g), land=land,
                mask=mask, net=net, T=T, plating=plating)
    return G, info


_cache = {}


def amg(A, tol=1e-10):
    """A solver for the SPD network matrix A: smoothed-aggregation AMG with the
    'evolution' strength measure under conjugate gradients.  (The default
    strength measure stalls on these boards: strong in-plane copper, weak
    via barrels between layers.)  Every solve is checked to have converged."""
    import pyamg
    ml = pyamg.smoothed_aggregation_solver(A, symmetry='symmetric', strength='evolution', max_coarse=500)

    def solve(b, x0=None):
        res = []
        x = ml.solve(b, x0=x0, tol=tol, accel='cg', maxiter=400, residuals=res)
        # aimed at tol; a residual past 1e-6 of both the start (cold starts) and
        # of the right-hand side (warm starts begin close) is a failure
        if res[-1] > 1e-6 * max(res[0], np.linalg.norm(b)):
            raise RuntimeError('network solve did not converge: residual %.1e of %.1e' % (res[-1], res[0]))
        return x
    return solve


def forget():
    """Drop the cached networks and solver hierarchies (they are large)."""
    _cache.clear()


def solve(c, net, currents, T=20.0, net_cache=_cache):
    """currents: {part ref: amps into the copper at its terminal on this net}.

    They must sum to zero.  The most negative terminal is the reference (0 V).
    """
    key = (c.path, c.res, net, T)
    if key not in net_cache:
        G, info = network(c, net, T)
        net_cache[key] = (G, info, {})
    G, info, lu = net_cache[key]
    assert abs(sum(currents.values())) < 1e-9 * max(1, max(map(abs, currents.values()))), currents
    ref = min(currents, key=currents.get)
    r = info['terms'][ref]
    if ref not in lu:
        # only the copper joined to the reference terminal: an island (a
        # pour or stub not tied in, or a board still being routed) carries
        # no current, and left in it makes the matrix singular
        _, comp = csgraph.connected_components(G, directed=False)
        live = comp == comp[r]
        keep = live.copy(); keep[r] = False
        lu[ref] = (live, keep, amg(G[keep][:, keep].tocsr()))
    live, keep, sol = lu[ref]
    cut = sorted(p for p, a in currents.items() if a and not live[info['terms'][p]])
    if cut:
        raise RuntimeError('%s: no copper joins %s to %s' % (net, ', '.join(cut), ref))
    I = np.zeros(info['n'])
    for part, amps in currents.items():
        I[info['terms'][part]] += amps
    V = np.zeros(info['n'])
    V[keep] = sol(I[keep])
    s = Solution()
    s.net, s.V, s.info, s.currents = net, V, info, currents
    a, b, g = info['edges']
    s.edge_i = g * (V[a] - V[b])             # amps from a to b
    s.loss = float(np.sum(g * (V[a] - V[b]) ** 2))
    s.term_v = {p: float(V[t]) if live[t] else float('nan') for p, t in info['terms'].items()}
    return s


def maps(c, s):
    """Per-cell loss (W) and current density (A/mm2) per layer, from one solution."""
    info = s.info
    ids, ncell = info['ids'], info['ncell']
    a, b, g = info['edges']
    p = g * (s.V[a] - s.V[b]) ** 2
    # every node's heat lands in a cell: a barrel node's in the cell at the
    # hole's centre on its layer, a terminal's (solder) in the cell it joins
    rep = np.arange(info['n'])
    rep[ncell:] = -1
    for hi, nodes in info['barrels']:
        h = c.holes[hi]
        iy, ix = c.cell(h['x'], h['y'])
        for li, node in nodes:
            cell = ids[li, iy, ix]
            if cell < 0:
                cell = info['land'].get((hi, li), -1)
            rep[node] = cell
    ra, rb = rep[a], rep[b]
    ra = np.where(ra < 0, rb, ra)
    rb = np.where(rb < 0, ra, rb)
    loss = np.zeros(ncell)
    ok = (ra >= 0) & (rb >= 0)
    np.add.at(loss, ra[ok], p[ok] / 2)
    np.add.at(loss, rb[ok], p[ok] / 2)
    # sheet current from the in-plane gradients: K = G_sheet * |grad V|, J = K / t
    L = ids.shape[0]
    J = np.zeros(ids.shape)
    W = np.zeros(ids.shape)
    Vc = np.full(ids.shape, np.nan)
    m = info['mask']
    Vc[m] = s.V[ids[m]]
    r = rho(info['T'])
    for li in range(L):
        sig = 1 / r
        gy, gx = np.gradient(Vc[li], c.res * 1e-3)
        E = np.hypot(np.nan_to_num(gx), np.nan_to_num(gy))
        J[li] = np.where(m[li], sig * E * 1e-6, 0)      # A/mm2
        W[li][m[li]] = loss[ids[li][m[li]]]
    return dict(J=J, W=W, V=Vc)


def barrel_currents(c, s):
    """Largest current through any segment of each hole's barrel: [(hole, amps)]."""
    info = s.info
    a, b, g = info['edges']
    V = s.V
    out = []
    for hi, nodes in info['barrels']:
        best = 0.0
        for (l1, n1), (l2, n2) in zip(nodes, nodes[1:]):
            h = c.holes[hi]
            length = abs(c.zc[l2] - c.zc[l1]) * 1e-3
            gseg = 1e4 if h['kind'] == 'pad' else np.pi * h['d'] * 1e-3 * info['plating'] / (rho(info['T']) * length)
            best = max(best, abs(gseg * (V[n1] - V[n2])))
        out.append((hi, best))
    return out
