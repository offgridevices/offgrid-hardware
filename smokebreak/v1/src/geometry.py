"""SmokeBreak compact: the one source of every mechanical number.

Two frames:
  case  (fx, fy): mm from the case's back-left outer corner, x toward the
                  drone end, y toward the user, z up from the desk.
  board (x, y):   mm from the board's back-left corner (board.py, place.py).
board = case - BOARD_AT.

The face follows one rule: a single margin M everywhere.  The screen window
sits M from the left and M from the back; the balance well is centred under
the screen and ends M before the front; the switch guard ends M before the
right edge; the Limit rocker is centred under the switch and ends M before
the front.  place.py and the enclosure both import this file.
"""

# ---------------------------------------------------------------- case
CASE_W, CASE_D, CASE_H = 97.0, 56.0, 15.0
CASE_R = 8.0                      # outer corner radius (G2: superellipse, n = 5)
G2_N = 5.0
WALL = 2.4                        # side walls
GAP = 0.3                         # board to wall
BOARD_AT = WALL + GAP             # the board's corner, in case coordinates
FLOOR = 1.4                       # printed floor
PANEL = 1.6                       # top panel (the face)
M = 6.0                           # the one margin

# ---------------------------------------------------------------- board
BOARD_W = CASE_W - 2 * BOARD_AT   # 91.6
BOARD_H = CASE_D - 2 * BOARD_AT   # 48.6
BOARD_R = 5.0
PCB_T = 1.6
PCB_TOP_Z = 4.3                   # floor 1.4 + 1.3 lead clearance + 1.6 board
PANEL_UNDER_Z = CASE_H - PANEL    # 13.4


def b(fx, fy):
    """case -> board coordinates."""
    return fx - BOARD_AT, fy - BOARD_AT


# ---------------------------------------------------------------- screen: EastRising ER-TFT2.25-1
# outline 62.50 x 17.90 x 2.36; active 55.29 x 14.80, 1.61 from the short end
# opposite the FPC, 1.55 from each long edge; 8-pin FPC out of the other end
SCR_WIN = (M, M, 55.0, 14.5)                  # window in the face: x, y, w, h (case)
SCR_WIN_R = 2.2                               # its G2 corner radius
ACTIVE = (55.29, 14.80)
_ax0 = M + SCR_WIN[2] / 2 - ACTIVE[0] / 2     # active area, case
_ay0 = M + SCR_WIN[3] / 2 - ACTIVE[1] / 2
MODULE = (_ax0 - 1.61, _ay0 - 1.55, 62.50, 17.90)     # outline, case: the FPC end is the right end
MODULE_T = 2.36
MODULE_Z = PANEL_UNDER_Z - MODULE_T           # its underside: parts below it stay under this
UNDER_SCREEN_MAX = MODULE_Z - PCB_TOP_Z - 0.4 # tallest part under the module (0.4 for the folded FPC)

# ---------------------------------------------------------------- balance well
XH_PITCH = 6.6                                 # socket centres (bodies 5.75 wide: 0.85 between)
XH_D = 5.75
XH_H = 7.0                                     # top-entry XH height
WELL_MARGIN = 1.2                              # well wall to socket body
WELL_CX = M + SCR_WIN[2] / 2                   # centred under the screen (case x)
WELL_W = 4 * XH_PITCH + XH_D + 2 * WELL_MARGIN
WELL_Y1 = CASE_D - M                           # its front edge (case y)
PIN1_FY = WELL_Y1 - 1.6 - 2.45                 # pin 1 line: the body's front 2.45 past pin 1, 1.6 to the wall
WELL_Y0 = PIN1_FY - 2.5 * 6 - 2.45 - WELL_MARGIN   # the 6S socket's back end, + margin
WELL = (WELL_CX - WELL_W / 2, WELL_Y0, WELL_W, WELL_Y1 - WELL_Y0)
WELL_R = 2.5
WELL_FLOOR_Z = PCB_TOP_Z + XH_H                # the floor plate sits on the sockets' tops
SOCKET_X = [WELL_CX + XH_PITCH * k for k in (-2, -1, 0, 1, 2)]   # 2S .. 6S (case x)

# ---------------------------------------------------------------- switch, ring, guard, rocker
GUARD_W, GUARD_L, GUARD_H = 24.0, 30.0, 13.5
GUARD_X0 = CASE_W - M - GUARD_W
TOG = (GUARD_X0 + GUARD_W / 2, M + 12.0)       # switch centre (case)
RING_R = 9.5                                   # status LEDs on this radius
RING_SLOT = (RING_R - 0.9, RING_R + 0.9)       # the light ring cut in the face
TOG_BUSHING_D = 6.35                           # 1/4-40 thread
TOG_SHOULDER = 8.89                            # PCB to shoulder (C&K 7000 series)
ROCK_W, ROCK_H = 24.0, 8.0
ROCK_Y0 = CASE_D - M - ROCK_H                  # its front edge M from the front
ROCK = (TOG[0] - ROCK_W / 2, ROCK_Y0, ROCK_W, ROCK_H)
ROCK_SW_DX = 6.5                               # its two switches, either side of the centre
ROCK_SW_FY = ROCK_Y0 + 2.7

# ---------------------------------------------------------------- plugs: XT60, XT30 male through the battery end
# both mouths 2.5 mm proud of the end wall (the XT60's body must stop short of the well)
PLUG_PROUD = 2.47
J1_AT = (-BOARD_AT - PLUG_PROUD + 13.17, 27.4)     # board coords of the XT60 footprint origin
J2_AT = (6.3, 43.75)                              # XT30, rotated 270: its pegs must stay on the board, so its mouth sits 0.9 inside the wall
USB_FX = 30.0                                      # USB-C in the back wall (case x)

# ---------------------------------------------------------------- drone leads, out of the drone end
J3_AT = (88.4, 24.5)          # XT60 lead, 12 AWG pads (board)
J4_AT = (88.4, 34.2)          # XT30 lead, 16 AWG pads (board)

# ---------------------------------------------------------------- mounting: M3 into heat-set inserts
HOLES = [(87.0, 4.6), (87.2, 46.2), (56.4, 46.2)]      # board coords
