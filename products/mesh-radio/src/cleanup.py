# -*- coding: utf-8 -*-
"""Verified clean-up of a routed board: unused escape vias and stray stubs.

Every change is tried on its own and kept only if KiCad's DRC then shows
no more unconnected items and no more errors than before, so it can never
open a connection.

  1. each dangling via (KiCad: a via whose tracks are all on one layer):
     the via alone first (its tracks then meet where it stood), then the
     via with the stubs that end on it; each dangling track: the track
  2. each track end that overshoots a T-junction: pulled back to the
     junction (the nearest point on the segment where another track end,
     a via or a pad of the same net touches it); kept only if the warning
     count drops
  3. each track end that only touches same-net copper edge to edge: joined
     to the nearest same-net track end or via by a short segment; kept only
     if the warning count drops

Each edit runs in a child process (python3 cleanup.py BOARD OP UUID...):
KiCad 10's Python bindings never free a loaded board, and one load per
trial took the 2 Nov run past 16 GB.  Dangling items are tried in batches
first (all, then halves), one by one only where a batch makes things worse.
"""
import math, os, shutil, subprocess, sys
from collections import Counter
import pcbnew
import pcb


def _counts(e, w, u):
    return '%d errors %s, %d warnings %s, %d unconnected' % (
        len(e), dict(Counter(v['type'] for v in e)), len(w), dict(Counter(v['type'] for v in w)), len(u))


def _by_uuid(b, uid):
    return next((t for t in b.GetTracks() if t.m_Uuid.AsString() == uid), None)


def _remove(b, ids):
    gone = [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]
    for t in gone:
        pcb.remove(b, t)
    return bool(gone)


def _via_stubs(b, uid):
    v = _by_uuid(b, uid)
    if v is None or v.GetClass() != 'PCB_VIA':
        return False
    p = v.GetPosition()
    ids = {uid} | {t.m_Uuid.AsString() for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK'
                   and t.GetNetname() == v.GetNetname() and (t.GetStart() == p or t.GetEnd() == p)}
    return _remove(b, ids)


def _branch(b, uid):
    """A dangling track and the whole dead-end run of track behind it, up to
    the first point where it meets a pad, a via, a fill or a third track
    (3 Nov: a VSYS run on In4 cut back one piece per round, rounds ran out)."""
    t = _by_uuid(b, uid)
    if t is None or t.GetClass() != 'PCB_TRACK':
        return False
    net, lay = t.GetNetname(), t.GetLayer()
    segs = [o for o in b.GetTracks() if o.GetClass() == 'PCB_TRACK' and o.GetNetname() == net and o.GetLayer() == lay]
    vias = [o for o in b.GetTracks() if o.GetClass() == 'PCB_VIA' and o.GetNetname() == net]
    pads = [pd for fp in b.GetFootprints() for pd in fp.Pads() if pd.GetNetname() == net and pd.IsOnLayer(lay)]
    zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsOnLayer(lay)]
    near = lambda p, q, r: (p - q).EuclideanNorm() <= r

    def anchored(p, w):
        return (any(near(p, v.GetPosition(), v.GetWidth(lay) / 2 + w / 2) for v in vias)
                or any(pd.HitTest(p) for pd in pads)
                or any(z.HitTestFilledArea(lay, p) for z in zones))

    def others_at(p, skip):
        return [o for o in segs if o.m_Uuid.AsString() not in skip and (near(o.GetStart(), p, 1000) or near(o.GetEnd(), p, 1000))]

    # the dangling end: the one with nothing on it
    take = {uid}
    ends = [e for e in (t.GetStart(), t.GetEnd()) if not anchored(e, t.GetWidth()) and not others_at(e, take)]
    if not ends:
        return False
    cur, p = t, (t.GetEnd() if ends[0] == t.GetStart() else t.GetStart())
    for _ in range(500):
        if anchored(p, cur.GetWidth()):
            break
        nxt = others_at(p, take)
        if len(nxt) != 1:
            break
        cur = nxt[0]; take.add(cur.m_Uuid.AsString())
        p = cur.GetEnd() if near(cur.GetStart(), p, 1000) else cur.GetStart()
    return _remove(b, take)


def _trim(b, uid):
    """Pull a dangling end that overshoots a T-junction back to it."""
    t = _by_uuid(b, uid)
    if t is None:
        return False
    net, lay = t.GetNetname(), t.GetLayer()
    A, B = t.GetStart(), t.GetEnd()
    pts = []
    for o in b.GetTracks():
        if o.m_Uuid.AsString() == uid or o.GetNetname() != net:
            continue
        if o.GetClass() == 'PCB_VIA':
            pts.append(o.GetPosition())
        elif o.GetLayer() == lay:
            pts += [o.GetStart(), o.GetEnd()]
    for fp in b.GetFootprints():
        for pd in fp.Pads():
            if pd.GetNetname() == net and pd.IsOnLayer(lay):
                pts.append(pd.GetPosition())
    L2 = (B.x - A.x) ** 2 + (B.y - A.y) ** 2
    if L2 == 0:
        return False

    def on_seg(q):
        s = ((q.x - A.x) * (B.x - A.x) + (q.y - A.y) * (B.y - A.y)) / L2
        if not 0.0 <= s <= 1.0:
            return None
        px, py = A.x + s * (B.x - A.x), A.y + s * (B.y - A.y)
        return s if math.hypot(q.x - px, q.y - py) < t.GetWidth() / 2 else None

    def free(end):
        return not any(abs(q.x - end.x) < 2000 and abs(q.y - end.y) < 2000 for q in pts)
    ss = sorted(s for s in (on_seg(q) for q in pts) if s is not None)
    if not ss:
        return False
    if free(A):
        t.SetStart(pcbnew.VECTOR2I(int(A.x + ss[0] * (B.x - A.x)), int(A.y + ss[0] * (B.y - A.y))))
    elif free(B):
        t.SetEnd(pcbnew.VECTOR2I(int(A.x + ss[-1] * (B.x - A.x)), int(A.y + ss[-1] * (B.y - A.y))))
    else:
        return False
    return True


def _join(b, uid):
    """Join a dangling end that only touches same-net copper edge to edge
    to the nearest same-net track end or via on its layer."""
    t = _by_uuid(b, uid)
    if t is None:
        return False
    net, lay = t.GetNetname(), t.GetLayer()
    ends = []
    for o in b.GetTracks():
        if o.m_Uuid.AsString() == uid or o.GetNetname() != net:
            continue
        if o.GetClass() == 'PCB_VIA':
            ends.append(o.GetPosition())
        elif o.GetLayer() == lay:
            ends += [o.GetStart(), o.GetEnd()]
    best = None
    for end in (t.GetStart(), t.GetEnd()):
        if any(abs(q.x - end.x) < 2000 and abs(q.y - end.y) < 2000 for q in ends):
            continue                         # this end is joined
        for q in ends:
            d = math.hypot(q.x - end.x, q.y - end.y)
            if d <= 2 * t.GetWidth() and (best is None or d < best[0]):
                best = (d, end, q)
    if best is None:
        return False
    s = pcbnew.PCB_TRACK(b)
    s.SetStart(best[1]); s.SetEnd(best[2]); s.SetWidth(t.GetWidth()); s.SetLayer(lay); s.SetNet(t.GetNet())
    b.Add(s)
    return True


def _dedupe(path):
    """Take out every track piece that is an exact copy of another (same
    net, layer, width and ends, either way round).  A dangling stub laid
    twice is otherwise never removed: taking out either copy alone leaves
    the other dangling, so no warning goes away (3 Nov: two VSYS stubs)."""
    b = pcbnew.LoadBoard(path)
    seen, dup = set(), []
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_TRACK':
            continue
        a, e = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
        k = (t.GetNetname(), t.GetLayer(), t.GetWidth(), min(a, e), max(a, e))
        if k in seen:
            dup.append(t)
        seen.add(k)
    for t in dup:
        pcb.remove(b, t)
    if dup:
        b.Save(path)
    return len(dup)


OPS = {'remove': lambda b, ids: _remove(b, set(ids)), 'via_stubs': lambda b, ids: _via_stubs(b, ids[0]),
       'trim': lambda b, ids: _trim(b, ids[0]), 'branch': lambda b, ids: _branch(b, ids[0]), 'join': lambda b, ids: _join(b, ids[0])}


def clean(path, extra_rules='', rounds=6, log=print):
    """Edits `path` in place.  Returns the final DRC (errors, warnings,
    unconnected)."""
    def drc():
        pcb.write_rules(path, extra_rules)
        return pcb.drc(path, path + '.clean.json')

    def trial(op, ids):
        """Apply OPS[op] in a child process; the new DRC, or None if the
        edit did not apply (the board is then as it was)."""
        shutil.copy(path, path + '.bak')
        r = subprocess.run([sys.executable, os.path.abspath(__file__), path, op] + list(ids),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            shutil.copy(path + '.bak', path)
            return None
        return drc()

    n = _dedupe(path)
    if n:
        log('  %d duplicate track pieces taken out' % n)
    state = list(drc())
    log('clean-up start: ' + _counts(*state))

    def keep_if_no_worse(op, ids, need_fewer_warnings=False):
        r = trial(op, ids)
        if r is None:
            return False
        e2, w2, u2 = r
        e, w, u = state
        if len(u2) > len(u) or len(e2) > len(e) or (need_fewer_warnings and len(w2) >= len(w)):
            shutil.copy(path + '.bak', path)
            return False
        state[:] = [e2, w2, u2]
        return True

    def take_out(items):
        """items: [(uuid, net, kind)].  All at once, else halves, else one by
        one (a via with its stubs if alone fails).  Returns how many went."""
        if not items:
            return 0
        if keep_if_no_worse('remove', [i[0] for i in items]):
            for uid, net, kind in items:
                log('  removed %-14s %s' % (net, kind))
            return len(items)
        if len(items) == 1:
            uid, net, kind = items[0]
            if kind == 'PCB_VIA' and keep_if_no_worse('via_stubs', [uid]):
                log('  removed %-14s %s + stubs' % (net, kind))
                return 1
            return 0
        h = len(items) // 2
        return take_out(items[:h]) + take_out(items[h:])

    tried = set()
    for _ in range(rounds):
        items = []
        for v in state[1]:
            if v['type'] not in ('via_dangling', 'track_dangling'):
                continue
            it = v['items'][0]
            if it['uuid'] in tried:
                continue
            tried.add(it['uuid'])
            d = it['description']
            net = d.split('[')[1].split(']')[0] if '[' in d else '?'
            items.append((it['uuid'], net, 'PCB_VIA' if d.startswith('Via') else 'PCB_TRACK'))
        if not take_out(items):
            break

    for v in [v for v in state[1] if v['type'] == 'track_dangling']:
        if keep_if_no_worse('branch', [v['items'][0]['uuid']], need_fewer_warnings=True):
            log('  took out the dead-end run behind %s' % v['items'][0]['description'][:40])
    for v in [v for v in state[1] if v['type'] == 'track_dangling']:
        if keep_if_no_worse('trim', [v['items'][0]['uuid']], need_fewer_warnings=True):
            log('  trimmed %s' % v['items'][0]['description'][:40])
    for v in [v for v in state[1] if v['type'] == 'track_dangling']:
        if keep_if_no_worse('join', [v['items'][0]['uuid']], need_fewer_warnings=True):
            log('  joined %s' % v['items'][0]['description'][:40])
    e, w, u = drc()
    log('clean-up end: ' + _counts(e, w, u))
    return e, w, u


if __name__ == '__main__':
    # child process of clean(): BOARD OP UUID...; exit 0 if edited and saved
    path, op, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
    b = pcbnew.LoadBoard(path)
    if not OPS[op](b, ids):
        sys.exit(3)
    b.Save(path)
