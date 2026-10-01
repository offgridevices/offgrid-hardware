# -*- coding: utf-8 -*-
"""The circuit: every component and every connection, as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects to,
with the reason for anything that is not obvious.

Pin numbers are footprint pad numbers, which for every IC here are the
datasheet pin numbers.  Exceptions are called out where they occur: the
USB-C receptacle (pads named by USB-C contact) and the ESC shunt's Kelvin
sense pads (3 and 4, net-tied to its current pads).

Two boards, one stack (Ridge 3), both 36 x 36 mm on the 25.5 mm
M3/M2-grommet pattern of the GEPRC TAKER G4 AIO that Phase 1 flew:

  FC   STM32G473CEU6 + IIM-42652 (105 C) + 16 MB flash, USB-C, boot
       button, analog OSD (AT7456E) and an HD VTX port (DJI / Walksnail /
       HDZero, MSP DisplayPort), 5 V 2 A BEC and a switchable 9 V VTX BEC,
       all rated for 6S.  firmware/ has the board's Betaflight target,
       one build per gyro.
  ESC  4 x (AT32F421G8U7 + DRV8320H + 6 x ISZ023N06LM6 60 V FETs + 0.5 mOhm
       shunt and INA186 current sense + FET thermistor), 2-6S, wired to
       the AM32 target RIDGE3_F421 (firmware/am32).

They connect through one 8-wire lead, soldered at the ESC, plugged at the
flight controller (Molex Micro-Lock Plus), pin 1 to pin 1:
"""

# The FPV-standard 8-pin flight-controller <-> 4-in-1 ESC pinout.
STACK_PINS = {
    '1': 'VBAT', '2': 'GND', '3': 'CUR', '4': 'TLM',
    '5': 'M1_SIG', '6': 'M2_SIG', '7': 'M3_SIG', '8': 'M4_SIG',
}

class Comp:
    def __init__(self, ref, part, pins, block, note='', option=None):
        self.ref, self.part, self.pins, self.block, self.note = ref, part, pins, block, note
        self.option = option

COMPS = []
_counts = {}

# Option groups: parts a cheaper build may leave off, from the same board.
# Each group owns nets that only its own parts use (OPTION_NETS); nothing
# outside the group may touch them, so leaving the group off cannot take
# power or a signal from anything else (verify.py checks this).
#   fpv       the analog OSD, the 9 V video supply and its switch, the HD
#             video connector and the video pads' parts
#   blackbox  the 16 MB flash (Betaflight runs without it: no blackbox)
OPTIONS = ('fpv', 'blackbox')
OPTION_NETS = {
    'fpv': {'VBAT_VTX', '+9V', 'BUCK9_SW', 'BUCK9_CB', 'BUCK9_VCC', 'BUCK9_RT', 'BUCK9_FB', 'BUCK9_EN',
            'VTX_OFF_G', '+3V3_OSD', 'OSD_XI', 'OSD_XO', 'OSD_RST', 'OSD_VIN', 'OSD_VOUT', 'CAM_VIDEO',
            'VTX_VIDEO', 'HD_SBUS'},
    'blackbox': set(),
}
_option = None


class option:
    """with option('fpv'): every part added inside belongs to that group."""
    def __init__(self, name):
        assert name in OPTIONS, name
        self.name = name

    def __enter__(self):
        global _option
        self.prev, _option = _option, self.name

    def __exit__(self, *a):
        global _option
        _option = self.prev


def add(prefix, part, pins, block, note='', ref=None):
    if ref is None:
        _counts[prefix] = _counts.get(prefix, 0) + 1
        ref = '%s%d' % (prefix, _counts[prefix])
    c = Comp(ref, part, dict(pins), block, note, _option)
    COMPS.append(c)
    return c

def cap(part, a, b, block, note=''):
    return add('C', part, {'1': a, '2': b}, block, note)

def res(part, a, b, block, note=''):
    return add('R', part, {'1': a, '2': b}, block, note)

GND = 'GND'

def mounting():
    for i in range(1, 5):
        add('H', 'HOLE', {}, 'mech', 'slotted M2 grommet hole', ref='H%d' % i)

# =====================================================================
#  FLIGHT CONTROLLER BOARD
# =====================================================================
def fc_power():
    B = 'power'
    # Battery.  Two ways in, for two jobs:
    #   * the ESC lead (pin 1 VBAT, pin 2 GND): the flight controller itself,
    #     its 5 V and 3.3 V rails.  One JST-SH contact is rated 1 A (JST, AWG
    #     28), which the FC's own loads stay under from 2S up (README).
    #   * two solder pads, wired to the ESC's battery pads: VBAT_VTX, the
    #     9 V video supply's own input (fpv group).  A digital VTX takes up
    #     to 18 W; through the lead that is 1.5 A on an empty 6S pack, past
    #     the contact's rating.  Fed only from these pads, the video supply
    #     can never load the lead: with the pads unwired it has no input
    #     and stays off.
    # The two inputs share the ground.  Wired as the README says (these
    # pads to the ESC's battery pads), the motor current does not flow in
    # the loop the lead and these wires make: the ESC feeds its end of the
    # lead from its battery pads by their own copper (esc_power).
    add('J', 'SH8_RA', dict(STACK_PINS, **{'9': None, '10': None}), B,
        'to 4-in-1 ESC (pads 9/10 are mechanical tabs)', ref='J_ESC')
    # 33 V stand-off, 53 V clamp at 7.5 A: above a full 6S pack (25.2 V),
    # below the 5 V buck's 85 V absolute maximum.
    add('D', 'SMF33A', {'1': 'VBAT', '2': GND}, B, 'VBAT TVS', ref='D_TVS')
    cap('C10U50_1210', 'VBAT', GND, B, 'VBAT bulk')

    # Current from the ESC: the average of its four channels' sense
    # amplifiers, 12.5 mV per amp of battery current (ibata_scale 125).
    # The 100k keeps an unconnected input at 0 A, not noise.
    res('R100K', 'CUR', GND, B, 'CUR default low')
    res('R1K', 'CUR', 'ADC_CURR', B, 'CUR RC filter')
    cap('C100N', 'ADC_CURR', GND, B, 'CUR RC filter')

    # Battery voltage: 30k / 2k (ratio 16, vbat_scale 160).  25.2 V gives
    # 1.58 V at PB2, and the 53 V TVS clamp 3.3 V, under PB2's 4.0 V
    # absolute maximum (TT_a pin).  The 30k dissipates 19 mW, 30% of 1/16 W.
    res('R30K', 'VBAT', 'ADC_VBAT', B, 'VBAT divider top')
    res('R2K', 'ADC_VBAT', GND, B, 'VBAT divider bottom')
    cap('C100N', 'ADC_VBAT', GND, B, 'VBAT filter')

    # 5 V, 2 A: TI LMR38020F (80 V, forced PWM at 1 MHz; datasheet
    # SNVSC40E tables 8-1, 9-1).  Vout = 1.0 V x (1 + 100k/24.9k) = 5.02 V.
    # RT 25.5k = 1.0 MHz.  Loaded to 1.2 A (60% of 2 A): MCU, receiver,
    # camera, LED strip, buzzer.
    add('U', 'LMR38020F', {'1': GND, '2': 'VBAT', '3': 'VBAT', '4': 'BUCK5_RT', '5': 'BUCK5_FB',
                           '6': None, '7': 'BUCK5_CB', '8': 'BUCK5_SW', '9': GND},
        B, '5V BEC', ref='U_BUCK5')
    cap('C10U50_1210', 'VBAT', GND, B, '5V BEC input')
    cap('C100N_100', 'VBAT', GND, B, '5V BEC input HF')
    res('R25K5', 'BUCK5_RT', GND, B, '5V BEC 1 MHz')
    cap('C100N', 'BUCK5_CB', 'BUCK5_SW', B, '5V BEC bootstrap')
    add('L', 'L4U7_5V', {'1': 'BUCK5_SW', '2': '+5V'}, B, '5V BEC inductor', ref='L_5V')
    for _ in range(3):
        cap('C22U25', '+5V', GND, B, '5V BEC output')
    res('R100K', '+5V', 'BUCK5_FB', B, '5V BEC feedback top')
    res('R24K9', 'BUCK5_FB', GND, B, '5V BEC feedback bottom')

    with option('fpv'):
        # the video supply's input: two pads for 20-22 AWG from the ESC's
        # battery pads, and its own surge clamp and bulk capacitor
        add('P', 'PAD_MOTOR', {'1': 'VBAT_VTX'}, B, 'video battery in +', ref='P_BAT')
        add('P', 'PAD_MOTOR', {'1': GND}, B, 'video battery in -', ref='P_BATG')
        add('D', 'SMF33A', {'1': 'VBAT_VTX', '2': GND}, B, 'VBAT_VTX TVS', ref='D_TVS9')
        cap('C10U50_1210', 'VBAT_VTX', GND, B, 'VBAT_VTX bulk')
        # 9 V, 2 A for the video transmitter and camera: TI LM76003 (60 V,
        # 3.5 A, forced PWM for a steady 1 MHz under analog video; datasheet
        # SNVSAK0A 8.2.2).  Vout = 1.006 V x (1 + 100k/12.4k) = 9.1 V; for a
        # 10 V rail change the 12.4k to 11.0k.  9 V fits every HD VTX's input
        # range (O4 Lite 3.7-13.2 V, HDZero Race V3 4-12 V, O3 7.4-26.4 V) and
        # keeps regulating down to about 9.5 V of battery (3S).
        # EN: UVLO at 6.0 V (100k / 24.9k), so the rail stays off while USB
        # back-feeds about 4 V to VBAT through the 5 V buck; and an N-FET from
        # EN to ground, driven by PB5 (Betaflight PINIO1), turns the VTX off.
        # PB5 is pulled low at boot: the VTX is on unless the pilot switches it.
        add('U', 'LM76003', dict(
            [(str(k), 'BUCK9_SW') for k in (1, 2, 3, 4, 5)] +
            [(str(k), GND) for k in (7, 19, 23, 27, 28, 29, 30, 13, 14, 15, 24, 25, 26, 31)] +
            [(str(k), 'VBAT_VTX') for k in (20, 21, 22)] +
            [('6', 'BUCK9_CB'), ('8', 'BUCK9_VCC'), ('9', '+9V'), ('10', 'BUCK9_RT'),
             ('11', None), ('12', 'BUCK9_FB'), ('16', None), ('17', 'BUCK9_VCC'), ('18', 'BUCK9_EN')]),
            B, '9V VTX BEC', ref='U_BUCK9')
        cap('C10U50_1210', 'VBAT_VTX', GND, B, '9V BEC input')
        cap('C100N_100', 'VBAT_VTX', GND, B, '9V BEC input HF')
        cap('C470N', 'BUCK9_CB', 'BUCK9_SW', B, '9V BEC bootstrap')
        cap('C2U2', 'BUCK9_VCC', GND, B, '9V BEC VCC')
        cap('C1U_25', '+9V', GND, B, '9V BEC BIAS')
        res('R24K3', 'BUCK9_RT', GND, B, '9V BEC 994 kHz')
        res('R100K', 'VBAT_VTX', 'BUCK9_EN', B, '9V BEC UVLO top')
        res('R24K9', 'BUCK9_EN', GND, B, '9V BEC UVLO bottom')
        add('Q', 'AO3400A', {'1': 'VTX_OFF_G', '2': GND, '3': 'BUCK9_EN'}, B, 'VTX power switch', ref='Q_VTX')
        res('R100', 'VTX_OFF', 'VTX_OFF_G', B, 'VTX switch gate')
        res('R100K', 'VTX_OFF_G', GND, B, 'VTX switch gate pulldown')
        add('L', 'L6U8_BIG', {'1': 'BUCK9_SW', '2': '+9V'}, B, '9V BEC inductor', ref='L_9V')
        for _ in range(4):
            cap('C22U25', '+9V', GND, B, '9V BEC output')
        res('R100K', '+9V', 'BUCK9_FB', B, '9V BEC feedback top')
        res('R12K4', 'BUCK9_FB', GND, B, '9V BEC feedback bottom')

    # 3.3 V for the MCU, gyro, flash and OSD: TI TLV76733 (16 V, 1 A) from
    # the 5 V rail.
    # DRV package: 1 OUT, 2 SNS (tied to OUT, per TI), 3 and 5 GND, 4 EN,
    # 6 IN, 7 thermal pad.
    add('U', 'TLV76733', {'1': '+3V3', '2': '+3V3', '3': GND, '4': '+5V', '5': GND,
                          '6': '+5V', '7': GND}, B, '3.3V LDO', ref='U_LDO')
    cap('C1U_25', '+5V', GND, B, 'LDO in')
    cap('C4U7', '+3V3', GND, B, 'LDO out')

def fc_core():
    B = 'fc'
    # STM32G473CEU6 (UFQFPN-48).  Pin assignment is TAKERG4AIO's, plus the
    # OSD chip select (PA8, as TAKERG4AIO) and the VTX power switch (PB5).
    pins = {
        '1': '+3V3',        # VBAT (backup domain) - no RTC battery, tie to 3.3 V
        '2': None,          # PC13
        '3': None,          # PC14
        '4': None,          # PC15
        '5': 'HSE_IN',      # PF0-OSC_IN
        '6': 'HSE_OUT',     # PF1-OSC_OUT
        '7': 'NRST',        # PG10-NRST
        '8': 'M1_SIG',      # PA0  MOTOR1 (TIM2_CH1)
        '9': 'M2_SIG',      # PA1  MOTOR2
        '10': 'M3_SIG',     # PA2  MOTOR3
        '11': 'M4_SIG',     # PA3  MOTOR4
        '12': 'GYRO_INT',   # PA4  GYRO_1_EXTI
        '13': 'SPI1_SCK',   # PA5
        '14': 'SPI1_MISO',  # PA6
        '15': 'SPI1_MOSI',  # PA7
        '16': None,         # PC4
        '17': 'GYRO_CS',    # PB0  GYRO_1_CS
        '18': 'ADC_CURR',   # PB1  ADC_CURR
        '19': 'ADC_VBAT',   # PB2  ADC_VBAT
        '20': '+3V3',       # VREF+
        '21': '+3V3',       # VDDA
        '22': None,         # PB10 LPUART1 TX (unused)
        '23': '+3V3',       # VDD
        '24': 'TLM',        # PB11 LPUART1 RX <- ESC telemetry, if an ESC sends it
        '25': None,         # PB12
        '26': 'SPI2_SCK',   # PB13 flash + OSD
        '27': 'SPI2_MISO',  # PB14 (TT_a, 4.0 V max: the OSD runs at 3.3 V)
        '28': 'SPI2_MOSI',  # PB15
        '29': 'FLASH_CS',   # PC6
        '30': 'OSD_CS',     # PA8  MAX7456_SPI_CS_PIN
        '31': 'UART1_TX',   # PA9  HD VTX (MSP DisplayPort) / analog VTX control
        '32': 'UART1_RX',   # PA10
        '33': 'USB_DM',     # PA11
        '34': 'USB_DP',     # PA12
        '35': '+3V3',       # VDD
        '36': 'SWDIO',      # PA13
        '37': 'SWCLK',      # PA14
        '38': None,         # PA15 (no beeper: DShot beacon)
        '39': 'UART4_TX',   # PC10 GPS
        '40': 'UART4_RX',   # PC11
        '41': 'UART2_TX',   # PB3  receiver (CRSF)
        '42': 'UART2_RX',   # PB4
        '43': 'VTX_OFF',    # PB5  PINIO1: high = 9 V rail off
        '44': 'LED_STRIP',  # PB6
        '45': 'LED0',       # PB7  status LED, active low
        '46': 'BOOT0',      # PB8-BOOT0
        '47': None,         # PB9
        '48': '+3V3',       # VDD
        '49': GND,          # exposed pad = VSS
    }
    add('U', 'STM32G473', pins, B, 'flight controller MCU', ref='U_FC')
    for n in ('pin 1 VBAT', 'pin 23 VDD', 'pin 35 VDD', 'pin 48 VDD', 'pin 20/21 VREF+/VDDA'):
        cap('C100N', '+3V3', GND, B, 'U_FC ' + n)
    cap('C1U', '+3V3', GND, B, 'U_FC VDDA bulk')
    cap('C4U7', '+3V3', GND, B, 'U_FC bulk')
    cap('C100N', 'NRST', GND, B, 'U_FC reset filter')

    # 8 MHz crystal (Betaflight SYSTEM_HSE_MHZ 8), 10 pF load: 2 x (10 - ~3
    # pF stray) = 14 pF -> 12 pF.
    add('Y', 'XTAL8M', {'1': 'HSE_IN', '2': GND, '3': 'HSE_OUT', '4': GND}, B, 'HSE crystal', ref='Y1')
    cap('C12P', 'HSE_IN', GND, B, 'crystal load')
    cap('C12P', 'HSE_OUT', GND, B, 'crystal load')

    # BOOT0: pulled low; the button pulls it to 3.3 V for USB DFU.
    res('R10K', 'BOOT0', GND, B, 'BOOT0 pulldown')
    add('SW', 'BOOTSW', {'1': '+3V3', '2': 'BOOT0'}, B, 'DFU boot button', ref='SW_BOOT')

    # IMU on SPI1: TDK IIM-42652, the industrial member of the ICM-42688-P
    # family, specified -40..+105 C (DS-000440 table 1; the consumer IMUs
    # Betaflight supports stop at 85 C, which a board at 50 C air passes in
    # hard flying).  Betaflight's icm426xx driver reads it (USE_ACCGYRO_
    # IIM42652, Betaflight 2025.12).  The ICM-42688-P (85 C) has the same
    # pin table and axes, so it is a second source on the same pads under
    # the same firmware.  Pins per the IIM-42652 pin table:
    #   2, 3, 10, 11  RESV: "No Connect or Connect to GND": open
    #   7             RESV: "Connect to GND"
    #   9             INT2/FSYNC: "Connect to GND if FSYNC not used"
    # Own 10-ohm / 4.7 uF filter off the 3.3 V rail (VDD 1.71-3.6 V).
    # Placed rotated 90 degrees, pin 1 rear-left, so its +X points at the
    # board's front arrow and +Y to the left, Betaflight's body frame:
    # GYRO_1_ALIGN = CW0 (DS-000440 fig. 15, the ICM-42688-P's axes).
    add('U', 'IIM42652', {'1': 'SPI1_MISO', '2': None, '3': None, '4': 'GYRO_INT',
                          '5': '+3V3_GYRO', '6': GND, '7': GND, '8': '+3V3_GYRO',
                          '9': GND, '10': None, '11': None, '12': 'GYRO_CS',
                          '13': 'SPI1_SCK', '14': 'SPI1_MOSI'}, B, 'gyro', ref='U_IMU')
    res('R10', '+3V3', '+3V3_GYRO', B, 'gyro supply filter')
    cap('C4U7', '+3V3_GYRO', GND, B, 'gyro VDD bulk')
    cap('C100N', '+3V3_GYRO', GND, B, 'gyro VDD')
    cap('C100N', '+3V3_GYRO', GND, B, 'gyro VDDIO')

    # 16 MB blackbox flash on SPI2: Infineon S25FL128L, rated to 125 C (the
    # Winbond part it replaces stops at 85 C).  /WP and IO3/RESET# held high.
    # Optional (blackbox group): Betaflight probes SPI2 for it at boot and,
    # finding nothing, runs without a blackbox.  Its chip-select pull-up
    # stays with the core, so the line idles high whether it is fitted or
    # not, as it must while the MCU resets (SPI2 is shared with the OSD).
    with option('blackbox'):
        add('U', 'S25FL128L', {'1': 'FLASH_CS', '2': 'SPI2_MISO', '3': '+3V3', '4': GND,
                               '5': 'SPI2_MOSI', '6': 'SPI2_SCK', '7': '+3V3', '8': '+3V3',
                               '9': GND}, B, 'blackbox flash', ref='U_FLASH')
        cap('C100N', '+3V3', GND, B, 'flash')
    res('R10K', '+3V3', 'FLASH_CS', B, 'flash CS pullup')

    # The video group (fpv): the analog OSD and the HD VTX port.  Optional:
    # nothing outside the group uses its nets (OPTION_NETS).  The OSD's
    # chip-select pull-up stays with the core, for the same reason as the
    # flash's.
    res('R10K', '+3V3', 'OSD_CS', B, 'OSD CS pullup')
    with option('fpv'):
        # Analog OSD: AT7456E (MAX7456-compatible; the only one still made) on
        # SPI2 with the flash, at 3.3 V: PB14 (SPI2 MISO) is a 4.0 V-maximum
        # pin, and the chip is specified from 3.15 V.  27 MHz crystal on
        # CLKIN/XFB (the oscillator's capacitors are on chip).  Camera video:
        # 75 ohm termination, AC-coupled into VIN.  Out: VOUT and SAG tied (no
        # sag correction), 75 ohm back-termination to the VTX.
        add('U', 'AT7456E', {'1': None, '2': None, '3': '+3V3_OSD', '4': GND, '5': 'OSD_XI',
                             '6': 'OSD_XO', '7': None, '8': 'OSD_CS', '9': 'SPI2_MOSI',
                             '10': 'SPI2_SCK', '11': 'SPI2_MISO', '12': None, '13': None,
                             '14': None, '15': None, '16': None, '17': None, '18': None,
                             '19': 'OSD_RST', '20': GND, '21': '+3V3_OSD', '22': 'OSD_VIN',
                             '23': GND, '24': '+3V3_OSD', '25': 'OSD_VOUT', '26': 'OSD_VOUT',
                             '27': None, '28': None, '29': GND}, B, 'analog OSD', ref='U_OSD')
        add('FB', 'FB600', {'1': '+3V3', '2': '+3V3_OSD'}, B, 'OSD supply filter', ref='FB_OSD')
        cap('C4U7', '+3V3_OSD', GND, B, 'OSD bulk')
        for n in ('DVDD', 'AVDD', 'PVDD'):
            cap('C100N', '+3V3_OSD', GND, B, 'OSD ' + n)
        res('R10K', '+3V3_OSD', 'OSD_RST', B, 'OSD reset pullup')
        add('Y', 'XTAL27M', {'1': 'OSD_XI', '2': GND, '3': 'OSD_XO', '4': GND}, B, 'OSD crystal', ref='Y2')
        res('R75', 'CAM_VIDEO', GND, B, 'camera termination')
        cap('C100N', 'CAM_VIDEO', 'OSD_VIN', B, 'camera coupling')
        res('R75', 'OSD_VOUT', 'VTX_VIDEO', B, 'VTX back-termination')

        # Digital HD VTX: JST-SH 6-pin, Betaflight connector standard, which is
        # DJI's O3/O4 cable pin for pin: 1 V+ (9 V rail), 2 GND, 3 FC TX,
        # 4 FC RX, 5 GND, 6 SBUS/HDL.  Pin 6 reaches UART2 RX (the receiver
        # port) only through a solder jumper, closed only when a DJI radio
        # replaces the receiver.
        add('J', 'SH6_V', {'1': '+9V', '2': GND, '3': 'UART1_TX', '4': 'UART1_RX', '5': GND,
                           '6': 'HD_SBUS', '7': None, '8': None}, B, 'HD VTX (DJI / Walksnail / HDZero)', ref='J_HD')
        add('SJ', 'SJ_OPEN', {'1': 'HD_SBUS', '2': 'UART2_RX'}, B, 'SBUS jumper (open)', ref='SJ_SBUS')

    # USB-C.  5.1k Rd on each CC so a C-to-C cable supplies 5 V.  VBUS feeds
    # the 5 V rail through a Schottky so the board runs (and configures) on
    # USB alone, and the BEC can never back-feed the host.
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'USB_VBUS', 'B4A9': 'USB_VBUS',
                      'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
                      'A7': 'USB_DM', 'B7': 'USB_DM', 'A8': None, 'B8': None,
                      '1': GND, '2': GND, '3': GND, '4': GND}, B, 'USB-C', ref='J_USB')
    res('R5K1', 'USB_CC1', GND, B, 'CC1 Rd')
    res('R5K1', 'USB_CC2', GND, B, 'CC2 Rd')
    add('U', 'USBLC6', {'1': 'USB_DP', '2': GND, '3': 'USB_DM', '4': 'USB_DM',
                        '5': 'USB_VBUS', '6': 'USB_DP'}, B, 'USB ESD', ref='U_ESD')
    add('D', 'RB160VAM40', {'1': '+5V', '2': 'USB_VBUS'}, B, 'USB VBUS OR-ing', ref='D_USB')

    # Status LEDs.  LED0 is active-low (Betaflight drives the pin low = on).
    add('LED', 'LED_RED', {'1': GND, '2': 'LED_PWR_A'}, B, 'power LED', ref='LED_PWR')   # pad 1 cathode
    res('R1K', '+3V3', 'LED_PWR_A', B, 'power LED')
    add('LED', 'LED_BLUE', {'2': 'LED0_A', '1': 'LED0'}, B, 'status LED', ref='LED_STAT')
    res('R330', '+3V3', 'LED0_A', B, 'status LED')

    # No beeper: Betaflight beeps through the motors (DShot beacon), which
    # finds a lost quad as well as a buzzer and needs no parts.  PA15 is
    # left free.

    # Solder pads, labelled from the flight controller's side (T = FC TX).
    pads = [('P_RX5V', '+5V'), ('P_RXG', GND), ('P_R2', 'UART2_RX'), ('P_T2', 'UART2_TX'),
            ('P_T1', 'UART1_TX'), ('P_R1', 'UART1_RX'), ('P_T4', 'UART4_TX'), ('P_R4', 'UART4_RX'),
            ('P_5V', '+5V'), ('P_G1', GND), ('P_LED', 'LED_STRIP')]
    for ref, net in pads:
        add('P', 'PAD_SIG', {'1': net}, B, 'pad', ref=ref)
    # analog video: camera (5 V, G, video) and VTX (9 V, G, video)
    with option('fpv'):
        for ref, net in [('P_CAM5V', '+5V'), ('P_CAMG', GND), ('P_CAM', 'CAM_VIDEO'),
                         ('P_VTX9V', '+9V'), ('P_VTXG', GND), ('P_VTX', 'VTX_VIDEO')]:
            add('P', 'PAD_SIG', {'1': net}, B, 'pad', ref=ref)
    for ref, net in [('TP_SWDIO', 'SWDIO'), ('TP_SWCLK', 'SWCLK'), ('TP_NRST', 'NRST')]:
        add('TP', 'PAD_TP', {'1': net}, B, 'test point', ref=ref)

# =====================================================================
#  4-IN-1 ESC BOARD
# =====================================================================
# the ESC's bus ceramics (esc_power)
BULK_N = 8


def esc_power():
    B = 'power'
    # Battery pads, sized for 14-16 AWG.  Nothing hangs on the leads: the
    # bus capacitance is on the board (below).
    add('P', 'PAD_BAT', {'1': 'VBAT'}, B, 'BAT+', ref='P_BAT+')
    add('P', 'PAD_BAT_K', {'1': GND, '2': 'FC_GND'}, B, 'BAT-', ref='P_BAT-')
    # Surge clamp at the battery pads: Littelfuse 5.0SMDJ33A, 5 kW
    # (10/1000 us), 33 V stand-off, breaking down at 36.7-40.6 V and
    # clamping 53.3 V at 94 A: under the 60 V FETs.  33 V, not 28 V: a
    # throttle chop into a tired pack lifts the bus to about 35 V for
    # milliseconds (STRESS.md), which a 28 V part would try to absorb.
    # Pad 2 is the cathode (EasyEDA's symbol for this part: 1 A, 2 K).
    add('D', 'TVS_5SMDJ33A', {'1': GND, '2': 'VBAT'}, B, 'battery TVS', ref='D_TVS')
    # Bus capacitance: BULK_N 10 uF 50 V 1210 ceramics (about 5 uF each at
    # 25 V) on the planes, as many as the board takes.  An electrolytic here would carry
    # 4-10 A of the channels' ripple against a 0.5-3.6 A rating (sim
    # scratch study, STRESS.md); the ceramics share it at about 0.5 A
    # each.  Murata GCJ: soft (resin) terminations, so board flex cracks
    # the termination, not the dielectric, and a cracked part opens
    # instead of shorting the battery.
    for k in range(BULK_N):
        cap('C10U50_SOFT', 'VBAT', GND, B, 'bus bulk %d' % (k + 1))

    # The lead to the flight controller, soldered: one pad per wire,
    # VBAT, FC_GND, CUR and the four motor signals (the flight controller
    # has the connector).  No connector on the ESC: its middle runs past
    # 100 C in hard flying on a hot day (STRESS.md), and a solder joint to
    # silicone-insulated wire has no such limit.
    # CUR is the average of the four channels' current-sense outputs.
    # Ground: FC_GND reaches the ground plane only at the battery pad,
    # through a copper tap of its own (the battery pad's Kelvin pad,
    # PAD_BAT_K).  The flight controller's video supply has its own wires
    # from these battery pads, so its ground meets the ESC's twice: through
    # the lead and through those wires.  Were the lead's ground on the plane
    # anywhere else, the motor current's drop across the plane between the
    # battery pad and that point (100 mV at 20 A a motor, rev 1) would
    # drive current round that loop, 1.6 A in rev 1 (STRESS.md).  From the
    # battery pad itself the loop carries only the FC's own current.  A
    # 100 nF capacitor joins FC_GND to the plane at the pads, so the fast
    # edges of the motor signals still return by the shortest way.
    for ref, net in (('P_LV', 'VBAT'), ('P_LG', 'FC_GND'), ('P_LC', 'CUR'), ('P_L1', 'M1_SIG'),
                     ('P_L2', 'M2_SIG'), ('P_L3', 'M3_SIG'), ('P_L4', 'M4_SIG')):
        add('P', 'PAD_SIG', {'1': net}, B, 'stack lead pad', ref=ref)
    cap('C100N', 'FC_GND', GND, B, 'stack ground AC tie')
    for n in (1, 2, 3, 4):
        res('R10K_0201', 'M%d_IOUT' % n, 'CUR', B, 'CUR average %d' % n)
    cap('C100N', 'CUR', GND, B, 'CUR filter')

    # 3.3 V for the four MCUs, current-sense amplifiers and thermistors (about 80 mA):
    # ADI MAX15062A (60 V in, fixed 3.3 V, 300 mA), 33 uH per its table 1.
    # MODE to ground: fixed-frequency PWM.
    add('U', 'MAX15062A', {'1': 'VBAT', '2': 'VBAT', '3': 'BUCK_VCC', '4': '+3V3',
                           '5': GND, '6': None, '7': GND, '8': 'BUCK_LX'},
        B, 'ESC 3.3V buck', ref='U_BUCK')
    cap('C1U_100', 'VBAT', GND, B, 'buck input')
    cap('C1U_25_X7R', 'BUCK_VCC', GND, B, 'buck VCC')
    add('L', 'L33U', {'1': 'BUCK_LX', '2': '+3V3'}, B, 'buck inductor', ref='L1')
    cap('C10U_16_X7R', '+3V3', GND, B, 'buck output')

    # Shared battery-voltage divider for AM32: 100k / 10k, ratio 11
    # (TARGET_VOLTAGE_DIVIDER 110): 25.2 V -> 2.29 V at PA6.
    res('R100K', 'VBAT', 'ESC_VSENSE', B, 'ESC vsense top')
    res('R10K_0201', 'ESC_VSENSE', GND, B, 'ESC vsense bottom')
    cap('C100N', 'ESC_VSENSE', GND, B, 'ESC vsense filter')
    # Common points for the SWD programming lead: supply and ground.  Each
    # MCU has its own SWDIO and SWCLK pads (in its channel, below): the four
    # channels are laid out and routed as one, and a clock shared by all
    # four would have to reach every channel's MCU through the others.
    add('TP', 'PAD_TP', {'1': '+3V3'}, B, 'SWD 3V3', ref='TP_3V3')
    add('TP', 'PAD_TP', {'1': GND}, B, 'SWD GND', ref='TP_GND')

# The DRV8320H's gate current, set by its IDRIVE pin (TI SLVSDJ3D table
# 7-2): source / sink 10/20, 30/60, 60/120, 120/240, 260/520, 570/1140 or
# 1000/2000 mA.  The level is chosen on the half-bridge simulation
# (sim/spice.py, STRESS.md): the lowest peak drain voltage that keeps the
# switching loss in the thermal budget.
#   value: (source A, what the pin connects to: None = open, else (part, net))
IDRIVE_LEVELS = {0.06: ('R75K_0201', GND), 0.12: None, 0.26: ('R75K_0201', 'DVDD')}
IDRIVE = 0.06

# One ESC channel.  Wired to AM32 hardware groups AT_B + AT_045 (targets.h:
# SKYSTARS_F80_F421 and others), which the RIDGE3_F421 target in
# firmware/am32 uses, on the Artery AT32F421G8U7's QFN-28 (pin numbers:
# AT32F421 datasheet figure 5, table 5):
#   input PB4 (TMR3_CH1)
#   phase A: high PA10, low PB1, comparator PA0
#   phase B: high PA9,  low PB0, comparator PA4
#   phase C: high PA8,  low PA7, comparator PA5
#   virtual neutral PA1 (the comparator's + input)
#   battery voltage PA3, current PA6, FET thermistor PA2 (USE_NTC: AM32's
#   temperature limit then reads the power stage itself, not the MCU die)
def esc(n):
    B = 'esc%d' % n
    p = lambda s: 'M%d_%s' % (n, s)
    add('U', 'AT32F421G', {
        '1': p('BOOT0'),                        # BOOT0: low, boot from flash
        '2': None, '3': None,                   # PF0, PF1
        '4': p('NRST'),
        '5': '+3V3',                            # VDDA
        '6': p('CMP_A'),                        # PA0  CMP-
        '7': p('NEUTRAL'),                      # PA1  CMP+
        '8': p('NTC'),                          # PA2  ADC_IN2
        '9': 'ESC_VSENSE',                      # PA3  ADC_IN3
        '10': p('CMP_B'),                       # PA4  CMP-
        '11': p('CMP_C'),                       # PA5  CMP-
        '12': p('ISENSE'),                      # PA6  ADC_IN6
        '13': p('LC'),                          # PA7  TMR1_CH1C
        '14': p('LB'),                          # PB0  TMR1_CH2C
        '15': p('LA'),                          # PB1  TMR1_CH3C
        '16': GND,                              # VSS
        '17': '+3V3',                           # VDD
        '18': p('HC'),                          # PA8  TMR1_CH1
        '19': p('HB'),                          # PA9  TMR1_CH2
        '20': p('HA'),                          # PA10 TMR1_CH3
        '21': p('SWDIO'),                       # PA13
        '22': p('SWCLK'),                       # PA14
        '23': None, '24': None,                 # PA15, PB3
        '25': p('SIG'),                         # PB4  DShot in (and bootloader)
        '26': None, '27': None, '28': None,     # PB5, PB6, PB7
        '29': GND,                              # exposed pad
    }, B, 'ESC %d MCU' % n, ref='U_ESC%d' % n)
    # 100 nF at VDD and at VDDA for the fast edges; the bulk is the buck's
    # 10 uF on the same +3V3 copper
    cap('C100N', '+3V3', GND, B, 'U_ESC%d VDD' % n)
    cap('C100N', '+3V3', GND, B, 'U_ESC%d VDDA' % n)
    cap('C100N', p('NRST'), GND, B, 'U_ESC%d reset filter' % n)
    res('R10K_0201', p('BOOT0'), GND, B, 'U_ESC%d BOOT0' % n)
    # The power stage's temperature: a 10k NTC (Murata NCU15XH103F60RC,
    # B 3380 K) at the channel's FETs, from PA2 to ground, under a 10k from
    # +3V3 (AM32's NTC_table for it is in firmware/am32).
    add('RT', 'NTC10K', {'1': p('NTC'), '2': GND}, B, 'ESC %d FET thermistor' % n, ref='RT%d' % n)
    res('R10K_0201', '+3V3', p('NTC'), B, 'thermistor bias')

    # Gate driver: TI DRV8320H (smart gate drive, hardware interface).
    #   MODE to ground: 6x PWM, INHx / INLx straight from the MCU's timer.
    #   IDRIVE: the gate current, above.  The driver sources and sinks
    #     that current (sink twice source) and holds the other FET of the
    #     leg off with 2 A (ISTRONG) while one switches, then 50 mA: no
    #     gate resistors.
    #   VDS open (Hi-Z): overcurrent trip at 0.6 V across a conducting FET,
    #     150 A hot, a short, not a hard punch; 4 ms automatic retry.
    #   The high side runs from its charge pump (VCP), not bootstrap
    #     capacitors, so 100 % duty holds.  Its dead time: it waits for the
    #     other gate to fall, then 100 ns, on top of AM32's own.
    #   ENABLE on +3V3: the driver wakes with the MCU's supply.  nFAULT is
    #     not read (AM32 has no use for it).
    add('U', 'DRV8320H', {
        '1': p('CPH'), '32': p('CPL'), '2': p('VCP'), '3': 'VBAT', '4': 'VBAT',   # VM, VDRAIN
        '5': p('GHA'), '6': p('A'), '7': p('GLA'), '8': p('SRC'),
        '9': p('SRC'), '10': p('GLB'), '11': p('B'), '12': p('GHB'),
        '13': p('GHC'), '14': p('C'), '15': p('GLC'), '16': p('SRC'),
        '17': None,                             # nFAULT
        '18': GND,                              # MODE: 6x PWM
        '19': p('IDRIVE') if IDRIVE_LEVELS[IDRIVE] else None,
        '20': None,                             # VDS: Hi-Z, 0.6 V
        '21': None,                             # NC
        '22': '+3V3',                           # ENABLE
        '23': GND,                              # AGND
        '24': p('DVDD'),
        '25': p('HA'), '26': p('LA'), '27': p('HB'), '28': p('LB'), '29': p('HC'), '30': p('LC'),
        '31': GND,                              # PGND
        '33': GND,                              # exposed pad
    }, B, 'ESC %d gate driver' % n, ref='U_GD%d' % n)
    cap('C100N', 'VBAT', GND, B, 'driver VM')
    cap('C1U_25_X7R', p('VCP'), 'VBAT', B, 'driver charge pump')
    cap('C47N_50', p('CPH'), p('CPL'), B, 'driver flying cap')
    cap('C1U_25_X7R', p('DVDD'), GND, B, 'driver DVDD')
    lvl = IDRIVE_LEVELS[IDRIVE]
    if lvl:
        res(lvl[0], p('IDRIVE'), p('DVDD') if lvl[1] == 'DVDD' else lvl[1], B, 'driver IDRIVE')

    for ph in 'ABC':
        # Half-bridge of two 60 V FETs.  Pads 1-3 source, 4 gate, 5-8 and
        # the tab (9) drain.  The low side's source goes to the channel's
        # sense node, which returns to ground through the shunt.
        add('Q', 'ISZ023N06LM6', {'1': p(ph), '2': p(ph), '3': p(ph), '4': p('GH' + ph),
                                '5': 'VBAT', '6': 'VBAT', '7': 'VBAT', '8': 'VBAT', '9': 'VBAT'},
            B, 'high side ' + ph, ref='Q%d%sH' % (n, ph))
        add('Q', 'ISZ023N06LM6', {'1': p('SRC'), '2': p('SRC'), '3': p('SRC'), '4': p('GL' + ph),
                                '5': p(ph), '6': p(ph), '7': p(ph), '8': p(ph), '9': p(ph)},
            B, 'low side ' + ph, ref='Q%d%sL' % (n, ph))
        # Bridge decoupling right under the half-bridge, VBAT to the sense
        # node, so the switching loop closes through the board's thickness
        # and stays on the bridge side of the shunt.
        cap('C_BRIDGE', 'VBAT', p('SRC'), B, 'bridge ' + ph)
        # Back-EMF divider 20k / 2k (ratio 11: a 35 V spike reaches 3.2 V).
        res('R20K', p(ph), p('CMP_' + ph), B, 'BEMF ' + ph)
        res('R2K_0201', p('CMP_' + ph), GND, B, 'BEMF ' + ph)
        # Virtual neutral: 10k from each divided phase (CMP) to a star.  The
        # star sits at the mean of the three CMP nodes, so CMP - NEUTRAL
        # crosses zero where the phase crosses the mean of the three phases,
        # as a star of the phases themselves would; the comparator sees
        # 10k / (10k + 20k || 2k) = 0.85 of that difference.
        res('R10K_0201', p('CMP_' + ph), p('NEUTRAL'), B, 'neutral ' + ph)

    # Current sense: 0.5 mOhm from the sense node to ground, read by an
    # INA186A3 (100 V/V): 50 mV/A at PA6 through 1k / 100 nF (1.6 kHz).
    # 0.2 W in the shunt at 20 A.
    # The shunt's footprint has Kelvin sense pads (3 on the sense-node end,
    # 4 on the ground end, net-tied to the current pads), so the amplifier
    # reads the voltage across the resistor itself, not across the pour or
    # plane carrying 20 A: a millivolt of plane drop would read as 2 A.
    add('R', 'SHUNT_0M5', {'1': p('SRC'), '2': GND, '3': p('SNSP'), '4': p('SNSN')}, B,
        'ESC %d shunt' % n, ref='R_SH%d' % n)
    # INA186A3 (100 V/V, SC-70-6): REF to ground, output from 0 V up.
    add('U', 'INA186A3', {'1': GND, '2': GND, '3': '+3V3', '4': p('SNSP'), '5': p('SNSN'), '6': p('IOUT')},
        B, 'ESC %d current amplifier' % n, ref='U_CS%d' % n)
    cap('C100N', '+3V3', GND, B, 'U_CS%d supply' % n)
    res('R1K_0201', p('IOUT'), p('ISENSE'), B, 'current filter')
    cap('C100N', p('ISENSE'), GND, B, 'current filter')

    for ph in 'ABC':
        add('P', 'PAD_MOTOR', {'1': p(ph)}, B, 'motor %d phase %s' % (n, ph), ref='P_M%d%s' % (n, ph))
    add('TP', 'PAD_TP', {'1': p('SWDIO')}, B, 'ESC%d SWDIO' % n, ref='TP_E%d_DIO' % n)
    add('TP', 'PAD_TP', {'1': p('SWCLK')}, B, 'ESC%d SWCLK' % n, ref='TP_E%d_CLK' % n)

def build(board):
    COMPS.clear(); _counts.clear()
    if board == 'fc':
        fc_power(); fc_core()
    elif board == 'esc':
        esc_power()
        for n in (1, 2, 3, 4):
            esc(n)
    else:
        raise ValueError(board)
    mounting()
    return list(COMPS)

def nets(comps):
    out = {}
    for c in comps:
        for pad, net in c.pins.items():
            if net:
                out.setdefault(net, []).append((c.ref, pad))
    return out

if __name__ == '__main__':
    import parts
    allp = {**parts.PARTS, **parts.PADS}
    for b in ('fc', 'esc'):
        cs = build(b)
        ns = nets(cs)
        print('%s: %d components (%d assembled), %d nets' % (
            b, len(cs), sum(1 for c in cs if c.part in parts.PARTS), len(ns)))
        for c in cs:
            assert c.part in allp, c.part
        for n, members in sorted(ns.items()):
            if len(members) < 2:
                print('  single-pin net:', n, members)
