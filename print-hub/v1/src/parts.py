# -*- coding: utf-8 -*-
"""Every part on the board, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the LCSC
part number JLCPCB assembles from, the manufacturer part number for anyone
buying elsewhere, and a description.  Stock and prices were read from
JLCPCB's catalogue on 17 Oct 2026 (tools/lcsc.py; docs/parts.md has the
table and the second sources).  Read them again before ordering.

Footprints named 'ph:*' live in ../ph.pretty: the IC, diode, LED, switch,
connector and inductor footprints there are JLCPCB/EasyEDA's own library
entries for these exact LCSC parts (src/easyeda_raw, cleaned by
footprints.py), so the pad numbering and the 0-degree orientation are the
ones the assembly line uses.  Every pad number is the datasheet pin number,
checked against the EasyEDA symbol's pin names (docs/parts.md).  Plain
two-terminal R/C parts use KiCad's standard footprints, whose 0-degree
orientation matches JLCPCB's.

Choices that matter:
  * Port switch TI TPS25200: current limit 1.92-2.20 A with 47k on ILIM,
    and its output is clamped to 5.4 V (input survives 20 V), so no fault
    upstream can put 9 V on a USB port.
  * Buck Silergy SY8368A: 8 A switches for a 5 A load, 28 V input.
  * Every MLCC on the 9 V input is a 25 V or 50 V part; the 5 V rail's
    are 25 V parts too, so their capacitance holds up under bias.
"""

R0402 = 'Resistor_SMD:R_0402_1005Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
UNIROYAL, SAMSUNG = 'UNI-ROYAL', 'Samsung Electro-Mechanics'


def R(value, lcsc, mpn, fp=R0402, maker=UNIROYAL, desc=None):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker, kind='R',
                desc=desc or 'Resistor %s 1%% 0402' % value)


def C(value, fp, lcsc, mpn, rating, maker=SAMSUNG):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker, kind='C',
                desc='Capacitor %s %s' % (value, rating))


PARTS = {
    # ------------------------------------------------------------ ICs and modules
    'ESP32S3': dict(fp='ph:WIFIM-SMD_ESP32-S3-WROOM-1-N8', lcsc='C2913198', mpn='ESP32-S3-WROOM-1-N8',
                    value='ESP32-S3-WROOM-1-N8', maker='Espressif', kind='U',
                    desc='Wi-Fi + BLE module, ESP32-S3, 8 MB flash, PCB antenna'),
    'HUSB238': dict(fp='ph:DFN-10_L3.0-W3.0-P0.50-BL-EP2.5', lcsc='C7471904', mpn='HUSB238_002DD',
                    value='HUSB238', maker='Hynetek', kind='U',
                    desc='USB-PD sink controller, I2C status, DFN-10 3 x 3'),
    'SY8368A': dict(fp='ph:QFN-12_L3.0-W3.0-P0.45-TL-EP', lcsc='C207642', mpn='SY8368AQQC',
                    value='SY8368A', maker='Silergy', kind='U',
                    desc='Synchronous buck 4-28 V in, 8 A, 800 kHz, QFN-12 3 x 3'),
    'AP2112K': dict(fp='ph:SOT-25-5_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C51118', mpn='AP2112K-3.3TRG1',
                    value='AP2112K-3.3', maker='Diodes Inc', kind='U', desc='LDO 3.3 V 600 mA, SOT-25'),
    'USBLC6': dict(fp='ph:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C7519', mpn='USBLC6-2SC6',
                   value='USBLC6-2SC6', maker='STMicroelectronics', kind='U', desc='USB ESD protection, SOT-23-6'),
    'TPS25200': dict(fp='ph:WSON-6_L2.0-W2.0-P0.65-TL-EP', lcsc='C128401', mpn='TPS25200DRVR',
                     value='TPS25200', maker='Texas Instruments', kind='U',
                     desc='USB power switch 2.5 A adjustable limit, 5.4 V output clamp, WSON-6 2 x 2'),
    'INA180A2': dict(fp='ph:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL', lcsc='C192764', mpn='INA180A2IDBVR',
                     value='INA180A2', maker='Texas Instruments', kind='U',
                     desc='Current-sense amplifier 50 V/V, SOT-23-5 (pinout A)'),
    'WS2812B': dict(fp='ph:LED-SMD_4P-L2.2-W2.0-P1.00_WS2815C-2020-4P', lcsc='C52917434', mpn='WS2812B-2020-V6',
                    value='WS2812B-2020', maker='Worldsemi', kind='LED',
                    desc='RGB LED with driver, 3.3-5.3 V, 2 x 2 mm'),
    # ------------------------------------------------------------ discretes
    'SMAJ15A': dict(fp='ph:SMA_L4.3-W2.6-LS5.0-RD', lcsc='C19077535', mpn='SMAJ15A', value='SMAJ15A',
                    maker='hongjiacheng', kind='D',
                    desc='TVS 15 V stand-off, 24.4 V clamp, 400 W, SMA (pad 1 cathode)'),
    'B5819W': dict(fp='ph:SOD-123_L2.7-W1.6-LS3.7-RD-1', lcsc='C8598', mpn='B5819W SL', value='B5819W',
                   maker='Changjiang', kind='D', desc='Schottky 40 V 1 A, SOD-123 (pad 1 cathode)'),
    'L2U2': dict(fp='ph:IND-SMD_L7.0-W6.6', lcsc='C167218', mpn='FXL0630-2R2-M', value='2.2uH',
                 maker='Changjiang', kind='L', desc='Inductor 2.2 uH, 10 A sat, 15 mOhm, molded 7 x 6.6'),
    'SHUNT20M': R('20mR', 'C163047', 'RLS12FTCR020', fp=R1206, maker='TA-I Tech',
                  desc='Current shunt 20 mOhm 1 % 1 W, 1206'),
    # ------------------------------------------------------------ connectors, buttons
    'USBC': dict(fp='ph:USB-C_SMD-TYPE-C-31-M-12_1', lcsc='C165948', mpn='TYPE-C-31-M-12', value='USB-C',
                 maker='Korean Hroparts', kind='J', desc='USB-C receptacle, USB 2.0, 16 contacts, 5 A'),
    'USBA': dict(fp='ph:USB-A-TH__USB-AF-90', lcsc='C2345', mpn='902-131A1011D10100', value='USB-A',
                 maker='Jing Extension', kind='J', tht=True,
                 desc='USB-A receptacle, right angle, through-hole, 1.5 A per contact'),
    'BUTTON': dict(fp='ph:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5', lcsc='C318884', mpn='TS-1187A-B-A-B',
                   value='button', maker='XKB', kind='SW', desc='Tactile switch 5.1 x 5.1 mm'),
    # ------------------------------------------------------------ resistors
    'R100R': R('100R', 'C25076', '0402WGF1000TCE'),
    'R470R': R('470R', 'C25117', '0402WGF4700TCE'),
    'R1K': R('1k', 'C11702', '0402WGF1001TCE'),
    'R4K7': R('4.7k', 'C25900', '0402WGF4701TCE'),
    'R5K1': R('5.1k', 'C25905', '0402WGF5101TCE'),
    'R10K': R('10k', 'C25744', '0402WGF1002TCE'),
    'R15K': R('15k', 'C25756', '0402WGF1502TCE'),
    'R47K': R('47k', 'C25792', '0402WGF4702TCE'),
    'R75K': R('75k', 'C25798', '0402WGF7502TCE'),
    'R100K': R('100k', 'C25741', '0402WGF1003TCE'),
    # ------------------------------------------------------------ capacitors
    'C22P': C('22pF', C0402, 'C1555', '0402CG220J500NT', '50V C0G 0402', 'FH (Fenghua)'),
    'C100N': C('100nF', C0402, 'C1525', 'CL05B104KO5NNNC', '16V X7R 0402'),
    'C100N_50': C('100nF', C0402, 'C307331', 'CL05B104KB54PNC', '50V X7R 0402'),
    'C1U_25': C('1uF', C0402, 'C52923', 'CL05A105KA5NQNC', '25V X5R 0402'),
    'C1U_50': C('1uF', C0603, 'C15849', 'CL10A105KB8NNNC', '50V X5R 0603'),
    'C10U_10': C('10uF', C0603, 'C19702', 'CL10A106KP8NNNC', '10V X5R 0603'),
    'C22U_6V3': C('22uF', C0603, 'C59461', 'CL10A226MQ8NRNC', '6.3V X5R 0603'),
    'C10U_50': C('10uF', C1206, 'C13585', 'CL31A106KBHNNNE', '50V X5R 1206'),
    'C22U_25': C('22uF', C1206, 'C12891', 'CL31A226KAHNNNE', '25V X5R 1206'),
}

# Copper-only footprints: nothing is bought or placed for these.
PADS = {
    'TP': dict(fp='ph:PAD_TP', kind='PAD'),
    'HOLE': dict(fp='ph:MOUNT_M3', kind='H'),
}
