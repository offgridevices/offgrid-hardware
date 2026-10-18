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
        # a through-hole pad (or an unplated hole) blocks the other side too
        other = 'B' if side == 'T' else 'T'
        for p in self.fp[ref].Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = p.GetBoundingBox()
                self.taken[other].append((bb.GetLeft() / 1e6 - pcb.CX - 0.15, bb.GetTop() / 1e6 - pcb.CY - 0.15,
                                          bb.GetRight() / 1e6 - pcb.CX + 0.15, bb.GetBottom() / 1e6 - pcb.CY + 0.15))

    def remove(self, ref):
        """Take a placed (surface-mount) part off the board again."""
        x, y, rot, side = self.pl.pop(ref)
        self.taken[side].remove(self.rect(ref, x, y, rot, side))

    def footprint_at(self, ref):
        """ref's footprint, moved to where ref is placed."""
        x, y, rot, side = self.pl[ref]
        fp = self.fp[ref]
        if (side == 'B') != fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetPosition(pcb.P(x, y))
        fp.SetOrientationDegrees(rot)
        return fp

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


def who(B, boxes):
    """The placed parts (or 'keepout') behind courtyard boxes, for messages."""
    out = []
    for o in boxes:
        hit = [r for r, v in B.pl.items() if not r.startswith('_') and v[3] in 'TB'
               and all(abs(a - b) < 1e-6 for a, b in zip(B.rect(r, *v), o))]
        out.append(hit[0] if hit else 'keepout %s' % [round(v, 2) for v in o])
    return out


def overlap(a, b, g=0.0):
    return not (a[2] + g <= b[0] or b[2] + g <= a[0] or a[3] + g <= b[1] or b[3] + g <= a[1])


# ---------------------------------------------------------------- RF chains
PATH_NETS = set()        # every net that is a node of some RF path (layout.py fills it)

def chain(B, comps, start, nets, direction, side='T', pitch_gap=0.25, shunt_side=1, refs=None, alternate=False):
    """Lay out an RF path.

    start      (x, y) of the first node (usually just off the chip pad the
               path leaves; the track from the pad to it is drawn later)
    nets       the nets in order along the path, first to last
    direction  angle of travel in degrees (0 = +x, 90 = up the screen)
    The series part between two nodes sits on the line, its pads along it;
    each shunt part of a node stands across the line beside the node, its
    node pad nearest the line (shunt_side picks the side; alternate puts
    them on both).  Every part is placed only where its courtyard is free:
    a part that does not fit moves along the line until it does, and the
    next node starts after it.  Returns each node's (x, y), by net.
    """
    a = math.radians(direction)
    ux, uy = math.cos(a), -math.sin(a)                 # along the path
    nx, ny = -uy, ux                                   # across it (shunt_side 1)
    pool = [B.comps[r] for r in refs] if refs else list(comps)
    pool = [c for c in pool if c.ref not in B.pl]
    x0, y0 = start
    pos = 0.0
    nodes = {}

    def at(t, s_=0.0):
        return x0 + ux * t + nx * s_, y0 + uy * t + ny * s_

    def try_put(c, rot, t, s_, pad_net):
        """Place c with its pad on pad_net at along-line t, across-line s_
        (pad position, not the part's centre).  True if it fits."""
        px, py = at(t, s_)
        # where that pad sits relative to the part origin at this rotation
        (_, pads) = B.geom(c.ref, 0, 0, rot, side)
        pad = [p for p, n in c.pins.items() if n == pad_net][0]
        dx, dy = pads[pad]
        cx, cy = px - dx, py - dy
        if B.fits(c.ref, cx, cy, rot, side):
            B.put(c.ref, cx, cy, rot, side)
            return True
        return False

    def along_rot(c, first_net):
        """Rotation putting c's pads along the line, first_net's pad first."""
        for rot in (direction % 360, (direction + 180) % 360):
            (_, pads) = B.geom(c.ref, 0, 0, rot, side)
            p1 = [p for p, n in c.pins.items() if n == first_net][0]
            p2 = [p for p, n in c.pins.items() if n != first_net][0]
            d = (pads[p2][0] - pads[p1][0]) * ux + (pads[p2][1] - pads[p1][1]) * uy
            if d > 0:
                return rot, d
        raise ValueError('cannot turn %s along %d' % (c.ref, direction))

    def across_rot(c, node_net, sgn):
        """Rotation standing c across the line, its node pad nearest the line."""
        for rot in ((direction + 90) % 360, (direction + 270) % 360):
            (_, pads) = B.geom(c.ref, 0, 0, rot, side)
            p1 = [p for p, n in c.pins.items() if n == node_net][0]
            p2 = [p for p, n in c.pins.items() if n != node_net][0]
            d = (pads[p2][0] - pads[p1][0]) * nx + (pads[p2][1] - pads[p1][1]) * ny
            if d * sgn > 0:
                return rot
        raise ValueError('cannot stand %s across %d' % (c.ref, direction))

    for k, net in enumerate(nets):
        nodes[net] = at(pos) + (direction,)
        path = set(nets) | set(PATH_NETS)
        # shunts: parts from this node to ground, or to a supply off the path
        # (a feed choke; the amplifier's big one is placed before the chain)
        sh = [c for c in pool if c.ref not in B.pl and len(c.pins) == 2 and net in c.pins.values()
              and len(set(c.pins.values()) - {net}) == 1
              and not (set(c.pins.values()) - {net}) & (set(nets) | set(PATH_NETS))]
        # the longest shunt goes on shunt_side, the others alternate from the
        # far side: a node's row of shunts stays short along the line
        size = lambda c: max(B.size[c.ref][0][2] - B.size[c.ref][0][0], B.size[c.ref][0][3] - B.size[c.ref][0][1])
        sh.sort(key=lambda c: ('GND' not in c.pins.values(), -size(c), c.ref))
        sgn = shunt_side
        reach = pos
        for c in sh:
            placed = False
            for step in range(0, 60):                  # nearest the node first, either side
                t = pos + step * 0.2
                for sg in (sgn, -sgn):
                    rot = across_rot(c, net, sg)
                    for s_ in (sg * 0.55, sg * 0.75):
                        if try_put(c, rot, t, s_, net):
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break
            if not placed:
                px, py = at(pos, sgn * 0.55)
                rot = across_rot(c, net, sgn)
                r = B.rect(c.ref, px, py, rot, side)
                hits = [o for o in B.taken[side] + B.keepouts[side] if overlap(r, o, GAP)]
                raise ValueError('chain %s: no room for shunt %s near (%.2f, %.2f) box %s: %s'
                                 % (net, c.ref, px, py, [round(v, 2) for v in r], who(B, hits[:4])))
            bx = B.rect(c.ref, *B.pl[c.ref][:3], side)
            reach = max(reach, max((bx[0] - x0) * ux + (bx[1] - y0) * uy, (bx[2] - x0) * ux + (bx[3] - y0) * uy,
                                   (bx[0] - x0) * ux + (bx[3] - y0) * uy, (bx[2] - x0) * ux + (bx[1] - y0) * uy))
            if alternate or len(sh) > 1:
                sgn = -sgn
        if k == len(nets) - 1:
            break
        ser = [c for c in pool if c.ref not in B.pl and set(c.pins.values()) == {net, nets[k + 1]}]
        if not ser:
            raise ValueError('chain: nothing joins %s and %s' % (net, nets[k + 1]))
        far = pos
        t0 = None
        for i, c in enumerate(ser):
            rot, span = along_rot(c, net)
            placed = False
            if i == 0:                                    # on the line
                for step in range(0, 150):
                    t = pos + pitch_gap + step * 0.1
                    if try_put(c, rot, t, 0.0, net):
                        placed = True; t0 = t
                        break
            else:                                         # a trap's other part: beside it, level with it
                # level with the first part if at all possible: try every
                # offset out to 2.4 mm on both sides before moving along
                offs = [sg * (0.9 + 0.1 * j) for j in range(16) for sg in (-shunt_side, shunt_side)]
                for step in range(0, 60):
                    for off in offs:
                        t = t0 + step * 0.1
                        if try_put(c, rot, t, off, net):
                            placed = True
                            break
                    if placed:
                        break
            if not placed:
                px, py = at(pos + pitch_gap)
                r = B.rect(c.ref, px, py, rot, side)
                hits = [o for o in B.taken[side] + B.keepouts[side] if overlap(r, o, GAP)]
                raise ValueError('chain: no room for series %s at (%.2f, %.2f): %s' % (c.ref, px, py, who(B, hits[:4])))
            far = max(far, t + span)
        pos = max(far + pitch_gap, reach - 0.2 if sh else far + pitch_gap)
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
