# -*- coding: utf-8 -*-
"""LayerCam Pro v1: the plan drawn in Prusa's case, and its two fit checks.

Draws images/plan-section.png (two cuts through the lens) from Prusa's
printed case for the Buddy3D camera, and checks in numbers what the drawing
shows:

  1. the six IR LEDs (straight light pipes, so each LED right under its
     front hole) against the IR-cut holder's base on the same face;
  2. the heatsink (on the main chip, at CHIP_XY) against the new case:
     its footprint inside the case at every height it spans, and its top
     under the new lid's inner face; and how many vent slots are over it;
  3. how far the main chip is from the image sensor (reported; the thermal
     model of the routed board decides whether it is far enough).

The case files are Prusa's (Printables model 1343977, GPL v2):
buddy-camera-bottom-r2.stl, buddy-camera-top-r1.stl, buddy-camera-lid-r1.stl.
They are downloaded, not committed. Put them in one folder and run:

    python3 src/plan_section.py <folder with the three STLs>

Needs numpy, trimesh, shapely, matplotlib, Pillow (a venv in out/ is fine).
Exits 1 if a check fails; the plan's README lists both as open risks until
the board's own design checks replace this script.

The frame is LayerCam's "lens frame" (../../../layercam/v1/src/geometry.py):
origin on the lens axis at the case's outer front face, +Z into the case.
"""
import math
import os
import sys

import numpy as np
import trimesh
from shapely.ops import unary_union

# ------------------------------------------------------------ the plan's numbers
BOARD_Z0, BOARD_T = 21.0, 1.6          # board front face, thickness (docs/decisions.md)
WALL = 2.5                             # new case wall at the board
LED_R, LED_ANGLES = 13.0, (0, 60, 120, 180, 240, 300)   # Prusa's holes (LayerCam geometry.py)
LED_SIZE = 3.75                        # OSRAM SFH 4715CS body, square
PIPE_D = 2.01                          # Bivar LPV2-0750
HOLDER_BOX = (-10.6, -9.8, 10.6, 9.8)  # Commonlands CLA219 base with its ears (full rectangle)
CHIP_H, TAPE_H = 0.85, 0.25            # RV1106 package, 3M 8810 tape
SINK = (20.0, 20.0, 15.0)              # stock heatsink, mm
# The main chip and its heatsink, lens frame X, Y. The image sensor is fixed
# on the lens axis (0, 0) by Prusa's lens bore; the lid's vent slots span
# X -10..10, Y -15.5..6.5. The chip goes towards -Y, as far from the sensor
# as keeps the heatsink inside the case: (0, -15.5) is the limit; at
# (0, -15) three of the six slots are over it, at (0, -12) four but the chip
# then nearly backs onto the sensor.
CHIP_XY = (0.0, -15.0)
CHIP_SIZE = 12.3                       # RV1106G3 QFN-128
SIDE_WALL = 2.0                        # new case side walls round the heatsink
LID_PLATE_Z = 41.0                     # the lid's flat top is at Z 41.0 or higher over the heatsink
LID_T = 1.6                            # new lid's thickness under the vents
MIN_GAP = 0.5                          # clearance each check asks for


def load_case(folder):
    """Prusa's three parts, assembled in the lens frame (measured 26 Oct 2026)."""
    def part(name):
        return trimesh.load(os.path.join(folder, 'buddy-camera-%s.stl' % name))
    bottom, top, lid = part('bottom-r2'), part('top-r1'), part('lid-r1')
    flip = np.eye(4)
    flip[:3, :3] = np.diag([1, -1, -1])
    flip[:3, 3] = [-4.21, 3.39, 45.68]
    top.apply_transform(flip)
    lid.apply_transform(flip)
    shift = np.eye(4)
    shift[:3, 3] = [-1.28, -0.74, -2.0]
    for m in (bottom, top, lid):
        m.apply_transform(shift)
    return trimesh.util.concatenate([bottom, top, lid]), lid


def hull_at(case, z):
    s = case.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    return unary_union(s.to_2D(to_2D=np.eye(4))[0].polygons_full).convex_hull


def led_gaps():
    """Clearance from each LED body to the holder's base (negative = overlap)."""
    x0, y0, x1, y1 = HOLDER_BOX
    out = []
    for a in LED_ANGLES:
        x, y = LED_R * math.cos(math.radians(a)), LED_R * math.sin(math.radians(a))
        h = LED_SIZE / 2
        # boxes apart along either axis -> the larger separation; else overlap depth
        gx = max(x0 - (x + h), (x - h) - x1)
        gy = max(y0 - (y + h), (y - h) - y1)
        out.append((a, x, y, max(gx, gy)))
    return out


def sink_box():
    from shapely.geometry import box
    cx, cy = CHIP_XY
    return box(cx - SINK[0] / 2, cy - SINK[1] / 2, cx + SINK[0] / 2, cy + SINK[1] / 2)


def vent_slots(case):
    """The lid's vent slots: the holes in the case's section just under its top."""
    s = case.section(plane_origin=[0, 0, 41.5], plane_normal=[0, 0, 1])
    from shapely.geometry import Polygon
    return [Polygon(h) for p in s.to_2D(to_2D=np.eye(4))[0].polygons_full for h in p.interiors]


def sink_fit(case):
    """(footprint fits at every height, gap from its top to the new lid's inner face,
    vent slots over it)."""
    fp = sink_box()
    sink_top = BOARD_Z0 + BOARD_T + CHIP_H + TAPE_H + SINK[2]
    under_plate = hull_at(case, LID_PLATE_Z).contains(fp)
    sides = all(hull_at(case, z).buffer(-SIDE_WALL).contains(fp)
                for z in np.arange(BOARD_Z0 + BOARD_T, sink_top + MIN_GAP, 1.0))
    gap = (LID_PLATE_Z - LID_T) - sink_top
    slots = sum(1 for v in vent_slots(case) if v.intersection(fp).area > 0.5 * v.area)
    return under_plate and sides, sink_top, gap, slots


def draw(case, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from PIL import Image

    bz1 = BOARD_Z0 + BOARD_T
    sink_z0 = bz1 + CHIP_H + TAPE_H
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.2))
    for k, (normal, axis, label) in enumerate((([0, 1, 0], 0, 'X'), ([1, 0, 0], 1, 'Y'))):
        ax = axes[k]
        for e in case.section(plane_origin=[0, 0, 0], plane_normal=normal).discrete:
            ax.plot(e[:, axis], e[:, 2], color='#9aa3ad', lw=1)
        zs = np.arange(0.2, 41.6, 0.4)
        lo, hi = [], []
        for z in zs:
            b = hull_at(case, z).bounds
            lo.append(b[axis])
            hi.append(b[axis + 2])
        ax.fill_betweenx(zs, lo, hi, color='#e8ecf0', zorder=0)
        ax.plot(lo, zs, color='#3a4450', lw=2)
        ax.plot(hi, zs, color='#3a4450', lw=2)
        b = hull_at(case, BOARD_Z0 + 0.8).bounds
        w0, w1 = b[axis] + WALL, b[axis + 2] - WALL
        ax.add_patch(Rectangle((w0, BOARD_Z0), w1 - w0, BOARD_T, color='#1f7a3a', zorder=5))
        ax.text(w1 - 1, BOARD_Z0 - 0.6, 'one board,\n%.0f mm across' % (w1 - w0),
                ha='right', va='bottom', color='#1f7a3a', fontsize=9, zorder=6)
        ax.add_patch(Rectangle((-5, BOARD_Z0 - 1.0), 10, 1.0, color='k', zorder=6))       # sensor
        hz0 = BOARD_Z0 - 1.0 - 9.5
        ax.add_patch(Rectangle((HOLDER_BOX[0], hz0), HOLDER_BOX[2] - HOLDER_BOX[0], 9.5,
                               fill=False, ec='#444', lw=1.5, zorder=6, hatch='//'))
        ax.add_patch(Rectangle((-7.2, 0.2), 14.4, hz0 - 0.2, color='#6b7c93', alpha=.85, zorder=6))
        ax.text(0, 5, 'lens', ha='center', color='w', fontsize=9, zorder=7)
        ax.text(0, 15, 'IR-cut\nholder', ha='center', fontsize=8, zorder=7)
        if k == 0:
            for x in (-LED_R, LED_R):
                ax.add_patch(Rectangle((x - PIPE_D / 2, 0.0), PIPE_D, BOARD_Z0 - 0.6,
                                       color='#d62728', alpha=.55, zorder=6))
            ax.text(-LED_R, 10, 'light\npipe', ha='center', fontsize=8, color='#8b0000', zorder=7, rotation=90)
        else:
            ax.add_patch(Rectangle((-14.15 - 1.5, 0.0), 3.0, BOARD_Z0 - 0.6, color='#f2c94c', alpha=.6, zorder=6))
            ax.text(-14.15, 10, 'light\nsensor\ntube', ha='center', fontsize=7, zorder=7)
        c = CHIP_XY[axis]                 # the chip's offset along this cut's axis
        ax.add_patch(Rectangle((c - CHIP_SIZE / 2, bz1), CHIP_SIZE, CHIP_H, color='#333', zorder=6))
        ax.add_patch(Rectangle((c - SINK[axis] / 2, sink_z0), SINK[axis], SINK[2], color='#c0c6cc', ec='#555', zorder=6))
        for i in range(6):
            ax.add_patch(Rectangle((c - SINK[axis] / 2 + 1 + i * 3.4, sink_z0 + 2), 1.2, SINK[2] - 2.2,
                                   color='#8c949c', zorder=7))
        ax.text(c, sink_z0 + SINK[2] / 2, 'stock heatsink\n%gx%gx%g' % SINK, ha='center', fontsize=8, zorder=8)
        ax.set_aspect('equal')
        ax.set_xlim(-45, 45)
        ax.set_ylim(44, -3)
        ax.set_xlabel(label + ' mm')
        ax.set_ylabel('Z mm from the front face into the case')
        ax.set_title('Cut through the lens, ' + ('left-right' if k == 0 else 'top-bottom'))
    axes[0].annotate('USB-C opening\n(Prusa: tilted ~28 deg)', xy=(-35.5, 26.6), xytext=(-44, 36),
                     fontsize=8, arrowprops=dict(arrowstyle='->'))
    plt.tight_layout()
    tmp = path + '.tmp.png'
    plt.savefig(tmp, dpi=110)
    Image.open(tmp).convert('RGB').quantize(256).save(path, optimize=True)
    os.remove(tmp)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    case, _ = load_case(sys.argv[1])
    ok = True

    print('1. IR LEDs (%.2f mm square) against the IR-cut holder base:' % LED_SIZE)
    for a, x, y, gap in led_gaps():
        bad = gap < MIN_GAP
        ok &= not bad
        print('   %3d deg (%6.2f, %6.2f): gap %+.2f mm%s' % (a, x, y, gap, '  FAIL' if bad else ''))

    fits, sink_top, gap, slots = sink_fit(case)
    good = fits and gap >= MIN_GAP and slots >= 3
    ok &= good
    print('2. Heatsink %gx%gx%g on the chip at (%g, %g): footprint inside the case %s; top Z %.2f, '
          '%.1f mm lid inner face Z %.2f or higher: gap %+.2f mm; %d vent slots over it%s'
          % (SINK + CHIP_XY + ('at every height' if fits else 'NOT everywhere', sink_top, LID_T,
             LID_PLATE_Z - LID_T, gap, slots, '' if good else '  FAIL')))
    d = math.hypot(*CHIP_XY)
    print('3. Main chip centre %.1f mm from the image sensor (edge to edge about %.1f mm across the board): '
          'the thermal model decides' % (d, d - CHIP_SIZE / 2 - 3.1))

    here = os.path.dirname(os.path.abspath(__file__))
    draw(case, os.path.join(here, '..', 'images', 'plan-section.png'))
    print('drew images/plan-section.png')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
