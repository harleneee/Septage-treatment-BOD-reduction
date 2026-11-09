"""Interactive Streamlit UI.  Run: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

from septage import animation as anim
from septage import model as m
from septage import plots
from septage.presets import PAPER_EXAMPLE

st.set_page_config(page_title="Septage BOD Simulation", layout="wide")

# ------------------------------------------------------------------ look
# Visual layer only ("engineering datasheet"): colours and fonts are set in
# .streamlit/config.toml; this CSS adds what the theme cannot express —
# uppercase section labels, mono numbers, hairline rules, flat readouts.
# It changes no widget, label or value.
STYLE = """
<style>
:root { --paper:#F5F3EE; --panel:#ECE9E1; --ink:#1B1E22; --ink2:#5A5F66; --rule:#C9C4B8;
        --accent:#C2410C; --pass:#2F6B3A; --fail:#A61B1B;
        --cond:"IBM Plex Sans Condensed", "Arial Narrow", sans-serif;
        --mono:"IBM Plex Mono", Consolas, monospace; }

/* title block: condensed heading over a single hairline rule */
h1 { font-family:var(--cond) !important; font-weight:600 !important; font-size:40px !important;
     line-height:1.1 !important; letter-spacing:-0.005em; padding:0 0 .55rem !important;
     border-bottom:1px solid var(--rule); margin-bottom:1.6rem !important; }

/* sidebar: inputs grouped under small uppercase section labels with a hairline above */
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  font-family:var(--cond) !important; font-size:11.5px !important; font-weight:600 !important;
  text-transform:uppercase; letter-spacing:.06em; color:var(--ink2) !important;
  border-top:1px solid var(--rule); padding:1rem 0 .1rem !important; margin-top:.9rem !important; }
[data-testid="stWidgetLabel"] p { font-size:14px; }

/* every number and unit in mono: inputs, slider values, captions, inline values */
[data-testid="stNumberInputField"], [data-testid="stSliderThumbValue"] p,
[data-testid="stSliderTickBar"] p, .main code, [data-testid="stMain"] code,
[data-testid="stCaptionContainer"] { font-family:var(--mono) !important; }
[data-testid="stMain"] code { background:none !important; color:inherit !important; padding:0 !important;
  font-size:.92em; }

/* sliders: thin ink track; accent only on the thumb and its value */
[data-testid="stSlider"] [role="group"] > div > div:first-child { height:2px !important;
  background:var(--ink) !important; }
[data-testid="stSlider"] [role="group"] > div > div:nth-child(2) > div:last-child,
[data-testid="stSliderThumbValue"] p { color:var(--accent) !important; font-size:12px; }
[data-testid="stSliderTickBar"] p { color:var(--ink2) !important; font-size:11px; }

/* buttons: square, text-forward. Primary = solid accent; secondary = text link style */
[data-testid="stBaseButton-primary"] { border-radius:2px !important; box-shadow:none !important;
  font-family:var(--cond); font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
[data-testid="stBaseButton-primary"] p { font-family:var(--cond); font-weight:600; }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] { background:transparent !important;
  border:none !important; box-shadow:none !important; color:var(--ink) !important; min-height:2rem; }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p { text-decoration:underline;
  text-decoration-color:var(--rule); text-underline-offset:4px; text-decoration-thickness:1px; }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover p { color:var(--accent);
  text-decoration-color:var(--accent); }

/* metric row as datasheet readouts: small uppercase label over a large mono value */
[data-testid="stMetric"] { background:none !important; border:none !important; padding:0 !important;
  box-shadow:none !important; }
[data-testid="stMetricLabel"] p, .readout-label { font-family:var(--cond) !important; font-size:11.5px !important;
  font-weight:600 !important; text-transform:uppercase; letter-spacing:.06em; color:var(--ink2) !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] p { font-family:var(--mono) !important;
  font-size:34px !important; font-weight:500 !important; color:var(--ink); letter-spacing:-0.01em; }
[data-testid="stMetricValue"] p span { font-size:15px; font-weight:400; color:var(--ink2) !important;
  letter-spacing:0; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] p { font-family:var(--mono) !important;
  font-size:12.5px !important; background:none !important; }

/* compliance result: one coloured indicator line, no box */
.readout-label { margin:.3rem 0 .45rem; }
.verdict { font-size:14.5px; line-height:1.45; margin-top:.35rem; }
.verdict .word { font-family:var(--cond); font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
.verdict .num { font-family:var(--mono); white-space:nowrap; }
.verdict.pass { color:var(--pass); } .verdict.fail { color:var(--fail); }

/* tabs: condensed uppercase labels, accent underline on the active tab, hairline below */
[data-testid="stTabs"] { margin-top:1.4rem; }
[data-testid="stTab"] p { font-family:var(--cond) !important; font-size:13px !important; font-weight:600 !important;
  text-transform:uppercase; letter-spacing:.06em; color:var(--ink2); }
[data-testid="stTab"][aria-selected="true"] p { color:var(--ink); }
[data-testid="stTab"] .react-aria-SelectionIndicator { background:var(--accent) !important; height:2px !important; }

/* notes and warnings: a hairline at the left instead of a filled box */
[data-testid="stAlertContainer"] { background:transparent !important; border:none !important;
  border-left:2px solid var(--rule) !important; border-radius:0 !important; padding:.2rem 0 .2rem .9rem !important; }
[data-testid="stAlertContainer"] p { color:var(--ink) !important; }

/* no drop shadows anywhere */
[data-testid="stDataFrame"], [data-testid="stImage"], img { box-shadow:none !important; }
</style>
"""
st.html(STYLE)

st.title("Septage treatment: BOD reduction")

# Widget values live in st.session_state (keyed below), so buttons can set them.
DEFAULTS = {"c0": 2000.0, "q": 50.0, "limit": m.DAO_2016_08_BOD_LIMIT,
            "rem_0": 5.0, "rem_1": 35.0, "rem_2": 92.0, "rem_3": 60.0,
            "kinetic": False, "reactor": "cstr", "k": 1.5, "vol": 200.0}
for key, val in DEFAULTS.items():
    st.session_state.setdefault(key, val)


def current_inputs():
    """Read the inputs from session state -> (Params, kinetic flag)."""
    ss = st.session_state
    rem = tuple(ss[f"rem_{i}"] / 100 for i in range(len(m.STAGE_NAMES)))
    p = m.Params(ss.c0, ss.q, rem, ss.limit, ss.k, ss.vol, ss.reactor)
    return p, ss.kinetic


def run_simulation():
    """'Run simulation': store the model results that the animation will play."""
    p, kin = current_inputs()
    run_id = st.session_state.get("anim_run", {}).get("payload", {}).get("run_id", 0) + 1
    st.session_state.anim_run = {"payload": anim.payload_from_params(p, kin, run_id),
                                 "inputs": (p, kin)}


def load_paper_example():
    st.session_state.c0 = PAPER_EXAMPLE["influent_bod"]
    for i, pct in enumerate(PAPER_EXAMPLE["removal_pct"]):
        st.session_state[f"rem_{i}"] = pct
    st.session_state.kinetic = False


sb = st.sidebar
sb.button("▶ Run simulation", type="primary", on_click=run_simulation, width="stretch")
sb.button("Load paper example", on_click=load_paper_example, width="stretch",
          help="C0 = 1000 mg/L; 1000 → 800 → 150 → 50 mg/L (95 % overall), screening set to 0 %")
sb.header("Inputs")
sb.number_input("Influent BOD (mg/L)", 10.0, 100000.0, step=50.0, key="c0")
sb.number_input("Flow (m³/day)", 1.0, 5000.0, step=5.0, key="q")
sb.number_input("Effluent limit (mg/L)", 1.0, 500.0, step=5.0, key="limit")
sb.subheader("Removal per stage (%)")
for i, n in enumerate(m.STAGE_NAMES):
    sb.slider(n, 0.0, 100.0, step=0.01, format="%.2f", key=f"rem_{i}")
sb.subheader("Biological stage model")
sb.checkbox("Use first-order kinetics", key="kinetic")
sb.selectbox("Reactor type", ["cstr", "pfr"], key="reactor")
sb.slider("Rate constant k (1/day)", 0.05, 10.0, step=0.05, key="k")
sb.number_input("Reactor volume (m³)", 1.0, 20000.0, step=10.0, key="vol")

p, kinetic = current_inputs()
limit = p.limit
if kinetic:
    st.caption(f"HRT = V/Q = {p.hrt:.2f} days → biological removal {m.kinetic_removal(p):.1%}")

s = m.summary(p, kinetic)
a, b, c, d = st.columns(4)
# Same values and text as before; ":gray[...]" only sets the unit in a lighter tone.
a.metric("Effluent BOD", f"{s['effluent_bod_mg_l']:.1f} :gray[mg/L]")
b.metric("Overall removal", f"{s['overall_removal_pct']:.2f} :gray[%]")
c.metric("Effluent load", f"{s['effluent_load_kg_day']:.2f} :gray[kg/day]",
         f"-{s['influent_load_kg_day'] - s['effluent_load_kg_day']:.1f} from {s['influent_load_kg_day']:.1f}")
# Compliance: one coloured indicator line (same verdict and limit), no box.
ok = s["meets_limit"]
d.html(f'<div class="readout-label">Effluent limit</div>'
       f'<div class="verdict {"pass" if ok else "fail"}">● <span class="word">'
       f'{"Meets" if ok else "FAILS"} DAO 2016-08 limit</span> <span class="num">'
       f'— C<sub>eff</sub> {s["effluent_bod_mg_l"]:.1f} {"≤" if ok else "&gt;"} {limit:g} mg/L</span></div>')

t0, t1, t2, t3, t4 = st.tabs(["Animation", "Stages", "Kinetics", "Sensitivity", "Literature comparison"])
with t0:
    run = st.session_state.get("anim_run")
    note = st.empty()  # always present, so the animation's position never shifts (no restart)
    if run is None:
        note.info("Set the inputs, then click **▶ Run simulation** in the sidebar to play the animation.")
    else:
        if run["inputs"] != (p, kinetic):
            note.caption("⚠️ Inputs changed — run again to animate the new values.")
        anim.render_animation(run["payload"])
with t1:
    st.dataframe(m.simulate(p, kinetic).round(2), width='stretch')
    v = m.verify(p, kinetic)
    # backticks only switch the numbers to the mono font (styled flat in STYLE)
    st.write(f"Closed-form check: simulated `{v['simulated']:.4f}` vs formula `{v['closed_form']:.4f}` "
             f"→ {'✅ match' if v['match'] else '❌ mismatch'}")
    l, r = st.columns(2)
    l.pyplot(plots.plot_profile(p, kinetic))
    r.pyplot(plots.plot_removed(p, kinetic))
with t2:
    st.pyplot(plots.plot_kinetics(p))
with t3:
    delta = st.slider("Change in removal (± percentage points)", 1, 20, 5) / 100
    st.dataframe(m.sensitivity(p, delta).round(2), width='stretch')
    st.pyplot(plots.plot_sensitivity(p, delta))
with t4:
    path = Path(__file__).parent / "data" / "literature_bod.csv"
    up = st.file_uploader("Reference CSV (source, stage, influent_bod_mg_l, bod_mg_l)", type="csv")
    ref = pd.read_csv(up) if up else pd.read_csv(path)
    if ref["source"].str.contains("PLACEHOLDER").any():
        st.warning("Using placeholder reference values. Replace data/literature_bod.csv with real "
                   "values from Baltazar et al. (2021) and Pausta et al. (2023).")
    tbl, stats = m.compare_with_literature(p, ref, kinetic)
    st.dataframe(tbl.round(2), width='stretch')
    st.write(f"**RMSE:** `{stats['rmse']:.2f} mg/L` · **Mean |% error|:** `{stats['mean_abs_pct_error']:.1f} %`")
    st.pyplot(plots.plot_comparison(tbl))
