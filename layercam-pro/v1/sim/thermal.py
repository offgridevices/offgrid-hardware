# -*- coding: utf-8 -*-
"""LayerCam Pro v1: temperatures inside the case; rated for a 65 C chamber (70 C reported).

The rating (owner's decision, 1 Nov 2026): every part inside its rating in a
65 C chamber in snapshot mode, day and night, with the ESP32-C6's Wi-Fi
power save ON (the C6 firmware sets it).  Prusa's firmware caps the chamber
at 55 C on the CORE One and 60 C on the CORE One L.  The script exits 1 if
that requirement fails; 70 C and power save off are reported as
information only.

    python3 sim/thermal.py              writes sim/thermal.md and thermal_<case>.png, exits 1 on a FAIL
    (tools/kd python3 sim/thermal.py    the same; with KiCad's Python it measures the routed board's copper)

The model, from the inside out:

  the board    a 2D finite-difference plate on a 0.5 mm grid over the real
               outline (src/pcb.py's board_polygon(): geometry.OUTLINE with
               the USB-C tab).  In-plane conductance from the 6-layer
               1.6 mm build with a copper coverage factor per layer; each
               part's heat (sim/power_budget.py) on its footprint at its
               place (the routed board layercam-pro.kicad_pcb when it
               exists, else src/layout_main.py's FIXED places).  The back
               face (F) loses heat to the back cavity, the front face (B)
               to the front cavity, by radiation and by conduction across
               the still air (Catton's enclosure correlation, Nu >= 1); the
               board edge to the case wall across its 0.5 mm clearance; the
               four M2 screws into printed bosses.
  the sensor   the bare SC4336H on the front face at (0, 0): its die sits
               above the board under it by its own heat x an assumed
               theta-JB; inside the IR-cut holder's base the front face
               loses less heat (the holder traps air).
  heatsink     20 x 20 x 15 mm aluminium on 3M 8810 tape on the RV1106 at
               board (0, 15).  The junction splits its heat between the
               board (exposed pad and vias) and the heatsink (theta-JC top
               + tape).  The heatsink gives heat to the back cavity's air
               (its sides and fins), to the board under its overhang, to the
               lid across the 0.7 mm gap under it, and straight to the
               chamber through the three 20 x 2 mm lid slots over its fins:
               still-air conduction up each slot, radiation out through it,
               and the stack-driven exchange flow between the lower and the
               upper slot through the fin channels (natural convection).
  the case     PC carbon fibre, 2 mm walls, Prusa's outside (outer hull
               125.6 cm^2, measured); the lid patch over the heatsink is
               its own node (it takes heat from the heatsink and spreads it
               into the rest of the lid).  Natural convection and radiation
               to a 70 C chamber, no airflow credited; the other three lid
               slots give the back cavity a small stack-effect exchange.
  junctions    each part's own resistance from the board under it (datasheet
               theta-JB / psi-JB where given, else estimated and marked).

Case figures measured from Prusa's STLs (buddy-camera-bottom-r2, -top-r1,
-lid-r1, assembled with src/plan_section.py's transforms) on 1 Nov 2026:
convex hull 125.6 cm^2 / 111.0 cm^3 (as LayerCam v1); with 2 mm walls the
front cavity (the inner front face at Z 2.0 to the board's front face at
Z 21.0) holds 38.2 cm^3 behind 31.1 cm^2 of side wall and 11.9 cm^2 of front
wall, the back cavity (Z 22.6 to the lid's inner face) 48.1 cm^3 behind
34.2 cm^2 of side wall and 14.6 cm^2 of lid; the lid's six slots are
20 x 2 mm at lens Y -14.5, -10.5, -6.5, -2.5, 1.5, 5.5 (the first three
over the heatsink, plan_section.py).
"""
import math, os, re, sys, types
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(V1, 'src'))
try:
    import pcbnew  # noqa: F401  (KiCad's Python: only to measure the routed board)
    HAVE_PCBNEW = True
except ImportError:
    # src/pcb.py and src/layout_main.py import pcbnew at the top for their board-building half; the
    # geometry this model reads needs none of it, so a stand-in module lets them import
    _stub = types.ModuleType('pcbnew')
    _stub.FromMM = lambda x: int(round(x * 1e6))
    _stub.__getattr__ = lambda name: 0
    sys.modules['pcbnew'] = _stub
    HAVE_PCBNEW = False
import geometry as G
import parts
import pcb
import layout_main as LM
import power_budget as power

OUT = os.path.join(HERE, 'thermal.md')
ROUTED = os.path.join(V1, 'layercam-pro.kicad_pcb')
SIGMA = 5.670e-8

# ---------------------------------------------------------------- environment and case
T_AMB = 65.0                      # the rating: every part inside its rating in a 65 C chamber (owner, 1 Nov 2026)
T_INFO = 70.0                     # the earlier 70 C target, reported as information
PRUSA_CAP = (55.0, 60.0)          # Prusa's firmware chamber cap: CORE One, CORE One L
REQ = ('snap_day_ps', 'snap_night_ps')    # the requirement cases: snapshot mode, Wi-Fi power save ON
REQ_NIGHT = 'snap_night_ps'
A_OUT = 125.6e-4                  # m^2, the case's outer hull (Prusa's outside, STL)
A_IN = (11.9 + 31.1 + 34.2 + 14.6) * 1e-4   # m^2, the inner wall (front, side walls, lid) with 2 mm walls
WALL_T = 0.002
# PC carbon fibre, printed.  Stratasys FDM PC: 0.28 W/mK (ASTM E1952, its data sheet); unfilled PC 0.20
# (Covestro, ISO 8302).  Short carbon fibre raises it a little, mostly along the print layers: 0.30
# through the wall and 0.45 along it, ESTIMATED (no PC-CF filament data sheet found gives a value).
K_WALL, K_WALL_INPLANE = 0.30, 0.45
EPS_HOUSING = 0.90                # printed matte plastic in the infrared
BED_RAD_W = 0.10                  # bed at 100-110 C seen by the camera's front, ~0.14 view factor (estimate)
# the camera's mounting: its lens looks down at the bed about 45 degrees below horizontal (ASSUMED from the
# CORE One's top-front corner mount), so the lid faces up and back and +Y on the lid points partly up
TILT = 45.0
SLOT_YC = (-14.52, -10.52, -6.52, -2.52, 1.48, 5.48)    # lens frame Y (measured)
SLOT_L, SLOT_W = 20.0e-3, 2.0e-3
LID_T = 1.6e-3                    # the new lid over the heatsink (plan_section.py)
LID_GAP = 0.7e-3                  # heatsink top (Z 38.7) to the lid's inner face (Z 39.4 or higher)
LID_TOP_AREA = 14.6e-4            # the lid's inner face (STL)
VENT_CD = 0.6

# ---------------------------------------------------------------- inside the case
EPS_EFF = 0.75                    # board (solder mask 0.9) to wall (0.9), less what the holder, lens and heatsink shade
GAP_F, GAP_B = 0.0155, 0.0123     # mean depth of the back / front cavity (volume over the board's face), m
H_CAV = 0.058                     # cavity height along the board (enclosure aspect ratio)
K_AIR, NU_AIR, ALPHA_AIR = 0.0300, 2.1e-5, 3.0e-5     # air at ~ 85 C
MU_AIR, RHO_AIR, CP_AIR = 2.1e-5, 0.98, 1008.0
EDGE_GAP = 0.5e-3                 # board edge to the case wall (geometry.py: 2.0 mm wall, 0.5 mm clearance)
HOLDER_FACTOR = 0.5               # the front face under the IR-cut holder's base loses half as much (it traps air)
G_BOSS = 6e-4                     # each M2 screw into its printed boss, board to wall (column of PC-CF, ESTIMATED)

# ---------------------------------------------------------------- the board
K_CU, K_FR4 = 385.0, 0.8
# copper coverage per layer: measured on the routed board where KiCad's Python and the routed board are
# there; until then LayerCam v1's routed main board's (a board of the same stackup and plane plan, more
# densely packed), ESTIMATED for the Pro
COVER = {'F.Cu': 0.667, 'In1.Cu': 0.890, 'In2.Cu': 0.656, 'In3.Cu': 0.836, 'In4.Cu': 0.890, 'B.Cu': 0.728}
COVER_SRC = 'ESTIMATED: LayerCam v1\'s routed main board\'s figures (the Pro is not routed yet)'
CU_T = {'F.Cu': 0.035, 'B.Cu': 0.035, 'In1.Cu': 0.035, 'In2.Cu': 0.035, 'In3.Cu': 0.035, 'In4.Cu': 0.035}
BOARD_T = 1.6e-3
DX = 0.5e-3                       # grid, m
PLACE_SRC = 'src/layout_main.py FIXED (no routed board yet)'


def measure_cover():
    """Each copper layer's share of the outline on the routed board (needs KiCad's Python)."""
    global COVER_SRC
    if not (HAVE_PCBNEW and os.path.exists(ROUTED)):
        return
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    pcb.configure('main')
    b = pcbnew.LoadBoard(ROUTED)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    area = pcb.board_polygon().area
    for l in pcb.cu_layers():
        ps = pcbnew.SHAPE_POLY_SET()
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.GetLayerSet().Contains(l) and z.IsFilled():
                ps.Append(z.GetFilledPolysList(l))
        for t in b.GetTracks():
            if t.IsOnLayer(l):
                t.TransformShapeToPolygon(ps, l, 0, 5000, pcbnew.ERROR_INSIDE)
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(l):
                    p.TransformShapeToPolygon(ps, l, 0, 5000, pcbnew.ERROR_INSIDE)
        ps.Simplify()
        polys = []
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            ext = [pcb.xy(o.CPoint(k)) for k in range(o.PointCount())]
            holes = [[pcb.xy(ps.Hole(i, h).CPoint(k)) for k in range(ps.Hole(i, h).PointCount())]
                     for h in range(ps.HoleCount(i))]
            if len(ext) > 2:
                polys.append(Polygon(ext, holes).buffer(0))
        COVER[b.GetLayerName(l)] = round(unary_union(polys).area / area, 3)
    COVER_SRC = 'measured on the routed board (%s)' % os.path.relpath(ROUTED, V1)


# footprints the heat is spread over (mm, centred on the part's place)
FOOT = {'U1': (9.0, 9.0), 'U2': (3.0, 1.7), 'L1': (2.5, 2.0), 'U3': (3.0, 3.0), 'L2': (2.5, 2.0),
        'L3': (2.5, 2.0), 'L4': (2.5, 2.0), 'U4': (3.0, 1.7), 'L5': (2.5, 2.0), 'U6': (13.2, 12.5),
        'U5': (8.0, 6.0), 'U7': (2.0, 2.0), 'Q1': (2.9, 1.3), 'J1': (8.9, 7.3), 'U8': (5.75, 3.87),
        'U9': (2.0, 2.0), 'D2': (3.5, 2.8), 'D3': (3.5, 2.8), 'D4': (3.5, 2.8), 'D5': (3.5, 2.8),
        'D6': (3.5, 2.8), 'D7': (3.5, 2.8), 'R45': (3.2, 1.6), 'R46': (3.2, 1.6), 'R47': (3.2, 1.6)}

# ---------------------------------------------------------------- the heatsink and the RV1106
SINK = G.HEATSINK                 # 20 x 20 x 15 mm
SINK_BASE = 2.0e-3                # base plate (typical stock part, ASSUMED)
SINK_FINS, SINK_FIN_T = 7, 1.2e-3 # straight fins (typical 20 x 20 stock pattern, ASSUMED); gaps 1.9 mm
EPS_SINK = 0.85                   # black anodised (the usual stock finish; bare aluminium would be ~0.1)
H_FIN = 11.0                      # W/m^2K on the heatsink's outer envelope inside the case (LayerCam v1 estimate)
H_FIN_INNER = 3.0                 # on fin faces between fins (they see each other; air barely moves) (v1 estimate)
TAPE_T, TAPE_K = 0.25e-3, 0.6     # 3M 8810: 0.25 mm, 0.6 W/mK (3M data sheet)
INTERFACE_R = 0.5                 # tape to the package and to the heatsink: two contacts (ESTIMATED)
CHIP = 12.3e-3                    # RV1106G3 QFN-128
CHIP_H = 0.85e-3
THETA_JC_SOC = 8.4                # RV1106 datasheet table 4-1, junction to case (top)
R_DIE_EP = 3.0                    # die to exposed pad, ASSUMED (12 x 12 QFN, 7 x 7 pad)
THETA_JB_SOC = 12.5               # JEDEC 2s2p theta-JB, read from the board at the package edge (pessimistic)
N_EP_VIAS, VIA_DRILL, VIA_PLATE = 25, 0.20e-3, 18e-6     # layout_main.zones(): 5 x 5 filled vias
SOC_XY = tuple(LM.FIXED['U1'][:2])

# ---------------------------------------------------------------- the other parts' own resistances (K/W)
PSI_JB_TLV = 40.6                 # TLV62569 DBV (SLVSDG1C 6.4)
R_JB_EA = 15.0                    # EA3036C: thetaJC 7.5 + pad to board (ASSUMED)
R_JB_IND = 60.0                   # 2520 inductor on its pads (ASSUMED)
R_C6 = 6.0                        # ESP32-C6-MINI shield above the board (13.2 x 12.5 LGA with a 3 x 3 EPAD; ASSUMED)
PSI_JB_LDO = 64.8                 # TLV75528 DRV (SBVS320D 6.4)
R_JB_SENSOR = 15.0                # SC4336H CSP-35 die to board (ASSUMED: datasheet under NDA)
R_LED_J = 120.0                   # VSMY3850 junction to the board (its RthJA on a JEDEC board is 250 K/W; ASSUMED)

checks = []
SUMMARY = {'lim': {}}


def check(ok, what, warn=False):
    checks.append(('PASS' if ok else ('WARN' if warn else 'FAIL'), what))


# ---------------------------------------------------------------- geometry
def board_polygon():
    return pcb.board_polygon()


def placements():
    """ref -> (x, y, side): the routed board's places when it exists, else layout_main.FIXED and, for the
    string resistors (placed by place_small), a spot 3 mm outward from the LED they feed."""
    global PLACE_SRC
    out = {}
    if os.path.exists(ROUTED):
        s = open(ROUTED).read()
        for m in re.finditer(r'\(footprint "[^"]*"\s.*?\(layer "([FB])\.Cu"\).*?\(at ([-\d.]+) ([-\d.]+)'
                             r'(?: [-\d.]+)?\).*?\(property "Reference" "([A-Z]+\d+)"', s, re.S):
            out[m.group(4)] = (float(m.group(2)) - pcb.CX, float(m.group(3)) - pcb.CY, m.group(1))
        if out:
            PLACE_SRC = 'the routed board (layercam-pro.kicad_pcb)'
            return out
    for ref, v in LM.FIXED.items():
        if v:
            out[ref] = (float(v[0]), float(v[1]), v[3])
    for ref, _code in power.string_resistors():
        led = LM.ANCHOR.get([c.note for c in power.COMPS['main'] if c.ref == ref][0], ('D2', '1'))[0]
        x, y, _ = out[led]
        r = math.hypot(x, y) or 1.0
        out[ref] = (x + 3.0 * x / r, y + 3.0 * y / r, 'B')
    return out


def sheet_conductance(scale=1.0):
    cu = sum(CU_T[k] * 1e-3 * min(1.0, COVER[k] * scale) for k in CU_T)
    return K_CU * cu + K_FR4 * (BOARD_T - sum(CU_T.values()) * 1e-3)


def ep_via_resistance():
    a = math.pi * ((VIA_DRILL / 2 + VIA_PLATE) ** 2 - (VIA_DRILL / 2) ** 2)
    r_one = 0.155e-3 / (K_CU * a)          # F.Cu pad to In1, through PCBWay's 0.1195 mm 2116 + copper
    r_vias = r_one / N_EP_VIAS
    r_fr4 = 0.1195e-3 / (0.3 * 49e-6)      # the prepreg under the 7 x 7 pad, in parallel
    return 1 / (1 / r_vias + 1 / r_fr4)


def slot_boxes():
    """The lid slots in board coordinates (x0, y0, x1, y1), and which lie over the heatsink."""
    sx, sy = SOC_XY
    hw, hh = SINK[0] / 2, SINK[1] / 2
    out = []
    for yc in SLOT_YC:
        y = -yc
        over = (sy - hh <= y - 1.0) and (y + 1.0 <= sy + hh)
        out.append(((-10.0, y - 1.0, 10.0, y + 1.0), over))
    return out


# ---------------------------------------------------------------- the board solver
class Board:
    def __init__(self, cover_scale=1.0, cu_slot=None):
        """cu_slot = (y, x half-length): a cut through every copper layer along y between the SoC and the
        sensor (a design option the README names), FR4 only across it."""
        from shapely import contains_xy
        poly = board_polygon()
        x0, y0, x1, y1 = poly.bounds
        xs = np.arange(x0 + DX * 500, x1, DX * 1e3)
        ys = np.arange(y0 + DX * 500, y1, DX * 1e3)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        self.inside = contains_xy(poly, X, Y)
        for hx, hy in [(v[0], v[1]) for k, v in LM.FIXED.items() if k.startswith('H') and v]:
            self.inside &= (X - hx) ** 2 + (Y - hy) ** 2 > (1.1) ** 2      # screw holes
        self.X, self.Y, self.xs, self.ys = X, Y, xs, ys
        self.n = int(self.inside.sum())
        self.idx = -np.ones(X.shape, int)
        self.idx[self.inside] = np.arange(self.n)
        self.area = poly.area * 1e-6
        ks = sheet_conductance(cover_scale)
        k_fr4 = K_FR4 * BOARD_T
        rows, cols, vals = [], [], []
        nx, ny = X.shape
        for di, dj in ((1, 0), (0, 1)):
            a = self.idx[:nx - di, :ny - dj]
            b = self.idx[di:, dj:]
            m = (a >= 0) & (b >= 0)
            kk = np.full(a.shape, ks)
            if cu_slot and dj == 1:
                yc, xh = cu_slot
                ya, yb = Y[:nx - di, :ny - dj], Y[di:, dj:]
                cut = (ya < yc) & (yb >= yc) & (np.abs(X[:nx - di, :ny - dj]) <= xh)
                kk[cut] = k_fr4
            a, b, kk = a[m], b[m], kk[m]
            rows += [a, b, a, b]; cols += [a, b, b, a]
            vals += [kk, kk, -kk, -kk]
        self.K = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                               shape=(self.n, self.n))
        self.place = placements()
        out = ~self.inside
        nb = np.zeros_like(self.inside)
        nb[1:, :] |= out[:-1, :]; nb[:-1, :] |= out[1:, :]; nb[:, 1:] |= out[:, :-1]; nb[:, :-1] |= out[:, 1:]
        nb[0, :] = nb[-1, :] = True
        holes = np.zeros_like(self.inside)
        for hx, hy in [(v[0], v[1]) for k, v in LM.FIXED.items() if k in ('H1', 'H2', 'H3', 'H4')]:
            holes |= (X - hx) ** 2 + (Y - hy) ** 2 <= 2.25 ** 2
        self.edge = (self.inside & nb & ~holes)[self.inside]
        self.perimeter = poly.exterior.length * 1e-3       # m: the edge conductance is spread over the edge nodes
        self.boss = (self.inside & holes)[self.inside]
        sx, sy = SOC_XY
        self.under_sink = (self.mask(sx, sy, SINK[0], SINK[1]) & ~self.mask(sx, sy, CHIP * 1e3, CHIP * 1e3))[self.inside]
        hx0, hy0, hx1, hy1 = G.HOLDER_BOX
        self.under_holder = self.mask((hx0 + hx1) / 2, -(hy0 + hy1) / 2, hx1 - hx0, hy1 - hy0)[self.inside]

    def mask(self, x, y, w, h):
        return self.inside & (np.abs(self.X - x) <= w / 2) & (np.abs(self.Y - y) <= h / 2)

    def sources(self, heat):
        q = np.zeros(self.X.shape)
        for ref, p in heat.items():
            if ref in self.place and p:
                x, y, _ = self.place[ref]
                m = self.mask(x, y, *FOOT.get(ref, (2.0, 2.0)))
                if m.sum() == 0:
                    raise ValueError('no board under ' + ref)
                q[m] += p / m.sum()
        return q[self.inside]

    def solve(self, q, hF, hB, t_wall, t_sink, g_ovh):
        """Board temperatures: each node loses heat from its back face to the back cavity (under the heatsink's
        overhang, to the heatsink), from its front face to the front cavity (less under the IR-cut holder),
        from the outer edge across its clearance and at the screw bosses to the wall."""
        a = DX ** 2
        gF = np.full(self.n, hF * a)
        gF[self.under_sink] = 0.0
        gB = np.full(self.n, hB * a)
        gB[self.under_holder] *= HOLDER_FACTOR
        g_e = np.where(self.edge, K_AIR * self.perimeter * BOARD_T / EDGE_GAP / max(self.edge.sum(), 1), 0.0)
        g_b = np.where(self.boss, G_BOSS / max(self.boss.sum() / 4, 1), 0.0)
        g_wall = gF + gB + g_e + g_b
        g_s = np.zeros(self.n)
        g_s[self.under_sink] = g_ovh / self.under_sink.sum()
        A = self.K + sp.diags(g_wall + g_s)
        T = spla.spsolve(A.tocsc(), q + g_wall * t_wall + g_s * t_sink)
        self.last = dict(q_faces=float(((gF + gB) * (T - t_wall)).sum()), q_edge=float(((g_e + g_b) * (T - t_wall)).sum()),
                         q_sink=float((g_s * (T - t_sink)).sum()))
        full = np.full(self.X.shape, np.nan)
        full[self.inside] = T
        return full

    def at(self, T, ref, w=None, h=None, stat='mean'):
        x, y, _ = self.place[ref]
        fw, fh = FOOT.get(ref, (2.0, 2.0))
        m = self.mask(x, y, w or fw, h or fh)
        return float(np.nanmax(T[m]) if stat == 'max' else np.nanmean(T[m]))


# ---------------------------------------------------------------- heat transfer coefficients
def nu_enclosure(dt, gap):
    """Catton's correlation for a tall enclosure (Incropera eq. 9.52, H/L 2-10), at least conduction."""
    pr = NU_AIR / ALPHA_AIR
    ra = 9.81 * max(dt, 0.1) / (273.15 + T_AMB + 10) * gap ** 3 / (NU_AIR * ALPHA_AIR)
    return max(1.0, 0.22 * (pr / (0.2 + pr) * ra) ** 0.28 * (H_CAV / gap) ** -0.25)


def h_inside(t_b, t_w):
    tm = (t_b + t_w) / 2 + 273.15
    h_rad = 4 * SIGMA * EPS_EFF * tm ** 3
    dt = t_b - t_w
    return (h_rad + nu_enclosure(dt, GAP_F) * K_AIR / GAP_F, h_rad + nu_enclosure(dt, GAP_B) * K_AIR / GAP_B)


H_FORCED = 0.0                    # extra outside convection (chamber air moving), W/m^2K


def h_outside(t_w, t_amb):
    dt = max(t_w - t_amb, 0.5)
    h_conv = 1.32 * (dt / 0.05) ** 0.25 + H_FORCED   # laminar natural convection, 50 mm body (still chamber air)
    tm = (t_w + t_amb) / 2 + 273.15
    return h_conv + 4 * SIGMA * EPS_HOUSING * tm ** 3


def stack_flow(dt, dh, area, t_amb, channel=None):
    """Volume flow (m^3/s) of a stack-driven exchange: in through a lower opening, out through an upper one
    dh higher, the column between them dt warmer than the chamber.  Two orifices (each area, Cd 0.6) in series
    with, optionally, laminar flow through parallel-plate channels (n, gap, height, length)."""
    if dt <= 0 or dh <= 0:
        return 0.0
    dp = RHO_AIR * 9.81 * dh * dt / (t_amb + 273.15)
    a_or = 2 * RHO_AIR / 2 / (VENT_CD * area) ** 2               # dp = a_or Q^2 (both orifices)
    b_lam = 0.0
    if channel:
        n, s, hc, L = channel
        b_lam = 12 * MU_AIR * L / (n * s ** 3 * hc)              # dp = b_lam Q
    return (-b_lam + math.sqrt(b_lam ** 2 + 4 * a_or * dp)) / (2 * a_or)


# ---------------------------------------------------------------- the heatsink's paths
SLOTS_OPEN = True                 # the three slots over the heatsink open (False: taped over)
LID_PAD = None                    # (thickness m, k W/mK): a gap pad filling the gap from the fin tops to the lid


def sink_paths(t_s, t_amb, h_o):
    """Conductances (W/K) from the heatsink: to the inside air, to the lid's inner face, and straight to the
    chamber through its slots (conduction, radiation, and the exchange flow linearised at t_s)."""
    w, d, h = SINK[0] * 1e-3, SINK[1] * 1e-3, SINK[2] * 1e-3
    fin_h = h - SINK_BASE
    gaps = SINK_FINS - 1
    s = (w - SINK_FINS * SINK_FIN_T) / gaps
    env = 4 * w * h
    inner = gaps * 2 * d * fin_h
    g_air = H_FIN * env + H_FIN_INNER * inner
    over = [b for b, o in slot_boxes() if o]
    a_slots = len(over) * SLOT_L * SLOT_W if SLOTS_OPEN else 0.0
    a_top = w * d - a_slots
    h_rad_sl = 4 * SIGMA * (1 / (1 / EPS_SINK + 1 / 0.9 - 1)) * ((t_s + t_amb) / 2 + 273.15) ** 3
    phi = SINK_FINS * SINK_FIN_T / w                             # fin tips' share of the top
    if LID_PAD:
        tp, kp = LID_PAD
        g_gap = kp * phi * a_top / tp + K_AIR * (1 - phi) * a_top / (LID_GAP + s / 2)
    else:
        g_gap = K_AIR * phi * a_top / LID_GAP + K_AIR * (1 - phi) * a_top / (LID_GAP + s / 2) + h_rad_sl * a_top
    g_lid = 1 / (1 / g_gap + LID_T / (K_WALL * a_top))
    out = dict(g_air=g_air, g_lid=g_lid, a_slots=a_slots, g_slot_cond=0.0, g_slot_rad=0.0, q_stack=0.0)
    if a_slots:
        depth = LID_GAP + LID_T
        g_c1 = K_AIR * SLOT_W * SLOT_L / depth
        g_o1 = h_o * SLOT_W * SLOT_L
        out['g_slot_cond'] = len(over) / (1 / g_c1 + 1 / g_o1)
        f = math.sqrt(1 + (depth / SLOT_W) ** 2) - depth / SLOT_W          # view out of a slot (v1's plate.py)
        h_rad = 4 * SIGMA * EPS_SINK * ((t_s + t_amb) / 2 + 273.15) ** 3
        out['g_slot_rad'] = h_rad * f * a_slots
        # exchange flow: in at the lowest slot over the fins, out at the highest, through the fin channels
        # (fins assumed to run across the slots, the favourable case); the column at the heatsink's temperature
        ys = sorted(b[1] for b in over)
        dh = (ys[-1] - ys[0]) * 1e-3 * math.cos(math.radians(TILT))
        q = stack_flow(t_s - t_amb, dh, SLOT_L * SLOT_W, t_amb,
                       channel=(gaps, s, fin_h, (ys[-1] - ys[0]) * 1e-3))
        out['q_stack'] = RHO_AIR * CP_AIR * q * max(t_s - t_amb, 0.0)
    out['g_amb'] = out['g_slot_cond'] + out['g_slot_rad'] + out['q_stack'] / max(t_s - t_amb, 0.1)
    return out


def tape_r():
    return TAPE_T / (TAPE_K * CHIP ** 2) + INTERFACE_R


def r_top():
    return THETA_JC_SOC + tape_r() + 0.3                         # + the base's spreading (estimate)


def g_overhang(hF):
    """The board under the heatsink's overhang to the heatsink's underside, across the package's height."""
    a = (SINK[0] * SINK[1]) * 1e-6 - CHIP ** 2
    gap = CHIP_H + TAPE_T
    return (K_AIR / gap + 4 * SIGMA * 0.8 * 358 ** 3) * a


def lid_patch():
    """The lid round the heatsink: its outer area and its conductance into the rest of the case."""
    w = SINK[0] * 1e-3
    lam = math.sqrt(K_WALL_INPLANE * LID_T / 11.0)
    a_slots_all = len(SLOT_YC) * SLOT_L * SLOT_W
    a = min((w + 2 * lam) ** 2, LID_TOP_AREA) - a_slots_all
    g_pw = K_WALL_INPLANE * LID_T * 4 * (w + 2 * lam) / lam
    return a, g_pw


# ---------------------------------------------------------------- the whole case
SINK_ON = True


def vent_flow_w(t_air, t_amb):
    """The back cavity's air through the three slots that are not over the heatsink (stack effect)."""
    other = [b for b, o in slot_boxes() if not o]
    ys = sorted(b[1] for b in other)
    dh = (ys[-1] - ys[0]) * 1e-3 * math.cos(math.radians(TILT))
    q = stack_flow(t_air - t_amb, dh, SLOT_L * SLOT_W, t_amb)
    return RHO_AIR * CP_AIR * q * max(t_air - t_amb, 0.0)


def run_case(board, heat, t_amb=T_AMB, led_on=None, vents=True):
    heat_in = dict(heat)
    heat = dict(heat)
    p_total = sum(heat.values())
    p_soc = heat.get('U1', 0.0)
    q_top = 0.0
    q_board = board.sources(heat)
    r_jb = R_DIE_EP + ep_via_resistance()
    rt = r_top()
    a_p, g_pw = lid_patch()
    if not SINK_ON:
        a_p, g_pw = 0.0, 0.0
    t_w = t_amb + 8.0
    t_b = t_w + 15.0
    t_s = t_b
    t_p = t_w
    tj = t_b
    q = q_board
    for it in range(400):
        hF, hB = h_inside(t_b, t_w)
        g_ovh = g_overhang(hF) if SINK_ON else 0.0
        T = board.solve(q, hF, hB, t_w, t_s, g_ovh)
        t_b_new = float(np.nanmean(T))
        t_air = (t_b_new + t_w) / 2
        h_o = h_outside(t_w, t_amb)
        q_vent = vent_flow_w(t_air, t_amb) if vents else 0.0
        q_slot = q_patch = 0.0
        sp_ = None
        if SINK_ON:
            t_ep = float(np.nanmean(T[board.mask(*SOC_XY, 7.0, 7.0)]))
            t_under = float(np.nanmean(T[board.mask(*SOC_XY, SINK[0], SINK[1])]))
            sp_ = sink_paths(t_s, t_amb, h_o)
            ga, gl, gs = sp_['g_air'], sp_['g_lid'], sp_['g_amb']
            ho_p = h_o * a_p
            # unknowns Tj, Ts, Tp
            M = np.array([[1 / r_jb + 1 / rt, -1 / rt, 0.0],
                          [-1 / rt, 1 / rt + g_ovh + ga + gl + gs, -gl],
                          [0.0, -gl, gl + g_pw + ho_p]])
            rhs = [p_soc + t_ep / r_jb, g_ovh * t_under + ga * t_air + gs * t_amb, g_pw * t_w + ho_p * t_amb]
            tj, t_s_new, t_p_new = np.linalg.solve(M, rhs)
            q_top_new = (tj - t_s_new) / rt
            q_top = 0.5 * q_top + 0.5 * q_top_new
            t_s = 0.5 * t_s + 0.5 * t_s_new
            t_p = t_p_new
            q_slot = gs * (t_s - t_amb)
            q_patch = ho_p * (t_p - t_amb)
            h2 = dict(heat)
            h2['U1'] = p_soc - q_top
            q = board.sources(h2)
        # everything else reaches the wall and leaves through it
        q_into_wall = p_total - q_vent - q_slot - q_patch
        r_wall = WALL_T / (K_WALL * A_IN) + 1 / (h_o * (A_OUT - a_p))
        t_w_new = t_amb + (q_into_wall + BED_RAD_W) * r_wall
        done = abs(t_w_new - t_w) < 2e-3 and abs(t_b_new - t_b) < 2e-3 and (not SINK_ON or abs(q_top - q_top_new) < 1e-4)
        t_w = 0.5 * t_w + 0.5 * t_w_new
        t_b = t_b_new
        if done:
            break
    return dict(T=T, t_w=t_w, t_b=t_b, t_air=(t_b + t_w) / 2, q_vent=q_vent, p_total=p_total, t_amb=t_amb,
                heat=heat, heat_in=heat_in, flows=dict(board.last), h_in=(hF, hB), h_out=h_o, led_on=led_on,
                q_top=q_top, t_sink=t_s if SINK_ON else None, t_patch=t_p if SINK_ON else None, q_slot=q_slot,
                q_patch=q_patch, sink=sp_, tj_top=tj, iters=it)


# ---------------------------------------------------------------- per-part temperatures
TEMP_CLASS = {'X5R': 85, 'X6S': 105, 'X7S': 125, 'X7R': 125, 'C0G': 125}


def cap_class(codes):
    out = {}
    for c in codes:
        d = re.search(r'\b(X\d[RSPT]|C0G)\b', parts.PARTS[c]['desc']).group(1)
        out.setdefault((d, TEMP_CLASS[d]), []).append(c)
    return out


SENSOR = 'SC4336H image sensor (U8)'
C6 = 'ESP32-C6-MINI-1U-H4 (U6)'
TJ = 'RV1106 junction (U1)'


def part_temps(board, res, case=None):
    T = res['T']
    heat = res['heat']
    out = []        # (name, temperature, limit, limit source)
    p_soc = heat['U1'] - res.get('q_top', 0.0)
    r_via = ep_via_resistance()
    t_ep = board.at(T, 'U1', 7.0, 7.0)
    x, y, _ = board.place['U1']
    band = board.mask(x, y, 14.3, 14.3) & ~board.mask(x, y, 12.3, 12.3)
    t_edge = float(np.nanmean(T[band]))
    tj_a = t_ep + p_soc * (R_DIE_EP + r_via)
    tj_b = t_edge + p_soc * THETA_JB_SOC
    tj = max(tj_a, tj_b)
    res['soc'] = dict(t_ep=t_ep, t_edge=t_edge, tj_a=tj_a, tj_b=tj_b, r_via=r_via, p=p_soc)
    out.append((TJ, tj, 125, 'Tj max (datasheet 4.1)'))
    out.append(('internal air (RV1106 / EA3036C ambient)', res['t_air'], 85, 'ambient operating max (RV1106 T3-2, '
                'EA3036C TA)'))
    if res.get('t_sink') is not None:
        t_top = tj - (tj - res['t_sink']) * THETA_JC_SOC / r_top()
        out.append(('3M 8810 tape on the RV1106', t_top, 100, 'long-term 100 C (3M; UNVERIFIED: data sheet not '
                    'read here)'))
    p_s = heat.get('U8', 0.0)
    out.append((SENSOR, board.at(T, 'U8', stat='max') + p_s * R_JB_SENSOR, 85,
                '-30..85 C operating; best image to 60 C (SmartSens)'))
    out.append((C6, board.at(T, 'U6', stat='max') + heat.get('U6', 0) * R_C6, 105, '-40..105 C, the -H4 grade '
                '(Espressif)'))
    out.append(('W25N02KV flash (U5)', board.at(T, 'U5', stat='max') + heat.get('U5', 0) * 20, 85, '-40..85 C (Winbond)'))
    out.append(('USB-C receptacle USB4105 (J1)', board.at(T, 'J1', stat='max') + 1.0, 85, '-40..85 C incl. rise (GCT)'))
    out.append(('status LED LED1 (KT-0603G)', board.at(T, 'LED1', 2, 2, stat='max'), 85, '-40..85 C (KENTO)'))
    for ref, nm in (('U2', 'TLV62569 0.9 V (U2)'), ('U4', 'TLV62569 Wi-Fi (U4)')):
        out.append((nm + ' junction', board.at(T, ref, stat='max') + heat.get(ref, 0) * PSI_JB_TLV, 125,
                    'TJ max (SLVSDG1C 6.3)'))
    out.append(('EA3036C junction (U3)', board.at(T, 'U3', stat='max') + heat.get('U3', 0) * R_JB_EA, 125,
                'TJ range (datasheet)'))
    out.append(('TLV75528 sensor LDO junction (U9)', board.at(T, 'U9', stat='max') + heat.get('U9', 0) * PSI_JB_LDO,
                125, 'TJ max (SBVS320D)'))
    for ref in ('L1', 'L2', 'L3', 'L4', 'L5'):
        out.append(('inductor %s (DFE252012F)' % ref, board.at(T, ref, stat='max') + heat.get(ref, 0) * R_JB_IND, 125,
                    '-40..125 C incl. self-heating (Murata)'))
    out.append(('DRV8210P IR-cut driver (U7)', board.at(T, 'U7', stat='max'), 125, 'TA -40..125 C (TI)'))
    big = cap_class(('C1U', 'C2U2', 'C4U7', 'C10U', 'C22U'))
    for (cls, lim), refs in big.items():
        nm = '%s capacitors (%s)' % (cls, ', '.join(parts.PARTS[c]['value'] for c in refs))
        src = '%s: -55..%d C' % (cls, lim)
        out.append((nm + ' under the SoC (B face)', board.at(T, 'U1', 12.0, 12.0, stat='max'), lim, src))
        out.append((nm + ' at the bucks', max(board.at(T, r, 5, 5, stat='max') for r in ('U2', 'U3', 'U4')), lim, src))
        out.append((nm + ' at the sensor', board.at(T, 'U8', 11.2, 8.8, stat='max'), lim, src))
    out.append(('crystals Y1 (24 MHz) / Y2 (32 kHz)', max(board.at(T, r, 3, 3, stat='max') for r in ('Y1', 'Y2')), 125,
                '-40..125 C (ECS, Abracon)'))
    out.append(('TEMT6000 light sensor (Q2)', board.at(T, 'Q2', 4, 2, stat='max'), 100, '-40..100 C (Vishay)'))
    out.append(('PicoBlade IR-cut lead socket (J3)', board.at(T, 'J3', 4, 4, stat='max'), 105, '-40..105 C (Molex)'))
    out.append(('USBLC6 / SMF6.0CA (U10 / D1)', max(board.at(T, r, 3, 3, stat='max') for r in ('U10', 'D1')), 125,
                'TJ to 125 / 150 C'))
    led_b = max(board.at(T, 'D%d' % k, stat='max') for k in range(2, 8))
    p_led = _led_heat_each(res)
    out.append(('IR LEDs VSMY3850X01, junction while lit', led_b + p_led * R_LED_J, 100,
                'Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade\'s own data sheet not read)'))
    out.append(('IR LEDs VSMY3850X01, ambient', res['t_air'] * 0.5 + led_b * 0.5, 105,
                '-40..105 C, X01 grade (parts.py; the base part is rated 85 C)'))
    out.append(('case wall (PC carbon fibre)', res['t_w'], 110, 'softens near its HDT, ~110 C (PC; ESTIMATED)'))
    return out


def _led_heat_each(res):
    """Each LED's heat while lit: the junction follows the instantaneous power (its time constant is far
    shorter than a 2 s flash), the board the average."""
    if res.get('led_on'):
        return res['led_on'][0]
    return res['heat_in'].get('D2', 0.0)


def resistor_check(board, res):
    """String resistors 1206 (UNI-ROYAL 1206W4F): 0.25 W at 70 C, linear to 0 at 155 C; checked at their
    power while lit (a 1206 heats in about a second, so a 2 s flash is near steady state), their ambient the
    board under them."""
    h = res['led_on'][1] if res.get('led_on') else 0.0
    refs = [r for r, _ in power.string_resistors()]
    t = max(board.at(res['T'], r, stat='max') for r in refs)
    rating = 0.25 * min(1.0, max(0.0, (155 - t) / (155 - 70)))
    return h, t, rating


# ---------------------------------------------------------------- plotting
def plot(board, res, name, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from PIL import Image
    fig, ax = plt.subplots(figsize=(5.4, 4.6), dpi=100)
    T = res['T']
    ext = [board.xs[0], board.xs[-1], board.ys[-1], board.ys[0]]
    im = ax.imshow(T.T, extent=ext, origin='upper', cmap='inferno')
    sx, sy = SOC_XY
    ax.add_patch(Rectangle((sx - SINK[0] / 2, sy - SINK[1] / 2), SINK[0], SINK[1], fill=False, ec='w', lw=0.6, ls='--'))
    for (x0, y0, x1, y1), over in slot_boxes():
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec='c' if over else '0.6', lw=0.5))
    for ref in ('U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U8', 'U9', 'J1', 'LED1'):
        x, y, side = board.place[ref]
        ax.text(x, y, ref, color='cyan', ha='center', va='center', fontsize=6)
    ax.set_title(title, fontsize=8)
    ax.set_xlabel('board x (mm), seen from the back (F); dashed: heatsink, cyan: its slots', fontsize=6)
    ax.tick_params(labelsize=6)
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label('board temperature (C)', fontsize=7)
    cb.ax.tick_params(labelsize=6)
    fig.tight_layout()
    path = os.path.join(HERE, 'thermal_%s.png' % name)
    fig.savefig(path)
    plt.close(fig)
    Image.open(path).convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
    return os.path.basename(path)


# ---------------------------------------------------------------- write-up helpers
def ambient_limit(board, heat, limit_fn, lo=-20.0, hi=85.0, led_on=None):
    """The highest chamber temperature at which limit_fn holds (bisection), or None if it never does."""
    if not limit_fn(board, run_case(board, heat, t_amb=lo, led_on=led_on)):
        return None
    if limit_fn(board, run_case(board, heat, t_amb=hi, led_on=led_on)):
        return hi
    for _ in range(10):
        mid = (lo + hi) / 2
        ok = limit_fn(board, run_case(board, heat, t_amb=mid, led_on=led_on))
        lo, hi = (mid, hi) if ok else (lo, mid)
    return lo


def first_over(board, heat, t_amb, led_on=None):
    res = run_case(board, heat, t_amb=t_amb, led_on=led_on)
    over = sorted(((t - lim, nm) for nm, t, lim, src in part_temps(board, res)), reverse=True)
    return over[0][1]


def within(board, res, keys=None):
    for name, t, lim, src in part_temps(board, res):
        if keys and not any(k in name for k in keys):
            continue
        if t > lim:
            return False
    return True


def ptemp(board, res, key):
    return {nm: t for nm, t, lim, src in part_temps(board, res)}[key]


CASES = [('snap_day_ps', 'Snapshot, day, Wi-Fi power save on (the rating)', 'req'),
         ('snap_night_ps', 'Snapshot, night, IR LEDs lit 2 s of every 10 s, Wi-Fi power save on (the rating)', 'req'),
         ('snap_day', 'Snapshot, day, Wi-Fi power save off (information)', 'info'),
         ('snap_night', 'Snapshot, night, Wi-Fi power save off (information)', 'info'),
         ('day', 'Live view, day: streaming (reported, not required)', 'live'),
         ('night', 'Live view, night: streaming with the IR LEDs on (reported, not required)', 'live'),
         ('worst', 'Stress bound: SoC flat out, Wi-Fi transmitting, LEDs at the high corner (reported)', 'stress')]
SHORT = {'snap_day': 'snapshot day, PS off', 'snap_night': 'snapshot night, PS off', 'snap_day_ps': 'snapshot day, PS on',
         'snap_night_ps': 'snapshot night, PS on', 'day': 'live view day', 'night': 'live view night',
         'worst': 'stress bound'}


def led_of(name):
    h = power.heat(name)
    return power.led_on(name) if h.get('D2') else None


def case_run(board, name, **kw):
    return run_case(board, power.heat(name), led_on=led_of(name), **kw)


def tj_of(board, res):
    part_temps(board, res)
    return max(res['soc']['tj_a'], res['soc']['tj_b'])


def fmt_amb(a):
    return 'never (not even at -20 C)' if a is None else ('85 C or more' if a >= 84.9 else '%.1f C' % a)


# ---------------------------------------------------------------- the report
def main():
    global EPS_EFF, NU_AIR, H_FORCED, TILT, SLOTS_OPEN, LID_PAD, SINK_ON, K_WALL, K_WALL_INPLANE
    measure_cover()
    board = Board()
    L = []
    w = L.append
    w('# LayerCam Pro v1: temperatures, rated for a @TA@ chamber\n')
    w('Computed by `sim/thermal.py`: the one board as a 2D plate on a 0.5 mm grid (outline from `src/pcb.py` / '
      '`src/geometry.py`, part places from %s, heat from `sim/power_budget.py`), in the PC-CF case with Prusa\'s '
      'outside, its stock 20 x 20 x 15 mm heatsink under three lid slots, in a %.0f C chamber with still air. The '
      'model and every assumed number are listed at the end; the copper coverage is %s.\n'
      % (PLACE_SRC, T_AMB, COVER_SRC))
    w('**The rating: a %.0f C chamber.** The owner decided (1 Nov 2026) that LayerCam Pro is rated for a %.0f C '
      'chamber, not 70 C: every part inside its rating in **snapshot mode** (one still at most every 10 s; a timelapse '
      'frame per layer is one of those shots, so timelapse mode is the same load), day and night, with the ESP32-C6\'s '
      '**Wi-Fi power save on** (the C6 firmware build sets it). Prusa\'s firmware caps the chamber at %.0f C on the '
      'CORE One and %.0f C on the CORE One L, so %.0f C is %.0f K above the higher of the two. This script exits 1 '
      'only if that requirement fails (`snap_day_ps`, `snap_night_ps` at %.0f C). The earlier 70 C target and power '
      'save off (`snap_day`, `snap_night`, the C6 as first built) are reported as information, not checked; so are '
      'live view and the stress bound.\n'
      % (T_AMB, T_AMB, PRUSA_CAP[0], PRUSA_CAP[1], T_AMB, T_AMB - PRUSA_CAP[1], T_AMB))
    w('A 10 s cycle is modelled by its average heat (the case\'s time constant is many minutes); the LED junctions and '
      'string resistors are checked at their power while lit. Each case below is at the %.0f C rating; the verdict '
      'also gives every mode at %.0f C.\n' % (T_AMB, T_INFO))
    w('Board: %.1f cm^2 a face; in-plane conductance %.4f W/K per square (copper coverage F %.0f %%, In1 %.0f %%, '
      'In2 %.0f %%, In3 %.0f %%, In4 %.0f %%, B %.0f %%). SoC exposed pad to the planes: %.2f K/W through %d filled '
      'vias; junction to heatsink %.1f K/W (theta-JC top %.1f + 3M 8810 tape %.1f + base 0.3).\n'
      % (board.area * 1e4, sheet_conductance(), *[100 * COVER[k] for k in
                                                 ('F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu')],
         ep_via_resistance(), N_EP_VIAS, r_top(), THETA_JC_SOC, tape_r()))
    allres = {}
    for name, title, kind in CASES:
        res = case_run(board, name)
        allres[name] = res
        temps = part_temps(board, res, name)
        h = power.heat(name)
        w('## %s\n' % title)
        top = sorted(((k, v) for k, v in h.items() if v > 0.005), key=lambda kv: -kv[1])
        w('Heat in the case: **%.2f W** (%s).\n' % (sum(h.values()), ', '.join('%s %.2f' % (k, v) for k, v in top)))
        so = res['soc']
        sk = res['sink']
        w('| | value |\n|---|---|')
        w('| case wall | %.1f C (%.1f K over the chamber) |' % (res['t_w'], res['t_w'] - T_AMB))
        w('| air inside (mean of board and wall) | %.1f C |' % res['t_air'])
        w('| board mean / max | %.1f / %.1f C |' % (np.nanmean(res['T']), np.nanmax(res['T'])))
        w('| board heat out: faces / edge and bosses / into the heatsink\'s underside | %.2f / %.2f / %.2f W |'
          % (res['flows']['q_faces'], res['flows']['q_edge'], res['flows']['q_sink']))
        w('| heatsink | %.1f C; %.2f W from the junction; out to the chamber through its slots %.3f W (exchange flow '
          '%.3f W), through the lid patch %.3f W (patch %.1f C) |'
          % (res['t_sink'], res['q_top'], res['q_slot'], sk['q_stack'], res['q_patch'], res['t_patch']))
        w('| other slots\' air exchange | %.3f W |' % res['q_vent'])
        w('| RV1106 | %.2f W into the board; board under the pad %.1f C, at the package edge %.1f C; Tj %.1f C (pad path) '
          '/ %.1f C (theta-JB 12.5 from the edge) |' % (so['p'], so['t_ep'], so['t_edge'], so['tj_a'], so['tj_b']))
        w('')
        w('| part | temperature (C) | limit (C) | margin (K) | limit from |\n|---|---|---|---|---|')
        for nm, t, lim, src in sorted(temps, key=lambda r: r[2] - r[1]):
            w('| %s | %.1f | %.0f | %+.1f | %s |' % (nm, t, lim, lim - t, src))
        hr, tr, rating = resistor_check(board, res)
        if hr > 0:
            w('| 47R string resistors, power while lit | %.3f W | %.3f W at %.0f C | %+.3f W | 0.25 W to 70 C, 0 at '
              '155 C |' % (hr, rating, tr, rating - hr))
        ts = ptemp(board, res, SENSOR)
        w('\nImage sensor: **%.1f C** against its 85 C rating (%+.1f K) and its best-image limit of 60 C (%+.1f K).\n'
          % (ts, 85 - ts, 60 - ts))
        png = plot(board, res, name, '%s: chamber %.0f C' % (SHORT[name], T_AMB))
        w('![%s](%s)\n' % (name, png))
        if kind != 'req':
            continue
        for nm, t, lim, src in temps:
            soft = any(k in nm for k in ('internal air', 'case wall', 'tape', 'ambient'))
            check(t <= lim, '%s: %s %.1f C against %.0f C (%s)' % (name, nm, t, lim, src),
                  warn=soft and t <= lim + 5)
        if hr > 0:
            check(hr <= rating, '%s: string resistor %.3f W while lit against %.3f W derated at %.0f C'
                  % (name, hr, rating, tr))
        check(ts <= 60, '%s: image sensor %.1f C against its best-image 60 C' % (name, ts), warn=True)
        check(ptemp(board, res, TJ) <= 115, '%s: RV1106 junction %.1f C with 10 K margin (115 C)'
              % (name, ptemp(board, res, TJ)), warn=True)

    # ------------------------------------------------ the same modes at 70 C (information)
    SUMMARY['at70'] = {name: case_run(board, name, t_amb=T_INFO) for name, title, kind in CASES if name != 'worst'}

    # ------------------------------------------------ what moves it
    w('## Sensitivity (snap_night_ps: the rating case, night, power save on, @TA@)\n')
    w('| change | RV1106 Tj (C) | image sensor (C) | C6 (C) | flash (C) | USB-C (C) | heatsink (C) | out by the slots '
      '/ lid patch (W) |\n|---|---|---|---|---|---|---|---|')

    def row(lab, res, b=board):
        w('| %s | %.1f | %.1f | %.1f | %.1f | %.1f | %s | %s |'
          % (lab, tj_of(b, res), ptemp(b, res, SENSOR), ptemp(b, res, C6), ptemp(b, res, 'W25N02KV flash (U5)'),
             ptemp(b, res, 'USB-C receptacle USB4105 (J1)'),
             '%.1f' % res['t_sink'] if res['t_sink'] is not None else '-',
             '%.3f / %.3f' % (res['q_slot'], res['q_patch'])))
    base = allres[REQ_NIGHT]
    row('as above', base)
    row('Wi-Fi power save off (snap_night, information)', allres['snap_night'])
    SINK_ON = False
    r_ns = case_run(board, REQ_NIGHT)
    row('no heatsink (bare chip)', r_ns)
    SINK_ON = True
    SLOTS_OPEN = False
    row('the three slots over the heatsink taped over', case_run(board, REQ_NIGHT))
    SLOTS_OPEN = True
    t0 = TILT
    TILT = 90.0
    row('camera looking straight down (slots level: no exchange flow)', case_run(board, REQ_NIGHT))
    TILT = 0.0
    row('camera looking level (slots one above the other)', case_run(board, REQ_NIGHT))
    TILT = t0
    LID_PAD = (1.0e-3, 6.0)
    r_pad = case_run(board, REQ_NIGHT)
    row('a 1 mm 6 W/mK gap pad from the fin tops to the lid (option)', r_pad)
    within_ = lambda b, r: within(b, r)
    SUMMARY['pad_lim'] = (ambient_limit(board, power.heat('snap_night'), within_, led_on=led_of('snap_night')),
                          ambient_limit(board, power.heat('snap_night_ps'), within_, led_on=led_of('snap_night_ps')))
    LID_PAD = None
    b_slot = Board(cu_slot=(5.4, 11.0))
    row('a slot through the copper between SoC and sensor (y 5.4, 22 mm long; option)', case_run(b_slot, REQ_NIGHT),
        b_slot)
    b2 = Board(cover_scale=0.7)
    row('copper coverage x0.7 (a more perforated routed board)', case_run(b2, REQ_NIGHT), b2)
    k0, k1 = K_WALL, K_WALL_INPLANE
    K_WALL, K_WALL_INPLANE = 0.20, 0.25
    row('case wall 0.20 W/mK (plain PC)', case_run(board, REQ_NIGHT))
    K_WALL, K_WALL_INPLANE = 0.50, 0.90
    row('case wall 0.50 / 0.90 W/mK (high fibre loading)', case_run(board, REQ_NIGHT))
    K_WALL, K_WALL_INPLANE = k0, k1
    e0 = EPS_EFF
    EPS_EFF = 0.6
    row('inside emissivity 0.6 (bare metal holder, lens, shields)', case_run(board, REQ_NIGHT))
    EPS_EFF = 0.85
    b3 = Board(cover_scale=1.2)
    r3 = case_run(b3, REQ_NIGHT)
    row('optimistic bracket: emissivity 0.85, copper x1.2', r3, b3)
    SUMMARY['opt'] = (tj_of(b3, r3), ptemp(b3, r3, SENSOR))
    EPS_EFF = e0
    H_FORCED = 3.9 * math.sqrt(0.5 / 0.05) - 1.32 * (10 / 0.05) ** 0.25
    row('chamber air moving at 0.5 m/s past the case', case_run(board, REQ_NIGHT))
    H_FORCED = 0.0
    hq = dict(power.heat(REQ_NIGHT)); hq['U1'] *= 1.5
    row('SoC idle 50 % higher than assumed', run_case(board, hq, led_on=led_of(REQ_NIGHT)))
    hq = dict(power.heat(REQ_NIGHT)); hq['U6'] *= 1.3
    row('C6 30 % above its datasheet figures (hot)', run_case(board, hq, led_on=led_of(REQ_NIGHT)))
    w('')

    # ------------------------------------------------ chamber limits
    w('## Highest chamber temperature per case\n')
    w('Bisection on the same model: the chamber temperature at which the first part reaches its limit, and the '
      'image sensor\'s two limits.\n')
    w('| case | every part inside its limit up to (first part there) | image sensor 85 C at | image sensor 60 C '
      '(best image) at | RV1106 Tj 125 C at |')
    w('|---|---|---|---|---|')
    for name, title, kind in CASES:
        h = power.heat(name)
        lo = led_of(name)
        a_all = ambient_limit(board, h, lambda b, r: within(b, r), led_on=lo)
        a_85 = ambient_limit(board, h, lambda b, r: ptemp(b, r, SENSOR) <= 85, led_on=lo)
        a_60 = ambient_limit(board, h, lambda b, r: ptemp(b, r, SENSOR) <= 60, led_on=lo)
        a_125 = ambient_limit(board, h, lambda b, r: tj_of(b, r) <= 125, led_on=lo)

        def lab(a):
            if a is None:
                return 'never (%s)' % first_over(board, h, -20.0, led_on=lo)
            if a >= 84.9:
                return '85 C or more'
            return '%.1f C (%s)' % (a, first_over(board, h, a + 0.3, led_on=lo))
        SUMMARY['lim'][name] = dict(all=a_all, s85=a_85, s60=a_60, tj=a_125,
                                    first=None if a_all is None or a_all >= 84.9 else first_over(board, h, a_all + 0.3, led_on=lo))
        w('| %s | %s | %s | %s | %s |' % (SHORT[name], lab(a_all), fmt_amb(a_85), fmt_amb(a_60), fmt_amb(a_125)))
    w('')
    for n in REQ:
        a = SUMMARY['lim'][n]['all']
        check(a is not None and a >= T_AMB, '%s keeps every part inside its rating up to a %s chamber (rating '
              '%.0f C)' % (n, fmt_amb(a), T_AMB))
    lim_req = min((SUMMARY['lim'][n]['all'] if SUMMARY['lim'][n]['all'] is not None else -99) for n in REQ)
    check(lim_req >= T_AMB + 5, 'snapshot-mode margin %.1f K at @TA@ (power save on), against a model uncertainty of '
          'about +-10 K' % (lim_req - T_AMB), warn=True)

    # ------------------------------------------------ firmware rules
    w('## Firmware rules (thermal governor)\n')
    w('The RV1106\'s TSADC reads its own junction (+-3 C). In a steady state every part sits at a fixed offset from '
      'it for a given load, so the junction temperature at the chamber where the first part reaches its rating is a '
      'threshold for that mode, less the sensor\'s 3 C error.\n')
    w('| mode | chamber limit (first part) | RV1106 Tj there (steady state) | rule: allowed while TSADC below | '
      'at @TA@ the TSADC reads |')
    w('|---|---|---|---|---|')
    rd = SUMMARY.setdefault('rule', {})
    for name in ('snap_day_ps', 'snap_night_ps', 'snap_day', 'snap_night', 'day', 'night'):
        a = SUMMARY['lim'][name]['all']
        h = power.heat(name)
        tj70 = tj_of(board, allres[name])
        if a is None or a >= 84.9:
            w('| %s | %s | - | - | %.0f C |' % (SHORT[name], fmt_amb(a), tj70))
            continue
        tj = tj_of(board, run_case(board, h, t_amb=a, led_on=led_of(name)))
        rd[name] = (a, tj)
        w('| %s | %.1f C (%s) | %.0f C | **%.0f C** | %.0f C |' % (SHORT[name], a, SUMMARY['lim'][name]['first'], tj,
                                                                   tj - 3, tj70))
    w('')
    t_live = min([rd[n][1] for n in ('day', 'night') if n in rd] or [100]) - 3
    t_snap = min([rd[n][1] for n in REQ if n in rd] or [100]) - 3
    SUMMARY['gov'] = (t_live, t_snap)
    w('1. **Snapshot mode is the default**: CPU at its lowest OPP between shots, NPU off, sensor in standby, the C6\'s '
      'Wi-Fi power save on (the rating assumes it).')
    w('2. **Live view** only while TSADC < %.0f C; above it, back to snapshot mode ("live view paused: camera too '
      'warm").' % t_live)
    w('3. TSADC > %.0f C in snapshot mode: stretch the interval to 30 s, cap Wi-Fi TX power, shorten the IR flash.'
      % t_snap)
    w('4. TSADC > 110 C: stop capturing (keep Wi-Fi associated, report the fault); > 120 C power the sensor and Wi-Fi '
      'down; Linux critical trip at 125 C.')
    w('')

    # ------------------------------------------------ the heat paths
    a_p, g_pw = lid_patch()
    sp0 = sink_paths(base['t_sink'], T_AMB, base['h_out'])
    w('## The heatsink and the slots\n')
    w('snap_night_ps at @TA@. The junction sends %.2f W of its %.2f W into the heatsink (junction to heatsink %.1f K/W, '
      'against %.1f K/W into the board); the heatsink at %.1f C passes it on:\n'
      % (base['q_top'], power.heat(REQ_NIGHT)['U1'], r_top(), R_DIE_EP + ep_via_resistance(), base['t_sink']))
    w('| path from the heatsink | conductance (W/K) | heat (W) |\n|---|---|---|')
    t_air = base['t_air']
    w('| sides and fins to the air inside the case (%.0f mm^2 of envelope at %.0f W/m^2K, %.0f mm^2 of fin faces at %.0f) '
      '| %.4f | %.3f |' % (4 * SINK[0] * SINK[2], H_FIN, (SINK_FINS - 1) * 2 * SINK[1] * (SINK[2] - SINK_BASE * 1e3),
                           H_FIN_INNER, sp0['g_air'], sp0['g_air'] * (base['t_sink'] - t_air)))
    w('| top across the 0.7 mm gap and 1.6 mm of lid into the lid patch (%.1f cm^2 outside, %.4f W/K into the rest of '
      'the lid) | %.4f | %.3f |' % (a_p * 1e4, g_pw, sp0['g_lid'], sp0['g_lid'] * (base['t_sink'] - base['t_patch'])))
    w('| up the three slots\' still air (2.3 mm) to the chamber | %.4f | %.3f |'
      % (sp0['g_slot_cond'], sp0['g_slot_cond'] * (base['t_sink'] - T_AMB)))
    w('| radiation out through the slots | %.4f | %.3f |' % (sp0['g_slot_rad'], sp0['g_slot_rad'] * (base['t_sink'] - T_AMB)))
    w('| exchange flow, in at the lowest slot and out at the highest (%.1f mm higher at a %.0f deg tilt) through the '
      'fin channels | %.4f | %.3f |' % (8.0 * math.cos(math.radians(TILT)), TILT,
                                        sp0['q_stack'] / max(base['t_sink'] - T_AMB, 0.1), sp0['q_stack']))
    w('| the board under its overhang | %.4f | %.3f |' % (g_overhang(base['h_in'][0]), -base['flows']['q_sink']))
    w('')
    w('**The slots are not a way out for much heat.** Three 2 x 20 mm openings 2.3 mm deep give the fins %.4f W/K to the '
      'chamber in all: a 2 mm slot is too narrow for air to circulate in it (Rayleigh number about %.0f on its width), '
      'so it conducts like still air, and the stack-driven exchange between slots a few millimetres apart, through '
      '1.9 mm fin channels, moves %.1f mm^3/s. For comparison the whole case gives the chamber %.3f W/K. The '
      'heatsink still helps, because it spreads the junction\'s heat into the back cavity and the lid: without it the '
      'junction is %.1f C and the sensor %.1f C (sensitivity above).\n'
      % (sp0['g_amb'], 9.81 / 350 * 15 * SLOT_W ** 3 / (NU_AIR * ALPHA_AIR),
         sp0['q_stack'] / max(RHO_AIR * CP_AIR * max(base['t_sink'] - T_AMB, 0.1), 1e-9) * 1e9,
         base['h_out'] * A_OUT, tj_of(board, r_ns), ptemp(board, r_ns, SENSOR)))
    SUMMARY['sink'] = dict(g_amb=sp0['g_amb'], q_slot=base['q_slot'], q_patch=base['q_patch'], q_top=base['q_top'],
                           tj_ns=tj_of(board, r_ns), s_ns=ptemp(board, r_ns, SENSOR), s_pad=ptemp(board, r_pad, SENSOR))

    # ------------------------------------------------ parts list against the chamber
    w('## Every part\'s rating against the chamber\n')
    w('From `src/parts.py` and docs/parts-check-2026-10-31.md. Flagged against snap_night_ps (the rating case): a part '
      'rated below 85 C, over its rating, or within 10 K of it.\n')
    w('| part | rated | snapshot night, PS on, at @TA@ (C) | live night at @TA@ (C) | flag (snapshot) |\n|---|---|---|---|---|')
    tsn = {nm: t for nm, t, lim, src in part_temps(board, allres[REQ_NIGHT])}
    tln = {nm: t for nm, t, lim, src in part_temps(board, allres['night'])}
    mean = {'s': float(np.nanmean(allres[REQ_NIGHT]['T'])), 'l': float(np.nanmean(allres['night']['T']))}
    holder = {'s': ptemp(board, allres[REQ_NIGHT], SENSOR), 'l': ptemp(board, allres['night'], SENSOR)}

    def g(key, d, m):
        if key == 'MEAN':
            return mean[m]
        if key == 'HOLDER':
            return holder[m]
        if key == 'LENS':
            return (d['case wall (PC carbon fibre)'] + holder[m]) / 2
        if key == 'IND':
            return max(v for k, v in d.items() if 'inductor' in k)
        if key == 'X6S':
            return max(v for k, v in d.items() if k.startswith('X6S'))
        if key == 'X7S':
            return max(v for k, v in d.items() if k.startswith('X7S'))
        return d[key]
    rated = [('RV1106G3', 'Tj 125, ambient -20..85', TJ),
             ('RV1106G3 / EA3036C ambient (the air inside)', '-20..85 / -40..85', 'internal air (RV1106 / EA3036C ambient)'),
             ('SC4336H image sensor', '-30..85, best image to 60', SENSOR),
             ('ESP32-C6-MINI-1U-H4', '-40..105', C6),
             ('W25N02KVZEIR', '-40..85', 'W25N02KV flash (U5)'),
             ('USB4105-GF-A USB-C', '-40..85', 'USB-C receptacle USB4105 (J1)'),
             ('KT-0603G status LED', '-40..85', 'status LED LED1 (KT-0603G)'),
             ('TLV62569, EA3036C (junction)', 'TJ -40..125', 'TLV62569 0.9 V (U2) junction'),
             ('TLV75528', 'TJ -40..125', 'TLV75528 sensor LDO junction (U9)'),
             ('DRV8210P', 'TA -40..125', 'DRV8210P IR-cut driver (U7)'),
             ('AO3400A', 'TJ -55..150', 'MEAN'),
             ('crystals ECS 24 MHz, Abracon 32 kHz', '-40..125', 'crystals Y1 (24 MHz) / Y2 (32 kHz)'),
             ('Molex 53261 PicoBlade', '-40..105', 'PicoBlade IR-cut lead socket (J3)'),
             ('USBLC6-2SC6, SMF6.0CA', 'TJ to 125 / 150', 'USBLC6 / SMF6.0CA (U10 / D1)'),
             ('VSMY3850X01 IR LED (junction while lit)', 'Tj 100 (base part), -40..105 (X01)',
              'IR LEDs VSMY3850X01, junction while lit'),
             ('TEMT6000', '-40..100', 'TEMT6000 light sensor (Q2)'),
             ('DFE252012F inductors', '-40..125', 'IND'),
             ('BLM15PD121 bead', '-55..125', 'MEAN'),
             ('0402 / 1206 thick-film resistors', '-55..155 (power derates above 70)', 'X6S'),
             ('C0G / X7R capacitors', '-55..125', 'X6S'),
             ('X7S capacitors (1uF)', '-55..125', 'X7S'),
             ('X6S capacitors (2.2uF .. 22uF)', '-55..105', 'X6S'),
             ('3M 8810 tape (bought)', '100 long term (UNVERIFIED)', '3M 8810 tape on the RV1106'),
             ('CLA219 IR-cut holder (bought)', 'not published (plastic, NdFeB magnet)', 'HOLDER'),
             ('Towin CCL127028MPR lens (bought)', 'not published', 'LENS'),
             ('light rods (bought)', '-40..125 (Bivar, its PC pipes in general)', 'IR LEDs VSMY3850X01, ambient'),
             ('PC-CF case', 'HDT ~110 (ESTIMATED)', 'case wall (PC carbon fibre)')]
    for nm, rt, key in rated:
        ts, tl_ = g(key, tsn, 's'), g(key, tln, 'l')
        m = re.findall(r'(-?\d+)', rt.split('(')[0])
        hi = max(int(x) for x in m) if m else None
        if 'VSMY' in nm:
            hi = 100
        flag = []
        if hi is None:
            flag.append('UNKNOWN rating: ask the maker')
        elif hi < 85:
            flag.append('RATED BELOW 85 C')
        if hi is not None and ts > hi:
            flag.append('OVER its rating')
        elif hi is not None and hi - ts < 10:
            flag.append('under 10 K margin')
        w('| %s | %s | %.0f | %.0f | %s |' % (nm, rt, ts, tl_, '; '.join(flag)))
    w('')

    # ------------------------------------------------ model and assumptions
    w('## Model and assumptions\n')
    w('- Chamber %.0f C, still air (no credit for the chamber fan); bed radiation %.2f W on the front. The camera looks '
      'down about %.0f deg below horizontal (ASSUMED; it sets how far apart in height the slots are).'
      % (T_AMB, BED_RAD_W, TILT))
    w('- Case: Prusa\'s outside, outer hull %.1f cm^2 (measured from the STLs); new inside with 2 mm walls, %.1f cm^2 '
      'of inner wall, cavities %.1f mm (back) and %.1f mm (front) deep on average. PC carbon fibre at %.2f W/mK through '
      'the wall and %.2f along it: ESTIMATED from Stratasys\' FDM PC (0.28 W/mK, ASTM E1952) and unfilled PC (0.20); no '
      'PC-CF filament data sheet found gives a value. The wall itself is not the bottleneck (sensitivity: 0.20-0.50). '
      'Emissivity %.2f outside; natural convection 1.32 (dT/0.05 m)^0.25 plus linearised radiation.'
      % (A_OUT * 1e4, A_IN * 1e4, GAP_F * 1e3, GAP_B * 1e3, K_WALL, K_WALL_INPLANE, EPS_HOUSING))
    w('- Inside: radiation board to wall with effective emissivity %.2f; still-air conduction across the cavities with '
      'Catton\'s enclosure correlation (Nu %.2f / %.2f back / front in the rating case); board edge to the wall across %.1f mm '
      'of air; %.4f W/K at each M2 boss; the front face under the IR-cut holder\'s base at %.0f %% (the holder traps '
      'air). Board places: %s.'
      % (EPS_EFF, nu_enclosure(np.nanmean(base['T']) - base['t_w'], GAP_F),
         nu_enclosure(np.nanmean(base['T']) - base['t_w'], GAP_B), EDGE_GAP * 1e3, G_BOSS, HOLDER_FACTOR * 100,
         PLACE_SRC))
    w('- Copper coverage %s (docs/lessons.md: simulate heat on the routed board; routing raised temperatures 15 K on '
      'Ridge 3). Rerun with `tools/kd python3 sim/thermal.py` once layercam-pro.kicad_pcb is routed.' % COVER_SRC)
    w('- Heatsink: 20 x 20 x 15 mm aluminium, %.0f mm base, %d straight fins %.1f mm thick (ASSUMED: a typical stock '
      'part; the listing is to be confirmed), black anodised (emissivity %.2f); envelope %.0f W/m^2K and fin faces %.0f '
      'W/m^2K to the inside (LayerCam v1\'s estimates); on 3M 8810 (0.25 mm, 0.6 W/mK) over the 12.3 mm package with '
      '%.1f K/W of contacts; top 0.7 mm under a 1.6 mm lid. The exchange flow assumes the fins run across the slots '
      '(the favourable way); fins along the slots would block it, which the taped-slot row bounds.'
      % (SINK_BASE * 1e3, SINK_FINS, SINK_FIN_T * 1e3, EPS_SINK, H_FIN, H_FIN_INNER, INTERFACE_R))
    w('- RV1106: die to exposed pad %.0f K/W (ASSUMED) plus the computed via array; the datasheet theta-JB (%.1f K/W, '
      'JEDEC 2s2p) from the board at the package edge as the pessimistic reading; the higher is used.'
      % (R_DIE_EP, THETA_JB_SOC))
    w('- Above the board: TLV62569 psi-JB %.1f, TLV75528 %.1f K/W (TI); EA3036C %.0f, inductors %.0f, ESP32-C6 module '
      '%.0f, SC4336H die %.0f, IR LED junction %.0f K/W: ASSUMED.' % (PSI_JB_TLV, PSI_JB_LDO, R_JB_EA, R_JB_IND, R_C6,
                                                                      R_JB_SENSOR, R_LED_J))
    w('- Loads: sim/power.md (the RV1106\'s snapshot currents and the C6\'s duty cycles are ASSUMED; the C6\'s currents '
      'are Espressif\'s at 25 C). Model uncertainty about +-10 K. Measure the first board in a 70 C oven and rerun.')
    w('')
    return L, allres, board


def verdict(board, allres):
    V = []
    v = V.append
    t = {n: {nm: x for nm, x, lim, src in part_temps(board, allres[n])} for n in allres}
    at70 = SUMMARY['at70']
    t70 = {n: {nm: x for nm, x, lim, src in part_temps(board, at70[n])} for n in at70}
    lim = SUMMARY['lim']
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    req = min((lim[n]['all'] if lim[n]['all'] is not None else -99) for n in REQ)
    first_n = min(REQ, key=lambda n: lim[n]['all'] if lim[n]['all'] is not None else -99)
    worst = sorted(((l - x, nm, x, l) for nm, x, l, src in part_temps(board, allres[REQ_NIGHT])))[0]
    v('## Verdict\n')
    v('**Rated for a %.0f C chamber: %s** (%d FAIL, %d WARN). The owner\'s decision: LayerCam Pro is rated for a '
      '%.0f C chamber in snapshot and timelapse mode, day and night, with the ESP32-C6\'s Wi-Fi power save on (its '
      'firmware sets it), the stock heatsink and no fan. Prusa\'s firmware caps the chamber at %.0f C on the CORE One '
      'and %.0f C on the CORE One L, so the rating sits %.0f K above the highest chamber a stock printer allows.\n'
      % (T_AMB, 'PASS' if not fails else 'FAIL', len(fails), len(warns), T_AMB, PRUSA_CAP[0], PRUSA_CAP[1],
         T_AMB - PRUSA_CAP[1]))
    v('With power save on, every part stays inside its rating up to a **%s** chamber by night and **%s** by day: '
      '%.1f K of margin over the rating at night, inside the model\'s +-10 K uncertainty, so the first board must be '
      'measured in a %.0f C oven before this is called a pass. The part closest to its limit at @TA@ is the **%s**: '
      '%.1f C against %d C (%+.1f K).\n'
      % (fmt_amb(lim['snap_night_ps']['all']), fmt_amb(lim['snap_day_ps']['all']), req - T_AMB, T_AMB, worst[1],
         worst[2], worst[3], worst[0]))
    cols = ('snap_day_ps', 'snap_night_ps', 'snap_day', 'snap_night', 'day', 'night')
    rows_ = (('RV1106 junction (125 C)', TJ), ('image sensor (85 C; best image 60 C)', SENSOR),
             ('ESP32-C6 (105 C)', C6), ('flash (85 C)', 'W25N02KV flash (U5)'),
             ('USB-C (85 C)', 'USB-C receptacle USB4105 (J1)'), ('status LED (85 C)', 'status LED LED1 (KT-0603G)'),
             ('air inside (85 C ambient parts)', 'internal air (RV1106 / EA3036C ambient)'),
             ('IR LED junction while lit (100 C)', 'IR LEDs VSMY3850X01, junction while lit'), ('board max', None),
             ('heatsink', 'SINK'))
    for tag, res_, tt in (('@TA@ (the rating; power save on is the requirement)', allres, t),
                          ('%.0f C (information only)' % T_INFO, at70, t70)):
        v('At %s:\n' % tag)
        v('| | %s |\n|---|%s' % (' | '.join(SHORT[n] for n in cols), '---|' * len(cols)))
        for lab, k in rows_:
            vals = []
            for n in cols:
                r = res_[n]
                vals.append(float(np.nanmax(r['T'])) if k is None else (r['t_sink'] if k == 'SINK' else tt[n][k]))
            v('| %s | %s |' % (lab, ' | '.join('%.1f C' % x for x in vals)))
        v('| heat in the case | %s |' % ' | '.join('%.2f W' % res_[n]['p_total'] for n in cols))
        v('')
    v('**Highest chamber temperature with every part inside its rating** (bisection):\n')
    v('| mode | every part in rating up to | first part there | image sensor 85 C at | image sensor 60 C at |')
    v('|---|---|---|---|---|')
    for n in ('snap_day_ps', 'snap_night_ps', 'snap_day', 'snap_night', 'day', 'night', 'worst'):
        v('| %s%s | **%s** | %s | %s | %s |' % (SHORT[n], ' (rating)' if n in REQ else '', fmt_amb(lim[n]['all']),
                                             lim[n]['first'] or '-', fmt_amb(lim[n]['s85']), fmt_amb(lim[n]['s60'])))
    v('')
    s = SUMMARY['sink']
    bn = allres[REQ_NIGHT]['T']
    k85 = (SENSOR, 'W25N02KV flash (U5)', 'USB-C receptacle USB4105 (J1)', 'status LED LED1 (KT-0603G)')
    v('- **Image sensor** (the rating case, night): %.1f C at @TA@ against 85 C (%+.1f K); its 85 C is reached at a %s '
      'chamber. Its best image ends at 60 C, which it passes at a %s chamber: above that the picture degrades (noise, '
      'dark current) but the sensor works. At %.0f C it would be %.1f C.'
      % (t[REQ_NIGHT][SENSOR], 85 - t[REQ_NIGHT][SENSOR], fmt_amb(lim[REQ_NIGHT]['s85']), fmt_amb(lim[REQ_NIGHT]['s60']),
         T_INFO, t70[REQ_NIGHT][SENSOR]))
    v('- **The board is nearly isothermal** (%.1f-%.1f C in night snapshots at @TA@): six copper layers spread the heat '
      'faster than the still air takes it off, so the four parts rated 85 C (USB-C, flash, image sensor, status LED) '
      'are within %.1f K of each other and their order is inside the model\'s uncertainty: the margin is the board\'s '
      'as a whole.' % (np.nanmin(bn), np.nanmax(bn), max(t[REQ_NIGHT][k] for k in k85) - min(t[REQ_NIGHT][k] for k in k85)))
    v('- **Wi-Fi power save is needed for the rating**: off (the C6 as first built), the limit drops to %s by night and %s '
      'by day, %.1f K lower; the sensor runs %.1f K and the junction %.1f K warmer. The C6 firmware must set it, and the '
      'first board should confirm the C6\'s current with it on (power.md: 47 mA against 98 mA, ASSUMED duty cycles).'
      % (fmt_amb(lim['snap_night']['all']), fmt_amb(lim['snap_day']['all']),
         (lim[REQ_NIGHT]['all'] or 0) - (lim['snap_night']['all'] or 0), t['snap_night'][SENSOR] - t[REQ_NIGHT][SENSOR],
         t['snap_night'][TJ] - t[REQ_NIGHT][TJ]))
    v('- **70 C is not met** (information): with power save on, %s by day and %s by night; off, %s and %s. The parts '
      'that stop it are the 85 C ones above.' % (fmt_amb(lim['snap_day_ps']['all']), fmt_amb(lim['snap_night_ps']['all']),
                                                 fmt_amb(lim['snap_day']['all']), fmt_amb(lim['snap_night']['all'])))
    pl = SUMMARY.get('pad_lim', (None, None))
    v('- **The vent slots carry little**: %.3f W of the heatsink\'s %.2f W leaves through its three slots and %.3f W '
      'through the lid over it; the rest goes into the case\'s inside air and the board. Without the heatsink the '
      'sensor would be %.1f C, with a 1 mm gap pad from the fin tops to the lid %.1f C (chamber limit then %s by night, '
      'power save on).' % (s['q_slot'], s['q_top'], s['q_patch'], s['s_ns'], s['s_pad'], fmt_amb(pl[1])))
    v('- Live view: every part in rating to %s by day and %s by night; it stays a firmware-gated mode (TSADC below '
      '%.0f C; snapshot mode stretches to 30 s above %.0f C).'
      % (fmt_amb(lim['day']['all']), fmt_amb(lim['night']['all']), *SUMMARY['gov']))
    v('- Model uncertainty about +-10 K (optimistic bracket: RV1106 %.1f C, sensor %.1f C in the rating case); the '
      'placement is layout_main.py\'s, the copper coverage LayerCam v1\'s, the snapshot currents ASSUMED. Rerun on the '
      'routed board and measure the first board in a %.0f C oven.' % (SUMMARY['opt'] + (T_AMB,)))
    v('')
    return V


if __name__ == '__main__':
    L, allres, board = main()
    i = [k for k, x in enumerate(L) if x.startswith('## Snapshot, day')][0]
    L[i:i] = verdict(board, allres)
    w = L.append
    w('## Checks\n')
    for s_, what in checks:
        w('- %s %s' % (s_, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    L = [x.replace('@TA@', '%.0f C' % T_AMB) for x in L]
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    for f in os.listdir(HERE):
        if f.startswith('thermal_') and f.endswith('.png') and f[8:-4] not in allres:
            os.remove(os.path.join(HERE, f))
    sys.exit(1 if fails else 0)
