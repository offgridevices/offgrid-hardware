"""Pack memory: the box remembers battery packs by a number it gives them.

No pack has an ID chip, so the box fingerprints what it can measure and the
owner confirms ("Pack 7?", + yes, - next).  The owner writes the number on
the pack with a marker the first time ("New pack 12").

Fingerprint
* Cell count: exact match required.
* Internal resistance, when both this plug-in and the stored pack have a
  reading: pack IR within +-IR_MATCH_PERMILLE (25 %) of the stored latest
  value, or within IR_MATCH_MIN_MOHM (the ~2-4 mOhm resolution of a 2 A
  step on the VIN ADC), and every per-cell IR within +-CELL_IR_MATCH_PERMILLE
  (30 %) or CELL_IR_MATCH_MIN_MOHM.  IR moves with temperature and charge
  state, so the window is wide; it separates a 5 mOhm pack from a 15 mOhm
  pack of the same cell count, which is what the owner cannot do by eye.
* Ranking: packs whose IR was compared come first, closest fingerprint
  (sum of the relative IR deviations, permille) first; packs that could not
  be compared follow; recency breaks ties (most recently seen first).
  At a plain plug-in nothing has drawn current yet, so IR is usually not
  available and the ranking is cell count + recency; the machine passes the
  IR of a run made before the question was answered (the box can wake with
  the guard open, see machine.py).

Per-cell IR (`cell_ir_mohm`) comes from the balance taps at two currents.
The taps are read against board GND and the pack's B- sits above GND by
I x (Q11 + the main lead's negative wire), a common offset that cancels in
every cell difference except cell 1's (tap 1 - GND).  Cell 1 is corrected
by CELL1_RETURN_MOHM (Q11 ~7 mOhm + ~3 mOhm of a typical lead and XT60); a
long or thin negative wire still reads cell 1 low by its excess.  Since a
pack is only ever compared with itself on the same box the pattern stays
self-consistent.

Prompt (`Prompt`, driven by the rocker levels btn_plus / btn_minus)
* Options: the ranked candidates, then "New pack N" (N = next_number).
  With no candidate the only option is "New pack N".
* + confirms the option shown; - shows the next one (after "new" it wraps
  to the first candidate).  Presses in the first PROMPT_DEAD_MS are ignored
  (the screen has not been read yet), a button already held when the prompt
  appears does not count, both halves at once are ignored.
* No input for PROMPT_TIMEOUT_MS: SKIP.  A skipped plug-in is recorded
  nowhere (better no data than another pack's data in a record).

Stored per pack: number, cells, first and last seen (RTC seconds, 0 = clock
not set: it is set over USB and lost when unpowered), first and last visit
sequence numbers (a 32-bit counter, always present; recency and the LRU use
it, with serial-number arithmetic so a wrap of the counter is harmless),
uses, IR at first sight and latest IR (pack and per cell, -1 = unknown),
worst cell (highest per-cell IR if it stands >= 2 mOhm above the best;
before any per-cell IR, the lowest cell at a plug-in more than 20 mV out of
balance), imbalance at the latest plug-in
and the worst seen.

Derived: `ir_change_pct` (latest vs first sight) and `wearing` (pack IR up
more than WEAR_PERMILLE = 40 % over first sight).

Full (SLOTS = 32): the least recently seen pack is replaced.  Pack numbers
are never reused: the counter only goes up ("Pack 33", never a second
"Pack 1").

C layout: a fixed array of 32 packed structs in a flash page (wear-levelled,
written at confirmation and at the end of a run that measured IR), the
candidate list a uint16 array of 33 entries.
"""
from dataclasses import dataclass, field
from enum import IntEnum

from .battery import DELTA_BALANCED_MV, IR_MIN_DI_MA
from .inputs import idiv, N_TAPS

SLOTS = 32
MAX_CELLS = 14
BAL_CELLS = N_TAPS                 # per-cell figures only exist for 2S-6S (balance sockets)
UNKNOWN = -1
TIME_NONE = 0                      # RTC not set (lost when unpowered, set over USB)
NEW = 0                            # option value meaning "new pack"
SEQ_MASK = 0xFFFFFFFF              # 32-bit visit counter
SEQ_HALF = 0x80000000

IR_MATCH_PERMILLE = 250
IR_MATCH_MIN_MOHM = 5
CELL_IR_MATCH_PERMILLE = 300
CELL_IR_MATCH_MIN_MOHM = 2
WEAR_PERMILLE = 400                # "wearing": pack IR up > 40 % over first sight
CELL1_RETURN_MOHM = 10             # Q11 (BSC070N10LS5, ~7 mOhm at 12 V gate) + ~3 mOhm negative lead
WORST_CELL_MIN_MOHM = 2            # a cell is "the weakest" only if it stands this far above the best

PROMPT_DELAY_MS = 2000             # pack in this long (balance lead in, battery screen read) before asking
PROMPT_DEAD_MS = 300               # presses this soon after the question appears are ignored
PROMPT_TIMEOUT_MS = 5000           # no input this long: skip


class Answer(IntEnum):
    PENDING = 0
    CONFIRMED = 1
    SKIPPED = 2


def _cells_list():
    return [UNKNOWN] * BAL_CELLS


@dataclass
class PackRecord:
    number: int
    cells: int
    first_time_s: int = TIME_NONE
    last_time_s: int = TIME_NONE
    first_seq: int = 0
    last_seq: int = 0
    uses: int = 0
    ir_first_mohm: int = UNKNOWN
    ir_first_cells: list = field(default_factory=_cells_list)
    ir_last_mohm: int = UNKNOWN
    ir_last_cells: list = field(default_factory=_cells_list)
    worst_cell: int = UNKNOWN          # index: highest per-cell IR (if it stands out), else the
                                       # lowest cell at a plug-in that was not balanced
    imbalance_mv: int = UNKNOWN        # max - min cell at the latest plug-in
    max_imbalance_mv: int = UNKNOWN    # worst plug-in imbalance seen


# ---------------------------------------------------------------- derived

def ir_known(p):
    return p.ir_first_mohm > 0 and p.ir_last_mohm >= 0


def ir_change_pct(p):
    """Latest pack IR vs first sight, percent (truncated).  0 when unknown
    (check ir_known)."""
    if not ir_known(p):
        return 0
    return idiv((p.ir_last_mohm - p.ir_first_mohm) * 100, p.ir_first_mohm)


def wearing(p):
    return ir_known(p) and (p.ir_last_mohm - p.ir_first_mohm) * 1000 > p.ir_first_mohm * WEAR_PERMILLE


def cell_ir_mohm(lo_cells_mv, lo_ma, hi_cells_mv, hi_ma):
    """Per-cell IR from the balance cells at two currents (see the module
    docstring for cell 1).  None if dI is too small or the reads differ."""
    di = hi_ma - lo_ma
    n = len(lo_cells_mv)
    if di < IR_MIN_DI_MA or n == 0 or n != len(hi_cells_mv) or n > BAL_CELLS:
        return None
    out = []
    for i in range(n):
        sag_uv = (lo_cells_mv[i] - hi_cells_mv[i]) * 1000
        half = di // 2 if sag_uv >= 0 else -(di // 2)
        r = idiv(sag_uv + half, di)                 # rounded: a 4 mOhm cell is 24 mV at 6 A
        if i == 0:
            r += CELL1_RETURN_MOHM
        out.append(r if r > 0 else 0)
    return out


def _within(meas, ref, permille, floor):
    d = abs(meas - ref)
    return d <= floor or d * 1000 <= ref * permille


def _dev_permille(meas, ref):
    return idiv(abs(meas - ref) * 1000, ref) if ref > 0 else 0


# ---------------------------------------------------------------- the table

class PackMemory:
    def __init__(self):
        self.packs = []
        self.seq = 0                   # last visit number handed out (uint32)
        self.next_number = 1

    # ---------------------------------------------------------- lookup
    def find(self, number):
        for p in self.packs:
            if p.number == number:
                return p
        return None

    def age(self, p):
        """Visits since this pack was last seen (0 = the latest).  Serial
        arithmetic: correct across a wrap of the 32-bit counter."""
        return (self.seq - p.last_seq) & SEQ_MASK

    def fingerprint(self, p, cells, ir_mohm=UNKNOWN, cell_ir=None):
        """(matches, compared, score).  compared: an IR comparison was made;
        score: sum of relative deviations, permille (lower = closer)."""
        if p.cells != cells:
            return False, False, 0
        compared = False
        score = 0
        if ir_mohm >= 0 and p.ir_last_mohm >= 0:
            compared = True
            if not _within(ir_mohm, p.ir_last_mohm, IR_MATCH_PERMILLE, IR_MATCH_MIN_MOHM):
                return False, True, 0
            score += _dev_permille(ir_mohm, p.ir_last_mohm)
        if cell_ir is not None and len(cell_ir) == cells and cells <= BAL_CELLS \
                and p.ir_last_cells[0] >= 0:
            compared = True
            total = 0
            for i in range(cells):
                ref = p.ir_last_cells[i]
                if not _within(cell_ir[i], ref, CELL_IR_MATCH_PERMILLE, CELL_IR_MATCH_MIN_MOHM):
                    return False, True, 0
                total += _dev_permille(cell_ir[i], ref)
            score += idiv(total, cells)
        return True, compared, score

    def candidates(self, cells, ir_mohm=UNKNOWN, cell_ir=None):
        """Stored packs that match, best first."""
        ranked = []
        for p in self.packs:
            ok, compared, score = self.fingerprint(p, cells, ir_mohm, cell_ir)
            if ok:
                ranked.append((0 if compared else 1, score, self.age(p), p))
        ranked.sort(key=lambda x: (x[0], x[1], x[2]))
        return [x[3] for x in ranked]

    # ---------------------------------------------------------- updates
    def confirm(self, number, cells, time_s=TIME_NONE, imbalance_mv=UNKNOWN, lo_idx=UNKNOWN):
        """The owner said yes.  number = NEW (0) for a new pack.  Records
        the plug-in and returns the record."""
        self.seq = (self.seq + 1) & SEQ_MASK
        p = self.find(number) if number != NEW else None
        if p is None:
            p = self._new(cells, time_s)
        p.last_seq = self.seq
        p.last_time_s = time_s          # TIME_NONE if the clock is not set: "last seen" unknown, seq still orders
        p.uses += 1
        if imbalance_mv >= 0:
            p.imbalance_mv = imbalance_mv
            if imbalance_mv > p.max_imbalance_mv:
                p.max_imbalance_mv = imbalance_mv
            if p.ir_last_cells[0] < 0 and lo_idx >= 0 and imbalance_mv > DELTA_BALANCED_MV:
                p.worst_cell = lo_idx   # no per-cell IR yet: the lowest cell, if it stands out
        return p

    def _new(self, cells, time_s):
        if len(self.packs) >= SLOTS:
            oldest = self.packs[0]
            for q in self.packs:
                if self.age(q) > self.age(oldest):
                    oldest = q
            self.packs.remove(oldest)
        p = PackRecord(self.next_number, cells, first_time_s=time_s, first_seq=self.seq)
        self.next_number += 1
        self.packs.append(p)
        return p

    def record_ir(self, p, ir_mohm, cell_ir=None):
        """A run measured IR on this pack.  The first reading ever is kept
        as "first sight"; every reading becomes the latest."""
        if ir_mohm >= 0:
            if p.ir_first_mohm < 0:
                p.ir_first_mohm = ir_mohm
            p.ir_last_mohm = ir_mohm
        if cell_ir is not None and len(cell_ir) == p.cells and p.cells <= BAL_CELLS:
            if p.ir_first_cells[0] < 0:
                p.ir_first_cells = list(cell_ir) + [UNKNOWN] * (BAL_CELLS - p.cells)
            p.ir_last_cells = list(cell_ir) + [UNKNOWN] * (BAL_CELLS - p.cells)
            worst = best = 0
            for i in range(p.cells):
                if cell_ir[i] > cell_ir[worst]:
                    worst = i
                if cell_ir[i] < cell_ir[best]:
                    best = i
            p.worst_cell = worst if cell_ir[worst] - cell_ir[best] >= WORST_CELL_MIN_MOHM else UNKNOWN

    def export(self):
        """USB export: plain rows, by number."""
        return [(p.number, p.cells, p.uses, p.first_time_s, p.last_time_s, p.last_seq,
                 p.ir_first_mohm, p.ir_last_mohm, ir_change_pct(p), wearing(p), p.worst_cell,
                 p.max_imbalance_mv) for p in sorted(self.packs, key=lambda q: q.number)]


# ---------------------------------------------------------------- the question

class Prompt:
    """"Pack 7?" on the battery screen.  Fed the debounced rocker levels
    once per tick.  Never touches a switch; the machine drops it (skip) the
    moment anything else needs the rocker or the screen."""

    def __init__(self, mem, cells, now_ms, plus=False, minus=False, ir_mohm=UNKNOWN, cell_ir=None):
        self.mem = mem
        self.cells = cells
        self.options = [p.number for p in mem.candidates(cells, ir_mohm, cell_ir)] + [NEW]
        self.idx = 0
        self.new_number = mem.next_number
        self.since_ms = now_ms
        self.input_ms = now_ms         # last press (or the start): the timeout runs from here
        self.answer = Answer.PENDING
        self.chosen = UNKNOWN
        self._plus = plus              # a button already held does not count as a press
        self._minus = minus

    @property
    def option(self):
        return self.options[self.idx]

    @property
    def is_new(self):
        return self.option == NEW

    def left_ms(self, now_ms):
        return PROMPT_TIMEOUT_MS - (now_ms - self.input_ms)

    def skip(self):
        if self.answer == Answer.PENDING:
            self.answer = Answer.SKIPPED

    def step(self, now_ms, plus, minus):
        if self.answer != Answer.PENDING:
            return self.answer
        plus_edge = plus and not self._plus
        minus_edge = minus and not self._minus
        self._plus, self._minus = plus, minus
        if now_ms - self.input_ms >= PROMPT_TIMEOUT_MS:
            self.answer = Answer.SKIPPED
            return self.answer
        if now_ms - self.since_ms < PROMPT_DEAD_MS or (plus and minus):
            return self.answer
        if plus_edge:
            self.chosen = self.option
            self.answer = Answer.CONFIRMED
        elif minus_edge:
            self.idx = (self.idx + 1) % len(self.options)
            self.input_ms = now_ms
        return self.answer
