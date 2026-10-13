"""SmokeBreak v1: where every part goes (layout A: the battery end).

The board is planned like a city: districts with one job each, streets
between them, parts in rows, every part of a kind facing the same way.

    battery end  XT60 and XT30 male through the end wall; behind them, along
                 the front, the balance well: five top-entry JST-XH sockets,
                 2S nearest the XT30 up to 6S, black-wire pins in one line
    under screen the battery gate, the pre-charge FET, the MCU, the divider
                 row-houses; the two pre-charge resistors along the back
    centre       the power district: TPS48000 over the two FETs back to back
    drone end    the Arm: the toggle in its status ring; the drone leads'
                 solder pads at the end wall, the shunt between them
    front right  the Limit rocker's two switches, the beeper between them,
                 the comparators and the probe in a row above
    back right   USB-C through the back wall, the aux supply beside it

Coordinates: mm from the board's back-left corner, x toward the drone end,
y toward the user.  Each entry: (x, y, rotation degrees, side, fixed).  Fixed
parts are where the case, the connectors or the physics put them; the
others are anchors that make.py's legaliser nudges (0.25 mm grid, nearest
free spot) until no two courtyards touch.

Mechanical stack: the PCB's top face is 11.5 mm below the underside of the
top panel (the XT connectors' axes at the body's mid-height).  The toggle
(8.89 mm PCB-to-shoulder) seats on a 2.6 mm printed boss under the panel.
Under the screen (x 3-49, y 1-27) parts stay below 8.5 mm: the XT60 is
8.2 mm, the pre-charge resistors 7.5 mm.  The well's sockets stand 7 mm.
Four M3 holes 5 mm in from each edge, 9.4 mm keep-out round each.
"""
import math

import board as B
import circuit as C

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


# ================================================================ fixed by the case and the physics
for i, (x, y) in enumerate(B.HOLES, 1):
    fix(f'H{i}', x, y)

# battery end: male plugs through the end wall (mouths 3 mm past the edge)
fix('J1', 10.2, 20.0, 0)              # XT60 male
fix('J2', 6.5, 34.8, 270)             # XT30 male, by the well
# the balance well: top-entry sockets, pin 1 (black wire) on one line at the front
SOCKET_PIN1_Y = 48.0
SOCKETS = (('J12', 16.0), ('J11', 23.1), ('J10', 30.2), ('J9', 37.3), ('J5', 44.4))   # 2S .. 6S
for ref, x in SOCKETS:
    fix(ref, x, SOCKET_PIN1_Y, 90)

# the two 5 W pre-charge resistors end to end along the back, under the screen:
# FET side (PRE_K) west, drone side (VOUT) east
fix('R_PRE', 22.4, 4.6, 0)
fix('R_PRE2', 47.2, 4.6, 0)
fix('J8', 66.0, 4.3, 180)             # USB-C through the back wall

# the Arm: toggle under the face's toggle, status ring round its bushing
TOG = (73.2, 19.5)
RING_R = 9.5
fix('SW1', *TOG, 0)
for i in range(12):
    a = math.radians(120 + 30 * i)                       # LED1 at 7 o'clock (its driver sits there), clockwise
    fix(f'LED{i + 1}', TOG[0] + RING_R * math.cos(a), TOG[1] + RING_R * math.sin(a), -90 * round((i + 7) / 3))
fix('U6', 73.2, 36.6, 0)                                 # hall switch under the guard's tip magnet

# drone end: the leads' solder pads at the end wall, minus pads side by side
fix('J3', 87.2, 18.2, 0)              # XT60 lead, 12 AWG
fix('J4', 87.2, 33.7, 0)              # XT30 lead, 16 AWG
fix('RS1', 82.5, 34.0, 270)           # shunt off the minus pads
fix('U2', 77.6, 34.3, 90)             # its amplifier beside it

# power district: TPS48000 over the FETs, back to back, sources facing
fix('Q1', 50.0, 25.0, 90)
fix('Q2', 57.5, 25.0, 270)
fix('U1', 53.75, 17.0, 180)

# Limit rocker: two switches under the paddle's ends, the beeper between them
fix('SW2', 60.0, 45.5, 0)
fix('SW3', 80.0, 45.5, 0)
fix('BZ1', 70.0, 45.5, 0)

# under the screen
fix('U5', 34.0, 15.2, 90)             # MCU, tight under the resistors
fix('J7', 43.0, 17.3, 90)             # display FPC (the tail folds back under the module)
fix('Q3', 19.0, 14.6, 270)            # pre-charge FET: tab (drain) north toward the resistors
fix('Q11', 19.5, 27.5, 90)            # battery-minus FET between the two minus pins and ground

# ================================================================ anchors (legalised)
# battery gate: one input cap in the pocket over the XT60, the damper's caps
# in the pocket under the XT30, the TVS and the rest in front of the 2S/3S sockets
at('C1', 12.6, 10.3, 0)
at('C3', 16.4, 22.0, 90)
at('R74', 20.4, 23.7, 0)
at('D20', 25.0, 23.4, 0)
at('C50', 11.4, 44.3, 90)
at('C51', 11.4, 49.0, 90)
at('R67', 16.9, 33.0, 0)
at('D1', 16.45, 37.8, 0)
at('C2', 22.9, 31.9, 0)

# pre-charge gate, between the FET and the MCU
at('D3', 24.35, 12.9, 270)                # PRE_D (Q3 tab) -> PRE_K (resistors)
at('R20', 25.55, 17.55, 0)
at('D19', 25.6, 19.4, 0)
at('D2', 19.9, 20.3, 0)
at('R19', 19.9, 22.0, 0)
for ref, (x, y, r) in {'Q4': (48.4, 32.4, 0), 'Q5': (48.4, 35.4, 0), 'R21': (50.6, 31.6, 90),
                       'R22': (50.6, 35.4, 90), 'R23': (46.2, 31.6, 90), 'R24': (46.2, 35.4, 90)}.items():
    at(ref, x, y, r)
at('RT2', 58.6, 9.4, 0)                  # thermistor at the resistors' drone-side lead
at('R25', 60.4, 9.4, 90)

# balance row-houses: one column per tap, under the screen's front edge,
# facing the MCU's ADC pins; the taps' OR diodes beside them
for i, k in enumerate(range(2, C.BALANCE_MAX + 2)):
    parts_k = [r for r, c in C.COMPONENTS.items() if c['group'] == 'balance' and not r.startswith('J')
               and any(n in (f'BAL{k}', f'BAL{k}_ADC') for n in c['pins'].values())]
    d = [r for r in parts_k if r.startswith('D')][0]
    cap = [r for r in parts_k if r.startswith('C')][0]
    rs = [r for r in parts_k if r.startswith('R')]
    top = [r for r in rs if f'BAL{k}' in C.COMPONENTS[r]['pins'].values()][0]
    bot = [r for r in rs if r != top][0]
    x = 28.6 + 1.95 * i
    at(top, x, 23.5, 90)
    at(bot, x, 26.6, 90)
    at(cap, x, 29.15, 90)
    # the taps' OR diodes: four over the 3S socket, two over the 4S
    at(d, *((21.0 + 1.6 * i, 35.55) if i < 4 else (28.0 + 1.5 * (i - 4), 32.5)), 90)
at('R75', 31.6, 32.5, 90)               # balance black wire -> ground
at('Q8', 42.7, 28.0, 0)
at('R52', 39.9, 28.0, 90)

# MCU neighbours
col(['C34', 'C38', 'C36'], 26.75, 9.6, 2.0, 90)     # west of the MCU, beside D3
at('C35', 40.0, 23.0, 90)
at('C37', 25.6, 21.4, 0)
fix('J6', 34.0, 15.2, 0, 'B')           # SWD pogo pads on the underside, under the MCU (factory jig)

# display: the backlight FET and its four LED resistors beside the FPC
at('Q9', 47.0, 10.4, 0)
at('R60', 49.4, 10.2, 90)
col(['R56', 'R57', 'R58', 'R59', 'C41'], 46.35, 12.78, 1.65, 0)

# power district passives round the TPS48000: a row above it, a 2 x 3 grid east
for ref, (x, y, r) in {
    'R13': (49.6, 12.4, 90), 'R2': (51.2, 12.4, 90), 'R3': (52.8, 12.4, 90), 'R4': (54.4, 12.4, 90),
    'R5': (56.0, 12.4, 90), 'R8': (57.6, 12.4, 90),
    'R9': (49.6, 16.6, 90), 'R10': (49.6, 19.0, 90), 'C5': (50.8, 21.0, 0),
    'R6': (57.2, 16.05, 90), 'R7': (57.2, 18.1, 90), 'R69': (57.2, 20.15, 90),
    'R11': (58.5, 16.05, 90), 'R12': (58.5, 18.1, 90), 'C54': (58.5, 20.15, 90),
    'R1': (59.2, 13.4, 90), 'C4': (60.8, 13.4, 90),
    'D18': (53.75, 29.6, 0), 'RT1': (50.0, 29.6, 0), 'R35': (50.0, 30.75, 0),
}.items():
    at(ref, x, y, r)

# pre-charge driver (cascode) east of the 6S socket, its resistors in a column
at('Q4', 50.4, 32.85, 0)
at('Q5', 50.4, 35.9, 0)
col(['R21', 'R23', 'R22', 'R24'], 53.5, 32.0, 1.58, 0)

# the logic street under the ring, three rows:
#   enable gate, latch, peak comparator and its reference
#   3V3 LDO, high-side comparator and its reference
#   current-sense RC, toggle input filters
for ref, (x, y, r) in {
    'U7': (55.85, 32.4, 0), 'C12': (57.7, 32.4, 90), 'U9': (60.2, 32.4, 0), 'C11': (62.7, 32.4, 90),
    'U8': (65.35, 32.4, 0), 'C10': (68.0, 32.4, 90), 'R17': (69.35, 32.4, 90), 'C9': (70.65, 32.4, 90),
    'R66': (71.95, 32.4, 90),
    'U4': (56.65, 36.0, 0), 'C32': (59.55, 36.0, 90), 'C33': (61.4, 36.0, 90), 'U12': (64.35, 36.0, 0),
    'R70': (67.0, 36.0, 90), 'R71': (68.35, 36.0, 90), 'C55': (69.65, 36.0, 90), 'C56': (70.75, 36.0, 90),
    'R16': (58.6, 39.3, 0), 'C8': (60.8, 39.3, 0), 'R54': (63.05, 39.3, 0), 'C39': (65.25, 39.3, 0),
    'R55': (67.5, 39.3, 0), 'C40': (69.75, 39.3, 0),
}.items():
    at(ref, x, y, r)

# current sense round the amplifier, beside the shunt; the hall switch's cap
for ref, (x, y, r) in {
    'R14': (79.6, 31.4, 0), 'C6': (77.6, 31.4, 0), 'R15': (79.35, 37.95, 0), 'C7': (77.3, 36.9, 0),
    'C13': (73.2, 38.8, 0), 'C14': (83.0, 28.4, 0),
}.items():
    at(ref, x, y, r)

# drone side: snubber by the leads; probe and sensing along the front
for ref, (x, y, r) in {
    'R68': (76.1, 40.2, 90), 'C52': (79.0, 40.9, 90), 'C53': (82.5, 40.9, 90),
    'Q6': (52.6, 39.4, 0), 'Q7': (55.6, 39.4, 0), 'R26': (52.6, 42.0, 90), 'R27': (54.0, 42.0, 90),
    'R72': (51.2, 42.0, 90), 'R73': (55.4, 42.0, 90), 'R18': (56.8, 42.0, 90),
    'R28': (49.6, 44.4, 90), 'R29': (51.4, 45.0, 90), 'D4': (53.4, 45.0, 90),
    'R30': (55.2, 45.0, 90), 'R31': (56.6, 45.0, 90), 'C15': (57.4, 48.6, 90),
    'R32': (49.6, 48.2, 90), 'D5': (52.3, 48.6, 0), 'C16': (54.8, 48.6, 90),
    'R33': (63.8, 43.0, 90), 'R34': (63.8, 46.0, 90), 'C17': (63.8, 48.8, 90),
}.items():
    at(ref, x, y, r)

# beeper driver between the beeper and the right switch
at('R61', 75.4, 45.6, 90)
at('D17', 76.9, 45.4, 90)
at('Q10', 77.4, 49.4, 0)

# status ring: its six 100 nF inside the ring, three each side of the toggle;
# the driver at 7 o'clock by LED1
col(['C48', 'C43', 'C44'], TOG[0] - 5.7, TOG[1] - 3.5, 3.5, 90)
col(['C47', 'C46', 'C45'], TOG[0] + 5.7, TOG[1] - 3.5, 3.5, 90)
at('U10', 64.7, 28.4, 0)
at('C42', 68.4, 30.3, 0)

# USB-C beside its port: ESD, CC pull-downs, VBUS sense
at('U11', 63.6, 11.7, 90)
row(['R62', 'R63', 'R64', 'R65'], 61.6, 8.8, 1.2, 90)
at('C49', 70.9, 9.6, 90)

# aux supply, back right: OR diodes -> filter -> buck -> output caps
col(['D14', 'D15', 'D16'], 73.6, 1.6, 1.7, 0)
at('R53', 77.4, 1.75, 0)
at('C26', 81.7, 1.75, 0)
at('C27', 81.6, 3.75, 0)
at('U3', 77.9, 4.6, 0)
at('C28', 75.45, 7.25, 90)
at('C29', 77.9, 7.4, 0)
at('L1', 81.6, 6.8, 0)
at('C30', 81.9, 10.1, 0)
at('C31', 81.9, 12.2, 0)
