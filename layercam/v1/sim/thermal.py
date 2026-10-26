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
CU_T = {'F.Cu': 0.035, 'B.Cu': 0.035, 'In1.Cu': 0.0152, 'In2.Cu': 0.0152, 'In3.Cu': 0.0152, 'In4.Cu': 0.0152}
DX = 0.5e-3                       # grid, m

# footprints the heat is spread over (mm, centred on the part's place in layout_main.py)
FOOT = {'U1': (9.0, 9.0), 'U2': (3.0, 1.7), 'L1': (2.5, 2.0), 'U3': (3.0, 3.0), 'L2': (2.5, 2.0),
        'L3': (2.5, 2.0), 'L4': (2.5, 2.0), 'U4': (3.0, 1.7), 'L5': (2.5, 2.0), 'U6': (12.0, 12.0),
        'U5': (8.0, 6.0), 'U7': (2.0, 2.0), 'Q1': (2.9, 1.3), 'J1': (4.0, 8.0)}
SINK_R = None                     # K/W from the SoC area straight to the chamber (a metal lid + gap pad), None = none
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
    r_one = 0.115e-3 / (K_CU * a)          # F.Cu pad to In1, through the 0.0994 prepreg + copper
    r_vias = r_one / N_EP_VIAS
    r_fr4 = 0.0994e-3 / (0.3 * 49e-6)      # the prepreg under the 7 x 7 pad, in parallel
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
        g_s = np.zeros(self.n)
        if SINK_R:
            m = self.mask(*self.place['U1'][:2], 10.0, 10.0)[self.inside]
            g_s[m] = 1 / SINK_R / m.sum()
        A = self.K + sp.diags(g_wall + g_m + g_s)
        T = spla.spsolve(A.tocsc(), q + g_wall * t_wall + g_m * t_mod + g_s * self.t_amb)
        self.q_sink = float((g_s * (T - self.t_amb)).sum())
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


def run_case(board, heat, t_amb=T_AMB, vents=True, ring_contact=True):
    heat_in = dict(heat)
    heat = dict(heat)
    p_total = sum(heat.values())
    p_cam = heat.pop('camera module', 0.0)
    p_ring = heat.pop('ring resistors', 0.0) + heat.pop('ring LEDs', 0.0)
    p_cable = heat.pop('cable, connectors', 0.0)
    heat['J1'] = p_cable                            # half on the main board's connector, half on the USB board
    q = board.sources(heat)
    q_board = q.sum()
    a_mod = G.MODULE_W * G.MODULE_H * 1e-6
    g_gap = (K_AIR / (G.MODULE_SHIM * 1e-3) + 8.0) * a_mod      # module to board: 1 mm air + radiation
    t_w = t_amb + 10.0
    t_b = t_w + 20.0
    t_m = t_b
    board.t_amb = t_amb
    for it in range(200):
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
        # everything else reaches the wall and leaves through it
        q_into_wall = p_total - q_ring_out - q_vent - board.q_sink
        a_rest = A_OUT - (spread if ring_contact else 0.0)
        h_o = h_outside(t_w, t_amb)
        r_wall = WALL_T / (K_PLASTIC * A_OUT * 0.85) + 1 / (h_o * a_rest)
        t_w_new = t_amb + (q_into_wall + BED_RAD_W) * r_wall
        if abs(t_w_new - t_w) < 1e-4 and abs(t_b_new - t_b) < 1e-4 and abs(t_m_new - t_m) < 1e-4:
            break
        t_w = 0.5 * t_w + 0.5 * t_w_new
        t_m = 0.5 * t_m + 0.5 * t_m_new
        t_b = t_b_new
    t_cam = t_m + SENSOR_RISE
    return dict(T=T, t_w=t_w, t_b=t_b, t_air=(t_b + t_w) / 2, t_ring=t_ring, q_vent=q_vent, q_ring_out=q_ring_out,
                q_board=q_board, p_ring=p_ring, p_cam=p_cam, t_cam=t_cam, t_mod=t_m, h_in=(hF, hB), h_out=h_o,
                heat=heat, heat_in=heat_in, flows=dict(board.last), p_total=p_total, t_amb=t_amb)


# ---------------------------------------------------------------- per-part temperatures
def part_temps(board, res, case):
    T = res['T']
    heat = res['heat']
    out = []        # (name, temperature, limit, limit source)
    p_soc = heat['U1']
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
    out.append(('X5R capacitors under the SoC (B face)', board.at(T, 'U1', 12.0, 12.0, stat='max'), 85,
                'X5R: -55..85 C (Samsung)'))
    out.append(('X5R capacitors at the bucks', max(board.at(T, r, 5, 5, stat='max') for r in ('U2', 'U3', 'U4')), 85,
                'X5R: -55..85 C (Samsung)'))
    out.append(('X5R capacitors elsewhere (board mean)', float(np.nanmean(T)), 85, 'X5R: -55..85 C'))
    out.append(('24 MHz crystal Y1', board.at(T, 'Y1', 3, 3, stat='max'), 85, '-40..85 C (YXC)'))
    out.append(('crystals Y2 / Y3, oscillator Y4', max(board.at(T, r, 3, 3, stat='max') for r in ('Y2', 'Y3', 'Y4')), 85,
                '-40..85 C'))
    out.append(('status LED LED1', board.at(T, 'LED1', 2, 2, stat='max'), 85, '-40..85 C (KENTO)'))
    out.append(('side button SW1 (TS24CA)', board.at(T, 'SW1', 4, 2, stat='max'), 70, '-20..70 C (catalogue)'))
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


def _led_heat_each(res):
    return res['heat_in'].get('ring LEDs', 0.0) / 6


def resistor_check(res, case):
    """39 R 1206 (UNI-ROYAL 1206W4F): 0.25 W at 70 C, linear to 0 at 155 C."""
    h = res['heat_in'].get('ring resistors', 0.0) / 3
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
    for ref in ('U1', 'U2', 'U3', 'U4', 'U6', 'U5', 'J1', 'J2', 'SW1'):
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
def ambient_limit(board, heat, limit_fn, lo=-20.0, hi=85.0):
    """The highest chamber temperature at which limit_fn holds (bisection), or lo if it never does."""
    if not limit_fn(board, run_case(board, heat, t_amb=lo)):
        return None
    for _ in range(16):
        mid = (lo + hi) / 2
        ok = limit_fn(board, run_case(board, heat, t_amb=mid))
        lo, hi = (mid, hi) if ok else (lo, mid)
    return lo


def first_over(board, heat, t_amb, skip=()):
    res = run_case(board, heat, t_amb=t_amb)
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


def main():
    board = Board()
    L = []
    w = L.append
    w('# LayerCam v1: temperatures at 65 C ambient\n')
    w('Computed by `sim/thermal.py`: the main board as a 2D plate on a 0.5 mm grid (outline from `src/geometry.py`, '
      'part places from `src/layout_main.py`, heat from `sim/power_budget.py`), inside Prusa\'s printed housing in a '
      '%.0f C chamber with still air. The model and every assumed number are listed at the end; the board is the '
      'placed design (routing changes the copper coverage, see the sensitivity).\n' % T_AMB)
    w('Board: %.1f cm^2 a face; in-plane conductance %.4f W/K per square (copper coverage F %.0f %%, In1 %.0f %%, '
      'In2 %.0f %%, In3 %.0f %%, In4 %.0f %%, B %.0f %%). SoC exposed pad to the planes: %.2f K/W through %d filled '
      'vias.\n' % (board.area * 1e4, sheet_conductance(), *[100 * COVER[k] for k in
                                                           ('F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu')],
                   ep_via_resistance(), N_EP_VIAS))
    cases = [('day', 'Day: streaming, Wi-Fi average, LEDs off'),
             ('night', 'Night: streaming with the IR LEDs on'),
             ('worst', 'Worst sustained: SoC at its measured maximum, Wi-Fi transmitting, LEDs at the high corner')]
    allres = {}
    for name, title in cases:
        h = power.heat(name)
        res = run_case(board, h)
        allres[name] = res
        temps = part_temps(board, res, name)
        tot = sum(power.heat(name).values())
        w('## %s\n' % title)
        top = sorted(((k, v) for k, v in power.heat(name).items() if v > 0.005), key=lambda kv: -kv[1])
        w('Heat in the housing: **%.2f W** (%s).\n' % (tot, ', '.join('%s %.2f' % (k, v) for k, v in top)))
        s = res['soc']
        w('| | value |\n|---|---|')
        w('| housing wall | %.1f C (%.1f K over the chamber; outside h %.1f W/m^2K) |' % (res['t_w'], res['t_w'] - T_AMB,
                                                                                     res['h_out']))
        w('| air inside (mean of board and wall) | %.1f C |' % res['t_air'])
        w('| main board mean / max | %.1f / %.1f C |' % (np.nanmean(res['T']), np.nanmax(res['T'])))
        w('| inside heat transfer, F / B face | %.1f / %.1f W/m^2K |' % res['h_in'])
        w('| lid-slot air exchange | %.2f W |' % res['q_vent'])
        w('| board heat out: faces to the wall / edge to the pocket / into the camera module | %.2f / %.2f / %.2f W |'
          % (res['flows']['q_wall'] - res['flows']['q_edge'], res['flows']['q_edge'], res['flows']['q_mod']))
        w('| LED ring | %.1f C (%.2f W; %.2f W out through the front wall) |' % (res['t_ring'], res['p_ring'],
                                                                            res['q_ring_out']))
        w('| RV1106 | %.2f W; board under the pad %.1f C, at the package edge %.1f C; Tj %.1f C (pad path) / %.1f C '
          '(thetaJB 12.5 from the edge) |' % (s['p'], s['t_ep'], s['t_edge'], s['tj_a'], s['tj_b']))
        w('')
        w('| part | temperature (C) | limit (C) | margin (K) | limit from |\n|---|---|---|---|---|')
        for nm, t, lim, src in sorted(temps, key=lambda r: r[2] - r[1]):
            w('| %s | %.1f | %.0f | %+.1f | %s |' % (nm, t, lim, lim - t, src))
        hr, tr, rating = resistor_check(res, name)
        if hr > 0:
            w('| 39 R string resistor (ring), power | %.3f W | %.3f W at %.0f C | | 0.25 W to 70 C, 0 at 155 C |'
              % (hr, rating, tr))
        w('')
        png = plot(board, res, name, '%s: chamber %.0f C' % (title.split(':')[0], T_AMB))
        w('![%s](%s)\n' % (name, png))
        # checks
        for nm, t, lim, src in temps:
            soft = any(k in nm for k in ('AP6256', 'SC3336', 'housing', 'surroundings', 'inductor'))
            check(t <= lim, '%s: %s %.1f C against %.0f C (%s)' % (name, nm, t, lim, src), warn=soft and t <= lim + 5)
        if hr > 0:
            check(hr <= rating, '%s: 39 R dissipates %.3f W against %.3f W derated at %.0f C' % (name, hr, rating, tr))

    # ------------------------------------------------ what moves it
    w('## Sensitivity (night case, RV1106 Tj / board max / ring)\n')
    w('| change | RV1106 Tj (C) | board max (C) | ring (C) |\n|---|---|---|---|')
    base = allres['night']

    def row(lab, res, b=board):
        part_temps(b, res, 'night')
        w('| %s | %.1f | %.1f | %.1f |' % (lab, max(res['soc']['tj_a'], res['soc']['tj_b']), np.nanmax(res['T']),
                                          res['t_ring']))
    row('as above', base)
    row('no lid slots (vents taped or facing down)', run_case(board, power.heat('night'), vents=False))
    row('ring not touching the front wall', run_case(board, power.heat('night'), ring_contact=False))
    b2 = Board(cover_scale=0.7)
    row('copper coverage x0.7 (a more perforated routed board)', run_case(b2, power.heat('night')), b2)
    global EPS_EFF, NU_GAP, H_FORCED, SINK_R
    e0, n0 = EPS_EFF, NU_GAP
    EPS_EFF = 0.6
    row('inside emissivity 0.6 (bare metal shields, lens holder)', run_case(board, power.heat('night')))
    EPS_EFF = e0
    NU_GAP = 1.5
    row('air gaps convecting (Nu 1.5)', run_case(board, power.heat('night')))
    NU_GAP = n0
    H_FORCED = 3.9 * math.sqrt(0.5 / 0.05) - 1.32 * (14 / 0.05) ** 0.25
    row('chamber air moving at 0.5 m/s past the housing (forced h %.0f W/m^2K)' % (3.9 * math.sqrt(0.5 / 0.05)),
        run_case(board, power.heat('night')))
    H_FORCED = 0.0
    EPS_EFF, NU_GAP = 0.85, 1.5
    b3 = Board(cover_scale=1.2)
    row('optimistic bracket: emissivity 0.85, Nu 1.5, copper x1.2', run_case(b3, power.heat('night')), b3)
    EPS_EFF, NU_GAP = e0, n0
    SINK_R = 26.0
    row('aluminium lid with a gap pad on the SoC (26 K/W SoC to chamber)', run_case(board, power.heat('night')))
    SINK_R = None
    hq = dict(power.heat('night')); hq['U1'] *= 0.75
    row('SoC heat -25 % (lower clocks, NPU off, lower bitrate)', run_case(board, hq))
    hq = dict(power.heat('night')); hq['ring LEDs'] *= 0.5; hq['ring resistors'] *= 0.5
    row('IR LEDs at 50 % PWM', run_case(board, hq))
    w('')

    # ------------------------------------------------ the ambient at which each case runs out
    w('## Highest chamber temperature per case\n')
    w('The chamber temperature at which the first part reaches its limit (bisection on the same model; "never" = '
      'not even at -20 C). The button (rated 70 C) is left out of the second column: it is the first to go in every '
      'case and is a part swap.\n')
    w('| case | every part inside its limit up to | the same without the button | RV1106 Tj 125 C reached at | '
      'RV1106 Tj 105 C (20 K margin) at |')
    w('|---|---|---|---|---|')

    def fmt(a, heat, skip=()):
        if a is None:
            return 'never (%s)' % first_over(board, heat, -20.0, skip)
        return '%.0f C (%s)' % (a, first_over(board, heat, a + 0.5, skip))

    def tj(b, r):
        part_temps(b, r, None)
        return max(r['soc']['tj_a'], r['soc']['tj_b'])

    def lim_rows(rows):
        global SINK_R
        for lab, heat, sink in rows:
            SINK_R = sink
            a_all = ambient_limit(board, heat, lambda b, r: within(b, r))
            a_nb = ambient_limit(board, heat, lambda b, r: within(b, r, skip=('button',)))
            a_125 = ambient_limit(board, heat, lambda b, r: tj(b, r) <= 125)
            a_105 = ambient_limit(board, heat, lambda b, r: tj(b, r) <= 105)
            w('| %s | %s | %s | %s | %s |' % (lab, fmt(a_all, heat), fmt(a_nb, heat, ('button',)),
                                              '%.0f C' % a_125 if a_125 is not None else 'never',
                                              '%.0f C' % a_105 if a_105 is not None else 'never'))
            SINK_R = None
    lim_rows([(n, power.heat(n), None) for n, t in cases])
    w('')
    lims = None

    # ------------------------------------------------ what it would take
    w('## What it would take\n')
    w('The same model with the changes that matter, one at a time and together. *Throttled*: SoC heat -40 % (CPU '
      'capped near 800 MHz, NPU off, H.264 at a modest bitrate; to be measured), Wi-Fi on 2.4 GHz at reduced TX power '
      '(average 0.08 A). *LEDs 30 %*: IR_PWM at 30 % duty with the 39 R kept. *Al lid*: an aluminium lid (or a plate '
      'in the lid\'s vent window) touching the SoC through a 1 mm gap pad and a spacer, 26 K/W from the SoC area to '
      'the chamber (pad 2 K/W, lid 24 K/W from ~30 cm^2 of outer surface).\n')

    def mod(case, soc=1.0, wifi=None, led=1.0):
        h = dict(power.heat(case))
        h['U1'] *= soc
        if wifi is not None:
            h['U6'] = 3.33 * wifi
        for k in ('ring LEDs', 'ring resistors', 'Q1'):
            if k in h:
                h[k] *= led
        return h
    mrows = [('day, throttled', mod('day', 0.6, 0.08), None),
             ('day, Al lid', mod('day'), 26.0),
             ('day, throttled + Al lid', mod('day', 0.6, 0.08), 26.0),
             ('night, throttled + LEDs 30 %', mod('night', 0.6, 0.08, 0.3), None),
             ('night, throttled + LEDs 30 % + Al lid', mod('night', 0.6, 0.08, 0.3), 26.0)]
    w('| change | heat (W) | at 65 C: RV1106 Tj / board max / AP6256 / sensor / ring (C) |\n|---|---|---|')
    for lab, h, sink in mrows:
        SINK_R = sink
        r = run_case(board, h)
        pt = {nm: t for nm, t, lim, src in part_temps(board, r, None)}
        w('| %s | %.2f | %.0f / %.0f / %.0f / %.0f / %.0f |' % (lab, sum(h.values()), pt['RV1106 junction (U1)'],
                                                              np.nanmax(r['T']), pt['AP6256 module (U6)'],
                                                              pt['SC3336 sensor (camera module)'], r['t_ring']))
        SINK_R = None
    w('')
    w('Highest chamber temperature with those changes:\n')
    w('| case | every part inside its limit up to | the same without the button | RV1106 Tj 125 C reached at | '
      'RV1106 Tj 105 C at |')
    w('|---|---|---|---|---|')
    lim_rows(mrows)
    w('')

    # ------------------------------------------------ parts list against 65 C
    w('## Every part\'s rating against the chamber\n')
    w('From `src/parts.py` (descriptions, the JLCPCB catalogue\'s temperature field read 26 Oct 2026, the datasheets). '
      'A part rated below 85 C, or whose estimate above leaves under 10 K, is flagged.\n')
    w('| part | rated | worst estimate (C) | flag |\n|---|---|---|---|')
    worst_t = {nm: t for nm, t, lim, src in part_temps(board, allres['worst'], 'worst')}
    night_t = {nm: t for nm, t, lim, src in part_temps(board, allres['night'], 'night')}
    board_mean_w = float(np.nanmean(allres['worst']['T']))
    rated = [
        ('RV1106G3', 'Tj 125, ambient -20..85', worst_t['RV1106 junction (U1)']),
        ('W25N02KVZEIR', '-40..85', worst_t['W25N02KV flash (U5)']),
        ('AP6256', '-30..85 (full RF -20..75)', worst_t['AP6256 module (U6)']),
        ('EA3036C', 'TA -40..85, TJ to 125', worst_t['EA3036C junction (U3)']),
        ('TLV62569', 'TJ -40..125', worst_t['TLV62569 0.9 V (U2) junction']),
        ('DRV8837', 'TA -40..85', worst_t['DRV8837 (U7)']),
        ('AO3400A', 'TJ -55..150', board_mean_w),
        ('ASH7KW 32.768 kHz osc.', '-40..85', worst_t['crystals Y2 / Y3, oscillator Y4']),
        ('X322524MOB4SI 24 MHz', '-40..85', worst_t['24 MHz crystal Y1']),
        ('3225 37.4 MHz', '-40..85', worst_t['crystals Y2 / Y3, oscillator Y4']),
        ('Q13FC1350 32.768 kHz', '-40..85', worst_t['crystals Y2 / Y3, oscillator Y4']),
        ('KT-0603G LED', '-40..85', worst_t['status LED LED1']),
        ('XF2M-2015-1A FFC', '-30..85', worst_t['camera FFC connector J2 (XF2M)']),
        ('JST SH BM06B / SM06B', '-25..85', worst_t['SH connectors J1 / J4 (JST)']),
        ('Molex 53261 PicoBlade', '-40..105', worst_t['PicoBlade J3']),
        ('Hirose U.FL', '-40..90', worst_t['U.FL J5']),
        ('TS24CA side button', '-20..70', worst_t['side button SW1 (TS24CA)']),
        ('TYPE-C-31-M-12 USB-C', '-30..80', worst_t['USB-C receptacle (USB board)']),
        ('USBLC6-2SC6', 'TJ -40..125', worst_t['USB-C receptacle (USB board)']),
        ('SMF5.0CA TVS', '-55..150', worst_t['USB-C receptacle (USB board)']),
        ('JNJ 850 nm IR LED', '-40..100, Tj 115', worst_t['IR LEDs (ring), junction']),
        ('TEMT6000', '-40..100', worst_t['TEMT6000 light sensor (ring)']),
        ('FPA252012D inductors', 'not in the catalogue (typ. -40..125)', max(v for k, v in worst_t.items() if 'inductor' in k)),
        ('BLM15PD121 bead', '-55..125', board_mean_w),
        ('0402 / 1206 thick-film resistors', '-55..155 (power derates above 70)', worst_t['X5R capacitors under the SoC (B face)']),
        ('C0G / X7R capacitors (12p, 18p, 1n, 10n, 100n)', '-55..125', worst_t['X5R capacitors under the SoC (B face)']),
        ('X5R capacitors (1u, 4.7u, 10u, 22u)', '-55..85', worst_t['X5R capacitors under the SoC (B face)']),
        ('SC3336 module (bought)', '-30..85, best image to 60', worst_t['SC3336 sensor (camera module)']),
        ('CLA219 IR-cut holder (bought)', 'not published (plastic, NdFeB magnet)', board_mean_w),
        ('Towin CCL127028MPR lens (bought)', 'not published', worst_t['housing wall (PETG/ASA print)']),
    ]
    for nm, rt, t in rated:
        m = re.findall(r'(-?\d+)', rt.split('(')[0])
        hi = max(int(x) for x in m) if m else None
        flag = ''
        if hi is None:
            flag = 'UNKNOWN rating: ask the maker'
        elif hi < 85:
            flag = 'RATED BELOW 85 C'
        if hi is not None and t > hi:
            flag = (flag + '; ' if flag else '') + 'OVER its rating'
        elif hi is not None and hi - t < 10:
            flag = (flag + '; ' if flag else '') + 'under 10 K margin'
        w('| %s | %s | %.0f | %s |' % (nm, rt, t, flag))
    w('')

    # ------------------------------------------------ model and assumptions
    w('## Model and assumptions\n')
    w('- Chamber %.0f C, still air (no credit for the chamber fan); bed radiation %.2f W on the front.' % (T_AMB, BED_RAD_W))
    w('- Housing: outer hull %.1f cm^2, 2 mm walls at %.2f W/mK, emissivity %.2f; natural convection 1.32 (dT/0.05 m)^0.25 '
      'plus linearised radiation outside. Lid slots: %.0f mm^2 split in two halves %.0f mm apart, Cd %.1f.'
      % (A_OUT * 1e4, K_PLASTIC, EPS_HOUSING, VENT_A * 1e6, VENT_H * 1e3, VENT_CD))
    w('- Inside: radiation board to wall with effective emissivity %.2f; still-air conduction across %.1f / %.1f mm '
      'gaps (F / B) with Nu %.1f.' % (EPS_EFF, GAP_F * 1e3, GAP_B * 1e3, NU_GAP))
    w('- Copper coverage per layer as listed above (ASSUMED until the board is routed; rerun on the routed board, '
      'docs/lessons.md: routing raised temperatures 15 K on Ridge 3).')
    w('- RV1106: die to exposed pad %.0f K/W (ASSUMED) plus the computed via array; the datasheet thetaJB (%.1f K/W, '
      'JEDEC 2s2p) from the board temperature at the package edge as the pessimistic reading; the higher is used.'
      % (R_DIE_EP, THETA_JB_SOC))
    w('- TLV62569 psiJB %.1f K/W (TI). EA3036C %.0f K/W, inductors %.0f K/W, AP6256 %.0f K/W above the board, LED '
      'junction %.0f K/W above the ring: ASSUMED.' % (PSI_JB_TLV, R_JB_EA, R_JB_IND, R_AP6256, R_LED_J))
    w('- Camera module: one node coupled to the board across its 1 mm shim gap (air conduction + radiation) and to the '
      'lid from its back face; the sensor die %.0f K above it. Board edge to the housing pocket across %.1f mm of air.'
      % (SENSOR_RISE, EDGE_GAP * 1e3))
    w('- LED ring: front face pressed on the printed wall (contact %.0f W/m^2K), heat through 2 mm of plastic to the '
      'outside over the ring\'s area plus 5 mm all round; back face to the inside. The ring has no copper pours, so '
      'the LEDs sit on thin tracks.' % H_RING_CONTACT)
    w('')
    return L, allres, lims


if __name__ == '__main__':
    L, allres, lims = main()
    w = L.append
    w('## Checks\n')
    for s, what in checks:
        w('- %s %s' % (s, what))
    w('')
    fails = [c for c in checks if c[0] == 'FAIL']
    warns = [c for c in checks if c[0] == 'WARN']
    w('**%s, %d WARN**' % ('no FAIL' if not fails else '%d FAIL' % len(fails), len(warns)))
    open(OUT, 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    sys.exit(1 if fails else 0)
