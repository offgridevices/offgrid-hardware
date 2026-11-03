"""10 Arm: an aircraft-style guarded toggle. Lift the smoked guard to arm,
flick the toggle away from you to power, pull it toward you to bind.
96 x 56 x 18 mm body; the guard is shown open."""
import math

VIEW = dict(elevation=30, azimuth=-32)

W, D, H, R = 96.0, 56.0, 18.0, 9.0
TXF, TYF = 72.0, 31.0          # toggle centre (face coords, y toward the user)
RB = 13.5
HYF = 13.0                     # hinge line (face y)
GL, GW, GH = 33.0, 22.0, 11.0  # guard length, width, wall height
OPEN = 104.0                   # guard open angle


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
    rbox(s, W, D, H, R, (0, 0, H / 2), 'pitch_soft', edge=1.4, name='body')

    # screen (1.3" OLED under glass)
    x, y = B(27, 21)
    s.box((38, 24, 0.6), (x, y, top + 0.2), m=s.mat('matte glass', '#050505', 0.35), bevel=0.6, name='window')
    s.text('0.42A', 5.0, (x - 15, y - 1.5, top + 0.52), m='white_led', mono=True, align='LEFT', name='amps')
    s.text('On, safe', 1.8, (x - 15, y + 6.8, top + 0.52), m='green', align='LEFT', name='state')
    s.text('16.8V 4S', 1.4, (x + 15, y + 6.8, top + 0.52), m='screen_txt', mono=True, align='RIGHT', name='batt')
    s.text('LIMIT AUTO 2.0A  DRONE 3', 1.2, (x - 15, y - 8.4, top + 0.52), m='screen_txt', mono=True, align='LEFT', name='lim')
    # limit rocker: aluminium paddle on two tact switches
    x, y = B(27, 46.5)
    s.box((38, 9, 2.4), (x, y, top + 1.2), m='anodised', bevel=1.0, name='rocker')
    s.box((0.5, 6, 0.1), (x, y, top + 2.42), m='screen', bevel=0, name='rocker-split')
    s.text('-', 3.0, (x - 9.5, y, top + 2.42), m='bone', mono=True)
    s.text('+', 3.0, (x + 9.5, y, top + 2.42), m='bone', mono=True)
    x, y = B(8, 54.0)
    s.text('AUTO 1A 2A 5A 10A 20A  20A: PROPS OFF', 1.15, (x, y, top + 0.02), mono=True, align='LEFT', m='bone')

    # toggle: Beacon Ring round the bushing, metal lever leaning away (On)
    tx, ty = B(TXF, TYF)
    s.status_ring(RB, 1.6, loc=(tx, ty, top + 0.15), m='green')
    s.cyl(4.6, 0.9, (tx, ty, top + 0.45), m='steel', bevel=0.2, verts=6, name='nut')
    s.cyl(3.0, 3.4, (tx, ty, top + 2.6), m='steel', bevel=0.3, name='bushing')
    L = 12.0
    a = math.radians(22)
    s.cyl(1.25, L, (tx, ty + math.sin(a) * L / 2, top + 4.0 + math.cos(a) * L / 2), m='aluminium',
          bevel=0.3, rot=(-22, 0, 0), name='lever')
    s.sphere(1.6, (tx, ty + math.sin(a) * L, top + 4.0 + math.cos(a) * L), m='aluminium', name='lever-tip')
    for lab, dy in (('On', -6.0), ('Off', 0.0), ('Bind', 6.0)):
        x, y = B(TXF + 6.6, TYF + dy)
        s.text(lab, 1.8, (x, y, top + 0.02), align='LEFT')
    x, y = B(TXF - 6.8, TYF + 4.0)
    s.arrow(5, (x, y - 2.0, top + 0.02), rot_z=-90, shaft=0.3, head=0.8)

    # guard: smoked polycarbonate U-cover, hinged on a steel pin, shown open
    hx, hy = B(TXF, HYF)
    hz = top + 2.2
    s.box((GW + 4, 4.5, 2.4), (hx, hy + 0.8, top + 1.2), m='anodised', bevel=0.6, name='hinge-block')
    s.cyl(1.1, GW + 5, (hx, hy, hz), m='steel', bevel=0.2, rot=(0, 90, 0), name='pin')
    piv = bpy.data.objects.new('guard', None)
    bpy.context.collection.objects.link(piv)
    piv.location = (hx, hy, hz)
    parts = [s.box((GW, GL, 1.6), (0, -GL / 2 - 1.0, 0), m='smoked', bevel=0.5, name='guard-top'),
             s.box((1.6, GL, GH), (-GW / 2 + 0.8, -GL / 2 - 1.0, -GH / 2 + 0.8), m='smoked', bevel=0.5, name='guard-wall'),
             s.box((1.6, GL, GH), (GW / 2 - 0.8, -GL / 2 - 1.0, -GH / 2 + 0.8), m='smoked', bevel=0.5, name='guard-wall'),
             s.box((GW, 1.6, GH), (0, -GL - 0.2, -GH / 2 + 0.8), m='smoked', bevel=0.5, name='guard-lip'),
             s.cyl(1.6, 1.0, (0, -GL + 2.0, -0.4), m='steel', bevel=0.2, name='guard-magnet')]
    for p in parts:
        p.parent = piv
    piv.rotation_euler = (math.radians(-OPEN), 0, 0)

    # face printing
    x, y = B(3.5, 5.6)
    s.text('Battery', 1.9, (x, y, top + 0.02), align='LEFT')
    s.arrow(7, (x + 3.5, y - 2.4, top + 0.02), shaft=0.3, head=0.8)
    x, y = B(W - 3.5, D - 5.6)
    s.text('Drone', 1.9, (x, y, top + 0.02), align='RIGHT')
    s.arrow(7, (x - 3.5, y - 2.2, top + 0.02), shaft=0.3, head=0.8)
    x, y = B(TXF - 12, D - 3.2)
    s.lockup(10.2, (x + 3.67, y + 0.4, top + 0.05), m='bone')

    # connectors
    x, y = B(0, 20.75)
    s.xt60((x - 2, y, 9), male=True, name='in60')
    x, y = B(0, 41)
    s.xt30((x - 1.5, y, 8), male=True, name='in30')
    x, y = B(W, 22)
    s.leads((x - 3, y, 8), (x + 52, y - 2, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 2, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = B(W, 42)
    s.leads((x - 3, y, 7), (x + 32, y - 12, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 12, 2.6), rot=(0, 0, 180), male=False, name='out30')
    s.usb_c((B(TXF - 18, 0)[0], D / 2 + 0.1, 9), rot=(0, 0, 90))
