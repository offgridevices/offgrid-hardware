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
HALF = 16.9                      # 33.8 mm square, the TAKER G4's footprint
HOLE = 12.75                     # 25.5 mm pattern
HOLE_KEEPOUT_R = 3.1             # grommet flange + clearance, no copper
STD_FP = '/usr/share/kicad/footprints'

def P(x, y):
    return pcbnew.VECTOR2I(MM(CX + x), MM(CY + y))

def lib_path(lib):
    return os.path.join(V1, 'aio.pretty') if lib == 'aio' else os.path.join(STD_FP, lib + '.pretty')

_fp_cache = {}
def load_fp(fpid):
    lib, name = fpid.split(':')
    return pcbnew.FootprintLoad(lib_path(lib), name)

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

def outline(b):
    pts = [(-HALF, -HALF), (HALF, -HALF), (HALF, HALF), (-HALF, HALF)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*pts[i])); s.SetEnd(P(*pts[(i + 1) % 4]))
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

def write_rules(board_path):
    import os
    open(os.path.splitext(board_path)[0] + '.kicad_dru', 'w').write(RULES)


# Stackups, 1.6 mm, 1 oz outer and 0.5 oz inner copper.  4 layers:
# JLCPCB's standard JLC04161H-7628.  6 layers: nominal figures for the fab's
# standard 6-layer 1.6 mm build (nothing here needs controlled impedance).
# Mask and silk colours follow the OffGrid brand: Pitch ground (black
# mask), Bone type (white silk); ENIG keeps the QFN pads flat.
DIELECTRIC = {4: [('prepreg', 0.2104, '7628', 4.4), ('core', 1.065, 'FR4', 4.6), ('prepreg', 0.2104, '7628', 4.4)],
              6: [('prepreg', 0.1, 'FR4', 4.4), ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.45, 'FR4', 4.4),
                  ('core', 0.4, 'FR4', 4.6), ('prepreg', 0.1, 'FR4', 4.4)]}


def stackup_text(n):
    cu = ['F.Cu'] + ['In%d.Cu' % i for i in range(1, n - 1)] + ['B.Cu']
    L = ['\t\t(stackup',
         '\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))',
         '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
         '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))']
    for k, name in enumerate(cu):
        outer = k in (0, n - 1)
        L.append('\t\t\t(layer "%s" (type "copper") (thickness %s))' % (name, '0.035' if outer else '0.0152'))
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


def set_stackup(path):
    """Write the stackup (colours, finish, dielectric) into a saved board.
    KiCad's Python API does not reach BOARD_STACKUP, so this edits the
    file; KiCad keeps the block on every later load and save."""
    import re
    n = pcbnew.LoadBoard(path).GetCopperLayerCount()
    s = open(path).read()
    s = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', s, flags=re.S)
    s = s.replace('\t(setup\n', '\t(setup\n' + stackup_text(n), 1)
    open(path, 'w').write(s)
