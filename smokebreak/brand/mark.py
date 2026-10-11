"""The OffGrid mark and lockup: the one source every SmokeBreak drawing,
screen, render and animation takes them from.  Nothing else may draw the
Beacon Ring with its own numbers.

From the brand hand-off (offgrid-brand v3.2), as used on Ridge 3
(ridge-3/src/brand.py):

  mark    200 x 200 box, y down:
          arc  M124.5 55.4 A58 58 0 1 1 75.5 55.4, stroke 22, round caps
          node circle r 17 at (100, 40)
  lockup  800 x 200: mark at translate(20 12); "OffGrid" in Instrument Sans
          600, size 92, letter-spacing -3, x 240, no ligatures, kerning on.
          Owner's change (2026-09-29): the word's capitals are centred on
          the ring's centre.

Everything is returned as shapely geometry in the brand's own units (y
down) or scaled to millimetres; `verify_mark.py` checks the numbers.
"""
import math
import os
from functools import lru_cache

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.ops import unary_union

FONTS = os.environ.get('SB_FONTS', '/tmp/claude-0/-home-user-offgrid-hardware/'
                       'bb4d9657-83a6-5d9a-b4a3-ba3efc9cb84f/scratchpad/ref')
SANS = os.path.join(FONTS, 'InstrumentSans-VariableFont.ttf')

# ------------------------------------------------------------------ the mark
BOX = 200.0
ARC_A = (124.5, 55.4)          # arc start (right end of the opening)
ARC_B = (75.5, 55.4)           # arc end (left end of the opening)
ARC_R = 58.0
STROKE = 22.0
NODE_C = (100.0, 40.0)
NODE_R = 17.0

# the lockup
MARK_AT = (20.0, 12.0)
WORD = dict(text='OffGrid', x=240.0, size=92.0, tracking=-3.0, weight=600)
LOCKUP_BOX = (800.0, 200.0)

# the arrow (ridge-3 arrow_mm): flat shaft, solid head, right-angle ends
ARROW_SHAFT, ARROW_HEAD = 0.25, 0.9


def ring_centre():
    """Centre of the large clockwise arc through ARC_A and ARC_B."""
    (x0, y0), (x1, y1), r = ARC_A, ARC_B, ARC_R
    h = math.sqrt(r * r - ((x1 - x0) / 2) ** 2)
    return (x0 + x1) / 2, (y0 + y1) / 2 + h


def gap_half_angle():
    """Half the opening, measured at the ring's centreline, in degrees from 12 o'clock."""
    cx, cy = ring_centre()
    return math.degrees(math.atan2(ARC_A[0] - cx, cy - ARC_A[1]))


@lru_cache(maxsize=None)
def mark(steps=180):
    """The Beacon Ring in its 200-unit box, y down."""
    cx, cy = ring_centre()
    a0 = math.atan2(ARC_A[1] - cy, ARC_A[0] - cx)
    a1 = math.atan2(ARC_B[1] - cy, ARC_B[0] - cx)
    if a1 <= a0:
        a1 += 2 * math.pi
    pts = [(cx + ARC_R * math.cos(a0 + (a1 - a0) * k / steps),
            cy + ARC_R * math.sin(a0 + (a1 - a0) * k / steps)) for k in range(steps + 1)]
    ring = LineString(pts).buffer(STROKE / 2, quad_segs=32, cap_style='round')
    node = Point(*NODE_C).buffer(NODE_R, quad_segs=32)
    return unary_union([ring, node])


def mark_parts():
    """(ring, node) separately, same units: for parts made or lit separately."""
    cx, cy = ring_centre()
    a0 = math.atan2(ARC_A[1] - cy, ARC_A[0] - cx)
    a1 = math.atan2(ARC_B[1] - cy, ARC_B[0] - cx) + 2 * math.pi
    pts = [(cx + ARC_R * math.cos(a0 + (a1 - a0) * k / 180),
            cy + ARC_R * math.sin(a0 + (a1 - a0) * k / 180)) for k in range(181)]
    ring = LineString(pts).buffer(STROKE / 2, quad_segs=32, cap_style='round')
    node = Point(*NODE_C).buffer(NODE_R, quad_segs=32)
    return ring, node


def by_ring_radius(R, centre=(0.0, 0.0), y_up=False):
    """The mark scaled so its ring's centreline radius is R, with the ring's
    centre at `centre`.  y_up=True flips to y-up coordinates (Blender)."""
    k = R / ARC_R
    cx, cy = ring_centre()
    g = affinity.translate(mark(), -cx, -cy)
    g = affinity.scale(g, k, k, origin=(0, 0))
    if y_up:
        g = affinity.scale(g, 1, -1, origin=(0, 0))
    return affinity.translate(g, *centre)


def proportions():
    """The mark's proportions relative to the ring's centreline radius R."""
    cx, cy = ring_centre()
    return dict(stroke=STROKE / ARC_R, node_r=NODE_R / ARC_R,
                node_offset=(cy - NODE_C[1]) / ARC_R, gap_half_deg=gap_half_angle())


# ------------------------------------------------------------------ the word
class _Pen:
    def __init__(self, steps=10):
        self.steps, self.contours, self.cur, self.p = steps, [], [], None

    def moveTo(self, p):
        self._close(); self.cur = [p]; self.p = p

    def lineTo(self, p):
        self.cur.append(p); self.p = p

    def qCurveTo(self, *pts):
        pts = list(pts)
        if pts[-1] is None:
            pts = pts[:-1]
        on = pts[-1]
        offs = pts[:-1]
        segs = []
        for i, c in enumerate(offs):
            e = on if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2)
            segs.append((c, e))
        for c, e in segs:
            s0 = self.p
            for k in range(1, self.steps + 1):
                t = k / self.steps
                self.cur.append(((1 - t) ** 2 * s0[0] + 2 * (1 - t) * t * c[0] + t * t * e[0],
                                 (1 - t) ** 2 * s0[1] + 2 * (1 - t) * t * c[1] + t * t * e[1]))
            self.p = e

    def curveTo(self, *pts):
        c1, c2, e = pts[-3], pts[-2], pts[-1]
        s0 = self.p
        for k in range(1, self.steps + 1):
            t = k / self.steps
            mt = 1 - t
            self.cur.append((mt ** 3 * s0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * e[0],
                             mt ** 3 * s0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * e[1]))
        self.p = e

    def closePath(self):
        self._close()

    endPath = closePath

    def _close(self):
        if len(self.cur) >= 3:
            self.contours.append(self.cur)
        self.cur = []

    def shape(self):
        """Fill by the non-zero rule: contours wound like the largest fill,
        the others are counters (variable fonts keep overlaps)."""
        self._close()
        if not self.contours:
            return Polygon()
        def area(c):
            return 0.5 * sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1]
                             for i in range(len(c)))
        sign = 1 if area(max(self.contours, key=lambda c: abs(area(c)))) > 0 else -1
        fills = [Polygon(c).buffer(0) for c in self.contours if area(c) * sign > 0]
        holes = [Polygon(c).buffer(0) for c in self.contours if area(c) * sign <= 0]
        return unary_union(fills).difference(unary_union(holes)) if holes else unary_union(fills)


@lru_cache(maxsize=None)
def _font(weight):
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    blob = hb.Blob.from_file_path(SANS)
    face = hb.Face(blob)
    font = hb.Font(face)
    font.set_variations({'wght': weight})
    cap = TTFont(SANS)['OS/2'].sCapHeight
    return hb, face, font, cap


def word(text=WORD['text'], size=WORD['size'], tracking=WORD['tracking'], weight=WORD['weight']):
    """Shaped text (HarfBuzz, kerning on, no ligatures) as shapely geometry,
    y down, baseline at 0, starting at x 0.  Returns (geometry, cap height)."""
    hb, face, font, cap_units = _font(weight)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {'liga': False, 'kern': True})
    k = size / face.upem
    x = 0.0
    parts = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = _Pen()
        font.draw_glyph_with_pen(info.codepoint, pen)
        g = pen.shape()
        if not g.is_empty:
            parts.append(affinity.affine_transform(g, [k, 0, 0, -k, x + pos.x_offset * k, -pos.y_offset * k]))
        x += pos.x_advance * k + tracking
    return unary_union(parts), cap_units * k


@lru_cache(maxsize=None)
def lockup():
    """(mark, word) in the lockup's 800 x 200 units, y down."""
    m = affinity.translate(mark(), *MARK_AT)
    w, cap = word()
    baseline = MARK_AT[1] + ring_centre()[1] + cap / 2
    return m, affinity.translate(w, WORD['x'], baseline)


def lockup_by_width(width, centre=(0.0, 0.0), y_up=False):
    """The lockup `width` mm across its ink, centred on `centre`."""
    m, w = lockup()
    g = unary_union([m, w])
    x0, y0, x1, y1 = g.bounds
    k = width / (x1 - x0)
    out = []
    for part in (m, w):
        p = affinity.translate(part, -(x0 + x1) / 2, -(y0 + y1) / 2)
        p = affinity.scale(p, k, k, origin=(0, 0))
        if y_up:
            p = affinity.scale(p, 1, -1, origin=(0, 0))
        out.append(affinity.translate(p, *centre))
    return tuple(out)


# ------------------------------------------------------------------ export
def polygons(g):
    """Every polygon of a geometry, as a list."""
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, 'geoms', []) if isinstance(p, Polygon)]


def svg_path(g, digits=3):
    """An SVG path (fill-rule evenodd) for a geometry."""
    out = []
    for p in polygons(g):
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            out.append('M' + ' L'.join(f'{x:.{digits}f} {y:.{digits}f}' for x, y in pts) + ' Z')
    return ' '.join(out)


def svg_mark(cx, cy, R, fill='#F1ECE0', extra=''):
    """An SVG <path> of the mark, ring centreline radius R, ring centre at
    (cx, cy), in SVG (y-down) user units."""
    return f'<path d="{svg_path(by_ring_radius(R, centre=(cx, cy)))}" fill="{fill}" fill-rule="evenodd" {extra}/>'


def svg_lockup(cx, cy, width, fill='#F1ECE0', extra=''):
    """An SVG <path> of the horizontal lockup, `width` across its ink,
    centred on (cx, cy), in SVG (y-down) user units."""
    from shapely.ops import unary_union
    mk, wd = lockup_by_width(width, centre=(cx, cy))
    return f'<path d="{svg_path(unary_union([mk, wd]))}" fill="{fill}" fill-rule="evenodd" {extra}/>'


def svg_word(x, y_baseline, cap, fill='#F1ECE0', anchor='start', extra=''):
    """An SVG <path> of the word OffGrid as in the lockup, capitals `cap`
    tall, its baseline at y_baseline; anchor start | middle | end at x."""
    g, c = word()
    k = cap / c
    g = affinity.scale(g, k, k, origin=(0, 0))
    x0, _, x1, _ = g.bounds
    dx = {'start': -x0, 'end': -x1}.get(anchor, -(x0 + x1) / 2)
    g = affinity.translate(g, x + dx, y_baseline)
    return f'<path d="{svg_path(g)}" fill="{fill}" fill-rule="evenodd" {extra}/>'
