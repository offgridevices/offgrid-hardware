"""The Arm flow, S00-S13 (SPEC §6), including abusive sequences."""
from conftest import make_rig
from model import limits
from model.inputs import Toggle
from model.machine import Led, ProbeSrc, State
from model.sim_world import Drone, Pack, Rig, World


def test_startup_shows_mark_then_safe():
    r = make_rig(balance=False)
    r.run(100)
    assert r.screen.id == 'S00' and r.out.led == Led.OFF and not r.out.main_on
    r.run(1500)
    assert r.state == State.SAFE and r.screen.id == 'S01'
    assert r.screen.data['vin_mv'] == 16000 and r.screen.data['cells'] == 4
    assert r.out.led == Led.EMBER_DIM


def test_happy_path_screens_leds_and_beeps_in_order():
    r = make_rig(balance=False).boot()
    r.open_guard()
    assert r.state == State.ARMED and r.screen.id == 'S02' and r.out.led == Led.EMBER_PULSE
    assert 'arm' in r.beeps
    r.on(5)
    assert r.state == State.CHECKING and r.out.led == Led.WHITE and r.out.probe_src == ProbeSrc.R1K
    r.run_until(lambda x: x.state == State.LIVE, 1000)
    r.run(700)
    assert r.screens[r.screens.index('S02'):] == ['S02', 'S03', 'S04', 'S05', 'S06']
    assert r.out.led == Led.GREEN and r.out.main_on and not r.out.precharge_on
    assert r.out.probe_src == ProbeSrc.OFF
    assert 'engage' in r.beeps and 'tick' in r.beeps
    assert abs(r.screen.data['ma'] - 350) < 20      # INA290 auto-zeroed (sim offset 12 mA)


def test_check_takes_about_a_third_of_a_second_and_nothing_powered_meanwhile():
    r = make_rig().boot()
    r.open_guard()
    r.w.toggle = Toggle.ON
    for _ in range(300):
        r.tick()
        assert not r.out.main_on and not r.out.precharge_on
    assert r.state == State.CHECKING


def test_toggle_off_turns_drone_off():
    r = make_rig().boot()
    assert r.go_live() == State.LIVE
    r.off()
    assert r.state == State.ARMED and not r.out.main_on and 'cut' in r.beeps


def test_guard_close_while_live_is_power_cut_then_safe():
    r = make_rig().boot()
    r.go_live()
    r.w.guard_closed = True
    r.w.toggle = Toggle.OFF
    r.tick()
    assert not r.out.main_on and r.state == State.POWER_CUT and r.screen.id == 'S12'
    r.run(1300)
    assert r.state == State.SAFE


def test_flicking_on_with_guard_closed_does_nothing():
    r = make_rig().boot()
    r.w.toggle = Toggle.ON              # (cam broken / forced)
    r.run(500)
    assert r.state == State.SAFE and not r.ever_probe
    r.open_guard(500)
    assert r.state == State.ARMED and r.screen.data['hint'] == 'switch_off_first'
    assert not r.ever_probe and not r.ever_main
    r.off(20)
    r.on()
    r.run_until(lambda x: x.state == State.LIVE, 1000)
    assert r.state == State.LIVE


def test_toggle_left_on_while_guard_closes_and_opens_again_never_auto_powers():
    r = make_rig().boot()
    r.go_live()
    r.w.cam_works = False
    r.close_guard(1500)                 # toggle stays ON
    assert r.state == State.SAFE and r.w.toggle == Toggle.ON
    r.open_guard(3000)
    assert r.state == State.ARMED and not r.out.main_on and not r.out.precharge_on
    assert r.out.probe_src == ProbeSrc.OFF


def test_guard_closing_mid_precharge_cuts_the_same_tick():
    r = Rig(World(pack=Pack.of(14, 4.2), drone=Drone.quad(cap_uf=5000))).boot()
    r.open_guard()
    r.w.toggle = Toggle.ON
    r.run_until(lambda x: x.state == State.PRECHARGE, 1000)
    r.run(30)
    assert r.out.precharge_on
    r.w.guard_closed = True
    r.tick()
    assert not r.out.precharge_on and not r.out.main_on and r.state == State.POWER_CUT


def test_guard_closing_mid_check_stops_the_probe():
    r = make_rig().boot()
    r.open_guard()
    r.on(100)
    assert r.out.probe_src != ProbeSrc.OFF
    r.w.guard_closed = True
    r.tick()
    assert r.out.probe_src == ProbeSrc.OFF and r.state == State.POWER_CUT


def test_bind_pulled_mid_check_cancels_and_does_not_bind():
    r = make_rig().boot()
    r.open_guard()
    r.on(100)
    r.w.toggle = Toggle.BIND             # straight from ON (the OFF pass was missed)
    r.run(400)
    assert r.state == State.ARMED and not r.ever_main and not r.ever_pre
    r.w.toggle = Toggle.OFF              # realistic: through OFF, quickly
    r.run(20)
    r.w.toggle = Toggle.BIND
    r.run(400)
    assert r.state == State.ARMED and not r.ever_pre


def test_bind_three_short_power_cycles_then_stays_on():
    r = make_rig().boot()
    r.open_guard(400)
    r.bind(300)                           # pull and let it spring back
    assert r.screen.id in ('S03', 'S04', 'S10')
    on_ms, cur = [], 0
    for _ in range(8000):
        r.tick()
        if r.w.last_out.main_on:
            cur += 1
        elif cur:
            on_ms.append(cur)
            cur = 0
        if r.state == State.LIVE:
            break
    assert r.state == State.LIVE and r.m.bind_live
    assert r.main_edges == 4 and len(on_ms) == 3
    assert all(t < 2000 for t in on_ms)
    assert 'S10' in r.screens and r.screens.count('S10') >= 1
    r.run(2000)
    assert r.out.main_on                  # toggle sprang back to OFF: drone stays on after bind
    r.on()
    r.off()
    assert not r.out.main_on and r.state == State.ARMED


def test_bind_needs_the_guard_open():
    r = make_rig().boot()
    r.w.toggle = Toggle.BIND
    r.run(300)
    r.w.toggle = Toggle.OFF
    r.run(3000)
    assert r.state == State.SAFE and not r.ever_probe


def test_bind_led_blue():
    r = make_rig().boot()
    r.open_guard()
    r.bind()
    r.run_until(lambda x: x.state == State.BIND, 1000)
    assert r.out.led == Led.BLUE and r.screen.id == 'S10'


def press_n(r, n, which='plus'):
    for _ in range(n):
        r.press(which, 60, 60)


def test_limit_picker_overlay_and_peak_threshold():
    r = make_rig().boot()
    press_n(r, 2)                         # AUTO -> 1 -> 2
    assert r.screen.id == 'S13' and r.screen.data['limit_ma'] == 2000
    assert r.out.peak_threshold_ma == 8000
    r.run(2100)
    assert r.screen.id != 'S13'


def test_25a_confirm_while_live_then_60s_back_to_10a():
    r = make_rig().boot()
    press_n(r, 4)                         # 10 A
    r.go_live()
    r.plus()
    assert r.screen.id == 'S11' and r.m.limit.confirm_pending
    r.run(500)
    r.plus()
    assert r.m.limit.motor_test and r.out.peak_threshold_ma == limits.PEAK_MAX_MA
    r.w.drone.demand_a = 20.0             # props off, motors spinning
    r.run(30_000, dt=10)
    assert r.state in (State.LIVE, State.WARNING)
    r.w.drone.demand_a = 0.0
    r.run(31_000, dt=10)
    assert r.m.limit.idx == limits.IDX_10A and not r.m.limit.motor_test


def test_25a_confirm_times_out_after_3s():
    r = make_rig().boot()
    press_n(r, 5)                         # 10 A, then + asks
    assert r.screen.id == 'S11'
    r.run(3100)
    assert not r.m.limit.confirm_pending and r.m.limit.idx == limits.IDX_10A
    assert r.screen.id != 'S11'


def test_rocker_mashing_while_live_never_arms_25a():
    r = make_rig().boot()
    r.go_live()
    for _ in range(40):
        r.press('plus', 30, 30)
        assert not r.m.limit.motor_test
    assert r.state == State.LIVE and r.out.main_on


def test_rocker_mashing_minus_and_both():
    r = make_rig().boot()
    for _ in range(10):
        r.press('minus', 20, 20)
    assert r.m.limit.idx == limits.AUTO
    r.w.plus = r.w.minus = True
    r.run(300)
    r.w.plus = r.w.minus = False
    r.run(50)
    assert r.m.limit.idx == limits.AUTO


def test_closing_the_guard_ends_motor_test():
    r = make_rig().boot()
    press_n(r, 4)
    r.go_live()
    r.plus()
    r.run(500)
    r.plus()
    assert r.m.limit.motor_test
    r.close_guard()
    assert r.m.limit.idx == limits.IDX_10A


def test_rocker_ignored_during_abort():
    r = make_rig(drone=Drone(cap_uf=1000, short_ohm=0.3)).boot()
    r.go_live()
    assert r.state == State.ABORT
    press_n(r, 3)
    assert r.m.limit.idx == limits.AUTO and r.screen.id == 'S08'


def test_fault_needs_guard_closed_and_toggle_cycle_does_not_clear_it():
    r = make_rig(drone=Drone(cap_uf=1000, short_ohm=0.3)).boot()
    r.go_live()
    assert r.state == State.ABORT and r.out.led == Led.RED_FLASH and r.out.beep_loop == 'alarm'
    r.off(500)
    r.on(500)
    assert r.state == State.ABORT and not r.ever_pre
    r.w.drone.short_ohm = 0.0            # fixed the short
    r.close_guard(1300)
    assert r.state == State.SAFE and r.out.beep_loop is None
    assert r.go_live() == State.LIVE


def test_startup_with_guard_open_and_toggle_on_does_not_power():
    w = World(pack=Pack.of(4, 4.0), drone=Drone.quad())
    w.guard_closed = False
    w.toggle = Toggle.ON
    r = Rig(w)
    r.run(4000)
    assert r.state == State.ARMED and not r.ever_probe


def test_battery_swapped_with_switch_left_on_does_not_auto_power():
    r = make_rig().boot()
    r.go_live()
    pack = r.w.pack
    r.w.pack = None
    r.w.balance = None
    r.run(3000)
    assert not r.out.main_on
    r.w.pack = pack
    r.run(3000)
    assert not r.out.main_on and not r.out.precharge_on
    assert r.state in (State.ARMED, State.ABORT)


def test_overcurrent_average_trip_message():
    r = make_rig().boot()
    press_n(r, 2)                         # 2 A
    r.go_live()
    r.run(700)
    r.w.drone.demand_a = 2.5
    r.run(400)
    assert r.state == State.ABORT and r.screen.id == 'S08'
    assert r.screen.data['title'] == 'Over 2.00 A for 0.2 s'
    assert not r.out.main_on


def test_esc_tones_pass_on_auto():
    r = make_rig().boot()
    r.go_live()
    r.run(700)
    for _ in range(6):                    # 60 ms beeps at 4 A, 300 ms apart
        r.w.drone.demand_a = 3.6
        r.run(60)
        r.w.drone.demand_a = 0.0
        r.run(240)
    assert r.state == State.LIVE


def test_peak_comparator_spike():
    r = make_rig().boot()
    r.go_live()
    r.run(700)
    r.w.drone.demand_a = 15.0             # over 4 x 3 A, under the driver trip
    r.run(5)
    assert r.state == State.ABORT and r.m.fault_data['threshold_ma'] == 12000
    assert r.screen.data['title'] == 'Spike over 12.0 A'


def test_short_while_live_hits_driver_trip():
    r = make_rig().boot()
    r.go_live()
    r.run(700)
    r.w.drone.short_ohm = 0.02
    r.run(5)
    assert r.state == State.ABORT and not r.out.main_on
    assert r.m.fault.name in ('SHORT_TRIP', 'OVERCURRENT_PEAK')


def test_overtemperature_cut():
    r = make_rig().boot()
    r.go_live()
    r.w.force_ntc_fet_dc = 1005
    r.run(5)
    assert r.state == State.ABORT and r.m.fault.name == 'OVERTEMP'


def test_precharge_stall_end_to_end_shows_where_it_stopped():
    r = make_rig(drone=Drone(cap_uf=1000, fault_ohm=3.0, fault_on_v=6.0)).boot()
    assert r.go_live() == State.ABORT
    assert r.m.fault.name == 'PRECHARGE_STALL' and not r.ever_main
    assert r.screen.data['title'] == 'Stopped while charging'
    assert ' V · ' in r.screen.data['value'] and r.screen.data['value'].endswith(' A')


def test_precharge_energy_budget_refuses_rapid_retries_at_14s():
    r = Rig(World(pack=Pack.of(14, 4.2), drone=Drone(cap_uf=1000, fault_ohm=3.0, fault_on_v=6.0))).boot()
    faults = []
    for _ in range(10):
        r.go_live()
        faults.append(r.m.fault.name)
        r.close_guard(1300)
    assert faults[0] == 'PRECHARGE_STALL' and 'PRECHARGE_BUDGET' in faults
