"""3 V probe classifier (SPEC §4 stage 1, ARCHITECTURE §4).

Sequence run by the machine (main switch and pre-charge OFF the whole time):

    phase HIGH : 3.0 V source through 1 kOhm for PROBE_T_HIGH_MS
    phase LOW  : 3.0 V source through 100 Ohm for PROBE_T_LOW_MS
    phase HIGH2: back to 1 kOhm for PROBE_T_HIGH2_MS

The last phase exists for reversed leads on a drone with a big capacitor:
on 1 kOhm alone the capacitor is still charging toward the diode clamp when
the first phase ends, so the two-current comparison is made between the
settled 100 Ohm reading and the settled 1 kOhm reading *after* 100 Ohm has
charged the capacitor up to the clamp.

VOUT_low is sampled every PROBE_SAMPLE_MS (ADC on a 1 kHz timer trigger,
oversampled x16 in hardware).  `classify()` gets the three sample arrays and
returns one verdict.  Pure integer arithmetic; every threshold is a constant.

How each verdict is told apart:

* OPEN      the very first 1 kOhm sample is already near the source: there is
            less than ~0.7 uF on the lead, i.e. nothing (or only a meter) attached.
* SHORT     the node settles; the load resistance computed from the 100 Ohm
            reading, R = Rs * V / (Vs - V), is under 1 Ohm.
* HALF_SHORT  same, 1..150 Ohm (1S: only under 10 Ohm, because a 1S flight
            controller already runs at 3 V and draws ~30-40 mA, looking like ~75 Ohm).
* REVERSED  the node settles at 0.9-1.6 V on 100 Ohm and barely moves when
            the source goes back to 1 kOhm (ratio < 1.35): two body diodes in
            series.  A
            resistor's reading scales by 4x or more between the two sources.
* OK        the node is still charging at the end (a capacitor), or settles
            above 150 Ohm.  Capacitance comes from the initial rise: C = I*t/dV.

A big capacitor in parallel with a half-short never settles inside the window,
so a still-rising LOW phase is extrapolated to its asymptote (three equally
spaced points, Aitken's delta-squared) before deciding it is "just a capacitor".
"""
from dataclasses import dataclass
from enum import IntEnum

from .inputs import idiv

PROBE_SRC_MV = 3000
PROBE_R_HIGH_OHM = 1000
PROBE_R_LOW_OHM = 100
PROBE_SAMPLE_MS = 1
PROBE_T_HIGH_MS = 50
PROBE_T_LOW_MS = 250
PROBE_T_HIGH2_MS = 50
PROBE_T_FIRST2_MS = PROBE_T_HIGH_MS + PROBE_T_LOW_MS     # end of the 100 Ohm phase
PROBE_TOTAL_MS = PROBE_T_FIRST2_MS + PROBE_T_HIGH2_MS

OPEN_FIRST_SAMPLE_MV = 2500        # 1 ms into 1 kOhm: > 2.5 V means C < ~0.7 uF
SETTLE_WINDOW_SAMPLES = 10         # "settled" = moved less than SETTLE_MAX_MV in 10 ms
SETTLE_MAX_MV = 15
AVG_SAMPLES = 5                    # final value = mean of the last 5 samples

SHORT_MAX_MOHM = 1000              # < 1 Ohm: dead short
HALF_SHORT_MAX_MOHM = 150000       # 1..150 Ohm: half-short
HALF_SHORT_1S_MAX_MOHM = 10000     # 1S: only < 10 Ohm counts (FC runs at 3 V)

DIODE_MIN_MV = 900                 # clamp window on the 100 Ohm source
DIODE_MAX_MV = 1600
DIODE_HIGH_MIN_MV = 700            # and it must still clamp back on 1 kOhm
DIODE_MAX_RATIO_PERMILLE = 1350    # V(100 Ohm) / V(1 kOhm, 2nd) below 1.35: a diode, not a resistor

CAP_FIT_RISE_MV = 400              # rise used for C = I*t/dV
EXTRAP_SPACING_SAMPLES = 80        # Aitken points: end-160, end-80, end
EXTRAP_LINEAR_PERMILLE = 950       # 2nd step >= 95 % of 1st: still a straight ramp, no asymptote
NO_LOAD_PERMILLE = 950             # asymptote above 95 % of source: no resistive load to speak of

NO_BIG_CAP_UF = 100                # SPEC §4: "No big capacitor found" on 4S+
NO_BIG_CAP_MIN_CELLS = 4


class Verdict(IntEnum):
    OK = 0
    OPEN = 1
    SHORT = 2
    HALF_SHORT = 3
    REVERSED = 4


@dataclass
class ProbeResult:
    verdict: Verdict
    load_mohm: int = -1            # resistive load seen (-1 = none / capacitor only)
    cap_uf: int = 0                # capacitance estimate (0 = none found)
    v_high_mv: int = 0             # final reading on 1 kOhm (the second 1 kOhm phase if run)
    v_low_mv: int = 0              # settled / final reading on 100 Ohm


def _mean_tail(s, n=AVG_SAMPLES):
    n = min(n, len(s))
    return idiv(sum(s[-n:]), n)


def _settled(s):
    if len(s) <= SETTLE_WINDOW_SAMPLES:
        return False
    return abs(s[-1] - s[-1 - SETTLE_WINDOW_SAMPLES]) <= SETTLE_MAX_MV


def load_mohm(v_mv, rs_ohm, vs_mv=PROBE_SRC_MV):
    """Divider inversion: R = Rs * V / (Vs - V).  -1 if V >= Vs (no load)."""
    if v_mv >= vs_mv:
        return -1
    if v_mv <= 0:
        return 0
    return idiv(rs_ohm * 1000 * v_mv, vs_mv - v_mv)


def extrapolate_mv(s):
    """Asymptote of a still-settling first-order rise, from three equally
    spaced points (Aitken delta-squared).  None if the rise is still a
    straight ramp (pure capacitor, no resistive load).  int64 in C."""
    k = EXTRAP_SPACING_SAMPLES
    if len(s) < 2 * k + 1:
        return None
    v1, v2, v3 = s[-1 - 2 * k], s[-1 - k], s[-1]
    d1, d2 = v2 - v1, v3 - v2
    if d1 <= 0:
        return v3
    if d2 * 1000 >= d1 * EXTRAP_LINEAR_PERMILLE:
        return None
    return idiv(v1 * v3 - v2 * v2, v1 + v3 - 2 * v2)


def capacitance_uf(high, low, vs_mv=PROBE_SRC_MV):
    """C = I * t / dV over the first CAP_FIT_RISE_MV of rise, using the
    average source current over that rise.  I in uA, t in ms, dV in mV -> uF.
    Uses the 1 kOhm phase if it rose far enough (small caps), else the start
    of the 100 Ohm phase (big caps)."""
    for k, v in enumerate(high):
        if v >= CAP_FIT_RISE_MV:
            t_ms = (k + 1) * PROBE_SAMPLE_MS
            i_ua = idiv((vs_mv - idiv(v, 2)) * 1000, PROBE_R_HIGH_OHM)
            return idiv(i_ua * t_ms, v)
    v0 = high[-1] if high else 0
    k_end = len(low) - 1
    for k, v in enumerate(low):
        if v - v0 >= CAP_FIT_RISE_MV:
            k_end = k
            break
    if k_end < 0:
        return 0
    dv = low[k_end] - v0
    if dv <= 0:
        return 0
    t_ms = (k_end + 1) * PROBE_SAMPLE_MS
    i_ua = idiv((vs_mv - v0 - idiv(dv, 2)) * 1000, PROBE_R_LOW_OHM)
    return idiv(i_ua * t_ms, dv)


def classify(high, low, high2=None, cells=0):
    """high, low, high2: VOUT_low samples in mV, one per PROBE_SAMPLE_MS, for
    the 1 kOhm, 100 Ohm and second 1 kOhm phases (high2 may be omitted: the
    first 1 kOhm phase is then used for the diode test).  cells: best
    cell-count guess (1 enables the 1S rule; 0 = unknown = multi-cell)."""
    if not high or not low:
        return ProbeResult(Verdict.OPEN)
    h2 = high2 if high2 else high
    v_hi = _mean_tail(h2)
    v_lo = _mean_tail(low)

    if high[0] >= OPEN_FIRST_SAMPLE_MV and v_lo * 1000 >= PROBE_SRC_MV * NO_LOAD_PERMILLE:
        return ProbeResult(Verdict.OPEN, -1, 0, v_hi, v_lo)

    cap = capacitance_uf(high, low)

    if _settled(low):
        v_inf = v_lo
    else:
        v_inf = extrapolate_mv(low)
        if v_inf is None or v_inf * 1000 >= PROBE_SRC_MV * NO_LOAD_PERMILLE:
            return ProbeResult(Verdict.OK, -1, cap, v_hi, v_lo)

    if (_settled(h2) and _settled(low) and DIODE_MIN_MV <= v_lo <= DIODE_MAX_MV
            and v_hi >= DIODE_HIGH_MIN_MV and v_lo * 1000 <= v_hi * DIODE_MAX_RATIO_PERMILLE):
        return ProbeResult(Verdict.REVERSED, -1, 0, v_hi, v_lo)

    r = load_mohm(v_inf, PROBE_R_LOW_OHM)
    if r < 0:
        return ProbeResult(Verdict.OK, -1, cap, v_hi, v_lo)
    if r < SHORT_MAX_MOHM:
        return ProbeResult(Verdict.SHORT, r, 0, v_hi, v_lo)
    half_max = HALF_SHORT_1S_MAX_MOHM if cells == 1 else HALF_SHORT_MAX_MOHM
    if r < half_max:
        return ProbeResult(Verdict.HALF_SHORT, r, cap, v_hi, v_lo)
    return ProbeResult(Verdict.OK, r, cap, v_hi, v_lo)


def no_big_cap(cap_uf, cells):
    """SPEC §4: pass with a warning when a 4S+ drone shows < 100 uF."""
    return cells >= NO_BIG_CAP_MIN_CELLS and cap_uf < NO_BIG_CAP_UF
