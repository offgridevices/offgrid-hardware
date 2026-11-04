# -*- coding: utf-8 -*-
"""LayerCam v1: the power chain worked through from the datasheets.

    tools/kd python3 sim/power_budget.py   writes sim/power.md, exits 1 on a FAIL
    (plain python3 works too: nothing here needs KiCad)

The divider resistors, the regulator, inductor and capacitor choices are
read from src/circuit.py and src/parts.py (built with circuit.build), so a
change there is re-checked by running this again.  The load currents are
the datasheet or measured figures below, each with its source; where no
source gives a number the figure is marked ASSUMED and the verdict says so.

thermal.py imports heat() from here: the heat each part makes in each
operating case.

Worst case means the corner that hurts: VREF and resistor tolerances at
their ends, inductance -20 %, the switching frequency at its datasheet
minimum, hot switch resistance, the IR LEDs' forward voltage at its spread.
"""
import math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(V1, 'src'))
import circuit, parts

OUT = os.path.join(HERE, 'power.md')

# ---------------------------------------------------------------- the circuit, read
COMPS = {b: circuit.build(b) for b in circuit.BOARDS}


def _val(code):
    """'R47K' -> 47e3, 'R6K2' -> 6.2e3, 'R1R' -> 1, 'R240R' -> 240."""
    v = parts.PARTS[code]['value']
    m = re.match(r'([\d.]+)\s*([kMR]?)', v.replace('R', 'R'))
    x = float(m.group(1))
    return x * {'k': 1e3, 'M': 1e6, 'R': 1.0, '': 1.0}[m.group(2)]


def divider(board, fb_net, out_net):
    """(top, bottom) resistances on a feedback node, from the netlist."""
    top = bot = None
    for c in COMPS[board]:
        if c.part.startswith('R') and fb_net in c.pins.values():
            other = [n for n in c.pins.values() if n != fb_net][0]
            if other == out_net:
                top = _val(c.part)
            elif other == 'GND':
                bot = _val(c.part)
    return top, bot


def caps_on(board, net):
    """[(part code, count)] of capacitors between net and ground."""
    out = {}
    for c in COMPS[board]:
        if c.ref.startswith('C') and c.part in parts.PARTS and sorted(c.pins.values()) == sorted([net, 'GND']):
            out[c.part] = out.get(c.part, 0) + 1
    return out


def part_of(board, ref):
    return [c.part for c in COMPS[board] if c.ref == ref][0]


def ind(ref):
    code = part_of('main', ref)
    d = parts.PARTS[code]['desc']
    L = float(re.search(r'([\d.]+) uH', d).group(1)) * 1e-6
    return code, L, INDUCTORS[code]


# ---------------------------------------------------------------- datasheet figures
# TI TLV62569 (SLVSDG1C): VFB 0.588/0.600/0.612 V; RDS(on) 100 / 60 mOhm; ILIM 3 A (DBV, typ);
# 2 A rated; 1.5 MHz typ (no min/max given: +-20 % assumed); thetaJB 41.2 C/W (DBV).
TLV = dict(vref=(0.588, 0.600, 0.612), rhs=0.100, rls=0.060, ilim=3.0, irated=2.0, fsw=1.5e6, fsw_min=1.2e6,
           tjmax=125, theta_jb=41.2, name='TLV62569')
# Everanalog EA3036C (Ver. 1.4): VREF 0.588/0.6/0.612; RDS(on) P 120 / N 110 mOhm; ILIM-P 1.8 A min;
# 1 A per channel (peak 1.2 A at 3.3 V, 1.5 A at <= 1.8 V with 1.5 uH); fsw 1.0/1.5/2.0 MHz; total < 6 W.
EA = dict(vref=(0.588, 0.600, 0.612), rhs=0.120, rls=0.110, ilim=1.8, irated=1.0, fsw=1.5e6, fsw_min=1.0e6,
          tjmax=125, name='EA3036C')
RTOL = 0.01                         # UNI-ROYAL 0402WGF: 1 %
RDS_HOT = 1.35                      # switch resistance at Tj ~ 100 C against 25 C (typical CMOS, ASSUMED)
T_SW = 4e-9                         # switching edge time, rise + fall (ASSUMED, small integrated buck)
L_TOL = 0.20                        # inductors +-20 % (parts list)
# Changjiang FPA252012D (JLCPCB catalogue, read 26 Oct 2026): rated (heating) / saturation current, DCR
INDUCTORS = {'L1U5': dict(irms=2.9, isat=3.6, dcr=0.060), 'L2U2': dict(irms=2.4, isat=3.0, dcr=0.084),
             'L4U7': dict(irms=1.6, isat=2.1, dcr=0.200)}
# MLCC DC bias: fraction of nominal left at a bias.  The parts are now Murata X6S / X7S (parts.py:
# GRM188C80J226ME15D 22u 6.3 V X6S 0603, GRM188C81A106MA73D 10u 10 V X6S 0603, GRM155C80J475MEAAD 4.7u 6.3 V
# X6S 0402, GRM155C71A105KE11D 1u 10 V X7S 0402).  Murata's SimSurfing curves could not be reached (403); these
# fractions are ASSUMED from typical high-CV X6S / X7S behaviour in these case sizes (to +-10 %).
DCBIAS = {'C22U': [(0, 1.0), (0.9, 0.85), (1.4, 0.74), (1.8, 0.65), (3.3, 0.40), (3.6, 0.36)],
          'C10U': [(0, 1.0), (0.9, 0.92), (1.4, 0.84), (1.8, 0.77), (3.3, 0.55), (5.0, 0.38), (5.25, 0.36)],
          'C1U': [(0, 1.0), (3.3, 0.78), (5.0, 0.65)], 'C4U7': [(0, 1.0), (1.0, 0.80)],
          'C100N': [(0, 1.0), (5.0, 0.90)]}
NOMINAL = {'C22U': 22e-6, 'C10U': 10e-6, 'C1U': 1e-6, 'C4U7': 4.7e-6, 'C100N': 0.1e-6}
X5R_HOT = 0.85                      # X6S / X7S lose up to 22 % at their 105 / 125 C; ~15 % near 100 C (ASSUMED)

# Supply: Prusa's camera port on the printer's mainboard: "Input: 5VDC 1 A" (Prusa product page for the
# Buddy3D camera); USB tolerance at the receptacle
VSYS = (4.75, 5.0, 5.25)
SOURCE_A = 1.0
CABLE_R = 0.06                      # USB board + SH cable + contacts, round trip, ohm (ASSUMED)

# ---------------------------------------------------------------- loads (A) per operating case
# RV1106G3: Luckfox Core1106 power reference V1.0 (measured, 25 C room): VDD_0V9 1210 mA max at 0.88 V,
# VCC_1V8 38.9 mA, VCC_3V3 94.4 mA, 5 V in 467 mA.  Typical streaming (ISP + H.264, NPU idle):
# ASSUMED 0.60 A on 0.9 V.  Hot: leakage ASSUMED +15 % on the core at Tj ~ 110 C.
# The DDR3L is inside the package; Rockchip gives no current: ASSUMED 0.12 A typical, 0.30 A max.
# AP6256: 1 A peak at VBAT 3.3 V (AMPAK datasheet); continuous TX ASSUMED 0.40 A, streaming average
# ASSUMED 0.12 A (a few Mbit/s up on 5 GHz: the radio transmits a few % of the time, receives the rest).
# SC3336 module: 3.3 V into its own LDOs; sensor ~ 150-200 mW class (SmartSens flyer gives none):
# ASSUMED 0.06 A typical, 0.08 A max.  W25N02KV: 25 / 35 mA read (typ / max, Winbond).
# IR-cut coil 20 ohm at 3.3 V through the DRV8837 (280 mOhm HS + LS): pulses of 100-500 ms.
# Snapshot mode (the product's requirement, coordinator 26 Oct 2026): Prusa Connect takes a still at most
# every 10 s and the timelapse one full-resolution frame per layer.  Modelled as: between shots the SC3336 in
# software standby (not streaming), the CPU at its lowest DVFS point with ISP / VENC / NPU clock-gated, Wi-Fi
# associated on 2.4 GHz in power-save; each shot wakes the sensor, settles exposure, grabs and JPEG-encodes a
# frame and uploads it: ACTIVE_S of the SHOT_S period at the streaming loads.  At night the IR LEDs light for
# LED_ON_S of each shot.  All currents below are ASSUMED (no published RV1106 idle figure was found; Luckfox
# publishes only the Core1106 maximum): idle core 0.18 A is ~15 % of that maximum (a Cortex-A7 at its lowest
# OPP plus always-on logic); DDR 0.05 A with little traffic; sensor standby 5 mA; Wi-Fi 2.4 GHz power-save with
# a ~0.8 Mbit/s average upload (one ~1 MB JPEG per 10 s) about 0.05 A average.
SHOT_S, ACTIVE_S, LED_ON_S = 10.0, 1.5, 2.0
_k = ACTIVE_S / SHOT_S


def _avg(idle, active):
    return idle * (1 - _k) + active * _k


CASES = {
    'snap_day': dict(desc='snapshot, day: one still every 10 s, idle between (REQUIREMENT CASE)',
                     v09=_avg(0.18, 0.60), ddr=_avg(0.05, 0.12), v18=0.03, soc33=0.04, nand=_avg(0.0, 0.02),
                     cam=_avg(0.005, 0.06), wifi=0.05, ircut=0.0, led=False),
    'snap_night': dict(desc='snapshot, night: the same, IR LEDs on for 2 s of each 10 s (REQUIREMENT CASE)',
                       v09=_avg(0.18, 0.60), ddr=_avg(0.05, 0.12), v18=0.03, soc33=0.04, nand=_avg(0.0, 0.02),
                       cam=_avg(0.005, 0.06), wifi=0.05, ircut=0.0, led=True, led_duty=LED_ON_S / SHOT_S),
    'snap_burst': dict(desc='snapshot, night, during a shot (seconds): streaming loads, Wi-Fi transmitting, LEDs on',
                       v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.02, cam=0.06, wifi=0.32, ircut=0.0, led=True),
    'day': dict(desc='live view, day: streaming 3 MP 30 fps, Wi-Fi average, IR LEDs off (reported only)',
                v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.005, cam=0.06, wifi=0.12, ircut=0.0, led=False),
    'night': dict(desc='live view, night: the same with the six IR LEDs on at 100 % (reported only)',
                  v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.005, cam=0.06, wifi=0.12, ircut=0.0, led=True),
    'worst': dict(desc='worst sustained (stress bound): SoC at the measured maximum +15 % hot leakage, DDR max, '
                       'Wi-Fi transmitting continuously, IR LEDs on at the high-current corner',
                  v09=1.21 * 1.15, ddr=0.30, v18=0.045, soc33=0.094, nand=0.035, cam=0.08, wifi=0.40, ircut=0.0,
                  led='max'),
    'peak': dict(desc='peak (milliseconds): worst plus a 1 A Wi-Fi burst and an IR-cut pulse',
                 v09=1.21 * 1.15, ddr=0.30, v18=0.045, soc33=0.094, nand=0.035, cam=0.08, wifi=1.0, ircut=None,
                 led='max'),
}
REQUIRED = ('snap_day', 'snap_night')
# LEDs: JNJ-LTJI0106W90 850 nm: VF 1.4 typ / 2.1 max at 100 mA, 25 C (datasheet); at ~55 mA about 0.1 V
# less (typical 850 nm AlGaAs curve, ASSUMED); -1.5 mV/K (typical, ASSUMED); IF 100 mA max, Tj 115 C max.
# Radiant power 40 mW at 100 mA typ: about 40 % of that is light at these currents, the rest heat.
VF100_TYP, VF100_MAX, VF_LOW_I = 1.40, 2.10, 0.10
VF_TC = -1.5e-3
LED_IMAX, LED_TJMAX = 0.100, 115
LED_WALL_PLUG = 0.25                # fraction of the LED's electrical power that leaves as light (ASSUMED)
R_LED_TOL = 0.01
IRCUT_COIL = 20.0                   # ohm (Commonlands CLA219 note in circuit.py)
DRV_RDS = 0.28

checks = []


def check(ok, what, warn=False):
    checks.append(('PASS' if ok else ('WARN' if warn else 'FAIL'), what))


# ---------------------------------------------------------------- models
def vout_range(top, bot, vref):
    lo = vref[0] * (1 + top * (1 - RTOL) / (bot * (1 + RTOL)))
    nom = vref[1] * (1 + top / bot)
    hi = vref[2] * (1 + top * (1 + RTOL) / (bot * (1 - RTOL)))
    return lo, nom, hi


def eff_c(code, v, hot=True):
    pts = DCBIAS[code]
    for (v0, f0), (v1, f1) in zip(pts[:-1], pts[1:]):
        if v0 <= v <= v1:
            f = f0 + (f1 - f0) * (v - v0) / (v1 - v0)
            break
    else:
        f = pts[-1][1]
    return NOMINAL[code] * f * (X5R_HOT if hot and code != 'C100N' else 1.0)


def caps_eff(board, net, v):
    return sum(n * eff_c(code, v) for code, n in caps_on(board, net).items() if code in NOMINAL)


def buck(reg, vin, vout, iout, L, dcr, fsw=None, hot=True):
    """Losses of a synchronous buck at one operating point."""
    fsw = fsw or reg['fsw']
    k = RDS_HOT if hot else 1.0
    rhs, rls = reg['rhs'] * k, reg['rls'] * k
    d = min(1.0, (vout + iout * (rls + dcr)) / (vin - iout * (rhs - rls)))
    di = vout * (1 - d) / (L * fsw)
    irms = math.sqrt(iout ** 2 + di ** 2 / 12)
    p_cond = irms ** 2 * (d * rhs + (1 - d) * rls)
    p_sw = vin * iout * T_SW * fsw + 0.004            # edges + gate drive / quiescent (ASSUMED 4 mW)
    p_dcr = irms ** 2 * dcr * 1.16                     # copper at ~ +40 C
    pout = vout * iout
    pin = pout + p_cond + p_sw + p_dcr
    return dict(d=d, di=di, ipk=iout + di / 2, irms=irms, p_ic=p_cond + p_sw, p_l=p_dcr, pin=pin,
                eff=pout / pin if pin else 0, iin=pin / vin)


def led_string(vsys, r, vf):
    i = max(0.0, (vsys - 2 * vf) / r)
    return i


def string_resistor():
    """The part code of the ring's string resistors (VSYS to a string anode)."""
    return [c.part for c in COMPS['ring'] if c.ref.startswith('R') and 'VSYS' in c.pins.values()][0]


def led_cases(r=None):
    r = r or _val(string_resistor())
    vf_typ = VF100_TYP - VF_LOW_I
    vf_hot = vf_typ + VF_TC * (90 - 25)                # LED junction ~ 90 C (thermal.py)
    vf_max = VF100_MAX - VF_LOW_I
    out = {
        'nominal (5.0 V, typical VF, LEDs warm)': (VSYS[1] - CABLE_R * 0.4, r, vf_hot),
        'high (5.25 V, typical VF hot, R -1 %)': (VSYS[2], r * (1 - R_LED_TOL), vf_hot),
        'low (4.75 V, maximum VF cold, R +1 %)': (VSYS[0] - CABLE_R * 1.0, r * (1 + R_LED_TOL), vf_max),
    }
    res = {}
    for k, (v, rr, vf) in out.items():
        i = led_string(v, rr, vf)
        res[k] = dict(v=v, r=rr, vf=vf, i=i, pr=i * i * rr, pled=i * vf)
    return r, res


def rails():
    """Each rail's regulator, divider, inductor and the load's allowed range."""
    t09, b09 = divider('main', 'FB_0V9', 'VDD_0V9')
    t33, b33 = divider('main', 'FB_3V3', 'VCC_3V3')
    tdd, bdd = divider('main', 'FB_DDR', 'VCC_DDR')
    t18, b18 = divider('main', 'FB_1V8', 'VCC_1V8')
    twf, bwf = divider('main', 'FB_WIFI', 'VWIFI')
    return [
        dict(name='VDD_0V9', reg=TLV, ref='U2', L='L1', div=(t09, b09), load='v09',
             allowed=(0.85, 0.95), allowed_src='RV1106 CPU_DVDD 0.85-1.05, DVDD/PMU 0.81-0.95 (datasheet Rev 2.2 T3-2)'),
        dict(name='VCC_DDR', reg=EA, ref='U3 CH2', L='L3', div=(tdd, bdd), load='ddr',
             allowed=(1.283, 1.45), allowed_src='DDR3L VDDQ 1.283-1.45 (RV1106 T3-2)'),
        dict(name='VCC_1V8', reg=EA, ref='U3 CH3', L='L4', div=(t18, b18), load='v18',
             allowed=(1.62, 1.98), allowed_src='1.8 V domains 1.62-1.98'),
        dict(name='VCC_3V3', reg=EA, ref='U3 CH1', L='L2', div=(t33, b33), load='v33',
             allowed=(3.0, 3.465), allowed_src='VCCIO 3.0-3.465 (USB_AVDD to 3.6)'),
        dict(name='VWIFI', reg=TLV, ref='U4', L='L5', div=(twf, bwf), load='wifi',
             allowed=(3.2, 4.8), allowed_src='AP6256 VBAT 3.2-4.8 for full RF (datasheet note 1)'),
    ]


def loads(case):
    c = CASES[case]
    ircut = IRCUT_COIL and (3.3 / (IRCUT_COIL + DRV_RDS)) if c['ircut'] is None else c['ircut']
    v33 = c['soc33'] + c['nand'] + c['cam'] + 0.005 + 0.002 + 0.0013 + ircut   # + VDDIO, 32k osc, status LED
    return dict(v09=c['v09'], ddr=c['ddr'], v18=c['v18'] + 0.003, v33=v33, wifi=c['wifi'], ircut=ircut)


def solve_case(case, vin=VSYS[1]):
    """Regulator operating points, VSYS current and heat by part for one case."""
    ld = loads(case)
    out = {'rails': {}, 'heat': {}}
    for r in rails():
        lo, nom, hi = vout_range(*r['div'], r['reg']['vref'])
        code, L, ii = ind(r['L'])
        b = buck(r['reg'], vin, nom, ld[r['load']], L, ii['dcr'])
        out['rails'][r['name']] = dict(b, iout=ld[r['load']], vout=nom)
    rr = out['rails']
    h = out['heat']
    h['U2'] = rr['VDD_0V9']['p_ic']; h['L1'] = rr['VDD_0V9']['p_l']
    h['U4'] = rr['VWIFI']['p_ic']; h['L5'] = rr['VWIFI']['p_l']
    h['U3'] = rr['VCC_3V3']['p_ic'] + rr['VCC_DDR']['p_ic'] + rr['VCC_1V8']['p_ic']
    h['L2'] = rr['VCC_3V3']['p_l']; h['L3'] = rr['VCC_DDR']['p_l']; h['L4'] = rr['VCC_1V8']['p_l']
    c = CASES[case]
    h['U1'] = rr['VDD_0V9']['vout'] * c['v09'] + rr['VCC_DDR']['vout'] * c['ddr'] + 1.8 * c['v18'] + 3.33 * c['soc33']
    h['U5'] = 3.33 * c['nand']
    h['U6'] = rr['VWIFI']['vout'] * c['wifi']           # all of it heat (RF output small), incl. its own buck
    h['camera module'] = 3.33 * c['cam']
    h['U7'] = (ld['ircut'] ** 2) * DRV_RDS
    pin = sum(x['pin'] for x in rr.values())
    i_led = 0.0
    if c['led']:
        _, lc = led_cases()
        sel = lc['high (5.25 V, typical VF hot, R -1 %)'] if c['led'] == 'max' else lc['nominal (5.0 V, typical VF, LEDs warm)']
        duty = c.get('led_duty', 1.0)
        i_led = 3 * sel['i'] * duty
        h['ring resistors'] = 3 * sel['pr'] * duty
        h['ring LEDs'] = 6 * sel['i'] * sel['vf'] * (1 - LED_WALL_PLUG) * duty
        h['Q1'] = (3 * sel['i']) ** 2 * 0.05 * duty
        out['led_on'] = dict(sel, duty=duty, led_heat_each=sel['i'] * sel['vf'] * (1 - LED_WALL_PLUG))
        led_v = sel['v']
    else:
        led_v = vin
    i_reg = pin / vin
    out['i_vsys'] = i_reg + i_led + vin / 28e3
    out['i_led'] = i_led
    out['p_in'] = pin + i_led * led_v
    out['heat_total'] = sum(h.values()) + out['i_vsys'] ** 2 * CABLE_R
    h['cable, connectors'] = out['i_vsys'] ** 2 * CABLE_R
    return out


def led_on(case):
    """For thermal.py: while the LEDs are lit, each LED's heat and each resistor's power (W)."""
    lo = solve_case(case).get('led_on')
    return (lo['led_heat_each'], lo['pr']) if lo else (0.0, 0.0)


def heat(case):
    """For thermal.py: {part: W} in one operating case (at 5.0 V in; 'worst' at 5.25 V for the LEDs)."""
    return solve_case(case)['heat']


# ---------------------------------------------------------------- the write-up
def run():
    L = []
    w = L.append
    w('# LayerCam v1: power budget and regulators\n')
    w('Computed by `sim/power_budget.py` from `src/circuit.py` / `src/parts.py` (dividers, inductors, capacitors read from the '
      'netlist) and the datasheet figures in the script. Figures marked *assumed* have no datasheet behind them; '
      'they are listed under *Assumptions* with the reason for each value.\n')

    # ------------------------------------------------ loads
    w('## Loads per operating case\n')
    w('| case | 0.9 V | DDR 1.36 V | 1.8 V | 3.3 V | Wi-Fi 3.3 V | IR LEDs (VSYS) | VSYS current | VSYS power |')
    w('|---|---|---|---|---|---|---|---|---|')
    sol = {}
    for k in CASES:
        s = solve_case(k)
        sol[k] = s
        ld = loads(k)
        w('| %s | %.2f A | %.2f A | %.3f A | %.3f A | %.2f A | %.0f mA | **%.2f A** | %.2f W |'
          % (CASES[k]['desc'], ld['v09'], ld['ddr'], ld['v18'], ld['v33'], ld['wifi'], s['i_led'] * 1e3,
             s['i_vsys'], s['p_in']))
    w('')
    w('VSYS current at 5.0 V in, regulator losses from the buck model below (switch and inductor resistance hot, '
      '4 ns edges); the LED strings straight from VSYS.\n')

    # ------------------------------------------------ the source
    w('## The 5 V source\n')
    w('Prusa\'s own camera on this port is rated "5 VDC 1 A" (Prusa product page): the printer\'s mainboard feeds it '
      'over the USB-C cable. LayerCam presents 5.1 k Rd on both CC lines and reads nothing back, so it must live within '
      'whatever the port gives without negotiation.\n')
    w('| case | VSYS current | against 1 A |\n|---|---|---|')
    for k in ('snap_day', 'snap_night', 'snap_burst', 'day', 'night', 'worst', 'peak'):
        i = sol[k]['i_vsys']
        w('| %s | %.2f A | %s |' % (k, i, 'within' if i <= SOURCE_A else 'OVER by %.0f %%' % (100 * (i / SOURCE_A - 1))))
    w('')
    for k in REQUIRED:
        check(sol[k]['i_vsys'] <= 0.5 * SOURCE_A, '%s draws %.2f A on average, under half the port\'s 1 A'
              % (k, sol[k]['i_vsys']))
    check(sol['snap_burst']['i_vsys'] <= 0.8 * SOURCE_A, 'a night snapshot (seconds) draws %.2f A, under 80 %% of '
          'the port\'s 1 A' % sol['snap_burst']['i_vsys'])
    check(sol['night']['i_vsys'] <= 0.8 * SOURCE_A, 'live view at night draws %.2f A, under 80 %% of the port\'s 1 A'
          % sol['night']['i_vsys'], warn=True)
    check(sol['worst']['i_vsys'] <= SOURCE_A,
          'worst sustained (stress bound) %.2f A against the port\'s 1 A rating' % sol['worst']['i_vsys'], warn=True)
    check(sol['peak']['i_vsys'] <= 1.5 * SOURCE_A,
          'millisecond peak %.2f A (the 10 uF caps on VSYS carry the edge; the port must not trip)'
          % sol['peak']['i_vsys'], warn=True)

    # ------------------------------------------------ each rail
    w('## Each regulator\n')
    w('| rail | regulator | divider | Vout nom (corners) | allowed | load in a shot / worst | rating | L | '
      'ripple / peak (L -20 %, fsw min) | Isat | Irms rating | efficiency (worst) | C out effective |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rails():
        lo, nom, hi = vout_range(*r['div'], r['reg']['vref'])
        code, Lval, ii = ind(r['L'])
        typ = loads('snap_burst')[r['load']]
        wc = loads('worst')[r['load']]
        pk = loads('peak')[r['load']]
        b = buck(r['reg'], VSYS[2], nom, max(wc, pk), Lval * (1 - L_TOL), ii['dcr'], fsw=r['reg']['fsw_min'])
        bw = sol['worst']['rails'][r['name']]
        ceff = caps_eff('main', r['name'], nom)
        rating = r['reg']['irated']
        if r['reg'] is EA and r['name'] == 'VCC_3V3':
            rating = 1.0
        w('| %s | %s %s | %.0fk / %.0fk | %.3f V (%.3f-%.3f) | %.3f-%.3f | %.2f / %.2f A (peak %.2f) | %.1f A | %s %.1f uH '
          '| %.2f / %.2f A | %.1f A | %.1f A | %.0f %% | %.0f uF |'
          % (r['name'], r['reg']['name'], r['ref'], r['div'][0] / 1e3, r['div'][1] / 1e3, nom, lo, hi,
             r['allowed'][0], r['allowed'][1], typ, wc, pk, rating, parts.PARTS[code]['mpn'], Lval * 1e6,
             b['di'], b['ipk'], ii['isat'], ii['irms'], 100 * bw['eff'], ceff * 1e6))
        # checks
        check(r['allowed'][0] <= lo and hi <= r['allowed'][1],
              '%s set to %.3f V (%.3f-%.3f with VREF +-2 %% and 1 %% resistors) inside %.3f-%.3f (%s)'
              % (r['name'], nom, lo, hi, r['allowed'][0], r['allowed'][1], r['allowed_src']))
        check(max(wc, pk) <= 0.7 * rating or (r['reg'] is TLV and max(wc, pk) <= 0.7 * rating),
              '%s worst load %.2f A within 70 %% of %s\'s %.1f A' % (r['name'], max(wc, pk), r['reg']['name'], rating),
              warn=True)
        check(b['ipk'] <= 0.8 * ii['isat'], '%s inductor peak %.2f A (L -20 %%, fsw min, 5.25 V in) under 80 %% of '
              'its %.1f A saturation' % (r['name'], b['ipk'], ii['isat']))
        check(b['irms'] <= 0.7 * ii['irms'], '%s inductor RMS %.2f A under 70 %% of its %.1f A rating (it runs in a '
              '65 C+ housing)' % (r['name'], b['irms'], ii['irms']), warn=True)
        if r['reg'] is EA:
            check(b['ipk'] < r['reg']['ilim'],
                  '%s peak %.2f A under the EA3036C\'s 1.8 A minimum current limit' % (r['name'], b['ipk']))
        else:
            check(ii['isat'] >= 1.1 * r['reg']['ilim'],
                  '%s inductor saturates at %.1f A, against the TLV62569\'s %.1f A typical switch limit (no maximum '
                  'given): in a short or hard overload the inductor saturates before the limit acts'
                  % (r['name'], ii['isat'], r['reg']['ilim']), warn=True)
    w('')
    w('The ripple and peak column is at the corner that maximises them: 5.25 V in, inductance -20 %, the switching '
      'frequency at its datasheet minimum (EA3036C 1.0 MHz; TLV62569 has none, 1.2 MHz assumed), at the larger of '
      'the worst sustained and peak loads. *C out effective* sums every ceramic on the rail at its bias and at 85 C '
      '(-15 %, X6S / X7S near 100 C).\n')

    ea_out = sum(loads('peak')[k] * v for k, v in (('v33', 3.33), ('ddr', 1.36), ('v18', 1.8)))
    check(ea_out < 6.0, 'EA3036C total output %.2f W at peak, under its 6 W limit' % ea_out)
    # transient / static margin on the two tight rails
    w('### The two rails with little room\n')
    r09 = [r for r in rails() if r['name'] == 'VDD_0V9'][0]
    lo, nom, hi = vout_range(*r09['div'], TLV['vref'])
    c09 = caps_eff('main', 'VDD_0V9', nom)
    f_c = 60e3                       # loop crossover ASSUMED (fsw / 25)
    step = 0.5
    droop = step / (2 * math.pi * f_c * c09)
    w('- **VDD_0V9**: %.3f V nominal from %.0fk / %.0fk; lowest corner %.3f V against the CPU\'s 0.85 V minimum, '
      'leaving %.0f mV for ripple and load steps. A 0.5 A step (CPU or NPU waking) on %.0f uF effective with an '
      'assumed 60 kHz loop crossover dips about %.0f mV: the low corner then reaches %.3f V.'
      % (nom, r09['div'][0] / 1e3, r09['div'][1] / 1e3, lo, (lo - 0.85) * 1e3, c09 * 1e6, droop * 1e3, lo - droop))
    check(lo - droop >= 0.85, 'VDD_0V9 low corner minus a 0.5 A step droop (%.3f V) stays at or above the CPU\'s 0.85 V'
          % (lo - droop), warn=True)
    # the fix
    for top in (49.9e3, 51e3):
        l2, n2, h2 = vout_range(top, r09['div'][1], TLV['vref'])
        w('  - with %.1fk on top: %.3f V (%.3f-%.3f), %.0f mV above 0.85 at the low corner less the step, %.0f mV under '
          'the logic\'s 0.95 V at the high corner.' % (top / 1e3, n2, l2, h2, (l2 - droop - 0.85) * 1e3, (0.95 - h2) * 1e3))
    rwf = [r for r in rails() if r['name'] == 'VWIFI'][0]
    lo, nom, hi = vout_range(*rwf['div'], TLV['vref'])
    cwf = caps_eff('main', 'VWIFI', nom)
    droopw = (1.0 - loads('worst')['wifi']) / (2 * math.pi * f_c * cwf)
    w('- **VWIFI**: %.3f V nominal (%.3f-%.3f); AMPAK guarantees full RF only from 3.2 V. A transmit burst (0.4 A to '
      '1 A) on %.0f uF effective dips about %.0f mV: the low corner reaches %.3f V.'
      % (nom, lo, hi, cwf * 1e6, droopw * 1e3, lo - droopw))
    check(lo - droopw >= 3.2, 'VWIFI low corner minus a TX-burst droop (%.3f V) stays at or above 3.2 V' % (lo - droopw),
          warn=True)
    l2, n2, h2 = vout_range(100e3, 20e3, TLV['vref'])
    w('  - with 20k in place of 22k at the bottom: %.3f V (%.3f-%.3f), %.0f mV of room above 3.2 V after the burst; '
      'VBAT may be anything to 4.8 V (it is a battery input), and VDDIO stays on the 3.3 V rail.'
      % (n2, l2, h2, (l2 - droopw - 3.2) * 1e3))
    w('')

    # ------------------------------------------------ capacitors
    w('## Capacitors at their bias\n')
    w('| net | parts | nominal | effective at bias, 85 C | rating against the rail |\n|---|---|---|---|---|')
    for net, v in (('VSYS', 5.25), ('VDD_0V9', 0.9), ('VCC_DDR', 1.36), ('VCC_1V8', 1.8), ('VCC_3V3', 3.33),
                   ('VWIFI', 3.33)):
        cs = caps_on('main', net)
        nomc = sum(NOMINAL.get(k, 0) * n for k, n in cs.items())
        effc = sum(eff_c(k, v) * n for k, n in cs.items() if k in NOMINAL)
        ratings = ', '.join('%d x %s (%s)' % (n, parts.PARTS[k]['value'], parts.PARTS[k]['desc'].split(' ', 2)[2])
                            for k, n in sorted(cs.items()))
        worst_ratio = max(v / float(re.search(r'([\d.]+)V', parts.PARTS[k]['desc']).group(1)) for k in cs)
        w('| %s | %s | %.1f uF | %.1f uF | %.0f %% of the lowest-rated part |' % (net, ratings, nomc * 1e6, effc * 1e6,
                                                                                 100 * worst_ratio))
        check(worst_ratio <= 0.85, '%s: every capacitor rated above the rail (worst %.0f %% of its rating)'
              % (net, 100 * worst_ratio))
    usb_c = sum(NOMINAL.get(k, 0) * n for k, n in caps_on('usb', 'VSYS').items())
    tot_vsys = sum(NOMINAL.get(k, 0) * n for k, n in caps_on('main', 'VSYS').items()) + usb_c
    w('')
    w('TI asks for 10-47 uF effective on the TLV62569 with 2.2 uH (its table 4: 2 x 22 uF the standard). The 0.9 V '
      'rail carries %.0f uF effective, most of it the SoC\'s decoupling behind the plane: more than TI tested. With '
      'peak-current-mode control extra output capacitance lowers the crossover rather than destabilising it, but '
      'check it on the bench with a load step.\n' % (caps_eff('main', 'VDD_0V9', 0.9) * 1e6))
    check(caps_eff('main', 'VDD_0V9', 0.9) <= 53e-6, 'VDD_0V9 output capacitance %.0f uF effective inside TI\'s '
          'tested range for the TLV62569 (to about 53 uF)' % (caps_eff('main', 'VDD_0V9', 0.9) * 1e6), warn=True)
    w('Hot plug: %.0f uF nominal sits on VSYS (USB board %.0f uF, main board %.0f uF) with no inrush limit. USB 2.0 '
      'allows a device 10 uF at attach. The printer\'s port is the only source and the camera is normally plugged in '
      'with the printer off, so this is a WARN; a soft-start load switch on the main board would make it compliant.\n'
      % (tot_vsys * 1e6, usb_c * 1e6, (tot_vsys - usb_c) * 1e6))
    check(tot_vsys <= 10e-6, 'VSYS capacitance at attach %.0f uF against USB\'s 10 uF' % (tot_vsys * 1e6), warn=True)

    # ------------------------------------------------ LEDs
    r, lc = led_cases()
    w('## IR LED strings (ring board)\n')
    w('Three strings of two 850 nm LEDs, each through %.0f ohm from VSYS, switched by Q1 (AO3400A) on LED_K. '
      'JNJ-LTJI0106W90: VF 1.4 V typ / 2.1 V max at 100 mA, 100 mA continuous, Tj 115 C max.\n' % r)
    w('| corner | VSYS at the ring | VF each | string current | resistor power | per LED |')
    w('|---|---|---|---|---|---|')
    for k, d in lc.items():
        w('| %s | %.2f V | %.2f V | %.1f mA | %.3f W | %.0f mW |' % (k, d['v'], d['vf'], d['i'] * 1e3, d['pr'],
                                                                   d['i'] * d['vf'] * 1e3))
    ihi = lc['high (5.25 V, typical VF hot, R -1 %)']
    ilo = lc['low (4.75 V, maximum VF cold, R +1 %)']
    w('')
    w('The string current spans %.0f-%.0f mA (%.1f : 1) over the supply and VF spread: two LEDs take 2.4-4 V of a '
      '4.7-5.25 V supply, so the resistor sees a small, very variable remainder.\n'
      % (ilo['i'] * 1e3, ihi['i'] * 1e3, ihi['i'] / max(ilo['i'], 1e-9)))
    check(ihi['i'] <= LED_IMAX, 'LED current %.0f mA at the high corner under the 100 mA rating' % (ihi['i'] * 1e3))
    check(ihi['pr'] <= 0.5 * 0.25, '%.0f R power' % r + ' %.3f W at the high corner within half its 0.25 W (it derates above '
          '70 C; thermal.py checks it at the ring\'s temperature)' % ihi['pr'], warn=True)
    check(ihi['i'] / max(ilo['i'], 1e-9) < 2.0, 'IR brightness spread %.1f : 1 between corners' %
          (ihi['i'] / max(ilo['i'], 1e-9)), warn=True)
    w('| resistor | current high / nominal / low corner | resistor power, high corner |\n|---|---|---|')
    for rr in (39, 47, 56):
        _, l2 = led_cases(rr)
        w('| %d R | %.0f / %.0f / %.0f mA | %.3f W |' % (rr, l2['high (5.25 V, typical VF hot, R -1 %)']['i'] * 1e3,
                                                         l2['nominal (5.0 V, typical VF, LEDs warm)']['i'] * 1e3,
                                                         l2['low (4.75 V, maximum VF cold, R +1 %)']['i'] * 1e3,
                                                         l2['high (5.25 V, typical VF hot, R -1 %)']['pr']))
    w('')

    # ------------------------------------------------ IR-cut
    i_cut = 3.3 / (IRCUT_COIL + DRV_RDS)
    w('## IR-cut filter\n')
    w('DRV8837 from 3.3 V into the 20 ohm coil: %.0f mA for 100-500 ms per switch (%.2f W in the coil, %.0f mW in the '
      'bridge), twice a day. The coil warms to about 23 ohm at 65 C (copper +0.39 %%/K): %.0f mA. The 3.3 V buck has '
      'room for it (counted in the peak case).\n' % (i_cut * 1e3, i_cut ** 2 * IRCUT_COIL, i_cut ** 2 * DRV_RDS * 1e3,
                                                    3.3 / (23 + DRV_RDS) * 1e3))
    check(i_cut <= 1.8, 'IR-cut pulse %.0f mA within the DRV8837\'s 1.8 A' % (i_cut * 1e3))

    # ------------------------------------------------ cables
    w('## Cables\n')
    iw = sol['worst']['i_vsys']
    w('- USB cable (SH, 1 A per contact): VSYS and ground on two contacts each, %.2f A worst: %.2f A a contact.' %
      (iw, iw / 2))
    check(iw / 2 <= 0.7, 'SH contacts carry %.2f A each (rated 1 A)' % (iw / 2))
    w('- LED ring cable: %.0f mA on two contacts each way.\n' % (ihi['i'] * 3e3))

    # ------------------------------------------------ assumptions
    w('## Assumptions (no datasheet number behind them)\n')
    w('- RV1106 typical streaming core current 0.60 A (half the Core1106 maximum); DDR3L 0.12 A typical, 0.30 A max; '
      '+15 % core leakage when hot. Measure these on the first board (USB power meter plus the rail shunts).')
    w('- AP6256 average 0.12 A while streaming, 0.40 A transmitting continuously (AMPAK gives only the 1 A peak).')
    w('- SC3336 module 0.06-0.08 A from 3.3 V (SmartSens publishes no figure in the flyer).')
    w('- Capacitor DC-bias fractions (Samsung curves, read approximately), switch resistance x1.35 hot, 4 ns edges, '
      'TLV62569 fsw +-20 %, loop crossover 60 kHz for the droop estimates.')
    w('- 850 nm LED: VF 0.1 V lower at 55 mA than at 100 mA, -1.5 mV/K, 25 % of its power leaves as light.')
    w('')
    return L, sol


def verdict(sol):
    V = []
    v = V.append
    _, lc = led_cases()
    rs = _val(string_resistor())
    hi = lc['high (5.25 V, typical VF hot, R -1 %)']
    lo = lc['low (4.75 V, maximum VF cold, R +1 %)']
    nom = lc['nominal (5.0 V, typical VF, LEDs warm)']
    fails = [c for c in checks if c[0] == 'FAIL']
    v('## Verdict\n')
    v('**%s** In snapshot mode (the requirement) the camera averages %.2f A by day and %.2f A by night, %.2f A '
      'during a night shot, all well inside the port\'s 1 A. Live view and the stress bound are reported only.\n'
      % ('PASS with WARNs.' if not fails else '%d FAIL.' % len(fails), sol['snap_day']['i_vsys'],
         sol['snap_night']['i_vsys'], sol['snap_burst']['i_vsys']))
    for r in rails():
        lo_, nom_, hi_ = vout_range(*r['div'], r['reg']['vref'])
        v('- %s: %.0fk / %.0fk = %.3f V (%.3f-%.3f) in %.3f-%.3f.' % (r['name'], r['div'][0] / 1e3, r['div'][1] / 1e3,
                                                                    nom_, lo_, hi_, *r['allowed']))
    v('- Regulators carry their worst loads with room (0.9 V %.2f of 2 A; EA3036C channels at most %.2f of 1 A; '
      'Wi-Fi %.1f A peak of 2 A); every inductor peak is under 80 %% of its saturation current.'
      % (loads('worst')['v09'], max(loads('peak')[k] for k in ('v33', 'ddr', 'v18')), loads('peak')['wifi']))
    v('- IR LED strings with %.0f R: %.0f mA nominal, %.0f-%.0f mA over the supply and VF spread; %.3f W per resistor '
      'at the high corner while lit (lit %.0f %% of the time in snapshot mode; thermal.md checks its derating).'
      % (rs, nom['i'] * 1e3, lo['i'] * 1e3, hi['i'] * 1e3, hi['pr'], 100 * LED_ON_S / SHOT_S))
    v('- The 1 u / 4.7 u / 10 u / 22 u capacitors are now Murata X7S / X6S (125 / 105 C). DC-bias fractions for them '
      'are assumed (SimSurfing not reachable); the 0.9 V rail\'s %.0f uF effective is still past TI\'s tested range '
      'for the TLV62569: check its load step on the bench.' % (caps_eff('main', 'VDD_0V9', 0.9) * 1e6))
    v('- Remaining WARNs: the stress bound against the 1 A port, the LED brightness spread '
      '(a constant-current sink would remove it), L1 / L5 saturating at the TLV62569\'s typical current limit, '
      '%.0f uF on VSYS at hot plug.' % ((sum(NOMINAL.get(k, 0) * n for k, n in caps_on('main', 'VSYS').items()) +
                                         sum(NOMINAL.get(k, 0) * n for k, n in caps_on('usb', 'VSYS').items())) * 1e6))
    v('- Not verified: every snapshot-mode current (ASSUMED, see the CASES comment: measure idle, shot and upload '
      'currents on the first board), the FPA252012D datasheet, Murata DC-bias curves, the loops with this much '
      'output capacitance.')
    v('')
    return V


def main():
    L, sol = run()
    i = [k for k, x in enumerate(L) if x.startswith('## Loads per')][0]
    L[i:i] = verdict(sol)
    w = L.append
    w('## Checks\n')
    for s, what in checks:
        w('- %s %s' % (s, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
