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
    drain tab carries the battery (VBAT planes on In3 and In6) through filled vias;
  * the LOW-side FET on the bottom, 2.4 mm further out, source pins
    inwards.  Its drain tab lies under the top switch-node pour and joins
    it through filled vias in the tab;
  * the bridge capacitor on the bottom, under the high-side drain: its
    VBAT pad takes a via straight up into that drain tab, its other pad
    sits at the low-side source pins.  The switching loop closes through
    the board's thickness.
The low-side sources of a channel return to ground through its current
shunt: they, the bridge capacitors' return pads and the shunt meet on the
bottom and on a pour on In5 under the channel ("M<n>_SRC").  The shunt
stands in the channel's corner slot (+u end, bottom), between the FET row
and the mounting hole; its amplifier sits inside it.

Behind the power stage, on the bottom: the gate driver and the MCU side by
side (each channel's pair turned like a pinwheel, so the four pairs clear
each other at the centre), with their small parts round them.  The top
carries the high-side FETs, the motor and battery pads, the stack
connector in the middle and the small parts that fit round it.

Stackup (8 layers): F signals + power | In1 GND | In2 signals | In3 VBAT
(signals under each channel's chips) | In4 GND | In5 signals + channel
return pours | In6 VBAT | B signals + power.
"""
import math, os
import pcbnew
import shapely
import pcb, circuit, parts
from pcb import MM

H = pcb.HALF
PITCH = 5.0          # phase spacing: a 1.7 mm gap between FETs for the channel's vias
# phase C on the -u side, A on +u: the order of the DRV8320H's gate pins
# as it lies (bottom, turned half round), C and B along its FET-side row,
# A down its +u side
PH_U = {'C': -PITCH, 'B': 0.0, 'A': PITCH}
SHUNT_PHASE = 'C'    # the phase beside the shunt (the channel's -u end)
Y_HS = 12.3          # high-side FET centre (top)
Y_LS = 14.7          # low-side FET centre (bottom), its drain under the motor pad
Y_CAP = 11.35        # bridge capacitor (bottom, along the row): between the driver and the low side
Y_PAD = 16.4         # motor pads (top)
Y_CHIP = 6.6         # driver and MCU row (bottom)

# channel: rotation of the rear-edge template (degrees, KiCad's sense)
CHANNELS = {1: 0, 2: 90, 3: -90, 4: 180}


def xf_point(n, u, yr):
    a = math.radians(CHANNELS[n])
    return (u * math.cos(a) + yr * math.sin(a), -u * math.sin(a) + yr * math.cos(a))


def xf(n, u, yr, rot, side):
    x, y = xf_point(n, u, yr)
    return (round(x, 4), round(y, 4), (rot + CHANNELS[n]) % 360, side)


# The back-EMF resistors (top, over the driver) tap each phase where its
# switch-node sense line reaches the driver: pin 1 on or beside the escape
# via in the driver's SHx pad (the same node as the FETs' switch node, the
# sense line's few mm of track between; route_local's sense line takes
# the pad in), pin 2 the divided tap towards the MCU.
# In the gaps between the low sides, beside the drains they tapped, their
# three lines to the MCU had to cross the FET row with the gate and sense
# lines and the thermistor's, and the row has room for those alone: no
# routing found them all a way.  From over the driver they stay in the
# chips' strip, where In3's window (SIG_WINDOW) takes them under the MCU.
# Spots found by tools/mcu_cluster_search.py, with the MCU's parts.
RBH = {'C': (-1.3, 8.67, 180, 'T'), 'B': (1.05, 8.92, 90, 'T'), 'A': (2.32, 8.8, 270, 'T')}


def template():
    """role -> (u, yr, rotation, side) for the rear-edge channel."""
    t = {}
    for ph, u in PH_U.items():
        t['Q%sH' % ph] = (u, Y_HS, 0, 'T')
        t['Q%sL' % ph] = (u, Y_LS, 0, 'B')
        t['P' + ph] = (u, Y_PAD, 0, 'T')
        # bridge capacitor along the row, under the high-side drain: its
        # VBAT pad (1) at -u reaches into the battery strip along the
        # return's inner edge (its vias, VBAT_VIAS), its return pad (2) at
        # +u sits in the return strip above the low-side source pins.
        # (Upright, 3.5 mm of courtyard, it does not fit the 2.9 mm between
        # the driver and the low side.)  The phase beside the shunt
        # (SHUNT_PHASE) has it turned round: there its return pad faces the
        # shunt, so the return reaches the shunt's sense pad on the bottom
        # past it (the battery pad there walled the shunt's pocket off).
        t['CBR_' + ph] = (u, Y_CAP, 180 if ph == SHUNT_PHASE else 0, 'B')
        # back-EMF: the phase-side 20k resistor over the driver, on its
        # SHx pin's via (RBH)
        t['RBH_' + ph] = RBH[ph]
    # The gate driver (DRV8320H, 5 x 5) on the bottom behind the FET row,
    # turned half round: its FET-side row carries phases C and B, its +u
    # side phase A, its -u side the setting pins, its centre-side row the
    # PWM inputs.  The MCU (AT32F421, 4 x 4) beside it on the -u side, its
    # PWM pins facing the driver.  The pair spans u -8.06 .. 3.4: the next
    # channel's pair starts at yr 3.7, so the four pairs pinwheel round the
    # centre (each chip clear of the next channel's escape vias).
    t['GD'] = (0.3, Y_CHIP, 180, 'B')
    t['MCU'] = (-5.63, Y_CHIP, 0, 'B')
    # The current shunt in the channel's -u end corridor (no line crosses
    # the FET row there), along the row on the bottom: its sense-node pad
    # (1) in the return pour, its ground pad (2) further out, its Kelvin
    # pads towards the FETs.  The amplifier over it on top: its sense pins
    # over the sense-node end (pin 4 straight over its Kelvin pad), its
    # ground pins over the ground pad's vias (SHUNT_GND_VIAS), its
    # capacitor beside it at the corridor's outer edge.
    t['R_SH'] = (-8.5, 11.8, 270, 'B')
    t['U_CS'] = (-8.1, 11.5, 0, 'T')
    t['C_CS'] = (-9.7, 10.2, 90, 'T')
    t['R_IF'] = (-6.9, 8.1, 180, 'T')
    t['C_IF'] = (-8.15, 8.35, 90, 'T')
    t['R_CUR'] = (-7.4, 15.0, 90, 'T')
    # the FETs' thermistor on top in the strip between the MCU and phase
    # C's high side, by its drain copper (the battery side, where the high
    # side's heat spreads) and in the chips' strip with the MCU's analog
    # inputs: at the edge between the low sides its line to the MCU had to
    # cross the FET row (see RBH)
    t['RT'] = (-4.4, 9.45, 0, 'T')
    # The chips' small parts on top over them, inside the rings of their
    # pins' escape vias, each beside the pins it serves (a pad over its
    # own net's via takes it in the pad).  Found by a search for the
    # shortest connections that clears every pad, via and courtyard of all
    # four turned channels.  Driver: charge-pump flying and VCP capacitors
    # and VM decoupling at its +u side, DVDD and the IDRIVE setting at -u.
    t['C_CP'] = (2.5, 4.45, 180, 'T')
    t['C_VCP'] = (1.85, 5.95, 0, 'T')
    # (the VM and the charge-pump capacitors turned so their battery pads
    # are off the driver's exposed pad, where no battery via fits: the
    # charge pump's over the VM pin, a via in it, the VM capacitor's
    # joined to that; the VM capacitor's ground pad over the exposed pad
    # takes a via there.  The charge pump's VCP pad, over the exposed pad,
    # has no via either: its line leaves on the top past the battery pad's
    # north edge, between it and the CPH pin's via, to the VCP pin's via,
    # so the capacitor sits far enough south and east for that line and
    # for the exposed pad's middle via.)
    t['C_VM'] = (1.95, 7.27, 180, 'T')
    t['C_DVDD'] = (-1.7, 4.7, 0, 'T')
    t['R_ID'] = (-1.7, 7.35, 0, 'T')
    # MCU: supply and reset capacitors, the thermistor's bias, the
    # back-EMF dividers' low legs and the neutral star, and the SWD test
    # points.  The analog pins (thermistor, comparators, current) face the
    # middle and take their escape vias alternately at the inner and
    # outer ends of their pads (across, escape_pins); these parts keep
    # off every via spot (0.2 mm hole to copper), each capacitor's supply
    # pad by its own pin, and the rest as short as that leaves: a
    # simulated-annealing search over their spots and turns
    # (tools/mcu_cluster_search.py).
    t['C_VDD'] = (-3.7, 6.0, 180, 'T')
    t['C_VDDA'] = (-8.0, 5.25, 90, 'T')
    t['C_RST'] = (-7.4, 6.85, 0, 'T')
    t['R_NTB'] = (-6.85, 5.6, 90, 'T')
    t['RS_A'] = (-6.2, 8.9, 180, 'T')
    t['RS_B'] = (-5.7, 6.25, 180, 'T')
    t['RS_C'] = (-5.1, 7.15, 180, 'T')
    t['RBL_A'] = (-6.15, 9.7, 0, 'T')
    t['RBL_B'] = (-5.4, 5.4, 0, 'T')
    t['RBL_C'] = (-2.7, 9.15, 270, 'T')
    # SWD test points on top, the side that faces the flight controller
    # (the bootloader is flashed once, before the stack goes together),
    # beside the MCU's SWD pins
    t['TP_DIO'] = (-3.1, 7.75, 90, 'T')
    t['TP_CLK'] = (-4.85, 8.25, 270, 'T')
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
        elif ref == 'RT%d' % n: out['RT'] = ref
        elif ref.startswith('Q%d' % n): out['Q' + ref[-2:]] = ref
        elif ref.startswith('P_M%d' % n): out['P' + ref[-1]] = ref
        elif ref == 'TP_E%d_DIO' % n: out['TP_DIO'] = ref
        elif ref == 'TP_E%d_CLK' % n: out['TP_CLK'] = ref
        elif note == 'U_ESC%d VDD' % n: out['C_VDD'] = ref
        elif note == 'U_ESC%d VDDA' % n: out['C_VDDA'] = ref
        elif note == 'U_ESC%d reset filter' % n: out['C_RST'] = ref
        elif note == 'driver VM': out['C_VM'] = ref
        elif note == 'driver charge pump': out['C_VCP'] = ref
        elif note == 'driver flying cap': out['C_CP'] = ref
        elif note == 'driver DVDD': out['C_DVDD'] = ref
        elif note == 'driver IDRIVE': out['R_ID'] = ref
        elif note == 'thermistor bias': out['R_NTB'] = ref
        elif note.startswith('bridge '): out['CBR_' + note[-1]] = ref
        elif note.startswith('BEMF '):
            out[('RBH_' if c.part == 'R20K' else 'RBL_') + note[-1]] = ref
        elif note.startswith('neutral '): out['RS_' + note[-1]] = ref
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
BAT_U, BAT_YR = 9.4, 16.05
GLOBAL = {
    'P_BAT+': (-BAT_U, BAT_YR, 0, 'T'),
    'P_BAT-': (BAT_U, BAT_YR, 0, 'T'),
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, 'T'), 'H2': (pcb.HOLE, -pcb.HOLE, 0, 'T'),
    'H3': (pcb.HOLE, pcb.HOLE, 0, 'T'), 'H4': (-pcb.HOLE, pcb.HOLE, 0, 'T'),
    # The middle, inside the four channels' chips.  Top: the stack lead's
    # pads (signals in the row nearer motor 4's driver, supply and current
    # behind them; 1.27 mm apart, so a 0.47 mm gap that a soldering iron
    # does not bridge, 0.8 mm for 28-30 AWG), a bus capacitor below them.
    # Bottom: two more bus capacitors, the drivers' enable clamp, and the
    # lead's vias.
    'P_L1': (-1.905, -3.15, 0, 'T'), 'P_L2': (-0.635, -3.15, 0, 'T'),
    'P_L3': (0.635, -3.15, 0, 'T'), 'P_L4': (1.905, -3.15, 0, 'T'),
    'P_LV': (-1.27, -1.88, 0, 'T'), 'P_LC': (1.27, -1.88, 0, 'T'),
    # the lead's ground wire on top in motor 1's end corridor past phase
    # A's FETs, 2.5 mm from the battery minus pad's Kelvin tap (circuit.py:
    # it carries the FC's own current; from the middle that was a trace
    # 25 mm long through the channel's busiest corner)
    'P_LG': (8.3, 13.5, 0, 'T'),
}
GLOBAL_BY_NOTE = {
    # top: in a row between the lead's pads and the bus capacitor, the
    # enable feed and current filter; beside the pads, the enable and
    # battery-voltage filters; beside the capacitor, the battery-voltage
    # divider
    'bus bulk 1': (0.0, 2.09, 0, 'T'),
    'driver enable feed': (-2.25, -0.42, 0, 'T'),
    'CUR filter': (2.4, -0.42, 0, 'T'),
    'driver enable filter': (-3.15, -2.4, 90, 'T'),
    'ESC vsense filter': (3.2, -2.4, 90, 'T'),
    'ESC vsense top': (3.15, 1.15, 90, 'T'),
    'ESC vsense bottom': (3.15, 2.8, 90, 'T'),
    # bottom: two more bus capacitors, and beside the lead's vias the
    # enable clamp
    'bus bulk 2': (-1.8, 1.1, 90, 'B'),
    'bus bulk 3': (1.8, 1.1, 90, 'B'),
    'driver enable clamp': (-2.85, -2.4, 90, 'B'),
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
               'GD', 'MCU', 'R_SH', 'U_CS', 'RBH_A', 'RBH_B', 'RBH_C', 'RS_A', 'RS_B', 'RS_C')


# global parts that stay exactly where the table puts them; the others
# are only hints for the packer
# the stack lead's wire pads
LEAD_PADS = ('P_LV', 'P_LG', 'P_LC', 'P_L1', 'P_L2', 'P_L3', 'P_L4')
# those in the middle, each with a via in the pad (lead_vias); the ground
# wire's pad by the battery pad joins the pad's tap on the top
LEAD_MIDDLE = tuple(r for r in LEAD_PADS if r != 'P_LG')
GLOBAL_FIXED = ('P_BAT+', 'P_BAT-', 'H1', 'H2', 'H3', 'H4') + LEAD_PADS


# Packing order: the parts that must sit at a channel chip's pins first,
# then the supplies' chips and inductor, then their other parts, then the
# rest (filters, dividers, test points).  A supply's parts move with their
# chip (pack_anchor).
def pack_priority(c):
    # the channels' parts first: the template places every one of them
    # clear of the others, so they keep their spots.  Then the shared
    # parts in what is left: the bus capacitors, then the rest (filters,
    # dividers, the enable clamp)
    if c.block.startswith('esc') or c.note.startswith('CUR average '):
        return -10
    if c.note.startswith('bus bulk'):
        return -1
    return 3


def pack_anchor(c):
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
# the current and voltage filters and the dividers
EITHER_SIDE = ('CUR filter', 'ESC vsense top', 'ESC vsense bottom', 'ESC vsense filter')


def either_side(c):
    return c.note in EITHER_SIDE


def escape_keep(comps, place):
    """Where the MCUs' and drivers' signal vias come through to the far
    side, so no other part puts a pad there: each signal pin that leaves its
    side of the board has its via in the pad at the pad's outer end
    (VIA_ESCAPE, fanout.dogbones).  (At the MCU's 0.4 mm pitch a pin next
    to one with an outer via takes its via at the inner end, over the chip,
    where only the template's own parts are.)  Each spot is the via plus
    0.1 mm, and
    takes a pad of the via's own net.  The stack lead's pads' vias
    (lead_vias) are kept the same way.  The
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
    # the stack lead's pads take their via in the pad (lead_vias)
    for c in comps:
        if c.ref in LEAD_MIDDLE:
            x, y = place[c.ref][:2]
            spot('B', x, y, VIA_INPAD[0], c.pins['1'])
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
        # the passives may turn 90 degrees to fit
        turn = lambda c: c.ref[:1] in 'RCD' and not c.ref.startswith(('R_SH', 'CBR'))
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
# The MCU's pads (0.4 mm pitch) are 0.2 mm wide: its escape via (the
# smallest JLCPCB makes) overhangs the pad's sides by 0.025 mm, inside the
# pad's mask opening and 0.175 mm from the next pad.
ESCAPE_OVERHANG = 0.03
HOLE_CL = 0.2                  # via hole to other copper (JLCPCB multilayer)
# The routers keep only copper clearances (0.1 mm): they see every via with
# at least this ring, so their copper stays HOLE_CL from its hole.
VIA_RING = HOLE_CL - 0.1
# Freerouting may also drop a signal via onto a same-net pad (route.py):
# under the chips both sides are full of parts, and a pad is often the
# only spot left.  Its 0.1 mm ring keeps the hole 0.2 mm from other copper.
VIA_IN_PAD = VIA_SIG

GAPS = (-7.5, -2.5, 2.5, 7.5)  # via corridors: the gaps between phases and both ends
# The FET band is its channel's, whatever channel's copper is nearest
# (stamp.region): the next channel's MCU sits beside the band's end
# corridor, and would otherwise take its entrance from the gate lines
# that cross the FET row there.
STAMP_CLAIM = [(-9.0, 9.0), (9.0, 9.0), (9.0, 19.0), (-9.0, 19.0)]
import stamp as _stamp          # (route_local and the pipeline both ask stamp.region)
_stamp.CLAIM = STAMP_CLAIM
# per corridor, from its centre: one return via on the centre line.  Every
# signal between the driver and MCU and the FETs, the motor pads and the
# back-EMF resistors (gate drives, switch-node taps, back-EMF: 12 a
# channel) passes the band of vias across the FET row in these
# corridors, on top and on In2 (In5 carries the return there).  A pair of
# vias passed one track between them a layer; one via passes one either side
# (0.45 mm from its centre keeps a 0.2 mm track 0.2 mm from its hole).  The
# return's layers stay tied by these and the leg's vias at the shunt: the
# bottom's pour alone would not do, the low-side gate stubs cut it at every
# corridor, so each phase's piece reaches the shunt through In5.
SRC_VIA = ((0.0, 11.85),)
# gate resistors (0201, upright): u from the phase centre (the corridor's
# centre line), the high side's yr (top), the low side's yr (bottom).  The
# FETs' gate pins are at +0.97: the high side's at yr 13.98 (top), the low
# side's at 13.02 (bottom).  The low side's courtyard ends 0.02 mm short of
# the back-EMF resistor's below it.
GATE_CELL = (2.5, 13.1, 13.75)
# the top over the driver inside the ring of its pins' escape vias
DRIVER_RING = (-4.45, 5.45, -0.95, 9.0)
# The high-side drain's battery vias, from the phase centre: one row along
# the strip's inner edge, two of them in the bridge capacitor's battery pad.
# A row along the channel's return current leaves it a clear run; a column
# across it (rev 1) walled it off.
VBAT_VIAS = ((-1.2, 10.2), (-0.35, 10.15), (0.35, 10.15), (1.2, 10.15))
# beside the shunt the strip starts here (from the phase centre): the
# return passes it to the shunt's pocket, 1.2 mm wide over the bridge
# capacitor's turned-round return pad; three of the drain's vias stay
BRIDGE_VBAT_SHUNT = -0.8
# the return's vias between the bottom and In5 at every phase, from the
# phase centre: beside the half-bridge, just outside the high side's drain
# (pad 9 and leads reach u +-1.145 on the top, where these through vias
# come out: 1.6 leaves the 0.2 mm hole clearance); the one at -u further
# out, clear of the bridge capacitor's battery pad, and between the
# shunt's Kelvin pads where phase C's lands
SRC_PH_VIAS = ((-1.9, 11.8), (1.6, 11.3), (1.6, 12.2))
# beside the shunt, with the bridge capacitor turned round (its battery pad
# at +u), only the -u one, in the return's way to the shunt's pocket (the
# shunt's Kelvin pad takes its escape via below it)
SRC_PH_VIAS_SHUNT = ((-1.9, 11.8),)
# the return's copper on In5 reaches further out, under the low-side source
# pins, to the switch node's vias
SRC_IN_EDGE = Y_LS - 0.4        # under the low side's drain body, short of its switch-node vias
# and further in than the bottom's under the driver, to the vias of its
# return pin at the row's -u end (src_ties take the others); under the MCU
# (u < SRC_IN_SPLIT) it stops where the bottom's does: its keepout there
# barred every via from the strip between the MCU and the FET row, where
# the current filter's and the MCU's bottom-edge parts sit, and the lines
# from the FET row turn in under the MCU
SRC_IN_INNER = 9.2
SRC_IN_MCU = 9.75
SRC_IN_SPLIT = -2.4
# The FETs' copper edges, template yr (the Infineon TSDSON-8 FL land,
# footprints.tsdson8fl_fp): the high side's drain ends at Y_HS + 0.46 and
# its source leads start at Y_HS + 1.0; the low side (bottom, turned over)
# has its source leads from Y_LS - 1.9 to Y_LS - 1.0 and its drain from
# Y_LS - 0.46 out.  Each pour stops 0.2 mm short of the other net's pad.
HS_DRAIN_END = Y_HS + 0.46 + 0.14       # top battery pour's outer edge
TOP_SW_START = Y_HS + 0.46 + 0.34       # top switch-node pour's inner edge
BOT_SW_START = Y_LS - 0.46 - 0.1        # bottom switch-node pour's inner edge
SRC_OUT = Y_LS - 1.0 + 0.25             # the return's outer edge (over the source leads)
# switch-node vias in the low-side drain (its body pad and leads)
SW_VIAS = [(du, yr) for yr in (Y_LS + 0.05, Y_LS + 0.8, Y_LS + 1.55) for du in (-0.8, 0.0, 0.8)
           if (du, yr) != (0.8, Y_LS + 0.05)]
# the shunt's sense-node pad in the channel's -u end corridor (template
# R_SH, rot 270): the return reaches it along the FET band on the bottom
# (its pocket, BOT_SRC) and on In5, which phase C's vias beside the pocket
# tie (SRC_PH_VIAS); the top over the pad carries the current amplifier's
# parts, so no vias in it
SRC_LEG_VIAS = []
# the top switch node, notched round the high side's gate lead (u + 0.975)
TOP_SW = lambda u: [(u - 1.6, TOP_SW_START), (u + 0.6, TOP_SW_START), (u + 0.6, Y_HS + 2.1),
                    (u + 1.6, Y_HS + 2.1), (u + 1.6, 17.65), (u - 1.6, 17.65)]
HS_DRAIN = lambda u: [(u - 1.6, 10.15), (u + 1.6, 10.15), (u + 1.6, HS_DRAIN_END), (u - 1.6, HS_DRAIN_END)]
BOT_SW = lambda u: [(u - 1.6, BOT_SW_START), (u + 1.6, BOT_SW_START), (u + 1.6, 16.85), (u - 1.6, 16.85)]
BOT_SRC = [(-6.95, SRC_OUT), (-6.95, 11.25), (-9.5, 11.25), (-9.5, 9.3), (-6.7, 9.3), (-6.7, 9.75),
           (6.6, 9.75), (6.6, 10.75), (7.9, 10.75), (7.9, SRC_OUT)]


def in_src():
    """The return's outline on In5: the bottom's, its outer edge at
    SRC_IN_EDGE and its inner edge SRC_IN_INNER further in under the
    driver (no parts there), SRC_IN_MCU under the MCU."""
    out = []
    for u, yr in BOT_SRC:
        if yr == SRC_OUT:
            out.append((u, SRC_IN_EDGE))
        elif yr == 9.75 and u < SRC_IN_SPLIT:
            out += [(u, SRC_IN_MCU), (SRC_IN_SPLIT, SRC_IN_MCU), (SRC_IN_SPLIT, SRC_IN_INNER)]
        elif yr == 9.75:
            out.append((u, SRC_IN_INNER))
        else:
            out.append((u, yr))
    return out


def reserved():
    """Board regions (side, bbox) the packer keeps free: every channel's
    FET band (its power copper, corridors and fixed parts, both sides)
    and the panel's tab zones at the corners."""
    out = []
    for n in CHANNELS:
        pts = [xf_point(n, u, yr) for u, yr in ((-11.0, 9.75), (11.0, pcb.HALF))]
        bb = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        out += [('T', bb), ('B', bb)]
    out += [(side, z) for z in pcb.tab_zones() for side in ('T', 'B')]
    return out


def _cu(side):
    return pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu


def _zone(b, n, net, layer, pts, prio=3, name=None, clearance=0.2):
    poly = [xf_point(n, u, yr) for u, yr in pts]
    return pcb.zone(b, net, layer, poly, clearance=clearance, min_width=0.2, priority=prio,
                    thermal=False, name=name)


def _in_keepout(x, y, r):
    return any(math.hypot(x - sx * pcb.HOLE, y - sy * pcb.HOLE) < pcb.HOLE_COPPER_R + r + 0.05
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
            _zone(b, n, 'VBAT', pcbnew.F_Cu, HS_DRAIN(u), name='high-side drain')
            # bottom: switch node over the low-side drain, reaching out to
            # the phase end of the back-EMF resistor that taps it
            _zone(b, n, sw, pcbnew.B_Cu, BOT_SW(u), name='switch node')
            for c in comps:
                if c.block != 'esc%d' % n or not c.note.startswith('BEMF ') or c.pins.get('1') != sw:
                    continue
                x0, y0, x1, y1 = _pad_box(b, c.ref, '1')
                q = [_to_template(n, x, y) for x, y in ((x0, y0), (x1, y1))]
                pu0, pu1 = min(q[0][0], q[1][0]), max(q[0][0], q[1][0])
                py0, py1 = min(q[0][1], q[1][1]), max(q[0][1], q[1][1])
                # copper from the pad to the nearest point well inside the
                # pour (0.25 mm in from its edge): the box spanning both, so
                # it overlaps the pour whichever way the pad lies from it.
                # (A resistor away from the pour, on its sense line by the
                # driver, takes none.)
                cu_ = min(max((pu0 + pu1) / 2, u - 1.35), u + 1.35)
                cy_ = min(max((py0 + py1) / 2, 13.9), 16.6)
                if u - 1.6 <= (pu0 + pu1) / 2 <= u + 1.6 and BOT_SW_START <= (py0 + py1) / 2 <= 16.85:
                    continue
                if abs((pu0 + pu1) / 2 - cu_) > 2.0 or abs((py0 + py1) / 2 - cy_) > 2.0:
                    continue
                w2 = 0.25
                ua, ub = min(pu0, cu_ - w2), max(pu1, cu_ + w2)
                ya, yb = min(py0, cy_ - w2), max(py1, cy_ + w2)
                tab = [(ua, ya), (ub, ya), (ub, yb), (ua, yb)]
                _zone(b, n, sw, pcbnew.B_Cu, tab, prio=4, name='bemf tab')
            # bottom: a battery strip along the return's inner edge, round
            # the bridge capacitor's VBAT pad and the drain's vias.  Beside
            # the shunt it starts short of the phase's -u end, where the
            # return passes to the shunt's pocket (BRIDGE_VBAT_SHUNT)
            lo = u + (BRIDGE_VBAT_SHUNT if ph == SHUNT_PHASE else -1.62)
            _zone(b, n, 'VBAT', pcbnew.B_Cu, [(lo, 9.75), (u + 1.62, 9.75), (u + 1.62, 10.75),
                                              (lo, 10.75)], prio=5, name='bridge VBAT')
            for du, yr in VBAT_VIAS:
                if u + du - VIA_PWR[0] / 2 >= lo:
                    _via(b, n, u + du, yr, 'VBAT', VIA_PWR, count)
            for du, yr in (SRC_PH_VIAS_SHUNT if ph == SHUNT_PHASE else SRC_PH_VIAS):
                _via(b, n, u + du, yr, m('SRC'), VIA_PWR, count)
            for du, yr in SW_VIAS:
                _via(b, n, u + du, yr, sw, VIA_PWR, count)
        # the channel's return: bottom and In5, the FET band plus the leg
        # to the shunt
        _zone(b, n, m('SRC'), pcbnew.B_Cu, BOT_SRC, prio=3, name='return')
        _zone(b, n, m('SRC'), SRC_IN, in_src(), prio=3, name='return')
        for g in GAPS[1:]:            # (the -u end is the shunt's)
            for du, yr in SRC_VIA:
                _via(b, n, g + du, yr, m('SRC'), VIA_PWR, count)
        for u, yr in SRC_LEG_VIAS:
            _via(b, n, u, yr, m('SRC'), VIA_PWR, count)
    return count


# The shunt's ground pad (template R_SH pad 2: u -9.4 .. -7.6, yr 12.4 ..
# 14.1) carries the channel's whole current to the ground planes: a grid
# of power vias in it (0.6 mm apart), all but the one beside the Kelvin
# pad (u -7.65 .. -7.15 up to yr 12.75).  The top over them stays clear.
SHUNT_GND_VIAS = [(u, yr) for yr in (12.75, 13.35, 13.95) for u in (-9.1, -8.5, -7.9) if (u, yr) != (-7.9, 12.75)]


def shunt_vias(b, comps):
    """The ground vias in every shunt's ground pad (SHUNT_GND_VIAS)."""
    count = {}
    for n in CHANNELS:
        for u, yr in SHUNT_GND_VIAS:
            _via(b, n, u, yr, 'GND', VIA_PWR, count)
    return count.get('GND', 0)


# a gate stub's via: in the corridor on the phase's +u side, where the
# FET's gate pin faces, level with the pin
GATE_VIA_DU = 1.95


def gate_stubs(b, comps):
    """Every FET's gate pin 4 reaches a via in the corridor beside it by a
    short fixed track on the FET's own side; the router joins the driver's
    gate pins to these vias.  (The low sides' gate pins lie inside the
    return pour, which no router may cross.)  Locked."""
    k = 0
    for n in CHANNELS:
        r = roles(comps, n)
        for ph, u in PH_U.items():
            for fet, layer in (('Q%sH' % ph, pcbnew.F_Cu), ('Q%sL' % ph, pcbnew.B_Cu)):
                gate = next(p for p in b.FindFootprintByReference(r[fet]).Pads() if p.GetNumber() == '4')
                gx, gy = gate.GetPosition().x / 1e6 - pcb.CX, gate.GetPosition().y / 1e6 - pcb.CY
                gu, gyr = _to_template(n, gx, gy)
                vx, vy = xf_point(n, u + GATE_VIA_DU, gyr)
                tr = pcbnew.PCB_TRACK(b)
                tr.SetStart(gate.GetPosition()); tr.SetEnd(pcb.P(vx, vy)); tr.SetWidth(MM(0.25))
                tr.SetLayer(layer); tr.SetNet(gate.GetNet()); tr.SetLocked(True)
                b.Add(tr)
                v = pcb.via(b, vx, vy, gate.GetNetname(), d=VIA_SIG[0], drill=VIA_SIG[1])
                v.SetLocked(True)
                k += 1
    return k


# The driver's low-side source pins next to the return (the corner of its
# FET-side row) reach its bottom pour straight out, on the bottom: no
# router may cross the pour to them.
SRC_TIE_TO = 10.05                    # template yr: inside the bottom return (BOT_SRC from 9.75)


def src_ties(b, comps):
    """Fixed bottom tracks from the driver's return pins at the corner by
    the return (the FET-side ends of the +u column and of the FET-side
    row) out into the bottom return pour.  Locked."""
    k = 0
    for n in CHANNELS:
        r = roles(comps, n)
        fp = b.FindFootprintByReference(r['GD'])
        for p in fp.Pads():
            if p.GetNetname() != 'M%d_SRC' % n:
                continue
            x, y = p.GetPosition().x / 1e6 - pcb.CX, p.GetPosition().y / 1e6 - pcb.CY
            u, yr = _to_template(n, x, y)
            if u < 1.0:                # (the -u end of the row reaches the return through In5)
                continue
            ex, ey = xf_point(n, u, SRC_TIE_TO)
            tr = pcbnew.PCB_TRACK(b)
            tr.SetStart(p.GetPosition()); tr.SetEnd(pcb.P(ex, ey)); tr.SetWidth(MM(0.25))
            tr.SetLayer(pcbnew.B_Cu); tr.SetNet(p.GetNet()); tr.SetLocked(True)
            b.Add(tr)
            k += 1
    return k


def dsn_keepouts(b):
    """The board handed to Freerouting (route.PRE_EXPORT): the power
    copper's keepouts (routing_keepouts), and In3 a plane again.  On a
    signal layer Freerouting takes a pour for copper no other net's via
    may pass, and a keepout there for one no via may pass either: either
    way the channel's lines lost every via through the FET row.  The maze
    router (route_local, the repairs) has In3's windows (SIG_WINDOW): an
    inner pour keeps its tracks out and lets its vias through."""
    k = routing_keepouts(b)
    b.SetLayerType(SIG_IN, pcbnew.LT_POWER)
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
            areas.append((pcbnew.F_Cu, HS_DRAIN(u)))
            areas.append((pcbnew.B_Cu, BOT_SW(u)))
        areas.append((pcbnew.B_Cu, BOT_SRC))
        areas.append((SRC_IN, in_src()))
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
    cu = pcb.cu_layers(b)
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


# Eight layers: F signals + power | In1 GND | In2 signals | In3 VBAT
# (signals under the chips, SIG_WINDOW) | In4 GND | In5 signals + channel
# returns | In6 VBAT | B signals + power.
# Every amp of the four motors crosses a ground plane and a battery plane
# on its way from the battery pads to the FETs and back; on six layers
# (rev 1: one plane each) that was 2.3 mOhm, the biggest single heat source
# in a full-throttle burst (STRESS.md).  Two planes of each halve it, and
# the signal layers keep the 0.1 mm the gate drive needs through the FET
# row.  (The other way to the same copper, 2 oz inner layers on six, etches
# no finer than 0.15 mm track / 0.15 mm gap (JLCPCB, multilayer), and at
# 0.15 / 0.15 the channel does not route.)
LAYERS = 8
INNER_OZ = 1.0
GND_PLANES = (pcbnew.In1_Cu, pcbnew.In4_Cu)
VBAT_PLANES = (pcbnew.In3_Cu, pcbnew.In6_Cu)
SRC_IN = pcbnew.In5_Cu         # the inner layer that carries the channel returns
# Under each channel's two chips the battery plane on In3 gives way to
# signals.  Every line from the FET row (gates, switch-node sense, the
# back-EMF taps, the thermistor, the current amplifier) and every PWM line
# ends round the MCU and the driver, whose pins take their escape vias in
# their pads; with In2 and In5 alone (In5's return pour starts at
# SRC_IN_INNER / SRC_IN_MCU) the lines laid first walled the comparators'
# and the current filter's pins in, and no routing reached them.  The battery's
# current does not run there: it goes from the battery pads to the FET
# rows round the board's edge, on In6 whole and on In3 outside the
# windows; In3 keeps In4's ground beside it as the signals' reference.
# Template frame (u, yr): the chips' strip, from the next channel's region
# to the return pour's inner edge (in_src); the four turned windows clear each
# other and the middle square.  The maze router (route_local, the
# repairs) routes in them; Freerouting sees In3 as the plane it was
# (dsn_keepouts).
SIG_IN = pcbnew.In3_Cu
SIG_WINDOW = [(-9.4, 3.7), (3.6, 3.7), (3.6, SRC_IN_INNER), (SRC_IN_SPLIT, SRC_IN_INNER),
              (SRC_IN_SPLIT, SRC_IN_MCU), (-9.4, SRC_IN_MCU)]
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, SIG_IN, SRC_IN, pcbnew.B_Cu]
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
# (SRC_VIA), and the channel has no track to spare there: gate drive
# 0.1 mm, sense 0.12 mm.  The DRV8300 drives 0.75 A / 1.5 A peaks, for tens
# of nanoseconds, through its 10 ohm gate resistors (41 nC a switch: a few
# mA on average): 10 mm of 0.1 mm 1 oz track adds 0.05 ohm, 0.5 % of the
# gate loop.  The bootstrap lines keep 0.2 mm: they are short stubs, and
# they carry the capacitor's recharge.
GATE_W = 0.1
SENSE_W = 0.12
BOOT_W = 0.2


# Routed supplies (width, clearance): the battery's current runs in the
# planes and pours, so what is left on tracks is small: the battery's taps
# 0.2 mm (the enable clamp, the voltage divider, the stack lead's supply
# pad to its plane vias).  Each channel's 3.3 V (DVDD, ~22 mA) is 0.15 mm
# (widths).
SUPPLY_RULES = {
    'VBAT': (0.2, 0.13),
    # the lead's ground, its wire pad to the battery pad's tap: the FC's
    # own current, up to 2 A
    'FC_GND': (0.4, 0.1),
}


def widths(comps):
    """Router widths: gate drive GATE_W, the driver's switch-node sense
    SENSE_W, the charge pumps and each channel's 3.3 V (DVDD) 0.15 mm,
    the supplies per SUPPLY_RULES,
    everything else the 0.1 mm default."""
    nets, gate, boot, drv = net_groups(comps)
    w = {x: GATE_W for x in gate}
    w.update({x: BOOT_W for x in boot})
    w.update({x: SENSE_W for x in drv})
    w.update({x: 0.15 for x in nets if x[:1] == 'M' and x[2:] in ('_VCP', '_CPH', '_CPL', '_DVDD')})
    w.update({n: r[0] for n, r in SUPPLY_RULES.items()})
    return w


def clearances(comps):
    """The switch nodes and the battery reach 25.2 V plus switching
    overshoot, so 31-50 V: IPC-2221B asks 0.13 mm on outer layers under
    solder mask (B4) and 0.1 mm on inner layers (B1).  0.13 mm round those
    nets everywhere; everything else is 3.3 V or 11.4 V logic and gate
    drive, 0.1 mm (B4 and B1 both allow it below 30 V).  The high-side
    gates and the charge pump (VCP, CPH) ride up to 11 V above the battery
    and the phases, about 36 V from ground and from the other phases' low
    side: 0.13 mm round them too."""
    nets, gate, boot, drv = net_groups(comps)
    cl = {x: 0.1 for x in widths(comps)}
    hv = [x for x in nets if x[:1] == 'M' and x[2:] in ('_GHA', '_GHB', '_GHC', '_VCP', '_CPH')]
    for x in drv + hv:
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


def lead_vias(b, comps):
    """One filled and capped via in the middle of each stack-lead pad in
    the board's middle (VIA_INPAD): the supply pad's to the battery
    planes, the others' to the inner signal layers, so nothing runs on the
    top between pads a soldering iron works on, and the bottom under them
    keeps its parts' pads clear of the vias (escape_keep)."""
    k = 0
    for ref in LEAD_MIDDLE:
        pad = b.FindFootprintByReference(ref).Pads()[0]
        q = pad.GetPosition()
        pcb.via(b, q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, pad.GetNetname(), d=VIA_INPAD[0], drill=VIA_INPAD[1])
        k += 1
    return k


def plane_vias(b, comps, bounds):
    """The plane vias (GND, VBAT) and the stubs to them, the same in every
    channel: the template channel's parts' first, each via at a spot whose
    turned copies clear the other channels' copper too, turned onto the
    other channels; then the shared parts'.  (Fanned out channel by
    channel, each channel's vias landed a little differently round its
    neighbours' copper, 0.1-1 mm, and the template's routing, stamp.py,
    had to keep off all of them, in the MCU's and the driver's crowded
    middles too.)  Returns (vias placed, pads without one)."""
    import fanout, stamp
    from shapely.geometry import Point
    parts = channel_parts(comps)
    t = stamp.template_channel(CHANNELS)
    mine = set(parts[t].values())
    chan = set(r for rr in parts.values() for r in rr.values())
    cu = pcb.cu_layers(b)
    obs = fanout.Obstacles(b, cu)
    rv = max(FANOUT['via_d'], FANOUT['inpad']['d']) / 2
    cl = max(FANOUT['clearance'], FANOUT['inpad']['cl'])
    rel = lambda q: _to_template(t, q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY)

    def everywhere(x, y, net):
        u, yr = _to_template(t, x - pcb.CX, y - pcb.CY)
        for n in CHANNELS:
            if n != t:
                px, py = xf_point(n, u, yr)
                px, py = px + pcb.CX, py + pcb.CY
                if not (obs.clear(Point(px, py).buffer(rv), net, cu, cl) and obs.via_room(px, py, 2 * rv + 0.15)):
                    return False
        return True
    opts = {x: y for x, y in FANOUT.items() if x != 'inpad'}
    before = {it.m_Uuid.AsString() for it in b.GetTracks()}
    k, failed = fanout.fanout(b, {'GND', 'VBAT'}, bounds, skip=power_refs(comps) | (set(c.ref for c in comps) - mine),
                              via_ok=everywhere, inpad=FANOUT['inpad'], **opts)
    new = [it for it in b.GetTracks() if it.m_Uuid.AsString() not in before]
    copies = []
    for n in CHANNELS:
        if n == t:
            continue
        for it in new:
            if it.GetClass() == 'PCB_VIA':
                c = pcb.via(b, *xf_point(n, *rel(it.GetPosition())), it.GetNetname(),
                            d=it.GetWidth(pcbnew.F_Cu) / 1e6, drill=it.GetDrillValue() / 1e6)
            else:
                c = pcbnew.PCB_TRACK(b)
                c.SetStart(pcb.P(*xf_point(n, *rel(it.GetStart())))); c.SetEnd(pcb.P(*xf_point(n, *rel(it.GetEnd()))))
                c.SetWidth(it.GetWidth()); c.SetLayer(it.GetLayer()); c.SetNet(it.GetNet())
                b.Add(c)
            c.SetLocked(it.IsLocked())
            copies.append(c)
    bad = _clashing(b, copies, clearances(comps))
    if bad:
        raise SystemExit('plane vias: %d of the template channel\'s vias and stubs, turned, clash in another '
                         'channel' % len(bad))
    k += sum(1 for c in copies if c.GetClass() == 'PCB_VIA')
    k2, failed2 = fanout.fanout(b, {'GND', 'VBAT'}, bounds, skip=power_refs(comps) | chan, inpad=FANOUT['inpad'],
                                **opts)
    return k + k2, failed + failed2


def power_refs(comps):
    """Parts whose plane connections the power copper already makes (the
    stack lead's supply pad: lead_vias)."""
    out = {'P_BAT+', 'P_BAT-', 'P_LV'}
    for n in CHANNELS:
        r = roles(comps, n)
        out |= {r[k] for k in ('QAH', 'QBH', 'QCH', 'QAL', 'QBL', 'QCL', 'CBR_A', 'CBR_B', 'CBR_C', 'R_SH',
                               'PA', 'PB', 'PC')}
    return out


def build(out_path, route=True):
    """The placed board with its power copper, escape and plane vias and
    (route) the lines route_local lays first."""
    b, comps, fps = build_placed(out_path)
    cu = pcb.cu_layers(b)
    # the battery planes keep 1 mm from the hole walls: a crash that cracks
    # a wall should not bring a metal screw to the pack's positive
    pcb.hole_keepouts(b, cu, inner_clear={l: 1.0 for l in VBAT_PLANES})
    pcb.tab_keepouts(b, cu)
    via_rules(b)
    e = H - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for l in GND_PLANES:
        pcb.zone(b, 'GND', l, full, name='GND plane', thermal=False)
    for l in VBAT_PLANES:
        pcb.zone(b, 'VBAT', l, full, name='VBAT plane', thermal=False)
    # the battery plane's windows for signals under the chips (SIG_WINDOW)
    for n in CHANNELS:
        pcb.rule_area(b, [xf_point(n, u, yr) for u, yr in SIG_WINDOW], [SIG_IN], tracks=False, vias=False,
                      pads=False, pours=True, name='signal window')
    for l in cu[1:-1]:
        plane = l in GND_PLANES + VBAT_PLANES and l not in ROUTE_LAYERS
        b.SetLayerType(l, pcbnew.LT_POWER if plane else pcbnew.LT_SIGNAL)
    print('power vias:', power_copper(b, comps))
    print('shunt ground vias:', shunt_vias(b, comps))
    print('gate stubs:', gate_stubs(b, comps))
    print('return ties:', src_ties(b, comps))
    print('stack lead pad vias:', lead_vias(b, comps))
    nets, gate, boot, drv = net_groups(comps)
    cl = clearances(comps)
    # the netclasses carry clearances() and widths() to Freerouting and the DRC
    w = widths(comps)
    for name, members in (('GATE', [x for x in gate if cl[x] <= 0.1]), ('GATE_HI', [x for x in gate if cl[x] > 0.1]),
                          ('BOOT', boot), ('SWITCH', drv),
                          ('PUMP', sorted(x for x in nets if x[:1] == 'M' and x[2:] in ('_VCP', '_CPH')))):
        if members:
            pcb.netclass(b, name, members, width=w[members[0]], clearance=cl[members[0]],
                         via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
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
    need, maybe, late, inpad = escape_pins(b, comps)
    # the lines and buses to the middle first, in their own pads only (a
    # dog-bone beside one would take a neighbouring chip's plane via spot:
    # those that find no room in the pad wait for the plane vias, below)
    mcus = set(roles(comps, n)['MCU'] for n in CHANNELS)
    k, late = fanout.dogbones(b, late, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL,
                              inpad_overhang=ESCAPE_OVERHANG, inpad_only=True,
                              inner_first=across(b, [q for q in late if q[0] in mcus]))
    print('escape vias in the pads of the lines and buses to the middle: %d' % k)
    pins = need + kelvin_pins(comps)
    k, bad = fanout.dogbones(b, pins, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL,
                             inpad_overhang=ESCAPE_OVERHANG,
                             inner_first=across(b, [q for q in need if q[0] in mcus]))
    print('escape vias (QFN pins, Kelvin sense): %d of %d, none for %s' % (k, len(pins), bad))
    # pins whose run out on their own layer has no spot for a via: one in
    # or beside the pad, in every channel or in none (the channels are
    # routed as one)
    got, skipped = [], []
    for group in maybe:
        before = {t.m_Uuid.AsString() for t in b.GetTracks()}
        kk, bb = fanout.dogbones(b, group, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL,
                                     inpad_overhang=ESCAPE_OVERHANG)
        if bb:
            for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
                b.Remove(t)
            skipped.append(group[0][1])
        else:
            got.append(group[0])
    print('escape vias where the run out has no via spot: %s; no room in some channel: MCU/driver pins %s'
          % (', '.join('%s pin %s' % g for g in got) or 'none', ', '.join(skipped) or 'none'))
    # pins whose run out leaves the channel's region: a via in the pad, in
    # every channel or in none
    got, skipped = [], []
    for group in inpad:
        before = {t.m_Uuid.AsString() for t in b.GetTracks()}
        kk, bb = fanout.dogbones(b, group, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL,
                                 inpad_overhang=ESCAPE_OVERHANG, inpad_only=True)
        if bb:
            for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() not in before]:
                b.Remove(t)
            skipped.append(group[0][1])
        else:
            got.append(group[0])
    print('in-pad vias where the run out leaves the channel\'s region: %s; no room in the pad: %s'
          % (', '.join('%s pin %s' % g for g in got) or 'none', ', '.join('pin ' + x for x in skipped) or 'none'))
    k, failed = plane_vias(b, comps, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2))
    print('fanout: %d plane vias, %d pads without one: %s' % (k, len(failed), failed))
    k, bad = fanout.dogbones(b, late, via_d=VIA_SIG[0], via_drill=VIA_SIG[1], inpad=VIA_ESCAPE, hole_cl=HOLE_CL,
                             inpad_overhang=ESCAPE_OVERHANG)
    print('escape vias beside the pads of the lines and buses to the middle: %d of %d, none for %s'
          % (k, len(late), bad))
    if route:
        local, left = route_local(b, comps)
        print('routed first (shared parts\' own nets, channels\' lines to them): %s, %d open %s'
              % (', '.join(local), len(left), left))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(out_path)
    return b


def _clashing(b, items, clmap, default=0.1):
    """The tracks and vias in `items` closer to another net's copper (pads,
    tracks, vias, pours) than the clearance."""
    from shapely.geometry import LineString, Point, Polygon
    mm = lambda v: v / 1e6
    cu = pcb.cu_layers(b)

    def geoms(t):
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition()
            g = Point(mm(q.x), mm(q.y)).buffer(max(mm(t.GetWidth(pcbnew.F_Cu)) / 2,
                                                   mm(t.GetDrillValue()) / 2 + VIA_RING))
            return [(l, g) for l in cu]
        s, e = t.GetStart(), t.GetEnd()
        return [(t.GetLayer(), LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2))]

    ids = set(id(t) for t in items)
    other = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in cu:
                if p.IsOnLayer(l):
                    sp = p.GetEffectivePolygon(l)
                    for k in range(sp.OutlineCount()):
                        o = sp.Outline(k)
                        other.append((l, p.GetNetname(), Polygon([(mm(o.CPoint(i).x), mm(o.CPoint(i).y))
                                                                   for i in range(o.PointCount())])))
    for t in b.GetTracks():
        if id(t) not in ids:
            other += [(l, t.GetNetname(), g) for l, g in geoms(t)]
    n_fixed = len(other)
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in cu:
            # (a plane's fill opens round a via when it is filled again)
            if b.GetLayerType(l) == pcbnew.LT_POWER:
                continue
            if z.GetLayerSet().Contains(l) and z.IsFilled():
                sp = z.GetFilledPolysList(l)
                for k in range(sp.OutlineCount()):
                    o = sp.Outline(k)
                    other.append((l, z.GetNetname(), Polygon([(mm(o.CPoint(i).x), mm(o.CPoint(i).y))
                                                              for i in range(o.PointCount())])))
    # an inner-layer pour keeps tracks out, not vias: a via through it gets
    # a clearance hole in the fill when it is filled again (as finish.py's
    # router has it)
    inner = set(cu[1:-1])
    pours = set(id(g) for l, on, g in other[n_fixed:] if l in inner)
    out = []
    for t in items:
        c = clmap.get(t.GetNetname(), default)
        via = t.GetClass() == 'PCB_VIA'
        if any(ol == l and on != t.GetNetname() and not (via and id(og) in pours)
               and g.distance(og) < max(c, clmap.get(on, default)) - 1e-6
               for l, g in geoms(t) for ol, on, og in other):
            out.append(t)
    return out


# The middle of the board belongs to the shared nets, the rest to the
# channels.  The middle is a square round the centre (it turns onto itself
# with the channels), halfway between the furthest reach of the shared
# parts' pads there and the nearest copper of any channel (core_half).  A
# channel's line to a shared part is copied from channel 1 as far as the
# square, CORE_CUT inside its edge, so the copy's end lies clear of the
# keepout round the square that the middle is routed under.
CORE_CUT = 0.25


def core_half(b, comps):
    """Half the side of the middle square (board mm from the centre along x
    or y, i.e. the max-norm): halfway between the shared parts' pads in the
    middle and the channels' copper (their parts' pads and their own nets'
    vias).  Anything else routed in the middle and turned onto every
    channel, as stamp.py does with what the template channel lacks, walls
    in the pins the channels' routing must reach (rev 2's drivers reach to
    3.7 mm from the centre)."""
    cu = pcb.cu_layers(b)
    chan = set(r for rr in channel_parts(comps).values() for r in rr.values())
    reach = lambda x, y: max(abs(x - pcb.CX), abs(y - pcb.CY))
    pads = {}
    own = {}
    for fp in b.GetFootprints():
        mine = fp.GetReference() in chan
        for p in fp.Pads():
            for l in cu:
                if not p.IsOnLayer(l):
                    continue
                sp = p.GetEffectivePolygon(l)
                for k in range(sp.OutlineCount()):
                    o = sp.Outline(k)
                    r = [reach(o.CPoint(i).x / 1e6, o.CPoint(i).y / 1e6) for i in range(o.PointCount())]
                    pads.setdefault(mine, []).append((min(r), max(r)))
            if p.GetNetname():
                own[p.GetNetname()] = own.get(p.GetNetname(), True) and mine
    c_min = min(lo for lo, hi in pads[True])
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and own.get(t.GetNetname()):
            q = t.GetPosition()
            c_min = min(c_min, reach(q.x / 1e6, q.y / 1e6) - t.GetWidth(pcbnew.F_Cu) / 2e6)
    s_max = max(hi for lo, hi in pads[False] if hi < c_min)
    if c_min - s_max < 0.1:
        raise SystemExit('the middle: shared pads reach %.2f mm, a channel\'s copper %.2f mm: no room between'
                         % (s_max, c_min))
    return (s_max + c_min) / 2


def _keepouts(b, geom, name):
    """Rule areas (no tracks, no vias, every copper layer) over `geom`
    (absolute board mm); returned, to be removed again."""
    import stamp
    rel = lambda q: [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
    return [pcb.rule_area(b, rel(q), pcb.cu_layers(b), tracks=True, vias=True, pads=False, pours=False, name=name)
            for q in stamp._simple(geom.simplify(0.01))]


def _drop(b, zones):
    for z in zones:
        b.Remove(z)


def _first_keepouts(b, comps, half, ends):
    """Keepouts for channel 1's leg of a line or bus, the part copied onto
    every channel: it stays in channel 1's region (stamp.region) and the
    middle inside the copy's cut (CORE_CUT), and off the copper another
    channel has where channel 1 has none (stamp.foreign), so its copies
    land on free copper.  `ends`: the pads it joins, which the region's
    keepout leaves room round."""
    import stamp
    from shapely.geometry import box
    from shapely.ops import unary_union
    parts = channel_parts(comps)
    reg = stamp.region(b, parts, CHANNELS)
    h = half - CORE_CUT
    inner = box(pcb.CX - h, pcb.CY - h, pcb.CX + h, pcb.CY + h)
    full = box(pcb.CX - pcb.HALF - 1, pcb.CY - pcb.HALF - 1, pcb.CX + pcb.HALF + 1, pcb.CY + pcb.HALF + 1)
    free = unary_union([stamp._pad_poly(p, next(l for l in pcb.cu_layers(b) if p.IsOnLayer(l))).buffer(0.3)
                        for p in ends])
    zs = _keepouts(b, full.difference(inner.union(reg)).difference(free), 'channel 1 and the middle')
    rel = lambda q: [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
    obs = stamp.foreign(b, parts, CHANNELS, stamp.counterparts(b, parts, CHANNELS), reg)
    # (inside the middle square they need not: a copy that runs into
    # something there is cut back to the square's edge, _band_part, and
    # joined on from there.  Except vias, up to the copy's cut: a via
    # copied onto a shared part's pad went, and with it the copy's way on
    # to the next layer, leaving it to be joined on from a layer the
    # middle has no room on.)
    core = box(pcb.CX - half, pcb.CY - half, pcb.CX + half, pcb.CY + half)
    for l, g in sorted(obs.items()):
        for q in stamp._simple(g.difference(core).simplify(0.01)):
            zs.append(pcb.rule_area(b, rel(q), [l], tracks=True, vias=True, pads=False, pours=False,
                                    name='other channels'))
        for q in stamp._simple(g.intersection(core).difference(inner).simplify(0.01)):
            zs.append(pcb.rule_area(b, rel(q), [l], tracks=False, vias=True, pads=False, pours=False,
                                    name='other channels'))
    return zs



def route_local(b, comps):
    """Joined by the maze router before anything else, and fixed:
      * each channel's lines that the board's router does not find
        (FIRST_LINES), first: the sense, gate, 3.3 V and PWM lines have the
        fewest ways through, the lines to the middle below have room to go
        round them;
      * the nets whose every pad is on a shared part (the stack lead's
        current filter, the enable clamp): short loops in the crowded
        middle; and the lead's ground pad to the battery pad's tap;
      * a channel's own line to a shared part (each MCU's signal input from
        the stack connector): its pin sits in the ring of escape vias round
        the MCU, facing the driver, and the channel's routing, stamped the
        same in every channel (stamp.py), walls it in;
      * a bus from one pin in every channel to shared parts (each MCU's
        battery voltage input from the one divider), for the same reason:
        channel 1's pin to the nearest shared pad first, that line's part
        outside the middle copied onto every channel, then the net joined.
    Routed with the rest, they found their way taken.  Channel 1's line or
    bus is routed in its own region (stamp.region) and the middle square
    (core_half) only, and every join in the middle only: what lies outside
    the middle is then the same in every channel, and what lies in it
    turns onto the middle, so nothing stamp.py turns into the template
    channel's frame blocks the pins its routing must reach.  Returns (the
    nets, those left open)."""
    import finish
    chan_of = {r: n for n in CHANNELS for r in roles(comps, n).values()}
    refs = {}
    for c in comps:
        for n in c.pins.values():
            if n:
                refs.setdefault(n, set()).add(c.ref)
    shared_only = [n for n, r in refs.items() if not any(x in chan_of for x in r)]
    lines = [n for n, r in refs.items() if len(set(chan_of[x] for x in r if x in chan_of)) == 1
             and any(x not in chan_of for x in r)]
    order = lambda n: (finish.mst_length(b, n), n)
    local = [n for n in sorted(shared_only, key=order) + sorted(lines, key=order) if n not in ('GND', 'VBAT')]
    finish.ROUTE_LAYERS, finish.RES = ROUTE_LAYERS, FINISH_RES
    finish.VIA_D, finish.VIA_DRILL = VIA_SIG
    finish.VIA_RING, finish.POFV_GAP = VIA_RING, None
    w, cl = widths(comps), clearances(comps)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # the power pours' keepouts, as the board's router has them: a via in a
    # pour's neck (the return's at the shunt) cuts it in two
    zones0 = set(z.m_Uuid.AsString() for z in b.Zones())
    routing_keepouts(b)
    pours = [z for z in b.Zones() if z.m_Uuid.AsString() not in zones0]
    import stamp
    from shapely.geometry import box
    half = core_half(b, comps)
    chan_refs = set(r for rr in channel_parts(comps).values() for r in rr.values())
    full = box(pcb.CX - pcb.HALF - 1, pcb.CY - pcb.HALF - 1, pcb.CX + pcb.HALF + 1, pcb.CY + pcb.HALF + 1)
    core = box(pcb.CX - half, pcb.CY - half, pcb.CX + half, pcb.CY + half)
    # the middle's own nets: kept to the middle when all their pads are in it
    inner = lambda n: all(max(abs(p.GetPosition().x / 1e6 - pcb.CX), abs(p.GetPosition().y / 1e6 - pcb.CY)) < half
                          for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == n)
    left, legs = [], []

    def leg(net, pins, a, z):
        """Channel 1's leg from a channel pin (`a`) to a shared pad (`z`;
        None: the net's other pads), in its region and the middle, off the
        other channels' copper (_first_keepouts); returns its band part."""
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        ends = [a, z] if z else [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == net]
        ko = _first_keepouts(b, comps, half, ends)
        if z:
            ok = finish.route_connection(b, net, finish._geom_of(a), finish._geom_of(z), track_w=w.get(net, 0.1),
                                         clmap=cl)
        else:
            ok = not finish.route_net(b, net, track_w=w.get(net, 0.1), clmap=cl, lock=True)
        _drop(b, ko)
        if not ok:
            print('   %s: no way from %s pin %s to its shared pad in channel 1\'s region and the middle'
                  % (net, a.GetParentFootprint().GetReference(), a.GetNumber()))
            return None
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
        return _band_part(b, before, half, pins)

    # 1. each channel's own lines that the board's router does not find
    # (FIRST_LINES).  Channel 1's, in its region and off the copper other
    # channels have and it lacks, copied onto every channel (each finished
    # in its own region if a copy was cut short).
    reg = stamp.region(b, channel_parts(comps), CHANNELS)

    def lay(roles):
        for role in roles:
            t1 = 'M1_%s' % role
            before = set(t.m_Uuid.AsString() for t in b.GetTracks())
            ko = _channel_keepouts(b, comps, 1, reg)
            failed = finish.route_net(b, t1, track_w=w.get(t1, 0.1), clmap=cl, lock=True)
            _drop(b, ko)
            local.append(t1)
            if failed:
                print('   %s: no way in channel 1\'s region' % t1)
                left.append(t1)
                continue
            pins = [p for fp in b.GetFootprints() if fp.GetReference() in chan_refs for p in fp.Pads()
                    if p.GetNetname() == t1]
            exit_ = _band_part(b, before, half, pins)
            for n in sorted(CHANNELS):
                if n == 1:
                    continue
                net = 'M%d_%s' % (n, role)
                _copy(b, n, net, exit_, cl)
                ko = _channel_keepouts(b, comps, n, reg)
                if finish.route_net(b, net, track_w=w.get(net, 0.1), clmap=cl, lock=True):
                    left.append(net)
                _drop(b, ko)
    lay(FIRST_LINES)
    # 2. channel 1's legs, every line's and bus's, before anything is copied
    # or joined in the middle (a join, not turned with the channels, would
    # stand in a later leg's way in every channel)
    for t1, m in sorted(stamp.lines(b, channel_parts(comps), CHANNELS).items()):
        pins = [p for fp in b.GetFootprints() if fp.GetReference() in chan_refs for p in fp.Pads()
                if p.GetNetname() == t1]
        exit_ = leg(t1, pins, pins[0], None)
        if exit_ is None:
            left.append(t1)
        else:
            legs.append((exit_, {n: net for n, net in m.items()}))
    # the buses (one pin in every channel, and shared parts: each MCU's
    # battery voltage input from the one divider, the current amplifiers'
    # outputs to the average): from channel 1's pin to the nearest of the
    # shared parts' pads
    for net, m in stamp.buses(b, channel_parts(comps), CHANNELS).items():
        local.append(net)
        ref, num = m[1]
        pin = next(q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num)
        far = [q for fp in b.GetFootprints() if fp.GetReference() not in chan_refs
               for q in fp.Pads() if q.GetNetname() == net]
        exit_ = leg(net, [pin], pin, _nearest(far, pin.GetPosition()))
        if exit_ is None:
            left.append(net)
        else:
            legs.append((exit_, {n: net for n in CHANNELS}))
    # 3. every leg's band part copied, turned, onto every channel, and
    # 4. joined in the middle only: each copy from its end to the nearest
    # shared pad, then each net whole.  (The keepout lies half a track and
    # the grid's margin outside the square: a copy cut back to its edge is
    # joined on from there.)
    e = half + w.get('', 0.1) / 2 + 0.1
    ko = _keepouts(b, full.difference(box(pcb.CX - e, pcb.CY - e, pcb.CX + e, pcb.CY + e)), 'middle')
    copies = [(n, net, _copy(b, n, net, exit_, cl)) for exit_, m in legs for n, net in sorted(m.items()) if n != 1]
    for n, net, ids in copies:
        _join(b, comps, n, net, ids, w, cl)
    for exit_, m in legs:
        for net in sorted(set(m.values())):
            if finish.route_net(b, net, track_w=w.get(net, 0.1), clmap=cl, lock=True):
                left.append(net)
    _drop(b, ko)
    # 4b. each channel's lines laid after the legs (LATE_LINES), as in 1.
    lay(LATE_LINES)
    # 5. the shared parts' own nets: short loops in the middle (kept to it
    # when all their pads are in it), and the stack lead's ground pad to
    # the battery pad's tap
    for n in [n for n in local if n not in lines and n not in stamp.buses(b, channel_parts(comps), CHANNELS)]:
        ko = _keepouts(b, full.difference(core), 'middle') if inner(n) else []
        if finish.route_net(b, n, track_w=w.get(n, 0.1), clmap=cl, lock=True):
            left.append(n)
        _drop(b, ko)
    _drop(b, pours)
    return local, left


# Channel lines laid by the maze router, in this order, before anything
# else is routed (route_local, step 1):
#   * each phase's switch-node sense line (the driver's SHx pin), then its
#     two gate lines.  The phases' copper lies under the pours' keepouts,
#     all but the switch-node vias under the FETs (on the inner layers), and
#     the board's router aims at the nearest pad, a FET's lead inside a
#     pour; the maze router takes any copper of the net it can reach.  The
#     driver's pins come out as GLB SHB GHB GHC SHC GLC along its FET-side
#     edge (phase A's GHA SHA GLA on its +u side), each gate beside its
#     phase's sense pin with its gate vias past the FETs' +u side, so in
#     every phase one gate line crosses the sense line: laid with the rest,
#     the board's router took a gate line the long way round the next phase
#     and walled in that phase's gates.  Laid phase by phase, sense first,
#     each gate line finds its crossing while the strip below the driver is
#     still open.
#   * the channel's 3.3 V (the driver's DVDD regulator to the MCU, the
#     amplifier and their capacitors).  The MCU's two supply pins sit on
#     opposite sides of the chip (VDDA left, VDD right, by the driver's
#     regulator pin); the PWM line from the MCU's top edge (LC) passes
#     under the chip to reach the far end of the driver's row, and laid
#     before the supply it walled the right-hand pin off from the left on
#     every layer it could take (no path for the repair either).  Laid
#     first, the supply crosses under the chip on an inner layer, and the
#     PWM line takes the other.
#   * the MCU's six PWM lines, in the order of the driver's inputs (HA LA HB
#     LB HC LC along its edge facing the middle).  The MCU's timer pins come
#     round its corner as LC LB | LA HC HB HA, so three of them must cross
#     the others, in the narrow strip between the two chips' corners and the
#     middle; the board's router, with the comparators' lines through the
#     same strip, left two of them open in every routing.  Laid first, from
#     the inner pin out, each takes the line beside the one before.
FIRST_LINES = ('A', 'GHA', 'GLA', 'B', 'GLB', 'GHB', 'C', 'GLC', 'GHC', 'DVDD', 'HA', 'LA', 'HB', 'LB', 'HC', 'LC')
# Channel lines laid by the maze router after the lines and buses to the
# middle (route_local, step 4b): the MCU's analog inputs, round its pins
# (the neutral star, the comparators' dividers, the thermistor, the current
# filter).  Most of their parts sit over the MCU's exposed pad, where no
# through via fits, so their pads join on the top or along it to a via
# spot at the chip's edge, and the few ways there are taken by whichever
# line comes first: left to the board's router with the rest, two or three
# of them stayed open in every routing (the star or comparator B walled in
# by the others).  Laid here in this order, the star first (four pads,
# three of them over the exposed pad), then the comparators, each finds
# its way, and the board's router has only the shunt's sense lines and the
# reset and debug lines left round them.  (Laid before the legs to the
# middle they took the legs' way in.)  The parts' spots were searched with
# these lines' ways in mind (tools/mcu_cluster_search.py: --reserve, the
# wall check).
LATE_LINES = ('NEUTRAL', 'CMP_B', 'CMP_C', 'CMP_A', 'NTC', 'ISENSE', 'IOUT')


def _channel_keepouts(b, comps, n, reg):
    """Keepouts for routing channel n's own net: everything outside its
    region (`reg`, the template's, turned), and for the template channel
    the copper other channels have where it has none (stamp.foreign)."""
    import stamp
    from shapely.geometry import box
    full = box(pcb.CX - pcb.HALF - 1, pcb.CY - pcb.HALF - 1, pcb.CX + pcb.HALF + 1, pcb.CY + pcb.HALF + 1)
    mine = stamp._turn_geom(reg, CHANNELS[n])
    zs = _keepouts(b, full.difference(mine), 'channel %d' % n)
    if n == stamp.template_channel(CHANNELS):
        rel = lambda q: [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
        parts = channel_parts(comps)
        for l, g in sorted(stamp.foreign(b, parts, CHANNELS, stamp.counterparts(b, parts, CHANNELS), reg).items()):
            for q in stamp._simple(g.intersection(mine.buffer(0.5)).simplify(0.01)):
                zs.append(pcb.rule_area(b, rel(q), [l], tracks=True, vias=True, pads=False, pours=False,
                                        name='other channels'))
    return zs


def _nearest(pads, p):
    return min(pads, key=lambda q: (q.GetPosition().x - p.x) ** 2 + (q.GetPosition().y - p.y) ** 2)


def _band_part(b, before, half, pins):
    """The tracks and vias added since `before` (their ids) that run from
    the channel's pin (`pins`: its pads on the net) out to the middle
    square (core_half), cut CORE_CUT inside its edge: [(kind, geometry in
    the template frame, item)], a segment across the edge cut there.  Only
    copper joined to the pin outside the middle: what the line does after
    it enters the middle (beside the shared pad it ends on, say) is not the
    channel's, and its copies would lead nowhere."""
    from shapely.geometry import LineString, Point, box
    from shapely.ops import split
    import stamp
    # (template frame = channel 1's: board mm relative to the centre)
    tp = lambda p: (p.x / 1e6 - pcb.CX, p.y / 1e6 - pcb.CY)
    h = half - CORE_CUT
    mid = box(-h, -h, h, h)
    edge = LineString(box(-half, -half, half, half).exterior.coords)
    pieces = []                # (kind, geometry, item, {layer: shape})
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in before:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = tp(t.GetPosition())
            if not mid.contains(Point(c)):
                g = Point(c).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6)
                pieces.append(('via', c, t, {l: g for l in pcb.cu_layers(b)}))
            continue
        # cut at the square's edge too: a piece inside it that runs into
        # something in another channel goes on its own
        out = LineString([tp(t.GetStart()), tp(t.GetEnd())]).difference(mid)
        out = split(out, edge) if out.intersects(edge) else out
        for piece in getattr(out, 'geoms', [out]):
            if not piece.is_empty and piece.length > 1e-6:
                c = list(piece.coords)
                pieces.append(('track', (c[0], c[-1]), t, {t.GetLayer(): piece.buffer(t.GetWidth() / 2e6)}))
    rel = lambda g: shapely.transform(g, lambda xy: xy - (pcb.CX, pcb.CY))
    reached = [{l: rel(stamp._pad_poly(p, l)) for l in pcb.cu_layers(b) if p.IsOnLayer(l)} for p in pins]
    # and the net's copper already there (the pin's escape via)
    net = pins[0].GetNetname()
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in before and t.GetNetname() == net:
            reached.append({l: rel(g) for l, g in stamp._item_geoms(t).items()})
    touch = lambda a, c: any(l in c and a[l].distance(c[l]) < 1e-3 for l in a)
    keep, grew = [], True
    while grew:
        grew = False
        for pc in pieces:
            if pc not in keep and any(touch(pc[3], r) for r in reached):
                keep.append(pc); reached.append(pc[3]); grew = True
    return [pc[:3] for pc in keep]


def _copy(b, n, net, exit_, cl):
    """Channel 1's band part (_band_part) copied, turned, onto channel n as
    `net`, fixed; a copy that runs into this channel's other copper goes,
    and with it what is then cut off from the pin.  Returns the ids of the
    copies kept."""
    import finish
    copies = []
    for kind, g, t in exit_:
        if kind == 'via':
            c = pcb.via(b, *xf_point(n, *g), net, d=t.GetWidth(pcbnew.F_Cu) / 1e6,
                        drill=t.GetDrillValue() / 1e6)
        else:
            c = pcbnew.PCB_TRACK(b)
            c.SetStart(pcb.P(*xf_point(n, *g[0]))); c.SetEnd(pcb.P(*xf_point(n, *g[1])))
            c.SetWidth(t.GetWidth()); c.SetLayer(t.GetLayer()); c.SetNet(b.FindNet(net))
            b.Add(c)
        copies.append(c)
    ids = set(c.m_Uuid.AsString() for c in copies)
    for c in _clashing(b, copies, cl):
        pcb.remove(b, c)
    finish._drop_floating(b, net)
    for c in b.GetTracks():
        if c.m_Uuid.AsString() in ids:
            c.SetLocked(True)
    return ids


def _join(b, comps, n, net, ids, w, cl):
    """On from the copy's (_copy) end nearest the middle (the maze router
    would otherwise leave from the pin whichever way is cheapest) to the
    nearest of the shared parts' pads of the net.  A copy that cannot go on
    to it stays: the net's other copper in the middle may be nearer
    (route_local joins the net whole next), and failing that the board's
    router finishes it from there."""
    import finish
    kept = [c for c in b.GetTracks() if c.m_Uuid.AsString() in ids and c.GetClass() != 'PCB_VIA']
    if not kept:
        return
    ends = [(t, p) for t in kept for p in (t.GetStart(), t.GetEnd())]
    t, p = min(ends, key=lambda e: max(abs(e[1].x / 1e6 - pcb.CX), abs(e[1].y / 1e6 - pcb.CY)))
    from shapely.geometry import Point
    a = {t.GetLayer(): [Point(p.x / 1e6, p.y / 1e6).buffer(t.GetWidth() / 2e6)]}
    chan_refs = set(r for rr in channel_parts(comps).values() for r in rr.values())
    far = [q for fp in b.GetFootprints() if fp.GetReference() not in chan_refs
           for q in fp.Pads() if q.GetNetname() == net]
    before = set(x.m_Uuid.AsString() for x in b.GetTracks())
    if far and finish.route_connection(b, net, a, finish._geom_of(_nearest(far, p)), track_w=w.get(net, 0.1),
                                       clmap=cl):
        for x in b.GetTracks():
            if x.m_Uuid.AsString() not in before:
                x.SetLocked(True)

ESCAPE_ROOM = 0.6     # clear run beyond a QFN pin's pad that lets it escape on its own layer


def outward_room(b, fp, pad, reach=1.5, inside=None):
    """How far (mm) a track can run straight out from `pad`, away from its
    chip, on the chip's own layer before it meets another part's courtyard
    or other copper (0.1 mm of clearance each side), or leaves `inside`
    (absolute board mm: the chip's channel's region, stamp.region)."""
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
    if inside is not None:
        e = pcb.HALF + 1
        obst.append(box(pcb.CX - e, pcb.CY - e, pcb.CX + e, pcb.CY + e).difference(inside))
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


def _via_obstacles(b):
    """What a through via must keep 0.1 mm from, on every layer: other
    pads on either side, the fixed tracks and vias, the pours and keepouts
    on the outer layers.  (The inner planes let a via through.)"""
    from shapely.geometry import box, LineString, Point, Polygon
    from shapely.ops import unary_union
    mm = lambda v: v / 1e6
    obst = []
    for o in b.GetFootprints():
        for q in o.Pads():
            if q.IsOnLayer(pcbnew.F_Cu) or q.IsOnLayer(pcbnew.B_Cu) or q.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                bb = q.GetBoundingBox()
                obst.append(box(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
    for t in b.GetTracks():
        a = t.GetPosition()
        if isinstance(t, pcbnew.PCB_VIA):
            obst.append(Point(mm(a.x), mm(a.y)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            s, e = t.GetStart(), t.GetEnd()
            obst.append(LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2))
    for z in b.Zones():
        if z.IsOnLayer(pcbnew.F_Cu) or z.IsOnLayer(pcbnew.B_Cu) or (z.GetIsRuleArea() and z.GetDoNotAllowVias()):
            ol = z.Outline().Outline(0)
            obst.append(Polygon([(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())]))
    return unary_union(obst)


def via_spots(obst, fp, pad, room, step=0.05):
    """Distances along `pad`'s outward run (from its edge, up to `room`) at
    which a signal via, 0.1 mm clear of `obst` (_via_obstacles) and of
    every pad but this one, fits: where a pin that escapes on its own layer
    can change layers."""
    from shapely.geometry import Point, box
    mm = lambda v: v / 1e6
    cx, cy = mm(fp.GetPosition().x), mm(fp.GetPosition().y)
    px, py = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
    dx, dy = px - cx, py - cy
    ux, uy = (math.copysign(1, dx), 0.0) if abs(dx) > abs(dy) else (0.0, math.copysign(1, dy))
    half = max(mm(pad.GetSize().x), mm(pad.GetSize().y)) / 2
    bb = pad.GetBoundingBox()
    own = box(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
    rest = obst.difference(own)
    r = VIA_SIG[0] / 2 + 0.1
    out = set()
    for k in range(1, int(room / step) + 1):
        d = round(step * k, 3)
        c = Point(px + ux * (half + d), py + uy * (half + d)).buffer(r)
        if not c.intersects(rest):
            out.add(d)
    return out


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
    output, which leaves its corner of the amplifier on the inner layers."""
    out = []
    for n in CHANNELS:
        r = roles(comps, n)
        out += [(r['R_SH'], '3'), (r['R_SH'], '4'), (r['U_CS'], '4'), (r['U_CS'], '5'), (r['U_CS'], '6')]
    return out


def across(b, pins):
    """The pins (ref, number) whose net lies across their chip: the mean of
    the net's other pads is on the far half of the chip from the pin's
    edge.  Their escape via sits at the pad's inner end, over the chip,
    and the line crosses under it on the inner layers; at the outer end it
    would set out the way it then has to come back, round the chip.  (The
    MCU's analog pins face the middle, their dividers and filters lie
    past the chip towards the FETs.  build asks it of the MCUs only: the
    driver's nets all leave outwards, to the FETs, and its PWM inputs,
    laid first (FIRST_LINES), meet the bundle from the MCU over its edge
    that faces the middle.)"""
    nets = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                q = p.GetPosition()
                nets.setdefault(p.GetNetname(), []).append((fp.GetReference(), q.x / 1e6, q.y / 1e6))
    out = set()
    for ref, num in pins:
        fp = b.FindFootprintByReference(ref)
        pad = next(p for p in fp.Pads() if p.GetNumber() == num)
        cx, cy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
        dx, dy = pad.GetPosition().x / 1e6 - cx, pad.GetPosition().y / 1e6 - cy
        nx, ny = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))
        others = [(x, y) for r, x, y in nets.get(pad.GetNetname(), []) if r != ref]
        if others:
            mx = sum(x for x, y in others) / len(others) - cx
            my = sum(y for x, y in others) / len(others) - cy
            if mx * nx + my * ny < 0:
                out.add((ref, num))
    return out


def escape_pins(b, comps):
    """QFN pins (MCUs and drivers) that get an escape via in their pad:
    every signal pin that has no room beyond its pad on the chip's own
    layer.  Both sides are packed round the chips, so for those a pin's own
    pad is the one sure spot for its via; unused ones are removed after
    routing (cleanup.py).  A pin with ESCAPE_ROOM clear beyond its pad, and
    a spot along that run where a via fits (the same spot in every
    channel), escapes outwards on its own layer instead: a row of in-pad
    vias walls
    the chip in on every layer (0.5 mm apart, no track passes between),
    and a pin that can do without one leaves a gap in the wall.  Unless its
    net has a pad over the chip on the other side (a bootstrap capacitor):
    that pad is reached through the pin's own via.  A pin that needs one in
    any channel gets one in every channel: the channels are routed as one
    (stamp.py), and the copies must find the same vias.
    A pin whose clear run leaves its channel's region short of ESCAPE_ROOM
    (stamp.region: past the middle of the gap to the next channel's copper
    the run is that channel's, and each channel routes in its own region)
    takes a via in its pad where one fits in every channel (a dog-bone
    beside it would stand in that last strip of its own region), and
    otherwise escapes on its own layer as far as it can.  Returns (pins
    that need a via, groups of pins with no via spot along their run,
    pins of lines to the middle, groups of pins in-pad only)."""
    qfn = {}
    for n in CHANNELS:
        r = roles(comps, n)
        qfn[r['MCU']] = 'MCU'
        qfn[r['GD']] = 'GD'
    chan = set(r for rr in channel_parts(comps).values() for r in rr.values())
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                q = p.GetPosition()
                pads.setdefault(p.GetNetname(), []).append((fp.GetReference(), fp.IsFlipped(), q.x / 1e6, q.y / 1e6))
    need, late, tight = set(), set(), set()
    obst = _via_obstacles(b)
    import stamp
    reg = stamp.region(b, channel_parts(comps), CHANNELS)
    home = {}
    for n in CHANNELS:
        r = roles(comps, n)
        home[r['MCU']] = home[r['GD']] = stamp._turn_geom(reg, CHANNELS[n])
    spots = {}               # (role, pin) -> via spots common to every channel so far
    for ref in sorted(qfn):
        fp = b.FindFootprintByReference(ref)
        bb = fp.GetBoundingBox(False)
        x0, y0, x1, y1 = bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6
        for p in fp.Pads():
            net = p.GetNetname()
            if not net or net in ('GND', 'VBAT'):
                continue
            if not any(r_ != ref for r_, fl, ox, oy in pads[net]):
                continue
            key = (qfn[ref], p.GetNumber())
            # a line or bus to the shared parts in the middle (route_local)
            # leaves by the inner layers: outwards on its own layer it
            # meets the next channel's chips.  Its via comes after the
            # plane vias (build), which come first for the chips' supplies.
            if any(r_ not in chan for r_, fl, ox, oy in pads[net]):
                late.add(key)
                continue
            over = any(fl != fp.IsFlipped() and x0 <= ox <= x1 and y0 <= oy <= y1
                       for r_, fl, ox, oy in pads[net])
            room = outward_room(b, fp, p)
            if over or room < ESCAPE_ROOM:
                need.add(key)
                continue
            room = outward_room(b, fp, p, inside=home[ref])
            if room < ESCAPE_ROOM:
                tight.add(key)
                continue
            # a clear run is not enough: the net must be able to change
            # layers somewhere along it, at the same spot in every channel
            # (the channels share one routing, which sees every channel's
            # neighbours at once)
            s = via_spots(obst, fp, p, room)
            spots[key] = s if key not in spots else spots[key] & s
    # in pin order round each chip: an escape takes the end of its pad its
    # neighbour on one side left it (at a 0.4 mm pitch two neighbours'
    # vias at the same end break the hole-to-copper gap), so taken in
    # order the vias alternate ends along a row
    pins = lambda keys: sorted(((ref, num) for ref, role in qfn.items() for r_, num in keys if r_ == role),
                               key=lambda q: (q[0], int(q[1]) if q[1].isdigit() else 0, q[1]))
    maybe = sorted(k for k, s in spots.items() if not s and k not in need | late | tight)
    inpad = sorted(tight - need - late)
    return pins(need), [pins([k]) for k in maybe], pins(late), [pins([k]) for k in inpad]


# ============================================================ artwork
PRODUCT = 'Ridge 3'               # the lineup: Ridge 3 / 7 / 12, by prop size
FIRMWARE = 'RIDGE3_F421'          # the AM32 build to flash (firmware/am32)
# the board's revision, printed by a corner and kept in the title block;
# each board keeps its own (a change to one board moves only its number)
REVISION = '2.0'


def artwork(b, comps):
    """OffGrid silkscreen.  Top (it faces the flight controller): the
    OffGrid mark, the motor number by every motor's pads, battery polarity,
    the pack range, pin 1 of the stack connector, the SWD pad names, the
    board's name and firmware.  Bottom: battery polarity (and the firmware,
    when the top has no room; with no room on either side it is left off,
    and firmware/README.md names the build).  On each side the front arrow
    (the same everywhere) with the side's name, "Top" or "Bottom"; the
    revision by a corner.  Codes in JetBrains Mono, words in Instrument
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
    # the front arrow and which side this is, in the mirror spot
    mirror = [(x, y) for x, y in top.grid_spots((-mark_at[0], mark_at[1]), radius=11.0, step=0.1)]
    A.side_mark(top, mirror, 'Top')
    # SWD test points, on whichever side they are, before the motor
    # numbers: each has one pad to sit by
    for n in CHANNELS:
        r = roles(comps, n)
        for role, s_ in (('TP_DIO', 'D%d'), ('TP_CLK', 'C%d')):
            pl = top if side[r[role]] == 'T' else bot
            pl.label(r[role], s_ % n, size=1.2, dist=0.7, smallest=1.0, face='mono')
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
    # near it as fits, else turned to read along a free strip.  The
    # firmware goes on the bottom if the top has no room left for it (it
    # is read when flashing, with the board in hand)
    at = None
    # (sizes down to the floors: 1.1 mm capitals in Instrument Sans, 1.0 in
    # JetBrains Mono, whose strokes stay over the fabs' 0.15 mm there)
    for runs, caps, sides in (([('sans', PRODUCT + ' ESC')], (1.4, 1.3, 1.2, 1.1), (top,)),
                              ([('mono', FIRMWARE)], (1.1, 1.0), (top, bot))):
        for pl in sides:
            near = (0.0, at + 1.9) if at is not None and pl is top else (0.0, 0.0)
            pts = pl.grid_spots(near, radius=16.0, step=0.25)
            tries = []
            for c in caps:
                g0 = brand.line(runs, c)[0].bounds
                mid = (g0[1] + g0[3]) / 2
                tries.append((c, [(0.0, near[1] + dy - mid, 0, None)
                                  for dy in sorted((0.1 * k for k in range(-340, 341)), key=abs)
                                  if abs(near[1] + dy) < pcb.HALF]))
            for c in caps:
                g0 = brand.line(runs, c)[0].bounds
                mid = (g0[1] + g0[3]) / 2
                tries.append((c, [(x, y - mid, 0, None) for x, y in pts]))
                tries.append((c, [(x - mid, y, 90, None) for x, y in pts]))
            if any(pl.text(runs, sp, size=c, vias='fewest') for c, sp in tries):
                if pl is top:
                    at = top.placed[-1].centroid.y - pcb.CY
                break
        else:
            print('   silk: %s left off: no room on %s at its smallest size'
                  % (runs[0][1], ' or '.join('the ' + {'T': 'top', 'B': 'bottom'}[pl.side] for pl in sides)))
    # the stack lead's pads: what each wire is
    for ref, s_ in (('P_LV', '+'), ('P_LG', 'G'), ('P_LC', 'C'), ('P_L1', '1'), ('P_L2', '2'),
                    ('P_L3', '3'), ('P_L4', '4')):
        top.label(ref, s_, dist=0.7, size=0.9, smallest=0.7, face='mono')
    # which way is forward on the bottom too: the ESC must sit in the stack
    # the same way round as the FC, or every motor number is wrong
    A.side_mark(bot, bot.grid_spots((0.0, -6.0), radius=16.0, step=0.25), 'Bottom')
    # the revision, by a corner: the top first, with the name
    A.revision((top, bot), REVISION)


if __name__ == '__main__':
    import sys
    build_placed(sys.argv[1] if len(sys.argv) > 1 else '/tmp/esc3.kicad_pcb', legal='--nolegal' not in sys.argv)
