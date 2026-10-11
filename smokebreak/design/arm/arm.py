"""SmokeBreak Arm: the chosen industrial design (concept 10), refined, and its
demo animation.

    <bpy venv>/bin/python arm.py still      # hero.png and top.png
    <bpy venv>/bin/python arm.py video      # arm-demo.mp4 (3D + the real screen + sound)

The screen in the animation plays ../../ui/frames24 (made by ui/screens.py
and resampled to 24 fps), so the 3D product shows exactly the screens in
the storyboard, in sync with the guard and the switch.

Units: mm. +X runs battery end -> drone end, +Y away from the user.
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SB, 'concepts', '_blender'))
import bpy            # noqa: E402
import studio as s    # noqa: E402

FPS = 24
UI_FRAMES = os.path.join(SB, 'ui', 'frames24')
UI_VIDEO = os.path.join(SB, 'ui', 'arm-sequence.mp4')

# ---------------------------------------------------------------- geometry
W, D, H, R = 96.0, 58.0, 18.0, 9.0        # body
TX, TY = 73.0, 31.0                        # toggle, face coords (x from left, y from back)
HY = 12.0                                  # guard hinge line, face y
GL, GW, GH = 34.0, 24.0, 17.0              # guard length, width, wall height
OPEN = 108.0                               # open angle, degrees
LEVER_ON, LEVER_OFF, LEVER_BIND = 24.0, 0.0, -24.0
SCR = (28.5, 21.0, 46.0, 26.0)             # screen window centre x, y, width, height (face coords)
ACTIVE = (42.7, 22.7)                      # 1.9" 320 x 170 IPS active area


def F(x, y):
    """Face coordinates (x from the left edge, y from the back edge) to world."""
    return (x - W / 2, D / 2 - y)


def rbox(w, d, h, r, loc, m, edge=1.4, name='rbox'):
    import bmesh
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    vert = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6
            and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6]
    bmesh.ops.bevel(bm, geom=vert, offset=r, segments=10, affect='EDGES', profile=0.5)
    bm.to_mesh(o.data)
    bm.free()
    return s._finish(o, m, bevel=edge, segments=4)


def ring_material():
    """The Beacon Ring's light, its own material so its colour can be animated."""
    m = bpy.data.materials.new('beacon light')
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = s.srgb(s.EMBER)
    p.inputs['Emission Color'].default_value = s.srgb(s.EMBER)
    p.inputs['Emission Strength'].default_value = 1.0
    p.inputs['Roughness'].default_value = 0.35
    return m


def guard_material():
    """Translucent Ember polycarbonate: the ring lights it from inside."""
    m = bpy.data.materials.new('guard ember PC')
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = s.srgb('#FF7A1A')
    p.inputs['Roughness'].default_value = 0.18
    p.inputs['Transmission Weight'].default_value = 0.92
    p.inputs['IOR'].default_value = 1.58
    p.inputs['Coat Weight'].default_value = 0.6
    return m


def screen_material(sequence=True):
    m = bpy.data.materials.new('screen')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1)
    p.inputs['Roughness'].default_value = 0.6
    p.inputs['Specular IOR Level'].default_value = 0.1
    p.inputs['Emission Strength'].default_value = 2.4
    tex = nt.nodes.new('ShaderNodeTexImage')
    first = os.path.join(UI_FRAMES, 'f00001.png')
    img = bpy.data.images.load(first)
    if sequence:
        img.source = 'SEQUENCE'
        tex.image_user.frame_duration = len(os.listdir(UI_FRAMES))
        tex.image_user.frame_start = 1
        tex.image_user.frame_offset = 0
        tex.image_user.use_auto_refresh = True
    tex.image = img
    nt.links.new(tex.outputs['Color'], p.inputs['Emission Color'])
    return m, tex


def screen_plane(m):
    x, y = F(SCR[0], SCR[1])
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, H + 0.66))
    o = bpy.context.active_object
    o.name = 'screen-active'
    o.scale = (ACTIVE[0], ACTIVE[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    s.assign(o, m)
    return o


def build(still_frame=None):
    """The product. Returns the handles the animation drives."""
    top = H
    rbox(W, D, H, R, (0, 0, H / 2), 'pitch_soft', name='body')
    # a thin anodised band where the face meets the body
    rbox(W - 2.4, D - 2.4, 1.0, R - 1.2, (0, 0, H + 0.1), 'anodised', edge=0.4, name='face-plate')

    # screen: black glass window with the live panel under it
    x, y = F(SCR[0], SCR[1])
    s.box((SCR[2], SCR[3], 0.6), (x, y, top + 0.32), m=s.mat('glass black', '#050505', 0.06, coat=1.0),
          bevel=0.8, name='window')
    smat, tex = screen_material(sequence=still_frame is None)
    if still_frame is not None:
        tex.image = bpy.data.images.load(os.path.join(UI_FRAMES, f'f{still_frame:05d}.png'))
    screen_plane(smat)

    # Limit rocker: an aluminium paddle over two switches, with the steps printed beneath
    x, y = F(SCR[0], 45.5)
    s.box((40, 9, 2.4), (x, y, top + 1.4), m='brushed', bevel=1.0, name='rocker')
    s.box((0.5, 6, 0.1), (x, y, top + 2.62), m='screen', bevel=0, name='rocker-split')
    s.text('–', 3.0, (x - 10, y, top + 2.62), m='pitch', mono=True)
    s.text('+', 3.0, (x + 10, y, top + 2.62), m='pitch', mono=True)
    x, y = F(8.5, 53.0)
    s.text('Limit', 1.9, (x, y, top + 0.62), align='LEFT')
    s.text('AUTO 1 2 5 10 25 A', 1.3, (x + 8, y, top + 0.62), mono=True, align='LEFT')

    # toggle with the Beacon Ring round its bushing
    rmat = ring_material()
    tx, ty = F(TX, TY)
    ring = s.beacon_ring(13.0, 1.7, loc=(tx, ty, top + 0.65), m=rmat, name='beacon')
    s.cyl(4.6, 0.9, (tx, ty, top + 0.95), m='steel', bevel=0.2, verts=6, name='nut')
    s.cyl(3.0, 3.4, (tx, ty, top + 3.0), m='steel', bevel=0.3, name='bushing')
    lever = bpy.data.objects.new('lever', None)
    bpy.context.collection.objects.link(lever)
    lever.location = (tx, ty, top + 4.4)
    L = 11.0
    for p in (s.cyl(1.25, L, (0, 0, L / 2), m='aluminium', bevel=0.3, name='lever-bat'),
              s.sphere(1.7, (0, 0, L), m='aluminium', name='lever-tip')):
        p.parent = lever
    for lab, dy in (('On', -7.0), ('Off', 0.0), ('Bind', 7.0)):
        x, y = F(TX + 16.5, TY + dy)
        s.text(lab, 1.8, (x, y, top + 0.62), align='LEFT')

    # guard: translucent Ember polycarbonate on a steel pin
    hx, hy = F(TX, HY)
    hz = top + 2.6
    s.box((GW + 5, 4.5, 3.0), (hx, hy + 0.6, top + 1.5), m='anodised', bevel=0.6, name='hinge-block')
    s.cyl(1.1, GW + 6, (hx, hy, hz), m='steel', bevel=0.2, rot=(0, 90, 0), name='pin')
    guard = bpy.data.objects.new('guard', None)
    bpy.context.collection.objects.link(guard)
    guard.location = (hx, hy, hz)
    gm = guard_material()
    wall_z = -GH / 2 + 1.2
    for p in (s.box((GW, GL, 1.8), (0, -GL / 2 - 1.0, 0), m=gm, bevel=0.6, name='guard-top'),
              s.box((1.8, GL, GH), (-GW / 2 + 0.9, -GL / 2 - 1.0, wall_z), m=gm, bevel=0.6, name='guard-wall'),
              s.box((1.8, GL, GH), (GW / 2 - 0.9, -GL / 2 - 1.0, wall_z), m=gm, bevel=0.6, name='guard-wall'),
              s.box((GW, 1.8, GH), (0, -GL - 0.1, wall_z), m=gm, bevel=0.6, name='guard-lip'),
              s.text('ARM', 3.2, (0, -GL / 2 - 2, 0.95), m='bone', name='guard-word')):
        p.parent = guard
    # an arrow on the face, beside the guard: lift
    x, y = F(TX - 16.5, TY + 9)
    s.arrow(7, (x, y, top + 0.62), rot_z=90, shaft=0.35, head=0.9)
    s.text('Lift', 1.8, (x, y + 5.6, top + 0.62))

    # face printing: in and out
    x, y = F(4.0, 4.8)
    s.text('Battery', 1.9, (x, y, top + 0.62), align='LEFT')
    s.arrow(8, (x + 4, y - 2.6, top + 0.62), shaft=0.35, head=0.9)
    x, y = F(W - 4.0, D - 4.8)
    s.text('Drone', 1.9, (x, y, top + 0.62), align='RIGHT')
    s.arrow(8, (x - 4, y + 2.6, top + 0.62), shaft=0.35, head=0.9)
    x, y = F(50, 51.5)
    s.beacon_ring(1.3, 0.45, loc=(x - 3.0, y + 0.4, top + 0.65), m='bone', name='mark')
    s.text('OffGrid', 2.0, (x - 0.5, y, top + 0.62), align='LEFT', name='wordmark')
    s.text('SmokeBreak', 1.5, (x - 0.5, y - 3.2, top + 0.62), align='LEFT', m=s.mat('bone dim', '#9E978A', 0.6))

    # connectors: male XT60 + XT30 in, female leads out, USB-C at the back
    x, y = F(0, 20.75)
    s.xt60((x - 2, y, 9), male=True, name='in60')
    x, y = F(0, 42)
    s.xt30((x - 1.5, y, 8), male=True, name='in30')
    x, y = F(W, 22)
    s.leads((x - 3, y, 8), (x + 52, y - 2, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 2, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = F(W, 44)
    s.leads((x - 3, y, 7), (x + 32, y - 12, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 12, 2.6), rot=(0, 0, 180), male=False, name='out30')
    s.usb_c((F(40, 0)[0], D / 2 + 0.1, 9), rot=(0, 0, 90))
    return dict(guard=guard, lever=lever, ring=rmat)


# ---------------------------------------------------------------- the story
# seconds, matching ui/screens.py TIMELINE
T_LIFT1, T_FLICK1, T_LIVE, T_WARN, T_CLOSE1 = 2.0, 4.2, 8.0, 11.5, 13.9
T_LIFT2, T_FLICK2, T_ABORT, T_CLOSE2, T_END = 16.1, 17.1, 17.9, 20.5, 22.0

DIM = (s.EMBER, 0.6)


def key_guard(g, t, deg):
    g.rotation_euler = (math.radians(-deg), 0, 0)
    g.keyframe_insert('rotation_euler', frame=int(t * FPS) + 1)


def key_lever(lv, t, deg):
    lv.rotation_euler = (math.radians(-deg), 0, 0)
    lv.keyframe_insert('rotation_euler', frame=int(t * FPS) + 1)


def key_ring(m, t, colour, strength):
    p = m.node_tree.nodes['Principled BSDF']
    f = int(t * FPS) + 1
    p.inputs['Emission Color'].default_value = s.srgb(colour)
    p.inputs['Base Color'].default_value = s.srgb(colour)
    p.inputs['Emission Strength'].default_value = strength
    for k in ('Emission Color', 'Base Color', 'Emission Strength'):
        p.inputs[k].keyframe_insert('default_value', frame=f)


def animate(h):
    g, lv, rm = h['guard'], h['lever'], h['ring']
    # guard: closed, lift, close (with an overshoot snap), lift, close
    for t, a in ((0, 0), (T_LIFT1 - 0.05, 0), (T_LIFT1 + 0.35, OPEN + 6), (T_LIFT1 + 0.55, OPEN),
                 (T_CLOSE1, OPEN), (T_CLOSE1 + 0.22, -1.5), (T_CLOSE1 + 0.32, 0),
                 (T_LIFT2 - 0.05, 0), (T_LIFT2 + 0.3, OPEN + 6), (T_LIFT2 + 0.5, OPEN),
                 (T_CLOSE2, OPEN), (T_CLOSE2 + 0.22, -1.5), (T_CLOSE2 + 0.32, 0)):
        key_guard(g, t, a)
    # lever: off, flick on, cammed off by the closing guard, again
    for t, a in ((0, LEVER_OFF), (T_FLICK1 - 0.04, LEVER_OFF), (T_FLICK1 + 0.08, LEVER_ON),
                 (T_CLOSE1 + 0.05, LEVER_ON), (T_CLOSE1 + 0.2, LEVER_OFF),
                 (T_FLICK2 - 0.04, LEVER_OFF), (T_FLICK2 + 0.08, LEVER_ON),
                 (T_CLOSE2 + 0.05, LEVER_ON), (T_CLOSE2 + 0.2, LEVER_OFF)):
        key_lever(lv, t, a)
    # ring light
    seq = [(0, s.EMBER, 0.6), (T_LIFT1, s.EMBER, 0.6)]
    t = T_LIFT1 + 0.05
    while t < T_FLICK1:                       # armed: Ember pulse
        seq += [(t, s.EMBER, 7.0), (t + 0.25, s.EMBER, 2.0)]
        t += 0.5
    seq += [(T_FLICK1, '#FFF4E6', 4.0), (T_LIVE - 0.05, '#FFF4E6', 4.0), (T_LIVE, s.GREEN, 14.0),
            (T_LIVE + 0.6, s.GREEN, 6.0), (T_WARN - 0.05, s.GREEN, 6.0), (T_WARN, s.EMBER, 8.0),
            (T_CLOSE1, s.EMBER, 8.0), (T_CLOSE1 + 0.3, s.EMBER, 0.6), (T_LIFT2, s.EMBER, 0.6),
            (T_LIFT2 + 0.1, s.EMBER, 7.0), (T_FLICK2, '#FFF4E6', 4.0)]
    t = T_ABORT
    while t < T_CLOSE2:                       # abort: red flashing
        seq += [(t, s.RED, 14.0), (t + 0.16, s.RED, 1.0)]
        t += 0.33
    seq += [(T_CLOSE2 + 0.3, s.EMBER, 0.6), (T_END, s.EMBER, 0.6)]
    for t, c, k in seq:
        key_ring(rm, t, c, k)
    # constant interpolation for the light, so changes are crisp
    for m in (rm,):
        ad = m.node_tree.animation_data
        _set_interp(ad.action, 'CONSTANT')


def _set_interp(action, mode):
    curves = []
    if hasattr(action, 'fcurves'):
        curves = list(action.fcurves)
    try:
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    curves += list(cb.fcurves)
    except Exception:
        pass
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = mode


def camera(cam, pivot):
    """A slow drift across the product, starting high and settling lower."""
    sc = bpy.context.scene
    pivot.rotation_euler = (0, 0, math.radians(-14))
    pivot.keyframe_insert('rotation_euler', frame=1)
    pivot.rotation_euler = (0, 0, math.radians(10))
    pivot.keyframe_insert('rotation_euler', frame=int(T_END * FPS))
    _set_interp(pivot.animation_data.action, 'BEZIER')


def render_still():
    sc = s.reset()
    h = build(still_frame=int(9.5 * FPS))          # a Live screen
    key_guard(h['guard'], 0, OPEN)
    key_lever(h['lever'], 0, LEVER_ON)
    key_ring(h['ring'], 0, s.GREEN, 8.0)
    cam, pivot = s.stage(elevation=30, azimuth=-30)
    sc.render.filepath = os.path.join(HERE, 'hero.png')
    bpy.ops.render.render(write_still=True)
    # top view
    lo, hi = s.bounds([o for o in sc.objects if o.name != 'floor'])
    cam.constraints.clear()
    cam.parent = None
    cam.data.type = 'ORTHO'
    cam.data.shift_x = cam.data.shift_y = 0
    cam.data.ortho_scale = max(hi.x - lo.x, hi.y - lo.y) * 1.1
    c = (lo + hi) / 2
    cam.location = (c.x, c.y, hi.z + 500)
    cam.rotation_euler = (0, 0, 0)
    sc.render.filepath = os.path.join(HERE, 'top.png')
    bpy.ops.render.render(write_still=True)


def render_video(quick=False):
    sc = s.reset()
    h = build()
    animate(h)
    cam, pivot = s.stage(elevation=34, azimuth=-24, lens=95)
    cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
    camera(cam, pivot)
    sc.frame_start, sc.frame_end = 1, int(T_END * FPS)
    sc.render.fps = FPS
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 50 if quick else 75
    sc.cycles.samples = 6 if quick else 10
    sc.cycles.max_bounces = 6
    sc.render.use_persistent_data = True
    tmp = tempfile.mkdtemp(prefix='sb-arm-')
    try:
        sc.render.filepath = os.path.join(tmp, 'f_')
        sc.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(animation=True)
        out = os.path.join(HERE, 'arm-demo.mp4')
        # the 3D film, the flat screen inset bottom-right, and the beeps from the screen video
        inset_w = 300 if not quick else 200
        fc = (f"[1:v]trim=0:{T_END},setpts=PTS-STARTPTS,scale={inset_w}:-2,"
              f"pad=iw+8:ih+8:4:4:color=0x1B1813[ui];[0:v][ui]overlay=W-w-24:H-h-24[v]")
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i',
                        os.path.join(tmp, 'f_%04d.png'), '-i', UI_VIDEO, '-filter_complex', fc,
                        '-map', '[v]', '-map', '1:a', '-t', str(T_END), '-c:v', 'libx264', '-pix_fmt',
                        'yuv420p', '-crf', '18', '-c:a', 'aac', out], check=True)
        print(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'still'
    if what == 'still':
        render_still()
    else:
        render_video(quick='--quick' in sys.argv)
