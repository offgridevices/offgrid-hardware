# -*- coding: utf-8 -*-
"""Ridge 3 flight controller (36 x 36 mm, 25.5 mm slotted holes):
placement, power copper, planes and silkscreen.

Double-sided assembly.  Top: MCU, gyro, flash, OSD and both crystals,
connectors, solder pads, LEDs, boot button.  Bottom: the two switching
supplies (5 V at the rear, 9 V on the right), the 3.3 V LDO and the
USB-C's VBUS diode and CC resistors.  Front of the quad is -y (top of
every plot).  USB-C faces LEFT, as in v1; the ESC lead leaves from the
rear.

Power: the battery comes in on the ESC lead (pin 1) and the P_BAT pad.  A
top pour behind the lead's pins joins them and runs down a leg inside the
rear-right hole to the 9 V BEC's vias; each BEC's input capacitor, IC and
inductor sit together on the bottom with their switch node, input and
ground as pours (routers kept out of them).  5 V and 9 V leave their BECs
as pours; the rest of their nets is routed at 0.4 and 0.3 mm.

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

T, Bo = 'T', 'B'
PE = 16.8                        # edge solder pads: centre distance from the board centre

# Anchors: the two BEC ICs.  Their passives and pours are placed relative
# to them.
A5 = (-3.0, 11.9)                # U_BUCK5, rot 180, bottom: VIN/GND pins rear, SW front right
A9 = (13.0, 5.0)                 # U_BUCK9, rot 0, bottom: SW pins front, PVIN/PGND rear


def at(a, dx, dy, rot, side=Bo):
    return (round(a[0] + dx, 3), round(a[1] + dy, 3), rot, side)


# ref: (x, y, rotation, side).  Parts named here by reference.
PLACE = {
    # MCU at 0 deg.  Its pins, by side:
    #   rear  (1-12)  crystal, NRST, MOTOR1-4, gyro INT      -> ESC lead
    #   right (13-24) SPI1 gyro, ADC, VDDA/VREF, TLM         -> gyro
    #   front (25-36) SPI2 flash + OSD, UART1, USB, SWDIO     -> flash, OSD, USB
    #   left  (37-48) SWCLK, beeper, UART4, UART2, VTX switch,
    #                 LED strip, LED0, BOOT0                  -> left pads
    'U_FC':    (-1.0, 1.1, 0, T),
    # gyro right of the MCU, rotation fixed at 90 (circuit.py, firmware CW270)
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
    'J_ESC':   (-1.0, 14.6, 0, T),
    'P_BATG':  (6.0, 16.2, 0, T),
    'P_BAT':   (8.5, 16.2, 0, T),
    'J_HD':    (15.4, -4.5, 90, T),
    'SW_BOOT': (16.3, 6.0, 90, T),
    'SJ_SBUS': (12.0, -8.0, 90, T),
    'Q_BZ':    (11.0, 1.2, 0, T),
    'LED_STAT': (-7.0, 6.0, 0, T),
    'LED_PWR':  (13.2, 5.0, 90, T),
    'FB_OSD':  (-7.0, -9.5, 90, T),
    # SWD (debugging only: the FC flashes over USB) on the bottom, left of
    # the name band, near the MCU's SWD pins; reset on top
    'TP_SWDIO': (-9.0, -6.0, 0, Bo), 'TP_SWCLK': (-9.0, -4.4, 0, Bo), 'TP_NRST': (-5.3, 10.4, 0, T),
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
    # right edge: buzzer
    'P_BZ+':   (PE, 0.9, 90, T), 'P_BZ-': (PE, 2.4, 90, T),
    # ---- bottom, 9 V BEC on the right: switch pins forward to the
    # inductor, PVIN/PGND pins back to the input capacitor
    'U_BUCK9': at(A9, 0, 0, 0),
    'L_9V':    at(A9, 0.5, -8.3, 90),
    # ---- bottom, 5 V BEC at the rear: IC and inductor side by side, the
    # IC's SW pin (front right) at the inductor's SW end, its VIN/GND pins
    # (rear) at the input capacitor
    'U_BUCK5': at(A5, 0, 0, 180),
    'L_5V':    at(A5, 5.45, -0.3, 270),
    # ---- mounting
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, T), 'H2': (pcb.HOLE, -pcb.HOLE, 0, T),
    'H3': (pcb.HOLE, pcb.HOLE, 0, T),   'H4': (-pcb.HOLE, pcb.HOLE, 0, T),
}
# Passives, by their circuit.py note; a list for notes that repeat (in
# circuit order).
PLACE_BY_NOTE = {
    # battery: bulk capacitor on the top VBAT pour, TVS at its left end
    'VBAT bulk':            (5.3, 9.3, 90, T),
    'VBAT TVS':             (-8.2, 13.8, 90, T),
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
    '5V BEC 1 MHz':         at(A5, -3.5, 2.5, 90),
    '5V BEC output':        [(6.2, 14.3, 270, Bo), (6.2, 10.7, 90, Bo), (8.4, 12.5, 90, Bo)],
    '5V BEC feedback top':  at(A5, -2.4, -4.5, 0),
    '5V BEC feedback bottom': at(A5, -2.4, -5.5, 0),
    '3.3V LDO':             (8.4, 8.0, 0, Bo),
    'LDO in':               (8.4, 9.6, 0, Bo),
    'LDO out':              (8.4, 6.5, 0, Bo),
    # 9 V BEC: input capacitors behind PVIN/PGND, the pin-6..11 parts in
    # the strip between the IC and the inductor, feedback at FB (right)
    '9V BEC input HF':      at(A9, -1.0, 3.2, 180),
    '9V BEC input':         (11.5, 7.2, 0, T),
    '9V BEC bootstrap':     at(A9, -0.3, -3.25, 180),
    '9V BEC BIAS':          at(A9, 2.3, -3.25, 0),
    '9V BEC 994 kHz':       at(A9, 4.0, -3.0, 90),
    '9V BEC VCC':           at(A9, 2.8, 3.2, 0),
    '9V BEC UVLO top':      at(A9, 2.6, 4.3, 0),
    '9V BEC UVLO bottom':   at(A9, 3.6, 5.0, 90),
    'VTX power switch':     (12.2, 3.8, 0, T),
    'VTX switch gate':      (10.0, 3.4, 90, T),
    'VTX switch gate pulldown': (10.0, 5.2, 90, T),
    '9V BEC output':        [(9.0, -2.4, 270, Bo), (9.0, -6.0, 90, Bo), (9.0, -9.4, 90, Bo), (16.0, -8.9, 0, Bo)],
    '9V BEC feedback top':  at(A9, 4.1, -2.4, 90),
    '9V BEC feedback bottom': at(A9, 4.1, -4.4, 90),
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
    # LEDs, beeper
    'power LED':            (13.2, 7.0, 90, T),
    'status LED':           (-7.0, 7.7, 0, T),
    'beeper gate':          (11.0, 3.0, 0, T),
    'beeper gate pulldown': (11.0, 4.0, 0, T),
}
# parts that stay exactly where the tables put them; the rest are hints
# for the packer
FIXED_REFS = {'U_FC', 'U_IMU', 'U_OSD', 'U_FLASH', 'J_USB', 'J_ESC', 'J_HD', 'SW_BOOT', 'P_BAT', 'P_BATG',
              'L_9V', 'U_BUCK9', 'U_BUCK5', 'L_5V', 'D_USB'}
FIXED_NOTES = {'5V BEC input HF', '5V BEC bootstrap', '5V BEC input', '5V BEC 1 MHz', '5V BEC output',
               '9V BEC input HF', '9V BEC input', '9V BEC bootstrap', '9V BEC VCC', '9V BEC output',
               'VBAT bulk', 'VBAT TVS', 'CC1 Rd', 'CC2 Rd'}


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
    (T, (12.6, 0.2, 15.8, 3.1)),           # buzzer pads' labels
    (T, (-12.4, 5.4, -8.4, 10.2)),         # the OffGrid mark
    (Bo, (-10.0, -17.7, 10.0, -12.5)),     # the lockup (bottom, front band)
    (Bo, (-7.0, -3.0, 7.0, 4.6)),          # the board's name (bottom, under the MCU)
    # the stack lead's corridor: from the ESC lead's signal pins (3-8) to
    # the MCU's rear pins, kept free of parts on top so the six lines run
    # straight on the top layer (the 5 V BEC's pours under it leave no
    # room for vias)
    (T, (-3.0, 5.7, 3.2, 11.7)),
]


def reserved():
    """Board regions (side, bbox) the packer keeps free: the power pours
    and the power vias (both sides), and KEEP_FREE."""
    out = [(side, r) for net, side, poly in pours() if net != 'GND' for r in _rects(poly)] + KEEP_FREE
    # the production panel's tab zones along the edges, near the corners
    out += [(side, z) for z in pcb.tab_zones() for side in (T, Bo)]
    for net, pts in vias():
        for x, y in pts:
            for side in (T, Bo):
                out.append((side, (x - 0.35, y - 0.35, x + 0.35, y + 0.35)))
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
        # top: battery.  Pin 1 of the ESC lead and the P_BAT pad joined
        # behind the lead's pins; a leg down inside the rear-right hole to
        # the 9 V BEC's vias and bulk capacitor; arms to the battery bulk
        # capacitor and the TVS
        ('VBAT', T, [(-5.0, 12.2), (-4.0, 12.2), (-4.0, 13.75), (3.9, 13.75), (3.9, 11.4), (7.4, 11.4),
                     (7.4, 8.45), (14.9, 8.45), (14.9, 9.55), (9.5, 9.55), (9.5, 17.4), (7.4, 17.4),
                     (7.4, 14.95), (-3.8, 14.95), (-3.8, 17.4), (-5.0, 17.4), (-5.0, 15.35), (-7.5, 15.35),
                     (-7.5, 16.15), (-8.9, 16.15), (-8.9, 14.75), (-5.0, 14.75)]),
        # 5 V BEC (bottom, relative to its IC): input round the back of
        # its VIN/EN pins and the input capacitors, switch node to the
        # inductor, ground at the IC's GND pin and the HF capacitor
        ('VBAT', Bo, _rel(A5, [(-5.9, -0.15), (-4.25, -0.15), (-4.25, 3.85), (-0.95, 3.85), (-0.95, 3.2),
                               (0.95, 3.2), (0.95, 5.45), (-5.9, 5.45)])),
        ('BUCK5_SW', Bo, _rel(A5, [(1.3, -4.9), (2.3, -4.9), (2.3, -3.75), (7.0, -3.75), (7.0, -1.6),
                                   (1.3, -1.6)])),
        ('GND', Bo, _rel(A5, [(1.2, 1.6), (3.4, 1.6), (3.4, 5.45), (1.2, 5.45)])),
        ('+5V', Bo, [(0.8, 11.2), (7.1, 11.2), (7.1, 12.8), (9.0, 12.8), (9.0, 14.0), (7.1, 14.0),
                     (7.1, 13.9), (0.8, 13.9)]),
        # 9 V BEC (bottom, relative to its IC)
        ('VBAT', Bo, _rel(A9, [(-0.75, 1.55), (0.72, 1.55), (0.72, 2.9), (2.2, 2.9), (2.2, 4.55),
                               (-0.9, 4.55), (-0.9, 2.5), (-0.75, 2.5)])),
        ('BUCK9_SW', Bo, _rel(A9, [(-2.9, -1.95), (-0.37, -1.95), (-0.37, -3.95), (2.35, -3.95),
                                   (2.35, -6.7), (-1.35, -6.7), (-1.35, -3.95), (-2.9, -3.95)])),
        # (its left edge 0.8 mm clear of the 3.3 V LDO's pins: the lane
        # where the LDO's EN pin loops round its GND pin to IN)
        ('GND', Bo, _rel(A9, [(-3.05, 0.6), (-1.05, 0.6), (-1.05, 4.3), (-3.05, 4.3)])),
        # 9 V: the inductor's output end, the output capacitors (left
        # column and front right) and the vias up to the HD connector
        ('+9V', Bo, [(8.3, -2.85), (11.6, -2.85), (11.6, -4.85), (15.7, -4.85), (15.7, -9.75), (13.5, -9.75),
                     (13.5, -7.9), (11.6, -7.9), (11.6, -9.1), (8.3, -9.1), (8.3, -8.0), (9.93, -8.0),
                     (9.93, -5.6), (8.3, -5.6)]),
        # top: from those vias to pin 1 of the HD connector
        ('+9V', T, [(13.3, -8.75), (15.2, -8.75), (15.2, -6.5), (13.3, -6.5)]),
    ]


def vias():
    """(net, [(x, y)]) of the power vias."""
    return [
        ('VBAT', [(-4.4, 16.55), (-4.4, 17.25)]),                   # top pour to the 5 V BEC
        ('VBAT', [(12.7, 9.1), (13.5, 9.1), (14.3, 9.1)]),           # top pour to the 9 V BEC
        ('+9V', [(13.9, -8.3), (14.7, -8.3)]),                      # 9 V to the HD connector (pin 1 above)
    ]


def power_copper(b):
    k = 0
    for net, side, poly in pours():
        layer = pcbnew.F_Cu if side == T else pcbnew.B_Cu
        pcb.zone(b, net, layer, poly, clearance=0.2, min_width=0.2, priority=2 if net == 'GND' else 3,
                 thermal=False, name='%s pour' % net)
    for net, pts in vias():
        for x, y in pts:
            v = pcb.via(b, x, y, net, d=VIA_PWR[0], drill=VIA_PWR[1]); v.SetLocked(True)
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
if LAYERS == 4:
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
    PLANES = [('GND', pcbnew.In1_Cu), ('+3V3', pcbnew.In2_Cu)]
else:
    CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    PLANES = [('GND', pcbnew.In1_Cu), ('+3V3', pcbnew.In4_Cu)]
# Router rules per supply net (netclasses): (width, clearance) in mm.
# 9 V and the switch nodes 0.4 mm.  The battery's current runs in its
# pours; its tracks feed the dividers and the 9 V BEC's input capacitor:
# 0.3 mm, as USB's 0.5 A.  5 V 0.3 mm: its heavy
# current stays in the BEC's pour, and no branch carries more than the
# camera's or the LED strip's ~0.7 A (0.3 mm outer copper: 1 A at a
# 10 C rise), while 0.4 mm could not pass between the LDO's input
# capacitor and its thermal pad.  The bootstrap nodes swing with the
# switch nodes, 0.25 mm.  The filtered 3.3 V feeds (OSD ~0.1 A, gyro ~1
# mA) and the 9 V BEC's VCC reach 0.5 mm pitch pins: 0.2 and 0.15 mm, and
# 3.3-5 V needs only the 0.1 mm clearance.
NET_RULES = {
    'VBAT': (0.3, 0.15), '+9V': (0.4, 0.15), 'USB_VBUS': (0.3, 0.15),
    'BUCK5_SW': (0.4, 0.15), 'BUCK9_SW': (0.4, 0.15),
    '+5V': (0.3, 0.15),
    'BUCK5_CB': (0.25, 0.15), 'BUCK9_CB': (0.25, 0.15),
    '+3V3_OSD': (0.2, 0.1), 'BUCK9_VCC': (0.2, 0.1), '+3V3_GYRO': (0.15, 0.1),
}
# Low-current pins on the supply nets, by part note and net: joined to
# their net at this width before the autorouter runs (finish.route_taps).
# The BECs' feedback tops and the 9 V BEC's BIAS pin and capacitor are
# sense lines (TI: thin, from the output capacitors); the 3.3 V LDO draws
# at most ~0.3 A from 5 V (0.2 mm outer copper: 0.7 A), its EN pin none.
# The 9 V BEC's two VCC pins, on opposite sides of the IC, join their
# capacitor while the space round the IC is still open.
TAPS = {
    ('5V BEC feedback top', '+5V'): 0.2, ('9V BEC feedback top', '+9V'): 0.2,
    ('9V BEC BIAS', '+9V'): 0.2, ('9V VTX BEC', '+9V'): 0.2,
    ('3.3V LDO', '+5V'): 0.2, ('LDO in', '+5V'): 0.2,
    ('9V VTX BEC', 'BUCK9_VCC'): 0.2,
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
    bec = {'U_BUCK5', 'U_BUCK9', 'U_LDO'}
    # ground pins beside a ground exposed pad join it with a stub, which
    # leaves the spot outside them to the pins round them (the LDO's
    # thermal pad is 1.6 mm2: exposed pads from 1 mm2 in this group)
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
    ('P_BZ+', '5V'), ('P_BZ-', 'BZ-'),                                    # buzzer: 5V and BZ-
    ('P_VTX9V', '9V'), ('P_VTXG', 'G'), ('P_VTX', 'VTX'),
    ('P_CAM', 'CAM'), ('P_CAMG', 'G'), ('P_CAM5V', '5V'),
    ('P_BAT', 'BAT'), ('P_BATG', 'G'),
    ('TP_SWDIO', 'DIO'), ('TP_SWCLK', 'CLK'), ('TP_NRST', 'RST'),
]


def artwork(b):
    """OffGrid silkscreen: codes in JetBrains Mono, words in Instrument Sans,
    the bare mark and the front arrow on the top; the lockup and what the
    board is on the bottom, on the centre line."""
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
    if not top.geom(brand.arrow_mm(2.6, 'Front', cap=1.2, side=True), [s for s in everywhere if s[1] < -8],
                    vias='fewest', margin=0.2, quiet=True):
        top.geom(brand.arrow_mm(2.6), [s for s in everywhere if s[1] < -8], vias='fewest', margin=0.2)
    mark, clear = brand.mark_mm(3.0)
    top.geom(mark, everywhere, clear=clear, vias='fewest')

    bot = A.SilkPlacer(b, 'B', brand=True, via_clear=0.1)
    # The bottom carries the supplies at the rear and right.  Two bands
    # are kept free on the centre line: the front edge (the lockup) and
    # under the MCU (what the board is).  The lockup and the name sit
    # exactly on the centre line: only their height may move to clear a via
    # or a part.
    for w in (20.0, 18.0, 16.0):
        g, clear = brand.lockup_mm(w, mirror=True)
        h = g.bounds[3] - g.bounds[1]
        y0 = -pcb.HALF + 0.35 + 0.4 + h / 2 + 0.01       # edge, then the placer's 0.4 mm margin
        if bot.geom(g, [(0.0, y0 + 0.05 * k) for k in range(30)], clear=clear, vias='fewest', quiet=True):
            break
    # the front arrow: along the left edge, under the USB-C (with its
    # word if there is room)
    spots = [(x, y) for x in (-16.2, -16.0, -15.8, -15.6) for y in (0.0, -0.5, 0.5, -1.0, 1.0)]
    if not bot.geom(brand.arrow_mm(5.0, 'Front', cap=1.2, mirror=True, side=True), spots, vias='fewest',
                    margin=0.2, quiet=True):
        bot.geom(brand.arrow_mm(5.0, mirror=True), spots, vias='fewest', margin=0.2)
    # what the board is: the product name, then the firmware to flash
    base = -0.8
    for runs, cap, step in (([('sans', PRODUCT)], 2.4, 2.2),
                            ([('sans', 'Flight controller')], 1.2, 1.9),
                            ([('mono', FIRMWARE)], 1.1, 0)):
        g0 = brand.line(runs, cap)[0].bounds
        mid = (g0[1] + g0[3]) / 2           # box centre below the baseline
        spots = [(0.0, base + mid + dy, 0, None) for dy in (0.0, 0.1, -0.1, 0.2, 0.3, 0.4, 0.6, 0.8)]
        if bot.text(runs, spots, size=cap, vias='fewest'):
            base = bot.placed[-1].centroid.y - pcb.CY - mid + step
    # the bottom's pad names (SWD), after the name has its place
    for ref, s in LABELS:
        if side[ref] == 'B':
            bot.label(ref, s, size=1.2, smallest=1.1, face='mono')
