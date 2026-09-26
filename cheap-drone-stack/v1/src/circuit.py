# -*- coding: utf-8 -*-
"""The circuit: every component and every connection, as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects to,
with the reason for anything that is not obvious.

Pin numbers are footprint pad numbers, which for every IC here are the
datasheet pin numbers.  Two exceptions are called out where they occur: the
USB-C receptacle (pads named by USB-C contact) and the AON7934's two exposed
pads (numbered 9 and 10 by the footprint, assigned by geometry - see there).

Two boards, one stack, both 33.8 x 33.8 mm on the 25.5 mm M3/M2-grommet
pattern of the GEPRC TAKER G4 AIO that Phase 1 flew:

  FC   STM32G473CEU6 + BMI270 (or ICM-42688-P) + 16 MB flash, USB-C, three UARTs,
       beeper, LED strip, battery voltage and current inputs, 5 V 2 A BEC.
       Pin map mirrors Betaflight target GEPR/TAKERG4AIO, so that stock
       target also runs it (see firmware/ for the board's own target).
  ESC  4 x (STM32F051K6U6 + JSM6288Q + 3 x AON7934 half-bridge), wired to
       AM32 target FD6288_F051 so the stock AM32 release runs it.

They connect through one 8-pin JST-SH lead, pin 1 to pin 1:
"""

# The FPV-standard 8-pin flight-controller <-> 4-in-1 ESC pinout.
STACK_PINS = {
    '1': 'VBAT', '2': 'GND', '3': 'CUR', '4': 'TLM',
    '5': 'M1_SIG', '6': 'M2_SIG', '7': 'M3_SIG', '8': 'M4_SIG',
}

class Comp:
    def __init__(self, ref, part, pins, block, note=''):
        self.ref, self.part, self.pins, self.block, self.note = ref, part, pins, block, note

COMPS = []
_counts = {}

def add(prefix, part, pins, block, note='', ref=None):
    if ref is None:
        _counts[prefix] = _counts.get(prefix, 0) + 1
        ref = '%s%d' % (prefix, _counts[prefix])
    c = Comp(ref, part, dict(pins), block, note)
    COMPS.append(c)
    return c

def cap(part, a, b, block, note=''):
    return add('C', part, {'1': a, '2': b}, block, note)

def res(part, a, b, block, note=''):
    return add('R', part, {'1': a, '2': b}, block, note)

GND = 'GND'

def mounting():
    for i in range(1, 5):
        add('H', 'HOLE', {}, 'mech', 'M3 hole (M2 with grommet)', ref='H%d' % i)

# =====================================================================
#  FLIGHT CONTROLLER BOARD
# =====================================================================
def fc_power():
    B = 'power'
    # Battery comes in on the ESC lead.  A VBAT/GND pad pair is broken out
    # for accessories (a VTX later), fed from the same lead.
    add('J', 'SH8_RA', dict(STACK_PINS, **{'9': None, '10': None}), B,
        'to 4-in-1 ESC (pads 9/10 are mechanical tabs)', ref='J_ESC')
    # Current input: our ESC has no sensor, but a commercial one on this
    # lead may.  The 100k keeps an unconnected input at 0 A, not noise.
    res('R100K', 'CUR', GND, B, 'CUR default low')
    res('R1K', 'CUR', 'ADC_CURR', B, 'CUR RC filter')
    cap('C100N', 'ADC_CURR', GND, B, 'CUR RC filter')

    # Battery voltage divider 10k/1k -> Betaflight vbat_scale 110.
    res('R10K', 'VBAT', 'ADC_VBAT', B, 'VBAT divider top')
    res('R1K', 'ADC_VBAT', GND, B, 'VBAT divider bottom')
    cap('C100N', 'ADC_VBAT', GND, B, 'VBAT filter')

    # 5 V BEC, TI LMR51420 datasheet table 9-2 (1.1 MHz, 5 V): L 4.7 uH,
    # Cout 2 x >= 10 uF.  Vout = 0.6 V x (1 + 15k/2k) = 5.1 V.  36 V part:
    # 4S is 16.8 V charged and regen spikes ride on top of that.
    add('U', 'LMR51420', {'1': GND, '2': 'BUCK_SW', '3': 'VBAT', '4': 'BUCK_FB',
                          '5': 'VBAT', '6': 'BUCK_CB'}, B, '5V BEC', ref='U_BUCK')
    cap('C10U50', 'VBAT', GND, B, 'BEC input')
    cap('C100N', 'VBAT', GND, B, 'BEC input HF')
    cap('C100N', 'BUCK_CB', 'BUCK_SW', B, 'BEC bootstrap')
    add('L', 'L4U7H', {'1': 'BUCK_SW', '2': '+5V'}, B, 'BEC inductor', ref='L1')
    cap('C22U25', '+5V', GND, B, 'BEC output')
    cap('C22U25', '+5V', GND, B, 'BEC output')
    res('R15K', '+5V', 'BUCK_FB', B, 'BEC feedback top')
    res('R2K', 'BUCK_FB', GND, B, 'BEC feedback bottom')

    # 3.3 V for the MCU, gyro and flash.
    add('U', 'ME6211', {'1': '+5V', '2': GND, '3': '+5V', '4': None, '5': '+3V3'},
        B, '3.3V LDO', ref='U_LDO')
    cap('C1U', '+5V', GND, B, 'LDO in')
    cap('C4U7', '+3V3', GND, B, 'LDO out')

def fc_core():
    B = 'fc'
    # STM32G473CEU6 (UFQFPN-48).  Pin assignment is TAKERG4AIO's.
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
        '26': 'SPI2_SCK',   # PB13 flash
        '27': 'SPI2_MISO',  # PB14
        '28': 'SPI2_MOSI',  # PB15
        '29': 'FLASH_CS',   # PC6
        '30': None,         # PA8  (OSD CS in the stock target; no OSD fitted)
        '31': 'UART1_TX',   # PA9
        '32': 'UART1_RX',   # PA10
        '33': 'USB_DM',     # PA11
        '34': 'USB_DP',     # PA12
        '35': '+3V3',       # VDD
        '36': 'SWDIO',      # PA13
        '37': 'SWCLK',      # PA14
        '38': 'BEEPER',     # PA15 (BEEPER_INVERTED: high = on)
        '39': 'UART4_TX',   # PC10
        '40': 'UART4_RX',   # PC11
        '41': 'UART2_TX',   # PB3  receiver (CRSF)
        '42': 'UART2_RX',   # PB4
        '43': None,         # PB5
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

    # 8 MHz crystal (Betaflight SYSTEM_HSE_MHZ 8).  CL = 10 pF, so the load
    # caps are 2 x (10 - ~3 pF stray) = 14 pF -> 12 pF nearest basic part.
    add('Y', 'XTAL8M', {'1': 'HSE_IN', '2': GND, '3': 'HSE_OUT', '4': GND}, B, 'HSE crystal', ref='Y1')
    cap('C12P', 'HSE_IN', GND, B, 'crystal load')
    cap('C12P', 'HSE_OUT', GND, B, 'crystal load')

    # BOOT0: pulled low; the button pulls it to 3.3 V for USB DFU.
    res('R10K', 'BOOT0', GND, B, 'BOOT0 pulldown')
    add('SW', 'BOOTSW', {'1': '+3V3', '2': 'BOOT0'}, B, 'DFU boot button', ref='SW_BOOT')

    # IMU on SPI1: Bosch BMI270, or the ICM-42688-P on the same pads (both
    # are LGA-14 2.5 x 3 with the same SPI/power pins; Betaflight detects
    # either).  Pins 2 and 3 are left open: the BMI270's aux I2C must not
    # be grounded (Bosch), and ICM-42688-P table 9 allows RESV pins 2, 3,
    # 10, 11 "NC or GND".  Pins 10/11 (BMI270 OCSB/OSDO) grounded is fine
    # with OIS off, its reset state; pin 9 grounded is the ICM's FSYNC
    # when unused and the BMI270's INT2, which stays an input unless
    # enabled.  Own 10-ohm / 4.7 uF filter off the 3.3 V rail.
    # Placed rotated 90 degrees so the ICM's +X points at the board's front arrow
    # and its +Y to the left, which is Betaflight's body frame, so
    # GYRO_1_ALIGN = CW0 and board alignment stays 0/0/0.
    add('U', 'BMI270', {'1': 'SPI1_MISO', '2': None, '3': None, '4': 'GYRO_INT',
                           '5': '+3V3_GYRO', '6': GND, '7': GND, '8': '+3V3_GYRO',
                           '9': GND, '10': GND, '11': GND, '12': 'GYRO_CS',
                           '13': 'SPI1_SCK', '14': 'SPI1_MOSI'}, B, 'gyro', ref='U_IMU')
    res('R10', '+3V3', '+3V3_GYRO', B, 'gyro supply filter')
    cap('C4U7', '+3V3_GYRO', GND, B, 'gyro VDD bulk')
    cap('C100N', '+3V3_GYRO', GND, B, 'gyro VDD')
    cap('C100N', '+3V3_GYRO', GND, B, 'gyro VDDIO')

    # 16 MB blackbox flash on SPI2.  /WP and /HOLD held high (plain SPI).
    add('U', 'PY25Q128', {'1': 'FLASH_CS', '2': 'SPI2_MISO', '3': '+3V3', '4': GND,
                         '5': 'SPI2_MOSI', '6': 'SPI2_SCK', '7': '+3V3', '8': '+3V3',
                         '9': GND}, B, 'blackbox flash', ref='U_FLASH')
    cap('C100N', '+3V3', GND, B, 'flash')
    res('R10K', '+3V3', 'FLASH_CS', B, 'flash CS pullup')

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
    add('D', '1N5819WS', {'1': '+5V', '2': 'USB_VBUS'}, B, 'USB VBUS OR-ing', ref='D_USB')

    # Status LEDs.  LED0 is active-low (Betaflight drives the pin low = on).
    add('LED', 'LED_RED', {'1': 'LED_PWR_A', '2': GND}, B, 'power LED', ref='LED_PWR')
    res('R1K', '+3V3', 'LED_PWR_A', B, 'power LED')
    add('LED', 'LED_BLUE', {'2': 'LED0_A', '1': 'LED0'}, B, 'status LED', ref='LED_STAT')
    res('R330', '+3V3', 'LED0_A', B, 'status LED')     # blue LED, Vf ~3 V: 1k left it dim

    # Beeper: low-side AO3400A, buzzer between 5 V and BZ-.  FPV buzzers are
    # active (self-driven) 5 V parts, which Betaflight switches with a
    # steady level, so no flyback diode is needed.
    add('Q', 'AO3400A', {'1': 'BEEPER_G', '2': GND, '3': 'BZ-'}, B, 'beeper switch', ref='Q_BZ')
    res('R100', 'BEEPER', 'BEEPER_G', B, 'beeper gate')
    res('R10K', 'BEEPER_G', GND, B, 'beeper gate pulldown')

    # Solder pads, labelled from the flight controller's side (T = FC TX).
    pads = [('P_RX5V', '+5V'), ('P_RXG', GND), ('P_R2', 'UART2_RX'), ('P_T2', 'UART2_TX'),
            ('P_T1', 'UART1_TX'), ('P_R1', 'UART1_RX'), ('P_T4', 'UART4_TX'), ('P_R4', 'UART4_RX'),
            ('P_5V', '+5V'), ('P_G1', GND), ('P_LED', 'LED_STRIP'),
            ('P_BZ+', '+5V'), ('P_BZ-', 'BZ-'), ('P_VBAT', 'VBAT'), ('P_G2', GND),
            ('P_3V3', '+3V3'), ('P_G3', GND)]
    for ref, net in pads:
        add('P', 'PAD_SIG', {'1': net}, B, 'pad', ref=ref)
    for ref, net in [('TP_SWDIO', 'SWDIO'), ('TP_SWCLK', 'SWCLK'), ('TP_NRST', 'NRST')]:
        add('TP', 'PAD_TP', {'1': net}, B, 'test point', ref=ref)

# =====================================================================
#  4-IN-1 ESC BOARD
# =====================================================================
def esc_power():
    B = 'power'
    # Battery pads.  The XT30 pigtail and the low-ESR bulk capacitor
    # (470 uF 35 V, soldered across these same pads) land here.
    add('P', 'PAD_BAT', {'1': 'VBAT'}, B, 'BAT+', ref='P_BAT+')
    add('P', 'PAD_BAT', {'1': GND}, B, 'BAT-', ref='P_BAT-')
    # To the flight controller.  CUR and TLM are not driven by this ESC.
    add('J', 'SH8_V', dict(STACK_PINS, **{'3': None, '4': None, '9': None, '10': None}), B,
        'to flight controller (pads 9/10 are mechanical tabs)', ref='J_FC')

    # 3.3 V for the four ESC MCUs, straight from the pack with the same
    # buck as the FC's BEC: table 9-2 gives Rfbt 100k / Rfbb 22.1k for
    # 3.3 V; 22k (basic part) gives 3.33 V.  A linear regulator from 16.8 V
    # would burn over a watt.
    add('U', 'LMR51420', {'1': GND, '2': 'BUCK_SW', '3': 'VBAT', '4': 'BUCK_FB',
                          '5': 'VBAT', '6': 'BUCK_CB'}, B, 'ESC 3.3V buck', ref='U_BUCK')
    cap('C10U50', 'VBAT', GND, B, 'buck input')
    cap('C100N', 'VBAT', GND, B, 'buck input HF')
    cap('C100N', 'BUCK_CB', 'BUCK_SW', B, 'buck bootstrap')
    add('L', 'L4U7', {'1': 'BUCK_SW', '2': '+3V3'}, B, 'buck inductor', ref='L1')
    cap('C22U25', '+3V3', GND, B, 'buck output')
    cap('C22U25', '+3V3', GND, B, 'buck output')
    res('R100K', '+3V3', 'BUCK_FB', B, 'buck feedback top')
    res('R22K', 'BUCK_FB', GND, B, 'buck feedback bottom')
    add('LED', 'LED_RED', {'1': 'LED_PWR_A', '2': GND}, B, 'power LED', ref='LED_PWR')
    res('R1K', '+3V3', 'LED_PWR_A', B, 'power LED')

    # Shared battery-voltage divider for AM32 (target FD6288_F051 uses
    # TARGET_VOLTAGE_DIVIDER 65, i.e. a ratio of 6.5 = (11k + 2k) / 2k).
    res('R11K', 'VBAT', 'ESC_VSENSE', B, 'ESC vsense top')
    res('R2K', 'ESC_VSENSE', GND, B, 'ESC vsense bottom')
    cap('C100N', 'ESC_VSENSE', GND, B, 'ESC vsense filter')
    # Common points for the SWD programming lead.
    add('TP', 'PAD_TP', {'1': '+3V3'}, B, 'SWD 3V3', ref='TP_3V3')
    add('TP', 'PAD_TP', {'1': GND}, B, 'SWD GND', ref='TP_GND')

# One ESC channel.  Wired to AM32 hardware group F0_A (target FD6288_F051):
#   input PA2 (TIM15_CH1)
#   phase A: high PA10, low PB1, comparator PA5
#   phase B: high PA9,  low PB0, comparator PA4
#   phase C: high PA8,  low PA7, comparator PA0
#   virtual neutral on PA1 (COMP1 non-inverting input)
#   battery voltage on PA3, current on PA6 (no sensor: tied to ground)
def esc(n):
    B = 'esc%d' % n
    p = lambda s: 'M%d_%s' % (n, s)
    add('U', 'STM32F051', {
        '1': '+3V3', '5': '+3V3', '17': '+3V3', '33': GND,
        '2': None, '3': None,                  # PF0/PF1: AM32 runs on HSI
        '4': p('NRST'),
        '6': p('CMP_C'),                       # PA0
        '7': p('NEUTRAL'),                     # PA1
        '8': p('SIG'),                         # PA2  DShot in
        '9': 'ESC_VSENSE',                     # PA3
        '10': p('CMP_B'),                      # PA4
        '11': p('CMP_A'),                      # PA5
        '12': GND,                             # PA6  current ADC, no sensor per ESC
        '13': p('LC'),                         # PA7  TIM1_CH1N
        '14': p('LB'),                         # PB0  TIM1_CH2N
        '15': p('LA'),                         # PB1  TIM1_CH3N
        '16': None,                            # PB2
        '18': p('HC'),                         # PA8  TIM1_CH1
        '19': p('HB'),                         # PA9  TIM1_CH2
        '20': p('HA'),                         # PA10 TIM1_CH3
        '21': None, '22': None,                # PA11/PA12
        '23': p('SWDIO'),                      # PA13
        '24': p('SWCLK'),                      # PA14
        '25': None, '26': None, '27': None, '28': None, '29': None, '30': None,
        '31': GND,                             # BOOT0: always boot from flash
        '32': None,
    }, B, 'ESC %d MCU' % n, ref='U_ESC%d' % n)
    cap('C100N', '+3V3', GND, B, 'U_ESC%d VDD pin 1' % n)
    cap('C4U7', '+3V3', GND, B, 'U_ESC%d VDD pin 17' % n)     # ST's 4.7 uF bulk, at the MCU
    cap('C1U', '+3V3', GND, B, 'U_ESC%d VDDA' % n)
    cap('C100N', p('NRST'), GND, B, 'U_ESC%d reset filter' % n)

    # Gate driver.  VCC from the pack through 330 ohm into 10 uF, clamped
    # at 15 V: 4S gives 10-15 V at the gates, inside the driver's 8-20 V
    # range, with 5 V to spare below the AON7934's +/-20 V gate rating.
    # (Not for 2S or 3S: too close to the driver's undervoltage lockout.)
    add('U', 'JSM6288Q', {
        '1': p('LA'), '2': p('LB'), '3': p('LC'),          # LIN1..3
        '4': p('VCC'), '5': None, '6': GND, '7': None, '8': None,
        '9': p('GLC'), '10': p('GLB'), '11': p('GLA'),    # LO3..1
        '12': p('C'), '13': p('GHC'), '14': p('VBC'),      # VS3 HO3 VB3
        '15': p('B'), '16': p('GHB'), '17': p('VBB'),      # VS2 HO2 VB2
        '18': p('A'), '19': p('GHA'), '20': p('VBA'),      # VS1 HO1 VB1
        '21': None,
        '22': p('HA'), '23': p('HB'), '24': p('HC'),      # HIN1..3
        '25': GND,                                          # exposed pad -> COM
    }, B, 'ESC %d gate driver' % n, ref='U_GD%d' % n)
    res('R330', 'VBAT', p('VCC'), B, 'driver VCC filter')
    # 15 V clamp: the gates see VCC (low side) and VCC - Vf (high side), so
    # this keeps them 5 V inside the AON7934's +/-20 V at a full 16.8 V pack
    # plus regen.  330 ohm: the driver draws a few mA (1.7 V drop at 5 mA),
    # and at 16.8 V the Zener takes the rest, (16.8 - 15) / 330 = 5.5 mA.
    add('D', 'BZX585C15', {'1': p('VCC'), '2': GND}, B, 'driver VCC clamp')
    cap('C10U50', p('VCC'), GND, B, 'driver VCC bulk')
    cap('C100N', p('VCC'), GND, B, 'driver VCC HF')

    for ph in 'ABC':
        # Bootstrap: Schottky from VCC, 1 uF from VB to VS (the phase node).
        add('D', 'RB521S30', {'2': p('VCC'), '1': p('VB' + ph)}, B, 'bootstrap ' + ph)
        cap('C1U', p('VB' + ph), p(ph), B, 'bootstrap ' + ph)
        # Half-bridge.  AON7934 pads: 1 G1, 2-4 D1, 5-7 S2, 8 G2.  The two
        # exposed pads are numbered 9 and 10 by the footprint: 9 is the
        # narrow one beside the D1 pins (D1, battery), 10 the wide one beside
        # the S2 pins (S1/D2, the switch node) - datasheet bottom view.
        # The driver drives the gates directly, as small ESCs do: its
        # 1.5 A / 1.8 A outputs and the FETs' own 1.3-1.8 ohm internal gate
        # resistance set the edge rate.
        add('Q', 'AON7934', {'1': p('GH' + ph), '2': 'VBAT', '3': 'VBAT', '4': 'VBAT',
                             '9': 'VBAT', '10': p(ph),
                             '5': GND, '6': GND, '7': GND, '8': p('GL' + ph)},
            B, 'half-bridge ' + ph, ref='Q%d%s' % (n, ph))
        # Back-EMF divider: 10k / 2.2k (ratio 5.5, 16.8 V -> 3.05 V).
        res('R10K', p(ph), p('CMP_' + ph), B, 'BEMF ' + ph)
        res('R2K2', p('CMP_' + ph), GND, B, 'BEMF ' + ph)
        # Virtual neutral: one 10k from each phase to a star point, which
        # has 2.2k/3 = 733 -> 750 ohm to ground so it scales exactly like
        # the phase dividers.
        res('R10K', p(ph), p('NEUTRAL'), B, 'neutral ' + ph)
    res('R750', p('NEUTRAL'), GND, B, 'neutral to ground')

    # Local decoupling right at the half-bridges (the 470 uF on the
    # battery pads does the heavy lifting; these kill the switching edges).
    cap('C10U50', 'VBAT', GND, B, 'ESC %d bulk' % n)
    cap('C10U50', 'VBAT', GND, B, 'ESC %d bulk' % n)
    cap('C100N', 'VBAT', GND, B, 'ESC %d HF' % n)

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
