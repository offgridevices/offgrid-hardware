"""02 Puck - Ø80 x 22 mm machined aluminium puck with a glass top.
Press the glass for Power; the Beacon Ring glows under it around a round IPS;
the ring's dot is a stainless Bind button; Limit is a pill on the front rim.
Battery in through the left flat (-X), drone leads out of the right flat (+X)."""
import math

VIEW = dict(elevation=36, azimuth=-30)

RO, H, XF = 40.0, 22.0, 37.0
RG, RR = 33.0, 20.0
NODE_Y = RR * 60 / 58.0          # node centre, toward +Y (12 o'clock)
LIM = [('AUTO', 145), ('1', 123), ('2', 101), ('5', 79), ('10', 57), ('20', 35)]


def build(s):
    import bpy
    body = s.cyl(RO, H, (0, 0, H / 2), m='anodised', bevel=0, verts=160, name='shell')
    for sx in (-1, 1):
        c = s.box((20, 100, 40), (sx * (XF + 10), 0, H / 2), m=None, bevel=0, name='cutter')
        mod = body.modifiers.new('flat', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = c
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(c, do_unlink=True)
    b = body.modifiers.new('bevel', 'BEVEL'); b.width, b.segments, b.limit_method = 1.2, 4, 'ANGLE'
    s.cyl(RO - 2, 0.8, (0, 0, 0.3), m='rubber', bevel=0.2, name='foot')

    top = H
    # glass top (black-backed), round IPS in the centre
    s.cyl(RG, 1.2, (0, 0, top + 0.4), m='screen', bevel=0.5, verts=128, name='glass')
    g = top + 1.05
    s.cyl(16.2, 0.1, (0, 0, g), m=s.mat('ips black', '#020202', 0.2), bevel=0, name='ips')
    ips = s.mat('ips text', s.BONE, 0.5, emit=s.BONE, strength=1.0)
    s.text('16.8V', 6.0, (0, -0.5, g + 0.06), m=ips, mono=True)
    s.text('4S', 2.4, (0, 7.5, g + 0.06), m=s.mat('ips grey', '#b9b2a3', 0.5, emit='#b9b2a3', strength=0.6), mono=True)
    s.text('LIMIT AUTO', 1.7, (0, -6.3, g + 0.06), m=ips, mono=True)
    s.text('Press the glass', 1.7, (0, -9.4, g + 0.06), m=s.mat('ips ember', s.EMBER, 0.5, emit=s.EMBER, strength=1.2))
    # Beacon Ring light under the glass (no node: the node is the Bind button)
    s.status_ring(RR, 2.2, loc=(0, 0, g), m='ember')
    s.torus(5.9, 0.7, (0, NODE_Y, g + 0.2), m='ember', name='bind-halo')
    s.cyl(4.6, 2.2, (0, NODE_Y, g + 0.9), m='brushed', bevel=0.6, name='bind')
    s.text('Bind', 1.8, (7.0, NODE_Y, g + 0.02), align='LEFT')
    # Limit scale around the lower arc
    for i, (lab, a) in enumerate(LIM):
        t = math.radians(a)
        dx, dy = 24.3 * math.cos(t), -24.3 * math.sin(t)
        s.cyl(0.75, 0.1, (dx, dy, g + 0.02), m='white_led' if i == 0 else 'cap', bevel=0, verts=24, name='dot')
        lx, ly = 28.2 * math.cos(t), -28.2 * math.sin(t)
        s.text(lab, 1.6, (lx, ly, g + 0.02), m='ember' if lab == '20' else 'bone', mono=True)
    s.text('Limit', 1.6, (0, -30.8, g + 0.02))
    s.text('Battery', 1.7, (-27.5, 3.4, g + 0.02))
    s.arrow(6.5, (-27.5, 1.0, g + 0.02), rot_z=0)
    s.text('Drone', 1.7, (27.5, 3.4, g + 0.02))
    s.arrow(6.5, (27.5, 1.0, g + 0.02), rot_z=0)
    # Limit pill on the front rim (6 o'clock)
    s.box((12, 2.4, 4.4), (0, -RO - 0.4, H / 2), m='brushed', bevel=1.1, name='limit')
    # battery: XT60 + XT30 male in the left flat, rib between
    s.xt60((-XF - 4 + 8, -6.75, 11), male=True, name='in60')
    s.xt30((-XF - 3 + 5, 8.5, 11), male=True, name='in30')
    s.box((1.2, 2.0, 12), (-XF - 0.6, 2.4, 11), m='anodised', bevel=0.3, name='rib')
    # USB-C on the back rim
    s.usb_c((0, RO + 0.2, 10), rot=(0, 0, -90))
    # drone leads out of the right flat through glands
    for y in (-6.5, 7):
        s.cyl(3.2, 3, (XF + 1.2, y, 11), m='rubber', bevel=0.6, rot=(0, 90, 0), name='gland')
    for dy, m in ((-2.0, 'red_wire'), (2.0, 'black_wire')):
        s.tube_path([(XF + 1, -6.5 + dy, 11), (XF + 18, -6.5 + dy, 11), (XF + 24, -30 + dy, 2.0), (XF + 14, -62 + dy, 1.9)],
                    1.8, m=m, name='lead60')
    s.xt60((XF + 14, -62 - 8 - 1.5, 4.1), rot=(0, 0, 90), male=False, name='out60')
    for dy, m in ((-1.4, 'red_wire'), (1.4, 'black_wire')):
        s.tube_path([(XF + 1, 7 + dy, 11), (XF + 26, 7 + dy, 10), (XF + 40, -14 + dy, 1.5), (XF + 40, -36 + dy, 1.4)],
                    1.3, m=m, name='lead30')
    s.xt30((XF + 40, -36 - 5 - 1.4, 2.6), rot=(0, 0, 90), male=False, name='out30')
