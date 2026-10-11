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
import place

OUT = os.path.join(B.V1, 'smokebreak.kicad_pcb')

HV_NETS = ['VIN', 'VOUT', 'SRC', 'GATE', 'TPS_VS', 'TPS_BST', 'TPS_PU', 'PRE_G', 'PRE_R',
           'PRE_PULL', 'AUX', 'AUX_F', 'BUCK_SW', 'BUCK_BOOT', 'PROBE'] + [f'BAL{k}' for k in range(2, 10)]

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
        if ref in fps and fixed:
            settled += boxes(fps[ref])
    for name, poly, layers in POWER_KEEPOUTS:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        settled.append((min(xs), min(ys), max(xs), max(ys), 0.1))
    cands = sorted(((i * GRID, j * GRID) for i in range(-40, 41) for j in range(-40, 41)),
                   key=lambda d: (math.hypot(*d), abs(d[1]), d))
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        if ref not in fps or fixed:
            continue
        fp = fps[ref]
        bs = boxes(fp)
        allowed = [k for k in KEEPOUT_GUESTS if ref in KEEPOUT_GUESTS[k]]
        obst = [s for s in settled if not any(_is_keepout(s, k) for k in allowed)]
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
SPLIT = 76.0            # In2: VIN west of this line, VOUT east of it (Q1 | Q2)
VIN_BAND = [(0.4, 0.4), (51.8, 0.4), (51.8, 7.6), (17.0, 7.6), (17.0, 41.0), (SPLIT - 0.4, 41.0),
            (SPLIT - 0.4, B.H - 0.4), (0.4, B.H - 0.4)]      # + a strip along the back to the pre-charge FET
VOUT_BAND = [(77.4, 0.4), (B.W - 0.4, 0.4), (B.W - 0.4, B.H - 0.4), (SPLIT + 0.4, B.H - 0.4),
             (SPLIT + 0.4, 41.0), (77.4, 41.0)]
BATT_NEG = [(9.6, 21.6), (15.4, 21.6), (15.4, 26.8), (18.0, 26.8), (18.0, 33.6), (15.4, 33.6),
            (15.4, 38.4), (9.6, 38.4)]
# drone negative strip between J3 and J4 (both layers), notched round the
# shunt's sense pad on that end
NEG = [(79.6, 21.4), (82.95, 21.4), (82.95, 29.45), (81.4, 29.45), (81.4, 32.3), (82.95, 32.3),
       (82.95, 37.8), (79.6, 37.8)]


def power_copper(b):
    full = B.board_poly(0.4)
    B.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.3, name='GND plane')
    # In4: the power layer, VIN west of the FETs, VOUT east of them
    B.zone(b, 'VIN', pcbnew.In4_Cu, B.rect(0.4, 0.4, SPLIT - 0.4, B.H - 0.4), clearance=0.4, name='VIN plane')
    B.zone(b, 'VOUT', pcbnew.In4_Cu, B.rect(SPLIT + 0.4, 0.4, B.W - 0.4, B.H - 0.4), clearance=0.4,
           name='VOUT plane')
    # Q1's drain, the sources, Q2's drain + J4's positive: solid surface copper
    B.zone(b, 'VIN', pcbnew.F_Cu, B.rect(64.6, 44.4, 71.35, 51.2), clearance=0.3, priority=2, thermal=False,
           name='Q1 drain')
    B.zone(b, 'SRC', pcbnew.F_Cu, B.rect(73.45, 45.95, 76.55, 48.45),
           clearance=0.3, priority=2, thermal=False, name='sources')
    B.zone(b, 'VOUT', pcbnew.F_Cu, [(78.4, 44.4), (81.0, 44.4), (81.0, 42.6), (84.4, 40.0), (86.4, 40.0),
                                    (86.4, 44.6), (86.4, 51.4), (78.4, 51.4)],
           clearance=0.3, priority=2, thermal=False, name='Q2 drain')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, 'DRONE_NEG', layer, NEG, clearance=0.3, priority=2, thermal=False, name='drone negative')
    # battery minus: both connectors' minus pads to Q11's drain, both outer layers;
    # Q11's sources into the ground plane
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, 'BATT_NEG', layer, BATT_NEG, clearance=0.3, priority=3, thermal=False, name='battery minus')
    # the shunt's GND end: surface copper and vias into the GND plane
    B.zone(b, 'GND', pcbnew.F_Cu, B.rect(83.8, 23.6, 85.6, 28.9), clearance=0.3, priority=2, thermal=False,
           name='shunt GND')
    # vias from the surface copper into the planes (0.8 / 0.4 mm, ~2 A each)
    pv = dict(d=0.8, drill=0.4)
    for x in (65.2, 66.45, 67.7):
        for y in (45.2, 46.45, 47.7, 48.95, 50.2):
            B.via(b, x, y, 'VIN', **pv)
    for x, y in ((79.0, 50.75), (80.25, 50.75), (81.5, 50.75), (82.75, 50.75), (84.0, 50.75), (85.25, 50.75),
                 ):
        B.via(b, x, y, 'VOUT', **pv)
    B.zone(b, 'GND', pcbnew.F_Cu, B.rect(19.7, 27.0, 22.4, 33.4), clearance=0.3, priority=2, thermal=False,
           name='Q11 sources')
    for y in (27.6, 28.9, 30.2, 31.5, 32.8):           # Q11's sources (x 20.5) into the plane
        B.via(b, 21.6, y, 'GND', **pv)
    # the pre-charge FET's source into the VIN strip
    B.track(b, [(50.1, 9.4), (50.1, 7.2)], 1.0, pcbnew.F_Cu, 'VIN')
    for x in (49.5, 50.7):
        B.via(b, x, 7.0, 'VIN', **pv)
    for x in (84.25, 85.35):
        for y in (24.1, 25.2, 26.3):
            B.via(b, x, y, 'GND', **pv)
    for v in b.GetTracks():
        v.SetLocked(True)


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
    top = [t('Supply', 16.0, 1.9, 1.2, T), t('Cells', 38.0, 24.6, 1.2, T), t('Brain', 38.0, 38.9, 1.2, T),
           t('Power', 75.0, 51.2, 1.2, T), t('Sense', 89.4, 33.6, 1.2, T), t('Light', 67.0, 16.4, 1.2, T),
           t('SmokeBreak v1', 47.0, 51.4, 1.2, T)]
    bottom = [
        t('Drone', 8.0, 30.6, 1.8, Bs), t('Battery', 86.0, 30.6, 1.8, Bs),
        dict(kind='arrow', x0=46.0, y0=16.0, x1=46.0, y1=10.2, layer=Bs, fixed=True),   # to pin 1
        t('Black wire', 47.0, 15.6, 1.3, Bs, 'start', fixed=True), t('Balance', 56.0, 5.4, 1.3, Bs, fixed=True),
        t('USB-C', 37.0, 9.8, 1.3, Bs), t('Pre-charge', 19.0, 10.4, 1.3, Bs), t('Toggle', 27.0, 37.6, 1.3, Bs),
    ]
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
    best = None
    for yy in [y * 0.5 for y in range(int(2 * (lh / 2 + 2)), int(2 * (B.H - lh / 2 - 4)))]:
        for xx in [x * 0.5 for x in range(int(2 * (lw / 2 + 2)), int(2 * (B.W - lw / 2 - 2)))]:
            bx = (xx - lw / 2 - 1, yy - lh / 2 - 1, xx + lw / 2 + 1, yy + lh / 2 + 4)   # + the name below
            n = _count(bx, obs['B']) + 100 * _count(bx, pads_b)
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
KEEPOUT_GUESTS = {'drone negative': ('C14', 'C52', 'C53', 'RS1')}


def _is_keepout(box, name):
    poly = [p for n, p, l in POWER_KEEPOUTS if n == name][0]
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return box[:4] == (min(xs), min(ys), max(xs), max(ys))


# (name, polygon, layers): power copper no other track may cut
POWER_KEEPOUTS = [
    ('sources', B.rect(73.6, 46.1, 76.4, 48.3), [pcbnew.F_Cu]),
    ('Q1 drain', B.rect(64.8, 44.6, 71.2, 51.0), [pcbnew.F_Cu]),
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
    B.netclass(b, 'Supply', ['+5V', '+3V3'], 0.3, B.CLEAR)
    B.netclass(b, 'Pulse', ['PRE_D', 'PRE_K'], 0.8, B.HV_CLEAR)          # pre-charge: 7.5 A for ~0.1 s
    power_copper(b)
    moved = legalise(fps, b)
    import fanout
    cl = {n: B.HV_CLEAR for n in HV_NETS + ['PRE_D', 'PRE_K']}
    done, left = fanout.fanout_gnd(b, classes=cl)
    print(f'  ground fan-out: {done} pads, {left} left to the router')
    done, left = fanout.fanout_gnd(b, nets=('VIN',), classes=cl, region=(0.0, SPLIT - 1.0))
    print(f'  VIN fan-out into In4: {done} pads, {left} left')
    done, left = fanout.fanout_gnd(b, nets=('VOUT',), classes=cl, region=(SPLIT + 1.0, B.W))
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
