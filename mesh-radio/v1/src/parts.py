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

PARTS['LFCN1000'] = ic(
    'LFCN-1000+', ('Mini-Circuits', US), 'C879868', '', 'og:FILTER-SMD_1206-4P-L3.2-W1.6-L',
    'Low-pass filter DC-1000 MHz, 10 W, LTCC 1206',
    [('1', 'RF IN', P), ('2', 'GND', PI), ('3', 'RF OUT', P), ('4', 'GND', PI)],
    left=['1'], right=['3', '2', '4'], prefix='FL')

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
     ('6', 'OUT', P), ('7', 'DVDT', P), ('8', 'GND', PI), ('9', 'ILM', P), ('10', 'ITIMER', P)],
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
cap('C47u', '47uF', '0805', '6.3V X5R', 'CL21A476MQYNNNE', 'C16780')
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
res('R68_0805', '68R', '0805', 'RC0805FR-0768RL', 'C137498')
# the pad's first resistor takes the most power (sim/rf: 118 mW at +22 dBm drive)
res('R68_0805_AS', '68R', '0805', 'RCS080568R0FKEA', 'C2114866', VISHAY, '1% 0.4 W anti-surge')
res('R150_0805', '150R', '0805', 'RC0805FR-07150RL', 'C114523')
res('R22m', '22mR', '1206', 'ERJ-8BWFR022V', 'C2075813', PANASONIC, '1% 1 W')

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
_two('D', 'ZENER4V7', 'UDZVTE-174.7B', ROHM, 'C209560', 'og:SOD-323FL', '4.7V', 'Zener 4.7 V 200 mW, SOD-323FL',
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
_two('TH', 'NTC10K', 'NCP15XH103F03RC', MURATA, 'C77131', 'og:R_0402', '10k NTC', 'Thermistor NTC 10 k B3380, 0402',
     ('Device', 'Thermistor_NTC'))
_two('SW', 'B3U', 'B3U-1000P', OMRON, 'C231329', 'og:KEY-SMD_B3U-1000PM', 'B3U-1000P', 'Tactile switch, top push',
     ('Switch', 'SW_Push'))
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
    'UFL': '26-U.FL-R-SMT-1(80)CT-ND',
    'ANT2450': '712-2450AT18A0100001ECT-ND',
    'B3U': 'SW1020CT-ND',
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
    'C47u': '1276-1852-1-ND',
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
    'LFCN1000': '3157-LFCN-1000+CT-ND',
    'NMOS': 'SSM3K56ACTL3FCT-ND',
    'NRF52840': '4823-NRF52840-QIAA-F-R7CT-ND',
    'NTC10K': '490-4801-1-ND',
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
    'USBC': '12401610E4#2ACT-ND',
    'XTAL32K': '535-9543-1-ND',
    'XTAL32M': '535-13900-1-ND',
}
SECOND = {
    'C100n': 'Murata GRM155R71C104KA88J (0402 100nF 16V X7R) DK 490-6328-1-ND stock 7,440,307 $0.025@10 $0.0141@100',
    'C10u': 'Taiyo Yuden EMK107BBJ106MA-T (0603 10uF 16V X5R) DK 587-3238-1-ND stock 703,701 $0.185@10 $0.119@100',
    'C10u25': 'KYOCERA AVX KGM21AR51E106KU (0805 10uF 25V X5R) DK 478-KGM21AR51E106KUCT-ND stock 5,472 $0.386@10 $0.2584@100.',
    'C12p': 'Murata GRM1555C1H120JA01D (0402 12pF 50V C0G) DK 490-5924-1-ND stock 2,493 $0.023@10 $0.0129@100.',
    'C1u25': 'TDK CGA3E1X7R1E105K080AC (0603 1uF 25V X7R) DK 445-6931-1-ND stock 867,741 $0.095@10 $0.0582@100.',
    'C47n': 'KEMET C0402C473K3RACTU (0402 47nF 25V X7R) DK 399-C0402C473K3RACTUCT-ND stock 276,448 $0.073@10 $0.0434@100.',
    'C47u': 'Samsung CL21A476MQYNNNG (same part, different packaging code) DK 1276-6467-1-ND stock 19,300 $0.204@10 $0.1321@100.',
    'C4u7': 'TDK C1608X5R1E475K080AC (0603 4.7uF 25V X5R) DK 445-9050-1-ND stock 641,155 $0.145@10 $0.0914@100.',
    'L470n': 'TDK TFM252012ALMAR47MTAA (2520 0.47uH 4.9A/24mOhm) DK 445-181489-1-ND stock 940 $0.468@10 $0.3845@100; or Bourns SRP2512TMA-R47M (2.5x2.0x1.2, 6.2A/18mOhm) DK 118-SRP2512TMA-R47MCT-ND stock 1,750 $0.2',
    'NTC10K': 'NCU15XH103F60RC (0402 10k NTC B3380K) DK 490-18149-1-ND stock 45,468 $0.065@10 $0.0527@100. Check B-value vs firmware table (NCP15XH103 is B3380 also).',
    'R1.5M': 'Stackpole RMCF0402FT1M50 DK RMCF0402FT1M50CT-ND stock 33,358 $0.023@10 $0.0107@100. | DK stock 34',
    'R301k': 'Panasonic ERJ-2RKF3013X (0402 301k 1%) DK P301KLCT-ND stock 246,107 $0.033@10 $0.0164@100. (RC0402FR-13301KL also 0.) JLC C171693 has 4,857.',
    'R4.7k': 'Yageo RC0402FR-134K7L (same part, 10k reel code) DK 13-RC0402FR-134K7LCT-ND stock 769,461 $0.022@10 $0.0103@100.',
    'R510k': 'Yageo RC0402FR-13510KL DK 13-RC0402FR-13510KLCT-ND stock ~43,759 (read from page) $0.022@10 $0.0103@100. (Panasonic ERJ-2RKF5103X also 0.)',
    'TPD4E05U06': 'Diodes Inc DT1240-04LP-7 (U-DFN2510-10, same 2.5x1.0 10-pin flow-through, 5.5V) DK DT1240-04LP-7DICT-ND stock 127,377 $0.296@10 $0.1868@100 - confirm pinout. Beware GOODWORK clone listing at DK.',
    'XTAL32M': 'Abracon ABM11N-32.0000MHZ-8-D1X-T3 (2016, 8pF, 50 ohm) DK 535-ABM11N-32.0000MHZ-8-D1X-T3CT-ND stock 1,000 $0.553@10 $0.4803@100',
}
for _k, _pn in DIGIKEY.items():
    if _k in PARTS:
        PARTS[_k]['digikey'] = _pn
for _k, _s in SECOND.items():
    if _k in PARTS:
        PARTS[_k]['second'] = _s
