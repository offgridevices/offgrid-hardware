"""Canary v1 — the circuit, in code.

Every part, its manufacturer part number, footprint and the net on each pin.
The schematic (schematic.py), the board (board.py), the BOM/CPL (fab.py) and
the firmware pin check (check_pins.py) are all generated from, or checked
against, this one file.

Nets
  VBUS      5 V from USB-C, after the TVS (feeds the LDO and the sounder)
  +3V3      LDO output: MCU, sensors, LEDs
  SDA/SCL   I2C bus: SGP40 (0x59), SHT40 (0x44), SCD41 (0x62)
"""

# Datasheet I2C addresses, used by the firmware and the simulation harness.
I2C = {'SGP40': 0x59, 'SHT40': 0x44, 'SCD41': 0x62}

R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
LED0603 = 'LED_SMD:LED_0603_1608Metric'


def P(ref, lib, value, fp, pins, mpn, mfr, lcsc='', desc='', pos=(0, 0), rot=0,
      dnp=False, bom=True):
    return dict(ref=ref, lib=lib, value=value, fp=fp, pins=pins, mpn=mpn, mfr=mfr,
                lcsc=lcsc, desc=desc, pos=pos, rot=rot, dnp=dnp, bom=bom)


def R(ref, value, a, b, mpn, pos, rot=0, lcsc=''):
    return P(ref, 'Device:R', value, R0603, {'1': a, '2': b}, mpn, 'YAGEO', lcsc,
             f'Resistor {value} 0603', pos, rot)


def C(ref, value, a, b, mpn, pos, fp=C0603, rot=0, lcsc='', mfr='Samsung Electro-Mechanics'):
    return P(ref, 'Device:C', value, fp, {'1': a, '2': b}, mpn, mfr, lcsc,
             f'Capacitor {value}', pos, rot)


PARTS = [
    # ---------------------------------------------------------------- power
    P('J1', 'Connector:USB_C_Receptacle_PowerOnly_6P', 'USB-C power',
      'Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190_6P_TopMnt_Horizontal',
      {'A5': 'CC1', 'B5': 'CC2', 'A9': 'VBUS', 'B9': 'VBUS', 'A12': 'GND', 'B12': 'GND',
       'SH': 'GND'},
      'USB4125-GF-A-0190', 'GCT', 'C5246813', 'USB-C receptacle, power only, 3 A', (35, 52)),
    R('R1', '5.1k', 'CC1', 'GND', 'RC0603FR-075K1L', (68, 62), lcsc='C105580'),
    R('R2', '5.1k', 'CC2', 'GND', 'RC0603FR-075K1L', (80, 62), lcsc='C105580'),
    P('D1', 'Diode:SMF5V0A', 'SMF5.0A', 'Diode_SMD:D_SMF', {'1': 'VBUS', '2': 'GND'},
      'SMF5.0A', 'Littelfuse', 'C151296', 'TVS 5 V unidirectional, 200 W', (100, 45)),
    C('C1', '10u', 'VBUS', 'GND', 'CL21A106KAYNNNE', (115, 52), fp=C0805, lcsc='C15850'),
    P('U1', 'Regulator_Linear:AP2112K-3.3', 'AP2112K-3.3', 'Package_TO_SOT_SMD:SOT-23-5',
      {'1': 'VBUS', '2': 'GND', '3': 'VBUS', '4': None, '5': '+3V3'},
      'AP2112K-3.3TRG1', 'Diodes Incorporated', 'C51118', 'LDO 3.3 V 600 mA', (140, 52)),
    C('C2', '10u', '+3V3', 'GND', 'CL21A106KAYNNNE', (165, 52), fp=C0805, lcsc='C15850'),

    # ------------------------------------------------------------------ MCU
    P('U2', 'MCU_Microchip_ATmega:ATmega328P-A', 'ATmega328P-AU',
      'Package_QFP:TQFP-32_7x7mm_P0.8mm',
      {'1': 'LED_GRN', '2': None, '3': 'GND', '4': '+3V3', '5': 'GND', '6': '+3V3',
       '7': None, '8': None, '9': 'LED_AMB', '10': 'LED_RED', '11': None,
       '12': None, '13': 'BUZ', '14': None, '15': 'MOSI', '16': 'MISO', '17': 'SCK',
       '18': '+3V3', '19': None, '20': 'AREF', '21': 'GND', '22': None,
       '23': 'NTC_BRD', '24': 'NTC_PRB_F', '25': None, '26': None,
       '27': 'SDA', '28': 'SCL', '29': 'RESET', '30': 'RXD', '31': 'TXD', '32': 'BTN'},
      'ATMEGA328P-AU', 'Microchip Technology', 'C14877',
      'AVR MCU 32 KB flash, internal 8 MHz RC', (165, 140)),
    C('C3', '100n', '+3V3', 'GND', 'CL10B104KA8NNNC', (115, 105), lcsc='C1590'),
    C('C4', '100n', '+3V3', 'GND', 'CL10B104KA8NNNC', (127, 105), lcsc='C1590'),
    C('C5', '100n', '+3V3', 'GND', 'CL10B104KA8NNNC', (139, 105), lcsc='C1590'),
    C('C6', '100n', 'AREF', 'GND', 'CL10B104KA8NNNC', (122, 140), lcsc='C1590'),
    R('R3', '10k', '+3V3', 'RESET', 'RC0603FR-0710KL', (222, 190), lcsc='C98220'),
    P('J2', 'Connector:AVR-ISP-6', 'ISP (Tag-Connect)',
      'Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical',
      {'1': 'MISO', '2': '+3V3', '3': 'SCK', '4': 'MOSI', '5': 'RESET', '6': 'GND'},
      'TC2030-IDC-NL', 'Tag-Connect', '', 'Programming pads, no part fitted', (250, 190),
      bom=False),
    P('TP1', 'Connector:TestPoint', 'TXD', 'TestPoint:TestPoint_Pad_D1.0mm', {'1': 'TXD'},
      '', '', '', 'Test pad, serial telemetry out', (282, 192), bom=False),
    P('TP2', 'Connector:TestPoint', 'RXD', 'TestPoint:TestPoint_Pad_D1.0mm', {'1': 'RXD'},
      '', '', '', 'Test pad, serial in', (294, 192), bom=False),
    P('TP3', 'Connector:TestPoint', 'GND', 'TestPoint:TestPoint_Pad_D1.0mm', {'1': 'GND'},
      '', '', '', 'Test pad, ground', (306, 192), bom=False),

    # -------------------------------------------------------------- sensors
    P('U3', 'canary:SGP40', 'SGP40', 'canary:Sensirion_DFN-6_2.44x2.44mm_P0.8mm_SGP40',
      {'1': '+3V3', '2': 'GND', '3': 'SDA', '4': 'GND', '5': '+3V3', '6': 'SCL', '7': 'GND'},
      'SGP40-D-R4', 'Sensirion', 'C2874215', 'MOX VOC gas sensor, I2C 0x59', (305, 52)),
    C('C7', '1u', '+3V3', 'GND', 'CL10A105KA8NNNC', (282, 52), lcsc='C5673'),
    P('U4', 'Sensor_Humidity:SHT4x', 'SHT40', 'Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad',
      {'1': 'SDA', '2': 'SCL', '3': '+3V3', '4': 'GND'},
      'SHT40-AD1B-R2', 'Sensirion', 'C2909890', 'Humidity + temperature sensor, I2C 0x44',
      (305, 97)),
    C('C8', '100n', '+3V3', 'GND', 'CL10B104KA8NNNC', (282, 97), lcsc='C1590'),
    P('U5', 'Sensor_Gas:SCD41-D-R2', 'SCD41',
      'Sensor:Sensirion_SCD4x-1EP_10.1x10.1mm_P1.25mm_EP4.8x4.8mm',
      {'6': 'GND', '7': '+3V3', '9': 'SCL', '10': 'SDA', '19': '+3V3', '20': 'GND',
       '21': 'GND'},
      'SCD41-D-R2', 'Sensirion', 'C3659294', 'Photoacoustic CO2 sensor, I2C 0x62', (305, 140)),
    C('C9', '10u', '+3V3', 'GND', 'CL21A106KAYNNNE', (268, 140), fp=C0805, lcsc='C15850'),
    C('C10', '100n', '+3V3', 'GND', 'CL10B104KA8NNNC', (281, 140), lcsc='C1590'),
    R('R4', '4.7k', '+3V3', 'SDA', 'RC0603FR-074K7L', (240, 47), lcsc='C99782'),
    R('R5', '4.7k', '+3V3', 'SCL', 'RC0603FR-074K7L', (253, 47), lcsc='C99782'),

    # --------------------------------------------------------- temperature
    # On-board NTC sits on the thermal tab: copper that is exposed on the
    # bottom face, so the board laid on a battery pack reads the pack.
    R('R6', '10k 0.1%', '+3V3', 'NTC_BRD', 'RT0603BRD0710KL', (30, 198), lcsc='C95204'),
    P('TH1', 'Device:Thermistor_NTC', '10k B3380', R0603, {'1': 'NTC_BRD', '2': 'GND'},
      'NCU18XH103F60RB', 'Murata Electronics', 'C440252', 'NTC 10 kΩ 1 %, B25/50 3380 K',
      (30, 228)),
    C('C11', '100n', 'NTC_BRD', 'GND', 'CL10B104KA8NNNC', (45, 228), lcsc='C1590'),
    # Optional remote probe (10k B3950 NTC on a JST-PH lead) for packs that
    # charge inside the frame. Open connector reads as "no probe".
    R('R7', '10k 0.1%', '+3V3', 'NTC_PRB', 'RT0603BRD0710KL', (70, 198), lcsc='C95204'),
    R('R8', '1k', 'NTC_PRB', 'NTC_PRB_F', 'RC0603FR-071KL', (88, 210), rot=90, lcsc='C22548'),
    C('C12', '100n', 'NTC_PRB_F', 'GND', 'CL10B104KA8NNNC', (103, 228), lcsc='C1590'),
    P('J3', 'Connector_Generic_MountingPin:Conn_01x02_MountingPin', 'Probe', 'Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal',
      {'1': 'NTC_PRB', '2': 'GND', 'MP': 'GND'},
      'S2B-PH-SM4-TB(LF)(SN)', 'JST', 'C295747', 'JST-PH 2-pin, remote NTC probe', (75, 250)),

    # ------------------------------------------------------- alarm and UI
    # Magnetic transducer from VBUS, low-side switched; D2 clamps the coil.
    P('BZ1', 'Device:Buzzer', 'CMT-8504', 'Buzzer_Beeper:MagneticBuzzer_CUI_CMT-8504-100-SMT',
      {'1': 'VBUS', '2': 'BUZ_D'},
      'CMT-8504-100-SMT-TR', 'Same Sky (CUI Devices)', 'C22359707',
      'Magnetic transducer 4 kHz, 15 Ω, 100 dB @10 cm',
      (48, 110)),
    P('D2', 'Device:D_Schottky', 'B5819W', 'Diode_SMD:D_SOD-123', {'1': 'VBUS', '2': 'BUZ_D'},
      'B5819W-TP', 'Micro Commercial Co', 'C84354', 'Schottky 40 V 1 A, coil clamp', (25, 110)),
    P('Q1', 'Transistor_FET:AO3400A', 'AO3400A', 'Package_TO_SOT_SMD:SOT-23',
      {'1': 'BUZ_G', '2': 'GND', '3': 'BUZ_D'},
      'AO3400A', 'Alpha & Omega Semiconductor', 'C20917', 'N-MOSFET 30 V 5.7 A logic level',
      (52, 138)),
    R('R9', '100', 'BUZ', 'BUZ_G', 'RC0603FR-07100RL', (30, 150), rot=90, lcsc='C105588'),
    R('R10', '100k', 'BUZ_G', 'GND', 'RC0603FR-07100KL', (45, 155), lcsc='C14675'),
    C('C13', '10u', 'VBUS', 'GND', 'CL21A106KAYNNNE', (78, 110), fp=C0805, lcsc='C15850'),

    P('D3', 'Device:LED', 'Green', LED0603, {'1': 'GND', '2': 'LED_GRN_A'},
      'APT1608SGC', 'Kingbright', 'C5875754', 'LED green 0603', (130, 258), rot=90),
    P('D4', 'Device:LED', 'Amber', LED0603, {'1': 'GND', '2': 'LED_AMB_A'},
      'APT1608SYCK', 'Kingbright', 'C5875726', 'LED yellow 0603', (152, 258), rot=90),
    P('D5', 'Device:LED', 'Red', LED0603, {'1': 'GND', '2': 'LED_RED_A'},
      'APT1608EC', 'Kingbright', 'C5554143', 'LED red 0603', (174, 258), rot=90),
    R('R11', '1k', 'LED_GRN', 'LED_GRN_A', 'RC0603FR-071KL', (130, 218), lcsc='C22548'),
    R('R12', '1k', 'LED_AMB', 'LED_AMB_A', 'RC0603FR-071KL', (152, 218), lcsc='C22548'),
    R('R13', '470', 'LED_RED', 'LED_RED_A', 'RC0603FR-07470RL', (174, 218), lcsc='C114669'),
    P('SW1', 'Switch:SW_Push', 'TEST / HUSH', 'Button_Switch_SMD:SW_SPST_TL3342',
      {'1': 'BTN', '2': 'GND'},
      'TL3342F160QG/TR', 'E-Switch', 'C2886898', 'Tactile switch 4.2 mm, 160 gf', (200, 258), rot=90),
    R('R14', '10k', '+3V3', 'BTN', 'RC0603FR-0710KL', (200, 218), lcsc='C98220'),

    # --------------------------------------------------------- mechanical
    P('H1', 'Mechanical:MountingHole', 'M2', 'MountingHole:MountingHole_2.2mm_M2', {},
      '', '', '', 'Mounting hole', (340, 205), bom=False),
    P('H2', 'Mechanical:MountingHole', 'M2', 'MountingHole:MountingHole_2.2mm_M2', {},
      '', '', '', 'Mounting hole', (352, 205), bom=False),
    P('FID1', 'Mechanical:Fiducial', 'Fiducial', 'Fiducial:Fiducial_1mm_Mask2mm', {},
      '', '', '', 'Assembly fiducial', (340, 218), bom=False),
    P('FID2', 'Mechanical:Fiducial', 'Fiducial', 'Fiducial:Fiducial_1mm_Mask2mm', {},
      '', '', '', 'Assembly fiducial', (352, 218), bom=False),
    P('FID3', 'Mechanical:Fiducial', 'Fiducial', 'Fiducial:Fiducial_1mm_Mask2mm', {},
      '', '', '', 'Assembly fiducial', (364, 218), bom=False),
]

# Footprint pads with no schematic pin (mechanical tabs tied to ground).
BOARD_ONLY = set()

# Power flags for ERC: nets driven by passive pins.
PWR_FLAGS = ['VBUS', 'GND']

# MCU pin map, the contract with firmware/board.h (check_pins.py compares them).
MCU = 'U2'
FIRMWARE_PINS = {
    'LED_GRN': 'PD3', 'LED_AMB': 'PD5', 'LED_RED': 'PD6', 'BUZ': 'PB1',
    'BTN': 'PD2', 'SDA': 'PC4', 'SCL': 'PC5', 'NTC_BRD': 'PC0', 'NTC_PRB_F': 'PC1',
    'TXD': 'PD1', 'RXD': 'PD0',
}


def nets():
    """{net: [(ref, pin), ...]}"""
    out = {}
    for p in PARTS:
        for pin, net in p['pins'].items():
            if net:
                out.setdefault(net, []).append((p['ref'], pin))
    return out


if __name__ == '__main__':
    for n, conns in sorted(nets().items()):
        print(f'{n:12s} {len(conns):2d}  ' + ' '.join(f'{r}.{p}' for r, p in conns))
