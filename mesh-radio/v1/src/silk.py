# -*- coding: utf-8 -*-
"""Silkscreen and artwork for the routed board.

Every label sits where it touches no pad, no hole and no other ink
(artwork.SilkPlacer), set in the OffGrid brand faces as filled outlines
(brand.py): words in Instrument Sans 500, port names and numerals in
JetBrains Mono 500.  White silk on the black mask.

  TOP     the board name and revision, the OffGrid mark, the buttons and
          the LoRa antenna port
  BOTTOM  the plugs (battery with its + pin, solar, drone, GPS), the
          OffGrid lockup and the subdued flag of the United States
          (flag.py, silk only)
"""
import os
import pcbnew
from shapely import affinity
import pcb, brand, flag, artwork

NAME = 'Mesh Radio'
# the revision, from this revision's folder name (v1 -> V1), so a copy into
# v2/ prints V2 with no edit; a code, so brand mono, uppercase
REV = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).upper()
SUBDUED_HOISTS = (4.5, 4.0, 3.75, 3.5, 3.25, 3.0, 2.75, 2.5)


def _ref(b, value):
    """The reference of the one footprint whose value is `value`."""
    m = [fp.GetReference() for fp in b.GetFootprints() if fp.GetValue() == value]
    if len(m) != 1:
        raise KeyError('%s: %d footprints' % (value, len(m)))
    return m[0]


def _refs(b, value):
    return sorted(fp.GetReference() for fp in b.GetFootprints() if fp.GetValue() == value)


def strip(b):
    """Remove the board-level silkscreen so it can be laid out again;
    copper is untouched."""
    n = 0
    for d in list(b.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            pcb.remove(b, d); n += 1
    return n


def draw(b, comps, log=print):
    """comps: circuit.build(), to find parts by what they are."""
    artwork.hide_fields(b)
    by = lambda part, note=None: [c.ref for c in comps if c.part == part and (note is None or c.note == note)][0]
    # ---------------------------------------------------------------- top
    top = artwork.SilkPlacer(b, 'T', brand=True, via_clear=0.05)
    top.label(by('SKRP', 'reset'), 'RST', size=0.7, face='mono', smallest=0.5)
    top.label(by('SKRP', 'user'), 'USR', size=0.7, face='mono', smallest=0.5)
    top.label(by('UFL'), 'LORA', size=0.7, face='mono', smallest=0.5)
    named = None
    for size, radius in ((1.0, 10.0), (0.9, 30.0), (0.8, 30.0), (0.7, 30.0)):
        named = top.text_near(NAME, (0.0, -pcb.HY + 1.6), size=size, face='sans', radius=radius)
        if named is not None:
            break
    revved = None
    if named is not None:
        revved = top.text_near(REV, named, size=0.7, face='mono', radius=8.0)
    m, clear = brand.mark_mm(2.6)
    top.geom(m, top.roomiest(need=1.6)[:400], clear=clear, vias=False, hull=True, quiet=True)
    # ------------------------------------------------------------- bottom
    bot = artwork.SilkPlacer(b, 'B', brand=True, via_clear=0.05)
    bat = by('JST_PH2')
    # the battery's + pin, large: a standard LiPo (Adafruit/SparkFun JST-PH,
    # red lead on pin 1) plugs in this way round
    bot.label(bat, '+', size=1.6, face='mono', smallest=1.0, pad='1')
    for part, s in (('JST_PH2', 'BAT'), ('JST_SH2', 'SOLAR'), ('JST_GH6', 'DRONE'), ('JST_SH6', 'GPS')):
        bot.label(by(part), s, size=0.7, face='mono', smallest=0.5)
    if named is None:
        for size in (0.8, 0.7):
            named = bot.text_near(NAME, (0.0, pcb.HY - 1.6), size=size, face='sans', radius=30.0)
            if named is not None:
                break
    if revved is None:
        revved = bot.text_near(REV, named or (0.0, pcb.HY - 1.6), size=0.6, face='mono', radius=30.0)
    log('revision: %s %s' % (REV, 'printed' if revved is not None else 'NOT PRINTED'))
    if revved is None:
        raise SystemExit('silk: no room for the revision %r on either side' % REV)
    _lockup(bot, sizes=(9.0, 8.0, 7.0, 6.0, 5.0), mark=True, rots=(0,), log=log)
    flagged = _subdued(bot, 'B', SUBDUED_HOISTS) or _subdued(top, 'T', SUBDUED_HOISTS)
    log('flag: %s' % ('subdued (silk), hoist %.2f mm at (%.1f, %.1f), %s'
                      % (flagged[1] + ('top' if flagged[0] == 'T' else 'bottom',)) if flagged else 'no room'))
    return top, bot


def _subdued(placer, side, hoists):
    """The subdued flag, as large as it fits on `side`: (side, (hoist, x, y))."""
    for h in hoists:
        g = flag.placed(h, 0, 0, mirror=side == 'B', style='subdued')['silk']
        at = placer.geom(g, placer.roomiest(need=h / 2)[:800], clear=0.3, vias='fewest', margin=0.3, quiet=True)
        if at is not None:
            return (side, (h,) + tuple(at))
    return None


def _lockup(bot, sizes, mark=False, rots=(0,), log=print):
    """The OffGrid lockup on the bottom, as large as it fits (or, with
    mark=True and no room for any lockup, the bare mark)."""
    for w in sizes:
        for rot in rots:
            lock, clear = brand.lockup_mm(w, mirror=True)
            if rot:
                lock = affinity.rotate(lock, -rot, origin=(0, 0))
            at = bot.geom(lock, bot.roomiest(need=w / 5)[:600], clear=clear, vias='fewest', quiet=True)
            if at is not None:
                log('brand: lockup %.1f mm at (%.1f, %.1f)' % ((w,) + tuple(at)))
                return at
    if mark:
        for w in (3.0, 2.6, 2.2):
            m, clear = brand.mark_mm(w)
            at = bot.geom(affinity.scale(m, -1, 1, origin=(0, 0)), bot.roomiest(need=w / 2)[:600], clear=clear,
                          vias='fewest', hull=True, quiet=True)
            if at is not None:
                log('brand: mark %.1f mm at (%.1f, %.1f)' % ((w,) + tuple(at)))
                return at
    log('silk: no room for the brand')
    return None
