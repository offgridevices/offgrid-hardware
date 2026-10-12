"""A small simulated plant so scenarios run end to end.

This is test equipment, not firmware: it uses floats (volts, amps, seconds)
and is never ported.  It models just enough of the board and the outside
world for every decision in the firmware model to be exercised:

* the pack: cells (OCV + IR each), lead resistance; on the input, reversed,
  or plugged into the drone side
* the balance lead: which pack it belongs to, shifted along the header,
  broken wires
* the drone: bulk capacitance, leakage, resistive loads (1S FC, half-short,
  short), reversed leads (two body diodes), regulators that start drawing
  idle current above a voltage, a digital VTX drawing constant power, a
  fault that appears only above some voltage, and a motor demand
* the board: probe source (3.0 V through 1 kOhm / 100 Ohm and a Schottky),
  the board's own 4.1 uF on VOUT, pre-charge (D3 + 7.8 Ohm), back-to-back
  switch with a slow gate, the low-side shunt + INA181A2 (sees pre-charge
  current too), the INP AND gate (MCU_EN, guard, peak latch cleared by the
  programmable LMV331 - which also trips above its ~52 A common-mode
  ceiling - or the fixed ~65 A hard-short LMV331), the TPS48000 SCP at
  ~99 A, the reverse-battery FET Q11 in the battery return (lifts the
  balance taps under load), FET and RPRE temperatures, the aux diode-OR
  (is the MCU awake at all?)

`Rig` wires a World to a Machine and gives the tests human-sized verbs:
open_guard(), on(), off(), bind(), plus(), close_guard(), run(ms).
"""
import math
from dataclasses import dataclass, field

from .inputs import Inputs, Toggle, N_TAPS, aux_powered
from .machine import Machine, ProbeSrc, State
from .precharge import RPRE_MOHM
from .probe import BOARD_CAP_NF

PROBE_V = 3.0
SCHOTTKY_V = 0.0           # the probe's 3.0 V is specified after its diode
SWITCH_OHM = 0.009         # Q1 + Q2 + shunt
SLEW_MS_FULL = 50.0        # slow gate: 0 -> VIN in 50 ms
SCP_TRIP_A = 99.0          # TPS48000 SCP, RISCP 40.2 kOhm (SIM.md case 3; model value)
HARD_SHORT_A = 65.0        # fixed LMV331 on the shunt, 64.7 mV (circuit.py R70/R71; SIM.md case 3)
PEAK_CM_CEILING_A = 52.0   # LMV331 input above ~2.6 V pulls PEAK_OK low whatever PEAK_REF is (SIM.md 3a)
INA_MAX_A = 65.6           # INA181A2: 50 V/V x 1 mOhm, output 0-3.28 V
D3_V = 0.45                # pre-charge Schottky SS2H10 forward drop
Q11_OHM = 0.007            # reverse-battery FET in the battery return (BSC070N10LS5, gate at 12 V)
SUBSTEPS = 10              # node solver substeps when the main switch is open


@dataclass
class Pack:
    cells_v: list
    cell_ir_mohm: float = 4.0
    lead_mohm: float = 6.0

    @staticmethod
    def of(n, v=3.85, ir=4.0):
        return Pack([v] * n, ir)

    @property
    def ocv(self):
        return sum(self.cells_v)

    @property
    def r(self):
        return (self.cell_ir_mohm * len(self.cells_v) + self.lead_mohm) / 1000.0


@dataclass
class Balance:
    pack: Pack = None              # None: same pack as the main lead
    shift: int = 0                 # pins the black wire sits above pin 1
    broken: list = field(default_factory=list)   # wire numbers (1..n) that are open


@dataclass
class Drone:
    cap_uf: float = 1000.0
    leak_ohm: float = 20000.0
    load_ohm: float = 0.0          # resistive load at any voltage (1S FC, half-short), 0 = none
    short_ohm: float = 0.0         # dead short, 0 = none
    reversed: bool = False         # leads soldered backwards: two body diodes in series
    diode_v: float = 1.0
    diode_ohm: float = 10.0
    idle_a: float = 0.35           # regulators' draw once above reg_on_v
    reg_on_v: float = 5.0
    vtx_w: float = 0.0             # constant-power digital VTX above vtx_on_v
    vtx_on_v: float = 8.0
    fault_ohm: float = 0.0         # appears only above fault_on_v (a 5 V part on battery voltage)
    fault_on_v: float = 6.0
    demand_a: float = 0.0          # motors (test sets this), when above reg_on_v
    battery: tuple = None          # (ocv_v signed, r_ohm): a battery plugged into the drone side

    @staticmethod
    def whoop_1s():
        return Drone(cap_uf=60, leak_ohm=50000, load_ohm=75, idle_a=0.25, reg_on_v=3.3)

    @staticmethod
    def quad(cap_uf=1000.0, idle_a=0.35, vtx_w=0.0):
        return Drone(cap_uf=cap_uf, idle_a=idle_a, vtx_w=vtx_w)


class World:
    def __init__(self, pack=None, drone=None, balance=None, usb=False, input_reversed=False):
        self.pack = pack
        self.input_reversed = input_reversed
        self.drone = drone
        self.balance = balance
        self.usb = usb
        self.guard_closed = True
        self.toggle = Toggle.OFF
        self.plus = False
        self.minus = False
        self.cam_works = True          # guard cams the toggle to OFF as it closes
        self.ina_offset_ma = 12
        self.t_amb = 25.0
        self.t_fet = 25.0
        self.t_rpre = 25.0
        self.force_ntc_fet_dc = None
        self.v = 0.0                   # drone-side node, volts
        self.i_main = 0.0
        self.i_pre = 0.0
        self.i_shunt = 0.0             # drone return current through the low-side shunt
        self.peak_latch = False
        self.short_latch = False
        self.peak_threshold_a = 0.0
        self.t_ms = 0
        self.max_drone_v = 0.0         # highest drone-side voltage while the board drove it
        self.drone_batt_energy = 0.0   # charge drawn from the input into the drone, A*s
        self.last_out = None

    # ---------------------------------------------------------- the input side
    def vin_ocv(self):
        if self.pack is None or self.input_reversed:
            return 0.0
        return self.pack.ocv

    def vin(self):
        if self.pack is None or self.input_reversed:
            return 0.0
        return max(0.0, self.pack.ocv - (self.i_main + self.i_pre) * (self.pack.r + Q11_OHM))

    # ---------------------------------------------------------- balance taps
    def taps(self, divider_en=True):
        t = [0] * N_TAPS
        b = self.balance
        if b is None or not divider_en:
            return t
        pack = b.pack or self.pack
        if pack is None:
            return t
        same = b.pack is None
        i = (self.i_main + self.i_pre) if same else 0.0
        n = len(pack.cells_v)
        if b.shift > 0 and not (same and self.pack is not None and not self.input_reversed):
            return t                   # no ground reference: floats, reads 0
        # pack B- sits above board GND by I x (Q11 + the main lead's negative half):
        # every tap reads high by that much under load (the 10 Ohm in the black
        # wire, R75, keeps the balance lead from sharing the return)
        v = i * (Q11_OHM + pack.lead_mohm / 2000.0) if same else 0.0
        for w in range(1, n + 1):
            v += pack.cells_v[w - 1] - i * pack.cell_ir_mohm / 1000.0
            pin = 1 + b.shift + w      # XH pin number of wire w
            if pin > 9 or w in b.broken:
                continue
            t[pin - 2] = int(round(v * 1000))
        return t

    def bal_top_mv(self):
        b = self.balance
        if b is None:
            return 0
        pack = b.pack or self.pack
        return int(pack.ocv * 1000) if pack else 0

    def bal_referenced(self):
        return self.balance is not None and self.balance.shift == 0

    # ---------------------------------------------------------- awake?
    def powered(self):
        return aux_powered(int(self.vin() * 1000), int(self.v * 1000), self.bal_top_mv(),
                           self.bal_referenced(), self.usb)

    def sense(self):
        out = self.last_out
        vin_mv = int(round(self.vin() * 1000))
        vout_mv = int(round(self.v * 1000))
        i_ma = int(round(min(self.i_shunt, INA_MAX_A) * 1000)) + self.ina_offset_ma
        ntc_fet = self.force_ntc_fet_dc if self.force_ntc_fet_dc is not None else int(self.t_fet * 10)
        return Inputs(
            t_ms=self.t_ms, vin_mv=vin_mv, vout_mv=max(vout_mv, -5000),
            vout_low_mv=min(max(vout_mv, 0), 3300), current_ma=i_ma,
            peak_trip=self.peak_latch, short_trip=self.short_latch,
            taps_mv=self.taps(out.divider_en if out else True),
            ntc_fet_dc=ntc_fet, ntc_rpre_dc=int(self.t_rpre * 10),
            guard_closed=self.guard_closed, toggle=self.toggle,
            btn_minus=self.minus, btn_plus=self.plus, usb_present=self.usb)

    # ---------------------------------------------------------- physics
    def _drone_loads(self, v):
        """(conductance list [(G, Vsrc)], nonlinear current at v)."""
        d = self.drone
        g = []
        inl = 0.0
        if d is None:
            g.append((1e-6, 0.0))      # a few uF of lead/node only (handled via cap)
            return g, inl
        if d.leak_ohm:
            g.append((1.0 / d.leak_ohm, 0.0))
        if d.load_ohm:
            g.append((1.0 / d.load_ohm, 0.0))
        if d.short_ohm:
            g.append((1.0 / d.short_ohm, 0.0))
        if d.fault_ohm and v > d.fault_on_v:
            g.append((1.0 / d.fault_ohm, 0.0))
        if d.battery is not None:
            ocv, r = d.battery
            g.append((1.0 / r, ocv))
        if not d.reversed and v > d.reg_on_v:
            inl += d.idle_a + d.demand_a
            if d.vtx_w and v > d.vtx_on_v:
                inl += d.vtx_w / v
        return g, inl

    def _cap_f(self):
        return ((self.drone.cap_uf if self.drone else 0.2) + BOARD_CAP_NF / 1000.0) * 1e-6

    def apply(self, out, dt_ms):
        self.last_out = out
        dt = dt_ms / 1000.0
        vin_ocv = self.vin_ocv()
        vin_prev = self.vin()
        inp_gate = out.main_on and not self.guard_closed and not self.peak_latch and not self.short_latch \
            and vin_ocv > 0
        if not out.main_on:
            self.peak_latch = False    # MCU_EN low resets the comparator latch and the driver
            self.short_latch = False
        self.peak_threshold_a = out.peak_threshold_ma / 1000.0
        rpre = RPRE_MOHM / 1000.0
        c = self._cap_f()
        self.i_pre = 0.0
        if inp_gate:
            target = vin_prev - self.i_main * SWITCH_OHM
            slew = max(vin_ocv, 1.0) / SLEW_MS_FULL * dt_ms
            v_new = min(target, self.v + slew) if self.v < target else target
            g, inl = self._drone_loads(v_new)
            i_load = inl + sum(gg * (v_new - vs) for gg, vs in g)
            if self.drone and self.drone.reversed and v_new > self.drone.diode_v:
                i_load += (v_new - self.drone.diode_v) / self.drone.diode_ohm
            i_cap = c * (v_new - self.v) / dt
            i = max(0.0, i_load + i_cap)
            if out.precharge_on:
                self.i_pre = max(0.0, (vin_prev - D3_V - v_new) / rpre)
            self.v = v_new
            self.i_main = i
            if i > min(self.peak_threshold_a, PEAK_CM_CEILING_A) and self.peak_threshold_a > 0:
                self.peak_latch = True
            if i > HARD_SHORT_A:
                self.peak_latch = True     # U12 shares PEAK_OK with the programmable comparator
            if i > SCP_TRIP_A:
                self.short_latch = True
            if self.peak_latch or self.short_latch:
                self.i_main = min(i, INA_MAX_A)
        else:
            self.i_main = 0.0
            h = dt / SUBSTEPS
            ipre_sum = 0.0
            for _ in range(SUBSTEPS):
                g, inl = self._drone_loads(self.v)
                if out.precharge_on and vin_ocv > 0 and self.v < vin_prev - D3_V:   # D3 blocks back-feed
                    g = g + [(1.0 / rpre, vin_prev - D3_V)]
                if out.probe_src != ProbeSrc.OFF and self.v < PROBE_V:
                    rs = 1000.0 if out.probe_src == ProbeSrc.R1K else 100.0
                    g = g + [(1.0 / rs, PROBE_V - SCHOTTKY_V)]
                self.v = self._solve(g, inl, c, h)
                if out.precharge_on and vin_ocv > 0:
                    ipre_sum += max(0.0, (vin_prev - D3_V - self.v) / rpre)
            self.i_pre = ipre_sum / SUBSTEPS
        # low-side shunt: whatever the drone draws, through the main switch or RPRE
        self.i_shunt = self.i_main if inp_gate else self.i_pre
        if self.v > self.max_drone_v and (out.main_on or out.precharge_on):
            self.max_drone_v = self.v
        self.drone_batt_energy += self.i_main * dt
        # thermal: FET (8 K/W, 40 s), RPRE (2 J/K, 30 s cooling)
        p_fet = self.i_main ** 2 * SWITCH_OHM
        self.t_fet += ((self.t_amb + 8.0 * p_fet) - self.t_fet) * (dt / 40.0)
        p_pre = self.i_pre ** 2 * rpre
        self.t_rpre += p_pre * dt / 2.0 - (self.t_rpre - self.t_amb) * (dt / 30.0)
        self.t_ms += dt_ms

    def _solve(self, g, inl, c, h):
        """Exact first-order step for the linear part, nonlinear current held."""
        d = self.drone
        rev = d is not None and d.reversed
        for diode_on in ((False, True) if rev else (False,)):
            gg = list(g)
            if diode_on:
                gg.append((1.0 / d.diode_ohm, d.diode_v))
            gs = sum(x for x, _ in gg)
            if gs <= 0:
                v = self.v - inl * h / c
            else:
                vinf = (sum(x * vs for x, vs in gg) - inl) / gs
                tau = c / gs
                v = vinf + (self.v - vinf) * math.exp(-h / tau)
            if not rev or diode_on or v <= d.diode_v:
                break
        has_neg_source = d is not None and d.battery is not None and d.battery[0] < 0
        return v if has_neg_source else max(v, 0.0)


class Rig:
    """A World plus a Machine, stepped together."""

    def __init__(self, world, machine=None, dt_ms=1):
        self.w = world
        self.m = machine or Machine()
        self.dt = dt_ms
        self.out = None
        self.awake = False
        self.states = []           # state after each tick (deduplicated)
        self.screens = []          # screen ids seen (deduplicated)
        self.beeps = []
        self.ever_main = False     # MCU_EN ever asserted
        self.ever_pre = False      # pre-charge FET ever on
        self.ever_probe = False
        self.main_edges = 0        # number of separate main-switch closures
        self.ever_main_prev = False

    def tick(self, dt=None):
        dt = dt or self.dt
        if not self.w.powered():
            if self.awake:
                self.m.reset()
            self.awake = False
            from .machine import Outputs
            self.out = Outputs(divider_en=False)
            self.out.screen.id = 'dark'
            self.ever_main_prev = False
            self.w.apply(self.out, dt)
            self._log('dark', 'dark')
            return self.out
        if not self.awake:
            self.m.reset()
            self.awake = True
        inp = self.w.sense()
        self.out = self.m.step(inp)
        if self.out.main_on and not self.ever_main_prev:
            self.main_edges += 1
        self.ever_main_prev = self.out.main_on
        self.ever_main |= self.out.main_on
        self.ever_pre |= self.out.precharge_on
        self.ever_probe |= self.out.probe_src != ProbeSrc.OFF
        if self.out.beep:
            self.beeps.append(self.out.beep)
        self.w.apply(self.out, dt)
        self._log(self.m.state, self.out.screen.id)
        return self.out

    def _log(self, state, screen):
        if not self.states or self.states[-1] != state:
            self.states.append(state)
        if not self.screens or self.screens[-1] != screen:
            self.screens.append(screen)

    def run(self, ms, dt=None):
        dt = dt or self.dt
        for _ in range(int(ms // dt)):
            self.tick(dt)
        return self.out

    def run_until(self, pred, max_ms, dt=None):
        dt = dt or self.dt
        n = 0
        while n < max_ms:
            self.tick(dt)
            n += dt
            if pred(self):
                return True
        return False

    # human verbs
    def boot(self):
        self.run(1600)
        return self

    def open_guard(self, ms=50):
        self.w.guard_closed = False
        self.run(ms)

    def close_guard(self, ms=50):
        self.w.guard_closed = True
        if self.w.cam_works:
            self.w.toggle = Toggle.OFF
        self.run(ms)

    def on(self, ms=10):
        self.w.toggle = Toggle.ON
        self.run(ms)

    def off(self, ms=10):
        self.w.toggle = Toggle.OFF
        self.run(ms)

    def bind(self, hold_ms=300):
        self.w.toggle = Toggle.BIND
        self.run(hold_ms)
        self.w.toggle = Toggle.OFF
        self.run(10)

    def press(self, which, hold_ms=60, gap_ms=60):
        setattr(self.w, which, True)
        self.run(hold_ms)
        setattr(self.w, which, False)
        self.run(gap_ms)

    def plus(self, **kw):
        self.press('plus', **kw)

    def minus(self, **kw):
        self.press('minus', **kw)

    def go_live(self, max_ms=2500):
        """Open the guard and flick on; run until LIVE/WARNING or ABORT."""
        self.open_guard()
        self.w.toggle = Toggle.ON
        self.run_until(lambda r: r.m.state in (State.LIVE, State.WARNING, State.ABORT), max_ms)
        return self.m.state

    @property
    def state(self):
        return self.m.state

    @property
    def screen(self):
        return self.out.screen
