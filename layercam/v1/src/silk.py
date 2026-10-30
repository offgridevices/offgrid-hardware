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
import pcb, brand

NAME = 'LayerCam'
# the revision, from this revision's folder name (v1 -> V1)
REV = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).upper()
CAP = 1.0
# boxes kept free of stitching vias for the artwork (stitch.py), board mm
ART = {'main': [(-6.5, 21.5, 6.5, 28.0)], 'usb': [(-13.6, 10.4, 7.4, 15.5)], 'ring': []}


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


def text(fam, s, cap=CAP):
    g, _ = brand.styled(fam, s, cap)
    return g


def draw(b):
    bd = pcb.BOARD
    if bd == 'main':
        import geometry as G
        top = Placer(b, 'T')
        # the bring-up pads: 5V on its own; the console and boot pads are a
        # row 1.6 mm apart with no room for a label at any one of them (even
        # a letter), so one legend names them left to right in their order
        x, y = pcb.xy(b.FindFootprintByReference('TP4').GetPosition())
        top.put(text('mono', '5V', 0.7), x, y - 1.4, search=2.0)
        row = sorted((pcb.xy(b.FindFootprintByReference(r).GetPosition()), l)
                     for r, l in (('TP1', 'TX'), ('TP2', 'RX'), ('TP3', 'G'), ('TP5', 'BOOT')))
        cx = sum(p[0] for p, _ in row) / len(row)
        cy = min(p[1] for p, _ in row)
        legend = ' '.join(l for _, l in row)
        if not any(top.put(text('mono', legend, h), cx, cy + dy, search=s, must=False)
                   for h in (0.6, 0.5) for dy, s in ((-1.5, 2.0), (-2.5, 4.0), (1.5, 6.0))):
            raise SystemExit('silk: no room for the %s legend' % legend)
        # the name where it fits on the back face (the SoC's band and the
        # heatsink take the middle): the first free spot of these
        name = brand.line([('sans', NAME), ('mono', REV)], 1.3)[0]
        for x, y in ((0.0, 23.2), (0.0, 27.2), (-11.0, 9.0), (11.0, 9.0), (-11.0, -6.0), (11.0, -12.0)):
            if top.put(name, x, y, search=5.0, must=False):
                break
        else:
            raise SystemExit('silk: no room for the name on the back face')
        top.put(brand.line([('mono', 'CERN-OHL-S-2.0'), ('sans', 'offgridevices')], 0.7)[0], 0.0, 26.0,
                search=4.0, must=False)
        bot = Placer(b, 'B')
        for ref, label in (('J4', 'Ring'), ('J3', 'IR-cut'), ('J5', 'Wi-Fi')):
            x, y = pcb.xy(b.FindFootprintByReference(ref).GetPosition())
            bot.put(text('sans', label, 0.8), x, y + 5.0, search=4.0, must=False)
        lk, _ = brand.lockup_mm(14.0)
        bot.put(lk, 0.0, 24.0, search=5.0, must=False)
    elif bd == 'ring':
        bot = Placer(b, 'B')
        bot.put(brand.line([('sans', NAME), ('mono', REV)], 0.9)[0], -11.0, -6.0, rot=0, search=5.0, must=False)
        bot.put(text('mono', 'IR 850', 0.8), 0.0, 13.0, search=4.0, must=False)
    elif bd == 'usb':
        bot = Placer(b, 'B')
        lk, _ = brand.lockup_mm(10.0)
        bot.put(lk, 2.2, 12.9, search=2.0)
        bot.put(brand.line([('sans', NAME), ('mono', REV)], 0.9)[0], -9.0, 12.9, search=2.0)
