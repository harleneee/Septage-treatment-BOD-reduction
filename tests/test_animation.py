"""The animation payload must only repeat what the model computed."""
import json

import numpy as np
import pandas as pd
import pytest

from septage import animation as anim
from septage import model as m
from septage.presets import PAPER_EXAMPLE


@pytest.mark.parametrize("kinetic", [False, True])
@pytest.mark.parametrize("reactor", ["cstr", "pfr"])
def test_payload_matches_model_output(kinetic, reactor):
    p = m.Params(reactor=reactor)
    payload = anim.payload_from_params(p, kinetic)
    table = m.simulate(p, kinetic)

    assert len(payload["stages"]) == len(table)
    for s, row in zip(payload["stages"], table.to_dict("records")):
        assert s["name"] == row["Stage"]
        assert s["removal_fraction"] == row["Removal fraction"]
        assert s["bod_in"] == row["BOD in (mg/L)"]
        assert s["bod_out"] == row["BOD out (mg/L)"]
        assert s["bod_removed"] == row["BOD removed (mg/L)"]
        assert s["load_removed"] == row["Load removed (kg/day)"]
        # labels use the same rounding as the app's table (DataFrame.round(2))
        assert float(s["bod_out_label"]) == np.round(row["BOD out (mg/L)"], 2)

    assert payload["c_eff"] == pytest.approx(m.closed_form(p, kinetic), rel=1e-12)
    summ = m.summary(p, kinetic)
    assert payload["passed"] == summ["meets_limit"]
    assert payload["overall_removal_pct"] == pytest.approx(summ["overall_removal_pct"])
    assert payload["load_out"] == pytest.approx(summ["effluent_load_kg_day"])
    if kinetic:
        assert payload["kinetics"]["tau"] == p.hrt and payload["kinetics"]["reactor"] == reactor
    else:
        assert payload["kinetics"] is None


def test_three_stage_table_works():
    rows = []
    c = 1000.0
    for name, r in [("Primary treatment", 0.2), ("Biological treatment", 0.8125), ("Polishing", 2 / 3)]:
        rows.append({"Stage": name, "Removal fraction": r, "BOD in (mg/L)": c, "BOD out (mg/L)": c * (1 - r),
                     "BOD removed (mg/L)": c * r, "Load out (kg/day)": 0.0, "Load removed (kg/day)": 0.0})
        c *= 1 - r
    payload = anim.build_animation_payload(pd.DataFrame(rows), 1000.0, 50.0, 60.0)
    assert [s["kind"] for s in payload["stages"]] == ["settling", "biological", "polishing"]
    assert payload["c_eff_label"] == "50.00" and payload["passed"]
    assert "__PAYLOAD__" not in anim.build_html(payload)


def test_paper_example_reproduces_conceptual_model():
    p = m.Params(influent_bod=PAPER_EXAMPLE["influent_bod"],
                 removal=tuple(x / 100 for x in PAPER_EXAMPLE["removal_pct"]))
    outs = m.simulate(p)["BOD out (mg/L)"].tolist()
    assert outs == pytest.approx([1000, 800, 150, 50])
    assert m.summary(p)["overall_removal_pct"] == pytest.approx(95.0)


def test_edge_cases_zero_full_and_huge():
    # 0 % stage passes water through; 100 % stage empties it; no division by zero
    p = m.Params(influent_bod=50000, removal=(0.0, 1.0, 0.5, 0.0))
    payload = anim.payload_from_params(p, False)
    s = payload["stages"]
    assert "no removal" in s[0]["narration"]
    assert s[0]["particles_in"] == s[0]["particles_out"] == anim.MAX_PARTICLES
    assert s[1]["particles_out"] == 0 and s[2]["particles_in"] == 0
    assert payload["c_eff"] == 0 and payload["passed"]
    json.dumps(payload)  # serialisable (no NaN/inf)
    # tiny but non-zero BOD keeps at least one particle
    assert anim.particle_count(30, 50000) == 1


def test_html_is_self_contained():
    html = anim.build_html(anim.payload_from_params(m.Params(), False))
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in html and "<script src" not in html
    assert "requestAnimationFrame" in html
