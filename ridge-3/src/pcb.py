# -*- coding: utf-8 -*-
"""Shared board construction for both boards: outline, stackup, rules,
footprints from the circuit, placement, zones, keepouts and text.

Coordinates everywhere in the placement tables are millimetres from the
board centre, x to the right, y towards the REAR (KiCad's y points down the
screen, so the front of the quad is at the top of every plot).
"""
import os
import pcbnew
import circuit, parts

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
MM = pcbnew.FromMM
CX, CY = 100.0, 100.0            # board centre on KiCad's page
HALF = 18.0                      # 36 mm square (SpeedyBee F405 AIO V2 size), 25.5 mm holes
HOLE = 12.75                     # 25.5 mm pattern
HOLE_KEEPOUT_R = 3.1             # grommet flange + clearance, no copper
# Mounting: each 3.2 mm hole (an M2 soft-mount grommet's neck; the grommet
# turns it into M2) opens to its corner through a 2.5 mm slot along the
# diagonal, so the grommet slides in from outside instead of being pushed
# through.  The rubber neck squeezes through the narrower slot and seats
# in the hole.
HOLE_D = 3.2
SLOT_W = 2.5
STD_FP = '/usr/share/kicad/footprints'

def P(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))

def lib_path(lib):
    return os.path.join(V1, 'aio.pretty') if lib == 'aio' else os.path.join(STD_FP, lib + '.pretty')

_fp_cache = {}
def load_fp(fpid):
    lib, name = fpid.split(':')
    return pcbnew.FootprintLoad(lib_path(lib), name)

# Every copper layer a board here can have, top to bottom; cu_layers() keeps
# the ones a board has (4, 6 or 8).
CU_ALL = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.In5_Cu,
          pcbnew.In6_Cu, pcbnew.B_Cu]


def cu_layers(b):
    """The board's copper layers, top to bottom."""
    return [l for l in CU_ALL if b.IsLayerEnabled(l)]


def new_board(layers=4):
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(layers)
    ds = b.GetDesignSettings()
    # JLCPCB standard 4-layer capability: 0.09 mm (3.5 mil) tracks and gaps
    # on 1 oz outer copper; PCBWay's standard is 0.1 mm (4 mil).  Signals
    # use 0.1 mm, which both fabs build at standard price.  0.25/0.45 mm
    # vias are the smallest JLCPCB makes without surcharge.
    ds.m_TrackMinWidth = MM(0.1)
    ds.m_MinClearance = MM(0.1)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.25)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.2)        # JLCPCB: via hole to track 0.2 mm
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.1)
    ds.m_SolderMaskExpansion = MM(0.05)
    ds.m_SolderMaskMinWidth = MM(0.1)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(0.1)); nc.SetTrackWidth(MM(0.1))
    nc.SetViaDiameter(MM(0.45)); nc.SetViaDrill(MM(0.25))
    return b

# KiCad 10's Python bindings: once an item taken off a board is garbage
# collected, later LoadBoard() calls in the same process return broken
# objects.  Everything removed goes through here and is kept alive.
_REMOVED = []

def remove(b, item):
    b.Remove(item)
    _REMOVED.append(item)

def add_net(b, name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
    return n

# Every point of the outline where the slot meets the board's edge or the
# hole is rounded off with arcs tangent to both sides, so the outline is
# one smooth curve with no sharp point anywhere.  Where the slot opens
# through the edge (a 45 degree point before): a tight arc off the edge
# (SLOT_TIP's first radius) sweeping on into a wide one along the slot's
# wall (its second), taking only SLOT_TIP's third figure of the straight
# edge, so the production panel's tabs keep their room between the slot and
# the edge pads.  Where the walls meet the hole: SLOT_HOLE_R, small, so the
# lip that holds the grommet in the hole stays.
SLOT_TIP = (0.3, 2.0, 0.95)       # mm: radius at the edge, radius along the wall, length of edge taken
SLOT_HOLE_R = 0.3


def _unit(x, y):
    import math
    l = math.hypot(x, y)
    return x / l, y / l


def _arc_mid(c, r, p, q):
    """The mid-point of the shorter arc of radius r round c from p to q."""
    mx, my = _unit((p[0] - c[0]) + (q[0] - c[0]), (p[1] - c[1]) + (q[1] - c[1]))
    return c[0] + r * mx, c[1] + r * my


def _fillet_compound(v, ue, uw, r1, r2, te):
    """Round the corner at v between an edge leaving along the unit
    direction ue and a wall leaving along uw: an arc of radius r1 tangent to
    the edge te from v, then an arc of radius r2, tangent to it and to the
    wall.  Returns [('arc', on edge, mid, joint), ('arc', joint, mid, on
    wall)]."""
    import math
    dot = ue[0] * uw[0] + ue[1] * uw[1]
    ne = _unit(uw[0] - dot * ue[0], uw[1] - dot * ue[1])     # into the corner, off the edge
    nw = _unit(ue[0] - dot * uw[0], ue[1] - dot * uw[1])     # into the corner, off the wall
    e = (v[0] + te * ue[0], v[1] + te * ue[1])
    c1 = (e[0] + r1 * ne[0], e[1] + r1 * ne[1])
    c2 = lambda t: (v[0] + t * uw[0] + r2 * nw[0], v[1] + t * uw[1] + r2 * nw[1])
    f = lambda t: math.hypot(c2(t)[0] - c1[0], c2(t)[1] - c1[1]) - (r2 - r1)
    # the wide arc holds the tight one inside it where they touch; of the
    # two places along the wall where that works, the far one (the wide arc
    # runs out along the wall)
    ts = [k * 0.001 for k in range(1, 20000)]
    roots = [(a, b) for a, b in zip(ts, ts[1:]) if f(a) * f(b) <= 0]
    if not roots:
        raise ValueError('no compound round for r %g / %g over %g mm' % (r1, r2, te))
    a, b = roots[-1]
    for _ in range(60):
        m = (a + b) / 2
        a, b = (a, m) if f(a) * f(m) <= 0 else (m, b)
    tw = (a + b) / 2
    w = (v[0] + tw * uw[0], v[1] + tw * uw[1])
    k = c2(tw)
    d = _unit(c1[0] - k[0], c1[1] - k[1])
    j = (k[0] + r2 * d[0], k[1] + r2 * d[1])
    return [('arc', e, _arc_mid(c1, r1, e, j), j), ('arc', j, _arc_mid(k, r2, j, w), w)]


def _slot(sx, sy):
    """One corner's mounting slot as a chain of points and arcs, from the
    vertical edge (x = +-HALF) round the hole to the horizontal edge
    (y = +-HALF), in board-centre mm: [('line', p0, p1) | ('arc', p0, mid,
    p1), ...], each item starting where the one before it ends."""
    import math
    r, a = HOLE_D / 2, SLOT_W / 2
    o = (sx * HOLE, sy * HOLE)
    d = (sx / math.sqrt(2), sy / math.sqrt(2))          # towards the corner
    n = (sx / math.sqrt(2), -sy / math.sqrt(2))         # across the slot, towards the vertical edge
    at = lambda t, k: (o[0] + t * d[0] + k * n[0], o[1] + t * d[1] + k * n[1])
    back = (-d[0], -d[1])
    chain = []
    # (side +1: the wall towards the vertical edge; -1: towards the horizontal one)
    walls = {}
    for side in (1, -1):
        # where the wall comes through the edge, and the arc there
        if side == 1:
            v, along = (sx * HALF, sy * HALF - sy * math.sqrt(2) * a), (0.0, -sy)
        else:
            v, along = (sx * HALF - sx * math.sqrt(2) * a, sy * HALF), (-sx, 0.0)
        tip = _fillet_compound(v, along, back, *SLOT_TIP)
        w = tip[-1][-1]
        # the arc between the wall and the hole: its centre SLOT_HOLE_R off
        # the wall on the board's side, SLOT_HOLE_R off the hole's edge
        q = SLOT_HOLE_R
        tc = math.sqrt((r + q) ** 2 - (a + q) ** 2)
        c = at(tc, side * (a + q))
        on_wall = at(tc, side * a)
        on_hole = (o[0] + (c[0] - o[0]) * r / (r + q), o[1] + (c[1] - o[1]) * r / (r + q))
        mx, my = (on_wall[0] - c[0]) + (on_hole[0] - c[0]), (on_wall[1] - c[1]) + (on_hole[1] - c[1])
        ml = math.hypot(mx, my)
        hmid = (c[0] + mx / ml * q, c[1] + my / ml * q)
        walls[side] = (tip, w, on_wall, hmid, on_hole)
    tip, w, on_wall, hmid, on_hole = walls[1]
    chain += tip + [('line', w, on_wall), ('arc', on_wall, hmid, on_hole)]
    far = (o[0] - r * d[0], o[1] - r * d[1])            # the hole's side away from the corner
    tip2, w2, on_wall2, hmid2, on_hole2 = walls[-1]
    chain += [('arc', on_hole, far, on_hole2), ('arc', on_hole2, hmid2, on_wall2), ('line', on_wall2, w2)]
    chain += _reverse(tip2)
    return chain


def _reverse(chain):
    return [(it[0],) + tuple(reversed(it[1:])) for it in reversed(chain)]


def outline_path():
    """The board outline, clockwise on screen from the top-left corner:
    a list of ('line', p0, p1) and ('arc', p0, mid, p1)."""
    chains = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = _slot(sx, sy)
        chains.append(_reverse(c) if (sx, sy) in ((1, -1), (-1, 1)) else c)
    path = []
    for i, c in enumerate(chains):
        path += c
        path.append(('line', c[-1][-1], chains[(i + 1) % 4][0][1]))
    return path


def arc_points(p0, pm, p1, n=24):
    """n + 1 points along the arc from p0 through pm to p1."""
    import math
    ax, ay = p0; bx, by = pm; cx_, cy_ = p1
    dd = 2 * (ax * (by - cy_) + bx * (cy_ - ay) + cx_ * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy_) + (bx * bx + by * by) * (cy_ - ay) + (cx_ * cx_ + cy_ * cy_) * (ay - by)) / dd
    uy = ((ax * ax + ay * ay) * (cx_ - bx) + (bx * bx + by * by) * (ax - cx_) + (cx_ * cx_ + cy_ * cy_) * (bx - ax)) / dd
    rad = math.hypot(ax - ux, ay - uy)
    a0 = math.atan2(ay - uy, ax - ux); am = math.atan2(by - uy, bx - ux); a1 = math.atan2(cy_ - uy, cx_ - ux)
    norm = lambda v: v % (2 * math.pi)
    span = norm(a1 - a0); via = norm(am - a0)
    if via > span:
        span -= 2 * math.pi
    return [(ux + rad * math.cos(a0 + span * k / n), uy + rad * math.sin(a0 + span * k / n)) for k in range(n + 1)]


def board_polygon(n_arc=24):
    """The board as a shapely polygon in board-centre mm (arcs as
    polylines)."""
    from shapely.geometry import Polygon
    ring = []
    for item in outline_path():
        if item[0] == 'line':
            ring.append(item[1])
        else:
            ring += arc_points(*item[1:], n=n_arc)[:-1]
    return Polygon(ring)


def redraw_outline(b):
    """The board's outline drawn again from outline_path() (a board built
    before the outline changed); nothing else on Edge.Cuts is kept."""
    for d in [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]:
        remove(b, d)
    outline(b)


def outline(b):
    for item in outline_path():
        if item[0] == 'line':
            s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(P(*item[1])); s.SetEnd(P(*item[2]))
        else:
            s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
            s.SetArcGeometry(P(*item[1]), P(*item[2]), P(*item[3]))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        b.Add(s)

def place_components(b, comps, placement):
    """placement: ref -> (x, y, rot, side)  side 'T' or 'B'."""
    allp = {**parts.PARTS, **parts.PADS}
    fps = {}
    for c in comps:
        pd = allp[c.part]
        fp = load_fp(pd['fp'])
        fp.SetReference(c.ref)
        fp.SetValue(pd.get('value', c.part))
        if 'lcsc' in pd:
            fp.SetField('LCSC', pd['lcsc'])
        # extra fields (LCSC number, generator tags) are data, not artwork
        for fld in fp.GetFields():
            if not (fld.IsReference() or fld.IsValue()):
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.F_Fab)
        b.Add(fp)
        # silkscreen carries no component outlines or designators on a
        # board this dense: move them to the fab (assembly drawing) layer
        fp.Reference().SetLayer(pcbnew.F_Fab)
        for it in fp.GraphicalItems():
            if it.GetLayer() == pcbnew.F_SilkS:
                it.SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            net = c.pins.get(pad.GetNumber())
            if net:
                pad.SetNet(add_net(b, net))
        if c.ref not in placement:
            raise KeyError('no placement for %s (%s)' % (c.ref, c.note))
        x, y, rot, side = placement[c.ref]
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fps[c.ref] = fp
    return fps

def zone(b, net, layer, poly, clearance=0.2, min_width=0.2, priority=0,
         thermal=True, name=None, spoke=0.3, gap=0.25):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    if net:
        z.SetNet(add_net(b, net))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in poly:
        ol.Append(MM(CX + x), MM(CY + y))
    z.SetLocalClearance(MM(clearance))
    z.SetMinThickness(MM(min_width))
    z.SetAssignedPriority(priority)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefSpokeWidth(MM(spoke)); z.SetThermalReliefGap(MM(gap))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z

def rule_area(b, poly, layers, tracks=True, vias=True, pads=False, pours=True, name=None):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in poly:
        ol.Append(MM(CX + x), MM(CY + y))
    z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowPads(pads); z.SetDoNotAllowZoneFills(pours)
    z.SetDoNotAllowFootprints(False)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z

def circle_poly(x, y, r, n=32):
    import math
    return [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def hole_keepouts(b, cu_layers):
    for sx in (-1, 1):
        for sy in (-1, 1):
            rule_area(b, circle_poly(sx * HOLE, sy * HOLE, HOLE_KEEPOUT_R), cu_layers,
                      tracks=True, vias=True, pads=False, pours=True, name='hole keepout')

# Mouse-bite tab zones (panel.py): along each edge, from the corner's slot
# to TAB_TO from the corner, TAB_DEPTH deep.  No part, track or via goes
# there, so the production panel always has room for its tabs clear of the
# slots and of the pads near the corners.
TAB_FROM, TAB_TO, TAB_DEPTH = 1.5, 7.0, 1.6


def tab_zones():
    """The eight tab zones as (x0, y0, x1, y1), board mm."""
    h, a, c, d = HALF, TAB_FROM, TAB_TO, TAB_DEPTH
    out = []
    for lo, hi in ((-h + a, -h + c), (h - c, h - a)):
        out += [(lo, -h, hi, -h + d), (lo, h - d, hi, h), (-h, lo, -h + d, hi), (h - d, lo, h, hi)]
    return out


def tab_keepouts(b, cu_layers):
    for x0, y0, x1, y1 in tab_zones():
        rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cu_layers, tracks=True, vias=True, pads=False,
                  pours=False, name='panel tab keepout')


def via(b, x, y, net, d=0.5, drill=0.25):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(drill))
    v.SetNet(add_net(b, net))
    v.SetIsFree(False)
    b.Add(v)
    return v

def track(b, pts, width, layer, net):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(MM(width))
        t.SetLayer(layer); t.SetNet(add_net(b, net))
        b.Add(t)

def text(b, s, x, y, size=0.8, layer=pcbnew.F_SilkS, rot=0, thick=0.15, bold=False, just=None):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick))
    t.SetTextAngleDegrees(rot)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Mask):
        t.SetMirrored(True)
    if just == 'left':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif just == 'right':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    b.Add(t)
    return t

def line(b, pts, layer, width=0.15):
    for a, c in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetLayer(layer); s.SetWidth(MM(width))
        b.Add(s)

def poly_shape(b, pts, layer, fill=True, width=0.0):
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_POLY)
    s.SetPolyPoints([P(x, y) for x, y in pts])
    s.SetLayer(layer); s.SetFilled(fill); s.SetWidth(MM(width))
    b.Add(s)
    return s

def netclass(b, name, nets, width, clearance=0.15, via_d=0.45, via_drill=0.25):
    ns = b.GetDesignSettings().m_NetSettings
    nc = pcbnew.NETCLASS(name)
    nc.SetTrackWidth(MM(width)); nc.SetClearance(MM(clearance))
    nc.SetViaDiameter(MM(via_d)); nc.SetViaDrill(MM(via_drill))
    ns.SetNetclass(name, nc)
    for n in nets:
        ns.SetNetclassPatternAssignment(n, name)
    ns.RecomputeEffectiveNetclasses() if hasattr(ns, 'RecomputeEffectiveNetclasses') else None
    for n in nets:
        ni = b.FindNet(n)
        if ni is not None:
            ni.SetNetClass(ns.GetNetClassByName(name))
    return nc

def usb_c_tie(b, fp, w=0.15, via_d=0.45, via_drill=0.25):
    """Join a USB-C receptacle's two D+ and two D- contacts.

    On the connector the four data contacts alternate D-, D+, D-, D+, so the
    pairs cannot both be joined on one layer.  D+ is joined on the top with a
    short jog past the pad ends; each D- contact drops through a via and the
    two vias are joined on the bottom.  Positions come from the pads, so
    this works at any placement or rotation."""
    pads = {p.GetNumber(): p for p in fp.Pads()}
    def c(n):
        q = pads[n].GetPosition(); return q.x / 1e6 - CX, q.y / 1e6 - CY
    ctr = fp.GetPosition(); cx, cy = ctr.x / 1e6 - CX, ctr.y / 1e6 - CY
    a6, b6, a7, b7 = c('A6'), c('B6'), c('A7'), c('B7')
    # unit vector from connector body towards the pad ends (inwards to the board)
    import math
    mx, my = (a6[0] + b6[0]) / 2 - cx, (a6[1] + b6[1]) / 2 - cy
    ln = math.hypot(mx, my); ux, uy = mx / ln, my / ln
    half = max(pads['A6'].GetSize().x, pads['A6'].GetSize().y) / 2e6
    end = lambda p, d: (p[0] + ux * (half + d), p[1] + uy * (half + d))
    net_p, net_m = pads['A6'].GetNetname(), pads['A7'].GetNetname()
    # D-: via just past each pad end, joined on B.Cu
    v1, v2 = end(b7, 0.35), end(a7, 0.35)
    for p, v in ((b7, v1), (a7, v2)):
        track(b, [p, v], w, pcbnew.F_Cu, net_m)
        via(b, v[0], v[1], net_m, via_d, via_drill)
    track(b, [v1, v2], w, pcbnew.B_Cu, net_m)
    # D+: jog on F.Cu clear of the D- vias
    j1, j2 = end(a6, 0.95), end(b6, 0.95)
    track(b, [a6, j1, j2, b6], w, pcbnew.F_Cu, net_p)

def pour_ground(path, layers, clearance=0.2):
    """Add ground fill to the given copper layers of a routed board, fill all
    zones and save.  Done after routing so the router never sees it."""
    b = pcbnew.LoadBoard(path)
    e = HALF - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for l in layers:
        zone(b, 'GND', l, full, clearance=clearance, name='GND fill', priority=0)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(path)
    return b

def drc(path, out_json):
    import subprocess, json
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all',
                    '--format', 'json', '-o', out_json, path], capture_output=True)
    r = json.load(open(out_json))
    errs = [v for v in r['violations'] if v['severity'] == 'error']
    warns = [v for v in r['violations'] if v['severity'] != 'error']
    return errs, warns, r['unconnected_items']

def tidy_tracks(path, snap=0.005):
    """Clean the maze router's leftovers: track ends of one net on one layer
    that lie within `snap` mm of each other (or of a via of the net) are
    joined at one point, then segments that became zero-length and exact
    duplicates are dropped.  Freerouting fails to "normalize" a net with
    such geometry and hangs; KiCad accepts it, but it is not clean copper.
    Returns (ends moved, segments removed)."""
    from collections import defaultdict
    b = pcbnew.LoadBoard(path)
    S = int(snap * 1e6)
    tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
    vias = defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            q = t.GetPosition(); vias[t.GetNetname()].append((q.x, q.y))
    ends = defaultdict(list)             # (net, layer) -> [(track, 'start'|'end')]
    for t in tracks:
        ends[(t.GetNetname(), t.GetLayer())] += [(t, 's'), (t, 'e')]
    moved = 0
    for (net, layer), items in ends.items():
        pts = [((t.GetStart() if k == 's' else t.GetEnd()).x, (t.GetStart() if k == 's' else t.GetEnd()).y)
               for t, k in items]
        anchors = vias.get(net, [])
        parent = list(range(len(pts)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if pts[i] != pts[j] and abs(pts[i][0] - pts[j][0]) <= S and abs(pts[i][1] - pts[j][1]) <= S:
                    parent[find(i)] = find(j)
        clusters = defaultdict(list)
        for i in range(len(pts)):
            clusters[find(i)].append(i)
        for members in clusters.values():
            cand = [a for a in anchors if any(abs(a[0] - pts[i][0]) <= S and abs(a[1] - pts[i][1]) <= S for i in members)]
            if len(set(pts[i] for i in members)) < 2 and not cand:
                continue
            target = cand[0] if cand else max(set(pts[i] for i in members), key=lambda q: sum(pts[i] == q for i in members))
            for i in members:
                if pts[i] != target:
                    t, k = items[i]
                    (t.SetStart if k == 's' else t.SetEnd)(pcbnew.VECTOR2I(int(target[0]), int(target[1])))
                    moved += 1
    removed = 0
    seen = {}
    for t in tracks:
        a, e = t.GetStart(), t.GetEnd()
        if a.x == e.x and a.y == e.y:
            remove(b, t); removed += 1
            continue
        key = (t.GetNetname(), t.GetLayer(), tuple(sorted(((a.x, a.y), (e.x, e.y)))))
        if key in seen:
            keep = seen[key]
            if t.GetWidth() > keep.GetWidth():
                keep.SetWidth(t.GetWidth())
            remove(b, t); removed += 1
        else:
            seen[key] = t
    b.Save(path)
    return moved, removed


def dedupe_vias(path):
    """Freerouting sometimes drops a via right on top of an existing via of
    the same net.  Keep one of any pair whose holes would be closer than the
    hole-to-hole rule, and move every track end that sat on the removed via
    onto the survivor so nothing is left dangling."""
    b = pcbnew.LoadBoard(path)
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
    gone = {}
    for i, a in enumerate(vias):
        if i in gone:
            continue
        pa = a.GetPosition()
        for j in range(i + 1, len(vias)):
            if j in gone or vias[j].GetNetname() != a.GetNetname():
                continue
            pc = vias[j].GetPosition()
            d = ((pa.x - pc.x) ** 2 + (pa.y - pc.y) ** 2) ** 0.5 / 1e6
            if d < (a.GetDrillValue() + vias[j].GetDrillValue()) / 2e6 + 0.25:
                gone[j] = i
    for j, i in gone.items():
        pj, pi = vias[j].GetPosition(), vias[i].GetPosition()
        for t in tracks:
            if t.GetNetname() != vias[j].GetNetname():
                continue
            for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                q = get()
                if abs(q.x - pj.x) < 20000 and abs(q.y - pj.y) < 20000:
                    put(pcbnew.VECTOR2I(pi.x, pi.y))
    for j in sorted(gone, reverse=True):
        remove(b, vias[j])
    b.Save(path)
    return len(gone)

RULES = """(version 1)
# JLCPCB 4-layer limits the board-setup numbers cannot express on their own.
(rule "plated component hole to track"
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole' && B.Type == 'Track'")
  (constraint hole_clearance (min 0.28mm)))
# Every plane-net pad already has its own via into the plane; one thermal
# spoke from the surface fill is enough.
(rule "one spoke is enough"
  (constraint min_resolved_spokes 1))
"""

# JLCPCB via-in-pad (POFV, "Epoxy Filled & Capped", free on 6 layers): every
# via is filled, and holes drilled afterwards (unplated mounting slots,
# plated pads) keep 0.45 mm from them.  Boards that put vias in pads add
# this to their rules.
POFV_RULES = """# JLCPCB via-in-pad (POFV): ordered "Epoxy Filled & Capped", every via is
# filled; holes drilled afterwards (the unplated mounting holes and plated
# pads) keep 0.45 mm from them.
(rule "POFV to drilled holes"
  (condition "A.Type == 'Via' && B.Type == 'Pad'")
  (constraint hole_to_hole (min 0.45mm)))
"""


# JLCPCB's finest track and gap on multilayer boards, by copper weight (oz)
# (capabilities page, "Min. track width and spacing"): 1 oz 0.09 / 0.09 mm,
# 2 oz 0.15 / 0.15 mm.  The board-setup minimums cover 1 oz and less.
FAB_MIN = {0.5: 0.09, 1.0: 0.09, 2.0: 0.15}
# and its multilayer via minimum: a 0.15 mm hole in a 0.25 mm via (at its
# small-via surcharge)
FAB_MIN_DRILL, FAB_MIN_VIA = 0.15, 0.25


def copper_rules(inner_oz):
    """DRC rules holding the inner layers to the fab's finest track and gap
    for their copper weight; '' where the board-setup minimums do."""
    m = FAB_MIN[inner_oz]
    if m <= FAB_MIN[1.0]:
        return ''
    return ('# %g oz inner copper: JLCPCB etches it no finer than %.2f mm track and %.2f mm gap\n'
            '(rule "%g oz inner copper"\n'
            '  (layer inner)\n'
            '  (constraint track_width (min %.2fmm))\n'
            '  (constraint clearance (min %.2fmm)))\n' % (inner_oz, m, m, inner_oz, m, m))


def write_rules(board_path, extra=''):
    import os
    open(os.path.splitext(board_path)[0] + '.kicad_dru', 'w').write(RULES + extra)


# Stackups, 1.6 mm, 1 oz outer copper; inner copper per board (the ESC's
# inner planes carry the motor current: 1 oz; the FC: 1 oz, for spreading
# its supplies' heat).  4 layers: JLCPCB's standard JLC04161H-7628.  6 and
# 8 layers: nominal figures for the fab's standard 1.6 mm builds (nothing
# here needs controlled impedance; 8 layers of 1 oz leave 1.3 mm of glass).
# Mask and silk colours follow the OffGrid brand: Pitch ground (black
# mask), Bone type (white silk); ENIG keeps the QFN pads flat.
DIELECTRIC = {4: [('prepreg', 0.2104, '7628', 4.4), ('core', 1.065, 'FR4', 4.6), ('prepreg', 0.2104, '7628', 4.4)],
              6: [('prepreg', 0.1, 'FR4', 4.4), ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.45, 'FR4', 4.4),
                  ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.1, 'FR4', 4.4)],
              8: [('prepreg', 0.12, 'FR4', 4.4), ('core', 0.2, 'FR4', 4.6), ('prepreg', 0.23, 'FR4', 4.4),
                  ('core', 0.2, 'FR4', 4.6), ('prepreg', 0.23, 'FR4', 4.4), ('core', 0.2, 'FR4', 4.6),
                  ('prepreg', 0.12, 'FR4', 4.4)]}


CU_MM = {0.5: '0.0175', 1.0: '0.035', 2.0: '0.07'}


def stackup_text(n, inner_oz=0.5):
    cu = ['F.Cu'] + ['In%d.Cu' % i for i in range(1, n - 1)] + ['B.Cu']
    L = ['\t\t(stackup',
         '\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))',
         '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
         '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))']
    for k, name in enumerate(cu):
        outer = k in (0, n - 1)
        L.append('\t\t\t(layer "%s" (type "copper") (thickness %s))' % (name, '0.035' if outer else CU_MM[inner_oz]))
        if k < n - 1:
            kind, t, mat, er = DIELECTRIC[n][k]
            L.append('\t\t\t(layer "dielectric %d" (type "%s") (color "FR4 natural") (thickness %s) '
                     '(material "%s") (epsilon_r %s) (loss_tangent 0.02))' % (k + 1, kind, t, mat, er))
    L += ['\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))',
          '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))',
          '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))',
          '\t\t\t(copper_finish "ENIG")',
          '\t\t\t(dielectric_constraints no)',
          '\t\t)']
    return '\n'.join(L) + '\n'


def set_stackup(path, inner_oz=0.5):
    """Write the stackup (colours, finish, copper, dielectric) into a saved board.
    KiCad's Python API does not reach BOARD_STACKUP, so this edits the
    file; KiCad keeps the block on every later load and save."""
    import re
    n = pcbnew.LoadBoard(path).GetCopperLayerCount()
    s = open(path).read()
    s = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', s, flags=re.S)
    s = s.replace('\t(setup\n', '\t(setup\n' + stackup_text(n, inner_oz), 1)
    open(path, 'w').write(s)
