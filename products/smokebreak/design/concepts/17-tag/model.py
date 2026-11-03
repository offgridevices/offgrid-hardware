"""17 - Tag: an e-ink luggage tag. Aluminium unibody, glass face, 2.9" e-ink,
three soft-keys named by the screen, Beacon Ring around the hanging eyelet."""
import math

VIEW = dict(elevation=34, azimuth=-28)

W, D, T = 104.0, 76.0, 12.0          # body (2D drawing coords: x right, y toward user)


def _fillet(poly, rs, seg=8):
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


def B(x, y):
    """2D drawing coords -> Blender XY (centred, +Y away from the user)."""
    return (x - W / 2, D / 2 - y)


def prism(s, name, outer, h, z0, bevel, m, holes=()):
    import bpy
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.extrude = max(0.01, h / 2 - bevel)
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    for loop in [outer] + list(holes):
        sp = cu.splines.new('POLY')
        sp.points.add(len(loop) - 1)
        for p, (x, y) in zip(sp.points, loop):
            p.co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    o.location = (0, 0, z0 + h / 2)
    s.assign(o, m)
    return o


def build(s):
    outline = _fillet([(30, 0), (74, 0), (W, 18), (W, D), (0, D), (0, 18)], [7, 7, 6, 6, 6, 6])
    EYE = (52, 11.5)
    eye = [(EYE[0] + 3.6 * math.cos(a * math.pi / 24), EYE[1] + 3.6 * math.sin(a * math.pi / 24)) for a in range(48)]
    out_b = [B(*p) for p in outline]
    hole_b = [B(*p) for p in eye][::-1]
    prism(s, 'unibody', out_b, T - 0.8, 0, 1.6, 'anodised', holes=[hole_b])
    # glass face (slightly inset), black coated glass
    inset = _fillet([(30.8, 0.9), (73.2, 0.9), (W - 0.9, 18.4), (W - 0.9, D - 0.9), (0.9, D - 0.9), (0.9, 18.4)],
                    [6.2, 6.2, 5.2, 5.2, 5.2, 5.2])
    eye2 = [(EYE[0] + 4.4 * math.cos(a * math.pi / 24), EYE[1] + 4.4 * math.sin(a * math.pi / 24)) for a in range(48)]
    prism(s, 'glass', [B(*p) for p in inset], 0.8, T - 0.8, 0.25,
          s.mat('black glass', '#0B0A09', 0.22, coat=0.3), holes=[[B(*p) for p in eye2][::-1]])
    top = T + 0.02

    # e-ink window: 72 x 33 at (16, 24)
    cx, cy = B(16 + 36, 24 + 16.5)
    s.box((72, 33, 0.3), (cx, cy, top), m='eink', bevel=0.4, name='eink')
    t = top + 0.18
    def ink(txt, size, x, y, mono=False, align='LEFT'):
        bx, by = B(16 + x, 24 + y)
        s.text(txt, size, (bx, by, t), m='eink_txt', mono=mono, align=align, depth=0.02)
    ink('Last check · kept unplugged', 2.2, 3.2, 4.6)
    ink('Passed', 7.0, 3.2, 12.6)
    ink('DRONE 3', 2.9, 68.8, 12.6, mono=True, align='RIGHT')
    ink('0.42 A IDLE · 1000 µF · 4S', 2.3, 3.2, 21.0, mono=True)
    lx, ly = B(16, 24 + 25.4)
    s.box((72, 0.2, 0.05), (lx + 36, ly, t), m='eink_txt', bevel=0, name='rule')
    keys = [(27, 'Bind', 11), (52, 'Power', 15), (77, 'Limit 2A', 11)]
    for kx, lab, kw in keys:
        ink(lab, 2.3, kx - 16, 29.3, align='CENTER')
        # printed arrow from the window down to the key
        ax, ay = B(kx, 59.6)
        s.arrow(3.4, (ax, ay, top - 0.02), rot_z=-90, shaft=0.25, head=0.75)
        # aluminium key
        kx_b, ky_b = B(kx, 66)
        s.box((kw, 5.2, 1.6), (kx_b, ky_b, T + 0.5), m='aluminium', bevel=0.7, name='key-' + lab)

    # Beacon Ring around the eyelet (light pipe in the glass)
    ex, ey = B(*EYE)
    s.status_ring(7.6, 2.0, loc=(ex, ey, top + 0.1), m='ember')
    # face print
    def bone(txt, size, x, y, align='LEFT', mono=False, w=False):
        bx, by = B(x, y)
        s.text(txt, size, (bx, by, top), m='bone', align=align, mono=mono, depth=0.02)
    bone('Battery', 1.8, 5, D - 4.5)
    bone('Drone', 1.8, W - 5, D - 4.5, align='RIGHT')
    bone('OffGrid', 2.0, W - 5, 22.5, align='RIGHT')
    bone('1S-14S', 1.5, 5, 22.5, mono=True)

    # battery side: XT60 + XT30 male, panel mount through the left end
    bx60 = B(0, 26 + 7.75); bx30 = B(0, 52 + 5)
    s.xt60((-W / 2 - 2.0, bx60[1], T / 2), male=True, name='in60')
    s.xt30((-W / 2 - 1.5, bx30[1], T / 2 - 0.5), male=True, name='in30')
    # drone side: grommets + leads + female plugs on the bench
    for yy, plug, dist, nm in ((30, 'xt30', 34, 'out30'), (56, 'xt60', 46, 'out60')):
        gx, gy = B(W, yy)
        s.cyl(3.4, 3.0, (gx + 1.2, gy, T / 2), m='rubber', bevel=0.6, rot=(0, 90, 0), name=nm + '-grommet')
        end = (gx + dist, gy - 6, 4.4)
        s.leads((gx + 2.5, gy, T / 2), end, sep=4.6, radius=1.9, sag=4, name=nm + '-lead')
        if plug == 'xt60':
            s.xt60((end[0] + 8, end[1], 4.1), rot=(0, 0, 180), male=False, name=nm)
        else:
            s.xt30((end[0] + 5, end[1], 2.6), rot=(0, 0, 180), male=False, name=nm)
    # USB-C on the right shoulder facet
    s.usb_c((37 - 0.3, 29 - 0.2, T / 2 - 0.5), rot=(0, 0, 239))
    # rubber feet
    for fx, fy in ((10, 26), (W - 10, 26), (10, D - 8), (W - 10, D - 8)):
        bx_, by_ = B(fx, fy)
        s.cyl(3, 0.6, (bx_, by_, -0.1), m='rubber', bevel=0.2, name='foot')
