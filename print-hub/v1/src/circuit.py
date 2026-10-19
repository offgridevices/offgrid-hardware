# -*- coding: utf-8 -*-
"""The circuit: every component and every connection, as code.

This is the schematic.  Each block reads top to bottom the way you would
check it against a datasheet: the part, then pin by pin what it connects
to, with the reason for anything that is not obvious.  Pin numbers are
footprint pad numbers, which for every part here are the datasheet pin
numbers (the USB-C receptacles' pads are named by contact).  A pin given
as None is deliberately left open.

Print Hub: five switched USB-A ports (power only) for a resin printer's
accessories, an ESP32-S3 that switches them over Wi-Fi or USB, a USB-C
POWER IN that asks a USB-PD charger for 9 V, and a USB-C DATA port to the
print server.

    POWER IN (USB-C) -> HUSB238 asks for 9 V -> SY8368A buck -> 5.16 V rail
        5 V rail -> per port: TPS25200 switch -> 20 mOhm shunt -> USB-A
                                  INA180 reads the shunt -> ESP32 ADC
    DATA (USB-C) -> ESP32-S3 native USB; its VBUS only feeds the logic
    logic 5 V = (5 V rail OR DATA VBUS, through Schottky diodes) -> 3.3 V LDO

The firmware's pin map (firmware/src/board.h) is checked against this file
by src/verify.py.
"""


class Comp:
    def __init__(self, ref, part, pins, block, note=''):
        self.ref, self.part, self.pins, self.block, self.note = ref, part, pins, block, note


COMPS = []
_count = {}
GND = 'GND'
NPORTS = 5

# Reference designators: the shared parts count from 1 (C1, R1 ...); port
# n's parts count from n x 100 + 1 (C101 ... for USB1), so a port reads as
# a group on the assembly drawing.
PORT = [0]


def add(prefix, part, pins, block, note='', ref=None):
    if ref is None:
        key = (prefix, PORT[0])
        _count[key] = _count.get(key, 0) + 1
        ref = '%s%d' % (prefix, PORT[0] * 100 + _count[key])
    c = Comp(ref, part, dict(pins), block, note)
    COMPS.append(c)
    return c


def cap(part, a, b, block, note=''):
    return add('C', part, {'1': a, '2': b}, block, note)


def res(part, a, b, block, note=''):
    return add('R', part, {'1': a, '2': b}, block, note)


# =====================================================================
#  POWER IN: USB-C, USB-PD sink, 9 V -> 5.16 V buck
# =====================================================================
def power_in():
    B = 'power in'
    # USB-C POWER IN.  Only VBUS, ground and CC are used: the charger talks
    # USB-PD to the HUSB238 over CC.  D+/D- and SBU stay open.  Shell to
    # ground.
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'VBUS_IN', 'B4A9': 'VBUS_IN',
                      'A5': 'CC1_IN', 'B5': 'CC2_IN', 'A6': None, 'B6': None, 'A7': None, 'B7': None,
                      'A8': None, 'B8': None, '1': GND, '2': GND, '3': GND, '4': GND},
        B, 'POWER IN', ref='J1')
    # TVS: 15 V stand-off, above the 9 V asked for (and 12 V, the most the
    # firmware ever asks for); clamps at 24.4 V, under the buck's 28 V.
    add('D', 'SMAJ15A', {'1': 'VBUS_IN', '2': GND}, B, 'input TVS', ref='D1')

    # HUSB238: USB-PD sink.  Its CC pins carry their own Rd pull-downs (do
    # not add 5.1k here).  VSET 6.1k (5.1k + 1k) asks for 9 V; ISET 10.47k
    # (10k + 470R) asks for 2 A, so a 20 W charger (9 V 2.22 A) still gives
    # 9 V; the firmware then asks for the 9 V PDO's full current over I2C
    # and reads the contract back (firmware/src/board.cpp).  GATE (an
    # open-drain PMOS driver) is not used.  D+/D- are left open: the legacy
    # charger detection they feed is no use here (the buck needs 9 V).
    add('U', 'HUSB238', {'1': 'VBUS_IN', '2': None, '3': None, '4': 'CC1_IN', '5': 'CC2_IN',
                         '6': 'SDA', '7': 'SCL', '8': 'PD_VSET', '9': 'PD_ISET', '10': None, '11': GND},
        B, 'USB-PD sink', ref='U1')
    cap('C1U_50', 'VBUS_IN', GND, B, 'HUSB238 VIN')
    res('R5K1', 'PD_VSET', 'PD_VSET2', B, 'VSET 9 V (5.1k of 6.1k)')
    res('R1K', 'PD_VSET2', GND, B, 'VSET 9 V (1k of 6.1k)')
    res('R10K', 'PD_ISET', 'PD_ISET2', B, 'ISET 2 A (10k of 10.47k)')
    res('R470R', 'PD_ISET2', GND, B, 'ISET 2 A (470R of 10.47k)')
    # I2C to the ESP32, 4.7k pull-ups to 3.3 V
    res('R4K7', 'SDA', '+3V3', B, 'I2C SDA pull-up')
    res('R4K7', 'SCL', '+3V3', B, 'I2C SCL pull-up')

    # SY8368A buck, 9 V (up to 15 V) -> 5.16 V, 5 A for the ports.
    #   VOUT = 0.6 x (1 + R_top / R_bot) = 0.6 x (1 + 76k / 10k) = 5.16 V
    #   (75k + 1k on top: 5.16 V leaves room for the shunt, the switch and
    #   the cable before a device sees 4.75 V)
    #   ILMT to ground: 8 A valley current limit
    #   EN from VBUS_IN through 100k: on whenever there is input
    #   PG not used
    add('U', 'SY8368A', {'1': GND, '2': 'BUCK_LX', '3': GND, '4': 'VBUS_IN', '5': 'VBUS_IN', '6': 'VBUS_IN',
                         '7': 'BUCK_BS', '8': 'BUCK_VCC', '9': 'BUCK_FB', '10': GND, '11': None,
                         '12': 'BUCK_EN'}, B, 'buck', ref='U2')
    for _ in range(2):
        cap('C10U_50', 'VBUS_IN', GND, B, 'buck input')
    cap('C100N_50', 'VBUS_IN', GND, B, 'buck input HF')
    res('R100K', 'VBUS_IN', 'BUCK_EN', B, 'buck enable')
    cap('C100N', 'BUCK_BS', 'BUCK_LX', B, 'buck bootstrap')
    cap('C1U_25', 'BUCK_VCC', GND, B, 'buck VCC')
    add('L', 'L2U2', {'1': 'BUCK_LX', '2': 'VRAIL'}, B, 'buck inductor', ref='L1')
    # board temperature, beside the buck and its inductor (the hottest
    # corner): 10k NTC to ground, 10k up to 3.3 V, into an ADC1 pin.  The
    # firmware turns the ports down before anything passes its rating
    # (sim/thermal/board_heat.md).
    res('NTC10K', 'NTC', GND, B, 'board temperature NTC')
    res('R10K', 'NTC', '+3V3', B, 'NTC pull-up')
    cap('C100N', 'NTC', GND, B, 'NTC filter')
    res('R75K', 'VRAIL', 'BUCK_FB2', B, 'feedback top (75k of 76k)')
    res('R1K', 'BUCK_FB2', 'BUCK_FB', B, 'feedback top (1k of 76k)')
    res('R10K', 'BUCK_FB', GND, B, 'feedback bottom')
    cap('C22P', 'VRAIL', 'BUCK_FB', B, 'feed-forward')
    for _ in range(4):
        cap('C22U_25', 'VRAIL', GND, B, 'buck output')

    # what the ESP32 measures: the input (100k / 15k: 15 V reads 1.96 V)
    # and the port rail (100k / 100k), each filtered by 100 nF
    res('R100K', 'VBUS_IN', 'VIN_SENSE', B, 'input sense top')
    res('R15K', 'VIN_SENSE', GND, B, 'input sense bottom')
    cap('C100N', 'VIN_SENSE', GND, B, 'input sense filter')
    res('R100K', 'VRAIL', 'RAIL_SENSE', B, 'rail sense top')
    res('R100K', 'RAIL_SENSE', GND, B, 'rail sense bottom')
    cap('C100N', 'RAIL_SENSE', GND, B, 'rail sense filter')


# =====================================================================
#  LOGIC: DATA USB-C, diode OR, 3.3 V, ESP32-S3, buttons, LEDs
# =====================================================================
def logic():
    B = 'logic'
    # USB-C DATA to the print server.  5.1k Rd on each CC: a plain USB
    # device.  Both D+ and both D- contacts joined (either plug way round).
    add('J', 'USBC', {'A1B12': GND, 'B1A12': GND, 'A4B9': 'VBUS_DATA', 'B4A9': 'VBUS_DATA',
                      'A5': 'CC1_DATA', 'B5': 'CC2_DATA', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DN',
                      'B7': 'USB_DN', 'A8': None, 'B8': None, '1': GND, '2': GND, '3': GND, '4': GND},
        B, 'DATA', ref='J2')
    cap('C10U_10', 'VBUS_DATA', GND, B, 'DATA VBUS')
    res('R5K1', 'CC1_DATA', GND, B, 'DATA CC1 Rd')
    res('R5K1', 'CC2_DATA', GND, B, 'DATA CC2 Rd')
    # USBLC6: I/O1 = D- (pins 1, 6), I/O2 = D+ (pins 3, 4), flow-through
    add('U', 'USBLC6', {'1': 'USB_DN', '2': GND, '3': 'USB_DP', '4': 'USB_DP', '5': 'VBUS_DATA', '6': 'USB_DN'},
        B, 'USB ESD', ref='U3')

    # The logic supply: the 5 V rail OR the DATA port's VBUS, each through a
    # Schottky (pad 1 cathode), so the board runs from the print server's
    # USB alone (ports off) and the server's VBUS never reaches a port.
    add('D', 'B5819W', {'1': 'VLOGIC', '2': 'VRAIL'}, B, 'logic OR from the rail', ref='D2')
    add('D', 'B5819W', {'1': 'VLOGIC', '2': 'VBUS_DATA'}, B, 'logic OR from DATA', ref='D3')
    cap('C10U_10', 'VLOGIC', GND, B, 'logic 5 V')
    # AP2112K: 1 VIN, 2 GND, 3 EN (to VIN), 4 NC, 5 VOUT
    add('U', 'AP2112K', {'1': 'VLOGIC', '2': GND, '3': 'VLOGIC', '4': None, '5': '+3V3'}, B, '3.3 V LDO', ref='U4')
    cap('C10U_10', '+3V3', GND, B, 'LDO output')
    cap('C22U_6V3', '+3V3', GND, B, 'ESP32 bulk (Wi-Fi bursts)')
    cap('C100N', '+3V3', GND, B, 'ESP32 3V3')

    # ESP32-S3-WROOM-1 (module pin -> GPIO in the comment).  Analogue inputs
    # on ADC1 only (ADC2 stops working while Wi-Fi is on).  Strapping pins
    # GPIO3, 45, 46 left open; GPIO0 is BOOT.
    esp = {
        '1': GND, '2': '+3V3', '3': 'ESP_EN',
        '4': 'IS3',          # IO4  port 3 current
        '5': 'IS4',          # IO5  port 4 current
        '6': 'IS5',          # IO6  port 5 current
        '7': 'VIN_SENSE',    # IO7
        '8': 'FLT2',         # IO15
        '9': 'FLT3',         # IO16
        '10': 'FLT4',        # IO17
        '11': 'FLT5',        # IO18
        '12': 'RAIL_SENSE',  # IO8
        '13': 'USB_DN',      # IO19
        '14': 'USB_DP',      # IO20
        '15': None,          # IO3  strapping (JTAG source)
        '16': None,          # IO46 strapping
        '17': 'NTC',         # IO9  board temperature (ADC1)
        '18': 'EN2',         # IO10
        '19': 'EN3',         # IO11
        '20': 'EN4',         # IO12
        '21': 'EN5',         # IO13
        '22': 'FLT1',        # IO14
        '23': 'EN1',         # IO21
        '24': None,          # IO47
        '25': None,          # IO48
        '26': None,          # IO45 strapping (flash voltage)
        '27': 'BOOT',        # IO0
        '28': None, '29': None, '30': None,   # IO35-37
        '31': 'LED_DIN0',    # IO38 LED chain
        '32': 'SDA',         # IO39
        '33': 'SCL',         # IO40
        '34': None, '35': None,               # IO41, IO42
        '36': 'RXD0',        # RXD0 (GPIO44)
        '37': 'TXD0',        # TXD0 (GPIO43)
        '38': 'IS2',         # IO2  port 2 current
        '39': 'IS1',         # IO1  port 1 current
        '40': GND, '41': GND,
    }
    add('U', 'ESP32S3', esp, B, 'ESP32-S3 module', ref='U5')
    # EN: 10k up, 1 uF down (power-on delay), RESET button to ground
    res('R10K', 'ESP_EN', '+3V3', B, 'EN pull-up')
    cap('C1U_25', 'ESP_EN', GND, B, 'EN delay')
    # buttons: pads 1 and 4 are diagonal, so they are on opposite sides of
    # the switch whichever pair the part joins inside
    add('SW', 'BUTTON', {'1': 'ESP_EN', '2': None, '3': None, '4': GND}, B, 'RESET', ref='SW1')
    res('R10K', 'BOOT', '+3V3', B, 'BOOT pull-up')
    add('SW', 'BUTTON', {'1': 'BOOT', '2': None, '3': None, '4': GND}, B, 'BOOT', ref='SW2')
    # UART0 test pads (boot log)
    add('TP', 'TP', {'1': 'TXD0'}, B, 'UART TX', ref='TP1')
    add('TP', 'TP', {'1': 'RXD0'}, B, 'UART RX', ref='TP2')
    add('TP', 'TP', {'1': GND}, B, 'ground', ref='TP3')
    add('TP', 'TP', {'1': 'VRAIL'}, B, '5 V rail', ref='TP4')

    # The status LED (the last in the chain is at the board's corner; the
    # five port LEDs are in the port blocks).  WS2812B-2020: 1 DO, 2 GND,
    # 3 DI, 4 VDD.  VDD from the logic 5 V, so the LEDs work on the print
    # server's USB too; its input threshold (0.55 VDD, 2.6 V) is under the
    # ESP32's 3.3 V.  100R in the data line at the source.
    res('R100R', 'LED_DIN0', 'LED_D0', B, 'LED data series')
    # chain: ESP32 -> status -> USB5 -> USB4 ... -> USB1 (nearest first)
    add('LED', 'WS2812B', {'1': 'LED_C5', '2': GND, '3': 'LED_D0', '4': 'VLOGIC'}, B, 'status LED', ref='LED1')
    cap('C100N', 'VLOGIC', GND, B, 'status LED')


# =====================================================================
#  PORTS: one block per USB-A port
# =====================================================================
def port(n):
    B = 'USB%d' % n
    vsw, vbus = 'PORT%d_SW' % n, 'VBUS%d' % n
    # TPS25200: 1 OUT, 2 ILIM, 3 FAULT (open drain, low = fault), 4 EN
    # (high = on), 5 GND, 6 IN, 7 pad.  47k on ILIM: 1.92 / 2.07 / 2.20 A
    # (min / typ / max).  EN pulled down, so the port stays off while the
    # ESP32 boots, resets or is being flashed.
    add('U', 'TPS25200', {'1': vsw, '2': 'ILIM%d' % n, '3': 'FLT%d' % n, '4': 'EN%d' % n, '5': GND,
                          '6': 'VRAIL', '7': GND}, B, 'port switch')
    cap('C100N', 'VRAIL', GND, B, 'switch input')
    cap('C22U_25', 'VRAIL', GND, B, 'rail bulk at the port')
    res('R47K', 'ILIM%d' % n, GND, B, 'current limit 2.07 A')
    res('R100K', 'EN%d' % n, GND, B, 'enable pull-down')
    res('R10K', 'FLT%d' % n, '+3V3', B, 'fault pull-up')
    # shunt after the switch: it measures this port only
    add('R', 'SHUNT20M', {'1': vsw, '2': vbus}, B, 'current shunt')
    # INA180A2 (pinout A): 1 OUT, 2 GND, 3 IN+ (switch side), 4 IN- (port
    # side), 5 VS.  20 mOhm x 50 = 1.0 V per A; from 3.3 V it cannot drive
    # the ADC pin past its supply.  1k / 100 nF filter into the ADC.
    add('U', 'INA180A2', {'1': 'ISA%d' % n, '2': GND, '3': vsw, '4': vbus, '5': '+3V3'}, B, 'current sense')
    cap('C100N', '+3V3', GND, B, 'amplifier supply')
    res('R1K', 'ISA%d' % n, 'IS%d' % n, B, 'ADC filter R')
    cap('C100N', 'IS%d' % n, GND, B, 'ADC filter C')
    cap('C22U_25', vbus, GND, B, 'port output')
    # USB-A: 1 VBUS, 2 D-, 3 D+, 4 GND, shell to ground.  D+ and D- joined:
    # a BC1.2 dedicated charging port, so a device may draw 1.5 A.
    add('J', 'USBA', {'1': vbus, '2': 'DCP%d' % n, '3': 'DCP%d' % n, '4': GND, 'SH1': GND, 'SH2': GND},
        B, 'USB-A port')
    # this port's LED, next in the chain
    add('LED', 'WS2812B', {'1': 'LED_C%d' % (n - 1) if n > 1 else None, '2': GND, '3': 'LED_C%d' % n,
                           '4': 'VLOGIC'}, B, 'port LED')
    cap('C100N', 'VLOGIC', GND, B, 'port LED')


def mounting():
    for i in range(2):
        add('H', 'HOLE', {}, 'mounting', 'M3 hole', ref='H%d' % (i + 1))


def build():
    COMPS.clear(); _count.clear()
    PORT[0] = 0
    power_in(); logic()
    for n in range(1, NPORTS + 1):
        PORT[0] = n
        port(n)
    PORT[0] = 0
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
    cs = build()
    ns = nets(cs)
    print('%d parts, %d nets' % (len(cs), len(ns)))
    for n, m in sorted(ns.items()):
        if len(m) < 2:
            print('single-pin net', n, m)
