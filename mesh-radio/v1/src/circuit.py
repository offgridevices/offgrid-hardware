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
POWER_NETS = ['GND', '3V3', 'VSYS', 'VSYS_SW', 'BAT_P', 'VPA', 'PA_IN', 'USB_5V', 'VIN_CHG', '3V3_GPS']

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
    'inputs': 'Every input: flat-clamp or bidirectional TVS, then a TPS259470A eFuse (over-voltage cut-off,\n'
              'current limit, reverse blocking). USB 5.8 V / 1.5 A, drone 5.8 V / 1.3 A, solar 10 V / 1.3 A.',
    'charger': 'Battery plug wired the Adafruit/SparkFun way (pad 1 = +). Cell protection on the minus side\n'
               '(OCD ~4.1 A, SCD ~21 A, OV 4.275 V, UV 2.8 V); reverse-battery P-FET on the plus side.',
    'system': 'The slide switch only drives the load switch enable; charging works with the board switched off.',
    'mcu': 'nRF52840 in normal-voltage mode: VDD = VDDH = the 3.3 V rail, so its pins and the SX1262 share one\n'
           'logic level. REG1 DC/DC on (10 uH + 15 nH). Nordic reference circuit, aQFN73.',
    'radio': 'Semtech SX1262MB2CAS (915 MHz) reference values. TCXO on DIO3 (set 2.2 V in firmware), DIO2 drives\n'
             'the antenna switch.',
    'frontend': 'Drive: SX1262 +11 dBm -> 30 dBm (1 W), +17 dBm -> ~35 dBm (3 W). The 15.9 dB pad keeps the\n'
                'amplifier input below its +13 dBm limit even at the SX1262 maximum (+22 dBm -> +6 dBm).',
    'pa_power': 'Amplifier runs from the battery through a power mux (charger SYS only when no battery), then a\n'
                'TPS63810 buck-boost set over I2C (0x75): ~2.7 V for 1 W, up to 4.0 V for 3 W.',
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
def efuse(name, raw, out, uv_bottom, ov_bottom, ilm, ok_net):
    """TPS259470A: UVLO/OVLO = 1.20 V x (1 M + Rb) / Rb (1 M tops: the
    datasheet asks for >= 350 k where the input can exceed 5 V or reverse),
    ILIM = 3334 / RILM, DVDT 1 nF (2 V/ms), ITIMER 1 nF.  AUXOFF ("input
    good") goes to the processor; FLT is left open because on an OR-ed
    input it also flags normal reverse blocking."""
    add('U', 'TPS259470A', {'5': raw, '6': out, '1': name + '_UV', '2': name + '_OV', '7': name + '_DVDT',
                            '9': name + '_ILM', '10': name + '_TMR', '3': ok_net, '4': None, '8': GND},
        note=name + ' eFuse')
    R('R1M', raw, name + '_UV'); R(uv_bottom, name + '_UV')
    R('R1M', raw, name + '_OV'); R(ov_bottom, name + '_OV')
    R(ilm, name + '_ILM')
    C('C1n', name + '_DVDT'); C('C1n', name + '_TMR')
    C('C1u25', raw, note='eFuse input, 25 V')
    if ok_net:
        R('R100k', ok_net, '3V3', note='input-good pull-up')


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
    efuse('USB', 'USB_VBUS', 'USB_5V', 'R383k', 'R261k', 'R2.21k', None)
    # USB_5V feeds the nRF52840 VBUS pin (USB detect and its USB PHY) and,
    # through a Schottky, the charger.  The 47 k drains Schottky leakage so
    # VBUS never reads "present" from solar or drone power.
    R('R47k', 'USB_5V', note='VBUS bleed')
    add('D', 'RB060MM', {'2': 'USB_5V', '1': 'VIN_CHG'}, note='USB into the charger')

    # Solar panel, 5-6 V nominal (rejects anything above 10 V); a reversed
    # panel is held by the bidirectional TVS and the eFuse (-15 V rated)
    add('J', 'JST_SH2', {'1': 'SOLAR_RAW', '2': GND, '3': None, '4': None}, note='solar input')
    add('D', 'SMF15CA', {'1': 'SOLAR_RAW', '2': GND}, note='solar TVS')
    efuse('SOL', 'SOLAR_RAW', 'VIN_CHG', 'R510k', 'R137k', 'R2.49k', 'SOLAR_OK')

    # Drone 5 V from the JST-GH drone port (charges the cell while carried)
    add('D', 'SMF15CA', {'1': 'DRONE_5V_RAW', '2': GND}, note='drone 5 V TVS')
    efuse('DRN', 'DRONE_5V_RAW', 'VIN_CHG', 'R383k', 'R261k', 'R2.49k', 'DRONE_OK')


def charger():
    _block[0] = 'charger'
    # BQ25185: ISET 604 R -> 500 mA charge (300 A.ohm / R); ILIM/VSET 13 k ->
    # 4.2 V and 1.1 A input limit (datasheet table 6-1); NTC on TS, hot/cold
    # cut-off at about 60 C / 0 C, placed at the battery plug.
    add('U', 'BQ25185', {'10': 'VIN_CHG', '1': 'VSYS', '2': 'BAT_P', '4': 'CHG_CE_N', '6': 'CHG_TS',
                         '7': 'CHG_ILIM', '8': 'CHG_ISET', '9': 'CHG_STAT1', '3': 'CHG_STAT2', '5': GND, '11': GND},
        note='charger')
    C('C1u25', 'VIN_CHG'); C('C10u25', 'VIN_CHG')
    C('C10u25', 'VSYS'); C('C10u25', 'BAT_P')
    R('R604R', 'CHG_ISET'); R('R13k', 'CHG_ILIM')
    add('TH', 'NTC10K', {'1': 'CHG_TS', '2': GND}, note='battery temperature')
    R('R100k', 'CHG_CE_N', note='charge enabled unless the processor says otherwise')
    R('R10k', 'CHG_STAT1', '3V3'); R('R10k', 'CHG_STAT2', '3V3')
    add('LED', 'LED_R', {'1': 'CHG_STAT1', '2': 'CHG_LED_A'}, note='charging (red)')
    R('R1k', 'CHG_LED_A', '3V3')

    # Battery plug, Adafruit/SparkFun polarity: pad 1 = +, pad 2 = -
    # (from the footprint geometry against Adafruit's; check with a meter on a
    # real Adafruit cell before ordering, docs/plan.md)
    add('J', 'JST_PH2', {'1': 'BATT_PLUS', '2': 'CELL_MINUS', '3': None, '4': None}, note='battery')
    # Reverse battery: P-FET on the plus side, gate to ground.  A cell
    # plugged in backwards leaves it off (body diode reversed).
    add('Q', 'CSD25485F5', {'3': 'BATT_PLUS', '2': 'BAT_P', '1': 'REV_G'}, note='reverse-battery FET')
    R('R100k', 'REV_G')
    # Cell protection for unprotected cells: BQ29700 on the minus side, two
    # back-to-back FETs, 22 mOhm sense so OCD = 100 mV / 24.2 mOhm = 4.1 A
    # and SCD = 500 mV / 24.2 mOhm = 21 A.  Its supply comes from BAT_P
    # (after the reverse FET) so a reversed cell never reaches its BAT pin.
    add('U', 'BQ29700', {'5': 'PROT_BAT', '4': 'CELL_MINUS', '6': 'PROT_VM', '3': 'PROT_DOUT', '2': 'PROT_COUT',
                         '1': None}, note='cell protector')
    R('R330R', 'BAT_P', 'PROT_BAT'); C('C100n', 'PROT_BAT', 'CELL_MINUS')
    R('R2.2k', 'PROT_VM', GND)
    add('Q', 'SSM10N954L', {'3': 'PROT_DOUT', '1': 'CELL_MINUS', '2': 'CELL_MINUS', '4': 'CELL_MINUS', '5': 'CELL_MINUS',
                            '8': 'PROT_COUT', '6': 'PROT_S2', '7': 'PROT_S2', '9': 'PROT_S2', '10': 'PROT_S2'},
        note='protection FETs')
    R('R22m', 'PROT_S2', GND, note='current sense')
    # Battery voltage for the firmware: 1 M / 1.5 M as on the RAK4631
    # (ADC multiplier 1.667), 1.7 uA
    R('R1M', 'BAT_P', 'VBAT_SENSE'); R('R1.5M', 'VBAT_SENSE'); C('C100n', 'VBAT_SENSE')


def system():
    _block[0] = 'system'
    add('SW', 'SLIDE', {'2': 'PWR_ON', '1': 'VSYS', '3': None}, note='power switch')
    R('R1M', 'PWR_ON', note='off when the switch is open')
    # TPS22965: CT 1 nF -> ~1.5 ms soft start; VBIAS from VSYS
    add('U', 'TPS22965', {'1': 'VSYS', '2': 'VSYS', '4': 'VSYS', '3': 'PWR_ON', '6': 'SW_CT', '7': 'VSYS_SW',
                          '8': 'VSYS_SW', '5': GND, '9': GND}, note='main power switch')
    C('C1n', 'SW_CT'); C('C1u25', 'VSYS'); C('C10u', 'VSYS_SW')
    # TPS62840: VSET 267 k -> 3.3 V; 100 % mode below 3.3 V in
    add('U', 'TPS62840', {'B1': 'VSYS_SW', 'C1': 'VSYS_SW', 'C2': 'BUCK_VSET', 'B2': 'BUCK_SW', 'A2': '3V3', 'A1': GND},
        note='3.3 V buck')
    R('R267k', 'BUCK_VSET')
    C('C4u7', 'VSYS_SW')
    L('L2u2', 'BUCK_SW', '3V3')
    C('C10u', '3V3'); C('C10u', '3V3')
    TP('3V3', 'test pad'); TP(GND, 'test pad'); TP('VSYS', 'test pad')


def mcu():
    _block[0] = 'mcu'
    gpio = {
        'D2': 'XL1', 'F2': 'XL2',
        'A12': 'PA_VSEL', 'B13': 'DRONE_OK', 'J1': 'SOLAR_OK', 'K2': 'VBAT_SENSE',
        'L1': 'TEMP_ALERT', 'M2': 'DISP_SCK', 'N1': 'DISP_MOSI', 'L24': 'IO6', 'J24': None,
        'T2': 'DISP_MISO', 'U1': 'DISP_CS', 'AD8': 'I2C_SDA', 'AC9': 'I2C_SCL',
        'AD10': 'DRONE_RX', 'AC11': 'DRONE_TX', 'AD12': 'GPS_PPS', 'AC13': 'NRF_RESET',
        'AC15': 'GPS_RX', 'AD16': 'GPS_TX', 'AC17': 'DRONE_CTS', 'AD18': 'DRONE_RTS', 'AC19': 'GPS_EN',
        'AD20': 'CHG_STAT1', 'AC21': 'CHG_STAT2', 'G1': 'DISP_DC', 'H2': 'DISP_RST',
        'B11': 'IO1', 'A10': 'IO2', 'B9': 'IO3', 'A8': 'IO4',
        'AD22': 'BTN_USER', 'Y23': 'PA_PWR_EN', 'W24': 'IO5', 'V23': 'LED_GREEN', 'U24': 'LED_BLUE',
        'T23': 'LNA_EN', 'R24': 'LORA_NRESET', 'P23': 'PA_EN', 'P2': 'DISP_BL', 'R1': 'GPS_RESET',
        'A20': 'LORA_NSS', 'B19': 'LORA_SCK', 'B17': 'LORA_MOSI', 'A16': 'LORA_MISO', 'B15': 'LORA_BUSY',
        'A14': 'LORA_DIO1',
    }
    pins = dict(gpio)
    pins.update({
        # normal-voltage mode: VDDH tied to VDD, REG0 unused (DCCH open)
        'Y2': '3V3', 'B1': '3V3', 'W1': '3V3', 'AD14': '3V3', 'AD23': '3V3', 'A22': '3V3', 'AB2': None,
        'B3': 'NRF_DCC', 'B5': 'NRF_DEC4', 'E24': 'NRF_DEC4', 'C1': 'NRF_DEC1', 'A18': None, 'D23': 'NRF_DEC3',
        'N24': 'NRF_DEC5', 'AD2': 'USB_5V', 'AC5': 'NRF_DECUSB', 'AD6': 'NRF_DP', 'AD4': 'NRF_DM',
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
    C('C4u7', 'USB_5V', note='VBUS'); C('C4u7', 'NRF_DECUSB')
    R('R22R', 'USB_DP', 'NRF_DP'); R('R22R', 'USB_DM', 'NRF_DM')
    # 32 MHz crystal, CL 8 pF: 2 x 8 - 3 - 1 = 12 pF
    add('Y', 'XTAL32M', {'1': 'XC1', '3': 'XC2', '2': GND}, note='32 MHz')
    C('C12p', 'XC1'); C('C12p', 'XC2')
    # 32.768 kHz crystal, CL 7 pF: 2 x 7 - 4 - 1 = 9 -> 10 pF
    add('Y', 'XTAL32K', {'1': 'XL1', '2': 'XL2'}, note='32.768 kHz')
    C('RF10pF', 'XL1'); C('RF10pF', 'XL2')
    # Bluetooth: Nordic's ANT match (0.8 pF / 4.7 nH / 0.5 pF), a 50 ohm line,
    # then Johanson's tee for the chip antenna (1.0 pF / 2.7 nH / 3.9 nH). tune
    C('RF0.8pF', 'NRF_ANT', note='tune'); L('L4.7nH', 'NRF_ANT', 'BLE_50R', note='tune'); C('RF0.5pF', 'BLE_50R', note='tune')
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
    # 15.9 dB pi pad, 68 / 150 / 68 ohm, 0805 (0.125 W: +20 dBm worst into it)
    R('R68_0805', 'LORA_TX50'); R('R150_0805', 'LORA_TX50', 'PA_DRIVE'); R('R68_0805', 'PA_DRIVE')
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
    L('L3.6nH_0603', 'PA_OUT', 'PA_M1', note='tune'); C('HV5.6pF', 'PA_M1', note='tune')
    add('C', 'HV47pF', {'1': 'PA_M1', '2': 'PA_M2'}, note='DC block')
    # LPF1: 5th-order elliptic, fc ~1.05 GHz, notches at 2f and 3f. tune
    C('HV3.3pF', 'PA_M2')
    L('L5.1nH', 'PA_M2', 'PA_M3'); add('C', 'HV1.5pF', {'1': 'PA_M2', '2': 'PA_M3'})
    C('HV4.3pF', 'PA_M3')
    L('L4.7nH_0603', 'PA_M3', 'PA_TX'); add('C', 'HV0.7pF', {'1': 'PA_M3', '2': 'PA_TX'})
    C('HV2.7pF', 'PA_TX')
    # SKY13330: CTRL high (transmit) = RF1-RF2, low = RF1-RF3; ENABLE 2.0 V
    add('U', 'SKY13330', {'11': 'PA_TX', '5': 'RX_SW', '2': 'ANT_SW', '7': 'RF_SW_CTRL', '8': 'RF_SW_EN', '9': '3V3',
                          '1': GND, '3': GND, '4': GND, '6': GND, '10': GND, '12': GND, '13': GND}, note='antenna switch')
    R('R220k', '3V3', 'RF_SW_EN'); R('R330k', 'RF_SW_EN')
    C('C100p', '3V3'); C('C10n', '3V3')
    # antenna path: LFCN-1000+ low-pass, 47 nH shunt to ground (ESD, ~transparent at 915 MHz), U.FL
    add('FL', 'LFCN1000', {'1': 'ANT_SW', '3': 'ANT', '2': GND, '4': GND}, note='antenna low-pass')
    L('L47nH', 'ANT', GND, note='antenna ESD shunt')
    add('J', 'UFL', {'1': 'ANT', '2': GND, '3': GND}, note='LoRa antenna')
    # LNA: DC block, 11 nH input match; C high = gain, low = bypass
    add('C', 'C1n', {'1': 'RX_SW', '2': 'LNA_INM'}, note='DC block (AI must stay below 0.9 V DC)')
    L('L11nH', 'LNA_INM', 'LNA_AI', note='tune')
    add('U', 'BGA7L1BN6', {'5': 'LNA_AI', '2': '3V3', '6': 'LNA_EN', '3': 'LNA_OUT', '1': GND, '4': GND}, note='LNA')
    C('C1n', '3V3'); C('C100n', '3V3')


def pa_power():
    _block[0] = 'pa_power'
    # TPS2121: IN1 (battery) has priority above 3.04 V (PR1 562 k / 301 k);
    # IN2 = charger SYS.  OV1/OV2 pulled up = both inputs off; the N-FET pulls
    # them low while the board is switched on, so a switched-off board draws
    # only the mux's standby current.  ILM 22.1 k -> 4.5 A.
    add('U', 'TPS2121', {'7': 'BAT_P', '2': 'VSYS', '6': 'MUX_PR1', '5': 'MUX_OFF', '4': 'MUX_OFF', '3': GND,
                         '1': 'PA_IN', '8': 'PA_IN', '9': None, '10': 'MUX_ILM', '11': 'MUX_SS', '12': GND},
        note='amplifier power mux')
    R('R562k', 'BAT_P', 'MUX_PR1'); R('R301k', 'MUX_PR1')
    R('R1M', 'BAT_P', 'MUX_OFF')
    add('Q', 'NMOS', {'3': 'MUX_OFF', '2': GND, '1': 'VSYS_SW'}, note='mux on with the board')
    R('R22.1k', 'MUX_ILM'); C('C10n', 'MUX_SS')
    C('C1u25', 'BAT_P'); C('C1u25', 'VSYS')
    C('C22u25', 'PA_IN'); C('C22u25', 'PA_IN')
    # TPS63810 buck-boost: I2C 0x75; VOUT = 1.8 V + 25 mV x code; boots at 3.3 V.
    # EN from the processor (1 M down: off until firmware wants it).
    add('U', 'TPS63810', {'A2': 'PA_IN', 'A3': 'PA_IN', 'A1': 'PA_PWR_EN', 'B1': 'PA_VSEL', 'D1': 'I2C_SCL',
                          'E1': 'I2C_SDA', 'B2': 'PA_LX1', 'B3': 'PA_LX1', 'D2': 'PA_LX2', 'D3': 'PA_LX2',
                          'E2': 'VPA', 'E3': 'VPA', 'C1': GND, 'C2': GND, 'C3': GND}, note='amplifier buck-boost')
    R('R1M', 'PA_PWR_EN'); R('R1M', 'PA_VSEL')
    C('C10u25', 'PA_IN')
    L('L470n', 'PA_LX1', 'PA_LX2')
    C('C47u', 'VPA'); C('C47u', 'VPA'); C('C100n', 'VPA')
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
    add('J', 'JST_GH6', {'1': 'DRONE_5V_RAW', '2': 'DRN_P2', '3': 'DRN_P3', '4': 'DRN_P4', '5': 'DRN_P5', '6': GND,
                         '7': None, '8': None}, note='drone port')
    R('R470R', 'DRN_P2', 'DRONE_RX'); R('R470R', 'DRONE_TX', 'DRN_P3')
    R('R470R', 'DRONE_RTS', 'DRN_P4'); R('R470R', 'DRN_P5', 'DRONE_CTS')
    add('D', 'TPD4E05U06', {'1': 'DRN_P2', '2': 'DRN_P3', '4': 'DRN_P4', '5': 'DRN_P5', '3': GND, '8': GND,
                            '6': None, '7': None, '9': None, '10': None}, note='drone ESD')
    # GPS add-on, JST-SH 6: 1 3V3 (switched), 2 GPS TX, 3 GPS RX, 4 PPS, 5 RESET, 6 GND
    add('J', 'JST_SH6', {'1': '3V3_GPS', '2': 'GPS_P2', '3': 'GPS_P3', '4': 'GPS_P4', '5': 'GPS_P5', '6': GND,
                         '7': None, '8': None}, note='GPS add-on')
    R('R470R', 'GPS_P2', 'GPS_RX'); R('R470R', 'GPS_TX', 'GPS_P3')
    R('R470R', 'GPS_P4', 'GPS_PPS'); R('R470R', 'GPS_RESET', 'GPS_P5')
    add('D', 'TPD4E05U06', {'1': 'GPS_P2', '2': 'GPS_P3', '4': 'GPS_P4', '5': 'GPS_P5', '3': GND, '8': GND,
                            '6': None, '7': None, '9': None, '10': None}, note='GPS ESD')
    add('U', 'TPS22916', {'A2': '3V3', 'B2': 'GPS_EN', 'A1': '3V3_GPS', 'B1': GND}, note='GPS power switch')
    R('R1M', 'GPS_EN'); C('C1u', '3V3_GPS')
    # Expansion header (fitted only when needed): a generic SPI display, I2C, six spare pins
    add('J', 'HDR_2x10', {'1': '3V3', '2': GND, '3': 'I2C_SDA', '4': 'I2C_SCL', '5': 'DISP_SCK', '6': 'DISP_MOSI',
                          '7': 'DISP_MISO', '8': 'DISP_CS', '9': 'DISP_DC', '10': 'DISP_RST', '11': 'DISP_BL',
                          '12': 'IO1', '13': 'IO2', '14': 'IO3', '15': 'IO4', '16': 'IO5', '17': 'IO6',
                          '18': 'VSYS_SW', '19': GND, '20': '3V3'}, note='expansion header')
    # Buttons (by the USB-C, as on the Heltec V4) and LEDs (active high, as RAK4631)
    add('SW', 'B3U', {'1': 'NRF_RESET', '2': GND}, note='reset')
    add('SW', 'B3U', {'1': 'BTN_USER', '2': GND}, note='user')
    R('R1k', 'LED_GREEN', 'LED_G_A'); add('LED', 'LED_G', {'2': 'LED_G_A', '1': GND}, note='green')
    R('R1k', 'LED_BLUE', 'LED_B_A'); add('LED', 'LED_B', {'2': 'LED_B_A', '1': GND}, note='blue')
