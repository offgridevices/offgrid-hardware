#!/usr/bin/env python3
"""Spots for the ESC MCU's small parts on top (esc_layout.template).

Each channel's MCU (AT32F421, QFN-28, on the bottom) has fourteen small
parts on the top over it: its supply and reset capacitors, the
thermistor's bias, the three back-EMF low legs and the neutral star, the
current filter (resistor and capacitor, between the amplifier's output
and the MCU's pin) and the two SWD test points.  With them: the back-EMF
dividers' 20k legs (over the driver on their switch-node sense pins, or
by the MCU with their phase pads on the sense lines) and the FETs'
thermistor by phase C's high side.  This searches
their spots and turns in the template channel's frame (simulated
annealing on a 0.05 mm grid) on a board built with the rest of the
layout as it is.

Hard rules (each broken one costs heavily):
  * courtyards clear of each other and of every other part's top
    courtyard (all four channels, as the template channel's routing sees
    them);
  * pads 0.1 mm clear of other nets' pads and top tracks, and of other
    nets' vias by the via's ring plus 0.1 mm or its hole plus 0.2 mm, the
    larger (JLCPCB multilayer hole to copper);
  * the MCU pins' escape vias where the build puts them: each pin's pad
    end taken in pin order round the chip, inner first where its net lies
    across the chip (esc_layout.across), the other end where its
    neighbour took that one (escape_pins);
  * each GND pad's plane via, laid as the build's fanout lays it, in its
    order (the channel's parts' pads, the driver's and the MCU's exposed
    pads): in the pad, else a stub to a plane via in reach, else on
    fanout's rings round the pad with a stub out; each net's clearance
    on every layer, 0.2 mm hole to copper, 0.25 mm hole to hole, its
    turned copies 0.6 mm from the other channels' vias (plane_spot,
    ep_spots: on the boards built so far they land where the build put
    them);
  * a pad with no via spot in reach not walled in on the top (walled);
  * the parts inside the channel's area (the middle above, the next
    channel's region left of it).
Cost: per net, the minimum spanning tree over its terminals (pin vias,
the parts' pads, other parts' pads and vias nearby), plus three times the distance
from each capacitor's supply pad (and the reset capacitor's NRST pad) to
its own pin's via, plus, with the trees' edges taken as straight top
tracks, each crossing of two nets' tracks (CROSS_W) and each track through
another net's pad or via (BLOCK_W): the top is the one layer the parts'
pads are on, and under the chip there is hardly a spot for a via to take
a track round.  The edges that count are the short ones (LOCAL), and
those from a pad with no spot for its own via within VIA_REACH (through
vias only: none over the chips' exposed pads, in the power copper's
keepouts, outside the channel's region or by other nets' copper), which
run on top to the nearest spot that takes one (and add that length), and
the plane vias' stubs; each mm of them costs TOP_W more.

    python3.12 tools/mcu_cluster_search.py BOARD [--seed N] [--iters N] [--out FILE]
                                              [--reserve ROUTED] [--start JSON] [--t0 T]
                                              [--cross-w MM] [--block-w MM]

BOARD: an ESC board built by esc_layout.build(path, route=False): the
copper laid before the routing, which stays wherever the parts go (with
route_local's lines, which follow the parts, the search would take them
for fixed).  ROUTED: a board esc_layout.build routed (route_local's lines
all laid): its driver lines to the FET row are kept as fixed copper, a
way through the strip the parts' vias would otherwise close (each of
three searches without it walled a phase's sense and gate lines in).
Prints the template lines to paste into
esc_layout.template(), and writes them as JSON to --out.  The search is
seeded: the same board, seed and count give the same spots.
"""
import argparse, json, math, os, random, sys
import numpy as np
import shapely
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
import pcbnew, pcb, parts, circuit
import esc_layout as E

ROLES = ['C_VDD', 'C_VDDA', 'C_RST', 'R_NTB', 'RS_A', 'RS_B', 'RS_C', 'RBL_A', 'RBL_B', 'RBL_C', 'TP_DIO', 'TP_CLK',
         'C_IF', 'R_IF', 'RBH_A', 'RBH_B', 'RBH_C', 'RT']
# the nets of the cluster, in channel 1 (and the planes')
NETS = {'M1_' + n for n in ('NRST', 'DVDD', 'CMP_A', 'CMP_B', 'CMP_C', 'NEUTRAL', 'NTC', 'ISENSE', 'IOUT',
                            'SWDIO', 'SWCLK', 'A', 'B', 'C')} | {'GND'}
AREA = (-9.6, 3.0, 3.8, 10.6)             # template frame, what the search looks at
# courtyards inside these (left, top, right, bottom): the MCU's parts over
# it, the back-EMF resistors anywhere over the two chips (over the driver
# on its switch-node sense pins, or by the MCU on a tap of those lines),
# the thermistor by phase C's high side, short of its drain's vias
BOUNDS = {None: (-8.9, 3.95, -2.2, 10.6),
          'RBH_A': (-8.9, 3.95, 3.6, 9.9), 'RBH_B': (-8.9, 3.95, 3.6, 9.9), 'RBH_C': (-8.9, 3.95, 3.6, 9.9),
          'RT': (-6.6, 8.9, -3.4, 10.4)}
bounds = lambda role: BOUNDS.get(role, BOUNDS[None])
PIN_VIA = (0.25, 0.15)                    # the MCU's in-pad escape vias (esc_layout.VIA_ESCAPE)
GND_VIA = (0.45, 0.25)                    # plane vias (esc_layout.VIA_INPAD, FANOUT), in the pad or
GND_CL, GND_HOLE_GAP = 0.1, 0.25          # beside it: 0.1 mm to other nets' copper, 0.25 via hole to hole
GND_PITCH = 0.6                           # a plane via beside its pad: 0.6 mm from every via (via_room)
STUB_W, SHARE = 0.25, 0.9                 # its stub, or one to a plane via already there
STEPS = (0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3, 1.7, 2.1, 2.5)   # fanout's rings round the pad
PLANE_MARGIN = 0.01                       # fanout.Obstacles.MARGIN as esc_layout.build sets it
TRACK_W = 0.1                             # the cluster's lines (esc_layout.widths)
# the maze router's view (finish.Grid): every via an obstacle at least its
# hole plus VIA_RING (esc_layout.VIA_RING: the hole-to-copper rule), each
# net's clearance, ROUTE_M of grid rounding margin
VIA_RING = 0.1
ROUTE_M = 0.03
WALL = 3.0                                # mm round a top-only pad its way out is looked for in
CAPS = (('C_VDD', '17'), ('C_VDDA', '5'), ('C_RST', '4'))
CROSS_W = 20.0                            # mm of connection a crossing of two nets' top tracks costs
BLOCK_W = 20.0                            # ... and a track through another net's pad or via
LOCAL = 2.0                               # mm: joins shorter than this are top tracks
TOP_W = 1.0                               # extra cost per mm of top track (the top over the chips is scarce)
VIA = (0.35, 0.15)                        # the routers' signal via (esc_layout.VIA_SIG)
VIA_REACH = 0.45                          # mm from a pad's edge to a via that takes it off the top
ESCAPE_REACH = 4.0                        # mm: how far a pad with none in reach looks for one
RES = 0.05                                # mm, the via spots' grid

mm = lambda v: v / 1e6
X = lambda v: mm(v) - pcb.CX


def rot_pt(x, y, r):
    """KiCad's turn: positive angles counter-clockwise on screen (y down)."""
    a = math.radians(r)
    c, s = round(math.cos(a), 9), round(math.sin(a), 9)
    return (x * c + y * s, -x * s + y * c)


def box_dist(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def circ_box(cx, cy, r, bx):
    return max(0.0, box_dist((cx, cy, cx, cy), bx) - r)


def near_pts(a, b):
    """The nearest points of two boxes (a track's ends between them)."""
    cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    pa = (min(max(cb[0], a[0]), a[2]), min(max(cb[1], a[1]), a[3]))
    pb = (min(max(pa[0], b[0]), b[2]), min(max(pa[1], b[1]), b[3]))
    return pa, pb


def seg_cross(p, q, r, s):
    """Whether segments pq and rs cross (not merely touch at an end)."""
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2, d3, d4 = o(p, q, r), o(p, q, s), o(r, s, p), o(r, s, q)
    return d1 * d2 < -1e-9 and d3 * d4 < -1e-9


def seg_box(p0, p1, bx):
    """Distance from a segment to a box (0 when they meet)."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    # clipped against the box (Liang-Barsky): any part inside meets it
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx[0]), (dx, bx[2] - x0), (-dy, y0 - bx[1]), (dy, bx[3] - y0)):
        if p == 0:
            if q < 0:
                break
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    else:
        if t0 <= t1:
            return 0.0
    ll = dx * dx + dy * dy

    def pt_seg(px, py):
        t = 0.0 if ll == 0 else min(1.0, max(0.0, ((px - x0) * dx + (py - y0) * dy) / ll))
        return math.hypot(px - x0 - t * dx, py - y0 - t * dy)
    return min([box_dist((x0, y0, x0, y0), bx), box_dist((x1, y1, x1, y1), bx)]
               + [pt_seg(cx, cy) for cx in (bx[0], bx[2]) for cy in (bx[1], bx[3])])


class Problem:
    def __init__(self, board_path, reserve=None):
        self.b = b = pcbnew.LoadBoard(board_path)
        self.comps = comps = circuit.build('esc')
        r1 = E.roles(comps, 1)
        self.r1 = r1
        self.refs = {r1[k]: k for k in ROLES}
        allp = {**parts.PARTS, **parts.PADS}
        self.cmap = cmap = {c.ref: c for c in comps}
        self.geo, self.prad = {}, {}
        for ref in self.refs:
            fp = pcb.load_fp(allp[cmap[ref].part]['fp'])
            pads = [(p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetSize(pcbnew.F_Cu).x),
                     mm(p.GetSize(pcbnew.F_Cu).y)) for p in fp.Pads() if p.GetNumber()]
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            self.geo[ref] = (pads, (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
            # each pad's corner radius (round, oval, rounded): the wall check
            # takes the pads by their real corners
            self.prad[ref] = [{pcbnew.PAD_SHAPE_CIRCLE: min(mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y)) / 2,
                               pcbnew.PAD_SHAPE_OVAL: min(mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y)) / 2,
                               pcbnew.PAD_SHAPE_ROUNDRECT: mm(p.GetRoundRectCornerRadius(pcbnew.F_Cu))}.get(p.GetShape(), 0.0)
                              for p in fp.Pads() if p.GetNumber()]
        inside = lambda x0, y0, x1, y1: x1 > AREA[0] and x0 < AREA[2] and y1 > AREA[1] and y0 < AREA[3]
        self.fix_cy, self.fix_pads, self.fix_vias, self.fix_tracks, self.terms = [], [], [], [], {}
        mcu = b.FindFootprintByReference(r1['MCU'])
        mcu_nets = set(p.GetNetname() for p in mcu.Pads())
        self._resv, self.rterms = set(), {}
        if reserve:
            self._reserve(reserve, mcu_nets)
        self._mcu_vias = [(t.GetNetname(), X(t.GetPosition().x), X(t.GetPosition().y)) for t in b.GetTracks()
                          if t.GetClass() == 'PCB_VIA' and t.GetNetname() in mcu_nets]
        for fp in b.GetFootprints():
            if fp.GetReference() in self.refs:
                continue
            if not fp.IsFlipped() and fp.GetValue() != 'HOLE':
                bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
                bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                if inside(*bx):
                    self.fix_cy.append(bx)
            for p in fp.Pads():
                x, y = X(p.GetPosition().x), X(p.GetPosition().y)
                if p.IsOnLayer(pcbnew.F_Cu):
                    bb = p.GetBoundingBox()
                    bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                    if inside(*bx):
                        self.fix_pads.append((p.GetNetname(), bx))
                if fp.GetReference() != r1['MCU'] and p.GetNetname() in NETS - {'GND'} and inside(x, y, x, y):
                    self.terms.setdefault(p.GetNetname(), []).append((x, y, x, y))
        # vias and top tracks that stay whatever the cluster does: not the
        # MCU's nets' (its escapes, recomputed below, and the lines laid
        # after placement) nor the planes' (fanned out again round the new
        # pads).  A cluster net's own (the amplifier's output escape) is
        # one of its terminals too.
        for t in b.GetTracks():
            net = t.GetNetname()
            if net == 'GND' or (net in mcu_nets and t.m_Uuid.AsString() not in self._resv):
                continue
            if t.GetClass() == 'PCB_VIA':
                x, y = X(t.GetPosition().x), X(t.GetPosition().y)
                if not inside(x, y, x, y):
                    continue
                r, dr = mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2
                self.fix_vias.append((net, x, y, max(r + 0.1, dr + 0.2)))
                if net in NETS:
                    self.terms.setdefault(net, []).append((x, y, x, y))
            elif t.GetLayer() == pcbnew.F_Cu:
                a = (X(t.GetStart().x), X(t.GetStart().y))
                e = (X(t.GetEnd().x), X(t.GetEnd().y))
                if inside(min(a[0], e[0]), min(a[1], e[1]), max(a[0], e[0]), max(a[1], e[1])):
                    self.fix_tracks.append((net, a, e, mm(t.GetWidth()) / 2))
        self.pin_vias = self._escapes(mcu)
        # the escape via the build put each pin on (escape_pins: in its pad,
        # in the build's order round the chip, or beside it where a part
        # covered the pad's spot): a part kept off it leaves it where it is.
        # A pin with none in reach keeps the model's spot.
        for pin, (net, x, y) in list(self.pin_vias.items()):
            pad = next(q for q in mcu.Pads() if q.GetNumber() == pin)
            px, py = X(pad.GetPosition().x), X(pad.GetPosition().y)
            near = [(vx, vy) for vnet, vx, vy in self._mcu_vias if vnet == net and math.hypot(vx - px, vy - py) < 1.6]
            if near:
                self.pin_vias[pin] = (net,) + min(near, key=lambda v: math.hypot(v[0] - px, v[1] - py))
        self.pin_spots = set((net, x, y) for net, x, y in self.pin_vias.values())
        # the template channel's plane vias in the area are fanned out again
        # round the new spots, in fanout's order (the board's footprints,
        # last placed first: esc_layout.plane_vias): each part's GND pads,
        # and the chips' exposed pads (fanout's grid of vias, else up to
        # two nearest the middle); a chip's GND pins join its exposed pad.
        # fan: ('part', ref, pad index) for a cluster part, ('fixed', box,
        # part centre) and ('ep', box) for the others.
        comps_ = self.comps
        mine = set(E.channel_parts(comps_)[1].values()) - E.power_refs(comps_)
        self.fan, boxes = [], []
        for c in reversed(comps_):
            if c.ref not in mine:
                continue
            fp = b.FindFootprintByReference(c.ref)
            fx, fy = X(fp.GetPosition().x), X(fp.GetPosition().y)
            gp = [p for p in fp.Pads() if p.GetNetname() == 'GND' and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
            box_of = lambda p: (X(p.GetBoundingBox().GetLeft()), X(p.GetBoundingBox().GetTop()),
                                X(p.GetBoundingBox().GetRight()), X(p.GetBoundingBox().GetBottom()))
            eps = [p for p in gp if mm(p.GetSize(pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu).x) *
                   mm(p.GetSize(pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu).y) >= 2.0]
            for p in gp:
                bx = box_of(p)
                if not (bx[2] > AREA[0] - 1 and bx[0] < AREA[2] + 1 and bx[3] > AREA[1] - 1 and bx[1] < AREA[3] + 1):
                    continue
                boxes.append(bx)
                if p in eps:
                    self.fan.append(('ep', bx))
                elif eps and min(box_dist(bx, box_of(q)) for q in eps) <= 1.2:
                    continue
                elif c.ref in self.refs:
                    k = [i for i, q in enumerate(self.geo[c.ref][0]) if q[0] == p.GetNumber()][0]
                    self.fan.append(('part', c.ref, k))
                else:
                    self.fan.append(('fixed', bx, (fx, fy)))
        inpad = lambda x, y: any(q[0] - 0.01 <= x <= q[2] + 0.01 and q[1] - 0.01 <= y <= q[3] + 0.01 for q in boxes)
        ends = set()
        for t in b.GetTracks():
            if t.GetClass() != 'PCB_VIA' and t.GetNetname() == 'GND':
                a_ = (round(X(t.GetStart().x), 3), round(X(t.GetStart().y), 3))
                e_ = (round(X(t.GetEnd().x), 3), round(X(t.GetEnd().y), 3))
                if inpad(*a_):
                    ends.add(e_)
                if inpad(*e_):
                    ends.add(a_)
        self.own_gnd = set()
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND':
                x, y = X(t.GetPosition().x), X(t.GetPosition().y)
                if inpad(x, y) or (round(x, 3), round(y, 3)) in ends:
                    self.own_gnd.add((x, y))
        self._via_spots(mcu_nets)
        self._spots, self._rules, self._obst = {}, {}, None

    def _reserve(self, path, mcu_nets):
        """route_local's lines (the driver's switch-node sense and gate
        lines to the FET row, the 3.3 V and the PWM lines between the
        chips, the channel's lines and buses to the middle: its signal
        input, battery voltage, driver enable), as the routed board `path`
        has them, onto the board as fixed copper: laid before the
        cluster's own lines, they need a way the cluster's vias and pads
        leave them, and they take the gaps and via spots the cluster's
        lines might have used.  The plane vias
        come before them (fanout): those keep to the board as built, and
        one on a reserved line costs as a blocked track."""
        b = self.b
        nets = set(r if r.startswith('ESC_') else 'M1_' + r for r in E.FIRST_LINES)
        # and the nets from the channel's parts to the shared parts in the
        # middle (the MCU's signal input, the battery-voltage and enable
        # buses), laid right after them
        parts = E.channel_parts(self.comps)
        ch1 = set(parts[1].values())
        anych = set(r for rr in parts.values() for r in rr.values())
        on = {}
        for c in self.comps:
            for n in c.pins.values():
                if n:
                    on.setdefault(n, set()).add(c.ref)
        nets |= set(n for n, rr in on.items() if rr & ch1 and rr - anych and n not in ('GND', 'VBAT'))
        k = 0
        for t in pcbnew.LoadBoard(path).GetTracks():
            if t.GetNetname() not in nets:
                continue
            if t.GetClass() == 'PCB_VIA':
                c = pcbnew.PCB_VIA(b)
                c.SetPosition(t.GetPosition()); c.SetWidth(t.GetWidth(pcbnew.F_Cu)); c.SetDrill(t.GetDrillValue())
            else:
                c = pcbnew.PCB_TRACK(b)
                c.SetStart(t.GetStart()); c.SetEnd(t.GetEnd()); c.SetWidth(t.GetWidth()); c.SetLayer(t.GetLayer())
            c.SetNet(b.FindNet(t.GetNetname()))
            b.Add(c)
            self._resv.add(c.m_Uuid.AsString())
            # its copper anchors the net's top-only pads (walled): points
            # along it, 0.1 mm apart
            if t.GetClass() == 'PCB_VIA':
                pts = [(X(t.GetPosition().x), X(t.GetPosition().y))]
            else:
                ax, ay, ex, ey = X(t.GetStart().x), X(t.GetStart().y), X(t.GetEnd().x), X(t.GetEnd().y)
                m = max(1, int(math.hypot(ex - ax, ey - ay) / 0.1))
                pts = [(ax + (ex - ax) * i / m, ay + (ey - ay) * i / m) for i in range(m + 1)]
            self.rterms.setdefault(t.GetNetname(), []).extend((x, y, x, y) for x, y in pts)
            k += 1
        self.reserved = (sorted(nets), k)

    def _via_spots(self, mcu_nets):
        """self.vok[net]: where a via of each cluster net may stand, on a
        RES grid over AREA (and 1 mm round): inside channel 1's region and
        off the copper other channels have there (stamp.region, foreign),
        outside every no-via rule area (the power copper's, the holes'),
        and clear of other nets' pads on every layer (the MCU's and the
        driver's exposed pads among them), their tracks and vias, as the
        maze router keeps a via (finish.Grid: 0.1 mm, ROUTE_M, every via at
        least its hole plus VIA_RING).  The cluster's own parts are not in
        it (via_spot)."""
        import stamp
        b = self.b
        x0, y0 = AREA[0] - 1.0, AREA[1] - 1.0
        W, H = int(round((AREA[2] - AREA[0] + 2.0) / RES)), int(round((AREA[3] - AREA[1] + 2.0) / RES))
        self.grid = (x0, y0, W, H)
        xs = x0 + (np.arange(W) + 0.5) * RES
        ys = y0 + (np.arange(H) + 0.5) * RES
        self.XX, self.YY = XX, YY = np.meshgrid(xs, ys)
        ring = VIA[0] / 2
        self.keep = keep = 0.1 + ring + ROUTE_M
        common = np.ones((H, W), bool)
        parts = E.channel_parts(self.comps)
        self._reg = reg = stamp.region(b, parts, E.CHANNELS)
        common &= shapely.contains_xy(reg.buffer(-ring), XX + pcb.CX, YY + pcb.CY)
        self._foreign = stamp.foreign(b, parts, E.CHANNELS, stamp.counterparts(b, parts, E.CHANNELS), reg)
        for l, g in self._foreign.items():
            common &= ~shapely.contains_xy(g.buffer(keep), XX + pcb.CX, YY + pcb.CY)
        E.routing_keepouts(b)
        for z in b.Zones():
            if not (z.GetIsRuleArea() and z.GetDoNotAllowVias()):
                continue
            o = z.Outline()
            for k in range(o.OutlineCount()):
                ol = o.Outline(k)
                poly = Polygon([(mm(ol.CPoint(i).x), mm(ol.CPoint(i).y)) for i in range(ol.PointCount())])
                if poly.is_valid and poly.area > 0:
                    common &= ~shapely.contains_xy(poly.buffer(ring + ROUTE_M), XX + pcb.CX, YY + pcb.CY)
        signets = sorted(NETS - {'GND'})
        self.vok = {n: common.copy() for n in signets}

        def block(net, d2):
            for n in signets:
                if n != net:
                    self.vok[n] &= d2
        for fp in b.GetFootprints():
            if fp.GetReference() in self.refs:
                continue
            for p in fp.Pads():
                if not p.IsOnCopperLayer():
                    continue
                bb = p.GetBoundingBox()
                bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                if bx[2] < x0 - keep or bx[0] > x0 + W * RES + keep or bx[3] < y0 - keep or bx[1] > y0 + H * RES + keep:
                    continue
                dx = np.maximum(np.maximum(bx[0] - XX, XX - bx[2]), 0.0)
                dy = np.maximum(np.maximum(bx[1] - YY, YY - bx[3]), 0.0)
                block(p.GetNetname(), dx * dx + dy * dy >= keep * keep)
        for t in b.GetTracks():
            net = t.GetNetname()
            if net == 'GND' or (net in mcu_nets and t.m_Uuid.AsString() not in self._resv):
                continue
            if t.GetClass() == 'PCB_VIA':
                vx, vy = X(t.GetPosition().x), X(t.GetPosition().y)
                k = max(mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2 + VIA_RING) + keep
                block(net, (XX - vx) ** 2 + (YY - vy) ** 2 >= k * k)
                continue
            ax, ay, ex, ey = X(t.GetStart().x), X(t.GetStart().y), X(t.GetEnd().x), X(t.GetEnd().y)
            k = mm(t.GetWidth()) / 2 + keep
            if max(ax, ex) < x0 - k or min(ax, ex) > x0 + W * RES + k or max(ay, ey) < y0 - k or \
                    min(ay, ey) > y0 + H * RES + k:
                continue
            dx, dy = ex - ax, ey - ay
            ll = dx * dx + dy * dy
            tt = np.clip(((XX - ax) * dx + (YY - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
            block(net, (XX - ax - tt * dx) ** 2 + (YY - ay - tt * dy) ** 2 >= k * k)
        for pin, (net, vx, vy) in self.pin_vias.items():
            k = max(PIN_VIA[0] / 2, PIN_VIA[1] / 2 + VIA_RING) + keep
            block(net, (XX - vx) ** 2 + (YY - vy) ** 2 >= k * k)
        # the copper a plane via keeps from (esc_layout.plane_vias, fanout,
        # at the time it runs: before route_local's lines), checked exactly
        # at each spot tried: other nets' pads on every layer, tracks and
        # vias (the MCU's escapes where the model puts them), each net's
        # clearance (esc_layout.clearances, fanout's NET_CL and MARGIN)
        # from the via's copper and E.HOLE_CL from its hole; via holes
        # GND_HOLE_GAP apart; its turned copies GND_PITCH from the other
        # channels' vias, so from the fixed ones here; and the copper other
        # channels have here (stamp.foreign).  A one on route_local's
        # reserved lines costs as a blocked track (resv).
        cl = E.clearances(self.comps)
        self.ncl = ncl = lambda n: max(0.1, cl.get(n, 0.1)) + PLANE_MARGIN

        def box_d2(bx):
            dx = np.maximum(np.maximum(bx[0] - XX, XX - bx[2]), 0.0)
            dy = np.maximum(np.maximum(bx[1] - YY, YY - bx[3]), 0.0)
            return dx * dx + dy * dy
        win = (AREA[0] - 4, AREA[1] - 4, AREA[2] + 4, AREA[3] + 4)
        inwin = lambda x0, y0, x1, y1: x1 > win[0] and x0 < win[2] and y1 > win[1] and y0 < win[3]
        op, ot, ov = [], [], []
        for fp in b.GetFootprints():
            if fp.GetReference() in self.refs:
                continue
            for p in fp.Pads():
                if p.GetNetname() == 'GND' or not p.IsOnCopperLayer():
                    continue
                bb = p.GetBoundingBox()
                bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                if inwin(*bx):
                    # a round, oval or rounded pad as its box shrunk by the
                    # corner radius, that radius round it
                    l = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
                    sz = p.GetSize(l)
                    r = {pcbnew.PAD_SHAPE_CIRCLE: min(mm(sz.x), mm(sz.y)) / 2,
                         pcbnew.PAD_SHAPE_OVAL: min(mm(sz.x), mm(sz.y)) / 2,
                         pcbnew.PAD_SHAPE_ROUNDRECT: mm(p.GetRoundRectCornerRadius(l))}.get(p.GetShape(), 0.0)
                    op.append((bx[0] + r, bx[1] + r, bx[2] - r, bx[3] - r, ncl(p.GetNetname()),
                               1.0 if p.IsOnLayer(pcbnew.F_Cu) else 0.0, r))
        resv = np.zeros((H, W), bool)
        gr = GND_VIA[0] / 2
        for t in b.GetTracks():
            net = t.GetNetname()
            if t.GetClass() == 'PCB_VIA':
                vx, vy = X(t.GetPosition().x), X(t.GetPosition().y)
                r, hr = mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2
                if t.m_Uuid.AsString() in self._resv:
                    resv |= (XX - vx) ** 2 + (YY - vy) ** 2 < (r + gr + ncl(net)) ** 2
                elif net == 'GND':
                    if (vx, vy) not in self.own_gnd:
                        ov.append((vx, vy, 0.0, hr, 1.0))
                elif net not in mcu_nets and inwin(vx, vy, vx, vy):
                    ov.append((vx, vy, r, hr, ncl(net)))
                continue
            if net == 'GND':
                continue
            ax, ay, ex, ey = X(t.GetStart().x), X(t.GetStart().y), X(t.GetEnd().x), X(t.GetEnd().y)
            hw = mm(t.GetWidth()) / 2
            if t.m_Uuid.AsString() in self._resv:
                dx, dy = ex - ax, ey - ay
                ll = dx * dx + dy * dy
                tt = np.clip(((XX - ax) * dx + (YY - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
                resv |= (XX - ax - tt * dx) ** 2 + (YY - ay - tt * dy) ** 2 < (hw + gr + ncl(net)) ** 2
                continue
            if inwin(min(ax, ex), min(ay, ey), max(ax, ex), max(ay, ey)):
                ot.append((ax, ay, ex, ey, hw, ncl(net), 1.0 if t.GetLayer() == pcbnew.F_Cu else 0.0))
        ov += [(vx, vy, PIN_VIA[0] / 2, PIN_VIA[1] / 2, ncl(net)) for net, vx, vy in self.pin_vias.values()]
        self.op, self.ot, self.ov = np.array(op).reshape(-1, 7), np.array(ot).reshape(-1, 7), np.array(ov).reshape(-1, 5)
        fg = [g for g in self._foreign.values()]
        from shapely.ops import unary_union
        self.fall = unary_union(fg).buffer(gr + 0.1 + PLANE_MARGIN) if fg else None
        self.ffront = self._foreign[pcbnew.F_Cu].buffer(STUB_W / 2 + 0.1 + PLANE_MARGIN) \
            if pcbnew.F_Cu in self._foreign else None
        self.resv = resv
        self.gkeep = max(GND_CL + gr, E.HOLE_CL + GND_VIA[1] / 2) + PLANE_MARGIN
        # where a top track of each cluster net may run past the fixed
        # copper, as the maze router sees it (TRACK_W, each net's
        # clearance, VIA_RING, ROUTE_M): the fixed top pads (by their real
        # corners), tracks and every via, the other channels' top copper,
        # inside the channel's region (route_local and the template's
        # routing keep each channel's lines to it): the wall check (walled)
        hw = TRACK_W / 2
        self.rcl = rcl = lambda n: max(0.1, cl.get(n, 0.1)) + ROUTE_M
        inreg = shapely.contains_xy(self._reg.buffer(-hw), XX + pcb.CX, YY + pcb.CY)
        self.tfree = {n: inreg.copy() for n in signets}
        for fp in b.GetFootprints():
            if fp.GetReference() in self.refs:
                continue
            for p in fp.Pads():
                if not p.IsOnLayer(pcbnew.F_Cu):
                    continue
                bb = p.GetBoundingBox()
                bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                if not inwin(*bx):
                    continue
                sz = p.GetSize(pcbnew.F_Cu)
                r = {pcbnew.PAD_SHAPE_CIRCLE: min(mm(sz.x), mm(sz.y)) / 2,
                     pcbnew.PAD_SHAPE_OVAL: min(mm(sz.x), mm(sz.y)) / 2,
                     pcbnew.PAD_SHAPE_ROUNDRECT: mm(p.GetRoundRectCornerRadius(pcbnew.F_Cu))}.get(p.GetShape(), 0.0)
                d2 = box_d2((bx[0] + r, bx[1] + r, bx[2] - r, bx[3] - r))
                for n in signets:
                    if p.GetNetname() != n:
                        self.tfree[n] &= d2 >= (r + hw + max(rcl(n), rcl(p.GetNetname()))) ** 2
        for t in b.GetTracks():
            net = t.GetNetname()
            if t.GetClass() == 'PCB_VIA':
                vx, vy = X(t.GetPosition().x), X(t.GetPosition().y)
                if (net == 'GND' and (vx, vy) in self.own_gnd) or not inwin(vx, vy, vx, vy) or \
                        (net in mcu_nets and t.m_Uuid.AsString() not in self._resv):
                    continue
                d2 = (XX - vx) ** 2 + (YY - vy) ** 2
                r = max(mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2 + VIA_RING)
            elif t.GetLayer() == pcbnew.F_Cu and net != 'GND':
                ax, ay, ex, ey = X(t.GetStart().x), X(t.GetStart().y), X(t.GetEnd().x), X(t.GetEnd().y)
                if not inwin(min(ax, ex), min(ay, ey), max(ax, ex), max(ay, ey)):
                    continue
                dx, dy = ex - ax, ey - ay
                ll = dx * dx + dy * dy
                tt = np.clip(((XX - ax) * dx + (YY - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
                d2 = (XX - ax - tt * dx) ** 2 + (YY - ay - tt * dy) ** 2
                r = mm(t.GetWidth()) / 2
            else:
                continue
            for n in signets:
                if net != n:
                    self.tfree[n] &= d2 >= (r + hw + max(rcl(n), rcl(net))) ** 2
        for net, vx, vy in self.pin_vias.values():
            d2 = (XX - vx) ** 2 + (YY - vy) ** 2
            for n in signets:
                if net != n:
                    self.tfree[n] &= d2 >= (max(PIN_VIA[0] / 2, PIN_VIA[1] / 2 + VIA_RING) + hw +
                                            max(rcl(n), rcl(net))) ** 2
        if pcbnew.F_Cu in self._foreign:
            fb = shapely.contains_xy(self._foreign[pcbnew.F_Cu].buffer(hw + 0.1 + ROUTE_M), XX + pcb.CX, YY + pcb.CY)
            for n in signets:
                self.tfree[n] &= ~fb
        # the plane vias that stay (a share stub may reach them)
        self.fix_gnd = [(v[0], v[1]) for v in ov if v[2] == 0.0]

    def _plane_ok(self, x, y, pads):
        """For plane vias at (x, y) (arrays): clear of the fixed copper and
        the boxes `pads` ((box, clearance)), and GND_PITCH from the fixed
        vias."""
        gr, gh = GND_VIA[0] / 2, GND_VIA[1] / 2
        ok = np.ones(len(x), bool)
        lo, hi = x.min() - 1.5, x.max() + 1.5
        lo2, hi2 = y.min() - 1.5, y.max() + 1.5
        op = self.op[(self.op[:, 2] > lo) & (self.op[:, 0] < hi) & (self.op[:, 3] > lo2) & (self.op[:, 1] < hi2)]
        boxes = [(q[:4], q[4], q[6]) for q in op] + [(bx, c, 0.0) for bx, c in pads]
        for bx, c, r in boxes:
            dx = np.maximum(np.maximum(bx[0] - x, x - bx[2]), 0.0)
            dy = np.maximum(np.maximum(bx[1] - y, y - bx[3]), 0.0)
            k = max(gr + c, gh + E.HOLE_CL) + r
            ok &= dx * dx + dy * dy >= k * k
        ot = self.ot[(np.maximum(self.ot[:, 0], self.ot[:, 2]) > lo) & (np.minimum(self.ot[:, 0], self.ot[:, 2]) < hi) &
                     (np.maximum(self.ot[:, 1], self.ot[:, 3]) > lo2) & (np.minimum(self.ot[:, 1], self.ot[:, 3]) < hi2)]
        for ax, ay, ex, ey, hw, c, _ in ot:
            dx, dy = ex - ax, ey - ay
            ll = dx * dx + dy * dy
            tt = np.clip(((x - ax) * dx + (y - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
            k = hw + max(gr + c, gh + E.HOLE_CL)
            ok &= (x - ax - tt * dx) ** 2 + (y - ay - tt * dy) ** 2 >= k * k
        ov = self.ov[(self.ov[:, 0] > lo) & (self.ov[:, 0] < hi) & (self.ov[:, 1] > lo2) & (self.ov[:, 1] < hi2)]
        for vx, vy, r, hr, c in ov:
            k = max(GND_PITCH, hr + GND_HOLE_GAP + gh, (r + gr + c) if r > 0 else 0.0)
            ok &= (x - vx) ** 2 + (y - vy) ** 2 >= k * k
        if self.fall is not None and ok.any():
            ok &= ~shapely.contains_xy(self.fall, x + pcb.CX, y + pcb.CY)
        return ok

    def via_spot(self, net, bx, pads, gnd, reach):
        """The nearest spot within `reach` of the box `bx` (in it too: a pad
        takes its own net's via) where a via of `net` fits, clear of the
        cluster's pads of other nets (`pads`) and of the vias `gnd` ((x, y,
        centre distance kept)): (distance from the box, (x, y)), or None.
        Cached: a step of the search moves one part."""
        if net not in self.vok:
            return 0.0, ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
        lo, hi = (bx[0] - reach - self.keep, bx[1] - reach - self.keep), \
            (bx[2] + reach + self.keep, bx[3] + reach + self.keep)
        near = tuple(ob for onet, ob in pads
                     if onet != net and not (ob[2] < lo[0] or ob[0] > hi[0] or ob[3] < lo[1] or ob[1] > hi[1]))
        vias = tuple((gx, gy, kk) for gx, gy, kk in gnd if lo[0] - kk < gx < hi[0] + kk and lo[1] - kk < gy < hi[1] + kk)
        key = (net, bx, reach, near, vias)
        if key not in self._spots:
            if len(self._spots) > 200000:
                self._spots.clear()
            self._spots[key] = self._via_spot(net, bx, near, vias, reach)
        return self._spots[key]

    def _via_spot(self, net, bx, near, vias, reach):
        x0, y0, W, H = self.grid
        i0, i1 = max(0, int((bx[0] - reach - x0) / RES)), min(W, int(math.ceil((bx[2] + reach - x0) / RES)))
        j0, j1 = max(0, int((bx[1] - reach - y0) / RES)), min(H, int(math.ceil((bx[3] + reach - y0) / RES)))
        XX, YY = self.XX[j0:j1, i0:i1].ravel(), self.YY[j0:j1, i0:i1].ravel()
        dx = np.maximum(np.maximum(bx[0] - XX, XX - bx[2]), 0.0)
        dy = np.maximum(np.maximum(bx[1] - YY, YY - bx[3]), 0.0)
        d2 = dx * dx + dy * dy
        cand = np.flatnonzero(self.vok[net][j0:j1, i0:i1].ravel() & (d2 <= reach * reach))
        cand = cand[np.argsort(d2[cand], kind='stable')]
        # nearest first, a batch at a time: the first that clears the
        # cluster's own copper
        keep = self.keep
        for c in range(0, len(cand), 128):
            sel = cand[c:c + 128]
            x, y = XX[sel], YY[sel]
            good = np.ones(len(sel), bool)
            for ob in near:
                ddx = np.maximum(np.maximum(ob[0] - x, x - ob[2]), 0.0)
                ddy = np.maximum(np.maximum(ob[1] - y, y - ob[3]), 0.0)
                good &= ddx * ddx + ddy * ddy >= keep * keep
            for gx, gy, k in vias:
                good &= (x - gx) ** 2 + (y - gy) ** 2 >= k * k
            if good.any():
                k = sel[int(np.argmax(good))]
                return math.sqrt(d2[k]), (float(XX[k]), float(YY[k]))
        return None

    def _cell(self, x, y):
        x0, y0, W, H = self.grid
        i, j = np.clip(((x - x0) / RES).astype(int), 0, W - 1), np.clip(((y - y0) / RES).astype(int), 0, H - 1)
        return j, i

    def _stubs_ok(self, px, py, x, y, pads):
        """For each end (x, y): whether a top stub (STUB_W) from (px, py)
        to it keeps each net's clearance from the top copper: the fixed
        pads, tracks and vias, the other channels', and the boxes `pads`
        ((box, clearance))."""
        n = int(min(80, max(4, math.ceil(max(np.hypot(x - px, y - py).max(), 0.05) / 0.05) + 1)))
        t = np.linspace(0.0, 1.0, n)[None, :]
        sx, sy = (px + (x[:, None] - px) * t).ravel(), (py + (y[:, None] - py) * t).ravel()
        sw = STUB_W / 2
        ok = np.ones(len(sx), bool)
        lo, hi, lo2, hi2 = sx.min() - 1, sx.max() + 1, sy.min() - 1, sy.max() + 1
        op = self.op[(self.op[:, 5] > 0) & (self.op[:, 2] > lo) & (self.op[:, 0] < hi) & (self.op[:, 3] > lo2) &
                     (self.op[:, 1] < hi2)]
        for bx, c, r in [(q[:4], q[4], q[6]) for q in op] + [(bx, c, 0.0) for bx, c in pads]:
            dx = np.maximum(np.maximum(bx[0] - sx, sx - bx[2]), 0.0)
            dy = np.maximum(np.maximum(bx[1] - sy, sy - bx[3]), 0.0)
            ok &= dx * dx + dy * dy >= (sw + c + r) ** 2
        ot = self.ot[(self.ot[:, 6] > 0) & (np.maximum(self.ot[:, 0], self.ot[:, 2]) > lo) &
                     (np.minimum(self.ot[:, 0], self.ot[:, 2]) < hi) & (np.maximum(self.ot[:, 1], self.ot[:, 3]) > lo2) &
                     (np.minimum(self.ot[:, 1], self.ot[:, 3]) < hi2)]
        for ax, ay, ex, ey, hw, c, _ in ot:
            dx, dy = ex - ax, ey - ay
            ll = dx * dx + dy * dy
            tt = np.clip(((sx - ax) * dx + (sy - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
            ok &= (sx - ax - tt * dx) ** 2 + (sy - ay - tt * dy) ** 2 >= (hw + sw + c) ** 2
        ov = self.ov[(self.ov[:, 2] > 0) & (self.ov[:, 0] > lo) & (self.ov[:, 0] < hi) & (self.ov[:, 1] > lo2) &
                     (self.ov[:, 1] < hi2)]
        for vx, vy, r, hr, c in ov:
            ok &= (sx - vx) ** 2 + (sy - vy) ** 2 >= (r + sw + c) ** 2
        if self.ffront is not None and ok.any():
            ok &= ~shapely.contains_xy(self.ffront, sx + pcb.CX, sy + pcb.CY)
        return ok.reshape(len(x), n).all(axis=1)

    def ep_spots(self, bx, pads, taken):
        """An exposed pad's plane vias, as fanout lays them: its grid
        (FANOUT ep_pitch), else (past the grid) spots on a 0.25 mm grid
        nearest its middle, up to two; each inside the pad, clear of the
        copper (_plane_ok; `pads`: the cluster's of other nets) and
        GND_PITCH from the plane vias `taken`.  None when it gets none and
        has no other plane via in it."""
        near = tuple(q for q in pads if not (q[0][2] < bx[0] - 1 or q[0][0] > bx[2] + 1 or q[0][3] < bx[1] - 1
                                             or q[0][1] > bx[3] + 1))
        tk = tuple(v for v in taken if bx[0] - 1 < v[0] < bx[2] + 1 and bx[1] - 1 < v[1] < bx[3] + 1)
        key = ('ep', bx, near, tk)
        if key not in self._spots:
            if len(self._spots) > 200000:
                self._spots.clear()
            self._spots[key] = self._ep_spots(bx, near, tk)
        return self._spots[key]

    def _ep_spots(self, bx, near, taken):
        gr = GND_VIA[0] / 2
        pitch = E.FANOUT['ep_pitch']
        w, h = bx[2] - bx[0], bx[3] - bx[1]
        nx, ny = max(1, int((w - GND_VIA[0]) / pitch) + 1), max(1, int((h - GND_VIA[0]) / pitch) + 1)
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        ox, oy = cx - (nx - 1) * pitch / 2, cy - (ny - 1) * pitch / 2
        grid = [(ox + i * pitch, oy + j * pitch) for i in range(nx) for j in range(ny)]
        m = 0.05 + gr
        fits = lambda q: bx[0] + m <= q[0] <= bx[2] - m and bx[1] + m <= q[1] <= bx[3] - m
        if len(grid) > 1 and not any(fits(q) for q in grid):
            grid = [(cx, cy)]
        fine = [(bx[0] + 0.25 * i, bx[1] + 0.25 * j) for i in range(int(w / 0.25) + 1) for j in range(int(h / 0.25) + 1)]
        fine.sort(key=lambda q: (round((q[0] - cx) ** 2 + (q[1] - cy) ** 2, 6), q))
        cand = [q for q in grid + fine]
        x, y = np.array([q[0] for q in cand]), np.array([q[1] for q in cand])
        ok = (x >= bx[0] + m) & (x <= bx[2] - m) & (y >= bx[1] + m) & (y <= bx[3] - m)
        ok &= self._plane_ok(x, y, near)
        placed = []
        for k in range(len(cand)):
            if k >= len(grid) and len(placed) >= 2:
                break
            if not ok[k]:
                continue
            q = (float(x[k]), float(y[k]))
            if all((q[0] - t[0]) ** 2 + (q[1] - t[1]) ** 2 >= GND_PITCH ** 2 for t in list(taken) + placed):
                placed.append(q)
        if not placed and not any(fits(t) for t in list(taken) + self.fix_gnd):
            return None
        return tuple(placed)

    def plane_spot(self, bx, centre, pads, taken):
        """Where the GND pad `bx` (of a part centred at `centre`) takes its
        plane via, as fanout does it: in the pad (inpad_spots: the centre,
        then along the long axis); else a stub to a plane via within SHARE;
        else a via on fanout's rings round the pad (STEPS, 15 degree steps
        from the part's centre outward) and a stub to it.  Clear of the
        copper (_plane_ok, _stubs_ok; `pads`: the cluster's of other nets,
        (box, clearance)) and of the plane vias `taken` ((x, y): placed
        before it).  Returns (stub length, (x, y), via placed), or None.
        Cached."""
        lo, hi = bx[0] - 3.5, bx[1] - 3.5
        near = tuple(q for q in pads if not (q[0][2] < lo or q[0][0] > bx[2] + 3.5 or q[0][3] < hi or
                                             q[0][1] > bx[3] + 3.5))
        tk = tuple(v for v in taken if lo < v[0] < bx[2] + 3.5 and hi < v[1] < bx[3] + 3.5)
        key = ('plane', bx, centre, near, tk)
        if key not in self._spots:
            if len(self._spots) > 200000:
                self._spots.clear()
            self._spots[key] = self._plane_spot(bx, centre, near, tk)
        return self._spots[key]

    def _plane_spot(self, bx, centre, near, taken):
        gr, gh = GND_VIA[0] / 2, GND_VIA[1] / 2
        px, py = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        w, h = bx[2] - bx[0], bx[3] - bx[1]

        def apart(x, y, pitch):
            ok = np.ones(len(x), bool)
            for tx, ty in taken:
                ok &= (x - tx) ** 2 + (y - ty) ** 2 >= pitch * pitch
            return ok
        # in the pad
        free = (max(w, h) - GND_VIA[0]) / 2
        spots = [(px, py)]
        for f in (0.5, 1.0):
            for sg in (-1, 1):
                if free * f > 0.05:
                    spots.append((px + sg * free * f, py) if w >= h else (px, py + sg * free * f))
        x, y = np.array([q[0] for q in spots]), np.array([q[1] for q in spots])
        ok = apart(x, y, 2 * gh + GND_HOLE_GAP)
        if ok.any():
            ok &= self._plane_ok(x, y, near)
        if ok.any():
            k = int(np.argmax(ok))
            return 0.0, (float(x[k]), float(y[k])), True
        # a stub to a plane via already there
        vs = [(vx, vy) for vx, vy in self.fix_gnd + list(taken) if box_dist(bx, (vx, vy, vx, vy)) <= SHARE + gr]
        if vs:
            vs.sort(key=lambda v: box_dist(bx, (v[0], v[1], v[0], v[1])))
            x, y = np.array([v[0] for v in vs]), np.array([v[1] for v in vs])
            ok = self._stubs_ok(px, py, x, y, near)
            if ok.any():
                k = int(np.argmax(ok))
                return math.hypot(x[k] - px, y[k] - py), (float(x[k]), float(y[k])), False
        # beside it, on fanout's rings
        a0 = math.atan2(py - centre[1], px - centre[0]) if abs(px - centre[0]) + abs(py - centre[1]) > 0.05 else 0.0
        reach = max(w, h) / 2
        ang = np.array([a0 + (math.pi / 12) * ((k + 1) // 2) * (1 if k % 2 else -1) for k in range(24)])
        for st in STEPS:
            d = reach + gr + GND_CL + st
            x, y = px + d * np.cos(ang), py + d * np.sin(ang)
            ok = apart(x, y, GND_PITCH)
            if ok.any():
                ok &= self._plane_ok(x, y, near)
            if ok.any():
                ok &= self._stubs_ok(px, py, x, y, near)
                if ok.any():
                    k = int(np.argmax(ok))
                    return d, (float(x[k]), float(y[k])), True
        return None

    def walled(self, net, bx, pads, gvias, gstubs, terms):
        """Whether the pad `bx` of `net`, which has no spot for a via of its
        own in reach, is walled in on the top: no way for a track from it
        (TRACK_W, each net's clearance) past the fixed copper (tfree), the
        cluster's pads of other nets (`pads`: (box, net, corner radius)) and its plane
        vias and their stubs (`gvias`, `gstubs`) to another of the net's
        terminals (`terms`: boxes), a spot for its via, or WALL away.
        Cached."""
        lo, hi = (bx[0] - WALL - 0.5, bx[1] - WALL - 0.5), (bx[2] + WALL + 0.5, bx[3] + WALL + 0.5)
        inb = lambda q: not (q[2] < lo[0] or q[0] > hi[0] or q[3] < lo[1] or q[1] > hi[1])
        near = tuple((ob, n, r) for ob, n, r in pads if n != net and inb(ob))
        gv = tuple(v for v in gvias if lo[0] < v[0] < hi[0] and lo[1] < v[1] < hi[1])
        gs = tuple(st for st in gstubs if inb((min(st[0][0], st[1][0]), min(st[0][1], st[1][1]),
                                              max(st[0][0], st[1][0]), max(st[0][1], st[1][1]))))
        tm = tuple(q for q in terms if inb(q))
        key = ('wall', net, bx, near, gv, gs, tm)
        if key not in self._spots:
            if len(self._spots) > 200000:
                self._spots.clear()
            self._spots[key] = self._walled(net, bx, near, gv, gs, tm)
        return self._spots[key]

    def _walled(self, net, bx, near, gv, gs, tm):
        from scipy import ndimage
        x0, y0, W, H = self.grid
        i0, i1 = max(0, int((bx[0] - WALL - x0) / RES)), min(W, int(math.ceil((bx[2] + WALL - x0) / RES)))
        j0, j1 = max(0, int((bx[1] - WALL - y0) / RES)), min(H, int(math.ceil((bx[3] + WALL - y0) / RES)))
        XX, YY = self.XX[j0:j1, i0:i1], self.YY[j0:j1, i0:i1]
        hw, c0 = TRACK_W / 2, self.rcl(net)
        free = self.tfree[net][j0:j1, i0:i1].copy()

        def sub(q, k):
            # the window's cells within k of the box q: (slices, X, Y)
            a0, a1 = max(0, int((q[0] - k - x0) / RES) - i0), min(i1 - i0, int(math.ceil((q[2] + k - x0) / RES)) - i0)
            b0, b1 = max(0, int((q[1] - k - y0) / RES) - j0), min(j1 - j0, int(math.ceil((q[3] + k - y0) / RES)) - j0)
            if a0 >= a1 or b0 >= b1:
                return None
            sl = (slice(b0, b1), slice(a0, a1))
            return sl, XX[sl], YY[sl]

        def d2box(q, X_, Y_):
            dx = np.maximum(np.maximum(q[0] - X_, X_ - q[2]), 0.0)
            dy = np.maximum(np.maximum(q[1] - Y_, Y_ - q[3]), 0.0)
            return dx * dx + dy * dy
        for ob, n, r in near:
            k = hw + max(c0, self.rcl(n)) + r
            w = sub(ob, k)
            if w:
                free[w[0]] &= d2box((ob[0] + r, ob[1] + r, ob[2] - r, ob[3] - r), w[1], w[2]) >= k * k
        cg = max(c0, self.rcl('GND'))
        k = GND_VIA[0] / 2 + hw + cg
        for vx, vy in gv:
            w = sub((vx, vy, vx, vy), k)
            if w:
                free[w[0]] &= (w[1] - vx) ** 2 + (w[2] - vy) ** 2 >= k * k
        k = STUB_W / 2 + hw + cg
        for (ax, ay), (ex, ey) in gs:
            w = sub((min(ax, ex), min(ay, ey), max(ax, ex), max(ay, ey)), k)
            if not w:
                continue
            dx, dy = ex - ax, ey - ay
            ll = dx * dx + dy * dy
            tt = np.clip(((w[1] - ax) * dx + (w[2] - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
            free[w[0]] &= (w[1] - ax - tt * dx) ** 2 + (w[2] - ay - tt * dy) ** 2 >= k * k
        mine = d2box(bx, XX, YY) == 0.0
        free |= mine
        lab, k = ndimage.label(free, structure=np.ones((3, 3), bool))
        ids = set(np.unique(lab[mine])) - {0}
        if not ids:
            return True
        reach = np.isin(lab, list(ids))
        if reach[0, :].any() or reach[-1, :].any() or reach[:, 0].any() or reach[:, -1].any():
            return False
        if (reach & self.vok[net][j0:j1, i0:i1]).any():
            return False
        for q in tm:
            if (reach & (d2box(q, XX, YY) <= RES * RES)).any():
                return False
        return True

    def _escapes(self, mcu):
        """{pin: (net, x, y)}: the MCU's signal pins' escape vias as the build
        places them: each edge in pin order, the preferred end (inner where
        the net lies across the chip) unless the previous pin on the edge
        took it."""
        mx, my = X(mcu.GetPosition().x), X(mcu.GetPosition().y)
        pins = [p for p in mcu.Pads() if p.GetNetname() and p.GetNetname() not in ('GND', 'VBAT')
                and p.GetNumber().isdigit()]
        inner = {num for ref, num in E.across(self.b, [(mcu.GetReference(), p.GetNumber()) for p in pins])}
        out, prev = {}, {}
        for p in sorted(pins, key=lambda q: int(q.GetNumber())):
            px, py = X(p.GetPosition().x), X(p.GetPosition().y)
            bb = p.GetBoundingBox()
            half = max(mm(bb.GetWidth()), mm(bb.GetHeight())) / 2 - PIN_VIA[0] / 2 - 0.03
            if abs(px - mx) > abs(py - my):
                edge, n = ('x', 1 if px > mx else -1), (1 if px > mx else -1, 0)
            else:
                edge, n = ('y', 1 if py > my else -1), (0, 1 if py > my else -1)
            ends = {'out': (px + n[0] * half, py + n[1] * half), 'in': (px - n[0] * half, py - n[1] * half)}
            want = ['in', 'out'] if p.GetNumber() in inner else ['out', 'in']
            last = prev.get(edge)
            end = want[1] if last is not None and last[1] == want[0] and int(p.GetNumber()) - last[0] == 1 else want[0]
            prev[edge] = (int(p.GetNumber()), end)
            out[p.GetNumber()] = (p.GetNetname(), *ends[end])
        return out

    def placed(self, ref, x, y, r):
        pads, cy = self.geo[ref]
        out = []
        for num, dx, dy, w, h in pads:
            px, py = rot_pt(dx, dy, r)
            if r % 180:
                w, h = h, w
            out.append((self.cmap[ref].pins.get(num, ''), (x + px - w / 2, y + py - h / 2, x + px + w / 2,
                                                            y + py + h / 2)))
        xs, ys = zip(*[rot_pt(a, c, r) for a, c in ((cy[0], cy[1]), (cy[2], cy[3]))])
        return out, (x + min(xs), y + min(ys), x + max(xs), y + max(ys))

    def _fixed_rules(self, a, x, y, r):
        """The rules part `a` at (x, y, r) breaks against what stays: its
        area, the fixed courtyards, and its pads against the fixed pads,
        vias, top tracks and the MCU's escape vias: [(penalty, what)].
        Cached per spot."""
        key = (a, x, y, r)
        got = self._rules.get(key)
        if got is not None:
            return got
        pads, ca = self.placed(a, x, y, r)
        role = self.refs[a]
        out = []
        bd = bounds(role)
        over = max(0.0, bd[0] - ca[0]) + max(0.0, bd[1] - ca[1]) + max(0.0, ca[2] - bd[2]) + max(0.0, ca[3] - bd[3])
        if over > 0:
            out.append((10 + 50 * over, ('area', role)))
        for c in self.fix_cy:
            o = min(ca[2], c[2]) - max(ca[0], c[0]), min(ca[3], c[3]) - max(ca[1], c[1])
            if o[0] > 0.001 and o[1] > 0.001:
                out.append((10 + 50 * min(o), ('courtyard', role)))
        for (net, bx), r in zip(pads, self.prad[a]):
            # a round or rounded pad by its real corners: the box shrunk
            # by the radius, that radius round it
            bx = (bx[0] + r, bx[1] + r, bx[2] - r, bx[3] - r)
            for onet, ob in self.fix_pads:
                if onet != net and box_dist(bx, ob) - r < 0.1:
                    out.append((10, ('pad-pad', role, onet)))
            for onet, vx, vy, keep in self.fix_vias:
                if onet != net and circ_box(vx, vy, 0.0, bx) - r < keep:
                    out.append((10, ('pad-via', role, onet)))
            for onet, p0, p1, hw in self.fix_tracks:
                if onet != net and seg_box(p0, p1, bx) - r < hw + 0.1:
                    out.append((10, ('pad-track', role, onet)))
            for pin, (pnet, vx, vy) in self.pin_vias.items():
                if pnet != net and circ_box(vx, vy, 0.0, bx) - r < max(PIN_VIA[0] / 2 + 0.1, PIN_VIA[1] / 2 + 0.2):
                    out.append((10, ('pad-pin via', role, pin)))
        if len(self._rules) > 500000:
            self._rules.clear()
        self._rules[key] = out
        return out

    def cost(self, pos, detail=False, weight=100.0):
        pl = {ref: self.placed(ref, *pos[ref]) for ref in self.refs}
        refs = list(self.refs)
        pen, why = 0.0, []

        def bad(k, *what):
            nonlocal pen
            pen += k
            why.append(what)
        for i, a in enumerate(refs):
            for k, what in self._fixed_rules(a, *pos[a]):
                bad(k, *what)
            ca = pl[a][1]
            for c in [pl[o][1] for o in refs[i + 1:]]:
                o = min(ca[2], c[2]) - max(ca[0], c[0]), min(ca[3], c[3]) - max(ca[1], c[1])
                if o[0] > 0.001 and o[1] > 0.001:
                    bad(10 + 50 * min(o), 'courtyard', self.refs[a])
        pads = [(a, net, bx) for a in refs for net, bx in pl[a][0]]
        # the plane vias, in the order fanout takes them (self.fan): a pad's
        # in the pad or at the end of a top stub (plane_spot), an exposed
        # pad's inside it (ep_spots)
        gnd, stubs, gtaken, glen = [], [], (), 0.0
        others = tuple((bx, self.ncl(net)) for a, net, bx in pads if net != 'GND')
        for item in self.fan:
            if item[0] == 'ep':
                vs = self.ep_spots(item[1], others, gtaken)
                if vs is None:
                    bad(10, 'plane via', 'exposed pad')
                    continue
                gnd.extend(vs)
                gtaken += tuple(vs)
                continue
            if item[0] == 'part':
                a = item[1]
                bx, centre = pl[a][0][item[2]][1], pos[a][:2]
            else:
                a, bx, centre = None, item[1], item[2]
            v = self.plane_spot(bx, centre, others, gtaken)
            if v is None:
                bad(10, 'plane via', self.refs.get(a, 'fixed part'))
                continue
            d, spot, new = v
            if d > 0:
                glen += d
                stubs.append(('GND', near_pts(bx, (spot[0], spot[1], spot[0], spot[1]))))
            if new:
                gnd.append(spot)
                gtaken += (spot,)
        for k, (a, net, bx) in enumerate(pads):
            for a2, net2, bx2 in pads[k + 1:]:
                if a2 != a and net2 != net and box_dist(bx, bx2) < 0.1:
                    bad(10, 'pad-pad', self.refs[a], self.refs[a2])
        terms = {net: list(v) for net, v in self.terms.items()}
        for pin, (net, vx, vy) in self.pin_vias.items():
            if net in NETS:
                terms.setdefault(net, []).append((vx, vy, vx, vy))
        for a, net, bx in pads:
            if net != 'GND':
                terms.setdefault(net, []).append(bx)
        # minimum spanning tree per net, its edges taken as straight top
        # tracks; an MCU net with two pins (the 3.3 V) is joined under the
        # chip first (esc_layout.FIRST_LINES), so its pins start joined
        length, edges = 0.0, []
        for net, ts in terms.items():
            pins = [i for i, t in enumerate(ts) if t[0] == t[2] and (net, t[0], t[1]) in self.pin_spots]
            seed = pins if len(pins) > 1 else [0]
            used = [ts[i] for i in seed]
            rest = [t for i, t in enumerate(ts) if i not in seed]
            while rest:
                d, i, u = min((box_dist(t, u), i, u) for i, t in enumerate(rest) for u in used)
                length += d
                t = rest.pop(i)
                edges.append((net, near_pts(u, t), u, t))
                used.append(t)
        # a top layer is planar: tracks of two nets that cross, or a track
        # through another net's pad or via, need a way round on another
        # layer, which under the chip has hardly a spot for a via.  The
        # short joins (LOCAL) count, and from a part's pad with no via spot
        # in reach (over the MCU's or the driver's exposed pad, say) the
        # track out to the nearest one: the rest take the inner layers.
        mine = set((net, bx) for a, net, bx in pads)
        other = [(net, bx) for a, net, bx in pads]
        kg = GND_VIA[0] / 2 + VIA[0] / 2 + 0.1
        taken0 = taken = tuple((gx, gy, kg) for gx, gy in gnd)
        top, esc = [], {}
        for n, (p, q), u, t in edges:
            if math.hypot(q[0] - p[0], q[1] - p[1]) < LOCAL:
                top.append((n, (p, q)))
                continue
            for e in (u, t):
                if (n, e) in mine and (n, e) not in esc and self.via_spot(n, e, other, taken, VIA_REACH) is None:
                    # no via in reach: a top track out to the nearest spot
                    # that takes one (ESCAPE_REACH; the spot is then taken),
                    # or the whole join on top
                    v = self.via_spot(n, e, other, taken, ESCAPE_REACH)
                    esc[(n, e)] = v and near_pts(e, (v[1][0], v[1][1], v[1][0], v[1][1]))
                    if v:
                        length += v[0]
                        taken += ((v[1][0], v[1][1], VIA[0] + 0.1),)
            if any((n, e) in esc and not esc[(n, e)] for e in (u, t)):
                top.append((n, (p, q)))
        # a pad with no via spot in reach must find a way out on the top:
        # to the net's pin via, a fixed terminal or a pad that takes a via,
        # to a via spot, or away (walled)
        nets_pads = [(bx, net, r) for a in refs for (net, bx), r in zip(pl[a][0], self.prad[a])]
        gst = tuple(pq for _, pq in stubs)
        topo = {}
        for a, net, bx in pads:
            if net == 'GND' or net not in self.vok:
                continue
            topo[(net, bx)] = self.via_spot(net, bx, other, taken0, VIA_REACH) is None
        for a, net, bx in pads:
            if not topo.get((net, bx)):
                continue
            anchors = [b2 for a2, n2, b2 in pads if n2 == net and b2 != bx and not topo.get((n2, b2))] + \
                list(self.terms.get(net, [])) + list(self.rterms.get(net, [])) + \
                [(vx - .125, vy - .125, vx + .125, vy + .125) for n2, vx, vy in self.pin_vias.values() if n2 == net]
            if self.walled(net, bx, nets_pads, tuple(gnd), gst, tuple(anchors)):
                bad(10, 'walled', self.refs[a], net)
        edges = top + [(n, pq) for (n, e), pq in esc.items() if pq] + stubs
        length += glen
        if gnd:
            gj, gi = self._cell(np.array([g[0] for g in gnd]), np.array([g[1] for g in gnd]))
            on_resv = int(self.resv[gj, gi].sum())
        else:
            on_resv = 0
        cross = 0
        for i, (n1, (p, q)) in enumerate(edges):
            for n2, (r, s_) in edges[i + 1:]:
                if n1 != n2 and seg_cross(p, q, r, s_):
                    cross += 1
        blocks = on_resv
        if self._obst is None:
            st = self.fix_pads + \
                [(net, (vx - .125, vy - .125, vx + .125, vy + .125)) for _, (net, vx, vy) in self.pin_vias.items()] + \
                [(net, (vx - k + .1, vy - k + .1, vx + k - .1, vy + k - .1)) for net, vx, vy, k in self.fix_vias]
            self._obst = (np.array([ob for _, ob in st]).reshape(-1, 4), np.array([n for n, _ in st], dtype=object))
        dyn = [(net, bx) for a, net, bx in pads] + \
              [('GND', (gx - GND_VIA[0] / 2, gy - GND_VIA[0] / 2, gx + GND_VIA[0] / 2, gy + GND_VIA[0] / 2))
               for gx, gy in gnd]
        ob_all = np.vstack([self._obst[0], np.array([ob for _, ob in dyn]).reshape(-1, 4)])
        on_all = np.concatenate([self._obst[1], np.array([n for n, _ in dyn], dtype=object)])
        for net, (p, q) in edges:
            m = (on_all != net) & (ob_all[:, 2] >= min(p[0], q[0])) & (ob_all[:, 0] <= max(p[0], q[0])) & \
                (ob_all[:, 3] >= min(p[1], q[1])) & (ob_all[:, 1] <= max(p[1], q[1]))
            for ob in ob_all[m]:
                if seg_box(p, q, ob) < 0.05:
                    blocks += 1
        near = 0.0
        for role, pin in CAPS:
            net, vx, vy = self.pin_vias[pin]
            near += 3.0 * min(circ_box(vx, vy, 0.0, bx) for n_, bx in pl[self.r1[role]][0] if n_ == net)
        top_len = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for _, (p, q) in edges)
        c = weight * pen + length + near + TOP_W * top_len + CROSS_W * cross + BLOCK_W * blocks
        return (c, pen, length, near, cross, blocks, why) if detail else c


def search(prob, seed, iters, t0=3.0, start=None):
    """Annealing, the broken rules' weight growing from 1 to 100 over the
    run: early on a part may pass through a spot that breaks a rule to
    reach a better one (the MCU's edges are rows of vias), by the end
    every rule binds."""
    rnd = random.Random(seed)
    wt = lambda it: 1.0 + 99.0 * (it / iters) ** 2
    pos = {}
    for ref in prob.refs:
        fp = prob.b.FindFootprintByReference(ref)
        pos[ref] = (round(X(fp.GetPosition().x), 3), round(X(fp.GetPosition().y), 3),
                    int(round(fp.GetOrientationDegrees())) % 360)
    if start:
        inv = {role: ref for ref, role in prob.refs.items()}
        for role, v in start.items():
            pos[inv[role]] = tuple(v)
    refs = sorted(prob.refs)
    cur, cc = pos, prob.cost(pos, weight=wt(0))
    best, bc = cur, prob.cost(pos)
    for it in range(iters):
        t = t0 * (1 - it / iters) + 0.01
        nxt = dict(cur)
        k = rnd.random()
        ref = rnd.choice(refs)
        x, y, r = nxt[ref]
        if k < 0.1:
            nxt[ref] = (x, y, (r + rnd.choice((90, 180, 270))) % 360)
        elif k < 0.18:
            o = rnd.choice(refs)
            if prob.geo[o][1] == prob.geo[ref][1]:
                (xo, yo, ro) = nxt[o]
                nxt[ref], nxt[o] = (xo, yo, r), (x, y, ro)
        else:
            step = rnd.choice((0.05, 0.05, 0.1, 0.2, 0.5, 1.0))
            bd = bounds(prob.refs[ref])
            nxt[ref] = (round(min(max(x + rnd.choice((-1, 0, 1)) * step, bd[0]), bd[2]), 3),
                        round(min(max(y + rnd.choice((-1, 0, 1)) * step, bd[1] - 0.15), bd[3]), 3), r)
        w = wt(it)
        if it % 1000 == 0:
            cc = prob.cost(cur, weight=w)
        nc = prob.cost(nxt, weight=w)
        if nc < cc or rnd.random() < math.exp((cc - nc) / t):
            cur, cc = nxt, nc
            full = prob.cost(cur)
            if full < bc:
                best, bc = cur, full
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('board')
    ap.add_argument('--seed', type=int, default=10)
    ap.add_argument('--iters', type=int, default=150000)
    ap.add_argument('--out')
    ap.add_argument('--reserve', help='a routed board whose driver lines to the FET row the parts must leave a way')
    ap.add_argument('--start', help='a JSON result (--out) to start from instead of the board\'s spots')
    ap.add_argument('--t0', type=float, default=3.0, help='starting temperature (lower: refine the board\'s spots)')
    ap.add_argument('--cross-w', type=float, default=CROSS_W)
    ap.add_argument('--block-w', type=float, default=BLOCK_W)
    a = ap.parse_args()
    globals().update(CROSS_W=a.cross_w, BLOCK_W=a.block_w)
    prob = Problem(a.board, a.reserve)
    best = search(prob, a.seed, a.iters, a.t0, json.load(open(a.start))['pos'] if a.start else None)
    c, pen, length, near, cross, blocks, why = prob.cost(best, detail=True)
    roles = {prob.refs[r]: v for r, v in best.items()}
    print('cost %.2f: %d rules broken %s, %.2f mm of connections, %.2f from capacitors to pins, '
          '%d crossings, %d tracks through other copper' % (c, len(why), why[:5], length, near / 3, cross, blocks))
    for role in ROLES:
        x, y, r = roles[role]
        print("    t['%s'] = (%s, %s, %d, 'T')" % (role, round(x, 3), round(y, 3), r))
    if a.out:
        json.dump({'pos': roles, 'cost': [c, pen, length, near]}, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
