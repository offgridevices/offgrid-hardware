# -*- coding: utf-8 -*-
"""The circuit: every component and every connection, as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects
to, with the reason for anything that is not obvious.  Pin numbers are
footprint pad numbers, which for every IC here are the datasheet pin
numbers (the USB-C receptacle's pads are named by contact).

One board: flight controller and 4-in-1 ESC together (an "AIO"), for a
3-inch quad on 2-4S, on the 25.5 mm M2 soft-mount pattern.  No video.

Firmware is stock on both halves, nothing custom is needed to fly:

  FC   wired pin for pin to Betaflight's TAKERG4AIO target (GEPRC TAKER G4
       AIO, the board Phase 1 flew): configs/GEPR/TAKERG4AIO/config.h in
       betaflight/config.  Pick that target in Betaflight Configurator.
  ESC  four AM32 ESCs, each wired to AM32's stock GEN_64K_G071 target
       (hardware group G0_A, Inc/targets.h in am32-firmware/AM32):
       ESC-configurator flashes and updates them from its normal list.

Motors are Betaflight's Quad X: 1 rear-right, 2 front-right, 3 rear-left,
4 front-left.  FC motor output n drives ESC n.
"""

class Comp:
    def __init__(self, ref, part, pins, block, note='', role=None):
        self.ref, self.part, self.pins, self.block, self.note = ref, part, pins, block, note
        self.role = role

COMPS = []
_counts = {}
_roles = set()

# Reference designators: the flight controller and power parts count up
# from 1 (C1, R1 ...); ESC channel n's parts count from n x 100 + 1 (C101
# ... for ESC 1), so a channel reads as a group on the assembly drawing.
# Every part also has a role, the key layout.py places it by: its
# explicit ref, or its note (a channel's roles start with "n:").
CHANNEL = [0]

def add(prefix, part, pins, block, note='', ref=None):
    role = ref
    if ref is None:
        key = (prefix, CHANNEL[0])
        _counts[key] = _counts.get(key, 0) + 1
        ref = '%s%d' % (prefix, CHANNEL[0] * 100 + _counts[key])
        role = ('%d:%s' % (CHANNEL[0], note)) if CHANNEL[0] else note
        base, k = role, 2
        while role in _roles:
            role = '%s#%d' % (base, k); k += 1
    _roles.add(role)
    c = Comp(ref, part, dict(pins), block, note, role)
    COMPS.append(c)
    return c

def cap(part, a, b, block, note='', ref=None):
    return add('C', part, {'1': a, '2': b}, block, note, ref)

def res(part, a, b, block, note='', ref=None):
    return add('R', part, {'1': a, '2': b}, block, note, ref)

GND = 'GND'

# =====================================================================
#  POWER: battery in, 5 V, 3.3 V (FC), 3.3 V (ESC), gate-drive supply
# =====================================================================
def power():
    B = 'power'
    # Battery pads for an 18 AWG XT30 lead, with the 470 uF low-ESR
    # electrolytic soldered across the same two pads.
    add('P', 'PAD_BAT', {'1': 'VBAT'}, B, 'battery +', ref='P_BAT+')
    add('P', 'PAD_BAT', {'1': GND}, B, 'battery -', ref='P_BAT-')
    # TVS across the battery: SMF22A, 22 V stand-off (above a 4S HV pack,
    # 17.4 V), 24.4 V breakdown, 35.5 V clamp at 5.6 A: under the 40 V
    # FETs.  It catches the short spikes the bulk capacitor is too slow or
    # too far away for; the capacitor does the heavy lifting (sim/).
    add('D', 'SMF22A', {'1': 'VBAT', '2': GND}, B, 'battery TVS', ref='D_TVS')

    # 5 V, 0.6 A: TI LMR36506R5 (fixed 5 V, 70 V absolute maximum on VIN:
    # 4x a full 4S HV pack).  RT to ground: 2.2 MHz.  EN/UVLO from a
    # divider, 1.263 V x (100k + 27k) / 27k = 5.9 V (5.5-6.4 V over the
    # threshold's spread): the converter stays off while USB back-feeds a
    # few volts into VBAT.
    # Load with no video gear: FC + gyro + flash ~0.12 A, four ESC MCUs and
    # amplifiers ~0.04 A, receiver ~0.15 A, buzzer ~0.03 A: 0.35 A, 58 %.
    add('U', 'LMR36506R5', {'1': GND, '2': None, '3': 'BEC_EN', '4': 'VBAT', '5': 'BEC_SW',
                            '6': 'BEC_BOOT', '7': 'BEC_VCC', '8': '+5V', '9': GND},
        B, '5 V BEC', ref='U_BEC')
    cap('C4U7_50', 'VBAT', GND, B, 'BEC input')
    cap('C100N_50', 'VBAT', GND, B, 'BEC input HF')
    res('R100K', 'VBAT', 'BEC_EN', B, 'BEC UVLO top')
    res('R27K_0201', 'BEC_EN', GND, B, 'BEC UVLO bottom')
    cap('C100N_50', 'BEC_BOOT', 'BEC_SW', B, 'BEC bootstrap')
    cap('C1U_25', 'BEC_VCC', GND, B, 'BEC VCC')
    add('L', 'L10U', {'1': 'BEC_SW', '2': '+5V'}, B, 'BEC inductor', ref='L_BEC')
    for _ in range(2):
        cap('C22U_25', '+5V', GND, B, 'BEC output')

    # 3.3 V for the flight controller (MCU, gyro, flash): TLV76733 from 5 V.
    # DRV: 1 OUT, 2 SNS (to OUT), 3/5 GND, 4 EN, 6 IN, 7 pad.
    add('U', 'TLV76733', {'1': '+3V3', '2': '+3V3', '3': GND, '4': '+5V', '5': GND,
                          '6': '+5V', '7': GND}, B, 'FC 3.3 V LDO', ref='U_LDO')
    cap('C1U_25', '+5V', GND, B, 'FC LDO in')
    cap('C4U7_25', '+3V3', GND, B, 'FC LDO out')

    # 3.3 V for the four ESC MCUs and current amplifiers, on its own LDO so
    # their switching noise stays off the gyro's supply.
    add('U', 'TLV76733', {'1': '+3V3E', '2': '+3V3E', '3': GND, '4': '+5V', '5': GND,
                          '6': '+5V', '7': GND}, B, 'ESC 3.3 V LDO', ref='U_LDOE')
    cap('C1U_25', '+5V', GND, B, 'ESC LDO in')
    cap('C4U7_25', '+3V3E', GND, B, 'ESC LDO out')

    # Gate-drive supply for the four DRV8300s: TPS7A1601 (60 V) at
    # 1.193 V x (1 + 82k / 10k) = 10.97 V.  10 V is where the FETs'
    # 2.3 mOhm is specified; 11 V is 55 % of the driver's 20 V GVDD and of
    # the FETs' 20 V gate rating.  Below about 11.5 V of battery (3S
    # sagging) it passes the pack through.  10 ohm + 4.7 uF ahead of it
    # blunt battery spikes.  EN tied to IN (EN is rated to IN + 0.3 V).
    add('U', 'TPS7A1601', {'1': 'GVDD', '2': 'GVDD_FB', '3': None, '4': GND, '5': 'GVDD_IN',
                           '6': None, '7': None, '8': 'GVDD_IN', '9': GND}, B, 'gate-drive LDO', ref='U_GVDD')
    res('R10R_0402', 'VBAT', 'GVDD_IN', B, 'gate-drive LDO input filter')
    cap('C4U7_50', 'GVDD_IN', GND, B, 'gate-drive LDO input')
    res('R82K', 'GVDD', 'GVDD_FB', B, 'gate-drive LDO feedback top')
    res('R10K_0201', 'GVDD_FB', GND, B, 'gate-drive LDO feedback bottom')
    cap('C10U_25', 'GVDD', GND, B, 'gate-drive LDO output')

    # Battery voltage for Betaflight: 10k / 1k, ratio 11 = Betaflight's
    # default vbat_scale 110.  17.4 V -> 1.58 V at PB2.
    res('R10K', 'VBAT', 'ADC_VBAT', B, 'VBAT divider top')
    res('R1K_0201', 'ADC_VBAT', GND, B, 'VBAT divider bottom')
    cap('C100N_0201', 'ADC_VBAT', GND, B, 'VBAT filter')

    # Battery current for Betaflight: the four ESC amplifiers' outputs
    # (50 mV/A of each motor's current) averaged through 10k each, and
    # pulled down by 62k: (50 / 4) x 62 / (62 + 2.5) = 12.02 mV/A of total
    # battery current = TAKERG4AIO's default ibata_scale 120.
    res('R62K_0201', 'CUR', GND, B, 'current average pulldown')
    cap('C100N_0201', 'CUR', GND, B, 'current filter')

# =====================================================================
#  FLIGHT CONTROLLER
# =====================================================================
def fc():
    B = 'fc'
    # STM32G473CEU6, UFQFPN-48.  TAKERG4AIO's pin map (its FC_TARGET_MCU is
    # the G474, a superset; Betaflight's G47x build runs on the G473).
    pins = {
        '1': '+3V3',        # VBAT (backup domain, no RTC battery)
        '2': None,          # PC13
        '3': None,          # PC14
        '4': None,          # PC15
        '5': 'HSE_IN',      # PF0-OSC_IN   (SYSTEM_HSE_MHZ 8)
        '6': 'HSE_OUT',     # PF1-OSC_OUT
        '7': 'NRST',        # PG10-NRST
        '8': 'M1_SIG',      # PA0  MOTOR1_PIN
        '9': 'M2_SIG',      # PA1  MOTOR2_PIN
        '10': 'M3_SIG',     # PA2  MOTOR3_PIN
        '11': 'M4_SIG',     # PA3  MOTOR4_PIN
        '12': 'GYRO_INT',   # PA4  GYRO_1_EXTI_PIN
        '13': 'SPI1_SCK',   # PA5  SPI1_SCK_PIN
        '14': 'SPI1_MISO',  # PA6  SPI1_SDI_PIN
        '15': 'SPI1_MOSI',  # PA7  SPI1_SDO_PIN
        '16': None,         # PC4
        '17': 'GYRO_CS',    # PB0  GYRO_1_CS_PIN
        '18': 'CUR',        # PB1  ADC_CURR_PIN
        '19': 'ADC_VBAT',   # PB2  ADC_VBAT_PIN
        '20': '+3V3',       # VREF+
        '21': '+3V3',       # VDDA
        '22': None,         # PB10 LPUART1 TX (no pad)
        '23': '+3V3',       # VDD
        '24': None,         # PB11 LPUART1 RX (no pad)
        '25': None,         # PB12
        '26': None,         # PB13 SPI2_SCK_PIN   (no flash fitted)
        '27': None,         # PB14 SPI2_SDI_PIN
        '28': None,         # PB15 SPI2_SDO_PIN
        '29': None,         # PC6  FLASH_CS_PIN
        '30': None,         # PA8  MAX7456_SPI_CS_PIN: no OSD on this board
        '31': 'UART1_TX',   # PA9  UART1_TX_PIN (spare: GPS)
        '32': 'UART1_RX',   # PA10 UART1_RX_PIN
        '33': 'USB_DM',     # PA11
        '34': 'USB_DP',     # PA12
        '35': '+3V3',       # VDD
        '36': None,         # PA13 SWDIO / I2C1_SCL_PIN (no baro or compass fitted)
        '37': None,         # PA14 SWCLK / I2C1_SDA_PIN
        '38': 'BEEPER',     # PA15 BEEPER_PIN (BEEPER_INVERTED: high = on)
        '39': None,         # PC10 UART4_TX_PIN (no pad)
        '40': None,         # PC11 UART4_RX_PIN (no pad)
        '41': 'UART2_TX',   # PB3  UART2_TX_PIN  -> receiver RX
        '42': 'UART2_RX',   # PB4  UART2_RX_PIN  <- receiver TX
        '43': None,         # PB5  SPI3_SDO_PIN (unused)
        '44': 'LED_STRIP',  # PB6  LED_STRIP_PIN
        '45': 'LED0',       # PB7  LED0_PIN (active low)
        '46': 'BOOT0',      # PB8-BOOT0
        '47': None,         # PB9
        '48': '+3V3',       # VDD
        '49': GND,          # exposed pad = VSS
    }
    add('U', 'STM32G473', pins, B, 'flight controller MCU', ref='U_FC')
    for n in ('VBAT pin 1', 'VDD pin 23', 'VDD pin 35', 'VDD pin 48', 'VREF+/VDDA pins 20/21'):
        cap('C100N_0201', '+3V3', GND, B, 'U_FC ' + n)
    cap('C1U_0201', '+3V3', GND, B, 'U_FC VDDA')
    cap('C4U7_0402', '+3V3', GND, B, 'U_FC bulk')
    cap('C100N_0201', 'NRST', GND, B, 'U_FC reset filter')

    # 8 MHz crystal, 10 pF load: 2 x (10 - ~3 pF stray) = 14 pF -> 12 pF.
    add('Y', 'XTAL8M', {'1': 'HSE_IN', '2': GND, '3': 'HSE_OUT', '4': GND}, B, 'HSE crystal', ref='Y1')
    cap('C12P', 'HSE_IN', GND, B, 'crystal load')
    cap('C12P', 'HSE_OUT', GND, B, 'crystal load')

    # BOOT0 pulled low; the button pulls it to 3.3 V for USB DFU.
    res('R10K_0201', 'BOOT0', GND, B, 'BOOT0 pulldown')
    add('SW', 'BOOTSW', {'1': '+3V3', '2': 'BOOT0'}, B, 'DFU boot button', ref='SW_BOOT')

    # Gyro: TDK ICM-42688-P on SPI1 (TAKERG4AIO: USE_GYRO_SPI_ICM42688P).
    # TDK table 9: RESV 7 and FSYNC 9 to GND; RESV 2, 3, 10, 11 "NC or GND"
    # (left open, so a Bosch BMI270 also fits these pads).  Its own 10 ohm /
    # 4.7 uF filter off the FC's 3.3 V.  TDK fig. 5: 0.1 uF + 2.2 uF on VDD,
    # 10 nF on VDDIO.  Placed so TAKERG4AIO's GYRO_1_ALIGN CW270 plus its
    # DEFAULT_ALIGN_BOARD_YAW 45 come out as the quad's own axes (layout.py).
    add('U', 'ICM42688P', {'1': 'SPI1_MISO', '2': None, '3': None, '4': 'GYRO_INT',
                           '5': '+3V3_GYRO', '6': GND, '7': GND, '8': '+3V3_GYRO',
                           '9': GND, '10': None, '11': None, '12': 'GYRO_CS',
                           '13': 'SPI1_SCK', '14': 'SPI1_MOSI'}, B, 'gyro', ref='U_IMU')
    res('R10R_0201', '+3V3', '+3V3_GYRO', B, 'gyro supply filter')
    cap('C4U7_0402', '+3V3_GYRO', GND, B, 'gyro VDD bulk')
    cap('C100N_0201', '+3V3_GYRO', GND, B, 'gyro VDD')
    cap('C100N_0201', '+3V3_GYRO', GND, B, 'gyro VDDIO')

    # No blackbox flash: on 35 x 35 mm with 24 power FETs there is no
    # 6 x 5 mm spot left that is not over the power stage's vias, and the
    # board's job is to fly.  Betaflight can log to an OpenLager on UART1.

    # USB-C, device only: 5.1k Rd on each CC so a C-to-C cable gives 5 V.
    # VBUS feeds the 5 V rail through a Schottky: the board configures on
    # USB alone, and the BEC never back-feeds the host.
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'USB_VBUS', 'B4A9': 'USB_VBUS',
                      'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
                      'A7': 'USB_DM', 'B7': 'USB_DM', 'A8': None, 'B8': None,
                      '8': GND, '9': GND, '10': GND, '11': GND}, B, 'USB-C', ref='J_USB')
    res('R5K1_0201', 'USB_CC1', GND, B, 'CC1 Rd')
    res('R5K1_0201', 'USB_CC2', GND, B, 'CC2 Rd')
    # USBLC6-2SC6: 1 I/O1, 2 GND, 3 I/O2, 4 I/O2, 5 VBUS, 6 I/O1.
    add('U', 'USBLC6', {'1': 'USB_DP', '2': GND, '3': 'USB_DM', '4': 'USB_DM',
                        '5': 'USB_VBUS', '6': 'USB_DP'}, B, 'USB ESD', ref='U_ESD')
    add('D', 'SS1040HE', {'1': '+5V', '2': 'USB_VBUS'}, B, 'USB VBUS OR-ing', ref='D_USB')

    # LEDs (pad 1 = cathode).  LED0 is active low.
    add('LED', 'LED_RED', {'1': GND, '2': 'LED_PWR_A'}, B, 'power LED', ref='LED_PWR')
    res('R1K_0201', '+3V3', 'LED_PWR_A', B, 'power LED')
    add('LED', 'LED_BLUE', {'1': 'LED0', '2': 'LED0_A'}, B, 'status LED', ref='LED_STAT')
    res('R330_0201', '+3V3', 'LED0_A', B, 'status LED')

    # Beeper: low-side AO3400A, active 5 V buzzer between 5 V and BZ-.
    add('Q', 'AO3400A', {'1': 'BEEPER_G', '2': GND, '3': 'BZ-'}, B, 'beeper switch', ref='Q_BZ')
    res('R100R_0201', 'BEEPER', 'BEEPER_G', B, 'beeper gate')
    res('R10K_0201', 'BEEPER_G', GND, B, 'beeper gate pulldown')

    # Solder pads, named from the flight controller's side (T = FC TX).
    pads = [('P_5V', '+5V'), ('P_G', GND), ('P_R2', 'UART2_RX'), ('P_T2', 'UART2_TX'),
            ('P_T1', 'UART1_TX'), ('P_R1', 'UART1_RX'), ('P_LED', 'LED_STRIP'),
            ('P_BZ+', '+5V'), ('P_BZ-', 'BZ-')]
    for ref, net in pads:
        add('P', 'PAD_SIG', {'1': net}, B, 'pad', ref=ref)

# =====================================================================
#  ESC: one channel, written once, four times
# =====================================================================
# AM32 hardware group G0_A on the STM32G071's 28-pin package (DS12232,
# pin table, "GP" pinout; PA9/PA10 are on pads PA11/PA12, which AM32
# remaps at start-up):
#   input PB4 (TIM3_CH1)
#   phase A: high PA10 [pad PA12], low PB1, comparator PB7 (COMP2 INM IO2)
#   phase B: high PA9  [pad PA11], low PB0, comparator PB3 (COMP2 INM IO1)
#   phase C: high PA8, low PA7, comparator PA2 (COMP2 INM IO3)
#   virtual neutral PA3 (COMP2 INP IO3)
#   current PA5 (MILLIVOLT_PER_AMP 20), battery voltage PA6 (divider 110)
def esc(n):
    B = 'esc%d' % n
    p = lambda s: 'M%d_%s' % (n, s)
    add('U', 'STM32G071G', {
        '1': None, '2': None,                   # PC14 / PC15
        '3': '+3V3E',                           # VDD/VDDA
        '4': GND,                               # VSS/VSSA
        '5': None,                              # PF2-NRST (internal pull-up and filter)
        '6': None, '7': None,                   # PA0 / PA1
        '8': p('CMP_C'),                        # PA2  COMP2_INM IO3
        '9': p('NEUTRAL'),                      # PA3  COMP2_INP IO3
        '10': None,                             # PA4
        '11': p('ISENSE'),                      # PA5  ADC_IN5 current
        '12': p('VSENSE'),                      # PA6  ADC_IN6 battery voltage
        '13': p('LC'),                          # PA7  TIM1_CH1N
        '14': p('LB'),                          # PB0  TIM1_CH2N
        '15': p('LA'),                          # PB1  TIM1_CH3N
        '16': p('HC'),                          # PA8  TIM1_CH1
        '17': None,                             # PC6
        '18': p('HB'),                          # PA11 [PA9]  TIM1_CH2
        '19': p('HA'),                          # PA12 [PA10] TIM1_CH3
        '20': p('SWDIO'),                       # PA13
        '21': p('SWCLK'),                       # PA14-BOOT0
        '22': None,                             # PA15
        '23': p('CMP_B'),                       # PB3  COMP2_INM IO1
        '24': p('SIG'),                         # PB4  DShot in (and AM32 bootloader)
        '25': None, '26': None,                 # PB5, PB6 (serial telemetry: unused, EDT over DShot)
        '27': p('CMP_A'),                       # PB7  COMP2_INM IO2
        '28': None,                             # PB8
    }, B, 'ESC %d MCU' % n, ref='U_E%d' % n)
    # 100 nF at the VDD pin; the bulk ST asks for (4.7 uF) is the ESC LDO's
    # output capacitor on the same +3V3E rail.
    cap('C100N_0201', '+3V3E', GND, B, 'U_E%d VDD' % n)

    # Gate driver: TI DRV8300D (bootstrap diodes inside).  MODE and DT open:
    # inputs non-inverting, 215 ns of its own dead time on top of AM32's.
    # TI 9.2.2: CBST 1 uF (0.4 uF left at 11 V, 8x the 50 nC a turn-on
    # takes); CGVDD >= 10 x CBST: 10 uF 0603 at the pin.
    add('U', 'DRV8300D', {
        '1': p('LA'), '2': p('LB'), '3': p('LC'),           # INLA..C
        '4': 'GVDD', '5': None, '6': GND, '7': None, '8': None,
        '9': p('GLC_D'), '10': p('GLB_D'), '11': p('GLA_D'),
        '12': p('C'), '13': p('GHC_D'), '14': p('BSTC'),    # SHC GHC BSTC
        '15': p('B'), '16': p('GHB_D'), '17': p('BSTB'),    # SHB GHB BSTB
        '18': p('A'), '19': p('GHA_D'), '20': p('BSTA'),    # SHA GHA BSTA
        '21': None,                                         # DT open: 215 ns
        '22': p('HA'), '23': p('HB'), '24': p('HC'),        # INHA..C
        '25': GND,                                          # exposed pad
    }, B, 'ESC %d gate driver' % n, ref='U_D%d' % n)
    cap('C10U_25', 'GVDD', GND, B, 'driver %d GVDD' % n)

    for ph in 'ABC':
        cap('C1U_25', p('BST' + ph), p(ph), B, 'bootstrap ' + ph)
        # Gate resistors 22 ohm high side, 10 ohm low side
        # (sim/halfbridge/options.py): the high side's slower turn-on is
        # what keeps the low side's drain under 40 V when it switches
        # (32 V at 15 A with a 2 nH loop, 39 V at a 30 A / 4 nH abuse
        # case, braking included), with no snubber parts.  The switch node
        # slews at most 1.85 V/ns (10-90 %), inside the DRV8300D's 2 V/ns.
        res('R22R_0201', p('GH%s_D' % ph), p('GH' + ph), B, 'gate high ' + ph)
        res('R10R_0201', p('GL%s_D' % ph), p('GL' + ph), B, 'gate low ' + ph)
        # Half-bridge of two Toshiba TPN2R304PL (40 V, 2.3 mOhm at 10 V):
        # pads 1-3 source, 4 gate, 5-8 and the tab (9) drain.  The low
        # side's source goes to the channel's sense node, which returns to
        # ground through the shunt.
        add('Q', 'TPN2R304PL', {'1': p(ph), '2': p(ph), '3': p(ph), '4': p('GH' + ph),
                                '5': 'VBAT', '6': 'VBAT', '7': 'VBAT', '8': 'VBAT', '9': 'VBAT'},
            B, 'high side ' + ph, ref='Q%d%sH' % (n, ph))
        add('Q', 'TPN2R304PL', {'1': p('SRC'), '2': p('SRC'), '3': p('SRC'), '4': p('GL' + ph),
                                '5': p(ph), '6': p(ph), '7': p(ph), '8': p(ph), '9': p(ph)},
            B, 'low side ' + ph, ref='Q%d%sL' % (n, ph))
        # Bridge decoupling, VBAT to the sense node: the switching loop
        # closes through the board, on the bridge side of the shunt.
        cap('C4U7_50', 'VBAT', p('SRC'), B, 'bridge ' + ph)
        # Back-EMF divider 10k / 2.2k (ratio 5.5): a full 4S HV pack
        # (17.4 V) reads 3.14 V, inside VDDA.  The 10k is an 0402 (50 V):
        # it sees the switch node.
        res('R10K', p(ph), p('CMP_' + ph), B, 'BEMF top ' + ph)
        res('R2K2_0201', p('CMP_' + ph), GND, B, 'BEMF bottom ' + ph)
        # Virtual neutral: 10k from each divided phase to a star at PA3.
        # The star sits at the mean of the three divided phases, so
        # CMP - NEUTRAL crosses zero where the phase crosses the mean of
        # the three, as a star of the phases themselves would.
        res('R10K_0201', p('CMP_' + ph), p('NEUTRAL'), B, 'neutral ' + ph)

    # Current: 0.5 mOhm Kelvin shunt (Stackpole HCS1206, 2 W) from the sense
    # node to ground, read by an INA186A3 (100 V/V): 50 mV/A at IOUT.
    # 1.5k / 1k makes that 20 mV/A at PA5, AM32 GEN_64K_G071's
    # MILLIVOLT_PER_AMP, and with the 100 nF (600 ohm source) a 2.65 kHz
    # filter.  0.11 W in
    # the shunt at 15 A.  Pads 3 and 4 are the shunt's Kelvin sense pads
    # (net-tied to 1 and 2): the amplifier reads the resistor, not the
    # copper carrying the current.
    add('R', 'SHUNT_0M5', {'1': p('SRC'), '2': GND, '3': p('SNSP'), '4': p('SNSN')}, B,
        'ESC %d shunt' % n, ref='R_S%d' % n)
    # INA186 DCK: 1 REF, 2 GND, 3 VS, 4 IN+, 5 IN-, 6 OUT.
    add('U', 'INA186A3', {'1': GND, '2': GND, '3': '+3V3E', '4': p('SNSP'), '5': p('SNSN'), '6': p('IOUT')},
        B, 'ESC %d current amplifier' % n, ref='U_A%d' % n)
    cap('C100N_0201', '+3V3E', GND, B, 'U_A%d supply' % n)
    res('R1K5_0201', p('IOUT'), p('ISENSE'), B, 'current divider top')
    res('R1K_0201', p('ISENSE'), GND, B, 'current divider bottom')
    cap('C100N_0201', p('ISENSE'), GND, B, 'current filter')
    res('R10K_0201', p('IOUT'), 'CUR', B, 'battery current average %d' % n)

    # Battery voltage for AM32: 100k / 10k, ratio 11 (TARGET_VOLTAGE_DIVIDER
    # 110).  One divider per channel keeps the channel self-contained.
    res('R100K', 'VBAT', p('VSENSE'), B, 'ESC %d vsense top' % n)
    res('R10K_0201', p('VSENSE'), GND, B, 'ESC %d vsense bottom' % n)
    # the divider is a 9.1 kohm source: the 100 nF lets the G071's ADC read
    # it correctly at any sampling time (sim/sense)
    cap('C100N_0201', p('VSENSE'), GND, B, 'ESC %d vsense filter' % n)

    # The flight controller's motor output, straight in.
    for ph in 'ABC':
        add('P', 'PAD_MOTOR', {'1': p(ph)}, B, 'motor %d phase %s' % (n, ph), ref='P_M%d%s' % (n, ph))
    # SWD, for the one-time AM32 bootloader flash.
    add('TP', 'PAD_TP', {'1': p('SWDIO')}, B, 'ESC %d SWDIO' % n, ref='TP_D%d' % n)
    add('TP', 'PAD_TP', {'1': p('SWCLK')}, B, 'ESC %d SWCLK' % n, ref='TP_C%d' % n)

def mounting():
    for i in range(1, 5):
        add('H', 'HOLE', {}, 'mech', 'M2 soft-mount grommet hole', ref='H%d' % i)

def build():
    COMPS.clear(); _counts.clear(); _roles.clear()
    CHANNEL[0] = 0
    power(); fc()
    for n in (1, 2, 3, 4):
        CHANNEL[0] = n
        esc(n)
    CHANNEL[0] = 0
    add('TP', 'PAD_TP', {'1': '+3V3E'}, 'power', 'SWD 3.3 V (ESC rail)', ref='TP_3V3')
    add('TP', 'PAD_TP', {'1': GND}, 'power', 'SWD ground', ref='TP_GND')
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
    cs = build()
    ns = nets(cs)
    print('%d components (%d assembled), %d nets' % (
        len(cs), sum(1 for c in cs if c.part in parts.PARTS), len(ns)))
    missing = sorted({c.part for c in cs if c.part not in allp})
    print('missing parts:', missing)
    for n, members in sorted(ns.items()):
        if len(members) < 2:
            print('  single-pin net:', n, members)
