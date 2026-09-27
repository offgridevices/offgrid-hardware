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
    # a row of capacitors inside the chips, on the bottom: the driver's
    # bootstrap and gate-drive supply capacitors (its supply pin faces the
    # centre), then the MCU's 100 nF (its supply pins face the centre too).
    # Six fit between the neighbouring channel's MCU and the next row,
    # turned 90 degrees.  The MCU's bulk and reset capacitors go on top,
    # over its supply and reset pins.
    for i, role in enumerate(('CBS_A', 'CBS_B', 'CBS_C', 'C_GV', 'C_GVHF', 'C_VDD')):
        t[role] = (-4.15 + 1.2 * i, 3.7, 90, 'B')
    t['C_VDDB'] = (1.9, 5.5, 0, 'T')
    t['C_RST'] = (3.9, 5.5, 0, 'T')
    # shunt along the row in the diagonal zone at the channel's +u end:
    # its sense-node pad (1) at +u, where the channel's return copper comes
    # in from the FET band, its ground pad inwards
    t['R_SH'] = (8.0, 8.0, 180, 'B')
    # On top, over the driver: the gate resistors and the SWD test points.
    # Over the MCU: the back-EMF dividers' low legs, the neutral's leg to
    # ground, the current filter and the CUR-average resistor.  In the
    # diagonal zone at the +u end, over the shunt: the current amplifier
    # and its supply capacitor.
    for i, ph in enumerate('ABC'):
        t['RGH_' + ph] = (-4.4 + 2.0 * i, 9.65, 0, 'T')
        t['RGL_' + ph] = (-4.4 + 2.0 * i, 8.65, 0, 'T')
    # SWD test points on top, the side that faces the flight controller:
    # the bootloader is flashed once, before the stack goes together, and
    # the bottom has no room left for seven pads
    t['TP_DIO'] = (7.0, 6.0, 0, 'T')
    t['R_CUR'] = (1.6, 7.65, 0, 'T')
    # the back-EMF dividers' low legs, the neutral's leg to ground and the
    # current filter all end on MCU pins: on the bottom, packed round the
    # MCU and into the diagonal zone beside it
    for role, pos in (('RBL_A', (5.3, 4.6)), ('RBL_B', (6.5, 4.6)), ('RBL_C', (7.7, 4.6)),
                      ('RNG', (5.3, 5.6)), ('R_IF', (6.5, 5.6)), ('C_IF', (7.7, 5.6))):
        t[role] = pos + (0, 'B')
    t['U_CS'] = (7.4, 7.6, 0, 'T')
    t['C_CS'] = (5.6, 6.0, 90, 'T')
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
        elif note == 'U_ESC%d VDD' % n: out['C_VDD'] = ref
        elif note == 'U_ESC%d VDD bulk' % n: out['C_VDDB'] = ref
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


# ---------------------------------------------------------------- global parts
# By note (first match, in circuit order).  Battery pads: plated through
# holes in the rear edge's two corner slots, outside motor 1's pads and
# FETs (+ left, - right).
BAT_U, BAT_YR = 9.5, 16.1
GLOBAL = {
    'P_BAT+': (-BAT_U, BAT_YR, 0, 'T'),
    'P_BAT-': (BAT_U, BAT_YR, 0, 'T'),
    'J_FC': (0.0, 1.75, 0, 'T'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
    # TVS in the rear-left corner slot beside the battery pads; the 3.3 V
    # buck and the gate-drive LDO in front of the stack connector
    'D_TVS': (-8.4, 11.6, 90, 'T'),
    # the inductor exactly fills the strip between the stack connector and
    # the front channel's parts, so it is fixed there
    'L1': (1.0, -2.75, 0, 'T'),
    'U_BUCK': (-2.9, -2.8, 0, 'T'),
    # the gate-drive LDO at the rear left, next to the battery pads it
    # feeds from, between channel 1's and channel 3's chips
    'U_GVDD': (-7.4, 7.3, 90, 'T'),
    'LED_PWR': (16.8, 13.2, 90, 'T'),
    # the SWD lead's supply and clock pads, on top with the SWD pads
    'TP_3V3': (-3.4, 3.4, 0, 'T'),
    'TP_GND': (3.4, -3.4, 0, 'T'),
    'TP_SWCLK': (-3.4, -3.4, 0, 'T'),
}
GLOBAL_BY_NOTE = {
    'CUR filter': (-5.0, 0.5, 90, 'T'),
    'buck input': (-2.9, -4.6, 0, 'T'),
    'buck VCC': (-4.5, -2.8, 90, 'T'),
    'buck output': (4.3, -2.6, 90, 'T'),
    'power LED': (16.8, 15.4, 90, 'T'),
    'gate-drive LDO input filter': (-7.4, 9.9, 0, 'T'),
    'gate-drive LDO input': (-9.3, 7.3, 90, 'T'),
    'gate-drive LDO feedback top': (-5.6, 6.0, 90, 'T'),
    'gate-drive LDO feedback bottom': (-5.6, 7.1, 90, 'T'),
    'gate-drive LDO output': (-5.6, 8.6, 90, 'T'),
    'ESC vsense top': (5.0, 0.5, 90, 'T'),
    'ESC vsense bottom': (6.0, 0.5, 90, 'T'),
    'ESC vsense filter': (7.0, 0.5, 90, 'T'),
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
               'GD', 'MCU', 'R_SH', 'RBH_A', 'RBH_B', 'RBH_C', 'RN_A', 'RN_B', 'RN_C')


# global parts that stay exactly where the table puts them; the others
# are only hints for the packer
GLOBAL_FIXED = ('P_BAT+', 'P_BAT-', 'J_FC', 'L1', 'H1', 'H2', 'H3', 'H4')


# Packing order: the parts that must sit at a channel chip's pins first,
# then the supplies' chips and inductor, then their other parts, then the
# rest (filters, dividers, test points).  A supply's parts move with their
# chip (pack_anchor).
def pack_priority(c):
    # the supplies first, while there is room for them: the 3.3 V buck
    # beside its (fixed) inductor, then the gate-drive LDO, each chip
    # before (it is larger) the parts that belong at its pins, which follow
    # it (pack_anchor); then the battery TVS
    if c.ref == 'U_BUCK' or (c.block == 'power' and 'buck' in c.note):
        return -3
    if c.ref == 'U_GVDD' or (c.block == 'power' and 'gate-drive LDO' in c.note):
        return -2
    if c.ref == 'D_TVS':
        return -1
    if c.note.startswith(('bootstrap ', 'driver GVDD')) or c.note.endswith((' VDD', ' VDD bulk', ' supply')) \
            or 'current amplifier' in c.note:
        return 0
    if c.ref in ('U_BUCK', 'U_GVDD'):
        return 1
    if c.block == 'power' and ('buck' in c.note or 'gate-drive LDO' in c.note):
        return 2
    return 3


def pack_anchor(c):
    if c.block == 'power' and c.ref != 'U_BUCK' and 'buck' in c.note:
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
    # the gate-drive LDO and its parts, and the battery TVS, go wherever
    # there is room: the LDO feeds all four drivers and the TVS only needs
    # the battery pads' copper, which is on both sides
    return c.note in EITHER_SIDE or c.ref in ('U_GVDD', 'D_TVS') or \
        (c.block == 'power' and 'gate-drive LDO' in c.note)


def escape_keep(comps, place):
    """Where the MCUs' and drivers' vias come through to the far side, so no
    other part puts a pad there: each signal pin that leaves its side of the
    board has its via inside the pad at the pad's outer end (VIA_MICRO,
    fanout.dogbones), and each driver's ground pad has the plane fan-out's
    2 x 2 grid (FANOUT ep_pitch, VIA_INPAD).  Each spot is the via plus
    0.1 mm."""
    import legalize
    allp = {**parts.PARTS, **parts.PADS}
    out = []

    def spot(far, x, y, d):
        r = d / 2 + 0.1
        out.append((far, (x - r, y - r, x + r, y + r)))
    for n in CHANNELS:
        r = roles(comps, n)
        # the six PWM lines join the two chips on their own side
        same = {'M%d_%s' % (n, k) for k in ('HA', 'HB', 'HC', 'LA', 'LB', 'LC')}
        for role in ('MCU', 'GD'):
            c = next(c for c in comps if c.ref == r[role])
            x, y, rot, side = place[c.ref][:4]
            far = 'B' if side == 'T' else 'T'
            for num, bb, th in legalize.pad_boxes(allp[c.part]['fp'], rot, side):
                net = c.pins.get(num)
                px, py = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                w, h = bb[2] - bb[0], bb[3] - bb[1]
                if net == 'GND' and w * h > 2.0:
                    # exposed pad: the fan-out's via grid
                    k = FANOUT['ep_pitch'] / 2
                    for dx in (-k, k):
                        for dy in (-k, k):
                            spot(far, x + px + dx, y + py + dy, FANOUT['via_d'])
                elif net not in (None, 'GND', 'VBAT') and net not in same:
                    # outward along the pad's long axis, as fanout.dogbones puts it
                    if abs(px) >= abs(py):
                        s_ = max(0.0, w / 2 - VIA_MICRO[0] / 2 - 0.08)
                        vx, vy = px + (s_ if px > 0 else -s_), py
                    else:
                        s_ = max(0.0, h / 2 - VIA_MICRO[0] / 2 - 0.08)
                        vx, vy = px, py + (s_ if py > 0 else -s_)
                    spot(far, x + vx, y + vy, VIA_MICRO[0])
    return out


def fixed(comps):
    f = set(GLOBAL_FIXED)
    for n in CHANNELS:
        r = roles(comps, n)
        f |= {r[k] for k in FIXED_ROLES}
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
VIA_SIG = (0.35, 0.2)          # signal vias (routers, escapes)
VIA_INPAD = (0.45, 0.3)        # plane vias in pads (POFV, filled and capped)
VIA_PWR = (0.5, 0.3)           # power vias: FET tabs, motor pads, returns
# QFN escapes: a via inside the pin's own pad, at its outer end, filled and
# capped with the rest (JLCPCB multilayer minimum 0.15 mm hole / 0.25 mm
# via; POFV takes 0.15-0.55 mm).  The chips sit too close to their
# neighbours for a ring of dog-bone vias beside the pins.
VIA_MICRO = (0.25, 0.15)
HOLE_CL = 0.15

GAPS = (-7.5, -2.5, 2.5, 7.5)  # via corridors: the gaps between phases and both ends
MARK_R = 2.6                   # half-size of the bottom-centre square kept for the mark
SRC_VIA = ((-0.4, 11.85), (0.4, 11.85))          # per corridor, from its centre
LS_GATE_VIA = (2.0, 13.15)     # from the phase centre (low-side gate, bottom pin 4 at +0.97)
HS_GATE_VIA = (2.5, 14.05)     # from the phase centre (high-side gate, top pin 4 at +0.97)
VBAT_VIAS = ((0.95, 10.3), (0.95, 11.1), (0.95, 12.0), (0.1, 12.0))    # from the phase centre
SW_VIAS = [(du, yr) for yr in (14.3, 15.1, 15.9) for du in (-0.8, 0.0, 0.8) if (du, yr) != (0.8, 14.3)]
# the return copper's leg from the FET band to the shunt, through the
# channel's +u corner, and a grid of vias in it
SRC_LEG = (6.6, 6.8, 10.6, 13.45)
SRC_LEG_VIAS = [(u, yr) for u in (8.3, 9.1, 9.9) for yr in (9.9, 10.7)]
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
        rects += [('TB', (7.9, 9.4, 10.3, 11.2)), ('T', (5.5, 7.1, 7.3, 8.9))]
        for sd, (u0, y0, u1, y1) in rects:
            pts = [xf_point(n, u, yr) for u, yr in ((u0, y0), (u1, y1))]
            bb = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
            for side in ('T', 'B') if sd == 'TB' else (sd,):
                out.append((side, bb))
    # the bottom's centre, inside the four channels' capacitor rows, is kept
    # for the OffGrid mark (artwork): no parts there, only vias and traces
    out.append(('B', (-MARK_R, -MARK_R, MARK_R, MARK_R)))
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
                # a strip from the pad to the nearest point well inside
                # the pour (0.25 mm in from its edge)
                cu_ = min(max((pu0 + pu1) / 2, u - 1.35), u + 1.35)
                cy_ = min(max((py0 + py1) / 2, 13.9), 16.6)
                if u - 1.6 <= (pu0 + pu1) / 2 <= u + 1.6 and 13.65 <= (py0 + py1) / 2 <= 16.85:
                    continue
                w2 = 0.25
                if abs(cu_ - (pu0 + pu1) / 2) >= abs(cy_ - (py0 + py1) / 2):
                    ya, yb = max(py0, cy_ - w2), min(py1, cy_ + w2)
                    if ya > yb - 0.3:
                        ya, yb = (py0 + py1) / 2 - w2, (py0 + py1) / 2 + w2
                    tab = [(min(pu0, cu_), ya), (max(pu1, cu_), ya), (max(pu1, cu_), yb), (min(pu0, cu_), yb)]
                else:
                    ua, ub = max(pu0, cu_ - w2), min(pu1, cu_ + w2)
                    if ua > ub - 0.3:
                        ua, ub = (pu0 + pu1) / 2 - w2, (pu0 + pu1) / 2 + w2
                    tab = [(ua, min(py0, cy_)), (ub, min(py0, cy_)), (ub, max(py1, cy_)), (ua, max(py1, cy_))]
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


def gate_vias(b, comps):
    """Every FET gate leaves its pin 4 by a short fixed stub, sideways into
    the corridor beside the phase, to a via: the gate trace changes layer
    there and the router starts from the via.  Locked."""
    k = 0
    for n in CHANNELS:
        r = roles(comps, n)
        for ph, u in PH_U.items():
            for role, (du, yr), layer in (('Q%sL' % ph, LS_GATE_VIA, pcbnew.B_Cu),
                                          ('Q%sH' % ph, HS_GATE_VIA, pcbnew.F_Cu)):
                fp = b.FindFootprintByReference(r[role])
                pad = next(p for p in fp.Pads() if p.GetNumber() == '4')
                x, y = xf_point(n, u + du, yr)
                v = pcb.via(b, x, y, pad.GetNetname(), d=VIA_SIG[0], drill=VIA_SIG[1]); v.SetLocked(True)
                tr = pcbnew.PCB_TRACK(b)
                tr.SetStart(pad.GetPosition()); tr.SetEnd(v.GetPosition()); tr.SetWidth(MM(0.25))
                tr.SetLayer(layer); tr.SetNet(pad.GetNet()); tr.SetLocked(True)
                b.Add(tr)
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


def net_groups(comps):
    nets = set(net for c in comps for net in c.pins.values() if net)
    gate = sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_GHA', '_GHB', '_GHC', '_GLA', '_GLB', '_GLC',
                                                                 '_GHA_D', '_GHB_D', '_GHC_D', '_GLA_D',
                                                                 '_GLB_D', '_GLC_D', '_BSTA', '_BSTB', '_BSTC'))
    drv = sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_A', '_B', '_C'))
    return nets, gate, drv


def widths(comps):
    """Router widths: gate drive and bootstrap 0.2 mm, the driver's
    switch-node sense 0.2 mm, supplies 0.25 mm, the buck's switch node
    0.4 mm, everything else the 0.1 mm default."""
    nets, gate, drv = net_groups(comps)
    w = {x: 0.2 for x in gate}
    w.update({x: 0.2 for x in drv})
    w.update({'+3V3': 0.25, 'GVDD': 0.25, 'GVDD_IN': 0.25, 'BUCK_LX': 0.4, 'BUCK_VCC': 0.2, 'VBAT': 0.3})
    return w


def clearances(comps):
    """The switch nodes and the battery reach 25.2 V plus switching
    overshoot, so 31-50 V: IPC-2221B asks 0.13 mm on outer layers under
    solder mask (B4) and 0.1 mm on inner layers (B1).  0.13 mm round those
    nets everywhere; everything else is 3.3 V or 11.4 V logic and gate
    drive, 0.1 mm (B4 and B1 both allow it below 30 V)."""
    nets, gate, drv = net_groups(comps)
    cl = {x: 0.1 for x in widths(comps)}
    for x in drv + ['VBAT']:
        cl[x] = 0.13
    cl['BUCK_LX'] = 0.15
    return cl


def via_rules(b):
    ds = b.GetDesignSettings()
    # the smallest via on the board is the QFN in-pad escape
    ds.m_ViasMinSize = MM(VIA_MICRO[0])
    ds.m_MinThroughDrill = MM(VIA_MICRO[1])
    ds.m_ViasMinAnnularWidth = MM((VIA_MICRO[0] - VIA_MICRO[1]) / 2)
    ds.m_HoleClearance = MM(HOLE_CL)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetViaDiameter(MM(VIA_SIG[0])); nc.SetViaDrill(MM(VIA_SIG[1]))


DRU_EXTRA = """# JLCPCB via-in-pad (POFV): ordered "Epoxy Filled & Capped", every via is
# filled; holes drilled afterwards (the unplated mounting holes and the
# plated battery pads) keep 0.45 mm from them.
(rule "POFV to drilled holes"
  (condition "A.Type == 'Via' && B.Type == 'Pad'")
  (constraint hole_to_hole (min 0.45mm)))
"""

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
    print('gate vias:', gate_vias(b, comps))
    nets, gate, drv = net_groups(comps)
    cl = clearances(comps)
    pcb.netclass(b, 'GATE', gate, width=0.2, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'SWITCH', drv, width=0.2, clearance=0.13, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'PWR', ['+3V3', 'GVDD', 'GVDD_IN', 'BUCK_VCC'], width=0.25, clearance=0.1,
                 via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'BUCKSW', ['BUCK_LX'], width=0.4, clearance=0.15, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'BAT', ['VBAT'], width=0.3, clearance=0.13, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    import fanout
    fanout.Obstacles.NET_CL = {x: c for x, c in cl.items() if c > 0.1}
    fanout.Obstacles.MARGIN = 0.01
    e2 = H - 0.4
    pins = escape_pins(b, comps)
    k, bad = fanout.dogbones(b, pins, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_MICRO)
    print('QFN escape vias: %d of %d, none for %s' % (k, len(pins), bad))
    k, failed = fanout.fanout(b, {'GND', 'VBAT'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2),
                              skip=power_refs(comps), **{x: y for x, y in FANOUT.items() if x != 'inpad'},
                              inpad=FANOUT['inpad'])
    print('fanout: %d plane vias, %d pads without one: %s' % (k, len(failed), failed))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


def escape_pins(b, comps):
    """QFN pins (MCUs and drivers) that get a dog-bone escape via: every
    pin whose net's nearest pad on another part is on the other side of the
    board, or whose net leaves the channel (signal, SWD, current sense)."""
    qfn = set()
    for n in CHANNELS:
        r = roles(comps, n)
        qfn |= {r['MCU'], r['GD']}
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                q = p.GetPosition()
                pads.setdefault(p.GetNetname(), []).append((fp.GetReference(), fp.IsFlipped(), q.x / 1e6, q.y / 1e6))
    out = []
    for ref in sorted(qfn):
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            net = p.GetNetname()
            if not net or net in ('GND', 'VBAT') or p.GetNumber() == '25':
                continue
            q = p.GetPosition(); x, y = q.x / 1e6, q.y / 1e6
            others = [(math.hypot(ox - x, oy - y), fl) for r_, fl, ox, oy in pads[net] if r_ != ref]
            if others and min(others)[1] != fp.IsFlipped():
                out.append((ref, p.GetNumber()))
    return out


# ============================================================ artwork
PRODUCT = 'Ridge 3'               # the lineup: Ridge 3 / 7 / 12, by prop size
FIRMWARE = 'RIDGE3_G071'          # the AM32 build to flash (firmware/am32)


def artwork(b, comps):
    """OffGrid silkscreen.  Top (it faces the flight controller): the
    motor number by every motor's pads, battery polarity, the pack range,
    pin 1 of the stack connector, the SWD pad names, the board's name, the
    front arrow.  Bottom (the side seen under the quad): the OffGrid mark at
    the board's centre, battery polarity, the front arrow.  Codes in JetBrains Mono, words in Instrument Sans.  Nothing
    lands on a pad, a hole or a part body."""
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
    for pl in (top, bot):
        pl.text([('mono', '2-6S')], [(x, y, 0, None) for x, y in pl.grid_spots((xb, 14.0), radius=12.0, step=0.2)],
                size=1.2)
    # the name and the firmware to flash, on top, before the small labels
    # take the room: on the centre line if anywhere there is room, else as
    # near it as fits, else turned to read along a free strip
    at = None
    for runs, cap in (([('sans', PRODUCT + ' ESC')], 1.4), ([('mono', FIRMWARE)], 1.1)):
        g0 = brand.line(runs, cap)[0].bounds
        mid = (g0[1] + g0[3]) / 2
        near = (0.0, at + 1.9) if at is not None else (0.0, 0.0)
        centred = [(0.0, near[1] + dy - mid, 0, None) for dy in sorted((0.1 * k for k in range(-90, 91)), key=abs)]
        pts = top.grid_spots(near, radius=16.0, step=0.25)
        anywhere = [(x, y - mid, 0, None) for x, y in pts]
        turned = [(x - mid, y, 90, None) for x, y in pts]
        for c in (cap, cap - 0.1, cap - 0.2, cap - 0.3):
            if any(top.text(runs, sp, size=c, vias='fewest') for sp in (centred, anywhere, turned)):
                at = top.placed[-1].centroid.y - pcb.CY
                break
    # SWD and supply test points, on whichever side they are
    for n in CHANNELS:
        r = roles(comps, n)
        pl = top if side[r['TP_DIO']] == 'T' else bot
        pl.label(r['TP_DIO'], 'D%d' % n, size=1.2, dist=0.7, smallest=1.0, face='mono')
    for ref, s_ in (('TP_3V3', '3V3'), ('TP_GND', 'GND'), ('TP_SWCLK', 'CLK')):
        (top if side[ref] == 'T' else bot).label(ref, s_, size=1.2, smallest=1.0, face='mono')
    top.label('J_FC', '1', pad='1', dist=0.8, size=1.2, smallest=0.9, face='mono')
    # the OffGrid mark at the exact centre of the bottom, in the square
    # kept free of parts for it (reserved()); only vias may sit under it
    for width in (2 * MARK_R - 0.4, 5.0, 4.5, 4.0):
        g, clear = brand.mark_mm(width)
        if bot.geom(g, [(0.0, 0.0)], clear=clear, vias='fewest', margin=0.0, quiet=True):
            break
    # which way is forward: the ESC must sit in the stack the same way round
    # as the FC, or every motor number is wrong
    for pl in (top, bot):
        spots = pl.grid_spots((0.0, -6.0), radius=11.0, step=0.25)
        if not any(pl.geom(brand.arrow_mm(2.6, 'Front', cap=1.2, mirror=pl.side == 'B'), spots, vias='fewest',
                           margin=m, quiet=True) for m in (0.6, 0.35)):
            pl.geom(brand.arrow_mm(2.6, mirror=pl.side == 'B'), spots, vias='fewest', margin=0.4)


if __name__ == '__main__':
    import sys
    build_placed(sys.argv[1] if len(sys.argv) > 1 else '/tmp/esc3.kicad_pcb', legal='--nolegal' not in sys.argv)
