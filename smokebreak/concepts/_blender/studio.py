"""SmokeBreak concept studio: a shared Blender (bpy) kit for modelling and
rendering the industrial-design concepts the same way, so they can be
compared side by side.

Each concept has a `model.py` beside its `concept.md` that defines

    def build(s):            # s is this module
        ...                  # make the product, centred on the origin,
                             # resting on z = 0, units = millimetres
        return [objects...]  # optional

and is rendered with

    python render_concept.py <concept folder> [--video] [--quick]

Units: 1 Blender unit = 1 mm.  +X is the product's length (battery end at
-X, drone end at +X), +Y away from the viewer, +Z up.
"""
import math
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('SB_FONTS', '/tmp/claude-0/-home-user-offgrid-hardware/'
                       'bb4d9657-83a6-5d9a-b4a3-ba3efc9cb84f/scratchpad/ref')

# ----------------------------------------------------------------- colours
def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)

PITCH, BONE, EMBER = '#1B1813', '#F1ECE0', '#FF6A00'
GREEN, RED = '#4caf50', '#e53935'
BACKDROP = '#E9E4D8'
AMASS_YELLOW = '#E2A90F'

# ----------------------------------------------------------------- scene
_mats = {}

def reset():
    _mats.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.001
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 32
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    world = bpy.data.worlds.new('world')
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs[0].default_value = srgb(BACKDROP)
    bg.inputs[1].default_value = 0.35
    return sc


def mat(name, colour='#808080', rough=0.5, metal=0.0, emit=None, strength=0.0,
        coat=0.0, transmission=0.0, alpha=1.0, ior=1.45):
    key = (name, colour, rough, metal, emit, strength, coat, transmission, alpha)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = srgb(colour)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['IOR'].default_value = ior
    if coat:
        p.inputs['Coat Weight'].default_value = coat
    if transmission:
        p.inputs['Transmission Weight'].default_value = transmission
    if alpha < 1:
        p.inputs['Alpha'].default_value = alpha
    if emit:
        p.inputs['Emission Color'].default_value = srgb(emit)
        p.inputs['Emission Strength'].default_value = strength
    _mats[key] = m
    return m


# a library of the materials the concepts share
def M(kind):
    return {
        'pitch':      lambda: mat('pitch matte', PITCH, 0.62),                 # moulded / printed black
        'pitch_soft': lambda: mat('pitch soft-touch', '#211D18', 0.85),        # soft-touch / MJF
        'anodised':   lambda: mat('black anodised Al', '#1E1C1A', 0.38, 0.85),
        'aluminium':  lambda: mat('bead-blasted Al', '#B9B6B0', 0.42, 1.0),
        'brushed':    lambda: mat('brushed Al', '#C9C6C0', 0.28, 1.0),
        'bone':       lambda: mat('bone', BONE, 0.55),
        'ember':      lambda: mat('ember light', EMBER, 0.4, emit=EMBER, strength=6.0),
        'ember_dim':  lambda: mat('ember paint', EMBER, 0.45),
        'green':      lambda: mat('green light', GREEN, 0.4, emit=GREEN, strength=5.0),
        'red':        lambda: mat('red light', RED, 0.4, emit=RED, strength=5.0),
        'white_led':  lambda: mat('white light', '#FFF6E8', 0.4, emit='#FFF6E8', strength=5.0),
        'glass':      lambda: mat('glass', '#FFFFFF', 0.02, transmission=1.0, ior=1.5),
        'smoked':     lambda: mat('smoked glass', '#8C8278', 0.05, transmission=1.0, ior=1.5),
        'frosted':    lambda: mat('frosted pipe', '#FFFFFF', 0.45, transmission=0.9),
        'screen':     lambda: mat('screen black', '#050505', 0.15, coat=1.0),
        'screen_txt': lambda: mat('screen text', '#9FE0A0', 0.5, emit='#9FE0A0', strength=1.2),
        'xt':         lambda: mat('amass nylon', AMASS_YELLOW, 0.5),
        'gold':       lambda: mat('gold', '#D4A84A', 0.25, 1.0),
        'red_wire':   lambda: mat('red silicone', '#B5302B', 0.55),
        'black_wire': lambda: mat('black silicone', '#1D1D1D', 0.55),
        'rubber':     lambda: mat('rubber', '#141414', 0.9),
        'pcb':        lambda: mat('pcb pitch', PITCH, 0.35, coat=0.3),
        'copper':     lambda: mat('enig', '#D9B45A', 0.3, 1.0),
        'cap':        lambda: mat('button cap', '#2A2620', 0.5),
        'usb':        lambda: mat('usb steel', '#9A9A9A', 0.3, 1.0),
        'leather':    lambda: mat('leather', '#5A3B26', 0.7),
        'wood':       lambda: mat('walnut', '#5B3A24', 0.55),
        'mat_green':  lambda: mat('cutting mat', '#2F3B33', 0.8),
        'eink':       lambda: mat('e-ink', '#D9D6CC', 0.8),
        'eink_txt':   lambda: mat('e-ink ink', '#1A1A1A', 0.8),
        'steel':      lambda: mat('steel', '#8A8C8F', 0.35, 1.0),
    }[kind]()


def assign(o, m):
    if isinstance(m, str):
        m = M(m)
    o.data.materials.clear()
    o.data.materials.append(m)
    return o


# ----------------------------------------------------------------- shapes
def _finish(o, m, bevel=0.0, segments=4, smooth=True):
    if bevel:
        b = o.modifiers.new('bevel', 'BEVEL')
        b.width = bevel
        b.segments = segments
        b.limit_method = 'ANGLE'
        b.harden_normals = False
    if smooth:
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        except Exception:
            for p in o.data.polygons:
                p.use_smooth = True
    if m is not None:
        assign(o, m)
    return o


def box(size, loc=(0, 0, 0), m='pitch', bevel=1.0, rot=(0, 0, 0), name='box'):
    """Box of `size` (x, y, z) mm centred at loc, rounded by `bevel` mm."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=[math.radians(a) for a in rot])
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return _finish(o, m, bevel)


def cyl(r, h, loc=(0, 0, 0), m='pitch', bevel=0.5, rot=(0, 0, 0), verts=96, name='cyl'):
    """Cylinder radius r, height h along its local Z, centred at loc."""
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts, location=loc,
                                        rotation=[math.radians(a) for a in rot])
    o = bpy.context.active_object
    o.name = name
    return _finish(o, m, bevel)


def sphere(r, loc=(0, 0, 0), m='pitch', name='sphere'):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
    o = bpy.context.active_object
    o.name = name
    return _finish(o, m, 0)


def torus(R, r, loc=(0, 0, 0), m='ember', rot=(0, 0, 0), name='torus'):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc,
                                     rotation=[math.radians(a) for a in rot],
                                     major_segments=96, minor_segments=24)
    o = bpy.context.active_object
    o.name = name
    return _finish(o, m, 0)


def tube_path(points, radius, m='red_wire', name='wire', resolution=12):
    """A round cable along a smooth path through `points` (mm)."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new('NURBS')
    sp.points.add(len(points) - 1)
    for p, xyz in zip(sp.points, points):
        p.co = (*xyz, 1)
    sp.order_u = min(4, len(points))
    sp.use_endpoint_u = True
    sp.resolution_u = resolution
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    assign(o, m)
    return o


def beacon_ring(radius, thickness, loc=(0, 0, 0), rot=(0, 0, 0), m='ember', node=True, gap_deg=48,
                name='beacon'):
    """The OffGrid Beacon Ring as a 3D light pipe: a ring open at 12 o'clock
    (local +Y) with the node dot in the gap.  Lies in its local XY plane."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = thickness / 2
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    n = 120
    a0 = math.radians(90 + gap_deg / 2)
    a1 = math.radians(90 + 360 - gap_deg / 2)
    sp.points.add(n)
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        sp.points[i].co = (radius * math.cos(a), radius * math.sin(a), 0, 1)
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    assign(o, m)
    parts = [o]
    if node:
        # brand proportions: node r 17 vs ring r 58 / stroke 22
        nr = radius * 17 / 58
        nd = sphere(nr, (0, radius + nr * 0.95, 0), m=m, name=name + '-node')
        nd.scale = (1, 1, max(0.25, thickness / (2 * nr)))
        parts.append(nd)
    e = bpy.data.objects.new(name + '-root', None)
    bpy.context.collection.objects.link(e)
    for p in parts:
        p.parent = e
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    return e


def text(s, size, loc=(0, 0, 0), rot=(0, 0, 0), m='bone', mono=False, weight=None,
         align='CENTER', depth=0.04, name='text'):
    """Flat text, `size` = cap-ish height in mm, lying in local XY facing +Z."""
    font_file = os.path.join(FONTS, 'JetBrainsMono-VariableFont.ttf' if mono else
                             'InstrumentSans-VariableFont.ttf')
    key = font_file
    f = bpy.data.fonts.get(key)
    if f is None:
        try:
            f = bpy.data.fonts.load(font_file)
            f.name = key
        except Exception:
            f = None
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = s
    if f:
        cu.font = f
    cu.size = size * 1.4
    cu.extrude = depth
    cu.align_x = align
    cu.align_y = 'CENTER'
    o = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    assign(o, m)
    return o


def arrow(length, loc=(0, 0, 0), rot_z=0, shaft=0.35, head=1.2, m='bone', z_rot_extra=(0, 0), name='arrow'):
    """The brand arrow (thin flat shaft, solid head) lying flat, pointing +X
    before rotation by rot_z degrees about Z."""
    hl = head * 1.4
    s = box((length - hl, shaft, 0.06), (-(hl) / 2, 0, 0), m=m, bevel=0, name=name + '-shaft')
    me = bpy.data.meshes.new(name + '-head')
    x1 = length / 2
    verts = [(x1, 0, 0), (x1 - hl, head, 0), (x1 - hl, -head, 0),
             (x1, 0, 0.06), (x1 - hl, head, 0.06), (x1 - hl, -head, 0.06)]
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    me.from_pydata(verts, [], faces)
    h = bpy.data.objects.new(name + '-head', me)
    bpy.context.collection.objects.link(h)
    assign(h, m)
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    s.parent = e
    h.parent = e
    e.location = loc
    e.rotation_euler = (math.radians(z_rot_extra[0]), math.radians(z_rot_extra[1]), math.radians(rot_z))
    return e


def screen(w, h, lines=('16.8V  4S', 'ON  0.42A'), loc=(0, 0, 0), rot=(0, 0, 0), name='screen', round_=False):
    """A display: black glass with glowing text, lying flat facing +Z."""
    parts = []
    if round_:
        g = cyl(w / 2, 0.6, (0, 0, 0), m='screen', bevel=0.2, name=name)
    else:
        g = box((w, h, 0.6), (0, 0, 0), m='screen', bevel=0.3, name=name)
    parts.append(g)
    n = len(lines)
    for i, ln in enumerate(lines):
        sz = (h * 0.55 / max(n, 1)) * (1.0 if i == 0 else 0.8)
        y = h * 0.28 - i * h * 0.6 / max(n - 1, 1) if n > 1 else 0
        parts.append(text(ln, sz, (0, y, 0.32), m='screen_txt', mono=True, name=name + f'-l{i}'))
    e = bpy.data.objects.new(name + '-root', None)
    bpy.context.collection.objects.link(e)
    for p in parts:
        p.parent = e
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    return e


def xt60(loc=(0, 0, 0), rot=(0, 0, 0), male=True, name='xt60', scale=1.0):
    """Simplified Amass XT60 plug/receptacle: 15.5 x 8.2 x 16 mm yellow body
    with the chamfered corner, mating face toward local -X."""
    s = scale
    parts = [box((16 * s, 15.5 * s, 8.2 * s), (0, 0, 0), m='xt', bevel=0.6 * s, name=name + '-body')]
    # chamfer hint: dark wedge on one corner
    parts.append(box((16.2 * s, 3 * s, 3 * s), (0, 7.2 * s, 3.6 * s), m='xt', bevel=0.4 * s,
                     rot=(45, 0, 0), name=name + '-chamfer'))
    for y in (-3.6, 3.6):
        if male:
            parts.append(cyl(1.75 * s, 4 * s, (-9.5 * s, y * s, 0), m='gold', bevel=0.2,
                             rot=(0, 90, 0), name=name + '-pin'))
        else:
            parts.append(cyl(2.4 * s, 0.4 * s, (-8.1 * s, y * s, 0), m='gold', bevel=0.1,
                             rot=(0, 90, 0), name=name + '-socket'))
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    for p in parts:
        p.parent = e
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    return e


def xt30(loc=(0, 0, 0), rot=(0, 0, 0), male=True, name='xt30'):
    return xt60(loc, rot, male, name, scale=0.62)


def usb_c(loc=(0, 0, 0), rot=(0, 0, 0), name='usbc'):
    """USB-C opening, 9 x 3.3 mm, facing local -X."""
    o = box((1.0, 9.0, 3.3), loc, m='usb', bevel=1.4, rot=rot, name=name)
    i = box((1.2, 7.0, 1.6), (loc[0] - 0.2, loc[1], loc[2]), m='screen', bevel=0.7, rot=rot, name=name + '-in')
    return o


def leads(start, end, sep=6.0, radius=2.0, sag=8.0, name='lead'):
    """A red and a black silicone lead from start to end (mm), side by side in Y."""
    out = []
    for dy, m in ((-sep / 2, 'red_wire'), (sep / 2, 'black_wire')):
        a = Vector(start) + Vector((0, dy, 0))
        b = Vector(end) + Vector((0, dy, 0))
        mid1 = a.lerp(b, 0.33) + Vector((0, 0, -sag * 0.4))
        mid2 = a.lerp(b, 0.66) + Vector((0, 0, -sag * 0.4))
        out.append(tube_path([tuple(a), tuple(mid1), tuple(mid2), tuple(b)], radius, m=m, name=name))
    return out


def hand_scale(loc=(0, -60, 0)):
    """A neutral scale reference: an XT60 on the floor, 15.5 mm wide."""
    return xt60(loc, (0, 0, 0), True, 'scale-xt60')


# ----------------------------------------------------------------- staging
def bounds(objs=None):
    pts = []
    for o in (objs or bpy.context.scene.objects):
        if o.type in ('MESH', 'CURVE', 'FONT'):
            try:
                for c in o.bound_box:
                    pts.append(o.matrix_world @ Vector(c))
            except Exception:
                pass
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def stage(radius_hint=None, elevation=28.0, azimuth=-35.0, lens=70.0):
    """Floor, lights and camera framed on everything in the scene.  Returns
    (camera, pivot): rotate the pivot about Z for a turntable."""
    bpy.context.view_layer.update()
    lo, hi = bounds()
    centre = (lo + hi) / 2
    size = (hi - lo).length
    r = radius_hint or size
    # floor: a big disc in the backdrop colour, slightly darker so shadows read
    floor = cyl(r * 12, 0.5, (centre.x, centre.y, lo.z - 0.25), m=mat('floor', '#E4DFD2', 0.8),
                bevel=0, name='floor')
    # pivot carries the camera for turntables
    pivot = bpy.data.objects.new('pivot', None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = (centre.x, centre.y, centre.z)
    cam_data = bpy.data.cameras.new('cam')
    cam_data.lens = lens
    cam_data.clip_start = 1
    cam_data.clip_end = r * 100
    cam = bpy.data.objects.new('cam', cam_data)
    bpy.context.collection.objects.link(cam)
    cam.parent = pivot
    # distance so the object fills ~70 % of the frame
    fov = 2 * math.atan(36 / (2 * lens))
    dist = (size * 0.55) / math.tan(fov / 2)
    el, az = math.radians(elevation), math.radians(azimuth)
    cam.location = (dist * math.cos(el) * math.sin(az), -dist * math.cos(el) * math.cos(az), dist * math.sin(el))
    con = cam.constraints.new('TRACK_TO')
    con.target = pivot
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    bpy.context.scene.camera = cam
    # lights: key softbox, fill, rim
    def area(name, loc, energy, size_, colour='#FFF4E6'):
        L = bpy.data.lights.new(name, 'AREA')
        L.energy = energy
        L.size = size_
        L.color = srgb(colour)[:3]
        o = bpy.data.objects.new(name, L)
        bpy.context.collection.objects.link(o)
        o.location = loc
        c = o.constraints.new('TRACK_TO')
        c.target = pivot
        c.track_axis = 'TRACK_NEGATIVE_Z'
        c.up_axis = 'UP_Y'
        return o
    k = size * 2.2
    scale_e = (size / 100.0) ** 2
    area('key', (centre.x - k * 0.7, centre.y - k * 0.9, centre.z + k * 1.1), 9e5 * scale_e, size * 1.4)
    area('fill', (centre.x + k * 1.1, centre.y - k * 0.4, centre.z + k * 0.5), 3e5 * scale_e, size * 1.8, '#F3F0FF')
    area('rim', (centre.x + k * 0.2, centre.y + k * 1.2, centre.z + k * 0.9), 6e5 * scale_e, size * 1.0)
    return cam, pivot


def turntable(pivot, frames=96, start_deg=0.0):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    pivot.rotation_euler = (0, 0, math.radians(start_deg))
    pivot.keyframe_insert('rotation_euler', frame=1)
    pivot.rotation_euler = (0, 0, math.radians(start_deg + 360))
    pivot.keyframe_insert('rotation_euler', frame=frames + 1)
    for fc in pivot.animation_data.action.fcurves if hasattr(pivot.animation_data.action, 'fcurves') else []:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    try:
        for layer in pivot.animation_data.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'LINEAR'
    except Exception:
        pass
