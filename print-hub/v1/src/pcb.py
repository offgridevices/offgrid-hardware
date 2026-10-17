# -*- coding: utf-8 -*-
"""Shared board construction: outline, stackup, rules, footprints from the
circuit, zones, keepouts, tracks, vias and text.

Coordinates are millimetres from the board centre, x to the right, y
towards the FRONT (KiCad's y points down the screen): the five USB-A ports
are along the bottom edge of every plot, POWER IN, DATA and the antenna
along the top.

Much of this follows ridge3-lite/v1/src/pcb.py; the rules are JLCPCB's
standard 4-layer tier (no fine-line or small-via surcharge).
"""
import os
import pcbnew
import circuit, parts

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
MM = pcbnew.FromMM
CX, CY = 100.0, 100.0            # board centre on KiCad's page
W, H = 104.0, 66.0               # board size; square corners (brand: right angles only)
HX, HY = W / 2, H / 2
HOLES = [(-49.0, -30.0), (49.0, -30.0), (-49.0, 30.0), (49.0, 30.0)]
STD_FP = '/usr/share/kicad/footprints'

# JLCPCB standard 4-layer: 0.127 mm track and gap is the floor; this board
# uses 0.15 mm, and 0.6 / 0.3 mm vias (no small-via surcharge)
TRACK, CLEAR = 0.15, 0.15
VIA = (0.6, 0.3)


def P(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))


def xy(v):
    """KiCad position -> board mm."""
    return v.x / 1e6 - CX, v.y / 1e6 - CY


def lib_path(lib):
    return os.path.join(V1, 'ph.pretty') if lib == 'ph' else os.path.join(STD_FP, lib + '.pretty')


def load_fp(fpid):
    lib, name = fpid.split(':')
    return pcbnew.FootprintLoad(lib_path(lib), name)


def new_board():
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.127)
    ds.m_MinClearance = MM(0.127)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.2)
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.13)
    ds.m_SolderMaskExpansion = MM(0.0)
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


def outline(b):
    pts = [(-HX, -HY), (HX, -HY), (HX, HY), (-HX, HY)]
    for a, c in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        b.Add(s)


def board_polygon():
    from shapely.geometry import box
    return box(-HX, -HY, HX, HY)


def place_components(b, comps, placement):
    """placement: ref -> (x, y, rot)  (every part on the top side)."""
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
        b.Add(fp)
        # reference designators and outlines go on the assembly drawing
        # (fab layer); the silkscreen carries labels drawn by silk.py
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
        x, y, rot = placement[c.ref]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fps[c.ref] = fp
    return fps


def pad_at(b, ref, num):
    fp = b.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return xy(p.GetPosition())
    raise KeyError('%s pad %s' % (ref, num))


def zone(b, net, layer, poly, clearance=0.25, min_width=0.2, priority=0, thermal=True, name=None,
         spoke=0.4, gap=0.3):
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


CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]


def via(b, x, y, net, d=VIA[0], drill=VIA[1], locked=True):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(drill))
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


def netclass(b, name, nets, width, clearance=CLEAR, via_d=VIA[0], via_drill=VIA[1]):
    ns = b.GetDesignSettings().m_NetSettings
    nc = pcbnew.NETCLASS(name)
    nc.SetTrackWidth(MM(width)); nc.SetClearance(MM(clearance))
    nc.SetViaDiameter(MM(via_d)); nc.SetViaDrill(MM(via_drill))
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
# JLCPCB limits the board-setup numbers cannot express on their own:
# plated hole to track 0.28 mm.
(rule "plated component hole to track"
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole' && B.Type == 'Track'")
  (constraint hole_clearance (min 0.28mm)))
# Ground pads join the fills by at least one thermal spoke.
(rule "one spoke is enough"
  (constraint min_resolved_spokes 1))
"""


def write_rules(board_path, extra=''):
    open(os.path.splitext(board_path)[0] + '.kicad_dru', 'w').write(RULES + extra)


# JLCPCB's standard 4-layer 1.6 mm stackup (JLC04161H-7628), 1 oz outer,
# 0.5 oz inner.  Mask and silk in the OffGrid brand colours: Pitch ground
# (black mask), Bone type (white silk).
STACKUP = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (color "FR4 natural") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (color "FR4 natural") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (color "FR4 natural") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def set_stackup(path):
    """KiCad's Python API does not reach BOARD_STACKUP, so this edits the
    saved file; KiCad keeps the block on every later load and save."""
    import re
    s = open(path).read()
    s = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', s, flags=re.S)
    s = s.replace('\t(setup\n', '\t(setup\n' + STACKUP, 1)
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
