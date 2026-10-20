# -*- coding: utf-8 -*-
"""Every part on the board, where it comes from, and its pins.

Each entry is one orderable line:
  mpn      the maker's part number (what a US or allied assembler buys)
  maker    the maker, and hq: where the maker is headquartered
  digikey  DigiKey part number, filled in from DigiKey by the part audit
           (S2: every part stocked at DigiKey); blank until then
  lcsc     LCSC number JLCPCB assembles the test boards from (S3)
  fp       footprint (og: = this board's library, built from the maker's
           land pattern as LCSC/EasyEDA publishes it for that exact part)
  sym      'box' (drawn from the pin table below) or a KiCad library symbol
           (lib, name) with `pinmap` from library pin to footprint pad

Pin tables are the datasheet's, pad by pad; each IC's table was read from
LCSC's symbol for the exact part and checked against the maker's datasheet
(docs/part-audit.md, with dates).  Stock and prices: docs/part-audit.md.

Sourcing rule (README S1): no part from a company headquartered in China,
Russia, Iran or North Korea, nor from Huawei, ZTE, Hytera, Hikvision or
Dahua.  Two consequences worth knowing:
  * resistors are Yageo (Taiwan), not JLCPCB's "basic" UNI-ROYAL
    (Kunshan, China) parts, so each value is an "extended" line at JLC;
  * no Nexperia parts (owned by Wingtech, China) and no GCT connectors
    (Hong Kong / mainland China).
"""

US, JP, TW, KR, NO, IE, CH = 'USA', 'Japan', 'Taiwan', 'South Korea', 'Norway', 'Ireland', 'Switzerland'
TI = ('Texas Instruments', US)


def ic(mpn, maker, lcsc, digikey, fp, desc, pins, left, right, prefix='U', **kw):
    m, hq = maker
    pt = {}
    for pad, name, typ in pins:
        pt[pad] = (name, typ)
    return dict(mpn=mpn, maker=m, hq=hq, lcsc=lcsc, digikey=digikey, fp=fp, desc=desc, value=mpn,
                sym='box', symbol=dict(pins=pt, left=left, right=right, prefix=prefix), kind=prefix, **kw)


P, PI, PO, I, O, B, OC, NC = 'passive', 'power_in', 'power_out', 'input', 'output', 'bidirectional', 'open_collector', 'no_connect'

PARTS = {}

# =================================================================== processor + Bluetooth
NRF_PINS = [
    # power and regulators
    ('Y2', 'VDDH', PI), ('AB2', 'DCCH', P), ('B1', 'VDD', PI), ('W1', 'VDD', PI), ('AD14', 'VDD', PI),
    ('AD23', 'VDD', PI), ('A22', 'VDD', PI), ('B3', 'DCC', P), ('B5', 'DEC4', P), ('C1', 'DEC1', P),
    ('A18', 'DEC2', P), ('D23', 'DEC3', P), ('N24', 'DEC5', P), ('E24', 'DEC6', P),
    ('AD2', 'VBUS', PI), ('AC5', 'DECUSB', P), ('AD4', 'D-', B), ('AD6', 'D+', B),
    ('B7', 'VSS', PI), ('0', 'VSS (EP)', PI), ('F23', 'VSS_PA', PI),
    # clocks, radio, debug
    ('B24', 'XC1', P), ('A23', 'XC2', P), ('D2', 'P0.00/XL1', P), ('F2', 'P0.01/XL2', P),
    ('H23', 'ANT', P), ('AA24', 'SWDCLK', I), ('AC24', 'SWDIO', B), ('AC13', 'P0.18/nRESET', B),
    # GPIO
    ('A12', 'P0.02/AIN0', B), ('B13', 'P0.03/AIN1', B), ('J1', 'P0.04/AIN2', B), ('K2', 'P0.05/AIN3', B),
    ('L1', 'P0.06', B), ('M2', 'P0.07', B), ('N1', 'P0.08', B), ('L24', 'P0.09/NFC1', B),
    ('J24', 'P0.10/NFC2', B), ('T2', 'P0.11', B), ('U1', 'P0.12', B), ('AD8', 'P0.13', B),
    ('AC9', 'P0.14', B), ('AD10', 'P0.15', B), ('AC11', 'P0.16', B), ('AD12', 'P0.17', B),
    ('AC15', 'P0.19', B), ('AD16', 'P0.20', B), ('AC17', 'P0.21', B), ('AD18', 'P0.22', B),
    ('AC19', 'P0.23', B), ('AD20', 'P0.24', B), ('AC21', 'P0.25', B), ('G1', 'P0.26', B),
    ('H2', 'P0.27', B), ('B11', 'P0.28/AIN4', B), ('A10', 'P0.29/AIN5', B), ('B9', 'P0.30/AIN6', B),
    ('A8', 'P0.31/AIN7', B), ('AD22', 'P1.00', B), ('Y23', 'P1.01', B), ('W24', 'P1.02', B),
    ('V23', 'P1.03', B), ('U24', 'P1.04', B), ('T23', 'P1.05', B), ('R24', 'P1.06', B),
    ('P23', 'P1.07', B), ('P2', 'P1.08', B), ('R1', 'P1.09', B), ('A20', 'P1.10', B),
    ('B19', 'P1.11', B), ('B17', 'P1.12', B), ('A16', 'P1.13', B), ('B15', 'P1.14', B),
    ('A14', 'P1.15', B),
]
PARTS['NRF52840'] = ic(
    'NRF52840-QIAA-F-R7', ('Nordic Semiconductor', NO), 'C3606858', '',
    'og:AQFN-73_L7.0-W7.0-P0.50-BL-EP4.8',
    'Bluetooth LE SoC, Cortex-M4F 64 MHz, 1 MB flash, 256 KB RAM, USB, aQFN-73 7 x 7',
    NRF_PINS,
    left=['Y2', 'AB2', 'B1', 'W1', 'AD14', 'AD23', 'A22', 'B3', 'B5', 'C1', 'A18', 'D23', 'N24', 'E24', '-',
          'AD2', 'AC5', 'AD4', 'AD6', '-', 'B24', 'A23', 'D2', 'F2', '-', 'H23', '-', 'AA24', 'AC24', 'AC13', '-',
          'B7', '0', 'F23'],
    right=['A12', 'B13', 'J1', 'K2', 'L1', 'M2', 'N1', 'L24', 'J24', 'T2', 'U1', 'AD8', 'AC9', 'AD10', 'AC11',
           'AD12', 'AC15', 'AD16', 'AC17', 'AD18', 'AC19', 'AD20', 'AC21', 'G1', 'H2', 'B11', 'A10', 'B9', 'A8',
           '-', 'AD22', 'Y23', 'W24', 'V23', 'U24', 'T23', 'R24', 'P23', 'P2', 'R1', 'A20', 'B19', 'B17', 'A16',
           'B15', 'A14'])

# =================================================================== LoRa radio
PARTS['SX1262'] = ic(
    'SX1262IMLTRT', ('Semtech', US), 'C191341', '', 'og:QFN-24_L4.0-W4.0-P0.50-BL-EP2.6',
    'LoRa transceiver 150-960 MHz, +22 dBm, QFN-24 4 x 4',
    [('1', 'VDD_IN', PI), ('2', 'GND', PI), ('3', 'XTA', P), ('4', 'XTB', P), ('5', 'GND', PI),
     ('6', 'DIO3', O), ('7', 'VREG', PO), ('8', 'GND', PI), ('9', 'DCC_SW', P), ('10', 'VBAT', PI),
     ('11', 'VBAT_IO', PI), ('12', 'DIO2', O), ('13', 'DIO1', O), ('14', 'BUSY', O), ('15', 'NRESET', I),
     ('16', 'MISO', O), ('17', 'MOSI', I), ('18', 'SCK', I), ('19', 'NSS', I), ('20', 'GND', PI),
     ('21', 'RFI_P', P), ('22', 'RFI_N', P), ('23', 'RFO', P), ('24', 'VR_PA', P), ('25', 'GND (EP)', PI)],
    left=['1', '10', '11', '7', '9', '24', '-', '3', '4', '-', '19', '18', '17', '16', '15'],
    right=['23', '21', '22', '-', '6', '12', '13', '14', '-', '2', '5', '8', '20', '25'])

# 32 MHz TCXO for the SX1262, powered from its DIO3
PARTS['TCXO32'] = ic(
    'ECS-TXO-20CSMV4-320-AP-TR', ('ECS Inc.', US), 'C54284784', '', 'og:OSC-SMD_4P-L2.0-W1.6-BL',
    'TCXO 32 MHz +/-0.5 ppm, clipped sine, -40..105 C, 2.0 x 1.6 (the -AY code is only -30 C)',
    [('1', 'GND', PI), ('2', 'GND', PI), ('3', 'OUT', O), ('4', 'VDD', P)],
    left=['4', '1', '2'], right=['3'], prefix='Y')

# =================================================================== RF front end
PARTS['QPA9510'] = ic(
    'QPA9510TR7', ('Qorvo', US), 'C52059849', '', 'og:QFN-16_3x3_QPA9510',
    'Power amplifier 100-1000 MHz, 35.4 dBm at 3.6 V, 33.8 dB gain, QFN-16 3 x 3',
    [('1', 'VCC1', PI), ('2', 'GND1', PI), ('3', 'RF IN', P), ('4', 'GND2', PI), ('5', 'VCC2', PI), ('6', 'VCC2', PI),
     ('7', 'NC', NC), ('8', '2F0', P), ('9', 'RF OUT', P), ('10', 'RF OUT', P), ('11', 'RF OUT', P), ('12', 'RF OUT', P),
     ('13', 'NC', NC), ('14', 'VCC (bias)', PI), ('15', 'APC2', I), ('16', 'APC1', I), ('17', 'GND (EP)', PI)],
    left=['3', '-', '16', '15', '-', '1', '5', '6', '14'], right=['9', '10', '11', '12', '8', '-', '2', '4', '17', '7', '13'])

PARTS['SKY13330'] = ic(
    'SKY13330-397LF', ('Skyworks Solutions', US), 'C2654715', '',
    'og:QFN-12_L2.0-W2.0-P0.50-BL-EP0.8',
    'SPDT antenna switch 0.1-3 GHz, +40 dBm abs. max, 0.35 dB loss, QFN-12 2 x 2',
    [('1', 'GND', PI), ('2', 'RF1 (ANT)', P), ('3', 'GND', PI), ('4', 'GND', PI), ('5', 'RF3 (RX)', P),
     ('6', 'GND', PI), ('7', 'CTRL', I), ('8', 'ENABLE', I), ('9', 'VBATT', PI), ('10', 'GND', PI),
     ('11', 'RF2 (TX)', P), ('12', 'GND', PI), ('13', 'GND (EP)', PI)],
    left=['11', '5', '-', '7', '8', '9'], right=['2', '-', '1', '3', '4', '6', '10', '12', '13'])

PARTS['BGA7L1BN6'] = ic(
    'BGA7L1BN6E6327XTSA1', ('Infineon Technologies', 'Germany'), 'C534173', '',
    'og:TSNP-6_L1.1-W0.7-P0.40-BL',
    'LNA 716-960 MHz, 13.6 dB, NF 0.75 dB, 4.9 mA, with bypass, TSNP-6',
    [('1', 'GND', PI), ('2', 'VCC', PI), ('3', 'AO', P), ('4', 'GND', PI), ('5', 'AI', P), ('6', 'C', I)],
    left=['5', '2', '6'], right=['3', '1', '4'])

# the same filter in 0805 with 8 pads (sim/rf: no stop-band re-entry 5.5-10 GHz,
# where the LFCN-1000+ lets the 6th-10th harmonics through); 5.5 W at 25 C,
# derating to 1 W at 125 C.  Pads: Mini-Circuits case GE0805C-2.
PARTS['LFCG1000'] = ic(
    'LFCG-1000+', ('Mini-Circuits', US), 'C4989745', '', 'og:FILTER-SMD_8P-L2.0-W1.3-BL_LFCG-XX',
    'Low-pass filter DC-1000 MHz, 5.5 W, LTCC 0805',
    [('8', 'RF IN', P), ('4', 'RF OUT', P), ('1', 'GND', PI), ('2', 'GND', PI), ('3', 'GND', PI),
     ('5', 'GND', PI), ('6', 'GND', PI), ('7', 'GND', PI)],
    left=['8'], right=['4', '1', '2', '3', '5', '6', '7'], prefix='FL')

PARTS['UFL'] = ic(
    'U.FL-R-SMT-1(80)', ('Hirose Electric', JP), 'C88374', '', 'og:RF-SMD_FRF05002-JSS103M',
    'U.FL coaxial receptacle, 50 ohm (LoRa antenna)',
    [('1', 'SIG', P), ('2', 'GND', P), ('3', 'GND', P)],
    left=['1'], right=['2', '3'], prefix='J')

PARTS['ANT2450'] = ic(
    '2450AT18A0100001E', ('Johanson Technology', US), 'C17430588', '', 'og:ANT-SMD_L3.2-W1.6',
    'Chip antenna 2.4 GHz, 3.2 x 1.6 (Bluetooth)',
    [('1', 'FEED', P), ('2', 'NC', NC)],
    left=['1'], right=['2'], prefix='AE')

# =================================================================== power
PARTS['TPS259470A'] = ic(
    'TPS259470ARPWR', TI, 'C3662799', '', 'og:VQFN-10_L2.0-W2.0-P0.45-TL',
    'eFuse 2.7-23 V, adjustable over-voltage and current limit, reverse blocking, auto-retry, QFN-10 2 x 2',
    [('1', 'EN/UVLO', I), ('2', 'OVLO', I), ('3', 'PG', OC), ('4', 'FLT', OC), ('5', 'IN', PI),
     ('6', 'OUT', PO), ('7', 'DVDT', P), ('8', 'GND', PI), ('9', 'ILM', P), ('10', 'ITIMER', P)],
    left=['5', '1', '2', '7', '9', '10'], right=['6', '3', '4', '8'])

PARTS['BQ25185'] = ic(
    'BQ25185DLHR', TI, 'C19725033', '', 'og:WSON-10_L2.2-W2.0-P0.40-BL-EP_TI_DLH0010A',
    'Li-ion linear charger with power path, 18 V input (25 V abs.), 1 A, WSON-10',
    [('1', 'SYS', PO), ('2', 'BAT', P), ('3', 'STAT2', OC), ('4', '~{CE}', I), ('5', 'GND', PI),
     ('6', 'TS/MR', P), ('7', 'ILIM/VSET', P), ('8', 'ISET', P), ('9', 'STAT1', OC), ('10', 'IN', PI),
     ('11', 'GND (EP)', PI)],
    left=['10', '4', '6', '7', '8'], right=['1', '2', '9', '3', '5', '11'])

PARTS['BQ29700'] = ic(
    'BQ29700DSER', TI, 'C183096', '', 'og:WSON-6_L1.5-W1.5-P0.50-TL',
    'Single-cell Li-ion protector, OV 4.275 V, UV 2.8 V, WSON-6',
    [('1', 'NC', NC), ('2', 'COUT', O), ('3', 'DOUT', O), ('4', 'VSS', PI), ('5', 'BAT', PI), ('6', 'V-', P)],
    left=['5', '4', '6'], right=['3', '2', '1'])

PARTS['SSM10N954L'] = ic(
    'SSM10N954L,EFF', ('Toshiba', JP), 'C5274420', '', 'og:CSP-10L_SSM10N954L',
    'Dual N-MOSFET, common drain, 12 V, 2.75 mOhm, for cell protection, CSP-10',
    [('1', 'S1', P), ('2', 'S1', P), ('4', 'S1', P), ('5', 'S1', P), ('3', 'G1', I),
     ('6', 'S2', P), ('7', 'S2', P), ('9', 'S2', P), ('10', 'S2', P), ('8', 'G2', I)],
    left=['3', '1', '2', '4', '5'], right=['8', '6', '7', '9', '10'], prefix='Q')

PARTS['CSD25485F5'] = ic(
    'CSD25485F5', TI, 'C2867111', '', 'og:PICOSTAR-3_L1.6-W0.8-P0.53-L',
    'P-MOSFET -20 V for reverse-battery protection, PicoStar 1.6 x 0.8',
    [('1', 'G', I), ('2', 'S', P), ('3', 'D', P)],
    left=['3', '1'], right=['2'], prefix='Q')

PARTS['TPS2121'] = ic(
    'TPS2121RUXR', TI, 'C485916', '', 'og:VQFN-12_TPS2121RUX',
    'Power mux 2.8-22 V, 4.5 A, priority switch-over, QFN-12 2 x 2 (amplifier supply: battery, else SYS)',
    [('1', 'OUT', PO), ('8', 'OUT', P), ('2', 'IN2', PI), ('7', 'IN1', PI), ('3', 'CP2', P), ('4', 'OV2', I),
     ('5', 'OV1', I), ('6', 'PR1', I), ('9', 'ST', P),   # ST: status output, grounded when unused (datasheet)
     ('10', 'ILM', P), ('11', 'SS', P), ('12', 'GND', PI)],
    left=['7', '2', '6', '5', '4', '3'], right=['1', '8', '9', '10', '11', '12'])

PARTS['TPS63810'] = ic(
    'TPS63810YFFR', TI, 'C1852139', '', 'og:DSBGA-15_L2.2-W1.4-R3-V5-P0.40-BL',
    'Buck-boost 2.2-5.5 V in, 1.8-5.2 V out (I2C), 2.5 A, 13 uA, WCSP-15 (amplifier supply)',
    [('A1', 'EN', I), ('A2', 'VIN', PI), ('A3', 'VIN', PI), ('B1', 'VSEL', I), ('B2', 'LX1', P), ('B3', 'LX1', P),
     ('C1', 'AGND', PI), ('C2', 'GND', PI), ('C3', 'GND', PI), ('D1', 'SCL', I), ('D2', 'LX2', P), ('D3', 'LX2', P),
     ('E1', 'SDA', B), ('E2', 'VOUT', PO), ('E3', 'VOUT', P)],
    left=['A2', 'A3', 'A1', 'B1', 'D1', 'E1'], right=['E2', 'E3', 'B2', 'B3', 'D2', 'D3', 'C1', 'C2', 'C3'])

PARTS['TPS62840'] = ic(
    'TPS62840YBGR', TI, 'C2071139', '', 'og:DSBGA-6_L1.4-W1.0-R2-C3-P0.40-BL',
    'Buck 1.8-6.5 V in, 750 mA, 60 nA quiescent, WCSP-6 (3.3 V rail)',
    [('A1', 'GND', PI), ('A2', 'VOS', PO), ('B1', 'VIN', PI), ('B2', 'SW', P), ('C1', 'EN', I), ('C2', 'VSET', P)],
    left=['B1', 'C1', 'C2'], right=['B2', 'A2', 'A1'])

PARTS['TPS22965'] = ic(
    'TPS22965DSGR', TI, 'C122837', '', 'og:UDFN-8_L2.0-W2.0-P0.50-TL-EP',
    'Load switch 5.7 V 4 A, 16 mOhm, quick output discharge, WSON-8 2 x 2 (main power switch)',
    [('1', 'VIN', PI), ('2', 'VIN', PI), ('3', 'ON', I), ('4', 'VBIAS', PI), ('5', 'GND', PI), ('6', 'CT', P),
     ('7', 'VOUT', PO), ('8', 'VOUT', P), ('9', 'GND (EP)', PI)],
    left=['1', '2', '4', '3', '6'], right=['7', '8', '5', '9'])

PARTS['TLV75528'] = ic(
    'TLV75528PDQNR', TI, 'C2865384', '', 'og:X2SON-4_L1.0-W1.0-P0.65-TL-EP',
    'LDO 2.8 V 500 mA, X2SON-4 1 x 1 (amplifier control voltage, on only while transmitting)',
    [('1', 'OUT', PO), ('2', 'GND', PI), ('3', 'EN', I), ('4', 'IN', PI), ('5', 'GND (EP)', PI)],
    left=['4', '3'], right=['1', '2', '5'])

PARTS['TMP1075'] = ic(
    'TMP1075NDRLR', TI, 'C3663690', '', 'og:SOT-563_L1.6-W1.2-P0.50-LS1.6-BR',
    'Temperature sensor, I2C, +/-1 C, SOT-563 (beside the amplifier)',
    [('1', 'SCL', I), ('2', 'GND', PI), ('3', 'ALERT', OC), ('4', 'A0', I), ('5', 'V+', PI), ('6', 'SDA', B)],
    left=['5', '4'], right=['6', '1', '3', '2'])

PARTS['TPD4E05U06'] = ic(
    'TPD4E05U06DQAR', TI, 'C138714', '', 'og:USON-10_L2.5-W1.0-P0.50-BL',
    '4-line ESD protection, 0.5 pF, USON-10 2.5 x 1',
    [('1', 'IO1', P), ('2', 'IO2', P), ('4', 'IO3', P), ('5', 'IO4', P), ('3', 'GND', PI), ('8', 'GND', PI),
     ('6', 'NC', NC), ('7', 'NC', NC), ('9', 'NC', NC), ('10', 'NC', NC)],
    left=['1', '2', '4', '5'], right=['3', '8', '6', '7', '9', '10'], prefix='D')

PARTS['TVS2200'] = ic(
    'TVS2200DRVR', TI, 'C523793', '', 'og:WSON-6_L2.0-W2.0-P0.65-BL-EP',
    'Flat-clamp surge protection 22 V, WSON-6 2 x 2 (USB input)',
    [('4', 'IN', P), ('5', 'IN', P), ('6', 'IN', P), ('1', 'GND', P), ('2', 'GND', P), ('3', 'GND', P),
     ('7', 'GND (EP)', P)],
    left=['4', '5', '6'], right=['1', '2', '3', '7'], prefix='D')

# Solar and drone inputs (sim/hotplug, 19 Oct): 60 V, so a 12 V panel's cold
# open-circuit voltage (26 V at -40 C) and a 20 V fault need no clamp, and it
# blocks a reversed input (to -60 V) and reverse current, so neither input
# needs a Schottky.  Chosen over TPS26600 (HTSSOP-16) for size.
PARTS['MAX17608'] = ic(
    'MAX17608ATC+T', ('Analog Devices', US), 'C2155884', '', 'og:TDFN-12_L3.0-W3.0-P0.50-BL-EP',
    'Current limiter 4.5-60 V, 1 A, OV/UV, reverse voltage (-60 V) and reverse current blocking, TDFN-12 3 x 3',
    [('1', 'IN', PI), ('2', 'IN', PI), ('3', 'OVLO', I), ('4', 'UVLO', I), ('5', 'EN', I), ('6', 'CLMODE', I),
     ('7', 'GND', PI), ('8', 'SETI', P), ('9', 'FLAG', OC), ('10', 'UVOV', OC), ('11', 'OUT', P), ('12', 'OUT', P),   # OUT passive: OR-ed onto VIN_CHG
     ('13', 'GND (EP)', PI)],
    left=['1', '2', '3', '4', '5', '6'], right=['11', '12', '8', '9', '10', '7', '13'])

# Cell-to-system bypass (sim/burst, sim/shorts): current-limited and blocking
# reverse current, in place of the LM66100, which let the charger's SYS rail
# charge the cell outside the charger's control
PARTS['TPS22950'] = ic(
    'TPS22950YBHR', TI, 'C3230039', '', 'og:DSBGA-6_L1.2-W0.8-R2-C3-P0.40-BL',
    'Load switch 1.8-5.5 V, 34 mOhm, adjustable current limit 0.05-3.5 A, reverse current blocking, WCSP-6',
    [('A1', 'ON', I), ('A2', 'FLT', OC), ('B1', 'VIN', PI), ('B2', 'VOUT', P), ('C1', 'GND', PI), ('C2', 'ILIM', P)],   # VOUT passive: shares SYS with the charger
    left=['B1', 'A1', 'C2'], right=['B2', 'A2', 'C1'])

PARTS['CSD25310Q2'] = ic(
    'CSD25310Q2T', TI, 'C2871649', '', 'og:WSON-6_DQK_CSD25310Q2',
    'P-MOSFET -20 V, 19.9 mOhm at -4.5 V, 9.6 A, SON 2 x 2 (reverse-battery FET)',
    [('1', 'S', P), ('2', 'S', P), ('5', 'S', P), ('6', 'S', P), ('7', 'S (EP)', P), ('3', 'G', I),
     ('4', 'D', P), ('8', 'D (EP)', P)],
    left=['4', '8', '3'], right=['1', '2', '5', '6', '7'], prefix='Q')

# =================================================================== connectors and controls
PARTS['USBC'] = ic(
    '12401610E4#2A', ('Amphenol ICC', US), 'C5119948', '', 'og:USB-C-SMD_TYPE-C-24P',
    'USB-C receptacle, USB 2.0, SMT with through-hole shell legs',
    [('A4', 'VBUS', P), ('A9', 'VBUS', P), ('B4', 'VBUS', P), ('B9', 'VBUS', P), ('A5', 'CC1', P), ('B5', 'CC2', P),
     ('A6', 'D+', P), ('B6', 'D+', P), ('A7', 'D-', P), ('B7', 'D-', P), ('A8', 'SBU1', NC), ('B8', 'SBU2', NC),
     ('A2', 'SSTXp1', NC), ('A3', 'SSTXn1', NC), ('B2', 'SSTXp2', NC), ('B3', 'SSTXn2', NC),
     ('A10', 'SSRXn2', NC), ('A11', 'SSRXp2', NC), ('B10', 'SSRXn1', NC), ('B11', 'SSRXp1', NC),
     ('A1', 'GND', P), ('A12', 'GND', P), ('B1', 'GND', P), ('B12', 'GND', P), ('14', 'SHIELD', P), ('15', 'SHIELD', P)],
    left=['A4', 'A9', 'B4', 'B9', '-', 'A5', 'B5', '-', 'A6', 'B6', 'A7', 'B7', '-', 'A1', 'A12', 'B1', 'B12', '14', '15'],
    right=['A8', 'B8', 'A2', 'A3', 'B2', 'B3', 'A10', 'A11', 'B10', 'B11'], prefix='J')

PARTS['JST_PH2'] = ic(
    'S2B-PH-SM4-TB(LF)(SN)', ('JST', JP), 'C295747', '', 'og:CONN-SMD_P2.00_S2B-PH-SM4-TB-LF-SN',
    'JST PH 2-pin right-angle SMT (battery)',
    [('1', '1', P), ('2', '2', P), ('3', 'MNT', P), ('4', 'MNT', P)],
    left=['1', '2'], right=['3', '4'], prefix='J')

PARTS['JST_SH2'] = ic(
    'SM02B-SRSS-TB(LF)(SN)', ('JST', JP), 'C160402', '', 'og:CONN-SMD_2P-P1.00_SM02B-SRSS-TB-LF-SN',
    'JST SH 2-pin right-angle SMT (solar input)',
    [('1', '1', P), ('2', '2', P), ('3', 'MNT', P), ('4', 'MNT', P)],
    left=['1', '2'], right=['3', '4'], prefix='J')

PARTS['JST_GH6'] = ic(
    'SM06B-GHS-TB(LF)(SN)', ('JST', JP), 'C133065', '', 'og:CONN-TH_SM06B-GHS-TB-LF-SN',
    'JST GH 6-pin locking right-angle SMT (drone port, Pixhawk TELEM pinout)',
    [(str(i), str(i), P) for i in range(1, 7)] + [('7', 'MNT', P), ('8', 'MNT', P)],
    left=['1', '2', '3', '4', '5', '6'], right=['7', '8'], prefix='J')

PARTS['JST_SH6'] = ic(
    'SM06B-SRSS-TB(LF)(SN)', ('JST', JP), 'C160405', '', 'og:CONN-SMD_SM06B-SRSS-TB-LF-SN',
    'JST SH 6-pin right-angle SMT (GPS add-on)',
    [(str(i), str(i), P) for i in range(1, 7)] + [('7', 'MNT', P), ('8', 'MNT', P)],
    left=['1', '2', '3', '4', '5', '6'], right=['7', '8'], prefix='J')

PARTS['HDR_2x10'] = dict(
    mpn='(not fitted) 2 x 10 header, 2.54 mm', maker='', hq='', lcsc='', digikey='', value='EXPANSION',
    fp='og:Header_2x1x10_Rows20.32', desc='Expansion header footprint, 2.54 mm, fitted only when needed',
    sym='box', kind='J', dnp=True,
    symbol=dict(prefix='J', left=[str(i) for i in range(1, 21, 2)], right=[str(i) for i in range(2, 21, 2)],
                pins={str(i): (str(i), P) for i in range(1, 21)}))

# =================================================================== small parts
def _two(kind, key, mpn, maker, lcsc, fp, value, desc, sym, pinmap=None, **kw):
    m, hq = maker
    PARTS[key] = dict(mpn=mpn, maker=m, hq=hq, lcsc=lcsc, digikey='', fp=fp, value=value, desc=desc,
                      sym=sym, kind=kind, **({'pinmap': pinmap} if pinmap else {}), **kw)

SAMSUNG, MURATA, YAGEO, TDK, ROHM, LITEON, ABRACON, PANASONIC, COILCRAFT, CK, OMRON, LITTELFUSE, VISHAY = (
    ('Samsung Electro-Mechanics', KR), ('Murata', JP), ('Yageo', TW), ('TDK', JP), ('Rohm', JP),
    ('Lite-On', TW), ('Abracon', US), ('Panasonic', JP), ('Coilcraft', US), ('C&K', US),
    ('Omron (Aratas)', JP), ('Littelfuse', US), ('Vishay Dale', US))
TAIYO = ('Taiyo Yuden', JP)

FP = {'0402': 'og:C_0402', '0603': 'og:C_0603', '0805': 'og:C_0805', '1206': 'og:R_1206'}

def cap(key, value, size, rating, mpn, lcsc, maker=SAMSUNG):
    _two('C', key, mpn, maker, lcsc, 'og:C_%s' % size, value, 'Capacitor %s %s %s' % (value, rating, size),
         ('Device', 'C'))

def res(key, value, size, mpn, lcsc, maker=YAGEO, note='1%'):
    _two('R', key, mpn, maker, lcsc, 'og:R_%s' % size, value, 'Resistor %s %s %s' % (value, note, size),
         ('Device', 'R'))

def ind(key, value, size, mpn, lcsc, maker=MURATA, note=''):
    _two('L', key, mpn, maker, lcsc, 'og:L_%s' % size, value, 'Inductor %s %s %s' % (value, size, note),
         ('Device', 'L'))

# decoupling and bulk (X7R/X5R, voltage rating >= 1.5x working)
cap('C100n', '100nF', '0402', '16V X7R', 'CL05B104KO5NNNC', 'C1525')
cap('C1u', '1uF', '0402', '16V X5R', 'CL05A105KO5NNNC', 'C29266')
cap('C1u25', '1uF', '0603', '25V X7R', 'CL10B105KA8NNNC', 'C29936')
cap('C470n', '470nF', '0402', '16V X5R', 'CL05A474KO5NNNC', 'C480644')
cap('C2u2', '2.2uF', '0402', '6.3V X5R', 'CL05A225MQ5NSNC', 'C12530')
cap('C4u7', '4.7uF', '0603', '10V X5R', 'CL10A475KP8NNNC', 'C1705')
cap('C10u', '10uF', '0603', '10V X5R', 'CL10A106KP8NNNC', 'C19702')
cap('C10u25', '10uF', '0805', '25V X5R', 'CL21A106KAYNNNE', 'C15850')
cap('C22u16', '22uF', '0805', '16V X5R', 'GRM21BR61C226ME44L', 'C86817', MURATA)
# amplifier rail (VPA up to 4.0 V = 63 % of 6.3 V); X7S, 1206: more capacitance left at 4 V and 85 C
# than the 0805 X5R it replaces (sim/thermal)
cap('C47u', '47uF', '1206', '6.3V X7S', 'C3216X7S0J476M160AC', 'C2167997', TDK)
# raw input side of the USB eFuse (20 V fault = 40 % of 50 V); the 4.7 uF + 1 R damps the cable ring (sim/hotplug)
cap('C1u50', '1uF', '0603', '50V X5R', 'UMK107BJ105KA-T', 'C92848', TAIYO)
cap('C4u7_50', '4.7uF', '1206', '50V X7R', 'CL31B475KBHNNNE', 'C51205')
cap('C47n', '47nF', '0402', '16V X7R', 'CL05B473KO5NNNC', 'C307434')
cap('C10n', '10nF', '0402', '50V X7R', 'CL05B103KB5NNNC', 'C15195')
cap('C1n', '1nF', '0402', '50V C0G', 'GRM1555C1H102JA01D', 'C76947', MURATA)
cap('C820p', '820pF', '0402', '50V C0G', 'GRM1555C1H821JA01D', 'C85943', MURATA)
cap('C100p', '100pF', '0402', '50V C0G', 'GRM1555C1H101JA01D', 'C77177', MURATA)
cap('C22p', '22pF', '0402', '50V C0G', 'GRM1555C1H220JA01D', 'C76960', MURATA)
cap('C12p', '12pF', '0402', '50V C0G', 'CL05C120JB5NNNC', 'C26406')
# RF: Murata GJM high-Q C0G
for v, code, lc in [('0.5pF', 'R50B', 'C76911'), ('1.0pF', '1R0B', 'C76898'),
                    ('1.5pF', '1R5B', 'C76900'), ('1.8pF', '1R8B', 'C76902'), ('2.4pF', '2R4B', 'C88888'),
                    ('3.0pF', '3R0B', 'C88891'), ('5.6pF', '5R6B', 'C161329'), ('10pF', '100J', 'C85874'),
                    ('11pF', '110J', 'C426107'), ('15pF', '150J', 'C88877'), ('27pF', '270J', 'C88884'),
                    ('39pF', '390J', 'C426038'), ('47pF', '470J', 'C161322')]:
    cap('RF' + v, v, '0402', '50V C0G high-Q', 'GJM1555C1H%sB01D' % code, lc, MURATA)
# PA harmonic filter: 250 V C0G (an open antenna roughly doubles the RF
# voltage); values from sim/rf (lowest loss with 2f-5f rejection, with the LFCN)
for v, size, mpn, lc in [('0.9pF', '0603', 'GQM1875C2ER90BB12D', 'C1865143'), ('1.3pF', '0603', 'GQM1875C2E1R3BB12D', 'C3901219'),
                         ('2.0pF', '0603', 'GQM1875C2E2R0BB12D', 'C6867410'), ('3.6pF', '0603', 'GQM1875C2E3R6BB12D', 'C2178747')]:
    cap('HV' + v, v, size, '250V C0G high-Q', mpn, lc, MURATA)
# the Bluetooth match's 0.8 pF at +-0.05 pF (sim/rf: +-0.1 pF loses 1 % of boards)
cap('RF0.8pF_W', '0.8pF', '0402', '50V C0G high-Q +-0.05pF', 'GJM1555C1HR80WB01D', 'C88902', MURATA)

for v, code, lc in [('0R', '0R', 'C106231'), ('22R', '22R', 'C114765'), ('330R', '330R', 'C105875'), ('470R', '470R', 'C114877'),
                    ('604R', '604R', 'C273693'), ('287k', '287K', 'C327358'), ('1k', '1K', 'C106235'), ('2.2k', '2K2', 'C114762'), ('2.21k', '2K21', 'C138019'),
                    ('2.49k', '2K49', 'C145071'), ('4.7k', '4K7', 'C105871'), ('5.1k', '5K1', 'C105872'), ('10k', '10K', 'C60490'),
                    ('13k', '13K', 'C138057'), ('15k', '15K', 'C114761'), ('22.1k', '22K1', 'C163478'), ('47k', '47K', 'C93943'),
                    ('100k', '100K', 'C60491'), ('137k', '137K', 'C138058'), ('220k', '220K', 'C138030'), ('261k', '261K', 'C185437'),
                    ('267k', '267K', 'C327360'), ('301k', '301K', 'C171693'), ('330k', '330K', 'C138006'), ('383k', '383K', 'C163468'),
                    ('510k', '510K', 'C137961'), ('562k', '562K', 'C273337'), ('1M', '1M', 'C138033'), ('1.5M', '1M5', 'C138034')]:
    res('R' + v, v, '0402', 'RC0402FR-07%sL' % code, lc)
# the antenna detector's coupler termination: 85 mW with the antenna off (sim/rf study 8), so 0805 0.5 W pulse-proof
res('R49.9R_0805', '49.9R', '0805', 'CRCW080549R9FKEAHP', 'C4088942', VISHAY, '1% 0.5 W pulse-proof')
res('R68_0805', '68R', '0805', 'RC0805FR-0768RL', 'C137498')
# the pad's first resistor takes the most power (sim/rf: 118 mW at +22 dBm drive)
res('R68_0805_AS', '68R', '0805', 'RCS080568R0FKEA', 'C2114866', VISHAY, '1% 0.4 W anti-surge')
res('R150_0805', '150R', '0805', 'RC0805FR-07150RL', 'C114523')
res('R22m', '22mR', '1206', 'ERJ-8BWFR022V', 'C2075813', PANASONIC, '1% 1 W')
# cell-protector sense since 19 Oct: OCD 4.8-6.7 A clears 3 W bursts (3.6-4.1 A), which 22 mOhm (3.3-4.9 A) did not
res('R15m', '15mR', '1206', 'WSLP1206R0150FEA', 'C844911', VISHAY, '1% 1 W metal strip')
# power-path fixes (sim/, 19 Oct)
for v, code, lc in [('1.15k', '1K15', 'C477191'), ('2.1k', '2K1', 'C163473'), ('7.68k', '7K68', 'C155695'),
                    ('20k', '20K', 'C93942'), ('374k', '374K', 'C185423')]:
    res('R' + v, v, '0402', 'RC0402FR-07%sL' % code, lc)
# USB input snubber: takes ~1 mJ in a few us when a 20 V source is plugged in
res('R1R_0805', '1R', '0805', 'CRCW08051R00FKEAHP', 'C313850', VISHAY, '1% 0.5 W pulse-proof')

ind('L10u', '10uH', '0805', 'MLZ2012M100WT000', 'C88173', TDK, 'nRF52840 DC/DC')
ind('L15u', '15uH', '0805', 'MLZ2012M150WT000', 'C383402', TDK, 'SX1262 DC/DC')
ind('L2u2', '2.2uH', '0806', 'DFE201610E-2R2M=P2', 'C337891', MURATA, '3.3 V buck')
ind('L470n', '0.47uH', '1008', 'DFE252012F-R47M=P2', 'C703140', MURATA, 'amplifier buck-boost')
for v, mpn, lc in [('1.5nH', 'LQW15AN1N5C00D', 'C167468'), ('2.5nH', 'LQW15AN2N5C00D', 'C703121'), ('2.7nH', 'LQW15AN2N7C00D', 'C98058'),
                   ('3.9nH', 'LQW15AN3N9C00D', 'C98063'), ('4.7nH', 'LQW15AN4N7C00D', 'C167480'),
                   ('11nH', 'LQW15AN11NJ00D', 'C167465'), ('15nH', 'LQW15AN15NJ00D', 'C94079'), ('47nH', 'LQW15AN47NJ00D', 'C192855')]:
    ind('L' + v, v, '0402', mpn, lc, MURATA, 'wire-wound RF')
# 3 W path: 0805 wire-wound, 2 A class (sim/rf: the 0402/0603 parts ran 1.1-2.7x
# past their rated self-heating at 3 W)
ind('L3.2nH_0805', '3.2nH', '0805', 'LQW2BAN3N2J00L', 'C2043110', MURATA, 'wire-wound RF 0805, harmonic filter')
ind('L3.6nH_0805', '3.6nH', '0805', 'LQW2BAN3N6J00L', 'C2045110', MURATA, 'wire-wound RF 0805, amplifier output match')
ind('L5.6nH_0603', '5.6nH', '0603', 'LQW18AN5N6C00D', 'C98081', MURATA, 'wire-wound RF, harmonic filter')
ind('L11nH_0603', '11nH', '0603', 'LQW18AN11NG00D', 'C701196', MURATA, 'wire-wound RF, amplifier supply feed')
ind('L8.1nH_PA', '8.1nH', '0908SQ', '0908SQ-8N1', 'C19191636', COILCRAFT, 'air-core, amplifier output choke (carries the 1.7 A collector current)')
_two('FB', 'FB120', 'BLM15AG100SN1D', MURATA, 'C76882', 'og:L_0402', '10R@100MHz', 'Ferrite bead 0402', ('Device', 'FerriteBead_Small'))

# diodes, LEDs, discretes
_two('D', 'RB060MM', 'RB060MM-30TR', ROHM, 'C308720', 'og:SOD-123FL', 'RB060MM-30', 'Schottky 30 V 2 A, SOD-123FL',
     ('Device', 'D_Schottky'), {'K': '1', 'A': '2'})
# solar and drone inputs: bidirectional (a reversed input is blocked by the MAX17608, not shorted by the clamp);
# 33 V stand-off clears a 12 V panel at -40 C (26 V), 53 V clamp is under the MAX17608's 60 V
_two('D', 'SMF33CA', 'SMF33CA', LITTELFUSE, 'C1851347', 'og:SOD-123FL', 'SMF33CA',
     'TVS 33 V bidirectional 200 W, SOD-123FL', ('Device', 'D_TVS'))
# the missing-antenna detector's diodes (two: forward and reflected; sim/rf study 8).  Infineon BAT68-04W,
# an 8 V RF Schottky series pair in SOT-323: 1 = D1 anode, 3 = D1 cathode / D2 anode, 2 = D2 cathode (Infineon
# BAT68 data sheet 2011-06-15, pin diagram).  Only D1 is used; circuit.py ties pin 2 to pin 3, which shorts D2.
# Chosen 20 Oct over the BAT15-02EL (4 V: the antenna-off reverse peak reached 5.7 V) and the BAT62 (40 V):
# every single BAT62 package is obsolete at DigiKey (-02V, -03W, -02LS) and none is stocked at LCSC.
PARTS['BAT68_04W'] = ic(
    'BAT6804WH6327XTSA1', ('Infineon Technologies', 'Germany'), 'C6129734', '', 'og:SOT-323',
    'RF Schottky diode pair (series) 8 V, CT <= 1 pF, VF 318 mV at 1 mA, SOT-323 (detector: D1 only)',
    [('1', 'A1', P), ('3', 'K1/A2', P), ('2', 'K2', P)],
    left=['1'], right=['3', '2'], prefix='D')
_two('D', 'ZENER4V7', 'UDZVTE-174.7B', ROHM, 'C209560', 'og:SOD-323FL', '4.7V', 'Zener 4.7 V 200 mW, SOD-323FL',
     ('Device', 'D_Zener'), {'K': '1', 'A': '2'})
# USB eFuse EN clamp since 19 Oct: 1 uA at 2.5 V (the 4.7 V part: 2 uA at 1 V), so its leakage at the
# 1.2 V EN threshold no longer moves the USB UVLO (sim/hotplug); clamps EN to ~5.9 V hot, under 6.5 V
_two('D', 'ZENER5V6', 'UDZVTE-175.6B', ROHM, 'C79630', 'og:SOD-323FL', '5.6V', 'Zener 5.6 V 200 mW, SOD-323FL',
     ('Device', 'D_Zener'), {'K': '1', 'A': '2'})
PARTS['LM66100'] = ic('LM66100DCKR', TI, 'C2869734', '', 'og:SC-70-6',
                      'Ideal diode 1.5-5.5 V 1.5 A, 79 mOhm, SC-70-6 (cell to system rail)',
                      [('1', 'VIN', PI), ('2', 'GND', PI), ('3', '~{CE}', I), ('4', 'NC', NC), ('5', 'ST', OC), ('6', 'VOUT', P)],
                      left=['1', '3'], right=['6', '5', '4', '2'])
for key, mpn, lc, col in [('LED_R', 'LTST-C191KRKT', 'C125099', 'red'), ('LED_G', 'LTST-C191KGKT', 'C125098', 'green'),
                          ('LED_B', 'LTST-C191TBKT', 'C99290', 'blue')]:
    _two('LED', key, mpn, LITEON, lc, 'og:LED0603-RD', col, 'LED %s 0603' % col, ('Device', 'LED'), {'K': '1', 'A': '2'})
_two('Y', 'XTAL32M', 'ABM11W-32.0000MHZ-8-D1X-T3', ABRACON, 'C5189005', 'og:CRYSTAL-SMD_4P-L2.0-W1.6-BL_CXAN-211',
     '32MHz', 'Crystal 32 MHz CL 8 pF, 2.0 x 1.6, -40..85 C', ('Device', 'Crystal_GND24'), {'1': '1', '3': '3', 'G': '2'},
     lie=False)
_two('Y', 'XTAL32K', 'ABS07-32.768KHZ-7-T', ABRACON, 'C276424', 'og:ABS07', '32.768kHz', 'Crystal 32.768 kHz CL 7 pF, 3.2 x 1.5',
     ('Device', 'Crystal'), None)
_two('TH', 'NTC10K', 'NCU15XH103F60RC', MURATA, 'C237326', 'og:R_0402', '10k NTC', 'Thermistor NTC 10 k B3380, 0402',
     ('Device', 'Thermistor_NTC'))
# buttons: -40 to +90 C (Alps spec KRP-703; the B3U was -25..+70 C, and sim/thermal
# puts the buttons at 61-68 C in a 60 C box).  Pads 1-2 are one contact, 3-4 the
# other.  Second source, same land pattern: C&K PTS810 SJS 250 SMTR LFS
# (-40..+85 C), DigiKey CKN10878CT-ND.
PARTS['SKRP'] = ic('SKRPADE010', ('Alps Alpine', JP), 'C127488', '', 'og:KEY-SMD_4P-L4.2-W3.2-P2.20-LS4.6',
                   'Tactile switch 4.2 x 3.2 mm, top push, 4 N, -40..+90 C',
                   [('1', 'A', P), ('2', 'A', P), ('3', 'B', P), ('4', 'B', P)],
                   left=['1', '2'], right=['3', '4'], prefix='SW')
PARTS['SLIDE'] = ic('JS102011SAQN', CK, 'C221660', '', 'og:SW-SMD_JS102011SAQN',
                    'Slide switch SPDT 300 mA (drives the power switch enable, carries no load current)',
                    [('1', 'A', P), ('2', 'COM', P), ('3', 'B', P)], left=['2'], right=['1', '3'], prefix='SW')
PARTS['TPS22916'] = ic('TPS22916CYFPR', TI, 'C2680319', '', 'og:DSBGA-4_TPS22916',
                       'Load switch 5.5 V 2 A, 0.5 uA, WCSP-4 (GPS add-on supply)',
                       [('A1', 'VOUT', PO), ('A2', 'VIN', PI), ('B1', 'GND', PI), ('B2', 'ON', I)],
                       left=['A2', 'B2'], right=['A1', 'B1'])
# 2N7002-class N-FET to turn the amplifier power mux on with the board
_two('Q', 'NMOS', 'SSM3K56ACT,L3F', ('Toshiba', JP), 'C146308', 'og:SOT-883', 'SSM3K56ACT', 'N-MOSFET 20 V 0.8 A, logic level, CST3',
     ('Device', 'Q_NMOS'), {'G': '1', 'S': '2', 'D': '3'})

res('R220R', '220R', '0402', 'RC0402FR-07220RL', 'C112291')
ind('L1.6nH', '1.6nH', '0402', 'LQG15HS1N6S02D', 'C162539', MURATA, 'multilayer RF')
for v, size, mpn, lc in [('5.6pF', '0603', 'GQM1875C2E5R6CB12D', 'C2171689'), ('10pF', '0603', 'GQM1875C2E100JB12D', 'C882554'),
                         ('15pF', '0603', 'GQM1875C2E150JB12D', 'C2181572'), ('47pF', '0603', 'GQM1875C2E470JB12D', 'C882552')]:
    cap('HV' + v, v, size, '250V C0G high-Q', mpn, lc, MURATA)
# test pads: bare copper, not an assembled part
PARTS['TP'] = dict(mpn='(copper pad)', maker='', hq='', lcsc='', digikey='', fp='og:TestPoint_Pad_1.0mm',
                   value='TP', desc='Test pad', sym=('Connector', 'TestPoint'), kind='TP', pinmap={'1': '1'},
                   assembled=False, lie=False)
PARTS['HDR_2x10']['assembled'] = False

# =================================================================== DigiKey numbers and second sources
# From docs/part-audit-2026-10-17.tsv (DigiKey pages read 17 Oct 2026).  SECOND is what a US or
# allied assembler buys where the first choice was out of stock or not for new designs at DigiKey;
# same footprint and rating unless the note says otherwise.  Parts added after the audit have no
# DigiKey number yet (docs/part-audit.md lists them).
DIGIKEY = {
    'LFCG1000': '3157-LFCG-1000+CT-ND',
    'BAT68_04W': 'BAT6804WH6327XTSA1CT-ND',  # 7,598 in stock, INR 43.95@1 / 30.39@10 / 23.50@100, 20 Oct 2026
    'R49.9R_0805': '541-49.9TCT-ND',  # 178,810 in stock, INR 18.15@1 / 8.98@10 / 5.12@100, 20 Oct 2026
    'L3.6nH_0805': '490-16042-1-ND',  # sim/rf fixes, checked 19 Oct
    'L3.2nH_0805': '490-16041-1-ND',  # sim/rf fixes, checked 19 Oct
    'HV2.0pF': '490-8124-1-ND',  # sim/rf fixes, checked 19 Oct
    'HV3.6pF': '490-8127-1-ND',  # sim/rf fixes, checked 19 Oct
    'HV0.9pF': '490-GQM1875C2ER90BB12DCT-ND',  # sim/rf fixes, checked 19 Oct
    'RF0.8pF_W': '490-11253-1-ND',  # sim/rf fixes, checked 19 Oct
    'R68_0805_AS': '541-10549-1-ND',  # sim/rf fixes, checked 19 Oct
    'UFL': '26-U.FL-R-SMT-1(80)CT-ND',
    'ANT2450': '712-2450AT18A0100001ECT-ND',
    'SKRP': '4809-SKRPADE010CT-ND',
    'BGA7L1BN6': 'BGA7L1BN6E6327XTSA1CT-ND',
    'BQ25185': '296-BQ25185DLHRCT-ND',
    'BQ29700': '296-43985-1-ND',
    'C100n': '1276-1001-1-ND',
    'C100p': '490-5922-1-ND',
    'C10n': '1276-1028-1-ND',
    'C10u': '1276-1192-1-ND',
    'C10u25': '1276-2891-1-ND',
    'C12p': '1276-1178-1-ND',
    'C1n': '490-3244-1-ND',
    'C1u': '1276-1067-1-ND',
    'C1u25': '1276-1184-1-ND',
    'C470n': '1276-CL05A474KO5NNNCCT-ND',
    'C47n': '1276-1077-1-ND',
    'C47u': '445-8037-1-ND',                # TDK C3216X7S0J476M160AC, stock 29,829 (LCSC 0)
    'C4u7': '1276-1044-1-ND',
    'C820p': '490-3242-1-ND',
    'CSD25485F5': '296-47760-1-ND',
    'FB120': '490-5176-1-ND',
    'HV10pF': '490-6086-1-ND',
    'HV15pF': '490-14794-1-ND',
    'HV47pF': '490-5900-1-ND',
    'HV5.6pF': '490-7162-1-ND',
    'JST_GH6': '455-1568-1-ND',
    'JST_PH2': '455-S2B-PH-SM4-TBCT-ND',
    'JST_SH2': '455-SM02B-SRSS-TBCT-ND',
    'JST_SH6': '455-SM06B-SRSS-TBCT-ND',
    'L1.6nH': '490-8388-1-ND',
    'L10u': '445-6396-1-ND',
    'L11nH': '490-6766-1-ND',
    'L11nH_0603': '490-6859-1-ND',
    'L15nH': '490-1148-1-ND',
    'L15u': '445-6397-1-ND',
    'L2.5nH': '490-6798-1-ND',
    'L2.7nH': '490-6800-1-ND',
    'L2u2': '490-17728-1-ND',
    'L3.9nH': '490-6813-1-ND',
    'L4.7nH': '490-1139-1-ND',
    'L470n': '490-13049-1-ND',
    'L47nH': '490-1154-1-ND',
    'LED_B': '160-1647-1-ND',
    'LED_G': '160-1446-1-ND',
    'LED_R': '160-1447-1-ND',
    'NMOS': 'SSM3K56ACTL3FCT-ND',
    'NRF52840': '4823-NRF52840-QIAA-F-R7CT-ND',
    'NTC10K': '490-18149-1-ND',  # NCU15XH103F60RC (the NCP15XH103F03RC is Not For New Designs)
    'QPA9510': '2312-QPA9510TR7CT-ND',
    'R0R': '311-0.0LRCT-ND',
    'R1.5M': '13-RC0402FR-071M5LCT-ND',
    'R100k': '311-100KLRCT-ND',
    'R10k': '311-10.0KLRCT-ND',
    'R137k': 'YAG2972CT-ND',
    'R13k': '311-13.0KLRCT-ND',
    'R150_0805': '311-150CRCT-ND',
    'R1M': '311-1.00MLRCT-ND',
    'R1k': '311-1.00KLRCT-ND',
    'R2.21k': '311-2.21KLRCT-ND',
    'R2.2k': '311-2.20KLRCT-ND',
    'R2.49k': '311-2.49KLRCT-ND',
    'R22.1k': '311-22.1KLRCT-ND',
    'R220R': '311-220LRCT-ND',
    'R220k': '311-220KLRCT-ND',
    'R22R': '311-22.0LRCT-ND',
    'R22m': 'P.022AUCT-ND',
    'R261k': '311-261KLRCT-ND',
    'R267k': 'YAG3079CT-ND',
    'R301k': '311-301KLRCT-ND',
    'R330R': '311-330LRCT-ND',
    'R330k': '311-330KLRCT-ND',
    'R383k': 'YAG3139CT-ND',
    'R4.7k': '311-4.7KLRCT-ND',
    'R470R': '311-470LRCT-ND',
    'R47k': '311-47.0KLRCT-ND',
    'R5.1k': '311-5.10KLRCT-ND',
    'R510k': '311-510KLRCT-ND',
    'R562k': '311-562KLRCT-ND',
    'R604R': 'YAG3199CT-ND',
    'R68_0805': '311-68.0CRCT-ND',
    'RB060MM': 'RB060MM-30CT-ND',
    'RF0.5pF': '490-6077-1-ND',
    'RF1.0pF': '490-6073-1-ND',
    'RF1.5pF': '490-8087-1-ND',
    'RF1.8pF': '490-8089-1-ND',
    'RF10pF': '490-3113-1-ND',
    'RF15pF': '490-3117-1-ND',
    'RF2.4pF': '490-8093-1-ND',
    'RF27pF': '490-17672-1-ND',
    'RF3.0pF': '490-8095-1-ND',
    'RF39pF': '490-17673-1-ND',
    'RF47pF': '490-14446-1-ND',
    'RF5.6pF': '490-11225-1-ND',
    'SKY13330': '863-1643-1-ND',
    'SLIDE': '401-1999-1-ND',
    'SMF15CA': '18-SMF15CACT-ND',
    'SSM10N954L': '264-SSM10N954LEFFCT-ND',
    'SX1262': 'SX1262IMLTRTCT-ND',
    'TLV75528': '296-TLV75528PDQNRCT-ND',
    'TMP1075': '296-TMP1075NDRLRCT-ND',
    'TPD4E05U06': '296-35765-1-ND',
    'TPS2121': '296-53410-1-ND',
    'TPS22916': '296-50065-1-ND',
    'TPS22965': '296-39362-1-ND',
    'TPS259470A': '296-TPS259470ARPWRCT-ND',
    'TPS62840': '296-TPS62840YBGRCT-ND',
    'TPS63810': '296-TPS63810YFFRCT-ND',
    'TVS2200': '296-52187-1-ND',
    # power-path fixes (sim/), DigiKey read 19 Oct 2026
    'MAX17608': '175-MAX17608ATC+TCT-ND',   # stock 5,872 (LCSC 2: buy at DigiKey)
    'TPS22950': '296-TPS22950YBHRCT-ND',    # stock 6,273
    'CSD25310Q2': '296-50290-1-ND',         # CSD25310Q2T, stock 11,868
    'SMF33CA': '18-SMF33CACT-ND',           # stock 5,506
    'C1u50': '587-2400-1-ND',               # stock 176,196
    'C4u7_50': '1276-2789-1-ND',            # stock 9,103
    'R1R_0805': '541-1.00TCT-ND',           # stock 8,399
    'R1.15k': 'YAG3033CT-ND',               # stock 111,866
    'R2.1k': 'YAG3098CT-ND',                # stock 114,724
    'R7.68k': 'YAG3237CT-ND',               # stock 41,149
    'ZENER5V6': 'UDZVTE-175.6BCT-ND',       # stock 52,738
    'R15m': 'WSLP-.015CT-ND',               # stock 125,506
    'R20k': '311-20.0KLRCT-ND',             # stock 1,793,976
    'R374k': 'YAG3136CT-ND',                # stock 48,246
    # DigiKey numbers added by the 19 Oct 2026 re-audit
    'TCXO32': '50-ECS-TXO-20CSMV4-320-AP-TRCT-ND',  # stock 2,765, $1.6708@100 (LCSC/JLC: 0)
    'C22u16': '490-10747-1-ND',             # Murata GRM21BR61C226ME44L: 0 in stock, 3,000 due 15 Feb 2027 (see SECOND)
    'HV1.3pF': '490-GQM1875C2E1R3BB12DCT-ND',  # Murata: 0 in stock, 21 wk lead (see SECOND)
    'R287k': 'YAG3088CT-ND',                # stock 51,464
    'USBC': '12401610E4#2ACT-ND',
    'XTAL32K': '535-9543-1-ND',
    'XTAL32M': '535-13900-1-ND',
}
SECOND = {
    # Re-audited 19 Oct 2026.  Every entry is from a non-Chinese maker.  DigiKey stock is for that
    # exact MPN; where DigiKey shows no quantity for a part (backorder), it is treated as 0.
    'HV0.9pF': 'Johanson QSCP251Q0R9B1GV001T (0603 0.9pF 250V high-Q) DK 712-QSCP251Q0R9B1GV001TCT-ND stock 69,420 $0.158@10 $0.0998@100 (Murata part: 0 at DigiKey, 21 wk; Vishay VJ0603D0R9BXPAJ not stocked). JLC/LCSC: 0, consign.',
    'HV1.3pF': 'Johanson QSCP251Q1R3B1GV001T (0603 1.3pF 250V high-Q) DK 712-QSCP251Q1R3B1GV001TCT-ND stock 40,828 $0.377@10 $0.2556@100 (Murata GQM1875C2E1R3BB12D: 0 at DigiKey, 21 wk lead; LCSC C3901219 11,685). JLC/LCSC has 0 of the Johanson part, so a JLC build uses the Murata C3901219.',
    'HV5.6pF': 'Vishay VJ0603D5R6CXPAJ (0603 5.6pF +-0.25pF 250V C0G) DK 720-1322-1-ND stock 117,926 $0.307@10 $0.2037@100 (Murata part: 143 at DigiKey). JLC C2241545 has 45.',
    'C100n': 'Murata GRM155R71C104KA88J (0402 100nF 16V X7R) DK 490-6328-1-ND stock 7,438,959 $0.025@10 $0.0141@100',
    'C10u': 'Taiyo Yuden EMK107BBJ106MA-T (0603 10uF 16V X5R) DK 587-3238-1-ND stock 703,792 $0.185@10 $0.119@100',
    'C10u25': 'KYOCERA AVX KGM21AR51E106KU (0805 10uF 25V X5R) DK 478-KGM21AR51E106KUCT-ND stock 4,559 $0.386@10 $0.2584@100.',
    'C12p': 'KEMET C0402C120J5GACTU (0402 12pF 50V C0G) DK 399-C0402C120J5GACTUCT-ND stock 980,151 $0.069@10 $0.0408@100; JLC C2649548 21,568. (Murata GRM1555C1H120JA01D is now 0 at DigiKey, 10k due 13 Nov; TDK C1005C0G1H120J050BA is obsolete.)',
    'C1u25': 'TDK CGA3E1X7R1E105K080AC (0603 1uF 25V X7R) DK 445-6931-1-ND stock 854,261 $0.095@10 $0.0582@100.',
    'C22u16': 'Samsung CL21A226MOQNNNE (0805 22uF 16V X5R) DK 1276-2909-1-ND stock 2,888 $0.19@10 $0.1225@100; JLC C98190 613,316. (Murata GRM21BR61C226ME44L: 0 at DigiKey, 3,000 due 15 Feb 2027; TDK C2012X5R1C226M125AC and Taiyo Yuden EMK212BBJ226MG-T also 0, due 25 Jan / 23 Oct.)',
    'C47n': 'KEMET C0402C473K3RACTU (0402 47nF 25V X7R) DK 399-C0402C473K3RACTUCT-ND stock 276,348 $0.073@10 $0.0434@100.',
    'C47u': 'No X7S drop-in found in stock. JLC/LCSC have 0 of the TDK part (C2167997), so consign it from DigiKey (445-8037-1-ND, 29,829). X5R fallback, same 1206: Samsung CL31A476MQHNNNE (JLC C68361 801,128; DK 1276-1167-1-ND only 72) - re-run the DC-bias sim first. Murata GRT31CC80J476KE13L (X6S): DigiKey shows no quantity (97,690 is listed under its -K twin, which shows 0), so do not rely on it.',
    'C4u7': 'TDK C1608X5R1E475K080AC (0603 4.7uF 25V X5R) DK 445-9050-1-ND stock 641,155 $0.145@10 $0.0914@100 (17 Oct; not re-read). The Samsung part has 13,446 at DigiKey on 19 Oct, so no second source is needed now.',
    'L2u2': 'TDK TFM201610GHM-2R2MTAA (2016, 2.2uH, 1.9A/2.4A, 152 mOhm max, 1.0 mm high) DK 445-173104-1-ND stock 5,582 $0.369@10 $0.303@100; JLC C136243 796. Murata DFE201610E-2R2M=P2 shows no DigiKey quantity (the 88,238 is the TDK part). Check DCR/Isat against the buck sim.',
    'L2.7nH': 'Murata LQW15AN2N7B00D (0402, +-0.1nH) DK 490-6799-1-ND stock 38,938 $0.102@10 $0.0836@100; JLC C91239 50,922. Same series and footprint as the C-tolerance part (DK 126).',
    'L4.7nH': 'Bourns CW100505-4N7J (0402 wirewound 4.7nH) DK CW100505-4N7JCT-ND stock 171,521 $0.207@10 $0.1699@100 (Q lower than the LQW15: re-check the match); Wurth 744765047A (DK listing $0.44, stock not read). LQW15AN4N7C00D: DK 17, LCSC 0, JLC 87.',
    'L470n': 'Bourns SRP2512TMA-R47M (2.5x2.0x1.2, 6.2A, 18 mOhm max) DK 118-SRP2512TMA-R47MCT-ND stock 1,750 $0.245@10 $0.2018@100; JLC C19190866 has 0. (TDK TFM252012ALMAR47MTAA shows no DigiKey quantity.) Check the land pattern.',
    'L8.1nH_PA': 'Same part (no other maker has this air-core 8.1 nH): not sold at DigiKey (search returns nothing, 19 Oct). Buy from Coilcraft direct (0908SQ-8N1JLB cut tape, JLC full reel 0908SQ-8N1JLC; G = 2% is 0908SQ-8N1GLB, listed by Farnell). Mouser: not confirmed (site unreachable). LCSC C19191636 has 73 at $1.2865@100.',
    'NTC10K': 'Murata NCU15XH103F60RC (0402 10k NTC B25/50 3380K) DK 490-18149-1-ND stock 40,000 $0.065@10 $0.0527@100. NCP15XH103F03RC is Not For New Designs.',
    'NMOS': 'No exact stocked drop-in. Toshiba SSM3K56CT,L3F (same CST3 package) DK SSM3K56CTL3FCT-ND is out of stock too, 9,022 due 21 Oct. onsemi NTNS3164NZT5G (SOT-883 1x0.6, 20V) DK NTNS3164NZT5GOSCT-ND stock 25,686 $0.345@10 $0.2191@100, but Id only 361 mA and Rds(on) 0.7 ohm at 4.5V: check the 3 gate-drive uses (cell-polarity check, two amplifier-mux gates). JLC has the Toshiba part (C146308, 8,201).',
    'R1.5M': 'KOA RK73H1ETTP1504F (0402 1.5M 1%) DK 2019-RK73H1ETTP1504FCT-ND stock 69,039 $0.028@10 $0.0137@100; JLC C159956 14,595. (Panasonic ERJ-2RKF1504X is not listed at DigiKey; the Stackpole part shows no quantity.)',
    'R2.21k': 'Vishay CRCW04022K21FKED (0402 2.21k 1%) DK 541-2.21KLCT-ND stock 306,497 $0.032@10 $0.0157@100; JLC C844505 8,802. For JLC, Panasonic ERJ-2RKF2211X (C416496, 28,686). Yageo RC0402FR-132K21L: DK 16,964, JLC 0.',
    # not on the board since 19 Oct, kept from the 17 Oct audit
    'R301k': 'Panasonic ERJ-2RKF3013X (0402 301k 1%) DK P301KLCT-ND stock 246,107 $0.033@10 $0.0164@100. (RC0402FR-13301KL also 0.) JLC C171693 has 4,857.',
    'R510k': 'Yageo RC0402FR-13510KL DK 13-RC0402FR-13510KLCT-ND stock ~43,759 (read from page) $0.022@10 $0.0103@100. (Panasonic ERJ-2RKF5103X also 0.)',
    'R4.7k': 'Yageo RC0402FR-134K7L (same part, 10k reel code) DK 13-RC0402FR-134K7LCT-ND stock 68,336 $0.022@10 $0.0103@100.',
    'R68_0805_AS': 'Panasonic ERJ-P06F68R0V (0805 68R 1% 0.5W anti-surge) DK 10-ERJ-P06F68R0VCT-ND stock 19,204 $0.095@10 $0.0542@100; JLC C543529 has 0. Vishay part: DK 21,541 but LCSC 195 / JLC 198, so consign for a JLC build above ~190 boards.',
    'SKRP': 'C&K PTS810 SJS 250 SMTR LFS (same land pattern, -40..+85 C, 600 gf) DK CKN10878CT-ND stock 44,489 $0.611@10 $0.5076@100; JLC C221897 16. Alps SKRPADE010 shows no DigiKey quantity (0; 20 wk lead).',
    'TPD4E05U06': 'TI TPD4E05U06QDQARQ1 (automotive version, same USON-10 2.5x1.0 DQA package, TI) DK 296-40696-1-ND stock 137,744 $0.876@10 $0.5787@100; JLC C81353 3,280. The Diodes DT1240-04LP-7 named on 17 Oct has no DigiKey stock (the 127,377 was this TI part). The standard part is back 7 Jan 2027.',
    'XTAL32M': 'Abracon ABM11N-32.0000MHZ-8-D1X-T3 (2016, 8pF, 50 ohm) DK 535-ABM11N-32.0000MHZ-8-D1X-T3CT-ND stock 1,000 $0.553@10 $0.4803@100. The ABM11W is due 23 Oct (3,000).',
}
for _k, _pn in DIGIKEY.items():
    if _k in PARTS:
        PARTS[_k]['digikey'] = _pn
for _k, _s in SECOND.items():
    if _k in PARTS:
        PARTS[_k]['second'] = _s
