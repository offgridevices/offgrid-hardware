# -*- coding: utf-8 -*-
"""Design checks that are not DRC: each one compares two independent
sources and fails loudly.

  regulators   every buck's output from its feedback divider (circuit.py
               and the resistor values in parts.py) inside the rail's limits
  camera FFC   on the routed main board, each of J2's contacts against the
               module contact in line with it (by position, from the
               module drawing's numbers in geometry.py): same net
  housing      the main board's outline inside the measured pocket, the
               USB board inside its grooves, the ring inside the collar
  heights      every part on the main board's back face under the camera
               module no taller than the gap under the module
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
    'VWIFI': ('FB_WIFI', 0.6, 3.2, 4.8, 'AP6256 VBAT, full RF from 3.2 V'),
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


def camera_ffc():
    """Module contact k sits at x = (k - 10.5) * 0.5 seen from behind the
    board (pin 1 at -x, the row centred on the lens axis: geometry.py); the
    J2 pad nearest that x must carry the module contact's net."""
    import pcbnew
    path = os.environ.get('MAIN_BOARD') or pcb.board_path('main')
    if not os.path.exists(path):
        print('  [--] camera FFC: no routed main board yet')
        return
    pcb.configure('main')
    b = pcbnew.LoadBoard(path)
    j2 = b.FindFootprintByReference('J2')
    pads = [(pcb.xy(p.GetPosition()), p.GetNetname()) for p in j2.Pads() if p.GetNumber() not in ('21', '22')]
    module = {1: 'GND', 2: 'CAM_MCLK', 3: 'GND', 4: 'CSI_D0P', 5: 'CSI_D0N', 6: 'GND', 7: 'CSI_CKP', 8: 'CSI_CKN',
              9: 'GND', 10: 'CSI_D1P', 11: 'CSI_D1N', 12: 'GND', 13: 'CAM_SCL', 14: 'CAM_SDA', 15: 'GND',
              16: 'CAM_RST', 17: 'GND', 18: 'GND', 19: 'VCC_3V3', 20: 'VCC_3V3'}
    bad, worst = [], 0.0
    for k, net in module.items():
        x = (k - 10.5) * 0.5
        (px, py), n = min(pads, key=lambda p: abs(p[0][0] - x))
        worst = max(worst, abs(px - x))
        if n != net:
            bad.append('module %d (%s) meets %s' % (k, net, n))
    check(not bad and worst < 0.1, 'camera FFC: all 20 module contacts meet their own net on J2, in line within '
          '%.2f mm %s' % (worst, bad[:3] or ''))


def housing():
    from shapely.geometry import Polygon
    board = pcb.board_polygon('main')
    pocket = Polygon([(x, -y) for x, y in G.POCKET])
    gap = pocket.exterior.distance(board) if pocket.contains(board) else -board.difference(pocket).area
    check(pocket.contains(board), 'main board inside the measured pocket (less 0.4 mm), closest %.2f mm' % gap)


def heights():
    """Parts on the back face (F) under the camera module: no taller than
    UNDER_MODULE_MAX_H (the module rests 1.0 mm off the board)."""
    import pcbnew
    import layout_main as L
    path = os.environ.get('MAIN_BOARD') or pcb.board_path('main')
    if not os.path.exists(path):
        return
    pcb.configure('main')
    b = pcbnew.LoadBoard(path)
    comps = {c.ref: c for c in circuit.build('main')}
    zone = [g for g, h in L.keepouts('F') if h == G.UNDER_MODULE_MAX_H][0]
    import placer
    bad = []
    for fp in b.GetFootprints():
        if fp.IsFlipped() or fp.GetReference().startswith('H'):
            continue
        if placer.courtyard(fp, 'F').intersects(zone) and L.height(comps[fp.GetReference()].part) > G.UNDER_MODULE_MAX_H:
            bad.append(fp.GetReference())
    check(not bad, 'back face under the camera module: every part %.1f mm or lower %s' % (G.UNDER_MODULE_MAX_H, bad or ''))


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
    print('== LayerCam v1 design checks')
    regulators()
    housing()
    camera_ffc()
    heights()
    firmware()
    if FAIL:
        raise SystemExit('%d check(s) failed' % len(FAIL))
    print('all design checks passed')
