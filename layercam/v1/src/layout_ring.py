# -*- coding: utf-8 -*-
"""Where every part of the LED ring goes.

Ring millimetres, origin on the lens axis, seen from IN FRONT of the camera
(KiCad's top, F = the ring's front face, which rests on the housing's front
wall): x = -X, y = -Y of the lens frame (geometry.py).

    F (front)  the six IR LEDs, each in the housing's pocket behind its
               2.4 mm hole (R 13, every 60 degrees from +X), long side
               along the ring; the light sensor in the pocket behind the
               5.8 mm window (lens frame (0, -14.15))
    B (back)   the three string resistors and the cable connector, whose
               cable goes back past the lens holder to the main board
"""
import math
from shapely.geometry import Point
import geometry as G

F, B = 'F', 'B'


def _ring(angle_deg, r):
    """lens-frame angle (from +X, counter-clockwise seen from behind) and
    radius -> ring board (x, y) and the rotation that lays a part's long
    side along the ring."""
    a = math.radians(angle_deg)
    X, Y = r * math.cos(a), r * math.sin(a)
    x, y = -X, -Y
    # the tangent on the board; KiCad turns parts counter-clockwise on
    # screen (y down), so the rotation is minus the screen angle
    t = math.degrees(math.atan2(y, x)) + 90.0
    return x, y, round(-t, 3) % 360


FIXED = {}
for i, a in enumerate(G.LED_ANGLES):
    x, y, rot = _ring(a, G.LED_R)
    FIXED['D%d' % (i + 1)] = (x, y, rot, F)
FIXED['Q1'] = (-G.LIGHT_WINDOW[0], -G.LIGHT_WINDOW[1], 0, F)
FIXED['J1'] = _ring(200, 13.2)[:3] + (B,)
for i, a in enumerate((35, 95, 140)):
    FIXED['R%d' % (i + 1)] = _ring(a, 13.2)[:3] + (B,)

ANCHOR, SIDE = {}, {}


# the badge at the bottom of the back face (silk.py): no vias
def art_keepout():
    from shapely.geometry import Point, box
    return box(-8.0, 9.6, 8.0, 17.0).intersection(Point(0, 0).buffer(16.6))


def keepouts(side):
    return []


def height(part):
    return 1.0
