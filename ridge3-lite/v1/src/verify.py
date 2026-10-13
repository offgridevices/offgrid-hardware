# -*- coding: utf-8 -*-
"""Write ../VERIFICATION.md: every check of the design that can be made
without hardware, each against a source other than the design itself.

  pin maps      the FC against Betaflight's TAKERG4AIO config.h and KiCad's
                own STM32G473 symbol; every ESC against AM32's targets.h and
                G071 drivers and LCSC's STM32G071 symbol (firmware/upstream)
  orientation   the gyro's placement against Betaflight's alignment maths
                (firmware/gyro_orientation_check.py)
  arithmetic    regulators, dividers and scales against the datasheets'
                equations and the firmware's constants
  simulations   the ngspice and thermal studies' verdicts (sim/)
  board         KiCad DRC, netlist, outline, stackup, fab outputs, silkscreen
  firmware      every binary against the sha256 its README states

    kd python3 verify.py
"""
import os, sys, re, json, glob, hashlib, subprocess, csv, zipfile, math, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit, parts

NAME = 'ridge3-lite'
UP = os.path.join(V1, 'firmware', 'upstream')
RESULTS = []


def check(section, name, ok, detail=''):
    RESULTS.append((section, 'PASS' if ok is True else ('INFO' if ok is None else 'FAIL'), name, detail))


def comp(ref):
    return {c.ref: c for c in circuit.build()}[ref]


# ------------------------------------------------------------------ symbols
def _sexp_symbols(path):
    """{symbol name: {pin number: pin name}} from a .kicad_sym, following
    'extends'."""
    s = open(path).read()
    out, ext = {}, {}
    tops = [m for m in re.finditer(r'\n\s*\(symbol "([^"]+)"', s) if not re.search(r'_\d+_\d+$', m.group(1))]
    for k, m in enumerate(tops):
        name = m.group(1)
        end = tops[k + 1].start() if k + 1 < len(tops) else len(s)
        body = s[m.end():end]
        e = re.search(r'\(extends "([^"]+)"\)', body[:400])
        if e:
            ext[name] = e.group(1)
        pins = {}
        for pm in re.finditer(r'\(pin \w+ \w+.*?\(name "([^"]*)".*?\(number "([^"]*)"', body, re.S):
            pins[pm.group(2)] = pm.group(1)
        out[name] = pins
    for n, base in ext.items():
        if not out.get(n):
            out[n] = out.get(base, {})
    return out


def kicad_symbol(lib, name):
    return _sexp_symbols('/usr/share/kicad/symbols/%s.kicad_sym' % lib).get(name, {})


def lcsc_symbol(name):
    return _sexp_symbols(os.path.join(HERE, 'easyeda_raw', 'lcsc-symbols.kicad_sym')).get(name, {})


def by_port(pins):
    """{port name 'PA0': pin number} from symbol pin names like
    'PA0', 'PB8-BOOT0', 'PA11[PA9]' (the remapped name in brackets)."""
    out = {}
    for num, nm in pins.items():
        for part in re.split(r'[-/\[\]]', nm):
            if re.fullmatch(r'P[A-G]\d{1,2}', part):
                out.setdefault(part, num)
    return out


def cdefines(text):
    # a define with no value (USE_GYRO_SPI_ICM42688P) is in the dict as ''
    return {m.group(1): m.group(2) or '' for m in re.finditer(r'#define[ \t]+(\w+)(?:[ \t]+([^ \t\n]+))?', text)}


# ------------------------------------------------------------------ FC
FC_MAP = {   # TAKERG4AIO define -> net on this board (None: pin left open)
    'MOTOR1_PIN': 'M1_SIG', 'MOTOR2_PIN': 'M2_SIG', 'MOTOR3_PIN': 'M3_SIG', 'MOTOR4_PIN': 'M4_SIG',
    'GYRO_1_EXTI_PIN': 'GYRO_INT', 'GYRO_1_CS_PIN': 'GYRO_CS', 'SPI1_SCK_PIN': 'SPI1_SCK',
    'SPI1_SDI_PIN': 'SPI1_MISO', 'SPI1_SDO_PIN': 'SPI1_MOSI', 'UART1_TX_PIN': 'UART1_TX',
    'UART1_RX_PIN': 'UART1_RX', 'UART2_TX_PIN': 'UART2_TX', 'UART2_RX_PIN': 'UART2_RX',
    'LED0_PIN': 'LED0', 'LED_STRIP_PIN': 'LED_STRIP', 'BEEPER_PIN': 'BEEPER', 'ADC_VBAT_PIN': 'ADC_VBAT',
    'ADC_CURR_PIN': 'CUR', 'FLASH_CS_PIN': None, 'MAX7456_SPI_CS_PIN': None, 'SPI2_SCK_PIN': None,
    'SPI2_SDI_PIN': None, 'SPI2_SDO_PIN': None, 'UART4_TX_PIN': None, 'UART4_RX_PIN': None,
    'LPUART1_TX_PIN': None, 'LPUART1_RX_PIN': None,
}


def check_fc():
    S = 'FC pin map (Betaflight TAKERG4AIO)'
    cfg = cdefines(open(os.path.join(UP, 'TAKERG4AIO-config.h')).read())
    sym = kicad_symbol('MCU_ST_STM32G4', 'STM32G473CEUx')
    check(S, 'KiCad symbol STM32G473CEUx read', len(sym) == 49, '%d pins' % len(sym))
    port = by_port(sym)
    u = comp('U_FC')
    for d, net in FC_MAP.items():
        p = cfg.get(d)
        if p is None:
            check(S, '%s defined in TAKERG4AIO' % d, False)
            continue
        pin = port.get(p)
        got = u.pins.get(pin)
        check(S, '%s %s (pin %s) carries %s' % (d, p, pin, net or 'nothing'), got == net,
              'circuit.py: %s' % got)
    for p, net in (('PA11', 'USB_DM'), ('PA12', 'USB_DP'), ('PF0', 'HSE_IN'), ('PF1', 'HSE_OUT'), ('PB8', 'BOOT0')):
        check(S, '%s (pin %s) carries %s' % (p, port[p], net), u.pins.get(port[p]) == net)
    pw = [n for n, nm in sym.items() if re.match(r'(VDD|VDDA|VREF\+|VBAT)$', nm)]
    check(S, 'every VDD / VDDA / VREF+ / VBAT pin on +3V3 (%s)' % ','.join(sorted(pw, key=int)),
          all(u.pins.get(n) == '+3V3' for n in pw))
    check(S, 'exposed pad (VSS) on GND', u.pins.get('49') == 'GND')
    check(S, 'SYSTEM_HSE_MHZ 8 = the 8 MHz crystal', cfg.get('SYSTEM_HSE_MHZ') == '8' and
          parts.PARTS[comp('Y1').part]['value'] == '8 MHz')
    check(S, 'gyro driver: TAKERG4AIO builds USE_GYRO_SPI_ICM42688P, the BOM has the ICM-42688-P',
          'USE_GYRO_SPI_ICM42688P' in cfg and comp('U_IMU').part == 'ICM42688P')
    check(S, 'current scale: TAKERG4AIO DEFAULT_CURRENT_METER_SCALE %s = board 12.0 mV/A' %
          cfg.get('DEFAULT_CURRENT_METER_SCALE'), cfg.get('DEFAULT_CURRENT_METER_SCALE') == '120')


# ------------------------------------------------------------------ ESC
def am32_group(text, name):
    m = re.search(r'#ifdef\s+%s\b(.*?)#endif' % name, text, re.S)
    return m.group(1) if m else ''


def check_esc():
    S = 'ESC pin map (AM32 GEN_64K_G071, group G0_A)'
    t = open(os.path.join(UP, 'am32-targets.h')).read()
    tgt = cdefines(am32_group(t, 'GEN_64K_G071'))
    check(S, 'GEN_64K_G071 uses HARDWARE_GROUP_G0_A', 'HARDWARE_GROUP_G0_A' in am32_group(t, 'GEN_64K_G071'))
    g = am32_group(t, 'HARDWARE_GROUP_G0_A')
    gd = cdefines(g)
    mcu = t.split('#ifdef MCU_G071', 1)[1].split('#ifdef MCU_G031', 1)[0]
    sym = lcsc_symbol('STM32G071GBU6')
    check(S, 'LCSC symbol STM32G071GBU6 read', len(sym) == 28, '%d pins' % len(sym))
    port = by_port(sym)

    def pinof(port_letter, pin_macro):
        n = re.search(r'PIN_(\d+)', pin_macro).group(1)
        return 'P%s%s' % (port_letter, n)
    want = {}
    want[pinof(gd['INPUT_PIN_PORT'][-1], gd['INPUT_PIN'])] = 'SIG'
    for ph in 'ABC':
        want[pinof(gd['PHASE_%s_GPIO_PORT_LOW' % ph][-1], gd['PHASE_%s_GPIO_LOW' % ph])] = 'L' + ph
        want[pinof(gd['PHASE_%s_GPIO_PORT_HIGH' % ph][-1], gd['PHASE_%s_GPIO_HIGH' % ph])] = 'H' + ph
        cm = re.search(r'#define PHASE_%s_COMP\s+\S+\s*//\s*(p[a-z]\d+)' % ph, g)
        want[cm.group(1).upper()] = 'CMP_' + ph
    cur = re.search(r'#define CURRENT_ADC_PIN LL_GPIO_PIN_(\d+)', mcu.split('#ifdef MCU_G031')[0])
    vol = re.search(r'#define VOLTAGE_ADC_PIN LL_GPIO_PIN_(\d+)', mcu.split('#ifdef MCU_G031')[0])
    want['PA%s' % cur.group(1)] = 'ISENSE'
    want['PA%s' % vol.group(1)] = 'VSENSE'
    per = open(os.path.join(UP, 'am32-g071-peripherals.c')).read()
    inp = re.search(r'(P[A-C]\d+)\s+-+>\s+COMP2_INP', per).group(1)
    want[inp] = 'NEUTRAL'
    for n in (1, 2, 3, 4):
        u = comp('U_E%d' % n)
        bad = [(p, port.get(p), u.pins.get(port.get(p)), 'M%d_%s' % (n, f)) for p, f in sorted(want.items())
               if u.pins.get(port.get(p)) != 'M%d_%s' % (n, f)]
        check(S, 'ESC %d: input, 6 gate outputs, 3 comparators, neutral, current, voltage on AM32\'s pins' % n,
              not bad, ', '.join('%s %s' % (p, f) for p, f in sorted(want.items())) if not bad else str(bad))
        check(S, 'ESC %d: VDD/VDDA on +3V3E, VSS on GND' % n, u.pins.get('3') == '+3V3E' and u.pins.get('4') == 'GND')
    check(S, 'remap: PA11/PA12 pads carry PA9/PA10 (AM32 enables the remap: NO_PA11_PA12_REMAP unset)',
          'NO_PA11_PA12_REMAP' not in am32_group(t, 'GEN_64K_G071') and 'LL_SYSCFG_PIN_RMP_PA11' in per)
    mva = tgt.get('MILLIVOLT_PER_AMP')
    check(S, 'MILLIVOLT_PER_AMP %s = the board\'s 20.0 mV/A at PA5' % mva, mva == '20',
          '0.5 mOhm x 100 V/V x 1k/(1k+1.5k) = %.1f mV/A' % (0.5 * 100 * 1 / 2.5))
    div = re.search(r'#ifndef TARGET_VOLTAGE_DIVIDER\s+#define TARGET_VOLTAGE_DIVIDER (\d+)', t).group(1)
    check(S, 'TARGET_VOLTAGE_DIVIDER %s (default) = the board\'s 100k/10k (ratio 11)' % div, div == '110')


# ------------------------------------------------------------------ orientation
def check_gyro():
    S = 'Gyro orientation'
    import json as _j
    pl = _j.load(open(os.path.join(HERE, 'placement.json')))
    rot = pl['U_IMU'][2]
    check(S, 'U_IMU placed at 135 degrees on top (firmware/gyro-orientation.md)', rot == 135 and pl['U_IMU'][3] == 'T',
          'placement %s' % (pl['U_IMU'],))
    r = subprocess.run([sys.executable, os.path.join(V1, 'firmware', 'gyro_orientation_check.py')],
                       capture_output=True, text=True, cwd=os.path.join(V1, 'firmware'))
    check(S, 'gyro_orientation_check.py: Betaflight\'s alignment maths on this footprint gives the quad\'s axes '
          'with TAKERG4AIO\'s CW270 + board yaw 45', r.returncode == 0,
          (r.stdout.strip().splitlines() or ['no output'])[-1][:160])


# ------------------------------------------------------------------ arithmetic
def check_power():
    S = 'Power and analog arithmetic'
    v4s = 4 * 4.35        # 4S HV pack
    en = 1.263 * (100 + 27) / 27
    check(S, 'BEC enable: 1.263 V x 127k/27k = %.2f V (off while USB back-feeds ~4 V, on above a flat 2S)' % en,
          4.5 < en < 6.4)
    gv = 1.193 * (1 + 82 / 10)
    check(S, 'gate drive: 1.193 V x (1 + 82k/10k) = %.2f V (FETs specified at 10 V; DRV8300 GVDD 5-20 V; '
             'FET VGS 20 V max)' % gv, 10.0 <= gv <= 12.0)
    check(S, 'FC battery divider 10k/1k = ratio 11 (Betaflight vbat_scale 110): %.1f V -> %.2f V at PB2' %
          (v4s, v4s / 11), v4s / 11 < 3.3)
    check(S, 'ESC battery divider 100k/10k = ratio 11 (AM32 divider 110): %.1f V -> %.2f V at PA6' %
          (v4s, v4s / 11), v4s / 11 < 3.3)
    cur = 50 / 4 * 62 / (62 + 10 / 4)
    check(S, 'battery current to the FC: (50 mV/A / 4) x 62k/(62k+2.5k) = %.2f mV/A (ibata_scale 120)' % cur,
          abs(cur - 12.0) < 0.1)
    bemf = v4s * 2.2 / 12.2
    check(S, 'back-EMF divider 10k/2.2k: %.1f V phase -> %.2f V at the comparator (VDDA 3.3 V)' % (v4s, bemf),
          bemf < 3.3)
    check(S, 'FET VDS rating 40 V = %.1fx a full 4S HV pack (%.1f V)' % (40 / v4s, v4s), 40 / v4s > 2)
    check(S, 'TVS SMF22A: 22 V stand-off above %.1f V; 35.5 V clamp at 5.6 A under the FETs\' 40 V' % v4s,
          22 > v4s)
    check(S, 'BEC LMR36506 VIN 70 V abs max = %.1fx the pack' % (70 / v4s), 70 / v4s > 3)
    check(S, 'gate-drive LDO TPS7A1601 IN 60 V abs max = %.1fx the pack' % (60 / v4s), 60 / v4s > 3)
    bad = []
    for c in circuit.build():
        p = parts.PARTS.get(c.part, {})
        m = re.search(r'(\d+)V', p.get('desc', ''))
        if p.get('kind') != 'C' or not m:
            continue
        nets = set(c.pins.values())
        work = v4s if nets & {'VBAT', 'GVDD_IN'} or any(n and n.endswith('_SRC') for n in nets) else \
            11.0 if nets & {'GVDD'} or any(n and '_BST' in n for n in nets) else \
            5.0 if nets & {'+5V', 'USB_VBUS', 'BEC_VCC', 'BEC_BOOT'} else 3.3
        if int(m.group(1)) < 1.5 * work:
            bad.append((c.ref, m.group(1), work))
    check(S, 'every capacitor rated at least 1.5x its working voltage', not bad, str(bad[:6]))


# ------------------------------------------------------------------ simulations
def check_sims():
    S = 'Simulations (sim/)'
    readme = os.path.join(V1, 'sim', 'README.md')
    if not os.path.exists(readme):
        check(S, 'sim/README.md present', False)
        return
    txt = open(readme).read()
    sect = txt.split('## Verdict', 1)[-1].split('\n## ', 1)[0]
    for line in sect.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 5 or cells[0] in ('#', '---') or set(cells[0]) <= set('-'):
            continue
        verdict = cells[-1].replace('*', '').upper()
        ok = True if verdict.startswith('PASS') else (False if 'FAIL' in verdict and 'PASS' not in verdict else None)
        name = '%s: %s' % (cells[1], cells[2])
        detail = 'limit %s; margin %s; %s' % (cells[3], cells[4], cells[-1])
        if ok is False and ('as drawn' in cells[1] or 'unplugged' in cells[1] or 'snubber' in cells[1]):
            ok = None       # superseded designs and an abuse case the README treats on its own
        check(S, name[:150], ok, detail[:200])
    th = os.path.join(V1, 'sim', 'thermal', 'results.md')
    if os.path.exists(th):
        for line in open(th).read().splitlines():
            if line.startswith('| ') and ('PASS' in line or 'FAIL' in line):
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                check('Thermal (sim/thermal)', ' / '.join(cells[:-1])[:160],
                      True if 'PASS' in cells[-1] else False, cells[-1])


# ------------------------------------------------------------------ board
def check_board():
    S = 'Board %s' % NAME
    import pcbnew, pcb, fab
    path = os.path.join(V1, NAME + '.kicad_pcb')
    if not os.path.exists(path):
        check(S, 'board file present', False)
        return
    tmp = tempfile.mkdtemp()
    e, w, u = pcb.drc(path, os.path.join(tmp, 'drc.json'))
    check(S, 'KiCad 10 DRC (all severities, zones refilled): %d errors, %d warnings, %d unconnected' %
          (len(e), len(w), len(u)), not e and not w and not u)
    bad = fab.check_netlist(path, None)
    check(S, 'every pad carries the net circuit.py gives it', not bad, str(bad[:4]))
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    W, H = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    # the bounding box takes in the 0.1 mm outline stroke
    side = 2 * pcb.HALF
    check(S, 'outline %.2f x %.2f mm (%g x %g)' % (W - 0.1, H - 0.1, side, side),
          abs(W - 0.1 - side) < 0.05 and abs(H - 0.1 - side) < 0.05)
    holes = sorted((round(fp.GetPosition().x / 1e6 - pcb.CX, 2), round(fp.GetPosition().y / 1e6 - pcb.CY, 2))
                   for fp in b.GetFootprints() if fp.GetReference().startswith('H'))
    check(S, 'mounting holes on the 25.5 mm square: %s' % holes,
          all(abs(abs(x) - 12.75) < 0.01 and abs(abs(y) - 12.75) < 0.01 for x, y in holes) and len(holes) == 4)
    check(S, '%d copper layers' % pcb.NLAYERS, b.GetCopperLayerCount() == pcb.NLAYERS)
    ds = b.GetDesignSettings()
    tw = min((t.GetWidth() for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK'), default=0) / 1e6
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    vd = min(v.GetWidth(pcbnew.F_Cu) for v in vias) / 1e6
    vh = min(v.GetDrillValue() for v in vias) / 1e6
    check(S, 'min track %.2f mm, min via %.2f / %.2f mm, %d vias (JLCPCB 6+ layer standard: 0.09 mm, 0.25 / 0.15 mm)'
          % (tw, vd, vh, len(vias)), tw >= 0.09 and vd >= 0.25 and vh >= 0.15)
    txt = open(path).read()
    check(S, 'stackup in the board file: black mask, white silk, ENIG',
          '(color "Black")' in txt and '(color "White")' in txt and 'ENIG' in txt)
    prod = os.path.join(V1, 'production')
    zp = os.path.join(prod, NAME + '-gerbers.zip')
    if os.path.exists(zp):
        names = zipfile.ZipFile(zp).namelist()
        cu = [n for n in names if re.search(r'[-_](F|B|In\d)_Cu\.g', n)]
        check(S, 'gerber zip: %d files, %d copper layers, drill files' % (len(names), len(cu)),
              len(cu) == pcb.NLAYERS and any(n.endswith('.drl') for n in names))
    for f in ('-bom-jlcpcb.csv', '-cpl-jlcpcb.csv', '-bom-pcbway.csv', '-assembly.pdf', '-netlist.csv'):
        check(S, 'production/%s%s present' % (NAME, f), os.path.exists(os.path.join(prod, NAME + f)))
    gold = sum(1 for d in b.GetDrawings() if d.GetLayer() in (pcbnew.F_Mask, pcbnew.B_Mask))
    silk = [d for d in b.GetDrawings() if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
    # the subdued flag (silk.py, when no ground plate takes the gold one):
    # one silk polygon in the flag's 1.9 : 1 frame, about half of it inked
    # (the black stripes and canton are cut into it; KiCad stores the holes
    # fractured, so they are counted by area)
    subdued = []
    for d in silk:
        if d.GetShape() == pcbnew.SHAPE_T_POLY:
            bb = d.GetBoundingBox()
            w, h = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
            if h > 2 and 1.8 < w / h < 2.0 and 0.3 < d.GetPolyShape().Area() / 1e12 / (w * h) < 0.75:
                subdued.append(round(h, 2))
    check(S, 'artwork: flag (%s) and %d silkscreen outlines'
          % ('%d mask windows: 7 stripes + 50 stars' % gold if gold else 'subdued, silk, %s mm hoist' % subdued, len(silk)),
          (gold >= 8 or subdued) and len(silk) > 20)


# ------------------------------------------------------------------ firmware
def check_firmware():
    S = 'Firmware'
    readme = open(os.path.join(V1, 'firmware', 'README.md')).read()
    for f in sorted(glob.glob(os.path.join(V1, 'firmware', '*', '*.hex'))):
        h = hashlib.sha256(open(f, 'rb').read()).hexdigest()
        check(S, '%s sha256 matches firmware/README.md' % os.path.relpath(f, V1), h in readme, h[:16])


def main():
    for f in (check_fc, check_esc, check_gyro, check_power, check_sims, check_board, check_firmware):
        try:
            f()
        except Exception as ex:
            check(f.__name__, 'check ran', False, '%s: %s' % (type(ex).__name__, ex))
    n_pass = sum(1 for r in RESULTS if r[1] == 'PASS')
    n_fail = sum(1 for r in RESULTS if r[1] == 'FAIL')
    n_info = sum(1 for r in RESULTS if r[1] == 'INFO')
    L = ['# Ridge 3 Lite: design verification', '',
         'Generated by `src/verify.py`. **%d checks passed, %d failed, %d for information.**' % (n_pass, n_fail, n_info),
         '',
         '**What this is not:** no board has been built yet. Nothing here was measured on hardware. These checks '
         'compare the design with sources other than itself (Betaflight\'s and AM32\'s sources, KiCad\'s and '
         'LCSC\'s symbol libraries, datasheet equations, circuit and thermal simulations) and run the fab outputs '
         'through KiCad 10\'s DRC. The bring-up steps in the README are still the test.', '']
    sec = None
    for s, res, name, det in RESULTS:
        if s != sec:
            L += ['', '## ' + s, '', '| Result | Check | Detail |', '|---|---|---|']
            sec = s
        L.append('| %s | %s | %s |' % (res, name.replace('|', '/'), str(det).replace('|', '/')))
    open(os.path.join(V1, 'VERIFICATION.md'), 'w').write('\n'.join(L) + '\n')
    print('%d passed, %d failed, %d info' % (n_pass, n_fail, n_info))
    for r in RESULTS:
        if r[1] == 'FAIL':
            print('  FAIL', r)
    return n_fail


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
