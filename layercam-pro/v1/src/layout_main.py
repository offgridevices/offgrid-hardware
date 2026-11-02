# -*- coding: utf-8 -*-
"""Where every part of the board goes.

Board millimetres, origin on the lens axis, x right, y down the screen,
seen from BEHIND the camera (KiCad's top, F = the board's back face, which
faces the lid).  y = -Y of the lens frame (geometry.py).

    F (back)   the RV1106 15 mm below the lens axis under its 20 x 20 mm
               heatsink (only low parts there); the power stage to its
               right, the flash below-left, the Wi-Fi module upper-left,
               the USB-C on the edge tab upper-left
    B (front)  the image sensor on the lens axis inside the IR-cut
               holder's base; the six IR LEDs round it; the light sensor
               below; the IR-cut driver and lead on the right, the LED
               switch on the left; the SoC's decoupling under it

The large parts have fixed places below.  Every small part (R, C, bead)
is placed by place_small(): beside the pin it serves, on the side that pin
is on, at the nearest free spot, so a change of circuit carries through.
"""
import math
from shapely.geometry import Point, box, Polygon
from shapely.ops import unary_union
import geometry as G
import pcb

F, B = 'F', 'B'

# ---------------------------------------------------------------- fixed parts
# ref -> (x, y, rot, side).  Board mm: x = X, y = -Y (geometry.py); F the
# back face (towards the lid), B the front face (the lens side).
SX, SY = G.SOC_XY[0], -G.SOC_XY[1]       # the SoC, board coordinates: (0, 15)
FIXED = {
    # F, the back face
    'U1': (SX, SY, 0, F),             # RV1106G3: its MIPI pins (top row, left) towards the sensor
    # the power stage right of the heatsink
    'U3': (16.2, 5.6, 90, F),         # triple buck
    'L2': (21.0, 1.6, 0, F),          # 3.3 V
    'L3': (21.0, 5.2, 0, F),          # DDR
    'L4': (21.0, 8.8, 0, F),          # 1.8 V (the case's shoulder is below it)
    'U2': (13.6, 21.8, 90, F),        # 0.9 V buck, below-right of the SoC
    'L1': (16.2, 18.6, 0, F),
    'Y1': (11.7, 17.2, 90, F),        # 24 MHz by the SoC's OSC pins (68/69, right side), clear of the heatsink and the 0.9 V strip
    'U5': (-13.0, 23.0, 90, F),       # SPI NAND, below-left (its pins are the SoC's bottom-left row)
    # Wi-Fi: the module upper-left, its SDIO corner (pins 24-29) towards
    # the SoC's SDMMC0 pins (11-18, left side); its buck beside it
    'U6': (-17.9, 2.4, 0, F),
    'U4': (-14.0, -6.5, 0, F),
    'L5': (-17.6, -6.6, 90, F),
    # USB-C on the edge tab, its mouth along the edge's outward normal
    # (board angle -149.6 deg), 4.2 mm out from the edge: 0.2 mm inside the
    # case's outer face.  The footprint's mouth is 5.24 mm from its origin
    # along its +y.
    'J1': None,
    'U10': (-21.6, -11.6, 0, F),      # USB ESD
    'D1': (-19.0, -15.2, 0, F),       # 5 V TVS
    'U9': (-3.6, -3.4, 0, F),         # the sensor's 2.8 V LDO, behind the sensor
    'LED1': (12.0, 2.4, 0, F),        # status, in the lid's vent window
    # test pads along the bottom edge, below the heatsink: the console's TX
    # RX G for a 3.3 V USB-serial lead and BOOT beside G for tweezers; 5V on
    # its own; the C6's USB pair for recovery
    # (BOOT, G, TX, RX left to right, BOOT nearest the SoC's boot pin 23 on
    # its left side)
    'TP5': (-3.0, 27.4, 0, F), 'TP3': (-1.0, 27.4, 0, F), 'TP1': (1.0, 27.4, 0, F), 'TP2': (3.0, 27.4, 0, F),
    'TP4': (-7.0, 27.4, 0, F),
    'TP6': (-19.4, 13.6, 0, F), 'TP7': (-17.4, 13.6, 0, F),
    # B, the front face
    # the image sensor on the lens axis; its MIPI balls (rows D-E) towards
    # the SoC.  KiCad flips a front-face part top to bottom (a pad at
    # (x, y) lands at (x, -y)); turned 180 degrees it lands at (-x, y), the
    # mirror image seen from behind that pairs.py draws to.  The picture
    # comes out turned 180 degrees: the sensor's flip and mirror bits turn
    # it back (firmware/README.md).
    'U8': (0.0, 0.0, 180, B),
    'D2': (13.000, -0.000, 90, B),        # IR LED at 0 degrees (lens frame)
    'D3': (7.200, -12.471, 0, B),        # IR LED at 60 degrees (lens frame)
    'D4': (-7.200, -12.471, 0, B),        # IR LED at 120 degrees (lens frame)
    'D5': (-13.000, -0.000, 90, B),        # IR LED at 180 degrees (lens frame)
    'D6': (-7.200, 12.471, 0, B),        # IR LED at 240 degrees (lens frame)
    'D7': (7.200, 12.471, 0, B),        # IR LED at 300 degrees (lens frame)
    # the strings' 1206 resistors (not placed by the small-part placer) by
    # each string's first LED, clear of the rods' channels
    'R90': (17.0, 2.4, 0, B), 'R91': (-11.5, -14.8, 0, B), 'R92': (-11.5, 14.8, 0, B),
    'Q2': (0.0, 14.15, 0, B),         # light sensor under the front window
    'Q1': (-17.0, 6.0, 0, B),         # IR LED switch
    'J3': (17.6, -5.6, 270, B),       # IR-cut lead
    'U7': (16.4, 5.6, 0, B),          # IR-cut H-bridge
    'Y2': (-9.6, 17.6, 90, B),        # RTC crystal under the SoC's left side
    # mounting
    'H1': (G.SCREWS[0][0], -G.SCREWS[0][1], 0, F), 'H2': (G.SCREWS[1][0], -G.SCREWS[1][1], 0, F),
    'H3': (G.SCREWS[2][0], -G.SCREWS[2][1], 0, F), 'H4': (G.SCREWS[3][0], -G.SCREWS[3][1], 0, F),
    'H5': (G.HOLDER_SCREWS[0][0], -G.HOLDER_SCREWS[0][1], 0, F),
    'H6': (G.HOLDER_SCREWS[1][0], -G.HOLDER_SCREWS[1][1], 0, F),
}


def _usb_place():
    ex, ey = G.USB_EDGE_XY
    a = math.radians(G.USB_NORMAL_DEG)
    ux, uy = math.cos(a), -math.sin(a)            # the outward normal, board coordinates
    ox, oy = ex + (4.2 - 5.24) * ux, -ey + (4.2 - 5.24) * uy
    rot = math.degrees(math.atan2(ux, uy))        # the footprint's +y (its mouth) onto the normal
    return (round(ox, 3), round(oy, 3), round(rot, 2), F)


FIXED['J1'] = _usb_place()

# small parts that must sit at a particular part rather than the first IC
# their net reaches: note -> (ref, pad) of the pin they serve
ANCHOR = {
    '5 V bulk': ('U3', '10'),
    'VBUS detect top': ('U1', '25'), 'VBUS detect bottom': ('U1', '25'), 'VBUS detect filter': ('U1', '25'),
    '0.9 V buck input': ('U2', '4'), '0.9 V feedback top': ('U2', '5'), '0.9 V feedback bottom': ('U2', '5'),
    '0.9 V feed-forward': ('U2', '5'),
    '0.9 V output': ('L1', '2'),
    'triple buck input': ('U3', '10'), 'triple buck VCC': ('U3', '16'),
    '1.8 V / DDR enable delay R': ('U3', '8'), '1.8 V / DDR enable delay C': ('U3', '8'),
    '3.3 V enable delay R': ('U3', '9'), '3.3 V enable delay C': ('U3', '9'),
    '3.3 V feedback top': ('U3', '14'), '3.3 V feedback bottom': ('U3', '14'), '3.3 V output': ('L2', '2'),
    'DDR feedback top': ('U3', '3'), 'DDR feedback bottom': ('U3', '3'), 'DDR output': ('L3', '2'),
    '1.8 V feedback top': ('U3', '2'), '1.8 V feedback bottom': ('U3', '2'), '1.8 V output': ('L4', '2'),
    'Wi-Fi buck input': ('U4', '4'), 'Wi-Fi feedback top': ('U4', '5'), 'Wi-Fi feedback bottom': ('U4', '5'),
    'Wi-Fi buck output': ('L5', '2'),
    'core decoupling': ('U1', '*VDD_0V9'), 'core bulk': ('U1', '*VDD_0V9'),
    'DDR decoupling': ('U1', '*VCC_DDR'), 'DDR bulk': ('U1', '*VCC_DDR'),
    '1.8 V decoupling (DDR PLL, OSC/PLL)': ('U1', '*VCC_1V8'), '1.8 V decoupling (DDR PLL)': ('U1', '53'),
    '3.3 V decoupling (VCCIO, PMU, USB)': ('U1', '*VCC_3V3'), '3.3 V bulk at the SoC': ('U1', '43'),
    'MIPI supply filter R': ('U1', '1'), 'MIPI supply filter C': ('U1', '1'), 'MIPI supply bulk': ('U1', '1'),
    'ADC/USB supply filter R': ('U1', '24'), 'ADC/USB supply filter C': ('U1', '24'),
    'codec supply bead': ('U1', '31'), 'codec supply': ('U1', '31'), 'codec VCM': ('U1', '30'),
    'OTP/TSADC supply bead': ('U1', '96'), 'OTP/TSADC supply': ('U1', '96'),
    'Ethernet supply bead': ('U1', '101'), 'Ethernet supply': ('U1', '101'), 'Ethernet bias (PHY unused)': ('U1', '102'),
    'DRAM ZQ 240R 1 %': ('U1', '52'), 'RTC supply R': ('U1', '19'), 'RTC supply C': ('U1', '19'),
    '24 MHz drive R': ('Y1', '3'), '24 MHz load': ('Y1', '*'), '24 MHz bias': ('Y1', '1'),
    'RTC load': ('Y2', '*'),
    'nPOR pull-up': ('U1', '66'), 'nPOR delay': ('U1', '66'),
    'boot pull-up': ('U1', '23'), 'boot filter': ('U1', '23'), 'boot pad series R': ('TP5', '1'),
    'status LED R': ('LED1', '2'),
    'NAND clock series R': ('U1', '48'), 'NAND /WP pull-up': ('U5', '3'), 'NAND /HOLD pull-up': ('U5', '7'),
    'NAND decoupling': ('U5', '8'),
    'Wi-Fi supply bulk': ('U6', '3'), 'Wi-Fi supply HF': ('U6', '3'),
    'Wi-Fi EN pull-down': ('U6', '8'), 'Wi-Fi EN filter': ('U6', '8'),
    'Wi-Fi GPIO9 pull-up': ('U6', '23'), 'Wi-Fi GPIO8 pull-up': ('U6', '22'),
    'SDIO clock series R': ('U1', '15'), 'SDIO pull-up': ('U6', '*'), 'SDIO card-detect to ground': ('U1', '11'),
    'sensor LDO input': ('U9', '6'), 'sensor LDO output': ('U9', '1'),
    'sensor AVDD': ('U8', 'B1'), 'sensor AVDD HF': ('U8', 'B1'), 'sensor AVDD HF 2': ('U8', 'B7'),
    'sensor DOVDD filter R': ('U8', 'C2'), 'sensor DOVDD': ('U8', 'C2'), 'sensor DOVDD HF': ('U8', 'C3'),
    'sensor DVDD': ('U8', 'B4'), 'sensor DVDD HF': ('U8', 'C1'), 'sensor DVDD HF 2': ('U8', 'E4'),
    'sensor VREFN': ('U8', 'E7'), 'sensor VREFN2': ('U8', 'D7'),
    'sensor clock series R': ('U1', '2'), 'camera I2C pull-up': ('U1', '5'),
    'sensor XSHUTDN pull-down': ('U1', '3'), 'sensor PWDNB pull-down': ('U1', '4'),
    'IR-cut driver VM': ('U7', '1'), 'IR-cut driver VCC': ('U7', '8'),
    'IR LED gate R': ('Q1', '1'), 'IR LED gate pull-down': ('Q1', '1'),
    'IR LED supply': ('D2', '1'),
    'light sensor supply R': ('Q2', '3'), 'light sensor load': ('Q2', '1'), 'light sensor filter': ('Q2', '1'),
    'CC1 Rd': ('J1', 'A5'), 'CC2 Rd': ('J1', 'B5'), '5 V at the connector': ('J1', 'A4B9'),
    '5 V HF': ('J1', 'B4A9'),
}
for k in range(3):
    ANCHOR['string %d resistor' % (k + 1)] = ('D%d' % (2 * k + 2), '1')
# the side a small part goes on, where it is not the side of its anchor
SIDE = {
    'core decoupling': B, 'core bulk': B, 'DDR decoupling': B, 'DDR bulk': B,
    '1.8 V decoupling (DDR PLL, OSC/PLL)': B, '1.8 V decoupling (DDR PLL)': B,
    '3.3 V decoupling (VCCIO, PMU, USB)': B, '3.3 V bulk at the SoC': B,
    'MIPI supply filter C': B, 'MIPI supply bulk': B,
    'ADC/USB supply filter C': F, 'codec supply': F, 'codec VCM': F,
    'RTC supply C': B,
    'VBUS detect top': B, 'VBUS detect bottom': B, 'VBUS detect filter': B, '24 MHz drive R': B,
    'ADC/USB supply filter R': B,
    'OTP/TSADC supply': B, 'Ethernet supply': B, 'DRAM ZQ 240R 1 %': B,
    '24 MHz load': F, 'RTC load': B, 'SDIO pull-up': B,
    # the sensor's decoupling on its own face, inside the holder's recess
    'sensor DOVDD filter R': B,
    # the 0.9 V output capacitor under its buck on the front face: on the
    # back, the heatsink's footprint and the buck fill the strip
    '0.9 V output': B,
}

CLEAR = 0.15          # courtyard to courtyard


def _core_band():
    """Under the SoC on B, between its exposed pad's vias and its pins'
    vias: where the 0.9 V decoupling goes (both its pads reach a plane via
    within a millimetre: 0.9 V inwards of the pins, ground in the pad)."""
    from shapely.geometry import box
    cx, cy = FIXED['U1'][:2]
    return box(cx - 4.75, cy - 4.75, cx + 4.75, cy + 4.75).difference(box(cx - 2.75, cy - 2.75, cx + 2.75, cy + 2.75))


def _strip():
    """The 0.9 V plane's strip out to the buck, less a margin: the output
    and bulk capacitors go here, over their plane."""
    return plane_polys()['VDD_0V9'].difference(_core_box(6.6)).buffer(-0.3)


def _core_box(h):
    from shapely.geometry import box
    cx, cy = FIXED['U1'][:2]
    return box(cx - h, cy - h, cx + h, cy + h)


def _outside_core():
    """B round the SoC, outside its 0.9 V plane: decoupling whose supply
    via must reach the 3.3 V plane, or a routed rail."""
    from shapely.geometry import box
    cx, cy = FIXED['U1'][:2]
    return pcb.board_polygon().difference(box(cx - 6.6, cy - 6.6, cx + 6.6, cy + 6.6))


REGION = {
    'core decoupling': _core_band, 'core bulk': lambda: _core_band().union(_strip()),
    '0.9 V output': lambda: _strip(),
    '3.3 V decoupling (VCCIO, PMU, USB)': _outside_core, '3.3 V bulk at the SoC': _outside_core,
    'DDR decoupling': _outside_core, 'DDR bulk': _outside_core,
    '1.8 V decoupling (DDR PLL, OSC/PLL)': _outside_core, '1.8 V decoupling (DDR PLL)': _outside_core,
}


BREAKOUT = 8.4        # half-width of the SoC's part-free breakout band (back face)


def via_ring():
    """The SoC's escape band, from its pads' outer ends to the part-free
    band's edge: only the SoC's own pins put plane vias here.  The back
    face's decoupling caps under it had put 38 there, a wall the signal
    pins could not get through to their vias."""
    cx, cy = FIXED['U1'][:2]
    return (box(cx - BREAKOUT, cy - BREAKOUT, cx + BREAKOUT, cy + BREAKOUT)
            .difference(box(cx - 6.0, cy - 6.0, cx + 6.0, cy + 6.0)), {'U1'})


# J3's contact 2 has contact 1 on one side and the connector's two tabs on
# the others: no way out on B, so it drops straight through to In2
PAD_VIAS = [('J3', '2')]


def escapes(b):
    """The SoC's signal pins that leave its face: a pin whose nearest other
    pad is on the back face, or whose net runs more than 20 mm.  The rest
    run out on F through the breakout band."""
    import pcbnew, board
    skip = set(board.PLANE_NETS['main']) | {n for v in board.DIFF['main'].values() for n in v[0]}
    pads = {}
    for fp in b.GetFootprints():
        for q in fp.Pads():
            pads.setdefault(q.GetNetname(), []).append((fp.GetReference(), q))
    out = set()
    for p in b.FindFootprintByReference('U1').Pads():
        n = p.GetNetname()
        if not n or n in skip or n.startswith('unconnected'):
            continue
        x, y = pcb.xy(p.GetPosition())
        near = sorted((math.dist((x, y), pcb.xy(q.GetPosition())), q.IsOnLayer(pcbnew.F_Cu))
                      for r, q in pads[n] if r != 'U1')
        if near and (not near[0][1] or near[0][0] > 20):
            out.add(n)
    return {'U1': sorted(out)}


# The SoC's 0.35 mm-pitch pins: their escape (and plane) vias 0.35 / 0.2 mm
# with 0.1 mm stubs.  With the board's 0.45 mm vias two escapes a pin apart
# (0.7 mm) left 0.25 mm between them, no room for the pin in the middle; at
# 0.35 mm a 0.1 mm stub passes with 0.125 mm each side.  0.126 mm keeps the
# 0.2 mm copper-to-hole rule (0.075 mm ring + 0.125); in the band the gap
# rule is PCBWay's 6-layer floor, 0.1 mm (pcb.ESCAPE_RULE).
ESCAPE = dict(ref='U1', via=(0.35, 0.2), clr=0.126, w=0.1)


SENSOR_BAND = (-2.7, -2.4, 2.7, 2.7)    # round the image sensor's balls: its escape stubs and vias


def sensor_area():
    """Where the sensor's escape clearance (0.1 mm) applies."""
    return box(*SENSOR_BAND)


def escape_area():
    """Where the 0.1 mm escape-band clearance applies: the SoC's pins and
    the band round them."""
    cx, cy = FIXED['U1'][:2]
    return box(cx - BREAKOUT, cy - BREAKOUT, cx + BREAKOUT, cy + BREAKOUT)


# the IR-cut holder's base covers HOLDER_BOX on the front face; inside it,
# round the sensor, a recess for the sensor and its 0402 decoupling (the
# holder's drawing gives no recess size: kept to the sensor's surroundings,
# parts 0.6 mm or lower, verify.py)
RECESS = (-5.6, -4.4, 5.6, 4.4)
UNDER_HOLDER_MAX_H = 0.6


def keepouts(side):
    """Areas a part on `side` may not touch: (shapely geometry, max height
    allowed there or 0)."""
    out = []
    if side == F:
        for x, y in G.HOLDER_SCREWS:
            out.append((Point(x, -y).buffer(1.95), 0))     # the screw heads
        # the SoC's breakout band: no part within 1.8 mm outside its pins
        cx, cy = FIXED['U1'][:2]
        out.append((box(cx - BREAKOUT, cy - BREAKOUT, cx + BREAKOUT, cy + BREAKOUT)
                    .difference(box(cx - 6.5, cy - 6.5, cx + 6.5, cy + 6.5)), 0))
        # the triple buck's breakout band
        ux, uy = FIXED['U3'][:2]
        out.append((box(ux - 2.9, uy - 2.9, ux + 2.9, uy + 2.9).difference(box(ux - 1.95, uy - 1.95, ux + 1.95, uy + 1.95)), 0))
        hw, hh = G.HEATSINK[0] / 2 + 0.2, G.HEATSINK[1] / 2 + 0.2
        out.append((box(cx - hw, cy - hh, cx + hw, cy + hh), G.UNDER_HEATSINK_MAX_H))
    else:
        x0, y0, x1, y1 = G.HOLDER_BOX
        holder = box(x0, -y1, x1, -y0)
        rx0, ry0, rx1, ry1 = RECESS
        recess = box(rx0, ry0, rx1, ry1)
        out.append((holder.difference(recess), 0))
        out.append((recess, UNDER_HOLDER_MAX_H))
        # the SoC's escape band on the front face too
        out.append((via_ring()[0], 0))
        for x, y in G.SCREWS:
            out.append((Point(x, -y).buffer(G.BOSS_D / 2 + 0.3), 0))
        # the light rods' channels in the case reach down round each LED
        for a in G.LED_ANGLES:
            lx, ly = G.led_xy(a)
            out.append((Point(lx, -ly).buffer(2.6).difference(box(lx - 2.4, -ly - 1.6, lx + 2.4, -ly + 1.6)), 0))
    for x, y in G.SCREWS:
        out.append((Point(x, -y).buffer(2.15), 0))
    return out


def height(part):
    """Body height above the board, mm (the 0402 R/C are 0.35-0.5)."""
    import parts
    fp = (parts.PARTS.get(part) or parts.PADS.get(part))['fp']
    return 0.5 if '0402' in fp else 1.0


def placement(comps, fps_crt):
    """ref -> (x, y, rot, side) for every part.  fps_crt(part, rot) gives a
    part's courtyard (shapely, around its origin)."""
    out = dict(FIXED)
    return out


# ---------------------------------------------------------------- planes
# In3 carries two planes: 0.9 V inside the SoC's pin ring (its core pins
# take their vias inwards, between the pins and the exposed pad) with a
# strip out to the 0.9 V buck below-right, and 3.3 V everywhere else.
SOC = FIXED['U1'][:2]
CORE_HALF = 5.85                  # to the pin ring's middle: the 3.3 V pins' vias sit outside it
# the strip out to the buck: from the SoC's right side below its 3.3 V
# pins there (81 and 88, above the centre) out to the buck and its
# inductor below-right
STRIP = (19.6, 4.6, 8.0)          # x1, then y0 / y1 from the SoC's centre


def plane_polys():
    from shapely.geometry import box
    cx, cy = SOC
    core = box(cx - CORE_HALF, cy - CORE_HALF, cx + CORE_HALF, cy + CORE_HALF)
    # the strip from the SoC's right side out to the buck's inductor and
    # output capacitors, and under the buck (its feedback network's 0.9 V
    # end takes a via to this plane)
    x1, y0, y1 = STRIP
    strip = box(cx + CORE_HALF, cy + y0, x1, cy + y1).union(box(cx + 10.5, cy + 3.6, x1, cy + 10.0))
    v09 = core.union(strip).intersection(pcb.board_polygon().buffer(-0.4))
    v33 = pcb.board_polygon().buffer(-0.4).difference(v09.buffer(0.4))
    return {'VDD_0V9': v09, 'VCC_3V3': v33, 'GND': pcb.board_polygon()}


def zones(b):
    import pcbnew
    full = pcb.board_polygon().buffer(-0.3)
    for lay, name in ((pcbnew.In1_Cu, 'GND plane In1'), (pcbnew.In4_Cu, 'GND plane In4')):
        for g in (getattr(full, 'geoms', None) or [full]):
            z = _zone_shape(b, 'GND', lay, g, name, 0)
    pp = plane_polys()
    _zone_shape(b, 'VDD_0V9', pcbnew.In3_Cu, pp['VDD_0V9'], '0.9 V plane', 2)
    for g in (getattr(pp['VCC_3V3'], 'geoms', None) or [pp['VCC_3V3']]):
        _zone_shape(b, 'VCC_3V3', pcbnew.In3_Cu, g, '3.3 V plane', 1)
    # the exposed pad: a 5 x 5 grid of filled, capped vias to the ground planes
    cx, cy = SOC
    for i in range(5):
        for j in range(5):
            pcb.via(b, cx - 2.4 + 1.2 * i, cy - 2.4 + 1.2 * j, 'GND')


def _zone_shape(b, net, layer, g, name, prio):
    import pcbnew
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(pcb.add_net(b, net))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in list(g.exterior.coords)[:-1]:
        ol.Append(pcb.MM(pcb.CX + x), pcb.MM(pcb.CY + y))
    for h in g.interiors:
        ol.NewHole()
        for (x, y) in list(h.coords)[:-1]:
            ol.Append(pcb.MM(pcb.CX + x), pcb.MM(pcb.CY + y), 0, 0)
    z.SetLocalClearance(pcb.MM(0.2))
    z.SetMinThickness(pcb.MM(0.15))
    z.SetAssignedPriority(prio)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName(name)
    b.Add(z)
    return z

# fanout: these (part, net) pads put their via towards the part's centre
INWARD = {('U1', 'VDD_0V9')}
