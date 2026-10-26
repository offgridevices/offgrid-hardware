# -*- coding: utf-8 -*-
"""Where every part of the USB board goes.

USB board millimetres: x along the receptacle's long side, y into the case
from the receptacle's mouth; the board's edge y = 0 rests against the
inside of the case's -X wall, behind the 9.4 x 3.8 opening (geometry.py).
Every part on F.

    the receptacle at the front edge, its mouth 1.2 mm past the edge and
    into the opening; ESD and the CC resistors behind it; the cable
    connector at the back edge, opening into the case
"""
F = 'F'
FIXED = {
    'J1': (0.0, 4.0, 180, F),         # mouth towards -y: 1.24 mm past the board edge
    'U1': (-4.4, 10.6, 0, F),           # USBLC6 on the data lines
    'D1': (9.8, 4.6, 90, F),          # TVS on 5 V
    'J2': (4.0, 12.5, 0, F),          # cable connector, opening towards +y
}
ANCHOR = {'CC1 Rd': ('J1', 'A5'), 'CC2 Rd': ('J1', 'B5'), '5 V at the connector': ('D1', '1')}
SIDE = {'CC1 Rd': 'B', 'CC2 Rd': 'B'}


def keepouts(side):
    return []


def height(part):
    return 1.0
