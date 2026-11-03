# -*- coding: utf-8 -*-
"""PCB parasitics of the power path, extracted from the routed board
(../mesh-radio.kicad_pcb) for the TRACE_* constants in board.py.

Run from mesh-radio/v1 in the pinned container (it needs pcbnew and scipy):

    tools/kd python3 sim/extract.py            # prints the table, writes sim/extract.txt

Method
------
Copper: resistivity 1.724e-8 Ohm m at 20 C (annealed copper, IEC 60028),
x (1 + 0.00393 x 5) = 1.758e-8 at 25 C; thickness per layer from the
board's own stackup (outer 35 um, inner 17.5 um); via barrels 18 um of
plating (JLCPCB's stated minimum average; typical is 20-25 um).

Power nets (tracks only: none of these nets has a pour on this board): each
net is a resistor network.  Every track or arc segment is a resistor
(rho L / (w t)); segment ends join where they coincide, lie inside a pad
or a via's annular ring on that layer, or end on another segment (a T,
which splits that segment).  A via is a chain of barrel resistors between
the copper layers it spans (rho dz / (pi d_drill t_plating)).  A
terminal is every pad of one part on that net, shorted together (the part's
pins are one node in the simulation).  R between two terminals is solved
exactly on that network (parallel routes included).  Track running inside a
pad is counted as track (slightly pessimistic).

Ground: the GND copper (zone fills, tracks and pads on all six layers, and
the GND vias and through-hole pads joining them) is rasterised on a square
grid (GRID, 0.1 mm) and solved as a resistor mesh (sheet resistance rho/t per
square).  The return resistance of a path is R between the GND pads of its
two ends.  The BQ29700 senses V- (through 2.2 k to GND) against VSS
(CELL_MINUS): the part of the ground return and of the CELL_MINUS track that
lies between those two taps and the sense resistor is in its sense loop; it
is reported separately (transfer resistance: tap potential per amp of the
burst current) and goes into the protector's sense resistance, not into
TRACE_BAT.

Loop inductance: the current's route is the least-resistance path through
the net's network; each segment is a microstrip over the nearest copper
layer that has GND under it at that point (from the same raster; the
return current runs in that layer under the track), L' = mu0/(2 pi)
ln(8h/w + w/4h) for w <= h, mu0 / (w/h + 1.393 + 0.667 ln(w/h + 1.444))
above (Wheeler/Hammerstad, air: L does not depend on the dielectric), h the
dielectric gap between the two copper layers.  Each via adds 0.2 h
(ln(4h/d) + 1) nH (h, d in mm; the partial self-inductance of the barrel,
pessimistic: the return in nearby GND vias reduces it).  Where both
conductors of a loop are tracks (BATT_PLUS out, CELL_MINUS back) the two
microstrip inductances are added (no mutual coupling counted: pessimistic).
Part pins, the parts' own lead inductance and capacitor ESL are not included.

The simulation's mapping (board.py): its BAT_P node is the reverse FET's
source pins (Q1); its VSYS node is the charger's SYS pins (U4).  board.py
uses L only on the high-current and input paths (TRACE_BAT, _MUX1, _PAIN,
_VPA, _USB, _SOLAR, _DRONE); the other branches are R only there.
"""
import math
import os
import re
import sys
from collections import defaultdict

import numpy as np
import pcbnew
from matplotlib.path import Path
from scipy.sparse import coo_matrix, identity
from scipy.sparse.linalg import spsolve

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'mesh-radio.kicad_pcb')
RHO = 1.724e-8 * (1 + 0.00393 * 5)     # Ohm m, copper at 25 C
T_PLATE = 18e-6                        # via barrel plating (m)
GRID = float(os.environ.get('GRID', 0.1))   # GND raster pitch (mm)
MU0_2PI = 0.2                          # nH/mm

b = pcbnew.LoadBoard(BOARD)
MM = 1e-6   # internal units (nm) -> mm


# ---------------------------------------------------------------- stackup
def stackup():
    """[(layer name, copper thickness mm, z of its centre mm)] from the file's stackup block."""
    s = open(BOARD).read()
    blk = re.search(r'\(stackup(.*?)\(copper_finish', s, re.S).group(1)
    z, out = 0.0, []
    for name, body in re.findall(r'\(layer "([^"]+)"(.*?)\n\t\t\t\)', blk, re.S):
        m = re.search(r'\(thickness ([\d.]+)\)', body)
        t = float(m.group(1)) if m else 0.0
        if '(type "copper")' in body:
            out.append((name, t, z + t / 2))
        if 'Mask' not in name:
            z += t
    return out


STACK = stackup()
CU = [n for n, _, _ in STACK]
LID = {n: b.GetLayerID(n) for n in CU}
LNAME = {v: k for k, v in LID.items()}
THK = {n: t * 1e-3 for n, t, _ in STACK}        # m
ZC = {n: zc for n, _, zc in STACK}              # mm
IDX = {n: i for i, n in enumerate(CU)}


def gap(a, c):
    """Dielectric between copper layers a and c (mm)."""
    return abs(ZC[a] - ZC[c]) - (THK[a] + THK[c]) * 1e3 / 2


def via_span(v):
    top, bot = LNAME.get(v.TopLayer()), LNAME.get(v.BottomLayer())
    i, j = sorted((IDX[top], IDX[bot]))
    return CU[i:j + 1]


def via_w(v):
    try:
        return v.GetWidth(LID['F.Cu']) * MM
    except TypeError:
        return v.GetWidth() * MM


def pad_layers(p):
    return [n for n in CU if p.IsOnLayer(LID[n])]


def pad_hit(p, x, y, layer, margin=0.0):
    """(x, y) on the pad's copper on that layer, or within margin (mm) of it."""
    pt = pcbnew.VECTOR2I(int(round(x / MM)), int(round(y / MM)))
    return p.HitTest(pt, int(round(margin / MM)), LID[layer])


def seg_closest(a, c, p, q):
    """Closest points of segments a-c and p-q: (distance, u on a-c, v on p-q)."""
    ax, ay = a; cx, cy = c; px, py = p; qx, qy = q
    d1 = (cx - ax, cy - ay); d2 = (qx - px, qy - py); r = (ax - px, ay - py)
    A = d1[0] ** 2 + d1[1] ** 2; E = d2[0] ** 2 + d2[1] ** 2; F = d2[0] * r[0] + d2[1] * r[1]
    if A < 1e-12 and E < 1e-12:
        return math.hypot(*r), 0.0, 0.0
    if A < 1e-12:
        u, v = 0.0, min(1, max(0, F / E))
    else:
        C = d1[0] * r[0] + d1[1] * r[1]
        if E < 1e-12:
            u, v = min(1, max(0, -C / A)), 0.0
        else:
            B = d1[0] * d2[0] + d1[1] * d2[1]
            den = A * E - B * B
            u = min(1, max(0, (B * F - C * E) / den)) if den > 1e-12 else 0.0
            v = (B * u + F) / E
            if v < 0:
                v, u = 0.0, min(1, max(0, -C / A))
            elif v > 1:
                v, u = 1.0, min(1, max(0, (B - C) / A))
    dx = ax + u * d1[0] - px - v * d2[0]
    dy = ay + u * d1[1] - py - v * d2[1]
    return math.hypot(dx, dy), u, v


def barrel_r(dz_mm, drill_mm):
    return RHO * dz_mm * 1e-3 / (math.pi * drill_mm * 1e-3 * T_PLATE)


def via_l(dz_mm, d_mm):
    return 0.2 * dz_mm * (math.log(4 * dz_mm / d_mm) + 1) if dz_mm > 0 else 0.0


def l_per_mm(w, h):
    """Microstrip inductance per length (nH/mm), air (L is independent of the dielectric)."""
    u = w / h
    if u <= 1:
        return MU0_2PI * math.log(8 / u + u / 4)
    return 2 * math.pi * MU0_2PI / (u + 1.393 + 0.667 * math.log(u + 1.444))


# ---------------------------------------------------------------- GND raster
class Ground:
    def __init__(self, h=GRID):
        bb = b.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = bb.GetX() * MM, bb.GetY() * MM
        self.nx, self.ny = int(math.ceil(bb.GetWidth() * MM / h)), int(math.ceil(bb.GetHeight() * MM / h))
        self.h = h
        xs = self.x0 + (np.arange(self.nx) + 0.5) * h
        ys = self.y0 + (np.arange(self.ny) + 0.5) * h
        self.X, self.Y = np.meshgrid(xs, ys)
        self.cov = {n: np.zeros((self.ny, self.nx), bool) for n in CU}
        for z in b.Zones():
            if z.GetNetname() != 'GND' or z.GetIsRuleArea():
                continue
            for L in z.GetLayerSet().Seq():
                if L not in LNAME:
                    continue
                self._poly(z.GetFilledPolysList(L), LNAME[L])
        self.vias = []
        for t in b.GetTracks():
            if t.GetNetname() != 'GND':
                continue
            if t.GetClass() == 'PCB_VIA':
                self.vias.append((t.GetPosition().x * MM, t.GetPosition().y * MM, t.GetDrillValue() * MM,
                                  via_span(t)))
            else:
                self._seg(t)
        self.gpads = [p for p in b.GetPads() if p.GetNetname() == 'GND']
        for p in self.gpads:
            for n in pad_layers(p):
                self.cov[n] |= self.pad_mask(p, n)
            if p.GetDrillSize().x > 0:
                self.vias.append((p.GetPosition().x * MM, p.GetPosition().y * MM, p.GetDrillSize().x * MM,
                                  pad_layers(p)))
        for x, y, d, span in self.vias:
            i, j = self.cell(x, y)
            for n in span:
                self.cov[n][j, i] = True
        self._solve_setup()

    def cell(self, x, y):
        return (min(self.nx - 1, max(0, int((x - self.x0) / self.h))),
                min(self.ny - 1, max(0, int((y - self.y0) / self.h))))

    def _poly(self, ps, layer):
        for k in range(ps.OutlineCount()):
            def pts(ch):
                return np.array([[ch.CPoint(i).x * MM, ch.CPoint(i).y * MM] for i in range(ch.PointCount())])
            o = pts(ps.Outline(k))
            m = self._inside(o)
            for hh in range(ps.HoleCount(k)):
                m &= ~self._inside(pts(ps.Hole(k, hh)))
            self.cov[layer] |= m

    def _inside(self, poly):
        m = np.zeros((self.ny, self.nx), bool)
        x0, y0 = poly.min(0)
        x1, y1 = poly.max(0)
        i0, j0 = self.cell(x0, y0)
        i1, j1 = self.cell(x1, y1)
        sub = np.c_[self.X[j0:j1 + 1, i0:i1 + 1].ravel(), self.Y[j0:j1 + 1, i0:i1 + 1].ravel()]
        m[j0:j1 + 1, i0:i1 + 1] = Path(poly).contains_points(sub).reshape(j1 - j0 + 1, i1 - i0 + 1)
        return m

    def _seg(self, t):
        layer = LNAME.get(t.GetLayer())
        if layer is None:
            return
        ax, ay, bx, by = t.GetStart().x * MM, t.GetStart().y * MM, t.GetEnd().x * MM, t.GetEnd().y * MM
        w = t.GetWidth() * MM
        i0, j0 = self.cell(min(ax, bx) - w, min(ay, by) - w)
        i1, j1 = self.cell(max(ax, bx) + w, max(ay, by) + w)
        X, Y = self.X[j0:j1 + 1, i0:i1 + 1], self.Y[j0:j1 + 1, i0:i1 + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-12
        u = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
        d = np.hypot(X - ax - u * dx, Y - ay - u * dy)
        self.cov[layer][j0:j1 + 1, i0:i1 + 1] |= d <= w / 2 + self.h / 4

    def pad_mask(self, p, layer):
        m = np.zeros((self.ny, self.nx), bool)
        bb = p.GetBoundingBox()
        i0, j0 = self.cell(bb.GetX() * MM, bb.GetY() * MM)
        i1, j1 = self.cell(bb.GetRight() * MM, bb.GetBottom() * MM)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                if pad_hit(p, self.X[j, i], self.Y[j, i], layer):
                    m[j, i] = True
        if not m.any():       # a pad smaller than a cell: its centre cell
            i, j = self.cell(p.GetPosition().x * MM, p.GetPosition().y * MM)
            m[j, i] = True
        return m

    def _solve_setup(self):
        idx = {}
        n0 = 0
        for n in CU:
            a = -np.ones((self.ny, self.nx), int)
            k = int(self.cov[n].sum())
            a[self.cov[n]] = np.arange(n0, n0 + k)
            idx[n] = a
            n0 += k
        self.idx, self.N = idx, n0
        r, c, g = [], [], []
        for n in CU:
            a, gs = idx[n], THK[n] / RHO          # conductance of one square
            for p, q in ((a[:, :-1], a[:, 1:]), (a[:-1, :], a[1:, :])):
                ok = (p >= 0) & (q >= 0)
                r.append(p[ok]); c.append(q[ok]); g.append(np.full(ok.sum(), gs))
        for x, y, d, span in self.vias:
            i, j = self.cell(x, y)
            on = [n for n in span if idx[n][j, i] >= 0]
            for u, v in zip(on, on[1:]):
                r.append(np.array([idx[u][j, i]])); c.append(np.array([idx[v][j, i]]))
                g.append(np.array([1.0 / barrel_r(abs(ZC[u] - ZC[v]), d)]))
        self.edges = (np.concatenate(r), np.concatenate(c), np.concatenate(g))

    def terminal(self, ref, numbers=None):
        cells = []
        for p in self.gpads:
            if p.GetParentFootprint().GetReference() != ref:
                continue
            if numbers and p.GetNumber() not in numbers:
                continue
            for n in pad_layers(p):
                m = self.pad_mask(p, n) & (self.idx[n] >= 0)
                cells += list(self.idx[n][m])
        if not cells:
            raise SystemExit('no GND copper under %s' % ref)
        return sorted(set(cells))

    def solve(self, src, snk, taps=()):
        """1 A from GND terminal src to snk.  Returns R, {tap: potential vs snk}."""
        N = self.N + 2
        S, K = self.N, self.N + 1
        r, c, g = self.edges
        big = 1e6
        r = np.concatenate([r, np.full(len(src), S), np.full(len(snk), K)])
        c = np.concatenate([c, src, snk])
        g = np.concatenate([g, np.full(len(src), big), np.full(len(snk), big)])
        G = coo_matrix((np.r_[-g, -g, g, g], (np.r_[r, c, r, c], np.r_[c, r, r, c])), shape=(N, N)).tocsr()
        keep = np.arange(N) != K
        G = G[keep][:, keep] + identity(N - 1, format='csr') * 1e-9    # floating islands (leakage to the sink)
        I = np.zeros(N - 1)
        I[S] = 1.0
        v = spsolve(G.tocsc(), I)
        vv = np.r_[v, 0.0]   # K is last
        return vv[S], dict((name, float(np.mean(vv[cells]))) for name, cells in taps)

    def ref_layer(self, layer, x, y):
        """The nearest other copper layer with GND under (x, y): (name, dielectric gap mm)."""
        i, j = self.cell(x, y)
        for n in sorted((n for n in CU if n != layer), key=lambda n: abs(ZC[n] - ZC[layer])):
            if self.cov[n][j, i]:
                return n, gap(layer, n)
        return None, 1.6


# ---------------------------------------------------------------- power-net networks
class Net:
    def __init__(self, name, gnd):
        self.name, self.gnd = name, gnd
        self.par = {}
        segs, self.vias = [], []
        for t in b.GetTracks():
            if t.GetNetname() != name:
                continue
            if t.GetClass() == 'PCB_VIA':
                self.vias.append(dict(x=t.GetPosition().x * MM, y=t.GetPosition().y * MM, d=t.GetDrillValue() * MM,
                                      w=via_w(t), span=via_span(t)))
            else:
                L = LNAME.get(t.GetLayer())
                a = (t.GetStart().x * MM, t.GetStart().y * MM)
                c = (t.GetEnd().x * MM, t.GetEnd().y * MM)
                segs.append(dict(layer=L, a=a, b=c, w=t.GetWidth() * MM, len=t.GetLength() * MM,
                                 arc=t.GetClass() == 'PCB_ARC', cuts=[]))
        self.pads = [p for p in b.GetPads() if p.GetNetname() == name]
        # Connections.  Strict ones first: a track end inside another track's copper, a via's ring or
        # a pad; a via inside a pad; a track crossing a pad.  Then, only between pieces that are
        # still apart, copper that merely overlaps (an end that stops just short of a via or pad,
        # as the routers leave them).  Overlap alone is not used between pieces already joined:
        # a chain of short wide segments overlaps its next-but-one neighbour, and joining those
        # would short out the copper between them.
        def ek(si, e):
            sg = segs[si]
            return self.key(('E', sg['layer'], round(sg[e][0], 4), round(sg[e][1], 4)))

        def attach(si, u):
            sg = segs[si]
            if sg['arc'] or u < 1e-3 or u > 1 - 1e-3:
                return ek(si, 'a' if u < 0.5 else 'b')
            k = self.key(('C', si, round(u, 6)))
            sg['cuts'].append((round(u, 6), k))
            return k
        cand = []      # (strict, side, side): a side is ('s', segment, u) or ('n', node key)
        for si, sg in enumerate(segs):
            for sj in range(si + 1, len(segs)):
                o = segs[sj]
                if o['layer'] != sg['layer']:
                    continue
                d, u, v = seg_closest(sg['a'], sg['b'], o['a'], o['b'])
                if d > (sg['w'] + o['w']) / 2 + 1e-4:
                    continue
                end_in = ((u in (0.0, 1.0) and d <= o['w'] / 2 + 1e-4) or (v in (0.0, 1.0) and d <= sg['w'] / 2 + 1e-4))
                cand.append((end_in, ('s', si, u), ('s', sj, v)))
            for vi, v in enumerate(self.vias):
                if sg['layer'] in v['span']:
                    d, u, _ = seg_closest(sg['a'], sg['b'], (v['x'], v['y']), (v['x'], v['y']))
                    if d <= (v['w'] + sg['w']) / 2 + 1e-4:
                        strict = d <= sg['w'] / 2 + 1e-4 or (u in (0.0, 1.0) and d <= v['w'] / 2 + 1e-4)
                        cand.append((strict, ('s', si, u), ('n', ('V', vi, sg['layer']))))
            for p in self.pads:
                if sg['layer'] not in pad_layers(p):
                    continue
                n = max(2, int(sg['len'] / 0.05) + 1)
                for margin, strict in ((0.0, True), (sg['w'] / 2, False)):
                    hit = [k / (n - 1) for k in range(n)
                           if pad_hit(p, sg['a'][0] + k / (n - 1) * (sg['b'][0] - sg['a'][0]),
                                      sg['a'][1] + k / (n - 1) * (sg['b'][1] - sg['a'][1]), sg['layer'], margin)]
                    if hit:
                        # the end inside the pad, else the first point that touches it
                        u = 0.0 if hit[0] == 0.0 else (1.0 if hit[-1] == 1.0 else hit[0])
                        cand.append((strict, ('s', si, u), ('n', self.padkey(p))))
                        break
        for vi, v in enumerate(self.vias):
            for p in self.pads:
                for n in v['span']:
                    if n in pad_layers(p):
                        if pad_hit(p, v['x'], v['y'], n):
                            cand.append((True, ('n', ('V', vi, n)), ('n', self.padkey(p))))
                        elif pad_hit(p, v['x'], v['y'], n, v['w'] / 2):
                            cand.append((False, ('n', ('V', vi, n)), ('n', self.padkey(p))))
        # connectivity bookkeeping (a separate union-find: along segments and via barrels too)
        cpar = {}

        def cf(k):
            cpar.setdefault(k, k)
            while cpar[k] != k:
                cpar[k] = cpar[cpar[k]]
                k = cpar[k]
            return k

        def cu(a, c):
            cpar[cf(a)] = cf(c)
        for si in range(len(segs)):
            cu(ek(si, 'a'), ek(si, 'b'))
        for vi, v in enumerate(self.vias):
            for n in v['span'][1:]:
                cu(('V', vi, v['span'][0]), ('V', vi, n))

        def side(x, apply):
            if x[0] == 'n':
                return x[1]
            return attach(x[1], x[2]) if apply else ek(x[1], 'a')
        for strict in (True, False):
            for st, x, y in cand:
                if st != strict:
                    continue
                if not strict and cf(side(x, False)) == cf(side(y, False)):
                    continue
                kx, ky = side(x, True), side(y, True)
                self.union(kx, ky)
                cu(kx, ky)
                for z in (x, y):
                    if z[0] == 's':
                        cu(kx if z is x else ky, ek(z[1], 'a'))
        # resistors: (node a, node b, R, L)
        self.res = []
        for s in segs:
            ka = ('E', s['layer'], round(s['a'][0], 4), round(s['a'][1], 4))
            kb = ('E', s['layer'], round(s['b'][0], 4), round(s['b'][1], 4))
            pts = [(0.0, ka)] + sorted(set(s['cuts'])) + [(1.0, kb)]
            for (u0, k0), (u1, k1) in zip(pts, pts[1:]):
                ln = s['len'] * (u1 - u0)
                R = RHO * ln * 1e-3 / (s['w'] * 1e-3 * THK[s['layer']])
                self.res.append((k0, k1, R, self.seg_l(s, u0, u1)))
        for vi, v in enumerate(self.vias):
            for u, w in zip(v['span'], v['span'][1:]):
                dz = abs(ZC[u] - ZC[w])
                self.res.append((('V', vi, u), ('V', vi, w), barrel_r(dz, v['d']), via_l(dz, v['d'])))
        self.nvias = len(self.vias)

    def seg_l(self, s, u0, u1):
        (ax, ay), (bx, by) = s['a'], s['b']
        ln = s['len'] * (u1 - u0)
        n = max(1, int(ln / 0.25))
        tot = 0.0
        for k in range(n):
            u = u0 + (u1 - u0) * (k + 0.5) / n
            _, h = self.gnd.ref_layer(s['layer'], ax + u * (bx - ax), ay + u * (by - ay))   # arcs: along the chord
            tot += l_per_mm(s['w'], h) * ln / n
        return tot

    def padkey(self, p):
        return ('P', p.GetParentFootprint().GetReference(), p.GetNumber())

    def key(self, k):
        self.par.setdefault(k, k)
        return k

    def find(self, k):
        self.par.setdefault(k, k)
        while self.par[k] != k:
            self.par[k] = self.par[self.par[k]]
            k = self.par[k]
        return k

    def union(self, a, c):
        ra, rc = self.find(a), self.find(c)
        if ra != rc:
            self.par[ra] = rc

    def term(self, ref, numbers=None):
        ks = set(self.find(self.padkey(p)) for p in self.pads
                 if p.GetParentFootprint().GetReference() == ref and (not numbers or p.GetNumber() in numbers))
        if not ks:
            raise SystemExit('%s: no pad of %s' % (self.name, ref))
        return ks

    def solve(self, a, c, taps=()):
        """R from terminal a to c (pads of a part, shorted), the least-resistance route's
        loop inductance and via count, and tap potentials per amp."""
        A, C = self.term(*a), self.term(*c)
        node = {}

        def nid(k):
            k = self.find(k)
            if k in A:
                k = 'A'
            elif k in C:
                k = 'C'
            return node.setdefault(k, len(node))
        edges = [(nid(p), nid(q), R, L, p, q) for p, q, R, L in self.res]
        n = len(node)
        G = np.zeros((n, n))
        for i, j, R, _, _, _ in edges:
            if i == j:
                continue
            g = 1.0 / max(R, 1e-9)
            G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
        ia, ic = node['A'], node['C']
        keep = [k for k in range(n) if k != ic]
        I = np.zeros(n)
        I[ia] = 1.0
        Gk = G[np.ix_(keep, keep)] + np.eye(len(keep)) * 1e-12
        v = np.zeros(n)
        v[keep] = np.linalg.solve(Gk, I[keep])
        R = v[ia]
        # least-resistance route (Dijkstra) for the loop inductance
        import heapq
        adj = defaultdict(list)
        for i, j, Rr, L, p, q in edges:
            vid = p[1] if p[0] == 'V' else None
            adj[i].append((j, Rr, L, vid))
            adj[j].append((i, Rr, L, vid))
        best = {ia: (0.0, 0.0, frozenset())}
        hq = [(0.0, 0, ia)]
        done, cnt = set(), 0
        while hq:
            d, _, i = heapq.heappop(hq)
            if i in done:
                continue
            done.add(i)
            if i == ic:
                break
            _, l, vs = best[i]
            for j, Rr, L, vid in adj[i]:
                if j not in done and (j not in best or d + Rr < best[j][0]):
                    best[j] = (d + Rr, l + L, vs | {vid} if vid is not None else vs)
                    cnt += 1
                    heapq.heappush(hq, (d + Rr, cnt, j))
        if ic not in best:
            raise SystemExit('%s: %s and %s are not connected' % (self.name, a, c))
        tv = {}
        for name, (ref, nums) in taps:
            ks = self.term(ref, nums)
            tv[name] = float(np.mean([v[nid(k)] for k in ks]))
        return dict(R=R, L=best[ic][1] * 1e-9, Rpath=best[ic][0], vias=len(best[ic][2]), taps=tv)


# the estimates the studies used before the board was routed (board.py until 3 Nov 2026)
EST = dict(TRACE_BAT=(0.006, 6e-9), TRACE_MUX1=(0.005, 5e-9), TRACE_PAIN=(0.003, 3e-9), TRACE_VPA=(0.005, 5e-9),
           TRACE_USB=(0.005, 5e-9), TRACE_5V=None, TRACE_CHG=None, TRACE_BYP=None, TRACE_SYS2=None,
           TRACE_SOLAR=(0.005, 5e-9), TRACE_DRONE=(0.005, 5e-9), SENSE_TRACE=None)   # hotplug/run.py had 5 mOhm, 5 nH


def on_net(net, prefix):
    """The one part whose reference starts with prefix and has a pad on net."""
    refs = sorted(set(p.GetParentFootprint().GetReference() for p in b.GetPads()
                      if p.GetNetname() == net and p.GetParentFootprint().GetReference().startswith(prefix)))
    if len(refs) != 1:
        raise SystemExit('%s: parts %s on %s' % (prefix, refs, net))
    return refs[0]


def find_ref(nets, value=None):
    """The footprint whose pads are on exactly these nets (and has this value)."""
    for fp in b.GetFootprints():
        ns = set(p.GetNetname() for p in fp.Pads())
        if ns == set(nets) and (value is None or fp.GetValue() == value):
            return fp.GetReference()
    raise SystemExit('no part on %s' % (nets,))


def main():
    sys.path.insert(0, HERE)
    import board as B
    print('extracting from %s (grid %.2f mm) ...' % (os.path.relpath(BOARD), GRID), file=sys.stderr)
    gnd = Ground()
    nets = {}

    def path(net, a, c, taps=()):
        if net not in nets:
            nets[net] = Net(net, gnd)
        return nets[net].solve(a, c, taps)

    def gpath(a, c, taps=()):
        return gnd.solve(gnd.terminal(a), gnd.terminal(c), [(n, gnd.terminal(r)) for n, r in taps])

    rvm = find_ref(['PROT_VM', 'GND'])          # the 2.2 k from the BQ29700's V- to GND
    vss = ('U5', ['4'])                         # BQ29700 VSS
    P = {}
    # cell loop: cell + -> J3 -> Q1 (BATT_PLUS); cell - <- J3 <- Q3 (CELL_MINUS) <- R34 (PROT_S2) <- GND
    P['batt_plus'] = path('BATT_PLUS', ('J3',), ('Q1',))
    P['cell_minus'] = path('CELL_MINUS', ('J3',), ('Q3',), taps=[('vss', vss)])
    P['prot_s2'] = path('PROT_S2', ('Q3',), ('R34',))
    P['gnd_cell'] = gpath('U14', 'R34', taps=[('vm', rvm)])     # TPS63810 GND -> sense resistor
    # BAT_P from the reverse FET's source
    P['mux1'] = path('BAT_P', ('Q1',), ('U13',))
    P['byp'] = path('BAT_P', ('Q1',), ('U6',))
    P['chg'] = path('BAT_P', ('Q1',), ('U4',))
    P['pain'] = path('PA_IN', ('U13',), ('U14',))
    P['vpa'] = path('VPA', ('U14',), ('L14',))                 # buck-boost VOUT -> the amplifier's collector choke
    P['gnd_pa'] = gpath('U10', 'U14')
    P['usb'] = path('USB_VBUS', ('J1',), ('U1',))
    P['gnd_usb'] = gpath('U4', 'J1')                          # the USB current's return (charger -> connector)
    P['usb5'] = path('USB_5V', ('U1',), ('D4',))
    P['vinchg'] = path('VIN_CHG', ('D4',), ('U4',))
    jsol, usol = on_net('SOLAR_CONN', 'J'), on_net('SOLAR_CONN', 'U')
    jdrn, udrn = on_net('DRONE_5V_CONN', 'J'), on_net('DRONE_5V_CONN', 'U')
    P['sol'] = path('SOLAR_CONN', (jsol,), (usol,))
    P['gnd_sol'] = gpath('U4', jsol)
    P['sol_out'] = path('VIN_CHG', (usol,), ('U4',))
    P['drn'] = path('DRONE_5V_CONN', (jdrn,), (udrn,))
    P['gnd_drn'] = gpath('U4', jdrn)
    P['drn_out'] = path('VIN_CHG', (udrn,), ('U4',))
    P['sys_mux2'] = path('VSYS', ('U4',), ('U13',))
    P['sys_buck'] = path('VSYS', ('U4',), ('U7',))

    # ----- into the simulation's constants
    cm, gc = P['cell_minus'], P['gnd_cell']
    cm_sense = cm['taps']['vss']               # CELL_MINUS between the VSS tap and Q3
    g_sense = gc[1]['vm']                 # GND between the 2.2 k's tap and the sense resistor
    sense = cm_sense + P['prot_s2']['R'] + g_sense
    trace_bat = (P['batt_plus']['R'] + cm['R'] - cm_sense + gc[0] - g_sense,
                 P['batt_plus']['L'] + cm['L'] + P['prot_s2']['L'])
    new = dict(
        TRACE_BAT=trace_bat,
        TRACE_MUX1=(P['mux1']['R'], P['mux1']['L']),
        TRACE_PAIN=(P['pain']['R'], P['pain']['L']),
        TRACE_VPA=(P['vpa']['R'] + P['gnd_pa'][0], P['vpa']['L']),
        TRACE_USB=(P['usb']['R'] + P['gnd_usb'][0], P['usb']['L']),
        TRACE_5V=(P['usb5']['R'] + P['vinchg']['R'], P['usb5']['L'] + P['vinchg']['L']),
        TRACE_CHG=(P['chg']['R'], P['chg']['L']),
        TRACE_BYP=(P['byp']['R'], P['byp']['L']),
        TRACE_SYS2=(P['sys_mux2']['R'], P['sys_mux2']['L']),
        TRACE_SOLAR=(P['sol']['R'] + P['gnd_sol'][0], P['sol']['L']),
        TRACE_DRONE=(P['drn']['R'] + P['gnd_drn'][0], P['drn']['L']),
        SENSE_TRACE=(sense, 0.0),
    )
    what = dict(
        TRACE_BAT='J3 -> Q1 drain (BATT_PLUS) + J3 <- Q3 (CELL_MINUS, outside the sense) + GND U14 -> R34 (outside the sense)',
        TRACE_MUX1='Q1 source -> U13 IN1 (BAT_P)',
        TRACE_PAIN='U13 OUT -> U14 VIN (PA_IN)',
        TRACE_VPA='U14 VOUT -> L14 collector choke (VPA) + GND U10 -> U14',
        TRACE_USB='J1 VBUS -> U1 IN (USB_VBUS) + GND U4 -> J1',
        TRACE_5V='U1 OUT -> D4 (USB_5V) + D4 -> U4 IN (VIN_CHG)',
        TRACE_CHG='Q1 source -> U4 BAT (BAT_P)',
        TRACE_BYP='Q1 source -> U6 VIN (BAT_P)',
        TRACE_SYS2='U4 SYS -> U13 IN2 (VSYS)',
        TRACE_SOLAR='%s -> %s IN (SOLAR_CONN) + GND U4 -> %s' % (jsol, usol, jsol),
        TRACE_DRONE='%s -> %s IN (DRONE_5V_CONN) + GND U4 -> %s' % (jdrn, udrn, jdrn),
        SENSE_TRACE='in the BQ29700 sense loop: CELL_MINUS VSS tap -> Q3, PROT_S2 Q3 -> R34, GND R34 -> %s' % rvm,
    )
    old = EST

    L = ['PCB parasitics of the power path, extracted from mesh-radio.kicad_pcb by sim/extract.py',
         '(copper %.3g Ohm m at 25 C; outer %.1f um, inner %.1f um, via plating %.0f um; GND mesh %.2f mm)' % (
             RHO, THK['F.Cu'] * 1e6, THK['In1.Cu'] * 1e6, T_PLATE * 1e6, GRID), '']
    L.append('%-12s %-22s %-22s  %s' % ('constant', 'estimate (R, L)', 'extracted (R, L)', 'path'))
    for k, (r, l) in new.items():
        o = old[k]
        os_ = '%5.1f mOhm %5.1f nH' % (o[0] * 1e3, o[1] * 1e9) if o else '(not modelled)'
        L.append('%-12s %-22s %5.1f mOhm %5.1f nH   %s' % (k, os_, r * 1e3, l * 1e9, what[k]))
    L += ['', 'Pieces (R solved on the whole network; L and vias along the least-resistance route):']
    for k, v in P.items():
        if isinstance(v, tuple):
            L.append('  %-11s GND  %6.2f mOhm %s' % (k, v[0] * 1e3, ' '.join('%s %.2f mOhm' % (a, x * 1e3)
                                                                       for a, x in v[1].items())))
        else:
            L.append('  %-11s net  %6.2f mOhm  (route %.2f mOhm, %d vias) %5.2f nH %s' % (
                k, v['R'] * 1e3, v['Rpath'] * 1e3, v['vias'], v['L'] * 1e9,
                ' '.join('tap %s %.2f mOhm' % (a, x * 1e3) for a, x in v['taps'].items())))
    L += ['', 'Per net: track length by layer (mm), narrowest track, vias']
    for n, net in nets.items():
        lens = defaultdict(float)
        ws = []
        for t in b.GetTracks():
            if t.GetNetname() == n and t.GetClass() != 'PCB_VIA':
                lens[LNAME.get(t.GetLayer())] += t.GetLength() * MM
                ws.append(t.GetWidth() * MM)
        L.append('  %-10s %s  min %.2f mm, %d vias' % (n, ' '.join('%s %.1f' % kv for kv in lens.items()),
                                                    min(ws), net.nvias))
    L.append('')
    L.append('board.py values (copy):')
    for k, (r, l) in new.items():
        L.append('  %s = (%.4f, %.1fe-9)' % (k, r, l * 1e9) if k != 'SENSE_TRACE' else '  %s = %.4f' % (k, r))
    def cur(k):
        v = getattr(B, k, None)
        return (v, 0.0) if isinstance(v, float) else v
    now = [k for k in new if cur(k) is None or
           abs(cur(k)[0] - new[k][0]) > 2e-4 or abs(cur(k)[1] - new[k][1]) > 0.2e-9]
    L.append('board.py differs from these (re-run the studies after copying): %s' % (', '.join(now) or 'none'))
    txt = '\n'.join(L) + '\n'
    print(txt)
    open(os.path.join(HERE, 'extract.txt'), 'w').write(txt)


if __name__ == '__main__':
    main()
