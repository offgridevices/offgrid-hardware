# -*- coding: utf-8 -*-
"""Production panel for bulk SMT assembly (JLCPCB Standard PCBA, PCBWay),
from one finished .kicad_pcb.

    make_panel(board_pcb, out_dir, name, cols=3, rows=2, board_name=None,
               rails='tb', verify=True, render=True)

    python3 panel.py fc  OUT_DIR                  (the committed FC board)
    python3 panel.py esc OUT_DIR --cols 3 --rows 2
    python3 panel.py path/to/x.kicad_pcb OUT_DIR --name ridge3-fc --board fc

Writes into OUT_DIR:

  <name>-panel.kicad_pcb (+ .kicad_pro/.kicad_dru/.kicad_prl, fp-lib-table)
  <name>-panel-gerbers.zip        fab.gerbers() on the panel: the same layers
                                  and options as the single board
  <name>-panel-bom-jlcpcb.csv     one line per LCSC part, Designators of every copy
  <name>-panel-cpl-jlcpcb.csv     one row per placed part per copy, fab.bom_cpl's rules
  <name>-panel-bom-pcbway.csv
  <name>-panel-top.png / -bottom.png
  <name>-panel-drc.json

Needs KiKit (pip install kikit; 1.8.1 is what this was written against,
running on KiCad 10.0) and, for the Gerber check, gerbonara.

Why the panel looks the way it does (numbers are JLCPCB's published guidance):

* Standard PCBA (the only JLCPCB service that places both sides, which the
  ESC needs) takes panels of 70 x 70 to 250 x 250 mm, with edge rails and
  fiducials required (jlcpcb.com/capabilities/pcb-assembly-capabilities).
* Mouse-bite tabs, not V-cut.  V-cut needs copper >= 0.4 mm from the cut
  line and zero gap between boards (jlcpcb.com/blog/v-cut-panelization-
  standards); the FC has wire pads 0.3 mm and ground/3V3 pours 0.35 mm from
  its edge on every layer, and its USB-C shell overhangs the edge by ~0.1 mm,
  which a zero-gap panel would drive into the neighbouring board.
* Boards 2 mm apart (JLC: 1.6-2 mm, 1.2 mm minimum), 5 mm rails on the two
  long sides (JLC minimum 5 mm process edge), 2 mm from the boards.  The
  36 mm boards would allow 2 x 2 (74 x 88 mm); the default is 3 x 2,
  112 x 88 mm, 6 boards, for fewer panels per order.
* The boards' corners are slotted for the mounting grommets: the outline
  is taken from Edge.Cuts as drawn, and no tab goes within 1.5 mm of a
  stretch of edge the slot has cut away.
* Mouse bites: 0.5 mm holes at 0.85 mm pitch (0.35 mm web: JLC asks for
  0.35-0.4 mm, 0.3 mm minimum), 5 holes per tab (JLC: 5-8), 2 tabs per side
  (JLC: at least 2 sets, one more per 50-60 mm).  The holes sit in the tab,
  tangent to the board edge: the pours are 0.35 mm inside the edge and JLC
  wants 0.3-0.5 mm between a mouse-bite hole and copper, so the holes cannot
  cut into the board; the price is a <= 0.25 mm nub to sand off.
* Tabs go only where nothing is near the edge: no placed part's courtyard
  within 1.5 mm along the edge (JLC: 1.5 mm between tab and component or
  pad), no pad, track or via within 1 mm, looking 1.5 mm into the board
  (a straight track counts only over the stretch of it inside that band).
  Worked out per board (both sides' parts), so it is the same code for the ESC.
* Fiducials: 1 mm copper, 2 mm mask opening, 3 per side in an L (top and
  bottom layer), centres 3.85 mm from the rail's outer edge (JLC: "5 mm
  process edges, 2 mm tooling holes, and 1 mm fiducials placed 3.85 mm from
  the panel edge", help article specifications-for-adding-process-edges-and-
  positioning-holes), >= 3 mm from any copper or silk (JLC fiducial keep-out),
  measured on the panel Gerbers.
* Tooling holes: 4 x 2.0 mm NPTH, rail centreline, 5 mm from the panel ends
  (the 1.152 mm hole is JLC's spec for holes on a single board for Economic
  PCBA; 2 mm is the one for Standard-PCBA process edges).
* Rail text: the board name, and JLCJLCJLCJLC so JLC prints its order number
  on the rail rather than on a board.
"""
import csv, os, sys, json, math, subprocess, tempfile, collections, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pcbnew
import fab

MM = 1000000                 # KiCad internal units per mm

# ---------------------------------------------------------------- defaults
GAP = 2.0                    # board to board and board to rail, mm
RAIL = 5.0                   # rail width, mm
TAB_WIDTH = 3.4              # mm: 5 holes of MB_DRILL at MB_PITCH
MB_DRILL = 0.5               # mouse-bite hole, mm
MB_SPACING = 0.84            # KiKit hole spacing; gives 0.85 mm pitch over 3.4 mm
MB_OFFSET = -MB_DRILL / 2    # holes in the tab, tangent to the board edge
EDGE_BAND = 1.5              # how far into the board a feature counts as "at the edge", mm
# (part courtyard margin, copper margin) along the edge, strictest first
TAB_MARGINS = [(1.5, 1.0), (1.0, 0.75), (0.75, 0.5), (0.5, 0.25)]
CORNER = 1.0                 # tabs stay this far from the board corners, mm
FID_COPPER, FID_OPENING = 1.0, 2.0
FID_FROM_EDGE = 3.85         # fiducial centre from the rail's outer edge
FID_FROM_END = 10.0          # ... and from the panel's end
FID_KEEPOUT = 3.0            # copper-free radius round a fiducial
TOOL_DRILL = 2.0
TOOL_FROM_END = 5.0
MIN_PANEL, MAX_PANEL = 70.0, 250.0

# JLCPCB wants 0.3-0.5 mm between a mouse-bite hole and copper.  (A like
# rule for the fiducial keep-out would be shadowed by the 0.5 mm local
# clearance KiKit gives the fiducial pad, so that one is measured on the
# Gerbers instead: fiducial_keepout().)
FAB_RULES = """
# Panel features against JLCPCB guidance (added by panel.py)
(rule "JLC: mouse-bite holes 0.3 mm from copper"
  (condition "A.memberOfFootprint('KiKit_MB_*')")
  (constraint hole_clearance (min 0.3mm)))
"""


_APP = None                  # KiKit's stand-in wx app must outlive the panel build


def run(cmd):
    return fab.run(cmd)


def _mm(v):
    return v / MM


# ------------------------------------------------------------ board model
def _shape(b):
    """The board's outline as one shapely polygon, in nm."""
    from kikit.substrate import Substrate
    from kikit.common import collectEdges
    from kikit.defs import Layer
    g = Substrate(collectEdges(b, Layer.Edge_Cuts)).substrates
    if g.geom_type != 'Polygon':
        raise SystemExit('panel.py lays out one-piece boards only; %s is not one' % b.GetFileName())
    return g


def _position_panel(page, panel):
    """KiKit's positionPanel (the panel's top-left corner to the page
    position; this preset's anchor is 'tl'), moved by a whole number of
    micrometres: KiKit's box of the outline's arcs, as polylines, is a few
    tens of nm off, and each copy's offset must stay a whole 0.1 um."""
    if page.get('anchor') != 'tl':
        raise SystemExit('panel.py places the panel by its top-left corner only')
    bb = panel.boardSubstrate.boundingBox()
    x0, y0 = bb.GetX(), bb.GetY()
    um = lambda v: int(round(v / 1000.0)) * 1000
    panel.translate((um(page['posx'] - x0), um(page['posy'] - y0)))


def _outline(b):
    """Bounding box of the board outline as (x0, y0, x1, y1) in nm, on
    whole micrometres (arcs come as polylines a few tens of nm off the
    edges they are tangent to; the copies' offsets must be whole 0.1 um)."""
    return tuple(int(round(v / 1000.0)) * 1000 for v in _shape(b).bounds)


def outline_cutouts(b, box, step=0.05):
    """Stretches of the bounding box's edges that are not board edge (the
    corner slots), as edge features of kind 'outline'."""
    from shapely.geometry import Point
    g = _shape(b)
    x0, y0, x1, y1 = (_mm(v) for v in box)
    out = []
    for side, length, at in (('top', x1 - x0, lambda t: (x0 + t, y0)), ('bottom', x1 - x0, lambda t: (x0 + t, y1)),
                             ('left', y1 - y0, lambda t: (x0, y0 + t)), ('right', y1 - y0, lambda t: (x1, y0 + t))):
        n = int(round(length / step))
        on = [g.boundary.distance(Point(*(v * MM for v in at(i * step)))) < 0.01 * MM for i in range(n + 1)]
        i = 0
        while i <= n:
            if on[i]:
                i += 1
                continue
            j = i
            while j + 1 <= n and not on[j + 1]:
                j += 1
            out.append((side, i * step, j * step, 0.0, 'slot in the outline', 'outline'))
            i = j + 1
    return out


def _placed(fp):
    return not (fp.GetAttributes() & (pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY))


def edge_features(b, box, band=EDGE_BAND):
    """Everything within `band` mm of a board edge, as
    (side, lo, hi, depth, what, kind): lo..hi is its extent along that edge
    (mm from the left or top end), depth how far inside the edge it starts
    (negative: it overhangs).  kind: 'part' (a placed part's courtyard) or
    'copper' (pad, track, via, copper graphic) or 'hole' (NPTH)."""
    x0, y0, x1, y1 = (_mm(v) for v in box)
    out = []

    def add(bb, what, kind):
        a0, b0, a1, b1 = _mm(bb.GetX()), _mm(bb.GetY()), _mm(bb.GetRight()), _mm(bb.GetBottom())
        for side, depth, lo, hi in (('top', b0 - y0, a0 - x0, a1 - x0), ('bottom', y1 - b1, a0 - x0, a1 - x0),
                                    ('left', a0 - x0, b0 - y0, b1 - y0), ('right', x1 - a1, b0 - y0, b1 - y0)):
            if depth < band:
                out.append((side, lo, hi, depth, what, kind))

    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if _placed(fp):
            cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
            add(cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False), ref, 'part')
        for p in fp.Pads():
            npth = p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
            add(p.GetBoundingBox(), '%s pad %s' % (ref, p.GetNumber()), 'hole' if npth else 'copper')
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_TRACE_T:
            # a straight track: only the stretch of it inside the band, not
            # its bounding box (a diagonal that touches the band at one end
            # would otherwise block all the edge it spans)
            w = _mm(t.GetWidth())
            a, c = t.GetStart(), t.GetEnd()
            out += _segment_in_band(((_mm(a.x), _mm(a.y)), (_mm(c.x), _mm(c.y))), w, (x0, y0, x1, y1), band,
                                    'track %s' % t.GetNetname())
            continue
        add(t.GetBoundingBox(), '%s %s' % ('via' if t.Type() == pcbnew.PCB_VIA_T else 'track', t.GetNetname()), 'copper')
    for d in b.GetDrawings():
        if d.IsOnCopperLayer():
            add(d.GetBoundingBox(), 'copper graphic', 'copper')
    return out


def _segment_in_band(seg, width, box, band, what):
    """Edge features (as edge_features) of a straight track of `width` from
    seg[0] to seg[1], all mm: for each edge, the part of the track whose
    copper comes within `band` of it, spanning lo..hi along that edge."""
    (ax, ay), (cx, cy) = seg
    x0, y0, x1, y1 = box
    out = []
    for side, d0, d1, u0, u1 in (('top', ay - y0, cy - y0, ax - x0, cx - x0),
                                 ('bottom', y1 - ay, y1 - cy, ax - x0, cx - x0),
                                 ('left', ax - x0, cx - x0, ay - y0, cy - y0),
                                 ('right', x1 - ax, x1 - cx, ay - y0, cy - y0)):
        # copper depth along the track: d(s) = d0 + (d1 - d0) s - width/2, s in 0..1
        d0, d1 = d0 - width / 2, d1 - width / 2
        if d0 >= band and d1 >= band:
            continue
        if d0 < band and d1 < band:
            s0, s1 = 0.0, 1.0
        else:
            s = (band - d0) / (d1 - d0)
            s0, s1 = (0.0, s) if d0 < band else (s, 1.0)
        u = sorted(u0 + (u1 - u0) * s for s in (s0, s1))
        out.append((side, u[0] - width / 2, u[1] + width / 2, min(d0, d1), what, 'copper'))
    return out


def _subtract(intervals, lo, hi):
    out = []
    for a, b in intervals:
        if hi <= a or lo >= b:
            out.append((a, b))
            continue
        if a < lo:
            out.append((a, lo))
        if hi < b:
            out.append((hi, b))
    return out


def tab_centres(feats, sides, length, width, count, m_part, m_cu, spread=True, corner=CORNER, step=0.05):
    """Centres (mm along the edge) of `count` tabs of `width` that are clear of
    every feature on any of `sides`, each as close as it can get to its
    share of the edge.  spread=True keeps tab i inside the i-th of `count`
    equal lengths of the edge (so an edge is never held at one end only)."""
    free = [(corner, length - corner)]
    for side, lo, hi, depth, what, kind in feats:
        if side in sides:
            m = m_part if kind in ('part', 'outline') else m_cu
            free = _subtract(free, lo - m, hi + m)
    feas = []
    for a, b in free:
        lo = math.ceil((a + width / 2) / step - 1e-9) * step
        hi = math.floor((b - width / 2) / step + 1e-9) * step
        if hi >= lo:
            feas.append((lo, hi))
    centres = []
    for i in range(count):
        t = length * (2 * i + 1) / (2 * count)
        seg = (length * i / count, length * (i + 1) / count)
        best = None
        for lo, hi in feas:
            if spread:
                lo, hi = max(lo, seg[0]), min(hi, seg[1])
                if hi < lo:
                    continue
            c = min(max(t, lo), hi)
            if best is None or abs(c - t) < abs(best - t):
                best = c
        if best is None:
            break
        centres.append(round(best, 4))
        feas = _subtract(feas, best - width - 1.0, best + width + 1.0)
    return sorted(centres)


def plan_tabs(b, box, width=TAB_WIDTH):
    """Tab positions for the two edge directions, with the margins used:
    spread along the edge at the strictest margins that allow it, else at
    relaxed margins, else (flagged) wherever they fit."""
    feats = edge_features(b, box) + outline_cutouts(b, box)
    w, h = _mm(box[2] - box[0]), _mm(box[3] - box[1])
    plan = {}
    for axis, sides, length in (('x', ('top', 'bottom'), w), ('y', ('left', 'right'), h)):
        count = max(2, int(math.ceil(length / 50.0)) + 1)
        for spread in (True, False):
            for m_part, m_cu in TAB_MARGINS:
                c = tab_centres(feats, sides, length, width, count, m_part, m_cu, spread)
                if len(c) == count:
                    plan[axis] = dict(centres=c, margins=(m_part, m_cu), count=count, length=length,
                                      spread=spread)
                    break
            if axis in plan:
                break
        else:
            blocked = sorted((f[1], f[2], f[4]) for f in feats if f[0] in sides)
            raise SystemExit('no room for %d tabs of %.1f mm along the %s edges; edge features: %s'
                             % (count, width, '/'.join(sides), blocked))
    # overhanging parts (courtyard outside the edge), per side
    over = {s: max([-f[3] for f in feats if f[0] == s and f[5] == 'part' and f[3] < 0] or [0.0])
            for s in ('top', 'bottom', 'left', 'right')}
    over_what = sorted(set('%s (%s, %.2f mm)' % (f[4], f[0], -f[3]) for f in feats if f[5] == 'part' and f[3] < 0))
    return plan, over, over_what, feats


# ------------------------------------------------------------- the panel
def _preset(name, rails, cols, rows):
    from kikit import panelize_ui_impl as ki
    long_tb = rails in ('tb', 'frame')
    fr = {'tb': 'railstb', 'lr': 'railslr', 'frame': 'frame'}[rails]
    h, v = ('%gmm' % FID_FROM_END, '%gmm' % FID_FROM_EDGE) if long_tb else ('%gmm' % FID_FROM_EDGE, '%gmm' % FID_FROM_END)
    th, tv = ('%gmm' % TOOL_FROM_END, '%gmm' % (RAIL / 2)) if long_tb else ('%gmm' % (RAIL / 2), '%gmm' % TOOL_FROM_END)
    label = '%s  %dx%d panel' % (name, cols, rows)
    if long_tb:
        text = dict(type='simple', text=label, anchor='mt', voffset='%gmm' % (RAIL / 2), hoffset='0mm',
                    orientation='0deg')
        text2 = dict(type='simple', text='JLCJLCJLCJLC', anchor='mb', voffset='-%gmm' % (RAIL / 2),
                     hoffset='0mm', orientation='0deg', width='1mm', height='1mm', thickness='0.15mm')
    else:
        text = dict(type='simple', text=label, anchor='ml', hoffset='%gmm' % (RAIL / 2), voffset='0mm',
                    orientation='90deg')
        text2 = dict(type='simple', text='JLCJLCJLCJLC', anchor='mr', hoffset='-%gmm' % (RAIL / 2),
                     voffset='0mm', orientation='90deg', width='1mm', height='1mm', thickness='0.15mm')
    text.update(width='1.5mm', height='1.5mm', thickness='0.25mm', layer='F.SilkS',
                hjustify='center', vjustify='center')
    text2.update(layer='F.SilkS', hjustify='center', vjustify='center')
    return ki.obtainPreset(
        [],
        source=dict(type='auto', tolerance='3mm'),
        tabs=dict(type='annotation', fillet='0mm'),
        cuts=dict(type='mousebites', drill='%gmm' % MB_DRILL, spacing='%gmm' % MB_SPACING,
                  offset='%gmm' % MB_OFFSET, prolong='0mm'),
        framing=dict(type=fr, width='%gmm' % RAIL, space='%gmm' % GAP, cuts='none'),
        tooling=dict(type='4hole', hoffset=th, voffset=tv, size='%gmm' % TOOL_DRILL, paste='false',
                     soldermaskmargin='0mm'),
        fiducials=dict(type='3fid', hoffset=h, voffset=v, coppersize='%gmm' % FID_COPPER,
                       opening='%gmm' % FID_OPENING, paste='false'),
        text=text, text2=text2,
        post=dict(millradius='0mm', origin='tl', refillzones='false', edgewidth='0.1mm'),
        page=dict(type='inherit', anchor='tl', posx='20mm', posy='20mm'),
        debug=dict(deterministic='true'))


def build_panel(board_pcb, panel_pcb, name, cols, rows, rails='tb'):
    """Lay the panel out with KiKit and save it.  Returns (refmap: panel
    designator -> (board designator, copy number), grid: copy -> (row, col),
    tab plan info)."""
    from kikit import panelize_ui_impl as ki
    from kikit.panelize import Panel, Origin, NonFatalErrors
    from kikit.annotations import TabAnnotation
    from kikit.common import fakeKiCADGui, fromDegrees
    global _APP
    _APP = fakeKiCADGui()
    preset = _preset(name, rails, cols, rows)
    pcbnew.KIID.SeedGenerator(42)
    board = pcbnew.LoadBoard(board_pcb)
    box = _outline(board)
    bw, bh = box[2] - box[0], box[3] - box[1]
    plan, over, over_what, feats = plan_tabs(board, box)

    gap = int(round(GAP * MM))
    for s in ('top', 'bottom', 'left', 'right'):
        if over[s] + 0.5 > GAP:
            raise SystemExit('%s: parts overhang the %s edge by %.2f mm, more than the %.1f mm gap allows'
                             % (name, s, over[s], GAP))
    if over['left'] + over['right'] + 0.5 > GAP and cols > 1 or over['top'] + over['bottom'] + 0.5 > GAP and rows > 1:
        raise SystemExit('%s: overhanging parts of neighbouring boards would meet in the gap' % name)

    panel = Panel(panel_pcb)
    panel.inheritDesignSettings(board)
    panel.inheritProperties(board)
    panel.inheritTitleBlock(board)
    panel.inheritLayerNames(board)
    src_area = ki.readSourceArea(preset['source'], board)
    # the box on whole micrometres: KiCad's box of a small outline arc (its
    # centre worked out from three points rounded to the nm) can stand a
    # few tens of nm off the edge the arc is tangent to, and each copy's
    # offset must be a whole 0.1 um (the Gerbers' resolution)
    um = lambda v: int(round(v / 1000.0)) * 1000
    x0, y0, x1, y1 = um(src_area.GetX()), um(src_area.GetY()), um(src_area.GetRight()), um(src_area.GetBottom())
    src_area = pcbnew.BOX2I(pcbnew.VECTOR2I(x0, y0), pcbnew.VECTOR2I(x1 - x0, y1 - y0))

    refmap = {}          # panel ref -> (original ref, copy number 1..n)

    def renamer(n, ref):
        new = '%s_%d' % (ref, n + 1)
        if new in refmap:
            raise SystemExit('designator %s would not be unique' % new)
        refmap[new] = (ref, n + 1)
        return new

    grid = {}
    cx0, cy0 = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    for i in range(rows):
        for j in range(cols):
            k = len(panel.substrates) + 1
            dest = pcbnew.VECTOR2I(cx0 + j * (bw + gap), cy0 + i * (bh + gap))
            panel.appendBoard(board_pcb, dest, sourceArea=src_area, origin=Origin.Center,
                              rotationAngle=fromDegrees(0), refRenamer=renamer, bakeText=True)
            grid[k] = (i, j)
    substrates = panel.substrates
    framing = ki.dummyFramingSubstrate(substrates, preset)
    panel.buildPartitionLineFromBB(framing)

    # tabs where plan_tabs found room, on every side that faces a neighbour or a rail
    n_tabs = 0
    for k, s in enumerate(substrates, 1):
        i, j = grid[k]
        minx, miny, maxx, maxy = s.bounds()
        faces = dict(top=i > 0 or rails in ('tb', 'frame'), bottom=i < rows - 1 or rails in ('tb', 'frame'),
                     left=j > 0 or rails in ('lr', 'frame'), right=j < cols - 1 or rails in ('lr', 'frame'))
        for side, on in faces.items():
            if not on:
                continue
            axis = 'x' if side in ('top', 'bottom') else 'y'
            for c in plan[axis]['centres']:
                c = c * MM
                origin, d = dict(top=((minx + c, miny), (0, 1)), bottom=((minx + c, maxy), (0, -1)),
                                 left=((minx, miny + c), (1, 0)), right=((maxx, miny + c), (-1, 0)))[side]
                s.annotations.append(TabAnnotation(None, origin, d, int(round(TAB_WIDTH * MM))))
                n_tabs += 1
    tab_cuts = panel.buildTabsFromAnnotations(0)
    if len(tab_cuts) != n_tabs:
        raise SystemExit('KiKit built %d of %d tabs' % (len(tab_cuts), n_tabs))

    pre_frame = panel.boardSubstrate.substrates
    frame_cuts = ki.buildFraming(preset, panel)
    ki.buildTabFillets(preset, panel, pre_frame)
    ki.buildTooling(preset, panel)
    ki.buildFiducials(preset, panel)
    for t in ('text', 'text2'):
        ki.buildText(preset[t], panel)
    ki.buildPostprocessing(preset['post'], panel)
    ki.makeTabCuts(preset, panel, tab_cuts)
    ki.makeOtherCuts(preset, panel, frame_cuts)
    ki.setStackup(preset['source'], panel)
    ki.setPageSize(preset['page'], panel, board)
    _position_panel(preset['page'], panel)
    panel.save(reconstructArcs=False, refillAllZones=False, edgeWidth=int(0.1 * MM))
    if panel.hasErrors():
        raise NonFatalErrors(panel.errors)
    return refmap, grid, dict(plan=plan, overhang=over, overhang_parts=over_what, tabs=n_tabs,
                              board_box=box)


def _finish_files(board_pcb, panel_pcb, out_dir):
    """Point the panel's project-relative paths (3D models, footprint
    libraries) back at the source board's folder, add the panel DRC rules,
    and drop KiCad's lock file."""
    src_dir = os.path.dirname(os.path.abspath(board_pcb))
    rel = os.path.relpath(src_dir, os.path.abspath(out_dir))
    txt = open(panel_pcb).read()
    txt = txt.replace('(model "${KIPRJMOD}/', '(model "${KIPRJMOD}/%s/' % rel)
    open(panel_pcb, 'w').write(txt)
    lib = os.path.join(src_dir, 'fp-lib-table')
    if os.path.exists(lib):
        open(os.path.join(out_dir, 'fp-lib-table'), 'w').write(
            open(lib).read().replace('${KIPRJMOD}/', '${KIPRJMOD}/%s/' % rel))
    dru = os.path.splitext(panel_pcb)[0] + '.kicad_dru'
    rules = open(dru).read() if os.path.exists(dru) else '(version 1)\n'
    open(dru, 'w').write(rules.rstrip('\n') + '\n' + FAB_RULES)
    for f in os.listdir(out_dir):
        if f.startswith('~') and f.endswith('.lck'):
            os.remove(os.path.join(out_dir, f))


# ------------------------------------------------------ copies and offsets
def copies(panel_board, src_board, refmap):
    """Per copy: its offset (nm) from the source board, checked to be one
    rigid translation of every footprint (same angle, same side).  Also
    returns the KiKit panel features (fiducials, tooling, mouse bites)."""
    src = {fp.GetReference(): fp for fp in src_board.GetFootprints()}
    per = collections.defaultdict(dict)
    feats = []
    for fp in panel_board.GetFootprints():
        ref = fp.GetReference()
        if ref in refmap:
            orig, k = refmap[ref]
            per[k][orig] = fp
        elif ref.startswith('KiKit_'):
            feats.append(fp)
        else:
            raise SystemExit('panel footprint %s belongs to no copy' % ref)
    offsets = {}
    for k, fps in sorted(per.items()):
        if set(fps) != set(src):
            raise SystemExit('copy %d: footprints differ from the board (%s)' % (k, sorted(set(src) ^ set(fps))[:8]))
        d = None
        for orig, fp in fps.items():
            s = src[orig]
            dd = (fp.GetPosition().x - s.GetPosition().x, fp.GetPosition().y - s.GetPosition().y)
            if d is None:
                d = dd
            if dd != d or fp.GetOrientationDegrees() != s.GetOrientationDegrees() or fp.IsFlipped() != s.IsFlipped():
                raise SystemExit('copy %d: %s is not the board translated by %s' % (k, orig, d))
        offsets[k] = d
    return offsets, feats


# ------------------------------------------------------------ BOM and CPL
def _cpl_row(ref, fp, p):
    """fab.bom_cpl's rule, for one footprint (kept identical; check_bom_cpl()
    compares the result against fab.bom_cpl's own output every run)."""
    q = fp.GetPosition()
    rot = fp.GetOrientationDegrees()
    bottom = fp.IsFlipped()
    off = p.get('jlc_rot', 0)
    if bottom and off:
        raise SystemExit('jlc_rot on a bottom-side part is not worked out: %s' % ref)
    rot += off
    if bottom:
        rot = 180 - rot
    rot = round(rot % 360, 2) % 360
    return [ref, '%.4fmm' % (q.x / 1e6), '%.4fmm' % (-q.y / 1e6), 'Bottom' if bottom else 'Top', ('%g' % rot)]


def bom_cpl(panel_board, src_board, board_name, refmap, out_dir, name):
    """Panel BOM (JLCPCB, PCBWay) and CPL.  The assembled set and the part
    data come from fab._assembled on the source board."""
    asm = {fp.GetReference(): p for fp, p in fab._assembled(src_board, board_name)}
    rows, sides = [], collections.defaultdict(set)
    groups = collections.OrderedDict()
    for fp in panel_board.GetFootprints():
        ref = fp.GetReference()
        if ref in refmap and refmap[ref][0] in asm:
            p = asm[refmap[ref][0]]
            rows.append(_cpl_row(ref, fp, p))
            sides[p['lcsc']].add('Bottom' if fp.IsFlipped() else 'Top')
    for orig, p in sorted(asm.items(), key=lambda a: (a[1]['lcsc'], fab._natural(a[0]))):
        groups.setdefault(p['lcsc'], (p, []))
    for ref, (orig, k) in refmap.items():
        if orig in asm:
            groups[asm[orig]['lcsc']][1].append(ref)
    rows.sort(key=lambda r: fab._natural(r[0]))
    fpname = lambda p: p['fp'].split(':')[1]
    paths = {}
    paths['bom'] = os.path.join(out_dir, '%s-bom-jlcpcb.csv' % name)
    with open(paths['bom'], 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for lcsc, (p, refs) in groups.items():
            w.writerow([p['value'], ','.join(sorted(refs, key=fab._natural)), fpname(p), lcsc])
    paths['bom_pcbway'] = os.path.join(out_dir, '%s-bom-pcbway.csv' % name)
    with open(paths['bom_pcbway'], 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Item #', 'Designator', 'Qty', 'Manufacturer Part Number', 'Description', 'Value',
                    'Package/Footprint', 'Type', 'LCSC Part #', 'Side'])
        for i, (lcsc, (p, refs)) in enumerate(groups.items(), 1):
            w.writerow([i, ','.join(sorted(refs, key=fab._natural)), len(refs), p['mpn'], p['desc'], p['value'],
                        fpname(p), 'SMD', lcsc, '+'.join(sorted(sides[lcsc]))])
    paths['cpl'] = os.path.join(out_dir, '%s-cpl-jlcpcb.csv' % name)
    with open(paths['cpl'], 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(rows)
    return paths


def _read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def check_bom_cpl(panel_paths, single_dir, single_name, refmap, offsets):
    """Every copy's CPL row == the single board's fab.bom_cpl row moved by
    that copy's offset (same layer, same rotation); BOM lines == the single
    board's lines with every copy's designators; BOM and CPL list the same
    designators."""
    units = lambda s: int(round(float(s.rstrip('mm')) * 1e4))   # 0.1 um
    single = {r['Designator']: r for r in _read_csv(os.path.join(single_dir, '%s-cpl-jlcpcb.csv' % single_name))}
    panel = {r['Designator']: r for r in _read_csv(panel_paths['cpl'])}
    n = len(offsets)
    if len(panel) != n * len(single):
        raise SystemExit('panel CPL has %d rows, want %d x %d' % (len(panel), n, len(single)))
    worst = 0
    for ref, r in panel.items():
        orig, k = refmap[ref]
        s = single[orig]
        dx, dy = offsets[k]
        if dx % 100 or dy % 100:
            raise SystemExit('copy offset %s is not a whole number of 0.1 um' % (offsets[k],))
        ex = (units(s['Mid X']) + dx // 100, units(s['Mid Y']) - dy // 100)
        got = (units(r['Mid X']), units(r['Mid Y']))
        worst = max(worst, abs(got[0] - ex[0]), abs(got[1] - ex[1]))
        if got != ex or r['Layer'] != s['Layer'] or float(r['Rotation']) != float(s['Rotation']):
            raise SystemExit('CPL %s: %s, want %s moved by %s' % (ref, dict(r), dict(s), offsets[k]))
    sbom = {r['LCSC Part #']: r for r in _read_csv(os.path.join(single_dir, '%s-bom-jlcpcb.csv' % single_name))}
    pbom = {r['LCSC Part #']: r for r in _read_csv(panel_paths['bom'])}
    if set(sbom) != set(pbom):
        raise SystemExit('panel BOM parts differ from the board BOM')
    back = {(o, k): ref for ref, (o, k) in refmap.items()}
    for lcsc, r in pbom.items():
        want = sorted((back[(o, k)] for o in sbom[lcsc]['Designator'].split(',') for k in offsets), key=fab._natural)
        if r['Designator'].split(',') != want or r['Comment'] != sbom[lcsc]['Comment'] \
                or r['Footprint'] != sbom[lcsc]['Footprint']:
            raise SystemExit('panel BOM line %s does not match the board BOM line' % lcsc)
    bom_refs = sorted(d for r in pbom.values() for d in r['Designator'].split(','))
    if bom_refs != sorted(panel) or len(bom_refs) != len(set(bom_refs)):
        raise SystemExit('panel BOM and CPL designators disagree')
    pw = _read_csv(panel_paths['bom_pcbway'])
    if sorted(d for r in pw for d in r['Designator'].split(',')) != sorted(panel) or \
            any(int(r['Qty']) != len(r['Designator'].split(',')) for r in pw):
        raise SystemExit('PCBWay panel BOM disagrees with the CPL')
    return dict(rows=len(panel), per_copy=len(single), copies=n, bom_lines=len(pbom),
                max_deviation_mm=worst / 1e4, bottom_rows=sum(1 for r in panel.values() if r['Layer'] == 'Bottom'))


# ---------------------------------------------------------- Gerber check
def _gerber_objects(path):
    """(centre, signature) for every object in a Gerber or Excellon file,
    coordinates in nm as integers; D-codes, net and component attributes
    (which differ between the board and the panel) are left out."""
    from gerbonara import GerberFile, ExcellonFile
    from gerbonara.graphic_objects import Flash, Line, Arc, Region
    nm = lambda v: int(round(v * MM))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        f = ExcellonFile.open(path) if path.endswith('.drl') else GerberFile.open(path)
    out = []

    def ap(a):
        if a is None:
            return None
        t = type(a).__name__
        if t == 'ApertureMacroInstance':
            return (t, a.macro.name, tuple(round(p, 6) for p in a.parameters))
        return (t,) + tuple((k, round(getattr(a, k), 6) if isinstance(getattr(a, k), float) else getattr(a, k))
                            for k in ('w', 'h', 'diameter', 'hole_dia', 'n_vertices', 'rotation', 'plated', 'depth')
                            if hasattr(a, k))

    for o in f.objects:
        pol = getattr(o, 'polarity_dark', True)
        if isinstance(o, Flash):
            pts = [(nm(o.x), nm(o.y))]
            sig = ('F', ap(o.aperture), pol)
        elif isinstance(o, Arc):
            pts = [(nm(o.x1), nm(o.y1)), (nm(o.x2), nm(o.y2))]
            sig = ('A', ap(o.aperture), pol, nm(o.cx), nm(o.cy), o.clockwise)
        elif isinstance(o, Line):
            pts = [(nm(o.x1), nm(o.y1)), (nm(o.x2), nm(o.y2))]
            sig = ('L', ap(o.aperture), pol)
        elif isinstance(o, Region):
            pts = [(nm(x), nm(y)) for x, y in o.outline]
            arcs = tuple(None if a is None else (a[0], None if a[1] is None else (nm(a[1][0]), nm(a[1][1])))
                         for a in (o.arc_centers or []))
            sig = ('R', pol, arcs)
        else:
            raise SystemExit('%s: unknown Gerber object %s' % (path, type(o).__name__))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append((((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2), pts, sig))
    return out


def feature_discs(feats, board):
    """(x, y, r) in Gerber nm for each KiKit feature footprint: centre and
    the radius of its largest pad plus its mask opening."""
    base = board.GetDesignSettings().m_SolderMaskExpansion
    out = []
    for f in feats:
        r = 0
        for p in f.Pads():
            m = max(p.GetLocalSolderMaskMargin() or 0, f.GetLocalSolderMaskMargin() or 0, base)
            r = max(r, max(p.GetSize().x, p.GetSize().y, p.GetDrillSize().x) // 2 + m)
        out.append((f.GetPosition().x, -f.GetPosition().y, r + int(0.02 * MM)))
    return out


def _is_feature(pts, discs):
    for x, y, r in discs:
        if all((px - x) ** 2 + (py - y) ** 2 <= r * r for px, py in pts):
            return True
    return False


# two copies of a filled region are the same shape when the area they do
# not share is under this (nm^2: 1 um^2)
REGION_TOL = 1e6


def _same_object(pts, q, sig, tol):
    """One object of a copy against one of the board (both moved to the
    board): every point within `tol` (nm), or for a filled region the same
    shape (REGION_TOL)."""
    if len(q) == len(pts) and all(abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol for a, b in zip(pts, q)):
        return True
    if sig[0] == 'R' and len(pts) > 2 and len(q) > 2:
        from shapely.geometry import Polygon
        return Polygon(pts).buffer(0).symmetric_difference(Polygon(q).buffer(0)).area <= REGION_TOL
    return False


def check_gerbers(single_gdir, single_name, panel_gdir, panel_name, box, offsets, discs, margin=1.0):
    """For every layer and drill file: the objects of each copy, moved back
    by that copy's offset, are exactly the single board's objects.  Objects
    that lie wholly within a panel feature (fiducial, tooling hole, mouse
    bite, with its mask opening) are counted apart, and so is everything
    outside every copy (rails, rail text)."""
    m = int(margin * MM)
    # Gerber y is KiCad -y
    gbox = (box[0], -box[3], box[2], -box[1])
    report = {}
    for f in sorted(os.listdir(single_gdir)):
        if not f.startswith(single_name + '-') or f.endswith(('.gbrjob', '_map.gbr')) or 'Edge_Cuts' in f:
            continue
        suffix = f[len(single_name):]
        pf = os.path.join(panel_gdir, panel_name + suffix)
        if not os.path.exists(pf):
            raise SystemExit('panel has no %s' % (panel_name + suffix))
        sobj = _gerber_objects(os.path.join(single_gdir, f))
        pobj = _gerber_objects(pf)
        for c, pts, sig in sobj:
            if not (gbox[0] - m <= c[0] <= gbox[2] + m and gbox[1] - m <= c[1] <= gbox[3] + m):
                raise SystemExit('%s: an object at %s lies more than %g mm outside the board' % (f, c, margin))
        want = collections.Counter((tuple(pts), sig) for c, pts, sig in sobj)
        got = {k: collections.Counter() for k in offsets}
        extra = collections.Counter()
        for c, pts, sig in pobj:
            if _is_feature(pts, discs):
                extra['feature'] += 1
                continue
            for k, (dx, dy) in offsets.items():
                gx, gy = dx, -dy
                if gbox[0] + gx - m <= c[0] <= gbox[2] + gx + m and gbox[1] + gy - m <= c[1] <= gbox[3] + gy + m:
                    got[k][(tuple((x - gx, y - gy) for x, y in pts), sig)] += 1
                    break
            else:
                extra[sig[0]] += 1
        # Excellon coordinates have 1 um resolution (KiCad: metric, 3 decimals),
        # and holes on half-um positions round either way once moved.  Gerbers
        # (4.6, 1 nm) match to 10 nm, and a filled region by its shape
        # (_same_object): KiCad works out some outlines (a solder mask opening
        # round a rounded pad) in board coordinates, and a vertex can land a
        # few nm apart, or elsewhere on the same straight side, once the copy
        # is moved.
        tol = 1000 if suffix.endswith('.drl') else 10
        rounded = 0
        for k in offsets:
            miss, more = want - got[k], got[k] - want
            if tol and (miss or more):
                rounded += sum(more.values())
                pool = list(miss.elements())
                left = []
                for pts, sig in more.elements():
                    for i, (q, s2) in enumerate(pool):
                        if s2 == sig and _same_object(pts, q, sig, tol):
                            del pool[i]
                            break
                    else:
                        left.append((pts, sig))
                miss, more = collections.Counter(pool), collections.Counter(left)
                rounded -= len(left)
            if miss or more:
                pts = [p for key in list(miss) + list(more) for p in key[0]]
                raise SystemExit('%s copy %d differs from the board: %d objects missing, %d extra, within '
                                 'x %.3f..%.3f, y %.3f..%.3f mm (board coordinates, Gerber y)'
                                 % (suffix, k, sum(miss.values()), sum(more.values()),
                                    min(p[0] for p in pts) / MM, max(p[0] for p in pts) / MM,
                                    min(p[1] for p in pts) / MM, max(p[1] for p in pts) / MM))
        report[suffix.lstrip('-')] = dict(objects_per_copy=sum(want.values()), panel_only=dict(extra))
        if rounded:
            report[suffix.lstrip('-')]['matched_within'] = (rounded, tol)
    return report


def fiducial_keepout(panel_gdir, panel_name, fids, discs):
    """Distance (mm) from each fiducial centre to the nearest copper and
    silkscreen on its side of the panel, read from the panel Gerbers
    (the fiducial itself and the other panel features left out)."""
    from shapely.geometry import Point, Polygon, LineString
    from shapely.ops import unary_union

    def shapes(path):
        # each object's own extent, its aperture included: a region's
        # outline, else its bounding box (gerbonara evaluates aperture
        # macros; a macro's parameters are not sizes, a free polygon pad's
        # first one is its rotation)
        from gerbonara import GerberFile
        from gerbonara.graphic_objects import Region
        from gerbonara.utils import MM as GMM
        from shapely.geometry import box
        nm = lambda v: int(round(v * MM))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            f = GerberFile.open(path)
        geo = []
        for o in f.objects:
            if not getattr(o, 'polarity_dark', True):
                continue            # clear (subtracted) polarity
            if isinstance(o, Region):
                pts = [(nm(x), nm(y)) for x, y in o.outline]
            elif hasattr(o, 'x1'):
                pts = [(nm(o.x1), nm(o.y1)), (nm(o.x2), nm(o.y2))]
            else:
                pts = [(nm(o.x), nm(o.y))]
            if _is_feature(pts, discs):
                continue            # panel feature
            if isinstance(o, Region):
                geo.append(Polygon(pts).buffer(0))
            else:
                (x0, y0), (x1, y1) = o.bounding_box(GMM)
                geo.append(box(nm(x0), nm(y0), nm(x1), nm(y1)))
        return unary_union(geo)

    side = {}
    for s_, cu, silk in (('T', 'F_Cu.gtl', 'F_Silkscreen.gto'), ('B', 'B_Cu.gbl', 'B_Silkscreen.gbo')):
        side[s_] = (shapes(os.path.join(panel_gdir, '%s-%s' % (panel_name, cu))),
                    shapes(os.path.join(panel_gdir, '%s-%s' % (panel_name, silk))))
    out = {}
    for f in fids:
        cu, silk = side['B' if f.IsFlipped() else 'T']
        c = Point(f.GetPosition().x, -f.GetPosition().y)
        out[f.GetReference()] = (round(cu.distance(c) / MM, 3), round(silk.distance(c) / MM, 3))
    worst = min(min(v) for v in out.values())
    if worst < FID_KEEPOUT:
        raise SystemExit('fiducial keep-out: copper or silk within %.2f mm of a fiducial centre (%s)' % (worst, out))
    return dict(min_mm=worst, copper_silk_mm=out)


# ------------------------------------------------------------------ DRC
def drc(pcb, out_json, refill):
    """kicad-cli DRC, all severities.  refill=True refills the zones first
    (in memory only; the file is never saved), as make.py's gate does."""
    cmd = ['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', out_json]
    if os.path.exists(out_json):
        os.remove(out_json)
    subprocess.run(cmd + (['--refill-zones'] if refill else []) + [pcb], capture_output=True, text=True)
    return json.load(open(out_json))


def _drc_summary(r, copy_boxes=None):
    """Violations by (type, severity), split into those that touch a panel
    feature (a KiKit_* footprint, or a point outside every board) and the
    rest."""
    panel_lvl, board_lvl = collections.Counter(), collections.Counter()
    details = []
    for v in r['violations']:
        items = v.get('items', [])
        pl = any('KiKit_' in it.get('description', '') for it in items)
        if copy_boxes and not pl:
            pts = [it['pos'] for it in items if 'pos' in it]
            pl = bool(pts) and all(not any(b[0] <= p['x'] * MM <= b[2] and b[1] <= p['y'] * MM <= b[3]
                                           for b in copy_boxes) for p in pts)
        (panel_lvl if pl else board_lvl)[(v['type'], v['severity'])] += 1
        details.append(('panel' if pl else 'board', v['type'], v['severity'], v['description'],
                        [it.get('description', '')[:80] for it in items]))
    return dict(panel=dict(panel_lvl), board=dict(board_lvl), unconnected=len(r['unconnected_items']),
                details=details)


# --------------------------------------------------------------- renders
def renders(pcb, out_dir, name, size):
    w, h = size
    width = 2000
    height = int(round(width * h / w)) + 100
    outs = []
    for side in ('top', 'bottom'):
        o = os.path.join(out_dir, '%s-%s.png' % (name, side))
        run(['kicad-cli', 'pcb', 'render', '--side', side, '--width', str(width), '--height', str(height),
             '--quality', 'high', '--use-board-stackup-colors', '--output', o, pcb])
        outs.append(o)
    return outs


# ----------------------------------------------------------------- main
def _geometry_checks(pb, box, offsets, feats, shape):
    """Panel size and rail features against the JLC numbers."""
    from kikit.substrate import Substrate
    from kikit.common import collectEdges
    from kikit.defs import Layer
    from shapely.geometry import box as sbox, Point
    sub = Substrate(collectEdges(pb, Layer.Edge_Cuts)).substrates
    x0, y0, x1, y1 = sub.bounds
    size = (round((x1 - x0) / MM, 4), round((y1 - y0) / MM, 4))
    if not (MIN_PANEL <= min(size) and max(size) <= MAX_PANEL):
        raise SystemExit('panel is %.2f x %.2f mm; JLCPCB Standard PCBA takes %g-%g mm' % (size + (MIN_PANEL, MAX_PANEL)))
    from shapely.affinity import translate
    boards = [translate(shape, dx, dy) for dx, dy in offsets.values()]
    for b_ in boards:
        # 1 um: KiKit re-segments the outline's arcs, a few nm off the source's
        if not sub.buffer(1000).contains(b_):
            raise SystemExit('a board copy is not inside the panel outline')
    fid = [f for f in feats if f.GetReference().startswith('KiKit_FID')]
    tool = [f for f in feats if f.GetReference().startswith('KiKit_TO')]
    mb = [f for f in feats if f.GetReference().startswith('KiKit_MB')]
    pt = lambda f: Point(f.GetPosition().x, f.GetPosition().y)
    res = dict(size_mm=size, fiducials=len(fid), tooling_holes=len(tool), mousebite_holes=len(mb))
    res['fid_to_board_edge_mm'] = round(min(pt(f).distance(b_) for f in fid for b_ in boards) / MM, 3)
    res['fid_opening_to_rail_edge_mm'] = round(min(sub.boundary.distance(pt(f)) for f in fid) / MM - FID_OPENING / 2, 3)
    res['tooling_web_mm'] = round(min(sub.boundary.distance(pt(f)) for f in tool) / MM - TOOL_DRILL / 2, 3)
    res['fid_to_tooling_edge_mm'] = round(min(pt(f).distance(pt(t)) for f in fid for t in tool) / MM - TOOL_DRILL / 2, 3)
    texts = [d for d in pb.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)]
    tb = [sbox(t.GetBoundingBox().GetX(), t.GetBoundingBox().GetY(), t.GetBoundingBox().GetRight(),
               t.GetBoundingBox().GetBottom()) for t in texts]
    res['text_to_fid_mm'] = round(min(pt(f).distance(t) for f in fid for t in tb) / MM, 3) if tb else None
    res['text_to_board_mm'] = round(min(t.distance(b_) for t in tb for b_ in boards) / MM, 3) if tb else None
    # mouse-bite holes: outside every board, never cutting into it
    res['mousebite_into_board_mm'] = round(max(MB_DRILL / 2 - min(pt(f).distance(b_) for b_ in boards) / MM
                                               for f in mb), 4)
    fails = []
    if res['fid_opening_to_rail_edge_mm'] < 0.1: fails.append('fiducial mask opening at a rail edge')
    if res['tooling_web_mm'] < 1.0: fails.append('tooling hole too close to the panel edge')
    if res['fid_to_tooling_edge_mm'] < FID_KEEPOUT: fails.append('tooling hole in a fiducial keep-out')
    if tb and res['text_to_fid_mm'] < FID_KEEPOUT: fails.append('rail text in a fiducial keep-out')
    if tb and res['text_to_board_mm'] < 1.0: fails.append('rail text near a board')
    if res['mousebite_into_board_mm'] > 1e-3: fails.append('mouse-bite holes cut into a board')
    if len(fid) != 6 or len(tool) != 4: fails.append('want 3+3 fiducials and 4 tooling holes')
    if fails:
        raise SystemExit('panel geometry: ' + '; '.join(fails) + ' %s' % res)
    return res


def make_panel(board_pcb, out_dir, name, cols=3, rows=2, board_name=None, rails='tb', verify=True, render=True):
    """Panel of cols x rows copies of board_pcb with rails, tabs, fiducials
    and tooling holes, plus its Gerbers, BOM, CPL and renders, in out_dir.

    board_pcb   finished single board (its .kicad_pro/.kicad_dru/fp-lib-table beside it)
    name        base name of the outputs: <name>-panel.kicad_pcb, <name>-panel-gerbers.zip, ...
    board_name  'fc' or 'esc' (circuit.py / parts.py key); default: the board's folder name
    rails       'tb' (rails top and bottom), 'lr' or 'frame'

    Returns a summary dict; raises SystemExit if any check fails."""
    board_pcb = os.path.abspath(board_pcb)
    board_name = board_name or os.path.basename(os.path.dirname(board_pcb))
    os.makedirs(out_dir, exist_ok=True)
    pname = name + '-panel'
    panel_pcb = os.path.join(out_dir, pname + '.kicad_pcb')

    src = pcbnew.LoadBoard(board_pcb)
    box = _outline(src)
    bw, bh = _mm(box[2] - box[0]), _mm(box[3] - box[1])
    W = cols * bw + (cols - 1) * GAP + (2 * (GAP + RAIL) if rails in ('lr', 'frame') else 0)
    H = rows * bh + (rows - 1) * GAP + (2 * (GAP + RAIL) if rails in ('tb', 'frame') else 0)
    if min(W, H) < MIN_PANEL or max(W, H) > MAX_PANEL:
        raise SystemExit('%d x %d of a %.1f x %.1f mm board with %s rails is %.1f x %.1f mm; JLCPCB Standard '
                         'PCBA needs %g-%g mm (try cols=3, rows=2 or rails="frame")'
                         % (cols, rows, bw, bh, rails, W, H, MIN_PANEL, MAX_PANEL))

    refmap, grid, info = build_panel(board_pcb, panel_pcb, name, cols, rows, rails)
    _finish_files(board_pcb, panel_pcb, out_dir)

    # The panel keeps the board's zone fills exactly as committed (KiKit
    # copies them; refilling moves fill edges by a few um, differently per
    # copy, from arc approximation).  DRC runs on that copper, and once more
    # on a refill, as make.py's gate does.
    pdrc = drc(panel_pcb, os.path.join(out_dir, pname + '-drc.json'), refill=False)
    pdrc_r = drc(panel_pcb, os.path.join(out_dir, pname + '-drc-refilled.json'), refill=True)

    pb = pcbnew.LoadBoard(panel_pcb)
    offsets, feats = copies(pb, src, refmap)
    zp, gfiles = fab.gerbers(panel_pcb, out_dir, pname)
    paths = bom_cpl(pb, src, board_name, refmap, out_dir, pname)
    out = dict(panel=panel_pcb, gerbers_zip=zp, gerber_files=gfiles, **paths, copies=len(offsets),
               grid='%d cols x %d rows' % (cols, rows), tabs=info, offsets_mm={k: (_mm(d[0]), _mm(d[1]))
                                                                               for k, d in offsets.items()})
    copy_boxes = [(box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy) for dx, dy in offsets.values()]
    out['drc'] = _drc_summary(pdrc, copy_boxes)
    out['drc_refilled'] = _drc_summary(pdrc_r, copy_boxes)

    if verify:
        out['geometry'] = _geometry_checks(pb, box, offsets, feats, _shape(src))
        with tempfile.TemporaryDirectory() as tmp:
            # the single board's own outputs, made by fab exactly as make.py makes them
            fab.gerbers(board_pcb, tmp, name)
            fab.bom_cpl(board_pcb, tmp, name, board_name)
            out['cpl_check'] = check_bom_cpl(paths, tmp, name, refmap, offsets)
            discs = feature_discs(feats, pb)
            out['gerber_check'] = check_gerbers(os.path.join(tmp, 'gerbers'), name, os.path.join(out_dir, 'gerbers'),
                                                pname, box, offsets, discs)
            out['fiducial_keepout'] = fiducial_keepout(
                os.path.join(out_dir, 'gerbers'), pname,
                [f for f in feats if f.GetReference().startswith('KiKit_FID')], discs)
            out['drc_board'] = _drc_summary(drc(board_pcb, os.path.join(tmp, 'drc.json'), refill=False))
            out['drc_board_refilled'] = _drc_summary(drc(board_pcb, os.path.join(tmp, 'drc-r.json'), refill=True))
        # every board-level violation of the panel must be one the board itself has, once per copy
        n = len(offsets)
        for p, b in (('drc', 'drc_board'), ('drc_refilled', 'drc_board_refilled')):
            want = {k: v * n for k, v in out[b]['board'].items()}
            if out[p]['board'] != want or out[p]['unconnected'] != out[b]['unconnected'] * n:
                raise SystemExit('panel %s: board-level results %s (+%d unconnected) are not %d x the board\'s own '
                                 '%s (+%d)' % (p, out[p]['board'], out[p]['unconnected'], n, out[b]['board'],
                                               out[b]['unconnected']))
    if render:
        out['images'] = renders(panel_pcb, out_dir, pname, (W, H))
    return out


def _print(out):
    print('  panel %s: %s, %d copies, %s mm' % (os.path.basename(out['panel']), out['grid'], out['copies'],
                                                 out.get('geometry', {}).get('size_mm')))
    for ax, p in out['tabs']['plan'].items():
        print('  tabs along %s edges at %s mm (margins part/copper %s mm)%s' % (
            'top/bottom' if ax == 'x' else 'left/right', p['centres'], p['margins'],
            '' if p['spread'] else '  WARNING: no room to spread them along the edge'))
    if out['tabs']['overhang_parts']:
        print('  parts overhanging the board edge: %s' % ', '.join(out['tabs']['overhang_parts']))
    for key, what in (('drc_board', 'board DRC'), ('drc_board_refilled', 'board DRC, zones refilled'),
                      ('drc', 'panel DRC'), ('drc_refilled', 'panel DRC, zones refilled')):
        if key in out:
            d = out[key]
            print('  %-27s board-level %s, panel-level %s, %d unconnected'
                  % (what + ':', d['board'] or 'none', d['panel'] or 'none', d['unconnected']))
    for det in out['drc']['details']:
        print('     %s' % (det,))
    if 'cpl_check' in out:
        print('  CPL/BOM check: %s' % out['cpl_check'])
        print('  Gerber check: every copy identical to the board on %d layers/drill files' % len(out['gerber_check']))
        for k, v in out['gerber_check'].items():
            print('     %-22s %5d objects per copy; panel-only %s%s' % (
                k, v['objects_per_copy'], v['panel_only'],
                ('; %d objects (all copies) equal to within %d nm' % v['matched_within'])
                if v.get('matched_within') else ''))
        print('  geometry: %s' % out['geometry'])
        print('  fiducial keep-out (copper, silk) from the Gerbers: %s' % out['fiducial_keepout'])
    print('  wrote %s' % ', '.join(os.path.basename(out[k]) for k in ('gerbers_zip', 'bom', 'bom_pcbway', 'cpl')))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Production panel of one board.')
    ap.add_argument('board', help="'fc', 'esc' or a .kicad_pcb path")
    ap.add_argument('out_dir')
    ap.add_argument('--name', help='output base name (default: the board file name)')
    ap.add_argument('--board', dest='board_name', help="circuit.py board key, 'fc' or 'esc'")
    ap.add_argument('--cols', type=int, default=3)
    ap.add_argument('--rows', type=int, default=2)
    ap.add_argument('--rails', default='tb', choices=['tb', 'lr', 'frame'])
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--no-render', action='store_true')
    a = ap.parse_args()
    boards = {'fc': 'ridge3-fc', 'esc': 'ridge3-esc'}
    if a.board in boards:
        pcb, board_name = os.path.join(V1, a.board, boards[a.board] + '.kicad_pcb'), a.board
    else:
        pcb, board_name = a.board, a.board_name
    name = a.name or os.path.splitext(os.path.basename(pcb))[0]
    o = make_panel(pcb, a.out_dir, name, a.cols, a.rows, board_name, a.rails, not a.no_verify, not a.no_render)
    _print(o)
    print('panel done')
