"""Battery checker (ARCHITECTURE §3 rows, §4 battery rows)."""
import pytest

from model import battery as B
from model.battery import BalanceState, Chem, Delta, Storage, Warn
from model.sim_world import Balance, Pack, World


def taps_for(cells_v, shift=0, broken=(), other=None):
    main = Pack(list(cells_v))
    bal = Balance(pack=Pack(list(other)) if other else None, shift=shift, broken=list(broken))
    w = World(pack=main, balance=bal)
    return int(main.ocv * 1000), w.taps()


def check(cells_v, **kw):
    vin, taps = taps_for(cells_v, **kw)
    return B.analyse(vin, taps)


def kinds(info):
    return [w[0] for w in info.warnings]


@pytest.mark.parametrize('n', range(1, 15))
def test_cell_count_from_vin_full_lipo_1s_to_14s(n):
    g = B.guess_cells(n * 4200)
    assert g.cells == n


@pytest.mark.parametrize('n', range(1, 15))
def test_cell_count_from_vin_full_lihv_1s_to_14s(n):
    assert B.guess_cells(n * 4350).cells == n


@pytest.mark.parametrize('n', range(1, 8))
def test_storage_charge_unambiguous_up_to_7s(n):
    g = B.guess_cells(n * 3850)
    assert g.cells == n and not g.ambiguous


@pytest.mark.parametrize('n', range(9, 15))
def test_storage_charge_9s_up_is_flagged_ambiguous_without_balance(n):
    g = B.guess_cells(n * 3850)
    assert g.ambiguous and n in g.candidates


@pytest.mark.parametrize('n', range(1, 7))
def test_balance_lead_settles_cell_count_1s_to_6s(n):
    info = check([3.85] * n)
    assert info.cells == n and info.cells_certain and info.balance == BalanceState.OK


def test_lihv_vs_lipo_ambiguity():
    # 17.4 V: 4S LiHV full, or 5S LiPo nearly empty
    g = B.guess_cells(17400)
    assert g.ambiguous and g.candidates[:2] == [4, 5] and g.cells == 4
    info = B.analyse(17400, [0] * 8)
    assert info.chem == Chem.LIHV_OR_HIGH
    # the balance lead resolves it
    info = check([4.35] * 4)
    assert info.cells == 4 and info.cells_certain and info.chem == Chem.LIHV_OR_HIGH
    assert info.soc_pct == 100
    info5 = check([3.48] * 5)
    assert info5.cells == 5 and info5.chem == Chem.LIPO and info5.soc_pct < 10


def test_overcharged_for_lipo_only_vs_overcharged():
    info = check([4.20, 4.31, 4.20, 4.20])
    assert (Warn.OVERCHARGED_LIPO, 1, 4310) in info.warnings
    assert info.chem == Chem.LIHV_OR_HIGH
    info = check([4.45, 4.35, 4.35, 4.35])
    assert info.warnings[0][:2] == (Warn.OVERCHARGED, 0)


# the 2S-6S sockets are keyed, so a plug cannot sit a pin off; the check stays
# as a guard (a lead plugged into a bigger pack's socket through an adapter)
@pytest.mark.parametrize('cells,shift', [(4, 1), (4, 2), (5, 1), (3, 3), (2, 3), (1, 3)])
def test_balance_plug_shifted_reads_correctly(cells, shift):
    cv = [3.80 + 0.01 * i for i in range(cells)]
    info = check(cv, shift=shift)
    assert info.bal.shift == shift
    assert info.cells == cells and info.cells_certain
    assert info.bal.cells_mv == [int(round(v * 1000)) for v in cv]
    assert not info.warnings


def test_balance_from_another_pack_same_count():
    info = check([4.20] * 4, other=[3.80] * 4)
    assert info.balance == BalanceState.OTHER_PACK
    assert kinds(info)[0] == Warn.OTHER_PACK
    assert info.lo_idx == -1                  # no per-cell verdicts from someone else's cells


def test_balance_from_another_pack_different_count():
    assert check([4.0] * 6, other=[4.0] * 4).balance == BalanceState.OTHER_PACK
    assert check([4.0] * 3, other=[3.7] * 4).balance == BalanceState.OTHER_PACK


def test_sum_versus_vin_mismatch_over_2_percent():
    vin, taps = taps_for([3.9] * 4)
    assert B.analyse(vin, taps).balance == BalanceState.OK
    assert B.analyse(vin + 400, taps).balance == BalanceState.OTHER_PACK     # 2.6 %
    assert B.analyse(vin + 250, taps).balance == BalanceState.OK             # 1.6 %


def test_broken_balance_wire_mid_pack():
    info = check([3.9] * 6, broken=[3])
    assert info.balance == BalanceState.BROKEN_WIRE and info.bal.broken_pin == 4
    assert Warn.BROKEN_WIRE in kinds(info)


def test_broken_top_balance_wire_is_count_mismatch():
    info = check([3.9] * 4, broken=[4])
    assert info.balance == BalanceState.BROKEN_WIRE
    assert info.cells == 4 and not info.cells_certain


@pytest.mark.parametrize('spread,verdict', [(0, Delta.BALANCED), (20, Delta.BALANCED), (21, Delta.DRIFTING),
                                            (50, Delta.DRIFTING), (51, Delta.OUT_OF_BALANCE),
                                            (120, Delta.OUT_OF_BALANCE)])
def test_delta_verdicts(spread, verdict):
    info = check([3.90, 3.90 + spread / 1000, 3.90, 3.90])
    assert info.delta_mv == spread and info.delta == verdict


def test_lowest_and_highest_marked():
    info = check([3.91, 3.95, 3.88, 3.92])
    assert info.lo_idx == 2 and info.hi_idx == 1


def test_overdischarged_cell_names_the_cell():
    info = check([3.60, 3.60, 2.71, 3.60])
    assert info.warnings[0] == (Warn.OVERDISCHARGED, 2, 2710)


def test_dead_cell_beats_everything():
    info = check([3.70, 2.30, 3.70, 3.70])
    assert info.warnings[0][:2] == (Warn.DEAD_CELL, 1)
    assert Warn.OUT_OF_BALANCE in kinds(info)


def test_soc_tables():
    assert B.soc_pct(4200, B.OCV_LIPO) == 100
    assert B.soc_pct(3270, B.OCV_LIPO) == 0
    assert B.soc_pct(3840, B.OCV_LIPO) == 50
    assert B.soc_pct(4350, B.OCV_LIHV) == 100
    for table in (B.OCV_LIPO, B.OCV_LIHV):
        vals = [B.soc_pct(v, table) for v in range(3200, 4400, 5)]
        assert vals == sorted(vals)


@pytest.mark.parametrize('v,hint', [(3.82, Storage.AT), (3.80, Storage.AT), (3.85, Storage.AT),
                                    (4.10, Storage.ABOVE), (3.65, Storage.BELOW)])
def test_storage_hint(v, hint):
    assert check([v] * 4).storage == hint


def test_balance_lead_only():
    taps = World(pack=Pack.of(3, 3.9), balance=Balance()).taps()
    info = B.analyse(0, taps)
    assert info.balance_only and info.cells == 3 and info.soc_pct > 0


def test_ir_estimate_needs_2a_step_and_flags_sag():
    assert B.ir_estimate(16800, 400, 16700, 1900, 4) is None          # dI 1.5 A: not trusted
    r, sag, warn = B.ir_estimate(16800, 400, 16620, 10400, 4)        # 18 mOhm pack
    assert r == 18 and sag == 180 and not warn
    r, sag, warn = B.ir_estimate(16800, 400, 14900, 10400, 4)        # 190 mOhm pack
    assert r == 190 and warn


def test_no_battery():
    info = B.analyse(0, [0] * 8)
    assert not info.main_present and info.cells == 0 and not info.bal.present
