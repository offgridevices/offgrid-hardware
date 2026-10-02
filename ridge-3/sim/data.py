# -*- coding: utf-8 -*-
"""Datasheet figures the stress simulations use, each with its source.

Values are the makers' own (document, table or figure; "Fig." means read
from that graph).  Where the physics needs a number no maker publishes (a
battery's internal resistance, a lead's inductance, the air speed over a
flying stack), it is marked ASSUMPTION, and the report says what it changes.
"""

# ------------------------------------------------------------------ ESC FETs
TPN2R304PL = FET = dict(
    part='Toshiba TPN2R304PL', spice='TPN2R304PL', src='TPN2R304PL datasheet Rev.4.0.A (2026-04-14)',
    vdss=40.0,                          # V (sec. 4); V(BR)DSS min 40 V (6.1)
    tch_max=175.0,                      # C (sec. 4)
    rth_ch_c=1.43,                      # K/W max (sec. 5)
    # rth(ch-c) single pulse, K/W vs pulse width s (Fig. 8.14, guaranteed max)
    zth=((1e-5, 0.056), (1e-4, 0.178), (1e-3, 0.554), (1e-2, 1.28), (1e-1, 1.43)),
    rds25_typ=1.8e-3, rds25_max=2.3e-3,       # VGS 10 V, 40 A (6.1)
    rds_ratio=((25, 1.0), (75, 1.26), (100, 1.40), (125, 1.56), (150, 1.73), (175, 1.89)),  # Fig. 8.9
    vth_min=1.4, vth_max=2.4,           # VDS 10 V, 0.3 mA (6.1)
    vth_typ_T=((25, 1.90), (75, 1.67), (100, 1.54), (125, 1.40), (150, 1.22)),   # Fig. 8.8, typical
    ciss=2750e-12, crss=66e-12, coss=650e-12,      # typ, 20 V, 1 MHz (6.2)
    qg=41e-9, qgd=6.2e-9, qoss=27e-9,              # typ (6.3)
    qrr=30e-9, trr=35e-9,               # IF 20 A, 100 A/us, VR 20 V (6.4)
    vsd_hot=0.75,                       # V: Fig. 8.6 gives 0.77-0.83 V at 10-43 A, 25 C; lower hot
    eas=39e-3, ias=80.0,                # single pulse from 25 C (4, note 5)
    c_th=0.0125,                        # J/K, ASSUMPTION: 3.3 x 3.3 x 0.9 mm package, ~25 mg
    # the datasheet's test conditions (6.1-6.4)
    tests=dict(id_r=40.0, vds_c=20.0, vdd_g=20.0, id_g=40.0, vr=20.0),
    model='Toshiba publishes a SPICE model of the TPN2R304PL (the "G0" grade, a BSIM3 model fitted '
          'to the on-state curves)',
)
# Toshiba's G0 model's body diode replaced by a charge-control diode fitted to
# the datasheet recovery test (spice.fit): lifetime, transit time (s)
TPN2R304PL['body_diode'] = (10e-9, 5e-9)
TPN2R304PL['vth_hot_drop'] = 1.90 - 1.22        # the typical curve's drop from 25 to 150 C

# Rev 2: Infineon ISZ023N06LM6 (OptiMOS 6), datasheet rev 2.0 (2024-05-06)
ISZ023N06LM6 = dict(
    part='Infineon ISZ023N06LM6', src='ISZ023N06LM6 datasheet rev. 2.0 (2024-05-06)', spice='ISZ023N06LM6',
    vdss=60.0,                          # V(BR)DSS min 60 V (table 4)
    tch_max=175.0,                      # Tj max (table 2)
    rth_ch_c=1.5,                       # RthJC max (table 3; typ 0.75)
    # ZthJC single pulse, K/W vs pulse width s (diagram 4, max)
    zth=((1e-5, 0.05), (1e-4, 0.20), (1e-3, 0.85), (1e-2, 1.40), (1e-1, 1.50)),
    rds25_typ=2.03e-3, rds25_max=2.3e-3,       # VGS 10 V, 20 A (table 4)
    rds_ratio=((25, 1.0), (50, 1.10), (75, 1.23), (100, 1.39), (125, 1.57), (150, 1.76), (175, 1.96)),  # diagram 9
    vth_min=1.1, vth_max=2.3,           # VDS = VGS, 38 uA (table 4)
    vth_typ_T=((25, 1.72), (75, 1.50), (100, 1.36), (125, 1.20), (150, 1.00), (175, 0.78)),   # diagram 10, 38 uA
    ciss=3200e-12, crss=21e-12, coss=870e-12,      # typ, 30 V, 1 MHz (table 5)
    qg=46e-9, qgd=6.0e-9, qoss=50e-9,              # typ, 0-10 V, 30 V (table 6)
    qrr=23e-9, trr=29e-9,               # IF 20 A, 100 A/us, VR 30 V (table 7)
    vsd_hot=0.70,                       # V: diagram 12, 20 A: 0.85 V at 25 C, 0.62 V at 175 C
    eas=148e-3, ias=20.0,               # single pulse, ID 20 A (table 2)
    c_th=0.0125,                        # J/K, ASSUMPTION: 3.3 x 3.3 x 1.0 mm package, ~25 mg
    body_diode=None,                    # Infineon's model's own diode (fitted to the part by Infineon)
    # the datasheet's test conditions (tables 4-7)
    tests=dict(id_r=20.0, vds_c=30.0, vdd_g=30.0, id_g=20.0, vr=30.0),
    model='Infineon publishes a SPICE model of the ISZ023N06LM6 (its OptiMOS 6 library, body diode '
          'included)',
)
ISZ023N06LM6['vth_hot_drop'] = 1.72 - 1.00
for _f in (TPN2R304PL, ISZ023N06LM6):
    _f['qg_11v'] = _f['qg'] * 11.33 / 10        # gate charge to the 11.3 V drive (above the plateau Qg ~ linear in V)
    _f['vth_min_hot'] = _f['vth_min'] - _f['vth_hot_drop']
BODY_DIODE = FET['body_diode']

# ------------------------------------------------------------------ ESC gate drive
DRV8300 = dict(
    part='TI DRV8300D (RGE)', src='TI SLVSFG5D, March 2022',
    i_source=(0.4, 0.75, 1.2), i_sink=(0.85, 1.5, 2.1),   # A peak, min/typ/max (7.5)
    r_pu=6.0, r_pd=1.5,                 # ohm: VGH_HI 0.6 V and VGH_LO 0.15 V typ at 100 mA (7.5)
    dead=(150e-9, 215e-9, 280e-9),      # DT open (7.5)
    slew_max=2.0,                       # V/ns on SHx, D variant (7.3)
    sh_min=-22.0, sh_note='-22 V for 2 us (DRV8300)',   # (7.3)
    tj_max=150.0, rth_jb=26.5,          # (7.3, 7.4); no thermal shutdown
    i_q=0.825e-3,                       # A, IGVDD switching at 20 kHz, typ (7.5)
)
GVDD = 11.33                            # V: TPS7A1601 at 1.169 V x (1 + 88.7k/10.2k)
TPS7A16 = dict(part='TI TPS7A1601 (DRB)', rth_jb=11.3, tj_max=125.0)          # SBVS171F 6.4, 6.3
MAX15062 = dict(part='ADI MAX15062A', rth_jb=40.0,                            # thetaJC 20 K/W + pads: ASSUMPTION
                eff=0.737, tj_max=125.0)       # PWM mode (MODE = GND), 24 V in, 50 mA (TOC03)
G071 = dict(part='ST STM32G071GBU6', tj_max=105.0, ta_max=85.0,               # DS12232 table 21 (suffix 6)
            rth_jb=44.0,                        # thetaJA 44 K/W (table 84), used as junction-to-board
            p_run=3.3 * 11e-3)                  # ~11 mA at 64 MHz with peripherals (tables 25, 33)
INA186 = dict(part='TI INA186A3', ta_max=125.0, p=3.3 * 65e-6, vin_abs=(-0.3, 42.0))   # SBOS...: 6.1, 6.3, 6.5
SHUNT = dict(part='Stackpole HCS1206FTL500', r=0.5e-3,
             p_rated=2.0, t_full=100.0, t_zero=170.0)   # 2 W to a 100 C terminal, 0 W at 170 C (p.3)
AM32 = dict(dead=625e-9,                # DEAD_TIME 40 at 64 MHz (firmware/README.md)
            f_min=24e3, f_max=48e3,     # variable PWM, 24 kHz low rpm to 48 kHz high (esc_power.md)
            current_limit=20.0,         # A per motor, battery side, 50 ms average (firmware/README.md)
            temp_limit=110.0)           # C, each MCU's own die sensor (firmware/README.md)
ESC_3V3_LOAD_REV1 = 4 * 11e-3 + 4 * 65e-6 + 1.3e-3   # A: four MCUs, four INA186, the power LED

# ------------------------------------------------------------------ capacitors
C_BRIDGE = dict(part='GRM21BZ71H475KE15L', c=4.7e-6, c_bias=1.03e-6,  # Murata SimSurfing: 1.03 uF at 25 V
                esr=4.2e-3, esl=0.4e-9)          # ESR at 1 MHz, 25 V (SimSurfing); ESL: ASSUMPTION for 0805
EXT_CAP = dict(desc='2 x Panasonic EEU-FR1H101 100 uF 50 V', c=200e-6,
               esr=0.058 / 2, esl=8e-9 / 2,     # each: |Z| 0.061 ohm at 100 kHz (FR-A table); ESL: ASSUMPTION 8 nH with leads
               ripple=2 * 0.87)                  # A rms at 100 kHz, 105 C, two cans (FR-A table)
# MLCC dielectrics on the boards and their temperature limits (makers' pages)
CAPS = {
    'C1U_16_0201': ('X5R', 85.0, 'Samsung CL03A105MO3NRNC, bootstrap'),
    'C1U_25': ('X5R', 85.0, 'Samsung CL05A105KA5NQNC'),
    'C1U': ('X5R', 85.0, 'Samsung CL05A105KA5NQNC'),
    'C10U_25': ('X5R', 85.0, 'Samsung CL21A106KAYNNNE'),
    'C22U25': ('X5R', 85.0, 'Murata GRM21BR61E226ME44L'),
    'C4U7': ('X5R', 85.0, 'Samsung CL05A475MP5NRNC'),
    'C2U2': ('X5R', 85.0, 'Samsung CL10A225KO8NNNC'),
    'C_BRIDGE': ('X7R', 125.0, 'Murata GRM21BZ71H475KE15L'),
    'C10U50_1210': ('X7R', 125.0, 'Taiyo Yuden UMK325AB7106KM-T'),
}
CAPS_REV2 = {
    'C100N': ('X7R', 125.0, 'Samsung CL05B104KB54PNC'),
    'C1U_100': ('X7R', 125.0, 'Yageo CC0805KKX7R0BB105'),
    'C1U_25_X7R': ('X7R', 125.0, 'Murata GCM188R71E105KA64D'),
    'C1U_10_X7R': ('X7R', 125.0, 'Murata GRM155Z71A105KE01D'),
    'C10U_16_X7R': ('X7R', 125.0, 'Samsung CL21B106KOQNNNE'),
    'C47N_50': ('X7R', 125.0, 'TDK CGA2B3X7R1H473KT0Y0F'),
    'C_BRIDGE': ('X7R', 125.0, 'Murata GRM21BZ71H475KE15L'),
    'C10U50_SOFT': ('X7S', 125.0, 'Murata GCJ32EC71H106KA01L'),
    'C10U50_1210': ('X7R', 125.0, 'Taiyo Yuden UMK325AB7106KM-T'),
}

# ------------------------------------------------------------------ FC
LMR38020F = dict(part='TI LMR38020F', rth_jb=13.6, tj_max=150.0, tsd=163.0,   # SNVSC40E 7.4, 7.3, 7.5
                 # efficiency, 5 V out, 24 V in, FPWM, vs A.  The datasheet has only 400 kHz
                 # curves; this board runs it at 1 MHz, which loses more (see report).
                 eff=((0.5, 0.896), (1.0, 0.907), (1.5, 0.898), (2.0, 0.885)), vout=5.0, f_note='400 kHz curve')
LM76003 = dict(part='TI LM76003', rth_jb=9.1, tj_max=125.0, tsd=160.0,       # SNVSAK0A 6.4, 10.3, 6.5
               # no 9 V curve: its loss in watts at 5 V out, 1 MHz, 24 V in (Fig. 28) is used,
               # since at a given input, current and frequency a buck's loss hardly depends on Vout
               eff=((0.5, 0.794), (1.0, 0.861), (1.5, 0.882), (2.0, 0.889), (2.5, 0.889)), vout=5.0,
               f_note='5 V, 1 MHz curve, loss in watts')
TLV76733 = dict(part='TI TLV76733 (DRV)', rth_jb=40.8, tj_max=125.0)         # 6.4, 6.3
G473 = dict(part='ST STM32G473CEU6', tj_max=105.0, ta_max=85.0,              # DS12712 table 17 (suffix 6)
            rth_jb=11.0, p_run=3.3 * 92e-3)     # thetaJB (table 118); 29.5 mA + all peripherals (tables 21, 35)
AT7456E = dict(part='AT7456E', t_max=85.0, rth_jb=20.0,     # -40..85 C (AT7456E-S402-V1.1); rth: ASSUMPTION
               p=3.3 * 51e-3)                   # 51 mA typ at 5 V (the only figure given), at 3.3 V: ASSUMPTION
ICM45686 = dict(part='TDK ICM-45686', t_max=85.0, p=3.3 * 0.44e-3)   # DS-000577 table 3 / abs max
W25Q128 = dict(part='Winbond W25Q128JVPIM', t_max=85.0)             # 9.2 (I grade)
FC_3V3_OWN = 92e-3 + 0.5e-3 + 20e-3 + 51e-3 + 2e-3    # A: MCU, gyro, flash writing, OSD, LEDs
FC_3V3_LOAD = FC_3V3_OWN                              # the design's (DESIGNS)
INDUCTORS = {'L_5V': dict(part='TDK SPM5020T-4R7M-LR', dcr=67.7e-3, t_max=125.0),     # TDK catalog
             'L_9V': dict(part='Vishay IHLP2525CZER6R8M01', dcr=60e-3, t_max=125.0),  # Vishay
             'L1': dict(part='Taiyo Yuden NRS4018T330MDGJV', dcr=0.552, t_max=125.0)}
JST_SH = dict(part='JST SH (SM08B/BM08B/BM06B-SRSS-TB)', i_rated=1.0,   # per contact, AWG 28 (eSH p.1)
              r_contact=20e-3, r_contact_aged=40e-3,                    # initial / after environmental tests
              t_max=85.0)                                               # -25..85 C, INCLUDING self-heating
SMF33A = dict(vbr=(36.7, 40.6), vc=53.3, ipp=3.8, c=198e-12)            # Vishay 88588 rev 2.4

# ------------------------------------------------------------------ the stack and its world
STACK = dict(gap=5.0)                   # mm between the ESC's top and the FC's bottom: ASSUMPTION (grommets + nuts)
BATTERY = dict(
    vfull=25.2,
    # 6S 1000-1300 mAh: no maker publishes internal resistance.  ASSUMPTION: a new,
    # warm, high-C pack ~3 mOhm/cell plus 5 mOhm of connector and leads = 25 mOhm;
    # a tired or cold pack 60-100 mOhm.
    r=0.025, r_tired=(0.06, 0.10),
    # leads: 12 AWG pair ~5.2-5.9 nH/cm (two-wire formula, 4 mm spacing); ~15 cm of
    # pack lead and ESC pigtail plus the connector: ASSUMPTION 120 nH, swept 100-300.
    l_lead=120e-9)
STACK_LEAD = dict(length=0.07, r_wire=0.213,     # m; AWG 28 ohm/m (copper)
                  l=50e-9)                       # H, VBAT wire with its GND neighbour at 1 mm pitch, 7 cm: ASSUMPTION
MOTOR = dict(
    part='BrotherHobby VY1507 3100KV on 6S, HQ 3x4x3 (maker test report 1507VY2019122301; typical)',
    r=0.1368,                            # ohm, "internal resistance"
    # load test at 24 V: throttle %, battery current A, thrust g (rpm 19539 at 30 %, 48120 at 100 %)
    load=((30, 2.6, 126), (40, 4.0, 188), (50, 6.2, 279), (60, 10.2, 413), (70, 13.5, 489),
          (80, 17.5, 628), (90, 23.0, 747), (100, 27.4, 879)),
    vtest=24.0,
    auw=450.0)                           # g, a 3-inch 6S quad with an HD VTX and a 1300 mAh pack: ASSUMPTION
REGEN = dict(i_bus=-100.0)              # A, all four motors chopped to the worst duty at full rpm (report derives it)

# air: convection coefficients over the boards, W/m2 K (thermal.air())
AIR = dict(eps=0.9,                     # black solder mask: ASSUMPTION (typical 0.85-0.95)
           h_still=9.0,                 # natural convection: 0.54 / 0.27 Ra^0.25 on the up / down faces
           enhance=1.5)                 # parts standing on the board over a flat plate: ASSUMPTION

# ------------------------------------------------------------------ the half-bridge bench (spice.half_bridge)
BRIDGE = dict(
    V=BATTERY['vfull'], Rg=10.0, gvdd=GVDD, vboot=GVDD - 0.8,   # bootstrap diode ~0.7-0.85 V at low current (7.5)
    rpu=DRV8300['r_pu'], rpd=DRV8300['r_pd'], ipu=DRV8300['i_source'][1], ipd=DRV8300['i_sink'][1],
    dead=AM32['dead'] + DRV8300['dead'][1],
    Cb=C_BRIDGE['c_bias'], ESRb=C_BRIDGE['esr'], ESLb=C_BRIDGE['esl'],
    Cb2=2 * C_BRIDGE['c_bias'], ESRb2=C_BRIDGE['esr'] / 2, ESLb2=2e-9,     # the channel's other two, ~5 mm away
    Cext=EXT_CAP['c'], ESRext=EXT_CAP['esr'], ESLext=EXT_CAP['esl'],
    Llead=BATTERY['l_lead'], Rbat=BATTERY['r'], Lplane=2e-9, Rplane=1.0e-3, Lg=3e-9)
BUS = dict(
    Vpack=BATTERY['vfull'], Rbat=BATTERY['r'], Llead=BATTERY['l_lead'], Rcontact=1e-3, Rplane=1.0e-3,
    Cbridge=12 * C_BRIDGE['c_bias'], ESRbridge=C_BRIDGE['esr'] / 12, ESLbridge=C_BRIDGE['esl'] / 12,
    Cmisc=2 * 0.5e-6,                   # the two 1 uF 100 V X7R 0805 (buck and LDO inputs) at 25 V: ASSUMPTION half
    Rstack=2 * STACK_LEAD['length'] * STACK_LEAD['r_wire'] + 4 * JST_SH['r_contact'],
    Lstack=STACK_LEAD['l'],
    Cfc=3 * 2.5e-6 + 2 * 0.1e-6, ESRfc=5e-3,     # 3 x UMK325AB7106KM at 25 V (~2.5 uF each) + 2 x 100 nF
    tvs_bv=38.6, tvs_rs=(SMF33A['vc'] - SMF33A['vbr'][1]) / SMF33A['ipp'], tvs_c=SMF33A['c'],
    Ifc=0.0, step=1e-9, maxstep=2e-9, tend=20e-6)
FC_LOAD_MAX = dict(i5=2.0, i9=2.0)      # both rails at their rating (circuit.py)


# ------------------------------------------------------------------ rev 2 parts
IIM42652 = dict(part='TDK IIM-42652', t_max=105.0, p=3.3 * 0.9e-3)      # DS -40..105 C; ~0.9 mA 6-axis LN: ASSUMPTION
S25FL128L = dict(part='Infineon S25FL128LAGNFM010', t_max=125.0)       # -40..125 C, AEC-Q100 grade 1
G071_6 = G071
# ESC gate driver: TI DRV8320H (RTV), TI SLVSDJ3D (March 2022)
DRV8320 = dict(
    part='TI DRV8320H (RTV)', src='TI SLVSDJ3D, March 2022',
    idrive=(0.01, 0.03, 0.06, 0.12, 0.26, 0.57, 1.0),  # A source, by the IDRIVE pin (7.5); sink = 2 x
    sink_ratio=2.0,
    r_pu=6.0, r_pd=1.5,                 # ohm near the rails: ASSUMPTION (as the DRV8300's, 7.5)
    vgs=11.0,                           # V: VGSH / VGSL typ at VM >= 12-13 V (7.5)
    dead_add=100e-9,                    # s after the other gate is seen low (8.3.1.3)
    i_vm=(10.5e-3, 14e-3),              # A typ / max, VM = 24 V, not switching (7.5)
    i_dvdd_max=30e-3,                   # A external load on DVDD (7.3): the channel's MCU, amplifier, NTC
    tj_max=150.0, ta_max=125.0, rth_jb=6.8, rth_ja=32.9,   # (7.3, 7.4)
    i_strong=2.0,                       # A hold-off of the other gate for 4 us (8.3.1.3)
    vds_ocp=0.6,                        # V: VDS pin open (7.5)
    slew_max=None,                      # no SHx slew limit given
    sh_min=-7.0, sh_note='-7 V for 200 ns (DRV8320H; -5 V continuous)',   # (7.1)
)
AT32F421 = dict(part='Artery AT32F421G8U7', tj_max=125.0, ta_max=105.0,      # datasheet v2.02 tables 11, 8
                rth_jb=44.8,                    # thetaJA QFN28 4x4 (table 63), used as junction-to-board
                i_run=20.7e-3,                  # A max at 120 MHz, all peripherals, 105 C (table 19)
                p_run=3.3 * 20e-3)              # ~20 mA at 120 MHz, hot (table 18): ASSUMPTION within it
# Each rev 2 channel's 3.3 V: the MCU, the INA186 (48 uA) and the
# thermistor's divider (~0.3 mA hot), from the flight controller's 3.3 V
# buck down the stack lead's pin 4 and through the channel's ferrite bead.
# The drivers' DVDD regulators feed only their own logic (inside their VM
# current), so they carry no external load (DVDD_LOAD); the first rev 2
# layout ran each channel from its DVDD, which the ground run showed at
# 0.46 W a driver.
CHANNEL_3V3 = AT32F421['i_run'] + 0.1e-3 + 0.3e-3
TVS_5SMDJ33A = dict(part='Littelfuse 5.0SMDJ33A', vbr=(36.7, 40.6), vc=53.3, ipp=93.9,
                    p_pk=5000.0, tj_max=150.0,  # 10/1000 us; derated to ~62 % at 120 C (Littelfuse curve)
                    c=3.0e-9)                   # ASSUMPTION: junction capacitance at 0 V, 5 kW SMC class
# On-board bus capacitance: 10 uF 50 V X7S 1210 (Murata GCJ32EC71H106KA01L),
# as many as the middle of the board holds (circuit.BULK_N)
BULK_N = 3
CERAMIC_BULK = dict(desc='%d x Murata GCJ32EC71H106KA01L 10 uF 50 V X7S 1210 on the board' % BULK_N,
                    c=BULK_N * 5.0e-6,          # ASSUMPTION 5 uF each at 25 V (Murata GRM32ER71H106K: 6.1)
                    esr=3e-3 / BULK_N,          # ASSUMPTION 3 mOhm each at 100 kHz
                    esl=0.6e-9 / BULK_N + 0.3e-9,   # ASSUMPTION 0.6 nH each + the planes to them
                    ripple=None, on_board=True, kind='ceramic')
C_BRIDGE_REV2 = C_BRIDGE                # same part: Murata X7R (125 C), 0805

# Rev 2 FC.  Both BECs are LMR38020F at 455 kHz (RT 57.6k), next to the
# datasheet's 400 kHz curves.  The 9 V one: the 5 V curve's loss in watts
# (buck_loss: at a given input, current and frequency a buck's loss hardly
# depends on its output voltage).
LMR38020F_455 = dict(LMR38020F, f_note='400 kHz curve; the board runs 455 kHz')
LMR38020F_9V = dict(LMR38020F_455, part='TI LMR38020F (9 V)',
                    f_note='5 V, 400 kHz curve, loss in watts; the board runs 9 V at 455 kHz')
# 3.3 V from 5 V: TI TPS628501 (DRL), SLUSEC8C: RthJB 20 K/W (6.4), TJ 150 C
# (6.3); efficiency, 5 V in, 3.3 V out, forced PWM at 2.25 MHz (MODE high),
# read from Fig. 9-3
TPS628501 = dict(part='TI TPS628501', kind='buck', ref='U_BUCK3', l='L_3V3', rth_jb=20.0, tj_max=150.0,
                 eff=((0.1, 0.87), (0.2, 0.92), (0.5, 0.947), (1.0, 0.945), (2.0, 0.933)), vout=3.3,
                 f_note='5 V in, PWM, Fig. 9-3')
TLV76733_LDO = dict(TLV76733, kind='ldo', ref='U_LDO', l=None)
# TI TMP390A2 thermostat on the 9 V BEC (circuit.fc_power): its channel A
# trips at 96 C (SETA 121k) with 20 C hysteresis (SETB at GND) and takes
# the BEC's EN low; trip accuracy +/-3.0 C over -55..130 C (SBOS904A, A2)
TMP390 = dict(part='TI TMP390A2', ref='U_TSW', trip=96.0, hyst=20.0, acc=3.0, t_max=130.0)
# Stack lead, FC end: Molex Micro-Lock Plus 505567, 1.5 A per contact,
# -40..+105 C (Molex 505567 / 505565 product pages).  Contact resistance:
# ASSUMPTION, JST SH's 20 / 40 mOhm (Molex's product specification not read).
MICROLOCK = dict(part='Molex Micro-Lock Plus 505567', i_rated=1.5, r_contact=20e-3, r_contact_aged=40e-3,
                 t_max=105.0)
# FC inductors (TDK catalog): SPM6530T-150M-HZ 119.9 mOhm max (109 typ), 125 C;
# TFM252012ALMAR47MTAA 19 mOhm, 150 C
INDUCTORS_REV2 = {'L_5V': dict(part='TDK SPM6530T-150M-HZ', dcr=119.9e-3, t_max=125.0),
                  'L_9V': dict(part='TDK SPM6530T-150M-HZ', dcr=119.9e-3, t_max=125.0),
                  'L_3V3': dict(part='TDK TFM252012ALMAR47MTAA', dcr=19e-3, t_max=150.0)}
CAPS_REV2.update({
    'C22U25_X7R': ('X7R', 125.0, 'Murata GRM32ER71E226KE15L'),
    'C10U25_X7R': ('X7R', 125.0, 'Murata GRM21BZ71E106KE15L'),
    'C4U7_X7R': ('X7R', 125.0, 'Murata GRM188Z71A475KE15D'),
    'C100N_100': ('X7R', 125.0, 'Murata GRM188R72A104KA35D'),
})

# The designs (design.py switches the files, use() these figures).  Each
# maps the generic names the simulations read to a part above.
DESIGNS = {
    'rev1': dict(
        FET=TPN2R304PL, AM32=dict(AM32), DRIVER=dict(DRV8300, kind='gvdd', vgs=GVDD),
        MCU_ESC=G071, GATE_LDO=TPS7A16, ESC_BUCK=MAX15062, CSA=INA186,
        ESC_3V3_LOAD=ESC_3V3_LOAD_REV1, DVDD_LOAD=0.0, FC_3V3_LOAD=FC_3V3_OWN,
        C_BRIDGE=C_BRIDGE, BULK=dict(EXT_CAP, on_board=False), CAPS=dict(CAPS), ESC_TVS=None,
        BUCK5=LMR38020F, BUCK9=LM76003, V33=TLV76733_LDO, MCU_FC=G473, OSD=AT7456E,
        GYRO=ICM45686, FLASH=W25Q128, STACK_CONN=JST_SH, HD_CONN=JST_SH, FC_TVS=SMF33A,
        INDUCTORS=dict(INDUCTORS), THERMOSTAT=None,
        # the FC's video supply runs from the lead (split=False); the lead's GND
        # pin is the ESC's plane at the connector (kelvin=False)
        LEAD=dict(split=False, kelvin=False, soldered=False),
    ),
    'rev2': dict(
        FET=ISZ023N06LM6,
        AM32=dict(AM32, dead=125e-9,            # DEAD_TIME 15 at 120 MHz (F421 target, firmware/am32)
                  f_min=24e3, f_max=24e3,       # fixed 24 kHz PWM (configurator)
                  sensor='RT',                  # the FET thermistor beside each channel's FETs
                  temp_limit=110.0),            # C at the thermistor (firmware/am32)
        DRIVER=dict(DRV8320, kind='vm', i_src=0.06),   # IDRIVE 60 mA (circuit.IDRIVE)
        # no 3.3 V regulator on the ESC: its four channels run from the
        # FC's 3.3 V buck (stack lead pin 4), none from the drivers' DVDD
        MCU_ESC=AT32F421, GATE_LDO=None, ESC_BUCK=None, CSA=INA186,
        ESC_3V3_LOAD=4 * CHANNEL_3V3, DVDD_LOAD=0.0,
        FC_3V3_LOAD=FC_3V3_OWN + 4 * CHANNEL_3V3,
        C_BRIDGE=C_BRIDGE_REV2, BULK=CERAMIC_BULK,
        CAPS=dict(CAPS_REV2), ESC_TVS=None,
        BUCK5=LMR38020F_455, BUCK9=LMR38020F_9V, V33=TPS628501,
        MCU_FC=G473, OSD=AT7456E, GYRO=IIM42652, FLASH=S25FL128L,
        STACK_CONN=MICROLOCK, HD_CONN=JST_SH, FC_TVS=SMF33A,
        INDUCTORS=dict(INDUCTORS_REV2), THERMOSTAT=TMP390,
        LEAD=dict(split=True, kelvin=True, soldered=True),
    ),
}
_derived = ('BRIDGE', 'BUS', 'BODY_DIODE')


def design_name():
    import design
    return design.current


def idrive(i_src):
    """The DRV8320's gate drive at an IDRIVE source current (A): source and
    sink current, and the dead time that follows (the driver turns a gate
    on 100 ns after it sees the other one low, about Qg / sink current, or
    AM32's, if longer)."""
    ipd = DRIVER['sink_ratio'] * i_src
    return dict(ipu=i_src, ipd=ipd, dead=max(AM32['dead'], FET['qg_11v'] / ipd + DRIVER['dead_add']))


def use(name):
    """Point the generic names at one design's parts, and the files too
    (design.use).  The simulations read data.FET, data.MCU_ESC, ... ."""
    import design
    design.use(name)
    g = globals()
    for k, v in DESIGNS[name].items():
        g[k] = v
    g['BODY_DIODE'] = FET['body_diode']
    b = g['BRIDGE']
    D = DRIVER
    if D['kind'] == 'gvdd':             # DRV8300: fixed peak currents through Rg, bootstrap high side
        b.update(Rg=10.0, gvdd=GVDD, vboot=GVDD - 0.8, ipu=D['i_source'][1], ipd=D['i_sink'][1],
                 dead=AM32['dead'] + D['dead'][1])
    else:                               # DRV8320: IDRIVE current, no gate resistor, charge pump
        b.update(Rg=0.5, gvdd=D['vgs'], vboot=D['vgs'], **idrive(D['i_src']))
    b.update(rpu=D['r_pu'], rpd=D['r_pd'], Cb=C_BRIDGE['c_bias'], ESRb=C_BRIDGE['esr'],
             ESLb=C_BRIDGE['esl'], Cb2=2 * C_BRIDGE['c_bias'], ESRb2=C_BRIDGE['esr'] / 2,
             Cext=BULK['c'], ESRext=BULK['esr'], ESLext=BULK['esl'])
    g['BUS'].update(Cbridge=12 * C_BRIDGE['c_bias'], ESRbridge=C_BRIDGE['esr'] / 12,
                    ESLbridge=C_BRIDGE['esl'] / 12,
                    tvs_bv=sum(FC_TVS['vbr']) / 2, tvs_rs=(FC_TVS['vc'] - FC_TVS['vbr'][1]) / FC_TVS['ipp'],
                    tvs_c=FC_TVS['c'])
    return name


use('rev2')
