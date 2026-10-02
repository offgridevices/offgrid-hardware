# -*- coding: utf-8 -*-
"""Design verification: every check that can be made without hardware.

    python3 verify.py        writes ../VERIFICATION.md, exits 1 on any FAIL

Nothing here replaces a bench test.  What it does is check the design
against sources other than the design itself:

  * the MCU pin maps against the parts' own pin tables (the flight
    controller's STM32G473 from KiCad's STM32 symbol library; the ESC's
    AT32F421, for which KiCad has no symbol, from Artery's datasheet) and
    against the firmware sources (Betaflight config.h, AM32 targets.h and
    its AT32F421 drivers): the pin each firmware drives carries the right net
  * the other ICs' pins against KiCad's symbol where KiCad has one
    (IIM-42652, AO3400A), else against the pin table of the datasheet
    (DRV8320H, LMR38020, TPS628501, TMP390, INA186, BSS138DW, S25FL128L,
    ISZ023N06LM6)
  * every power pin of every MCU against the rail it needs
  * the regulator, divider, gate-drive, enable and thermostat arithmetic,
    from the resistor and capacitor values in circuit.py and datasheet
    figures
  * the installed boards: DRC, netlist, fab outputs, stackup
  * the silkscreen: every stroke printable, the mark against the brand art
  * the firmware's scale factors (battery dividers, current sense, the FET
    thermistor's table, the gyro's scale and anti-alias filter) against the
    circuit and the parts' datasheets, and the firmware patches applied to
    their sources
  * the firmware images against the hashes in firmware/README.md

Pin tables and figures copied from datasheets into this file are checked
against the datasheets' own text (pdftotext output, or the PDF itself) when
the datasheets are at hand: RIDGE3_DATASHEETS names their folder.  The
firmware sources: AM32_SRC (AM32 at the commit the target patch is for),
AM32_BL_SRC (AM32-bootloader) and BF_SRC (Betaflight 2025.12.5).  Checks
that need a source that is not at hand SKIP.
"""
import math, os, re, sys, hashlib, glob, zipfile, collections, subprocess, struct
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, parts, fab

SYMBOLS = '/usr/share/kicad/symbols'
BRAND_PNG = os.environ.get('OFFGRID_BRAND', '/home/user/offgrid-brand') + \
    '/current/handoff/logo/png/offgrid-wordmark-horizontal-1600.png'

rows = []            # (section, check, result, detail)

# The boards the board-level checks read: board -> .kicad_pcb.  Left empty,
# the installed ones, ../<board>/<name>.kicad_pcb.
BOARD_FILES = {}


def board_file(board, name):
    return BOARD_FILES.get(board) or os.path.join(V1, board, name + '.kicad_pcb')


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


def two_pin(comps, a, b, kind):
    """The two-terminal parts of a kind (R, C, L by reference) between nets a and b."""
    return [x for x in comps if re.match(kind + r'(?!ED)[A-Z_]*\d', x.ref) and len(x.pins) == 2
            and set(x.pins.values()) == {a, b}]


def roles(c, table):
    """pin name -> net, for a part placed per a pin table (pin number -> name)."""
    return {name: c.pins.get(pin) for pin, name in table.items()}


def by_number(table):
    return sorted(table.items(), key=lambda kv: int(re.sub(r'\D', '', kv[0]) or 0))


def git_head(root):
    try:
        return subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ''


# ------------------------------------------------------------------ firmware sources
FW = os.path.join(V1, 'firmware')
BF_CONFIGS = ('RIDGE3',)        # the one build: the IIM-42652, and the ICM-42688-P (its same-pad second source)
BF_COMMIT = '7348054'           # Betaflight 2025.12.5
BF_PATCH = 'betaflight/patches/betaflight_2025.12.5_iim42652_scale_and_aaf.patch'
AM32_PATCH = 'am32/AM32_2738df3_RIDGE3_F421_target.patch'
AM32_COMMIT = '2738df3'
AM32_TARGET = 'RIDGE3_F421'
AM32_BL_COMMIT = '578ff29'
AM32 = os.environ.get('AM32_SRC', '')
AM32_BL = os.environ.get('AM32_BL_SRC', '')
BF = os.environ.get('BF_SRC', '')
DATASHEETS = os.environ.get('RIDGE3_DATASHEETS', '')


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


def patch_hunks(patch):
    """{file: [hunks]} of a git-style unified diff."""
    out = {}
    for block in re.split(r'^diff --git ', patch, flags=re.M)[1:]:
        m = re.search(r'^\+\+\+ b/(\S+)', block, re.M)
        if m:
            out[m.group(1)] = re.split(r'^@@[^\n]*\n', block, flags=re.M)[1:]
    return out


def hunk_text(hunk):
    """(the text a hunk replaces, the text it puts there)."""
    old, new = [], []
    for line in hunk.rstrip('\n').split('\n'):
        if line.startswith('\\'):
            continue
        tag, body = (line[:1], line[1:]) if line else (' ', '')
        if tag in ' -':
            old.append(body)
        if tag in ' +':
            new.append(body)
    return '\n'.join(old) + '\n', '\n'.join(new) + '\n'


def patched(root, patch_rel, rel):
    """(file `rel` of the checkout at `root` with firmware/<patch_rel> applied
    in memory, how), or (None, why) when it does not apply.  A checkout that
    already carries the patch is read as it is."""
    text = open(os.path.join(root, rel)).read()
    name = os.path.basename(patch_rel)
    pairs = [hunk_text(h) for h in patch_hunks(open(os.path.join(FW, patch_rel)).read()).get(rel, [])]
    if not pairs:
        return text, '%s does not touch %s' % (name, rel)
    if all(text.count(new) == 1 for old, new in pairs):
        return text, 'the checkout already has %s' % name
    for old, new in pairs:
        if text.count(old) != 1:
            return None, 'a hunk of %s does not apply to %s' % (name, rel)
        text = text.replace(old, new)
    return text, '%s applied in memory' % name


def am32_source(rel):
    return open(os.path.join(AM32, rel)).read()


def am32_targets():
    """(Inc/targets.h of the AM32 checkout with firmware/am32's patch applied in memory, how)."""
    return patched(AM32, AM32_PATCH, 'Inc/targets.h')


def am32_ntc_table():
    """The NTC_table the patch gives RIDGE3_F421 (Inc/ntc_tables.h), or None."""
    text = patched(AM32, AM32_PATCH, 'Inc/ntc_tables.h')[0]
    if text is None or '#ifdef %s\n' % AM32_TARGET not in text:
        return None
    m = re.search(r'int\s+NTC_table\[(\d+)\]\s*=\s*\{(.*?)\};', c_block(text, AM32_TARGET), re.S)
    if not m:
        return None
    body = re.sub(r'//[^\n]*', '', m.group(2))
    vals = [int(v) for v in re.findall(r'-?\d+', body)]
    return vals if len(vals) == int(m.group(1)) else None


def bf_source(rel):
    """(a Betaflight source file with firmware/betaflight's patch applied in memory, how)."""
    return patched(BF, BF_PATCH, rel)


# ------------------------------------------------------------------ datasheets
# Figures and pin tables copied from the parts' datasheets.  Each is checked
# against the datasheet's own text when the datasheets are at hand.
def ds_text(name):
    """A datasheet's text (pdftotext output) from RIDGE3_DATASHEETS, or None."""
    p = os.path.join(DATASHEETS, name) if DATASHEETS else ''
    if not p or not os.path.exists(p):
        return None
    return open(p, encoding='utf-8', errors='replace').read().replace('\x00', '')


def ds_raw(name):
    """A datasheet PDF's text in content order (pdftotext -raw), or None."""
    p = os.path.join(DATASHEETS, name) if DATASHEETS else ''
    if not p or not os.path.exists(p):
        return None
    try:
        return subprocess.run(['pdftotext', '-raw', p, '-'], capture_output=True, text=True, check=True).stdout
    except Exception:
        return None


# name: (value, datasheet text file, pattern that finds it there, where it is)
FIGS = {
    # TI LMR38020, SNVSC40E (5 V and 9 V BECs)
    'lmr_vref': (1.0, 'ti_lmr38020.txt', r'VREF\nFeedback reference voltage\nFPWM\n0\.985\n1\n1\.015\n',
                 'LMR38020 VREF 1.00 V (0.985-1.015)'),
    'lmr_en_rise': ((1.1, 1.25, 1.4), 'ti_lmr38020.txt', r'VEN-H\nEnable input high level\nVEN rising\n1\.1\n1\.25\n1\.4\n',
                    'LMR38020 EN rising 1.1/1.25/1.4 V'),
    'lmr_en_fall': ((0.95, 1.10, 1.22), 'ti_lmr38020.txt',
                    r'VEN-L\nEnable input low level\nVEN falling\n0\.95\n1\.10\n1\.22\n', 'LMR38020 EN falling 0.95/1.10/1.22 V'),
    'lmr_ihs': ((2.6, 3.2, 3.8), 'ti_lmr38020.txt',
                r'IHS-LIMIT\n High-side current limit\(2\)\n2A Version\n2\.6\n3\.2\n3\.8\n',
                'LMR38020 high-side current limit 2.6/3.2/3.8 A'),
    'lmr_vin': (80, 'ti_lmr38020.txt', r'4\.2-V to 80-V input voltage range', 'LMR38020 input 4.2-80 V'),
    'lmr_rt': ((30970, 1.027), 'ti_lmr38020.txt', r'RT kΩ = 30970 \S\s+fSW kHz\s+\S1\.027',
               'LMR38020 RT(kOhm) = 30970 x fSW(kHz)^-1.027, equation 2'),
    # TI TPS628501, SLUSEC8C (3.3 V)
    'tps_vfb': (0.6, 'ti_tps628501.txt', r'VFB\nFeedback voltage, adjustable version\n0\.6\nV\n', 'TPS628501 VFB 0.6 V'),
    # Murata BLM03AX601SN1D (each ESC channel's 3.3 V bead), JENF243A-0020AD-01
    'blm03': ((0.25, 0.85, 0.90), 'murata_BLM03AX601SN1D.txt', r'BLM03AX601SN1D\s+600±25％\s+600\s+250\s+0\.85\s+0\.90',
              'BLM03AX601SN1D 250 mA at 85 C, 0.85 Ohm max (0.90 after the tests)'),
    'tps_vfb_acc': (0.01, 'ti_tps628501.txt', r'VFB\nFeedback voltage accuracy\nPWM, VIN ≥ VOUT \+ 1V\n–1\n1\n%',
                    'TPS628501 VFB accuracy +/-1 % in PWM (7.5)'),
    'tps_iout': (1.0, 'ti_tps628501.txt', r'TPS628501DRLR\n1A\n', 'TPS628501: 1 A output current (device information)'),
    'tps_ilim': ((2.1, 2.6, 3.0), 'ti_tps628501.txt', r'DC value, for TPS628501;\nVIN = 3V to 6V\n2\.1\n2\.6\n3\.0\n',
                 'TPS628501 high-side current limit 2.1/2.6/3.0 A'),
    # TI TMP390, SBOS904A (video-supply thermostat)
    'tmp390_h20': (20, 'ti_tmp390.txt', r'When the SETB\s+input is connected to ground, Channel A operates with\s+20°C hysteresis',
                   'TMP390: SETB to ground gives channel A 20 C hysteresis'),
    # TI DRV8320H, SLVSDJ3D (ESC gate drivers)
    'drv_vm': (60, 'ti_drv8320.txt', r'VVM\s+Power supply voltage \(VM\)\s+6\s+60\s+V', 'DRV8320 VM 6-60 V (7.3)'),
    'drv_vi': (5.5, 'ti_drv8320.txt',
               r'Input voltage \(CAL, ENABLE, GAIN, IDRIVE, INHx, INLx, MODE, nSCS,\s+VI\s+0\s+5\.5\s+V',
               'DRV8320 ENABLE, INHx, INLx 0-5.5 V (7.3)'),
    'drv_idvdd': (30e-3, 'ti_drv8320.txt', r'IDVDD\s+External load current \(DVDD\)\s+0\s+30\(1\)\s+mA',
                  'DRV8320 DVDD external load 30 mA max (7.3)'),
    'drv_dvdd': ((3.0, 3.3, 3.6), 'ti_drv8320.txt', r'VDVDD\s+DVDD regulator voltage\s+IDVDD = 0 to 30mA\s+3\s+3\.3\s+3\.6\s+V',
                 'DRV8320 DVDD 3.0/3.3/3.6 V (7.5)'),
    'drv_vih': (1.5, 'ti_drv8320.txt', r'VIH\s+Input logic high voltage\s+1\.5\s+5\.5\s+V', 'DRV8320 VIH 1.5 V min (7.5)'),
    'drv_iih': (70e-6, 'ti_drv8320.txt', r'IIH\s+Input logic high current\s+VVIN = 5V\s+50\s+70\s+µA',
                'DRV8320 logic-input current 50/70 uA at 5 V (7.5)'),
    'drv_rpd': (100e3, 'ti_drv8320.txt', r'RPD\s+Pulldown resistance\s+To AGND\s+100\s+kΩ',
                'DRV8320 logic-input pull-down 100 kOhm (7.5)'),
    'drv_vgsh': ((8.4, 11, 12.5), 'ti_drv8320.txt', r'VVM = 13V, IVCP = 0 to 25mA\s+8\.4\s+11\s+12\.5',
                 'DRV8320 high-side gate drive 8.4/11/12.5 V at VM 13 V, 25 mA (7.5)'),
    'drv_vgsh6': ((10e-3, 4, 5, 6), 'ti_drv8320.txt', r'VVM = 6V, IVCP = 0 to 10mA\s+4\s+5\s+6',
                  'DRV8320 high-side gate drive 4/5/6 V at VM 6 V, 10 mA (7.5)'),
    'drv_idrive': ({(0, 'GND'): (10e-3, 20e-3), (18e3, 'GND'): (30e-3, 60e-3), (75e3, 'GND'): (60e-3, 120e-3),
                    (None, None): (120e-3, 240e-3), (75e3, 'DVDD'): (260e-3, 520e-3), (18e3, 'DVDD'): (570e-3, 1140e-3),
                    (0, 'DVDD'): (1000e-3, 2000e-3)}, 'ti_drv8320.txt',
                   r'IDRIVE = Tied to AGND\s+10\s+IDRIVE = 18kΩ ± 5% tied to AGND\s+30\s+IDRIVE = 75kΩ ± 5% tied to AGND\s+60'
                   r'\s+H/W Device\s+IDRIVE = Hi-Z\s+120\s+IDRIVE = 75kΩ ± 5% tied to DVDD\s+260\s+'
                   r'IDRIVE = 18kΩ ± 5% tied to DVDD\s+570\s+IDRIVE = Tied to DVDD\s+1000[\s\S]{0,4000}?'
                   r'IDRIVE = Tied to AGND\s+20\s+IDRIVE = 18kΩ ± 5% tied to AGND\s+60\s+IDRIVE = 75kΩ ± 5% tied to AGND\s+120'
                   r'\s+H/W Device\s+IDRIVE = Hi-Z\s+240\s+IDRIVE = 75kΩ ± 5% tied to DVDD\s+520\s+'
                   r'IDRIVE = 18kΩ ± 5% tied to DVDD\s+1140\s+IDRIVE = Tied to DVDD\s+2000',
                   'DRV8320H IDRIVE levels, source 10-1000 mA / sink 20-2000 mA (7.5)'),
    'drv_vds_hiz': (0.6, 'ti_drv8320.txt', r'H/W Device\s+VDS = Hi-Z\s+0\.6\b', 'DRV8320H VDS pin open: 0.6 V trip (7.5)'),
    'drv_mode_6x': ('GND', 'ti_drv8320.txt', r'6x PWM Mode \(PWM_MODE = 00b or MODE Pin Tied to AGND\)',
                    'DRV8320H MODE tied to AGND: 6x PWM (8.3.1.1.1)'),
    'drv_tdead': (100e-9, 'ti_drv8320.txt', r'DEAD_TIME = 11b\s+400\s+H/W Device\s+100', 'DRV8320H dead time 100 ns (7.5)'),
    # Artery AT32F421, datasheet v2.02 (ESC MCUs)
    'at32_vdd': ((2.4, 3.6), 'artery_AT32F421.txt', r'VDD\s+Digital operating voltage\s+-\s+2\.4\s+3\.6\s+V',
                 'AT32F421 VDD 2.4-3.6 V (table 11)'),
    'at32_idd': (20.7e-3, 'artery_AT32F421.txt', r'120 MHz\s+18\.9\s+20\.7',
                 'AT32F421 IDD 20.7 mA max, 120 MHz, 105 C, all peripherals on (table 19)'),
    'at32_fta': (0.3, 'artery_AT32F421.txt',
                 r'when set as analog mode, it loses 5 V tolerant\s+characteristic, and in this case, the input level must be less '
                 r'than VDD \+ 0\.3 V', 'AT32F421 FTa pins in analog mode: below VDD + 0.3 V (table 5 note 2)'),
    # TI INA186, SBOS318B (ESC current sense)
    'ina186_gain': ({'A1': 25, 'A2': 50, 'A3': 100, 'A4': 200, 'A5': 500}, 'ti_ina186.txt',
                    r'INA186A1: 25 V/V[\s\S]{0,300}INA186A2: 50 V/V[\s\S]{0,300}INA186A3: 100 V/V[\s\S]{0,300}'
                    r'INA186A4: 200 V/V[\s\S]{0,300}INA186A5: 500 V/V', 'INA186 gains A1-A5: 25/50/100/200/500 V/V'),
    'ina186_iq': (90e-6, 'ti_ina186.txt', r'maximum of 90 .A of', 'INA186 supply current 90 uA max'),
    'ina186_vs': ((1.7, 5.5), 'ti_ina186.txt', r'VS\s+3\s+1\s+A2\s+Analog\s+Power supply, 1\.7 V to 5\.5 V',
                  'INA186 VS 1.7-5.5 V (table 5-1)'),
    # Infineon ISZ023N06LM6, rev 2.0 (ESC FETs)
    'fet_vds': (60, 'ifx_ISZ023N06LM6.txt', r'Drain\S+source breakdown voltage\s+V\(BR\)DSS\s+60\b',
                'ISZ023N06LM6 V(BR)DSS 60 V'),
    'fet_vgs': (20, 'ifx_ISZ023N06LM6.txt', r'Gate source voltage\s+VGS\s+\S20\s+\S\s+20\s+V', 'ISZ023N06LM6 VGS +/-20 V'),
    'fet_rds': (2.3e-3, 'ifx_ISZ023N06LM6.txt', r'RDS\(on\),max\s+2\.3\s+m\S', 'ISZ023N06LM6 RDS(on) 2.3 mOhm max'),
    'fet_rds45': (2.9e-3, 'ifx_ISZ023N06LM6.txt', r'2\.60 2\.9\s+VGS=4\.5 V, ID=10 A',
                  'ISZ023N06LM6 RDS(on) 2.9 mOhm max at VGS 4.5 V'),
    'fet_qg': (61e-9, 'ifx_ISZ023N06LM6.txt', r'Qg\s+\S\s+46\s+61\s+nC\s+VDD=30 V, ID=20 A, VGS=0 to 10 V',
               'ISZ023N06LM6 Qg 46/61 nC to 10 V'),
    # inductors
    'spm6530_150': (3.0, 'tdk_SPM6530T-HZ_lcsc.txt',
                    r'15\.0\s+±20%\s+100\s+119\.9\s+109\.0\s+3\.0\s+3\.3\s+SPM6530T-150M-HZ',
                    'TDK SPM6530T-150M-HZ Isat 3.0 A (L down 20 %), Itemp 3.3 A'),
    'tfm_r47': (5.8, 'tdk_TFM252012ALMA.txt', r'0\.47\n±20%\n1\n24\n19\n5\.8\n6\.5\n4\.9\n5\.6\n20\nTFM252012ALMAR47MTAA',
                'TDK TFM252012ALMAR47MTAA Isat 5.8 A (L down 30 %)'),
    # Murata NCU15XH103F60RC (ESC FET thermistor)
    'ncu_b': ((3380, 3434, 3455), 'murata_NCU15XH103F60RC.txt',
              r'NCU15XH103F60RC\s+10k ±1%\s+3380 ±1%\s+3428\s+3434\s+3455',
              'Murata NCU15XH103F60RC 10k, B25/50 3380 K, B25/85 3434 K, B25/100 3455 K'),
    # NDK NX3225GD-8MHZ-STD-CRA-3 (FC HSE crystal)
    'xtal_cl': (8e-12, 'lcsc_NDK_NX3225GD_STD_CRA_3.txt', r'Load capacitance\s+CL\s+-\s+8\s+-\s+pF',
                'NDK NX3225GD STD-CRA-3 load capacitance 8 pF'),
    # TDK IIM-42652 (DS-000440) and ICM-42688-P (DS-000347)
    'iim_whoami': (0x6F, 'tdk_IIM-42652.txt', r'Name: WHO_AM_I[\s\S]{0,120}Reset value: 0x6F', 'IIM-42652 WHO_AM_I 0x6F'),
    'icm42688_whoami': (0x47, 'tdk_ICM-42688-P.txt', r'Name: WHO_AM_I[\s\S]{0,120}Reset value: 0x47',
                        'ICM-42688-P WHO_AM_I 0x47'),
    'iim_gyro_fs': (2000, 'tdk_IIM-42652.txt', r'GYRO_FS_SEL=0\s+±2000\s+\S/s', 'IIM-42652 GYRO_FS_SEL 0: +/-2000 dps (table 1)'),
    'iim_acc_lsb': (2048, 'tdk_IIM-42652.txt', r'ACCEL_FS_SEL =0\s+2,048\s+LSB/g', 'IIM-42652 ACCEL_FS_SEL 0: 2048 LSB/g (table 2)'),
    # Infineon S25FL128L, 002-00124 rev *L (blackbox flash)
    's25_id': ((0x01, 0x60, 0x18), 'ifx_S25FL128L.txt',
               r'00h\s+01h\s+Manufacturer ID for Infineon\s+01h\s+60h\s+Device ID MSB[\s\S]{0,80}18h \(128Mb\)',
               'S25FL128L JEDEC ID 01 60 18 (table 51)'),
}


def fig(key):
    return FIGS[key][0]


def figs_check(S, keys):
    """One check: the datasheet figures a section uses are in the datasheets' text."""
    missing, bad = [], []
    for k in keys:
        v, f, pat, what = FIGS[k]
        t = ds_text(f)
        if t is None:
            missing.append(f)
        elif not re.search(pat, t):
            bad.append('%s: not found in %s' % (what, f))
    name = 'the %d datasheet figures used here are in the datasheets\' text: %s' % (
        len(keys), '; '.join(FIGS[k][3] for k in keys))
    if bad:
        check(S, name, False, '; '.join(bad))
    elif missing:
        check(S, name, 'SKIP', 'not at hand (RIDGE3_DATASHEETS): %s' % ', '.join(sorted(set(missing))))
    else:
        check(S, name, True)


def ds_check(S, what, got, want, same=None):
    """One check: a table copied into this file (`want`) against the same
    table read out of the datasheet (`got`; None when it is not at hand)."""
    if got is None:
        check(S, '%s: as copied here' % what, 'SKIP', 'datasheet not at hand (RIDGE3_DATASHEETS)')
        return
    same = same or (lambda w, g: w == g)
    bad = ['%s: here %s, datasheet %s' % (k, w, got.get(k)) for k, w in want.items() if not same(w, got.get(k))]
    check(S, '%s: as copied here, %d entries' % (what, len(want)), not bad, '; '.join(bad[:8]))


# Artery AT32F421 datasheet v2.02 (2023.10.17), table 5, QFN28 column: pin ->
# (pin name, the alternate and additional functions AM32 asks of it).  KiCad
# 10 has no AT32 symbol.  29 is the exposed pad (VSS/VSSA).
AT32F421_QFN28 = {
    '1': ('BOOT0', set()), '2': ('PF0', set()), '3': ('PF1', set()), '4': ('NRST', set()), '5': ('VDDA', set()),
    '6': ('PA0', {'ADC1_IN0', 'CMP1_INP2', 'CMP1_INM6'}), '7': ('PA1', {'ADC1_IN1', 'CMP1_INP1'}),
    '8': ('PA2', {'ADC1_IN2', 'CMP1_INM7'}), '9': ('PA3', {'ADC1_IN3'}), '10': ('PA4', {'ADC1_IN4', 'CMP1_INM4'}),
    '11': ('PA5', {'ADC1_IN5', 'CMP1_INP0', 'CMP1_INM5'}), '12': ('PA6', {'ADC1_IN6', 'TMR3_CH1'}),
    '13': ('PA7', {'ADC1_IN7', 'TMR1_CH1C'}), '14': ('PB0', {'ADC1_IN8', 'TMR1_CH2C'}),
    '15': ('PB1', {'ADC1_IN9', 'TMR1_CH3C'}), '16': ('VSS', set()), '17': ('VDD', set()),
    '18': ('PA8', {'TMR1_CH1'}), '19': ('PA9', {'TMR1_CH2'}), '20': ('PA10', {'TMR1_CH3'}),
    '21': ('PA13', {'SWDIO'}), '22': ('PA14', {'SWCLK'}), '23': ('PA15', set()), '24': ('PB3', set()),
    '25': ('PB4', {'TMR3_CH1'}), '26': ('PB5', set()), '27': ('PB6', set()), '28': ('PB7', set()),
    '29': ('EPAD', set()),
}
AT32_PIN = {v[0]: k for k, v in AT32F421_QFN28.items()}

# TI SLVSDJ3D table 6-1, DRV8320H (RTV, WQFN-32); 33 is the thermal pad
# ("must be connected to ground"), numbered by the footprint
DRV8320H_RTV = {'1': 'CPH', '2': 'VCP', '3': 'VM', '4': 'VDRAIN', '5': 'GHA', '6': 'SHA', '7': 'GLA', '8': 'SLA',
                '9': 'SLB', '10': 'GLB', '11': 'SHB', '12': 'GHB', '13': 'GHC', '14': 'SHC', '15': 'GLC', '16': 'SLC',
                '17': 'nFAULT', '18': 'MODE', '19': 'IDRIVE', '20': 'VDS', '21': 'NC', '22': 'ENABLE', '23': 'AGND',
                '24': 'DVDD', '25': 'INHA', '26': 'INLA', '27': 'INHB', '28': 'INLB', '29': 'INHC', '30': 'INLC',
                '31': 'PGND', '32': 'CPL'}
DRV8320H_PAD = '33'
# TI SNVSC40E table 6-1, LMR38020 DDA (SO-8 PowerPAD); 9 is the PowerPAD
LMR38020_DDA = {'1': 'GND', '2': 'EN', '3': 'VIN', '4': 'RT/SYNC', '5': 'FB', '6': 'PG', '7': 'BOOT', '8': 'SW'}
# TI SLUSEC8C table 5-1, TPS628501 DRL (SOT-583)
TPS628501_DRL = {'1': 'VIN', '2': 'EN', '3': 'MODE/SYNC', '4': 'COMP/FSET', '5': 'FB', '6': 'PG', '7': 'SW', '8': 'GND'}
# TI SBOS904A pin functions, TMP390 DRL (SOT-563); table 7-1 rows used:
# SETA resistor (kOhm) -> channel A (hot) trip temperature (C)
TMP390_DRL = {'1': 'SETA', '2': 'SETB', '3': 'GND', '4': 'OUTB', '5': 'VDD', '6': 'OUTA'}
TMP390_SETA = {'105': 94, '121': 96, '140': 98}
# TI SBOS318B table 5-1, INA186 DCK (SC-70-6)
INA186_DCK = {'1': 'REF', '2': 'GND', '3': 'VS', '4': 'IN+', '5': 'IN–', '6': 'OUT'}
# Diodes DS30203 rev 16-2, BSS138DW (SOT363) top view: S2 G2 D1 along the
# bottom, D2 G1 S1 along the top; numbered the SOT-363 way (1-3 along the
# bottom left to right, 4-6 back along the top)
BSS138DW_SOT363 = {'1': 'S2', '2': 'G2', '3': 'D1', '4': 'S1', '5': 'G1', '6': 'D2'}
# Infineon 002-00124 rev *L figure 3, S25FL128L WSON 5 x 6 (WND008), top view
S25FL128L_WSON = {'1': 'CS#', '2': 'SO/IO1', '3': 'WP#/IO2', '4': 'VSS', '5': 'SI/IO0', '6': 'SCK',
                  '7': 'IO3/RESET#', '8': 'VCC'}
# Infineon ISZ023N06LM6 rev 2.0: pins 1-3 source, 4 gate, 5-8 drain (9:
# the footprint's drain tab)
ISZ023N06LM6_PINS = {'1': 'S', '2': 'S', '3': 'S', '4': 'G', '5': 'D', '6': 'D', '7': 'D', '8': 'D', '9': 'D'}
# TDK DS-000440 (IIM-42652) and DS-000347 (ICM-42688-P), table 10 both:
# what the unused pins may carry.  Pin 9 is INT2/FSYNC/CLKIN, "Connect to
# GND if FSYNC not used"; Betaflight uses neither INT2 nor FSYNC.
TDK_IMU_UNUSED = {'2': 'No Connect or Connect to GND', '3': 'No Connect or Connect to GND', '7': 'Connect to GND',
                  '9': 'Connect to GND if FSYNC not used', '10': 'No Connect or Connect to GND',
                  '11': 'No Connect or Connect to GND'}
TDK_RULE = {'No Connect or Connect to GND': {None, 'GND'}, 'Connect to GND': {'GND'},
            'Connect to GND if FSYNC not used': {'GND'}}
# TDK DS-000440 section 5.3: gyro anti-alias filter, 3 dB bandwidth (Hz) ->
# (GYRO_AAF_DELT, GYRO_AAF_DELTSQR, GYRO_AAF_BITSHIFT), the rows Betaflight uses
IIM42652_AAF = {258: (6, 36, 10), 536: (12, 144, 8), 997: (21, 440, 6), 1962: (37, 1376, 4)}
# Murata NTC catalogue (R44E), "Temperature Characteristics (Center Value)",
# column NCpppXH103 (the NCU15XH103F60RC): temperature (C) -> kOhm
NCU_XH103_RT = {-40: 195.652, -35: 148.171, -30: 113.347, -25: 87.559, -20: 68.237, -15: 53.650, -10: 42.506,
                -5: 33.892, 0: 27.219, 5: 22.021, 10: 17.926, 15: 14.674, 20: 12.081, 25: 10.000, 30: 8.315,
                35: 6.948, 40: 5.834, 45: 4.917, 50: 4.161, 55: 3.535, 60: 3.014, 65: 2.586, 70: 2.228, 75: 1.925,
                80: 1.669, 85: 1.452, 90: 1.268, 95: 1.110, 100: 0.974, 105: 0.858, 110: 0.758, 115: 0.672,
                120: 0.596, 125: 0.531}


def at32f421_from_ds():
    """AT32F421 table 5, QFN28 column, read out of the PDF: pin -> (name, functions)."""
    raw = ds_raw('artery_AT32F421.pdf')
    if raw is None:
        return None
    pinname = re.compile(r'^(P[A-F]\d{1,2}|VDDA|VSSA|VDD|VSS|NRST|BOOT0|EPAD)\b')
    func = re.compile(r'\b(TMR\d+_(?:CH\d+C?|BRK|EXT)|ADC1_IN\d+|CMP1_IN[MP]\d+|CMP1_OUT|SWDIO|SWCLK)\b')
    num = re.compile(r'^(?:\d+|-)(?:\(\d\))?$')
    k0 = raw.index('Table 5. AT32F421 series pin definitions')
    i = raw.index('Table 5. AT32F421 series pin definitions', k0 + 10)
    j = raw.index('(1) I = input', i)
    rows_, pend = [], []
    for ln in raw[i:j].split('\n'):
        w = ln.split()
        lead = 0
        while lead < len(w) and num.match(w[lead]):
            lead += 1
        if pend or (len(w) == 1 and re.match(r'^(?:\d+|-)\(\d\)$', w[0])):
            pend += w[:lead]                        # a row whose pin numbers break over lines
            if len(pend) < 5:
                continue
            nums, rest, pend = pend[:5], ' '.join(w[lead:]), []
        elif lead >= 5:
            nums, rest = w[:5], ' '.join(w[5:])
        else:
            if rows_:
                m = pinname.match(ln.strip())
                if rows_[-1][1] is None and m:
                    rows_[-1][1] = m.group(1)
                rows_[-1][2] |= set(func.findall(ln))
            continue
        m = pinname.match(rest)
        rows_.append([nums, m.group(1) if m else None, set(func.findall(rest))])
    return {nums[1].split('(')[0]: (name, funcs) for nums, name, funcs in rows_ if nums[1].split('(')[0] != '-'}


def drv8320h_from_ds():
    t = ds_text('ti_drv8320.txt')
    if t is None:
        return None
    i = t.index('Table 6-1. Pin Functions—32-Pin DRV8320 Devices\n')
    j = t.index('PWR = power', i)
    return {h: name for name, h in re.findall(r'^\s*(\w+)\s+(\d+|—)\s+(?:\d+|—)\s+(?:PWR|I/O|OD|NC|I|O)\b', t[i:j], re.M)
            if h != '—'}


def seq_table(fname, start, names, pin_first=False):
    """A pin table that pdftotext wrote one cell per line: pin -> name."""
    t = ds_text(fname)
    if t is None:
        return None
    i = t.index(start)
    if t.count(start) > 1:
        i = t.index(start, i + 1)                    # the first is the table of contents
    seg, alt = t[i:i + 6000], '|'.join(re.escape(n) for n in names)
    pat = r'\n(\d+)\s*\n(%s)\s*\n' if pin_first else r'\n(%s)\s*\n(\d+)\s*\n'
    out = {}
    for a, b in re.findall(pat % alt, seg):
        p, n = (a, b) if pin_first else (b, a)
        out.setdefault(p, n)
    return out


def ina186_from_ds():
    t = ds_text('ti_ina186.txt')
    if t is None:
        return None
    seg = t[t.index('Table 5-1. Pin Functions'):][:5000]
    return {p: n for n, p in re.findall(r'^\s*(REF|GND|IN–|IN\+|OUT|VS)\s+(\d)\s', seg, re.M)}


def bss138dw_from_ds():
    t = ds_text('diodes_BSS138DW.txt')
    if t is None:
        return None
    top, bot = re.search(r'\b(D2)\s+(G1)\s+(S1)\b', t), re.search(r'\b(S2)\s+(G2)\s+(D1)\b', t)
    if not top or not bot or bot.start() < top.start():
        return {}
    return {'1': bot.group(1), '2': bot.group(2), '3': bot.group(3), '4': top.group(3), '5': top.group(2), '6': top.group(1)}


def s25fl128l_from_ds():
    t = ds_text('ifx_S25FL128L.txt')
    if t is None:
        return None
    j = t.index('Figure 3      8-Connector package (WSON')
    i = t.rindex('Figure 2', 0, j)
    out = {}
    for a, p1, p2, b in re.findall(r'^\s*(\S.*?)\s+(\d)\s+(\d)\s+(\S.*?)\s*$', t[i:j], re.M):
        out[p1], out[p2] = re.sub(r'\s+', '', a), re.sub(r'\s+', '', b)
    return out


def tdk_imu_from_ds(fname):
    t = ds_text(fname)
    if t is None:
        return None
    i = t.index('PIN NUMBER') if 'PIN NUMBER' in t else t.index('Pin Number')
    seg, out = t[i:i + 6000], {}
    for p, d in re.findall(r'^\s*(\d{1,2})\s+RESV\s+(No Connect or Connect to GND|Connect to GND)', seg, re.M):
        out[p] = d
    m = re.search(r'^\s*9\s+INT2 / FSYNC / CLKIN\s+FSYNC: Frame sync input; (Connect to GND if FSYNC not used)', seg, re.M)
    if m:
        out['9'] = m.group(1)
    return out


def tmp390_seta_from_ds():
    t = ds_text('ti_tmp390.txt')
    if t is None:
        return None
    i = t.index('Table 7-1. TMP390 Channel A Threshold Setting\n')
    j = t.index('Table 7-2. TMP390 Channel B', i)
    return {r: int(tt) for tt, r, a, b in re.findall(r'\n(\d+)\n([\d.]+)\n(\d+)\n(\d+)(?=\n)', t[i:j])}


def iim42652_aaf_from_ds():
    t = ds_text('tdk_IIM-42652.txt')
    if t is None:
        return None
    i = t.index('ANTI-ALIAS FILTER')
    seg = t[i:i + 8000]
    return {int(hz): (int(a), int(b), int(c)) for hz, a, b, c in
            re.findall(r'^\s*(\d{2,4})\s+(\d+)\s+(\d+)\s+(\d+)\s*$', seg, re.M)}


def ncu_xh103_from_ds():
    t = ds_text('murata_NCU15XH103F60RC.txt')
    if t is None:
        return None
    i = t.find('Part Number NCpppXH103D NCpppXH103 ')
    out = {}
    for ln in (t[i:].split('\n') if i >= 0 else []):
        m = re.match(r'^\s*([–-]?\d+)\s+([\d.]+)\s+([\d.]+)\s', ln)
        if m:
            out[int(m.group(1).replace('–', '-'))] = float(m.group(3))
        elif out:
            break
    return out


# ------------------------------------------------------------------ pin maps
def check_fc_pins():
    S = 'FC pin map'
    fc = circuit.build('fc')
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
    cfgs = bf_configs()
    cfg = cfgs['RIDGE3']
    d = lambda k: cdefine(cfg, k)
    have = sorted(os.listdir(os.path.join(FW, 'betaflight/configs')))
    check(S, 'one Betaflight build, configs/RIDGE3: the IIM-42652 and its second source run the same driver',
          have == list(BF_CONFIGS), 'configs: %s' % ', '.join(have))
    want = {'MOTOR1': 'M1_SIG', 'MOTOR2': 'M2_SIG', 'MOTOR3': 'M3_SIG', 'MOTOR4': 'M4_SIG',
            'LED0': 'LED0', 'LED_STRIP': 'LED_STRIP',
            'UART1_TX': 'UART1_TX', 'UART1_RX': 'UART1_RX', 'UART2_TX': 'UART2_TX', 'UART2_RX': 'UART2_RX',
            'UART4_TX': 'UART4_TX', 'UART4_RX': 'UART4_RX',
            'SPI1_SCK': 'SPI1_SCK', 'SPI1_SDI': 'SPI1_MISO', 'SPI1_SDO': 'SPI1_MOSI',
            'SPI2_SCK': 'SPI2_SCK', 'SPI2_SDI': 'SPI2_MISO', 'SPI2_SDO': 'SPI2_MOSI',
            'GYRO_1_CS': 'GYRO_CS', 'GYRO_1_EXTI': 'GYRO_INT', 'FLASH_CS': 'FLASH_CS',
            'MAX7456_SPI_CS': 'OSD_CS', 'PINIO1': 'VTX_OFF',
            'ADC_VBAT': 'ADC_VBAT', 'ADC_CURR': 'ADC_CURR'}
    seen = set()
    for fn, port in re.findall(r'#define\s+(\w+)_PIN\s+(P[A-G]\d+)', cfg):
        seen.add(fn)
        net = ports.get(port, 'no such port')
        check(S, 'Betaflight %s_PIN %s' % (fn, port), net == want.get(fn, '?'),
              'carries %s' % net if net else 'not connected (unused on this board)')
    check(S, 'every function this board needs is defined in config.h (and nothing else: no beeper, no camera control)',
          set(want) <= seen, ', '.join(sorted(set(want) - seen)))
    # the peripherals on the far end of those nets: the gyro's pins from
    # KiCad's IIM-42652 symbol, the flash's from Infineon's WSON drawing
    imu_sym = symbol_pins('Sensor_Motion', 'IIM-42652')
    sym_pin = lambda nm: [k for k, v in imu_sym.items() if nm in v.split('/')]
    fl = {v: k for k, v in S25FL128L_WSON.items()}
    far = [('GYRO_CS', 'U_IMU', sym_pin('AP_CS')), ('SPI1_SCK', 'U_IMU', sym_pin('AP_SCLK')),
           ('SPI1_MOSI', 'U_IMU', sym_pin('AP_SDI')), ('SPI1_MISO', 'U_IMU', sym_pin('AP_SDO')),
           ('GYRO_INT', 'U_IMU', sym_pin('INT1')),
           ('FLASH_CS', 'U_FLASH', [fl['CS#']]), ('SPI2_MISO', 'U_FLASH', [fl['SO/IO1']]),
           ('SPI2_MOSI', 'U_FLASH', [fl['SI/IO0']]), ('SPI2_SCK', 'U_FLASH', [fl['SCK']]),
           ('OSD_CS', 'U_OSD', ['8']), ('SPI2_MOSI', 'U_OSD', ['9']), ('SPI2_SCK', 'U_OSD', ['10']),
           ('SPI2_MISO', 'U_OSD', ['11'])]
    names = {'U_IMU': 'IIM-42652, KiCad symbol Sensor_Motion:IIM-42652',
             'U_FLASH': 'S25FL128L WSON (Infineon 002-00124 fig. 3: 1 CS#, 2 SO, 5 SI, 6 SCK)',
             'U_OSD': 'AT7456E, the MAX7456 pinout: 8 /CS, 9 SDIN, 10 SCLK, 11 SDOUT (MAX7456 pin description)'}
    for net, ref, pin in far:
        check(S, '%s reaches %s pin %s' % (net, ref, '/'.join(pin) or '?'),
              len(pin) == 1 and comp('fc', ref).pins.get(pin[0]) == net, names[ref])
    flash = roles(comp('fc', 'U_FLASH'), S25FL128L_WSON)
    check(S, 'flash supply and control pins (WSON): VCC on +3V3, VSS on GND, WP# and IO3/RESET# held at 3.3 V (no write '
             'protect, no reset)', flash['VCC'] == '+3V3' and flash['VSS'] == 'GND' and flash['WP#/IO2'] == '+3V3'
          and flash['IO3/RESET#'] == '+3V3', str(flash))
    ds_check(S, 'S25FL128L WSON 5 x 6 pin numbers (Infineon 002-00124 rev *L fig. 3)', s25fl128l_from_ds(), S25FL128L_WSON)
    pullup = lambda n: any(re.match(r'R\d', x.ref) and set(x.pins.values()) == {'+3V3', n} for x in fc)
    check(S, 'OSD and flash share SPI2 (MAX7456_SPI_INSTANCE %s, FLASH_SPI_INSTANCE %s) on separate chip selects '
             '(%s, %s), each pulled up to 3.3 V so neither drives MISO while the MCU boots'
          % (d('MAX7456_SPI_INSTANCE'), d('FLASH_SPI_INSTANCE'), d('MAX7456_SPI_CS_PIN'), d('FLASH_CS_PIN')),
          d('MAX7456_SPI_INSTANCE') == 'SPI2' and d('FLASH_SPI_INSTANCE') == 'SPI2'
          and d('MAX7456_SPI_CS_PIN') != d('FLASH_CS_PIN') and pullup('OSD_CS') and pullup('FLASH_CS'))
    check(S, 'USE_MAX7456 in the build (a CONFIG= build does not get it from common_pre.h)',
          all(cdefine(v, 'USE_MAX7456') is not None for v in cfgs.values()))
    # HD VTX: MSP DisplayPort on UART1, to the 6-pin connector
    hd = comp('fc', 'J_HD').pins
    tx, rx = ports.get(d('UART1_TX_PIN')), ports.get(d('UART1_RX_PIN'))
    check(S, 'HD VTX: MSP_DISPLAYPORT_UART %s; UART1 TX/RX (%s/%s) on HD connector pins 3/4 '
             '(Betaflight connector standard: 1 V+, 2 GND, 3 FC TX, 4 FC RX, 5 GND, 6 SBUS)'
          % (d('MSP_DISPLAYPORT_UART'), tx, rx),
          d('MSP_DISPLAYPORT_UART') == 'SERIAL_PORT_USART1' and hd.get('3') == tx and hd.get('4') == rx
          and hd.get('2') == 'GND' and hd.get('5') == 'GND')
    # VTX power switch: PINIO1 -> gate resistor -> N-FET (pins from KiCad's
    # AO3400A symbol) -> the 9 V regulator's EN (pin from the LMR38020 table)
    sw = ports.get(d('PINIO1_PIN'))
    ser = [x for x in fc if re.match(r'R\d', x.ref) and sw in x.pins.values() and len(set(x.pins.values())) == 2]
    gate = [n for n in ser[0].pins.values() if n != sw][0] if len(ser) == 1 else None
    ao = {v: k for k, v in symbol_pins('Transistor_FET', 'AO3400A').items()}
    fet = [x for x in fc if x.part == 'AO3400A' and gate and x.pins.get(ao['G']) == gate]
    drain = fet[0].pins.get(ao['D']) if fet else None
    lmr = {v: k for k, v in LMR38020_DDA.items()}
    reg = [x for x in fc if x.part == 'LMR38020F' and drain and drain in x.pins.values()]
    on = ['%s pin %s (%s)' % (x.ref, k, LMR38020_DDA.get(k, 'PowerPAD')) for x in reg for k, v in sorted(x.pins.items())
          if v == drain]
    pulldown = gate is not None and any(re.match(r'R\d', x.ref) and set(x.pins.values()) == {gate, 'GND'} for x in fc)
    rail = None
    if len(reg) == 1:
        lx = reg[0].pins.get(lmr['SW'])
        ind = [x for x in fc if x.ref.startswith('L') and lx in x.pins.values()]
        rail = [n for n in ind[0].pins.values() if n != lx][0] if ind else None
    check(S, 'VTX switch: PINIO1_PIN %s (%s) -> %s -> %s gate (AO3400A, KiCad symbol: %s G, %s S, %s D), source on GND, '
             'gate pulled down, drain on the 9 V regulator\'s EN (LMR38020 pin %s, SNVSC40E table 6-1): PB5 high = EN low '
             '= rail %s off; low, and floating through reset = on'
          % (d('PINIO1_PIN'), sw, ser[0].part if len(ser) == 1 else '?', fet[0].ref if fet else '?', ao['G'], ao['S'],
             ao['D'], lmr['EN'], rail),
          bool(fet) and fet[0].pins.get(ao['S']) == 'GND' and len(reg) == 1 and reg[0].pins.get(lmr['EN']) == drain
          and pulldown and rail is not None,
          'drain (%s) on %s' % (drain, ', '.join(on) or 'no regulator pin'))
    check(S, 'the switched rail %s feeds HD connector pin 1' % rail, rail is not None and hd.get('1') == rail)
    check(S, 'PINIO1_CONFIG %s (PINIO_CONFIG_MODE_OUT_PP, not inverted: low at boot and while its mode is off = '
             'VTX on), PINIO1_BOX %s (BOXUSER1: the USER1 switch turns the VTX off)'
          % (d('PINIO1_CONFIG'), d('PINIO1_BOX')), d('PINIO1_CONFIG') == '1' and d('PINIO1_BOX') == '40')
    # the gyro: its unused pins as both datasheets ask, its supply and SPI
    # pins as KiCad's IIM-42652 symbol names them
    imu = comp('fc', 'U_IMU')
    bad = ['pin %s on %s (table 10: %s)' % (p, imu.pins.get(p), r) for p, r in TDK_IMU_UNUSED.items()
           if imu.pins.get(p) not in TDK_RULE[r]]
    sup = {p: imu.pins.get(p) for p, nm in imu_sym.items() if nm in ('VDD', 'VDDIO', 'GND')}
    bad += ['%s (%s) on %s' % (imu_sym[p], p, n) for p, n in sup.items()
            if n != ('GND' if imu_sym[p] == 'GND' else '+3V3_GYRO')]
    check(S, 'IMU pads take an IIM-42652 or an ICM-42688-P (table 10 of both, DS-000440 / DS-000347): RESV pins 2, 3, '
             '10, 11 open or on GND, RESV pin 7 on GND, pin 9 (INT2/FSYNC, unused) on GND; VDD and VDDIO on +3V3_GYRO, GND '
             'on GND', not bad, '; '.join(bad) or 'BOM part: %s' % parts.PARTS[imu.part]['mpn'])
    ds_check(S, 'IIM-42652 unused-pin rules (DS-000440 table 10)', tdk_imu_from_ds('tdk_IIM-42652.txt'), TDK_IMU_UNUSED)
    ds_check(S, 'ICM-42688-P unused-pin rules (DS-000347 table 10)', tdk_imu_from_ds('tdk_ICM-42688-P.txt'),
             TDK_IMU_UNUSED)
    # Gyro alignment against the placed footprint.  Pad 1 is the chip's
    # pin-1 corner.  TDK DS-000440 fig. 15 (IIM-42652) and DS-000347 fig.
    # 16 (ICM-42688-P), read from the figures, not machine-checked: pin 1
    # is at the chip's (-X, +Y) corner.  Betaflight body frame: +X forward,
    # +Y left; the board's front is -y in KiCad.  So with pin 1 rear-left
    # and the pad 12-14 edge on the left, the gyro is CW0.
    path = board_file('fc', 'ridge3-fc')
    if os.path.exists(path):
        b = pcbnew.LoadBoard(path)
        fp = b.FindFootprintByReference('U_IMU')
        ctr = fp.GetPosition()
        pad = {p.GetNumber(): p.GetPosition() for p in fp.Pads()}
        rel = lambda n: (pcbnew.ToMM(pad[n].x - ctr.x), pcbnew.ToMM(pad[n].y - ctr.y))
        p1, p13 = rel('1'), rel('13')
        rear_left = p1[0] < 0 and p1[1] > 0
        left_edge = p13[0] < 0 and abs(p13[0]) > abs(p13[1])
        check(S, 'IMU footprint on top, pin 1 rear-left, pads 12-14 along the left edge (%s)'
              % (os.path.relpath(path, V1) if path.startswith(V1) else path),
              not fp.IsFlipped() and rear_left and left_edge,
              'pad 1 at (%.2f, %.2f), pad 13 at (%.2f, %.2f) mm from centre' % (p1 + p13))
    else:
        check(S, 'IMU footprint orientation', False, 'no board at %s' % path)
    align = re.search(r'#define\s+GYRO_1_ALIGN\s+(\w+)', cfg).group(1)
    drivers = sorted(set(re.findall(r'#define\s+USE_(?:ACC|GYRO|ACCGYRO)_(?:SPI_)?(\w+)', cfg)))
    check(S, 'RIDGE3: GYRO_1_ALIGN CW0_DEG; drivers: the IIM-42652 (USE_ACCGYRO_IIM42652) and the ICM-42688-P '
             '(USE_GYRO_SPI_ICM42688P, USE_ACC_SPI_ICM42688P) only',
          align == 'CW0_DEG' and drivers == ['ICM42688P', 'IIM42652'] and d('USE_ACCGYRO_IIM42652') == ''
          and d('USE_GYRO_SPI_ICM42688P') == '' and d('USE_ACC_SPI_ICM42688P') == '', '%s, drivers %s' % (align, drivers))
    check(S, 'the BOM gyro (%s) is one the build drives' % parts.PARTS[imu.part]['mpn'],
          imu.part == 'IIM42652' and 'IIM42652' in drivers)
    if BF:
        mpu_h = open(os.path.join(BF, 'src/main/drivers/accgyro/accgyro_mpu.h')).read()
        mpu_c = open(os.path.join(BF, 'src/main/drivers/accgyro/accgyro_mpu.c')).read()
        drv_c = bf_source('src/main/drivers/accgyro/accgyro_spi_icm426xx.c')[0] or ''
        who = {k: cdefine(mpu_h, k + '_WHO_AM_I_CONST') for k in ('IIM42652', 'ICM42688P')}
        val = lambda s: int(re.sub(r'[()\s]', '', s), 16) if s else None
        m = re.search(r'#if ([^\n]*)\n\s*icm426xxSpiDetect,', mpu_c)
        gate_defs = re.findall(r'defined\((\w+)\)', m.group(1)) if m else []
        check(S, 'Betaflight finds the gyro: WHO_AM_I IIM-42652 %s, ICM-42688-P %s (accgyro_mpu.h) = the datasheets\' '
                 '0x6F (DS-000440) and 0x47 (DS-000347); icm426xx.c maps both; its detector is built in by %s, which '
                 'config.h defines' % (who['IIM42652'], who['ICM42688P'], ' or '.join(gate_defs) or '?'),
              val(who['IIM42652']) == fig('iim_whoami') and val(who['ICM42688P']) == fig('icm42688_whoami')
              and 'case IIM42652_WHO_AM_I_CONST:' in drv_c and 'case ICM42688P_WHO_AM_I_CONST:' in drv_c
              and any(cdefine(cfg, g) is not None for g in gate_defs))
    else:
        check(S, 'Betaflight finds the gyro (WHO_AM_I)', 'SKIP', 'set BF_SRC to a Betaflight 2025.12.5 checkout')
    check(S, 'BOARD_NAME RIDGE3, MANUFACTURER_ID OFFG',
          [cdefine(cfgs[k], 'BOARD_NAME') for k in BF_CONFIGS] == list(BF_CONFIGS)
          and all(cdefine(v, 'MANUFACTURER_ID') == 'OFFG' for v in cfgs.values()))
    check(S, 'no board rotation (DEFAULT_ALIGN_BOARD_* unset)',
          not any(re.search(r'#define\s+DEFAULT_ALIGN_BOARD', v) for v in cfgs.values()))
    denom = d('DEFAULT_PID_PROCESS_DENOM')
    rate = None
    if BF:
        sync = open(os.path.join(BF, 'src/main/drivers/accgyro/gyro_sync.c')).read()
        body = sync[sync.index('uint16_t gyroSetSampleRate('):]
        rates = set()
        for chip in ('IIM_42652_SPI', 'ICM_42688P_SPI'):
            k = body.find('case %s:' % chip)
            k = k if k >= 0 else body.find('default:')
            mm = re.search(r'gyroSampleRateHz\s*=\s*(\d+);', body[k:])
            rates.add(int(mm.group(1)) if mm else None)
        rate = rates.pop() if len(rates) == 1 else None
    check(S, 'PID loop %s kHz: the IIM-42652 / ICM-42688-P gyro rate in Betaflight (gyro_sync.c) %s kHz / '
             'DEFAULT_PID_PROCESS_DENOM %s' % ('%g' % (rate / 1e3 / int(denom)) if rate and denom else '?',
                                               '%g' % (rate / 1e3) if rate else '?', denom),
          (denom == '2' and rate is not None) if BF else 'SKIP', '' if BF else 'set BF_SRC')
    check(S, 'HSE crystal on PF0/PF1 with SYSTEM_HSE_MHZ 8 (two-pad 8 MHz part, pads 1/2)',
          c.pins['5'] == 'HSE_IN' and c.pins['6'] == 'HSE_OUT' and d('SYSTEM_HSE_MHZ') == '8'
          and comp('fc', 'Y1').part == 'XTAL8M' and comp('fc', 'Y1').pins == {'1': 'HSE_IN', '2': 'HSE_OUT'})
    check(S, 'USB D+/D- on PA12/PA11', ports['PA12'] == 'USB_DP' and ports['PA11'] == 'USB_DM')
    check(S, 'SWD on PA13/PA14 to test pads', ports['PA13'] == 'SWDIO' and ports['PA14'] == 'SWCLK'
          and comp('fc', 'TP_SWDIO').pins['1'] == 'SWDIO')
    pd = [x for x in fc if re.match(r'R\d', x.ref) and set(x.pins.values()) == {'BOOT0', 'GND'}]
    sw_ = comp('fc', 'SW_BOOT').pins
    check(S, 'BOOT0 (pin 46, PB8-BOOT0) pulled down (%s), the DFU button between BOOT0 and 3.3 V (KMR223G: pads 1/4 and '
             '2/3 joined inside, 5 the frame, per the C&K drawing: not machine-checked)'
          % ', '.join(x.part for x in pd),
          pins['46'] == 'PB8' and ports['PB8'] == 'BOOT0' and len(pd) == 1
          and {sw_.get('1'), sw_.get('4')} == {'BOOT0'} and {sw_.get('2'), sw_.get('3')} == {'+3V3'}
          and sw_.get('5') == 'GND', str(sw_))
    check(S, 'NRST (pin 7, PG10-NRST) to the RST test pad, 100 nF to ground',
          pins['7'] == 'PG10' and ports['PG10'] == 'NRST' and comp('fc', 'TP_NRST').pins['1'] == 'NRST'
          and any(x.part == 'C100N' and set(x.pins.values()) == {'NRST', 'GND'} for x in fc))
    if BF:
        m25 = open(os.path.join(BF, 'src/main/drivers/flash/flash_m25p16.c')).read()
        jid = fig('s25_id')
        code = '0x%02X%02X%02X' % jid
        check(S, 'blackbox flash S25FL128L: JEDEC ID %02X %02X %02X (002-00124 table 51) is in Betaflight\'s m25p16 table, '
                 'which USE_FLASH_M25P16 builds in' % jid,
              re.search(r'\{\s*%s\s*,' % code, m25, re.I) is not None and d('USE_FLASH_M25P16') == '')
    else:
        check(S, 'blackbox flash JEDEC ID in Betaflight\'s m25p16 table', 'SKIP', 'set BF_SRC')
    figs_check(S, ['iim_whoami', 'icm42688_whoami', 's25_id'])


def at32_ports(ref):
    """pin name (PA0..., VDD...) -> net, for an AT32F421 on the ESC (pin numbers: AT32F421_QFN28)."""
    c = comp('esc', ref)
    return {AT32F421_QFN28[p][0]: c.pins.get(p) for p in AT32F421_QFN28}


def am32_phase_map(tgt):
    """What RIDGE3_F421 asks of the MCU's pins: port -> (net suffix,
    functions); the phases' (high, low, comparator) ports; the hardware
    groups; their defines; and the ports asked to do two things."""
    tb = c_block(tgt, AM32_TARGET)
    groups = re.findall(r'#define\s+(HARDWARE_GROUP_\w+)', tb)
    blocks = {g: c_block(tgt, g) for g in groups}
    gd = {}
    for g in groups:
        gd.update(dict(re.findall(r'#define\s+(\w+)\s+(\S+)', blocks[g])))
    mcu = c_block(tgt, 'MCU_AT421')
    digits = lambda s: re.search(r'(\d+)$', s).group(1)
    port = lambda pin_key, port_key: 'P%s%s' % (gd[port_key][-1], digits(gd[pin_key]))
    cmp_h = am32_source('Mcu/f421/Drivers/drivers/inc/at32f421_cmp.h')
    inv = {int(v, 16): p for p, v in re.findall(r'CMP_INVERTING_(PA\d+)\s*=\s*(0x[0-9A-Fa-f]+)', cmp_h)}
    ninv = {int(v, 16): p for p, v in re.findall(r'CMP_NON_INVERTING_(PA\d+)\s*=\s*(0x[0-9A-Fa-f]+)', cmp_h)}

    def field(name):
        m = re.search(r'\b%s\s*:\s*(\d+);\s*/\*\s*\[(\d+)(?::(\d+))?\]' % name, cmp_h)
        width, lsb = int(m.group(1)), int(m.group(3) or m.group(2))
        return lambda v: (v >> lsb) & ((1 << width) - 1)
    invsel, ninvsel = field('cmpinvsel'), field('cmpninvsel')
    adc_c = am32_source('Mcu/f421/Src/ADC.c')
    adc_port = {k: p for p, k in re.findall(
        r'gpio_mode_QUICK\(GPIO([A-F]),\s*GPIO_MODE_ANALOG,\s*GPIO_PULL_NONE,\s*(\w+_ADC_PIN)\)', adc_c)}
    want, phases, clash = {}, {}, []

    class Want(dict):
        def __setitem__(self, k, v):
            if k in self and self[k] != v:
                clash.append('%s: %s and %s' % (k, self[k][0], v[0]))
            dict.__setitem__(self, k, v)
    want = Want()
    tim = '%s_CH%s' % (gd['IC_TIMER_REGISTER'], digits(gd['IC_TIMER_CHANNEL']))
    want[port('INPUT_PIN', 'INPUT_PIN_PORT')] = ('SIG', {tim})
    plus = set()
    for ph in 'ABC':
        hi = port('PHASE_%s_GPIO_HIGH' % ph, 'PHASE_%s_GPIO_PORT_HIGH' % ph)
        lo = port('PHASE_%s_GPIO_LOW' % ph, 'PHASE_%s_GPIO_PORT_LOW' % ph)
        # a phase's high and low side: one TMR1 channel and its complement
        chans = [f for f in AT32F421_QFN28.get(AT32_PIN.get(hi), ('', set()))[1] if re.match(r'TMR1_CH\d$', f)]
        ch = chans[0] if chans else 'TMR1_CH?'
        want[hi] = ('H' + ph, {ch})
        want[lo] = ('L' + ph, {ch + 'C'})
        v = int(gd['PHASE_%s_COMP' % ph], 16)
        cp = inv.get(invsel(v), '?')
        want[cp] = ('CMP_' + ph, {'CMP1_INM%d' % invsel(v)})
        plus.add(ninvsel(v))
        phases[ph] = (hi, lo, cp)
    if len(plus) == 1:
        k = plus.pop()
        want[ninv.get(k, '?')] = ('NEUTRAL', {'CMP1_INP%d' % k})
    else:
        want['?'] = ('NEUTRAL', {'one non-inverting input for all three phases'})
    for what, net in (('CURRENT', 'ISENSE'), ('VOLTAGE', 'ESC_VSENSE'), ('NTC', 'NTC')):
        pin_def = cdefine(tb, what + '_ADC_PIN') or cdefine(mcu, what + '_ADC_PIN')
        ch_def = cdefine(tb, what + '_ADC_CHANNEL') or cdefine(mcu, what + '_ADC_CHANNEL')
        if what == 'NTC' and cdefine(tb, 'USE_NTC') is None:
            continue
        p = 'P%s%s' % (adc_port.get(what + '_ADC_PIN', '?'), digits(pin_def) if pin_def else '?')
        want[p] = (net, {'ADC1_IN%s' % (digits(ch_def) if ch_def else '?')})
    return dict(want), phases, groups, gd, clash


def check_esc_pins():
    S = 'ESC pin map'
    esc = circuit.build('esc')
    ds_check(S, 'AT32F421 QFN28 pin numbers and the functions AM32 uses (Artery datasheet v2.02 table 5; KiCad 10 has no '
                'AT32 symbol)', at32f421_from_ds(), AT32F421_QFN28,
             same=lambda w, g: g is not None and w[0] == g[0] and w[1] <= g[1])
    for n in (1, 2, 3, 4):
        m = 'M%d_' % n
        p = at32_ports('U_ESC%d' % n)
        check(S, 'ESC %d: VDD (pin %s) and VDDA (pin %s) on %s3V3, VSS (%s) and the exposed pad (%s) on GND, BOOT0 (%s) '
                 'on GND' % (n, AT32_PIN['VDD'], AT32_PIN['VDDA'], m, AT32_PIN['VSS'], AT32_PIN['EPAD'], AT32_PIN['BOOT0']),
              p['VDD'] == m + '3V3' and p['VDDA'] == m + '3V3' and p['VSS'] == 'GND' and p['EPAD'] == 'GND'
              and p['BOOT0'] == 'GND', ', '.join('%s %s' % (k, p[k]) for k in ('VDD', 'VDDA', 'VSS', 'EPAD', 'BOOT0')))
        check(S, 'ESC %d: NRST (pin %s) filtered 100 nF to ground; SWDIO (PA13, pin %s) to its own test pad TP_E%d_DIO, '
                 'SWCLK (PA14, pin %s) to TP_E%d_CLK' % (n, AT32_PIN['NRST'], AT32_PIN['PA13'], n, AT32_PIN['PA14'], n),
              p['NRST'] == m + 'NRST' and any(x.part == 'C100N' and set(x.pins.values()) == {m + 'NRST', 'GND'} for x in esc)
              and p['PA13'] == m + 'SWDIO' and p['PA14'] == m + 'SWCLK'
              and comp('esc', 'TP_E%d_DIO' % n).pins.get('1') == m + 'SWDIO'
              and comp('esc', 'TP_E%d_CLK' % n).pins.get('1') == m + 'SWCLK')
    # the stack lead: the FC's connector pins, soldered at the ESC.  Pin 4,
    # the usual pinout's telemetry, carries the FC's 3.3 V to the ESC
    lead = sorted(set(c.pins.get('1') for c in esc if c.part == 'PAD_LEAD'))
    jesc = comp('fc', 'J_ESC').pins
    at_esc = {'GND': 'FC_GND', '+3V3': 'ESC_3V3'}
    want_lead = sorted(set(at_esc.get(v, v) for v in jesc.values() if v))
    p3 = [k for k, v in jesc.items() if v == '+3V3']
    tlm = [c.ref for c in esc + circuit.build('fc') if 'TLM' in c.pins.values()]
    check(S, 'stack lead: the ESC\'s lead pads carry the FC connector\'s nets (its GND as FC_GND, its +3V3 on pin %s '
             'as ESC_3V3); no TLM line on either board: no serial telemetry' % '/'.join(p3),
          lead == want_lead and p3 == ['4'] and not tlm, 'pads %s; connector %s; TLM on %s' % (lead, want_lead, tlm))
    if not AM32:
        check(S, 'AM32 targets.h', 'SKIP', 'set AM32_SRC to an AM32 checkout (commit %s) to check against the firmware'
              % AM32_COMMIT)
        return
    head = git_head(AM32)
    check(S, 'AM32 checkout %s at commit %s (the patch and the images are for %s)' % (AM32, head[:7] or '?', AM32_COMMIT),
          head.startswith(AM32_COMMIT) if head else 'INFO', '' if head else 'not a git checkout')
    tgt, how = am32_targets()
    check(S, 'firmware/%s applies to Inc/targets.h' % AM32_PATCH, tgt is not None, how)
    ntc_h, how_ntc = patched(AM32, AM32_PATCH, 'Inc/ntc_tables.h')
    check(S, 'firmware/%s applies to Inc/ntc_tables.h (the thermistor\'s NTC_table)' % AM32_PATCH, ntc_h is not None,
          how_ntc)
    if tgt is None:
        return
    tb = c_block(tgt, AM32_TARGET)
    td = lambda k: cdefine(tb, k)
    want, phases, groups, gd, clash = am32_phase_map(tgt)
    main_c = am32_source('Src/main.c')
    m = re.search(r'_Static_assert\(sizeof\(FIRMWARE_NAME\)\s*<=\s*(\d+)', main_c)
    name_max = int(m.group(1)) - 1 if m else 12
    fname = (td('FIRMWARE_NAME') or '').strip('"')
    pin_groups = [g for g in groups if 'INPUT_PIN' in c_block(tgt, g)]
    check(S, '%s: groups %s (the pin group defines MCU_AT421), FILE_NAME "%s", FIRMWARE_NAME "%s" (%d of %d characters, '
             'main.c static assert)' % (AM32_TARGET, ' + '.join(g.replace('HARDWARE_GROUP_', '') for g in groups),
                                        (td('FILE_NAME') or '').strip('"'), fname, len(fname), name_max),
          len(pin_groups) == 1 and cdefine(c_block(tgt, pin_groups[0]), 'MCU_AT421') == ''
          and td('FILE_NAME') == '"%s"' % AM32_TARGET and 0 < len(fname) <= name_max)
    blocks = [tb] + [c_block(tgt, g) for g in groups]
    over = [k for k in ('CURRENT_ADC_PIN', 'CURRENT_ADC_CHANNEL', 'PA2_VOLTAGE',
                        'USE_ADC_INPUT', 'NO_CURRENT_SENSE', 'USE_SERIAL_TELEMETRY', 'USE_INVERTED_LOW',
                        'USE_INVERTED_HIGH', 'PWM_ENABLE_BRIDGE')
            if any(cdefine(b, k) is not None for b in blocks)]
    check(S, '%s and its groups leave the MCU_AT421 current-sense default alone (no current ADC pin override, '
             'PA2_VOLTAGE or USE_ADC_INPUT; the voltage and thermistor pins are the target\'s, checked against the '
             'board below), current sense on, no USE_SERIAL_TELEMETRY, and drive the gates non-inverted (no '
             'USE_INVERTED_LOW / _HIGH, no PWM_ENABLE_BRIDGE: in 6x PWM mode the DRV8320H takes INHx / INLx active high, '
             'SLVSDJ3D 8.3.1.1.1)' % AM32_TARGET, not over, ', '.join(over))
    cant = ['%s (pin %s) cannot be %s' % (p, AT32_PIN.get(p), '/'.join(sorted(f))) for p, (_, f) in want.items()
            if p not in AT32_PIN or not f <= AT32F421_QFN28[AT32_PIN[p]][1]]
    cant += ['%s asked to be both' % c_ for c_ in clash]
    check(S, 'every pin AM32 uses can do what AM32 uses it for (datasheet table 5): input %s; a TMR1 CHx/CHxC pair per '
             'phase; comparator inputs decoded from PHASE_x_COMP with the Artery driver\'s own register map '
             '(at32f421_cmp.h: CMPINVSEL [6:4] and CMPNINVSEL [8:7], CMP_INVERTING_PAx / CMP_NON_INVERTING_PAx); ADC '
             'channels' % next(iter([f for q, (k, f) in want.items() if k == 'SIG'][0])), not cant, '; '.join(cant))
    for n in (1, 2, 3, 4):
        p = at32_ports('U_ESC%d' % n)
        exp = lambda f: f if f == 'ESC_VSENSE' else 'M%d_%s' % (n, f)
        bad = ['%s wants %s, has %s' % (q, exp(f), p.get(q)) for q, (f, _) in want.items() if p.get(q) != exp(f)]
        check(S, 'ESC %d: input, six gate outputs, three comparator inputs, neutral, current, voltage and FET thermistor '
                 'match the groups and the MCU_AT421 defaults' % n, not bad,
              '; '.join(bad) or ', '.join('%s %s (pin %s)' % (q, f, AT32_PIN.get(q)) for q, (f, _) in sorted(want.items())))
    # each AM32 phase is one half-bridge, from the MCU through the driver
    # (TI's pin table) and the FETs (Infineon's) to the comparator input
    # AM32 reads for that phase
    drv = {v: k for k, v in DRV8320H_RTV.items()}
    fets = [x for x in esc if x.part == 'ISZ023N06LM6']
    fpin = lambda f, role: {f.pins.get(k) for k, v in ISZ023N06LM6_PINS.items() if v == role}
    for n in (1, 2, 3, 4):
        p = at32_ports('U_ESC%d' % n)
        dn = roles(comp('esc', 'U_GD%d' % n), DRV8320H_RTV)
        bad, path = [], []
        for ph, (hi, lo, cp) in sorted(phases.items()):
            L = [x for x in 'ABC' if dn['INH' + x] == p.get(hi) and dn['INL' + x] == p.get(lo)]
            if len(L) != 1:
                bad.append('%s: %s/%s on no one INHx/INLx pair' % (ph, hi, lo))
                continue
            L = L[0]
            node = dn['SH' + L]
            hs = [f for f in fets if fpin(f, 'G') == {dn['GH' + L]}]
            ls = [f for f in fets if fpin(f, 'G') == {dn['GL' + L]}]
            div = [x for x in esc if re.match(r'R\d', x.ref) and set(x.pins.values()) == {node, p.get(cp)}]
            pad = [x for x in esc if x.part == 'PAD_MOTOR' and node in x.pins.values()]
            if not (len(hs) == 1 and len(ls) == 1 and fpin(hs[0], 'D') == {'VBAT'} and fpin(hs[0], 'S') == {node}
                    and fpin(ls[0], 'D') == {node} and fpin(ls[0], 'S') == {dn['SL' + L]} and len(div) == 1 and pad):
                bad.append('%s: driver channel %s, node %s, FETs %s/%s, divider %s, pad %s' % (
                    ph, L, node, [f.ref for f in hs], [f.ref for f in ls], [x.ref for x in div], [x.ref for x in pad]))
                continue
            path.append('%s: %s/%s -> INH%s/INL%s -> %s/%s -> %s (%s) -> %s -> %s' % (
                ph, hi, lo, L, L, hs[0].ref, ls[0].ref, node, pad[0].ref, div[0].ref, cp))
        check(S, 'ESC %d: each AM32 phase is one half-bridge: its high/low outputs reach one INHx/INLx pair of the '
                 'DRV8320H (SLVSDJ3D table 6-1), whose GHx/GLx drive that half-bridge\'s gates (ISZ023N06LM6: 1-3 S, 4 G, '
                 '5-8 D), whose node (SHx, the motor pad) is divided down to the comparator input AM32 reads for that '
                 'phase' % n, not bad, '; '.join(bad) or ' | '.join(path))
    # dead time: TMR1 on APB2 at the CPU clock, no clock division
    mcu = c_block(tgt, 'MCU_AT421')
    per = am32_source('Mcu/f421/Src/peripherals.c')
    mhz = int(cdefine(mcu, 'CPU_FREQUENCY_MHZ'))
    dt = int(td('DEAD_TIME'))
    tmr1 = 'TMR1->brk_bit.dtc = DEAD_TIME' in per and 'crm_apb2_div_set(CRM_APB2_DIV_1)' in per and 'clkdiv' not in per
    check(S, 'DEAD_TIME %d = %.0f ns at %d MHz (TMR1 on APB2, undivided; DTC linear below 128), on top of the DRV8320H\'s '
             'own %.0f ns after it sees the other gate off (SLVSDJ3D 7.5): not checked on a scope'
          % (dt, dt * 1e3 / mhz, mhz, fig('drv_tdead') * 1e9), 'INFO' if tmr1 and dt < 128 else False)
    figs_check(S, ['drv_tdead', 'drv_mode_6x'])


# ------------------------------------------------------------------ firmware scales
INA180_GAIN = {'A1': 20, 'A2': 50, 'A3': 100, 'A4': 200}      # TI INA180 datasheet, device comparison


def shunt_mohm(part):
    """SHUNT_0M5 -> 0.5 (milliohm)."""
    m = re.match(r'SHUNT_(\d+)M(\d*)$', part)
    return float(m.group(1) + ('.' + m.group(2) if m.group(2) else '')) if m else None


def ntc_t(r_k):
    """Temperature (C) of the Murata XH103 thermistor at r_k kOhm: log-linear
    between the R-T table's 5 C points; None outside -40..125 C."""
    pts = sorted(NCU_XH103_RT.items())
    for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
        if r1 <= r_k <= r0:
            return t0 + (t1 - t0) * math.log(r0 / r_k) / math.log(r0 / r1)
    return None


def am32_ntc_reading(table, adc):
    """AM32's getNTCDegrees (Mcu/f421/Src/ADC.c) on a 12-bit reading."""
    p1, p2 = table[adc >> 6], table[(adc >> 6) + 1]
    num = (p1 - p2) * (adc & 0x3F)
    return p1 - int(num / 64)                    # C division truncates toward zero


def check_fw_scales():
    """The firmware's voltage, current, temperature and gyro scale factors
    against the circuit's parts and the datasheets."""
    S = 'Firmware scales'
    cfg = bf_configs()['RIDGE3']
    cli = open(os.path.join(FW, 'betaflight/cli-setup.txt')).read()
    esc, fc = circuit.build('esc'), circuit.build('fc')
    ina = {v: k for k, v in INA186_DCK.items()}
    ds_check(S, 'INA186 DCK pin numbers (SBOS318B table 5-1)', ina186_from_ds(), INA186_DCK)
    # ESC: one shunt and one INA186 per channel -> MILLIVOLT_PER_AMP
    gains = fig('ina186_gain')
    sens, bad = set(), []
    for n in (1, 2, 3, 4):
        sh, amp = comp('esc', 'R_SH%d' % n), comp('esc', 'U_CS%d' % n)
        g = re.match(r'INA186(A\d)$', amp.part)
        src, m = 'M%d_SRC' % n, 'M%d_' % n
        # low side, Kelvin: IN+ on the shunt's sense-node sense pad, IN- on
        # its ground sense pad (SBOS318B table 5-1: for low-side sensing
        # IN+ to the load side, IN- to the ground side); REF grounded, so
        # 0 A reads 0 V; supplied from the channel's 3.3 V
        want_amp = {ina['REF']: 'GND', ina['GND']: 'GND', ina['VS']: m + '3V3', ina['IN+']: m + 'SNSP',
                    ina['IN–']: m + 'SNSN', ina['OUT']: m + 'IOUT'}
        if not (g and shunt_mohm(sh.part) and sh.pins == {'1': src, '2': 'GND', '3': m + 'SNSP', '4': m + 'SNSN'}
                and amp.pins == want_amp):
            bad.append('ESC %d: %s %s %s' % (n, sh.part, amp.part, amp.pins))
            continue
        sens.add(shunt_mohm(sh.part) * gains[g.group(1)])
        filt = [x for x in esc if re.match(r'R\d', x.ref) and set(x.pins.values()) == {'M%d_IOUT' % n, 'M%d_ISENSE' % n}]
        if not filt:
            bad.append('ESC %d: no series resistor from IOUT to ISENSE' % n)
    mv_a = sens.pop() if len(sens) == 1 and not bad else None
    tgt = am32_targets()[0] if AM32 else None
    want = am32_phase_map(tgt)[0] if tgt else {}
    at = {f: q for q, (f, _) in want.items()}
    mpa = cdefine(c_block(tgt, AM32_TARGET), 'MILLIVOLT_PER_AMP') if tgt else None
    check(S, 'ESC current: %s mOhm shunt x INA186%s %s V/V (SBOS318B) = %s mV/A at %s (low side, Kelvin, REF grounded) = '
             'AM32 MILLIVOLT_PER_AMP %s' % (shunt_mohm(comp('esc', 'R_SH1').part), comp('esc', 'U_CS1').part[6:],
                                           gains.get(comp('esc', 'U_CS1').part[6:]), mv_a, at.get('ISENSE', '?'), mpa),
          (mv_a is not None and mpa is not None and abs(mv_a - float(mpa)) < 1e-9) if tgt else 'SKIP',
          '; '.join(bad) or ('%.0f A full scale at 3.3 V' % (3300 / mv_a) if mv_a else ''))
    if tgt:
        tdv = cdefine(c_block(tgt, AM32_TARGET), 'TARGET_VOLTAGE_DIVIDER')
        r = esc_vsense_ratio()
        check(S, 'ESC battery divider ratio %.2f = AM32 TARGET_VOLTAGE_DIVIDER %s / 10; 6S full 25.2 V -> %.2f V at %s'
              % (r, tdv, 25.2 / r, at.get('ESC_VSENSE', '?')), tdv is not None and round(r * 10) == int(tdv) and 25.2 / r < 3.3)
    # ESC: the FET thermistor's table against the thermistor's datasheet
    ds_check(S, 'Murata XH103 R-T table, center values (NCU15XH103F60RC catalogue page)', ncu_xh103_from_ds(),
             NCU_XH103_RT, same=lambda w, g: g is not None and abs(w - g) < 1e-6)
    table = am32_ntc_table() if AM32 else None
    if table is None:
        check(S, 'ESC FET thermistor: AM32 NTC_table against the thermistor', 'SKIP' if not AM32 else False,
              'set AM32_SRC' if not AM32 else 'no NTC_table for %s after the patch' % AM32_TARGET)
    else:
        bad, rb = [], set()
        for n in (1, 2, 3, 4):
            m = 'M%d_' % n
            p = at32_ports('U_ESC%d' % n)
            rt = comp('esc', 'RT%d' % n)
            bias = two_pin(esc, p['VDDA'], m + 'NTC', 'R')
            if not (parts.PARTS[rt.part]['mpn'].startswith('NCU15XH103') and set(rt.pins.values()) == {m + 'NTC', 'GND'}
                    and len(bias) == 1 and p.get(at.get('NTC')) == m + 'NTC'):
                bad.append('ESC %d: %s %s, bias %s, MCU %s on %s' % (n, rt.part, rt.pins, [x.part for x in bias],
                                                                   at.get('NTC'), p.get(at.get('NTC'))))
                continue
            rb.add(value(bias[0].part))
        if bad or len(rb) != 1:
            check(S, 'ESC FET thermistor wiring: Murata XH103 from the NTC pin to ground under one bias resistor from VDDA',
                  False, '; '.join(bad) or str(rb))
        else:
            rb = rb.pop()
            # entry i is the temperature at ADC = 64 i (ADC.c: raw >> 6);
            # the reading is ratiometric to VDDA, the bias resistor's supply
            err, worst = [], (0.0, '')
            for i, t in enumerate(table):
                adc = 64 * i
                if adc <= 0 or adc >= 4096:
                    continue
                true = ntc_t(rb / 1e3 * adc / (4096 - adc))
                if true is None:
                    continue
                e = t - true
                err.append(e)
                if abs(e) > abs(worst[0]):
                    worst = (e, 'entry %d (ADC %d): %d C where the thermistor is at %.1f C' % (i, adc, t, true))
            use = []
            for t in (85, 100, 110, 125):
                r_ = NCU_XH103_RT[t]
                adc = int(4096 * r_ / (r_ + rb / 1e3))
                use.append('%d C reads %d' % (t, am32_ntc_reading(table, adc)))
            check(S, 'ESC FET thermistor: AM32 NTC_table (%s, ntc_tables.h) against Murata\'s R-T table for the '
                     'NCU15XH103 (center values) with the circuit\'s %gk bias from VDDA: every entry from -40 to 125 C within '
                     '1 C (the table\'s own resolution)' % (AM32_TARGET, rb / 1e3),
                  bool(err) and max(abs(e) for e in err) <= 1.0,
                  'worst %s; in use: %s' % (worst[1], ', '.join(use)))
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
    # FC: the gyro's scale and anti-alias filter in Betaflight's driver
    # (with firmware/betaflight's patch) against the IIM-42652 datasheet
    ds_check(S, 'IIM-42652 anti-alias filter rows Betaflight uses (DS-000440 section 5.3)', iim42652_aaf_from_ds(),
             IIM42652_AAF, same=lambda w, g: g == w)
    if not BF:
        check(S, 'Betaflight IIM-42652 scales and anti-alias filter', 'SKIP', 'set BF_SRC to a Betaflight 2025.12.5 checkout')
    else:
        head = git_head(BF)
        check(S, 'Betaflight checkout %s at commit %s (2025.12.5, the build firmware/betaflight is for)'
              % (BF, head[:7] or '?'), head.startswith(BF_COMMIT) if head else 'INFO', '' if head else 'not a git checkout')
        src, how = bf_source('src/main/drivers/accgyro/accgyro_spi_icm426xx.c')
        check(S, 'firmware/%s applies to the Betaflight source' % BF_PATCH, src is not None, how)
        if src is not None:
            def arm(fn, case):
                body = src[re.search(re.escape(fn) + r'[^;{]*\)\s*\{', src).start():]       # the definition
                body = body[:body.index('\n}\n')]
                k = body.find('case %s:' % case)
                return body[k:] if k >= 0 else body[body.find('default:'):]
            sc = re.search(r'GYRO_SCALE_(\d+)DPS', arm('bool icm426xxSpiGyroDetect(', 'IIM_42652_SPI'))
            acc = re.search(r'acc_1G\s*=\s*([\d\s\*]+);', arm('void icm426xxAccInit(', 'IIM_42652_SPI'))
            lsb = None
            if acc:
                lsb = 1
                for f in acc.group(1).split('*'):
                    lsb *= int(f)
            check(S, 'IIM-42652 scale in Betaflight: gyro %s dps, accelerometer %s LSB/g = the datasheet at the full scale '
                     'the driver sets (GYRO_FS_SEL / ACCEL_FS_SEL 0): +/-%d dps, %d LSB/g (DS-000440 tables 1, 2)'
                  % (sc.group(1) if sc else '?', lsb, fig('iim_gyro_fs'), fig('iim_acc_lsb')),
                  sc is not None and int(sc.group(1)) == fig('iim_gyro_fs') and lsb == fig('iim_acc_lsb'))
            lut = re.search(r'(aafLUT\w+)\[', arm('static aafConfig_t getGyroAafConfig(', 'IIM_42652_SPI'))
            rows_ = {}
            if lut:
                m = re.search(r'static aafConfig_t %s\[\w+\]\s*=\s*\{(.*?)\};' % lut.group(1), src, re.S)
                rows_ = {int(hz): (int(a), int(b_), int(c_)) for hz, a, b_, c_ in re.findall(
                    r'\[AAF_CONFIG_(\d+)HZ\]\s*=\s*\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}', m.group(1) if m else '')}
            bad = ['%d Hz: %s, datasheet %s' % (hz, v, IIM42652_AAF.get(hz)) for hz, v in sorted(rows_.items())
                   if IIM42652_AAF.get(hz) != v]
            check(S, 'IIM-42652 anti-alias filter in Betaflight (%s) = the datasheet\'s (DELT, DELTSQR, BITSHIFT) for each '
                     'bandwidth it sets' % (lut.group(1) if lut else '?'), bool(rows_) and not bad,
                  '; '.join(bad) or ', '.join('%d Hz %s' % kv for kv in sorted(rows_.items())))
    figs_check(S, ['ina186_gain', 'ncu_b', 'iim_gyro_fs', 'iim_acc_lsb'])


# ------------------------------------------------------------------ circuit arithmetic
def esc_vsense_ratio():
    top = value(find('esc', 'ESC vsense top')[0].part)
    bot = value(find('esc', 'ESC vsense bottom')[0].part)
    return (top + bot) / bot


def check_power():
    S = 'Power and analog'
    VMAX = 25.2          # a full 6S pack
    fc, esc = circuit.build('fc'), circuit.build('esc')
    lmr = {v: k for k, v in LMR38020_DDA.items()}
    ds_check(S, 'LMR38020 DDA pin numbers (SNVSC40E table 6-1)',
             seq_table('ti_lmr38020.txt', 'Table 6-1. Pin Functions', list(LMR38020_DDA.values())), LMR38020_DDA)
    ds_check(S, 'TPS628501 DRL pin numbers (SLUSEC8C table 5-1)',
             seq_table('ti_tps628501.txt', 'Table 5-1. Pin Functions', list(TPS628501_DRL.values())), TPS628501_DRL)
    ds_check(S, 'TMP390 DRL pin numbers (SBOS904A pin functions)',
             seq_table('ti_tmp390.txt', 'Pin Functions\n', list(TMP390_DRL.values()), pin_first=True), TMP390_DRL)
    ds_check(S, 'TMP390 SETA resistors used (SBOS904A table 7-1)', tmp390_seta_from_ds(), TMP390_SETA)
    ds_check(S, 'BSS138DW SOT363 pins (Diodes DS30203 top view)', bss138dw_from_ds(), BSS138DW_SOT363)
    ds_check(S, 'DRV8320H RTV pin numbers (SLVSDJ3D table 6-1)', drv8320h_from_ds(), DRV8320H_RTV)
    # --- FC supplies
    vref = fig('lmr_vref')
    t, b = value(find('fc', '5V BEC feedback top')[0].part), value(find('fc', '5V BEC feedback bottom')[0].part)
    v = vref * (1 + t / b)
    check(S, 'FC 5 V BEC (LMR38020F, VREF 1.00 V): 1.0 x (1 + %gk/%gk) = %.2f V (USB-safe 5 V rail)'
          % (t / 1e3, b / 1e3, v), 4.9 <= v <= 5.25)
    t, b = value(find('fc', '9V BEC feedback top')[0].part), value(find('fc', '9V BEC feedback bottom')[0].part)
    v = vref * (1 + t / b)
    check(S, 'FC 9 V video BEC (LMR38020F, VREF 1.00 V): %.2f V (DJI O3/O4, Walksnail, HDZero, analog VTX: 7-26 V '
             'inputs, HDZero 7-13 V)' % v, 8.6 <= v <= 9.5)
    t, b = value(find('fc', '9V BEC UVLO top')[0].part), value(find('fc', '9V BEC UVLO bottom')[0].part)
    er, ef = fig('lmr_en_rise'), fig('lmr_en_fall')
    v = er[1] * (1 + t / b)
    check(S, '9 V BEC enable divider %gk/%gk: on above %.2f V (%.2f-%.2f V over EN rising %g-%g V), off below %.2f V typ; '
             'below that the rail stays off instead of browning out' % (t / 1e3, b / 1e3, v, er[0] * (1 + t / b),
                                                                     er[2] * (1 + t / b), er[0], er[2], ef[1] * (1 + t / b)),
          5.5 <= v <= 6.5)
    a, ex = fig('lmr_rt')
    for c in [x for x in fc if x.part == 'LMR38020F']:
        p = roles(c, LMR38020_DDA)
        vin = p['VIN']
        bulk = [x for x in two_pin(fc, vin, 'GND', 'C') if value(x.part) >= 9.9e-6]
        en_ok = p['EN'] == vin or (two_pin(fc, vin, p['EN'], 'R') and two_pin(fc, p['EN'], 'GND', 'R'))
        ind = [x for x in fc if x.ref.startswith('L') and p['SW'] in x.pins.values()]
        out = [n for n in ind[0].pins.values() if n != p['SW']][0] if len(ind) == 1 else None
        rt = two_pin(fc, p['RT/SYNC'], 'GND', 'R')
        ok = (p['GND'] == 'GND' and c.pins.get('9') == 'GND' and bool(bulk) and bool(en_ok)
              and bool(two_pin(fc, p['BOOT'], p['SW'], 'C')) and out is not None and bool(two_pin(fc, out, p['FB'], 'R'))
              and bool(two_pin(fc, p['FB'], 'GND', 'R')) and len(rt) == 1)
        fsw = (a / (value(rt[0].part) / 1e3)) ** (1 / ex) if len(rt) == 1 else 0
        check(S, '%s (%s) against the LMR38020 DDA pin table (1 GND, 2 EN, 3 VIN, 4 RT/SYNC, 5 FB, 6 PG, 7 BOOT, 8 SW, 9 '
                 'PowerPAD): VIN on the input rail with its 10 uF, EN on VIN or on a divider from it, BOOT-SW capacitor, SW to '
                 'the inductor, FB divider from the output, RT to ground (%.0f kHz, equation 2)' % (c.ref, c.note, fsw), ok,
              ', '.join('%s %s=%s' % (k, nm, c.pins.get(k)) for k, nm in by_number(LMR38020_DDA)))
    for c in [x for x in fc if x.part == 'TPS628501']:
        p = roles(c, TPS628501_DRL)
        vin = p['VIN']
        ind = [x for x in fc if x.ref.startswith('L') and p['SW'] in x.pins.values()]
        out = [n for n in ind[0].pins.values() if n != p['SW']][0] if len(ind) == 1 else None
        ok = (p['GND'] == 'GND' and bool(two_pin(fc, vin, 'GND', 'C')) and p['EN'] == vin and p['MODE/SYNC'] in (vin, 'GND')
              and (p['COMP/FSET'] in ('GND', vin) or bool(two_pin(fc, p['COMP/FSET'], 'GND', 'R'))) and out == '+3V3'
              and bool(two_pin(fc, out, p['FB'], 'R')) and bool(two_pin(fc, p['FB'], 'GND', 'R')))
        check(S, '%s (%s) against the TPS628501 DRL pin table (1 VIN, 2 EN, 3 MODE/SYNC, 4 COMP/FSET, 5 FB, 6 PG, 7 SW, 8 '
                 'GND): VIN on %s with its capacitor, EN high, MODE %s, COMP/FSET %s, SW to the inductor, FB divider from %s'
              % (c.ref, c.note, vin, 'high (forced PWM)' if p['MODE/SYNC'] == vin else p['MODE/SYNC'], p['COMP/FSET'], out),
              ok, ', '.join('%s %s=%s' % (k, nm, c.pins.get(k)) for k, nm in by_number(TPS628501_DRL)))
    t, b = value(find('fc', '3.3V buck feedback top')[0].part), value(find('fc', '3.3V buck feedback bottom')[0].part)
    v = fig('tps_vfb') * (1 + t / b)
    check(S, 'FC 3.3 V (TPS628501, VFB 0.6 V): 0.6 x (1 + %gk/%gk) = %.3f V (MCU, gyro, flash and OSD: 3.3 V within 3 %%)'
          % (t / 1e3, b / 1e3, v), 3.2 <= v <= 3.4)
    # the video supply's thermostat: TMP390 -> BSS138DW inverter -> the 9 V BEC's EN
    reg9 = find('fc', '9V VTX BEC')[0]
    for c in [x for x in fc if x.part.startswith('TMP390')]:
        p = roles(c, TMP390_DRL)
        seta = two_pin(fc, p['SETA'], 'GND', 'R')
        rk = '%g' % (value(seta[0].part) / 1e3) if len(seta) == 1 else '?'
        trip = TMP390_SETA.get(rk)
        hyst = fig('tmp390_h20') if p['SETB'] == 'GND' else None
        outa = p['OUTA']
        bss = [x for x in fc if x.part == 'BSS138DW' and outa in x.pins.values()]
        ok, cut, how = False, None, 'no BSS138DW on OUTA'
        if len(bss) == 1:
            q = roles(bss[0], BSS138DW_SOT363)
            i1 = '1' if q['G1'] == outa else ('2' if q['G2'] == outa else None)
            if i1:
                i2 = '2' if i1 == '1' else '1'
                cut = q['D' + i2]
                ok = (q['S' + i1] == 'GND' and q['D' + i1] == q['G' + i2] and bool(two_pin(fc, '+3V3', q['G' + i2], 'R'))
                      and q['S' + i2] == 'GND')
                on = ['%s (%s)' % (k, LMR38020_DDA.get(k, 'PowerPAD')) for k, n in sorted(reg9.pins.items()) if n == cut]
                how = 'the cut-off FET\'s drain (%s) is on %s pin %s' % (cut, reg9.ref, ', '.join(on) or 'none')
        check(S, 'video-supply thermostat: %s (TMP390) SETA %sk -> trips at %s C (SBOS904A table 7-1), SETB to ground -> %s C '
                 'hysteresis, back on at %s C; OUTA (open drain, low when hot) pulled up to its own 3.3 V supply drives the '
                 'BSS138DW inverter, whose second FET pulls the 9 V BEC\'s EN (LMR38020 pin %s) low when hot'
              % (c.ref, rk, trip, hyst, trip - hyst if trip and hyst else '?', lmr['EN']),
              ok and trip is not None and hyst is not None and p['VDD'] == '+3V3' and p['GND'] == 'GND'
              and bool(two_pin(fc, '+3V3', outa, 'R')) and cut is not None and reg9.pins.get(lmr['EN']) == cut, how)
    # --- ESC: each channel's DRV8320H (pin names from TI's table)
    drv = {v: k for k, v in DRV8320H_RTV.items()}
    bad = collections.defaultdict(list)
    idrv = fig('drv_idrive')
    levels = set()
    for n in (1, 2, 3, 4):
        m = 'M%d_' % n
        g = comp('esc', 'U_GD%d' % n)
        p = roles(g, DRV8320H_RTV)
        cap = lambda a, b_: [x for x in two_pin(esc, a, b_, 'C')]
        vcp, fly, dv = cap(p['VCP'], p['VM']), cap(p['CPH'], p['CPL']), cap(p['DVDD'], 'GND')
        if not (p['VM'] == 'VBAT' and p['VDRAIN'] == 'VBAT' and [x for x in cap('VBAT', 'GND') if value(x.part) <= 1e-6]):
            bad['VM and VDRAIN on VBAT with a local ceramic'].append(n)
        if not (len(vcp) == 1 and abs(value(vcp[0].part) - 1e-6) < 1e-9 and RATED.get(vcp[0].part, 0) >= 25):
            bad['VCP: 1 uF 25 V to VM'].append(n)
        if not (len(fly) == 1 and abs(value(fly[0].part) - 47e-9) < 1e-12 and RATED.get(fly[0].part, 0) * 0.6 >= VMAX):
            bad['CPH-CPL: 47 nF, VM-rated'].append(n)
        if not (p['DVDD'] == m + 'DVDD' and [x for x in dv if abs(value(x.part) - 1e-6) < 1e-9]):
            bad['DVDD (%sDVDD): 1 uF to ground' % m].append(n)
        if not (p['AGND'] == 'GND' and p['PGND'] == 'GND' and g.pins.get(DRV8320H_PAD) == 'GND'):
            bad['AGND, PGND and the thermal pad on GND'].append(n)
        if p['ENABLE'] != 'DRV_EN':
            bad['ENABLE on DRV_EN'].append(n)
        if p['MODE'] != fig('drv_mode_6x'):
            bad['MODE tied to AGND: 6x PWM'].append(n)
        if p['VDS'] is not None:
            bad['VDS open'].append(n)
        r_id = [x for x in esc if re.match(r'R\d', x.ref) and p['IDRIVE'] and p['IDRIVE'] in x.pins.values()]
        if p['IDRIVE'] is None:
            key = (None, None)
        elif len(r_id) == 1:
            other = [v_ for v_ in r_id[0].pins.values() if v_ != p['IDRIVE']][0]
            key = (value(r_id[0].part), 'DVDD' if other == m + 'DVDD' else other)
        else:
            key = ('?', '?')
        if key not in idrv:
            bad['IDRIVE at one of its seven levels'].append(n)
        levels.add(key)
    lv = levels.pop() if len(levels) == 1 else None
    check(S, 'DRV8320H, all four, against TI\'s pin table: VM and VDRAIN on VBAT, VCP 1 uF 25 V to VM, CPH-CPL 47 nF '
             'VM-rated, DVDD 1 uF, grounds, ENABLE on DRV_EN, MODE to ground (6x PWM), VDS open (Hi-Z: %.1f V trip, %.0f A '
             'through a %.1f mOhm FET), IDRIVE %s: %.0f mA source / %.0f mA sink'
          % (fig('drv_vds_hiz'), fig('drv_vds_hiz') / fig('fet_rds'), fig('fet_rds') * 1e3,
             'open' if lv == (None, None) else ('%gk to %s' % (lv[0] / 1e3, lv[1]) if lv and lv[0] not in (0, '?')
                                               else str(lv)),
             idrv.get(lv, (0, 0))[0] * 1e3, idrv.get(lv, (0, 0))[1] * 1e3),
          not bad and lv in idrv, '; '.join('%s: ESC %s' % (k, v_) for k, v_ in bad.items()))
    # the drivers' ENABLE: fed from the bus, clamped
    ren = [x for x in esc if re.match(r'R\d', x.ref) and set(x.pins.values()) == {'VBAT', 'DRV_EN'}]
    dz = [x for x in esc if x.part == 'EDZV4V7' and set(x.pins.values()) == {'DRV_EN', 'GND'}]
    nin = sum(1 for n in (1, 2, 3, 4) if roles(comp('esc', 'U_GD%d' % n), DRV8320H_RTV)['ENABLE'] == 'DRV_EN')
    if len(ren) == 1 and dz:
        r = value(ren[0].part)
        rpd_typ = fig('drv_rpd') / nin
        rpd_min = 5.0 / fig('drv_iih') / nin           # IIH at its 70 uA maximum, read as a resistance
        vt = 6.0 * rpd_typ / (r + rpd_typ)
        vw = 6.0 * rpd_min / (r + rpd_min)
        vz = 4.7                                        # EDZV 4.7 V (parts.py; ROHM datasheet not in the set)
        iz = (VMAX - vz) / r - nin * vz / fig('drv_rpd')
        check(S, 'driver ENABLE (DRV_EN, %d drivers): %gk from VBAT; at 6.0 V (2S empty) %.2f V typ, %.2f V with every input '
                 'at its 70 uA maximum (VIH 1.5 V); at 6S a 4.7 V Zener holds it under the inputs\' 5.5 V (%.2f mA in it, '
                 '%.0f mW in the %gk)' % (nin, r / 1e3, vt, vw, iz * 1e3, (VMAX - vz) ** 2 / r * 1e3, r / 1e3),
              vw >= fig('drv_vih') and vz <= fig('drv_vi') and nin == 4,
              'Zener voltage 4.7 V nominal from parts.py: its datasheet is not in the set (unverified)')
    else:
        check(S, 'driver ENABLE: one resistor from VBAT and a Zener to ground', False, '%s %s' % (ren, dz))
    # each channel's 3.3 V: the FC's 3.3 V buck (TPS628501, forced PWM),
    # down the stack lead's pin 4 (ESC_3V3), through the channel's bead
    tf = find('fc', '3.3V buck feedback top')[0]
    t, b = value(tf.part), value(find('fc', '3.3V buck feedback bottom')[0].part)
    acc, rtol = fig('tps_vfb_acc'), 0.01                # 0402WGF: F = 1 %
    v3 = (fig('tps_vfb') * (1 - acc) * (1 + t * (1 - rtol) / (b * (1 + rtol))),
          fig('tps_vfb') * (1 + acc) * (1 + t * (1 + rtol) / (b * (1 - rtol))))
    worst, bad3, chans = [], [], []
    for n in (1, 2, 3, 4):
        m = 'M%d_' % n
        net = m + '3V3'
        bead = [x for x in esc if set(x.pins.values()) == {'ESC_3V3', net}]
        if not (len(bead) == 1 and parts.PARTS[bead[0].part].get('kind') == 'FB'):
            bad3.append('ESC %d: no single bead from ESC_3V3 to %s' % (n, net))
        load, other = 0.0, []
        for x in [x for x in esc if net in x.pins.values()]:
            if x in bead or x.ref.startswith('C'):
                continue
            if x.part == 'AT32F421G':
                load += fig('at32_idd')
            elif x.part.startswith('INA186'):
                load += fig('ina186_iq')
            elif re.match(r'R\d', x.ref):
                load += v3[1] / value(x.part)            # the far end at 0 V
            else:
                other.append(x.ref)
        gates = 6 * fig('drv_iih')                       # INHx, INLx high (the 5 V figure)
        chans.append(load + gates)
        worst.append((load + gates, n, other))
        # the driver's DVDD regulator: its 1 uF and, at most, its IDRIVE resistor
        dv = [x for x in esc if m + 'DVDD' in x.pins.values() and x.ref != 'U_GD%d' % n]
        dv_load = sum(fig('drv_dvdd')[2] / value(x.part) for x in dv if re.match(r'R\d', x.ref))
        if [x.ref for x in dv if not (x.note in ('driver DVDD', 'driver IDRIVE'))] or dv_load > fig('drv_idvdd'):
            bad3.append('ESC %d: DVDD feeds %s' % (n, [x.ref for x in dv]))
    hub = sorted(x.ref for x in esc if 'ESC_3V3' in x.pins.values())
    want_hub = sorted(['P_L3V'] + ['FB%d' % n for n in (1, 2, 3, 4)] + [x.ref for x in find('esc', 'ESC 3.3V hub')])
    if hub != want_hub:
        bad3.append('ESC_3V3 carries %s' % hub)
    tot, n, other = max(worst)
    esc_i = sum(chans)
    check(S, 'ESC 3.3 V: each channel\'s MCU, amplifier, thermistor and gate inputs from ESC_3V3 (the FC\'s 3.3 V, lead '
             'pin 4) through its own bead; worst channel %.1f mA (ESC %d): AT32F421 %.1f mA (table 19), INA186 %.2f mA, '
             'resistors at %.2f V into 0 V, six gate inputs %.2f mA.  Each DRV8320H\'s DVDD feeds only its 1 uF (and '
             'IDRIVE resistor), no external load (SLVSDJ3D: 30 mA max)'
          % (tot * 1e3, n, fig('at32_idd') * 1e3, fig('ina186_iq') * 1e3, v3[1], 6 * fig('drv_iih') * 1e3),
          not bad3 and not other, '; '.join(bad3 + (['unknown loads: %s' % other] if other else [])))
    iout = fig('tps_iout')
    check(S, 'FC 3.3 V buck (TPS628501, %.0f A): the ESC\'s four channels take %.0f mA (datasheet maxima), %.0f %% of it, '
             'leaving %.0f mA for the FC\'s own 3.3 V parts' % (iout, esc_i * 1e3, 100 * esc_i / iout, (iout - esc_i) * 1e3),
          esc_i <= 0.25 * iout, 'pass mark: the ESC under a quarter of the buck')
    # the drop from the FC's buck to the farthest pin: the lead's wire and
    # its one connector contact, aged (ASSUMPTION: 0.1 Ohm), and the bead
    # (Murata: 0.90 Ohm max after its tests)
    bead_i, _, bead_r = fig('blm03')
    beads = [x.part for x in esc if x.note == 'channel 3.3 V feed']
    drop = esc_i * 0.1 + tot * bead_r
    vlo, vhi = v3[0] - drop, v3[1]
    vdd, vs = fig('at32_vdd'), fig('ina186_vs')
    check(S, 'ESC channel 3.3 V %.3f-%.3f V: the FC buck\'s 0.6 V +/-%.0f %% (PWM, SLUSEC8C 7.5) x (1 + %gk/%gk, 1 %%) less '
             '%.0f mV of lead and bead at full load; inside the AT32F421\'s VDD %.1f-%.1f V (table 11) and the INA186\'s VS '
             '%.1f-%.1f V' % (vlo, vhi, 100 * acc, t / 1e3, b / 1e3, drop * 1e3, vdd[0], vdd[1], vs[0], vs[1]),
          vdd[0] <= vlo and vhi <= vdd[1] and vs[0] <= vlo and vhi <= vs[1],
          'the lead\'s 0.1 Ohm assumed; the bead\'s %.2f Ohm from Murata' % bead_r)
    check(S, 'ESC channel beads (%s, Murata BLM03AX601SN1D): %.1f mA in the worst channel, %.0f %% of the %.0f mA rating'
          % (', '.join(sorted(set(beads))), tot * 1e3, 100 * tot / bead_i, bead_i * 1e3),
          len(beads) == 4 and set(parts.PARTS[x]['mpn'] for x in beads) == {'BLM03AX601SN1D'} and tot <= 0.5 * bead_i)
    # battery dividers
    r = esc_vsense_ratio()
    check(S, 'ESC battery sense: %.1f V / %.1f = %.2f V (< %.2f V, the lowest channel 3.3 V = VDDA, the ADC reference)'
          % (VMAX, r, VMAX / r, vlo), VMAX / r < vlo)
    t, b = value(find('fc', 'VBAT divider top')[0].part), value(find('fc', 'VBAT divider bottom')[0].part)
    k = (t + b) / b
    check(S, 'FC battery sense: %.1f V / %.0f = %.2f V at PB2 (< 3.3 V; vbat_scale 160)' % (VMAX, k, VMAX / k), VMAX / k < 3.0)
    # back-EMF and virtual neutral
    ph = find('esc', 'BEMF A')
    bt = value([c for c in ph if c.part == 'R20K'][0].part); bb = value([c for c in ph if c.part != 'R20K'][0].part)
    kr = bb / (bt + bb)
    lim = vlo + fig('at32_fta')
    check(S, 'BEMF divider %gk/%gk: %.1f V phase -> %.2f V at the comparator; a 35 V spike -> %.2f V (< %.2f V: an FTa pin '
             'in analog mode stays under VDD + 0.3 V, at the lowest channel 3.3 V)' % (bt / 1e3, bb / 1e3, VMAX, VMAX * kr, 35 * kr, lim),
          35 * kr < lim)
    # virtual neutral: equal legs from the three divided phases to a star
    # that only the MCU's comparator input loads; the star is then the mean
    # of the three CMP nodes, and CMP - NEUTRAL crosses zero where the
    # phase crosses the mean of the phases
    bad, rleg = [], set()
    for n in (1, 2, 3, 4):
        m = lambda s: 'M%d_%s' % (n, s)
        on = [(c, k_) for c in esc for k_, v_ in c.pins.items() if v_ == m('NEUTRAL')]
        legs = [c for c, k_ in on if c.note.startswith('neutral ')]
        others = [c.ref for c, k_ in on if not c.note.startswith('neutral ') and c.ref != 'U_ESC%d' % n]
        if others or sorted(set(c.pins.values()) - {m('NEUTRAL')} for c in legs) != \
                sorted({m('CMP_' + ph_)} for ph_ in 'ABC'):
            bad.append(n)
        rleg |= set(value(c.part) for c in legs)
    rl = min(rleg)
    rth = bt * bb / (bt + bb)
    check(S, 'virtual neutral: %gk from each of CMP_A/B/C to a star only the comparator loads, in all four ESCs: '
             'the star is their mean; the comparator sees %.2f of CMP minus that mean'
          % (rl / 1e3, rl / (rl + rth)), not bad and len(rleg) == 1, str(bad))
    # current sense
    sh = find('esc', 'ESC 1 shunt')[0]; amp = find('esc', 'ESC 1 current amplifier')[0]
    g = re.match(r'(INA18[06])(A\d)$', amp.part)
    gain = (fig('ina186_gain') if g.group(1) == 'INA186' else INA180_GAIN)[g.group(2)]
    mv_a = shunt_mohm(sh.part) * gain
    check(S, 'current sense: %.1f mOhm x %d V/V = %.0f mV/A; the 3.3 V ADC range is %.0f A per motor' %
          (shunt_mohm(sh.part), gain, mv_a, 3300 / mv_a), 3300 / mv_a >= 40)
    check(S, 'shunt dissipation at 20 A per motor: %.2f W in a 2 W 1206 (%.0f %%)' % (20 ** 2 * shunt_mohm(sh.part) * 1e-3,
          100 * 20 ** 2 * shunt_mohm(sh.part) * 1e-3 / 2), 20 ** 2 * shunt_mohm(sh.part) * 1e-3 <= 0.6 * 2)
    ina = {v_: k_ for k_, v_ in INA186_DCK.items()}
    check(S, 'current sense is Kelvin: the amplifier inputs (IN+ pin %s, IN- pin %s) are nets of their own, tied to '
             'the shunt only by its footprint\'s net-tie pads' % (ina['IN+'], ina['IN–']),
          sh.pins.get('3', '').endswith('SNSP') and amp.pins[ina['IN+']] == sh.pins['3']
          and sh.pins.get('4', '').endswith('SNSN') and amp.pins[ina['IN–']] == sh.pins['4'] and amp.pins[ina['GND']] == 'GND')
    # --- voltage derating: every part that sees the pack, against 25.2 V
    seen = set()
    for bd, comps_ in (('esc', esc), ('fc', fc)):
        for c in comps_:
            if c.part in seen or c.part not in RATED:
                continue
            if not any(n in ('VBAT', 'VBAT_VTX') or n.endswith(('_A', '_B', '_C')) for n in c.pins.values() if n):
                continue
            if c.part in ('C1U_25_X7R',):            # VCP to VM: the charge pump's voltage, below
                continue
            seen.add(c.part)
            rv = RATED[c.part]
            if c.part.startswith('SMF'):
                check(S, '%s TVS: stand-off %d V >= %.1f V (conducts only above a full pack)' % (c.part, rv, VMAX),
                      rv >= VMAX)
                continue
            ratio = VMAX / rv
            check(S, '%s: %.0f %% of its %g V rating at 6S (60 %% rule)' % (c.part, 100 * ratio, rv), ratio <= 0.6)
    vg = fig('drv_vgsh')
    check(S, 'charge-pump capacitor (VCP to VM) %g V rating: %.0f %% at the high-side drive\'s %.1f V maximum (SLVSDJ3D 7.5)'
          % (RATED['C1U_25_X7R'], 100 * vg[2] / RATED['C1U_25_X7R'], vg[2]), vg[2] / RATED['C1U_25_X7R'] <= 0.6)
    # --- inductors against their regulators' current limits (datasheets)
    ISAT = {'SPM6530T-150M-HZ': 'spm6530_150', 'TFM252012ALMAR47MTAA': 'tfm_r47'}
    # cores that saturate softly (TDK: SPM-HZ metal composite), for which TI
    # relaxes "ideally Isat >= the current limit" (SNVSC40E 9.2.2.4)
    SOFT = {'SPM6530T-150M-HZ': 'metal composite'}
    ihs, itps = fig('lmr_ihs'), fig('tps_ilim')
    for bd, note, reg, limit, vout, lnote in (
            ('fc', '5V BEC inductor', 'LMR38020F high-side limit', ihs, '5V BEC feedback', '5V BEC'),
            ('fc', '9V BEC inductor', 'LMR38020F high-side limit', ihs, '9V BEC feedback', '9V VTX BEC'),
            ('fc', '3.3V buck inductor', 'TPS628501 high-side limit', itps, None, None)):
        ind = find(bd, note)[0]
        mpn = parts.PARTS[ind.part]['mpn']
        isat = fig(ISAT[mpn]) if mpn in ISAT else parts.PARTS[ind.part].get('isat')
        name = '%s %s (%s)' % (bd.upper(), mpn, note)
        if isat is None:
            check(S, '%s: Isat vs the %s' % (name, reg), 'INFO', 'Isat of %s not in this file' % mpn)
            continue
        if lnote:
            # TI's floor: Isat no less than the peak inductor current at full
            # load; and that peak under the limit's minimum, so every part
            # delivers its 2 A
            t, b = value(find('fc', vout + ' top')[0].part), value(find('fc', vout + ' bottom')[0].part)
            vo = fig('lmr_vref') * (1 + t / b)
            reg_c = find('fc', lnote)[0]
            rt = two_pin(fc, roles(reg_c, LMR38020_DDA)['RT/SYNC'], 'GND', 'R')
            fsw = (fig('lmr_rt')[0] / (value(rt[0].part) / 1e3)) ** (1 / fig('lmr_rt')[1]) * 1e3
            lh = float(re.match(r'([\d.]+)', parts.PARTS[ind.part]['value']).group(1)) * 1e-6
            ripple = (VMAX - vo) * vo / (VMAX * lh * fsw)
            peak = 2 + ripple / 2
            check(S, '%s: full-load peak 2 A + %.2f A / 2 = %.2f A (6S, %.0f kHz) <= Isat %s A (TI SNVSC40E 9.2.2.4: '
                     'must)' % (name, ripple, peak, fsw / 1e3, isat), peak <= isat)
            check(S, '%s: full-load peak %.2f A < the %s\'s minimum %.2f A, so 2 A is reached on every part'
                     % (name, peak, reg, limit[0]), peak < limit[0])
        if isat >= limit[2]:
            check(S, '%s: Isat %s A >= the %s %.2f A max' % (name, isat, reg, limit[2]), True)
        elif mpn in SOFT:
            check(S, '%s: Isat %s A < the %s %.2f A max' % (name, isat, reg, limit[2]), 'INFO',
                  'TI: "ideally" at least the limit, relaxed for soft-saturating cores; this is %s: on an output '
                  'short the inductance sags (20 %% at Isat), it does not collapse, and hiccup mode follows'
                  % SOFT[mpn])
        else:
            check(S, '%s: Isat %s A >= the %s %.2f A max' % (name, isat, reg, limit[2]), False,
                  'a hard-saturating core must not saturate before the current limit acts')
    # --- gate drive (the DRV8320H's own supplies)
    vgs = fig('fet_vgs')
    check(S, 'gate drive (DRV8320H high side %.1f/%.0f/%.1f V at VM >= 13 V): %.0f %% typ (%.0f %% max) of the '
             'ISZ023N06LM6\'s +/-%d V gate rating' % (vg[0], vg[1], vg[2], 100 * vg[1] / vgs, 100 * vg[2] / vgs, vgs),
          vg[1] / vgs <= 0.6)
    v6 = fig('drv_vgsh6')
    check(S, 'gate drive at 6 V (2S empty): %g-%g V (typ %g V) against the FET\'s RDS(on) specified down to 4.5 V (%.1f mOhm max)'
          % (v6[1], v6[3], v6[2], fig('fet_rds45') * 1e3), 'INFO', 'below 4.5 V the datasheet gives no RDS(on) limit')
    if AM32:
        mm = re.search(r'eepromBuffer\.pwm_frequency < (\d+) && eepromBuffer\.pwm_frequency > (\d+)',
                       am32_source('Src/main.c'))
        fmax = (int(mm.group(1)) - 1) * 1e3 if mm else None
    else:
        fmax = None
    if fmax:
        icp = fig('fet_qg') * fmax
        check(S, 'charge pump: one high-side gate switching at AM32\'s highest PWM setting (%.0f kHz, main.c) x %.0f nC (Qg '
                 'max to 10 V) = %.1f mA, within the %.0f mA the DRV8320H\'s VCP is specified for at VM 6 V'
              % (fmax / 1e3, fig('fet_qg') * 1e9, icp * 1e3, v6[0] * 1e3), icp <= v6[0])
    else:
        check(S, 'charge pump against AM32\'s highest PWM frequency', 'SKIP', 'set AM32_SRC')
    for i in (5, 10, 15, 20):
        p_ = i * i * 2 * fig('fet_rds')
        check(S, 'conduction loss per motor at %d A: %.2f W (two FETs at %.1f mOhm max, 25 C)' % (i, p_, fig('fet_rds') * 1e3),
              'INFO', 'hot (about 1.5 x at 125 C): %.2f W' % (1.5 * p_))
    # --- FC details
    cl = value(find('fc', 'crystal load')[0].part)
    check(S, 'HSE load caps %d pF each: CL = %.1f pF with 3 pF stray (crystal CL %g pF)'
          % (cl * 1e12, cl * 1e12 / 2 + 3, fig('xtal_cl') * 1e12), abs(cl * 1e12 / 2 + 3 - fig('xtal_cl') * 1e12) <= 1.5)
    cc = [x for x in fc if x.note.startswith('CC') and x.note.endswith('Rd')]
    check(S, 'USB-C: 5.1k Rd on CC1 and CC2 (C-to-C cables supply 5 V)', len(cc) == 2 and all(x.part == 'R5K1' for x in cc))
    fc_caps = [x for x in fc if x.note.startswith('U_FC pin')]
    check(S, 'FC MCU: one 100 nF per VDD/VBAT/VDDA pin group (%d) plus 1 uF and 4.7 uF bulk' % len(fc_caps),
          len(fc_caps) == 5)
    for n in (1, 2, 3, 4):
        net = {'M%d_3V3' % n, 'GND'}
        vdd, vdda = find('esc', 'U_ESC%d VDD' % n), find('esc', 'U_ESC%d VDDA' % n)
        ok = (len(vdd) == 1 and len(vdda) == 1 and abs(value(vdd[0].part) - 100e-9) < 1e-12
              and abs(value(vdda[0].part) - 1e-6) < 1e-9 and parts.PARTS[vdda[0].part]['fp'] == parts.C0402
              and all(set(x.pins.values()) == net for x in vdd + vdda))
        check(S, 'ESC %d MCU: 100 nF at VDD; at VDDA 1 uF 0402, Artery\'s 100 nF + 1 uF (AT32F421 figure 8) in one '
                 'case (its impedance the 100 nF\'s or lower at every frequency)' % n, ok,
              '%s %s' % ([x.part for x in vdd], [x.part for x in vdda]))
    figs_check(S, ['lmr_vref', 'lmr_en_rise', 'lmr_en_fall', 'lmr_ihs', 'lmr_vin', 'lmr_rt', 'tps_vfb', 'tps_vfb_acc', 'tps_iout', 'tps_ilim', 'blm03',
                   'tmp390_h20', 'drv_vm', 'drv_vi', 'drv_idvdd', 'drv_dvdd', 'drv_vih', 'drv_iih', 'drv_rpd', 'drv_vgsh',
                   'drv_vgsh6', 'drv_idrive', 'drv_vds_hiz', 'at32_vdd', 'at32_idd', 'at32_fta', 'ina186_iq', 'ina186_vs',
                   'fet_vds', 'fet_vgs', 'fet_rds', 'fet_rds45', 'fet_qg', 'spm6530_150', 'tfm_r47', 'xtal_cl'])


# absolute maximum or rated voltage: datasheet figures above, or the part
# number's voltage code (Murata 1E = 25 V, 1H = 50 V, 2A = 100 V; Samsung
# CL05B104KB: B = 50 V; Taiyo Yuden UMK = 50 V; TDK CGA ...1H = 50 V)
RATED = {
    'ISZ023N06LM6': FIGS['fet_vds'][0], 'DRV8320H': FIGS['drv_vm'][0], 'LMR38020F': FIGS['lmr_vin'][0],
    'C10U50_SOFT': 50, 'C_BRIDGE': 50, 'C100N': 50, 'C10U50_1210': 50, 'C100N_100': 100, 'C1U_25_X7R': 25,
    'C47N_50': 50, 'SMF33A': 33,
}


# ------------------------------------------------------------------ boards
def check_board(board, name):
    S = 'Board %s' % board.upper()
    path = board_file(board, name)
    if not os.path.exists(path):
        check(S, 'installed board', False, path)
        return
    tmp = os.path.join(os.path.dirname(path), '.verify_drc.json')
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
                  round(a.GetRadius() / 1e6, 2)) for a in arcs if abs(a.GetRadius() / 1e6 - pcb.HOLE_D / 2) < 0.01)
    want = sorted((sx * pcb.HOLE, sy * pcb.HOLE, pcb.HOLE_D / 2) for sx in (-1, 1) for sy in (-1, 1))
    poly = pcbnew.SHAPE_POLY_SET()
    closed = b.GetBoardPolygonOutlines(poly, False) and poly.OutlineCount() == 1
    check(S, 'mounting: four %.1f mm holes on the 25.5 mm pattern, each open to its corner through a %.1f mm slot '
             '(M2 soft-mount grommets slide in); outline closed' % (pcb.HOLE_D, pcb.SLOT_W),
          got == [tuple(round(v, 2) for v in t) for t in want] and closed, str(got))
    # no sharp point anywhere on the outline: where the slots meet the edge
    # and the hole it is rounded, and at every joint the two pieces meeting
    # there share a tangent (read back from the board's own Edge.Cuts)
    joints = {}
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        ends = [d.GetStart(), d.GetEnd()]
        for q in ends:
            if d.GetShape() == pcbnew.SHAPE_T_ARC:
                c = d.GetCenter()
                t = (-(q.y - c.y), q.x - c.x)        # square to the radius
            else:
                t = (ends[1].x - ends[0].x, ends[1].y - ends[0].y)
            joints.setdefault((q.x, q.y), []).append(t)
    turns = []
    for ts in joints.values():
        if len(ts) != 2:
            turns.append(180.0)
            continue
        (ax, ay), (bx, by) = ts
        c = abs(ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by))
        turns.append(math.degrees(math.acos(min(1.0, c))))
    rounds = collections.Counter(round(a.GetRadius() / 1e6, 2) for a in arcs)
    want = collections.Counter()
    for r, n in ((pcb.HOLE_D / 2, 4), (pcb.SLOT_TIP[0], 8), (pcb.SLOT_TIP[1], 8), (pcb.SLOT_HOLE_R, 8)):
        want[round(r, 2)] += n
    check(S, 'outline: no sharp point; where each slot opens through the edge a round of r %.1f mm sweeping into '
             'r %.1f mm (8), where it meets the hole r %.1f mm (8); every one of its %d joints tangent (largest turn '
             '%.2f degrees)' % (pcb.SLOT_TIP[0], pcb.SLOT_TIP[1], pcb.SLOT_HOLE_R, len(joints), max(turns)),
          rounds == want and max(turns) < 1.0, str(dict(rounds)))
    # the grommets' places (H1-H4: no pads, the holes are the outline's)
    # on those centres
    hs = sorted((round(fp.GetPosition().x / 1e6 - pcb.CX, 2), round(fp.GetPosition().y / 1e6 - pcb.CY, 2))
                for fp in b.GetFootprints() if fp.GetReference() in ('H1', 'H2', 'H3', 'H4'))
    check(S, 'grommet places H1-H4 on the holes\' centres: %s' % hs,
          len(hs) == 4 and all(abs(abs(x) - pcb.HOLE) < 0.01 and abs(abs(y) - pcb.HOLE) < 0.01 for x, y in hs))
    if board == 'esc':
        # each driver's own capacitors (VM, charge pump, flying, DVDD) at the
        # driver pads on their nets: from each capacitor pad's centre to the
        # nearest copper of that driver pad (the exposed pad by its edge, not
        # its centre)
        from shapely.geometry import Point, Polygon
        pos, shape = {}, {}
        for fp_ in b.GetFootprints():
            cu = pcbnew.B_Cu if fp_.IsFlipped() else pcbnew.F_Cu
            for p_ in fp_.Pads():
                if p_.GetNumber():
                    key = (fp_.GetReference(), p_.GetNumber())
                    pos.setdefault(key, p_.GetPosition())
                    sps = p_.GetEffectivePolygon(cu)
                    shape.setdefault(key, []).extend(
                        Polygon([(sps.Outline(k).CPoint(i).x / 1e6, sps.Outline(k).CPoint(i).y / 1e6)
                                 for i in range(sps.Outline(k).PointCount())]) for k in range(sps.OutlineCount()))
        dist = lambda a, c: min(Point(pos[a].x / 1e6, pos[a].y / 1e6).distance(q) for q in shape[c])
        comps_ = circuit.build('esc')
        far, missing = [], []
        for c in comps_:
            if c.note not in ('driver VM', 'driver charge pump', 'driver flying cap', 'driver DVDD'):
                continue
            gd = 'U_GD' + c.block[-1]
            g = comp('esc', gd).pins
            ds_ = []
            for pad, net in c.pins.items():
                near = [dist((c.ref, pad), (gd, k)) for k, v in g.items() if v == net and (gd, k) in pos and (c.ref, pad) in pos]
                if near:
                    ds_.append(min(near))
                else:
                    missing.append('%s.%s' % (c.ref, pad))
            if ds_:
                far.append((max(ds_), c.ref))
        check(S, 'driver capacitors (VM, charge pump, flying, DVDD) at their drivers: %d, each pad\'s centre within %.2f mm '
                 'of the driver pad on its net' % (len(far), max(far)[0] if far else 0), len(far) == 16 and not missing
              and max(far)[0] <= 2.0, 'farthest %s' % ', '.join('%s %.2f mm' % (r, v) for v, r in sorted(far)[-3:])
              + ('; not placed: %s' % missing if missing else ''))
        # the thermistors at their FETs, and the MCUs' 1 uF (at VDDA)
        rt, bulk = [], []
        for n in (1, 2, 3, 4):
            fets = [x.ref for x in comps_ if x.part == 'ISZ023N06LM6' and x.block == 'esc%d' % n]
            rt_fp = b.FindFootprintByReference('RT%d' % n)
            fpads = [p_ for r_ in fets if b.FindFootprintByReference(r_) for p_ in b.FindFootprintByReference(r_).Pads()]
            if rt_fp and fpads:
                rt.append(min(math.hypot(a.GetPosition().x - q.GetPosition().x, a.GetPosition().y - q.GetPosition().y)
                              for a in rt_fp.Pads() for q in fpads) / 1e6)
            cap = [x.ref for x in comps_ if x.note == 'U_ESC%d VDDA' % n]
            mcu = b.FindFootprintByReference('U_ESC%d' % n)
            cp = b.FindFootprintByReference(cap[0]) if cap else None
            if mcu and cp:
                c0 = [p_ for p_ in cp.Pads() if p_.GetNetname() == 'M%d_3V3' % n]
                vdd = [p_ for p_ in mcu.Pads() if p_.GetNetname() == 'M%d_3V3' % n]
                if c0 and vdd:
                    bulk.append(min(math.hypot(p_.GetPosition().x - c0[0].GetPosition().x,
                                               p_.GetPosition().y - c0[0].GetPosition().y) for p_ in vdd) / 1e6)
        check(S, 'FET thermistors: nearest pad of each to a FET of its channel: %s mm'
              % ', '.join('%.1f' % v for v in rt), 'INFO', 'they read the power stage through the copper between')
        check(S, 'MCU 1 uF (VDDA): each one\'s supply pad to the nearer of its MCU\'s VDD/VDDA pins: %s mm'
              % ', '.join('%.1f' % v for v in bulk), 'INFO', 'on the top, the MCU on the bottom: through the board')
    ds = b.GetDesignSettings()
    check(S, '%d copper layers; min track %.2f mm, clearance %.2f mm, via %.2f/%.2f mm (JLCPCB multilayer: '
             '%.2f mm track and gap, %.2f mm via, %.2f mm hole)'
          % (b.GetCopperLayerCount(), ds.m_TrackMinWidth / 1e6, ds.m_MinClearance / 1e6, ds.m_ViasMinSize / 1e6,
             ds.m_MinThroughDrill / 1e6, pcb.FAB_MIN[1.0], pcb.FAB_MIN_VIA, pcb.FAB_MIN_DRILL),
          ds.m_TrackMinWidth >= pcb.MM(pcb.FAB_MIN[1.0]) and ds.m_MinClearance >= pcb.MM(pcb.FAB_MIN[1.0])
          and ds.m_ViasMinSize >= pcb.MM(pcb.FAB_MIN_VIA) and ds.m_MinThroughDrill >= pcb.MM(pcb.FAB_MIN_DRILL))
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
    prod = os.path.join(os.path.dirname(path), 'production')
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
            if fp.GetReference() not in rows_ or \
                    abs((float(rows_[fp.GetReference()]['Rotation']) - want + 180) % 360 - 180) > 0.01:
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
    path = board_file(board, name)
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
        if fp is None:
            bad.append('%s: not on the board' % ref)
            continue
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
    check(S, 'solder pads: %d pad faces on %d parts (battery, motor, wire, lead and test pads, jumpers), mask open '
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


def find_shape(polys, tpl):
    """Where the geometry `tpl` (board-centre mm) is printed among the silk
    outlines `polys` (board mm): aligned on its largest piece, a copy
    counts when the outlines there cover it with an overlap (intersection
    over union, within its box) of 0.95 or more.  Returns the offsets."""
    from shapely import affinity
    from shapely.ops import unary_union
    pieces = list(tpl.geoms) if hasattr(tpl, 'geoms') else [tpl]
    key = max(pieces, key=lambda g: g.area)
    found = []
    for p in polys:
        if abs(p.area - key.area) > 0.02 * key.area:
            continue
        t = affinity.translate(tpl, p.bounds[0] - key.bounds[0], p.bounds[1] - key.bounds[1])
        env = t.envelope.buffer(0.02)
        near = unary_union([q.intersection(env) for q in polys if q.intersects(env)])
        if t.union(near).area and t.intersection(near).area / t.union(near).area >= 0.95:
            found.append((round(t.bounds[0], 2), round(t.bounds[1], 2)))
    return sorted(set(found))


def check_silk(board, name):
    S = 'Silkscreen %s' % board.upper()
    import numpy as np
    import brand
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    path = board_file(board, name)
    b = pcbnew.LoadBoard(path)
    sides = {}
    for layer, lname in ((pcbnew.F_SilkS, 'top'), (pcbnew.B_SilkS, 'bottom')):
        polys = sides[lname] = []
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
        # the front arrow: one on each side, the same everywhere, with the
        # side's name by it
        mirror = lname == 'bottom'
        arrow = brand.front_arrow_mm(mirror)
        aw, ah = arrow.bounds[2] - arrow.bounds[0], arrow.bounds[3] - arrow.bounds[1]
        n = len(find_shape(polys, arrow))
        check(S, '%s: the front arrow, %.2f x %.2f mm (brand.FRONT_ARROW, the same on both sides of both boards): '
                 '%d found' % (lname, aw, ah, n), n == 1)
        word = 'Top' if lname == 'top' else 'Bottom'
        t = brand.styled('sans', word, brand.SIDE_CAP)[0]
        n = sum(len(find_shape(polys, brand.place(t, 0, 0, rot=r, mirror=mirror))) for r in (0, 90))
        check(S, '%s: the side\'s name, "%s", printed by the arrow: %d found' % (lname, word, n), n == 1)
        from shapely.geometry import Point
        flanges = unary_union([Point(pcb.CX + sx * pcb.HOLE, pcb.CY + sy * pcb.HOLE).buffer(pcb.GROMMET_SILK_R)
                               for sx in (-1, 1) for sy in (-1, 1)])
        under = [p for p in polys if p.intersects(flanges)]
        check(S, '%s: no ink under the grommet flanges (%.1f mm round each mounting hole)' % (lname, pcb.GROMMET_SILK_R),
              not under, '%d outlines, the first at %s' % (len(under), tuple(round(v - 100, 1) for v in
                                                                               under[0].centroid.coords[0]))
              if under else '')
    # the revision: printed on the board and in its title block (the
    # Gerbers' file attributes carry it), the same as the layout's
    L = __import__(board + '_layout')
    rev = b.GetTitleBlock().GetRevision()
    runs = [('mono', 'REV ' + L.REVISION)]
    where = [(sd, size) for sd, ps in sides.items() for size in (1.2, 1.1, 1.0) for r in (0, 90)
             if find_shape(ps, brand.place(brand.line(runs, size)[0], 0, 0, rot=r, mirror=sd == 'bottom'))]
    check(S, 'revision %s (%s_layout.REVISION): printed "REV %s" %s; title block revision %r'
          % (L.REVISION, board, L.REVISION, ', '.join('on the %s at %.1f mm' % w for w in where) or 'nowhere', rev),
          len(where) == 1 and rev == L.REVISION)
    if board == 'fc':
        got = [h for h in L.FLAG_H if find_shape(sides['bottom'], brand.us_flag_mm(h, mirror=True))]
        check(S, 'bottom: the flag of the United States over the product name, %s mm high (union at the upper '
                 'left as seen from below)' % (', '.join('%.1f' % h for h in got) or 'none'), len(got) == 1)


def check_brand():
    S = 'Brand'
    import brand
    from shapely import affinity
    m, w = brand.lockup()
    check(S, 'mark geometry from offgrid-mark-bone.svg: ring r 58, stroke 22, gap at the top, node r 17',
          abs(m.bounds[2] - m.bounds[0] - 138) < 0.1)
    # the "O" (its overshoot even above and below) against the ring's centre
    o = min((w.geoms if hasattr(w, 'geoms') else [w]), key=lambda p: p.bounds[0])
    off = (o.bounds[1] + o.bounds[3]) / 2 - (brand.MARK_AT[1] + brand.ring_centre()[1])
    check(S, 'lockup: "OffGrid" on one line with the mark, its capitals centred on the ring (%.1f units off, of '
             'the lockup\'s 200)' % abs(off), abs(off) < 1.5)
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
    listed = re.findall(r'^([0-9a-f]{64})  (\S+)$', readme, re.M)
    for h, f in listed:
        p = os.path.join(FW, f)
        ok = os.path.exists(p) and hashlib.sha256(open(p, 'rb').read()).hexdigest() == h
        check(S, '%s matches the sha256 in firmware/README.md' % f, ok)
    files = sorted(os.path.relpath(p, FW) for p in glob.glob(os.path.join(FW, '**', '*'), recursive=True)
                   if os.path.isfile(p) and re.search(r'\.(hex|patch)$', p))
    unlisted = [f for f in files if f not in {f_ for h, f_ in listed}]
    check(S, 'every image and patch in firmware/ has a sha256 line in firmware/README.md', not unlisted, ', '.join(unlisted))
    stale = sorted(os.path.relpath(p, FW) for p in glob.glob(os.path.join(FW, '**', '*'), recursive=True)
                   if re.search(r'G071|RIDGE3_BMI|55c9684|F051|CHEAPDRONE', os.path.relpath(p, FW), re.I))
    check(S, 'no files left from rev 1 (G071 images and patch, the RIDGE3_BMI config and image) or earlier (F051, '
             'CHEAPDRONE)', not stale, ', '.join(stale))
    # Betaflight: one image per config, carrying its board name
    for k, cfg in bf_configs().items():
        name = cdefine(cfg, 'BOARD_NAME')
        p = os.path.join(FW, 'betaflight/betaflight_2025.12.5_STM32G47X_%s.hex' % name)
        img = bytes(read_ihex(p).values()) if os.path.exists(p) else b''
        check(S, 'betaflight/%s carries BOARD_NAME %s' % (os.path.basename(p), name),
              re.search(rb'[^A-Z0-9_]' + name.encode() + rb'\x00', img) is not None)
    # AM32 firmware: the F421 link map (Mcu/f421/AT32F421x6_FLASH.ld) and the
    # MCU_AT421 block of targets.h place it; FILE_NAME just below the settings
    fw = glob.glob(os.path.join(FW, 'am32', 'AM32_%s_*.hex' % AM32_TARGET))
    bl = glob.glob(os.path.join(FW, 'am32', 'AM32_F421_BOOTLOADER_*.hex'))
    app = eeprom = None
    if len(fw) == 1:
        mem = read_ihex(fw[0])
        if AM32:
            ld = am32_source('Mcu/f421/AT32F421x6_FLASH.ld')
            org = lambda region: re.search(r'^\s*%s\s*\([rwx]+\)\s*:\s*ORIGIN = (0x[0-9A-Fa-f]+)' % region, ld, re.M)
            fn = re.search(r'^\s*FILE_NAME\s*\([rwx]+\)\s*:\s*ORIGIN = ORIGIN\(EEPROM\) - (\d+)', ld, re.M)
            app, eeprom = int(org('FLASH').group(1), 16), int(org('EEPROM').group(1), 16)
            fname_add = eeprom - int(fn.group(1))
            tgt = am32_targets()[0]
            mcu = c_block(tgt, 'MCU_AT421') if tgt else ''
            ee_src = re.search(r'#define EEPROM_START_ADD \(uint32_t\)(0x[0-9A-Fa-f]+)', mcu)
            same = (ee_src and int(ee_src.group(1), 16) == eeprom
                    and int(cdefine(mcu, 'APPLICATION_ADDRESS') or '0', 16) == app)
            table = am32_ntc_table()
            ntc = table is not None and struct.pack('<%di' % len(table), *table) in bytes(
                mem.get(a, 0) for a in range(min(mem), max(mem) + 1))
            how = 'link map and MCU_AT421 agree' if same else 'the link map and MCU_AT421 disagree'
        else:
            app, eeprom, fname_add, same, ntc = 0x08001000, 0x08007C00, 0x08007BE0, True, None
            how = 'AM32_SRC not set: the F421 layout taken as 0x08001000 / 0x08007C00'
        fname = bytes(mem.get(a, 0) for a in range(fname_add, fname_add + 32)).split(b'\x00')[0].decode('ascii', 'replace')
        code = [a for a in mem if a < fname_add]
        check(S, 'am32/%s: code 0x%08X-0x%08X (from the application address 0x%08X, below FILE_NAME), FILE_NAME "%s" at '
                 '0x%08X, nothing at or past the settings page 0x%08X (%s)'
              % (os.path.basename(fw[0]), min(code), max(code), app, fname, fname_add, eeprom, how),
              min(code) == app and max(mem) < eeprom and fname == AM32_TARGET and bool(same))
        check(S, 'am32/%s holds the patch\'s NTC_table for %s (built with the patch)' % (os.path.basename(fw[0]), AM32_TARGET),
              ntc if ntc is not None else 'SKIP', '' if ntc is not None else 'set AM32_SRC')
    else:
        check(S, 'one AM32 %s image in firmware/am32' % AM32_TARGET, False, str(fw))
    # AM32 bootloader: its device-info block (AM32-bootloader main.c devinfo,
    # placed by bootloader/ldscript_bl.ld) names the comms pin and the layout
    if len(bl) != 1:
        check(S, 'one AM32 F421 bootloader in firmware/am32', False, str(bl))
    elif not AM32_BL:
        check(S, 'am32/%s device info' % os.path.basename(bl[0]), 'SKIP',
              'set AM32_BL_SRC to an AM32-bootloader checkout (commit %s)' % AM32_BL_COMMIT)
    else:
        mem = read_ihex(bl[0])
        head = git_head(AM32_BL)
        check(S, 'AM32-bootloader checkout %s at commit %s (the image is built from %s)'
              % (AM32_BL, head[:7] or '?', AM32_BL_COMMIT), head.startswith(AM32_BL_COMMIT) if head else 'INFO')
        src = lambda rel: open(os.path.join(AM32_BL, rel)).read()
        main_c, ld = src('bootloader/main.c'), src('bootloader/ldscript_bl.ld')
        blutil, ver_h = src('Mcu/f421/Inc/blutil.h'), src('Inc/version.h')
        name = os.path.basename(bl[0])
        mn = re.search(r'BOOTLOADER_(P[A-F])(\d+)(?:_(\d+)K)?_V(\d+)\.hex$', name)
        mf = re.search(r'FLASH \(rx\)\s*:\s*ORIGIN = (0x[0-9A-Fa-f]+), LENGTH = (\d+)K-(\d+)', ld)
        devinfo = int(mf.group(1), 16) + int(mf.group(2)) * 1024 - int(mf.group(3))
        bl_end = int(mf.group(1), 16) + int(mf.group(2)) * 1024
        pin = re.search(r'USE_%s%s\)?\s*\n#define input_pin\s+GPIO_PIN\((\d+)\)\s*\n#define input_port\s+GPIO([A-F])\s*\n'
                        r'#define PIN_NUMBER\s+(\d+)\s*\n#define PORT_LETTER\s+(\d+)' % (mn.group(1), mn.group(2)), main_c)
        size = int(mn.group(3) or re.search(r'#define BOARD_FLASH_SIZE (\d+)', blutil).group(1))
        lay = re.search(r'#if BOARD_FLASH_SIZE == %d\s*\n#define EEPROM_START_ADD \(MCU_FLASH_START\+(0x[0-9a-fA-F]+)\)\s*\n'
                        r'#define FLASH_SIZE_CODE (0x[0-9a-fA-F]+)\s*\n#define ADDRESS_SHIFT (\d+)' % size, main_c)
        flash0 = int(re.search(r'#define MCU_FLASH_START (0x[0-9A-Fa-f]+)', main_c).group(1), 16)
        fw_rel = int(re.search(r'#else\s*\n#define FIRMWARE_RELATIVE_START (0x[0-9A-Fa-f]+)', main_c).group(1), 16)
        m1 = int(re.search(r'#define DEVINFO_MAGIC1 (0x[0-9a-fA-F]+)', main_c).group(1), 16)
        m2 = int(re.search(r'#define DEVINFO_MAGIC2 (0x[0-9a-fA-F]+)', main_c).group(1), 16)
        proto = int(re.search(r'#define BOOTLOADER_PROTOCOL_VERSION (\d+)', main_c).group(1))
        init = re.search(r"\.deviceInfo = \{'4','7','1',PIN_CODE,FLASH_SIZE_CODE,(0x[0-9a-fA-F]+),(0x[0-9a-fA-F]+),"
                         r"BOOTLOADER_PROTOCOL_VERSION,(0x[0-9a-fA-F]+)\}", main_c)
        body = main_c[main_c.index('static const struct __attribute__((packed))'):main_c.index('} devinfo')]
        sizes = sum((int(w) // 8) * int(n or 1) for w, n in re.findall(r'uint(8|16|32)_t\s+\w+(?:\[(\d+)\])?;',
                                                                       re.sub(r'/\*.*?\*/', '', body, flags=re.S)))
        pin_code = int(pin.group(4)) << 4 | int(pin.group(3))
        ee = flash0 + int(lay.group(1), 16)
        shift = int(lay.group(3))
        want = (struct.pack('<II', m1, m2) + b'471'
                + bytes([pin_code, int(lay.group(2), 16), int(init.group(1), 16), int(init.group(2), 16), proto,
                         int(init.group(3), 16), sizes, shift])
                + struct.pack('<HHHH', (fw_rel >> shift) & 0xFFFF, ((ee - 32) >> shift) & 0xFFFF, (ee >> shift) & 0xFFFF,
                              ((ee + 48) >> shift) & 0xFFFF))
        got = bytes(mem.get(a, 0xFF) for a in range(devinfo, devinfo + len(want)))
        version = re.search(r'#define BOOTLOADER_VERSION (\d+)', ver_h).group(1)
        # the comms pin is the ESC input AM32 listens on, and the circuit's
        want_pin = None
        if AM32 and am32_targets()[0]:
            want_pin = [q for q, (f, _) in am32_phase_map(am32_targets()[0])[0].items() if f == 'SIG'][0]
        sig = sorted(set(at32_ports('U_ESC%d' % n).get('%s%s' % (mn.group(1), mn.group(2))) for n in (1, 2, 3, 4)))
        check(S, 'am32/%s: device info at 0x%08X (ldscript_bl.ld DEVINFO, main.c devinfo, %d bytes): magic, "471", pin code '
                 '0x%02X (%s%s; the ESC input in AM32 %s, on %s), flash-size code 0x%02X (%d KB layout, f421 blutil.h), '
                 'protocol %d, firmware 0x%04X, file name 0x%04X, settings 0x%04X, tune 0x%04X; settings 0x%08X = AM32\'s '
                 'EEPROM_START_ADD %s; no code at or past 0x%08X; V%s = version.h %s'
              % (name, devinfo, len(want), pin_code, mn.group(1), mn.group(2), want_pin or '?', '/'.join(map(str, sig)),
                 int(lay.group(2), 16), size, proto, fw_rel, (ee - 32) & 0xFFFF, ee & 0xFFFF, (ee + 48) & 0xFFFF, ee,
                 '0x%08X' % eeprom if eeprom else '?', bl_end, mn.group(4), version),
              got == want and max(mem) < bl_end and (eeprom is None or ee == eeprom) and mn.group(4) == version
              and (want_pin is None or want_pin == '%s%s' % (mn.group(1), mn.group(2)))
              and sig == ['M%d_SIG' % n for n in (1, 2, 3, 4)] and (app is None or app == flash0 + fw_rel),
              'image %s, source %s' % (got.hex(' '), want.hex(' ')) if got != want else '')
    # the flashing script writes these two images
    sh = open(os.path.join(FW, 'am32', 'flash_esc.sh')).read()
    imgs = re.findall(r'^(?:BL|FW)=(\S+)$', sh, re.M)
    check(S, 'am32/flash_esc.sh writes %s, both in firmware/am32' % ' and '.join(imgs),
          len(imgs) == 2 and all(os.path.exists(os.path.join(FW, 'am32', f)) for f in imgs)
          and {os.path.basename(f) for f in fw + bl} == set(imgs))


def check_options():
    """Option groups (circuit.OPTIONS): a build that leaves a group off must
    leave everything else working.  Every net a group owns is touched only
    by that group's parts; every other net a remaining part uses still has
    a part at each end (a signal or supply that only the group drove would
    be left with one pin); and the supplies that feed the rest keep their
    sources."""
    S = 'Option groups'
    for board in ('fc', 'esc'):
        comps = circuit.build(board)
        full = circuit.nets(comps)
        for opt in circuit.OPTIONS:
            grp = [c for c in comps if c.option == opt]
            if not grp:
                continue
            owned = circuit.OPTION_NETS[opt]
            bad = sorted('%s on %s' % (c.ref, n) for c in comps if c.option != opt
                         for n in c.pins.values() if n in owned)
            check(S, '%s, %s group: its nets (%d) reach no part outside it' % (board, opt, len(owned)),
                  not bad, ', '.join(bad) or '%d parts in the group' % len(grp))
            rest = [c for c in comps if c.option != opt]
            left = circuit.nets(rest)
            lost = sorted(n for n, m in left.items() if len(m) < 2 and len(full[n]) >= 2
                          and not all(c.part in parts.PADS or c.ref.startswith('U_') for c in comps
                                      if c.ref in {r for r, _ in m}))
            single = sorted(n for n, m in left.items() if len(m) < 2 and len(full[n]) >= 2)
            check(S, '%s without the %s group: no net left with a single pin, beyond MCU pins the group used'
                  % (board, opt), not lost, 'left on an MCU pin only: %s' % (', '.join(single) or 'none'))
            supplies = {'fc': ['VBAT', 'GND', '+5V', '+3V3', '+3V3_GYRO'],
                        'esc': ['VBAT', 'GND', 'DRV_EN', 'ESC_3V3'] + ['M%d_%s' % (n, r) for n in (1, 2, 3, 4)
                                                                      for r in ('DVDD', '3V3')]}[board]
            src = {n: sorted(r for r, _ in left.get(n, [])) for n in supplies}
            check(S, '%s without the %s group: every supply keeps its source' % (board, opt),
                  all(len(v) >= 2 for v in src.values()) and not any(n in owned for n in supplies),
                  '; '.join('%s %d parts' % (n, len(v)) for n, v in src.items()))


def find_source(name, test):
    """A checkout or folder this session left in a scratchpad (when no
    environment variable names it)."""
    for pat in ('/tmp/claude-*/*/*/scratchpad/%s' % name, '/tmp/claude-*/**/%s' % name):
        for guess in glob.glob(pat, recursive=True):
            if os.path.exists(os.path.join(guess, test)):
                return guess
    return ''


def main():
    global AM32, AM32_BL, BF, DATASHEETS
    AM32 = AM32 or find_source('am32', 'Inc/targets.h')
    AM32_BL = AM32_BL or find_source('am32-bootloader', 'bootloader/main.c')
    BF = BF or find_source('bf', 'src/main/drivers/accgyro/accgyro_spi_icm426xx.c')
    DATASHEETS = DATASHEETS or find_source('parts2/ds', 'ti_drv8320.txt')
    check_fc_pins()
    check_esc_pins()
    check_fw_scales()
    check_power()
    check_options()
    for board, name in (('fc', 'ridge3-fc'), ('esc', 'ridge3-esc')):
        check_board(board, name)
        if os.path.exists(board_file(board, name)):
            check_pads_models(board, name)
            check_silk(board, name)
    check_brand()
    check_firmware()
    n_fail = sum(1 for r in rows if r[2] == 'FAIL')
    n_pass = sum(1 for r in rows if r[2] == 'PASS')
    out = ['# Ridge 3 stack: design verification', '',
           'Generated by `src/verify.py`. %d checks passed, %d failed, %d skipped or informational.' %
           (n_pass, n_fail, len(rows) - n_pass - n_fail), '',
           '**What this is not:** no board has been built. Nothing here was measured on hardware. '
           'These checks compare the design against sources other than itself (KiCad\'s symbol '
           'libraries, the parts\' datasheets, the Betaflight and AM32 sources, the brand files) '
           'and run the fab outputs through KiCad\'s DRC. Bring-up on the bench, in the order in '
           'the README, is still the test.', '',
           'Sources read: AM32 %s; AM32-bootloader %s; Betaflight %s; datasheets %s.' % (
               AM32 or 'not found', AM32_BL or 'not found', BF or 'not found', DATASHEETS or 'not found'), '']
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
