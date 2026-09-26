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
  * the firmware images against the hashes in firmware/README.md
"""
import os, re, sys, hashlib, glob, zipfile
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
    # Betaflight config.h
    cfg = open(os.path.join(V1, 'firmware/betaflight/configs/CHEAPDRONE_G473/config.h')).read()
    want = {'MOTOR1': 'M1_SIG', 'MOTOR2': 'M2_SIG', 'MOTOR3': 'M3_SIG', 'MOTOR4': 'M4_SIG',
            'BEEPER': 'BEEPER', 'LED0': 'LED0', 'LED_STRIP': 'LED_STRIP',
            'UART1_TX': 'UART1_TX', 'UART1_RX': 'UART1_RX', 'UART2_TX': 'UART2_TX', 'UART2_RX': 'UART2_RX',
            'UART4_TX': 'UART4_TX', 'UART4_RX': 'UART4_RX', 'LPUART1_TX': None, 'LPUART1_RX': 'TLM',
            'SPI1_SCK': 'SPI1_SCK', 'SPI1_SDI': 'SPI1_MISO', 'SPI1_SDO': 'SPI1_MOSI',
            'SPI2_SCK': 'SPI2_SCK', 'SPI2_SDI': 'SPI2_MISO', 'SPI2_SDO': 'SPI2_MOSI',
            'GYRO_1_CS': 'GYRO_CS', 'GYRO_1_EXTI': 'GYRO_INT', 'FLASH_CS': 'FLASH_CS',
            'ADC_VBAT': 'ADC_VBAT', 'ADC_CURR': 'ADC_CURR'}
    seen = set()
    for fn, port in re.findall(r'#define\s+(\w+)_PIN\s+(P[A-G]\d+)', cfg):
        seen.add(fn)
        net = ports.get(port, 'no such port')
        exp = want.get(fn, '?')
        check(S, 'Betaflight %s_PIN %s' % (fn, port), net == exp,
              'carries %s' % net if net else 'not connected (unused on this board)')
    check(S, 'every function this board needs is defined in config.h', set(want) <= seen,
          ', '.join(sorted(set(want) - seen)))
    # the peripherals on the far end of those nets
    far = {'GYRO_CS': ('U_IMU', '12'), 'SPI1_SCK': ('U_IMU', '13'), 'SPI1_MOSI': ('U_IMU', '14'),
           'SPI1_MISO': ('U_IMU', '1'), 'GYRO_INT': ('U_IMU', '4'), 'FLASH_CS': ('U_FLASH', '1'),
           'SPI2_MISO': ('U_FLASH', '2'), 'SPI2_MOSI': ('U_FLASH', '5'), 'SPI2_SCK': ('U_FLASH', '6')}
    names = {'U_IMU': 'ICM-42688-P (DS-000347 pin table)', 'U_FLASH': 'W25Q128 (SOIC/WSON-8 pinout)'}
    for net, (ref, pin) in far.items():
        check(S, '%s reaches %s pin %s' % (net, ref, pin), comp('fc', ref).pins.get(pin) == net, names[ref])
    check(S, 'HSE crystal on PF0/PF1 with SYSTEM_HSE_MHZ 8',
          c.pins['5'] == 'HSE_IN' and c.pins['6'] == 'HSE_OUT' and 'SYSTEM_HSE_MHZ      8' in cfg
          and comp('fc', 'Y1').part == 'XTAL8M')
    check(S, 'USB D+/D- on PA12/PA11', ports['PA12'] == 'USB_DP' and ports['PA11'] == 'USB_DM')
    check(S, 'SWD on PA13/PA14 to test pads', ports['PA13'] == 'SWDIO' and ports['PA14'] == 'SWCLK'
          and comp('fc', 'TP_SWDIO').pins['1'] == 'SWDIO')
    check(S, 'BOOT0 (pin 46, PB8-BOOT0) pulled down 10k, DFU button to 3.3 V',
          pins['46'] == 'PB8' and ports['PB8'] == 'BOOT0'
          and any(x.part == 'R10K' and set(x.pins.values()) == {'BOOT0', 'GND'} for x in circuit.build('fc'))
          and comp('fc', 'SW_BOOT').pins == {'1': '+3V3', '2': 'BOOT0'})
    check(S, 'NRST (pin 7, PG10-NRST) to the RST test pad, 100 nF to ground',
          pins['7'] == 'PG10' and ports['PG10'] == 'NRST' and comp('fc', 'TP_NRST').pins['1'] == 'NRST'
          and any(x.part == 'C100N' and set(x.pins.values()) == {'NRST', 'GND'} for x in circuit.build('fc')))


def am32_group(name):
    t = open(os.path.join(AM32, 'Inc/targets.h')).read()
    i = t.index('#ifdef %s\n' % name)
    j = t.index('#endif', i)
    return t[i:j]


AM32 = os.environ.get('AM32_SRC', '')


def check_esc_pins():
    S = 'ESC pin map'
    pins = symbol_pins('MCU_ST_STM32F0', 'STM32F051K6Ux')
    for n in (1, 2, 3, 4):
        ports, power, _, c = port_nets('esc', 'U_ESC%d' % n, 'MCU_ST_STM32F0', 'STM32F051K6Ux')
        bad = []
        for name, nets in power.items():
            if name.startswith(('VDD', 'VDDA')) and any(x != '+3V3' for x in nets):
                bad.append('%s=%s' % (name, nets))
            if name.startswith('VSS') and any(x != 'GND' for x in nets):
                bad.append('%s=%s' % (name, nets))
        check(S, 'ESC %d: VDD/VDDA on +3V3, VSS on GND (KiCad symbol STM32F051K6Ux)' % n, not bad, ', '.join(bad))
    ports, _, _, c = port_nets('esc', 'U_ESC1', 'MCU_ST_STM32F0', 'STM32F051K6Ux')
    tgt = open(os.path.join(AM32, 'Inc/targets.h')).read() if AM32 else None
    if not tgt:
        check(S, 'AM32 targets.h', 'SKIP', 'set AM32_SRC to an AM32 checkout to check against the firmware')
        return
    fd = tgt[tgt.index('#ifdef FD6288_F051'):]
    fd = fd[:fd.index('#endif')]
    check(S, 'AM32 target FD6288_F051 uses HARDWARE_GROUP_F0_A', 'HARDWARE_GROUP_F0_A' in fd)
    g = am32_group('HARDWARE_GROUP_F0_A')
    d = dict(re.findall(r'#define\s+(\w+)\s+(\S+)', g))
    def port(pin_key, port_key):
        return 'P%s%s' % (d[port_key][-1], d[pin_key].split('_')[-1])
    want = {port('INPUT_PIN', 'INPUT_PIN_PORT'): 'SIG'}
    for ph in 'ABC':
        want[port('PHASE_%s_GPIO_HIGH' % ph, 'PHASE_%s_GPIO_PORT_HIGH' % ph)] = 'H' + ph
        want[port('PHASE_%s_GPIO_LOW' % ph, 'PHASE_%s_GPIO_PORT_LOW' % ph)] = 'L' + ph
        want[d['PHASE_%s_COMP' % ph].replace('COMP_', '')] = 'CMP_' + ph
    for n in (1, 2, 3, 4):
        ports, _, _, _ = port_nets('esc', 'U_ESC%d' % n, 'MCU_ST_STM32F0', 'STM32F051K6Ux')
        bad = ['%s wants %s, has %s' % (p, f, ports.get(p)) for p, f in want.items()
               if ports.get(p) != 'M%d_%s' % (n, f)]
        check(S, 'ESC %d: input, six gate outputs and three comparator inputs match group F0_A' % n,
              not bad, '; '.join(bad) or ', '.join('%s %s' % (p, f) for p, f in sorted(want.items())))
    # the MCU family defaults: which comparator, which ADC inputs
    mcu = tgt[tgt.index('#ifdef MCU_F051\n'):]
    mcu = mcu[:mcu.index('\n#endif\n\n')]
    md = dict(re.findall(r'#define\s+(\w+)\s+(\S+)', mcu))
    overridden = [k for k in ('CURRENT_ADC_PIN', 'VOLTAGE_ADC_PIN') if k in g or k in fd]
    check(S, 'AM32 MCU_F051 uses COMP1 (MAIN_COMP %s); COMP1 + input is PA1 (RM0091): virtual neutral there'
          % md.get('MAIN_COMP'), md.get('MAIN_COMP') == 'COMP1' and all(
              port_nets('esc', 'U_ESC%d' % n, 'MCU_ST_STM32F0', 'STM32F051K6Ux')[0]['PA1'] == 'M%d_NEUTRAL' % n
              for n in (1, 2, 3, 4)))
    vpin = 'PA' + md.get('VOLTAGE_ADC_PIN', '?').split('_')[-1]
    cpin = 'PA' + md.get('CURRENT_ADC_PIN', '?').split('_')[-1]
    check(S, 'AM32 F051 battery voltage ADC on %s, current on %s (not overridden by the target): %s, %s'
          % (vpin, cpin, ports.get(vpin), ports.get(cpin)),
          not overridden and ports.get(vpin) == 'ESC_VSENSE' and ports.get(cpin) == 'GND',
          'current input grounded: no sensor per ESC, reads 0 A')
    check(S, 'ESC voltage divider matches TARGET_VOLTAGE_DIVIDER 65 (ratio 6.5)',
          'TARGET_VOLTAGE_DIVIDER 65' in fd and abs(esc_vsense_ratio() - 6.5) < 1e-9,
          'ratio %.3f' % esc_vsense_ratio())


# ------------------------------------------------------------------ circuit arithmetic
def esc_vsense_ratio():
    top = value(find('esc', 'ESC vsense top')[0].part)
    bot = value(find('esc', 'ESC vsense bottom')[0].part)
    return (top + bot) / bot


def check_power():
    S = 'Power and analog'
    VREF = 0.6          # LMR51420 feedback reference (datasheet 7.5: 0.6 V)
    t, b = value(find('fc', 'BEC feedback top')[0].part), value(find('fc', 'BEC feedback bottom')[0].part)
    v = VREF * (1 + t / b)
    check(S, 'FC BEC: 0.6 V x (1 + %gk/%gk) = %.2f V (5 V rail, USB-safe)' % (t / 1e3, b / 1e3, v), 4.9 <= v <= 5.25)
    t, b = value(find('esc', 'buck feedback top')[0].part), value(find('esc', 'buck feedback bottom')[0].part)
    v = VREF * (1 + t / b)
    check(S, 'ESC buck: 0.6 V x (1 + %gk/%gk) = %.3f V (STM32F051: 2.0-3.6 V)' % (t / 1e3, b / 1e3, v),
          3.2 <= v <= 3.45)
    t, b = value(find('fc', 'VBAT divider top')[0].part), value(find('fc', 'VBAT divider bottom')[0].part)
    k = (t + b) / b
    check(S, 'FC VBAT divider %gk/%gk: ratio %.1f -> vbat_scale %d; 4S full 16.8 V -> %.2f V at the ADC'
          % (t / 1e3, b / 1e3, k, round(k * 10), 16.8 / k), round(k * 10) == 110 and 16.8 / k < 3.3)
    cli = open(os.path.join(V1, 'firmware/betaflight/cli-setup.txt')).read()
    check(S, 'cli-setup.txt sets vbat_scale 110', 'set vbat_scale = 110' in cli)
    r = esc_vsense_ratio()
    check(S, 'ESC battery sense: 16.8 V / %.1f = %.2f V at PA3 (< 3.3 V)' % (r, 16.8 / r), 16.8 / r < 3.3)
    bt, bb = value(find('esc', 'BEMF A')[0].part), value(find('esc', 'BEMF A')[1].part)
    kr = bb / (bt + bb)
    check(S, 'BEMF divider %gk/%gk: 16.8 V phase -> %.2f V at the comparator (< VDDA 3.33 V)'
          % (bt / 1e3, bb / 1e3, 16.8 * kr), 16.8 * kr < 3.3)
    rn = value(find('esc', 'neutral to ground')[0].part)
    rs = value(find('esc', 'neutral A')[0].part) / 3
    kn = rn / (rs + rn)
    check(S, 'virtual neutral scales like the phases: %.4f vs %.4f (%.1f %% apart)' % (kn, kr, 100 * (kn / kr - 1)),
          abs(kn / kr - 1) < 0.03)
    # gate drive
    check(S, 'gate driver VCC = VBAT through 10 ohm: 4S 12.0-16.8 V inside JSM6288Q VCC 8-20 V and '
             'AON7934 VGS +/-20 V', True, 'not for 2S/3S at low charge: below driver UVLO')
    cb = value(find('esc', 'bootstrap A')[1].part) if find('esc', 'bootstrap A')[1].part.startswith('C') \
        else value(find('esc', 'bootstrap A')[0].part)
    QG = 11e-9      # AON7934 Q1 (the high side, D1 on the battery) Qg at 10 V, datasheet max
    dv = QG / cb
    check(S, 'bootstrap %.1f uF vs high-side gate charge <= %d nC: droop %.3f V per turn-on' % (cb * 1e6, QG * 1e9, dv),
          dv < 0.5, 'AON7934 datasheet: Q1 Qg(10 V) max 11 nC')
    # conduction loss, for the record: two FETs conduct at a time in six-step
    # drive, one high side (Q1, <10.2 mOhm) and one low side (Q2, <7.7 mOhm)
    for i in (5, 10, 15):
        p = i * i * (10.2e-3 + 7.7e-3)
        check(S, 'conduction loss per motor at %d A: %.2f W (datasheet max RDS(on) at 25 C)' % (i, p), 'INFO',
              'hot (125 C) max: %.2f W' % (i * i * (13.7e-3 + 10.3e-3)))
    # HSE load caps
    cl = value(find('fc', 'crystal load')[0].part)
    check(S, 'HSE load caps %d pF each: CL = %.1f pF with 3 pF stray (crystal CL 10 pF)' % (cl * 1e12, cl * 1e12 / 2 + 3),
          abs(cl * 1e12 / 2 + 3 - 10) <= 1.5)
    # USB
    cc = [x for x in circuit.build('fc') if x.note.startswith('CC') and x.note.endswith('Rd')]
    check(S, 'USB-C: 5.1k Rd on CC1 and CC2 (C-to-C cables supply 5 V)', len(cc) == 2 and all(x.part == 'R5K1' for x in cc))
    # every MCU VDD pin has a 100 nF
    fc_caps = [x for x in circuit.build('fc') if x.note.startswith('U_FC pin')]
    check(S, 'FC MCU: one 100 nF per VDD/VBAT/VDDA pin group (%d) plus 1 uF and 4.7 uF bulk' % len(fc_caps),
          len(fc_caps) == 5)
    for n in (1, 2, 3, 4):
        e = [x for x in circuit.build('esc') if x.note.startswith('U_ESC%d V' % n)]
        check(S, 'ESC %d MCU: 100 nF on VDD pins 1 and 17, 1 uF on VDDA' % n, len(e) == 3)


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
    check(S, 'outline %.2f x %.2f mm, square corners' % (w, h), abs(w - 33.8) < 0.01 and abs(h - 33.8) < 0.01)
    holes = sorted((round(p.GetPosition().x / 1e6 - pcb.CX, 2), round(p.GetPosition().y / 1e6 - pcb.CY, 2))
                   for fp in b.GetFootprints() if fp.GetReference().startswith('H') for p in fp.Pads())
    check(S, 'mounting holes on the 25.5 mm square: %s' % holes,
          all(abs(abs(x) - 12.75) < 0.01 and abs(abs(y) - 12.75) < 0.01 for x, y in holes) and len(holes) == 4)
    ds = b.GetDesignSettings()
    check(S, '%d copper layers; min track %.2f mm, clearance %.2f mm, via %.2f/%.2f mm (JLCPCB/PCBWay standard)'
          % (b.GetCopperLayerCount(), ds.m_TrackMinWidth / 1e6, ds.m_MinClearance / 1e6, ds.m_ViasMinSize / 1e6,
             ds.m_MinThroughDrill / 1e6), ds.m_TrackMinWidth >= 90000 and ds.m_MinThroughDrill >= 200000)
    txt = open(path).read()
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
    for f in ('-bom-jlcpcb.csv', '-cpl-jlcpcb.csv', '-bom-pcbway.csv', '-assembly.pdf', '-netlist.csv'):
        check(S, 'production/%s%s present' % (name, f), os.path.exists(os.path.join(prod, name + f)))


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
    readme = open(os.path.join(V1, 'firmware/README.md')).read()
    for h, f in re.findall(r'^([0-9a-f]{64})  (\S+)$', readme, re.M):
        p = os.path.join(V1, 'firmware', f)
        ok = os.path.exists(p) and hashlib.sha256(open(p, 'rb').read()).hexdigest() == h
        check(S, '%s matches the sha256 in firmware/README.md' % f, ok)


def main():
    global AM32
    if not AM32:
        for guess in glob.glob('/tmp/claude-*/**/am32', recursive=True):
            if os.path.exists(os.path.join(guess, 'Inc/targets.h')):
                AM32 = guess
                break
    check_fc_pins()
    check_esc_pins()
    check_power()
    for board, name in (('fc', 'cheapdrone-fc'), ('esc', 'cheapdrone-esc')):
        check_board(board, name)
        if os.path.exists(os.path.join(V1, board, name + '.kicad_pcb')):
            check_silk(board, name)
    check_brand()
    check_firmware()
    n_fail = sum(1 for r in rows if r[2] == 'FAIL')
    n_pass = sum(1 for r in rows if r[2] == 'PASS')
    out = ['# Cheap Drone stack v1: design verification', '',
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
