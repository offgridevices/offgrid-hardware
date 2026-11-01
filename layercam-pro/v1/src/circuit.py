# -*- coding: utf-8 -*-
"""The circuit: every component and every connection of the one board,
as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects
to, with the reason for anything that is not obvious.  Pin numbers are
footprint pad numbers, which for every part here are the datasheet pin
numbers (the USB-C receptacle's pads are named by contact; the image
sensor's balls by row and column).  A pin given as None is deliberately
left open.

LayerCam Pro is one board in a case with the outside of Prusa's Buddy3D
camera case:

    USB-C (5 V, and USB 2.0 for flashing) -> ESD, TVS
    5 V -> four bucks -> RV1106G3 (Linux, ISP, H.264), SPI NAND (256 MB)
    ESP32-C6 Wi-Fi module over SDIO (esp-hosted), its own 3.25 V buck
    SC4336H image sensor on the front face, its 2.8 V LDO, 2-lane MIPI
    H-bridge for the IR-cut holder; six 850 nm LEDs and their switch;
    the light sensor

LayerCam v1's main-board circuit is the starting point; what changed and
why is said where it changed.  The RV1106 pin plan follows Luckfox's RV1106
boards (the SDK's device trees); the Wi-Fi and sensor hookup and its
sources: docs/hookup.md.  The firmware's device tree (firmware/dts/) is
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
BOARDS = ('main',)


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


# =====================================================================
#  THE BOARD
# =====================================================================
def main_power():
    B = 'power'
    # 5 V from the USB-C (usb()); the bulk at the bucks
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
    #   VDD_0V9 = 0.6 x (1 + 51k / 100k) = 0.906 V (CPU, logic, NPU;
    #   0.85-0.95 V; 2 A for the 1.21 A measured peak).  Luckfox's 47k
    #   gives 0.882 V, whose low tolerance corner (0.859 V) leaves no room
    #   for a load step above 0.85 V (sim/power.md).
    add('U', 'TLV62569', {'1': 'VSYS', '2': GND, '3': 'SW_0V9', '4': 'VSYS', '5': 'FB_0V9'}, B,
        '0.9 V buck', ref='U2')
    cap('C10U', 'VSYS', GND, B, '0.9 V buck input')
    add('L', 'L2U2', {'1': 'SW_0V9', '2': 'VDD_0V9'}, B, '0.9 V inductor', ref='L1')
    res('R51K', 'VDD_0V9', 'FB_0V9', B, '0.9 V feedback top')
    res('R100K', 'FB_0V9', GND, B, '0.9 V feedback bottom')
    # TI's feed-forward for a 100k bottom resistor (SLVSDG1C 8.2.2.3)
    cap('C6P8', 'VDD_0V9', 'FB_0V9', B, '0.9 V feed-forward')
    # one 22 uF here: with the SoC's own decoupling the rail has about
    # 56 uF, inside TI's tested 10-47 uF effective once DC bias is counted
    cap('C22U', 'VDD_0V9', GND, B, '0.9 V output')

    # EA3036C (U3): three 1 A bucks.  CH1 3.3 V (last), CH2 1.36 V DDR3L,
    # CH3 1.8 V.  0.6 V reference.
    #   3.3 V  = 0.6 x (1 + 100k / 22.6k) = 3.255 V (VCCIO 3.0-3.465 V; the
    #            EA3036C sits in PFM at these loads, which runs high, so
    #            3.25 V as Luckfox's Core1106 rather than 3.3 V)
    #   DDR    = 0.6 x (1 + 127k / 100k) = 1.362 V (DDR3L 1.283-1.45 V)
    #   1.8 V  = 0.6 x (1 + 200k / 100k) = 1.800 V
    add('U', 'EA3036C', {'1': GND, '2': 'FB_1V8', '3': 'FB_DDR', '4': GND, '5': GND, '6': 'LX_DDR',
                         '7': 'VSYS', '8': 'EN_MID', '9': 'EN_3V3', '10': 'VSYS', '11': 'LX_3V3', '12': GND,
                         '13': GND, '14': 'FB_3V3', '15': GND, '16': 'VSYS', '17': GND, '18': 'EN_MID',
                         '19': 'VSYS', '20': 'LX_1V8', '21': GND}, B, 'triple buck', ref='U3')
    for _ in range(3):
        cap('C10U', 'VSYS', GND, B, 'triple buck input')
    cap('C1U', 'VSYS', GND, B, 'triple buck VCC')
    # enables: 1.8 V + DDR at 100k x 330 nF, 3.3 V at 200k x 470 nF.  The
    # EN threshold is anywhere in 0.4-1.4 V: from 5 V that is 2.7-11 ms
    # (1.8 V / DDR), always after the 0.9 V buck's 0.8 ms soft start, and
    # 7.8-31 ms (3.3 V), always after 1.8 V
    res('R100K', 'VSYS', 'EN_MID', B, '1.8 V / DDR enable delay R')
    cap('C330N', 'EN_MID', GND, B, '1.8 V / DDR enable delay C')
    res('R200K', 'VSYS', 'EN_3V3', B, '3.3 V enable delay R')
    cap('C470N', 'EN_3V3', GND, B, '3.3 V enable delay C')
    add('L', 'L1U5', {'1': 'LX_3V3', '2': 'VCC_3V3'}, B, '3.3 V inductor', ref='L2')
    res('R100K', 'VCC_3V3', 'FB_3V3', B, '3.3 V feedback top')
    res('R22K6', 'FB_3V3', GND, B, '3.3 V feedback bottom')
    # 220 pF across each top resistor: Everanalog's application circuit
    # (EA3036C v1.4 fig. 2) and every Luckfox EA3036C board
    cap('C220P', 'VCC_3V3', 'FB_3V3', B, '3.3 V feed-forward')
    cap('C22U', 'VCC_3V3', GND, B, '3.3 V output')
    cap('C22U', 'VCC_3V3', GND, B, '3.3 V output')
    add('L', 'L1U5', {'1': 'LX_DDR', '2': 'VCC_DDR'}, B, 'DDR inductor', ref='L3')
    res('R127K', 'VCC_DDR', 'FB_DDR', B, 'DDR feedback top')
    res('R100K', 'FB_DDR', GND, B, 'DDR feedback bottom')
    cap('C220P', 'VCC_DDR', 'FB_DDR', B, 'DDR feed-forward')
    cap('C22U', 'VCC_DDR', GND, B, 'DDR output')
    add('L', 'L1U5', {'1': 'LX_1V8', '2': 'VCC_1V8'}, B, '1.8 V inductor', ref='L4')
    res('R200K', 'VCC_1V8', 'FB_1V8', B, '1.8 V feedback top')
    res('R100K', 'FB_1V8', GND, B, '1.8 V feedback bottom')
    cap('C220P', 'VCC_1V8', 'FB_1V8', B, '1.8 V feed-forward')
    cap('C22U', 'VCC_1V8', GND, B, '1.8 V output')

    # The Wi-Fi module's own 3.3 V (U4): its 0.38 A transmit bursts stay
    # off the SoC's rails.
    #   VWIFI = 0.6 x (1 + 100k / 22.6k) = 3.255 V, the same as VCC_3V3:
    #   the ESP32-C6's I/O runs at its supply and talks straight to the
    #   SoC's 3.3 V SDIO and UART pins (3.0-3.6 V; LayerCam v1's 3.60 V
    #   for the AP6256 would be the C6's absolute maximum)
    add('U', 'TLV62569', {'1': 'VSYS', '2': GND, '3': 'SW_WIFI', '4': 'VSYS', '5': 'FB_WIFI'}, B,
        'Wi-Fi buck', ref='U4')
    cap('C10U', 'VSYS', GND, B, 'Wi-Fi buck input')
    add('L', 'L2U2', {'1': 'SW_WIFI', '2': 'VWIFI'}, B, 'Wi-Fi inductor', ref='L5')
    res('R100K', 'VWIFI', 'FB_WIFI', B, 'Wi-Fi feedback top')
    res('R22K6', 'FB_WIFI', GND, B, 'Wi-Fi feedback bottom')
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
        '4': 'CAM_PWDN',        # GPIO3_C6 (1.8 V): sensor PWDNB
        '5': 'CAM_SCL',         # I2C4_SCL_M2
        '6': None,
        '7': 'CAM_SDA',         # I2C4_SDA_M2
        '8': None, '9': None,
        '10': 'VDD_0V9',        # DVDD_1
        '11': 'SD_DET',         # SDMMC0_DET: to ground (the SDIO card is always present)
        '12': 'SD_D1', '13': 'VCC_3V3',   # VCCIO4 = 3.3 V (the Wi-Fi's SDIO, SDMMC0)
        '14': 'SD_D0', '15': 'SD_CLK_SOC', '16': 'SD_CMD', '17': 'SD_D3', '18': 'SD_D2',
        '19': 'VCC_RTC',        # RTC_AVDD3V3: 3.3 V through 100R, 1 uF
        '20': 'RTC_XOUT', '21': 'RTC_XIN',
        '22': 'ALS',            # SARADC_IN1: the light sensor, 0-1.8 V
        '23': 'BOOT_KEY',       # SARADC_IN0: the BOOT pad (MaskROM at power-up)
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
        '58': None,             # RTC_CLKO: not used
        '59': None,             # GPIO0_A1: unused
        '60': 'WIFI_BOOT',      # GPIO0_A2: the C6's GPIO9 strap (low = download, to flash it)
        '61': 'VCC_3V3',        # PMU_VCC3V3
        '62': 'WIFI_HOST_WAKE', # GPIO0_A3 (PMU domain, can wake the SoC): the C6's IO4
        '63': None, '64': None, '65': None,
        '66': 'NPOR',
        '67': 'VDD_0V9',        # PMU_DVDD0V9
        '68': 'XIN_24M', '69': 'XOUT_24M',
        '70': 'VCC_1V8',        # OSC/PLL_AVDD1V8
        '71': 'VDD_0V9',        # OSC_PLL_DVDD
        '72': 'IRCUT_A',        # GPIO1_A0: H-bridge IN1 (pulled down inside: bridge off at reset)
        '73': 'IRCUT_B',        # GPIO1_A1: H-bridge IN2
        '74': 'WIFI_EN',        # GPIO1_A2: the C6's EN (mmc-pwrseq)
        '75': 'WIFI_RXD',       # UART1_TX_M0 -> the C6's RXD0 (flashing it from Linux)
        '76': 'WIFI_TXD',       # UART1_RX_M0 <- the C6's TXD0
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
    for _ in range(7):                  # one per 3.3 V pin: 13, 28, 43, 61, 81, 88, 108
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

    # MaskROM: SARADC_IN0 held low while the camera powers up makes the
    # SoC wait for flashing over USB.  No button (a switch's plastic is
    # rated 70-85 C; this one would sit at 90 C): two pads, BOOT and
    # ground side by side, bridged with tweezers while plugging in, only to
    # recover a camera whose flash is empty or broken.  Everyday updates
    # and Wi-Fi setup need no key (firmware/README.md).  10k up to 1.8 V,
    # 1 nF, 100R to the pad.
    res('R10K', 'BOOT_KEY', 'VCC_1V8', B, 'boot pull-up')
    cap('C1N', 'BOOT_KEY', GND, B, 'boot filter')
    res('R100R', 'BOOT_KEY', 'BOOT_SW', B, 'boot pad series R')
    add('TP', 'TP', {'1': 'BOOT_SW'}, B, 'boot pad', ref='TP5')

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
    # ESP32-C6-MINI-1U-H4 (U6), Espressif's ESP32-C6-MINI-1/1U datasheet
    # v1.5.  esp-hosted firmware on it, SDIO slave on IO18-23 to the SoC's
    # SDMMC0 (as v1's AP6256); the SoC holds EN low until Linux's
    # mmc-pwrseq raises it.  The SoC can also pull GPIO9 low and talk to
    # UART0 to put new firmware on it (firmware/README.md).  The module's
    # antenna socket is MHF III (W.FL): a short lead to an RP-SMA socket in
    # the case wall.
    w = {'1': GND, '2': GND, '3': 'VWIFI', '4': None, '5': None, '6': None, '7': None,
         '8': 'WIFI_EN',
         '9': 'WIFI_HOST_WAKE',  # IO4: esp-hosted's host-wake output (MTMS strap: harmless low)
         '10': None, '11': GND, '12': None, '13': None, '14': GND, '15': None, '16': None,
         '17': 'WIFI_USB_DM',    # IO12 / IO13: the C6's own USB, test pads for recovery
         '18': 'WIFI_USB_DP',
         '19': None, '20': None, '21': None,
         '22': 'WIFI_IO8',       # strap: high for download mode (10k up)
         '23': 'WIFI_BOOT',      # IO9 strap: high = boot from flash (10k up)
         '24': 'SD_CMD', '25': 'SD_CLK', '26': 'SD_D0', '27': 'SD_D1', '28': 'SD_D2', '29': 'SD_D3',
         '30': 'WIFI_RXD', '31': 'WIFI_TXD',
         '32': None, '33': None, '34': None, '35': None}
    for k in list(range(36, 62)):
        w[str(k)] = GND           # the ground row, the corners and the 3 x 3 centre pad
    add('U', 'ESP32C6', w, B, 'Wi-Fi module', ref='U6')
    # Espressif fig. 9-1: 22 uF + 100 nF at 3V3
    cap('C22U', 'VWIFI', GND, B, 'Wi-Fi supply bulk')
    cap('C100N', 'VWIFI', GND, B, 'Wi-Fi supply HF')
    # EN held low until Linux (as v1's WL_REG_ON); the straps pulled up to
    # the module's own supply
    res('R100K', 'WIFI_EN', GND, B, 'Wi-Fi EN pull-down')
    cap('C100N', 'WIFI_EN', GND, B, 'Wi-Fi EN filter')
    res('R10K', 'WIFI_BOOT', 'VWIFI', B, 'Wi-Fi GPIO9 pull-up')
    res('R10K', 'WIFI_IO8', 'VWIFI', B, 'Wi-Fi GPIO8 pull-up')
    add('TP', 'TP', {'1': 'WIFI_USB_DM'}, B, 'Wi-Fi USB D- pad', ref='TP6')
    add('TP', 'TP', {'1': 'WIFI_USB_DP'}, B, 'Wi-Fi USB D+ pad', ref='TP7')
    # SDIO: 22R in the clock at the SoC, 10k pull-ups on CMD and data (as
    # v1; esp-hosted asks for external pull-ups on every data line)
    res('R22R', 'SD_CLK_SOC', 'SD_CLK', B, 'SDIO clock series R')
    for n in ('SD_CMD', 'SD_D0', 'SD_D1', 'SD_D2', 'SD_D3'):
        res('R10K', n, 'VCC_3V3', B, 'SDIO pull-up')
    # card detect held firmly low (1k against the pin's 16-43k pull-up)
    res('R1K', 'SD_DET', GND, B, 'SDIO card-detect to ground')


def main_camera():
    B = 'camera'
    # SC4336H (U8), bare on the front face, its optical centre on the lens
    # axis.  Balls by row (A-E) and column (1-7), the SC4336P's map, which
    # SmartSens says the SC4336H keeps (docs/hookup.md: the datasheet is
    # under NDA; this map is to be confirmed before ordering).
    #   AVDD 2.8 V from its own LDO, DOVDD 1.8 V, DVDD from the sensor's
    #   own regulator (capacitors only).  SID low: I2C address 0x30.
    #   XSHUTDN and PWDNB from the SoC (both low = off).  24 MHz clock.
    s = {'A1': GND, 'A2': None, 'A3': 'CAM_MCLK', 'A4': 'CAM_SDA', 'A5': 'CAM_SCL', 'A6': 'CAM_RST',
         'A7': None,             # EFSYNC: external frame sync, unused
         'B1': 'CAM_AVDD', 'B2': GND, 'B3': None,   # FSYNC out, unused
         'B4': 'CAM_DVDD', 'B5': GND,                # SID low
         'B6': 'CAM_DVDD', 'B7': 'CAM_AVDD',
         'C1': 'CAM_DVDD', 'C2': 'CAM_DOVDD', 'C3': 'CAM_DOVDD', 'C4': 'CSI_CKP', 'C5': None,
         'C6': 'CAM_PWDN', 'C7': GND,
         'D1': None, 'D2': 'CSI_D1N', 'D3': 'CSI_D1P', 'D4': 'CSI_CKN', 'D5': 'CSI_D0N', 'D6': GND,
         'D7': 'CAM_VREFN2',
         'E1': None, 'E2': None, 'E3': None, 'E4': 'CAM_DVDD', 'E5': 'CSI_D0P', 'E6': None,
         'E7': 'CAM_VREFN'}
    add('U', 'SC4336H', s, B, 'image sensor', ref='U8')
    # 2.8 V: TLV75528 (U9: 1 OUT, 2 NC, 3 GND, 4 EN, 5 NC, 6 IN, 7 pad)
    # from 3.3 V, on whenever 3.3 V is (the sensor's own XSHUTDN turns it
    # off); a low-noise LDO, not a buck, for the pixels
    add('U', 'TLV75528', {'1': 'CAM_AVDD', '2': None, '3': GND, '4': 'VCC_3V3', '5': None, '6': 'VCC_3V3',
                          '7': GND}, B, 'sensor 2.8 V LDO', ref='U9')
    cap('C1U', 'VCC_3V3', GND, B, 'sensor LDO input')
    cap('C1U', 'CAM_AVDD', GND, B, 'sensor LDO output')
    cap('C1U', 'CAM_AVDD', GND, B, 'sensor AVDD')
    cap('C100N', 'CAM_AVDD', GND, B, 'sensor AVDD HF')
    cap('C100N', 'CAM_AVDD', GND, B, 'sensor AVDD HF 2')
    # 1.8 V I/O through 1R, as the SoC's MIPI supply: the sensor's
    # switching current stays off VCC_1V8
    res('R1R', 'VCC_1V8', 'CAM_DOVDD', B, 'sensor DOVDD filter R')
    cap('C1U', 'CAM_DOVDD', GND, B, 'sensor DOVDD')
    cap('C100N', 'CAM_DOVDD', GND, B, 'sensor DOVDD HF')
    cap('C4U7', 'CAM_DVDD', GND, B, 'sensor DVDD')
    cap('C100N', 'CAM_DVDD', GND, B, 'sensor DVDD HF')
    cap('C100N', 'CAM_DVDD', GND, B, 'sensor DVDD HF 2')
    cap('C2U2', 'CAM_VREFN', GND, B, 'sensor VREFN')
    cap('C2U2', 'CAM_VREFN2', GND, B, 'sensor VREFN2')
    res('R22R', 'CAM_MCLK_SOC', 'CAM_MCLK', B, 'sensor clock series R')
    res('R4K7', 'CAM_SCL', 'VCC_1V8', B, 'camera I2C pull-up')
    res('R4K7', 'CAM_SDA', 'VCC_1V8', B, 'camera I2C pull-up')
    # the sensor held off until Linux turns it on
    res('R100K', 'CAM_RST', GND, B, 'sensor XSHUTDN pull-down')
    res('R100K', 'CAM_PWDN', GND, B, 'sensor PWDNB pull-down')

    # IR-cut filter: DRV8210P (U7; pin for pin the DRV8837, rated to 125 C)
    # 1 VM, 2 OUT1, 3 OUT2, 4 GND, 5 IN2, 6 IN1, 7 nSLEEP, 8 VCC, 9 pad.
    # 3.3 V across the 20 ohm coil (Commonlands: 3.3 V for 100-500 ms); the
    # driver pulses it.  IN1 and IN2 have pull-downs inside.
    add('U', 'DRV8210P', {'1': 'VCC_3V3', '2': 'IRCUT_1', '3': 'IRCUT_2', '4': GND, '5': 'IRCUT_B',
                         '6': 'IRCUT_A', '7': 'VCC_3V3', '8': 'VCC_3V3', '9': GND}, B, 'IR-cut driver',
        ref='U7')
    cap('C1U', 'VCC_3V3', GND, B, 'IR-cut driver VM')
    cap('C100N', 'VCC_3V3', GND, B, 'IR-cut driver VCC')
    # the holder's lead: red (pin 1) positive opens the filter (night)
    add('J', 'PB2R', {'1': 'IRCUT_1', '2': 'IRCUT_2', '3': GND, '4': GND}, B, 'IR-cut connector', ref='J3')


def main_lights():
    B = 'lights'
    # Six 850 nm LEDs on the front face (geometry.LED_*), three strings of
    # two: 5 V -> 47R -> LED -> LED -> LED_K; the MOSFET (Q1: 1 G, 2 S, 3 D)
    # switches LED_K to ground, PWM-dimmed.  (5.0 - 2 x 1.45) / 47 = 45 mA
    # a string, 0.10 W in each 0.25 W resistor (as LayerCam v1's ring).  The
    # LEDs light only while a night frame is taken (the firmware).
    # VSMY3850X01: pad 1 anode, pad 2 cathode.
    for s in range(3):
        a, m = 'STR%d_A' % (s + 1), 'STR%d_M' % (s + 1)
        res('R47R_1206', 'VSYS', a, B, 'string %d resistor' % (s + 1))
        add('D', 'IRLED', {'1': a, '2': m}, B, 'IR LED %d' % (2 * s + 1), ref='D%d' % (2 * s + 2))
        add('D', 'IRLED', {'1': m, '2': 'LED_K'}, B, 'IR LED %d' % (2 * s + 2), ref='D%d' % (2 * s + 3))
    cap('C10U', 'VSYS', GND, B, 'IR LED supply')
    add('Q', 'AO3400A', {'1': 'IR_GATE', '2': GND, '3': 'LED_K'}, B, 'IR LED switch', ref='Q1')
    res('R100R', 'IR_PWM', 'IR_GATE', B, 'IR LED gate R')
    res('R100K', 'IR_GATE', GND, B, 'IR LED gate pull-down (off at reset)')
    # light sensor behind the front window: TEMT6000 (Q2) pads 1, 2
    # emitter, pad 3 collector; from 1.8 V through 1k; 22k load: about
    # 0.5 V at 50 lux, 1.8 V (full scale) from a few hundred lux
    add('Q', 'TEMT6000', {'1': 'ALS', '2': 'ALS', '3': 'ALS_VCC'}, B, 'light sensor', ref='Q2')
    res('R1K', 'VCC_1V8', 'ALS_VCC', B, 'light sensor supply R')
    res('R22K', 'ALS', GND, B, 'light sensor load')
    cap('C100N', 'ALS', GND, B, 'light sensor filter')


def main_usb():
    B = 'usb'
    # USB-C (J1) on the board's edge tab: 5.1k Rd on each CC (a USB
    # device: the printer's port gives 5 V); both D+ and both D- contacts
    # joined (either plug way round)
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'VSYS', 'B4A9': 'VSYS', 'A5': 'CC1', 'B5': 'CC2',
                      'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM', 'A8': None, 'B8': None,
                      '1': GND, '2': GND, '3': GND, '4': GND}, B, 'USB-C', ref='J1')
    res('R5K1', 'CC1', GND, B, 'CC1 Rd')
    res('R5K1', 'CC2', GND, B, 'CC2 Rd')
    # USBLC6 (U10): I/O1 = D- (pins 1, 6), I/O2 = D+ (pins 3, 4)
    add('U', 'USBLC6', {'1': 'USB_DM', '2': GND, '3': 'USB_DP', '4': 'USB_DP', '5': 'VSYS', '6': 'USB_DM'},
        B, 'USB ESD', ref='U10')
    # 6.0 V stand-off: above USB's 5.5 V VBUS maximum, so it does not
    # leak when hot; clamps at 10.3 V
    add('D', 'SMF6V0', {'1': 'VSYS', '2': GND}, B, '5 V TVS', ref='D1')
    cap('C10U', 'VSYS', GND, B, '5 V at the connector')
    cap('C100N', 'VSYS', GND, B, '5 V HF')


def main_mechanics():
    # four M2 screws into the case's bosses; the two M1.6 screws that hold
    # the IR-cut holder over the sensor
    for i in range(4):
        add('H', 'HOLE_M2', {}, 'mounting', 'M2 hole', ref='H%d' % (i + 1))
    for i in range(2):
        add('H', 'HOLE_M1V6', {}, 'mounting', 'lens holder screw', ref='H%d' % (i + 5))


FUNCS = None


def _funcs():
    return [main_power, main_soc, main_storage, main_wifi, main_camera, main_lights, main_usb, main_mechanics]


def _hand_refs(board):
    import re, inspect
    return {r for f in _funcs() for r in re.findall(r"ref='([A-Z]+\d+)'", inspect.getsource(f))}


def build(board='main'):
    if board != 'main':
        raise KeyError(board)
    COMPS.clear(); _count.clear()
    RESERVED.clear(); RESERVED.update(_hand_refs(board))
    for f in _funcs():
        f()
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
