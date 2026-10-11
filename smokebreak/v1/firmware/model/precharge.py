"""Pre-charge supervisor (SPEC §4 stage 2, §5, §14.1; sim/SIM.md case 1).

The pre-charge P-FET Q3 connects VIN to the drone through the Schottky D3
and RPRE.  RPRE is ONE bank for 1S-14S: R_PRE + R_PRE2, 2 x 15 Ohm 5 W
(Vishay AC05) in parallel = 7.5 Ohm (src/circuit.py §4; SIM.md case 1(a):
6.8-8.2 Ohm gets every 8S-14S drone with a 15 W VTX past 75 % in < 1 s,
10 Ohm and up stall at 8S).  There is no bank switch any more.

The current shunt is low side, in the drone's return, so the INA181A2 does
see pre-charge current; the supervisor still computes it from the resistor
drop, I = (VIN - VOUT) / RPRE, so it does not depend on the amplifier's
zero or range.  (D3's ~0.5 V makes that a slight over-estimate: safe.)

Closing the main switch.  The BSC040N10NS5's linear-mode SOA is tiny (SIM.md
finding 4: 0.53 A for 10 ms at 25 V), so the main switch closes only after
the pre-charge has SETTLED (VOUT rose less than 1 % of VIN over the last
20 ms) AND the gap still across it, VIN - VOUT, is at most 12 V (SIM.md
"Design values chosen", main-switch close rule; case 1(b)).  "Settled" is a
net rise, not a peak-to-peak band, so a drone whose regulator hiccups at its
UVLO (a 1S whoop on 7.5 Ohm) still counts as settled; the gap is then taken
from the LOWEST VOUT in the window, the worst case the switch could close
across.  So:

PASS  : settled, VIN - VOUT <= CLOSE_GAP_MAX_MV.  This includes low-voltage
        drones whose VTX sits at its 6 V UVLO with a small gap (SIM.md case
        1(b): 2S-5S with a 10 W VTX stall at ~6 V and close within SOA).
ABORT : STALL    settled with more than 12 V still across RPRE: the drone
                 draws power at that voltage (a VTX stuck at its UVLO, a 5 V
                 part on battery voltage).  Refused; the main switch never
                 closes.  SIM.md case 1(b): 6S at 3.5 V/cell + 10 W VTX ends
                 at a 14.9 V gap -> refused.
        TIMEOUT  not settled after 1 s
        ENERGY   this attempt put more than ATTEMPT_BUDGET (12 J) into RPRE
        BUDGET   this attempt plus the last minute's attempts exceed MINUTE_BUDGET
        HOT      RPRE thermistor over its limit
        COLLAPSE VIN fell away (bad pack, lead pulled)

Energy into RPRE = integral of (VIN - VOUT)^2 / RPRE dt.  In integer units:
mV * mV / mOhm = mW, and mW * ms = uJ.  (VIN - VOUT)^2 reaches 3.7e9 at 14S,
so the C version uses uint64 for the product.
"""
from dataclasses import dataclass, field
from enum import IntEnum

from .inputs import idiv

RPRE_MOHM = 7500                   # 2 x 15 Ohm 5 W AC05 in parallel (circuit.py R_PRE, R_PRE2)

CLOSE_GAP_MAX_MV = 12000           # SIM.md case 1(b): close the main switch across <= 12 V only
SETTLE_WINDOW_MS = 20              # SIM.md case 1(b): "VOUT within 1 % for 20 ms"
SETTLE_PERMILLE = 10               # 1 % of VIN ...
SETTLE_MIN_MV = 50                 # ... but never finer than 50 mV (1S, ADC noise)
TIMEOUT_MS = 1000

# Per attempt: SIM.md case 1(c): the worst normal attempt (14S LiHV, 5000 uF,
# 15 W VTX) puts ~10.6 J into RPRE, half in each resistor.  The abort budget
# is 12 J (6 J per resistor, ~55 % of the AC05's single-pulse rating; SIM.md
# "Design values chosen", RPRE energy).  Per minute: unchanged.
ATTEMPT_BUDGET_UJ = 12_000_000
MINUTE_BUDGET_UJ = 45_000_000      # any 60 s
MINUTE_MS = 60_000
LEDGER_SLOTS = 16                  # last 16 attempts are enough to cover a minute
RPRE_HOT_DC = 1200                 # 120 degC on the resistor's NTC (RT2): refuse / abort
COLLAPSE_PERMILLE = 700            # VIN under 70 % of its value at start


class Status(IntEnum):
    RUNNING = 0
    PASS = 1
    ABORT = 2


class Reason(IntEnum):
    NONE = 0
    STALL = 1                      # settled with gap > CLOSE_GAP_MAX_MV: refused
    TIMEOUT = 2
    ENERGY = 3
    BUDGET = 4
    HOT = 5
    COLLAPSE = 6


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
    """One pre-charge attempt.  Create, call step() every tick, read status.
    `rpre_mohm` exists for unit tests only; the board has one value."""

    def __init__(self, t_ms, vin_mv, ledger, rpre_mohm=RPRE_MOHM):
        self.t0 = t_ms
        self.t_last = t_ms
        self.vin0 = vin_mv
        self.rpre = rpre_mohm
        self.ledger = ledger
        self.energy_uj = 0
        self.prior_uj = ledger.used_uj(t_ms)
        self.hist = []                 # (t_ms, vout_mv) for the settle window
        self.status = Status.RUNNING
        self.reason = Reason.NONE
        self.stop_vout_mv = 0
        self.stop_vin_mv = 0
        self.stop_ma = 0
        self.closed = False

    def current_ma(self, vin_mv, vout_mv):
        dv = vin_mv - vout_mv
        return idiv(dv * 1000, self.rpre) if dv > 0 else 0

    @property
    def gap_mv(self):
        """VIN - VOUT when the attempt stopped (what the main switch would close across)."""
        return self.stop_vin_mv - self.stop_vout_mv

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
        while self.hist and t_ms - self.hist[0][0] > SETTLE_WINDOW_MS:
            self.hist.pop(0)

        if vin_mv * 1000 < self.vin0 * COLLAPSE_PERMILLE:
            self._stop(Status.ABORT, Reason.COLLAPSE, vin_mv, vout_mv)
        elif ntc_rpre_dc >= RPRE_HOT_DC:
            self._stop(Status.ABORT, Reason.HOT, vin_mv, vout_mv)
        elif self.energy_uj > ATTEMPT_BUDGET_UJ:
            self._stop(Status.ABORT, Reason.ENERGY, vin_mv, vout_mv)
        elif self.prior_uj + self.energy_uj > MINUTE_BUDGET_UJ:
            self._stop(Status.ABORT, Reason.BUDGET, vin_mv, vout_mv)
        elif self._settled(vin_mv, vout_mv):
            v_low = min(v for _, v in self.hist)        # worst case across the window
            if vin_mv - v_low <= CLOSE_GAP_MAX_MV:
                self._stop(Status.PASS, Reason.NONE, vin_mv, v_low)
            else:
                self._stop(Status.ABORT, Reason.STALL, vin_mv, v_low)
        elif elapsed >= TIMEOUT_MS:
            self._stop(Status.ABORT, Reason.TIMEOUT, vin_mv, vout_mv)
        return self.status

    def _settled(self, vin_mv, vout_mv):
        """VOUT rose less than max(1 % of VIN, 50 mV) over a full window."""
        t_old, v_old = self.hist[0]
        if self.hist[-1][0] - t_old < SETTLE_WINDOW_MS:
            return False
        return vout_mv - v_old < max(SETTLE_MIN_MV, idiv(vin_mv * SETTLE_PERMILLE, 1000))
