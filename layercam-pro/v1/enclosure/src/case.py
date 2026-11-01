# -*- coding: utf-8 -*-
"""LayerCam Pro v1: the printed case, built from Prusa's Buddy3D case files.

The OUTSIDE is Prusa's printed case for the Buddy3D camera on the CORE One
(Printables model 1343977, GPL v2: buddy-camera-bottom-r2, -top-r1, -lid-r1);
the INSIDE is new, for one circuit board (../src/geometry.py).  Changes to
the outside: the USB-C opening moves (level plug, on the board's edge tab),
a hole for an RP-SMA bulkhead, round magnet pockets instead of Prusa's
slide-in block magnets, the SD-card slot closed, and screw holes for the
board's four screws (the two side screws are new holes; see README.md).

Prusa's files are downloaded, not committed.  Put the three STL files (and,
for the face measurements, the three STEP files) in one folder and run:

    python3 enclosure/src/case.py <folder with Prusa's files>

It writes enclosure/print/*.stl (the printable parts, in print orientation),
enclosure/images/*.png and runs enclosure/src/check.py (exits 1 if a check
fails).  Scratch goes to enclosure/out/ (git-ignored).

Needs numpy, scipy, shapely, trimesh, manifold3d, matplotlib, Pillow, and
cadquery-ocp for the STEP measurements (all in a venv in out/ is fine).

How it is built (all in the lens frame of geometry.py: origin on the lens
axis at the outer front face, +Z into the case):

  1. Prusa's three meshes are assembled with plan_section.py's transforms.
     The outer surface of the new case IS Prusa's surface (their triangles).
  2. Openings that move or close are plugged with the case's convex hull
     (the old USB-C recess, the SD slot, the old screw counterbores).
  3. The envelope E (Prusa's outside, filled) is taken as horizontal
     sections every 0.1 mm.  The new cavity N is E eroded by a 2.0 mm ball,
     built as 0.2 mm slabs (one print layer each), so every wall is 2.0 mm
     normal to the outside.  A filler (E eroded by 0.5 mm) closes Prusa's
     old pockets behind the skin.
  4. case = (Prusa + plugs + filler) - N, split at Z 21.0 (the board's
     front face, Prusa's own outer seam) into the front shell and the back
     shell, and at Prusa's lid outline into the lid; then the new inside is
     added and the openings are cut.

The STEP files' tessellation is not watertight (their faces are not sewn),
so the solids use Prusa's STL triangles; the STEP files give the exact
planes and cylinders (read_step_faces) used to check the measurements.
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3
import trimesh
from shapely import affinity
from shapely.geometry import Polygon, MultiPolygon, Point, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ENC, '..', 'src'))
import geometry as G  # noqa: E402

# ------------------------------------------------------------------ numbers
WALL = 2.0                 # wall, normal to the outside
FILL_IN = 0.5              # the filler stays this far inside Prusa's skin
SLAB = 0.2                 # cavity slab = one 0.2 mm print layer
ZSTEP = 0.1                # envelope sections
CLEAR = 0.5                # round the board
SPLIT_Z = G.BOARD_Z        # front shell below, back shell above (Prusa's outer seam)
BOARD_BACK = G.BOARD_Z + G.BOARD_T

# light rods (2.0 mm clear rod, cut to length), and the LEDs under them
LED_H = 2.3                # OSRAM SFH 4715CS height over the board (OSLON Black; confirm on its drawing)
LED_SIZE = 3.75
ROD_GAP = 0.3              # rod end to LED top
ROD_CH_D = 2.15            # channel
ROD_TUBE_D = 4.0           # printed guide tube round the channel
ROD_TUBE_TOP = G.BOARD_Z - LED_H - 0.7    # tube ends 0.7 mm short of the LED
FACE_HOLE_DEPTH = 0.3      # Prusa's Ø2.4 hole through the outer 0.3 mm
# light sensor (TEMT6000X01, 4 x 2 x 1.05 mm on the front face, under the window)
WINDOW_DEPTH = 2.0         # Prusa's Ø5.8 window recess
SENSOR_H = 1.05
LIGHT_TUBE_ID, LIGHT_TUBE_OD = 4.0, 6.4
LIGHT_TUBE_TOP = G.BOARD_Z - SENSOR_H - 0.65
# lens and IR-cut holder keep-out
HOLDER_Z0 = 11.5
# board screws: M2 x 10 pan or socket head, self-tapping into the front shell
PILOT_D = 1.7
PILOT_DEPTH = 7.0
BOSS_TOP_D = G.BOSS_D      # touches the board only inside this
BOSS_LOW_D = 6.0           # below BOSS_STEP_Z
BOSS_STEP_Z = G.BOARD_Z - 3.5
BACK_PAD_T = 1.0           # back shell's contact pad on the board's back face
BACK_BOSS_D = 7.0
HEAD_SEAT_Z = 25.0         # screw head seat (Prusa's), counterbore above it
HEAD_BORE_D = 4.2          # Prusa's counterbore (M2 socket head 3.8)
# lid screws (Prusa's: M2 self-tapping into the back shell)
LID_SCREWS = [(-15.5, -13.5), (15.5, -13.5)]
LID_PILOT_Z0 = 31.7
LID_BOSS_D = 5.2
# lid: 1.6 mm over the heatsink and vent slots
LID_TOP_Z = 41.85
LID_SEAT_Z = 38.45         # Prusa's back shell face under the lid
LID_THIN = 1.6
LID_POCKET = (-11.5, -26.3, 11.5, 7.6)    # X0, Y0, X1, Y1 of the 1.6 mm area
VENT_YS = [-14.5, -10.5, -6.5, -2.5, 1.5, 5.5]
VENT_X = 9.0               # slot centres run X -9..9, Ø2 ends (Prusa)
# heatsink: 20 x 20 x 15 on 3M 8810 tape on the 0.85 mm chip
SINK_Z0 = BOARD_BACK + 0.85 + 0.25
SINK_GAP = 0.5
# USB-C: GCT USB4105-GF-A, top mount on the back face, mouth at the tab edge
USB_W, USB_H, USB_L = 8.94, 3.26, 7.35
USB_MOUTH_PROUD = 0.0      # receptacle mouth past the tab edge (GCT: the mouth is at the PCB edge)
USB_AXIS_Z = BOARD_BACK + USB_H / 2
USB_OPEN = (9.4, 3.8)      # obround opening
USB_PLUG = (13.0, 7.2)     # seat for the plug's overmould (USB-C max 12.35 x 6.5)
USB_SEAT_IN = 0.2          # the mouth sits this far inside the seat
USB_BLOCK_T = 1.6          # wall behind the seat
# RP-SMA female bulkhead (1/4-36 UNS), D-hole, nut inside
SMA_HOLE_D, SMA_FLAT = 6.5, 5.9            # Ø6.5 with a flat 5.9 across
SMA_NUT_KEEP = (10.4, 5.0)                 # nut + washer room inside (Ø, length past the wall)
SMA_BODY_KEEP = (7.5, 9.0)                 # jack body and crimp behind the nut
# magnets: 10 x 3 mm discs, SH grade, epoxied flush in pockets
MAG_D, MAG_T = 10.0, 3.0
MAG_POCKET_D, MAG_POCKET_T = 10.3, 3.1
MAG_FLOOR = 1.2
MAG_BACK_D = 13.0

# Prusa's assembly (plan_section.py)
FLIP = np.array([[1, 0, 0, -4.21], [0, -1, 0, 3.39], [0, 0, -1, 45.68], [0, 0, 0, 1.0]])
SHIFT = np.array([[1, 0, 0, -1.28], [0, 1, 0, -0.74], [0, 0, 1, -2.0], [0, 0, 0, 1.0]])
PARTS = {'bottom': 'buddy-camera-bottom-r2', 'top': 'buddy-camera-top-r1', 'lid': 'buddy-camera-lid-r1'}

# Prusa's faces used here: nominal outward normals (lens frame, measured from
# the STEP files); the exact planes are fitted to the hull at run time.
FACE_N = {
    'magnet_a': (0.5, 0.048, 0.865),        # Prusa's magnet slot under the +X back chamfer
    'magnet_b': (0.0, -0.783, 0.622),       # ... and under the -Y back chamfer
    'sma': (0.707, -0.554, 0.44),           # +X -Y back chamfer: faces the front-left post (README)
    'usb_old': (-0.75, 0.433, -0.5),        # the -X +Y facet with Prusa's USB-C recess
    'front_y': (0.0, 0.866, -0.5),          # the front shell's +Y facet with Prusa's slots
}
# print orientation of each part (applied to the lens-frame part)
PRINT_POSE = {
    'front-shell': np.eye(4),
    'back-shell': np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, LID_SEAT_Z], [0, 0, 0, 1.0]]),
    'lid': np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, LID_TOP_Z], [0, 0, 0, 1.0]]),
}


# ------------------------------------------------------------------ helpers
def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def frame(z):
    """Two unit vectors completing z to a right-handed frame."""
    z = unit(z)
    a = np.array([0, 0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0, 0])
    x = unit(np.cross(a, z))
    return x, np.cross(z, x), z


def place(m, origin, ex, ey, ez):
    """Move a manifold built in a local frame to origin with axes ex, ey, ez."""
    M = np.column_stack([ex, ey, ez, origin]).astype(float)
    return m.transform(M)


def to_manifold(mesh):
    return m3.Manifold(m3.Mesh(vert_properties=np.asarray(mesh.vertices, np.float32),
                               tri_verts=np.asarray(mesh.faces, np.uint32)))


def to_trimesh(m):
    me = m.to_mesh()
    return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=False)


def section(poly_or_multi):
    """shapely (Multi)Polygon -> manifold CrossSection."""
    rings = []
    geoms = poly_or_multi.geoms if hasattr(poly_or_multi, 'geoms') else [poly_or_multi]
    for p in geoms:
        if p.is_empty:
            continue
        p = Polygon(p.exterior.coords, [h.coords for h in p.interiors])
        rings.append(np.array(p.exterior.coords[:-1]))
        rings += [np.array(h.coords[:-1]) for h in p.interiors]
    return m3.CrossSection(rings, m3.FillRule.EvenOdd)


def prism(poly, z0, z1):
    if poly.is_empty:
        return m3.Manifold()
    return m3.Manifold.extrude(section(poly), z1 - z0).translate((0, 0, z0))


def cyl(p0, p1, d, seg=48):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    h = np.linalg.norm(p1 - p0)
    ex, ey, ez = frame(p1 - p0)
    return place(m3.Manifold.cylinder(h, d / 2, d / 2, seg), p0, ex, ey, ez)


def zcyl(x, y, z0, z1, d, seg=48):
    return m3.Manifold.cylinder(z1 - z0, d / 2, d / 2, seg).translate((x, y, z0))


def local_prism(poly, t0, t1, origin, ex, ey, ez):
    """A shapely shape in the (ex, ey) plane at origin, extruded t0..t1 along ez."""
    return place(prism(poly, t0, t1), origin, ex, ey, ez)


def obround(w, h):
    r = min(w, h) / 2
    if w >= h:
        return box(-(w / 2 - r), -1e-6, w / 2 - r, 1e-6).buffer(r, quad_segs=12)
    return box(-1e-6, -(h / 2 - r), 1e-6, h / 2 - r).buffer(r, quad_segs=12)


def rounded_rect(w, h, r):
    return box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, quad_segs=12)


def union(ms):
    ms = [m for m in ms if not m.is_empty()]
    return m3.Manifold.batch_boolean(ms, m3.OpType.Add) if ms else m3.Manifold()


# ------------------------------------------------------------------ Prusa's case
def load_prusa(folder):
    """Prusa's three parts in the lens frame (trimesh), as plan_section.py."""
    out = {}
    for k, name in PARTS.items():
        m = trimesh.load(os.path.join(folder, name + '.stl'))
        if k != 'bottom':
            m.apply_transform(FLIP)
        m.apply_transform(SHIFT)
        out[k] = m
    return out


def read_step_faces(folder):
    """Planes and cylinders of Prusa's STEP files in the lens frame (for checks).
    Returns {part: {'planes': [(area, n, centre)], 'cyls': [(d, axis, point)]}},
    or {} if OCP or the STEP files are missing."""
    try:
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
        from OCP.TopoDS import TopoDS
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
    except ImportError:
        return {}
    out = {}
    for k, name in PARTS.items():
        path = os.path.join(folder, name + '.step')
        if not os.path.exists(path):
            return {}
        r = STEPControl_Reader()
        r.ReadFile(path)
        r.TransferRoots()
        s = r.OneShape()
        T = SHIFT @ (FLIP if k != 'bottom' else np.eye(4))
        R = T[:3, :3]
        planes, cyls = [], []
        e = TopExp_Explorer(s, TopAbs_FACE)
        while e.More():
            f = TopoDS.Face_s(e.Current()) if hasattr(TopoDS, 'Face_s') else TopoDS.Face(e.Current())
            a = BRepAdaptor_Surface(f)
            if a.GetType() == GeomAbs_Plane:
                d = a.Plane().Axis().Direction()
                n = np.array([d.X(), d.Y(), d.Z()]) * (-1 if f.Orientation() == TopAbs_REVERSED else 1)
                g = GProp_GProps()
                BRepGProp.SurfaceProperties_s(f, g)
                c = g.CentreOfMass()
                planes.append((g.Mass(), R @ n, (T @ [c.X(), c.Y(), c.Z(), 1])[:3]))
            elif a.GetType() == GeomAbs_Cylinder:
                cy = a.Cylinder()
                d, p = cy.Axis().Direction(), cy.Axis().Location()
                cyls.append((2 * cy.Radius(), R @ [d.X(), d.Y(), d.Z()], (T @ [p.X(), p.Y(), p.Z(), 1])[:3]))
            e.Next()
        out[k] = {'planes': planes, 'cyls': cyls}
    return out


def hull_plane(hull, n_nominal):
    """The hull facet nearest a nominal outward normal: (unit n, offset d), n.p = d."""
    n0 = unit(n_nominal)
    fn = hull.face_normals
    k = np.argmax(fn @ n0)
    n = fn[k]
    sel = (fn @ n) > 0.9999
    d = float(np.mean(hull.triangles_center[sel] @ n))
    return unit(n), d


# ------------------------------------------------------------------ envelope and cavity
class Envelope:
    """Horizontal sections of Prusa's case, filled (outer outlines only)."""

    def __init__(self, solid):
        self.z = np.arange(-0.047, LID_TOP_Z + ZSTEP, ZSTEP)   # off Prusa's flat faces
        self.P = []
        for z in self.z:
            rings = solid.slice(float(z)).to_polygons()
            outs = []
            for r in rings:
                r = np.asarray(r)
                if len(r) >= 3:
                    p = Polygon(r)
                    if p.is_valid and p.exterior.is_ccw and p.area > 1e-3:
                        outs.append(p)
                    elif not p.is_valid:
                        p = p.buffer(0)
                        if p.area > 1e-3 and Polygon(r).exterior.is_ccw:
                            outs.append(p)
            self.P.append(self._close_slits(unary_union(outs).buffer(0)) if outs else Polygon())
        self._cache = {}

    @staticmethod
    def _close_slits(q, g=1.0, min_area=20.0):
        """A narrow opening through the wall leaves the section a C shape whose
        outline runs round the inside too.  Add back the inside: the large
        pieces that a closing by g (bridging gaps under 2g) encloses.  Small
        notches in the outside (texture, seams) stay as they are."""
        c = q.buffer(g, quad_segs=4).buffer(-g, quad_segs=4)
        geoms = c.geoms if hasattr(c, 'geoms') else [c]
        cf = unary_union([Polygon(p.exterior) for p in geoms])
        extra = cf.difference(q)
        geoms = extra.geoms if hasattr(extra, 'geoms') else [extra]
        big = [p for p in geoms if p.area > min_area]
        return unary_union([q] + big).buffer(0) if big else q

    def eroded(self, i, r):
        key = (i, round(r, 3))
        if key not in self._cache:
            p = self.P[i]
            self._cache[key] = p.buffer(-r, quad_segs=6) if r > 1e-6 else p
        return self._cache[key]

    def erode_slab(self, z0, z1, w):
        """Points of the slab z0..z1 at least w from the outside (ball erosion)."""
        res = None
        for i, z in enumerate(self.z):
            d = max(z0 - z, z - z1, 0.0)
            if d > w:
                continue
            p = self.eroded(i, math.sqrt(max(w * w - d * d, 0.0)))
            res = p if res is None else res.intersection(p)
            if res.is_empty:
                return res
        if res is None or z0 - w < 0 or z1 + w > LID_TOP_Z:
            return Polygon()     # the ball reaches past the case's front or back
        return res

    def stack(self, w, z0=0.0, z1=LID_TOP_Z, simplify=0.02):
        """E eroded by w, as SLAB-thick prisms."""
        slabs = []
        zs = np.arange(z0, z1, SLAB)
        for za in zs:
            zb = min(za + SLAB, z1)
            p = self.erode_slab(za, zb, w)
            if p.is_empty:
                continue
            p = p.simplify(simplify, preserve_topology=True).buffer(0)
            slabs.append(prism(p, za - 1e-3, zb + 1e-3))
        return union(slabs)


# ------------------------------------------------------------------ board and parts on it
def board_polygon(pad=0.0):
    """The board in the lens frame: geometry.OUTLINE with the USB-C tab."""
    poly = Polygon(G.OUTLINE)
    ex, ey = G.USB_EDGE_XY
    a = math.radians(G.USB_NORMAL_DEG)
    t = box(-1.0, -G.USB_TAB_W / 2, G.USB_TAB, G.USB_TAB_W / 2)
    t = affinity.rotate(t, a, origin=(0, 0), use_radians=True)
    t = affinity.translate(t, ex, ey)
    p = poly.union(t)
    return p.buffer(pad, quad_segs=8) if pad else p


def usb_frame():
    """(origin on the board edge at the plug axis height, u outward, s along the edge, z)."""
    a = math.radians(G.USB_NORMAL_DEG)
    u = np.array([math.cos(a), math.sin(a), 0.0])
    z = np.array([0, 0, 1.0])
    s = np.cross(z, u)
    o = np.array([G.USB_EDGE_XY[0], G.USB_EDGE_XY[1], USB_AXIS_Z])
    return o, u, s, z


def sink_box(gap=0.0):
    x, y = G.SOC_XY
    w, h, t = G.HEATSINK
    return (x - w / 2 - gap, y - h / 2 - gap, SINK_Z0 - gap, x + w / 2 + gap, y + h / 2 + gap, SINK_Z0 + t + gap)


def rod_axis(a):
    """(front end at the hole, Z 0; LED end, the rod's top 0.3 mm short of the LED)."""
    hx, hy = G.hole_xy(a)
    lx, ly = G.led_xy(a)
    return np.array([hx, hy, 0.0]), np.array([lx, ly, G.BOARD_Z - LED_H - ROD_GAP])


# ------------------------------------------------------------------ the build
def prusa_solid(folder):
    """Prusa's case in the lens frame with the openings that close or move
    plugged (to the convex hull): (solid, parts, hull mesh, planes)."""
    prusa = load_prusa(folder)
    U = {k: to_manifold(m) for k, m in prusa.items()}
    assert all(m.status() == m3.Error.NoError for m in U.values()), 'Prusa STL not manifold'
    hull_mesh = trimesh.util.concatenate(list(prusa.values())).convex_hull
    hull = to_manifold(hull_mesh)
    planes = {k: hull_plane(hull_mesh, n) for k, n in FACE_N.items()}
    n_u, _ = planes['usb_old']
    c_old = np.array([-33.1, 8.9, 26.6])          # Prusa's USB-C opening (measured)
    ex, ey, ez = frame(n_u)
    plugs = [
        local_prism(box(-8.0, -7.5, 8.0, 7.5), -5.0, 3.0, c_old, ex, ey, ez),     # old USB-C recess
        m3.Manifold.cube((20.5, 8.0, 3.9)).translate((-12.6, -37.0, 20.4)),       # SD-card slot
        m3.Manifold.cube((7.0, 11.0, 9.0)).translate((7.2, -37.0, 20.4)),         # antenna-lead slit
        union([zcyl(x, 26.1, 21.4, 36.0, 4.7) for x in (-13.0, 13.0)]),         # old screw counterbores
        front_y_slots(U['bottom'], planes['front_y']),                          # (cut again later)
    ]
    solid = union(list(U.values()) + [union(plugs) ^ hull])
    return solid, U, prusa, hull_mesh, planes


def build(folder, log=print):
    solid, U, prusa, hull_mesh, planes = prusa_solid(folder)
    info = {'planes': planes}
    log('envelope sections ...')
    env = Envelope(solid)
    log('cavity (2.0 mm ball erosion, %.1f mm slabs) ...' % SLAB)
    N = env.stack(WALL + 0.01)
    log('filler ...')
    Fill = env.stack(FILL_IN)
    case = (solid + Fill) - N
    info['env'] = env

    # ---- lid region (Prusa's lid and everything above its seat inside its outline)
    lid_fp = unary_union([Polygon(r) for r in U['lid'].slice(LID_SEAT_Z + 0.3).to_polygons()
                          if Polygon(r).exterior.is_ccw]).buffer(0)
    lid_region = U['lid'] + prism(lid_fp, LID_SEAT_Z, 60.0)
    above = m3.Manifold.cube((200, 200, 100)).translate((-100, -100, SPLIT_Z))
    front = case - above
    back = (case ^ above) - lid_region
    lid = case ^ lid_region

    Eps = Fill          # internal additions stay inside this (0.5 mm under Prusa's skin)
    sink = sink_box(SINK_GAP)
    sink_keep = m3.Manifold.cube((sink[3] - sink[0], sink[4] - sink[1], sink[5] - sink[2])).translate(sink[:3])
    bpoly = board_polygon()
    board_clear = prism(board_polygon(CLEAR), SPLIT_Z - 0.0, BOARD_BACK + CLEAR)

    # ================================================================ front shell
    add, cut = [], []
    for (x, y) in G.SCREWS:
        add.append(zcyl(x, y, 0.0, BOSS_STEP_Z, BOSS_LOW_D))
        add.append(zcyl(x, y, BOSS_STEP_Z - 0.01, SPLIT_Z, BOSS_TOP_D))
        cut.append(zcyl(x, y, SPLIT_Z - PILOT_DEPTH, SPLIT_Z + 1, PILOT_D, 24))
    # light rods: a guide tube with a Ø2.15 channel from each LED to its hole
    for a in G.LED_ANGLES:
        p0, p1 = rod_axis(a)
        d = unit(p1 - p0)
        q0 = p0 + d * (1.0 / d[2])                     # inside the front plate
        q1 = p0 + d * ((ROD_TUBE_TOP - p0[2]) / d[2])
        add.append(cyl(q0, q1, ROD_TUBE_D, 40))
        cut.append(cyl(p0 - d * 2.0, p0 + d * ((p1[2] + 1.5 - p0[2]) / d[2]), ROD_CH_D, 32))
        hx, hy = G.hole_xy(a)
        cut.append(zcyl(hx, hy, -1.0, FACE_HOLE_DEPTH, G.LED_HOLE_D, 32))
    # light sensor tube
    wx, wy = G.LIGHT_WINDOW
    add.append(zcyl(wx, wy, 1.0, LIGHT_TUBE_TOP, LIGHT_TUBE_OD))
    cut.append(zcyl(wx, wy, -1.0, WINDOW_DEPTH, G.LIGHT_WINDOW_D))
    cut.append(zcyl(wx, wy, 0.0, LIGHT_TUBE_TOP + 1.0, LIGHT_TUBE_ID))
    # lens bore and the IR-cut holder's volume
    cut.append(zcyl(0, 0, -1.0, HOLDER_Z0 + 0.01, G.BORE_D, 96))
    x0, y0, x1, y1 = G.HOLDER_BOX
    cut.append(m3.Manifold.cube((x1 - x0, y1 - y0, SPLIT_Z + 1 - HOLDER_Z0)).translate((x0, y0, HOLDER_Z0)))
    # Prusa's slots in the +Y facet stay open
    cut.append(front_y_slots(U['bottom'], planes['front_y']))
    # USB-C: the tab sits over the front shell's rim; keep 0.5 under it
    o, u, s, z = usb_frame()
    tab_room = local_prism(box(-0.5, -G.USB_TAB_W / 2 - CLEAR, G.USB_TAB + 0.25, G.USB_TAB_W / 2 + CLEAR),
                           SPLIT_Z - 0.5 - USB_AXIS_Z, SPLIT_Z + 0.01 - USB_AXIS_Z, o, u, s, z)
    cut.append(tab_room)
    usb_cuts, usb_add = usb_features(planes['usb_old'])
    front = (front + (union(add) ^ Eps)) - union(cut) - union(usb_cuts)
    front = front - (above)

    # ================================================================ back shell
    add, cut = [], []
    for (x, y) in G.SCREWS:
        add.append(zcyl(x, y, BOARD_BACK, BOARD_BACK + BACK_PAD_T, BOSS_TOP_D))
        add.append(zcyl(x, y, BOARD_BACK + BACK_PAD_T - 0.01, 50.0, BACK_BOSS_D))
        cut.append(zcyl(x, y, SPLIT_Z - 1, HEAD_SEAT_Z + 0.01, G.SCREW_D, 24))
        cut.append(zcyl(x, y, HEAD_SEAT_Z, 60.0, HEAD_BORE_D, 40))
    for (x, y) in LID_SCREWS:
        add.append(zcyl(x, y, LID_PILOT_Z0 - 1.5, LID_SEAT_Z, LID_BOSS_D))
        # webs to the side and -Y walls (the boss stands in the cavity)
        sx = 1.0 if x > 0 else -1.0
        add.append(m3.Manifold.cube((16.0, 2.4, LID_SEAT_Z - LID_PILOT_Z0 + 1.5)).translate(
            (x if sx > 0 else x - 16.0, y - 1.2, LID_PILOT_Z0 - 1.5)))
        add.append(m3.Manifold.cube((2.4, 16.0, LID_SEAT_Z - LID_PILOT_Z0 + 1.5)).translate(
            (x - 1.2, y - 16.0, LID_PILOT_Z0 - 1.5)))
        cut.append(zcyl(x, y, LID_PILOT_Z0, LID_SEAT_Z + 1, PILOT_D, 24))
    mag_cuts, mag_add, info['magnets'] = magnet_features(planes)
    add += mag_add
    sma_cuts, sma_add, sma_keep, info['sma'] = sma_features(planes['sma'], Eps, N)
    add += sma_add
    add += usb_add
    back_add = (union(add) ^ Eps) - sink_keep - sma_keep
    back = back + back_add
    back = back - union(cut) - union(mag_cuts) - union(sma_cuts) - union(usb_cuts)
    back = back - board_clear_except_bosses(board_clear)
    back = back - sink_keep - lid_region
    back = back ^ above

    # ================================================================ lid
    lid_cut = []
    px0, py0, px1, py1 = LID_POCKET
    lid_cut.append(m3.Manifold.cube((px1 - px0, py1 - py0, LID_TOP_Z - LID_THIN - 30.0)).translate((px0, py0, 30.0)))
    for y in VENT_YS:
        lid_cut.append(prism(affinity.translate(obround(2 * VENT_X + 2.0, 2.0), 0, y), 30.0, 50.0))
    for (x, y) in LID_SCREWS:
        lid_cut.append(zcyl(x, y, 30.0, 50.0, 2.3, 24))
        lid_cut.append(zcyl(x, y, 39.5, 50.0, HEAD_BORE_D, 40))
    lid = lid - union(lid_cut)

    info.update(dict(board=bpoly, sink=sink_box(), usb=usb_info(planes['usb_old']), N=N, solid=solid,
                     prusa=prusa))
    parts = {'front-shell': front, 'back-shell': back, 'lid': lid}
    for k, m in parts.items():
        assert m.status() == m3.Error.NoError, k
        parts[k] = largest_piece(m, k, log)
    return parts, info


def largest_piece(m, name, log):
    """Drop slivers left by the booleans (report them)."""
    pieces = m.decompose()
    if len(pieces) == 1:
        return m
    pieces.sort(key=lambda p: -p.volume())
    small = [round(p.volume(), 3) for p in pieces[1:]]
    if sum(small) > 0:
        log('  %s: dropped %d slivers, %.3f mm3' % (name, len(small), sum(small)))
        for p in pieces[1:]:
            if p.volume() > 1.0:
                b = p.bounding_box()
                log('    %.1f mm3 at %s' % (p.volume(), np.round(np.array(b).reshape(2, 3).mean(0), 1)))
    return pieces[0]


def board_clear_except_bosses(board_clear):
    """0.5 mm round the board (sides and back face), except the screw pads."""
    pads = union([zcyl(x, y, SPLIT_Z - 1, BOARD_BACK + BACK_PAD_T + 0.02, BOSS_TOP_D + 0.02) for x, y in G.SCREWS])
    return board_clear - pads


def front_y_slots(bottom, plane):
    """Prusa's slots through the front shell's +Y facet: cut through the new wall."""
    n, d = plane
    ex, ey, ez = frame(n)
    # bottom part in the facet's frame, sliced 0.6 mm under the facet
    M = np.vstack([np.column_stack([ex, ey, ez]).T, [0, 0, 0]])
    M = np.column_stack([M, [0, 0, -d, 1]])
    loc = bottom.transform(M[:3, :])
    holes = []
    for r in loc.slice(-0.6).to_polygons():
        p = Polygon(r)
        if p.is_valid and not p.exterior.is_ccw and 0.5 < p.area < 60 and abs(p.centroid.x) < 11:
            holes.append(Polygon(r))
    if not holes:
        return m3.Manifold()
    slots = unary_union(holes)
    return local_prism(slots, -5.0, 1.0, n * d, ex, ey, ez)


def usb_info(plane_old):
    """Where the plug's axis meets the outside, and the seat for the plug."""
    o, u, s, z = usb_frame()
    n, d = plane_old
    t_out = (d - n @ o) / (n @ u)                 # along the axis to the facet
    t_mouth = G.USB_TAB + USB_MOUTH_PROUD
    return dict(origin=o, u=u, s=s, t_outer=t_out, t_mouth=t_mouth, t_seat=t_mouth + USB_SEAT_IN,
                axis_z=USB_AXIS_Z)


def usb_features(plane_old):
    """Level USB-C: obround opening, a vertical seat for the plug's overmould
    (the facet slopes 30 deg), the receptacle's room, and a block behind the seat."""
    i = usb_info(plane_old)
    o, u, s, z = i['origin'], i['u'], i['s'], np.array([0, 0, 1.0])
    ts = i['t_seat']
    # local frame: x = s (across), y = z (up), extrude along u
    cuts = [
        local_prism(obround(*USB_OPEN), -1.0, 30.0, o, s, z, u),
        local_prism(rounded_rect(USB_PLUG[0], USB_PLUG[1], 2.6), ts, 30.0, o, s, z, u),
        # the receptacle with 0.3 round it (its body may reach into the wall)
        local_prism(box(-USB_W / 2 - 0.3, -USB_H / 2 - 0.01, USB_W / 2 + 0.3, USB_H / 2 + 0.3),
                    i['t_mouth'] - USB_L - 1.0, ts + 0.01, o, s, z, u),
    ]
    blk = local_prism(box(-USB_PLUG[0] / 2 - 1.8, BOARD_BACK + 0.3 - USB_AXIS_Z, USB_PLUG[0] / 2 + 1.8,
                          USB_PLUG[1] / 2 + 1.8), ts - USB_BLOCK_T, 30.0, o, s, z, u)
    return cuts, [blk]


def magnet_features(planes):
    """Disc pockets on Prusa's two magnet faces (flush, epoxied), with backing."""
    out_c, out_a, info = [], [], {}
    # centres on the faces: A where Prusa's magnet sat, moved 4.5 mm towards +Y
    # off the side screw's counterbore; B in the middle of its face
    centres = {'magnet_a': np.array([29.97, 8.38, 34.5]), 'magnet_b': np.array([0.0, -31.96, 33.88])}
    for k, c in centres.items():
        n, d = planes[k]
        c = c + n * (d - n @ c)                     # onto the face
        out_c.append(cyl(c - n * MAG_POCKET_T, c + n * 2.0, MAG_POCKET_D, 64))
        out_a.append(cyl(c - n * (MAG_POCKET_T + MAG_FLOOR + 0.3), c + n * 0.5, MAG_BACK_D, 64))
        info[k] = (c, n)
    return out_c, out_a, info


def sma_features(plane, Eps, N):
    """The RP-SMA bulkhead: a Ø6.5 D-hole in the +X -Y back chamfer, a flat
    land for the nut inside, and room behind it for the jack."""
    n, d = plane
    c = sma_centre(plane)
    ex, ey, ez = frame(n)
    # the flat towards the lid (ey is the up-slope direction on the face)
    hole = Point(0, 0).buffer(SMA_HOLE_D / 2, quad_segs=24).intersection(
        box(-5, -5, 5, SMA_FLAT - SMA_HOLE_D / 2))
    cuts = [local_prism(hole, -8.0, 2.0, c, ex, ey, ez)]
    # inside: the wall is 2.0 here; nut and jack room
    keep = union([cyl(c - n * WALL, c - n * (WALL + SMA_NUT_KEEP[1]), SMA_NUT_KEEP[0], 48),
                  cyl(c - n * (WALL + SMA_NUT_KEEP[1] - 0.01), c - n * (WALL + SMA_NUT_KEEP[1] + SMA_BODY_KEEP[1]),
                      SMA_BODY_KEEP[0], 40)])
    land = cyl(c - n * (WALL + 0.02), c + n * 0.5, 13.0, 48)   # a flat Ø13 land, 2.0 thick
    return cuts, [land], keep, dict(centre=c, n=n, ex=ex, ey=ey)


SMA_CENTRE = (24.6, -17.2)     # X, Y on the face (chosen by sma_search)


def sma_keep_points(c, n, step=0.8):
    """Points filling the bulkhead's room inside the case (nut, then jack body)."""
    ex, ey, _ = frame(n)
    pts = []
    for (d, l0, l1) in ((SMA_NUT_KEEP[0], WALL, WALL + SMA_NUT_KEEP[1]),
                        (SMA_BODY_KEEP[0], WALL + SMA_NUT_KEEP[1], WALL + SMA_NUT_KEEP[1] + SMA_BODY_KEEP[1])):
        for t in np.arange(l0 + 0.2, l1 + 1e-6, step):
            for r in np.arange(0, d / 2 + 1e-6, step):
                for a in np.linspace(0, 2 * math.pi, max(1, int(2 * math.pi * r / step)), endpoint=False):
                    pts.append(c - n * t + (ex * math.cos(a) + ey * math.sin(a)) * r)
    return np.array(pts)


def sma_search(folder, step=0.5):
    """Where on the +X -Y back chamfer the bulkhead fits: a flat Ø13 land on
    Prusa's surface, and room inside clear of the board's parts (Z > 26.3),
    the heatsink, the lid, the screw bosses, inside the cavity.  Prints the
    best centres (by clearance); SMA_CENTRE is the one chosen."""
    solid, U, prusa, hull_mesh, planes = prusa_solid(folder)
    n, d = planes['sma']
    ex, ey, _ = frame(n)
    top = prusa['top']
    env = Envelope(solid)
    cav = to_trimesh(env.stack(WALL + 0.01, 21.0, LID_TOP_Z))
    sx0, sy0, sz0, sx1, sy1, sz1 = sink_box(SINK_GAP)
    c0 = np.array([23.37, -18.47, 30.8])
    c0 = c0 + n * (d - n @ c0)
    res = []
    for a in np.arange(-10, 10.01, step):
        for b in np.arange(-10, 10.01, step):
            c = c0 + ex * a + ey * b
            # flat land: rays from 0.5 outside, along -n, hit the top part 0.5 away
            ring = [c + n * 0.5 + (ex * math.cos(t) + ey * math.sin(t)) * r
                    for r in (0, 3.5, 6.5) for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
            loc, idx, _ = top.ray.intersects_location(ring, [-n] * len(ring), multiple_hits=False)
            if len(idx) < len(ring):
                continue
            dev = np.abs((loc - np.array(ring)[idx]) @ (-n) - 0.5).max()
            if dev > 0.12:
                continue
            P = sma_keep_points(c, n, 1.0)
            clear = min(P[:, 2].min() - 26.3, 38.2 - P[:, 2].max())
            inside_sink = ((P[:, 0] > sx0) & (P[:, 0] < sx1) & (P[:, 1] > sy0) & (P[:, 1] < sy1) &
                           (P[:, 2] > sz0) & (P[:, 2] < sz1)).any()
            for (x, y) in LID_SCREWS:
                m = P[:, 2] > LID_PILOT_Z0 - 1.5
                if m.any():
                    clear = min(clear, np.hypot(P[m, 0] - x, P[m, 1] - y).min() - LID_BOSS_D / 2)
            for (x, y) in G.SCREWS:
                clear = min(clear, np.hypot(P[:, 0] - x, P[:, 1] - y).min() - BACK_BOSS_D / 2)
            if inside_sink or clear < 0:
                continue
            if not cav.contains(P).all():
                continue
            res.append((clear, c))
    res.sort(key=lambda r: -r[0])
    for clear, c in res[:8]:
        print('centre (%.2f, %.2f, %.2f): clearance %.2f mm' % (c[0], c[1], c[2], clear))
    return res


def sma_centre(plane):
    n, d = plane
    x, y = SMA_CENTRE
    zc = (d - n[0] * x - n[1] * y) / n[2]
    return np.array([x, y, zc])


# ------------------------------------------------------------------ output
def export(parts, outdir):
    os.makedirs(outdir, exist_ok=True)
    paths = {}
    for k, m in parts.items():
        t = to_trimesh(m)
        t.apply_transform(PRINT_POSE[k])
        t.apply_translation((0, 0, -t.bounds[0][2]))
        p = os.path.join(outdir, 'layercam-pro-%s.stl' % k)
        t.export(p)
        paths[k] = p
    return paths


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('prusa_folder')
    ap.add_argument('--no-images', action='store_true')
    a = ap.parse_args()
    parts, info = build(a.prusa_folder)
    paths = export(parts, os.path.join(ENC, 'print'))
    for k, p in paths.items():
        print('wrote', os.path.relpath(p, ENC), '%.1f cm3' % (parts[k].volume() / 1000))
    import check
    ok = check.run(parts, info, a.prusa_folder)
    if not a.no_images:
        import render
        render.draw(parts, info, os.path.join(ENC, 'images'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
