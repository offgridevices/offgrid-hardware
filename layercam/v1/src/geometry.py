# -*- coding: utf-8 -*-
"""Every mechanical number the boards share with the housing.

The housing is Prusa's own printed case for the Buddy3D camera (Printables
model 1343977: buddy-camera-bottom-r2, -top-r1, -lid-r1), unchanged.  These
numbers were measured from its STEP and STL files on 26 Oct 2026
(docs/housing.md has the method and the sections).

The "lens frame": origin on the lens axis at the outer front face, +Z
towards the back (into the case), X and Y across the front face as seen from
BEHIND the camera (the way the boards are drawn), +Y towards the case's
straight edge, -Y towards its round edge.  Board coordinates (pcb.py) are
these X, Y with KiCad's y pointing down the screen, so board y = -Y.
"""

# ---------------------------------------------------------------- main board
# Four printed bosses (pilot holes for M2 self-tapping screws, Ø1.7, 5.55
# deep).  Their tops are the board seat: the board's FRONT face (the lens
# side) rests on them at Z = 19.3.
SEAT_Z = 19.3
SCREWS = [(-16.07, -21.15), (16.08, -21.15), (-16.07, 20.95), (16.08, 20.95)]
SCREW_D = 2.2                 # board hole for an M2 (clearance)
BOSS_D = 3.5                  # the boss under the board: no part within this on the front

# The pocket at the seat, Z 19.4-20.9, measured, then 0.4 mm clearance; the
# board takes a simpler outline inside that: straight sides at X = +-19.0,
# a straight edge at Y = +22.9 (the pocket's bump beyond it is left free for
# wires), and an arc at -Y through (0, -29.2), centre (0, 2.1).
MAIN_HALF_W = 19.0
MAIN_TOP_Y = 22.9
# ... and a tab into the pocket's bump at the middle of the straight edge
# (measured: the bump is 15.0 wide at Y 24.4 with the clearance), so the
# Wi-Fi module fits between the edge and the lens holder
MAIN_TAB = [(-8.5, 22.9), (-7.0, 24.4), (7.0, 24.4), (8.5, 22.9)]
MAIN_ARC_C = (0.0, 2.1)
MAIN_ARC_R = 31.3

# The pocket's outline at the seat (lens frame X, Y), measured from Prusa's
# STEP and shrunk by the 0.4 mm clearance: verify.py checks the main
# board's outline lies inside it.
POCKET = [
    (-19.121, 22.999), (-9.512, 23.019), (-9.256, 23.134), (-7.178, 24.735), (-5.106, 25.938),
    (-4.089, 26.869), (-2.892, 27.684), (-1.425, 28.283), (-0.001, 28.475), (1.437, 28.282),
    (2.887, 27.691), (4.098, 26.869), (5.114, 25.938), (7.187, 24.735), (9.265, 23.134),
    (9.521, 23.019), (19.129, 22.999), (19.129, -22.868), (17.487, -24.054), (14.800, -25.677),
    (11.898, -27.047), (10.366, -27.631), (7.285, -28.536), (5.614, -28.890), (2.432, -29.302),
    (0.794, -29.387), (-2.484, -29.298), (-5.666, -28.878), (-7.336, -28.522), (-10.415, -27.610),
    (-13.745, -26.222), (-14.048, -26.264), (-14.360, -26.576), (-17.035, -25.060), (-19.121, -23.620),
]

# Free height above each face (from the housing, lens frame Z):
#   front (lens side, Z < 19.3): down to Z 9.5 over the whole board (so
#     9.8 mm), and to the LED ring at Z ~3.6 in a circle round the lens.
#   back (Z > 20.9 with a 1.6 mm board): 7.7 mm everywhere, 10 mm inside
#     X +-13.6, Y -18..15, 17.5 mm in the lid's vent window X -11..12,
#     Y -20..10.
FRONT_FREE = 9.8
BACK_FREE = 7.7
BACK_FREE_CENTRE = 10.0

# The lens bore in the front face: Ø14.9, Z 0-3.6.  The lens's front must be
# no wider; lens + holder + IR-cut, from the camera module's sensor board to
# the front face, must fit Z 2-19.3.
BORE_D = 14.9

# ---------------------------------------------------------------- LED ring
# Six IR LED holes Ø2.4 at R 13.0, every 60 degrees from +X; a light window
# Ø5.8 at (0, -14.15).  The ring board sits at Z 2.0-3.6 on two locating
# pins at (+-8.5, 0.2).
LED_R = 13.0
LED_ANGLES = [0, 60, 120, 180, 240, 300]
LED_HOLE_D = 2.4
LIGHT_WINDOW = (0.0, -14.15)
LIGHT_WINDOW_D = 5.8
RING_PINS = [(-8.5, 0.2), (8.5, 0.2)]
RING_Z = (2.0, 3.6)

# ---------------------------------------------------------------- USB-C board
# A separate board slides into two grooves in the top shell, behind an
# obround opening (9.4 x 3.8 mm) in the shell's -X facet.  In the slot's own
# frame (u along the plug, out of the case; v along the receptacle's long
# side; n the board normal) the grooves take a board 22.0 wide
# (v -7.9 .. +14.1) and 1.2 thick (n -2.6 .. -1.4) whose edge stops at the
# wall's inside face (u = -1.7); the opening is centred at v 0, n +0.2.
USB_W = 22.0
USB_L = 16.0
USB_T = 1.2
USB_V0 = -7.9                 # the board's edge at v = -7.9; the receptacle centre at v = 0

# ---------------------------------------------------------------- camera stack
# The SC3336 (B) module sits BEHIND the main board, its sensor face towards
# the board's back face, 1.0 mm away (two M1.6 x 1.0 nylon washers on the
# holder screws).  The sensor looks forward through a window in the main
# board; the CLA219 IR-cut holder sits on the board's front face over the
# window, and two M1.6 screws through the module's holder holes, the
# washers and the board clamp all three.  Lens: Towin CCL127028MPR
# (2.8 mm, F2.5, IR corrected, TTL 20.9): its front lands ~0.2 mm behind
# the housing's front face (docs/housing.md has the stack).
MODULE_W, MODULE_H = 25.0, 24.0            # SC3336 (B); its FFC connector edge towards +Y
# the lens is not in the module's middle: Luckfox's drawing ("SC3336 3MP
# Camera (B)", wiki.luckfox.com) puts the axis 8.4 from the far edge and
# 15.6 from the connector edge (the holder holes, 18 apart, on the axis).
# Its FFC connector is on the module's back, mouth at the edge, its 20
# contacts centred on the axis, pin 1 at -X.
MODULE_TO_FFC_EDGE = 15.6                  # lens axis to the module's connector edge (+Y)
MODULE_TO_FAR_EDGE = 8.4                   # lens axis to the opposite edge (-Y)
MODULE_SHIM = 1.0                          # gap between the module's sensor face and the board
MODULE_PCB_T = 1.2
WINDOW = (14.4, 14.4)                      # through the main board, centred on the lens axis
HOLDER_SCREWS = [(-9.0, 0.0), (9.0, 0.0)]  # CLA219 and the module's holder holes, 18 mm apart
HOLDER_SCREW_D = 1.8                       # M1.6 clearance
HOLDER_BOX = (-10.6, -9.8, 10.6, 9.8)      # CLA219 body and ears on the front face (X0, Y0, X1, Y1)
# parts on the back face under the module must clear the 1.0 mm shim
UNDER_MODULE_MAX_H = 0.6

# ---------------------------------------------------------------- SoC heatsink
# A stock 14 x 14 x 10 mm aluminium heatsink on thermal tape, stuck on the
# RV1106 (back face).  The case's rounded end leaves 10 mm only from here:
# centred at board (0, 15.9) it covers 9.65 mm of the 12.3 mm package and
# overhangs its -y edge by 4.3 mm (mechanical/heat-plate/README.md).  Its
# base sits on the package (0.85 mm) and the tape (0.25 mm): parts under
# the overhang 0.8 mm or lower (a 0.80 mm package leaves 1.05 mm under it).
HEATSINK_C = (0.0, 15.9)                   # board coordinates
HEATSINK_SIZE = 14.0
UNDER_HEATSINK_MAX_H = 0.8

# ---------------------------------------------------------------- LED ring board
RING_OUT_R = 16.5
RING_IN_R = 9.55                           # the housing's collar is R 9.3
RING_KEYS_DEG = [0, 90, 180]               # the collar's keys at +X, +Y, -X (lens frame)
RING_KEY_R = 10.7
RING_KEY_W = 2.8

# ---------------------------------------------------------------- USB board frame
# board coordinates: y into the case from the mouth (-u), the mouth's centre
# at (0, 0) on the board edge, and x = -v.  The board is drawn from its parts'
# face, which faces the slot's +n (the receptacle sits in the opening at
# n +0.2); seen from there, with y into the case, v runs right to left.  (It
# was once drawn with x = v: a mirror image, whose long side would have met
# the wall where the grooves are short.  verify.py checks this.)
USB_BOX = (-(USB_V0 + USB_W), 0.0, -USB_V0, USB_L)
