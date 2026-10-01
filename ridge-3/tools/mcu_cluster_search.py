#!/usr/bin/env python3
"""Spots for the ESC MCU's small parts on top (esc_layout.template).

Each channel's MCU (AT32F421, QFN-28, on the bottom) has fourteen small
parts on the top over it: its supply and reset capacitors, the
thermistor's bias, the three back-EMF low legs and the neutral star, the
current filter (resistor and capacitor, between the amplifier's output
and the MCU's pin) and the two SWD test points.  With them: the back-EMF
dividers' 20k legs over the driver, each on its switch-node sense pin,
and the FETs' thermistor by phase C's high side.  This searches
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
  * each GND pad's plane via in the pad (fanout's inpad rule: 0.45 mm,
    0.1 mm from other nets' copper on every layer, its hole 0.2 mm from
    their copper and 0.45 mm from every other hole);
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
run on top to the nearest spot that takes one (and add that length).

    python3.12 tools/mcu_cluster_search.py BOARD [--seed N] [--iters N] [--out FILE]
                                              [--cross-w MM] [--block-w MM]

BOARD: an ESC board built by esc_layout.build(path, route=False): the
copper laid before the routing, which stays wherever the parts go (with
route_local's lines, which follow the parts, the search would take them
for fixed).  Prints the template lines to paste into
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
# it, the back-EMF resistors over the driver (on its switch-node sense
# pins), the thermistor by phase C's high side, short of its drain's vias
BOUNDS = {None: (-8.9, 3.95, -2.2, 10.6),
          'RBH_A': (-2.6, 3.95, 3.6, 9.9), 'RBH_B': (-2.6, 3.95, 3.6, 9.9), 'RBH_C': (-2.6, 3.95, 3.6, 9.9),
          'RT': (-6.6, 8.9, -3.4, 10.4)}
bounds = lambda role: BOUNDS.get(role, BOUNDS[None])
PIN_VIA = (0.25, 0.15)                    # the MCU's in-pad escape vias (esc_layout.VIA_ESCAPE)
GND_VIA = (0.45, 0.25)                    # plane vias (esc_layout.VIA_INPAD, FANOUT), in the pad or
GND_CL, GND_HOLE_GAP = 0.1, 0.25          # beside it: 0.1 mm to other nets' copper, 0.25 via hole to hole
GND_PITCH = 0.6                           # a plane via beside its pad: 0.6 mm from every via (via_room)
STUB_W, SHARE = 0.25, 0.9                 # its stub, or one to a plane via already there
STEPS = (0.02, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3, 1.7, 2.1, 2.5)   # fanout's rings round the pad
CAPS = (('C_VDD', '17'), ('C_VDDA', '5'), ('C_RST', '4'))
CROSS_W = 20.0                            # mm of connection a crossing of two nets' top tracks costs
BLOCK_W = 20.0                            # ... and a track through another net's pad or via
LOCAL = 2.0                               # mm: joins shorter than this are top tracks
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
    def __init__(self, board_path):
        self.b = b = pcbnew.LoadBoard(board_path)
        self.comps = comps = circuit.build('esc')
        r1 = E.roles(comps, 1)
        self.r1 = r1
        self.refs = {r1[k]: k for k in ROLES}
        allp = {**parts.PARTS, **parts.PADS}
        self.cmap = cmap = {c.ref: c for c in comps}
        self.geo = {}
        for ref in self.refs:
            fp = pcb.load_fp(allp[cmap[ref].part]['fp'])
            pads = [(p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetSize(pcbnew.F_Cu).x),
                     mm(p.GetSize(pcbnew.F_Cu).y)) for p in fp.Pads() if p.GetNumber()]
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            self.geo[ref] = (pads, (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))
        inside = lambda x0, y0, x1, y1: x1 > AREA[0] and x0 < AREA[2] and y1 > AREA[1] and y0 < AREA[3]
        self.fix_cy, self.fix_pads, self.fix_vias, self.fix_tracks, self.terms = [], [], [], [], {}
        mcu = b.FindFootprintByReference(r1['MCU'])
        mcu_nets = set(p.GetNetname() for p in mcu.Pads())
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
            if net in mcu_nets | {'GND'}:
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
        # the cluster parts' own plane vias (in their GND pads, or at the end
        # of a stub from one): fanned out again round the new spots
        cl_pads = []
        for ref in self.refs:
            for p in b.FindFootprintByReference(ref).Pads():
                if p.GetNetname() == 'GND':
                    bb = p.GetBoundingBox()
                    cl_pads.append((X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom())))
        inpad = lambda x, y: any(q[0] - 0.01 <= x <= q[2] + 0.01 and q[1] - 0.01 <= y <= q[3] + 0.01 for q in cl_pads)
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
        self._spots = {}

    def _via_spots(self, mcu_nets):
        """self.vok[net]: where a via of each cluster net may stand, on a
        RES grid over AREA (and 1 mm round): inside channel 1's region and
        off the copper other channels have there (stamp.region, foreign),
        outside every no-via rule area (the power copper's, the holes'),
        and clear of other nets' pads on every layer (the MCU's and the
        driver's exposed pads among them), their tracks and vias by the
        via's ring plus 0.1 mm or its hole plus 0.2 mm.  The cluster's own
        parts are not in it (via_spot)."""
        import stamp
        b = self.b
        x0, y0 = AREA[0] - 1.0, AREA[1] - 1.0
        W, H = int(round((AREA[2] - AREA[0] + 2.0) / RES)), int(round((AREA[3] - AREA[1] + 2.0) / RES))
        self.grid = (x0, y0, W, H)
        xs = x0 + (np.arange(W) + 0.5) * RES
        ys = y0 + (np.arange(H) + 0.5) * RES
        self.XX, self.YY = XX, YY = np.meshgrid(xs, ys)
        ring = VIA[0] / 2
        self.keep = keep = max(ring + 0.1, VIA[1] / 2 + 0.2)
        common = np.ones((H, W), bool)
        parts = E.channel_parts(self.comps)
        reg = stamp.region(b, parts, E.CHANNELS)
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
                    common &= ~shapely.contains_xy(poly.buffer(ring), XX + pcb.CX, YY + pcb.CY)
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
                bb = p.GetBoundingBox()
                bx = (X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom()))
                if bx[2] < x0 - keep or bx[0] > x0 + W * RES + keep or bx[3] < y0 - keep or bx[1] > y0 + H * RES + keep:
                    continue
                dx = np.maximum(np.maximum(bx[0] - XX, XX - bx[2]), 0.0)
                dy = np.maximum(np.maximum(bx[1] - YY, YY - bx[3]), 0.0)
                block(p.GetNetname(), dx * dx + dy * dy >= keep * keep)
        for t in b.GetTracks():
            net = t.GetNetname()
            if net in mcu_nets | {'GND'}:
                continue
            if t.GetClass() == 'PCB_VIA':
                vx, vy = X(t.GetPosition().x), X(t.GetPosition().y)
                k = mm(t.GetWidth(pcbnew.F_Cu)) / 2 + ring + 0.1
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
            k = PIN_VIA[0] / 2 + ring + 0.1
            block(net, (XX - vx) ** 2 + (YY - vy) ** 2 >= k * k)
        # where a GND pad's plane via may stand (esc_layout.plane_vias,
        # fanout: its turned copies clear of the other channels too): in the
        # pad GND_CL from other nets' copper on every layer, its hole 0.2 mm
        # from their copper and GND_HOLE_GAP from every via hole (gin);
        # beside the pad also GND_PITCH from every via (goff); and where the
        # stub out to it may run on top (stub: STUB_W, 0.1 mm clear)
        gr, gh = GND_VIA[0] / 2, GND_VIA[1] / 2
        self.gkeep = gk = max(GND_CL + gr, E.HOLE_CL + gh)
        gin = np.ones((H, W), bool)
        stub = np.ones((H, W), bool)
        sk = STUB_W / 2 + 0.1
        for l, g in self._foreign.items():
            gin &= ~shapely.contains_xy(g.buffer(gk), XX + pcb.CX, YY + pcb.CY)
            if l == pcbnew.F_Cu:
                stub &= ~shapely.contains_xy(g.buffer(sk), XX + pcb.CX, YY + pcb.CY)

        def box_d2(bx):
            dx = np.maximum(np.maximum(bx[0] - XX, XX - bx[2]), 0.0)
            dy = np.maximum(np.maximum(bx[1] - YY, YY - bx[3]), 0.0)
            return dx * dx + dy * dy
        for fp in b.GetFootprints():
            if fp.GetReference() in self.refs:
                continue
            for p in fp.Pads():
                if p.GetNetname() == 'GND':
                    continue
                bb = p.GetBoundingBox()
                d2 = box_d2((X(bb.GetLeft()), X(bb.GetTop()), X(bb.GetRight()), X(bb.GetBottom())))
                gin &= d2 >= gk * gk
                if p.IsOnLayer(pcbnew.F_Cu):
                    stub &= d2 >= sk * sk
        vias = []
        for t in b.GetTracks():
            net = t.GetNetname()
            if t.GetClass() == 'PCB_VIA':
                vx, vy = X(t.GetPosition().x), X(t.GetPosition().y)
                if net == 'GND' and (vx, vy) not in self.own_gnd:
                    vias.append((vx, vy, mm(t.GetDrillValue()) / 2, None))
                elif net not in mcu_nets | {'GND'}:
                    vias.append((vx, vy, mm(t.GetDrillValue()) / 2, mm(t.GetWidth(pcbnew.F_Cu)) / 2))
                continue
            if net in mcu_nets | {'GND'}:
                continue
            ax, ay, ex, ey = X(t.GetStart().x), X(t.GetStart().y), X(t.GetEnd().x), X(t.GetEnd().y)
            dx, dy = ex - ax, ey - ay
            ll = dx * dx + dy * dy
            tt = np.clip(((XX - ax) * dx + (YY - ay) * dy) / ll, 0.0, 1.0) if ll else 0.0
            d2 = (XX - ax - tt * dx) ** 2 + (YY - ay - tt * dy) ** 2
            hw = mm(t.GetWidth()) / 2
            gin &= d2 >= (hw + gk) ** 2
            if t.GetLayer() == pcbnew.F_Cu:
                stub &= d2 >= (hw + sk) ** 2
        vias += [(vx, vy, PIN_VIA[1] / 2, PIN_VIA[0] / 2) for _, vx, vy in self.pin_vias.values()]
        goff = gin.copy()
        for vx, vy, hr, r in vias:
            d2 = (XX - vx) ** 2 + (YY - vy) ** 2
            k = hr + GND_HOLE_GAP + gh if r is None else max(hr + GND_HOLE_GAP + gh, r + gk)
            gin &= d2 >= k * k
            goff &= d2 >= max(k, GND_PITCH) ** 2
            if r is not None:
                stub &= d2 >= (r + sk) ** 2
        self.gin, self.goff, self.stub = gin, goff, stub
        # the plane vias that stay (a share stub may reach them)
        self.fix_gnd = [(vx, vy) for vx, vy, hr, r in vias if r is None]

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
        """For each end (x, y): whether a top stub from (px, py) to it keeps
        clear of the fixed top copper (self.stub) and the boxes `pads`."""
        n = 12
        t = np.linspace(0.0, 1.0, n)[None, :]
        sx, sy = px + (x[:, None] - px) * t, py + (y[:, None] - py) * t
        j, i = self._cell(sx, sy)
        ok = self.stub[j, i].all(axis=1)
        sk = STUB_W / 2 + 0.1
        for ob in pads:
            dx = np.maximum(np.maximum(ob[0] - sx, sx - ob[2]), 0.0)
            dy = np.maximum(np.maximum(ob[1] - sy, sy - ob[3]), 0.0)
            ok &= (dx * dx + dy * dy).min(axis=1) >= sk * sk
        return ok

    def plane_spot(self, bx, centre, pads, taken):
        """Where the GND pad `bx` (of a part centred at `centre`) takes its
        plane via, as fanout does it: in the pad (inpad_spots: the centre,
        then along the long axis); else a stub to a plane via within SHARE;
        else a via on fanout's rings round the pad (STEPS, 15 degree steps
        from the part's centre outward) and a stub to it.  Clear of the
        cluster's pads of other nets (`pads`: their boxes) and of the plane
        vias `taken` ((x, y): placed before it, in the pad).  Returns
        (stub length, (x, y), via placed), or None.  Cached."""
        lo, hi = bx[0] - 3.5, bx[1] - 3.5
        near = tuple(ob for ob in pads if not (ob[2] < lo or ob[0] > bx[2] + 3.5 or ob[3] < hi or ob[1] > bx[3] + 3.5))
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

        def clear(x, y, pitch):
            ok = np.ones(len(x), bool)
            for ob in near:
                dx = np.maximum(np.maximum(ob[0] - x, x - ob[2]), 0.0)
                dy = np.maximum(np.maximum(ob[1] - y, y - ob[3]), 0.0)
                ok &= dx * dx + dy * dy >= self.gkeep * self.gkeep
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
        j, i = self._cell(x, y)
        ok = self.gin[j, i] & clear(x, y, 2 * gh + GND_HOLE_GAP)
        if ok.any():
            k = int(np.argmax(ok))
            return 0.0, (float(x[k]), float(y[k])), True
        # a stub to a plane via already there
        vs = [(vx, vy) for vx, vy in self.fix_gnd + list(taken)
              if box_dist(bx, (vx, vy, vx, vy)) <= SHARE + gr]
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
            j, i = self._cell(x, y)
            ok = self.goff[j, i] & clear(x, y, GND_PITCH)
            if ok.any():
                ok &= self._stubs_ok(px, py, x, y, near)
                if ok.any():
                    k = int(np.argmax(ok))
                    return d, (float(x[k]), float(y[k])), True
        return None

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

    def cost(self, pos, detail=False, weight=100.0):
        pl = {ref: self.placed(ref, *pos[ref]) for ref in self.refs}
        refs = list(self.refs)
        pen, why = 0.0, []

        def bad(k, *what):
            nonlocal pen
            pen += k
            why.append(what)
        for i, a in enumerate(refs):
            ca = pl[a][1]
            bd = bounds(self.refs[a])
            over = max(0.0, bd[0] - ca[0]) + max(0.0, bd[1] - ca[1]) + max(0.0, ca[2] - bd[2]) + \
                max(0.0, ca[3] - bd[3])
            if over > 0:
                bad(10 + 50 * over, 'area', self.refs[a])
            for c in self.fix_cy + [pl[o][1] for o in refs[i + 1:]]:
                o = min(ca[2], c[2]) - max(ca[0], c[0]), min(ca[3], c[3]) - max(ca[1], c[1])
                if o[0] > 0.001 and o[1] > 0.001:
                    bad(10 + 50 * min(o), 'courtyard', self.refs[a])
        pads = [(a, net, bx) for a in refs for net, bx in pl[a][0]]
        # each GND pad's plane via, in the order fanout takes them: in the
        # pad, or a top stub out to one (plane_spot)
        gnd, stubs, gtaken, glen = [], [], (), 0.0
        others = tuple(bx for a, net, bx in pads if net != 'GND')
        for a, net, bx in pads:
            if net != 'GND':
                continue
            v = self.plane_spot(bx, pos[a][:2], others, gtaken)
            if v is None:
                bad(10, 'plane via', self.refs[a])
                continue
            d, spot, new = v
            if d > 0:
                glen += d
                stubs.append(('GND', near_pts(bx, (spot[0], spot[1], spot[0], spot[1]))))
            if new:
                gnd.append(spot)
                gtaken += (spot,)
        for k, (a, net, bx) in enumerate(pads):
            for onet, ob in self.fix_pads:
                if onet != net and box_dist(bx, ob) < 0.1:
                    bad(10, 'pad-pad', self.refs[a], onet)
            for onet, vx, vy, keep in self.fix_vias:
                if onet != net and circ_box(vx, vy, 0.0, bx) < keep:
                    bad(10, 'pad-via', self.refs[a], onet)
            for onet, p0, p1, hw in self.fix_tracks:
                if onet != net and seg_box(p0, p1, bx) < hw + 0.1:
                    bad(10, 'pad-track', self.refs[a], onet)
            for pin, (pnet, vx, vy) in self.pin_vias.items():
                if pnet != net and circ_box(vx, vy, 0.0, bx) < max(PIN_VIA[0] / 2 + 0.1, PIN_VIA[1] / 2 + 0.2):
                    bad(10, 'pad-pin via', self.refs[a], pin)
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
        taken = tuple((gx, gy, kg) for gx, gy in gnd)
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
        edges = top + [(n, pq) for (n, e), pq in esc.items() if pq] + stubs
        length += glen
        cross = 0
        for i, (n1, (p, q)) in enumerate(edges):
            for n2, (r, s_) in edges[i + 1:]:
                if n1 != n2 and seg_cross(p, q, r, s_):
                    cross += 1
        blocks = 0
        obst = [(net, bx) for a, net, bx in pads] + self.fix_pads + \
               [(net, (vx - .125, vy - .125, vx + .125, vy + .125)) for _, (net, vx, vy) in self.pin_vias.items()] + \
               [(net, (vx - k + .1, vy - k + .1, vx + k - .1, vy + k - .1)) for net, vx, vy, k in self.fix_vias] + \
               [('GND', (gx - GND_VIA[0] / 2, gy - GND_VIA[0] / 2, gx + GND_VIA[0] / 2, gy + GND_VIA[0] / 2))
                for gx, gy in gnd]
        for net, (p, q) in edges:
            sb = (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))
            for onet, ob in obst:
                if onet == net or ob[2] < sb[0] or ob[0] > sb[2] or ob[3] < sb[1] or ob[1] > sb[3]:
                    continue
                if seg_box(p, q, ob) < 0.05:
                    blocks += 1
        near = 0.0
        for role, pin in CAPS:
            net, vx, vy = self.pin_vias[pin]
            near += 3.0 * min(circ_box(vx, vy, 0.0, bx) for n_, bx in pl[self.r1[role]][0] if n_ == net)
        c = weight * pen + length + near + CROSS_W * cross + BLOCK_W * blocks
        return (c, pen, length, near, cross, blocks, why) if detail else c


def search(prob, seed, iters):
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
    refs = sorted(prob.refs)
    cur, cc = pos, prob.cost(pos, weight=wt(0))
    best, bc = cur, prob.cost(pos)
    for it in range(iters):
        t = 3.0 * (1 - it / iters) + 0.01
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
    ap.add_argument('--cross-w', type=float, default=CROSS_W)
    ap.add_argument('--block-w', type=float, default=BLOCK_W)
    a = ap.parse_args()
    globals().update(CROSS_W=a.cross_w, BLOCK_W=a.block_w)
    prob = Problem(a.board)
    best = search(prob, a.seed, a.iters)
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
