# -*- coding: utf-8 -*-
"""LayerCam v1: impedance of the controlled tracks on PCBWay's stackups.

    tools/kd python3 sim/impedance.py      writes sim/impedance.md, exits 1 on a FAIL

Everything the boards are built with is read from the code, not copied:
  src/pcb.py    STACKUP6   the main board's layers (thickness, Dk) - PCBWay's build
                STACKUP2   the 2-layer boards' core: thickness() - 0.07, epsilon_r
                configure  the netclass clearance CLEAR of each board
  src/stitch.py            the ground fill keeps CLEAR + 0.05 from other nets
  src/board.py  DIFF       each pair class's width and gap
                RF_W       the antenna feed's width (B.Cu over In4)
  src/geometry.py USB_T    the USB board's thickness

PCBWay's published "Regular" 6-layer 1.6 mm build No. 1 (pcbway.com multi-layer laminated structure, read
27 Oct 2026) is kept below only to check that STACKUP6 still matches it.  PCBWay publishes no solder-mask
thickness or Dk (its own calculator leaves the mask out): typical LPI figures are assumed (15 um on copper,
30 um on laminate, Dk 3.8) and the no-mask figures are given too.

Field solver: fieldsolve.py (2D finite volume), checked here against Cohn's exact stripline and
Hammerstad-Jensen's microstrip first.  Closed forms (IPC-2141, Hammerstad-Jensen) for the bare pairs as a
sanity column.
"""
import ast, math, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import fieldsolve as fs

OUT = os.path.join(HERE, 'impedance.md')


# ---------------------------------------------------------------- read the design
def _src(name):
    return open(os.path.join(V1, 'src', name)).read()


def _assign(src, name):
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def read_stackup6():
    s = _src('pcb.py')
    blk = s[s.index('STACKUP6 = '):s.index('STACKUP2 = ')]
    out = []
    for m in re.finditer(r'\(layer "([^"]+)" \(type "([^"]+)"\)(?: \(color "[^"]*"\))? \(thickness ([\d.]+)\)'
                         r'(?: \(material "([^"]*)"\) \(epsilon_r ([\d.]+)\))?', blk):
        n, t, th, mat, er = m.groups()
        out.append(dict(name=n, type=t, t=float(th), material=mat, er=float(er) if er else None))
    return out


def read_stackup2():
    s = _src('pcb.py')
    er = float(re.search(r'STACKUP2 = .*?epsilon_r ([\d.]+)', s, re.S).group(1))
    cu = float(re.search(r'STACKUP2 = .*?"F.Cu" \(type "copper"\) \(thickness ([\d.]+)\)', s, re.S).group(1))
    usb_t = float(re.search(r'USB_T = ([\d.]+)', _src('geometry.py')).group(1))
    sub = float(re.search(r"STACKUP2 % \(thickness\(\) - ([\d.]+)\)", s).group(1))
    return dict(core=usb_t - sub, er=er, cu=cu, board_t=usb_t)


def read_clear(board):
    s = _src('pcb.py')
    if board == 'main':
        m = re.search(r"if board == 'main':\s*LAYERS, TRACK, CLEAR, VIA = 6, ([\d.]+), ([\d.]+)", s)
    else:
        m = re.search(r"else:\s*LAYERS, TRACK, CLEAR, VIA = 2, ([\d.]+), ([\d.]+)", s)
    return float(m.group(1)), float(m.group(2))


def read_fill_extra():
    return float(re.search(r"clearance=pcb\.CLEAR \+ ([\d.]+)", _src('stitch.py')).group(1))


ST6 = read_stackup6()
ST2 = read_stackup2()
BOARD_SRC = _src('board.py')
DIFF = _assign(BOARD_SRC, 'DIFF')
RF_W = _assign(BOARD_SRC, 'RF_W')
FILL_EXTRA = read_fill_extra()
TRACK_MAIN, CLEAR_MAIN = read_clear('main')
TRACK_USB, CLEAR_USB = read_clear('usb')
FILL_MAIN = CLEAR_MAIN + FILL_EXTRA
FILL_USB = CLEAR_USB + FILL_EXTRA


if os.environ.get('IMPEDANCE_STACKUP') == 'pcbway-no1':
    # preview: PCBWay's published build in place of STACKUP6 (set when src/pcb.py has not caught up yet)
    ST6 = [dict(name='F.Cu', type='copper', t=0.035, material=None, er=None),
           dict(name='dielectric 1', type='prepreg', t=0.1195, material='2116', er=4.45),
           dict(name='In1.Cu', type='copper', t=0.035, material=None, er=None),
           dict(name='dielectric 2', type='core', t=0.43, material='FR4', er=4.6),
           dict(name='In2.Cu', type='copper', t=0.035, material=None, er=None),
           dict(name='dielectric 3', type='prepreg', t=0.175, material='7628', er=4.74),
           dict(name='In3.Cu', type='copper', t=0.035, material=None, er=None),
           dict(name='dielectric 4', type='core', t=0.43, material='FR4', er=4.6),
           dict(name='In4.Cu', type='copper', t=0.035, material=None, er=None),
           dict(name='dielectric 5', type='prepreg', t=0.1195, material='2116', er=4.45),
           dict(name='B.Cu', type='copper', t=0.035, material=None, er=None)]
    OUT = os.environ.get('IMPEDANCE_OUT', OUT)


def layer(name):
    return [x for x in ST6 if x['name'] == name][0]


# the outer layers: F.Cu over dielectric 1 to In1, B.Cu over dielectric 5 to In4
OUTER = {'F': dict(h=layer('dielectric 1')['t'], er=layer('dielectric 1')['er'], t=layer('F.Cu')['t'], ref='In1'),
         'B': dict(h=layer('dielectric 5')['t'], er=layer('dielectric 5')['er'], t=layer('B.Cu')['t'], ref='In4')}

# PCBWay's published build No. 1, for the check only (thickness after lamination, Dk)
PCBWAY_NO1 = [('F.Cu', 0.035, None), ('dielectric 1', 0.1195, 4.45), ('In1.Cu', 0.035, None),
              ('dielectric 2', 0.43, 4.6), ('In2.Cu', 0.035, None), ('dielectric 3', 0.175, 4.74),
              ('In3.Cu', 0.035, None), ('dielectric 4', 0.43, 4.6), ('In4.Cu', 0.035, None),
              ('dielectric 5', 0.1195, 4.45), ('B.Cu', 0.035, None)]

MASK = dict(on_sub=0.0305, on_cu=0.0152, er=3.8)     # typical LPI (PCBWay publishes none): ASSUMED
ETCH = 0.0127                     # track top narrower by 0.5 mil a side (typical etch): ASSUMED
ETCH_TOL = 0.015                  # width error checked: +-0.015 mm at the same pitch
TARGET = {'MIPI': (100.0, 0.10), 'USB': (90.0, 0.10), 'RF': (50.0, 0.10)}
GAP_MIN = {'main': CLEAR_MAIN, 'usb': CLEAR_USB}

checks = []


def check(ok, what, warn=False):
    checks.append(('PASS' if ok else ('WARN' if warn else 'FAIL'), what))


# ---------------------------------------------------------------- closed forms (sanity column)
def hj(w, h, t, er):
    """Hammerstad-Jensen microstrip with Wheeler's thickness correction (Wadell 3.5.1)."""
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
    return z01(ur) / math.sqrt(ee(ur)), ee(ur) * (z01(u1) / z01(ur)) ** 2


def closed_forms(w, s, h, t, er):
    ipc = 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (0.8 * w + t))
    z, _ = hj(w, h, t, er)
    k = 1 - 0.48 * math.exp(-0.96 * s / h) if s else 1.0
    return dict(ipc_z0=ipc, ipc_zd=2 * ipc * k, hj_z0=z, hj_zd=2 * z * k)


# ---------------------------------------------------------------- field-solver sections
def microstrip_section(w, s, h, t, er, pair=True, mask=True, gnd_gap=None, etch=ETCH, hmin=0.001):
    """Edge-coupled pair (or one track) on the surface over a plane at y = 0; gnd_gap: coplanar ground
    fill this far from each outer track edge, to the sides of the domain."""
    xc = [-(s + w) / 2, (s + w) / 2] if pair else [0.0]
    span = 2.0 + (s + 2 * w) + 2 * h
    ytop = h + t + 1.5 + h
    xf = [-span, span]
    for x in xc:
        xf += [x - w / 2, x + w / 2, x - w / 2 + etch, x + w / 2 - etch]
    xo = None
    if gnd_gap is not None:
        xo = max(abs(x) for x in xc) + w / 2 + gnd_gap
        xf += [-xo, xo, -xo - etch, xo + etch]
    yf = [0, h, h + t, h + MASK['on_sub'], h + t + MASK['on_cu'], ytop]
    sec = fs.Section(fs.axis(xf, -span, span, hmin=hmin), fs.axis(yf, 0, ytop, hmin=hmin))

    def halfw(Y):
        return w / 2 - etch * np.clip((Y - h) / t, 0, 1)

    def eps(X, Y):
        e = np.ones_like(X)
        e[Y < h] = er
        if mask:
            m = (Y >= h) & (Y < h + MASK['on_sub'])
            for x in xc:
                m |= (np.abs(X - x) <= halfw(np.minimum(Y, h + t)) + MASK['on_cu']) & (Y < h + t + MASK['on_cu']) \
                    & (Y >= h)
            if xo is not None:
                m |= (np.abs(X) >= xo - MASK['on_cu']) & (Y < h + t + MASK['on_cu']) & (Y >= h)
            e[m] = MASK['er']
        return e
    sec.set_eps(eps)
    tol = 1e-9
    for k, x in enumerate(xc, start=1):
        sec.add_conductor(k, lambda X, Y, x=x: (Y >= h - tol) & (Y <= h + t + tol) & (np.abs(X - x) <= halfw(Y) + tol))
    if xo is not None:
        sec.add_conductor(0, lambda X, Y: (Y >= h - tol) & (Y <= h + t + tol)
                          & (np.abs(X) >= xo + etch * np.clip((Y - h) / t, 0, 1) - tol))
    return sec, list(range(1, len(xc) + 1))


def solve(**kw):
    sec, ks = microstrip_section(**kw)
    return fs.lines(sec, ks)


def zdiff(w, s, lay, fill=None, mask=True, dw=0.0):
    """Zdiff of a pair on outer layer lay ('F' / 'B' / 'usb'), the track dw wider (same pitch)."""
    p = OUTER[lay] if lay in OUTER else dict(h=ST2['core'], er=ST2['er'], t=ST2['cu'])
    g = None if fill is None else fill - dw / 2
    return solve(w=w + dw, s=s - dw, h=p['h'], t=p['t'], er=p['er'], gnd_gap=g, mask=mask)['Zdiff']


def z0(w, lay, fill=None, mask=True, dw=0.0):
    p = OUTER[lay]
    g = None if fill is None else fill - dw / 2
    return solve(w=w + dw, s=0, h=p['h'], t=p['t'], er=p['er'], pair=False, gnd_gap=g, mask=mask)['Z0']


# ---------------------------------------------------------------- solver checks
def validate():
    from scipy.special import ellipk
    rows = []
    b, w, er = 0.4, 0.2, 4.0
    k = 1 / math.cosh(math.pi * w / (2 * b))
    exact = 30 * math.pi / math.sqrt(er) * ellipk(k * k) / ellipk(1 - k * k)
    sec = fs.Section(fs.axis([-w / 2, w / 2, -2, 2], -2, 2), fs.axis([0, b / 2, b], 0, b))
    sec.cond[0, :] = sec.cond[-1, :] = -1
    sec.cond[0, 0] = sec.cond[-1, 0] = sec.cond[0, -1] = sec.cond[-1, -1] = 0
    sec.set_eps(lambda X, Y: np.full_like(X, er))
    sec.add_conductor(1, lambda X, Y: (np.abs(Y - b / 2) < 1e-9) & (np.abs(X) <= w / 2 + 1e-9))
    rows.append(('stripline b 0.4, w 0.2, t 0, er 4 (Cohn, exact)', exact, fs.lines(sec, [1])['Z0']))
    for wh in (1.0, 2.0):
        ref, _ = hj(wh * 0.1, 0.1, 0.0, 4.1)
        z = solve(w=wh * 0.1, s=0, h=0.1, t=1e-4, er=4.1, pair=False, mask=False, etch=0.0)['Z0']
        rows.append(('microstrip w/h %.0f, t 0, er 4.1 (Hammerstad-Jensen)' % wh, ref, z))
    return rows


def usb_routed_length():
    path = os.path.join(V1, 'usb', 'layercam-usb.kicad_pcb')
    if not os.path.exists(path):
        return None
    tot = {}
    for m in re.finditer(r'\(segment\s+\(start ([\d.-]+) ([\d.-]+)\)\s+\(end ([\d.-]+) ([\d.-]+)\)\s+\(width ([\d.]+)\)'
                         r'\s+\(layer "[^"]+"\)\s+\(net "([^"]+)"', open(path).read()):
        x1, y1, x2, y2, wd, net = m.groups()
        if net in ('USB_DP', 'USB_DM'):
            tot[net] = tot.get(net, 0) + math.hypot(float(x2) - float(x1), float(y2) - float(y1))
    return tot or None


# ---------------------------------------------------------------- the analysis
def pair_rows(w_, name, w, s, lays, board='main'):
    """Check one pair rule on its layers; return its row values."""
    tgt, tol = TARGET[name if name != 'USB board' else 'USB']
    lo, hi = tgt * (1 - tol), tgt * (1 + tol)
    fill = FILL_MAIN if board == 'main' else FILL_USB
    res = []
    for lay in lays:
        bare = zdiff(w, s, lay) if board == 'main' else None
        fl = zdiff(w, s, lay, fill)
        nar = zdiff(w, s, lay, fill, dw=-ETCH_TOL)
        wid = zdiff(w, s, lay, fill, dw=+ETCH_TOL)
        nomask = zdiff(w, s, lay, fill if board != 'main' else None, mask=False)
        zs = [z for z in (bare, fl, nar, wid) if z is not None]
        ok = all(lo <= z <= hi for z in zs)
        w_('| %s | %s | %.3f / %.3f | %s | %.1f | %.1f / %.1f | %.1f | %.0f +-%.0f %% | %s |'
           % (name, lay if lay in OUTER else 'F (2-layer)', w, s, '%.1f' % bare if bare else '-', fl, nar, wid, nomask,
              tgt, tol * 100, 'PASS' if ok else 'FAIL'))
        check(ok, '%s %.3f / %.3f on %s: %.1f-%.1f ohm (bare, beside the fill, +-%.3f mm etch) inside %.0f-%.0f'
              % (name, w, s, lay if lay in OUTER else 'the USB board', min(zs), max(zs), ETCH_TOL, lo, hi))
        check(s >= GAP_MIN[board] - 1e-9, '%s gap %.3f mm at or above the %s board\'s %.3f mm clearance'
              % (name, s, board, GAP_MIN[board]))
        res.append((lay, ok, zs))
    return res


def suggest_pair(name, w0, s0, lays, board='main'):
    """The smallest change from (w0, s0) that passes on every layer it runs on."""
    tgt, tol = TARGET[name if name != 'USB board' else 'USB']
    lo, hi = tgt * (1 - tol), tgt * (1 + tol)
    fill = FILL_MAIN if board == 'main' else FILL_USB
    best = None
    for w in np.round(np.arange(0.10, 0.36, 0.01), 3):
        for s in (GAP_MIN[board], 0.15, 0.175, 0.20):
            zs = []
            for lay in lays:
                zs += [zdiff(w, s, lay, fill), zdiff(w, s, lay, fill, dw=-ETCH_TOL), zdiff(w, s, lay, fill, dw=ETCH_TOL)]
                if board == 'main':
                    zs.append(zdiff(w, s, lay))
            if all(lo <= z <= hi for z in zs):
                d = abs(w - w0) + abs(s - s0)
                if best is None or d < best[0]:
                    best = (d, w, s, min(zs), max(zs))
    return best


def run():
    L = []
    w_ = L.append
    w_('# LayerCam v1: impedance of the controlled tracks (PCBWay)\n')
    w_('Computed by `sim/impedance.py` (field solver `sim/fieldsolve.py`) from what the boards are built with: '
       'stackups from `src/pcb.py` (STACKUP6, STACKUP2), pair rules from `src/board.py` (DIFF, RF_W), clearances '
       'from `src/pcb.py` and `src/stitch.py`.\n')

    # ------------------------------------------------ stackup
    w_('## Stackup (src/pcb.py STACKUP6, PCBWay\'s regular 6-layer 1.6 mm build No. 1)\n')
    w_('| layer | type | thickness (mm) | Dk |\n|---|---|---|---|')
    for x in ST6:
        if x['type'] in ('copper', 'prepreg', 'core'):
            w_('| %s | %s%s | %.4f | %s |' % (x['name'], x['type'], ' ' + x['material'] if x['material'] else '', x['t'],
                                           '%.2f' % x['er'] if x['er'] else '-'))
    w_('')
    mism = []
    for name, t, er in PCBWAY_NO1:
        try:
            x = layer(name)
        except IndexError:
            mism.append(name + ' missing')
            continue
        if abs(x['t'] - t) > 1e-3 or (er and abs((x['er'] or 0) - er) > 1e-3):
            mism.append('%s %.4f mm Dk %s (PCBWay: %.4f mm Dk %s)' % (name, x['t'], x['er'], t, er))
    check(not mism, 'src/pcb.py STACKUP6 matches PCBWay\'s published build No. 1' +
          ('' if not mism else ': ' + '; '.join(mism)))
    w_('Outer layers: F.Cu over %.4f mm (Dk %.2f) to In1, B.Cu over %.4f mm (Dk %.2f) to In4; copper %.3f mm. '
       'Solder mask (PCBWay publishes none, ASSUMED): %.0f um on copper, %.0f um on laminate, Dk %.1f. Track '
       'etch: top %.1f um narrower a side (ASSUMED). USB board: 2 layers, %.2f mm board, core %.2f mm, Dk %.1f, '
       'copper %.3f mm (STACKUP2). Ground fill: %.3f mm from other nets on the main board, %.3f mm on the USB '
       'board (CLEAR + %.2f, stitch.py).\n'
       % (OUTER['F']['h'], OUTER['F']['er'], OUTER['B']['h'], OUTER['B']['er'], OUTER['F']['t'], MASK['on_cu'] * 1e3,
          MASK['on_sub'] * 1e3, MASK['er'], ETCH * 1e3, ST2['board_t'], ST2['core'], ST2['er'], ST2['cu'], FILL_MAIN,
          FILL_USB, FILL_EXTRA))

    # ------------------------------------------------ solver checks
    w_('## Field solver checked against exact results\n')
    w_('| case | reference (ohm) | solver (ohm) | error |\n|---|---|---|---|')
    for name, ref, z in validate():
        err = (z - ref) / ref
        w_('| %s | %.2f | %.2f | %+.2f %% |' % (name, ref, z, 100 * err))
        check(abs(err) < 0.015, 'solver within 1.5 %% of %s (%+.2f %%)' % (name.split(' (')[0], 100 * err))
    w_('')

    # ------------------------------------------------ pairs
    w_('## Differential pairs\n')
    w_('*Bare*: the pair alone over its plane; *fill*: with the ground fill %.3f mm beside it (stitch.py; where '
       'MIPI lanes run side by side there is no fill between them, so the bare figure applies there). The etch '
       'columns move the track %.3f mm narrower / wider at the same pitch, with the fill. Zdiff = 2 Zodd.\n'
       % (FILL_MAIN, ETCH_TOL))
    w_('| pair | layer | w / gap (mm) | bare | fill | narrower / wider | no mask | target | |')
    w_('|---|---|---|---|---|---|---|---|---|')
    pairs = {'MIPI': ('F',), 'USB': ('F', 'B')}
    out = {}
    for name, lays in pairs.items():
        nets, w, s = DIFF['main'][name]
        res = pair_rows(w_, name, w, s, lays)
        out[name] = (w, s, res)
    nets, wu, su = DIFF['usb']['USB']
    out['USB board'] = (wu, su, pair_rows(w_, 'USB board', wu, su, ('usb',), board='usb'))
    w_('')
    cf = {n: closed_forms(DIFF['main'][n][1], DIFF['main'][n][2], OUTER['F']['h'], OUTER['F']['t'], OUTER['F']['er'])
          for n in pairs}
    w_('Closed forms for the bare pairs on F (no mask, no fill; IPC-2141 reads high for w/h near 1): ' +
       '; '.join('%s IPC-2141 %.1f, Hammerstad-Jensen %.1f ohm' % (n, c['ipc_zd'], c['hj_zd']) for n, c in cf.items())
       + '.\n')
    sugg = {}
    for name, (w, s, res) in out.items():
        if not all(ok for lay, ok, zs in res):
            board = 'usb' if name == 'USB board' else 'main'
            lays = ('usb',) if board == 'usb' else pairs[name]
            sugg[name] = suggest_pair(name, w, s, lays, board)
    for name, sg in sugg.items():
        if sg:
            w_('- **%s: change to %.3f / %.3f mm** (%.1f-%.1f ohm on every layer it uses, across fill and etch).'
               % (name, sg[1], sg[2], sg[3], sg[4]))
        else:
            w_('- **%s**: no width / gap in the searched range passes; needs a different reference.' % name)
    if sugg:
        w_('')

    # ------------------------------------------------ RF
    w_('## Antenna feed (RF netclass, 50 ohm single-ended)\n')
    w_('ANT_FEED / ANT: one %.2f mm track on B.Cu over In4 (board.RF_W), about 5.5 mm from the AP6256\'s antenna pin '
       'through the 0402 pi match to the U.FL, with the B ground fill %.3f mm away on both sides. Reported as a plain '
       'microstrip and as the coplanar line with ground the fill makes (the one that is built).\n'
       % (RF_W, FILL_MAIN))
    tgt, tol = TARGET['RF']
    lo, hi = tgt * (1 - tol), tgt * (1 + tol)
    zm = z0(RF_W, 'B')
    zc = z0(RF_W, 'B', FILL_MAIN)
    zn = z0(RF_W, 'B', FILL_MAIN, dw=-ETCH_TOL)
    zw = z0(RF_W, 'B', FILL_MAIN, dw=ETCH_TOL)
    znm = z0(RF_W, 'B', FILL_MAIN, mask=False)
    hjz, _ = hj(RF_W, OUTER['B']['h'], OUTER['B']['t'], OUTER['B']['er'])
    w_('| width (mm) | microstrip (no fill) | with the fill (CPWG) | narrower / wider | no mask | Hammerstad-Jensen '
       '(bare microstrip) | target |\n|---|---|---|---|---|---|---|')
    w_('| %.3f | %.1f | %.1f | %.1f / %.1f | %.1f | %.1f | 50 +-10 %% |' % (RF_W, zm, zc, zn, zw, znm, hjz))
    rf_ok = all(lo <= z <= hi for z in (zc, zn, zw))
    check(rf_ok, 'RF %.3f mm on B with the fill: %.1f ohm (%.1f-%.1f across the etch) inside %.0f-%.0f'
          % (RF_W, zc, min(zn, zw), max(zn, zw), lo, hi))
    check(lo <= zm <= hi, 'RF %.3f mm on B as a plain microstrip (where the fill is cut back): %.1f ohm' % (RF_W, zm),
          warn=True)
    rf_best = None
    for w in np.round(np.arange(0.10, 0.40, 0.005), 3):
        z = z0(w, 'B', FILL_MAIN)
        if rf_best is None or abs(z - tgt) < abs(rf_best[1] - tgt):
            rf_best = (w, z)
    zbm = z0(rf_best[0], 'B')
    w_('')
    w_('50.0 ohm with the fill is reached at **%.3f mm** (%.1f ohm; %.1f ohm as a plain microstrip). %s\n'
       % (rf_best[0], rf_best[1], zbm, 'The current %.2f mm is inside +-10 %%: no change needed.' % RF_W if rf_ok
          else '**Change RF_W to %.3f mm.**' % rf_best[0]))
    elen = 5.5 * math.sqrt(solve(w=RF_W, s=0, h=OUTER['B']['h'], t=OUTER['B']['t'], er=OUTER['B']['er'], pair=False,
                                 gnd_gap=FILL_MAIN)['eeff']) / (299.792458 / 5.5)
    w_('At 5.5 GHz the 5.5 mm run is %.2f wavelengths long, so its impedance matters (at 2.4 GHz %.2f).\n'
       % (elen, elen * 2.45 / 5.5))

    # ------------------------------------------------ USB board length
    ln = usb_routed_length()
    if ln:
        w_('The routed USB board\'s pair: D+ %.1f mm, D- %.1f mm of track (including the joins between the '
           'receptacle\'s two contact rows), about %.0f ps: close to the lumped limit for USB 2.0\'s 500 ps edges; '
           'the 6-wire SH cable after it is uncontrolled anyway.\n'
           % (ln.get('USB_DP', 0), ln.get('USB_DM', 0), max(ln.values()) * 5.7))
    return L, out, sugg, (RF_W, zm, zc, zn, zw, rf_ok, rf_best)


def main():
    L, out, sugg, rf = run()
    w = L.append
    w('## Ordering\n')
    w('Order with PCBWay\'s impedance control: **100 ohm differential on L1 (F.Cu) for the MIPI class, 90 ohm '
      'differential on L1 / L6 (F.Cu, B.Cu) for USB, 50 ohm single-ended on L6 (B.Cu) for the antenna feed**, '
      'all referenced to the adjacent ground plane (In1 / In4), +-10 %. Give them the widths below and let them '
      'trim to their process; ask for their stackup report and the mask they use. The USB board (2-layer, 1.2 mm) '
      'needs no impedance control (its pair is short and the fill sets it). Via-in-pad under the RV1106 must be '
      'ordered as resin-filled and capped.\n')
    w('## Checks\n')
    for s_, what in checks:
        w('- %s %s' % (s_, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    w('## Verdict\n')
    for name, (wd, sd, res) in out.items():
        ok = all(r[1] for r in res)
        zs = [z for r in res for z in r[2]]
        sg = sugg.get(name)
        w('- **%s %.3f / %.3f mm: %s** (%.1f-%.1f ohm)%s' % (name, wd, sd, 'PASS' if ok else 'FAIL', min(zs), max(zs),
                                                            '' if ok or not sg else
                                                            '; change to %.3f / %.3f mm' % (sg[1], sg[2])))
    rw, zm, zc, zn, zw, rf_ok, rf_best = rf
    w('- **RF %.3f mm on B: %s** (%.1f ohm with the fill, %.1f-%.1f across the etch; %.1f ohm as a plain '
      'microstrip)%s' % (rw, 'PASS' if rf_ok else 'FAIL', zc, min(zn, zw), max(zn, zw), zm,
                         '' if rf_ok else '; change to %.3f mm (%.1f ohm)' % rf_best))
    w('- JLCPCB (the earlier fab, 0.0994 mm 3313 prepreg) is no longer modelled.')
    w('')
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
