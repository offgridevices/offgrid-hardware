# -*- coding: utf-8 -*-
"""Operating points, environments and the part-to-heat mapping of each board.

A case name is  <load>-<ambient>-<air>-<sun>,  e.g.  full-50C-wash-sun:
  load     idle hover cruise full abuse stall demo (steady), or a transient
           profile: punch full60 full30 abuse2 stall2
  ambient  25C, 50C, ... (any number followed by C)
  air      still (natural convection only) | wash (prop wash, speed per load) |
           halfwash (the same with every forced-convection h halved: the pessimistic case)
  sun      sun (1000 W/m2 on the top) | shade
Omitted fields default to 25C-wash-shade.  Sets: desert, matrix, quick, tosh.
Every number below is explained, with its source, in README.md.
"""
import csv
import math
import os
import re

from thermal import Drive

V_BATT = 16.8          # V, a full 4S pack (4.2 V/cell): worst case for switching and LDO losses (built-in model)
F_PWM = 24e3           # Hz, AM32 default PWM frequency
T_RF = 20e-9           # s, tr + tf of TPN2R304PL at 4.7 ohm gate resistance (datasheet 7.8 + 12.2 ns)
Q_OSS = 27e-9          # C, TPN2R304PL output charge at 20 V
T_DEAD = 1.155e-6      # s per edge: AM32 DEAD_TIME 60 at 64 MHz (0.94 us) + DRV8300D's 215 ns (sim/halfbridge)
V_F = 0.8              # V, body diode during dead time
R25_TPN = 2.3e-3       # ohm, TPN2R304PL RDS(on) max at VGS = 10 V, 25 C
QG = 45e-9             # C, TPN2R304PL gate charge at ~11 V


def rds_norm(Tj):
    """RDS(on)(Tj)/RDS(on)(25 C), fit to Toshiba Fig. 8.9 (VGS = 10 V):
    1.8 mOhm at 25 C, 2.5 at 100 C, 3.4 at 175 C."""
    x = Tj - 25.0
    return 1.0 + 0.0047 * x + 1.0e-5 * x * x


# ---------------------------------------------------------------------------
#  Loads (per motor).  I = battery-side DC current per motor, D = PWM duty.
#  Phase current I_ph = I / D.  v = air speed over the board top (bottom gets
#  half: the frame plate shields it), v_wire = over the motor wires (they run
#  along the arms, under the props).  motor_rise = motor can over ambient.
# ---------------------------------------------------------------------------
LOADS = {
    'idle':   dict(I=0.0, D=0.0, v=0.0, v_wire=0.0, motor_rise=0, batt_rise=0,
                   desc='armed on the ground, motors stopped, electronics on'),
    'hover':  dict(I=3.5, D=0.35, v=2.5, v_wire=6.0, motor_rise=20, batt_rise=5, desc='hover, 3.5 A per motor'),
    'cruise': dict(I=7.0, D=0.55, v=6.0, v_wire=9.0, motor_rise=35, batt_rise=8, desc='cruise, 7 A per motor'),
    'full':   dict(I=15.0, D=1.0, v=8.0, v_wire=12.0, motor_rise=55, batt_rise=10, desc='full throttle, 15 A per motor'),
    'abuse4': dict(I=28.0, D=1.0, v=8.0, v_wire=12.0, motor_rise=60, batt_rise=10,
                   desc='all four motors at 28 A'),
    # a crash with one prop jammed: motor 1's rotor locked, 25 A phase current at
    # ~30 % duty through one high side and two low sides, the other three at hover
    'abuse':  dict(I=7.5, D=0.3, v=2.5, v_wire=6.0, motor_rise=20, batt_rise=5, locked=1, others='hover',
                   desc='motor 1 stalled (prop jammed), 25 A phase, others hover'),
    'stall':  dict(I=9.0, D=0.3, v=6.0, v_wire=9.0, motor_rise=35, batt_rise=8, locked=1, others='cruise',
                   desc='motor 1 rotor locked, 30 A phase through one FET pair (others cruise)'),
    'demo':   dict(I=0.0, D=0.0, v=6.0, v_wire=9.0, motor_rise=35, batt_rise=8, fixed_fet_W=2.0,
                   desc='demo: 2 W per FET package only (no copper or wire I2R), motors at cruise temperature'),
    'tosh':   dict(P=2.67, v=0.0, desc="Toshiba Note 3 test: 2.67 W (PD), still air"),
    'toshb':  dict(P=0.63, v=0.0, desc="Toshiba Note 4 test: 0.63 W (PD), still air"),
    'tosh1':  dict(P=1.0, v=0.0, desc="Toshiba board at 1 W, still air"),
}

TRANSIENTS = {
    'punch':  dict(init='hover', segments=[('hover', 10), ('full', 3)] * 8 + [('hover', 10)], dt=0.25,
                   desc='steady hover, then 8 x (10 s hover + 3 s full throttle)'),
    'full60': dict(init='hover', segments=[('full', 60), ('hover', 30)], dt=0.2,
                   desc='steady hover, 60 s full throttle (motor maker\'s limit), 30 s hover'),
    'full30': dict(init='hover', segments=[('full', 30), ('hover', 20)], dt=0.2,
                   desc='steady hover, 30 s full throttle, 20 s hover'),
    'abuse2': dict(init='cruise', segments=[('abuse', 2), ('hover', 10)], dt=0.05,
                   desc='steady cruise, then motor 1 stalled at 25 A for 2 s (others hover), 10 s hover'),
    'abuse42': dict(init='cruise', segments=[('abuse4', 2), ('cruise', 10)], dt=0.05,
                    desc='steady cruise, 2 s at 28 A per motor (all four), 10 s cruise'),
    'stall2': dict(init='cruise', segments=[('stall', 2), ('cruise', 10)], dt=0.05,
                   desc='steady cruise, motor 1 locked for 2 s at 30 A, 10 s cruise'),
}

SETS = {
    'desert': ['idle-50C-still-sun', 'hover-50C-wash-sun', 'cruise-50C-wash-sun', 'full-50C-wash-sun',
               'full-50C-halfwash-sun', 'full60-50C-wash-sun', 'full60-50C-halfwash-sun', 'punch-50C-wash-sun',
               'abuse2-50C-wash-sun', 'abuse2-50C-halfwash-sun'],
    'report': ['%s-%s-%s-%s' % (l, a, w, s) for l in ('hover', 'cruise', 'full', 'full60', 'abuse2')
               for a in ('25C', '50C') for w in ('wash', 'halfwash') for s in ('shade', 'sun')],
    'quick': ['hover-25C-wash-shade', 'full-50C-wash-sun'],
    'matrix': ['%s-%s-%s-%s' % (l, a, w, s) for l in ('idle', 'hover', 'cruise', 'full') for a in ('25C', '50C')
               for w in ('still', 'wash') for s in ('shade', 'sun')],
    'tosh': ['tosh-25C-still-shade', 'tosh1-25C-still-shade'],
    'toshb': ['toshb-25C-still-shade'],
    'ridge': ['demo-25C-wash-shade', 'demo-25C-still-shade', 'demo-50C-wash-sun'],
}

PROFILES = ('aio3', 'ridge3', 'tosh', 'generic')


# ---------------------------------------------------------------------------
#  FET loss table from the switching study (../losses.csv)
# ---------------------------------------------------------------------------
class Losses:
    """Per-motor (six FETs) power-stage loss vs phase current and junction
    temperature, from sim/halfbridge/run.py (../losses.csv).

    Long format (what the switching study writes): one row per (fpwm_hz,
    tj_c, phase_current_a) with pcond_w, psw_w, pdead_w, ptotal_w.  The
    components are spread over the six FETs by who carries them (fet_coeffs),
    each FET at its own junction temperature.
    Wide format also accepted: a current column and one total-loss column per
    junction temperature (header carries the number: P_25C, loss_100C ...);
    the total is then spread with the built-in model's shares.
    Linear in current and temperature; beyond the last current, conduction
    grows as I^2 and switching / dead time as I; beyond the last temperature,
    linear extrapolation."""

    COMPS = ('pcond_w', 'psw_w', 'pdead_w')

    def __init__(self, path, fpwm=F_PWM):
        self.path = path if path and os.path.exists(path) else None
        self.ok = False
        if not self.path:
            return
        lines = [l for l in open(self.path) if l.strip() and not l.lstrip().startswith('#')]
        rows = list(csv.reader(lines))
        hdr = [h.strip().lower() for h in rows[0]]
        data = [[float(x) for x in r] for r in rows[1:] if r and r[0].strip()]
        col = {h: k for k, h in enumerate(hdr)}
        if 'tj_c' in col and 'phase_current_a' in col:
            if 'fpwm_hz' in col:
                fs = sorted({r[col['fpwm_hz']] for r in data})
                self.fpwm = min(fs, key=lambda f: abs(f - fpwm))
                data = [r for r in data if r[col['fpwm_hz']] == self.fpwm]
            else:
                self.fpwm = fpwm
            self.T = sorted({r[col['tj_c']] for r in data})
            self.I = sorted({r[col['phase_current_a']] for r in data})
            names = [c for c in self.COMPS if c in col] or ['ptotal_w']
            self.tab = {c: [[0.0] * len(self.I) for _ in self.T] for c in names + ['ptotal_w']}
            for r in data:
                iT, iI = self.T.index(r[col['tj_c']]), self.I.index(r[col['phase_current_a']])
                for c in self.tab:
                    if c in col:
                        self.tab[c][iT][iI] = r[col[c]]
            self.split = all(c in col for c in self.COMPS)
            self.phase = True
        else:
            ic = [k for k, h in enumerate(hdr) if 'current' in h or h in ('i', 'i_a')]
            if not ic:
                raise SystemExit('losses.csv: no current column in %s' % hdr)
            ic = ic[0]
            self.phase = 'phase' in hdr[ic]
            cols = []
            for k, h in enumerate(hdr):
                m = re.search(r'(-?\d+(?:\.\d+)?)', h)
                if k != ic and m:
                    cols.append((float(m.group(1)), k))
            if not cols:
                raise SystemExit('losses.csv: no per-temperature loss columns in %s' % hdr)
            cols.sort()
            self.I = [r[ic] for r in data]
            self.T = [t for t, _ in cols]
            self.tab = {'ptotal_w': [[r[k] for r in data] for _, k in cols]}
            self.split = False
            self.fpwm = None
        self.ok = True

    def describe(self):
        if not self.ok:
            return 'built-in model (no losses.csv)'
        return '%s (%s%d %s currents to %g A, Tj %s C%s)' % (
            os.path.relpath(self.path), '%g kHz, ' % (self.fpwm / 1e3) if self.fpwm else '', len(self.I),
            'phase' if self.phase else 'battery', self.I[-1], '/'.join('%g' % t for t in self.T),
            ', conduction/switching/dead-time split' if self.split else '')

    def _at_I(self, row, I, quad):
        Is = self.I
        if I >= Is[-1]:
            return row[-1] * (I / Is[-1]) ** (2 if quad else 1)
        for i in range(len(Is) - 1):
            if Is[i] <= I <= Is[i + 1]:
                return row[i] + (row[i + 1] - row[i]) * (I - Is[i]) / (Is[i + 1] - Is[i])
        return row[0]

    def get(self, comp, I, Tj):
        rows = self.tab[comp]
        ps = [self._at_I(r, I, comp == 'pcond_w' or not self.split) for r in rows]
        if len(ps) == 1:
            return ps[0]
        Ts = self.T
        k = 0 if Tj < Ts[0] else (len(Ts) - 2 if Tj >= Ts[-1] else max(i for i in range(len(Ts) - 1) if Ts[i] <= Tj))
        return max(0.0, ps[k] + (ps[k + 1] - ps[k]) * (Tj - Ts[k]) / (Ts[k + 1] - Ts[k]))


def fet_coeffs(role, D, locked_phase=None, phase=None):
    """Shares of one FET in a 6-step complementary-PWM bridge:
    (conduction: fraction of time it carries I_ph, summing to 2 over the six
    FETs as two always conduct; switching share; dead-time share, each
    summing to 1).  Rotating: each phase is the PWM phase 1/3 of the time
    (high side on for D, low side for 1-D: the high side takes the hard
    switching, the low side's body diode the dead time), the return phase
    1/3 (low side on), floating 1/3.  Locked rotor: A PWM, B return, C off.
    PWM is assumed to switch even at full throttle (as the loss study does)."""
    pwm = 1.0 if D > 0 else 0.0
    if locked_phase is None:
        return (D / 3, pwm / 3, 0) if role == 'H' else ((2 - D) / 3, 0, pwm / 3)
    if phase == 'A':
        return (D, pwm, 0) if role == 'H' else (1 - D, 0, pwm)
    if phase == 'B':
        return (0, 0, 0) if role == 'H' else (1, 0, 0)
    return (0, 0, 0)


def fet_model(c, Iph, Tj, R25=R25_TPN):
    """Built-in loss model (used when there is no losses.csv), one FET."""
    cc, cs, cd = c
    return (cc * Iph ** 2 * R25 * rds_norm(Tj) +
            cs * (0.5 * V_BATT * Iph * T_RF * F_PWM + Q_OSS * V_BATT * F_PWM) +
            cd * 2 * T_DEAD * F_PWM * V_F * Iph)


def fet_power_fn(role, phase, ld, losses, locked, R25=R25_TPN):
    D = ld['D']
    I = ld['I']
    Iph = I / D if D > 0 else 0.0
    if Iph == 0:
        return 0.0
    lp = 'A' if locked else None
    c = fet_coeffs(role, D, lp, phase)
    if not losses.ok:
        return lambda Tj: fet_model(c, Iph, Tj, R25)
    Icsv = Iph if losses.phase else I
    if losses.split:
        cc, cs, cd = c
        return lambda Tj: (cc / 2 * losses.get('pcond_w', Icsv, Tj) + cs * losses.get('psw_w', Icsv, Tj) +
                           cd * losses.get('pdead_w', Icsv, Tj))
    allc = [fet_coeffs(r, D, lp, p) for p in 'ABC' for r in 'HL']

    def f(Tj):
        tot = sum(fet_model(cc, Iph, Tj, R25) for cc in allc)
        return fet_model(c, Iph, Tj, R25) * losses.get('ptotal_w', Icsv, Tj) / tot
    return f


# ---------------------------------------------------------------------------
#  Board profiles: which parts make heat, which pads carry wires
# ---------------------------------------------------------------------------
def detect(g):
    refs = {f['ref']: f for f in g.fps}
    if 'Q1AH' in refs:
        return 'aio3'
    if 'Q1A' in refs and 'AON7934' in refs['Q1A']['value']:
        return 'ridge3'
    if 'Q1' in refs and 'TPN2R304' in refs['Q1']['value'] and len(refs) <= 3:
        return 'tosh'
    return 'generic'


X7R_LCSC = {'C437557', 'C307331'}       # GRM21BZ71H475KE15L 4.7 uF 50 V 0805, CL05B104KB54PNC 100 nF 50 V 0402
DRAIN = ['5', '6', '7', '8', '9']          # TSON Advance: 5-8 and the tab
SOURCE = ['1', '2', '3']
AWG26 = dict(d_cu_mm=0.405, ins_mm=0.25)   # silicone, ~0.9 mm OD
AWG18 = dict(d_cu_mm=1.024, ins_mm=0.40)   # silicone, ~1.8 mm OD


def topology(prof, g):
    refs = {f['ref'] for f in g.fps}
    E, W = [], []

    def el(name, ref, **kw):
        if ref in refs:
            E.append(dict(name=name, ref=ref, **kw))

    if prof == 'aio3':
        for n in range(1, 5):
            for ph in 'ABC':
                for r in 'HL':
                    el('Q%d%s%s' % (n, ph, r), 'Q%d%s%s' % (n, ph, r), pads=DRAIN, rth=1.43, cj=0.0035,
                       kind='fet', motor=n, phase=ph, role=r, tmax=175)
            el('R_S%d' % n, 'R_S%d' % n, pads=['1', '2'], kind='shunt', motor=n, tmax=170)
            el('U_E%d' % n, 'U_E%d' % n, pads=None, rth=30.0, kind='mcu', tmax=105, P=0.05)
            el('U_D%d' % n, 'U_D%d' % n, pads=['25'], rth=11.5, kind='ic', tmax=150, P='driver')
            el('U_A%d' % n, 'U_A%d' % n, pads=None, kind='ic', tmax=125, P=0.002)
            for ph in 'ABC':
                if 'P_M%d%s' % (n, ph) in refs:
                    W.append(dict(name='M%d%s' % (n, ph), ref='P_M%d%s' % (n, ph), pads=['1'], kind='motor',
                                  motor=n, phase=ph, length_mm=60, **AWG26))
        el('U_FC', 'U_FC', pads=None, rth=30.0, kind='ic', tmax=105, P=0.10)
        # BEC: sim/bec/results.txt, 2.2 MHz, 0.35 A, 17.4 V in: 264 mW typ / 303 mW worst in the IC, 21 mW in L
        el('U_BEC', 'U_BEC', pads=None, rth=26.1, kind='reg', tmax=150, P=0.30)
        el('L_BEC', 'L_BEC', pads=None, kind='reg', tmax=125, P=0.021)
        el('U_LDO', 'U_LDO', pads=None, rth=18.9, kind='reg', tmax=125, P=(5 - 3.3) * 0.12)
        el('U_LDOE', 'U_LDOE', pads=None, rth=18.9, kind='reg', tmax=125, P=(5 - 3.3) * 0.045)
        # gate-drive LDO: sim/gate_supply/results.txt, 24 kHz, max currents: 98.5 mW (+2.5 mW in the 10R)
        el('U_GVDD', 'U_GVDD', pads=None, rth=4.7, kind='reg', tmax=125, P='gvdd')
        el('U_IMU', 'U_IMU', pads=None, kind='ic', tmax=85, P=0.003)
        el('U_FLASH', 'U_FLASH', pads=None, kind='ic', tmax=85, P=0.01)
        el('Y1', 'Y1', pads=None, kind='mon', tmax=85, P=0.0)
        el('J_USB', 'J_USB', pads=None, kind='mon', tmax=85, P=0.0)
        for f in g.fps:
            if re.match(r'C\d', f['ref']):
                x7r = f.get('lcsc') in X7R_LCSC
                el(f['ref'], f['ref'], pads=None, kind='capX7R' if x7r else 'capX5R', tmax=125 if x7r else 85, P=0.0)
        for s in '+-':
            if 'P_BAT' + s in refs:
                W.append(dict(name='BAT' + s, ref='P_BAT' + s, pads=['1'], kind='battery', length_mm=80, **AWG18))
    elif prof == 'ridge3':
        for n in range(1, 5):
            for ph in 'ABC':
                ref = 'Q%d%s' % (n, ph)
                # AON7934 dual: high-side die on the VBAT tab (9), low-side on the switch-node tab (10)
                el(ref + '.HS', ref, pads=['9'], rth=4.0, cj=0.003, kind='fet', motor=n, phase=ph, role='H', tmax=150)
                el(ref + '.LS', ref, pads=['10'], rth=4.0, cj=0.003, kind='fet', motor=n, phase=ph, role='L', tmax=150)
                if 'P_M%d%s' % (n, ph) in refs:
                    W.append(dict(name='M%d%s' % (n, ph), ref='P_M%d%s' % (n, ph), pads=None, kind='motor',
                                  motor=n, phase=ph, length_mm=50, **AWG26))
            el('U_ESC%d' % n, 'U_ESC%d' % n, pads=None, rth=15.0, kind='ic', tmax=105, P=0.05)
            el('U_GD%d' % n, 'U_GD%d' % n, pads=None, rth=12.0, kind='ic', tmax=150, P=0.05)
        el('U_BUCK', 'U_BUCK', pads=None, rth=30.0, kind='reg', tmax=150, P=0.30)
        el('L1', 'L1', pads=None, kind='reg', tmax=125, P=0.05)
        for s in '+-':
            if 'P_BAT' + s in refs:
                W.append(dict(name='BAT' + s, ref='P_BAT' + s, pads=None, kind='battery', length_mm=80, **AWG18))
    elif prof == 'tosh':
        el('Q1', 'Q1', pads=DRAIN, rth=1.43, cj=0.0035, kind='fet', tmax=175)
    else:
        for f in g.fps:
            if f['ref'].startswith('Q') and f['pads']:
                el(f['ref'], f['ref'], pads=None, kind='fet', tmax=150)
    return dict(elements=E, wires=W, profile=prof)


def load_line(I, key='D'):
    """A load quantity (duty D, air speeds v / v_wire, motor_rise, batt_rise)
    at battery current I per motor: piecewise linear through idle (0 A), hover,
    cruise and full (the motor and airframe's load line)."""
    # below hover, a propeller load: phase current ~ rpm^2 ~ D^2, so battery
    # current ~ D^3: D and air speed ~ I^(1/3), motor heating ~ I_ph^2 ~ I^(4/3),
    # pack heating ~ I^2 (a straight line to zero would hold I_ph = I/D at the
    # hover value all the way down)
    Ih = LOADS['hover']['I']
    if I < Ih:
        expo = {'D': 1 / 3., 'v': 1 / 3., 'v_wire': 1 / 3., 'motor_rise': 4 / 3., 'batt_rise': 2.0}[key]
        return LOADS['hover'][key] * (max(I, 0.0) / Ih) ** expo
    pts = [(LOADS[k]['I'], LOADS[k][key]) for k in ('hover', 'cruise', 'full')]
    for (i0, d0), (i1, d1) in zip(pts, pts[1:]):
        if I <= i1:
            return d0 + (d1 - d0) * (I - i0) / (i1 - i0)
    return pts[-1][1]


def duty_for(I):
    return load_line(I, 'D')


def motor_ld(ld, n):
    """Load of motor n (1-4): ld itself, or with ld['scale'] (a per-motor
    current factor, e.g. an AM32 temperature derating) its current scaled and
    the duty taken from the load line."""
    if 'scale' not in ld:
        return ld
    I = ld['I'] * ld['scale'][n - 1]
    return dict(ld, I=I, D=duty_for(I), motor_rise=load_line(I, 'motor_rise'))


def joule_scenarios(prof, ld, refs):
    """Copper current distributions: list of (weight * I^2, injections at 1 A scale)."""
    out = []
    I, D = ld.get('I', 0.0), ld.get('D', 0.0)
    if I <= 0 or D <= 0:
        return out
    Iph = I / D
    locked = ld.get('locked')
    oth = LOADS[ld.get('others', 'cruise')]
    Ib = [motor_ld(ld, n)['I'] for n in range(1, 5)]
    Dn = [motor_ld(ld, n)['D'] for n in range(1, 5)]
    if locked:
        Ib = [I] + [oth['I']] * 3                    # locked motor draws D*I_ph = I from the pack
    Itot = sum(Ib)
    if prof == 'aio3':
        vb = [('P_BAT+', ['1'], 1.0)]
        gn = [('P_BAT-', ['1'], -1.0)]
        for n in range(1, 5):
            share = Ib[n - 1] / Itot
            if locked and n == 1:
                vb.append(('Q1AH', DRAIN, -share))
            else:
                vb += [('Q%d%sH' % (n, ph), DRAIN, -share / 3) for ph in 'ABC']
            gn.append(('R_S%d' % n, ['2'], share))
            src = [('R_S%d' % n, ['1'], 1.0)]
            if locked and n == 1:
                src += [('Q1AL', SOURCE, -(1 - D)), ('Q1BL', SOURCE, -D)]
            else:
                src += [('Q%d%sL' % (n, ph), SOURCE, -1 / 3.) for ph in 'ABC']
            out.append((Ib[n - 1] ** 2, src))
            for ph in 'ABC':
                if locked and n == 1:
                    cH, cL = {'A': (D, 1 - D), 'B': (0, 1), 'C': (0, 0)}[ph]
                    ip = Iph
                elif locked:
                    cH, cL = oth['D'] / 3, (2 - oth['D']) / 3
                    ip = oth['I'] / oth['D']
                else:
                    cH, cL = Dn[n - 1] / 3, (2 - Dn[n - 1]) / 3
                    ip = Ib[n - 1] / Dn[n - 1] if Dn[n - 1] > 0 else 0.0
                pm = ('P_M%d%s' % (n, ph), ['1'], 1.0)
                if cH:
                    out.append((cH * ip ** 2, [pm, ('Q%d%sH' % (n, ph), SOURCE, -1.0)]))
                if cL:
                    out.append((cL * ip ** 2, [pm, ('Q%d%sL' % (n, ph), DRAIN, -1.0)]))
        out.append((Itot ** 2, vb))
        out.append((Itot ** 2, gn))
    elif prof == 'ridge3':
        vb = [('P_BAT+', ['1'], 1.0)] + [('Q%d%s' % (n, ph), ['2', '3', '4', '9'], -1 / 12.) for n in range(1, 5) for ph in 'ABC']
        gn = [('P_BAT-', ['1'], -1.0)] + [('Q%d%s' % (n, ph), ['5', '6', '7'], 1 / 12.) for n in range(1, 5) for ph in 'ABC']
        out += [(Itot ** 2, vb), (Itot ** 2, gn)]
        for n in range(1, 5):
            for ph in 'ABC':
                out.append((2 / 3. * Iph ** 2, [('P_M%d%s' % (n, ph), ['1'], 1.0), ('Q%d%s' % (n, ph), ['10'], -1.0)]))
    return out


def drive_for(prof, topo, load, env, losses):
    ld = dict(LOADS[load]) if isinstance(load, str) else dict(load)
    load = ld.get('name', load) if not isinstance(load, str) else load
    if 'scale' in ld:      # derated: airflow and pack temperature follow the mean current
        Im = ld['I'] * sum(ld['scale']) / 4
        for key in ('v', 'v_wire', 'batt_rise'):
            ld[key] = load_line(Im, key)
    Ta = env['Ta']
    wash = env['air'] in ('wash', 'halfwash')
    v = ld.get('v', 0.0) if wash else 0.0
    power = {}
    I, D = ld.get('I', 0.0), ld.get('D', 0.0)
    locked = ld.get('locked')
    oth = LOADS[ld.get('others', 'cruise')]
    for e in topo['elements']:
        k = e.get('kind')
        if k == 'fet':
            if 'P' in ld:
                power[e['name']] = ld['P']
            elif 'fixed_fet_W' in ld:
                power[e['name']] = ld['fixed_fet_W'] / 2.0
            elif 'role' not in e:        # generic board: each FET a sixth of one motor's loss
                Iph = I / D if D > 0 else 0.0
                if losses.ok:
                    power[e['name']] = (lambda Tj, Iph=Iph: losses.get('ptotal_w', Iph, Tj) / 6) if Iph else 0.0
                else:
                    cs = [fet_coeffs(r, D) for r in 'HL'] if D > 0 else []
                    power[e['name']] = (lambda Tj, Iph=Iph, cs=cs: sum(fet_model(c, Iph, Tj) for c in cs) / 2) if Iph else 0.0
            elif locked and e.get('motor') != 1:
                power[e['name']] = fet_power_fn(e['role'], e['phase'], oth, losses, False)
            else:
                power[e['name']] = fet_power_fn(e['role'], e['phase'], motor_ld(ld, e['motor']), losses,
                                                locked and e.get('motor') == 1)
        elif k == 'shunt':
            Im = motor_ld(ld, e['motor'])['I'] if (not locked or e.get('motor') == 1) else oth['I']
            power[e['name']] = Im ** 2 * 0.5e-3
        else:
            p = e.get('P', 0.0)
            if p == 'driver':     # gate charge energy, mostly in the driver: 2 switching FETs x Qg x V x f, + 1 mA quiescent
                p = (2 * QG * 11 * F_PWM if D > 0 else 0.0) + 11 * 1e-3
            elif p == 'gvdd':     # motors running: the gate-supply study's 0.1 W; idle: drivers' quiescent only
                p = 0.10 if D > 0 else (V_BATT - 11) * 4e-3
            power[e['name']] = p
    wc, wf = {}, {}
    Ib = [motor_ld(ld, n)['I'] for n in range(1, 5)]
    if locked:
        Ib = [I] + [oth['I']] * 3
    for w in topo['wires']:
        if w['kind'] == 'motor':
            n = w['motor']
            if locked and n == 1:
                Irms = (I / D) if w['phase'] in 'AB' else 0.0
            elif locked:
                Irms = oth['I'] / oth['D'] * math.sqrt(2 / 3.)
            else:
                mn = motor_ld(ld, n)
                Irms = (mn['I'] / mn['D'] if mn['D'] > 0 else 0.0) * math.sqrt(2 / 3.)
            wc[w['name']] = Irms
            wf[w['name']] = Ta + motor_ld(ld, n).get('motor_rise', 0)
        else:
            wc[w['name']] = sum(Ib) + 0.15
            wf[w['name']] = Ta + ld.get('batt_rise', 0)
    refs = {f for f in [e['ref'] for e in topo['elements']]}
    js = joule_scenarios(prof, ld, refs) if prof in ('aio3', 'ridge3') else []
    return Drive(dict(Ta=Ta, v_top=v, v_bot=0.5 * v, v_wire=ld.get('v_wire', 0.0) if wash else 0.0,
                      turb=0.5 if env['air'] == 'halfwash' else 1.0,
                      solar=1000.0 if env['sun'] else 0.0, power=power, wire_current=wc, wire_far=wf,
                      joule=js, label=load))


def parse(name):
    toks = name.split('-')
    load = toks[0]
    env = dict(Ta=25.0, air='wash', sun=False)
    for t in toks[1:]:
        m = re.match(r'^(-?\d+(?:\.\d+)?)C$', t)
        if m:
            env['Ta'] = float(m.group(1))
        elif t in ('still', 'wash', 'halfwash'):
            env['air'] = t
        elif t in ('sun', 'shade'):
            env['sun'] = t == 'sun'
        else:
            raise SystemExit('unknown case token %r in %r' % (t, name))
    if load not in LOADS and load not in TRANSIENTS:
        raise SystemExit('unknown load %r (loads: %s; transients: %s)' % (load, ', '.join(LOADS), ', '.join(TRANSIENTS)))
    return load, env


def env_desc(env):
    return '%g C ambient, %s, %s' % (env['Ta'], {'wash': 'prop wash', 'halfwash': 'prop wash with h halved',
                                                 'still': 'still air'}[env['air']],
                                      'sun 1000 W/m2' if env['sun'] else 'shade')


def make_case(name, prof, topo, losses):
    load, env = parse(name)
    if load in TRANSIENTS:
        tr = TRANSIENTS[load]
        cache = {}

        def dv(l):
            if l not in cache:
                cache[l] = drive_for(prof, topo, l, env, losses)
            return cache[l]
        return dict(name=name, desc='%s; %s' % (tr['desc'], env_desc(env)), init=dv(tr['init']),
                    segments=[(dur, dv(l)) for l, dur in tr['segments']], dt=tr['dt'])
    return dict(name=name, desc='%s; %s' % (LOADS[load]['desc'], env_desc(env)),
                drive=drive_for(prof, topo, load, env, losses))


def expand(spec, prof):
    out = []
    for s in spec.split(','):
        s = s.strip()
        out += SETS.get(s, [s])
    return out


def group_powers(pw):
    grp = {}
    for k, v in pw.items():
        if re.match(r'Q\d', k):
            g = 'FETs'
        elif k.startswith('R_S'):
            g = 'shunts'
        elif k in ('copper I2R', 'wires I2R', 'sun'):
            g = k
        else:
            g = 'other parts'
        grp[g] = grp.get(g, 0.0) + v
    return grp


def describe():
    print(__doc__)
    print('loads:')
    for k, v in LOADS.items():
        print('  %-8s %s' % (k, v['desc']))
    print('transient profiles:')
    for k, v in TRANSIENTS.items():
        print('  %-8s %s' % (k, v['desc']))
    print('sets:')
    for k, v in SETS.items():
        print('  %-8s %s' % (k, ', '.join(v)))
