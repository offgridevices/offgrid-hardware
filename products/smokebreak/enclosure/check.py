"""Fit checks for the exported enclosure (trimesh + manifold3d).

    python check.py        # after enclosure.py (CadQuery + trimesh); writes out/fit_check.txt

Everything is checked in the case frame (the STLs are mirrored back on load).
"""
import math
import os
import sys

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import enclosure as E  # noqa: E402
from enclosure import G  # noqa: E402

OUT = E.OUT
MIRROR = np.array([[1, 0, 0, 0], [0, -1, 0, G.CASE_D], [0, 0, 1, 0], [0, 0, 0, 1]], float)
LINES = []
TOL = 0.01


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    LINES.append(s)


def load(path):
    m = trimesh.load(path, force='mesh')
    m.apply_transform(MIRROR)                         # file frame -> case frame (trimesh fixes the winding)
    return m


def boxm(x0, y0, z0, x1, y1, z1):
    return trimesh.creation.box(bounds=[[x0, y0, z0], [x1, y1, z1]])


def ivol(a, b):
    try:
        r = trimesh.boolean.intersection([a, b], engine='manifold')
        return 0.0 if r.is_empty else float(r.volume)
    except Exception as e:                            # noqa: BLE001
        return float('nan')


def surface_gap(moving, fixed, n=60000):
    """Smallest distance from points on `moving` to `fixed`; negative = inside `fixed`."""
    pts, _ = trimesh.sample.sample_surface_even(moving, n, seed=1) if moving.area > 0 else (moving.vertices, None)
    pts = np.vstack([pts, moving.vertices])
    sd = trimesh.proximity.signed_distance(fixed, pts)    # + inside
    return float(-sd.max())


def magnet_field(rot, centre, R, L, br, p, nz=40, nphi=180):
    """B (tesla) at p from a uniformly axially magnetised cylinder (axis +z before `rot`): the side surface
    current K = Br/mu0, summed as nz loops by Biot-Savart (mu0 cancels)."""
    phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
    dphi = 2 * np.pi / nphi
    B = np.zeros(3)
    R3 = rot[:3, :3]
    c = (rot @ np.r_[centre, 1])[:3]
    for z in (np.arange(nz) + 0.5) / nz * L - L / 2:
        pts = np.c_[R * np.cos(phi), R * np.sin(phi), np.full(nphi, z)]
        dl = np.c_[-R * np.sin(phi), R * np.cos(phi), np.zeros(nphi)] * dphi
        pts = pts @ R3.T + c
        dl = dl @ R3.T
        r = p - pts
        B += (br / (4 * np.pi)) * (L / nz) * np.sum(np.cross(dl, r) / np.linalg.norm(r, axis=1)[:, None] ** 3, axis=0)
    return B


def main():
    P = E.board_parts(refresh=False)
    parts = {n: load(os.path.join(OUT, f'{n}.stl')) for n in E.PART_NAMES}
    ctx = os.path.join(OUT, 'context')

    say('== STL integrity (case frame; volumes in mm^3)')
    for n, m in parts.items():
        say(f'  {n:11s} watertight={m.is_watertight} winding_ok={m.is_winding_consistent} volume={m.volume:9.1f} '
            f'bodies={len(m.split(only_watertight=False))}')

    top, floor, guard, rocker = parts['top'], parts['bottom'], parts['guard'], parts['rocker']

    # ------------------------------------------------------------ component boxes
    say('\n== Component boxes (courtyard x height table; XH sockets: body outline) vs top shell and floor')
    passthrough = {'J1': 'XT60 mouth through the battery-end wall', 'J2': 'XT30 mouth through the battery-end wall',
                   'J8': 'USB-C in the back-wall opening'}
    hits, expected = [], []
    for ref, p in sorted(P.items()):
        h = E.part_height(p['fp'])
        if h <= 0 or not p['courtyard'] or p['side'] != 'T':
            continue
        c = p['fab'] if 'JST_XH' in p['fp'] else p['courtyard']
        b = boxm(c[0], c[1], G.PCB_TOP_Z, c[2], c[3], G.PCB_TOP_Z + h)
        for name, m in (('top', top), ('bottom', floor), ('rocker', rocker), ('guard', guard)):
            v = ivol(b, m)
            if v > TOL or v != v:
                (expected if ref in passthrough else hits).append((ref, name, v, h))
    for ref, name, v, h in hits:
        say(f'  INTERFERENCE {ref:7s} x {name:7s} {v:8.3f} mm^3 (h {h})')
    if not hits:
        say('  no interference > 0.01 mm^3 (all parts, all four bodies)')
    for ref, name, v, h in expected:
        say(f'  expected pass-through {ref} x {name}: box overlap {v:.1f} mm^3 ({passthrough[ref]}; real body checked below)')

    # through-hole leads under the board vs the floor (1.3 mm protrusion)
    lead_hits = []
    for ref, p in P.items():
        for (_, x, y, dx, dy, pw) in p['tht']:
            if ref.startswith('H'):
                continue
            r = max(dx, dy) / 2 + 0.2
            lead = trimesh.creation.cylinder(radius=r, segment=[[x, y, E.Z_PCB_BOT - 1.3], [x, y, E.Z_PCB_BOT]])
            v = ivol(lead, floor)
            if v > TOL:
                lead_hits.append((ref, v))
    say(f'  THT leads (1.3 mm below the PCB) vs floor: {"none" if not lead_hits else lead_hits}')

    # ------------------------------------------------------------ pass-through parts: real bodies
    say('\n== Pass-through parts: real 3D bodies (lib/*.wrl) vs top shell; gap = smallest distance, <0 = overlap')
    for f, what in (('xt_J1.stl', 'XT60 (J1)'), ('xt_J2.stl', 'XT30 (J2)'), ('usb_J8.stl', 'USB-C (J8)')):
        m = load(os.path.join(ctx, f))
        g = surface_gap(m, top, 40000)
        say(f'  {what:11s} min gap to the shell {g:+.3f} mm')
    tog = load(os.path.join(ctx, 'toggle.stl'))
    say(f'  SW1 bushing + lever vs shell: overlap {ivol(tog, top):.4f} mm^3, min gap {surface_gap(tog, top):+.3f} mm '
        f'(Ø{G.TOG_BUSHING_D} bushing in a Ø{E.BUSH_HOLE_D} hole: {(E.BUSH_HOLE_D - G.TOG_BUSHING_D) / 2:.3f} radial)')
    sw1box = boxm(*[P['SW1']['courtyard'][i] for i in (0, 1)], G.PCB_TOP_Z, *[P['SW1']['courtyard'][i] for i in (2, 3)],
                  G.PCB_TOP_Z + G.TOG_SHOULDER)
    say(f'  SW1 body to its shoulder vs shell: gap {surface_gap(sw1box, top):+.3f} mm (the 0.2 mm shoulder pad)')

    # ------------------------------------------------------------ display
    say('\n== Display module (MODULE x MODULE_T) in its pocket')
    disp = load(os.path.join(ctx, 'display.stl'))
    say(f'  overlap {ivol(disp, top):.4f} mm^3')
    mx, my, mw, mh = G.MODULE
    z0, z1 = G.MODULE_Z, G.MODULE_Z + G.MODULE_T
    probes = {'left (-x)': (0, -1), 'right (+x, beside the FPC slot)': (0, 1), 'back (-y)': (1, -1), 'front (+y)': (1, 1)}
    for nm, (axis, sgn) in probes.items():
        n = 400
        t = np.linspace(0.02, 0.98, n)
        zz = np.linspace(z0 + 0.02, z1 - 0.4, 6)
        pts = []
        for z in zz:
            for u in t:
                if axis == 0:
                    pts.append((mx if sgn < 0 else mx + mw, my + u * mh, z))
                else:
                    pts.append((mx + u * mw, my if sgn < 0 else my + mh, z))
        pts = np.array(pts)
        if nm.startswith('right'):
            fy = my + mh / 2
            pts = pts[np.abs(pts[:, 1] - fy) > E.FPC_SLOT_W / 2 + 0.1]
        d = trimesh.proximity.closest_point(top, pts)[1]
        say(f'  {nm:34s} clearance {d.min():.3f} mm')
    say(f'  top: the module face bears on the window lip at z {G.PANEL_UNDER_Z} (contact by design)')
    say(f'  under-screen rule (parts under the module <= {G.UNDER_SCREEN_MAX:.2f} mm):')
    worst = []
    for ref, p in P.items():
        c = p['courtyard']
        if not c or p['side'] != 'T':
            continue
        if c[2] > mx and c[0] < mx + mw and c[3] > my and c[1] < my + mh:
            worst.append((E.part_height(p['fp']), ref))
    worst.sort(reverse=True)
    bad = [w for w in worst if w[0] > G.UNDER_SCREEN_MAX]
    say(f'    tallest: {worst[:4]}  violations: {bad or "none"}')

    # ------------------------------------------------------------ guard
    say('\n== Guard')
    z_tip = G.PCB_TOP_Z + E.LEVER_TIP_ABOVE_PCB
    say(f'  height above the face {E.GUARD_H_FIT:.1f} mm (geometry.py GUARD_H {G.GUARD_H}); lever tip z {z_tip:.2f}, '
        f'roof underside z {G.CASE_H + E.GUARD_H_FIT - E.GUARD_ROOF:.2f}')
    say(f'  closed: overlap with shell {ivol(guard, top):.4f} mm^3, with rocker {ivol(guard, rocker):.4f} mm^3')
    tx, ty = G.TOG
    shoulder = G.PCB_TOP_Z + G.TOG_SHOULDER
    bush_top = G.PCB_TOP_Z + 14.99
    for tilt in (0, 20, -20):
        lever = trimesh.creation.cylinder(radius=1.6, segment=[[tx, ty, bush_top], [tx, ty, z_tip]])
        lever.apply_transform(rotation_matrix(math.radians(tilt), [1, 0, 0], [tx, ty, shoulder]))
        say(f'  lever tilted {tilt:+d} deg (pivot at the shoulder): overlap {ivol(lever, guard):.4f} mm^3, '
            f'gap {surface_gap(lever, guard, 8000):+.2f} mm')
    free = 0
    for deg in range(0, 181, 5):
        g = guard.copy()
        g.apply_transform(rotation_matrix(math.radians(deg), [1, 0, 0], [0, E.HINGE_Y, E.HINGE_Z]))
        v = ivol(g, top)
        if v > TOL:
            say(f'  opening sweep: first contact with the shell at {deg} deg ({v:.2f} mm^3)')
            break
        free = deg
    else:
        say('  opening sweep: no contact with the shell 0..180 deg')
    say(f'  free to {free} deg')
    lever = trimesh.creation.cylinder(radius=1.6, segment=[[tx, ty, bush_top], [tx, ty, z_tip]])
    worst = 0.0
    for deg in range(0, free + 1, 5):
        g = guard.copy()
        g.apply_transform(rotation_matrix(math.radians(deg), [1, 0, 0], [0, E.HINGE_Y, E.HINGE_Z]))
        worst = max(worst, ivol(g, lever))
    say(f'  opening sweep 0..{free} deg vs the upright lever: worst overlap {worst:.4f} mm^3')
    # hinge pin: hidden, loaded from inside
    ax0, ax1 = E.GUARD_PIN_X0, E.GUARD_PIN_X0 + E.GUARD_PIN_L
    pin = trimesh.creation.cylinder(radius=E.PIN_D / 2, segment=[[ax0, E.HINGE_Y, E.HINGE_Z], [ax1, E.HINGE_Y, E.HINGE_Z]])
    path = trimesh.creation.cylinder(radius=E.PIN_D / 2, segment=[[E.PIN_GROOVE_X0 + 0.5, E.HINGE_Y, E.HINGE_Z], [ax0, E.HINGE_Y, E.HINGE_Z]])
    outside = [top.contains([[x, E.HINGE_Y, E.HINGE_Z]])[0] for x in np.linspace(ax1 + 0.5, 96.5, 12)]
    say(f'  hinge pin Ø{E.PIN_D} x {E.GUARD_PIN_L:g} at x {ax0:.1f}..{ax1:.1f}: press interference in the right lug '
        f'{ivol(pin, top):.3f} mm^3 (Ø{E.PIN_PRESS_D} bore), loading path x {E.PIN_GROOVE_X0 + 0.5:.1f}..{ax0:.1f} '
        f'overlap {ivol(path, top):.4f} mm^3, solid shell between the blind end and the outside: {all(outside)}')
    # magnet field at U6 (Biot-Savart on the magnet's equivalent surface current), Bz = across the package
    mag_y, mz0, mz1 = E.magnet_pose()
    u6 = P['U6']
    sens = np.array([u6['cx'], u6['cy'], G.PCB_TOP_Z + 0.65])        # SOT-23 Hall element 0.65 mm over the seat
    say(f'  magnet Ø{E.MAGNET_D:g} x {E.MAGNET_T:g} N52 centre (x {tx:.1f}, y {mag_y:.2f}), z {mz0:.1f}..{mz1:.1f}; '
        f'U6 element at (y {sens[1]:.2f}, z {sens[2]:.2f}): {abs(mag_y - sens[1]):.2f} mm off-axis, '
        f'{mz0 - sens[2]:.2f} mm below the magnet')
    rel = None
    for d10 in range(0, 900, 5):
        rot = rotation_matrix(math.radians(d10 / 10), [1, 0, 0], [0, E.HINGE_Y, E.HINGE_Z])
        if abs(magnet_field(rot, np.array([tx, mag_y, (mz0 + mz1) / 2]), E.MAGNET_D / 2, E.MAGNET_T, 1.42, sens)[2]) < 0.5e-3:
            rel = d10 / 10
            break
    say(f'    |Bz| falls below BRP min (0.5 mT) at {rel} deg open')
    for deg in (0, 10, 20, 30):
        rot = rotation_matrix(math.radians(deg), [1, 0, 0], [0, E.HINGE_Y, E.HINGE_Z])
        for br, tag in ((1.42, 'Br 1.42 T'),):
            b = magnet_field(rot, np.array([tx, mag_y, (mz0 + mz1) / 2]), E.MAGNET_D / 2, E.MAGNET_T, br, sens)
        say(f'    guard open {deg:2d} deg: |Bz| at U6 = {abs(b[2]) * 1e3:6.2f} mT, |B| = {np.linalg.norm(b) * 1e3:6.2f} mT ({tag})')
    say('    DRV5032FA (SLVSDC7H): BOP +-1.5/3/4.8 mT, BRP +-0.5/1.5/3 mT (min/typ/max); target closed >= 9.6 mT, '
        'open must fall below BRP min 0.5 mT')

    # ------------------------------------------------------------ rocker
    say('\n== Rocker')
    say(f'  at rest: overlap with shell {ivol(rocker, top):.4f} mm^3')
    sw_top = G.PCB_TOP_Z + E.B3U_H
    say(f'  nub to B3U actuator at rest {E.NUB_GAP:.2f} mm; B3U travel 0.15 mm')
    for side, ref in ((-1, 'SW2'), (1, 'SW3')):
        p = P[ref]
        dx = abs(p['cx'] - G.TOG[0])
        need = math.degrees(math.atan((E.NUB_GAP + 0.15) / dx))
        r = rocker.copy()
        r.apply_transform(rotation_matrix(math.radians(side * need * 1.3), [0, 1, 0], [G.TOG[0], 0, E.ROCK_PIN_Z]))
        sw = boxm(p['courtyard'][0], p['courtyard'][1], G.PCB_TOP_Z, p['courtyard'][2], p['courtyard'][3], sw_top)
        say(f'  {ref} (dx {dx:.1f}): {need:.2f} deg tilt presses it; at 1.3x that tilt: overlap with shell '
            f'{ivol(r, top):.4f} mm^3, nub reaches {ivol(r, sw):.3f} mm^3 into the switch box (actuation)')

    # ------------------------------------------------------------ drone leads
    say('\n== Drone leads (12 AWG Ø{} / 16 AWG Ø{})'.format(E.WIRE_D['J3'], E.WIRE_D['J4']))
    wires = load(os.path.join(ctx, 'wires.stl'))
    inside = boxm(-1, -1, -1, G.CASE_W - G.WALL - 0.2, G.CASE_D + 1, 20)
    vt = vf = 0.0
    for piece in wires.split(only_watertight=True):
        w_in = trimesh.boolean.intersection([piece, inside], engine='manifold')
        if not w_in.is_empty:
            vt += ivol(w_in, top)
            vf += ivol(w_in, floor)
    say(f'  inside the case: overlap with shell {vt:.4f}, with floor {vf:.4f} mm^3')
    say(f'  in the end wall: crown clearance +{E.WIRE_CROWN_CLR} mm radial, floor-tab saddles squeeze '
        f'{E.WIRE_SQUEEZE} mm on the diameter')

    # ------------------------------------------------------------ floor / screws
    say('\n== Fastening')
    say(f'  boss Ø{2 * E.BOSS_R} PCB top z {G.PCB_TOP_Z} to panel z {G.PANEL_UNDER_Z} ({G.PANEL_UNDER_Z - G.PCB_TOP_Z:.1f} mm), '
        f'insert hole Ø{E.INSERT_D} x {E.INSERT_DEPTH}')
    say(f'  screw: ISO 7380 M3 x 8 from below; head seat z {E.CBORE_DEPTH}, tip z {E.CBORE_DEPTH + 8:.1f} '
        f'(insert spans z {G.PCB_TOP_Z}..{G.PCB_TOP_Z + 5.7:.1f})')

    # ------------------------------------------------------------ text
    say('\n== Text inlays')
    import shapely.ops as so
    for txt, x in E.text_labels():
        pgs = so.unary_union(E.glyph_polygons(txt, E.TEXT_CAP))
        parts_n = len(getattr(pgs, 'geoms', [pgs]))
        lo, hi = 0.0, 1.0                              # thinnest stroke: smallest erosion that splits or drops a glyph
        for _ in range(20):
            mid = (lo + hi) / 2
            er = pgs.buffer(-mid, join_style=1)
            n = 0 if er.is_empty else len(getattr(er, 'geoms', [er]))
            lo, hi = (mid, hi) if n == parts_n else (lo, mid)
        say(f'  {txt:5s} at x {x:5.1f}: cap {E.TEXT_CAP} mm, thinnest stroke {2 * lo:.2f} mm, depth {E.TEXT_DEPTH} mm')
    say(f'  top shell vs text inlay overlap {ivol(top, parts["text_inlay"]):.4f} mm^3; vs ring inlay '
        f'{ivol(top, parts["ring_inlay"]):.4f} mm^3')

    with open(os.path.join(OUT, 'fit_check.txt'), 'w') as f:
        f.write('\n'.join(LINES) + '\n')


if __name__ == '__main__':
    main()
