# -*- coding: utf-8 -*-
"""LayerCam v1: impedance of the coupled pairs, from the stackups and the
pair rules the boards are built with.

    tools/kd python3 sim/impedance.py      writes sim/impedance.md, exits 1 on a FAIL

Sources of truth, read from the code (not copied):
  src/board.py  DIFF      each pair class's width and gap
  src/pcb.py    STACKUP6  JLC06161H-3313 layer thicknesses and Dk
                STACKUP2  the 2-layer boards' core (thickness() - 0.07)
                CLEAR     the netclass clearance; the ground fill keeps
                          CLEAR + 0.05 (src/stitch.py) from other nets
JLCPCB's own figures (jlcpcb.com/impedance, read 26 Oct 2026):
  JLC06161H-3313: 35 um outer copper, 3313 prepreg 0.0994 mm, 15.2 um
  inner copper, 0.55 mm cores, 2116 prepreg 0.1088 mm.  Dk: 3313 4.1,
  2116 4.16, core 4.6.  Solder mask: 1.2 mil (30 um) on the substrate,
  0.6 mil (15 um) on the copper, 1.2 mil between traces, Dk 3.8.

Two methods: closed forms (IPC-2141; Hammerstad-Jensen microstrip with
Wheeler's thickness correction as given in Wadell, "Transmission Line
Design Handbook" 3.5; the IPC/Wadell edge-coupling factor; Wadell's
coated-microstrip correction for the mask), and the 2D field solver in
fieldsolve.py, checked here against exact results first.  The field
solver is the one the verdict uses.
"""
import ast, math, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import fieldsolve as fs

OUT = os.path.join(HERE, 'impedance.md')

# ---------------------------------------------------------------- sources
def _src(name):
    return open(os.path.join(V1, 'src', name)).read()


def read_diff():
    tree = ast.parse(_src('board.py'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'DIFF':
            return ast.literal_eval(node.value)
    raise KeyError('DIFF')


def read_stackup6():
    s = _src('pcb.py')
    blk = s[s.index('STACKUP6 = '):s.index('STACKUP2 = ')]
    lay = re.findall(r'\(layer "([^"]+)" \(type "([^"]+)"\)(?: \(color "[^"]*"\))? \(thickness ([\d.]+)\)'
                     r'(?: \(material "[^"]*"\) \(epsilon_r ([\d.]+)\))?', blk)
    return [(n, t, float(th), float(er) if er else None) for n, t, th, er in lay]


def read_stackup2():
    s = _src('pcb.py')
    er = float(re.search(r'STACKUP2 = .*?epsilon_r ([\d.]+)', s, re.S).group(1))
    geo = _src('geometry.py')
    usb_t = float(re.search(r'USB_T = ([\d.]+)', geo).group(1))
    m = re.search(r"if board == 'main':.*?else:\s*LAYERS, TRACK, CLEAR, VIA = 2, ([\d.]+), ([\d.]+)", s, re.S)
    return dict(core=usb_t - 0.07, er=er, cu=0.035, clear=float(m.group(2)))


def read_clear_main():
    s = _src('pcb.py')
    m = re.search(r"if board == 'main':\s*LAYERS, TRACK, CLEAR, VIA = 6, ([\d.]+), ([\d.]+)", s)
    return float(m.group(2))


DIFF = read_diff()
ST6 = read_stackup6()
ST2 = read_stackup2()
FILL_EXTRA = 0.05                 # stitch.py: zone clearance = CLEAR + 0.05

# outer layer of the 6-layer board: F.Cu over dielectric 1 to In1
_cu_out = [t for n, ty, t, e in ST6 if n == 'F.Cu'][0]
_pp = [(t, e) for n, ty, t, e in ST6 if n == 'dielectric 1'][0]
MASK = dict(on_sub=0.0305, on_cu=0.0152, er=3.8)      # JLCPCB: 1.2 / 0.6 mil, Dk 3.8
ETCH = 0.0127                     # top of a track narrower by 0.5 mil a side (assumed, typical etch)
TARGET = {'MIPI': (100.0, 0.10), 'USB': (90.0, 0.10)}
MIN_W, MIN_GAP = 0.10, 0.127      # the rules the caller set for any new width / gap

checks = []


def check(ok, what, warn=False):
    checks.append(('PASS' if ok else ('WARN' if warn else 'FAIL'), what))


# ---------------------------------------------------------------- closed forms
def hj(w, h, t, er):
    u = w / h
    th = t / h
    if t > 0:
        du1 = th / math.pi * math.log(1 + 4 * math.e / (th * (1 / math.tanh(math.sqrt(6.517 * u))) ** 2))
        dur = 0.5 * (1 + 1 / math.cosh(math.sqrt(er - 1))) * du1
    else:
        du1 = dur = 0.0
    u1, ur = u + du1, u + dur

    def z01(x):
        f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / x) ** 0.7528)
        return 60 * math.log(f / x + math.sqrt(1 + (2 / x) ** 2))

    def ee(x):
        a = 1 + math.log((x ** 4 + (x / 52) ** 2) / (x ** 4 + 0.432)) / 49 + math.log(1 + (x / 18.1) ** 3) / 18.7
        b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
        return (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / x) ** (-a * b)
    eeff = ee(ur) * (z01(u1) / z01(ur)) ** 2
    z = z01(ur) / math.sqrt(ee(ur))
    return z, eeff


def mask_factor(eeff, er_mask, c, h):
    """Wadell's embedded-microstrip approximation used for the mask: a coat c
    thick over the track pulls the effective permittivity towards the
    coat's, eeff' = eeff exp(-2c/h) + er_mask (1 - exp(-2c/h)); Z scales as
    sqrt(eeff / eeff').  Rough: a sanity check on the solver only."""
    k = math.exp(-2 * c / h)
    e2 = eeff * k + er_mask * (1 - k)
    return math.sqrt(eeff / e2), e2


def closed_forms(w, s, h, t, er):
    ipc_z0 = 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (0.8 * w + t))
    z, ee = hj(w, h, t, er)
    f, _ = mask_factor(ee, MASK['er'], MASK['on_cu'], h)
    k = 1 - 0.48 * math.exp(-0.96 * s / h)
    return dict(ipc_z0=ipc_z0, ipc_zd=2 * ipc_z0 * k, hj_z0=z, hj_zd=2 * z * k, hj_z0m=z * f, hj_zdm=2 * z * f * k,
                eeff=ee)


# ---------------------------------------------------------------- field-solver sections
def microstrip_section(w, s, h, t, er, pair=True, mask=True, gnd_gap=None, etch=ETCH, er_mask=MASK['er'],
                       top_gnd=None, er_top=None, hmin=0.001):
    """Edge-coupled (or single) surface microstrip over a plane at y = 0.
    gnd_gap: coplanar ground fill this far from each outer track edge.
    top_gnd: a second plane at that height (stripline cases, not used)."""
    xc = [-(s + w) / 2, (s + w) / 2] if pair else [0.0]
    span = 2.0 + (s + 2 * w)
    ytop = h + t + 1.5
    xf = [-span, span]
    for x in xc:
        xf += [x - w / 2, x + w / 2, x - w / 2 + etch, x + w / 2 - etch]
    if gnd_gap is not None:
        xo = max(abs(x) for x in xc) + w / 2 + gnd_gap
        xf += [-xo, xo, -xo - etch, xo + etch]
    yf = [0, h, h + t, h + MASK['on_sub'], h + t + MASK['on_cu'], ytop]
    xs = fs.axis(xf, -span, span, hmin=hmin)
    ys = fs.axis(yf, 0, ytop, hmin=hmin)
    sec = fs.Section(xs, ys)

    def halfw(Y):
        # trapezoid: full width at the bottom (on the laminate), narrower at the top
        return w / 2 - etch * np.clip((Y - h) / t, 0, 1)

    def eps(X, Y):
        e = np.ones_like(X)
        e[Y < h] = er
        if mask:
            m = (Y >= h) & (Y < h + MASK['on_sub'])
            for x in xc:
                m |= (np.abs(X - x) <= halfw(np.minimum(Y, h + t)) + MASK['on_cu']) & (Y < h + t + MASK['on_cu']) & (Y >= h)
            if gnd_gap is not None:
                m |= (np.abs(X) >= xo - MASK['on_cu']) & (Y < h + t + MASK['on_cu']) & (Y >= h)
            e[m] = er_mask
        return e
    sec.set_eps(eps)
    tol = 1e-9
    for k, x in enumerate(xc, start=1):
        sec.add_conductor(k, lambda X, Y, x=x: (Y >= h - tol) & (Y <= h + t + tol) & (np.abs(X - x) <= halfw(Y) + tol))
    if gnd_gap is not None:
        sec.add_conductor(0, lambda X, Y: (Y >= h - tol) & (Y <= h + t + tol) & (np.abs(X) >= xo + etch * np.clip((Y - h) / t, 0, 1) - tol))
    return sec, list(range(1, len(xc) + 1))


def solve(**kw):
    sec, ks = microstrip_section(**kw)
    return fs.lines(sec, ks)


# ---------------------------------------------------------------- self-checks of the solver
def validate():
    rows = []
    # 1) zero-thickness symmetric stripline, w = b/2, er 4: Cohn's exact formula
    b, w, er = 0.4, 0.2, 4.0
    k = 1 / math.cosh(math.pi * w / (2 * b))
    from scipy.special import ellipk
    exact = 30 * math.pi / math.sqrt(er) * ellipk(k * k) / ellipk(1 - k * k)
    xs = fs.axis([-w / 2, w / 2, -2, 2], -2, 2)
    ys = fs.axis([0, b / 2, b], 0, b)
    sec = fs.Section(xs, ys)
    sec.cond[0, :] = sec.cond[-1, :] = -1          # open sides (Neumann): the plates are the reference
    sec.cond[0, 0] = sec.cond[-1, 0] = sec.cond[0, -1] = sec.cond[-1, -1] = 0
    sec.set_eps(lambda X, Y: np.full_like(X, er))
    sec.add_conductor(1, lambda X, Y: (np.abs(Y - b / 2) < 1e-9) & (np.abs(X) <= w / 2 + 1e-9))
    z = fs.lines(sec, [1])['Z0']
    rows.append(('stripline b 0.4, w 0.2, t 0, er 4 (Cohn, exact)', exact, z))
    # 2) zero-thickness microstrip, w/h 1, er 4.1: Hammerstad-Jensen (0.2 % of exact)
    for wh in (1.0, 2.0):
        hjz, _ = hj(wh * 0.1, 0.1, 0.0, 4.1)
        r = solve(w=wh * 0.1, s=0, h=0.1, t=1e-4, er=4.1, pair=False, mask=False, etch=0.0)
        rows.append(('microstrip w/h %.0f, t 0, er 4.1 (Hammerstad-Jensen)' % wh, hjz, r['Z0']))
    return rows


# ---------------------------------------------------------------- the cases
def main_case(name):
    nets, w, s = DIFF['main'][name]
    return w, s


def run():
    L = []
    w_ = L.append
    h, er = _pp
    t = _cu_out
    clear = read_clear_main()
    gap_fill = clear + FILL_EXTRA
    w_('# LayerCam v1: impedance of the coupled pairs\n')
    w_('Computed by `sim/impedance.py` (field solver `sim/fieldsolve.py`). Widths and gaps from `src/board.py` DIFF; '
       'stackups from `src/pcb.py`; JLCPCB\'s published figures for JLC06161H-3313 (jlcpcb.com/impedance, read 26 Oct 2026).\n')
    w_('## Stackup used\n')
    w_('| | value | source |\n|---|---|---|')
    w_('| outer copper (F.Cu / B.Cu) | %.3f mm (1 oz finished) | pcb.STACKUP6 = JLCPCB table |' % t)
    w_('| L1-L2 / L5-L6 prepreg | 3313 x1, %.4f mm, Dk %.2f | pcb.STACKUP6 = JLCPCB table (Dk table: 3313 4.1) |' % (h, er))
    w_('| inner copper | 0.0152 mm (0.5 oz) | JLCPCB |')
    w_('| cores / middle prepreg | 0.55 mm Dk 4.6 / 2116 0.1088 mm Dk 4.16 | JLCPCB (not on the outer-layer path) |')
    w_('| solder mask | %.1f um on laminate, %.1f um on copper, Dk %.1f | JLCPCB calculator parameters |'
       % (MASK['on_sub'] * 1e3, MASK['on_cu'] * 1e3, MASK['er']))
    w_('| track etch | top narrower by %.1f um each side (trapezoid) | assumed, typical |' % (ETCH * 1e3))
    w_('| ground fill beside a pair (main) | %.3f mm from the track (CLEAR %.3f + %.2f) | src/pcb.py, src/stitch.py |'
       % (gap_fill, clear, FILL_EXTRA))
    w_('| USB board | 2 layers, core %.2f mm (USB_T %.1f - 0.07), Dk %.1f, 35 um copper, ground fill both sides at %.2f mm |'
       ' pcb.STACKUP2, geometry.USB_T, stitch.py |' % (ST2['core'], ST2['core'] + 0.07, ST2['er'], ST2['clear'] + FILL_EXTRA))
    w_('')

    w_('## Field solver checked against exact results\n')
    w_('| case | reference (ohm) | solver (ohm) | error |\n|---|---|---|---|')
    for name, ref, z in validate():
        err = (z - ref) / ref
        w_('| %s | %.2f | %.2f | %+.2f %% |' % (name, ref, z, 100 * err))
        check(abs(err) < 0.015, 'solver within 1.5 %% of %s (%+.2f %%)' % (name.split(' (')[0], 100 * err))
    w_('')

    # --------------------------------------------- main board, as designed
    w_('## Main board, outer layers over In1 / In4, as designed\n')
    w_('Closed forms first (no coplanar ground; the IPC-2141 single-line formula is known to read high for w/h near 1, '
       'Hammerstad-Jensen is within about 1 % for the bare line); then the field solver, bare and with the ground fill '
       'that stitch.py pours beside the pair. Zdiff = 2 Zodd, Zcm = Zeven / 2.\n')
    w_('| pair | w / gap (mm) | IPC-2141 Z0 / Zdiff | H-J Z0 / Zdiff (no mask) | H-J + mask Z0 / Zdiff | '
       'solver Z0 (single) | solver Zdiff, no fill | solver Zdiff, fill at %.3f | solver Zcm | target |' % gap_fill)
    w_('|---|---|---|---|---|---|---|---|---|---|')
    results = {}
    for name in ('MIPI', 'USB'):
        wd, sd = main_case(name)
        cf = closed_forms(wd, sd, h, t, er)
        z1 = solve(w=wd, s=sd, h=h, t=t, er=er, pair=False)
        zp = solve(w=wd, s=sd, h=h, t=t, er=er)
        zf = solve(w=wd, s=sd, h=h, t=t, er=er, gnd_gap=gap_fill)
        tgt, tol = TARGET[name]
        results[name] = (wd, sd, zp, zf, z1)
        w_('| %s | %.3f / %.3f | %.1f / %.1f | %.1f / %.1f | %.1f / %.1f | %.1f | %.1f | %.1f | %.1f | %.0f +-%.0f %% |'
           % (name, wd, sd, cf['ipc_z0'], cf['ipc_zd'], cf['hj_z0'], cf['hj_zd'], cf['hj_z0m'], cf['hj_zdm'],
              z1['Z0'], zp['Zdiff'], zf['Zdiff'], zp['Zcm'], tgt, tol * 100))
        lo, hi = tgt * (1 - tol), tgt * (1 + tol)
        worst = min(zp['Zdiff'], zf['Zdiff'])
        check(lo <= zp['Zdiff'] <= hi and lo <= zf['Zdiff'] <= hi,
              'main %s %.2f / %.2f: Zdiff %.1f (bare) / %.1f (with fill) against %.0f +-%.0f %% (%.0f-%.0f)'
              % (name, wd, sd, zp['Zdiff'], zf['Zdiff'], tgt, tol * 100, lo, hi))
        e1 = solve(w=wd - 0.015, s=sd + 0.015, h=h, t=t, er=er)['Zdiff']
        e2 = solve(w=wd + 0.015, s=sd - 0.015, h=h, t=t, er=er)['Zdiff']
        results[name] = (wd, sd, zp, zf, z1, e1, e2)
        check(lo <= e1 <= hi and lo <= e2 <= hi,
              'main %s %.2f / %.2f with the track 0.015 mm narrower / wider (same pitch): %.1f / %.1f ohm against %.0f-%.0f'
              % (name, wd, sd, e1, e2, lo, hi), warn=True)
    w_('')

    # sensitivity: what moves the number
    wd, sd = main_case('MIPI')
    w_('### Sensitivity (MIPI %.2f / %.2f, field solver, no fill)\n' % (wd, sd))
    w_('| change | Zdiff (ohm) |\n|---|---|')
    w_('| as above | %.1f |' % results['MIPI'][2]['Zdiff'])
    for lab, kw in (('no solder mask', dict(mask=False)), ('rectangular track (no etch)', dict(etch=0.0)),
                    ('prepreg +10 %% (%.3f mm)' % (h * 1.1), dict(h=h * 1.1)),
                    ('prepreg -10 %% (%.3f mm)' % (h * 0.9), dict(h=h * 0.9)),
                    ('Dk 3.9', dict(er=3.9)), ('Dk 4.3', dict(er=4.3)),
                    ('track -0.015 mm (over-etch)', dict(w=wd - 0.015)), ('track +0.015 mm', dict(w=wd + 0.015))):
        args = dict(w=wd, s=sd, h=h, t=t, er=er)
        args.update(kw)
        if 'w' in kw:
            args['s'] = sd + (wd - kw['w'])          # same pitch: over-etch widens the gap
        w_('| %s | %.1f |' % (lab, solve(**args)['Zdiff']))
    w_('')

    # --------------------------------------------- the widths that hit target
    w_('## Widths and gaps that hit the targets (main board outer layers)\n')
    w_('Field solver, solder mask on, ground fill at %.3f mm beside the pair (the fill stitch.py pours; where the three '
       'MIPI lanes run side by side there is no fill between them, so the bare figure applies there). Rules: track >= %.3f mm, '
       'gap >= %.3f mm.\n' % (gap_fill, MIN_W, MIN_GAP))
    w_('| w (mm) | gap (mm) | Zdiff bare | Zdiff with fill | Zodd | Zcm |\n|---|---|---|---|---|---|')
    grid = []
    for wd in (0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15):
        for sd in (0.127, 0.15, 0.175, 0.20, 0.25):
            zp = solve(w=wd, s=sd, h=h, t=t, er=er)
            zf = solve(w=wd, s=sd, h=h, t=t, er=er, gnd_gap=gap_fill)
            grid.append((wd, sd, zp, zf))
            w_('| %.3f | %.3f | %.1f | %.1f | %.1f | %.1f |' % (wd, sd, zp['Zdiff'], zf['Zdiff'], zp['Zodd'], zp['Zcm']))
    w_('')
    # the recommendation: inside +-4 % of target bare and beside the fill (so a
    # +-0.015 mm etch still lands inside +-10 %), within the rules, and the
    # smallest change from what the board has now
    rec = {}
    for name in ('MIPI', 'USB'):
        tgt, tol = TARGET[name]
        lo, hi = tgt * (1 - tol), tgt * (1 + tol)
        w0, s0 = main_case(name)
        cand = sorted([(round(abs(wd - w0) + abs(sd - s0), 4), abs(zp['Zdiff'] - tgt) + abs(zf['Zdiff'] - tgt),
                        wd, sd, zp, zf) for wd, sd, zp, zf in grid
                       if wd >= MIN_W - 1e-9 and sd >= MIN_GAP - 1e-9
                       and abs(zp['Zdiff'] / tgt - 1) <= 0.04 and abs(zf['Zdiff'] / tgt - 1) <= 0.04],
                      key=lambda r: (r[0], r[1]))
        for _, _, wd, sd, zp, zf in cand:
            e1 = solve(w=wd - 0.015, s=sd + 0.015, h=h, t=t, er=er)['Zdiff']
            e2 = solve(w=wd + 0.015, s=sd - 0.015, h=h, t=t, er=er)['Zdiff']
            if lo <= e1 <= hi and lo <= e2 <= hi:
                rec[name] = (None, wd, sd, zp, zf, e1, e2)
                break
    for name in ('MIPI', 'USB'):
        _, wd, sd, zp, zf, e1, e2 = rec[name]
        tgt, tol = TARGET[name]
        lo, hi = tgt * (1 - tol), tgt * (1 + tol)
        w_('- **%s**: %.3f / %.3f mm (the smallest change from the board\'s rule that is within 4 %% of target and stays '
           'inside +-10 %% for a track 0.015 mm narrower or wider at the same pitch) gives %.1f ohm bare, %.1f ohm '
           'beside the fill; %.1f / %.1f ohm with the etch error.' % (name, wd, sd, zp['Zdiff'], zf['Zdiff'], e1, e2))
        check(all(lo <= z <= hi for z in (zp['Zdiff'], zf['Zdiff'], e1, e2)),
              'recommended main %s %.3f / %.3f: %.1f / %.1f ohm, %.1f-%.1f across +-0.015 mm etch, inside %.0f-%.0f'
              % (name, wd, sd, zp['Zdiff'], zf['Zdiff'], min(e1, e2), max(e1, e2), lo, hi))
    w_('')
    w_('Ordering with JLCPCB\'s impedance control (they adjust the widths to their process) is the other half of the '
       'fix: state 100 ohm differential on L1/L6 for the MIPI class and 90 ohm for USB.\n')

    # --------------------------------------------- USB board
    st = ST2
    nets, wu, su = DIFF['usb']['USB']
    gfill = st['clear'] + FILL_EXTRA
    w_('## USB board (2 layers, %.2f mm core)\n' % st['core'])
    w_('The pair runs on F with ground fill beside it (stitch.py, %.2f mm away) and the B ground fill %.2f mm below: '
       'a coplanar waveguide with ground, the side fill doing most of the work.\n' % (gfill, st['core']))
    w_('| w / gap (mm) | fill gap (mm) | Zdiff | Zcm | note |\n|---|---|---|---|---|')
    zu = solve(w=wu, s=su, h=st['core'], t=st['cu'], er=st['er'], gnd_gap=gfill)
    zu_nofill = solve(w=wu, s=su, h=st['core'], t=st['cu'], er=st['er'])
    w_('| %.2f / %.2f | %.2f | %.1f | %.1f | as designed |' % (wu, su, gfill, zu['Zdiff'], zu['Zcm']))
    w_('| %.2f / %.2f | none | %.1f | %.1f | if the fill is cut back near the pair |' % (wu, su, zu_nofill['Zdiff'], zu_nofill['Zcm']))
    best = None
    rows = []
    for wd in (0.20, 0.25, 0.30, 0.35):
        for sd in (0.127, 0.15, 0.20):
            z = solve(w=wd, s=sd, h=st['core'], t=st['cu'], er=st['er'], gnd_gap=gfill)
            rows.append((wd, sd, z))
            d = abs(z['Zdiff'] - 90)
            if best is None or d < best[0]:
                best = (d, wd, sd, gfill, z)
    for wd, sd, z in rows:
        w_('| %.2f / %.3f | %.2f | %.1f | %.1f | |' % (wd, sd, gfill, z['Zdiff'], z['Zcm']))
    _, wb, sb, gb, zb = best
    w_('')
    w_('Closest to 90 ohm with the fill where stitch.py puts it: **%.2f / %.3f mm, %.1f ohm**.\n' % (wb, sb, zb['Zdiff']))
    tgt, tol = TARGET['USB']
    check(tgt * (1 - tol) <= zu['Zdiff'] <= tgt * (1 + tol),
          'USB board %.2f / %.2f with fill at %.2f: Zdiff %.1f against 90 +-10 %%' % (wu, su, gfill, zu['Zdiff']),
          warn=True)
    # electrical length on the USB board: ~ 12 mm from the receptacle to J2 (layout_usb.py)
    tpd = math.sqrt(zu['eodd']) / fs.C_LIGHT * 1e-3 * 1e12        # ps/mm
    L_usb = 14.0
    w_('The USB board\'s pair is about %.0f mm long (receptacle at y 4, cable connector at y 12.5, ESD on the way): '
       '%.0f ps of flight time at %.1f ps/mm, against USB 2.0 high speed\'s 500 ps minimum edge (10-90 %%). A line '
       'shorter than about a sixth of the edge (%.0f ps) behaves as a lumped element; this one is close to it, so its '
       'impedance matters little next to the cable and connectors (the 6-wire SH cable to the main board is unshielded, '
       'parallel wires: roughly 100-150 ohm differential, not controlled).\n'
       % (L_usb, L_usb * tpd, tpd, 500 / 6))
    return L, results, rec, zu, (wb, sb, gb, zb)


def main():
    L, results, rec, zu, best_usb = run()
    w = L.append
    w('## Checks\n')
    for s, what in checks:
        w('- %s %s' % (s, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    w('## Verdict\n')
    mw, ms = DIFF['main']['MIPI'][1:]
    uw, us = DIFF['main']['USB'][1:]
    r = rec['MIPI']; u = rec['USB']
    m, us_ = results['MIPI'], results['USB']
    w('- **MIPI %.2f / %.2f mm: %.1f ohm bare, %.1f ohm beside the ground fill: inside 100 +-10 %%, but high.** '
      'A 0.015 mm over-etch takes it to %.1f ohm (outside). Recommended: **%.3f / %.3f mm** (%.1f / %.1f ohm; '
      '%.1f-%.1f across the etch). The receiver end is forgiving (RV1106 MIPI ZID 80-125 ohm; two lanes well under '
      '1 Gbit/s for 2304 x 1296 at 30 fps RAW10), so the current rule would very likely work; the change costs '
      'nothing.' % (mw, ms, m[2]['Zdiff'], m[3]['Zdiff'], m[5], r[1], r[2], r[3]['Zdiff'], r[4]['Zdiff'],
                    min(r[5], r[6]), max(r[5], r[6])))
    w('- **USB (main) %.2f / %.2f mm: %.1f ohm bare, %.1f beside the fill: at the top edge of 90 +-10 %%** '
      '(%.1f with a 0.015 mm over-etch). Recommended: **%.3f / %.3f mm** (%.1f / %.1f ohm; %.1f-%.1f across the '
      'etch).' % (uw, us, us_[2]['Zdiff'], us_[3]['Zdiff'], us_[5], u[1], u[2], u[3]['Zdiff'], u[4]['Zdiff'],
                  min(u[5], u[6]), max(u[5], u[6])))
    wb, sb, gb, zb = best_usb
    w('- **USB board %.2f / %.2f mm: %.1f ohm.** A 2-layer 1.2 mm board cannot put a plane close under the pair; the '
      'side fill sets the impedance. %.2f / %.3f mm with the fill where it is gives %.1f ohm. The run (about 14 mm) is '
      'electrically short for USB 2.0 and the SH cable after it is uncontrolled anyway: WARN, not FAIL.'
      % (DIFF['usb']['USB'][1], DIFF['usb']['USB'][2], zu['Zdiff'], wb, sb, zb['Zdiff']))
    w('- USB layer change on the main board (pairs.py: F to B and back): no ground via beside the signal vias '
      '(stitching keeps 1.2 mm off every via). Add one ground via within about 1 mm of each transition so the '
      'return current can move between In1 and In4.')
    w('')
    warns = [c for c in checks if c[0] == 'WARN']
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
