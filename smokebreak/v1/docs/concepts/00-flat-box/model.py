"""00 - the flat-box baseline from SPEC.md (the design to beat)."""
VIEW = dict(elevation=32, azimuth=-30)


def build(s):
    W, D, H = 86, 56, 20
    s.box((W, D, H), (0, 0, H / 2), m='pitch_soft', bevel=4, name='case')
    s.box((W - 4, D - 4, 1.2), (0, 0, H + 0.2), m='pcb', bevel=2.5, name='face')
    top = H + 0.85
    s.screen(28, 15, ('16.8V  4S', 'ON  0.42A'), loc=(-20, 10, top))
    s.status_ring(9, 2.2, loc=(20, 9, top + 0.3), m='ember')
    s.cyl(5.6, 2.4, (20, 9, top + 1.0), m='cap', bevel=0.6, name='power')
    s.text('Power', 1.8, (20, 9, top + 2.25))
    for i, (lab, y) in enumerate((('Bind', -8), ('Limit', -18))):
        s.cyl(3.4, 2.0, (-32, y, top + 0.8), m='cap', bevel=0.5, name=lab)
        s.arrow(6, (-23.5, y, top + 0.05), rot_z=180)
        s.text(lab, 2.0, (-19.5, y, top + 0.05), align='LEFT')
    s.text('1 Battery in  →  2 Drone in  →  3 Press Power', 1.6, (-6, -24, top + 0.05))
    # connectors: battery side (male, panel), drone side (female, leads)
    s.xt60((-W / 2 - 6, 6, 8), rot=(0, 0, 0), male=True, name='in60')
    s.xt30((-W / 2 - 4, -12, 6), male=True, name='in30')
    s.leads((W / 2, 6, 9), (W / 2 + 60, 14, 5), name='out60-lead')
    s.xt60((W / 2 + 70, 14, 5), rot=(0, 0, 180), male=False, name='out60')
    s.usb_c((0, D / 2, 10), rot=(0, 0, 90))
