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
NLAYERS = int(__import__("os").environ.get("BOARD_LAYERS", 8))   # 8 copper layers as built (6: trials)
HALF = float(__import__("os").environ.get("BOARD_HALF", 19.0))   # 38 mm square as built (BOARD_HALF: trial sizes)
CORNER_R = 3.0                   # rounded corners
HOLE = 12.75                     # 25.5 mm pattern (M2 soft-mount grommets)
HOLE_KEEPOUT_R = 3.1             # grommet flange + clearance: no copper
STD_FP = '/usr/share/kicad/footprints'

def P(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))

def lib_path(lib):
    return os.path.join(V1, 'og.pretty') if lib == 'og' else os.path.join(STD_FP, lib + '.pretty')

_fp_cache = {}
def load_fp(fpid):
    lib, name = fpid.split(':')
    return pcbnew.FootprintLoad(lib_path(lib), name)

def new_board(layers=4):
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(layers)
    ds = b.GetDesignSettings()
    # JLCPCB multilayer capability: 0.09 mm (3.5 mil) tracks and gaps on
    # 1 oz copper.  Signals use it (PCBWay's standard is 0.1 mm: order this
    # board from JLCPCB, or from PCBWay as a 3.5 mil job).
    ds.m_TrackMinWidth = MM(0.09)
    ds.m_MinClearance = MM(0.09)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.25)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.2)        # JLCPCB: via hole to track 0.2 mm
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.1)
    ds.m_SolderMaskExpansion = MM(0.0)       # openings = pads; JLCPCB sizes them in its own process
    ds.m_SolderMaskMinWidth = MM(0.1)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(0.09)); nc.SetTrackWidth(MM(0.09))   # JLCPCB multilayer minimum
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

def outline_path():
    """The board outline, clockwise on screen from the top edge: a square
    with rounded corners, as ('line', p0, p1) and ('arc', p0, mid, p1)."""
    import math
    h, r = HALF, CORNER_R
    k = r * (1 - 1 / math.sqrt(2))
    return [('line', (-h + r, -h), (h - r, -h)), ('arc', (h - r, -h), (h - k, -h + k), (h, -h + r)),
            ('line', (h, -h + r), (h, h - r)), ('arc', (h, h - r), (h - k, h - k), (h - r, h)),
            ('line', (h - r, h), (-h + r, h)), ('arc', (-h + r, h), (-h + k, h - k), (-h, h - r)),
            ('line', (-h, h - r), (-h, -h + r)), ('arc', (-h, -h + r), (-h + k, -h + k), (-h + r, -h))]


def board_polygon(n_arc=24):
    """The board as a shapely polygon in board-centre mm."""
    from shapely.geometry import box
    h, r = HALF, CORNER_R
    return box(-h + r, -h + r, h - r, h - r).buffer(r, quad_segs=n_arc)


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

# Signal layers whose leftover copper is flooded with the battery net, not
# ground.  The battery current otherwise has the one VBAT plane (In6) while
# the return has In1 and the fill of every other layer: at full throttle In6
# made 4.2 of the copper's 11 W and the hottest FET sat 10 C higher
# (sim/thermal, full60 50 C sun).  Every VBAT through via (battery pad,
# high-side drains) joins these fills to In6.
VBAT_FILL = {8: ('In3.Cu', 'In4.Cu'), 6: ()}[NLAYERS]


def pour_ground(path, layers, clearance=0.2):
    """Add ground fill (VBAT on the VBAT_FILL layers) to the given copper
    layers of a routed board, fill all zones and save.  Done after routing so
    the router never sees it."""
    b = pcbnew.LoadBoard(path)
    e = HALF - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    for l in layers:
        net = 'VBAT' if b.GetLayerName(l) in VBAT_FILL else 'GND'
        z = zone(b, net, l, full, clearance=clearance, name=net + ' fill', priority=0)
        # reflowed board: SMD pads solid into the fill (a crowded pad has no room
        # for a spoke), plated holes on spokes
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
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
# inner planes carry the motor current: 1 oz; the FC: 0.5 oz).  4 layers:
# JLCPCB's standard JLC04161H-7628.  6 layers: nominal figures for the fab's
# standard 6-layer 1.6 mm build (nothing here needs controlled impedance).
# Mask and silk colours follow the OffGrid brand: Pitch ground (black
# mask), Bone type (white silk); ENIG keeps the QFN pads flat.
DIELECTRIC = {4: [('prepreg', 0.2104, '7628', 4.4), ('core', 1.065, 'FR4', 4.6), ('prepreg', 0.2104, '7628', 4.4)],
              6: [('prepreg', 0.1, 'FR4', 4.4), ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.45, 'FR4', 4.4),
                  ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.1, 'FR4', 4.4)],
              8: [('prepreg', 0.1, 'FR4', 4.4), ('core', 0.2, 'FR4', 4.6), ('prepreg', 0.2, 'FR4', 4.4),
                  ('core', 0.2, 'FR4', 4.6), ('prepreg', 0.2, 'FR4', 4.4), ('core', 0.2, 'FR4', 4.6),
                  ('prepreg', 0.1, 'FR4', 4.4)]}


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


# The copper layers by job.  6 layers: F parts, In1 ground, In2 signals,
# In3 the channels' return pours, In4 battery, B parts.  8 layers: two more
# signal layers (In3, In4) before the return (In5) and battery (In6) planes.
INNER = {6: dict(gnd='In1.Cu', sig=['In2.Cu'], src='In3.Cu', vbat='In4.Cu'),
         8: dict(gnd='In1.Cu', sig=['In2.Cu', 'In3.Cu', 'In4.Cu'], src='In5.Cu', vbat='In6.Cu')}[NLAYERS]


def layer_id(name):
    return {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu, 'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu,
            'In3.Cu': pcbnew.In3_Cu, 'In4.Cu': pcbnew.In4_Cu, 'In5.Cu': pcbnew.In5_Cu, 'In6.Cu': pcbnew.In6_Cu}[name]


CU_NAMES = ['F.Cu'] + ['In%d.Cu' % i for i in range(1, NLAYERS - 1)] + ['B.Cu']
CU_IDS = [layer_id(n) for n in CU_NAMES]
