# -*- coding: utf-8 -*-
"""LayerCam Pro v1: the power chain worked through from the datasheets.

    python3 sim/power_budget.py        writes sim/power.md, exits 1 on a FAIL
    (tools/kd python3 sim/power_budget.py works too: nothing here needs KiCad)

The divider resistors, the regulator, inductor and capacitor choices are
read from src/circuit.py and src/parts.py (built with circuit.build), so a
change there is re-checked by running this again.  The load currents are
the datasheet or measured figures below, each with its source; where no
source gives a number the figure is marked ASSUMED and the verdict says so.

What changed from LayerCam v1's copy: one board (no ring or USB board, no
cables inside the case); the ESP32-C6-MINI-1U-H4 in place of the AP6256,
on its own buck at 3.25 V; the bare SC4336H image sensor in place of the
SC3336 module, its analogue rail from the TLV75528 2.8 V LDO and its I/O
from VCC_1V8; the six VSMY3850X01 LEDs on the board; the DRV8210P in place
of the DRV8837.  The Wi-Fi's power save is OFF today (esp-hosted gives no
way to turn it on from Linux), so the snapshot cases come in two flavours:
power save off (the C6 firmware built without firmware/tools/c6-power-save.sh) and on.

thermal.py imports heat() and led_on() from here: the heat each part makes
in each operating case.

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
    """'R47K' -> 47e3, 'R6K2' -> 6.2e3, 'R1R' -> 1, 'R240R' -> 240, 'R22K6' -> 22.6e3."""
    v = parts.PARTS[code]['value']
    m = re.match(r'([\d.]+)\s*([kMR]?)', v)
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
# Murata DFE252012F: saturation current from parts.py's description (Murata's figure); the temperature-rise
# current and DCR are typical for the series and ASSUMED (Murata's product pages could not be read: 2026-11-01)
INDUCTORS = {'L1U5': dict(irms=2.4, isat=2.7, dcr=0.065, src='Isat Murata; Irms, DCR ASSUMED'),
             'L2U2': dict(irms=2.0, isat=2.3, dcr=0.090, src='Isat Murata; Irms, DCR ASSUMED')}
# MLCC DC bias: fraction of nominal left at a bias.  Murata / Taiyo Yuden X6S / X7S parts (parts.py).  The
# makers' curves could not be reached; these fractions are ASSUMED from typical high-CV X6S / X7S behaviour in
# these case sizes (to +-10 %).
DCBIAS = {'C22U': [(0, 1.0), (0.9, 0.85), (1.4, 0.74), (1.8, 0.65), (3.3, 0.40), (3.6, 0.36)],
          'C10U': [(0, 1.0), (0.9, 0.92), (1.4, 0.84), (1.8, 0.77), (3.3, 0.55), (5.0, 0.38), (5.25, 0.36)],
          'C1U': [(0, 1.0), (2.8, 0.82), (3.3, 0.78), (5.0, 0.65)], 'C4U7': [(0, 1.0), (1.0, 0.80)],
          'C100N': [(0, 1.0), (5.0, 0.90)]}
NOMINAL = {'C22U': 22e-6, 'C10U': 10e-6, 'C1U': 1e-6, 'C4U7': 4.7e-6, 'C100N': 0.1e-6}
X5R_HOT = 0.85                      # X6S / X7S lose up to 22 % at their 105 / 125 C; ~15 % near 100 C (ASSUMED)

# Supply: Prusa's camera port on the printer's mainboard: "Input: 5VDC 1 A" (Prusa product page for the
# Buddy3D camera); USB tolerance at the receptacle
VSYS = (4.75, 5.0, 5.25)
SOURCE_A = 1.0
CABLE_R = 0.04                      # USB-C receptacle contacts + board copper, round trip, ohm (ASSUMED); the
                                    # printer's cable is outside the case and not counted as heat inside

# ---------------------------------------------------------------- loads (A) per operating case
# RV1106G3: Luckfox Core1106 power reference V1.0 (measured, 25 C room): VDD_0V9 1210 mA max at 0.88 V,
# VCC_1V8 38.9 mA, VCC_3V3 94.4 mA, 5 V in 467 mA.  Typical streaming (ISP + H.264, NPU idle):
# ASSUMED 0.60 A on 0.9 V.  Hot: leakage ASSUMED +15 % on the core at Tj ~ 110 C.
# The DDR3L is inside the package; Rockchip gives no current: ASSUMED 0.12 A typical, 0.30 A max.
# W25N02KV: 25 / 35 mA read (typ / max, Winbond).
#
# ESP32-C6-MINI-1U (Espressif ESP32-C6-MINI-1 & MINI-1U datasheet v1.5, 3.3 V, 25 C):
#   Table 6-4  TX 802.11b 1 Mbps @ 20.5 dBm 382 mA; 802.11g 54 Mbps @ 19 dBm 316 mA; 802.11n HT20 MCS7
#              @ 18 dBm 295 mA; HT40 MCS7 280 mA; 802.11ax MCS9 @ 15.5 dBm 251 mA (all at 100 % duty)
#              RX 802.11b/g/n HT20 78 mA, HT40 82 mA, 802.11ax HE20 78 mA (peripherals off, CPU idle)
#   Table 6-7  modem-sleep (Wi-Fi clock-gated) at 160 MHz: CPU running 27 / 38 mA, idle 17 / 28 mA
#              (all peripheral clocks disabled / enabled); at 80 MHz 19 / 30, 14 / 25 mA
#   Table 6-8  light-sleep 180 uA (35 uA with peripherals off); deep-sleep 7 uA
C6_TX = {'11b_20.5dBm': 0.382, '11g_19dBm': 0.316, 'HT20_MCS7_18dBm': 0.295, 'HT40_MCS7': 0.280,
         'HE_MCS9_15.5dBm': 0.251}
C6_RX = 0.078
C6_MODEM_SLEEP = 0.028              # 160 MHz, CPU idle, peripheral clocks on (the SDIO slave is running)
C6_LIGHT_SLEEP = 0.000180
C6_HOSTED = 0.010                   # esp-hosted's CPU and SDIO work on top of the RX figure (ASSUMED)
C6_LISTEN = C6_RX + C6_HOSTED       # power save OFF: the receiver on all the time, listening
C6_TX_USE = C6_TX['HT20_MCS7_18dBm']   # the rate a camera in a metal printer is likely to use (ASSUMED)
C6_RF_OUT = 10 ** (18.0 / 10) * 1e-3   # W radiated while transmitting at 18 dBm (leaves by the antenna)
# Snapshot traffic: one ~1 MB JPEG every 10 s (Prusa Connect), ~0.5 s of TX airtime and 1.0 s of radio-on
# each 10 s (ASSUMED: 8 Mbit at ~16 Mbit/s of TCP over a mid-quality link).  Beacons: DTIM 1 at 102.4 ms,
# ~4 ms awake each with power save on (ASSUMED).
TX_AIR, RADIO_ON, BEACON_DUTY = 0.05, 0.10, 0.04


def c6_snapshot(power_save):
    """The C6's average current in snapshot mode."""
    if not power_save:
        # power save off: listening whenever not transmitting
        return C6_LISTEN * (1 - TX_AIR) + C6_TX_USE * TX_AIR
    # power save on (modem-sleep between DTIM beacons): radio clock-gated except for the beacons and the
    # upload window, which is TX for TX_AIR and listening for the rest of RADIO_ON
    base = C6_MODEM_SLEEP + (C6_LISTEN - C6_MODEM_SLEEP) * BEACON_DUTY
    return base * (1 - RADIO_ON) + C6_LISTEN * (RADIO_ON - TX_AIR) + C6_TX_USE * TX_AIR


C6_LIVE_TX = 0.15                   # live view: ~4 Mbit/s H.264 up, ~15 % TX airtime (ASSUMED)
C6_LIVE = C6_LISTEN * (1 - C6_LIVE_TX) + C6_TX_USE * C6_LIVE_TX
C6_WORST = C6_TX['11b_20.5dBm'] + C6_HOSTED     # transmitting continuously at the highest-current setting
C6_PEAK = 0.50                      # Espressif: the 3.3 V supply must deliver >= 0.5 A (datasheet 6.2)

# SC4336H: SmartSens gives "< 120 mW at 30 fps" (press release, May 2025).  The SC4336 family's rails
# (SC4336 datasheet V0.3 as summarised by a third party: docs/hookup notes): AVDD 2.8 V 20.9 mA, DOVDD
# 1.8 V 50.1 mA at 2-lane 30 fps = 149 mW.  Streaming: the SC4336H's 120 mW split in the SC4336's ratio
# (AVDD 16.8 mA, DOVDD 40.3 mA); worst: the SC4336's own figures.  Software standby between shots: ASSUMED
# 1 mA AVDD + 2 mA DOVDD (no published figure).
CAM_I = dict(stream=(0.0168, 0.0403), max=(0.0209, 0.0501), standby=(0.001, 0.002))
V_AVDD = 2.8
# IR-cut coil 20 ohm at 3.3 V through the DRV8210P (TI SLVSFY8B: HS + LS 525 + 525 mOhm, DSG package):
# pulses of 100-500 ms twice a day.
# Snapshot mode (the product's requirement): Prusa Connect takes a still at most every 10 s and the timelapse
# one full-resolution frame per layer (taken in the same pipeline; a layer takes 10 s or more, so a timelapse
# frame stands in for a snapshot rather than adding one at this rate).  Between shots the sensor in software
# standby, the CPU at its lowest DVFS point with ISP / VENC / NPU clock-gated; each shot wakes the sensor,
# settles exposure, grabs and JPEG-encodes a frame: ACTIVE_S of the SHOT_S period at the streaming loads.  At
# night the IR LEDs light for LED_ON_S of each shot (night frames only).  The SoC's snapshot currents are
# ASSUMED as in LayerCam v1: idle core 0.18 A (~15 % of the Core1106 maximum), DDR 0.05 A.
SHOT_S, ACTIVE_S, LED_ON_S = 10.0, 1.5, 2.0
_k = ACTIVE_S / SHOT_S


def _avg(idle, active):
    return idle * (1 - _k) + active * _k


def _snap(desc, wifi, led):
    d = dict(desc=desc, v09=_avg(0.18, 0.60), ddr=_avg(0.05, 0.12), v18=0.03, soc33=0.04, nand=_avg(0.0, 0.02),
             cam=tuple(_avg(a, b) for a, b in zip(CAM_I['standby'], CAM_I['stream'])), wifi=wifi,
             tx=TX_AIR, ircut=0.0, led=led)
    if led:
        d['led_duty'] = LED_ON_S / SHOT_S
    return d


CASES = {
    'snap_day': _snap('snapshot, day, Wi-Fi power save OFF (firmware built without the power-save step): one still every 10 s, idle between '
                      '(REQUIREMENT CASE)', c6_snapshot(False), False),
    'snap_night': _snap('snapshot, night, Wi-Fi power save OFF: the same, IR LEDs on for 2 s of each 10 s '
                        '(REQUIREMENT CASE)', c6_snapshot(False), True),
    'snap_day_ps': _snap('snapshot, day, Wi-Fi power save ON (once fixed)', c6_snapshot(True), False),
    'snap_night_ps': _snap('snapshot, night, Wi-Fi power save ON (once fixed)', c6_snapshot(True), True),
    'snap_burst': dict(desc='snapshot, night, during a shot (seconds): streaming loads, Wi-Fi uploading, LEDs on',
                       v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.02, cam=CAM_I['stream'],
                       wifi=0.5 * C6_LISTEN + 0.5 * C6_TX_USE, tx=0.5, ircut=0.0, led=True),
    'day': dict(desc='live view, day: streaming 2560 x 1440 at 30 fps, Wi-Fi average, IR LEDs off (reported only)',
                v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.005, cam=CAM_I['stream'], wifi=C6_LIVE,
                tx=C6_LIVE_TX, ircut=0.0, led=False),
    'night': dict(desc='live view, night: the same with the six IR LEDs on at 100 % (reported only)',
                  v09=0.60, ddr=0.12, v18=0.035, soc33=0.06, nand=0.005, cam=CAM_I['stream'], wifi=C6_LIVE,
                  tx=C6_LIVE_TX, ircut=0.0, led=True),
    'worst': dict(desc='worst sustained (stress bound): SoC at the measured maximum +15 % hot leakage, DDR max, '
                       'Wi-Fi transmitting continuously at 20.5 dBm, sensor at the SC4336 figures, IR LEDs on at the '
                       'high-current corner',
                  v09=1.21 * 1.15, ddr=0.30, v18=0.045, soc33=0.094, nand=0.035, cam=CAM_I['max'], wifi=C6_WORST,
                  tx=1.0, ircut=0.0, led='max'),
    'peak': dict(desc='peak (milliseconds): worst plus the C6\'s 0.5 A supply peak and an IR-cut pulse',
                 v09=1.21 * 1.15, ddr=0.30, v18=0.045, soc33=0.094, nand=0.035, cam=CAM_I['max'], wifi=C6_PEAK,
                 tx=1.0, ircut=None, led='max'),
}
REQUIRED = ('snap_day', 'snap_night', 'snap_day_ps', 'snap_night_ps')
# LEDs: Vishay VSMY3850 (doc 83399 rev 1.5, the base part; parts.py's X01 grade): VF 1.6 typ / 2.0 max at
# 100 mA; at 45 mA about 0.15 V less (circuit.py's 1.45 V; Vishay fig. 3, read approximately); TKVF
# -1.45 mV/K; IF 100 mA max; radiant power 55 mW at 100 mA (about 34 % of 160 mW in), -0.35 %/K.
VF100_TYP, VF100_MAX, VF_LOW_I = 1.60, 2.00, 0.15
VF_TC = -1.45e-3
LED_IMAX = 0.100
LED_WALL_PLUG = 0.27                # light out / electrical in at 45 mA and ~85 C (34 % less 0.35 %/K x 60 K)
R_LED_TOL = 0.01
IRCUT_COIL = 20.0                   # ohm (Commonlands CLA219 note in circuit.py)
DRV_RDS = 1.05                      # DRV8210P DSG: HS 525 + LS 525 mOhm (TI SLVSFY8B, 7.5)
LDO_IQ = 33e-6                      # TLV75528 ground current (SBVS320D, 33 uA max)

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
    return max(0.0, (vsys - 2 * vf) / r)


def string_resistors():
    """The string resistors: (ref, part code), VSYS to a string anode."""
    return [(c.ref, c.part) for c in COMPS['main'] if c.ref.startswith('R') and 'VSYS' in c.pins.values()
            and any(n.startswith('STR') for n in c.pins.values())]


def string_resistor():
    return string_resistors()[0][1]


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
             allowed=(1.70, 1.90), allowed_src='1.8 V domains 1.62-1.98; the sensor\'s DOVDD 1.8 +-0.1 V (SmartSens)'),
        dict(name='VCC_3V3', reg=EA, ref='U3 CH1', L='L2', div=(t33, b33), load='v33',
             allowed=(3.0, 3.465), allowed_src='VCCIO 3.0-3.465 (USB_AVDD to 3.6)'),
        dict(name='VWIFI', reg=TLV, ref='U4', L='L5', div=(twf, bwf), load='wifi',
             allowed=(3.0, 3.6), allowed_src='ESP32-C6-MINI-1U VDD33 3.0-3.6 V (datasheet v1.5 table 6-2; '
                                            '3.6 V is also its absolute maximum, table 6-1)'),
    ]


def loads(case):
    c = CASES[case]
    ircut = (3.3 / (IRCUT_COIL + DRV_RDS)) if c['ircut'] is None else c['ircut']
    i_avdd, i_dovdd = c['cam']
    # 3.3 V: SoC I/O, NAND, the sensor LDO's input (its output current plus ground current), the 1.3 mA
    # status LED, the IR-cut pulse
    v33 = c['soc33'] + c['nand'] + i_avdd + LDO_IQ + 0.0013 + ircut
    # 1.8 V: SoC, the sensor's DOVDD (through 1R), the light sensor (~1 mA) and the I2C / boot pull-ups
    v18 = c['v18'] + i_dovdd + 0.003
    return dict(v09=c['v09'], ddr=c['ddr'], v18=v18, v33=v33, wifi=c['wifi'], ircut=ircut, avdd=i_avdd,
                dovdd=i_dovdd)


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
    v33, v18 = rr['VCC_3V3']['vout'], rr['VCC_1V8']['vout']
    h['U1'] = rr['VDD_0V9']['vout'] * c['v09'] + rr['VCC_DDR']['vout'] * c['ddr'] + v18 * c['v18'] + v33 * c['soc33']
    h['U5'] = v33 * c['nand']
    # the C6: everything it draws becomes heat, less what the antenna radiates while it transmits
    h['U6'] = rr['VWIFI']['vout'] * c['wifi'] - C6_RF_OUT * c.get('tx', 0.0)
    h['U8'] = V_AVDD * ld['avdd'] + v18 * ld['dovdd']          # the image sensor
    h['U9'] = (v33 - V_AVDD) * ld['avdd'] + v33 * LDO_IQ      # its 2.8 V LDO
    h['U7'] = (ld['ircut'] ** 2) * DRV_RDS
    pin = sum(x['pin'] for x in rr.values())
    i_led = 0.0
    if c['led']:
        _, lc = led_cases()
        sel = lc['high (5.25 V, typical VF hot, R -1 %)'] if c['led'] == 'max' else lc['nominal (5.0 V, typical VF, LEDs warm)']
        duty = c.get('led_duty', 1.0)
        i_led = 3 * sel['i'] * duty
        for ref, _code in string_resistors():
            h[ref] = sel['pr'] * duty
        for k in range(2, 8):
            h['D%d' % k] = sel['i'] * sel['vf'] * (1 - LED_WALL_PLUG) * duty
        h['Q1'] = (3 * sel['i']) ** 2 * 0.05 * duty
        out['led_on'] = dict(sel, duty=duty, led_heat_each=sel['i'] * sel['vf'] * (1 - LED_WALL_PLUG))
        led_v = sel['v']
    else:
        led_v = vin
    i_reg = pin / vin
    out['i_vsys'] = i_reg + i_led + vin / 28e3
    out['i_led'] = i_led
    out['p_in'] = pin + i_led * led_v
    h['J1'] = out['i_vsys'] ** 2 * CABLE_R              # the receptacle's contacts and the board copper
    out['heat_total'] = sum(h.values())
    return out


def led_on(case):
    """For thermal.py: while the LEDs are lit, each LED's heat and each resistor's power (W)."""
    lo = solve_case(case).get('led_on')
    return (lo['led_heat_each'], lo['pr']) if lo else (0.0, 0.0)


def heat(case):
    """For thermal.py: {ref: W} in one operating case (at 5.0 V in; 'worst' at 5.25 V for the LEDs)."""
    return solve_case(case)['heat']


# ---------------------------------------------------------------- the write-up
def run():
    L = []
    w = L.append
    w('# LayerCam Pro v1: power budget and regulators\n')
    w('Computed by `sim/power_budget.py` from `src/circuit.py` / `src/parts.py` (dividers, inductors, capacitors read '
      'from the netlist) and the datasheet figures in the script. Figures marked *assumed* have no datasheet behind '
      'them; they are listed under *Assumptions* with the reason for each value. LayerCam v1\'s budget '
      '(products/layercam/layercam/sim/power.md) is the starting point: the RV1106 side is unchanged.\n')

    # ------------------------------------------------ the Wi-Fi
    w('## The Wi-Fi module (ESP32-C6-MINI-1U-H4)\n')
    w('Espressif\'s module datasheet v1.5 (3.3 V, 25 C) gives:\n')
    w('| state | current | source |\n|---|---|---|')
    for k, v in C6_TX.items():
        w('| TX %s (100 %% duty) | %.0f mA | table 6-4 |' % (k.replace('_', ' '), v * 1e3))
    w('| RX / listen, HT20 or HE20 (CPU idle) | %.0f mA | table 6-4 |' % (C6_RX * 1e3))
    w('| modem-sleep, 160 MHz, CPU idle, peripheral clocks on | %.0f mA | table 6-7 |' % (C6_MODEM_SLEEP * 1e3))
    w('| light-sleep | %.2f mA | table 6-8 |' % (C6_LIGHT_SLEEP * 1e3))
    w('')
    w('**Power save is OFF** unless the C6\'s firmware is built with it on (`firmware/tools/c6-power-save.sh`, which '
      'the 65 C rating needs): esp-hosted gives Linux no way to turn it on, so the receiver '
      'listens all the time (%.0f mA: the RX figure plus an assumed %.0f mA for esp-hosted\'s CPU and the SDIO link). '
      'In snapshot mode each 10 s carries one ~1 MB JPEG: %.0f %% TX airtime at %.0f mA (HT20 MCS7, 18 dBm) and the '
      'radio on for %.0f %% of the time.\n'
      % (C6_LISTEN * 1e3, C6_HOSTED * 1e3, TX_AIR * 100, C6_TX_USE * 1e3, RADIO_ON * 100))
    w('| C6 average | power save off (firmware built without the power-save step) | power save on (modem-sleep between DTIM beacons) |\n|---|---|---|')
    w('| snapshot mode | **%.0f mA** (%.0f mW) | **%.0f mA** (%.0f mW) |'
      % (c6_snapshot(False) * 1e3, c6_snapshot(False) * 3.255e3, c6_snapshot(True) * 1e3, c6_snapshot(True) * 3.255e3))
    w('| live view (~4 Mbit/s up, %.0f %% TX) | %.0f mA | the same (the radio is busy) |' % (C6_LIVE_TX * 100, C6_LIVE * 1e3))
    w('')
    w('Light-sleep (0.18 mA) would cut the floor further but stops the SDIO link, so it is not counted. '
      'LayerCam v1 assumed 50 mA for the AP6256 in power-save; the C6 with power save off draws about twice that.\n')

    # ------------------------------------------------ the sensor
    w('## The image sensor (SC4336H) and its 2.8 V LDO\n')
    w('SmartSens gives the SC4336H as "< 120 mW at 30 fps"; the SC4336 family draws AVDD 20.9 mA (2.8 V) and DOVDD '
      '50.1 mA (1.8 V) at 2-lane 30 fps (149 mW; a third-party summary of the SC4336 datasheet). The model streams at '
      'the SC4336H\'s 120 mW split in the SC4336\'s ratio and uses the SC4336 figures for the stress bound.\n')
    w('| state | AVDD (2.8 V, TLV75528 from 3.3 V) | DOVDD (1.8 V, 1R from VCC_1V8) | sensor | LDO |\n|---|---|---|---|---|')
    v33n = vout_range(*divider('main', 'FB_3V3', 'VCC_3V3'), EA['vref'])[1]
    for k, lab in (('stream', 'streaming 30 fps (SC4336H)'), ('max', 'SC4336 figures (stress bound)'),
                   ('standby', 'software standby (ASSUMED)')):
        a, d = CAM_I[k]
        w('| %s | %.1f mA | %.1f mA | %.0f mW | %.1f mW |' % (lab, a * 1e3, d * 1e3, (V_AVDD * a + 1.8 * d) * 1e3,
                                                             (v33n - V_AVDD) * a * 1e3))
    w('')
    a = CAM_I['max'][0]
    w('The LDO drops %.2f V (3.3 V rail nominal %.3f V; TLV755P dropout about 0.2 V at 500 mA, far less at %.0f mA): '
      'it regulates at the 3.3 V rail\'s low corner too.\n' % (v33n - V_AVDD, v33n, a * 1e3))
    lo33 = vout_range(*divider('main', 'FB_3V3', 'VCC_3V3'), EA['vref'])[0]
    check(lo33 - V_AVDD >= 0.15, 'sensor LDO headroom %.2f V at the 3.3 V rail\'s low corner (TLV75528 needs about '
          '0.05 V at %.0f mA)' % (lo33 - V_AVDD, a * 1e3))

    # ------------------------------------------------ loads
    w('## Loads per operating case\n')
    w('| case | 0.9 V | DDR 1.36 V | 1.8 V | 3.3 V | Wi-Fi 3.25 V | IR LEDs (VSYS) | VSYS current | VSYS power |')
    w('|---|---|---|---|---|---|---|---|---|')
    sol = {}
    for k in CASES:
        s = solve_case(k)
        sol[k] = s
        ld = loads(k)
        w('| %s | %.2f A | %.2f A | %.3f A | %.3f A | %.3f A | %.0f mA | **%.2f A** | %.2f W |'
          % (CASES[k]['desc'], ld['v09'], ld['ddr'], ld['v18'], ld['v33'], ld['wifi'], s['i_led'] * 1e3,
             s['i_vsys'], s['p_in']))
    w('')
    w('VSYS current at 5.0 V in, regulator losses from the buck model below (switch and inductor resistance hot, '
      '4 ns edges); the LED strings straight from VSYS. All of the input power is heat inside the case except the '
      'light the LEDs emit and the Wi-Fi\'s radiated power.\n')
    w('| case | heat in the case | the largest parts |\n|---|---|---|')
    for k in CASES:
        h = sol[k]['heat']
        top = sorted(h.items(), key=lambda kv: -kv[1])[:5]
        w('| %s | %.2f W | %s |' % (k, sum(h.values()), ', '.join('%s %.2f' % kv for kv in top)))
    w('')

    # ------------------------------------------------ the source
    w('## The 5 V source\n')
    w('Prusa\'s own camera on this port is rated "5 VDC 1 A" (Prusa product page): the printer\'s mainboard feeds it '
      'over the USB-C cable. The camera presents 5.1 k Rd on both CC lines and reads nothing back, so it must live '
      'within whatever the port gives without negotiation.\n')
    w('| case | VSYS current | against 1 A |\n|---|---|---|')
    for k in CASES:
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
        w('| %s | %s %s | %.0fk / %.1fk | %.3f V (%.3f-%.3f) | %.3f-%.3f | %.2f / %.2f A (peak %.2f) | %.1f A | %s %.1f uH '
          '| %.2f / %.2f A | %.1f A | %.1f A | %.0f %% | %.0f uF |'
          % (r['name'], r['reg']['name'], r['ref'], r['div'][0] / 1e3, r['div'][1] / 1e3, nom, lo, hi,
             r['allowed'][0], r['allowed'][1], typ, wc, pk, rating, parts.PARTS[code]['mpn'], Lval * 1e6,
             b['di'], b['ipk'], ii['isat'], ii['irms'], 100 * bw['eff'], ceff * 1e6))
        check(r['allowed'][0] <= lo and hi <= r['allowed'][1],
              '%s set to %.3f V (%.3f-%.3f with VREF +-2 %% and 1 %% resistors) inside %.3f-%.3f (%s)'
              % (r['name'], nom, lo, hi, r['allowed'][0], r['allowed'][1], r['allowed_src']))
        check(max(wc, pk) <= 0.7 * rating,
              '%s worst load %.2f A within 70 %% of %s\'s %.1f A' % (r['name'], max(wc, pk), r['reg']['name'], rating),
              warn=True)
        check(b['ipk'] <= 0.8 * ii['isat'], '%s inductor peak %.2f A (L -20 %%, fsw min, 5.25 V in) under 80 %% of '
              'its %.1f A saturation' % (r['name'], b['ipk'], ii['isat']))
        check(b['irms'] <= 0.7 * ii['irms'], '%s inductor RMS %.2f A under 70 %% of its %.1f A rating (ASSUMED; it '
              'runs in a 70 C+ case)' % (r['name'], b['irms'], ii['irms']), warn=True)
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
      '(-15 %, X6S / X7S near 100 C). The inductors are Murata DFE252012F: saturation current from parts.py; the '
      'Irms rating and DCR are typical values (ASSUMED).\n')

    ea_out = sum(loads('peak')[k] * v for k, v in (('v33', 3.26), ('ddr', 1.36), ('v18', 1.8)))
    check(ea_out < 6.0, 'EA3036C total output %.2f W at peak, under its 6 W limit' % ea_out)
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
    rwf = [r for r in rails() if r['name'] == 'VWIFI'][0]
    lo, nom, hi = vout_range(*rwf['div'], TLV['vref'])
    cwf = caps_eff('main', 'VWIFI', nom)
    stepw = C6_PEAK - C6_LISTEN
    droopw = stepw / (2 * math.pi * f_c * cwf)
    w('- **VWIFI**: %.3f V nominal (%.3f-%.3f) from %.0fk / %.1fk, inside the C6\'s 3.0-3.6 V with %.0f mV under its '
      '3.6 V absolute maximum at the high corner (LayerCam v1\'s 3.60 V would have sat on it). A transmit burst '
      '(%.0f mA listening to the %.1f A supply peak) on %.0f uF effective dips about %.0f mV: the low corner reaches '
      '%.3f V.' % (nom, lo, hi, rwf['div'][0] / 1e3, rwf['div'][1] / 1e3, (3.6 - hi) * 1e3, C6_LISTEN * 1e3, C6_PEAK,
                    cwf * 1e6, droopw * 1e3, lo - droopw))
    check(lo - droopw >= 3.0, 'VWIFI low corner minus a TX-burst droop (%.3f V) stays at or above the C6\'s 3.0 V'
          % (lo - droopw), warn=True)
    check(abs(nom - vout_range(*divider('main', 'FB_3V3', 'VCC_3V3'), EA['vref'])[1]) <= 0.1,
          'VWIFI within 0.1 V of VCC_3V3 (the C6\'s I/O runs at its supply and meets the SoC\'s 3.3 V pins directly)')
    w('')

    # ------------------------------------------------ capacitors
    w('## Capacitors at their bias\n')
    w('| net | parts | nominal | effective at bias, 85 C | rating against the rail |\n|---|---|---|---|---|')
    for net, v in (('VSYS', 5.25), ('VDD_0V9', 0.9), ('VCC_DDR', 1.36), ('VCC_1V8', 1.8), ('VCC_3V3', 3.33),
                   ('VWIFI', 3.33), ('CAM_AVDD', 2.8), ('CAM_DOVDD', 1.8)):
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
    tot_vsys = sum(NOMINAL.get(k, 0) * n for k, n in caps_on('main', 'VSYS').items())
    w('')
    w('TI asks for 10-47 uF effective on the TLV62569 with 2.2 uH (its table 4: 2 x 22 uF the standard). The 0.9 V '
      'rail carries %.0f uF effective, most of it the SoC\'s decoupling behind the plane. With peak-current-mode '
      'control extra output capacitance lowers the crossover rather than destabilising it, but check it on the bench '
      'with a load step. The TLV75528 needs 1 uF in (and >= 0.47 uF effective out, at most 200 uF): %.1f uF at its '
      'output net.\n' % (caps_eff('main', 'VDD_0V9', 0.9) * 1e6, caps_eff('main', 'CAM_AVDD', 2.8) * 1e6))
    check(caps_eff('main', 'VDD_0V9', 0.9) <= 53e-6, 'VDD_0V9 output capacitance %.0f uF effective inside TI\'s '
          'tested range for the TLV62569 (to about 53 uF)' % (caps_eff('main', 'VDD_0V9', 0.9) * 1e6), warn=True)
    check(caps_eff('main', 'CAM_AVDD', 2.8) >= 0.47e-6, 'TLV75528 output %.1f uF effective, at least the 0.47 uF '
          'TI asks for' % (caps_eff('main', 'CAM_AVDD', 2.8) * 1e6))
    w('Hot plug: %.0f uF nominal sits on VSYS with no inrush limit. USB 2.0 allows a device 10 uF at attach. The '
      'printer\'s port is the only source and the camera is normally plugged in with the printer off, so this is a '
      'WARN; a soft-start load switch would make it compliant.\n' % (tot_vsys * 1e6))
    check(tot_vsys <= 10e-6, 'VSYS capacitance at attach %.0f uF against USB\'s 10 uF' % (tot_vsys * 1e6), warn=True)

    # ------------------------------------------------ LEDs
    r, lc = led_cases()
    w('## IR LED strings (on the board\'s front face)\n')
    w('Three strings of two 850 nm VSMY3850X01 LEDs, each through %.0f ohm (1206) from VSYS, switched by Q1 '
      '(AO3400A) on LED_K, lit only while a night frame is taken. Vishay VSMY3850: VF 1.6 V typ / 2.0 V max at '
      '100 mA, 100 mA continuous; the base part\'s datasheet (doc 83399 rev 1.5) rates Tj 100 C and ambient '
      '-40..85 C; parts.py gives the X01 grade -40..105 C (its datasheet was not read: confirm).\n' % r)
    w('| corner | VSYS | VF each | string current | resistor power | per LED |')
    w('|---|---|---|---|---|---|')
    for k, d in lc.items():
        w('| %s | %.2f V | %.2f V | %.1f mA | %.3f W | %.0f mW |' % (k, d['v'], d['vf'], d['i'] * 1e3, d['pr'],
                                                                   d['i'] * d['vf'] * 1e3))
    ihi = lc['high (5.25 V, typical VF hot, R -1 %)']
    ilo = lc['low (4.75 V, maximum VF cold, R +1 %)']
    w('')
    w('The string current spans %.0f-%.0f mA (%.1f : 1) over the supply and VF spread: two LEDs take 2.6-3.7 V of a '
      '4.7-5.25 V supply, so the resistor sees a small, very variable remainder.\n'
      % (ilo['i'] * 1e3, ihi['i'] * 1e3, ihi['i'] / max(ilo['i'], 1e-9)))
    check(ihi['i'] <= LED_IMAX, 'LED current %.0f mA at the high corner under the 100 mA rating' % (ihi['i'] * 1e3))
    check(ihi['pr'] <= 0.5 * 0.25, '%.0f R power' % r + ' %.3f W at the high corner within half its 0.25 W (it derates '
          'above 70 C; thermal.py checks it at the board\'s temperature)' % ihi['pr'], warn=True)
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
    w('DRV8210P from 3.3 V into the 20 ohm coil: %.0f mA for 100-500 ms per switch (%.2f W in the coil, %.0f mW in the '
      'bridge, HS + LS %.2f ohm), twice a day. The coil warms to about 23.5 ohm at 85 C (copper +0.39 %%/K): %.0f mA. '
      'The 3.3 V buck has room for it (counted in the peak case).\n' % (i_cut * 1e3, i_cut ** 2 * IRCUT_COIL,
                                                                       i_cut ** 2 * DRV_RDS * 1e3, DRV_RDS,
                                                                       3.3 / (23.5 + DRV_RDS) * 1e3))
    check(i_cut <= 1.0, 'IR-cut pulse %.0f mA well within the DRV8210P\'s current limit' % (i_cut * 1e3))

    # ------------------------------------------------ connector
    w('## USB-C\n')
    iw = sol['worst']['i_vsys']
    w('- USB4105-GF-A: VBUS and ground on two contacts each (A4B9 / B4A9, A1B12 / B1A12), %.2f A worst sustained: '
      '%.2f A a contact; USB 2.0 type-C contacts carry 3 A by the USB-C specification.\n' % (iw, iw / 2))
    check(iw / 2 <= 1.0, 'USB-C contacts carry %.2f A each' % (iw / 2))

    # ------------------------------------------------ assumptions
    w('## Assumptions (no datasheet number behind them)\n')
    w('- RV1106 typical streaming core current 0.60 A (half the Core1106 maximum); DDR3L 0.12 A typical, 0.30 A max; '
      '+15 % core leakage when hot; snapshot idle 0.18 A core, 0.05 A DDR. Measure these on the first board (USB power '
      'meter plus the rail shunts).')
    w('- ESP32-C6: %.0f mA for esp-hosted\'s CPU and SDIO on top of Espressif\'s RX figure; %.0f %% TX airtime at '
      'HT20 MCS7 and %.0f %% radio-on per 10 s in snapshot mode; DTIM beacons %.0f %% awake with power save on; %.0f %% '
      'TX in live view. Espressif\'s figures are at 3.3 V and 25 C; at 3.25 V and 90 C the RF currents are similar, the '
      'sleep floors higher.' % (C6_HOSTED * 1e3, TX_AIR * 100, RADIO_ON * 100, BEACON_DUTY * 100, C6_LIVE_TX * 100))
    w('- SC4336H: streaming split of its 120 mW in the SC4336\'s AVDD / DOVDD ratio; standby 1 mA + 2 mA. The SC4336 '
      'currents are from a third-party summary of its datasheet (the SC4336H datasheet is under NDA).')
    w('- Inductor Irms ratings and DCR (Murata pages not reachable); capacitor DC-bias fractions; switch resistance x1.35 '
      'hot, 4 ns edges, TLV62569 fsw +-20 %, loop crossover 60 kHz for the droop estimates; USB-C contacts and board '
      'copper 0.04 ohm round trip.')
    w('- 850 nm LED: VF 0.15 V lower at 45 mA than at 100 mA, -1.45 mV/K (Vishay), 27 % of its power leaves as light.')
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
    v('**%s** In snapshot mode (the requirement) the camera averages %.2f A by day and %.2f A by night with the '
      'Wi-Fi\'s power save off (the C6 firmware built without tools/c6-power-save.sh) (%.2f / %.2f A once it is on), %.2f A during a night shot: all well inside the '
      'port\'s 1 A. Heat in the case in snapshot mode: %.2f W by day, %.2f W by night (power save off); %.2f / %.2f W '
      'with it on. Live view and the stress bound are reported only.\n'
      % ('PASS with WARNs.' if not fails else '%d FAIL.' % len(fails), sol['snap_day']['i_vsys'],
         sol['snap_night']['i_vsys'], sol['snap_day_ps']['i_vsys'], sol['snap_night_ps']['i_vsys'],
         sol['snap_burst']['i_vsys'], sol['snap_day']['heat_total'], sol['snap_night']['heat_total'],
         sol['snap_day_ps']['heat_total'], sol['snap_night_ps']['heat_total']))
    v('- **Wi-Fi power save off costs %.0f mW** in snapshot mode (the C6 at %.0f mA against %.0f mA with it on): the '
      'C6 is then the second-largest heat source in the case after the RV1106.'
      % ((sol['snap_day']['heat']['U6'] - sol['snap_day_ps']['heat']['U6']) * 1e3, c6_snapshot(False) * 1e3,
         c6_snapshot(True) * 1e3))
    for r in rails():
        lo_, nom_, hi_ = vout_range(*r['div'], r['reg']['vref'])
        v('- %s: %.0fk / %.1fk = %.3f V (%.3f-%.3f) in %.3f-%.3f.' % (r['name'], r['div'][0] / 1e3, r['div'][1] / 1e3,
                                                                    nom_, lo_, hi_, *r['allowed']))
    v('- Regulators carry their worst loads with room (0.9 V %.2f of 2 A; EA3036C channels at most %.2f of 1 A; '
      'Wi-Fi %.2f A peak of 2 A); every inductor peak is under 80 %% of its saturation current.'
      % (loads('worst')['v09'], max(loads('peak')[k] for k in ('v33', 'ddr', 'v18')), loads('peak')['wifi']))
    v('- IR LED strings with %.0f R: %.0f mA nominal, %.0f-%.0f mA over the supply and VF spread; %.3f W per resistor '
      'at the high corner while lit (lit %.0f %% of the time in night snapshots; thermal.md checks its derating).'
      % (rs, nom['i'] * 1e3, lo['i'] * 1e3, hi['i'] * 1e3, hi['pr'], 100 * LED_ON_S / SHOT_S))
    v('- Remaining WARNs: the stress bound against the 1 A port, the LED brightness spread (a constant-current sink '
      'would remove it), L1 / L5 saturating below the TLV62569\'s typical current limit, the VSYS capacitance at hot '
      'plug.')
    v('- Not verified: every snapshot-mode current (ASSUMED: measure idle, shot and upload currents on the first '
      'board, with power save off and on), the SC4336H\'s own currents, the Murata inductor Irms / DCR and DC-bias '
      'curves, the VSMY3850X01 grade\'s ratings.')
    v('')
    return V


def main():
    L, sol = run()
    i = [k for k, x in enumerate(L) if x.startswith('## The Wi-Fi module')][0]
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
