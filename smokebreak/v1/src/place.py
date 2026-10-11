"""SmokeBreak v1: where every part goes.

The board is planned like a city: districts with one job each, streets
between them, parts in rows, every part of a kind facing the same way.

    back edge    supply block | balance connector + divider row-houses | USB-C | pre-charge resistor
    west gate    battery in: XT60 + XT30 male, TVS, input capacitors
    downtown     the MCU under the screen, its ADC side facing the dividers
    east         the Arm: the toggle in its status ring, the guard's hall sensor
    south-east   power district: TPS48000, the two FETs back to back
    east gate    drone out: XT60 + XT30 female, the shunt and its amplifier between them
    south-west   the Limit rocker's two switches with the beeper between them

Coordinates: mm from the board's back-left corner, x right, y towards the
user.  Each entry: (x, y, rotation degrees, side, fixed).  Fixed parts are
where the case, the connectors or the physics put them; the others are
anchors that make.py's legaliser nudges (0.25 mm grid, nearest free spot)
until no two courtyards touch.

Mechanical stack (sets every height on this board): the PCB's top face is
11.5 mm below the underside of the top panel, so the XT connectors' axes
sit at the body's mid-height (as in design/arm).  The toggle (8.89 mm
PCB-to-shoulder) seats against a 2.6 mm printed boss under the panel.
Under the screen (board x 2.5-48.5, y 5-31) parts must stay below 8.5 mm:
the tallest is the XT60 at 8.1 mm.
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


# ================================================================ fixed by the case and the physics
for i, (x, y) in enumerate(B.HOLES, 1):
    fix(f'H{i}', x, y)

# the Arm: toggle under the face's toggle, status ring round its bushing
TOG = (67.0, 28.0)
RING_R = 9.5
fix('SW1', *TOG, 0)
for i in range(12):
    a = math.radians(120 + 30 * i)                       # LED1 at 7 o'clock (its driver sits there), clockwise
    # pads square to the board (the router and the paste stencil like that);
    # the light pipe evens out each LED's own turn
    fix(f'LED{i + 1}', TOG[0] + RING_R * math.cos(a), TOG[1] + RING_R * math.sin(a), -90 * round((i + 7) / 3))
fix('U6', 65.6, 42.6, 0)                                 # hall switch under the guard's tip magnet

# gates: connector faces flush with the 3 mm walls (outer faces at x -3 and x 97)
fix('J1', 10.2, 20.0, 0)              # XT60 male
fix('J2', 6.5, 38.5, 270)             # XT30 male
fix('J3', 84.4, 19.0, 270)            # XT60 female
fix('J4', 85.3, 39.0, 90)             # XT30 female
fix('J8', 57.0, 4.3, 180)             # USB-C through the back wall
fix('J5', 38.0, 8.4, 0)               # JST-XH 9 balance, through the back wall
fix('R_PRE', 75.0, 4.4, 0)            # the two 5 W pre-charge resistors, in rows along the back,
fix('R_PRE2', 67.5, 12.6, 0)          # FET side (PRE_K) west, drone side (VOUT) east

# controls under the Limit rocker's ends, the beeper between them
fix('SW2', 15.5, 42.5, 0)
fix('SW3', 35.5, 42.5, 0)
fix('BZ1', 25.5, 46.3, 0)

# downtown and the power district
fix('U5', 38.0, 31.5, 90)             # MCU: ADC pins north, control pins south, toggle pins east
fix('J7', 52.5, 27.6, 90)             # display FPC, entered from the screen side (west)
fix('Q3', 52.4, 12.8, 90)             # pre-charge FET: source (VIN) north, drain tab south
at('D3', 57.4, 17.6, 90)
fix('Q1', 71.25, 47.2, 90)             # back to back, sources facing
fix('Q2', 78.75, 47.2, 270)
fix('RS1', 83.4, 29.5, 90)            # shunt between the drone connectors' negatives, force pads west->east
fix('U2', 89.4, 29.5, 90)             # its amplifier right beside it

# ================================================================ anchors (legalised)
# status ring: one 100 nF per LED pair, just outside the ring
for k in range(6):
    a = math.radians(-90 + 60 * k + 15)
    at(f'C{43 + k}', TOG[0] + 12.0 * math.cos(a), TOG[1] + 12.0 * math.sin(a), -(60 * k + 15) + 90)
at('U10', 58.6, 39.4, 0)
at('C42', 58.6, 42.0, 0)
at('C13', 64.6, 43.6, 90)

# battery gate
at('D1', 17.2, 20.0, 90)
at('C1', 21.6, 18.2, 0)
at('C2', 21.6, 21.8, 0)
at('C3', 17.2, 24.6, 0)

# supply block (north-west): OR diodes -> filter -> buck -> LDO
at('D14', 9.2, 7.6, 0)
at('D15', 9.2, 9.3, 0)
at('D16', 9.2, 11.0, 0)
at('R53', 11.8, 9.3, 90)
at('C26', 14.2, 9.3, 90)
at('C27', 16.4, 9.6, 90)
at('U3', 18.6, 9.6, 0)
at('C28', 18.6, 6.8, 0)
at('C29', 18.6, 12.1, 0)
at('L1', 22.4, 9.6, 0)
at('C30', 21.2, 4.4, 90)
at('C31', 23.4, 4.4, 90)
at('U4', 16.4, 3.4, 90)
at('C32', 12.6, 2.6, 0)
at('C33', 12.6, 4.6, 0)

# balance row-houses: one column per tap under its pin, 2.5 mm apart
pin_x = {k: 48.0 - (k - 1) * 2.5 for k in range(1, 10)}
for k in range(2, 10):
    parts_k = [r for r, c in C.COMPONENTS.items() if c['group'] == 'balance' and r != 'J5'
               and any(n in (f'BAL{k}', f'BAL{k}_ADC') for n in c['pins'].values())]
    d = [r for r in parts_k if r.startswith('D')][0]
    cap = [r for r in parts_k if r.startswith('C')][0]
    rs = [r for r in parts_k if r.startswith('R')]
    top = [r for r in rs if f'BAL{k}' in C.COMPONENTS[r]['pins'].values()][0]
    bot = [r for r in rs if r != top][0]
    x = pin_x[k]
    at(d, x, 13.0, 90)
    at(top, x, 16.55, 90)
    at(bot, x, 19.7, 90)
    at(cap, x, 22.25, 90)
at('R75', 48.0, 13.4, 90)               # balance black wire -> ground, under pin 1's column
at('Q8', 25.6, 19.6, 0)
at('R52', 25.6, 22.6, 90)

# MCU neighbours
at('C34', 45.2, 32.2, 90)
at('C35', 46.6, 32.2, 90)
at('C37', 45.6, 35.2, 0)
at('C36', 38.0, 24.4, 0)
at('C38', 45.2, 29.4, 90)
at('J6', 28.4, 34.0, 90)

# display
at('C41', 49.0, 14.0, 90)
for i, ref in enumerate(['R56', 'R57', 'R58', 'R59']):
    at(ref, 53.6 + 1.2 * i, 32.4, 90)
at('Q9', 54.8, 35.6, 0)
at('R60', 52.2, 35.6, 90)

# power district: TPS48000 north of the FETs, its passives around it
fix('U1', 74.6, 41.4, 180)             # TPS48000 right above the FETs: GATE over Q1's gate, SRC over the source copper
for ref, (x, y, r) in {
    'C5': (71.2, 43.4, 0), 'R6': (78.4, 43.2, 0), 'R7': (78.4, 41.4, 0),
    # VS filter at pin 20 (east end), the dividers and pull-ups in a row north of the control pins
    'R1': (79.0, 37.4, 90), 'C4': (80.4, 37.4, 90),
    'R2': (77.6, 37.6, 90), 'R3': (76.2, 37.6, 90), 'R4': (74.8, 37.6, 90), 'R5': (73.4, 37.6, 90),
    'R8': (72.0, 38.0, 90), 'R9': (69.0, 41.0, 90), 'R10': (67.6, 41.0, 90), 'R11': (66.2, 41.0, 90),
    'R12': (64.8, 41.0, 90), 'R13': (63.4, 41.0, 90),
}.items():
    at(ref, x, y, r)
# current sense next to the shunt; peak comparator, latch, enable gate in a row
for ref, (x, y, r) in {
    'R14': (85.8, 28.4, 0), 'R15': (85.8, 30.6, 0), 'C6': (93.2, 29.5, 90),
    'C7': (91.6, 25.6, 0), 'R16': (61.2, 37.4, 0), 'C8': (63.6, 37.4, 0),
    'U8': (55.0, 40.4, 0), 'C10': (55.0, 42.8, 0), 'R17': (52.4, 42.8, 90), 'C9': (53.8, 44.8, 0),
    'U9': (59.2, 40.4, 0), 'C11': (59.2, 42.8, 0),
    'U7': (63.2, 40.6, 0), 'C12': (63.2, 42.4, 0), 'R18': (47.2, 40.6, 0), 'R66': (57.6, 38.2, 0),
}.items():
    at(ref, x, y, r)

# pre-charge, along the back next to its resistor
at('D2', 48.2, 13.0, 90)                # Q3's gate clamp and pull-up beside it
at('R19', 48.2, 16.0, 90)
at('R20', 48.2, 19.2, 90)
at('D19', 48.2, 22.4, 90)
at('Q4', 45.4, 41.0, 0)                 # the AND of MCU and guard, south of the MCU
at('Q5', 45.4, 44.2, 0)
for ref, (x, y, r) in {'R21': (47.6, 41.0, 90), 'R22': (47.6, 44.2, 90), 'R23': (43.4, 41.0, 90),
                       'R24': (43.4, 44.2, 90)}.items():
    at(ref, x, y, r)
at('RT2', 82.0, 9.0, 0)                 # thermistor on the resistors' drone-side leads
at('R25', 84.2, 9.0, 0)

# drone side: probe, VOUT and VIN sensing, south of the MCU
at('C14', 81.2, 23.4, 90)
at('RT1', 69.0, 43.4, 0)                # thermistor at Q1's edge
at('R35', 66.0, 38.4, 0)
for ref, (x, y, r) in {
    'Q6': (40.6, 40.4, 0), 'Q7': (43.4, 40.4, 0), 'R26': (40.6, 44.2, 90), 'R27': (43.4, 44.2, 90),
    'R28': (46.0, 44.2, 90), 'R29': (47.6, 44.2, 90), 'D4': (49.6, 44.2, 90),
    'R30': (40.6, 47.8, 90), 'R31': (42.0, 47.8, 90), 'C15': (43.4, 47.8, 90),
    'R32': (44.8, 47.8, 90), 'D5': (47.0, 47.8, 0), 'C16': (49.0, 47.8, 90),
    'R33': (40.6, 50.6, 0), 'R34': (43.0, 50.6, 0), 'C17': (45.4, 50.6, 0),
}.items():
    at(ref, x, y, r)

# controls, beeper driver, USB
at('R54', 47.2, 37.2, 0)
at('R55', 49.6, 37.2, 0)
at('C39', 47.2, 38.6, 0)
at('C40', 49.6, 38.6, 0)
at('Q10', 31.2, 40.4, 0)
at('R61', 33.6, 40.4, 90)
at('D17', 31.2, 43.0, 90)
at('U11', 47.0, 26.0, 90)
at('R62', 62.4, 8.4, 0)
at('R63', 51.0, 7.0, 0)
at('R64', 55.8, 21.8, 90)
at('R65', 55.8, 24.4, 90)
at('C49', 30.0, 24.6, 0)

# ---------------------------------------------------------------- from the simulations
# battery return: Q11 between the two battery minus pads and the ground plane
fix('Q11', 17.6, 30.2, 90)              # drain (BATT_NEG) west to the connectors, sources east
at('R74', 21.8, 34.6, 90)
at('D20', 21.8, 37.8, 90)
# input damper and output snubber: 0.33 / 0.47 Ohm + 2 x 4.7 uF each
at('C50', 25.0, 28.8, 90)
at('C51', 25.0, 33.2, 90)
at('R67', 25.0, 37.0, 90)
at('C52', 73.6, 26.6, 90)       # snubber caps inside the status ring, beside the toggle
at('C53', 73.6, 31.0, 90)
at('R68', 76.4, 20.6, 90)
at('R69', 70.6, 39.6, 0)                # Cdvdt beside the TPS48000
at('C54', 70.6, 41.2, 0)
at('D18', 78.6, 39.4, 0)                # gate clamp across Q1/Q2
at('U12', 61.6, 47.4, 0)                # hard-short comparator among the controller's passives
at('R70', 59.4, 46.2, 90)
at('R71', 59.4, 48.8, 90)
at('C55', 63.6, 46.0, 90)
at('C56', 63.6, 48.8, 90)
at('R72', 37.8, 41.0, 90)               # probe base resistors
at('R73', 39.0, 41.0, 90)
