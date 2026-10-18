#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print Hub v1 enclosure: a base tray and a lid, parametric, build123d 0.13.

Run it in the ogkicad-printhub:1 image from this folder:

    docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp \
        -v /home/user/offgrid-hardware:/w \
        -w /w/print-hub/v1/mechanical/enclosure ogkicad-printhub:1 python3 enclosure.py

It writes, next to itself:
    printhub-base.stl            base, in its print orientation (floor on the bed)
    printhub-lid.stl             lid, in its print orientation (top face on the bed)
    printhub-feet.stl            the four printed feet, upright
    printhub-enclosure-step.zip  all parts in their assembled position (zipped STEP)
    printhub-preview.png         assembled iso view + exploded view
    printhub-views.png           top, back, underside and the lid's heat pads from below
    case_gaps.json               the air gaps between the board and the case, for
                                 sim/thermal/board_heat.py
and runs the fit check (also on its own: python3 enclosure.py --check-only;
--no-check skips it).
The exit code is 1 if any fit-check line FAILs.

COORDINATES.  Every position below is written in the board's KiCad
coordinates, as in the layout: millimetres from the board centre, x to the
right, y towards the FRONT edge (the USB-A side), z up from the board's
bottom face.  KiCad's y axis points down the screen, so a right-handed 3D
model needs y flipped: the helpers kbox()/kcbox()/kcyl()/ktext() do that, and the
exported files have +Y pointing to the BACK of the box (USB-C side), +Z up.
Building straight in KiCad (x, y) would give a mirror image of the real box.

THE SPLIT.  The base and the lid meet on one flat plane just above the
board's top face (SPLIT_Z).  The base is a shallow tray with the standoffs;
the board drops into it; the lid carries everything above the board and its
connector cut-outs are notches open at its bottom edge, so it lowers straight
down over the connectors.

HEAT.  The lid's underside steps down to just above the parts (heat pads)
and the base's floor sits 1 mm under the board, so the heat crosses thin air
gaps to the case instead of 8 mm above and 4 mm below.  Printed feet keep the
floor's outer face in free air.  The gaps go out in case_gaps.json.

THE FRONT WALL.  The USB-A mouths sit only 0.5-0.6 mm past the board edge,
and a plug's overmould has to reach within ~0.5 mm of the mouth.  A normal
wall (outside the board edge plus fit clearance) would put the mouths 1.7 mm
behind its outer face.  So the front wall is moved back over the board: its
outer face is MOUTH_SETBACK in front of the mouths and it is a full WALL thick
above and below the board.  The board's front edge slips into a slot in it;
only the strip directly in front of the board edge (FRONT_SKIN, ~0.6 mm) is
thinner.  The strip of board under the wall carries nothing but the USB-A
receptacles (layout.py), so the lid's wall presses right on it between them.
"""
import gzip
import math
import os, zipfile
import shutil
import sys
import tempfile

from build123d import Box, Compound, Cylinder, Pos, Rot, export_step, export_stl, extrude

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_V1 = os.path.normpath(os.path.join(HERE, '..', '..'))          # print-hub/v1
STEP_DIR = os.path.join(REPO_V1, 'ph.3dshapes')
FONT_MONO = os.path.join(REPO_V1, 'fonts', 'JetBrainsMono-VariableFont.ttf')

# =============================================================================
# 1. THE BOARD (from the routed board, ../../print-hub.kicad_pcb; KiCad coordinates)
# =============================================================================
BOARD_W = 86.0             # board width, x (src/pcb.py W)
BOARD_D = 50.0             # board depth, y (src/pcb.py H)
BOARD_T = 1.6              # board thickness
HX, HY = BOARD_W / 2, BOARD_D / 2
# M3 mounting holes (src/pcb.py HOLES): only two, the back-left corner and
# left of the ESP32 module.  The front edge is held by the case itself: the
# lid's front wall presses on it and a ledge in the base carries it (section 3).
HOLES = [(-39.5, -21.5), (7.0, -2.5)]
HOLE_D = 3.2               # plated hole diameter
KEEP_CLEAR_R = 3.5         # no parts on the board within this radius of a hole

# ESP32-S3 module and its PCB antenna (back-right corner); module origin (33.0, -8.4)
ESP_X = (23.2, 42.8)        # module courtyard, x (the body is 24.0..42.0)
ESP_Y = (-25.0, 0.6)        # module body, y (25.5 mm long, antenna end flush with the back edge)
ANTENNA_Y = (-25.0, -18.4)  # antenna area (the module's first 6.6 mm)
ANTENNA_METAL_KEEPOUT = 10.0  # no screws or inserts closer than this to the antenna area

# =============================================================================
# 2. CONNECTORS AND PARTS (measured from the STEP models in ../../ph.3dshapes)
# =============================================================================
# USB-A receptacle, USB-AF-90 through-hole.  The EasyEDA STEP is centred on
# its shell, mouth towards -y(STEP), with the board's top face at z = -3.85
# (STEP).  Matching its pin rows to the footprint's pads (signal row at
# y = -1.36, shield legs at +1.36) puts the footprint origin 4.5 mm behind
# the shell centre.  Results, relative to the board:
USBA_PITCH = 17.0                          # src/layout.py PITCH
USBA_X = [-34.0, -17.0, 0.0, 17.0, 34.0]   # port 1..5 centres
USBA_FP_Y = 14.0                           # footprint origin y (src/layout.py USBA_Y = HY - 11)
USBA_STEP_Z_BOARDTOP = -3.85               # STEP z of the board's top face
USBA_STEP_DY = 4.5                         # footprint origin -> STEP origin, along +y (towards the mouth)
USBA_MOUTH_Y = USBA_FP_Y + 11.5            # mouth plane, 25.5 (the STEP; the footprint courtyard says 25.6)
USBA_MOUTH_Y_SPEC = HY + 0.6               # the board notes: 0.6 mm past the front edge; the flush check uses both
USBA_REAR_Y = USBA_FP_Y - 2.5              # back of the shell
USBA_HALF_W = 7.20           # half width of the mouth flange (the shell itself is +-6.55)
USBA_MOUTH_Z = (0.35, 7.35)  # mouth flange, height above the board's top face
USBA_TOP = 7.35              # tallest point above the board's top face (top flange lip)
USBA_PIN_BELOW_MEASURED = 2.40   # shield legs below the board's bottom face (STEP: 4.0 below the top)
USBA_PIN_HALF_W = 7.78       # shield legs splay out to +-7.78 (neighbours' legs 1.4 mm apart at 17 mm pitch)
USBA_PIN_Y = (USBA_FP_Y - 2.2, USBA_FP_Y + 4.5)   # where the pins are, y
# USB-C receptacle, TYPE-C-31-M-12 (top mount).  STEP body 8.94 x 7.9 x 3.2,
# 0.05 above the board; the footprint is rotated 180 so the mouth faces -y.
USBC = {'POWER': -30.0, 'DATA': -2.0}       # label -> receptacle centre x (footprint y -20.4, rotated 180)
USBC_MOUTH_Y = -(HY + 0.59)  # mouth plane (0.59 past the back edge)
USBC_REAR_Y = USBC_MOUTH_Y + 7.9
USBC_HALF_W = 4.47
USBC_Z = (0.05, 3.25)        # body, height above the board's top face
USBC_PLUG_W = 12.5           # USB-C plug overmould, width ...
USBC_PLUG_H = 7.0            # ... and height, centred on the receptacle
# Tactile buttons, 5.1 x 5.1 x 1.5 (STEP: body 5.2 x 5.2, legs 6.5 wide)
BUTTONS = {'RST': (15.0, -10.4), 'BOOT': (15.0, -3.4)}   # SW1, SW2
BUTTON_BODY = (6.5, 5.2)     # x, y incl. legs
BUTTON_H = 1.5               # top of the plunger above the board's top face
BUTTON_COURTYARD = (7.2, 5.3)
# Tallest SMD part: the buck inductor L1, 7.0 (x, pads left and right) x 6.6 (y) x 3.1 tall
INDUCTOR = (-38.0, -7.1, 7.0, 6.6, 3.1)
ESP_H = 3.11                 # module height (STEP)
# Addressable LEDs, 2 x 2 mm, top-facing
LED_SIZE = 2.2               # body + tolerance, for the fit check
LED_H = 1.0
# Port LEDs at (cx + 6.4, USBA_Y - 4.0) and the status LED, as on the routed board
PORT_LED_DX, PORT_LED_Y = 6.4, USBA_FP_Y - 4.0
STATUS_LED = (21.0, -0.3)
LEDS = [(x + PORT_LED_DX, PORT_LED_Y) for x in USBA_X] + [STATUS_LED]
# Every part on the board, for the lid's heat pads and their check: read from
# the routed board (courtyards, via pcbnew in a subprocess, every run), with
# the height of each footprint type above the board's top face (the heat
# brief's figures, raised where the board's 3D model is taller: SOD-123 1.45,
# SOT-23-6 1.6, DFN 0.89).  The first matching name fragment wins; a
# footprint that matches none stops the build.
BOARD_PCB = os.path.join(REPO_V1, 'print-hub.kicad_pcb')
PART_HEIGHTS = [
    ('USB-A-TH', 7.35),          # its region keeps the full ceiling
    ('USB-C_SMD', 3.25),
    ('IND-SMD', 3.1),            # buck inductor L1
    ('WIFIM-SMD_ESP32', 3.11),
    ('SW-SMD', 1.5),             # buttons (the pad stays at the guide tubes' height, see HEAT PADS)
    ('C_1206', 1.6),
    ('R_1206', 0.65),            # current shunts
    ('SMA_', 2.4),               # input TVS D1
    ('SOD-123', 1.45),
    ('SOT-23-6', 1.6),           # USBLC6-2SC6
    ('SOT-23', 1.2), ('SOT-25', 1.2),
    ('QFN', 0.85), ('DFN', 0.9), ('WSON', 0.85),
    ('LED-SMD_4P-L2.2', 0.9),    # WS2812B-2020
    ('_0603_', 0.9),
    ('_0402_', 0.55),
    ('PAD_TP', 0.0),             # test pads (no probe access through the lid)
    ('MOUNT_M3', None),          # mounting holes: the lid's bosses sit there
]

# =============================================================================
# 3. ENCLOSURE DESIGN CHOICES
# =============================================================================
WALL = 2.0                   # side, back, front wall thickness
TOP_T = 2.0                  # lid top plate
FLOOR_T = 2.0                # base floor
FIT = 0.3                    # clearance between the board edge and the walls
SPLIT_GAP = 0.1              # base/lid split plane sits this far above the board top
MOUTH_SETBACK = 0.4          # front wall outer face is this far in front of the USB-A mouths
PIN_PROTRUSION = 3.0         # design value for TH pins under the board (measured 2.4; notes say 2.5-3)
PIN_FLOOR_CLEAR = 1.0        # pins clear the floor by at least this
HEADROOM = 0.6               # min air between the tallest part (USB-A lip) and the lid's ceiling
LID_CEILING_Z = 10.0         # underside of the lid's top plate (z above the board's bottom face)
USBA_CUT_CLEAR = 0.5         # clearance around the USB-A mouth flange in the front wall
USBC_CUT_CLEAR = 0.5         # clearance around the USB-C receptacle in the back wall
USBC_PLUG_CLEAR = 0.5        # clearance around the USB-C plug overmould in the outer recess
USBC_RECESS_SETBACK = 0.4    # recess floor sits this far behind the USB-C mouth -> plug seats fully

# Fastening: 2 holes, both M3 screws into the base.  Both are well over 10 mm
# from the antenna area, so no hole needs the old printed peg.
FASTENER = 'insert'          # 'insert' = M3 heat-set inserts; 'selftap' = 2.6 mm pilot holes
INSERT_HOLE_D = 4.0          # hole for an M3 x 4 mm heat-set insert (check your insert's datasheet)
INSERT_LEN = 4.0
INSERT_POCKET_EXTRA = 1.0    # pocket deeper than the insert, for displaced plastic
PILOT_D = 2.6                # self-tapping pilot hole
PILOT_DEPTH = 5.5
SCREW_LEN = 12.0             # M3 x 12 ISO 4762 socket head cap screw
SCREW_HEAD_D = 5.5
SCREW_HEAD_H = 3.0
SCREW_CLEAR_D = 3.4          # clearance hole in the lid
CBORE_D = 6.2                # counterbore for the screw head
BRIDGE_LAYER = 0.2           # one layer: the stepped "bridging" layers at the counterbore floor
STANDOFF_D = 7.0             # base standoffs (under the board, inside the keep-clear circle)
LID_BOSS_D = 6.8             # lid bosses where they touch the board (inside the 7.0 keep-clear circle;
                             # not 6.6: that would just touch the side wall and leave a non-manifold edge)
LID_COLLAR_D = 9.0           # lid bosses widen above all parts, round the counterbore
LID_COLLAR_Z = 6.0           # ... from this height up (inside the heat pad above the parts)

# HEAT PADS.  Heat has to cross the air between the board and the case, so
# the lid's underside follows the parts: over every point of the board it
# sits PAD_CLEAR above the tallest part within PAD_GROW of that point (each
# part's courtyard grown by PAD_GROW), never lower than PAD_MIN_GAP above the
# bare board and never higher than the ceiling.  The pads grow down from the
# top plate (they print upwards, upside-down lid) and every step is
# vertical, so the lid still lowers straight down over the parts.
PAD_CLEAR = 0.6              # lid underside above the top of each part
PAD_GROW = 0.5               # around each courtyard
POCKET_GROW = {'USB-A-TH': 1.0, 'SW-SMD': 1.0}   # more round these, to keep the clearance they had
                             # before the pads (1 mm round the USB-A shells and the buttons)
PAD_MIN_GAP = 1.2            # lid underside above the bare board top
# The base's floor sits BOTTOM_GAP under the board, with a recess for the
# USB-A pins (down to the old floor, PIN_FLOOR_CLEAR under the pins)
BOTTOM_GAP = 1.0
PIN_RECESS_CLEAR = 1.0       # the pin recess reaches this far past the pins in x and y

# The front strip.  With only two screws, both towards the back-left, the
# board's front edge is clamped by the case: the base's front wall is a
# ledge under it (touching the board, like the standoffs), and the lid's
# front wall comes down onto the board's top face between the USB-A notches
# and at both front corners (y FRONT_IN..board edge; nothing but the
# receptacles is on that strip, and they sit in the notches).  So the board
# is held at the two screws and along its whole front edge, and cannot rock.
FRONT_LEDGE_GAP = 0.0        # base ledge under the board's front strip: touches the board
FRONT_PRESS = True           # lid's front wall reaches down onto the board between the notches

# Board support under the two buttons (so a paperclip push does not flex the board)
BUTTON_PILLAR = (12.0, 18.0, -12.5, -1.3)   # x0, x1, y0, y1
SUPPORT_GAP = 0.1            # the button pillar stops this far below the board

# LED light windows: 'hole' = through hole (works in any colour, incl. black);
# 'thin' = 0.4 mm skin left in the top plate (only for white/natural material)
LED_WINDOW = 'hole'
LED_WINDOW_D = 2.5
LED_THIN_SKIN = 0.4

# Buttons: 'pin' = 3 mm paperclip hole with a guide tube down to the button;
# 'flexure' = printed cantilever plungers in the lid (FDM PETG/PLA; not brittle resin)
BUTTON_STYLE = 'pin'
BUTTON_HOLE_D = 3.0
GUIDE_TUBE = 5.0             # square guide tube, outer size
GUIDE_GAP = 1.0              # tube ends this far above the button top
FLEX_LEN = 12.0              # flexure tongue length (free end 3 mm past the button)
FLEX_W = 6.0                 # tongue width (two tongues, 7 mm apart, share a 1 mm slot)
FLEX_SLOT = 1.0
FLEX_T = 1.0                 # tongue thickness
FLEX_POST = 2.5              # square post from the tongue down to the button
FLEX_POST_GAP = 0.3

# Vents (well away from the antenna in the back-right corner)
VENT_W = 1.6                 # slot width
VENT_PITCH = 3.2
TOP_VENT_X = (-42.0, -27.6)  # over the buck converter (U2 at -30) and its inductor (L1 at -38)
TOP_VENT_Y = (-15.0, -1.0)
LEFT_VENT_Y = (-15.0, 3.0)   # left wall, next to the buck and inductor
RIGHT_VENT_Y = (-8.0, 7.2)   # right wall, >= 10 mm from the antenna, clear of port 5's LED window
SIDE_VENT_TOP = 7.7          # side slots run from the split plane up to this z (open at the lid edge)
SIDE_VENT_INTO_PAD = 2.0     # ... and on into the heat pad, so they open into the air under it

# Text, engraved into the lid's top face, JetBrains Mono (brand: mono for numerals and codes, uppercase)
TEXT_DEPTH = 0.6
TEXT_WEIGHT = 500            # brand: JetBrains Mono 500
TEXT_TRACKING = 0.06         # brand: mono tracking 0.06 em
TEXT_PORT_SIZE = 7.0         # port numbers 1-5, over the USB-A shells
TEXT_PORT_Y = 18.5
TEXT_LABEL_SIZE = 4.0        # POWER / DATA, over the USB-Cs
TEXT_LABEL_Y = -20.0
TEXT_LABEL_DX = {'POWER': 1.0, 'DATA': 0.0}   # POWER moved right, clear of the back-left screw head
TEXT_BUTTON_SIZE = 3.6       # RST / BOOT, right of their holes (the screw is on the left)
TEXT_BUTTON_DY = -0.6        # towards the back of the hole centre, clear of the status LED window
TEXT_TITLE = 'PRINT HUB'
TEXT_TITLE_SIZE = 5.0
TEXT_TITLE_AT = (0.0, 4.8)   # centred, between the screw beside the ESP32 and the port LED windows
TEXT_CLEAR = 1.0             # engraved text keeps this far from every opening, other text and the edge

# Feet: recesses in the bottom, each takes a printed foot (printhub-feet.stl)
FOOT_D = 10.6                # recesses for the printed feet (or 10 mm rubber bumpers)
FEET_H = 3.5                 # printed feet stand this far below the floor, so it is in free air
FEET_PRINT_D = 10.4          # printed foot, glued into its recess
FOOT_DEPTH = 1.0
FEET = [(-31.0, -18.0), (31.0, -18.0), (-31.0, 18.0), (31.0, 18.0)]   # clear of the insert pockets

# Exports
STL_TOL = 0.02
STEP_TIMESTAMP = '2026-10-17T00:00:00'   # fixed, so a rebuild gives a byte-identical STEP
PREVIEW_TOL = 0.15
PREVIEW_DPI = 80
PREVIEW_SUPERSAMPLE = 2       # render at 2x and average down (anti-aliasing)
EXPLODE = 26.0               # preview: lid lifted this far, board this far / 2

# =============================================================================
# 4. DERIVED DIMENSIONS
# =============================================================================
BOARD_TOP = BOARD_T
SPLIT_Z = BOARD_TOP + SPLIT_GAP
FLOOR_TOP = -(PIN_PROTRUSION + PIN_FLOOR_CLEAR)            # floor of the USB-A pin recess
FLOOR_BOT = FLOOR_TOP - FLOOR_T                            # the base's outer bottom face
RAISED_FLOOR_Z = -BOTTOM_GAP                               # the floor everywhere else, under the board
PIN_RECESS_Y = (USBA_PIN_Y[0] - PIN_RECESS_CLEAR, USBA_PIN_Y[1] + PIN_RECESS_CLEAR)
TOP_Z = LID_CEILING_Z + TOP_T
IN_X = HX + FIT                                              # inner faces of the side walls
OUT_X = IN_X + WALL
BACK_IN = -(HY + FIT)                                        # back wall (y < 0)
BACK_OUT = BACK_IN - WALL
FRONT_OUT = USBA_MOUTH_Y + MOUTH_SETBACK                     # front wall (y > 0)
FRONT_IN = FRONT_OUT - WALL
FRONT_SKIN = FRONT_OUT - (HY + FIT)                          # wall left in front of the board edge
USBC_ZC = BOARD_TOP + sum(USBC_Z) / 2                        # USB-C centre line
USBA_ZC = BOARD_TOP + sum(USBA_MOUTH_Z) / 2
CBORE_FLOOR = None   # set below, from the screw length


def screw_tip_target():
    """z where the screw tip should end: the bottom of the insert (or of the pilot engagement)."""
    return -INSERT_LEN if FASTENER == 'insert' else -(PILOT_DEPTH - 1.5)


CBORE_FLOOR = screw_tip_target() + SCREW_LEN                  # z of the counterbore floor
CBORE_DEPTH = TOP_Z - CBORE_FLOOR


def screw_holes():
    return list(HOLES)


# -----------------------------------------------------------------------------
# The board's parts, the heat pads and the floor recesses (one table each,
# used to build the parts, to check them and to write case_gaps.json)
# -----------------------------------------------------------------------------
_READ_BOARD = r'''
import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
out = []
for fp in b.GetFootprints():
    bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if bb.GetWidth() <= 0:                         # no courtyard (test pads): the pads instead
        bb = None
        for pad in fp.Pads():
            q = pad.GetBoundingBox()
            if bb is None:
                bb = q
            else:
                bb.Merge(q)
    out.append([fp.GetReference(), fp.GetFPIDAsString(),
                bb.GetLeft() / 1e6 - 100.0, bb.GetRight() / 1e6 - 100.0,
                bb.GetTop() / 1e6 - 100.0, bb.GetBottom() / 1e6 - 100.0])
print('PARTS ' + json.dumps(sorted(out)))
'''
_PARTS = None


def board_parts():
    """[(ref, footprint, (x0, x1, y0, y1) courtyard, height or None)] from the routed board."""
    global _PARTS
    if _PARTS is None:
        import json, subprocess
        res = subprocess.run([sys.executable, '-c', _READ_BOARD, BOARD_PCB], capture_output=True, text=True)
        line = [l for l in res.stdout.splitlines() if l.startswith('PARTS ')]
        if res.returncode or not line:
            raise SystemExit('could not read %s with pcbnew:\n%s' % (BOARD_PCB, res.stderr[-2000:]))
        _PARTS = []
        for ref, fpid, x0, x1, y0, y1 in json.loads(line[0][6:]):
            h = [hh for frag, hh in PART_HEIGHTS if frag in fpid]
            if not h:
                raise SystemExit('no height for %s (%s): add it to PART_HEIGHTS' % (ref, fpid))
            _PARTS.append((ref, fpid, (x0, x1, y0, y1), h[0]))
    return _PARTS


SLAB = (-IN_X, IN_X, BACK_IN, FRONT_IN)       # where the lid's heat pad is: inside the walls


def clip(r, c=SLAB):
    x0, x1, y0, y1 = max(r[0], c[0]), min(r[1], c[1]), max(r[2], c[2]), min(r[3], c[3])
    return (x0, x1, y0, y1) if x0 < x1 and y0 < y1 else None


def heat_pad_rects():
    """[(x0, x1, y0, y1, gap)]: where the lid's underside must rise above
    PAD_MIN_GAP, gap = its height above the board's top face.  A point's gap
    is the largest of the rectangles that contain it (PAD_MIN_GAP if none)."""
    ceiling = LID_CEILING_Z - BOARD_TOP
    out = []
    for ref, fpid, (x0, x1, y0, y1), h in board_parts():
        if h is None:
            continue
        gap = h + PAD_CLEAR
        if 'SW-SMD' in fpid and BUTTON_STYLE == 'pin':
            gap = BUTTON_H + GUIDE_GAP            # as the guide tubes: the paperclip lands as before
        if 'USB-A' in fpid:
            gap = ceiling                         # the receptacles keep the full ceiling
        gap = min(gap, ceiling)
        g = max([PAD_GROW] + [v for frag, v in POCKET_GROW.items() if frag in fpid])
        r = clip((x0 - g, x1 + g, y0 - g, y1 + g))
        if gap > PAD_MIN_GAP + 1e-6 and r:
            out.append(r + (round(gap, 3),))
    return out


def floor_recess_rects():
    """[(x0, x1, y0, y1, gap)]: where the base's floor drops below BOTTOM_GAP,
    gap = its depth below the board's bottom face.  The USB-A pins and shield
    legs of neighbouring ports are only 1.4 mm apart, so one recess takes all five."""
    return [clip((-IN_X, IN_X, PIN_RECESS_Y[0], PIN_RECESS_Y[1])) + (-FLOOR_TOP,)]


def write_gaps_json():
    """case_gaps.json for sim/thermal/board_heat.py: the air gaps between the
    board's faces and the case, from the same tables the model is built from."""
    import json
    rect = lambda r: {'x0': round(r[0], 3), 'y0': round(r[2], 3), 'x1': round(r[1], 3), 'y1': round(r[3], 3),
                      'gap_mm': round(r[4], 3)}
    data = {'outside_mm': [round(v, 3) for v in outer_size()], 'wall_mm': WALL, 'feet_mm': FEET_H,
            'top_default_mm': PAD_MIN_GAP, 'top': [rect(r) for r in heat_pad_rects()],
            'bottom_default_mm': BOTTOM_GAP, 'bottom': [rect(r) for r in floor_recess_rects()]}
    with open(os.path.join(HERE, 'case_gaps.json'), 'w') as f:
        json.dump(data, f, indent=1)
        f.write('\n')


def dist_to_antenna(p):
    x, y = p
    dx = max(ESP_X[0] - x, 0.0, x - ESP_X[1])
    dy = max(ANTENNA_Y[0] - y, 0.0, y - ANTENNA_Y[1])
    return math.hypot(dx, dy)


# =============================================================================
# 5. HELPERS (KiCad x, y in; right-handed 3D out, Y = -y)
# =============================================================================
def kbox(x0, x1, y0, y1, z0, z1):
    """Box spanning x0..x1, y0..y1 (KiCad), z0..z1."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Pos((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def kcbox(x, y, sx, sy, z0, z1):
    """Box centred on (x, y) KiCad."""
    return kbox(x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, z0, z1)


def kcyl(x, y, d, z0, z1):
    return Pos(x, -y, (z0 + z1) / 2) * Cylinder(d / 2, abs(z1 - z0))


def text_outline(txt, size):
    """Text as shapely (multi)polygons in mm, centred on (0, 0), y up.

    The brand font is a variable font whose glyphs are drawn with overlapping
    contours; OCCT's own text builder turns those into broken faces.  So the
    outlines come from fontTools at the brand weight, and shapely merges the
    overlapping contours (outer contours united, counters subtracted)."""
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely import affinity

    class Flatten(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.contours, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            for i in range(1, 9):
                t = i / 8
                a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                self.cur.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                                 a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for i in range(1, 7):
                t = i / 6
                a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                self.cur.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))

        def _closePath(self):
            if len(self.cur) >= 3:
                self.contours.append(self.cur)
            self.cur = []

        _endPath = _closePath

    font = TTFont(FONT_MONO)
    upm = font['head'].unitsPerEm
    gs = font.getGlyphSet(location={'wght': TEXT_WEIGHT})
    cmap = font.getBestCmap()
    track = TEXT_TRACKING * upm
    x0, polys = 0.0, []
    for ch in txt:
        g = gs[cmap[ord(ch)]]
        pen = Flatten(gs)
        g.draw(pen)
        outer, inner = [], []
        for c in pen.contours:
            p = Polygon(c)
            if not p.is_valid:
                p = p.buffer(0)
            area = sum(px * qy - qx * py for (px, py), (qx, qy) in zip(c, c[1:] + c[:1])) / 2
            (outer if area < 0 else inner).append(p)       # TrueType: outer contours run clockwise
        if outer:
            shape = unary_union(outer).difference(unary_union(inner)) if inner else unary_union(outer)
            polys.append(affinity.translate(shape, x0, 0))
        x0 += g.width + track
    shape = affinity.scale(unary_union(polys), size / upm, size / upm, origin=(0, 0))
    shape = shape.simplify(0.02)            # drop curve points closer than 0.02 mm to the outline
    minx, miny, maxx, maxy = shape.bounds
    return affinity.translate(shape, -(minx + maxx) / 2, -(miny + maxy) / 2)


def aligned_outline(txt, size, halign='center'):
    """text_outline, moved so x is its centre, its right end ('right') or its left end ('left')."""
    from shapely import affinity
    shape = text_outline(txt, size)
    if halign == 'right':
        shape = affinity.translate(shape, -shape.bounds[2], 0)
    elif halign == 'left':
        shape = affinity.translate(shape, -shape.bounds[0], 0)
    return shape


def ktext(txt, size, x, y, z_top, depth, halign='center'):
    """Engraving tool: text read from above with the front edge towards you.
    `size` is the font size (em) in mm; capitals come out about 0.73 x size tall.
    halign 'right' puts the text's right end at x, 'left' its left end."""
    from build123d import Face, Wire
    shape = aligned_outline(txt, size, halign)
    geoms = getattr(shape, 'geoms', [shape])
    tools = []
    for poly in geoms:
        outer = Wire.make_polygon([(px, py, 0) for px, py in list(poly.exterior.coords)[:-1]], close=True)
        holes = [Wire.make_polygon([(px, py, 0) for px, py in list(r.coords)[:-1]], close=True)
                 for r in poly.interiors]
        tools.append(extrude(Face(outer, holes), amount=depth + 0.2, dir=(0, 0, 1)))   # up, whatever the winding
    return Pos(x, -y, z_top - depth) * Compound(children=tools)


def cut_all(shape, tools, debug=False):
    """Subtract the tools one by one (one big multi-tool cut can go wrong with text)."""
    for i, t in enumerate(tools):
        shape = shape.cut(t)
        if debug:
            print('   cut', i, round(shape.volume, 1))
    return shape


def fuse_all(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out + s
    return out


# =============================================================================
# 6. THE PARTS
# =============================================================================
def connector_cuts():
    """Cut-outs shared by base and lid (each takes the part inside its own z range)."""
    cuts = []
    # USB-A: a rectangle round the mouth flange, through the front wall; it
    # reaches below the split plane, so in the lid it is a notch open at the bottom
    for cx in USBA_X:
        z0 = BOARD_TOP + USBA_MOUTH_Z[0] - USBA_CUT_CLEAR
        z1 = BOARD_TOP + USBA_MOUTH_Z[1] + USBA_CUT_CLEAR
        cuts.append(kbox(cx - USBA_HALF_W - USBA_CUT_CLEAR, cx + USBA_HALF_W + USBA_CUT_CLEAR,
                         FRONT_IN - 1.0, FRONT_OUT + 1.0, z0, z1))
    # USB-C: the receptacle passes through the wall; round it an outer recess
    # the size of the plug overmould, its floor just behind the mouth
    for cx in USBC.values():
        cuts.append(kbox(cx - USBC_HALF_W - USBC_CUT_CLEAR, cx + USBC_HALF_W + USBC_CUT_CLEAR,
                         BACK_OUT - 1.0, BACK_IN + 1.0,
                         BOARD_TOP + USBC_Z[0] - USBC_CUT_CLEAR, BOARD_TOP + USBC_Z[1] + USBC_CUT_CLEAR))
        hw = USBC_PLUG_W / 2 + USBC_PLUG_CLEAR
        hh = USBC_PLUG_H / 2 + USBC_PLUG_CLEAR
        cuts.append(kbox(cx - hw, cx + hw, BACK_OUT - 1.0, USBC_MOUTH_Y - USBC_RECESS_SETBACK,
                         USBC_ZC - hh, USBC_ZC + hh))
    return cuts


def build_base():
    shell = kbox(-OUT_X, OUT_X, BACK_OUT, FRONT_OUT, FLOOR_BOT, SPLIT_Z)
    # inside: full depth behind the front wall; in the board's own layer the
    # pocket reaches the board edge + FIT, leaving the front skin.  What is
    # left of the front wall under the board is the ledge the front strip rests on.
    # The floor is raised to BOTTOM_GAP under the board, with recesses down
    # to FLOOR_TOP where something sticks out below the board (floor_recess_rects).
    cuts = [kbox(-IN_X, IN_X, BACK_IN, FRONT_IN, RAISED_FLOOR_Z, SPLIT_Z + 1),
            kbox(-IN_X, IN_X, BACK_IN, HY + FIT, -FRONT_LEDGE_GAP, SPLIT_Z + 1)]
    cuts += [kbox(x0, x1, y0, y1, -gap, RAISED_FLOOR_Z + 0.01) for x0, x1, y0, y1, gap in floor_recess_rects()]
    base = shell.cut(*cuts)
    # standoffs (round, inside each hole's keep-clear circle), button pillar
    adds = [kcyl(x, y, STANDOFF_D, RAISED_FLOOR_Z - 0.01, 0.0) for x, y in HOLES]
    x0, x1, y0, y1 = BUTTON_PILLAR
    adds.append(kbox(x0, x1, y0, y1, RAISED_FLOOR_Z - 0.01, -SUPPORT_GAP))
    base = fuse_all([base] + adds)
    holes = []
    for x, y in screw_holes():
        if FASTENER == 'insert':
            holes.append(kcyl(x, y, INSERT_HOLE_D, -(INSERT_LEN + INSERT_POCKET_EXTRA), 0.5))
        else:
            holes.append(kcyl(x, y, PILOT_D, -PILOT_DEPTH, 0.5))
    holes += [kcyl(x, y, FOOT_D, FLOOR_BOT - 1, FLOOR_BOT + FOOT_DEPTH) for x, y in FEET]
    holes += connector_cuts()
    return base.cut(*holes)


def build_lid():
    shell = kbox(-OUT_X, OUT_X, BACK_OUT, FRONT_OUT, SPLIT_Z, TOP_Z)
    lid = shell.cut(kbox(-IN_X, IN_X, BACK_IN, FRONT_IN, SPLIT_Z - 1, LID_CEILING_Z))
    adds = []
    for x, y in HOLES:
        adds.append(kcyl(x, y, LID_BOSS_D, BOARD_TOP, LID_CEILING_Z + 0.01))
        adds.append(kcyl(x, y, LID_COLLAR_D, LID_COLLAR_Z, LID_CEILING_Z + 0.01))
    if BUTTON_STYLE == 'pin':
        for x, y in BUTTONS.values():
            adds.append(kcbox(x, y, GUIDE_TUBE, GUIDE_TUBE,
                              BOARD_TOP + BUTTON_H + GUIDE_GAP, LID_CEILING_Z + 0.01))
    if FRONT_PRESS:
        # the front wall down onto the board's front strip; the USB-A notches
        # (connector_cuts, from below the board top) leave it between the ports
        adds.append(kbox(-IN_X, IN_X, FRONT_IN, HY + FIT, BOARD_TOP, SPLIT_Z + 0.01))
    adds.append(heat_pad())
    # clip the collars/bosses to the outline
    lid = fuse_all([lid] + adds) & kbox(-OUT_X, OUT_X, BACK_OUT, FRONT_OUT, BOARD_TOP - 1, TOP_Z)

    cuts = connector_cuts()
    for x, y in screw_holes():
        # screw: clearance hole, counterbore, and two one-layer bridging steps
        # so the counterbore floor prints face-down without supports
        cuts.append(kcyl(x, y, SCREW_CLEAR_D, BOARD_TOP - 0.5, CBORE_FLOOR))
        cuts.append(kcyl(x, y, CBORE_D, CBORE_FLOOR, TOP_Z + 1))
        cuts.append(kcbox(x, y, SCREW_CLEAR_D, CBORE_D, CBORE_FLOOR - BRIDGE_LAYER, CBORE_FLOOR + 0.01))
        cuts.append(kcbox(x, y, SCREW_CLEAR_D, SCREW_CLEAR_D, CBORE_FLOOR - 2 * BRIDGE_LAYER, CBORE_FLOOR))
    # LED windows
    for x, y in LEDS:
        # from just above the LED, through the heat pad
        if LED_WINDOW == 'hole':
            cuts.append(kcyl(x, y, LED_WINDOW_D, BOARD_TOP + LED_H, TOP_Z + 1))
        else:
            cuts.append(kcyl(x, y, LED_WINDOW_D, BOARD_TOP + LED_H, TOP_Z - LED_THIN_SKIN))
    # buttons
    if BUTTON_STYLE == 'pin':
        for x, y in BUTTONS.values():
            cuts.append(kcyl(x, y, BUTTON_HOLE_D, BOARD_TOP + BUTTON_H, TOP_Z + 1))
    else:
        cuts += flexure_cuts()
    # vents: top slots over the buck, side slots open at the lid's bottom edge
    for (x0, x1, y0, y1), (z0, z1) in vent_slots():
        cuts.append(kbox(x0, x1, y0, y1, z0, z1))
    # engraved text
    for txt, size, x, y, halign in text_items():
        cuts.append(ktext(txt, size, x, y, TOP_Z, TEXT_DEPTH, halign=halign))
    lid = cut_all(lid, cuts)
    if BUTTON_STYLE == 'flexure':
        lid = fuse_all([lid] + flexure_posts())
    return lid


def heat_pad():
    """The lid's heat pad: a slab from PAD_MIN_GAP above the board up into the
    top plate, with a pocket over every part that needs more room."""
    slab = kbox(*SLAB, BOARD_TOP + PAD_MIN_GAP, LID_CEILING_Z + 0.5)
    pockets = []
    for x0, x1, y0, y1, gap in heat_pad_rects():
        z1 = BOARD_TOP + gap if BOARD_TOP + gap < LID_CEILING_Z - 1e-6 else TOP_Z + 1
        pockets.append(kbox(x0, x1, y0, y1, BOARD_TOP, z1))
    return slab.cut(*pockets)


def vent_slots():
    """((x0, x1, y0, y1), (z0, z1)) of every vent slot: top slots over the buck
    (through the heat pad), side slots in the lid's walls, open at its bottom
    edge and reaching SIDE_VENT_INTO_PAD into the pad."""
    out = []
    x = TOP_VENT_X[0] + VENT_W / 2
    while x + VENT_W / 2 <= TOP_VENT_X[1] + 1e-6:
        out.append(((x - VENT_W / 2, x + VENT_W / 2, TOP_VENT_Y[0], TOP_VENT_Y[1]), (BOARD_TOP + 0.3, TOP_Z + 1)))
        x += VENT_PITCH
    for (ya, yb), (xa, xb) in ((LEFT_VENT_Y, (-OUT_X - 1, -IN_X + SIDE_VENT_INTO_PAD)),
                               (RIGHT_VENT_Y, (IN_X - SIDE_VENT_INTO_PAD, OUT_X + 1))):
        y = ya + VENT_W / 2
        while y + VENT_W / 2 <= yb + 1e-6:
            out.append(((xa, xb, y - VENT_W / 2, y + VENT_W / 2), (SPLIT_Z - 1, SIDE_VENT_TOP)))
            y += VENT_PITCH
    return out


def text_items():
    """(text, size, x, y, halign) of everything engraved on the lid."""
    items = [(str(n), TEXT_PORT_SIZE, cx, TEXT_PORT_Y, 'center') for n, cx in enumerate(USBA_X, 1)]
    items += [(label, TEXT_LABEL_SIZE, cx + TEXT_LABEL_DX.get(label, 0.0), TEXT_LABEL_Y, 'center')
              for label, cx in USBC.items()]
    for label, (x, y) in BUTTONS.items():
        if BUTTON_STYLE == 'pin':
            # left-aligned, 1.2 mm right of the paperclip hole (the screw beside the ESP32 is on the left)
            items.append((label, TEXT_BUTTON_SIZE, x + BUTTON_HOLE_D / 2 + 1.2, y + TEXT_BUTTON_DY, 'left'))
        else:
            # right-aligned, 1.2 mm clear of the flexure slot
            items.append((label, TEXT_BUTTON_SIZE, x - 3.0 - FLEX_SLOT - 1.2, y, 'right'))
    items.append((TEXT_TITLE, TEXT_TITLE_SIZE, TEXT_TITLE_AT[0], TEXT_TITLE_AT[1], 'center'))
    return items


def top_plate_layout():
    """The lid's top face in 2D (shapely, KiCad x/y): (openings, texts).
    openings: (name, group, shape) of everything cut through the top plate;
    texts: (text, shape) of the engraving."""
    from shapely.geometry import Point, box
    from shapely import affinity
    openings = []
    for x, y in screw_holes():
        openings.append(('screw head (%g, %g)' % (x, y), 'cbore', Point(x, y).buffer(CBORE_D / 2, 64)))
    for i, (x, y) in enumerate(LEDS):
        openings.append(('LED window %s' % ('status' if i == 5 else 'port %d' % (i + 1)), 'led',
                         Point(x, y).buffer(LED_WINDOW_D / 2, 64)))
    if BUTTON_STYLE == 'pin':
        for label, (x, y) in BUTTONS.items():
            openings.append(('%s hole' % label, 'button', Point(x, y).buffer(BUTTON_HOLE_D / 2, 64)))
    else:
        (bx, y_rst), (_, y_boot) = BUTTONS['RST'], BUTTONS['BOOT']
        ys = sorted([y_rst, y_boot])
        openings.append(('button flexures', 'button', box(bx - 3.0 - FLEX_SLOT, ys[0] - FLEX_W / 2 - FLEX_SLOT,
                                                          bx - 3.0 + FLEX_LEN, ys[1] + FLEX_W / 2 + FLEX_SLOT)))
    for (x0, x1, y0, y1), (z0, z1) in vent_slots():
        if z1 > LID_CEILING_Z:
            openings.append(('top vents', 'vent', box(x0, y0, x1, y1)))
    texts = []
    for txt, size, x, y, halign in text_items():
        s = affinity.scale(aligned_outline(txt, size, halign), 1, -1, origin=(0, 0))   # y up -> KiCad y down
        texts.append((txt, affinity.translate(s, x, y)))
    return openings, texts


def flexure_cuts():
    """An E-shaped slot through the top plate frees two tongues (rooted on the
    +x side, free ends past the buttons); the tongues are thinned from inside."""
    (bx, y_rst), (_, y_boot) = BUTTONS['RST'], BUTTONS['BOOT']
    x_free = bx - 3.0                  # free end 3 mm past the button centre
    x_root = x_free + FLEX_LEN
    ys = sorted([y_rst, y_boot])
    y_lo = ys[0] - FLEX_W / 2
    y_hi = ys[1] + FLEX_W / 2
    z0 = BOARD_TOP + 0.3              # through the heat pad as well
    cuts = [kbox(x_free - FLEX_SLOT, x_root, y_lo - FLEX_SLOT, y_lo, z0, TOP_Z + 1),
            kbox(x_free - FLEX_SLOT, x_root, y_hi, y_hi + FLEX_SLOT, z0, TOP_Z + 1),
            kbox(x_free - FLEX_SLOT, x_free, y_lo - FLEX_SLOT, y_hi + FLEX_SLOT, z0, TOP_Z + 1)]
    mid = (ys[0] + ys[1]) / 2
    cuts.append(kbox(x_free - FLEX_SLOT, x_root, mid - FLEX_SLOT / 2, mid + FLEX_SLOT / 2,
                     z0, TOP_Z + 1))
    cuts.append(kbox(x_free, x_root, y_lo, y_hi, z0, TOP_Z - FLEX_T))
    return cuts


def flexure_posts():
    return [kcbox(x, y, FLEX_POST, FLEX_POST, BOARD_TOP + BUTTON_H + FLEX_POST_GAP, TOP_Z - FLEX_T + 0.01)
            for x, y in BUTTONS.values()]


# =============================================================================
# 7. THE BOARD AND ITS PARTS AS SIMPLE BOXES (for the fit check and preview)
# =============================================================================
def board_solid():
    b = kbox(-HX, HX, -HY, HY, 0, BOARD_T)
    return b.cut(*[kcyl(x, y, HOLE_D, -1, BOARD_T + 1) for x, y in HOLES])


def part_boxes():
    """name -> solid, from the measured STEP sizes (z above the board's bottom face)."""
    T = BOARD_TOP
    p = {}
    for n, cx in enumerate(USBA_X, 1):
        # rear body (sits on the board) and the mouth flange (lifted 0.35)
        p['USB-A %d body' % n] = kbox(cx - USBA_HALF_W, cx + USBA_HALF_W, USBA_REAR_Y, USBA_MOUTH_Y - 2.5,
                                      T, T + USBA_TOP)
        p['USB-A %d mouth' % n] = kbox(cx - USBA_HALF_W, cx + USBA_HALF_W, USBA_MOUTH_Y - 2.5, USBA_MOUTH_Y,
                                       T + USBA_MOUTH_Z[0], T + USBA_MOUTH_Z[1])
        p['USB-A %d pins (design %.1f mm)' % (n, PIN_PROTRUSION)] = kbox(
            cx - USBA_PIN_HALF_W, cx + USBA_PIN_HALF_W, USBA_PIN_Y[0], USBA_PIN_Y[1], -PIN_PROTRUSION, 0)
    for label, cx in USBC.items():
        p['USB-C %s' % label] = kbox(cx - USBC_HALF_W, cx + USBC_HALF_W, USBC_MOUTH_Y, USBC_REAR_Y,
                                     T + USBC_Z[0], T + USBC_Z[1])
    p['ESP32-S3 module'] = kbox(ESP_X[0], ESP_X[1], ESP_Y[0], ESP_Y[1], T, T + ESP_H)
    for label, (x, y) in BUTTONS.items():
        p['button %s' % label] = kcbox(x, y, BUTTON_BODY[0], BUTTON_BODY[1], T, T + BUTTON_H)
    x, y, sx, sy, h = INDUCTOR
    p['buck inductor'] = kcbox(x, y, sx, sy, T, T + h)      # rotated 180: same box
    for i, (x, y) in enumerate(LEDS):
        p['LED %s' % ('status' if i == 5 else 'port %d' % (i + 1))] = kcbox(x, y, LED_SIZE, LED_SIZE, T, T + LED_H)
    return p


def courtyard_boxes(extra=0.0):
    """ref -> every part's courtyard from the board file, PART_HEIGHTS (+ extra) tall,
    cut to the inside of the walls (USB-A and USB-C: their own boxes and STEP
    models check them against the walls; mounting holes: the bosses are there)."""
    out = {}
    for ref, fpid, r, h in board_parts():
        if h is None or 'USB-A' in fpid:
            continue
        r = clip(r)
        if r:
            out[ref] = kbox(*r, BOARD_TOP, BOARD_TOP + h + extra - 0.002)
    return out


def feet_solids():
    """The printed feet in their assembled place, in the base's foot recesses."""
    return [kcyl(x, y, FEET_PRINT_D, FLOOR_BOT - FEET_H, FLOOR_BOT + FOOT_DEPTH) for x, y in FEET]


def screws():
    out = {}
    for x, y in screw_holes():
        tip = CBORE_FLOOR - SCREW_LEN
        out['screw (%g, %g)' % (x, y)] = fuse_all([kcyl(x, y, 3.0, tip, CBORE_FLOOR),
                                                   kcyl(x, y, SCREW_HEAD_D, CBORE_FLOOR, CBORE_FLOOR + SCREW_HEAD_H)])
    return out


# =============================================================================
# 8. THE REAL STEP MODELS (fit check only; skipped if the files are missing)
# =============================================================================
def load_step(name):
    from build123d import import_step
    src = os.path.join(STEP_DIR, name + '.stpZ')
    if not os.path.exists(src):
        return None
    tmp = os.path.join(tempfile.gettempdir(), name + '.step')
    with gzip.open(src) as a, open(tmp, 'wb') as b:
        shutil.copyfileobj(a, b)
    return import_step(tmp)


def real_connectors():
    out = {}
    a = load_step('USB-A-TH__USB-AF-90')
    if a is not None:
        for n, cx in enumerate(USBA_X, 1):
            # STEP (right-handed, mouth at -Y = front) -> board: no rotation
            out['USB-A %d (STEP)' % n] = Pos(cx, -(USBA_FP_Y + USBA_STEP_DY), BOARD_TOP - USBA_STEP_Z_BOARDTOP) * a
    c = load_step('USB-C_SMD-TYPE-C-31-M-12_1')
    if c is not None:
        cb = c.bounding_box()
        for label, cx in USBC.items():
            # footprint model rotation 180 and part rotation 180 cancel: shift so the mouth is at USBC_MOUTH_Y
            out['USB-C %s (STEP)' % label] = Pos(cx, -USBC_MOUTH_Y - cb.max.Y, BOARD_TOP) * c
    return out


# =============================================================================
# 9. FIT CHECK
# =============================================================================
class Report:
    def __init__(self):
        self.lines, self.fails = [], 0

    def add(self, ok, what, detail=''):
        self.fails += 0 if ok else 1
        line = '  [%s] %-46s %s' % ('PASS' if ok else 'FAIL', what, detail)
        self.lines.append(line)
        print(line)

    def info(self, text):
        self.lines.append('  ' + text)
        print('  ' + text)


def overlap(a, b):
    try:
        v = (a & b).volume
    except Exception:
        v = 0.0
    return v


def probe(shape, axis, at, lo=-80, hi=80):
    """Segments (start, end) where a thin line along axis ('x','y','z') through
    point `at` (two KiCad coordinates for the other axes) is inside `shape`.
    Returned in KiCad terms (y positive towards the front)."""
    e = 0.02
    if axis == 'x':
        y, z = at
        line = kbox(lo, hi, y - e, y + e, z - e, z + e)
    elif axis == 'y':
        x, z = at
        line = kbox(x - e, x + e, lo, hi, z - e, z + e)
    else:
        x, y = at
        line = kbox(x - e, x + e, y - e, y + e, lo, hi)
    segs = []
    try:
        hit = shape & line
        for s in hit.solids():
            bb = s.bounding_box()
            if axis == 'x':
                segs.append((bb.min.X, bb.max.X))
            elif axis == 'y':
                segs.append((-bb.max.Y, -bb.min.Y))
            else:
                segs.append((bb.min.Z, bb.max.Z))
    except Exception:
        pass
    return sorted(segs)


def fit_check(base, lid):
    r = Report()
    print('\nFIT CHECK  (KiCad coordinates: y towards the front; z above the board bottom face)')
    enclosure = {'base': base, 'lid': lid}
    things = {'board': board_solid()}
    things.update(part_boxes())

    r.info('-- 1. parts (boxes from measured STEP sizes) must not intersect base or lid')
    worst = {}
    for name, s in things.items():
        for pn, p in enclosure.items():
            v = overlap(s, p)
            d = s.distance_to(p)
            worst[(name, pn)] = d
            if v > 1e-4:
                r.add(False, '%s vs %s' % (name, pn), 'INTERSECTS, %.3f mm^3' % v)
        d = min(worst[(name, 'base')], worst[(name, 'lid')])
        touch = name == 'board'
        r.add(True if touch else d > 0.05, name,
              'clear, min gap %.2f mm%s' % (d, ' (board is clamped: contact intended)' if touch else ''))
    # the board must not be touched by anything but standoffs, bosses and ledge
    r.info('-- 2. real STEP models (all solids incl. pins) against the enclosure')
    reals = real_connectors()
    if not reals:
        r.info('STEP files not found: skipped')
    for name, s in reals.items():
        v = overlap(s, base) + overlap(s, lid)
        d = min(s.distance_to(base), s.distance_to(lid))
        r.add(v < 1e-4, name, 'overlap %.4f mm^3, min gap %.2f mm' % (v, d))

    r.info('-- 3. connector mouths and plug seating')
    # front wall outer face, measured between ports, compared with the USB-A mouth
    face = max(seg[1] for seg in probe(lid, 'y', (9.0, 6.0)))
    for mouth, src in ((USBA_MOUTH_Y, 'STEP'), (USBA_MOUTH_Y_SPEC, 'board notes')):
        setback = face - mouth
        r.add(0.0 <= setback <= 0.5, 'USB-A mouth vs front outer face (%s)' % src,
              'mouth y %.2f, face y %.2f -> mouth %.2f mm behind the face (0..0.5 wanted)' % (mouth, face, setback))
    # a USB-A plug with a 16 x 8 overmould, its face 0.5 mm in front of the mouth
    for n, cx in enumerate(USBA_X, 1):
        plug = kbox(cx - 8.0, cx + 8.0, USBA_MOUTH_Y + 0.5, USBA_MOUTH_Y + 30, USBA_ZC - 4.0, USBA_ZC + 4.0)
        metal = kbox(cx - 6.0, cx + 6.0, USBA_MOUTH_Y - 12, USBA_MOUTH_Y + 0.6, USBA_ZC - 2.25, USBA_ZC + 2.25)
        v = overlap(plug, lid) + overlap(plug, base) + overlap(metal, lid) + overlap(metal, base)
        r.add(v < 1e-4, 'USB-A %d plug (16 x 8 overmould) seats' % n,
              'overmould stops %.2f mm short of the mouth (<= 0.5)' % (face - USBA_MOUTH_Y))
    for label, cx in USBC.items():
        om = kbox(cx - USBC_PLUG_W / 2, cx + USBC_PLUG_W / 2, USBC_MOUTH_Y - 0.5, USBC_MOUTH_Y - 30,
                  USBC_ZC - USBC_PLUG_H / 2, USBC_ZC + USBC_PLUG_H / 2)
        v = overlap(om, lid) + overlap(om, base)
        floor = USBC_MOUTH_Y - USBC_RECESS_SETBACK
        r.add(v < 1e-4, 'USB-C %s plug (12.5 x 7 overmould) seats' % label,
              'recess floor y %.2f, %.2f mm outside the mouth (<= 0.5)' % (floor, USBC_RECESS_SETBACK))
    # clearance round the USB-A mouth flange in the cut-out
    gaps = []
    for cx in USBA_X:
        m = kbox(cx - USBA_HALF_W, cx + USBA_HALF_W, USBA_MOUTH_Y - 2.5, USBA_MOUTH_Y,
                 BOARD_TOP + USBA_MOUTH_Z[0], BOARD_TOP + USBA_MOUTH_Z[1])
        gaps.append(min(m.distance_to(lid), m.distance_to(base)))
    r.add(min(gaps) >= USBA_CUT_CLEAR - 0.06, 'USB-A cut-out clearance round the shell',
          'min %.2f mm (%.1f wanted)' % (min(gaps), USBA_CUT_CLEAR))

    r.info('-- 4. heights')
    air = min(probe(lid, 'z', (cx, (USBA_REAR_Y + USBA_MOUTH_Y) / 2))[0][0] for cx in USBA_X) - (BOARD_TOP + USBA_TOP)
    r.add(air >= HEADROOM, 'lid ceiling over the USB-A shells', '%.2f mm of air' % air)
    for pins in (PIN_PROTRUSION, USBA_PIN_BELOW_MEASURED):
        c = -pins - FLOOR_TOP
        r.add(c >= 1.0, 'TH pins (%.1f mm) to the recess floor' % pins, '%.2f mm clear (>= 1.0)' % c)
    # heat pads: every part from the board file, PAD_CLEAR taller than it is, must not touch the lid
    raised = courtyard_boxes(PAD_CLEAR)
    hits = [ref for ref, s in raised.items() if overlap(s, lid) > 1e-4]
    r.add(not hits, 'lid underside >= %.1f mm above every part' % PAD_CLEAR,
          '%d parts from the board file (courtyards, PART_HEIGHTS)%s' % (
              len(raised), ': TOO CLOSE ' + ', '.join(hits) if hits else ''))
    pad = heat_pad()                        # the walls keep FIT from the board edge, as before
    near = min((s.distance_to(pad), ref) for ref, s in courtyard_boxes().items())
    r.add(near[0] >= PAD_GROW - 0.01, 'heat pads clear of every part\'s courtyard',
          'min %.2f mm (%s; the pads stop %.1f mm outside the courtyards)' % (near[0], near[1], PAD_GROW))
    pads = heat_pad_rects()
    r.info('heat pads: lid underside %.1f mm above the bare board, %d raised areas up to %.2f mm' % (
        PAD_MIN_GAP, len(pads), max(p[4] for p in pads)))
    # the raised floor: BOTTOM_GAP under the board except the recesses and the supports
    flat, deep, bad = 0, 0, []
    recesses = floor_recess_rects()
    for gx in range(-40, 41, 8):
        for gy in range(-22, 23, 4):
            if any(math.hypot(gx - hx, gy - hy) < STANDOFF_D / 2 + 0.2 for hx, hy in HOLES):
                continue
            if BUTTON_PILLAR[0] - 0.2 < gx < BUTTON_PILLAR[1] + 0.2 and BUTTON_PILLAR[2] - 0.2 < gy < BUTTON_PILLAR[3] + 0.2:
                continue
            if gy > FRONT_IN - 0.2:
                continue
            segs = [sg for sg in probe(base, 'z', (gx, gy)) if sg[1] <= 0.5]
            top = segs[-1][1] if segs else -99.0
            want = max([g for x0, x1, y0, y1, g in recesses if x0 <= gx <= x1 and y0 <= gy <= y1] + [BOTTOM_GAP])
            if abs(-top - want) < 0.02:
                deep, flat = deep + (want > BOTTOM_GAP), flat + (want == BOTTOM_GAP)
            else:
                bad.append('(%d, %d) %.2f' % (gx, gy, -top))
    r.add(not bad, 'floor %.1f mm under the board, recess %.1f mm' % (BOTTOM_GAP, recesses[0][4]),
          '%d points at %.1f, %d in the pin recess%s' % (flat, BOTTOM_GAP, deep, (': WRONG ' + ', '.join(bad)) if bad else ''))

    r.info('-- 5. wall thickness (probed through the solids)')
    def thick(shape, axis, at, pick):
        segs = probe(shape, axis, at)
        if not segs:
            return None
        s = segs[0] if pick == 'first' else segs[-1]
        return s[1] - s[0]
    probes = [
        ('left wall, lid', lid, 'x', (10.0, 2.2), 'first'),        # z 2.2: under the heat pad
        ('left wall, base', base, 'x', (10.0, -0.5), 'first'),
        ('right wall, lid', lid, 'x', (-20.0, 2.2), 'last'),
        ('right wall, base', base, 'x', (-20.0, -0.5), 'last'),
        ('back wall, lid', lid, 'y', (20.0, 2.2), 'first'),
        ('back wall, base', base, 'y', (20.0, -0.5), 'first'),
        ('front wall between ports, lid', lid, 'y', (9.0, 6.0), 'last'),
        ('front wall, base (under the board)', base, 'y', (9.0, -0.5), 'last'),
        ('lid top plate (over the USB-A)', lid, 'z', (8.5, 18.0), 'last'),
        ('base floor (under the pin recess)', base, 'z', (8.5, 15.0), 'first'),
    ]
    for name, shp, ax, at, pick in probes:
        t = thick(shp, ax, at, pick)
        r.add(t is not None and t >= WALL - 0.01, name, '%.2f mm' % (t or 0))
    t = thick(base, 'y', (9.0, 0.8), 'last')
    r.info('note: front skin in front of the board edge (z 0..1.7) is %.2f mm by design (see notes)' % (t or 0))
    t = thick(base, 'y', (USBC['POWER'], 0.0), 'first')
    r.info('note: frame round each USB-C in the recess floor is %.2f mm by design' % (t or 0))
    r.info('note: under the engraved text the top plate is %.1f mm' % (TOP_T - TEXT_DEPTH))
    t = thick(base, 'z', (-20.0, -10.0), 'first')
    r.info('note: under the rest of the board the raised floor is %.1f mm of plastic (z %.1f..%.1f)' % (
        t or 0, FLOOR_BOT, RAISED_FLOOR_Z))

    r.info('-- 6. fasteners, board support, antenna')
    for x, y in screw_holes():
        d = dist_to_antenna((x, y))
        metal_r = (INSERT_HOLE_D / 2 if FASTENER == 'insert' else 1.5)
        ok = d - max(metal_r, SCREW_HEAD_D / 2) >= ANTENNA_METAL_KEEPOUT
        r.add(ok, 'M3 screw + %s at (%g, %g)' % ('insert' if FASTENER == 'insert' else 'pilot', x, y),
              '%.1f mm from the antenna area (>= %.0f)' % (d - max(metal_r, SCREW_HEAD_D / 2), ANTENNA_METAL_KEEPOUT))
    tip = CBORE_FLOOR - SCREW_LEN
    eng = -tip                     # the insert (or the standoff) starts at z 0
    want = INSERT_LEN if FASTENER == 'insert' else PILOT_DEPTH - 1.5
    r.add(eng >= want - 0.5 and tip >= -(INSERT_LEN + INSERT_POCKET_EXTRA if FASTENER == 'insert' else PILOT_DEPTH),
          'M3 x %g screw engagement' % SCREW_LEN,
          'tip at z %.2f, %.1f mm into the %s; head %.2f mm below the lid top' % (
              tip, eng, 'insert' if FASTENER == 'insert' else 'standoff', CBORE_DEPTH - SCREW_HEAD_H))
    parts_all = dict(things)
    parts_all.update(courtyard_boxes())
    for name, s in screws().items():
        hits = [n for n, p in parts_all.items() if overlap(s, p) > 1e-4]
        r.add(not hits, name + ' misses all parts', ', '.join(hits))
    # the front strip: the lid's front wall on the board's top face between the
    # notches, the base's ledge under its bottom face, all along the edge
    ym = (FRONT_IN + HY) / 2
    spans, x = [], -HX
    for cx in USBA_X:
        a = cx - USBA_HALF_W - USBA_CUT_CLEAR
        if a > x:
            spans.append((x, a))
        x = cx + USBA_HALF_W + USBA_CUT_CLEAR
    if x < HX:
        spans.append((x, HX))
    lows = []
    for a, b in spans:
        segs = probe(lid, 'z', ((a + b) / 2, ym))
        lows.append(segs[0][0] if segs else 99.0)
    ok = all(abs(z - BOARD_TOP) < 0.02 for z in lows)
    r.add(ok, 'lid presses on the board\'s front strip',
          '%d pads, %.1f..%.1f mm wide, at z %.2f..%.2f (board top %.2f)' % (
              len(spans), min(b - a for a, b in spans), max(b - a for a, b in spans), min(lows), max(lows), BOARD_TOP))
    tops = []
    for xp in (-HX + 0.5, -20.0, 0.0, 20.0, HX - 0.5):
        segs = [sg for sg in probe(base, 'z', (xp, ym)) if sg[1] <= 0.5]
        tops.append(segs[-1][1] if segs else -99.0)
    r.add(all(abs(z - (-FRONT_LEDGE_GAP)) < 0.02 for z in tops), 'base ledge under the board\'s front strip',
          'y %.1f..%.1f, x %.0f..%.0f, top at z %.2f..%.2f (board bottom 0)' % (
              FRONT_IN, HY, -HX, HX, min(tops), max(tops)))
    r.info('board held by %d screws (lid bosses on top, standoffs below) and its whole front edge' % len(screw_holes()))
    # no vent within the antenna keep-out either
    dv = min(rect_dist(v[0], (ESP_X[0], ESP_X[1], ANTENNA_Y[0], ANTENNA_Y[1])) for v in vent_slots())
    r.add(dv >= ANTENNA_METAL_KEEPOUT, 'vents away from the antenna area', 'nearest %.1f mm (>= %.0f)' % (
        dv, ANTENNA_METAL_KEEPOUT))
    # a foot recess must not meet an insert pocket (the pocket reaches into the floor)
    pocket_r = INSERT_HOLE_D / 2 if FASTENER == 'insert' else PILOT_D / 2
    df = min(math.hypot(fx - hx, fy - hy) - FOOT_D / 2 - pocket_r for fx, fy in FEET for hx, hy in screw_holes())
    r.add(df >= 0.5, 'foot recesses clear of the screw pockets', 'nearest %.1f mm apart (>= 0.5)' % df)

    r.info('-- 7. lid top face: openings and engraved text')
    openings, texts = top_plate_layout()
    web, wpair = 99.0, ''
    for i, (na, ga, sa) in enumerate(openings):
        for nb, gb, sb in openings[i + 1:]:
            if ga == gb == 'vent':
                continue
            d = sa.distance(sb)
            if d < web:
                web, wpair = d, '%s / %s' % (na, nb)
    r.add(web >= 1.0, 'openings in the top plate keep a 1 mm web', 'min %.2f mm (%s)' % (web, wpair))
    from shapely.geometry import box as sbox
    edge = sbox(-OUT_X, BACK_OUT, OUT_X, FRONT_OUT)
    for k, (txt, ts) in enumerate(texts):
        near = [(edge.exterior.distance(ts), 'lid edge')]
        near += [(ts.distance(s), n) for n, g, s in openings]
        near += [(ts.distance(s2), '"%s"' % t2) for j, (t2, s2) in enumerate(texts) if j != k]
        d, what = min(near)
        r.add(d >= TEXT_CLEAR - 0.005 and edge.contains(ts), 'text "%s" clear' % txt,
              '%.2f mm to the nearest: %s (>= %.1f)' % (d, what, TEXT_CLEAR))

    r.info('-- 8. exported STL files')
    for name in ('printhub-base.stl', 'printhub-lid.stl', 'printhub-feet.stl'):
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            r.info('%s not written: skipped' % name)
            continue
        ok, detail = stl_check(path)
        r.add(ok, name, detail)
    feet = feet_solids()
    fz = [f.bounding_box() for f in feet]
    below = min(FLOOR_BOT - b.min.Z for b in fz)
    fit = all(overlap(f, base) < 1e-4 for f in feet)
    r.add(len(feet) == len(FEET) >= 4 and below >= 3.0 and fit, 'feet under the base',
          '%d printed feet, %.1f mm below the floor (>= 3), in their recesses' % (len(feet), below))
    r.info('-- 9. overhangs in print orientation (faces pointing down, above the bed)')
    known = {'printhub-base.stl': {FOOT_DEPTH: 'foot recess ceilings: %.1f mm round bridges' % FOOT_D},
             'printhub-lid.stl': {TEXT_DEPTH: 'engraved text floors: letter-stroke bridges',
                                  CBORE_DEPTH: 'counterbore floor, bridging layer 1 (spans <= %.1f)' % CBORE_D,
                                  CBORE_DEPTH + BRIDGE_LAYER: 'bridging layer 2 (spans %.1f)' % SCREW_CLEAR_D,
                                  CBORE_DEPTH + 2 * BRIDGE_LAYER: 'square-to-round corners of the bridged hole (tiny)'},
             'printhub-feet.stl': {}}
    if BUTTON_STYLE == 'flexure':
        known['printhub-lid.stl'][FLEX_T] = 'flexure tongue thinning (open upwards: none)'
    for name, levels in known.items():
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        for z, area in overhangs(path):
            what = [t for zz, t in levels.items() if abs(zz - z) < 0.03]
            r.add(bool(what), '%s overhang at z %.2f' % (name[9:-4], z),
                  '%.0f mm^2: %s' % (area, what[0] if what else 'UNEXPECTED, needs support'))

    print('\nFIT CHECK RESULT: %s (%d failed)\n' % ('PASS' if r.fails == 0 else 'FAIL', r.fails))
    return r


def rect_dist(a, b):
    """Distance between two rectangles (x0, x1, y0, y1)."""
    dx = max(b[0] - a[1], 0.0, a[0] - b[1])
    dy = max(b[2] - a[3], 0.0, a[2] - b[3])
    return math.hypot(dx, dy)


def stl_check(path):
    """Closed (every edge shared by exactly two triangles) and lying on z = 0."""
    import numpy as np
    with open(path, 'rb') as f:
        f.read(80)
        n = int(np.frombuffer(f.read(4), np.uint32)[0])
        rec = np.frombuffer(f.read(50 * n), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    V = rec['v'].reshape(-1, 3)
    _, idx = np.unique(np.round(V, 4), axis=0, return_inverse=True)
    tri = idx.reshape(-1, 3)
    edges = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    bad = int((counts != 2).sum())
    zmin, zmax = float(V[:, 2].min()), float(V[:, 2].max())
    return bad == 0 and abs(zmin) < 1e-3, '%d triangles, %s, z %.2f..%.2f (on the bed)' % (
        n, 'watertight' if bad == 0 else '%d open/non-manifold edges' % bad, zmin, zmax)


def overhangs(path):
    """(z, area) of every height where triangles face down (steeper than 60 deg
    from vertical) without sitting on the bed."""
    import numpy as np
    with open(path, 'rb') as f:
        f.read(80)
        n = int(np.frombuffer(f.read(4), np.uint32)[0])
        rec = np.frombuffer(f.read(50 * n), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    T = rec['v'].astype(float)
    nn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    area = np.linalg.norm(nn, axis=1) / 2
    nz = nn[:, 2] / (2 * area + 1e-12)
    zc = np.round(T[:, :, 2].mean(1), 2)
    down = (nz < -0.5) & (zc > 0.05)
    return [(float(z), float(area[down & (zc == z)].sum())) for z in np.unique(zc[down])]


# =============================================================================
# 10. PREVIEW
# =============================================================================
def mesh(shape, tol=PREVIEW_TOL):
    """Triangles (n, 3, 3), wound so the normals point out of the solid."""
    import numpy as np
    v, t = shape.tessellate(tol, 0.3)
    P = np.array([[p.X, p.Y, p.Z] for p in v])
    T = P[np.array(t)]
    if np.einsum('ij,ij->i', T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() < 0:
        T = T[:, ::-1]                                   # make the signed volume positive
    return T


def raster(items, elev, azim, size_px):
    """Orthographic z-buffer render (numpy), flat shaded, with dark lines at
    creases and silhouettes.  items: (shape, rgb, z offset, engraved?).
    Returns an RGB image array; matplotlib only displays it, because its own
    3D painter's sort lets inner faces show through the lid."""
    import numpy as np
    e, a = math.radians(elev), math.radians(azim)
    eye = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    right = np.array([-math.sin(a), math.cos(a), 0.0])
    up = np.cross(eye, right)
    light = 0.55 * eye + np.array([-0.25, -0.35, 0.75])
    light /= np.linalg.norm(light)
    tris, cols, nrms = [], [], []
    for shape, rgb, dz, engraved in items:
        T = mesh(shape) + np.array([0, 0, dz])
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
        keep = n @ eye > 1e-4                               # back-face culling
        T, n = T[keep], n[keep]
        c = np.tile(np.array(rgb, float), (len(T), 1))
        if engraved:                                         # engraving floors and walls in a dark tone
            zs = T[:, :, 2] - dz
            c[(zs.min(1) > TOP_Z - TEXT_DEPTH - 0.02) & (zs.mean(1) < TOP_Z - 0.01)] = (0.22, 0.22, 0.24)
        k = 0.50 + 0.50 * np.clip(n @ light, 0, 1)
        tris.append(T)
        cols.append(np.clip(c * k[:, None], 0, 1))
        nrms.append(n)
    T, C, N = np.concatenate(tris), np.concatenate(cols), np.concatenate(nrms)
    X, Y, Z = T @ right, T @ up, T @ eye                     # screen x, y and depth (bigger = nearer)
    W, H = size_px
    lo = np.array([X.min(), Y.min()])
    hi = np.array([X.max(), Y.max()])
    s = 0.94 * min(W / (hi[0] - lo[0]), H / (hi[1] - lo[1]))
    off = np.array([W, H]) / 2 - s * (lo + hi) / 2
    PX = X * s + off[0]
    PY = H - (Y * s + off[1])
    zbuf = np.full((H, W), -np.inf)
    ibuf = np.full((H, W), -1, dtype=np.int64)
    for i in range(len(T)):
        x, y, z = PX[i], PY[i], Z[i]
        x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, W - 1)
        y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        win = inside & (zz > sub)
        sub[win] = zz[win]
        ibuf[y0:y1 + 1, x0:x1 + 1][win] = i
    img = np.ones((H, W, 3))
    hit = ibuf >= 0
    img[hit] = C[ibuf[hit]]
    # lines: where the surface normal turns sharply or the depth jumps
    nb = np.zeros((H, W, 3))
    nb[hit] = N[ibuf[hit]]
    zb = np.where(hit, zbuf, zbuf[hit].min() - 50 if hit.any() else 0)
    edge = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        n2 = np.roll(nb, (-dy, -dx), (0, 1))
        z2 = np.roll(zb, (-dy, -dx), (0, 1))
        h2 = np.roll(hit, (-dy, -dx), (0, 1))
        crease = (nb * n2).sum(2) < 0.94
        jump = np.abs(zb - z2) > 2.5 / s * 3
        edge |= (hit | h2) & (crease | jump | (hit != h2))
    img[edge] = img[edge] * 0.35
    return img


def _downsample(img, k):
    H, W, _ = img.shape
    return img[:H - H % k, :W - W % k].reshape(H // k, k, W // k, k, 3).mean((1, 3))


def render(base, lid, feet):
    """printhub-preview.png: assembled iso + exploded.  printhub-views.png:
    top (front edge at the bottom), back (USB-C side), underside and the
    lid's heat pads from below."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    board = board_solid()
    conns = [kbox(cx - 6.55, cx + 6.55, USBA_REAR_Y, USBA_MOUTH_Y, BOARD_TOP + 1.0, BOARD_TOP + 6.7) for cx in USBA_X]
    conns += [kbox(cx - USBC_HALF_W, cx + USBC_HALF_W, USBC_MOUTH_Y, USBC_REAR_Y, BOARD_TOP + USBC_Z[0],
                   BOARD_TOP + USBC_Z[1]) for cx in USBC.values()]
    esp = kbox(ESP_X[0], ESP_X[1], ESP_Y[0], ESP_Y[1], BOARD_TOP, BOARD_TOP + ESP_H)
    grey, light_grey, metal = (0.80, 0.80, 0.78), (0.88, 0.88, 0.86), (0.70, 0.72, 0.76)
    pcb = EXPLODE / 2.3
    closed = [(base, grey, 0, False), (lid, light_grey, 0, True)] + [(f, metal, 0, False) for f in feet]
    exploded = ([(base, grey, 0, False), (board, (0.20, 0.52, 0.31), pcb, False)] +
                [(f, metal, -EXPLODE / 3, False) for f in feet] +
                [(c, metal, pcb, False) for c in conns] + [(esp, (0.40, 0.40, 0.43), pcb, False)] +
                [(lid, light_grey, EXPLODE, True)])
    ss = PREVIEW_SUPERSAMPLE

    def sheet(path, panels, figsize):
        fig = plt.figure(figsize=figsize, dpi=PREVIEW_DPI)
        for i, (title, items, elev, azim) in enumerate(panels):
            w = int(figsize[0] * PREVIEW_DPI / len(panels))
            h = int((figsize[1] - 0.5) * PREVIEW_DPI)
            img = _downsample(raster(items, elev, azim, (w * ss, h * ss)), ss)
            ax = fig.add_axes([i / len(panels), 0, 1 / len(panels), 1 - 0.5 / figsize[1]])
            ax.imshow(img, interpolation='lanczos')
            ax.set_axis_off()
            ax.set_title(title, fontsize=11)
        fig.savefig(path, dpi=PREVIEW_DPI, pil_kwargs={'optimize': True})
        plt.close(fig)

    size = '%.1f x %.1f x %.1f mm' % outer_size()
    sheet(os.path.join(HERE, 'printhub-preview.png'),
          [('Print Hub v1 enclosure, assembled (' + size + ')', closed, 30, -60),
           ('Exploded: feet, base, board, lid', exploded, 22, -60)], (13, 5.6))
    sheet(os.path.join(HERE, 'printhub-views.png'),
          [('Top (front edge down)', [(lid, light_grey, 0, True)], 90, -90),
           ('Back: USB-C recesses, left vents', closed, 20, 122),
           ('Underside: printed feet', closed, -50, -60),
           ('Lid from below: heat pads', [(lid, light_grey, 0, False)], -90, -90)], (20, 4.6))


def outer_size():
    return (2 * OUT_X, FRONT_OUT - BACK_OUT, TOP_Z - FLOOR_BOT)


# =============================================================================
# 11. MAIN
# =============================================================================
def main():
    check_only = '--check-only' in sys.argv
    print('Print Hub v1 enclosure')
    print('  outer size %.1f x %.1f x %.1f mm (w x d x h), %.1f mm tall on its printed feet' % (
        outer_size() + (outer_size()[2] + FEET_H,)))
    print('  board bottom at z 0; bottom face %.1f; floor %.1f (pin recess %.1f); split %.2f; ceiling %.2f; top %.2f' % (
        FLOOR_BOT, RAISED_FLOOR_Z, FLOOR_TOP, SPLIT_Z, LID_CEILING_Z, TOP_Z))
    print('  air gaps: above the board %.1f mm (bare board) to %.1f; below %.1f mm (pin recess %.1f)' % (
        PAD_MIN_GAP, max(p[4] for p in heat_pad_rects()), BOTTOM_GAP, -FLOOR_TOP))
    print('  screws: %d x M3 x %g ISO 4762, counterbore %.2f deep; %s' % (
        len(screw_holes()), SCREW_LEN, CBORE_DEPTH,
        '%d x M3 x %g heat-set inserts (hole %.1f)' % (len(screw_holes()), INSERT_LEN, INSERT_HOLE_D)
        if FASTENER == 'insert' else 'self-tapping into %.1f pilot holes' % PILOT_D))
    base = build_base()
    lid = build_lid()
    feet = feet_solids()
    print('  base %.1f cm^3, lid %.1f cm^3, feet %.1f cm^3' % (
        base.volume / 1000, lid.volume / 1000, sum(f.volume for f in feet) / 1000))
    write_gaps_json()
    print('  wrote case_gaps.json')
    if not check_only:
        base.label, lid.label = 'printhub-base', 'printhub-lid'
        for i, f in enumerate(feet, 1):
            f.label = 'printhub-foot-%d' % i
        # the STEP goes out zipped (the repository keeps STEP files zipped)
        raw = os.path.join(tempfile.gettempdir(), 'printhub-enclosure.step')
        export_step(Compound(children=[base, lid] + feet, label='printhub-enclosure'), raw, timestamp=STEP_TIMESTAMP)
        with zipfile.ZipFile(os.path.join(HERE, 'printhub-enclosure-step.zip'), 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=9) as z:
            info = zipfile.ZipInfo('printhub-enclosure.step', date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, open(raw, 'rb').read())
        os.remove(raw)
        # STLs in print orientation, resting on z = 0
        b = Pos(0, 0, -FLOOR_BOT) * base
        export_stl(b, os.path.join(HERE, 'printhub-base.stl'), tolerance=STL_TOL, angular_tolerance=0.2)
        l = Pos(0, 0, TOP_Z) * (Rot(180, 0, 0) * lid)
        export_stl(l, os.path.join(HERE, 'printhub-lid.stl'), tolerance=STL_TOL, angular_tolerance=0.2)
        # the four feet in a row, upright (each prints as a plain cylinder)
        pitch = FEET_PRINT_D + 3.0
        row = [Pos((i - 1.5) * pitch, 0, 0) * kcyl(0, 0, FEET_PRINT_D, 0, FOOT_DEPTH + FEET_H) for i in range(len(FEET))]
        export_stl(Compound(children=row), os.path.join(HERE, 'printhub-feet.stl'), tolerance=STL_TOL,
                   angular_tolerance=0.2)
        render(base, lid, feet)
        print('  wrote printhub-base.stl, printhub-lid.stl, printhub-feet.stl, printhub-enclosure-step.zip,'
              ' printhub-preview.png, printhub-views.png')
    if '--no-check' in sys.argv:
        return 0
    r = fit_check(base, lid)
    return 0 if r.fails == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
