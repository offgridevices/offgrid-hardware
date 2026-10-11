"""Every part on the SmokeBreak v1 board, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the
manufacturer and manufacturer part number (MPN) PCBWay buys from, the LCSC
number where LCSC stocks it, a description, and how it is fitted:

  smt   placed by PCBWay (top side only: one-sided assembly)
  tht   through-hole, hand-soldered by the owner (connectors, toggle,
        pre-charge resistor)
  off   not on the board: bought and fitted separately (the display panel,
        it plugs into J7)

Special parts' footprints and 3D models come from LCSC's own library
(easyeda2kicad, ../lib/smokebreak.pretty); passives use KiCad's standard
footprints.  Part research and prices: ../docs/PARTS.md.
"""

LIB = 'smokebreak'
STD_R = {'0402': 'Resistor_SMD:R_0402_1005Metric', '0603': 'Resistor_SMD:R_0603_1608Metric',
         '0805': 'Resistor_SMD:R_0805_2012Metric', '1206': 'Resistor_SMD:R_1206_3216Metric'}
STD_C = {'0402': 'Capacitor_SMD:C_0402_1005Metric', '0603': 'Capacitor_SMD:C_0603_1608Metric',
         '0805': 'Capacitor_SMD:C_0805_2012Metric', '1206': 'Capacitor_SMD:C_1206_3216Metric',
         '1210': 'Capacitor_SMD:C_1210_3225Metric'}


def P(fp, mfr, mpn, lcsc, desc, fit='smt'):
    return dict(fp=None if fp is None else (fp if ':' in fp else f'{LIB}:{fp}'), mfr=mfr, mpn=mpn, lcsc=lcsc, desc=desc, fit=fit)


PARTS = {
    # ---------------------------------------------------------- power path
    'TPS48000':  P('VSSOP-19_L5.1-W3.0-P0.50-LS4.9', 'Texas Instruments', 'TPS48000QDGXRQ1', 'C43131315',
                   'Smart high-side driver, 3.5-95 V, -65 V reverse, low-side sense, SCP'),
    'BSC040':    P('PG-TDSON-8_L5.9-W5.1-P1.27-LS6.1-BL', 'Infineon', 'BSC040N10NS5', 'C534334',
                   'N-MOSFET 100 V 4.0 mOhm, SuperSO8'),
    'SHUNT1M':   P('RES-SMD_4P-L3.8-W3.1', 'Vishay Dale', 'WSK12161L000FEA', 'C844476',
                   'Current shunt 1 mOhm 1 % 3 W, four-terminal 1216'),
    'INA181A2':  P('SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', 'Texas Instruments', 'INA181A2IDBVR', 'C2058784',
                   'Current-sense amplifier, gain 50, -0.2..26 V CM (low side: CM ~0 V)'),
    'TVS64':     P('SMB_L4.6-W3.6-LS5.3-BI', 'Littelfuse', 'SMBJ64CA', 'C151269',
                   'TVS bidirectional 58 V stand-off, 600 W, SMB'),
    'DMP10H':    P('SOT-223_L6.5-W3.5-P2.30-LS7.0-BR', 'Diodes Incorporated', 'DMP10H400SE-13', 'C156277',
                   'P-MOSFET -100 V 250 mOhm, SOT-223 (pre-charge switch)'),
    'RPRE22':    P('RES-TH_BD7.5-L18.0-P22.00-D1.0', 'Vishay', 'AC05000002209JAC00', 'C1364873',
                   'Resistor 22 Ohm 5 W cemented wirewound, pulse rated (pre-charge)', fit='tht'),
    'SS2H10':    P('Diode_SMD:D_SMA', 'Vishay', 'SS2H10-E3/52T', None,
                   'Schottky 100 V 2 A, SMA (pre-charge reverse block)'),
    # ---------------------------------------------------------- aux supply
    'LMR36506':  P('VQFN-9_L2.1-W2.1-P0.50-TL', 'Texas Instruments', 'LMR36506R5RPER', 'C2866484',
                   'Buck 3.6-65 V in, 5 V fixed, 600 mA (pin-compatible with LMR36503R5)'),
    'L47U':      P('IND-SMD_L4.0-W4.0_SLS3DXX', 'Sunlord', 'SWPA4030S470MT', 'C54731',
                   'Inductor 47 uH 4x4x3 mm'),
    'TLV75533':  P('SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', 'Texas Instruments', 'TLV75533PDBVR', 'C404027',
                   'LDO 3.3 V 500 mA'),
    # ---------------------------------------------------------- logic
    'STM32G0B1': P('LQFP-64_L10.0-W10.0-P0.50-LS12.0-BL', 'STMicroelectronics', 'STM32G0B1RBT6', 'C5143679',
                   'MCU Cortex-M0+ 64 MHz, 128 KB flash, 144 KB RAM, USB crystal-less, LQFP-64 '
                   '(STM32G0B1RET6 / RCT6 fit the same pads)'),
    'DRV5032':   P('SOT-23-3_L2.9-W1.3-P0.95-LS2.4-BR', 'Texas Instruments', 'DRV5032FADBZR', 'C140921',
                   'Hall switch, omnipolar, push-pull, 1.3 uA (guard magnet)'),
    'LVC1G11':   P('SC-88-6_L2.0-W1.3-P0.65-LS2.1-BL', 'Nexperia', '74LVC1G11GW,125', 'C282348',
                   '3-input AND gate (switch enable)'),
    'LMV331':    P('SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', 'Texas Instruments', 'LMV331IDBVR', 'C34731',
                   'Comparator, open drain, ~200 ns (peak current)'),
    'LVC1G74':   P('SSOP-8_L2.0-W2.3-P0.50-LS3.1-BR', 'Texas Instruments', 'SN74LVC1G74DCUR', 'C70285',
                   'D flip-flop with clear (peak-trip latch)'),
    'AHCT1G125': P('Package_TO_SOT_SMD:SOT-23-5', 'Texas Instruments', 'SN74AHCT1G125DBVR', None,
                   'Buffer 5 V, TTL inputs (LED data level shift)'),
    # ---------------------------------------------------------- small discretes
    'BAT46WJ':   P('SOD-323F_L2.0-W1.6-LS2.5-RD', 'Nexperia', 'BAT46WJ,115', 'C114696',
                   'Schottky 100 V 250 mA, SOD-323F'),
    'BAT54S':    P('SOT-23-3_L3.0-W1.7-P0.95-LS2.9-BR', 'Nexperia', 'BAT54S,215', 'C47546',
                   'Dual series Schottky 30 V (ADC clamp)'),
    '1N4148WS':  P('SOD-323_L1.8-W1.3-LS2.5-RD', 'Jiangsu Changjing (CJ)', '1N4148WS', 'C2128',
                   'Switching diode 100 V / 75 V working, SOD-323 (supply and balance OR)'),
    'BZT52C10':  P('SOD-123_L2.7-W1.6-LS3.7-RD', 'Diodes Incorporated', 'BZT52C10-7-F', 'C155227',
                   'Zener 10 V (P-FET gate clamp)'),
    '2N7002':    P('SOT-23_L2.9-W1.3-P1.90-LS2.4-BR', 'Nexperia', '2N7002,215', 'C65189',
                   'N-MOSFET 60 V small signal'),
    'BC817':     P('SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR', 'Nexperia', 'BC817-40,215', 'C52801',
                   'NPN 45 V 500 mA'),
    'AO3401A':   P('SOT-23_L2.9-W1.3-P1.90-LS2.4-BR', 'Alpha & Omega', 'AO3401A', 'C15127',
                   'P-MOSFET -30 V (3 V probe source)'),
    'AO3400A':   P('SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', 'Alpha & Omega', 'AO3400A', 'C20917',
                   'N-MOSFET 30 V (backlight PWM)'),
    'NTC10K':    P('R0402', 'Murata', 'NCP15XH103F03RC', 'C77131', 'NTC 10 k 1 % B3380, 0402'),
    # ---------------------------------------------------------- user interface
    'WS2812':    P('LED-SMD_4P-L2.2-W2.0-P1.00_WS2815C-2020-4P', 'Worldsemi', 'WS2812B-2020-V6', 'C52917434',
                   'Addressable RGB LED 2020 (status ring)'),
    'MLT8530':   P('BUZ-SMD_4P-L8.5-W8.5-P8.50-BR', 'Jiangsu Huaneng', 'MLT-8530', 'C94599',
                   'Magnetic buzzer 8.5 mm, 80 dB @ 10 cm'),
    'B3U':       P('KEY-SMD_B3U-1000PM', 'Omron', 'B3U-1000P', 'C231329', 'Tact switch 3 x 2.5 mm (Limit rocker)'),
    'TOGGLE':    P('SW_Toggle_SPDT_P4.70mm_THT', 'C&K', '7107SYCQE', None,
                   'Toggle ON-OFF-(ON), 1/4-40, PC pins (alternates: NKK MN19SS1W03, '
                   'E-Switch 100SP5T1B1M2QEH)', fit='tht'),
    'FH34_30':   P('FFC-SMD_30P-P0.50_FH34SRJ-30S-0.5SH', 'Hirose', 'FH34SRJ-30S-0.5SH(50)', 'C324727',
                   'FPC connector 30 pin 0.5 mm, dual contact (display)'),
    'TFT1901':   P(None, 'QDtech', 'TFT1901', None,
                   'Display 1.9" IPS 170x320 ST7789, 30-pin FPC (plugs into J7)', fit='off'),
    # ---------------------------------------------------------- connectors
    'XT60M':     P('CONN-TH_XT60PW-M', 'Amass', 'XT60PW-M', 'C98732', 'XT60 male, PCB horizontal (battery)', fit='tht'),
    'XT30M':     P('CONN-TH_XT30PW-M', 'Amass', 'XT30PW-M30.G.Y', 'C431092', 'XT30 male, PCB horizontal (battery)', fit='tht'),
    'XT60F':     P('TH_2P-XT60PW-F', 'Amass', 'XT60PW-F', 'C428722', 'XT60 female, PCB horizontal (drone)', fit='tht'),
    'XT30F':     P('CONN-TH_XT30PW-F30.G.Y', 'Amass', 'XT30PW-F30.G.Y', 'C30170176', 'XT30 female, PCB horizontal (drone)', fit='tht'),
    'XH9':       P('CONN-TH_S9B-XH-A-LF-SN', 'JST', 'S9B-XH-A(LF)(SN)', 'C157911', 'JST-XH 9 pin side entry (balance)', fit='tht'),
    'USBC':      P('USB-C_SMD-TYPE-C-31-M-12_1', 'Korean Hroparts', 'TYPE-C-31-M-12', 'C165948', 'USB-C receptacle 16 pin'),
    'USBLC6':    P('SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', 'STMicroelectronics', 'USBLC6-2SC6', 'C7519', 'USB ESD protection'),
    'TC2030':    P('Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical', None, None, None,
                   'SWD programming pads (Tag-Connect TC2030-IDC-NL), no part', fit='none'),
    'HOLE':      P('MountingHole:MountingHole_2.7mm_M2.5', None, None, None, 'M2.5 mounting hole', fit='none'),
}

# ---------------------------------------------------------------- passives
# Yageo resistors (RC = 1 %, RT = 0.1 % thin film), Samsung MLCCs.
RES_SERIES = {'1%': 'RC{size}FR-07{val}L', '0.1%': 'RT{size}BRD07{val}L'}


def yageo_value(ohms):
    """'4K7', '100R', '1M1' style values as Yageo writes them in MPNs."""
    for unit, k in (('M', 1e6), ('K', 1e3)):
        if ohms >= k:
            v = ohms / k
            whole = int(v)
            frac = round((v - whole) * 100)
            if frac == 0:
                return f'{whole}{unit}'
            s = f'{v:.3g}'.replace('.', unit)
            return s
    v = ohms
    if v == int(v):
        return f'{int(v)}R'
    return f'{v:g}'.replace('.', 'R')


def resistor(ohms, size='0402', tol='1%'):
    key = f'R{size}-{ohms:g}-{tol}'
    if key not in PARTS:
        mpn = RES_SERIES[tol].format(size=size, val=yageo_value(ohms))
        PARTS[key] = P(STD_R[size], 'Yageo', mpn, None, f'Resistor {fmt_ohms(ohms)} {tol} {size}')
    return key


CAPS = {
    ('100n', '16V', '0402'): 'CL05B104KO5NNNC',
    ('1n', '50V', '0402'): 'CL05B102KB5NNNC',
    ('10n', '50V', '0402'): 'CL05B103KB5NNNC',
    ('1u', '25V', '0402'): 'CL05A105KA5NQNC',
    ('1u', '25V', '0603'): 'CL10A105KA8NNNC',
    ('4u7', '10V', '0603'): 'CL10A475KP8NNNC',
    ('10u', '10V', '0805'): 'CL21A106KPFNNNE',
    ('100n', '100V', '0603'): 'CL10B104KC8NNNC',
    ('1u', '100V', '1206'): 'CL31B105KCHNNNE',
    ('2u2', '100V', '1210'): 'CL32B225KCJSNNE',
}


def cap(value, volts, size):
    key = f'C{size}-{value}-{volts}'
    if key not in PARTS:
        PARTS[key] = P(STD_C[size], 'Samsung Electro-Mechanics', CAPS[(value, volts, size)], None,
                       f'Capacitor {value}F {volts} {size} X7R/X5R')
    return key


def fmt_ohms(o):
    if o >= 1e6:
        return f'{o / 1e6:g} M'
    if o >= 1e3:
        return f'{o / 1e3:g} k'
    return f'{o:g} Ohm'
