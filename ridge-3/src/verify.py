# -*- coding: utf-8 -*-
"""Design verification: every check that can be made without hardware.

    python3 verify.py        writes ../VERIFICATION.md, exits 1 on any FAIL

Nothing here replaces a bench test.  What it does is check the design
against sources other than the design itself:

  * the MCU pin maps against KiCad's own STM32 symbol libraries (pin number
    -> port) and against the firmware sources (Betaflight config.h, AM32
    targets.h): the pin each firmware drives carries the right net
  * every power pin of every MCU against the rail it needs
  * the regulator, divider and gate-drive arithmetic, from the resistor and
    capacitor values in circuit.py
  * the installed boards: DRC, netlist, fab outputs, stackup
  * the silkscreen: every stroke printable, the mark against the brand art
  * the firmware's scale factors (battery dividers, current sense) against
    the circuit, and the AM32 target patch applied to the AM32 source
  * the firmware images against the hashes in firmware/README.md
"""
import math, os, re, sys, hashlib, glob, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, parts, fab

SYMBOLS = '/usr/share/kicad/symbols'
BRAND_PNG = os.environ.get('OFFGRID_BRAND', '/home/user/offgrid-brand') + \
    '/current/handoff/logo/png/offgrid-wordmark-horizontal-1600.png'

rows = []            # (section, check, result, detail)


def check(section, name, ok, detail=''):
    if hasattr(ok, 'item'):          # numpy bool
        ok = bool(ok)
    rows.append((section, name, 'PASS' if ok is True else ('FAIL' if ok is False else ok), detail))


# ------------------------------------------------------------------ helpers
def symbol_pins(lib, name):
    """pin number -> pin name, from a KiCad symbol (following 'extends')."""
    text = open(os.path.join(SYMBOLS, lib + '.kicad_sym')).read()
    i = text.index('\t(symbol "%s"' % name)
    j = text.find('\n\t(symbol "', i + 5)
    block = text[i:j if j > 0 else len(text)]
    m = re.search(r'\(extends "([^"]+)"\)', block)
    if m:
        return symbol_pins(lib, m.group(1))
    pins = {}
    for chunk in block.split('(pin ')[1:]:
        nm = re.search(r'\(name "([^"]*)"', chunk)
        no = re.search(r'\(number "([^"]*)"', chunk)
        if nm and no:
            pins[no.group(1)] = nm.group(1)
    return pins


def comp(board, ref):
    return [c for c in circuit.build(board) if c.ref == ref][0]


def port_nets(board, ref, lib, sym):
    """port name (PA0...) -> net, and power pin name -> [nets]."""
    pins = symbol_pins(lib, sym)
    c = comp(board, ref)
    ports, power = {}, {}
    for num, name in pins.items():
        net = c.pins.get(num)
        base = name.split('-')[0].split('/')[0]
        if re.match(r'P[A-G]\d+$', base):
            ports[base] = net
        else:
            power.setdefault(name, []).append(net)
    return ports, power, pins, c


def value(part):
    """R15K -> 15e3, R2K2 -> 2.2e3, R750 -> 750, C10U50 -> 10e-6, C12P -> 12e-12."""
    m = re.match(r'([RC])(\d+)([KMUNP]?)(\d*)', part)
    kind, a, unit, b = m.groups()
    mult = {'': 1, 'K': 1e3, 'M': 1e6, 'U': 1e-6, 'N': 1e-9, 'P': 1e-12}[unit]
    if kind == 'C' and unit == 'U' and b and len(b) == 2:      # C10U50: 10 uF, 50 V
        b = ''
    num = float(a + ('.' + b if b else ''))
    return num * mult


def find(board, note):
    return [c for c in circuit.build(board) if c.note == note]


# ------------------------------------------------------------------ firmware sources
FW = os.path.join(V1, 'firmware')
BF_CONFIGS = ('RIDGE3', 'RIDGE3_ICM')           # BMI270 build, ICM-42688-P build
AM32_PATCH = 'am32/AM32_55c9684_RIDGE3_G071_targets.patch'
AM32_COMMIT = '55c9684'
AM32_TARGET = 'RIDGE3_G071'
AM32 = os.environ.get('AM32_SRC', '')


def bf_configs():
    return {k: open(os.path.join(FW, 'betaflight/configs/%s/config.h' % k)).read() for k in BF_CONFIGS}


def cdefine(text, name):
    """The value of '#define NAME value' in C source ('' for a bare define, None if absent)."""
    m = re.search(r'^[ \t]*#define[ \t]+%s(?:[ \t]+(.*?))?[ \t]*(?://.*)?$' % name, text, re.M)
    return None if m is None else (m.group(1) or '')


def cli_set(cli, name):
    """The value of an uncommented 'set name = value' line in cli-setup.txt."""
    m = re.search(r'^set\s+%s\s*=\s*(.*?)\s*$' % name, cli, re.M)
    return m.group(1) if m else None


def c_block(text, ifdef):
    """'#ifdef NAME' up to its own '#endif' (nested #if blocks included)."""
    i = text.index('#ifdef %s\n' % ifdef)
    depth, out = 0, []
    for line in text[i:].split('\n'):
        s = line.strip()
        if s.startswith('#if'):
            depth += 1
        elif s.startswith('#endif'):
            depth -= 1
            if depth == 0:
                break
        out.append(line)
    return '\n'.join(out)


def read_ihex(path):
    """address -> byte, from an Intel hex file."""
    mem, base = {}, 0
    for line in open(path):
        line = line.strip()
        if not line.startswith(':'):
            continue
        n, addr, typ = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        data = bytes.fromhex(line[9:9 + 2 * n])
        if typ == 0:
            for i, byte in enumerate(data):
                mem[base + addr + i] = byte
        elif typ == 2:
            base = int.from_bytes(data, 'big') << 4
        elif typ == 4:
            base = int.from_bytes(data, 'big') << 16
    return mem


def symbol_alts(lib, name):
    """pin number -> (pin name, [alternate functions]), from a KiCad symbol."""
    text = open(os.path.join(SYMBOLS, lib + '.kicad_sym')).read()
    i = text.index('\t(symbol "%s"' % name)
    j = text.find('\n\t(symbol "', i + 5)
    block = text[i:j if j > 0 else len(text)]
    m = re.search(r'\(extends "([^"]+)"\)', block)
    if m:
        return symbol_alts(lib, m.group(1))
    pins = {}
    for chunk in block.split('(pin ')[1:]:
        nm = re.search(r'\(name "([^"]*)"', chunk)
        no = re.search(r'\(number "([^"]*)"', chunk)
        if nm and no:
            pins[no.group(1)] = (nm.group(1), re.findall(r'\(alternate "([^"]*)"', chunk))
    return pins


def alt_fns(pin, port):
    """The alternate functions of one port on a symbol pin ('TIM1_CH2 (PA9)' counts for PA9 only)."""
    out = set()
    for a in pin[1]:
        m = re.match(r'(\S+)(?: \((P[A-F]\d+)\))?$', a)
        if m and m.group(2) in (None, port):
            out.add(m.group(1))
    return out


def am32_source(rel):
    return open(os.path.join(AM32, rel)).read()


def am32_targets():
    """(Inc/targets.h of the AM32 checkout with firmware/am32's patch applied in memory, how)."""
    t = am32_source('Inc/targets.h')
    if '#ifdef %s\n' % AM32_TARGET in t:
        return t, 'the checkout already has %s' % AM32_TARGET
    patch = open(os.path.join(FW, AM32_PATCH)).read()
    for hunk in re.split(r'^@@[^\n]*\n', patch, flags=re.M)[1:]:
        old, new = [], []
        for line in hunk.rstrip('\n').split('\n'):
            if line.startswith('\\'):
                continue
            tag, body = (line[:1], line[1:]) if line else (' ', '')
            if tag in ' -':
                old.append(body)
            if tag in ' +':
                new.append(body)
        o, n = '\n'.join(old) + '\n', '\n'.join(new) + '\n'
        if t.count(o) != 1:
            return None, 'a hunk of %s does not apply' % os.path.basename(AM32_PATCH)
        t = t.replace(o, n)
    return t, '%s applied' % os.path.basename(AM32_PATCH)


# ------------------------------------------------------------------ pin maps
def check_fc_pins():
    S = 'FC pin map'
    ports, power, pins, c = port_nets('fc', 'U_FC', 'MCU_ST_STM32G4', 'STM32G473CEUx')
    check(S, 'KiCad symbol STM32G473CEUx has %d pins; footprint pins in circuit.py: %d' % (len(pins), len(c.pins)),
          set(pins) <= set(c.pins) | {'49'} and len(c.pins) >= len(pins))
    # power pins
    bad = []
    for name, nets in power.items():
        want = 'GND' if name.startswith('VSS') or name == 'EP' else ('NRST' if 'NRST' in name else '+3V3')
        if name.startswith(('VDD', 'VREF', 'VBAT')) or name.startswith('VSS'):
            if any(n != want for n in nets):
                bad.append('%s=%s' % (name, nets))
    check(S, 'every VDD/VDDA/VREF+/VBAT pin on +3V3, every VSS on GND', not bad, ', '.join(bad))
    # Betaflight config.h, one per gyro chip: the pin map must be the same
    cfgs = bf_configs()
    pinmap = {k: [(a, b.split('//')[0].strip()) for a, b in re.findall(
                  r'#define\s+(\w+_PIN|TIMER_PIN_MAPPING|\w+_INSTANCE|\w+_DMA_OPT|\w+_UART|PINIO\d_\w+)\s+(.*)', v)]
              for k, v in cfgs.items()}
    check(S, 'the BMI270 and ICM-42688-P configs have the same pin, timer, bus, UART and PINIO map',
          pinmap['RIDGE3'] == pinmap['RIDGE3_ICM'])
    cfg = cfgs['RIDGE3']
    d = lambda k: cdefine(cfg, k)
    fc = circuit.build('fc')
    VTX_SWITCH = ('VTX_EN_N', 'VTX_OFF')        # the net name circuit.py gives PB5's VTX switch line
    want = {'MOTOR1': 'M1_SIG', 'MOTOR2': 'M2_SIG', 'MOTOR3': 'M3_SIG', 'MOTOR4': 'M4_SIG',
            'BEEPER': 'BEEPER', 'LED0': 'LED0', 'LED_STRIP': 'LED_STRIP',
            'UART1_TX': 'UART1_TX', 'UART1_RX': 'UART1_RX', 'UART2_TX': 'UART2_TX', 'UART2_RX': 'UART2_RX',
            'UART4_TX': 'UART4_TX', 'UART4_RX': 'UART4_RX', 'LPUART1_TX': None, 'LPUART1_RX': 'TLM',
            'SPI1_SCK': 'SPI1_SCK', 'SPI1_SDI': 'SPI1_MISO', 'SPI1_SDO': 'SPI1_MOSI',
            'SPI2_SCK': 'SPI2_SCK', 'SPI2_SDI': 'SPI2_MISO', 'SPI2_SDO': 'SPI2_MOSI',
            'GYRO_1_CS': 'GYRO_CS', 'GYRO_1_EXTI': 'GYRO_INT', 'FLASH_CS': 'FLASH_CS',
            'MAX7456_SPI_CS': 'OSD_CS', 'PINIO1': VTX_SWITCH,
            'ADC_VBAT': 'ADC_VBAT', 'ADC_CURR': 'ADC_CURR'}
    seen = set()
    for fn, port in re.findall(r'#define\s+(\w+)_PIN\s+(P[A-G]\d+)', cfg):
        seen.add(fn)
        net = ports.get(port, 'no such port')
        exp = want.get(fn, '?')
        check(S, 'Betaflight %s_PIN %s' % (fn, port), net in exp if isinstance(exp, tuple) else net == exp,
              'carries %s' % net if net else 'not connected (unused on this board)')
    check(S, 'every function this board needs is defined in config.h (and nothing else, e.g. no camera control)',
          set(want) <= seen, ', '.join(sorted(set(want) - seen)))
    # the peripherals on the far end of those nets
    far = [('GYRO_CS', 'U_IMU', '12'), ('SPI1_SCK', 'U_IMU', '13'), ('SPI1_MOSI', 'U_IMU', '14'),
           ('SPI1_MISO', 'U_IMU', '1'), ('GYRO_INT', 'U_IMU', '4'),
           ('FLASH_CS', 'U_FLASH', '1'), ('SPI2_MISO', 'U_FLASH', '2'), ('SPI2_MOSI', 'U_FLASH', '5'),
           ('SPI2_SCK', 'U_FLASH', '6'),
           ('OSD_CS', 'U_OSD', '8'), ('SPI2_MOSI', 'U_OSD', '9'), ('SPI2_SCK', 'U_OSD', '10'),
           ('SPI2_MISO', 'U_OSD', '11')]
    names = {'U_IMU': 'BMI270 sec. 7.1 / ICM-42688-P table 9 (same pins)',
             'U_FLASH': 'W25Q128JV, WSON-8 (Winbond datasheet pinout)',
             'U_OSD': 'AT7456E, the MAX7456 pinout: 8 /CS, 9 SDIN, 10 SCLK, 11 SDOUT (MAX7456 pin description)'}
    for net, ref, pin in far:
        check(S, '%s reaches %s pin %s' % (net, ref, pin), comp('fc', ref).pins.get(pin) == net, names[ref])
    pullup = lambda n: any(re.match(r'R\d', x.ref) and set(x.pins.values()) == {'+3V3', n} for x in fc)
    check(S, 'OSD and flash share SPI2 (MAX7456_SPI_INSTANCE %s, FLASH_SPI_INSTANCE %s) on separate chip selects '
             '(%s, %s), each pulled up to 3.3 V so neither drives MISO while the MCU boots'
          % (d('MAX7456_SPI_INSTANCE'), d('FLASH_SPI_INSTANCE'), d('MAX7456_SPI_CS_PIN'), d('FLASH_CS_PIN')),
          d('MAX7456_SPI_INSTANCE') == 'SPI2' and d('FLASH_SPI_INSTANCE') == 'SPI2'
          and d('MAX7456_SPI_CS_PIN') != d('FLASH_CS_PIN') and pullup('OSD_CS') and pullup('FLASH_CS'))
    check(S, 'USE_MAX7456 in both builds (a CONFIG= build does not get it from common_pre.h)',
          all(cdefine(v, 'USE_MAX7456') is not None for v in cfgs.values()))
    # HD VTX: MSP DisplayPort on UART1, to the 6-pin connector
    hd = comp('fc', 'J_HD').pins
    tx, rx = ports.get(d('UART1_TX_PIN')), ports.get(d('UART1_RX_PIN'))
    check(S, 'HD VTX: MSP_DISPLAYPORT_UART %s; UART1 TX/RX (%s/%s) on HD connector pins 3/4 '
             '(Betaflight connector standard: 1 V+, 2 GND, 3 FC TX, 4 FC RX, 5 GND, 6 SBUS)'
          % (d('MSP_DISPLAYPORT_UART'), tx, rx),
          d('MSP_DISPLAYPORT_UART') == 'SERIAL_PORT_USART1' and hd.get('3') == tx and hd.get('4') == rx
          and hd.get('2') == 'GND' and hd.get('5') == 'GND')
    # VTX power switch: PINIO1 -> gate resistor -> N-FET on the 9 V regulator's EN
    sw = ports.get(d('PINIO1_PIN'))
    ser = [x for x in fc if re.match(r'R\d', x.ref) and sw in x.pins.values() and len(set(x.pins.values())) == 2]
    gate = [n for n in ser[0].pins.values() if n != sw][0] if len(ser) == 1 else None
    fet = [x for x in fc if x.part == 'AO3400A' and gate and x.pins.get('1') == gate]     # SOT-23: 1 G, 2 S, 3 D
    en = fet[0].pins.get('3') if fet else None
    reg = [x for x in fc if x.part == 'LM76003' and en and x.pins.get('18') == en]      # LM76003 pin 18 = EN
    pulldown = gate is not None and any(re.match(r'R\d', x.ref) and set(x.pins.values()) == {gate, 'GND'} for x in fc)
    rail = None
    if reg:
        lx = reg[0].pins.get('1')                                                        # pins 1-5 = SW
        ind = [x for x in fc if x.ref.startswith('L') and lx in x.pins.values()]
        rail = [n for n in ind[0].pins.values() if n != lx][0] if ind else None
    check(S, 'VTX switch: PINIO1_PIN %s (%s) -> %s -> %s gate, drain on %s pin 18 (LM76003 EN), gate pulled down: '
             'PB5 high = EN low = rail %s off; low, and floating through reset = on'
          % (d('PINIO1_PIN'), sw, ser[0].part if len(ser) == 1 else '?', fet[0].ref if fet else '?',
             reg[0].ref if reg else '?', rail),
          bool(fet) and fet[0].pins.get('2') == 'GND' and bool(reg) and pulldown and rail is not None)
    check(S, 'the switched rail %s feeds HD connector pin 1' % rail, rail is not None and hd.get('1') == rail)
    check(S, 'PINIO1_CONFIG %s (PINIO_CONFIG_MODE_OUT_PP, not inverted: low at boot and while its mode is off = '
             'VTX on), PINIO1_BOX %s (BOXUSER1: the USER1 switch turns the VTX off)'
          % (d('PINIO1_CONFIG'), d('PINIO1_BOX')), d('PINIO1_CONFIG') == '1' and d('PINIO1_BOX') == '40')
    imu = comp('fc', 'U_IMU')
    check(S, 'IMU pads take a BMI270 or an ICM-42688-P: pins 2/3 open (BMI270 aux I2C must not be grounded), '
             'SPI and supply pins shared', imu.pins.get('2') is None and imu.pins.get('3') is None
          and imu.pins['12'] == 'GYRO_CS' and imu.pins['5'] == '+3V3_GYRO' and imu.pins['8'] == '+3V3_GYRO',
          'BOM part: %s' % parts.PARTS[imu.part]['mpn'])
    # Gyro alignment against the placed footprint.  Pad 1 is the chip's
    # pin-1 corner.  TDK DS-000347 fig. 15: pin 1 is at the ICM's (-X, +Y)
    # corner.  Bosch BST-BMI270-DS000-08 sec. 8.2: pin 1 is at the BMI270's
    # (+x, +y) corner.  Betaflight body frame: +X forward, +Y left; the
    # board's front is -y in KiCad.  So with pin 1 rear-left and the pad
    # 12-14 edge on the left, the ICM is CW0 and the BMI270 CW270.
    b = pcbnew.LoadBoard(os.path.join(V1, 'fc', 'ridge3-fc.kicad_pcb'))
    fp = b.FindFootprintByReference('U_IMU')
    ctr = fp.GetPosition()
    pad = {p.GetNumber(): p.GetPosition() for p in fp.Pads()}
    rel = lambda n: (pcbnew.ToMM(pad[n].x - ctr.x), pcbnew.ToMM(pad[n].y - ctr.y))
    p1, p13 = rel('1'), rel('13')
    rear_left = p1[0] < 0 and p1[1] > 0
    left_edge = p13[0] < 0 and abs(p13[0]) > abs(p13[1])
    check(S, 'IMU footprint on top, pin 1 rear-left, pads 12-14 along the left edge',
          not fp.IsFlipped() and rear_left and left_edge,
          'pad 1 at (%.2f, %.2f), pad 13 at (%.2f, %.2f) mm from centre' % (p1 + p13))
    align = {k: re.search(r'#define\s+GYRO_1_ALIGN\s+(\w+)', v).group(1) for k, v in cfgs.items()}
    drivers = {k: sorted(set(re.findall(r'#define\s+USE_(?:ACC|GYRO|ACCGYRO)_(?:SPI_)?(\w+)', v)))
               for k, v in cfgs.items()}
    check(S, 'RIDGE3 (BMI270 build): GYRO_1_ALIGN CW270_DEG, BMI270 driver only',
          align['RIDGE3'] == 'CW270_DEG' and drivers['RIDGE3'] == ['BMI270'],
          '%s, drivers %s' % (align['RIDGE3'], drivers['RIDGE3']))
    check(S, 'RIDGE3_ICM (ICM-42688-P build): GYRO_1_ALIGN CW0_DEG, ICM-42688-P driver only',
          align['RIDGE3_ICM'] == 'CW0_DEG' and drivers['RIDGE3_ICM'] == ['ICM42688P'],
          '%s, drivers %s' % (align['RIDGE3_ICM'], drivers['RIDGE3_ICM']))
    check(S, 'BOARD_NAME RIDGE3 / RIDGE3_ICM, MANUFACTURER_ID OFFG',
          [cdefine(cfgs[k], 'BOARD_NAME') for k in BF_CONFIGS] == list(BF_CONFIGS)
          and all(cdefine(v, 'MANUFACTURER_ID') == 'OFFG' for v in cfgs.values()))
    check(S, 'no board rotation in either build (DEFAULT_ALIGN_BOARD_* unset)',
          not any(re.search(r'#define\s+DEFAULT_ALIGN_BOARD', v) for v in cfgs.values()))
    check(S, 'PID loop: BMI270 3.2 kHz (denom 1), ICM 8 kHz / 2 = 4 kHz',
          re.search(r'DEFAULT_PID_PROCESS_DENOM\s+1\b', cfgs['RIDGE3']) is not None
          and re.search(r'DEFAULT_PID_PROCESS_DENOM\s+2\b', cfgs['RIDGE3_ICM']) is not None)
    check(S, 'HSE crystal on PF0/PF1 with SYSTEM_HSE_MHZ 8',
          c.pins['5'] == 'HSE_IN' and c.pins['6'] == 'HSE_OUT' and d('SYSTEM_HSE_MHZ') == '8'
          and comp('fc', 'Y1').part == 'XTAL8M')
    check(S, 'USB D+/D- on PA12/PA11', ports['PA12'] == 'USB_DP' and ports['PA11'] == 'USB_DM')
    check(S, 'SWD on PA13/PA14 to test pads', ports['PA13'] == 'SWDIO' and ports['PA14'] == 'SWCLK'
          and comp('fc', 'TP_SWDIO').pins['1'] == 'SWDIO')
    check(S, 'BOOT0 (pin 46, PB8-BOOT0) pulled down 10k, DFU button to 3.3 V',
          pins['46'] == 'PB8' and ports['PB8'] == 'BOOT0'
          and any(x.part == 'R10K' and set(x.pins.values()) == {'BOOT0', 'GND'} for x in fc)
          and comp('fc', 'SW_BOOT').pins == {'1': '+3V3', '2': 'BOOT0'})
    check(S, 'NRST (pin 7, PG10-NRST) to the RST test pad, 100 nF to ground',
          pins['7'] == 'PG10' and ports['PG10'] == 'NRST' and comp('fc', 'TP_NRST').pins['1'] == 'NRST'
          and any(x.part == 'C100N' and set(x.pins.values()) == {'NRST', 'GND'} for x in fc))


# The ESC MCU is an STM32G071GBU6 or G071G8U6 (UFQFPN28, "GP" pinout).  KiCad
# 10 has no symbol for that package's GP variant (only the G071GxUxN "PD"
# variant, whose pins 15 and 22-25 differ); the STM32G081GBUx is the same
# die plus AES in the same GP pinout, so the pin numbers are read from it,
# and cross-checked here against DS12232 (STM32G071x8/xB) table 12 / fig. 9.
G071_SYMBOL = ('MCU_ST_STM32G0', 'STM32G081GBUx')
DS12232_QFN28_GP = {'3': 'VDD', '4': 'VSS', '5': 'PF2', '8': 'PA2', '9': 'PA3', '11': 'PA5', '12': 'PA6',
                    '13': 'PA7', '14': 'PB0', '15': 'PB1', '16': 'PA8', '18': 'PA9/PA11', '19': 'PA10/PA12',
                    '20': 'PA13', '21': 'PA14', '23': 'PB3', '24': 'PB4', '27': 'PB7'}


def check_esc_pins():
    S = 'ESC pin map'
    sym = symbol_alts(*G071_SYMBOL)
    bad = ['pin %s is %s, not %s' % (k, sym.get(k, ('none',))[0], v) for k, v in DS12232_QFN28_GP.items()
           if sym.get(k, ('',))[0] != v]
    check(S, 'KiCad %s pin numbers = STM32G071 UFQFPN28 GP pinout (DS12232) for every pin the ESC uses'
          % G071_SYMBOL[1], not bad, '; '.join(bad))
    esc = circuit.build('esc')
    for n in (1, 2, 3, 4):
        ports, power, _, c = port_nets('esc', 'U_ESC%d' % n, *G071_SYMBOL)
        bad = ['%s=%s' % (k, v) for k, v in power.items()
               if (k.startswith('VDD') and set(v) != {'+3V3'}) or (k.startswith('VSS') and set(v) != {'GND'})]
        check(S, 'ESC %d: VDD/VDDA (pin 3) on +3V3, VSS/VSSA (pin 4) on GND' % n,
              not bad and 'VDD' in power and 'VSS' in power, ', '.join(bad))
        check(S, 'ESC %d: NRST (pin 5, PF2-NRST) filtered 100 nF to ground; SWDIO (PA13) to its own test pad '
                 'TP_E%d_DIO, SWCLK (PA14) to its own test pad TP_E%d_CLK' % (n, n, n),
              ports.get('PF2') == 'M%d_NRST' % n
              and any(x.part == 'C100N' and set(x.pins.values()) == {'M%d_NRST' % n, 'GND'} for x in esc)
              and ports.get('PA13') == 'M%d_SWDIO' % n and ports.get('PA14') == 'M%d_SWCLK' % n
              and comp('esc', 'TP_E%d_DIO' % n).pins.get('1') == 'M%d_SWDIO' % n
              and comp('esc', 'TP_E%d_CLK' % n).pins.get('1') == 'M%d_SWCLK' % n)
    if not AM32:
        check(S, 'AM32 targets.h', 'SKIP', 'set AM32_SRC to an AM32 checkout (commit %s) to check against the firmware'
              % AM32_COMMIT)
        return
    try:
        import subprocess
        head = subprocess.run(['git', '-C', AM32, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        head = ''
    check(S, 'AM32 checkout %s at commit %s (the patch and the images are for %s)' % (AM32, head[:7] or '?', AM32_COMMIT),
          head.startswith(AM32_COMMIT) if head else 'INFO', '' if head else 'not a git checkout')
    tgt, how = am32_targets()
    check(S, 'firmware/%s applies to Inc/targets.h' % AM32_PATCH, tgt is not None, how)
    if tgt is None:
        return
    tb = c_block(tgt, AM32_TARGET)
    g = c_block(tgt, 'HARDWARE_GROUP_G0_A')
    mcu = c_block(tgt, 'MCU_G071')
    td = lambda k: cdefine(tb, k)
    gd = dict(re.findall(r'#define\s+(\w+)\s+(\S+)', g))
    main_c = am32_source('Src/main.c')
    m = re.search(r'_Static_assert\(sizeof\(FIRMWARE_NAME\)\s*<=\s*(\d+)', main_c)
    name_max = int(m.group(1)) - 1 if m else 12
    fname = (td('FIRMWARE_NAME') or '').strip('"')
    check(S, '%s: HARDWARE_GROUP_G0_A, SIXTY_FOUR_KB_MEMORY, FILE_NAME "%s", FIRMWARE_NAME "%s" (%d of %d characters, '
             'main.c static assert)' % (AM32_TARGET, (td('FILE_NAME') or '').strip('"'), fname, len(fname), name_max),
          td('HARDWARE_GROUP_G0_A') == '' and td('SIXTY_FOUR_KB_MEMORY') == ''
          and td('FILE_NAME') == '"%s"' % AM32_TARGET and 0 < len(fname) <= name_max
          and cdefine(g, 'MCU_G071') == '')
    over = [k for k in ('CURRENT_ADC_PIN', 'VOLTAGE_ADC_PIN', 'CURRENT_ADC_CHANNEL', 'VOLTAGE_ADC_CHANNEL',
                        'NO_PA11_PA12_REMAP', 'USE_SERIAL_TELEMETRY', 'NO_CURRENT_SENSE', 'N_VARIANT')
            if cdefine(tb, k) is not None or cdefine(g, k) is not None]
    check(S, '%s and G0_A leave the MCU_G071 defaults alone: no ADC pin overrides, no NO_PA11_PA12_REMAP, '
             'no USE_SERIAL_TELEMETRY, current sense on' % AM32_TARGET, not over, ', '.join(over))
    check(S, 'no serial telemetry: the ESC\'s stack connector pin 4 (TLM) is not connected',
          comp('esc', 'J_FC').pins.get('4') is None and cdefine(tb, 'USE_SERIAL_TELEMETRY') is None)
    # which port each function uses: G0_A group, MCU_G071 defaults, g071 drivers, ST's LL headers
    port = lambda pin_key, port_key: 'P%s%s' % (gd[port_key][-1], gd[pin_key].split('_')[-1])
    ll = am32_source('Mcu/g071/Drivers/STM32G0xx_HAL_Driver/Inc/stm32g0xx_ll_comp.h')
    comp_io = {k: (a, b) for k, a, b in re.findall(
        r'#define\s+(LL_COMP_INPUT_(?:MINUS|PLUS)_IO\d)\s.*?pin (P[A-F]\d+) for COMP1, pin (P[A-F]\d+) for COMP2', ll)}
    main_comp = cdefine(mcu, 'MAIN_COMP')
    ci = 1 if main_comp == 'COMP2' else 0
    comparator_c = am32_source('Mcu/g071/Src/comparator.c')
    plus = set(re.findall(r'LL_COMP_ConfigInputs\(active_COMP,\s*PHASE_\w_COMP,\s*(LL_COMP_INPUT_PLUS_IO\d)\)',
                          comparator_c))
    adc_c = am32_source('Mcu/g071/Src/ADC.c')
    adc_port = dict(re.findall(r'Pin = (VOLTAGE|CURRENT)_ADC_PIN;[^}]*?LL_GPIO_Init\(GPIO([A-F])', adc_c))
    cur_pin = 'P%s%s' % (adc_port.get('CURRENT', '?'), cdefine(mcu, 'CURRENT_ADC_PIN').split('_')[-1])
    volt_pin = 'P%s%s' % (adc_port.get('VOLTAGE', '?'), cdefine(mcu, 'VOLTAGE_ADC_PIN').split('_')[-1])
    tim = '%s_CH%s' % (gd['IC_TIMER_REGISTER'], gd['IC_TIMER_CHANNEL'][-1])
    bysym = {nm: k for k, (nm0, _) in sym.items() for nm in nm0.split('/')}
    want = {port('INPUT_PIN', 'INPUT_PIN_PORT'): ('SIG', {tim})}
    for ph in 'ABC':
        hi = port('PHASE_%s_GPIO_HIGH' % ph, 'PHASE_%s_GPIO_PORT_HIGH' % ph)
        lo = port('PHASE_%s_GPIO_LOW' % ph, 'PHASE_%s_GPIO_PORT_LOW' % ph)
        # a phase's high and low side must be one TIM1 channel and its complement
        chans = [f for f in alt_fns(sym[bysym[hi]], hi) if re.match(r'TIM1_CH\d$', f)] if hi in bysym else []
        ch = chans[0] if chans else 'TIM1_CH?'
        want[hi] = ('H' + ph, {ch})
        want[lo] = ('L' + ph, {ch + 'N'})
        want[comp_io.get(gd['PHASE_%s_COMP' % ph], ('?', '?'))[ci]] = ('CMP_' + ph, {'%s_INM' % main_comp})
    want[comp_io.get(plus.pop() if len(plus) == 1 else '?', ('?', '?'))[ci]] = ('NEUTRAL', {'%s_INP' % main_comp})
    want[cur_pin] = ('ISENSE', {'ADC1_IN%s' % cdefine(mcu, 'CURRENT_ADC_CHANNEL').split('_')[-1]})
    want[volt_pin] = ('ESC_VSENSE', {'ADC1_IN%s' % cdefine(mcu, 'VOLTAGE_ADC_CHANNEL').split('_')[-1]})
    cant = ['%s (pin %s) cannot be %s' % (p, bysym.get(p), '/'.join(sorted(f)))
            for p, (_, f) in want.items() if p not in bysym or not f <= alt_fns(sym[bysym[p]], p)]
    check(S, 'every G0_A pin can do what AM32 uses it for (KiCad alternate functions): input %s; TIM1 CHx/CHxN '
             'pairs per phase; %s inputs; ADC channels' % (tim, main_comp), not cant, '; '.join(cant))
    for n in (1, 2, 3, 4):
        ports = port_nets('esc', 'U_ESC%d' % n, *G071_SYMBOL)[0]
        exp = lambda f: f if f == 'ESC_VSENSE' else 'M%d_%s' % (n, f)
        bad = ['%s wants %s, has %s' % (p, exp(f), ports.get(p)) for p, (f, _) in want.items() if ports.get(p) != exp(f)]
        check(S, 'ESC %d: input, six gate outputs, three comparator inputs, neutral, current and voltage match '
                 'group G0_A and the MCU_G071 defaults' % n, not bad,
              '; '.join(bad) or ', '.join('%s %s (pin %s)' % (p, f, bysym.get(p)) for p, (f, _) in sorted(want.items())))
    per = am32_source('Mcu/g071/Src/peripherals.c')
    remap = re.search(r'#ifndef NO_PA11_PA12_REMAP\s+LL_SYSCFG_EnablePinRemap\(LL_SYSCFG_PIN_RMP_PA11\);\s+'
                      r'LL_SYSCFG_EnablePinRemap\(LL_SYSCFG_PIN_RMP_PA12\);', per)
    check(S, 'pins 18/19 are PA11/PA12 until remapped to PA9/PA10 (KiCad names %s, %s); AM32\'s g071 '
             'peripherals.c remaps them at start-up unless NO_PA11_PA12_REMAP is defined' % (sym['18'][0], sym['19'][0]),
          remap is not None and sym['18'][0] == 'PA9/PA11' and sym['19'][0] == 'PA10/PA12'
          and cdefine(tb, 'NO_PA11_PA12_REMAP') is None and cdefine(g, 'NO_PA11_PA12_REMAP') is None)
    # dead time: TIM1 on PCLK (64 MHz), clock division 1
    mhz = int(cdefine(mcu, 'CPU_FREQUENCY_MHZ'))
    dt = int(td('DEAD_TIME'))
    tim1 = 'LL_RCC_TIM1_CLKSOURCE_PCLK1' in per and 'LL_TIM_CLOCKDIVISION_DIV1' in per
    check(S, 'DEAD_TIME %d = %.0f ns at %d MHz (TIM1 on PCLK, clock division 1; DTG linear below 128), plus the '
             'DRV8300\'s own 150-280 ns (DT pin open): not checked on a scope' % (dt, dt * 1e3 / mhz, mhz),
          'INFO' if tim1 and dt < 128 else False)


# ------------------------------------------------------------------ firmware scales
INA_GAIN = {'A1': 20, 'A2': 50, 'A3': 100, 'A4': 200}      # TI INA180 / INA186 datasheets, device comparison tables


def shunt_mohm(part):
    """SHUNT_0M5 -> 0.5 (milliohm)."""
    m = re.match(r'SHUNT_(\d+)M(\d*)$', part)
    return float(m.group(1) + ('.' + m.group(2) if m.group(2) else '')) if m else None


def check_fw_scales():
    """The firmware's voltage and current scale factors against the circuit's resistors and amplifiers."""
    S = 'Firmware scales'
    cfg = bf_configs()['RIDGE3']
    cli = open(os.path.join(FW, 'betaflight/cli-setup.txt')).read()
    esc, fc = circuit.build('esc'), circuit.build('fc')
    # ESC: one shunt and one INA186 per channel -> MILLIVOLT_PER_AMP at PA5
    sens, bad = set(), []
    for n in (1, 2, 3, 4):
        sh, amp = comp('esc', 'R_SH%d' % n), comp('esc', 'U_CS%d' % n)
        g = re.match(r'INA186(A\d)$', amp.part)
        src, m = 'M%d_SRC' % n, 'M%d_' % n
        # INA186 DCK: 1 REF, 2 GND, 3 VS, 4 IN+, 5 IN-, 6 OUT; low side, Kelvin:
        # IN+ on the shunt's sense-node sense pad, IN- on its ground sense pad
        if not (g and shunt_mohm(sh.part)
                and sh.pins == {'1': src, '2': 'GND', '3': m + 'SNSP', '4': m + 'SNSN'}
                and amp.pins == {'1': 'GND', '2': 'GND', '3': '+3V3', '4': m + 'SNSP', '5': m + 'SNSN',
                                 '6': m + 'IOUT'}):
            bad.append('ESC %d: %s %s %s' % (n, sh.part, amp.part, amp.pins))
            continue
        sens.add(shunt_mohm(sh.part) * INA_GAIN[g.group(1)])
        filt = [x for x in esc if re.match(r'R\d', x.ref) and set(x.pins.values()) == {'M%d_IOUT' % n, 'M%d_ISENSE' % n}]
        if not filt:
            bad.append('ESC %d: no series resistor from IOUT to ISENSE' % n)
    mv_a = sens.pop() if len(sens) == 1 and not bad else None
    tgt = am32_targets()[0] if AM32 else None
    mpa = cdefine(c_block(tgt, AM32_TARGET), 'MILLIVOLT_PER_AMP') if tgt else None
    check(S, 'ESC current: %s mOhm shunt x INA186 gain = %s mV/A at PA5 (low-side, Kelvin) = '
             'AM32 MILLIVOLT_PER_AMP %s' % (shunt_mohm(comp('esc', 'R_SH1').part), mv_a, mpa),
          (mv_a is not None and mpa is not None and abs(mv_a - float(mpa)) < 1e-9) if tgt else 'SKIP',
          '; '.join(bad) or ('66 A full scale at 3.3 V' if mv_a else ''))
    if tgt:
        tdv = cdefine(c_block(tgt, AM32_TARGET), 'TARGET_VOLTAGE_DIVIDER')
        r = esc_vsense_ratio()
        check(S, 'ESC battery divider ratio %.2f = AM32 TARGET_VOLTAGE_DIVIDER %s / 10; 6S full 25.2 V -> %.2f V at PA6'
              % (r, tdv, 25.2 / r), tdv is not None and round(r * 10) == int(tdv) and 25.2 / r < 3.3)
    # FC: CUR = the four channel outputs averaged through equal resistors, loaded by the FC's input
    avg = [x for x in esc if re.match(r'R\d', x.ref) and 'CUR' in x.pins.values()
           and any(re.match(r'M\d_IOUT$', v or '') for v in x.pins.values())]
    ravg = {value(x.part) for x in avg}
    load = [value(x.part) for b in (esc, fc) for x in b
            if re.match(r'R\d', x.ref) and set(x.pins.values()) == {'CUR', 'GND'}]
    if len(avg) == 4 and len(ravg) == 1 and mv_a is not None:
        rs = ravg.pop() / 4                                     # Thevenin: four equal resistors in parallel
        rl = 1 / sum(1 / r for r in load) if load else float('inf')
        k = rl / (rl + rs)
        per_a = mv_a / 4 * k                                    # mV per amp of total battery current
        scale = cdefine(cfg, 'DEFAULT_CURRENT_METER_SCALE')
        err = int(scale) / (per_a * 10) - 1 if scale else None
        check(S, 'FC current: CUR = average of 4 x %g mV/A through %d x %gk, loaded by %s: %.2f mV/A = ibata_scale '
                 '%.1f (mV per 10 A); config.h DEFAULT_CURRENT_METER_SCALE %s (%+.1f %%)'
              % (mv_a, len(avg), rs * 4 / 1e3, ' || '.join('%gk' % (r / 1e3) for r in load) or 'nothing',
                 per_a, per_a * 10, scale, 100 * err if err is not None else 0),
              err is not None and abs(err) < 0.03,
              'the ESC\'s %.1fk source into the FC\'s %gk makes CUR read %.1f %% low; %d would be exact'
              % (rs / 1e3, rl / 1e3, 100 * (1 - k), round(per_a * 10)) if k < 1 else '')
    else:
        check(S, 'FC current: four equal averaging resistors from the channels to CUR', False,
              '%d found, values %s' % (len(avg), sorted(ravg)))
    check(S, 'config.h: current meter ADC, offset 0 (0 A = 0 V: INA186 output from ground, REF grounded), '
             'voltage meter ADC',
          cdefine(cfg, 'DEFAULT_CURRENT_METER_SOURCE') == 'CURRENT_METER_ADC'
          and cdefine(cfg, 'DEFAULT_CURRENT_METER_OFFSET') == '0'
          and cdefine(cfg, 'DEFAULT_VOLTAGE_METER_SOURCE') == 'VOLTAGE_METER_ADC')
    t, b = value(find('fc', 'VBAT divider top')[0].part), value(find('fc', 'VBAT divider bottom')[0].part)
    k = (t + b) / b
    vs = cdefine(cfg, 'DEFAULT_VOLTAGE_METER_SCALE')
    check(S, 'FC battery divider %gk/%gk: ratio %.1f -> vbat_scale %d = config.h DEFAULT_VOLTAGE_METER_SCALE %s '
             '(uint8, max 255); 6S full 25.2 V -> %.2f V at PB2' % (t / 1e3, b / 1e3, k, round(k * 10), vs, 25.2 / k),
          vs is not None and round(k * 10) == int(vs) <= 255 and 25.2 / k < 3.3)
    same = {'vbat_scale': cdefine(cfg, 'DEFAULT_VOLTAGE_METER_SCALE'),
            'ibata_scale': cdefine(cfg, 'DEFAULT_CURRENT_METER_SCALE'),
            'ibata_offset': cdefine(cfg, 'DEFAULT_CURRENT_METER_OFFSET'),
            'current_meter': 'ADC', 'battery_meter': 'ADC',
            'pinio_config': cdefine(cfg, 'PINIO1_CONFIG') + ',1,1,1',
            'pinio_box': cdefine(cfg, 'PINIO1_BOX') + ',255,255,255',
            'vcd_video_system': 'HD', 'osd_displayport_device': 'MSP',
            'dshot_bidir': 'ON', 'serialrx_provider': 'CRSF'}
    bad = ['%s = %s, want %s' % (k_, cli_set(cli, k_), v) for k_, v in same.items() if cli_set(cli, k_) != v]
    hd_uart = re.search(r'^serial\s+UART1\s+131073\b', cli, re.M) is not None
    check(S, 'cli-setup.txt agrees with config.h (scales, PINIO) and sets up an HD system: UART1 131073 '
             '(MSP + VTX_MSP), vcd_video_system HD, displayport MSP', not bad and hd_uart,
          '; '.join(bad) + ('' if hd_uart else '; no "serial UART1 131073"'))


# ------------------------------------------------------------------ circuit arithmetic
def esc_vsense_ratio():
    top = value(find('esc', 'ESC vsense top')[0].part)
    bot = value(find('esc', 'ESC vsense bottom')[0].part)
    return (top + bot) / bot


def check_power():
    S = 'Power and analog'
    VMAX = 25.2          # a full 6S pack
    # --- FC supplies (reference voltages: datasheet electrical tables)
    t, b = value(find('fc', '5V BEC feedback top')[0].part), value(find('fc', '5V BEC feedback bottom')[0].part)
    v = 1.0 * (1 + t / b)
    check(S, 'FC 5 V BEC (LMR38020F, VREF 1.00 V): 1.0 x (1 + %gk/%gk) = %.2f V (USB-safe 5 V rail)'
          % (t / 1e3, b / 1e3, v), 4.9 <= v <= 5.25)
    t, b = value(find('fc', '9V BEC feedback top')[0].part), value(find('fc', '9V BEC feedback bottom')[0].part)
    v = 1.006 * (1 + t / b)
    check(S, 'FC 9 V VTX BEC (LM76003, VFB 1.006 V typ): %.2f V (DJI O3/O4, Walksnail, HDZero, analog VTX: 7-26 V '
             'inputs, HDZero 7-13 V)' % v, 8.6 <= v <= 9.5)
    t, b = value(find('fc', '9V BEC UVLO top')[0].part), value(find('fc', '9V BEC UVLO bottom')[0].part)
    v = 1.204 * (1 + t / b)
    check(S, '9 V BEC turns on above %.2f V (EN 1.204 V typ x (1 + %gk/%gk)): a 2S pack (6.0 V empty) still '
             'runs it; below that the rail stays off instead of browning out' % (v, t / 1e3, b / 1e3), 5.5 <= v <= 6.5)
    # --- ESC supplies
    t, b = value(find('esc', 'gate-drive LDO feedback top')[0].part), value(find('esc', 'gate-drive LDO feedback bottom')[0].part)
    v = 1.169 * (1 + t / b)
    check(S, 'ESC gate drive (TPS7A1601, VFB 1.169 V): %.2f V: %.0f %% of the FETs\' +/-20 V gate rating and of '
             'the DRV8300\'s 20 V GVDD maximum' % (v, 100 * v / 20), 10.0 <= v <= 12.0 and v / 20 <= 0.6)
    i_gvdd = 4 * (1.5e-3 + 2 * 41e-9 * 48e3)      # 4 drivers: IQ + 2 gates switching at 48 kHz, 41 nC each
    p = (VMAX - v) * i_gvdd
    check(S, 'gate-drive LDO at 6S: %.0f mA (of 100 mA) x %.1f V = %.2f W; +%.0f C through the VSON-8\'s 44.5 C/W '
             '(TI SBVS171F)' % (i_gvdd * 1e3, VMAX - v, p, p * 44.5), p < 0.5 and i_gvdd < 0.06)
    check(S, 'ESC 3.3 V: MAX15062A fixed 3.3 V (no divider), 60 V input', find('esc', 'ESC 3.3V buck')[0].part == 'MAX15062A')
    # battery dividers
    r = esc_vsense_ratio()
    check(S, 'ESC battery sense: %.1f V / %.1f = %.2f V at PA6 (< 3.3 V)' % (VMAX, r, VMAX / r), VMAX / r < 3.0)
    t, b = value(find('fc', 'VBAT divider top')[0].part), value(find('fc', 'VBAT divider bottom')[0].part)
    k = (t + b) / b
    check(S, 'FC battery sense: %.1f V / %.0f = %.2f V at PB2 (< 3.3 V; vbat_scale 160)' % (VMAX, k, VMAX / k), VMAX / k < 3.0)
    # back-EMF and virtual neutral
    ph = find('esc', 'BEMF A')
    bt = value([c for c in ph if c.part == 'R20K'][0].part); bb = value([c for c in ph if c.part != 'R20K'][0].part)
    kr = bb / (bt + bb)
    check(S, 'BEMF divider %gk/%gk: %.1f V phase -> %.2f V at the comparator; a 35 V spike -> %.2f V (< VDDA 3.3 V)'
          % (bt / 1e3, bb / 1e3, VMAX, VMAX * kr, 35 * kr), 35 * kr < 3.3)
    # virtual neutral: equal legs from the three divided phases to a star
    # that only the MCU's comparator input loads; the star is then the mean
    # of the three CMP nodes, and CMP - NEUTRAL crosses zero where the
    # phase crosses the mean of the phases
    comps_ = circuit.build('esc')
    bad, rleg = [], set()
    for n in (1, 2, 3, 4):
        m = lambda s: 'M%d_%s' % (n, s)
        on = [(c, k) for c in comps_ for k, v in c.pins.items() if v == m('NEUTRAL')]
        legs = [c for c, k in on if c.note.startswith('neutral ')]
        others = [c.ref for c, k in on if not c.note.startswith('neutral ') and c.ref != 'U_ESC%d' % n]
        if others or sorted(set(c.pins.values()) - {m('NEUTRAL')} for c in legs) != \
                sorted({m('CMP_' + ph)} for ph in 'ABC'):
            bad.append(n)
        rleg |= set(value(c.part) for c in legs)
    rl = min(rleg)
    rth = bt * bb / (bt + bb)
    check(S, 'virtual neutral: %gk from each of CMP_A/B/C to a star only the comparator loads, in all four ESCs: '
             'the star is their mean; the comparator sees %.2f of CMP minus that mean'
          % (rl / 1e3, rl / (rl + rth)), not bad and len(rleg) == 1, str(bad))
    # current sense
    sh = find('esc', 'ESC 1 shunt')[0]; amp = find('esc', 'ESC 1 current amplifier')[0]
    gain = {'INA180A1': 20, 'INA180A2': 50, 'INA180A3': 100, 'INA180A4': 200, 'INA186A3': 100}[amp.part]
    mv_a = shunt_mohm(sh.part) * gain
    check(S, 'current sense: %.1f mOhm x %d V/V = %.0f mV/A; the 3.3 V ADC range is %.0f A per motor' %
          (shunt_mohm(sh.part), gain, mv_a, 3300 / mv_a), 3300 / mv_a >= 40)
    check(S, 'shunt dissipation at 20 A per motor: %.2f W in a 2 W 1206 (%.0f %%)' % (20 ** 2 * shunt_mohm(sh.part) * 1e-3,
          100 * 20 ** 2 * shunt_mohm(sh.part) * 1e-3 / 2), 20 ** 2 * shunt_mohm(sh.part) * 1e-3 <= 0.6 * 2)
    check(S, 'current sense is Kelvin: the amplifier inputs (IN+ pin 4, IN- pin 5) are nets of their own, tied to '
             'the shunt only by its footprint\'s net-tie pads', sh.pins.get('3', '').endswith('SNSP')
          and amp.pins['4'] == sh.pins['3'] and sh.pins.get('4', '').endswith('SNSN') and amp.pins['5'] == sh.pins['4']
          and amp.pins['1'] == 'GND')
    # --- voltage derating: every part that sees the pack, against 25.2 V
    RATED = {   # absolute maximum or rated voltage, datasheet
        'TPN2R304PL': 40, 'DRV8300D': 100, 'MAX15062A': 60, 'TPS7A1601': 60, 'C_BRIDGE': 50, 'C1U_100': 100,
        'C10U50_1210': 50, 'C100N_100': 100, 'LMR38020F': 80, 'LM76003': 60, 'SMF26A': 26, 'SMF33A': 33,
    }
    seen = set()
    for bd in ('esc', 'fc'):
        for c in circuit.build(bd):
            if c.part in seen or c.part not in RATED:
                continue
            if not any(n == 'VBAT' or n.endswith(('_A', '_B', '_C')) for n in c.pins.values() if n):
                continue
            seen.add(c.part)
            rv = RATED[c.part]
            if c.part.startswith('SMF'):
                check(S, '%s TVS: stand-off %d V >= %.1f V (conducts only above a full pack)' % (c.part, rv, VMAX),
                      rv >= VMAX)
                continue
            ratio = VMAX / rv
            if c.part == 'TPN2R304PL':
                check(S, '40 V FETs at 6S: %.0f %% of their rating (the chosen "Balanced: 40 V parts, 2-6S"; the 60 %% '
                         'rule holds to 5S, 21 V = 53 %%)' % (100 * ratio), 'INFO',
                      'switching spikes are held down by the bridge capacitors under every half-bridge and the '
                      'low-ESR capacitor on the battery leads')
                continue
            check(S, '%s: %.0f %% of its %d V rating at 6S (60 %% rule)' % (c.part, 100 * ratio, rv), ratio <= 0.6)
    # --- inductors against their regulators' current limits (datasheets)
    for bd, note, reg, limit in (('fc', '5V BEC inductor', 'LMR38020F high-side limit', 3.8),
                                 ('fc', '9V BEC inductor', 'LM76003 high-side limit', 6.8),
                                 ('esc', 'buck inductor', 'MAX15062A peak limit', 0.62)):
        ind = find(bd, note)[0]
        isat = parts.PARTS[ind.part].get('isat')
        check(S, '%s %s: Isat %s A vs the %s %.2f A max' % (bd.upper(), parts.PARTS[ind.part]['mpn'], isat, reg, limit),
              isat is not None and isat >= limit if isat is not None else 'INFO', '' if isat else 'isat not in parts.py')
    # --- gate drive
    bs = find('esc', 'bootstrap A')[0].part
    cb = value(bs)
    QG = 41e-9      # TPN2R304PL Qg at 10 V (datasheet)
    KEEP = 0.2      # a 1 uF 16 V X5R 0201 at ~10.5 V of bias: taken as 20 % left (an estimate; X5R MLCCs of
                    # this size keep 20-30 % there -- check Samsung's DC-bias curve for CL03A105MO3NRNC)
    dv = QG / (cb * KEEP)
    check(S, 'bootstrap %s 1 uF (taken as %.1f uF at 11 V) vs 41 nC gate charge: %.2f V droop per turn-on'
          % (parts.PARTS[bs]['mpn'], cb * KEEP * 1e6, dv), dv < 0.5)
    for i in (5, 10, 15, 20):
        p = i * i * 2 * 2.3e-3
        check(S, 'conduction loss per motor at %d A: %.2f W (two FETs at 2.3 mOhm max, 25 C)' % (i, p), 'INFO',
              'hot (about 1.5 x at 125 C): %.2f W' % (1.5 * p))
    # --- FC details
    cl = value(find('fc', 'crystal load')[0].part)
    check(S, 'HSE load caps %d pF each: CL = %.1f pF with 3 pF stray (crystal CL 10 pF)' % (cl * 1e12, cl * 1e12 / 2 + 3),
          abs(cl * 1e12 / 2 + 3 - 10) <= 1.5)
    cc = [x for x in circuit.build('fc') if x.note.startswith('CC') and x.note.endswith('Rd')]
    check(S, 'USB-C: 5.1k Rd on CC1 and CC2 (C-to-C cables supply 5 V)', len(cc) == 2 and all(x.part == 'R5K1' for x in cc))
    fc_caps = [x for x in circuit.build('fc') if x.note.startswith('U_FC pin')]
    check(S, 'FC MCU: one 100 nF per VDD/VBAT/VDDA pin group (%d) plus 1 uF and 4.7 uF bulk' % len(fc_caps),
          len(fc_caps) == 5)
    for n in (1, 2, 3, 4):
        e = [x for x in circuit.build('esc') if x.note.startswith('U_ESC%d V' % n)]
        check(S, 'ESC %d MCU: 100 nF on VDD/VDDA; the 4.7 uF of bulk is the buck\'s shared 10 uF '
                 '(its distance: Board ESC)' % n, len(e) == 1 and e[0].part == 'C100N')


# ------------------------------------------------------------------ boards
def check_board(board, name):
    S = 'Board %s' % board.upper()
    path = os.path.join(V1, board, name + '.kicad_pcb')
    if not os.path.exists(path):
        check(S, 'installed board', False, path)
        return
    tmp = os.path.join(V1, board, '.verify_drc.json')
    e, w, u = pcb.drc(path, tmp)
    os.remove(tmp)
    check(S, 'KiCad DRC (all severities, zones refilled): %d errors, %d warnings, %d unconnected'
          % (len(e), len(w), len(u)), not (e or w or u))
    bad = fab.check_netlist(path, board)
    check(S, 'every pad on the board carries the net circuit.py gives it', not bad, str(bad[:3]))
    b = pcbnew.LoadBoard(path)
    xs, ys = [], []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(p.x / 1e6); ys.append(p.y / 1e6)
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    check(S, 'outline %.2f x %.2f mm' % (w, h), abs(w - 36.0) < 0.01 and abs(h - 36.0) < 0.01)
    # the four mounting slots: an arc of the 3.2 mm hole round each 25.5 mm
    # position, open to its corner
    arcs = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_ARC]
    got = sorted((round(a.GetCenter().x / 1e6 - pcb.CX, 2), round(a.GetCenter().y / 1e6 - pcb.CY, 2),
                  round(a.GetRadius() / 1e6, 2)) for a in arcs)
    want = sorted((sx * pcb.HOLE, sy * pcb.HOLE, pcb.HOLE_D / 2) for sx in (-1, 1) for sy in (-1, 1))
    poly = pcbnew.SHAPE_POLY_SET()
    closed = b.GetBoardPolygonOutlines(poly, False) and poly.OutlineCount() == 1
    check(S, 'mounting: four %.1f mm holes on the 25.5 mm pattern, each open to its corner through a %.1f mm slot '
             '(M2 soft-mount grommets slide in); outline closed' % (pcb.HOLE_D, pcb.SLOT_W),
          got == [tuple(round(v, 2) for v in t) for t in want] and closed, str(got))
    holes = sorted((round(p.GetPosition().x / 1e6 - pcb.CX, 2), round(p.GetPosition().y / 1e6 - pcb.CY, 2))
                   for fp in b.GetFootprints() if fp.GetReference().startswith('H') for p in fp.Pads())
    check(S, 'mounting holes on the 25.5 mm square: %s' % holes,
          all(abs(abs(x) - 12.75) < 0.01 and abs(abs(y) - 12.75) < 0.01 for x, y in holes) and len(holes) == 4)
    if board == 'esc':
        # gate resistors at their FETs' gate pins, bootstrap caps at their
        # driver's BST and SH pins (pad centre to pad centre)
        pos = {}
        for fp_ in b.GetFootprints():
            for p_ in fp_.Pads():
                if p_.GetNumber():
                    pos[(fp_.GetReference(), p_.GetNumber())] = p_.GetPosition()
        dist = lambda a, c: math.hypot(pos[a].x - pos[c].x, pos[a].y - pos[c].y) / 1e6
        comps_ = circuit.build('esc')
        far_g, far_b = [], []
        for c in comps_:
            if c.note.startswith(('gate high ', 'gate low ')):
                fet = [x for x in comps_ if x.part == 'TPN2R304PL' and x.pins.get('4') == c.pins['2']][0]
                far_g.append(dist((c.ref, '2'), (fet.ref, '4')))
            if c.note.startswith('bootstrap '):
                gd = [x for x in comps_ if x.ref.startswith('U_GD') and c.pins['1'] in x.pins.values()][0]
                bst = [k for k, v in gd.pins.items() if v == c.pins['1']][0]
                sh = [k for k, v in gd.pins.items() if v == c.pins['2']][0]
                far_b.append(max(dist((c.ref, '1'), (gd.ref, bst)), dist((c.ref, '2'), (gd.ref, sh))))
        check(S, 'gate resistors at their FETs: %d, each within %.2f mm of its FET\'s gate pin'
              % (len(far_g), max(far_g)), len(far_g) == 24 and max(far_g) <= 2.0)
        check(S, 'bootstrap capacitors at their drivers: %d, each pad within %.2f mm of its BST or SH pin'
              % (len(far_b), max(far_b)), len(far_b) == 12 and max(far_b) <= 1.5)
        # the four MCUs share the buck's 10 uF output capacitor as bulk
        bulk = find('esc', 'buck output')[0].ref
        c = [p for p in b.FindFootprintByReference(bulk).Pads() if p.GetNetname() == '+3V3'][0].GetPosition()
        far = []
        for n in (1, 2, 3, 4):
            vdd = [p for p in b.FindFootprintByReference('U_ESC%d' % n).Pads() if p.GetNetname() == '+3V3']
            far.append(min(math.hypot(p.GetPosition().x - c.x, p.GetPosition().y - c.y) for p in vdd) / 1e6)
        check(S, 'MCU bulk: the buck\'s 10 uF (%s) to each ESC MCU\'s VDD pin: %s mm on +3V3'
              % (bulk, ', '.join('%.1f' % d for d in far)), 'INFO',
              'the 100 nF at each pin takes the fast edges; bulk serves the slow load steps')
    ds = b.GetDesignSettings()
    check(S, '%d copper layers; min track %.2f mm, clearance %.2f mm, via %.2f/%.2f mm (JLCPCB/PCBWay standard)'
          % (b.GetCopperLayerCount(), ds.m_TrackMinWidth / 1e6, ds.m_MinClearance / 1e6, ds.m_ViasMinSize / 1e6,
             ds.m_MinThroughDrill / 1e6), ds.m_TrackMinWidth >= 90000 and ds.m_MinThroughDrill >= 200000)
    txt = open(path).read()
    # inner copper weight (the board file's stackup) against the fab's
    # finest track and gap for it: 2 oz etches no finer than 0.15 mm, and
    # the DRC above holds the inner layers to that when the board has it
    # (pcb.copper_rules in its .kicad_dru)
    inner = sorted(set(float(t) for t in re.findall(r'\(layer "In\d+\.Cu"\s+\(type "copper"\)\s+\(thickness ([\d.]+)\)',
                                                      txt)))
    oz = {0.0175: 0.5, 0.035: 1.0, 0.07: 2.0}
    weights = [oz.get(t) for t in inner]
    dru = open(os.path.splitext(path)[0] + '.kicad_dru').read() if os.path.exists(os.path.splitext(path)[0] + '.kicad_dru') else ''
    held = all(w is not None and (pcb.FAB_MIN[w] <= pcb.FAB_MIN[1.0] or pcb.copper_rules(w) in dru) for w in weights)
    check(S, 'inner copper %s oz: the fab\'s finest track and gap for it, %s mm, %s'
          % ('/'.join('%g' % w for w in weights if w), '/'.join('%.2f' % pcb.FAB_MIN[w] for w in weights if w),
             'are what the board-setup minimums and the DRC hold every layer to'),
          len(weights) == 1 and held, str(inner))
    check(S, 'stackup in the board file: black mask, white silk, ENIG',
          '(color "Black")' in txt and '(color "White")' in txt and '(copper_finish "ENIG")' in txt)
    prod = os.path.join(V1, board, 'production')
    zp = os.path.join(prod, name + '-gerbers.zip')
    if os.path.exists(zp):
        names = zipfile.ZipFile(zp).namelist()
        ncu = b.GetCopperLayerCount()
        cu = [x for x in names if re.search(r'_Cu\.g', x)]
        check(S, 'gerber zip: %d files, %d copper layers, drill files, job file' % (len(names), len(cu)),
              len(cu) == ncu and any(x.endswith('PTH.drl') for x in names) and any(x.endswith('.gbrjob') for x in names))
        job = zipfile.ZipFile(zp).read([x for x in names if x.endswith('.gbrjob')][0]).decode()
        check(S, 'gerber job file states %d layers and ENIG' % ncu,
              ('"LayerNumber": %d' % ncu in job or '"LayerNumber":  %d' % ncu in job) and 'ENIG' in job)
    cpl = os.path.join(prod, name + '-cpl-jlcpcb.csv')
    if os.path.exists(cpl):
        import csv
        rows_ = {r['Designator']: r for r in csv.DictReader(open(cpl))}
        comps_ = {c.ref: c for c in circuit.build(board)}
        bad = []
        for fp in b.GetFootprints():
            c = comps_.get(fp.GetReference())
            if c is None or c.part not in parts.PARTS:
                continue
            off = parts.PARTS[c.part].get('jlc_rot', 0)
            want = (fp.GetOrientationDegrees() + off) % 360
            if fp.IsFlipped():
                want = (180 - fp.GetOrientationDegrees()) % 360
            if abs((float(rows_[fp.GetReference()]['Rotation']) - want + 180) % 360 - 180) > 0.01:
                bad.append(fp.GetReference())
        offs = sorted('%s +%d' % (c.ref, parts.PARTS[c.part]['jlc_rot']) for c in comps_.values()
                      if c.part in parts.PARTS and parts.PARTS[c.part].get('jlc_rot'))
        check(S, 'CPL rotation of every part = board rotation (+ JLCPCB footprint offset for second-source '
                 'parts: %s)' % (', '.join(offs) or 'none'), not bad, ', '.join(bad))
    for f in ('-bom-jlcpcb.csv', '-cpl-jlcpcb.csv', '-bom-pcbway.csv', '-assembly.pdf', '-netlist.csv'):
        check(S, 'production/%s%s present' % (name, f), os.path.exists(os.path.join(prod, name + f)))


# ------------------------------------------------------------------ solder pads, 3D models
def check_pads_models(board, name):
    """The pads things are soldered to by hand (battery and motor leads,
    signal wires, test clips, the solder jumper): mask open over each, and
    no other part over any of them, neither its courtyard nor its 3D body as
    the renders draw it, on every side the pad has copper (a plated pad's
    joint wets both).  And every 3D model inside its part's courtyard: a
    model drawn off its part shows bodies over pads the board keeps clear."""
    import models3d
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    S = 'Board %s' % board.upper()
    path = os.path.join(V1, board, name + '.kicad_pcb')
    b = pcbnew.LoadBoard(path)
    comps = {c.ref: c for c in circuit.build(board)}
    outl = models3d.board_outlines(path, b)

    def polys(sps):
        return [Polygon([(sps.Outline(k).CPoint(i).x / 1e6, sps.Outline(k).CPoint(i).y / 1e6)
                         for i in range(sps.Outline(k).PointCount())]) for k in range(sps.OutlineCount())]
    court = {fp.GetReference(): {'T': unary_union(polys(fp.GetCourtyard(pcbnew.F_CrtYd))),
                                 'B': unary_union(polys(fp.GetCourtyard(pcbnew.B_CrtYd)))} for fp in b.GetFootprints()}
    off, sunk = [], []
    for ref, (side, pg, lb, zr) in sorted(outl.items()):
        cy = court[ref][side]
        if cy.is_empty:
            off.append('%s (no courtyard)' % ref)
        elif pg.difference(cy.buffer(0.15)).area > 0.01:
            off.append('%s %.1f mm2 out' % (ref, pg.difference(cy.buffer(0.15)).area))
        tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in b.FindFootprintByReference(ref).Pads())
        if not tht and abs(zr[0]) > 0.02:
            sunk.append('%s %+.2f mm' % (ref, zr[0]))
    check(S, '3D models: all %d inside their parts\' courtyards (0.15 mm), so the renders show each body '
             'where the part goes' % len(outl), not off, ', '.join(off))
    check(S, '3D models: every surface-mount part\'s model starts at the board (0.02 mm), none sunk into it '
             'or showing through to the other side', not sunk, ', '.join(sunk))
    padrefs = sorted(r for r, c in comps.items() if c.part in parts.PADS and parts.PADS[c.part]['kind'] == 'PAD')
    bad, n, near = [], 0, (99.0, '')
    for ref in padrefs:
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            for side, cu, mask in (('T', pcbnew.F_Cu, pcbnew.F_Mask), ('B', pcbnew.B_Cu, pcbnew.B_Mask)):
                if not p.IsOnLayer(cu):
                    continue
                n += 1
                where = '%s.%s %s' % (ref, p.GetNumber() or '-', 'top' if side == 'T' else 'bottom')
                if not p.IsOnLayer(mask):
                    bad.append(where + ': no mask opening')
                pg = unary_union(polys(p.GetEffectivePolygon(cu)))
                for other, cys in court.items():
                    if other != ref and cys[side].intersection(pg).area > 1e-4:
                        bad.append('%s: under %s\'s courtyard' % (where, other))
                for other, (s2, body, lb, zr) in outl.items():
                    if other == ref or s2 != side:
                        continue
                    if body.intersection(pg).area > 1e-4:
                        bad.append('%s: under %s\'s 3D body' % (where, other))
                    elif comps[ref].part != 'PAD_TP' and body.distance(pg) < near[0]:
                        near = (body.distance(pg), '%s from %s' % (other, where))
    check(S, 'solder pads: %d pad faces on %d parts (battery, motor, wire and test pads, jumpers), mask open '
             'over every one, no part\'s courtyard or 3D body over any' % (n, len(padrefs)), not bad, '; '.join(bad[:6]))
    check(S, 'nearest part body to a wire pad: %.2f mm (%s)' % near, 'INFO',
          'room for the iron and the wire beside it')


# ------------------------------------------------------------------ silkscreen
def stroke_widths(p, px=400):
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from skimage.morphology import skeletonize
    x0, y0, x1, y1 = p.bounds
    W, H = int((x1 - x0) * px) + 10, int((y1 - y0) * px) + 10
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    d.polygon([((x - x0) * px + 5, (y - y0) * px + 5) for x, y in p.exterior.coords], fill=255)
    for h in p.interiors:
        d.polygon([((x - x0) * px + 5, (y - y0) * px + 5) for x, y in h.coords], fill=0)
    a = np.array(im) > 127
    return 2 * ndimage.distance_transform_edt(a)[skeletonize(a)] / px


def check_silk(board, name):
    S = 'Silkscreen %s' % board.upper()
    import numpy as np
    import brand
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    path = os.path.join(V1, board, name + '.kicad_pcb')
    b = pcbnew.LoadBoard(path)
    for layer, lname in ((pcbnew.F_SilkS, 'top'), (pcbnew.B_SilkS, 'bottom')):
        polys = []
        other = 0
        for d in b.GetDrawings():
            if d.GetLayer() != layer:
                continue
            if isinstance(d, pcbnew.PCB_SHAPE) and d.GetShape() == pcbnew.SHAPE_T_POLY:
                ps = d.GetPolyShape()
                for k in range(ps.OutlineCount()):
                    ol = ps.Outline(k)
                    ext = [(ol.CPoint(i).x / 1e6, ol.CPoint(i).y / 1e6) for i in range(ol.PointCount())]
                    holes = []
                    for h in range(ps.HoleCount(k)):
                        hl = ps.Hole(k, h)
                        holes.append([(hl.CPoint(i).x / 1e6, hl.CPoint(i).y / 1e6) for i in range(hl.PointCount())])
                    polys.append(Polygon(ext, holes))
            else:
                other += 1
        # stroke width = twice the distance from the centre line to the
        # edge, read along each outline's skeleton (400 px/mm raster)
        medians, allw = [], []
        for p in polys:
            w = stroke_widths(p)
            if len(w):
                medians.append((float(np.median(w)), p))
                allw.extend(w)
        thin = sorted(((m, p) for m, p in medians if m < brand.MIN_STROKE), key=lambda t: t[0])
        med = float(np.median(allw)) if allw else 0
        p10 = float(np.percentile(allw, 10)) if allw else 0
        check(S, '%s: %d outlines; stroke width median %.3f mm, 10th percentile %.3f mm (pass: median >= %.2f, '
              '10th percentile >= 0.12)' % (lname, len(polys), med, p10, brand.MIN_STROKE),
              med >= brand.MIN_STROKE and p10 >= 0.12,
              ('%d outlines (hyphens, underscores, crossbars) have their own median under %.2f mm, the thinnest %.3f mm '
               'at %s; JLCPCB lists 0.153 mm as the silkscreen minimum' %
               (len(thin), brand.MIN_STROKE, thin[0][0], tuple(round(v - 100, 1) for v in thin[0][1].centroid.coords[0])))
              if thin else 'every outline has its median stroke over the floor')
        check(S, '%s: no stroke-font text left (brand faces only)' % lname,
              not any(isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == layer for d in b.GetDrawings()))
        # the OffGrid mark: its ring, found by shape, at or over the brand's
        # minimum (16 px for the mark; 24 px in the lockup, the FC's bottom)
        ring = max(brand.mark().geoms, key=lambda g: g.area)
        found = []
        for p in polys:
            x0, y0, x1, y1 = p.bounds
            if x1 - x0 < 1.0:
                continue
            k = (x1 - x0) / (ring.bounds[2] - ring.bounds[0])
            from shapely import affinity
            r = affinity.scale(ring, k, k, origin=(0, 0))
            r = affinity.translate(r, x0 - r.bounds[0], y0 - r.bounds[1])
            if p.symmetric_difference(r).area < 0.1 * p.area:
                found.append((x1 - x0) * 200 / 138 / (25.4 / 96))
        if found or (board, lname) in (('fc', 'top'), ('fc', 'bottom'), ('esc', 'top')):
            need = 24 if (board, lname) == ('fc', 'bottom') else 16
            check(S, '%s: OffGrid mark at %s px (brand minimum %d px, 1 px = 1/96 in)'
                  % (lname, ', '.join('%.1f' % v for v in found) or 'none', need),
                  bool(found) and min(found) >= need)
        from shapely.geometry import Point
        flanges = unary_union([Point(pcb.CX + sx * pcb.HOLE, pcb.CY + sy * pcb.HOLE).buffer(pcb.HOLE_KEEPOUT_R)
                               for sx in (-1, 1) for sy in (-1, 1)])
        under = [p for p in polys if p.intersects(flanges)]
        check(S, '%s: no ink under the grommet flanges (%.1f mm round each mounting hole)' % (lname, pcb.HOLE_KEEPOUT_R),
              not under, '%d outlines, the first at %s' % (len(under), tuple(round(v - 100, 1) for v in
                                                                               under[0].centroid.coords[0]))
              if under else '')


def check_brand():
    S = 'Brand'
    import brand
    from shapely import affinity
    m, w = brand.lockup()
    check(S, 'mark geometry from offgrid-mark-bone.svg: ring r 58, stroke 22, gap at the top, node r 17',
          abs(m.bounds[2] - m.bounds[0] - 138) < 0.1)
    try:
        import numpy as np
        from PIL import Image, ImageDraw
        ref = np.array(Image.open(BRAND_PNG).convert('RGB')).astype(int)
    except Exception as ex:
        check(S, 'mark against the brand PNG', 'SKIP', 'brand repo not found (%s)' % BRAND_PNG)
        return
    ember = (abs(ref[..., 0] - 255) < 60) & (abs(ref[..., 1] - 106) < 60) & (ref[..., 2] < 80)
    im = Image.new('L', (1600, 400), 0); d = ImageDraw.Draw(im)
    for p in (m.geoms if hasattr(m, 'geoms') else [m]):
        d.polygon([(x * 2, y * 2) for x, y in p.exterior.coords], fill=255)
        for h in p.interiors:
            d.polygon([(x * 2, y * 2) for x, y in h.coords], fill=0)
    mine = np.array(im) > 127
    iou = (mine & ember).sum() / (mine | ember).sum()
    check(S, 'mark drawn from the SVG numbers overlaps the brand\'s own 1600 px lockup PNG: IoU %.3f' % iou, iou > 0.95)
    for f, face in (('Instrument Sans', brand.SANS), ('JetBrains Mono', brand.MONO)):
        h = hashlib.sha256(open(face, 'rb').read()).hexdigest()
        check(S, '%s variable font vendored (OFL), sha256 %s...' % (f, h[:16]), os.path.exists(face))


# ------------------------------------------------------------------ firmware
def check_firmware():
    S = 'Firmware'
    readme = open(os.path.join(FW, 'README.md')).read()
    for h, f in re.findall(r'^([0-9a-f]{64})  (\S+)$', readme, re.M):
        p = os.path.join(FW, f)
        ok = os.path.exists(p) and hashlib.sha256(open(p, 'rb').read()).hexdigest() == h
        check(S, '%s matches the sha256 in firmware/README.md' % f, ok)
    stale = sorted(os.path.relpath(p, FW) for p in glob.glob(os.path.join(FW, '**', '*'), recursive=True)
                   if re.search(r'CHEAPDRONE|F051|F421|at32', os.path.basename(p), re.I))
    check(S, 'no files left from the F051/AT32 ESC or the CHEAPDRONE configs', not stale, ', '.join(stale))
    # Betaflight: one image per config, carrying its board name
    for k, cfg in bf_configs().items():
        name = cdefine(cfg, 'BOARD_NAME')
        p = os.path.join(FW, 'betaflight/betaflight_2025.12.5_STM32G47X_%s.hex' % name)
        img = bytes(read_ihex(p).values()) if os.path.exists(p) else b''
        check(S, 'betaflight/%s carries BOARD_NAME %s' % (os.path.basename(p), name),
              re.search(rb'[^A-Z0-9_]' + name.encode() + rb'\x00', img) is not None)
    # AM32 firmware: application at 0x08001000, FILE_NAME just below the settings page
    fw = glob.glob(os.path.join(FW, 'am32', 'AM32_%s_*.hex' % AM32_TARGET))
    bl = glob.glob(os.path.join(FW, 'am32', 'AM32_G071_BOOTLOADER_*.hex'))
    if len(fw) == 1:
        mem = read_ihex(fw[0])
        eeprom, app = 0x0800F800, 0x08001000          # SIXTY_FOUR_KB_MEMORY / APPLICATION_ADDRESS (MCU_G071)
        if AM32:
            tgt = am32_targets()[0]
            mcu = c_block(tgt, 'MCU_G071') if tgt else ''
            m = re.search(r'#ifdef SIXTY_FOUR_KB_MEMORY\s*\n\s*#define EEPROM_START_ADD \(uint32_t\)(0x[0-9A-Fa-f]+)', mcu)
            eeprom = int(m.group(1), 16) if m else eeprom
            app = int(cdefine(mcu, 'APPLICATION_ADDRESS') or hex(app), 16)
        fname = bytes(mem.get(a, 0) for a in range(eeprom - 32, eeprom)).split(b'\x00')[0].decode('ascii', 'replace')
        code = [a for a in mem if a < eeprom - 32]
        check(S, 'am32/%s: code 0x%08X-0x%08X (from APPLICATION_ADDRESS, below the settings page at 0x%08X), '
                 'FILE_NAME "%s" at 0x%08X' % (os.path.basename(fw[0]), min(code), max(code), eeprom, fname, eeprom - 32),
              min(code) == app and max(mem) < eeprom and fname == AM32_TARGET)
    else:
        check(S, 'one AM32 %s image in firmware/am32' % AM32_TARGET, False, str(fw))
    # AM32 bootloader: its device-info block names the comms pin and the flash layout
    if len(bl) == 1:
        mem = read_ihex(bl[0])
        info = bytes(mem.get(a, 0xFF) for a in range(0x08000FE0, 0x08000FE0 + 17))
        m = re.search(r'BOOTLOADER_(P[A-C])(\d+)_(\d+)K', os.path.basename(bl[0]))
        pin_code = ((ord(m.group(1)[1]) - ord('A')) << 4 | int(m.group(2))) if m else None
        size_code = {32: 0x1F, 64: 0x35, 128: 0x2B}.get(int(m.group(3))) if m else None
        want_pin = None
        if AM32 and am32_targets()[0]:
            gd = dict(re.findall(r'#define\s+(\w+)\s+(\S+)', c_block(am32_targets()[0], 'HARDWARE_GROUP_G0_A')))
            want_pin = 'P%s%s' % (gd['INPUT_PIN_PORT'][-1], gd['INPUT_PIN'].split('_')[-1])
        check(S, 'am32/%s: device info at 0x08000FE0 (AM32-bootloader main.c devinfo): magic, "471", pin code 0x%02X '
                 '(%s%s; the ESC input is %s), flash size code 0x%02X (%sK: settings at 0x0800F800), no code past '
                 '0x08001000' % (os.path.basename(bl[0]), info[11], m.group(1) if m else '?', m.group(2) if m else '?',
                                 want_pin or '?', info[12], m.group(3) if m else '?'),
              info[:8] == bytes.fromhex('dae32559d963b84e') and info[8:11] == b'471' and info[11] == pin_code
              and info[12] == size_code and m.group(3) == '64' and max(mem) < 0x08001000
              and (want_pin is None or want_pin == '%s%s' % (m.group(1), m.group(2))))
    else:
        check(S, 'one AM32 G071 bootloader in firmware/am32', False, str(bl))


def main():
    global AM32
    if not AM32:
        for guess in glob.glob('/tmp/claude-*/**/am32', recursive=True):
            if os.path.exists(os.path.join(guess, 'Inc/targets.h')):
                AM32 = guess
                break
    check_fc_pins()
    check_esc_pins()
    check_fw_scales()
    check_power()
    for board, name in (('fc', 'ridge3-fc'), ('esc', 'ridge3-esc')):
        check_board(board, name)
        if os.path.exists(os.path.join(V1, board, name + '.kicad_pcb')):
            check_pads_models(board, name)
            check_silk(board, name)
    check_brand()
    check_firmware()
    n_fail = sum(1 for r in rows if r[2] == 'FAIL')
    n_pass = sum(1 for r in rows if r[2] == 'PASS')
    out = ['# Ridge 3 stack: design verification', '',
           'Generated by `src/verify.py`. %d checks passed, %d failed, %d skipped.' %
           (n_pass, n_fail, len(rows) - n_pass - n_fail), '',
           '**What this is not:** no board has been built. Nothing here was measured on hardware. '
           'These checks compare the design against sources other than itself (KiCad\'s STM32 '
           'symbol libraries, the Betaflight and AM32 sources, datasheet figures, the brand '
           'files) and run the fab outputs through KiCad\'s DRC. Bring-up on the bench, in the '
           'order in the README, is still the test.', '']
    sec = None
    for s, name, res, detail in rows:
        if s != sec:
            out += ['', '## ' + s, '', '| Result | Check | Detail |', '|---|---|---|']
            sec = s
        out.append('| %s | %s | %s |' % (res, name.replace('|', '/'), detail.replace('|', '/')))
    open(os.path.join(V1, 'VERIFICATION.md'), 'w').write('\n'.join(out) + '\n')
    for s, name, res, detail in rows:
        if res != 'PASS':
            print('%s  %s: %s  %s' % (res, s, name, detail))
    print('%d passed, %d failed' % (n_pass, n_fail))
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()
