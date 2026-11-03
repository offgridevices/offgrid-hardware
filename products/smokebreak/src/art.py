"""SmokeBreak v1 silkscreen art: the exact OffGrid lockup and mark, labels in
Instrument Sans (sentence case), numerals in JetBrains Mono, and the brand's
plain arrows, all as filled polygons in board millimetres.

Runs in the Python that has shapely + uharfbuzz (the brand tools' venv);
make.py calls it with a JSON list of items and reads polygons back:

    python art.py spec.json out.json

Item kinds (all positions in board mm, y towards the user):
  {"kind": "text", "text": "Battery", "x":, "y":, "cap": 1.6, "anchor": "start|middle|end",
   "font": "sans|mono", "weight": 500, "rot": 0, "layer": "F.SilkS"}
     y is the baseline; rot in degrees, counter-clockwise as seen from the top
  {"kind": "lockup", "x":, "y":, "width":, "layer":}   centred on (x, y)
  {"kind": "mark", "x":, "y":, "R":, "layer":}         ring centre at (x, y)
  {"kind": "arrow", "x0":, "y0":, "x1":, "y1":, "shaft": 0.25, "head": 0.9, "layer":}
  {"kind": "rect", "x0":, "y0":, "x1":, "y1":, "layer":}
  {"kind": "flag", "x":, "y":, "hoist":, "layer":}       US flag centred on (x, y), Flag Code
     proportions (EO 10834); ink is the red stripes and the union, the
     stars and the white stripes are the board showing through
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brand as M                                         # noqa: E402
from shapely import affinity                             # noqa: E402
from shapely.geometry import Polygon                     # noqa: E402
from shapely.ops import unary_union                      # noqa: E402

MONO = os.path.join(M.FONTS, 'JetBrainsMono-VariableFont.ttf')


def shaped(text, size, weight, path):
    """Text shaped with HarfBuzz (kerning on, no ligatures), y down, baseline 0."""
    if path == M.SANS:
        return M.word(text, size=size, tracking=0.0, weight=weight)
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    face = hb.Face(hb.Blob.from_file_path(path))
    font = hb.Font(face)
    font.set_variations({'wght': weight})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {'liga': False, 'kern': True})
    k = size / face.upem
    x, parts = 0.0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = M._Pen()
        font.draw_glyph_with_pen(info.codepoint, pen)
        g = pen.shape()
        if not g.is_empty:
            parts.append(affinity.affine_transform(g, [k, 0, 0, -k, x + pos.x_offset * k, -pos.y_offset * k]))
        x += pos.x_advance * k
    return unary_union(parts), TTFont(path)['OS/2'].sCapHeight * k


def text(it):
    path = MONO if it.get('font') == 'mono' else M.SANS
    weight = it.get('weight', 500)
    g, cap = shaped(it['text'], 100.0, weight, path)
    k = it['cap'] / cap
    g = affinity.scale(g, k, k, origin=(0, 0))
    x0, _, x1, _ = g.bounds
    w = x1 - x0
    dx = {'start': -x0, 'middle': -(x0 + x1) / 2, 'end': -x1}[it.get('anchor', 'start')]
    g = affinity.translate(g, dx, 0)
    if it.get('rot'):
        g = affinity.rotate(g, -it['rot'], origin=(0, 0))        # y down: CCW on the board
    return affinity.translate(g, it['x'], it['y']), w


def arrow(it):
    x0, y0, x1, y1 = it['x0'], it['y0'], it['x1'], it['y1']
    s, h = it.get('shaft', M.ARROW_SHAFT), it.get('head', M.ARROW_HEAD)
    L = math.hypot(x1 - x0, y1 - y0)
    hl = h * 1.0                                   # head length = head width: a right angle at the tip
    shaft = Polygon([(0, -s / 2), (L - hl, -s / 2), (L - hl, s / 2), (0, s / 2)])
    head = Polygon([(L - hl, -h / 2), (L, 0), (L - hl, h / 2)])
    g = unary_union([shaft, head])
    g = affinity.rotate(g, math.degrees(math.atan2(y1 - y0, x1 - x0)), origin=(0, 0))
    return affinity.translate(g, x0, y0)


def star(cx, cy, d):
    """Five-pointed star, point up, circumscribed diameter d (y down)."""
    R, r = d / 2, d / 2 * 0.381966
    pts = []
    for i in range(10):
        ang = math.radians(-90 + 36 * i)
        rr = R if i % 2 == 0 else r
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return Polygon(pts)


def flag(it):
    """US flag per the Flag Code / EO 10834: hoist A = 1, fly B = 1.9, union
    C = 7/13 by D = 0.76, star spacing E = F = 0.054, G = H = 0.063, star
    diameter K = 0.0616, stripes L = 1/13."""
    A = it['hoist']
    B_, C, D, E, G, K, L = 1.9 * A, 7 / 13 * A, 0.76 * A, 0.054 * A, 0.063 * A, 0.0616 * A, A / 13
    x0, y0 = it['x'] - B_ / 2, it['y'] - A / 2
    red = [Polygon([(x0, y0 + 2 * i * L), (x0 + B_, y0 + 2 * i * L), (x0 + B_, y0 + (2 * i + 1) * L),
                    (x0, y0 + (2 * i + 1) * L)]) for i in range(7)]
    union = Polygon([(x0, y0), (x0 + D, y0), (x0 + D, y0 + C), (x0, y0 + C)])
    stars = []
    for row in range(9):
        cols = range(6) if row % 2 == 0 else range(5)
        for k in cols:
            sx = x0 + G * (2 * k + 1) if row % 2 == 0 else x0 + G * (2 * k + 2)
            stars.append(star(sx, y0 + E * (row + 1), K))
    return unary_union(red + [union]).difference(unary_union(stars))


def build(items):
    out = []
    for it in items:
        k = it['kind']
        extra = {}
        if k == 'text':
            g, w = text(it)
            extra['width'] = w
        elif k == 'lockup':
            g = unary_union(M.lockup_by_width(it['width'], (it['x'], it['y'])))
        elif k == 'mark':
            g = M.by_ring_radius(it['R'], (it['x'], it['y']))
        elif k == 'arrow':
            g = arrow(it)
        elif k == 'flag':
            g = flag(it)
        elif k == 'rect':
            g = Polygon([(it['x0'], it['y0']), (it['x1'], it['y0']), (it['x1'], it['y1']), (it['x0'], it['y1'])])
        else:
            raise ValueError(k)
        polys = []
        for p in M.polygons(g):
            polys.append(dict(outer=[list(c) for c in p.exterior.coords[:-1]],
                              holes=[[list(c) for c in r.coords[:-1]] for r in p.interiors]))
        out.append(dict(layer=it['layer'], polys=polys, bounds=list(g.bounds), **extra))
    return out


if __name__ == '__main__':
    items = json.load(open(sys.argv[1]))
    json.dump(build(items), open(sys.argv[2], 'w'))
