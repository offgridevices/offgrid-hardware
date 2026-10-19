"""13 Bench Clock - a machined wedge that faces you like a desk clock.

Face toward -Y (the viewer), battery input at the back-left (-X), drone leads
leave the back-right (+X), Power is the full-width bar on top.
"""
import math

VIEW = dict(elevation=24, azimuth=-32)

W, D, H, LIP, FY = 84.0, 52.0, 50.0, 10.0, 20.0   # width, depth, height, front lip, face run


def prism_x(s, profile, x0, x1, m, bevel, name):
    """Extrude a convex (y, z) profile along X into a closed mesh."""
    import bpy
    n = len(profile)
    verts = [(x0, y, z) for y, z in profile] + [(x1, y, z) for y, z in profile]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.validate()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    # make the normals point outward whatever the profile winding
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return s._finish(o, m, bevel)


def group(s, loc, rot, name):
    import bpy
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    return e


def twin(s, pts, sep=5.0, r=2.1, name='lead'):
    """A red + black silicone pair along pts, side by side in X."""
    out = []
    for dx, m in ((-sep / 2, 'red_wire'), (sep / 2, 'black_wire')):
        out.append(s.tube_path([(x + dx, y, z) for x, y, z in pts], r, m=m, name=name))
    return out


def build(s):
    y0 = -D / 2                       # front at y = -26, back at +26
    prof = [(y0, 0), (y0, LIP), (y0 + FY, H), (y0 + D, H), (y0 + D, 0)]
    prism_x(s, prof, -W / 2, W / 2, 'anodised', 1.6, 'body')
    s.box((W - 2, D - 2, 1.0), (0, 0, 0.5), m='rubber', bevel=0.4, name='foot')

    # --- the sloped glass face: a group whose local XY is the face plane
    tilt = math.degrees(math.atan2(FY, H - LIP))           # 26.6 deg from vertical
    ang = 90 - tilt                                         # 63.4 deg from horizontal
    fc = (0, y0 + FY / 2, (LIP + H) / 2)
    face = group(s, fc, (ang, 0, 0), 'face')
    parts = []
    parts.append(s.box((W - 6, 40.0, 0.8), (0, 0, 0.45), m='screen', bevel=0.6, name='glass'))
    parts.append(s.screen(43, 22, ('16.8V  4S', 'Ready'), loc=(-15, 6, 0.95)))
    parts.append(s.status_ring(8.0, 2.2, loc=(24, 5, 1.2), m='ember'))
    for x, lab in ((10, 'Bind'), (26, 'Limit')):
        parts.append(s.cyl(3.8, 1.8, (x, -14, 1.5), m='cap', bevel=0.5, name=lab))
        parts.append(s.text(lab, 1.7, (x + 5, -14, 0.9), align='LEFT', name=lab + '-t'))
    parts.append(s.text('1 Battery  →  2 Drone  →  3 Tap bar', 1.5, (-15, -14, 0.9), name='steps'))
    for p in parts:
        p.parent = face

    # --- Power bar across the top, with an Ember light slit under it
    bar_y = y0 + FY + 9
    s.box((W - 14, 13, 0.6), (0, bar_y, H + 0.2), m='ember', bevel=0.2, name='slit')
    s.box((W - 16, 11.5, 4.2), (0, bar_y, H + 2.4), m='aluminium', bevel=1.4, name='power-bar')
    s.text('Power', 3.4, (0, bar_y, H + 4.52), m='pitch', name='bar-t')

    # --- back panel: battery in (male, panel-mount) left, USB-C, drone leads right
    yb = y0 + D
    s.xt60((-26, yb - 3, 15), rot=(0, 0, -90), male=True, name='in60')
    s.xt30((-9, yb - 1, 13), rot=(0, 0, -90), male=True, name='in30')
    s.box((1.4, 2.5, 14), (-17, yb + 1.0, 15), m='anodised', bevel=0.3, name='rib')
    s.usb_c((4, yb + 0.3, 14), rot=(0, 0, -90))
    for x in (18, 31):
        s.cyl(4.0, 3.0, (x, yb + 1.2, 14), m='rubber', bevel=0.6, rot=(90, 0, 0), name='grommet')
    s.text('Battery', 2.2, (-20, yb + 0.05, 27), rot=(90, 0, 180), name='t-batt')
    s.text('Drone', 2.2, (24, yb + 0.05, 27), rot=(90, 0, 180), name='t-drone')
    s.text('USB-C', 1.6, (4, yb + 0.05, 20), rot=(90, 0, 180), name='t-usb')

    # drone leads curl from the back round to the right, female plugs on the bench
    twin(s, [(18, yb + 2, 14), (19, yb + 16, 8), (34, yb + 26, 3), (62, yb + 12, 3), (72, 8, 4.1)], name='lead60')
    s.xt60((72, 2, 4.1), rot=(0, 0, 90), male=False, name='out60')
    twin(s, [(31, yb + 2, 14), (34, yb + 12, 6), (52, yb + 18, 2.6), (84, yb + 10, 2.6), (92, yb - 6, 2.6)],
         sep=3.6, r=1.5, name='lead30')
    s.xt30((92, yb - 12, 2.6), rot=(0, 0, 90), male=False, name='out30')
    # battery lead runs off behind the left
    twin(s, [(-26, yb + 9, 15), (-27, yb + 20, 8), (-40, yb + 34, 2.2), (-62, yb + 40, 2.2)], name='batt-lead')
    s.xt60((-26, yb + 12, 15), rot=(0, 0, 90), male=False, name='batt-plug')
