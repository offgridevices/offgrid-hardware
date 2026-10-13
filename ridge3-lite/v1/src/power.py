# -*- coding: utf-8 -*-
"""Power copper: the pours and the fixed vias that carry the motor and
battery current.  Everything is drawn once in the rear channel's template
coordinates (u along the edge, r towards it; layout.py) and turned onto
each channel's edge.

Stackup (6 layers, 1 oz copper on all of them):

  F.Cu   parts; battery and motor pads; switch node up to the motor pads
  In1    ground plane, solid
  In2    signals
  In3    each channel's return ("Mn_SRC": low-side sources to the shunt)
         under its FETs; signals elsewhere
  In4    battery plane (VBAT), solid
  B.Cu   the FETs and their pours: VBAT over the high sides' drain tabs,
         the switch node (Mn_A/B/C) between the rows, the return along
         the edge

The current in one phase:  battery pad -> VBAT vias -> In4 -> drain-tab
vias -> high-side FET -> switch-node pour (B.Cu) -> vias -> motor pad
(F.Cu);  back through the low-side FET -> source strip (B.Cu) and its vias
-> In3 return pour -> shunt -> ground vias -> In1 -> battery pad.

A via goes through every layer, so each one here sits where the far side
has copper of its own net or nothing: never under another net's pad.
Every via is filled and capped (JLCPCB POFV, free on 6 layers), so the
ones in pads are flat for soldering.
"""
import pcb, layout as L

VIA_PWR = (0.5, 0.25)     # diameter, drill
VIA_GATE = (0.4, 0.2)     # in the 0.4 mm gate pins


def _xf(n, pts):
    rot = L.CHANNELS[n]
    return [L.place(rot, u, r) for u, r in pts]


def _rect(u0, r0, u1, r1):
    return [(u0, r0), (u1, r0), (u1, r1), (u0, r1)]


def channel_copper(n):
    """(zones, vias, tracks) for channel n.  zones: (net, layer name,
    polygon in board mm, priority); vias: (x, y, net, (d, drill));
    tracks: (net, layer name, [points in board mm], width)."""
    p = lambda s: 'M%d_%s' % (n, s)
    Z, V, T = [], [], []
    ph_u = L.PH_U
    a, c = ph_u['A'], ph_u['C']
    left = (n == 3)
    # ---- bottom: VBAT over the high sides' drain tabs, one pour for the bank
    # (its inner edge just clears the drain-tab vias at r 8.0: the strip
    # inside it, up to the driver, takes the bootstrap capacitors and gate
    # resistors)
    Z.append(('VBAT', 'B.Cu', _rect(a - 1.75, L.R_HS - 1.575, c + 1.75, L.R_HS + 1.1), 2))
    src_free = []                      # u of the return vias at the edge
    for ph, u0 in ph_u.items():
        net = p(ph)
        # switch node: from the high side's source row to the low side's
        # drain tab, across the peg lane
        Z.append((net, 'B.Cu', _rect(u0 - 1.75, L.R_HS + 1.2, u0 + 1.75, L.R_LS + 0.95), 3))
        # drain-tab vias into the VBAT plane; the one at (u0, 8.0) is in the
        # bridge capacitor's VBAT pad on top
        tabs = ((u0 - 0.9, 8.45), (u0, 8.0), (u0 - 0.9, 9.45), (u0, 9.45), (u0 + 0.9, 9.45))
        if left and ph == 'A':
            # the USB-C's VBUS contact leaves over A's -u side: its two
            # vias there move to the +u side
            tabs = ((u0 + 0.9, 8.45), (u0, 8.0), (u0 + 0.45, 8.9), (u0, 9.45), (u0 + 0.9, 9.45))
        for u, r in tabs:
            V.append((u, r, 'VBAT', VIA_PWR))
        # the bridge capacitor's return, between this high side's drain
        # pins and the next one's (in the capacitor's other pad)
        V.append((u0 + 1.9, 7.8, p('SRC'), VIA_PWR))
        # gate pins take their via in the pad, except where the left
        # edge's USB-C sits over them (below)
        if not (left and ph in 'AB'):
            V.append((u0 - 0.97, L.R_HS + 1.68, p('GH' + ph), VIA_GATE))
        if not (left and ph == 'B'):
            V.append((u0 - 0.97, L.R_LS + 1.68, p('GL' + ph), VIA_GATE))
        # the low side's sources down into the In3 return, in the gap to
        # the next FET (over the sources on top are the motor pads)
        src_free.append(u0 + 1.9)
    src_free.append(a - 1.6)
    # ---- switch node up to the motor pads (top)
    if not left:
        for ph, u0 in ph_u.items():
            net = p(ph)
            for u, r in ((u0 - 0.7, L.PEG_R), (u0 + 0.1, L.PEG_R), (u0 + 0.9, L.PEG_R),
                         (u0 - 0.6, 13.5), (u0 + 0.6, 13.5), (u0 - 0.4, 14.55), (u0 + 0.4, 14.55)):
                V.append((u, r, net, VIA_PWR))
            Z.append((net, 'F.Cu', _rect(u0 - 1.0, L.PEG_R - 0.45, u0 + 1.3, L.R_PAD + 1.2), 3))
    else:
        # The left edge (USB-C): its shell pads stand over phase A at
        # r 10.2-12.2 and 14.2-16.2, u 0.6-2.8.  The pads stand at r 13.2
        # (layout.PAD_U_LEFT).  A rises under the USB-C's body and runs to
        # its pad between the shell pads; B and C drop straight into
        # their own drain tabs.
        pa, pb, pc, pr = L.PAD_U_LEFT['A'], L.PAD_U_LEFT['B'], L.PAD_U_LEFT['C'], L.R_PAD_LEFT
        for u, r in ((-0.9, 12.7), (0.0, 13.0), (0.9, 12.7), (-0.5, 13.7), (0.4, 13.75), (1.3, 13.55)):
            V.append((u, r, p('A'), VIA_PWR))
        Z.append((p('A'), 'F.Cu', [(-1.3, 12.45), (pa + 0.7, 12.45), (pa + 0.7, pr + 1.2),
                                   (pa - 0.7, pr + 1.2), (pa - 0.7, 13.95), (-1.3, 13.95)], 3))
        for u, r in ((5.15, L.PEG_R), (5.1, 12.9), (5.1, 13.7), (5.65, 14.3)):
            V.append((u, r, p('B'), VIA_PWR))
        Z.append((p('B'), 'F.Cu', _rect(pb - 0.7, L.PEG_R - 0.45, pb + 0.7, pr + 1.2), 3))
        for u, r in ((7.9, L.PEG_R), (8.8, L.PEG_R), (8.0, 13.2), (8.8, 13.2), (8.4, 14.0)):
            V.append((u, r, p('C'), VIA_PWR))
        Z.append((p('C'), 'F.Cu', _rect(pc - 0.7, L.PEG_R - 0.45, pc + 0.9, pr + 1.2), 3))
        # the USB-C's shell pads take the edge over A's and B's gaps
        src_free = [u for u in src_free if not (0.3 < u < 3.0)]
        # Three gate pins sit under the USB-C (its contacts at r 10.1-11.2
        # over A's high-side gate, its shell pads over B's): a short track
        # on the bottom takes each to a via where the top is clear, A's
        # round the front locating peg in the peg lane (u -0.56).
        g = L.R_HS + 1.68
        T.append((p('GHA'), 'B.Cu', [(-0.77, g), (-1.25, 11.3), (-1.5, L.PEG_R)], 0.15))
        V.append((-1.5, L.PEG_R, p('GHA'), VIA_GATE))
        T.append((p('GHB'), 'B.Cu', [(3.03, g), (3.03, L.PEG_R), (3.4, L.PEG_R)], 0.15))
        V.append((3.4, L.PEG_R, p('GHB'), VIA_GATE))
        T.append((p('GLB'), 'B.Cu', [(3.03, L.R_LS + 1.68), (2.5, 16.5)], 0.15))
        V.append((2.5, 16.5, p('GLB'), VIA_GATE))
    for u in src_free:
        for r in (15.65, 16.35):
            V.append((u, r, p('SRC'), VIA_PWR))
    # ---- return: the source strip along the edge (bottom), the In3 pour
    shunt_u, shunt_r = L.template()['R_S'][:2]
    s1u = shunt_u + 1.55                       # shunt pad 1 (the return), towards the FETs
    Z.append((p('SRC'), 'B.Cu', [(s1u - 0.85, shunt_r - 0.9), (s1u + 0.85, shunt_r - 0.9), (s1u + 0.85, 15.4),
                                 (c + 2.15, 15.4), (c + 2.15, 16.7), (s1u - 0.85, 16.7)], 3))
    Z.append((p('SRC'), pcb.INNER['src'], _rect(s1u - 0.9, 7.2, c + 2.3, 16.7), 2))
    # The shunt's vias stand on the inner edge of its pads: over the outer
    # part, on top, are the receiver / aux pads (layout.fixed).  On the
    # rear edge the battery pads are there instead: BAT- over pad 2 takes
    # its ground vias outboard as well, and pad 1's return vias go out
    # past BAT+'s end at the edge.
    s2u = shunt_u - 1.55
    for du in (-0.4, 0.4):
        V.append((s2u + du, shunt_r - 0.6, 'GND', VIA_PWR))
        if n == 1:
            V.append((s2u + du, shunt_r + 0.3, 'GND', VIA_PWR))
        else:
            V.append((s1u + du, shunt_r - 0.6, p('SRC'), VIA_PWR))
    if n == 1:
        for u in (s1u + 0.45, s1u + 1.2):
            V.append((u, 16.45, p('SRC'), VIA_PWR))
    # the gate-drive corner round the driver (layout.DRIVE_*)
    for suffix, pts, width in L.DRIVE_TRACKS:
        T.append((p(suffix), 'B.Cu', [(u, L.drv(y)) for u, y in pts], width))
    for suffix, u, y in L.DRIVE_VIAS:
        V.append((u, L.drv(y), p(suffix), VIA_GATE))
    zones = [(net, lay, _xf(n, poly), pr) for net, lay, poly, pr in Z]
    vias = [(x, y, net, d) for (u, r, net, d) in V for (x, y) in _xf(n, [(u, r)])]
    tracks = [(net, lay, _xf(n, pts), w) for net, lay, pts, w in T]
    return zones, vias, tracks


def battery_copper():
    """The battery pads' vias into the planes (rear edge, left half; see
    layout.fixed).  BAT- stands over the rear channel's shunt ground pad
    and shares its vias; BAT+ has a field of its own beside the rear
    channel's FETs, clear of the shunt's return pad underneath."""
    V = []
    for u in (-3.75, -2.95):
        for r in (12.45, 13.25, 14.05, 14.85):
            V.append((u, r, 'VBAT', VIA_PWR))
    for r in (12.45, 13.25):
        V.append((-4.55, r, 'VBAT', VIA_PWR))
    for r in (12.35, 13.1, 13.85):
        V.append((-6.75, r, 'GND', VIA_PWR))
    return [(x, y, net, d) for (u, r, net, d) in V for (x, y) in _xf(1, [(u, r)])]


def all_copper():
    zones, vias, tracks = [], [], []
    for n in L.CHANNELS:
        z, v, t = channel_copper(n)
        zones += z; vias += v; tracks += t
    vias += battery_copper()
    return zones, vias, tracks


def via_sites():
    """Every fixed via as (box, net) for the packer: no part may put a pad
    of another net there (a filled, capped via may sit under a part's
    body, or inside a pad of its own net)."""
    out = []
    for x, y, net, (d, _) in all_copper()[1]:
        h = d / 2 + 0.1
        out.append(((x - h, y - h, x + h, y + h), net))
    return out
