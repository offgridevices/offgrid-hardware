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

HV_NETS = ['VIN', 'VOUT', 'SRC', 'GATE', 'TPS_VS', 'TPS_BST', 'TPS_PU', 'PRE_G', 'PRE_D', 'PRE_K',
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
    for t in b.GetTracks():                 # fixed vias of the power copper
        q, r = t.GetPosition(), pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
        x, y = pcbnew.ToMM(q.x) - B.OX, pcbnew.ToMM(q.y) - B.OY
        settled.append((x - r, y - r, x + r, y + r, 0.2))
    moved = []
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        if ref in fps and fixed:
            settled += boxes(fps[ref])
    cands = sorted(((i * GRID, j * GRID) for i in range(-40, 41) for j in range(-40, 41)),
                   key=lambda d: (math.hypot(*d), abs(d[1]), d))
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        if ref not in fps or fixed:
            continue
        fp = fps[ref]
        bs = boxes(fp)
        for dx, dy in cands:
            if inside(bs, dx, dy) and not hit(bs, settled, dx, dy):
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
VIN_BAND = [(0.4, 11.0), (17.0, 11.0), (17.0, 41.0), (SPLIT - 0.4, 41.0), (SPLIT - 0.4, B.H - 0.4),
            (0.4, B.H - 0.4)]
VOUT_BAND = [(77.4, 0.4), (B.W - 0.4, 0.4), (B.W - 0.4, B.H - 0.4), (SPLIT + 0.4, B.H - 0.4),
             (SPLIT + 0.4, 41.0), (77.4, 41.0)]
# drone negative strip between J3 and J4 (both layers), notched round the
# shunt's sense pad on that end
NEG = [(79.6, 21.4), (82.95, 21.4), (82.95, 29.45), (81.4, 29.45), (81.4, 32.3), (82.95, 32.3),
       (82.95, 37.8), (79.6, 37.8)]


def power_copper(b):
    full = B.board_poly(0.4)
    B.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.3, name='GND plane')
    # In2: VIN from the battery connectors down the west side and along the
    # south to Q1; VOUT up the east side.  The rest of In2 routes signals.
    B.zone(b, 'VIN', pcbnew.In2_Cu, VIN_BAND, clearance=0.4, name='VIN plane')
    B.zone(b, 'VOUT', pcbnew.In2_Cu, VOUT_BAND, clearance=0.4, name='VOUT plane')
    # Q1's drain, the sources, Q2's drain + J4's positive: solid surface copper
    B.zone(b, 'VIN', pcbnew.F_Cu, B.rect(64.6, 44.4, 71.35, 51.2), clearance=0.3, priority=2, thermal=False,
           name='Q1 drain')
    B.zone(b, 'SRC', pcbnew.F_Cu, [(73.45, 45.95), (74.9, 45.95), (74.9, 44.6), (76.55, 44.6), (76.55, 48.45),
                                   (75.1, 48.45), (75.1, 49.8), (73.45, 49.8)],
           clearance=0.3, priority=2, thermal=False, name='sources')
    B.zone(b, 'VOUT', pcbnew.F_Cu, [(78.4, 44.4), (81.0, 44.4), (81.0, 42.6), (84.4, 40.0), (86.4, 40.0),
                                    (86.4, 44.6), (86.4, 51.4), (78.4, 51.4)],
           clearance=0.3, priority=2, thermal=False, name='Q2 drain')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, 'DRONE_NEG', layer, NEG, clearance=0.3, priority=2, thermal=False, name='drone negative')
    # the shunt's GND end: surface copper and vias into the GND plane
    B.zone(b, 'GND', pcbnew.F_Cu, B.rect(83.8, 23.6, 85.6, 28.9), clearance=0.3, priority=2, thermal=False,
           name='shunt GND')
    # vias from the surface copper into the planes (0.8 / 0.4 mm, ~2 A each)
    pv = dict(d=0.8, drill=0.4)
    for x in (65.2, 66.45, 67.7):
        for y in (45.2, 46.45, 47.7, 48.95, 50.2):
            B.via(b, x, y, 'VIN', **pv)
    for x, y in ((79.0, 50.75), (80.25, 50.75), (81.5, 50.75), (82.75, 50.75), (84.0, 50.75), (85.25, 50.75),
                 (82.6, 44.6), (83.85, 43.6), (85.1, 42.6), (85.6, 44.6), (85.6, 45.85), (85.6, 47.1),
                 (85.6, 48.35), (84.35, 48.35), (83.1, 48.35)):
        B.via(b, x, y, 'VOUT', **pv)
    for x in (84.25, 85.35):
        for y in (24.1, 25.2, 26.3):
            B.via(b, x, y, 'GND', **pv)
    for v in b.GetTracks():
        v.SetLocked(True)


# ---------------------------------------------------------------- artwork
# The bottom is the side the owner solders the connectors, toggle and
# resistors from, so it carries the words; positions there are given as
# seen from the bottom (x_view = W - x) and mirrored onto the board.  The
# lockup sits alone on a clean black field (no copper tracks or vias under
# it), with clear space far beyond a quarter of its width.
LOCKUP_FIELD = (30.0, 40.6, 64.0, 51.0)          # bottom view: x0, y0, x1, y1


def bottom_art():
    S = 'B.SilkS'
    t = lambda s, x, y, cap=1.5, anchor='start', **k: dict(kind='text', text=s, x=x, y=y, cap=cap,
                                                         anchor=anchor, layer=S, **k)
    cx = (LOCKUP_FIELD[0] + LOCKUP_FIELD[2]) / 2
    items = [
        dict(kind='lockup', x=cx, y=44.6, width=24.0, layer=S),
        t('SmokeBreak', cx, 49.4, 1.3, 'middle'),
        # the ends
        t('Drone', 4.6, 30.6, 1.8), t('Battery', 89.4, 30.6, 1.8, 'end'),
        # balance: pin 1 is the black wire
        dict(kind='arrow', x0=46.0, y0=15.0, x1=46.0, y1=10.6, layer=S),
        t('Black wire', 47.4, 14.6, 1.3),
        t('Balance', 56.0, 3.0, 1.3, 'middle'),
        t('USB-C', 37.0, 9.6, 1.3, 'middle'),
        t('Pre-charge', 19.0, 10.4, 1.3, 'middle'),
        t('Toggle', 27.0, 37.2, 1.3, 'middle'),
    ]
    return items


def add_art(b, work):
    items = bottom_art()
    res = B.art(items, work)
    for it, r in zip(items, res):
        mirror = B.W / 2 if it['layer'].startswith('B.') else None
        B.add_polys(b, r['polys'], it['layer'], mirror_x=mirror)


def dsn_keepouts(b):
    """Routing-only: In2's power bands are copper the signals must leave alone."""
    for poly in (VIN_BAND, VOUT_BAND):
        B.rule_area(b, poly, [pcbnew.In2_Cu], tracks=True, vias=False, pads=False, pours=False)


def build():
    b = B.new_board(OUT)
    B.outline(b)
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    fps = B.place_components(b, place.PL)
    B.netclass(b, 'HV', HV_NETS, 0.2, B.HV_CLEAR)
    B.netclass(b, 'Supply', ['+5V', '+3V3'], 0.3, B.CLEAR)
    power_copper(b)
    moved = legalise(fps, b)
    return b, fps, moved


if __name__ == '__main__':
    b, fps, moved = build()
    for ref, dx, dy in moved:
        print(f'  moved {ref:6s} {dx:+.2f} {dy:+.2f}')
    pcbnew.SaveBoard(OUT, b)
    B.set_stackup(OUT)
    B.write_rules(OUT)
    print('placed', len(fps), '->', OUT)
