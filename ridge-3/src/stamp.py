# -*- coding: utf-8 -*-
"""Route one channel of a board built from turned copies of a channel
template, then stamp that routing onto the other channels.

The ESC's four channels are one template turned 0, 90, -90 and 180
degrees round the board's centre (esc_layout.CHANNELS).  Routed all at
once, the channels fight over the same corridors and the router leaves a
different handful of connections open in each.  So one channel is routed
on its own, in a way that fits every channel:

  1. Its region.  Every point of the board belongs to the channel whose
     parts' pads are nearest, measured in the template's frame and turned,
     so the four regions are exact turned copies of one another; each is
     shrunk by half a clearance, so neighbouring copies keep a clearance
     between them.  Everything outside the template channel's region is a
     keepout for the router.
  2. What differs between channels.  The shared parts' pads, and any
     fixed copper of a channel (its own or a shared net's: plane vias,
     escape vias) whose turned copy the template channel lacks, are turned
     into the template's frame, where they block the router as they would
     in their own channel.
  3. Freerouting routes the template channel's own nets only (the nets
     whose pads all sit on its parts; every other net's class is ignored,
     -inc), inside the region, with a few sets of router costs at once
     (VARIANTS); the routing that leaves the fewest nets open is kept.  A
     shared net with two or more pads on the channel's parts (a chip's
     supply and its capacitors) is routed with it that far (local_shared).
  4. The routing is copied, turned, onto every channel, each net renamed to
     its counterpart there.  KiCad's DRC checks the result, and a copied
     track or via in any violation is removed again (a packed part may sit
     a few hundredths of a millimetre off its turned spot).

The board's router then routes the shared nets and whatever the copies
left open, with the copies as its starting wiring.
"""
import math, os, re, json, shutil, subprocess
import numpy as np
import pcbnew
import shapely
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union, split
import pcb, route

ALL_CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
VIA_RING = 0.0          # vias count with at least this ring (route.VIA_RING)


def mm(v):
    return v / 1e6


def _cs(a):
    r = math.radians(a)
    return round(math.cos(r), 12), round(math.sin(r), 12)


def turn(a, x, y):
    """Template frame -> the channel turned by `a` degrees (KiCad's sense,
    esc_layout.xf_point).  Board mm relative to the centre."""
    c, s = _cs(a)
    return (x * c + y * s, -x * s + y * c)


def unturn(a, x, y):
    c, s = _cs(a)
    return (x * c - y * s, x * s + y * c)


def _turn_geom(g, a, inverse=False):
    f = unturn if inverse else turn
    return shapely.transform(g, lambda xy: np.column_stack(f(a, xy[:, 0] - pcb.CX, xy[:, 1] - pcb.CY))
                             + (pcb.CX, pcb.CY))


def _pad_poly(p, layer):
    sp = p.GetEffectivePolygon(layer)
    out = []
    for k in range(sp.OutlineCount()):
        ol = sp.Outline(k)
        out.append(Polygon([(mm(ol.CPoint(q).x), mm(ol.CPoint(q).y)) for q in range(ol.PointCount())]))
    return unary_union(out)


def _item_geoms(t):
    """{layer: geometry} of a track or via (a via on every copper layer)."""
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        r = max(mm(t.GetWidth(pcbnew.F_Cu)) / 2, mm(t.GetDrillValue()) / 2 + VIA_RING)
        g = Point(mm(p.x), mm(p.y)).buffer(r, 16)
        return {l: g for l in ALL_CU}
    s, e = t.GetStart(), t.GetEnd()
    return {t.GetLayer(): LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2, 8)}


def template_channel(channels):
    t = [n for n, a in channels.items() if a % 360 == 0]
    if not t:
        raise SystemExit('stamp: no channel at 0 degrees to serve as the template')
    return t[0]


def counterparts(b, parts, channels):
    """{template net: {channel: its net there}} for every net whose pads
    all sit on the template channel's parts, where every channel has a net
    on exactly the same pads (role, pad number)."""
    role_of = {ref: (n, role) for n, rr in parts.items() for role, ref in rr.items()}
    pads_of = {}
    for fp in b.GetFootprints():
        k = role_of.get(fp.GetReference())
        for p in fp.Pads():
            if p.GetNetname():
                pads_of.setdefault(p.GetNetname(), []).append(k and (k[0], k[1], p.GetNumber()))
    sig = {}
    for net, pl in pads_of.items():
        if None in pl or len(set(k[0] for k in pl)) != 1:
            continue
        sig[(pl[0][0], frozenset((r, num) for _, r, num in pl))] = net
    t = template_channel(channels)
    out = {}
    for (n, s), net in sig.items():
        if n == t:
            m = {k: sig.get((k, s)) for k in channels}
            if all(m.values()):
                out[net] = m
    return out


def _mask_polys(mask, res, K):
    """Boolean grid (cells at (i - K) * res) -> shapely geometry, board mm
    relative to the centre."""
    boxes = []
    for j in range(mask.shape[0]):
        row = mask[j]
        if not row.any():
            continue
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        for a, c in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            boxes.append(box((a - K - 0.5) * res, (j - K - 0.5) * res, (c - K - 0.5) * res, (j - K + 0.5) * res))
    return unary_union(boxes)


def region(b, parts, channels, res=0.1, shrink=0.07):
    """The template channel's region (absolute board mm): the points whose
    nearest channel pads are its own, shrunk by `shrink`."""
    from scipy import ndimage
    t = template_channel(channels)
    K = int(math.ceil(pcb.HALF / res)) + 2
    xs = (np.arange(2 * K + 1) - K) * res
    X, Y = np.meshgrid(xs, xs)
    geoms = []
    for ref in parts[t].values():
        for p in b.FindFootprintByReference(ref).Pads():
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(l):
                    geoms.append(_pad_poly(p, l))
    inside = shapely.contains_xy(unary_union(geoms), X + pcb.CX, Y + pcb.CY)
    d = ndimage.distance_transform_edt(~inside) * res
    dist = {}
    for k, a in channels.items():
        u, v = unturn(a, X, Y)
        iu = np.clip(np.rint(u / res).astype(int) + K, 0, 2 * K)
        jv = np.clip(np.rint(v / res).astype(int) + K, 0, 2 * K)
        dist[k] = d[jv, iu]
    others = np.min([dist[k] for k in channels if k != t], axis=0)
    g = _mask_polys(dist[t] < others, res, K).buffer(-shrink).simplify(0.02)
    g = shapely.transform(g, lambda xy: xy + (pcb.CX, pcb.CY))
    return unary_union([q for q in getattr(g, 'geoms', [g]) if q.area > 0.05])


def _simple(g):
    """Split polygons with holes into polygons without (the DSN keepouts
    take a plain outline)."""
    out = []
    todo = [q for q in getattr(g, 'geoms', [g]) if isinstance(q, Polygon) and not q.is_empty]
    while todo:
        q = todo.pop()
        if q.area < 1e-4:
            continue
        if not q.interiors:
            out.append(q)
            continue
        cx = q.interiors[0].centroid.x
        (x0, y0, x1, y1) = q.bounds
        for piece in split(q, LineString([(cx, y0 - 1), (cx, y1 + 1)])).geoms:
            todo.append(piece)
    return out


def lines(b, parts, channels):
    """{template channel's net: {channel: net}} for the nets that run from
    one channel's parts to shared parts only (each MCU's signal input from
    the stack connector), matched by the channel pad (role, number)."""
    t = template_channel(channels)
    chan_of = {ref: (n, role) for n, rr in parts.items() for role, ref in rr.items()}
    on = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname():
                on.setdefault(p.GetNetname(), []).append((chan_of.get(fp.GetReference()), p.GetNumber()))
    out = {}
    for net, pl in on.items():
        mine = [(c, num) for c, num in pl if c]
        if not mine or len(mine) == len(pl) or len(set(c[0] for c, num in mine)) != 1 or mine[0][0][0] != t:
            continue
        (n, role), num = mine[0]
        m = {}
        for k in channels:
            fp = b.FindFootprintByReference(parts[k][role])
            m[k] = next(p.GetNetname() for p in fp.Pads() if p.GetNumber() == num)
        out[net] = m
    return out


def foreign(b, parts, channels, nets, reg, clear=0.13, match=0.08):
    """{layer: geometry} in the template's frame: what another channel's
    region holds that the template channel's does not.  The shared parts'
    pads, and the tracks and vias (a channel's own or a shared net's) of
    which the template channel has no turned copy."""
    t = template_channel(channels)
    refs = set(r for rr in parts.values() for r in rr.values())
    local = {}                 # a channel's own net -> (channel, template net)
    for tn, m in nets.items():
        for k, net in m.items():
            local[net] = (k, tn)
    # a channel's own line to a shared part (each MCU's signal input from
    # the stack connector) is compared with the template channel's line
    # on the same pad
    for tn, m in lines(b, parts, channels).items():
        for k, net in m.items():
            local.setdefault(net, (k, tn))
    own = {}
    for tr in b.GetTracks():
        own.setdefault(tr.GetNetname(), []).append(_item_geoms(tr))
    reach = reg.buffer(0.6)
    out = {l: [] for l in ALL_CU}

    def add(geoms, a):
        for l, g in geoms.items():
            g = _turn_geom(g, a, inverse=True)
            if g.intersects(reach):
                out[l].append(g.buffer(clear, 8))

    def matched(geoms, a, tn):
        # the same copper within the parts' packing grid (a few 0.01 mm)
        for l, g in geoms.items():
            g = _turn_geom(g, a, inverse=True)
            if not any(l in o and o[l].hausdorff_distance(g) < match for o in own.get(tn, [])):
                return False
        return True

    for k, a in channels.items():
        if k == t:
            continue
        for fp in b.GetFootprints():
            if fp.GetReference() in refs:
                continue
            for p in fp.Pads():
                add({l: _pad_poly(p, l) for l in ALL_CU if p.IsOnLayer(l)}, a)
        for tr in b.GetTracks():
            net = tr.GetNetname()
            if net in local and local[net][0] != k:
                continue
            # copper the template channel has a turned copy of (its own net's,
            # or the same shared net's) is there already
            if matched(_item_geoms(tr), a, local[net][1] if net in local else net):
                continue
            add(_item_geoms(tr), a)
    return {l: unary_union(gs) for l, gs in out.items() if gs}


def _dsn_poly(layer, poly):
    pts = list(poly.exterior.coords)[:-1]
    xy = '  '.join('%.1f %.1f' % (x * 1000, -y * 1000) for x, y in pts)
    return '    (keepout "" (polygon %s 0  %s))\n' % (layer, xy)


def _q(name):
    return '"%s"' % name if re.search(r'[\s()"]', name) else name


def edit_dsn(dsn, nets, keep, temp=None):
    """Ignore every net but `nets` (their classes are split: <class>_NR
    holds the rest), and add `keep` ({layer name: [polygon]}) as keepouts.
    temp: {temporary net: shared net}; each temporary net is routed with its
    shared net's class rules.  Returns the ignored classes' names."""
    txt = open(dsn).read()
    ignored = []
    temp = temp or {}
    bases = {}
    for tn, x in temp.items():
        bases.setdefault(x, []).append(tn)

    def cls(m):
        name, body, rest = m.group(1), m.group(2), m.group(3)
        toks = [x for x in re.findall(r'"[^"]*"|[^\s()]+', body) if x.strip('"') not in temp]
        toks += [_q(tn) for x in toks for tn in bases.get(x.strip('"'), [])]
        mine = [x for x in toks if x.strip('"') in nets]
        other = [x for x in toks if x.strip('"') not in nets]
        blocks = []
        if mine:
            blocks.append('(class %s %s\n      %s' % (name, ' '.join(mine), rest))
        if other:
            ignored.append(name + '_NR')
            blocks.append('(class %s_NR %s\n      %s' % (name, ' '.join(other), rest))
        return '\n    '.join(blocks)

    txt = re.sub(r'\(class (\S+)((?:\s+(?:"[^"]*"|[^\s()]+))*)\s*(\(circuit.*?\n    \))', cls, txt, flags=re.S)
    ins = ''.join(_dsn_poly(l, q) for l, qs in keep.items() for q in qs)
    if ins:
        j = txt.index('\n', txt.rindex('(keepout ')) + 1
        while txt[j:].startswith('      ') or txt[j:].startswith('        '):
            j = txt.index('\n', j) + 1
        txt = txt[:j] + ins + txt[j:]
    open(dsn, 'w').write(txt)
    return ignored


def _open_nets(path, nets, work):
    out = os.path.join(work, 'stamp_drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json', '-o', out, path],
                   capture_output=True)
    r = json.load(open(out))
    left = set()
    for u in r['unconnected_items']:
        for it in u['items']:
            m = re.search(r'\[([^\]]+)\]', it['description'])
            if m and m.group(1) in nets:
                left.add(m.group(1))
    return left, r


# Freerouting cost settings the template channel is routed with, all at
# once; the routing that leaves the fewest of its nets open is kept (the
# first of equals).  None: Freerouting's own defaults.  Freerouting is
# deterministic for a given input, and different costs give different
# routings (route.AUTOROUTE).
VARIANTS = [dict(via_costs=20, start_ripup_costs=100),
            dict(via_costs=25, start_ripup_costs=100),
            dict(via_costs=30, start_ripup_costs=100),
            None]


def _with_costs(dsn, out, costs):
    txt = open(dsn).read()
    if costs:
        sig = [m.group(1) for m in re.finditer(r'\(layer (\S+)\s+\(type signal\)', txt)]
        j = txt.index('\n    (boundary') + 1
        txt = txt[:j] + route._autoroute_block(costs, sig) + txt[j:]
    open(out, 'w').write(txt)


def local_shared(b, parts, channels, nets, planes=()):
    """A shared net with two or more pads on the template channel's parts
    (a chip's supply pin and its capacitors) is routed with the channel as
    far as those pads go: on the template board they (and the fixed copper
    on them) get a temporary net of their own, X~, which the copies turn
    back into X in every channel.  Plane nets are left out (their pads have
    plane vias).  Returns {X~: {channel: X}}."""
    t = template_channel(channels)
    pads = {}
    for ref in sorted(parts[t].values()):
        for p in b.FindFootprintByReference(ref).Pads():
            x = p.GetNetname()
            if x and x not in nets and x not in planes:
                pads.setdefault(x, []).append(p)
    out = {}
    for x, pl in sorted(pads.items()):
        if len(pl) < 2:
            continue
        ni = pcb.add_net(b, x + '~')
        mine = []
        for p in pl:
            p.SetNet(ni)
            mine.append({l: _pad_poly(p, l) for l in ALL_CU if p.IsOnLayer(l)})
        moved = True
        while moved:
            moved = False
            for tr in b.GetTracks():
                if tr.GetNetname() != x:
                    continue
                g = _item_geoms(tr)
                if any(l in m and g[l].intersects(m[l]) for m in mine for l in g):
                    tr.SetNet(ni); mine.append(g); moved = True
        out[x + '~'] = {k: x for k in channels}
    return out


def route_template(placed, work, parts, channels, passes=30, log=print, variants=None, planes=(), repair=None):
    """Route the template channel alone.  repair: a command, run as
    `repair + [board in, board out, job.json]` (job: the open nets and the
    nets it may move) on each of Freerouting's routings, all at once (the
    region and the obstacles are rule areas on the template board, so a
    router working on it keeps to them too).  Returns (routed board path,
    nets map, nets it left open, region)."""
    variants = VARIANTS if variants is None else variants
    os.makedirs(work, exist_ok=True)
    b = pcbnew.LoadBoard(placed)
    nets = counterparts(b, parts, channels)
    reg = region(b, parts, channels)
    log('stamp: %d nets per channel, region %.0f mm^2' % (len(nets), reg.area))
    obs = foreign(b, parts, channels, nets, reg)
    full = box(pcb.CX - pcb.HALF - 1, pcb.CY - pcb.HALF - 1, pcb.CX + pcb.HALF + 1, pcb.CY + pcb.HALF + 1)
    rel = lambda q: [(x - pcb.CX, y - pcb.CY) for x, y in list(q.exterior.coords)[:-1]]
    outside = _simple(full.difference(reg).simplify(0.02))
    for q in outside:
        pcb.rule_area(b, rel(q), ALL_CU, tracks=True, vias=True, pads=False, pours=False, name='stamp region')
    k = 0
    for l in ALL_CU:
        for q in _simple(obs[l].intersection(reg.buffer(0.3)).simplify(0.01)) if l in obs else []:
            pcb.rule_area(b, rel(q), [l], tracks=True, vias=True, pads=False, pours=False, name='stamp obstacle')
            k += 1
    # the fixed copper stays as it is, whatever routes round it
    for t in b.GetTracks():
        t.SetLocked(True)
    log('stamp: %d keepouts outside the region, %d over other channels\' copper' % (len(outside), k))
    keep = {}
    src = os.path.join(work, 'template.kicad_pcb')
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(placed)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(src)[0] + ext)
    temp = local_shared(b, parts, channels, nets, planes)
    b.Save(src)
    log('stamp: shared nets routed with the channel as far as its pads go: %s'
        % ', '.join(sorted(v[template_channel(channels)] for v in temp.values())))
    nets = dict(nets, **temp)
    temp_cls = {tn: m[template_channel(channels)] for tn, m in temp.items()}
    out, left = _route_stage(src, work, 'template', set(nets), keep, temp_cls, variants, passes, log, repair)
    log('stamp: template channel routed, %d of its nets open %s' % (len(left), sorted(left)))
    return out, nets, left, reg


def _route_stage(src, work, tag, targets, keep, temp_cls, variants, passes, log, repair=None):
    """One Freerouting stage on the template board: `targets` routed, with
    every cost variant at once, each routing then repaired (see
    route_template); the one leaving the fewest of them open is kept.
    Returns (board path, targets left open)."""
    from concurrent.futures import ThreadPoolExecutor
    dsn = os.path.join(work, tag + '.dsn')
    route.export_dsn(src, dsn)
    ignored = edit_dsn(dsn, targets, keep, temp_cls)

    def run(i):
        d = os.path.join(work, '%s%d.dsn' % (tag, i)); ses = os.path.join(work, '%s%d.ses' % (tag, i))
        _with_costs(dsn, d, variants[i])
        route.freeroute(d, ses, passes=passes, log=os.path.join(work, 'freerouting_%s%d.log' % (tag, i)),
                        extra=['-inc', ','.join(ignored)])
        return ses

    with ThreadPoolExecutor(max_workers=len(variants)) as ex:
        sessions = list(ex.map(run, range(len(variants))))
    res = []
    for i, ses in enumerate(sessions):
        out = os.path.join(work, '%s%d_routed.kicad_pcb' % (tag, i))
        route.import_ses(src, ses, out)
        for ext in ('.kicad_pro', '.kicad_dru'):
            s = os.path.splitext(src)[0] + ext
            if os.path.exists(s):
                shutil.copy(s, os.path.splitext(out)[0] + ext)
        left, _ = _open_nets(out, targets, work)
        log('stamp: %s, costs %s: %d of %d nets open %s' % (tag, variants[i] or 'default', len(left), len(targets),
                                                              sorted(left)))
        res.append((out, left))
    if repair:
        # the router's rip-up and re-route on every routing (how far it
        # gets does not follow from where it starts), each in a process of
        # its own, all at once
        procs = []
        for i, (out, left) in enumerate(res):
            if not left:
                continue
            rep = out.replace('_routed.kicad_pcb', '_repaired.kicad_pcb')
            job = os.path.splitext(rep)[0] + '.json'
            json.dump({'open': sorted(left), 'mine': sorted(targets)}, open(job, 'w'))
            logf = open(os.path.splitext(rep)[0] + '.log', 'w')
            procs.append((i, rep, logf, subprocess.Popen(list(repair) + [out, rep, job], stdout=logf,
                                                         stderr=subprocess.STDOUT)))
        for i, rep, logf, p in procs:
            p.wait()
            logf.close()
            if p.returncode != 0 or not os.path.exists(rep):
                log('stamp: repair of %s failed, see %s' % (os.path.basename(res[i][0]), logf.name))
                continue
            for ext in ('.kicad_pro', '.kicad_dru'):
                shutil.copy(os.path.splitext(src)[0] + ext, os.path.splitext(rep)[0] + ext)
            left, _ = _open_nets(rep, targets, work)
            log('stamp: %s repaired: %d open %s' % (os.path.basename(rep), len(left), sorted(left)))
            res[i] = (rep, left)
    return min(res, key=lambda r: len(r[1]))


def _key(t, net=None):
    net = net or t.GetNetname()
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        return ('v', net, round(mm(p.x), 3), round(mm(p.y), 3))
    s, e = t.GetStart(), t.GetEnd()
    a, c = (round(mm(s.x), 3), round(mm(s.y), 3)), (round(mm(e.x), 3), round(mm(e.y), 3))
    return ('t', net, t.GetLayer()) + tuple(sorted([a, c]))


def stamp(placed, routed, out, nets, channels, rules='', log=print, rounds=4):
    """Copy the routing of the template channel's nets from `routed` onto
    every channel of `placed`; save as `out`.  Copies in DRC violations
    are removed.  Returns the number of copies kept."""
    pb = pcbnew.LoadBoard(placed)
    tb = pcbnew.LoadBoard(routed)
    before = set(_key(t) for t in pb.GetTracks())
    tc = template_channel(channels)
    items = [t for t in tb.GetTracks()
             if t.GetNetname() in nets and _key(t, nets[t.GetNetname()][tc]) not in before]
    ids = set()
    for k, a in channels.items():
        for t in items:
            net = pcb.add_net(pb, nets[t.GetNetname()][k])
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                x, y = turn(a, mm(p.x) - pcb.CX, mm(p.y) - pcb.CY)
                n = pcbnew.PCB_VIA(pb)
                n.SetPosition(pcb.P(x, y)); n.SetWidth(t.GetWidth(pcbnew.F_Cu)); n.SetDrill(t.GetDrillValue())
                n.SetViaType(t.GetViaType())
                if t.GetViaType() != pcbnew.VIATYPE_THROUGH:
                    n.SetLayerPair(t.TopLayer(), t.BottomLayer())
            else:
                s, e = t.GetStart(), t.GetEnd()
                n = pcbnew.PCB_TRACK(pb)
                n.SetStart(pcb.P(*turn(a, mm(s.x) - pcb.CX, mm(s.y) - pcb.CY)))
                n.SetEnd(pcb.P(*turn(a, mm(e.x) - pcb.CX, mm(e.y) - pcb.CY)))
                n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer())
            n.SetNet(net)
            pb.Add(n)
            ids.add(n.m_Uuid.AsString())
    pb.Save(out)
    for ext in ('.kicad_pro',):
        s = os.path.splitext(placed)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(out)[0] + ext)
    pcb.write_rules(out, rules)
    total = len(ids)
    for r in range(rounds):
        e, w, u = pcb.drc(out, os.path.splitext(out)[0] + '_stamp_drc.json')
        bad = set(i['uuid'] for v in e for i in v['items']) & ids
        log('stamp: DRC round %d: %d errors, %d with a copy in them' % (r + 1, len(e), len(bad)))
        if not bad:
            break
        b = pcbnew.LoadBoard(out)
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in bad:
                b.Remove(t)
        ids -= bad
        b.Save(out)
    log('stamp: %d of %d copies kept (%d per channel routed)' % (len(ids), total, len(items)))
    return len(ids)
