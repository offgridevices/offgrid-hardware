"""14 Build Mat - the smoke stopper is the corner of a silicone build mat.

400 x 260 x 3 mm mat, centred on the origin. Pod (96 x 64 x 14 mm, machined)
in the front-right corner; battery bay behind it; drone circle on the left;
the drone leads run in a moulded groove from the pod to the drone.
"""
import math

VIEW = dict(elevation=40, azimuth=-18)

MW, MD, MT = 400.0, 260.0, 3.0
PW, PD, PH = 96.0, 64.0, 14.0
PC = (138.0, -84.0)                 # pod centre (x, y)
BAY = (138.0, 29.0, 84.0, 46.0)     # bay centre x, y, w, d
DZ = (-62.0, 6.0, 104.0)            # drone circle


def flat_curve(s, pts, r, m, name, zscale=0.15):
    o = s.tube_path(pts, r, m=m, name=name)
    o.scale = (1, 1, zscale)
    return o


def drone(s, cx, cy, z):
    arm = s.mat('carbon', '#25231f', 0.45)
    for ang in (45, 135, 225, 315):
        a = math.radians(ang)
        L = 112
        s.box((L, 12, 4), (cx + math.cos(a) * L / 2, cy + math.sin(a) * L / 2, z + 2), m=arm, bevel=1.2,
              rot=(0, 0, ang), name='arm')
        mx, my = cx + math.cos(a) * L, cy + math.sin(a) * L
        s.cyl(14, 16, (mx, my, z + 12), m=s.mat('motor', '#3b3731', 0.35, 0.6), bevel=1.0, name='motor')
        s.cyl(2.5, 6, (mx, my, z + 22), m='steel', bevel=0.3, name='shaft')
    s.box((36, 52, 20), (cx, cy, z + 14), m=s.mat('stack', '#34302a', 0.5), bevel=2.0, name='stack')
    s.box((42, 76, 3), (cx, cy, z + 25.5), m=arm, bevel=1.0, name='top-plate')
    s.box((22, 10, 14), (cx, cy + 34, z + 34), m='rubber', bevel=1.5, name='camera')


def build(s):
    silicone = s.mat('platinum silicone', '#24211C', 0.82)
    s.box((MW, MD, MT), (0, 0, MT / 2), m=silicone, bevel=6.0, name='mat')
    top = MT

    # --- printed marks (Bone)
    fy = -MD / 2 + 9
    s.text('1 Battery in the bay   →   2 Drone on the circle   →   3 Press Power', 4.2,
           (-185, fy, top + 0.02), align='LEFT', name='steps')
    s.lockup(39.1, (144.0, MD / 2 - 13, top + 0.05), m='bone')
    s.torus(DZ[2], 0.5, (DZ[0], DZ[1], top + 0.05), m='bone', name='drone-circle').scale = (1, 1, 0.1)
    s.text('Drone here  ·  props off', 4.5, (DZ[0], DZ[1] - DZ[2] - 8, top + 0.02), name='dz-t')
    bx, by, bw, bd = BAY
    s.text('Battery', 4.5, (bx - bw / 2, by + bd / 2 + 9, top + 0.02), align='LEFT', name='bay-t')
    # battery bay rim (raised silicone)
    s.box((bw + 6, 3, 6), (bx, by + bd / 2 + 1.5, top + 3), m=silicone, bevel=1.2, name='rim-back')
    s.box((3, bd + 6, 6), (bx - bw / 2 - 1.5, by, top + 3), m=silicone, bevel=1.2, name='rim-left')
    s.box((3, bd + 6, 6), (bx + bw / 2 + 1.5, by, top + 3), m=silicone, bevel=1.2, name='rim-right')

    # --- moulded groove from the pod's left side to the drone circle
    g = [(PC[0] - PW / 2, -74, top), (60, -70, top), (34, -56, top), (20, -34, top), (6, -16, top)]
    flat_curve(s, g, 5.0, s.mat('groove', '#121110', 0.9), 'groove')
    s.tube_path([(PC[0] - PW / 2 - 2, -74, top + 7), (60, -70, top + 3.2), (34, -56, top + 3.2),
                 (20, -34, top + 3.2), (6, -16, top + 8), (-30, 0, top + 18)], 2.6, m='black_wire', name='drone-lead')

    # --- the pod
    px, py = PC
    z0 = top
    s.box((PW, PD, PH), (px, py, z0 + PH / 2), m='anodised', bevel=4.0, name='pod')
    t = z0 + PH
    s.box((88, 31, 0.6), (px, py + 14, t + 0.1), m='screen', bevel=1.0, name='glass')
    s.screen(44, 24, ('16.8V  4S', 'Drone 3'), loc=(px - 19, py + 14, t + 0.45))
    s.status_ring(10.0, 2.6, loc=(px + 25.5, py + 13, t + 0.6), m='ember')
    s.cyl(6.6, 2.6, (px + 25.5, py + 13, t + 1.2), m='cap', bevel=0.8, name='power')
    s.text('Power', 1.8, (px + 25.5, py + 13, t + 2.55), name='power-t')
    # Limit: six direct-select keys, Bind at the end
    s.text('Limit · tap the one you want', 1.7, (px - 43, py - 7, t + 0.02), align='LEFT', name='lim-t')
    for i, lab in enumerate(('AUTO', '1', '2', '5', '10', '20')):
        kx = px - 48 + 5 + 10.6 / 2 + i * 11.8
        s.box((10.6, 12, 1.8), (kx, py - 17, t + 0.6), m='cap', bevel=0.8, name='lim-' + lab)
        s.text(lab, 2.4 if lab != 'AUTO' else 1.8, (kx, py - 19, t + 1.52), mono=True, name='lim-t-' + lab)
        s.sphere(0.8, (kx, py - 13.5, t + 1.5), m='green' if i == 0 else 'cap', name='lim-led')
        if lab == '20':
            s.box((11.6, 13, 0.5), (kx, py - 17, t + 0.05), m='ember', bevel=0.4, name='lim-20-rim')
    s.box((13, 12, 1.8), (px + 36.5, py - 17, t + 0.6), m='cap', bevel=0.8, name='bind')
    s.text('Bind', 2.0, (px + 36.5, py - 17, t + 1.52), name='bind-t')
    # USB-C on the right end, drone-lead grommet on the left end
    s.usb_c((px + PW / 2 + 0.3, py, z0 + 7), rot=(0, 0, 180))
    s.cyl(4.0, 3.0, (px - PW / 2 - 1.0, -74 - 0 + 0, z0 + 7), m='rubber', bevel=0.6, rot=(0, 90, 0), name='grommet')

    # --- battery in its bay, lead into the pod's back (male XT60 there)
    s.box((75, 35, 35), (bx, by + 2, top + 17.5), m=s.mat('lipo', '#33404A', 0.55), bevel=2.0, name='lipo')
    s.text('4S 1500', 6.0, (bx, by + 2, top + 35.05), m=s.mat('lipo-t', '#C8D0D6', 0.6), mono=True, name='lipo-t')
    yb = py + PD / 2
    s.xt60((px - 20, yb - 3, z0 + 7), rot=(0, 0, -90), male=True, name='in60')
    s.xt30((px, yb - 1, z0 + 6), rot=(0, 0, -90), male=True, name='in30')
    s.xt60((px - 20, yb + 12, z0 + 7), rot=(0, 0, 90), male=False, name='batt-plug')
    for dx, m in ((-2.5, 'red_wire'), (2.5, 'black_wire')):
        s.tube_path([(px - 20 + dx, yb + 20, z0 + 7), (px - 20 + dx, yb + 26, z0 + 4), (bx - 26 + dx, by - 22, top + 4),
                     (bx - 26 + dx, by - 15, top + 16)], 2.0, m=m, name='batt-lead')

    # --- a 5-inch quad on the circle, props off, for scale
    drone(s, DZ[0], DZ[1], top)
