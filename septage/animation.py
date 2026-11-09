"""Animated side-view of the treatment train.

The animation never computes BOD itself: `build_animation_payload` copies the
numbers out of the model's stage table (`model.simulate`) into a JSON-friendly
dict, and `render_animation` injects that dict into a self-contained
HTML/SVG/JavaScript page (septage/animation.html, no external libraries).

Display strings (e.g. "1235.00") are formatted here in Python with the same
rounding as the app's stage table (`DataFrame.round(2)`), so the animated
counters land on exactly the numbers shown in the table.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import model as m

MAX_PARTICLES = 250  # particles drawn for the influent; illustrative only
TEMPLATE = Path(__file__).with_name("animation.html")


# ---------------------------------------------------------------- helpers

def fmt(value: float) -> str:
    """Same rounding as the stage table (DataFrame.round(2) uses np.round)."""
    return f"{float(np.round(value, 2)):.2f}"


def fmt_pct(fraction: float) -> str:
    """0.8125 -> '81.25', 0.35 -> '35', 2/3 -> '66.67'."""
    return f"{fraction * 100:.2f}".rstrip("0").rstrip(".")


def particle_count(c: float, c0: float) -> int:
    """Particles proportional to BOD, with MAX_PARTICLES at the influent.

    Any water that still has BOD keeps at least 1 particle, so a very small
    BOD (e.g. 30 mg/L out of 50 000) does not look like perfectly clean water.
    Only BOD = 0 gives 0 particles.
    """
    if c0 <= 0 or c <= 0:
        return 0
    return max(1, round(MAX_PARTICLES * c / c0))


def stage_kind(name: str) -> str:
    """Pick the drawing for a stage from its name (works for 3 or 4 stages)."""
    s = name.lower()
    if "screen" in s or "grit" in s:
        return "screening"
    if "settl" in s or "primary" in s or "sediment" in s or "clarif" in s:
        return "settling"
    if "biolog" in s or "aerat" in s or "secondary" in s or "reactor" in s:
        return "biological"
    if "polish" in s or "disinfect" in s or "tertiary" in s or "uv" in s or "chlor" in s:
        return "polishing"
    return "generic"


STORY = {
    "screening": "bar screens catch rags and debris; grit settles in the channel",
    "settling": "heavy solids sink and form a sludge layer that is piped to drying beds",
    "biological": "microorganisms break down dissolved organics",
    "polishing": "final polishing and disinfection remove the remaining organics",
    "generic": "treatment removes organic matter",
}


# ---------------------------------------------------------------- payload

def build_animation_payload(stage_table: pd.DataFrame, c0: float, flow: float,
                            limit: float, kinetics: dict | None = None,
                            run_id: int = 0) -> dict:
    """Package model output for the animation.

    stage_table: output of `model.simulate` (any number of rows/stages).
    kinetics:    None for fixed-removal mode, else
                 {"reactor": "cstr"|"pfr", "tau": days, "k": 1/day}.
    run_id:      changes on every "Run simulation" click so the animation restarts.
    """
    stages = []
    for row in stage_table.to_dict("records"):
        name = str(row["Stage"])
        kind = stage_kind(name)
        r = float(row["Removal fraction"])
        c_in, c_out = float(row["BOD in (mg/L)"]), float(row["BOD out (mg/L)"])
        removed = float(row["BOD removed (mg/L)"])

        if c_in <= 0:
            text = f"{name}: no BOD left to remove — water passes through at 0.00 mg/L"
        elif r == 0:
            text = f"{name}: no removal at this stage — water passes through at {fmt(c_in)} mg/L"
        else:
            text = (f"{name}: {STORY[kind]} — {fmt(c_in)} → {fmt(c_out)} mg/L "
                    f"(−{fmt(removed)} mg/L, {fmt_pct(r)}%)")
            if kind == "biological" and kinetics:
                text += (f" · first-order kinetics, τ = {kinetics['tau']:.2f} d, "
                         f"k = {kinetics['k']:.2f} d⁻¹")

        stages.append({
            "name": name,
            "kind": kind,
            "removal_fraction": r,
            "bod_in": c_in,
            "bod_out": c_out,
            "bod_removed": removed,
            "load_in": m.load_kg_day(c_in, flow),
            "load_out": float(row["Load out (kg/day)"]),
            "load_removed": float(row["Load removed (kg/day)"]),
            "bod_in_label": fmt(c_in),
            "bod_out_label": fmt(c_out),
            "removed_label": fmt(removed),
            "pct_label": fmt_pct(r),
            "particles_in": particle_count(c_in, c0),
            "particles_out": particle_count(c_out, c0),
            "narration": text,
        })

    c_eff = stages[-1]["bod_out"] if stages else c0
    overall = 100 * (1 - c_eff / c0) if c0 > 0 else 0.0
    passed = c_eff <= limit  # same test as model.summary
    load_in, load_out = m.load_kg_day(c0, flow), m.load_kg_day(c_eff, flow)
    sign = "≤" if passed else ">"
    verdict = f"C_eff = {fmt(c_eff)} mg/L {sign} {limit:g} mg/L (DAO 2016-08)"

    kin = None
    if kinetics:
        kin = {"reactor": kinetics["reactor"], "tau": float(kinetics["tau"]),
               "k": float(kinetics["k"]), "tau_label": f"{kinetics['tau']:.2f}",
               "k_label": f"{kinetics['k']:.2f}"}

    return {
        "run_id": run_id,
        "c0": float(c0), "c0_label": fmt(c0),
        "c_eff": c_eff, "c_eff_label": fmt(c_eff),
        "flow": float(flow), "flow_label": f"{flow:g}",
        "limit": float(limit), "limit_label": f"{limit:g}",
        "overall_removal_pct": overall, "overall_label": f"{overall:.2f}",
        "load_in": load_in, "load_out": load_out,
        "load_in_label": fmt(load_in), "load_out_label": fmt(load_out),
        "passed": bool(passed),
        "verdict": verdict,
        "mode": "kinetic" if kin else "fixed",
        "kinetics": kin,
        "particles_c0": particle_count(c0, c0),
        "stages": stages,
        "narration_arrival": (f"Arrival: a vacuum truck discharges septage into the receiving tank — "
                              f"BOD₀ = {fmt(c0)} mg/L at Q = {flow:g} m³/day "
                              f"({fmt(load_in)} kg BOD/day)."),
        "narration_outfall": (f"Outfall: treated water enters the river — {verdict}: "
                              + ("meets the effluent limit." if passed
                                 else "exceeds the effluent limit.")),
    }


def payload_from_params(p: m.Params, kinetic: bool, run_id: int = 0) -> dict:
    """Run the existing model and build the payload from its output."""
    kin = {"reactor": p.reactor, "tau": p.hrt, "k": p.k} if kinetic else None
    return build_animation_payload(m.simulate(p, kinetic), p.influent_bod, p.flow,
                                   p.limit, kin, run_id)


# ---------------------------------------------------------------- rendering

def build_html(payload: dict) -> str:
    """Insert the payload into the HTML template as JSON."""
    data = json.dumps(payload).replace("</", "<\\/")  # keep </script> out of the JSON
    return TEMPLATE.read_text(encoding="utf-8").replace("__PAYLOAD__", data)


# Fixed frame height (px).  Chosen so the whole animation — controls, scene,
# narration, tally and summary — fits in the visible area of a 1366x768 laptop
# browser window (about 650 px tall) once the page is scrolled to the tabs.
# Inside the frame the 1600x900 scene scales to fit, so nothing is ever cut off.
ANIMATION_HEIGHT = 640


def render_animation(payload: dict, height: int = ANIMATION_HEIGHT) -> None:
    """Show the animation full-width in a fixed-height frame (no inner scrolling:
    the page inside is exactly the frame's height and never overflows)."""
    import streamlit as st
    st.iframe(build_html(payload), width="stretch", height=height)
