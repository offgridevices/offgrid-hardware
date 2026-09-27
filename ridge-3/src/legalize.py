# -*- coding: utf-8 -*-
"""Nudge hand-placed parts apart until no two courtyards on the same side
overlap, nothing crosses the board edge and nothing sits in a mounting-hole
keepout.  Placement stays a human decision; this only removes the last
fractions of a millimetre of overlap so the tables can be written roughly.

Parts named in `fixed` never move (connectors, MCUs, pads, holes)."""
import math
import pcb, parts

_bb_cache = {}

def local_bbox(fpid):
    """Courtyard bbox of a footprint at rotation 0, in mm, about its origin."""
    if fpid not in _bb_cache:
        fp = pcb.load_fp(fpid)
        import pcbnew
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount():
            bb = cy.BBox()
            _bb_cache[fpid] = (bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
        else:
            bb = fp.GetBoundingBox(False)
            _bb_cache[fpid] = (bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
    return _bb_cache[fpid]

def rot_bbox(bb, rot, side):
    x0, y0, x1, y1 = bb
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if side == 'B':
        pts = [(x, -y) for x, y in pts]     # KiCad flips top/bottom about the x axis
    a = math.radians(rot)
    # KiCad: positive angle rotates counter-clockwise on screen (y down)
    rp = [(x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)) for x, y in pts]
    xs = [p[0] for p in rp]; ys = [p[1] for p in rp]
    return min(xs), min(ys), max(xs), max(ys)

_pth_cache = {}

def through_hole(fpid):
    """True if the footprint has plated or unplated holes: it occupies
    both sides of the board."""
    if fpid not in _pth_cache:
        import pcbnew
        _pth_cache[fpid] = any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                               for p in pcb.load_fp(fpid).Pads())
    return _pth_cache[fpid]

def boxes(comps, placement):
    allp = {**parts.PARTS, **parts.PADS}
    out = {}
    for c in comps:
        x, y, rot, side = placement[c.ref][:4]
        fpid = allp[c.part]['fp']
        bb = rot_bbox(local_bbox(fpid), rot, side)
        out[c.ref] = (x + bb[0], y + bb[1], x + bb[2], y + bb[3], 'TB' if through_hole(fpid) else side)
    return out

def overlaps(bx, gap=0.0):
    refs = list(bx)
    res = []
    for i, a in enumerate(refs):
        A = bx[a]
        for b in refs[i + 1:]:
            B = bx[b]
            if a.startswith('H') or b.startswith('H'):
                continue            # holes are circles: checked separately below
            if A[4] != B[4] and 'TB' not in (A[4], B[4]):
                continue
            ox = min(A[2], B[2]) - max(A[0], B[0]) + gap
            oy = min(A[3], B[3]) - max(A[1], B[1]) + gap
            if ox > 0 and oy > 0:
                res.append((a, b, ox, oy))
    return res

def legalize(comps, placement, fixed, half=pcb.HALF, iters=400, gap=0.02, verbose=True,
             edge_ok=()):
    pl = {k: list(v) for k, v in placement.items()}
    start = {k: (v[0], v[1]) for k, v in pl.items()}
    holes = [(sx * pcb.HOLE, sy * pcb.HOLE) for sx in (-1, 1) for sy in (-1, 1)]
    R = pcb.HOLE_KEEPOUT_R
    for it in range(iters):
        bx = boxes(comps, pl)
        moved = False
        for a, b, ox, oy in overlaps(bx, gap):
            if a.startswith('H') and b.startswith('H'):
                continue
            fa, fb = (a in fixed or a.startswith('H')), (b in fixed or b.startswith('H'))
            if fa and fb:
                continue
            A, B = bx[a], bx[b]
            cax, cay = (A[0] + A[2]) / 2, (A[1] + A[3]) / 2
            cbx, cby = (B[0] + B[2]) / 2, (B[1] + B[3]) / 2
            if ox < oy:
                d = ox + 0.01; axis = 0; s = 1 if cbx >= cax else -1
            else:
                d = oy + 0.01; axis = 1; s = 1 if cby >= cay else -1
            if fa:
                pl[b][axis] += s * d
            elif fb:
                pl[a][axis] -= s * d
            else:
                pl[a][axis] -= s * d / 2; pl[b][axis] += s * d / 2
            moved = True
        # board edge and hole keepouts
        bx = boxes(comps, pl)
        for r, (x0, y0, x1, y1, side) in bx.items():
            if r in fixed or r.startswith('H') or r in edge_ok:
                continue
            e = half - 0.25
            if x0 < -e: pl[r][0] += -e - x0; moved = True
            if x1 > e: pl[r][0] -= x1 - e; moved = True
            if y0 < -e: pl[r][1] += -e - y0; moved = True
            if y1 > e: pl[r][1] -= y1 - e; moved = True
            for hx, hy in holes:
                nx = min(max(hx, x0), x1); ny = min(max(hy, y0), y1)
                dd = math.hypot(nx - hx, ny - hy)
                if dd < R:
                    if dd < 1e-6:
                        continue
                    k = (R - dd + 0.02) / dd
                    pl[r][0] += (nx - hx) * k; pl[r][1] += (ny - hy) * k
                    moved = True
        if not moved:
            break
    bx = boxes(comps, pl)
    left = [o for o in overlaps(bx, 0.0) if not (o[0].startswith('H') and o[1].startswith('H'))]
    if verbose:
        big = sorted(((math.hypot(pl[k][0] - start[k][0], pl[k][1] - start[k][1]), k) for k in pl), reverse=True)
        print('legalize: %d iterations, %d overlaps left; largest moves: %s' % (
            it + 1, len(left), ', '.join('%s %.2f' % (k, d) for d, k in big[:6] if d > 0.05)))
        for o in left[:12]:
            print('   still overlapping: %s / %s (%.2f x %.2f)' % o)
    return {k: tuple(v) for k, v in pl.items()}, left


# ------------------------------------------------------------------ packing
# The push-apart pass above settles fractions of a millimetre; where a
# region is simply full it shuffles parts back and forth.  pack() instead
# places parts one at a time, each at the free spot nearest to where the
# table put it: occupancy is a bitmap per side (0.05 mm cells) with a
# summed-area table, so "is this courtyard free" is four lookups.  Larger
# parts go first; two-pad parts may also try the other orientation.
# Deterministic: same tables, same result.

CELL = 0.05


def _grid_setup(half):
    import numpy as np
    n = int(round(2 * half / CELL))
    return np, n


def _mark(occ, bb, half, n):
    x0, y0, x1, y1 = bb
    i0 = max(0, int((x0 + half) / CELL)); i1 = min(n, int(math.ceil((x1 + half) / CELL)))
    j0 = max(0, int((y0 + half) / CELL)); j1 = min(n, int(math.ceil((y1 + half) / CELL)))
    occ[j0:j1, i0:i1] = True


def _sat(np, occ):
    s = np.zeros((occ.shape[0] + 1, occ.shape[1] + 1), dtype=np.int32)
    s[1:, 1:] = occ.cumsum(0).cumsum(1)
    return s


def pack(comps, placement, fixed, half=pcb.HALF, gap=0.1, edge=0.25, radius=8.0, verbose=True,
         rotatable=None, reserved=(), priority=None, anchor=None):
    """Returns (placement, unplaced refs).  `gap` is kept between
    courtyards; `edge` between a courtyard and the board edge; hole
    keepouts are occupied on both sides; `reserved` is a list of
    (side 'T'/'B', (x0, y0, x1, y1)) kept free for copper (via corridors).
    `priority(comp)` (lower first) orders the parts before size does: the
    parts that must sit at a pin (decoupling, bootstrap) go before the
    ones that only need to be somewhere near.  `anchor(comp)` names the
    part a part belongs with (a regulator's capacitors: the regulator);
    once the anchor is placed, the part's table position moves with it."""
    np, n = _grid_setup(half)
    allp = {**parts.PARTS, **parts.PADS}
    occ = {'T': np.zeros((n, n), dtype=bool), 'B': np.zeros((n, n), dtype=bool)}
    # board edge margin
    m = int(round(edge / CELL))
    for s in occ.values():
        s[:m, :] = s[-m:, :] = s[:, :m] = s[:, -m:] = True
    # hole keepouts
    ys, xs = np.mgrid[0:n, 0:n]
    cx = (xs + 0.5) * CELL - half; cy = (ys + 0.5) * CELL - half
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole = (cx - sx * pcb.HOLE) ** 2 + (cy - sy * pcb.HOLE) ** 2 < (pcb.HOLE_KEEPOUT_R + gap) ** 2
            for s in occ.values():
                s |= hole
    for sd, bb in reserved:
        _mark(occ[sd], bb, half, n)
    pl = {k: tuple(v) for k, v in placement.items()}
    info = {}
    for c in comps:
        fpid = allp[c.part]['fp']
        x, y, rot, side = pl[c.ref][:4]
        info[c.ref] = (fpid, 'TB' if through_hole(fpid) else side)

    def sides(sd):
        return ('T', 'B') if sd == 'TB' else (sd,)

    # fixed parts (and holes) first, exactly where they are
    for c in comps:
        if c.ref in fixed or c.ref.startswith('H'):
            if c.ref.startswith('H'):
                continue
            fpid, sd = info[c.ref]
            x, y, rot, side = pl[c.ref][:4]
            bb = rot_bbox(local_bbox(fpid), rot, side)
            for s in sides(sd):
                _mark(occ[s], (x + bb[0] - gap / 2, y + bb[1] - gap / 2, x + bb[2] + gap / 2, y + bb[3] + gap / 2),
                      half, n)
    movable = [c for c in comps if c.ref not in fixed and not c.ref.startswith('H')]

    def size(c):
        bb = local_bbox(info[c.ref][0])
        return (bb[2] - bb[0]) * (bb[3] - bb[1])
    movable.sort(key=lambda c: ((priority(c) if priority else 0), -round(size(c), 2), c.ref))
    # search offsets, nearest first, out to twice `radius` (a part only
    # goes past `radius` when nothing nearer is free)
    R = int(2 * radius / CELL)
    dj, di = np.mgrid[-R:R + 1, -R:R + 1]
    d2 = (di * di + dj * dj).ravel()
    order = np.argsort(d2, kind='stable')
    di = di.ravel()[order]; dj = dj.ravel()[order]; d2 = d2[order]
    keep = d2 <= R * R
    di, dj = di[keep], dj[keep]
    left = []
    moved = []
    sats = {s: _sat(np, o) for s, o in occ.items()}
    shift = {}
    for c in movable:
        fpid, sd = info[c.ref]
        x, y, rot, side = pl[c.ref][:4]
        a = anchor(c) if anchor else None
        if a in shift:
            x, y = x + shift[a][0], y + shift[a][1]
        rots = [rot]
        if rotatable and rotatable(c):
            rots.append((rot + 90) % 360)
        best = None
        for r in rots:
            bb = rot_bbox(local_bbox(fpid), r, side)
            w = int(math.ceil((bb[2] - bb[0] + gap) / CELL)); h = int(math.ceil((bb[3] - bb[1] + gap) / CELL))
            # cell index of the box's lower-left corner for the hint position
            i0 = int(round((x + bb[0] - gap / 2 + half) / CELL)); j0 = int(round((y + bb[1] - gap / 2 + half) / CELL))
            ii = i0 + di; jj = j0 + dj
            ok = (ii >= 0) & (jj >= 0) & (ii + w <= n) & (jj + h <= n)
            ii, jj, dd = ii[ok], jj[ok], (di[ok] ** 2 + dj[ok] ** 2)
            free = np.ones(len(ii), dtype=bool)
            for s in sides(sd):
                S = sats[s]
                tot = S[jj + h, ii + w] - S[jj, ii + w] - S[jj + h, ii] + S[jj, ii]
                free &= tot == 0
            if not free.any():
                continue
            k = int(np.argmax(free))       # candidates are sorted by distance
            cand = (int(dd[k]) + (0 if r == rot else 4), r, ii[k], jj[k], bb, w, h)
            if best is None or cand[0] < best[0]:
                best = cand
        if best is None:
            left.append(c.ref)
            continue
        _, r, i, j, bb, w, h = best
        nx = i * CELL - half - bb[0] + gap / 2; ny = j * CELL - half - bb[1] + gap / 2
        x0, y0 = placement[c.ref][:2]
        moved.append((math.hypot(nx - x0, ny - y0), c.ref))
        shift[c.ref] = (float(nx) - x0, float(ny) - y0)
        pl[c.ref] = (round(float(nx), 3), round(float(ny), 3), r, side)
        for s in sides(sd):
            occ[s][j:j + h, i:i + w] = True
            sats[s] = _sat(np, occ[s])
    if verbose:
        moved.sort(reverse=True)
        print('pack: %d parts placed, %d without room%s; largest moves: %s' % (
            len(movable) - len(left), len(left), (' ' + str(left)) if left else '',
            ', '.join('%s %.2f' % (r, d) for d, r in moved[:8] if d > 0.05)))
    return pl, left
