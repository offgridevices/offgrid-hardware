# -*- coding: utf-8 -*-
"""LayerCam v1: temperatures inside Prusa's camera housing in a 65 C chamber.

    tools/kd python3 sim/thermal.py     writes sim/thermal.md and thermal_<case>.png, exits 1 on a FAIL

The model, from the inside out:

  main board   a 2D finite-difference plate on a 0.5 mm grid over the real
               outline (src/geometry.py: straight sides, the arc, the tab,
               the lens window cut out).  In-plane conductance from the
               JLC06161H-3313 copper (pcb.STACKUP6) with a coverage factor
               per layer; each part's heat (sim/power_budget.py) put on its
               footprint at its place in src/layout_main.py.  Both faces
               lose heat to the housing's inner wall by radiation and by
               conduction across the still air gaps (src/geometry.py's
               free heights; the gaps are too thin for convection cells).
  camera       the SC3336 module 1 mm behind the board: most of its heat
  module       crosses that gap into the board, the rest goes to the lid.
  LED ring     one lump: its front face against the housing's front wall
               (a contact through the wall to the outside), its back face
               to the inside.
  housing      Prusa's printed case (Printables 1343977), outer hull
               125.6 cm^2, 2 mm walls; natural convection and radiation to
               a 65 C chamber, no airflow credited; the six 20 x 2 mm lid
               slots give a small stack-effect air exchange.
  junctions    each part's own resistance from the board under it (datasheet
               theta-JB / psi-JB where given, else estimated and marked).

Housing figures measured from Prusa's STLs (buddy-camera-bottom-r2, -top-r1,
-lid-r1) on 26 Oct 2026: convex hull area 125.6 cm^2 and volume 111 cm^3,
plastic 46.7 cm^3, lid slots 6 x 20 x 2 mm spanning 22 mm.
"""
import math, os, re, sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(V1, 'src'))
import geometry as G
import parts
import power_budget as power

OUT = os.path.join(HERE, 'thermal.md')
SIGMA = 5.670e-8

# ---------------------------------------------------------------- environment and housing
T_AMB = 65.0                      # CORE One chamber, the requirement
A_OUT = 125.6e-4                  # m^2, housing outer hull (STL)
WALL_T, K_PLASTIC = 0.002, 0.20   # PETG / ASA wall, W/mK
EPS_HOUSING = 0.90                # printed plastic in the infrared (any colour)
BED_RAD_W = 0.10                  # bed at 100-110 C seen by the camera's front, ~0.14 view factor (estimate)
VENT_A, VENT_H, VENT_CD = 6 * 20e-6 * 2, 0.011, 0.6     # slot area (m^2), height between the halves, discharge coeff.

# ---------------------------------------------------------------- inside the housing
EPS_EFF = 0.75                    # board (solder mask 0.9) to wall (0.9), with view-factor losses (estimate)
NU_GAP = 1.1                      # air gaps of 8-10 mm: Ra ~ 1e3, conduction regime
GAP_F, GAP_B = 0.0085, 0.0098     # F (back face, 7.7-17.5 mm free) and B (front face, 9.8 mm) gaps, m
K_AIR = 0.0300                    # W/mK at ~ 85 C

# ---------------------------------------------------------------- the main board
K_CU, K_FR4 = 385.0, 0.8
# copper coverage per layer (ASSUMED for the routed board: outer layers signals + ground fill, inner
# planes perforated by vias, In2 signals + fill)
COVER = {'F.Cu': 0.55, 'In1.Cu': 0.90, 'In2.Cu': 0.50, 'In3.Cu': 0.85, 'In4.Cu': 0.90, 'B.Cu': 0.55}
# PCBWay's regular 6-layer 1.6 mm build (sim/impedance.md): 1 oz outer finished, 1 oz (0.035 mm) inner
CU_T = {'F.Cu': 0.035, 'B.Cu': 0.035, 'In1.Cu': 0.035, 'In2.Cu': 0.035, 'In3.Cu': 0.035, 'In4.Cu': 0.035}
DX = 0.5e-3                       # grid, m

# footprints the heat is spread over (mm, centred on the part's place in layout_main.py)
FOOT = {'U1': (9.0, 9.0), 'U2': (3.0, 1.7), 'L1': (2.5, 2.0), 'U3': (3.0, 3.0), 'L2': (2.5, 2.0),
        'L3': (2.5, 2.0), 'L4': (2.5, 2.0), 'U4': (3.0, 1.7), 'L5': (2.5, 2.0), 'U6': (12.0, 12.0),
        'U5': (8.0, 6.0), 'U7': (2.0, 2.0), 'Q1': (2.9, 1.3), 'J1': (4.0, 8.0)}
DESIGN_PATH = 'cnc'               # the heat path the design uses (the case sections below); None = bare board
HEATPATH = None                   # a heat path from the RV1106's top (mechanical/heat-plate/heat_paths.json), None = none
HEATPATHS_JSON = os.path.join(V1, 'mechanical', 'heat-plate', 'heat_paths.json')


def heat_paths():
    """The three heat paths designed in mechanical/heat-plate/plate.py: junction-to-part resistance r_top
    (theta-JC top + pad / tape + metal), part to the air inside g_air, part to the chamber g_amb (through
    the lid plastic and the slots), and the outer lid area that path uses."""
    import json
    return json.load(open(HEATPATHS_JSON))['paths']
H_FORCED = 0.0                    # extra outside convection (chamber air moving), W/m^2K
SENSOR_RISE = 3.0                 # the sensor die over its module board (estimate)
EDGE_GAP = 0.6e-3                 # board edge to the housing pocket wall (0.4 mm clearance and more, geometry.py)

# ---------------------------------------------------------------- the parts' own resistances (K/W)
# RV1106 (datasheet Rev 2.2 table 4-1, JEDEC 2s2p): thetaJA 27.3, thetaJB 12.5, thetaJC 8.4.  The board model
# already holds the spreading, so the junction sits above the board under the exposed pad by the die-to-pad
# resistance (ASSUMED 3 K/W for a 12 x 12 QFN with a 7 x 7 pad) plus the 25 filled vias to the planes (below).
# The pessimistic reading, thetaJB from the board at the package edge, is reported too and the higher is used.
R_DIE_EP = 3.0
THETA_JB_SOC = 12.5
N_EP_VIAS, VIA_DRILL, VIA_PLATE = 25, 0.20e-3, 18e-6     # layout_main.zones(): 5 x 5, pcb.VIA 0.45 / 0.2
PSI_JB_TLV = 40.6                 # TLV62569 DBV (SLVSDG1C 6.4)
R_JB_EA = 15.0                    # EA3036C: thetaJC 7.5 + pad to board (ASSUMED)
R_JB_IND = 60.0                   # 2520 inductor on its pads (ASSUMED)
R_AP6256 = 8.0                    # module shield / die above the board (ASSUMED: 12 x 12 LGA, 44 pads)
R_LED_J = 40.0 + 80.0             # LED junction to solder point + pad to ring on thin tracks (ASSUMED)
H_RING_CONTACT = 150.0            # ring front face against the printed wall (0.2 mm effective air), W/m^2K

checks = []
SUMMARY = {'lim': {}, 'mit': {}}


def check(ok, what, warn=False):
    checks.append(('PASS' if ok else ('WARN' if warn else 'FAIL'), what))


# ---------------------------------------------------------------- geometry
def board_polygon():
    from shapely.geometry import Polygon, box
    w2, top = G.MAIN_HALF_W, G.MAIN_TOP_Y
    cy, r = G.MAIN_ARC_C[1], G.MAIN_ARC_R
    yj = cy - math.sqrt(r * r - w2 * w2)
    a0, a1 = math.atan2(yj - cy, w2), math.atan2(yj - cy, -w2)
    if a1 > a0:
        a1 -= 2 * math.pi
    arc = [(r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(a0, a1, 64)]
    ptsY = [(-w2, top)] + list(G.MAIN_TAB) + [(w2, top)] + arc
    poly = Polygon([(x, -y) for x, y in ptsY])
    ww, wh = G.WINDOW
    return poly.difference(box(-ww / 2, -wh / 2, ww / 2, wh / 2))


def placements():
    """ref -> (x, y, side) from layout_main.FIXED, read as text (it imports pcbnew)."""
    s = open(os.path.join(V1, 'src', 'layout_main.py')).read()
    out = {}
    for m in re.finditer(r"'([A-Z]+\d+)': \(([-\d.]+), ([-\d.]+), (\d+), ([FB])\)", s):
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)), m.group(5))
    return out


def sheet_conductance(scale=1.0):
    cu = sum(CU_T[k] * 1e-3 * COVER[k] for k in CU_T) * scale
    return K_CU * cu + K_FR4 * (1.6e-3 - sum(CU_T.values()) * 1e-3)


def ep_via_resistance():
    a = math.pi * ((VIA_DRILL / 2 + VIA_PLATE) ** 2 - (VIA_DRILL / 2) ** 2)
    r_one = 0.155e-3 / (K_CU * a)          # F.Cu pad to In1, through PCBWay's 0.1195 mm 2116 + copper
    r_vias = r_one / N_EP_VIAS
    r_fr4 = 0.1195e-3 / (0.3 * 49e-6)      # the prepreg under the 7 x 7 pad, in parallel
    return 1 / (1 / r_vias + 1 / r_fr4)


# ---------------------------------------------------------------- the board solver
class Board:
    def __init__(self, cover_scale=1.0):
        from shapely import contains_xy
        poly = board_polygon()
        x0, y0, x1, y1 = poly.bounds
        xs = np.arange(x0 + DX * 500, x1, DX * 1e3)
        ys = np.arange(y0 + DX * 500, y1, DX * 1e3)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        self.inside = contains_xy(poly, X, Y)
        self.X, self.Y, self.xs, self.ys = X, Y, xs, ys
        self.n = int(self.inside.sum())
        self.idx = -np.ones(X.shape, int)
        self.idx[self.inside] = np.arange(self.n)
        self.area = poly.area * 1e-6
        ks = sheet_conductance(cover_scale)       # W/K between neighbours on a square grid
        rows, cols, vals = [], [], []
        nx, ny = X.shape
        for di, dj in ((1, 0), (0, 1)):
            a = self.idx[:nx - di, :ny - dj]
            b = self.idx[di:, dj:]
            m = (a >= 0) & (b >= 0)
            a, b = a[m], b[m]
            rows += [a, b, a, b]; cols += [a, b, b, a]
            vals += [np.full(a.size, ks), np.full(a.size, ks), np.full(a.size, -ks), np.full(a.size, -ks)]
        self.K = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                               shape=(self.n, self.n))
        self.place = placements()
        # outer-edge nodes (a neighbour outside the board, not at the lens window): they face the
        # housing's pocket wall across EDGE_GAP of air
        out = ~self.inside
        nb = np.zeros_like(self.inside)
        nb[1:, :] |= out[:-1, :]; nb[:-1, :] |= out[1:, :]; nb[:, 1:] |= out[:, :-1]; nb[:, :-1] |= out[:, 1:]
        nb[0, :] = nb[-1, :] = True
        win = (np.abs(X) < G.WINDOW[0] / 2 + 1.0) & (np.abs(Y) < G.WINDOW[1] / 2 + 1.0)
        self.edge = (self.inside & nb & ~win)[self.inside]
        self.under_module = self.mask(0, 0, G.MODULE_W, G.MODULE_H)[self.inside]

    def mask(self, x, y, w, h):
        return self.inside & (np.abs(self.X - x) <= w / 2) & (np.abs(self.Y - y) <= h / 2)

    def sources(self, heat):
        q = np.zeros(self.X.shape)
        for ref, p in heat.items():
            if ref in FOOT and ref in self.place:
                x, y, _ = self.place[ref]
                m = self.mask(x, y, *FOOT[ref])
                if m.sum() == 0:
                    raise ValueError('no board under ' + ref)
                share = 0.5 if ref == 'J1' else 1.0
                q[m] += p * share / m.sum()
        return q[self.inside]

    def solve(self, q, hF, hB, t_wall, t_mod, g_mod_total):
        """Board temperatures: each node loses heat to the wall from both faces (the F face under the
        camera module goes to the module instead), the outer edge to the pocket wall."""
        a = DX ** 2
        g_wall = np.full(self.n, (hF + hB) * a)
        g_wall[self.under_module] = hB * a
        g_wall[self.edge] += K_AIR * DX * 1.6e-3 / EDGE_GAP
        g_m = np.zeros(self.n)
        g_m[self.under_module] = g_mod_total / self.under_module.sum()
        A = self.K + sp.diags(g_wall + g_m)
        T = spla.spsolve(A.tocsc(), q + g_wall * t_wall + g_m * t_mod)
        self.last = dict(q_wall=float((g_wall * (T - t_wall)).sum()), q_mod=float((g_m * (T - t_mod)).sum()),
                         q_edge=float((np.where(self.edge, K_AIR * DX * 1.6e-3 / EDGE_GAP, 0) * (T - t_wall)).sum()))
        full = np.full(self.X.shape, np.nan)
        full[self.inside] = T
        return full

    def at(self, T, ref, w=None, h=None, stat='mean'):
        x, y, _ = self.place[ref]
        fw, fh = FOOT.get(ref, (2.0, 2.0))
        m = self.mask(x, y, w or fw, h or fh)
        return float(np.nanmax(T[m]) if stat == 'max' else np.nanmean(T[m]))


# ---------------------------------------------------------------- the whole housing
def h_inside(t_b, t_w):
    tm = (t_b + t_w) / 2 + 273.15
    h_rad = 4 * SIGMA * EPS_EFF * tm ** 3
    return h_rad + NU_GAP * K_AIR / GAP_F, h_rad + NU_GAP * K_AIR / GAP_B


def h_outside(t_w, t_amb):
    dt = max(t_w - t_amb, 0.5)
    h_conv = 1.32 * (dt / 0.05) ** 0.25 + H_FORCED   # laminar natural convection, 50 mm body (still chamber air)
    tm = (t_w + t_amb) / 2 + 273.15
    return h_conv + 4 * SIGMA * EPS_HOUSING * tm ** 3


def vent_flow_w(t_air, t_amb):
    dt = max(t_air - t_amb, 0.0)
    a1 = a2 = VENT_A / 2
    a_eff = 1 / math.sqrt(1 / a1 ** 2 + 1 / a2 ** 2)
    v = VENT_CD * a_eff * math.sqrt(2 * 9.81 * VENT_H * dt / (t_amb + 273.15))
    return 1.0 * 1007 * v * dt                     # rho ~ 1.0 kg/m^3 at 75 C


def ring_paths(t_amb, h_in):
    r_out, r_in = G.RING_OUT_R * 1e-3, G.RING_IN_R * 1e-3
    a = math.pi * (r_out ** 2 - r_in ** 2) * 0.85        # less the LED and window openings
    spread = math.pi * ((r_out + 0.005) ** 2 - max(r_in - 0.005, 0) ** 2)    # wall area it warms outside
    r_direct = 1 / (H_RING_CONTACT * a) + WALL_T / (K_PLASTIC * a) + 1 / (h_outside(t_amb + 20, t_amb) * spread)
    r_inside = 1 / (h_in * a)
    return r_direct, r_inside, a, spread


def run_case(board, heat, t_amb=T_AMB, vents=True, ring_contact=True, led_on=None):
    heat_in = dict(heat)
    heat = dict(heat)
    p_total = sum(heat.values())
    p_cam = heat.pop('camera module', 0.0)
    p_ring = heat.pop('ring resistors', 0.0) + heat.pop('ring LEDs', 0.0)
    p_cable = heat.pop('cable, connectors', 0.0)
    heat['J1'] = p_cable                            # half on the main board's connector, half on the USB board
    p_soc = heat.get('U1', 0.0)
    hp = HEATPATH
    q_top = 0.0
    t_s = t_amb + 20.0
    q = board.sources(heat)
    q_board = q.sum()
    r_jb = R_DIE_EP + ep_via_resistance()
    a_mod = G.MODULE_W * G.MODULE_H * 1e-6
    g_gap = (K_AIR / (G.MODULE_SHIM * 1e-3) + 8.0) * a_mod      # module to board: 1 mm air + radiation
    t_w = t_amb + 10.0
    t_b = t_w + 20.0
    t_m = t_b
    board.t_amb = t_amb
    for it in range(400):
        hF, hB = h_inside(t_b, t_w)
        T = board.solve(q, hF, hB, t_w, t_m, g_gap)
        t_b_new = float(np.nanmean(T))
        # camera module: its own heat, the gap to the board, its back face to the lid
        t_under = float(np.nanmean(T[board.mask(0, 0, G.MODULE_W, G.MODULE_H)]))
        g_back = hF * a_mod
        t_m_new = (p_cam + g_gap * t_under + g_back * t_w) / (g_gap + g_back)
        # ring
        r_d, r_i, a_ring, spread = ring_paths(t_amb, (hF + hB) / 2)
        if not ring_contact:
            r_d = 1e9
        t_ring = (p_ring + t_amb / r_d + t_w / r_i) / (1 / r_d + 1 / r_i)
        q_ring_out = (t_ring - t_amb) / r_d
        t_air = (t_b_new + t_w) / 2
        q_vent = vent_flow_w(t_air, t_amb) if vents else 0.0
        q_sink_amb = 0.0
        if hp:
            # the junction splits its heat between the board (exposed pad) and the part on its top
            t_ep = float(np.nanmean(T[board.mask(*board.place['U1'][:2], 7.0, 7.0)]))
            # junction and part solved together (2 x 2): P = (Tj-Tep)/rjb + (Tj-Ts)/rt,
            # (Tj-Ts)/rt = g_air (Ts-Tair) + g_amb (Ts-Tamb)
            g_air, g_amb, rt = hp['g_air'], hp['g_amb'], hp['r_top']
            M = np.array([[1 / r_jb + 1 / rt, -1 / rt], [-1 / rt, 1 / rt + g_air + g_amb]])
            tj, t_s = np.linalg.solve(M, [p_soc + t_ep / r_jb, g_air * t_air + g_amb * t_amb])
            q_top_new = (tj - t_s) / rt
            q_top = 0.5 * q_top + 0.5 * q_top_new
            q_sink_amb = g_amb * (t_s - t_amb)
            h2 = dict(heat)
            h2['U1'] = p_soc - q_top
            q = board.sources(h2)
        # everything else reaches the wall and leaves through it
        q_into_wall = p_total - q_ring_out - q_vent - q_sink_amb
        a_rest = A_OUT - (spread if ring_contact else 0.0) - (hp['a_out_used'] if hp else 0.0)
        h_o = h_outside(t_w, t_amb)
        r_wall = WALL_T / (K_PLASTIC * A_OUT * 0.85) + 1 / (h_o * a_rest)
        t_w_new = t_amb + (q_into_wall + BED_RAD_W) * r_wall
        if abs(t_w_new - t_w) < 2e-3 and abs(t_b_new - t_b) < 2e-3 and abs(t_m_new - t_m) < 2e-3 and \
                (not hp or abs(q_top - q_top_new) < 1e-4):
            break
        t_w = 0.5 * t_w + 0.5 * t_w_new
        t_m = 0.5 * t_m + 0.5 * t_m_new
        t_b = t_b_new
    t_cam = t_m + SENSOR_RISE
    return dict(T=T, t_w=t_w, t_b=t_b, t_air=(t_b + t_w) / 2, t_ring=t_ring, q_vent=q_vent, q_ring_out=q_ring_out,
                q_board=q_board, p_ring=p_ring, p_cam=p_cam, t_cam=t_cam, t_mod=t_m, h_in=(hF, hB), h_out=h_o,
                heat=heat, heat_in=heat_in, flows=dict(board.last), p_total=p_total, t_amb=t_amb, led_on=led_on,
                q_top=q_top, t_sink=t_s if hp else None, q_sink_amb=q_sink_amb)


# ---------------------------------------------------------------- per-part temperatures
def part_temps(board, res, case):
    T = res['T']
    heat = res['heat']
    out = []        # (name, temperature, limit, limit source)
    p_soc = heat['U1'] - res.get('q_top', 0.0)      # what goes into the board (the rest leaves by the top)
    r_via = ep_via_resistance()
    t_ep = board.at(T, 'U1', 7.0, 7.0)
    # board at the package edge: a 1 mm band just outside the 12.3 mm body, on the centreline sides
    x, y, _ = board.place['U1']
    band = board.mask(x, y, 14.3, 14.3) & ~board.mask(x, y, 12.3, 12.3)
    t_edge = float(np.nanmean(T[band]))
    tj_a = t_ep + p_soc * (R_DIE_EP + r_via)
    tj_b = t_edge + p_soc * THETA_JB_SOC
    tj = max(tj_a, tj_b)
    res['soc'] = dict(t_ep=t_ep, t_edge=t_edge, tj_a=tj_a, tj_b=tj_b, r_via=r_via, p=p_soc)
    out.append(('RV1106 junction (U1)', tj, 125, 'Tj max (datasheet 4.1)'))
    out.append(('RV1106 surroundings (internal air)', res['t_air'], 85, 'ambient operating max (T3-2)'))
    for ref, nm in (('U2', 'TLV62569 0.9 V (U2)'), ('U4', 'TLV62569 Wi-Fi (U4)')):
        out.append((nm + ' junction', board.at(T, ref, stat='max') + heat.get(ref, 0) * PSI_JB_TLV, 125,
                    'TJ max (SLVSDG1C 6.3)'))
    out.append(('EA3036C junction (U3)', board.at(T, 'U3', stat='max') + heat.get('U3', 0) * R_JB_EA, 125,
                'TJ range (datasheet)'))
    for ref in ('L1', 'L2', 'L3', 'L4', 'L5'):
        out.append(('inductor %s (FPA252012D)' % ref, board.at(T, ref, stat='max') + heat.get(ref, 0) * R_JB_IND, 125,
                    'typical for molded 2520 power inductors (UNVERIFIED: no datasheet read)'))
    out.append(('AP6256 module (U6)', board.at(T, 'U6', stat='max') + heat.get('U6', 0) * R_AP6256, 85,
                'operating max; full RF only to 75 C'))
    out.append(('SC3336 sensor (camera module)', res['t_cam'], 85, 'operating max; best image to 60 C (SmartSens)'))
    out.append(('W25N02KV flash (U5)', board.at(T, 'U5', stat='max') + heat.get('U5', 0) * 20, 85, '-40..85 C (Winbond)'))
    out.append(('DRV8837 (U7)', board.at(T, 'U7', stat='max'), 85, 'ambient -40..85 C (TI)'))
    big = cap_class(('C1U', 'C4U7', 'C10U', 'C22U'))
    for (cls, lim), refs in big.items():
        nm = '%s capacitors (%s)' % (cls, ', '.join(parts.PARTS[c]['value'] for c in refs))
        src = '%s: -55..%d C (%s)' % (cls, lim, parts.PARTS[refs[0]]['maker'])
        out.append((nm + ' under the SoC (B face)', board.at(T, 'U1', 12.0, 12.0, stat='max'), lim, src))
        out.append((nm + ' at the bucks', max(board.at(T, r, 5, 5, stat='max') for r in ('U2', 'U3', 'U4')), lim, src))
    out.append(('24 MHz crystal Y1', board.at(T, 'Y1', 3, 3, stat='max'), 85, '-40..85 C (YXC)'))
    out.append(('crystals Y2 / Y3, oscillator Y4', max(board.at(T, r, 3, 3, stat='max') for r in ('Y2', 'Y3', 'Y4')), 85,
                '-40..85 C'))
    out.append(('status LED LED1', board.at(T, 'LED1', 2, 2, stat='max'), 85, '-40..85 C (KENTO)'))
    out.append(('camera FFC connector J2 (XF2M)', board.at(T, 'J2', 12, 4, stat='max'), 85, '-30..85 C incl. rise (Omron)'))
    out.append(('SH connectors J1 / J4 (JST)', max(board.at(T, r, 4, 8, stat='max') for r in ('J1', 'J4')), 85,
                '-25..85 C incl. rise (JST)'))
    out.append(('U.FL J5', board.at(T, 'J5', 3, 3, stat='max'), 90, '-40..90 C (Hirose)'))
    out.append(('PicoBlade J3', board.at(T, 'J3', 4, 4, stat='max'), 105, '-40..105 C (Molex)'))
    out.append(('USB-C receptacle (USB board)', res['t_air'] + 2.0, 80, '-30..80 C (catalogue)'))
    out.append(('IR LEDs (ring), junction', res['t_ring'] + _led_heat_each(res) * R_LED_J, 115, 'Tj max (JNJ)'))
    out.append(('IR LEDs (ring), case', res['t_ring'] + _led_heat_each(res) * 40, 100, 'operating -40..100 C (JNJ)'))
    out.append(('TEMT6000 light sensor (ring)', res['t_ring'], 100, '-40..100 C (Vishay)'))
    out.append(('housing wall (PETG/ASA print)', res['t_w'], 80, 'PETG softens ~ 80 C (Tg); ASA/PC higher'))
    return out


TEMP_CLASS = {'X5R': 85, 'X6S': 105, 'X7S': 125, 'X7R': 125, 'C0G': 125}


def cap_class(codes):
    """{(dielectric, limit C): [part codes]} from parts.py's descriptions."""
    out = {}
    for c in codes:
        d = re.search(r'\b(X\d[RSPT]|C0G)\b', parts.PARTS[c]['desc']).group(1)
        out.setdefault((d, TEMP_CLASS[d]), []).append(c)
    return out


def _led_heat_each(res):
    """Each LED's heat while lit: the junction follows the instantaneous power (its time constant is far
    shorter than a 2 s flash), the ring the average."""
    if res.get('led_on'):
        return res['led_on'][0]
    return res['heat_in'].get('ring LEDs', 0.0) / 6


def resistor_check(res, case):
    """String resistor 1206 (UNI-ROYAL 1206W4F): 0.25 W at 70 C, linear to 0 at 155 C; checked at its power
    while lit (a 1206 heats in about a second, so a 2 s flash is near steady state)."""
    h = res['led_on'][1] if res.get('led_on') else res['heat_in'].get('ring resistors', 0.0) / 3
    t = res['t_ring']
    rating = 0.25 * min(1.0, max(0.0, (155 - t) / (155 - 70)))
    return h, t, rating


# ---------------------------------------------------------------- plotting
def plot(board, res, name, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.2, 6.4), dpi=110)
    T = res['T']
    ext = [board.xs[0], board.xs[-1], board.ys[-1], board.ys[0]]
    im = ax.imshow(T.T, extent=ext, origin='upper', cmap='inferno')
    for ref in ('U1', 'U2', 'U3', 'U4', 'U6', 'U5', 'J1', 'J2'):
        x, y, side = board.place[ref]
        ax.text(x, y, ref, color='cyan', ha='center', va='center', fontsize=7)
    ax.set_title(title, fontsize=8)
    ax.set_xlabel('x (mm), seen from the back (F)', fontsize=7)
    ax.tick_params(labelsize=6)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label('board temperature (C)', fontsize=7)
    cb.ax.tick_params(labelsize=6)
    fig.tight_layout()
    path = os.path.join(HERE, 'thermal_%s.png' % name)
    fig.savefig(path)
    plt.close(fig)
    return os.path.basename(path)


# ---------------------------------------------------------------- write-up
def ambient_limit(board, heat, limit_fn, lo=-20.0, hi=85.0, led_on=None):
    """The highest chamber temperature at which limit_fn holds (bisection), or None if it never does."""
    if not limit_fn(board, run_case(board, heat, t_amb=lo, led_on=led_on)):
        return None
    for _ in range(10):
        mid = (lo + hi) / 2
        ok = limit_fn(board, run_case(board, heat, t_amb=mid, led_on=led_on))
        lo, hi = (mid, hi) if ok else (lo, mid)
    return lo


def first_over(board, heat, t_amb, skip=(), led_on=None):
    res = run_case(board, heat, t_amb=t_amb, led_on=led_on)
    over = sorted(((t - lim, nm) for nm, t, lim, src in part_temps(board, res, None)
                   if not any(k in nm for k in skip)), reverse=True)
    return over[0][1]


def within(board, res, keys=None, skip=()):
    for name, t, lim, src in part_temps(board, res, None):
        if any(k in name for k in skip):
            continue
        if keys and not any(k in name for k in keys):
            continue
        if t > lim:
            return False
    return True


CASES = [('snap_day', 'Snapshot, day (requirement)', 'req'),
         ('snap_night', 'Snapshot, night, IR LEDs lit 2 s of every 10 s (requirement)', 'req'),
         ('day', 'Live view, day: streaming (reported, not required)', 'live'),
         ('night', 'Live view, night: streaming with the IR LEDs on (reported, not required)', 'live'),
         ('worst', 'Stress bound: SoC flat out, Wi-Fi transmitting, LEDs at the high corner (reported)', 'stress')]


def case_run(board, name, **kw):
    return run_case(board, power.heat(name), led_on=power.led_on(name) if power.heat(name).get('ring LEDs') else None,
                    **kw)


def tj_of(board, res):
    part_temps(board, res, None)
    return max(res['soc']['tj_a'], res['soc']['tj_b'])


def fmt_amb(a):
    return 'never (not even at -20 C)' if a is None else ('85 C or more' if a > 84.5 else '%.0f C' % a)


def main():
    global EPS_EFF, NU_GAP, H_FORCED, HEATPATH
    hps = heat_paths()
    HEATPATH = hps[DESIGN_PATH] if DESIGN_PATH else None
    board = Board()
    L = []
    w = L.append
    w('# LayerCam v1: temperatures in a 65 C chamber\n')
    w('Computed by `sim/thermal.py`: the main board as a 2D plate on a 0.5 mm grid (outline from `src/geometry.py`, '
      'part places from `src/layout_main.py`, heat from `sim/power_budget.py`), inside Prusa\'s printed housing in a '
      '%.0f C chamber with still air. The model and every assumed number are listed at the end; the board is the '
      'placed design (routing changes the copper coverage, see the sensitivity).\n' % T_AMB)
    w('The requirement cases are **snapshot mode** (`snap_day`, `snap_night`): a still at most every 10 s, the sensor '
      'in standby, the CPU at its lowest DVFS point and Wi-Fi in power-save between shots (power_budget.py has the '
      'loads). The housing\'s time constant is many minutes, so a 10 s cycle is modelled by its average heat; the '
      'LED junctions and the string resistors are checked at their power while lit. Live view (`day`, `night`) and '
      'the stress bound are reported, not checked; live view gets a chamber limit and a firmware rule instead.\n')
    w('Every case below includes the **%s heat path** from the RV1106\'s top (`mechanical/heat-plate/`, chosen in '
      '*Heat paths compared*). The side button has been removed from the design (test pads instead).\n'
      % DESIGN_PATH)
    w('Board: %.1f cm^2 a face; in-plane conductance %.4f W/K per square (copper coverage F %.0f %%, In1 %.0f %%, '
      'In2 %.0f %%, In3 %.0f %%, In4 %.0f %%, B %.0f %%). SoC exposed pad to the planes: %.2f K/W through %d filled '
      'vias.\n' % (board.area * 1e4, sheet_conductance(), *[100 * COVER[k] for k in
                                                           ('F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu')],
                   ep_via_resistance(), N_EP_VIAS))
    allres = {}
    for name, title, kind in CASES:
        res = case_run(board, name)
        allres[name] = res
        temps = part_temps(board, res, name)
        h = power.heat(name)
        w('## %s\n' % title)
        top = sorted(((k, v) for k, v in h.items() if v > 0.005), key=lambda kv: -kv[1])
        w('Heat in the housing: **%.2f W** (%s).\n' % (sum(h.values()), ', '.join('%s %.2f' % (k, v) for k, v in top)))
        so = res['soc']
        w('| | value |\n|---|---|')
        w('| housing wall | %.1f C (%.1f K over the chamber) |' % (res['t_w'], res['t_w'] - T_AMB))
        w('| air inside (mean of board and wall) | %.1f C |' % res['t_air'])
        w('| main board mean / max | %.1f / %.1f C |' % (np.nanmean(res['T']), np.nanmax(res['T'])))
        w('| board heat out: faces / edge to the pocket / into the camera module | %.2f / %.2f / %.2f W |'
          % (res['flows']['q_wall'] - res['flows']['q_edge'], res['flows']['q_edge'], res['flows']['q_mod']))
        w('| lid-slot air exchange | %.2f W |' % res['q_vent'])
        w('| LED ring (average) | %.1f C (%.2f W average; %.2f W out through the front wall) |'
          % (res['t_ring'], res['p_ring'], res['q_ring_out']))
        w('| RV1106 | %.2f W; board under the pad %.1f C, at the package edge %.1f C; Tj %.1f C (pad path) / %.1f C '
          '(thetaJB 12.5 from the edge) |' % (so['p'], so['t_ep'], so['t_edge'], so['tj_a'], so['tj_b']))
        w('')
        w('| part | temperature (C) | limit (C) | margin (K) | limit from |\n|---|---|---|---|---|')
        for nm, t, lim, src in sorted(temps, key=lambda r: r[2] - r[1]):
            w('| %s | %.1f | %.0f | %+.1f | %s |' % (nm, t, lim, lim - t, src))
        hr, tr, rating = resistor_check(res, name)
        if hr > 0:
            w('| %s string resistor (ring), power while lit | %.3f W | %.3f W at %.0f C | %+.3f W | 0.25 W to 70 C, 0 '
              'at 155 C |' % (parts.PARTS[power.string_resistor()]['value'], hr, rating, tr, rating - hr))
        w('')
        png = plot(board, res, name, '%s: chamber %.0f C' % (title.split(':')[0].split(' (')[0], T_AMB))
        w('![%s](%s)\n' % (name, png))
        if kind != 'req':
            continue
        for nm, t, lim, src in temps:
            soft = any(k in nm for k in ('housing', 'surroundings', 'inductor'))
            check(t <= lim, '%s: %s %.1f C against %.0f C (%s)' % (name, nm, t, lim, src),
                  warn=soft and t <= lim + 5)
        if hr > 0:
            check(hr <= rating, '%s: string resistor %.3f W while lit against %.3f W derated at %.0f C'
                  % (name, hr, rating, tr))
        # a 10 K margin on the parts that matter most
        tp = {nm: t for nm, t, lim, src in temps}
        for key, lim in (('RV1106 junction (U1)', 115), ('AP6256 module (U6)', 75), ('SC3336 sensor (camera module)', 75)):
            check(tp[key] <= lim, '%s: %s %.1f C with %d K margin (%s C)' % (name, key, tp[key], {115: 10, 75: 10}[lim],
                                                                             lim), warn=True)

    # ------------------------------------------------ what moves it
    w('## Sensitivity (snap_night, RV1106 Tj / board max / ring average)\n')
    w('| change | RV1106 Tj (C) | board max (C) | ring (C) |\n|---|---|---|---|')

    def row(lab, res, b=board):
        w('| %s | %.1f | %.1f | %.1f |' % (lab, tj_of(b, res), np.nanmax(res['T']), res['t_ring']))
    base = allres['snap_night']
    row('as above', base)
    row('no lid slots (vents taped or facing down)', case_run(board, 'snap_night', vents=False))
    row('ring not touching the front wall', case_run(board, 'snap_night', ring_contact=False))
    b2 = Board(cover_scale=0.7)
    row('copper coverage x0.7 (a more perforated routed board)', case_run(b2, 'snap_night'), b2)
    e0, n0 = EPS_EFF, NU_GAP
    EPS_EFF = 0.6
    row('inside emissivity 0.6 (bare metal shields, lens holder)', case_run(board, 'snap_night'))
    EPS_EFF = 0.85; NU_GAP = 1.5
    b3 = Board(cover_scale=1.2)
    r3 = case_run(b3, 'snap_night')
    row('optimistic bracket: emissivity 0.85, Nu 1.5, copper x1.2', r3, b3)
    SUMMARY['opt'] = tj_of(b3, r3)
    EPS_EFF, NU_GAP = e0, n0
    H_FORCED = 3.9 * math.sqrt(0.5 / 0.05) - 1.32 * (10 / 0.05) ** 0.25
    row('chamber air moving at 0.5 m/s past the housing', case_run(board, 'snap_night'))
    H_FORCED = 0.0
    hq = dict(power.heat('snap_night')); hq['U1'] *= 1.5
    row('SoC idle 50 % higher than assumed', run_case(board, hq, led_on=power.led_on('snap_night')))
    hq = dict(power.heat('snap_night')); hq['U6'] *= 2
    row('Wi-Fi average twice the assumed 0.05 A', run_case(board, hq, led_on=power.led_on('snap_night')))
    w('')

    # ------------------------------------------------ chamber limits
    w('## Highest chamber temperature per case\n')
    w('Bisection on the same model: the chamber temperature at which the first part reaches its limit.\n')
    w('| case | every part inside its limit up to (first part there) | RV1106 Tj 125 C at | '
      'RV1106 Tj 115 C (10 K margin) at |')
    w('|---|---|---|---|')
    for name, title, kind in CASES:
        h = power.heat(name)
        lo = power.led_on(name) if h.get('ring LEDs') else None
        a_all = ambient_limit(board, h, lambda b, r: within(b, r), led_on=lo)
        a_125 = ambient_limit(board, h, lambda b, r: tj_of(b, r) <= 125, led_on=lo)
        a_115 = ambient_limit(board, h, lambda b, r: tj_of(b, r) <= 115, led_on=lo)

        def lab(a):
            if a is None:
                return 'never (%s)' % first_over(board, h, -20.0, (), led_on=lo)
            if a > 84.5:
                return '85 C or more'
            return '%.1f C (%s)' % (a, first_over(board, h, a + 0.5, (), led_on=lo))
        SUMMARY['lim'][name] = (a_all, a_all, a_125, a_115)
        w('| %s | %s | %s | %s |' % (name, lab(a_all), fmt_amb(a_125), fmt_amb(a_115)))
    w('')
    lim_req = min(SUMMARY['lim'][n][0] if SUMMARY['lim'][n][0] is not None else -99 for n in ('snap_day', 'snap_night'))
    check(lim_req >= T_AMB, 'snapshot mode (heat path: %s) keeps every part inside its rating up to a %s chamber '
          '(requirement %.0f C)' % (DESIGN_PATH, fmt_amb(lim_req), T_AMB))
    check(lim_req >= T_AMB + 5, 'snapshot-mode margin %.1f K at 65 C, against a model uncertainty of about +-10 K'
          % (lim_req - T_AMB), warn=True)

    # ------------------------------------------------ firmware rules for live view
    w('## Firmware rules (thermal governor)\n')
    w('The RV1106\'s TSADC reads its own junction (+-3 C). In a steady state every part sits at a fixed offset from '
      'it for a given load, so a junction temperature can stand in for the hottest part. For each mode: the junction '
      'temperature at the chamber temperature where the first part reaches its rating. '
      'Live view may run while the TSADC is below that reading, less the sensor\'s 3 C error; above it the firmware '
      'falls back to snapshot mode.\n')
    w('| mode | chamber limit (first part) | RV1106 Tj there (steady state) | rule: allowed while '
      'TSADC below | at 65 C in snapshot mode the TSADC reads |')
    w('|---|---|---|---|---|')
    tj_snap = {n: tj_of(board, allres[n]) for n in ('snap_day', 'snap_night')}
    rd = SUMMARY.setdefault('rule', {})
    for lab_, name in (('snapshot, day', 'snap_day'), ('snapshot, night', 'snap_night'), ('live view, day', 'day'),
                       ('live view, night', 'night')):
        a = SUMMARY['lim'][name][1]
        h = power.heat(name)
        lo = power.led_on(name) if h.get('ring LEDs') else None
        if a is None or a > 84.5:
            w('| %s | %s | - | - | %.0f C |' % (lab_, fmt_amb(a), tj_snap['snap_night']))
            continue
        tj = tj_of(board, run_case(board, h, t_amb=a, led_on=lo))
        rd[name] = (a, tj)
        w('| %s | %.0f C | %.0f C | **%.0f C** | %.0f C |' % (lab_, a, tj, tj - 3, tj_snap['snap_night']))
    w('')
    w('Rule set, in order (to be tuned on a board in an oven):\n')
    t_live = min([rd[n][1] for n in ('day', 'night') if n in rd] or [100]) - 3
    t_snap = min([rd[n][1] for n in ('snap_day', 'snap_night') if n in rd] or [100]) - 3
    SUMMARY['gov'] = (t_live, t_snap)
    w('1. **Snapshot mode is the default**: CPU at its lowest OPP between shots, NPU off, sensor in standby, Wi-Fi '
      'power-save on 2.4 GHz.')
    w('2. **Live view** only while TSADC < %.0f C; crossing it ends live view (back to snapshot mode, the user sees '
      '"live view paused: camera too warm"). In a 65 C chamber the snapshot-mode reading is %.0f C.'
      % (t_live, tj_snap['snap_night']))
    w('3. TSADC > %.0f C in snapshot mode: stretch the interval to 30 s, cap Wi-Fi TX power, shorten the IR flash to '
      '1 s (the reading at which the first 85 C part reaches its rating in snapshot mode).' % t_snap)
    w('4. TSADC > 110 C: stop capturing (keep Wi-Fi associated, report the fault).')
    w('5. TSADC > 120 C: power the sensor and Wi-Fi down; Linux critical trip (shutdown) at 125 C.')
    w('')

    # ------------------------------------------------ the heat paths compared
    w('## Heat paths from the RV1106 compared\n')
    w('The three parts in `mechanical/heat-plate/` (plate.py computes each path from its geometry; README.md has '
      'the parts). The junction splits its heat between the board (exposed pad, %.1f K/W) and the part on its top '
      '(theta-JC top 8.4 K/W + pad or tape + metal); the part passes it to the air inside and, for the two that '
      'reach the lid pocket, through the 3.35 mm lid and its slots to the chamber.\n' % (R_DIE_EP + ep_via_resistance()))
    w('| heat path | junction to part (K/W) | part to chamber (K/W) | part to inside air (K/W) | snap_night at 65 C: '
      'RV1106 / AP6256 / SC3336 / board max (C) | heat leaving by the top / straight out (W) | snapshot keeps every '
      'part in rating up to | live view (day / night) every part in rating up to |')
    w('|---|---|---|---|---|---|---|---|')
    keep = HEATPATH
    comp = {}
    for key, lab_ in ((None, 'none (bare board)'), ('heatsink', '1: 14 x 14 x 6 heatsink on tape'),
                      ('cnc', '2: CNC 6061 block, gap pads'), ('sheet', '3: bent 1.5 mm 5052 sheet, gap pads')):
        HEATPATH = hps[key] if key else None
        r = case_run(board, 'snap_night')
        pt = {nm: t for nm, t, lim, src in part_temps(board, r, None)}
        lims = []
        for c in ('snap_day', 'snap_night', 'day', 'night'):
            h = power.heat(c)
            lims.append(ambient_limit(board, h, lambda b, rr: within(b, rr),
                                      led_on=power.led_on(c) if h.get('ring LEDs') else None))
        snap = min((x if x is not None else -99) for x in lims[:2])
        first = first_over(board, power.heat('snap_night'), snap + 0.3, (), led_on=power.led_on('snap_night'))
        comp[key] = dict(tj=pt['RV1106 junction (U1)'], ap=pt['AP6256 module (U6)'],
                         cam=pt['SC3336 sensor (camera module)'], bmax=float(np.nanmax(r['T'])), snap=snap,
                         first=first, live=(lims[2], lims[3]), q_top=r['q_top'], q_amb=r['q_sink_amb'])
        hp = hps.get(key) if key else None
        w('| %s | %s | %s | %s | %.1f / %.1f / %.1f / %.1f | %.2f / %.2f | **%.1f C** (%s) | %s / %s |'
          % (lab_, '%.1f' % hp['r_top'] if hp else '-', '%.0f' % (1 / hp['g_amb']) if hp and hp['g_amb'] else '-',
             '%.0f' % (1 / hp['g_air']) if hp else '-', comp[key]['tj'], comp[key]['ap'], comp[key]['cam'],
             comp[key]['bmax'], r['q_top'], r['q_sink_amb'], snap, first, fmt_amb(lims[2]), fmt_amb(lims[3])))
    HEATPATH = keep
    SUMMARY['comp'] = comp
    w('')

    # ------------------------------------------------ parts list against 65 C
    w('## Every part\'s rating against the chamber\n')
    w('From `src/parts.py` (descriptions, the JLCPCB catalogue\'s temperature field read 26 Oct 2026, the datasheets). '
      'Flagged against the snapshot-night case: a part rated below 85 C, over its rating, or within 10 K of it.\n')
    w('| part | rated | snap_night at 65 C (C) | live night at 65 C (C) | flag (snapshot) |\n|---|---|---|---|---|')
    tsn = {nm: t for nm, t, lim, src in part_temps(board, allres['snap_night'], None)}
    tln = {nm: t for nm, t, lim, src in part_temps(board, allres['night'], None)}
    mean = {'s': float(np.nanmean(allres['snap_night']['T'])), 'l': float(np.nanmean(allres['night']['T']))}
    capk = {nm: (lim, src) for nm, t, lim, src in part_temps(board, allres['snap_night'], None) if 'capacitors' in nm}
    soc_caps = [nm for nm in capk if 'under the SoC' in nm]

    def g(key, d, m):
        if key == 'MEAN':
            return mean[m]
        if key == 'LENS':
            return (d['housing wall (PETG/ASA print)'] + mean[m]) / 2
        if key == 'IND':
            return max(v for k, v in d.items() if 'inductor' in k)
        return d[key]
    rated = [('RV1106G3', 'Tj 125, ambient -20..85', 'RV1106 junction (U1)'),
             ('W25N02KVZEIR', '-40..85', 'W25N02KV flash (U5)'),
             ('AP6256', '-30..85 (full RF -20..75)', 'AP6256 module (U6)'),
             ('EA3036C', 'TA -40..85, TJ to 125', 'EA3036C junction (U3)'),
             ('TLV62569', 'TJ -40..125', 'TLV62569 0.9 V (U2) junction'),
             ('DRV8837', 'TA -40..85', 'DRV8837 (U7)'),
             ('AO3400A', 'TJ -55..150', 'MEAN'),
             ('crystals / oscillator (24M, 37.4M, 32k)', '-40..85', 'crystals Y2 / Y3, oscillator Y4'),
             ('KT-0603G LED', '-40..85', 'status LED LED1'),
             ('XF2M-2015-1A FFC', '-30..85', 'camera FFC connector J2 (XF2M)'),
             ('JST SH BM06B / SM06B', '-25..85', 'SH connectors J1 / J4 (JST)'),
             ('Molex 53261 PicoBlade', '-40..105', 'PicoBlade J3'),
             ('Hirose U.FL', '-40..90', 'U.FL J5'),
             ('TYPE-C-31-M-12 USB-C', '-30..80', 'USB-C receptacle (USB board)'),
             ('USBLC6-2SC6, SMF5.0CA', 'TJ to 125 / 150', 'USB-C receptacle (USB board)'),
             ('JNJ 850 nm IR LED (junction while lit)', '-40..100, Tj 115', 'IR LEDs (ring), junction'),
             ('TEMT6000', '-40..100', 'TEMT6000 light sensor (ring)'),
             ('FPA252012D inductors', 'not in the catalogue (typ. -40..125)', 'IND'),
             ('BLM15PD121 bead', '-55..125', 'MEAN'),
             ('0402 / 1206 thick-film resistors', '-55..155 (power derates above 70)', soc_caps[0]),
             ('C0G / X7R capacitors (12p, 18p, 1n, 10n, 100n)', '-55..125', soc_caps[0])]
    for nm in soc_caps:
        rated.append((nm.replace(' under the SoC (B face)', ''), '-55..%d' % capk[nm][0], nm))
    rated += [('SC3336 module (bought)', '-30..85, best image to 60', 'SC3336 sensor (camera module)'),
              ('CLA219 IR-cut holder (bought)', 'not published (plastic, NdFeB magnet)', 'MEAN'),
              ('Towin CCL127028MPR lens (bought)', 'not published', 'LENS')]
    for nm, rt, key in rated:
        ts, tl_ = g(key, tsn, 's'), g(key, tln, 'l')
        m = re.findall(r'(-?\d+)', rt.split('(')[0])
        hi = max(int(x) for x in m) if m else None
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
    w('- Chamber %.0f C, still air (no credit for the chamber fan); bed radiation %.2f W on the front.' % (T_AMB, BED_RAD_W))
    w('- Housing: outer hull %.1f cm^2, 2 mm walls at %.2f W/mK, emissivity %.2f; natural convection 1.32 (dT/0.05 m)^0.25 '
      'plus linearised radiation outside. Lid slots: %.0f mm^2 split in two halves %.0f mm apart, Cd %.1f.'
      % (A_OUT * 1e4, K_PLASTIC, EPS_HOUSING, VENT_A * 1e6, VENT_H * 1e3, VENT_CD))
    w('- Inside: radiation board to wall with effective emissivity %.2f; still-air conduction across %.1f / %.1f mm '
      'gaps (F / B) with Nu %.1f; board edge to the pocket across %.1f mm of air.'
      % (EPS_EFF, GAP_F * 1e3, GAP_B * 1e3, NU_GAP, EDGE_GAP * 1e3))
    w('- Copper coverage per layer as listed above (ASSUMED until the board is routed; rerun on the routed board, '
      'docs/lessons.md: routing raised temperatures 15 K on Ridge 3).')
    w('- RV1106: die to exposed pad %.0f K/W (ASSUMED) plus the computed via array; the datasheet thetaJB (%.1f K/W, '
      'JEDEC 2s2p) from the board at the package edge as the pessimistic reading; the higher is used.'
      % (R_DIE_EP, THETA_JB_SOC))
    w('- TLV62569 psiJB %.1f K/W (TI). EA3036C %.0f K/W, inductors %.0f K/W, AP6256 %.0f K/W above the board, LED '
      'junction %.0f K/W above the ring: ASSUMED.' % (PSI_JB_TLV, R_JB_EA, R_JB_IND, R_AP6256, R_LED_J))
    w('- Camera module: one node coupled to the board across its 1 mm shim gap and to the lid from its back face; the '
      'sensor die %.0f K above it.' % SENSOR_RISE)
    w('- LED ring: front face pressed on the printed wall (contact %.0f W/m^2K), heat through 2 mm of plastic to the '
      'outside; back face to the inside. No copper pours on the ring.' % H_RING_CONTACT)
    w('- Snapshot mode: the 10 s cycle averaged (housing and board time constants of minutes); the SoC\'s own rise '
      'during a 1.5 s shot (about 0.4 W x 4 K/W) is under 2 K and not added.')
    w('')
    return L, allres


def verdict(board, allres):
    V = []
    v = V.append
    t = {n: {nm: x for nm, x, lim, src in part_temps(board, allres[n], None)} for n in allres}
    lim = SUMMARY['lim']
    comp = SUMMARY['comp']
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    req = min((lim[n][0] if lim[n][0] is not None else -99) for n in ('snap_day', 'snap_night'))
    v('## Verdict\n')
    v('**Snapshot mode at 65 C, with the %s heat path: %s** (%d FAIL, %d WARN). Every part stays inside its rating '
      'up to a **%s** chamber: a margin of %.1f K, inside the model\'s +-10 K uncertainty, so the first board must be '
      'measured in a 65 C oven before this is called a pass.\n'
      % (DESIGN_PATH, 'PASS (marginal)' if not fails else 'FAIL', len(fails), len(warns), fmt_amb(req), req - T_AMB))
    v('| at 65 C, %s heat path | snap_day | snap_night | live day | live night |\n|---|---|---|---|---|' % DESIGN_PATH)
    for lab, k in (('RV1106 junction', 'RV1106 junction (U1)'), ('AP6256 (85 C)', 'AP6256 module (U6)'),
                   ('SC3336 sensor (85 C)', 'SC3336 sensor (camera module)'), ('USB-C (80 C)', 'USB-C receptacle (USB board)'),
                   ('crystals (85 C)', 'crystals Y2 / Y3, oscillator Y4'), ('board max', None),
                   ('LED ring (average)', 'RING'), ('IR LED junction while lit', 'IR LEDs (ring), junction')):
        vals = []
        for n in ('snap_day', 'snap_night', 'day', 'night'):
            r = allres[n]
            vals.append(float(np.nanmax(r['T'])) if k is None else (r['t_ring'] if k == 'RING' else t[n][k]))
        v('| %s | %s |' % (lab, ' | '.join('%.1f C' % x for x in vals)))
    v('| heat in the housing | %s |' % ' | '.join('%.2f W' % allres[n]['p_total'] for n in ('snap_day', 'snap_night',
                                                                                              'day', 'night')))
    v('')
    v('Heat paths (snap_night at 65 C; chamber limit for snapshot mode):\n')
    for key, lab in ((None, 'bare board'), ('heatsink', '1 heatsink 14x14x6'), ('cnc', '2 CNC block'),
                     ('sheet', '3 bent sheet')):
        c = comp[key]
        v('- %s: RV1106 %.1f, AP6256 %.1f, SC3336 %.1f C; snapshot in rating to **%.1f C** (first: %s); live view to '
          '%s / %s.' % (lab, c['tj'], c['ap'], c['cam'], c['snap'], c['first'], fmt_amb(c['live'][0]),
                        fmt_amb(c['live'][1])))
    v('')
    over = {}
    for n in ('snap_day', 'snap_night'):
        for nm, x, lm, src in part_temps(board, allres[n], None):
            if x > lm - 3:
                over[nm] = (max(x, over.get(nm, (0, 0))[0]), lm)
    if over:
        v('- Within 3 K of their rating in snapshot mode at 65 C: ' + '; '.join(
            '%s %.1f / %d C' % (nm, x, lm) for nm, (x, lm) in sorted(over.items(), key=lambda kv: kv[1][1] - kv[1][0])))
    hr, tr, rating = resistor_check(allres['snap_night'], 'snap_night')
    v('- String resistor (%s) while lit at night: %.3f W against %.3f W derated at %.0f C.'
      % (parts.PARTS[power.string_resistor()]['value'], hr, rating, tr))
    v('- Live view stays a firmware-gated mode: every part in rating to %s by day and %s by night with the %s path. '
      'Governor: live view only while TSADC < %.0f C; snapshot mode stretches to 30 s above %.0f C; stop at 110 C; '
      'shutdown 125 C.' % (fmt_amb(lim['day'][0]), fmt_amb(lim['night'][0]), DESIGN_PATH, *SUMMARY['gov']))
    v('- AP6256 and SC3336 run above 75 C in snapshot mode (full RF and best image end there): WARN, they work.')
    v('- Model uncertainty about +-10 K (optimistic bracket %.0f K lower on the SoC); the snapshot currents are '
      'ASSUMED. Measure on the first board and rerun.'
      % (t['snap_night']['RV1106 junction (U1)'] - SUMMARY.get('opt', t['snap_night']['RV1106 junction (U1)'])))
    v('')
    return V


if __name__ == '__main__':
    L, allres = main()
    i = [k for k, x in enumerate(L) if x.startswith('## Snapshot, day')][0]
    L[i:i] = verdict(Board(), allres)
    w = L.append
    w('## Checks\n')
    for s_, what in checks:
        w('- %s %s' % (s_, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    for f in os.listdir(HERE):
        if f.startswith('thermal_') and f.endswith('.png') and f[8:-4] not in allres:
            os.remove(os.path.join(HERE, f))
    sys.exit(1 if fails else 0)
