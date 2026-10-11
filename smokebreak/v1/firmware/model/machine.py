"""The SmokeBreak main state machine (SPEC §4, §5, §6; ARCHITECTURE §4).

One call to `Machine.step(inputs)` per control tick (1 ms in the model, the
C firmware's 1 kHz control task).  It returns `Outputs`: the switch commands,
the screen to draw (S-number + data), the ring colour and a beep.

States
    STARTUP    S00, 1.5 s, all switches off
    SAFE       guard closed.  S01 / battery screens S14-S18
    ARMED      guard open, nothing powered.  S02
    CHECKING   3 V probe.  S03
    PRECHARGE  through RPRE (one 7.5 Ohm bank) until VOUT settles.  S04
    ENGAGING   main switch closing on its slow gate, pre-charge still on.  Entered
               only when the pre-charge has settled with VIN - VOUT <= 12 V
               (SIM.md case 1(b)); otherwise PRECHARGE_STALL, nothing closes.  S05
    LIVE       S05 flash, then S06
    WARNING    live, but something changed / battery warning.  S07 or S15
    ABORT      S08 / S09 / S17, alarm, needs the guard closed
    BIND       ELRS three power cycles, then live.  S10
    POWER_CUT  guard closed from any armed state.  S12, then SAFE
Overlays (any state but STARTUP / ABORT / POWER_CUT): S11 "Props off?" while
the 25 A confirm is pending, S13 for 2 s after the limit changes.

Rules
  1. Guard closed => every switch off this tick (the hall switch also gates
     INP and, through Q5 in series with Q4, the pre-charge FET in hardware),
     ABORT cleared, motor test ended.
  2. A fault latches ABORT until the guard is closed.
  3. ON (or BIND) is acted on only after the toggle has been seen at OFF while
     ARMED since the last arming / run / fault.  So a toggle held on while the
     guard closes and opens again (a broken cam), a toggle flicked with the
     guard closed, or a toggle still on after a fault never powers anything.
  4. BIND starts only from ARMED.  Pulling toward BIND mid-check passes
     through OFF, which cancels the check; it does not chain into a bind:
     after a run ends or is cancelled the toggle must rest at OFF for
     REARM_OFF_MS before ON or BIND counts again.
"""
from dataclasses import dataclass, field
from enum import IntEnum

from . import battery, limits, memory, precharge, probe
from .inputs import Toggle, idiv

STARTUP_MS = 1500
POWER_CUT_MS = 1200
MAIN_RAMP_MS = 50                  # TPS48000 slow gate (Cdvdt R1 100k + C1 22n) closes the last <= 12 V
                                   # in ~6-11 ms (SIM.md case 1(b)); 50 ms allowed
LIVE_FLASH_MS = 600                # S05 shown this long after going live
OVERLAY_MS = 2000                  # S13 after a limit change
SHIFT_NOTICE_MS = 3000             # S18 shown this long after a shifted plug is found
REARM_OFF_MS = 300                 # OFF held this long after a run before ON/BIND counts
RESIDUAL_MS = 60000                # drone side still charged from our own run up to 60 s ago ...
RESIDUAL_MARGIN_MV = 300           # ... and no higher than when we let go: residual charge, not a battery

VOUT_DRONE_BATT_MV = 2500          # drone side above this with no input battery: battery on the drone side
VOUT_POWERED_MV = 1000             # drone side above this before anything closes: both sides powered
VOUT_REVERSED_MV = -1000           # below this: reversed battery on the drone side

OVERTEMP_DC = 1000                 # FET NTC, 100 degC
COLLAPSE_PERMILLE = 700            # VIN under 70 % of its resting value ...
COLLAPSE_CELL_MV = 2700            # ... or under 2.7 V per cell
COLLAPSE_DEBOUNCE_MS = 20
IR_SETTLE_MS = 500                 # ignore the first 0.5 s of live for the IR points

BIND_CYCLES = 3                    # short power-ups, then a final one that stays on
BIND_ON_MS = 800                   # on time after the main switch closes (< 2 s with pre-charge)
BIND_OFF_MS = 800


class State(IntEnum):
    STARTUP = 0
    SAFE = 1
    ARMED = 2
    CHECKING = 3
    PRECHARGE = 4
    ENGAGING = 5
    LIVE = 6
    WARNING = 7
    ABORT = 8
    BIND = 9
    POWER_CUT = 10


class Fault(IntEnum):
    NONE = 0
    SHORT = 1
    HALF_SHORT = 2
    REVERSED_LEADS = 3
    BOTH_POWERED = 4
    BATT_ON_DRONE_SIDE = 5
    REVERSED_BATT_DRONE_SIDE = 6
    PRECHARGE_STALL = 7            # settled with > 12 V left across RPRE: refused (drone draws power)
    PRECHARGE_TIMEOUT = 8
    PRECHARGE_ENERGY = 9
    PRECHARGE_BUDGET = 10
    PRECHARGE_HOT = 11
    OVERCURRENT_AVG = 12
    OVERCURRENT_PEAK = 13
    SHORT_TRIP = 14
    OVERTEMP = 15
    INPUT_COLLAPSE = 16


class Led(IntEnum):
    OFF = 0
    EMBER_DIM = 1
    EMBER_PULSE = 2
    WHITE = 3
    GREEN = 4
    EMBER = 5
    RED_FLASH = 6
    BLUE = 7


class ProbeSrc(IntEnum):
    OFF = 0
    R1K = 1
    R100 = 2


# beep patterns (one-shot unless noted); names match ui/screens.py sound()
BEEP_ARM, BEEP_TICK, BEEP_RISE, BEEP_ENGAGE = 'arm', 'tick', 'rise', 'engage'
BEEP_WARN, BEEP_ALARM, BEEP_CUT, BEEP_BIND = 'warn', 'alarm', 'cut', 'bind'

_PRE_FAULT = {
    precharge.Reason.STALL: Fault.PRECHARGE_STALL,
    precharge.Reason.TIMEOUT: Fault.PRECHARGE_TIMEOUT,
    precharge.Reason.ENERGY: Fault.PRECHARGE_ENERGY,
    precharge.Reason.BUDGET: Fault.PRECHARGE_BUDGET,
    precharge.Reason.HOT: Fault.PRECHARGE_HOT,
    precharge.Reason.COLLAPSE: Fault.INPUT_COLLAPSE,
}


@dataclass
class Screen:
    id: str
    data: dict = field(default_factory=dict)


@dataclass
class Outputs:
    precharge_on: bool = False
    main_on: bool = False          # MCU_EN into the INP AND gate
    probe_src: ProbeSrc = ProbeSrc.OFF
    divider_en: bool = True        # balance dividers' ground FET
    peak_threshold_ma: int = 0     # programmed into the comparator's PWM DAC
    screen: Screen = field(default_factory=lambda: Screen('S00'))
    led: Led = Led.OFF
    beep: str = None               # one-shot pattern started this tick
    beep_loop: str = None          # pattern repeated while it stays set (the abort alarm)


def fmt_v(mv):
    return f'{idiv(mv, 100) / 10:.1f} V' if mv >= 0 else f'-{idiv(-mv, 100) / 10:.1f} V'


def fmt_a(ma):
    return f'{ma / 1000:.2f} A' if ma < 10000 else f'{ma / 1000:.1f} A'


def fmt_ohm(mohm):
    return f'{mohm / 1000:.1f} Ω' if mohm < 10000 else f'{idiv(mohm + 500, 1000)} Ω'


class Machine:
    def __init__(self, mem=None):
        self.memory = mem if mem is not None else memory.DroneMemory()
        self.ledger = precharge.EnergyLedger()   # kept across MCU resets (conservative)
        self.limiter = limits.AverageLimiter()
        self.reset()

    # -------------------------------------------------------------- lifecycle
    def reset(self):
        """MCU power-up.  Memory (flash) survives; everything else is RAM."""
        self.state = State.STARTUP
        self.t = None
        self.t_state = 0
        self.off_seen = False
        self.off_since = -1
        self.rearm_ms = 0
        self.last_powered_ms = -1
        self.last_powered_vout_mv = 0
        self.residual = False
        self.fault = Fault.NONE
        self.fault_data = {}
        self.batt = battery.BatteryInfo()
        self.batt_idle = battery.BatteryInfo()   # last analysis taken with (almost) no current flowing
        self.bind_mode = False
        self.bind_saw_on = False
        self.bind_live = False
        self.bind_cycle = 0
        self.bind_phase = ''
        self.t_phase = 0
        self.pre = None
        self.high, self.low, self.high2 = [], [], []
        self.probe_result = None
        self.check_done = 0
        self.visit = None
        self.cells = 0
        self.vin_rest = 0
        self.i_zero = 0
        self.live_since = 0
        self.idle_done = False
        self.idle_ma = -1
        self.ir_lo = None
        self.ir_hi = None
        self.ir = None
        self.warn_list = []
        self.collapse_ms = 0
        self.shift_since = -1
        self.armed_hint = ''
        self.beep = None
        self.prev = None
        self.limit = limits.LimitSelector()   # RAM: back to AUTO after a power loss

    def _go(self, state):
        self.state = state
        self.t_state = self.t

    # -------------------------------------------------------------- helpers
    def _active_limit_ma(self):
        # AUTO uses what the drone drew last visit; this visit's reading only
        # takes effect next time (the limit never tightens under a live drone)
        idle = self.visit.ref_idle_ma if self.visit is not None else -1
        return self.limit.active_ma(idle, self.cells or self.batt.cells)

    def _abort(self, fault, **data):
        if self.pre is not None:
            self.pre.close()
            self.pre = None
        self.fault = fault
        self.fault_data = data
        self.bind_mode = False
        self._go(State.ABORT)
        self.beep = BEEP_ALARM

    def _to_armed(self, inp, beep=None, after_run=False):
        if self.pre is not None:
            self.pre.close()
            self.pre = None
        self.bind_mode = False
        self.bind_live = False
        self.rearm_ms = REARM_OFF_MS if after_run else 0
        self.off_since = self.t if inp.toggle == Toggle.OFF else -1
        self.off_seen = inp.toggle == Toggle.OFF and not after_run
        self._go(State.ARMED)
        if beep:
            self.beep = beep

    def _drone_side_battery(self, inp):
        return inp.vin_mv < battery.VIN_PRESENT_MV and inp.vout_mv >= VOUT_DRONE_BATT_MV

    # -------------------------------------------------------------- main tick
    def step(self, inp):
        if self.t is None:
            self.t = inp.t_ms
            self.t_state = inp.t_ms
        dt = inp.t_ms - self.t
        self.t = now = inp.t_ms
        self.beep = None
        current = max(0, inp.current_ma - self.i_zero)

        self.batt = battery.analyse(inp.vin_mv, inp.taps_mv, current)
        # Cell voltages are trusted at idle only.  The taps are read against
        # board GND, but the pack's B- reaches GND through the reverse-battery
        # FET Q11 (and the balance black wire through 10 Ohm, R75), so with
        # current flowing every tap reads high by I x (Q11 + lead) and the
        # cells sag by I x their IR.  Per-cell verdicts use batt_idle.
        if self.batt.resting:
            self.batt_idle = self.batt
        if self.batt.bal.present and self.batt.bal.shift > 0 and self.batt.main_present:
            if self.shift_since < 0:
                self.shift_since = now
        else:
            self.shift_since = -1

        rocker_ok = self.state not in (State.STARTUP, State.ABORT, State.POWER_CUT)
        changed = self.limit.step(now, inp.btn_plus, inp.btn_minus, rocker_ok)
        if 'confirm' in self.limit.events or 'motor_on' in self.limit.events:
            self.beep = BEEP_WARN
        if changed and 'motor_off' in self.limit.events and self._powered():
            self.beep = BEEP_CUT

        if self.state == State.STARTUP:
            if now - self.t_state >= STARTUP_MS:
                if inp.guard_closed:
                    self._go(State.SAFE)
                else:
                    self._to_armed(inp)
        elif inp.guard_closed:
            self._guard_closed(inp)
        else:
            self._guard_open(inp, now, dt, current)

        self.prev = inp
        return self._outputs(inp, now)

    def _powered(self):
        return self.state in (State.PRECHARGE, State.ENGAGING, State.LIVE, State.WARNING, State.BIND)

    def _guard_closed(self, inp):
        if self.state == State.SAFE:
            return
        if self.state == State.POWER_CUT:
            if self.t - self.t_state >= POWER_CUT_MS:
                self._go(State.SAFE)
            return
        # every other state: cut, clear, reset
        if self.pre is not None:
            self.pre.close()
            self.pre = None
        self.fault = Fault.NONE
        self.fault_data = {}
        self.bind_mode = False
        self.bind_live = False
        self.limit.end_motor_test(self.t)
        self.off_seen = False
        self._go(State.POWER_CUT)
        self.beep = BEEP_CUT

    def _guard_open(self, inp, now, dt, current):
        s = self.state
        if s in (State.SAFE, State.POWER_CUT):
            self._to_armed(inp, BEEP_ARM)
            self.armed_hint = ''
            return
        if s == State.ABORT:
            return                       # only the guard resets a fault
        if s == State.ARMED:
            self._armed(inp, now)
        elif s == State.CHECKING:
            self._checking(inp, now)
        elif s == State.PRECHARGE:
            self._precharge(inp, now)
        elif s == State.ENGAGING:
            self._engaging(inp, now, dt, current)
        elif s in (State.LIVE, State.WARNING):
            self._live(inp, now, dt, current)
        elif s == State.BIND:
            self._bind(inp, now, dt, current)

    # -------------------------------------------------------------- ARMED
    def _armed(self, inp, now):
        if inp.toggle == Toggle.OFF:
            if self.off_since < 0:
                self.off_since = now
            if now - self.off_since >= self.rearm_ms:
                self.off_seen = True
            return
        self.off_since = -1
        if not self.off_seen:
            if not self.armed_hint:
                self.armed_hint = 'switch_off_first'
            return
        self.off_seen = False
        self.bind_mode = inp.toggle == Toggle.BIND
        self.bind_saw_on = False
        self.armed_hint = ''
        if inp.vin_mv < battery.VIN_PRESENT_MV:
            if inp.vout_mv >= VOUT_DRONE_BATT_MV:
                self._abort(Fault.BATT_ON_DRONE_SIDE, vout_mv=inp.vout_mv)
            else:
                self.armed_hint = 'no_battery'
                self.beep = BEEP_WARN
            return
        self.residual = False
        if inp.vout_mv > VOUT_POWERED_MV:
            if (self.last_powered_ms >= 0 and now - self.last_powered_ms <= RESIDUAL_MS
                    and inp.vout_mv <= self.last_powered_vout_mv + RESIDUAL_MARGIN_MV):
                # Our own drone, its capacitors still charged.  The 3 V probe
                # cannot drive a node above 3 V, but held charge already rules
                # out a short, a half-short and reversed leads (each would have
                # drained it).  Go straight to the supervised pre-charge, which
                # still catches a fault that appears at higher voltage.
                self.residual = True
                self.i_zero = inp.current_ma
                self.vin_rest = inp.vin_mv
                self.cells = self.batt.cells
                self.check_done = 4
                self.warn_list = []
                self._start_precharge(inp, now)
                return
            self._abort(Fault.BOTH_POWERED, vout_mv=inp.vout_mv)
            return
        if inp.vout_mv < VOUT_REVERSED_MV:
            self._abort(Fault.REVERSED_BATT_DRONE_SIDE, vout_mv=inp.vout_mv)
            return
        # start the run: auto-zero the INA181A2 (switch open), freeze the resting numbers
        self.i_zero = inp.current_ma
        self.vin_rest = inp.vin_mv
        self.cells = self.batt.cells
        self.high, self.low, self.high2 = [], [], []
        self.probe_result = None
        self.check_done = 0
        self.visit = None
        self.warn_list = []
        self._go(State.CHECKING)
        self.beep = BEEP_TICK

    def _cancelled(self, inp):
        """Toggle leaving the run.  Normal run: anything but ON cancels.
        Bind run: the toggle springs back to OFF by itself, so only an ON
        followed by OFF (the user taking the switch back) cancels."""
        if not self.bind_mode:
            return inp.toggle != Toggle.ON
        if inp.toggle == Toggle.ON:
            self.bind_saw_on = True
        return self.bind_saw_on and inp.toggle == Toggle.OFF

    # -------------------------------------------------------------- CHECKING
    def _checking(self, inp, now):
        if self._cancelled(inp):
            self._to_armed(inp, after_run=True)
            return
        el = now - self.t_state
        if 0 < el <= probe.PROBE_T_HIGH_MS:
            self.high.append(inp.vout_low_mv)
        elif probe.PROBE_T_HIGH_MS < el <= probe.PROBE_T_FIRST2_MS:
            self.low.append(inp.vout_low_mv)
        elif probe.PROBE_T_FIRST2_MS < el <= probe.PROBE_TOTAL_MS:
            self.high2.append(inp.vout_low_mv)
        if el in (probe.PROBE_T_HIGH_MS, probe.PROBE_T_FIRST2_MS):
            self.check_done += 1               # S03 lines: 3 V probe, short circuit
            self.beep = BEEP_TICK
        if el < probe.PROBE_TOTAL_MS:
            return
        r = probe.classify(self.high, self.low, self.high2, self.cells)
        self.probe_result = r
        self.check_done = 4
        if r.verdict == probe.Verdict.SHORT:
            self._abort(Fault.SHORT, mohm=r.load_mohm)
            return
        if r.verdict == probe.Verdict.HALF_SHORT:
            self._abort(Fault.HALF_SHORT, mohm=r.load_mohm)
            return
        if r.verdict == probe.Verdict.REVERSED:
            self._abort(Fault.REVERSED_LEADS, v_mv=r.v_low_mv)
            return
        self.beep = BEEP_TICK
        if r.verdict == probe.Verdict.OK and r.cap_uf > 0 and self.cells:
            self.visit = self.memory.visit(self.cells, r.cap_uf)
        self._start_precharge(inp, now)

    def _start_precharge(self, inp, now):
        self.pre = precharge.Supervisor(now, inp.vin_mv, self.ledger)
        why = self.pre.can_start(inp.ntc_rpre_dc)
        if why != precharge.Reason.NONE:
            self.pre = None
            self._abort(_PRE_FAULT[why], wait_ms=self.ledger.wait_ms(now), vin_mv=inp.vin_mv,
                        vout_mv=inp.vout_mv, ma=0)
            return
        if self.bind_mode and self.state == State.BIND:
            self.bind_phase = 'pre'
            self.t_phase = now
        else:
            self._go(State.PRECHARGE)
            if self.bind_mode:
                self.bind_cycle = 1
            self.beep = BEEP_RISE

    # -------------------------------------------------------------- PRECHARGE
    def _precharge_step(self, inp, now):
        """Returns True on pass, False while running; aborts on failure."""
        st = self.pre.step(now, inp.vin_mv, inp.vout_mv, inp.ntc_rpre_dc)
        if st == precharge.Status.RUNNING:
            return False
        p = self.pre
        self.pre = None
        if st == precharge.Status.PASS:
            return True
        self._abort(_PRE_FAULT[p.reason], vin_mv=p.stop_vin_mv, vout_mv=p.stop_vout_mv, ma=p.stop_ma,
                    energy_uj=p.energy_uj, wait_ms=self.ledger.wait_ms(now))
        return False

    def _precharge(self, inp, now):
        if self._cancelled(inp):
            self._to_armed(inp, BEEP_CUT, after_run=True)
            return
        if self._precharge_step(inp, now):
            self.limiter.reset()
            self.check_done = 5
            if self.bind_mode:
                self._go(State.BIND)
                self.bind_phase = 'ramp'
                self.t_phase = now
            else:
                self._go(State.ENGAGING)

    # -------------------------------------------------------------- ENGAGING
    def _engaging(self, inp, now, dt, current):
        if self._cancelled(inp):
            self._to_armed(inp, BEEP_CUT, after_run=True)
            return
        if self._trips(inp, dt, current):
            return
        if now - self.t_state >= MAIN_RAMP_MS:
            self._enter_live(now)

    def _enter_live(self, now):
        self._go(State.LIVE)
        self.live_since = now
        self.idle_done = False
        self.idle_ma = -1
        self.ir_lo = self.ir_hi = None
        self.ir = None
        self.collapse_ms = 0
        self.beep = BEEP_ENGAGE
        w = []
        if self.visit is not None:
            w += [('drone',) + x for x in self.visit.warnings]
        r = self.probe_result
        if r is not None and probe.no_big_cap(r.cap_uf, self.cells):
            w.append(('drone', 'no_big_cap', 0, r.cap_uf))
        for kind, idx, mv in self.batt_idle.warnings:      # idle cell readings, not under load
            if kind != battery.Warn.HIGH_IR:
                w.append(('battery', kind, idx, mv))
        self.warn_list = w
        if w:
            self._go(State.WARNING)
            self.live_since = now
            self.beep = BEEP_WARN

    # -------------------------------------------------------------- shared live checks
    def _trips(self, inp, dt, current):
        """Peak, driver short, average, temperature, input collapse."""
        lim = self._active_limit_ma()
        if inp.short_trip:
            self._abort(Fault.SHORT_TRIP, ma=current)
            return True
        if inp.peak_trip:
            self._abort(Fault.OVERCURRENT_PEAK, threshold_ma=limits.peak_threshold_ma(lim), limit_ma=lim)
            return True
        self.limiter.add(current, dt)
        if self.limiter.over(lim):
            self._abort(Fault.OVERCURRENT_AVG, limit_ma=lim, avg_ma=self.limiter.avg_ma(),
                        peak_ma=self.limiter.window_peak_ma())
            return True
        if inp.ntc_fet_dc >= OVERTEMP_DC:
            self._abort(Fault.OVERTEMP, dc=inp.ntc_fet_dc)
            return True
        floor = max(idiv(self.vin_rest * COLLAPSE_PERMILLE, 1000), self.cells * COLLAPSE_CELL_MV)
        if inp.vin_mv < floor:
            self.collapse_ms += dt
            if self.collapse_ms >= COLLAPSE_DEBOUNCE_MS:
                self._abort(Fault.INPUT_COLLAPSE, vin_mv=inp.vin_mv, rest_mv=self.vin_rest, ma=current)
                return True
        else:
            self.collapse_ms = 0
        return False

    # -------------------------------------------------------------- LIVE / WARNING
    def _live(self, inp, now, dt, current):
        if self.bind_live:
            if inp.toggle == Toggle.ON:
                self.bind_live = False        # the switch takes over; OFF now cuts as usual
        elif inp.toggle != Toggle.ON:
            self._to_armed(inp, BEEP_CUT, after_run=True)
            return
        if self._trips(inp, dt, current):
            return
        el = now - self.live_since
        # idle current at 10 s -> drone memory
        if not self.idle_done and el >= memory.IDLE_RECORD_MS:
            self.idle_done = True
            self.idle_ma = self.limiter.avg_ma()
            if self.visit is not None and self.memory.record_idle(self.visit, self.idle_ma):
                kind, old, new = self.visit.warnings[-1]
                self.warn_list.append(('drone', kind, old, new))
        # internal resistance from the lowest and highest current seen
        if el >= IR_SETTLE_MS:
            pt = (current, inp.vin_mv)
            if self.ir_lo is None or current < self.ir_lo[0]:
                self.ir_lo = pt
            if self.ir_hi is None or current > self.ir_hi[0]:
                self.ir_hi = pt
            res = battery.ir_estimate(self.ir_lo[1], self.ir_lo[0], self.ir_hi[1], self.ir_hi[0], self.cells)
            if res is not None:
                self.ir = res + (self.ir_hi[0],)
                if res[2] and not any(w[1] == battery.Warn.HIGH_IR for w in self.warn_list):
                    self.warn_list.append(('battery', battery.Warn.HIGH_IR, res[0], res[1]))
        if self.warn_list and self.state == State.LIVE:
            self._go(State.WARNING)
            self.beep = BEEP_WARN

    # -------------------------------------------------------------- BIND
    def _bind(self, inp, now, dt, current):
        if self._cancelled(inp):
            self._to_armed(inp, BEEP_CUT, after_run=True)
            return
        ph = self.bind_phase
        if ph == 'pre':
            if self._precharge_step(inp, now):
                self.limiter.reset()
                self.bind_phase, self.t_phase = 'ramp', now
            return
        if ph in ('ramp', 'on'):
            if self._trips(inp, dt, current):
                return
            if ph == 'ramp' and now - self.t_phase >= MAIN_RAMP_MS:
                if self.bind_cycle > BIND_CYCLES:
                    self.bind_mode = False
                    self.bind_live = True
                    self._enter_live(now)
                    return
                self.bind_phase, self.t_phase = 'on', now
                self.beep = BEEP_BIND
            elif ph == 'on' and now - self.t_phase >= BIND_ON_MS:
                self.bind_phase, self.t_phase = 'off', now
            return
        if ph == 'off' and now - self.t_phase >= BIND_OFF_MS:
            self.bind_cycle += 1
            self._start_precharge(inp, now)

    # -------------------------------------------------------------- outputs
    def _outputs(self, inp, now):
        o = self._drive(inp, now)
        if o.main_on or o.precharge_on:
            self.last_powered_ms = now
            self.last_powered_vout_mv = max(inp.vout_mv, 0)
        return o

    def _drive(self, inp, now):
        o = Outputs()
        s = self.state
        if s == State.CHECKING:
            el = now - self.t_state
            o.probe_src = ProbeSrc.R100 if probe.PROBE_T_HIGH_MS <= el < probe.PROBE_T_FIRST2_MS \
                else ProbeSrc.R1K
        o.precharge_on = s == State.PRECHARGE or s == State.ENGAGING or (
            s == State.BIND and self.bind_phase in ('pre', 'ramp'))
        o.main_on = s in (State.ENGAGING, State.LIVE, State.WARNING) or (
            s == State.BIND and self.bind_phase in ('ramp', 'on'))
        o.peak_threshold_ma = limits.peak_threshold_ma(self._active_limit_ma())
        o.led = self._led(inp, s)
        o.screen = self._screen(inp, s, now)
        o.beep = self.beep
        o.beep_loop = BEEP_ALARM if s == State.ABORT else None
        return o

    def _led(self, inp, s):
        if s == State.STARTUP:
            return Led.OFF
        if s in (State.SAFE, State.POWER_CUT):
            return Led.EMBER_DIM if (self.batt.main_present or self.batt.bal.present) else Led.OFF
        if s == State.ARMED:
            return Led.EMBER_PULSE
        if s in (State.CHECKING, State.PRECHARGE, State.ENGAGING):
            return Led.BLUE if self.bind_mode else Led.WHITE
        if s == State.LIVE:
            return Led.GREEN
        if s == State.WARNING:
            return Led.EMBER
        if s == State.ABORT:
            return Led.RED_FLASH
        if s == State.BIND:
            return Led.BLUE
        return Led.OFF

    def _battery_screen(self, inp, now):
        b = self.batt
        if self._drone_side_battery(inp):
            return Screen('S17', {'vout_mv': inp.vout_mv})
        if b.balance_only:
            return Screen('S16', self._batt_data(b))
        if self.shift_since >= 0 and now - self.shift_since < SHIFT_NOTICE_MS:
            return Screen('S18', dict(self._batt_data(b), shift=b.bal.shift))
        if b.warnings:
            return Screen('S15', dict(self._batt_data(b), warning=b.warnings[0]))
        if b.bal.present:
            return Screen('S14', self._batt_data(b))
        return Screen('S01', {'vin_mv': b.vin_mv, 'cells': b.cells, 'guess': b.guess.ambiguous,
                              'battery': b.main_present})

    @staticmethod
    def _batt_data(b):
        return {'vin_mv': b.vin_mv, 'cells': b.cells, 'certain': b.cells_certain, 'soc': b.soc_pct,
                'cells_mv': list(b.bal.cells_mv), 'lo': b.lo_idx, 'hi': b.hi_idx, 'delta_mv': b.delta_mv,
                'delta': b.delta, 'storage': b.storage, 'chem': b.chem, 'shift': b.bal.shift,
                'balance': b.balance}

    def _screen(self, inp, s, now):
        if s == State.STARTUP:
            return Screen('S00')
        if s == State.POWER_CUT:
            return Screen('S12')
        if s == State.ABORT:
            return self._abort_screen()
        if self.limit.confirm_pending:
            return Screen('S11', {'left_ms': limits.CONFIRM_WINDOW_MS - (now - self.limit.confirm_since_ms)})
        if self.limit.last_change_ms >= 0 and now - self.limit.last_change_ms < OVERLAY_MS:
            lim = self._active_limit_ma()
            return Screen('S13', {'idx': self.limit.idx, 'limit_ma': lim,
                                  'peak_ma': limits.peak_threshold_ma(lim)})
        if s == State.SAFE:
            return self._battery_screen(inp, now)
        if s == State.ARMED:
            if self._drone_side_battery(inp):
                return Screen('S17', {'vout_mv': inp.vout_mv})
            return Screen('S02', {'vin_mv': inp.vin_mv, 'cells': self.batt.cells, 'hint': self.armed_hint})
        if s == State.CHECKING:
            return Screen('S03', {'done': self.check_done})
        if s == State.PRECHARGE:
            return Screen('S04', {'vout_mv': inp.vout_mv, 'vin_mv': inp.vin_mv})
        if s == State.ENGAGING:
            return Screen('S05')
        if s == State.BIND:
            return Screen('S10', {'step': min(self.bind_cycle, BIND_CYCLES), 'phase': self.bind_phase})
        if s in (State.LIVE, State.WARNING):
            if now - self.live_since < LIVE_FLASH_MS:
                return Screen('S05')
            if s == State.WARNING:
                drone = [w for w in self.warn_list if w[0] == 'drone']
                if drone:
                    return Screen('S07', {'warning': drone[0][1:], 'all': list(self.warn_list)})
                return Screen('S15', {'warning': self.warn_list[0][1:], 'ir': self.ir})
            return Screen('S06', {'ma': max(0, inp.current_ma - self.i_zero), 'limit_ma': self._active_limit_ma(),
                                  'auto': self.limit.idx == limits.AUTO,
                                  'drone': self.visit.profile.number if self.visit else 0,
                                  'new': self.visit.new if self.visit else True,
                                  'same': bool(self.visit and not self.visit.new and self.idle_done),
                                  't_s': idiv(now - self.live_since, 1000)})
        return Screen('S01')

    def _abort_screen(self):
        f, d = self.fault, self.fault_data
        if f == Fault.REVERSED_LEADS:
            return Screen('S09', {'fault': f, 'title': 'Leads reversed', 'value': 'RED ↔ BLACK'})
        if f == Fault.REVERSED_BATT_DRONE_SIDE:
            return Screen('S09', {'fault': f, 'title': 'Reversed battery on the drone side',
                                  'value': fmt_v(d['vout_mv'])})
        if f == Fault.BATT_ON_DRONE_SIDE:
            return Screen('S17', {'fault': f, 'vout_mv': d['vout_mv']})
        titles = {
            Fault.SHORT: ('Short circuit', lambda: fmt_ohm(d['mohm'])),
            Fault.HALF_SHORT: ('Half-short', lambda: fmt_ohm(d['mohm'])),
            Fault.BOTH_POWERED: ('Drone side already has power', lambda: fmt_v(d['vout_mv'])),
            # (the screen's lines: "Unplug the drone's battery, or wait for it to discharge.")
            # refused: the main switch may only close across <= 12 V (SIM.md case 1(b))
            Fault.PRECHARGE_STALL: ('Drone draws power at {}'.format(fmt_v(d.get('vout_mv', 0))),
                                    lambda: f"{fmt_v(d['vin_mv'] - d['vout_mv'])} gap · {fmt_a(d['ma'])}"),
            Fault.PRECHARGE_TIMEOUT: ('Charging took too long', lambda: f"{fmt_v(d['vout_mv'])} · {fmt_a(d['ma'])}"),
            Fault.PRECHARGE_ENERGY: ('Charge resistor too hot', lambda: f"{fmt_v(d['vout_mv'])} · {fmt_a(d['ma'])}"),
            Fault.PRECHARGE_BUDGET: ('Charge resistor cooling', lambda: f"wait {idiv(d['wait_ms'] + 999, 1000)} s"),
            Fault.PRECHARGE_HOT: ('Charge resistor cooling', lambda: f"wait {idiv(d['wait_ms'] + 999, 1000)} s"),
            Fault.OVERCURRENT_AVG: ('Over {} for 0.2 s'.format(fmt_a(d.get('limit_ma', 0))),
                                    lambda: f"peak {fmt_a(d['peak_ma'])}"),
            Fault.OVERCURRENT_PEAK: ('Spike over {}'.format(fmt_a(d.get('threshold_ma', 0))),
                                     lambda: fmt_a(d['threshold_ma'])),
            Fault.SHORT_TRIP: ('Short on the drone', lambda: 'driver trip'),
            Fault.OVERTEMP: ('Switch too hot', lambda: f"{idiv(d['dc'], 10)} °C"),
            Fault.INPUT_COLLAPSE: ('Battery voltage collapsed', lambda: fmt_v(d['vin_mv'])),
        }
        title, val = titles[f]
        return Screen('S08', {'fault': f, 'title': title, 'value': val()})
