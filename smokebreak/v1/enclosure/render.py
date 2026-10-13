"""Preview renders of the exported STLs (Blender bpy, headless Cycles).

    /root/bpyenv/bin/python render.py

-> out/preview_iso.png (assembly, guard closed), out/preview_open.png (guard open, iso from the back),
   out/preview_top.png (the face), out/preview_top_underside.png (the top shell from below),
   out/preview_floor.png (the floor, inside up), out/preview_section.png (cut through the switch).
Files are in the export frame: x toward the drone end, Y toward the back, z up.
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
CTX = os.path.join(OUT, 'context')

COL = {'top': (0.10, 0.095, 0.085), 'bottom': (0.16, 0.15, 0.14), 'guard': (0.89, 0.36, 0.02),
       'rocker': (0.62, 0.64, 0.66), 'ring_inlay': (0.45, 0.95, 0.6), 'text_inlay': (0.95, 0.93, 0.86),
       'pcb': (0.05, 0.2, 0.08), 'display': (0.01, 0.01, 0.02), 'parts': (0.6, 0.62, 0.55),
       'xt': (0.95, 0.75, 0.1), 'usb': (0.75, 0.75, 0.78), 'toggle': (0.8, 0.8, 0.82), 'wires': (0.7, 0.08, 0.06)}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1100
    sc.render.film_transparent = False
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.92, 0.9, 0.86, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
    sc.view_settings.view_transform = 'Standard'
    return sc


def mat(name, rgb, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = 0.55
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
    return m


def load(path, color, matrix=None, alpha=1.0):
    bpy.ops.wm.stl_import(filepath=path)
    o = bpy.context.selected_objects[0]
    o.data.materials.append(mat(os.path.basename(path), color, alpha))
    if matrix is not None:
        o.matrix_world = matrix
    for p in o.data.polygons:
        p.use_smooth = False
    return o


def light_and_camera(sc, loc, target, ortho=None, lens=50):
    cam = bpy.data.cameras.new('c')
    if ortho:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho
    else:
        cam.lens = lens
    co = bpy.data.objects.new('c', cam)
    sc.collection.objects.link(co)
    co.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co
    for i, (lx, ly, lz, e) in enumerate([(60, -80, 120, 3.0), (-80, 60, 80, 1.5), (40, 120, -60, 1.0)]):
        ld = bpy.data.lights.new(f'l{i}', 'SUN')
        ld.energy = e
        lo = bpy.data.objects.new(f'l{i}', ld)
        sc.collection.objects.link(lo)
        lo.rotation_euler = (Vector((48, 28, 8)) - Vector((48 + lx, 28 + ly, 8 + lz))).to_track_quat('-Z', 'Y').to_euler()


def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    print('wrote', name)


def guard_matrix(deg):
    # hinge axis in the export frame: along x through (Y = 56 - 2.6, z = 13.0); opening tips the guard toward +Y
    y, z = 56.0 - 2.6, 13.0
    return Matrix.Translation((0, y, z)) @ Matrix.Rotation(math.radians(-deg), 4, 'X') @ Matrix.Translation((0, -y, -z))


def context(sc):
    if not os.path.isdir(CTX):
        return
    for f in sorted(os.listdir(CTX)):
        key = f.split('.')[0].split('_')[0]
        load(os.path.join(CTX, f), COL.get(key, COL['parts']))


def scene_assembly(guard_deg=0.0, with_ctx=True, skip=()):
    sc = reset()
    for p in ('top', 'bottom', 'rocker', 'ring_inlay', 'text_inlay'):
        if p not in skip:
            load(os.path.join(OUT, f'{p}.stl'), COL[p])
    if 'guard' not in skip:
        load(os.path.join(OUT, 'guard.stl'), COL['guard'], guard_matrix(guard_deg))
    if with_ctx:
        context(sc)
    return sc


def main():
    sc = scene_assembly(0.0)
    light_and_camera(sc, (48 + 95, 28 - 120, 115), (48, 26, 8), lens=60)
    render(sc, 'preview_iso.png')

    sc = scene_assembly(105.0)
    light_and_camera(sc, (48 + 90, 28 + 130, 110), (48, 30, 12), lens=60)
    render(sc, 'preview_open.png')

    sc = scene_assembly(0.0, with_ctx=False)
    light_and_camera(sc, (48.5, 28, 200), (48.5, 28, 0), ortho=108)
    render(sc, 'preview_top.png')

    sc = reset()
    load(os.path.join(OUT, 'top.stl'), (0.35, 0.33, 0.3))
    light_and_camera(sc, (48.5 + 60, 28 - 70, -110), (48.5, 28, 8), lens=55)
    render(sc, 'preview_top_underside.png')

    sc = reset()
    load(os.path.join(OUT, 'bottom.stl'), (0.35, 0.33, 0.3))
    light_and_camera(sc, (48.5 + 60, 28 - 90, 110), (48.5, 28, 0), lens=55)
    render(sc, 'preview_floor.png')


if __name__ == '__main__':
    main()
