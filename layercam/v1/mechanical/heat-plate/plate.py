# -*- coding: utf-8 -*-
"""LayerCam v1: three ways to take the RV1106's heat towards the lid, as parts.

    tools/kd python3 mechanical/heat-plate/plate.py      (from layercam/v1)

writes, next to this file:
    sheet_bracket.stl      option 3: one piece of 1.5 mm 5052 sheet, bent twice (Z shape)
    cnc_block.stl          option 2: one CNC-machined 6061 part (foot, column, flange)
    heatsink_14x14x6.stl   option 1: an off-the-shelf 14 x 14 x 6 mm heatsink, as an envelope
    drawing.png            plan, section and flat pattern with the dimensions
    heat_paths.json        each option's thermal path, read by sim/thermal.py

All coordinates are the lens frame of src/geometry.py (origin on the lens axis at the case's outer front
face, +Z into the case, X / Y as seen from behind; board y = -Y).

The housing numbers below were measured from Prusa's STLs (Printables 1343977, buddy-camera-bottom-r2,
-top-r1, -lid-r1, assembled as in docs/housing.md) on 26-27 Oct 2026 by casting rays up from Z 21.0 on a
0.25 mm grid.  Set HOUSING_DIR to a folder with asm_bottom.stl / asm_top.stl / asm_lid.stl (the assembled
copies) and the script re-measures and checks every part's clearance against the real case.
"""
import json, math, os, sys
import numpy as np
import trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(V1, 'src'))
import geometry as G

# ---------------------------------------------------------------- the housing (measured)
LID_UNDER_Z = 38.5            # underside of the lid inside its vent-window pocket
LID_TOP_Z = 41.85             # the lid's outer face: slots 3.35 mm deep
SLOT_X = (-10.0, 10.0)        # six through-slots, 20 x 2 mm, 4 mm pitch
SLOT_YC = (-14.5, -10.5, -6.5, -2.5, 1.5, 5.5)
SLOT_W = 2.0
# the pocket the slots open from (ceiling at LID_UNDER_Z): half-width against Y; outside it the ceiling
# drops to Z 32 (X +-13 .. 15) and, towards the round end, follows the shell down to Z 27-30 over the SoC
POCKET = [(-21.0, 4.25), (-20.5, 6.25), (-20.0, 7.75), (-19.5, 9.0), (-19.0, 10.25), (-18.5, 11.0),
          (8.0, 11.0)]
# lowest ceiling over a 14 x 14 footprint centred at (0, Y) (for the off-the-shelf heatsink)
CEIL_14 = {-19.4: 27.50, -18.9: 28.22, -18.4: 28.94, -17.9: 29.66, -17.4: 30.37, -16.9: 31.08, -16.4: 31.80,
           -15.9: 32.51}

# ---------------------------------------------------------------- the board
BOARD_T = 1.55                                # PCBWay's regular 6-layer '1.6 mm' build: 1.55 finished, +-10 %
BOARD_BACK_Z = G.SEAT_Z + BOARD_T             # 20.85
SOC_X, SOC_Y = 0.0, -19.4                     # board (0, 19.4): layout_main.FIXED['U1']
SOC_W, SOC_H = 12.3, 0.85                     # QFN-128 12.3 x 12.3, 0.85 mm (0.90 max)
SOC_TOP_Z = BOARD_BACK_Z + SOC_H              # 21.75
MODULE = (-G.MODULE_W / 2, -8.4, G.MODULE_W / 2, 15.6)    # camera module on the back face (docs/housing.md)
MODULE_TOP_Z = BOARD_BACK_Z + G.MODULE_SHIM + G.MODULE_PCB_T + 3.0   # + its connector and parts (3 mm, est.)
LED1 = (8.8, -14.0)                           # status LED, meant to show through slot 1

# ---------------------------------------------------------------- materials and pads
K_AL5052, K_AL6061, K_AIR = 138.0, 167.0, 0.030
THETA_JC_SOC = 8.4                            # RV1106G2/G3 junction to case (top), datasheet table 4-1
# t-Global TG-A6200: 6.2 W/mK ultra-soft silicone pad, tacky both sides (Digi-Key 1168-TG-A6200-...-ND)
PAD = dict(k=6.2, name='t-Global TG-A6200')
PAD_BOTTOM = (1.5, 0.30)                      # thickness, compression (30 %): absorbs the stack tolerance
PAD_TOP = (0.5, 0.20)
# 3M 8810 thermally conductive tape (the usual heatsink tape), 0.25 mm, ~0.6 W/mK
TAPE = dict(t=0.25, k=0.6, name='3M 8810')
INTERFACE_R = 0.3                             # K/W, the two contact interfaces of a pad (estimate)

T_SHEET = 1.5
BEND_R = 1.5                                  # inside bend radius = t (5052-H32 bends tight)


def pocket_halfwidth(y):
    ys, hs = zip(*POCKET)
    return float(np.interp(y, ys, hs, left=0.0, right=0.0))


# ---------------------------------------------------------------- option 3: the bent sheet
def sheet_bracket():
    """Z-shaped bracket: foot on the SoC, web up at Y -14.7..-13.2, flange in the lid pocket."""
    foot_z0 = SOC_TOP_Z + PAD_BOTTOM[0] * (1 - PAD_BOTTOM[1])       # underside of the foot
    flange_z1 = LID_UNDER_Z - PAD_TOP[0] * (1 - PAD_TOP[1])         # top of the flange
    web_y1 = SOC_Y + SOC_W / 2 + 0.05                                # web's outer (+Y) face just past the SoC
    web_y0 = web_y1 - T_SHEET
    d = dict(foot=(-6.0, 6.0, SOC_Y - SOC_W / 2 + 0.15, web_y1, foot_z0, foot_z0 + T_SHEET),
             web=(-6.0, 6.0, web_y0, web_y1, foot_z0, flange_z1),
             flange=(-10.6, 10.6, web_y0, 7.6, flange_z1 - T_SHEET, flange_z1))
    # outline of the parts as boxes; bends drawn as quarter rounds in the STL
    meshes = []
    fx0, fx1, fy0, fy1, fz0, fz1 = d['foot']
    meshes.append(box_mesh(fx0, fx1, fy0, web_y0 - BEND_R + 0.0, fz0, fz1))
    meshes.append(box_mesh(-6.0, 6.0, web_y0, web_y1, fz0 + T_SHEET + BEND_R, flange_z1 - T_SHEET - BEND_R))
    meshes.append(box_mesh(-10.6, 10.6, web_y0 + T_SHEET + BEND_R, 7.6, flange_z1 - T_SHEET, flange_z1))
    meshes.append(bend_mesh(-6.0, 6.0, (web_y0 - BEND_R, fz0 + T_SHEET + BEND_R), BEND_R, 'low'))
    meshes.append(bend_mesh(-6.0, 6.0, (web_y1 + BEND_R, flange_z1 - T_SHEET - BEND_R), BEND_R, 'high'))
    # the flange's 6 mm-wide strip that carries the second bend joins the 21.2 mm flange (relief cut at +-6)
    m = trimesh.util.concatenate(meshes)
    # flat pattern (neutral axis K = 0.4)
    k = 0.4
    ba = math.pi / 2 * (BEND_R + k * T_SHEET)
    foot_flat = (web_y0 - BEND_R) - fy0
    web_flat = (flange_z1 - T_SHEET - BEND_R) - (fz0 + T_SHEET + BEND_R)
    flange_flat = 7.6 - (web_y0 + T_SHEET + BEND_R)
    flat = dict(foot=foot_flat, bend=ba, web=web_flat, flange=flange_flat,
                total=foot_flat + web_flat + flange_flat + 2 * ba)
    return m, d, flat


def box_mesh(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
    b.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return b


def prism(pts, axis_from, axis_to):
    """A convex polygon pts [(u, v)] extruded along w from axis_from to axis_to (fan-triangulated, so no
    triangulation library is needed); returns vertices in (u, v, w)."""
    n = len(pts)
    v = [(u, vv, axis_from) for u, vv in pts] + [(u, vv, axis_to) for u, vv in pts]
    f = []
    for i in range(1, n - 1):
        f.append((0, i + 1, i))
        f.append((n, n + i, n + i + 1))
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n + j))
        f.append((i, n + j, n + i))
    m = trimesh.Trimesh(vertices=np.array(v, float), faces=np.array(f), process=True)
    m.fix_normals()
    return m


def bend_mesh(x0, x1, centre, r, which):
    """A 90 degree bend of the sheet, axis along X, inside radius r, centre (y, z): a ring of small quads."""
    cy, cz = centre
    a = np.linspace(-math.pi / 2, 0, 9) if which == 'low' else np.linspace(math.pi / 2, math.pi, 9)
    parts_ = []
    for t0, t1 in zip(a[:-1], a[1:]):
        quad = [(cy + r * math.cos(t0), cz + r * math.sin(t0)), (cy + (r + T_SHEET) * math.cos(t0),
                                                                cz + (r + T_SHEET) * math.sin(t0)),
                (cy + (r + T_SHEET) * math.cos(t1), cz + (r + T_SHEET) * math.sin(t1)),
                (cy + r * math.cos(t1), cz + r * math.sin(t1))]
        m = prism(quad, x0, x1)
        m.vertices = m.vertices[:, [2, 0, 1]]          # (Y, Z, X) -> (X, Y, Z)
        m.fix_normals()
        parts_.append(m)
    return trimesh.util.concatenate(parts_)


# ---------------------------------------------------------------- option 2: the CNC block
def cnc_block():
    foot_z0 = SOC_TOP_Z + PAD_BOTTOM[0] * (1 - PAD_BOTTOM[1])
    flange_z1 = LID_UNDER_Z - PAD_TOP[0] * (1 - PAD_TOP[1])
    flange_t = 2.5
    foot = (-6.0, 6.0, SOC_Y - SOC_W / 2 + 0.15, SOC_Y + SOC_W / 2 - 0.15, foot_z0, foot_z0 + 2.0)
    column = (-6.0, 6.0, -20.0, SOC_Y + SOC_W / 2 - 0.15, foot_z0 + 2.0, flange_z1 - flange_t)
    # flange: the pocket less 0.4 mm all round, as a polygon
    pts = [(-5.8, -20.3), (5.8, -20.3), (7.7, -19.5), (10.6, -18.3), (10.6, 7.6), (-10.6, 7.6), (-10.6, -18.3),
           (-7.7, -19.5)]
    flange = Polygon(pts)
    meshes = [box_mesh(*foot), box_mesh(*column)]
    fm = prism(pts, flange_z1 - flange_t, flange_z1)
    meshes.append(fm)
    m = trimesh.util.concatenate(meshes)
    return m, dict(foot=foot, column=column, flange=pts, flange_z=(flange_z1 - flange_t, flange_z1)), flange


# ---------------------------------------------------------------- option 1: an off-the-shelf heatsink
def heatsink(h=6.0, size=14.0, cy=-18.4):
    z0 = SOC_TOP_Z + TAPE['t']
    return box_mesh(-size / 2, size / 2, cy - size / 2, cy + size / 2, z0, z0 + h), dict(h=h, size=size, cy=cy, z0=z0)


# ---------------------------------------------------------------- clearance checks
def checks(parts):
    out = []
    # against the measured pocket / ceiling
    for name, (m, kind) in parts.items():
        v = m.vertices
        top = v[:, 2].max()
        out.append((name, 'top of part', top, LID_UNDER_Z))
        # anything above Z 32 must lie inside the pocket (less 0.3 mm)
        hi = v[v[:, 2] > 32.0]
        if len(hi):
            worst = max(abs(x) - pocket_halfwidth(y) for x, y, z in hi)
            out.append((name, 'inside the lid pocket (mm into the wall, < 0 = clear)', worst, -0.3))
        # the camera module
        mod = box(*MODULE)
        low = v[v[:, 2] < MODULE_TOP_Z + 0.5]
        hit = any(mod.buffer(0.3).contains(Polygon([(x - 0.01, y - 0.01), (x + 0.01, y - 0.01),
                                                    (x + 0.01, y + 0.01)]).centroid) for x, y, z in low)
        out.append((name, 'clear of the camera module (over its height)', 0.0 if not hit else 1.0, 0.5))
        led = Polygon([(LED1[0] - 0.8, LED1[1] - 0.4), (LED1[0] + 0.8, LED1[1] - 0.4), (LED1[0] + 0.8, LED1[1] + 0.4),
                       (LED1[0] - 0.8, LED1[1] + 0.4)])
        foot = unary_union([Polygon([(x - 0.1, y - 0.1), (x + 0.1, y - 0.1), (x + 0.1, y + 0.1)])
                            for x, y, z in v[v[:, 2] < 30]]).convex_hull
        out.append((name, 'footprint clear of LED1 (mm)', foot.distance(led), 0.5))
    hd = os.environ.get('HOUSING_DIR')
    if hd:
        ms = [trimesh.load(os.path.join(hd, 'asm_%s.stl' % n)) for n in ('bottom', 'top', 'lid')]
        A = trimesh.util.concatenate(ms)
        for name, (m, kind) in parts.items():
            pts = m.sample(4000)
            d = trimesh.proximity.signed_distance(A, pts)       # > 0 inside the case's plastic
            out.append((name, 'against the real case STLs: deepest point inside plastic (mm)', float(d.max()), 0.0))
    return out


# ---------------------------------------------------------------- thermal paths
def lid_path(contact_area_mm2, flange_poly, slot_area_mm2, h_out=14.0):
    """Flange -> top pad -> lid plastic -> the lid's outside, plus the slots straight to the chamber."""
    a = contact_area_mm2 * 1e-6
    r_pad = PAD_TOP[0] * (1 - PAD_TOP[1]) * 1e-3 / (PAD['k'] * a) + INTERFACE_R
    r_lid = (LID_TOP_Z - LID_UNDER_Z) * 1e-3 / (0.20 * a)
    spread = math.sqrt(0.20 * (LID_TOP_Z - LID_UNDER_Z) * 1e-3 / (2 * h_out)) * 1e3     # mm a plastic fin reaches
    a_out = (flange_poly.buffer(spread).area - slot_area_mm2) * 1e-6
    r_out = 1 / (h_out * a_out)
    # slots: the pad face at the bottom of a 2 x 20 x 3.35 mm slot; still-air conduction up the slot plus
    # radiation through it (view factor of a long channel w/d)
    depth = LID_TOP_Z - LID_UNDER_Z
    f = math.sqrt(1 + (depth / SLOT_W) ** 2) - depth / SLOT_W
    h_slot = K_AIR / (depth * 1e-3) + 4 * 5.67e-8 * 0.9 * 350 ** 3 * f
    g_slot = h_slot * slot_area_mm2 * 1e-6
    g = 1 / (r_pad + r_lid + r_out) + g_slot
    return dict(r_pad_top=r_pad, r_lid=r_lid, r_lid_out=r_out, lid_out_area_cm2=a_out * 1e4, g_slots=g_slot,
                h_slot=h_slot, g_amb=g, a_out_used=a_out)


def flange_slot_area(poly):
    s = unary_union([box(SLOT_X[0], y - SLOT_W / 2, SLOT_X[1], y + SLOT_W / 2) for y in SLOT_YC])
    return poly.intersection(s).area


def thermal(sheet, cnc, hs):
    out = {}
    h_int = 5.0                       # part faces to the air inside (radiation to surfaces at ~ the air temperature,
    #                                   weak natural convection): W/m^2K (estimate)
    # --- option 1: heatsink
    m1, d1 = hs
    overlap = SOC_W * (min(d1['cy'] + 7, SOC_Y + SOC_W / 2) - max(d1['cy'] - 7, SOC_Y - SOC_W / 2))
    r_tape = TAPE['t'] * 1e-3 / (TAPE['k'] * overlap * 1e-6) + INTERFACE_R
    env = d1['size'] ** 2 + 4 * d1['size'] * d1['h']
    fins = 5 * 2 * d1['size'] * (d1['h'] - 1.5)               # five fins, both faces (typical 14 x 14 x 6 pattern)
    g_air = (11.0 * env + 3.0 * max(fins - 4 * d1['size'] * d1['h'], 0)) * 1e-6
    out['heatsink'] = dict(r_top=THETA_JC_SOC + r_tape + 0.5, g_air=g_air, g_amb=0.0, a_out_used=0.0,
                           note='14 x 14 x %.0f mm black aluminium heatsink on 3M 8810 tape, centred at board (0, %.1f)'
                                % (d1['h'], -d1['cy']), r_tape=r_tape)
    # --- option 2: CNC block
    m2, d2, fl2 = cnc
    slot2 = flange_slot_area(fl2)
    lp = lid_path(fl2.area - slot2, fl2, slot2)
    fx0, fx1, fy0, fy1, fz0, fz1 = d2['foot']
    cx0, cx1, cy0, cy1, cz0, cz1 = d2['column']
    r_pad_b = PAD_BOTTOM[0] * (1 - PAD_BOTTOM[1]) * 1e-3 / (PAD['k'] * (fx1 - fx0) * (fy1 - fy0) * 1e-6) + INTERFACE_R
    r_col = (cz1 - cz0) * 1e-3 / (K_AL6061 * (cx1 - cx0) * (cy1 - cy0) * 1e-6)
    r_spread = 1.5                     # foot and flange spreading (estimate for 2-2.5 mm aluminium)
    a_int = (fl2.area + 2 * ((cx1 - cx0) + (cy1 - cy0)) * (cz1 - cz0)) * 1e-6
    out['cnc'] = dict(lp, r_top=THETA_JC_SOC + r_pad_b + r_col + r_spread, g_air=h_int * a_int, r_pad_bottom=r_pad_b,
                      r_metal=r_col + r_spread, note='CNC 6061 block, flange in the lid pocket on a 0.5 mm pad')
    # --- option 3: sheet
    m3, d3, flat = sheet
    fl3 = box(-10.6, d3['flange'][2], 10.6, 7.6)
    slot3 = flange_slot_area(fl3)
    lp3 = lid_path(fl3.area - slot3, fl3, slot3)
    x0, x1, y0, y1, z0, z1 = d3['foot']
    r_pad_b3 = PAD_BOTTOM[0] * (1 - PAD_BOTTOM[1]) * 1e-3 / (PAD['k'] * (x1 - x0) * (y1 - y0) * 1e-6) + INTERFACE_R
    web_len = d3['web'][5] - d3['web'][4]
    r_web = web_len * 1e-3 / (K_AL5052 * 12e-3 * T_SHEET * 1e-3)
    r_sp3 = 3.0                        # 1.5 mm foot and flange spread worse than the block's
    a_int3 = (fl3.area + 2 * 12 * web_len) * 1e-6
    out['sheet'] = dict(lp3, r_top=THETA_JC_SOC + r_pad_b3 + r_web + r_sp3, g_air=h_int * a_int3, r_pad_bottom=r_pad_b3,
                        r_metal=r_web + r_sp3, note='1.5 mm 5052 sheet, bent twice, flange in the lid pocket on a 0.5 mm pad')
    return out


def drawing(sheet, cnc, hs, flat, paths):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon as MPoly
    fig, axs = plt.subplots(1, 3, figsize=(16, 6.2), dpi=110)
    m3, d3, _ = sheet
    m2, d2, fl2 = cnc
    # --- plan (seen from behind, lens frame X right, Y up)
    ax = axs[0]
    py = np.linspace(-21, 8, 60)
    ax.plot([pocket_halfwidth(y) for y in py], py, 'k-', lw=0.8)
    ax.plot([-pocket_halfwidth(y) for y in py], py, 'k-', lw=0.8, label='lid pocket (ceiling Z 38.5)')
    for yc in SLOT_YC:
        ax.add_patch(Rectangle((SLOT_X[0], yc - 1), 20, 2, fc='#cfe8ff', ec='b', lw=0.6))
    ax.add_patch(Rectangle((SOC_X - SOC_W / 2, SOC_Y - SOC_W / 2), SOC_W, SOC_W, fc='none', ec='r', lw=1.2))
    ax.text(0, SOC_Y - 7.5, 'RV1106 12.3 sq. at (0, -19.4)\n(board (0, 19.4))', color='r', ha='center', fontsize=7)
    ax.add_patch(Rectangle((MODULE[0], MODULE[1]), MODULE[2] - MODULE[0], MODULE[3] - MODULE[1], fc='none', ec='g',
                           ls='--'))
    ax.text(0, 12, 'camera module (Z 21.9-~26)', color='g', ha='center', fontsize=7)
    x0, x1, y0, y1, *_ = d3['flange']
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc='none', ec='m', lw=1.4))
    x0, x1, y0, y1, *_ = d3['foot']
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc='none', ec='m', lw=1.4, ls=':'))
    ax.add_patch(MPoly(d2['flange'], closed=True, fc='none', ec='orange', lw=1.0, ls='-.'))
    ax.plot(*LED1, 'g*')
    ax.text(LED1[0] + 0.5, LED1[1] + 0.5, 'LED1', fontsize=6)
    ax.set_title('plan from behind (lens frame). magenta: sheet (flange solid, foot dotted);\n'
                 'orange: CNC flange; blue: lid slots 20 x 2', fontsize=8)
    ax.set_xlim(-16, 16); ax.set_ylim(-28, 17); ax.set_aspect('equal'); ax.grid(lw=0.3)
    ax.annotate('', (-10.6, 9.5), (10.6, 9.5), arrowprops=dict(arrowstyle='<->', lw=0.6))
    ax.text(0, 10, '21.2', ha='center', fontsize=7)
    # --- section at X = 0
    ax = axs[1]
    ax.add_patch(Rectangle((-32, G.SEAT_Z), 56, 1.6, fc='#9c9', ec='k', lw=0.5))
    ax.add_patch(Rectangle((SOC_Y - SOC_W / 2, BOARD_BACK_Z), SOC_W, SOC_H, fc='k'))
    ax.add_patch(Rectangle((-8.4, BOARD_BACK_Z + 1.0), 24, 1.2, fc='#7a7', ec='k', lw=0.5))
    ax.text(3, 23.6, 'camera module', fontsize=7)
    ceil = [(y, LID_UNDER_Z if pocket_halfwidth(y) > 0 else None) for y in np.linspace(-28, 12, 81)]
    ax.add_patch(Rectangle((-21, LID_UNDER_Z), 29, LID_TOP_Z - LID_UNDER_Z, fc='#ddd', ec='k', lw=0.5))
    for yc in SLOT_YC:
        ax.add_patch(Rectangle((yc - 1, LID_UNDER_Z), 2, LID_TOP_Z - LID_UNDER_Z, fc='#cfe8ff', ec='b', lw=0.4))
    ys_ = [-27, -26, -25, -24, -23, -22, -21]
    zs_ = [27.6, 29.1, 30.6, 32.1, 33.6, 35.0, 38.5]
    ax.plot(ys_, zs_, 'k-', lw=1.2, label='case shell (X = 0)')
    for part, c in ((m3, 'm'), (m2, 'orange')):
        try:
            sec = part.section(plane_origin=[0.01, 0, 0], plane_normal=[1, 0, 0])
            for seg in (sec.discrete if sec is not None else []):
                ax.plot(seg[:, 1], seg[:, 2], '-', color=c, lw=1.0)
        except Exception:                   # trimesh's section needs networkx; fall back to the outline points
            v = part.vertices
            ax.plot(v[:, 1], v[:, 2], '.', ms=1.5, color=c)
    ax.text(-20, 30, 'pad 1.5 -> 1.05\n(TG-A6200)', fontsize=7)
    ax.text(-9, 37.2, 'pad 0.5 -> 0.4', fontsize=7)
    ax.set_title('section X = 0 (Z up = towards the lid); magenta sheet, orange CNC', fontsize=8)
    ax.set_xlim(-28, 12); ax.set_ylim(18, 43); ax.set_aspect('equal'); ax.grid(lw=0.3)
    ax.set_xlabel('Y (mm)'); ax.set_ylabel('Z (mm)')
    # --- flat pattern of the sheet
    ax = axs[2]
    y = 0
    segs = [('foot', flat['foot'], 12.0), ('bend', flat['bend'], 12.0), ('web', flat['web'], 12.0),
            ('bend', flat['bend'], 12.0), ('flange', flat['flange'], 21.2)]
    for name, L, wdt in segs:
        ax.add_patch(Rectangle((-wdt / 2, y), wdt, L, fc='#eee' if name != 'bend' else '#fdd', ec='k', lw=0.6))
        ax.text(wdt / 2 + 0.6, y + L / 2, '%s %.2f' % (name, L), fontsize=7, va='center')
        y += L
    ax.text(0, -2.5, 'blank %.2f x 21.2 (12.0 wide below the flange), 1.5 mm 5052-H32,\n'
            'bends 90 deg up / 90 deg down, inside R %.1f, K 0.4; relief 1 x 1.5 at the flange corners'
            % (flat['total'], BEND_R), ha='center', fontsize=7)
    ax.set_xlim(-14, 22); ax.set_ylim(-5, y + 2); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('option 3 flat pattern', fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'drawing.png'))
    plt.close(fig)


def main():
    sheet = sheet_bracket()
    cnc = cnc_block()
    hs = heatsink()
    sheet[0].export(os.path.join(HERE, 'sheet_bracket.stl'))
    cnc[0].export(os.path.join(HERE, 'cnc_block.stl'))
    hs[0].export(os.path.join(HERE, 'heatsink_14x14x6.stl'))
    res = checks({'sheet': (sheet[0], 'sheet'), 'cnc': (cnc[0], 'cnc'), 'heatsink': (hs[0], 'heatsink')})
    paths = thermal(sheet, cnc, hs)
    m3, d3, flat = sheet
    drawing(sheet, cnc, hs, flat, paths)
    info = dict(paths=paths, sheet=dict(d3, flat=flat, mass_g=m3.volume * 2.68e-3),
                cnc=dict(foot=cnc[1]['foot'], column=cnc[1]['column'], flange=cnc[1]['flange'],
                         flange_z=cnc[1]['flange_z'], mass_g=cnc[0].volume * 2.70e-3),
                heatsink=hs[1], checks=res,
                stack=dict(soc_top_z=SOC_TOP_Z, lid_under_z=LID_UNDER_Z, gap=LID_UNDER_Z - SOC_TOP_Z))
    json.dump(info, open(os.path.join(HERE, 'heat_paths.json'), 'w'), indent=1, default=float)
    for r in res:
        print('%-9s %-62s %8.2f (limit %.2f)' % r)
    for k, v in paths.items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})
    print('sheet flat', {k: round(v, 2) for k, v in flat.items()}, 'mass %.1f g' % info['sheet']['mass_g'],
          'cnc mass %.1f g' % info['cnc']['mass_g'])


if __name__ == '__main__':
    main()
