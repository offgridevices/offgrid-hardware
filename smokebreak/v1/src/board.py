"""SmokeBreak v1: board construction.  Outline, stackup, rules, footprints from
circuit.py placed from place.py, zones, keepouts and text.

Board coordinates: millimetres from the board's back-left corner, x to the
right (battery end -> drone end), y towards the FRONT (the user).  KiCad's
page has the board at (OX, OY).
"""
import math
import os

import pcbnew

import circuit
import parts

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..'))
LIB = os.path.join(V1, 'lib')
STD_FP = '/usr/share/kicad/footprints'
MM = pcbnew.FromMM
OX, OY = 100.0, 100.0

# The board inside the Arm (100 x 58 x 18 mm body, 3 mm walls)
W, H = 94.0, 52.0
CORNER_R = 3.0
HOLES = [(3.6, 3.6), (W - 3.6, 3.6), (3.6, H - 3.6), (W - 3.6, H - 3.6)]

# PCBWay standard 4-layer capability is 0.1 mm / 0.1 mm and 0.2 mm holes;
# this board keeps comfortable margins over it.
TRACK, CLEAR = 0.125, 0.12        # 5 mil track, 0.12 gap: inside PCBWay's standard 4 / 4 mil (0.1)
VIA_D, VIA_DRILL = 0.6, 0.3
HV_CLEAR = 0.2       # nets that can carry up to 61 V: IPC-2221B 51-100 V asks 0.13 mm (B4 coated, A6 leads)
CU_ALL = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def lib_path(lib):
    return os.path.join(LIB, 'smokebreak.pretty') if lib == 'smokebreak' else os.path.join(STD_FP, lib + '.pretty')


def load_fp(fpid):
    lib, name = fpid.split(':')
    fp = pcbnew.FootprintLoad(lib_path(lib), name)
    if fp is None:
        raise KeyError(fpid)
    return fp


_KEEP = []


def remove(b, item):
    b.Remove(item)
    _KEEP.append(item)


def add_net(b, name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
    return n


def new_board(path):
    """A board with its project (.kicad_pro holds KiCad 10's rules and net classes)."""
    for ext in ('.kicad_pcb', '.kicad_pro', '.kicad_prl'):
        p = os.path.splitext(path)[0] + ext
        if os.path.exists(p):
            os.remove(p)
    b = pcbnew.NewBoard(path)
    b.SetCopperLayerCount(6)
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.1)
    ds.m_MinClearance = MM(0.1)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.2)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.2)
    ds.m_HoleToHoleMin = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.1)
    ds.m_SolderMaskExpansion = MM(0.0)       # the fab sets its own mask expansion
    ds.m_SolderMaskMinWidth = MM(0.08)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(CLEAR)); nc.SetTrackWidth(MM(TRACK))
    nc.SetViaDiameter(MM(VIA_D)); nc.SetViaDrill(MM(VIA_DRILL))
    return b


# ---------------------------------------------------------------- outline
def outline(b):
    r = CORNER_R
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, c in segs:
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        b.Add(s)
    for cx, cy, a0 in ((r, r, 180), (W - r, r, 270), (W - r, H - r, 0), (r, H - r, 90)):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(cx, cy))
        s.SetStart(P(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        b.Add(s)


def board_poly(inset=0.0, n=8):
    """The outline as a polygon, inset by `inset` mm."""
    r = max(CORNER_R - inset, 0.01)
    pts = []
    for cx, cy, a0 in ((CORNER_R, CORNER_R, 180), (W - CORNER_R, CORNER_R, 270),
                       (W - CORNER_R, H - CORNER_R, 0), (CORNER_R, H - CORNER_R, 90)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------- footprints
def place_components(b, placement):
    """placement: ref -> (x, y, rot_deg, side 'T'|'B').  Parts without a
    footprint (bought separately) are skipped."""
    fps = {}
    for ref, c in circuit.COMPONENTS.items():
        pd = parts.PARTS[c['part']]
        if pd['fp'] is None:
            continue
        fp = load_fp(pd['fp'])
        fp.SetReference(ref)
        fp.SetValue(c['value'] or pd['mpn'] or '')
        for k, v in (('MPN', pd['mpn']), ('Manufacturer', pd['mfr']), ('LCSC', pd['lcsc'])):
            if v:
                fp.SetField(k, v)
        for fld in fp.GetFields():
            if not (fld.IsReference() or fld.IsValue()):
                fld.SetVisible(False)
        if pd['fit'] in ('none',):
            fp.SetBoardOnly(True)
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        if pd['fit'] == 'tht':
            fp.SetExcludedFromPosFiles(True)      # hand-soldered: not in the pick-and-place file
        b.Add(fp)
        # designators on the fab layer; silkscreen is kept for the art and labels
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.6), MM(0.6)))
        fp.Reference().SetTextThickness(MM(0.1))
        fp.Value().SetLayer(pcbnew.F_Fab)
        fp.Value().SetVisible(False)
        for it in fp.GraphicalItems():
            if it.GetLayer() == pcbnew.F_SilkS:
                it.SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            net = c['pins'].get(pad.GetNumber())
            if net:
                pad.SetNet(add_net(b, net))
        if ref not in placement:
            raise KeyError(f'no placement for {ref} ({c["part"]}, {c["group"]})')
        x, y, rot, side = placement[ref][:4]
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fps[ref] = fp
    return fps


# ---------------------------------------------------------------- copper shapes
def zone(b, net, layer, poly, clearance=0.2, min_width=0.2, priority=0, thermal=True, name=None,
         spoke=0.5, gap=0.3):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    if net:
        z.SetNet(add_net(b, net))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in poly:
        ol.Append(MM(OX + x), MM(OY + y))
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


def rule_area(b, poly, layers, tracks=True, vias=True, pads=False, pours=True, footprints=False, name=None):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in poly:
        ol.Append(MM(OX + x), MM(OY + y))
    z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowPads(pads); z.SetDoNotAllowZoneFills(pours)
    z.SetDoNotAllowFootprints(footprints)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z


def circle_poly(x, y, r, n=36):
    return [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def via(b, x, y, net, d=VIA_D, drill=VIA_DRILL):
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


def netclass(b, name, nets, width, clearance, via_d=VIA_D, via_drill=VIA_DRILL):
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


def text(b, s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0, thick=0.15, just=None):
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


def poly_shape(b, pts, layer, fill=True, width=0.0):
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_POLY)
    s.SetPolyPoints([P(x, y) for x, y in pts])
    s.SetLayer(layer); s.SetFilled(fill); s.SetWidth(MM(width))
    b.Add(s)
    return s


def line(b, pts, layer, width=0.15):
    for a, c in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetLayer(layer); s.SetWidth(MM(width))
        b.Add(s)


def drc(path, out_json):
    import json
    import subprocess
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all',
                    '--format', 'json', '-o', out_json, path], capture_output=True)
    r = json.load(open(out_json))
    errs = [v for v in r['violations'] if v['severity'] == 'error']
    warns = [v for v in r['violations'] if v['severity'] != 'error']
    return errs, warns, r['unconnected_items']


# ---------------------------------------------------------------- after routing (from Ridge 3)
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


RULES = """(version 1)
# Pads of one part sit as close as its maker made them (a 0.5 mm pitch
# controller has 60 V pins 0.22 mm apart): the HV class's clearance is for
# copper between parts.
%s
(rule "plated hole to track"
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole' && B.Type == 'Track'")
  (constraint hole_clearance (min 0.25mm)))
"""


FINE_PITCH = ['U1', 'U3', 'J8']      # parts whose own pads sit closer than the class clearances


def write_rules(board_path, extra=''):
    within = ''.join('(rule "pads within %s"\n  (condition "A.memberOfFootprint(\'%s\') && B.memberOfFootprint(\'%s\')")\n'
                     '  (constraint clearance (min 0.09mm)))\n' % (r, r, r) for r in FINE_PITCH)
    open(os.path.splitext(board_path)[0] + '.kicad_dru', 'w').write(RULES % within + extra)


# ---------------------------------------------------------------- artwork (art.py polygons)
import sys as _sys
ART_PYTHON = os.environ.get('SB_ART_PYTHON', _sys.executable)     # needs shapely, uharfbuzz, fontTools


def art(items, work):
    """Run art.py (needs shapely + uharfbuzz) on `items`; returns its result list."""
    import json
    import subprocess
    spec, out = os.path.join(work, 'art_in.json'), os.path.join(work, 'art_out.json')
    json.dump(items, open(spec, 'w'))
    subprocess.run([ART_PYTHON, os.path.join(HERE, 'art.py'), spec, out], check=True)
    return json.load(open(out))


LAYERS = {'F.SilkS': pcbnew.F_SilkS, 'B.SilkS': pcbnew.B_SilkS, 'F.Fab': pcbnew.F_Fab,
          'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu, 'F.Mask': pcbnew.F_Mask, 'B.Mask': pcbnew.B_Mask}


def add_polys(b, polys, layer, mirror_x=None):
    """Filled polygons (board mm) with holes; mirror_x mirrors about x for the bottom side."""
    out = []
    for p in polys:
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        f = (lambda x: 2 * mirror_x - x) if mirror_x is not None else (lambda x: x)
        for x, y in p['outer']:
            ps.Append(MM(OX + f(x)), MM(OY + y))
        for k, h in enumerate(p['holes']):
            ps.NewHole()
            for x, y in h:
                ps.Append(MM(OX + f(x)), MM(OY + y), 0, k)
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_POLY)
        s.SetPolyShape(ps)
        s.SetLayer(LAYERS[layer] if isinstance(layer, str) else layer)
        s.SetFilled(True)
        s.SetWidth(0)
        b.Add(s)
        out.append(s)
    return out
