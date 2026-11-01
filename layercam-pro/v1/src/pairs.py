# -*- coding: utf-8 -*-
"""The board's coupled pairs, drawn before anything else is placed or
routed: the image sensor's three MIPI lanes.

Each pair is a centreline (the waypoints below, corners cut to 45 degrees)
and its two tracks are that line offset either side by half the pair's
pitch, so the two stay coupled through every bend; each lane turns as far
left as right, so its two tracks come out the same length.

  MIPI  (0.12 / 0.15 mm, 100 ohm; B over In4, F over In1)
        The sensor is on the front face (B) on the lens axis, the SoC on
        the back face (F) 15 mm below it.  Each lane leaves the sensor's
        CSP between its balls on short 0.1 mm stubs, pairs up below the
        package, runs left on B (nested L-shapes: the outermost lane turns
        first), drops to F through two vias with a ground via beside them,
        and runs left again on F into the SoC's top row (pins 123-128).
        Seen from behind, the sensor's D0 and clock lanes have N to the
        left of P, the SoC wants P to the left: their two vias stand one
        above the other, so the tracks change sides at the layer change.
  USB   routed with the rest (it carries only firmware flashing).

Coordinates are the board's (x right, y down, mm, origin on the lens
axis), the same as layout_main.py.
"""
import math
import pcbnew
import pcb

# (P net, N net) per lane, D0 / clock / D1
MIPI = (('CSI_D0P', 'CSI_D0N'), ('CSI_CKP', 'CSI_CKN'), ('CSI_D1P', 'CSI_D1N'))
from board import DIFF
MIPI_W, MIPI_S = DIFF['main']['MIPI'][1:]
H = (MIPI_W + MIPI_S) / 2          # each track from its lane's centreline
CHAMFER = 0.5
ESC_W = 0.1                        # the stubs between the sensor's balls

# The sensor's balls on B, board coordinates (its footprint mirrored), and
# the stub out of the package for each: ball -> (x, y) where the stub
# reaches the pair's start row PAIR_Y0.  Stubs leave between the edge row's
# balls (0.64 mm apart: 0.44 mm between pads).
SENSOR = {
    'CSI_D0P': [(-0.64, 1.16), (-0.64, 2.20)],
    'CSI_D0N': [(-0.64, 0.58), (-0.96, 0.90), (-0.96, 2.20)],
    # the clock's two tracks part round the via of DVDD's ball E4, which
    # sits between them on the package's edge row
    'CSI_CKP': [(0.00, 0.00), (0.32, 0.32), (0.32, 1.41), (0.42, 1.51), (0.42, 2.20)],
    'CSI_CKN': [(0.00, 0.58), (-0.32, 0.90), (-0.32, 1.41), (-0.42, 1.51), (-0.42, 2.20)],
    'CSI_D1P': [(0.64, 0.58), (0.96, 0.90), (0.96, 2.20)],
    'CSI_D1N': [(1.28, 0.58), (1.60, 0.90), (1.60, 2.20)],
}
PAIR_Y0 = 2.5                      # where each lane's two tracks are coupled
LANE_X0 = (-0.80, 0.0, 1.28)       # lane centrelines there (D0, CK, D1)

# The sensor's other inner balls: a 0.1 mm stub each to a via between the
# balls (0.35 / 0.2 mm, as the SoC's escapes: 0.16 mm to the next ball's
# pad); the edge balls are routed.  net -> [(ball, via)]
ESC_VIA = (0.35, 0.2)
SENSOR_VIAS = {
    'GND': [('A1', (1.60, -0.87)), ('B2', (1.60, -0.87)), ('B5', (-0.96, -0.87)),
            ('C7', (-1.60, 0.29)), ('D6', (-1.60, 0.29))],
    'CAM_DVDD': [('B4', (0.32, -0.87)), ('B6', (-1.60, -0.87)), ('E4', (0.0, 1.85))],
    'CAM_DOVDD': [('C2', (0.96, -0.29)), ('C3', (0.96, -0.29))],
    'CAM_PWDN': [('C6', (-0.96, -0.29))],
}
SWAP = (True, True, False)         # N left of P on the sensor side: change sides at the vias
# on B: each lane runs down to its row, left (west) to its via column; the
# westmost lane turns first.  0.55 mm between rows: a lane is 0.39 wide
B_ROW = (2.9, 3.45, 4.0)
VIA_X = (-10.0, -8.0, -6.0)        # lane centre at the vias, west of the SoC's pins
VIA_Y = 4.9                        # the first via of each lane; the second VIA_DY below
VIA_DY = 0.7
VIA_DX = 0.35
FY0 = VIA_Y + VIA_DY + 1.2         # where each lane is a pair again on F
# on F: from the vias down, right (east) at its row, down into the SoC's
# pins; the eastmost lane (D1) turns first
F_ROW = (8.1, 7.55, 7.0)


def chamfer(pts, c=CHAMFER):
    """Cut every corner of a polyline to 45 degree steps: each corner
    loses up to c along both its segments (less where a segment is short)."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[i + 1]
        la, lb = math.hypot(bx - ax, by - ay), math.hypot(cx - bx, cy - by)
        k = min(c, la / 2, lb / 2)
        out.append((bx - (bx - ax) / la * k, by - (by - ay) / la * k))
        out.append((bx + (cx - bx) / lb * k, by + (cy - by) / lb * k))
    out.append(pts[-1])
    return out


def offset(pts, d):
    """The polyline moved sideways by d (positive: to +x when heading -y,
    i.e. along (-dy, dx)), with mitred corners."""
    def norm(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dx, dy)
        return (-dy / l, dx / l), (dx / l, dy / l)
    out = []
    for i, p in enumerate(pts):
        if i == 0:
            (nx, ny), _ = norm(pts[0], pts[1])
            out.append((p[0] + d * nx, p[1] + d * ny))
        elif i == len(pts) - 1:
            (nx, ny), _ = norm(pts[-2], pts[-1])
            out.append((p[0] + d * nx, p[1] + d * ny))
        else:
            (n1x, n1y), _ = norm(pts[i - 1], p)
            (n2x, n2y), _ = norm(p, pts[i + 1])
            mx, my = n1x + n2x, n1y + n2y
            k = d / (1 + n1x * n2x + n1y * n2y)
            out.append((p[0] + k * mx, p[1] + k * my))
    return out


def _draw(b, pts, w, layer, net):
    pts = [p for i, p in enumerate(pts) if i == 0 or math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) > 1e-4]
    pcb.track(b, pts, w, layer, net)


def _lane_b(i):
    """Lane i's centreline on B, from PAIR_Y0 to just above its first via."""
    x0, row, vx = LANE_X0[i], B_ROW[i], VIA_X[i]
    return chamfer([(x0, PAIR_Y0), (x0, row), (vx, row), (vx, VIA_Y - 0.55)], CHAMFER)


def ball(b, name):
    return pcb.pad_at(b, 'U8', name)


def sensor(b):
    """The sensor's inner balls out to their vias; returns the (ref, pad)
    of the ground balls done here (the plane fan-out leaves them)."""
    done, vias = set(), set()
    for net, items in SENSOR_VIAS.items():
        for name, v in items:
            _draw(b, [ball(b, name), v], ESC_W, pcbnew.B_Cu, net)
            if v not in vias:
                pcb.via(b, v[0], v[1], net, d=ESC_VIA[0], drill=ESC_VIA[1])
                vias.add(v)
            if net == 'GND':
                done.add(('U8', name))
    return done


def mipi(b):
    for i, (p, n) in enumerate(MIPI):
        # stubs out of the package, then the couple
        line = _lane_b(i)
        for net, side in ((p, 1), (n, -1)):
            stub = SENSOR[net]
            _draw(b, stub, ESC_W, pcbnew.B_Cu, net)
            # the side each net is on as the lane heads down (+y): with
            # SWAP, N left (-x) of P; without, P left of N
            s = (side if SWAP[i] else -side)
            t = offset(line, -s * H)          # offset(+d) is to +x when heading -y, i.e. to -x heading +y
            _draw(b, [stub[-1]] + t, MIPI_W, pcbnew.B_Cu, net)
        # the layer change.  Heading down at x = vx: the left track to the
        # first via (left, upper), the right track past it to the second
        # (right, lower).
        vx = VIA_X[i]
        left_net, right_net = (n, p) if SWAP[i] else (p, n)
        v1 = (vx - VIA_DX, VIA_Y)
        v2 = (vx + VIA_DX, VIA_Y + VIA_DY)
        end = line[-1]
        _draw(b, [(end[0] - H, end[1]), (v1[0], v1[1] - 0.2), v1], MIPI_W, pcbnew.B_Cu, left_net)
        _draw(b, [(end[0] + H, end[1]), (v2[0], v1[1] - 0.2 + (v2[0] - end[0] - H)),
                  v2], MIPI_W, pcbnew.B_Cu, right_net)
        for v, net in ((v1, left_net), (v2, right_net)):
            pcb.via(b, v[0], v[1], net)
        # F: the pair leaves heading down with P on the left (the SoC's
        # order) at FY0
        px, nx = vx - H, vx + H
        if SWAP[i]:
            # P (via 2, right-lower) goes down-left to its place; N (via 1,
            # left-upper) goes right above via 2, down its right side and in
            # below it at 45 degrees
            _draw(b, [v2, (px, v2[1] + (v2[0] - px)), (px, FY0)], MIPI_W, pcbnew.F_Cu, p)
            nr = v2[0] + 0.62
            ye = FY0 - 0.3
            _draw(b, [v1, (nr - 0.3, v1[1]), (nr, v1[1] + 0.3), (nr, ye - (nr - nx)), (nx, ye), (nx, FY0)],
                  MIPI_W, pcbnew.F_Cu, n)
        else:
            _draw(b, [v1, (v1[0], v1[1] + 0.2), (px, v1[1] + 0.2 + (px - v1[0])), (px, FY0)], MIPI_W, pcbnew.F_Cu, p)
            _draw(b, [v2, (nx, v2[1] + (v2[0] - nx)), (nx, FY0)], MIPI_W, pcbnew.F_Cu, n)
        # down, east at its row, down into the SoC's pins (P on the -x pad)
        pp = pcb.pad_at(b, 'U1', {'CSI_D0P': '128', 'CSI_CKP': '126', 'CSI_D1P': '124'}[p])
        pn = pcb.pad_at(b, 'U1', {'CSI_D0N': '127', 'CSI_CKN': '125', 'CSI_D1N': '123'}[n])
        cx = (pp[0] + pn[0]) / 2
        fl = chamfer([(vx, FY0), (vx, F_ROW[i]), (cx, F_ROW[i]), (cx, pp[1] - 0.45)], CHAMFER)
        for net, d, pad in ((p, H, pp), (n, -H, pn)):
            t = offset(fl, d)
            _draw(b, t + [(pad[0], t[-1][1] + abs(pad[0] - t[-1][0])), pad], MIPI_W, pcbnew.F_Cu, net)
        # the return current's way between the planes at the layer change
        gnd_via_near(b, (vx, VIA_Y + VIA_DY / 2), rmin=0.9)


def gnd_via_near(b, centre, rmin=0.75, rmax=1.6):
    """A ground via as close to `centre` as fits (0.25 mm steps out, every
    15 degrees): clear of every pad, track and via of another net by the
    fanout's clearance, inside the board."""
    import power
    from shapely.geometry import Point, LineString
    vr = pcb.VIA[0] / 2
    obst = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != 'GND':
                for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if p.IsOnLayer(lay):
                        obst.append(power._pad_poly(p, lay))
    for t in b.GetTracks():
        if t.GetNetname() == 'GND':
            continue
        if t.GetClass() == 'PCB_VIA':
            obst.append(Point(pcb.xy(t.GetPosition())).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6))
        else:
            obst.append(LineString([pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())]).buffer(t.GetWidth() / 2e6))
    edge = pcb.board_polygon().buffer(-(pcb.EDGE_BAND + vr + 0.01))  # clear of the edge band
    r = rmin
    while r <= rmax:
        for k in range(24):
            a = math.radians(15 * k)
            q = Point(centre[0] + r * math.cos(a), centre[1] + r * math.sin(a))
            v = q.buffer(vr)
            if edge.contains(q) and all(o.distance(v) >= power.CLR for o in obst):
                pcb.via(b, q.x, q.y, 'GND')
                return q.x, q.y
        r += 0.25
    raise SystemExit('pairs: no room for a ground via near (%.2f, %.2f)' % centre)


def lengths(b):
    """Each pair net's routed length, mm (tracks only)."""
    out = {}
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            out[t.GetNetname()] = out.get(t.GetNetname(), 0) + t.GetLength() / 1e6
    return {n: round(out.get(n, 0), 2) for pair in MIPI for n in pair}


def draw(b):
    done = sensor(b)
    mipi(b)
    return done
