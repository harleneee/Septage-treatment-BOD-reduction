"""Run the full analysis; writes tables (CSV) and figures (PNG) to ./output."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd

from septage import model as m
from septage import plots

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)
p = m.Params()
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

for label, kin in (("fixed", False), ("kinetic", True)):
    df = m.simulate(p, kin)
    df.to_csv(OUT / f"stages_{label}.csv", index=False)
    print(f"\n=== Stage table ({label}) ===\n{df.round(2)}")
    print("Summary:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.summary(p, kin).items()})
    print("Closed-form check:", m.verify(p, kin))
    plots.plot_profile(p, kin).savefig(OUT / f"profile_{label}.png", dpi=150)
    plots.plot_removed(p, kin).savefig(OUT / f"removed_{label}.png", dpi=150)

sens = m.sensitivity(p)
sens.to_csv(OUT / "sensitivity.csv", index=False)
print(f"\n=== Sensitivity ===\n{sens.round(2)}")
plots.plot_sensitivity(p).savefig(OUT / "sensitivity.png", dpi=150)
plots.plot_kinetics(p).savefig(OUT / "kinetics.png", dpi=150)

ref = pd.read_csv(Path(__file__).parent / "data" / "literature_bod.csv")
tbl, stats = m.compare_with_literature(p, ref, kinetic=True)
tbl.to_csv(OUT / "comparison.csv", index=False)
print(f"\n=== Literature comparison ===\n{tbl.round(2)}\n{stats}")
if ref["source"].str.contains("PLACEHOLDER").any():
    print("WARNING: data/literature_bod.csv holds placeholder values, not real published data.")
plots.plot_comparison(tbl).savefig(OUT / "comparison.png", dpi=150)
print(f"\nSaved outputs to {OUT}")
