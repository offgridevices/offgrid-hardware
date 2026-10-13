# -*- coding: utf-8 -*-
"""Turn layout.py's template and fixed positions into one placement table
(ref -> (x, y, rotation, side)), and draw it for checking.

    kd python3 placement.py out.png      plot of both sides
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import circuit, layout, pcb

EXPLICIT = ('U_D', 'U_E', 'R_S', 'U_A', 'TP_D', 'TP_C')


def channel_role(n, key):
    """A template key -> the role circuit.py gives that part in channel n."""
    if key[0] == 'Q' and len(key) == 3:
        return 'Q%d%s' % (n, key[1:])
    if key.startswith('P_M'):
        return 'P_M%d%s' % (n, key[3:])
    if key in EXPLICIT:
        return key + str(n)
    # a role that names its own channel ('driver 1 GVDD'): '#' in the key
    return '%d:%s' % (n, key.replace('#', str(n)))


def table(comps=None):
    """ref -> (x, y, rot, side) for every part placed so far, and the list
    of parts with no position yet."""
    comps = comps or circuit.build()
    by_role = {c.role: c for c in comps}
    out = {}
    for n, rot in layout.CHANNELS.items():
        for key, (u, r, a, side) in layout.channel_template(n).items():
            role = channel_role(n, key)
            if role not in by_role:
                raise KeyError('template key %r: no part with role %r' % (key, role))
            x, y = layout.place(rot, u, r)
            out[by_role[role].ref] = (x, y, (a + rot) % 360, side)
    for role, pos in layout.fixed().items():
        if role not in by_role:
            raise KeyError('fixed: no part with role %r' % role)
        out[by_role[role].ref] = pos
    missing = [c for c in comps if c.ref not in out]
    return out, missing


# Parts that serve one particular pin: role (without the channel prefix)
# -> (ref, pad) of that pin ('%d' takes the channel number).
PIN_ANCHOR = {
    'U_FC VBAT pin 1': ('U_FC', '1'), 'U_FC VDD pin 23': ('U_FC', '23'), 'U_FC VDD pin 35': ('U_FC', '35'),
    'U_FC VDD pin 48': ('U_FC', '48'), 'U_FC VREF+/VDDA pins 20/21': ('U_FC', '21'), 'U_FC VDDA': ('U_FC', '20'),
    'U_FC bulk': ('U_FC', '23'), 'U_FC reset filter': ('U_FC', '7'),
    'gyro VDD': ('U_IMU', '8'), 'gyro VDDIO': ('U_IMU', '5'), 'gyro VDD bulk': ('U_IMU', '8'),
    'gyro supply filter': ('U_IMU', '8'),
    'FC LDO in': ('U_LDO', '6'), 'FC LDO out': ('U_LDO', '1'), 'ESC LDO in': ('U_LDOE', '6'),
    'ESC LDO out': ('U_LDOE', '1'), 'BEC input': ('U_BEC', '4'), 'BEC input HF': ('U_BEC', '4'),
    'BEC VCC': ('U_BEC', '7'), 'BEC bootstrap': ('U_BEC', '6'), 'BEC output': ('L_BEC', '2'),
    'BEC output#2': ('L_BEC', '2'), 'BEC UVLO top': ('U_BEC', '3'), 'BEC UVLO bottom': ('U_BEC', '3'),
    'gate-drive LDO input': ('U_GVDD', '8'), 'gate-drive LDO input filter': ('U_GVDD', '8'),
    'gate-drive LDO output': ('U_GVDD', '1'), 'gate-drive LDO feedback top': ('U_GVDD', '2'),
    'gate-drive LDO feedback bottom': ('U_GVDD', '2'),
    'crystal load': ('Y1', '1'), 'crystal load#2': ('Y1', '3'), 'BOOT0 pulldown': ('U_FC', '46'),
    'U_E%d VDD': ('U_E%d', '3'), 'U_E%d VDD bulk': ('U_E%d', '3'), 'driver %d GVDD': ('U_D%d', '4'),
    'U_A%d supply': ('U_A%d', '3'), 'bootstrap A': ('U_D%d', '20'), 'bootstrap B': ('U_D%d', '17'),
    'bootstrap C': ('U_D%d', '14'), 'gate high A': ('U_D%d', '19'), 'gate high B': ('U_D%d', '16'),
    'gate high C': ('U_D%d', '13'), 'gate low A': ('U_D%d', '11'), 'gate low B': ('U_D%d', '10'),
    'gate low C': ('U_D%d', '9'), 'current divider top': ('U_A%d', '6'), 'current divider bottom': ('U_E%d', '11'),
    'current filter': ('U_E%d', '11'), 'battery current average %d': ('U_A%d', '6'),
    'ESC %d vsense top': ('U_E%d', '12'), 'ESC %d vsense bottom': ('U_E%d', '12'),
    'ESC %d vsense filter': ('U_E%d', '12'),
    'neutral A': ('U_E%d', '9'), 'neutral B': ('U_E%d', '9'), 'neutral C': ('U_E%d', '9'),
    'BEMF bottom A': ('U_E%d', '27'), 'BEMF bottom B': ('U_E%d', '23'), 'BEMF bottom C': ('U_E%d', '8'),
    'BEMF top A': ('Q%dAL', '5'), 'BEMF top B': ('Q%dBL', '5'), 'BEMF top C': ('Q%dCL', '5'),
    'TP_D%d': ('U_E%d', '20'), 'TP_C%d': ('U_E%d', '21'),
    # each LED's resistor at its LED, the divider and filter parts at the
    # MCU pin they serve, the beeper switch's pulldown at its gate
    'power LED': ('LED_PWR', '2'), 'status LED': ('LED_STAT', '2'),
    'VBAT divider bottom': ('U_FC', '19'), 'VBAT filter': ('U_FC', '19'),
    'current average pulldown': ('U_FC', '18'), 'current filter': ('U_FC', '18'),
    'beeper gate pulldown': ('Q_BZ', '1'),
}
# the capacitors that stay on the bottom, at their chip's pin (the
# driver's bootstrap and supply, the MCUs' and amplifiers' decoupling)
REGULATORS = ('U_LDO', 'U_LDOE', 'U_GVDD')
BOTTOM_ROLES = ('bootstrap', 'GVDD', 'VDD', 'supply', 'gate high', 'gate low')
# the small parts that must sit right at their pin go first
FIRST = ('VDD', 'bootstrap', 'gate ', 'GVDD', 'supply', 'gyro', 'LDO', 'BEC', 'crystal')


def anchor_of(c):
    """(ref, pad) a small part belongs beside, or None."""
    role = c.role
    n = None
    if ':' in role:
        n, role = role.split(':', 1)
        n = int(n)
    for key, (ref, pad) in PIN_ANCHOR.items():
        if ('%d' in ref) != bool(n):
            continue
        k = key % n if '%d' in key else key
        if k == role:
            return (ref % n if n else ref), pad
    if c.ref.startswith('TP_') and c.ref[-1].isdigit():
        n = int(c.ref[-1])
        return ('U_E%d' % n, '20' if c.ref.startswith('TP_D') else '21')
    return None


def hints(comps, pl, fps):
    """Hint positions for the parts not in pl: beside their anchor pin, or
    beside the placed pin of their most specific net."""
    import pcbnew
    pads = {}
    for ref, fp in fps.items():
        for p in fp.Pads():
            q = p.GetPosition()
            pads[(ref, p.GetNumber())] = (q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, p.GetNetname())
    bynet = {}
    for (ref, num), (x, y, net) in pads.items():
        if net:
            bynet.setdefault(net, []).append((ref, num))
    out = {}
    for c in comps:
        if c.ref in pl:
            continue
        a = anchor_of(c)
        if not a:
            best = None
            for net in set(v for v in c.pins.values() if v):
                m = bynet.get(net, [])
                if m and (best is None or len(m) < len(best)):
                    best = m
            a = best[0] if best else None
        if not a or a not in pads:
            out[c.ref] = (0.0, 0.0, 0, 'T')
            continue
        ref, num = a
        x, y, _ = pads[a]
        cx, cy, _, side = pl[ref]
        # a step outwards from the anchor part's centre
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy) or 1.0
        out[c.ref] = (x + 0.9 * dx / d, y + 0.9 * dy / d, 0, side)
    return out


def channel_copies(comps):
    """{channel 1 ref: [(channel n ref, turn of channel n)]} for every part
    that belongs to one channel (role 'n:...', or a ref ending in its
    channel's digit such as TP_D1)."""
    by_role = {c.role: c.ref for c in comps}
    out = {}
    for c in comps:
        if c.role.startswith('1:'):
            import re
            key = c.role[2:]
            cp = []
            for n in layout.CHANNELS:
                if n == 1:
                    continue
                # roles name their channel's chips too ('U_E1 VDD', 'ESC 1 vsense top')
                k = '%d:%s' % (n, key)
                if k not in by_role:
                    k = '%d:%s' % (n, re.sub(r'(?<![0-9])1(?![0-9])', str(n), key))
                cp.append((by_role[k], layout.CHANNELS[n]))
            out[c.ref] = cp
        elif c.ref in ('TP_D1', 'TP_C1'):
            out[c.ref] = [(c.ref[:-1] + str(n), layout.CHANNELS[n]) for n in layout.CHANNELS if n != 1]
    return out


def pack_all(verbose=True, sym=False, gap=0.1, sides=True):
    """The full placement: layout.py's parts where it puts them, every
    other part packed beside its pin.  sym: each channel's own parts are
    placed once, for channel 1, and turned onto the other three, so the
    four channels are copies of one another (stamp.py routes one and
    copies the routing).  Off by default: the whole board is routed at
    once, and each channel's passives packed on their own sit nearer their
    pins (the battery pads, USB-C, receiver pads and BEC take different
    room in each channel): 12 % less wire.  The power stage stays a copy
    either way (layout.template).  Returns (placement, unplaced)."""
    import pcbnew, legalize
    comps = circuit.build()
    pl, missing = table(comps)
    placed = [c for c in comps if c.ref in pl]
    b = pcb.new_board(6)
    fps = pcb.place_components(b, placed, pl)
    hint = hints(comps, pl, fps)
    hint.update({r: v for r, v in layout.hint().items() if r not in pl})
    full = dict(pl, **hint)

    copies = channel_copies(comps) if sym else {}
    in_channel = set(copies) | {k for v in copies.values() for k, _ in v}

    def prio(c):
        r = c.role.split(':')[-1]
        # the regulators, then their own capacitors and feedback divider,
        # before anything else can take the room at their pins
        if c.ref in REGULATORS:
            return -12
        if 'LDO' in r:
            return -10
        if not c.part.startswith(('C', 'R')):
            p = -1                       # the bigger loose parts before the passives
        else:
            p = 0 if any(k in r for k in FIRST) else 1
        # the channels' parts need room four times over: they go first
        return 2 * p + (0 if c.ref in in_channel else 1)
    small = lambda c: c.part.startswith(('C', 'R', 'PAD_TP')) or c.ref in ('D_USB', 'D_TVS', 'Q_BZ')
    flip = small
    if sides:
        # signal parts on top, where each pad can take a filled via of
        # its own straight down; the bottom keeps the power stage, the
        # chips and only the capacitors that must sit at a chip's pin, so
        # the room between them is free for those vias to pass
        for c in comps:
            if c.ref in pl or c.ref not in full:
                continue
            x, y, r, sd = full[c.ref]
            role = c.role.split(':')[-1]
            at_pin = any(k in role for k in BOTTOM_ROLES)
            full[c.ref] = (x, y, r, 'B' if at_pin and sd == 'B' else ('T' if small(c) else sd))
        flip = None
    import power
    pegs = [('B', (x - 0.45, y - 0.45, x + 0.45, y + 0.45)) for x, y in layout.usb_pegs()]
    if layout.FLAG:
        pegs.append((layout.FLAG['side'], layout.flag_box(0.1)))
    # the power pours: no other part on them
    for net, lay, poly, pr in power.all_copper()[0]:
        if lay in ('F.Cu', 'B.Cu'):
            xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
            pegs.append(('T' if lay == 'F.Cu' else 'B', (min(xs), min(ys), max(xs), max(ys))))
    keep = [(sd, bb, net) for bb, net in power.via_sites() for sd in ('T', 'B')]
    pl2, left = legalize.pack(comps, full, fixed=set(pl), gap=gap, edge=0.3, radius=9.0, verbose=verbose,
                              rotatable=lambda c: True, priority=prio, flip=flip, reserved=pegs, pad_keep=keep,
                              sym=copies or None)
    return pl2, left


def plot(png, pl=None):
    import pcbnew, pcb
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly, Circle
    comps = circuit.build()
    if pl is None:
        pl, missing = table(comps)
    else:
        missing = [c for c in comps if c.ref not in pl]
    placed = [c for c in comps if c.ref in pl]
    b = pcb.new_board(6)
    pcb.outline(b)
    fps = pcb.place_components(b, placed, pl)
    fig, axs = plt.subplots(1, 2, figsize=(22, 11))
    for ax, side, title in ((axs[0], 'T', 'TOP (seen from above)'), (axs[1], 'B', 'BOTTOM (seen from above, through the board)')):
        bp = pcb.board_polygon()
        ax.add_patch(MPoly(list(bp.exterior.coords), closed=True, fill=False, ec='k', lw=1.5))
        for sx in (-1, 1):
            for sy in (-1, 1):
                ax.add_patch(Circle((sx * pcb.HOLE, sy * pcb.HOLE), 1.6, fill=False, ec='k'))
                ax.add_patch(Circle((sx * pcb.HOLE, sy * pcb.HOLE), pcb.HOLE_KEEPOUT_R, fill=False, ec='0.6', ls='--'))
        for ref, fp in fps.items():
            onb = fp.IsFlipped()
            if (side == 'B') != onb:
                continue
            lay = pcbnew.B_CrtYd if onb else pcbnew.F_CrtYd
            cy = fp.GetCourtyard(lay)
            col = 'tab:red' if ref.startswith('Q') else 'tab:blue' if ref.startswith('U') else 'tab:green' if ref.startswith('P') else '0.3'
            for i in range(cy.OutlineCount()):
                o = cy.Outline(i)
                pts = [(o.CPoint(k).x / 1e6 - pcb.CX, o.CPoint(k).y / 1e6 - pcb.CY) for k in range(o.PointCount())]
                ax.add_patch(MPoly(pts, closed=True, fill=True, alpha=0.15, fc=col, ec=col, lw=0.8))
            for p in fp.Pads():
                q = p.GetPosition(); s = p.GetBoundingBox()
                ax.add_patch(MPoly([(s.GetLeft() / 1e6 - pcb.CX, s.GetTop() / 1e6 - pcb.CY),
                                    (s.GetRight() / 1e6 - pcb.CX, s.GetTop() / 1e6 - pcb.CY),
                                    (s.GetRight() / 1e6 - pcb.CX, s.GetBottom() / 1e6 - pcb.CY),
                                    (s.GetLeft() / 1e6 - pcb.CX, s.GetBottom() / 1e6 - pcb.CY)],
                                   closed=True, fill=True, fc='gold', ec='none', alpha=0.7))
                if p.GetNumber() in ('1', '4', '13', '25', '9') or len(fp.Pads()) <= 3:
                    ax.text(q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, p.GetNumber(), fontsize=4, ha='center', va='center')
            c = fp.GetPosition()
            ax.text(c.x / 1e6 - pcb.CX, c.y / 1e6 - pcb.CY, ref, fontsize=5.5, ha='center', va='center', color='k')
        ax.set_xlim(-18, 18); ax.set_ylim(18, -18); ax.set_aspect('equal'); ax.set_title(title)
        ax.grid(True, lw=0.3); ax.set_xticks(range(-17, 18, 1)); ax.set_yticks(range(-17, 18, 1))
        ax.tick_params(labelsize=5)
        if side == 'B':
            pass
    fig.suptitle('%d placed, %d to place: %s' % (len(placed), len(missing),
                 ', '.join(sorted(c.role for c in missing))[:400]), fontsize=8)
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    return missing


if __name__ == '__main__':
    png = sys.argv[1] if len(sys.argv) > 1 else '/w/out/placement.png'
    if '--pack' in sys.argv:
        pl, left = pack_all()
        m = plot(png, {k: v for k, v in pl.items() if k not in left})
    else:
        m = plot(png)
    print('%d unplaced' % len(m))
