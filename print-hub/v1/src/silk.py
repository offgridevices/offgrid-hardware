# -*- coding: utf-8 -*-
"""Silkscreen: labels and the OffGrid brand, as filled outlines in the
brand faces (brand.py): words in Instrument Sans 500, numbers and codes in
JetBrains Mono 500.  White silk on the black mask.

  TOP     the port numbers by each port's LED, POWER IN / DATA, the
          buttons, the test pads, "Print Hub" with its revision, and the
          OffGrid mark
  BOTTOM  the OffGrid lockup, what to plug in, the licence

Every label is placed where it touches no pad, hole or mask opening (the
fab would clip it there), searched outwards from where it is meant to go.
"""
import os
import pcbnew
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb, brand, layout

NAME = 'Print Hub'
# the revision, from this revision's folder name (v1 -> V1): a copy into
# v2/ prints V2 with no edit
REV = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).upper()
CAP = 1.2              # cap height of the labels, mm
# where the big artwork goes, kept free of stitching vias (stitch.py):
# (x0, y0, x1, y1), board mm.  Top: the title and the mark, in the band
# between the logic and the ports.  Bottom: the lockup and the notes.
ART = [(-14.0, -9.5, 14.0, 1.0), (-22.0, -11.0, 22.0, 13.0)]


def strip(b):
    """Remove every silkscreen drawing this module made (copper untouched)."""
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            pcb.remove(b, d)


def _blocked(b, side):
    cu = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(cu) or p.GetDrillSize().x > 0:
                bb = p.GetBoundingBox()
                out.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                               bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY).buffer(0.2))
        if side == 'T':
            # the parts' bodies too: ink under a part is never seen
            c = fp.GetCourtyard(pcbnew.F_CrtYd)
            if c.OutlineCount() and fp.GetReference()[0] not in 'H':
                bb = c.BBox()
                out.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                               bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            # vias are tented: ink may cross the ring, not the hole
            out.append(Point(pcb.xy(t.GetPosition())).buffer(t.GetDrillValue() / 2e6 + 0.15))
    return unary_union(out)


class Placer:
    def __init__(self, b, side):
        self.b, self.side = b, side
        self.layer = pcbnew.F_SilkS if side == 'T' else pcbnew.B_SilkS
        self.free = pcb.board_polygon().buffer(-0.6).difference(_blocked(b, side))
        self.used = []

    def put(self, g, x, y, anchor='c', rot=0, search=6.0, step=0.25):
        """Place g (baseline at y 0) near (x, y); returns where, or raises."""
        mirror = self.side == 'B'
        for r in [i * step for i in range(int(search / step) + 1)]:
            for dx, dy in ([(0, 0)] if r == 0 else
                           [(r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, r), (r, -r), (-r, -r)]):
                gg = brand.place(g, x + dx, y + dy, anchor, rot, mirror)
                if self.free.contains(gg.buffer(0.15)) and not any(u.intersects(gg.buffer(0.3)) for u in self.used):
                    self.used.append(gg)
                    brand.add(self.b, gg, self.layer)
                    return x + dx, y + dy
        raise SystemExit('silk: no room for a label near (%.1f, %.1f)' % (x, y))


def text(fam, s, cap=CAP):
    g, _ = brand.styled(fam, s, cap)
    return g


def draw(b):
    top = Placer(b, 'T')
    # each port's number, left of its LED
    for i, x in enumerate(layout.PORT_X):
        top.put(text('mono', str(i + 1), 1.8), x + 2.9, layout.USBA_Y - 4.5)
    jy = layout.USBC_Y + 4.0
    top.put(brand.line([('sans', 'Power in'), ('mono', 'PD 9V')], CAP)[0], layout.J1_X, jy + 1.6)
    top.put(text('sans', 'Data'), layout.J2_X, jy + 1.6)
    for ref, label in (('SW1', 'Reset'), ('SW2', 'Boot')):
        x, y = pcb.xy(b.FindFootprintByReference(ref).GetPosition())
        top.put(text('sans', label), x - 4.6, y, anchor='r')
    for ref, label in (('TP1', 'TX'), ('TP2', 'RX'), ('TP3', 'GND'), ('TP4', '5V')):
        x, y = pcb.xy(b.FindFootprintByReference(ref).GetPosition())
        top.put(text('mono', label, 0.9), x, y + 1.9)
    title = brand.line([('sans', NAME), ('mono', REV)], 2.4)[0]
    top.put(title, 0.0, -1.5)
    mk, clear = brand.mark_mm(5.0)
    top.put(affinity.translate(mk, 0, 0), 0.0, -6.5)

    bot = Placer(b, 'B')
    lk, _ = brand.lockup_mm(36.0)
    bot.put(lk, 0.0, -6.0)
    bot.put(brand.line([('sans', NAME), ('mono', REV)], 2.4)[0], 0.0, 1.0)
    bot.put(text('sans', 'Power: a USB-C PD charger, 30 W or more'), 0.0, 5.5)
    bot.put(text('sans', 'Data: the print server (USB) or Wi-Fi'), 0.0, 8.0)
    bot.put(brand.line([('mono', 'CERN-OHL-S-2.0'), ('sans', 'offgridevices')], 1.0)[0], 0.0, 11.5)
    return top, bot
