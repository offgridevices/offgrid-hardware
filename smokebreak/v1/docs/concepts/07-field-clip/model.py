"""07 Field clip: a rugged 96 x 54 x 19 mm tag with a carabiner loop at the
battery end. Battery males on the front flank; the 12 cm drone tails are shown
stowed: they loop round and park in the device's own inputs."""
import math

VIEW = dict(elevation=32, azimuth=-32)

L, W, H = 96.0, 54.0, 19.0


def loop_curve(s, pts, radius, m, name, cyclic=True):
    import bpy
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, xyz in zip(sp.points, pts):
        p.co = (*xyz, 1)
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    s.assign(o, m)
    return o


def build(s):
    s.box((L, W, H), (0, 0, H / 2), m='anodised', bevel=6.0, name='shell')
    s.box((L - 7, W - 7, 0.6), (0, 0, H - 0.05), m='pcb', bevel=4.0, name='face')
    top = H + 0.3

    def B(x, y):
        return (x - L / 2, W / 2 - y)

    # sunlight-readable colour reflective LCD
    x, y = B(23.75, 22.5)
    s.box((29, 29, 0.8), (x, y, top - 0.2), m='screen', bevel=0.6, name='lcd-bezel')
    s.box((26, 26, 0.5), (x, y, top + 0.1), m='eink', bevel=0.3, name='lcd')
    s.text('ON', 3.4, (x - 10.5, y + 8.0, top + 0.4), m=s.mat('mip green', '#1f7a2a', 0.7), mono=True, align='LEFT')
    s.text('0.42A', 3.4, (x - 10.5, y + 2.5, top + 0.4), m='eink_txt', mono=True, align='LEFT')
    s.text('16.8V 4S', 1.8, (x - 10.5, y - 3.0, top + 0.4), m='eink_txt', mono=True, align='LEFT')
    s.text('AUTO 2.0A', 1.4, (x - 10.5, y - 7.5, top + 0.4), m='eink_txt', mono=True, align='LEFT')
    # Power: Beacon Ring round a big glove-friendly cap
    x, y = B(55, 21.5)
    s.status_ring(8.1, 2.6, loc=(x, y, top), m='green')
    s.cyl(5.2, 2.8, (x, y, top + 0.8), m='cap', bevel=0.8, name='power')
    x, y = B(55, 39.4)
    s.text('Power', 2.0, (x, y, top))
    # Limit and Bind pill keys
    for ly, lab in ((13.75, 'Limit'), (30.75, 'Bind')):
        x, y = B(80.5, ly)
        s.box((19, 8.5, 2.0), (x, y, top + 0.6), m='cap', bevel=0.9, name=lab)
        s.text(lab, 2.0, (x, y, top + 1.62))
    x, y = B(80.5, 22.0)
    s.text('AUTO 1 2 5 10 20A', 1.15, (x, y, top), mono=True)
    x, y = B(80.5, 38.8)
    s.text('Puts receiver in bind', 1.15, (x, y, top))
    x, y = B(48, 47.4)
    s.text('1 Battery in  →  2 Drone in  →  3 Press Power', 1.8, (x - 6, y, top))

    # front flank: battery males (rib between), USB-C flap
    s.xt60((-28.25, -W / 2 + 4, 7.9), rot=(0, 0, 90), male=True, name='in60')
    s.xt30((-11.0, -W / 2 + 4, 7.9), rot=(0, 0, 90), male=True, name='in30')
    s.box((1.6, 4, 10), (-19.0, -W / 2 - 1.2, 7.9), m='anodised', bevel=0.5, name='rib')
    s.text('Battery in', 1.6, (-20, -W / 2 - 0.05, 15.6), rot=(90, 0, 0), m='aluminium')
    s.box((16, 1.4, 7.4), (26, -W / 2 - 0.3, 9.1), m='rubber', bevel=0.6, name='usb-flap')
    s.text('USB-C', 1.4, (26, -W / 2 - 0.05, 3.6), rot=(90, 0, 0), m='aluminium')

    # stowed drone tails: female plugs parked on the device's own inputs
    s.xt60((-28.25, -W / 2 - 12, 7.9), rot=(0, 0, -90), male=False, name='park60')
    s.xt30((-11.0, -W / 2 - 6.0, 7.9), rot=(0, 0, -90), male=False, name='park30')
    s.cyl(5.0, 10, (L / 2 + 3, 6, 8), rot=(0, 90, 0), m='rubber', bevel=1.2, name='boot')
    for dx, m in ((-3.6, 'red_wire'), (3.6, 'black_wire')):
        s.tube_path([(-28.25 + dx, -W / 2 - 20, 7.9), (-26 + dx, -W / 2 - 25, 3.0), (10, -W / 2 - 25 - dx * 0.3, 1.8),
                     (L / 2 + 8, -W / 2 - 18, 1.8), (L / 2 + 14, -4, 3.5), (L / 2 + 8, 6 + dx * 0.5, 8)],
                    1.65, m=m, name='tail60')
        s.tube_path([(-11 + dx * 0.6, -W / 2 - 11, 7.9), (-9 + dx * 0.6, -W / 2 - 15, 3.0), (14, -W / 2 - 19 - dx * 0.3, 1.8),
                     (L / 2 + 2, -W / 2 - 12, 1.8), (L / 2 + 9, -2, 3.5), (L / 2 + 8, 6 + dx * 0.2, 8)],
                    1.2, m=m, name='tail30')

    # TPE loop at the battery end (opening faces +-Y) and a carabiner through it
    s.torus(5.2, 1.8, (-L / 2 - 0.5, 0, 7.2), m='rubber', rot=(90, 0, 0), name='loop')
    pts = []
    cx, a, b = -L / 2 - 4.0 - 21, 21.0, 10.5   # stadium-ish ellipse, right end inside the loop
    for i in range(72):
        t = 2 * math.pi * i / 72
        px = cx + a * math.cos(t)
        py = b * math.sin(t) * (1.0 if math.cos(t) < 0.4 else 0.9)
        pz = 1.7 + 3.4 * (px - (cx - a)) / (2 * a)
        pts.append((px, py, pz))
    loop_curve(s, pts, 1.7, 'brushed', 'carabiner')
    s.cyl(1.0, 18, (cx - 2, -b + 0.4, 2.4), rot=(0, 90, 0), m='steel', bevel=0.2, name='gate')
