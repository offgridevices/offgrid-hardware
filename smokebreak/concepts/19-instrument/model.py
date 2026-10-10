"""19 - Instrument: the board is the hero, suspended in a smoked glass shell on
a machined aluminium base; steel hi-fi keys on the front edge."""
import math

VIEW = dict(elevation=30, azimuth=-32)

W, D = 96.0, 64.0
ZB, ZT = 8.0, 26.0


def B(x, y):
    return (x - W / 2, D / 2 - y)


def build(s):
    # machined aluminium base (dark anodised), 8 mm
    s.box((W, D, ZB), (0, 0, ZB / 2), m=s.mat('graphite anodised', '#3A3834', 0.35, 0.9), bevel=1.2, name='base')
    # rubber feet
    for fx, fy in ((-38, -22), (38, -22), (-38, 22), (38, 22)):
        s.cyl(4, 0.6, (fx, fy, -0.2), m='rubber', bevel=0.2, name='foot')

    # ---- power board on a thermal pad
    zp = ZB + 0.4
    s.box((88, 56, 1.6), (0, 0, zp + 0.8), m='pcb', bevel=0.4, name='power-board')
    top = zp + 1.6

    def comp(x, y, w, d, h, m, name='part'):
        cx, cy = B(x + w / 2, y + d / 2)
        return s.box((w, d, h), (cx, cy, top + h / 2), m=m, bevel=min(0.3, h / 3), name=name)

    comp(50, 10, 33, 15, 0.08, 'copper', 'pour-a')
    comp(50, 34, 36, 17, 0.08, 'copper', 'pour-b')
    comp(12, 48, 34, 6, 0.08, 'copper', 'pour-c')
    comp(55, 18, 5, 6, 1.1, 'pitch', 'fet-a')
    comp(63, 18, 5, 6, 1.1, 'pitch', 'fet-b')
    comp(72, 18.5, 6.3, 3.2, 0.7, 'pitch', 'shunt')
    for i in range(4):
        comp(54 + i * 8, 38, 6.3, 3.2, 0.7, 'pitch', 'pulse-r')
    comp(54, 44.5, 5.4, 3.6, 2.2, 'pitch', 'tvs')
    comp(66, 44.5, 4.9, 3.0, 1.0, 'pitch', 'driver')
    comp(75, 44, 4, 4, 2.0, s.mat('inductor', '#4A4A4A', 0.5), 'inductor')
    for y in (16, 22, 40, 46):
        comp(85, y - 2, 6, 4, 0.1, 'gold', 'pad')
    s.text('SMOKEBREAK REV 1.0  ·  2 OZ', 1.3, B(26, 57.5) + (top + 0.01,), m='bone', mono=True, depth=0.01)

    # ---- logic board on brass standoffs, OLED close under the glass
    brass = s.mat('brass', '#B08D4A', 0.3, 1.0)
    for sx, sy in ((9, 12), (43, 12), (9, 42), (43, 42)):
        bx, by = B(sx, sy)
        s.cyl(1.6, 9.0, (bx, by, top + 4.5), m=brass, bevel=0.2, verts=24, name='standoff')
    zl = top + 9.0
    lx, ly = B(4 + 21, 6 + 18)
    s.box((42, 36, 1.2), (lx, ly, zl + 0.6), m='pcb', bevel=0.3, name='logic-board')
    # header between boards
    hx, hy = B(26, 44)
    s.box((10, 2.5, 9.0), (hx, hy, top + 4.5), m='pitch', bevel=0.2, name='b2b-header')
    s.screen(30, 19, ('ON 0.42A', 'DRONE 3'), loc=B(12 + 15, 17 + 9.5) + (zl + 1.2 + 2.2,), name='oled')
    s.box((3, 9, 3.2), B(26.5, 4) + (zl + 2.8,), m='usb', bevel=0.8, name='usb-recept')
    s.usb_c(B(26.5, -0.2) + (zl + 2.8,), rot=(0, 0, -90))

    # ---- smoked glass shell (hollow), etched + edge-lit Beacon Ring
    import bpy
    shell = s.box((W - 0.4, D - 0.4, ZT - ZB), (0, 0, (ZB + ZT) / 2), m=s.mat('smoke glass', '#241F1A', 0.18,
                  coat=0.25, alpha=0.55), bevel=2.0, name='shell')
    so = shell.modifiers.new('solid', 'SOLIDIFY')
    so.thickness = 2.0
    so.offset = -1
    rx, ry = B(70, 30)
    s.beacon_ring(13, 1.9, loc=(rx, ry, ZT + 0.05), m='ember')

    def glass_txt(t, size, x, y, align='CENTER', mono=False):
        s.text(t, size, B(x, y) + (ZT + 0.02,), m='bone', align=align, mono=mono, depth=0.01)

    for x, lab in ((54, 'Bind'), (70, 'Power'), (86, 'Limit')):
        glass_txt(lab, 1.9, x, D - 4.0)
        ax, ay = B(x, D - 1.6)
        s.arrow(2.4, (ax, ay, ZT + 0.02), rot_z=-90, shaft=0.25, head=0.6)
    glass_txt('OffGrid', 2.2, 12, D - 4.0, align='LEFT')
    glass_txt('Battery', 1.7, 4, 6, align='LEFT')
    glass_txt('Drone', 1.7, W - 4, 6, align='RIGHT')

    # ---- machined steel keys on the base front face
    for x, r in ((54, 3.4), (70, 5.0), (86, 3.4)):
        bx, _ = B(x, 0)
        s.cyl(r, 2.2, (bx, -D / 2 - 0.6, 4.0), m='brushed', bevel=0.5, rot=(90, 0, 0), name='key')

    # ---- connectors: battery male through the left wall, drone leads out the right
    s.xt60((-W / 2 - 3.5, 10.25, 13.2), male=True, name='in60')
    s.xt30((-W / 2 - 2.5, -13.0, 12.0), male=True, name='in30')
    for y, plug, nm in ((14.0, 'xt30', 'out30'), (-10.0, 'xt60', 'out60')):
        s.cyl(3.4, 3.0, (W / 2 + 0.8, y, 15.0), m='rubber', bevel=0.6, rot=(0, 90, 0), name=nm + '-grommet')
        end = (W / 2 + 44, y - 12, 4.4)
        s.leads((W / 2 + 2.2, y, 15.0), end, sep=4.6, radius=1.9, sag=5, name=nm + '-lead')
        if plug == 'xt60':
            s.xt60((end[0] + 8, end[1], 4.1), rot=(0, 0, 180), male=False, name=nm)
        else:
            s.xt30((end[0] + 5, end[1], 2.6), rot=(0, 0, 180), male=False, name=nm)
