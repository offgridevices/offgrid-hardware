# -*- coding: utf-8 -*-
"""Mesh Radio v1 thermal studies (README E1-E4, P7).

  1. Board thermal model: a layered (2.5-D) finite-difference model of the
     62 x 25.4 mm, 4-layer JLC04161H-7628 board.  Each copper layer is a
     conducting sheet (copper coverage is an input: the routed board's real
     copper replaces it later), FR-4 between the layers, plated vias, the
     QPA9510's paddle and its nine filled vias, convection + radiation from
     both faces.  Heat sources sit at the parts' positions from
     src/placement.json.  Steady listening; Meshtastic transmit duty cycles
     (one 1 s message a minute, 25 % and 50 % "storms", continuous) at
     1 W, 2.5 W and 3 W; USB charging on top.  Ambient -40 ... 85 C, still
     air in an enclosure (h = 10 W/m2K) and a small sealed case (5 W/m2K).
  2. Temperature-rating audit of every part in parts.py used by circuit.py,
     and the charger's NTC (TS) window.
  3. Cold start at -40 C: clocks, the X5R capacitance in the converter
     loops against the datasheet minimums, mechanical notes.
  4. Compactness: board length and amplifier copper against the heat.

Run from mesh-radio/v1 in the pinned container:
    tools/kd python3 sim/thermal/run.py
Writes results.txt and the PNGs next to this file (about 5-10 min, 4 cores).
Needs numpy, scipy (sparse LU) and matplotlib; reads src/circuit.py,
src/parts.py and src/placement.json and changes nothing in src/.

Every number that is an assumption rather than a datasheet value is marked
ASSUMED in PARAMS or in the source table below.
"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import json
import math
import os
import sys
import time
import multiprocessing as mp

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(V1, 'src'))
import circuit  # noqa: E402
import parts    # noqa: E402

SIGMA = 5.670e-8
OUT = []


def out(s=''):
    OUT.append(s)
    print(s)


# ---------------------------------------------------------------------------
# Board and stack-up (JLC04161H-7628, 1.6 mm): F 1 oz | 7628 0.2104 | In1 0.5 oz |
# core 1.065 | In2 0.5 oz | 7628 0.2104 | B 1 oz
PARAMS = dict(
    length=62.0, width=25.4, dx=0.5,            # mm; dx = grid pitch
    x_cut=0.0,                                  # mm taken off the USB (-x) end (study 4)
    t_cu=[35e-6, 15.2e-6, 15.2e-6, 35e-6],      # m, finished copper F, In1, In2, B
    cov=[0.70, 1.00, 0.50, 0.70],               # copper coverage (INPUT; routed board replaces it)
    t_diel=[0.2104e-3, 1.065e-3, 0.2104e-3],    # m, F-In1 prepreg, core, In2-B prepreg
    k_cu=385.0,                                 # W/mK, electrodeposited copper
    k_fr4_z=0.29, k_fr4_xy=0.81,                # W/mK, FR-4 (7628 glass) through / in plane
    rc_cu=3.45e6, rc_fr4=2.0e6,                 # J/m3K volumetric heat capacity
    via_density=8.0,                            # ASSUMED stitching vias per cm2 (0.4/0.2 mm), ground pours
    via_drill=0.2e-3, plating=20e-6,            # m; JLC plates ~18-25 um in the barrel (ASSUMED 20)
    pa_vias=9, pa_via_drill=0.3e-3,             # src/board.py PA_VIAS: nine 0.3 mm holes, 0.55 mm grid
    k_via_fill=0.5,                             # W/mK resin fill (POFV, non-conductive epoxy; ASSUMED)
    paddle=1.5e-3, paste_frac=0.75 * 0.8,       # 1.5 mm paddle; paste 75 % of it (footprints.py), 20 % voids ASSUMED
    t_solder=50e-6, k_solder=58.0,              # SAC305 joint under the paddle (ASSUMED 50 um)
    pa_island=True,                             # paddle copper on F joins the F pour only through vias (conservative)
    theta_jc=12.5,                              # C/W QPA9510 data sheet (23 Jun 2025) p.3
    pa_case_C=0.015,                            # J/K package + die (3 x 3 x 0.85 mm), ASSUMED
    emissivity=0.9,                             # solder mask
    radiation=True,
    sinks=[],                                   # extra paths to ambient (x0, y0, x1, y1, layer, W/m2K) for fixes
)

CU_LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
ANT_BOX = (-22.6, 8.9, -11.9, 12.7)             # src/layout.py: Bluetooth antenna, no copper on In1/In2/B, no pour on F


class Board:
    """The finite-difference board.  Unknowns: temperature rise above ambient
    of every cell of the four copper-layer nodes, plus the amplifier case."""

    def __init__(self, p, h_conv, t_amb):
        self.p = p
        dx = p['dx'] * 1e-3
        L = p['length'] - p['x_cut']
        self.x0 = -p['length'] / 2 + p['x_cut']
        self.nx = int(round(L / p['dx']))
        self.ny = int(round(p['width'] / p['dx']))
        self.dxm = L / self.nx * 1e-3
        self.dym = p['width'] / self.ny * 1e-3
        nx, ny = self.nx, self.ny
        self.xc = self.x0 + (np.arange(nx) + 0.5) * L / nx
        self.yc = -p['width'] / 2 + (np.arange(ny) + 0.5) * p['width'] / ny
        X, Y = np.meshgrid(self.xc, self.yc)
        self.X, self.Y = X, Y
        N = nx * ny
        self.N = N
        self.case = 4 * N
        n = 4 * N + 1
        A = self.dxm * self.dym
        # copper coverage maps
        cov = [np.full((ny, nx), c, float) for c in p['cov']]
        x0, y0, x1, y1 = ANT_BOX
        ant = (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
        for l in range(4):
            cov[l][ant] = 0.0
        # amplifier paddle cells (F): an island of solid copper
        pa = self.part_xy('U11')
        hp = p['paddle'] / 2 * 1e3 + 1e-6
        self.pad = (np.abs(X - pa[0]) <= hp) & (np.abs(Y - pa[1]) <= hp)
        if not self.pad.any():
            self.pad = (np.abs(X - pa[0]) <= p['dx']) & (np.abs(Y - pa[1]) <= p['dx'])
        cov[0][self.pad] = 1.0
        self.cov = cov
        # FR-4 thickness lumped into each copper node
        td = p['t_diel']
        share = [td[0] / 2, td[0] / 2 + td[1] / 2, td[1] / 2 + td[2] / 2, td[2] / 2]
        rows, cols, vals = [], [], []

        def link(i, j, g):
            rows.extend([i, j, i, j]); cols.extend([i, j, j, i])
            vals.extend([g, g, -g, -g])

        idx = np.arange(N).reshape(ny, nx)
        Cap = np.zeros(n)
        for l in range(4):
            S = p['k_cu'] * p['t_cu'][l] * cov[l] + p['k_fr4_xy'] * share[l]   # sheet conductance W/K
            base = l * N
            # x neighbours
            Sa, Sb = S[:, :-1], S[:, 1:]
            g = 2 * Sa * Sb / np.maximum(Sa + Sb, 1e-30) * self.dym / self.dxm
            if l == 0 and p['pa_island']:
                cut = self.pad[:, :-1] ^ self.pad[:, 1:]
                g = np.where(cut, p['k_fr4_xy'] * share[0] * self.dym / self.dxm, g)
            ia, ib = idx[:, :-1].ravel() + base, idx[:, 1:].ravel() + base
            rows.extend(np.r_[ia, ib, ia, ib]); cols.extend(np.r_[ia, ib, ib, ia])
            gv = g.ravel(); vals.extend(np.r_[gv, gv, -gv, -gv])
            Sa, Sb = S[:-1, :], S[1:, :]
            g = 2 * Sa * Sb / np.maximum(Sa + Sb, 1e-30) * self.dxm / self.dym
            if l == 0 and p['pa_island']:
                cut = self.pad[:-1, :] ^ self.pad[1:, :]
                g = np.where(cut, p['k_fr4_xy'] * share[0] * self.dxm / self.dym, g)
            ia, ib = idx[:-1, :].ravel() + base, idx[1:, :].ravel() + base
            rows.extend(np.r_[ia, ib, ia, ib]); cols.extend(np.r_[ia, ib, ib, ia])
            gv = g.ravel(); vals.extend(np.r_[gv, gv, -gv, -gv])
            Cap[base:base + N] = A * (p['rc_cu'] * p['t_cu'][l] * cov[l] + p['rc_fr4'] * share[l]).ravel()
        # vertical: dielectric + stitching vias (+ the paddle vias)
        a_bar = math.pi * ((p['via_drill'] / 2 + 0) ** 2 - (p['via_drill'] / 2 - p['plating']) ** 2)
        a_pa = math.pi * ((p['pa_via_drill'] / 2) ** 2 - (p['pa_via_drill'] / 2 - p['plating']) ** 2)
        a_fill = math.pi * (p['pa_via_drill'] / 2 - p['plating']) ** 2
        self.via = dict(a_barrel_stitch=a_bar, a_barrel_pa=a_pa)
        npad = self.pad.sum()
        for l in range(3):
            t = p['t_diel'][l] + (p['t_cu'][l] + p['t_cu'][l + 1]) / 2
            g = p['k_fr4_z'] * A / p['t_diel'][l] * np.ones((ny, nx))
            gvia = p['via_density'] * 1e4 * A * p['k_cu'] * a_bar / t
            g = g + gvia * np.minimum(cov[0] > 0, cov[3] > 0)
            gpa = p['pa_vias'] * (p['k_cu'] * a_pa + p['k_via_fill'] * a_fill) / t
            g = g + np.where(self.pad, gpa / npad, 0.0)
            ia = idx.ravel() + l * N
            ib = idx.ravel() + (l + 1) * N
            gv = g.ravel()
            rows.extend(np.r_[ia, ib, ia, ib]); cols.extend(np.r_[ia, ib, ib, ia])
            vals.extend(np.r_[gv, gv, -gv, -gv])
        # the case node: solder to the paddle cells
        g_sol = p['k_solder'] * p['paddle'] ** 2 * p['paste_frac'] / p['t_solder']
        self.g_solder = g_sol
        for c in idx[self.pad]:
            link(self.case, int(c), g_sol / npad)
        Cap[self.case] = p['pa_case_C']
        # faces to ambient
        if p['radiation']:
            ta = t_amb + 273.15
            ts = ta + 20.0             # linearised 20 K above ambient (see README)
            h_rad = p['emissivity'] * SIGMA * (ts ** 2 + ta ** 2) * (ts + ta)
        else:
            h_rad = 0.0
        self.h_rad = h_rad
        gamb = np.zeros(n)
        for l in (0, 3):
            gamb[l * N:(l + 1) * N] = (h_conv + h_rad) * A
        for (sx0, sy0, sx1, sy1, sl, hs) in p['sinks']:
            m = ((X > sx0) & (X < sx1) & (Y > sy0) & (Y < sy1)).ravel()
            gamb[sl * N + np.nonzero(m)[0]] += hs * A
        G = sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsc()
        G = G + sp.diags(gamb)
        self.G = G.tocsc()
        self.C = Cap
        self.gamb = gamb
        self._lu = {}

    # -- geometry helpers ----------------------------------------------------
    @staticmethod
    def part_xy(ref):
        x, y, rot, side = PLACEMENT[ref]
        return x, y

    def rect_weights(self, cx, cy, w, h, layer):
        """Node indices and weights (sum 1) under a w x h mm rectangle."""
        m = (np.abs(self.X - cx) <= w / 2) & (np.abs(self.Y - cy) <= h / 2)
        if not m.any():
            d = (self.X - cx) ** 2 + (self.Y - cy) ** 2
            m = d == d.min()
        ii = np.nonzero(m.ravel())[0] + layer * self.N
        return ii, np.full(len(ii), 1.0 / len(ii))

    def part_weights(self, ref, w, h):
        x, y, rot, side = PLACEMENT[ref]
        x = max(x, self.x0 + self.p['dx'])                 # parts cut off (study 4) sit at the new edge
        if rot % 180 == 90:
            w, h = h, w
        return self.rect_weights(x, y, w, h, 0 if side == 'T' else 3)

    def lu(self, dt):
        if dt not in self._lu:
            M = self.G if dt == 0 else self.G + sp.diags(self.C / dt)
            self._lu[dt] = spla.splu(M.tocsc())
        return self._lu[dt]

    def steady(self, q):
        return self.lu(0).solve(q)


# ---------------------------------------------------------------------------
# Parts, positions, sizes
PLACEMENT = {}


def load_placement():
    d = json.load(open(os.path.join(V1, 'src', 'placement.json')))
    d.pop('_nodes', None)
    PLACEMENT.update({k: tuple(v) for k, v in d.items()})


def ref(part, note=None):
    m = [c.ref for c in COMPS if c.part == part and (note is None or c.note == note)]
    assert len(m) == 1, (part, note, m)
    return m[0]


# body sizes (mm) used to spread a part's heat and to average the board under it
SIZE = {'QPA9510': (3, 3), 'TPS63810': (2.2, 1.4), 'L470n': (2.5, 2.0), 'TPS2121': (2, 2), 'BQ25185': (2.2, 2.0),
        'RB060MM': (3.5, 1.8), 'TPS259470A': (2, 2), 'TPS62840': (1.4, 1.0), 'L2u2': (2.0, 1.6),
        'SX1262': (4, 4), 'NRF52840': (7, 7), 'CSD25485F5': (1.5, 0.8), 'SSM10N954L': (2.0, 1.4),
        'R22m': (3.2, 1.6), 'JST_PH2': (6.0, 4.0), 'SKY13330': (2, 2), 'LFCN1000': (3.2, 1.6),
        'L8.1nH_PA': (2.5, 2.3), 'L3.6nH_0603': (1.6, 0.8), 'L5.1nH': (1.0, 0.5), 'L4.7nH_0603': (1.6, 0.8),
        'R68_0805': (2.0, 1.25), 'R150_0805': (2.0, 1.25), 'BGA7L1BN6': (1.1, 0.7), 'TLV75528': (1, 1),
        'TMP1075': (1.6, 1.2), 'NTC10K': (1.0, 0.5), 'LM66100': (2, 2.1), 'TPS22965': (2, 2), 'TPS22916': (0.8, 0.8),
        'BQ29700': (1.5, 1.5), 'XTAL32K': (3.2, 1.5), 'XTAL32M': (2.0, 1.6), 'TCXO32': (2.0, 1.6),
        'B3U': (3.0, 2.5), 'SLIDE': (6.7, 2.6), 'USBC': (8.9, 7.3), 'UFL': (3, 2.6), 'JST_GH6': (9, 4.3),
        'JST_SH2': (4, 4.3), 'JST_SH6': (8, 4.3), 'LED_R': (1.6, 0.8), 'LED_G': (1.6, 0.8), 'LED_B': (1.6, 0.8),
        'ANT2450': (3.2, 1.6), 'TVS2200': (2, 2), 'TPD4E05U06': (2.5, 1.0), 'ZENER4V7': (1.7, 1.25), 'NMOS': (1, 0.6),
        'FB120': (1.0, 0.5), 'HDR_2x10': (2, 2), 'TP': (1, 1)}
CAP_SIZE = {'og:C_0402': (1.0, 0.5), 'og:C_0603': (1.6, 0.8), 'og:C_0805': (2.0, 1.25)}


def size_of(c):
    if c.part in SIZE:
        return SIZE[c.part]
    fp = parts.PARTS[c.part]['fp']
    return CAP_SIZE.get(fp, (1.0, 0.5))


# ---------------------------------------------------------------------------
# Operating points (datasheets and the power simulations, sim/README.md)
VBAT_TX = 3.4        # V, cell under a burst (a worn / half-empty cell; burst study: 3.39 A worst)
TX = {   # name: (VCC, ICC, RF out W, TPS63810 efficiency)
    '1W': (2.7, 1.0, 1.00, 0.92),     # 30 dBm; TPS63810 Fig. 32: ~92-94 % at 1 A (2.7 V out, buck)
    '2.5W': (3.6, 2.0, 2.51, 0.89),   # 34 dBm; Fig. 32/33 ~91-93 % at 2 A, -2 pts for boost from a 3.4 V cell
    '3W': (4.0, 2.3, 3.16, 0.87),     # 35 dBm; ~89 % at 2.3 A from 3.6 V, -2 pts deeper boost; sim/README "85 % deep boost"
}
R_MUX = 0.090        # TPS2121 RON max -40..105 C, data sheet SLVSEA3F p.7
R_REVFET = 0.062     # CSD25485F5: 42 mOhm max at VGS -4.5 V, ~48 at -3.4 V, x1.3 hot (SLPS606B p.4) ASSUMED
R_PROT = 0.0036      # SSM10N954L 2.75 mOhm max x1.3 hot
R_SENSE = 0.022      # R22m
R_JST = 0.020        # JST PH contacts, 2 x 10 mOhm initial, ASSUMED half of the heat on the board side
R_CHOKE = 0.008      # 0908SQ-8N1 DCR (< 10 mOhm, Coilcraft) ASSUMED
IL_DB = dict(match=0.15, lpf=0.30, switch=0.35, lfcn=0.70)   # dB: match/LPF ASSUMED; SKY13330 0.35 max (p.3); LFCN-1000+ ~0.7 dB at 915 MHz (typ. table)
I_CHG = 0.497        # A, ISET 604 R (sim/README)
V_USB = 5.0          # V at the charger input (user's case: covers a 5.25 V port minus the Schottky)
VF_D4 = 0.33         # V, RB060MM-30 at 0.5 A (p.1: 0.40 typ at 1 A)


def tx_sources(power):
    """Watts per part during a burst (no USB: the cell carries everything)."""
    vcc, icc, pout, eta = TX[power]
    pdc = vcc * icc
    i_in = pdc / eta / VBAT_TX
    i_cell = i_in + 0.15
    s = {}
    s['U_PA'] = pdc - pout
    s['U_BB'] = pdc * (1 / eta - 1)
    s['U_MUX'] = i_in ** 2 * R_MUX
    s['Q_REV'] = i_cell ** 2 * R_REVFET
    s['Q_PROT'] = i_cell ** 2 * R_PROT
    s['R_SENSE'] = i_cell ** 2 * R_SENSE
    s['J_BAT'] = i_cell ** 2 * R_JST
    s['L_CHOKE'] = icc ** 2 * R_CHOKE
    p = pout
    for k in ('match', 'lpf', 'switch', 'lfcn'):
        loss = p * (1 - 10 ** (-IL_DB[k] / 10))
        s['RF_' + k] = loss
        p -= loss
    s['_ant'] = p
    s['U_SX'] = 3.3 * 0.102 - 0.100     # SX1262 +20 dBm: 102 mA (DS rev 1.2 Table 3-6 p.17) minus 100 mW RF
    s['R_PAD1'], s['R_PAD2'], s['R_PAD3'] = 0.073, 0.021, 0.004   # 15.9 dB pad (circuit.py: 73 mW in the first 68 R)
    s['U_BUCK'] = 0.45 * (1 / 0.90 - 1)  # TPS62840: ~136 mA at 3.3 V, 90 %
    s['U_NRF'] = 0.016
    s['U_APC'] = 0.005
    s['_i_in'] = i_in
    s['_i_cell'] = i_cell
    return s


LISTEN = {'U_NRF': 0.010, 'U_SX': 0.015, 'U_LNA': 0.016, 'U_BUCK': 0.005}


def chg_sources(vbat):
    i_in = I_CHG + 0.02
    return {'U_CHG': (V_USB - vbat) * I_CHG + (V_USB - 4.5) * 0.02, 'D_USB': VF_D4 * i_in, 'U_EFUSE': 0.045 * i_in ** 2}


def build_maps():
    """source name -> list of (ref, fraction); metric name -> (ref, psi, source name)."""
    lpf = [ref('L5.1nH'), ref('L4.7nH_0603')]
    src = {
        'U_PA': [('U11', 1.0)], 'U_BB': [(ref('TPS63810'), 1.0)], 'U_MUX': [(ref('TPS2121'), 1.0)],
        'Q_REV': [(ref('CSD25485F5'), 1.0)], 'Q_PROT': [(ref('SSM10N954L'), 1.0)], 'R_SENSE': [(ref('R22m'), 1.0)],
        'J_BAT': [(ref('JST_PH2'), 1.0)], 'L_CHOKE': [(ref('L8.1nH_PA'), 1.0)],
        'RF_match': [(ref('L3.6nH_0603'), 1.0)], 'RF_lpf': [(lpf[0], 0.5), (lpf[1], 0.5)],
        'RF_switch': [(ref('SKY13330'), 1.0)], 'RF_lfcn': [(ref('LFCN1000'), 1.0)],
        'U_SX': [(ref('SX1262'), 1.0)], 'U_BUCK': [(ref('TPS62840'), 0.7), (ref('L2u2'), 0.3)],
        'U_NRF': [(ref('NRF52840'), 1.0)], 'U_APC': [(ref('TLV75528'), 1.0)], 'U_LNA': [(ref('BGA7L1BN6'), 1.0)],
        'U_CHG': [(ref('BQ25185'), 1.0)], 'D_USB': [(ref('RB060MM', 'USB into the charger'), 1.0)],
        'U_EFUSE': [(ref('TPS259470A', 'USB eFuse'), 1.0)],
    }
    pads = [c.ref for c in COMPS if c.part in ('R68_0805', 'R150_0805')]
    pads.sort(key=lambda r: PLACEMENT[r][0])
    src['R_PAD1'] = [(pads[0], 1.0)]; src['R_PAD2'] = [(ref('R150_0805'), 1.0)]
    src['R_PAD3'] = [([r for r in pads if r != pads[0] and r != ref('R150_0805')][0], 1.0)]
    # junction metrics: Tj = board under the part + psi_JB x its own power
    met = {
        'QPA9510 Tj': ('U11', None, 'U_PA'),             # handled specially (case + theta_jc)
        'TPS63810 Tj': (ref('TPS63810'), 20.5, 'U_BB'),  # psi_JB, SLVSEK4C p.5
        'TPS2121 Tj': (ref('TPS2121'), 15.5, 'U_MUX'),   # psi_JB, SLVSEA3F p.7
        'CSD25485F5 Tj': (ref('CSD25485F5'), 30.0, 'Q_REV'),   # ASSUMED R_jb (only RthJA 90/245 C/W published)
        'BQ25185 Tj': (ref('BQ25185'), 34.7, 'U_CHG'),   # psi_JB, SLUSF65B p.5
        'TPS62840 Tj': (ref('TPS62840'), 39.4, 'U_BUCK'),
        'USB eFuse Tj': (ref('TPS259470A', 'USB eFuse'), 27.6, 'U_EFUSE'),
        'RB060MM (USB) Tj': (ref('RB060MM', 'USB into the charger'), 60.0, 'D_USB'),  # ASSUMED R_j-lead SOD-123FL
    }
    return src, met


TJMAX = {'QPA9510 Tj': 175.0, 'TPS63810 Tj': 125.0, 'TPS2121 Tj': 125.0, 'CSD25485F5 Tj': 150.0,
         'BQ25185 Tj': 125.0, 'TPS62840 Tj': 125.0, 'USB eFuse Tj': 125.0, 'RB060MM (USB) Tj': 150.0}


def ambient_rated():
    """Parts whose rating is an ambient / body temperature: the board under them
    is their 'ambient'.  ref -> (label, max C)."""
    d = {}
    lim = {'SX1262': 85, 'NRF52840': 85, 'SKY13330': 85, 'BGA7L1BN6': 85, 'BQ29700': 85, 'TPS22916': 85,
           'XTAL32K': 85, 'XTAL32M': 85, 'TCXO32': 105, 'LED_R': 85, 'LED_G': 85, 'LED_B': 85,
           'JST_PH2': 85, 'JST_GH6': 85, 'JST_SH2': 85, 'JST_SH6': 85, 'B3U': 70, 'SLIDE': 85, 'USBC': 85,
           'UFL': 90, 'LFCN1000': 100, 'L8.1nH_PA': 125, 'NTC10K': 125, 'TMP1075': 125}
    for c in COMPS:
        if c.part in lim:
            d[c.ref] = ('%s %s' % (c.part, c.ref), lim[c.part])
        elif 'X5R' in parts.PARTS[c.part].get('desc', ''):
            d[c.ref] = ('X5R %s %s' % (c.part, c.ref), 85)
    return d


# ---------------------------------------------------------------------------
# Transient engine
DT_ON = [0.005] * 4 + [0.02] * 4 + [0.05] * 18          # 1.0 s burst
DT_OFF1 = DT_ON                                         # first second after the burst


def schedule(t_off):
    s = [(dt, 1) for dt in DT_ON]
    if t_off > 0:
        s += [(dt, 0) for dt in DT_OFF1]
        s += [(1.0, 0)] * int(round(t_off - 1))
    return s


class Case:
    """One board (h, ambient, parameters) with its unit responses."""

    def __init__(self, p, h, tamb):
        self.p, self.h, self.tamb = p, h, tamb
        self.B = Board(p, h, tamb)
        self.src_map, self.met_map = build_maps()
        B = self.B
        self.Wsrc = {}
        for name, lst in self.src_map.items():
            v = np.zeros(B.G.shape[0])
            for r, f in lst:
                if r == 'U11':
                    v[B.case] += f
                    continue
                c = CBYREF[r]
                ii, w = B.part_weights(r, *size_of(c))
                v[ii] += f * w
            self.Wsrc[name] = v
        # metric weights
        self.Wmet = {}
        for m, (r, psi, sname) in self.met_map.items():
            if r == 'U11':
                v = np.zeros(B.G.shape[0]); v[B.case] = 1.0
            else:
                v = np.zeros(B.G.shape[0])
                ii, w = B.part_weights(r, *size_of(CBYREF[r])); v[ii] = w
            self.Wmet[m] = (v, psi if r != 'U11' else p['theta_jc'], sname)
        self.amb = ambient_rated()
        self.Wamb = {}
        for r in self.amb:
            v = np.zeros(B.G.shape[0]); ii, w = B.part_weights(r, *size_of(CBYREF[r])); v[ii] = w
            self.Wamb[r] = v
        v = np.zeros(B.G.shape[0]); v[B.case] = 1.0
        self.Wextra = {'QPA9510 case': v}
        for nm, r in (('battery plug J3', ref('JST_PH2')), ('NTC TH1', ref('NTC10K')), ('TMP1075', ref('TMP1075'))):
            v = np.zeros(B.G.shape[0]); ii, w = B.part_weights(r, *size_of(CBYREF[r])); v[ii] = w
            self.Wextra[nm] = v
        # every metric as one matrix (rows) for fast evaluation of transients
        self.names = list(self.Wmet) + list(self.Wextra) + list(self.Wamb)
        self.M = sp.csr_matrix(np.vstack([self.Wmet[k][0] for k in self.Wmet] + [self.Wextra[k] for k in self.Wextra]
                                         + [self.Wamb[k] for k in self.Wamb]))

    def q(self, powers):
        v = np.zeros(self.B.G.shape[0])
        for k, w in powers.items():
            if k in self.Wsrc:
                v += w * self.Wsrc[k]
        return v

    def own(self, powers, on=1.0):
        """psi x own power for each junction metric (row-aligned with names)."""
        a = np.zeros(len(self.names))
        for i, k in enumerate(self.Wmet):
            vw, psi, sname = self.Wmet[k]
            a[i] = psi * powers.get(sname, 0.0) * on
        return a

    def steady_metrics(self, powers):
        th = self.B.steady(self.q(powers))
        return self.M @ th + self.own(powers), th

    def periodic(self, powers, t_off, max_periods=8, tol=0.1):
        return self.periodic_multi([powers], t_off, max_periods, tol)[0]

    def periodic_multi(self, plist, t_off, max_periods=8, tol=0.1):
        """TX pattern only (one column per power set): 1 s on, t_off s off, run to
        a periodic state.  Returns per column: peak, mean, min per metric, the time
        trace, and the field at the end of the last burst."""
        Q = np.column_stack([self.q(pw) for pw in plist])
        own = np.column_stack([self.own(pw) for pw in plist])           # metrics x k
        if t_off == 0:
            th = self.B.steady(Q)
            m = self.M @ th + own
            return [dict(peak=m[:, k], mean=m[:, k], min=m[:, k], trace=None, field=th[:, k]) for k in range(len(plist))]
        duty = 1.0 / (1.0 + t_off)
        th = self.B.steady(Q * duty)
        sch = schedule(t_off)
        C = self.B.C[:, None]
        last = None
        for it in range(max_periods):
            tr_t, tr = [0.0], [self.M @ th]
            t = 0.0
            field = None
            for dt, on in sch:
                rhs = C / dt * th + (Q if on else 0.0)
                th = self.B.lu(dt).solve(rhs)
                t += dt
                tr_t.append(t)
                tr.append(self.M @ th + (own if on else 0.0))
                if on and abs(t - 1.0) < 1e-9:
                    field = th.copy()
            tr = np.array(tr)                    # steps x metrics x k
            pk = tr.max(axis=0)
            if last is not None and np.max(np.abs(pk - last)) < tol:
                break
            last = pk
        tr_t = np.array(tr_t)
        dts = np.diff(tr_t)
        mean = (tr[1:] * dts[:, None, None]).sum(axis=0) / dts.sum()
        mn = tr.min(axis=0)
        return [dict(peak=pk[:, k], mean=mean[:, k], min=mn[:, k], trace=(tr_t, tr[:, :, k]), field=field[:, k])
                for k in range(len(plist))]


# ---------------------------------------------------------------------------
def verdict_rows(case, tot_peak, charging, chg_frac):
    """Return list of (criterion, value, limit, verdict) and the overall verdict."""
    rows = []
    nm = case.names
    v = dict(zip(nm, tot_peak))
    tj, tc = v['QPA9510 Tj'], v['QPA9510 case']
    vt = 'FAIL' if (tc > 85 or tj > 175) else ('MARGINAL' if (tj > 160 or tc > 80) else 'PASS')
    rows.append(('QPA9510 case <= 85 (Tj <= 160)', '%.0f / %.0f' % (tc, tj), vt))
    for m in ('TPS63810 Tj', 'TPS2121 Tj', 'CSD25485F5 Tj', 'TPS62840 Tj', 'USB eFuse Tj', 'RB060MM (USB) Tj'):
        lim = TJMAX[m]
        if not charging and m in ('USB eFuse Tj', 'RB060MM (USB) Tj'):
            continue
        x = v[m]
        rows.append((m + ' <= %d' % (lim - 15), '%.0f' % x, 'FAIL' if x > lim else ('MARGINAL' if x > lim - 15 else 'PASS')))
    if charging:
        x = v['BQ25185 Tj']
        rows.append(('BQ25185 Tj <= TREG 100 (charge %d %%)' % round(100 * chg_frac), '%.0f' % x,
                     'FAIL' if x > 110 else ('MARGINAL' if chg_frac < 0.999 else 'PASS')))
    x = v['battery plug J3']
    if charging:
        rows.append(('cell area <= 45 (charging)', '%.0f' % x, 'FAIL' if x > 45 else ('MARGINAL' if x > 40 else 'PASS')))
    rows.append(('cell area <= 60', '%.0f' % x, 'FAIL' if x > 60 else ('MARGINAL' if x > 55 else 'PASS')))
    worst = None
    for r, (lab, lim) in case.amb.items():
        x = v[r]
        marg = lim - x
        if worst is None or marg < worst[0]:
            worst = (marg, lab, x, lim)
    marg, lab, x, lim = worst
    rows.append(('tightest rated part: %s <= %d' % (lab, lim), '%.0f' % x,
                 'FAIL' if marg < 0 else ('MARGINAL' if marg < 5 else 'PASS')))
    order = {'PASS': 0, 'MARGINAL': 1, 'FAIL': 2}
    overall = max((r[2] for r in rows), key=lambda s: order[s])
    return rows, overall


def inherent_fails(cs, listen_m):
    """Criteria that already fail while only listening: set by the ambient (a cell in a
    60 C box is at 60 C), not by transmitting; the duty tables leave them out."""
    rows, ov = verdict_rows(cs, cs.tamb + listen_m, False, 0.0)
    return set(r[0] for r in rows if r[2] == 'FAIL')


def duty_ok(rows, inherent):
    for crit, val, v in rows:
        if crit in inherent:
            continue
        if v == 'FAIL' or (v == 'MARGINAL' and 'QPA9510' in crit):
            return False
    return True


def combine(case, tx_res, listen_m, chg_m, chg_own, charging, kind='peak'):
    """Total temperatures (C) = ambient + TX periodic + listening + charging x fraction
    (the charger throttles at TREG 100 C)."""
    base = case.tamb + tx_res[kind] + listen_m
    frac = 0.0
    if charging:
        ib = case.names.index('BQ25185 Tj')
        unit = chg_m[ib]
        avail = 100.0 - base[ib]
        frac = 1.0 if unit <= avail else max(0.0, avail / unit)
        base = base + frac * chg_m
    return base, frac


NPROC = int(os.environ.get('NPROC', os.cpu_count() or 1))


def _work(p, h, ta, offs):
    cs = Case(p, h, ta)
    d = {}
    d[(h, ta, 'listen')], _ = cs.steady_metrics(LISTEN)
    d[(h, ta, 'chg')], _ = cs.steady_metrics(chg_sources(3.0))
    d[(h, ta, 'chg3.7')], _ = cs.steady_metrics(chg_sources(3.7))
    pws = list(TX)
    for off in offs:
        rs = cs.periodic_multi([tx_sources(pw) for pw in pws], off)
        for pw, r in zip(pws, rs):
            if not (h == 10.0 and ta == 60 and pw == '2.5W' and off == 3):
                r['field'] = None
            d[(h, ta, pw, off)] = r
    return d


ALL_FIXES = {'pa_island': False, 'k_via_fill': 385.0, 't_cu': [70e-6, 35e-6, 35e-6, 70e-6],
             'cov': [0.85, 1.0, 0.8, 0.85], 'via_density': 25.0}
PAD_SINK = [(15.0, -12.7, 25.0, -2.7, 3, 3000.0)]


def _maxduty_variant(ch, tambs, offs):
    """Highest passing duty (no charging, h = 10) per power and ambient for a variant."""
    pv = dict(PARAMS)
    pv.update(ch)
    outd = {}
    for ta in tambs:
        cs = Case(pv, 10.0, ta)
        lm, _ = cs.steady_metrics(LISTEN)
        cm, _ = cs.steady_metrics(chg_sources(3.0))
        best = {pw: 0.0 for pw in TX}
        inh = inherent_fails(cs, lm)
        for off in offs:
            for pw, r in zip(TX, cs.periodic_multi([tx_sources(pw) for pw in TX], off)):
                tot, frac = combine(cs, r, lm, cm, None, False)
                rows, ov = verdict_rows(cs, tot, False, frac)
                if duty_ok(rows, inh):
                    best[pw] = max(best[pw], 1.0 / (1 + off))
        for pw in TX:
            outd[(pw, ta)] = best[pw]
    return outd


def _variant(lab, ch, probe):
    pv = dict(PARAMS)
    h = ch.get('_h', 10.0)
    for k, v in ch.items():
        if not k.startswith('_'):
            pv[k] = v
    if ch.get('_shift'):
        pv['x_cut'] = -2 * ch['_shift']      # a longer board: parts stay put, length added at the USB end
    cs = Case(pv, h, 60)
    lm, _ = cs.steady_metrics(LISTEN)
    vals = []
    groups = {}
    for pw, off in probe:
        groups.setdefault(off, []).append(pw)
    got = {}
    for off, pws in groups.items():
        for pw, r in zip(pws, cs.periodic_multi([tx_sources(pw) for pw in pws], off)):
            got[(pw, off)] = r
    for pw, off in probe:
        v = dict(zip(cs.names, 60 + got[(pw, off)]['peak'] + lm))
        vals.append((v['QPA9510 case'], v['QPA9510 Tj'], v['TPS63810 Tj']))
    return vals


# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    global COMPS, CBYREF
    COMPS = circuit.build()
    CBYREF = {c.ref: c for c in COMPS}
    load_placement()
    p = dict(PARAMS)
    out('Mesh Radio v1 - thermal studies (sim/thermal/run.py), %s' % time.strftime('%Y-%m-%d'))
    out('Board %.0f x %.1f mm, grid %.2f mm; copper F/In1/In2/B %s um at coverage %s; via density %.0f /cm2'
        % (p['length'], p['width'], p['dx'], [round(t * 1e6, 1) for t in p['t_cu']], p['cov'], p['via_density']))
    pa = PLACEMENT['U11']
    out('QPA9510 (U11) at (%.2f, %.2f) mm top (placement.json; the task brief said ~(21.7, -6.7))' % (pa[0], pa[1]))

    # ---- via array and paddle numbers
    B = Board(p, 10.0, 25.0)
    a_pa = B.via['a_barrel_pa']
    t1 = p['t_diel'][0] + (p['t_cu'][0] + p['t_cu'][1]) / 2
    tall = sum(p['t_diel']) + sum(p['t_cu'][1:3]) + (p['t_cu'][0] + p['t_cu'][3]) / 2
    a_fill = math.pi * (p['pa_via_drill'] / 2 - p['plating']) ** 2
    g1 = p['k_cu'] * a_pa + p['k_via_fill'] * a_fill
    out()
    out('=' * 100)
    out('STUDY 1: board thermal model')
    out('=' * 100)
    out('Heat path from the QPA9510 die:')
    out('  junction -> case (paddle)      theta_jc %.1f C/W (QPA9510 data sheet 23 Jun 2025, p.3, CW)' % p['theta_jc'])
    out('  paddle solder (%.0f %% of 1.5 mm sq wetted, %.0f um SAC305)  %.2f C/W' % (100 * p['paste_frac'], p['t_solder'] * 1e6, 1 / B.g_solder))
    out('  one 0.3 mm via, %.0f um plating, resin-filled: barrel %.4f mm2; F->In1 %.0f C/W, F->B %.0f C/W'
        % (p['plating'] * 1e6, a_pa * 1e6, t1 / g1, tall / g1))
    out('  nine in parallel (src/board.py PA_VIAS): F->In1 %.1f C/W, F->B %.1f C/W' % (t1 / g1 / 9, tall / g1 / 9))
    out('  (copper-filled vias would be %.1f C/W F->B for nine)' % (tall / (p['k_cu'] * math.pi * (p['pa_via_drill'] / 2) ** 2) / 9))
    sheet = [p['k_cu'] * t * c for t, c in zip(p['t_cu'], p['cov'])]
    out('  copper sheet conductance per square: F %.1f, In1 %.1f, In2 %.1f, B %.1f mW/K (sum %.1f)'
        % tuple([s * 1e3 for s in sheet] + [sum(sheet) * 1e3]))

    # ---- the operating points
    out()
    out('Heat sources during a 1 s burst (W), cell at %.1f V under load, no USB:' % VBAT_TX)
    hdr = ['', 'PA (VCC x ICC - RF)', 'TPS63810', 'TPS2121', 'rev FET', 'prot FET+sense+plug', 'RF filters/switch',
           'SX1262+pad', 'other', 'total', 'into antenna', 'cell A']
    out('  ' + ' | '.join(hdr))
    for pw in TX:
        s = tx_sources(pw)
        rf = sum(v for k, v in s.items() if k.startswith('RF_'))
        oth = s['U_BUCK'] + s['U_NRF'] + s['U_APC'] + s['L_CHOKE']
        tot = sum(v for k, v in s.items() if not k.startswith('_'))
        out('  %-5s | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f W (%.1f dBm) | %.2f'
            % (pw, s['U_PA'], s['U_BB'], s['U_MUX'], s['Q_REV'], s['Q_PROT'] + s['R_SENSE'] + s['J_BAT'], rf,
               s['U_SX'] + s['R_PAD1'] + s['R_PAD2'] + s['R_PAD3'], oth, tot, s['_ant'], 10 * math.log10(s['_ant'] * 1e3), s['_i_cell']))
    out('  PA supply: 1 W 1.0 A at 2.7 V; 2.5 W 2.0 A at 3.6 V; 3 W 2.3 A at 4.0 V (docs/plan.md, sim burst study)')
    out('  Listening: %.3f W in all (nRF52840, SX1262 RX, LNA, buck)' % sum(LISTEN.values()))
    for vb in (3.0, 3.7, 4.1):
        c = chg_sources(vb)
        out('  USB charging, cell %.1f V: BQ25185 %.2f W ((5.0 - VBAT) x 0.497 A + SYS), Schottky D4 %.2f W, eFuse %.3f W'
            % (vb, c['U_CHG'], c['D_USB'], c['U_EFUSE']))

    # ---- run every (h, ambient)
    TAMBS = [-40, -20, 0, 25, 60, 85]
    HS = [10.0, 5.0]
    OFFS = [59, 29, 14, 5, 3, 1, 0]                 # 1 s on, t_off off: duty 1/60 ... continuous
    NAMED = {59: '1 msg/min', 3: 'storm 25 %', 1: 'storm 50 %', 0: 'continuous'}
    res = {}
    keep = {}
    jobs = [(h, ta) for h in HS for ta in TAMBS]
    with mp.Pool(NPROC) as pool:
        for (h, ta), d in zip(jobs, pool.starmap(_work, [(p, h, ta, OFFS) for h, ta in jobs])):
            res.update(d)
            keep[(h, ta)] = Case(p, h, ta)
            print('  h=%g Ta=%g done (%.0f s)' % (h, ta, time.time() - t0), file=sys.stderr)
    names = keep[(10.0, 25)].names
    out()
    out('Radiation (eps 0.9) linearised 20 K above ambient: h_rad = %s W/m2K at %s C'
        % ([round(keep[(10.0, t)].B.h_rad, 1) for t in TAMBS], TAMBS))
    # listening
    out()
    out('--- Steady listening (no transmit): rise above ambient, C')
    for h in HS:
        lm = res[(h, 25, 'listen')]
        out('  h=%g: QPA9510 case +%.2f, nRF52840 +%.2f, SX1262 +%.2f, cell area +%.2f  -> PASS from -40 to 60 C;'
            ' at 85 C the 85 C-rated parts sit 1-2 C over their limit (MARGINAL, inherent to an 85 C box)'
            % (h, lm[names.index('QPA9510 case')], lm[names.index(ref('NRF52840'))], lm[names.index(ref('SX1262'))],
               lm[names.index('battery plug J3')]))

    # main table
    out()
    out('--- Transmit cases: peak temperatures (C) during the burst, periodic steady state')
    out('    "cell" = board under the battery plug J3 (the cell sits there); charging = USB at the same time, cell 3.0 V')
    summary = {}
    for h in HS:
        out()
        out('h = %g W/m2K (%s)' % (h, 'still air in an enclosure' if h == 10 else 'small sealed case'))
        out('  %-6s %-5s %-11s %-3s | %5s %5s %5s %5s %5s %5s %5s %5s | %-8s %s'
            % ('Ta', 'power', 'duty', 'chg', 'PA Tj', 'case', '63810', '2121', 'revFET', '25185', 'cell', 'NTC', 'verdict', 'binding'))
        for ta in TAMBS:
            for pw in TX:
                for off in (59, 3, 1, 0):
                    for chg in (False, True):
                        cs = keep[(h, ta)]
                        r = res[(h, ta, pw, off)]
                        tot, frac = combine(cs, r, res[(h, ta, 'listen')], res[(h, ta, 'chg')], None, chg)
                        rows, ov = verdict_rows(cs, tot, chg, frac)
                        bad = [x for x in rows if x[2] == ov and ov != 'PASS']
                        v = dict(zip(names, tot))
                        note = '; '.join('%s = %s' % (b[0], b[1]) for b in bad[:3])
                        if chg and (ta < 0):
                            note = '(charging is blocked below 0 C by TS/firmware) ' + note
                        out('  %-6s %-5s %-11s %-3s | %5.0f %5.0f %5.0f %5.0f %5.0f %5.0f %5.0f %5.0f | %-8s %s'
                            % (ta, pw, NAMED[off], 'yes' if chg else 'no', v['QPA9510 Tj'], v['QPA9510 case'], v['TPS63810 Tj'],
                               v['TPS2121 Tj'], v['CSD25485F5 Tj'], v['BQ25185 Tj'] if chg else float('nan'),
                               v['battery plug J3'], v['NTC TH1'], ov, note))
                        summary[(h, ta, pw, off, chg)] = (ov, rows, v, frac)

    # ---- maximum duty cycle that passes, per ambient (firmware throttle table)
    out()
    out('--- Highest transmit duty cycle that passes every criterion (1 s messages), no charging')
    out('    (largest passing point of duty 1/60, 1/30, 1/15, 1/6, 1/4, 1/2, 1; none = not even one message a minute)')
    maxduty = {}
    inherent_note = set()
    for h in HS:
        out('  h = %g:' % h)
        for pw in TX:
            line = []
            for ta in TAMBS:
                cs = keep[(h, ta)]
                ok = 0.0
                inh = inherent_fails(cs, res[(h, ta, 'listen')])
                if inh:
                    inherent_note.add('%g C: %s' % (ta, '; '.join(sorted(inh))))
                for off in OFFS:
                    d = 1.0 / (1 + off)
                    tot, frac = combine(cs, res[(h, ta, pw, off)], res[(h, ta, 'listen')], res[(h, ta, 'chg')], None, False)
                    rows, ov = verdict_rows(cs, tot, False, frac)
                    if duty_ok(rows, inh):
                        ok = d
                maxduty[(h, pw, ta)] = ok
                line.append('%5s C: %s' % (ta, ('%.0f %%' % (100 * ok)) if ok >= 0.1 else ('1/%d' % round(1 / ok) if ok > 0 else 'none')))
            out('    %-5s ' % pw + ' | '.join(line))

    out('  left out because they fail with the radio only listening (set by the ambient, not by transmitting):')
    for n in sorted(inherent_note):
        out('    ' + n)

    # ---- charging-only table and the NTC
    out()
    out('--- USB charging alone (listening), cell at 3.0 / 3.7 V')
    out('  %-5s %-4s %-5s | %-10s %-9s %-7s %-7s %-6s' % ('h', 'Ta', 'VBAT', 'BQ25185 Tj', 'charge %', 'cell C', 'NTC C', 'D4 Tj'))
    chg_tab = {}
    for h in HS:
        for ta in TAMBS:
            for vb in (3.0, 3.7):
                cm = res[(h, ta, 'chg' if vb == 3.0 else 'chg3.7')]
                lm = res[(h, ta, 'listen')]
                ib = names.index('BQ25185 Tj')
                base = ta + lm
                avail = 100 - base[ib]
                frac = 1.0 if cm[ib] <= avail else max(0.0, avail / cm[ib])
                tot = base + frac * cm
                v = dict(zip(names, tot))
                chg_tab[(h, ta, vb)] = (ta + lm[ib] + cm[ib], frac, v)
                out('  %-5g %-4d %-5.1f | %-10.0f %-9.0f %-7.0f %-7.0f %-6.0f' % (h, ta, vb, ta + lm[ib] + cm[ib], 100 * frac,
                                                                             v['battery plug J3'], v['NTC TH1'], v['RB060MM (USB) Tj']))
    out('  (BQ25185 Tj column is without throttling; "charge %" is what TREG 100 C leaves; cell and NTC columns are after throttling)')

    out()
    out('--- Charging current options (ISET), cell 3.0 V, listening, h = 10 (scaled from the 497 mA run; loss ~ current)')
    out('  %-8s %-5s | %-10s %-9s %-7s %-7s' % ('ICHG', 'Ta', 'BQ25185 Tj', 'charge %', 'cell C', 'NTC C'))
    for ichg in (0.497, 0.400, 0.300, 0.200):
        for ta in (0, 25, 40):
            ta_key = 25 if ta == 40 else ta
            cm = res[(10.0, ta_key, 'chg')] * (ichg / I_CHG)
            lm = res[(10.0, ta_key, 'listen')]
            ib = names.index('BQ25185 Tj')
            base = ta + lm
            avail = 100 - base[ib]
            frac = 1.0 if cm[ib] <= avail else max(0.0, avail / cm[ib])
            v = dict(zip(names, base + frac * cm))
            out('  %-8s %-5d | %-10.0f %-9.0f %-7.0f %-7.0f' % ('%d mA' % round(ichg * 1e3), ta, ta + lm[ib] + cm[ib],
                                                             100 * frac, v['battery plug J3'], v['NTC TH1']))
    out('  (40 C uses the 25 C board solution shifted by 15 C; ISET = 300 A.ohm / I: 604 R -> 497 mA, 750 R -> 400 mA,'
        ' 1.0 k -> 300 mA, 1.5 k -> 200 mA)')

    out()
    out('--- Highest passing duty (no charging, h = 10) with the board fixes')
    fixv = (('ALL board fixes', dict(ALL_FIXES)), ('ALL board fixes + thermal pad to metal wall', dict(ALL_FIXES, sinks=PAD_SINK)))
    with mp.Pool(NPROC) as pool:
        parts_md = pool.starmap(_maxduty_variant, [(ch, [ta], OFFS) for lab, ch in fixv for ta in (25, 60)])
    for k, (lab, ch) in enumerate(fixv):
        md = dict(parts_md[2 * k]); md.update(parts_md[2 * k + 1])
        out('  %s:' % lab)
        for pw in TX:
            out('    %-5s ' % pw + ' | '.join('%d C: %s' % (ta, ('%.0f %%' % (100 * md[(pw, ta)])) if md[(pw, ta)] >= 0.1 else
                                                         ('1/%d' % round(1 / md[(pw, ta)]) if md[(pw, ta)] > 0 else 'none'))
                                          for ta in (25, 60)))
        print('  fixes max duty %s (%.0f s)' % (lab, time.time() - t0), file=sys.stderr)

    # TMP1075 vs PA case: offsets for a firmware limit
    out()
    out('--- TMP1075 (U17, bottom, under the PA end) against the PA case, 60 C ambient, h = 10')
    offs = []
    for pw in TX:
        for off in (59, 14, 3, 1, 0):
            r = res[(10.0, 60, pw, off)]
            i_c, i_t = names.index('QPA9510 case'), names.index('TMP1075')
            d = r['peak'][i_c] - r['mean'][i_t]
            offs.append(d)
            out('  %-5s duty 1/%-3d PA case peak - TMP1075 mean = %.1f C (TMP1075 mean rise %.1f C)'
                % (pw, 1 + off, d, r['mean'][i_t]))
    for k, pw in enumerate(TX):
        o = max(offs[5 * k:5 * k + 5])
        out('  -> %s: the burst alone lifts the PA case %.0f C above the TMP1075; to hold the case at 85 C the TMP1075 must'
            ' read below %.0f C before a message%s' % (pw, o, 85 - o, '' if 85 - o > 0 else ' (impossible: never at this power)'))
    out('  The spike happens inside the 1 s burst, within 2-3 mm of the PA: the TMP1075 (3 mm away, under the board) sees'
        ' the slow average only.  It can enforce the duty-cycle limit, not protect a single burst.')

    # ---- burst swing (solder fatigue)
    out()
    out('--- Temperature swing per burst at 25 C, h=10, one message a minute (solder-joint cycling)')
    for pw in TX:
        r = res[(10.0, 25, pw, 59)]
        tr_t, tr = r['trace']
        for m in ('QPA9510 case', 'TPS63810 Tj', 'TPS2121 Tj'):
            i = names.index(m)
            out('  %-5s %-13s swing %.1f C (peak %.1f, before burst %.1f)' % (pw, m, tr[:, i].max() - tr[0, i], tr[:, i].max() + 25, tr[0, i] + 25))

    # sensitivity and fixes (60 C, h = 10)
    out()
    out('--- Sensitivity and fixes: 60 C ambient, PA case / PA Tj / TPS63810 Tj peak, C')
    variants = [
        ('baseline (as placed, coverage 70/100/50/70 %)', {}),
        ('h=5 and no radiation (worst sealed box)', {'radiation': False, '_h': 5.0}),
        ('copper coverage 50/100/30/50 %', {'cov': [0.5, 1.0, 0.3, 0.5]}),
        ('copper coverage 85/100/80/85 % (solid pours)', {'cov': [0.85, 1.0, 0.8, 0.85]}),
        ('2 oz outer + 1 oz inner copper', {'t_cu': [70e-6, 35e-6, 35e-6, 70e-6]}),
        ('PA paddle joined to the top pour (no island)', {'pa_island': False}),
        ('copper-filled paddle vias (VIPPO Cu)', {'k_via_fill': 385.0}),
        ('stitching vias 25 /cm2 round the PA end', {'via_density': 25.0}),
        ('thermal pad 10x10 mm under PA end to a metal case wall', {'sinks': [(15.0, -12.7, 25.0, -2.7, 3, 3000.0)]}),
        ('M2 screw at the PA-end hole to a metal standoff/wall', {'sinks': [(26.4, -12.1, 30.4, -8.1, 3, 1500.0)]}),
        ('board 52 mm (10 mm off the USB end)', {'x_cut': 10.0}),
        ('board 72 mm (10 mm longer at the USB end)', {'_shift': 5.0}),
        ('board 42 mm (20 mm off the USB end)', {'x_cut': 20.0}),
        ('ALL board fixes (no island, Cu vias, 2/1 oz, 85 % pours, 25 vias/cm2)', dict(ALL_FIXES)),
        ('ALL board fixes + 10x10 mm thermal pad to a metal wall', dict(ALL_FIXES, sinks=PAD_SINK)),
    ]
    probe = [('1W', 59), ('1W', 3), ('2.5W', 59), ('2.5W', 3), ('3W', 59), ('3W', 3)]
    out('  %-55s ' % '' + ' '.join('%-17s' % ('%s 1/%d' % (pw, 1 + off) if off else '%s cont.' % pw) for pw, off in probe))
    sens = {}
    with mp.Pool(NPROC) as pool:
        vals_all = pool.starmap(_variant, [(lab, ch, probe) for lab, ch in variants])
    for (lab, ch), vals in zip(variants, vals_all):
        sens[lab] = vals
        out('  %-55s ' % lab + ' '.join('%3.0f/%3.0f/%3.0f      ' % v for v in vals))

    # ---- plots
    plot_field(keep[(10.0, 60)], res[(10.0, 60, '2.5W', 3)], 'thermal_map.png',
               '2.5 W, 25 % storm, 60 C ambient, h = 10: end of a burst')
    plot_trace(res, names)
    plot_maxduty(maxduty, TAMBS)
    plot_charging(chg_tab, TAMBS)
    plot_sens(sens, probe)

    study2_3()
    out()
    out('run time %.0f s' % (time.time() - t0))
    open(os.path.join(HERE, 'results.txt'), 'w').write('\n'.join(OUT) + '\n')


# ---------------------------------------------------------------------------
# Plots: one plain style; categorical slots 1-3 of the reference palette
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
SER = ['#2a78d6', '#eb6834', '#1baf7a']
SEQ = LinearSegmentedColormap.from_list('seq', ['#f4f8fd', '#9cc3ef', '#2a78d6', '#0d3a73'])


def style(ax):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def plot_field(cs, r, fn, title):
    B = cs.B
    th = r['field']
    fig, axs = plt.subplots(2, 1, figsize=(8, 6.2))
    vmax = cs.tamb + th.max()
    for ax, l, nm in ((axs[0], 0, 'top (F.Cu)'), (axs[1], 3, 'bottom (B.Cu), seen from the top')):
        T = cs.tamb + th[l * B.N:(l + 1) * B.N].reshape(B.ny, B.nx)
        im = ax.imshow(T, origin='upper', extent=[B.xc[0], B.xc[-1], B.yc[-1], B.yc[0]], cmap=SEQ, vmin=cs.tamb, vmax=vmax,
                       aspect='equal')
        for rr, lab in (('U11', 'PA'), (ref('TPS63810'), '63810'), (ref('TPS2121'), '2121'), (ref('JST_PH2'), 'J3 cell'),
                        (ref('BQ25185'), 'charger'), (ref('NRF52840'), 'nRF'), (ref('SX1262'), 'SX1262')):
            x, y, rot, side = PLACEMENT[rr]
            if (side == 'T') == (l == 0):
                ax.plot(x, y, 'o', ms=3, color=INK)
                ax.annotate(lab, (x, y), xytext=(3, 3), textcoords='offset points', fontsize=7, color=INK)
        ax.set_title(nm, fontsize=9, color=INK, loc='left')
        ax.tick_params(colors=INK2, labelsize=7)
        cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
        cb.set_label('C', fontsize=8)
        cb.ax.tick_params(labelsize=7)
    axs[1].set_xlabel('x along the board (mm, USB end left)', fontsize=8, color=INK2)
    fig.suptitle(title + ' (PA case %.0f C)' % (cs.tamb + th[B.case]), fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, fn), dpi=130)
    plt.close(fig)


def plot_trace(res, names):
    fig, ax = plt.subplots(figsize=(8, 4))
    i = names.index('QPA9510 Tj')
    j = names.index('QPA9510 case')
    for k, pw in enumerate(TX):
        tr_t, tr = res[(10.0, 60, pw, 3)]['trace']
        ax.plot(tr_t, 60 + tr[:, i], color=SER[k], lw=2, label='%s junction' % pw)
        ax.plot(tr_t, 60 + tr[:, j], color=SER[k], lw=1.2, ls='--', label='%s case' % pw)
    ax.axhline(85, color=INK2, lw=1, ls=':')
    ax.text(3.95, 86, 'case limit 85 C', ha='right', fontsize=8, color=INK2)
    ax.axhline(160, color=INK2, lw=1, ls=':')
    ax.text(3.95, 161, 'junction 175 C - 15 C margin', ha='right', fontsize=8, color=INK2)
    ax.set_xlabel('time in one 4 s period: 1 s burst, 3 s off (s)', fontsize=9, color=INK2)
    ax.set_ylabel('QPA9510 temperature (C)', fontsize=9, color=INK2)
    ax.set_title('Amplifier during a 25 % message storm, 60 C sealed box, h = 10', fontsize=10, color=INK, loc='left')
    style(ax)
    ax.legend(fontsize=7, frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'pa_burst.png'), dpi=130)
    plt.close(fig)


def plot_maxduty(md, tambs):
    levels = [0.0, 1 / 60, 1 / 30, 1 / 15, 1 / 6, 1 / 4, 1 / 2, 1.0]
    labels = ['none', '1/60', '1/30', '1/15', '1/6', '25 %', '50 %', 'always']
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    for ax, h in zip(axs, (10.0, 5.0)):
        for k, pw in enumerate(TX):
            y = [min(range(len(levels)), key=lambda i: abs(levels[i] - md[(h, pw, t)])) + 0.06 * (k - 1) for t in tambs]
            ax.plot(tambs, y, '-o', color=SER[k], lw=2, ms=5, label=pw)
        ax.set_yticks(range(len(levels)))
        ax.set_yticklabels(labels)
        ax.set_xlabel('ambient (C)', fontsize=9, color=INK2)
        ax.set_title('h = %g W/m2K' % h, fontsize=10, color=INK, loc='left')
        style(ax)
    axs[0].set_ylabel('1 s messages allowed (duty)', fontsize=9, color=INK2)
    axs[0].legend(fontsize=8, frameon=False)
    fig.suptitle('Highest transmit duty that passes every limit (board as placed, no charging)', fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'max_duty.png'), dpi=130)
    plt.close(fig)


def plot_charging(tab, tambs):
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
    for k, vb in enumerate((3.0, 3.7)):
        axs[0].plot(tambs, [tab[(10.0, t, vb)][0] for t in tambs], '-o', color=SER[k], lw=2, ms=5, label='cell %.1f V' % vb)
        axs[1].plot(tambs, [100 * tab[(10.0, t, vb)][1] for t in tambs], '-o', color=SER[k], lw=2, ms=5, label='cell %.1f V' % vb)
    axs[0].axhline(100, color=INK2, ls=':', lw=1)
    axs[0].text(tambs[0], 102, 'TREG 100 C', fontsize=8, color=INK2)
    axs[0].set_ylabel('BQ25185 junction, unthrottled (C)', fontsize=9, color=INK2)
    axs[1].set_ylabel('charge current left by TREG (%)', fontsize=9, color=INK2)
    for ax in axs:
        ax.set_xlabel('ambient (C)', fontsize=9, color=INK2)
        style(ax)
        ax.legend(fontsize=8, frameon=False)
    fig.suptitle('USB charging at 497 mA, listening, h = 10', fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'charging.png'), dpi=130)
    plt.close(fig)


def plot_sens(sens, probe):
    labs = list(sens)
    k = [i for i, (pw, off) in enumerate(probe) if (pw, off) == ('2.5W', 3)][0]
    vals = [sens[l][k][0] for l in labs]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(labs))[::-1]
    ax.barh(y, [v - 60 for v in vals], left=60, color=SER[0], height=0.6)
    for yy, v in zip(y, vals):
        ax.text(v + 1, yy, '%.0f' % v, va='center', fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=8)
    ax.axvline(85, color=INK2, ls=':', lw=1)
    ax.text(86, y[0] + 0.45, 'case limit 85 C', fontsize=8, color=INK2)
    ax.set_xlabel('QPA9510 case peak (C), 2.5 W, 25 % storm, 60 C, h = 10', fontsize=9, color=INK2)
    style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'fixes.png'), dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Studies 2 and 3: data from the makers' data sheets
# key: (low C, high C, what the rating is, source).  'v' = read from a copy of the
# data sheet in this session; 'd' = distributor listing / series spec, copy not read.
RATING = {
    'ANT2450': (-40, 125, 'operating', 'Johanson 2450AT18A100 data sheet r4 p.1', 'v'),
    'B3U': (-25, 70, 'ambient operating', 'Omron B3U data sheet (en-b3u) p.1', 'v'),
    'BGA7L1BN6': (-40, 85, 'ambient TA', 'Infineon BGA7L1BN6 data sheet p.9', 'v'),
    'BQ25185': (-40, 125, 'junction TJ', 'TI SLUSF65B p.6', 'v'),
    'BQ29700': (-40, 85, 'ambient TFUNC', 'TI BQ29700 data sheet p.4/p.5', 'v'),
    'C100n': (-55, 125, 'X7R class', 'EIA X7R class (Samsung CL05B series)', 'd'),
    'C100p': (-55, 125, 'C0G class', 'Murata GRM1555C series', 'd'),
    'C10n': (-55, 125, 'X7R class', 'Samsung CL05B series', 'd'),
    'C10u': (-55, 85, 'X5R class', 'Samsung CL10A series (X5R)', 'd'),
    'C10u25': (-55, 85, 'X5R class', 'Samsung CL21A series (X5R)', 'd'),
    'C12p': (-55, 125, 'C0G class', 'Samsung CL05C series', 'd'),
    'C1n': (-55, 125, 'C0G class', 'Murata GRM1555C series', 'd'),
    'C1u': (-55, 85, 'X5R class', 'Samsung CL05A series (X5R)', 'd'),
    'C1u25': (-55, 125, 'X7R class', 'Samsung CL10B series', 'd'),
    'C22u16': (-55, 85, 'X5R class', 'Murata GRM21BR61C226ME44 (R6 = X5R)', 'd'),
    'C470n': (-55, 85, 'X5R class', 'Samsung CL05A series (X5R)', 'd'),
    'C47n': (-55, 125, 'X7R class', 'Samsung CL05B series', 'd'),
    'C47u': (-55, 85, 'X5R class', 'Samsung CL21A series (X5R)', 'd'),
    'C4u7': (-55, 85, 'X5R class', 'Samsung CL10A series (X5R)', 'd'),
    'C820p': (-55, 125, 'C0G class', 'Murata GRM1555C series', 'd'),
    'CSD25485F5': (-55, 150, 'junction TJ', 'TI SLPS606B p.1', 'v'),
    'FB120': (-55, 125, 'operating', 'Murata BLM15AG series', 'd'),
    'HDR_2x10': (None, None, 'not fitted', '-', '-'),
    'HV0.7pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'), 'HV1.5pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'),
    'HV10pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'), 'HV15pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'),
    'HV2.7pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'), 'HV3.3pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'),
    'HV4.3pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'), 'HV47pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'),
    'HV5.6pF': (-55, 125, 'C0G class', 'Murata GQM series', 'd'),
    'JST_GH6': (-25, 85, 'incl. temperature rise', 'JST GH catalogue (same as PH/SH; docs/part-audit.md)', 'd'),
    'JST_PH2': (-25, 85, 'incl. temperature rise', 'JST PH catalogue p.1 (copy in session)', 'v'),
    'JST_SH2': (-25, 85, 'incl. temperature rise', 'JST SH catalogue (docs/part-audit.md)', 'd'),
    'JST_SH6': (-25, 85, 'incl. temperature rise', 'JST SH catalogue (docs/part-audit.md)', 'd'),
    'L1.6nH': (-55, 125, 'operating', 'Murata LQG15HS series', 'd'),
    'L10u': (-55, 125, 'operating', 'TDK MLZ2012 series', 'd'),
    'L11nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'), 'L11nH_0603': (-55, 125, 'operating', 'Murata LQW18AN series', 'd'),
    'L15nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'), 'L15u': (-55, 125, 'operating', 'TDK MLZ2012 series', 'd'),
    'L2.5nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'), 'L2.7nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'),
    'L2u2': (-40, 125, 'incl. self-heating', 'Murata DFE201610E series', 'd'),
    'L3.6nH_0603': (-55, 125, 'operating', 'Murata LQW18AN series', 'd'), 'L3.9nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'),
    'L4.7nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'), 'L4.7nH_0603': (-55, 125, 'operating', 'Murata LQW18AN series', 'd'),
    'L470n': (-40, 125, 'incl. self-heating', 'Murata DFE252012F series', 'd'),
    'L47nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'), 'L5.1nH': (-55, 125, 'operating', 'Murata LQW15AN series', 'd'),
    'L8.1nH_PA': (-40, 125, 'ambient; full Irms to +80 C only', 'Coilcraft 0806SQ/0807SQ/0908SQ series (distributor: -40..80 C)', 'd'),
    'LED_B': (-55, 85, 'operating', 'Lite-On LTST-C191 data sheet (third-party copy, Rev H)', 'd'),
    'LED_G': (-55, 85, 'operating', 'Lite-On LTST-C191 series', 'd'),
    'LED_R': (-55, 85, 'operating', 'Lite-On LTST-C191KRKT DS22-2000-223 Rev H', 'd'),
    'LFCN1000': (-55, 100, 'operating', 'Mini-Circuits LFCN-1000+ data sheet p.1', 'v'),
    'LM66100': (-40, 125, 'junction TJ', 'TI LM66100 data sheet p.4', 'v'),
    'NMOS': (-55, 150, 'channel Tch (storage -55)', 'Toshiba SSM3K56ACT data sheet', 'd'),
    'NRF52840': (-40, 85, 'ambient TA', 'Nordic nRF52840 PS v1.1 p.611', 'v'),
    'NTC10K': (-40, 125, 'operating', 'Murata NCP15 series', 'd'),
    'QPA9510': (-40, 85, 'case TCASE (Tj 175 C for 1e6 h MTTF)', 'Qorvo QPA9510 data sheet 23 Jun 2025 p.2', 'v'),
    'R0R': (-55, 155, 'operating', 'Yageo RC_L series', 'd'), 'R1.5M': (-55, 155, 'operating', 'Yageo RC_L series', 'd'),
    'R100k': (-55, 155, 'operating', 'Yageo RC_L series', 'd'), 'R10k': (-55, 155, 'operating', 'Yageo RC_L series', 'd'),
    'R137k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R13k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R150_0805': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R1M': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R1k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R2.21k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R2.2k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R2.49k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R22.1k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R220R': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R220k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R22R': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R22m': (-55, 155, 'operating', 'Panasonic ERJ-8BW series', 'd'), 'R261k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R267k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R287k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R301k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R330R': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R330k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R383k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R4.7k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R470R': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R47k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R5.1k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R510k': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R562k': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'R604R': (-55, 155, 'operating', 'Yageo RC_L', 'd'), 'R68_0805': (-55, 155, 'operating', 'Yageo RC_L', 'd'),
    'RB060MM': (None, 150, 'junction Tj (no low limit; storage -55)', 'Rohm RB060MM-30 data sheet Rev.003 p.1', 'v'),
    'SKY13330': (-40, 85, 'operating TOP', 'Skyworks SKY13330-397LF data sheet p.3', 'v'),
    'SLIDE': (-40, 85, 'operating', 'C&K JS series (distributor listings agree)', 'd'),
    'SSM10N954L': (None, 150, 'channel Tch (storage -55)', 'Toshiba SSM10N954L data sheet p.2', 'v'),
    'SX1262': (-40, 85, 'operating (under bias)', 'Semtech SX1261/2 DS rev 1.2 Table 3-3 p.14', 'v'),
    'TCXO32': (-40, 105, 'operating (-AP code)', 'ECS-TXO-20CSMV4 data sheet p.1', 'v'),
    'TLV75528': (-40, 125, 'junction TJ', 'TI TLV755P data sheet p.4', 'v'),
    'TMP1075': (-55, 125, 'operating', 'TI TMP1075 data sheet p.3/p.5', 'v'),
    'TP': (None, None, 'copper pad', '-', '-'),
    'TPD4E05U06': (-40, 125, 'ambient TA', 'TI TPD4E05U06 data sheet p.6', 'v'),
    'TPS2121': (-40, 125, 'junction TJ', 'TI SLVSEA3F p.6', 'v'),
    'TPS22916': (-40, 85, 'ambient TA', 'TI SLVSDO5F p.4', 'v'),
    'TPS22965': (-40, 105, 'ambient TA', 'TI TPS22965 data sheet p.5', 'v'),
    'TPS259470A': (-40, 125, 'junction TJ', 'TI TPS25947 data sheet p.8', 'v'),
    'TPS62840': (-40, 125, 'junction TJ', 'TI TPS62840 data sheet p.6', 'v'),
    'TPS63810': (-40, 125, 'junction TJ', 'TI SLVSEK4C p.4', 'v'),
    'TVS2200': (-40, 125, 'ambient TA', 'TI TVS2200 data sheet p.4', 'v'),
    'UFL': (-40, 90, 'operating', 'Hirose U.FL series (distributor listings; copy not read)', 'd'),
    'USBC': (-40, 85, 'operating (CONFLICTING: some listings -20 C)', 'Amphenol 12401610E4#2A (distributor listings disagree)', 'd'),
    'XTAL32K': (-40, 85, 'operating', 'Abracon ABS07 data sheet p.1', 'v'),
    'XTAL32M': (-40, 85, 'operating (D = -40..85 code)', 'Abracon ABM11W data sheet p.1-2', 'v'),
    'ZENER4V7': (None, 150, 'junction Tj (storage -55)', 'Rohm UDZV series', 'd'),
    'RF0.5pF': (-55, 125, 'C0G class', 'Murata GJM series', 'd'),
}
for _k in ('RF0.8pF', 'RF1.0pF', 'RF1.5pF', 'RF1.8pF', 'RF10pF', 'RF15pF', 'RF2.4pF', 'RF27pF', 'RF3.0pF', 'RF39pF',
           'RF47pF', 'RF5.6pF'):
    RATING[_k] = (-55, 125, 'C0G class', 'Murata GJM series', 'd')


def ntc_r(t, r25=10e3):
    b = 3380.0 if t < 50 else 3434.0      # Murata NCP15XH103F03RC B25/50 3380 K, B25/85 3434 K
    return r25 * math.exp(b * (1 / (t + 273.15) - 1 / 298.15))


def ntc_t(r):
    lo, hi = -60.0, 150.0
    for _ in range(80):
        m = (lo + hi) / 2
        if ntc_r(m) > r:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def study2_3():
    used = sorted(set(c.part for c in COMPS))
    out()
    out('=' * 100)
    out('STUDY 2: temperature-rating audit (E1: every part -40..+85 C or better)')
    out('=' * 100)
    out('  v = read from a copy of the maker data sheet in this session; d = series spec / distributor listing (copy not read)')
    out('  %-12s %-28s %-20s %-6s %-6s %-40s %s' % ('part', 'mpn', 'maker', 'low', 'high', 'rating', 'source'))
    fails = []
    for k in used:
        pd = parts.PARTS[k]
        lo, hi, what, srcs, vflag = RATING[k]
        refs = [c.ref for c in COMPS if c.part == k]
        ok = True
        if lo is not None and lo > -40:
            ok = False
        if hi is not None and hi < 85:
            ok = False
        flag = '' if ok else '  <-- does not cover -40..+85'
        if 'X5R' in what:
            flag = '  (85 C max, no margin: check hot spots)'
        if k == 'QPA9510':
            flag = '  (case limit 85 C, see study 1)'
        out('  %-12s %-28s %-20s %-6s %-6s %-40s %s [%s]%s' % (k, pd.get('mpn', '')[:28], (pd.get('maker') or '')[:20],
                                                               lo if lo is not None else '-', hi if hi is not None else '-',
                                                               what[:40], srcs, vflag, flag))
        if not ok:
            fails.append((k, refs, lo, hi))
    out()
    out('Parts that do not cover -40..+85 C:')
    for k, refs, lo, hi in fails:
        out('  %s (%s): %s..%s C' % (k, ' '.join(refs), lo, hi))
    out('  Owner decision 3 (docs/plan.md) accepts the buttons and JST connectors at -25 C; it does not mention their'
        ' upper limits: B3U +70 C is BELOW the 85 C of E1 and only 10 C above the 60 C box.')
    out('  Unverified: Amphenol USB-C lower limit (listings say -40 or -20 C); Coilcraft 0908SQ full current only to +80 C.')

    # NTC window
    out()
    out('--- Charger NTC (TS) window: BQ25185 TS/MR pin, NTC10K = Murata NCP15XH103F03RC straight to GND (circuit.py)')
    out('  TS bias ITSMR 36.5/38/39.5 uA (SLUSF65B p.8); VHOT 0.105/0.115/0.125 V (falling), VCOLD 0.9575/1.0075/1.0575 V'
        ' (rising); exits VHOT_EXIT 0.135, VCOLD_EXIT 0.820 V typ')
    win = {}
    for nm, v, lst in (('hot stop', 'VHOT', [(0.115, 38e-6), (0.105, 39.5e-6), (0.125, 36.5e-6)]),
                       ('cold stop', 'VCOLD', [(1.0075, 38e-6), (0.9575, 39.5e-6), (1.0575, 36.5e-6)])):
        ts = [ntc_t(vv / ii) for vv, ii in lst]
        win[nm] = (ts[0], min(ts), max(ts))
        out('  %-9s typ %.1f C (spread %.1f .. %.1f C, NTC 1 %% and B tolerance not included)' % (nm, ts[0], min(ts), max(ts)))
    out('  resume: hot below %.1f C, cold above %.1f C (typ)' % (ntc_t(0.135 / 38e-6), ntc_t(0.820 / 38e-6)))
    out('  TS/MR "button pressed" (90 mV): NTC above %.1f C' % ntc_t(0.090 / 38e-6))
    out('  => the hardware alone stops charging below %.1f C typ (%.1f .. %.1f C over the tolerances): at the 0 C LiPo rule,'
        ' MARGINAL (a worst-case part charges down to %.1f C).  It stops above %.1f C typ (%.1f .. %.1f C), NOT at 45 C:'
        ' the 45 C limit exists only in firmware (CE pin).'
        % (win['cold stop'] + (win['cold stop'][1],) + win['hot stop']))
    out('  => the NTC (TH1) is on the board 2.8 mm from the charger (U4), not on the cell: it reads charger heat (study 1 table).')
    out('  => CHG_TS goes nowhere but the charger and TH1: the processor cannot read the NTC.  Firmware has the TMP1075 at the'
        ' amplifier end and the nRF52840 die sensor; neither sees the cell.')
    out('  => no single resistor (series or parallel) moves the hot stop to 45 C and keeps the cold stop at 0 C with a'
        ' B3380 NTC: the window is a fixed ~0/60 C design (no JEITA in the BQ25185).')

    out()
    out('=' * 100)
    out('STUDY 3: cold start at -40 C')
    out('=' * 100)
    out('Outside their range at -40 C: B3U buttons (-25 C), JST PH/GH/SH (-25 C) [accepted, owner decision 3];'
        ' Amphenol USB-C if its true lower limit is -20 C (unverified).  Every IC, crystal and passive covers -40 C.')
    out('Clocks:')
    out('  ABM11W 32 MHz (-D1X: -40..85 C): ESR <= 50 Ohm over temperature, C0 <= 2 pF (ABM11W p.1) vs nRF52840'
        ' RS_HFXO_3PF <= 100 Ohm (PS p.96): PASS, 2x margin for start-up.')
    out('  ABS07 32.768 kHz: ESR <= 70 kOhm at -40..85 C (ABS07 p.1) vs nRF52840 RS_LFXO <= 100 kOhm (PS p.97): PASS.')
    df = [-0.036 * (t - 25) ** 2 for t in (-40, 85, 60)]
    out('  ABS07 frequency: -0.036 ppm/C^2 parabola -> %.0f ppm at -40 C, %.0f ppm at +85 C, %.0f ppm at 60 C (plus +-20 ppm'
        ' tolerance).  The Adafruit core declares the LFXO as NRF_CLOCK_LF_ACCURACY_20_PPM (bluefruit.cpp, USE_LFXO):'
        ' Bluetooth timing then assumes 20 ppm while the crystal is off by up to ~170 ppm -> dropped BLE connections'
        ' when cold or hot.  MARGINAL; fix in the board variant: declare 250 ppm (or 150 ppm).' % tuple(df))
    out('  TCXO ECS-TXO-20CSMV4-320-AP: -40..+105 C, +-0.5 ppm, start-up 2 ms (p.1): PASS (firmware TCXO delay >= 5 ms).')
    out('Converter loops (effective capacitance = nominal x tolerance x DC bias x cold; X5R loses up to 15 % at -40 C):')
    rows = [
        ('TPS63810 COUT (VPA)', '2 x 47u 0805 6.3 V X5R (19 uF each at 4.0 V) + 2 x 4.7u 0603 10 V (2.6 uF at 4 V)',
         2 * 19 * 0.8 * 0.85 + 2 * 2.6 * 0.9 * 0.85, 16.0, 'SLVSEK4C p.4 (13 min) / p.27 (16 recommended)'),
        ('TPS63810 CIN (PA_IN)', '2 x 22u 0805 16 V X5R (14 uF at 4.5 V) + 10u 0805 25 V (7 uF)',
         2 * 14 * 0.8 * 0.85 + 7 * 0.9 * 0.85, 5.0, 'SLVSEK4C p.4 / p.26'),
        ('TPS62840 COUT (3V3)', '2 x 10u 0603 10 V X5R (5.5 uF at 3.3 V) + 2 x 4.7u 0603 (3 uF) + 1u 0402s',
         2 * 5.5 * 0.9 * 0.85 + 2 * 3.0 * 0.9 * 0.85, 3.0, 'TPS62840 p.6 (3..40 uF effective)'),
        ('TPS62840 CIN (VSYS_SW)', '4.7u 0603 10 V (2.4 uF at 4.5 V) + 10u 0603 (5 uF)',
         2.4 * 0.9 * 0.85 + 5 * 0.9 * 0.85, 1.0, 'TPS62840 p.6 (1 uF min effective)'),
    ]
    for nm, what, eff, mn, srcs in rows:
        out('  %-22s %-80s worst %.1f uF vs min %.0f uF -> %s  [%s]' % (nm, what, eff, mn, 'PASS' if eff >= mn else 'FAIL', srcs))
    out('  TPS62840 COUT upper limit 40 uF: nominal at +25 C about 2 x 6 + 2 x 3 + 4 x 0.6 = 20 uF -> PASS.')
    out('  Both converters are internally compensated; with the effective capacitance inside the ranges above at -40 C the'
        ' loops stay in their datasheet-stable region: PASS.  (TPS63810 inductor DFE252012F-R47M: metal alloy, 0.47 uH'
        ' -20 %% = 0.38 uH, at the 390 nH minimum; inductance hardly moves with temperature: MARGINAL on tolerance, not cold.)')
    out('Battery: a LiPo cell at -40 C cannot deliver 2-3 A bursts (internal resistance rises 5-10x below -20 C); the'
        ' burst study\'s worn-cell case (0.3 Ohm) is the nearest proxy.  Firmware should cap power below -20 C.')
    out('Mechanical:')
    out('  U.FL (Hirose, -40..+90 C): fine thermally; it unmates under shock/vibration (drone drop): add a retention clip'
        ' or a dab of staking compound over the mated plug.')
    out('  0908SQ air-core choke (L14): tinned copper coil on copper pads, CTE close to the board (17 vs 14-17 ppm/C), the'
        ' spring coil is compliant, so thermal cycling is a small risk; shock is the bigger one (a 2-3 mm tall coil on two'
        ' joints).  Stake it with a dot of low-loss RF adhesive; do not let adhesive fill the coil (it shifts the inductance).')
    out('  WLCSP parts (TPS63810, TPS62840, TPS22916, SSM10N954L, CSD25485F5) and the nRF52840 aQFN: per-burst swings at'
        ' the TPS63810 are a few C (study 1) but 500 k cycles a year at one message a minute; with drop shock, underfill'
        ' (or corner bonding) of the WLCSPs is advisable for the field build.')


if __name__ == '__main__':
    main()
