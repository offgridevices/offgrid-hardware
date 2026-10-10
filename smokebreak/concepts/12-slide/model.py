"""12 Slide: one machined slider, Off -> Check -> On, with a spring-return
Bind zone past On; a Limit fader with 20 A behind a sideways gate.
114 x 58 x 16 mm body, 23.5 mm at the knob."""
import math

VIEW = dict(elevation=36, azimuth=-26)

W, D, H, R = 114.0, 58.0, 16.0, 8.0
TYF = 38.5
POS = {'Off': 19, 'Check': 39, 'On': 59, 'Bind': 79}
FX = 104
FPOS = [11, 16.5, 22, 27.5, 33, 43.5]
FLAB = ['AUTO', '1A', '2A', '5A', '10A', '20A']
GATE = 3.2


def B(x, y):
    return (x - W / 2, D / 2 - y)


def rbox(s, w, d, h, r, loc, m, edge=1.2, name='rbox'):
    import bpy
    import bmesh
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    vert = [e for e in bm.edges
            if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6 and abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-6]
    bmesh.ops.bevel(bm, geom=vert, offset=r, segments=10, affect='EDGES', profile=0.5)
    bm.to_mesh(o.data)
    bm.free()
    return s._finish(o, m, bevel=edge, segments=4)


def slot(s, xf0, yf0, xf1, yf1, w, top, name):
    """A dark slot between two face points."""
    (x0, y0), (x1, y1) = B(xf0, yf0), B(xf1, yf1)
    L = math.hypot(x1 - x0, y1 - y0) + w
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    s.box((L, w, 0.4), ((x0 + x1) / 2, (y0 + y1) / 2, top + 0.02), m=s.mat('slot', '#060504', 0.9), bevel=0.15, rot=(0, 0, ang), name=name)


def build(s):
    top = H
    rbox(s, W, D, H, R, (0, 0, H / 2), 'pitch_soft', edge=1.3, name='body')

    # 2.08" bar OLED
    x, y = B(53, 11.25)
    s.box((62, 15.5, 0.6), (x, y, top + 0.2), m=s.mat('matte glass', '#050505', 0.35), bevel=0.5, name='window')
    s.text('0.42A', 4.8, (x - 28, y - 0.4, top + 0.52), m='white_led', mono=True, align='LEFT', name='amps')
    s.text('On, safe', 1.8, (x + 0, y + 3.8, top + 0.52), m='green', align='LEFT', name='state')
    s.text('16.8V 4S  DRONE 3', 1.25, (x + 0, y + 0.2, top + 0.52), m='screen_txt', mono=True, align='LEFT', name='batt')
    s.text('LIMIT AUTO 2.0A', 1.25, (x + 0, y - 3.4, top + 0.52), m='screen_txt', mono=True, align='LEFT', name='lim')
    # Beacon Ring status light
    x, y = B(11, 12)
    s.beacon_ring(6.0, 1.5, loc=(x, y, top + 0.15), m='green')

    # main slider track, detent ticks and labels
    slot(s, POS['Off'] - 2, TYF, POS['Bind'] + 2, TYF, 3.6, top, 'track')
    for lab, xf in POS.items():
        x, y = B(xf, TYF + 7.9)
        s.box((0.3, 1.4, 0.06), (x, y, top + 0.03), m='bone', bevel=0, name='tick')
        x, y = B(xf, TYF + 12.0)
        s.text(lab, 2.1, (x, y, top + 0.02), name='pos-' + lab)
    x, y = B(POS['Bind'], TYF + 15.4)
    s.text('springs back', 1.3, (x, y, top + 0.02), m='bone')
    # zig-zag spring mark between On and Bind
    zx0, zx1 = POS['On'] + 6, POS['Bind'] - 6
    pts = [(zx0 + i * (zx1 - zx0) / 6, TYF + (7 if i % 2 else 9)) for i in range(7)]
    for (a, b), (c, d) in zip(pts, pts[1:]):
        (x0, y0), (x1, y1) = B(a, b), B(c, d)
        s.box((math.hypot(x1 - x0, y1 - y0), 0.25, 0.06), ((x0 + x1) / 2, (y0 + y1) / 2, top + 0.03), m='bone', bevel=0,
              rot=(0, 0, math.degrees(math.atan2(y1 - y0, x1 - x0))), name='spring-mark')
    x, y = B((POS['Off'] + POS['On']) / 2, TYF - 5.2)
    s.arrow(30, (x, y, top + 0.02), shaft=0.3, head=0.9)

    # the knob at On: bead-blasted aluminium block with grip grooves, on a dark stem
    x, y = B(POS['On'], TYF)
    s.box((11, 3, 2.0), (x, y, top + 1.0), m='anodised', bevel=0.4, name='stem')
    s.box((15, 12, 5.5), (x, y, top + 2.0 + 2.75), m='aluminium', bevel=1.6, name='knob')
    for i in range(-2, 3):
        s.box((0.7, 8.5, 0.5), (x + i * 2.2, y, top + 7.5), m='anodised', bevel=0.15, name='groove')

    # Limit fader with the 20 A gate
    slot(s, FX, FPOS[0] - 1.5, FX, FPOS[4] + 2.5, 3.2, top, 'fader')
    slot(s, FX, FPOS[4] + 2.5, FX + GATE, FPOS[4] + 5.0, 3.2, top, 'gate')
    slot(s, FX + GATE, FPOS[4] + 5.0, FX + GATE, FPOS[5] + 1.5, 3.2, top, 'fader20')
    for lab, yf in zip(FLAB, FPOS):
        x, y = B(FX - 4.6, yf)
        s.text(lab, 1.3, (x, y, top + 0.02), mono=True, align='RIGHT', m='ember' if lab == '20A' else 'bone')
    x, y = B(FX + 1, FPOS[0] - 4.4)
    s.text('Limit', 1.8, (x, y, top + 0.02))
    x, y = B(FX, FPOS[0])
    s.box((2.4, 2.4, 1.6), (x, y, top + 0.8), m='anodised', bevel=0.3, name='fader-stem')
    s.box((8, 6, 3.6), (x, y, top + 1.6 + 1.8), m='aluminium', bevel=1.0, name='fader-knob')

    # ends and lockup
    x, y = B(4, D - 3.2)
    s.text('Battery', 1.8, (x, y, top + 0.02), align='LEFT')
    x, y = B(FX - 12, D - 3.2)
    s.text('Drone', 1.8, (x, y, top + 0.02), align='RIGHT')
    x, y = B(4, 27)
    s.beacon_ring(1.2, 0.4, loc=(x + 1.2, y + 0.3, top + 0.05), m='bone')
    s.text('OffGrid', 1.8, (x + 3.2, y + 0.1, top + 0.02), align='LEFT', name='wordmark')

    # connectors
    x, y = B(0, 18.75)
    s.xt60((x - 2, y, 8.5), male=True, name='in60')
    x, y = B(0, 37)
    s.xt30((x - 1.5, y, 7.5), male=True, name='in30')
    x, y = B(W, 16)
    s.leads((x - 3, y, 8), (x + 52, y - 2, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 2, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = B(W, 36)
    s.leads((x - 3, y, 7), (x + 32, y - 12, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 12, 2.6), rot=(0, 0, 180), male=False, name='out30')
    s.usb_c((0, D / 2 + 0.1, 8), rot=(0, 0, 90))
