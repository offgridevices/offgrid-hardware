# -*- coding: utf-8 -*-
"""Small RF circuit engine for the Mesh Radio v1 RF studies (numpy only).

A circuit is a list of elements between named nodes ('GND' is ground).
`Circuit.solve()` builds the nodal admittance matrix at every frequency
(and every Monte Carlo sample at once: element values may be arrays of
shape (S,) and the result has shape (S, F, ...)), then returns either
S-parameters between ports or the node voltages for given injected
currents.  Nodal analysis rather than ABCD cascades because the studies
need voltages on internal nodes (open-antenna stress) and because the
filters are not plain ladders.

Part models (where every number comes from) are in `PARTS_DB` below and
are documented in README.md.
"""
import math
import re

import numpy as np

Z0 = 50.0
C0_LIGHT = 299792458.0


# ----------------------------------------------------------------------------- helpers
def db10(x):
    return 10 * np.log10(np.maximum(np.abs(x), 1e-30))


def db20(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-30))


def rl_db(gamma):
    return -db20(gamma)


def vswr(gamma):
    g = np.minimum(np.abs(gamma), 0.999999)
    return (1 + g) / (1 - g)


def zin_to_gamma(z, z0=Z0):
    return (z - z0) / (z + z0)


def gamma_to_z(g, z0=Z0):
    return z0 * (1 + g) / (1 - g)


def dbm_to_w(p):
    return 1e-3 * 10 ** (np.asarray(p) / 10.0)


def w_to_dbm(p):
    return 10 * np.log10(np.maximum(p, 1e-30) / 1e-3)


# ----------------------------------------------------------------------------- elements
# Every element returns its admittance (two-terminal) or Y matrix (two-port)
# as a function of the angular frequency array w (shape (F,)) and broadcasts
# against sample arrays of shape (S, 1).

def _as(x):
    """Sample value -> array of shape (S, 1) so it broadcasts with (F,)."""
    a = np.asarray(x, dtype=float)
    if a.ndim == 0:
        return a.reshape(1, 1)
    return a.reshape(-1, 1)


class Cap:
    """C in series with ESL and a frequency-dependent ESR (ESR(f) = esr1g*sqrt(f/1 GHz))."""
    def __init__(self, c, esr1g=0.1, esl=0.3e-9, lmount=0.0):
        self.c, self.esr1g, self.esl, self.lmount = c, esr1g, esl, lmount

    def z(self, w):
        f = w / (2 * np.pi)
        c, esr, esl = _as(self.c), _as(self.esr1g), _as(self.esl) + _as(self.lmount)
        return esr * np.sqrt(f / 1e9) + 1j * w * esl + 1.0 / (1j * w * c)

    def y(self, w):
        return 1.0 / self.z(w)


class Ind:
    """L with series R(f) = max(Rdc, w_q L / Q_q * sqrt(f / f_q)) and a parallel
    self-capacitance Cp = 1 / ((2 pi SRF)^2 L).  Q_q is the maker's minimum Q at
    its test frequency f_q, so the loss is pessimistic; SRF is the minimum, so Cp
    is the largest the maker allows."""
    def __init__(self, l, q=50.0, fq=250e6, srf=10e9, rdc=0.05, lmount=0.0, rscale=1.0):
        self.l, self.q, self.fq, self.srf, self.rdc, self.lmount, self.rscale = l, q, fq, srf, rdc, lmount, rscale

    def r(self, w):
        f = w / (2 * np.pi)
        l = _as(self.l)
        rq = 2 * np.pi * self.fq * l / self.q * np.sqrt(f / self.fq)
        return np.maximum(rq, self.rdc) * _as(self.rscale)

    def y(self, w):
        l = _as(self.l)
        cp = 1.0 / ((2 * np.pi * self.srf) ** 2 * l) if self.srf else 0.0
        zl = self.r(w) + 1j * w * (l + _as(self.lmount))
        return 1.0 / zl + 1j * w * cp


class Res:
    """Thick-film chip resistor: R with series L and parallel C."""
    def __init__(self, r, ls=0.5e-9, cp=0.05e-12):
        self.r, self.ls, self.cp = r, ls, cp

    def y(self, w):
        return 1.0 / (_as(self.r) + 1j * w * _as(self.ls)) + 1j * w * _as(self.cp)


class Admittance:
    """Arbitrary two-terminal admittance given as a function of w."""
    def __init__(self, fn):
        self.fn = fn

    def y(self, w):
        return self.fn(w)


class Line:
    """Lossy 50-ohm microstrip, as a two-port Y matrix.  alpha in dB/mm:
    conductor 0.002 dB/mm x sqrt(f/1 GHz) + dielectric 0.003 dB/mm x f/1 GHz
    (FR-4, tan d 0.02, eps_eff 3.3; README)."""
    def __init__(self, length_mm, z0=Z0, eps_eff=3.3, ac=0.002, ad=0.003):
        self.len, self.z0, self.ee, self.ac, self.ad = length_mm, z0, eps_eff, ac, ad

    def ymat(self, w):
        f = w / (2 * np.pi)
        L = _as(self.len) * 1e-3
        a_db_mm = self.ac * np.sqrt(f / 1e9) + self.ad * (f / 1e9)
        alpha = a_db_mm * 1e3 / 8.686                     # Np/m
        beta = w * math.sqrt(self.ee) / C0_LIGHT
        gl = (alpha + 1j * beta) * L
        gl = np.where(np.abs(gl) < 1e-9, 1e-9 + 0j, gl)
        y11 = 1.0 / (self.z0 * np.tanh(gl))
        y12 = -1.0 / (self.z0 * np.sinh(gl))
        return y11, y12, y12, y11


class CoupledLine:
    """Symmetric edge-coupled microstrip pair as a 4-port Y matrix, nodes (a1, a2, b1, b2):
    a1-a2 is one line, b1-b2 the other, a1 and b1 at the same end.  Even/odd-mode
    impedances and effective permittivities from a field solve (coupler.py); loss as
    Line (FR-4 class, both modes)."""
    def __init__(self, ze, zo, ee, eo, length_mm, ac=0.002, ad=0.003):
        self.ze, self.zo, self.ee, self.eo, self.len, self.ac, self.ad = ze, zo, ee, eo, length_mm, ac, ad

    def ymat(self, w):
        f = w / (2 * np.pi)
        L = self.len * 1e-3
        alpha = (self.ac * np.sqrt(f / 1e9) + self.ad * (f / 1e9)) * 1e3 / 8.686
        Y = np.zeros(w.shape + (4, 4), dtype=complex)
        A = np.zeros(w.shape + (2, 2), dtype=complex)
        Bm = np.zeros(w.shape + (2, 2), dtype=complex)
        for z, e, sg in ((self.ze, self.ee, 1), (self.zo, self.eo, -1)):
            gl = (alpha + 1j * w * math.sqrt(e) / C0_LIGHT) * L
            y11 = 1.0 / (z * np.tanh(gl))
            y12 = -1.0 / (z * np.sinh(gl))
            m = np.stack([np.stack([y11, y12], -1), np.stack([y12, y11], -1)], -2)
            A += m / 2
            Bm += sg * m / 2
        Y[..., :2, :2] = A
        Y[..., :2, 2:] = Bm
        Y[..., 2:, :2] = Bm
        Y[..., 2:, 2:] = A
        return Y


class TwoPortS:
    """Two-port from S-parameters (functions of w), referenced to Z0."""
    def __init__(self, sfn, z0=Z0):
        self.sfn, self.z0 = sfn, z0

    def ymat(self, w):
        s11, s12, s21, s22 = self.sfn(w)
        # Y = (1/Z0) (I - S)(I + S)^-1  for a 2x2, written out
        d = (1 + s11) * (1 + s22) - s12 * s21
        y11 = ((1 - s11) * (1 + s22) + s12 * s21) / d
        y12 = -2 * s12 / d
        y21 = -2 * s21 / d
        y22 = ((1 + s11) * (1 - s22) + s12 * s21) / d
        return y11 / self.z0, y12 / self.z0, y21 / self.z0, y22 / self.z0


# ----------------------------------------------------------------------------- circuit
class Circuit:
    def __init__(self, name=''):
        self.name = name
        self.nodes = []
        self.elems = []         # (kind, a, b, element, label)

    def _n(self, n):
        if n == 'GND':
            return -1
        if n not in self.nodes:
            self.nodes.append(n)
        return self.nodes.index(n)

    def add(self, a, b, elem, label=''):
        self._n(a), self._n(b)
        self.elems.append(('2t', a, b, elem, label))
        return elem

    def add2(self, a, b, elem, label=''):
        """Two-port between nodes a (port 1) and b (port 2), both referenced to ground."""
        self._n(a), self._n(b)
        self.elems.append(('2p', a, b, elem, label))
        return elem

    def addn(self, nodes, elem, label=''):
        """N-port between `nodes` (all referenced to ground); elem.ymat(w) -> (F, N, N)."""
        for n in nodes:
            self._n(n)
        self.elems.append(('np', tuple(nodes), None, elem, label))
        return elem

    def copy(self):
        c = Circuit(self.name)
        c.nodes = list(self.nodes)
        c.elems = list(self.elems)
        return c

    def ymatrix(self, w, nsamp=1, extra=None):
        N, F = len(self.nodes), len(w)
        Y = np.zeros((nsamp, F, N, N), dtype=complex)
        idx = {n: i for i, n in enumerate(self.nodes)}
        idx['GND'] = -1
        for kind, a, b, el, _ in self.elems + (extra or []):
            if kind == 'np':
                ii = [idx[n] for n in a]
                ym = el.ymat(w)
                for r, i in enumerate(ii):
                    for q, j in enumerate(ii):
                        if i >= 0 and j >= 0:
                            Y[:, :, i, j] += ym[..., r, q]
                continue
            ia, ib = idx[a], idx[b]
            if kind == '2t':
                y = np.broadcast_to(el.y(w), (nsamp, F))
                if ia >= 0:
                    Y[:, :, ia, ia] += y
                if ib >= 0:
                    Y[:, :, ib, ib] += y
                if ia >= 0 and ib >= 0:
                    Y[:, :, ia, ib] -= y
                    Y[:, :, ib, ia] -= y
            else:
                y11, y12, y21, y22 = [np.broadcast_to(v, (nsamp, F)) for v in el.ymat(w)]
                Y[:, :, ia, ia] += y11
                Y[:, :, ia, ib] += y12
                Y[:, :, ib, ia] += y21
                Y[:, :, ib, ib] += y22
        return Y

    def sparams(self, f, ports, nsamp=1, z0=Z0, probe=None):
        """S-matrix (S, F, P, P) between `ports` (node names), all referenced to z0.
        With probe=[nodes], also returns the node voltages for a unit incident wave
        (sqrt(z0)-normalised: V_port = a + b) at each port: (S, F, P, len(probe))."""
        w = 2 * np.pi * np.asarray(f, dtype=float)
        Y = self.ymatrix(w, nsamp)
        pi = [self.nodes.index(p) for p in ports]
        for i in pi:
            Y[:, :, i, i] += 1.0 / z0
        P, N = len(ports), len(self.nodes)
        I = np.zeros((nsamp, len(w), N, P), dtype=complex)
        for k, i in enumerate(pi):
            I[:, :, i, k] = 2.0 / z0          # 2 V source behind z0 = incident wave of 1 V
        V = np.linalg.solve(Y, I)              # (S, F, N, P)
        S = np.empty((nsamp, len(w), P, P), dtype=complex)
        for j, i in enumerate(pi):
            S[:, :, j, :] = V[:, :, i, :]
        S -= np.eye(P)
        if probe:
            pv = np.stack([V[:, :, self.nodes.index(n), :] for n in probe], axis=-1)
            return S, pv
        return S

    def voltages(self, f, inject, loads=None, nsamp=1):
        """Node voltages for injected currents {node: I (array over (S,F) or scalar)}
        and extra shunt admittances {node: Y(w)}."""
        w = 2 * np.pi * np.asarray(f, dtype=float)
        extra = []
        for n, yfn in (loads or {}).items():
            extra.append(('2t', n, 'GND', Admittance(yfn), 'load'))
        Y = self.ymatrix(w, nsamp, extra)
        N = len(self.nodes)
        I = np.zeros((nsamp, len(w), N, 1), dtype=complex)
        for n, cur in inject.items():
            I[:, :, self.nodes.index(n), 0] = cur
        V = np.linalg.solve(Y, I)[..., 0]
        return {n: V[:, :, i] for i, n in enumerate(self.nodes)}


def mismatch_eff(s11, s21):
    """Fraction of the power entering port 1 that reaches a matched port 2."""
    return np.abs(s21) ** 2 / np.maximum(1 - np.abs(s11) ** 2, 1e-12)


def avail_gain(s, gs=0.0):
    """Available power gain port 1 -> 2 of a two-port with source reflection gs."""
    s11, s12, s21, s22 = s[..., 0, 0], s[..., 0, 1], s[..., 1, 0], s[..., 1, 1]
    gout = s22 + s12 * s21 * gs / (1 - s11 * gs)
    return np.abs(s21) ** 2 * (1 - np.abs(gs) ** 2) / (np.abs(1 - s11 * gs) ** 2 * (1 - np.abs(gout) ** 2))


# ----------------------------------------------------------------------------- part data
# Package parasitics (assumed typical values; README "Models"): series inductance
# of the chip itself, and the via + pad inductance added to every shunt part.
ESL = {'0402': 0.30e-9, '0603': 0.40e-9, '0805': 0.50e-9}
L_VIA = 0.15e-9

# Murata GJM high-Q C0G, maximum ESR (Murata GJM catalogue C-29-C, spec table "ESR"):
#   0.1-1 pF: 350 mOhm*pF / C;  1-5 pF: 300 mOhm;  5-10 pF: 250 mOhm  (at 1 GHz);
#   10-33 pF: 400 mOhm at 500 MHz (-> x sqrt(2) at 1 GHz).
# The GQM (250 V) parts use the same copper-electrode C0G and are given the same limits
# (assumption: Murata publishes the GQM ESR only as typical curves).
def gjm_esr_1g(c_pf):
    if c_pf <= 1.0:
        return 0.35 / c_pf
    if c_pf <= 5.0:
        return 0.30
    if c_pf <= 10.0:
        return 0.25
    return 0.40 * math.sqrt(2)


CAP_TOL = {'W': ('abs', 0.05e-12), 'B': ('abs', 0.10e-12), 'C': ('abs', 0.25e-12), 'D': ('abs', 0.5e-12),
           'F': ('rel', 0.01), 'G': ('rel', 0.02), 'J': ('rel', 0.05), 'K': ('rel', 0.10), 'M': ('rel', 0.20)}
IND_TOL = {'B': ('abs', 0.1e-9), 'C': ('abs', 0.2e-9), 'S': ('abs', 0.3e-9), 'D': ('abs', 0.5e-9),
           'G': ('rel', 0.02), 'J': ('rel', 0.05)}

# Murata reference specifications (Q is the minimum at the test frequency; SRF minimum):
#   LQW15AN_00: JELF243A-0050AC-01 (Q at 250 MHz, 200 MHz for 47 nH);
#   LQW18AN_00: Murata data sheet "LQW18AN_00 Series" (Q at 250 MHz);
#   LQG15HS: Murata catalogue (Q 8 min at 100 MHz) - not verified this session;
#   Coilcraft 0908SQ-8N1: Coilcraft site was unreachable; typical air-core values ASSUMED.
IND_DB = {
    #  mpn                q    fq      srf     rdc     Irated  note
    'LQW15AN1N5C00D': (10, 250e6, 18.0e9, 0.03, 1.000),
    'LQW15AN2N5C00D': (20, 250e6, 15.0e9, 0.05, 0.850),
    'LQW15AN2N7C00D': (20, 250e6, 15.0e9, 0.05, 0.850),
    'LQW15AN3N9C00D': (25, 250e6, 10.0e9, 0.07, 0.750),
    'LQW15AN4N7C00D': (25, 250e6, 8.0e9, 0.07, 0.750),
    'LQW15AN5N1C00D': (25, 250e6, 8.0e9, 0.12, 0.600),
    'LQW15AN11NJ00D': (30, 250e6, 5.5e9, 0.14, 0.500),
    'LQW15AN15NJ00D': (30, 250e6, 5.0e9, 0.16, 0.460),
    'LQW15AN47NJ00D': (25, 200e6, 2.9e9, 1.08, 0.210),
    'LQW18AN3N6D00D': (25, 250e6, 6.0e9, 0.059, 0.850),
    'LQW18AN4N7D00D': (35, 250e6, 6.0e9, 0.059, 0.850),
    'LQW18AN5N6C00D': (35, 250e6, 6.0e9, 0.082, 0.750),
    'LQW18AN11NG00D': (35, 250e6, 6.0e9, 0.11, 0.650),
    'LQG15HS1N6S02D': (8, 100e6, 6.0e9, 0.10, 0.300),
    '0908SQ-8N1':     (100, 900e6, 5.0e9, 0.004, 4.0),
    # Murata LQW2BAN 0805 (proposed fixes; DigiKey listing Oct 2026: Q min @ f, SRF, Rdc max, rated current)
    'LQW2BAN3N2J00L': (95, 1.5e9, 13.8e9, 0.020, 3.8),
    'LQW2BAN3N6J00L': (75, 1.5e9, 11.8e9, 0.050, 2.0),
    'LQW2BAN6N8J00L': (90, 1.0e9, 6.2e9, 0.030, 3.0),
    'LQW2BAN47NJ00L': (70, 500e6, 1.5e9, 0.200, 1.25),
}
# Temperature coefficients (README): C0G 0 +-30 ppm/C (Murata); wire-wound ceramic-core
# inductors +25..+125 ppm/C (Coilcraft's published range for ceramic wire-wound chips,
# used for the Murata LQW because Murata does not publish one); thick-film resistors
# +-100 ppm/C (Yageo RC series, R > 10 ohm).
TC_C0G = (-30e-6, 30e-6)
TC_IND = (25e-6, 125e-6)
TC_RES = (-100e-6, 100e-6)


def parse_value(s):
    m = re.match(r'([0-9.]+)\s*(pF|nF|uF|nH|uH|R|k|M)?', s)
    v = float(m.group(1))
    mult = {'pF': 1e-12, 'nF': 1e-9, 'uF': 1e-6, 'nH': 1e-9, 'uH': 1e-6, 'R': 1.0, 'k': 1e3, 'M': 1e6, None: 1.0}
    return v * mult[m.group(2)]


def part_info(part):
    """Turn a parts.py entry into (kind, nominal value, tolerance tuple, size, mpn, model dict)."""
    mpn, kind = part['mpn'], part['kind']
    desc = part.get('desc', '')
    size = next((s for s in ('0402', '0603', '0805', '1206') if s in desc), '0402')
    if '0908SQ' in mpn:
        size = '0908'
    val = parse_value(part['value'])
    info = dict(mpn=mpn, kind=kind, size=size, value=val)
    if kind == 'C':
        if mpn.startswith(('GJM', 'GQM', 'GRM')):
            tol = CAP_TOL[mpn[13]]
        else:   # Samsung CL05C120JB5NNNC style: tolerance letter after the value code
            tol = CAP_TOL[mpn[8]]
        info['tol'] = tol
        info['esr1g'] = gjm_esr_1g(val * 1e12) if mpn.startswith(('GJM', 'GQM')) else 0.15
        info['esl'] = ESL.get(size, 0.4e-9)
        info['tc'] = TC_C0G
    elif kind == 'L':
        if mpn in IND_DB:
            q, fq, srf, rdc, irat = IND_DB[mpn]
        else:
            raise KeyError('no RF model for inductor %s' % mpn)
        info.update(q=q, fq=fq, srf=srf, rdc=rdc, irated=irat, tc=TC_IND)
        if mpn.startswith('LQ'):
            info['tol'] = IND_TOL[mpn[10]]
        else:
            info['tol'] = ('rel', 0.05)      # Coilcraft 0908SQ: +-5 % assumed (J)
    elif kind == 'R':
        info['value'] = parse_value(part['value'])
        info['tol'] = ('rel', 0.01)
        info['tc'] = TC_RES
    return info


def draw(info, rng, n, temp_c, mode='mc'):
    """Sample values for one part: production tolerance (uniform, worst-case-ish) and a
    per-part temperature coefficient drawn from the maker's range, applied at temp_c.
    mode='nom' returns the nominal value at 25 C (TC still applied at its mid value)."""
    v0 = info['value']
    if mode == 'nom':
        tcm = 0.5 * (info['tc'][0] + info['tc'][1]) if 'tc' in info else 0.0
        return np.full(n, v0 * (1 + tcm * (temp_c - 25.0)))
    kind, t = info['tol']
    u = rng.uniform(-1, 1, n)
    v = v0 + u * t if kind == 'abs' else v0 * (1 + u * t)
    if 'tc' in info:
        tc = rng.uniform(info['tc'][0], info['tc'][1], n)
        v = v * (1 + tc * (temp_c - 25.0))
    return v


def element(info, value, shunt=False):
    """RF model element for one part at a given (sampled) value."""
    k = info['kind']
    lm = L_VIA if shunt else 0.0
    if k == 'C':
        return Cap(value, info['esr1g'], info['esl'], lm)
    if k == 'L':
        return Ind(value, info['q'], info['fq'], info['srf'], info['rdc'], lm)
    if k == 'R':
        ls = {'0402': 0.4e-9, '0603': 0.5e-9, '0805': 0.7e-9}.get(info['size'], 0.5e-9)
        return Res(value, ls + lm, 0.05e-12)
    raise ValueError(k)
