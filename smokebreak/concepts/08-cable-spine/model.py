"""08 Cable spine: the leads and the electronics form one flat, soft sleeve.
100 x 30 x 9.5 mm soft-touch silicone spine, dead-front (the words and Beacon
Ring glow up through the skin), silicone domes for Power / Limit / Bind, flat
bonded twin leads Y-split to XT60 + XT30 male (battery) and female (drone)."""

VIEW = dict(elevation=34, azimuth=-26)

L, W, H = 100.0, 30.0, 9.5


def tail(s, root, split, plugs, name):
    for dy, m in ((-1.75, 'red_wire'), (1.75, 'black_wire')):
        r = (root[0], root[1] + dy, root[2])
        sp = (split[0], split[1] + dy, split[2])
        mid = ((r[0] + sp[0]) / 2, (r[1] + sp[1]) / 2, max(1.8, (r[2] + sp[2]) / 2 - 0.8))
        s.tube_path([r, mid, sp], 1.65, m=m, name=f'{name}-{m}')
        for i, (kind, back) in enumerate(plugs):
            b = (back[0], back[1] + dy * (0.9 if kind == 60 else 0.55), back[2])
            mid2 = ((sp[0] + b[0]) / 2, (sp[1] + b[1]) / 2, 1.8)
            s.tube_path([sp, mid2, b], 1.65 if kind == 60 else 1.2, m=m, name=f'{name}-{i}-{m}')


def build(s):
    sil = s.mat('soft-touch silicone', '#1C1916', 0.9)
    s.box((L, W, H), (0, 0, H / 2), m=sil, bevel=4.4, name='spine')
    for sx in (-1, 1):
        s.box((16, 13, 6.2), (sx * (L / 2 + 3), 0, 3.3), m=sil, bevel=2.8, name='taper')
    top = H + 0.02
    glow = s.mat('glow txt', '#9FE0A0', 0.5, emit='#9FE0A0', strength=1.6)
    glow_g = s.mat('glow green', '#4caf50', 0.5, emit='#4caf50', strength=2.2)
    bone = s.mat('bone print', '#CFC8BA', 0.7)

    def B(x, y):
        return (x - L / 2, W / 2 - y)

    x, y = B(5.5, 11.0)
    s.text('Battery', 1.8, (x, y, top), m=bone, align='LEFT')
    x, y = B(10, 16.2)
    s.arrow(9, (x, y, top), shaft=0.28, head=0.9, m=bone)
    # dead-front OLED: only the lit words show
    x, y = B(19, 12.0)
    s.text('ON 0.42A', 2.7, (x, y, top), m=glow_g, mono=True, align='LEFT')
    x, y = B(19, 16.4)
    s.text('16.8V 4S', 1.7, (x, y, top), m=glow, mono=True, align='LEFT')
    x, y = B(19, 20.2)
    s.text('AUTO 2.0A · DRONE 3', 1.25, (x, y, top), m=glow, mono=True, align='LEFT')
    # Beacon Ring glowing through the skin, Power dome inside it
    x, y = B(61, 15)
    s.beacon_ring(5.8, 1.6, loc=(x, y, top - 0.55), m='green')
    d = s.sphere(3.6, (x, y + 0.6, H - 0.3), m=sil, name='power-dome')
    d.scale = (1, 1, 0.42)
    x, y = B(61, 27.2)
    s.text('Press the ring', 1.4, (x, y, top), m=bone)
    # Limit and Bind domes
    for ly, lab in ((10.2, 'Limit'), (21.0, 'Bind')):
        x, y = B(77.5, ly)
        d = s.sphere(3.3, (x, y, H - 0.3), m=sil, name=lab)
        d.scale = (1, 1, 0.42)
        x, y = B(82.2, ly)
        s.text(lab, 1.8, (x, y, top), m=bone, align='LEFT')
    x, y = B(94.5, 13.2)
    s.arrow(6, (x, y, top), shaft=0.28, head=0.9, m=bone)
    x, y = B(94.5, 18.4)
    s.text('Drone', 1.4, (x, y, top), m=bone)
    # front lip: USB-C + etched line
    s.usb_c((36, -W / 2 - 0.1, 4.6), rot=(0, 0, 90))
    s.text('Bench use only', 1.3, (-20, -W / 2 - 0.02, 4.6), rot=(90, 0, 0), m=bone)

    # flat bonded twin tails, Y-split to XT60 + XT30
    s.xt60((-104, -18, 4.1), male=True, name='bat60')
    s.xt30((-100, 14, 2.6), male=True, name='bat30')
    tail(s, (-L / 2 - 10, 0, 3.0), (-80, 0, 1.8), [(60, (-96, -18, 4.1)), (30, (-95, 14, 2.6))], 'bat')
    s.xt60((104, -18, 4.1), rot=(0, 0, 180), male=False, name='dr60')
    s.xt30((100, 14, 2.6), rot=(0, 0, 180), male=False, name='dr30')
    tail(s, (L / 2 + 10, 0, 3.0), (80, 0, 1.8), [(60, (96, -18, 4.1)), (30, (95, 14, 2.6))], 'dr')
