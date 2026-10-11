"""Two-tier limit and the Limit rocker (SPEC §4 stage 3, §6, §7)."""
import pytest

from model import limits as L


@pytest.mark.parametrize('idle,cells,expect', [
    (-1, 1, 1000), (-1, 2, 3000), (-1, 6, 3000),          # new drone
    (420, 4, 920),                                         # idle + 0.5 A beats 1.5 x idle
    (2000, 6, 3000),                                       # 1.5 x idle beats idle + 0.5 A
    (0, 4, 500), (40, 1, 540),                             # floor 0.5 A
    (4000, 6, 5000),                                       # ceiling 5 A
])
def test_auto_limit(idle, cells, expect):
    assert L.auto_limit_ma(idle, cells) == expect


def test_peak_threshold_is_4x_clamped_to_amp_range():
    assert L.peak_threshold_ma(2000) == 8000
    assert L.peak_threshold_ma(10000) == 40000
    assert L.peak_threshold_ma(25000) == L.PEAK_MAX_MA


def test_average_over_200ms_passes_esc_tones():
    lim = L.AverageLimiter()
    for t in range(1000):
        lim.add(500, 1)
    for t in range(40):                      # 40 ms at 4 A (ESC tone / VTX boot)
        lim.add(4000, 1)
        assert not lim.over(2000)
    assert lim.window_peak_ma() == 4000


def test_average_trips_on_sustained_overcurrent():
    lim = L.AverageLimiter()
    tripped_at = None
    for t in range(1, 400):
        lim.add(2600, 1)
        if lim.over(2000):
            tripped_at = t
            break
    assert tripped_at is not None and tripped_at < 200


def test_average_steady_value_and_coarse_ticks():
    lim = L.AverageLimiter()
    for _ in range(50):
        lim.add(1234, 10)
    assert lim.avg_ma() == 1234


def press(sel, t, plus=False, minus=False):
    sel.step(t, plus, minus)
    sel.step(t + 50, False, False)


def test_rocker_steps_and_25a_confirm():
    s = L.LimitSelector()
    t = 0
    for expect in (1, 2, 3, 4):
        t += 200
        press(s, t, plus=True)
        assert s.idx == expect
    t += 200
    press(s, t, plus=True)
    assert s.confirm_pending and s.idx == L.IDX_10A
    t += 1000
    press(s, t, plus=True)
    assert s.idx == L.IDX_25A and s.motor_test and not s.confirm_pending


def test_25a_times_out_after_60s_to_previous_setting():
    s = L.LimitSelector(idx=L.IDX_10A)
    press(s, 0, plus=True)
    press(s, 1000, plus=True)
    assert s.motor_test
    s.step(1000 + L.MOTOR_TEST_MS - 1, False, False)
    assert s.motor_test
    s.step(1000 + L.MOTOR_TEST_MS, False, False)
    assert s.idx == L.IDX_10A and 'motor_off' in s.events


def test_25a_confirm_window_times_out_after_3s():
    s = L.LimitSelector(idx=L.IDX_10A)
    press(s, 0, plus=True)
    s.step(L.CONFIRM_WINDOW_MS, False, False)
    assert not s.confirm_pending and s.idx == L.IDX_10A
    press(s, L.CONFIRM_WINDOW_MS + 100, plus=True)     # a late + asks again, does not arm
    assert s.confirm_pending and s.idx == L.IDX_10A


@pytest.mark.parametrize('period', [60, 100, 160, 250])
def test_rocker_mashing_cannot_confirm_motor_test(period):
    s = L.LimitSelector()
    for k in range(80):                                # + mashed for several seconds
        s.step(k * period // 2, k % 2 == 0, False)
        assert s.idx != L.IDX_25A


def test_press_inside_dead_time_cancels_prompt():
    s = L.LimitSelector(idx=L.IDX_10A)
    press(s, 0, plus=True)
    press(s, 200, plus=True)
    assert not s.confirm_pending and s.idx == L.IDX_10A


def test_minus_cancels_confirm_and_leaves_25a():
    s = L.LimitSelector(idx=L.IDX_10A)
    press(s, 0, plus=True)
    press(s, 500, minus=True)
    assert not s.confirm_pending and s.idx == L.IDX_10A
    press(s, 1000, plus=True)
    press(s, 1500, plus=True)
    assert s.motor_test
    press(s, 2000, minus=True)
    assert s.idx == L.IDX_10A


def test_both_halves_at_once_and_floor():
    s = L.LimitSelector(idx=2)
    s.step(0, True, True)
    assert s.idx == 2
    s = L.LimitSelector()
    press(s, 0, minus=True)
    assert s.idx == L.AUTO
