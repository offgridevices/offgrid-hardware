"""1S..14S end to end, drone memory end to end, AUTO limit in use."""
import pytest

from conftest import make_rig
from model import limits, memory
from model.machine import Machine, State, fmt_v
from model import precharge as pc
from model.sim_world import Balance, Drone, Pack, Rig, World


def drone_for(cells):
    if cells == 1:
        return Drone.whoop_1s()
    if cells <= 7:
        return Drone(cap_uf=1000, idle_a=0.3, vtx_w=8.0)
    return Drone(cap_uf=3300, idle_a=0.1, vtx_w=4.0)      # heavy-lift: VTX on its own BEC


def test_8s_with_15w_vtx_goes_live_on_7_5_ohm():
    """The old 22 Ohm bank stalled here (~9.6 W at 75 % of 8S); the single
    7.5 Ohm bank gets a 15 W VTX past its UVLO at 8S (SIM.md case 1(a))."""
    w = World(pack=Pack.of(8, 4.2), drone=Drone(cap_uf=1000, idle_a=0.1, vtx_w=15.0))
    r = Rig(w).boot()
    assert r.go_live() == State.LIVE
    assert r.ever_main


def test_6s_at_3v5_with_10w_vtx_is_refused_not_closed_across_15v():
    """SIM.md case 1(b): the VTX sits at its 6 V UVLO, ~14.9 V would be left
    across the main switch (> 12 V, outside its SOA): refused, with where."""
    w = World(pack=Pack.of(6, 3.5), drone=Drone(cap_uf=2200, idle_a=0.35, vtx_w=10.0, vtx_on_v=6.0))
    r = Rig(w).boot()
    assert r.go_live() == State.ABORT and r.m.fault.name == 'PRECHARGE_STALL'
    assert not r.ever_main
    d = r.m.fault_data
    assert d['vin_mv'] - d['vout_mv'] > pc.CLOSE_GAP_MAX_MV
    assert 5500 <= d['vout_mv'] <= 6500 and 14_000 <= d['vin_mv'] - d['vout_mv'] <= 16_000
    assert r.screen.data['title'] == 'Drone draws power at ' + fmt_v(d['vout_mv'])
    assert r.screen.data['value'].startswith(fmt_v(d['vin_mv'] - d['vout_mv']) + ' gap · ')


@pytest.mark.parametrize('cells', range(1, 15))
def test_full_pack_goes_live(cells):
    w = World(pack=Pack.of(cells, 4.2), drone=drone_for(cells), balance=Balance() if cells <= 8 else None)
    r = Rig(w).boot()
    assert r.go_live() == State.LIVE, (r.m.fault, r.m.fault_data)
    assert r.m.cells == cells
    r.run(700)
    assert r.screen.id == 'S06'
    assert r.m.ledger.entries


def test_1s_whoop_auto_limit_is_1a():
    r = Rig(World(pack=Pack.of(1, 4.2), drone=Drone.whoop_1s())).boot()
    r.go_live()
    assert r.state == State.LIVE
    assert r.m._active_limit_ma() == 1000 and r.out.peak_threshold_ma == 4000


def test_new_multi_cell_drone_auto_limit_is_3a():
    r = make_rig().boot()
    r.go_live()
    assert r.m._active_limit_ma() == 3000 and r.out.peak_threshold_ma == 12000


def test_14s_heavy_lift_5000uf_with_vtx():
    w = World(pack=Pack.of(14, 4.35), drone=Drone(cap_uf=5000, idle_a=0.15, vtx_w=15.0))
    r = Rig(w).boot()
    assert r.go_live() == State.LIVE
    # SIM.md case 1(c): ~10.6 J, inside the 12 J per-attempt abort
    assert 8_000_000 < r.m.ledger.entries[-1][1] < pc.ATTEMPT_BUDGET_UJ


def test_drone_memory_end_to_end_same_then_draws_more():
    m = Machine()
    w = World(pack=Pack.of(4, 4.0), drone=Drone.quad(idle_a=0.42))
    r = Rig(w, m).boot()
    # visit 1: new drone, idle learnt at 10 s
    r.go_live()
    assert r.m.visit.new
    r.run(10_500, dt=10)
    assert r.m.visit.profile.idle_ma == pytest.approx(420, abs=15)
    r.off(400)
    r.w.v = 0.0                           # unplugged and plugged back in: caps discharged
    # visit 2: recognised, same as last time, AUTO now 1.5x idle / idle + 0.5 A
    r.on()
    r.run_until(lambda x: x.state == State.LIVE, 1000)
    assert not r.m.visit.new and r.m.visit.profile.number == 1
    assert r.m._active_limit_ma() == limits.auto_limit_ma(r.m.visit.ref_idle_ma, 4)
    r.run(10_500, dt=10)
    assert r.state == State.LIVE and r.screen.data['same']
    r.off(400)
    r.w.v = 0.0
    # visit 3: the VTX regulator is failing
    w.drone.idle_a = 0.71
    r.on()
    r.run_until(lambda x: x.state in (State.LIVE, State.WARNING), 1000)
    r.run(10_500, dt=10)
    assert r.state == State.WARNING and r.screen.id == 'S07'
    kind, old, new = r.screen.data['warning']
    assert kind == memory.W_IDLE_UP and old < 450 and new > 680


def test_drone_memory_capacitor_broke_off():
    m = Machine()
    w = World(pack=Pack.of(6, 4.0), drone=Drone.quad(cap_uf=1000))
    r = Rig(w, m).boot()
    r.go_live()
    r.close_guard(1300)
    r.w.drone.cap_uf = 300
    r.run(70_000, dt=10)                  # long enough for the residual charge rule to lapse
    r.w.v = 0.0                           # caps bled down on the bench
    assert r.go_live() == State.WARNING
    r.run(700)
    assert r.screen.id == 'S07' and r.screen.data['warning'][0] == memory.W_CAP_DOWN


def test_no_big_capacitor_on_4s_warns():
    r = make_rig(drone=Drone(cap_uf=50)).boot()
    assert r.go_live() == State.WARNING
    r.run(700)
    assert r.screen.id == 'S07' and r.screen.data['warning'][0] == 'no_big_cap'


def test_residual_charge_after_power_off_repowers_without_probe():
    r = make_rig().boot()
    r.go_live()
    r.off(400)
    assert r.w.v > 1.0                    # caps still charged
    r.on()
    r.run_until(lambda x: x.state in (State.LIVE, State.ABORT), 1000)
    assert r.state == State.LIVE and r.m.residual


def test_unknown_charged_drone_is_not_assumed_safe():
    w = World(pack=Pack.of(4, 4.0), drone=Drone.quad())
    w.v = 6.0                             # someone else's charged drone
    r = Rig(w).boot()
    r.go_live()
    assert r.m.fault.name == 'BOTH_POWERED'
