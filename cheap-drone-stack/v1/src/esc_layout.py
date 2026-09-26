# -*- coding: utf-8 -*-
"""4-in-1 ESC board: placement, power copper and silkscreen.

One motor channel is laid out once, as a template, and stamped four times,
all on the bottom side: M1 on the rear edge, M2 right, M3 left, M4 front.

Each channel owns one board edge.  Its three half-bridges stand in a row
along that edge with their switch nodes facing out, straight into the
motor pads; the gate driver sits behind the middle half-bridge and the MCU
beside the driver.  The channels are the template mirrored, so a channel
looks the same seen from its own side.  All twelve motor pads are on top,
where they can be soldered with the stack assembled; the channels reach
them through via clusters.

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
CHANNELS = {1: (0, 'B'), 2: (90, 'B'), 3: (-90, 'B'), 4: (180, 'B')}

# role: (u, yr, rotation, side)   side: 'same' / 'opp' (other side) / 'T'
#
# FLOORPLAN.  Seen in plan (top and bottom at once) the board has eight dense
# blocks: four drivers, one behind the middle of each FET row, and four
# MCUs, one in each corner.  No two of them are stacked: each has the other
# side of the board under it free (or holding a few small parts), which is
# where its vias go.
#
#   Every channel is built on the bottom, from the one template: the MCU
#       beside the driver on its HIN side (+u), so PA8-10 run straight
#       across to HIN1-3 and PA7/PB0/PB1 loop round the driver's input
#       corner to LIN1-3.  All four have the same handedness, so each MCU
#       takes a different corner (M1 rear-left, M2 rear-right, M3
#       front-left, M4 front-right), just behind the next channel's FET C.
#       The top side carries only the motor and battery pads, the FC
#       connector, the bulk capacitors under the FETs and a few small
#       parts, so it is free for vias.
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
# channel's own side): PA8-10 run straight across to HIN1-3, PA7/PB0/PB1
# loop under the driver-MCU gap to LIN1-3.
TOP_CHANNELS = [(2.4, 4.9, 4.3, 6.95),                    # HIN, driver -> MCU
                (0.55, 2.5, 1.95, 4.7), (0.55, 2.5, 6.85, 3.2), (5.45, 2.5, 6.85, 3.6),   # LIN U
                (2.75, 6.95, 4.15, 9.45)]                  # HO1/VB1/SWD up the gap


def top_template(fu, pu):
    """The channel template (every channel is built from it, on the bottom)."""
    sw = {ph: fu[ph] + 0.42 for ph in 'ABC'}      # switch-node pad centre (u)
    t = {
        # driver: VS/HO/VB face to the FETs, HIN side (+u) to the MCU
        'GD': (0.5, 6.9, -90, 'same'),
        'MCU': (6.9, 6.4, 90, 'same'),
        # bootstrap capacitors in a row in front of the switch nodes
        'C_BA': (sw['A'], 9.95, 0, 'same'),
        'C_BB': (fu['B'] + 0.75, 9.95, 180, 'same'),
        # C's bootstrap capacitor: the next channel's MCU stands right behind
        # FET C, so it sits on top, just inside FET C's bulk capacitor and
        # clear of that MCU's pin escapes; a stub from its VS pad to a filled
        # via takes it down into the switch node's inner tip (boot_vias)
        'C_BC': (sw['C'] + 1.38, 10.45, 180, 'opp'),
        'D_A': (2.5098, 10.3026, -90, 'opp'),
        'D_B': (0.0606, 9.85, 180, 'opp'),      # clear of HO2's escape via (ho2_vias)
        'D_C': (-1.667, 9.7852, 90, 'opp'),
        # driver supply: HF cap and clamp at VCC/COM, bulk cap and the
        # 330 ohm out in the corner pocket beside FET C
        'C_VCCHF': (-0.4201, 3.8697, 180, 'same'),
        'D_Z': (3.0459, 3.7196, 90, 'opp'),
        'C_VCC': (-8.7999, 12.8624, -90, 'opp'),
        'R_VCC': (-9.0893, 12.4275, 90, 'same'),
        # MCU decoupling; SWD pads in the corner pocket beside FET A
        'C_VDD17': (2.8195, 3.829, 180, 'same'),
        'C_VDDA': (10.5457, 9.275, -90, 'opp'),
        'C_RST': (8.9298, 11.0946, 180, 'same'),
        'C_VDD1': (8.8252, 10.0306, 180, 'same'),
        'TP_DIO': (4.9388, 10.3304, -90, 'opp'),
        'TP_CLK': (3.6996, 9.7826, -90, 'opp'),
        'R_BA_L': (6.3511, 2.5869, 180, 'same'), 'R_BB_L': (6.3903, 2.7879, 180, 'opp'),
        'R_BC_L': (8.9278, 10.262, 180, 'opp'), 'R_N': (9.1378, 3.2485, 90, 'opp'),
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
    t.update(top_template(fu, pu))      # every channel: MCU on the driver's input-corner side
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
        elif kind == 'G':
            globals()[name] = tuple(v)
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
        # the parts that hang on the FET row follow it (2.2 mm towards +x),
        # except B's bootstrap capacitor, which stays under the driver's VS2 /
        # VB2 pins (the driver does not follow FET B: motor 2's MCU is in the
        # way), and C's, which stands past the next MCU's pin 5-8 escapes
        'C_BA': (3.42, 9.95, 0, 'same'), 'C_BB': (0.75, 9.95, 180, 'same'), 'C_BC': (-7.3, 10.45, 0, 'opp'),
        'D_A': (3.3012, 10.1808, 0, 'opp'), 'D_B': (1.0571, 9.85, 0, 'opp'),
        'D_C': (-2.0175, 10.2559, 0, 'opp'),
        'C_VCC': (-14.8352, 8.7425, 180, 'opp'), 'R_VCC': (-14.3355, 9.1223, 0, 'same'),
        # the corner pocket beside FET A holds BAT+'s vias
        'TP_DIO': (5.5319, 10.1372, -90, 'same'), 'TP_CLK': (6.7833, 10.1301, -90, 'same'),
        'C_RST': (10.535, 8.7202, -90, 'same'), 'C_VDD1': (8.8285, 10.0336, 180, 'same'),
    },
}


# ---------------------------------------------------------------- power pads
POWER = {
    'P_BAT+': (-8.2, 13.9, 0, 'T'),
    'P_BAT-': (-4.6, 13.9, 0, 'T'),
    'J_FC':   (0.0, 0.0, 90, 'T'),
    # 3.3 V buck for the four MCUs: bottom centre, under the FC connector
    # (regulator, inductor and bootstrap capacitor: BUCK below)
    'C1':     (-3.2071, 0.8814, 90, 'T'),
    'C2':     (-3.2188, -1.4208, 180, 'T'),
    'C4':     (3.4624, -0.8521, -90, 'T'),
    'R1':     (-0.3103, -1.7312, -90, 'B'),
    'R2':     (1.2625, 2.2648, 0, 'B'),
    # small parts on the free strips under the side motor pads
    'C5':     (-15.6, -8.2, 90, 'B'),
    'R4':     (-15.604, -2.3271, 0, 'B'),
    'R5':     (-15.5801, 8.4859, 180, 'B'),
    'C6':     (-15.0246, 9.128, -90, 'T'),
    'LED_PWR': (15.5, -8.6, 90, 'B'),
    'R3':     (14.4, -8.6, 90, 'B'),
    'TP_3V3': (-15.9946, 2.708, -90, 'B'),
    'TP_GND': (-16.0002, 7.3638, -90, 'B'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
}


# The buck's regulator, inductor and bootstrap capacitor are one rigid group
# on the bottom: the inductor's SW pad right against the regulator's SW pin
# (pin 2), the bootstrap capacitor beside pin 6 (CB), and the SW and CB
# connections laid down as fixed copper (buck_copper) - they are not left to
# the router.  Offsets at group rotation 0 in board axes: pins 1-3 face +y,
# the inductor below them (hand 'R': to the right of the regulator, 'L': to
# the left), its SW pad under pin 2.  The capacitor's SW end runs in under
# the regulator, between its pin rows, to pin 2; pin 1 (GND) takes its plane
# via under the inductor, between its pads.  All of this copper stays inside
# the three parts' courtyards.  BUCK = (x, y, rotation, hand).
BUCK = (-1.5945, 0.9019, 90, 'R')
BUCK_PARTS = {'U_BUCK': (0.0, 0.0, 180), 'L1': (1.35, 3.5, 180), 'C3': (2.13, -0.4, 270)}
BUCK_COPPER = [('BUCK_SW', 0.4, [(0.0, 1.15), (0.0, 2.6)]),
               ('BUCK_SW', 0.4, [(2.13, 0.08), (0.0, 0.08), (0.0, 1.15)]),
               ('BUCK_CB', 0.25, [(0.95, -1.15), (2.13, -0.88)]),
               ('GND', 0.25, [(0.95, 1.15), (1.35, 2.6)])]
BUCK_VIAS = [('GND', 1.35, 2.6)]
# hand 'L': the inductor's body is on the other side, pin 1's via goes
# just beside its SW pad instead
BUCK_GND_L = (1.1, 2.6)


def _buck_xf(g, dx, dy):
    x0, y0, rot, hand = g
    for _ in range((int(round(rot)) // 90) % 4):
        dx, dy = dy, -dx
    return x0 + dx, y0 + dy


def buck_place(g=None):
    g = g or BUCK
    out = {}
    for ref, (dx, dy, r) in BUCK_PARTS.items():
        if g[3] == 'L' and ref == 'L1':
            dx, r = -dx, r - 180
        x, y = _buck_xf(g, dx, dy)
        out[ref] = (round(x, 4), round(y, 4), (r + int(round(g[2]))) % 360, 'B')
    return out


def buck_copper(b, g=None):
    """The buck's SW, CB and pin-1 GND connections as locked tracks on the
    bottom, and pin 1's plane via."""
    g = g or BUCK
    k = 0
    left = g[3] == 'L'
    for net, x, y in BUCK_VIAS:
        vx, vy = _buck_xf(g, *(BUCK_GND_L if left else (x, y)))
        v = pcb.via(b, vx, vy, net, d=VIA_INPAD[0], drill=VIA_INPAD[1])
        v.SetLocked(True)
    for net, w, pts in BUCK_COPPER:
        if left and net == 'GND':
            pts = [pts[0], BUCK_GND_L]
        pts = [_buck_xf(g, x, y) for x, y in pts]
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(MM(pcb.CX + xa), MM(pcb.CY + ya)))
            t.SetEnd(pcbnew.VECTOR2I(MM(pcb.CX + xb), MM(pcb.CY + yb)))
            t.SetWidth(MM(w)); t.SetLayer(pcbnew.B_Cu); t.SetNet(b.FindNet(net)); t.SetLocked(True)
            b.Add(t); k += 1
    return k


if os.environ.get('ESC_OPT'):
    load_opt(os.environ['ESC_OPT'])


def placement(comps):
    place = dict(POWER)
    place.update(buck_place())
    for n in CHANNELS:
        r = roles(comps, n)
        t = channel_template(n)
        for role, ref in r.items():
            place[ref] = xf(n, *t[role])
    return place


FIXED_ROLES = ('QA', 'QB', 'QC', 'PA', 'PB', 'PC', 'C_BULK1', 'C_BULK2', 'C_HF', 'GD', 'MCU', 'C_BC')


def fixed(comps):
    f = {'P_BAT+', 'P_BAT-', 'J_FC', 'H1', 'H2', 'H3', 'H4'} | set(BUCK_PARTS)   # the buck group is rigid
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
DRU_EXTRA = '''# JLCPCB via-in-pad (POFV): ordered "Epoxy Filled & Capped", every via is
# filled; holes drilled afterwards (here: the unplated mounting holes) keep
# 0.45 mm from them.  Via to via: the board's normal hole-to-hole rule.
(rule "POFV to drilled holes"
  (condition "A.Type == 'Via' && B.Type == 'Pad'")
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
    print('bootstrap VS vias:', boot_vias(b, comps), ' buck copper:', buck_copper(b))
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
    k, bad = gate_vias(b, comps)
    print('gate vias in pads: %d, none for %s' % (k, bad))
    k, bad = ho2_vias(b, comps)
    print('HO2 escape vias: %d, none for %s' % (k, bad))
    pins = escape_pins(b, comps)
    k, bad = fanout.dogbones(b, pins, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    print('QFN escape vias: %d of %d, none for %s' % (k, len(pins), bad))
    # plane vias stay out of the channels' surface routing lanes
    from shapely.geometry import Point
    lanes = channel_lanes()
    lane_ok = lambda x, y, net: not any(l.intersects(Point(x, y).buffer(VIA_INPAD[0] / 2)) for l in lanes)
    n, failed = fanout.fanout(b, {'GND', 'VBAT'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2),
                              skip=fet_refs(comps), via_ok=lane_ok, **FANOUT)
    print('fanout: %d plane vias, %d pads without one: %s' % (n, len(failed), failed))
    if 'inpad' in FANOUT and os.environ.get('ESCAPE_VIAS', '1') == '1':
        k = fanout.escape_vias(b, {'GND', 'VBAT'}, FANOUT['inpad'], far=ESCAPE_FAR, refs=('J_FC',),
                               bounds=(pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2))
        print('escape vias in pads:', k)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


BOOT_VIA = (0.6, 10.9)      # from the FET's centre: in the switch-node pour's inner tip


def boot_vias(b, comps):
    """Every bootstrap capacitor's VS pad is tied to its switch node by
    fixed copper: a stub to a filled via in the switch-node pour's inner tip
    (C's capacitor is on top, just inside FET C's bulk capacitor; A's and
    B's stand on the FET's side, just behind it).  The driver's VS pins then
    only have to reach their capacitor.  Locked."""
    k = 0
    for n in CHANNELS:
        t = channel_template(n)
        for ph in 'ABC':
            cap = b.FindFootprintByReference(roles(comps, n)['C_B' + ph])
            pad = next(p for p in cap.Pads() if p.GetNetname() == 'M%d_%s' % (n, ph))
            # straight behind the VS pad where that is over the pour's tip
            # (A and B), else at BOOT_VIA (C, on top; motor 1's B)
            x0 = t['Q' + ph][0]
            u = {'A': t['C_BA'][0] + 0.48, 'B': t['C_BB'][0] - 0.48, 'C': None}[ph]
            if u is None or not (x0 - 0.12 <= u <= x0 + 0.96):
                u = x0 + BOOT_VIA[0]
            u = min(u, x0 + 0.8)          # clear of the low-side gate pad (x0 + 1.2)
            x, y = xf_point(n, u, BOOT_VIA[1])
            v = pcb.via(b, x, y, pad.GetNetname(), d=VIA_INPAD[0], drill=VIA_INPAD[1])
            v.SetLocked(True)
            tr = pcbnew.PCB_TRACK(b)
            tr.SetStart(pad.GetPosition()); tr.SetEnd(v.GetPosition()); tr.SetWidth(MM(0.25))
            tr.SetLayer(pcbnew.B_Cu if cap.IsFlipped() else pcbnew.F_Cu); tr.SetNet(pad.GetNet()); tr.SetLocked(True)
            b.Add(tr)
            k += 1
    return k


HO2_VIA_YR = 10.55    # HO2's escape: through the gap between B's bootstrap pads


def ho2_vias(b, comps):
    """The driver's HO2 (pin 16) sits between VS2 and VB2, which run straight
    down to B's bootstrap capacitor, and FET B's high-side gate is on the far
    side of VS2's copper: a stub down through the gap between the capacitor's
    pads to a via just past it, locked.  Returns (placed, failed)."""
    import fanout
    from shapely.geometry import Point, LineString
    layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    obs = fanout.Obstacles(b, layers)
    d, dr = VIA_SIG
    k, bad = 0, []
    for n in CHANNELS:
        r = roles(comps, n)
        gd = b.FindFootprintByReference(r['GD'])
        pad = next(p for p in gd.Pads() if p.GetNumber() == '16')
        t = channel_template(n)
        x, y = xf_point(n, t['GD'][0] + 0.25, HO2_VIA_YR)
        q = pad.GetPosition(); px, py = q.x / 1e6, q.y / 1e6
        vx, vy = pcb.CX + x, pcb.CY + y
        net = pad.GetNetname()
        if not (obs.clear(Point(vx, vy).buffer(d / 2), net, layers, 0.1) and obs.hole_room(vx, vy, dr / 2, 0.45)
                and obs.clear(LineString([(px, py), (vx, vy)]).buffer(0.075), net, [pcbnew.B_Cu], 0.1)):
            bad.append(r['GD'])
            continue
        v = pcb.via(b, x, y, net, d=d, drill=dr); v.SetLocked(True)
        tr = pcbnew.PCB_TRACK(b); tr.SetStart(q); tr.SetEnd(v.GetPosition()); tr.SetWidth(MM(0.15))
        tr.SetLayer(pcbnew.B_Cu if gd.IsFlipped() else pcbnew.F_Cu); tr.SetNet(pad.GetNet()); tr.SetLocked(True)
        b.Add(tr)
        k += 1
    return k, bad


def channel_lanes():
    """The surface routing channels (TOP_CHANNELS) of every channel as
    board-mm polygons (board origin at pcb.CX, pcb.CY)."""
    from shapely.geometry import Polygon
    out = []
    for n in CHANNELS:
        for u0, y0, u1, y1 in TOP_CHANNELS:
            out.append(Polygon([(pcb.CX + a, pcb.CY + c) for a, c in
                                (xf_point(n, u, yr) for u, yr in ((u0, y0), (u1, y0), (u1, y1), (u0, y1)))]))
    return out


GATE_VIA_YR = (11.08, 11.14, 11.0, 10.9, 10.8)   # gate via, tried in turn (the pad spans 10.98-11.38)


def gate_vias(b, comps):
    """A filled via in every FET gate pad (pad 1 high side, pad 8 low side),
    at its inner end: the gate trace can change layer right at the FET.  The
    bulk capacitor on top reaches to yr 11.43, so the via sits at the pad's
    driver end, or just past it where a battery pad leaves no room.
    Locked.  Returns (placed, failed pads)."""
    import fanout
    from shapely.geometry import Point
    layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    obs = fanout.Obstacles(b, layers)
    d, dr = VIA_SIG
    k, bad = 0, []
    for n in CHANNELS:
        r = roles(comps, n)
        t = channel_template(n)
        for ph in 'ABC':
            fp = b.FindFootprintByReference(r['Q' + ph])
            x0 = t['Q' + ph][0]
            for num, du in (('1', -1.5), ('8', 1.5)):
                pad = next(p for p in fp.Pads() if p.GetNumber() == num)
                net = pad.GetNetname()
                spot = None
                for yr in GATE_VIA_YR:
                    x, y = xf_point(n, x0 + du, yr)
                    vx, vy = pcb.CX + x, pcb.CY + y
                    g = Point(vx, vy).buffer(d / 2)
                    if obs.clear(g, net, layers, 0.1) and obs.hole_room(vx, vy, dr / 2, 0.45):
                        spot = (x, y, g, vx, vy)
                        break
                if not spot:
                    bad.append((fp.GetReference(), num))
                    continue
                x, y, g, vx, vy = spot
                v = pcb.via(b, x, y, net, d=d, drill=dr)
                v.SetLocked(True)
                obs.add(g, net, layers); obs.holes.append((vx, vy, dr / 2))
                k += 1
    return k, bad


# MCU pins that always get an escape via: SIG (8), CMP_A/B/C (11/10/6),
# NEUTRAL (7), SWDIO/SWCLK (23/24)
MCU_ESCAPES = ('6', '7', '8', '10', '11', '23', '24')
# driver pins that always get one: LO1 (11) and LO2 (10) leave on the side
# facing FET C and would have to cross the HO/VB/VS escapes to reach FETs
# A and B; LO1 first, so it takes the spot just outside the pin row
GD_ESCAPES = ('11', '10')


def escape_pins(b, comps):
    """QFN pins (MCUs and drivers) that get a dog-bone escape via: the MCU
    pins above, and every pin whose net's nearest pad on another part is on
    the other side of the board."""
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
    for n in CHANNELS:
        out += [(roles(comps, n)['GD'], num) for num in GD_ESCAPES]
    for ref in sorted(qfn):
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            if (ref, p.GetNumber()) in out:
                continue
            net = p.GetNetname()
            if not net or net in ('GND', 'VBAT') or p.GetNumber() in ('25', '33'):
                continue
            if ref.startswith('U_ESC') and p.GetNumber() in MCU_ESCAPES:
                out.append((ref, p.GetNumber()))
                continue
            q = p.GetPosition(); x, y = q.x / 1e6, q.y / 1e6
            others = [(math.hypot(ox - x, oy - y), fl) for r_, fl, ox, oy in pads[net] if r_ != ref]
            if others and min(others)[1] != fp.IsFlipped():
                out.append((ref, p.GetNumber()))
    return out


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
            # on the bottom a size smaller if need be, so both of motor 1's
            # sit the same way round under their pads
            pl.label(r[key], s_, size=1.2, dist=0.7, smallest=1.1 if pl is top else 1.0, face='mono')
    bot.label('TP_3V3', '3V3', size=1.2, face='mono')
    bot.label('TP_GND', 'GND', size=1.2, face='mono')
    top.label('J_FC', '1', pad='1', dist=0.8, size=1.2, face='mono')
    # The top carries no dense parts (all four channels are built on the
    # bottom), so it takes the horizontal lockup, as large as fits, with
    # what the board is under it; the bare mark only if no lockup fits.
    placed = None
    for width in (14.0, 13.0, 12.0, 11.0, 10.0):
        g, clear = brand.lockup_mm(width)
        at = top.geom(g, top.grid_spots((-2.0, -4.0), radius=12.0, step=0.25), clear=clear, vias='fewest',
                      quiet=True)
        if at:
            placed = (g, clear, at)
            break
    runs = [('sans', 'Cheap drone ESC'), ('mono', 'v1')]
    if placed:
        g, clear, (x, y) = placed
        near = (x, y + (g.bounds[3] - g.bounds[1]) / 2 + clear + 0.9)
    else:
        near = None
        for width in (4.0, 3.5, 3.0):
            g, clear = brand.mark_mm(width)
            near = top.geom(g, top.grid_spots((0.0, 0.0), radius=17.0, step=0.25), clear=clear, vias='fewest',
                            quiet=True)
            if near:
                break
        near = near or (0.0, 0.0)
    # what the board is: near the mark if it fits, else anywhere on top,
    # upright then on its side, a little smaller, and last on the bottom
    done = False
    for pl, caps in ((top, (1.2, 1.1, 1.0)), (bot, (1.2, 1.1))):
        pts = pl.grid_spots(near if pl is top else (0.0, 0.0), radius=17.0, step=0.25)
        for cap in caps:
            for rot in (0, 90):
                # vias here are filled and capped under the mask: silk may
                # cross them, so take the fitting spot that crosses fewest
                if pl.text(runs, [(sx, sy, rot, None) for sx, sy in pts], size=cap, vias='fewest'):
                    done = True
                    break
            if done:
                break
        if done:
            break
    # which way is forward: the ESC must sit in the stack the same way round
    # as the FC, or every motor number is wrong.  Kept well clear of the
    # pad labels so the word reads on its own.
    for pl in (top, bot):
        spots = pl.grid_spots((0.0, -6.0), radius=11.0, step=0.25)
        if not any(pl.geom(brand.arrow_mm(2.6, 'Front', cap=1.2, mirror=pl.side == 'B'), spots, vias='fewest',
                           margin=m, quiet=True) for m in (0.6, 0.35)):
            pl.geom(brand.arrow_mm(2.6), spots, vias='fewest', margin=0.4)
