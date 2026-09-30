# -*- coding: utf-8 -*-
"""Datasheet figures the stress simulations use, each with its source.

Values are the makers' own (document, table or figure; "Fig." means read
from that graph).  Where the physics needs a number no maker publishes (a
battery's internal resistance, a lead's inductance, the air speed over a
flying stack), it is marked ASSUMPTION, and the report says what it changes.
"""

# ------------------------------------------------------------------ ESC FETs
FET = dict(
    part='Toshiba TPN2R304PL', src='TPN2R304PL datasheet Rev.4.0.A (2026-04-14)',
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
)
FET['qg_11v'] = FET['qg'] * 11.33 / 10  # gate charge to the 11.3 V drive (above the plateau Qg ~ linear in V)
FET['vth_min_hot'] = FET['vth_min'] - (1.90 - 1.22)   # the typical curve's drop from 25 to 150 C

# Toshiba's G0 model's body diode replaced by a charge-control diode fitted to
# the datasheet recovery test (spice.fit): lifetime, transit time (s)
BODY_DIODE = (10e-9, 5e-9)

# ------------------------------------------------------------------ ESC gate drive
DRV8300 = dict(
    part='TI DRV8300D (RGE)', src='TI SLVSFG5D, March 2022',
    i_source=(0.4, 0.75, 1.2), i_sink=(0.85, 1.5, 2.1),   # A peak, min/typ/max (7.5)
    r_pu=6.0, r_pd=1.5,                 # ohm: VGH_HI 0.6 V and VGH_LO 0.15 V typ at 100 mA (7.5)
    dead=(150e-9, 215e-9, 280e-9),      # DT open (7.5)
    slew_max=2.0,                       # V/ns on SHx, D variant (7.3)
    sh_min=-22.0,                       # V for 2 us (7.3)
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
ESC_3V3_LOAD = 4 * 11e-3 + 4 * 65e-6 + 1.3e-3   # A: four MCUs, four INA186, the power LED

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
FC_3V3_LOAD = 92e-3 + 0.5e-3 + 20e-3 + 51e-3 + 2e-3   # A: MCU, gyro, flash writing, OSD, LEDs
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
