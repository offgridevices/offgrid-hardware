"""01 Baton - two narrow boards in a Ø32 x 140 mm anodised aluminium tube.
Battery end (-X): XT60 + XT30 male in the end cap. Drone end (+X): rubber boot,
two female leads and USB-C. Everything you touch is on the flat top spine."""
import math

VIEW = dict(elevation=30, azimuth=-38)

R = 16.0            # tube radius
AX = 13.0           # axis height: the flat foot (axis - 13) sits on z = 0
TOP = AX + 13.0     # the spine (top flat), z = 26
X0, XC, XB, X1 = -70.0, -56.0, 54.0, 70.0   # battery face, cap joint, boot start, drone end


def _cut_flats(bpy, o, s, x0, x1):
    """Mill the top spine and the foot flat into a round part."""
    for zc in (TOP + 10, AX - 13 - 10):
        c = s.box((x1 - x0 + 10, 60, 20), ((x0 + x1) / 2, 0, zc), m=None, bevel=0, name='cutter')
        mod = o.modifiers.new('flat', 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = c
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(c, do_unlink=True)
    b = o.modifiers.new('bevel', 'BEVEL')
    b.width, b.segments, b.limit_method = 0.7, 3, 'ANGLE'
    return o


def build(s):
    import bpy
    # body: anodised tube, printed end cap, rubber boot
    body = s.cyl(R, XB - XC, ((XB + XC) / 2, 0, AX), m='anodised', bevel=0, rot=(0, 90, 0), verts=128, name='tube')
    _cut_flats(bpy, body, s, XC, XB)
    cap = s.cyl(R, XC - X0, ((XC + X0) / 2, 0, AX), m='pitch_soft', bevel=0, rot=(0, 90, 0), verts=128, name='cap')
    _cut_flats(bpy, cap, s, X0, XC)
    bpy.ops.mesh.primitive_cone_add(radius1=R, radius2=9, depth=X1 - XB, vertices=96,
                                    location=((X1 + XB) / 2, 0, AX), rotation=(0, math.radians(90), 0))
    boot = bpy.context.active_object
    boot.name = 'boot'
    s.assign(boot, 'rubber')
    c = s.box((40, 60, 20), ((X1 + XB) / 2, 0, -10), m=None, bevel=0, name='cutter')
    mod = boot.modifiers.new('foot', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = c
    bpy.context.view_layer.objects.active = boot
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(c, do_unlink=True)

    t = TOP + 0.02
    # battery label + arrow into the tube (on the cap's spine)
    s.text('Battery', 2.0, (X0 + 1.5, 4.0, t), align='LEFT')
    s.arrow(9, (X0 + 7.0, 0.5, t), rot_z=0)
    # screen window: 1.14" IPS under glass
    s.box((34, 16, 0.6), (-34, 0, TOP + 0.1), m=s.mat('ips glass', '#060606', 0.45), bevel=0.5, name='window')
    s.text('16.8V 4S', 3.6, (-35, 2.8, TOP + 0.45), m=s.mat('ips text', s.BONE, 0.5, emit=s.BONE, strength=1.0), mono=True)
    s.text('LIMIT AUTO', 1.7, (-40.5, -2.0, TOP + 0.45), m=s.mat('ips text', s.BONE, 0.5, emit=s.BONE, strength=1.0), mono=True)
    s.text('Press the ring', 1.7, (-40.0, -5.0, TOP + 0.45), m=s.mat('ips ember', s.EMBER, 0.5, emit=s.EMBER, strength=1.2))
    # Power in the Beacon Ring
    px = -8.0
    s.cyl(8.6, 0.3, (px, 0, TOP + 0.1), m='screen', bevel=0, name='ring-well')
    s.status_ring(6.0, 1.7, loc=(px, -0.6, TOP + 0.4), m='ember')
    s.cyl(3.9, 1.8, (px, -0.6, TOP + 0.9), m='brushed', bevel=0.5, name='power')
    s.text('Power', 1.5, (px, -8.0, t))
    # Bind
    s.cyl(2.7, 1.2, (6, 0, TOP + 0.6), m='brushed', bevel=0.4, name='bind')
    s.text('Bind', 1.5, (6, -5.2, t))
    # Limit slider: slot AUTO..10, dog-leg gate to 20
    s.box((18.6, 2.6, 0.5), (26, 0, TOP + 0.05), m='screen', bevel=0.3, name='slot')
    s.box((4.6, 2.6, 0.5), (36.6, 1.8, TOP + 0.05), m='screen', bevel=0.3, rot=(0, 0, -55), name='slot-gate')
    s.box((4.0, 2.6, 0.5), (39.8, 3.6, TOP + 0.05), m='screen', bevel=0.3, name='slot-20')
    s.box((4.8, 4.4, 1.8), (17, 0, TOP + 0.9), m='brushed', bevel=0.8, name='slider')
    for lab, x in (('AUTO', 17), ('1', 21.5), ('2', 26), ('5', 30.5), ('10', 35)):
        s.text(lab, 1.4, (x, -4.6, t), mono=True)
    s.text('20', 1.4, (41, 6.4, t), m='ember', mono=True)
    s.text('Props off', 1.2, (41, -4.6, t), m='ember')
    s.text('Limit', 1.6, (15, 4.8, t), align='LEFT')
    # drone label + arrow out
    s.text('Drone', 2.0, (46, 4.0, t), align='LEFT')
    s.arrow(8, (49.5, 0.5, t), rot_z=0)
    # battery end: XT60 male over XT30 male, rib between (the board edge)
    s.xt60((X0 - 4 + 8, 0, AX + 4.3), male=True, name='in60')
    s.xt30((X0 - 3 + 5, 0, AX - 5.0), male=True, name='in30')
    s.box((1.2, 19, 1.4), (X0 - 0.6, 0, AX - 1.2), m='pitch_soft', bevel=0.3, name='rib')
    # drone end: USB-C above the leads
    s.usb_c((X1 + 0.3, 0, AX + 5.5), rot=(0, 0, 180))
    # leads: XT60 (14 AWG) and XT30, curving forward onto the bench
    for dy, m in ((-2.1, 'red_wire'), (2.1, 'black_wire')):
        s.tube_path([(X1 - 2, dy, AX - 1.5), (X1 + 20, dy, AX - 2), (X1 + 30, dy - 25, 2.2), (X1 + 20, dy - 58, 1.9)],
                    1.8, m=m, name='lead60')
    s.xt60((X1 + 20, -58 - 8 - 1.5, 4.1), rot=(0, 0, 90), male=False, name='out60')
    for dy, m in ((-1.4, 'red_wire'), (1.4, 'black_wire')):
        s.tube_path([(X1 - 2, dy + 2.5, AX - 4.5), (X1 + 26, dy + 2.5, AX - 4), (X1 + 50, dy - 10, 1.6), (X1 + 52, dy - 30, 1.4)],
                    1.3, m=m, name='lead30')
    s.xt30((X1 + 52, -30 - 5 - 1.4, 2.6), rot=(0, 0, 90), male=False, name='out30')
