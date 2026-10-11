"""Pre-charge supervisor (SPEC §4 stage 2, §5, §14.1).

The pre-charge P-FET connects VIN to the drone through RPRE.  RPRE is fed
from VIN *ahead of the shunt* (ARCHITECTURE §2), so the INA290 does not see
pre-charge current: the supervisor computes it, I = (VIN - VOUT) / RPRE.

PASS  : VOUT >= 75 % of VIN.
ABORT : STALL    VOUT rose less than STALL_MIN_RISE over the last STALL_WINDOW
                 while below 75 % and current still flows (a fault that only
                 appears at higher voltage, e.g. a 5 V part on battery voltage)
        TIMEOUT  still below 75 % after 1 s
        ENERGY   this attempt put more than ATTEMPT_BUDGET into RPRE
        BUDGET   this attempt plus the last minute's attempts exceed MINUTE_BUDGET
        HOT      RPRE thermistor over its limit
        COLLAPSE VIN fell away (bad pack, lead pulled)

Energy into RPRE = integral of (VIN - VOUT)^2 / RPRE dt.  In integer units:
mV * mV / mOhm = mW, and mW * ms = uJ.  (VIN - VOUT)^2 reaches 3.7e9 at 14S,
so the C version uses uint64 for the product.

Two resistor values, chosen from VIN (not from the cell-count guess, so a
mis-guessed pack still gets the right resistor): ~2 Ohm for packs up to 7S
LiHV (30.45 V), ~22 Ohm above.
"""
from dataclasses import dataclass, field
from enum import IntEnum

from .inputs import idiv

RPRE_LOW_MOHM = 2000
RPRE_HIGH_MOHM = 22000
RPRE_SWITCH_MV = 30450             # 7S LiHV full; above this, the 22 Ohm bank

PASS_PERMILLE = 750                # VOUT >= 75 % of VIN
TIMEOUT_MS = 1000
STALL_WINDOW_MS = 30
STALL_MIN_RISE_MV = 50             # or VIN/200, whichever is larger
STALL_MIN_CURRENT_MA = 20

# Per attempt: 5000 uF to 75 % of 60.9 V is ~8.7 J with no load, but a 15 W
# digital VTX switching on part-way up raises it to ~17 J (the resistor
# carries the VTX current too).  RPRE must be pulse-rated for 20 J.
ATTEMPT_BUDGET_UJ = 20_000_000
MINUTE_BUDGET_UJ = 45_000_000      # any 60 s
MINUTE_MS = 60_000
LEDGER_SLOTS = 16                  # last 16 attempts are enough to cover a minute
RPRE_HOT_DC = 1200                 # 120 degC on the resistor's NTC: refuse / abort
COLLAPSE_PERMILLE = 700            # VIN under 70 % of its value at start


class Status(IntEnum):
    RUNNING = 0
    PASS = 1
    ABORT = 2


class Reason(IntEnum):
    NONE = 0
    STALL = 1
    TIMEOUT = 2
    ENERGY = 3
    BUDGET = 4
    HOT = 5
    COLLAPSE = 6


def rpre_for(vin_mv):
    return RPRE_HIGH_MOHM if vin_mv > RPRE_SWITCH_MV else RPRE_LOW_MOHM


@dataclass
class EnergyLedger:
    """Energy of recent attempts, for the per-minute budget.  Fixed ring of
    (end time, uJ) in C."""
    entries: list = field(default_factory=list)   # [(t_ms, uj)]

    def used_uj(self, now_ms):
        return sum(e for t, e in self.entries if now_ms - t < MINUTE_MS)

    def add(self, now_ms, uj):
        self.entries.append((now_ms, uj))
        if len(self.entries) > LEDGER_SLOTS:
            self.entries.pop(0)

    def wait_ms(self, now_ms):
        """How long until a full attempt budget is available again."""
        need = self.used_uj(now_ms) + ATTEMPT_BUDGET_UJ - MINUTE_BUDGET_UJ
        if need <= 0:
            return 0
        freed = 0
        for t, e in sorted(self.entries):
            if now_ms - t >= MINUTE_MS:
                continue
            freed += e
            if freed >= need:
                return MINUTE_MS - (now_ms - t)
        return MINUTE_MS


class Supervisor:
    """One pre-charge attempt.  Create, call step() every tick, read status."""

    def __init__(self, t_ms, vin_mv, ledger, rpre_mohm=None):
        self.t0 = t_ms
        self.t_last = t_ms
        self.vin0 = vin_mv
        self.rpre = rpre_mohm if rpre_mohm is not None else rpre_for(vin_mv)
        self.ledger = ledger
        self.energy_uj = 0
        self.prior_uj = ledger.used_uj(t_ms)
        self.hist = []                 # (t_ms, vout_mv) for the stall window
        self.status = Status.RUNNING
        self.reason = Reason.NONE
        self.stop_vout_mv = 0
        self.stop_vin_mv = 0
        self.stop_ma = 0
        self.closed = False

    def current_ma(self, vin_mv, vout_mv):
        dv = vin_mv - vout_mv
        return idiv(dv * 1000, self.rpre) if dv > 0 else 0

    def can_start(self, ntc_rpre_dc):
        if ntc_rpre_dc >= RPRE_HOT_DC:
            return Reason.HOT
        if self.prior_uj + ATTEMPT_BUDGET_UJ > MINUTE_BUDGET_UJ and self.prior_uj > 0:
            return Reason.BUDGET
        return Reason.NONE

    def _stop(self, status, reason, vin_mv, vout_mv):
        self.status = status
        self.reason = reason
        self.stop_vin_mv = vin_mv
        self.stop_vout_mv = vout_mv
        self.stop_ma = self.current_ma(vin_mv, vout_mv)
        self.close()

    def close(self):
        """Book this attempt's energy into the minute ledger (once)."""
        if not self.closed:
            self.ledger.add(self.t_last, self.energy_uj)
            self.closed = True

    def step(self, t_ms, vin_mv, vout_mv, ntc_rpre_dc=250):
        if self.status != Status.RUNNING:
            return self.status
        dt = t_ms - self.t_last
        self.t_last = t_ms
        dv = vin_mv - vout_mv
        if dv > 0 and dt > 0:
            self.energy_uj += idiv(dv * dv, self.rpre) * dt
        elapsed = t_ms - self.t0
        self.hist.append((t_ms, vout_mv))
        while self.hist and t_ms - self.hist[0][0] > STALL_WINDOW_MS:
            self.hist.pop(0)

        if vout_mv * 1000 >= vin_mv * PASS_PERMILLE and vin_mv > 0:
            self._stop(Status.PASS, Reason.NONE, vin_mv, vout_mv)
        elif vin_mv * 1000 < self.vin0 * COLLAPSE_PERMILLE:
            self._stop(Status.ABORT, Reason.COLLAPSE, vin_mv, vout_mv)
        elif ntc_rpre_dc >= RPRE_HOT_DC:
            self._stop(Status.ABORT, Reason.HOT, vin_mv, vout_mv)
        elif self.energy_uj > ATTEMPT_BUDGET_UJ:
            self._stop(Status.ABORT, Reason.ENERGY, vin_mv, vout_mv)
        elif self.prior_uj + self.energy_uj > MINUTE_BUDGET_UJ:
            self._stop(Status.ABORT, Reason.BUDGET, vin_mv, vout_mv)
        elif elapsed >= STALL_WINDOW_MS and self._stalled(vin_mv, vout_mv):
            self._stop(Status.ABORT, Reason.STALL, vin_mv, vout_mv)
        elif elapsed >= TIMEOUT_MS:
            self._stop(Status.ABORT, Reason.TIMEOUT, vin_mv, vout_mv)
        return self.status

    def _stalled(self, vin_mv, vout_mv):
        t_old, v_old = self.hist[0]
        if self.hist[-1][0] - t_old < STALL_WINDOW_MS:
            return False
        rise_min = max(STALL_MIN_RISE_MV, idiv(vin_mv, 200))
        return (vout_mv - v_old < rise_min
                and self.current_ma(vin_mv, vout_mv) >= STALL_MIN_CURRENT_MA)
