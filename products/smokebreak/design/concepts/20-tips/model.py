"""20 - Tips: one aluminium body, swappable magnetic connector tips at each end
(XT60 fitted here); an XT90 tip lies on the bench, ready to swap in."""
import math

VIEW = dict(elevation=30, azimuth=-30)

W, D, H = 84.0, 52.0, 18.0
TW, TH, TC = 30.0, 13.0, 9.0


def B(x, y):
    return (x - W / 2, D / 2 - y)


def tip_collar(s, x, y, z, name):
    return s.box((TC, TW, TH), (x, y, z), m=s.mat('tip nylon', '#35312B', 0.7), bevel=3.0, name=name)


def build(s):
    # body
    s.box((W, D, H), (0, 0, H / 2), m='anodised', bevel=4.0, name='body')
    s.box((W - 3, D - 3, 0.6), (0, 0, H + 0.1), m=s.mat('black glass', '#0B0A09', 0.22, coat=0.3), bevel=2.6,
          name='face')
    top = H + 0.42

    def txt(t, size, x, y, align='LEFT', mono=False, m='bone'):
        s.text(t, size, B(x, y) + (top,), m=m, align=align, mono=mono, depth=0.02)

    s.screen(33, 20, ('16.8V 4S', 'XT60 TIPS'), loc=B(23.5, 19) + (top + 0.1,), name='oled')
    for i, (n, sub) in enumerate((('Bind', 'Puts the receiver in bind'), ('Limit', 'AUTO 1 2 5 10 20A'))):
        y = 36 + i * 7.6
        s.cyl(2.8, 1.6, B(10, y) + (top + 0.6,), m='cap', bevel=0.5, name=n)
        ax, ay = B(16.5, y)
        s.arrow(4.4, (ax, ay, top), rot_z=180, shaft=0.25, head=0.7)
        txt(n, 2.0, 20.5, y - 0.6)
        txt(sub, 1.4, 20.5, y + 2.4, mono=(n == 'Limit'))
    rc = B(60, 26)
    s.status_ring(11, 2.2, loc=rc + (top + 0.1,), m='ember')
    s.cyl(7, 2.2, rc + (top + 1.0,), m='cap', bevel=0.7, name='power')
    s.text('Power', 2.0, rc + (top + 2.12,), m='bone', depth=0.02)
    txt('Press to check, then power on', 1.6, 60, 42.5, align='CENTER')
    txt('Battery tip', 1.7, 4, 5, )
    txt('Drone tip', 1.7, W - 4, 5, align='RIGHT')
    txt('OffGrid', 2.2, W - 4, D - 4, align='RIGHT')
    s.usb_c((0, D / 2 + 0.3, H / 2), rot=(0, 0, -90))

    # battery tip (XT60 male) at -X
    tip_collar(s, -W / 2 - TC / 2 + 0.6, 0, H / 2, 'tip-batt')
    s.xt60((-W / 2 - TC - 6, 0, H / 2), male=True, name='in60')
    # seam: a thin ember line? no - a dark gap ring around the socket
    s.box((0.6, TW + 1.5, TH + 1.5), (-W / 2 - 0.1, 0, H / 2), m='rubber', bevel=0.5, name='seam-l')

    # drone tip at +X with lead and female XT60
    tip_collar(s, W / 2 + TC / 2 - 0.6, 0, H / 2, 'tip-drone')
    s.box((0.6, TW + 1.5, TH + 1.5), (W / 2 + 0.1, 0, H / 2), m='rubber', bevel=0.5, name='seam-r')
    end = (W / 2 + TC + 44, -14, 4.4)
    s.leads((W / 2 + TC - 0.5, 0, H / 2), end, sep=4.6, radius=1.9, sag=5, name='out-lead')
    s.xt60((end[0] + 8, end[1], 4.1), rot=(0, 0, 180), male=False, name='out60')

    # spare XT90 tip on the bench, turned so its tongue (contacts + magnets) faces the viewer
    import bpy
    fx, fy = -26.0, -D / 2 - 36.0
    parts = [tip_collar(s, 0, 0, TH / 2, 'tip-xt90'),
             s.box((12, 24, 10), (TC / 2 + 6, 0, TH / 2), m='pitch_soft', bevel=2.0, name='tongue')]
    for dy in (-5, 5):
        parts.append(s.cyl(2.0, 1.0, (TC / 2 + 12.3, dy, TH / 2), m='gold', bevel=0.2, rot=(0, 90, 0), name='contact'))
    for dy in (-10, 10):
        parts.append(s.cyl(1.4, 0.6, (TC / 2 + 12.1, dy, TH / 2), m='steel', bevel=0.1, rot=(0, 90, 0), name='magnet'))
    parts.append(s.cyl(0.8, 0.8, (TC / 2 + 12.2, 0, TH / 2 - 3), m='gold', bevel=0.1, rot=(0, 90, 0), name='id-pin'))
    parts.append(s.xt60((-TC / 2 - 10.5, 0, TH / 2), male=True, name='xt90', scale=1.35))
    parts.append(s.text('XT90', 2.2, (0, 0, TH + 0.02), m='bone', mono=True, depth=0.02, rot=(0, 0, 90)))
    e = bpy.data.objects.new('spare-tip', None)
    bpy.context.collection.objects.link(e)
    for p_ in parts:
        p_.parent = e
    e.location = (fx, fy, 0)
    e.rotation_euler = (0, 0, math.radians(235))
