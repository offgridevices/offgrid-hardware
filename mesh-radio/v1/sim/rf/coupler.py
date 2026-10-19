# -*- coding: utf-8 -*-
"""Missing-antenna detector: size the printed coupler on the 6-layer stack and predict REFL_DET.

Stack (src/pcb.py, JLC06161H-2116B): F.Cu (35 um, solder mask ~15 um, er 3.8) over 0.1164 mm of 2116
prepreg (er 4.16) to the solid In1 ground.  Cross-section (left to right):
    top ground pour | g_out | main ANT line 0.22 | s | coupled line w_c | g_out | top ground pour
The even/odd parameters come from a 2-D finite-difference Laplace solve of that cross-section (with
and without dielectric), checked against src/impedance.py's closed form for the plain 0.22 / 0.18 mm
line.  The coupler is then a 4-port (even/odd transmission lines) inside the actual terminations:
    main line: filter (50 ohm source) -> coupler -> U.FL (antenna, |Gamma| at every phase)
    coupled line: filter end -> 49.9 R to GND;  U.FL end -> BAT15-02EL -> REFL_DET (1 nF || 100 k)
The detector DC level is solved from the diode equation averaged over an RF cycle (peak detector
with a resistive load), at -40 / 25 / 85 C.

    tools/kd python3 sim/rf/coupler.py      # from mesh-radio/v1; writes coupler.txt, coupler.png
"""
import math
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize import brentq
from scipy.special import i0e
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src'))
import rflib as R   # noqa: E402

EPS0 = 8.854e-12
C0 = 299792458.0
H, ER, T_CU = 0.1164, 4.16, 0.035          # mm
MASK_T, MASK_ER = 0.015, 3.8               # mm over copper; gaps filled to copper top + MASK_T (ASSUMED)
W_DRAWN, G_DRAWN = 0.22, 0.18             # the line as drawn (impedance.py)
W_MAIN, G_OUT = 0.17, 0.25                 # 50 ohm with 35 um copper and mask (this solver; see coupler.txt)
DX = 0.0025
F0 = 915e6
OUT = []


def out(s=''):
    OUT.append(s)
    print(s)


# ----------------------------------------------------------------------------- 2-D field solve
def cross_section(strips, dx=DX, top=1.0, pour=0.6):
    """strips: list of (x0, x1) for the signal strips (mm).  Ground pours lie outside
    [min(x0) - G_OUT, max(x1) + G_OUT].  Returns the Maxwell capacitance matrices (F/m)
    with dielectrics and in air."""
    xl = min(a for a, b in strips) - G_OUT
    xr = max(b for a, b in strips) + G_OUT
    X0, X1 = xl - pour, xr + pour
    nx = int(round((X1 - X0) / dx))
    ny = int(round(top / dx))
    xs = X0 + dx * np.arange(nx + 1)
    ys = dx * np.arange(ny + 1)
    j_sub = int(round(H / dx))
    j_cu = int(round((H + T_CU) / dx))
    j_mask = int(round((H + T_CU + MASK_T) / dx))
    cond = np.full((nx + 1, ny + 1), -1, dtype=int)      # -1 free, 0 ground, k>0 strip k
    cond[:, 0] = 0
    cond[:, -1] = 0
    cond[0, :] = 0
    cond[-1, :] = 0
    for i, x in enumerate(xs):
        if x <= xl + 1e-9 or x >= xr - 1e-9:
            cond[i, j_sub:j_cu + 1] = 0
        for k, (a, b) in enumerate(strips, 1):
            if a - 1e-9 <= x <= b + 1e-9:
                cond[i, j_sub:j_cu + 1] = k

    def solve(eps_cell):
        idx = -np.ones((nx + 1, ny + 1), dtype=int)
        free = cond < 0
        idx[free] = np.arange(free.sum())
        n = free.sum()
        rows, cols, vals = [], [], []
        nstrip = len(strips)
        rhs = np.zeros((n, nstrip))
        # edge coefficients
        ex = np.zeros((nx, ny + 1))            # between (i,j)-(i+1,j)
        ex[:, 1:-1] = 0.5 * (eps_cell[:, :-1] + eps_cell[:, 1:])
        ex[:, 0] = eps_cell[:, 0]
        ex[:, -1] = eps_cell[:, -1]
        ey = np.zeros((nx + 1, ny))            # between (i,j)-(i,j+1)
        ey[1:-1, :] = 0.5 * (eps_cell[:-1, :] + eps_cell[1:, :])
        ey[0, :] = eps_cell[0, :]
        ey[-1, :] = eps_cell[-1, :]
        diag = np.zeros(n)
        ii, jj = np.nonzero(free)
        nbrs = [((ii + 1, jj), ex[np.minimum(ii, nx - 1), jj]), ((ii - 1, jj), ex[np.maximum(ii - 1, 0), jj]),
                ((ii, jj + 1), ey[ii, np.minimum(jj, ny - 1)]), ((ii, jj - 1), ey[ii, np.maximum(jj - 1, 0)])]
        me = idx[ii, jj]
        for (ni, nj), coef in nbrs:
            diag += coef
            other = cond[ni, nj]
            isfree = other < 0
            rows.append(me[isfree])
            cols.append(idx[ni[isfree], nj[isfree]])
            vals.append(-coef[isfree])
            for k in range(1, nstrip + 1):
                m = other == k
                rhs[me[m], k - 1] += coef[m]
        A = sp.csr_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [me]), np.concatenate(cols + [me]))),
                          shape=(n, n))
        lu = spla.splu(A.tocsc())
        Cm = np.zeros((nstrip, nstrip))
        for k in range(nstrip):
            phi = np.zeros((nx + 1, ny + 1))
            phi[cond == k + 1] = 1.0
            phi[free] = lu.solve(rhs[:, k])
            # charge on each strip = sum of flux out of its nodes into free/other nodes
            for q in range(nstrip):
                qi, qj = np.nonzero(cond == q + 1)
                tot = 0.0
                for (di, dj, e) in ((1, 0, ex), (-1, 0, ex), (0, 1, ey), (0, -1, ey)):
                    ni, nj = qi + di, qj + dj
                    ok = cond[ni, nj] != q + 1
                    ei = np.minimum(qi, ni)[ok] if di else qi[ok]
                    ej = np.minimum(qj, nj)[ok] if dj else qj[ok]
                    coef = e[ei, ej]
                    tot += np.sum(coef * (phi[qi[ok], qj[ok]] - phi[ni[ok], nj[ok]]))
                Cm[q, k] = EPS0 * tot
        return Cm

    eps = np.ones((nx, ny))
    yc = 0.5 * (ys[:-1] + ys[1:])
    eps[:, yc < H] = ER
    mask = (yc >= H) & (yc < (H + T_CU + MASK_T))
    eps[:, mask] = MASK_ER
    return solve(eps), solve(np.ones((nx, ny)))


def line_params(Cd, Ca):
    L = np.linalg.inv(Ca) / C0 ** 2
    return L, Cd


def single_line(w=W_MAIN, dx=DX):
    Cd, Ca = cross_section([(0, w)], dx=dx)
    eeff = Cd[0, 0] / Ca[0, 0]
    z = 1 / (C0 * math.sqrt(Cd[0, 0] * Ca[0, 0]))
    return z, eeff


def coupled(s, wc=None, dx=DX):
    wc = W_MAIN if wc is None else wc
    Cd, Ca = cross_section([(0, W_MAIN), (W_MAIN + s, W_MAIN + s + wc)], dx=dx)
    ce, co = Cd[0, 0] + Cd[0, 1], Cd[0, 0] - Cd[0, 1]
    ce0, co0 = Ca[0, 0] + Ca[0, 1], Ca[0, 0] - Ca[0, 1]
    ze = 1 / (C0 * math.sqrt(ce * ce0))
    zo = 1 / (C0 * math.sqrt(co * co0))
    return dict(ze=ze, zo=zo, ee=ce / ce0, eo=co / co0, k=(ze - zo) / (ze + zo), Cd=Cd, Ca=Ca)


# ----------------------------------------------------------------------------- coupler 4-port
def coupler_y(p, length_mm, f, loss_db_mm=0.005):
    """4x4 Y matrix (ports a1, a2, b1, b2) of a symmetric coupled pair from even/odd modes."""
    w = 2 * math.pi * f
    l = length_mm * 1e-3
    alpha = loss_db_mm * 1e3 / 8.686
    Ys = {}
    for m, z, e in (('e', p['ze'], p['ee']), ('o', p['zo'], p['eo'])):
        g = (alpha + 1j * w * math.sqrt(e) / C0) * l
        y11 = 1 / (z * np.tanh(g))
        y12 = -1 / (z * np.sinh(g))
        Ys[m] = np.array([[y11, y12], [y12, y11]])
    A = (Ys['e'] + Ys['o']) / 2
    Bm = (Ys['e'] - Ys['o']) / 2
    return np.block([[A, Bm], [Bm, A]])


def solve_ports(Y, src_v, z_src, loads):
    """Node voltages of the 4-port with a Thevenin source on a1 and admittance loads on a2, b1, b2."""
    Yt = Y.copy().astype(complex)
    Yt[0, 0] += 1 / z_src
    for k, y in loads.items():
        Yt[k, k] += y
    I = np.zeros(4, dtype=complex)
    I[0] = src_v / z_src
    return np.linalg.solve(Yt, I)


def sparams(Y, z0=50.0):
    Yt = Y + np.eye(4) / z0
    S = np.zeros((4, 4), dtype=complex)
    for k in range(4):
        I = np.zeros(4, dtype=complex)
        I[k] = 2 / z0
        V = np.linalg.solve(Yt, I)
        S[:, k] = V
    return S - np.eye(4)


# ----------------------------------------------------------------------------- detector
# BAT15-02EL: Infineon data sheet values used to set a diode equation (ASSUMED fit): VF ~0.32 V at 10 mA,
# ~0.23 V at 1 mA -> n 1.1, Is 1e-7 A at 25 C; Is ~ T^2 exp(-phi_b/(Vt)) with barrier 0.55 eV.
# Junction capacitance 0.26 pF; reverse voltage 4 V max.
DIODE = dict(n=1.1, is25=1e-7, phib=0.55, cj=0.26e-12, vr=4.0)
RL, CL = 100e3, 1e-9
DESIGNS = [(0.10, 5.5), (0.125, 5.5), (0.15, 5.5), (0.15, 8.0)]
CHOSEN = (0.125, 5.5)


def diode_is(tc):
    t = tc + 273.15
    t0 = 298.15
    vt = 8.617e-5 * t
    return DIODE['is25'] * (t / t0) ** 2 * math.exp(-DIODE['phib'] / vt + DIODE['phib'] / (8.617e-5 * t0))


def detector_vdc(vpk, tc):
    """DC at REFL_DET for an RF peak vpk (V) at the anode: mean diode current = V/RL."""
    t = tc + 273.15
    nvt = DIODE['n'] * 8.617e-5 * t
    isat = diode_is(tc)
    if vpk <= 0:
        return 0.0
    # mean of Is (exp((vpk sin - V)/nvt) - 1) over a cycle = Is (I0(vpk/nvt) exp(-V/nvt) - 1)
    f = lambda v: isat * (i0e(vpk / nvt) * math.exp(vpk / nvt - v / nvt) - 1) - v / RL
    return brentq(f, 0.0, vpk + 1.0)


def detector_zin(vpk, vdc):
    """Large-signal RF input resistance of a peak detector ~ RL/2 (plus Cj)."""
    return RL / 2


def main():
    global T_CU, MASK_T, G_OUT
    out('Mesh Radio v1 - missing-antenna detector coupler (sim/rf/coupler.py)')
    out('Stack: F.Cu %.3f mm + %.3f mm mask (er %.1f, ASSUMED) over %.4f mm 2116 (er %.2f) to In1; lines %.2f mm,'
        ' outer gap to the top pour %.2f mm.' % (T_CU, MASK_T, MASK_ER, H, ER, W_MAIN, G_OUT))
    from impedance import cpwg
    zc, ec = cpwg(W_DRAWN, G_DRAWN, H, ER)
    keep = (T_CU, MASK_T, G_OUT)
    T_CU, MASK_T, G_OUT = DX, 0.0, G_DRAWN
    zt, et = single_line(w=W_DRAWN)
    T_CU, MASK_T, G_OUT = keep
    out('Field-solver check: 0.22 mm line, 0.18 mm gaps, copper one grid cell thin and no mask: %.1f ohm (eeff %.2f);'
        % (zt, et))
    out('  impedance.py closed form for the same: %.1f ohm (eeff %.2f).  (The 2.5 um grid reads ~1 ohm low.)' % (zc, ec))
    out('The line with 35 um copper and mask (the real board):')
    for w, g in ((0.22, 0.18), (0.20, 0.18), (0.17, 0.25), (0.16, 0.18)):
        G_OUT = g
        z, e = single_line(w=w)
        out('   w %.2f mm, gap %.2f mm: %.1f ohm, eeff %.2f' % (w, g, z, e))
    G_OUT = keep[2]
    out('  -> the drawn 0.22 / 0.18 mm line is ~43-44 ohm, not 51.6 (copper side walls 0.18 mm from the pour, and the mask).')
    out('     0.17 / 0.25 mm is 50 ohm; the coupler below uses it for both lines.')
    out()
    out('Coupled pair, both lines %.2f mm, each with %.2f mm to the pour on its outer side:' % (W_MAIN, G_OUT))
    out('   gap s   Z0e    Z0o    eeff_e  eeff_o   k (dB)   Z0 = sqrt(Ze Zo)')
    pars = {}
    for s in (0.10, 0.125, 0.15, 0.20):
        p = coupled(s)
        pars[s] = p
        out('   %.3f  %5.1f  %5.1f   %.3f   %.3f   %6.1f   %5.1f' % (s, p['ze'], p['zo'], p['ee'], p['eo'],
                                                                    20 * math.log10(p['k']), math.sqrt(p['ze'] * p['zo'])))
    out()
    out('Coupler alone, 50 ohm on all ports, 915 MHz (coupling = reflected wave at the U.FL end -> diode end;')
    out('directivity = coupling minus the forward wave leaking to the same port):')
    out('   gap s  length   coupling  directivity')
    table = {}
    for s in (0.10, 0.125, 0.15, 0.20):
        for l in (5.0, 5.5, 6.0, 8.0, 10.0):
            S = sparams(coupler_y(pars[s], l, F0))
            # ports: 0 a1 (filter end, main), 1 a2 (U.FL end, main), 2 b1 (filter end, coupled), 3 b2 (U.FL end, coupled)
            cpl = -R.db20(S[3, 1])      # wave entering at the U.FL end (reflection) -> coupled U.FL end (diode)
            iso = -R.db20(S[3, 0])      # forward wave -> diode end
            table[(s, l)] = (cpl, iso - cpl)
            out('   %.2f   %4.1f mm   %6.1f dB    %5.1f dB' % (s, l, cpl, iso - cpl))
    # chosen design and detector levels
    out()
    out('Detector levels at REFL_DET (BAT15-02EL into 1 nF || 100 k; diode model ASSUMED, see DIODE), 902-928 MHz, the')
    out('antenna reflection at every phase.  Forward power = the conducted power at the U.FL; "missing" = |Gamma| 1 at the')
    out('U.FL; good antennas VSWR 1.5 (|Gamma| 0.2) and 2 (0.33).  Range = min..max over phase and band.')
    res = {}
    for s, l in DESIGNS:
        p = pars[s]
        out()
        cpl, d = (lambda S: (-R.db20(S[3, 1]), -R.db20(S[3, 0]) + R.db20(S[3, 1])))(sparams(coupler_y(p, l, F0)))
        out('  design: gap %.2f mm, length %.1f mm  (coupling %.1f dB, directivity %.1f dB at 915 MHz)' % (s, l, cpl, d))
        out('   P(U.FL)  antenna      -40 C          25 C          85 C        RF peak at anode   reverse peak')
        for pdbm in (30.0, 35.0, 36.0):
            for lab, gm in (('VSWR 1.5', 0.2), ('VSWR 2', 1 / 3), ('missing', 1.0)):
                vmin, vmax = 1e9, 0
                for f in (902e6, 915e6, 928e6):
                    Y = coupler_y(p, l, f)
                    for ph in np.linspace(0, 2 * np.pi, 72, endpoint=False):
                        g = gm * np.exp(1j * ph)
                        yl = (1 - g) / (50 * (1 + g)) if abs(1 + g) > 1e-9 else 1e9
                        zd = 1 / (1 / detector_zin(1, 1) + 1j * 2 * math.pi * f * DIODE['cj'])
                        # source: forward wave of pdbm (+ the loss of nothing: the coupler sits at the U.FL)
                        vs = 2 * math.sqrt(2 * 50 * R.dbm_to_w(pdbm))
                        V = solve_ports(Y, vs, 50.0, {1: yl, 2: 1 / 49.9, 3: 1 / zd})
                        # scale so the incident (forward) power at the U.FL is pdbm regardless of mismatch:
                        vpk = abs(V[3])
                        vmin, vmax = min(vmin, vpk), max(vmax, vpk)
                row = []
                for tc in (-40, 25, 85):
                    row.append((detector_vdc(vmin, tc), detector_vdc(vmax, tc)))
                res[(s, l, pdbm, lab)] = (vmin, vmax, row)
                out('   %4.0f dBm %-9s ' % (pdbm, lab) + '  '.join('%.2f-%.2f V' % r for r in row)
                    + '    %.2f-%.2f V      %.2f V' % (vmin, vmax, vmax + row[0][1]))
    out()
    out('Firmware threshold per power setting (it reads the reflected wave, so it scales with forward power).  Worst')
    out('case over -40..85 C, 902-928 MHz and every phase: the highest reading with a VSWR-2 antenna against the lowest')
    out('with the antenna missing.  "D 15 dB" repeats it with the directivity forced down to 15 dB (layout, U.FL).')
    thr = {}
    for s, l in DESIGNS:
        for pdbm in (30.0, 35.0):
            hi_good = max(r[1] for r in res[(s, l, pdbm, 'VSWR 2')][2])
            lo_miss = min(r[0] for r in res[(s, l, pdbm, 'missing')][2])
            # pessimistic directivity: extra forward leak at the diode, in phase with the worst case
            vmiss = 0.5 * (res[(s, l, pdbm, 'missing')][0] + res[(s, l, pdbm, 'missing')][1])
            leak = vmiss * 10 ** (-15 / 20)
            hi_p = max(detector_vdc(res[(s, l, pdbm, 'VSWR 2')][1] + leak, tc) for tc in (-40, 25, 85))
            lo_p = min(detector_vdc(max(res[(s, l, pdbm, 'missing')][0] - leak, 0), tc) for tc in (-40, 25, 85))
            t = math.sqrt(max(hi_good, 0.02) * lo_miss)
            thr[(s, l, pdbm)] = t
            out('   gap %.3f x %.1f mm, %2.0f dBm: VSWR-2 max %.2f V, missing min %.2f V -> threshold %.2f V (contrast %.1f dB);'
                ' D 15 dB: %.2f / %.2f V' % (s, l, pdbm, hi_good, lo_miss, t, 20 * math.log10(lo_miss / max(hi_good, 0.02)),
                                             hi_p, lo_p))
    out()
    out('Timing: 1 nF || 100 k decays with tau = 100 us; it charges through the diode (~1 k at these currents) in ~1 us.')
    out('The reading settles within ~0.3 ms of PA_EN; sample at 0.5-1 ms.  The nRF52840 SAADC (tacq 10-40 us) samples a')
    out('100 k source with < 1 LSB error at tacq 40 us (Nordic: 40 us allows up to 800 k).  100 k also keeps the detector')
    out('load ~50 k at RF, far above the ~50 ohm coupled line, so the coupled port stays terminated by the 49.9 R end.')
    with open(os.path.join(HERE, 'coupler.txt'), 'w') as fh:
        fh.write('\n'.join(OUT) + '\n')
    # plot: detector DC vs antenna |Gamma| for the chosen design at 25 C
    s, l = CHOSEN
    p = pars[s]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for pdbm, col in ((30.0, run_c(0)), (35.0, run_c(1))):
        gms = np.linspace(0.0, 1.0, 41)
        lo, hi = [], []
        for gm in gms:
            vv = []
            for f in (902e6, 915e6, 928e6):
                Y = coupler_y(p, l, f)
                for ph in np.linspace(0, 2 * np.pi, 36, endpoint=False):
                    g = gm * np.exp(1j * ph)
                    yl = (1 - g) / (50 * (1 + g)) if abs(1 + g) > 1e-9 else 1e9
                    zd = 1 / (1 / detector_zin(1, 1) + 1j * 2 * math.pi * f * DIODE['cj'])
                    vs = 2 * math.sqrt(2 * 50 * R.dbm_to_w(pdbm))
                    V = solve_ports(Y, vs, 50.0, {1: yl, 2: 1 / 49.9, 3: 1 / zd})
                    vv.append(detector_vdc(abs(V[3]), 25))
            lo.append(min(vv))
            hi.append(max(vv))
        ax.fill_between(gms, lo, hi, color=col, alpha=0.3, lw=0)
        ax.plot(gms, lo, color=col, lw=1.5, label='%.0f dBm at the U.FL (band: every phase, 902-928 MHz)' % pdbm)
        ax.plot(gms, hi, color=col, lw=1.5)
    ax.set_xlabel('antenna |Gamma| (0.2 = VSWR 1.5, 0.33 = VSWR 2, 1 = missing)')
    ax.set_ylabel('REFL_DET, V (25 C)')
    ax.set_title('Missing-antenna detector, coupler %.3f mm gap x %.1f mm' % (s, l), fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'coupler.png'), dpi=110)
    plt.close(fig)


def run_c(i):
    return ['#2a78d6', '#eb6834'][i]


if __name__ == '__main__':
    main()
