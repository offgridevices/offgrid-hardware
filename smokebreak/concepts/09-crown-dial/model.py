"""09 Crown: a machined, knurled aluminium crown round a round glass display.
Turn = Limit, press the glass = Power, the Beacon Ring's node = Bind.
88 x 72 x 18 mm body, 24.5 mm at the crown."""
import math

VIEW = dict(elevation=34, azimuth=-30)

W, D, H, R = 88.0, 72.0, 18.0, 16.0
CXF, CYF = 50.0, 39.0          # crown centre in face coordinates (x right, y toward the user)
RB = 31.0                      # Beacon Ring radius
RO, RI = 22.5, 18.8            # crown outer / inner radius
CROWN_H = 6.5


def B(x, y):
    """Face coordinates (mm, y toward the user) to Blender X/Y."""
    return (x - W / 2, D / 2 - y)


def rbox(s, w, d, h, r, loc, m, edge=1.2, name='rbox'):
    """Box with plan-view corner radius r and a soft edge bevel."""
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
    bmesh.ops.bevel(bm, geom=vert, offset=r, segments=12, affect='EDGES', profile=0.5)
    bm.to_mesh(o.data)
    bm.free()
    return s._finish(o, m, bevel=edge, segments=4)


def tube(s, r_out, r_in, h, loc, m, name):
    import bpy
    o = s.cyl(r_out, h, loc, m=m, bevel=0.6, verts=128, name=name)
    cut = s.cyl(r_in, h + 4, loc, m=None, bevel=0, verts=128, name=name + '-cut')
    mod = o.modifiers.new('bore', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cut
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier='bore')
    bpy.data.objects.remove(cut, do_unlink=True)
    return o


def build(s):
    top = H
    rbox(s, W, D, H, R, (0, 0, H / 2), 'pitch_soft', edge=1.6, name='body')

    cx, cy = B(CXF, CYF)
    # Beacon Ring light pipe round the crown (lit green: on, safe), gap at 12 o'clock (+Y)
    s.status_ring(RB, 1.7, loc=(cx, cy, top + 0.15), m='green')
    # Bind key = the ring's node
    nx, ny = cx, cy + RB + 0.6
    s.torus(3.3, 0.45, (nx, ny, top + 0.2), m='green', name='bind-halo')
    s.cyl(2.8, 1.4, (nx, ny, top + 0.7), m='cap', bevel=0.4, name='bind')
    s.text('Bind', 1.7, (nx + 4.6, ny, top + 0.02), align='LEFT')

    # crown: anodised aluminium tube with knurling, on a dark gap ring
    s.cyl(RO + 1.0, 0.6, (cx, cy, top + 0.3), m='screen', bevel=0.2, name='crown-gap')
    tube(s, RO, RI, CROWN_H, (cx, cy, top + 0.6 + CROWN_H / 2), 'anodised', 'crown')
    n = 72
    for i in range(n):
        a = 2 * math.pi * i / n
        s.box((0.7, 0.9, CROWN_H - 1.6), (cx + (RO + 0.15) * math.cos(a), cy + (RO + 0.15) * math.sin(a),
                                           top + 0.6 + CROWN_H / 2),
              m='anodised', bevel=0.2, rot=(0, 0, math.degrees(a)), name='knurl')
    # glass display, sunk 0.6 mm inside the crown
    zg = top + 0.6 + CROWN_H - 0.9
    s.cyl(RI - 0.15, 1.2, (cx, cy, zg - 0.6), m='screen', bevel=0.3, name='display')
    s.text('0.42A', 3.4, (cx, cy + 0.6, zg + 0.02), m='white_led', mono=True, name='disp-amps')
    s.text('On, safe', 1.6, (cx, cy + 6.4, zg + 0.02), m='green', name='disp-state')
    s.text('16.8V 4S', 1.3, (cx, cy - 5.0, zg + 0.02), m='screen_txt', mono=True, name='disp-batt')
    for lab, ang in (('AUTO', -110), ('1', -66), ('2', -22), ('5', 22), ('10', 66), ('20', 110)):
        a = math.radians(ang)
        r = RI - 3.2
        s.text(lab, 1.0, (cx + r * math.sin(a), cy + r * math.cos(a), zg + 0.02),
               m='ember' if lab == '20' else 'white_led', mono=True, name='disp-scale')
    s.box((0.5, 0.5, 0.1), (cx + (RI - 1.3) * math.sin(math.radians(-110)), cy + (RI - 1.3) * math.cos(math.radians(-110)), zg + 0.05),
          m='white_led', bevel=0.1, name='disp-pointer')

    # face printing
    x, y = B(6, D - 7)
    s.text('Battery', 2.2, (x, y, top + 0.02), align='LEFT')
    x, y = B(10, D - 3.8)
    s.arrow(8, (x, y, top + 0.02), shaft=0.3, head=0.9)
    x, y = B(W - 6, D - 7)
    s.text('Drone', 2.2, (x, y, top + 0.02), align='RIGHT')
    x, y = B(W - 10, D - 3.8)
    s.arrow(8, (x, y, top + 0.02), shaft=0.3, head=0.9)
    x, y = B(9.5, 9)
    s.lockup(11.9, (x + 4.28, y, top + 0.05), m='bone')

    # battery side: XT60 + XT30 male, panel mounted in the left end
    x, y = B(0, 24)
    s.xt60((x - 2, y, 9), male=True, name='in60')
    x, y = B(0, 47)
    s.xt30((x - 1.5, y, 8), male=True, name='in30')
    s.box((3, 1.6, 9), (-W / 2 - 1.0, B(0, 37.5)[1], 9), m='pitch_soft', bevel=0.5, name='rib')
    # drone side: female XT60 + XT30 on 10 cm leads
    x, y = B(W, 26)
    s.leads((x - 3, y, 8), (x + 52, y - 4, 4.4), sep=5.5, radius=2.0, sag=4, name='out60-lead')
    s.xt60((x + 60, y - 4, 4.1), rot=(0, 0, 180), male=False, name='out60')
    x, y = B(W, 52)
    s.leads((x - 3, y, 7), (x + 32, y - 14, 2.8), sep=3.6, radius=1.4, sag=3, name='out30-lead')
    s.xt30((x + 37, y - 14, 2.6), rot=(0, 0, 180), male=False, name='out30')
    # USB-C in the back edge
    s.usb_c((0, D / 2 + 0.1, 9), rot=(0, 0, 90))
