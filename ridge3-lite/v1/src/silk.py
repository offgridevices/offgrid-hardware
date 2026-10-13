# -*- coding: utf-8 -*-
"""Silkscreen and artwork for the routed board.

Every label sits where it touches no pad, no hole, no grommet flange and
no other ink (artwork.SilkPlacer), set in the OffGrid brand faces as filled
outlines (brand.py): words in Instrument Sans 500, pad names and numerals
in JetBrains Mono 500.  White silk on the black mask; the flag adds ENIG
gold.

  TOP     pad names, battery polarity and rating, motor numbers, the
          front arrow, "Ridge 3 Lite" and the OffGrid mark
  BOTTOM  the ESC programming pads, the OffGrid lockup and the flag of
          the United States (flag.py), made of the board's three colours
"""
import math, os
import pcbnew
from shapely.geometry import Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb, brand, flag, layout, artwork

NAME = 'Ridge 3 Lite'
# the revision, from this revision's folder name (v1 -> V1), so a copy into
# v2/ prints V2 with no edit; a code, so brand mono, uppercase
REV = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).upper()


def _copper_free(b, side, extra=0.25):
    """Where the outer layer of `side` has nothing but ground: no pad, no
    via, no track of another net.  Ground vias and tracks may stay under the
    flag: every via is filled and capped, so in a mask window it plates flat
    with the stripe round it.  A shapely geometry in board-centre mm."""
    cu = pcbnew.F_Cu if side == 'T' else pcbnew.B_Cu
    blocks = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(cu) or p.GetDrillSize().x > 0:
                bb = p.GetBoundingBox()
                blocks.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                                  bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY).buffer(extra))
        crt = fp.GetCourtyard(pcbnew.F_CrtYd if side == 'T' else pcbnew.B_CrtYd)
        if crt.OutlineCount() and fp.IsFlipped() == (side == 'B'):
            bb = crt.BBox()
            blocks.append(box(bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                              bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY))
    for t in b.GetTracks():
        q = t.GetPosition()
        if t.GetNetname() == 'GND':
            continue
        if t.GetClass() == 'PCB_VIA':
            blocks.append(Point(q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY).buffer(t.GetWidth(cu) / 2e6 + extra))
        elif t.GetLayer() == cu:
            s, e = t.GetStart(), t.GetEnd()
            from shapely.geometry import LineString
            blocks.append(LineString([(s.x / 1e6 - pcb.CX, s.y / 1e6 - pcb.CY),
                                      (e.x / 1e6 - pcb.CX, e.y / 1e6 - pcb.CY)]).buffer(t.GetWidth() / 2e6 + extra))
    for z in b.Zones():
        if z.IsOnLayer(cu) and not z.GetIsRuleArea() and z.GetNetname() != 'GND':
            ol = z.Outline()
            for i in range(ol.OutlineCount()):
                o = ol.Outline(i)
                from shapely.geometry import Polygon
                blocks.append(Polygon([(o.CPoint(k).x / 1e6 - pcb.CX, o.CPoint(k).y / 1e6 - pcb.CY)
                                       for k in range(o.PointCount())]).buffer(extra))
    for sx in (-1, 1):
        for sy in (-1, 1):
            blocks.append(Point(sx * pcb.HOLE, sy * pcb.HOLE).buffer(pcb.HOLE_KEEPOUT_R))
    return pcb.board_polygon().buffer(-0.6).difference(unary_union(blocks))


FLAG_HOISTS = (6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0)
SUBDUED_HOISTS = (5.0, 4.5, 4.0, 3.75, 3.5, 3.25, 3.0, 2.75, 2.5)


def flag_spot(b, side, hoists=(7.0, 6.5, 6.0, 5.5), step=0.25):
    """The largest flag that fits on ground-only copper of `side`, and where:
    (hoist, x, y) or None."""
    free = _copper_free(b, side)
    import shapely
    shapely.prepare(free)
    for h in hoists:
        W = flag.B * h
        cands = []
        n = int(pcb.HALF / step)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x, y = i * step, j * step
                r = box(x - W / 2 - 0.3, y - h / 2 - 0.3, x + W / 2 + 0.3, y + h / 2 + 0.3)
                if free.contains(r):
                    cands.append((x * x + y * y, x, y))
        if cands:
            cands.sort()
            return h, cands[0][1], cands[0][2]
    return None


def add_flag(b, side, hoist, x, y):
    """The flag at (x, y), over its ground plate (board.py draws the plate
    and keeps vias and tracks out): mask windows for the gold stripes and
    stars, silk for the white stripes."""
    mirror = side == 'B'
    f = flag.placed(hoist, x, y, mirror=mirror)
    mask = pcbnew.F_Mask if side == 'T' else pcbnew.B_Mask
    silk = pcbnew.F_SilkS if side == 'T' else pcbnew.B_SilkS
    brand.add(b, f['gold'], mask)
    brand.add(b, f['silk'], silk)
    return f


def strip(b):
    """Remove the board-level silkscreen and mask artwork (the flag's
    windows included) so it can be laid out again; copper is untouched."""
    n = 0
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS, pcbnew.F_Mask, pcbnew.B_Mask):
            pcb.remove(b, d); n += 1
    return n


def draw(b, log=print):
    artwork.hide_fields(b)
    # ---------------------------------------------------------------- top
    top = artwork.SilkPlacer(b, 'T', brand=True, via_clear=0.05)
    F = layout.FLAG
    if F:
        side, spot = F['side'], (F['hoist'], F['x'], F['y'])
    else:
        # the largest flag the routed board's ground copper takes, top first
        side, spot = 'T', flag_spot(b, 'T', hoists=FLAG_HOISTS)
        if spot is None:
            side, spot = 'B', flag_spot(b, 'B', hoists=FLAG_HOISTS)
    flagged = None
    if spot:
        f = add_flag(b, side, *spot)
        flagged = (side, spot)
        if side == 'T':
            top.placed.append(affinity.translate(f['plate'], pcb.CX, pcb.CY))
        log('flag: hoist %.1f mm at (%.1f, %.1f), %s' % (spot[0], spot[1], spot[2], 'top' if side == 'T' else 'bottom'))
    else:
        log('flag: no ground plate for the gold flag; the subdued one goes in last')
    for ref, s in (('P_T2', 'T2'), ('P_R2', 'R2'), ('P_G', 'G'), ('P_5V', '5V'),
                   ('P_T1', 'T1'), ('P_R1', 'R1'), ('P_LED', 'LED'), ('P_BZ+', 'BZ+'), ('P_BZ-', 'BZ-')):
        top.label(ref, s, size=0.75, face='mono', smallest=0.55)
    top.label('P_BAT+', '+', size=1.6, face='mono', smallest=1.0)
    top.label('P_BAT-', '-', size=1.6, face='mono', smallest=1.0)
    bx, by = artwork.pad_xy(b, 'P_BAT+')
    top.text_near('2-4S', (bx - 2.0, by - 3.6), size=0.8, face='mono')
    for n in (1, 2, 3, 4):
        x, y = artwork.pad_xy(b, 'P_M%dB' % n)
        top.text_near(str(n), (x * 0.82, y * 0.82), size=1.3, face='mono', radius=3.0)
    top.text_near('BOOT', artwork.pad_xy(b, 'SW_BOOT'), size=0.6, face='sans', radius=3.5)
    top.shape_near(lambda x, y: artwork.arrow(b, x, y, length=3.2, width=0.25, head=0.6), (0.0, -9.0), radius=6.0)
    named = None
    for size, rot, radius in ((0.9, 0, 8.0), (0.8, 0, 16.0), (0.8, 90, 16.0), (0.7, 0, 16.0), (0.7, 90, 16.0)):
        named = top.text_near(NAME, (0.0, -11.0), size=size, face='sans', radius=radius, rot=rot)
        if named is not None:
            break
    # the revision beside the name (wherever the name went)
    revved = None
    if named is not None:
        revved = top.text_near(REV, named, size=0.7, face='mono', radius=6.0)
    m, clear = brand.mark_mm(2.6)
    top.geom(m, top.roomiest(need=1.6)[:400], clear=clear, vias=False, hull=True, quiet=True)
    # ------------------------------------------------------------- bottom
    bot = artwork.SilkPlacer(b, 'B', brand=True, via_clear=0.05)
    if flagged and flagged[0] == 'B':
        bot.placed.append(affinity.translate(f['plate'], pcb.CX, pcb.CY))
    for n in (1, 2, 3, 4):
        bot.label('TP_D%d' % n, 'D%d' % n, size=0.6, face='mono', smallest=0.45)
        bot.label('TP_C%d' % n, 'C%d' % n, size=0.6, face='mono', smallest=0.45)
    bot.label('TP_3V3', '3V3', size=0.6, face='mono', smallest=0.45)
    bot.label('TP_GND', 'G', size=0.6, face='mono', smallest=0.45)
    if named is None:
        for size in (0.8, 0.7):
            named = bot.text_near(NAME, (0.0, -11.0), size=size, face='sans', radius=16.0)
            if named is not None:
                break
    if revved is None:
        revved = bot.text_near(REV, named or (0.0, -11.0), size=0.6, face='mono', radius=16.0)
    log('revision: %s %s' % (REV, 'printed' if revved is not None else 'NOT PRINTED'))
    if not flagged:
        # no ground plate took the gold flag: the subdued one, in silk alone.
        # The board has one roomy spot left, mid-bottom: the flag takes it
        # and the brand goes where it fits as large as it can (a corner,
        # beside a mounting hole, on this board)
        flagged = _subdued(bot, 'B', SUBDUED_HOISTS)
        _lockup(bot, sizes=(9.0, 8.0, 7.0, 6.0, 5.5, 5.0, 4.5), mark=True, rots=(0, 90, 45, -45, 135, -135))
        if not flagged:
            flagged = _subdued(top, 'T', SUBDUED_HOISTS)
        if flagged:
            log('flag: subdued (silk only), hoist %.2f mm at (%.1f, %.1f), %s' % (flagged[1] + ('top' if flagged[0] == 'T' else 'bottom',)))
        else:
            log('flag: no room for the flag')
    else:
        _lockup(bot)
    return top, bot


def _subdued(placer, side, hoists):
    """The subdued flag, as large as it fits on `side`: (side, (hoist, x, y))."""
    for h in hoists:
        g = flag.placed(h, 0, 0, mirror=side == 'B', style='subdued')['silk']
        at = placer.geom(g, placer.roomiest(need=h / 2)[:800], clear=0.3, vias='fewest', margin=0.3, quiet=True)
        if at is not None:
            return (side, (h,) + tuple(at))
    return None


def _lockup(bot, sizes=(9.0, 7.0), mark=False, rots=(0,)):
    """The OffGrid lockup on the bottom, as large as it fits (or, with
    mark=True and no room for any lockup, the bare mark)."""
    for w in sizes:
        for rot in rots:
            lock, clear = brand.lockup_mm(w, mirror=True)
            if rot:
                # reading upwards, as seen from below
                lock = affinity.rotate(lock, -rot, origin=(0, 0))
            at = bot.geom(lock, bot.roomiest(need=w / 5)[:600], clear=clear, vias='fewest', quiet=True)
            if at is not None:
                print('   brand: lockup %.1f mm at (%.1f, %.1f), turned %d' % ((w,) + tuple(at) + (rot,)))
                return at
    if mark:
        for w in (3.0, 2.6, 2.2):
            m, clear = brand.mark_mm(w)
            at = bot.geom(affinity.scale(m, -1, 1, origin=(0, 0)), bot.roomiest(need=w / 2)[:600], clear=clear,
                          vias='fewest', hull=True, quiet=True)
            if at is not None:
                print('   brand: mark %.1f mm at (%.1f, %.1f)' % ((w,) + tuple(at)))
                return at
    print('   silk: no room for the brand')
    return None
