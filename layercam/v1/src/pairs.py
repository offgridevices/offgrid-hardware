# -*- coding: utf-8 -*-
"""The main board's coupled pairs, drawn before anything else is placed or
routed: the camera's three MIPI lanes and the USB pair.

Each pair is a centreline (the waypoints below, corners cut to 45 degrees)
and its two tracks are that line offset either side by half the pair's
pitch, so the two stay coupled through every bend and come out the same
length (each pair turns as far left as right).  Ends: the tracks fan out
onto their pads at 45 degrees.

  MIPI  (F, over the In1 ground plane, 0.10 / 0.15 mm, 100 ohm)
        from the SoC's top row (pins 123-128) up its left side, round the
        lens window's left (outside the holder screw), across above the
        window and up into the camera connector J2.  D0, clock and D1 keep
        their order the whole way; at J2 they spread to its 1.5 mm pitch.
  USB   (0.12 / 0.15 mm, 90 ohm)
        from the cable connector J1 right and down on F, left of the MIPI
        lanes; through two vias to B at the SoC's corner, which the 0.9 V
        buck fills on F; back up to F beside the SoC's pins 26 / 27.

Coordinates are the board's (x right, y down, mm, origin on the lens
axis), the same as layout_main.py.
"""
import math
import pcbnew
import pcb

# (P net, N net, P on the -offset side) per lane, D0 / clock / D1
MIPI = (('CSI_D0P', 'CSI_D0N'), ('CSI_CKP', 'CSI_CKN'), ('CSI_D1P', 'CSI_D1N'))
MIPI_W, MIPI_S = 0.10, 0.15
USB_W, USB_S = 0.12, 0.15
CHAMFER = 1.0

# the lanes' waypoints, one value per lane (D0, clock, D1)
U1_X = (-5.245, -4.545, -3.845)        # centre of each lane's two SoC pads
U1_Y = 13.34                           # the SoC's top row
LEFT_Y = (12.55, 11.8, 11.05)          # the run left above the SoC
UP_X = (-11.95, -11.2, -10.45)         # the run up, outside the holder screw H5
TOP_Y = (-12.05, -11.3, -10.55)        # the run right, below the NAND U5
J2_X = (-3.0, -1.5, 0.0)               # centre of each lane's two J2 pads
J2_Y, J2_END = -22.8, -21.6            # J2's pads; where the lanes split for them

# USB: J1's pads 3 (D-) and 4 (D+), the SoC's 26 (D-) and 27 (D+)
USB_F1 = [(-16.4, -2.0), (-13.75, -2.0), (-13.75, 13.1)]
USB_VIA1 = 13.6                        # the via pair's row, F -> B
USB_B = [(-13.75, 14.1), (-13.75, 23.6), (-9.0, 23.6), (-8.3, 22.9), (-8.0, 22.9)]
USB_VIA2 = -7.6                        # the via pair's column, B -> F
USB_F2 = [(-7.25, 22.9), (-6.06, 22.9)]
VIA_SPREAD = 0.35                      # each via of a pair from the pair's centre


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


def mipi(b):
    for i, (p, n) in enumerate(MIPI):
        line = chamfer([(U1_X[i], U1_Y), (U1_X[i], LEFT_Y[i]), (UP_X[i], LEFT_Y[i]), (UP_X[i], TOP_Y[i]),
                        (J2_X[i], TOP_Y[i]), (J2_X[i], J2_END)])
        h = (MIPI_W + MIPI_S) / 2
        for net, s in ((p, -1), (n, 1)):
            t = offset(line, s * h)
            pad_x = J2_X[i] + s * 0.25
            # spread from the pair's pitch to J2's 0.5 mm at 45 degrees
            t += [(pad_x, J2_END - (0.25 - h)), (pad_x, J2_Y)]
            _draw(b, t, MIPI_W, pcbnew.F_Cu, net)


def usb(b):
    h = (USB_W + USB_S) / 2
    f1, bb, f2 = chamfer(USB_F1), chamfer(USB_B, 0.7), USB_F2
    (vx1, vy1), (vx2, vy2) = USB_F1[-1], USB_B[-1]
    for net, s, pad_y in (('USB_DM', -1, -2.5), ('USB_DP', 1, -1.5)):
        # F: from J1's pad, spread in at 45 degrees, right and down
        t = offset(f1, s * h)
        d = abs(pad_y - t[0][1])
        _draw(b, [(t[0][0] - 1.26, pad_y), (t[0][0] - d, pad_y)] + t, USB_W, pcbnew.F_Cu, net)
        # heading down here: D- is on +x
        via1 = (vx1 - s * VIA_SPREAD, USB_VIA1)
        _draw(b, [t[-1], via1], USB_W, pcbnew.F_Cu, net)
        pcb.via(b, via1[0], via1[1], net)
        t = offset(bb, s * h)
        _draw(b, [via1] + t, USB_W, pcbnew.B_Cu, net)
        # heading +x here: D- is on -y
        via2 = (USB_VIA2, vy2 + s * VIA_SPREAD)
        _draw(b, [t[-1], via2], USB_W, pcbnew.B_Cu, net)
        pcb.via(b, via2[0], via2[1], net)
        t = offset(f2, s * h)
        _draw(b, [via2] + t, USB_W, pcbnew.F_Cu, net)


def lengths(b):
    """Each pair net's routed length, mm (tracks only)."""
    out = {}
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            out[t.GetNetname()] = out.get(t.GetNetname(), 0) + t.GetLength() / 1e6
    return {n: round(out.get(n, 0), 2) for pair in MIPI + (('USB_DP', 'USB_DM'),) for n in pair}


def pin28(b):
    """The SoC's 3.3 V pin 28, just below the USB pins: the USB pair's
    stubs and via leave it no straight way out, so its via goes down-left
    of it on a dog-leg."""
    x, y = pcb.pad_at(b, 'U1', '28')
    pts = [(x, y), (x - 0.69, y), (x - 1.14, y + 0.45)]
    pcb.track(b, pts, 0.2, pcbnew.F_Cu, 'VCC_3V3')
    pcb.via(b, pts[-1][0], pts[-1][1], 'VCC_3V3')
    return {('U1', '28')}


def draw(b):
    mipi(b)
    usb(b)
    return pin28(b)
