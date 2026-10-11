"""Battery checker (ARCHITECTURE §2.4, §3, §4).

Inputs: VIN from the main lead and the eight balance taps (XH pins 2..9,
measured against board GND).  Output: one `BatteryInfo` the screens read.

Balance lead decoding, from the tap pattern alone:

    [  0,   0, 3.8, 7.6, 11.4, 15.2,  0,  0 ]   4S, plug shifted by 2 pins
     ^^^^^^^^ black wire lands on a tap at 0 V (it is B-, which is board GND
              when the main lead is in), unconnected pins read 0 through
              their divider.

* leading taps at ~0 V: the plug is shifted (black wire not on pin 1).  With
  the main lead in, the black wire is at GND (via Q11) wherever it lands, so
  readings stay correct at idle.  With the balance lead alone a shifted plug
  gives the board no ground: it stays dark (safe), so the model never sees
  that case awake.
* a ~0 V tap with higher taps above it: a broken balance wire (that tap's
  divider pulls it down).
* the run ends where taps drop back to ~0 V: the pins above the plug.

Idle only: the taps are read against board GND.  The pack's B- reaches GND
through the reverse-battery FET Q11 in the battery return, and the balance
lead's black wire (XH pin 1) through 10 Ohm (R75, so the thin wire never
shares the main return).  With current flowing every tap therefore reads
high by I x (Q11 + lead) on top of each cell's own I x IR sag, so per-cell
numbers are only valid when `resting`; the machine keeps the last resting
analysis (`Machine.batt_idle`) for its decisions.

Limit: a cell sitting at ~0 V on tap 1 is indistinguishable from a one-pin
shift; it is reported as a shift (the pack is scrap either way, and the
sum/VIN check still flags a mismatch when the counts disagree).
"""
from dataclasses import dataclass, field
from enum import IntEnum

from .inputs import idiv, N_TAPS

VIN_PRESENT_MV = 2500          # below this there is no battery on the main lead
TAP_ZERO_MV = 300              # a tap below this is at GND / unconnected
CELL_PRESENT_MIN_MV = 100      # a step smaller than this is not a cell

# cell-count guess from VIN alone (resting cell window)
GUESS_CELL_MIN_MV = 3450
GUESS_CELL_MAX_MV = 4400
MAX_CELLS = 14

# verdicts (ARCHITECTURE §3)
DELTA_BALANCED_MV = 20
DELTA_DRIFTING_MV = 50
DEAD_CELL_MV = 2500
OVERDISCHARGED_MV = 3000
LIPO_MAX_MV = 4250
LIHV_MAX_MV = 4400
STORAGE_LO_MV = 3800
STORAGE_HI_MV = 3850
SUM_MISMATCH_PERMILLE = 20     # cells sum vs VIN, > 2 %
TOP_WIRE_MATCH_PERMILLE = 100  # one missing top cell within 10 % of the others: broken top wire
RESTING_MAX_MA = 100           # SoC from OCV only when (nearly) no current flows

# internal resistance (ΔV/ΔI)
IR_MIN_DI_MA = 2000
IR_WARN_MOHM_PER_CELL = 20     # healthy FPV packs: 2-10 mOhm/cell; 20+ sags visibly
SAG_WARN_MV_PER_CELL = 300

# resting OCV -> % tables (mV, %), ascending.  Piecewise linear.
OCV_LIPO = [(3270, 0), (3610, 5), (3690, 10), (3710, 15), (3730, 20), (3750, 25), (3770, 30),
            (3790, 35), (3800, 40), (3820, 45), (3840, 50), (3850, 55), (3870, 60), (3910, 65),
            (3950, 70), (3980, 75), (4020, 80), (4080, 85), (4110, 90), (4150, 95), (4200, 100)]
OCV_LIHV = [(3300, 0), (3620, 5), (3700, 10), (3720, 15), (3740, 20), (3760, 25), (3780, 30),
            (3800, 35), (3820, 40), (3840, 45), (3870, 50), (3900, 55), (3940, 60), (3980, 65),
            (4020, 70), (4070, 75), (4120, 80), (4180, 85), (4230, 90), (4280, 95), (4350, 100)]


class Delta(IntEnum):
    NONE = 0
    BALANCED = 1
    DRIFTING = 2
    OUT_OF_BALANCE = 3


class Chem(IntEnum):
    LIPO = 0               # every cell <= 4.25 V: treated as LiPo
    LIHV_OR_HIGH = 1       # a cell 4.25..4.40 V: LiHV, or an over-charged LiPo


class Storage(IntEnum):
    UNKNOWN = 0
    BELOW = 1
    AT = 2
    ABOVE = 3


class BalanceState(IntEnum):
    NONE = 0               # no balance lead
    OK = 1
    BROKEN_WIRE = 2        # a tap in the middle reads 0 V, or top wire(s) missing
    OTHER_PACK = 3         # cells do not add up to this pack


class Warn(IntEnum):
    """Battery warnings, most severe first (the screen shows the first)."""
    DEAD_CELL = 0
    OVERCHARGED = 1        # > 4.40 V: too high even for LiHV
    OVERDISCHARGED = 2
    OVERCHARGED_LIPO = 3   # 4.25..4.40 V: fine for LiHV only
    OTHER_PACK = 4
    BROKEN_WIRE = 5
    OUT_OF_BALANCE = 6
    HIGH_IR = 7


@dataclass
class CellCountGuess:
    cells: int = 0
    candidates: list = field(default_factory=list)
    ambiguous: bool = False        # more than one plausible count (LiHV n vs nearly-empty n+1)
    out_of_range: bool = False     # no count puts the cells in 3.45-4.40 V


@dataclass
class BalanceRead:
    present: bool = False
    shift: int = 0                 # pins the black wire sits above pin 1
    cells_mv: list = field(default_factory=list)
    broken_pin: int = 0            # XH pin number of a broken wire (0 = none)
    top_mv: int = 0


@dataclass
class BatteryInfo:
    vin_mv: int = 0
    main_present: bool = False
    cells: int = 0                 # best cell count
    cells_certain: bool = False    # confirmed by a matching balance lead
    guess: CellCountGuess = field(default_factory=CellCountGuess)
    bal: BalanceRead = field(default_factory=BalanceRead)
    balance: BalanceState = BalanceState.NONE
    balance_only: bool = False     # balance lead in, nothing on the main lead
    chem: Chem = Chem.LIPO
    soc_pct: int = -1
    resting: bool = True
    lo_idx: int = -1
    hi_idx: int = -1
    delta_mv: int = 0
    delta: Delta = Delta.NONE
    storage: Storage = Storage.UNKNOWN
    warnings: list = field(default_factory=list)     # [(Warn, cell_index or -1, mV)]
    sum_mv: int = 0


# ---------------------------------------------------------------- pieces

def guess_cells(vin_mv):
    g = CellCountGuess()
    if vin_mv < VIN_PRESENT_MV:
        return g
    for n in range(1, MAX_CELLS + 1):
        if GUESS_CELL_MIN_MV * n <= vin_mv <= GUESS_CELL_MAX_MV * n:
            g.candidates.append(n)
    if g.candidates:
        g.cells = g.candidates[0]          # fewest cells: "n LiHV" over "n+1 nearly empty"
        g.ambiguous = len(g.candidates) > 1
    else:
        g.cells = min(MAX_CELLS, max(1, idiv(vin_mv + GUESS_CELL_MAX_MV - 1, GUESS_CELL_MAX_MV)))
        g.out_of_range = True
    return g


def read_balance(taps_mv):
    b = BalanceRead()
    k = 0
    while k < N_TAPS and taps_mv[k] < TAP_ZERO_MV:
        k += 1
    if k == N_TAPS:
        return b
    b.present = True
    b.shift = k
    prev = 0
    cells = []
    i = k
    while i < N_TAPS:
        v = taps_mv[i]
        if v >= TAP_ZERO_MV and v - prev >= CELL_PRESENT_MIN_MV:
            cells.append(v - prev)
            prev = v
            i += 1
            continue
        # a dip to 0 V with live taps above it = broken wire at this pin
        above = [j for j in range(i + 1, N_TAPS) if taps_mv[j] - prev >= CELL_PRESENT_MIN_MV]
        if v < TAP_ZERO_MV and above:
            if b.broken_pin == 0:
                b.broken_pin = i + 2
            j = above[0]
            cells.append(taps_mv[j] - prev)       # two cells merged across the broken tap
            prev = taps_mv[j]
            i = j + 1
            continue
        break
    b.cells_mv = cells
    b.top_mv = prev
    return b


def soc_pct(cell_mv, table):
    if cell_mv <= table[0][0]:
        return 0
    if cell_mv >= table[-1][0]:
        return 100
    for (v0, p0), (v1, p1) in zip(table, table[1:]):
        if cell_mv <= v1:
            return p0 + idiv((cell_mv - v0) * (p1 - p0), v1 - v0)
    return 100


def delta_verdict(delta_mv):
    if delta_mv <= DELTA_BALANCED_MV:
        return Delta.BALANCED
    if delta_mv <= DELTA_DRIFTING_MV:
        return Delta.DRIFTING
    return Delta.OUT_OF_BALANCE


def ir_estimate(v_lo_i_mv, i_lo_ma, v_hi_i_mv, i_hi_ma, cells=1):
    """Pack internal resistance from two (V, I) points.  mV/mA = Ohm, x1000
    -> mOhm.  Returns (pack_mohm, sag_mv, warn) or None if dI is too small
    to trust (ADC noise and lead resistance would dominate)."""
    di = i_hi_ma - i_lo_ma
    if di < IR_MIN_DI_MA:
        return None
    sag = v_lo_i_mv - v_hi_i_mv
    if sag < 0:
        sag = 0
    r = idiv(sag * 1000, di)
    n = max(cells, 1)
    warn = r > IR_WARN_MOHM_PER_CELL * n or sag > SAG_WARN_MV_PER_CELL * n
    return r, sag, warn


# ---------------------------------------------------------------- the check

def analyse(vin_mv, taps_mv, current_ma=0):
    info = BatteryInfo(vin_mv=vin_mv)
    info.main_present = vin_mv >= VIN_PRESENT_MV
    info.guess = guess_cells(vin_mv)
    info.bal = read_balance(taps_mv)
    info.resting = current_ma <= RESTING_MAX_MA
    bal = info.bal
    cells_mv = bal.cells_mv

    if bal.present and not info.main_present:
        info.balance_only = True

    if bal.present:
        nb = len(cells_mv)
        info.sum_mv = bal.top_mv
        info.balance = BalanceState.BROKEN_WIRE if bal.broken_pin else BalanceState.OK
        if info.main_present and nb:
            avg = idiv(bal.top_mv, nb)
            n_main = max(1, idiv(vin_mv + idiv(avg, 2), avg))   # VIN / average cell, rounded
            mismatch = abs(vin_mv - bal.top_mv) * 1000 > vin_mv * SUM_MISMATCH_PERMILLE
            if n_main == nb and not mismatch:
                info.cells = nb
                info.cells_certain = not bal.broken_pin
            elif n_main > nb:
                missing = n_main - nb
                per = idiv(vin_mv - bal.top_mv, missing)
                if missing == 1 and abs(per - avg) * 1000 <= avg * TOP_WIRE_MATCH_PERMILLE:
                    info.balance = BalanceState.BROKEN_WIRE   # top wire(s) open
                    info.cells = n_main
                    if bal.broken_pin == 0:
                        bal.broken_pin = bal.shift + nb + 2   # first missing pin
                else:
                    info.balance = BalanceState.OTHER_PACK
                    info.cells = info.guess.cells
            else:
                info.balance = BalanceState.OTHER_PACK
                info.cells = info.guess.cells
        else:
            info.cells = nb
            info.cells_certain = not bal.broken_pin
    else:
        info.cells = info.guess.cells

    # per-cell findings (only when the balance cells belong to this pack)
    w = info.warnings
    usable = bal.present and info.balance != BalanceState.OTHER_PACK and cells_mv and not bal.broken_pin
    if usable:
        lo = min(range(len(cells_mv)), key=lambda i: cells_mv[i])
        hi = max(range(len(cells_mv)), key=lambda i: cells_mv[i])
        info.lo_idx, info.hi_idx = lo, hi
        info.delta_mv = cells_mv[hi] - cells_mv[lo]
        info.delta = delta_verdict(info.delta_mv)
        if cells_mv[hi] > LIPO_MAX_MV:
            info.chem = Chem.LIHV_OR_HIGH
        for i, v in enumerate(cells_mv):
            if v < DEAD_CELL_MV:
                w.append((Warn.DEAD_CELL, i, v))
            elif v < OVERDISCHARGED_MV:
                w.append((Warn.OVERDISCHARGED, i, v))
            elif v > LIHV_MAX_MV:
                w.append((Warn.OVERCHARGED, i, v))
            elif v > LIPO_MAX_MV:
                w.append((Warn.OVERCHARGED_LIPO, i, v))
        if info.delta == Delta.OUT_OF_BALANCE:
            w.append((Warn.OUT_OF_BALANCE, hi, info.delta_mv))
        avg = idiv(bal.top_mv, len(cells_mv))
        if STORAGE_LO_MV <= avg <= STORAGE_HI_MV:
            info.storage = Storage.AT
        elif avg > STORAGE_HI_MV:
            info.storage = Storage.ABOVE
        else:
            info.storage = Storage.BELOW
    elif info.main_present and info.cells:
        avg = idiv(vin_mv, info.cells)
        if avg > LIPO_MAX_MV:
            info.chem = Chem.LIHV_OR_HIGH
        if avg < OVERDISCHARGED_MV:
            w.append((Warn.OVERDISCHARGED, -1, avg))
    if info.balance == BalanceState.OTHER_PACK:
        w.append((Warn.OTHER_PACK, -1, bal.top_mv))
    elif info.balance == BalanceState.BROKEN_WIRE:
        w.append((Warn.BROKEN_WIRE, -1, bal.broken_pin))
    w.sort(key=lambda x: x[0])

    # state of charge from the resting average cell
    if info.cells:
        pack = vin_mv if info.main_present else bal.top_mv
        if pack >= VIN_PRESENT_MV or info.balance_only:
            avg = idiv(pack, info.cells)
            table = OCV_LIHV if info.chem == Chem.LIHV_OR_HIGH else OCV_LIPO
            info.soc_pct = soc_pct(avg, table)
    return info
