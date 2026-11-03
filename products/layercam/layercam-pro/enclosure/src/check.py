# -*- coding: utf-8 -*-
"""Checks of the printed case against the board (numbers, not pictures).

    python3 enclosure/src/check.py <folder with Prusa's files>

checks the committed enclosure/print/*.stl (case.py runs the same checks on
the parts it has just built).  Exits 1 if a check fails.

  1. the board (geometry.OUTLINE with its USB-C tab, 1.6 mm) fits: every
     part keeps CLEAR (0.5 mm) from it except the four screw pads, which
     touch it only inside BOSS_D; the tab's end (no copper within 0.3 mm
     of it) may come closer;
  2. every light-rod channel runs from its LED to its front hole: the 2.0 mm
     rod along it touches nothing, the channel is walled from the front
     plate to the tube's top, it opens at the hole, and its top end is 0.3 mm
     short of the LED;
  3. the heatsink clears the lid by >= 0.5 mm (and the back shell), with the
     lid 1.6 mm thick over it and vent slots over it;
  4. the USB-C receptacle's mouth: level plug axis at Z 24.2, the mouth 0 to
     0.5 mm inside the outside (the plug seat's floor), the opening clear;
  5. walls: the outer skin of every part is >= 1.6 mm thick (rays inwards
     from Prusa's outer surface), except at openings' edges;
  6. magnet pockets: flush depth and the floor behind them;
  7. the RP-SMA bulkhead: wall at the hole, and its room inside.
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case as C  # noqa: E402
import geometry as G  # noqa: E402

MIN_WALL = 1.6


def _box(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return m3.Manifold.cube(tuple(hi - lo)).translate(tuple(lo))


def gap(a, b, search=3.0):
    """Smallest distance between two manifolds (search as far as `search`)."""
    if a.is_empty() or b.is_empty():
        return float('inf')
    if not (a ^ b).is_empty() and (a ^ b).volume() > 1e-6:
        return -((a ^ b).volume())       # overlap: report minus its volume
    return a.min_gap(b, search)


def run(parts, info, folder=None, log=print):
    ok = True
    res = {}

    def report(name, good, text):
        nonlocal ok
        ok &= bool(good)
        log('%s %s: %s' % ('PASS' if good else 'FAIL', name, text))
        res[name] = text

    # ------------------------------------------------------------ 0 Prusa's front features (STEP)
    faces = C.read_step_faces(folder) if folder else {}
    if faces:
        cyl = faces['bottom']['cyls']
        def near(d, xy):
            c = [p for dd, ax, p in cyl if abs(dd - d) < 0.03 and abs(ax[2]) > 0.99]
            return min(np.hypot(p[0] - xy[0], p[1] - xy[1]) for p in c) if c else float('inf')
        led = max(near(G.LED_HOLE_D, C.hole_xy(a)) for a in G.LED_ANGLES)
        off = max(math.hypot(C.hole_xy(a)[0] - G.hole_xy(a)[0], C.hole_xy(a)[1] - G.hole_xy(a)[1]) for a in G.LED_ANGLES)
        win = near(G.LIGHT_WINDOW_D, G.LIGHT_WINDOW)
        bore = near(G.BORE_D, (0, 0))
        report("Prusa's front holes", max(led, win, bore) < 0.05,
               'the six Ø%.1f LED holes cut where Prusa\'s STEP has them (%s; up to %.2f mm off geometry.hole_xy), '
               'the Ø%.1f window %.2f mm and the Ø%.1f bore %.2f mm from geometry'
               % (G.LED_HOLE_D, ', '.join('%d: (%.2f, %.2f)' % ((a,) + tuple(C.hole_xy(a))) for a in G.LED_ANGLES),
                  off, G.LIGHT_WINDOW_D, win, G.BORE_D, bore))

    # ------------------------------------------------------------ 1 board
    board = C.prism(C.board_polygon(), G.BOARD_Z, G.BOARD_Z + G.BOARD_T)
    pads = C.union([C.zcyl(x, y, G.BOARD_Z - 3, G.BOARD_Z + G.BOARD_T + 3, G.BOSS_D + 0.05) for x, y in G.SCREWS])
    o, u, s, z = C.usb_frame()
    tab_end = C.local_prism(C.box(G.USB_TAB - 0.6, -G.USB_TAB_W / 2 - 0.01, G.USB_TAB + 0.01, G.USB_TAB_W / 2 + 0.01),
                            G.BOARD_Z - 0.01 - o[2], G.BOARD_Z + G.BOARD_T + 0.01 - o[2], o, u, s, z)
    rest = board - pads - tab_end
    gaps = {k: gap(rest, m - pads) for k, m in parts.items()}
    tab_gaps = {k: gap(tab_end, m) for k, m in parts.items()}
    pad_touch = [gap(C.zcyl(x, y, G.BOARD_Z, G.BOARD_Z + G.BOARD_T, G.BOSS_D + 0.4) - C.zcyl(x, y, 0, 50, G.BOSS_D + 0.2),
                     parts['front-shell'] + parts['back-shell']) for x, y in G.SCREWS]
    gmin = min(gaps.values())
    # the same with the outline that fits (FIT_OUTLINE), for when geometry.OUTLINE is cut down
    fitb = C.prism(C.board_polygon(outline=list(info['fit_outline'].exterior.coords)),
                   G.BOARD_Z, G.BOARD_Z + G.BOARD_T) - pads - tab_end
    fit_gap = min(gap(fitb, m - pads) for m in parts.values())
    report('board clearance', gmin >= C.CLEAR - 0.02 and min(tab_gaps.values()) >= 0.15 and min(pad_touch) > 0.0,
           'board to case %.2f mm (front %.2f, back %.2f, lid %.2f); tab end (no copper within 0.3 mm) %.2f mm; '
           'the four screw pads touch it only inside Ø%.1f (Ø%.1f round them clear by %.2f mm); '
           'with FIT_OUTLINE the board clears the case by %.2f mm'
           % (gmin, gaps['front-shell'], gaps['back-shell'], gaps['lid'], min(tab_gaps.values()), G.BOSS_D,
              G.BOSS_D + 0.4, min(pad_touch), fit_gap))
    fit = info['fit_outline']
    room = info['board_room']
    tab = C.board_polygon().difference(C.Polygon(G.OUTLINE).buffer(0.01))
    excess = C.Polygon(G.OUTLINE).difference(room)
    ring = C.Polygon(G.OUTLINE).exterior
    far = max(room.exterior.distance(ring.interpolate(t)) if not room.contains(ring.interpolate(t)) else 0.0
              for t in np.linspace(0, ring.length, 3000))
    report('board outline', excess.area < 0.05 and far < 0.02,
           'geometry.OUTLINE (%.0f mm2, plus the %.0f mm2 USB-C tab) inside the room the case leaves '
           '(wall >= %.1f, %.1f round it from Z %.1f to %.1f): %.2f mm2 outside, by up to %.2f mm%s'
           % (C.Polygon(G.OUTLINE).area, tab.area, C.MIN_WALL, C.CLEAR, G.BOARD_Z - C.CLEAR,
              G.BOARD_Z + G.BOARD_T + C.CLEAR, excess.area, far,
              '' if excess.area < 0.05 else '; an outline that fits: FIT_OUTLINE (out/fit-outline.txt)'))
    res['fit_outline'] = [(round(x, 2), round(y, 2)) for x, y in fit.exterior.coords[:-1]]
    seat = [parts['front-shell'] ^ C.zcyl(x, y, G.BOARD_Z - 0.3, G.BOARD_Z + 0.01, G.BOSS_D) for x, y in G.SCREWS]
    report('board seat', all(abs(p.bounding_box()[5] - G.BOARD_Z) < 0.02 for p in seat),
           'four Ø%.1f boss tops at Z %.2f (the board\'s front face), pilot Ø%.1f x %.1f deep for M2 self-tapping'
           % (G.BOSS_D, max(p.bounding_box()[5] for p in seat), C.PILOT_D, C.PILOT_DEPTH))

    # ------------------------------------------------------------ 2 rods
    front = parts['front-shell']
    ftm = C.to_trimesh(front)
    lines = []
    good = True
    for a in G.LED_ANGLES:
        p0, p1 = C.rod_axis(a)
        d = C.unit(p1 - p0)
        rod = C.cyl(p0 + d * 0.01, p1, G.ROD_D, 48)
        g = gap(rod, front, 1.0)
        lean = math.degrees(math.acos(d[2]))
        # walled: points 0.15 mm outside the channel are inside material from
        # the front plate to the tube's top
        ex, ey, _ = C.frame(d)
        zs = np.linspace(1.0, C.ROD_TUBE_TOP - 0.3, 25)
        pts = [p0 + d * ((zz - p0[2]) / d[2]) + (ex * math.cos(t) + ey * math.sin(t)) * (C.ROD_CH_D / 2 + 0.15)
               for zz in zs for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
        walled = ftm.contains(np.array(pts)).mean()
        # open at the front and at the LED end (a ray along the axis is not blocked)
        hits = ftm.ray.intersects_any([p1 + d * 0.5], [-d])[0] or ftm.ray.intersects_any([p0 + d * 1.0], [d])[0]
        led_gap = (G.BOARD_Z - C.LED_H) - p1[2]
        length = np.linalg.norm(p1 - p0)
        gd = g >= (C.ROD_CH_D - G.ROD_D) / 2 - 0.02 and walled > 0.99 and not hits and abs(led_gap - C.ROD_GAP) < 1e-6
        good &= gd
        lines.append('%3d deg: lean %.1f deg, rod %.1f mm long, rod to case %.3f, walled %.0f%%, LED gap %.1f'
                     % (a, lean, length, g, 100 * walled, led_gap))
    report('light rods', good, 'channels Ø%.2f from each LED (Z %.1f) to its Ø%.1f hole (Z 0):\n      '
           % (C.ROD_CH_D, G.BOARD_Z, G.LED_HOLE_D) + '\n      '.join(lines))
    wx, wy = G.LIGHT_WINDOW
    tube_open = not ftm.ray.intersects_any([[wx, wy, C.LIGHT_TUBE_TOP - 0.1]], [[0, 0, -1]])[0]
    sens = _box((wx - 2.2, wy - 1.2, G.BOARD_Z - C.SENSOR_H), (wx + 2.2, wy + 1.2, G.BOARD_Z))
    report('light sensor tube', tube_open and gap(sens, front) > 0.3,
           'Ø%.1f tube from the Ø%.1f window to Z %.2f, %.2f mm short of the TEMT6000; open end to end'
           % (C.LIGHT_TUBE_ID, G.LIGHT_WINDOW_D, C.LIGHT_TUBE_TOP, gap(sens, front)))
    x0, y0, x1, y1 = G.HOLDER_BOX
    holder = _box((x0, y0, C.HOLDER_Z0), (x1, y1, G.BOARD_Z)) + C.zcyl(0, 0, 0.0, C.HOLDER_Z0, G.BORE_D - 0.02, 96)
    hg = gap(holder, front, 2.0)
    report('IR-cut holder volume', hg >= 0.0, 'box %s from Z %.1f to %.1f and the Ø%.1f bore to the front: clear by %.2f mm'
           % (str(G.HOLDER_BOX), C.HOLDER_Z0, G.BOARD_Z, G.BORE_D, hg))

    # ------------------------------------------------------------ 3 heatsink
    x0, y0, z0, x1, y1, z1 = C.sink_box()
    sink = _box((x0, y0, z0), (x1, y1, z1))
    g_lid = gap(sink, parts['lid'], 5.0)
    g_back = gap(sink, parts['back-shell'], 5.0)
    lidtm = C.to_trimesh(parts['lid'])
    above = lidtm.ray.intersects_location([[G.SOC_XY[0], G.SOC_XY[1], z1]], [[0, 0, 1]])[0]
    thick = (np.sort(above[:, 2])[1] - np.sort(above[:, 2])[0]) if len(above) >= 2 else float('nan')
    slots = sum(1 for yv in C.VENT_YS if y0 <= yv <= y1)
    report('heatsink', g_lid >= 0.5 and g_back >= 0.3, 'top at Z %.2f; lid %.2f mm above it (lid %.2f mm thick there), '
           'back shell %.2f mm away; %d vent slots over it'
           % (z1, g_lid, thick if not math.isnan(thick) else C.LID_THIN, g_back, slots))

    # ------------------------------------------------------------ 4 USB
    ui = info['usb']
    back = parts['back-shell']
    btm = C.to_trimesh(back)
    alltm = trimesh.util.concatenate([C.to_trimesh(m) for m in parts.values()])
    o, u, s = ui['origin'], ui['u'], ui['s']
    mouth = o + u * ui['t_mouth']
    corners = [mouth + s * a + np.array([0, 0, b]) for a in (-C.USB_W / 2, 0, C.USB_W / 2) for b in (-C.USB_H / 2, C.USB_H / 2)]
    blocked = alltm.ray.intersects_any(np.array(corners) + u * 0.05, [u] * len(corners)).any()
    # the seat floor: ray from outside, along -u, beside the opening
    probe = o + u * 15 + s * (C.USB_OPEN[0] / 2 + 0.8)
    loc = btm.ray.intersects_location([probe], [-u])[0]
    t_floor = (loc - o) @ u
    t_floor = t_floor.max() if len(t_floor) else float('nan')
    inside = t_floor - ui['t_mouth']
    report('USB-C mouth', 0.0 <= inside <= 0.5 and not blocked and abs(o[2] - 24.2) < 0.1,
           'plug axis level at Z %.2f along %.1f deg; mouth %.2f mm from the board edge, %.2f mm inside the seat '
           'floor (a vertical seat %.1f x %.1f for the plug, cut into the sloping facet, whose surface is %.2f mm '
           'out along the axis); opening %.1f x %.1f obround clear'
           % (o[2], G.USB_NORMAL_DEG, ui['t_mouth'], inside, C.USB_PLUG[0], C.USB_PLUG[1], ui['t_outer'],
              C.USB_OPEN[0], C.USB_OPEN[1]))

    # ------------------------------------------------------------ 5 walls
    wall_lines, wall_ok = [], True
    prusa = trimesh.util.concatenate(list(info['prusa'].values()))
    pq = trimesh.proximity.ProximityQuery(prusa)
    cuts_near = info.get('openings')
    from scipy.spatial import cKDTree
    for k, m in parts.items():
        tm = C.to_trimesh(m)
        P, fi = trimesh.sample.sample_surface_even(tm, 30000, seed=2)
        Nn = tm.face_normals[fi]
        dist = np.concatenate([pq.on_surface(P[i:i + 3000])[1] for i in range(0, len(P), 3000)])
        # the outside: faces that look out of Prusa's (filled) case; the inside:
        # new faces that look into it (Prusa's own faces that look in, and the
        # walls of its texture grooves, are neither)
        out = info['env'].outside(P + Nn * 0.12)
        skin = out
        # the seams (the split at Z 21.0, the lid seat at Z 38.45) are neither
        seam = (np.abs(Nn[:, 2]) > 0.999) & ((np.abs(P[:, 2] - C.SPLIT_Z) < 0.01) | (np.abs(P[:, 2] - C.LID_SEAT_Z) < 0.01))
        inner = (dist >= 0.02) & ~out & ~seam
        S = P[skin]
        keep = ~(cuts_near(S, k) if cuts_near is not None else np.zeros(len(S), bool))
        S = S[keep]
        # local wall thickness: from a point of the outside to the nearest point of the inside
        t, _ = cKDTree(P[inner]).query(S)
        thin = t < MIN_WALL - 0.05
        lines = '%s: %d points of the outside (openings and seams left out): thinnest %.2f mm, 1%% under %.2f, median %.2f; %.2f%% under %.1f mm' % (
            k, len(S), t.min(), np.percentile(t, 1), np.median(t), thin.mean() * 100, MIN_WALL)
        if thin.any():
            lines += ' (thinnest at %s)' % np.round(S[np.argmin(t)], 1).tolist()
        wall_lines.append(lines)
        wall_ok &= thin.mean() < 0.001
        res['thin_' + k] = (S[thin], t[thin])
    report('wall thickness', wall_ok, '\n      ' + '\n      '.join(wall_lines))
    ov = {(a, b): (parts[a] ^ parts[b]).volume() for a in parts for b in parts if a < b}
    report('parts apart', max(ov.values()) < 0.01, ', '.join('%s/%s overlap %.3f mm3' % (a, b, v) for (a, b), v in ov.items()))

    # ------------------------------------------------------------ 6 magnets
    lines, good = [], True
    for k, (c, n) in info['magnets'].items():
        loc = btm.ray.intersects_location([c + n * 2.0], [-n])[0]
        dz = np.sort((c + n * 2.0 - loc) @ n - 2.0) if len(loc) else []
        depth = dz[0] if len(dz) else float('nan')
        floor = (dz[1] - dz[0]) if len(dz) > 1 else float('nan')
        good &= abs(depth - C.MAG_POCKET_T) < 0.05 and floor >= 1.0
        lines.append('%s at (%.1f, %.1f, %.1f): pocket Ø%.1f x %.2f deep (magnet %g x %g flush, epoxy 0.1), floor %.2f mm'
                     % (k, c[0], c[1], c[2], C.MAG_POCKET_D, depth, C.MAG_D, C.MAG_T, floor))
    report('magnet pockets', good, '\n      ' + '\n      '.join(lines))

    # ------------------------------------------------------------ 7 RP-SMA
    si = info['sma']
    c, n = si['centre'], si['n']
    P = C.sma_keep_points(c, n, 0.8)
    clash = np.any([C.to_trimesh(m).contains(P) for m in parts.values()], axis=0).mean() * 100
    loc = btm.ray.intersects_location([c + n * 1.0 + si['ey'] * 4.5], [-n])[0]
    wt = np.sort((c + n * 1.0 + si['ey'] * 4.5 - loc) @ n - 1.0) if len(loc) else []
    wall = (wt[1] - wt[0]) if len(wt) > 1 else float('nan')
    report('RP-SMA bulkhead', clash == 0 and 1.6 <= wall <= 3.0,
           'Ø%.1f D-hole (flat %.1f) at (%.1f, %.1f, %.1f), axis %s; wall %.2f mm at the hole; nut and jack room '
           'inside clear (%.1f%% of it in material)'
           % (C.SMA_HOLE_D, C.SMA_FLAT, c[0], c[1], c[2], np.round(n, 3).tolist(), wall, clash))
    global LAST
    LAST = res
    return ok


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    import time
    t0 = time.time()
    folder = sys.argv[1]
    parts = {}
    for k, pose in C.PRINT_POSE.items():
        t = trimesh.load(os.path.join(C.ENC, 'print', 'layercam-pro-%s.stl' % k))
        t.apply_transform(np.linalg.inv(pose))
        parts[k] = C.to_manifold(t)
    info = C.check_info(folder)
    ok = run(parts, info, folder)
    print('checked in %.0f s' % (time.time() - t0))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
