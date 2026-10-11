"""3 V probe classifier (SPEC §4 stage 1; ARCHITECTURE §4 rows: short, half-short, reversed)."""
import pytest

from conftest import run_probe, probe_samples
from model import probe
from model.probe import Verdict
from model.sim_world import Drone


@pytest.mark.parametrize('ohm', [0.01, 0.1, 0.3, 0.8])
def test_dead_short_named_with_resistance(ohm):
    r = run_probe(Drone(cap_uf=1000, short_ohm=ohm))
    assert r.verdict == Verdict.SHORT
    assert abs(r.load_mohm - ohm * 1000) <= max(30, ohm * 100)


@pytest.mark.parametrize('ohm', [2, 18, 47, 100, 140])
def test_half_short_resistance_within_10_percent(ohm):
    r = run_probe(Drone(cap_uf=470, load_ohm=ohm))
    assert r.verdict == Verdict.HALF_SHORT
    assert abs(r.load_mohm - ohm * 1000) <= ohm * 100


def test_half_short_hidden_behind_big_capacitor_is_extrapolated():
    # 100 Ohm in parallel with 5000 uF never settles in 250 ms
    r = run_probe(Drone(cap_uf=5000, load_ohm=100))
    assert r.verdict == Verdict.HALF_SHORT
    assert abs(r.load_mohm - 100000) <= 10000


def test_above_150_ohm_is_a_load_not_a_fault():
    assert run_probe(Drone(cap_uf=470, load_ohm=300)).verdict == Verdict.OK


@pytest.mark.parametrize('cap', [10, 1000, 2200, 4700])
def test_reversed_leads_diode_clamp(cap):
    r = run_probe(Drone(cap_uf=cap, reversed=True))
    assert r.verdict == Verdict.REVERSED
    assert probe.DIODE_MIN_MV <= r.v_low_mv <= probe.DIODE_MAX_MV


def test_reversed_signature_barely_moves_between_sources():
    hi, lo, hi2 = probe_samples(Drone(cap_uf=1000, reversed=True))
    assert lo[-1] * 1000 < hi2[-1] * probe.DIODE_MAX_RATIO_PERMILLE


def test_nothing_attached_is_open():
    assert run_probe(None).verdict == Verdict.OPEN


@pytest.mark.parametrize('cap', [20, 100, 470, 1000, 2000, 5000, 10000])
def test_capacitance_estimate_within_10_percent(cap):
    r = run_probe(Drone(cap_uf=cap))
    assert r.verdict == Verdict.OK
    assert abs(r.cap_uf - cap) <= cap * 0.10


def test_1s_flight_controller_load_is_ok_on_1s_only():
    whoop = Drone.whoop_1s()          # ~75 Ohm at 3 V: the FC is running
    assert run_probe(whoop, cells=1).verdict == Verdict.OK
    assert run_probe(whoop, cells=4).verdict == Verdict.HALF_SHORT


def test_1s_still_catches_hard_faults():
    assert run_probe(Drone(cap_uf=60, load_ohm=5), cells=1).verdict == Verdict.HALF_SHORT
    assert run_probe(Drone(cap_uf=60, short_ohm=0.2), cells=1).verdict == Verdict.SHORT


def test_no_big_cap_warning_rule():
    assert probe.no_big_cap(60, 4)
    assert probe.no_big_cap(99, 6)
    assert not probe.no_big_cap(100, 4)
    assert not probe.no_big_cap(60, 3)


def test_load_math_and_constants():
    assert probe.load_mohm(9, 100) == 300            # 0.3 Ohm on 100 Ohm reads 9 mV
    assert probe.load_mohm(3000, 100) == -1
    assert probe.PROBE_SRC_MV * 1000 // (probe.PROBE_R_LOW_OHM * 1000) <= 30   # <= 30 mA (SPEC §3)
    assert probe.PROBE_TOTAL_MS <= 400
