# -*- coding: utf-8 -*-
"""Every part on the board, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the LCSC
part number JLCPCB assembles from, the manufacturer part number for
anyone buying elsewhere, and a description.  Stock was read from JLCPCB's
and LCSC's catalogues on 2 Oct 2026 (tools/lcsc.py); read it again with
tools/lcsc.py before any order: stock changes.

Footprints named 'og:*' live in ../og.pretty: the IC, transistor, diode,
LED, crystal, connector and inductor footprints there are JLCPCB/EasyEDA's
own library entries for these exact LCSC parts (src/easyeda_raw, cleaned by
footprints.py), so the pad geometry and the 0-degree orientation match what
the assembly line expects.  Plain two-terminal R/C parts use KiCad's
standard footprints, whose 0-degree orientation already matches.

Choices that matter for the board surviving full throttle in the heat:
  * FETs: Toshiba TPN2R304PL, 40 V (2.3x a full 4S HV pack), 2.3 mOhm
    maximum at 10 V, 175 C channel rating, 1.43 C/W junction to case.
  * 5 V BEC: TI LMR36506, 70 V absolute maximum on its input.
  * gate drive: TI DRV8300D at a regulated 11 V (TPS7A1601, 60 V input).
  * every MLCC at a rating at least 1.5x its working voltage; the ones on
    the battery are 50 V parts.
"""

R0201 = 'og:R_0201_0603Metric_L'
R0402 = 'og:R_0402_1005Metric_L'
C0201 = 'og:C_0201_0603Metric_L'
C0402 = 'og:C_0402_1005Metric_L'
C0603 = 'og:C_0603_1608Metric_L'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'

def R(value, fp, lcsc, mpn, maker, tol='1%'):
    size = '0201' if fp == R0201 else '0402'
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker,
                desc='Resistor %s %s %s' % (value, tol, size), kind='R')

def C(value, fp, lcsc, mpn, rating, maker):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker,
                desc='Capacitor %s %s' % (value, rating), kind='C')

ST, TI = 'STMicroelectronics', 'Texas Instruments'
YAGEO, UNIROYAL, SAMSUNG, MURATA = 'Yageo', 'UNI-ROYAL', 'Samsung Electro-Mechanics', 'Murata'

PARTS = {
    # ------------------------------------------------------------ ICs
    'STM32G473': dict(fp='og:UFQFPN-48_L7.0-W7.0-P0.50-BL-EP5.6', lcsc='C1342773', mpn='STM32G473CEU6',
                      value='STM32G473CEU6', maker=ST, kind='U',
                      desc='MCU Cortex-M4F 170 MHz, 512 KB flash, UFQFPN-48 (flight controller)'),
    'ICM42688P': dict(fp='og:LGA-14_L3.0-W2.5-P0.50-TL', lcsc='C1850418', mpn='ICM-42688-P',
                      value='ICM-42688-P', maker='TDK InvenSense', kind='U',
                      desc='6-axis IMU (gyro + accelerometer), SPI, LGA-14 2.5 x 3'),
    'STM32G071G': dict(fp='og:UFQFPN-28_L4.0-W4.0-P0.50-BL', lcsc='C529347', mpn='STM32G071GBU6',
                       value='STM32G071GBU6', maker=ST, kind='U',
                       desc='MCU Cortex-M0+ 64 MHz, 128 KB flash, UFQFPN-28 (ESC, AM32)'),
    'DRV8300D': dict(fp='og:VQFN-24_L4.0-W4.0-P0.50-TL-EP2.5', lcsc='C3655801', mpn='DRV8300DRGER',
                     value='DRV8300DRGER', maker=TI, kind='U',
                     desc='100 V three-phase gate driver, bootstrap diodes, VQFN-24 4 x 4'),
    'INA186A3': dict(fp='og:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL-1', lcsc='C2058245', mpn='INA186A3IDCKR',
                     value='INA186A3', maker=TI, kind='U',
                     desc='Current-sense amplifier 100 V/V, zero drift, SC-70-6'),
    'LMR36506R5': dict(fp='og:VQFN-9_L2.1-W2.1-P0.50-TL', lcsc='C2866484', mpn='LMR36506R5RPER',
                       value='LMR36506R5', maker=TI, kind='U',
                       desc='Buck 4.2-65 V in, fixed 5 V 0.6 A, VQFN-HR-9 2 x 2 (BEC)'),
    'TLV76733': dict(fp='og:WSON-6_L2.0-W2.0-P0.65-TL-EP', lcsc='C2848334', mpn='TLV76733DRVR',
                     value='TLV76733', maker=TI, kind='U',
                     desc='LDO 3.3 V 1 A, 16 V in, WSON-6 2 x 2'),
    'TPS7A1601': dict(fp='og:SON-8_L3.0-W3.0-P0.65-TL-EP', lcsc='C2867753', mpn='TPS7A1601DRBR',
                      value='TPS7A1601', maker=TI, kind='U',
                      desc='LDO adjustable 100 mA, 60 V in, SON-8 3 x 3 (gate-drive supply)'),
    'USBLC6': dict(fp='og:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C7519', mpn='USBLC6-2SC6',
                   value='USBLC6-2SC6', maker=ST, kind='U', desc='USB ESD protection, SOT-23-6'),
    # ------------------------------------------------------------ discretes
    'TPN2R304PL': dict(fp='og:TSON-8_L3.1-W3.1-P0.65-LS3.3-BL-EP', lcsc='C5802634', mpn='TPN2R304PL,L1Q',
                       value='TPN2R304PL', maker='Toshiba', kind='Q',
                       desc='N-MOSFET 40 V 80 A, 2.3 mOhm max at 10 V, TSON Advance 3.3 x 3.3'),
    'AO3400A': dict(fp='og:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', lcsc='C20917', mpn='AO3400A',
                    value='AO3400A', maker='Alpha & Omega', kind='Q', desc='N-MOSFET 30 V 5.7 A, SOT-23 (buzzer)'),
    # MCC's SMF22A-TP: Active (DigiKey); the GOODWORK SMF22A first chosen
    # publishes no lifecycle status (docs/lifecycle.md)
    'SMF22A': dict(fp='og:SOD-123FL_L2.8-W1.9-LS3.7-RD', lcsc='C1974299', mpn='SMF22A-TP',
                   value='SMF22A', maker='MCC', kind='D',
                   desc='TVS 22 V stand-off, 35.5 V clamp at 5.6 A, 200 W, SOD-123FL'),
    # PANJIT SS1040HE, Active; it replaces ROHM's RB160VAM-40, now NRND
    # (docs/lifecycle.md).  Same SOD-323HE land, cathode on pad 1.
    'SS1040HE': dict(fp='og:SOD-323HE_L2.0-W1.4-LS2.5-RD', lcsc='C282389', mpn='SS1040HEWS_R1_00001',
                     value='SS1040HE', maker='PANJIT', kind='D', desc='Schottky 40 V 1 A, SOD-323HE (USB OR-ing)'),
    'LED_RED': dict(fp='og:LED0603-RD', lcsc='C125099', mpn='LTST-C191KRKT', value='red',
                    maker='Lite-On', kind='LED', desc='LED red 0603 (pad 1 cathode)'),
    'LED_BLUE': dict(fp='og:LED0603-RD', lcsc='C99290', mpn='LTST-C191TBKT', value='blue',
                     maker='Lite-On', kind='LED', desc='LED blue 0603 (pad 1 cathode)'),
    'XTAL8M': dict(fp='og:CRYSTAL-SMD_4P-L3.2-W2.5-BL', lcsc='C5727434', mpn='ECS-80-10-33-CHN-TR3',
                   value='8 MHz', maker='ECS', kind='Y', desc='Crystal 8 MHz 10 ppm, 10 pF, 3.2 x 2.5'),
    # 0.92 A saturation against the BEC's 0.71 A simulated peak (sim/bec);
    # in a dead short the LMR36506's cycle-by-cycle limit and hiccup mode
    # protect it.
    'L10U': dict(fp='og:IND-SMD_L3.0-W3.0_SWPA3010S', lcsc='C45403', mpn='SWPA3015S100MT', value='10uH',
                 maker='Sunlord', kind='L', desc='Inductor 10 uH, 0.92 A sat, 0.77 A rms, 325 mOhm, shielded 3 x 3 x 1.5'),
    'SHUNT_0M5': dict(fp='og:RES-SMD_1206_HCS1206', lcsc='C346511', mpn='HCS1206FTL500',
                      value='0.5mOhm', maker='Stackpole', kind='R',
                      desc='Current shunt 0.5 mOhm 1 % 2 W, metal element, 1206'),
    # ------------------------------------------------------------ connectors, switch
    # Surface-mount shell (pads 8-11): nothing but two 0.65 mm locating pegs
    # goes through the board, so the ESC FETs can sit under it.
    'USBC': dict(fp='og:USB-C-SMD_TYPE-C-16P-USB4110-GF-A', lcsc='C5143397', mpn='USB4110-GF-A',
                 value='USB-C', maker='GCT', kind='J',
                 desc='USB-C receptacle, USB 2.0, 16 contacts, all-SMD shell'),
    'BOOTSW': dict(fp='og:KEY-SMD_B3U-1000PM', lcsc='C231329', mpn='B3U-1000P', value='BOOT',
                   maker='Omron', kind='SW', desc='Tactile switch 3 x 2.5 mm (DFU boot)'),
    # ------------------------------------------------------------ resistors
    'R10R_0402': R('10R', R0402, 'C25077', '0402WGF100JTCE', UNIROYAL),
    'R10K':      R('10k', R0402, 'C25744', '0402WGF1002TCE', UNIROYAL),
    'R82K':      R('82k', R0402, 'C482240', 'CRCW040282K0FKED', 'Vishay'),
    'R100K':     R('100k', R0402, 'C25741', '0402WGF1003TCE', UNIROYAL),
    'R22R_0201': R('22R', R0201, 'C155743', 'RC0201FR-0722RL', YAGEO),
    'R10R_0201': R('10R', R0201, 'C106226', 'RC0201FR-0710RL', YAGEO),
    'R100R_0201': R('100R', R0201, 'C77623', 'RC0201FR-07100RL', YAGEO),
    'R330_0201': R('330R', R0201, 'C274872', 'RC0201FR-07330RL', YAGEO),
    'R1K_0201':  R('1k', R0201, 'C138165', 'RC0201FR-071KL', YAGEO),
    'R1K5_0201': R('1.5k', R0201, 'C270361', '0201WMF1501TEE', UNIROYAL),
    'R2K2_0201': R('2.2k', R0201, 'C142018', 'RC0201FR-072K2L', YAGEO),
    'R5K1_0201': R('5.1k', R0201, 'C274341', 'RC0201FR-075K1L', YAGEO),
    'R10K_0201': R('10k', R0201, 'C106225', 'RC0201FR-0710KL', YAGEO),
    'R27K_0201': R('27k', R0201, 'C273283', 'RC0201FR-0727KL', YAGEO),
    'R62K_0201': R('62k', R0201, 'C295812', 'RC0201FR-0762KL', YAGEO),
    # ------------------------------------------------------------ capacitors
    'C12P':      C('12pF', C0402, 'C1547', '0402CG120J500NT', '50V C0G 0402', 'FH (Fenghua)'),
    'C100N_0201': C('100nF', C0201, 'C307380', 'CL03A104KO3NNNC', '16V X5R 0201', SAMSUNG),
    'C1U_0201':  C('1uF', C0201, 'C76935', 'GRM033R61A105ME44D', '10V X5R 0201', MURATA),
    'C100N_50':  C('100nF', C0402, 'C307331', 'CL05B104KB54PNC', '50V X7R 0402', SAMSUNG),
    'C1U_25':    C('1uF', C0402, 'C52923', 'CL05A105KA5NQNC', '25V X5R 0402', SAMSUNG),
    'C4U7_0402': C('4.7uF', C0402, 'C23733', 'CL05A475MP5NRNC', '10V X5R 0402', SAMSUNG),
    'C10U_25':   C('10uF', C0603, 'C96446', 'CL10A106MA8NRNC', '25V X5R 0603', SAMSUNG),
    'C4U7_25':   C('4.7uF', C0805, 'C1779', 'CL21A475KAQNNNE', '25V X5R 0805', SAMSUNG),
    'C22U_25':   C('22uF', C0805, 'C86816', 'GRM21BR61E226ME44L', '25V X5R 0805', MURATA),
    'C4U7_50':   C('4.7uF', C0805, 'C437557', 'GRM21BZ71H475KE15L', '50V X7R 0805', MURATA),
}

# Copper-only footprints: no part is bought or placed for these.
PADS = {
    'PAD_BAT':   dict(fp='og:PAD_BAT',   kind='PAD'),
    'PAD_MOTOR': dict(fp='og:PAD_MOTOR', kind='PAD'),
    'PAD_SIG':   dict(fp='og:PAD_SIG',   kind='PAD'),
    'PAD_TP':    dict(fp='og:PAD_TP',    kind='PAD'),
    'HOLE':      dict(fp='og:MOUNT_M2',  kind='H'),
}
