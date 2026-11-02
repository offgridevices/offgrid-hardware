import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import probe  # noqa: E402
from model.machine import Outputs, ProbeSrc  # noqa: E402
from model.sim_world import Balance, Drone, Pack, Rig, World  # noqa: E402


def probe_samples(drone):
    """Drive a World's probe source exactly as the machine does and return
    the (1 kOhm, 100 Ohm, 1 kOhm again) VOUT_low sample arrays."""
    w = World(pack=None, drone=drone, usb=True)
    hi, lo, hi2 = [], [], []
    for k in range(probe.PROBE_TOTAL_MS):
        low = probe.PROBE_T_HIGH_MS <= k < probe.PROBE_T_FIRST2_MS
        w.apply(Outputs(probe_src=ProbeSrc.R100 if low else ProbeSrc.R1K), 1)
        v = w.sense().vout_low_mv
        (lo if low else hi if k < probe.PROBE_T_HIGH_MS else hi2).append(v)
    return hi, lo, hi2


def run_probe(drone, cells=4):
    hi, lo, hi2 = probe_samples(drone)
    return probe.classify(hi, lo, hi2, cells)


def make_rig(cells=4, v=4.0, drone='quad', balance=True, **kw):
    pack = Pack.of(cells, v) if cells else None
    if drone == 'quad':
        drone = Drone.quad()
    bal = Balance() if (balance and cells and cells <= 8) else None
    return Rig(World(pack=pack, drone=drone, balance=bal, **kw))


@pytest.fixture
def rig():
    return make_rig().boot()
