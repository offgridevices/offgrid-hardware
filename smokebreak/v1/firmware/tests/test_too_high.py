"""Over-voltage refusal (machine rule 5, State.TOO_HIGH): a pack above 14S
LiHV on the main input, or a VIN reading at the ADC's full scale."""
import pytest

from model import battery, limits
from model.inputs import ADC_VIN_MAX_MV, Inputs, Toggle
from model.machine import (Fault, Led, Machine, ProbeSrc, State, VIN_FULL_SCALE_MV, VIN_TOO_HIGH_MV,
                           vin_too_high)
from model.sim_world import Balance, Drone, Pack, Rig, World

LIHV_14S_MV = 14 * 4350


# ---------------------------------------------------------------- the threshold

def test_threshold_sits_between_14s_lihv_with_tolerance_and_the_tvs():
    assert LIHV_14S_MV == 60900
    assert LIHV_14S_MV * 1024 // 1000 < VIN_TOO_HIGH_MV        # 1.9 % divider + 0.5 % ADC: never a real pack
    assert VIN_TOO_HIGH_MV < 64000                              # SMBJ64CA stand-off
    assert 15 * 4200 >= VIN_TOO_HIGH_MV                         # a full 15S LiPo is refused
    assert VIN_TOO_HIGH_MV < VIN_FULL_SCALE_MV < ADC_VIN_MAX_MV


@pytest.mark.parametrize('mv, high', [
    (LIHV_14S_MV, False), (VIN_TOO_HIGH_MV - 1, False), (VIN_TOO_HIGH_MV, True), (VIN_TOO_HIGH_MV + 1, True),
    (VIN_FULL_SCALE_MV - 1, True), (VIN_FULL_SCALE_MV, True), (ADC_VIN_MAX_MV, True), (0, False)])
def test_vin_too_high_boundaries(mv, high):
    assert vin_too_high(mv) == high


# ---------------------------------------------------------------- exact boundaries through the machine

class Bench:
    """Machine fed hand-made samples, 1 ms apart (exact mV, no plant)."""

    def __init__(self, vin_mv, guard_closed=True, usb=True):
        self.m = Machine()
        self.t = 0
        self.inp = Inputs(vin_mv=vin_mv, guard_closed=guard_closed, usb_present=usb)
        self.out = None
        self.ever_on = False

    def run(self, ms, **changes):
        for k, v in changes.items():
            setattr(self.inp, k, v)
        for _ in range(ms):
            self.inp.t_ms = self.t
            self.out = self.m.step(self.inp)
            self.ever_on |= self.out.main_on or self.out.precharge_on or self.out.probe_src != ProbeSrc.OFF
            self.t += 1
        return self.out


@pytest.mark.parametrize('mv, refused', [
    (VIN_TOO_HIGH_MV - 1, False), (VIN_TOO_HIGH_MV, True), (VIN_TOO_HIGH_MV + 1, True), (ADC_VIN_MAX_MV, True)])
def test_at_just_below_and_just_above_the_threshold(mv, refused):
    b = Bench(mv)
    b.run(2000)
    assert (b.m.state == State.TOO_HIGH) == refused
    if refused:
        assert b.m.fault == Fault.TOO_HIGH and b.out.screen.id == 'S08'
        assert b.out.led == Led.RED_FLASH and b.out.beep_loop == 'alarm'
    else:
        assert b.m.state == State.SAFE and b.out.screen.id != 'S08'


def test_refused_from_the_first_tick_no_startup_wait():
    b = Bench(VIN_TOO_HIGH_MV + 500)
    b.run(1)
    assert b.m.state == State.TOO_HIGH and b.out.screen.data['value'] == '63.0 V'
    assert b.out.screen.data['vin_mv'] == 63000 and not b.out.screen.data['full_scale']


def test_adc_full_scale_reads_as_over_66_v():
    b = Bench(ADC_VIN_MAX_MV)
    b.run(10)
    d = b.out.screen.data
    assert b.m.state == State.TOO_HIGH and d['full_scale'] and d['value'] == 'over 66.0 V'


def test_cannot_arm_while_refused_whatever_the_guard_and_toggle_do():
    b = Bench(64000)
    b.run(2000)
    b.run(200, guard_closed=False)
    b.run(200, toggle=Toggle.OFF)
    b.run(500, toggle=Toggle.ON)
    b.run(200, toggle=Toggle.OFF)
    b.run(500, toggle=Toggle.BIND)
    b.run(200, toggle=Toggle.OFF, guard_closed=True)
    b.run(1500)
    b.run(200, guard_closed=False)
    b.run(500, toggle=Toggle.ON)
    assert b.m.state == State.TOO_HIGH and not b.ever_on


def test_rocker_is_ignored_while_refused():
    b = Bench(64000)
    b.run(2000)
    for _ in range(5):
        b.run(60, btn_plus=True)
        b.run(60, btn_plus=False)
    assert b.m.limit.idx == limits.AUTO and b.out.screen.id == 'S08'


def test_latched_until_unplugged_not_by_a_lower_reading():
    b = Bench(63000)
    b.run(100)
    b.run(500, vin_mv=VIN_TOO_HIGH_MV - 2000)          # still a pack on the input: stays refused
    assert b.m.state == State.TOO_HIGH
    assert b.out.screen.data['vin_mv'] == 63000         # the reading that was refused
    b.run(10, vin_mv=battery.VIN_PRESENT_MV)            # not yet gone
    assert b.m.state == State.TOO_HIGH
    b.run(10, vin_mv=battery.VIN_PRESENT_MV - 1)        # unplugged
    assert b.m.state == State.SAFE and b.m.fault == Fault.NONE and not b.ever_on


def test_unplugged_with_guard_open_and_toggle_on_needs_off_first():
    b = Bench(63000, guard_closed=False)
    b.run(100, toggle=Toggle.ON)
    b.run(100, vin_mv=0)
    assert b.m.state == State.ARMED
    b.run(500, vin_mv=16000)                             # a good pack, toggle still ON
    assert b.m.state == State.ARMED and b.out.screen.data['hint'] == 'switch_off_first' and not b.ever_on
    b.run(50, toggle=Toggle.OFF)
    b.run(5, toggle=Toggle.ON)
    assert b.m.state == State.CHECKING


# ---------------------------------------------------------------- end to end (plant)

def test_15s_pack_refused_end_to_end():
    r = Rig(World(pack=Pack.of(15, 4.2), drone=Drone.quad())).boot()
    assert r.state == State.TOO_HIGH and r.screen.id == 'S08'
    assert r.screen.data['title'] == 'Battery voltage too high' and r.screen.data['value'] == '63.0 V'
    assert r.out.beep_loop == 'alarm' and 'alarm' in r.beeps
    assert r.go_live() == State.TOO_HIGH
    r.run(2000)
    assert not r.ever_probe and not r.ever_pre and not r.ever_main and r.w.max_drone_v == 0


def test_16s_pack_saturates_the_adc_and_is_refused():
    r = Rig(World(pack=Pack.of(16, 4.2), drone=Drone.quad())).boot()      # 67.2 V, ADC tops out at 66 V
    assert r.m.batt.vin_mv == ADC_VIN_MAX_MV
    assert r.state == State.TOO_HIGH and r.screen.data['value'] == 'over 66.0 V'
    r.go_live()
    assert not r.ever_pre and not r.ever_main


def test_overcharged_14s_just_below_is_not_refused():
    r = Rig(World(pack=Pack.of(14, 4.46), drone=Drone.quad(cap_uf=2200))).boot()   # 62.44 V
    assert r.state == State.SAFE
    assert r.go_live() in (State.LIVE, State.WARNING)


def test_refusal_clears_on_unplug_then_a_good_pack_arms():
    r = Rig(World(pack=Pack.of(15, 4.2), drone=Drone.quad(), usb=True)).boot()
    r.open_guard()
    r.on(500)
    assert r.state == State.TOO_HIGH
    r.off()
    r.w.pack = None
    r.run(50)
    assert r.state == State.ARMED and r.m.fault == Fault.NONE
    r.w.pack = Pack.of(4, 4.0)
    r.run(50)
    assert r.go_live() == State.LIVE and r.ever_main


def test_refusal_clears_when_the_box_goes_dark():
    r = Rig(World(pack=Pack.of(15, 4.2), drone=Drone.quad())).boot()
    assert r.state == State.TOO_HIGH
    r.w.pack = None
    r.run(100)
    assert r.screen.id == 'dark'
    r.w.pack = Pack.of(6, 4.1)
    r.boot()
    assert r.state == State.SAFE and r.go_live() == State.LIVE


def test_guard_close_does_not_clear_it():
    r = Rig(World(pack=Pack.of(15, 4.2), drone=Drone.quad())).boot()
    r.open_guard()
    r.close_guard(1500)
    assert r.state == State.TOO_HIGH and r.screen.id == 'S08'


def test_input_rising_over_the_limit_while_live_cuts_at_once():
    r = Rig(World(pack=Pack.of(14, 4.2), drone=Drone.quad(), usb=True)).boot()
    assert r.go_live() == State.LIVE
    r.w.pack = Pack.of(15, 4.2)                          # (a swap the plant allows in one tick)
    r.tick()
    assert r.state == State.TOO_HIGH and not r.out.main_on and not r.out.precharge_on


def test_no_pack_question_on_a_refused_pack():
    r = Rig(World(pack=Pack.of(15, 4.2), drone=Drone.quad(), balance=None)).boot()
    r.run(8000)
    assert r.m.prompt is None and r.m.packs.packs == []
