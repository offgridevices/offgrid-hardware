"""18 - Ignition: a desk-instrument wedge; power is a key you turn, and the key
carries the drone's history. Key shown turned to On (ring green)."""
import math

VIEW = dict(elevation=30, azimuth=-30)

W, D, HB, HF = 92.0, 64.0, 26.0, 13.0
A = math.atan((HB - HF) / D)          # slope angle
SL = math.hypot(D, HB - HF)
N = (0.0, -math.sin(A), math.cos(A))  # face normal (toward the user and up)


def P(u, v, h=0.0):
    """Point on the sloped face: u along X from the left end, v down the slope
    from the back edge (drawing coords), h along the face normal."""
    return (u - W / 2 + N[0] * h,
            D / 2 - v * math.cos(A) + N[1] * h,
            HB - v * math.sin(A) + N[2] * h)


def _fillet(poly, rs, seg=6):
    out = []
    n = len(poly)
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        r = rs[i]
        v1 = (p0[0] - p1[0], p0[1] - p1[1]); v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        u1 = (v1[0] / l1, v1[1] / l1); u2 = (v2[0] / l2, v2[1] / l2)
        ang = math.acos(max(-1, min(1, u1[0] * u2[0] + u1[1] * u2[1])))
        t = r / math.tan(ang / 2)
        bis = (u1[0] + u2[0], u1[1] + u2[1]); bl = math.hypot(*bis); bis = (bis[0] / bl, bis[1] / bl)
        c = (p1[0] + bis[0] * r / math.sin(ang / 2), p1[1] + bis[1] * r / math.sin(ang / 2))
        a = (p1[0] + u1[0] * t, p1[1] + u1[1] * t); b = (p1[0] + u2[0] * t, p1[1] + u2[1] * t)
        a0 = math.atan2(a[1] - c[1], a[0] - c[0]); a1 = math.atan2(b[1] - c[1], b[0] - c[0])
        da = a1 - a0
        while da > math.pi: da -= 2 * math.pi
        while da < -math.pi: da += 2 * math.pi
        for k in range(seg + 1):
            aa = a0 + da * k / seg
            out.append((c[0] + r * math.cos(aa), c[1] + r * math.sin(aa)))
    return out


def wedge(s, m):
    import bpy
    prof = _fillet([(-D / 2, 0), (D / 2, 0), (D / 2, HB), (-D / 2, HF)], [3, 3, 4, 4])   # (Y, Z)
    n = len(prof)
    verts = [(-W / 2, y, z) for y, z in prof] + [(W / 2, y, z) for y, z in prof]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    me = bpy.data.meshes.new('wedge')
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new('wedge', me)
    bpy.context.collection.objects.link(o)
    bv = o.modifiers.new('bevel', 'BEVEL')
    bv.width = 2.2
    bv.segments = 5
    bv.limit_method = 'ANGLE'
    bv.angle_limit = math.radians(60)
    s.assign(o, m)
    for p in me.polygons:
        p.use_smooth = False
    return o


def build(s):
    import bpy
    rot = (math.degrees(A), 0, 0)
    wedge(s, 'anodised')
    glass = s.mat('black glass', '#0B0A09', 0.22, coat=0.3)
    s.box((W - 3, SL - 3, 0.6), P(W / 2, SL / 2, 0.05), m=glass, bevel=0.3, rot=rot, name='face-glass')

    # screen
    s.screen(36, 20, ('ON 0.42A', 'DRONE 3 KEY'), loc=P(27, 19.5, 0.45), rot=rot, name='oled')

    def txt(t, size, u, v, align='LEFT', mono=False, m='bone'):
        s.text(t, size, P(u, v, 0.4), rot=rot, m=m, mono=mono, align=align, depth=0.02)

    # Limit: button + six lit dots
    s.cyl(3.6, 1.6, P(13, 46, 0.9), m='cap', bevel=0.5, rot=rot, name='limit')
    txt('Limit', 2.4, 20.5, 41.5)
    vals = [('AUTO', 2.6), ('1', 8.4), ('2', 12.4), ('5', 16.4), ('10', 20.8), ('20A', 26.2)]
    for i, (v, xx) in enumerate(vals):
        txt(v, 1.6, 20.5 + xx, 45.8, align='CENTER', mono=True)
        s.cyl(0.7, 0.3, P(20.5 + xx, 49.3, 0.45), m='white_led' if i == 0 else 'cap', bevel=0, rot=rot,
              verts=24, name='dot')
    txt('20A: props off', 1.6, 20.5, 53.6)

    # ignition: Beacon Ring + barrel + key
    c = (63.0, 30.0)
    s.status_ring(14.5, 1.9, loc=P(c[0], c[1], 0.45), rot=rot, m='green')
    for lab, a in (('Off', 0), ('On', 60), ('Bind', 110)):
        r = 19.8
        th = math.radians(a - 90)
        u = c[0] + r * math.cos(th) - (0 if a == 0 else 1.2)
        v = c[1] + r * math.sin(th) + (-0.6 if a == 0 else 1.2)
        txt(lab, 2.2, u, v, align='CENTER' if a == 0 else 'LEFT')
    s.cyl(11.0, 3.2, P(c[0], c[1], 1.6), m='brushed', bevel=0.8, rot=rot, name='barrel')
    hub = bpy.data.objects.new('key-hub', None)
    bpy.context.collection.objects.link(hub)
    hub.location = P(c[0], c[1], 3.2)
    hub.rotation_euler = (A, 0, 0)
    key_parts = []
    keymat = s.mat('key bone anodised', '#E9E3D5', 0.4, 0.0)
    stem = s.box((4.4, 7, 2.6), (0, 0, 1.3), m='brushed', bevel=0.4, name='key-stem')
    paddle = s.box((4.8, 26, 20), (0, 0, 2.5 + 10), m=keymat, bevel=2.2, name='key-paddle')
    hole = s.cyl(2.3, 5.4, (0, 7.5, 2.5 + 15.5), m=s.mat('hole', '#0B0A09', 0.6), bevel=0.2, rot=(0, 90, 0), name='key-hole')
    num = s.text('3', 7, (2.45, -5, 13.5), rot=(90, 0, 90), m='pitch', mono=True, depth=0.05, name='key-num')
    tag = s.text('Drone', 2.2, (2.45, -5, 8.5), rot=(90, 0, 90), m='pitch', depth=0.05, name='key-tag')
    num2 = s.text('3', 7, (-2.45, 5, 13.5), rot=(90, 0, -90), m='pitch', mono=True, depth=0.05, name='key-num2')
    piv = bpy.data.objects.new('key-rot', None)
    bpy.context.collection.objects.link(piv)
    piv.parent = hub
    piv.rotation_euler = (0, 0, math.radians(-60))     # turned to On
    for p in (stem, paddle, hole, num, tag, num2):
        p.parent = piv

    # face print
    txt('Battery', 2.0, 5, SL - 4)
    txt('Drone', 2.0, W - 5, SL - 4, align='RIGHT')
    txt('OffGrid', 2.4, 48, SL - 4, align='CENTER')
    txt('Turn to On to check and power. Past On to bind.', 1.6, c[0], c[1] + 27.5, align='CENTER')

    # battery side: male XT60 + XT30 through the left end
    s.xt60((-W / 2 - 3, 6.25, 10.5), male=True, name='in60')
    s.xt30((-W / 2 - 2, -15.0, 7.5), male=True, name='in30')
    # drone side: leads + female plugs
    for y, z, plug, nm in ((8.0, 10.0, 'xt60', 'out60'), (-12.0, 7.0, 'xt30', 'out30')):
        s.cyl(3.4, 3.0, (W / 2 + 1.0, y, z), m='rubber', bevel=0.6, rot=(0, 90, 0), name=nm + '-grommet')
        end = (W / 2 + 46, y - 14, 4.4)
        s.leads((W / 2 + 2.4, y, z), end, sep=4.6, radius=1.9, sag=4, name=nm + '-lead')
        if plug == 'xt60':
            s.xt60((end[0] + 8, end[1], 4.1), rot=(0, 0, 180), male=False, name=nm)
        else:
            s.xt30((end[0] + 5, end[1], 2.6), rot=(0, 0, 180), male=False, name=nm)
    s.usb_c((10, D / 2 + 0.3, 12), rot=(0, 0, -90))

    # spare key lying on the bench (Drone 1, bone) for scale and story
    s.box((26, 20, 4.8), (-20, -D / 2 - 26, 2.4), m=s.mat('key grey', '#8C857A', 0.4, 0.6), bevel=2.2, name='spare-key')
    s.box((5, 14, 1.4), (-20, -D / 2 - 26 + 17, 0.7), m='copper', bevel=0.3, name='spare-blade')
    s.text('2', 6, (-24, -D / 2 - 27, 4.85), m='pitch', mono=True, depth=0.05)
