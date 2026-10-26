# -*- coding: utf-8 -*-
"""The circuit: every component and every connection of the three boards,
as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects
to, with the reason for anything that is not obvious.  Pin numbers are
footprint pad numbers, which for every part here are the datasheet pin
numbers (the USB-C receptacle's pads are named by contact).  A pin given
as None is deliberately left open.

LayerCam is three boards in Prusa's Buddy3D camera housing:

    USB board   USB-C (5 V and USB 2.0 for flashing) -> ESD -> 6-wire cable
    main board  5 V -> four bucks -> RV1106G3 (Linux, ISP, H.264)
                SPI NAND (256 MB), AP6256 Wi-Fi over SDIO, U.FL antenna
                FFC to the SC3336 camera module, H-bridge for its IR-cut
                IR LED switch and light-sensor input for the ring
    LED ring    six 850 nm LEDs in three strings, a light sensor

The RV1106 pin plan follows Luckfox's RV1106 boards (the SDK's device
trees), checked pin by pin against the RV1106 datasheet Rev 2.2
(docs/rv1106_pins.md).  The firmware's device tree (firmware/dts/) is
checked against this file by src/verify.py.
"""


class Comp:
    def __init__(self, ref, part, pins, block, note='', side='F'):
        self.ref, self.part, self.pins, self.block, self.note, self.side = ref, part, pins, block, note, side


COMPS = []
_count = {}
# the references given by hand on each board, which the automatic numbering
# skips (filled by build())
RESERVED = set()
GND = 'GND'
BOARDS = ('main', 'ring', 'usb')


def add(prefix, part, pins, block, note='', ref=None):
    if ref is None:
        # the next free number: parts given a number by hand keep theirs
        used = {c.ref for c in COMPS} | RESERVED
        while True:
            _count[prefix] = _count.get(prefix, 0) + 1
            ref = '%s%d' % (prefix, _count[prefix])
            if ref not in used:
                break
    elif ref in {c.ref for c in COMPS}:
        raise ValueError('reference %s used twice' % ref)
    c = Comp(ref, part, dict(pins), block, note)
    COMPS.append(c)
    return c


def cap(part, a, b, block, note=''):
    return add('C', part, {'1': a, '2': b}, block, note)


def res(part, a, b, block, note=''):
    return add('R', part, {'1': a, '2': b}, block, note)


# The 6-wire cable between the USB board and the main board.  Symmetric:
# a cable that turns the connector round swaps only D+ and D- (USB then
# fails to enumerate, nothing is damaged).  Two contacts each for 5 V and
# ground (an SH contact is rated 1 A).
USB_CABLE = {'1': 'VSYS', '2': GND, '3': 'USB_DM', '4': 'USB_DP', '5': GND, '6': 'VSYS'}
# The 6-wire cable between the main board and the LED ring, symmetric the
# same way: turned round, the light sensor's supply and output swap, and a
# 1 k resistor on the main board limits what flows (the sensor's
# emitter-collector rating is 1.5 V).
RING_CABLE = {'1': 'VSYS', '2': 'LED_K', '3': 'ALS_VCC', '4': 'ALS', '5': 'LED_K', '6': 'VSYS'}


# =====================================================================
#  MAIN BOARD
# =====================================================================
def main_power():
    B = 'power'
    # 5 V in from the USB board.  Its TVS is at the USB-C; here the bulk.
    add('J', 'SH6V', dict(USB_CABLE, **{'7': GND, '8': GND}), B, 'USB cable', ref='J1')
    cap('C10U', 'VSYS', GND, B, '5 V bulk')
    cap('C10U', 'VSYS', GND, B, '5 V bulk')
    cap('C100N', 'VSYS', GND, B, '5 V HF')
    # USB OTG VBUS detect: 5 V -> 10k / 18k -> 3.2 V at the pin (Luckfox)
    res('R10K', 'VSYS', 'USB_VBUSDET', B, 'VBUS detect top')
    res('R18K', 'USB_VBUSDET', GND, B, 'VBUS detect bottom')
    cap('C100N', 'USB_VBUSDET', GND, B, 'VBUS detect filter')

    # Power-up order, as every Luckfox RV1106 board: 0.9 V core first, then
    # 1.8 V and the DDR together, then 3.3 V last; RC delays on the enables
    # (EN threshold 1.4 V from 5 V: 0.33 RC).  0.9 V: enable tied to 5 V.
    #   TLV62569 (U2): 1 EN, 2 GND, 3 SW, 4 VIN, 5 FB; 0.6 V reference.
    #   VDD_0V9 = 0.6 x (1 + 47k / 100k) = 0.882 V (CPU, logic, NPU;
    #   0.85-0.95 V; Luckfox's value; 2 A for the 1.21 A measured peak)
    add('U', 'TLV62569', {'1': 'VSYS', '2': GND, '3': 'SW_0V9', '4': 'VSYS', '5': 'FB_0V9'}, B,
        '0.9 V buck', ref='U2')
    cap('C10U', 'VSYS', GND, B, '0.9 V buck input')
    add('L', 'L2U2', {'1': 'SW_0V9', '2': 'VDD_0V9'}, B, '0.9 V inductor', ref='L1')
    res('R47K', 'VDD_0V9', 'FB_0V9', B, '0.9 V feedback top')
    res('R100K', 'FB_0V9', GND, B, '0.9 V feedback bottom')
    cap('C22U', 'VDD_0V9', GND, B, '0.9 V output')
    cap('C22U', 'VDD_0V9', GND, B, '0.9 V output')

    # EA3036C (U3): three 1 A bucks.  CH1 3.3 V (last), CH2 1.36 V DDR3L,
    # CH3 1.8 V.  0.6 V reference.
    #   3.3 V  = 0.6 x (1 + 100k / 22k)  = 3.327 V (VCCIO 3.0-3.465 V)
    #   DDR    = 0.6 x (1 + 127k / 100k) = 1.362 V (DDR3L 1.283-1.45 V)
    #   1.8 V  = 0.6 x (1 + 200k / 100k) = 1.800 V
    add('U', 'EA3036C', {'1': GND, '2': 'FB_1V8', '3': 'FB_DDR', '4': GND, '5': GND, '6': 'LX_DDR',
                         '7': 'VSYS', '8': 'EN_MID', '9': 'EN_3V3', '10': 'VSYS', '11': 'LX_3V3', '12': GND,
                         '13': GND, '14': 'FB_3V3', '15': GND, '16': 'VSYS', '17': GND, '18': 'EN_MID',
                         '19': 'VSYS', '20': 'LX_1V8', '21': GND}, B, 'triple buck', ref='U3')
    for _ in range(3):
        cap('C10U', 'VSYS', GND, B, 'triple buck input')
    cap('C1U', 'VSYS', GND, B, 'triple buck VCC')
    # enables: 1.8 V + DDR at 100k x 100 nF (3.3 ms), 3.3 V at 200k x 100 nF
    res('R100K', 'VSYS', 'EN_MID', B, '1.8 V / DDR enable delay R')
    cap('C100N', 'EN_MID', GND, B, '1.8 V / DDR enable delay C')
    res('R200K', 'VSYS', 'EN_3V3', B, '3.3 V enable delay R')
    cap('C100N', 'EN_3V3', GND, B, '3.3 V enable delay C')
    add('L', 'L1U5', {'1': 'LX_3V3', '2': 'VCC_3V3'}, B, '3.3 V inductor', ref='L2')
    res('R100K', 'VCC_3V3', 'FB_3V3', B, '3.3 V feedback top')
    res('R22K', 'FB_3V3', GND, B, '3.3 V feedback bottom')
    cap('C22U', 'VCC_3V3', GND, B, '3.3 V output')
    cap('C22U', 'VCC_3V3', GND, B, '3.3 V output')
    add('L', 'L1U5', {'1': 'LX_DDR', '2': 'VCC_DDR'}, B, 'DDR inductor', ref='L3')
    res('R127K', 'VCC_DDR', 'FB_DDR', B, 'DDR feedback top')
    res('R100K', 'FB_DDR', GND, B, 'DDR feedback bottom')
    cap('C22U', 'VCC_DDR', GND, B, 'DDR output')
    add('L', 'L1U5', {'1': 'LX_1V8', '2': 'VCC_1V8'}, B, '1.8 V inductor', ref='L4')
    res('R200K', 'VCC_1V8', 'FB_1V8', B, '1.8 V feedback top')
    res('R100K', 'FB_1V8', GND, B, '1.8 V feedback bottom')
    cap('C22U', 'VCC_1V8', GND, B, '1.8 V output')

    # The Wi-Fi module's own 3.3 V (U4): it draws 1 A peaks when it
    # transmits, which must not dip the SoC's rails.
    #   3.3 V = 0.6 x (1 + 100k / 22k) = 3.327 V (VBAT 3.2-4.8 V)
    add('U', 'TLV62569', {'1': 'VSYS', '2': GND, '3': 'SW_WIFI', '4': 'VSYS', '5': 'FB_WIFI'}, B,
        'Wi-Fi buck', ref='U4')
    cap('C10U', 'VSYS', GND, B, 'Wi-Fi buck input')
    add('L', 'L2U2', {'1': 'SW_WIFI', '2': 'VWIFI'}, B, 'Wi-Fi inductor', ref='L5')
    res('R100K', 'VWIFI', 'FB_WIFI', B, 'Wi-Fi feedback top')
    res('R22K', 'FB_WIFI', GND, B, 'Wi-Fi feedback bottom')
    cap('C22U', 'VWIFI', GND, B, 'Wi-Fi buck output')
    cap('C22U', 'VWIFI', GND, B, 'Wi-Fi buck output')


def main_soc():
    B = 'soc'
    # RV1106G3 (U1), every pin.  Supplies and their decoupling follow the
    # Luckfox Pico Pro/Max ("close to power pin").
    p = {
        '1': 'VCC_1V8_MIPI',    # MIPI_AVDD1V8 / VCCIO7: 1.8 V only, 1R + 100 nF
        '2': 'CAM_MCLK_SOC',    # MIPI_CLK0_OUT (GPIO3_C4): sensor clock, 22R
        '3': 'CAM_RST',         # GPIO3_C5: sensor reset/powerdown
        '4': None,              # GPIO3_C6 (1.8 V): unused
        '5': 'CAM_SCL',         # I2C4_SCL_M2
        '6': None,
        '7': 'CAM_SDA',         # I2C4_SDA_M2
        '8': None, '9': None,
        '10': 'VDD_0V9',        # DVDD_1
        '11': 'SD_DET',         # SDMMC0_DET: 10k to ground (SDIO card always present)
        '12': 'SD_D1', '13': 'VCC_3V3',   # VCCIO4 = 3.3 V (the Wi-Fi's SDIO)
        '14': 'SD_D0', '15': 'SD_CLK_SOC', '16': 'SD_CMD', '17': 'SD_D3', '18': 'SD_D2',
        '19': 'VCC_RTC',        # RTC_AVDD3V3: 3.3 V through 100R, 1 uF
        '20': 'RTC_XOUT', '21': 'RTC_XIN',
        '22': 'ALS',            # SARADC_IN1: the ring's light sensor, 0-1.8 V
        '23': 'BOOT_KEY',       # SARADC_IN0: the button (MaskROM at power-up, a user key after)
        '24': 'VCC_1V8_ADC',    # SARADC_USB_AVDD1V8: 1R + 100 nF
        '25': 'USB_VBUSDET', '26': 'USB_DM', '27': 'USB_DP',
        '28': 'VCC_3V3',        # USB_AVDD3V3
        '29': None,             # codec unused (LINEOUT)
        '30': 'CODEC_VCM',      # 4.7 uF, as Luckfox
        '31': 'VCC_1V8_CODEC',  # CODEC_AVDD1V8: bead
        '32': None, '33': None, '34': None, '35': None, '36': None,
        '37': GND,              # CODEC_AVSS
        '38': None,
        '39': 'NAND_IO3', '40': None, '41': 'NAND_IO0', '42': 'NAND_IO1',
        '43': 'VCC_3V3',        # VCCIO3 = 3.3 V (flash)
        '44': 'NAND_IO2', '45': None, '46': None,
        '47': 'NAND_CS', '48': 'NAND_CLK_SOC',
        '49': 'VCC_DDR', '50': 'VCC_DDR',
        '51': 'VDD_0V9',
        '52': 'DRAM_ZQ',        # 240R 1 % to ground
        '53': 'VCC_1V8',        # DDR_PLL_AVDD1V8
        '54': 'VDD_0V9', '55': 'VDD_0V9',
        '56': 'VCC_DDR',
        '57': GND,              # TVSS
        '58': None,             # RTC_CLKO: not used (the Wi-Fi gets its own 32 kHz oscillator)
        '59': 'BT_REG_ON',      # GPIO0_A1
        '60': 'BT_WAKE',        # GPIO0_A2
        '61': 'VCC_3V3',        # PMU_VCC3V3
        '62': 'WL_HOST_WAKE',   # GPIO0_A3 (PMU domain, can wake the SoC)
        '63': 'BT_HOST_WAKE',   # GPIO0_A4
        '64': 'BT_RTS',         # UART1_RTS_M0
        '65': 'BT_CTS',         # UART1_CTS_M0
        '66': 'NPOR',
        '67': 'VDD_0V9',        # PMU_DVDD0V9
        '68': 'XIN_24M', '69': 'XOUT_24M',
        '70': 'VCC_1V8',        # OSC/PLL_AVDD1V8
        '71': 'VDD_0V9',        # OSC_PLL_DVDD
        '72': 'IRCUT_A',        # GPIO1_A0: H-bridge IN1 (pulled down inside: bridge off at reset)
        '73': 'IRCUT_B',        # GPIO1_A1: H-bridge IN2
        '74': 'WL_REG_ON',      # GPIO1_A2
        '75': 'BT_TXD',         # UART1_TX_M0
        '76': 'BT_RXD',         # UART1_RX_M0
        '77': 'IR_PWM',         # PWM3_IR_M1: the IR LED switch
        '78': None,
        '79': 'DBG_TX', '80': 'DBG_RX',   # UART2_M1, the kernel console, 115200
        '81': 'VCC_3V3',        # VCCIO1
        '82': 'VDD_0V9',
        '83': None, '84': None, '85': None, '86': None, '87': None,
        '88': 'VCC_3V3',        # VCCIO6
        '89': None, '90': None, '91': None, '92': None, '93': None, '94': None,
        '95': 'LED_STATUS',     # GPIO1_C0 (3.3 V)
        '96': 'VCC_1V8_OTP',    # OTP/ETH/TSADC_AVDD1V8: bead
        '97': None, '98': None, '99': None, '100': None,  # Ethernet PHY unused
        '101': 'VCC_3V3_ETH',   # ETH_AVDD3V3: bead (kept powered, as Luckfox)
        '102': 'ETH_EXTR',      # bias resistor to ground
        '103': 'VDD_0V9',
        '104': None, '105': None, '106': None, '107': None,
        '108': 'VCC_3V3',       # VCCIO5
        '109': None, '110': None, '111': None, '112': None, '113': None, '114': None,
        '115': 'VDD_0V9',       # CPU_DVDD: tied to the 0.9 V rail, as every Luckfox RV1106 board
        '116': 'VDD_0V9',
        '117': None, '118': None, '119': None, '120': None, '121': None, '122': None,  # lanes 2/3, CK1
        '123': 'CSI_D1N', '124': 'CSI_D1P', '125': 'CSI_CKN', '126': 'CSI_CKP',
        '127': 'CSI_D0N', '128': 'CSI_D0P',
        '129': GND,             # exposed pad: ground and the main heat path
    }
    add('U', 'RV1106G3', p, B, 'SoC', ref='U1')

    # supplies at the pins
    for _ in range(6):
        cap('C100N', 'VDD_0V9', GND, B, 'core decoupling')
    for _ in range(3):
        cap('C1U', 'VDD_0V9', GND, B, 'core decoupling')
    for _ in range(3):
        cap('C10U', 'VDD_0V9', GND, B, 'core bulk')
    for _ in range(3):
        cap('C100N', 'VCC_DDR', GND, B, 'DDR decoupling')
    cap('C1U', 'VCC_DDR', GND, B, 'DDR decoupling')
    cap('C10U', 'VCC_DDR', GND, B, 'DDR bulk')
    cap('C10U', 'VCC_DDR', GND, B, 'DDR bulk')
    for _ in range(3):
        cap('C100N', 'VCC_1V8', GND, B, '1.8 V decoupling (DDR PLL, OSC/PLL)')
    cap('C1U', 'VCC_1V8', GND, B, '1.8 V decoupling (DDR PLL)')
    for _ in range(6):
        cap('C100N', 'VCC_3V3', GND, B, '3.3 V decoupling (VCCIO, PMU, USB)')
    cap('C10U', 'VCC_3V3', GND, B, '3.3 V bulk at the SoC')
    res('R1R', 'VCC_1V8', 'VCC_1V8_MIPI', B, 'MIPI supply filter R')
    cap('C100N', 'VCC_1V8_MIPI', GND, B, 'MIPI supply filter C')
    cap('C1U', 'VCC_1V8_MIPI', GND, B, 'MIPI supply bulk')
    res('R1R', 'VCC_1V8', 'VCC_1V8_ADC', B, 'ADC/USB supply filter R')
    cap('C100N', 'VCC_1V8_ADC', GND, B, 'ADC/USB supply filter C')
    add('L', 'BEAD', {'1': 'VCC_1V8', '2': 'VCC_1V8_CODEC'}, B, 'codec supply bead')
    cap('C1U', 'VCC_1V8_CODEC', GND, B, 'codec supply')
    cap('C4U7', 'CODEC_VCM', GND, B, 'codec VCM')
    add('L', 'BEAD', {'1': 'VCC_1V8', '2': 'VCC_1V8_OTP'}, B, 'OTP/TSADC supply bead')
    cap('C100N', 'VCC_1V8_OTP', GND, B, 'OTP/TSADC supply')
    add('L', 'BEAD', {'1': 'VCC_3V3', '2': 'VCC_3V3_ETH'}, B, 'Ethernet supply bead')
    cap('C100N', 'VCC_3V3_ETH', GND, B, 'Ethernet supply')
    res('R6K2', 'ETH_EXTR', GND, B, 'Ethernet bias (PHY unused)')
    res('R240R', 'DRAM_ZQ', GND, B, 'DRAM ZQ 240R 1 %')
    res('R100R', 'VCC_3V3', 'VCC_RTC', B, 'RTC supply R')
    cap('C1U', 'VCC_RTC', GND, B, 'RTC supply C')

    # 24 MHz: XOUT -> 22R -> crystal; 18 pF each side; 1M across (Luckfox).
    # Crystal: 1 OSC1, 2 GND, 3 OSC2, 4 GND.
    res('R22R', 'XOUT_24M', 'XOUT_24M_X', B, '24 MHz drive R')
    add('Y', 'XTAL24M', {'1': 'XIN_24M', '2': GND, '3': 'XOUT_24M_X', '4': GND}, B, '24 MHz crystal', ref='Y1')
    cap('C18P', 'XIN_24M', GND, B, '24 MHz load')
    cap('C18P', 'XOUT_24M_X', GND, B, '24 MHz load')
    res('R1M', 'XIN_24M', 'XOUT_24M_X', B, '24 MHz bias')
    # 32.768 kHz RTC crystal (12.5 pF: 2 x (12.5 - 3) = 19 -> 18 pF)
    add('Y', 'XTAL32K', {'1': 'RTC_XIN', '2': 'RTC_XOUT'}, B, 'RTC crystal', ref='Y2')
    cap('C18P', 'RTC_XIN', GND, B, 'RTC load')
    cap('C18P', 'RTC_XOUT', GND, B, 'RTC load')

    # reset: 1k up, 10 nF down (the SoC has its own power-on reset)
    res('R1K', 'NPOR', 'VCC_3V3', B, 'nPOR pull-up')
    cap('C10N', 'NPOR', GND, B, 'nPOR delay')

    # the button: SARADC_IN0, 10k up to 1.8 V, 1 nF, 100R to the switch.
    # Held while the camera powers up: MaskROM (flashing over USB).  After
    # boot: the setup key (firmware/README.md).  The switch sits at the
    # housing's round edge, under Prusa's printed flex key.
    res('R10K', 'BOOT_KEY', 'VCC_1V8', B, 'button pull-up')
    cap('C1N', 'BOOT_KEY', GND, B, 'button filter')
    res('R100R', 'BOOT_KEY', 'BOOT_SW', B, 'button series R')
    add('SW', 'BTN_SIDE', {'1': 'BOOT_SW', '2': GND, '3': None, '4': None}, B, 'button', ref='SW1')

    # status LED, 3.3 V GPIO, 1k (1.3 mA: plenty for an indicator)
    res('R1K', 'LED_STATUS', 'LED_STATUS_A', B, 'status LED R')
    add('LED', 'LED_GRN', {'1': GND, '2': 'LED_STATUS_A'}, B, 'status LED', ref='LED1')

    # kernel console test pads
    add('TP', 'TP', {'1': 'DBG_TX'}, B, 'console TX', ref='TP1')
    add('TP', 'TP', {'1': 'DBG_RX'}, B, 'console RX', ref='TP2')
    add('TP', 'TP', {'1': GND}, B, 'console ground', ref='TP3')
    add('TP', 'TP', {'1': 'VSYS'}, B, '5 V', ref='TP4')


def main_storage():
    B = 'storage'
    # W25N02KV (U5): 1 /CS, 2 DO(IO1), 3 /WP(IO2), 4 GND, 5 DI(IO0), 6 CLK,
    # 7 /HOLD(IO3), 8 VCC, 9 pad.  Quad SPI; 22R in the clock at the SoC;
    # /WP and /HOLD pulled up (Luckfox Pro/Max).
    add('U', 'W25N02KV', {'1': 'NAND_CS', '2': 'NAND_IO1', '3': 'NAND_IO2', '4': GND, '5': 'NAND_IO0',
                          '6': 'NAND_CLK', '7': 'NAND_IO3', '8': 'VCC_3V3', '9': GND}, B, 'SPI NAND', ref='U5')
    res('R22R', 'NAND_CLK_SOC', 'NAND_CLK', B, 'NAND clock series R')
    res('R10K', 'NAND_IO2', 'VCC_3V3', B, 'NAND /WP pull-up')
    res('R10K', 'NAND_IO3', 'VCC_3V3', B, 'NAND /HOLD pull-up')
    cap('C100N', 'VCC_3V3', GND, B, 'NAND decoupling')
    cap('C1U', 'VCC_3V3', GND, B, 'NAND decoupling')


def main_wifi():
    B = 'wifi'
    # AP6256 (U6), AMPAK datasheet pin assignment.  SDIO at 3.3 V
    # (SDIO_VSEL low), out-of-band interrupt on WL_HOST_WAKE, Bluetooth on
    # UART1 with flow control.  The 37.4 MHz crystal and the 32.768 kHz
    # sleep clock are external (as on Radxa's ROCK 4C+, same BCM43456).
    w = {
        '1': GND, '2': 'ANT_FEED', '3': GND, '4': None, '5': None,
        '6': 'BT_WAKE', '7': 'BT_HOST_WAKE', '8': None,
        '9': 'VWIFI',           # VBAT
        '10': 'XTAL37_IN', '11': 'XTAL37_OUT',
        '12': 'WL_REG_ON', '13': 'WL_HOST_WAKE',
        '14': 'SD_D2', '15': 'SD_D3', '16': 'SD_CMD', '17': 'SD_CLK', '18': 'SD_D0', '19': 'SD_D1',
        '20': GND,
        '21': 'WIFI_LX',        # VIN_LDO_OUT: the module's own buck, 4.7 uH to VIN_LDO
        '22': 'VCC_3V3',        # VDDIO
        '23': 'WIFI_VLDO',      # VIN_LDO
        '24': 'WIFI_LPO',
        '25': None, '26': None, '27': None, '28': None,   # PCM unused
        '29': GND,              # SDIO_VSEL: low = 3.3 V I/O
        '30': None, '31': GND, '32': None, '33': GND,
        '34': 'BT_REG_ON', '35': None, '36': GND,
        '37': None, '38': None, '39': None, '40': None,
        '41': 'BT_CTS',         # module RTS -> SoC CTS
        '42': 'BT_RXD',         # module TXD -> SoC RXD
        '43': 'BT_TXD',         # module RXD <- SoC TXD
        '44': 'BT_RTS',         # module CTS <- SoC RTS
        '45': None, '46': None, '47': None,   # test points
    }
    add('U', 'AP6256', w, B, 'Wi-Fi module', ref='U6')
    cap('C22U', 'VWIFI', GND, B, 'Wi-Fi VBAT bulk')
    cap('C100N', 'VWIFI', GND, B, 'Wi-Fi VBAT HF')
    cap('C100N', 'VCC_3V3', GND, B, 'Wi-Fi VDDIO')
    add('L', 'L4U7', {'1': 'WIFI_LX', '2': 'WIFI_VLDO'}, B, 'Wi-Fi internal buck inductor', ref='L6')
    cap('C10U', 'WIFI_VLDO', GND, B, 'Wi-Fi internal buck output')
    # 37.4 MHz, 12 pF crystal, 12 pF caps (ROCK 4C+)
    add('Y', 'XTAL37M4', {'1': 'XTAL37_IN', '2': GND, '3': 'XTAL37_OUT', '4': GND}, B, '37.4 MHz crystal',
        ref='Y3')
    cap('C12P', 'XTAL37_IN', GND, B, '37.4 MHz load')
    cap('C12P', 'XTAL37_OUT', GND, B, '37.4 MHz load')
    # sleep clock: 1 OUT, 2 GND, 3 OE (high = on), 4 VDD
    add('Y', 'OSC32K', {'1': 'WIFI_LPO', '2': GND, '3': 'VCC_3V3', '4': 'VCC_3V3'}, B, '32 kHz oscillator',
        ref='Y4')
    cap('C100N', 'VCC_3V3', GND, B, '32 kHz oscillator supply')
    # SDIO: 22R in the clock at the SoC, 10k pull-ups on CMD and data
    res('R22R', 'SD_CLK_SOC', 'SD_CLK', B, 'SDIO clock series R')
    for n in ('SD_CMD', 'SD_D0', 'SD_D1', 'SD_D2', 'SD_D3'):
        res('R10K', n, 'VCC_3V3', B, 'SDIO pull-up')
    res('R10K', 'SD_DET', GND, B, 'SDIO card-detect to ground')
    # power-on controls held low until Linux raises them
    res('R100K', 'WL_REG_ON', GND, B, 'WL_REG_ON pull-down')
    res('R100K', 'BT_REG_ON', GND, B, 'BT_REG_ON pull-down')
    # antenna: 50 ohm feed -> pi match (0R through, both shunts empty until
    # tuned) -> U.FL.  An external 2.4/5 GHz flex antenna on a pigtail, as
    # Prusa's camera.
    add('C', 'DNP_C0402', {'1': 'ANT_FEED', '2': GND}, B, 'antenna match shunt 1 (empty)')
    res('R0R', 'ANT_FEED', 'ANT', B, 'antenna match series')
    add('C', 'DNP_C0402', {'1': 'ANT', '2': GND}, B, 'antenna match shunt 2 (empty)')
    add('J', 'UFL', {'1': 'ANT', '2': GND, '3': GND}, B, 'antenna', ref='J5')


def main_camera():
    B = 'camera'
    # The SC3336 module's 20-pin FFC (Luckfox pinout, module side):
    #   1 GND, 2 MCLK, 3 GND, 4 D0P, 5 D0N, 6 GND, 7 CLKP, 8 CLKN, 9 GND,
    #   10 D1P, 11 D1N, 12 GND, 13 SCL, 14 SDA, 15 GND, 16 RESET, 17 GND,
    #   18 GND, 19 3.3 V, 20 3.3 V
    # The module's connector and ours face each other across the module's
    # edge, so a straight cable lands module pin k on our pin 21 - k:
    # CAM_PIN_FLIP.  layout.py places the connector that way and
    # verify.py checks every contact against the module's, by position.
    module = {1: GND, 2: 'CAM_MCLK', 3: GND, 4: 'CSI_D0P', 5: 'CSI_D0N', 6: GND, 7: 'CSI_CKP', 8: 'CSI_CKN',
              9: GND, 10: 'CSI_D1P', 11: 'CSI_D1N', 12: GND, 13: 'CAM_SCL', 14: 'CAM_SDA', 15: GND,
              16: 'CAM_RST', 17: GND, 18: GND, 19: 'VCC_3V3', 20: 'VCC_3V3'}
    pins = {str(21 - k if CAM_PIN_FLIP else k): n for k, n in module.items()}
    pins.update({'21': GND, '22': GND})
    add('J', 'FPC20', pins, B, 'camera FFC', ref='J2')
    res('R22R', 'CAM_MCLK_SOC', 'CAM_MCLK', B, 'sensor clock series R')
    res('R4K7', 'CAM_SCL', 'VCC_1V8', B, 'camera I2C pull-up')
    res('R4K7', 'CAM_SDA', 'VCC_1V8', B, 'camera I2C pull-up')
    cap('C10U', 'VCC_3V3', GND, B, 'camera supply')
    cap('C100N', 'VCC_3V3', GND, B, 'camera supply')

    # IR-cut filter: DRV8837 (U7) 1 VM, 2 OUT1, 3 OUT2, 4 GND, 5 IN2, 6 IN1,
    # 7 nSLEEP, 8 VCC, 9 pad.  3.3 V across the 20 ohm coil (Commonlands:
    # 3.3 V for 100-500 ms); the driver pulses it.  IN1 and IN2 have
    # pull-downs inside: the bridge is off until Linux drives it.
    add('U', 'DRV8837', {'1': 'VCC_3V3', '2': 'IRCUT_1', '3': 'IRCUT_2', '4': GND, '5': 'IRCUT_B',
                         '6': 'IRCUT_A', '7': 'VCC_3V3', '8': 'VCC_3V3', '9': GND}, B, 'IR-cut driver',
        ref='U7')
    cap('C1U', 'VCC_3V3', GND, B, 'IR-cut driver VM')
    cap('C100N', 'VCC_3V3', GND, B, 'IR-cut driver VCC')
    # the holder's lead: red (pin 1) positive opens the filter (night)
    add('J', 'PB2R', {'1': 'IRCUT_1', '2': 'IRCUT_2', '3': GND, '4': GND}, B, 'IR-cut connector', ref='J3')

    # IR LEDs on the ring: their strings run from 5 V to LED_K; this
    # MOSFET (Q1: 1 G, 2 S, 3 D) switches LED_K to ground, PWM-dimmed.
    add('Q', 'AO3400A', {'1': 'IR_GATE', '2': GND, '3': 'LED_K'}, B, 'IR LED switch', ref='Q1')
    res('R100R', 'IR_PWM', 'IR_GATE', B, 'IR LED gate R')
    res('R100K', 'IR_GATE', GND, B, 'IR LED gate pull-down (off at reset)')
    # light sensor: the ring's phototransistor from ALS_VCC (1.8 V through
    # 1k) to ALS; 22k to ground here: about 0.5 V at 50 lux, 1.8 V (full
    # scale) from a few hundred lux.  The camera only needs dark vs light.
    res('R1K', 'VCC_1V8', 'ALS_VCC', B, 'light sensor supply R')
    res('R22K', 'ALS', GND, B, 'light sensor load')
    cap('C100N', 'ALS', GND, B, 'light sensor filter')
    add('J', 'SH6V', dict(RING_CABLE, **{'7': GND, '8': GND}), B, 'LED ring cable', ref='J4')
    cap('C10U', 'VSYS', GND, B, 'IR LED supply')


def main_mechanics():
    # four M2 screws into Prusa's bosses; the two M1.6 screws that clamp
    # camera module, board and IR-cut holder together
    for i in range(4):
        add('H', 'HOLE_M2', {}, 'mounting', 'M2 hole', ref='H%d' % (i + 1))
    for i in range(2):
        add('H', 'HOLE_M1V6', {}, 'mounting', 'lens holder screw', ref='H%d' % (i + 5))


# =====================================================================
#  LED RING
# =====================================================================
def ring():
    B = 'ring'
    add('J', 'SH6V', dict(RING_CABLE, **{'7': None, '8': None}), B, 'cable', ref='J1')
    # three strings of two LEDs: 5 V -> 39R -> LED -> LED -> LED_K.
    # (5.0 - 2 x 1.45) / 39 = 54 mA per string; 0.11 W in each 0.25 W
    # resistor.  IR LED: pad 1 anode, pad 2 cathode.
    for s in range(3):
        a, m = 'STR%d_A' % (s + 1), 'STR%d_M' % (s + 1)
        res('R39R_1206', 'VSYS', a, B, 'string %d resistor' % (s + 1))
        add('D', 'IRLED', {'1': a, '2': m}, B, 'IR LED %d' % (2 * s + 1))
        add('D', 'IRLED', {'1': m, '2': 'LED_K'}, B, 'IR LED %d' % (2 * s + 2))
    # light sensor behind the front window: TEMT6000 pads 1, 2 emitter,
    # pad 3 collector (Vishay drawing)
    add('Q', 'TEMT6000', {'1': 'ALS', '2': 'ALS', '3': 'ALS_VCC'}, B, 'light sensor', ref='Q1')


# =====================================================================
#  USB BOARD
# =====================================================================
def usb():
    B = 'usb'
    # USB-C: 5.1k Rd on each CC (a USB device: the printer's port gives
    # 5 V); both D+ and both D- contacts joined (either plug way round)
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'VSYS', 'B4A9': 'VSYS', 'A5': 'CC1', 'B5': 'CC2',
                      'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM', 'A8': None, 'B8': None,
                      '1': GND, '2': GND, '3': GND, '4': GND}, B, 'USB-C', ref='J1')
    res('R5K1', 'CC1', GND, B, 'CC1 Rd')
    res('R5K1', 'CC2', GND, B, 'CC2 Rd')
    # USBLC6: I/O1 = D- (pins 1, 6), I/O2 = D+ (pins 3, 4), flow-through
    add('U', 'USBLC6', {'1': 'USB_DM', '2': GND, '3': 'USB_DP', '4': 'USB_DP', '5': 'VSYS', '6': 'USB_DM'},
        B, 'USB ESD', ref='U1')
    add('D', 'SMF5V0', {'1': 'VSYS', '2': GND}, B, '5 V TVS', ref='D1')
    cap('C10U', 'VSYS', GND, B, '5 V at the connector')
    add('J', 'SH6R', dict(USB_CABLE, **{'7': GND, '8': GND}), B, 'cable', ref='J2')


# the camera FFC: True when the two connectors face each other (layout.py)
CAM_PIN_FLIP = False


def _hand_refs(board):
    import re, inspect
    fns = {'main': [main_power, main_soc, main_storage, main_wifi, main_camera, main_mechanics],
           'ring': [ring], 'usb': [usb]}[board]
    return {r for f in fns for r in re.findall(r"ref='([A-Z]+\d+)'", inspect.getsource(f))}


def build(board='main'):
    COMPS.clear(); _count.clear()
    RESERVED.clear(); RESERVED.update(_hand_refs(board))
    if board == 'main':
        main_power(); main_soc(); main_storage(); main_wifi(); main_camera(); main_mechanics()
    elif board == 'ring':
        ring()
    elif board == 'usb':
        usb()
    else:
        raise KeyError(board)
    return list(COMPS)


def nets(comps):
    out = {}
    for c in comps:
        for pad, net in c.pins.items():
            if net:
                out.setdefault(net, []).append((c.ref, pad))
    return out


if __name__ == '__main__':
    for b in BOARDS:
        cs = build(b)
        ns = nets(cs)
        print('%s: %d parts, %d nets' % (b, len(cs), len(ns)))
        for n, m in sorted(ns.items()):
            if len(m) < 2:
                print('   single-pin net', n, m)
