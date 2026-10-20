# -*- coding: utf-8 -*-
"""The circuit: every component and every connection, as code.

This is the schematic.  src/sch.py draws it as a KiCad schematic (one page
per block below) and checks that KiCad's netlist of the drawing equals this
file.  Each block reads top to bottom the way you would check it against a
datasheet: the part, then pin by pin what it connects to, with the reason
for anything that is not obvious.  Pin numbers are footprint pad numbers,
which for every IC here are the datasheet's pin (or ball) names.

Mesh Radio v1 (working name): a LoRa mesh radio on one board.

  nRF52840 (Bluetooth + processor) -- SX1262 (LoRa) -- 15 dB pad -- QPA9510
  amplifier (up to ~3 W) -- harmonic filter -- SKY13330 antenna switch --
  LFCN-1000+ filter -- U.FL.  Receive: switch -- BGA7L1BN6 low-noise
  amplifier -- SX1262.

Firmware: Meshtastic (a board variant in this folder), MeshCore later.
The pin choices follow the RAK4631 where they can (the SX1262 bus, I2C,
the LEDs), so both firmwares port with a pin map and little else.

Values marked "tune" are the maker's reference values (or a calculated
start) for parts that set an RF match; they are set on built boards with a
network analyser (docs/plan.md).
"""

class Comp:
    def __init__(self, ref, part, pins, block, note=''):
        self.ref, self.part, self.pins, self.block, self.note = ref, part, pins, block, note

COMPS = []
_count = {}
_block = ['']

def add(prefix, part, pins, note=''):
    _count[prefix] = _count.get(prefix, 0) + 1
    c = Comp('%s%d' % (prefix, _count[prefix]), part, dict(pins), _block[0], note)
    COMPS.append(c)
    return c

def C(part, a, b='GND', note=''):
    return add('C', part, {'1': a, '2': b}, note)

def R(part, a, b='GND', note=''):
    return add('R', part, {'1': a, '2': b}, note)

def L(part, a, b, note=''):
    return add('L', part, {'1': a, '2': b}, note)

def TP(net, note=''):
    return add('TP', 'TP', {'1': net}, note)

GND = 'GND'

# Nets drawn as power ports on the schematic (everything else gets a label)
POWER_NETS = ['GND', '3V3', 'VSYS', 'BAT_P', 'VPA', 'PA_IN', 'USB_5V', 'VIN_CHG', '3V3_GPS']

BLOCKS = [
    ('inputs', 'Power in: USB-C, solar, drone 5 V (each surge-clamped and fused)'),
    ('charger', 'Charger and battery: protection, reverse polarity, battery sense'),
    ('system', 'System power: on/off switch, 3.3 V rail'),
    ('mcu', 'Processor and Bluetooth: nRF52840'),
    ('radio', 'LoRa radio: SX1262, its clock, transmit match and receive balun'),
    ('frontend', 'RF front end: 15 dB pad, 3 W amplifier, filters, antenna switch, LNA'),
    ('pa_power', 'Amplifier power: battery-first supply, buck-boost, control voltage, temperature'),
    ('ports', 'Ports: drone (JST-GH), GPS add-on (JST-SH), expansion header, buttons, LEDs'),
]

BLOCK_NOTES = {
    'inputs': 'USB: 22 V flat-clamp TVS, a 4.7 uF + 1 R snubber and a TPS259470A eFuse (cut-off 5.4 V, 1.5 A).\n'
              'Solar and drone: 33 V TVS and a 60 V MAX17608 (cut-off 10 V, 0.71 A, blocks -60 V and reverse current).',
    'charger': 'Battery plug wired the Adafruit/SparkFun way (pad 1 = +). Cell protection on the minus side\n'
               '(OCD ~5.8 A, SCD ~29 A, OV 4.275 V, UV 2.8 V); reverse-battery P-FET on the plus side, on only\n'
               'when the cell is the right way round. Charge 300 mA. Current-limited cell-to-SYS bypass.',
    'system': 'The slide switch drives only enables (3.3 V buck, cell bypass); charging works with the board off.',
    'mcu': 'nRF52840 in normal-voltage mode: VDD = VDDH = the 3.3 V rail, so its pins and the SX1262 share one\n'
           'logic level. REG1 DC/DC on (10 uH + 15 nH). Nordic reference circuit, aQFN73.',
    'radio': 'Semtech SX1262MB2CAS (915 MHz) reference values. TCXO on DIO3 (set 2.2 V in firmware), DIO2 drives\n'
             'the antenna switch.',
    'frontend': 'Drive: SX1262 +11 dBm -> 30 dBm (1 W), +17 dBm -> ~35 dBm (3 W). The 15.9 dB pad keeps the\n'
                'amplifier input below its +13 dBm limit even at the SX1262 maximum (+22 dBm -> +6 dBm).',
    'pa_power': 'Amplifier runs from the battery through a power mux (battery first down to 2.6 V; firmware selects\n'
                'charger SYS when no cell is fitted), then a TPS63810 buck-boost (I2C 0x75): 2.7 V for 1 W, 4.0 V for 3 W.',
    'ports': 'Drone port wired as Pixhawk TELEM (pins from the autopilot side): 1 5V, 2 TX, 3 RX, 4 CTS, 5 RTS,\n'
             '6 GND. Series resistors and ESD on every external signal.',
}

OVERVIEW = ('Mesh Radio v1 (working name) - OffGrid Devices\n'
            'LoRa 902-928 MHz mesh radio, up to ~3 W; Bluetooth LE; one LiPo cell; USB-C, solar and drone power.\n'
            'NDAA-ready parts list: every part from a US / EU / Japan / Taiwan / Korea / Norway maker.\n'
            'Each box below is one page. Every connection is a named label; the same name is the same wire.\n'
            'This drawing is generated from src/circuit.py by src/sch.py: change the code, not the drawing.')


def build():
    global COMPS, _count
    COMPS, _count = [], {}
    inputs(); charger(); system(); mcu(); radio(); frontend(); pa_power(); ports()
    return COMPS


def nets(comps=None):
    out = {}
    for c in comps or COMPS:
        for pad, n in c.pins.items():
            if n:
                out.setdefault(n, []).append((c.ref, pad))
    return out


# =====================================================================
def usb_efuse(raw, out):
    """TPS259470A on USB: UVLO = 1.20 V x (20 k + 7.68 k) / 7.68 k = 4.33 V,
    OVLO = 1.20 V x (1 M + 287 k) / 287 k = 5.38 V (the nRF52840's VBUS is
    5.5 V max), ILIM = 3334 / 2.21 k = 1.51 A, DVDT 1 nF (2 V/ms), ITIMER
    1 nF.  A 5.6 V zener holds EN/UVLO inside its 6.5 V rating with 20 V
    on the input (5.9 V at most, hot).  The EN divider is low-impedance
    (20 k on top) and the zener is far below its knee at the 1.2 V
    threshold (1 uA max even at 2.5 V), so its leakage cannot move UVLO;
    with the 4.7 V zener (2 uA at 1 V) and 1 M on top, UVLO could rise
    above OVLO and USB would never turn on (sim/hotplug).  AUXOFF and FLT
    are left open (firmware reads USB on VBUS)."""
    add('U', 'TPS259470A', {'5': raw, '6': out, '1': 'USB_UV', '2': 'USB_OV', '7': 'USB_DVDT',
                            '9': 'USB_ILM', '10': 'USB_TMR', '3': None, '4': None, '8': GND}, note='USB eFuse')
    R('R20k', raw, 'USB_UV'); R('R7.68k', 'USB_UV')
    add('D', 'ZENER5V6', {'1': 'USB_UV', '2': GND}, note='EN clamp')
    R('R1M', raw, 'USB_OV'); R('R287k', 'USB_OV')
    # 100 pF on OVLO (22 us with the divider): a 5 V plug-in rings VBUS to
    # ~5.5 V for a few us, enough to trip OVLO (5.22-5.57 V), and OVLO only
    # releases below 4.89 V, so USB stayed off until unplugged (sim/reverse);
    # a real over-voltage still cuts off within ~2 us
    C('C100p', 'USB_OV', note='OVLO ring filter')
    R('R2.21k', 'USB_ILM')
    C('C1n', 'USB_DVDT'); C('C1n', 'USB_TMR')
    C('C1u50', raw, note='eFuse input, 50 V')
    # Snubber: a 20 V source plugged in through 1 m of cable rings the input
    # toward 40 V; the TVS2200 alone clamped it at 27.4-28.2 V, against the
    # eFuse's 28 V rating (hot).  4.7 uF + 1 R damps the ring to 23.3 V and
    # the TVS no longer conducts (sim/hotplug).  4.7 + 1 uF stays inside the
    # USB sink's 10 uF.
    C('C4u7_50', raw, 'USB_SNB', note='snubber')
    R('R1R_0805', 'USB_SNB', GND, note='snubber, pulse-proof')


def hv_input(name, conn, ok_net):
    """MAX17608 (60 V, -60 V reverse, blocks reverse current) on the solar
    and drone inputs: OVLO = 1.5 V x (1.5 M + 267 k) / 267 k = 9.93 V; the
    UVLO pin is tied up to IN through 1 M so only the internal UVLO (4.0 V
    rising / 3.5 V falling) applies: the charger pulls a panel down to
    VINDPM (3.6 V with a flat cell) and a higher UVLO would cut it off.
    SETI 2.1 k = 0.71 A (67 % of its 1.1 A DC rating; charging at 300 mA
    plus the system needs ~0.5 A, so it only limits a no-cell transmit from
    drone or solar power); CLMODE to GND = continuous current limit (with
    auto-retry it would hiccup against the charger's own input limit).  EN
    open (internal pull-up), FLAG and UVOV open: they float when the input
    is absent.  Instead <name>_OK reads the input
    voltage on an ADC pin: 1.5 M / 100 k = 1/16 (5 V -> 0.31 V, 10 V ->
    0.63 V; a 20 V plug-in ring to 38 V -> 2.3 V, under the pin's 3.6 V).
    33 V bidirectional TVS at the connector."""
    add('D', 'SMF33CA', {'1': conn, '2': GND}, note=name + ' surge clamp')
    add('U', 'MAX17608', {'1': conn, '2': conn, '3': name + '_OV', '4': name + '_UV', '5': None, '6': GND, '7': GND,
                          '8': name + '_SETI', '9': None, '10': None, '11': 'VIN_CHG', '12': 'VIN_CHG', '13': GND},
        note=name + ' 60 V current limiter')
    R('R1.5M', conn, name + '_OV'); R('R267k', name + '_OV')
    R('R1M', conn, name + '_UV', note='UVLO pin held high: internal 4 V UVLO')
    R('R2.1k', name + '_SETI')
    C('C1u50', conn, note='input, 50 V')
    R('R1.5M', conn, ok_net); R('R100k', ok_net, note='input voltage / 16 to the ADC')


def inputs():
    _block[0] = 'inputs'
    # USB-C, a power sink with USB 2.0 data: 5.1 k on each CC asks for 5 V
    add('J', 'USBC', {'A4': 'USB_VBUS', 'A9': 'USB_VBUS', 'B4': 'USB_VBUS', 'B9': 'USB_VBUS',
                      'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM',
                      'A1': GND, 'A12': GND, 'B1': GND, 'B12': GND, '14': GND, '15': GND,
                      'A8': None, 'B8': None, 'A2': None, 'A3': None, 'B2': None, 'B3': None,
                      'A10': None, 'A11': None, 'B10': None, 'B11': None}, note='USB-C')
    R('R5.1k', 'USB_CC1'); R('R5.1k', 'USB_CC2')
    add('D', 'TPD4E05U06', {'1': 'USB_DP', '2': 'USB_DM', '4': 'USB_CC1', '5': 'USB_CC2', '3': GND, '8': GND,
                            '6': None, '7': None, '9': None, '10': None}, note='USB ESD')
    add('D', 'TVS2200', {'4': 'USB_VBUS', '5': 'USB_VBUS', '6': 'USB_VBUS', '1': GND, '2': GND, '3': GND, '7': GND},
        note='USB surge clamp')
    usb_efuse('USB_VBUS', 'USB_5V')
    # USB_5V feeds the nRF52840 VBUS pin (USB detect and its USB PHY) and,
    # through a Schottky, the charger.  The bleed drains that Schottky's
    # reverse leakage when solar or drone power holds VIN_CHG up to 10 V
    # and USB is out: ~0.4 mA typical at 85 C (sim/hotplug), which 47 k
    # turned into 10 V on VBUS (5.8 V max); 2.2 k holds it under 1 V
    # typical, 4 V at the diode's maximum leakage.  Costs 2.3 mA from USB.
    R('R2.2k', 'USB_5V', note='VBUS bleed')
    # 22 R into the nRF52840's VBUS, with its 4.7 uF in mcu() and one more
    # here (~200 us): the eFuse takes ~2 us to cut off a 5 -> 20 V step, in
    # which USB_5V follows the input to ~15 V; VBUS (5.8 V abs max, a few
    # mA) sees ~0.2 V of it (sim/hotplug)
    R('R22R', 'USB_5V', 'NRF_VBUS', note='VBUS filter')
    C('C4u7', 'NRF_VBUS', note='VBUS filter')
    add('D', 'RB060MM', {'2': 'USB_5V', '1': 'VIN_CHG'}, note='USB into the charger')

    # Solar panel, 5-6 V nominal, on its own JST-SH: cut off above 10 V; a
    # 12 V panel (26 V open circuit at -40 C) or a reversed panel is harmless.
    add('J', 'JST_SH2', {'1': 'SOLAR_CONN', '2': GND, '3': None, '4': None}, note='solar input')
    hv_input('SOL', 'SOLAR_CONN', 'SOLAR_OK')
    # Drone 5 V from the JST-GH drone port (charges the cell while carried),
    # protected the same way
    hv_input('DRN', 'DRONE_5V_CONN', 'DRONE_OK')


def charger():
    _block[0] = 'charger'
    # BQ25185: ISET 1 k -> 300 mA charge (300 A.ohm / R); ILIM/VSET 13 k ->
    # 4.2 V and 1.1 A input limit (datasheet table 6-1); NTC on TS, hot/cold
    # cut-off at about 60 C / 0 C, placed beside the battery plug and also
    # read by the processor (CHG_TS on P0.31/AIN7).
    add('U', 'BQ25185', {'10': 'VIN_CHG', '1': 'VSYS', '2': 'BAT_P', '4': 'CHG_CE_N', '6': 'CHG_TS',
                         '7': 'CHG_ILIM', '8': 'CHG_ISET', '9': 'CHG_STAT1', '3': 'CHG_STAT2', '5': GND, '11': GND},
        note='charger')
    # 1 uF only on IN (it had 1 + 10 uF): a weak panel (20 % sun, 37 mA) could
    # not charge 11 uF through the MAX17608's ~1 ms turn-on ramp without
    # sagging under its 3.5 V UVLO, so the input hiccupped (sim/solar)
    C('C1u25', 'VIN_CHG')
    C('C10u25', 'VSYS'); C('C10u25', 'BAT_P')
    R('R1k', 'CHG_ISET'); R('R13k', 'CHG_ILIM')
    add('TH', 'NTC10K', {'1': 'CHG_TS', '2': GND}, note='battery temperature')
    # /CE: pulled low = charging on, also when the board is switched off.
    # The processor can stop charging (firmware holds the cell to 0-45 C
    # using the TMP1075 and this NTC's reading, tighter than the charger's
    # own 0-60 C window) and toggling /CE restarts the charger's TS/MR
    # button timer: a cell above ~67 C reads as a held button, which after
    # 10 s would arm ship mode at the next loss of input power.
    R('R100k', 'CHG_CE_N', note='charge enabled unless the processor says otherwise')
    R('R10k', 'CHG_STAT1', '3V3'); R('R10k', 'CHG_STAT2', '3V3')
    # STAT2 low = charging (STAT1 low = fault), datasheet table 6-2
    add('LED', 'LED_R', {'1': 'CHG_STAT2', '2': 'CHG_LED_A'}, note='charging (red)')
    R('R1k', 'CHG_LED_A', '3V3')

    # Battery plug, Adafruit/SparkFun polarity: pad 1 = +, pad 2 = -
    # (from the footprint geometry against Adafruit's; check with a meter on a
    # real Adafruit cell before ordering, docs/plan.md)
    add('J', 'JST_PH2', {'1': 'BATT_PLUS', '2': 'CELL_MINUS', '3': None, '4': None}, note='battery')
    # Reverse battery: P-FET on the plus side, held off (gate pulled up to
    # BAT_P) unless a small N-FET, whose gate is the cell's + and source the
    # cell's -, sees the cell the right way round and pulls the gate down to
    # the cell's minus.  With the gate simply tied to the cell's minus, USB
    # power (charger on BAT_P) wakes the protector, which pulls the cell's
    # minus to ground, so a cell then plugged in backwards turned the FET
    # on: ~33 A through the cell and IC substrate diodes (sim/reverse).
    # The 1 M across the plug keeps the N-FET off with no cell fitted; its
    # gate is filtered (100 k / 100 nF, 10 ms) so neither the plug-in ring of
    # the cell leads nor BAT_P rising at a USB plug-in (coupled onto the empty
    # pad by the FET's capacitance) can turn it on: either would latch the
    # FET on (sim/reverse).  Bigger FET than before: 3 W bursts draw up to
    # 4.1 A (sim/burst).
    add('Q', 'CSD25310Q2', {'4': 'BATT_PLUS', '8': 'BATT_PLUS', '1': 'BAT_P', '2': 'BAT_P', '5': 'BAT_P', '6': 'BAT_P',
                            '7': 'BAT_P', '3': 'REV_G'}, note='reverse-battery FET')
    R('R1M', 'REV_G', 'BAT_P', note='off unless the cell is the right way round')
    add('Q', 'NMOS', {'3': 'REV_G', '2': 'CELL_MINUS', '1': 'POL_G'}, note='cell-polarity check')
    R('R1M', 'BATT_PLUS', 'CELL_MINUS', note='no cell: polarity check off')
    R('R100k', 'BATT_PLUS', 'POL_G'); C('C100n', 'POL_G', 'CELL_MINUS', note='polarity check filter')
    # its gate clamped (4.7 V zener, through the 100 k): a reversed cell onto
    # live pads put 9-11 V on it, past its 8 V rating (sim/reverse, 20 Oct)
    add('D', 'ZENER4V7', {'1': 'POL_G', '2': 'CELL_MINUS'}, note='polarity check gate clamp')
    # Cell protection for unprotected cells: BQ29700 on the minus side, two
    # back-to-back FETs, 15 mOhm sense so OCD = 100 mV / 17.2 mOhm = 5.8 A
    # (4.8-6.7 A over tolerance and temperature) and SCD = 500 mV / 17.2 mOhm
    # = 29 A (22-35 A); with 22 mOhm, OCD could trip at 3.3 A, inside a 3 W
    # burst (sim/shorts).  Its supply comes from BAT_P (after the reverse
    # FET) so a reversed cell never reaches its BAT pin.
    add('U', 'BQ29700', {'5': 'PROT_BAT', '4': 'CELL_MINUS', '6': 'PROT_VM', '3': 'PROT_DOUT', '2': 'PROT_COUT',
                         '1': None}, note='cell protector')
    R('R330R', 'BAT_P', 'PROT_BAT'); C('C100n', 'PROT_BAT', 'CELL_MINUS')
    R('R2.2k', 'PROT_VM', GND)
    add('Q', 'SSM10N954L', {'3': 'PROT_DOUT', '1': 'CELL_MINUS', '2': 'CELL_MINUS', '4': 'CELL_MINUS', '5': 'CELL_MINUS',
                            '8': 'PROT_COUT', '6': 'PROT_S2', '7': 'PROT_S2', '9': 'PROT_S2', '10': 'PROT_S2'},
        note='protection FETs')
    R('R15m', 'PROT_S2', GND, note='current sense')
    # Cell-to-SYS bypass: a 3 W burst can sag a worn cell below the
    # charger's 3.0 V battery-disconnect (60 us), which would drop SYS and
    # reset the board; this keeps the system rail on the cell.  TPS22950
    # (on with the power switch, current limit 1.0 A: RILIM 1.15 k, 0.75-
    # 1.25 A, so a short on VSYS is limited) then a Schottky, which blocks
    # SYS from charging the cell.  The LM66100 that was here let SYS charge
    # the cell at ~0.9 A outside the charger's control; the TPS22950's own
    # reverse blocking acts only above ~1 A (44 mV), so a weak source such
    # as a panel still charged the cell through it (sim/solar).  FLT open.
    add('U', 'TPS22950', {'B1': 'BAT_P', 'B2': 'BYP_OUT', 'A1': 'PWR_ON', 'C2': 'BYP_ILIM', 'C1': GND, 'A2': None},
        note='cell-to-SYS bypass')
    R('R1.15k', 'BYP_ILIM')
    add('D', 'RB060MM', {'2': 'BYP_OUT', '1': 'VSYS'}, note='bypass: no charging from SYS')
    # Battery voltage for the firmware: 1 M / 1.5 M as on the RAK4631
    # (ADC multiplier 1.667), 1.7 uA
    R('R1M', 'BAT_P', 'VBAT_SENSE'); R('R1.5M', 'VBAT_SENSE'); C('C100n', 'VBAT_SENSE')


def system():
    _block[0] = 'system'
    add('SW', 'SLIDE', {'2': 'PWR_ON', '1': 'VSYS', '3': None}, note='power switch')
    R('R1M', 'PWR_ON', note='off when the switch is open')
    # The switch enables the buck directly (no load switch: a short at the
    # buck input is a short on VSYS, which the charger and the current-
    # limited cell bypass both limit).
    C('C1u25', 'VSYS'); C('C10u', 'VSYS')
    # TPS62840: VSET 267 k -> 3.3 V; 100 % mode below 3.3 V in; EN = switch
    add('U', 'TPS62840', {'B1': 'VSYS', 'C1': 'PWR_ON', 'C2': 'BUCK_VSET', 'B2': 'BUCK_SW', 'A2': '3V3', 'A1': GND},
        note='3.3 V buck')
    R('R267k', 'BUCK_VSET')
    C('C4u7', 'VSYS')
    L('L2u2', 'BUCK_SW', '3V3')
    C('C10u', '3V3'); C('C10u', '3V3')
    TP('3V3', 'test pad'); TP(GND, 'test pad'); TP('VSYS', 'test pad')


def mcu():
    _block[0] = 'mcu'
    gpio = {
        'D2': 'XL1', 'F2': 'XL2',
        'A12': 'PA_SRC_SYS', 'B13': 'DRONE_OK', 'J1': 'SOLAR_OK', 'K2': 'VBAT_SENSE',
        'L1': 'TEMP_ALERT', 'M2': 'DISP_SCK', 'N1': 'DISP_MOSI', 'L24': 'CHG_CE_N', 'J24': 'IO6',
        'T2': 'DISP_MISO', 'U1': 'DISP_CS', 'AD8': 'I2C_SDA', 'AC9': 'I2C_SCL',
        'AD10': 'DRONE_RX', 'AC11': 'DRONE_TX', 'AD12': 'GPS_PPS', 'AC13': 'NRF_RESET',
        'AC15': 'GPS_RX', 'AD16': 'GPS_TX', 'AC17': 'DRONE_CTS', 'AD18': 'DRONE_RTS', 'AC19': 'GPS_EN',
        'AD20': 'CHG_STAT1', 'AC21': 'CHG_STAT2', 'G1': 'DISP_DC', 'H2': 'DISP_RST',
        'B11': 'IO1', 'A10': 'IO2', 'B9': 'REFL_DET', 'A8': 'CHG_TS',
        'AD22': 'BTN_USER', 'Y23': 'PA_PWR_EN', 'W24': 'IO5', 'V23': 'LED_GREEN', 'U24': 'LED_BLUE',
        'T23': 'LNA_EN', 'R24': 'LORA_NRESET', 'P23': 'PA_EN', 'P2': 'DISP_BL', 'R1': 'GPS_RESET',
        'A20': 'LORA_NSS', 'B19': 'LORA_SCK', 'B17': 'LORA_MOSI', 'A16': 'LORA_MISO', 'B15': 'LORA_BUSY',
        'A14': 'LORA_DIO1',
    }
    # P0.09/P0.10 are NFC pins until UICR NFCPINS makes them GPIO (the
    # Adafruit bootloader does).  P1.10-P1.15 are 'low-frequency I/O' pins in
    # the PS; the SX1262 bus sits there exactly as on the RAK4631.
    pins = dict(gpio)
    pins.update({
        # normal-voltage mode: VDDH tied to VDD, REG0 unused (DCCH open)
        'Y2': '3V3', 'B1': '3V3', 'W1': '3V3', 'AD14': '3V3', 'AD23': '3V3', 'A22': '3V3', 'AB2': None,
        'B3': 'NRF_DCC', 'B5': 'NRF_DEC4', 'E24': 'NRF_DEC4', 'C1': 'NRF_DEC1', 'A18': None, 'D23': 'NRF_DEC3',
        'N24': 'NRF_DEC5', 'AD2': 'NRF_VBUS', 'AC5': 'NRF_DECUSB', 'AD6': 'NRF_DP', 'AD4': 'NRF_DM',
        'B24': 'XC1', 'A23': 'XC2', 'H23': 'NRF_ANT', 'AA24': 'SWDCLK', 'AC24': 'SWDIO',
        'B7': GND, '0': GND, 'F23': GND,
    })
    add('U', 'NRF52840', pins, note='nRF52840')
    # supply decoupling (Nordic config 2/4 values)
    C('C4u7', '3V3', note='VDD W1'); C('C1u', '3V3', note='VDD B1')
    C('C100n', '3V3', note='VDD A22'); C('C100n', '3V3', note='VDD AD23'); C('C100n', '3V3', note='VDD AD14')
    C('C4u7', '3V3', note='VDDH')
    # REG1 DC/DC: DCC -> 10 uH -> 15 nH -> DEC4 (= DEC6)
    L('L10u', 'NRF_DCC', 'NRF_DCC_L'); L('L15nH', 'NRF_DCC_L', 'NRF_DEC4')
    C('C1u', 'NRF_DEC4'); C('C47n', 'NRF_DEC4')
    C('C100n', 'NRF_DEC1'); C('C100p', 'NRF_DEC3'); C('C820p', 'NRF_DEC5', note='DEC5: needed only on older build codes; harmless')
    # USB: on-chip PHY and pull-up; 22 R pads as on Adafruit's Feather
    C('C4u7', 'NRF_VBUS', note='VBUS'); C('C4u7', 'NRF_DECUSB')
    R('R22R', 'USB_DP', 'NRF_DP'); R('R22R', 'USB_DM', 'NRF_DM')
    # 32 MHz crystal, CL 8 pF: 2 x 8 - 3 - 1 = 12 pF
    add('Y', 'XTAL32M', {'1': 'XC1', '3': 'XC2', '2': GND}, note='32 MHz')
    C('C12p', 'XC1'); C('C12p', 'XC2')
    # 32.768 kHz crystal, CL 7 pF: 2 x 7 - 4 - 1 = 9 -> 10 pF
    add('Y', 'XTAL32K', {'1': 'XL1', '2': 'XL2'}, note='32.768 kHz')
    C('RF10pF', 'XL1'); C('RF10pF', 'XL2')
    # Bluetooth: Nordic's ANT match (0.8 pF / 4.7 nH / 0.5 pF), a 50 ohm line,
    # then Johanson's tee for the chip antenna (1.0 pF / 2.7 nH / 3.9 nH). tune
    C('RF0.8pF_W', 'NRF_ANT', note='tune'); L('L4.7nH', 'NRF_ANT', 'BLE_50R', note='tune'); C('RF0.5pF', 'BLE_50R', note='tune')
    add('C', 'RF1.0pF', {'1': 'BLE_50R', '2': 'BLE_T'}, note='tune')
    L('L2.7nH', 'BLE_T', GND, note='tune'); L('L3.9nH', 'BLE_T', 'BLE_FEED', note='tune')
    add('AE', 'ANT2450', {'1': 'BLE_FEED', '2': None}, note='Bluetooth antenna')
    # debug and reset
    TP('SWDIO', 'SWD'); TP('SWDCLK', 'SWD'); TP('NRF_RESET', 'reset')


def radio():
    _block[0] = 'radio'
    add('U', 'SX1262', {'1': '3V3', '10': '3V3', '11': '3V3', '7': 'LORA_VREG', '9': 'LORA_DCC', '24': 'LORA_VRPA',
                        '3': 'LORA_XTA', '4': None, '19': 'LORA_NSS', '18': 'LORA_SCK', '17': 'LORA_MOSI',
                        '16': 'LORA_MISO', '15': 'LORA_NRESET', '23': 'LORA_RFO', '21': 'LORA_RFI_P',
                        '22': 'LORA_RFI_N', '6': 'LORA_DIO3', '12': 'LORA_DIO2', '13': 'LORA_DIO1', '14': 'LORA_BUSY',
                        '2': GND, '5': GND, '8': GND, '20': GND, '25': GND}, note='SX1262')
    C('C1u', '3V3', note='VDD_IN'); C('C100n', '3V3', note='VBAT'); C('C100n', '3V3', note='VBAT_IO')
    C('C470n', 'LORA_VREG'); L('L15u', 'LORA_DCC', 'LORA_VREG')
    # TCXO powered from DIO3; XTA through 220 R + 10 pF, XTB open
    add('Y', 'TCXO32', {'4': 'LORA_DIO3', '1': GND, '2': GND, '3': 'TCXO_OUT'}, note='32 MHz TCXO')
    C('C100n', 'LORA_DIO3')
    R('R220R', 'TCXO_OUT', 'TCXO_AC'); add('C', 'RF10pF', {'1': 'TCXO_AC', '2': 'LORA_XTA'})
    # Transmit: VR_PA feed, Semtech's high-power match and 2nd-harmonic trap
    C('C47n', 'LORA_VRPA'); C('RF47pF', 'LORA_VRPA')
    L('L47nH', 'LORA_VRPA', 'LORA_RFO', note='PA feed')
    R('R0R', 'LORA_RFO', 'LORA_TXA', note='tune')
    L('L2.5nH', 'LORA_TXA', 'LORA_TXB', note='2f trap, tune'); add('C', 'RF3.0pF', {'1': 'LORA_TXA', '2': 'LORA_TXB'}, note='2f trap, tune')
    C('RF5.6pF', 'LORA_TXB', note='tune')
    add('C', 'RF39pF', {'1': 'LORA_TXB', '2': 'LORA_TXC'})
    L('L4.7nH', 'LORA_TXC', 'LORA_TX50', note='tune'); C('RF1.8pF', 'LORA_TX50', note='tune')
    # Receive balun (single-ended from the LNA to RFI_P/RFI_N); C11 also blocks DC
    add('C', 'RF2.4pF', {'1': 'LNA_OUT', '2': 'LORA_RFI_N'}, note='tune')
    L('L15nH', 'LORA_RFI_N', 'LORA_RFI_P', note='tune'); C('RF1.8pF', 'LORA_RFI_P', note='tune')
    # DIO2 (3.3 V, high in transmit) -> 2.2 V for the switch (its CTRL <= 2.7 V)
    R('R4.7k', 'LORA_DIO2', 'RF_SW_CTRL'); R('R10k', 'RF_SW_CTRL')


def frontend():
    _block[0] = 'frontend'
    # 15.9 dB pi pad, 68 / 150 / 68 ohm, 0805 (0.125 W).  Firmware caps the
    # SX1262 at +20 dBm (SX126X_MAX_POWER): the first 68 R then takes 73 mW,
    # 58 % of its rating; +22 dBm would be 92 %.
    R('R68_0805_AS', 'LORA_TX50'); R('R150_0805', 'LORA_TX50', 'PA_DRIVE'); R('R68_0805', 'PA_DRIVE')
    # QPA9510, Qorvo EVB values (880-915 MHz), output match scaled ~2 % up. tune
    add('C', 'RF47pF', {'1': 'PA_DRIVE', '2': 'PA_RFIN'}, note='DC block')
    add('U', 'QPA9510', {'3': 'PA_RFIN', '1': 'PA_VCC1', '5': 'PA_VCC2', '6': 'PA_VCC2', '14': 'VPA', '16': 'PA_APC',
                         '15': 'PA_APC', '8': 'PA_2F0', '9': 'PA_OUT', '10': 'PA_OUT', '11': 'PA_OUT', '12': 'PA_OUT',
                         '2': GND, '4': GND, '17': GND, '7': None, '13': None}, note='3 W amplifier')
    # stage 1 supply
    add('FB', 'FB120', {'1': 'VPA', '2': 'PA_V1F'}); C('C10n', 'PA_V1F'); C('C1n', 'PA_V1F'); C('RF27pF', 'PA_V1F')
    L('L11nH_0603', 'PA_V1F', 'PA_VCC1', note='tune')
    # stage 2 supply
    C('C4u7', 'VPA'); C('C10n', 'VPA'); C('C1n', 'VPA')
    add('FB', 'FB120', {'1': 'VPA', '2': 'PA_V2F'}); C('RF15pF', 'PA_V2F')
    L('L1.6nH', 'PA_V2F', 'PA_VCC2', note='tune'); C('RF27pF', 'PA_VCC2'); C('RF27pF', 'PA_VCC2')
    C('RF47pF', 'VPA', note='bias pin 14')
    C('RF1.5pF', 'PA_2F0', note='2nd-harmonic termination, tune')
    C('C10n', 'PA_APC'); C('C10n', 'PA_APC')
    # output stage: collector choke from VPA (carries ~1.7 A), match, DC block
    L('L8.1nH_PA', 'VPA', 'PA_OUT', note='collector choke')
    C('C4u7', 'VPA'); C('C1n', 'VPA'); C('RF47pF', 'VPA')
    C('HV15pF', 'PA_OUT', note='tune'); C('HV10pF', 'PA_OUT', note='tune')
    L('L3.6nH_0805', 'PA_OUT', 'PA_M1', note='tune'); C('HV5.6pF', 'PA_M1', note='tune')
    add('C', 'HV47pF', {'1': 'PA_M1', '2': 'PA_M2'}, note='DC block')
    # LPF1: 5th-order elliptic, notches near 1.4 and 2.3 GHz (sim/rf: chosen for the
    # lowest loss with the LFCN-1000+ carrying 2f-5f; 0.4 dB less loss than the
    # textbook 2f/3f notches, so 3 W still reaches the U.FL). tune
    C('HV2.0pF', 'PA_M2')
    L('L3.2nH_0805', 'PA_M2', 'PA_M3'); add('C', 'HV3.6pF', {'1': 'PA_M2', '2': 'PA_M3'})
    C('HV1.3pF', 'PA_M3')
    L('L3.2nH_0805', 'PA_M3', 'PA_TX'); add('C', 'HV1.3pF', {'1': 'PA_M3', '2': 'PA_TX'})
    C('HV0.9pF', 'PA_TX')
    # SKY13330: CTRL high (transmit) = RF1-RF2, low = RF1-RF3; ENABLE 2.0 V
    add('U', 'SKY13330', {'11': 'PA_TX', '5': 'RX_SW', '2': 'ANT_SW', '7': 'RF_SW_CTRL', '8': 'RF_SW_EN', '9': '3V3',
                          '1': GND, '3': GND, '4': GND, '6': GND, '10': GND, '12': GND, '13': GND}, note='antenna switch')
    R('R220k', '3V3', 'RF_SW_EN'); R('R330k', 'RF_SW_EN')
    C('C100p', '3V3'); C('C10n', '3V3')
    # antenna path: LFCG-1000+ low-pass, 47 nH shunt to ground (ESD, ~transparent at 915 MHz), U.FL
    add('FL', 'LFCG1000', {'8': 'ANT_SW', '4': 'ANT', '1': GND, '2': GND, '3': GND, '5': GND, '6': GND, '7': GND},
        note='antenna low-pass')
    # missing-antenna detector: a printed line beside the ANT line (layout.py),
    # terminated in 49.9 R at its filter end; at its U.FL end the reflected
    # wave is rectified into REFL_DET (P0.30, AIN6).  With the antenna off, firmware
    # sees it ~1 ms into a packet and cuts the amplifier (sim/rf follow-up).
    R('R49.9R', 'REFL_CPL'); add('D', 'BAT15', {'2': 'REFL_CPL', '1': 'REFL_DET'}, note='reflected-wave detector')
    C('C1n', 'REFL_DET'); R('R100k', 'REFL_DET')
    L('L47nH', 'ANT', GND, note='antenna ESD shunt')
    add('J', 'UFL', {'1': 'ANT', '2': GND, '3': GND}, note='LoRa antenna')
    # LNA: DC block, 11 nH input match; C high = gain, low = bypass
    add('C', 'C1n', {'1': 'RX_SW', '2': 'LNA_INM'}, note='DC block (AI must stay below 0.9 V DC)')
    L('L11nH', 'LNA_INM', 'LNA_AI', note='tune')
    add('U', 'BGA7L1BN6', {'5': 'LNA_AI', '2': '3V3', '6': 'LNA_EN', '3': 'LNA_OUT', '1': GND, '4': GND}, note='LNA')
    C('C1n', '3V3'); C('C100n', '3V3')


def pa_power():
    _block[0] = 'pa_power'
    # TPS2121: IN1 (battery) has priority above 2.65 V, falling 2.60 V (PR1
    # 562 k / 374 k): at 3.04 V (301 k) a worn or cold cell's sag in a burst
    # switched the mux over, and its 100 us gap reset the TPS63810
    # (sim/burst).  IN2 = charger SYS.  With no cell fitted the charger
    # holds BAT_P up and the mux would pick it: firmware then sets
    # PA_SRC_SYS (P0.02), whose N-FET pulls PR1 low so IN2 is used.  OV1/OV2 pulled up = both inputs off; the N-FET pulls
    # them low while the amplifier is enabled (PA_PWR_EN), so its 0.3 mA runs
    # only when firmware wants the amplifier.  ILM 22.1 k -> 4.5 A; ST unused
    # (grounded, per the datasheet).
    add('U', 'TPS2121', {'7': 'BAT_P', '2': 'VSYS', '6': 'MUX_PR1', '5': 'MUX_OFF', '4': 'MUX_OFF', '3': GND,
                         '1': 'PA_IN', '8': 'PA_IN', '9': GND, '10': 'MUX_ILM', '11': 'MUX_SS', '12': GND},
        note='amplifier power mux')
    R('R562k', 'BAT_P', 'MUX_PR1'); R('R374k', 'MUX_PR1')
    add('Q', 'NMOS', {'3': 'MUX_PR1', '2': GND, '1': 'PA_SRC_SYS'}, note='amplifier from SYS (no cell)')
    R('R1M', 'PA_SRC_SYS', note='battery first unless firmware says otherwise')
    R('R1M', 'BAT_P', 'MUX_OFF')
    add('Q', 'NMOS', {'3': 'MUX_OFF', '2': GND, '1': 'PA_PWR_EN'}, note='mux on with the amplifier')
    R('R22.1k', 'MUX_ILM'); C('C10n', 'MUX_SS')
    C('C1u25', 'BAT_P'); C('C1u25', 'VSYS')
    C('C22u16', 'PA_IN'); C('C22u16', 'PA_IN')
    # TPS63810 buck-boost: I2C 0x75; VOUT = 1.8 V + 25 mV x code (VSEL tied
    # low: VOUT1 only, as firmware always used it); boots at 3.3 V
    # and loses its registers when the mux removes its input, so firmware
    # writes them after every enable.  EN from the processor (1 M down: off
    # until firmware wants it).  Firmware ceiling 3.6 V (~34 dBm): the QPA9510
    # is rated for a 10:1 mismatch (a missing antenna) at 3.6 V only; 4.0 V
    # (~35 dBm) is an opt-in setting for a known-good antenna.
    add('U', 'TPS63810', {'A2': 'PA_IN', 'A3': 'PA_IN', 'A1': 'PA_PWR_EN', 'B1': GND, 'D1': 'I2C_SCL',
                          'E1': 'I2C_SDA', 'B2': 'PA_LX1', 'B3': 'PA_LX1', 'D2': 'PA_LX2', 'D3': 'PA_LX2',
                          'E2': 'VPA', 'E3': 'VPA', 'C1': GND, 'C2': GND, 'C3': GND}, note='amplifier buck-boost')
    R('R1M', 'PA_PWR_EN')
    C('C10u25', 'PA_IN')
    L('L470n', 'PA_LX1', 'PA_LX2')
    C('C47u', 'VPA', note='1206 X7S'); C('C47u', 'VPA', note='1206 X7S'); C('C100n', 'VPA')
    # amplifier control voltage: 2.8 V only while transmitting (EN = PA_EN, the
    # firmware's TXEN); both APC pins at 0 V = amplifier standby (58 uA)
    add('U', 'TLV75528', {'4': '3V3', '3': 'PA_EN', '1': 'PA_APC', '2': GND, '5': GND}, note='APC supply')
    C('C1u', '3V3'); C('C1u', 'PA_APC')
    R('R100k', 'PA_EN', note='amplifier off while the processor boots')
    # temperature beside the amplifier, I2C 0x48, for thermal throttling
    add('U', 'TMP1075', {'5': '3V3', '4': GND, '6': 'I2C_SDA', '1': 'I2C_SCL', '3': 'TEMP_ALERT', '2': GND},
        note='amplifier temperature')
    C('C100n', '3V3')
    R('R100k', 'TEMP_ALERT', '3V3')
    R('R4.7k', 'I2C_SDA', '3V3'); R('R4.7k', 'I2C_SCL', '3V3')


def ports():
    _block[0] = 'ports'
    # Drone port, JST-GH 6, Pixhawk TELEM pinout seen from the autopilot:
    # 1 +5V (into this board), 2 TX (autopilot out), 3 RX (autopilot in),
    # 4 CTS (autopilot in), 5 RTS (autopilot out), 6 GND.  470 R in series on
    # every line limits current into an unpowered board or drone.
    add('J', 'JST_GH6', {'1': 'DRONE_5V_CONN', '2': 'DRN_P2', '3': 'DRN_P3', '4': 'DRN_P4', '5': 'DRN_P5', '6': GND,
                         '7': None, '8': None}, note='drone port')
    R('R470R', 'DRN_P2', 'DRONE_RX'); R('R470R', 'DRONE_TX', 'DRN_P3')
    R('R470R', 'DRONE_RTS', 'DRN_P4'); R('R470R', 'DRN_P5', 'DRONE_CTS')
    add('D', 'TPD4E05U06', {'1': 'DRN_P2', '2': 'DRN_P3', '4': 'DRN_P4', '5': 'DRN_P5', '3': GND, '8': GND,
                            '6': None, '7': None, '9': None, '10': None}, note='drone ESD')
    # GPS add-on, JST-SH 6: 1 3V3 (switched), 2 GPS TX, 3 GPS RX, 4 PPS, 5 RESET, 6 GND.
    # Firmware sets these pins to inputs whenever GPS power is off, so the
    # processor never feeds an unpowered module through its pins.
    add('J', 'JST_SH6', {'1': '3V3_GPS', '2': 'GPS_P2', '3': 'GPS_P3', '4': 'GPS_P4', '5': 'GPS_P5', '6': GND,
                         '7': None, '8': None}, note='GPS add-on')
    R('R470R', 'GPS_P2', 'GPS_RX'); R('R470R', 'GPS_TX', 'GPS_P3')
    R('R470R', 'GPS_P4', 'GPS_PPS'); R('R470R', 'GPS_RESET', 'GPS_P5')
    add('D', 'TPD4E05U06', {'1': 'GPS_P2', '2': 'GPS_P3', '4': 'GPS_P4', '5': 'GPS_P5', '3': GND, '8': GND,
                            '6': None, '7': None, '9': None, '10': None}, note='GPS ESD')
    add('U', 'TPS22916', {'A2': '3V3', 'B2': 'GPS_EN', 'A1': '3V3_GPS', 'B1': GND}, note='GPS power switch')
    R('R1M', 'GPS_EN'); C('C1u', '3V3_GPS')
    # Expansion header (fitted only when needed): a generic SPI display, I2C, four
    # spare pins (P0.30 / P0.31 read the antenna detector and the charger's NTC)
    add('J', 'HDR_2x10', {'1': '3V3', '2': GND, '3': 'I2C_SDA', '4': 'I2C_SCL', '5': 'DISP_SCK', '6': 'DISP_MOSI',
                          '7': 'DISP_MISO', '8': 'DISP_CS', '9': 'DISP_DC', '10': 'DISP_RST', '11': 'DISP_BL',
                          '12': 'IO1', '13': 'IO2', '14': None, '15': None, '16': 'IO5', '17': 'IO6',
                          '18': GND, '19': GND, '20': '3V3'}, note='expansion header')
    # Buttons (by the USB-C, as on the Heltec V4) and LEDs (active high, as RAK4631)
    add('SW', 'SKRP', {'1': 'NRF_RESET', '2': 'NRF_RESET', '3': GND, '4': GND}, note='reset')
    add('SW', 'SKRP', {'1': 'BTN_USER', '2': 'BTN_USER', '3': GND, '4': GND}, note='user')
    R('R1k', 'LED_GREEN', 'LED_G_A'); add('LED', 'LED_G', {'2': 'LED_G_A', '1': GND}, note='green')
    R('R220R', 'LED_BLUE', 'LED_B_A'); add('LED', 'LED_B', {'2': 'LED_B_A', '1': GND}, note='blue')
