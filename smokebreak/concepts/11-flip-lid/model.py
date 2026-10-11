"""11 Flip: a lighter-style flip lid. Open it and it wakes, press Power,
snap it shut and the drone is off. Limit is a knurled flint wheel.
84 x 52 x 16 mm body + 6.5 mm brushed aluminium lid (shown open)."""
import math

VIEW = dict(elevation=34, azimuth=-24, lens=62)

W, D, H, R = 84.0, 52.0, 16.0, 7.0
LT = 6.5
OPEN = 102.0


def B(x, y):
    return (x - W / 2, D / 2 - y)


def rbox(s, w, d, h, r, loc, m, edge=1.2, name='rbox'):
    import bpy
    import bmesh
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    vert = [e for e in bm.edges
            if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6]
    bmesh.ops.bevel(bm, geom=vert, offset=r, segments=10, affect='EDGES', profile=0.5)
    bm.to_mesh(o.data)
    bm.free()
    return s._finish(o, m, bevel=edge, segments=4)


def build(s):
    import bpy
    top = H
    rbox(s, W, D, H, R, (0, 0, H / 2), 'pitch_soft', edge=1.2, name='body')
    graphite = s.mat('graphite brushed Al', '#6A665E', 0.32, 1.0)

    # screen
    x, y = B(24, 18.5)
    s.box((34, 21, 0.6), (x, y, top + 0.2), m='screen', bevel=0.6, name='window')
    s.text('0.42A', 4.6, (x - 13.5, y - 1.2, top + 0.52), m='white_led', mono=True, align='LEFT', name='amps')
    s.text('On, safe', 1.7, (x - 13.5, y + 6.2, top + 0.52), m='green', align='LEFT', name='state')
    s.text('16.8V 4S', 1.3, (x + 13.5, y + 6.2, top + 0.52), m='screen_txt', mono=True, align='RIGHT', name='batt')
    # Power in the Beacon Ring
    x, y = B(63, 19.5)
    s.status_ring(10.5, 1.6, loc=(x, y, top + 0.15), m='green')
    s.cyl(6.6, 2.0, (x, y, top + 1.0), m='cap', bevel=0.6, name='power')
    s.text('Power', 2.0, (x, y, top + 2.02))
    # Bind key
    x, y = B(11, 41)
    s.cyl(3.2, 1.5, (x, y, top + 0.75), m='cap', bevel=0.4, name='bind')
    s.text('Bind', 1.9, (x + 4.6, y, top + 0.02), align='LEFT')
    # Limit: knurled steel flint wheel, axis along X, 4.4 mm proud of the face
    WR, WW = 6.5, 8.0
    x, y = B(47, 41)
    zc = top - (WR - 4.4)
    s.box((WW + 2, 2 * math.sqrt(WR ** 2 - (WR - 4.4) ** 2) + 1.2, 0.4), (x, y, top + 0.0), m='screen', bevel=0.2, name='slot')
    s.cyl(WR - 0.4, WW, (x, y, zc), m='steel', bevel=0.3, rot=(0, 90, 0), name='wheel')
    for i in range(40):
        a = 2 * math.pi * i / 40
        s.box((WW, 0.7, 0.7), (x, y + (WR - 0.35) * math.cos(a), zc + (WR - 0.35) * math.sin(a)),
              m='steel', bevel=0.1, rot=(math.degrees(a) + 45, 0, 0), name='tooth')
    x, y = B(55.5, 39.5)
    s.text('Limit: roll the wheel', 1.9, (x, y, top + 0.02), align='LEFT')
    x, y = B(55.5, 43.6)
    s.text('AUTO 1A 2A 5A 10A 20A', 1.25, (x, y, top + 0.02), mono=True, align='LEFT')
    # ends
    x, y = B(4, D - 3.6)
    s.text('Battery', 1.8, (x, y, top + 0.02), align='LEFT')
    x, y = B(W - 4, D - 3.6)
    s.text('Drone', 1.8, (x, y, top + 0.02), align='RIGHT')

    # hinge knuckles on the back edge
    hy = D / 2 - 0.5
    for x0, x1 in ((6, 20), (34, 50), (64, 78)):
        cx = (x0 + x1) / 2 - W / 2
        s.cyl(1.9, x1 - x0, (cx, hy, top + 0.4), m=graphite, bevel=0.3, rot=(0, 90, 0), name='knuckle')
    s.cyl(0.8, W - 10, (0, hy, top + 0.4), m='steel', bevel=0.1, rot=(0, 90, 0), name='pin')

    # the lid, open; children built as if closed, relative to the hinge line
    piv = bpy.data.objects.new('lid', None)
    bpy.context.collection.objects.link(piv)
    piv.location = (0, hy, top + 0.4)
    parts = [rbox(s, W, D, LT, R, (0, -D / 2, LT / 2 + 0.2), graphite, edge=1.0, name='lid'),
             s.box((W - 4, D - 4, 0.2), (0, -D / 2, 0.15), m='pitch', bevel=0.3, name='lid-liner')]
    # printing inside the lid (faces -Z while closed, the user once open)
    inside = [('1 Battery in   →   2 Drone in   →   3 Power', 2.4, -40, False),
              ('Close the lid: drone off, instantly.', 1.8, -32, False),
              ('Bench use only. Do not fly with this attached.', 1.6, -27.5, False),
              ('OffGrid', 2.4, -13, False)]
    for txt, sz, yy, mono in inside:
        t = s.text(txt, sz, (0, yy, 0.02), rot=(180, 0, 0), mono=mono, name='lid-text')
        parts.append(t)
    # engraved mark on the outside
    br = s.beacon_ring(8.5, 1.8, loc=(0, -D / 2 + 2, LT + 0.25), m='pitch', name='lid-mark')
    parts.append(br)
    parts.append(s.cyl(1.6, 0.8, (0, -D + 4, 2.0), m='steel', bevel=0.1, name='lid-magnet'))
    for p in parts:
        p.parent = piv
    piv.rotation_euler = (math.radians(-OPEN), 0, 0)

    # connectors
    x, y = B(0, 19.75)
    s.xt60((x - 2, y, 8.5), male=True, name='in60')
    x, y = B(0, 38)
    s.xt30((x - 1.5, y, 7.5), male=True, name='in30')
    x, y = B(W, 18)
    s.leads((x - 3, y, 8), (x + 52, y - 2, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 2, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = B(W, 38)
    s.leads((x - 3, y, 7), (x + 32, y - 12, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 12, 2.6), rot=(0, 0, 180), male=False, name='out30')
    # USB-C on the front edge (the hinge takes the back)
    s.usb_c((10, -D / 2 - 0.1, 8), rot=(0, 0, 90))
