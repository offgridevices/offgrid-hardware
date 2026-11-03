# -*- coding: utf-8 -*-
"""Silkscreen and artwork for the routed board.

Every label sits where it touches no pad, no hole and no other ink
(artwork.SilkPlacer), set in the OffGrid brand faces as filled outlines
(brand.py): words in Instrument Sans 500, port names and numerals in
JetBrains Mono 500.  White silk on the black mask.

  TOP     the board name and revision, the OffGrid mark, the controls
          (USER and RESET buttons, POWER switch: each framed and named)
          and the LoRa antenna port
  BOTTOM  the plugs (battery with its + pin, solar, drone, GPS, display /
          I2C), the OffGrid lockup and the subdued flag of the
          United States
          (flag.py, silk only)
"""
import os
import pcbnew
from shapely import affinity
import pcb, brand, flag, artwork, parts

NAME = 'Mesh Radio'
# the revision, from this revision's folder name (v1 -> V1), so a copy into
# v2/ prints V2 with no edit; a code, so brand mono, uppercase
REV = 'V1'          # revision 1.0 (README, Revisions); set here, not from the folder's name
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
    """comps: circuit.build(), to find parts by what they are.  Ink stays
    off part bodies (courtyards less their 0.10 mm margin): under a part it
    cannot be read."""
    artwork.hide_fields(b)
    # parts the assembler does not fit (the expansion header) have no body
    unfitted = {c.ref for c in comps if c.part in parts.PARTS
                and (not parts.PARTS[c.part].get('assembled', True) or parts.PARTS[c.part].get('dnp'))}
    by = lambda part, note=None: [c.ref for c in comps if c.part == part and (note is None or c.note == note)][0]
    # ---------------------------------------------------------------- top
    top = artwork.SilkPlacer(b, 'T', brand=True, via_clear=0.05, bodies=True, body_margin=0.10, no_body=unfitted)
    # the controls (owner, 2 Nov 2026: say exactly which does what): each
    # button and the power switch framed, its name in full beside the frame
    for ref, word in ((by('SKRP', 'user'), 'USER'), (by('SKRP', 'reset'), 'RESET'), (by('SLIDE'), 'POWER')):
        if _control(top, b, ref, word) is None:
            raise SystemExit('silk: no room to label %s (%s)' % (word, ref))
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
    bot = artwork.SilkPlacer(b, 'B', brand=True, via_clear=0.05, bodies=True, body_margin=0.10, no_body=unfitted)
    bat = by('JST_PH2')
    # the battery's + pin, large: a standard LiPo (Adafruit/SparkFun JST-PH,
    # red lead on pin 1) plugs in this way round
    bot.label(bat, '+', size=1.6, face='mono', smallest=1.0, pad='1')
    for part, s in (('JST_PH2', 'BAT'), ('JST_SH2', 'SOLAR'), ('JST_GH6', 'DRONE'), ('JST_SH6', 'GPS'),
                    ('JST_SH10', 'DISP/I2C')):
        if bot.label(by(part), s, size=0.7, face='mono', smallest=0.5) is None:
            # (3 Nov: the battery and display plugs' names found no spot
            # beside the plug) the nearest free spot round the plug instead
            q = b.FindFootprintByReference(by(part)).GetPosition()
            at = None
            for sz in (0.7, 0.6, 0.5):
                at = bot.text_near(s, (q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY), size=sz, face='mono', radius=6.0)
                if at is not None:
                    log('plug name %s at (%.1f, %.1f), %.1f mm' % (s, at[0], at[1], sz))
                    break
            if at is None:
                raise SystemExit('silk: no room for the plug name %r' % s)
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


def _control(placer, b, ref, word, margin=0.3, width=0.15, sizes=(0.8, 0.7, 0.6)):
    """Frame a control (button, switch) in silk round its body, open on any
    side the board edge cuts off, and set its name beside the frame, on
    the board's inner side first.  Returns the label's spot or None."""
    from shapely.geometry import box
    fp = b.FindFootprintByReference(ref)
    crt = fp.GetCourtyard(pcbnew.F_CrtYd if placer.side == 'T' else pcbnew.B_CrtYd).BBox()
    x0, y0 = crt.GetLeft() / 1e6 - 0.10, crt.GetTop() / 1e6 - 0.10        # the courtyard less its 0.10 margin
    x1, y1 = crt.GetRight() / 1e6 + 0.10, crt.GetBottom() / 1e6 + 0.10
    frame = None
    for m in (margin, margin - 0.1, margin - 0.2, margin + 0.15):
        bx = box(x0 - m, y0 - m, x1 + m, y1 + m)
        # the ring, cut off where the board edge takes it (open on that side)
        g = bx.exterior.buffer(width / 2, cap_style='square', join_style='mitre').intersection(
            placer.inside.buffer(-0.01))
        if g.is_empty:
            continue
        if placer._fits(g):
            frame, fb = g, bx
            break
    if frame is None:
        print('   silk: no room for the frame round %s' % ref)
        fb = box(x0, y0, x1, y1)
    else:
        placer._add_geom(frame)
        placer.placed.append(frame)
    # the name: above / below the frame (towards the board's middle first), then beside it
    cx, cy = (fb.bounds[0] + fb.bounds[2]) / 2 - pcb.CX, (fb.bounds[1] + fb.bounds[3]) / 2 - pcb.CY
    top_y, bot_y = fb.bounds[1] - pcb.CY, fb.bounds[3] - pcb.CY
    inward = -1 if cy > 0 else 1
    for sz in sizes:
        near = top_y - 0.25 - sz / 2 if inward < 0 else bot_y + 0.25 + sz / 2
        far = bot_y + 0.25 + sz / 2 if inward < 0 else top_y - 0.25 - sz / 2
        spots = [(cx + dx, near, 0, None) for dx in (0, 0.3, -0.3, 0.6, -0.6)]
        spots += [(cx + dx, far, 0, None) for dx in (0, 0.3, -0.3)]
        rx, lx = fb.bounds[2] - pcb.CX + 0.3, fb.bounds[0] - pcb.CX - 0.3
        spots += [(rx, cy + dy, 0, 'left') for dy in (0, 0.3, -0.3)] + [(lx, cy + dy, 0, 'right') for dy in (0, 0.3, -0.3)]
        at = placer.text(word, spots, size=sz, face='mono')
        if at is not None:
            return at
    return placer.text_near(word, (cx, cy), size=sizes[-1], radius=4.0, face='mono')


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
