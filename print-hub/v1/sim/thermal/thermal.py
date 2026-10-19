# -*- coding: utf-8 -*-
"""Board-level thermal simulator for a multilayer PCB read from KiCad.

    tools/kd python3 sim/thermal/thermal.py BOARD.kicad_pcb --case full-50C-wash-sun
    tools/kd python3 sim/thermal/thermal.py BOARD.kicad_pcb --case desert     (the worst-case set)
    tools/kd python3 sim/thermal/thermal.py BOARD.kicad_pcb --list            (what the cases are)

Finite-volume model on a uniform in-plane grid (0.2 mm default) with one node
per copper layer per cell; the dielectric between two copper layers is a
through-thickness conductance, and half of each dielectric's in-plane
conduction and heat capacity is lumped into the copper node on either side.
The copper of every layer is rasterised from pcbnew (zones refilled first,
tracks, arcs, pads, via pads, copper graphics) at 8 sub-pixels per cell, and
the conductance across each cell face is the parallel sum of series rows of
sub-pixels, so a 0.1 mm gap between two pours stays an insulator even though
it is smaller than a cell.  Vias and plated holes are copper barrels.
Components inject heat at their pads, optionally through a junction node
(Rth junction-to-pad); wires on pads are 1-D fins with Joule heating and a
far end held at the motor's or battery's temperature; DC current flow in the
power nets is solved on the same grid to get the copper's own I^2 R heat.
Top and bottom lose heat by convection (natural, forced, or both) and
radiation; the top can absorb sunlight.  Steady state: scipy SuperLU with
fixed-point iterations for the nonlinear terms (radiation, natural
convection, R_DS(on)(T), copper resistivity(T)).  Transient: implicit Euler.

All physical constants and their sources are in README.md next to this file.
"""
import argparse
import json
import math
import os
import re
import sys
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, HERE)

SIGMA = 5.670374e-8          # Stefan-Boltzmann, W/m2K4
T_RUNAWAY = 600.0            # C: a solution past this is reported as 'no steady state'
G0 = 9.81


# ---------------------------------------------------------------------------
#  Materials (README "Materials" lists the sources)
# ---------------------------------------------------------------------------
class Params:
    k_cu = 390.0             # W/mK, electrodeposited / rolled foil (pure Cu 401)
    rc_cu = 8930 * 385.0     # J/m3K = 3.44e6
    rho_cu = 1.72e-8         # ohm m at 20 C (IACS 100 %: 1.724e-8)
    alpha_cu = 0.00393       # 1/K resistivity tempco
    k_fr4_xy = 0.3           # W/mK, in-plane; 0.3 reproduces Toshiba's Rth(ch-a) on both test boards
                             # (measured laminates reach ~0.8 in-plane: --fr4-xy 0.8 is the optimistic bound)
    k_fr4_z = 0.3            # W/mK, through-plane
    rc_fr4 = 1900 * 1100.0   # J/m3K = 2.09e6
    plating = 18e-6          # m, via / PTH barrel wall copper
    k_via_fill = 0.0         # W/mK, 0 = air; ~0.5 for non-conductive POFV epoxy
    emissivity = 0.9         # solder mask (top; bottom the same unless emissivity_bot is set)
    emissivity_bot = None
    absorptivity = 0.9       # black solder mask, solar
    rc_pkg = 1.8e6           # J/m3K, mould compound / ceramic average for package bodies
    pkg_fill = 0.9           # fraction of the bounding box that is solid
    t_frame = 0.2e-3         # m, copper leadframe / exposed pad of a package (TSON, QFN)
    cell_mm = 0.2
    ss = 8                   # sub-pixels per cell edge (even)
    inner_oz = None          # override inner copper weight (oz); None = the board's stackup
    outer_oz = None
    stack = None             # override the dielectric thicknesses, mm, top to bottom


OZ_M = 34.79e-6              # 1 oz/ft2 of copper = 34.8 um (35 um nominal)


# ---------------------------------------------------------------------------
#  Air properties and convection correlations
# ---------------------------------------------------------------------------
# Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, Table A.4 (air, 1 atm)
_AIR_T = np.array([250., 300., 350., 400., 450.])
_AIR_NU = np.array([11.44e-6, 15.89e-6, 20.92e-6, 26.41e-6, 32.39e-6])
_AIR_K = np.array([22.3e-3, 26.3e-3, 30.0e-3, 33.8e-3, 37.3e-3])
_AIR_A = np.array([15.9e-6, 22.5e-6, 29.9e-6, 38.3e-6, 47.2e-6])
_AIR_PR = np.array([0.720, 0.707, 0.700, 0.690, 0.686])


def air(T_K):
    T = float(np.clip(T_K, 250, 450))
    return (np.interp(T, _AIR_T, _AIR_NU), np.interp(T, _AIR_T, _AIR_K),
            np.interp(T, _AIR_T, _AIR_A), np.interp(T, _AIR_T, _AIR_PR))


def h_plate_natural(dT, Ta_C, L, up=True):
    """Average natural-convection h of a horizontal plate, hot face up
    (Nu = 0.54 Ra^1/4, Incropera eq. 9.30) or down (Nu = 0.52 Ra^1/5,
    Incropera 7th ed. eq. 9.32).  L = area / perimeter.  dT may be an array."""
    dT = np.maximum(np.abs(dT), 1e-3)
    Tf = Ta_C + 273.15 + 0.5 * float(np.mean(dT))
    nu, k, a, pr = air(Tf)
    Ra = G0 * (1.0 / Tf) * dT * L ** 3 / (nu * a)
    Nu = 0.54 * Ra ** 0.25 if up else 0.52 * Ra ** 0.2
    return Nu * k / L


def h_plate_forced(v, Ta_C, L, dT=20.0):
    """Average laminar flat-plate h, Nu = 0.664 Re^1/2 Pr^1/3 (Incropera 7.30)."""
    if v <= 0:
        return 0.0
    nu, k, a, pr = air(Ta_C + 273.15 + 0.5 * dT)
    Re = v * L / nu
    return 0.664 * Re ** 0.5 * pr ** (1 / 3.) * k / L


def h_cyl(v, D, dT, Ta_C, fscale=1.0):
    """Cylinder in cross-flow (Churchill-Bernstein, Incropera 7.54) combined
    with natural convection (Churchill-Chu, Incropera 9.34), cubic blend."""
    dT = np.maximum(np.abs(dT), 1e-3)
    Tf = Ta_C + 273.15 + 0.5 * float(np.mean(dT))
    nu, k, a, pr = air(Tf)
    Ra = G0 / Tf * dT * D ** 3 / (nu * a)
    Nun = (0.60 + 0.387 * Ra ** (1 / 6.) / (1 + (0.559 / pr) ** (9 / 16.)) ** (8 / 27.)) ** 2
    hn = Nun * k / D
    if v > 0:
        Re = v * D / nu
        Nuf = 0.3 + 0.62 * Re ** 0.5 * pr ** (1 / 3.) / (1 + (0.4 / pr) ** (2 / 3.)) ** 0.25 * \
            (1 + (Re / 282000.) ** (5 / 8.)) ** (4 / 5.)
        hf = fscale * Nuf * k / D
    else:
        hf = 0.0
    return (hn ** 3 + hf ** 3) ** (1 / 3.)


# ---------------------------------------------------------------------------
#  Geometry
# ---------------------------------------------------------------------------
class Geom:
    """Rasterised board.  Coordinates in mm, KiCad orientation (y down)."""

    def __init__(self, name, x0, y0, nx, ny, d_mm, ss):
        self.name, self.x0, self.y0, self.nx, self.ny, self.d, self.ss = name, x0, y0, nx, ny, d_mm, ss
        self.ds = d_mm / ss
        self.W, self.H = nx * ss, ny * ss
        self.items = []          # (layer index, net, [pts mm arrays])  all copper
        self.board_polys = []    # outline polygons (fractured), mm
        self.holes = []          # (x, y, diameter) non-plated holes, mm
        self.vias = []           # dict(x, y, drill, top, bot, net)
        self.fps = []            # dict(ref, value, fpid, side, x, y, w, h, height, pads=[...])
        self.cu_names, self.t_cu, self.t_diel = [], None, None
        self._net_cache = {}

    # -- rasterising -------------------------------------------------------
    def _to_px(self, pts):
        return [((x - self.x0) / self.ds - 0.5, (y - self.y0) / self.ds - 0.5) for x, y in pts]

    def raster(self, polys, value_holes=None):
        from PIL import Image, ImageDraw
        img = Image.new('1', (self.W, self.H), 0)
        dr = ImageDraw.Draw(img)
        for pts in polys:
            if len(pts) >= 3:
                dr.polygon(self._to_px(pts), fill=1)
        if value_holes:
            for x, y, dia in value_holes:
                cx, cy = (x - self.x0) / self.ds - 0.5, (y - self.y0) / self.ds - 0.5
                r = dia / 2 / self.ds
                dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
        return np.array(img, dtype=bool)

    def raster_local(self, pts):
        """Rasterise one small polygon; returns (cell indices flat, area m2 per cell)."""
        from PIL import Image, ImageDraw
        pts = np.asarray(pts, float)
        ss = self.ss
        c0 = max(int((pts[:, 0].min() - self.x0) / self.d) - 1, 0)
        r0 = max(int((pts[:, 1].min() - self.y0) / self.d) - 1, 0)
        c1 = min(int((pts[:, 0].max() - self.x0) / self.d) + 2, self.nx)
        r1 = min(int((pts[:, 1].max() - self.y0) / self.d) + 2, self.ny)
        img = Image.new('1', ((c1 - c0) * ss, (r1 - r0) * ss), 0)
        ox, oy = c0 * ss, r0 * ss
        ImageDraw.Draw(img).polygon([(px - ox, py - oy) for px, py in self._to_px(pts)], fill=1)
        a = np.array(img, dtype=float).reshape(r1 - r0, ss, c1 - c0, ss).sum((1, 3))
        jj, ii = np.nonzero(a)
        if len(jj) == 0:   # sub-pixel pad: put it in the cell under its centroid
            cx, cy = pts.mean(0)
            i = int((cx - self.x0) / self.d); j = int((cy - self.y0) / self.d)
            return np.array([j * self.nx + i]), np.array([1e-12])
        cells = (jj + r0) * self.nx + (ii + c0)
        return cells, a[jj, ii] * (self.ds * 1e-3) ** 2

    def copper(self, layer):
        if not hasattr(self, '_cu'):
            self._cu = [self.raster([p for (l, n, ps) in self.items if l == k for p in ps])
                        for k in range(len(self.cu_names))]
            for (l, n), mask in getattr(self, 'extra', {}).items():
                self._cu[l] = self._cu[l] | mask
        return self._cu[layer]

    def net_copper(self, net, layer):
        key = (net, layer)
        if key not in self._net_cache:
            self._net_cache[key] = self.raster([p for (l, n, ps) in self.items if l == layer and n == net for p in ps])
            if (layer, net) in getattr(self, 'extra', {}):
                self._net_cache[key] = self._net_cache[key] | self.extra[(layer, net)]
        return self._net_cache[key]

    def via_layers(self, v):
        """Layers a via barrel joins: its end layers plus every layer where
        its own net's copper reaches it (a ring 0.35-0.5 mm from the centre,
        outside its own pad).  On the others it passes through an antipad, so
        the barrel bypasses that layer's node."""
        if 'conn' in v:
            return v['conn']
        r0, r1 = (v['drill'] / 2 + 0.2) / self.ds, (v['drill'] / 2 + 0.35) / self.ds
        cy, cx = (v['y'] - self.y0) / self.ds - 0.5, (v['x'] - self.x0) / self.ds - 0.5
        R = int(r1) + 2
        j0, i0 = int(cy) - R, int(cx) - R
        jj, ii = np.mgrid[j0:j0 + 2 * R + 1, i0:i0 + 2 * R + 1]
        d = np.hypot(jj - cy, ii - cx)
        ring = (d >= r0) & (d <= r1) & (jj >= 0) & (ii >= 0) & (jj < self.H) & (ii < self.W)
        jj, ii = jj[ring], ii[ring]
        conn = [v['top']]
        for k in range(v['top'] + 1, v['bot']):
            if v['net'] and self.net_copper(v['net'], k)[jj, ii].any():
                conn.append(k)
        conn.append(v['bot'])
        v['conn'] = conn
        return conn

    def add_copper(self, layer, net, mask):
        """Extra copper as a sub-pixel mask (what-if studies: fills, pours)."""
        self.extra = getattr(self, 'extra', {})
        k = (layer, net)
        self.extra[k] = self.extra[k] | mask if k in self.extra else mask
        for a in ('_cu',):
            if hasattr(self, a):
                delattr(self, a)
        self._net_cache = {}
        for v in self.vias:
            v.pop('conn', None)

    def board(self):
        if not hasattr(self, '_board'):
            self._board = self.raster(self.board_polys, self.holes)
        return self._board

    def fp(self, ref):
        for f in self.fps:
            if f['ref'] == ref:
                return f
        return None


def _polys(ps):
    """SHAPE_POLY_SET -> list of point arrays (mm); fractures holes first."""
    import pcbnew
    if any(ps.HoleCount(i) for i in range(ps.OutlineCount())):
        try:
            ps.Fracture()
        except TypeError:
            ps.Fracture(pcbnew.SHAPE_POLY_SET.PM_FAST)
    out = []
    for i in range(ps.OutlineCount()):
        ol = ps.Outline(i)
        n = ol.PointCount()
        out.append(np.array([(ol.CPoint(k).x * 1e-6, ol.CPoint(k).y * 1e-6) for k in range(n)]))
    return out


def _shape(item, layer):
    import pcbnew
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, 0, 2000, pcbnew.ERROR_INSIDE)
    return _polys(ps)


def read_stackup(path, ncu):
    """Copper and dielectric thicknesses (m) from the board file's (stackup)."""
    s = open(path).read()
    m = re.search(r'\(stackup(.*?)\n\t\t\)', s, re.S)
    cu, diel = [], []
    if m:
        cur = None
        for blk in re.finditer(r'\(layer "([^"]+)"(.*?)(?=\n\t\t\t\(layer |\Z)', m.group(1), re.S):
            name, body = blk.group(1), blk.group(2)
            ts = [float(t) for t in re.findall(r'\(thickness ([\d.]+)', body)]
            if '(type "copper")' in body:
                if cur is not None:
                    diel.append(cur)
                cu.append(ts[0] * 1e-3 if ts else 0.035e-3)
                cur = 0.0
            elif name.startswith('dielectric') and cur is not None:
                cur += sum(ts) * 1e-3
    if len(cu) != ncu or len(diel) != ncu - 1:
        # fallback: 1 oz outer, 0.5 oz inner; dielectrics as src/pcb.py writes
        # them (JLC04161H-7628 for 4 layers, nominal 6-layer 1.6 mm build),
        # otherwise the rest of 1.6 mm spread evenly
        cu = [0.035e-3] + [0.0175e-3] * (ncu - 2) + [0.035e-3]
        diel = {4: [0.2104e-3, 1.065e-3, 0.2104e-3],
                6: [0.1e-3, 0.4e-3, 0.45e-3, 0.4e-3, 0.1e-3]}.get(ncu, [(1.6e-3 - sum(cu)) / (ncu - 1)] * (ncu - 1))
        print('  stackup: none in the file, using the default %d-layer 1.6 mm stack (src/pcb.py)' % ncu)
    return np.array(cu), np.array(diel)


def load_kicad(path, P=Params, fill=True):
    import pcbnew
    t0 = time.time()
    b = pcbnew.LoadBoard(path)
    if fill and len(b.Zones()):
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    stack = list(b.GetEnabledLayers().CuStack())
    L = {lid: k for k, lid in enumerate(stack)}
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps, True)
    bb = ps.BBox()
    xmin, ymin = bb.GetX() * 1e-6, bb.GetY() * 1e-6
    w, h = bb.GetWidth() * 1e-6, bb.GetHeight() * 1e-6
    d = P.cell_mm
    nx, ny = int(math.ceil(w / d)) + 2, int(math.ceil(h / d)) + 2
    g = Geom(os.path.splitext(os.path.basename(path))[0], xmin - d, ymin - d, nx, ny, d, P.ss)
    g.board_polys = _polys(ps)
    g.cu_names = [b.GetLayerName(l) for l in stack]
    g.t_cu, g.t_diel = read_stackup(path, len(stack))
    n = len(stack)
    if P.stack:
        if len(P.stack) != n - 1:
            raise SystemExit('--stack needs %d dielectric thicknesses' % (n - 1))
        g.t_diel = np.array(P.stack) * 1e-3
    if P.outer_oz:
        g.t_cu[0] = g.t_cu[-1] = P.outer_oz * OZ_M
    if P.inner_oz and n > 2:
        g.t_cu[1:-1] = P.inner_oz * OZ_M
    # copper items
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for lid in z.GetLayerSet().CuStack():
            if lid in L:
                g.items.append((L[lid], z.GetNetname(), _polys(z.GetFilledPolysList(lid))))
    for t in b.GetTracks():
        cls = t.GetClass()
        if cls in ('PCB_TRACK', 'PCB_ARC'):
            g.items.append((L[t.GetLayer()], t.GetNetname(), _shape(t, t.GetLayer())))
        elif cls == 'PCB_VIA':
            top, bot = L[t.TopLayer()], L[t.BottomLayer()]
            for k in range(min(top, bot), max(top, bot) + 1):
                if t.FlashLayer(stack[k]):
                    g.items.append((k, t.GetNetname(), _shape(t, stack[k])))
            p = t.GetPosition()
            g.vias.append(dict(x=p.x * 1e-6, y=p.y * 1e-6, drill=t.GetDrillValue() * 1e-6,
                               top=min(top, bot), bot=max(top, bot), net=t.GetNetname()))
    for dw in b.GetDrawings():
        if dw.GetLayer() in L and dw.GetClass() == 'PCB_SHAPE':
            g.items.append((L[dw.GetLayer()], dw.GetNetname() if hasattr(dw, 'GetNetname') else '', _shape(dw, dw.GetLayer())))
    for f in b.GetFootprints():
        side = 1 if f.IsFlipped() else 0
        cy = f.GetCourtyard(pcbnew.B_CrtYd if side else pcbnew.F_CrtYd)
        bbx = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        height = None
        for m in f.Models():
            mh = re.search(r'-H(\d+(?:\.\d+)?)', os.path.basename(m.m_Filename))
            if mh:
                height = float(mh.group(1))
        fpid = f.GetFPIDAsString()
        try:
            lcsc = f.GetFieldText('LCSC')
        except Exception:
            lcsc = ''
        rec = dict(ref=f.GetReference(), value=f.GetValue(), fpid=fpid, side=side, lcsc=lcsc,
                   x=f.GetPosition().x * 1e-6, y=f.GetPosition().y * 1e-6,
                   w=bbx.GetWidth() * 1e-6, h=bbx.GetHeight() * 1e-6,
                   bx=bbx.GetX() * 1e-6, by=bbx.GetY() * 1e-6,
                   height=height or guess_height(fpid), pads=[])
        for gi in f.GraphicalItems():
            if gi.GetLayer() in L and gi.GetClass() == 'PCB_SHAPE':
                g.items.append((L[gi.GetLayer()], '', _shape(gi, gi.GetLayer())))
        for pd in f.Pads():
            attr = pd.GetAttribute()
            pos = pd.GetPosition()
            if attr == pcbnew.PAD_ATTRIB_NPTH:
                g.holes.append((pos.x * 1e-6, pos.y * 1e-6, pd.GetDrillSize().x * 1e-6))
                continue
            lays = [L[l] for l in pd.GetLayerSet().CuStack() if l in L]
            pr = dict(num=pd.GetNumber(), net=pd.GetNetname(), layers=lays, cells={}, area=0.0,
                      x=pos.x * 1e-6, y=pos.y * 1e-6, polys={})
            for k in lays:
                if attr == pcbnew.PAD_ATTRIB_PTH and not pd.FlashLayer(stack[k]):
                    continue
                pp = _shape(pd, stack[k])
                g.items.append((k, pd.GetNetname(), pp))
                pr['polys'][k] = pp
                if pp:
                    cells, area = g.raster_local(np.vstack(pp))
                    pr['cells'][k] = (cells, area)
                    if k == lays[0] or not pr['area']:
                        pr['area'] = float(area.sum())
            if attr == pcbnew.PAD_ATTRIB_PTH:
                g.vias.append(dict(x=pos.x * 1e-6, y=pos.y * 1e-6, drill=pd.GetDrillSize().x * 1e-6,
                                   top=min(lays), bot=max(lays), net=pd.GetNetname()))
            rec['pads'].append(pr)
        g.fps.append(rec)
    print('  read %s: %d copper layers, %d items, %d vias/holes, %d footprints, grid %d x %d (%.2f mm) in %.1f s' % (
        os.path.basename(path), n, len(g.items), len(g.vias), len(g.fps), nx, ny, d, time.time() - t0))
    print('  stackup (um): ' + ' | '.join('%s %.1f' % (nm, t * 1e6) for nm, t in zip(g.cu_names, g.t_cu)) +
          '   dielectrics (mm): ' + ', '.join('%.3f' % (t * 1e3) for t in g.t_diel))
    return g


_HEIGHTS = [('0201', 0.3), ('0402', 0.5), ('0603', 0.8), ('0805', 1.0), ('1206', 0.7), ('TSON', 0.9),
            ('DFN', 0.9), ('SON', 0.9), ('QFN', 0.9), ('LGA', 0.9), ('UFQFPN', 0.6), ('SOT-23', 1.1),
            ('SC-70', 1.0), ('SOD', 1.0), ('IND', 2.0), ('LED', 0.6), ('USB', 3.2), ('CONN', 4.0),
            ('CRYSTAL', 0.8), ('KEY', 0.6), ('WSON', 0.8), ('SMF', 1.1)]


def guess_height(fpid):
    u = fpid.upper()
    for k, hgt in _HEIGHTS:
        if k in u:
            return hgt
    return 0.0 if ('PAD' in u or 'HOLE' in u or 'MOUNT' in u) else 0.8


# ---------------------------------------------------------------------------
#  Network assembly
# ---------------------------------------------------------------------------
def face_conductance(kt, ss, nx, ny):
    """kt: (H, W) per-square conductance of each sub-pixel (W/K, or S for the
    electrical solve).  Returns gx (ny, nx-1) and gy (ny-1, nx), the
    conductance between neighbouring cell centres.

    Three estimates over the window of sub-pixels between the two centres:
      lower: parallel sum of series rows (exact for features running along
             the face normal; a gap across the path makes it ~0; but a
             diagonal trace has no straight row and comes out too high in
             resistance)
      upper: series sum of parallel columns (exact for straight features too;
             lets current move sideways freely, so it bridges diagonal gaps)
      frac:  harmonic mean of the two cells' area-averaged conductance (the
             usual effective-medium value: right for diagonal traces a cell
             or more wide, but blind to a gap narrower than a cell)
    and takes max(lower, min(frac, upper)): a straight gap stays an
    insulator (upper ~ 0), a diagonal trace conducts (frac), straight
    features are exact (lower).  Checked against straight and 45-degree
    strips in validate.py."""
    H, W = kt.shape
    R = 1.0 / kt
    cm = kt.reshape(ny, ss, nx, ss).mean((1, 3))           # cell mean (parallel)
    out = []
    for axis in (1, 0):
        if axis == 1:
            n = nx
            Rrow, Kcol = R, kt.reshape(ny, ss, W).sum(1)    # rows: (H, W); columns summed over band: (ny, W)
        else:
            n = ny
            Rrow, Kcol = R.T, kt.T.reshape(nx, ss, H).sum(1)
        cs = np.zeros((Rrow.shape[0], Rrow.shape[1] + 1))
        np.cumsum(Rrow, axis=1, out=cs[:, 1:])
        st = np.arange(n - 1) * ss + ss // 2
        lower = (1.0 / (cs[:, st + ss] - cs[:, st])).reshape(-1, ss, n - 1).sum(1)
        cs = np.zeros((Kcol.shape[0], Kcol.shape[1] + 1))
        np.cumsum(1.0 / Kcol, axis=1, out=cs[:, 1:])
        upper = 1.0 / (cs[:, st + ss] - cs[:, st])
        c = cm if axis == 1 else cm.T
        frac = 2 * c[:, :-1] * c[:, 1:] / (c[:, :-1] + c[:, 1:])
        g = np.maximum(lower, np.minimum(frac, upper))
        out.append(g if axis == 1 else g.T)
    return out[0], out[1]


def cu_weight(cu):
    """Copper weight per sub-pixel: 1 inside, 0.5 on the rim.  PIL fills a
    polygon including the pixels its edge passes through, half a sub-pixel
    proud on each side; halving the rim takes that back (a 0.3 mm trace
    drawn at 0.025 mm sub-pixels would otherwise be 8 % too wide)."""
    inner = cu.copy()
    inner[1:, :] &= cu[:-1, :]; inner[:-1, :] &= cu[1:, :]
    inner[:, 1:] &= cu[:, :-1]; inner[:, :-1] &= cu[:, 1:]
    return np.where(inner, 1.0, np.where(cu, 0.5, 0.0))


def block_mean(a, ss):
    H, W = a.shape
    return a.reshape(H // ss, ss, W // ss, ss).mean((1, 3))


class Model:
    """Thermal network of one board plus its attachments (junctions, wires,
    optional heat-spreader plates: see add_plates)."""

    def __init__(self, g, topo, P=Params, cooling=None):
        t0 = time.time()
        self.g, self.P, self.topo = g, P, topo
        nL = self.nL = len(g.cu_names)
        ss, nx, ny = g.ss, g.nx, g.ny
        A = (g.d * 1e-3) ** 2
        bsub = g.board()
        fb = block_mean(bsub.astype(float), ss)
        act = fb >= 0.5
        self.cid = -np.ones((ny, nx), int)
        self.cid[act] = np.arange(act.sum())
        self.cpos = np.nonzero(act)                     # (row, column) of each active cell
        self.nc = nc = int(act.sum())
        self.fb = fb[act]
        self.nb = nc * nL
        tc, td = g.t_cu, g.t_diel
        thalf = np.array([(td[l - 1] if l > 0 else 0) / 2 + (td[l] if l < nL - 1 else 0) / 2 for l in range(nL)])
        rows, cols, vals = [], [], []
        C = np.zeros(self.nb)
        self.cufrac = np.zeros((nL, nc))

        def link(a, b, gv):
            rows.append(a); cols.append(b); vals.append(gv)

        # package leadframes: under the pads a junction feeds, the part's own
        # copper (~0.2 mm) spreads heat sideways as well as the board's
        frame = {}
        for e in topo['elements']:
            f = g.fp(e['ref'])
            if e.get('rth') is None or f is None:
                continue
            l = (nL - 1) if f['side'] else 0
            for pd in f['pads']:
                if (e.get('pads') is None or pd['num'] in e['pads']) and l in pd.get('polys', {}):
                    frame.setdefault(l, []).extend(pd['polys'][l])
        for l in range(nL):
            cu = cu_weight(g.copper(l))
            kt = cu * P.k_cu * tc[l] + (1 - cu) * P.k_fr4_xy * tc[l] + P.k_fr4_xy * thalf[l]
            if l in frame:
                kt = kt + g.raster(frame[l]) * P.k_cu * P.t_frame
            kt = np.where(bsub, kt, 1e-12)
            gx, gy = face_conductance(kt, ss, nx, ny)
            ia, ib = self.cid[:, :-1], self.cid[:, 1:]
            m = (ia >= 0) & (ib >= 0)
            link(ia[m] * nL + l, ib[m] * nL + l, gx[m])
            ia, ib = self.cid[:-1, :], self.cid[1:, :]
            m = (ia >= 0) & (ib >= 0)
            link(ia[m] * nL + l, ib[m] * nL + l, gy[m])
            f = block_mean(cu, ss)[act]
            self.cufrac[l] = f
            C[np.arange(nc) * nL + l] = A * self.fb * (f * tc[l] * P.rc_cu + (1 - f) * tc[l] * P.rc_fr4 + thalf[l] * P.rc_fr4)
        for l in range(nL - 1):
            kz1 = self.cufrac[l] * P.k_cu + (1 - self.cufrac[l]) * P.k_fr4_z
            kz2 = self.cufrac[l + 1] * P.k_cu + (1 - self.cufrac[l + 1]) * P.k_fr4_z
            R = tc[l] / 2 / kz1 + td[l] / P.k_fr4_z + tc[l + 1] / 2 / kz2
            idx = np.arange(nc) * nL
            link(idx + l, idx + l + 1, A * self.fb / R)
        # vias and plated holes: copper barrel (+ fill) between successive layers
        nv = 0
        for v in g.vias:
            c = self.cell_at(v['x'], v['y'])
            if c < 0:
                continue
            r = v['drill'] / 2 * 1e-3
            Ab = math.pi * ((r + P.plating) ** 2 - r ** 2)
            Af = math.pi * r ** 2
            conn = g.via_layers(v)
            for a, b in zip(conn, conn[1:]):
                Lz = sum(tc[l] / 2 + td[l] + tc[l + 1] / 2 for l in range(a, b))
                link(np.array([c * nL + a]), np.array([c * nL + b]), np.array([(P.k_cu * Ab + P.k_via_fill * Af) / Lz]))
            nv += 1
        self.surface = np.zeros((2, nc))     # m2 exposed, top and bottom
        self.surface[0] = A * self.fb
        self.surface[1] = A * self.fb
        # length scales for the convection correlations: area / perimeter
        # (natural, Incropera 9.6.3) and the side of the equivalent square (forced)
        area = self.fb.sum() * A
        perim = sum(float(np.sum(np.hypot(*np.diff(np.vstack([p, p[:1]]), axis=0).T))) for p in g.board_polys) * 1e-3
        self.area = area
        self.L_nat = area / perim if perim > 0 else math.sqrt(area) / 4
        self.L_flow = math.sqrt(area)
        # extra nodes ---------------------------------------------------------
        self.extra = []                      # names
        N = self.nb
        # component bodies: extra convective area and heat capacity at their pads
        for f in g.fps:
            if not f['pads'] or f['height'] <= 0:
                continue
            side = f['side']
            l = nL - 1 if side else 0
            cells, areas = self.pad_cells(f, None, l)
            if len(cells) == 0:
                continue
            wgt = areas / areas.sum()
            fin = 2 * (f['w'] + f['h']) * f['height'] * 1e-6
            np.add.at(self.surface[side], cells, fin * wgt)
            cpk = f['w'] * f['h'] * f['height'] * 1e-9 * P.rc_pkg * P.pkg_fill
            np.add.at(C, cells * nL + l, cpk * wgt)
        # junction nodes
        self.junc = {}
        Cx = []
        for e in topo['elements']:
            if e.get('rth') is None:
                continue
            f = g.fp(e['ref'])
            l = (nL - 1) if f['side'] else 0
            cells, areas = self.pad_cells(f, e['pads'], l)
            if len(cells) == 0:
                print('  warning: %s has no pad copper for its junction' % e['name'])
                continue
            j = N; N += 1
            self.junc[e['name']] = j
            gtot = 1.0 / e['rth']
            hc, ha = self.hubs(cells, areas)
            link(np.full(len(hc), j), hc * nL + l, gtot * ha / ha.sum())
            Cx.append(e.get('cj', 0.003))
            self.extra.append(e['name'])
        # wires: chain of nodes, node 0 soldered on the pad
        self.wires = []
        for w in topo['wires']:
            f = g.fp(w['ref'])
            if f is None:
                continue
            l = (nL - 1) if f['side'] else 0
            cells, areas = self.pad_cells(f, w.get('pads'), l)
            if len(cells) == 0:
                continue
            ns = w.get('segments', 10)
            Lw = w['length_mm'] * 1e-3
            dx = Lw / ns
            Acu = math.pi / 4 * (w['d_cu_mm'] * 1e-3) ** 2
            Do = (w['d_cu_mm'] + 2 * w['ins_mm']) * 1e-3
            Ains = math.pi / 4 * (Do ** 2 - (w['d_cu_mm'] * 1e-3) ** 2)
            first = N
            nodes = np.arange(N, N + ns); N += ns
            # joint: solder fillet over the pad, ~ k_solder 50 W/mK over 0.1 mm
            hc, ha = self.hubs(cells, areas)
            link(np.full(len(hc), nodes[0]), hc * nL + l, 50.0 * ha / 0.1e-3 + 1e-9)
            gseg = P.k_cu * Acu / dx
            link(nodes[:-1], nodes[1:], np.full(ns - 1, gseg))
            Cx += [Acu * dx * P.rc_cu + Ains * dx * 1.6e6] * ns
            self.extra += ['%s.%d' % (w['name'], i) for i in range(ns)]
            self.wires.append(dict(w, nodes=nodes, dx=dx, Acu=Acu, Do=Do,
                                   gend=P.k_cu * Acu / (dx / 2),
                                   rins=math.log(Do / (w['d_cu_mm'] * 1e-3)) / (2 * math.pi * 0.2)))
        # surfaces that lose heat: the two board faces, unless a plate covers them
        A_ = (g.d * 1e-3) ** 2
        self.faces = [dict(idx=np.arange(nc) * nL, area=self.surface[0], side=0, up=True, mult=1.0, eps=None),
                      dict(idx=np.arange(nc) * nL + nL - 1, area=self.surface[1], side=1, up=False, mult=1.0, eps=None)]
        self.solar_idx, self.solar_area = np.arange(nc) * nL, self.fb * A_
        self.plates = {}
        if cooling:
            N = self.add_plates(cooling, N, link, Cx, topo)
        self.N = N
        self.C = np.concatenate([C, np.array(Cx)])
        r = np.concatenate(rows); c = np.concatenate(cols); v = np.concatenate(vals)
        G = sp.coo_matrix((v, (r, c)), shape=(N, N))
        G = G + G.T
        d = np.asarray(G.sum(1)).ravel()
        self.G = (sp.diags(d) - G).tocsc()
        self._joule = {}
        print('  model: %d cells x %d layers = %d nodes + %d extra (%d junctions, %d wire nodes), %d vias, built in %.1f s' % (
            nc, nL, self.nb, N - self.nb, len(self.junc), sum(len(w['nodes']) for w in self.wires), nv, time.time() - t0))

    # -- heat-spreader plates --------------------------------------------------
    # Aluminium 6061-T6: k 167 W/mK, rho 2700 kg/m3, cp 896 J/kgK.  Gap pad 3 W/mK.
    K_AL, RC_AL, RHO_AL = 167.0, 2700 * 896.0, 2700.0
    K_PAD, RHO_PAD = 3.0, 3100.0
    Z_PLATE = 1.5e-3       # plate underside above the board face: 1.0 mm parts + 0.5 mm pad
    H_GAP_RAD = 8.0        # W/m2K, radiation across the gap (eps 0.9 board, 0.85 anodised plate, ~90 C)
    K_BODY = dict(C=3.0, R=5.0, L=4.0, D=1.0, U=0.8, Q=0.8, Y=1.0)   # W/mK, through a package body
    # junction to package top (K/W): datasheet RthJC(top) where given; TSON and STM32 assumed
    R_JTOP = dict(fet=15.0, U_BEC=47.5, U_GVDD=45.9, U_LDO=92.3, U_LDOE=92.3, U_FC=25.0, U_E=30.0, U_D=42.5)

    def add_plates(self, cooling, N, link, Cx, topo):
        """cooling: {'top' and/or 'bottom': dict(t=plate m, fins=bool)}.
        A plate covers the whole face.  It is joined:
          - to the board face across the 1.5 mm gap: air conduction + radiation;
          - to every part on that face through the part body and a gap pad
            (3 W/mK) whose thickness is 0.5 mm on parts 1.0 mm or taller (the
            plate is pocketed over taller ones) and 1.5 mm - height on lower
            parts (a stepped pad: the thicker the pad, the lower the part).
            Contact area 0.8 x the courtyard box.  Parts with a junction node
            connect from the junction through RthJ-top instead of the body.
        Its outer face takes over the board face's convection, radiation and
        (top) sun; fins multiply its convection."""
        g, P, nL, nc = self.g, self.P, self.nL, self.nc
        A = (g.d * 1e-3) ** 2
        self.plate_mass = {}
        for sname, opt in cooling.items():
            side = 0 if sname == 'top' else 1
            l = 0 if side == 0 else nL - 1
            t = opt.get('t', 1.0e-3)
            base = N; N += nc
            nodes = base + np.arange(nc)
            # in-plane
            for ia, ib in ((self.cid[:, :-1], self.cid[:, 1:]), (self.cid[:-1, :], self.cid[1:, :])):
                m = (ia >= 0) & (ib >= 0)
                link(base + ia[m], base + ib[m], np.full(int(m.sum()), self.K_AL * t))
            t_fin = 0.0
            mult = 1.0
            if opt.get('fins'):
                # 4 mm fins, 0.5 mm thick, 1.5 mm pitch: per pitch 1.0 mm of base exposed plus
                # 2 x 4 mm + 0.5 mm tip of fin at efficiency ~0.98 (mL ~ 0.16 at h 60 W/m2K)
                fh, ft, pitch, eta = 4e-3, 0.5e-3, 1.5e-3, 0.98
                mult = ((pitch - ft) + eta * (2 * fh + ft)) / pitch
                t_fin = ft * fh / pitch
            Cx += list(A * self.fb * self.RC_AL * (t + t_fin))
            area_plate = float(self.fb.sum() * A)
            mass = area_plate * (t + t_fin) * self.RHO_AL * 1e3
            # board face <-> plate across the gap: air + radiation; with fill=True the
            # bare board (not under a part) touches the plate through 1.5 mm of pad
            gg = A * self.fb * (0.028 / self.Z_PLATE + self.H_GAP_RAD)
            if opt.get('fill'):
                under = np.zeros((g.ny, g.nx), bool)
                for f in g.fps:
                    if f['side'] == side and f['height'] > 0 and f['pads']:
                        j0 = max(int((f['by'] - g.y0) / g.d), 0); i0 = max(int((f['bx'] - g.x0) / g.d), 0)
                        under[j0:int((f['by'] + f['h'] - g.y0) / g.d) + 1, i0:int((f['bx'] + f['w'] - g.x0) / g.d) + 1] = True
                bare = ~under[self.cid >= 0]
                gg = np.where(bare, A * self.fb * self.K_PAD / self.Z_PLATE, gg)
                fill_vol = float((A * self.fb)[bare].sum()) * self.Z_PLATE
            else:
                fill_vol = 0.0
            link(np.arange(nc) * nL + l, nodes, gg)
            # parts
            pad_vol = 0.0
            ncontact = 0
            jtop = {e['ref']: e['name'] for e in topo['elements'] if e['name'] in self.junc}
            for f in g.fps:
                if f['side'] != side or f['height'] <= 0 or not f['pads'] or f['ref'][0] not in self.K_BODY:
                    continue
                Ac = 0.8 * f['w'] * f['h'] * 1e-6
                tp = 0.5e-3 if f['height'] >= 1.0 else (1.5 - f['height']) * 1e-3
                pad_vol += Ac * tp
                # plate cells over the part
                j0 = int((f['by'] - g.y0) / g.d); j1 = int((f['by'] + f['h'] - g.y0) / g.d) + 1
                i0 = int((f['bx'] - g.x0) / g.d); i1 = int((f['bx'] + f['w'] - g.x0) / g.d) + 1
                cc = self.cid[max(j0, 0):j1, max(i0, 0):i1].ravel()
                cc = cc[cc >= 0]
                if len(cc) == 0:
                    continue
                ph, pa = self.hubs(cc, np.ones(len(cc)))
                topn = N; N += 1
                Cx.append(0.0)
                link(np.full(len(ph), topn), base + ph, self.K_PAD * Ac / tp * pa / pa.sum())
                ref = f['ref']
                key = 'fet' if (ref.startswith('Q') and ref[1:2].isdigit()) else \
                    ('U_E' if ref.startswith('U_E') else ('U_D' if ref.startswith('U_D') else ref))
                if ref in jtop and key in self.R_JTOP:
                    link(np.array([self.junc[jtop[ref]]]), np.array([topn]), np.array([1.0 / self.R_JTOP[key]]))
                else:
                    cells, areas = self.pad_cells(f, None, l)
                    if len(cells) == 0:
                        continue
                    hc, ha = self.hubs(cells, areas)
                    gb = self.K_BODY[ref[0]] * Ac / (f['height'] * 1e-3)
                    link(hc * nL + l, np.full(len(hc), topn), gb * ha / ha.sum())
                ncontact += 1
            mass += (pad_vol + fill_vol) * self.RHO_PAD * 1e3
            self.plate_mass[sname] = mass
            # the plate's outer face replaces the board face
            self.surface[side][:] = 0.0
            self.faces[side] = dict(idx=nodes, area=A * self.fb, side=side, up=(side == 0), mult=mult, eps=0.85)
            if side == 0:
                self.solar_idx, self.solar_area = nodes, A * self.fb
            self.plates[sname] = nodes
            print('  %s plate: %.1f g (%s), %d parts in contact, pad %.0f mm3' % (
                sname, mass, 'finned' if mult > 1 else 'flat', ncontact, pad_vol * 1e9))
        return N

    # -- helpers -------------------------------------------------------------
    def cell_at(self, x, y):
        g = self.g
        i = int((x - g.x0) / g.d); j = int((y - g.y0) / g.d)
        if 0 <= i < g.nx and 0 <= j < g.ny:
            return self.cid[j, i]
        return -1

    def pad_cells(self, f, pads, layer):
        """Active cell ids and copper areas (m2) under the given pads (numbers,
        or None = all pads) of footprint f on one layer."""
        cs, ar = [], []
        for p in f['pads']:
            if pads is not None and p['num'] not in pads:
                continue
            if layer in p['cells']:
                cells, areas = p['cells'][layer]
                cid = self.cid.ravel()[cells]
                m = cid >= 0
                cs.append(cid[m]); ar.append(areas[m])
        if not cs:
            return np.zeros(0, int), np.zeros(0)
        cs, ar = np.concatenate(cs), np.concatenate(ar)
        u, inv = np.unique(cs, return_inverse=True)
        return u, np.bincount(inv, ar)

    def hubs(self, cells, areas, k=3):
        """Up to k x k representative cells of a pad set, each carrying the
        copper area of its share: a node tied to hundreds of cells makes a
        dense matrix row, which the fill-reducing ordering handles very badly
        (minutes instead of seconds); the pad copper spreads the heat anyway."""
        if len(cells) <= k * k:
            return cells, areas
        jj, ii = self.cpos[0][cells], self.cpos[1][cells]
        bx = np.minimum((np.argsort(np.argsort(ii)) * k) // len(ii), k - 1)
        by = np.minimum((np.argsort(np.argsort(jj)) * k) // len(jj), k - 1)
        grp = bx * k + by
        hc, ha = [], []
        for gidx in np.unique(grp):
            m = grp == gidx
            hc.append(cells[m][np.argmax(areas[m])]); ha.append(areas[m].sum())
        return np.array(hc), np.array(ha)

    def elem_cells(self, e):
        if not hasattr(self, '_ecache'):
            self._ecache = {}
        if e['name'] not in self._ecache:
            f = self.g.fp(e['ref'])
            l = (self.nL - 1) if f['side'] else 0
            self._ecache[e['name']] = self.pad_cells(f, e.get('pads'), l) + (l,)
        return self._ecache[e['name']]

    def layer_field(self, T, l):
        out = np.full(self.cid.shape, np.nan)
        m = self.cid >= 0
        out[m] = T[self.cid[m] * self.nL + l]
        return out

    # -- copper Joule heat ---------------------------------------------------
    def joule_map(self, inject):
        """Heat (W per board node) of a DC current distribution at 20 C.
        inject: list of (ref, [pad numbers], amps); amps sum to zero, all on one net."""
        key = tuple((r, tuple(p), round(i, 9)) for r, p, i in inject)
        if key in self._joule:
            return self._joule[key]
        g, P, nL, nc = self.g, self.P, self.nL, self.nc
        nets = set()
        src = []
        for ref, pads, amps in inject:
            f = g.fp(ref)
            if f is None:
                continue
            for p in f['pads']:
                if p['num'] in pads:
                    nets.add(p['net'])
            src.append((f, pads, amps))
        if len(nets) != 1 or len(src) < 2:
            self._joule[key] = None
            return None
        net = nets.pop()
        ss, nx, ny = g.ss, g.nx, g.ny
        bsub = g.board()
        rows, cols, vals, tags = [], [], [], []
        has = np.zeros(self.nb, bool)
        for l in range(nL):
            cu = g.net_copper(net, l) & bsub
            if not cu.any():
                continue
            st = cu_weight(cu) * g.t_cu[l] / P.rho_cu + 1e-9
            gx, gy = face_conductance(st, ss, nx, ny)
            for ia, ib, gg in ((self.cid[:, :-1], self.cid[:, 1:], gx), (self.cid[:-1, :], self.cid[1:, :], gy)):
                m = (ia >= 0) & (ib >= 0) & (gg > 1e-3)
                rows.append(ia[m] * nL + l); cols.append(ib[m] * nL + l); vals.append(gg[m])
                tags.append(np.full(int(m.sum()), -1))
            cid = self.cid[block_mean(cu.astype(float), ss) > 0]
            has[cid[cid >= 0] * nL + l] = True
        for vi, v in enumerate(g.vias):
            if v['net'] != net:
                continue
            c = self.cell_at(v['x'], v['y'])
            if c < 0:
                continue
            r = v['drill'] / 2 * 1e-3
            Ab = math.pi * ((r + P.plating) ** 2 - r ** 2)
            conn = g.via_layers(v)
            for a, b in zip(conn, conn[1:]):
                Lz = sum(g.t_cu[l] / 2 + g.t_diel[l] + g.t_cu[l + 1] / 2 for l in range(a, b))
                rows.append(np.array([c * nL + a])); cols.append(np.array([c * nL + b]))
                vals.append(np.array([Ab / (P.rho_cu * Lz)]))
                tags.append(np.array([vi]))
                has[c * nL + a] = has[c * nL + b] = True
        b = np.zeros(self.nb)
        for f, pads, amps in src:
            cells, areas, lays = [], [], []
            for p in f['pads']:
                if p['num'] in pads:
                    for l, (cc, aa) in p['cells'].items():
                        cid = self.cid.ravel()[cc]
                        m = cid >= 0
                        cells.append(cid[m] * nL + l); areas.append(aa[m])
            if not cells:
                continue
            cells, areas = np.concatenate(cells), np.concatenate(areas)
            np.add.at(b, cells, amps * areas / areas.sum())
            has[cells] = True
        idx = np.nonzero(has)[0]
        loc = -np.ones(self.nb, int)
        loc[idx] = np.arange(len(idx))
        r, c, v, tg = np.concatenate(rows), np.concatenate(cols), np.concatenate(vals), np.concatenate(tags)
        m = (loc[r] >= 0) & (loc[c] >= 0)
        r, c, v, tg = loc[r[m]], loc[c[m]], v[m], tg[m]
        n = len(idx)
        Gm = sp.coo_matrix((v, (r, c)), shape=(n, n))
        Gm = Gm + Gm.T
        Gm = (sp.diags(np.asarray(Gm.sum(1)).ravel() + 1e-6) - Gm).tocsc()
        V = sla.splu(Gm, permc_spec='MMD_AT_PLUS_A').solve(b[idx])
        q = v * (V[r] - V[c]) ** 2
        heat = np.zeros(self.nb)
        np.add.at(heat, idx[r], q / 2)
        np.add.at(heat, idx[c], q / 2)
        tot = float(q.sum())
        Iin = sum(a for _, _, a in src if a > 0)
        self._joule[key] = heat
        # detail for breakdowns: in-plane heat per node, heat per via (W at the injected amps, 20 C)
        ip = tg < 0
        heat_ip = np.zeros(self.nb)
        np.add.at(heat_ip, idx[r[ip]], q[ip] / 2)
        np.add.at(heat_ip, idx[c[ip]], q[ip] / 2)
        vh = {}
        for t_, q_, a_, b_ in zip(tg[~ip], q[~ip], idx[r[~ip]], idx[c[~ip]]):
            vh.setdefault(int(t_), [0.0, a_, b_])[0] += float(q_)
        if not hasattr(self, 'jdetail'):
            self.jdetail = {}
        self.jdetail[key] = dict(net=net, R=tot / max(Iin, 1e-9) ** 2, inplane=heat_ip,
                                 vias={k: (w, a, b) for k, (w, a, b) in vh.items()})
        print('    copper path on %-8s %.3f mOhm (%s)' % (net, 1e3 * tot / max(Iin, 1e-9) ** 2,
                                                       ' '.join(sorted({r for r, _, a in inject}))[:60]))
        return heat


# ---------------------------------------------------------------------------
#  Solving
# ---------------------------------------------------------------------------
class Drive:
    """Everything that changes with the operating point: element powers (each a
    function of its junction / pad temperature), wire currents and far-end
    temperatures, copper current distributions, air speed, ambient, sun."""

    def __init__(self, d):
        self.__dict__.update(d)


class Solver:
    def __init__(self, model):
        self.m = model

    # boundary heat loss (W per node) and its secant conductance
    def boundary(self, T, dv):
        m = self.m
        nL, nc = m.nL, m.nc
        Ta = dv.Ta
        TaK = Ta + 273.15
        out_idx, out_G = [], []
        for fc in m.faces:
            side, idx, area = fc['side'], fc['idx'], fc['area']
            Ts = T[idx]
            dT = Ts - Ta
            if getattr(dv, 'h_fixed', None) is not None:     # analytic checks: given h, no radiation
                out_idx.append(idx); out_G.append(area * dv.h_fixed[side])
                continue
            hn = h_plate_natural(dT, Ta, m.L_nat, up=fc['up'])
            v = dv.v_top if side == 0 else dv.v_bot
            hf = dv.turb * h_plate_forced(v, Ta, m.L_flow, float(np.mean(np.abs(dT))))
            hc = fc['mult'] * (hn ** 3 + hf ** 3) ** (1 / 3.)
            TsK = Ts + 273.15
            eps = fc['eps'] or (m.P.emissivity if side == 0 else (m.P.emissivity_bot or m.P.emissivity))
            hr = eps * SIGMA * (TsK ** 2 + TaK ** 2) * (TsK + TaK)
            out_idx.append(idx); out_G.append(area * (hc + hr))
        for w in m.wires:
            Tw = T[w['nodes']]
            dT = Tw - Ta
            # motor wires run out along the arms under the props; battery leads stay near the frame centre
            hc = h_cyl(dv.v_wire if w['kind'] == 'motor' else dv.v_top, w['Do'], dT, Ta, dv.turb)
            TwK = Tw + 273.15
            hr = 0.9 * SIGMA * (TwK ** 2 + TaK ** 2) * (TwK + TaK)
            per_len = 1.0 / (w['rins'] + 1.0 / ((hc + hr) * math.pi * w['Do']))
            out_idx.append(w['nodes']); out_G.append(per_len * w['dx'])
        return np.concatenate(out_idx), np.concatenate(out_G)

    def sources(self, T, dv):
        """Heat input (W per node) at temperature field T, plus fixed-temperature
        (wire far end) conductances and their right-hand side."""
        m = self.m
        nL = m.nL
        q = np.zeros(m.N)
        pw = {}
        for e in m.topo['elements']:
            f = m.g.fp(e['ref'])
            if f is None:
                continue
            fn = dv.power.get(e['name'], 0.0)
            if e['name'] in m.junc:
                Tj = T[m.junc[e['name']]]
                p = fn(Tj) if callable(fn) else fn
                q[m.junc[e['name']]] += p
            else:
                cells, areas, l = m.elem_cells(e)
                if len(cells) == 0:
                    continue
                Tp = float(np.average(T[cells * nL + l], weights=areas))
                p = fn(Tp) if callable(fn) else fn
                np.add.at(q, cells * nL + l, p * areas / areas.sum())
            pw[e['name']] = p
        # copper I^2 R
        pj = 0.0
        for wgt, inj in dv.joule:
            hm = m.joule_map(inj)
            if hm is not None:
                h = wgt * hm * (1 + m.P.alpha_cu * (T[:m.nb] - 20))
                q[:m.nb] += h
                pj += h.sum()
        pw['copper I2R'] = pj
        self.qjoule = q[:m.nb].copy() if pj else None
        # sun on the top
        if dv.solar > 0:      # projected (plan) area of the top, components included
            qs = m.P.absorptivity * dv.solar * m.solar_area
            q[m.solar_idx] += qs
            pw['sun'] = float(qs.sum())
        # wires: Joule heat, far end
        gfix = np.zeros(m.N)
        tfix = np.zeros(m.N)
        pwire = 0.0
        for w in m.wires:
            I = dv.wire_current.get(w['name'], 0.0)
            Tw = T[w['nodes']]
            pl = I ** 2 * m.P.rho_cu * (1 + m.P.alpha_cu * (Tw - 20)) / w['Acu'] * w['dx']
            q[w['nodes']] += pl
            pwire += pl.sum()
            last = w['nodes'][-1]
            gfix[last] += w['gend']
            tfix[last] += w['gend'] * dv.wire_far.get(w['name'], dv.Ta)
        pw['wires I2R'] = pwire
        return q, gfix, tfix, pw

    def factor(self, Hdiag, extra_diag=None):
        t0 = time.time()
        A = self.m.G + sp.diags(Hdiag + (extra_diag if extra_diag is not None else 0))
        lu = sla.splu(A.tocsc(), permc_spec='MMD_AT_PLUS_A')
        self.t_factor = time.time() - t0
        return lu

    def steady(self, dv, T0=None, tol=2e-3, verbose=True, reuse=False):
        """reuse: start from the last call's factorisation (refactored only if
        the surface conductances drift > 25 %): for sweeps of nearby cases."""
        m = self.m
        T = np.full(m.N, dv.Ta + 30.0) if T0 is None else T0.copy()
        lu, Hlin = (self._fact if reuse and getattr(self, '_fact', None) else (None, None))
        t0 = time.time()
        nfac = 0
        for it in range(200):
            bidx, bG = self.boundary(T, dv)
            q, gfix, tfix, pw = self.sources(T, dv)
            Hnow = np.zeros(m.N)
            np.add.at(Hnow, bidx, bG)
            if lu is None or (np.max(np.abs(Hnow[bidx] - Hlin[bidx]) / Hlin[bidx]) > 0.25 and nfac < 4):
                Hlin = Hnow.copy()
                lu = self.factor(Hlin, gfix)
                nfac += 1
            # A T = q + Hlin Ta + tfix - (Hnow - Hlin)(T - Ta)
            rhs = q + Hlin * dv.Ta + tfix - (Hnow - Hlin) * (T - dv.Ta)
            Tn = lu.solve(rhs)
            if not np.all(np.isfinite(Tn)) or Tn.max() > T_RUNAWAY:
                # losses grow with temperature faster than the board can shed them
                self.runaway = True
                T = np.minimum(np.nan_to_num(Tn, nan=T_RUNAWAY, posinf=T_RUNAWAY), T_RUNAWAY)
                print('  steady: NO STEADY STATE below %.0f C (thermal runaway / far beyond ratings)' % T_RUNAWAY)
                self.balance = dict(power_in=np.nan, convection_radiation=np.nan, into_wire_far_ends=np.nan, error=np.nan)
                return T, pw
            dmax = np.max(np.abs(Tn - T))
            T = T + 0.85 * (Tn - T) if it > 0 else Tn
            if dmax < tol:
                break
        self.runaway = False
        self._fact = (lu, Hlin)
        self.check_balance(T, dv, pw)
        if verbose:
            print('  steady: %d iterations, %d factorisations (%.1f s each), %.1f s' % (
                it + 1, nfac, self.t_factor, time.time() - t0))
        return T, pw

    def check_balance(self, T, dv, pw):
        m = self.m
        bidx, bG = self.boundary(T, dv)
        out = float(np.sum(bG * (T[bidx] - dv.Ta)))
        wend = sum(w['gend'] * (T[w['nodes'][-1]] - dv.wire_far.get(w['name'], dv.Ta)) for w in m.wires)
        pin = sum(v for v in pw.values())
        # heat the wires hand to the board through their pads = their I2R - their own losses to air and far ends
        wn = np.concatenate([w['nodes'] for w in m.wires]) if m.wires else np.zeros(0, int)
        wout = float(np.sum((bG * (T[bidx] - dv.Ta))[np.isin(bidx, wn)]))
        self.balance = dict(power_in=pin, convection_radiation=out, into_wire_far_ends=wend,
                            wires_into_board=pw.get('wires I2R', 0.0) - wout - wend,
                            error=pin - out - wend)

    def transient(self, segments, T0, dt=0.1, record=None):
        """segments: list of (duration s, Drive).  Implicit Euler, one
        factorisation; boundary/nonlinear terms lagged one step."""
        m = self.m
        T = T0.copy()
        self.runaway = False
        self.peak = (-np.inf, 0.0, T0.copy(), {}, segments[0][1])
        # linearise the boundary at the initial field with the fastest airflow in the profile
        dvs = [d for _, d in segments]
        fast = max(dvs, key=lambda d: d.v_top)
        bidx, bG = self.boundary(T + 10.0, fast)
        Hlin = np.zeros(m.N)
        np.add.at(Hlin, bidx, bG)
        gfix_all = None
        hist = []
        t = 0.0
        t0 = time.time()
        q, gfix, tfix, pw = self.sources(T, dvs[0])
        lu = self.factor(Hlin + m.C / dt, gfix)
        for dur, dv in segments:
            nstep = max(1, int(round(dur / dt)))
            for k in range(nstep):
                bidx, bG = self.boundary(T, dv)
                Hnow = np.zeros(m.N)
                np.add.at(Hnow, bidx, bG)
                q, gfix2, tfix, pw = self.sources(T, dv)
                rhs = m.C / dt * T + q + Hlin * dv.Ta + tfix - (Hnow - Hlin) * (T - dv.Ta)
                T = lu.solve(rhs)
                t += dt
                if not np.all(np.isfinite(T)) or T.max() > T_RUNAWAY:
                    print('  transient: runaway past %.0f C at t = %.1f s, stopped' % (T_RUNAWAY, t))
                    T = np.minimum(np.nan_to_num(T, nan=T_RUNAWAY, posinf=T_RUNAWAY), T_RUNAWAY)
                    self.runaway = True
                    return T, hist
                if record:
                    r = record(T)
                    hist.append((t, r, sum(pw.values()), dv.label))
                    if not (r[0] <= self.peak[0]):
                        self.peak = (r[0], t, T.copy(), pw, dv)
        print('  transient: %.0f s simulated in %d steps of %.2f s, %.1f s wall' % (t, len(hist), dt, time.time() - t0))
        return T, hist


# ---------------------------------------------------------------------------
#  Reporting
# ---------------------------------------------------------------------------
def summarize(model, T, topo):
    g, nL = model.g, model.nL
    rows = []
    for e in topo['elements']:
        f = g.fp(e['ref'])
        if f is None:
            continue
        cells, areas, l = model.elem_cells(e)
        if len(cells) == 0:
            continue
        Tp = T[cells * nL + l]
        Tj = T[model.junc[e['name']]] if e['name'] in model.junc else float(Tp.max())
        rows.append(dict(name=e['name'], ref=e['ref'], kind=e.get('kind', ''), side='B' if f['side'] else 'F',
                         T_pad_mean=float(np.average(Tp, weights=areas)), T_pad_max=float(Tp.max()), T_j=float(Tj),
                         T_limit=e.get('tmax')))
    board = T[:model.nb]
    lay = {g.cu_names[l]: (float(np.nanmin(board[l::nL])), float(np.nanmax(board[l::nL]))) for l in range(nL)}
    wires = {w['name']: float(T[w['nodes']].max()) for w in model.wires}
    return rows, lay, wires


def hotspots(model, q, n=6, sep=1.5):
    """The most concentrated copper I^2 R heat: local maxima of W/cm2 (per
    layer, per cell), at least sep mm apart, with the heat within 1 mm and the
    nearest parts."""
    if q is None:
        return []
    g, nL = model.g, model.nL
    A = (g.d * 1e-3) ** 2 * 1e4                        # cm2 per cell
    dens = q / A
    jj, ii = model.cpos
    x = g.x0 + (ii + 0.5) * g.d
    y = g.y0 + (jj + 0.5) * g.d
    out, taken = [], []
    for k in np.argsort(-dens):
        c, l = divmod(int(k), nL)
        if dens[k] <= 0 or len(out) >= n:
            break
        if any((x[c] - a) ** 2 + (y[c] - b) ** 2 < sep ** 2 for a, b in taken):
            continue
        taken.append((x[c], y[c]))
        near = (x - x[c]) ** 2 + (y - y[c]) ** 2 < 1.0
        w1 = float(q.reshape(-1, nL)[near].sum())
        refs = sorted(g.fps, key=lambda f: (f['x'] - x[c]) ** 2 + (f['y'] - y[c]) ** 2)[:3]
        out.append(dict(layer=g.cu_names[l], x=float(x[c]), y=float(y[c]), W_cm2=float(dens[k]), W_1mm=w1,
                        near=[f['ref'] for f in refs]))
    return out


def plot_maps(model, T, topo, rows, path, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    g, nL = model.g, model.nL
    ext = (g.x0, g.x0 + g.nx * g.d, g.y0 + g.ny * g.d, g.y0)
    fields = [model.layer_field(T, l) for l in range(nL)]
    vmin = min(np.nanmin(f) for f in fields); vmax = max(np.nanmax(f) for f in fields)
    ncol = 3 if nL > 4 else nL
    nrow = int(math.ceil(nL / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 4.3 * nrow + 0.6), squeeze=False)
    for l in range(nrow * ncol):
        ax = axs.flat[l]
        if l >= nL:
            ax.axis('off'); continue
        im = ax.imshow(fields[l], extent=ext, cmap='inferno', vmin=vmin, vmax=vmax, interpolation='nearest')
        ax.set_title('%s  %.1f-%.1f C' % (g.cu_names[l], np.nanmin(fields[l]), np.nanmax(fields[l])), fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=axs, shrink=0.8, label='C')
    fig.suptitle(title, fontsize=10)
    fig.savefig(path + '_layers.png', dpi=110)
    plt.close(fig)
    # top / bottom with parts
    hot = {r['ref']: r for r in rows}
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.2))
    for ax, l, side, nm in ((axs[0], 0, 0, 'top (%s), seen from above' % g.cu_names[0]),
                            (axs[1], nL - 1, 1, 'bottom (%s), seen from above' % g.cu_names[-1])):
        im = ax.imshow(fields[l], extent=ext, cmap='inferno', vmin=vmin, vmax=vmax, interpolation='nearest')
        for f in g.fps:
            if f['side'] != side or not f['pads']:
                continue
            ax.add_patch(Rectangle((f['bx'], f['by']), f['w'], f['h'], fill=False, lw=0.4, ec='#7fd0ff'))
            if f['ref'] in hot and hot[f['ref']]['kind'] in ('fet', 'ic', 'shunt', 'reg'):
                r = [x for x in rows if x['ref'] == f['ref']]
                tj = max(x['T_j'] for x in r)
                ax.text(f['x'], f['y'], '%s\n%.0f' % (f['ref'], tj), fontsize=5.5, ha='center', va='center',
                        color='white')
        ax.set_title(nm, fontsize=9)
        ax.set_xlabel('mm'); ax.set_aspect('equal')
    fig.colorbar(im, ax=axs, shrink=0.85, label='C (labels: junction / part max)')
    fig.suptitle(title, fontsize=10)
    fig.savefig(path + '_top_bottom.png', dpi=130)
    plt.close(fig)


def plot_transient(hist, path, title, names):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.array([h[0] for h in hist])
    rec = np.array([h[1] for h in hist])
    pw = np.array([h[2] for h in hist])
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    for k, nm in enumerate(names):
        a1.plot(t, rec[:, k], lw=1.2, label=nm)
    a1.set_ylabel('C'); a1.grid(alpha=0.3); a1.legend(fontsize=8)
    a1.set_title(title, fontsize=10)
    a2.plot(t, pw, color='k', lw=1)
    a2.set_ylabel('heat in, W'); a2.set_xlabel('s'); a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path + '_transient.png', dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
#  Driver
# ---------------------------------------------------------------------------
def run_case(model, topo, case, outdir, plots=True, dt=None):
    import cases
    os.makedirs(outdir, exist_ok=True)
    s = Solver(model)
    name = case['name']
    print('\n== %s: %s' % (name, case['desc']))
    t0 = time.time()
    res = dict(case=name, desc=case['desc'], board=model.g.name)
    if case.get('segments'):
        dt = dt or case.get('dt', 0.1)
        dv0 = case['init']
        T, pw0 = s.steady(dv0, verbose=True)
        if s.runaway:
            print('  the starting point has no steady state; transient skipped')
            res['runaway'] = True
            return res
        fets = [e['name'] for e in topo['elements'] if e.get('kind') == 'fet' and e['name'] in model.junc]
        others = [e['name'] for e in topo['elements'] if e.get('kind') != 'fet' and e['name'] in model.junc]
        nb, nL = model.nb, model.nL

        mcus = [e['name'] for e in topo['elements'] if e.get('kind') == 'mcu' and e['name'] in model.junc]

        def record(Tf):
            fj = [Tf[model.junc[n]] for n in fets]
            return [max(fj) if fj else np.nan, float(np.mean(fj)) if fj else np.nan,
                    float(Tf[:nb].max()), float(Tf[:nb].mean()),
                    max([Tf[w['nodes']].max() for w in model.wires] or [np.nan]),
                    max([Tf[model.junc[n]] for n in mcus] or [np.nan])]
        T, hist = s.transient(case['segments'], T, dt=dt, record=record)
        names = ['FET junction max', 'FET junction mean', 'board max', 'board mean', 'wire max', 'ESC MCU max']
        if plots:
            plot_transient(hist, os.path.join(outdir, name), '%s: %s' % (model.g.name, case['desc']), names)
        arr = np.array([h[1] for h in hist])
        res['transient'] = dict(peak={n: float(np.nanmax(arr[:, k])) for k, n in enumerate(names)},
                                t_peak=float(hist[int(np.nanargmax(arr[:, 0]))][0]) if fets else None,
                                final={n: float(arr[-1, k]) for k, n in enumerate(names)})
        with open(os.path.join(outdir, name + '_transient.csv'), 'w') as fh:
            fh.write('t_s,' + ','.join(n.replace(' ', '_') for n in names) + ',heat_W,segment\n')
            for h in hist:
                fh.write('%.2f,%s,%.3f,%s\n' % (h[0], ','.join('%.2f' % x for x in h[1]), h[2], h[3]))
        # report the field at the moment of the hottest FET junction
        _, tpk, T, pw, dvh = s.peak
        label = 'at t = %.1f s (hottest junction)' % tpk
    else:
        dv = dvh = case['drive']
        T, pw = s.steady(dv)
        res['balance'] = s.balance
        label = 'steady state'
        if s.runaway:
            res['runaway'] = True
            label = 'NO STEADY STATE (runaway; field shown is clipped)'
    rows, lay, wires = summarize(model, T, topo)
    s.sources(T, dvh)
    res['hotspots'] = hotspots(model, getattr(s, 'qjoule', None))
    for h in res['hotspots'][:4]:
        print('  copper hot spot: %s (%.1f, %.1f) mm, %.0f W/cm2, %.2f W within 1 mm, near %s' % (
            h['layer'], h['x'], h['y'], h['W_cm2'], h['W_1mm'], ' '.join(h['near'])))
    res.update(powers={k: float(v) for k, v in pw.items()}, parts=rows, layers=lay, wires=wires,
               total_heat_W=float(sum(pw.values())), runtime_s=time.time() - t0)
    print('  heat in (%s): ' % label + ', '.join('%s %.2f W' % (k, v) for k, v in cases.group_powers(pw).items()))
    fr = [r for r in rows if r['kind'] == 'fet']
    if fr:
        fr.sort(key=lambda r: -r['T_j'])
        print('  FET junctions: max %.1f C (%s), min %.1f C;  limit %s C' % (
            fr[0]['T_j'], fr[0]['name'], fr[-1]['T_j'], fr[0]['T_limit']))
    over = sorted([r for r in rows if r['T_limit'] and r['T_j'] > r['T_limit']], key=lambda r: r['T_limit'] - r['T_j'])
    res['over_limit'] = [r['name'] for r in over]
    if over:
        print('  OVER RATING: ' + ', '.join('%s %.0f>%g' % (r['name'], r['T_j'], r['T_limit']) for r in over[:12]) +
              (' (+%d more)' % (len(over) - 12) if len(over) > 12 else ''))
    oth = sorted([r for r in rows if r['kind'] != 'fet'], key=lambda r: -r['T_j'])[:6]
    if oth:
        print('  hottest other parts: ' + ', '.join('%s %.1f' % (r['name'], r['T_j']) for r in oth))
    print('  board: ' + ', '.join('%s %.1f-%.1f' % (k, a, b) for k, (a, b) in lay.items()))
    if wires:
        print('  wires (hottest point): ' + ', '.join('%s %.0f' % (k, v) for k, v in sorted(wires.items())[:3]) + ' ...')
    if 'balance' in res:
        bl = res['balance']
        print('  energy balance: in %.3f W, to air %.3f W, into wire ends %.3f W, error %.2e W; wires put %.2f W into the board' % (
            bl['power_in'], bl['convection_radiation'], bl['into_wire_far_ends'], bl['error'], bl.get('wires_into_board', 0)))
    with open(os.path.join(outdir, name + '.json'), 'w') as fh:
        json.dump(res, fh, indent=1)
    with open(os.path.join(outdir, name + '_parts.csv'), 'w') as fh:
        fh.write('name,ref,kind,side,T_pad_mean_C,T_pad_max_C,T_junction_C,T_limit_C,power_W\n')
        for r in sorted(rows, key=lambda r: -r['T_j']):
            fh.write('%s,%s,%s,%s,%.2f,%.2f,%.2f,%s,%.4f\n' % (r['name'], r['ref'], r['kind'], r['side'], r['T_pad_mean'],
                                                             r['T_pad_max'], r['T_j'], r['T_limit'] or '', pw.get(r['name'], 0)))
    if plots:
        plot_maps(model, T, topo, rows, os.path.join(outdir, name), '%s  %s  (%s)' % (model.g.name, case['desc'], label))
    print('  wrote %s/%s.*  (%.1f s)' % (os.path.relpath(outdir, os.getcwd()), name, time.time() - t0))
    run_case.last = dict(T=T, solver=s, drive=dvh, powers=pw)     # for scripts that post-process the field
    return res


def main(argv=None):
    import cases
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board', nargs='?')
    ap.add_argument('--case', default='full-50C-wash-sun',
                    help='comma list of <load>-<ambient>-<air>-<sun> names, a transient profile, or a set (see --list)')
    ap.add_argument('--profile', default='auto', help='part mapping: auto, %s' % ', '.join(cases.PROFILES))
    ap.add_argument('--cell', type=float, default=0.2, help='grid cell, mm (default 0.2)')
    ap.add_argument('--inner-oz', type=float, help='override inner copper weight, oz')
    ap.add_argument('--outer-oz', type=float, help='override outer copper weight, oz')
    ap.add_argument('--stack', help='override dielectric thicknesses, mm, top to bottom: e.g. 0.0994,0.5,0.2,0.5,0.0994')
    ap.add_argument('--losses', help='FET loss table (default ../losses.csv if present)')
    ap.add_argument('--emissivity', type=float)
    ap.add_argument('--fr4-xy', type=float, help='FR-4 in-plane conductivity W/mK (default 0.3)')
    ap.add_argument('--via-fill', type=float, help='via fill conductivity W/mK (0 air, 0.5 epoxy)')
    ap.add_argument('--dt', type=float, help='transient step, s (default: per profile, 0.05-0.25)')
    ap.add_argument('--out', help='output directory (default out/thermal/<board>/)')
    ap.add_argument('--no-plots', action='store_true')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)
    if a.list:
        cases.describe()
        return
    if not a.board:
        ap.error('board file required')
    P = Params
    P.cell_mm = a.cell
    P.ss = max(2, int(round(a.cell / 0.025 / 2)) * 2)
    P.inner_oz, P.outer_oz = a.inner_oz, a.outer_oz
    P.stack = [float(x) for x in a.stack.split(',')] if a.stack else None
    if a.emissivity is not None:
        P.emissivity = a.emissivity
    if a.fr4_xy is not None:
        P.k_fr4_xy = a.fr4_xy
    if a.via_fill is not None:
        P.k_via_fill = a.via_fill
    t0 = time.time()
    g = load_kicad(a.board, P)
    prof = cases.detect(g) if a.profile == 'auto' else a.profile
    losses = cases.Losses(a.losses or os.path.join(HERE, '..', 'losses.csv'))
    topo = cases.topology(prof, g)
    print('  profile %s: %d heat sources, %d wires; FET losses: %s' % (prof, len(topo['elements']), len(topo['wires']), losses.describe()))
    model = Model(g, topo, P)
    outdir = a.out or os.path.join(REPO, 'out', 'thermal', g.name)
    results = []
    for cname in cases.expand(a.case, prof):
        case = cases.make_case(cname, prof, topo, losses)
        results.append(run_case(model, topo, case, outdir, plots=not a.no_plots, dt=a.dt))
    if len(results) > 1:
        print('\n== summary (%s)' % g.name)
        print('  %-34s %8s %8s %9s %8s' % ('case', 'heat W', 'FET Tj', 'board max', 'limit'))
        for r in results:
            if 'parts' not in r:
                print('  %-34s   no steady starting point (runaway)' % r['case'])
                continue
            fr = [p for p in r['parts'] if p['kind'] == 'fet']
            tj = r['transient']['peak']['FET junction max'] if 'transient' in r else max([p['T_j'] for p in fr] or [np.nan])
            print('  %-34s %8.2f %8.1f %9.1f %8s %s' % (r['case'], r['total_heat_W'], tj,
                                                       max(b for a_, b in r['layers'].values()),
                                                       fr[0]['T_limit'] if fr else '', 'RUNAWAY' if r.get('runaway') else ''))
        with open(os.path.join(outdir, 'summary.json'), 'w') as fh:
            json.dump(results, fh, indent=1)
    print('\n  total %.1f s' % (time.time() - t0))
    return results


if __name__ == '__main__':
    main()
