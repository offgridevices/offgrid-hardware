# -*- coding: utf-8 -*-
"""4-in-1 ESC board: placement, power copper and silkscreen.

One motor channel is laid out once, as a template, and stamped four times:

    M2  right edge, top side          M3  left edge, top side
    M1  rear edge, bottom side        M4  front edge, bottom side

Each channel owns one board edge.  Its three half-bridges stand in a row
along that edge with their switch nodes facing out, straight into the
motor pads; the gate driver sits behind the middle half-bridge and the MCU
beside the driver.  Bottom-side channels are the template mirrored, so a
channel looks the same seen from its own side.  All twelve motor pads are
on top, where they can be soldered with the stack assembled; the bottom
channels reach them through via clusters.

The template is written for a channel on the REAR edge seen from above:
u runs along the edge (+u = right), yr is the ordinary board y (the edge
is at yr = +16.9, the board centre at yr = 0).

Stackup: F.Cu parts + power copper, In1 solid GND, In2 solid VBAT,
B.Cu parts + power copper.  Every FET pin goes to its plane through a
column of vias right beside it; a bulk capacitor sits directly under each
FET on the opposite side, between those same via columns.

The battery pads share the rear edge with motor 1's pads (rear-left: BAT+
outermost, BAT- next to it); motor 1's three pads sit rear-right.
"""
import math, os
import pcbnew
import pcb, circuit
from pcb import MM

H = pcb.HALF
Y0 = 12.15            # centre line of the FET row (yr)
PITCH = 5.2           # FET spacing along the edge
PAD_YR = 15.4         # motor pad centre (yr)
FET_U = {'A': PITCH, 'B': 0.0, 'C': -PITCH}

# channel: (rotation from the rear edge, side it is built on)
CHANNELS = {1: (0, 'B'), 2: (90, 'T'), 3: (-90, 'T'), 4: (180, 'B')}

# role: (u, yr, rotation, side)   side: 'same' / 'opp' (other side) / 'T'
#
# FLOORPLAN.  Seen in plan (top and bottom at once) the board has eight dense
# blocks: four drivers, one behind the middle of each FET row, and four
# MCUs, one in each corner.  No two of them are stacked: each has the other
# side of the board under it free (or holding a few small parts), which is
# where its vias go.
#
#   top channels (2, 3):  MCU beside the driver on its HIN side (+u), so
#       PA8-10 run straight across to HIN1-3 and PA7/PB0/PB1 loop round the
#       driver's input corner to LIN1-3.  Corners: M2 front-right, M3 rear-left.
#   bottom channels (1, 4): the other two corners (the +u corners already
#       hold the top-side MCUs).  The MCU sits on the driver's -u side,
#       lower (towards the board centre): PA8-10 face the driver across the
#       gap, PA7/PB0/PB1 face the FET row; the HIN and LIN bundles cross, so
#       part of them runs on the inner layers.  (Turning the MCU so that the
#       six inputs meet the driver as one uncrossed bundle was tried: the
#       bundle then runs over the driver's VCC pin, right under the FC
#       connector's pads, and VCC has no way out.)  Corners: M1 rear-right,
#       M4 front-left.
#
# The bootstrap capacitors stand in a row just behind the FETs, each in front
# of its half-bridge's switch node; the back-EMF dividers sit on the far side
# of the FET row by the motor pads (a free strip on the other side of the
# board), whose phase node they tap.


def fet_row(fu, pu):
    t = {}
    for ph in 'ABC':
        # half-bridges: switch node (exposed pad 10) facing the edge,
        # gates towards the driver
        t['Q' + ph] = (fu[ph], Y0, -90, 'same')
        t['P' + ph] = (pu[ph], PAD_YR, 0, 'T')
    # bulk decoupling right under each half-bridge, between its via columns
    t['C_BULK1'] = (fu['A'], Y0, 0, 'opp')
    t['C_HF'] = (fu['B'], Y0, 0, 'opp')
    t['C_BULK2'] = (fu['C'], Y0, 0, 'opp')
    return t


# Back-EMF: the resistor from each phase (R_Bx_H) and to the neutral
# (R_Nx) stand in the gaps beside that phase's motor pad, on top, touching
# its switch-node copper; the dividers' ground legs (R_Bx_L, R_N) sit at the
# MCU's comparator pins.  Slot u for each, relative to the motor pads.
def bemf_slots(pu):
    return {'R_BA_H': pu['A'] + 1.675, 'R_NA': pu['A'] - 1.675,
            'R_NB': pu['B'] + 1.675, 'R_BB_H': pu['B'] - 1.675,
            'R_NC': pu['C'] + 1.675, 'R_BC_H': pu['C'] - 1.675}

EDGE_YR = 15.15     # back-EMF resistors between the motor pads


# Surface routing channels kept free of parts (template u/yr boxes, the
# channel's own side): top channels' PA8-10 run straight across to HIN1-3,
# their PA7/PB0/PB1 loop under the driver-MCU gap to LIN1-3.
TOP_CHANNELS = [(2.4, 4.9, 4.3, 6.95),                    # HIN, driver -> MCU
                (0.55, 2.5, 1.95, 4.7), (0.55, 2.5, 6.85, 3.2), (5.45, 2.5, 6.85, 3.6),   # LIN U
                (2.75, 6.95, 4.15, 9.45)]                  # HO1/VB1/SWD up the gap
BOT_CHANNELS = []


def top_template(fu, pu):
    """Channel built on the top side (M2, M3)."""
    sw = {ph: fu[ph] + 0.42 for ph in 'ABC'}      # switch-node pad centre (u)
    t = {
        # driver: VS/HO/VB face to the FETs, HIN side (+u) to the MCU
        'GD': (0.5, 6.9, -90, 'same'),
        'MCU': (6.9, 6.4, 90, 'same'),
        # bootstrap capacitors in a row in front of the switch nodes
        'C_BA': (sw['A'], 9.95, 0, 'same'),
        'C_BB': (0.75, 9.95, 180, 'same'),
        'C_BC': (sw['C'], 9.95, 0, 'same'),
        'D_A': (4.2334, 10.3357, 180, 'opp'),
        'D_B': (1.9004, 10.1858, 0, 'opp'),
        'D_C': (-10.1314, 9.2947, 90, 'same'),
        # driver supply: HF cap and clamp at VCC/COM, bulk cap and the
        # 330 ohm out in the corner pocket beside FET C
        'C_VCCHF': (-0.381, 3.9192, 180, 'same'),
        'D_Z': (-0.5473, 2.8307, 180, 'same'),
        'C_VCC': (-8.6, 12.5, -90, 'same'),
        'R_VCC': (-8.6, 10.1, 0, 'same'),
        # MCU decoupling; SWD pads in the corner pocket beside FET A
        'C_VDD17': (2.9088, 3.8259, 180, 'same'),
        'C_VDDA': (10.135, 1.2227, 90, 'same'),
        'C_RST': (10.5305, 8.9757, -90, 'same'),
        'C_VDD1': (8.6766, 9.9835, 180, 'same'),
        'TP_DIO': (8.9, 11.2, 0, 'same'),
        'TP_CLK': (8.9, 12.6, 0, 'same'),
        'R_BA_L': (7.9012, 2.7549, 0, 'same'), 'R_BB_L': (9.9146, 2.7386, 0, 'same'),
        'R_BC_L': (10.5657, 7.0247, -90, 'same'), 'R_N': (10.5604, 4.6478, 90, 'same'),
    }
    for k, u in bemf_slots(pu).items():
        t[k] = (u, EDGE_YR, 90, 'same')
    return t


def bottom_template(fu, pu):
    """Channel built on the bottom side (M1, M4), seen from its own side."""
    sw = {ph: fu[ph] + 0.42 for ph in 'ABC'}
    t = {
        # driver behind FET B; MCU on its -u side, lower, its PA8-10 side
        # facing the driver across the gap and its PA7/PB0/PB1 side facing
        # the FET row: both land where the other side of the board is free
        'GD': (-0.5, 6.9, -90, 'same'),
        'MCU': (-6.4, 4.7, -90, 'same'),
        'C_BA': (sw['A'], 9.95, 0, 'same'),
        'C_BB': (sw['B'], 9.95, 0, 'same'),
        'C_BC': (sw['C'], 9.95, 0, 'same'),
        'D_A': (2.5731, 8.1601, 90, 'same'),
        'D_B': (-4.1301, 8.718, 180, 'same'),
        'D_C': (-6.384, 8.7113, 180, 'same'),
        'C_VCCHF': (-1.1704, 3.8623, 180, 'same'),
        'D_Z': (-2.7194, 3.2578, 90, 'same'),
        'C_VCC': (-8.6, 12.5, -90, 'same'),
        'R_VCC': (-8.6, 10.1, 0, 'same'),
        'C_VDD17': (-3.8796, 8.9807, -90, 'opp'),
        'C_VDDA': (-10.1303, 1.921, 90, 'same'),
        'C_RST': (-10.0334, 6.1242, -90, 'same'),
        'C_VDD1': (-10.0303, 3.8753, -90, 'same'),
        'TP_DIO': (8.9, 11.2, 0, 'same'),
        'TP_CLK': (8.9, 12.6, 0, 'same'),
        'R_BA_L': (-6.4209, 8.573, 0, 'opp'), 'R_BB_L': (-10.0604, 8.1149, -90, 'same'),
        'R_BC_L': (-8.5072, 8.3664, 0, 'same'), 'R_N': (-8.426, 8.5655, 0, 'opp'),
    }
    # the phase-side resistors on top, between the motor pads
    for k, u in bemf_slots(pu).items():
        t[k] = (u, EDGE_YR, 90, 'opp')
    return t


# Motor 1 shares the rear edge with the battery pads: its FET row moves right
# and its pads move right of the battery pads.  u here is template u (the
# channel is mirrored: global x = -u).
# (global x = -u: FETs at x = -3.0, 2.2, 7.4, pads at x = -0.9, 2.2, 7.4;
#  7.4 is as far right as FET C's outer via column clears hole H3)
M1_FET_U = {'A': 3.0, 'B': -2.2, 'C': -7.4}
M1_PAD_U = {'A': 0.9, 'B': -2.2, 'C': -7.4}


def xf_point(n, u, yr):
    theta, cside = CHANNELS[n]
    x, y = (-u if cside == 'B' else u), yr
    a = math.radians(theta)
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))


def xf(n, u, yr, rot, side_rel):
    theta, cside = CHANNELS[n]
    if side_rel == 'same':
        side = cside
    elif side_rel == 'opp':
        side = 'B' if cside == 'T' else 'T'
    else:
        side = side_rel
    if cside == 'B':
        rot = 180 - rot
    x, y = xf_point(n, u, yr)
    return (round(x, 4), round(y, 4), (rot + theta) % 360, side)


def roles(comps, n):
    """Map template roles to this channel's references."""
    out = {}
    blk = 'esc%d' % n
    bulk = 0
    for c in comps:
        if c.block != blk:
            continue
        note = c.note
        if c.ref.startswith('U_ESC'): out['MCU'] = c.ref
        elif c.ref.startswith('U_GD'): out['GD'] = c.ref
        elif c.ref.startswith('Q'): out['Q' + c.ref[-1]] = c.ref
        elif c.ref.startswith('P_M'): out['P' + c.ref[-1]] = c.ref
        elif c.ref.startswith('TP_E'): out['TP_DIO' if c.ref.endswith('DIO') else 'TP_CLK'] = c.ref
        elif note.endswith('VDD pin 1'): out['C_VDD1'] = c.ref
        elif note.endswith('VDD pin 17'): out['C_VDD17'] = c.ref
        elif note.endswith('VDDA'): out['C_VDDA'] = c.ref
        elif note.endswith('reset filter'): out['C_RST'] = c.ref
        elif note == 'driver VCC filter': out['R_VCC'] = c.ref
        elif note == 'driver VCC bulk': out['C_VCC'] = c.ref
        elif note == 'driver VCC HF': out['C_VCCHF'] = c.ref
        elif note == 'driver VCC clamp': out['D_Z'] = c.ref
        elif note.startswith('bootstrap '):
            ph = note[-1]
            out[('D_' if c.ref.startswith('D') else 'C_B') + ph] = c.ref
        elif note.startswith('BEMF '):
            ph = note[-1]
            out['R_B%s_%s' % (ph, 'H' if c.part == 'R10K' else 'L')] = c.ref
        elif note.startswith('neutral to'): out['R_N'] = c.ref
        elif note.startswith('neutral '): out['R_N' + note[-1]] = c.ref
        elif note.endswith(' bulk'):
            bulk += 1
            out['C_BULK%d' % bulk] = c.ref
        elif note.endswith(' HF'): out['C_HF'] = c.ref
        else:
            raise KeyError('unplaced role for %s (%s)' % (c.ref, note))
    return out


def channel_template(n):
    fu, pu = (M1_FET_U, M1_PAD_U) if n == 1 else (FET_U, FET_U)
    t = fet_row(fu, pu)
    t.update(top_template(fu, pu) if CHANNELS[n][1] == 'T' else bottom_template(fu, pu))
    if n == 1:
        # FET A sits half under BAT-: its HF capacitor fits beside the pad
        t['C_BULK1'] = (M1_FET_U['B'], Y0, 0, 'opp')
        t['C_HF'] = (2.0, Y0, 90, 'opp')
    t.update(CH_OVERRIDE.get(n, {}))
    t.update(OPT.get('T' if CHANNELS[n][1] == 'T' else 'B', {}))
    if n == 1:
        t.update(OPT.get('1', {}))
    return t


# optimiser output (place_opt.py), applied over the tables when present
OPT = {}


def load_opt(path):
    import json
    d = json.load(open(path))
    OPT.clear()
    for k, v in d.items():
        kind, name = k.split('|', 1)
        if kind == 'P':
            POWER[name] = tuple(v)
        else:
            OPT.setdefault(kind, {})[name] = tuple(v)


if os.environ.get('ESC_OPT'):
    pass    # loaded after POWER is defined (see below)


CH_OVERRIDE = {
    1: {  # back-EMF: top slots where the battery pads leave room, the rest
          # on the bottom between the switch-node pours (u = -x)
        'R_BA_H': (2.6, EDGE_YR, 90, 'opp'), 'R_NA': (-0.65, EDGE_YR, 90, 'same'),
        'R_BB_H': (-3.9, EDGE_YR, 90, 'opp'), 'R_NB': (-3.75, EDGE_YR, 90, 'same'),
        'R_BC_H': (-5.7, EDGE_YR, 90, 'opp'), 'R_NC': (-9.1, EDGE_YR, 90, 'opp'),
        # driver supply and SWD pads in the pocket beside motor 2's FET C
        'C_VCC': (-12.5, 8.6, 180, 'same'), 'R_VCC': (-15.3, 8.0, 90, 'same'),
        'TP_DIO': (-15.6, 5.3, 0, 'same'), 'TP_CLK': (-15.6, 4.0, 0, 'same'),
    },
}


# ---------------------------------------------------------------- power pads
POWER = {
    'P_BAT+': (-8.2, 13.9, 0, 'T'),
    'P_BAT-': (-4.6, 13.9, 0, 'T'),
    'J_FC':   (0.0, 0.0, 90, 'T'),
    # 3.3 V buck for the four MCUs: bottom centre, under the FC connector
    'U_BUCK': (-2.1267, 0.0648, 90, 'B'),
    'L1':     (2.5141, -0.2816, -90, 'B'),
    'C1':     (-2.3331, 2.7348, 0, 'B'),
    'C2':     (0.2731, 0.5439, -90, 'B'),
    'C3':     (1.4951, 2.4205, 0, 'B'),
    'C4':     (1.6681, -3.4969, 180, 'B'),
    'R1':     (0.31, -1.438, -90, 'B'),
    'R2':     (-0.0237, 2.526, -90, 'B'),
    # small parts on the free strips under the side motor pads
    'C5':     (-15.6, -8.2, 90, 'B'),
    'R4':     (-15.604, -2.3271, 0, 'B'),
    'R5':     (-15.5801, 8.4859, 180, 'B'),
    'C6':     (-15.0246, 9.128, -90, 'T'),
    'LED_PWR': (15.5, -8.6, 90, 'B'),
    'R3':     (14.4, -8.6, 90, 'B'),
    'TP_3V3': (-15.5, 0.0, 0, 'B'),
    'TP_GND': (-15.5, 1.3, 0, 'B'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
}


if os.environ.get('ESC_OPT'):
    load_opt(os.environ['ESC_OPT'])


def placement(comps):
    place = dict(POWER)
    for n in CHANNELS:
        r = roles(comps, n)
        t = channel_template(n)
        for role, ref in r.items():
            place[ref] = xf(n, *t[role])
    return place


FIXED_ROLES = ('QA', 'QB', 'QC', 'PA', 'PB', 'PC', 'C_BULK1', 'C_BULK2', 'C_HF', 'GD', 'MCU')


def fixed(comps):
    f = {'P_BAT+', 'P_BAT-', 'J_FC', 'H1', 'H2', 'H3', 'H4'}
    for n in CHANNELS:
        r = roles(comps, n)
        f |= {r[k] for k in FIXED_ROLES}
    return f


if __name__ == '__main__':
    import sys
    comps = circuit.build('esc')
    pl = placement(comps)
    missing = [c.ref for c in comps if c.ref not in pl]
    print('placed %d of %d; missing %s' % (len(pl), len(comps), missing))


def build_placed(out_path, legal=True):
    b = pcb.new_board(LAYERS)
    via_rules(b)
    pcb.outline(b)
    comps = circuit.build('esc')
    place = placement(comps)
    if legal:
        import legalize
        place, left = legalize.legalize(comps, place, fixed(comps))
    fps = pcb.place_components(b, comps, place)
    b.Save(out_path)
    return b, comps, fps


# ---------------------------------------------------------------- power copper
VIA_D, VIA_DRILL = 0.5, 0.3          # power vias
COL_DY = (-0.4, 0.35, 1.1)           # via column positions along the FET, from Y0
COL_DX = 2.1                         # via column distance from the FET centre


def _layer(n, side_rel):
    cside = CHANNELS[n][1]
    side = cside if side_rel == 'same' else ('B' if cside == 'T' else 'T')
    return pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu


def _in_keepout(x, y, r):
    return any(math.hypot(x - sx * pcb.HOLE, y - sy * pcb.HOLE) < pcb.HOLE_KEEPOUT_R + r + 0.05
               for sx in (-1, 1) for sy in (-1, 1))


def _zone(b, n, net, side_rel, pts, prio=3, name=None):
    poly = [xf_point(n, u, yr) for u, yr in pts]
    z = pcb.zone(b, net, _layer(n, side_rel), poly, clearance=0.15, min_width=0.2, priority=prio,
                 thermal=False, name=name)
    return z


def _via(b, n, u, yr, net, count):
    x, y = xf_point(n, u, yr)
    if _in_keepout(x, y, VIA_D / 2):
        return 0
    v = pcb.via(b, x, y, net, d=VIA_D, drill=VIA_DRILL)
    v.SetLocked(True)
    count[net] = count.get(net, 0) + 1
    return 1


def power_copper(b, comps):
    """Via columns, switch-node copper and bulk-capacitor copper for every
    half-bridge; vias in the battery pads.  Returns via counts per net."""
    count = {}
    for n in CHANNELS:
        t = channel_template(n)
        for ph in 'ABC':
            x0, y0 = t['Q' + ph][0], t['Q' + ph][1]
            px = t['P' + ph][0]
            sw = 'M%d_%s' % (n, ph)
            # plane via columns: VBAT beside pins 2-4, GND beside pins 5-7
            for dy in COL_DY:
                _via(b, n, x0 - COL_DX, y0 + dy, 'VBAT', count)
                _via(b, n, x0 + COL_DX, y0 + dy, 'GND', count)
            # pins + exposed pad 9 + via column, on the FET's side
            _zone(b, n, 'VBAT', 'same', [(x0 - 2.5, y0 - 1.3), (x0 - 0.3, y0 - 1.3),
                                         (x0 - 0.3, y0 + 1.45), (x0 - 2.5, y0 + 1.45)])
            _zone(b, n, 'GND', 'same', [(x0 + 1.05, y0 - 0.75), (x0 + 2.5, y0 - 0.75),
                                        (x0 + 2.5, y0 + 1.45), (x0 + 1.05, y0 + 1.45)])
            # switch node: exposed pad 10 straight out to the motor pad
            xl, xr = min(x0, px) - 1.0, max(x0, px) + 1.0
            _zone(b, n, sw, 'same', [(x0 - 0.12, y0 - 1.3), (x0 + 0.96, y0 - 1.3), (x0 + 0.96, y0 + 1.4),
                                     (xr, y0 + 1.4), (xr, 16.5), (xl, 16.5), (xl, y0 + 1.4),
                                     (x0 - 0.12, y0 + 1.4)], name='switch node')
            # the back-EMF resistors standing beside this phase's motor pad:
            # a copper tab from the pad (or the switch-node pour) to their
            # phase-end pad, so no trace has to come here
            for role in ('R_B%s_H' % ph, 'R_N%s' % ph):
                ur, yr_r, rot_r, side_r = t[role]
                if abs(yr_r - EDGE_YR) > 0.01:
                    continue
                on_fet_side = (_layer(n, side_r) == _layer(n, 'same'))
                lo, hi = (xl, xr) if on_fet_side else (px - 1.0, px + 1.0)
                if ur > hi:
                    ua, ub = hi - 0.1, ur + 0.1
                elif ur < lo:
                    ua, ub = ur - 0.1, lo + 0.1
                else:
                    continue
                y1 = yr_r + 0.51
                _zone(b, n, sw, side_r, [(ua, y1 - 0.24), (ub, y1 - 0.24), (ub, y1 + 0.24), (ua, y1 + 0.24)],
                      prio=4, name='bemf tab')
            if CHANNELS[n][1] == 'B':
                # bottom channel: the pad is on top, reached by vias in the pad
                # (3 x 2 at 0.76 / 0.8 mm pitch: POFV holes > 0.45 mm apart)
                for du in (-0.76, 0.0, 0.76):
                    for yr in (PAD_YR - 0.4, PAD_YR + 0.4):
                        _via(b, n, px + du, yr, sw, count)
            # bulk capacitor under the FET, joined to the same via columns
            if not (n == 1 and ph == 'A'):
                _zone(b, n, 'VBAT', 'opp', [(x0 - 2.5, y0 - 0.75), (x0 - 0.3, y0 - 0.75),
                                            (x0 - 0.3, y0 + 1.45), (x0 - 2.5, y0 + 1.45)])
                _zone(b, n, 'GND', 'opp', [(x0 + 0.3, y0 - 0.75), (x0 + 2.5, y0 - 0.75),
                                           (x0 + 2.5, y0 + 1.45), (x0 + 0.3, y0 + 1.45)])
    # battery pads: a grid of vias into the planes, wherever the other side
    # (motor 1's FET A sits under BAT-) and the vias already there allow
    import fanout
    from shapely.geometry import Point
    obs = fanout.Obstacles(b, [pcbnew.F_Cu, pcbnew.B_Cu])
    for ref, net in (('P_BAT+', 'VBAT'), ('P_BAT-', 'GND')):
        cx, cy = POWER[ref][0], POWER[ref][1]
        for dx in (-0.76, 0.0, 0.76):          # 0.76 mm grid: POFV hole spacing
            for dy in (-1.83, -1.07, -0.31, 0.45, 1.21, 1.97):
                x, y = cx + dx, cy + dy
                g = Point(pcb.CX + x, pcb.CY + y).buffer(VIA_D / 2)
                if _in_keepout(x, y, VIA_D / 2) or not obs.via_room(pcb.CX + x, pcb.CY + y, VIA_D + 0.2):
                    continue
                if not obs.clear(g, net, [pcbnew.F_Cu, pcbnew.B_Cu], 0.2):
                    continue
                v = pcb.via(b, x, y, net, d=VIA_D, drill=VIA_DRILL); v.SetLocked(True)
                obs.add(g, net, [pcbnew.F_Cu, pcbnew.B_Cu]); obs.vias.append((pcb.CX + x, pcb.CY + y))
                count[net] = count.get(net, 0) + 1
    return count


def routing_keepouts(b):
    """Rule areas (no tracks, no vias) over the half-bridge pours, added only
    to the copy of the board handed to Freerouting: it treats pours as
    planes other nets may cross, and a trace across a pour splits it when
    the pour is refilled.  Openings are left where connections land: each
    high-side gate pad (inside the VBAT pour) and the inner tip of each
    switch-node pour (driver VS pin, bootstrap capacitor)."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    n_added = 0
    for n in CHANNELS:
        t = channel_template(n)
        for ph in 'ABC':
            x0, y0 = t['Q' + ph][0], t['Q' + ph][1]
            px = t['P' + ph][0]
            xl, xr = min(x0, px) - 1.0, max(x0, px) + 1.0
            areas = {'same': [], 'opp': []}
            vb = box(x0 - 2.5, y0 - 1.3, x0 - 0.3, y0 + 1.45).difference(box(x0 - 2.05, y0 - 1.5, x0 - 0.95, y0 - 0.45))
            areas['same'] += [vb, box(x0 + 1.05, y0 - 0.75, x0 + 2.5, y0 + 1.45)]
            sw = unary_union([box(x0 - 0.12, y0 - 1.3, x0 + 0.96, y0 + 1.4), box(xl, y0 + 1.4, xr, 16.5)])
            areas['same'].append(sw.difference(box(x0 - 0.6, y0 - 1.5, x0 + 1.5, y0 - 0.8)))
            if not (n == 1 and ph == 'A'):
                areas['opp'] += [box(x0 - 2.5, y0 - 0.75, x0 - 0.3, y0 + 1.45), box(x0 + 0.3, y0 - 0.75, x0 + 2.5, y0 + 1.45)]
            for side_rel, geoms in areas.items():
                for g in geoms:
                    for poly in (g.geoms if hasattr(g, 'geoms') else [g]):
                        pts = [xf_point(n, u, yr) for u, yr in list(poly.exterior.coords)[:-1]]
                        pcb.rule_area(b, pts, [_layer(n, side_rel)], tracks=True, vias=True, pads=False,
                                      pours=False, name='pour keepout')
                        n_added += 1
    # Freerouting keeps only its own clearance from the outline, not the
    # board's 0.3 mm copper-to-edge rule: a 0.3 mm strip along each edge
    h, w = pcb.HALF, 0.3
    cu = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)
          if b.IsLayerEnabled(l)]
    for x0, y0, x1, y1 in ((-h, -h, h, -h + w), (-h, h - w, h, h), (-h, -h, -h + w, h), (h - w, -h, h, h)):
        pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cu, tracks=True, vias=True, pads=False,
                      pours=False, name='edge keepout')
        n_added += 1
    return n_added


def fet_refs(comps):
    out = set()
    for n in CHANNELS:
        r = roles(comps, n)
        out |= {r[k] for k in ('QA', 'QB', 'QC', 'C_BULK1', 'C_BULK2', 'C_HF')}
    out |= {'P_BAT+', 'P_BAT-'}
    out.discard(roles(comps, 1)['C_HF'])      # motor 1's HF cap has no zone: fan it out
    return out


# Six layers.  Every patch of this board carries a half-bridge channel on
# one side and another on the other side, so four layers left too few
# routing layers (Freerouting and the in-house router both stalled at over
# a hundred open connections).  Stackup: F signals | In1 GND | In2, In3
# signals | In4 VBAT | B signals.
LAYERS = 6
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]


def net_groups(comps):
    nets = set(net for c in comps for net in c.pins.values() if net)
    gate = sorted(n for n in nets if n[:1] == 'M' and n[2:5] in ('_GH', '_GL', '_VB'))
    drv = sorted(n for n in nets if n[:1] == 'M' and n[2:] in ('_VCC', '_A', '_B', '_C'))
    return nets, gate, drv


# Net widths for the router: gate drive and bootstrap 0.2 mm, driver supply
# and switch-node sense 0.25 mm, 3.3 V 0.25 mm, buck switch node 0.4 mm.
def widths(comps):
    nets, gate, drv = net_groups(comps)
    w = {n: 0.2 for n in gate}
    w.update({n: 0.2 for n in drv})
    w.update({'+3V3': 0.2, 'BUCK_SW': 0.4, 'BUCK_CB': 0.2, 'VBAT': 0.3})
    return w


# Clearances.  Nothing on this board exceeds 16.8 V (plus switching
# overshoot), where IPC-2221B asks 0.1 mm between outer-layer conductors
# (B2, 16-30 V).  0.1 mm everywhere, 0.15 round the buck's switch node.
# Space for vias is what limits this board, so no more than that.
def clearances(comps):
    return {n: (0.15 if n == 'BUCK_SW' else 0.1) for n in widths(comps)}

# Vias.  This is a 6-layer JLCPCB build, which makes 0.25/0.15 mm vias and
# via-in-pad (epoxy filled, copper capped: POFV) at standard price.
#   signal vias (Freerouting, finisher)             0.35 / 0.2 mm
#   plane vias in passive pads and signal escape
#   vias in pads (POFV)                             0.45 / 0.3 mm  (JLC's free size)
#   plane vias in QFN exposed pads (POFV)           0.45 / 0.3 mm
#   plane vias beside a pad that cannot take one    0.45 / 0.25 mm
#   FET, battery and motor-pad power vias           0.5 / 0.3 mm
# Every 0.3 mm drill is an in-pad (filled) or power via; in-pad holes keep
# more than 0.45 mm to any other hole (JLC's POFV rule, DRU_EXTRA below).
# Hole to other-net copper 0.15 mm (a 0.35/0.2 via at 0.1 mm clearance
# gives 0.175).  Space for vias is what limits this board.
VIA_SIG = (0.35, 0.2)

# Extra DRC rule for the ESC (pcb.write_rules(path, DRU_EXTRA)): JLCPCB's
# via-in-pad (POFV) holes must stay more than 0.45 mm from any other hole.
# Every 0.3 mm-drill via here is an in-pad or power via (signal vias are
# 0.2 mm), so the rule is keyed on the drill.  The FET via columns sit at
# exactly 0.45 mm (not in pads), hence min 0.45.
DRU_EXTRA = '''# JLCPCB via-in-pad (POFV): filled via holes keep 0.45 mm from other holes.
(rule "POFV hole spacing"
  (condition "A.Type == 'Via' && A.Hole >= 0.29mm")
  (constraint hole_to_hole (min 0.45mm)))
'''
ESCAPE_FAR = float(os.environ.get('ESCAPE_FAR', 5.0))   # see fanout.escape_vias
VIA_INPAD = (0.45, 0.3)
VIA_OFFPAD = (0.45, 0.25)   # plane via beside a pad that cannot take one
HOLE_CL = 0.15


def via_rules(b):
    ds = b.GetDesignSettings()
    ds.m_ViasMinSize = MM(VIA_SIG[0])
    ds.m_MinThroughDrill = MM(VIA_SIG[1])
    ds.m_ViasMinAnnularWidth = MM((VIA_SIG[0] - VIA_SIG[1]) / 2)
    ds.m_HoleClearance = MM(HOLE_CL)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetViaDiameter(MM(VIA_SIG[0])); nc.SetViaDrill(MM(VIA_SIG[1]))


# Plane fan-out: every ground/pack pad of a passive gets its plane via in the
# pad itself; QFN ground pins join their own exposed pad; four vias in each
# MCU/driver exposed pad (a 1.5 mm grid) are plenty and leave the inner
# layers under them to the router.  Where a pad cannot take a via (the other
# side of the board is occupied there), a via beside it, or a stub to a
# ground via within 0.9 mm.
FANOUT = dict(ep_pitch=float(os.environ.get('FANOUT_EP', 1.5)), share=float(os.environ.get('FANOUT_SHARE', 0.9)),
              ep_join=0.2, via_d=VIA_INPAD[0], via_drill=VIA_INPAD[1], off_drill=VIA_OFFPAD[1], clearance=0.1,
              steps=(0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3, 1.7, 2.1, 2.5), far_share=3.0)
if os.environ.get('FANOUT_INPAD', '1') == '1':
    FANOUT['inpad'] = dict(d=VIA_INPAD[0], drill=VIA_INPAD[1], cl=0.1, hole_cl=HOLE_CL, hole_gap=0.45, min_pad=0.34)


def build(out_path):
    b, comps, fps = build_placed(out_path)
    cu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    pcb.hole_keepouts(b, cu)
    e = H - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    pcb.zone(b, 'GND', pcbnew.In1_Cu, full, name='GND plane', thermal=False)
    pcb.zone(b, 'VBAT', pcbnew.In4_Cu, full, name='VBAT plane', thermal=False)
    for l, t in ((pcbnew.In1_Cu, pcbnew.LT_POWER), (pcbnew.In2_Cu, pcbnew.LT_SIGNAL),
                 (pcbnew.In3_Cu, pcbnew.LT_SIGNAL), (pcbnew.In4_Cu, pcbnew.LT_POWER)):
        b.SetLayerType(l, t)
    count = power_copper(b, comps)
    print('power vias:', count)
    nets, gate, drv = net_groups(comps)
    pcb.netclass(b, 'GATE', gate, width=0.2, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'DRIVE', drv, width=0.2, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'PWR', ['+3V3', 'BUCK_CB'], width=0.2, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'SW', ['BUCK_SW'], width=0.4, clearance=0.15, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'BAT', ['VBAT'], width=0.3, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    import fanout
    fanout.Obstacles.NET_CL = {n: c for n, c in clearances(comps).items() if c > 0.1}
    fanout.Obstacles.MARGIN = 0.01
    e2 = H - 0.4
    n, failed = fanout.fanout(b, {'GND', 'VBAT'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2),
                              skip=fet_refs(comps), **FANOUT)
    print('fanout: %d plane vias, %d pads without one: %s' % (n, len(failed), failed))
    if 'inpad' in FANOUT and os.environ.get('ESCAPE_VIAS', '1') == '1':
        k = fanout.escape_vias(b, {'GND', 'VBAT'}, FANOUT['inpad'], far=ESCAPE_FAR, refs=('J_FC',),
                               bounds=(pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2))
        print('escape vias in pads:', k)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


# ---------------------------------------------------------------- artwork
def artwork(b, comps):
    """OffGrid silkscreen: motor number at every motor pad, battery
    polarity, SWD pad names, front arrows, the bare mark and what the board is.
    Codes in JetBrains Mono, words in Instrument Sans.  Nothing lands on a
    pad, a hole or a part body."""
    import artwork as A, brand
    from shapely.geometry import box
    from shapely.ops import unary_union
    A.hide_fields(b)
    A.strip(b)
    top = A.SilkPlacer(b, 'T', bodies=True, brand=True, via_clear=0.1)
    bot = A.SilkPlacer(b, 'B', bodies=True, brand=True, via_clear=0.1)
    side = {fp.GetReference(): ('B' if fp.IsFlipped() else 'T') for fp in b.GetFootprints()}
    # battery polarity first (square-ended strokes, outboard of each pad),
    # then every motor pad's motor number beside it along the edge (the
    # order of a motor's three wires does not matter)
    def sign(plus, s=0.4, w=0.3):
        g = box(-s, -w / 2, s, w / 2)
        return unary_union([g, box(-w / 2, -s, w / 2, s)]) if plus else g
    xp, yp = POWER['P_BAT+'][:2]; xm, ym = POWER['P_BAT-'][:2]
    # outboard of each pad, level with each other
    for plus, x0, y0 in ((True, xp, yp), (False, xm, ym)):
        beside = [(x0 + (-1) ** plus * (1.3 + d), y0 + dy) for d in (0.55, 0.6, 0.7, 0.8, 0.95)
                  for dy in (1.0, 1.6, 0.4, 2.0, 0.0)]
        top.geom(sign(plus), beside, vias=False, margin=0.12)
    # one number per motor, as large as fits, in the nearest free spot that
    # is clearly this motor's: at least 2 mm nearer its own three pads than
    # any other motor's pads or the battery pads (so '1' never reads '-1')
    import math
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
    # the one limit that matters, beside the battery pads
    top.text([('mono', '4S'), ('sans', 'only')],
             [(x, y, 0, None) for x, y in top.grid_spots(((xp + xm) / 2, 9.5), radius=8.0, step=0.25)], size=1.2)
    # SWD pads, labelled on whichever side they are
    for n in CHANNELS:
        r = roles(comps, n)
        for key, s_ in (('TP_DIO', 'D%d' % n), ('TP_CLK', 'C%d' % n)):
            pl = top if side[r[key]] == 'T' else bot
            pl.label(r[key], s_, size=1.2, dist=0.7, smallest=1.1, face='mono')
    bot.label('TP_3V3', '3V3', size=1.2, face='mono')
    bot.label('TP_GND', 'GND', size=1.2, face='mono')
    top.label('J_FC', '1', pad='1', dist=0.8, size=1.2, face='mono')
    # which way is forward: the ESC must sit in the stack the same way round
    # as the FC, or every motor number is wrong
    for pl in (top, bot):
        spots = pl.grid_spots((0.0, -6.0), radius=11.0, step=0.25)
        if not pl.geom(brand.arrow_mm(2.6, 'Front', cap=1.2, mirror=pl.side == 'B'), spots, vias='fewest',
                       margin=0.25, quiet=True):
            pl.geom(brand.arrow_mm(2.6), spots, vias='fewest', margin=0.25)
    # This board is full edge to edge: no room for the lockup, so the bare
    # mark (the brand's everywhere mark), with what the board is beside it
    placed = None
    for width in (4.0, 3.5, 3.0):
        g, clear = brand.mark_mm(width)
        for pl in (bot, top):
            at = pl.geom(g, pl.grid_spots((0.0, 0.0), radius=17.0, step=0.25), clear=clear, vias='fewest',
                         quiet=True)
            if at:
                placed = (pl, at)
                break
        if placed:
            break
    pl, near = (placed[0], placed[1]) if placed else (bot, (0.0, 0.0))
    for runs, cap in (([('sans', 'Cheap drone ESC'), ('mono', 'v1')], 1.2),):
        for p in (pl, top if pl is bot else bot):
            spots = [(x, y, 0, None) for x, y in p.grid_spots(near, radius=17.0, step=0.25)]
            if p.text(runs, spots, size=cap, vias='fewest'):
                near = (p.placed[-1].centroid.x - pcb.CX, p.placed[-1].centroid.y - pcb.CY)
                break
