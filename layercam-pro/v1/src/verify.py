# -*- coding: utf-8 -*-
"""Design checks that are not DRC: each one compares two independent
sources and fails loudly.

  regulators   every buck's output from its feedback divider (circuit.py
               and the resistor values in parts.py) inside the rail's limits
  sensor       the image sensor's balls: every net in circuit.py on the
               ball the SC4336P-family library names for it (by position on
               the routed board)
  case         the board inside the case's outline (Prusa's outside less a
               wall), the screws 3 mm or more from the edge, the IR LEDs
               clear of the IR-cut holder's base, the USB-C's mouth where
               the case's opening is
  heights      the parts under the IR-cut holder's recess and under the
               SoC's heatsink no taller than the room there
  firmware     the device tree's pins (firmware/) against circuit.py
               (when the firmware is present)

    python3 src/verify.py            (inside the toolchain: tools/kd)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit, parts, pcb, geometry as G

FAIL = []


def check(ok, what):
    print('  [%s] %s' % ('ok' if ok else 'FAIL', what), flush=True)
    if not ok:
        FAIL.append(what)


def ohms(part):
    v = parts.PARTS[part]['value'].lower().replace('r', '')
    k = 1e3 if v.endswith('k') else 1e6 if v.endswith('m') else 1
    return float(v.rstrip('km')) * k


# rail -> (feedback net, reference V, low limit, high limit, what sets the limits)
RAILS = {
    'VDD_0V9': ('FB_0V9', 0.6, 0.85, 0.95, 'RV1106 core'),
    'VCC_3V3': ('FB_3V3', 0.6, 3.0, 3.465, 'VCCIO 3.3 V +-5 %'),
    'VCC_DDR': ('FB_DDR', 0.6, 1.283, 1.45, 'DDR3L 1.35 V'),
    'VCC_1V8': ('FB_1V8', 0.6, 1.71, 1.89, '1.8 V +-5 %'),
    'VWIFI': ('FB_WIFI', 0.6, 3.0, 3.6, 'ESP32-C6 3V3, 3.0-3.6 V'),
}


def regulators():
    comps = circuit.build('main')
    for rail, (fb, vref, lo, hi, why) in RAILS.items():
        top = [c for c in comps if c.ref.startswith('R') and set(c.pins.values()) == {rail, fb}]
        bot = [c for c in comps if c.ref.startswith('R') and set(c.pins.values()) == {fb, 'GND'}]
        if len(top) != 1 or len(bot) != 1:
            check(False, '%s: one resistor %s-%s and one %s-GND (found %d, %d)' % (rail, rail, fb, fb, len(top), len(bot)))
            continue
        rt, rb = ohms(top[0].part), ohms(bot[0].part)
        v = vref * (1 + rt / rb)
        check(lo <= v <= hi, '%s = %.3f V (%s / %s; %.3f-%.3f V, %s)'
              % (rail, v, top[0].part[1:], bot[0].part[1:], lo, hi, why))


def _board():
    import pcbnew
    path = os.environ.get('MAIN_BOARD') or pcb.board_path('main')
    if not os.path.exists(path):
        return None
    pcb.configure('main')
    return pcbnew.LoadBoard(path)


# the SC4336P-family CSP-35 ball names (EasyEDA C9900187041's symbol), the
# second source against circuit.py's nets
BALL_NAMES = {'A1': 'AGND', 'A3': 'EXTCLK', 'A4': 'SDA', 'A5': 'SCL', 'A6': 'XSHUTDN', 'B1': 'AVDD', 'B2': 'DOGND',
              'B4': 'DVDD', 'B5': 'SID', 'B6': 'DVDD', 'B7': 'AVDD', 'C1': 'DVDD', 'C2': 'DOVDD', 'C3': 'DOVDD',
              'C4': 'MCP', 'C6': 'PWDNB', 'C7': 'AGND', 'D2': 'MD1N', 'D3': 'MD1P', 'D4': 'MCN', 'D5': 'MD0N',
              'D6': 'DOGND', 'D7': 'VREFN2', 'E4': 'DVDD', 'E5': 'MD0P', 'E7': 'VREFN'}
NAME_NET = {'AGND': 'GND', 'DOGND': 'GND', 'SID': 'GND', 'EXTCLK': 'CAM_MCLK', 'SDA': 'CAM_SDA', 'SCL': 'CAM_SCL',
            'XSHUTDN': 'CAM_RST', 'PWDNB': 'CAM_PWDN', 'AVDD': 'CAM_AVDD', 'DVDD': 'CAM_DVDD', 'DOVDD': 'CAM_DOVDD',
            'MCP': 'CSI_CKP', 'MCN': 'CSI_CKN', 'MD0P': 'CSI_D0P', 'MD0N': 'CSI_D0N', 'MD1P': 'CSI_D1P',
            'MD1N': 'CSI_D1N', 'VREFN': 'CAM_VREFN', 'VREFN2': 'CAM_VREFN2'}


def sensor():
    comps = {c.ref: c for c in circuit.build('main')}
    pins = comps['U8'].pins
    bad = [(b, n, pins.get(b)) for b, n in BALL_NAMES.items() if pins.get(b) != NAME_NET[n]]
    nc = [b for b, n in pins.items() if n and b not in BALL_NAMES]
    check(not bad and not nc, 'image sensor: every ball carries the net its name calls for %s' % ((bad + nc)[:4] or ''))
    b = _board()
    if b is None:
        print('  [--] sensor on the board: no board yet')
        return
    fp = b.FindFootprintByReference('U8')
    # on the front face, centred on the lens axis; A1 at the +x, -y corner
    # seen from behind (the footprint mirrored)
    x, y = pcb.xy(fp.GetPosition())
    a1 = pcb.pad_at(b, 'U8', 'A1')
    check(fp.IsFlipped() and abs(x) < 0.01 and abs(y) < 0.01 and a1[0] > 1.8 and a1[1] < -1.0,
          'image sensor on the front face on the lens axis, ball A1 at (%.2f, %.2f)' % a1)


def case():
    from shapely.geometry import Polygon, Point, box
    import math
    board = pcb.board_polygon('main')
    outline = Polygon([(x, -y) for x, y in G.OUTLINE])
    # the board's outline is the case's inside: the outline itself, plus
    # the USB tab into the wall
    extra = board.difference(outline.buffer(0.01)).area
    check(extra <= G.USB_TAB * G.USB_TAB_W + 0.5, 'board inside the case outline but for the USB tab (%.1f mm2 outside)' % extra)
    d = min(board.exterior.distance(Point(x, -y)) for x, y in G.SCREWS)
    check(d >= 3.0, 'screw holes 3.0 mm or more from the edge (closest %.2f mm)' % d)
    x0, y0, x1, y1 = G.HOLDER_BOX
    holder = box(x0, -y1, x1, -y0)
    b = _board()
    if b is None:
        return
    gaps = []
    for k, a in enumerate(G.LED_ANGLES):
        fp = b.FindFootprintByReference('D%d' % (k + 2))
        import placer
        gaps.append(placer.courtyard(fp, 'B').distance(holder))
        lx, ly = G.led_xy(a)
        px, py = pcb.xy(fp.GetPosition())
        check(math.hypot(px - lx, py + ly) < 0.01, 'D%d under its rod at %d degrees' % (k + 2, a))
    check(min(gaps) >= 0.3, 'IR LEDs clear of the IR-cut holder\'s base (closest courtyard %.2f mm)' % min(gaps))
    # the USB-C's mouth: 5.24 mm from the footprint's origin along its +y
    fp = b.FindFootprintByReference('J1')
    ox, oy = pcb.xy(fp.GetPosition())
    r = math.radians(fp.GetOrientationDegrees())
    mx, my = ox + 5.24 * math.sin(r), oy + 5.24 * math.cos(r)
    ex, ey = G.USB_EDGE_XY
    a = math.radians(G.USB_NORMAL_DEG)
    out = (mx - ex) * math.cos(a) + (my + ey) * -math.sin(a)
    side = (mx - ex) * math.sin(a) + (my + ey) * math.cos(a)
    check(abs(out - 4.2) < 0.05 and abs(side) < 0.05,
          'USB-C mouth 4.2 mm out along the edge normal, on the opening\'s centre (%.2f out, %.2f aside)' % (out, side))


def heights():
    """Parts under the IR-cut holder's recess (front face) and under the
    SoC's heatsink (back face): no taller than the room there."""
    import layout_main as L, placer
    from shapely.geometry import box
    b = _board()
    if b is None:
        return
    comps = {c.ref: c for c in circuit.build('main')}
    rx0, ry0, rx1, ry1 = L.RECESS
    recess = box(rx0, ry0, rx1, ry1)
    bad = [fp.GetReference() for fp in b.GetFootprints()
           if fp.IsFlipped() and fp.GetReference() not in ('U8',) and not fp.GetReference().startswith('H')
           and placer.courtyard(fp, 'B').intersects(recess)
           and L.height(comps[fp.GetReference()].part) > L.UNDER_HOLDER_MAX_H]
    check(not bad, 'front face in the IR-cut holder\'s recess: every part %.1f mm or lower %s' % (L.UNDER_HOLDER_MAX_H, bad or ''))
    x0, y0, x1, y1 = G.HOLDER_BOX
    ring = box(x0, -y1, x1, -y0).difference(recess)
    bad = [fp.GetReference() for fp in b.GetFootprints()
           if fp.IsFlipped() and not fp.GetReference().startswith('H') and placer.courtyard(fp, 'B').intersects(ring)]
    check(not bad, 'front face under the IR-cut holder\'s base (outside the recess): no part %s' % (bad or ''))
    cx, cy = G.SOC_XY[0], -G.SOC_XY[1]
    hw, hh = G.HEATSINK[0] / 2, G.HEATSINK[1] / 2
    hs = box(cx - hw, cy - hh, cx + hw, cy + hh)
    bad = [fp.GetReference() for fp in b.GetFootprints()
           if not fp.IsFlipped() and fp.GetReference() not in ('U1',) and not fp.GetReference().startswith('H')
           and placer.courtyard(fp, 'F').intersects(hs)
           and L.height(comps[fp.GetReference()].part) > G.UNDER_HEATSINK_MAX_H]
    check(not bad, 'back face under the SoC heatsink: every part %.1f mm or lower %s' % (G.UNDER_HEATSINK_MAX_H, bad or ''))


def firmware():
    dts = os.path.join(V1, 'firmware')
    try:
        import check_firmware
    except ImportError:
        print('  [--] firmware pin map: no firmware check yet (src/check_firmware.py)')
        return
    for ok, what in check_firmware.run(dts):
        check(ok, what)


if __name__ == '__main__':
    print('== LayerCam Pro v1 design checks')
    regulators()
    sensor()
    case()
    heights()
    firmware()
    if FAIL:
        raise SystemExit('%d check(s) failed' % len(FAIL))
    print('all design checks passed')
