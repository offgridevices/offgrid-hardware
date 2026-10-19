"""Fuse options, rendered so they can be compared by eye.

    <bpy venv>/bin/python options.py      # b-closed.png, b-open.png, c-inline.png

B: the case 8 mm deeper at the front; a MINI blade fuse stands in a bay at
   the battery end's front corner under a one-screw cover.
C: the product as it is, plus an inline blade fuse holder on the drone's
   XT60 lead (outside the case).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'arm'))
import arm                   # noqa: E402
import bpy                   # noqa: E402
s = arm.s

FUSE_GREEN = '#2E9E4F'       # 30 A MINI blade colour


def fuse(loc, name='fuse'):
    """MINI blade fuse, 10.9 x 3.8 mm, grip up, blades down."""
    x, y, z = loc
    body = s.mat('fuse 30A', FUSE_GREEN, 0.25, coat=0.6)
    parts = [s.box((10.9, 3.8, 8.7), (x, y, z + 4.35), m=body, bevel=0.5, name=name),
             s.box((10.0, 3.9, 2.2), (x, y, z + 7.6), m=s.mat('fuse grip', '#237A3C', 0.4), bevel=0.4)]
    for dx in (-3.6, 3.6):
        parts.append(s.box((2.8, 0.8, 6.0), (x + dx, y, z - 3.0), m='steel', bevel=0.1))
    s.text('30', 2.6, (x, y - 1.95, z + 4.6), rot=(90, 0, 0), m=s.mat('fuse ink', '#F1ECE0', 0.5))
    return parts


def variant_b(open_=False):
    sc = s.reset()
    arm.D = 66.0                                  # 8 mm deeper, at the front
    h = arm.build(still_frame=int((arm.T0 + 0.8) * arm.FPS))
    arm.key_guard(h['guard'], 0, 0.0)
    arm.key_lever(h['lever'], 0, arm.LEVER_OFF)
    arm.key_ring(h['ring'], 0, s.EMBER, 0.6)
    top = arm.H
    # the bay: front-left corner, a cover flush with the face, one screw
    cx, cy = arm.F(9.5, 60.0)
    body = bpy.data.objects['body']
    plate = bpy.data.objects['face-plate']
    for o in (body, plate):
        arm.cut(o, (13.0, 8.0, 12.0), (cx, cy, top - 4.0))
    s.box((13.0, 8.0, 0.3), (cx, cy, top - 10.0), m=s.mat('bay floor', '#0B0A08', 0.7), bevel=0.2)
    lift = 14.0 if open_ else 0.0
    cover = s.box((12.6, 7.6, 1.6), (cx, cy, top - 0.4 + lift), m='anodised', bevel=0.5, name='cover')
    if open_:
        cover.rotation_euler = (math.radians(-18), 0, math.radians(12))
    s.cyl(1.4, 0.4, (cx + 4.4, cy, top + 0.45 + lift), m='steel', bevel=0.1, name='screw')
    s.text('FUSE', 1.3, (cx - 1.2, cy + 1.3, top + 0.45 + lift), m='bone')
    s.text('30 A  58 V', 1.0, (cx - 1.2, cy - 1.4, top + 0.45 + lift), m='bone', mono=True)
    fz = (top - 9.5) + (20.0 if open_ else 0.0)
    fuse((cx, cy, fz))
    cam, pivot = s.stage(elevation=34, azimuth=-28)
    cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
    sc.render.filepath = os.path.join(HERE, 'b-open.png' if open_ else 'b-closed.png')
    bpy.ops.render.render(write_still=True)


def variant_c():
    sc = s.reset()
    arm.D = 58.0
    h = arm.build(still_frame=int((arm.T0 + 0.8) * arm.FPS))
    arm.key_guard(h['guard'], 0, 0.0)
    arm.key_lever(h['lever'], 0, arm.LEVER_OFF)
    arm.key_ring(h['ring'], 0, s.EMBER, 0.6)
    # inline blade holder on the XT60 lead's red wire, a third of the way out
    x, y = arm.P(94 + arm.WALL, 18.2)
    hx, hy, hz = x + 22, y + 2.4, 5.6
    s.box((26, 11, 9), (hx, hy, hz), m=s.mat('holder', '#141210', 0.55), bevel=1.5, name='holder')
    s.box((26.2, 11.2, 0.6), (hx, hy, hz + 1.2), m=s.mat('seam', '#050505', 0.6), bevel=0.2)
    s.text('30 A', 1.8, (hx, hy, hz + 4.55), m='bone')
    cam, pivot = s.stage(elevation=32, azimuth=30)
    cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
    sc.render.filepath = os.path.join(HERE, 'c-inline.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    which = sys.argv[1:] or ['b-closed', 'b-open', 'c']
    for w in which:
        if w == 'b-closed':
            variant_b(False)
        elif w == 'b-open':
            variant_b(True)
        elif w == 'c':
            variant_c()
        sc = bpy.context.scene
