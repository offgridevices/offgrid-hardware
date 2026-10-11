"""Two-tier current limit and the Limit rocker (SPEC §4 stage 3, §6, §7).

Tier 1, firmware: the INA290 is sampled at 10 kHz; the ISR sums samples into
10 ms buckets; the 200 ms average is the sum of the last 20 buckets.  Trip
when the average exceeds the active setting.

Tier 2, hardware: a comparator on the INA290 output pulls INP low in <= 5 us
above a threshold the MCU programs through PWM + RC.  The model computes the
threshold (4 x the active setting, clamped to the amplifier's 40 A range).

Tier 3, the TPS48111's own fixed short trip, needs nothing from firmware.

Rocker: AUTO < 1 < 2 < 5 < 10 < 25 A.  Stepping + from 10 A asks "Props
off?" (S11); a second + between CONFIRM_MIN_MS and CONFIRM_WINDOW_MS after
the prompt arms 25 A for MOTOR_TEST_MS, then the previous setting returns.
A + inside the first CONFIRM_MIN_MS cancels the prompt instead, so mashing +
(or contact bounce) can never confirm the motor test: the user has to stop,
read "Props off?" and press once more.
"""
from dataclasses import dataclass, field

from .inputs import idiv, clamp

AUTO = 0
SETTINGS_MA = [0, 1000, 2000, 5000, 10000, 25000]   # index 0 = AUTO
IDX_10A = 4
IDX_25A = 5

AVG_WINDOW_MS = 200
BUCKET_MS = 10
N_BUCKETS = AVG_WINDOW_MS // BUCKET_MS
PEAK_FACTOR = 4
PEAK_MAX_MA = 40000                 # INA290 output range: 0-40 A

CONFIRM_WINDOW_MS = 3000
CONFIRM_MIN_MS = 400
MOTOR_TEST_MS = 60000

# AUTO (SPEC §7)
AUTO_IDLE_NUM, AUTO_IDLE_DEN = 3, 2  # 1.5 x idle
AUTO_MIN_HEADROOM_MA = 500           # at least idle + 0.5 A
AUTO_MIN_MA = 500
AUTO_MAX_MA = 5000
AUTO_NEW_1S_MA = 1000
AUTO_NEW_MA = 3000


def auto_limit_ma(idle_ma, cells):
    """idle_ma: this drone's remembered idle current, or -1 if unknown."""
    if idle_ma is None or idle_ma < 0:
        return AUTO_NEW_1S_MA if cells == 1 else AUTO_NEW_MA
    lim = max(idiv(idle_ma * AUTO_IDLE_NUM, AUTO_IDLE_DEN), idle_ma + AUTO_MIN_HEADROOM_MA)
    return clamp(lim, AUTO_MIN_MA, AUTO_MAX_MA)


def peak_threshold_ma(limit_ma):
    return min(limit_ma * PEAK_FACTOR, PEAK_MAX_MA)


class AverageLimiter:
    """200 ms boxcar of 10 ms buckets of charge (mA*ms).  In C: the 10 kHz
    ADC ISR adds into `acc`, the 100 Hz tick rotates the ring."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.buckets = [0] * N_BUCKETS
        self.idx = 0
        self.acc = 0            # charge in the bucket being filled, mA*ms
        self.acc_ms = 0
        self.peak_ma = 0        # highest single sample in the window (for the message)
        self.peaks = [0] * N_BUCKETS

    def add(self, current_ma, dt_ms):
        while dt_ms > 0:
            take = min(dt_ms, BUCKET_MS - self.acc_ms)
            self.acc += current_ma * take
            self.acc_ms += take
            dt_ms -= take
            self.peaks[self.idx] = max(self.peaks[self.idx], current_ma)
            if self.acc_ms >= BUCKET_MS:
                self.buckets[self.idx] = self.acc
                self.idx = (self.idx + 1) % N_BUCKETS
                self.buckets[self.idx] = 0
                self.peaks[self.idx] = 0
                self.acc = 0
                self.acc_ms = 0

    def avg_ma(self):
        """Average over the last 190-200 ms: the 19 completed buckets plus
        the one being filled.  Buckets from before reset() count as 0 A, so
        the first 200 ms after switch-on are judged leniently, never harshly."""
        total = sum(self.buckets) - self.buckets[self.idx] + self.acc
        return idiv(total, (N_BUCKETS - 1) * BUCKET_MS + self.acc_ms)

    def window_peak_ma(self):
        return max(self.peaks)

    def over(self, limit_ma):
        return self.avg_ma() > limit_ma


@dataclass
class LimitSelector:
    idx: int = AUTO
    prev_idx: int = IDX_10A
    confirm_since_ms: int = -1          # >= 0 while "Props off?" is showing
    motor_until_ms: int = -1            # >= 0 while 25 A is active
    last_change_ms: int = -1            # for the S13 overlay
    _plus: bool = False
    _minus: bool = False
    events: list = field(default_factory=list)   # 'confirm', 'motor_on', 'motor_off', 'cancel', 'change'

    @property
    def confirm_pending(self):
        return self.confirm_since_ms >= 0

    @property
    def motor_test(self):
        return self.idx == IDX_25A

    def setting_ma(self):
        return SETTINGS_MA[self.idx]

    def active_ma(self, idle_ma, cells):
        return auto_limit_ma(idle_ma, cells) if self.idx == AUTO else SETTINGS_MA[self.idx]

    def end_motor_test(self, now_ms):
        if self.idx == IDX_25A:
            self.idx = self.prev_idx
            self.motor_until_ms = -1
            self.last_change_ms = now_ms
            self.events.append('motor_off')
        self.confirm_since_ms = -1

    def step(self, now_ms, plus, minus, enabled=True):
        """Feed debounced rocker levels.  Returns True if the setting changed."""
        self.events = []
        plus_edge = plus and not self._plus
        minus_edge = minus and not self._minus
        self._plus, self._minus = plus, minus
        changed = False

        if self.confirm_pending and now_ms - self.confirm_since_ms >= CONFIRM_WINDOW_MS:
            self.confirm_since_ms = -1
            self.events.append('cancel')
        if self.motor_test and now_ms >= self.motor_until_ms:
            self.end_motor_test(now_ms)
            changed = True

        if not enabled or (plus and minus):
            return changed                      # both halves at once: ignored
        if self.confirm_pending:
            if plus_edge and now_ms - self.confirm_since_ms < CONFIRM_MIN_MS:
                self.confirm_since_ms = -1          # pressed before the prompt could be read: mashing
                self.events.append('cancel')
                return changed
            if plus_edge:
                self.prev_idx = self.idx
                self.idx = IDX_25A
                self.motor_until_ms = now_ms + MOTOR_TEST_MS
                self.confirm_since_ms = -1
                self.last_change_ms = now_ms
                self.events.append('motor_on')
                return True
            if minus_edge:
                self.confirm_since_ms = -1
                self.events.append('cancel')
            return changed
        if plus_edge:
            if self.idx == IDX_10A:
                self.confirm_since_ms = now_ms
                self.events.append('confirm')
            elif self.idx < IDX_10A:
                self.idx += 1
                self.last_change_ms = now_ms
                self.events.append('change')
                changed = True
        elif minus_edge:
            if self.idx == IDX_25A:
                self.end_motor_test(now_ms)
                changed = True
            elif self.idx > AUTO:
                self.idx -= 1
                self.last_change_ms = now_ms
                self.events.append('change')
                changed = True
        return changed
