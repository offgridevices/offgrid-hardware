"""SmokeBreak v1: build the board.  python3 make.py [--route]

Places every part from place.py, legalises the anchors (no two courtyards
or pads touch, 0.25 mm grid), writes ../smokebreak.kicad_pcb, and with
--route routes, pours and checks it.
"""
import math
import os
import sys

import pcbnew

import board as B
import circuit
import place

OUT = os.path.join(B.V1, 'smokebreak.kicad_pcb')

PULSE_NETS = ['PRE_D', 'PRE_K', 'PRE_M']
SUPPLY_NETS = ['+5V', '+3V3', 'VBUS']
HV_NETS = ['VIN', 'VOUT', 'SRC', 'GATE', 'TPS_VS', 'TPS_BST', 'TPS_PU', 'PRE_G', 'PRE_R',
           'PRE_PULL', 'AUX', 'AUX_F', 'BUCK_SW', 'BUCK_BOOT', 'PROBE'] + [f'BAL{k}' for k in range(2, 8)]

GRID = 0.25
GAP = 0.25          # extra space between neighbours' pads


def boxes(fp):
    """Courtyard box and pads box (board mm, x0 y0 x1 y1)."""
    out = []
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        bb = cy.BBox()
        out.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom(), 0.0))
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        out.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom(), GAP))
    mm = lambda v: pcbnew.ToMM(v)
    return [(mm(a) - B.OX, mm(b) - B.OY, mm(c) - B.OX, mm(d) - B.OY, g) for a, b, c, d, g in out]


def hit(bs, others, dx=0.0, dy=0.0):
    for (a, b, c, d, g) in bs:
        a, b, c, d = a + dx, b + dy, c + dx, d + dy
        for (e, f, h, i, g2) in others:
            m = max(g, g2)
            if a < h + m and e < c + m and b < i + m and f < d + m:
                return True
    return False


def inside(bs, dx, dy, inset=0.5):
    for (a, b, c, d, g) in bs:
        if a + dx < inset or b + dy < inset or c + dx > B.W - inset or d + dy > B.H - inset:
            return False
    return True


def legalise(fps, b):
    settled = []
    for t in b.GetTracks():                 # fixed vias and tracks of the power copper
        bb = t.GetBoundingBox()
        settled.append((pcbnew.ToMM(bb.GetLeft()) - B.OX, pcbnew.ToMM(bb.GetTop()) - B.OY,
                        pcbnew.ToMM(bb.GetRight()) - B.OX, pcbnew.ToMM(bb.GetBottom()) - B.OY, 0.2))
    moved = []
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        if ref in fps and fixed and side == 'T':
            settled += boxes(fps[ref])
    keep = [(name, box) for name, poly, layers in POWER_KEEPOUTS for box in _rect_boxes(poly)]
    cands = sorted(((i * GRID, j * GRID) for i in range(-40, 41) for j in range(-40, 41)),
                   key=lambda d: (math.hypot(*d), abs(d[1]), d))
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        if ref not in fps or fixed:
            continue
        fp = fps[ref]
        bs = boxes(fp)
        allowed = [k for k in KEEPOUT_GUESTS if ref in KEEPOUT_GUESTS[k]]
        obst = settled + [box for name, box in keep if name not in allowed]
        for dx, dy in cands:
            if inside(bs, dx, dy) and not hit(bs, obst, dx, dy):
                break
        else:
            raise RuntimeError(f'no room for {ref}')
        if dx or dy:
            fp.SetPosition(B.P(x + dx, y + dy))
            moved.append((ref, dx, dy))
        settled += [(a + dx, b + dy, c + dx, d + dy, g) for a, b, c, d, g in bs]
    return moved


# ---------------------------------------------------------------- power copper
# Layers: F.Cu parts + signals + power pours; In1 solid GND; In2 the power
# planes (VIN west, VOUT east); B.Cu signals + GND fill + DRONE_NEG strip.
SPLIT = 53.75           # In4: VIN west of the FETs' sources, VOUT east of them (Q1 | Q2)
BACK = 9.5              # ... except a VIN strip along the back (y < BACK) for the aux supply
VOUT_PLANE = [(SPLIT + 0.4, BACK + 0.4), (B.W - 0.4, BACK + 0.4), (B.W - 0.4, B.H - 0.4), (SPLIT + 0.4, B.H - 0.4)]
VIN_PLANE = [(0.4, 0.4), (B.W - 0.4, 0.4), (B.W - 0.4, BACK - 0.4), (SPLIT - 0.4, BACK - 0.4),
             (SPLIT - 0.4, B.H - 0.4), (0.4, B.H - 0.4)]
# battery minus: J1's and J2's minus pins to Q11's drain (both outer layers)
BATT_NEG = [(11.0, 21.8), (15.4, 21.8), (15.4, 24.4), (17.9, 24.4), (17.9, 30.5), (14.2, 30.5),
            (14.2, 34.4), (9.4, 34.4), (9.4, 30.4), (11.0, 30.4)]
# drone minus: the two leads' minus pads side by side, and the shunt's drone end
NEG = [(84.9, 19.0), (89.6, 19.0), (89.6, 33.4), (85.3, 33.4), (85.3, 36.4), (82.8, 36.4), (82.8, 33.9),
       (84.9, 33.9)]
# Q1's drain: west of its pads, and a strip south under the 6S socket's body
# where its plane vias go (the board's centre, under the lockup, stays via-free)
Q1_DRAIN = [(45.0, 20.4), (48.9, 20.4), (48.9, 31.3), (42.6, 31.3), (42.6, 29.7), (45.0, 29.7)]
# the underside art's fields: no vias (tracks and the ground fill may pass)
LOCKUP_W = 22.0
ART_FIELDS = [
    ('brand field', B.rect(B.W / 2 - LOCKUP_W / 2 - 0.5, 22.0, B.W / 2 + LOCKUP_W / 2 + 0.5, 29.95)),
    ('name field', B.rect(37.5, 1.2, 56.5, 8.2)),
    ('flag field', B.rect(65.0, 43.0, 75.0, 49.5)),
    ('smoke field', B.rect(13.0, 3.4, 32.0, 6.2)),
]
SOURCES = B.rect(52.35, 22.6, 55.15, 27.4)
Q2_DRAIN = B.rect(59.85, 19.2, 62.2, 30.6)


def power_copper(b):
    full = B.board_poly(0.4)
    B.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.3, name='GND plane')
    # In4: the power layer
    B.zone(b, 'VIN', pcbnew.In4_Cu, VIN_PLANE, clearance=0.4, name='VIN plane')
    B.zone(b, 'VOUT', pcbnew.In4_Cu, VOUT_PLANE, clearance=0.4, name='VOUT plane')
    # surface copper of the power path: Q1's drain, the sources, Q2's drain
    B.zone(b, 'VIN', pcbnew.F_Cu, Q1_DRAIN, clearance=0.3, priority=2, thermal=False, name='Q1 drain')
    B.zone(b, 'SRC', pcbnew.F_Cu, SOURCES, clearance=0.3, priority=2, thermal=False, name='sources')
    B.zone(b, 'VOUT', pcbnew.F_Cu, Q2_DRAIN, clearance=0.3, priority=2, thermal=False, name='Q2 drain')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, 'DRONE_NEG', layer, NEG, clearance=0.3, priority=2, thermal=False, name='drone negative')
        B.zone(b, 'BATT_NEG', layer, BATT_NEG, clearance=0.3, priority=3, thermal=False, name='battery minus')
    # Q11's sources and the shunt's ground end: surface copper into the GND plane
    B.zone(b, 'GND', pcbnew.F_Cu, B.rect(21.9, 24.9, 24.2, 30.1), clearance=0.3, priority=2, thermal=False,
           name='Q11 sources')
    B.zone(b, 'GND', pcbnew.F_Cu, B.rect(79.9, 34.4, 81.3, 37.2), clearance=0.3, priority=2, thermal=False,
           name='shunt GND')
    # vias from the surface copper into the planes (0.8 / 0.4 mm, ~2 A each)
    pv = dict(d=0.8, drill=0.4)
    # Q1's drain: a row of 1.0 / 0.6 mm vias at each end of its copper (as much
    # barrel as twelve 0.4 mm ones), the middle left to the lockup underneath
    for x in (45.55, 46.8, 48.05):
        B.via(b, x, 20.9, 'VIN', d=1.0, drill=0.6)
    for x in (43.05, 44.3, 45.55, 46.8, 48.05):
        B.via(b, x, 30.55, 'VIN', d=1.0, drill=0.6)
    for y in (19.8, 21.1, 22.4, 23.7, 25.0, 26.3, 27.6, 28.9, 30.0):  # Q2's drain, east of its pads
        B.via(b, 61.6, y, 'VOUT', **pv)
    for y in (25.5, 26.8, 28.1, 29.4):                                 # Q11's sources into the plane
        B.via(b, 23.6, y, 'GND', **pv)
    for y in (35.0, 36.4):                                             # the shunt's ground end
        B.via(b, 80.4, y, 'GND', **pv)
    # the pre-charge FET's source pin east into the VIN plane
    q3 = {p.GetNumber(): p.GetPosition() for p in b.FindFootprintByReference('Q3').Pads()}
    sx, sy = pcbnew.ToMM(q3['3'].x) - B.OX, pcbnew.ToMM(q3['3'].y) - B.OY
    B.track(b, [(sx, sy), (sx + 1.5, sy)], 1.0, pcbnew.F_Cu, 'VIN')
    for k in (-0.6, 0.6):
        B.via(b, sx + 1.9, sy + k, 'VIN', **pv)
    for v in b.GetTracks():
        v.SetLocked(True)


def screw_keepouts(b):
    """No track or via under an M3 washer or a printed boss: a 9.4 mm circle
    round each hole, every copper layer (pours may fill it; the plated ring
    the washer bears on is the hole's own pad)."""
    import math
    for i, (x, y) in enumerate(B.HOLES, 1):
        circle = [(x + 4.7 * math.cos(math.radians(a)), y + 4.7 * math.sin(math.radians(a))) for a in range(0, 360, 15)]
        B.rule_area(b, circle, B.CU_ALL, tracks=True, vias=True, pads=False, pours=False, name=f'screw keep-out {i}')


def art_fields(b):
    """The underside art's fields: no vias through them on any layer."""
    for name, poly in ART_FIELDS:
        B.rule_area(b, poly, B.CU_ALL, tracks=False, vias=True, pads=False, pours=False, name=name)


# ---------------------------------------------------------------- artwork
# Done on the routed board: every word is placed where it clears the pads
# (and on the bottom, the vias), nearest its intended spot.  The bottom is
# the side the owner solders the connectors, toggle and resistors from, so
# it carries the words; positions there are as seen from the bottom
# (x_view = W - x) and mirrored onto the board.  The lockup goes where the
# bottom is cleanest, with clear space far beyond a quarter of its width.

def _obstacles(b, side, vias=True):
    """Boxes (board mm) silk must not touch on one side."""
    mm = lambda v: pcbnew.ToMM(v)
    box = lambda bb, g: (mm(bb.GetLeft()) - B.OX - g, mm(bb.GetTop()) - B.OY - g,
                         mm(bb.GetRight()) - B.OX + g, mm(bb.GetBottom()) - B.OY + g)
    cu = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(cu) or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                out.append(box(p.GetBoundingBox(), 0.2))
        if side == 'T':
            fp.BuildCourtyardCaches()
            cy = fp.GetCourtyard(pcbnew.F_CrtYd)
            if cy.OutlineCount():
                out.append(box(cy.BBox(), 0.0))
    for t in b.GetTracks():
        if vias and t.GetClass() == 'PCB_VIA':
            out.append(box(t.GetBoundingBox(), 0.15))
    return out


def _free(bx, obs, edge=0.6):
    x0, y0, x1, y1 = bx
    if x0 < edge or y0 < edge or x1 > B.W - edge or y1 > B.H - edge:
        return False
    return not any(x0 < c and a < x1 and y0 < d and b_ < y1 for a, b_, c, d in obs)


def _count(bx, obs):
    x0, y0, x1, y1 = bx
    return sum(1 for a, b_, c, d in obs if x0 < c and a < x1 and y0 < d and b_ < y1)


def art_items():
    """(top items, bottom items) at their intended spots (bottom ones in bottom view)."""
    T, Bs = 'F.SilkS', 'B.SilkS'
    t = lambda s, x, y, cap, layer, anchor='middle', **k: dict(kind='text', text=s, x=x, y=y, cap=cap,
                                                               anchor=anchor, layer=layer, **k)
    # the top is full: only the districts with room for their name get one
    top = [t('Brain', 38.0, 39.6, 1.2, T), t('Power', 75.0, 51.2, 1.2, T), t('Sense', 89.4, 33.6, 1.2, T)]
    bottom = [
        t('Drone', 8.0, 30.6, 1.8, Bs), t('Battery', 86.0, 30.6, 1.8, Bs),
        t('USB-C', B.W - 12.0, 43.6, 1.3, Bs), t('Pre-charge', B.W - 55.0, 17.6, 1.3, Bs),
        t('Toggle', 27.0, 37.6, 1.3, Bs), t('SmokeBreak v1  2026', 47.0, 49.6, 1.1, Bs),
    ]
    # each balance socket: its size under it, an arrow up to pin 1 (the black wire)
    for ref, x, rot in place.SOCKETS:
        n = len([k for k in circuit.COMPONENTS[ref]['pins']])
        pin1 = x + (n - 1) * 1.25
        bottom += [t(f'{n - 1}S', B.W - x, 10.1, 1.3, Bs, fixed=True),
                   dict(kind='arrow', x0=B.W - pin1, y0=11.0, x1=B.W - pin1, y1=7.9, layer=Bs, fixed=True)]
    return top, bottom


def add_art(b, work):
    import json
    top, bottom = art_items()
    obs = {'T': _obstacles(b, 'T'), 'B': _obstacles(b, 'B')}
    placed = []
    # the lockup: the cleanest 26 x 9 mm of the bottom (fewest vias and pads),
    # nearest the middle of the front half
    lw, lh = 24.0, 6.0
    pads_b = [o for o in _obstacles(b, 'B', vias=False)]
    # the labels pinned to their parts (the black-wire arrow, Balance) keep
    # their places: the lockup never touches them
    pinned = [it for it in bottom if it.get('fixed')]
    pinned_boxes = []
    for r in B.art(pinned, work):
        x0, y0, x1, y1 = r['bounds']
        pinned_boxes.append((B.W - x1 - 1.0, y0 - 1.0, B.W - x0 + 1.0, y1 + 1.0))
    best = None
    for yy in [y * 0.5 for y in range(int(2 * (lh / 2 + 2)), int(2 * (B.H - lh / 2 - 4)))]:
        for xx in [x * 0.5 for x in range(int(2 * (lw / 2 + 2)), int(2 * (B.W - lw / 2 - 2)))]:
            bx = (xx - lw / 2 - 1, yy - lh / 2 - 1, xx + lw / 2 + 1, yy + lh / 2 + 4)   # + the name below
            n = _count(bx, obs['B']) + 100 * _count(bx, pads_b) + 10000 * _count(bx, pinned_boxes)
            score = (n, abs(xx - B.W / 2) + abs(yy - 0.62 * B.H))
            if best is None or score < best[0]:
                best = (score, xx, yy)
    _, lx, ly = best                                   # board coordinates
    vx = B.W - lx                                      # bottom view
    bottom = [dict(kind='lockup', x=vx, y=ly, width=lw, layer='B.SilkS'),
              dict(kind='text', text='SmokeBreak', x=vx, y=ly + lh / 2 + 2.6, cap=1.3, anchor='middle',
                   layer='B.SilkS')] + bottom
    # measure every item, then nudge each to the nearest free spot
    res = B.art(top + bottom, work)
    out = []
    for it, r in zip(top + bottom, res):
        side = 'B' if it['layer'].startswith('B.') else 'T'
        x0, y0, x1, y1 = r['bounds']
        if side == 'B':                                # to board coordinates
            x0, x1 = B.W - x1, B.W - x0
        fixed = it.get('fixed') or it['kind'] == 'lockup' or it.get('text') == 'SmokeBreak' and side == 'B'
        dx = dy = 0.0
        if not fixed:
            for dx, dy in sorted(((i * 0.25, j * 0.25) for i in range(-24, 25) for j in range(-16, 17)),
                                 key=lambda d: (d[0] ** 2 + d[1] ** 2, abs(d[1]))):
                if _free((x0 + dx, y0 + dy, x1 + dx, y1 + dy), obs[side] + placed):
                    break
            else:
                print('  no room for', it.get('text'))
                continue
        placed.append((x0 + dx - 0.3, y0 + dy - 0.3, x1 + dx + 0.3, y1 + dy + 0.3))
        polys = [dict(outer=[[x + (dx if side == 'T' else -dx), y + dy] for x, y in p['outer']],
                      holes=[[[x + (dx if side == 'T' else -dx), y + dy] for x, y in h] for h in p['holes']])
                 for p in r['polys']]
        B.add_polys(b, polys, it['layer'], mirror_x=B.W / 2 if side == 'B' else None)
        out.append((it.get('text', it['kind']), side, round(x0 + dx, 2), round(y0 + dy, 2)))
    return out


def dsn_keepouts(b):
    """Routing-only extras (none on 6 layers: the planes have In4 to themselves)."""
    return


# parts that belong inside a power area (their pads are its copper)
KEEPOUT_GUESTS = {'drone negative': ('RS1',)}


def _rect_boxes(poly, gap=0.1):
    """A rectilinear power-copper outline as legaliser boxes: one per band
    between its corners' y values (its bounding box would block the notches)."""
    ys = sorted({p[1] for p in poly})
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        ym = (y0 + y1) / 2
        xs = []
        for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
            if (ay - ym) * (by - ym) < 0:
                xs.append(ax + (bx - ax) * (ym - ay) / (by - ay))
        xs.sort()
        out += [(xs[i], y0, xs[i + 1], y1, gap) for i in range(0, len(xs) - 1, 2)]
    return out


# (name, polygon, layers): power copper no other track may cut
POWER_KEEPOUTS = [
    ('sources', SOURCES, [pcbnew.F_Cu]),
    ('Q1 drain', Q1_DRAIN, [pcbnew.F_Cu]),
    ('Q2 drain', Q2_DRAIN, [pcbnew.F_Cu]),
    ('drone negative', NEG, [pcbnew.F_Cu, pcbnew.B_Cu]),
    ('battery minus', BATT_NEG, [pcbnew.F_Cu, pcbnew.B_Cu]),
]


def power_keepouts(b):
    """Rule areas over the surface power copper: no tracks through it (a track
    across the FETs' source copper or the drone-negative strip splits it)."""
    for name, poly, layers in POWER_KEEPOUTS:
        B.rule_area(b, poly, layers, tracks=True, vias=False, pads=False, pours=False, name='keepout ' + name)


def build():
    b = B.new_board(OUT)
    B.outline(b)
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    b.SetLayerType(pcbnew.In4_Cu, pcbnew.LT_POWER)
    fps = B.place_components(b, place.PL)
    B.netclass(b, 'HV', HV_NETS, 0.2, B.HV_CLEAR)
    B.netclass(b, 'Supply', SUPPLY_NETS, 0.3, B.CLEAR)
    B.netclass(b, 'Pulse', PULSE_NETS, 0.8, B.HV_CLEAR)                  # pre-charge: 7.8 A for ~0.1 s
    power_copper(b)
    moved = legalise(fps, b)
    screw_keepouts(b)
    art_fields(b)
    import fanout
    cl = {n: B.HV_CLEAR for n in HV_NETS + PULSE_NETS}
    done, left = fanout.fanout_gnd(b, classes=cl)
    print(f'  ground fan-out: {done} pads, {left} left to the router')
    done, left = fanout.fanout_gnd(b, nets=('VIN',), classes=cl, region=VIN_PLANE)
    print(f'  VIN fan-out into In4: {done} pads, {left} left')
    done, left = fanout.fanout_gnd(b, nets=('VOUT',), classes=cl, region=VOUT_PLANE)
    print(f'  VOUT fan-out into In4: {done} pads, {left} left')
    for t in b.GetTracks():
        t.SetLocked(True)
    power_keepouts(b)
    return b, fps, moved


if __name__ == '__main__':
    b, fps, moved = build()
    for ref, dx, dy in moved:
        print(f'  moved {ref:6s} {dx:+.2f} {dy:+.2f}')
    pcbnew.SaveBoard(OUT, b)
    B.set_stackup(OUT)
    B.write_rules(OUT)
    print('placed', len(fps), '->', OUT)
