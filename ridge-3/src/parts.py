# -*- coding: utf-8 -*-
"""Every part on the board, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the LCSC part
number JLCPCB assembles from, the manufacturer part number for anyone buying
elsewhere, and a description.  Entries added for Ridge 3 also carry

  dk      the DigiKey part number (cut tape where DigiKey sells it cut)
  dk_mpn  the part DigiKey sells under `dk`, when it is not `mpn`: another
          reel size of the same die (TI ...DGNT / ...RNPT / ...DRVT), or, for
          a passive, an equivalent from a maker DigiKey stocks (Yageo /
          Panasonic for the UNI-ROYAL resistors JLCPCB fits as basic parts)
  maker   manufacturer and the country of its headquarters

Sourcing rules (owner): key chips from non-Chinese makers, stocked at both
LCSC/JLCPCB and DigiKey; the one exception is the AT7456E analog OSD chip.
Voltage use <= 60 % of rating at 6S (25.2 V); the 40 V FETs (63 %) are the
owner-approved exception.

How the numbers in the comments were checked, all on 2026-09-27:
  JLC   JLCPCB's parts API (stock, 'basic' or 'extended').  Basic parts carry
        no per-part setup fee at JLCPCB, so passives are basic where a value
        allows.  Prices are LCSC's product API at 100 / 1000 pieces.
  DK    digikey.com product pages (marked 'DK web'), otherwise DigiKey's own
        feed on findchips.com (marked 'DK fc').  The feed misreports some
        commodity lines as 0 in stock both ways; every part where it said 0
        was re-checked on digikey.com.

Footprints named 'aio:*' live in ../aio.pretty.  The IC, transistor, diode,
LED, crystal, connector and inductor footprints there were converted from
JLCPCB/EasyEDA's own library entries for these exact LCSC parts, so pad
geometry and 0-degree orientation match what the assembly line expects
(footprints.py lists the few pads it renames or resizes).  Plain two-terminal
R/C/ferrite parts use KiCad's standard footprints, whose 0-degree orientation
already matches.  Pad numbers are datasheet pin numbers; an exposed pad is
pin count + 1.
"""

R0402 = 'Resistor_SMD:R_0402_1005Metric'
C0201 = 'Capacitor_SMD:C_0201_0603Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
L0402 = 'Inductor_SMD:L_0402_1005Metric'

UNIROYAL = 'UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China)'
SAMSUNG = 'Samsung Electro-Mechanics (South Korea)'
MURATA = 'Murata (Japan)'
YAGEO = 'Yageo (Taiwan)'
TI = 'Texas Instruments (USA)'
UR_YAGEO = UNIROYAL + '; DigiKey equivalent: Yageo (Taiwan)'

def R(value, lcsc, mpn, dk=None, dk_mpn=None, maker=UNIROYAL):
    e = dict(fp=R0402, lcsc=lcsc, mpn=mpn, value=value,
             desc='Resistor %s 1%% 0402' % value, kind='R')
    if dk:
        e.update(dk=dk, dk_mpn=dk_mpn, maker=maker)
    return e

def R0201(value, lcsc, mpn, dk):
    """Yageo RC0201 1 %: the same part at JLC/LCSC and DigiKey."""
    return dict(fp='Resistor_SMD:R_0201_0603Metric', lcsc=lcsc, mpn=mpn, value=value,
                desc='Resistor %s 1%% 0201' % value, kind='R', dk=dk, dk_mpn=mpn, maker='Yageo (Taiwan)')

def C(value, fp, lcsc, mpn, rating, dk=None, dk_mpn=None, maker=SAMSUNG):
    e = dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value,
             desc='Capacitor %s %s' % (value, rating), kind='C')
    if dk:
        e.update(dk=dk, dk_mpn=dk_mpn, maker=maker)
    return e

PARTS = {
    # =================================================================
    #  ICs
    # =================================================================
    # JLC 1,430 ext, $5.25; DK fc STM32G473CEU6-ND 1,268 (tray).  The same MCU
    # as the GEPRC TAKER G4 AIO.
    'STM32G473': dict(fp='aio:UFQFPN-48_L7.0-W7.0-P0.50-BL-EP5.6', lcsc='C1342773',
                      mpn='STM32G473CEU6', value='STM32G473CEU6',
                      desc='MCU Cortex-M4 170 MHz 512 KB, UFQFPN-48', kind='U',
                      dk='STM32G473CEU6-ND', maker='STMicroelectronics (Switzerland)'),
    # TDK ICM-45686 (DS-000577 rev 1.1, via LCSC C22459454): the fitted
    # gyro.  Same 14-lead 2.5 x 3 mm LGA as the ICM-42688-P (lead width,
    # length, pitch and centres equal; 0.81 mm high, not 0.91), same pin
    # functions and the same axes against pin 1 (fig. 13 = the 42688's fig.
    # 15).  JLC 1,022 ext, $11.84 / 8.12 (1 / 100+) on 2026-09-29; DK
    # 1428-ICM-45686CT-ND 0 (fc), $5.26 / 3.56 (1 / 1000).
    # Rev 2 IMU: TDK IIM-42652, -40..+105 C, the ICM-42688-P's pins and
    # axes (DS-000440).  JLC 4,292 ext, $11.05 (2026-09-30).  Same-pad second
    # source: ICM-42688-P (85 C).
    'IIM42652': dict(fp='aio:LGA-14_L3.0-W2.5-P0.50-TL', lcsc='C2988404',
                     mpn='IIM-42652', value='IIM-42652',
                     desc='6-axis IMU (TDK InvenSense, industrial, -40..105 C), SPI, LGA-14 2.5x3', kind='U',
                     maker='TDK InvenSense (Japan/US)'),
    # Rev 2 flash: Infineon S25FL128LAGNFM010, 128 Mbit, -40..+125 C,
    # AEC-Q100 grade 1 (datasheet 002-00124 rev *L).  WSON 5 x 6 (WND008):
    # the Winbond WSON 6 x 5's pin order (1 CS#, 2 SO, 3 WP#, 4 VSS, 5 SI,
    # 6 SCK, 7 IO3/RESET#, 8 VCC) and 1.27 mm pitch; its 4.0 x 3.4 mm pad
    # fits this land.  JEDEC ID 01 60 18, in Betaflight's m25p16 list.
    # LCSC C5880817 lists it with 0 in stock: JLCPCB global sourcing.
    'S25FL128L': dict(fp='aio:WSON-8_L6.0-W5.0-P1.27-BL-EP', lcsc='C5880817', source='global',
                      mpn='S25FL128LAGNFM010', value='S25FL128LAGNFM010',
                      desc='128 Mbit SPI NOR flash, -40..125 C (AEC-Q100 grade 1), WSON-8 5x6', kind='U',
                      maker='Infineon Technologies (Germany)'),
    # JLC 46,763 ext, $0.14 / 0.10.  DK web: USBLC6-2SC6 (497-5235-1-ND) 0,
    # 3,000 past due; the automotive USBLC6-2SC6Y (497-11882-1-ND, same die,
    # pinout and SOT-23-6) is in stock, 39,426.
    'USBLC6': dict(fp='aio:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C7519',
                   mpn='USBLC6-2SC6', value='USBLC6-2SC6',
                   desc='USB ESD protection, SOT-23-6', kind='U',
                   dk='497-11882-1-ND', dk_mpn='USBLC6-2SC6Y',
                   maker='STMicroelectronics (Switzerland)'),

    # ---------------------------------------------------------------- ESC ICs
    # Rev 2 ESC MCU.  Artery AT32F421G8U7, QFN-28 4x4 (0.4 mm pitch): Cortex-M4
    # 120 MHz, TA -40..105 C, TJ 125 C (datasheet v2.02 tables 11, 8), where
    # the STM32G071GBU6 stops at TJ 105 C.  AM32's f421 port, hardware
    # groups AT_B + AT_045; AM32 reads an NTC thermistor only on Artery
    # parts, so its temperature limit can watch the FETs.  The 5 x 5 mm
    # STM32G431KBU3 (TJ 130 C) was the other candidate; with the 5 x 5 mm
    # DRV8320H beside it there is no room for it on this board.  Pins:
    # 1 BOOT0, 2 PF0, 3 PF1, 4 NRST, 5 VDDA, 6-13 PA0-PA7, 14 PB0, 15 PB1,
    # 16 VSS, 17 VDD, 18-20 PA8-PA10, 21 PA13, 22 PA14, 23 PA15, 24-28
    # PB3-PB7, 29 exposed pad (VSS).  EasyEDA land: 0.20 x 0.85 mm pads,
    # EP 2.4 mm.  JLC 6,230 ext, $0.56 at 100 (2026-10-01).
    'AT32F421G': dict(fp='aio:QFN-28_L4.0-W4.0-P0.40-TL-EP2.4', lcsc='C2765098',
                      mpn='AT32F421G8U7', value='AT32F421G8U7',
                      desc='ESC MCU Cortex-M4 120 MHz 64 KB, -40..105 C (TJ 125 C), QFN-28 4x4', kind='U',
                      maker='Artery Technology (offices in Hsinchu, Taiwan; R&D in mainland China): approved exception'),
    # Rev 2 gate driver.  TI DRV8320HRTVR, WQFN-32 5x5 (RTV): 6-60 V (65 V
    # abs), TJ -40..150 C, smart gate drive with the gate current set by
    # one resistor (IDRIVE, 7 levels, sink = 2 x source), 2 A hold-off of
    # the other FET while one switches, charge-pump high side (no
    # bootstrap), VDS overcurrent with 4 ms retry (TI SLVSDJ3D).  Pins as
    # circuit.esc; 33 = exposed pad.  EasyEDA land 0.28 x 0.80 mm, EP 3.5
    # (TI RTV0032E: EP 3.45).  VM supply current 10.5 mA typ, 14 max at
    # 24 V (0.26-0.35 W from 6S, each).
    # JLC 2,708 ext, $2.05 at 100; TI store 50,791 (2026-09-30).
    'DRV8320H': dict(fp='aio:QFN-32_L5.0-W5.0-P0.50-TL-EP3.5', lcsc='C701782',
                     mpn='DRV8320HRTVR', value='DRV8320H',
                     desc='60 V 3-phase smart gate driver, IDRIVE by pin, WQFN-32 5x5', kind='U', maker=TI),
    # TI INA180A3IDBVR, 100 V/V, SOT-23-5: 1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS.
    # Common mode -0.2 to 26 V (low-side shunt: ~0 V).
    # JLC 89,459 ext, $0.19 / 0.14; DK web 296-47654-1-ND 4,197.
    # ESC current sense: TI INA186A3 (100 V/V, 35 kHz, 40 V common mode,
    # +/-50 uV offset = 0.1 A on a 0.5 mOhm shunt), SC-70-6: half the
    # area of the INA180's SOT-23-5, which the ESC's top side needed.
    # Pins (DCK): 1 REF, 2 GND, 3 VS, 4 IN+, 5 IN-, 6 OUT.  JLC 6,229 ext,
    # $0.66 / 0.58; DK 296-INA186A3IDCKRCT-ND 9,071, $0.57 at 100.
    'INA186A3': dict(fp='aio:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL', lcsc='C2058245',
                     mpn='INA186A3IDCKR', value='INA186A3',
                     desc='Current-sense amp 100 V/V, SC-70-6', kind='U',
                     dk='296-INA186A3IDCKRCT-ND', maker=TI),

    # ---------------------------------------------------------------- FC ICs
    # TI LMR38020FDDAR: 4.2-80 V in (25.2 V = 31 %), 2 A, forced PWM.
    # SO-8 PowerPAD (DDA): 1 GND, 2 EN, 3 VIN, 4 RT/SYNC, 5 FB, 6 PG, 7 BOOT,
    # 8 SW, 9 = PowerPAD.  footprints.py widens EasyEDA's 3.3 x 2.4 mm
    # thermal pad to TI's DDA0008B 3.4 x 2.71 mm; signal pads are EasyEDA's
    # 0.63 x 1.87 mm at +/-2.68 (TI: 0.6 x 1.55 at +/-2.7).
    # JLC 7,706 ext, $0.75 / 0.67; DK web 296-LMR38020FDDARCT-ND only 155.
    'LMR38020F': dict(fp='aio:ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP-1', lcsc='C5149193',
                      mpn='LMR38020FDDAR', value='LMR38020F',
                      desc='Buck 80 V in, 2 A, FPWM, SO-8 PowerPAD', kind='U',
                      dk='296-LMR38020FDDARCT-ND', maker=TI),
    # Rev 2 FC 3.3 V: TI TPS628501DRLR, 2.7-6 V in, 1 A sync buck, -40..150
    # C junction, SOT-583 (DRL): 1 VIN, 2 EN, 3 MODE/SYNC, 4 COMP/FSET, 5 FB,
    # 6 PG, 7 SW, 8 GND (SLUSEC8C table 5-1).  JLC 85 ext (C3193207,
    # 2026-10-01); DK 1,168: PCBWay sources it for volume.
    'TPS628501': dict(fp='aio:SOT-583-8_L2.1-W1.6-P0.50-LS1.6-BL', lcsc='C3193207',
                      mpn='TPS628501DRLR', value='TPS628501',
                      desc='Buck 2.7-6 V in, 1 A, 150 C, SOT-583', kind='U', maker=TI),
    # Rev 2 FC video-supply thermostat: TI TMP390A2DRLR, resistor-set
    # temperature switch, open-drain active-low outputs, SOT-563 (DRL):
    # 1 SETA, 2 SETB, 3 GND, 4 OUTB, 5 VDD, 6 OUTA (SBOS904A 5).  JLC 37,610
    # ext (C5219772, 2026-10-01).
    'TMP390A2': dict(fp='aio:SOT-563_L1.6-W1.2-P0.50-LS1.6-BR', lcsc='C5219772',
                     mpn='TMP390A2DRLR', value='TMP390A2',
                     desc='Temperature switch, resistor-set trip, open drain, SOT-563', kind='U',
                     maker=TI),
    # EXCEPTION to the non-Chinese rule (owner-approved): AT7456E, Hangzhou
    # Zhongke Microelectronics (China), the only MAX7456-compatible OSD chip
    # still made; the MAX7456 is obsolete.  Not sold bare at DigiKey.
    # HTSSOP-28-EP: pins as MAX7456 (3 DVDD, 4 DGND, 5 CLKIN, 6 XFB, 8 CS,
    # 9 SDIN, 10 SCLK, 11 SDOUT, 19 RESET, 20 AGND, 21 AVDD, 22 VIN, 23 PGND,
    # 24 PVDD, 25 SAG, 26 VOUT), 29 = exposed pad (AGND).  Land EP 6.7 x 2.9
    # mm for a 6.2 x 2.75 mm package pad.
    # JLC 40,392 ext (LCSC 35,480), $1.86 / 1.71; DK: none.
    'AT7456E': dict(fp='aio:TSSOP-28_L9.7-W4.4-P0.65-LS6.4-BL-EP-2', lcsc='C82351',
                    mpn='AT7456E', value='AT7456E',
                    desc='Analog video OSD (MAX7456-compatible), HTSSOP-28-EP', kind='U',
                    dk=None, maker='Hangzhou Zhongke Microelectronics (China) - approved exception'),

    # =================================================================
    #  Transistors
    # =================================================================
    # Diodes Inc. BSS138DW-7-F: two N-FETs, 50 V, VGS(th) 0.5-1.5 V,
    # -55..150 C, SOT-363: 1 S2, 2 G2, 3 D1, 4 S1, 5 G1, 6 D2 (DS30203 rev
    # 16-2, top view).  JLC 121,381 ext (C154900, 2026-10-01).
    'BSS138DW': dict(fp='aio:SC-70-6_L2.0-W1.3-P0.65-LS2.1-BL', lcsc='C154900',
                     mpn='BSS138DW-7-F', value='BSS138DW',
                     desc='Dual N-MOSFET 50 V logic level, SOT-363, -55..150 C', kind='Q',
                     maker='Diodes Incorporated (USA)'),
    # VTX-rail switch (PINIO1).  2.5 V-specified gate (48 mOhm).
    # JLC 1,062,531 basic, $0.07 / 0.05; DK fc 785-1000-1-ND 316,253.
    'AO3400A': dict(fp='aio:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', lcsc='C20917',
                    mpn='AO3400A', value='AO3400A',
                    desc='N-MOSFET 30 V logic level, SOT-23', kind='Q',
                    dk='785-1000-1-ND', maker='Alpha & Omega Semiconductor (USA)'),
    # Rev 2 FET.  Infineon ISZ023N06LM6 (OptiMOS 6, logic level): 60 V,
    # 2.3 mOhm max at 10 V (2.03 typ; 2.9 max at 4.5 V, so a 2S pack's
    # ~6.5 V gate drive still switches it fully), Tj 175 C, RthJC 1.5 K/W
    # max, Qg 46 nC to 10 V, Qgd 6 nC, Qrr 23 nC (20 A, 100 A/us), EAS
    # 148 mJ (datasheet rev 2.0, 2024-05-06).  At 6S (25.2 V) it runs at 42 %
    # of its rating, inside the <= 60 % rule the 40 V part broke (63 %).
    # PG-TSDSON-8 FL on Infineon's own land (footprints.tsdson8fl_fp).  Not
    # stocked by LCSC: JLCPCB fits it through its global sourcing, PCBWay
    # through turnkey.  DK 448-ISZ023N06LM6ATMA1CT-ND 2,625 at $1.49/100
    # (2026-09-30).  Second source on the same land: Vishay SiSS22LDN
    # (60 V, 3.65 mOhm, 150 C; LCSC C3279453, DK 69,952), and Infineon
    # BSZ040N06LS5 (60 V, 4.0 mOhm, 150 C; LCSC C3279309, JLC 4,990).
    'ISZ023N06LM6': dict(fp='aio:TSDSON-8FL_L3.3-W3.3-P0.65_IFX', lcsc=None, source='global',
                         mpn='ISZ023N06LM6ATMA1', value='ISZ023N06LM6',
                         desc='N-MOSFET 60 V 2.3 mOhm logic level, PG-TSDSON-8 FL 3.3x3.3', kind='Q',
                         dk='448-ISZ023N06LM6ATMA1CT-ND', maker='Infineon Technologies (Germany)'),

    # =================================================================
    #  Diodes, TVS, LEDs, crystals
    # =================================================================
    # ROHM EDZV 4.7 V (4.55-4.75 V at 5 mA), SOD-523 (EMD2).  Pad 1 = cathode.
    'EDZV4V7': dict(fp='aio:SOD-523_L1.2-W0.8-LS1.6-RD', lcsc='C209619',
                    mpn='EDZVT2R4.7B', value='4.7V', maker='ROHM (Japan)',
                    desc='Zener 4.7 V 150 mW, SOD-523', kind='D'),
    # ROHM RB160VAM-40: 40 V 1 A Schottky, SOD-323HE.  Pad 1 = cathode (the
    # 2.0 x 1.1 mm heat-sink pad), pad 2 = anode; ROHM land b4 1.1, l1 2.0,
    # l2 0.8 matches (EasyEDA anode pad 0.9).  USB VBUS OR-ing at 5 V: 13 %.
    # JLC 29,347 ext, $0.06 / 0.05; DK web RB160VAM-40CT-ND 9,541.
    'RB160VAM40': dict(fp='aio:SOD-323HE_L2.0-W1.4-LS2.5-RD', lcsc='C703624',
                       mpn='RB160VAM-40TR', value='RB160VAM-40',
                       desc='Schottky 40 V 1 A, SOD-323HE', kind='D',
                       dk='RB160VAM-40CT-ND', maker='ROHM (Japan)'),
    # SMF33A: VRWM 33 V, VBR 36.7-40.6 V, VC 53.3 V at 3.8 A.
    # JLC 4,498 ext, $0.23 / 0.17; DK web SMF33A-E3-08CT-ND 42,426.
    'SMF33A': dict(fp='aio:SMF_L2.8-W1.8-LS3.7-RD', lcsc='C1972966',
                   mpn='SMF33A-E3-08', value='SMF33A',
                   desc='TVS 33 V stand-off, 53.3 V clamp, 200 W, SMF (DO-219AB)', kind='D',
                   dk='SMF33A-E3-08CT-ND', maker='Vishay (USA)'),
    # Status LEDs, rev 2: Rohm, rated -40..+100 C (the rev 1 Lite-On
    # LTST-C191KRKT is -55..+85 C, the blue LTST-C191TBKT -20..+80 C).
    # Rohm's 110 C AEC-Q102 CSL0901 parts had no stock (JLC 38 / 1 on
    # 2026-10-01).  Lands and pin numbers are JLC/EasyEDA's for these exact
    # parts, so the two pad orders differ: the red's pad 1 is the cathode,
    # the blue's pad 2 (EasyEDA symbols, C2962748 / C2837822).
    # Red SML-D15UWT86, 620 nm, VF 2.0 V typ at 20 mA: JLC 3,000 ext.
    'LED_RED': dict(fp='aio:LED0603-RD_1', lcsc='C2962748',
                    mpn='SML-D15UWT86', value='RED', desc='LED red 0603, -40..100 C', kind='LED',
                    maker='Rohm (Japan)'),
    # Blue SMLD12BN1WT86, 470 nm, VF 2.9 V typ at 5 mA: JLC 1,070 ext.
    'LED_BLUE': dict(fp='aio:LED0603-R-RD_BLUE', lcsc='C2837822',
                     mpn='SMLD12BN1WT86', value='BLUE', desc='LED blue 0603, -40..100 C', kind='LED',
                     maker='Rohm (Japan)'),
    # 8 MHz HSE crystal, rev 2: NDK NX3225GD-8MHZ-STD-CRA-3, -40..+150 C,
    # AEC-Q200, CL 8 pF, ESR 500 Ohm max, drive 200 uW max, +/-50 ppm at
    # 25 C, +/-150 ppm over temperature (NDK spec).  NDK gives no C0: with
    # 2-5 pF, gm_crit = 4 ESR (2 pi f)^2 (C0 + CL)^2 = 0.51-0.85 mA/V, under
    # the G4's 1.5 mA/V Gmcritmax (STM32G431 datasheet; same oscillator).
    # Two pads, 1.5 x 2.7 mm at 1.9 mm centres (JLC/EasyEDA land).  Load
    # capacitors 10 pF (circuit.py).  The rev 1 ECS-80-10-33-CHN was -40..85
    # C.  JLC 32,455 ext (C889706, 2026-10-01).
    'XTAL8M': dict(fp='aio:OSC-SMD_2P-L3.2-W2.5', lcsc='C889706',
                   mpn='NX3225GD-8MHZ-STD-CRA-3', value='8MHz',
                   desc='Crystal 8 MHz 8 pF 3225, -40..150 C, AEC-Q200', kind='Y',
                   maker='NDK (Japan)'),
    # 27 MHz OSD crystal, rev 2: Abracon ABM8AIG-27.000MHZ-12-2Z-T3, -40..+125
    # C, AEC-Q200, CL 12 pF, ESR 40 Ohm (Abracon datasheet); the same 3225
    # four-pad land as rev 1 (pins 1/3 crystal, 2/4 ground).  The OSD chip
    # has its load capacitors on chip and gives no crystal limits; the
    # MAX7456 EV kit's crystal (HC49US, 18 pF class) asks more of it than
    # this one.  JLC 1 ext (C1985432): JLC global sourcing or PCBWay from
    # DigiKey (8,544 on 2026-10-01).  The rev 1 Hosonic E3SB27E00000DE was
    # -20..70 C.  JLC-stocked alternative on the same land: SCTF
    # SX3B27.000F1010G30 (China), -40..105 C, CL 10 pF (C7302036, 2,951).
    'XTAL27M': dict(fp='aio:CRYSTAL-SMD_4P-L3.2-W2.5-BL', lcsc='C1985432',
                    mpn='ABM8AIG-27.000MHZ-12-2Z-T3', value='27MHz',
                    desc='Crystal 27 MHz 12 pF 3225, -40..125 C, AEC-Q200', kind='Y',
                    maker='Abracon (USA)'),

    # =================================================================
    #  Inductors, ferrite
    # =================================================================
    # Rev 2 FC bucks (both LMR38020F at 455 kHz, on the bottom, facing the
    # ESC across the stack's gap: 3.0 mm tall at most, as rev 1's IHLP):
    # TDK SPM6530T-150M-HZ, 15 uH, 119.9 mOhm max (109 typ), Isat 3.0 A (L down
    # 20 %), Itemp 3.3 A, metal composite, AEC-Q200, -40..+125 C, 7.1 x 6.5 x
    # 3.0 mm.  JLC 2,707 ext (C307809, 2026-10-01).  (Coilcraft's XAL5050, 69.7
    # mOhm, is 5.1 mm tall.)  Isat against the LMR38020: the full-load peak is
    # 2.4 A (2 A + half the 0.85 A ripple at 9 V from 6S), under Isat as TI
    # requires; the high-side current limit (3.2 A typ, 3.8 A max) is above it,
    # which TI allows for soft-saturating cores like this metal composite
    # (SNVSC40E, inductor selection): on an output short the inductance sags, it
    # does not collapse, and hiccup mode follows.
    'L15U_SPM6530': dict(fp='aio:IND-SMD_L7.1-W6.5_SPM6530T', lcsc='C307809',
                         mpn='SPM6530T-150M-HZ', value='15uH',
                         desc='Inductor 15 uH, Isat 3.0 A, 7.1 x 6.5 x 3.0 mm, AEC-Q200, 125 C', kind='L',
                         maker='TDK (Japan)'),
    # Rev 2 FC 3.3 V buck: TDK TFM252012ALMAR47MTAA, 0.47 uH, 19 mOhm, 4.9 A,
    # -55..150 C, 2.5 x 2.0 mm.  JLC 130 ext (C404800, 2026-10-01).
    'L470N_TFM': dict(fp='aio:IND-SMD_L2.5-W2.0_TFM252012ALMA2R2MTAA', lcsc='C404800',
                      mpn='TFM252012ALMAR47MTAA', value='0.47uH',
                      desc='Inductor 0.47 uH 4.9 A, 2.5 x 2.0 mm, -55..150 C', kind='L',
                      maker='TDK (Japan)'),
    # OSD supply bead, Murata BLM15PX601SN1D: 600 Ohm at 100 MHz, 0.9 A,
    # 0.23 Ohm (the OSD draws <= 73 mA: 8 %).  Pads 1, 2.
    # JLC 78,675 ext, $0.021 / 0.017; DK web 490-9657-1-ND 694,669.
    'FB600': dict(fp=L0402, lcsc='C160977', mpn='BLM15PX601SN1D', value='600R@100MHz',
                  desc='Ferrite bead 600 Ohm at 100 MHz, 0.9 A, 0402', kind='FB',
                  dk='490-9657-1-ND', maker=MURATA),
    # ESC channel 3.3 V bead, Murata BLM03AX601SN1D (0201): 600 Ohm +/-25 %
    # at 100 MHz, 250 mA at 85 C, 0.85 Ohm max (0.90 after the life tests),
    # -55..125 C (Murata JENF243A-0020AD-01); a channel draws <= 22 mA.
    # LCSC C88953, 63,350 in stock.
    'FB600_0201': dict(fp='Inductor_SMD:L_0201_0603Metric', lcsc='C88953', mpn='BLM03AX601SN1D',
                       value='600R@100MHz', desc='Ferrite bead 600 Ohm at 100 MHz, 0.25 A, 0201', kind='FB',
                       maker=MURATA),

    # =================================================================
    #  Shunts
    # =================================================================
    # Per-channel ESC shunt, 0.5 mOhm (so MILLIVOLT_PER_AMP = 0.5 x 100 =
    # 50 with the INA180A3).  Stackpole HCS1206FTL500: 0.5 mOhm, 1 %, 2 W
    # at 100 C, +/-200 ppm/K, metal element, AEC-Q200; 0.2 W at 20 A = 10 %.
    # Land (generated in footprints.py, EasyEDA has no entry): Stackpole's
    # 1.70 x 1.80 mm pads, 1.40 mm gap (4.8 x 1.8 mm copper), plus Kelvin
    # sense pads 3 (net-tied to 1) and 4 (net-tied to 2), 0.25 x 0.5 mm, off
    # the inner corners on the +y side; courtyard 5.0 x 2.45 mm (fits the
    # 3.4 x 6.2 mm slot).  Pads 1, 2 current; 3, 4 sense.  The Yageo
    # PU2512FKGP60U5L 2512 (C2084576) is the fallback if the 1206 runs out.
    # JLC 1,951 ext (LCSC 1,822), $0.47 / 0.40; DK web HCS1206FTL500CT-ND 31,022.
    'SHUNT_0M5': dict(fp='aio:RES-SMD_1206_HCS1206', lcsc='C346511',
                      mpn='HCS1206FTL500', value='0.5mR',
                      desc='Current shunt 0.5 mOhm 1% 2 W 1206', kind='R',
                      dk='HCS1206FTL500CT-ND', maker='Stackpole Electronics (USA)'),

    # =================================================================
    #  Connectors, switch
    # =================================================================
    # GCT USB4105-GF-A-120, USB 2.0 Type-C, 16 contacts.  Pads as in
    # circuit.py: A1B12 B1A12 (GND), A4B9 B4A9 (VBUS), A5 B5 (CC), A6 B6
    # (D+), A7 B7 (D-), A8 B8 (SBU), shell 1-4 (plated slots), and two
    # unnumbered non-plated pegs.  footprints.py renames EasyEDA's 'A1-B12'
    # style names.  Matches GCT's recommended PCB layout (pads 1.15 mm long,
    # 0.6/0.3 mm wide; slots 0.6 x 1.7 / 0.6 x 1.4; pegs 0.65 mm).
    # Replaces v1's TYPE-C-31-M-12 (Shenzhen).
    # JLC 4,947 ext (LCSC 3,794), $0.53 / 0.53; DK web 2073-USB4105-GF-A-120CT-ND 50,551.
    'USBC': dict(fp='aio:USB-C-SMD_MC-311D', lcsc='C5184243',
                 mpn='USB4105-GF-A-120', value='USB-C',
                 desc='USB-C receptacle USB 2.0, 16 contacts', kind='J',
                 dk='2073-USB4105-GF-A-120CT-ND', maker='Global Connector Technology (UK)'),
    # JST SH 1.0 mm 8-pin.  Right-angle on the FC, vertical on the ESC.
    # SM08B: JLC 123,874 ext; DK fc 455-1808-1-ND 62,910.
    # Rev 2 stack lead, flight-controller end: Molex Micro-Lock Plus 1.25 mm,
    # 8 positions, right angle, positive lock, -40..+105 C, 1.5 A per
    # contact (505567-0871; mate 505565-0801 + 505431 terminals).  Pads 9/10
    # are the solder tabs.  JLC 13,230 ext (C585387, 2026-10-01).
    'MLP8_RA': dict(fp='aio:CONN-SMD_8P-P1.25_5055670871', lcsc='C585387',
                    mpn='5055670871', value='Micro-Lock Plus 8P RA',
                    desc='Molex Micro-Lock Plus 1.25 mm 8-pin right-angle SMD, locking', kind='J',
                    maker='Molex (USA)'),
    # Omron B3U-1000P (DigiKey now lists the maker as Aratas, Omron's
    # components spin-off of July 2026): 3.0 x 2.5 mm, pads 1, 2; land 0.8 x
    # 1.7 mm at 3.4 mm centres = Omron's.  Replaces v1's XUNPU TS-1088.
    # JLC 153,225 ext, $0.15 / 0.11; DK fc SW1020CT-ND 135,347.
    # Rev 2 boot button: C&K KMR223G LFG, 4.2 x 2.8 x 1.9 mm, 2 N, gold
    # contacts, -40..125 C, 200k cycles, ground pin (pad 5).  Terminals 1-4
    # and 2-3 are joined; the button closes 1/4 to 2/3.  Gold contacts want
    # 1 mA to make reliably.  JLC 6,990 ext (C221678, 2026-10-01).
    'KMR223G': dict(fp='aio:SW-SMD_5P-L4.2-W2.8-P1.60-LS4.6-TR', lcsc='C221678',
                    mpn='KMR223GLFG', value='BOOT',
                    desc='Tact switch 4.2 x 2.8 mm SMD, gold, -40..125 C', kind='SW',
                    maker='C&K (USA)'),

    # =================================================================
    #  Resistors, 0402 1 %.  UNI-ROYAL is what JLCPCB fits as basic parts;
    #  dk_mpn is the Yageo (or Panasonic) equivalent DigiKey stocks.
    #  DK stock from findchips (DK fc) unless marked.
    # =================================================================
    # JLC 1,958,434 basic; DK fc 311-10.0LRCT-ND 3,656,195.
    'R10':   R('10R',  'C25077', '0402WGF100JTCE', '311-10.0LRCT-ND', 'RC0402FR-0710RL', UR_YAGEO),
    # JLC 673,244 ext; DK fc 311-75.0LRCT-ND 51,098.
    'R75':   R('75R',  'C25133', '0402WGF750JTCE', '311-75.0LRCT-ND', 'RC0402FR-0775RL', UR_YAGEO),
    # JLC 4,641,463 basic; DK fc 311-100LRCT-ND 2,985,832.
    'R100':  R('100R', 'C25076', '0402WGF1000TCE', '311-100LRCT-ND', 'RC0402FR-07100RL', UR_YAGEO),
    # JLC 8,606,512 basic; DK fc 311-1.00KLRCT-ND 5,435,324.
    'R1K':   R('1k',   'C11702', '0402WGF1001TCE', '311-1.00KLRCT-ND', 'RC0402FR-071KL', UR_YAGEO),
    # JLC 1,303,529 basic; DK fc 311-330LRCT-ND 3,437,857.
    'R330':  R('330R', 'C25104', '0402WGF3300TCE', '311-330LRCT-ND', 'RC0402FR-07330RL', UR_YAGEO),
    # JLC 8,514,186 basic; DK fc 311-2KLRCT-ND 178,633.
    'R2K':   R('2k',   'C4109',  '0402WGF2001TCE', '311-2KLRCT-ND', 'RC0402FR-072KL', UR_YAGEO),
    # JLC 6,566,797 basic; DK fc 311-5.10KLRCT-ND 1,031,683.
    'R5K1':  R('5.1k', 'C25905', '0402WGF5101TCE', '311-5.10KLRCT-ND', 'RC0402FR-075K1L', UR_YAGEO),
    # JLC 23,609,853 basic; DK fc 311-10.0KLRCT-ND 11,721,670.
    'R10K':  R('10k',  'C25744', '0402WGF1002TCE', '311-10.0KLRCT-ND', 'RC0402FR-0710KL', UR_YAGEO),
    # LM76003 FB bottom, 9.1 V.  JLC 264,652 ext; DK fc 311-12.4KLRCT-ND 24,115.
    'R12K4': R('12.4k', 'C11692', '0402WGF1242TCE', '311-12.4KLRCT-ND', 'RC0402FR-0712K4L', UR_YAGEO),
    # BEMF / neutral dividers.  JLC 3,310,957 basic; DK fc 311-20.0KLRCT-ND 2,372,480.
    'R20K':  R('20k',  'C25765', '0402WGF2002TCE', '311-20.0KLRCT-ND', 'RC0402FR-0720KL', UR_YAGEO),
    # LMR38020 FB bottom (5.02 V) and LM76003 UVLO.  JLC 25,811 ext; DK fc 311-24.9KLRCT-ND 63,651.
    'R24K9': R('24.9k', 'C25874', '0402WGF2492TCE', '311-24.9KLRCT-ND', 'RC0402FR-0724K9L', UR_YAGEO),
    # 6S battery divider top: 23.6 V across it, 47 % of the 50 V rating,
    # 18.6 mW = 30 % of 1/16 W.  JLC 73,275 ext; DK fc 311-30.0KLRCT-ND 1,211,795.
    'R30K':  R('30k',  'C25776', '0402WGF3002TCE', '311-30.0KLRCT-ND', 'RC0402FR-0730KL', UR_YAGEO),
    # JLC 9,762,794 basic; DK fc 311-100KLRCT-ND 6,854,918.
    'R33K_0603': dict(R('33k', 'C126359', 'RC0603FR-0733KL'), fp='Resistor_SMD:R_0603_1608Metric',
                      desc='Resistor 33k 1% 0603, 100 mW 75 V', maker='Yageo (Taiwan)'),
    'R57K6': R('57.6k', 'C26983', '0402WGF5762TCE'),
    'R121K': R('121k', 'C11693', '0402WGF1213TCE'),
    'R22K1': R('22.1k', 'C43473', '0402WGF2212TCE'),
    'R3K3': R('3.3k', 'C25890', '0402WGF3301TCE'),
    'R100K': R('100k', 'C25741', '0402WGF1003TCE', '311-100KLRCT-ND', 'RC0402FR-07100KL', UR_YAGEO),

    # =================================================================
    #  Resistors, 0201 1 %, Yageo RC0201: the ESC's low-voltage resistors
    #  (gates, back-EMF low legs, current filters and average, vsense
    #  bottom, LED).  Half the area of 0402, which the channels need for
    #  their chips' escapes.  Rated 25 V working and 1/20 W: none of them
    #  sees more than 11.4 V (a gate resistor only sees the gate current's
    #  drop) or 14 mW (a gate resistor at 48 kHz).  JLC has no 0201 basic
    #  resistors, so the same Yageo part at JLC and DigiKey.  JLC stock on
    #  27 Sep 2026; DigiKey numbers from DigiKey's RC0201 kit list
    #  (RC0201-R-SKE24L).
    # =================================================================
    # JLC 80,353 ext (3,300 ESCs at 24 each).
    # JLC 2,415,899 ext.
    'R1K_0201':  R0201('1k', 'C138165', 'RC0201FR-071KL', '311-1KMCT-ND'),
    # JLC 17,212 ext (1,400 ESCs at 12 each).
    'R2K_0201':  R0201('2k', 'C327392', 'RC0201FR-072KL', 'YAG2280CT-ND'),
    # JLC 2,582,336 ext.
    'R10K_0201': R0201('10k', 'C106225', 'RC0201FR-0710KL', '311-10.0KMCT-ND'),
    # FET thermistor: Murata NCU15XH103F60RC, 10k 1 % at 25 C, B25/50
    # 3380 K, 0402, AEC-Q200, -40..125 C.  JLC 28,768 ext (2026-10-01).
    'NTC10K': dict(fp='Resistor_SMD:R_0402_1005Metric', lcsc='C237326', mpn='NCU15XH103F60RC',
                   value='NTC 10k B3380', desc='NTC thermistor 10k 1% B3380 0402', kind='R', maker=MURATA),
    # DRV8320H IDRIVE setting (75k 5 %: the pin's level).  JLC 35,170 ext.
    'R75K_0201': dict(fp='Resistor_SMD:R_0201_0603Metric', lcsc='C295816', mpn='RC0201FR-0775KL',
                      value='75k', desc='Resistor 75k 1% 0201', kind='R', maker='Yageo (Taiwan)'),
    # DRV8320H IDRIVE setting 30/60 mA (18k 5 % to AGND).  JLC 23,318 ext
    # (2026-10-02).
    'R18K_0201': dict(fp='Resistor_SMD:R_0201_0603Metric', lcsc='C295780', mpn='RC0201FR-0718KL',
                      value='18k', desc='Resistor 18k 1% 0201', kind='R', maker='Yageo (Taiwan)'),
    # =================================================================
    #  Capacitors.  Effective capacitance under DC bias from Murata's
    #  SimSurfing data (25 C) for the Murata part or its Murata equivalent.
    # =================================================================
    # JLC 187,303 ext (Samsung; the basic 12 pF is Fenghua, China), $0.009 / 0.007;
    # JLC 14,231,847 basic; DK web 1276-CL05B104KB54PNCCT-ND 48,207.
    'C100N':  C('100nF', C0402, 'C307331', 'CL05B104KB54PNC',  '50V X7R 0402', '1276-CL05B104KB54PNCCT-ND'),
    # Murata GRM188R72A104KA35D 100 nF 100 V X7R 0603 (25.2 V = 25 %; 81 nF
    # left at 25 V).  JLC 71,749 ext, $0.038 / 0.036; DK web 490-3285-1-ND 735,979.
    'C100N_100': C('100nF', C0603, 'C77058', 'GRM188R72A104KA35D', '100V X7R 0603',
                   '490-3285-1-ND', maker=MURATA),
    # Bridge decoupling, one per half-bridge (12 per ESC), 0805 as the
    # floorplan requires.  4.7 uF 50 V X7R 0805 is the largest 50 V X7R 0805
    # stocked (no 10 uF 50 V X7R 0805 exists at JLC); of those stocked at
    # both, Murata's is the only one with published bias data.  Effective
    # capacitance (Murata SimSurfing): 4.98 uF at 0 V, 2.26 uF at 11.4 V,
    # 1.55 uF at 16.8 V, 1.17 uF at 22.2 V, 1.02 uF at 25.2 V.  (A 4.7 uF
    # 50 V 1206 keeps 2.53 uF and a 10 uF 50 V 1210 6.1 uF at 25.2 V.)
    # JLC 111,968 ext, $0.14 / 0.13; DK web 490-GRM21BZ71H475KE15LCT-ND 127,160.
    'C_BRIDGE': C('4.7uF', C0805, 'C437557', 'GRM21BZ71H475KE15L', '50V X7R 0805',
                  '490-GRM21BZ71H475KE15LCT-ND', maker=MURATA),
    # 10 uF 50 V X7R 1210, Taiyo Yuden (25.2 V = 50 %).  A Murata 1210 10 uF
    # 50 V X7R keeps 9.1 uF at 11.4 V and 6.1 uF at 25.2 V.
    # JLC 6,801 ext, $0.31 / 0.28; DK web 587-3167-1-ND 180,319.
    'C10U50_1210': C('10uF', C1210, 'C386167', 'UMK325AB7106KM-T', '50V X7R 1210',
                     '587-3167-1-ND', maker='Taiyo Yuden (Japan)'),
    # ---- every capacitor X7R / X7S (125 C) or better: boards that pass
    # 85 C have no X5R.
    # ESC bus capacitance: Murata GCJ32EC71H106KA01L, 10 uF 50 V X7S 1210,
    # automotive, soft (resin) terminations.  At 25.2 V: about 5 uF
    # (ASSUMPTION: Murata's data for the same-size GRM32ER71H106K gives
    # 6.1 uF; X7S taken lower).  JLC 260 ext, $0.53 (2026-09-30); Murata
    # makes it in volume (DigiKey not checked).
    # Rev 2 FC: X7R in place of every X5R (X5R is rated to 85 C)
    'C22U25_X7R': C('22uF', C1210, 'C21397', 'GRM32ER71E226KE15L', '25V X7R 1210', maker=MURATA),
    'C10U25_X7R': C('10uF', C0805, 'C237493', 'GRM21BZ71E106KE15L', '25V X7R 0805', maker=MURATA),
    'C4U7_X7R': C('4.7uF', C0603, 'C913474', 'GRM188Z71A475KE15D', '10V X7R 0603', maker=MURATA),
    'C10P': C('10pF', C0402, 'C76946', 'GRM1555C1H100JA01D', '50V C0G 0402', maker=MURATA),
    'C10U50_SOFT': C('10uF', C1210, 'C437431', 'GCJ32EC71H106KA01L', '50V X7S 1210 soft termination',
                     maker=MURATA),
    # 1 uF 25 V X7R 0603, Murata automotive (driver charge pump across
    # VBAT and VCP at ~11 V, DVDD, MCU VDDA, buck VCC).  JLC 107,530 ext.
    'C1U_25_X7R': C('1uF', C0603, 'C85862', 'GCM188R71E105KA64D', '25V X7R 0603', maker=MURATA),
    # 1 uF 10 V X7R 0402, Murata (each ESC MCU's VDDA: Artery's 100 nF +
    # 1 uF, AT32F421 figure 8, in one 0402; each driver's DVDD).  JLC
    # 233,801 ext, $0.021.
    'C1U_10_X7R': C('1uF', C0402, 'C528974', 'GRM155Z71A105KE01D', '10V X7R 0402', maker=MURATA),
    # 47 nF 50 V X7R 0402, TDK automotive: the DRV8320's charge-pump
    # flying capacitor (TI: 47 nF, VM-rated).  JLC 61,977 ext.
    'C47N_50': C('47nF', C0402, 'C343051', 'CGA2B3X7R1H473KT0Y0F', '50V X7R 0402', maker='TDK (Japan)'),
}

# Maximum seated height (mm, seating plane to the top of the body, the
# standoff included) of every part on the ESC's bottom, from each maker's
# own package drawing: the heatsink (heatsink.py) pockets them to this.
HEIGHTS = {
    'ISZ023N06LM6': 1.10,   # Infineon datasheet rev 2.0, PG-TSDSON-8-U03 outline, A 0.90-1.10
    'C_BRIDGE':     1.45,   # Murata GRM21BZ71H475KE15-01A spec, T 1.25 +/- 0.2
    'C10U50_SOFT':  2.80,   # Murata GCJ32EC71H106KA01-02B spec, T 2.5 +/- 0.3
    'C100N':        0.55,   # Samsung CL05B104KB54PN data sheet, T 0.50 +/- 0.05
    'DRV8320H':     0.80,   # TI SLVSDJ3D, RTV0032E outline, 0.8 max
    'AT32F421G':    0.80,   # Artery AT32F421 datasheet v2.02 table 50, A 0.70-0.80
    'EDZV4V7':      0.70,   # ROHM EDZV4.7B datasheet rev 004, EMD2 outline, 0.50-0.70
    'SHUNT_0M5':    1.05,   # Stackpole HCS series datasheet, 1206 L500, T 0.90 +/- 0.15
}
for _k, _h in HEIGHTS.items():
    PARTS[_k]['h'] = _h

# Things that are copper only: solder pads, test points, mounting holes.
# They carry no LCSC number and are left out of the BOM and pick-and-place.
PADS = {
    'PAD_BAT':   dict(fp='aio:PAD_BAT',   kind='PAD'),
    'PAD_BAT_K': dict(fp='aio:PAD_BAT_K', kind='PAD'),
    'PAD_MOTOR': dict(fp='aio:PAD_MOTOR', kind='PAD'),
    'PAD_SIG':   dict(fp='aio:PAD_SIG',   kind='PAD'),
    'PAD_TP':    dict(fp='aio:PAD_TP',    kind='PAD'),
    'PAD_LEAD':  dict(fp='aio:PAD_LEAD',  kind='PAD'),
    'HOLE':      dict(fp='aio:MOUNT_M2_SLOT', kind='H'),
}
