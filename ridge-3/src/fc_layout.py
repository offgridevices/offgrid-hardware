# -*- coding: utf-8 -*-
"""Ridge 3 flight controller (36 x 36 mm, 25.5 mm slotted holes):
placement, power copper, planes and silkscreen.

Double-sided assembly.  Top: MCU, gyro, flash, OSD and both crystals,
connectors, solder pads, LEDs, the boot button and the video battery's
clamp.  Bottom: the three switching supplies (5 V at the rear, 9 V on the
right, 3.3 V at the front left), the video supply's thermostat and the
USB-C's VBUS diode and CC resistors.  Front of the quad is -y (top of
every plot).  USB-C faces LEFT, as in v1; the ESC lead leaves from the
rear.

Power: two battery inputs (circuit.fc_power).  The ESC lead's pin 1 feeds
the 5 V BEC: a top pour behind the lead's pins, vias down to the BEC's
input pour.  The P_BAT pad feeds only the 9 V video BEC: a top pour to its
clamp and input capacitor, vias down to its input pour.  Each BEC's input
capacitor, IC and inductor sit together on the bottom with their switch
node, input and ground as pours (routers kept out of them).  5 V and 9 V
leave their BECs as pours; the rest of their nets is routed at 0.4 and
0.3 mm.

Stackup (6 layers): F.Cu signals | In1 solid GND | In2 signals | In3
signals | In4 solid 3.3 V | B.Cu signals, parts and the supplies' copper.
On 4 layers (LAYERS = 4) the routers left 28 nets unfinished: the MCU,
OSD, flash and gyro share 36 mm with two switching supplies and 30 edge
pads.
"""
import math
import pcbnew
import pcb, circuit
from pcb import MM

PRODUCT = 'Ridge 3'
FIRMWARE = 'RIDGE3'              # the Betaflight build to flash (firmware/)
# the board's revision, printed by a corner and kept in the title block;
# each board keeps its own (a change to one board moves only its number)
REVISION = '2.0'

T, Bo = 'T', 'B'
PE = 16.8                        # edge solder pads: centre distance from the board centre

# Anchors: the three buck ICs.  Their passives and pours are placed relative
# to them.
A5 = (-3.0, 11.9)                # U_BUCK5, rot 180, bottom: VIN/GND pins rear, SW front right
A9 = (13.0, 4.0)                 # U_BUCK9, rot 180, bottom: as U_BUCK5, VIN/GND/EN rear, SW front right
A3 = (-8.9, -6.4)                # U_BUCK3 (3.3 V), bottom front left, beside the flag


def at(a, dx, dy, rot, side=Bo):
    return (round(a[0] + dx, 3), round(a[1] + dy, 3), rot, side)


# ref: (x, y, rotation, side).  Parts named here by reference.
PLACE = {
    # MCU at 0 deg.  Its pins, by side:
    #   rear  (1-12)  crystal, NRST, MOTOR1-4, gyro INT      -> ESC lead
    #   right (13-24) SPI1 gyro, ADC, VDDA/VREF, TLM         -> gyro
    #   front (25-36) SPI2 flash + OSD, UART1, USB, SWDIO     -> flash, OSD, USB
    #   left  (37-48) SWCLK, UART4, UART2, VTX switch,
    #                 LED strip, LED0, BOOT0                  -> left pads
    'U_FC':    (-1.0, 1.1, 0, T),
    # gyro right of the MCU, rotation fixed at 90 (circuit.py: firmware GYRO_1_ALIGN CW0)
    'U_IMU':   (5.2, 2.2, 90, T),
    # OSD in front of the MCU: SPI towards it, video towards the front pads
    'U_OSD':   (-1.0, -8.8, 0, T),
    'U_FLASH': (6.75, -8.6, 0, T),
    # the crystal left of the stack lead's corridor (KEEP_FREE), its pins
    # (5, 6) at the corridor's left edge
    'Y1':      (-5.3, 7.6, 90, T),
    'Y2':      (-8.1, -6.6, 270, T),
    # the USB-C's mouth at the board's edge: GCT's USB4105 drawing puts the
    # PCB edge 2.60 mm in front of the front shell tabs, which sit 2.38 mm
    # in front of the footprint's origin (a plug's overmould hangs below
    # the board's top, and an edge proud of the mouth would stop it short)
    'J_USB':   (-pcb.HALF + 2.38 + 2.60, 0.0, 270, T),
    # ESD array diagonally in front of the MCU's left pins: D- on its
    # left column, D+ on its right, so the two lines leave its front row
    # nested, D- outside, towards pins 33/34
    'U_ESD':   (-6.8, -3.6, 180, T),
    # under the USB-C (bottom): VBUS diode
    'D_USB':   (-13.2, 1.3, 180, Bo),
    'J_ESC':   (-2.3, 14.6, 0, T),
    'P_BATG':  (6.0, 16.2, 0, T),
    'P_BAT':   (8.5, 16.2, 0, T),
    'J_HD':    (15.4, -4.5, 90, T),
    'SW_BOOT': (15.9, 6.0, 90, T),
    'SJ_SBUS': (12.0, -8.0, 90, T),
    'LED_STAT': (-7.0, 6.0, 0, T),
    'LED_PWR':  (13.2, 5.0, 90, T),
    'FB_OSD':  (-7.0, -9.5, 90, T),
    # SWD (debugging only: the FC flashes over USB) on the bottom, left of
    # the name band, near the MCU's SWD pins; reset on top
    'TP_SWDIO': (-9.0, -1.6, 0, Bo), 'TP_SWCLK': (-9.0, -0.2, 0, Bo), 'TP_NRST': (-5.3, 10.4, 0, T),
    # ---- solder pads.  Left edge: receiver at the front, LED strip at the rear.
    'P_RX5V': (-PE, -10.3, 90, T), 'P_RXG': (-PE, -8.8, 90, T),
    'P_R2':   (-PE, -7.3, 90, T),  'P_T2':  (-PE, -5.8, 90, T),
    'P_5V':   (-PE, 6.4, 90, T), 'P_G1': (-PE, 7.9, 90, T), 'P_LED': (-PE, 9.4, 90, T),
    # front edge: UART4, then the analog video pads under the OSD's video
    # pins (VTX left of the camera, as VOUT is left of VIN), then UART1
    'P_T4':    (-10.0, -PE, 0, T), 'P_R4': (-8.5, -PE, 0, T),
    'P_VTX9V': (-6.8, -PE, 0, T), 'P_VTXG': (-5.3, -PE, 0, T), 'P_VTX': (-3.8, -PE, 0, T),
    'P_CAM':   (-2.3, -PE, 0, T), 'P_CAMG': (-0.8, -PE, 0, T), 'P_CAM5V': (0.7, -PE, 0, T),
    'P_T1':    (6.5, -PE, 0, T), 'P_R1': (8.0, -PE, 0, T),
    # ---- bottom, 9 V BEC on the right: its SW pin (front right) at the
    # inductor's near end in front of it, VIN/GND (rear) at the input
    # capacitors
    'U_BUCK9': at(A9, 0, 0, 180),
    'L_9V':    at(A9, 0.3, -8.8, 90),
    # ---- bottom, 5 V BEC at the rear: IC and inductor side by side, the
    # IC's SW pin (front right) at the inductor's front end, its VIN/GND
    # pins (rear) at the input capacitor
    'U_BUCK5': at(A5, 0, 0, 180),
    'L_5V':    at(A5, 6.15, -0.3, 270),
    # ---- bottom front left: the 3.3 V buck and its inductor
    'U_BUCK3': at(A3, 0, 0, 90),
    'L_3V3':   at(A3, 3.03, 0, 180),          # its SW end (pad 1) at the IC's SW pin
    # ---- mounting
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, T), 'H2': (pcb.HOLE, -pcb.HOLE, 0, T),
    'H3': (pcb.HOLE, pcb.HOLE, 0, T),   'H4': (-pcb.HOLE, pcb.HOLE, 0, T),
}
# Passives, by their circuit.py note; a list for notes that repeat (in
# circuit order).
PLACE_BY_NOTE = {
    # the lead's battery: its clamp on the bottom behind the 5 V BEC, its
    # anode end in the BEC's input pour, its ground end outboard of it,
    # far enough out that its courtyard clears the IC's at the RT pin's
    # corner
    'VBAT TVS':             (-8.1, 16.6, 180, Bo),
    # the video supply's own input (fpv group): its clamp and bulk
    # capacitor in front of its pads, the clamp's ground end clear of the
    # pads' courtyards
    'VBAT_VTX TVS':         (7.0, 12.45, 270, T),
    # current and battery-voltage dividers and filters: right front, clear
    # of the gyro
    'CUR default low':      (10.6, -3.4, 0, T),
    'CUR RC filter':        [(10.6, -2.4, 0, T), (10.6, -1.4, 0, T)],
    'VBAT divider top':     (12.4, -3.4, 0, T),
    'VBAT divider bottom':  (12.4, -2.4, 0, T),
    'VBAT filter':          (12.4, -1.4, 0, T),
    # 5 V BEC: hot loop (input capacitor, IC, bootstrap) fixed to the IC
    '5V BEC input HF':      at(A5, 0.63, 4.55, 0),
    '5V BEC bootstrap':     at(A5, 1.27, -4.5, 0),
    '5V BEC input':         at(A5, -4.4, -0.9, 90),
    '5V BEC 455 kHz':       at(A5, -3.5, 2.5, 90),
    '5V BEC output':        [(8.1, 10.3, 90, Bo), (8.1, 15.05, 90, Bo)],
    '5V BEC feedback top':  at(A5, -2.4, -4.5, 0),
    '5V BEC feedback bottom': at(A5, -2.4, -5.5, 0),
    # 9 V BEC, as the 5 V one (relative to A9, IC turned 180: rear row x
    # +1.9 GND, +0.63 EN, -0.63 VIN, -1.9 RT at +2.68; front row +1.9 SW,
    # +0.63 CB, -0.63 PG, -1.9 FB at -2.68): input HF capacitor behind
    # the rear row, across EN from VIN's pour to GND's, bulk input
    # capacitor above it on the top, bootstrap in front of CB/SW, between
    # the IC and the inductor; RT's resistor in line with its pin, past the
    # end of the IC's courtyard (2.59 mm from its centre along the rows),
    # the UVLO divider beside it (EN, boxed in between VIN and GND, leaves
    # its pin by a via in the pad, vias())
    '9V BEC input HF':      at(A9, 0.63, 4.45, 0),
    '9V BEC input':         (12.0, 7.9, 0, T),
    '9V BEC bootstrap':     at(A9, 1.3, -4.3, 0),
    '9V BEC 455 kHz':       at(A9, -3.65, 2.68, 180),
    '9V BEC UVLO top':      at(A9, -2.65, 4.9, 90),
    '9V BEC UVLO bottom':   (9.61, 5.08, 90, Bo),
    'VTX power switch':     (11.8, 4.3, 0, T),      # clear of the EN via above U_BUCK9's pin 2
    'VTX switch gate':      (10.0, 3.4, 90, T),
    'VTX switch gate pulldown': (10.0, 5.4, 90, T),
    # the thermostat on the bottom beside the 9 V BEC, the board's warmest
    # part, its inverter and cutoff at the IC's EN side
    'video supply thermostat': (9.3, 1.8, 90, Bo),
    'thermostat 96 C':      (7.72, 1.78, 90, Bo),
    'thermostat supply':    (8.03, 3.77, 180, Bo),
    'thermostat inverter and cutoff': (7.07, 5.94, 90, Bo),
    'thermostat inverter pullup': (4.77, 6.28, 90, Bo),
    'thermostat output pullup': (3.7, 6.28, 90, Bo),
    # the rear one's ground end over the 9 V pour's front edge, the front
    # one's under the flash (its via between the flash's pins, vias())
    '9V BEC output':        [(8.1, -5.4, 270, Bo), (8.1, -10.1, 90, Bo)],
    # the feedback divider beside the FB pin (the inductor in front of it)
    '9V BEC feedback top':  (9.28, -0.23, 0, Bo),
    '9V BEC feedback bottom': (9.27, -1.83, 270, Bo),
    # 3.3 V buck: input capacitor at VIN/GND, the inductor beside the SW
    # pin, output capacitors at the inductor's far end, feedback at FB
    # (IC turned 90: VIN/EN/MODE and COMP (ground) down its left side,
    # GND, SW, PG, FB down its right; VIN and GND at its rear end).  The
    # input capacitor sits right of the IC's centre line: the USB-C's
    # front shell tab is a plated hole, its copper on the bottom too, just
    # left of the capacitor's 5 V end.  The output capacitors sit in front
    # of the inductor's courtyard.
    '3.3V buck input':      at(A3, 0.55, 2.25, 0),
    '3.3V buck output':     [at(A3, 3.9, -2.8, 90), at(A3, 5.45, -2.8, 90)],
    '3.3V buck feedback top': at(A3, -1.9, -1.6, 90),
    '3.3V buck feed-forward': at(A3, -2.9, -1.6, 90),
    '3.3V buck feedback bottom': at(A3, -1.3, -3.4, 0),
    # MCU decoupling, in line with its own supply pin
    # (pin 35's under the MCU's front-left corner, on the bottom: the
    # strip in front of the MCU stays free for its front pins' lines)
    'U_FC pin 1 VBAT':      (-3.75, 5.8, 90, T),
    'U_FC pin 23 VDD':      (3.9, -1.15, 0, T),
    'U_FC pin 35 VDD':      (-4.4, -3.9, 0, Bo),
    'U_FC pin 48 VDD':      (-5.7, 3.85, 0, T),
    'U_FC pin 20/21 VREF+/VDDA': (3.9, -0.15, 0, T),
    'U_FC VDDA bulk':       (5.6, -0.6, 0, T),
    'U_FC bulk':            (-5.7, 4.9, 0, T),
    'U_FC reset filter':    (-0.75, 5.9, 90, T),
    'crystal load':         [(-7.3, 7.6, 90, T), (-3.5, 7.6, 90, T)],
    'BOOT0 pulldown':       (-5.7, 2.85, 0, T),
    # gyro filter and decoupling, at its supply pins (right and front)
    'gyro supply filter':   (8.6, 2.2, 90, T),
    'gyro VDD bulk':        (9.6, 2.2, 90, T),
    'gyro VDD':             (7.4, 2.6, 90, T),
    'gyro VDDIO':           (6.2, 0.1, 0, T),
    # flash; the chip-select pull-ups on the bottom, the strip in front of
    # the MCU stays free
    'flash':                (4.2, -13.0, 0, T),
    'flash CS pullup':      (3.45, -10.9, 90, Bo),
    'OSD CS pullup':        (2.3, -10.9, 90, Bo),
    # OSD: supply filter at its rear-left, decoupling and the video parts
    # on the bottom under its front pins, so the pads' labels keep the
    # band between it and the front edge
    'OSD bulk':             (-8.2, -11.0, 90, T),
    'OSD DVDD':             (-6.9, -5.6, 0, T),
    'OSD AVDD':             (0.0, -10.9, 90, Bo),
    'OSD PVDD':             (-3.45, -10.9, 90, Bo),
    'OSD reset pullup':     (1.15, -10.9, 90, Bo),
    'camera termination':   (-1.15, -10.9, 90, Bo),
    'camera coupling':      (-2.3, -10.9, 90, Bo),
    'VTX back-termination': (-4.6, -10.9, 90, Bo),
    # USB: CC resistors under the connector (bottom)
    'CC1 Rd':               (-13.2, -1.2, 0, Bo),
    'CC2 Rd':               (-13.2, -0.1, 0, Bo),
    # LEDs
    'power LED':            (13.2, 7.0, 90, T),
    'status LED':           (-7.0, 7.7, 0, T),
}
# parts that stay exactly where the tables put them; the rest are hints
# for the packer
FIXED_REFS = {'U_FC', 'U_IMU', 'U_OSD', 'U_FLASH', 'J_USB', 'J_ESC', 'J_HD', 'SW_BOOT', 'P_BAT', 'P_BATG',
              'L_9V', 'U_BUCK9', 'U_BUCK5', 'L_5V', 'D_USB', 'U_BUCK3', 'L_3V3'}
# (the hot loops' capacitors stay where the table puts them too)
FIXED_NOTES = {'5V BEC input HF', '5V BEC bootstrap', '5V BEC input', '5V BEC 455 kHz', '5V BEC output',
               '9V BEC input HF', '9V BEC input', '9V BEC bootstrap', '9V BEC output', '9V BEC 455 kHz',
               '9V BEC UVLO top',
               'VBAT TVS', 'VBAT_VTX TVS', 'CC1 Rd', 'CC2 Rd', '3.3V buck input', '3.3V buck output'}


def placement(comps):
    place = dict(PLACE)
    seen = {}
    for c in comps:
        if c.ref in place:
            continue
        if c.note not in PLACE_BY_NOTE:
            raise KeyError('no placement for %s (%s)' % (c.ref, c.note))
        p = PLACE_BY_NOTE[c.note]
        if isinstance(p, list):
            k = seen.get(c.note, 0); seen[c.note] = k + 1
            p = p[k]
        place[c.ref] = p
    return place


def fixed(comps):
    return (FIXED_REFS | {c.ref for c in comps if c.ref.startswith(('P_', 'H'))}
            | {c.ref for c in comps if c.note in FIXED_NOTES and c.ref not in PLACE})


def _rects(poly):
    """A rectilinear polygon as covering rectangles (its horizontal slabs)."""
    ys = sorted(set(p[1] for p in poly))
    out, n = [], len(poly)
    for y0, y1 in zip(ys, ys[1:]):
        ym = (y0 + y1) / 2
        xs = sorted(ax for (ax, ay), (bx, by) in ((poly[i], poly[(i + 1) % n]) for i in range(n))
                    if ax == bx and min(ay, by) < ym < max(ay, by))
        out += [(x0, y0, x1, y1) for x0, x1 in zip(xs[::2], xs[1::2])]
    return out


# Kept free of parts on top: the strip between the MCU's front pins and
# the OSD (their lines), the bands inboard of the edge pads (their labels).
KEEP_FREE = [
    (T, (-5.4, -5.0, 3.6, -3.0)),          # MCU front strip
    (T, (-11.5, -15.7, 1.4, -12.8)),       # front pads' labels
    (T, (5.8, -15.7, 8.7, -13.5)),
    (T, (-15.8, -11.0, -12.8, -5.1)),      # left pads' labels
    (T, (-15.8, 5.7, -12.8, 10.1)),
    (T, (-12.4, 5.4, -8.4, 10.2)),         # the OffGrid mark
    (Bo, (-10.0, -17.7, 10.0, -12.5)),     # the lockup (bottom, front band)
    (Bo, (-7.0, -3.0, 7.0, 4.6)),          # the board's name (bottom, under the MCU)
    # the stack lead's corridor: from the ESC lead's signal pins (3-8) to
    # the MCU's rear pins, kept free of parts on top so the six lines run
    # straight on the top layer (the 5 V BEC's pours under it leave no
    # room for vias)
    (T, (-3.0, 5.7, 3.2, 12.6)),
]


def reserved():
    """Board regions (side, bbox) the packer keeps free: the power pours
    and the power vias (both sides), and KEEP_FREE."""
    out = [(side, r) for net, side, poly in pours() if net != 'GND' for r in _rects(poly)] + KEEP_FREE
    # the production panel's tab zones along the edges, near the corners
    out += [(side, z) for z in pcb.tab_zones() for side in (T, Bo)]
    for net, pts, *_ in vias():
        for x, y in pts:
            for side in (T, Bo):
                out.append((side, (x - 0.35, y - 0.35, x + 0.35, y + 0.35)))
    return out


def clashes(fps):
    """The placement's errors as KiCad's DRC finds them, before any copper:
    two courtyards on one side that overlap or touch, and a pad with a hole
    (plated or not) inside another part's courtyard on either side (a
    plated hole's copper is on both).  The packer keeps the parts it places
    clear of everything; the fixed parts it never moves, so their places in
    the tables are checked here, and a wrong one stops the build before the
    routers run."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    def poly(sps):
        return unary_union([Polygon([(sps.Outline(k).CPoint(i).x / 1e6 - pcb.CX,
                                      sps.Outline(k).CPoint(i).y / 1e6 - pcb.CY)
                                     for i in range(sps.Outline(k).PointCount())])
                            for k in range(sps.OutlineCount())])
    court = {}
    for ref, fp in sorted(fps.items()):
        if hasattr(fp, 'BuildCourtyardCaches'):
            fp.BuildCourtyardCaches()
        for side, layer in ((T, pcbnew.F_CrtYd), (Bo, pcbnew.B_CrtYd)):
            g = poly(fp.GetCourtyard(layer))
            if not g.is_empty:
                court[(ref, side)] = g
    out = []
    keys = sorted(court)
    for i, (a, sa) in enumerate(keys):
        for c, sc in keys[i + 1:]:
            if sa == sc and a != c and court[(a, sa)].intersects(court[(c, sc)]):
                out.append('%s / %s (%s)' % (a, c, 'top' if sa == T else 'bottom'))
    for ref, fp in sorted(fps.items()):
        for p in fp.Pads():
            if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            bb = p.GetBoundingBox()
            pg = box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                     bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY)
            for (other, side), g in sorted(court.items()):
                if other != ref and g.intersects(pg):
                    out.append('%s pad %s (hole) / %s (%s)' % (ref, p.GetNumber() or '-', other,
                                                              'top' if side == T else 'bottom'))
    return out


def build_placed(out_path, legal=True, strict=True):
    b = pcb.new_board(LAYERS)
    pcb.outline(b)
    comps = circuit.build('fc')
    place = placement(comps)
    if legal:
        import legalize
        two_pad = lambda c: c.ref[:1] in 'RC' and c.note not in FIXED_NOTES
        place, left = legalize.pack(comps, place, fixed(comps), rotatable=two_pad, reserved=reserved())
        if left and strict:
            raise SystemExit('no room for %s' % left)
    fps = pcb.place_components(b, comps, place)
    bad = clashes(fps)
    print('placement: %s' % ('%d clashes: %s' % (len(bad), '; '.join(bad)) if bad else 'no courtyard overlaps, '
                             'no hole in a courtyard'))
    if bad and strict:
        raise SystemExit('placement clashes: %s' % '; '.join(bad))
    b.Save(out_path)
    return b, comps, fps


# ============================================================ power copper
# Zones connect solidly (no spokes): these carry the supplies' current.
VIA_PWR = (0.5, 0.25)
VIA_SIG = (0.35, 0.15)           # routers and the signal ICs' plane vias
# Freerouting may drop a signal via onto a same-net pad (route.py), filled
# and capped; the 0.1 mm ring keeps its hole 0.2 mm from other copper.
VIA_IN_PAD = VIA_SIG


def _rel(a, pts):
    return [(round(a[0] + x, 3), round(a[1] + y, 3)) for x, y in pts]


def pours():
    """(net, side, polygon) of every power pour, board mm."""
    return [
        # top: the lead's battery, from the ESC lead's pin 1 behind its
        # signal pins (clear of the connector's left tab) to the vias down
        # to the 5 V BEC
        ('VBAT', T, [(-7.25, 12.65), (-6.1, 12.65), (-6.1, 14.3), (-3.6, 14.3), (-3.6, 17.4), (-7.7, 17.4),
                     (-7.7, 14.3), (-7.25, 14.3)]),
        # top: the video supply's battery, from its pad down to its clamp and
        # the 9 V BEC's input capacitor and the vias by it
        ('VBAT_VTX', T, [(7.8, 17.4), (9.6, 17.4), (9.6, 9.75), (12.5, 9.75), (12.5, 8.3), (7.8, 8.3),
                         (7.8, 10.0), (6.2, 10.0), (6.2, 11.8), (7.8, 11.8)]),
        # 5 V BEC (bottom, relative to its IC): input round the back of
        # its VIN/EN pins, the HF capacitor, the clamp and the input
        # capacitor; switch node to the inductor; ground at the IC's GND
        # pin and the HF capacitor
        ('VBAT', Bo, _rel(A5, [(-4.95, -0.15), (-4.25, -0.15), (-4.25, 3.85), (-0.95, 3.85), (-0.95, 3.2),
                               (0.95, 3.2), (0.95, 3.85), (0.7, 3.85), (0.7, 5.45), (-4.95, 5.45)])),
        ('BUCK5_SW', Bo, _rel(A5, [(1.3, -4.9), (2.3, -4.9), (2.3, -4.15), (7.9, -4.15), (7.9, -1.9),
                                   (1.3, -1.9)])),
        ('GND', Bo, _rel(A5, [(1.2, 1.6), (3.4, 1.6), (3.4, 5.45), (1.2, 5.45)])),
        # 5 V: the inductor's output end to both output capacitors (round
        # the rear one's ground pad)
        ('+5V', Bo, [(1.2, 11.15), (9.6, 11.15), (9.6, 12.45), (5.4, 12.45), (5.4, 15.75), (9.6, 15.75),
                     (9.6, 17.4), (1.2, 17.4)]),
        # 9 V BEC (bottom, relative to its IC, turned as the 5 V one):
        # input from the vias down VIN's pin and to the HF capacitor and
        # the UVLO divider's top, clear of EN beside it;
        # switch node to the inductor round the bootstrap's CB end; ground
        # at the GND pin and the HF capacitor
        ('VBAT_VTX', Bo, _rel(A9, [(-3.0, 5.75), (0.55, 5.75), (0.55, 3.9), (0.0, 3.9), (0.0, 1.9),
                                   (-1.25, 1.9), (-1.25, 5.1), (-3.0, 5.1)])),
        ('BUCK9_SW', Bo, _rel(A9, [(1.35, -1.9), (2.45, -1.9), (2.45, -7.1), (-1.5, -7.1), (-1.5, -4.95),
                                   (1.35, -4.95)])),
        ('GND', Bo, _rel(A9, [(1.25, 1.9), (2.9, 1.9), (2.9, 5.3), (0.85, 5.3), (0.85, 3.85), (1.25, 3.85)])),
        # 9 V: the inductor's output end and both output capacitors' 9 V
        # pads, and the vias up to the HD connector
        ('+9V', Bo, [(6.5, -9.4), (15.2, -9.4), (15.2, -6.3), (6.5, -6.3)]),
        # top: from those vias to pin 1 of the HD connector
        ('+9V', T, [(13.3, -8.75), (15.2, -8.75), (15.2, -6.5), (13.3, -6.5)]),
        # top: the 9 V BEC's input capacitor's ground end, over the input
        # pour, to its via down to the BEC's ground pin
        ('GND', T, [(12.9, 6.55), (14.05, 6.55), (14.05, 6.95), (14.7, 6.95), (14.7, 7.45), (14.05, 7.45),
                    (14.05, 9.25), (12.9, 9.25)]),
        # 3.3 V buck (bottom, relative to its IC, turned 90: VIN, EN, MODE
        # and COMP down its left side, GND, SW, PG, FB down its right):
        # 5 V to the VIN/EN/MODE pins from the input capacitor, ground from
        # its other end to the GND pin (widening behind the switch node to
        # take the whole of the capacitor's pad), the switch node from the
        # SW pin (between PG and GND) to the inductor, 3.3 V from the
        # inductor's far end to both output capacitors
        ('+5V', Bo, _rel(A3, [(-1.55, -0.35), (-0.35, -0.35), (-0.35, 3.05), (-1.55, 3.05)])),
        ('GND', Bo, _rel(A3, [(0.4, 0.65), (1.3, 0.65), (1.3, 1.5), (2.05, 1.5), (2.05, 3.05), (0.4, 3.05)])),
        ('BUCK3_SW', Bo, _rel(A3, [(0.7, 0.1), (1.5, 0.1), (1.5, -1.2), (2.65, -1.2), (2.65, 1.2), (1.5, 1.2),
                                   (1.5, 0.4), (0.7, 0.4)])),
        ('+3V3', Bo, _rel(A3, [(3.3, -2.4), (6.0, -2.4), (6.0, -1.2), (4.7, -1.2), (4.7, 1.2), (3.4, 1.2),
                               (3.4, -1.2), (3.3, -1.2)])),
    ]


def vias():
    """(net, [(x, y)]) of the power vias, or (net, [(x, y)], (diameter,
    drill)) for a smaller one."""
    return [
        ('VBAT', [(-4.45, 16.3), (-4.45, 17.05), (-3.7, 17.3)]),     # the lead's battery to the 5 V BEC
        ('VBAT_VTX', [(11.4, 9.3), (12.2, 9.3)]),                   # the video battery to the 9 V BEC
        ('+9V', [(13.9, -8.3), (14.7, -8.3)]),                      # 9 V to the HD connector (pin 1 above)
        ('GND', [(14.45, 7.2)]),                                    # the 9 V input capacitor's ground
        ('GND', [(9.27, -11.55)], VIA_SIG),                         # the front 9 V output capacitor's ground
        # the 9 V BEC's EN pin, boxed in by its VIN and GND pins, the
        # exposed pad and the HF capacitor: a signal via in its pad (filled
        # and capped), at the pad's inner end, clear of the bulk
        # capacitor's ground pad on the top
        ('BUCK9_EN', [_rel(A9, [(0.63, 1.98)])[0]], VIA_SIG),
    ]


def power_copper(b):
    k = 0
    for net, side, poly in pours():
        layer = pcbnew.F_Cu if side == T else pcbnew.B_Cu
        pcb.zone(b, net, layer, poly, clearance=0.2, min_width=0.2, priority=2 if net == 'GND' else 3,
                 thermal=False, name='%s pour' % net)
    for net, pts, *size in vias():
        d, drill = size[0] if size else VIA_PWR
        for x, y in pts:
            v = pcb.via(b, x, y, net, d=d, drill=drill); v.SetLocked(True)
            k += 1
    return k


def routing_keepouts(b):
    """Rule areas (no tracks, no vias) over the power pours, added only to
    the copy of the board handed to Freerouting, which treats pours as
    planes other nets may cross.  Plus a 0.3 mm strip along each edge and
    over each mounting slot (Freerouting keeps only its own clearance from
    the outline)."""
    k = 0
    for net, side, poly in pours():
        layer = pcbnew.F_Cu if side == T else pcbnew.B_Cu
        pcb.rule_area(b, poly, [layer], tracks=True, vias=True, pads=False, pours=False, name='pour keepout')
        k += 1
    h, w = pcb.HALF, 0.3
    cu = [l for l in CU if b.IsLayerEnabled(l)]
    for x0, y0, x1, y1 in ((-h, -h, h, -h + w), (-h, h - w, h, h), (-h, -h, -h + w, h), (h - w, -h, h, h)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cu, tracks=True, vias=True, pads=False,
                      pours=False, name='edge keepout')
        k += 1
    a = pcb.SLOT_W / 2 + w
    for sx in (-1, 1):
        for sy in (-1, 1):
            d = (sx / math.sqrt(2), sy / math.sqrt(2)); nn = (sx / math.sqrt(2), -sy / math.sqrt(2))
            c = (sx * pcb.HOLE, sy * pcb.HOLE)
            pts = [(c[0] + t * d[0] + s_ * a * nn[0], c[1] + t * d[1] + s_ * a * nn[1])
                   for t, s_ in ((0, 1), (8.5, 1), (8.5, -1), (0, -1))]
            pcb.rule_area(b, pts, cu, tracks=True, vias=True, pads=False, pours=False, name='slot keepout')
            k += 1
    return k


# Every via filled and capped (POFV): the exposed pads' plane vias and the
# routers' vias in pads.
DRU_EXTRA = pcb.POFV_RULES

# ============================================================ board
LAYERS = 6
# 1 oz inner copper (rev 1: 0.5 oz).  The ground and 3.3 V planes are what
# spreads the supplies' heat across the board: at 50 C on the ground, the
# regulators' heat, not their rating, is what brings the gyro and the
# connectors to 85 C (STRESS.md), and twice the copper spreads it further.
# JLCPCB builds 1 oz inner layers at 0.1 / 0.1 mm like 0.5 oz.
INNER_OZ = 1.0
if LAYERS == 4:
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    PLANES = [('GND', pcbnew.In1_Cu), ('+3V3', pcbnew.In2_Cu)]
else:
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    PLANES = [('GND', pcbnew.In1_Cu), ('+3V3', pcbnew.In4_Cu)]
# Router rules per supply net (netclasses): (width, clearance) in mm.
# 9 V and the 5 V / 9 V switch nodes 0.4 mm; the 3.3 V buck's switch node
# 0.3 mm (its ~0.5 A).  The lead's battery current runs in its pours; its
# tracks feed the dividers and the clamp: 0.3 mm, as USB's 0.5 A.  The
# video battery's (up to 2 A, at 9 V 18 W from an empty 3S) runs in its
# pours too; anything the router adds is 0.5 mm.  5 V 0.3 mm: its heavy
# current stays in the BEC's pour, and no branch carries more than the
# camera's, the 3.3 V buck's or the LED strip's ~0.7 A (0.3 mm outer
# copper: 1 A at a 10 C rise).  The bootstrap nodes swing with the switch
# nodes, 0.25 mm.  The filtered 3.3 V feeds (OSD ~0.1 A, gyro ~1 mA) reach
# 0.5 mm pitch pins: 0.2 and 0.15 mm, and 3.3-5 V needs only the 0.1 mm
# clearance.
NET_RULES = {
    'VBAT': (0.3, 0.15), '+9V': (0.4, 0.15), 'USB_VBUS': (0.3, 0.15),
    'BUCK5_SW': (0.4, 0.15), 'BUCK9_SW': (0.4, 0.15), 'BUCK3_SW': (0.3, 0.15),
    'VBAT_VTX': (0.5, 0.15),
    '+5V': (0.3, 0.15),
    'BUCK5_CB': (0.25, 0.15), 'BUCK9_CB': (0.25, 0.15),
    '+3V3_OSD': (0.2, 0.1), '+3V3_GYRO': (0.15, 0.1),
}
# Low-current pins on the supply nets, by part note and net: joined to
# their net at this width before the autorouter runs (finish.route_taps).
# The bucks' feedback tops are sense lines (TI: thin, from the output
# capacitors).
TAPS = {
    ('5V BEC feedback top', '+5V'): 0.2, ('9V BEC feedback top', '+9V'): 0.2,
    ('3.3V buck feedback top', '+3V3'): 0.2,
}


def taps(comps):
    return {(c.ref, num): TAPS[(c.note, net)] for c in comps for num, net in c.pins.items()
            if (c.note, net) in TAPS}


# Routed first, by the in-house maze router, shortest first: the crystals,
# the gyro's SPI, the video lines and USB, while their area is still open.
# The gyro's MISO and MOSI run straight across, so they go before SCK,
# which has to cross them.
PREROUTE = ['HSE_IN', 'HSE_OUT', 'OSD_XI', 'OSD_XO', 'OSD_VIN', 'CAM_VIDEO', 'OSD_VOUT', 'VTX_VIDEO',
            'SPI1_MISO', 'SPI1_MOSI', 'GYRO_CS', 'GYRO_INT', 'SPI1_SCK', 'USB_DP', 'USB_DM']
CLMAP = {n: c for n, (w, c) in NET_RULES.items()}


def widths(comps):
    """Track width per net for the finishing routers (pipeline.py)."""
    return {n: w for n, (w, c) in NET_RULES.items()}


def clearances(comps):
    return dict(CLMAP)


def via_rules(b):
    """Signal vias 0.35 / 0.15 mm (JLCPCB's 0.15 mm hole; free with the
    6-layer POFV, every via filled and capped): the board's minimum, the
    default netclass and the supply classes."""
    ds = b.GetDesignSettings()
    ds.m_ViasMinSize = MM(VIA_SIG[0])
    ds.m_MinThroughDrill = MM(VIA_SIG[1])
    ds.m_ViasMinAnnularWidth = MM((VIA_SIG[0] - VIA_SIG[1]) / 2)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetViaDiameter(MM(VIA_SIG[0])); nc.SetViaDrill(MM(VIA_SIG[1]))
    groups = {}
    for n, rule in NET_RULES.items():
        groups.setdefault(rule, []).append(n)
    for (w, c), nets in sorted(groups.items(), reverse=True):
        pcb.netclass(b, 'PWR_%03d_%03d' % (round(w * 100), round(c * 100)), nets, width=w, clearance=c,
                     via_d=VIA_SIG[0], via_drill=VIA_SIG[1])


def build(out_path):
    b, comps, fps = build_placed(out_path)
    pcb.usb_c_tie(b, fps['J_USB'])
    # USBLC6-2SC6 is flow-through: pins 1/6 and 3/4 are the same line.
    # Join each pair straight under the package.
    esd = {p.GetNumber(): p for p in fps['U_ESD'].Pads()}
    esd_layer = pcbnew.B_Cu if fps['U_ESD'].IsFlipped() else pcbnew.F_Cu
    for a, c in (('1', '6'), ('3', '4')):
        pa, pc = esd[a].GetPosition(), esd[c].GetPosition()
        pcb.track(b, [(pa.x / 1e6 - pcb.CX, pa.y / 1e6 - pcb.CY), (pc.x / 1e6 - pcb.CX, pc.y / 1e6 - pcb.CY)],
                  0.2, esd_layer, esd[a].GetNetname())
    pcb.hole_keepouts(b, CU)
    pcb.tab_keepouts(b, CU)
    e = pcb.HALF - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    # unbroken ground and 3.3 V planes under everything
    for net, layer in PLANES:
        pcb.zone(b, net, layer, full, name='%s plane' % net)
    for l in CU[1:-1]:
        b.SetLayerType(l, pcbnew.LT_POWER if l in [p[1] for p in PLANES] else pcbnew.LT_SIGNAL)
    print('power vias:', power_copper(b))
    via_rules(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    import fanout, finish
    e2 = pcb.HALF - 0.4
    bounds = (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2)
    # plane vias: the supplies' exposed pads on a 1 mm grid (heat), the
    # signal ICs' on a 1.6 mm grid, so tracks still pass under them
    bec = {'U_BUCK5', 'U_BUCK9', 'U_BUCK3'}
    # ground pins beside a ground exposed pad join it with a stub, which
    # leaves the spot outside them to the pins round them (exposed pads
    # from 1 mm2 in this group)
    n1, f1 = fanout.fanout(b, {'GND', '+3V3'}, bounds, skip={c.ref for c in comps} - bec, ep_pitch=1.0,
                           ep_join=0.2, ep_min_area=1.0)
    n2, f2 = fanout.fanout(b, {'GND', '+3V3'}, bounds, skip=bec, ep_pitch=1.6, via_d=VIA_SIG[0],
                           via_drill=VIA_SIG[1], ep_join=0.2)
    print('fanout: %d plane vias, pads without one: %s' % (n1 + n2, f1 + f2))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    left = finish.route_taps(b, taps(comps), clmap=CLMAP, layers=ROUTE_LAYERS, via=VIA_SIG)
    print('supply taps: %d, not joined: %s' % (len(taps(comps)), left))
    # Pre-route the short, critical nets while their area is still open,
    # and lock them so the autorouter works around them.
    left = {}
    for net in PREROUTE:
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        left[net] = finish.route_net(b, net, clmap=CLMAP)
        if left[net]:
            # half a net, locked, only walls the autorouter in: it gets all of it
            for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
                b.Remove(t)
    print('pre-routed %d nets; left to the autorouter: %s' % (len(PREROUTE), sorted(k for k, v in left.items() if v)))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


if __name__ == '__main__':
    import sys
    if '--full' in sys.argv:
        build(sys.argv[1])
    else:
        build_placed(sys.argv[1] if len(sys.argv) > 1 else '/tmp/fc.kicad_pcb', legal='--nolegal' not in sys.argv,
                     strict=False)


# ---------------------------------------------------------------- artwork
LABELS = [
    ('P_T4', 'T4'), ('P_R4', 'R4'), ('P_T1', 'T1'), ('P_R1', 'R1'),
    ('P_RX5V', '5V'), ('P_RXG', 'G'), ('P_R2', 'R2'), ('P_T2', 'T2'),
    ('P_5V', '5V'), ('P_G1', 'G'), ('P_LED', 'LED'),
    ('P_VTX9V', '9V'), ('P_VTXG', 'G'), ('P_VTX', 'VTX'),
    ('P_CAM', 'CAM'), ('P_CAMG', 'G'), ('P_CAM5V', '5V'),
    ('P_BAT', 'BAT'), ('P_BATG', 'G'),
    ('TP_SWDIO', 'DIO'), ('TP_SWCLK', 'CLK'), ('TP_NRST', 'RST'),
]


# the flag over the product name: its height (the hoist; the fly is 1.9
# times it), largest first, and its gap to the name's capitals
FLAG_H = (4.0, 3.5)
FLAG_GAP = 0.9


def artwork(b):
    """OffGrid silkscreen: codes in JetBrains Mono, words in Instrument Sans,
    the bare mark on the top; the lockup, the flag of the United States and
    what the board is on the bottom, on the centre line.  On each side the
    front arrow (the same everywhere) with the side's name, "Top" or
    "Bottom"; the revision by a corner."""
    import artwork as A, brand
    A.hide_fields(b)
    A.strip(b)
    top = A.SilkPlacer(b, 'T', brand=True, via_clear=0.1, bodies=True)
    # 1.2 mm capitals, 1.1 at the least: at weight 500 that keeps the
    # median stroke of every glyph over the fabs' 0.15 mm silkscreen floor.
    # RST has the least room, so it goes first.
    side = {fp.GetReference(): ('B' if fp.IsFlipped() else 'T') for fp in b.GetFootprints()}
    for ref, s in sorted(LABELS, key=lambda rs: rs[0] != 'TP_NRST'):
        if side[ref] == 'T':
            top.label(ref, s, size=1.2, smallest=1.1, face='mono')
    top.label('J_ESC', '1', pad='1', dist=0.8, size=1.2, face='mono')
    top.label('J_HD', '1', pad='1', dist=0.8, size=1.2, face='mono')
    top.label('SW_BOOT', 'Boot', pad='1', size=1.2)
    everywhere = top.grid_spots((0.0, 0.0), radius=17.0, step=0.25)
    mark, clear = brand.mark_mm(3.0)
    top.geom(mark, everywhere, clear=clear, vias='fewest')
    # the front arrow, and which side this is
    A.side_mark(top, [s for s in everywhere if s[1] < -8], 'Top')

    bot = A.SilkPlacer(b, 'B', brand=True, via_clear=0.1)
    # The bottom carries the supplies at the rear and right.  Two bands
    # are kept free on the centre line: the front edge (the lockup) and
    # under the MCU (what the board is).  The lockup and the name sit
    # exactly on the centre line: only their height may move to clear a via
    # or a part.
    # It fits by its outline (the corner under the wordmark's end is
    # empty: the 9 V BEC's second output capacitor's pad sits there), from
    # the placer's 0.35 mm inside the edge.
    for w in (20.0, 18.0, 16.0):           # 16 mm: the mark at the brand's 24 px
        g, clear = brand.lockup_mm(w, mirror=True)
        h = g.bounds[3] - g.bounds[1]
        y0 = -pcb.HALF + 0.35 + h / 2 + 0.01
        if bot.geom(g, [(0.0, y0 + 0.05 * k) for k in range(30)], clear=clear, vias='fewest', quiet=True, hull=True):
            break
    else:
        raise SystemExit('fc: no room for the lockup on the bottom')
    # the front arrow and which side this is: along the left edge, under
    # the USB-C, else as near there as fits
    spots = [(x, y) for x in (-16.2, -16.0, -15.8, -15.6) for y in (0.0, -0.5, 0.5, -1.0, 1.0)]
    A.side_mark(bot, spots + bot.grid_spots((-15.0, 0.0), radius=16.0, step=0.25), 'Bottom')
    # what the board is: the product name, then the firmware to flash.
    # The flag of the United States goes over the product name, on the
    # centre line (the owner's request: where the company's name is), so
    # the name takes only a spot that leaves the flag room above it.
    from shapely import affinity

    def flag_spots(h, env):
        above = env.bounds[1] - pcb.CY - FLAG_GAP
        return [(0.0, above - h / 2 - 0.05 * k) for k in range(40)]

    def flag_room(env):
        for h in FLAG_H:
            f = brand.us_flag_mm(h, mirror=True)
            for x, y in flag_spots(h, env):
                e = affinity.translate(f, pcb.CX + x, pcb.CY + y).envelope
                if bot.fits(e, margin=0.1) and e.distance(env) >= bot.silk_clear:
                    return True
        return False
    base = -0.8
    name = None
    for runs, cap, step in (([('sans', PRODUCT)], 2.4, 2.2),
                            ([('sans', 'Flight controller')], 1.2, 1.9),
                            ([('mono', FIRMWARE)], 1.1, 0)):
        g0 = brand.line(runs, cap)[0].bounds
        mid = (g0[1] + g0[3]) / 2           # box centre below the baseline
        spots = [(0.0, base + mid + dy, 0, None) for dy in (0.0, 0.1, -0.1, 0.2, 0.3, 0.4, 0.6, 0.8)]
        if bot.text(runs, spots, size=cap, vias='fewest', accept=None if name else flag_room):
            base = bot.placed[-1].centroid.y - pcb.CY - mid + step
            name = name or bot.placed[-1]
    if name is None:
        raise SystemExit('fc: the product name found no room with the flag over it')
    for h in FLAG_H:
        if bot.geom(brand.us_flag_mm(h, mirror=True), flag_spots(h, name), vias='fewest', margin=0.1, quiet=True):
            break
    else:
        raise SystemExit('fc: no room for the flag over the product name')
    # the bottom's pad names (SWD), after the name has its place
    for ref, s in LABELS:
        if side[ref] == 'B':
            bot.label(ref, s, size=1.2, smallest=1.1, face='mono')
    # the revision, by a corner: the bottom first, with the name
    A.revision((bot, top), REVISION)
