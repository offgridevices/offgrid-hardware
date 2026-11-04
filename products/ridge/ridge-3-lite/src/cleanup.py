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
"""
import math, shutil
from collections import Counter
import pcbnew
import pcb


def _counts(e, w, u):
    return '%d errors %s, %d warnings %s, %d unconnected' % (
        len(e), dict(Counter(v['type'] for v in e)), len(w), dict(Counter(v['type'] for v in w)), len(u))


def _by_uuid(b, uid):
    return next((t for t in b.GetTracks() if t.m_Uuid.AsString() == uid), None)


def clean(path, extra_rules='', rounds=6, log=print):
    """Edits `path` in place.  Returns the final DRC (errors, warnings,
    unconnected)."""
    def drc():
        pcb.write_rules(path, extra_rules)
        return pcb.drc(path, path + '.clean.json')

    def trial(edit):
        """Apply edit(board) on a fresh load; keep it if DRC agrees."""
        shutil.copy(path, path + '.bak')
        b = pcbnew.LoadBoard(path)
        if not edit(b):
            return None
        b.Save(path)
        return drc()

    e, w, u = drc()
    log('clean-up start: ' + _counts(e, w, u))
    tried = set()
    for _ in range(rounds):
        progress = False
        for v in [v for v in w if v['type'] in ('via_dangling', 'track_dangling')]:
            uid = v['items'][0]['uuid']
            if uid in tried:
                continue
            tried.add(uid)
            b = pcbnew.LoadBoard(path)
            item = _by_uuid(b, uid)
            if item is None:
                continue
            groups = [[uid]]
            if item.GetClass() == 'PCB_VIA':
                p = item.GetPosition()
                groups.append([uid] + [t.m_Uuid.AsString() for t in b.GetTracks()
                                       if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == item.GetNetname()
                                       and (t.GetStart() == p or t.GetEnd() == p)])
            net, kind = item.GetNetname(), item.GetClass()
            for k, ids in enumerate(groups):
                def edit(b, ids=ids):
                    for t in [t for t in b.GetTracks() if t.m_Uuid.AsString() in ids]:
                        pcb.remove(b, t)
                    return True
                e2, w2, u2 = trial(edit)
                if len(u2) > len(u) or len(e2) > len(e):
                    shutil.copy(path + '.bak', path)
                    continue
                log('  removed %-14s %s%s' % (net, kind, '' if k == 0 else ' + %d stubs' % (len(ids) - 1)))
                e, w, u = e2, w2, u2
                progress = True
                break
        if not progress:
            break

    for v in [v for v in w if v['type'] == 'track_dangling']:
        uid = v['items'][0]['uuid']

        def edit(b, uid=uid):
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
        r = trial(edit)
        if r is None:
            continue
        e2, w2, u2 = r
        if len(u2) > len(u) or len(e2) > len(e) or len(w2) >= len(w):
            shutil.copy(path + '.bak', path)
        else:
            log('  trimmed %s' % v['items'][0]['description'][:40])
            e, w, u = e2, w2, u2

    # a dangling end that only touches same-net copper edge to edge (KiCad
    # counts that as connected but the end as free): join it to the
    # nearest same-net track end or via on its layer with a short segment
    for v in [v for v in w if v['type'] == 'track_dangling']:
        uid = v['items'][0]['uuid']

        def edit(b, uid=uid):
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
        r = trial(edit)
        if r is None:
            continue
        e2, w2, u2 = r
        if len(u2) > len(u) or len(e2) > len(e) or len(w2) >= len(w):
            shutil.copy(path + '.bak', path)
        else:
            log('  joined %s' % v['items'][0]['description'][:40])
            e, w, u = e2, w2, u2
    e, w, u = drc()
    log('clean-up end: ' + _counts(e, w, u))
    return e, w, u
