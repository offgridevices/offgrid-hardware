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
import math
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
TEMPLATE = {
    # half-bridges: switch node (exposed pad 10) facing the edge,
    # gates towards the driver
    'QA': (FET_U['A'], Y0, -90, 'same'),
    'QB': (FET_U['B'], Y0, -90, 'same'),
    'QC': (FET_U['C'], Y0, -90, 'same'),
    'PA': (FET_U['A'], PAD_YR, 0, 'T'),
    'PB': (FET_U['B'], PAD_YR, 0, 'T'),
    'PC': (FET_U['C'], PAD_YR, 0, 'T'),
    # bulk decoupling right under each half-bridge, between its via columns
    'C_BULK1': (FET_U['A'], Y0, 0, 'opp'),
    'C_HF':    (FET_U['B'], Y0, 0, 'opp'),
    'C_BULK2': (FET_U['C'], Y0, 0, 'opp'),
    # gate driver: VS/HO/VB side facing the FETs, HIN side facing the MCU
    'GD': (0.0, 6.9, -90, 'same'),
    # bootstrap diodes and capacitors under the driver
    'D_A': (2.3, 7.2, 90, 'opp'), 'D_B': (0.0, 7.2, 90, 'opp'), 'D_C': (-2.3, 7.2, 90, 'opp'),
    'C_BA': (2.1, 9.5, 90, 'opp'), 'C_BB': (0.0, 9.5, 90, 'opp'), 'C_BC': (-2.1, 9.5, 90, 'opp'),
    # driver supply: 10 ohm from the pack, 10 uF + 100 nF at VCC/COM
    'C_VCCHF': (-1.0, 4.0, 0, 'same'),
    'C_VCC':   (-3.4, 5.5, 90, 'same'),
    'R_VCC':   (-3.4, 8.3, 90, 'same'),
    # MCU: its PA8-10 (HA/HB/HC) line up with the driver's HIN1-3
    'MCU': (6.5, 6.9, 90, 'same'),
    'C_VDD17': (3.9, 3.35, 0, 'same'),
    'C_VDD1':  (10.2, 9.4, 90, 'same'),
    'C_VDDA':  (10.2, 7.2, 90, 'same'),
    'C_RST':   (10.2, 5.0, 90, 'same'),
    # back-EMF dividers and virtual neutral, left of the driver
    'R_BA_H': (-5.9, 4.6, 90, 'same'), 'R_BA_L': (-5.9, 6.8, 90, 'same'),
    'R_BB_H': (-7.1, 4.6, 90, 'same'), 'R_BB_L': (-7.1, 6.8, 90, 'same'),
    'R_BC_H': (-8.3, 4.6, 90, 'same'), 'R_BC_L': (-8.3, 6.8, 90, 'same'),
    'R_NA': (-5.9, 9.0, 90, 'same'), 'R_NB': (-7.1, 9.0, 90, 'same'),
    'R_NC': (-8.3, 9.0, 90, 'same'), 'R_N': (-9.5, 6.8, 90, 'same'),
    # SWD pads for flashing the AM32 bootloader
    'TP_DIO': (7.6, 3.1, 0, 'same'), 'TP_CLK': (9.0, 3.1, 0, 'same'),
}

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


# The two bottom-side channels are mirror images of the top-side ones, so
# without this every corner would stack a top-side MCU right over a
# bottom-side MCU (and a BEMF network over a BEMF network): two 0.5 mm-pitch
# QFNs back to back leave neither room for a via, and both routers stalled
# there.  On the bottom channels the MCU end and the BEMF end trade places,
# so each corner pairs one MCU with one resistor network.
MCU_END = ('MCU', 'C_VDD17', 'C_VDD1', 'C_VDDA', 'C_RST', 'TP_DIO', 'TP_CLK')
BEMF_END = ('R_BA_H', 'R_BA_L', 'R_BB_H', 'R_BB_L', 'R_BC_H', 'R_BC_L', 'R_NA', 'R_NB', 'R_NC', 'R_N',
            'C_VCC', 'R_VCC')


def channel_template(n):
    t = dict(TEMPLATE)
    if CHANNELS[n][1] == 'B':
        for k in MCU_END + BEMF_END:
            u, yr, rot, side = t[k]
            # the MCU turns round so its PA8-10 side still faces the driver
            t[k] = (-u, yr, (rot + 180) % 360 if k == 'MCU' else rot, side)
    if n == 1:
        for ph in 'ABC':
            u = M1_FET_U[ph]
            t['Q' + ph] = (u, Y0, -90, 'same')
            t['P' + ph] = (M1_PAD_U[ph], PAD_YR, 0, 'T')
        t['C_BULK1'] = (M1_FET_U['B'], Y0, 0, 'opp')
        t['C_BULK2'] = (M1_FET_U['C'], Y0, 0, 'opp')
        # FET A sits half under BAT-: its HF capacitor fits beside the pad
        t['C_HF'] = (2.0, Y0, 90, 'opp')
    return t


# ---------------------------------------------------------------- power pads
POWER = {
    'P_BAT+': (-8.2, 13.9, 0, 'T'),
    'P_BAT-': (-4.6, 13.9, 0, 'T'),
    'J_FC':   (0.0, 0.0, 90, 'T'),
    # 3.3 V buck for the four MCUs: bottom centre, in the band between the
    # motor 1 and motor 4 channels
    'U_BUCK': (-2.3, -1.3, 0, 'B'),
    'L1':     (2.9, -1.4, 0, 'B'),
    'C1':     (-2.6, 1.9, 0, 'B'),
    'C2':     (-4.6, -1.3, 90, 'B'),
    'C3':     (-5.0, 1.8, 90, 'B'),
    'C4':     (3.6, 1.9, 0, 'B'),
    'R1':     (0.5, 1.4, 0, 'B'),
    'R2':     (0.5, 2.5, 0, 'B'),
    # small parts in the free strips under the side motor pads
    'C5':     (-15.1, 6.4, 90, 'B'),
    'R4':     (-15.1, -1.0, 90, 'B'),
    'R5':     (-15.1, 1.2, 90, 'B'),
    'C6':     (-15.1, 3.4, 90, 'B'),
    'LED_PWR': (15.1, -6.0, 90, 'B'),
    'R3':     (15.1, -3.4, 90, 'B'),
    'TP_3V3': (15.1, 2.0, 0, 'B'),
    'TP_GND': (15.1, 3.6, 0, 'B'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
}


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
    z = pcb.zone(b, net, _layer(n, side_rel), poly, clearance=0.2, min_width=0.2, priority=prio,
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
            if CHANNELS[n][1] == 'B':
                # bottom channel: the pad is on top, reached by vias in the pad
                for du in (-0.5, 0.5):
                    for yr in (14.75, 15.4, 16.05):
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
        for dx in (-0.7, 0.0, 0.7):
            for dy in (-1.8, -1.05, -0.3, 0.45, 1.2, 1.95):
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
    w.update({n: 0.25 for n in drv})
    w.update({'+3V3': 0.25, 'BUCK_SW': 0.4, 'BUCK_CB': 0.25, 'VBAT': 0.3})
    return w

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
    pcb.netclass(b, 'GATE', gate, width=0.2, clearance=0.15)
    pcb.netclass(b, 'DRIVE', drv, width=0.25, clearance=0.15)
    pcb.netclass(b, 'PWR', ['+3V3', 'BUCK_CB'], width=0.25, clearance=0.15)
    pcb.netclass(b, 'SW', ['BUCK_SW'], width=0.4, clearance=0.15)
    pcb.netclass(b, 'BAT', ['VBAT'], width=0.3, clearance=0.15)
    import fanout
    e2 = H - 0.4
    n, failed = fanout.fanout(b, {'GND', 'VBAT'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2),
                              skip=fet_refs(comps))
    print('fanout: %d plane vias, %d pads without one: %s' % (n, len(failed), failed))
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
    for n in CHANNELS:
        r = roles(comps, n)
        for ph in 'ABC':
            top.label_along(r['P' + ph], str(n), sizes=(1.5, 1.3, 1.2), face='mono')
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
