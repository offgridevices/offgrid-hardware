# -*- coding: utf-8 -*-
"""Placement: where every part of circuit.py goes.

Board: 34 x 34 mm, rounded corners, four 3.2 mm grommet holes on the
25.5 mm square.  Coordinates are mm from the board centre, x to the right,
y towards the REAR (KiCad's y points down the screen, so the front of the
quad is at the top of every plot).  Rotations are KiCad's (degrees,
counter-clockwise on screen); a part on the bottom is flipped first.

The floor plan:

  BOTTOM  the power stage.  Each ESC channel owns one board edge: its six
          FETs stand in three radial half-bridges along the edge (high
          side inside, low side at the edge, the switch node between
          them), its shunt and current amplifier at the edge's clockwise
          end, and its gate driver and MCU side by side behind the FETs,
          the four pairs turned like a pinwheel round the centre.  The
          gate-drive supply sits in the middle, equidistant from the four
          drivers.
  TOP     the flight controller in the middle; each edge carries its
          motor's three pads at the edge's counter-clockwise end (over the
          FETs that drive them) and one connector at the other end:
          battery (rear), USB-C (left), receiver (front), aux pads (right).
          The bridge capacitors sit over the high-side FETs.

One channel is drawn once, for the REAR edge (u along x, r towards the
edge at y = +17), and turned for the others: rear M1 (rear-right motor),
right M2 (front-right), front M4 (front-left), left M3 (rear-left).

layout.py names the parts that decide the floor plan; placement.py packs
the small parts round them (each beside the pin it serves).
"""
import math
import os
import pcb

H = pcb.HALF
# The template is drawn for a 34 mm board; on a larger one every channel
# moves out with its edge by D (the holes stay on the 25.5 mm square).
D = round(pcb.HALF - 17.0, 4)

# ----------------------------------------------------------------- channels
# rotation of the rear-edge template onto each channel's edge (degrees, CCW
# on screen): rear -> right -> front -> left
CHANNELS = {1: 0, 2: 90, 4: 180, 3: 270}

PH_U = {'A': 0.2, 'B': 4.0, 'C': 7.8}    # half-bridge centres along the edge
# The high- and low-side rows stand 0.85 mm apart: a lane along every
# channel, full of switch-node copper, where the USB-C's two locating pegs
# (0.65 mm unplated holes) come through on the left edge.
R_HS = 9.175                             # high-side FET centre
R_LS = 14.275                            # low-side FET centre
PEG_R = 11.72                            # the peg lane's centre line
# motor pads (top): over their half-bridges, 0.3 mm towards +u so the low
# side's gate via (in its gate pin, at u - 0.97) keeps clear of the pad
PAD_U = {k: v + 0.3 for k, v in PH_U.items()}
R_PAD = 15.45
# ...except on the left edge, where the USB-C takes the edge up to u 2.75.
# There the pads stand 3.8 mm in from the edge, over the low sides' drain
# tabs (B and C take vias straight down into their own switch node; A
# comes from under the USB-C on a top strip, power.py), so the edge stays
# free for the return vias over the low sides' sources.
PAD_U_LEFT = {'A': 3.75, 'B': 5.85, 'C': 8.4}
R_PAD_LEFT = 13.3
# gate drivers (bottom): their centres stay 4.4 mm from the board's centre
# whatever the board's size, so a larger board widens the strip between
# each driver and its FETs (gate resistors, bootstrap capacitors, escapes)
R_CHIP_ABS = 4.0
# The driver stands beside its ESC MCU, between it and the board's centre:
# its high-side inputs (22-24) face the MCU's PWM pins across a 0.5 mm gap
# and its low-side inputs (1-3) the MCU's corner, so the six lines run on
# the bottom with no via; its gate, bootstrap and switch-node pins (13-18)
# face the strip towards the FETs; its low-side gate pins (9-11) face the
# centre, under the FC MCU, where no via may go (its exposed pad is the
# MCU's ground): their resistors sit there and their vias beyond it.
# Board-centre coordinates of channel 1 (DRV_R is r on the driver's scale).
DRV_U, DRV_R, DRV_ROT = -4.2, 5.3, 0
# The turned floor plan (DRV_TURN): the driver a quarter turn round and
# beside its FETs instead of round the FC MCU.  Its gate, bootstrap and
# switch-node pins (13-18) then face the free band in front of the high
# sides, its low-side gate pins (9-11) face +u, and only its four logic and
# supply inputs (1-4) face the board's centre: no gate trace starts under
# the FC MCU, and the packer sets the bootstrap capacitors and gate
# resistors at their pins.
DRV_TURN = os.environ.get('DRV_TURN', '0') == '1'
if DRV_TURN:
    DRV_U, DRV_R, DRV_ROT = -0.5, 5.6, 270
    if os.environ.get('DRV_POS'):
        DRV_U, DRV_R = (float(v) for v in os.environ['DRV_POS'].split(','))
R_CHIP = round(R_CHIP_ABS - D, 4)


def xf_point(rot, u, r):
    """Template (u, r) on the rear edge -> board (x, y), turned by `rot`
    degrees counter-clockwise on screen (y down)."""
    a = math.radians(rot)
    return (round(u * math.cos(a) + r * math.sin(a), 4), round(-u * math.sin(a) + r * math.cos(a), 4))


def place(rot, u, r):
    """Template (u, r) -> board (x, y) on this board: the edge offset D,
    then the channel's turn."""
    return xf_point(rot, u, r + D)


# ------------------------------------------------- the gate-drive corner
# Round each channel's driver (bottom), laid out by hand: the bootstrap
# capacitors, the six gate resistors, each gate resistor's via down to the
# inner layer that takes the gate to its FET, and the short tracks between
# them (power.channel_copper).  Coordinates are channel 1's (u = x), with
# r measured as the board-centre distance the driver keeps on every board
# size (R_CHIP_ABS): drv() turns that into the template's r.
#
# The driver's FET-side pins run BSTx, GHx, SHx side by side, so each
# bootstrap capacitor straddles its gate pin: its pads (0.4 mm apart) stand
# in front of BST and SH and the gate trace leaves straight out between
# them.  B and C in front of the FET-side row (pins 13-18), A beside the
# corner (pins 18-20).  The low-side gate pins (9-11) leave sideways.
# The whole gate-drive group (driver, bootstrap capacitors, gate resistors,
# and the ESC MCU beside it) moves this far out from the board's centre:
# the gap it opens round the FC MCU takes that MCU's escape vias and the
# drivers' own, where the four drivers would otherwise crowd the middle.
DRV_SHIFT = float(os.environ.get('DRV_SHIFT', 0.7))
# the ESC MCU's own step out (it keeps clear of the USB-C's pegs, the shunt
# and the power vias beyond)
UE_SHIFT = float(os.environ.get('UE_SHIFT', 0.1))
# the low-side gate resistors left to the packer instead of the row under
# the FC MCU (where no via may go)
GL_PACK = os.environ.get('GL_PACK', '0') == '1'


def drv(y):
    """Board-centre distance y on the driver's scale -> template r."""
    return round(y - R_CHIP_ABS + R_CHIP + DRV_SHIFT, 4)


DRIVE_PARTS = {
    # bootstrap capacitors in the strip, each straddling its gate pin's
    # escape: C beside pins 12-14, B beside 15-17, A beside 18-20 (A's
    # BST pin is round the corner, on the bottom row)
    'bootstrap C': (-1.25, 4.07, 90, 'B'), 'bootstrap B': (-0.15, 5.53, 90, 'B'),
    'bootstrap A': (-1.25, 7.03, 90, 'B'),
    # high-side gate resistors just beyond, in line with the escapes
    'gate high C': (0.60, 4.05, 0, 'B'), 'gate high B': (1.00, 5.55, 0, 'B'),
    'gate high A': (0.00, 7.03, 0, 'B'),
    # low-side gate resistors under the FC MCU, in a row 1 mm apart above
    # the driver's centre-facing pins (r 2.25 keeps each one's turned copy
    # clear of the next channel's strip)
    'gate low C': (-4.95, 2.25, 90, 'B'), 'gate low B': (-3.95, 2.25, 90, 'B'),
    'gate low A': (-2.95, 2.25, 90, 'B'),
    # the driver's 11 V decoupling right at its GVDD pin (4), beside the
    # low-side inputs' lane
    'driver # GVDD': (-7.25, 4.5, 90, 'B'),
}
# the driver's FET-side escapes, drawn by hand (driver scale, like
# DRIVE_PARTS; width): each bootstrap trace and switch-node trace straight
# into its capacitor, and each gate trace straight out between that
# capacitor's pads (0.40 mm apart) to its resistor.  On the router's grid
# that lane rounds shut, so these are fixed copper from the start.
DRIVE_TRACKS = [
    ('GHC_D', [(-2.3, 4.05), (0.28, 4.05)], 0.1),
    ('BSTC', [(-2.3, 4.55), (-1.25, 4.55)], 0.15),
    ('C', [(-2.95, 3.40), (-2.76, 3.59), (-1.25, 3.59)], 0.15),
    ('B', [(-2.3, 5.05), (-0.15, 5.05)], 0.15),
    ('GHB_D', [(-2.3, 5.55), (0.68, 5.55)], 0.1),
    ('BSTB', [(-2.3, 6.05), (-0.15, 6.01)], 0.15),
    ('A', [(-2.3, 6.55), (-1.25, 6.55)], 0.15),
    ('GHA_D', [(-2.95, 7.2), (-2.78, 7.03), (-0.32, 7.03)], 0.1),
    ('BSTA', [(-3.45, 7.2), (-3.45, 7.70), (-1.25, 7.70), (-1.25, 7.51)], 0.15),
]
# the strip between the driver's FET-side pins and the FETs (x0, y0, x1, y1
# on the driver's scale, like DRIVE_PARTS): no other part's via in it
DRIVE_STRIP = (-1.85, 3.3, 1.45, 7.95)
if DRV_TURN:
    DRIVE_STRIP = (-2.6, 7.3, 2.2, 9.3)    # the band between the driver and the high sides
DRIVE_VIAS = []
# fixed copper round the FC side's regulator (board-centre mm, layer,
# width): its input pin 6 to its capacitor and round the pins to pin 4
# (EN) - the lane between the pins and the capacitor rounds shut on the
# router's grid
# the gyro's SPI bus, drawn once and fixed (board-centre mm): its pin
# order crosses the FC MCU's, so MOSI and MISO drop through vias in their own
# MCU pads and come back up beyond the gyro; the router never found that
# alone in the crowded corner
SPI_TRACKS = [
    ('SPI1_MISO', 'F.Cu', [(8.7777, 2.6086), (8.8027, 2.5836)], 0.1),
    ('SPI1_MISO', 'F.Cu', [(7.3527, 2.5586), (7.4027, 2.6086)], 0.1),
    ('SPI1_MISO', 'F.Cu', [(7.2777, 2.5586), (7.3527, 2.5586)], 0.1),
    ('SPI1_MISO', 'F.Cu', [(7.4027, 2.6086), (8.7777, 2.6086)], 0.1),
    ('SPI1_MISO', 'F.Cu', [(7.2777, 2.5586), (7.2558, 2.5609)], 0.1),
    ('SPI1_MISO', 'In5.Cu', [(4.1027, 2.5836), (3.7777, 2.2586)], 0.1),
    ('SPI1_MISO', 'In5.Cu', [(8.8027, 2.5836), (4.1027, 2.5836)], 0.1),
    ('GYRO_CS', 'F.Cu', [(4.6527, 1.46), (3.9527, 0.76)], 0.1),
    ('GYRO_CS', 'F.Cu', [(5.1527, 1.46), (4.6527, 1.46)], 0.1),
    ('GYRO_CS', 'F.Cu', [(5.1527, 1.46), (5.2371, 1.5003)], 0.1),
    ('SPI1_SCK', 'F.Cu', [(3.9527, 2.6265), (3.9208, 2.659)], 0.1),
    ('SPI1_SCK', 'F.Cu', [(5.5527, 1.8765), (4.8027, 2.6265)], 0.1),
    ('SPI1_SCK', 'F.Cu', [(5.5527, 1.8765), (5.5906, 1.8538)], 0.1),
    ('SPI1_SCK', 'F.Cu', [(4.8027, 2.6265), (3.9527, 2.6265)], 0.1),
    ('SPI1_MOSI', 'F.Cu', [(8.55, 3.325), (9.325, 4.1)], 0.1),
    ('SPI1_MOSI', 'F.Cu', [(6.25, 2.225), (7.35, 3.325)], 0.1),
    ('SPI1_MOSI', 'F.Cu', [(6.25, 2.225), (6.2438, 2.2188)], 0.1),
    ('SPI1_MOSI', 'F.Cu', [(7.35, 3.325), (8.55, 3.325)], 0.1),
    ('SPI1_MOSI', 'F.Cu', [(9.325, 4.1), (9.625, 4.1)], 0.1),
    ('SPI1_MOSI', 'In3.Cu', [(4.125, 1.775), (3.625, 1.775)], 0.1),
    ('SPI1_MOSI', 'In3.Cu', [(9.625, 4.1), (6.45, 4.1)], 0.1),
    ('SPI1_MOSI', 'In3.Cu', [(6.45, 4.1), (4.125, 1.775)], 0.1),
]
SPI_VIAS = [
    ('SPI1_MISO', 3.7777, 2.2586),
    ('SPI1_MISO', 8.8027, 2.5836),
    ('SPI1_MOSI', 9.625, 4.1),
    ('SPI1_MOSI', 3.625, 1.775),
]
FC_TRACKS = [
    ('+5V', 'F.Cu', [(5.61, 4.75), (6.62, 4.74)], 0.2),
    ('+5V', 'F.Cu', [(5.61, 4.75), (6.1, 4.75), (6.1, 6.05), (5.61, 6.05)], 0.15),
]


def drive_gap():
    """The gap between each driver's MCU-facing pin row (its high-side
    inputs, GHA and BSTA) and its ESC MCU, in template (u0, r0, u1, r1):
    the driver's bootstrap A and gate A traces leave along it, so no
    other part's plane via may stand in it."""
    return (-6.6, drv(7.45), -1.0, 8.8 + UE_SHIFT - 1.95)


def template():
    """channel role -> (u, r, rotation, side) for the rear channel."""
    t = {}
    for ph, u in PH_U.items():
        # bottom, rotation 180: the source/gate row towards the edge (+r),
        # the drain tab inwards (-r); the gate pin at the row's -u end
        t['Q%sH' % ph] = (u, R_HS, 180, 'B')
        t['Q%sL' % ph] = (u, R_LS, 180, 'B')
        t['P_M%s' % ph] = (PAD_U[ph], R_PAD, 0, 'T')
        # bridge capacitor on top, lying along the edge over the high side's
        # drain: its VBAT pad takes vias straight down into that drain,
        # its sense-node pad vias to the channel's return pour inside
        # (pads at u and u + 1.9: the return via drops between two high
        # sides' drain pins)
        t['bridge ' + ph] = (u + 0.95, 8.0, 0, 'T')
    # driver (bottom) behind the FETs, its FET-side pins (13-18: GH, BST,
    # SH) towards them, the low-side gate pins (9-11) towards +u and the
    # inputs towards the MCU.  It spans u -3.26 .. 1.44: the four drivers
    # pinwheel clear of each other round the centre.
    t['U_D'] = (DRV_U, drv(DRV_R), DRV_ROT, 'B')
    # bootstrap capacitors (bottom), each straddling its phase's high-side
    # gate pin: the driver's pins run BSTx, GHx, SHx side by side, so the
    # capacitor's pads (0.4 mm apart) stand in front of BST and SH and the
    # gate trace leaves straight out between them.  B and C in front of
    # the FET-side row (pins 13-18), A beside the corner (pins 18-20).
    for key, (x, y, a, side) in ({} if DRV_TURN else DRIVE_PARTS).items():
        if GL_PACK and key.startswith('gate low'):
            continue                     # the packer sets them, clear of the FC MCU
        t[key] = (x, drv(y), a, side)
    # MCU beside the high-side row at the -u end, its gate outputs (pins
    # 13-21) facing the driver, its comparator side (22-28) the FETs.  It
    # sits on the FETs' copper, so its temperature sensor (AM32's thermal
    # limit) reads the power stage.  It stops short of r 11.27: the left
    # channel's copy keeps clear of the USB-C's front locating peg.
    t['U_E'] = (-4.95, 8.8 + UE_SHIFT, 180, 'B')
    # shunt along the edge at the -u end, sense-node pad (1) towards the
    # FETs; amplifier between it and the corner
    t['R_S'] = (-6.6, 15.15, 180, 'B')
    t['U_A'] = (-8.6, 12.6, 0, 'B')
    return t


def channel_template(n):
    """template() with channel n's own exceptions (the left channel's
    motor pads)."""
    t = template()
    if n == 3:
        for ph, u in PAD_U_LEFT.items():
            t['P_M%s' % ph] = (u, R_PAD_LEFT, 0, 'T')
    return t


def usb_pegs():
    """Board positions of the USB-C's two locating-peg holes (they go
    through the board: nothing on the bottom may sit on them)."""
    x, y, rot, side = fixed()['J_USB']
    a = math.radians(rot)
    out = []
    for lx, ly in ((2.89, -1.18), (-2.89, -1.18)):
        out.append((round(x + lx * math.cos(a) + ly * math.sin(a), 3),
                    round(y - lx * math.sin(a) + ly * math.cos(a), 3)))
    return out


# ----------------------------------------------------------------- the rest
def fixed():
    """ref/role -> (x, y, rotation, side): everything else that decides the
    floor plan.  The packer places the rest round these."""
    p = {}
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
        p['H%d' % i] = (sx * pcb.HOLE, sy * pcb.HOLE, 0, 'T')
    # rear edge, left half: battery pads (top), - outboard: it stands over
    # the rear channel's shunt ground pad and shares its vias
    p['P_BAT-'] = (-7.85, 14.05 + D, 0, 'T')
    p['P_BAT+'] = (-3.6, 14.05 + D, 0, 'T')
    # left edge, front half: USB-C, its mouth 1 mm past the edge.  Its
    # front shell pads stop at the front-left grommet's keepout; its pegs
    # land in the left channel's peg lane.
    p['J_USB'] = (-12.9 - D, -3.45, 270, 'T')
    # the CC pull-downs lying in line with their contacts (A5 at y -4.70,
    # B5 at y -1.70): each joins its contact with a short straight track
    p['CC1 Rd'] = (-9.3 - D, -4.70, 0, 'T')
    p['CC2 Rd'] = (-9.3 - D, -1.70, 0, 'T')
    # front edge, right half: receiver pads; right edge, rear half: aux.
    # One row 0.9 mm in from the edge: past the grommet keepout, and clear
    # of the shunt vias underneath (power.py)
    for k, ref in enumerate(('P_T2', 'P_R2', 'P_G', 'P_5V')):
        p[ref] = place(180, -8.6 + 1.7 * k, 16.1) + (0, 'T')
    for k, ref in enumerate(('P_BZ-', 'P_BZ+', 'P_LED', 'P_R1', 'P_T1')):
        p[ref] = place(90, -9.9 + 1.7 * k, 16.1) + (0, 'T')
    # flight controller: MCU at the centre, over the four drivers' middle.
    # Round it, a field beside each driver (r 3.8-9, beside the driver on
    # its low-side gate pins' side; layout.DRIVE_VIAS) takes that
    # channel's gate vias, so no part of the FC stands there: the crystal
    # to the MCU's left (its oscillator pins), the gyro to its right (SPI1)
    p['U_FC'] = (0.0, 0.0, 0, 'T')
    p['U_IMU'] = (6.6, 1.0, 135, 'T')   # firmware/README: TAKERG4AIO's CW270 + board yaw 45
    # the reset filter capacitor right under NRST (pin 7), clear of the
    # ESC signal pins (8-11) beside it
    p['U_FC reset filter'] = (0.25, 5.0, 270, 'T')
    # the beeper's gate resistor at the MCU's beeper pin (38); the one
    # long line runs from it to the switch by the beeper pads
    p['beeper gate'] = (-5.0, -2.25, 180, 'T')
    p['Y1'] = (-2.0, 6.5, 270, 'T')     # below the MCU's oscillator pins (5, 6): HSE_IN (1) top left, a lane above it
    # 5 V BEC front right, its inductor beside it (switch pins facing),
    # with room between for the bootstrap and VCC capacitors at their pins
    p['U_BEC'] = (2.45, -8.6, 0, 'T')
    p['L_BEC'] = (6.9, -8.6, 180, 'T')
    # its bootstrap capacitor between the SW (5) and BOOT (6) pins and the
    # inductor; the VCC capacitor below, reached past the 5 V pin (8)
    p['BEC bootstrap'] = (4.35, -7.9, 270, 'T')
    p['BEC VCC'] = (4.3, -10.6, 90, 'T')
    # the three regulators, each with its own capacitors (and the
    # gate-drive LDO's feedback divider) right at its pins: the packer
    # would otherwise find them room only millimetres away
    p['U_LDO'] = (4.58, 5.39, 0, 'T')
    p['FC LDO in'] = (6.62, 5.22, 270, 'T')        # +5V pad beside pin 6
    p['FC LDO out'] = (2.0, 6.0, 270, 'T')         # +3V3 pad beside pins 1-2
    p['U_LDOE'] = (-4.02, 10.19, 0, 'T')
    p['ESC LDO out'] = (-6.6, 10.45, 270, 'T')     # +3V3E pad beside pin 1
    p['ESC LDO in'] = (-1.95, 10.05, 270, 'T')     # +5V pad beside pin 6
    p['U_GVDD'] = (-7.2, 4.39, 90, 'T')
    p['gate-drive LDO input'] = (-7.2, 1.45, 0, 'T')            # over the input pins 5-8
    p['gate-drive LDO feedback top'] = (-7.86, 6.95, 0, 'T')    # under pins 1 (out) and 2 (FB)
    p['gate-drive LDO feedback bottom'] = (-7.0, 7.85, 0, 'T')
    # the two LEDs and the beeper switch at their spots, so the resistors
    # anchored to their pins are packed beside them
    p['LED_PWR'] = (6.5, -6.0, 0, 'T')
    p['LED_STAT'] = (6.5, -4.6, 0, 'T')
    p['Q_BZ'] = (11.5, 4.5, 0, 'T')
    return p


# The flag of the United States (flag.py), top side, front right: between
# the BEC and the front channel's shunt vias, clear of the front-right
# grommet.  Copper there is a ground plate of its own; no via, no track.
# The flag is not reserved before routing: it goes where routing leaves
# the largest ground-only spot (silk.flag_spot).  A reservation here
# (dict(hoist, x, y, side)) keeps parts, tracks and vias off its box.
FLAG = None


def flag_box(margin=0.0):
    """The flag's plate (0.15 mm round the flag) plus `margin`, as
    (x0, y0, x1, y1) in board mm."""
    import flag
    w, h = flag.B * FLAG['hoist'] / 2 + 0.15 + margin, FLAG['hoist'] / 2 + 0.15 + margin
    return (FLAG['x'] - w, FLAG['y'] - h, FLAG['x'] + w, FLAG['y'] + h)


def hint():
    """ref -> (x, y, rotation, side): where the packer should try first
    for parts that have no one pin to sit beside."""
    return {
        'D_TVS': (-4.8, 11.0, 90, 'T'),
        # gate-drive LDO on top, over the free strip beside the rear
        # channel's driver: its 11 V and battery vias drop there, clear of
        # the FC MCU (no via under it) and of the drivers' strips
        'U_GVDD': (-8.2, 4.4, 0, 'T'),
        'U_LDO': (4.6, 5.4, 0, 'T'), 'U_LDOE': (-4.0, 10.2, 0, 'T'),
        'U_ESD': (-7.8, -6.6, 90, 'T'), 'D_USB': (-7.6, -1.6, 90, 'T'),
        'SW_BOOT': (-6.4, -8.0, 0, 'T'), 'Q_BZ': (11.5, 4.5, 0, 'T'),
        'LED_PWR': (6.5, -6.0, 0, 'T'), 'LED_STAT': (6.5, -4.6, 0, 'T'),
    }


def channel_parts(comps):
    """{channel: {key: reference}}: every part that belongs to one channel,
    under a key that names its place in the template whatever the channel
    (stamp.py routes channel 1 alone and copies the routing)."""
    import re
    out = {n: {} for n in CHANNELS}
    for c in comps:
        n = None
        if ':' in c.role and c.role.split(':', 1)[0].isdigit():
            n, key = c.role.split(':', 1)
            n = int(n)
            # roles name their channel's chips too ('U_E1 VDD', 'ESC 1 vsense top')
            key = re.sub(r'(?<![0-9])%d(?![0-9])' % n, '#', key)
        else:
            m = re.match(r'^(Q|P_M)(\d)([ABC][HL]?)$', c.ref) or re.match(r'^(U_D|U_E|U_A|R_S|TP_D|TP_C)(\d)()$', c.ref)
            if m:
                n, key = int(m.group(2)), m.group(1) + '#' + m.group(3)
        if n in out:
            out[n][key] = c.ref
    keys = set(out[1])
    for n in CHANNELS:
        if set(out[n]) != keys:
            raise SystemExit('channel_parts: channel %d differs: %s' % (n, sorted(set(out[n]) ^ keys)))
    return out


# Freerouting passes for the one channel routed alone (stamp.py)
STAMP_PASSES = 30
