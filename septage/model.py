"""BOD reduction model for septage treatment.

Stages: screening/grit -> primary settling -> biological -> polishing/disinfection.
Units: concentration mg/L, flow m3/day, volume m3, k in 1/day, load kg/day.
(mg/L * m3/day = g/day, so kg/day = mg/L * m3/day / 1000.)
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

STAGE_NAMES = [
    "Screening & grit removal",
    "Primary settling",
    "Biological treatment",
    "Polishing & disinfection",
]

# DENR DAO 2016-08 BOD effluent limit (mg/L). The limit depends on the receiving
# water class; 50 mg/L is used as the default. VERIFY against the DAO table for
# your water class and change it in Params if needed.
DAO_2016_08_BOD_LIMIT = 50.0


@dataclass(frozen=True)
class Params:
    influent_bod: float = 2000.0  # mg/L
    flow: float = 50.0  # m3/day
    removal: tuple = (0.05, 0.35, 0.92, 0.60)  # fractional removal per stage
    limit: float = DAO_2016_08_BOD_LIMIT  # mg/L
    # Kinetic (biological stage) parameters
    k: float = 1.5  # first-order rate constant, 1/day
    volume: float = 200.0  # reactor volume, m3
    reactor: str = "cstr"  # "cstr" or "pfr"

    def __post_init__(self):
        if len(self.removal) != 4:
            raise ValueError("removal needs exactly 4 values")
        if any(not 0 <= r <= 1 for r in self.removal):
            raise ValueError("removal fractions must be in [0, 1]")
        if self.influent_bod < 0 or self.flow <= 0:
            raise ValueError("influent_bod must be >= 0 and flow > 0")
        if self.k < 0 or self.volume < 0:
            raise ValueError("k and volume must be >= 0")
        if self.reactor not in ("cstr", "pfr"):
            raise ValueError("reactor must be 'cstr' or 'pfr'")

    @property
    def hrt(self) -> float:
        """Hydraulic retention time (days) = V / Q."""
        return self.volume / self.flow


def load_kg_day(conc_mg_l: float, flow_m3_day: float) -> float:
    return conc_mg_l * flow_m3_day / 1000.0


def kinetic_removal(p: Params) -> float:
    """Fractional removal in the biological stage from first-order kinetics.

    CSTR: Ce = C0 / (1 + k*tau)      PFR: Ce = C0 * exp(-k*tau)
    """
    kt = p.k * p.hrt
    remaining = 1.0 / (1.0 + kt) if p.reactor == "cstr" else float(np.exp(-kt))
    return 1.0 - remaining


def simulate(p: Params, kinetic: bool = False) -> pd.DataFrame:
    """Stage-by-stage simulation. If kinetic, the biological stage uses
    first-order kinetics instead of the fixed removal fraction."""
    removal = list(p.removal)
    if kinetic:
        removal[2] = kinetic_removal(p)
    rows, c = [], p.influent_bod
    for name, r in zip(STAGE_NAMES, removal):
        c_in = c
        c = c_in * (1 - r)
        rows.append(
            {
                "Stage": name,
                "Removal fraction": r,
                "BOD in (mg/L)": c_in,
                "BOD out (mg/L)": c,
                "BOD removed (mg/L)": c_in - c,
                "Load out (kg/day)": load_kg_day(c, p.flow),
                "Load removed (kg/day)": load_kg_day(c_in - c, p.flow),
                "Cumulative removal (%)": 100 * (1 - c / p.influent_bod)
                if p.influent_bod > 0
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def closed_form(p: Params, kinetic: bool = False) -> float:
    """Effluent BOD from C_out = C0 * prod(1 - r_i)."""
    removal = list(p.removal)
    if kinetic:
        removal[2] = kinetic_removal(p)
    return p.influent_bod * float(np.prod(1 - np.array(removal)))


def verify(p: Params, kinetic: bool = False, tol: float = 1e-9) -> dict:
    sim = float(simulate(p, kinetic)["BOD out (mg/L)"].iloc[-1])
    cf = closed_form(p, kinetic)
    return {"simulated": sim, "closed_form": cf, "abs_diff": abs(sim - cf),
            "match": abs(sim - cf) <= tol * max(1.0, abs(cf))}


def summary(p: Params, kinetic: bool = False) -> dict:
    df = simulate(p, kinetic)
    out = float(df["BOD out (mg/L)"].iloc[-1])
    return {
        "effluent_bod_mg_l": out,
        "overall_removal_pct": float(df["Cumulative removal (%)"].iloc[-1]),
        "influent_load_kg_day": load_kg_day(p.influent_bod, p.flow),
        "effluent_load_kg_day": load_kg_day(out, p.flow),
        "limit_mg_l": p.limit,
        "meets_limit": out <= p.limit,
    }


def sensitivity(p: Params, delta: float = 0.05) -> pd.DataFrame:
    """One-at-a-time sensitivity of effluent BOD to each stage's removal rate.

    Each removal r_i is moved by +/- `delta` (absolute, clipped to [0, 1]). Because
    C_out = C0 * prod(1 - r_i) is linear in each r_i, dC/dr_i = -C_out/(1 - r_i)
    exactly; stages are ranked by the resulting BOD swing (mg/L).
    """
    base = closed_form(p)
    rows = []
    for i, name in enumerate(STAGE_NAMES):
        r = list(p.removal)
        r[i] = min(1.0, r[i] + delta)
        new = closed_form(replace(p, removal=tuple(r)))
        r_lo = list(p.removal)
        r_lo[i] = max(0.0, p.removal[i] - delta)
        low = closed_form(replace(p, removal=tuple(r_lo)))
        d = -base / (1 - p.removal[i]) if p.removal[i] < 1 else float("nan")
        rows.append(
            {
                "Stage": name,
                "Base removal": p.removal[i],
                f"BOD if +{delta:.0%} (mg/L)": new,
                f"BOD if -{delta:.0%} (mg/L)": low,
                "Change for +delta (mg/L)": new - base,
                "Swing (mg/L)": low - new,
                "dC/dr (mg/L per unit r)": d,
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("Swing (mg/L)", ascending=False).reset_index(drop=True)


def kinetic_grid(p: Params, hrts, flows=None) -> pd.DataFrame:
    """Effluent BOD (mg/L) vs retention time and (optionally) flow rate.

    With a fixed volume, flow changes HRT; here we vary flow and set
    volume = hrt * flow so each (hrt, flow) pair is explicit.
    """
    flows = [p.flow] if flows is None else flows
    rows = []
    for q in flows:
        for t in hrts:
            q_p = replace(p, flow=q, volume=t * q)
            rows.append({"flow": q, "hrt": t, "effluent_bod": closed_form(q_p, kinetic=True)})
    return pd.DataFrame(rows)


# ---------- comparison with published data ----------

def percent_error(sim, obs):
    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    return 100 * (sim - obs) / obs


def rmse(sim, obs):
    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    return float(np.sqrt(np.mean((sim - obs) ** 2)))


def compare_with_literature(p: Params, ref: pd.DataFrame, kinetic: bool = False) -> tuple:
    """Compare simulated BOD per stage against reference data.

    `ref` columns: source, stage (one of STAGE_NAMES), bod_mg_l (BOD *leaving* that stage).
    The simulation is run from each source's own influent BOD if an
    `influent_bod_mg_l` column is present, else from p.influent_bod.
    Returns (per-row table, {'rmse': ..., 'mean_abs_pct_error': ...}).
    """
    out = []
    for _, row in ref.iterrows():
        c0 = row["influent_bod_mg_l"] if "influent_bod_mg_l" in ref.columns and pd.notna(
            row.get("influent_bod_mg_l")) else p.influent_bod
        sim = simulate(replace(p, influent_bod=float(c0)), kinetic)
        s = float(sim.loc[sim["Stage"] == row["stage"], "BOD out (mg/L)"].iloc[0])
        out.append({"source": row["source"], "stage": row["stage"],
                    "observed (mg/L)": row["bod_mg_l"], "simulated (mg/L)": s,
                    "percent error (%)": float(percent_error(s, row["bod_mg_l"]))})
    tbl = pd.DataFrame(out)
    stats = {"rmse": rmse(tbl["simulated (mg/L)"], tbl["observed (mg/L)"]),
             "mean_abs_pct_error": float(tbl["percent error (%)"].abs().mean())}
    return tbl, stats
