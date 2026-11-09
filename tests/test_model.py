import math
from dataclasses import replace

import pandas as pd
import pytest

from septage import model as m


def test_stage_chain_matches_closed_form():
    p = m.Params()
    assert m.verify(p)["match"]
    assert m.verify(p, kinetic=True)["match"]


def test_hand_calculation():
    p = m.Params(influent_bod=1000, removal=(0.1, 0.5, 0.9, 0.5))
    assert m.simulate(p)["BOD out (mg/L)"].iloc[-1] == pytest.approx(1000 * 0.9 * 0.5 * 0.1 * 0.5)


def test_mass_balance():
    p = m.Params()
    df = m.simulate(p)
    assert df["Load removed (kg/day)"].sum() + df["Load out (kg/day)"].iloc[-1] == pytest.approx(
        m.load_kg_day(p.influent_bod, p.flow))


def test_load_units():
    assert m.load_kg_day(2000, 50) == pytest.approx(100.0)


def test_kinetics_cstr_and_pfr():
    p = m.Params(k=2.0, volume=100, flow=50)  # tau = 2 d
    assert m.kinetic_removal(p) == pytest.approx(1 - 1 / 5)
    assert m.kinetic_removal(replace(p, reactor="pfr")) == pytest.approx(1 - math.exp(-4))


def test_longer_retention_lowers_bod_and_higher_flow_raises_it():
    p = m.Params()
    assert m.closed_form(replace(p, volume=400), True) < m.closed_form(p, True)
    assert m.closed_form(replace(p, flow=100), True) > m.closed_form(p, True)


def test_limit_check():
    assert m.summary(m.Params(influent_bod=100, removal=(0, 0, 0.9, 0)))["meets_limit"]
    assert not m.summary(m.Params(influent_bod=1000, removal=(0, 0, 0, 0)))["meets_limit"]


def test_paper_example_meets_50_mg_l_limit():
    # 1000 -> 800 -> 150 -> 50 mg/L; float round-off gives 50.00000000000001,
    # which must still count as meeting the 50 mg/L limit
    p = m.Params(influent_bod=1000, removal=(0, 0.2, 0.8125, 2 / 3), limit=50)
    assert m.summary(p)["meets_limit"] is True


def test_sensitivity_ranks_biggest_lever_first_and_matches_derivative():
    p = m.Params()
    s = m.sensitivity(p, 0.01)
    # |dC/dr| = C_out/(1-r_i) is largest for the stage with the highest removal (biological)
    assert s.iloc[0]["Stage"] == m.STAGE_NAMES[2]
    row = s[s["Stage"] == m.STAGE_NAMES[1]].iloc[0]
    assert row["Change for +delta (mg/L)"] == pytest.approx(row["dC/dr (mg/L per unit r)"] * 0.01)


def test_error_metrics():
    assert m.percent_error(110, 100) == pytest.approx(10.0)
    assert m.rmse([1, 2, 3], [1, 2, 5]) == pytest.approx(math.sqrt(4 / 3))


def test_compare_with_literature():
    p = m.Params(influent_bod=1000, removal=(0, 0.5, 0.9, 0))
    ref = pd.DataFrame({"source": ["x"], "stage": [m.STAGE_NAMES[1]], "bod_mg_l": [500.0]})
    tbl, stats = m.compare_with_literature(p, ref)
    assert tbl["percent error (%)"].iloc[0] == pytest.approx(0.0)
    assert stats["rmse"] == pytest.approx(0.0)


def test_invalid_params():
    with pytest.raises(ValueError):
        m.Params(removal=(0.1, 0.2, 1.5, 0.1))
    with pytest.raises(ValueError):
        m.Params(flow=0)
