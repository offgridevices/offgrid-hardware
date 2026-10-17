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
    ('Y2', 'VDDH', PI), ('AB2', 'DCCH', P), ('B1', 'VDD', PO), ('W1', 'VDD', PO), ('AD14', 'VDD', PO),
    ('AD23', 'VDD', PO), ('A22', 'VDD', PO), ('B3', 'DCC', P), ('B5', 'DEC4', P), ('C1', 'DEC1', P),
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
    'NRF52840-QIAA-R', ('Nordic Semiconductor', NO), 'C190794', '',
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
    'ECS-TXO-20CSMV4-320-AY-TR', ('ECS Inc.', US), 'C19858587', '', 'og:OSC-SMD_4P-L2.0-W1.6-BL',
    'TCXO 32 MHz +/-0.5 ppm, clipped sine, 2.0 x 1.6',
    [('1', 'GND', PI), ('2', 'GND', PI), ('3', 'OUT', O), ('4', 'VDD', PI)],
    left=['4', '1', '2'], right=['3'], prefix='Y')

# =================================================================== RF front end
QPA_PINS = []   # filled in once its datasheet pin table is confirmed (docs/part-audit.md)

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
    [('1', 'OUT', PO), ('8', 'OUT', PO), ('2', 'IN2', PI), ('7', 'IN1', PI), ('3', 'CP2', P), ('4', 'OV2', I),
     ('5', 'OV1', I), ('6', 'PR1', I), ('9', 'ST', OC), ('10', 'ILM', P), ('11', 'SS', P), ('12', 'GND', PI)],
    left=['7', '2', '6', '5', '4', '3'], right=['1', '8', '9', '10', '11', '12'])

PARTS['TPS63810'] = ic(
    'TPS63810YFFR', TI, 'C1852139', '', 'og:DSBGA-15_L2.2-W1.4-R3-V5-P0.40-BL',
    'Buck-boost 2.2-5.5 V in, 1.8-5.2 V out (I2C), 2.5 A, 13 uA, WCSP-15 (amplifier supply)',
    [('A1', 'EN', I), ('A2', 'VIN', PI), ('A3', 'VIN', PI), ('B1', 'VSEL', I), ('B2', 'LX1', P), ('B3', 'LX1', P),
     ('C1', 'AGND', PI), ('C2', 'GND', PI), ('C3', 'GND', PI), ('D1', 'SCL', I), ('D2', 'LX2', P), ('D3', 'LX2', P),
     ('E1', 'SDA', B), ('E2', 'VOUT', PO), ('E3', 'VOUT', PO)],
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
     ('7', 'VOUT', PO), ('8', 'VOUT', PO), ('9', 'GND (EP)', PI)],
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
    fp='og:PinHeader_2x10_P2.54mm', desc='Expansion header footprint, 2.54 mm, fitted only when needed',
    sym='box', kind='J', dnp=True,
    symbol=dict(prefix='J', left=[str(i) for i in range(1, 21, 2)], right=[str(i) for i in range(2, 21, 2)],
                pins={str(i): (str(i), P) for i in range(1, 21)}))
