"""16 Wall Tile - a magnetic tile at eye level; Power is a light switch.

The tile (72 x 120 x 20 mm, glass face toward -Y) is stuck by its magnets to a
section of steel toolbox side. Battery input (male XT60 + XT30) and the drone
leads all point down; the leads hang to the bench.
"""
import math

VIEW = dict(elevation=18, azimuth=-30)

TW, TH, TD = 72.0, 120.0, 20.0
Z0 = 58.0                          # tile bottom above the bench
YF = -TD                           # face plane


def F(a, b):
    """Face mm (a from the left edge, b down from the top) -> world (x, z)."""
    return (a - TW / 2, Z0 + TH - b)


def build(s):
    # steel toolbox side, powder coated, standing on the bench
    s.box((190, 4, 196), (0, 2, 98), m=s.mat('powder coat', '#6F6C66', 0.55, 0.3), bevel=2.0, name='toolbox')
    for i in range(5):
        s.box((70, 1.2, 2.4), (48, -0.4, 176 - i * 8), m=s.mat('louvre', '#4E4B46', 0.6, 0.3), bevel=0.4, name='louvre')

    # the tile
    s.box((TW, TD, TH), (0, -TD / 2, Z0 + TH / 2), m='anodised', bevel=5.0, name='tile')
    s.box((TW - 5, 0.6, TH - 5), (0, YF - 0.1, Z0 + TH / 2), m='screen', bevel=3.0, name='glass')
    yf = YF - 0.45
    rot = (90, 0, 0)
    x, z = F(36, 25)
    s.screen(52, 31, ('16.8V  4S', 'Ready'), loc=(x, yf, z), rot=rot)
    # Beacon Ring round the light-switch rocker
    x, z = F(36, 70)
    s.beacon_ring(15.5, 3.4, loc=(x, yf - 0.3, z), rot=rot, m='ember')
    s.box((16, 2.2, 22), (x, yf - 1.2, z), m='cap', bevel=1.2, name='rocker-frame')
    s.box((14, 2.4, 10), (x, yf - 2.6, z + 5.2), m='cap', bevel=1.4, rot=(-6, 0, 0), name='rocker-on')
    s.box((14, 2.0, 10), (x, yf - 2.0, z - 5.2), m='cap', bevel=1.4, rot=(6, 0, 0), name='rocker-off')
    s.text('On', 2.8, (x, yf - 3.9, z + 5.2), rot=rot, name='on-t')
    s.text('Off', 2.8, (x, yf - 3.1, z - 5.4), rot=rot, name='off-t')
    # Bind / Limit
    for a, lab in ((21, 'Bind'), (51, 'Limit')):
        x, z = F(a, 99.5)
        s.box((26, 2.0, 11), (x, yf - 1.0, z), m='cap', bevel=1.2, name=lab)
        s.text(lab, 3.0, (x, yf - 2.05, z), rot=rot, name=lab + '-t')
    # bottom edge: Battery (arrow in) / Drone (arrow out)
    x, z = F(14, 113)
    s.text('Battery', 2.4, (x, yf - 0.05, z), rot=rot, name='batt-t')
    s.arrow(5, (x + 9, yf - 0.05, z), rot_z=0, z_rot_extra=(90, -90), name='batt-arrow')
    x, z = F(58, 113)
    s.text('Drone', 2.4, (x, yf - 0.05, z), rot=rot, name='drone-t')
    s.arrow(5, (x - 9, yf - 0.05, z), rot_z=0, z_rot_extra=(90, 90), name='drone-arrow')

    # underside: battery in (male), USB-C, drone leads; everything points down
    yb = -TD / 2
    s.xt60((-23, yb, Z0 + 3), rot=(0, -90, 0), male=True, name='in60')
    s.xt30((-7, yb, Z0 + 2), rot=(0, -90, 0), male=True, name='in30')
    s.usb_c((5, yb, Z0 - 0.3), rot=(0, -90, 0))
    for x in (16, 27):
        s.cyl(3.8, 3.0, (x, yb, Z0 - 1.0), m='rubber', bevel=0.6, name='grommet')

    # battery on the bench, its lead up into the tile
    s.box((75, 35, 35), (-70, -70, 17.5), m=s.mat('lipo', '#33404A', 0.55), bevel=2.5, name='lipo')
    s.xt60((-23, yb, Z0 - 13), rot=(0, 90, 0), male=False, name='batt-plug')
    for dx, m in ((-2.6, 'red_wire'), (2.6, 'black_wire')):
        s.tube_path([(-23, yb + dx, Z0 - 21), (-23, yb + dx, Z0 - 30), (-30, yb - 20 + dx, 34),
                     (-40, -60 + dx, 26), (-33, -60 + dx, 18)], 2.0, m=m, name='batt-lead')

    # drone leads hang straight down, then lie on the bench with female plugs
    for x, r, sep, end, tag in ((16, 2.1, 4.6, (36, -64, 4.1), '60'), (27, 1.5, 3.2, (62, -44, 2.6), '30')):
        for dy, m in ((-sep / 2, 'red_wire'), (sep / 2, 'black_wire')):
            s.tube_path([(x, yb + dy, Z0 - 2), (x, yb + dy, 30), (x + 2, yb - 4 + dy, 6),
                         (end[0] - 6, end[1] + 10 + dy, end[2]), (end[0], end[1] + 6 + dy, end[2])], r, m=m,
                        name='lead' + tag)
    s.xt60((36, -72, 4.1), rot=(0, 0, 90), male=False, name='out60')
    s.xt30((62, -49, 2.6), rot=(0, 0, 90), male=False, name='out30')
