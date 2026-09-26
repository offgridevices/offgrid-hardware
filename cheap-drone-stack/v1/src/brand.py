# -*- coding: utf-8 -*-
"""OffGrid brand artwork for the silkscreen, as filled outlines.

Everything here comes from the brand hand-off (offgrid-brand, v3.2):

  mark     offgrid-mark-bone.svg, the reversed Bone mark for dark planes:
           arc  M124.5 55.4 A58 58 0 1 1 75.5 55.4, stroke 22, round caps
           node circle r 17 at (100, 40), in a 200 x 200 box
  lockup   offgrid-wordmark-horizontal.svg, 800 x 200: mark at translate(20 12),
           "OffGrid" in Instrument Sans 600, size 92, letter-spacing -3,
           baseline at x 240 y 128
  type     tokens.json: labels in Instrument Sans 500, tracking 0.01 em
           (.og-label), sentence case, never bold; JetBrains Mono 500 for
           numerals, codes and serials only, uppercase, tracking 0.06 em;
           600 is the wordmark's alone
  colour   Pitch ground (matte black solder mask), Bone type and mark
           (white silkscreen).  No Ember: silkscreen has one colour.

Text is shaped with HarfBuzz (kerning included) from the variable fonts in
../fonts, so a board rebuilt anywhere gets the same outlines.  The glyphs
become KiCad polygons: the Gerbers carry the exact artwork, no font needed.
"""
import math, os
from functools import lru_cache
import pcbnew
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union
from shapely import affinity
import pcb

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
SANS = os.path.join(FONTS, 'InstrumentSans-VariableFont.ttf')
MONO = os.path.join(FONTS, 'JetBrainsMono-VariableFont.ttf')

# the lockup, in its own 800 x 200 units
MARK_AT = (20.0, 12.0)
WORD = dict(x=240.0, y=128.0, size=92.0, tracking=-3.0, weight=600)
NODE_R = 17.0                     # clear space round the mark = 1 x node radius

# silkscreen floor (JLCPCB and PCBWay): 0.15 mm lines
MIN_STROKE = 0.15


# ---------------------------------------------------------------- the mark
def mark(steps=96):
    """The Beacon Ring in its 200-unit box, y down (SVG coordinates)."""
    x0, y0, x1, y1, r = 124.5, 55.4, 75.5, 55.4, 58.0
    # centre of the large, clockwise (sweep 1) arc through both end points
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    h = math.sqrt(r * r - ((x1 - x0) / 2) ** 2)
    cx, cy = mx, my + h
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    if a1 <= a0:
        a1 += 2 * math.pi          # clockwise on screen = increasing angle with y down
    pts = [(cx + r * math.cos(a0 + (a1 - a0) * k / steps), cy + r * math.sin(a0 + (a1 - a0) * k / steps))
           for k in range(steps + 1)]
    ring = LineString(pts).buffer(11.0, quad_segs=24, cap_style='round')
    node = Point(100.0, 40.0).buffer(NODE_R, quad_segs=24)
    return unary_union([ring, node])


# ---------------------------------------------------------------- type
class Face:
    """One font at one weight, shaped by HarfBuzz."""
    def __init__(self, path, weight, width=None):
        import uharfbuzz as hb
        self.hb = hb
        self.path, self.weight = path, weight
        blob = hb.Blob.from_file_path(path)
        self.face = hb.Face(blob)
        self.font = hb.Font(self.face)
        var = {'wght': weight}
        if width is not None:
            var['wdth'] = width
        self.font.set_variations(var)
        self.upem = self.face.upem
        from fontTools.ttLib import TTFont
        self.cap = TTFont(path)['OS/2'].sCapHeight
        self._glyphs = {}

    def _glyph(self, gid):
        if gid not in self._glyphs:
            pen = _Pen()
            self.font.draw_glyph_with_pen(gid, pen)
            self._glyphs[gid] = pen.shape()
        return self._glyphs[gid]

    def outline(self, s, size, tracking=0.0, liga=True):
        """Shaped text in font-size units scaled to `size` (the em), y down,
        baseline at y 0, starting at x 0.  Returns (geometry, advance)."""
        hb = self.hb
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {'liga': liga, 'kern': True})
        k = size / self.upem
        x = 0.0
        parts = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            g = self._glyph(info.codepoint)
            if not g.is_empty:
                g = affinity.affine_transform(g, [k, 0, 0, -k, x + pos.x_offset * k, -pos.y_offset * k])
                parts.append(g)
            x += pos.x_advance * k + tracking
        return unary_union(parts), x - tracking

    def text(self, s, cap, tracking_em=0.0):
        """Text whose capital letters are `cap` mm tall.  Returns
        (geometry in mm, y down, baseline 0, x from 0; advance in mm)."""
        size = cap * self.upem / self.cap
        return self.outline(s, size, tracking=tracking_em * size, liga=tracking_em == 0)


class _Pen:
    """Flattens a glyph and fills it by the non-zero rule."""
    def __init__(self, steps=8):
        self.contours, self.cur, self.steps = [], [], steps

    def moveTo(self, p):
        self._close(); self.cur = [p]

    def lineTo(self, p):
        self.cur.append(p)

    def qCurveTo(self, *pts):
        p0 = self.cur[-1]
        offs, on = list(pts[:-1]), pts[-1]
        if on is None:
            on = ((offs[0][0] + offs[-1][0]) / 2, (offs[0][1] + offs[-1][1]) / 2)
        segs = []
        for i, c in enumerate(offs):
            e = ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2) if i + 1 < len(offs) else on
            segs.append((c, e))
        for c, e in segs:
            for n in range(1, self.steps + 1):
                t = n / self.steps
                self.cur.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * e[0],
                                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * e[1]))
            p0 = e

    def curveTo(self, *pts):
        c1, c2, e = pts[-3], pts[-2], pts[-1]
        p0 = self.cur[-1]
        for n in range(1, self.steps + 1):
            t = n / self.steps; m = 1 - t
            self.cur.append((m ** 3 * p0[0] + 3 * m * m * t * c1[0] + 3 * m * t * t * c2[0] + t ** 3 * e[0],
                             m ** 3 * p0[1] + 3 * m * m * t * c1[1] + 3 * m * t * t * c2[1] + t ** 3 * e[1]))

    def closePath(self):
        self._close()

    endPath = closePath

    def _close(self):
        if len(self.cur) >= 3:
            self.contours.append(self.cur)
        self.cur = []

    def shape(self):
        self._close()
        if not self.contours:
            return Polygon()
        # the non-zero rule: contours wound like the biggest one fill,
        # contours wound the other way are counters.  (Variable fonts keep
        # overlapping contours, so this is a union, not an even-odd fill.)
        polys = [(Polygon(c), _signed_area(c)) for c in self.contours]
        polys = [(p if p.is_valid else p.buffer(0), a) for p, a in polys]
        outer_sign = math.copysign(1, max(polys, key=lambda pa: abs(pa[1]))[1])
        fill = unary_union([p for p, a in polys if math.copysign(1, a) == outer_sign])
        cut = unary_union([p for p, a in polys if math.copysign(1, a) != outer_sign])
        return fill.difference(cut) if not cut.is_empty else fill


def _signed_area(c):
    return sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1] for i in range(len(c))) / 2


@lru_cache(None)
def sans(weight=500):
    return Face(SANS, weight, width=100)


@lru_cache(None)
def mono(weight=500):
    return Face(MONO, weight)


def lockup():
    """The horizontal lockup in its 800 x 200 units: (mark, wordmark)."""
    m = affinity.translate(mark(), *MARK_AT)
    size = WORD['size']
    w, _ = sans(WORD['weight']).outline('OffGrid', size, tracking=WORD['tracking'], liga=False)
    w = affinity.translate(w, WORD['x'], WORD['y'])
    return m, w


# ---------------------------------------------------------------- layout
TRACKING = {'sans': 0.01, 'mono': 0.06}          # em, from tokens.css .og-label / tokens.json mono


def styled(fam, s, cap):
    """Text in one of the two brand styles: (geometry, advance)."""
    if fam == 'mono':
        return mono(500).text(s.upper(), cap, TRACKING['mono'])
    return sans(500).text(s, cap, TRACKING['sans'])


def line(segments, cap, gap_em=0.28):
    """A line of mixed type: [('sans'|'mono', text), ...], words in
    Instrument Sans 500, codes in JetBrains Mono 500, one word space apart.
    Returns (geometry, width) with the baseline at y 0."""
    x, parts = 0.0, []
    for i, (fam, s) in enumerate(segments):
        g, adv = styled(fam, s, cap)
        parts.append(affinity.translate(g, x, 0))
        x += adv + (gap_em * cap * 1000 / 720 if i + 1 < len(segments) else 0)
    return unary_union(parts), x


def place(g, x, y, anchor='c', rot=0, mirror=False):
    """Move a geometry drawn with its baseline on y 0 so its anchor point
    lands on board (x, y), board-centre mm: anchor 'c' is the middle of the
    box, 'l'/'r' the middle of its left/right side.  rot is degrees
    counter-clockwise as seen from the side it is printed on; mirror for
    the bottom side."""
    x0, y0, x1, y1 = g.bounds
    ax = {'c': (x0 + x1) / 2, 'l': x0, 'r': x1}[anchor]
    g = affinity.translate(g, -ax, -(y0 + y1) / 2)
    if rot:
        g = affinity.rotate(g, -rot, origin=(0, 0))      # y down: negative = counter-clockwise on screen
    if mirror:
        g = affinity.scale(g, -1, 1, origin=(0, 0))
    return affinity.translate(g, x, y)


def add(b, g, layer):
    """Add a shapely geometry (board-centre mm, y down) as filled polygons."""
    items = []
    geoms = g.geoms if hasattr(g, 'geoms') else [g]
    for p in geoms:
        if p.is_empty or p.geom_type != 'Polygon':
            continue
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for (px, py) in list(p.exterior.coords)[:-1]:
            ps.Append(pcb.MM(pcb.CX + px), pcb.MM(pcb.CY + py))
        for k, h in enumerate(p.interiors):
            ps.NewHole()
            for (px, py) in list(h.coords)[:-1]:
                ps.Append(pcb.MM(pcb.CX + px), pcb.MM(pcb.CY + py), 0, k)
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_POLY)
        s.SetPolyShape(ps)
        s.SetLayer(layer); s.SetFilled(True); s.SetWidth(0)
        b.Add(s)
        items.append(s)
    return items


def thin_parts(g, w=MIN_STROKE):
    """Area of `g` narrower than w (mm^2): what a morphological opening
    removes.  0 means every stroke is at least w wide."""
    opened = g.buffer(-w / 2 * 0.98, quad_segs=4).buffer(w / 2 * 0.98, quad_segs=4)
    return g.difference(opened).area


def scaled(g, width, mirror=False):
    """g scaled to `width` mm across and centred on the origin; the scale
    factor too (brand units -> mm)."""
    k = width / (g.bounds[2] - g.bounds[0])
    return place(affinity.scale(g, k, k, origin=(0, 0)), 0, 0, mirror=mirror), k


def lockup_mm(width, mirror=False):
    """The horizontal lockup, `width` mm across, centred on the origin, and
    its clear space in mm (1 x node radius)."""
    m, w = lockup()
    g, k = scaled(unary_union([m, w]), width, mirror)
    return g, NODE_R * k


def mark_mm(width):
    """The bare mark, `width` mm across, and its clear space in mm."""
    g, k = scaled(mark(), width)
    return g, NODE_R * k


def arrow_mm(length, text=None, cap=1.1, shaft=0.25, head=0.9, gap=0.5, mirror=False, side=False):
    """Line-art arrow pointing to -y (the front), centred on the origin,
    with an optional word in Instrument Sans 500 beyond the head.  Square
    ends: right angles, per the brand."""
    h = length / 2
    hl = head * 1.4
    shaft_g = LineString([(0, h), (0, -h + hl * 0.9)]).buffer(shaft / 2, cap_style='flat')
    head_g = Polygon([(0, -h), (-head, -h + hl), (head, -h + hl)])
    parts = [shaft_g, head_g]
    if text:
        t, _ = styled('sans', text, cap)
        if side:     # the word to the right of the arrow, level with its head
            parts.append(place(t, head + gap, -h + cap / 2, anchor='l'))
        else:        # the word beyond the head
            parts.append(place(t, 0, -h - gap - cap / 2))
    g = unary_union(parts)
    x0, y0, x1, y1 = g.bounds
    g = affinity.translate(g, -(x0 + x1) / 2, -(y0 + y1) / 2)
    return affinity.scale(g, -1, 1, origin=(0, 0)) if mirror else g
