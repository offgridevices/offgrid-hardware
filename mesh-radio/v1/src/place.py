# -*- coding: utf-8 -*-
"""Placement helpers: RF chains laid out in a line, and a packer that puts
every small part beside the pin it serves.

layout.py decides the floor plan: where the chips, connectors and the RF
chains go.  This module turns that into a position for every part:

  chain()   an RF path given as its nets in order, from one chip pin to the
            next.  The series parts sit end to end along the path, each
            shunt part beside its node, turned across the path, so the
            50 ohm line between two parts is one short straight track.
  pack()    every part not yet placed goes beside the pin it serves (the
            chip pin on its net, preferring power pins for a decoupling
            capacitor), on the anchor's side if there is room, else the
            other side, nearest first; a courtyard never overlaps another.

All coordinates are board-centre mm (pcb.py); rotations are KiCad's.
"""
import math
import pcbnew
import pcb, circuit, parts

GAP = 0.15                       # courtyard to courtyard


class Board:
    """The parts as footprints (loaded once), their courtyard boxes, and
    what is taken on each side."""

    def __init__(self, comps):
        self.comps = {c.ref: c for c in comps}
        # footprints live on a scratch board: KiCad flips a footprint using
        # its parent board's layer stack, and segfaults without one
        self.board = pcbnew.BOARD()
        self.board.SetCopperLayerCount(pcb.NLAYERS)
        self.fp = {}
        self.size = {}               # ref -> (w, h) of courtyard at rotation 0, and pad centres
        for c in comps:
            fp = pcb.load_fp(parts.PARTS[c.part]['fp'])
            self.board.Add(fp)
            self.fp[c.ref] = fp
            self.size[c.ref] = box_of(fp)
        self.pl = {}                 # ref -> (x, y, rot, side)
        self.taken = {'T': [], 'B': []}
        self.keepouts = {'T': [], 'B': []}
        self._geom = {}
        self.netpads = {}
        for c in comps:
            for p, n in c.pins.items():
                if n:
                    self.netpads.setdefault(n, []).append((c.ref, p))

    def keep_out(self, box, sides=('T', 'B')):
        for s in sides:
            self.keepouts[s].append(box)

    def geom(self, ref, x, y, rot, side):
        """Courtyard box and pad centres of a part placed so, read back from
        KiCad itself (a bottom part is flipped exactly as pcb.place_components
        flips it)."""
        key = (ref, round(x, 3), round(y, 3), rot % 360, side)
        if key in self._geom:
            return self._geom[key]
        fp = self.fp[ref]
        flipped = fp.IsFlipped()
        if (side == 'B') != flipped:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetPosition(pcb.P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.BuildCourtyardCaches()
        xs, ys = [], []
        cl = pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd
        cy = fp.GetCourtyard(cl)
        if cy.OutlineCount():
            bb = cy.BBox()
            xs += [bb.GetLeft(), bb.GetRight()]; ys += [bb.GetTop(), bb.GetBottom()]
        pads = {}
        for p in fp.Pads():
            q = p.GetPosition()
            pads.setdefault(p.GetNumber(), (q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY))
            bb = p.GetBoundingBox()
            xs += [bb.GetLeft(), bb.GetRight()]; ys += [bb.GetTop(), bb.GetBottom()]
        box = (min(xs) / 1e6 - pcb.CX, min(ys) / 1e6 - pcb.CY, max(xs) / 1e6 - pcb.CX, max(ys) / 1e6 - pcb.CY)
        self._geom[key] = (box, pads)
        return box, pads

    def rect(self, ref, x, y, rot, side='T'):
        return self.geom(ref, x, y, rot, side)[0]

    def fits(self, ref, x, y, rot, side):
        r = self.rect(ref, x, y, rot, side)
        m = 0.25                                      # edge margin
        if r[0] < -pcb.HX + m or r[2] > pcb.HX - m or r[1] < -pcb.HY + m or r[3] > pcb.HY - m:
            return False
        for o in self.taken[side] + self.keepouts[side]:
            if overlap(r, o, GAP):
                return False
        return True

    def put(self, ref, x, y, rot, side, check=True):
        if check and not self.fits(ref, x, y, rot, side):
            raise ValueError('%s does not fit at (%.2f, %.2f) rot %d %s' % (ref, x, y, rot, side))
        self.pl[ref] = (round(x, 3), round(y, 3), rot % 360, side)
        self.taken[side].append(self.rect(ref, x, y, rot, side))

    def pad_xy(self, ref, pad):
        """Board position of a placed part's pad (centre)."""
        x, y, rot, side = self.pl[ref]
        return self.geom(ref, x, y, rot, side)[1][pad]


def box_of(fp):
    """Courtyard (or pad) box at rotation 0 relative to the anchor, and pad
    centres, in mm."""
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    fp.SetOrientationDegrees(0)
    fp.BuildCourtyardCaches()
    xs, ys = [], []
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        bb = cy.BBox()
        xs += [bb.GetLeft() / 1e6, bb.GetRight() / 1e6]
        ys += [bb.GetTop() / 1e6, bb.GetBottom() / 1e6]
    pads = {}
    for p in fp.Pads():
        q = p.GetPosition()
        pads.setdefault(p.GetNumber(), (q.x / 1e6, q.y / 1e6))
        bb = p.GetBoundingBox()
        xs += [bb.GetLeft() / 1e6, bb.GetRight() / 1e6]
        ys += [bb.GetTop() / 1e6, bb.GetBottom() / 1e6]
    return (min(xs), min(ys), max(xs), max(ys)), pads


def rotp(x, y, deg):
    """Turn (x, y) by KiCad's rotation (counter-clockwise on screen, y down)."""
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def overlap(a, b, g=0.0):
    return not (a[2] + g <= b[0] or b[2] + g <= a[0] or a[3] + g <= b[1] or b[3] + g <= a[1])


# ---------------------------------------------------------------- RF chains
def chain(B, comps, start, nets, direction, side='T', pitch_gap=0.35, shunt_side=1, refs=None, alternate=False):
    """Lay out an RF path.

    start      (x, y) of the first node (usually the chip pad the path leaves)
    nets       the nets in order along the path, first to last
    direction  angle of travel in degrees (0 = +x, 90 = -y up the screen)
    refs       optional: only these parts (else every part whose two pads
               join consecutive nets, or join a node to GND/a supply)
    The series part between two nodes sits on the line; each shunt part of
    a node sits beside it, alternating sides (shunt_side first).
    Returns the (x, y) of each node along the line, by net.
    """
    a = math.radians(direction)
    ux, uy = math.cos(a), -math.sin(a)                 # along the path
    nx, ny = -uy, ux                                   # across it
    rot_series = direction % 180                        # pads 1-2 along the path
    by = {c.ref: c for c in comps}
    pool = [by[r] for r in refs] if refs else list(comps)
    series = {}
    for c in pool:
        if c.ref in B.pl:
            continue
        ns = set(c.pins.values())
        for k in range(len(nets) - 1):
            if ns == {nets[k], nets[k + 1]}:
                series.setdefault(k, []).append(c)
    nodes = {}
    pos = 0.0
    x0, y0 = start
    sgn = shunt_side
    for k, net in enumerate(nets):
        nx_, ny_ = x0 + ux * pos, y0 + uy * pos
        nodes[net] = (nx_, ny_)
        # shunts of this node: two-pad parts with this net and a net not in the chain
        sh = [c for c in pool if c.ref not in B.pl and len(c.pins) == 2 and net in c.pins.values()
              and not (set(c.pins.values()) - {net}) & set(nets)]
        sh.sort(key=lambda c: c.ref)
        off = 0.0
        for c in sh:
            (bx0, by0, bx1, by1), pads = B.size[c.ref]
            L = bx1 - bx0
            W = by1 - by0
            # pad on the node side touches the line; the other end points away
            pin_node = [p for p, n in c.pins.items() if n == net][0]
            px, py = pads[pin_node]
            # turn so the node pad faces the path: pads lie along x at rot 0
            rot = (direction + (90 if sgn > 0 else -90)) % 360
            if px > 0:
                rot = (rot + 180) % 360
            d = 0.25 + abs(px) + 0.1
            cx = nx_ + nx * sgn * d + ux * off
            cy = ny_ + ny * sgn * d + uy * off
            B.put(c.ref, cx, cy, rot, side, check=False)
            if alternate:
                sgn = -sgn
                if sgn == shunt_side:
                    off += W + 0.3
            else:
                off += W + 0.3
        if k < len(nets) - 1:
            for i, c in enumerate(series.get(k, [])):
                (bx0, by0, bx1, by1), pads = B.size[c.ref]
                L = bx1 - bx0
                W = by1 - by0
                p1 = [p for p, n in c.pins.items() if n == net][0]
                rot = rot_series if pads[p1][0] < 0 else (rot_series + 180) % 360
                # parallel parts (a trap's L and C) side by side across the path
                o = (i - (len(series[k]) - 1) / 2) * (W + 0.2)
                cx = x0 + ux * (pos + pitch_gap + L / 2) + nx * o
                cy = y0 + uy * (pos + pitch_gap + L / 2) + ny * o
                B.put(c.ref, cx, cy, rot, side, check=False)
            Ls = [B.size[c.ref][0][2] - B.size[c.ref][0][0] for c in series.get(k, [])]
            pos += pitch_gap * 2 + (max(Ls) if Ls else 0.6)
    return nodes


# ---------------------------------------------------------------- the packer
POWER_HINT = ('3V3', 'VSYS', 'VSYS_SW', 'VPA', 'PA_IN', 'BAT_P', 'VIN_CHG', 'USB_5V', 'USB_VBUS')


def anchor_pad(B, c):
    """The (ref, pad) a part belongs beside: the placed chip or connector
    pad on its most specific net (fewest pads), never on GND."""
    best = None
    nets = [n for n in c.pins.values() if n and n != 'GND']
    netpads = B.netpads
    for n in nets:
        cands = [(r, p) for (r, p) in netpads.get(n, []) if r in B.pl and r != c.ref and len(B.comps[r].pins) > 2]
        if not cands:
            cands = [(r, p) for (r, p) in netpads.get(n, []) if r in B.pl and r != c.ref]
        if not cands:
            continue
        score = len(netpads[n]) + (100 if n in POWER_HINT else 0)
        if best is None or score < best[0]:
            best = (score, cands)
    if best is None:
        return None
    return best[1]


def pack(B, refs, prefer=None, step=0.25, rmax=14.0, log=print):
    """Place every part in refs beside its anchor pin.  prefer: ref -> side
    to try first.  Returns the parts that found no room."""
    left = []
    for ref in refs:
        if ref in B.pl:
            continue
        c = B.comps[ref]
        cands = anchor_pad(B, c)
        if not cands:
            left.append(ref); continue
        # target: the nearest candidate pad to the mean of all of them
        tx, ty, tside = None, None, None
        pts = [(B.pad_xy(r, p), B.pl[r][3]) for r, p in cands]
        (tx, ty), tside = pts[0]
        sides = [prefer.get(ref, tside)] if prefer and ref in prefer else [tside]
        sides += [s for s in ('T', 'B') if s not in sides]
        done = False
        for side in sides:
            r = 0.0
            while r <= rmax and not done:
                n = max(1, int(2 * math.pi * r / step))
                best = None
                for i in range(n):
                    a = 2 * math.pi * i / n
                    x, y = tx + r * math.cos(a), ty + r * math.sin(a)
                    for rot in (0, 90):
                        if B.fits(ref, x, y, rot, side):
                            # prefer the spot that puts the part's own pad of that net nearest the target
                            _, pp = B.geom(ref, x, y, rot, side)
                            d = min(math.hypot(px - tx, py - ty) for px, py in pp.values())
                            if best is None or d < best[0]:
                                best = (d, x, y, rot)
                if best:
                    B.put(ref, best[1], best[2], best[3], side)
                    done = True
                r += step
            if done:
                break
        if not done:
            left.append(ref)
    return left
