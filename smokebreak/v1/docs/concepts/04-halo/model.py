"""04 Halo - the product is the Beacon Ring: a machined C-shaped aluminium ring
(Ø96, band 24, 18 tall) open at 12 o'clock (+Y), with the Ø20 node standing in
the gap on a recessed bridge. The node is Power; the ring glows the status;
touch a printed number on the left arc for Limit; Bind is a button on the right
arc; the screen sits at 6 o'clock. Battery in at 9 o'clock (-X), drone out at 3."""
import math

VIEW = dict(elevation=38, azimuth=-24)

RC, BW, H = 36.0, 24.0, 18.0
RI, RO = RC - BW / 2, RC + BW / 2
GAP = 41.0
NR, NH = 10.0, 22.0
LIM = [('AUTO', 222), ('1', 239), ('2', 256), ('5', 273), ('10', 290), ('20', 307)]


def pol(r, a):
    """a: degrees clockwise from 12 o'clock (+Y)."""
    t = math.radians(a)
    return r * math.sin(t), r * math.cos(t)


def c_outline(r_in, r_out, a0, a1, n=96, tips=True):
    """Closed outline of an annular sector a0..a1 (clockwise) with round tips."""
    pts = [pol(r_out, a0 + (a1 - a0) * i / n) for i in range(n + 1)]
    rc, rw = (r_in + r_out) / 2, (r_out - r_in) / 2
    if tips:
        cx, cy = pol(rc, a1)
        for i in range(1, 16):          # tip cap at a1, from outer to inner
            u = math.radians(a1) + math.pi * i / 16
            pts.append((cx + rw * math.sin(u), cy + rw * math.cos(u)))
    pts += [pol(r_in, a1 - (a1 - a0) * i / n) for i in range(n + 1)]
    if tips:
        cx, cy = pol(rc, a0)
        for i in range(1, 16):
            u = math.radians(a0) + math.pi + math.pi * i / 16
            pts.append((cx + rw * math.sin(u), cy + rw * math.cos(u)))
    return pts


def prism(bpy, s, pts, z0, z1, m, bevel=1.0, name='prism'):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.extrude = (z1 - z0) / 2 - bevel
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, (x, y) in zip(sp.points, pts):
        p.co = (x, y, 0, 1)
    sp.use_cyclic_u = True
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    o.location = (0, 0, (z0 + z1) / 2)
    s.assign(o, m)
    return o


def build(s):
    import bpy
    # the ring (inset slightly so the curve bevel lands on the true outline)
    prism(bpy, s, c_outline(RI + 1, RO - 1, GAP, 360 - GAP), 0, H, 'anodised', bevel=1.0, name='ring')
    # recessed bridge under the node, and the node (Power)
    prism(bpy, s, c_outline(RC - 4, RC + 4, 360 - GAP - 6, 360 + GAP + 6, tips=False), 0, 4, 'pitch', bevel=0.4, name='bridge')
    s.cyl(NR, NH - 4, (0, RC, 4 + (NH - 4) / 2), m='anodised', bevel=1.2, name='node')
    s.torus(NR - 0.6, 0.7, (0, RC, NH + 0.1), m='ember', name='node-light')
    s.cyl(NR - 1.6, 1.6, (0, RC, NH + 0.4), m='brushed', bevel=0.6, name='power')
    s.text('Power', 2.2, (0, RC, NH + 1.25), m='pitch')
    # light channel along the inner edge of the top
    cu = bpy.data.curves.new('channel', 'CURVE')
    cu.dimensions = '3D'; cu.bevel_depth = 1.1; cu.bevel_resolution = 4; cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    n = 120
    sp.points.add(n)
    for i in range(n + 1):
        a = GAP + 4 + (360 - 2 * GAP - 8) * i / n
        x, y = pol(27.6, a)
        sp.points[i].co = (x, y, H - 0.5, 1)
    ch = bpy.data.objects.new('channel', cu)
    bpy.context.collection.objects.link(ch)
    s.assign(ch, 'ember')
    t = H + 0.02
    # screen at 6 o'clock
    s.box((30.6, 16.5, 0.6), (0, -38, H + 0.2), m=s.mat('ips glass', '#060606', 0.45), bevel=0.4, name='screen')
    ips = s.mat('ips text', s.BONE, 0.5, emit=s.BONE, strength=1.0)
    s.text('16.8V 4S', 4.0, (0, -35.2, H + 0.55), m=ips, mono=True)
    s.text('Press the dot to power on', 1.7, (0, -41.6, H + 0.55),
           m=s.mat('ips ember', s.EMBER, 0.5, emit=s.EMBER, strength=1.2))
    # Limit: touch a number on the left arc
    for i, (lab, a) in enumerate(LIM):
        x, y = pol(33.0, a)
        s.cyl(0.8 if i else 1.0, 0.1, (x, y, t), m='white_led' if i == 0 else 'cap', bevel=0, verts=24, name='dot')
        x, y = pol(40.5, a)
        s.text(lab, 2.2, (x, y, t), m='ember' if lab == '20' else 'bone', mono=True)
    x, y = pol(37.5, 323)
    s.text('Limit:', 1.8, (x - 1.5, y - 2.4, t))
    s.text('touch one', 1.5, (x - 1.5, y - 4.7, t))
    # Bind on the right arc
    x, y = pol(37.0, 58)
    s.cyl(3.2, 1.4, (x, y, H + 0.6), m='brushed', bevel=0.5, name='bind')
    s.text('Bind', 1.9, (x, y - 6.0, t))
    s.text('Drone', 2.0, (38.5, -6.0, t))
    s.arrow(10, (39, -9.0, t), rot_z=0)
    # battery: XT60 over XT30 (male) on the outer wall at 9 o'clock
    s.xt60((-RO - 4 + 8, 0, 12.7), male=True, name='in60')
    s.xt30((-RO - 3 + 5, 0, 4.3), male=True, name='in30')
    # 'Battery' printed on the wall just behind the connectors
    bx, by = pol(RO + 0.05, 287)
    s.text('Battery', 2.0, (bx, by, 12.7), rot=(90, 0, -107))
    # USB-C on the outer wall at 5 o'clock
    ux, uy = pol(RO, 150)
    s.usb_c((ux, uy, 9), rot=(0, 0, 120))
    # drone leads from 3 o'clock, onto the bench toward the front
    for dy, m in ((-2.0, 'red_wire'), (2.0, 'black_wire')):
        s.tube_path([(RO - 2, -4 + dy, 10), (RO + 18, -4 + dy, 10), (RO + 22, -28 + dy, 2.0), (RO + 12, -56 + dy, 1.9)],
                    1.8, m=m, name='lead60')
    s.xt60((RO + 12, -56 - 8 - 1.5, 4.1), rot=(0, 0, 90), male=False, name='out60')
    for dy, m in ((-1.4, 'red_wire'), (1.4, 'black_wire')):
        s.tube_path([(RO - 2, 6 + dy, 6), (RO + 26, 6 + dy, 6), (RO + 36, -12 + dy, 1.5), (RO + 34, -32 + dy, 1.4)],
                    1.3, m=m, name='lead30')
    s.xt30((RO + 34, -32 - 5 - 1.4, 2.6), rot=(0, 0, 90), male=False, name='out30')
