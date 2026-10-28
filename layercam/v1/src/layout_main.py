# -*- coding: utf-8 -*-
"""Where every part of the main board goes.

Board millimetres, origin on the lens axis, x right, y down the screen,
seen from BEHIND the camera (KiCad's top, F = the board's back face, which
faces the lid).  y = -Y of the lens frame (geometry.py).

    F (back)   the camera module covers the middle (25 x 24, 1 mm above
               the board: only 0402 parts under it); the RV1106 below it,
               the power stage to its right, the flash to its left; the
               camera FFC connector above it; the USB cable on the left
    B (front)  the IR-cut holder covers the middle; the Wi-Fi module above
               it (in the tab), the LED ring and IR-cut connectors and
               their drivers at the sides, the SoC's decoupling under it

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
# ref -> (x, y, rot, side)
FIXED = {
    # F, the back face
    'U1': (0.0, 19.4, 0, F),          # RV1106G3: MIPI (top row, left) towards the camera FFC
    # camera FFC: opening towards +y, 2.3 mm short of the module's edge (the
    # cable drops 2.3 mm from the module's connector to this one); centred
    # on the lens axis like the module's, so pin k is in line with pin k
    'J2': (0.0, -20.8, 0, F),
    'J1': (-16.4, -2.0, 90, F),       # USB cable from the USB board (on the case's -X side)
    'U5': (-15.8, -11.3, 90, F),      # SPI NAND, left of the camera module, above J1
    # the power stage in the strip right of the camera module
    'U3': (15.7, 0.6, 90, F),         # triple buck
    'L2': (15.9, -4.2, 0, F),         # 3.3 V
    'L3': (15.9, 5.2, 0, F),          # DDR
    'L4': (15.9, 8.6, 0, F),          # 1.8 V
    'U2': (-9.4, 25.0, 90, F),         # 0.9 V buck, below-left of the SoC
    'L1': (-12.3, 21.3, 270, F),   # switch end next to U2's SW pin
    'U4': (11.8, -18.3, 0, F),        # Wi-Fi buck, top right, clear of the camera module
    'L5': (16.0, -14.4, 90, F),
    'Y1': (9.6, 22.2, 90, F),         # 24 MHz at the SoC's OSC pins (68/69, right side)
    'LED1': (8.8, 14.0, 0, F),        # status, in the lid's vent window
    # test pads, clear of the SoC's breakout band: the console's TX RX G
    # for a 3.3 V USB-serial lead and BOOT beside G for tweezers, in the
    # round edge's right corner; 5V on its own in the left one
    'TP1': (9.2, 25.3, 0, F), 'TP2': (10.8, 25.1, 0, F), 'TP3': (12.4, 24.8, 0, F), 'TP5': (14.0, 24.3, 0, F),
    'TP4': (-13.6, 25.2, 0, F),
    # B, the front face
    'U6': (0.0, -16.4, 0, B),         # AP6256 between the lens holder and the top edge (in the tab)
    # round the AP6256 (U6, on B, mirrored: its antenna pin 2 at (-5.9,
    # -12.8), crystal pins 10/11 at (-5.9, -20.0 / -20.9), buck pins 21 / 23
    # at (3.6, -22.3) / (5.9, -20.9), sleep clock pin 24 at (5.9, -20.0))
    'Y3': (-9.1, -20.45, 180, B),     # 37.4 MHz: pad 1 by pin 10, pad 3 round to pin 11
    'L6': (8.6, -20.6, 90, B),        # Wi-Fi internal buck inductor, by pins 21 and 23
    'Y4': (9.8, -16.6, 90, B),        # 32.768 kHz oscillator, by pin 24
    # the antenna feed: pin 2 -> shunt C90 -> series R90 -> shunt C91 -> J5,
    # in a line along y -12.8 (pairs.py draws the 50 ohm track)
    'C90': (-7.7, -13.31, 90, B),
    'R90': (-9.2, -12.8, 180, B),
    'C91': (-10.65, -13.31, 90, B),
    'J5': (-12.8, -12.8, 270, B),     # U.FL, its signal pin towards U6
    'J4': (-16.0, 3.0, 90, B),        # LED ring cable (the ring's connector is behind it)
    'Q1': (-15.6, 10.6, 0, B),        # IR LED switch
    'J3': (15.9, 3.0, 270, B),        # IR-cut lead (the CLA219's motor is on this side)
    'U7': (15.0, 10.4, 0, B),         # IR-cut H-bridge
    'Y2': (-9.6, 21.0, 90, B),        # RTC crystal under the SoC's left side
    # mounting
    'H1': (G.SCREWS[0][0], -G.SCREWS[0][1], 0, F), 'H2': (G.SCREWS[1][0], -G.SCREWS[1][1], 0, F),
    'H3': (G.SCREWS[2][0], -G.SCREWS[2][1], 0, F), 'H4': (G.SCREWS[3][0], -G.SCREWS[3][1], 0, F),
    'H5': (G.HOLDER_SCREWS[0][0], -G.HOLDER_SCREWS[0][1], 0, F),
    'H6': (G.HOLDER_SCREWS[1][0], -G.HOLDER_SCREWS[1][1], 0, F),
}

# small parts that must sit at a particular part rather than the first IC
# their net reaches: note -> (ref, pad) of the pin they serve
ANCHOR = {
    '5 V bulk': ('J1', '1'), '5 V HF': ('J1', '1'),
    'VBUS detect top': ('U1', '25'), 'VBUS detect bottom': ('U1', '25'), 'VBUS detect filter': ('U1', '25'),
    '0.9 V buck input': ('U2', '4'), '0.9 V feedback top': ('U2', '5'), '0.9 V feedback bottom': ('U2', '5'),
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
    'Wi-Fi VBAT bulk': ('U6', '9'), 'Wi-Fi VBAT HF': ('U6', '9'), 'Wi-Fi VDDIO': ('U6', '22'),
    'Wi-Fi internal buck output': ('U6', '23'), '37.4 MHz load': ('Y3', '*'),
    '32 kHz oscillator supply': ('Y4', '4'),
    'SDIO clock series R': ('U1', '15'), 'SDIO pull-up': ('U6', '*'), 'SDIO card-detect to ground': ('U1', '11'),
    'WL_REG_ON pull-down': ('U6', '12'), 'BT_REG_ON pull-down': ('U6', '34'),
    'antenna match shunt 1 (empty)': ('U6', '2'), 'antenna match series': ('J5', '1'),
    'antenna match shunt 2 (empty)': ('J5', '1'),
    'sensor clock series R': ('U1', '2'), 'camera I2C pull-up': ('U1', '5'),
    'camera supply': ('J2', '*VCC_3V3'),
    'IR-cut driver VM': ('U7', '1'), 'IR-cut driver VCC': ('U7', '8'),
    'IR LED gate R': ('Q1', '1'), 'IR LED gate pull-down': ('Q1', '1'),
    'light sensor supply R': ('J4', '3'), 'light sensor load': ('J4', '4'), 'light sensor filter': ('J4', '4'),
    'IR LED supply': ('J4', '1'),
}
# the side a small part goes on, where it is not the side of its anchor
SIDE = {
    'core decoupling': B, 'core bulk': B, 'DDR decoupling': B, 'DDR bulk': B,
    '1.8 V decoupling (DDR PLL, OSC/PLL)': B, '1.8 V decoupling (DDR PLL)': B,
    '3.3 V decoupling (VCCIO, PMU, USB)': B, '3.3 V bulk at the SoC': B,
    'MIPI supply filter C': B, 'MIPI supply bulk': B,
    # the SoC's left-column filter caps on its own face: a via each beside
    # pins 19-30 had no room among the plane and USB vias there
    'ADC/USB supply filter C': F, 'codec supply': F, 'codec VCM': F, 'RTC supply C': F,
    # on the back face, their SoC pin reaching them by its escape via: on
    # the front they sat boxed in by the 0.9 V buck and by the crystal
    'VBUS detect top': B, 'VBUS detect bottom': B, 'VBUS detect filter': B, '24 MHz drive R': B,
    'OTP/TSADC supply': B, 'Ethernet supply': B, 'DRAM ZQ 240R 1 %': B,
    '24 MHz load': F, 'RTC load': B, 'SDIO pull-up': B,
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


def keepouts(side):
    """Areas a part on `side` may not touch: (shapely geometry, max height
    allowed there or 0)."""
    out = []
    ww, wh = G.WINDOW
    out.append((box(-ww / 2, -wh / 2, ww / 2, wh / 2).buffer(0.3), 0))
    if side == F:
        mw = G.MODULE_W / 2 + 0.15
        # board y = -Y: the connector edge is at -y
        out.append((box(-mw, -G.MODULE_TO_FFC_EDGE - 0.15, mw, G.MODULE_TO_FAR_EDGE + 0.15),
                    G.UNDER_MODULE_MAX_H))
        for x, y in G.HOLDER_SCREWS:
            out.append((Point(x, -y).buffer(1.95), 0))     # the nylon washers
        # the SoC's breakout band: no part within 1.8 mm outside its pins,
        # so the router has room to bring 0.35 mm-pitch pins out to vias
        cx, cy = FIXED['U1'][:2]
        out.append((box(cx - BREAKOUT, cy - BREAKOUT, cx + BREAKOUT, cy + BREAKOUT)
                    .difference(box(cx - 6.5, cy - 6.5, cx + 6.5, cy + 6.5)), 0))
        # the triple buck's breakout band: its 0.4 mm-pitch pins need room
        # between their pads and the input / enable caps
        ux, uy = FIXED['U3'][:2]
        out.append((box(ux - 2.9, uy - 2.9, ux + 2.9, uy + 2.9).difference(box(ux - 1.95, uy - 1.95, ux + 1.95, uy + 1.95)), 0))
        hx, hy = G.HEATSINK_C
        h = G.HEATSINK_SIZE / 2 + 0.2
        out.append((box(hx - h, hy - h, hx + h, hy + h), G.UNDER_HEATSINK_MAX_H))
    else:
        x0, y0, x1, y1 = G.HOLDER_BOX
        out.append((box(x0, -y1, x1, -y0), 0))
        # the SoC's escape band on the back face too: its pins' vias come
        # through here, and a part's pad would stand where a via must go
        out.append((via_ring()[0], 0))
        for x, y in G.SCREWS:
            out.append((Point(x, -y).buffer(G.BOSS_D / 2 + 0.3), 0))
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
# strip out to the 0.9 V buck, and 3.3 V everywhere else.
SOC = FIXED['U1'][:2]
CORE_HALF = 5.85                  # to the pin ring's middle: the 3.3 V pins' vias sit outside it
# the strip out to the buck, left of the SoC between its two 3.3 V pins on
# that side (13 and 28), whose outward vias stay in the 3.3 V plane
STRIP = (-14.3, -0.45, 3.25)      # x0, then y0 / y1 from the SoC's centre


def plane_polys():
    from shapely.geometry import box
    cx, cy = SOC
    core = box(cx - CORE_HALF, cy - CORE_HALF, cx + CORE_HALF, cy + CORE_HALF)
    # the strip from the SoC's left side out to the buck's inductor and
    # output capacitors
    x0, y0, y1 = STRIP
    strip = box(x0, cy + y0, cx - CORE_HALF, cy + y1).union(box(-15.5, cy - 6.5, cx - 8.0, cy + 5.0))
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
