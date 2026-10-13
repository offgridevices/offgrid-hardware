"""SmokeBreak: where the battery-side plugs go.

A pack's power and balance leads leave it side by side and are short: a 3S
450 mAh pack has about 45 mm of each, a 4S 1300-1500 mAh about 60-100 mm.
So the battery's XT30/XT60 and its balance socket must sit close together,
on the same end of the case.  This script builds the current layout and
four alternatives at true size (real XT60, XT30 and JST-XH sizes), renders
each from the battery end, and measures how far every balance socket is from
the power plug a pack of that size would use.

    <bpy venv>/bin/python sides.py            # renders/*.png + reach.json

Units: mm.  Battery end at -X, drone end at +X, +Y away from the user, Z up.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SB, 'concepts', '_blender'))
sys.path.insert(0, os.path.join(SB, 'design', 'arm'))
import bpy            # noqa: E402
import studio as s    # noqa: E402
import arm            # noqa: E402  body shape, guard, ring and screen materials

OUT = os.path.join(HERE, 'renders')

# JST-XH: mouth width = (pins - 1) x 2.5 + 4.9; side entry 6.1 tall, 11.5
# deep; top entry 5.75 deep, 7.0 tall (KiCad's JST models)
def xh_w(cells):
    return cells * 2.5 + 4.9


SIDE_H, TOP_D, TOP_H = 6.1, 5.75, 7.0
XT60_W, XT60_H = 15.5, 8.2
XT30_W, XT30_H = 9.6, 5.1


class Layout:
    """One concept: body size, the plugs and sockets (world coordinates of
    each mouth's centre and the way it faces), the top-face parts."""

    def __init__(self, key, name, L, D, H, R=9.0):
        self.key, self.name, self.L, self.D, self.H, self.R = key, name, L, D, H, R
        self.xt60 = self.xt30 = None
        self.sockets = {}          # cells -> (x, y, z, kind, rot)
        self.labels = {}
        self.top = {}

    # ------------------------------------------------------------ building
    def build(self, frame):
        L, D, H = self.L, self.D, self.H
        arm.rbox(L, D, H, self.R, (0, 0, H / 2), 'pitch_soft', name='body')
        arm.rbox(L - 2.4, D - 2.4, 1.0, self.R - 1.2, (0, 0, H + 0.1), 'anodised', edge=0.4, name='face')
        # battery plugs (male, mating face out of the battery end wall)
        for spec, fn, inset in ((self.xt60, s.xt60, 4.0), (self.xt30, s.xt30, 2.5)):
            if spec:                     # body mostly inside, pins out (as on the Arm)
                x, y, z = spec
                fn((x + inset, y, z), male=True)
        tops = [(x, y, cells) for cells, (x, y, z, kind, rot) in self.sockets.items() if kind == 'top']
        if tops:                   # the well: a dark recess in the face round the top-entry sockets
            xs = [x for x, y, c in tops]
            ys = [y - xh_w(c) / 2 for x, y, c in tops] + [y + xh_w(c) / 2 for x, y, c in tops]
            s.box((max(xs) - min(xs) + TOP_D + 7.0, max(ys) - min(ys) + 4.0, 0.8),
                  ((max(xs) + min(xs)) / 2 + 1.2, (max(ys) + min(ys)) / 2, H + 0.35),
                  m=s.mat('well', '#0B0A08', 0.7), bevel=1.2, name='well')
        for cells, (x, y, z, kind, rot) in self.sockets.items():
            self.socket(cells, x, y, z, kind, rot)
        # drone side: female leads out of the far end, as on the Arm
        x = L / 2
        s.leads((x - 3, 12, 8), (x + 42, 12, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
        s.xt60((x + 50, 12, 4.1), rot=(0, 0, 180), male=False, name='out60')
        s.leads((x - 3, -12, 7), (x + 26, -18, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
        s.xt30((x + 31, -18, 2.6), rot=(0, 0, 180), male=False, name='out30')
        self.face(frame)

    def socket(self, cells, x, y, z, kind, rot):
        """A JST-XH socket as seen from outside: white housing, dark mouth,
        its size printed beside it."""
        w = xh_w(cells)
        white = s.mat('jst nylon', '#EDEAE2', 0.55)
        if kind == 'side':          # mouth faces along rot (0: -X, 90: -Y, -90: +Y)
            a = math.radians(rot)
            dx, dy = -math.cos(a), -math.sin(a)
            o = s.box((2.0, w, SIDE_H), (x, y, z), m=white, bevel=0.3, rot=(0, 0, rot), name=f'xh{cells}')
            s.box((2.1, w - 1.6, SIDE_H - 1.8), (x + dx * 0.1, y + dy * 0.1, z - 0.3), m='screen', bevel=0.2,
                  rot=(0, 0, rot), name=f'xh{cells}-mouth')
            tz = z + SIDE_H / 2 + 1.6
            if tz > self.H - 1.2:
                tz = z - SIDE_H / 2 - 1.6
            label = self.labels.get(cells, f'{cells}S')
            s.text(label, 1.5, (x + dx * 1.05, y + dy * 1.05, tz), rot=(90, 0, rot - 90), name=f'xh{cells}-label')
        else:                       # top entry: mouth up, in the well
            o = s.box((TOP_D, w, 1.2), (x, y, z), m=white, bevel=0.3, rot=(0, 0, rot), name=f'xh{cells}')
            s.box((TOP_D - 1.6, w - 1.8, 1.3), (x, y, z + 0.05), m='screen', bevel=0.2, rot=(0, 0, rot),
                  name=f'xh{cells}-mouth')
            s.text(f'{cells}S', 1.9, (x - TOP_D / 2 - 0.2, y, self.H + 0.82), rot=(0, 0, rot + 90),
                   name=f'xh{cells}-label')
        return o

    def face(self, frame):
        """Screen, Limit rocker, toggle with its ring and the closed guard."""
        t = self.top
        H = self.H
        sx, sy = t['screen']
        s.box((46, 26, 0.6), (sx, sy, H + 0.32), m=s.mat('glass black', '#050505', 0.06, coat=1.0), bevel=0.8,
              name='window')
        sm, tex = arm.screen_material(sequence=False)
        tex.image = bpy.data.images.load(os.path.join(arm.UI_FRAMES, f'f{frame:05d}.png'))
        bpy.ops.mesh.primitive_plane_add(size=1, location=(sx, sy, H + 0.66))
        o = bpy.context.active_object
        o.scale = (arm.ACTIVE[0], arm.ACTIVE[1], 1)
        s.assign(o, sm)
        rx, ry = t['rocker']
        s.box((40, 9, 2.4), (rx, ry, H + 1.4), m='brushed', bevel=1.0, name='rocker')
        tx, ty = t['toggle']
        s.status_ring(10.0, 1.8, loc=(tx, ty, H + 0.65), m=arm.ring_material(), depth=1.2, name='ring')
        s.cyl(3.0, 3.4, (tx, ty, H + 3.0), m='steel', bevel=0.3, name='bushing')
        gm = arm.guard_material()
        GW, GL, GH = 30.0, 34.0, 15.0            # across X, along Y, tall (the Arm's guard)
        s.box((GW, GL, 1.8), (tx, ty, H + GH - 0.9), m=gm, bevel=0.6, name='guard-top')
        for dx in (-GW / 2 + 0.9, GW / 2 - 0.9):
            s.box((1.8, GL, GH), (tx + dx, ty, H + GH / 2), m=gm, bevel=0.6, name='guard-wall')
        for dy in (-GL / 2 + 0.9, GL / 2 - 0.9):
            s.box((GW, 1.8, GH), (tx, ty + dy, H + GH / 2), m=gm, bevel=0.6, name='guard-lip')
        # the mark, tone on tone, centred on the front wall
        s.beacon_ring(3.4, 0.06, loc=(0, -self.D / 2 - 0.02, H / 2), rot=(90, 0, 0),
                      m=s.mat('gloss pitch', '#0E0C09', 0.08, coat=1.0), name='mark-front')

    # ------------------------------------------------------------ measuring
    def reach(self):
        """Mouth-to-mouth distance (mm) from each balance socket to the plug a
        pack of that size uses: XT30 for 2S-4S, XT60 for 4S-6S."""
        out = {}
        for cells, (x, y, z, kind, rot) in sorted(self.sockets.items()):
            row = {}
            for plug, pos, sizes in (('XT30', self.xt30, (2, 3, 4)), ('XT60', self.xt60, (4, 5, 6))):
                if pos and cells in sizes:
                    row[plug] = round(math.dist((x, y, z), pos), 1)
            out[f'{cells}S'] = row
        return out


def layouts():
    out = []

    # 0. today: plugs on the battery end, balance sockets along the back wall
    a = Layout('today', 'Today: sockets along the back', 100, 58, 18)
    a.xt60 = (-50, 8.25, 9.0)
    a.xt30 = (-50, -13.0, 8.0)
    for cells, xb in ((6, 16.93), (5, 37.03), (4, 54.53), (3, 69.61), (2, 82.19)):
        a.sockets[cells] = (xb + 3.0 - 50, 29.0, 7.55, 'side', -90)
    a.top = dict(screen=(-21.5, 8.0), rocker=(-21.5, -16.5), toggle=(20.0, -2.0))
    out.append(a)

    # A. balance well: top-entry sockets in a recess right behind the plugs
    b = Layout('well', 'A. Balance well', 100, 58, 18)
    b.xt60 = (-50, 13.0, 8.6)
    b.xt30 = (-50, -12.0, 6.5)
    xa, xb_ = -42.5, -34.0
    ys = [-17.0, -4.5, 9.5]                       # 2S 3S 4S, the small packs' row, by the XT30
    for cells, y in zip((2, 3, 4), ys):
        b.sockets[cells] = (xa, y, 18.75, 'top', 0)
    for cells, y in zip((5, 6), (-11.0, 9.5)):
        b.sockets[cells] = (xb_, y, 18.75, 'top', 0)
    b.top = dict(screen=(-4.0, 8.0), rocker=(-4.0, -16.5), toggle=(33.0, -2.0))
    out.append(b)

    # B. split level: plugs and sockets in two tiers on the battery end wall
    c = Layout('split', 'B. Split-level end wall', 86, 66, 20.5, R=5.0)
    c.xt60 = (-43, 20.0, 5.6)
    c.xt30 = (-43, 4.6, 13.9)
    # lower tier (on the board's underside): XT60, 5S, 6S; upper tier: 4S, XT30, 3S, 2S
    c.sockets[5] = (-43, 2.1, 5.1, 'side', 0)
    c.sockets[6] = (-43, -18.25, 5.1, 'side', 0)
    c.sockets[4] = (-43, 18.3, 14.4, 'side', 0)
    c.sockets[3] = (-43, -7.9, 14.4, 'side', 0)
    c.sockets[2] = (-43, -20.7, 14.4, 'side', 0)
    c.top = dict(screen=(-8.0, 13.0), rocker=(-8.0, -15.5), toggle=(24.0, -1.0))
    out.append(c)

    # C. one 6S socket beside the plugs, shaped so a smaller plug sits at pin 1
    d = Layout('single', 'C. One smart socket', 92, 62, 18, R=6.0)
    d.xt60 = (-46, 14.0, 9.0)
    d.xt30 = (-46, -1.4, 8.0)
    d.sockets[6] = (-46, -17.0, 7.55, 'side', 0)
    d.labels[6] = '2S-6S  black wire this end >'
    d.top = dict(screen=(-14.0, 10.0), rocker=(-14.0, -18.0), toggle=(26.0, -2.0))
    out.append(d)

    # D. corner wrap: XT60, XT30 and 2S on the end, 3S-6S round the corner
    e = Layout('corner', 'D. Wrap round the corner', 100, 58, 18)
    e.xt60 = (-50, 11.0, 9.0)
    e.xt30 = (-50, -6.0, 8.0)
    e.sockets[2] = (-50, -16.6, 7.55, 'side', 0)
    for cells, x in ((3, -34.5), (4, -19.9), (5, -2.3), (6, 17.6)):
        e.sockets[cells] = (x, 29.0, 7.55, 'side', -90)
    e.top = dict(screen=(-21.5, 6.0), rocker=(-21.5, -16.5), toggle=(22.0, -4.0))
    out.append(e)
    return out


def render(lay, frame):
    sc = s.reset()
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.cycles.samples = 48
    lay.build(frame)
    cam, pivot = s.stage(elevation=22, azimuth=-118, lens=120)
    cam.data.shift_x, cam.data.shift_y = 0.0, 0.0
    pivot.location.x -= lay.L * 0.18          # aim at the battery end
    pivot.location.z = lay.H * 0.55
    sc.render.filepath = os.path.join(OUT, f'{lay.key}.png')
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    frame = int((arm.T0 + 0.8) * arm.FPS)        # the SAFE screen
    report = {}
    only = sys.argv[1:]
    for lay in layouts():
        report[lay.key] = dict(name=lay.name, size=[lay.L, lay.D, lay.H], reach=lay.reach())
        if not only or lay.key in only:
            render(lay, frame)
    json.dump(report, open(os.path.join(HERE, 'reach.json'), 'w'), indent=1)
    print(json.dumps(report, indent=1))
