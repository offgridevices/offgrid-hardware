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

def boxes(comps, placement):
    allp = {**parts.PARTS, **parts.PADS}
    out = {}
    for c in comps:
        x, y, rot, side = placement[c.ref][:4]
        bb = rot_bbox(local_bbox(allp[c.part]['fp']), rot, side)
        out[c.ref] = (x + bb[0], y + bb[1], x + bb[2], y + bb[3], side)
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
            if A[4] != B[4]:
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
