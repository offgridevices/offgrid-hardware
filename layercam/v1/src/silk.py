# -*- coding: utf-8 -*-
"""Silkscreen: labels and the OffGrid brand, as filled outlines in the
brand faces (brand.py): words in Instrument Sans 500, numbers and codes in
JetBrains Mono 500.  White silk.

  main  F (back, under the lid's vents): "LayerCam" and the revision,
        the lockup, the test pads, the licence.
        B (front): the connectors' names.
  ring  B: the name and revision (F rests on the housing).
  usb   B (the face away from the parts): the lockup, the name and the
        revision, along the bottom edge.

Every label is placed where it touches no pad, hole or mask opening (the
fab would clip it there), searched outwards from where it is meant to go.
"""
import os
import pcbnew
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb, brand

NAME = 'LayerCam'
# the revision, from this revision's folder name (v1 -> V1)
REV = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).upper()
CAP = 1.0
# boxes kept free of stitching vias for the artwork (stitch.py), board mm
ART = {'main': [(-6.5, 21.5, 6.5, 28.0)], 'usb': [(-13.6, 9.6, 7.4, 15.8)], 'ring': []}


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
        raise SystemExit('silk: %s has %.0f %% of its ink under 0.15 mm' % (what, 100 * thin))
    return g


def text(fam, s, cap=CAP):
    g, _ = brand.styled(fam, s, cap)
    return ink(g, s)


# The badges: the OffGrid lockup, the board's name and its revision, and the
# US flag where there is room for one at 5.26 mm of hoist (stars 0.32 mm,
# the smallest the silkscreen keeps).  Each is set at an exact place on the
# board's own axes; if anything there is in the way the build stops.  Text
# 1.0 mm or larger and the lockup 7.7 mm or wider keep the strokes at the
# fab's 0.15 mm (brand.thin_parts).
# every board 'LayerCam – <board>' and its revision (the USB board's block
# is too narrow for one line: the line break stands for the dash)
NAMES = {'main': 'LayerCam – Main', 'ring': 'LayerCam – Ring', 'usb': 'LayerCam'}
FLAG_HOIST = 5.26
# main, back face, centred on the board's centre line over the lens window,
# threaded between its vias: the lockup, and the name below it
MAIN_LOCKUP = (0.0, -14.6, 7.7)
MAIN_NAME = (0.0, -11.75, 1.0)
# ring, back face: the lockup level and centred at the bottom, the name on
# an arc beneath it, its baseline 15.45 mm from the centre
RING_LOCKUP = (0.0, 12.15, 8.0)
RING_ARC = (15.45, 1.0)
# USB board, back face (no parts): the flag, then the lockup over the name and
# revision, the two the flag's height, the pair centred on the board in the
# band below the CC resistors (kept free of vias, layout_usb.ART)
USB_BAND_Y = 12.7
USB_LOCKUP_W = 7.7
USB_GAP = 0.8


def _set(placer, g, what):
    """Put an artwork already in board coordinates, exactly there."""
    if not placer.free.contains(g.buffer(0.12)) or any(u.intersects(g.buffer(0.3)) for u in placer.used):
        raise SystemExit('silk: the %s does not fit where it is set' % what)
    placer.used.append(g)
    brand.add(placer.b, g, placer.layer)


def _block(rows, lockup_w, cap, gap):
    """The lockup over rows of type, each centred: geometry with its box
    centred on the origin (y down, as read)."""
    lk, _ = brand.lockup_mm(lockup_w)
    lb = lk.bounds
    parts = [affinity.translate(lk, -(lb[0] + lb[2]) / 2, -lb[1])]
    y = lb[3] - lb[1]
    for segs in rows:
        t, _ = brand.line(segs, cap)
        t = ink(t)
        tb = t.bounds
        y += gap
        # rows on a cap-height grid: the baseline a cap below the gap
        parts.append(affinity.translate(t, -(tb[0] + tb[2]) / 2, y + cap))
        y += cap
    g = unary_union(parts)
    b0 = g.bounds
    return affinity.translate(g, -(b0[0] + b0[2]) / 2, -(b0[1] + b0[3]) / 2)


def draw(b):
    bd = pcb.BOARD
    if bd == 'main':
        top = Placer(b, 'T')
        x, y, cap = MAIN_NAME
        _set(top, brand.place(ink(brand.line([('sans', NAMES['main']), ('mono', REV)], cap)[0]), x, y), 'name')
        x, y, w = MAIN_LOCKUP
        _set(top, brand.place(brand.lockup_mm(w)[0], x, y), 'lockup')
        # the bring-up pads: 5V on its own; the console and boot pads are a
        # row 1.6 mm apart with no room for a label at any one of them (even
        # a letter), so one legend names them left to right in their order
        x, y = pcb.xy(b.FindFootprintByReference('TP4').GetPosition())
        if not any(top.put(text('mono', '5V', 0.8), x + dx, y + dy, search=2.0, must=False)
                   for dx, dy in ((-1.7, -1.4), (0, -1.4), (1.6, 0), (-1.6, 0), (0, 1.4))):
            raise SystemExit('silk: no room for the 5V label')
        row = sorted((pcb.xy(b.FindFootprintByReference(r).GetPosition()), l)
                     for r, l in (('TP1', 'TX'), ('TP2', 'RX'), ('TP3', 'G'), ('TP5', 'BOOT')))
        cx = sum(p[0] for p, _ in row) / len(row)
        cy = min(p[1] for p, _ in row)
        legend = ' '.join(l for _, l in row)
        if not any(top.put(text('mono', legend, 0.8), cx, cy + dy, search=s, must=False)
                   for dy, s in ((-1.5, 2.0), (-2.5, 4.0), (1.5, 6.0))):
            raise SystemExit('silk: no room for the %s legend' % legend)
        top.put(ink(brand.line([('mono', 'CERN-OHL-S-2.0'), ('sans', 'offgridevices')], 1.0)[0]), 0.0, 26.0,
                search=4.0, must=False)
        bot = Placer(b, 'B')
        for ref, label in (('J4', 'Ring'), ('J3', 'IR-cut'), ('J5', 'Wi-Fi')):
            x, y = pcb.xy(b.FindFootprintByReference(ref).GetPosition())
            bot.put(text('sans', label, 1.0), x, y + 5.0, search=4.0, must=False)
    elif bd == 'ring':
        bot = Placer(b, 'B')
        x, y, w = RING_LOCKUP
        _set(bot, brand.place(brand.lockup_mm(w)[0], x, y, mirror=True), 'lockup')
        r, cap = RING_ARC
        g = ink(brand.arc_line([('sans', NAMES['ring']), ('mono', REV)], cap, r))
        _set(bot, affinity.scale(g, -1, 1, origin=(0, 0)), 'name')          # read from the back
    elif bd == 'usb':
        import geometry as G
        bot = Placer(b, 'B')
        x0, _, x1, _ = G.USB_BOX
        fl = brand.flag_mm(FLAG_HOIST)
        rows = [[('sans', NAMES['usb'])], [('mono', 'USB-C'), ('mono', REV)]]
        # the row gap that makes the block exactly the flag's height
        lo, hi = 0.0, 1.5
        for _ in range(30):
            gap = (lo + hi) / 2
            blk = _block(rows, USB_LOCKUP_W, 1.0, gap)
            if blk.bounds[3] - blk.bounds[1] < fl.bounds[3] - fl.bounds[1]:
                lo = gap
            else:
                hi = gap
        fw, bw = fl.bounds[2] - fl.bounds[0], blk.bounds[2] - blk.bounds[0]
        total = fw + USB_GAP + bw
        # as read from the back (x mirrored): the flag on the left
        cxv = -(x0 + x1) / 2                       # the board's centre in the back view
        fl_v = affinity.translate(fl, cxv - total / 2 + fw / 2, USB_BAND_Y)
        blk_v = affinity.translate(blk, cxv + total / 2 - bw / 2, USB_BAND_Y)
        _set(bot, affinity.scale(fl_v, -1, 1, origin=(0, 0)), 'flag')
        _set(bot, affinity.scale(blk_v, -1, 1, origin=(0, 0)), 'badge')
