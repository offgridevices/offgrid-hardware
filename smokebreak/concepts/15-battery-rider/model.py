"""15 Battery Rider - a machined saddle that straps onto the LiPo.

Pack (4S 1500, 75 x 35 x 35 mm) centred on the origin; the rider's top slab is
81 x 40 x 15 mm with 8 mm skirts hugging the pack. Battery end at -X (male
XT60 + XT30, the pack's own lead loops into it), drone leads leave +X.
"""
import math

VIEW = dict(elevation=24, azimuth=-30)

BL, BW, BH = 75.0, 35.0, 35.0
RL, RW, RT = 81.0, 40.0, 15.0
SK = 8.0
Z1 = BH + RT                       # top of the rider


def twin(s, pts, sep=5.0, r=2.1, name='lead', axis=1):
    out = []
    for d, m in ((-sep / 2, 'red_wire'), (sep / 2, 'black_wire')):
        q = [tuple(p[i] + (d if i == axis else 0) for i in range(3)) for p in pts]
        out.append(s.tube_path(q, r, m=m, name=name))
    return out


def build(s):
    # the pack
    lipo = s.mat('lipo', '#33404A', 0.55)
    s.box((BL, BW, BH), (0, 0, BH / 2), m=lipo, bevel=2.5, name='pack')
    s.text('4S 1500 mAh', 4.2, (0, -BW / 2 - 0.05, 12), rot=(90, 0, 0),
           m=s.mat('lipo-t', '#C8D0D6', 0.6), mono=True, name='pack-t')

    # the strap, round the pack and through the rider's tunnel
    strap = s.mat('strap', '#3B3A36', 0.8)
    for y in (-BW / 2 - 0.6, BW / 2 + 0.6):
        s.box((20, 1.2, BH + 2), (0, y, BH / 2), m=strap, bevel=0.3, name='strap-side')
    s.box((20, BW + 2.4, 1.2), (0, 0, -0.1), m=strap, bevel=0.3, name='strap-bottom')

    # the rider: top slab + skirts, machined and anodised
    s.box((RL, RW, RT), (0, 0, BH + RT / 2), m='anodised', bevel=2.8, name='rider')
    for y in (-RW / 2 + 1.25, RW / 2 - 1.25):
        s.box((RL, 2.5, SK + 1), (0, y, BH - SK / 2 + 0.5), m='anodised', bevel=0.8, name='skirt')
    # strap tunnel mouth on the front skirt
    s.box((24, 0.6, 3.6), (0, -RW / 2 - 0.05, BH - 1.6), m='screen', bevel=0.2, name='slot')

    # top face: glass, Beacon Ring + Power, screen, Bind, steps
    t = Z1
    s.box((RL - 4, RW - 6, 0.6), (0, 0, t + 0.05), m='screen', bevel=1.2, name='glass')
    s.status_ring(9.6, 2.5, loc=(-22.5, 0, t + 0.5), m='ember')
    s.cyl(6.2, 2.4, (-22.5, 0, t + 1.1), m='cap', bevel=0.7, name='power')
    s.text('Power', 1.8, (-22.5, 0, t + 2.35), name='power-t')
    s.screen(31, 16, ('16.8V 4S', 'Ready'), loc=(10, 4, t + 0.45))
    s.cyl(3.4, 1.6, (34, 5, t + 0.9), m='cap', bevel=0.4, name='bind')
    s.text('Bind', 1.6, (34, -1.5, t + 0.37), name='bind-t')
    s.text('1 Strap on  →  2 Plug in  →  3 Power', 1.45, (12, -11, t + 0.37), name='steps')

    # front flank: Limit rocker, minus / plus
    yf = -RW / 2
    s.box((31, 2.0, 6.6), (19, yf - 0.6, Z1 - 7.5), m='cap', bevel=0.9, name='limit-rocker')
    s.text('−', 3.0, (11, yf - 1.65, Z1 - 7.6), rot=(90, 0, 0), mono=True, name='minus')
    s.text('+', 3.0, (27, yf - 1.65, Z1 - 7.6), rot=(90, 0, 0), mono=True, name='plus')
    s.text('Limit', 2.4, (-34.5, yf - 0.05, Z1 - 5.5), rot=(90, 0, 0), align='LEFT', name='limit-t')
    s.text('AUTO 1 2 5 10 20A', 1.5, (-34.5, yf - 0.05, Z1 - 9.5), rot=(90, 0, 0), mono=True, align='LEFT',
           name='limit-scale')
    s.arrow(7, (-4, yf - 0.05, Z1 - 7.5), rot_z=0, z_rot_extra=(90, 0), name='limit-arrow')

    # battery end: male XT60 + XT30, panel-mount, rib between
    xe = -RL / 2
    s.xt30((xe + 2, -8.5, Z1 - 7.6), male=True, name='in30')
    s.box((2.5, 1.4, 11), (xe - 0.8, 0.5, Z1 - 7.5), m='anodised', bevel=0.3, name='rib')
    s.xt60((xe + 3, 9, Z1 - 7.5), male=True, name='in60')
    # the pack's own lead loops into it
    s.xt60((xe - 13, 9, Z1 - 7.5), rot=(0, 0, 180), male=False, name='batt-plug')
    twin(s, [(xe - 21, 9, Z1 - 7.5), (xe - 26, 9, Z1 - 12), (xe - 26, 9, 22), (xe - 18, 9, 17),
             (-BL / 2 + 0.5, 9, 17)], name='batt-lead')

    # USB-C on the rear flank
    s.usb_c((0, RW / 2 + 0.3, Z1 - 7.5), rot=(0, 0, -90))

    # drone end: two clamped leads with female plugs on the bench
    xd = RL / 2
    for y in (-9.5, 8.5):
        s.cyl(3.8, 3.0, (xd + 1.0, y, Z1 - 7.5), m='rubber', bevel=0.6, rot=(0, 90, 0), name='grommet')
    twin(s, [(xd + 2, -9.5, Z1 - 7.5), (xd + 14, -12, Z1 - 12), (xd + 18, -22, 6), (xd + 26, -34, 4.1),
             (xd + 30, -38, 4.1)], name='lead60', axis=1, sep=4.6)
    s.xt60((xd + 38, -38, 4.1), rot=(0, 0, 180), male=False, name='out60')
    twin(s, [(xd + 2, 8.5, Z1 - 7.5), (xd + 12, 10, Z1 - 14), (xd + 18, 14, 4), (xd + 34, 6, 2.6),
             (xd + 40, 4, 2.6)], name='lead30', axis=1, sep=3.2, r=1.5)
    s.xt30((xd + 45, 4, 2.6), rot=(0, 0, 180), male=False, name='out30')
