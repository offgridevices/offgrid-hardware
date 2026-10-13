# -*- coding: utf-8 -*-
"""Validation of thermal.py.

    tools/kd python3 sim/thermal/validate.py            (all checks, ~10 s)

1. Spreading in a copper plate: a 40 mm disc of 1 oz copper, heated over a
   3 mm disc at its centre, h on both faces; against the exact Bessel-function
   solution of the circular fin.
2. Through-thickness: 1.6 mm FR-4 between two full copper layers, uniform
   flux in at the top, h only at the bottom; against q t / k.
3. Transient: the same plate heated uniformly; against the lumped
   exponential 1 - exp(-t / tau) (the plate is isothermal, so this is exact
   for the network; it checks the capacities and the integrator).
4. Toshiba's own test: the TPN2R304PL datasheet gives Rth(ch-a) = 56 C/W on
   board (a) (Note 3, Fig. 5.1: FR-4 25.4 x 25.4 x 1.6 mm, 2 oz copper,
   nearly all of one face copper) and 235 C/W on board (b) (Note 4, Fig. 5.2:
   the same board with only the footprint and thin traces).  Both boards are
   drawn here with pcbnew, around the og:TSON-8 footprint the AIO uses, saved
   as .kicad_pcb, and run through the normal KiCad reader: the junction
   temperature rise at Toshiba's rated PD (2.67 W and 0.63 W, Ta = 25 C,
   still air) divided by PD is compared with 56 and 235 C/W.
"""
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thermal as th                       # noqa: E402
import cases                               # noqa: E402

OUT = os.path.join(th.REPO, 'out', 'thermal', 'validation')
FP_LIB = os.path.join(HERE, '..', '..', 'og.pretty')
FP_NAME = 'TSON-8_L3.1-W3.1-P0.65-LS3.3-BL-EP'


def circle(cx, cy, r, n=180):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


def synthetic(name, outline, layers, t_cu, t_diel, heat_poly, cell=0.2):
    """A Geom without KiCad: one outline, full copper on the given layers,
    one 'footprint' H1 whose single pad is heat_poly on layer 0."""
    P = th.Params
    P.cell_mm, P.ss = cell, 8
    pts = np.asarray(outline)
    x0, y0 = pts[:, 0].min() - cell, pts[:, 1].min() - cell
    nx = int(math.ceil((pts[:, 0].max() - pts[:, 0].min()) / cell)) + 2
    ny = int(math.ceil((pts[:, 1].max() - pts[:, 1].min()) / cell)) + 2
    g = th.Geom(name, x0, y0, nx, ny, cell, P.ss)
    g.board_polys = [pts]
    g.cu_names = ['L%d' % k for k in range(len(t_cu))]
    g.t_cu, g.t_diel = np.array(t_cu), np.array(t_diel)
    for k in layers:
        g.items.append((k, '', [pts]))
    cells, area = g.raster_local(heat_poly)
    g.fps = [dict(ref='H1', value='', fpid='', side=0, x=0, y=0, w=0, h=0, bx=0, by=0, height=0,
                  pads=[dict(num='1', net='', layers=[0], cells={0: (cells, area)}, area=area.sum(), x=0, y=0)])]
    return g


def drive(Ta=25.0, h=(10.0, 10.0), P=1.0, solar=0.0):
    return th.Drive(dict(Ta=Ta, v_top=0, v_bot=0, v_wire=0, turb=1, solar=solar, power={'H1': P},
                         wire_current={}, wire_far={}, joule=[], label='', h_fixed=h))


def check_spreading():
    from scipy.special import i0, i1, k0, k1
    R, a, P, h, t = 20.0, 1.5, 1.0, 10.0, 35e-6
    g = synthetic('disc', circle(0, 0, R), [0], [t], [], circle(0, 0, a, 64))
    topo = dict(elements=[dict(name='H1', ref='H1', pads=None, kind='src')], wires=[])
    m = th.Model(g, topo)
    T, _ = th.Solver(m).steady(drive(h=(h, h), P=P), verbose=False)
    kt = th.Params.k_cu * t
    mm_ = math.sqrt(2 * h / kt)
    Ra, Rr = a * 1e-3, R * 1e-3
    qs = P / (math.pi * Ra ** 2)
    beta = k1(mm_ * Rr) / i1(mm_ * Rr)
    # unknowns C (inside), A (outside)
    M = np.array([[i0(mm_ * Ra), -(k0(mm_ * Ra) + beta * i0(mm_ * Ra))],
                  [i1(mm_ * Ra), -(-k1(mm_ * Ra) + beta * i1(mm_ * Ra))]])
    C, A = np.linalg.solve(M, [-qs / (2 * h), 0.0])

    def exact(r):
        r = r * 1e-3
        return qs / (2 * h) + C * i0(mm_ * r) if r < Ra else A * (k0(mm_ * r) + beta * i0(mm_ * r))
    f = m.layer_field(T, 0) - 25.0
    xs = g.x0 + (np.arange(g.nx) + 0.5) * g.d
    ys = g.y0 + (np.arange(g.ny) + 0.5) * g.d
    out = []
    for r in (0.0, 3.0, 6.0, 10.0, 18.0):
        i = int(np.argmin(np.abs(xs - r))); j = int(np.argmin(np.abs(ys - 0.0)))
        out.append((r, f[j, i], exact(xs[i] if r > 0 else 0.0)))
    print('\n1. spreading, 1 oz copper disc R = 20 mm, 1 W over r < 1.5 mm, h = 10 W/m2K each face')
    print('   r mm   model K   exact K   error')
    for r, a_, e in out:
        print('   %4.1f  %8.3f  %8.3f   %+5.1f %%' % (r, a_, e, 100 * (a_ - e) / e))
    return out


def check_through():
    P, h, td = 1.0, 100.0, 1.53e-3
    sq = np.array([(0, 0), (20, 0), (20, 20), (0, 20)], float)
    g = synthetic('slab', sq, [0, 1], [35e-6, 35e-6], [td], sq)
    topo = dict(elements=[dict(name='H1', ref='H1', pads=None, kind='src')], wires=[])
    m = th.Model(g, topo)
    T, _ = th.Solver(m).steady(drive(h=(0.0, h), P=P), verbose=False)
    A = m.area
    q = P / A
    dT_model = float(np.mean(T[0:m.nb:2] - T[1:m.nb:2]))
    k = th.Params
    dT_exact = q * (td / k.k_fr4_z + 2 * (35e-6 / 2) / k.k_cu)
    Tb_exact = q / h
    print('\n2. through-thickness, 20 x 20 mm, 1.53 mm FR-4, 1 W uniform, h = 100 W/m2K under the bottom only')
    print('   top-bottom difference: model %.3f K, exact %.3f K (%+.2f %%); bottom rise model %.3f K, exact %.3f K' % (
        dT_model, dT_exact, 100 * (dT_model - dT_exact) / dT_exact, float(np.mean(T[1:m.nb:2]) - 25), Tb_exact))
    return dT_model, dT_exact


def check_transient():
    P, h = 1.0, 10.0
    sq = np.array([(0, 0), (20, 0), (20, 20), (0, 20)], float)
    g = synthetic('plate', sq, [0], [35e-6], [], sq)
    topo = dict(elements=[dict(name='H1', ref='H1', pads=None, kind='src')], wires=[])
    m = th.Model(g, topo)
    s = th.Solver(m)
    dv = drive(h=(h, h), P=P)
    T0 = np.full(m.N, 25.0)
    tau = m.C[:m.nb].sum() / (2 * h * m.area)
    rec = lambda T: [float(T[:m.nb].mean())]
    _, hist = s.transient([(3 * tau, dv)], T0, dt=0.05, record=rec)
    Tinf = P / (2 * h * m.area)
    rc = th.Params.rc_cu * 35e-6
    print('\n3. transient, 20 x 20 mm 1 oz plate, 1 W, h = 10 each face: tau = %.2f s (hand: rho c t / 2h = %.2f s)' % (
        tau, rc / (2 * h)))
    errs = []
    for frac in (0.5, 1.0, 2.0, 3.0):
        k = int(round(frac * tau / 0.05)) - 1
        t, v = hist[k][0], hist[k][1][0] - 25
        e = Tinf * (1 - math.exp(-t / tau))
        errs.append((t, v, e))
        print('   t = %5.2f s: model %.3f K, exact %.3f K (%+.2f %%)' % (t, v, e, 100 * (v - e) / e))
    return errs


# ---------------------------------------------------------------------------
#  Toshiba test boards, drawn with pcbnew
# ---------------------------------------------------------------------------
def make_tosh_board(path, variant):
    import pcbnew
    mm = pcbnew.FromMM
    V = lambda x, y: pcbnew.VECTOR2I(mm(x), mm(y))
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(2)
    b.GetDesignSettings().SetBoardThickness(mm(1.6))
    S = 25.4
    for (x1, y1), (x2, y2) in (((0, 0), (S, 0)), ((S, 0), (S, S)), ((S, S), (0, S)), ((0, S), (0, 0))):
        e = pcbnew.PCB_SHAPE(b)
        e.SetShape(pcbnew.SHAPE_T_SEGMENT)
        e.SetStart(V(x1, y1)); e.SetEnd(V(x2, y2))
        e.SetLayer(pcbnew.Edge_Cuts); e.SetWidth(mm(0.05))
        b.Add(e)
    nets = {}
    for n in ('D', 'S', 'G'):
        nets[n] = pcbnew.NETINFO_ITEM(b, n)
        b.Add(nets[n])
    fp = pcbnew.FootprintLoad(FP_LIB, FP_NAME)
    fp.SetReference('Q1'); fp.SetValue('TPN2R304PL')
    cx, cy = S / 2, S / 2
    # (a): source pins (1-3) towards the split, drain tab in the lower half; (b): drain pins up
    fp.SetPosition(V(cx, cy))
    fp.SetOrientationDegrees(180 if variant == 'a' else 0)
    b.Add(fp)
    for p in fp.Pads():
        p.SetNet(nets['S'] if p.GetNumber() in ('1', '2', '3') else nets['G'] if p.GetNumber() == '4' else nets['D'])

    def track(x1, y1, x2, y2, w, net):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(mm(w))
        t.SetLayer(pcbnew.F_Cu); t.SetNet(nets[net])
        b.Add(t)

    def zone(net, pts):
        z = pcbnew.ZONE(b)
        z.SetLayer(pcbnew.F_Cu)
        z.SetNet(nets[net])
        for x, y in pts:
            z.AppendCorner(V(x, y), -1)
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        b.Add(z)

    if variant == 'a':
        # Fig. 5.1: the face is copper, split across the middle; the gate runs
        # out in a narrow slot to the right edge
        split = cy - 1.1
        zone('S', [(0, 0), (S, 0), (S, split), (0, split)])
        zone('D', [(0, split), (S, split), (S, S), (0, S)])
        gx, gy = fp.FindPadByNumber('4').GetPosition().x * 1e-6, fp.FindPadByNumber('4').GetPosition().y * 1e-6
        track(gx, gy, gx, split, 0.25, 'G')
        track(gx, split, S - 0.3, split, 0.25, 'G')
    else:
        # Fig. 5.2: the footprint, 0.3 mm traces (assumed) to three 1.8 x 3 mm
        # pads on the lower edge and a drain lead round to the right
        d5 = fp.FindPadByNumber('5').GetPosition()
        dx, dy = d5.x * 1e-6, d5.y * 1e-6
        track(dx, dy, dx, cy - 2.6, 0.3, 'D'); track(dx, cy - 2.6, cx + 6.2, cy - 2.6, 0.3, 'D')
        track(cx + 6.2, cy - 2.6, cx + 6.2, cy + 7.4, 0.3, 'D')
        track(cx + 5.8, cy + 7.4, cx + 6.6, cy + 7.4, 0.8, 'D')
        for k in ('1', '2', '3'):
            pp = fp.FindPadByNumber(k).GetPosition()
            track(pp.x * 1e-6, pp.y * 1e-6, pp.x * 1e-6, cy + 4.5, 0.3, 'S')
        track(cx - 2.6, cy + 4.5, cx + 2.6, cy + 4.5, 0.3, 'S')
        track(cx - 2.6, cy + 4.5, cx - 2.6, S - 1.5, 0.3, 'S'); track(cx + 2.6, cy + 4.5, cx + 2.6, S - 1.5, 0.3, 'S')
        track(cx - 2.6, S - 2.9, cx - 2.6, S - 0.1, 1.8, 'S'); track(cx + 2.6, S - 2.9, cx + 2.6, S - 0.1, 1.8, 'S')
        g4 = fp.FindPadByNumber('4').GetPosition()
        track(g4.x * 1e-6, g4.y * 1e-6, g4.x * 1e-6, cy + 3.2, 0.25, 'G')
        track(g4.x * 1e-6, cy + 3.2, cx, cy + 3.2, 0.25, 'G'); track(cx, cy + 3.2, cx, S - 1.5, 0.25, 'G')
        track(cx, S - 2.9, cx, S - 0.1, 1.6, 'G')
    if len(b.Zones()):
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    # stackup: 2 oz (70 um) on the top, FR-4 to 1.6 mm, nothing on the bottom
    s = open(path).read()
    st = ('\t\t(stackup\n'
          '\t\t\t(layer "F.Cu" (type "copper") (thickness 0.07))\n'
          '\t\t\t(layer "dielectric 1" (type "core") (thickness 1.53) (material "FR4"))\n'
          '\t\t\t(layer "B.Cu" (type "copper") (thickness 0.07))\n'
          '\t\t)\n')
    import re
    s = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', s, flags=re.S)
    s = s.replace('\t(setup\n', '\t(setup\n' + st, 1)
    open(path, 'w').write(s)


def check_toshiba(variants=((0.3, 0.9), (0.3, 0.15), (0.8, 0.9))):
    os.makedirs(OUT, exist_ok=True)
    res = {}
    for variant, Pd, rth_ds in (('a', 2.67, 56.0), ('b', 0.63, 235.0)):
        path = os.path.join(OUT, 'tosh_%s.kicad_pcb' % variant)
        make_tosh_board(path, variant)
        P = th.Params
        P.cell_mm, P.ss = 0.2, 8
        g = th.load_kicad(path, P, fill=True)
        topo = cases.topology('tosh', g)
        k0 = P.k_fr4_xy
        for kxy, eps in variants:
            P.k_fr4_xy = kxy
            m = th.Model(g, topo, P)
            P.emissivity, P.emissivity_bot = eps, 0.9
            for Pw in ((Pd, 1.0) if (kxy, eps) == variants[0] else (Pd,)):
                dv = th.Drive(dict(Ta=25.0, v_top=0, v_bot=0, v_wire=0, turb=1, solar=0, power={'Q1': Pw},
                                   wire_current={}, wire_far={}, joule=[], label=''))
                s = th.Solver(m)
                T, _ = s.steady(dv, verbose=False)
                Tj = T[m.junc['Q1']]
                rth = (Tj - 25) / Pw
                res[(variant, eps, Pw)] = rth
                print('   board (%s), FR-4 in-plane %.1f W/mK, top emissivity %.2f, %.2f W: Tj = %.1f C, '
                      'Rth(ch-a) = %.1f C/W  (datasheet %.0f, %+.0f %%)' % (
                          variant, kxy, eps, Pw, Tj, rth, rth_ds, 100 * (rth - rth_ds) / rth_ds))
                if Pw == Pd and (kxy, eps) == variants[0]:
                    th.plot_maps(m, T, topo, th.summarize(m, T, topo)[0], os.path.join(OUT, 'tosh_%s' % variant),
                                 'Toshiba board (%s), %.2f W, Ta 25 C, still air: Tj %.1f C, Rth %.1f C/W' % (variant, Pw, Tj, rth))
        P.emissivity, P.emissivity_bot, P.k_fr4_xy = 0.9, None, k0
    return res


def main():
    t0 = time.time()
    check_spreading()
    check_through()
    check_transient()
    print('\n4. Toshiba TPN2R304PL datasheet Rth(ch-a), Ta = 25 C, still air, board horizontal')
    check_toshiba()
    print('\n  validation done in %.0f s; plots in %s' % (time.time() - t0, os.path.relpath(OUT)))


if __name__ == '__main__':
    main()
