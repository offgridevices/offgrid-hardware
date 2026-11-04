"""Grip and stability concept renders: thumb scoop in the front wall under
the toggle, steel floor, silicone feet.
    <bpy venv>/bin/python grip.py   -> 2-thumb-rest.png, 3-underside.png"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'arm'))
import arm                   # noqa: E402
import bpy                   # noqa: E402
s = arm.s

STEEL = None


def extras():
    """Scoop, floor plate and feet onto the built body."""
    body = bpy.data.objects['body']
    tx, ty = arm.F(arm.TX, 0)
    # thumb scoop: a shallow oval dish in the front wall, under the toggle
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(tx, -arm.D / 2 - 4.6, arm.H * 0.5))
    c = bpy.context.active_object
    c.scale = (12.0, 7.0, 6.5)
    mod = body.modifiers.new('scoop', 'BOOLEAN')
    mod.operation, mod.object, mod.solver = 'DIFFERENCE', c, 'EXACT'
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.modifier_move_to_index(modifier='scoop', index=0)
        bpy.ops.object.modifier_apply(modifier='scoop')
    bpy.data.objects.remove(c, do_unlink=True)
    # steel floor plate, inset 1.2 mm, brushed, four M3 screws
    steel = s.mat('steel plate', '#8E9498', 0.55, metal=1.0)
    arm.rbox(arm.W - 4, arm.D - 4, 1.5, arm.R - 2, (0, 0, -0.55), steel, edge=0.3, name='base-plate')
    for x, y in ((5, 5), (89, 5), (5, 47), (89, 47)):
        px, py = arm.P(x, y)
        s.cyl(2.8, 0.3, (px, py, -1.35), m='steel', bevel=0.1, name='screw')
    s.lockup(30.0, (0, 4, -1.33), rot=(180, 0, 0), m=s.mat('etch', '#C9CED1', 0.8, metal=0.6), name='plate-lockup')
    # silicone feet: two long strips along the ends
    rub = s.mat('silicone', '#141311', 0.85)
    for sx in (-arm.W / 2 + 9, arm.W / 2 - 9):
        s.box((7, arm.D - 16, 1.2), (sx, 0, -1.9), m=rub, bevel=0.5, name='foot')


def scene(name, el, az, flip=False, lens=70):
    sc = s.reset()
    h = arm.build(still_frame=int((arm.T0 + 0.8) * arm.FPS))
    arm.key_guard(h['guard'], 0, 0.0)
    arm.key_lever(h['lever'], 0, arm.LEVER_OFF)
    arm.key_ring(h['ring'], 0, s.EMBER, 0.6)
    extras()
    if flip:                      # upside down on the desk, to show the underside
        root = bpy.data.objects.new('root', None)
        bpy.context.collection.objects.link(root)
        for o in list(bpy.data.objects):
            if o is not root and o.parent is None:
                o.parent = root
        root.rotation_euler = (math.radians(180), 0, 0)
        root.location = (0, 0, arm.H + 14)
    cam, pivot = s.stage(elevation=el, azimuth=az, lens=lens)
    cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
    sc.render.filepath = os.path.join(HERE, name)
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    scene('2-thumb-rest.png', 14, 18)
    scene('3-underside.png', 40, -20, flip=True)
