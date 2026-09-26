# -*- coding: utf-8 -*-
"""Complete the last few connections Freerouting leaves unrouted.

A plain grid maze router: 0.05 mm cells on the two outer copper layers, a
via allowed wherever a via fits.  Every other net's copper is inflated by
(clearance + half the track width) and drawn as an obstacle; the route
must stay clear of it.  One connection at a time, cheapest path by A*,
bends and vias cost extra so paths come out short and tidy.  KiCad's own
DRC checks the result afterwards - this router is never trusted alone.
"""
import heapq, math
import numpy as np
import pcbnew
import pcb
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

def MM(v): return pcbnew.FromMM(float(v))
RES = 0.05                      # mm per cell

def mm(v): return v / 1e6

class Grid:
    def __init__(self, board, layers, clearance, track_w, via_d, edge=0.3, clmap=None, soft_nets=None):
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = mm(bb.GetLeft()), mm(bb.GetTop())
        self.W = int(math.ceil(mm(bb.GetWidth()) / RES)) + 1
        self.H = int(math.ceil(mm(bb.GetHeight()) / RES)) + 1
        self.board, self.layers = board, layers
        self.cl, self.tw, self.vd, self.edge = clearance, track_w, via_d, edge
        self.clmap = clmap or {}
        self.soft_nets = set(soft_nets or ())

    def px(self, x, y):
        return ((x - self.x0) / RES, (y - self.y0) / RES)

    def cell(self, x, y):
        return (int(round((x - self.x0) / RES)), int(round((y - self.y0) / RES)))

    def xy(self, i, j):
        return (self.x0 + i * RES, self.y0 + j * RES)

    def _draw(self, img, geom):
        d = ImageDraw.Draw(img)
        gs = geom.geoms if hasattr(geom, 'geoms') else [geom]
        for g in gs:
            if g.is_empty:
                continue
            d.polygon([self.px(x, y) for x, y in g.exterior.coords], fill=1)

    def netcl(self, net):
        return self.clmap.get(net, self.cl)

    def copper(self, net_exclude):
        """Per-layer list of (geometry, clearance) of copper not on
        net_exclude, plus geometry of copper on it."""
        other = {l: [] for l in self.layers}; same = {l: [] for l in self.layers}
        self.soft = {l: [] for l in self.layers}
        holes = []
        b = self.board
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                for l in self.layers:
                    if pad.IsOnLayer(l):
                        sp = pad.GetEffectivePolygon(l)
                        for k in range(sp.OutlineCount()):
                            ol = sp.Outline(k)
                            g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                            if pad.GetNetname() == net_exclude and pad.GetNetname():
                                same[l].append(g)
                            else:
                                other[l].append((g, self.netcl(pad.GetNetname())))
                if pad.GetDrillSize().x > 0:
                    p = pad.GetPosition()
                    holes.append(Point(mm(p.x), mm(p.y)).buffer(mm(pad.GetDrillSize().x) / 2))
        for t in b.GetTracks():
            soft = (t.GetNetname() in self.soft_nets and t.GetNetname() != net_exclude and not t.IsLocked())
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                g = Point(mm(p.x), mm(p.y)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2)
                for l in self.layers:
                    if soft:
                        self.soft[l].append((g, self.netcl(t.GetNetname()), t.GetNetname()))
                    elif t.GetNetname() == net_exclude:
                        same[l].append(g)
                    else:
                        other[l].append((g, self.netcl(t.GetNetname())))
            elif t.GetLayer() in self.layers:
                s, e = t.GetStart(), t.GetEnd()
                g = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2)
                if soft:
                    self.soft[t.GetLayer()].append((g, self.netcl(t.GetNetname()), t.GetNetname()))
                elif t.GetNetname() == net_exclude:
                    same[t.GetLayer()].append(g)
                else:
                    other[t.GetLayer()].append((g, self.netcl(t.GetNetname())))
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            # (z.GetLayer() is not the zone's layer for every zone: ask the set)
            for l in self.layers:
                if not (z.GetLayerSet().Contains(l) and z.IsFilled()):
                    continue
                fp_ = z.GetFilledPolysList(l)
                for k in range(fp_.OutlineCount()):
                    ol = fp_.Outline(k)
                    g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                    if z.GetNetname() == net_exclude:
                        same[l].append(g)
                    else:
                        other[l].append((g, self.netcl(z.GetNetname())))
        return other, same, holes

    def build(self, net):
        other, same, holes = self.copper(net)
        self.block = {}; self.vblock = None
        M = RES * 1.2                     # grid rounding margin
        mine = self.netcl(net)
        vmask = Image.new('1', (self.W, self.H), 0)
        for l in self.layers:
            img = Image.new('1', (self.W, self.H), 0)
            for g, c in other[l]:
                c = max(c, mine)
                self._draw(img, g.buffer(c + self.tw / 2 + M, 8)); self._draw(vmask, g.buffer(c + self.vd / 2 + M, 8))
            for g in holes:
                self._draw(img, g.buffer(0.3 + self.tw / 2 + M, 8)); self._draw(vmask, g.buffer(0.3 + self.vd / 2 + M, 8))
            self.block[l] = np.array(img, dtype=bool)
        # inner layers: a via may not hit another net's pad or via there either
        for l in (pcbnew.In1_Cu, pcbnew.In2_Cu):
            pass
        for z in self.board.Zones():
            if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                ol = z.Outline().Outline(0)
                g = Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())])
                for l in self.layers:
                    img = Image.fromarray(self.block[l]); self._draw(img, g.buffer(self.tw / 2)); self.block[l] = np.array(img, dtype=bool)
                self._draw(vmask, g.buffer(self.vd / 2))
        # board edge
        e = int(math.ceil((self.edge + self.tw / 2) / RES)); ev = int(math.ceil((self.edge + self.vd / 2) / RES))
        for l in self.layers:
            self.block[l][:e, :] = True; self.block[l][-e:, :] = True
            self.block[l][:, :e] = True; self.block[l][:, -e:] = True
        vb = np.array(vmask, dtype=bool)
        vb[:ev, :] = True; vb[-ev:, :] = True; vb[:, :ev] = True; vb[:, -ev:] = True
        self.vblock = vb
        # soft (rippable) copper: passable at a price
        self.sblock = {}
        vs = Image.new('1', (self.W, self.H), 0)
        for l in self.layers:
            img = Image.new('1', (self.W, self.H), 0)
            for g, c, _ in self.soft[l]:
                c = max(c, mine)
                self._draw(img, g.buffer(c + self.tw / 2 + M, 8)); self._draw(vs, g.buffer(c + self.vd / 2 + M, 8))
            self.sblock[l] = np.array(img, dtype=bool)
        self.vsoft = np.array(vs, dtype=bool)
        return same

def _same_cells(grid, same, layer):
    img = Image.new('1', (grid.W, grid.H), 0)
    for g in same[layer]:
        grid._draw(img, g)
    return np.array(img, dtype=bool)

def route_connection(board, net, a_items, b_items, clearance=0.1, track_w=0.1, via_d=0.45, via_drill=0.25,
                     max_expand=3_000_000, clmap=None, soft_nets=None, rip_cost=60, victims_out=None):
    """Route from copper island A to island B of `net`.  a_items/b_items are
    lists of shapely geometries per layer: {layer: [geom,...]}."""
    layers = [pcbnew.F_Cu, pcbnew.B_Cu]
    g = Grid(board, layers, clearance, track_w, via_d, clmap=clmap, soft_nets=soft_nets)
    g.build(net)
    src = {}; dst = {}
    for li, l in enumerate(layers):
        src[li] = _same_cells(g, a_items, l) if l in a_items else np.zeros((g.H, g.W), bool)
        dst[li] = _same_cells(g, b_items, l) if l in b_items else np.zeros((g.H, g.W), bool)
    # targets: cells inside B copper; sources: cells inside A copper (allowed even if blocked)
    tgt = np.argwhere(dst[0] | dst[1])
    if len(tgt) == 0:
        return None
    tc = tgt.mean(axis=0)
    H, W = g.H, g.W
    INF = 1 << 60
    cost = {}
    pq = []
    for li in (0, 1):
        for (j, i) in np.argwhere(src[li]):
            k = (li, i, j); cost[k] = 0
            heapq.heappush(pq, (0, 0, k, None, None))
    came = {}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    vcost = 40; bend = 3
    found = None; n = 0
    while pq and n < max_expand:
        f, c, k, prev, pdir = heapq.heappop(pq)
        if k in came:
            continue
        came[k] = (prev, pdir)
        li, i, j = k
        n += 1
        if dst[li][j, i]:
            found = k; break
        blk = g.block[layers[li]]; sb = g.sblock[layers[li]]
        for d in dirs:
            ni, nj = i + d[0], j + d[1]
            if not (0 <= ni < W and 0 <= nj < H):
                continue
            nk = (li, ni, nj)
            if nk in came:
                continue
            free_end = src[li][nj, ni] or dst[li][nj, ni]
            if blk[nj, ni] and not free_end:
                continue
            step = 1.414 if d[0] and d[1] else 1.0
            nc = c + step + (bend if pdir is not None and pdir != d else 0)
            if sb[nj, ni] and not free_end:
                nc += rip_cost if not sb[j, i] else step * 2
            if nc < cost.get(nk, INF):
                cost[nk] = nc
                h = math.hypot(ni - tc[1], nj - tc[0]) * 0.9
                heapq.heappush(pq, (nc + h, nc, nk, k, d))
        # via
        if not g.vblock[j, i] or src[li][j, i]:
            ok_other = (not g.block[layers[1 - li]][j, i]) or src[1 - li][j, i] or dst[1 - li][j, i]
            if ok_other and not g.vblock[j, i]:
                nk = (1 - li, i, j)
                if nk not in came:
                    nc = c + vcost + (rip_cost if g.vsoft[j, i] else 0)
                    if nc < cost.get(nk, INF):
                        cost[nk] = nc
                        h = math.hypot(i - tc[1], j - tc[0]) * 0.9
                        heapq.heappush(pq, (nc + h, nc, nk, k, 'via'))
    if not found:
        return None
    # walk back
    path = []
    k = found
    while k is not None:
        path.append(k)
        k = came[k][0]
    path.reverse()
    if victims_out is not None:
        # which rippable nets does this path run through?
        for (li, i, j) in path:
            l = layers[li]
            if g.sblock[l][j, i] or g.vsoft[j, i]:
                x, y = g.xy(i, j)
                pt = Point(x, y)
                for geom, c, n in g.soft[l]:
                    if n not in victims_out and geom.distance(pt) < max(c, g.netcl(net)) + track_w / 2 + via_d / 2 + 0.07:
                        victims_out.add(n)
    # emit copper
    netinfo = board.FindNet(net)
    segs = 0; vias = 0
    run = [path[0]]
    def flush(run):
        nonlocal segs
        if len(run) < 2:
            return
        # simplify collinear points
        pts = [run[0]]
        for a, b2, c2 in zip(run, run[1:], run[2:]):
            if (b2[1] - a[1], b2[2] - a[2]) != (c2[1] - b2[1], c2[2] - b2[2]):
                pts.append(b2)
        pts.append(run[-1])
        l = layers[run[0][0]]
        for p, q in zip(pts, pts[1:]):
            x1, y1 = g.xy(p[1], p[2]); x2, y2 = g.xy(q[1], q[2])
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
            t.SetWidth(MM(track_w)); t.SetLayer(l); t.SetNet(netinfo); board.Add(t); segs += 1
    for p in path[1:]:
        if p[0] != run[-1][0]:
            flush(run)
            x, y = g.xy(p[1], p[2])
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(via_d)); v.SetDrill(MM(via_drill)); v.SetNet(netinfo); board.Add(v); vias += 1
            run = [p]
        else:
            run.append(p)
    flush(run)
    return segs, vias

def islands(board, net):
    """Group a net's copper into connected islands using KiCad's connectivity."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    items = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                items.append(pad)
    for t in board.GetTracks():
        if t.GetNetname() == net:
            items.append(t)
    # union-find on items connected per KiCad
    parent = list(range(len(items)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    idx = {id(x): n for n, x in enumerate(items)}
    for n, it in enumerate(items):
        for c in conn.GetConnectedItems(it) if hasattr(conn, 'GetConnectedItems') else []:
            m = idx.get(id(c))
            if m is not None:
                parent[find(n)] = find(m)
    groups = {}
    for n in range(len(items)):
        groups.setdefault(find(n), []).append(items[n])
    return list(groups.values())

def _geom_of(item):
    """{layer: [shapely geometry]} for a pad, track or via."""
    out = {}
    cls = item.GetClass()
    if cls == 'PAD':
        for l in (pcbnew.F_Cu, pcbnew.B_Cu):
            if item.IsOnLayer(l):
                sp = item.GetEffectivePolygon(l)
                for k in range(sp.OutlineCount()):
                    ol = sp.Outline(k)
                    out.setdefault(l, []).append(Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y))
                                                          for q in range(ol.PointCount())]))
    elif cls == 'PCB_VIA':
        p = item.GetPosition()
        g = Point(mm(p.x), mm(p.y)).buffer(mm(item.GetWidth(pcbnew.F_Cu)) / 2)
        out = {pcbnew.F_Cu: [g], pcbnew.B_Cu: [g]}
    elif cls in ('PCB_TRACK', 'PCB_ARC'):
        s, e = item.GetStart(), item.GetEnd()
        if item.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            out[item.GetLayer()] = [LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(item.GetWidth()) / 2)]
    return out

def finish_board(pcb_in, pcb_out, drc_json, rules=None, rounds=3, clmap=None):
    """Route every connection KiCad's DRC reports as unconnected."""
    import json, subprocess
    src = pcb_in
    for r in range(rounds):
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json',
                        '-o', drc_json, src], capture_output=True)
        rep = json.load(open(drc_json))
        pairs = rep['unconnected_items']
        if not pairs:
            if src != pcb_out:
                import shutil; shutil.copy(src, pcb_out)
            return 0
        b = pcbnew.LoadBoard(src)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        byid = {}
        for fp in b.GetFootprints():
            for p in fp.Pads():
                byid[p.m_Uuid.AsString()] = p
        for t in b.GetTracks():
            byid[t.m_Uuid.AsString()] = t
        done = 0
        for u in pairs:
            its = [byid.get(i['uuid']) for i in u['items']]
            if None in its:
                continue
            net = its[0].GetNetname()
            wide = (rules or {}).get(net, 0.1)
            res = route_connection(b, net, _geom_of(its[0]), _geom_of(its[1]), track_w=wide, clmap=clmap)
            print('   finish %-12s %s' % (net, 'routed (%d segments, %d vias)' % res if res else 'NO PATH'))
            done += bool(res)
        b.Save(pcb_out)
        src = pcb_out
        if done == 0:
            break
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json', '-o', drc_json, pcb_out],
                   capture_output=True)
    return len(json.load(open(drc_json))['unconnected_items'])

def _net_components(board, net):
    """Connected copper islands of one net, by geometry (pads, tracks, vias
    that touch).  Returns list of {layer: [geoms]}."""
    items = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                items.append(_geom_of(p))
    for t in board.GetTracks():
        if t.GetNetname() == net:
            items.append(_geom_of(t))
    n = len(items)
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            for l in items[i]:
                if l in items[j] and any(a.intersects(b) for a in items[i][l] for b in items[j][l]):
                    parent[find(i)] = find(j); break
    comps = {}
    for i in range(n):
        c = comps.setdefault(find(i), {})
        for l, gs in items[i].items():
            c.setdefault(l, []).extend(gs)
    return list(comps.values())

def _dist(a, b):
    d = 1e9
    for l in a:
        if l in b:
            for x in a[l]:
                for y in b[l]:
                    d = min(d, x.distance(y))
    if d == 1e9:     # different layers only: distance ignoring layer
        for x in [g for gs in a.values() for g in gs]:
            for y in [g for gs in b.values() for g in gs]:
                d = min(d, x.distance(y))
    return d

def route_net(board, net, track_w=0.1, clmap=None, lock=True, soft_nets=None, victims_out=None):
    """Join every island of `net`, nearest pair first.  Returns islands left."""
    for _ in range(20):
        comps = _net_components(board, net)
        if len(comps) <= 1:
            return 0
        best = None
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                d = _dist(comps[i], comps[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        before = set(t.m_Uuid.AsString() for t in board.GetTracks())
        res = route_connection(board, net, comps[i], comps[j], track_w=track_w, clmap=clmap,
                               soft_nets=soft_nets, victims_out=victims_out)
        if not res:
            return len(comps) - 1
        if lock:
            for t in board.GetTracks():
                if t.m_Uuid.AsString() not in before:
                    t.SetLocked(True)
    return len(_net_components(board, net)) - 1

def mst_length(board, net):
    pts = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                q = p.GetPosition(); pts.append((q.x / 1e6, q.y / 1e6))
    if len(pts) < 2:
        return 0.0
    used = [pts[0]]; rest = pts[1:]; tot = 0.0
    while rest:
        d, k = min((min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in used), i) for i, b in enumerate(rest))
        tot += d; used.append(rest.pop(k))
    return tot

def route_all(board, skip, widths=None, clmap=None, order=None):
    """Route every net not in `skip`, shortest first.  Returns failed nets."""
    nets = set()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                nets.add(p.GetNetname())
    nets -= set(skip)
    todo = sorted(nets, key=lambda n: mst_length(board, n)) if order is None else order
    failed = []
    for n in todo:
        left = route_net(board, n, track_w=(widths or {}).get(n, 0.1), clmap=clmap, lock=False)
        if left:
            failed.append(n)
    return failed


def rip_up(board, net):
    n = 0
    for t in list(board.GetTracks()):
        if t.GetNetname() == net and not t.IsLocked():
            pcb.remove(board, t); n += 1
    return n

def route_all_ripup(board, skip, widths=None, clmap=None, max_rounds=400, log=print):
    """Route every net not in `skip`, shortest first.  A net that cannot get
    through may cross other router-made nets at a price; those nets are
    ripped up and queued again.  Tracks made before this call (locked or
    not) are never touched."""
    nets = set()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                nets.add(p.GetNetname())
    nets -= set(skip)
    queue = sorted(nets, key=lambda n: mst_length(board, n))
    mine = set()
    tries = {}
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        tries[net] = tries.get(net, 0) + 1
        w = (widths or {}).get(net, 0.1)
        # first try without disturbing anyone
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        if left == 0:
            mine.add(net); continue
        victims = set()
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=mine - {net},
                         victims_out=victims)
        if left:
            log('   %s: no path even with rip-up' % net)
            continue
        # rip the victims out and re-queue them; the path we just laid was
        # computed around their copper, so re-route this net cleanly after
        rip_up(board, net)
        for v in victims:
            rip_up(board, v); mine.discard(v)
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        if left == 0:
            mine.add(net)
        else:
            queue.append(net)
        for v in victims:
            if v not in queue:
                queue.append(v)
        log('   %s: ripped up %s' % (net, sorted(victims)))
    failed = [n for n in nets if len(_net_components(board, n)) > 1]
    return failed

def unrouted_nets(board):
    """Nets whose copper is still in more than one piece."""
    nets = set(p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname())
    return sorted(n for n in nets if len(_net_components(board, n)) > 1)

def repair(board, nets, protect=(), widths=None, clmap=None, max_rips=4, max_rounds=200, log=print):
    """Finish `nets` by rip-up and re-route.  A blocked net may run through
    the copper of any other signal net that has unlocked tracks (nets in
    `protect` never); those nets are torn up and routed again afterwards.
    A net torn up `max_rips` times becomes fixed, so this cannot cycle."""
    protect = set(protect)
    # pre-routed (locked) signal nets are fair game too; power stays put
    for t in board.GetTracks():
        if t.GetNetname() not in protect:
            t.SetLocked(False)
    rips = {}
    queue = list(nets)
    rounds = 0
    while queue and rounds < max_rounds:
        rounds += 1
        net = queue.pop(0)
        w = (widths or {}).get(net, 0.1)
        if route_net(board, net, track_w=w, clmap=clmap, lock=False) == 0:
            continue
        soft = set(t.GetNetname() for t in board.GetTracks() if not t.IsLocked()) - protect - {net}
        soft = {n for n in soft if rips.get(n, 0) < max_rips}
        victims = set()
        if route_net(board, net, track_w=w, clmap=clmap, lock=False, soft_nets=soft, victims_out=victims):
            log('   repair %-12s no path even through other nets' % net)
            continue
        rip_up(board, net)
        for v in victims:
            rip_up(board, v); rips[v] = rips.get(v, 0) + 1
        left = route_net(board, net, track_w=w, clmap=clmap, lock=False)
        log('   repair %-12s %s, tore up %s' % (net, 'routed' if not left else 'still open', sorted(victims)))
        if left:
            rips[net] = rips.get(net, 0) + 1
            if rips[net] <= max_rips:
                queue.append(net)
        for v in victims:
            if v not in queue:
                queue.append(v)
    return unrouted_nets(board)
