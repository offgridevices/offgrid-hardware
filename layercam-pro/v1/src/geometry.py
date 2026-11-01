# -*- coding: utf-8 -*-
"""Every mechanical number the board shares with the case.

The case is Prusa's printed case for the Buddy3D camera (Printables model
1343977, GPL v2: buddy-camera-bottom-r2, -top-r1, -lid-r1) on the OUTSIDE,
with a new inside (enclosure/).  The numbers below were measured from
Prusa's STL files (src/plan_section.py has the assembly and the method).

The "lens frame" (as LayerCam v1): origin on the lens axis at the case's
outer front face, +Z into the case; X, Y across the front face as seen from
BEHIND the camera, +Y towards the case's straight (top) edge.  Board
coordinates (pcb.py) are X and y = -Y, KiCad's y pointing down the screen.
F (KiCad's top) is the board's BACK face, towards the lid; B is the FRONT
face, the lens side.
"""
import math

# ---------------------------------------------------------------- the board
BOARD_Z = 21.0            # front face (lens side); 1.6 mm thick, back face at 22.6
BOARD_T = 1.6
# The outline: Prusa's case outside at Z 21.0-22.6 (the convex outline of
# its section, where the case is widest), less 2.5 mm (a 2.0 mm wall and
# 0.5 mm clearance), simplified.  Lens frame X, Y.
OUTLINE = [
    (-15.05, -29.20), (-16.75, -28.22), (-31.56, -2.57), (-32.64, -0.35), (-32.30, 1.30),
    (-15.92, 29.27), (15.83, 29.32), (32.30, 1.31), (32.54, -0.79), (16.16, -28.90),
]
# M2 holes into printed bosses; each at least 3.0 mm from the edge
# (verify.py), clear of the lens holder and the heatsink
SCREWS = [(-13.0, 25.5), (13.0, 25.5), (-13.0, -25.3), (13.0, -25.3)]
SCREW_D = 2.2
BOSS_D = 4.5              # the boss under the board (front face): no part within this
CORNER_CLEAR = 0.6        # copper and parts keep this far from the edge (the case is carbon-filled: it conducts a little)

# ---------------------------------------------------------------- lens stack
# Lens: Towin CCL127028MPR (M12, 2.8 mm, IR corrected, total track 20.9)
# in a Commonlands CLA219 IR-cut holder screwed to the board's front face
# over the image sensor.  The sensor's image plane is about 0.7 mm in front
# of the board, Z 20.3: the lens's front lands about 0.6 mm proud of the
# case's front face, inside the M12 thread's +-2 mm of focus travel.
BORE_D = 14.9                              # the lens bore through the front face (Prusa)
HOLDER_BOX = (-10.6, -9.8, 10.6, 9.8)      # CLA219 base with its ears: a full rectangle (lens frame)
HOLDER_SCREWS = [(-9.0, 0.0), (9.0, 0.0)]  # its two M1.6 self-tapping screws, from the back face
HOLDER_SCREW_D = 1.8
HOLDER_H = 9.5
# The image sensor (SmartSens SC4336H, 35-ball CSP), on the front face, its
# optical centre on the lens axis.
SENSOR_SIZE = (5.7, 3.7)                   # the SC4336P-family CSP-35 (EasyEDA C9900187041)

# ---------------------------------------------------------------- IR lights
# Prusa's six front holes, Ø2.4 at R 13.0, every 60 degrees from +X, and the
# light window Ø5.8 at (0, -14.15).  The LEDs sit on the board's front face;
# a 2 mm clear rod in a printed channel carries each one's light to its
# hole.  At 0 and 180 degrees the LED is straight under its hole; the other
# four would sit under the IR-cut holder's base, so they move out to R 14.4
# and their rods lean about 4 degrees to reach the holes.
HOLE_R = 13.0
LED_ANGLES = [0, 60, 120, 180, 240, 300]
LED_R = {0: 13.0, 180: 13.0, 60: 14.4, 120: 14.4, 240: 14.4, 300: 14.4}
LED_HOLE_D = 2.4
ROD_D = 2.0
LIGHT_WINDOW = (0.0, -14.15)
LIGHT_WINDOW_D = 5.8


def led_xy(a):
    """An LED's centre on the board, lens frame."""
    r = LED_R[a]
    return (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))


def hole_xy(a):
    return (HOLE_R * math.cos(math.radians(a)), HOLE_R * math.sin(math.radians(a)))


# ---------------------------------------------------------------- main chip, heatsink
# The lid's six vent slots span X -10..10, Y -15.5..6.5; the sensor is on
# the axis.  The RV1106 on the back face at (0, -15): a 20 x 20 x 15 mm
# heatsink on it fits in the case at every height and has three slots over
# it (plan_section.py checks it).
SOC_XY = (0.0, -15.0)
HEATSINK = (20.0, 20.0, 15.0)
UNDER_HEATSINK_MAX_H = 0.8    # parts under the heatsink's overhang (its base on the 0.85 mm package + 0.25 mm tape)

# ---------------------------------------------------------------- USB-C
# Prusa's opening is in the case's -X facet, centred at (-33.1, 8.9, 26.6),
# its plug axis 150 degrees from +X across the face and tilted 28 degrees
# to the front.  The board's edge there runs at 60 degrees, so its outward
# normal is 149.6 degrees: a receptacle on that edge points the way Prusa's
# does across the face, level instead of tilted.  The board has a tab there
# so the receptacle's mouth reaches the case wall.
USB_EDGE_XY = (-27.85, 8.9)                # on the edge, lens frame
USB_NORMAL_DEG = 149.6
USB_TAB = 2.2                              # how far the tab stands out from the edge
USB_TAB_W = 10.4

# ---------------------------------------------------------------- Wi-Fi
# ESP32-C6-MINI-1U-H4 on the back face; its U.FL takes a short U.FL to
# RP-SMA bulkhead lead to the case wall (enclosure/).
