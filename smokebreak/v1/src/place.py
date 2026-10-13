"""SmokeBreak compact: where every part goes.

The board (91.6 x 48.6 mm) sits in a 97 x 54 x 15 mm case.  Every
mechanical position comes from geometry.py (the enclosure reads the same
file), so the face's single 6 mm margin is the board's too.

    back strip   under the screen module (height limit 6.3 mm): the input
                 caps and the fire fuse by the battery plugs, the MCU, the two
                 flat pre-charge resistors, the display connector, USB-C
    battery end  XT60 and XT30 male, mouths out of the end wall
    the well     five top-entry JST-XH sockets centred under the screen, pin 1
                 (the black wire) of every one on one line at the front; the
                 divider row-houses, the OR diodes, the battery-minus FET and
                 the pre-charge FET in the stair behind the short sockets
    centre       the power district: TPS48000 over the back-to-back FETs
    drone end    the switch in its status ring, the hall switch under the
                 guard's tip, the Limit rocker's two switches and the beeper
                 under the paddle, the drone leads' pads at the end wall and
                 the shunt between their minus pads; the logic street and the
                 aux supply in the gaps

Coordinates: board mm from the back-left corner, x toward the drone end, y
toward the user.  Each entry: (x, y, rotation degrees, side, fixed).  Fixed
parts are where the case, the connectors or the physics put them; the others
are anchors that make.py's legaliser may nudge (0.25 mm grid).
"""
import math

import circuit as C
import geometry as G

PL = {}


def at(ref, x, y, rot=0, side='T', fixed=False):
    assert ref in C.COMPONENTS, ref
    PL[ref] = (round(x, 3), round(y, 3), rot, side, fixed)


def fix(ref, x, y, rot=0, side='T'):
    at(ref, x, y, rot, side, True)


def row(refs, x0, y, dx, rot=0):
    for i, r in enumerate(refs):
        at(r, x0 + i * dx, y, rot)


def col(refs, x, y0, dy, rot=0):
    for i, r in enumerate(refs):
        at(r, x, y0 + i * dy, rot)


B = G.b                                   # case -> board

# ================================================================ fixed by the case
for i, (x, y) in enumerate(G.HOLES, 1):
    fix(f'H{i}', x, y)
fix('J1', *G.J1_AT, 0)                    # XT60 male, mouth through the battery end
fix('J2', *G.J2_AT, 270)                  # XT30 male, below it, beside the 2S socket
PIN1_Y = B(0, G.PIN1_FY)[1]
SOCKETS = (('J12', 0), ('J11', 1), ('J10', 2), ('J9', 3), ('J5', 4))      # 2S .. 6S
for ref, k in SOCKETS:
    fix(ref, B(G.SOCKET_X[k], 0)[0], PIN1_Y, 90)
TOG = B(*G.TOG)
RING_R = G.RING_R
fix('SW1', *TOG, 0)
for i in range(12):
    a = math.radians(120 + 30 * i)                       # LED1 at 7 o'clock, clockwise
    fix(f'LED{i + 1}', TOG[0] + RING_R * math.cos(a), TOG[1] + RING_R * math.sin(a), -90 * round((i + 7) / 3))
fix('U6', TOG[0], B(0, G.M + G.GUARD_L)[1] - 0.7, 0)    # hall switch under the guard tip's magnet
SW_Y = B(0, G.ROCK_SW_FY)[1] - 0.6
fix('SW2', TOG[0] - 7.5, SW_Y, 0)                        # Limit -
fix('SW3', TOG[0] + 7.5, SW_Y, 0)                        # Limit +
fix('BZ1', TOG[0], SW_Y + 2.2, 0)                        # beeper under the paddle, between its switches
fix('J3', *G.J3_AT, 0)                                   # XT60 lead pads
fix('J4', *G.J4_AT, 0)                                   # XT30 lead pads
fix('J8', 62.1, 4.3, 180)                                # USB-C through the back wall
fix('J7', 51.9, 10.5, 90)                                # display FPC, opening toward the module's FPC end
fix('U5', 18.6, 12.9, 90)                                # MCU under the screen
fix('R_PRE', 31.2, 8.69, 90)                             # pre-charge resistors, flat, under the screen
fix('R_PRE2', 42.7, 8.69, 90)
fix('F1', 6.2, 16.0, 0)                                  # the fire fuse, its VBAT end by the XT60's +
fix('J6', 30.0, 30.0, 0, 'B')                            # SWD pogo pads on the underside

# ================================================================ battery corner (under the screen, x < 12)
at('D1', 4.0, 2.4, 0)                                    # TVS
at('R67', 8.8, 2.9, 90)
at('C3', 10.9, 2.9, 90)
row(['C1', 'C2'], 2.95, 6.9, 4.9, 0)
row(['C50', 'C51'], 2.95, 10.4, 4.9, 0)

# ================================================================ MCU's north side (under the screen)
row(['D14', 'D15', 'D16'], 14.0, 2.2, 3.6, 0)           # aux OR: VIN, VOUT, (USB into 5 V)
at('R53', 23.9, 2.5, 90)
row(['C34', 'C35', 'C36', 'C38'], 13.6, 4.6, 2.1, 0)    # MCU decaps
at('C37', 23.0, 4.6, 0)

# ================================================================ the stair behind the short sockets
# battery minus FET by the plugs' minus pins, drain west; the pre-charge FET
# and its diode on the way to R_PRE's pin 1; the divider row-houses (one
# column per tap) behind the 4S socket; the OR diodes between
fix('Q11', 16.65, 32.1, 90)
fix('Q3', 18.0, 22.95, 180)                              # tab east, toward its diode
fix('D3', 26.0, 22.75, 90)
at('R74', 20.6, 27.0, 0)
at('D20', 23.3, 28.6, 90)
for i, k in enumerate(range(2, C.BALANCE_MAX + 2)):
    parts_k = [r for r, c in C.COMPONENTS.items() if c['group'] == 'balance' and not r.startswith('J')
               and any(n in (f'BAL{k}', f'BAL{k}_ADC') for n in c['pins'].values())]
    d = [r for r in parts_k if r.startswith('D')][0]
    cap = [r for r in parts_k if r.startswith('C')][0]
    rs = [r for r in parts_k if r.startswith('R')]
    top = [r for r in rs if f'BAL{k}' in C.COMPONENTS[r]['pins'].values()][0]
    bot = [r for r in rs if r != top][0]
    x = 28.9 + 1.1 * i
    at(top, x, 20.2, 90)
    at(bot, x, 22.3, 90)
    at(cap, x, 24.4, 90)
    at(d, 23.2 + 1.8 * (i % 3), 27.8 + 3.4 * (i // 3), 90)
at('R75', 31.5, 27.6, 0)
at('Q8', 37.2, 22.0, 0)
at('R52', 39.6, 22.0, 90)
at('RT2', 37.0, 19.6, 0)                                 # the pre-charge resistors' NTC, between them
at('R25', 35.4, 24.8, 0)

# ================================================================ power district (centre column)
fix('Q1', 52.0, 28.0, 90)
fix('Q2', 59.5, 28.0, 270)
at('U1', 55.75, 22.4, 180)
for ref, (x, y, r) in {
    'R1': (49.6, 21.2, 90), 'C4': (51.0, 21.2, 90), 'R2': (49.6, 34.4, 90), 'R3': (51.0, 34.4, 90),
    'R4': (52.4, 34.4, 90), 'R5': (53.8, 34.4, 90), 'R8': (55.2, 34.4, 90), 'R13': (56.6, 34.4, 90),
    'R9': (60.4, 21.2, 90), 'R10': (61.8, 21.2, 90), 'C5': (55.75, 32.2, 0),
    'R6': (58.0, 34.4, 90), 'R7': (59.4, 34.4, 90), 'R69': (60.8, 34.4, 90), 'C54': (62.2, 34.4, 90),
    'R11': (58.0, 37.0, 90), 'R12': (59.4, 37.0, 90),
    'D18': (54.0, 37.0, 0), 'RT1': (49.2, 31.6, 90), 'R35': (49.2, 37.2, 90),
}.items():
    at(ref, x, y, r)
# pre-charge drive, below the FET district's resistor row
for ref, (x, y, r) in {
    'D2': (50.4, 37.4, 0), 'R19': (50.0, 39.4, 0), 'R20': (50.4, 41.2, 0), 'D19': (54.0, 39.4, 0),
    'Q4': (53.8, 41.6, 0), 'Q5': (57.0, 41.6, 0), 'R21': (52.6, 39.4, 90), 'R22': (55.6, 39.4, 90),
    'R23': (56.6, 39.4, 90), 'R24': (58.6, 39.4, 90),
}.items():
    at(ref, x, y, r)

# ================================================================ under the screen, east of the FPC connector
for ref, (x, y, r) in {
    'Q9': (58.4, 9.4, 0), 'Q12': (62.0, 9.4, 0), 'R80': (60.2, 11.6, 0), 'R60': (63.6, 12.0, 90),
    'R56': (59.0, 13.8, 0), 'C41': (62.8, 15.2, 90), 'U4': (58.4, 17.0, 0), 'C32': (61.2, 17.4, 90),
    'C33': (62.8, 18.6, 0),
}.items():
    at(ref, x, y, r)

# ================================================================ aux supply: bottom centre, between the well and the rocker
for ref, (x, y, r) in {
    'U3': (60.4, 47.2, 0), 'L1': (61.0, 37.4, 0), 'C26': (64.6, 47.4, 90), 'C27': (57.0, 46.0, 90),
    'C28': (63.2, 43.6, 0), 'C29': (63.4, 45.0, 0), 'R76': (57.0, 48.6, 90), 'R77': (63.4, 42.0, 0),
    'R78': (57.0, 44.0, 0), 'R79': (63.6, 41.2, 0), 'C57': (59.6, 43.4, 0),
    'C30': (65.4, 37.0, 90), 'C31': (65.4, 33.8, 90),
}.items():
    at(ref, x, y, r)

# ================================================================ USB support, beside the port
at('U11', 68.2, 2.6, 0)
row(['R62', 'R63', 'R64', 'R65'], 57.6, 9.0, 1.2, 90)
at('C49', 66.0, 9.6, 90)

# ================================================================ drone end: sense, logic, probe, snubber
for ref, (x, y, r) in {
    'RS1': (84.6, 29.6, 0), 'U2': (80.6, 29.8, 90), 'R14': (82.6, 27.0, 0), 'R15': (82.6, 32.4, 0),
    'C6': (80.4, 26.9, 0), 'C7': (78.4, 30.0, 90), 'R16': (75.4, 36.8, 0), 'C8': (75.4, 38.2, 0),
    'C14': (84.6, 36.0, 0), 'R68': (88.6, 40.0, 90), 'C52': (84.6, 41.0, 90), 'C53': (81.6, 47.4, 0),
    'U8': (71.0, 29.0, 0), 'C10': (71.0, 31.4, 0), 'R17': (68.6, 28.8, 90), 'C9': (68.6, 31.0, 90),
    'R66': (73.6, 29.0, 90), 'U9': (72.2, 34.6, 0), 'C11': (69.8, 34.6, 90),
    'U7': (81.0, 34.6, 0), 'C12': (78.6, 34.6, 90), 'R18': (83.6, 34.0, 90),
    'U12': (70.4, 25.4, 90), 'R70': (66.8, 25.0, 90), 'R71': (65.4, 25.0, 90), 'C55': (66.8, 27.4, 90),
    'C56': (65.4, 27.4, 90), 'C13': (78.4, 32.8, 0),
    'Q6': (89.6, 10.6, 90), 'Q7': (89.6, 14.4, 90), 'R26': (86.6, 13.0, 90), 'R27': (87.6, 17.2, 90),
    'R72': (85.6, 11.0, 90), 'R73': (86.6, 15.6, 90), 'R28': (89.6, 18.0, 90), 'R29': (85.2, 20.6, 90),
    'D4': (87.4, 20.4, 90), 'R30': (70.0, 2.0, 90), 'R31': (71.4, 2.0, 90), 'C15': (72.8, 2.0, 90),
    'R32': (74.2, 2.0, 90), 'D5': (77.4, 1.8, 0), 'C16': (80.2, 2.0, 90), 'R33': (63.6, 2.4, 90),
    'R34': (63.6, 4.6, 90), 'C17': (82.8, 2.0, 90),
}.items():
    at(ref, x, y, r)
for ref, (x, y, r) in {
    'R54': (70.4, 37.6, 90), 'C39': (71.8, 37.6, 90), 'R55': (81.0, 37.6, 90), 'C40': (82.4, 37.6, 90),
    'Q10': (78.4, 49.0, 0), 'R61': (75.0, 49.4, 0), 'D17': (72.0, 49.4, 0),
}.items():
    at(ref, x, y, r)

# status ring: six 100 nF inside the ring, three each side of the switch; the
# driver at 7 o'clock by LED1
col(['C48', 'C43', 'C44'], TOG[0] - 5.7, TOG[1] - 3.5, 3.5, 90)
col(['C47', 'C46', 'C45'], TOG[0] + 5.7, TOG[1] - 3.5, 3.5, 90)
at('U10', 66.8, 22.2, 0)
at('C42', 64.6, 20.2, 90)

# ================================================================ settle
# The anchors above are the intent; spread.py settles them into a legal
# placement (place_legal.py).  An entry whose anchor has since moved is stale
# and ignored, so the part falls back to its anchor until spread.py runs.
ANCHORS = dict(PL)
try:
    from place_legal import LEGAL
except ImportError:
    LEGAL = {}
for _ref, (_x, _y, _rot, _anchor) in LEGAL.items():
    if _ref in PL and not PL[_ref][4] and tuple(PL[_ref][:3]) == tuple(_anchor):
        PL[_ref] = (_x, _y, _rot, PL[_ref][3], False)
