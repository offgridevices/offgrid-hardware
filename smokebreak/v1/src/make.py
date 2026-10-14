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
import parts
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
# Layers: F.Cu parts + signals + power pours; In1 solid GND; In2, In3
# signals; In4 the power layer (VIN west, VOUT east); B.Cu signals + GND
# fill.  The battery corner (both plugs and the fuse's line side) is a VBAT
# island on every layer but In1, so the XT30's plus reaches the fuse.
# Battery current: plug + -> VBAT -> F1 -> VIN plane -> Q1 drain -> sources ->
# Q2 drain -> VOUT plane -> lead pads; back: lead minus -> shunt -> GND plane
# -> Q11 -> plug minus.
VBAT_AREA = [(0.4, 12.4), (4.3, 12.4), (4.3, 19.3), (13.4, 19.3), (13.4, 27.6), (8.2, 27.6), (8.2, 42.85),
             (13.4, 42.85), (13.4, 50.2), (0.4, 50.2)]
VIN_PLANE = [(0.4, 0.4), (44.0, 0.4), (44.0, 19.3), (55.35, 19.3), (55.35, 50.2), (13.8, 50.2), (13.8, 42.45),
             (8.6, 42.45), (8.6, 28.0), (13.8, 28.0), (13.8, 18.9), (4.7, 18.9), (4.7, 12.0), (0.4, 12.0)]
VOUT_PLANE = [(44.4, 0.4), (91.2, 0.4), (91.2, 50.2), (55.75, 50.2), (55.75, 18.9), (44.4, 18.9)]
# the fuse's load side, on the surface, its vias into the VIN plane under
# the fuse's body (the controller's pins leave no room east of it)
F1_LOAD = B.rect(4.7, 12.4, 11.6, 18.9)
# battery minus: J1's and J2's minus pins to Q11's drain (both outer layers)
BATT_NEG = [(8.6, 28.0), (18.2, 28.0), (18.2, 35.0), (14.4, 35.0), (14.4, 42.45), (8.6, 42.45)]
Q11_SOURCES = B.rect(19.0, 31.0, 21.4, 36.2)
# Q1's drain, west of its pads, down to its vias below the lockup's field
Q1_DRAIN = [(45.8, 24.9), (50.0, 24.9), (50.0, 31.0), (48.6, 31.0), (48.6, 35.4), (45.8, 35.4)]
SOURCES = [(54.4, 26.75), (55.4, 26.75), (55.4, 25.4), (57.1, 25.4), (57.1, 29.25), (56.1, 29.25),
           (56.1, 30.6), (54.4, 30.6)]
Q2_DRAIN = B.rect(61.9, 25.1, 64.8, 30.9)
# drone minus: the two leads' minus pads and the shunt's drone end
NEG = [(82.4, 27.6), (85.6, 27.6), (85.6, 24.3), (91.2, 24.3), (91.2, 33.7), (86.6, 33.7), (86.6, 29.5),
       (82.4, 29.5)]
SHUNT_GND = B.rect(82.6, 31.0, 86.2, 33.4)
# the underside art's fields: no vias (tracks and the ground fill may pass)
LOCKUP_W = 22.0
ART_FIELDS = [
    ('brand field', B.rect(B.W / 2 - LOCKUP_W / 2 - 0.5, 21.2, B.W / 2 + LOCKUP_W / 2 + 0.5, 29.6)),
    ('name field', B.rect(B.W / 2 - 9.5, 3.4, B.W / 2 + 9.5, 8.6)),
    ('flag field', B.rect(69.5, 43.0, 80.5, 49.4)),
    ('smoke field', B.rect(26.5, 9.9, 45.5, 12.3)),        # under the pre-charge resistors
]


def power_copper(b):
    full = B.board_poly(0.4)
    B.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.3, name='GND plane')
    B.zone(b, 'VIN', pcbnew.In4_Cu, VIN_PLANE, clearance=0.4, name='VIN plane')
    B.zone(b, 'VOUT', pcbnew.In4_Cu, VOUT_PLANE, clearance=0.4, name='VOUT plane')
    for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        B.zone(b, 'VBAT', layer, VBAT_AREA, clearance=0.4, priority=3, thermal=False, name='battery plus')
    B.zone(b, 'VIN', pcbnew.F_Cu, F1_LOAD, clearance=0.3, priority=2, thermal=False, name='fuse load side')
    B.zone(b, 'VIN', pcbnew.F_Cu, Q1_DRAIN, clearance=0.3, priority=2, thermal=False, name='Q1 drain')
    B.zone(b, 'SRC', pcbnew.F_Cu, SOURCES, clearance=0.3, priority=2, thermal=False, name='sources')
    B.zone(b, 'VOUT', pcbnew.F_Cu, Q2_DRAIN, clearance=0.3, priority=2, thermal=False, name='Q2 drain')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, 'DRONE_NEG', layer, NEG, clearance=0.3, priority=2, thermal=False, name='drone negative')
        B.zone(b, 'BATT_NEG', layer, BATT_NEG, clearance=0.3, priority=3, thermal=False, name='battery minus')
    B.zone(b, 'GND', pcbnew.F_Cu, Q11_SOURCES, clearance=0.3, priority=2, thermal=False, name='Q11 sources')
    B.zone(b, 'GND', pcbnew.F_Cu, SHUNT_GND, clearance=0.3, priority=2, thermal=False, name='shunt GND')
    big = dict(d=1.0, drill=0.6)              # ~3 A each
    pv = dict(d=0.8, drill=0.4)
    for x in (5.5, 6.6, 7.7):                 # the fuse's load side into the VIN plane, under its body
        for y in (13.4, 14.6, 15.8, 17.0, 18.2):
            B.via(b, x, y, 'VIN', **big)
    for x, y in ((1.3, 20.0), (2.5, 20.0), (1.3, 21.2), (2.5, 21.2), (1.3, 22.4), (2.5, 22.4),
                 (7.3, 20.0), (8.5, 20.0), (7.3, 21.2), (7.3, 22.4)):   # the XT30's plus, up to the fuse
        B.via(b, x, y, 'VBAT', **big)
    for x in (46.5, 47.8):                    # Q1's drain, below the lockup's field
        for y in (30.4, 31.6, 32.8, 34.0):
            B.via(b, x, y, 'VIN', **big)
    for x in (63.0, 64.2):                    # Q2's drain, east of its pads
        for y in (25.7, 26.9, 28.1, 29.3, 30.4):
            B.via(b, x, y, 'VOUT', **big)
    for y in (31.6, 32.8, 34.0, 35.3):        # Q11's sources into the GND plane
        B.via(b, 20.6, y, 'GND', **big)
    for x in (83.2, 84.4, 85.6):              # the shunt's ground end
        B.via(b, x, 32.6, 'GND', **big)
    for x, y in ((9.6, 29.0), (9.6, 33.6), (9.6, 38.6), (12.6, 37.0), (13.2, 39.6)):   # battery minus, F <-> B
        B.via(b, x, y, 'BATT_NEG', **big)
    for v in b.GetTracks():
        v.SetLocked(True)


def balance_buses(b):
    """Pin k of every balance socket is tap k, and every socket has its pin 1
    on one line: so tap k is one straight track along its pin row on B.Cu,
    socket to socket, before the router sees the board."""
    rows = {}
    for ref, _ in place.SOCKETS:
        for p in b.FindFootprintByReference(ref).Pads():
            q = p.GetPosition()
            rows.setdefault(p.GetNetname(), []).append((pcbnew.ToMM(q.x) - B.OX, pcbnew.ToMM(q.y) - B.OY))
    n = 0
    for net, pts in rows.items():
        if len(pts) > 1:
            pts.sort()
            B.track(b, [pts[0], pts[-1]], 0.4, pcbnew.B_Cu, net)
            n += 1
    return n


def screw_keepouts(b):
    """No track or via under an M3 washer or a printed boss: an 8 mm circle
    round each hole, every copper layer (pours may fill it; the plated ring
    the washer bears on is the hole's own pad)."""
    import math
    for i, (x, y) in enumerate(B.HOLES, 1):
        circle = [(x + 4.0 * math.cos(math.radians(a)), y + 4.0 * math.sin(math.radians(a))) for a in range(0, 360, 15)]
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

def _obstacles(b, side, vias=True, courtyards=True):
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
        if side == 'T' and courtyards:
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


def _pad(ref, num):
    """A pad's position (board mm) from the placement, without a board."""
    import math
    x, y, rot = place.PL[ref][:3]
    fp = B.load_fp(parts.PARTS[circuit.COMPONENTS[ref]['part']]['fp'])
    fp.SetPosition(B.P(50, 30)); fp.SetOrientationDegrees(rot)
    p = [p for p in fp.Pads() if p.GetNumber() == num][0].GetPosition()
    return x + pcbnew.ToMM(p.x) - B.OX - 50, y + pcbnew.ToMM(p.y) - B.OY - 30


def art_items():
    """(top items, bottom items), every one fixed where it is drawn.  Bottom
    items are in bottom view (x_view = W - x): the underside reads as a page
    seen from below.

    Underside, on the board's centre line: the product's name along the back,
    the OffGrid lockup at the exact centre.  The flag at the drone end's
    front corner.  The balance sockets each get their size and an arrow at
    pin 1 (the black wire), all on pin 1's line; the plugs and the drone pads
    their polarity.  Two small notes for whoever opens it up."""
    T, Bs = 'F.SilkS', 'B.SilkS'
    W = B.W

    def t(s, x, y, cap, layer, anchor='middle', **k):
        return dict(kind='text', text=s, x=x, y=y, cap=cap, anchor=anchor, layer=layer, fixed=True, **k)

    def v(x):                    # board x -> bottom view
        return W - x

    bottom = [
        # centred left to right; up from the middle by 1.2 mm so it clears the 6S socket's top pin
        dict(kind='lockup', x=W / 2, y=B.H / 2 - 1.2, width=19.0, layer=Bs, fixed=True),
        t('SmokeBreak', W / 2, 5.3, 2.0, Bs, weight=600),
        t('v1.0', W / 2, 7.55, 0.8, Bs, font='mono'),
        dict(kind='flag', x=v(75.0), y=46.2, hoist=5.26, layer=Bs, fixed=True),     # under the rocker, level with the screws
        t('The magic smoke stays in.', v(36.0), 11.55, 0.9, Bs),                    # under the pre-charge resistors
    ]
    # balance sockets: "4S ->" left of each pin 1, on pin 1's line
    for ref, x in place.SOCKETS:
        n = len(circuit.COMPONENTS[ref]['pins'])
        px, py = _pad(ref, '1')
        bottom += [t(f'{n - 1}S', v(px) - 2.75, py + 0.6, 1.2, Bs, anchor='end'),
                   dict(kind='arrow', x0=v(px) - 2.5, y0=py, x1=v(px) - 1.3, y1=py, head=0.7, layer=Bs, fixed=True)]
    # the battery plugs: name between the pins, polarity beside them
    for ref, name, cap, side in (('J1', 'XT60', 1.2, 3.0), ('J2', 'XT30', 1.0, 2.6)):
        (x1, y1), (x2, y2) = _pad(ref, '1'), _pad(ref, '2')     # 1 = minus, 2 = plus
        bottom += [t(name, v(x1), (y1 + y2) / 2 + cap / 2, cap, Bs),
                   t('\u2212', v(x1) + side, y1 + 0.6, 1.2, Bs), t('+', v(x2) + side, y2 + 0.6, 1.2, Bs)]
    # the drone leads' pads, both sides (the wires may go in from either):
    # the name between the pads, polarity on the board side of each
    top = []
    for ref, name, cap in (('J3', 'XT60', 1.0), ('J4', 'XT30', 0.9)):
        (x1, y1), (x2, y2) = _pad(ref, '1'), _pad(ref, '2')     # 1 = plus, 2 = minus
        for layer, f in ((T, lambda x: x), (Bs, v)):
            lst = top if layer == T else bottom
            fx = layer == Bs
            lst += [dict(t(name, f(x1), (y1 + y2) / 2 + cap / 2, cap, layer), fixed=fx),
                    dict(t('+', f(x1 - 3.0), y1 + 0.6, 1.2, layer), fixed=fx),
                    dict(t('\u2212', f(x2 - 3.0), y2 + 0.6, 1.2, layer), fixed=fx)]
    top += [dict(t('SmokeBreak v1.0', 60.0, 49.6, 0.8, T), fixed=False)]
    return top, bottom


def add_art(b, work):
    """Draw the art.  Fixed items stay exactly where they are drawn (a clash
    with a pad or a via is reported, not moved); the rest are nudged to the
    nearest free spot."""
    top, bottom = art_items()
    obs = {'T': _obstacles(b, 'T'), 'B': _obstacles(b, 'B')}
    copper = {'T': _obstacles(b, 'T', courtyards=False), 'B': obs['B']}
    res = B.art(top + bottom, work)
    out = []
    placed = []
    for it, r in zip(top + bottom, res):
        side = 'B' if it['layer'].startswith('B.') else 'T'
        x0, y0, x1, y1 = r['bounds']
        if side == 'B':                                # to board coordinates
            x0, x1 = B.W - x1, B.W - x0
        dx = dy = 0.0
        if it.get('fixed'):
            hits = _count((x0, y0, x1, y1), copper[side])
            if hits:
                print('  clash:', it.get('text', it['kind']), side, hits)
        else:
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
    ('battery plus', VBAT_AREA, [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]),
    ('fuse load side', F1_LOAD, [pcbnew.F_Cu]),
    ('sources', SOURCES, [pcbnew.F_Cu]),
    ('Q1 drain', Q1_DRAIN, [pcbnew.F_Cu]),
    ('Q2 drain', Q2_DRAIN, [pcbnew.F_Cu]),
    ('drone negative', NEG, [pcbnew.F_Cu, pcbnew.B_Cu]),
    ('battery minus', BATT_NEG, [pcbnew.F_Cu, pcbnew.B_Cu]),
    ('Q11 sources', Q11_SOURCES, [pcbnew.F_Cu]),
    ('shunt GND', SHUNT_GND, [pcbnew.F_Cu]),
]
# parts that belong inside a power area (their pads are its copper)
KEEPOUT_GUESTS = {'drone negative': ('RS1', 'J3', 'J4'), 'battery plus': ('F1', 'J1', 'J2'),
                  'fuse load side': ('F1',), 'battery minus': ('J1', 'J2', 'Q11'), 'Q11 sources': ('Q11',),
                  'shunt GND': ('RS1',), 'sources': ('Q1', 'Q2'), 'Q1 drain': ('Q1',), 'Q2 drain': ('Q2',)}


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
    print('  balance buses', balance_buses(b))
    import final
    final.gate_side_vias(b)
    j7 = final.pad_xy(b, 'J7', '2')                       # the display's ground pin, between signal pins
    B.track(b, [j7, (j7[0] - 1.2, j7[1])], 0.15, pcbnew.F_Cu, 'GND')
    B.via(b, j7[0] - 1.2, j7[1], 'GND', d=0.45, drill=0.2)
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
    B.set_stackup(OUT, inner_oz=1.0)
    B.write_rules(OUT)
    print('placed', len(fps), '->', OUT)
