# -*- coding: utf-8 -*-
"""Silkscreen: labels and the OffGrid brand, as filled outlines in the
brand faces (brand.py): words in Instrument Sans 500, numbers and codes in
JetBrains Mono 500.  White silk.

  F (back, under the lid): the US flag over the OffGrid lockup, one badge
     centred on the board's middle line in the open band at the top; each
     test pad's name (the console row 5V G TX RX, the recovery row D- D+ G
     BOOT).  Nothing else: what each part is lives in the documentation.
  B (front, the lens side): the IR-cut lead's name, and the product and
     revision in one line (a board must say what it is, for repairs).

The licence asks only that people can find the source (CERN-OHL-S-2.0,
section 4): the documentation and the repository say it, not the board.

Every label is placed where it touches no pad, hole or mask opening (the
fab would clip it there), searched outwards from where it is meant to go.
"""
import os
import pcbnew
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb, brand

NAME = 'LayerCam Pro'
# the revision, from this revision's folder name (v1 -> V1)
# the revision, set here and nowhere else (docs/versioning.md): 1.0, printed V1.
# Never from the folder's name: a moved folder must not change the copper
REV = 'V1'
CAP = 1.0
# boxes kept free of stitching vias for the artwork (stitch.py), board mm
ART = {'main': [(-8.6, -27.2, 8.6, -12.2)]}


def strip(b):
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            pcb.remove(b, d)


def _blocked(b, side):
    cu = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
    crt = pcbnew.F_CrtYd if side == 'T' else pcbnew.B_CrtYd
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(cu) or p.GetDrillSize().x > 0:
                bb = p.GetBoundingBox()
                out.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                               bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY).buffer(0.2))
        c = fp.GetCourtyard(crt)
        if c.OutlineCount() and fp.GetReference()[0] != 'H':
            bb = c.BBox()
            out.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                           bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            out.append(Point(pcb.xy(t.GetPosition())).buffer(t.GetDrillValue() / 2e6 + 0.15))
    return unary_union(out)


class Placer:
    def __init__(self, b, side, extra=None):
        self.b, self.side = b, side
        self.layer = pcbnew.F_SilkS if side == 'T' else pcbnew.B_SilkS
        free = pcb.board_polygon().buffer(-0.5).difference(_blocked(b, side))
        if extra is not None:
            free = free.difference(extra)
        self.free = free
        self.used = []

    def put(self, g, x, y, anchor='c', rot=0, search=6.0, step=0.25, must=True, ok=None):
        """ok(x, y): an extra test of a spot (a label nearest its own pad)."""
        mirror = self.side == 'B'
        for r in [i * step for i in range(int(search / step) + 1)]:
            for dx, dy in ([(0, 0)] if r == 0 else
                           [(r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, r), (r, -r), (-r, -r)]):
                if ok is not None and not ok(x + dx, y + dy):
                    continue
                gg = brand.place(g, x + dx, y + dy, anchor, rot, mirror)
                if self.free.contains(gg.buffer(0.12)) and not any(u.intersects(gg.buffer(0.3)) for u in self.used):
                    self.used.append(gg)
                    brand.add(self.b, gg, self.layer)
                    return x + dx, y + dy
        if must:
            raise SystemExit('silk: no room for a label near (%.1f, %.1f)' % (x, y))
        return None


# The brand's type at label sizes draws strokes of 0.11-0.13 mm, under the
# fab's 0.15 mm silkscreen line: every letter is grown by INK so each stroke
# reaches it (same font, size and spacing, a hair heavier), and checked
# (text 0.8 mm mono / 1.0 mm sans or larger).
# The lockup and the flag are drawn heavier than that and left as they are.
INK = 0.025


def ink(g, what='text'):
    g = g.buffer(INK, quad_segs=4)
    thin = brand.thin_parts(g) / g.area
    if thin > 0.06:
        raise SystemExit('silk: %s has %.0f %% of its ink under %.2f mm' % (what, 100 * thin, brand.MIN_STROKE))
    return g


def text(fam, s, cap=CAP):
    g, _ = brand.styled(fam, s, cap)
    return ink(g, s)


# The badge: the US flag over the OffGrid lockup, centred on x = 0, in the
# open band above the lens.  Set exactly; if anything is in the way the
# build stops.  PCBWay's silkscreen (pcbway.com capabilities and silkscreen
# guide, 2 Nov 2026): 0.15 mm lines, 0.8 mm text, 0.25 mm knocked-out
# shapes.  Every piece here keeps 0.18 mm ink and 0.25 mm bare
# (brand.thin_parts, brand.thin_gaps), or the build stops: the flag at
# 8 mm of hoist with round stars (0.49 mm; the ink round the union's top
# row 0.19 mm), the lockup 12 mm across.
NAMES = {'main': 'LayerCam Pro'}
FLAG_HOIST = 8.0
BADGE_X = 0.0
FLAG_Y = -22.6            # the flag's centre
LOCKUP_W = 12.0
BADGE_GAP = 2.4           # flag to lockup
LABEL_CAP = 1.0           # test pad names: JetBrains Mono, 1.0 mm caps (PCBWay's floor 0.8)
# each test pad's name, set centred above it (or below: draw())
PAD_NAMES = {'TP4': '5V', 'TP3': 'G', 'TP1': 'TX', 'TP2': 'RX',
             'TP6': 'D-', 'TP7': 'D+', 'TP8': 'G', 'TP5': 'BOOT'}
PAD_LABEL_DY = -1.45      # pad centre to the name's centre (above the 1.0 mm pad)
NAME_B = (0.0, -21.0)     # front face: the product and revision, centred above the lens


def _fits(placer, g):
    return placer.free.contains(g.buffer(0.12)) and not any(u.intersects(g.buffer(0.3)) for u in placer.used)


def _set(placer, g, what):
    """Put an artwork already in board coordinates, exactly there."""
    # (a few per cent are corners and serifs, which the ink only rounds)
    if brand.thin_parts(g) > 0.06 * g.area or brand.thin_gaps(g) > 0.05 * g.area:
        raise SystemExit('silk: the %s has ink under %.2f mm or gaps under %.2f mm'
                         % (what, brand.MIN_STROKE, brand.MIN_GAP))
    if not _fits(placer, g):
        raise SystemExit('silk: the %s does not fit where it is set' % what)
    placer.used.append(g)
    brand.add(placer.b, g, placer.layer)


def draw(b):
    top = Placer(b, 'T')
    flag = brand.place(brand.flag_mm(FLAG_HOIST, round_stars=True), BADGE_X, FLAG_Y)
    _set(top, flag, 'flag')
    lk, _ = brand.lockup_mm(LOCKUP_W)
    lb = lk.bounds
    _set(top, brand.place(lk, BADGE_X, flag.bounds[3] + BADGE_GAP + (lb[3] - lb[1]) / 2), 'lockup')
    # each row of pads has its names on one side (the side more of them fit
    # on); a name a part's pad would clip there goes on the other
    rows = {}
    for ref, label in PAD_NAMES.items():
        x, y = pcb.xy(b.FindFootprintByReference(ref).GetPosition())
        rows.setdefault(round(y, 1), []).append((ref, label, x, y))
    for _, row in sorted(rows.items()):
        def at(label, x, y, dy):
            return brand.place(text('mono', label, LABEL_CAP), x, y + dy)
        side = max((PAD_LABEL_DY, -PAD_LABEL_DY),
                   key=lambda dy: sum(_fits(top, at(l, x, y, dy)) for _, l, x, y in row))
        for ref, label, x, y in row:
            # the row's side; a name a part's pad would clip there takes the other
            g = next((g for g in (at(label, x, y, side), at(label, x, y, -side)) if _fits(top, g)),
                     at(label, x, y, side))
            _set(top, g, 'name of ' + ref)
    bot = Placer(b, 'B')
    x, y = pcb.xy(b.FindFootprintByReference('J3').GetPosition())
    # by the IR-cut lead's socket, clear of its body: across it, else
    # upright beside it on either side
    ir = text('sans', 'IR-cut', 1.2)
    import placer
    cy = placer.courtyard(b.FindFootprintByReference('J3'), 'B').buffer(0.4)
    clear = lambda gx, gy, r: not cy.intersects(brand.place(ir, gx, gy, 'c', r, True))
    bot.put(ir, x + 2.5, y - 4.0, search=4.0, must=False, ok=lambda px, py: clear(px, py, 0)) or \
        bot.put(ir, x + 4.0, y, rot=90, search=2.0, must=False, ok=lambda px, py: clear(px, py, 90)) or \
        bot.put(ir, x - 4.75, y, rot=90, search=4.0, ok=lambda px, py: clear(px, py, 90))
    x, y = NAME_B
    # centred: searched up and down the middle line only
    bot.put(ink(brand.line([('sans', NAMES['main']), ('mono', REV)], 1.2)[0]), x, y, search=3.0,
            ok=lambda px, py: abs(px - x) < 1e-6)
