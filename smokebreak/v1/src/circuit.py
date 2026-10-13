"""SmokeBreak v1: the circuit, as code.  Every part, every pin, every net.

The board's design follows ../ARCHITECTURE.md; pin maps were taken from
KiCad's symbol libraries, TI's datasheets and LCSC's symbols (noted where a
pin's role is not obvious).  `check()` fails on any pin left without a net
that is not declared unused, and on any net with only one pin.

    python3 circuit.py        # prints a summary and runs the checks
"""
import parts as P
from parts import resistor as R, cap as C

COMPONENTS = {}     # ref -> dict(part=key, value=str, pins={pin: net}, group=str)


def add(ref, part, pins, value='', group=''):
    assert ref not in COMPONENTS, ref
    COMPONENTS[ref] = dict(part=part, value=value, pins=dict(pins), group=group)
    return ref


_n = {}


def nxt(prefix):
    while True:
        _n[prefix] = _n.get(prefix, 0) + 1
        ref = f'{prefix}{_n[prefix]}'
        if ref not in COMPONENTS:
            return ref


def res(a, b, ohms, size='0402', tol='1%', group='', ref=None):
    return add(ref or nxt('R'), R(ohms, size, tol), {'1': a, '2': b}, P.fmt_ohms(ohms), group)


def capacitor(a, b, value, volts='16V', size='0402', group='', ref=None):
    return add(ref or nxt('C'), C(value, volts, size), {'1': a, '2': b}, f'{value}F {volts}', group)


NC = None   # an unused pin


# ======================================================================
# 1. Battery in: XT60 + XT30 male, TVS, input capacitance
# ======================================================================
# Pad polarity: the pad on the housing's flat (square-cornered) side is +, the
# chamfered side is - (XT convention; Amass drawings and the LCSC 3D models
# place the chamfer).  The pad numbering differs from part to part.
XT = {'XT60M': ('2', '1'), 'XT30M': ('2', '1'), 'XT60F': ('3', '4'), 'XT30F': ('1', '2')}   # (+, -)

g = 'battery in'
add('J1', 'XT60M', {XT['XT60M'][0]: 'VBAT', XT['XT60M'][1]: 'BATT_NEG', '3': NC, '4': NC}, 'XT60 male', g)
add('J2', 'XT30M', {XT['XT30M'][0]: 'VBAT', XT['XT30M'][1]: 'BATT_NEG', '3': NC, '4': NC}, 'XT30 male', g)
# the fire fuse: only a part inside failing shorted ever blows it (the switch
# clears every outside fault thousands of times faster); 40 A so 25 A runs
# at 63 % of its rating, 1000 A interrupting at 80 V DC
add('F1', 'FUSE40', {'1': 'VBAT', '2': 'VIN'}, '40 A 80 V', g)
# reverse-battery switch in the battery's return (sim case 2-4: a reversed 11S-14S
# plug-in would ring the TPS48000's SRC past -65 V without it).  Body diode
# GND -> BATT_NEG carries the first ~10 ms until the gate is up; a reversed pack
# finds the diode and the gate both off.
add('Q11', 'BSC070L', {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'Q11_G',
                       '5': 'BATT_NEG', '6': 'BATT_NEG', '7': 'BATT_NEG', '8': 'BATT_NEG'}, 'BSC070N10LS5', g)
res('VIN', 'Q11_G', 4.7e6, '0603', group=g, ref='R74')                           # ~10 uA from a 14S pack
add('D20', 'BZT52C12', {'1': 'Q11_G', '2': 'GND'}, '12 V', g)
add('D1', 'TVS64', {'1': 'VIN', '2': 'GND'}, 'SMBJ64CA', g)
capacitor('VIN', 'GND', '2u2', '100V', '1210', g)
capacitor('VIN', 'GND', '2u2', '100V', '1210', g)
capacitor('VIN', 'GND', '100n', '100V', '0603', g)
# damper (sim case 2): an RC across the input that eats the ring of a
# hot plug and of a short's turn-off; ceramic, so a reversed pack is fine
res('VIN', 'VIN_DAMP', 0.33, '1206', group=g, ref='R67')
capacitor('VIN_DAMP', 'GND', '4u7', '100V', '1210', g, ref='C50')
capacitor('VIN_DAMP', 'GND', '4u7', '100V', '1210', g, ref='C51')

# ======================================================================
# 2. The switch: TPS48000 + back-to-back BSC040N10NS5, low-side shunt
# ======================================================================
g = 'switch'
# BSC040N10NS5 (TDSON-8): 1-3 source, 4 gate, 5-8 drain (8 also the tab)
Q_S = {'1': 'S', '2': 'S', '3': 'S', '4': 'G', '5': 'D', '6': 'D', '7': 'D', '8': 'D'}
add('Q1', 'BSC040', {p: {'S': 'SRC', 'G': 'GATE', 'D': 'VIN'}[r] for p, r in Q_S.items()}, 'input FET', g)
add('Q2', 'BSC040', {p: {'S': 'SRC', 'G': 'GATE', 'D': 'VOUT'}[r] for p, r in Q_S.items()}, 'output FET', g)
add('U1', 'TPS48000', {
    '1': 'TPS_EN',       # EN/UVLO: divider from VIN, on above ~3.1 V
    '2': 'TPS_OV',       # OV: divider from VIN, cuts above ~64 V
    '3': 'TPS_INP',      # from the AND gate
    '4': 'TPS_FLTGD',    # open drain
    '5': 'TPS_FLT',      # open drain
    '6': 'GND',
    '7': 'TPS_CSSEL',    # > 1.58 V: low-side current sense
    '8': 'TPS_ISCP',
    '9': NC,             # TMR open: fastest short-circuit response (4 us)
    '10': 'TPS_SCPTEST',
    '11': NC,
    '12': 'TPS_BST',
    '13': 'SRC',
    '14': 'GATE',        # PD straight to the gates: fastest turn-off
    '15': 'TPS_PU',      # PU through a resistor: turn-on slew
    '17': 'SNS_GND',     # CS-: shunt sense, ground side
    '18': 'SNS_DRN',     # CS+: shunt sense, drone side
    '19': NC,
    '20': 'TPS_VS',
}, 'TPS48000', g)
res('VIN', 'TPS_VS', 10, '0603', group=g)
capacitor('TPS_VS', 'GND', '100n', '100V', '0603', g)
res('VIN', 'TPS_EN', 1e6, '0603', group=g)
res('TPS_EN', 'GND', 470e3, group=g)
res('VIN', 'TPS_OV', 1e6, '0603', group=g)
res('TPS_OV', 'GND', 19.6e3, group=g)          # OV = 1.23 V x (1 + 1M / 19.6k) = 64.0 V: just above the firmware's 62.5 V refusal
capacitor('TPS_BST', 'SRC', '1u', '25V', '0603', g)
res('TPS_PU', 'GATE', 100e3, group=g)         # slow turn-on with Cdvdt (sim case 1b)
res('GATE', 'SRC', 1e6, group=g)               # gates held off if the driver is unpowered
res('+3V3', 'TPS_CSSEL', 10e3, group=g)
res('TPS_ISCP', 'GND', 40.2e3, group=g)       # (99 A x 1 mOhm - 19 mV) / 2 uA: the last line of defence
# Cdvdt: gate to ground through 1 k (sim case 1b), and a 15 V gate clamp
res('GATE', 'CDVDT', 1e3, group=g, ref='R69')
capacitor('CDVDT', 'GND', '22n', '50V', '0402', g, ref='C54')
add('D18', 'BZT52C15', {'1': 'GATE', '2': 'SRC'}, '15 V', g)
res('TPS_SCPTEST', 'GND', 100e3, group=g)
res('TPS_FLT', '+3V3', 10e3, group=g)
res('TPS_FLTGD', '+3V3', 10e3, group=g)
res('TPS_INP', 'GND', 100e3, group=g)

# low-side shunt in the drone's return: pads 1 (force) + 2 (sense) one end,
# 4 (force) + 3 (sense) the other
add('RS1', 'SHUNT1M', {'1': 'DRONE_NEG', '2': 'SNS_DRN', '4': 'GND', '3': 'SNS_GND'}, '1 mOhm', g)

# ======================================================================
# 3. Current: INA181A2 on the same shunt, comparator, latch, enable gate
# ======================================================================
g = 'current'
res('SNS_DRN', 'INA_P', 10, group=g)
res('SNS_GND', 'INA_N', 10, group=g)
capacitor('INA_P', 'INA_N', '1n', '50V', '0402', g)
# low side: the common mode sits at ground, so a 26 V part does; firmware
# auto-zeroes its offset with the switch open before every arm
add('U2', 'INA181A2', {'1': 'I_SENSE', '2': 'GND', '3': 'INA_P', '4': 'INA_N', '5': 'GND', '6': '+3V3'},
    'INA181A2', g)
capacitor('+3V3', 'GND', '100n', group=g)
res('I_SENSE', 'I_ADC', 100, group=g)
capacitor('I_ADC', 'GND', '1n', '50V', '0402', g)
# peak comparator: trip when I_SENSE > PEAK_REF (MCU DAC)
res('PEAK_DAC', 'PEAK_REF', 1e3, group=g)
capacitor('PEAK_REF', 'GND', '10n', '50V', '0402', g)
add('U8', 'LMV331', {'1': 'PEAK_REF', '2': 'GND', '3': 'I_SENSE', '4': 'PEAK_OK', '5': '+3V3'}, 'LMV331', g)
res('PEAK_OK', '+3V3', 10e3, group=g, ref='R66')    # open-drain output (late ref: keeps the others)
# hard-short comparator straight on the shunt: 65 mV = 65 A, no amplifier
# slew in the way (sim case 3); wired onto the same latch-clear node
add('U12', 'LMV331', {'1': 'HS_REF', '2': 'GND', '3': 'SNS_DRN', '4': 'PEAK_OK', '5': '+3V3'}, 'LMV331', g)
res('+3V3', 'HS_REF', 49.9e3, group=g, ref='R70')
res('HS_REF', 'GND', 1e3, group=g, ref='R71')                                  # 64.7 mV = 65 A
capacitor('HS_REF', 'GND', '100n', group=g, ref='C55')
capacitor('+3V3', 'GND', '100n', group=g, ref='C56')
capacitor('+3V3', 'GND', '100n', group=g)
# latch: PEAK_OK low clears Q; the MCU re-arms with a clock edge
add('U9', 'LVC1G74', {'1': 'ARM_CLK', '2': '+3V3', '3': NC, '4': 'GND', '5': 'LATCH_OK', '6': 'PEAK_OK',
                      '7': '+3V3', '8': '+3V3'}, 'SN74LVC1G74', g)
capacitor('+3V3', 'GND', '100n', group=g)
# INP = MCU_EN AND GUARD_OPEN AND LATCH_OK
add('U7', 'LVC1G11', {'1': 'MCU_EN', '3': 'GUARD_OPEN', '6': 'LATCH_OK', '4': 'TPS_INP', '5': '+3V3', '2': 'GND'},
    '74LVC1G11', g)
capacitor('+3V3', 'GND', '100n', group=g)
res('MCU_EN', 'GND', 100e3, group=g)
# guard: the hall switch reads LOW with the guard's magnet over it
add('U6', 'DRV5032', {'1': '+3V3', '2': 'GUARD_OPEN', '3': 'GND'}, 'DRV5032FA', g)
capacitor('+3V3', 'GND', '100n', group=g)

# ======================================================================
# 4. Pre-charge: P-FET + Schottky + 2 x 3.9 Ohm 5 W in series, cut by the guard too
# ======================================================================
g = 'pre-charge'
add('Q3', 'SUD50P10', {'1': 'PRE_G', '2': 'PRE_D', '3': 'VIN'}, 'SUD50P10-43L', g)
add('D2', 'BZT52C10', {'1': 'VIN', '2': 'PRE_G'}, '10 V', g)                    # Vgs clamp: K at source
res('VIN', 'PRE_G', 100e3, '0603', group=g)
res('PRE_G', 'PRE_R', 47e3, '0805', group=g)                                  # ~1.2 mA at 60 V, 75 mW
add('D19', '1N4148WS', {'1': 'PRE_PULL', '2': 'PRE_R'}, '1N4148WS', g)           # a reversed pack cannot pull PRE_ON
# two NPNs in series: the MCU AND the guard must both say go
add('Q4', 'MMBTA42', {'1': 'PRE_B1', '3': 'PRE_PULL', '2': 'PRE_MID'}, 'MMBTA42', g)
add('Q5', 'BC817', {'1': 'PRE_B2', '3': 'PRE_MID', '2': 'GND'}, 'BC817', g)
res('PRE_ON', 'PRE_B1', 10e3, group=g)
res('GUARD_OPEN', 'PRE_B2', 10e3, group=g)
res('PRE_B1', 'GND', 100e3, group=g)
res('PRE_B2', 'GND', 100e3, group=g)
add('D3', 'SS2H10', {'1': 'PRE_K', '2': 'PRE_D'}, 'SS2H10', g)                # A at the FET, K to the resistor
# two 3.9 Ohm in series = 7.8 Ohm (sim case 1: 6.8-8.2 Ohm passes); each
# takes half the energy (6 J of the 12 J abort; the D2TO20's single-pulse
# curve gives ~10 J at 100 ms).  Flat TO-263 (4.5 mm): they fit under the
# screen.  Pins 1 and 3 are the element; the tab (2) is isolated, left to
# its own copper for the heat
add('R_PRE', 'D2TO20R3R9', {'1': 'PRE_K', '3': 'PRE_M', '2': NC}, '3.9 Ohm 20 W', g)
add('R_PRE2', 'D2TO20R3R9', {'1': 'PRE_M', '3': 'VOUT', '2': NC}, '3.9 Ohm 20 W', g)
add('RT2', 'NTC10K', {'1': 'NTC_PRE', '2': 'GND'}, '10 k NTC', g)
res('+3V3', 'NTC_PRE', 10e3, group=g)

# ======================================================================
# 5. Drone out: XT60 + XT30 female, 3 V probe, sensing
# ======================================================================
g = 'drone out'
# the drone leads: female XT60 and XT30 on short pigtails, soldered to pads
add('J3', 'XT60F_LEAD', {'1': 'VOUT', '2': 'DRONE_NEG'}, 'XT60 female lead', g)
add('J4', 'XT30F_LEAD', {'1': 'VOUT', '2': 'DRONE_NEG'}, 'XT30 female lead', g)
capacitor('VOUT', 'DRONE_NEG', '100n', '100V', '0603', g)
# output snubber (sim cases 3, 5): damps the drone-side ring after a cut and on plug-in
res('VOUT', 'VOUT_SNUB', 0.47, '0805', group=g, ref='R68')                     # 0.47: 0.22 lets a reversed drone-side 14S pull SRC to -70 V
capacitor('VOUT_SNUB', 'DRONE_NEG', '4u7', '100V', '1210', g, ref='C52')
capacitor('VOUT_SNUB', 'DRONE_NEG', '4u7', '100V', '1210', g, ref='C53')
# probe: 3.3 V through 1 k or 100 Ohm, then a 100 V Schottky into VOUT.
# 150 V PNPs: a reversed pack on the drone side puts -60 V on them
add('Q6', 'MMBT5401', {'1': 'PROBE_BB1', '2': '+3V3', '3': 'PROBE_A'}, 'MMBT5401', g)
add('Q7', 'MMBT5401', {'1': 'PROBE_BB2', '2': '+3V3', '3': 'PROBE_B'}, 'MMBT5401', g)
res('PROBE_BB1', '+3V3', 100e3, group=g)
res('PROBE_BB2', '+3V3', 100e3, group=g)
res('PROBE_1K_N', 'PROBE_BB1', 4.7e3, group=g, ref='R72')                      # 0.5 mA base for 3 mA
res('PROBE_100_N', 'PROBE_BB2', 820, group=g, ref='R73')                       # 3 mA base for 30 mA
res('PROBE_A', 'PROBE', 1e3, '0603', group=g)
res('PROBE_B', 'PROBE', 100, '0805', group=g)
add('D4', 'BAT46WJ', {'1': 'VOUT', '2': 'PROBE'}, 'BAT46WJ', g)
# VOUT 0-66 V and 0-3.3 V (clamped) for the probe
res('VOUT', 'VOUT_SENSE', 1e6, '0603', group=g)
res('VOUT_SENSE', 'GND', 52.3e3, group=g)
capacitor('VOUT_SENSE', 'GND', '100n', group=g)
res('VOUT', 'VOUT_LO', 100e3, '0603', group=g)
add('D5', 'BAT54S', {'1': 'GND', '2': '+3V3', '3': 'VOUT_LO'}, 'BAT54S', g)
capacitor('VOUT_LO', 'GND', '1n', '50V', '0402', g)
# VIN 0-66 V
res('VIN', 'VIN_SENSE', 1e6, '0603', group=g)
res('VIN_SENSE', 'GND', 52.3e3, group=g)
capacitor('VIN_SENSE', 'GND', '100n', group=g)
add('RT1', 'NTC10K', {'1': 'NTC_FET', '2': 'GND'}, '10 k NTC', g)
res('+3V3', 'NTC_FET', 10e3, group=g)

# ======================================================================
# 6. Balance lead: one JST-XH socket per size, 2S-6S, 0.1 % dividers,
#    switched ground, OR into AUX
# ======================================================================
g = 'balance'
BAL = {}
# a plug only fits its own socket, so it cannot sit a pin off; pin k of every
# socket is tap k (pin 1 the black wire)
for ref, cells in (('J5', 6), ('J9', 5), ('J10', 4), ('J11', 3), ('J12', 2)):
    add(ref, f'XHT{cells + 1}', {str(k): f'BAL{k}' for k in range(1, cells + 2)}, f'JST-XH {cells}S', g)
BALANCE_MAX = 6
# the black wire meets ground through 10 Ohm: with the main lead plugged in too,
# the balance lead's thin wire then carries a few mA of the return, not amps
res('BAL1', 'GND', 10, '1206', group=g, ref='R75')
TOPS = {2: 47e3, 3: 200e3, 4: 357e3, 5: 499e3, 6: 649e3, 7: 787e3}
for k in range(2, BALANCE_MAX + 2):
    res(f'BAL{k}', f'BAL{k}_ADC', TOPS[k], '0402', '0.1%', g)       # 25 V at most: 0402 is rated 50 V
    res(f'BAL{k}_ADC', 'DIV_GND', 100e3, '0402', '0.1%', g)
    capacitor(f'BAL{k}_ADC', 'DIV_GND', '100n', group=g)
    add(nxt('D'), '1N4148WS', {'1': 'AUX', '2': f'BAL{k}'}, '1N4148WS', g)
# the 7S and 8S taps of the old 9-pin socket are gone: their designators stay
# unused so every later part keeps its name
for prefix, n in (('R', 4), ('C', 2), ('D', 2)):
    for _ in range(n):
        nxt(prefix)
add('Q8', '2N7002', {'1': 'DIV_EN', '2': 'GND', '3': 'DIV_GND'}, '2N7002', g)
res('DIV_EN', 'GND', 100e3, group=g)

# ======================================================================
# 7. Aux supply: OR of VIN, VOUT, balance, USB -> 5 V buck -> 3.3 V LDO
# ======================================================================
g = 'supply'
add(nxt('D'), 'BAT46WJ', {'1': 'AUX', '2': 'VIN'}, 'BAT46WJ', g)      # Schottky: a 1S pack must still reach the buck's 3.6 V
add(nxt('D'), '1N4148WS', {'1': 'AUX', '2': 'VOUT'}, '1N4148WS', g)
add(nxt('D'), 'BAT46WJ', {'1': '+5V', '2': 'VBUS'}, 'BAT46WJ', g)    # USB feeds the 5 V rail directly (the buck needs 6 V)
res('AUX', 'AUX_F', 10, '0805', group=g)
capacitor('AUX_F', 'GND', '2u2', '100V', '1210', g)
capacitor('AUX_F', 'GND', '100n', '100V', '0603', g)
# LM5164: 6-100 V in (a 2S pack at 3 V/cell still runs it; a 24S pack plugged
# in by mistake cannot hurt it).  COT, 400 kHz: RON = 5 V x 2500 / 400 kHz.
# Type-3 ripple injection (RA, CA from SW, CB into FB): low output ripple.
add('U3', 'LM5164', {'1': 'GND', '2': 'AUX_F', '3': 'AUX_F', '4': 'BUCK_RON', '5': 'BUCK_FB',
                     '6': 'GND', '7': 'BUCK_BOOT', '8': 'BUCK_SW', '9': 'GND'}, 'LM5164DDAR', g)
capacitor('BUCK_RA', '+5V', '3n3', '50V', '0402', g)                             # CA (was the LMR's VCC cap)
capacitor('BUCK_BOOT', 'BUCK_SW', '2n2', '50V', '0402', g)                       # CBST: 2.2 nF max (datasheet)
add('L1', 'L47U6045', {'1': 'BUCK_SW', '2': '+5V'}, '47 uH', g)
res('BUCK_RON', 'GND', 30.9e3, group=g, ref='R76')
res('+5V', 'BUCK_FB', 453e3, group=g, ref='R77')                                # 1.2 V x (1 + 453/143) = 5.00 V
res('BUCK_FB', 'GND', 143e3, group=g, ref='R78')
res('BUCK_SW', 'BUCK_RA', 100e3, group=g, ref='R79')                             # RA: RA x CA = 330 us < 489 us
capacitor('BUCK_RA', 'BUCK_FB', '56p', '50V', '0402', g, ref='C57')              # CB >= 47 pF
capacitor('+5V', 'GND', '10u', '10V', '0805', g)
capacitor('+5V', 'GND', '10u', '10V', '0805', g)
add('U4', 'TLV75533', {'1': '+5V', '3': '+5V', '2': 'GND', '4': NC, '5': '+3V3'}, 'TLV75533', g)
capacitor('+3V3', 'GND', '1u', '25V', '0603', g)
capacitor('+3V3', 'GND', '4u7', '10V', '0603', g)

# ======================================================================
# 8. MCU: STM32G0B1RBT6 (LQFP-64)
# ======================================================================
g = 'mcu'
MCU = {
    # power
    '6': '+3V3', '7': '+3V3', '8': '+3V3', '9': 'GND',
    '12': 'NRST',                     # PF2-NRST
    # analog
    '17': 'VIN_SENSE', '18': 'VOUT_SENSE', '19': 'VOUT_LO', '20': 'I_ADC', '21': 'PEAK_DAC',
    '22': 'NTC_FET', '23': 'NTC_PRE',
    '24': 'BAL2_ADC', '27': 'BAL3_ADC', '28': 'BAL4_ADC', '29': 'BAL5_ADC', '30': 'BAL6_ADC',
    '31': 'BAL7_ADC', '26': 'VBUS_SENSE',
    # inputs
    '13': 'TOG_ON', '14': 'TOG_BIND', '15': 'BTN_MINUS', '16': 'BTN_PLUS', '3': 'GUARD_OPEN',
    '64': 'TPS_FLT', '1': 'TPS_FLTGD', '61': 'PEAK_OK',
    # outputs
    '58': 'MCU_EN', '60': 'ARM_CLK', '2': 'TPS_SCPTEST', '50': 'PRE_ON', '51': 'PROBE_1K_N',
    '52': 'PROBE_100_N', '53': 'DIV_EN', '36': 'BUZZER',
    # display (SPI2) and LEDs (SPI1 MOSI)
    '33': 'LCD_SCK', '34': 'LCD_CS', '35': 'LCD_SDA', '38': 'LCD_DC', '39': 'LCD_RST', '48': 'LCD_BL',
    '59': 'LED_DATA',
    # USB, SWD
    '43': 'USB_DM', '44': 'USB_DP', '45': 'SWDIO', '46': 'SWCLK',
}
for pin in range(1, 65):
    MCU.setdefault(str(pin), NC)
add('U5', 'STM32G0B1', MCU, 'STM32G0B1RBT6', g)
for _ in range(3):
    capacitor('+3V3', 'GND', '100n', group=g)
capacitor('+3V3', 'GND', '4u7', '10V', '0603', g)
capacitor('NRST', 'GND', '100n', group=g)
add('J6', 'SWDPADS', {'1': '+3V3', '2': 'SWDIO', '3': 'NRST', '4': 'SWCLK', '5': 'GND'}, 'SWD', g)

# ======================================================================
# 9. User interface: toggle, rocker, display, LEDs, buzzer, USB
# ======================================================================
g = 'controls'
# toggle: 2 common; On (latching) joins 2-3, Bind (momentary) joins 2-1
add('SW1', 'TOGGLE', {'2': 'GND', '3': 'TOG_ON', '1': 'TOG_BIND'}, 'ON-OFF-(ON)', g)
res('TOG_ON', '+3V3', 1e3, group=g)            # ~3 mA wets the silver contacts
res('TOG_BIND', '+3V3', 1e3, group=g)
capacitor('TOG_ON', 'GND', '10n', '50V', '0402', g)
capacitor('TOG_BIND', 'GND', '10n', '50V', '0402', g)
add('SW2', 'B3U', {'1': 'BTN_MINUS', '2': 'GND'}, 'Limit -', g)
add('SW3', 'B3U', {'1': 'BTN_PLUS', '2': 'GND'}, 'Limit +', g)

g = 'display'
# ER-TFT2.25-1 FPC: 1 LEDA, 2 GND, 3 RESET, 4 RS (D/C), 5 SDA, 6 SCL, 7 VDD, 8 CS
LCD = {'1': 'LCD_LEDA', '2': 'GND', '3': 'LCD_RST', '4': 'LCD_DC', '5': 'LCD_SDA', '6': 'LCD_SCK',
       '7': '+3V3', '8': 'LCD_CS', 'MP': 'GND'}
add('J7', 'FH12_8', LCD, 'ER-TFT2.25-1 FPC', g)
capacitor('+3V3', 'GND', '1u', '25V', '0603', g)
# backlight: four LEDs in parallel, cathodes on the panel's GND, ~60 mA total
# at 3.0 V: a high-side P-FET from 5 V and 33 Ohm, PWM from the MCU through
# an N-FET level shifter
res('BL_SW', 'LCD_LEDA', 33, '1206', group=g)                                   # (5 - 3.0) / 33 = 61 mA, 0.12 W
for _ in range(3):
    nxt('R')                       # R57-R59 (the old per-LED resistors) stay unused
add('Q9', 'AO3401A', {'1': 'BL_G', '2': '+5V', '3': 'BL_SW'}, 'AO3401A', g)
res('LCD_BL', 'GND', 100e3, group=g)
res('+5V', 'BL_G', 100e3, group=g, ref='R80')
add('Q12', '2N7002', {'1': 'LCD_BL', '2': 'GND', '3': 'BL_G'}, '2N7002', g)
add('X1', 'TFT225', {}, 'ER-TFT2.25-1 (plugs into J7)', g)

g = 'status ring'
add('U10', 'AHCT1G125', {'1': 'GND', '2': 'LED_DATA', '3': 'GND', '4': 'LED_DIN0', '5': '+5V'}, 'SN74AHCT1G125', g)
capacitor('+5V', 'GND', '100n', group=g)
prev = 'LED_DIN0'
for i in range(1, 13):
    nxt_net = f'LED_D{i}' if i < 12 else NC
    din = prev
    add(f'LED{i}', 'WS2812', {'1': nxt_net, '2': 'GND', '3': din, '4': '+5V'}, 'WS2812B-2020', g)
    prev = nxt_net
    if i % 2 == 0:
        capacitor('+5V', 'GND', '100n', group=g)

g = 'buzzer'
add('BZ1', 'MLT8530', {'1': '+5V', '2': 'BZ_N', '3': NC, '4': NC}, 'MLT-8530', g)
add('Q10', 'BC817', {'1': 'BZ_B', '3': 'BZ_N', '2': 'GND'}, 'BC817', g)
res('BUZZER', 'BZ_B', 1e3, group=g)
add(nxt('D'), '1N4148WS', {'1': '+5V', '2': 'BZ_N'}, '1N4148WS', g)

g = 'usb'
add('J8', 'USBC', {'A1B12': 'GND', 'B1A12': 'GND', 'A4B9': 'VBUS', 'B4A9': 'VBUS', 'A5': 'USB_CC1', 'B5': 'USB_CC2',
                   'A6': 'USB_DP_C', 'B6': 'USB_DP_C', 'A7': 'USB_DM_C', 'B7': 'USB_DM_C', 'A8': NC, 'B8': NC,
                   '1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND'}, 'USB-C', g)
res('USB_CC1', 'GND', 5.1e3, group=g)
res('USB_CC2', 'GND', 5.1e3, group=g)
add('U11', 'USBLC6', {'1': 'USB_DP_C', '6': 'USB_DP', '3': 'USB_DM_C', '4': 'USB_DM', '2': 'GND', '5': 'VBUS'},
    'USBLC6-2SC6', g)
res('VBUS', 'VBUS_SENSE', 100e3, group=g)
res('VBUS_SENSE', 'GND', 100e3, group=g)
capacitor('VBUS', 'GND', '1u', '25V', '0603', g)

# mounting holes
for i in range(1, 4):              # three M3: the screen covers the board's back-left
    add(f'H{i}', 'HOLE', {'1': NC}, 'M3', 'mechanical')


# ======================================================================
def nets():
    out = {}
    for ref, c in COMPONENTS.items():
        for pin, net in c['pins'].items():
            if net is not None:
                out.setdefault(net, []).append((ref, pin))
    return out


def check():
    errs = []
    for net, members in nets().items():
        if len(members) < 2:
            errs.append(f'net {net} has one pin: {members}')
    for ref, c in COMPONENTS.items():
        if c['part'] not in P.PARTS:
            errs.append(f'{ref}: unknown part {c["part"]}')
    return errs


if __name__ == '__main__':
    e = check()
    n = nets()
    print(f'{len(COMPONENTS)} parts, {len(n)} nets')
    from collections import Counter
    print(Counter(P.PARTS[c['part']]['fit'] for c in COMPONENTS.values()))
    print('\n'.join(e) if e else 'checks: OK')
