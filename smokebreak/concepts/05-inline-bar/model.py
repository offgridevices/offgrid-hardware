"""05 Inline bar: a slim anodised-aluminium bar that lives in the power lead.
128 x 24 x 15 mm, glass top over the PCB face, silicone boots, 8 cm battery
tail (XT60 + XT30 male) and 10 cm drone tail (XT60 + XT30 female)."""
import math

VIEW = dict(elevation=30, azimuth=-28)

L, W, H = 128.0, 24.0, 15.0


def tail(s, root, split, plugs, name):
    """Twin lead from `root` to `split`, then a red/black pair to each plug's back."""
    for dy, m in ((-1.8, 'red_wire'), (1.8, 'black_wire')):
        r = (root[0], root[1] + dy, root[2])
        sp = (split[0], split[1] + dy, split[2])
        mid = ((r[0] + sp[0]) / 2, (r[1] + sp[1]) / 2, max(1.8, (r[2] + sp[2]) / 2 - 1.5))
        s.tube_path([r, mid, sp], 1.65, m=m, name=f'{name}-{m}')
        for i, (kind, loc, back) in enumerate(plugs):
            b = (back[0], back[1] + dy * (0.9 if kind == 60 else 0.55), back[2])
            mid2 = ((sp[0] + b[0]) / 2, (sp[1] + b[1]) / 2, 1.8)
            s.tube_path([sp, mid2, b], 1.65 if kind == 60 else 1.2, m=m, name=f'{name}-{i}-{m}')


def build(s):
    top = H + 0.45
    # body: black anodised extrusion, glass window over the PCB face
    s.box((L, W, H), (0, 0, H / 2), m='anodised', bevel=4.0, name='extrusion')
    s.box((L - 10, 18, 0.6), (0, 0, H - 0.05), m='pcb', bevel=1.6, name='face')
    s.box((L - 10, 18, 0.5), (0, 0, H + 0.35), m='glass', bevel=1.6, name='glass')
    # end caps + silicone boots
    for sx in (-1, 1):
        s.box((2.0, W - 1, H - 1), (sx * (L / 2 + 0.6), 0, H / 2), m='aluminium', bevel=1.2, name='cap')
        s.cyl(4.6, 12, (sx * (L / 2 + 7), 0, 7.0), rot=(0, 90, 0), m='rubber', bevel=1.2, name='boot')

    # face (local 2D layout: x 0..128 left to right, y 0..24 back to front)
    def B(x, y):
        return (x - L / 2, W / 2 - y)

    x, y = B(7.5, 9.0)
    s.text('Battery', 1.9, (x, y, top), align='LEFT')
    x, y = B(12, 13.6)
    s.arrow(9, (x, y, top), rot_z=0, shaft=0.28, head=0.9)
    x, y = B(34, 12)
    s.screen(26, 12, ('ON  0.42A', '16.8V  4S'), loc=(x, y, top - 0.1))
    # Power: Beacon Ring light pipe round a cap
    x, y = B(62, 12.6)
    s.beacon_ring(6.0, 2.0, loc=(x, y, top), m='green')
    s.cyl(3.6, 2.2, (x, y, top + 0.6), m='cap', bevel=0.6, name='power')
    # Limit + pips
    x, y = B(78, 12.6)
    s.cyl(2.9, 1.8, (x, y, top + 0.5), m='cap', bevel=0.5, name='limit')
    x, y = B(78, 6.8)
    s.text('Limit', 1.8, (x, y, top))
    for i, (t, px) in enumerate((('AUTO', 87.0), ('1', 91.6), ('2', 94.2), ('5', 96.8), ('10', 99.9), ('20', 103.4))):
        x, y = B(px, 10.6)
        s.cyl(0.75, 0.4, (x, y, top + 0.1), m='white_led' if i == 0 else 'cap', bevel=0.1, verts=24, name='pip')
        x, y = B(px, 14.6)
        s.text(t, 1.3, (x, y, top), mono=True)
    x, y = B(94.5, 18.4)
    s.text('20A: props off', 1.1, (x, y, top))
    # Bind
    x, y = B(111, 12.6)
    s.cyl(2.9, 1.8, (x, y, top + 0.5), m='cap', bevel=0.5, name='bind')
    x, y = B(111, 6.8)
    s.text('Bind', 1.8, (x, y, top))
    # Drone out
    x, y = B(119, 9.0)
    s.arrow(5, (x, y, top), rot_z=0, shaft=0.28, head=0.9)
    x, y = B(119.5, 15.6)
    s.text('Drone', 1.5, (x, y, top))
    # USB-C on the front flank, laser-etched label
    s.usb_c((-46.5, -W / 2 - 0.2, 7.5), rot=(0, 0, 90))
    s.text('USB-C', 1.6, (-38, -W / 2 - 0.05, 7.5), rot=(90, 0, 0), m='aluminium', align='LEFT')
    s.text('SmokeBreak', 1.8, (50, -W / 2 - 0.05, 7.5), rot=(90, 0, 0), m='aluminium')

    # battery tail: XT60 + XT30 male, mating faces pointing away (-X)
    s.xt60((-104, -18, 4.1), rot=(0, 0, 0), male=True, name='bat60')
    s.xt30((-100, 16, 2.6), rot=(0, 0, 0), male=True, name='bat30')
    tail(s, (-76, 0, 7.0), (-84, 0, 3.0),
         [(60, (-104, -18), (-96, -18, 4.1)), (30, (-100, 16), (-95, 16, 2.6))], 'bat')
    # drone tail: XT60 + XT30 female, mating faces pointing away (+X)
    s.xt60((104, -18, 4.1), rot=(0, 0, 180), male=False, name='dr60')
    s.xt30((100, 16, 2.6), rot=(0, 0, 180), male=False, name='dr30')
    tail(s, (76, 0, 7.0), (84, 0, 3.0),
         [(60, (104, -18), (96, -18, 4.1)), (30, (100, 16), (95, 16, 2.6))], 'dr')
