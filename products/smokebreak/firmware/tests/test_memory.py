"""Drone memory (SPEC §7)."""
from model import memory as M


def test_new_drone_numbered_and_matched_within_15_percent():
    m = M.DroneMemory()
    v = m.visit(4, 1000)
    assert v.new and v.profile.number == 1
    assert not m.visit(4, 1140).new                # +14 %
    m2 = M.DroneMemory()
    m2.visit(4, 1000)
    other = m2.visit(4, 1160)                      # +16 %: a different drone
    assert other.new and other.profile.number == 2


def test_cell_count_is_part_of_the_key():
    m = M.DroneMemory()
    m.visit(4, 1000)
    assert m.visit(6, 1000).new


def test_closest_profile_wins():
    m = M.DroneMemory()
    m.visit(4, 1000)
    m.visit(4, 1200)
    assert m.visit(4, 1170).profile.number == 2


def test_idle_up_warning_needs_30_percent_and_100ma():
    for old, new, warn in ((420, 710, True), (420, 500, False), (200, 280, False), (1000, 1310, True)):
        m = M.DroneMemory()
        v = m.visit(4, 1000)
        m.record_idle(v, old)
        v2 = m.visit(4, 1000)
        assert m.record_idle(v2, new) == warn, (old, new)
        if warn:
            assert v2.warnings[-1] == (M.W_IDLE_UP, old, new)


def test_capacitance_down_30_percent_on_the_last_drone():
    m = M.DroneMemory()
    m.visit(6, 1000)
    v = m.visit(6, 380)                            # bulk cap broke off
    assert not v.new and v.warnings == [(M.W_CAP_DOWN, 1000, 380)]
    assert m.visit(6, 380).warnings == []          # "than last time": warns once


def test_capacitance_drop_after_another_drone_is_a_new_drone():
    m = M.DroneMemory()
    m.visit(6, 1000)
    m.visit(4, 470)                                # a different drone in between
    assert m.visit(6, 380).new


def test_lru_replacement_at_32():
    m = M.DroneMemory()
    for k in range(M.SLOTS):
        m.visit(4, int(100 * 1.2 ** k))          # 20 % apart: 32 different drones
    assert len(m.profiles) == M.SLOTS and m.next_number == M.SLOTS + 1
    first = m.profiles[0]
    m.visit(4, first.cap_uf)                      # touch drone 1: now most recent
    m.visit(5, 777)                               # 33rd drone evicts the least recent (drone 2)
    numbers = [p.number for p in m.profiles]
    assert len(m.profiles) == M.SLOTS and 1 in numbers and 2 not in numbers
    assert m.visit(5, 777).profile.number == M.SLOTS + 1


def test_export_rows():
    m = M.DroneMemory()
    v = m.visit(3, 470)
    m.record_idle(v, 250)
    assert m.export() == [(1, 3, 470, 250, 1)]
