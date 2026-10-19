# -*- coding: utf-8 -*-
"""The flag of the United States, as board copper, mask and silkscreen.

Proportions are the statutory ones (Executive Order 10834, 1959), in units
of the hoist A = 1:

  B fly 1.9          C canton hoist 7/13     D canton fly 0.76
  E, F star rows 0.054 apart (E from the canton's top edge)
  G, H star columns 0.063 apart (G from the canton's hoist edge)
  K star diameter 0.0616      L stripe 1/13

A board has three colours to paint with, and the flag maps onto them:

  red stripes    ENIG gold: windows in the solder mask over a copper plate
  white stripes  white silkscreen, on the mask between the windows
  blue canton    the black solder mask itself, over the same copper plate
  stars          gold: small windows in the mask over the plate.  On a flag
                 a few millimetres tall, silkscreen ink would run the 50
                 stars together; a mask window is cut far finer, so the
                 stars come out as crisp gold points on the black canton

The copper plate is a ground pour drawn under the whole flag, so the gold
is the board's ground, as any exposed copper should be.  Nothing is
soldered there and nothing carries current.
"""
import math
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely import affinity

B, C, D = 1.9, 7 / 13, 0.76
E = F = 0.054
G = H = 0.063
K = 0.0616


def star(cx, cy, d):
    """A five-pointed star of diameter d (point to point), one point up
    (y down on screen: 'up' is -y)."""
    ro, ri = d / 2, d / 2 * math.sin(math.radians(18)) / math.sin(math.radians(54))
    pts = []
    for k in range(10):
        a = math.radians(-90 + 36 * k)
        r = ro if k % 2 == 0 else ri
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return Polygon(pts)


def flag(hoist, min_star=0.2, min_gap=0.1):
    """The flag `hoist` mm tall, its top-left corner at the origin (y down).
    Returns dict(gold=..., silk=..., plate=...): the mask windows (red
    stripes and stars), the silkscreen (white stripes) and the copper plate
    under it all.  Each star is the statute's 0.0616 of the hoist, but at
    least min_star mm across, and never closer than min_gap mm to the next
    (the mask's finest web)."""
    A = hoist
    L = A / 13
    W = B * A
    red, white = [], []
    for i in range(13):
        s = box(0, i * L, W, (i + 1) * L)
        (red if i % 2 == 0 else white).append(s)
    canton = box(0, 0, D * A, C * A)
    gold = unary_union(red).difference(canton)
    stripes = unary_union(white).difference(canton)
    # nearest neighbours: the next row's star, half a column across
    pitch = math.hypot(F * A, H * A)
    d = min(max(K * A, min_star), pitch - min_gap)
    stars = []
    for row in range(9):
        y = (E + row * F) * A
        n, x0 = (6, G) if row % 2 == 0 else (5, G + H)
        for j in range(n):
            stars.append(star((x0 + 2 * H * j) * A, y, d))
    gold = unary_union([gold] + stars)
    return dict(gold=gold, silk=stripes, plate=box(-0.15, -0.15, W + 0.15, A + 0.15), size=(W, A), star=d)


def subdued(hoist, border=0.15, min_star=0.2, min_gap=0.15):
    """The flag in silkscreen alone, for a board with no ground plate big
    enough for the gold one: the subdued (black and white) flag of a
    uniform patch.  White stripes and a white canton with the stars cut out
    of it as black points (or, on a flag too small for silk to cut them, a
    plain black canton), inside a thin white border; the red stripes are
    the black mask.  Same frame as flag(); the 'gold' is empty."""
    A = hoist
    L = A / 13
    W = B * A
    canton = box(0, 0, D * A, C * A)
    white = unary_union([box(0, i * L, W, (i + 1) * L) for i in range(1, 13, 2)]).difference(canton)
    pitch = math.hypot(F * A, H * A)
    d = min(max(K * A, min_star), pitch - min_gap)
    frame = box(0, 0, W, A).difference(box(border, border, W - border, A - border))
    if d >= min_star:
        # a white canton with the stars cut out as black points
        stars = []
        for row in range(9):
            y = (E + row * F) * A
            n, x0 = (6, G) if row % 2 == 0 else (5, G + H)
            for j in range(n):
                stars.append(star((x0 + 2 * H * j) * A, y, d))
        field = canton.difference(unary_union(stars))
    else:
        # stars too small for silk to cut cleanly: the canton stays a plain
        # black field, framed by the border and the stripes
        field, d = Polygon(), 0.0
    silk = unary_union([white, field, frame])
    return dict(gold=Polygon(), silk=silk, plate=box(-0.15, -0.15, W + 0.15, A + 0.15), size=(W, A), star=d)


def placed(hoist, x, y, rot=0, mirror=False, style='gold'):
    """flag() (or subdued()) centred on board (x, y), turned rot degrees
    (counter-clockwise on screen) and mirrored for the bottom side."""
    f = (subdued if style == 'subdued' else flag)(hoist)
    W, A = f['size']
    out = {}
    for k in ('gold', 'silk', 'plate'):
        if f[k].is_empty:
            out[k] = f[k]
            continue
        g = affinity.translate(f[k], -W / 2, -A / 2)
        if rot:
            g = affinity.rotate(g, -rot, origin=(0, 0))
        if mirror:
            g = affinity.scale(g, -1, 1, origin=(0, 0))
        out[k] = affinity.translate(g, x, y)
    return out
