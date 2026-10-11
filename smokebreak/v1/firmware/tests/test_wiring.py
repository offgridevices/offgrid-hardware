"""ARCHITECTURE §4 (wrong connections and bad batteries), row by row, end to
end through the simulated plant, plus the §3 battery screens."""
from conftest import make_rig
from model import battery as B
from model.inputs import Toggle
from model.machine import Led, State
from model.sim_world import Balance, Drone, Pack, Rig, World


# --- §4 row 1: battery reversed on the input -------------------------------
def test_battery_reversed_on_input_board_stays_dark():
    r = Rig(World(pack=Pack.of(4, 4.2), drone=Drone.quad(), input_reversed=True))
    r.w.guard_closed = False
    r.w.toggle = Toggle.ON
    r.run(3000)
    assert set(r.screens) == {'dark'} and not r.ever_main and r.w.max_drone_v == 0


def test_battery_reversed_on_input_with_usb_reads_no_battery():
    r = Rig(World(pack=Pack.of(4, 4.2), drone=Drone.quad(), input_reversed=True, usb=True)).boot()
    assert r.screen.id == 'S01' and r.screen.data['battery'] is False
    r.open_guard()
    r.on(500)
    assert r.state == State.ARMED and r.screen.data['hint'] == 'no_battery' and not r.ever_probe


# --- row 2: battery on the drone side, nothing on the input ----------------
def test_battery_on_drone_side_wakes_board_and_explains():
    r = Rig(World(pack=None, drone=Drone(cap_uf=1000, battery=(16.8, 0.02)))).boot()
    assert r.state == State.SAFE and r.screen.id == 'S17'
    r.open_guard()
    assert r.screen.id == 'S17'
    r.on(100)
    assert r.state == State.ABORT and r.screen.id == 'S17' and r.m.fault.name == 'BATT_ON_DRONE_SIDE'
    assert not r.ever_probe and not r.ever_main


# --- row 3: batteries on both sides ---------------------------------------
def test_batteries_on_both_sides_never_closes_anything():
    r = Rig(World(pack=Pack.of(4, 4.0), drone=Drone(cap_uf=1000, battery=(16.4, 0.02)))).boot()
    r.go_live()
    assert r.m.fault.name == 'BOTH_POWERED'
    assert r.screen.data['title'] == 'Drone side already has power'
    assert not r.ever_pre and not r.ever_main and not r.ever_probe


# --- row 4: battery reversed on the drone side ------------------------------
def test_reversed_battery_on_drone_side():
    r = Rig(World(pack=Pack.of(4, 4.0), drone=Drone(cap_uf=1000, battery=(-16.0, 0.02)))).boot()
    r.go_live()
    assert r.m.fault.name == 'REVERSED_BATT_DRONE_SIDE' and r.screen.id == 'S09'
    assert not r.ever_pre and not r.ever_main


# --- row 5: drone wired backwards ------------------------------------------
def test_drone_wired_backwards_leads_reversed():
    r = make_rig(drone=Drone(cap_uf=1000, reversed=True)).boot()
    r.go_live()
    assert r.m.fault.name == 'REVERSED_LEADS' and r.screen.id == 'S09'
    assert r.screen.data['title'] == 'Leads reversed'
    assert not r.ever_pre and not r.ever_main


# --- row 6: dead short / half-short -----------------------------------------
def test_dead_short_shows_ohms_and_battery_never_reached_drone():
    r = make_rig(drone=Drone(cap_uf=1000, short_ohm=0.3)).boot()
    r.go_live()
    assert r.screen.id == 'S08' and r.screen.data['title'] == 'Short circuit'
    assert r.screen.data['value'] == '0.3 Ω'
    assert not r.ever_pre and not r.ever_main and r.w.max_drone_v == 0


def test_half_short_shows_ohms():
    r = make_rig(drone=Drone(cap_uf=1000, load_ohm=18)).boot()
    r.go_live()
    assert r.screen.data['title'] == 'Half-short' and r.screen.data['value'] == '18 Ω'
    assert not r.ever_pre


# --- row 7: balance plug shifted ---------------------------------------------
def test_balance_plug_shifted_reading_ok_screen():
    w = World(pack=Pack([3.81, 3.83, 3.80, 3.82]), drone=Drone.quad(), balance=Balance(shift=2))
    r = Rig(w).boot()
    assert r.screen.id == 'S18' and r.screen.data['shift'] == 2
    assert r.screen.data['cells_mv'] == [3810, 3830, 3800, 3820]
    r.run(3000)
    assert r.screen.id == 'S14' and r.screen.data['storage'] == B.Storage.AT


def test_balance_lead_alone_shifted_leaves_board_dark():
    r = Rig(World(pack=None, balance=Balance(pack=Pack.of(4, 3.9), shift=1)))
    r.run(2000)
    assert set(r.screens) == {'dark'}


# --- row 8: balance lead from another pack -----------------------------------
def test_balance_lead_from_another_pack():
    w = World(pack=Pack.of(4, 4.2), drone=Drone.quad(), balance=Balance(pack=Pack.of(4, 3.75)))
    r = Rig(w).boot()
    assert r.screen.id == 'S15' and r.screen.data['warning'][0] == B.Warn.OTHER_PACK


# --- row 9: deeply discharged pack: check runs, power allowed with a warning --
def test_deeply_discharged_pack_powers_with_warning():
    w = World(pack=Pack([3.30, 3.31, 2.71, 3.30]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    assert r.screen.id == 'S15' and r.screen.data['warning'] == (B.Warn.OVERDISCHARGED, 2, 2710)
    assert r.go_live() == State.WARNING
    r.run(700)
    assert r.out.main_on and r.screen.id == 'S15' and r.out.led == Led.EMBER


# --- row 10: over-charged / LiHV detection ------------------------------------
def test_overcharged_for_lipo_warning():
    w = World(pack=Pack([4.20, 4.31, 4.20, 4.20]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    assert r.screen.id == 'S15' and r.screen.data['warning'] == (B.Warn.OVERCHARGED_LIPO, 1, 4310)


# --- row 11: high internal resistance (sags) ------------------------------------
def test_high_ir_pack_sag_flagged_from_a_load_step():
    w = World(pack=Pack.of(4, 4.0, ir=25.0), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    for _ in range(4):
        r.plus()                          # 10 A
    r.run(2100)                           # let the S13 picker close
    r.go_live()
    r.run(1000)
    r.w.drone.demand_a = 6.0              # motor step
    r.run(300)
    assert r.state == State.WARNING and r.screen.id == 'S15'
    kind, pack_mohm, sag_mv = r.screen.data['warning']
    assert kind == B.Warn.HIGH_IR and 90 <= pack_mohm <= 120 and sag_mv > 500


def test_healthy_pack_step_does_not_warn():
    w = World(pack=Pack.of(4, 4.0, ir=3.0), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    for _ in range(4):
        r.plus()                          # 10 A
    r.run(2100)                           # let the S13 picker close
    r.go_live()
    r.run(1000)
    r.w.drone.demand_a = 6.0
    r.run(300)
    assert r.state == State.LIVE and r.m.ir is not None and r.m.ir[0] < 40


# --- row 12: pack collapsing under load ------------------------------------------
def test_pack_collapsing_under_load():
    w = World(pack=Pack.of(4, 4.0, ir=150.0), drone=Drone.quad())
    r = Rig(w).boot()
    for _ in range(4):
        r.plus()                          # 10 A
    r.run(2100)                           # let the S13 picker close
    r.go_live()
    r.run(700)
    r.w.drone.demand_a = 9.5
    r.run(200)
    assert r.state == State.ABORT and r.m.fault.name == 'INPUT_COLLAPSE'
    assert r.screen.data['title'] == 'Battery voltage collapsed' and not r.out.main_on


# --- row 14: USB plugged in while the drone is on ----------------------------------
def test_usb_plugged_in_while_live_changes_nothing():
    r = make_rig().boot()
    r.go_live()
    r.run(700)
    ma = r.screen.data['ma']
    r.w.usb = True
    r.run(2000)
    assert r.state == State.LIVE and abs(r.screen.data['ma'] - ma) < 5


# --- USB only: screen powered, nothing else -------------------------------------------
def test_usb_only_power():
    r = Rig(World(pack=None, drone=Drone.quad(), usb=True)).boot()
    assert r.screen.id == 'S01' and r.out.led == Led.OFF
    r.open_guard()
    r.on(1000)
    assert not r.ever_probe and not r.ever_pre and not r.ever_main


# --- §3: battery screens -------------------------------------------------------------------
def test_battery_screen_with_balance_lead():
    w = World(pack=Pack([4.11, 4.12, 4.10, 4.13]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    d = r.screen.data
    assert r.screen.id == 'S14' and d['cells'] == 4 and d['certain']
    assert d['lo'] == 2 and d['hi'] == 3 and d['delta_mv'] == 30 and d['delta'] == B.Delta.DRIFTING
    assert 85 <= d['soc'] <= 95 and d['storage'] == B.Storage.ABOVE


def test_balance_check_only_no_drone_no_main_lead():
    r = Rig(World(pack=None, balance=Balance(pack=Pack([3.85, 3.84, 3.86])))).boot()
    assert r.screen.id == 'S16' and r.screen.data['cells'] == 3
    assert r.screen.data['storage'] == B.Storage.AT
    r.open_guard()
    r.on(500)
    assert not r.ever_probe and r.screen.data.get('hint') == 'no_battery'


def test_out_of_balance_pack_warning():
    w = World(pack=Pack([3.95, 3.80, 3.95, 3.95]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    assert r.screen.id == 'S15' and r.screen.data['warning'][0] == B.Warn.OUT_OF_BALANCE


def test_dead_cell_screen():
    w = World(pack=Pack([3.70, 2.20, 3.70]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    assert r.screen.data['warning'][:2] == (B.Warn.DEAD_CELL, 1)
