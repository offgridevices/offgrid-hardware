"""Blender side of make_video.py: the exploded-view scene of one board.

    python scene.py -- BOARD.glb SPEC.json OUT.blend ANCHORS.json

BOARD.glb is KiCad's GLB export (tracks, pads, zones, inner copper,
silkscreen, soldermask).  SPEC.json is make_video.py's merged spec: the
board's facts (copper layer names), the timeline, the camera shots, the
lights and the render quality.

The board is taken apart into its physical layers: the parts on each side,
the silkscreen and solder mask of each side, and every copper layer as a
card on the FR-4 below it.  The board stands up on its edge, opens sideways
into those layers, holds, closes and lies down again, while the camera
moves between shots fitted to what is in view.  The via barrels stretch
between the outer coppers as the board opens.  ANCHORS.json gets, per frame,
each layer's two edge points on screen, for the labels (overlay.py).
"""
import bpy, bmesh, sys, json, math
import numpy as np
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

GLB, SPEC_PATH, BLEND, ANCHORS = sys.argv[sys.argv.index('--') + 1:][:4]
SPEC = json.load(open(SPEC_PATH))
S = 100.0                               # glTF metres -> scene units of 1 cm

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=GLB)

# ------------------------------------------------------------- flatten
# every mesh in world space, single user, board centred on the origin
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
owner, data_name = {}, {}
for o in meshes:
    p = o.parent
    owner[o.name] = p.name if (p is not None and p.parent is not None) else None
    data_name[o.name] = o.data.name
pcb = next(o for o in meshes if o.data.name.endswith('_PCB'))
bb = [pcb.matrix_world @ Vector(c) for c in pcb.bound_box]
x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
to_scene = Matrix.Scale(S, 4) @ Matrix.Translation((-(x0 + x1) / 2, -(y0 + y1) / 2, 0))
HX, HY = (x1 - x0) * S / 2, (y1 - y0) * S / 2      # board half size, cm
for o in meshes:
    mw = o.matrix_world.copy()
    if o.data.users > 1:
        o.data = o.data.copy()
    o.data.transform(to_scene @ mw)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
for o in [x for x in bpy.data.objects if x.type != 'MESH']:
    bpy.data.objects.remove(o)


def coords(o):
    a = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def zs_of(o):
    return coords(o)[:, 2]


def centres_z(o):
    a = np.empty(len(o.data.polygons) * 3)
    o.data.polygons.foreach_get('center', a)
    return a[2::3]


def subset(o, keep, name):
    """A new object of the faces of `o` where keep[face index]."""
    me = o.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep[f.index]], context='FACES')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


kind = {}
for o in meshes:
    d = data_name[o.name]
    if owner[o.name] is None and '_' in d:
        kind[o.name] = d.rsplit('_', 1)[1].split('.')[0]
board = {k: [o for o in meshes if kind.get(o.name) == k] for k in set(kind.values())}
comps = [o for o in meshes if o.name not in kind]
pcb = board['PCB'][0]
T = float(zs_of(pcb).max())                    # board top (dielectric), cm

# copper layers: the z bands of the copper mesh, bottom first
CU = list(reversed(SPEC['copper']))            # names, bottom first
cu = board['copper'][0]
bands = []
for v in np.unique(np.round(zs_of(cu), 5)):
    if bands and v - bands[-1][-1] < 0.005:
        bands[-1].append(v)
    else:
        bands.append([v])
bands = [(b[0], b[-1]) for b in bands]
assert len(bands) == len(CU), 'copper bands %s for layers %s' % (bands, CU)
mids = np.array([(a + b) / 2 for a, b in bands])


def split_layers(o, prefix):
    idx = np.abs(centres_z(o)[:, None] - mids[None, :]).argmin(axis=1)
    out = {}
    for k, name in enumerate(CU):
        if (idx == k).any():
            out[name] = subset(o, idx == k, '%s %s' % (prefix, name))
    bpy.data.objects.remove(o)
    return out


copper = split_layers(cu, 'copper')
pads = split_layers(board['pad'][0], 'pads') if board.get('pad') else {}

# FR-4 between the coppers: the board body squeezed into each gap; each
# slab rides with the copper above it
slab_under = {}
for k in range(len(CU) - 1):
    lo, hi = bands[k][1], bands[k + 1][0]
    me = pcb.data.copy()
    a = coords(pcb).copy()
    a[:, 2] = lo + a[:, 2] / T * (hi - lo)
    me.vertices.foreach_set('co', a.ravel())
    ob = bpy.data.objects.new('FR-4 under ' + CU[k + 1], me)
    scene.collection.objects.link(ob)
    slab_under[CU[k + 1]] = ob
bpy.data.objects.remove(pcb)

top = lambda o: float(zs_of(o).mean()) > T / 2
silk = {('top' if top(o) else 'bottom'): o for o in board.get('silkscreen', [])}
mask = {('top' if top(o) else 'bottom'): o for o in board.get('soldermask', [])}
via = board['via'][0] if board.get('via') else None
if via:
    via.name = 'vias'
comp_top = [o for o in comps if top(o)]
comp_bot = [o for o in comps if not top(o)]

# ------------------------------------------------------------ materials
def principled(name, color, metallic=0.0, rough=0.4, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


M_COPPER = principled('copper', (0.80, 0.36, 0.20), 1.0, 0.26)
M_INNER = principled('copper inner', (0.80, 0.34, 0.18), 1.0, 0.40)
M_GOLD = principled('ENIG gold', (0.95, 0.62, 0.22), 1.0, 0.3)
M_FR4 = principled('FR-4', (0.78, 0.74, 0.50), 0.0, 0.35, **{'Transmission Weight': 0.75, 'IOR': 1.5})
M_MASK = principled('solder mask', (0.014, 0.015, 0.017), 0.0, 0.42,
                    **{'Coat Weight': 1.0, 'Coat Roughness': 0.03})
M_SILK = principled('silkscreen', (0.80, 0.79, 0.75), 0.0, 0.55)
OUTER = (CU[0], CU[-1])


def assign(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


for name, o in copper.items():
    assign(o, M_COPPER if name in OUTER else M_INNER)
for name, o in pads.items():
    assign(o, M_GOLD if name in OUTER else M_INNER)
if via:
    assign(via, M_COPPER)
for o in slab_under.values():
    assign(o, M_FR4)
for o in mask.values():
    assign(o, M_MASK)
for o in silk.values():
    assign(o, M_SILK)

# component materials: glTF leaves metallic at 1; plastics and metals apart
seen = set()
for o in comps:
    for m in o.data.materials:
        if m is None or m.name in seen or not m.node_tree:
            continue
        seen.add(m.name)
        b = m.node_tree.nodes.get('Principled BSDF')
        if b is None:
            continue
        r, g, bl = b.inputs['Base Color'].default_value[:3]
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * bl
        sat = max(r, g, bl) - min(r, g, bl)
        if lum > 0.3 and sat < 0.15:
            mr = 1.0, 0.28                     # tin, silver: leads, shells
        elif r > 0.6 and g > 0.4 and bl < 0.4:
            mr = 1.0, 0.22                     # gold
        elif lum < 0.08:
            mr = 0.0, 0.38                     # black plastic
        else:
            mr = 0.0, 0.5
        b.inputs['Metallic'].default_value, b.inputs['Roughness'].default_value = mr

# chips: the library models print a logo and the package name on top;
# paint the top-surface markings in the body colour instead
for o in comps:
    if not owner[o.name] or owner[o.name][0] not in 'UQ' or len(o.data.materials) < 2:
        continue
    lum = []
    for m in o.data.materials:
        c = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value
        lum.append(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
    body = int(np.argmin(lum))
    zmax = float(zs_of(o).max()) if top(o) else float(zs_of(o).min())
    for p in o.data.polygons:
        if abs(p.center.z - zmax) < 0.0015 and abs(p.normal.z) > 0.9 and lum[p.material_index] > 0.2:
            p.material_index = body

# -------------------------------------------------------------- groups
# top to bottom; 'ref' is the z the group sits at when assembled
fz = lambda o: float(zs_of(o).mean())
G = []
if comp_top:
    G.append(('components top', comp_top, T))
for side, objs in (('silkscreen top', silk), ('mask top', mask)):
    if 'top' in objs:
        G.append((side, [objs['top']], fz(objs['top'])))
for k, name in enumerate(SPEC['copper']):
    G.append((name, [copper.get(name), pads.get(name), slab_under.get(name)], mids[len(CU) - 1 - k]))
for side, objs in (('mask bottom', mask), ('silkscreen bottom', silk)):
    if 'bottom' in objs:
        G.append((side, [objs['bottom']], fz(objs['bottom'])))
if comp_bot:
    G.append(('components bottom', comp_bot, 0.0))


def gap(a, b):
    """Space between neighbours when open, in board widths."""
    k = SPEC['gaps']
    if 'components' in a or 'components' in b:
        return k['components']
    if a in SPEC['copper'] and b in SPEC['copper']:
        return k['copper']
    return k['other']


W = 2 * max(HX, HY)
pos = [0.0]
for (a, _, _), (b, _, _) in zip(G, G[1:]):
    pos.append(pos[-1] + gap(a, b) * W)
c = (len(G) - 1) / 2                     # the stack opens about its middle
i0, i1 = math.floor(c), math.ceil(c)
zc = (G[i0][2] + G[i1][2]) / 2
pc = (pos[i0] + pos[i1]) / 2
MAXR = c
rig = bpy.data.objects.new('board', None)
scene.collection.objects.link(rig)
groups = []
for i, (name, objs, ref) in enumerate(G):
    objs = [o for o in objs if o is not None]
    z = np.concatenate([zs_of(o) for o in objs])
    empty = bpy.data.objects.new('grp ' + name, None)
    scene.collection.objects.link(empty)
    empty.parent = rig
    for o in objs:
        o.parent = empty
    groups.append(dict(name=name, empty=empty, ref=ref, lo=float(z.min()), hi=float(z.max()),
                       off=zc + (pc - pos[i]) - ref, rank=abs(i - c)))
mid = i0

# via barrels span the outer coppers; they stretch with the explosion
if via:
    via.parent = rig
    vlo, vhi = float(zs_of(via).min()), float(zs_of(via).max())
    via.data.transform(Matrix.Translation((0, 0, -vlo)))
    via.location.z = vlo

# ---------------------------------------------------------- animation
TL = SPEC['timeline']
N = TL['end']
frames = range(N + 1)
scene.frame_start, scene.frame_end = 0, N
scene.render.fps = SPEC['fps']


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def span(f, a, b):
    return ease((f - a) / (b - a))


def explode(g, f):
    d, st = TL['move'], TL['stagger']
    return (span(f, TL['open'] + (MAXR - g['rank']) * st, TL['open'] + (MAXR - g['rank']) * st + d)
            - span(f, TL['close'] + g['rank'] * st, TL['close'] + g['rank'] * st + d))


def stand(f):
    """0 lying flat, 1 standing on its edge with the top side facing -x."""
    return span(f, *TL['stand']) - span(f, *TL['lay'])


def keyed(ob, path, index, values):
    """One key per frame on ob.path[index], linear.  The first key goes in
    through keyframe_insert, which sets up the action and its slot."""
    ob.keyframe_insert(data_path=path, index=index, frame=0)
    fc = ob.animation_data.action.fcurves.find(path, index=index)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(values))
    fc.keyframe_points.foreach_set('co', [c for f, v in enumerate(values) for c in (f, v)])
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'


def keyed_socket(sock, values):
    for f, v in enumerate(values):
        sock.default_value = v
        sock.keyframe_insert('default_value', frame=f)


E = {g['name']: [explode(g, f) for f in frames] for g in groups}
EM = E[groups[mid]['name']]                    # how open the board is
for g in groups:
    keyed(g['empty'], 'location', 2, [e * g['off'] for e in E[g['name']]])
ANGLE = [-math.pi / 2 * stand(f) for f in frames]
keyed(rig, 'rotation_euler', 1, ANGLE)
if via:
    gF = next(g for g in groups if g['name'] == CU[-1])
    gB = next(g for g in groups if g['name'] == CU[0])
    h0 = vhi - vlo
    keyed(via, 'location', 2, [vlo + E[CU[0]][f] * gB['off'] for f in frames])
    keyed(via, 'scale', 2, [(h0 + E[CU[-1]][f] * gF['off'] - E[CU[0]][f] * gB['off']) / h0 for f in frames])
    for i in (0, 1):                           # and thin out as they stretch
        keyed(via, 'scale', i, [1 - SPEC['via_thin'] * (E[CU[-1]][f] + E[CU[0]][f]) / 2 for f in frames])
# FR-4 looks solid when closed and turns to tinted glass as the board
# opens, so the copper between the layers shows
fr4 = M_FR4.node_tree.nodes['Principled BSDF']
keyed_socket(fr4.inputs['Transmission Weight'], [0.15 + 0.85 * e for e in EM])
keyed_socket(fr4.inputs['Roughness'], [0.45 - 0.37 * e for e in EM])

# -------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new('camera')
cam_data.lens = SPEC['camera']['lens']
cam_data.clip_start, cam_data.clip_end = 0.5, 5000
cam = bpy.data.objects.new('camera', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
r = scene.render
r.resolution_x, r.resolution_y = SPEC['quality']['resolution']
r.resolution_percentage = 100


def direction(az, el):
    az, el = math.radians(az), math.radians(el)
    return Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))


def place(eye, look):
    cam.location = eye
    cam.rotation_euler = (look - eye).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()


def stack_points(mode):
    """World-space box corners of every group: 'flat' (closed, lying),
    'standing' (closed, on its edge) or 'open' (open, on its edge)."""
    rot = Matrix.Rotation(-math.pi / 2, 4, 'Y') if mode != 'flat' else Matrix.Identity(4)
    pts = []
    for g in groups:
        dz = g['off'] if mode == 'open' else 0.0
        for z in (g['lo'] + dz, g['hi'] + dz):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pts.append(rot @ Vector((sx * HX, sy * HY, z)))
    return pts


def fit(mode, az, el):
    """Camera distance and look-at point that frame the stack in `mode`
    inside SPEC['camera']['frame'][mode] (fractions of the frame)."""
    pts = stack_points(mode)
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    look = (lo + hi) / 2
    fx0, fx1, fy0, fy1 = SPEC['camera']['frame'][mode]
    d0, d1 = 1.0, 5000.0
    for _ in range(40):
        d = (d0 + d1) / 2
        place(look + direction(az, el) * d, look)
        ok = True
        for p in pts:
            v = world_to_camera_view(scene, cam, p)
            if not (v.z > 0 and fx0 <= v.x <= fx1 and fy0 <= 1 - v.y <= fy1):
                ok = False
                break
        d0, d1 = (d0, d) if ok else (d, d1)
    return d1, look


shots = []
for f, az, el, mode, scale in SPEC['camera']['shots']:
    d, look = fit(mode, az, el)
    shots.append((f, az, el, d * scale, look))


def shot_at(f):
    if f <= shots[0][0]:
        s = shots[0]
        return s[1], s[2], s[3], s[4]
    for a, b in zip(shots, shots[1:]):
        if f <= b[0]:
            t = ease((f - a[0]) / (b[0] - a[0]))
            return (a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t,
                    a[3] + (b[3] - a[3]) * t, a[4].lerp(b[4], t))
    s = shots[-1]
    return s[1], s[2], s[3], s[4]


def cam_at(f):
    az, el, d, look = shot_at(f)
    return look + direction(az, el) * d, look


locs, rots = [], []
for f in frames:
    eye, look = cam_at(f)
    locs.append(eye)
    rots.append((look - eye).to_track_quat('-Z', 'Y').to_euler())
for i in range(3):
    keyed(cam, 'location', i, [v[i] for v in locs])
    keyed(cam, 'rotation_euler', i, [v[i] for v in rots])
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = SPEC['camera']['fstop']
scene.unit_settings.scale_length = 0.01
focus = bpy.data.objects.new('focus', None)
scene.collection.objects.link(focus)
keyed(focus, 'location', 0, [cam_at(f)[1].x for f in frames])
keyed(focus, 'location', 2, [cam_at(f)[1].z for f in frames])
cam_data.dof.focus_object = focus

# -------------------------------------------------------------- lights
# positions and powers in the spec are for a 36 mm board: they scale with
# the board (distance with its size, power with the square of it)
K = W / 3.6
world = bpy.data.worlds.new('world')
scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld')
env = nt.nodes.new('ShaderNodeTexEnvironment')
import os
env.image = bpy.data.images.load(os.path.join(bpy.utils.system_resource('DATAFILES'), 'studiolights', 'world',
                                              SPEC['world']['hdri']))
mapping = nt.nodes.new('ShaderNodeMapping')
coord = nt.nodes.new('ShaderNodeTexCoord')
nt.links.new(coord.outputs['Generated'], mapping.inputs['Vector'])
mapping.inputs['Rotation'].default_value = (0, 0, math.radians(SPEC['world']['hdri_rotation']))
nt.links.new(mapping.outputs['Vector'], env.inputs['Vector'])
lit = nt.nodes.new('ShaderNodeBackground')
lit.inputs['Strength'].default_value = SPEC['world']['hdri_strength']
nt.links.new(env.outputs['Color'], lit.inputs['Color'])
# what the camera sees: a dark radial gradient
bg = nt.nodes.new('ShaderNodeBackground')
win = nt.nodes.new('ShaderNodeTexCoord')
sub = nt.nodes.new('ShaderNodeVectorMath')
sub.operation = 'SUBTRACT'
sub.inputs[1].default_value = (0.5, 0.5, 0)
nt.links.new(win.outputs['Window'], sub.inputs[0])
ln = nt.nodes.new('ShaderNodeVectorMath')
ln.operation = 'LENGTH'
nt.links.new(sub.outputs['Vector'], ln.inputs[0])
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.0, 0.75
ramp.color_ramp.elements[0].color = (*SPEC['world']['centre'], 1)
ramp.color_ramp.elements[1].color = (*SPEC['world']['edge'], 1)
nt.links.new(ln.outputs['Value'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
path = nt.nodes.new('ShaderNodeLightPath')
mix = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(path.outputs['Is Camera Ray'], mix.inputs['Fac'])
nt.links.new(lit.outputs['Background'], mix.inputs[1])
nt.links.new(bg.outputs['Background'], mix.inputs[2])
nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])


def area(name, loc, size, energy, color=(1, 1, 1), size_y=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.color = energy, color
    if size_y:
        ld.shape, ld.size, ld.size_y = 'RECTANGLE', size, size_y
    else:
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, zc)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


for L in SPEC['lights']:
    area(L['name'], [v * K for v in L['loc']], L['size'] * K, L['energy'] * K * K, tuple(L.get('color', (1, 1, 1))))

# a sheen on the copper while the board is open: a soft box where the
# copper faces mirror the camera, linked to the copper only (it would grey
# the black solder mask), lit only while the board is open
sh = SPEC['sheen']
hold = (TL['open_end'] + TL['close']) // 2
eye, look = cam_at(hold)
cdir = (eye - look).normalized()
n = Vector((-1, 0, 0))                         # the top side, standing
rdir = 2 * cdir.dot(n) * n - cdir
ob = area('sheen', look + rdir * sh['distance'] * K, sh['size'] * K, sh['energy'] * K * K)
rc = bpy.data.collections.new('sheen receivers')
for o in [*copper.values(), *pads.values(), *([via] if via else [])]:
    rc.objects.link(o)
ob.light_linking.receiver_collection = rc
for f in frames:
    ob.data.energy = sh['energy'] * K * K * EM[f]
    ob.data.keyframe_insert('energy', frame=f)

# a strip of light that sweeps across the board in the opening shot
sw = SPEC['sweep']
ob = area('sweep', [v * K for v in sw['from']], sw['size'] * K, sw['energy'] * K * K, size_y=sw['size_y'] * K)
ob.rotation_euler = (0, 0, 0)
for i in range(3):
    keyed(ob, 'location', i, [(sw['from'][i] + (sw['to'][i] - sw['from'][i]) * span(f, sw['f0'], sw['f1'])) * K
                              for f in frames])
for f, v in ((0, 0), (sw['f0'] + 6, 1), (sw['f1'] - 6, 1), (sw['f1'] + 12, 0)):
    ob.data.energy = v * sw['energy'] * K * K
    ob.data.keyframe_insert('energy', frame=f)

# -------------------------------------------------------------- render
Q = SPEC['quality']
r.engine = 'CYCLES'
r.use_persistent_data = True
r.film_transparent = False
cy = scene.cycles
cy.device = 'CPU'
cy.samples = Q['samples']
cy.use_adaptive_sampling = True
cy.adaptive_threshold = Q['noise_threshold']
cy.use_denoising = True
cy.denoiser = 'OPENIMAGEDENOISE'
cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 2, 3
cy.transmission_bounces, cy.transparent_max_bounces = 4, 4
cy.caustics_reflective = cy.caustics_refractive = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = SPEC['look']
r.image_settings.file_format = 'PNG'

# ------------------------------------------------------------ anchors
# per frame, each group's two edge midpoints (board x = +/-HX) on screen
anchors = {'size': [r.resolution_x, r.resolution_y], 'groups': [g['name'] for g in groups], 'frames': []}
for f in frames:
    eye, look = cam_at(f)
    place(eye, look)
    rot = Matrix.Rotation(ANGLE[f], 4, 'Y')
    row = []
    for g in groups:
        z = (g['lo'] + g['hi']) / 2 + E[g['name']][f] * g['off']
        pts = []
        for sx in (1, -1):
            v = world_to_camera_view(scene, cam, rot @ Vector((sx * HX, 0, z)))
            pts += [round(v.x * r.resolution_x, 1), round((1 - v.y) * r.resolution_y, 1)]
        row.append(pts + [round(E[g['name']][f], 4)])
    anchors['frames'].append(row)
json.dump(anchors, open(ANCHORS, 'w'))
scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print('BUILT', BLEND, 'layers', len(groups), 'frames', N + 1, 'parts', len(comp_top), '+', len(comp_bot))
