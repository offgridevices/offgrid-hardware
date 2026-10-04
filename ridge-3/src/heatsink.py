# -*- coding: utf-8 -*-
"""The ESC's heatsink: a machined aluminium plate under the ESC, a gap pad
between them, fins underneath.  One source for its CAD (STEP, the gap pad's
die-cut outline), its drawing, and the thermal model (sim/stack.py).

    python3.12 src/heatsink.py [board.kicad_pcb] [out_dir]
        into out_dir (default ../mechanical): the STEP (zipped) and an STL,
        the gap pad's DXF, the drawing, two 3D views and a JSON summary.
        Needs pcbnew, and CadQuery 2.x for the CAD files (CADQUERY_PYTHON=
        /path/to/python that has it, if this one does not)

make.py esc runs it whenever the board or PARAMS change.

The plate, from the board's own data (its routed bottom side and the
parts' heights in parts.HEIGHTS):

  * outline: the board's 36 mm square, PARAMS['inset'] inside it, rounded
  * top face PARAMS['gap'] below the ESC's bottom, set by four bosses round
    the mounting holes that the ESC is screwed down onto (the board's copper
    keep-out ring, bare laminate, takes them): the pad's squeeze is fixed by
    the machining, not by rubber grommets
  * a pocket over every part on the ESC's bottom, as deep as its maximum
    height (the pad drapes over it at the same squeeze); a part too tall for
    that and PARAMS['floor'] of metal under it gets a hole in the pad
    instead, and a window through the base if it needs one
  * a notch open to the rear edge at each battery pad: the leads are
    soldered from below
  * straight fins underneath along the board's front-rear axis (the air in
    forward flight), feet round the holes as long as the fins: the stack
    stands on the frame on them

Coordinates: board-centre mm with KiCad's axes (x right, y towards the
rear, i.e. down the page); z = 0 at the ESC's bottom face, negative below.
The STEP is in the same place as the board's own STEP once that is moved to
the board's centre; its y axis is KiCad's flipped (CAD convention, y up).
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(os.path.dirname(HERE), 'esc', 'ridge3-esc.kicad_pcb')
OUT = os.path.join(os.path.dirname(HERE), 'mechanical')
NAME = 'ridge3-esc-heatsink'

PARAMS = dict(
    # 6061-T6, black anodized (JLCCNC: 6061 with Type II black anodize)
    material='Aluminium 6061-T6, black anodized (Type II)',
    k=167.0,                    # W/m K, 6061-T6
    density=2.70,               # g/cm3
    eps=0.85,                   # black anodize, emissivity (ASSUMPTION, 0.8-0.9)
    inset=0.3,                  # mm inside the board's edge
    corner_r=1.0,               # outline corner radius
    gap=1.25,                   # mm, ESC bottom face to the plate's top face (the pad's squeezed thickness)
    base=2.3,                   # mm, the plate under the fins
    floor=0.8,                  # least metal under a pocket (JLCCNC's recommended wall)
    clear=0.2,                  # mm over a part that has a hole in the pad
    body_margin=0.25,           # a part's pocket: its pads' extent grown by this
    pocket_r=0.5,               # inside corner radius of the pockets (JLCCNC: R0.5 to 3 mm deep)
    level_step=0.4,             # pockets within this of a deeper one are cut as deep (fewer levels)
    hole_d=2.4,                 # M2 clearance
    boss_d=5.0,                 # bosses the ESC sits on: inside the board's 2.6 mm copper keep-out
    foot_d=6.0,                 # feet under the holes, as long as the fins
    pad_keepout=3.0,            # radius round each hole the pad leaves bare (boss + 0.5 mm)
    notch_w=4.5,                # battery-lead notch width (12-14 AWG silicone lead, 2.9-3.6 mm)
    fins=dict(h=8.0, t=1.0, gap=2.0),   # mm: height, thickness, slot between fins
    bypass=0.5,                 # share of the free stream that gets between the fins (ASSUMPTION)
    pad=dict(maker='T-Global Technology', mpn='TG-A6200-40-40-1.5', dk='1168-TG-A6200-40-40-1.5-ND',
             t=1.5, density=3.1, k_sheet=6.2,     # mm, g/cm3, W/m K (the data sheet's headline figure)
             note='TG-A6200, 6.2 W/m K, 50 Shore 00, -50..180 C, >= 10 kV/mm, 40 x 40 mm sheet: '
                  'cut to the outline in the DXF'),
)

# T-Global TG-A6200 data sheet (version 21, 2026-02-07), "Contact Pressure,
# Thermal Impedance, and Deflection": read off the charts' points, at 10,
# 30 and 50 psi.  The charts cover 0.5, 1.0 and 3.0 mm pads; other
# thicknesses are interpolated linearly between them.  The impedance is
# what the pad does between two plates, contact resistance included: about
# half of what its 6.2 W/m K headline gives.
PAD_CHART = dict(
    psi=(10.0, 30.0, 50.0),
    deflection={0.5: (6.0, 10.0, 12.0), 1.0: (10.0, 24.0, 35.0), 3.0: (13.0, 34.0, 46.0)},   # %
    impedance={0.5: (0.376, 0.310, 0.279), 1.0: (0.481, 0.445, 0.412), 3.0: (1.326, 1.029, 0.883)},  # C in2 / W
)
IN2 = 0.0254 ** 2


def _by_thickness(table, t):
    ts = sorted(table)
    if t <= ts[0]:
        return table[ts[0]]
    for a, b in zip(ts, ts[1:]):
        if t <= b:
            w = (t - a) / (b - a)
            return tuple(x + w * (y - x) for x, y in zip(table[a], table[b]))
    return table[ts[-1]]


def pad_state(t=None, gap=None):
    """The pad squeezed from t to gap: (deflection %, pressure psi, thermal
    impedance m2 K / W), from the maker's charts.  Outside the charts'
    pressures it stops: the design must sit inside them."""
    P = PARAMS
    t = t or P['pad']['t']
    gap = gap or P['gap']
    d = 100.0 * (t - gap) / t
    defl = _by_thickness(PAD_CHART['deflection'], t)
    imp = _by_thickness(PAD_CHART['impedance'], t)
    psi = PAD_CHART['psi']
    if not defl[0] <= d <= defl[-1]:
        raise SystemExit('heatsink: the pad squeezed %.0f %% is outside its charts (%.0f-%.0f %%)'
                         % (d, defl[0], defl[-1]))
    for i in range(len(psi) - 1):
        if d <= defl[i + 1]:
            w = (d - defl[i]) / (defl[i + 1] - defl[i])
            p = psi[i] + w * (psi[i + 1] - psi[i])
            z = imp[i] + w * (imp[i + 1] - imp[i])
            return d, p, z * IN2
    raise AssertionError


def fin_pitch():
    f = PARAMS['fins']
    return f['t'] + f['gap']


def fin_xs(half):
    """Fin centre lines: as many as fit with the outer fins' faces at least
    half a slot inside the outline, symmetric about the board's centre."""
    f = PARAMS['fins']
    p = fin_pitch()
    n = int((2 * (half - f['gap'] / 2) - f['t']) // p) + 1
    x0 = -(n - 1) * p / 2
    return [round(x0 + i * p, 4) for i in range(n)]


def _polys(g):
    """A shapely (multi)polygon as JSON: [{'ext': [...], 'int': [[...], ...]}]."""
    from shapely.geometry.polygon import orient
    def r(cs):
        """Rounded to 0.1 um, no point repeated (CAD needs real edges)."""
        out = []
        for x, y in cs:
            p = [round(x, 4), round(y, 4)]
            if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 2e-4:
                out.append(p)
        if out[0] != out[-1]:
            out.append(out[0])
        return out

    def flat(g):
        if g.geom_type == 'Polygon':
            return [] if g.is_empty or g.area < 1e-6 else [orient(g.simplify(1e-2))]
        return [p for h in getattr(g, 'geoms', []) for p in flat(h)]
    return [dict(ext=r(p.exterior.coords), int=[r(i.coords) for i in p.interiors]) for p in flat(g)]


def _shape(polys):
    from shapely.geometry import Polygon, MultiPolygon
    ps = [Polygon(p['ext'], p['int']) for p in polys]
    return MultiPolygon(ps) if len(ps) != 1 else ps[0]


def features(board=BOARD):
    """The heatsink's geometry from the routed board: board-centre mm (y
    towards the rear), depths below the plate's top face.

    The pockets come as depth levels: level d is everything cut at least d
    deep, its parts' pockets merged where the metal between them, or
    between one and the plate's edge or a notch, would be thinner than
    PARAMS['floor'], and its corners rounded to the cutter (PARAMS['pocket_r']).
    The deepest level, as deep as the base, is the windows through it."""
    import pcbnew, pcb, circuit, parts
    from shapely.geometry import box, Point
    from shapely.ops import unary_union
    P = PARAMS
    q = 8
    b = pcbnew.LoadBoard(board)
    comps = {c.ref: c for c in circuit.build('esc')}
    half = pcb.HALF - P['inset']
    mm = pcbnew.ToMM
    holes, notches, pockets, missing = [], [], [], []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        x, y = mm(fp.GetPosition().x) - pcb.CX, mm(fp.GetPosition().y) - pcb.CY
        c = comps.get(ref)
        if c is not None and c.part == 'HOLE':
            holes.append((round(x, 4), round(y, 4)))
            continue
        if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in fp.Pads()):
            # a lead through the board, soldered from below: a notch from it
            # to the nearest edge
            if not abs(y) > abs(x):
                raise SystemExit('heatsink: %s: notches run to the front or rear edge only' % ref)
            notches.append(dict(ref=ref, x=round(x, 4), y=round(y, 4), dir=1 if y > 0 else -1, w=P['notch_w']))
            continue
        if fp.GetLayer() != pcbnew.B_Cu:
            continue
        pads = list(fp.Pads())
        h = parts.PARTS.get(c.part, {}).get('h') if c is not None else None
        if h is None:
            missing.append(ref)
            continue
        xs = [mm(v) - pcb.CX for p in pads for v in (p.GetBoundingBox().GetLeft(), p.GetBoundingBox().GetRight())]
        ys = [mm(v) - pcb.CY for p in pads for v in (p.GetBoundingBox().GetTop(), p.GetBoundingBox().GetBottom())]
        body = [min(xs), min(ys), max(xs), max(ys)]
        m = P['body_margin']
        rect = [body[0] - m, body[1] - m, body[2] + m, body[3] + m]
        # at least a cutter's width across, so the rounding keeps it
        for i in (0, 1):
            short = 2 * P['pocket_r'] + 0.2 - (rect[i + 2] - rect[i])
            if short > 0:
                rect[i] -= short / 2; rect[i + 2] += short / 2
        room = P['base'] - P['floor']
        if h <= room:
            kind, depth = 'drape', h                     # pad over it, same squeeze
        else:
            depth = h - P['gap'] + P['clear']            # a hole in the pad, and clearance
            kind = 'clear' if depth <= room else 'window'
            depth = P['base'] if kind == 'window' else max(depth, 0.0)
        pockets.append(dict(ref=ref, part=c.part, body=[round(v, 4) for v in body],
                            rect=[round(v, 4) for v in rect], h=h, depth=round(depth, 4), kind=kind))
    if missing:
        raise SystemExit('heatsink: no height (parts.HEIGHTS) for the bottom parts %s' % sorted(missing))
    if len(holes) != 4:
        raise SystemExit('heatsink: expected 4 mounting holes, found %d' % len(holes))
    pockets.sort(key=lambda q_: q_['ref'])
    notches.sort(key=lambda q_: q_['ref'])
    # depth levels: from the deepest down, each pocket within level_step of
    # a level already made is cut that deep (still floor of metal under it)
    made = []
    for q_ in sorted(pockets, key=lambda q_: -q_['depth']):
        lv = next((d for d in made if d - q_['depth'] <= P['level_step']), None)
        if lv is None:
            made.append(q_['depth'])
        q_['depth'] = lv if lv is not None else q_['depth']
    holes.sort()

    outline = box(-half, -half, half, half).buffer(-P['corner_r'], quad_segs=q).buffer(P['corner_r'], quad_segs=q)
    cuts = [unary_union([box(n['x'] - n['w'] / 2, min(n['y'], n['dir'] * (half + 2)), n['x'] + n['w'] / 2,
                             max(n['y'], n['dir'] * (half + 2))), Point(n['x'], n['y']).buffer(n['w'] / 2, quad_segs=q)])
            for n in notches]
    through = unary_union(cuts + [box(-half - 5, -half - 5, half + 5, half + 5).difference(outline)])
    w, r = P['floor'] / 2, P['pocket_r']
    levels = []
    for d in sorted({q_['depth'] for q_ in pockets if q_['depth'] > 0}, reverse=True):
        # each pocket's corners rounded to the cutter, then merged with its
        # neighbours (and the edge, the notches) where the metal between
        # would be thinner than floor
        mine = [box(*q_['rect']).buffer(-r, quad_segs=q).buffer(r, quad_segs=q) for q_ in pockets if q_['depth'] >= d]
        R = unary_union(mine + [through]).buffer(w, quad_segs=q).buffer(-w, quad_segs=q)
        R = R.intersection(outline).difference(unary_union(cuts))
        # what is left of it round a pocket (the merge also breaks the
        # plate's corners at the notches: not a pocket)
        R = unary_union([g for g in getattr(R, 'geoms', [R]) if g.area > 1e-3 and any(g.intersects(m_) for m_ in mine)])
        for q_ in pockets:
            if q_['depth'] >= d and not R.union(unary_union(cuts)).buffer(1e-3).contains(box(*q_['body'])):
                raise SystemExit('heatsink: %s does not fit its pocket after rounding' % q_['ref'])
        levels.append(dict(depth=d, through=d >= P['base'], polys=_polys(R)))
    allp = unary_union([_shape(l_['polys']) for l_ in levels])
    plate = outline.difference(unary_union(cuts))
    for hx, hy in holes:
        plate = plate.difference(Point(hx, hy).buffer(P['hole_d'] / 2, quad_segs=q))
    pad = outline.difference(unary_union(cuts))
    for hx, hy in holes:
        pad = pad.difference(Point(hx, hy).buffer(P['pad_keepout'], quad_segs=q))
    # a hole in the pad over each part it does not drape: the pocket round it
    for q_ in pockets:
        if q_['kind'] != 'drape':
            lvl = _shape(next(l_ for l_ in levels if l_['depth'] == q_['depth'])['polys'])
            for comp in getattr(lvl, 'geoms', [lvl]):
                if comp.intersects(box(*q_['body'])):
                    pad = pad.difference(comp)
    pad = pad.buffer(-0.3, quad_segs=q).buffer(0.3, quad_segs=q)
    # the fins' footprint: straight along y, clipped to the outline.  A fin
    # that crosses a foot runs into it; one that would pass it closer than a
    # slot's width is cut back a slot's width from it; whole fins are taken
    # away along a notch; no stub shorter than 4 mm is left
    fin = P['fins']
    xs_ = fin_xs(half)
    fins = []
    for x in xs_:
        g = box(x - fin['t'] / 2, -half - 1, x + fin['t'] / 2, half + 1).intersection(outline)
        for hx, hy in holes:
            clear = abs(x - hx) - fin['t'] / 2 - P['foot_d'] / 2
            if -fin['t'] / 2 < clear < fin['gap']:
                g = g.difference(Point(hx, hy).buffer(P['foot_d'] / 2 + fin['gap'], quad_segs=q))
        fins.append(g)
    fins = unary_union(fins)
    for n in notches:
        hit = [x for x in xs_ if abs(x - n['x']) < n['w'] / 2 + fin['t'] / 2]
        if hit:
            y0 = n['y'] - n['dir'] * n['w'] / 2
            fins = fins.difference(box(min(hit) - fin['t'], min(y0, n['dir'] * (half + 2)),
                                       max(hit) + fin['t'], max(y0, n['dir'] * (half + 2))))
    fins = fins.difference(unary_union(cuts))
    fins = unary_union([g for g in getattr(fins, 'geoms', [fins]) if g.area >= 4 * fin['t']])
    return dict(half=half, corner_r=P['corner_r'], gap=P['gap'], base=P['base'], holes=holes,
                notches=notches, pockets=pockets, levels=levels, plate=_polys(plate), pad=_polys(pad),
                pocketed=_polys(allp), fins=dict(P['fins'], xs=xs_, polys=_polys(fins)),
                hole_d=P['hole_d'], boss_d=P['boss_d'], foot_d=P['foot_d'], pad_keepout=P['pad_keepout'])


def masks(f, X, Y):
    """Where the plate, the pad and the pockets are, at points (X, Y)
    (board-centre mm): dict(plate, pad, contact, t) with t the base's
    thickness (mm) at each point of the plate.  contact: the pad between
    bare board and the plate's top face (not over a part or a pocket, which
    the model leaves out)."""
    import numpy as np
    from shapely import contains_xy
    plate = contains_xy(_shape(f['plate']), X, Y)
    t = np.where(plate, f['base'], 0.0)
    for l_ in sorted(f['levels'], key=lambda l_: l_['depth']):
        inside = contains_xy(_shape(l_['polys']), X, Y)
        if l_['through']:
            plate &= ~inside
        t = np.where(inside, f['base'] - l_['depth'], t)
    pad = contains_xy(_shape(f['pad']), X, Y) & plate
    contact = pad & ~contains_xy(_shape(f['pocketed']), X, Y)
    return dict(plate=plate, pad=pad, contact=contact, t=np.where(plate, t, 0.0))


def thermal(f=None):
    """What sim/stack.py needs besides the geometry."""
    P = PARAMS
    d, psi, r = pad_state()
    return dict(k=P['k'], eps=P['eps'], pad_r=r, pad_t=P['gap'], pad_psi=psi, pad_deflection=d,
                fins=dict(P['fins']), pitch=fin_pitch(), bypass=P['bypass'],
                length=2 * (f['half'] if f else 18.0 - P['inset']))


# ---------------------------------------------------------------- CAD
def solid(f):
    """The plate as a CadQuery solid: CAD axes (y = -KiCad y), z = 0 at the
    ESC's bottom face."""
    import cadquery as cq
    P = PARAMS
    half, gap, base = f['half'], f['gap'], f['base']
    fin = f['fins']
    z_top, z_bot = -gap, -gap - base
    z_tip = z_bot - fin['h']
    plate = (cq.Workplane('XY').workplane(offset=z_bot).rect(2 * half, 2 * half).extrude(base)
             .edges('|Z').fillet(f['corner_r']))
    # bosses up to the board, feet down to the fins' tips
    for hx, hy in f['holes']:
        plate = plate.union(cq.Workplane('XY').workplane(offset=z_top).center(hx, -hy)
                            .circle(f['boss_d'] / 2).extrude(gap))
        plate = plate.union(cq.Workplane('XY').workplane(offset=z_tip).center(hx, -hy)
                            .circle(f['foot_d'] / 2).extrude(fin['h']))
    # the fins' footprint
    flip = lambda ring: [(x, -y) for x, y in ring[:-1]]
    for poly in fin['polys']:
        plate = plate.union(cq.Workplane('XY').workplane(offset=z_tip).polyline(flip(poly['ext'])).close()
                            .extrude(fin['h'] + 0.01))
    # the pocket levels from the top face (the deepest: windows through the base)
    for l_ in f['levels']:
        d = base + 0.02 if l_['through'] else l_['depth']
        z0 = z_top - d
        for poly in l_['polys']:
            flip = lambda ring: [(x, -y) for x, y in ring[:-1]]
            cut = cq.Workplane('XY').workplane(offset=z0).polyline(flip(poly['ext'])).close().extrude(d + 0.01)
            for hole in poly['int']:
                cut = cut.cut(cq.Workplane('XY').workplane(offset=z0 - 0.01).polyline(flip(hole)).close()
                              .extrude(d + 0.03))
            plate = plate.cut(cut)
    # battery-lead notches, through everything; the fins they cross go
    # whole across the notch's length (no slivers)
    for n in f['notches']:
        w = n['w'] / 2
        far = n['y'] + n['dir'] * (half + 1 - abs(n['y']))
        cy_, ln = -(n['y'] + far) / 2, abs(far - n['y'])
        cut = (cq.Workplane('XY').workplane(offset=z_tip - 0.1).center(n['x'], cy_).rect(2 * w, ln)
               .extrude(gap + base + fin['h'] + 0.2))
        cut = cut.union(cq.Workplane('XY').workplane(offset=z_tip - 0.1).center(n['x'], -n['y'])
                        .circle(w).extrude(gap + base + fin['h'] + 0.2))
        plate = plate.cut(cut)
    for hx, hy in f['holes']:
        plate = plate.cut(cq.Workplane('XY').workplane(offset=z_tip - 0.1).center(hx, -hy)
                          .circle(f['hole_d'] / 2).extrude(gap + base + fin['h'] + 0.2))
    return plate


def write_pad_dxf(f, path):
    """The gap pad's die-cut outline (mm, CAD axes, seen from above)."""
    import ezdxf
    ezdxf.options.write_fixed_meta_data_for_testing = True     # no time stamp or random GUID: same pad, same bytes
    doc = ezdxf.new('R2010', units=4)
    msp = doc.modelspace()
    for poly in f['pad']:
        for ring in [poly['ext']] + poly['int']:
            msp.add_lwpolyline([(x, -y) for x, y in ring[:-1]], close=True)
    doc.saveas(path)


def write_cad(f, out):
    """STEP and STL of the plate, DXF of the pad, the 3D views; returns the
    plate's volume (mm3) and the pad's area (mm2)."""
    import cadquery as cq
    from cadquery.occ_impl.shapes import Face, Wire
    os.makedirs(out, exist_ok=True)
    s = solid(f)
    cq.exporters.export(s, os.path.join(out, NAME + '.step'))
    stl = os.path.join(out, NAME + '.stl')
    cq.exporters.export(s, stl, tolerance=0.02, angularTolerance=0.1)
    render_views(stl, os.path.join(out, NAME + '-views.png'))
    write_pad_dxf(f, os.path.join(out, 'ridge3-esc-gap-pad.dxf'))
    area = 0.0
    for poly in f['pad']:
        ring = lambda pts: Wire.makePolygon([cq.Vector(x, -y, 0) for x, y in pts[:-1]], close=True)
        area += Face.makeFromWires(ring(poly['ext']), [ring(i) for i in poly['int']]).Area()
    return s.val().Volume(), area


def render_views(stl, png):
    """Two views of the plate from its STL (VTK, off screen, as CadQuery
    installs it): from above, black anodized as ordered, and from below in
    grey, where black would hide the fins.  CAD +y is the quad's front."""
    import vtk
    r = vtk.vtkSTLReader(); r.SetFileName(stl)
    n = vtk.vtkPolyDataNormals(); n.SetInputConnection(r.GetOutputPort()); n.SetFeatureAngle(30); n.SplittingOn()
    fe = vtk.vtkFeatureEdges(); fe.SetInputConnection(r.GetOutputPort())
    fe.BoundaryEdgesOff(); fe.FeatureEdgesOn(); fe.SetFeatureAngle(40); fe.ManifoldEdgesOff(); fe.NonManifoldEdgesOff()
    w = vtk.vtkRenderWindow(); w.SetOffScreenRendering(1); w.SetSize(2400, 1000); w.SetMultiSamples(8)
    for x0, colour, cam_pos in ((0.0, (0.20, 0.21, 0.23), (-55, -75, 70)), (0.5, (0.55, 0.57, 0.60), (-45, 80, -70))):
        m = vtk.vtkPolyDataMapper(); m.SetInputConnection(n.GetOutputPort())
        a = vtk.vtkActor(); a.SetMapper(m)
        p = a.GetProperty(); p.SetColor(*colour); p.SetAmbient(0.25); p.SetDiffuse(0.75)
        p.SetSpecular(0.35); p.SetSpecularPower(25)
        em = vtk.vtkPolyDataMapper(); em.SetInputConnection(fe.GetOutputPort()); em.ScalarVisibilityOff()
        ea = vtk.vtkActor(); ea.SetMapper(em); ea.GetProperty().SetColor(0.55, 0.57, 0.6)
        ren = vtk.vtkRenderer(); ren.SetViewport(x0, 0, x0 + 0.5, 1)
        ren.AddActor(a); ren.AddActor(ea)
        ren.SetBackground(1, 1, 1); ren.SetBackground2(0.88, 0.9, 0.93); ren.GradientBackgroundOn()
        for pos, k in (((40, -60, 90), 0.9), ((-60, 40, -40), 0.45)):
            l = vtk.vtkLight(); l.SetPosition(*pos); l.SetFocalPoint(0, 0, 0); l.SetIntensity(k); ren.AddLight(l)
        l = vtk.vtkLight(); l.SetLightTypeToHeadlight(); l.SetIntensity(0.35); ren.AddLight(l)
        cam = ren.GetActiveCamera()
        cam.SetFocalPoint(0, 0, -5.5); cam.SetPosition(*cam_pos); cam.SetViewUp(0, 0, 1)
        ren.ResetCamera(); cam.Zoom(0.95)
        w.AddRenderer(ren)
    w.Render()
    f = vtk.vtkWindowToImageFilter(); f.SetInput(w); f.ReadFrontBufferOff(); f.Update()
    out = vtk.vtkPNGWriter(); out.SetFileName(png); out.SetInputConnection(f.GetOutputPort()); out.Write()


# ---------------------------------------------------------------- drawing
def _patch(polys, mirror=False, **kw):
    """Matplotlib patch of JSON polygons in CAD axes (y = -KiCad y); mirror:
    seen from below (x flipped)."""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    sx = -1 if mirror else 1
    verts, codes = [], []
    for poly in polys:
        for ring in [poly['ext']] + poly['int']:
            pts = [(sx * x, -y) for x, y in ring]
            verts += pts
            codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(verts, codes), **kw)


def drawing(f, out, summary):
    """A one-page drawing for the CNC order (A3): top and bottom views, a
    section, the gap pad, and the notes that need a drawing (the bosses'
    height over the pad face sets the pad's squeeze)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    P = PARAMS
    half, fin = f['half'], f['fins']
    fig = plt.figure(figsize=(16.54, 11.69))
    ax_t = fig.add_axes([0.03, 0.32, 0.31, 0.60])
    ax_b = fig.add_axes([0.36, 0.32, 0.31, 0.60])
    ax_s = fig.add_axes([0.70, 0.62, 0.28, 0.28])
    ax_p = fig.add_axes([0.70, 0.30, 0.28, 0.28])
    ax_n = fig.add_axes([0.03, 0.02, 0.94, 0.26]); ax_n.axis('off')
    shade = {}
    deps = sorted(l_['depth'] for l_ in f['levels'] if not l_['through'])
    for i, d in enumerate(deps):
        shade[d] = plt.cm.Blues(0.35 + 0.5 * i / max(1, len(deps) - 1))

    def frame(ax, title):
        ax.set_xlim(-half - 2, half + 2); ax.set_ylim(-half - 2, half + 2); ax.set_aspect('equal')
        ax.tick_params(labelsize=7); ax.set_title(title, fontsize=9)
        ax.grid(lw=0.2, color='0.8')

    # top: the pad face, the pocket levels (deeper darker), the windows
    frame(ax_t, 'TOP (pad face), seen from above.  Front of the quad up.')
    ax_t.add_patch(_patch(f['plate'], fc='#d9d9d9', ec='k', lw=0.8))
    for l_ in sorted(f['levels'], key=lambda l_: l_['depth']):
        ax_t.add_patch(_patch(l_['polys'], fc='w' if l_['through'] else shade[l_['depth']], ec='k', lw=0.5))
    for hx, hy in f['holes']:
        ax_t.add_patch(Circle((hx, -hy), f['boss_d'] / 2, fc='#8c8c8c', ec='k', lw=0.8))
        ax_t.add_patch(Circle((hx, -hy), f['hole_d'] / 2, fc='w', ec='k', lw=0.8))
    for d, c in shade.items():
        ax_t.add_patch(Rectangle((0, 0), 0, 0, fc=c, ec='k', label='pocket %.2f deep' % d))
    ax_t.add_patch(Rectangle((0, 0), 0, 0, fc='w', ec='k', label='window through the base'))
    ax_t.add_patch(Rectangle((0, 0), 0, 0, fc='#8c8c8c', ec='k', label='boss, %.2f above the pad face' % f['gap']))
    ax_t.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2, fontsize=7, frameon=False)
    # bottom: fins and feet, seen from below
    frame(ax_b, 'BOTTOM (fins), seen from below (x mirrored).  Front up.')
    ax_b.add_patch(_patch(f['plate'], mirror=True, fc='#efefef', ec='k', lw=0.8))
    ax_b.add_patch(_patch(fin['polys'], mirror=True, fc='#8c8c8c', ec='k', lw=0.4))
    for hx, hy in f['holes']:
        ax_b.add_patch(Circle((-hx, -hy), f['foot_d'] / 2, fc='#8c8c8c', ec='k', lw=0.8))
        ax_b.add_patch(Circle((-hx, -hy), f['hole_d'] / 2, fc='w', ec='k', lw=0.8))
    # section at y = 0
    z_top, z_bot = -f['gap'], -f['gap'] - f['base']
    ax_s.set_title("SECTION at y = 0; z from the ESC's bottom face (mm)", fontsize=9)
    ax_s.add_patch(Rectangle((-half - 0.3, 0), 2 * half + 0.6, 1.6, fc='#2e7d32', ec='k', lw=0.5, alpha=0.5))
    ax_s.add_patch(Rectangle((-half, z_top), 2 * half, f['gap'], fc='#4fa3e0', ec='none', alpha=0.4))
    ax_s.add_patch(Rectangle((-half, z_bot), 2 * half, f['base'], fc='#d9d9d9', ec='k', lw=0.8))
    for x in fin['xs']:
        ax_s.add_patch(Rectangle((x - fin['t'] / 2, z_bot - fin['h']), fin['t'], fin['h'], fc='#d9d9d9', ec='k', lw=0.5))
    ax_s.text(0, 0.8, 'ESC, 1.6 mm', ha='center', va='center', fontsize=8)
    ax_s.text(0, z_top / 2, 'gap pad, %.2f mm squeezed' % f['gap'], ha='center', va='center', fontsize=7)
    ax_s.set_xlim(-half - 2, half + 2); ax_s.set_ylim(z_bot - fin['h'] - 1.5, 3); ax_s.set_aspect('equal')
    ax_s.tick_params(labelsize=7)
    # the pad
    frame(ax_p, 'GAP PAD %s: cut to this outline (DXF)' % P['pad']['mpn'])
    ax_p.add_patch(_patch(f['pad'], fc='#4fa3e0', ec='k', lw=0.6))
    # notes
    d, psi, r = pad_state()
    pocket_refs = {}
    for q_ in f['pockets']:
        pocket_refs.setdefault((q_['kind'], q_['depth']), []).append(q_['ref'])
    groups = '; '.join('%s %s (%s)' % ('window through the base:' if k == 'window' else
                                         ('pocket %.2f deep, pad over:' % dep if k == 'drape' else
                                          'pocket %.2f deep, pad cut away:' % dep), '', ', '.join(v))
                       for (k, dep), v in sorted(pocket_refs.items(), key=lambda kv: -kv[0][1]))
    notes = [
        'Ridge 3 ESC heatsink.  %s.  The STEP (%s.step) is the master; this sheet gives what needs a drawing.' % (P['material'], NAME),
        'Outline %.1f x %.1f mm, R%.1f corners.  Base %.2f mm.  Fins %.1f thick, %.1f slots, %.1f tall, along the front-rear '
        'axis.  Bosses %s%.1f stand %.2f above the pad face; feet %s%.1f flush with the fin tips; holes %s%.1f through.' % (
            2 * half, 2 * half, f['corner_r'], f['base'], fin['t'], fin['gap'], fin['h'], u'\u00d8', f['boss_d'], f['gap'],
            u'\u00d8', f['foot_d'], u'\u00d8', f['hole_d']),
        'Pockets (one per part on the ESC\'s bottom, merged where the metal between would be under %.1f mm; inside corners '
        'R%.1f): %s.' % (P['floor'], P['pocket_r'], groups),
        'TOLERANCES: ISO 2768-m unless stated.  Boss top faces to the pad face: %.2f +/-0.05 (sets the pad\'s squeeze).  '
        'Pad face flatness 0.05.  Pocket depths +0.1/-0.' % f['gap'],
        'FINISH: black anodize (Type II) all over; boss tops and feet may be left bare (rack points).  Break sharp edges 0.2.',
        'GAP PAD: %s %s (DigiKey %s): %s.  Squeezed %.1f -> %.2f mm (%.0f %%, about %.0f psi on the maker\'s chart, '
        'about %.0f N on the board): %.2f C in2/W.' % (P['pad']['maker'], P['pad']['mpn'], P['pad']['dk'], P['pad']['note'],
                                                     P['pad']['t'], f['gap'], d, psi, summary.get('pad_force_N', 0), r / IN2),
        'MASS: plate %.1f g (from the model), pad %.1f g.  The stack stands %.1f mm higher on the frame (pad, base, fins).' % (
            summary.get('plate_g', float('nan')), summary.get('pad_g', float('nan')), f['gap'] + f['base'] + fin['h']),
    ]
    import textwrap
    y = 1.0
    for s_ in notes:
        lines = textwrap.wrap(s_, 210)
        ax_n.text(0, y, '\n'.join(lines), fontsize=8.5, va='top', transform=ax_n.transAxes, family='DejaVu Sans')
        y -= 0.075 * len(lines) + 0.04
    os.makedirs(out, exist_ok=True)
    pdf = os.path.join(out, NAME + '.pdf')
    fig.savefig(pdf, metadata={'CreationDate': None})      # the same bytes from the same drawing
    fig.savefig(os.path.join(out, NAME + '.png'), dpi=110)
    plt.close(fig)
    return pdf


def summary_of(f, plate_mm3, pad_mm2):
    P = PARAMS
    d, psi, r = pad_state()
    return dict(features=f, params=P, plate_g=round(plate_mm3 * 1e-3 * P['density'], 2),
                pad_g=round(pad_mm2 * P['pad']['t'] * 1e-3 * P['pad']['density'], 2),
                pad_area_mm2=round(pad_mm2, 1), pad_deflection_pct=round(d, 1), pad_psi=round(psi, 1),
                pad_impedance_m2KW=float('%.4g' % r),
                pad_force_N=round(psi * 6894.76 * pad_mm2 * 1e-6))


def _cad(f, out):
    """write_cad in an interpreter that has CadQuery: this one, or
    CADQUERY_PYTHON's."""
    try:
        import cadquery  # noqa: F401
        return write_cad(f, out)
    except ImportError:
        pass
    import subprocess, tempfile
    py = os.environ.get('CADQUERY_PYTHON')
    if not py:
        raise SystemExit('heatsink: the STEP needs CadQuery 2.x: install it, or set CADQUERY_PYTHON '
                         'to a python that has it')
    with tempfile.TemporaryDirectory(prefix='heatsink-') as tmp:
        fj = os.path.join(tmp, 'features.json')
        with open(fj, 'w') as fh:
            json.dump(f, fh)
        r = subprocess.run([py, os.path.abspath(__file__), '--cad', fj, out], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('heatsink: CadQuery failed:\n' + r.stderr[-3000:])
    v = json.loads(r.stdout.strip().splitlines()[-1])
    return v['volume'], v['pad_area']


def build(board=BOARD, out=OUT):
    """Everything into out: the STEP, zipped (CadQuery writes it at ~7 MB,
    every facet of the pockets' rounding a face), an STL (for a viewer or a
    printed test fit), the 3D views, the pad's DXF, the drawing, and the
    JSON that current() checks."""
    import stable
    f = features(board)
    vol, area = _cad(f, out)
    stable.zip_one(os.path.join(out, NAME + '.step'), os.path.join(out, NAME + '-step.zip'))
    s = summary_of(f, vol, area)
    with open(os.path.join(out, NAME + '.json'), 'w') as fh:
        json.dump(s, fh, indent=1, sort_keys=True)
    drawing(f, out, s)
    return s


def current(out=OUT, board=BOARD):
    """True if the committed outputs were made from this board and these
    parameters (their JSON has the same features and PARAMS)."""
    p = os.path.join(out, NAME + '.json')
    if not all(os.path.exists(os.path.join(out, x)) for x in
               (NAME + '.json', NAME + '-step.zip', NAME + '.stl', NAME + '-views.png', NAME + '.pdf',
                'ridge3-esc-gap-pad.dxf')):
        return False
    s = json.load(open(p))
    f = json.loads(json.dumps(features(board)))
    return s.get('features') == f and s.get('params') == json.loads(json.dumps(PARAMS))


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    if sys.argv[1:2] == ['--cad']:
        f = json.load(open(sys.argv[2]))
        vol, area = write_cad(f, sys.argv[3])
        print(json.dumps(dict(volume=vol, pad_area=area)))
        raise SystemExit
    s = build(*sys.argv[1:])
    print('heatsink: plate %.1f g, pad %.1f g (%.0f mm2), pad %.0f %% squeezed at %.0f psi (%d N), %.2e m2 K/W'
          % (s['plate_g'], s['pad_g'], s['pad_area_mm2'], s['pad_deflection_pct'], s['pad_psi'],
             s['pad_force_N'], s['pad_impedance_m2KW']))
