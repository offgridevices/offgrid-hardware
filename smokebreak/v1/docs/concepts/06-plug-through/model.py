"""06 Plug-through: a rigid dongle with no leads. 64 x 38 x 21 mm machined
aluminium unibody, black-glass top that is the Power key, Bind and Limit on
the front flank, XT60 + XT30 male at the battery end, female at the drone end.
Shown with the battery's XT60 about to plug in and the drone's pigtail mated."""

VIEW = dict(elevation=30, azimuth=-38)

L, W, H = 64.0, 38.0, 21.0


def build(s):
    s.box((L, W, H), (0, 0, H / 2), m='anodised', bevel=3.0, name='unibody')
    # black glass top (the whole plate is the Power key), small reveal round it
    s.box((L - 3.0, W - 3.0, 1.4), (0, 0, H + 0.1), m='screen', bevel=1.4, name='glass-key')
    top = H + 0.82

    def B(x, y):
        return (x - L / 2, W / 2 - y)

    x, y = B(17, 18)
    s.status_ring(6.6, 1.6, loc=(x, y, top - 0.35), m='green')
    x, y = B(17, 32.2)
    s.text('Press the glass', 1.6, (x, y, top))
    x, y = B(45.5, 13)
    s.screen(25, 12, ('ON  0.42A', '16.8V  4S'), loc=(x, y, top - 0.25))
    x, y = B(32, 24.4)
    s.text('Press to check, then power on.', 1.45, (x, y, top), align='LEFT')
    x, y = B(32, 27.6)
    s.text('Press again to turn off.', 1.45, (x, y, top), align='LEFT', m='aluminium')
    x, y = B(55.5, 33)
    s.arrow(7, (x, y, top), shaft=0.28, head=0.9)
    x, y = B(51.2, 33)
    s.text('Drone', 1.5, (x, y, top), align='RIGHT')
    x, y = B(2.8, 4.6)
    s.text('Battery', 1.5, (x, y, top), align='LEFT')

    # front flank: Bind and Limit keys with etched names
    for cx, lab in ((-9.5, 'Bind'), (8.5, 'Limit')):
        s.box((12.5, 2.0, 3.8), (cx, -W / 2 - 0.2, 9.6), m='cap', bevel=1.5, name=lab)
        s.text(lab, 1.8, (cx, -W / 2 - 0.05, 14.0), rot=(90, 0, 0), m='aluminium')
    s.text('AUTO 1 2 5 10 20A', 1.2, (8.5, -W / 2 - 0.05, 5.0), rot=(90, 0, 0), m='aluminium', mono=True)

    # battery end: male XT60 + XT30 panel-mount, rib between
    s.xt60((-L / 2 + 4, -8, 7.7), male=True, name='in60')
    s.xt30((-L / 2 + 5, 10, 7.7), male=True, name='in30')
    s.box((3.0, 1.6, 10), (-L / 2 - 1.0, 2.2, 7.7), m='anodised', bevel=0.5, name='rib')
    s.text('Battery in', 1.6, (-L / 2 - 0.05, 0, 16.5), rot=(90, 0, -90), m='aluminium')
    # drone end: female XT60 + XT30
    s.xt60((L / 2 - 4, -8, 7.7), rot=(0, 0, 180), male=False, name='out60')
    s.xt30((L / 2 - 5, 10, 7.7), rot=(0, 0, 180), male=False, name='out30')
    # USB-C on the back flank
    s.usb_c((10, W / 2 + 0.2, 10.5), rot=(0, 0, -90))

    # the battery's female XT60, about to plug in, lead going back to the pack
    s.xt60((-58, -8, 7.7), rot=(0, 0, 180), male=False, name='bat-plug')
    for dy, m in ((-3.6, 'red_wire'), (3.6, 'black_wire')):
        s.tube_path([(-66, -8 + dy, 7.7), (-80, -8 + dy * 1.2, 6.5), (-90, -16 + dy, 2.0), (-100, -30 + dy, 1.8)],
                    1.65, m=m, name='bat-lead')
    s.arrow(10, (-44, -8, 13.5), rot_z=0, shaft=0.5, head=1.4, m='pitch')
    # the drone's own pigtail, mated into the female end
    s.xt60((L / 2 + 12, -8, 7.7), male=True, name='drone-plug')
    for dy, m in ((-3.6, 'red_wire'), (3.6, 'black_wire')):
        s.tube_path([(L / 2 + 20, -8 + dy, 7.7), (L / 2 + 34, -8 + dy, 6.5), (L / 2 + 42, 4 + dy, 2.0), (L / 2 + 46, 18 + dy, 1.8)],
                    1.65, m=m, name='drone-lead')
