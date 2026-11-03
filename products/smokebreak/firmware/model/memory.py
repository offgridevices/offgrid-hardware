"""Drone memory (SPEC §7): 32 profiles keyed by cell count + capacitance.

* Match: same cell count, capacitance within +-15 % of the stored value
  (closest wins).
* Capacitor-loss match: a drone whose bulk capacitor broke off reads far
  below 85 % of its stored value and would never match.  So if nothing
  matches, the *most recently seen* profile with the same cell count is
  taken to be the same drone when its capacitance fell by more than 30 %:
  that is the realistic case (crash, plug the same drone straight back in)
  and it is the only way the "capacitance down" warning can ever fire.
* Warnings, against the stored (last visit's) values:
      idle current up > 30 % AND > 0.1 A
      capacitance down > 30 %
* Every visit then overwrites the stored values ("than last time"), so a
  warning shows once per change, not forever.
* Full: the least recently seen profile is replaced.  Drone numbers are never
  reused ("Drone 7, new").

C layout: a fixed array of 32 packed structs in a flash page (wear-levelled),
`seq` is a 32-bit visit counter standing in for "date of last visit".
"""
from dataclasses import dataclass, field

from .inputs import idiv

SLOTS = 32
MATCH_PERMILLE = 150
IDLE_UP_PERMILLE = 300
IDLE_UP_MIN_MA = 100
CAP_DOWN_PERMILLE = 300
IDLE_RECORD_MS = 10000          # idle current is taken 10 s after the drone goes live

W_IDLE_UP = 'idle_up'
W_CAP_DOWN = 'cap_down'


@dataclass
class Profile:
    number: int
    cells: int
    cap_uf: int
    idle_ma: int = -1           # -1 until a 10 s idle reading exists
    seq: int = 0                # last visit (higher = more recent)
    visits: int = 1


@dataclass
class Visit:
    profile: Profile
    new: bool
    warnings: list = field(default_factory=list)    # [(kind, old, new)]
    ref_cap_uf: int = 0         # stored values this visit is compared with
    ref_idle_ma: int = -1


class DroneMemory:
    def __init__(self):
        self.profiles = []
        self.seq = 0
        self.next_number = 1

    def _cap_match(self, p, cap_uf):
        return abs(cap_uf - p.cap_uf) * 1000 <= p.cap_uf * MATCH_PERMILLE

    def find(self, cells, cap_uf):
        best = None
        for p in self.profiles:
            if p.cells == cells and self._cap_match(p, cap_uf):
                if best is None or abs(cap_uf - p.cap_uf) < abs(cap_uf - best.cap_uf):
                    best = p
        return best

    def _last_seen(self, cells):
        same = [p for p in self.profiles if p.cells == cells]
        return max(same, key=lambda p: p.seq) if same else None

    def visit(self, cells, cap_uf):
        """Called when the probe passes.  Returns a Visit with any
        capacitance warning; idle is added later by record_idle()."""
        self.seq += 1
        p = self.find(cells, cap_uf)
        warnings = []
        if p is None:
            last = self._last_seen(cells)
            if last is not None and last.seq == self.seq - 1 and \
                    (last.cap_uf - cap_uf) * 1000 > last.cap_uf * CAP_DOWN_PERMILLE:
                p = last
        if p is None:
            p = self._new(cells, cap_uf)
            return Visit(p, True)
        v = Visit(p, False, warnings, p.cap_uf, p.idle_ma)
        if (p.cap_uf - cap_uf) * 1000 > p.cap_uf * CAP_DOWN_PERMILLE:
            warnings.append((W_CAP_DOWN, p.cap_uf, cap_uf))
        p.cap_uf = cap_uf
        p.seq = self.seq
        p.visits += 1
        return v

    def _new(self, cells, cap_uf):
        if len(self.profiles) >= SLOTS:
            oldest = min(self.profiles, key=lambda q: q.seq)
            self.profiles.remove(oldest)
        p = Profile(self.next_number, cells, cap_uf, -1, self.seq)
        self.next_number += 1
        self.profiles.append(p)
        return p

    def record_idle(self, visit, idle_ma):
        """10 s after live.  Adds an idle warning to the visit if needed and
        stores the new idle current.  Returns True if a warning was added."""
        old = visit.ref_idle_ma
        added = False
        if old >= 0 and idle_ma - old > IDLE_UP_MIN_MA and (idle_ma - old) * 1000 > old * IDLE_UP_PERMILLE:
            visit.warnings.append((W_IDLE_UP, old, idle_ma))
            added = True
        visit.profile.idle_ma = idle_ma
        return added

    def export(self):
        """USB export: plain rows."""
        return [(p.number, p.cells, p.cap_uf, p.idle_ma, p.seq) for p in
                sorted(self.profiles, key=lambda q: q.number)]


def pct_change(old, new):
    return idiv((new - old) * 100, old) if old else 0
