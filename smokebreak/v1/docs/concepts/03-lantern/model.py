"""03 Lantern - stands upright: Ø46 x 98 mm on a Ø52 stainless base.
Turn the knurled crown for Limit, press its centre (inside the Beacon Ring) for
Power, a frosted halo band glows the status all round. Battery in on the left
(-X), drone leads out on the right (+X), 1.47" IPS behind a flat on the front."""
import math

VIEW = dict(elevation=30, azimuth=-32, lens=52)

R = 23.0
ZB1, ZBODY, ZH, ZC = 7.0, 80.0, 85.0, 98.0
STEPS = ['AUTO', '1', '2', '5', '10', '20']


def build(s):
    import bpy
    s.cyl(26, ZB1, (0, 0, ZB1 / 2), m='brushed', bevel=1.0, verts=128, name='base')
    body = s.cyl(R, ZBODY - ZB1, (0, 0, (ZB1 + ZBODY) / 2), m='anodised', bevel=0, verts=160, name='body')
    # flat window for the screen on the front (-Y)
    c = s.box((22.8, 12, 42), (0, -20 - 6, 54), m=None, bevel=0, name='cutter')
    mod = body.modifiers.new('window', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = c
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(c, do_unlink=True)
    b = body.modifiers.new('bevel', 'BEVEL'); b.width, b.segments, b.limit_method = 0.6, 3, 'ANGLE'
    # halo band (glowing frosted glass) and the rotating crown
    s.cyl(R - 0.4, ZH - ZBODY, (0, 0, (ZBODY + ZH) / 2), m='ember', bevel=0, verts=128, name='halo')
    s.cyl(R, ZC - ZH, (0, 0, (ZH + ZC) / 2), m='anodised', bevel=1.0, verts=128, name='crown')
    for i in range(72):                                   # knurl
        t = 2 * math.pi * i / 72
        s.box((0.9, 0.9, 5.0), (R * math.cos(t), R * math.sin(t), ZH + 3.2), m='anodised', bevel=0.2,
              rot=(0, 0, math.degrees(t) + 45), name='knurl')
    # Limit marks on the crown skirt; AUTO faces the front index
    for k, lab in enumerate(STEPS):
        t = -90 + k * 36
        tr = math.radians(t)
        s.text(lab, 2.2, ((R + 0.05) * math.cos(tr), (R + 0.05) * math.sin(tr), ZH + 9.0),
               rot=(90, 0, t + 90), m='ember' if lab == '20' else 'bone', mono=True)
    # crown top: Power in the Beacon Ring
    s.cyl(R - 1.8, 0.3, (0, 0, ZC + 0.1), m='screen', bevel=0, verts=128, name='crown-face')
    s.status_ring(13.0, 2.2, loc=(0, -1.2, ZC + 0.4), m='ember')
    s.cyl(8.2, 2.0, (0, -1.2, ZC + 1.0), m='brushed', bevel=0.7, name='power')
    s.text('Power', 2.2, (0, -1.2, ZC + 2.05), m='pitch')
    # front: index mark, screen, Bind
    s.text('Limit: turn', 1.7, (0, -23.05, ZBODY - 3.4), rot=(90, 0, 0))
    s.arrow(2.6, (0, -23.05, ZBODY - 1.1), rot_z=90, z_rot_extra=(90, 0))
    sy = -20.3
    s.box((20, 0.6, 38), (0, sy, 54), m='screen', bevel=0.4, name='screen')
    ips = s.mat('ips text', s.BONE, 0.5, emit=s.BONE, strength=1.0)
    s.text('4S', 2.4, (0, sy - 0.35, 68), rot=(90, 0, 0), m=ips, mono=True)
    s.text('16.8', 5.6, (0, sy - 0.35, 60.5), rot=(90, 0, 0), m=ips, mono=True)
    s.text('VOLTS', 1.9, (0, sy - 0.35, 56), rot=(90, 0, 0), m=ips, mono=True)
    s.text('LIMIT AUTO', 1.7, (0, sy - 0.35, 49), rot=(90, 0, 0), m=ips, mono=True)
    em = s.mat('ips ember', s.EMBER, 0.5, emit=s.EMBER, strength=1.2)
    s.text('Press', 2.0, (0, sy - 0.35, 43.5), rot=(90, 0, 0), m=em)
    s.text('the top', 2.0, (0, sy - 0.35, 40.2), rot=(90, 0, 0), m=em)
    s.cyl(3.1, 1.6, (0, -R - 0.2, 29), m='brushed', bevel=0.5, rot=(90, 0, 0), name='bind')
    s.text('Bind', 1.9, (0, -R - 0.05, 23.8), rot=(90, 0, 0))
    s.text('Bench use only', 1.4, (0, -R - 0.05, 13), rot=(90, 0, 0), m=s.mat('grey print', '#8a8377', 0.6))
    # battery: XT60 over XT30 (male) on the left, label above
    s.xt60((-R - 4 + 8, 0, 26.1), male=True, name='in60')
    s.xt30((-R - 3 + 5, 0, 14.5), male=True, name='in30')
    s.text('Battery', 2.2, (-R - 0.05, 0, 37), rot=(90, 0, -90))
    s.arrow(5, (-R - 0.05, 0, 33), rot_z=-90, z_rot_extra=(90, 0))
    # USB-C on the back
    s.usb_c((0, R + 0.2, 40), rot=(0, 0, -90))
    # drone leads from the right, low down, onto the bench
    for dy, m in ((-2.0, 'red_wire'), (2.0, 'black_wire')):
        s.tube_path([(R - 1, dy, 24), (R + 22, dy, 23), (R + 30, dy - 28, 2.0), (R + 22, dy - 52, 1.9)],
                    1.8, m=m, name='lead60')
    s.xt60((R + 22, -52 - 8 - 1.5, 4.1), rot=(0, 0, 90), male=False, name='out60')
    for dy, m in ((-1.4, 'red_wire'), (1.4, 'black_wire')):
        s.tube_path([(R - 1, dy + 4, 13), (R + 28, dy + 4, 12), (R + 46, dy - 8, 1.5), (R + 48, dy - 28, 1.4)],
                    1.3, m=m, name='lead30')
    s.xt30((R + 48, -28 - 5 - 1.4, 2.6), rot=(0, 0, 90), male=False, name='out30')
    # framing helpers: invisible markers that widen the bounds the studio frames on,
    # so the tall body is not cropped at the top of the 16:10 frame
    for p in ((-75, -95, 0), (75, 70, 125)):
        mk = s.box((1, 1, 1), p, m=None, bevel=0, name='frame-marker')
        mk.hide_render = True
