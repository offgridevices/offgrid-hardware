"""Canary v1 board: placement, outline, nets, artwork. Runs inside KiCad 10.0.6
(pcbnew Python), see make.py.

Board 60 x 40 mm, 2 layers, 1.6 mm FR-4, all parts on the top side.

Two routed slots isolate the parts that measure from the parts that warm:
  - the sensor head (SGP40 + SHT40) at the right end, behind a 24 mm slot
  - the thermal tab (NTC TH1) at the bottom-left corner, behind an L of
    slots; its copper is poured on both faces, so the board laid on a battery
    pack reads the pack's surface temperature through the tab.
"""
import math, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import circuit
from models3d import MODELS

ROOT = os.path.dirname(HERE)
FPDIR = '/usr/share/kicad/footprints'
MM = pcbnew.FromMM

X0, Y0, W, H, RAD = 100.0, 100.0, 60.0, 40.0, 2.5
X1, Y1 = X0 + W, Y0 + H

# Slots: (x, y) centre-line segments, 1.0 mm wide stadiums.
SLOT_W = 1.0
SLOTS = [
    ((150.0, 104.2), (150.0, 123.0)),     # sensor head
    ((101.6, 129.5), (112.0, 129.5)),     # thermal tab, top edge
    ((115.6, 132.4), (115.6, 138.4)),     # thermal tab, right edge
]

# ref: (x, y, rotation)
PLACE = {
    'J1': (103.4, 112.0, 270),
    'D1': (109.6, 106.6, 90),
    'C1': (112.2, 107.0, 90),
    'U1': (115.2, 110.5, 0),
    'C2': (118.6, 110.5, 90),
    'R1': (109.6, 115.4, 0),
    'R2': (109.6, 117.2, 0),
    'BZ1': (125.0, 106.6, 0),
    'C13': (118.2, 103.4, 0),
    'Q1': (133.2, 105.4, 0),
    'D2': (133.2, 109.4, 0),
    'R9': (136.4, 104.0, 90),
    'R10': (136.4, 107.6, 90),
    'D3': (138.6, 102.6, 0),
    'D4': (142.8, 102.6, 0),
    'D5': (147.0, 102.6, 0),
    'R11': (138.6, 105.6, 90),
    'R12': (142.8, 105.6, 90),
    'R13': (147.0, 105.6, 90),
    'U2': (128.0, 121.0, 0),
    'C3': (120.4, 118.6, 90),
    'C4': (120.4, 123.4, 90),
    'C5': (134.6, 123.8, 90),
    'C6': (134.6, 120.4, 90),
    'R3': (125.4, 114.2, 0),
    'R4': (137.6, 111.6, 0),
    'R5': (137.6, 113.4, 0),
    'U5': (143.6, 121.0, 0),
    'C9': (140.6, 128.4, 0),
    'C10': (144.4, 128.4, 0),
    'U3': (155.4, 107.6, 0),
    'C7': (155.4, 111.4, 0),
    'U4': (155.4, 118.4, 0),
    'C8': (155.4, 121.0, 0),
    'TH1': (106.0, 135.2, 0),
    'C11': (109.4, 135.2, 90),
    'R6': (118.4, 128.0, 90),
    'J3': (124.6, 134.9, 0),
    'R7': (131.0, 133.4, 90),
    'R8': (131.0, 137.2, 90),
    'C12': (133.2, 137.2, 90),
    'J2': (136.8, 133.2, 0),
    'TP1': (145.0, 131.0, 0),
    'TP2': (147.6, 131.0, 0),
    'TP3': (150.2, 131.0, 0),
    'SW1': (146.2, 136.4, 0),
    'R14': (152.8, 134.2, 90),
    'H1': (103.6, 103.6, 0),
    'H2': (156.6, 136.6, 0),
    'FID1': (110.2, 102.2, 0),
    'FID2': (158.0, 102.0, 0),
    'FID3': (152.6, 138.4, 0),
}


# Ground vias that tie the thermal tab's top and bottom copper together.
TAB_VIAS = [(102.6, 132.0), (105.0, 132.0), (107.4, 132.0), (110.0, 132.0), (112.6, 132.0),
            (102.6, 137.6), (105.0, 137.6), (107.4, 137.6), (110.0, 137.6), (112.6, 137.6),
            (112.6, 134.8), (102.6, 134.8)]


VIA_D, VIA_DRILL = 0.6, 0.3
GLOBAL_NETS = ('GND', '+3V3', 'VBUS')


def _via(b, net, x, y):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL))
    v.SetNet(net); v.SetLocked(True)
    b.Add(v)
    return v


def _track(b, net, a, c, w=0.4):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I_MM(*a)); t.SetEnd(pcbnew.VECTOR2I_MM(*c))
    t.SetWidth(MM(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True)
    b.Add(t)


def _inside_slot_zone(x, y, m):
    h = SLOT_W / 2 + m
    for (ax, ay), (cx, cy) in SLOTS:
        if min(ax, cx) - h <= x <= max(ax, cx) + h and min(ay, cy) - h <= y <= max(ay, cy) + h:
            return True
    return False


def _rect_dist(px, py, bb):
    dx = max(bb[0] - px, 0, px - bb[2]); dy = max(bb[1] - py, 0, py - bb[3])
    return math.hypot(dx, dy)


# Exposed pads tied to ground through vias in the pad (fab: tent/plug vias)
EP_VIAS = {('U5', '21'): [(-1.2, -1.2), (1.2, -1.2), (-1.2, 1.2), (1.2, 1.2)]}
# SHT40: its footprint keeps copper out from under the sensor, so every pad
# must be entered straight from outside the body. Fixed stubs do that; the
# router finishes from their ends. (ref, pad): end point, footprint frame.
STUBS = {('U4', '1'): (-1.7, -0.4), ('U4', '2'): (-1.7, 0.4), ('U4', '3'): (1.7, 0.4)}
FANOUT_DIR = {('U4', '4'): 0.0}     # degrees: straight out to the right

# Short same-net straps from an exposed pad to its ground pin
EP_STRAPS = {'U3': [((0.3, 0.8), (1.15, 0.8)), ((-0.3, 0.0), (-1.15, 0.0))]}


def fanout(b, net_name='GND'):
    """A via next to every ground pad, so ground needs no routing: the
    bottom layer is a solid ground plane and the top is poured too."""
    net = b.FindNet(net_name)
    pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
    obst = []   # (bbox, netcode)
    for p in pads:
        bb = p.GetBoundingBox()
        obst.append(((bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6),
                     p.GetNetCode(), (p.GetParentFootprint().GetReference(), p.GetNumber())))
    vias = [(x, y) for x, y in TAB_VIAS]
    placed = []

    def ok(x, y, own):
        if not (X0 + 1.0 <= x <= X1 - 1.0 and Y0 + 1.0 <= y <= Y1 - 1.0):
            return False
        if _inside_slot_zone(x, y, 0.75):
            return False
        for bb, code, key in obst:
            if key == own:
                continue
            gap = 0.25 if code != net.GetNetCode() else 0.15
            if _rect_dist(x, y, bb) < VIA_D / 2 + gap:
                return False
        for vx, vy in vias:
            if math.hypot(x - vx, y - vy) < VIA_D + 0.3:
                return False
        return True

    def track_ok(a, e, own, w):
        n = max(2, int(math.hypot(e[0] - a[0], e[1] - a[1]) / 0.05))
        for i in range(n + 1):
            x = a[0] + (e[0] - a[0]) * i / n; y = a[1] + (e[1] - a[1]) * i / n
            for bb, code, key in obst:
                if key == own or code == net.GetNetCode():
                    continue
                if _rect_dist(x, y, bb) < w / 2 + 0.22:
                    return False
        return True

    for fp in b.GetFootprints():
        ref = fp.GetReference()
        c = fp.GetPosition()
        cx, cy = c.x / 1e6, c.y / 1e6
        for p in fp.Pads():
            if p.GetNetCode() != net.GetNetCode() or p.HasHole():
                continue
            if (ref, p.GetNumber()) in EP_VIAS:
                for dx, dy in EP_VIAS[(ref, p.GetNumber())]:
                    _via(b, net, cx + dx, cy + dy); vias.append((cx + dx, cy + dy))
                continue
            if ref == 'U3' and p.GetNumber() == '7':
                continue
            px, py = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
            bb = p.GetBoundingBox()
            hw, hh = bb.GetWidth() / 2e6, bb.GetHeight() / 2e6
            # prefer directions pointing away from the footprint centre
            ang0 = math.degrees(math.atan2(py - cy, px - cx)) if (px, py) != (cx, cy) else 90
            ang0 = round(ang0 / 90.0) * 90.0 if abs(((ang0 + 45) % 90) - 45) < 30 else ang0
            dirs = (0, 45, -45, 90, -90, 135, -135, 180)
            if (ref, p.GetNumber()) in FANOUT_DIR:
                ang0, dirs = FANOUT_DIR[(ref, p.GetNumber())], (0,)
            done = False
            for dist_extra in (0.45, 0.8, 1.2, 1.7):
                for k in dirs:
                    a = math.radians(ang0 + k)
                    ux, uy = math.cos(a), math.sin(a)
                    # distance from pad centre to its edge along (ux,uy)
                    t = min(hw / abs(ux) if abs(ux) > 1e-6 else 1e9, hh / abs(uy) if abs(uy) > 1e-6 else 1e9)
                    d = t + dist_extra
                    x, y = round(px + ux * d, 3), round(py + uy * d, 3)
                    own = (ref, p.GetNumber())
                    if ok(x, y, own) and track_ok((px, py), (x, y), own, min(0.4, 2 * min(hw, hh))):
                        _via(b, net, x, y)
                        _track(b, net, (px, py), (x, y), w=min(0.4, 2 * min(hw, hh)))
                        vias.append((x, y)); placed.append((ref, p.GetNumber()))
                        done = True
                        break
                if done:
                    break
            if not done:
                print('fanout: no room next to', ref, p.GetNumber())
    for (ref, pad), (ex, ey) in STUBS.items():
        fp = b.FindFootprintByReference(ref)
        pd = [q for q in fp.Pads() if q.GetNumber() == pad][0]
        c = fp.GetPosition()
        a = (pd.GetPosition().x / 1e6, pd.GetPosition().y / 1e6)
        _track(b, pd.GetNet(), a, (c.x / 1e6 + ex, c.y / 1e6 + ey), w=0.25)
    for ref, straps in EP_STRAPS.items():
        fp = b.FindFootprintByReference(ref)
        c = fp.GetPosition()
        for a, e in straps:
            _track(b, net, (c.x / 1e6 + a[0], c.y / 1e6 + a[1]), (c.x / 1e6 + e[0], c.y / 1e6 + e[1]), w=0.3)
    return placed


NETLIST = os.path.join(ROOT, 'out', 'canary.net')


def schematic_nets(path):
    sys.path.insert(0, HERE)
    from sexpr import parse, find, findall
    root = parse(open(path).read())
    out = {}
    for n in findall(find(root, 'nets'), 'net'):
        out[find(n, 'name')[1]] = [(find(x, 'ref')[1], find(x, 'pin')[1]) for x in findall(n, 'node')]
    return out


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(ROOT, 'canary.pretty') if lib == 'canary' else os.path.join(FPDIR, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit('footprint not found: ' + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def seg(b, a, c, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I_MM(*a)); s.SetEnd(pcbnew.VECTOR2I_MM(*c))
    s.SetLayer(layer); s.SetWidth(MM(w))
    b.Add(s)


def arc(b, centre, start, angle, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(pcbnew.VECTOR2I_MM(*centre))
    s.SetStart(pcbnew.VECTOR2I_MM(*start))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T), True)
    s.SetLayer(layer); s.SetWidth(MM(w))
    b.Add(s)


def outline(b):
    r = RAD
    seg(b, (X0 + r, Y0), (X1 - r, Y0)); seg(b, (X1, Y0 + r), (X1, Y1 - r))
    seg(b, (X1 - r, Y1), (X0 + r, Y1)); seg(b, (X0, Y1 - r), (X0, Y0 + r))
    arc(b, (X1 - r, Y0 + r), (X1 - r, Y0), 90)
    arc(b, (X1 - r, Y1 - r), (X1, Y1 - r), 90)
    arc(b, (X0 + r, Y1 - r), (X0 + r, Y1), 90)
    arc(b, (X0 + r, Y0 + r), (X0, Y0 + r), 90)
    h = SLOT_W / 2
    for (ax, ay), (cx, cy) in SLOTS:
        if ax == cx:       # vertical
            seg(b, (ax - h, ay), (ax - h, cy)); seg(b, (ax + h, ay), (ax + h, cy))
            arc(b, (ax, ay), (ax - h, ay), 180)   # top cap
            arc(b, (cx, cy), (cx + h, cy), 180)   # bottom cap
        else:              # horizontal
            seg(b, (ax, ay - h), (cx, cy - h)); seg(b, (ax, ay + h), (cx, cy + h))
            arc(b, (ax, ay), (ax, ay + h), 180)
            arc(b, (cx, cy), (cx, cy - h), 180)


def text(b, s, x, y, size=1.0, layer=pcbnew.F_SilkS, thick=0.15, bold=False, mirror=False,
         justify=None):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I_MM(size, size))
    t.SetTextThickness(MM(thick))
    t.SetBold(bold)
    if mirror:
        t.SetMirrored(True)
    if justify == 'left':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    b.Add(t)


def zone(b, net, layer, pts, prio=0, name=None):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(net)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(MM(x), MM(y))
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.25))
    z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3))
    z.SetThermalReliefSpokeWidth(MM(0.35))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name:
        z.SetZoneName(name)
    b.Add(z)
    return z


def slot_keepouts(b, margin=0.45):
    """Rule areas round each slot so the autorouter keeps tracks and vias at
    the fab's edge clearance from the routed slot (it sees only the outer
    outline)."""
    h = SLOT_W / 2 + margin
    for (ax, ay), (cx, cy) in SLOTS:
        z = pcbnew.ZONE(b)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        x0, x1 = min(ax, cx) - h, max(ax, cx) + h
        y0, y1 = min(ay, cy) - h, max(ay, cy) + h
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(MM(x), MM(y))
        b.Add(z)


def board_rules(b):
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.15)
    ds.m_MinClearance = MM(0.15)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleToHoleMin = MM(0.25)


def build(path):
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(2)
    board_rules(b)
    # Nets come from the schematic's own netlist export (what KiCad's
    # "Update PCB from Schematic" would apply), so board and schematic agree
    # by construction; check_netlist.py has already proved that netlist
    # equals circuit.py.
    nets, pinnet = {}, {}
    for name, nodes in schematic_nets(NETLIST).items():
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        nets[name.lstrip('/')] = ni
        for ref, pin in nodes:
            pinnet[(ref, pin)] = ni
    for p in circuit.PARTS:
        fp = load_fp(p['fp'])
        fp.SetReference(p['ref'])
        if p['ref'] in MODELS:
            # KiCad 10.0.6 has no 3D model for this part: use ours (src/models3d.py)
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = '${KIPRJMOD}/canary.3dshapes/' + MODELS[p['ref']]
            fp.Models().append(m)
        fp.SetValue(p['value'])
        x, y, rot = PLACE[p['ref']]
        b.Add(fp)
        fp.SetPosition(pcbnew.VECTOR2I_MM(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            ni = pinnet.get((p['ref'], pad.GetNumber()))
            if ni:
                pad.SetNet(ni)
        for k in ('MPN', 'Manufacturer', 'LCSC', 'Description'):
            v = p[{'MPN': 'mpn', 'Manufacturer': 'mfr', 'LCSC': 'lcsc', 'Description': 'desc'}[k]]
            fp.SetField(k, v)
            if fp.GetField(k):
                fp.GetField(k).SetVisible(False)
        # small, tidy reference designators; the fab drawing carries them,
        # silkscreen keeps only what a user needs
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        if not p['bom']:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
        if p['ref'].startswith(('H', 'FID', 'TP', 'J2')):
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    outline(b)
    slot_keepouts(b)
    for x, y in TAB_VIAS:
        _via(b, nets['GND'], x, y)
    fanout(b)
    b.Save(path)
    return b


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out', 'placed.kicad_pcb'))
