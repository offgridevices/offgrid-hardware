# -*- coding: utf-8 -*-
"""Every part on the board, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the LCSC part
number JLCPCB assembles from, the manufacturer part number for anyone buying
elsewhere, and a description.

Every LCSC number here was checked against JLCPCB's live parts API when the
board was designed (stock and 'basic' vs 'extended' noted in the comment).
Basic parts carry no per-part setup fee at JLCPCB, so the passives were
chosen from the basic library wherever a value would do.

Footprints named 'aio:*' live in ../aio.pretty. The IC, transistor, diode,
LED, crystal, connector and inductor footprints there were converted from
JLCPCB/EasyEDA's own library entries for these exact LCSC parts, so pad
geometry and 0-degree orientation match what the assembly line expects.
Plain two-terminal R/C parts use KiCad's standard footprints, whose
0-degree orientation already matches.
"""

R0402 = 'Resistor_SMD:R_0402_1005Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'

def R(value, lcsc, mpn):
    return dict(fp=R0402, lcsc=lcsc, mpn=mpn, value=value,
                desc='Resistor %s 1%% 0402' % value, kind='R')

def C(value, fp, lcsc, mpn, rating):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value,
                desc='Capacitor %s %s' % (value, rating), kind='C')

PARTS = {
    # ---------------------------------------------------------------- ICs
    # 1,690 in stock, extended.  The same MCU as the GEPRC TAKER G4 AIO.
    'STM32G473': dict(fp='aio:UFQFPN-48_L7.0-W7.0-P0.50-BL-EP5.6', lcsc='C1342773',
                      mpn='STM32G473CEU6', value='STM32G473CEU6',
                      desc='MCU Cortex-M4 170 MHz 512 KB, UFQFPN-48', kind='U'),
    # Genuine TDK part (392 in stock).  A Tokmas clone is cheaper but the
    # flight controller's gyro is not the place to find out a clone differs.
    'ICM42688P': dict(fp='aio:LGA-14_L3.0-W2.5-P0.50-TL', lcsc='C1850418',
                      mpn='ICM-42688-P', value='ICM-42688-P',
                      desc='6-axis IMU, SPI, LGA-14 2.5x3', kind='U'),
    # Bosch BMI270 on the ICM-42688-P's land pattern (pads within 0.09 mm;
    # JLCPCB's library footprint for it is this one turned 180 degrees).
    # $1.36 against $15.43 at 1000, and in stock where the ICM is not.
    # Its pins 2/3 (aux I2C) must not be grounded, so circuit.py leaves
    # them open, which the ICM-42688-P also allows: either part fits.
    'BMI270': dict(fp='aio:LGA-14_L3.0-W2.5-P0.50-TL', lcsc='C2836813',
                   mpn='BMI270', value='BMI270', jlc_rot=180,
                   desc='6-axis IMU (Bosch), SPI, LGA-14 2.5x3', kind='U'),
    # Puya PY25Q128HA on the W25Q128's WSON-8 land (pads within 0.11 mm;
    # JLCPCB's footprint is this one turned 90 degrees).
    'PY25Q128': dict(fp='aio:WSON-8_L6.0-W5.0-P1.27-BL-EP', lcsc='C18208279',
                     mpn='PY25Q128HA-WXH-IR', value='PY25Q128HA', jlc_rot=90,
                     desc='16 MB SPI NOR flash (blackbox), WSON-8 6x5', kind='U'),
    'W25Q128': dict(fp='aio:WSON-8_L6.0-W5.0-P1.27-BL-EP', lcsc='C190862',
                    mpn='W25Q128JVPIQ', value='W25Q128JVPIQ',
                    desc='16 MB SPI NOR flash (blackbox), WSON-8 6x5', kind='U'),
    # 36 V input: 4S is 16.8 V charged and regen spikes ride on top of that.
    'LMR51420': dict(fp='aio:SOT-23-6_L2.9-W1.6-P0.95-LS2.9-BL', lcsc='C5383002',
                     mpn='LMR51420YDDCR', value='LMR51420YDDCR',
                     desc='Buck 4.5-36 V in, 2 A, 1.1 MHz, SOT-23-6', kind='U'),
    'ME6211': dict(fp='aio:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BL', lcsc='C82942',
                   mpn='ME6211C33M5G-N', value='ME6211C33',
                   desc='LDO 3.3 V 500 mA, SOT-23-5', kind='U'),
    # 40 V common-mode: survives the same spikes as the buck.
    'INA186A2': dict(fp='aio:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL', lcsc='C2058238',
                     mpn='INA186A2IDCKR', value='INA186A2',
                     desc='Current-sense amp 50 V/V, 40 V CM, SC-70-6', kind='U'),
    'USBLC6': dict(fp='aio:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C7519',
                   mpn='USBLC6-2SC6', value='USBLC6-2SC6',
                   desc='USB ESD protection, SOT-23-6', kind='U'),
    # ESC MCU: the original AM32 platform.  Flashes with any ST-Link through
    # STM32CubeProgrammer, which matters because every one arrives blank.
    'STM32F051': dict(fp='aio:UFQFPN-32_L5.0-W5.0-P0.50-BL-EP', lcsc='C81451',
                      mpn='STM32F051K6U6', value='STM32F051K6U6',
                      desc='ESC MCU Cortex-M0 48 MHz, UFQFPN-32', kind='U'),
    # FD6288Q-compatible 3-phase gate driver, both inputs active-high.
    # Genuine Fortior stock was zero; JSMSEMI's part is pin-for-pin (31,906).
    'JSM6288Q': dict(fp='aio:VQFN-24_L4.0-W4.0-P0.50-TL-EP2.7', lcsc='C19077370',
                     mpn='JSM6288Q', value='JSM6288Q',
                     desc='3-phase gate driver (FD6288Q equiv.), QFN-24 4x4', kind='U'),
    # One half-bridge per package: high FET D1->S1=D2 low FET ->S2.
    # 30 V, +/-20 V gate, 10.2/7.7 mOhm at 10 V.  129,263 in stock.
    'AON7934': dict(fp='aio:DFN-8_L3.0-W3.0-P0.65-BL_AON7934', lcsc='C485677',
                    mpn='AON7934', value='AON7934',
                    desc='Dual asymmetric N-MOSFET half-bridge 30 V, DFN3x3', kind='Q'),
    # Same JLCPCB footprint as the 2N7002, and specified at 2.5 V gate drive
    # (48 mOhm), which the 3.3 V GPIO needs.  Basic part.
    'AO3400A': dict(fp='aio:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', lcsc='C20917',
                    mpn='AO3400A', value='AO3400A',
                    desc='N-MOSFET 30 V logic level, beeper driver, SOT-23', kind='Q'),
    '2N7002': dict(fp='aio:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', lcsc='C8545',
                   mpn='2N7002', value='2N7002',
                   desc='N-MOSFET 60 V, beeper driver, SOT-23', kind='Q'),

    # ---------------------------------------------------------------- discretes
    '1N5819WS': dict(fp='aio:SOD-323_L1.8-W1.3-LS2.5-RD', lcsc='C191023',
                     mpn='1N5819WS', value='1N5819WS',
                     desc='Schottky 40 V 1 A, SOD-323 (basic)', kind='D'),
    # Bootstrap diodes: 30 V 200 mA Schottky in SOD-523, a third the area of
    # SOD-323.  Driver VCC tops out at 16.8 V on a full 4S pack.
    # 15 V clamp on each gate driver's supply (same JLCPCB SOD-523
    # footprint as the RB521S30: pad 1 cathode).
    'BZX585C15': dict(fp='aio:SOD-523_L1.2-W0.8-LS1.6-RD', lcsc='C550633',
                      mpn='BZX585-C15,135', value='15V',
                      desc='Zener 15 V 300 mW, SOD-523', kind='D'),
    'RB521S30': dict(fp='aio:SOD-523_L1.2-W0.8-LS1.6-RD', lcsc='C145179',
                     mpn='RB521S30T1G', value='RB521S30',
                     desc='Schottky 30 V 200 mA, SOD-523', kind='D'),
    'LED_RED': dict(fp='aio:LED-SMD_L1.6-W0.8-R-RD', lcsc='C2286',
                    mpn='KT-0603R', value='RED', desc='LED red 0603 (basic)', kind='LED'),
    'LED_BLUE': dict(fp='aio:LED0603-RD_BLUE', lcsc='C965807',
                     mpn='XL-1608UBC-04', value='BLUE', desc='LED blue 0603', kind='LED'),
    'XTAL8M': dict(fp='aio:CRYSTAL-SMD_4P-L3.2-W2.5-BL', lcsc='C400090',
                   mpn='TAXM8M4RDBCCT2T', value='8MHz',
                   desc='Crystal 8 MHz 10 pF 3225', kind='Y'),
    # FC BEC inductor: Isat 5 A, above the LMR51420's 2.7-5.1 A current
    # limit as TI's design procedure asks (9.2.2.4).  The 3 x 3 mm FNR3015
    # saturates at 1.4 A: fine for the ESC's 0.1 A 3.3 V rail, not for a
    # 2 A BEC.
    'L4U7H': dict(fp='aio:IND-SMD_L5.4-W5.2_FXL0530', lcsc='C177246',
                  mpn='FXL0530-4R7-M', value='4.7uH',
                  desc='Inductor 4.7 uH Isat 5 A, 5.4 x 5.2 mm molded', kind='L'),
    'L4U7': dict(fp='aio:IND-SMD_L3.0-W3.0_FNR30XXS', lcsc='C167753',
                 mpn='FNR3015S4R7MT', value='4.7uH',
                 desc='Inductor 4.7 uH 1.3 A shielded 3x3', kind='L'),
    'SHUNT': dict(fp='aio:RES-SMD_L6.4-W3.2_RLM25', lcsc='C710260',
                  mpn='RLM25FEGMR50M', value='0.5mR',
                  desc='Current shunt 0.5 mOhm 3 W 2512', kind='R'),
    'USBC': dict(fp='aio:USB-C_SMD-TYPE-C-31-M-12_1', lcsc='C165948',
                 mpn='TYPE-C-31-M-12', value='USB-C',
                 desc='USB-C receptacle 16P', kind='J'),
    # JST SH 1.0 mm 8-pin, the FPV-standard flight-controller <-> 4-in-1 ESC
    # lead.  Right-angle on the flight controller (rear edge, cable leaves
    # backwards and folds down), vertical on the ESC (cable comes straight
    # down from above).  Genuine JST, 124,934 / 12,540 in stock.
    'SH8_RA': dict(fp='aio:CONN-TH_SM08B-SRSS-TB-LF-SN', lcsc='C160407',
                   mpn='SM08B-SRSS-TB(LF)(SN)', value='SH-8P RA',
                   desc='JST SH 8-pin right-angle SMD', kind='J'),
    'SH8_V': dict(fp='aio:CONN-TH_BM08B-SRSS-TB-LF-SN', lcsc='C160394',
                  mpn='BM08B-SRSS-TB(LF)(SN)', value='SH-8P V',
                  desc='JST SH 8-pin vertical SMD', kind='J'),
    'BOOTSW': dict(fp='aio:SW-SMD_L3.9-W3.0-P4.45', lcsc='C720477',
                   mpn='TS-1088-AR02016', value='BOOT',
                   desc='Tact switch 4x3 mm (basic)', kind='SW'),

    # ---------------------------------------------------------------- resistors (basic unless noted)
    'R10':   R('10R',  'C25077', '0402WGF100JTCE'),
    'R100':  R('100R', 'C25076', '0402WGF1000TCE'),
    'R750':  R('750R', 'C25132', '0402WGF7500TCE'),   # extended
    'R1K':   R('1k',   'C11702', '0402WGF1001TCE'),
    'R330':  R('330R', 'C25104', '0402WGF3300TCE'),
    'R2K':   R('2k',   'C4109',  '0402WGF2001TCE'),
    'R2K2':  R('2.2k', 'C25879', '0402WGF2201TCE'),
    'R5K1':  R('5.1k', 'C25905', '0402WGF5101TCE'),
    'R10K':  R('10k',  'C25744', '0402WGF1002TCE'),
    'R11K':  R('11k',  'C25749', '0402WGF1102TCE'),   # extended
    'R15K':  R('15k',  'C25756', '0402WGF1502TCE'),
    'R22K':  R('22k',  'C25768', '0402WGF2202TCE'),
    'R100K': R('100k', 'C25741', '0402WGF1003TCE'),

    # ---------------------------------------------------------------- capacitors (basic)
    'C12P':   C('12pF',  C0402, 'C1547',   '0402CG120J500NT',  '50V C0G 0402'),
    'C100N':  C('100nF', C0402, 'C307331', 'CL05B104KB54PNC',  '50V X7R 0402'),
    'C1U':    C('1uF',   C0402, 'C52923',  'CL05A105KA5NQNC',  '25V X5R 0402'),
    'C4U7':   C('4.7uF', C0402, 'C23733',  'CL05A475MP5NRNC',  '10V X5R 0402'),
    # Samsung rather than Murata: 216k at JLCPCB against a few thousand
    'C10U50': C('10uF',  C0805, 'C2932476', 'CL21A106KBYQNNE', '50V X5R 0805'),
    'C22U25': C('22uF',  C0805, 'C45783',  'CL21A226MAQNNNE',  '25V X5R 0805'),
    'C10U50B':C('10uF',  C1206, 'C13585',  'CL31A106KBHNNNE',  '50V X5R 1206'),
}

# Things that are copper only: solder pads, test points, mounting holes.
# They carry no LCSC number and are left out of the BOM and pick-and-place.
PADS = {
    'PAD_BAT':   dict(fp='aio:PAD_BAT',   kind='PAD'),
    'PAD_MOTOR': dict(fp='aio:PAD_MOTOR', kind='PAD'),
    'PAD_SIG':   dict(fp='aio:PAD_SIG',   kind='PAD'),
    'PAD_TP':    dict(fp='aio:PAD_TP',    kind='PAD'),
    'HOLE':      dict(fp='aio:HOLE_M3',   kind='H'),
}
