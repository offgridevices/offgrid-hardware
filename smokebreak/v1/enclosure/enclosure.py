"""SmokeBreak compact enclosure, CadQuery.

    /root/cqenv/bin/python enclosure.py            # refresh the board dump, build, export
    /root/cqenv/bin/python enclosure.py --no-dump  # reuse board_parts.json

Every mechanical number comes from ../src/geometry.py; part positions come
from place.PL via dump_board.py (system python3, pcbnew), written to
board_parts.json beside this file.

Modelling frame: the case frame of geometry.py (x toward the drone end, y
toward the user, z up).  That frame is left-handed, so every exported body is
mirrored y -> CASE_D - y on the way out: the files are in a right-handed frame
with x toward the drone end, Y toward the BACK (the user at Y = 0) and z up,
the same convention as KiCad's 3D view.  Text is built pre-mirrored so it
reads correctly in the files.

Parts (out/<part>.step + .stl): top, bottom, guard, rocker, ring_inlay,
text_inlay; out/assembly.step adds the PCB, the display and the components
as boxes for a visual fit check.  check.py does the fit checks, render.py the
previews.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import cadquery as cq
from cadquery import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'src')
LIB3D = os.path.join(os.path.dirname(HERE), 'lib', 'smokebreak.3dshapes')
FONT_VAR = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'brand', 'fonts', 'InstrumentSans-VariableFont.ttf')
OUT = os.path.join(HERE, 'out')
sys.path.insert(0, SRC)
import geometry as G  # noqa: E402

# ================================================================ design parameters (enclosure only)
CLR = 0.2                     # general part-to-shell clearance
Z_PCB_BOT = G.PCB_TOP_Z - G.PCB_T                    # 2.7
SHELL_TOP_FILLET = 0.6        # outer top edge

# display pocket
POCKET_CLR = 0.2
POCKET_WALL = 1.0
FPC_SLOT_W = 9.0              # FPC exit in the pocket's right wall (the FPC folds down and back to J7)

# balance well
WELL_WALL = 1.2
PLATE_T = 1.0
SOCKET_CLR = 0.15             # plate cutout = XH body + this, each side

# toggle, ring
BUSH_HOLE_D = 6.6
SHOULDER_PAD_R = 4.5          # 0.2 mm ring under the panel: the switch shoulder bears on it
RING_BRIDGE_W = 1.2
RING_BRIDGE_DEG = (45.0, 165.0, 285.0)               # between LEDs (LEDs sit on multiples of 30 deg)

# toggle lever (from lib/smokebreak.3dshapes/SW_Toggle_CK7107.wrl: bushing 8.89-14.99, lever to 26.0 above the PCB)
LEVER_TIP_ABOVE_PCB = 26.0
GUARD_ROOF = 1.6
GUARD_WALL = 1.6
GUARD_LEVER_CLR = 1.0
GUARD_H_FIT = max(G.GUARD_H, G.PCB_TOP_Z + LEVER_TIP_ABOVE_PCB + GUARD_LEVER_CLR + GUARD_ROOF - G.CASE_H)
GUARD_R = 3.0                 # G2 plan corners

# guard hinge: Ø2 steel pin across a bay at the back edge
PIN_D = 2.0
PIN_PRESS_D = 1.9             # in the shell (press fit)
PIN_FREE_D = 2.25             # in the moving part
HINGE_Y, HINGE_Z = 2.6, 13.0  # pin axis (case)
KNUCKLE_R = 2.2
KNUCKLE_X = (73.0, 85.0)
BAY_X = (KNUCKLE_X[0] - 0.4, KNUCKLE_X[1] + 0.4)
BAY_Y1 = 8.0
BAY_FLOOR_Z = HINGE_Z - KNUCKLE_R - 0.4             # 10.4
HINGE_BLOCK = (70.0, G.WALL, 94.6, 8.8, BAY_FLOOR_Z - 1.0, G.PANEL_UNDER_Z)   # x0 y0 x1 y1 z0 z1
GUARD_PIN_X0 = 71.4                                  # blind end in the left lug; open at the right end face
MAGNET_D, MAGNET_T = 4.0, 2.0
MAGNET_POCKET = (4.15, 2.1)

# rocker
ROCK_CLR = 0.25
ROCK_CAP_Z = (13.0, G.CASE_H + 0.4)                  # 0.4 proud of the face
ROCK_PIN_Z = 11.0
ROCK_RIB = (G.TOG[0] - 2.0, G.TOG[0] + 2.0, 9.0)     # x0 x1 z_bottom
ROCK_CRADLE_Y = ((40.0, 41.7), (50.3, 52.0))
ROCK_PIN_LEN = 12.0
NUB_GAP = 0.2                 # nub to B3U actuator at rest
B3U_H = 1.6

# fastening
INSERT_D, INSERT_DEPTH = 4.0, 6.5                    # M3 x 5.7 heat-set inserts
BOSS_R = 3.75
H2_BOSS_TOP_UNDER_ROCKER = 12.0
SCREW_D, CBORE_D, CBORE_DEPTH = 3.4, 6.2, 1.7        # ISO 7380 M3 x 8 button head, flush
STANDOFF_R = 4.5

# floor
FLOOR_CLR = 0.15
BUMPON_D, BUMPON_DEPTH = 10.0, 0.5
FINGER_NOTCH_Z = 2.0          # the back finger lip: the back wall stops this far above the desk plane
HOOK_Y = (12.0, 36.0)         # floor tongue into the battery-end wall (y range)
RIB_W = 1.2

# drone leads: strain relief = the floor's end tab squeezing the wires up into crowns in the end wall
WIRE_Z = 8.0                  # wire centre line where it crosses the end wall
WIRE_D = {'J3': 3.6, 'J4': 2.4}                      # 12 AWG, 16 AWG insulation
WIRE_CROWN_CLR = 0.15
WIRE_SQUEEZE = 0.5            # diametral
LEAD_NOTCH_Y = (17.0, 44.5)

# text
TEXT_CAP = 2.5
TEXT_DEPTH = 0.6

# component heights above the PCB (box check), by footprint name
def part_height(fp):
    n = fp.split(':')[-1]
    table = [
        ('XT60', 8.2), ('XT30', 5.0), ('JST_XH', 7.0), ('SW_Toggle', G.TOG_SHOULDER), ('USB-C', 3.25),
        ('BUZ-', 3.0), ('L_Changjiang', 4.5), ('IND-', 4.5), ('TO-263', 4.6), ('Fuse_', 4.2), ('FH12', 2.0),
        ('FFC-', 2.0), ('KEY-SMD_B3U', B3U_H), ('C_1210', 2.5), ('C_1206', 1.6), ('C_0805', 1.3),
        ('TO-252', 2.4), ('SMB', 2.4), ('D_SMA', 2.4), ('SOT-223', 1.8),
        ('LQFP', 1.7), ('VSSOP', 1.7), ('SOIC', 1.7), ('SSOP', 1.7), ('TSSOP', 1.7), ('VQFN', 1.7),
        ('SOT-', 1.2), ('SC-88', 1.2), ('SOD-', 1.2), ('PG-TDSON', 1.2),
        ('MountingHole', 0.0), ('SWD_Pads', 0.0), ('WirePads', 0.0),
    ]
    for key, h in table:
        if key in n:
            return h
    return 1.0                                       # passives, LEDs, shunt


# ================================================================ board data
def board_parts(refresh=True):
    path = os.path.join(HERE, 'board_parts.json')
    if refresh:
        r = subprocess.run(['python3', os.path.join(HERE, 'dump_board.py')], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)
    with open(path) as f:
        d = json.load(f)
    for v in d.values():
        for k in ('courtyard', 'fab', 'pads'):
            if v[k]:
                v[k] = [v[k][0] + G.BOARD_AT, v[k][1] + G.BOARD_AT, v[k][2] + G.BOARD_AT, v[k][3] + G.BOARD_AT]
        v['cx'], v['cy'] = v['x'] + G.BOARD_AT, v['y'] + G.BOARD_AT
        v['tht'] = [(n, x + G.BOARD_AT, y + G.BOARD_AT, dx, dy, pw) for (n, x, y, dx, dy, pw) in v['tht']]
    return d


def read_wrl(path):
    """VRML IndexedFaceSets -> list of (vertices mm, triangles), in footprint coordinates (y down, z up)."""
    t = open(path).read()
    shapes = []
    for m in re.finditer(r'point\s*\[([^\]]*)\]\s*\}?\s*(?:coordIndex\s*\[([^\]]*)\])?', t):
        pts, idx = m.group(1), m.group(2)
        if idx is None:
            rest = t[m.end():]
            mi = re.search(r'coordIndex\s*\[([^\]]*)\]', rest)
            idx = mi.group(1)
        nums = [float(v) for v in re.findall(r'-?\d+\.?\d*(?:[eE]-?\d+)?', pts)]
        verts = [(nums[i] * 2.54, -nums[i + 1] * 2.54, nums[i + 2] * 2.54) for i in range(0, len(nums) - 2, 3)]
        ids = [int(v) for v in re.findall(r'-?\d+', idx)]
        tris, poly = [], []
        for i in ids:
            if i < 0:
                for j in range(1, len(poly) - 1):
                    tris.append((poly[0], poly[j], poly[j + 1]))
                poly = []
            else:
                poly.append(i)
        shapes.append((verts, tris))
    return shapes


def place_pt(part, p):
    """footprint point (mm, y down) -> case coordinates."""
    th = math.radians(part['rot'])
    x, y, z = p
    xr = x * math.cos(th) + y * math.sin(th)
    yr = -x * math.sin(th) + y * math.cos(th)
    return (part['cx'] + xr, part['cy'] + yr, G.PCB_TOP_Z + z)


def part_mesh_shapes(part, wrl):
    out = []
    for verts, tris in read_wrl(os.path.join(LIB3D, wrl)):
        out.append(([place_pt(part, v) for v in verts], tris))
    return out


# ================================================================ geometry helpers (case frame)
def g2_corner_pts(cx, cy, r, a0, n, k):
    pts = []
    for i in range(k + 1):
        t = math.radians(a0 + 90 * i / k)
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + r * math.copysign(abs(c) ** (2 / n), c), cy + r * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def g2_wire(x0, y0, w, h, r, n=G.G2_N, k=24):
    """Rounded rectangle with superellipse corners |x|^n + |y|^n = r^n (G2 at the joints)."""
    corners = [(x0 + w - r, y0 + r, -90), (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90), (x0 + r, y0 + r, 180)]
    edges, first, prev = [], None, None
    for cx, cy, a0 in corners:
        pts = g2_corner_pts(cx, cy, r, a0, n, k)
        t0 = V(-math.sin(math.radians(a0)), math.cos(math.radians(a0)), 0)
        t1 = V(-math.sin(math.radians(a0 + 90)), math.cos(math.radians(a0 + 90)), 0)
        if prev is not None and math.dist(prev, pts[0]) > 1e-6:
            edges.append(cq.Edge.makeLine(V(*prev, 0), V(*pts[0], 0)))
        edges.append(cq.Edge.makeSpline([V(px, py, 0) for px, py in pts], tangents=[t0, t1]))
        first = first or pts[0]
        prev = pts[-1]
    if math.dist(prev, first) > 1e-6:
        edges.append(cq.Edge.makeLine(V(*prev, 0), V(*first, 0)))
    return cq.Wire.assembleEdges(edges)


def prism(wire, z0, z1):
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(wire), V(0, 0, z1 - z0)).translate(V(0, 0, z0))


def g2_prism(x0, y0, w, h, r, z0, z1, grow=0.0):
    return prism(g2_wire(x0 - grow, y0 - grow, w + 2 * grow, h + 2 * grow, r + grow), z0, z1)


def box(x0, y0, z0, x1, y1, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl_z(x, y, r, z0, z1):
    return cq.Solid.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def cyl_x(y, z, r, x0, x1):
    return cq.Solid.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cyl_y(x, z, r, y0, y1):
    return cq.Solid.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))


def comp(shapes):
    return cq.Compound.makeCompound(list(shapes))


def poly_prism_x(poly_yz, x0, x1):
    """A polygon in the (y, z) plane extruded along x."""
    pts = [V(x0, y, z) for y, z in poly_yz]
    w = cq.Wire.makePolygon(pts + [pts[0]])
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), V(x1 - x0, 0, 0))


def mirror_out(s):
    """case frame -> file frame (right-handed, Y toward the back)."""
    return s.mirror('XZ', V(0, G.CASE_D / 2, 0))


# ================================================================ derived positions
def outer_wire():
    return g2_wire(0, 0, G.CASE_W, G.CASE_D, G.CASE_R)


def inner_wire(extra=0.0):
    return outer_wire().offset2D(-(G.WALL + extra), 'arc')[0]


def plug_profile(part, wrl, x_planes, grow):
    """The plug body's (y, z) section through the end wall, grown by `grow` (shapely)."""
    import numpy as np
    import shapely.geometry as sg
    import shapely.ops as so
    import trimesh
    polys = []
    for verts, tris in part_mesh_shapes(part, wrl):
        if not tris:
            continue
        m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(tris), process=True)
        for xp in x_planes:
            sec = m.section(plane_origin=(xp, 0, 0), plane_normal=(1, 0, 0))
            if sec is None:
                continue
            if len(sec.vertices) >= 3:
                polys.append(sg.MultiPoint([(p[1], p[2]) for p in sec.vertices]).convex_hull)
    body = so.unary_union(polys).convex_hull
    g = body.buffer(grow, join_style=1, resolution=8).simplify(0.01)
    return list(g.exterior.coords)[:-1], body


# ================================================================ the parts
def dbg(name, s):
    if os.environ.get('SB_DEBUG'):
        print(name, round(s.Volume(), 1), len(s.Solids()), s.isValid())


def build(P):
    S = {}
    BA = G.BOARD_AT
    tog_x, tog_y = G.TOG
    holes = [(x + BA, y + BA) for x, y in G.HOLES]
    sw2, sw3 = P['SW2'], P['SW3']
    nubs = [(sw2['cx'], sw2['cy']), (sw3['cx'], sw3['cy'])]

    # ------------------------------------------------------------ top shell
    outer = prism(outer_wire(), 0, G.CASE_H)
    try:
        top_edges = outer.edges(cq.selectors.BoxSelector((-1, -1, G.CASE_H - 0.01), (G.CASE_W + 1, G.CASE_D + 1, G.CASE_H + 0.01)))
        outer = outer.fillet(SHELL_TOP_FILLET, top_edges.vals() if hasattr(top_edges, 'vals') else top_edges)
    except Exception as e:                            # noqa: BLE001
        print('top edge fillet skipped:', e)
    shell = outer.cut(prism(inner_wire(), -1, G.PANEL_UNDER_Z))

    adds = []
    # display pocket frame, merged into the back and left walls
    mx, my, mw, mh = G.MODULE
    px0, py0, px1, py1 = mx - POCKET_CLR, my - POCKET_CLR, mx + mw + POCKET_CLR, my + mh + POCKET_CLR
    fz0 = G.MODULE_Z
    adds.append(box(G.WALL - 0.5, G.WALL - 0.5, fz0, px1 + POCKET_WALL, py1 + POCKET_WALL, G.PANEL_UNDER_Z))
    # balance well walls and floor plate
    wx, wy, ww, wh = G.WELL
    adds.append(g2_prism(wx, wy, ww, wh, G.WELL_R, G.WELL_FLOOR_Z, G.PANEL_UNDER_Z, grow=WELL_WALL))
    # bosses
    for (hx, hy) in holes:
        adds.append(cyl_z(hx, hy, BOSS_R, G.PCB_TOP_Z, G.PANEL_UNDER_Z))
    h2x, h2y = holes[1]
    adds.append(box(h2x + 3.0, h2y - 0.8, 6.0, G.CASE_W - G.WALL + 0.3, h2y + 0.8, G.PANEL_UNDER_Z))   # H2 to the drone-end wall
    adds.append(box(h2x - 0.8, h2y + 3.0, 6.0, h2x + 0.8, G.CASE_D - G.WALL + 0.3, G.PANEL_UNDER_Z))   # H2 to the front wall
    # hinge block (lugs for the guard pin)
    hb = HINGE_BLOCK
    adds.append(box(hb[0], hb[1] - 0.3, hb[4], hb[2], hb[3], hb[5]))
    # rocker pin cradles
    for (cy0, cy1) in ROCK_CRADLE_Y:
        adds.append(box(ROCK_RIB[0], cy0, ROCK_RIB[2], ROCK_RIB[1], cy1, G.PANEL_UNDER_Z))
    # toggle shoulder pad
    adds.append(cyl_z(tog_x, tog_y, SHOULDER_PAD_R, G.PCB_TOP_Z + G.TOG_SHOULDER + 0.01, G.PANEL_UNDER_Z + 0.01))
    shell = shell.fuse(*adds).clean()
    dbg('shell+adds', shell)
    shell = shell.intersect(outer)                    # nothing outside the skin
    dbg('shell&outer', shell)

    cuts = []
    # display: window and pocket (+ the FPC exit at its right end)
    cuts.append(g2_prism(*G.SCR_WIN, G.SCR_WIN_R, G.PANEL_UNDER_Z - 1, G.CASE_H + 1))
    cuts.append(box(px0, py0, fz0 - 1, px1, py1, G.PANEL_UNDER_Z))
    fpc_cy = my + mh / 2
    cuts.append(box(px1 - 0.5, fpc_cy - FPC_SLOT_W / 2, fz0 - 1, px1 + POCKET_WALL + 0.5, fpc_cy + FPC_SLOT_W / 2, G.PANEL_UNDER_Z))
    # balance well: open down to the plate, one cutout per socket through the plate
    cuts.append(g2_prism(wx, wy, ww, wh, G.WELL_R, G.WELL_FLOOR_Z + PLATE_T, G.CASE_H + 1))
    for ref in ('J12', 'J11', 'J10', 'J9', 'J5'):
        fx0, fy0, fx1, fy1 = P[ref]['fab']
        cuts.append(box(fx0 - SOCKET_CLR, fy0 - SOCKET_CLR, G.WELL_FLOOR_Z - 0.5, fx1 + SOCKET_CLR, fy1 + SOCKET_CLR,
                        G.WELL_FLOOR_Z + PLATE_T + 0.5))
    # toggle bushing, light ring
    cuts.append(cyl_z(tog_x, tog_y, BUSH_HOLE_D / 2, G.PANEL_UNDER_Z - 1, G.CASE_H + 1))
    S['ring_inlay'] = ring = ring_solid(tog_x, tog_y, G.PANEL_UNDER_Z, G.CASE_H)
    cuts.append(ring_solid(tog_x, tog_y, G.PANEL_UNDER_Z - 0.5, G.CASE_H + 1))
    # rocker opening; the H2 boss steps down under it
    rx, ry, rw, rh = G.ROCK
    cuts.append(g2_prism(rx, ry, rw, rh, 2.5, H2_BOSS_TOP_UNDER_ROCKER, G.CASE_H + 1, grow=ROCK_CLR))
    cuts.append(cyl_y(G.TOG[0], ROCK_PIN_Z, PIN_PRESS_D / 2, ROCK_CRADLE_Y[0][0] - 0.5, ROCK_CRADLE_Y[1][1]))
    # guard hinge bay (open to the back) and the pin bore (blind left, open at the drone end)
    cuts.append(box(BAY_X[0], -1, BAY_FLOOR_Z, BAY_X[1], BAY_Y1, G.CASE_H + 1))
    cuts.append(cyl_x(HINGE_Y, HINGE_Z, PIN_PRESS_D / 2, GUARD_PIN_X0, G.CASE_W + 1))
    # heat-set insert holes
    for (hx, hy) in holes:
        cuts.append(cyl_z(hx, hy, INSERT_D / 2, G.PCB_TOP_Z - 0.5, G.PCB_TOP_Z + INSERT_DEPTH))
    # battery end: XT60 and XT30 through the wall
    j1 = P['J1']
    prof, _ = plug_profile(j1, 'CONN-TH_XT60PW-M.wrl', [0.05, 0.6, 1.2, 1.8, 2.35], CLR)
    cuts.append(poly_prism_x(prof, -1.0, G.WALL + 0.6))
    b = j1['courtyard']
    cuts.append(box(G.WALL - 0.1, b[1] - 0.3, G.PCB_TOP_Z - 0.3, wx, b[3] + 0.3,
                    G.PCB_TOP_Z + 8.1 + 0.3))
    j2 = P['J2']
    prof, _ = plug_profile(j2, 'CONN-TH_XT30PW-M.wrl', [0.05, 0.6, 1.2, 1.8, 2.35], CLR)
    cuts.append(poly_prism_x(prof, -1.0, G.WALL + 0.6))
    prof, _ = plug_profile(j2, 'CONN-TH_XT30PW-M.wrl', [0.05, 0.6, 1.2, 1.8, 2.35], CLR + 0.4)
    cuts.append(poly_prism_x(prof, -1.0, 1.1))       # counterbore for the female's shoulder (its mouth sits 1 mm in)
    # back wall: USB-C (stadium 9.2 x 3.4, centre z PCB+1.6) with an outside counterbore for the plug overmold
    j8 = P['J8']
    uz = G.PCB_TOP_Z + 1.63
    cuts.append(stadium_y(j8['cx'], uz, 9.2, 3.4, -1, G.WALL + 0.5))
    cuts.append(stadium_y(j8['cx'], uz, 12.4, 6.4, -1, 1.4))
    # drone end: one notch for the four leads (the floor's tab closes it from below), crowns over each wire
    cuts.append(box(G.CASE_W - G.WALL - 0.1, LEAD_NOTCH_Y[0], -1, G.CASE_W + 1, LEAD_NOTCH_Y[1], WIRE_Z))
    for ref in ('J3', 'J4'):
        for (_, _, py, _, _, _) in P[ref]['tht']:
            cuts.append(cyl_x(py, WIRE_Z, WIRE_D[ref] / 2 + WIRE_CROWN_CLR, G.CASE_W - G.WALL - 0.5, G.CASE_W + 1))
    # back finger lip: the back wall stops FINGER_NOTCH_Z above the desk plane along the straight back edge
    cuts.append(box(G.CASE_R, -1, -1, G.CASE_W - G.CASE_R, G.WALL + 0.05, FINGER_NOTCH_Z))
    # floor hook groove in the battery-end wall
    cuts.append(box(1.6, HOOK_Y[0] - 0.5, 1.5, G.WALL + 0.1, HOOK_Y[1] + 0.5, 2.5))
    # component clearance (everything not designed to pass through)
    skip = {'J1', 'J2', 'J8', 'SW1', 'J3', 'J4', 'J5', 'J9', 'J10', 'J11', 'J12'}
    for ref, p in P.items():
        h = part_height(p['fp'])
        if ref in skip or h <= 0 or p['side'] != 'T' or not p['courtyard']:
            continue
        c = p['courtyard']
        cuts.append(box(c[0], c[1], G.PCB_TOP_Z - 0.5, c[2], c[3], G.PCB_TOP_Z + h + 0.3))
    c = j8['courtyard']
    cuts.append(box(c[0], G.WALL, G.PCB_TOP_Z - 0.5, c[2], c[3], G.PCB_TOP_Z + 3.25 + 0.3))
    c = j2['courtyard']
    cuts.append(box(G.WALL - 0.1, c[1], G.PCB_TOP_Z - 0.5, c[2] + 0.3, c[3], G.PCB_TOP_Z + 5.0 + 0.3))
    # text pockets
    S['text_inlay'] = text = text_solids(P)
    cuts.append(text)
    shell = shell.cut(*cuts).clean()
    S['top'] = shell

    # ------------------------------------------------------------ floor
    S['bottom'] = floor_solid(P, holes)

    # ------------------------------------------------------------ guard
    S['guard'] = guard_solid()

    # ------------------------------------------------------------ rocker
    S['rocker'] = rocker_solid(nubs)
    return S


def stadium_y(cx, cz, w, h, y0, y1):
    """A slot w (x) by h (z) with round ends, along y."""
    r = h / 2
    body = box(cx - w / 2 + r, y0, cz - r, cx + w / 2 - r, y1, cz + r)
    return body.fuse(cyl_y(cx - w / 2 + r, cz, r, y0, y1), cyl_y(cx + w / 2 - r, cz, r, y0, y1)).clean()


def ring_solid(cx, cy, z0, z1):
    r0, r1 = G.RING_SLOT
    ring = cyl_z(cx, cy, r1, z0, z1).cut(cyl_z(cx, cy, r0, z0 - 1, z1 + 1))
    bridges = []
    for a in RING_BRIDGE_DEG:
        br = box(r0 - 1, -RING_BRIDGE_W / 2, z0 - 1, r1 + 1, RING_BRIDGE_W / 2, z1 + 1)
        bridges.append(br.rotate(V(0, 0, 0), V(0, 0, 1), a).translate(V(cx, cy, 0)))
    return ring.cut(*bridges).clean()


_FONT = None


def bold_font():
    """Instance the brand variable font at weight 700 (CadQuery text needs a static font)."""
    global _FONT
    if _FONT:
        return _FONT
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    f = TTFont(FONT_VAR)
    axes = {a.axisTag: (a.minValue, a.maxValue) for a in f['fvar'].axes}
    loc = {'wght': min(700, axes['wght'][1])}
    for tag, (lo, hi) in axes.items():
        if tag != 'wght':
            loc[tag] = None
    inst = instancer.instantiateVariableFont(f, {'wght': loc['wght']}, overlap=instancer.OverlapMode.REMOVE)
    d = tempfile.mkdtemp(prefix='sbfont')
    path = os.path.join(d, 'InstrumentSans-Bold.ttf')
    inst.save(path)
    cap = inst['OS/2'].sCapHeight / inst['head'].unitsPerEm
    _FONT = (path, cap)
    return _FONT


TEXT_LABELS = None


def text_labels():
    labels = [(f'{k + 2}S', G.SOCKET_X[k]) for k in range(5)] + [('LIMIT', G.TOG[0])]
    return labels


def glyph_polygons(txt, cap_h):
    """Text outline as shapely polygons (mm, baseline at y = 0, centred on x = 0), from the brand font
    instanced at weight 700 with overlaps removed; curves flattened to 0.01 mm."""
    import shapely.geometry as sg
    import shapely.ops as so
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont
    path, cap = bold_font()
    font = TTFont(path)
    upm = font['head'].unitsPerEm
    k = cap_h / (cap * upm)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()

    class Flat(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.contours, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            for i in range(1, 17):
                t = i / 16
                a, b_, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
                self.cur.append((a * p0[0] + b_ * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b_ * p1[1] + c * p2[1] + d * p3[1]))

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for i in range(1, 13):
                t = i / 12
                a, b_, c = (1 - t) ** 2, 2 * t * (1 - t), t * t
                self.cur.append((a * p0[0] + b_ * p1[0] + c * p2[0], a * p0[1] + b_ * p1[1] + c * p2[1]))

        def _closePath(self):
            if len(self.cur) >= 3:
                self.contours.append(self.cur)
            self.cur = []

        _endPath = _closePath

    shapes, x = [], 0.0
    for ch in txt:
        gname = cmap[ord(ch)]
        pen = Flat(gs)
        gs[gname].draw(pen)
        geo = None
        for c in pen.contours:
            pg = sg.Polygon([((px + x) * k, py * k) for px, py in c]).buffer(0)
            geo = pg if geo is None else geo.symmetric_difference(pg)
        if geo is not None:
            shapes.append(geo)
        x += font['hmtx'][gname][0]
    geo = so.unary_union(shapes)
    minx, miny, maxx, maxy = geo.bounds
    from shapely import affinity
    geo = affinity.translate(geo, -(minx + maxx) / 2, 0).simplify(0.005)
    return list(geo.geoms) if geo.geom_type == 'MultiPolygon' else [geo]


def text_solids(P):
    """'2S'..'6S' under the sockets and 'LIMIT' under the rocker, one baseline, cap height centred in the
    front margin; sunk TEXT_DEPTH into the face.  Built in the file frame's orientation, mirrored into
    the case frame (the export mirrors it back)."""
    y_mid = G.CASE_D - G.M / 2
    out = []
    for txt, x in text_labels():
        for pg in glyph_polygons(txt, TEXT_CAP):
            def wire(coords):
                pts = [V(px + x, y_mid + TEXT_CAP / 2 - py, 0) for px, py in list(coords)[:-1]]    # mirrored: y -> -y
                return cq.Wire.makePolygon(pts + [pts[0]])
            f = cq.Face.makeFromWires(wire(pg.exterior.coords), [wire(i.coords) for i in pg.interiors])
            out.append(cq.Solid.extrudeLinear(f, V(0, 0, TEXT_DEPTH + 0.01)).translate(V(0, 0, G.CASE_H - TEXT_DEPTH)))
    return comp(out)


def floor_solid(P, holes):
    fw = inner_wire(FLOOR_CLR)
    floor = prism(fw, 0, G.FLOOR)
    adds = []
    # PCB standoffs at the screws (the screw stack: head, floor, standoff, PCB, boss)
    for hx, hy in holes:
        adds.append(cyl_z(hx, hy, STANDOFF_R, G.FLOOR - 0.01, Z_PCB_BOT))
    # back lip rim (the finger lip's inner face)
    adds.append(box(G.CASE_R, G.WALL + FLOOR_CLR, G.FLOOR - 0.01, G.CASE_W - G.CASE_R, G.WALL + FLOOR_CLR + 0.6,
                    FINGER_NOTCH_Z))
    # hook: lip + tongue into the battery-end wall groove
    adds.append(box(G.WALL + FLOOR_CLR, HOOK_Y[0], G.FLOOR - 0.01, G.WALL + FLOOR_CLR + 0.8, HOOK_Y[1], 2.4))
    adds.append(box(1.7, HOOK_Y[0], 1.65, G.WALL + FLOOR_CLR + 0.1, HOOK_Y[1], 2.35))
    # drone-lead clamp tab: fills the end-wall notch, saddles squeeze the wires up into the crowns
    tab = box(G.CASE_W - G.WALL - 0.1, LEAD_NOTCH_Y[0] + FLOOR_CLR, 0, G.CASE_W, LEAD_NOTCH_Y[1] - FLOOR_CLR,
              WIRE_Z - 0.1).fuse(box(G.CASE_W - G.WALL - FLOOR_CLR - 0.05, LEAD_NOTCH_Y[0] + FLOOR_CLR, 0, G.CASE_W - G.WALL,
                                     LEAD_NOTCH_Y[1] - FLOOR_CLR, G.FLOOR))
    tab = tab.intersect(prism(outer_wire(), -1, G.CASE_H))
    sad = []
    for ref in ('J3', 'J4'):
        for (_, _, py, _, _, _) in P[ref]['tht']:
            sad.append(cyl_x(py, WIRE_Z, WIRE_D[ref] / 2 - WIRE_SQUEEZE / 2, G.CASE_W - G.WALL - 1, G.CASE_W + 1))
    adds.append(tab.cut(*sad))
    # PCB support ribs (0.1 short of the PCB), clear of every through-hole lead
    ribs = []
    rib_top = Z_PCB_BOT - 0.1
    for k in range(4):
        x = (G.SOCKET_X[k] + G.SOCKET_X[k + 1]) / 2
        ribs.append(box(x - RIB_W / 2, G.WELL[1] + 1, G.FLOOR - 0.01, x + RIB_W / 2, G.WELL[1] + G.WELL[3] - 0.5, rib_top))
    ry = (P['SW2']['cy'] + P['SW3']['cy']) / 2
    ribs.append(box(P['SW2']['cx'] - 2, ry - RIB_W / 2, G.FLOOR - 0.01, P['SW3']['cx'] + 1, ry + RIB_W / 2, rib_top))
    keep = []
    for ref, p in P.items():
        for (_, x, y, dx, dy, pw) in p['tht']:
            if ref.startswith('H'):
                continue
            keep.append(cyl_z(x, y, pw / 2 + 1.0, 0, 5))
        if p['side'] == 'B' and p['courtyard']:
            c = p['courtyard']
            keep.append(box(c[0], c[1], 0, c[2], c[3], 5))
    for hx, hy in holes:
        keep.append(cyl_z(hx, hy, STANDOFF_R + 0.5, 0, 5))
    adds.append(comp(ribs).cut(*keep))
    floor = floor.fuse(*adds).clean()
    cuts = []
    for hx, hy in holes:
        cuts.append(cyl_z(hx, hy, SCREW_D / 2, -1, 5))
        cuts.append(cyl_z(hx, hy, CBORE_D / 2, -1, CBORE_DEPTH))
    for bx, by in bumpon_xy(holes):
        cuts.append(cyl_z(bx, by, BUMPON_D / 2, -1, BUMPON_DEPTH))
    return floor.cut(*cuts).clean()


def bumpon_xy(holes):
    return [(9.5, 9.5), (9.5, G.CASE_D - 9.5), (80.5, 9.5), (80.5, G.CASE_D - 9.5)]


def guard_solid():
    x0 = G.GUARD_X0
    y0 = G.M
    z0, z1 = G.CASE_H, G.CASE_H + GUARD_H_FIT
    w, l = G.GUARD_W, G.GUARD_L
    body = g2_prism(x0, y0, w, l, GUARD_R, z0, z1)
    inner = g2_prism(x0 + GUARD_WALL, y0 + GUARD_WALL, w - 2 * GUARD_WALL, l - 2 * GUARD_WALL, GUARD_R - GUARD_WALL + 0.2,
                     z0 - 1, z1 - GUARD_ROOF)
    g = body.cut(inner)
    # magnet block in the tip, over U6
    tip_y1 = y0 + l
    mag_y = tip_y1 - 0.6 - MAGNET_POCKET[0] / 2
    blk = box(G.TOG[0] - 3.5, mag_y - 3.0, z0, G.TOG[0] + 3.5, tip_y1 - 0.5, z0 + MAGNET_POCKET[1] + 1.0)
    g = g.fuse(blk)
    # thumb tab at the tip
    tab = g2_prism(G.TOG[0] - 6.0, tip_y1 - 3.0, 12.0, 5.0, 1.5, z1 - GUARD_ROOF, z1)
    g = g.fuse(tab)
    # knuckle and web down into the hinge bay
    kx0, kx1 = KNUCKLE_X
    web = box(kx0, HINGE_Y, HINGE_Z, kx1, y0 + GUARD_WALL, z0 + 1.0)
    knuckle = cyl_x(HINGE_Y, HINGE_Z, KNUCKLE_R, kx0, kx1)
    g = g.fuse(web, knuckle).clean()
    g = g.cut(cyl_x(HINGE_Y, HINGE_Z, PIN_FREE_D / 2, kx0 - 1, kx1 + 1),
              cyl_z(G.TOG[0], mag_y, MAGNET_POCKET[0] / 2, z0 - 1, z0 + MAGNET_POCKET[1])).clean()
    return g


def guard_rotated(g, deg):
    return g.rotate(V(0, HINGE_Y, HINGE_Z), V(1, HINGE_Y, HINGE_Z), deg)


def rocker_solid(nubs):
    rx, ry, rw, rh = G.ROCK
    cap = g2_prism(rx, ry, rw, rh, 2.5, *ROCK_CAP_Z)
    rib = box(ROCK_RIB[0], ry + 0.3, ROCK_RIB[2], ROCK_RIB[1], ry + rh - 0.3, ROCK_CAP_Z[0] + 0.01)
    parts = [rib]
    sw_top = G.PCB_TOP_Z + B3U_H
    for (nx, ny) in nubs:
        parts.append(cyl_z(nx, ny, 1.5, sw_top + NUB_GAP + 1.0, ROCK_CAP_Z[0] + 0.01))
        parts.append(cyl_z(nx, ny, 0.8, sw_top + NUB_GAP, sw_top + NUB_GAP + 1.01))
    r = cap.fuse(*parts).clean()
    return r.cut(cyl_y(G.TOG[0], ROCK_PIN_Z, PIN_FREE_D / 2, ry - 1, ry + rh + 1)).clean()


def rocker_rotated(r, deg):
    return r.rotate(V(G.TOG[0], 0, ROCK_PIN_Z), V(G.TOG[0], 1, ROCK_PIN_Z), deg)


# ================================================================ assembly context (PCB, display, parts)
def context_solids(P):
    BA = G.BOARD_AT
    pcb = prism(g2_wire(BA, BA, G.BOARD_W, G.BOARD_H, G.BOARD_R, n=2.0), Z_PCB_BOT, G.PCB_TOP_Z)
    pcb = pcb.cut(*[cyl_z(x + BA, y + BA, 1.6, 0, 6) for x, y in G.HOLES])
    mx, my, mw, mh = G.MODULE
    display = box(mx, my, G.MODULE_Z, mx + mw, my + mh, G.MODULE_Z + G.MODULE_T)
    boxes = {}
    for ref, p in P.items():
        h = part_height(p['fp'])
        if h <= 0 or not p['courtyard'] or p['side'] != 'T':
            continue
        c = p['fab'] if 'JST_XH' in p['fp'] else p['courtyard']
        boxes[ref] = box(c[0], c[1], G.PCB_TOP_Z, c[2], c[3], G.PCB_TOP_Z + h)
    tx, ty = G.TOG
    z = G.PCB_TOP_Z
    toggle_top = cyl_z(tx, ty, G.TOG_BUSHING_D / 2, z + G.TOG_SHOULDER, z + 14.99).fuse(
        cq.Solid.makeCone(1.6, 1.15, LEVER_TIP_ABOVE_PCB - 15.0, V(tx, ty, z + 15.0), V(0, 0, 1)))
    wires = []
    for ref in ('J3', 'J4'):
        r = WIRE_D[ref] / 2
        for (_, x, y, _, _, _) in P[ref]['tht']:
            wires.append(cyl_z(x, y, r, Z_PCB_BOT - 1.0, WIRE_Z))
            wires.append(cq.Solid.makeSphere(r, V(x, y, WIRE_Z), angleDegrees1=-90, angleDegrees2=90))
            wires.append(cyl_x(y, WIRE_Z, r, x, G.CASE_W + 8))
    return dict(pcb=pcb, display=display, boxes=boxes, toggle_top=toggle_top,
                wires=cq.Compound.makeCompound(wires))


# ================================================================ export
PART_NAMES = ('top', 'bottom', 'guard', 'rocker', 'ring_inlay', 'text_inlay')
COLORS = {'top': (0.16, 0.15, 0.13), 'bottom': (0.22, 0.21, 0.19), 'guard': (0.89, 0.36, 0.0),
          'rocker': (0.72, 0.74, 0.76), 'ring_inlay': (0.85, 0.95, 0.88), 'text_inlay': (0.95, 0.93, 0.88)}


def export_all(S, P):
    os.makedirs(OUT, exist_ok=True)
    for name in PART_NAMES:
        s = mirror_out(S[name])
        cq.exporters.export(s, os.path.join(OUT, f'{name}.step'))
        cq.exporters.export(s, os.path.join(OUT, f'{name}.stl'), tolerance=0.01, angularTolerance=0.1)
    ctx = context_solids(P)
    asm = cq.Assembly(name='smokebreak')
    for name in PART_NAMES:
        asm.add(mirror_out(S[name]), name=name, color=cq.Color(*COLORS[name], 1.0))
    asm.add(mirror_out(ctx['pcb']), name='pcb', color=cq.Color(0.1, 0.1, 0.1, 1))
    asm.add(mirror_out(ctx['display']), name='display_module', color=cq.Color(0.02, 0.02, 0.05, 1))
    asm.add(mirror_out(ctx['toggle_top']), name='SW1_bushing_lever', color=cq.Color(0.8, 0.8, 0.82, 1))
    asm.add(mirror_out(ctx['wires']), name='drone_leads', color=cq.Color(0.7, 0.1, 0.1, 1))
    for ref, b in ctx['boxes'].items():
        asm.add(mirror_out(b), name=f'part_{ref}', color=cq.Color(0.55, 0.6, 0.5, 1))
    asm.save(os.path.join(OUT, 'assembly.step'), 'STEP')
    # context meshes for the previews and the fit check (export frame)
    cdir = os.path.join(OUT, 'context')
    os.makedirs(cdir, exist_ok=True)
    stl = lambda s, n: cq.exporters.export(mirror_out(s), os.path.join(cdir, n), tolerance=0.02, angularTolerance=0.2)
    stl(ctx['pcb'], 'pcb.stl')
    stl(ctx['display'], 'display.stl')
    stl(ctx['toggle_top'], 'toggle.stl')
    stl(ctx['wires'], 'wires.stl')
    stl(comp([b for r, b in ctx['boxes'].items() if r not in ('J1', 'J2', 'J8')]), 'parts.stl')
    import numpy as np
    import trimesh
    for ref, wrl, pre in (('J1', 'CONN-TH_XT60PW-M.wrl', 'xt'), ('J2', 'CONN-TH_XT30PW-M.wrl', 'xt'),
                          ('J8', 'USB-C_SMD-TYPE-C-31-M-12_1.wrl', 'usb')):
        ms = [trimesh.Trimesh(np.array(v), np.array(t)) for v, t in part_mesh_shapes(P[ref], wrl) if t]
        m = trimesh.util.concatenate(ms)
        m.vertices[:, 1] = G.CASE_D - m.vertices[:, 1]
        m.invert()
        m.export(os.path.join(cdir, f'{pre}_{ref}.stl'))
    return ctx


def main():
    refresh = '--no-dump' not in sys.argv
    P = board_parts(refresh)
    S = build(P)
    for k, s in S.items():
        print(f'{k:12s} valid={s.isValid()} volume={s.Volume():9.1f} mm3 solids={len(s.Solids())}')
    export_all(S, P)
    print('guard height above the face', round(GUARD_H_FIT, 2), '(geometry.py GUARD_H', G.GUARD_H, ')')
    print('exported to', OUT)


if __name__ == '__main__':
    main()
