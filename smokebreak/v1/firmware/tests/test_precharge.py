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
    out = Outputs(precharge_on=True, rpre_mohm=sup.rpre)
    t = 0
    while t < ms and sup.status == pc.Status.RUNNING:
        w.apply(out, 1)
        t += 1
        i = w.sense()
        sup.step(t, i.vin_mv, i.vout_mv, i.ntc_rpre_dc)
    return sup, t


def test_resistor_choice_follows_vin():
    assert pc.rpre_for(4 * 4200) == pc.RPRE_LOW_MOHM
    assert pc.rpre_for(7 * 4350) == pc.RPRE_LOW_MOHM       # 7S LiHV still on 2 Ohm
    assert pc.rpre_for(8 * 3900) == pc.RPRE_HIGH_MOHM


def test_passes_at_75_percent_6s_2000uf():
    sup, t = ramp(6, Drone.quad(cap_uf=2000))
    assert sup.status == pc.Status.PASS
    assert sup.stop_vout_mv * 1000 >= sup.stop_vin_mv * 750
    assert t < 50


def test_14s_5000uf_passes_inside_1s_and_budget():
    sup, t = ramp(14, Drone.quad(cap_uf=5000), v=4.35)
    assert sup.status == pc.Status.PASS
    assert sup.rpre == pc.RPRE_HIGH_MOHM
    assert t < pc.TIMEOUT_MS
    assert 8_000_000 < sup.energy_uj < 12_000_000   # ~8.7 J for the caps + the idle load


def test_digital_vtx_switching_on_part_way_still_passes():
    # 22 Ohm at 14S leaves ~0.69 A at 75 %: a 15 W VTX plus 0.15 A of FC/RX fits
    for cells, v, idle in ((6, 4.2, 0.4), (14, 4.35, 0.15)):
        sup, _ = ramp(cells, Drone(cap_uf=1000, idle_a=idle, vtx_w=15.0, vtx_on_v=8.0), v=v)
        assert sup.status == pc.Status.PASS, cells


def test_load_too_big_for_22_ohm_stalls_and_says_where():
    sup, _ = ramp(14, Drone(cap_uf=1000, idle_a=0.6, vtx_w=15.0, vtx_on_v=8.0), v=4.35)
    assert sup.reason == pc.Reason.STALL and 5000 < sup.stop_vout_mv < 45700 and sup.stop_ma > 500


def test_stall_when_fault_appears_at_higher_voltage():
    # a 5 V part across battery voltage: 3 Ohm appears above 6 V
    sup, t = ramp(4, Drone(cap_uf=1000, fault_ohm=3.0, fault_on_v=6.0))
    assert sup.status == pc.Status.ABORT and sup.reason == pc.Reason.STALL
    assert 6000 < sup.stop_vout_mv < 12600
    assert sup.stop_ma > 1000                # reports the current it stopped at
    assert t < 200


def test_current_is_computed_from_resistor_drop():
    sup = pc.Supervisor(0, 16800, pc.EnergyLedger(), rpre_mohm=2000)
    assert sup.current_ma(16800, 8800) == 4000


def test_timeout_after_1s_on_a_slow_climb():
    sup = pc.Supervisor(0, 20000, pc.EnergyLedger(), rpre_mohm=22000)
    v = 0
    for t in range(1, 1100):
        v += 14                              # 0.42 V per 30 ms: rising, never stalls, never reaches 15 V
        if sup.step(t, 20000, v) != pc.Status.RUNNING:
            break
    assert sup.reason == pc.Reason.TIMEOUT
    assert t == pc.TIMEOUT_MS


def test_energy_budget_per_attempt():
    sup = pc.Supervisor(0, 60000, pc.EnergyLedger(), rpre_mohm=500)
    v = 0
    for t in range(1, 200):
        v += 400
        if sup.step(t, 60000, v) != pc.Status.RUNNING:
            break
    assert sup.reason == pc.Reason.ENERGY


def test_energy_budget_per_minute_and_recovery():
    led = pc.EnergyLedger()
    led.add(0, 15_000_000)
    led.add(1000, 15_000_000)
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
