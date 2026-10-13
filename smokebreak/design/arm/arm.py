"""SmokeBreak Arm: the chosen industrial design (concept 10), refined, and its
demo animation.

    <bpy venv>/bin/python arm.py still      # hero.png and top.png
    <bpy venv>/bin/python arm.py showcase   # showcase-*.png: armed, back, closed
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
W, D, H, R = 100.0, 58.0, 18.0, 9.0       # body
WALL = 3.0                                 # the PCB (94 x 52) sits 3 mm in from every outside face
PCB_Z = 4.5                                # its top face (11.5 mm under the panel's underside)
TX, TY = 76.2, 22.5                        # toggle, face coords (x from left, y from back) = PCB (73.2, 19.5) + wall
HY = 10.5                                  # guard hinge line, face y
GL, GW, GH = 29.0, 30.0, 17.0              # guard length (its tip over the hall switch at PCB y 36.6), width, height
RING = 10.0                                # status light round the toggle (a plain ring, not the mark)
MARK_R = 3.4                               # the mark on the front wall: ring radius (8.1 mm wide)
OPEN = 108.0                               # open angle, degrees
LEVER_ON, LEVER_OFF, LEVER_BIND = 24.0, 0.0, -24.0
SCR = (29.0, 17.0, 46.0, 26.0)             # screen window centre x, y, width, height (face coords)
ACTIVE = (42.7, 22.7)                      # 1.9" 320 x 170 IPS active area


def F(x, y):
    """Face coordinates (x from the left edge, y from the back edge) to world."""
    return (x - W / 2, D / 2 - y)


def P(x, y):
    """PCB coordinates (v1/src/place.py) to world."""
    return F(x + WALL, y + WALL)


def cut(target, size, loc, bevel=0.8):
    """Boolean a rounded box out of target."""
    c = s.box(size, loc, m='pitch', bevel=bevel, name='cutter')
    mod = target.modifiers.new('cut', 'BOOLEAN')
    mod.operation, mod.object, mod.solver = 'DIFFERENCE', c, 'EXACT'
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_move_to_index(modifier='cut', index=0)   # before the edge bevel
        bpy.ops.object.modifier_apply(modifier='cut')
    bpy.data.objects.remove(c, do_unlink=True)
    return target


# the balance well: top-entry JST-XH sockets (PCB x, pins), pin 1 (the black
# wire) on one line at PCB y 48, pins running back 2.5 mm apart
SOCKETS = ((16.0, 3), (23.1, 4), (30.2, 5), (37.3, 6), (44.4, 7))
PIN1_Y, XH_D, XH_H = 48.0, 5.75, 7.0


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
    """The status light, its own material so its colour can be animated."""
    m = bpy.data.materials.new('status light')
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
    body = rbox(W, D, H, R, (0, 0, H / 2), 'pitch_soft', name='body')
    # a thin anodised band where the face meets the body
    plate = rbox(W - 2.4, D - 2.4, 1.0, R - 1.2, (0, 0, H + 0.1), 'anodised', edge=0.4, name='face-plate')
    # the balance well: one recess over the five sockets, down to their tops
    floor = PCB_Z + XH_H
    x0, x1 = SOCKETS[0][0] - XH_D / 2 - 1.2, SOCKETS[-1][0] + XH_D / 2 + 1.2
    y0, y1 = PIN1_Y - 2.5 * (SOCKETS[-1][1] - 1) - 2.45 - 1.2, PIN1_Y + 2.45 + 1.6
    (wx0, wy0), (wx1, wy1) = P(x0, y0), P(x1, y1)
    wsize = (wx1 - wx0, wy0 - wy1, top + 2 - floor)
    wloc = ((wx0 + wx1) / 2, (wy0 + wy1) / 2, floor + wsize[2] / 2)
    for o in (body, plate):
        cut(o, wsize, wloc)
    s.box((wsize[0], wsize[1], 0.4), (wloc[0], wloc[1], floor - 0.2), m=s.mat('well', '#0B0A08', 0.7),
          bevel=0.3, name='well-floor')
    white = s.mat('jst nylon', '#EDEAE2', 0.55)
    for x, pins in SOCKETS:
        L = 2.5 * (pins - 1) + 4.9
        cx, cy = P(x, PIN1_Y - 1.25 * (pins - 1))
        s.box((XH_D, L, 1.0), (cx, cy, floor + 0.1), m=white, bevel=0.3, name=f'xh{pins - 1}s')
        s.box((XH_D - 1.6, L - 1.8, 1.1), (cx, cy, floor + 0.15), m='screen', bevel=0.2, name=f'xh{pins - 1}s-mouth')
        # its size on the face's front lip, an arrow at pin 1 (the black wire)
        lx, ly = P(x, y1 + 0.2)
        s.text(f'{pins - 1}S', 1.4, (lx + 0.9, ly - 1.4, top + 0.62), align='LEFT')
        s.arrow(1.6, (lx - 0.2, ly - 2.1, top + 0.62), rot_z=90, shaft=0.3, head=0.9)

    # screen: black glass window with the live panel under it
    x, y = F(SCR[0], SCR[1])
    s.box((SCR[2], SCR[3], 0.6), (x, y, top + 0.32), m=s.mat('glass black', '#050505', 0.06, coat=1.0),
          bevel=0.8, name='window')
    smat, tex = screen_material(sequence=still_frame is None)
    if still_frame is not None:
        tex.image = bpy.data.images.load(os.path.join(UI_FRAMES, f'f{still_frame:05d}.png'))
    screen_plane(smat)

    # Limit rocker: an aluminium paddle over its two switches (PCB x 60 and 80),
    # the beeper between them; the steps printed in front
    x, y = P(70.0, 45.5)
    s.box((28, 8, 2.4), (x, y, top + 1.4), m='brushed', bevel=1.0, name='rocker')
    s.box((0.5, 5.5, 0.1), (x, y, top + 2.62), m='screen', bevel=0, name='rocker-split')
    s.text('–', 3.0, (x - 7, y, top + 2.62), m='pitch', mono=True)
    s.text('+', 3.0, (x + 7, y, top + 2.62), m='pitch', mono=True)
    x, y = F(59.5, 55.2)
    s.text('Limit', 1.6, (x, y, top + 0.62), align='LEFT')
    s.text('AUTO 1 2 5 10 25 A', 1.2, (x + 7, y, top + 0.62), mono=True, align='LEFT')

    # toggle with its status light round the bushing
    rmat = ring_material()
    tx, ty = F(TX, TY)
    s.status_ring(RING, 1.8, loc=(tx, ty, top + 0.65), m=rmat, depth=1.2, name='status-light')
    s.cyl(4.6, 0.9, (tx, ty, top + 0.95), m='steel', bevel=0.2, verts=6, name='nut')
    s.cyl(3.0, 3.4, (tx, ty, top + 3.0), m='steel', bevel=0.3, name='bushing')
    lever = bpy.data.objects.new('lever', None)
    bpy.context.collection.objects.link(lever)
    lever.location = (tx, ty, top + 4.4)
    L = 8.5                                 # clears the closed guard's top
    for p in (s.cyl(1.25, L, (0, 0, L / 2), m='aluminium', bevel=0.3, name='lever-bat'),
              s.sphere(1.7, (0, 0, L), m='aluminium', name='lever-tip')):
        p.parent = lever
    for lab, dy in (('On', -7.0), ('Off', 0.0), ('Bind', 7.0)):
        x, y = F(TX - GW / 2 - 1.6, TY + dy)
        s.text(lab, 1.8, (x, y, top + 0.62), align='RIGHT')

    # guard: translucent Ember polycarbonate, pivoting on a steel pin at its
    # base at the back; closed, its walls stand on the face and its top
    # covers the toggle
    hx, hy = F(TX, HY)
    hz = top + 1.6
    s.box((GW + 5, 4.5, 3.2), (hx, hy + 0.4, top + 1.6), m='anodised', bevel=0.6, name='hinge-block')
    s.cyl(1.1, GW + 6, (hx, hy, hz), m='steel', bevel=0.2, rot=(0, 90, 0), name='pin')
    guard = bpy.data.objects.new('guard', None)
    bpy.context.collection.objects.link(guard)
    guard.location = (hx, hy, hz)
    gm = guard_material()
    yc = -GL / 2 - 1.0
    for p in (s.box((GW, GL, 1.8), (0, yc, GH - 0.9), m=gm, bevel=0.6, name='guard-top'),
              s.box((1.8, GL, GH), (-GW / 2 + 0.9, yc, GH / 2), m=gm, bevel=0.6, name='guard-wall'),
              s.box((1.8, GL, GH), (GW / 2 - 0.9, yc, GH / 2), m=gm, bevel=0.6, name='guard-wall'),
              s.box((GW, 1.8, GH), (0, -GL - 0.1, GH / 2), m=gm, bevel=0.6, name='guard-lip')):
        p.parent = guard
    # an arrow on the face, beside the guard: lift
    x, y = F(TX - GW / 2 - 4.0, TY + 20.0)
    s.arrow(5, (x, y, top + 0.62), rot_z=90, shaft=0.35, head=0.9)
    s.text('Lift', 1.8, (x, y - 2.6, top + 0.62))

    # face printing: in and out
    x, y = F(4.0, 32.6)
    s.text('Battery', 1.9, (x, y, top + 0.62), align='LEFT')
    s.arrow(8, (x + 1, y - 2.6, top + 0.62), shaft=0.35, head=0.9)
    x, y = F(W - 4.0, 45.0)
    s.text('Drone', 1.9, (x, y, top + 0.62), align='RIGHT')
    s.arrow(8, (x - 8, y - 2.6, top + 0.62), shaft=0.35, head=0.9)
    # the brand, placed like Apple places its mark: never on the working
    # face, never round a control.  The mark alone, centred on the front
    # wall that faces the user, tone on tone (gloss black on soft-touch
    # black), with far more than a quarter of its width clear round it.
    # The lockup and the product name sit on the underside.
    s.beacon_ring(MARK_R, 0.06, loc=(0, -D / 2 - 0.02, H / 2), rot=(90, 0, 0),
                  m=s.mat('gloss pitch', '#0E0C09', 0.08, coat=1.0), name='mark-front')
    s.lockup(30.0, (0, 4, -0.03), rot=(180, 0, 0), m=s.mat('deboss', '#141210', 0.5), name='lockup-under')

    # connectors: male XT60 + XT30 through the battery end wall (PCB J1, J2);
    # the drone's leads (soldered to the PCB's pads J3, J4) out of the far
    # end, female plugs on them; USB-C through the back wall (PCB J8)
    x, y = P(-WALL, 20.0)
    s.xt60((x - 2, y, PCB_Z + 4.1), male=True, name='in60')
    x, y = P(-WALL, 34.8)
    s.xt30((x - 1.5, y, PCB_Z + 2.55), male=True, name='in30')
    x, y = P(94 + WALL, 18.2)                    # + at PCB y 15.2 (red), - at 21.2
    s.leads((x - 3, y, 7.5), (x + 52, y - 2, 4.4), sep=-6.0, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 2, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = P(94 + WALL, 33.7)                    # + at PCB y 36.0 (red), - at 31.4
    s.leads((x - 3, y, 6.5), (x + 32, y - 10, 2.8), sep=4.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 10, 2.6), rot=(0, 0, 180), male=False, name='out30')
    s.usb_c((P(66.0, 0)[0], D / 2 + 0.1, PCB_Z + 1.6), rot=(0, 0, -90))
    return dict(guard=guard, lever=lever, ring=rmat)


# ---------------------------------------------------------------- the story
# seconds, matching ui/screens.py TIMELINE
T0 = 1.5                                   # S00 start-up screen
T_LIFT1, T_FLICK1, T_LIVE, T_WARN, T_CLOSE1 = (T0 + t for t in (2.0, 4.2, 8.0, 11.5, 13.9))
T_LIFT2, T_FLICK2, T_ABORT, T_CLOSE2, T_END = (T0 + t for t in (16.1, 17.1, 17.9, 20.5, 22.0))

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
    h = build(still_frame=int((T0 + 9.5) * FPS))   # a Live screen
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


def render_showcase():
    """Three finished stills of the product as it ships (showcase-*.png):
    armed with the guard open, the back with its five balance sockets, and
    closed on the bench with the USB-C port in the front wall."""
    shots = [
        ('showcase-armed', OPEN, LEVER_ON, (s.GREEN, 8.0), int((T0 + 9.5) * FPS), 26, -30),
        ('showcase-back', 0.0, LEVER_OFF, (s.EMBER, 0.6), int((T0 + 0.8) * FPS), 22, 148),
        ('showcase-closed', 0.0, LEVER_OFF, (s.EMBER, 0.6), int((T0 + 0.8) * FPS), 18, -12),
    ]
    for name, guard, lever, ring, frame, el, az in shots:
        sc = s.reset()
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1200
        sc.cycles.samples = 64
        h = build(still_frame=frame)
        key_guard(h['guard'], 0, guard)
        key_lever(h['lever'], 0, lever)
        key_ring(h['ring'], 0, *ring)
        cam, pivot = s.stage(elevation=el, azimuth=az)
        cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
        sc.render.filepath = os.path.join(HERE, name + '.png')
        bpy.ops.render.render(write_still=True)
        print(sc.render.filepath)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'still'
    if what == 'showcase':
        render_showcase()
    elif what == 'still':
        render_still()
    else:
        render_video(quick='--quick' in sys.argv)
