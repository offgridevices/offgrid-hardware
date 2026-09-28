# -*- coding: utf-8 -*-
"""Ridge 3 ESC (36 x 36 mm, 25.5 mm holes): placement, power copper,
planes and silkscreen.

One motor channel is drawn once, as a template for the REAR edge, and
stamped four times by rotation: M1 rear, M2 right, M3 left, M4 front.  All
four channels are the same copper, turned.

Template axes: u along the edge (board x for the rear channel), yr towards
the edge (board y; the rear edge is at yr = +18).

The power stage of each phase is a vertical half-bridge:
  * the HIGH-side FET on the top, source pins towards the edge.  Its source
    pins and a top pour run straight out to the phase's motor pad; its
    drain tab carries the battery (VBAT plane on In4) through filled vias;
  * the LOW-side FET on the bottom, 2.4 mm further out, source pins
    inwards.  Its drain tab lies under the top switch-node pour and joins
    it through filled vias in the tab;
  * the bridge capacitor on the bottom, under the high-side drain: its
    VBAT pad takes a via straight up into that drain tab, its other pad
    sits at the low-side source pins.  The switching loop closes through
    the board's thickness.
The low-side sources of a channel return to ground through its current
shunt: they, the bridge capacitors' return pads and the shunt meet on the
bottom and on a pour on In3 under the channel ("M<n>_SRC").  The shunt
stands in the channel's corner slot (+u end, bottom), between the FET row
and the mounting hole; its amplifier sits inside it.

Behind the power stage, on the bottom: the gate driver and the MCU side by
side (each channel's pair turned like a pinwheel, so the four pairs clear
each other at the centre), with their small parts round them.  The top
carries the high-side FETs, the motor and battery pads, the stack
connector in the middle and the small parts that fit round it.

Stackup (6 layers): F signals + power | In1 GND | In2 signals |
In3 signals + channel return pours | In4 VBAT | B signals + power.
"""
import math, os
import pcbnew
import pcb, circuit, parts
from pcb import MM

H = pcb.HALF
PITCH = 5.0          # phase spacing: a 1.7 mm gap between FETs for the channel's vias
PH_U = {'A': -PITCH, 'B': 0.0, 'C': PITCH}
Y_HS = 12.3          # high-side FET centre (top)
Y_LS = 14.7          # low-side FET centre (bottom), its drain under the motor pad
Y_CAP = 10.65        # bridge capacitor row (bottom), under the high-side drain pins
Y_PAD = 16.4         # motor pads (top)
Y_CHIP = 7.2         # driver and MCU row (bottom)

# channel: rotation of the rear-edge template (degrees, KiCad's sense)
CHANNELS = {1: 0, 2: 90, 3: -90, 4: 180}


def xf_point(n, u, yr):
    a = math.radians(CHANNELS[n])
    return (u * math.cos(a) + yr * math.sin(a), -u * math.sin(a) + yr * math.cos(a))


def xf(n, u, yr, rot, side):
    x, y = xf_point(n, u, yr)
    return (round(x, 4), round(y, 4), (rot + CHANNELS[n]) % 360, side)


def template():
    """role -> (u, yr, rotation, side) for the rear-edge channel."""
    t = {}
    for ph, u in PH_U.items():
        t['Q%sH' % ph] = (u, Y_HS, 0, 'T')
        t['Q%sL' % ph] = (u, Y_LS, 0, 'B')
        t['P' + ph] = (u, Y_PAD, 0, 'T')
        # bridge capacitor along the row: VBAT pad (1) at +u, its return
        # pad at -u, straight above the low-side source pins 1 and 2
        t['CBR_' + ph] = (u, Y_CAP, 180, 'B')
    # back-EMF: the phase-side 20k resistors on the bottom beside the
    # low-side drains they tap: in each gap between two phases one
    # standing (courtyards leave room for one) and one lying across the
    # gap's outer end, and one standing in each end slot.  Each one's
    # phase end reaches its own drain copper through a short tab
    # (power_copper); pin 1 is the phase end.
    ga, gb = (PH_U['A'] + PH_U['B']) / 2, (PH_U['B'] + PH_U['C']) / 2
    t['RBH_A'] = (ga, Y_LS + 0.7, 90, 'B')
    t['RN_B'] = (ga, Y_LS + 2.6, 180, 'B')
    t['RBH_B'] = (gb, Y_LS + 0.7, 90, 'B')
    t['RN_C'] = (gb, Y_LS + 2.6, 180, 'B')
    t['RN_A'] = (PH_U['A'] - 2.36, Y_LS + 0.7, 90, 'B')
    t['RBH_C'] = (PH_U['C'] + 2.36, Y_LS + 0.7, 90, 'B')
    # Driver and MCU side by side on the bottom behind the FET row.  The
    # pair spans u -5.04 .. 4.8: the next channel's pair starts at
    # Y_CHIP - 2.35 = 4.85, so the four pairs pinwheel round the centre.
    # Driver turned with its gate, bootstrap and switch-node pins facing
    # the FETs; MCU with its supply and reset pins facing the centre.
    t['GD'] = (-2.69, Y_CHIP, 270, 'B')
    t['MCU'] = (2.38, Y_CHIP, 0, 'B')
    # a row of capacitors inside the chips, on the bottom, turned 90
    # degrees: the driver's gate-drive supply capacitors at its supply pin
    # (it faces the centre), the MCU's 100 nF at its supply pins (they face
    # the centre too).  The MCU's reset capacitor goes on top, over its
    # reset pin.
    t['C_GVHF'] = (-2.45, 3.7, 90, 'B')
    t['C_GV'] = (-1.25, 3.7, 90, 'B')
    t['C_VDD'] = (1.85, 3.7, 90, 'B')
    # The bootstrap capacitors (0201) on top over the driver, inside the
    # ring of its pins' escape vias, each across its BST and SH pins' vias
    # (bootstrap_stubs): the bootstrap loop is as short as it gets, and
    # nothing in the ring has to get out.
    t['CBS_A'] = (-4.05, 8.3, 270, 'T')
    t['CBS_B'] = (-2.94, 8.5, 0, 'T')
    t['CBS_C'] = (-1.45, 8.5, 0, 'T')
    # the MCU's reset capacitor on top, over the MCU's FET end, inside the
    # ring of its pins' escape vias; the rest of the top over the MCU is
    # left to the shared parts
    t['C_RST'] = (2.4, 8.45, 0, 'T')
    # shunt along the row in the diagonal zone at the channel's +u end:
    # its sense-node pad (1) at +u, where the channel's return copper comes
    # in from the FET band, its ground pad inwards
    t['R_SH'] = (8.0, 8.0, 180, 'B')
    # The gate resistors sit at the FETs, in the corridor on each phase's
    # +u side where its gate pins face: the high side's on top, the low
    # side's on the bottom, each upright with its gate end towards the
    # FET's gate pin and a via in its driver end (gate_cells).  The driver
    # nets then run out from the driver's escape vias on the inner layers;
    # nothing has to get out of the ring of vias round the driver's pins
    # (they wall it in on every layer), which stays free for its ground
    # pad's plane vias.  In the diagonal zone at the +u end, over the
    # shunt: the current amplifier and its supply capacitor.
    for ph, u in PH_U.items():
        t['RGH_' + ph] = (u + GATE_CELL[0], GATE_CELL[1], 270, 'T')
        t['RGL_' + ph] = (u + GATE_CELL[0], GATE_CELL[2], 90, 'B')
    # SWD test points on top, the side that faces the flight controller
    # (the bootloader is flashed once, before the stack goes together), at
    # the board's edge in the gaps either side of motor pad B: a clip
    # reaches them there, and the middle of the board has no room left.
    # Clock left, data right.
    t['TP_DIO'] = (2.5, 16.3, 0, 'T')
    t['TP_CLK'] = (-2.5, 16.3, 0, 'T')
    # the back-EMF dividers' low legs, the neutral's leg to ground and the
    # current filter's resistor end on the MCU's pins: one row of upright
    # 0201s on the bottom, in the strip between the MCU, the next channel's
    # driver and the shunt, the neutral's nearest its pin (PA3)
    # The current filter's resistor stands straight under the amplifier's
    # output pin, turned so its input end is there: the output drops onto
    # it through a via in its own pad (kelvin_pins), no routing.
    for i, role in enumerate(('RNG', 'RBL_C', 'RBL_A', 'R_IF', 'RBL_B')):
        t[role] = (5.41 + 0.9 * i, 5.99, 270 if role == 'R_IF' else 90, 'B')
    # the current amplifier on top over the shunt's sense end, clear of the
    # shunt's ground vias (reserved), its supply capacitor beside its
    # supply pin, clear of the sense vias below the shunt's sense pads
    t['U_CS'] = (8.9, 7.1, 0, 'T')
    t['C_CS'] = (10.7, 8.0, 90, 'T')
    t['C_IF'] = (5.6, 6.1, 90, 'T')
    # the CUR-average resistor from the amplifier's output, beside the
    # filter, upright: lying, it covers the next channel's driver pins
    t['R_CUR'] = (6.9, 5.6, 90, 'T')
    return t


def roles(comps, n):
    """Map template roles to this channel's references."""
    out = {}
    blk = 'esc%d' % n
    for c in comps:
        note, ref = c.note, c.ref
        if c.block != blk and note != 'CUR average %d' % n:
            continue
        if ref == 'U_ESC%d' % n: out['MCU'] = ref
        elif ref == 'U_GD%d' % n: out['GD'] = ref
        elif ref == 'R_SH%d' % n: out['R_SH'] = ref
        elif ref == 'U_CS%d' % n: out['U_CS'] = ref
        elif ref.startswith('Q%d' % n): out['Q' + ref[-2:]] = ref
        elif ref.startswith('P_M%d' % n): out['P' + ref[-1]] = ref
        elif ref == 'TP_E%d_DIO' % n: out['TP_DIO'] = ref
        elif ref == 'TP_E%d_CLK' % n: out['TP_CLK'] = ref
        elif note == 'U_ESC%d VDD' % n: out['C_VDD'] = ref
        elif note == 'U_ESC%d reset filter' % n: out['C_RST'] = ref
        elif note == 'driver GVDD': out['C_GV'] = ref
        elif note == 'driver GVDD HF': out['C_GVHF'] = ref
        elif note.startswith('bootstrap '): out['CBS_' + note[-1]] = ref
        elif note.startswith('gate high '): out['RGH_' + note[-1]] = ref
        elif note.startswith('gate low '): out['RGL_' + note[-1]] = ref
        elif note.startswith('bridge '): out['CBR_' + note[-1]] = ref
        elif note.startswith('BEMF '):
            out[('RBH_' if c.part == 'R20K' else 'RBL_') + note[-1]] = ref
        elif note.startswith('neutral to'): out['RNG'] = ref
        elif note.startswith('neutral '): out['RN_' + note[-1]] = ref
        elif note == 'U_CS%d supply' % n: out['C_CS'] = ref
        elif note == 'current filter':
            out['R_IF' if c.part.startswith('R') else 'C_IF'] = ref
        elif note == 'CUR average %d' % n: out['R_CUR'] = ref
        else:
            raise KeyError('unplaced role for %s (%s)' % (ref, note))
    return out


def channel_parts(comps):
    """{channel: {role: reference}}: the parts stamp.py routes as one."""
    return {n: roles(comps, n) for n in CHANNELS}


# Freerouting passes for the one channel routed alone (stamp.py)
STAMP_PASSES = 30



# ---------------------------------------------------------------- global parts
# By note (first match, in circuit order).  Battery pads: plated through
# holes in the rear edge's two corner slots, outside motor 1's pads and
# FETs (+ left, - right).
BAT_U, BAT_YR = 9.5, 16.1
GLOBAL = {
    'P_BAT+': (-BAT_U, BAT_YR, 0, 'T'),
    'P_BAT-': (BAT_U, BAT_YR, 0, 'T'),
    # The stack connector turned half round, its pins towards motor 1: its
    # two mechanical tabs then land between the escape vias of channels 2's
    # and 3's chips (the tabs' band, |y| < 1.65, is the only one free of
    # them on both sides), and the strip in front of it takes the supplies
    'J_FC': (0.0, 1.8, 180, 'T'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
    # in that strip, left to right: the buck's input and output capacitors,
    # the buck, the gate-drive LDO and its output capacitor; the buck's
    # inductor fills the bottom's centre, under the buck, inside the four
    # channels' capacitor rows
    'L1': (0.0, 0.0, 0, 'B'),
    'U_BUCK': (-0.6, -2.2, 0, 'T'),
    'U_GVDD': (2.6, -3.1, 90, 'T'),
    'LED_PWR': (16.8, 13.2, 90, 'T'),
    # the SWD lead's supply, clock and ground pads in the rear edge's other
    # gaps, in one row with motor 1's SWDIO pad: 3V3, CLK, (motor pads),
    # DIO 1, GND
    'TP_3V3': (-7.3, 16.3, 0, 'T'),
    'TP_GND': (7.3, 16.3, 0, 'T'),
}
GLOBAL_BY_NOTE = {
    'buck input': (-3.7, -1.85, 0, 'T'),
    'buck output': (-3.7, -4.0, 0, 'T'),
    'buck VCC': (-0.6, -4.3, 0, 'T'),
    'gate-drive LDO output': (6.3, -2.7, 90, 'T'),
    'gate-drive LDO feedback top': (4.9, -5.1, 0, 'T'),
    'gate-drive LDO feedback bottom': (6.6, -5.1, 0, 'T'),
    # behind the stack connector, over motor 1's MCU: the LDO's input
    # filter, the CUR filter and the battery divider
    'gate-drive LDO input': (2.4, 6.6, 0, 'T'),
    'gate-drive LDO input filter': (2.4, 4.6, 0, 'T'),
    'CUR filter': (0.9, 4.85, 90, 'T'),
    'ESC vsense top': (-3.6, 4.6, 0, 'T'),
    'ESC vsense bottom': (-2.1, 4.6, 0, 'T'),
    'ESC vsense filter': (-0.8, 4.6, 90, 'T'),
    'power LED': (16.8, 15.4, 90, 'T'),
}


def placement(comps):
    place = {}
    for ref, p in GLOBAL.items():
        place[ref] = p
    for c in comps:
        if c.ref in place or c.note not in GLOBAL_BY_NOTE:
            continue
        place[c.ref] = GLOBAL_BY_NOTE[c.note]
    t = template()
    for n in CHANNELS:
        for role, ref in roles(comps, n).items():
            place[ref] = xf(n, *t[role])
    return place


FIXED_ROLES = ('QAH', 'QBH', 'QCH', 'QAL', 'QBL', 'QCL', 'PA', 'PB', 'PC', 'CBR_A', 'CBR_B', 'CBR_C',
               'GD', 'MCU', 'R_SH', 'RBH_A', 'RBH_B', 'RBH_C', 'RN_A', 'RN_B', 'RN_C',
               'RGH_A', 'RGH_B', 'RGH_C', 'RGL_A', 'RGL_B', 'RGL_C', 'CBS_A', 'CBS_B', 'CBS_C')


# global parts that stay exactly where the table puts them; the others
# are only hints for the packer
GLOBAL_FIXED = ('P_BAT+', 'P_BAT-', 'J_FC', 'H1', 'H2', 'H3', 'H4')


# Packing order: the parts that must sit at a channel chip's pins first,
# then the supplies' chips and inductor, then their other parts, then the
# rest (filters, dividers, test points).  A supply's parts move with their
# chip (pack_anchor).
def pack_priority(c):
    # the channels' parts first: the template places every one of them
    # clear of the others, so they keep their spots.  Then the shared
    # parts in what is left, the supplies first, while there is room for
    # them: the 3.3 V buck and its inductor, then the gate-drive
    # LDO, each chip before (it is larger) the parts that belong at its
    # pins, which follow it (pack_anchor)
    if c.block.startswith('esc') or c.note.startswith('CUR average '):
        return -10
    if c.ref == 'U_BUCK' or (c.block == 'power' and 'buck' in c.note):
        return -3
    if c.ref == 'U_GVDD' or (c.block == 'power' and 'gate-drive LDO' in c.note):
        return -2
    if c.note.startswith(('bootstrap ', 'driver GVDD')) or c.note.endswith((' VDD', ' VDD bulk', ' supply')) \
            or 'current amplifier' in c.note:
        return 0
    if c.ref in ('U_BUCK', 'U_GVDD'):
        return 1
    if c.block == 'power' and ('buck' in c.note or 'gate-drive LDO' in c.note):
        return 2
    return 3


def pack_anchor(c):
    if c.block == 'power' and c.ref not in ('U_BUCK', 'L1') and 'buck' in c.note:
        return 'U_BUCK'
    if c.block == 'power' and c.ref != 'U_GVDD' and 'gate-drive LDO' in c.note:
        return 'U_GVDD'
    if c.note.startswith('U_CS') and c.note.endswith(' supply'):
        return 'U_CS' + c.note[4]
    return None


# An IC's exposed pad on a plane net can take its ground vias inside the
# pad; the packer then keeps the far side under it free (legalize.pack's
# `through`).  None of this board's movable ICs needs it: the gate-drive
# LDO (TPS7A1601, VSON-8) dissipates at most about 0.3 W ((25.2 - 11.3) V
# x 22 mA: four drivers' gate charge at 48 kHz plus their quiescent
# current), which its pad soldered to the top ground copper, with its
# ground vias beside it, carries.  EP_AREA sets the size above which an
# exposed pad would count.
EP_AREA = 1e9
_via_pads = {}


def via_pads(c):
    if c.ref not in _via_pads:
        out = []
        if c.ref.startswith('U'):
            fpid = {**parts.PARTS, **parts.PADS}[c.part]['fp']
            for p in pcb.load_fp(fpid).Pads():
                sz = p.GetSize(pcbnew.F_Cu)
                if c.pins.get(p.GetNumber()) in ('GND', 'VBAT') and sz.x * sz.y / 1e12 >= EP_AREA:
                    out.append(p.GetNumber())
        _via_pads[c.ref] = out
    return _via_pads[c.ref]


# parts that work equally well on either side (a via costs them nothing):
# the current and voltage filters, the dividers and the power LED
EITHER_SIDE = ('current filter', 'CUR filter', 'ESC vsense top', 'ESC vsense bottom', 'ESC vsense filter',
               'power LED')


def either_side(c):
    return c.note in EITHER_SIDE


def escape_keep(comps, place):
    """Where the MCUs' and drivers' signal vias come through to the far
    side, so no other part puts a pad there: each signal pin that leaves its
    side of the board has its via in the pad at the pad's outer end
    (VIA_ESCAPE, fanout.dogbones).  Each spot is the via plus 0.1 mm, and
    takes a pad of the via's own net.  The
    drivers' ground-pad vias are not kept: they are plane vias, parts may
    sit over them, and the fan-out drops any a far-side pad covers."""
    import legalize
    allp = {**parts.PARTS, **parts.PADS}
    out = []

    def spot(far, x, y, d, net):
        r = d / 2 + 0.1
        out.append((far, (x - r, y - r, x + r, y + r), net))
    for n in CHANNELS:
        r = roles(comps, n)
        for role in ('MCU', 'GD'):
            c = next(c for c in comps if c.ref == r[role])
            x, y, rot, side = place[c.ref][:4]
            far = 'B' if side == 'T' else 'T'
            for num, bb, th in legalize.pad_boxes(allp[c.part]['fp'], rot, side):
                net = c.pins.get(num)
                px, py = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                w, h = bb[2] - bb[0], bb[3] - bb[1]
                if net not in (None, 'GND', 'VBAT'):
                    # outward along the pad's long axis, as fanout.dogbones puts it
                    if abs(px) >= abs(py):
                        s_ = max(0.0, w / 2 - VIA_ESCAPE[0] / 2 - 0.08)
                        vx, vy = px + (s_ if px > 0 else -s_), py
                    else:
                        s_ = max(0.0, h / 2 - VIA_ESCAPE[0] / 2 - 0.08)
                        vx, vy = px, py + (s_ if py > 0 else -s_)
                    spot(far, x + vx, y + vy, VIA_ESCAPE[0], net)
    return out


def fixed(comps):
    """Every channel part stays exactly on its turned template spot (the
    packer's grid would move a part a few hundredths differently in each
    channel, and the channels are routed as one, stamp.py); the shared parts
    pack round them."""
    f = set(GLOBAL_FIXED)
    for n in CHANNELS:
        f |= set(roles(comps, n).values())
    return f


def build_placed(out_path, legal=True, strict=True):
    b = pcb.new_board(LAYERS)
    # 0.04 mm solder-mask expansion: the MCU's 0.5 mm-pitch corner pads
    # keep a 0.12 mm mask web (0.05 leaves exactly the 0.1 minimum)
    b.GetDesignSettings().m_SolderMaskExpansion = MM(0.04)
    pcb.outline(b)
    comps = circuit.build('esc')
    place = placement(comps)
    missing = [c.ref for c in comps if c.ref not in place]
    if missing:
        raise KeyError('no placement for %s' % missing)
    if legal:
        import legalize
        # the passives and the two supply chips may turn 90 degrees to fit
        turn = lambda c: (c.ref[:1] in 'RC' and not c.ref.startswith(('R_SH', 'CBR'))) or c.ref in ('U_BUCK', 'U_GVDD')
        place, left = legalize.pack(comps, place, fixed(comps), rotatable=turn, reserved=reserved(),
                                    priority=pack_priority, anchor=pack_anchor, through=via_pads, flip=either_side,
                                    pad_keep=escape_keep(comps, place))
        if left and strict:
            raise SystemExit('no room for %s' % left)
    fps = pcb.place_components(b, comps, place)
    b.Save(out_path)
    return b, comps, fps


# ============================================================ power copper
# All in template coordinates (u, yr), stamped for every channel.  Zones
# connect solidly (no thermal spokes): these are current paths.
# Every via keeps a 0.1 mm ring, so copper at the usual 0.1 mm clearance
# is 0.2 mm from its hole: JLCPCB's multilayer via-hole-to-track minimum.
VIA_SIG = (0.35, 0.15)         # signal vias (routers, escapes)
VIA_INPAD = (0.45, 0.25)       # plane vias in pads (POFV, filled and capped)
VIA_PWR = (0.5, 0.3)           # power vias: FET tabs, motor pads, returns
# QFN escapes: a via inside the pin's own pad, at its outer end, filled and
# capped with the rest (JLCPCB multilayer minimum 0.15 mm hole / 0.25 mm
# via; POFV takes 0.15-0.55 mm).  The chips sit too close to their
# neighbours for a ring of dog-bone vias beside the pins.  Its ring is
# 0.05 mm, so other copper keeps 0.15 mm from it (VIA_RING: the routers
# see it with a 0.1 mm ring).
VIA_ESCAPE = (0.25, 0.15)
HOLE_CL = 0.2                  # via hole to other copper (JLCPCB multilayer)
# The routers keep only copper clearances (0.1 mm): they see every via with
# at least this ring, so their copper stays HOLE_CL from its hole.
VIA_RING = HOLE_CL - 0.1
# Freerouting may also drop a signal via onto a same-net pad (route.py):
# under the chips both sides are full of parts, and a pad is often the
# only spot left.  Its 0.1 mm ring keeps the hole 0.2 mm from other copper.
VIA_IN_PAD = VIA_SIG

GAPS = (-7.5, -2.5, 2.5, 7.5)  # via corridors: the gaps between phases and both ends
# per corridor, from its centre: one return via on the centre line.  Every
# signal between the driver and MCU and the FETs, the motor pads and the
# back-EMF resistors (gate drives, switch-node taps, back-EMF, neutral, SWD:
# 14 a channel) passes the band of vias across the FET row in these
# corridors, on top and on In2 (In3 carries the return there).  A pair of
# vias passed one track between them a layer; one via passes one either side
# (0.45 mm from its centre keeps a 0.2 mm track 0.2 mm from its hole).  The
# return's layers stay tied by these and the leg's vias at the shunt: the
# bottom's pour alone would not do, the low-side gate stubs cut it at every
# corridor, so each phase's piece reaches the shunt through In3.
SRC_VIA = ((0.0, 11.85),)
# gate resistors (0201, upright): u from the phase centre (the corridor's
# centre line), the high side's yr (top), the low side's yr (bottom).  The
# FETs' gate pins are at +0.97: the high side's at yr 13.98 (top), the low
# side's at 13.02 (bottom).  The low side's courtyard ends 0.02 mm short of
# the back-EMF resistor's below it.
GATE_CELL = (2.5, 13.1, 13.75)
# the top over the driver inside the ring of its pins' escape vias
DRIVER_RING = (-4.45, 5.45, -0.95, 9.0)
VBAT_VIAS = ((0.95, 10.3), (0.95, 11.1), (0.95, 12.0), (0.1, 12.0))    # from the phase centre
SW_VIAS = [(du, yr) for yr in (14.3, 15.1, 15.9) for du in (-0.8, 0.0, 0.8) if (du, yr) != (0.8, 14.3)]
# the return copper's leg from the FET band to the shunt, through the
# channel's +u corner, and a grid of vias in it
SRC_LEG = (6.6, 6.8, 10.6, 13.45)
# (clear of the shunt's Kelvin sense vias below its sense pads, and of the
# corner's grommet keep-out, which takes the sixth spot)
SRC_LEG_VIAS = [(u, yr) for u in (8.3, 9.1, 9.9) for yr in (10.25, 11.05) if (u, yr) != (9.9, 11.05)]
TOP_SW = lambda u: [(u - 1.6, 13.45), (u + 0.55, 13.45), (u + 0.55, 14.55), (u + 1.6, 14.55),
                    (u + 1.6, 17.65), (u - 1.6, 17.65)]
BOT_SRC = [(-7.9, 13.45), (-7.9, 10.75), (-6.7, 10.75), (-6.7, 9.75), (6.6, 9.75), (6.6, 6.8),
           (10.6, 6.8), (10.6, 13.45)]


def reserved():
    """Board regions (side, bbox) the packer keeps free for the channel's
    fixed vias: the corridors, the return leg's via grid, the tops of the
    shunt's ground vias."""
    out = []
    for n in CHANNELS:
        rects = [('TB', (g - 1.05, 11.35, g + 1.05, 14.45)) for g in GAPS]
        # the bottom lanes between the bridge capacitors: the driver's and
        # the MCU's escape vias towards the FETs
        rects += [('B', (g - 1.0, 9.85, g + 1.0, 11.35)) for g in GAPS[1:3]]
        rects += [('TB', (7.9, 9.75, 10.3, 11.45)), ('T', (5.5, 7.1, 7.3, 8.9))]
        # the top over the driver, inside the ring of its escape vias:
        # anything there could not get out (the bootstrap capacitors are
        # fixed there)
        rects += [('T', DRIVER_RING)]
        for sd, (u0, y0, u1, y1) in rects:
            pts = [xf_point(n, u, yr) for u, yr in ((u0, y0), (u1, y1))]
            bb = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
            for side in ('T', 'B') if sd == 'TB' else (sd,):
                out.append((side, bb))
    # the panel's tab zones at the corners
    out += [(side, z) for z in pcb.tab_zones() for side in ('T', 'B')]
    return out


def _cu(side):
    return pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu


def _zone(b, n, net, layer, pts, prio=3, name=None, clearance=0.2):
    poly = [xf_point(n, u, yr) for u, yr in pts]
    return pcb.zone(b, net, layer, poly, clearance=clearance, min_width=0.2, priority=prio,
                    thermal=False, name=name)


def _in_keepout(x, y, r):
    return any(math.hypot(x - sx * pcb.HOLE, y - sy * pcb.HOLE) < pcb.HOLE_KEEPOUT_R + r + 0.05
               for sx in (-1, 1) for sy in (-1, 1))


def _via(b, n, u, yr, net, size, count):
    x, y = xf_point(n, u, yr)
    if _in_keepout(x, y, size[0] / 2):
        return None
    v = pcb.via(b, x, y, net, d=size[0], drill=size[1])
    v.SetLocked(True)
    count[net] = count.get(net, 0) + 1
    return v


def _pad_box(b, ref, num):
    """(u0, yr0, u1, yr1) of a pad, in board mm (not template)."""
    fp = b.FindFootprintByReference(ref)
    pad = next(p for p in fp.Pads() if p.GetNumber() == num)
    bb = pad.GetBoundingBox()
    return (bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY, bb.GetRight() / 1e6 - pcb.CX,
            bb.GetBottom() / 1e6 - pcb.CY)


def _to_template(n, x, y):
    a = math.radians(CHANNELS[n])
    # inverse of xf_point: rotate back
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def power_copper(b, comps):
    """Every channel's half-bridge copper, vias and return path.  Returns
    via counts per net."""
    count = {}
    for n in CHANNELS:
        r = roles(comps, n)
        m = lambda s: 'M%d_%s' % (n, s)
        for ph, u in PH_U.items():
            sw = m(ph)
            # top: switch node from the high-side sources to the motor pad,
            # notched round the gate pin; the drain side is battery
            _zone(b, n, sw, pcbnew.F_Cu, TOP_SW(u), name='switch node')
            _zone(b, n, 'VBAT', pcbnew.F_Cu, [(u - 1.6, 10.15), (u + 1.6, 10.15), (u + 1.6, 13.25),
                                              (u - 1.6, 13.25)], name='high-side drain')
            # bottom: switch node over the low-side drain, reaching out to
            # the phase ends of the back-EMF resistors that tap it
            pts = [(u - 1.6, 13.65), (u + 1.6, 13.65), (u + 1.6, 16.85), (u - 1.6, 16.85)]
            _zone(b, n, sw, pcbnew.B_Cu, pts, name='switch node')
            for c in comps:
                if c.block != 'esc%d' % n or not c.note.startswith(('BEMF ', 'neutral ')) or c.pins.get('1') != sw:
                    continue
                if c.note.startswith('neutral to'):
                    continue
                x0, y0, x1, y1 = _pad_box(b, c.ref, '1')
                q = [_to_template(n, x, y) for x, y in ((x0, y0), (x1, y1))]
                pu0, pu1 = min(q[0][0], q[1][0]), max(q[0][0], q[1][0])
                py0, py1 = min(q[0][1], q[1][1]), max(q[0][1], q[1][1])
                # copper from the pad to the nearest point well inside the
                # pour (0.25 mm in from its edge): the box spanning both, so
                # it overlaps the pour whichever way the pad lies from it
                cu_ = min(max((pu0 + pu1) / 2, u - 1.35), u + 1.35)
                cy_ = min(max((py0 + py1) / 2, 13.9), 16.6)
                if u - 1.6 <= (pu0 + pu1) / 2 <= u + 1.6 and 13.65 <= (py0 + py1) / 2 <= 16.85:
                    continue
                w2 = 0.25
                ua, ub = min(pu0, cu_ - w2), max(pu1, cu_ + w2)
                ya, yb = min(py0, cy_ - w2), max(py1, cy_ + w2)
                tab = [(ua, ya), (ub, ya), (ub, yb), (ua, yb)]
                _zone(b, n, sw, pcbnew.B_Cu, tab, prio=4, name='bemf tab')
            # bottom: battery island round the bridge capacitor's VBAT pad
            # and the high-side drain's vias beside the low-side sources
            _zone(b, n, 'VBAT', pcbnew.B_Cu, [(u + 0.3, 9.75), (u + 1.62, 9.75), (u + 1.62, 12.35),
                                              (u - 0.3, 12.35), (u - 0.3, 11.62), (u + 0.3, 11.62)],
                  prio=5, name='bridge VBAT')
            for du, yr in VBAT_VIAS:
                _via(b, n, u + du, yr, 'VBAT', VIA_PWR, count)
            for du, yr in SW_VIAS:
                _via(b, n, u + du, yr, sw, VIA_PWR, count)
        # the channel's return: bottom and In3, the FET band plus the leg
        # to the shunt
        leg = [(SRC_LEG[0], SRC_LEG[1]), (SRC_LEG[2], SRC_LEG[1]), (SRC_LEG[2], SRC_LEG[3])]
        _zone(b, n, m('SRC'), pcbnew.B_Cu, BOT_SRC, prio=3, name='return')
        _zone(b, n, m('SRC'), pcbnew.In3_Cu, BOT_SRC, prio=3, name='return')
        for g in GAPS:
            for du, yr in SRC_VIA:
                _via(b, n, g + du, yr, m('SRC'), VIA_PWR, count)
        for u, yr in SRC_LEG_VIAS:
            _via(b, n, u, yr, m('SRC'), VIA_PWR, count)
    return count


def shunt_vias(b, comps):
    """Ground vias in every shunt's ground pad, as many as fit round its
    Kelvin sense pad."""
    import fanout
    from shapely.geometry import Point
    layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    k = 0
    for n in CHANNELS:
        obs = fanout.Obstacles(b, layers)
        ref = roles(comps, n)['R_SH']
        fp = b.FindFootprintByReference(ref)
        pad = next(p for p in fp.Pads() if p.GetNumber() == '2')
        c = pad.GetPosition(); cx, cy = c.x / 1e6, c.y / 1e6
        for dx in (-0.4, 0.4):
            for dy in (-0.4, 0.4):
                vx, vy = cx + dx, cy + dy
                g = Point(vx, vy).buffer(VIA_PWR[0] / 2)
                if not (obs.clear(g, 'GND', layers, 0.2) and obs.hole_room(vx, vy, VIA_PWR[1] / 2, 0.45)):
                    continue
                v = pcb.via(b, vx - pcb.CX, vy - pcb.CY, 'GND', d=VIA_PWR[0], drill=VIA_PWR[1]); v.SetLocked(True)
                obs.add(g, 'GND', layers); obs.holes.append((vx, vy, VIA_PWR[1] / 2))
                k += 1
    return k


def gate_cells(b, comps):
    """Every FET's gate pin 4 reaches its gate resistor by a short fixed
    stub on the FET's own side; the resistor's driver end takes a via in
    its pad (filled, POFV), where the router starts.  Locked."""
    k = 0
    for n in CHANNELS:
        r = roles(comps, n)
        for ph in PH_U:
            for fet, res, layer in (('Q%sH' % ph, 'RGH_' + ph, pcbnew.F_Cu), ('Q%sL' % ph, 'RGL_' + ph, pcbnew.B_Cu)):
                gate = next(p for p in b.FindFootprintByReference(r[fet]).Pads() if p.GetNumber() == '4')
                rp = {p.GetNumber(): p for p in b.FindFootprintByReference(r[res]).Pads() if p.GetNumber()}
                if rp['2'].GetNetname() != gate.GetNetname():
                    raise SystemExit('%s pad 2 is not on %s' % (r[res], gate.GetNetname()))
                tr = pcbnew.PCB_TRACK(b)
                tr.SetStart(gate.GetPosition()); tr.SetEnd(rp['2'].GetPosition()); tr.SetWidth(MM(0.25))
                tr.SetLayer(layer); tr.SetNet(gate.GetNet()); tr.SetLocked(True)
                b.Add(tr)
                q = rp['1'].GetPosition()
                v = pcb.via(b, q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, rp['1'].GetNetname(),
                            d=VIA_ESCAPE[0], drill=VIA_ESCAPE[1])
                v.SetLocked(True)
                k += 1
    return k


def routing_keepouts(b):
    """Rule areas (no tracks, no vias) over the power copper, added only to
    the copy of the board handed to Freerouting, which treats pours as
    planes other nets may cross.  Plus a 0.3 mm strip along each edge
    (Freerouting keeps only its own clearance from the outline)."""
    k = 0
    for n in CHANNELS:
        areas = []
        for ph, u in PH_U.items():
            areas.append((pcbnew.F_Cu, TOP_SW(u)))
            areas.append((pcbnew.F_Cu, [(u - 1.6, 10.15), (u + 1.6, 10.15), (u + 1.6, 13.25), (u - 1.6, 13.25)]))
            areas.append((pcbnew.B_Cu, [(u - 1.6, 13.65), (u + 1.6, 13.65), (u + 1.6, 16.85), (u - 1.6, 16.85)]))
        areas.append((pcbnew.B_Cu, BOT_SRC))
        areas.append((pcbnew.In3_Cu, BOT_SRC))
        for layer, pts in areas:
            pcb.rule_area(b, [xf_point(n, u, yr) for u, yr in pts], [layer], tracks=True, vias=True,
                          pads=False, pours=False, name='pour keepout')
            k += 1
    # the back-EMF resistors' tabs into the switch-node pours too: a trace
    # of another net across one cuts the resistor off its phase
    for z in list(b.Zones()):
        if not z.GetIsRuleArea() and z.GetZoneName() == 'bemf tab':
            ol = z.Outline().Outline(0)
            pts = [(ol.CPoint(i).x / 1e6 - pcb.CX, ol.CPoint(i).y / 1e6 - pcb.CY) for i in range(ol.PointCount())]
            pcb.rule_area(b, pts, [pcbnew.B_Cu], tracks=True, vias=True, pads=False, pours=False,
                          name='pour keepout')
            k += 1
    h, w = pcb.HALF, 0.3
    cu = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)
          if b.IsLayerEnabled(l)]
    for x0, y0, x1, y1 in ((-h, -h, h, -h + w), (-h, h - w, h, h), (-h, -h, -h + w, h), (h - w, -h, h, h)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cu, tracks=True, vias=True, pads=False,
                      pours=False, name='edge keepout')
        k += 1
    # the mounting slots, widened by the same 0.3 mm (the holes themselves
    # sit inside the grommet keepouts)
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


# Six layers: F signals + power | In1 GND | In2 signals | In3 signals +
# channel returns | In4 VBAT | B signals + power.
LAYERS = 6
# 2 oz inner copper: In1 (ground) and In4 (battery) carry all four motors'
# current, and In3 the channel returns; twice the copper halves their loss
# and spreads the FETs' heat further.
INNER_OZ = 2.0
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
# the maze router's cell (mm): round the 0.5 mm-pitch escape vias its
# rounding margin (1.2 cells) closes gaps a 0.05 mm grid cannot see
FINISH_RES = 0.025


def net_groups(comps):
    nets = set(net for c in comps for net in c.pins.values() if net)
    gate = sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_GHA', '_GHB', '_GHC', '_GLA', '_GLB', '_GLC',
                                                                 '_GHA_D', '_GHB_D', '_GHC_D', '_GLA_D',
                                                                 '_GLB_D', '_GLC_D'))
    boot = sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_BSTA', '_BSTB', '_BSTC'))
    drv = sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_A', '_B', '_C'))
    return nets, gate, boot, drv


# Gate drive (driver to gate resistor to gate) and the driver's switch-node
# sense lines.  Every one of them crosses the FET row in the via corridors
# (SRC_VIA), where a 0.12 mm track leaves room for two a side of the
# corridor's via and a 0.2 mm one for one.  The DRV8300 drives 0.75 A /
# 1.5 A peaks through its 10 ohm gate resistors: 10 mm of 0.12 mm track adds
# ~0.04 ohm (outer layer; half that on 2 oz In2), under 0.5 % of the gate
# loop.  The bootstrap lines keep 0.2 mm: they are short stubs, and they
# carry the capacitor's recharge.
GATE_W = 0.12
SENSE_W = 0.15
BOOT_W = 0.2


# Routed supplies (width, clearance): the battery's current runs in the
# planes and pours, so what is left on tracks is small.  Gate-drive
# supply 0.2 mm (the four drivers average ~25 mA, their bootstrap pulses
# come from the capacitors beside them); 3.3 V 0.15 mm (four MCUs and
# four amplifiers, ~60 mA); the battery's taps 0.2 mm (the buck's ~10 mA
# input, the LDO's 25 mA, the voltage divider); the buck's switch node
# 0.4 mm.
SUPPLY_RULES = {
    'GVDD': (0.2, 0.1), 'GVDD_IN': (0.2, 0.1),
    '+3V3': (0.15, 0.1), 'BUCK_VCC': (0.15, 0.1),
    'VBAT': (0.2, 0.13), 'BUCK_LX': (0.4, 0.15),
}


def widths(comps):
    """Router widths: gate drive GATE_W, bootstrap BOOT_W, the driver's
    switch-node sense SENSE_W, the supplies per SUPPLY_RULES, everything
    else the 0.1 mm default."""
    nets, gate, boot, drv = net_groups(comps)
    w = {x: GATE_W for x in gate}
    w.update({x: BOOT_W for x in boot})
    w.update({x: SENSE_W for x in drv})
    w.update({n: r[0] for n, r in SUPPLY_RULES.items()})
    return w


def clearances(comps):
    """The switch nodes and the battery reach 25.2 V plus switching
    overshoot, so 31-50 V: IPC-2221B asks 0.13 mm on outer layers under
    solder mask (B4) and 0.1 mm on inner layers (B1).  0.13 mm round those
    nets everywhere; everything else is 3.3 V or 11.4 V logic and gate
    drive, 0.1 mm (B4 and B1 both allow it below 30 V)."""
    nets, gate, boot, drv = net_groups(comps)
    cl = {x: 0.1 for x in widths(comps)}
    for x in drv:
        cl[x] = 0.13
    cl.update({n: r[1] for n, r in SUPPLY_RULES.items()})
    return cl


def via_rules(b):
    ds = b.GetDesignSettings()
    # the smallest via on the board is the QFN in-pad escape
    ds.m_ViasMinSize = MM(VIA_ESCAPE[0])
    ds.m_MinThroughDrill = MM(VIA_ESCAPE[1])
    ds.m_ViasMinAnnularWidth = MM((VIA_ESCAPE[0] - VIA_ESCAPE[1]) / 2)
    ds.m_HoleClearance = MM(HOLE_CL)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetViaDiameter(MM(VIA_SIG[0])); nc.SetViaDrill(MM(VIA_SIG[1]))


DRU_EXTRA = pcb.POFV_RULES

FANOUT = dict(ep_pitch=1.5, share=0.9, ep_join=0.2, via_d=VIA_INPAD[0], via_drill=VIA_INPAD[1],
              off_drill=0.25, clearance=0.1, steps=(0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3, 1.7, 2.1, 2.5),
              far_share=3.0,
              inpad=dict(d=VIA_INPAD[0], drill=VIA_INPAD[1], cl=0.1, hole_cl=HOLE_CL, hole_gap=0.45, min_pad=0.34))


def power_refs(comps):
    """Parts whose plane connections the power copper already makes."""
    out = {'P_BAT+', 'P_BAT-'}
    for n in CHANNELS:
        r = roles(comps, n)
        out |= {r[k] for k in ('QAH', 'QBH', 'QCH', 'QAL', 'QBL', 'QCL', 'CBR_A', 'CBR_B', 'CBR_C', 'R_SH',
                               'PA', 'PB', 'PC')}
    return out


def build(out_path):
    b, comps, fps = build_placed(out_path)
    cu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    pcb.hole_keepouts(b, cu)
    pcb.tab_keepouts(b, cu)
    via_rules(b)
    e = H - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    pcb.zone(b, 'GND', pcbnew.In1_Cu, full, name='GND plane', thermal=False)
    pcb.zone(b, 'VBAT', pcbnew.In4_Cu, full, name='VBAT plane', thermal=False)
    for l, t in ((pcbnew.In1_Cu, pcbnew.LT_POWER), (pcbnew.In2_Cu, pcbnew.LT_SIGNAL),
                 (pcbnew.In3_Cu, pcbnew.LT_SIGNAL), (pcbnew.In4_Cu, pcbnew.LT_POWER)):
        b.SetLayerType(l, t)
    print('power vias:', power_copper(b, comps))
    print('shunt ground vias:', shunt_vias(b, comps))
    print('gate cells:', gate_cells(b, comps))
    nets, gate, boot, drv = net_groups(comps)
    cl = clearances(comps)
    pcb.netclass(b, 'GATE', gate, width=GATE_W, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'BOOT', boot, width=BOOT_W, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'SWITCH', drv, width=SENSE_W, clearance=0.13, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    groups = {}
    for n, rule in SUPPLY_RULES.items():
        groups.setdefault(rule, []).append(n)
    for (w, c), members in sorted(groups.items(), reverse=True):
        pcb.netclass(b, 'PWR_%03d_%03d' % (round(w * 100), round(c * 100)), members, width=w, clearance=c,
                     via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    import fanout
    fanout.Obstacles.NET_CL = {x: c for x, c in cl.items() if c > 0.1}
    fanout.Obstacles.MARGIN = 0.01
    e2 = H - 0.4
    pins = escape_pins(b, comps) + kelvin_pins(comps)
    k, bad = fanout.dogbones(b, pins, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL)
    print('escape vias (QFN pins, Kelvin sense): %d of %d, none for %s' % (k, len(pins), bad))
    print('bootstrap stubs:', bootstrap_stubs(b, comps))
    k, failed = fanout.fanout(b, {'GND', 'VBAT'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2),
                              skip=power_refs(comps), **{x: y for x, y in FANOUT.items() if x != 'inpad'},
                              inpad=FANOUT['inpad'])
    print('fanout: %d plane vias, %d pads without one: %s' % (k, len(failed), failed))
    local, left = route_local(b, comps)
    print('shared parts\' own nets, routed first: %s, %d open %s' % (', '.join(local), len(left), left))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


def route_local(b, comps):
    """The nets whose every pad is on a shared part (the buck's switch node
    and supply pin, the gate-drive LDO's input and feedback, the power LED):
    short loops in the crowded middle, joined by the maze router before
    anything else is routed there, and fixed.  Routed with the rest, they
    found the middle taken.  Returns (the nets, those left open)."""
    import finish
    chan = set(r for n in CHANNELS for r in roles(comps, n).values())
    refs = {}
    for c in comps:
        for n in c.pins.values():
            if n:
                refs.setdefault(n, set()).add(c.ref)
    local = sorted((n for n, r in refs.items() if n not in ('GND', 'VBAT') and not r & chan),
                   key=lambda n: (finish.mst_length(b, n), n))
    finish.ROUTE_LAYERS, finish.RES = ROUTE_LAYERS, FINISH_RES
    finish.VIA_D, finish.VIA_DRILL = VIA_SIG
    finish.VIA_RING, finish.POFV_GAP = VIA_RING, None
    w, cl = widths(comps), clearances(comps)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    left = [n for n in local if finish.route_net(b, n, track_w=w.get(n, 0.1), clmap=cl, lock=True)]
    return local, left


ESCAPE_ROOM = 0.6     # clear run beyond a QFN pin's pad that lets it escape on its own layer


def outward_room(b, fp, pad, reach=1.5):
    """How far (mm) a track can run straight out from `pad`, away from its
    chip, on the chip's own layer before it meets another part's courtyard
    or other copper (0.1 mm of clearance each side)."""
    from shapely.geometry import box, LineString, Point, Polygon
    from shapely.ops import unary_union
    mm = lambda v: v / 1e6
    side = fp.IsFlipped()
    layer = pcbnew.B_Cu if side else pcbnew.F_Cu
    crt = pcbnew.B_CrtYd if side else pcbnew.F_CrtYd
    obst = []
    for o in b.GetFootprints():
        if o.GetReference() == fp.GetReference():
            continue
        if o.IsFlipped() == side:
            cy = o.GetCourtyard(crt)
            if cy.OutlineCount():
                bb = cy.BBox()
                obst.append(box(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
        for q in o.Pads():
            if q.IsOnLayer(layer):
                bb = q.GetBoundingBox()
                obst.append(box(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() == layer:
            q = t.GetPosition()
            w = t.GetWidth(layer) if isinstance(t, pcbnew.PCB_VIA) else t.GetWidth()
            if isinstance(t, pcbnew.PCB_VIA):
                obst.append(Point(mm(q.x), mm(q.y)).buffer(mm(w) / 2))
            else:
                a, c = t.GetStart(), t.GetEnd()
                obst.append(LineString([(mm(a.x), mm(a.y)), (mm(c.x), mm(c.y))]).buffer(mm(w) / 2))
    for z in b.Zones():
        if z.IsOnLayer(layer) and not z.GetIsRuleArea() and z.GetNetname() != pad.GetNetname():
            ol = z.Outline().Outline(0)
            obst.append(Polygon([(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]))
    o = unary_union(obst)
    cx, cy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
    px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
    dx, dy = px - cx, py - cy
    ux, uy = (math.copysign(1, dx), 0.0) if abs(dx) > abs(dy) else (0.0, math.copysign(1, dy))
    half = max(mm(pad.GetSize().x), mm(pad.GetSize().y)) / 2
    x0, y0 = px + ux * half, py + uy * half
    free = 0.0
    for k in range(1, int(reach / 0.05) + 1):
        d = 0.05 * k
        if LineString([(x0, y0), (x0 + ux * d, y0 + uy * d)]).buffer(0.15).intersects(o):
            break
        free = d
    return free


def bootstrap_stubs(b, comps):
    """Each bootstrap capacitor's pads to its driver pins' escape vias (the
    nearest via of the pad's net), by short fixed tracks on top."""
    k = 0
    vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
    for n in CHANNELS:
        r = roles(comps, n)
        for ph in 'ABC':
            for p in b.FindFootprintByReference(r['CBS_' + ph]).Pads():
                if not p.GetNumber():
                    continue
                q = p.GetPosition()
                own = [v for v in vias if v.GetNetname() == p.GetNetname()]
                if not own:
                    raise SystemExit('%s pad %s: no via of %s' % (r['CBS_' + ph], p.GetNumber(), p.GetNetname()))
                v = min(own, key=lambda v: (v.GetPosition() - q).EuclideanNorm())
                if (v.GetPosition() - q).EuclideanNorm() > MM(1.2):
                    raise SystemExit('%s pad %s: its via is %.2f mm away' % (r['CBS_' + ph], p.GetNumber(),
                                     (v.GetPosition() - q).EuclideanNorm() / 1e6))
                tr = pcbnew.PCB_TRACK(b)
                tr.SetStart(q); tr.SetEnd(v.GetPosition()); tr.SetWidth(MM(0.2))
                tr.SetLayer(pcbnew.F_Cu); tr.SetNet(p.GetNet()); tr.SetLocked(True)
                b.Add(tr)
                k += 1
    return k


def kelvin_pins(comps):
    """The current sense's Kelvin pads: the shunt's sense pads (bottom)
    and the amplifier's inputs (top), a via each in or beside the pad.  The
    shunt's sense pads sit inside the channel's return pour, where no
    router could find a spot for a via of its own.  Also the amplifier's
    output: its via lands on the filter resistor's pad below.  And the
    back-EMF and neutral resistors' MCU ends (pin 2): they stand on the
    bottom among the FETs' pads, where no router finds a spot for a via of
    its own, and their nets come in on the inner layers.  Likewise the
    signal ends of the row of dividers' low legs by the MCU (back-EMF,
    neutral, current filter output): five 0201s side by side at 0.9 mm,
    walled in by the MCU, the next channel's driver and the shunt."""
    out = []
    for n in CHANNELS:
        r = roles(comps, n)
        out += [(r['R_SH'], '3'), (r['R_SH'], '4'), (r['U_CS'], '4'), (r['U_CS'], '5'), (r['U_CS'], '6')]
        out += [(r[k + ph], '2') for k in ('RBH_', 'RN_') for ph in 'ABC']
        out += [(r['RBL_' + ph], '1') for ph in 'ABC'] + [(r['RNG'], '1'), (r['R_IF'], '2')]
    return out


def escape_pins(b, comps):
    """QFN pins (MCUs and drivers) that get an escape via in their pad:
    every signal pin that has no room beyond its pad on the chip's own
    layer.  Both sides are packed round the chips, so for those a pin's own
    pad is the one sure spot for its via; unused ones are removed after
    routing (cleanup.py).  A pin with ESCAPE_ROOM clear beyond its pad
    escapes outwards on its own layer instead: a row of in-pad vias walls
    the chip in on every layer (0.5 mm apart, no track passes between),
    and a pin that can do without one leaves a gap in the wall.  Unless its
    net has a pad over the chip on the other side (a bootstrap capacitor):
    that pad is reached through the pin's own via.  A pin that needs one in
    any channel gets one in every channel: the channels are routed as one
    (stamp.py), and the copies must find the same vias."""
    qfn = {}
    for n in CHANNELS:
        r = roles(comps, n)
        qfn[r['MCU']] = 'MCU'
        qfn[r['GD']] = 'GD'
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                q = p.GetPosition()
                pads.setdefault(p.GetNetname(), []).append((fp.GetReference(), fp.IsFlipped(), q.x / 1e6, q.y / 1e6))
    need = set()
    for ref in sorted(qfn):
        fp = b.FindFootprintByReference(ref)
        bb = fp.GetBoundingBox(False)
        x0, y0, x1, y1 = bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6
        for p in fp.Pads():
            net = p.GetNetname()
            if not net or net in ('GND', 'VBAT') or p.GetNumber() == '25':
                continue
            if not any(r_ != ref for r_, fl, ox, oy in pads[net]):
                continue
            over = any(fl != fp.IsFlipped() and x0 <= ox <= x1 and y0 <= oy <= y1
                       for r_, fl, ox, oy in pads[net])
            if over or outward_room(b, fp, p) < ESCAPE_ROOM:
                need.add((qfn[ref], p.GetNumber()))
    return sorted((ref, num) for ref, role in qfn.items() for r_, num in need if r_ == role)


# ============================================================ artwork
PRODUCT = 'Ridge 3'               # the lineup: Ridge 3 / 7 / 12, by prop size
FIRMWARE = 'RIDGE3_G071'          # the AM32 build to flash (firmware/am32)


def artwork(b, comps):
    """OffGrid silkscreen.  Top (it faces the flight controller): the
    OffGrid mark, the motor number by every motor's pads, battery polarity,
    the pack range, pin 1 of the stack connector, the SWD pad names, the
    board's name and firmware, the front arrow.  Bottom: battery polarity
    and the front arrow.  Codes in JetBrains Mono, words in Instrument
    Sans.  Nothing lands on a pad, a hole, a part body or under a grommet.

    Both sides are full of parts; the mark takes the roomiest free spot of
    the top (the brand's minimum is 16 px, 2.92 mm of ink), and the top's
    front arrow the mirror spot across the centre line, so the two frame
    the front edge."""
    import artwork as A, brand
    from shapely.geometry import box
    from shapely.ops import unary_union
    A.hide_fields(b)
    A.strip(b)
    top = A.SilkPlacer(b, 'T', bodies=True, brand=True, via_clear=0.1)
    bot = A.SilkPlacer(b, 'B', bodies=True, brand=True, via_clear=0.1)
    side = {fp.GetReference(): ('B' if fp.IsFlipped() else 'T') for fp in b.GetFootprints()}

    def sign(plus, s=0.45, w=0.3):
        g = box(-s, -w / 2, s, w / 2)
        return unary_union([g, box(-w / 2, -s, w / 2, s)]) if plus else g
    # battery polarity on both sides (the leads go through), outboard of
    # each pad towards its corner
    for pl in (top, bot):
        for plus, ref in ((True, 'P_BAT+'), (False, 'P_BAT-')):
            x0, y0 = GLOBAL[ref][:2]
            out = -1 if x0 < 0 else 1
            beside = [(x0 + out * (1.5 + d), y0 + dy) for d in (0.6, 0.75, 0.9, 1.1) for dy in (0.0, -0.5, 0.5, -1.0)]
            beside += [(x0 + dx, y0 - (1.5 + d)) for d in (0.6, 0.8, 1.0) for dx in (0.0, out * 0.5, -out * 0.5)]
            pl.geom(sign(plus), beside, vias=False, margin=0.12)
    # the OffGrid mark, as large as the roomiest spot takes, with its clear
    # space (1 x node radius) kept from everything; then the front arrow
    mark_at = None
    for width in (4.0, 3.5, 3.0):
        g, clear = brand.mark_mm(width)
        reach = max(math.hypot(x, y) for x, y in g.convex_hull.exterior.coords)
        mark_at = top.geom(g, top.roomiest(reach + clear), clear=clear, vias='fewest', margin=clear, quiet=True,
                           hull=True)
        if mark_at:
            break
    else:
        raise SystemExit('esc: no room on the top for the OffGrid mark')
    mirror = [(x, y) for x, y in top.grid_spots((-mark_at[0], mark_at[1]), radius=11.0, step=0.1)]
    if not any(top.geom(brand.arrow_mm(2.6, 'Front', cap=1.2), mirror, vias='fewest', margin=m, quiet=True)
               for m in (0.35, 0.2)):
        top.geom(brand.arrow_mm(2.6), mirror, vias='fewest', margin=0.2)
    # SWD and supply test points, on whichever side they are, before the
    # motor numbers: each has one pad to sit by
    for n in CHANNELS:
        r = roles(comps, n)
        for role, s_ in (('TP_DIO', 'D%d'), ('TP_CLK', 'C%d')):
            pl = top if side[r[role]] == 'T' else bot
            pl.label(r[role], s_ % n, size=1.2, dist=0.7, smallest=1.0, face='mono')
    # (ground is 'G', as on the flight controller's pads)
    for ref, s_ in (('TP_3V3', '3V3'), ('TP_GND', 'G')):
        (top if side[ref] == 'T' else bot).label(ref, s_, size=1.2, smallest=1.0, face='mono')
    # one number per motor on top, as large as fits, in the nearest free
    # spot that is clearly this motor's: at least 2 mm nearer its own three
    # pads than any other motor's pads or the battery pads
    mpads = {n: [A.pad_xy(b, roles(comps, n)['P' + ph], '1') for ph in 'ABC'] for n in CHANNELS}
    batt = [A.pad_xy(b, 'P_BAT+', '1'), A.pad_xy(b, 'P_BAT-', '1')]
    for n in CHANNELS:
        own = mpads[n]
        others = [q for m in CHANNELS if m != n for q in mpads[m]] + batt
        near = lambda x, y, pts: min(math.hypot(x - px, y - py) for px, py in pts)
        spots = [(x, y, 0, None) for x, y in top.grid_spots(own[1], radius=8.0, step=0.2)
                 if near(x, y, others) >= near(x, y, own) + 2.0]
        for size in (1.5, 1.3, 1.2):
            if top.text([('mono', str(n))], spots, size=size):
                break
        else:
            for ph in 'ABC':
                top.label_along(roles(comps, n)['P' + ph], str(n), sizes=(1.5, 1.3, 1.2), face='mono')
    # the pack range, between the battery pads
    xb = (GLOBAL['P_BAT+'][0] + GLOBAL['P_BAT-'][0]) / 2
    top.text([('mono', '2-6S')], [(x, y, 0, None) for x, y in top.grid_spots((xb, 14.0), radius=12.0, step=0.2)],
             size=1.2)
    # the name and the firmware to flash, on top, before the small labels
    # take the room: on the centre line if anywhere there is room, else as
    # near it as fits, else turned to read along a free strip
    at = None
    # (sizes down to the floors: 1.1 mm capitals in Instrument Sans, 1.0 in
    # JetBrains Mono, whose strokes stay over the fabs' 0.15 mm there)
    for runs, caps in (([('sans', PRODUCT + ' ESC')], (1.4, 1.3, 1.2, 1.1)), ([('mono', FIRMWARE)], (1.1, 1.0))):
        near = (0.0, at + 1.9) if at is not None else (0.0, 0.0)
        pts = top.grid_spots(near, radius=16.0, step=0.25)
        tries = []
        for c in caps:
            g0 = brand.line(runs, c)[0].bounds
            mid = (g0[1] + g0[3]) / 2
            tries.append((c, [(0.0, near[1] + dy - mid, 0, None) for dy in sorted((0.1 * k for k in range(-340, 341)),
                                                                                  key=abs) if abs(near[1] + dy) < pcb.HALF]))
        for c in caps:
            g0 = brand.line(runs, c)[0].bounds
            mid = (g0[1] + g0[3]) / 2
            tries.append((c, [(x, y - mid, 0, None) for x, y in pts]))
            tries.append((c, [(x - mid, y, 90, None) for x, y in pts]))
        for c, sp in tries:
            if top.text(runs, sp, size=c, vias='fewest'):
                at = top.placed[-1].centroid.y - pcb.CY
                break
    top.label('J_FC', '1', pad='1', dist=0.8, size=1.2, smallest=0.9, face='mono')
    # which way is forward on the bottom too: the ESC must sit in the stack
    # the same way round as the FC, or every motor number is wrong
    spots = bot.grid_spots((0.0, -6.0), radius=11.0, step=0.25)
    if not any(bot.geom(brand.arrow_mm(2.6, 'Front', cap=1.2, mirror=True), spots, vias='fewest',
                        margin=m, quiet=True) for m in (0.6, 0.35)):
        bot.geom(brand.arrow_mm(2.6, mirror=True), spots, vias='fewest', margin=0.4)


if __name__ == '__main__':
    import sys
    build_placed(sys.argv[1] if len(sys.argv) > 1 else '/tmp/esc3.kicad_pcb', legal='--nolegal' not in sys.argv)
