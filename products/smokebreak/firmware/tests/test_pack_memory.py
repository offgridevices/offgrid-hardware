"""Pack memory (packs.py): fingerprint, the "Pack 7?" question, the table,
and the machine wiring (plug-in, rocker, IR from a run)."""
import pytest

from conftest import make_rig
from model import limits
from model import packs as P
from model.machine import Machine, State
from model.sim_world import Balance, Drone, Pack, Rig, World


def mem_with(*specs):
    """specs: (cells, ir_mohm or -1, cell_ir list or None) -> confirmed packs 1..n."""
    m = P.PackMemory()
    for cells, ir, cell_ir in specs:
        p = m.confirm(P.NEW, cells)
        m.record_ir(p, ir, cell_ir)
    return m


def run_prompt(q, events, start=0, end=None):
    """events: {t_ms: (plus, minus)} levels from that ms on; steps 1 ms at a time."""
    plus = minus = False
    end = end if end is not None else max(events) + 200
    for t in range(start, end):
        if t in events:
            plus, minus = events[t]
        q.step(t, plus, minus)
        if q.answer != P.Answer.PENDING:
            return t
    return None


def tap(t, which='plus', hold=50):
    lv = (True, False) if which == 'plus' else (False, True)
    return {t: lv, t + hold: (False, False)}


# ---------------------------------------------------------------- new pack / match

def test_first_pack_is_new_pack_1():
    m = P.PackMemory()
    assert m.candidates(4) == []
    q = P.Prompt(m, 4, 0)
    assert q.options == [P.NEW] and q.is_new and q.new_number == 1
    assert run_prompt(q, tap(400)) is not None and q.answer == P.Answer.CONFIRMED and q.chosen == P.NEW
    p = m.confirm(q.chosen, 4, 1_760_000_000, 12, 2)
    assert (p.number, p.cells, p.uses) == (1, 4, 1)
    assert p.first_seq == p.last_seq == 1 and p.first_time_s == p.last_time_s == 1_760_000_000
    assert p.ir_first_mohm == p.ir_last_mohm == P.UNKNOWN and p.imbalance_mv == 12
    assert m.next_number == 2


def test_same_cell_count_is_proposed_and_confirmed():
    m = P.PackMemory()
    m.confirm(P.NEW, 4)
    q = P.Prompt(m, 4, 0)
    assert q.options == [1, P.NEW] and q.option == 1 and not q.is_new
    run_prompt(q, tap(400))
    assert q.chosen == 1
    p = m.confirm(q.chosen, 4)
    assert p.number == 1 and p.uses == 2 and len(m.packs) == 1 and m.next_number == 2


@pytest.mark.parametrize('cells', [1, 3, 5, 6, 14])
def test_cell_count_must_match_exactly(cells):
    m = P.PackMemory()
    m.confirm(P.NEW, 4)
    assert m.candidates(cells) == []
    q = P.Prompt(m, cells, 0)
    assert q.options == [P.NEW] and q.new_number == 2


def test_new_pack_when_ir_does_not_match():
    m = mem_with((4, 20, None))
    assert m.candidates(4, 40) == []                 # +100 %: not this pack
    assert [p.number for p in m.candidates(4, 22)] == [1]


# ---------------------------------------------------------------- IR tolerance

@pytest.mark.parametrize('ir, ok', [
    (40, True), (30, True), (50, True),              # +-25 % of 40 mOhm is exactly 10
    (29, False), (51, False), (10, False), (80, False)])
def test_pack_ir_window_25_percent(ir, ok):
    m = mem_with((6, 40, None))
    assert (m.candidates(6, ir) != []) == ok


@pytest.mark.parametrize('ir, ok', [(3, True), (13, True), (2, False), (14, False)])
def test_pack_ir_window_floor_5_mohm_for_low_ir_packs(ir, ok):
    m = mem_with((4, 8, None))                       # 25 % of 8 = 2 < floor 5
    assert (m.candidates(4, ir) != []) == ok


@pytest.mark.parametrize('cells_ir, ok', [
    ([10, 10, 10, 10], True), ([13, 7, 10, 10], True),  # +-30 % of 10 is exactly 3
    ([14, 10, 10, 10], False), ([10, 10, 6, 10], False)])
def test_per_cell_ir_window_30_percent(cells_ir, ok):
    m = mem_with((4, 50, [10, 10, 10, 10]))
    assert (m.candidates(4, 50, cells_ir) != []) == ok


@pytest.mark.parametrize('cells_ir, ok', [([2, 6, 4, 4], True), ([4, 4, 7, 4], False), ([1, 4, 4, 4], False)])
def test_per_cell_ir_floor_2_mohm(cells_ir, ok):
    m = mem_with((4, 30, [4, 4, 4, 4]))
    assert (m.candidates(4, -1, cells_ir) != []) == ok


def test_cell_pattern_tells_apart_packs_with_the_same_total():
    m = mem_with((4, 40, [10, 10, 10, 10]), (4, 40, [6, 6, 6, 22]))
    assert [p.number for p in m.candidates(4, 40, [6, 6, 7, 21])] == [2]
    assert [p.number for p in m.candidates(4, 40, [10, 9, 11, 10])] == [1]


def test_unknown_ir_on_either_side_still_matches():
    m = mem_with((4, -1, None), (4, 30, [5, 5, 5, 5]))
    assert {p.number for p in m.candidates(4)} == {1, 2}            # nothing measured now
    assert [p.number for p in m.candidates(4, 300)] == [1]          # 2 ruled out, 1 has no IR to compare


def test_ranking_closest_ir_first_then_uncompared_then_recency():
    m = mem_with((4, 30, None), (4, 26, None), (4, -1, None))
    # 3 is the most recent but has no IR: compared packs come first, closest first
    assert [p.number for p in m.candidates(4, 27)] == [2, 1, 3]
    assert [p.number for p in m.candidates(4, 29)] == [1, 2, 3]
    assert [p.number for p in m.candidates(4, 28)] == [1, 2, 3]      # relative to the stored value: 2/30 < 2/26
    # nothing measured: recency only, most recent first
    assert [p.number for p in m.candidates(4)] == [3, 2, 1]
    m.confirm(1, 4)
    assert [p.number for p in m.candidates(4)] == [1, 3, 2]


# ---------------------------------------------------------------- the question

def test_minus_steps_through_candidates_then_new_then_wraps():
    m = mem_with((4, -1, None), (4, -1, None), (4, -1, None))
    q = P.Prompt(m, 4, 0)
    assert q.options == [3, 2, 1, P.NEW]
    seen = [q.option]
    t = 400
    for _ in range(4):
        q.step(t, False, True)
        q.step(t + 50, False, False)
        seen.append(q.option)
        t += 200
    assert seen == [3, 2, 1, P.NEW, 3]
    q.step(t, False, True)
    q.step(t + 50, False, False)
    q.step(t + 100, False, True)
    q.step(t + 150, False, False)
    q.step(t + 200, False, False)
    q.step(t + 250, True, False)
    assert q.answer == P.Answer.CONFIRMED and q.chosen == 1


def test_new_is_offered_with_the_next_number_and_confirms():
    m = mem_with((4, -1, None), (6, -1, None))
    q = P.Prompt(m, 4, 0)
    q.step(400, False, True)
    q.step(450, False, False)
    assert q.is_new and q.new_number == 3
    q.step(500, True, False)
    assert q.chosen == P.NEW
    assert m.confirm(q.chosen, 4).number == 3


def test_presses_in_the_first_300_ms_are_ignored():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0)
    q.step(100, True, False)
    q.step(150, False, False)
    q.step(200, False, True)
    q.step(250, False, False)
    assert q.answer == P.Answer.PENDING and q.option == 1
    q.step(P.PROMPT_DEAD_MS, True, False)
    assert q.answer == P.Answer.CONFIRMED


def test_button_already_held_when_asked_does_not_answer():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0, plus=True)
    for t in range(1, 2000):
        q.step(t, True, False)
    assert q.answer == P.Answer.PENDING
    q.step(2000, False, False)
    q.step(2001, True, False)
    assert q.answer == P.Answer.CONFIRMED


def test_both_halves_at_once_are_ignored():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0)
    q.step(400, True, True)
    q.step(500, True, True)
    q.step(600, False, True)          # releasing one half is not a press of the other
    q.step(700, False, False)
    assert q.answer == P.Answer.PENDING and q.option == 1


def test_no_input_times_out_to_skip():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0)
    for t in range(P.PROMPT_TIMEOUT_MS - 1):
        assert q.step(t, False, False) == P.Answer.PENDING
    assert q.left_ms(P.PROMPT_TIMEOUT_MS - 1) == 1
    assert q.step(P.PROMPT_TIMEOUT_MS, False, False) == P.Answer.SKIPPED
    assert q.step(P.PROMPT_TIMEOUT_MS + 10, True, False) == P.Answer.SKIPPED      # stays skipped


def test_minus_restarts_the_timeout():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0)
    q.step(4000, False, True)
    q.step(4050, False, False)
    assert q.step(8999, False, False) == P.Answer.PENDING
    assert q.step(9000, False, False) == P.Answer.SKIPPED


def test_skip_records_nothing():
    m = mem_with((4, -1, None))
    q = P.Prompt(m, 4, 0)
    q.skip()
    assert q.answer == P.Answer.SKIPPED
    assert m.seq == 1 and m.next_number == 2 and m.packs[0].uses == 1


# ---------------------------------------------------------------- numbers and the table

def test_numbers_are_never_reused_after_the_table_wraps():
    m = P.PackMemory()
    given = []
    for k in range(3 * P.SLOTS + 5):
        given.append(m.confirm(P.NEW, 1 + k % P.MAX_CELLS).number)
    assert given == list(range(1, 3 * P.SLOTS + 6))
    assert len(m.packs) == P.SLOTS
    assert sorted(p.number for p in m.packs) == list(range(2 * P.SLOTS + 6, 3 * P.SLOTS + 6))
    q = P.Prompt(m, 3, 0)
    assert q.new_number == 3 * P.SLOTS + 6


def test_full_table_replaces_the_least_recently_seen():
    m = P.PackMemory()
    for _ in range(P.SLOTS):
        m.confirm(P.NEW, 6)
    m.confirm(1, 6)                                   # pack 1 seen again: now the most recent
    new = m.confirm(P.NEW, 4)
    numbers = {p.number for p in m.packs}
    assert new.number == P.SLOTS + 1 and len(m.packs) == P.SLOTS
    assert 1 in numbers and 2 not in numbers
    assert m.find(2) is None and m.confirm(2, 6).number == P.SLOTS + 2   # an evicted number comes back as new


def test_visit_counter_wraparound_keeps_recency_and_lru():
    m = P.PackMemory()
    m.seq = P.SEQ_MASK - 3
    for _ in range(P.SLOTS):
        m.confirm(P.NEW, 4)                           # the counter wraps through 0 on the way
    assert m.seq < 100
    oldest = m.find(1)
    assert m.age(oldest) == P.SLOTS - 1 and m.age(m.find(P.SLOTS)) == 0
    assert [p.number for p in m.candidates(4)][:3] == [P.SLOTS, P.SLOTS - 1, P.SLOTS - 2]
    m.confirm(P.NEW, 4)
    assert m.find(1) is None and m.find(2) is not None


# ---------------------------------------------------------------- clock missing

def test_missing_clock_falls_back_to_the_visit_counter():
    m = P.PackMemory()
    p = m.confirm(P.NEW, 4, P.TIME_NONE)
    assert p.first_time_s == P.TIME_NONE and p.last_time_s == P.TIME_NONE and p.first_seq == 1
    m.confirm(P.NEW, 6)
    m.confirm(1, 4, 1_760_000_000)                    # clock set over USB this time
    assert p.first_time_s == P.TIME_NONE and p.last_time_s == 1_760_000_000
    m.confirm(1, 4, P.TIME_NONE)                      # clock lost again: last seen unknown, order intact
    assert p.last_time_s == P.TIME_NONE and p.last_seq == 4 and p.uses == 3
    assert m.age(p) == 0 and m.age(m.find(2)) == 2
    assert [q.number for q in m.candidates(4)] == [1]


# ---------------------------------------------------------------- IR history, wear

def test_ir_first_sight_is_kept_latest_is_updated():
    m = P.PackMemory()
    p = m.confirm(P.NEW, 4)
    assert not P.ir_known(p) and P.ir_change_pct(p) == 0 and not P.wearing(p)
    m.record_ir(p, 20, [4, 5, 4, 4])
    m.record_ir(p, 23, [4, 6, 5, 4])
    assert p.ir_first_mohm == 20 and p.ir_last_mohm == 23
    assert p.ir_first_cells == [4, 5, 4, 4, -1, -1] and p.ir_last_cells == [4, 6, 5, 4, -1, -1]
    assert P.ir_change_pct(p) == 15 and p.worst_cell == 1
    m.record_ir(p, 22, [4, 5, 5, 4])
    assert p.worst_cell == -1                                           # 1 mOhm apart: no weakest cell


@pytest.mark.parametrize('first, last, wear, pct', [
    (20, 28, False, 40), (20, 29, True, 45), (100, 140, False, 40), (100, 141, True, 41),
    (30, 25, False, -16), (30, 30, False, 0)])
def test_wearing_above_40_percent_over_first_sight(first, last, wear, pct):
    m = P.PackMemory()
    p = m.confirm(P.NEW, 6)
    m.record_ir(p, first)
    m.record_ir(p, last)
    assert P.wearing(p) == wear and P.ir_change_pct(p) == pct
    assert P.WEAR_PERMILLE == 400


def test_cell_ir_from_two_currents_with_cell_1_corrected():
    lo = [4000, 4000, 4000, 4000]
    hi = [3990, 3960, 3960, 3920]                     # 10 A step
    assert P.cell_ir_mohm(lo, 1000, hi, 11000) == [1 + P.CELL1_RETURN_MOHM, 4, 4, 8]
    assert P.cell_ir_mohm([4000, 4000], 0, [3976, 3976], 6010) == [4 + P.CELL1_RETURN_MOHM, 4]   # rounded, 3.99
    assert P.cell_ir_mohm(lo, 1000, hi, 2999) is None  # dI < 2 A
    assert P.cell_ir_mohm(lo, 1000, hi[:3], 11000) is None
    assert P.cell_ir_mohm([4000], 0, [4100], 5000) == [0]              # rose under load: clamped at 0


def test_worst_cell_and_imbalance_from_plug_ins():
    m = P.PackMemory()
    p = m.confirm(P.NEW, 4, imbalance_mv=10, lo_idx=2)
    assert p.worst_cell == -1 and p.imbalance_mv == 10                   # balanced: no weakest cell
    m.confirm(1, 4, imbalance_mv=60, lo_idx=3)
    assert p.worst_cell == 3 and p.imbalance_mv == 60 and p.max_imbalance_mv == 60
    m.confirm(1, 4, imbalance_mv=30, lo_idx=1)
    assert p.imbalance_mv == 30 and p.max_imbalance_mv == 60 and p.worst_cell == 1
    m.record_ir(p, 30, [4, 4, 9, 4])
    m.confirm(1, 4, imbalance_mv=80, lo_idx=0)
    assert p.worst_cell == 2                                             # per-cell IR wins once known


def test_export_rows():
    m = P.PackMemory()
    p = m.confirm(P.NEW, 4, 1_700_000_000, 15, 0)
    m.record_ir(p, 20)
    m.record_ir(p, 30)
    assert m.export() == [(1, 4, 1, 1_700_000_000, 1_700_000_000, 1, 20, 30, 50, True, -1, 15)]


# ================================================================ the machine

def rig4(m=None, usb=False, **kw):
    w = World(pack=Pack.of(4, 4.0), drone=Drone.quad(), balance=Balance(), usb=usb, **kw)
    return Rig(w, Machine(pack_mem=m) if m is not None else None)


def wait_ask(r, max_ms=6000):
    assert r.run_until(lambda x: (x.screen.data.get('pack') or {}).get('ask'), max_ms)
    return r.screen.data['pack']


def test_plug_in_asks_new_pack_and_plus_confirms():
    r = rig4().boot()
    assert r.screen.id == 'S14' and r.screen.data['pack'] is None       # battery screen first
    d = wait_ask(r)
    assert r.w.t_ms >= P.PROMPT_DELAY_MS and r.state == State.SAFE
    assert d['new'] and d['number'] == 1 and d['options'] == 1
    r.run(400)
    r.plus()
    d = r.screen.data['pack']
    assert d['ask'] is False and d['number'] == 1 and d['new'] and d['uses'] == 1
    assert r.m.packs.find(1).cells == 4 and r.m.limit.idx == limits.AUTO   # the + went to the question


def test_replug_proposes_the_known_pack_minus_then_new_then_back():
    r = rig4(usb=True).boot()
    wait_ask(r)
    r.run(400)
    r.plus()
    pack = r.w.pack
    r.w.pack, r.w.balance = None, None
    r.run(500)
    assert r.screen.data['pack'] is None
    r.w.pack, r.w.balance = pack, Balance()
    d = wait_ask(r)
    assert not d['new'] and d['number'] == 1 and d['uses'] == 1 and d['options'] == 2
    r.run(400)
    r.minus()
    assert r.screen.data['pack']['new'] and r.screen.data['pack']['number'] == 2
    r.minus()
    assert r.screen.data['pack']['number'] == 1
    r.plus()
    assert r.screen.data['pack']['ask'] is False and r.m.packs.find(1).uses == 2
    assert r.m.packs.next_number == 2 and r.m.limit.idx == limits.AUTO


def test_question_times_out_and_the_rocker_goes_back_to_the_limit():
    r = rig4().boot()
    wait_ask(r)
    r.run(P.PROMPT_TIMEOUT_MS + 10)
    assert r.screen.data['pack'] is None and r.m.packs.packs == []
    r.plus()
    assert r.m.limit.idx == 1 and r.screen.id == 'S13'
    r.run(3000)
    assert r.screen.data['pack'] is None                               # asked once per plug-in


def test_rocker_during_the_question_never_reaches_the_limit():
    r = rig4().boot()
    wait_ask(r)
    r.run(400)
    for _ in range(3):
        r.minus()
    r.plus()
    assert r.m.limit.idx == limits.AUTO and not r.m.limit.confirm_pending
    assert len(r.m.packs.packs) == 1


def test_question_never_blocks_arming_guard_open_skips_it():
    r = rig4().boot()
    wait_ask(r)
    assert r.go_live() == State.LIVE
    assert r.m.prompt is None and r.m.pack is None and r.m.packs.packs == []
    r.plus()
    assert r.m.limit.idx == 1                                           # the rocker is the limit again


def test_not_asked_while_the_limit_overlay_shows_or_the_rocker_is_held():
    r = rig4().boot()
    r.run(300)
    r.plus()                                                            # 1 A, S13 for 2 s
    r.run(1500)
    assert r.w.t_ms > P.PROMPT_DELAY_MS and r.m.prompt is None and r.screen.id == 'S13'
    r.w.minus = True                                                    # back to AUTO: S13 for 2 s more ...
    r.run(2600)                                                         # ... and held past its end
    assert r.screen.id != 'S13' and r.m.prompt is None
    r.w.minus = False
    r.run(20)
    assert r.m.prompt is not None and r.screen.data['pack']['ask']


def test_box_woken_with_the_guard_open_asks_once_the_guard_closes():
    w = World(pack=Pack.of(4, 4.0), drone=Drone.quad(), balance=Balance())
    w.guard_closed = False
    r = Rig(w)
    r.run(5000)
    assert r.state == State.ARMED and r.m.prompt is None
    r.close_guard(1300)
    wait_ask(r)


def press_to_10a(r):
    for _ in range(4):
        r.plus()
    r.run(2100)


def motor_run(r, demand=6.0):
    r.go_live()
    r.run(1000)
    r.w.drone.demand_a = demand
    r.run(300)
    r.w.drone.demand_a = 0.0
    r.off(50)


def test_run_ir_is_stored_on_the_confirmed_pack():
    r = rig4().boot()
    wait_ask(r)
    r.run(400)
    r.plus()
    press_to_10a(r)
    motor_run(r)
    assert r.state == State.ARMED
    p = r.m.packs.find(1)
    # VIN sees 4 x 4 mOhm cells + 6 mOhm lead + Q11 7 mOhm = 29 mOhm
    assert 26 <= p.ir_first_mohm <= 32 and p.ir_last_mohm == p.ir_first_mohm
    assert p.ir_first_cells == [4, 4, 4, 4, -1, -1]                   # 4 mOhm cells, cell 1 corrected
    assert p.worst_cell == -1                                           # none stands out
    assert P.ir_change_pct(p) == 0 and not P.wearing(p)


def test_wearing_pack_flagged_on_the_battery_screen():
    m = P.PackMemory()
    old = m.confirm(P.NEW, 4)
    m.record_ir(old, 18, [3, 3, 3, 3])                 # first sight: a fresh pack
    w = World(pack=Pack.of(4, 4.0, ir=4.0), drone=Drone.quad(), balance=Balance())
    r = Rig(w, Machine(pack_mem=m)).boot()
    d = wait_ask(r)
    assert d['number'] == 1 and not d['wearing']
    r.run(400)
    r.plus()
    press_to_10a(r)
    motor_run(r)
    r.close_guard(1300)
    d = r.screen.data['pack']
    assert d['number'] == 1 and d['ir_change_pct'] > 40 and d['wearing']


def test_ir_from_a_run_before_the_answer_ranks_the_candidates_and_is_stored():
    m = P.PackMemory()
    for ir in (12, 60):                                 # two 4S packs: a fresh one and a tired one
        p = m.confirm(P.NEW, 4)
        m.record_ir(p, ir)
    m.confirm(1, 4)                                     # pack 1 seen most recently
    w = World(pack=Pack.of(4, 4.0, ir=12.0), drone=Drone.quad(), balance=Balance())   # ~61 mOhm at VIN
    w.guard_closed = False
    r = Rig(w, Machine(pack_mem=m))
    r.run(1600)
    for _ in range(4):
        r.plus()
    r.run(2100)
    motor_run(r)
    assert r.m.plug_ir is not None and 50 <= r.m.plug_ir[0] <= 70
    r.close_guard(1300)
    d = wait_ask(r)
    assert d['number'] == 2 and d['options'] == 2      # pack 1 (12 mOhm) ruled out by IR
    r.run(400)
    r.plus()
    assert m.find(2).ir_last_mohm == r.m.plug_ir[0] and m.find(2).uses == 2


def test_clock_from_usb_is_stored_and_missing_clock_is_not():
    r = rig4(usb=True)
    r.w.clock_s = 1_760_000_000
    r.boot()
    wait_ask(r)
    r.run(400)
    r.plus()
    p = r.m.packs.find(1)
    assert p.first_time_s == 1_760_000_000 and p.last_time_s == p.first_time_s
    r2 = rig4()
    r2.boot()
    wait_ask(r2)
    r2.run(400)
    r2.plus()
    assert r2.m.packs.find(1).first_time_s == P.TIME_NONE


def test_unplug_while_asked_drops_the_question():
    r = rig4(usb=True).boot()
    wait_ask(r)
    r.w.pack, r.w.balance = None, None
    r.run(100)
    assert r.m.prompt is None and r.screen.data['pack'] is None and r.m.packs.packs == []


def test_imbalance_and_weak_cell_recorded_at_plug_in():
    w = World(pack=Pack([3.95, 3.80, 3.95, 3.95]), drone=Drone.quad(), balance=Balance())
    r = Rig(w).boot()
    d = wait_ask(r)
    assert r.screen.id == 'S15'                          # the warning screen carries the question
    r.run(400)
    r.plus()
    p = r.m.packs.find(1)
    assert p.imbalance_mv == 150 and p.max_imbalance_mv == 150 and p.worst_cell == 1


def test_ambiguous_cell_count_waits_for_certainty():
    w = World(pack=Pack.of(10, 3.85), drone=Drone(cap_uf=3300, idle_a=0.1))   # 9S/10S ambiguous, no balance
    r = Rig(w).boot()
    r.run(8000)
    assert r.m.batt.guess.ambiguous and r.m.prompt is None and r.m.packs.packs == []
