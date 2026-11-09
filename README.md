# Simulating the Cleaning of Household Sewage: BOD Reduction from Septic Tanks to Treated Water

BCS43 Computational Science · Bautista, De Castro, Desacola

Simulates BOD through four stages: screening & grit → primary settling → biological → polishing & disinfection.

## Model
- **Basic:** each stage removes a fixed fraction: `C_i = C_{i-1}(1 - r_i)`.
- **Closed form (verification):** `C_out = C0 · Π(1 - r_i)`.
- **Extended (biological stage):** first-order kinetics with `τ = V/Q`.
  CSTR: `Ce = C0/(1 + kτ)`; PFR: `Ce = C0·exp(-kτ)`.
- **Load:** `kg/day = mg/L × m³/day ÷ 1000`.
- **Compliance:** effluent BOD ≤ limit (default 50 mg/L; **verify the value for your water class in DENR DAO 2016-08**).
- **Sensitivity:** effluent BOD swing for ± change in each stage's removal.
- **Literature comparison:** percent error and RMSE vs `data/literature_bod.csv`.

`data/literature_bod.csv` columns: `source, stage, influent_bod_mg_l, bod_mg_l` (BOD leaving that stage).
Sources:
- **Maynilad Water Services (2006)** — Project 7 sewage/septage treatment plant EMP, Table 1.1 (design values):
  raw septage 2,752 mg/L → 963 mg/L after screening/grit/pre-aerated equalization → 193 mg/L after UASB + SBR.
  Design projections, not measurements.
- **Singh et al. (2023)**, *Adv. Environ. Technol.* 9(4):322–328 — lab hybrid constructed wetland,
  mean influent 2,395.6 mg/L → effluent 41.87 mg/L (measured).
- **Antonio (2011)** (IWA-7739) — Dumaguete pond + wetland system, design influent 2,500 mg/L,
  measured effluent 2 mg/L.

The default inputs (2000 mg/L, removals 5/35/92/60 %, k = 1.5/day, V = 200 m³) are illustrative.

## Animation tab
Click **▶ Run simulation** to play a two-tier side view: households drain into their own septic
tanks (top; narrative only, no BOD values), a vacuum truck pumps one out and hauls the septage to the
facility, then the treatment train below (`septage/animation.py` builds the
data from `model.simulate`; `septage/animation.html` draws it with plain SVG + JavaScript, no internet needed).
Water colour (log scale of BOD) and particle count follow the model's numbers; particles are illustrative.
**Load paper example** sets C0 = 1000 mg/L and removals 0 / 20 / 81.25 / 66.67 % → 1000 → 800 → 150 → 50 mg/L.

## Run
```
pip install -r requirements.txt
python -m pytest            # tests
python run_report.py        # tables + figures into ./output
streamlit run app.py        # interactive UI
```
