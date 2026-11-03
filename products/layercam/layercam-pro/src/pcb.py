# -*- coding: utf-8 -*-
"""Board construction for the one board: outline, stackup,
rules, footprints from the circuit, zones, keepouts, tracks, vias, text.

Coordinates are millimetres from each board's own origin, x to the right,
y down the screen (KiCad's).  configure(board) chooses the board; every
other function works on the board chosen last.

  main  origin on the lens axis.  KiCad's top side (F) is the main board's
        BACK face (towards the lid), seen from behind the camera: x = the
        housing's X, y = -Y (geometry.py).  B is the lens side.
  ring  origin on the lens axis.  F is the ring's FRONT face (the LEDs,
        towards the front wall), seen from in front: x = -X, y = -Y.
  usb   origin on the receptacle's mouth centre, x along it, y into the
        case.  F carries every part (layout_usb.py, geometry.USB_BOX).

The rules are PCBWay's (the boards are made and assembled there): on the
6-layer main board 0.1 mm track and gap is its floor; this board uses 0.1 mm
only round the RV1106's 0.35 mm pins, 0.127 mm elsewhere; vias in pads must
be ordered resin-filled and capped (POFV).  The ring and USB boards: the
standard 2-layer service.
Much of this follows products/print-hub/src/pcb.py.
"""
import math, os
import pcbnew
import circuit, parts, geometry as G

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
MM = pcbnew.FromMM
CX, CY = 100.0, 100.0            # board origin on KiCad's page
STD_FP = '/usr/share/kicad/footprints'

BOARD = None                     # 'main' | 'ring' | 'usb'
LAYERS = 6
TRACK, CLEAR = 0.127, 0.127
VIA = (0.45, 0.2)
HX = HY = W = H = 0.0            # half-extents and size of the outline's box


def configure(board):
    global BOARD, LAYERS, TRACK, CLEAR, VIA, HX, HY, W, H
    BOARD = board
    if board == 'main':
        LAYERS, TRACK, CLEAR, VIA = 6, 0.127, 0.127, (0.45, 0.2)
    else:
        LAYERS, TRACK, CLEAR, VIA = 2, 0.2, 0.13, (0.6, 0.3)
    x0, y0, x1, y1 = board_polygon().bounds
    HX, HY = max(-x0, x1), max(-y0, y1)
    W, H = x1 - x0, y1 - y0


def board_dir(board=None):
    # one board: its files at the revision's top (repo-structure.md)
    return V1


def board_path(board=None):
    return os.path.join(board_dir(), 'layercam-pro.kicad_pcb')


def P(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))


def xy(v):
    """KiCad position -> board mm."""
    return v.x / 1e6 - CX, v.y / 1e6 - CY


def lib_path(lib):
    return os.path.join(V1, 'lc.pretty') if lib == 'lc' else os.path.join(STD_FP, lib + '.pretty')


def load_fp(fpid):
    lib, name = fpid.split(':')
    return pcbnew.FootprintLoad(lib_path(lib), name)


# ---------------------------------------------------------------- outlines
def _arc_pts(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def usb_tab():
    """The USB-C tab, board mm: USB_TAB_W wide, from 1 mm inside
    geometry.USB_EDGE_XY to USB_TAB out from it along the outward normal.
    (The outline was cut down to fit the case after USB_EDGE_XY was set:
    the outline's edge there runs about 0.37 mm inside it, so the tab
    stands about 3.2 mm out of the outline.)"""
    from shapely.geometry import box
    from shapely import affinity
    ex, ey = G.USB_EDGE_XY
    a = math.radians(G.USB_NORMAL_DEG)
    # the tab: USB_TAB_W along the edge, from 1 mm inside it to USB_TAB out,
    # built along +x and turned to the outward normal (lens frame), then
    # into board coordinates
    t = box(-1.0, -G.USB_TAB_W / 2, G.USB_TAB, G.USB_TAB_W / 2)
    t = affinity.rotate(t, a, origin=(0, 0), use_radians=True)
    t = affinity.translate(t, ex, ey)
    return affinity.scale(t, 1, -1, origin=(0, 0))


def _main_polygon():
    """The board in board mm (x = X, y = -Y): the case-shaped outline
    (geometry.OUTLINE) with the USB-C tab on its -X upper edge."""
    from shapely.geometry import Polygon
    poly = Polygon([(x, -y) for x, y in G.OUTLINE]).union(usb_tab())
    # every inside corner rounded to the fab's cutter: PCBWay routes the
    # outline with a 2.0 mm bit (0.8 mm smallest), so an inside corner comes
    # out with its radius whatever the drawing says; drawn here, the
    # Gerbers, the DRC and the case all see the board as it is cut
    r = G.INSIDE_R
    poly = poly.buffer(r, join_style='round', quad_segs=16).buffer(-r, join_style='round', quad_segs=16)
    return poly.simplify(0.001)


def outline_items(board=None):
    """The outline as drawing items: ('line', a, b) in board mm."""
    pts = list(_main_polygon().exterior.coords)
    return [('line', a, c) for a, c in zip(pts, pts[1:])]


def board_polygon(board=None):
    return _main_polygon()


def outline(b):
    for it in outline_items():
        if it[0] == 'line':
            s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(P(*it[1])); s.SetEnd(P(*it[2]))
        elif it[0] == 'arc':
            s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
            s.SetArcGeometry(P(*it[1]), P(*it[2]), P(*it[3]))
        elif it[0] == 'circle':
            s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_CIRCLE)
            s.SetCenter(P(*it[1])); s.SetEnd(P(it[1][0] + it[2], it[1][1]))
        elif it[0] == 'poly':
            pts = it[1]
            for a, c in zip(pts, pts[1:] + pts[:1]):
                s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
                s.SetStart(P(*a)); s.SetEnd(P(*c))
                s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
                b.Add(s)
            continue
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        b.Add(s)


# ---------------------------------------------------------------- board, rules
def new_board(path=None):
    # NewBoard gives the board a project, so SaveBoard writes the net
    # classes into a .kicad_pro beside it (DRC reads them from there)
    b = pcbnew.NewBoard(path) if path else pcbnew.BOARD()
    b.SetCopperLayerCount(LAYERS)
    ds = b.GetDesignSettings()
    if LAYERS == 6:
        ds.m_TrackMinWidth = MM(0.09)
        ds.m_MinClearance = MM(0.09)
        ds.m_ViasMinSize = MM(0.4)
        ds.m_MinThroughDrill = MM(0.2)
        ds.m_ViasMinAnnularWidth = MM(0.1)            # PCBWay's 4 mil ring (their Medium tier)
    else:
        ds.m_TrackMinWidth = MM(0.127)
        ds.m_MinClearance = MM(0.127)
        ds.m_ViasMinSize = MM(0.5)
        ds.m_MinThroughDrill = MM(0.3)
        ds.m_ViasMinAnnularWidth = MM(0.13)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.2)
    ds.m_HoleToHoleMin = MM(0.28)                     # PCBWay: 11 mil
    ds.m_SolderMaskExpansion = MM(0.05)               # PCBWay: openings 2-4 mil over the pad
    ds.m_SolderMaskMinWidth = MM(0.1)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(CLEAR)); nc.SetTrackWidth(MM(TRACK))
    nc.SetViaDiameter(MM(VIA[0])); nc.SetViaDrill(MM(VIA[1]))
    return b


# KiCad 10's Python bindings: keep a reference to anything removed from a
# board, or a later LoadBoard() in the same process returns broken objects
# (docs/lessons.md).
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


def place_components(b, comps, placement):
    """placement: ref -> (x, y, rot[, side]); side 'F' (default) or 'B'.
    A part on B is flipped; its rotation is as seen from the top (F)."""
    allp = {**parts.PARTS, **parts.PADS}
    fps = {}
    for c in comps:
        pd = allp[c.part]
        fp = load_fp(pd['fp'])
        fp.SetReference(c.ref)
        fp.SetValue(pd.get('value', c.part))
        if 'lcsc' in pd:
            fp.SetField('LCSC', pd['lcsc'])
        for fld in fp.GetFields():
            if not (fld.IsReference() or fld.IsValue()):
                fld.SetVisible(False)
                fld.SetLayer(pcbnew.F_Fab)
        fp.Value().SetLayer(pcbnew.F_Fab); fp.Value().SetVisible(False)
        if pd.get('kind') == 'DNP':
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
                             | pcbnew.FP_DNP)
        b.Add(fp)
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
        pl = placement[c.ref]
        x, y, rot = pl[:3]
        side = pl[3] if len(pl) > 3 else 'F'
        fp.SetPosition(P(x, y))
        if side == 'B':
            fp.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        c.side = side
        fps[c.ref] = fp
    return fps


def pad_at(b, ref, num):
    fp = b.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return xy(p.GetPosition())
    raise KeyError('%s pad %s' % (ref, num))


def zone(b, net, layer, poly, clearance=0.2, min_width=0.15, priority=0, thermal=True, name=None,
         spoke=0.3, gap=0.25):
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


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rule_area(b, poly, layers, tracks=True, vias=True, pads=False, pours=True, footprints=False, name=None):
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
    z.SetDoNotAllowFootprints(footprints)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z


def rule_area_shape(b, geom, layers, name=None, tracks=True, vias=True, pours=False):
    """A rule area from a shapely (Multi)Polygon, holes included."""
    gs = getattr(geom, 'geoms', None) or [geom]
    out = []
    for g in gs:
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        for l in layers:
            ls.AddLayer(l)
        z.SetLayerSet(ls)
        ol = z.Outline(); ol.NewOutline()
        for (x, y) in list(g.exterior.coords)[:-1]:
            ol.Append(MM(CX + x), MM(CY + y))
        for h in g.interiors:
            ol.NewHole()
            for (x, y) in list(h.coords)[:-1]:
                ol.Append(MM(CX + x), MM(CY + y), 0, 0)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(pours)
        z.SetDoNotAllowFootprints(False)
        if name:
            z.SetZoneName(name)
        b.Add(z)
        out.append(z)
    return out


# no track or via within this of any board edge (the fab asks 0.3 mm)
EDGE_BAND = 0.35


def edge_band(width=None):
    """The band just inside every board edge (outline and cut-outs) where
    no track or via may go: the fab's 0.3 mm copper-to-edge, which the
    router does not see on curved and inner edges."""
    width = EDGE_BAND if width is None else width
    poly = board_polygon()
    return poly.difference(poly.buffer(-width, join_style=2)).buffer(0)


def cu_layers():
    if LAYERS == 6:
        return [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    return [pcbnew.F_Cu, pcbnew.B_Cu]


def via(b, x, y, net, d=None, drill=None, locked=True):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(MM(d or VIA[0])); v.SetDrill(MM(drill or VIA[1]))
    v.SetNet(add_net(b, net))
    v.SetLocked(locked)
    b.Add(v)
    return v


def track(b, pts, width, layer, net, locked=True):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(MM(width))
        t.SetLayer(layer); t.SetNet(add_net(b, net))
        t.SetLocked(locked)
        b.Add(t)


def netclass(b, name, nets, width, clearance=None, via_d=None, via_drill=None, diff_w=None, diff_gap=None):
    ns = b.GetDesignSettings().m_NetSettings
    nc = pcbnew.NETCLASS(name)
    nc.SetTrackWidth(MM(width)); nc.SetClearance(MM(clearance or CLEAR))
    nc.SetViaDiameter(MM(via_d or VIA[0])); nc.SetViaDrill(MM(via_drill or VIA[1]))
    if diff_w:
        nc.SetDiffPairWidth(MM(diff_w)); nc.SetDiffPairGap(MM(diff_gap))
    ns.SetNetclass(name, nc)
    for n in nets:
        ns.SetNetclassPatternAssignment(n, name)
    for n in nets:
        ni = b.FindNet(n)
        if ni is not None:
            ni.SetNetClass(ns.GetNetClassByName(name))
    return nc


def drc(path, out_json):
    import subprocess, json
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all',
                    '--format', 'json', '-o', out_json, path], capture_output=True)
    r = json.load(open(out_json))
    errs = [v for v in r['violations'] if v['severity'] == 'error']
    warns = [v for v in r['violations'] if v['severity'] != 'error']
    return errs, warns, r['unconnected_items']


RULES = """(version 1)
# Fab limits the board-setup numbers cannot express on their own:
# plated hole to track 0.28 mm (component holes; vias are drilled with the
# copper and keep the 0.2 mm hole clearance).
(rule "plated component hole to track"
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole' && B.Type == 'Track'")
  (constraint hole_clearance (min 0.28mm)))
# Ground pads join the fills by at least one thermal spoke.
(rule "one spoke is enough"
  (constraint min_resolved_spokes 1))
"""


ESCAPE_RULE = '''# The SoC's escape band (layout_main.ESCAPE): 0.1 mm, PCBWay's 6-layer
# floor (4 mil), between its 0.35 mm-pitch pins' stubs and 0.4 mm vias.
(rule "SoC escape band"
  (condition "A.intersectsArea('escape band') && B.intersectsArea('escape band')")
  (constraint clearance (min 0.1mm)))
# The image sensor's balls (0.64 x 0.58 mm pitch, 0.2 mm pads): the same
# 0.1 mm floor for its escape stubs and the vias between its balls
(rule "sensor escape band"
  (condition "A.intersectsArea('sensor band') && B.intersectsArea('sensor band')")
  (constraint clearance (min 0.1mm)))
'''


def write_rules(board_path, extra=''):
    open(os.path.splitext(board_path)[0] + '.kicad_dru', 'w').write(
        RULES + (ESCAPE_RULE if BOARD == 'main' else '') + extra)


# PCBWay's "Regular" 6-layer 1.6 mm build No. 1 (1 oz copper on every
# layer; 2116 prepreg next to the outer layers, so the outer-layer pairs
# reference In1 / In4 at 0.12 mm: sim/impedance.md).  Green mask.
STACKUP6 = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (color "FR4 natural") (thickness 0.1195) (material "2116") (epsilon_r 4.45) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 2" (type "core") (color "FR4 natural") (thickness 0.43) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 3" (type "prepreg") (color "FR4 natural") (thickness 0.175) (material "7628") (epsilon_r 4.74) (loss_tangent 0.02))
\t\t\t(layer "In3.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 4" (type "core") (color "FR4 natural") (thickness 0.43) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In4.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 5" (type "prepreg") (color "FR4 natural") (thickness 0.1195) (material "2116") (epsilon_r 4.45) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""
# The ring and USB boards: one FR4 core, 1 oz each side; green mask and ENIG
# as the main board (README, How to order).
STACKUP2 = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "core") (color "FR4 natural") (thickness %.3f) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Green") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def thickness(board=None):
    return G.BOARD_T


def set_stackup(path):
    """KiCad's Python API does not reach BOARD_STACKUP, so this edits the
    saved file; KiCad keeps the block on every later load and save.  The
    board's own thickness goes with it: the Gerber job file and the STEP
    model read that one, not the sum of the layers."""
    import re
    s = open(path).read()
    s = re.sub(r'(\(general\s*\(thickness )[\d.]+', lambda m: m.group(1) + '%g' % thickness(), s, count=1)
    s = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', s, flags=re.S)
    st = STACKUP6 if LAYERS == 6 else STACKUP2 % (thickness() - 0.07)
    s = s.replace('\t(setup\n', '\t(setup\n' + st, 1)
    open(path, 'w').write(s)


def text(b, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, thick=0.15):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick))
    t.SetTextAngleDegrees(rot)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Cu):
        t.SetMirrored(True)
    b.Add(t)
    return t


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
    pcbnew.SaveBoard(path, b)
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
            if d < (a.GetDrillValue() + vias[j].GetDrillValue()) / 2e6 + 0.28:
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
    pcbnew.SaveBoard(path, b)
    return len(gone)
