"""Matplotlib figures for the septage BOD model."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

from .model import Params, simulate, sensitivity, kinetic_grid, STAGE_NAMES

SHORT = ["Screening", "Primary", "Biological", "Polishing"]

# ---------------------------------------------------------------- chart style
# "Engineering datasheet" look shared by every figure: paper background, ink
# axes, hairline y-grid, IBM Plex fonts. Only the look changes — the data,
# axes and labels of each plot are exactly as before.
PAPER, INK, INK_2, HAIRLINE = "#F5F3EE", "#1B1E22", "#5A5F66", "#C9C4B8"
FAIL_RED = "#A61B1B"
# one muted colour per treatment stage (same order as STAGE_NAMES)
STAGE_COLORS = ["#8C7A5B", "#B08A3E", "#3F7D4E", "#3A6F9A"]
SANS, COND, MONO = "IBM Plex Sans", "IBM Plex Sans Condensed", "IBM Plex Mono"

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
for _ttf in sorted(FONT_DIR.glob("*.ttf")):   # register the bundled TTFs (no DejaVu fallback)
    font_manager.fontManager.addfont(str(_ttf))


def apply_style():
    """Set the shared rcParams used by every plot below."""
    plt.rcParams.update({
        "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
        "font.family": SANS, "font.size": 10,
        # log-axis tick labels (10², 10³) are mathtext: draw them in Plex Mono too
        "mathtext.fontset": "custom", "mathtext.rm": MONO, "mathtext.it": MONO, "mathtext.bf": MONO,
        "mathtext.default": "regular",
        "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": INK, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,      # only left + bottom spines
        "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
        "grid.color": HAIRLINE, "grid.linewidth": 0.6, "grid.linestyle": "-",
        "axes.titlesize": 12, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.titlepad": 10, "axes.labelsize": 9.5,
        "xtick.color": INK, "ytick.color": INK, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "xtick.major.width": 0.8, "ytick.major.width": 0.8, "xtick.minor.width": 0.5, "ytick.minor.width": 0.5,
        "lines.linewidth": 1.5, "lines.markersize": 5,
        "legend.frameon": False, "legend.fontsize": 8.5,
        "axes.prop_cycle": plt.cycler(color=[INK, "#3A6F9A", "#3F7D4E", "#B08A3E"]),
    })


def _finish(fig, ax):
    """Per-axes font roles rcParams cannot express: mono ticks, condensed title."""
    ax.tick_params(labelfontfamily=MONO)
    ax.title.set_fontfamily(COND)
    fig.tight_layout()
    return fig


def _limit_line(ax, limit, label):
    ax.axhline(limit, color=FAIL_RED, ls="--", lw=1.2, label=label)


apply_style()


# ---------------------------------------------------------------- figures
def plot_profile(p: Params, kinetic=False):
    df = simulate(p, kinetic)
    x = ["Influent"] + SHORT
    y = [p.influent_bod] + list(df["BOD out (mg/L)"])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, y, marker="o", color=INK, markerfacecolor=PAPER, markeredgewidth=1.3)
    _limit_line(ax, p.limit, f"DAO 2016-08 limit ({p.limit:g} mg/L)")
    ax.set_yscale("log")
    ax.set_ylabel("BOD (mg/L, log scale)")
    ax.set_title("BOD along the treatment train")
    ax.legend()
    return _finish(fig, ax)


def plot_removed(p: Params, kinetic=False):
    df = simulate(p, kinetic)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(SHORT, df["Load removed (kg/day)"], color=STAGE_COLORS[:len(SHORT)], width=0.6)
    ax.set_ylabel("BOD load removed (kg/day)")
    ax.set_title("BOD load removed per stage")
    return _finish(fig, ax)


def plot_sensitivity(p: Params, delta=0.05):
    s = sensitivity(p, delta).iloc[::-1]
    colors = [STAGE_COLORS[STAGE_NAMES.index(n) % len(STAGE_COLORS)] if n in STAGE_NAMES else INK
              for n in s["Stage"]]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(s["Stage"], s["Swing (mg/L)"], color=colors, height=0.6)
    ax.set_xlabel(f"Effluent BOD swing for ±{delta:.0%} removal (mg/L)")
    ax.set_title("Sensitivity to stage removal rate")
    ax.grid(False)                                   # horizontal bars: value axis is x,
    ax.grid(True, axis="x")                          # so the hairlines run vertically here
    return _finish(fig, ax)


def plot_kinetics(p: Params, max_hrt=10.0):
    hrts = np.linspace(0.1, max_hrt, 60)
    fig, ax = plt.subplots(figsize=(7, 4))
    for q in sorted({p.flow * 0.5, p.flow, p.flow * 2}):
        g = kinetic_grid(p, hrts, [q])
        ax.plot(g["hrt"], g["effluent_bod"], label=f"Q = {q:g} m³/day")
    _limit_line(ax, p.limit, "limit")
    ax.set_yscale("log")
    ax.set_xlabel("Biological-stage retention time (days)")
    ax.set_ylabel("Final effluent BOD (mg/L)")
    ax.set_title(f"First-order kinetics ({p.reactor.upper()}, k = {p.k:g}/day)")
    ax.legend()
    return _finish(fig, ax)


def plot_comparison(tbl):
    fig, ax = plt.subplots(figsize=(7, 4))
    idx = np.arange(len(tbl))
    ax.bar(idx - 0.2, tbl["observed (mg/L)"], 0.4, label="Published", color=PAPER, edgecolor=INK, linewidth=1)
    ax.bar(idx + 0.2, tbl["simulated (mg/L)"], 0.4, label="Simulated", color=INK)
    ax.set_xticks(idx)
    ax.set_xticklabels([f"{r.stage}\n{r.source[:22]}" for r in tbl.itertuples()], fontsize=7)
    ax.set_ylabel("BOD (mg/L)")
    ax.legend()
    return _finish(fig, ax)
