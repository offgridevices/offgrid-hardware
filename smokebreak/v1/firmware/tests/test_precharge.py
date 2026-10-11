"""Pre-charge supervisor (SPEC §4 stage 2, §14.1)."""
from model import precharge as pc
from model.machine import Outputs
from model.sim_world import Drone, Pack, World


def ramp(pack_cells, drone, v=4.2, ms=1200, ledger=None):
    """Run the supervisor against the simulated plant with the pre-charge on."""
    w = World(pack=Pack.of(pack_cells, v), drone=drone, usb=True)
    w.guard_closed = False
    led = ledger or pc.EnergyLedger()
    sup = pc.Supervisor(0, int(w.vin() * 1000), led)
    out = Outputs(precharge_on=True)
    t = 0
    while t < ms and sup.status == pc.Status.RUNNING:
        w.apply(out, 1)
        t += 1
        i = w.sense()
        sup.step(t, i.vin_mv, i.vout_mv, i.ntc_rpre_dc)
    return sup, t


def test_one_resistor_bank_for_every_pack():
    # circuit.py: R_PRE || R_PRE2, 2 x 15 Ohm 5 W = 7.5 Ohm, 1S-14S; no bank select
    assert pc.RPRE_MOHM == 7500
    assert not hasattr(pc, 'rpre_for') and not hasattr(pc, 'RPRE_HIGH_MOHM')
    for vin in (4200, 16800, 30450, 33600, 60900):
        assert pc.Supervisor(0, vin, pc.EnergyLedger()).rpre == pc.RPRE_MOHM


def test_settles_then_passes_with_a_small_gap_6s_2000uf():
    sup, t = ramp(6, Drone.quad(cap_uf=2000))
    assert sup.status == pc.Status.PASS
    assert sup.gap_mv <= pc.CLOSE_GAP_MAX_MV
    assert sup.stop_vout_mv * 1000 >= sup.stop_vin_mv * 750      # well past 75 % (SIM.md 1(a))
    assert pc.SETTLE_WINDOW_MS <= t < 200


def test_14s_5000uf_passes_inside_1s_and_budget():
    sup, t = ramp(14, Drone.quad(cap_uf=5000), v=4.35)
    assert sup.status == pc.Status.PASS and sup.rpre == pc.RPRE_MOHM
    assert t < pc.TIMEOUT_MS
    assert 8_000_000 < sup.energy_uj < pc.ATTEMPT_BUDGET_UJ   # ~9.3 J for the caps + the idle load


def test_digital_vtx_switching_on_part_way_still_passes():
    # SIM.md case 1(a): 7.5 Ohm gets a 15 W VTX past its UVLO at 8S-14S;
    # case 1(b): a 10 W VTX on a full 6S
    for cells, v, idle, vtx in ((6, 4.2, 0.4, 10.0), (8, 3.7, 0.1, 15.0), (14, 4.35, 0.15, 15.0)):
        sup, _ = ramp(cells, Drone(cap_uf=1000, idle_a=idle, vtx_w=vtx, vtx_on_v=8.0), v=v)
        assert sup.status == pc.Status.PASS, cells
        assert sup.gap_mv <= pc.CLOSE_GAP_MAX_MV


def test_vtx_stuck_at_uvlo_with_small_gap_closes():
    # SIM.md case 1(b): 4S at 4.35 V/cell, 10 W VTX stuck at its 6 V UVLO:
    # stall at ~6 V, 11.4 V gap, inside the 12 V close rule -> close
    sup, _ = ramp(4, Drone(cap_uf=2200, idle_a=0.17, vtx_w=10.0, vtx_on_v=6.0), v=4.35)
    assert sup.status == pc.Status.PASS
    assert 5500 < sup.stop_vout_mv < 6500 and 10_000 < sup.gap_mv <= pc.CLOSE_GAP_MAX_MV


def test_gap_over_12v_is_refused_6s_3v5_10w_vtx():
    # SIM.md case 1(b): 6S at 3.5 V/cell + 10 W VTX (+FC/RX) ends at a 14.9 V
    # gap -> refused, the main switch never closes across it
    sup, _ = ramp(6, Drone(cap_uf=2200, idle_a=0.35, vtx_w=10.0, vtx_on_v=6.0), v=3.5)
    assert sup.status == pc.Status.ABORT and sup.reason == pc.Reason.STALL
    assert 14_000 < sup.gap_mv < 16_000 and 5500 < sup.stop_vout_mv < 6500
    assert sup.stop_ma > 1500


def test_close_gap_boundary():
    for gap, ok in ((pc.CLOSE_GAP_MAX_MV, True), (pc.CLOSE_GAP_MAX_MV + 1, False)):
        sup = pc.Supervisor(0, 30000, pc.EnergyLedger())
        t = 0
        while sup.status == pc.Status.RUNNING:
            t += 1
            sup.step(t, 30000, 30000 - gap)          # flat: settled from the start
        assert (sup.status == pc.Status.PASS) == ok, gap
        assert t <= pc.SETTLE_WINDOW_MS + 1      # decided as soon as one full window is seen


def test_still_rising_is_not_settled():
    sup = pc.Supervisor(0, 20000, pc.EnergyLedger())
    v = 10000
    for t in range(1, 100):
        v += 15                                  # 0.3 V per 20 ms > 1 % of 20 V: still charging
        assert sup.step(t, 20000, v) == pc.Status.RUNNING


def test_load_too_big_stalls_and_says_where():
    # 15 W VTX from 8 V on a full 6S with 0.4 A of FC/RX: 7.5 Ohm cannot get it
    # past 8 V, and 17 V would be left across the switch -> refused
    sup, _ = ramp(6, Drone(cap_uf=1000, idle_a=0.4, vtx_w=15.0, vtx_on_v=8.0))
    assert sup.reason == pc.Reason.STALL and 7000 < sup.stop_vout_mv < 9000 and sup.stop_ma > 2000
    assert sup.gap_mv > pc.CLOSE_GAP_MAX_MV


def test_stall_when_fault_appears_at_higher_voltage():
    # a 5 V part across battery voltage: 3 Ohm appears above 6 V.  At 8S the
    # node stalls far below VIN: refused before the main switch closes
    sup, t = ramp(8, Drone(cap_uf=1000, fault_ohm=3.0, fault_on_v=6.0))
    assert sup.status == pc.Status.ABORT and sup.reason == pc.Reason.STALL
    assert 6000 < sup.stop_vout_mv < 12000
    assert sup.stop_ma > 1000                # reports the current it stopped at
    assert t < 200


def test_fault_at_higher_voltage_on_4s_is_left_to_the_live_limiter():
    # the same fault on 4S stalls with < 12 V across RPRE: the close rule allows
    # it (it cannot tell it from a VTX at its UVLO); the current limit then trips
    # (test_flow.test_fault_under_12v_gap_closes_then_limit_trips)
    sup, _ = ramp(4, Drone(cap_uf=1000, fault_ohm=3.0, fault_on_v=6.0))
    assert sup.status == pc.Status.PASS and sup.gap_mv <= pc.CLOSE_GAP_MAX_MV


def test_current_is_computed_from_resistor_drop():
    sup = pc.Supervisor(0, 16800, pc.EnergyLedger())
    assert sup.current_ma(16800, 8800) == 1066          # 8 V across 7.5 Ohm


def test_timeout_after_1s_on_a_slow_climb():
    sup = pc.Supervisor(0, 20000, pc.EnergyLedger(), rpre_mohm=100000)
    v = 0
    for t in range(1, 1100):
        v += 14                              # 0.28 V per 20 ms: rising (> 1 % of VIN), never settles
        if sup.step(t, 20000, v) != pc.Status.RUNNING:
            break
    assert sup.reason == pc.Reason.TIMEOUT
    assert t == pc.TIMEOUT_MS


def test_energy_budget_per_attempt_is_12j():
    # SIM.md case 1(c): abort at 12 J per attempt (6 J per resistor)
    assert pc.ATTEMPT_BUDGET_UJ == 12_000_000
    sup = pc.Supervisor(0, 60000, pc.EnergyLedger())
    v = 0
    for t in range(1, 200):
        v += 300                             # rising: never settles
        if sup.step(t, 60000, v) != pc.Status.RUNNING:
            break
    assert sup.reason == pc.Reason.ENERGY
    assert pc.ATTEMPT_BUDGET_UJ < sup.energy_uj < pc.ATTEMPT_BUDGET_UJ + 500_000
    # the previous, larger per-attempt budget would have let it run on
    assert t < 45


def test_attempt_under_12j_is_not_cut():
    sup = pc.Supervisor(0, 60000, pc.EnergyLedger())
    for t in range(1, 37):                   # ~11 J: ~48 V across 7.5 Ohm for 36 ms, still rising
        sup.step(t, 60000, 10000 + t * 40)
    assert sup.status == pc.Status.RUNNING and 10_000_000 < sup.energy_uj < pc.ATTEMPT_BUDGET_UJ


def test_energy_budget_per_minute_and_recovery():
    led = pc.EnergyLedger()
    led.add(0, 20_000_000)
    led.add(1000, 20_000_000)
    sup = pc.Supervisor(2000, 50000, led)
    assert sup.can_start(250) == pc.Reason.BUDGET
    assert 0 < led.wait_ms(2000) <= pc.MINUTE_MS
    later = pc.Supervisor(61_001, 50000, led)
    assert later.can_start(250) == pc.Reason.NONE


def test_hot_resistor_refuses():
    sup = pc.Supervisor(0, 16800, pc.EnergyLedger())
    assert sup.can_start(pc.RPRE_HOT_DC) == pc.Reason.HOT


def test_input_collapse_during_ramp():
    sup = pc.Supervisor(0, 16800, pc.EnergyLedger())
    sup.step(1, 16800, 1000)
    sup.step(2, 10000, 1200)
    assert sup.reason == pc.Reason.COLLAPSE


def test_attempt_energy_is_booked_once():
    led = pc.EnergyLedger()
    sup, _ = ramp(4, Drone.quad(), ledger=led)
    sup.close()
    assert len(led.entries) == 1 and led.entries[0][1] == sup.energy_uj
