"""Matplotlib figures: flow diagram, per-stage profile, time series, sensitivity tornado."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

BLUE, TEAL, GREY, RED, ORANGE = "#2b6cb0", "#2c9c8f", "#6b7280", "#c0392b", "#d97706"


def fig_flow_diagram(pipeline, snapshot=None):
    """Process flow diagram generated from the stage list. snapshot: optional steady_state() DataFrame."""
    labels = ["Collection\ntank"] + ["\n".join(s.label.rsplit(" ", 1)) for s in pipeline.stages] + ["Treated\ntank", "Reuse\ntank"]
    n = len(labels)
    fig, ax = plt.subplots(figsize=(1.55 * n, 2.6))
    ax.set_xlim(-0.5, n * 1.5)
    ax.set_ylim(-0.2, 2.2)
    ax.axis("off")
    for i, lab in enumerate(labels):
        x = i * 1.5
        colour = BLUE if 0 < i <= len(pipeline.stages) else TEAL
        ax.add_patch(FancyBboxPatch((x, 0.7), 1.1, 0.9, boxstyle="round,pad=0.03", fc=colour, ec="none", alpha=0.9))
        ax.text(x + 0.55, 1.15, lab, ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + 1.13, 1.15), (x + 1.47, 1.15), arrowstyle="-|>", mutation_scale=12, color=GREY))
        if snapshot is not None and i < len(snapshot):
            row = snapshot.iloc[i if i < len(snapshot) else -1]
            ax.text(x + 0.55, 0.45, f"{row['turbidity_ntu']:.2f} NTU\nTOC {row['toc_mgl']:.1f}\nlog {row['bacteria_log']:.1f}",
                    ha="center", va="top", fontsize=6.5, color=GREY)
    ax.set_title("Process flow (values: steady-state quality leaving each stage)" if snapshot is not None else "Process flow", fontsize=10)
    fig.tight_layout()
    return fig


def fig_stage_profile(ss):
    """Bar charts of key parameters leaving each stage (steady-state table)."""
    params = [("turbidity_ntu", "Turbidity (NTU)"), ("toc_mgl", "TOC (mg/L)"),
              ("bacteria_log", "Bacteria (log10 CFU/mL)"), ("tds_mgl", "TDS (mg/L)")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5))
    short = [s.replace(" ", "\n", 1) for s in ss.index]
    for ax, (col, title) in zip(axes.flat, params):
        colours = [GREY] + [BLUE] * (len(ss) - 1)
        ax.bar(range(len(ss)), ss[col], color=colours)
        ax.set_xticks(range(len(ss)))
        ax.set_xticklabels(short, fontsize=6.5)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Water quality leaving each stage (note: TDS is not reduced)", fontsize=11)
    fig.tight_layout()
    return fig


def fig_timeseries(df):
    fig, axes = plt.subplots(4, 1, figsize=(11, 11), sharex=True)
    d = df["t_h"] / 24.0
    ax = axes[0]
    ax.plot(d, df["collection_l"], label="Collection tank", color=BLUE)
    ax.plot(d, df["treated_l"], label="Treated tank", color=TEAL)
    ax.plot(d, df["reuse_l"], label="Reuse tank", color=ORANGE)
    ax.set_ylabel("Volume (L)")
    ax.legend(ncol=3, fontsize=8)
    ax.set_title("Tank volumes")

    ax = axes[1]
    ax.plot(d, df["reuse_tank.bacteria_log"], color=RED, label="Reuse tank bacteria")
    ax.plot(d, df["treated_tank.bacteria_log"], color=TEAL, label="Treated tank bacteria", alpha=0.8)
    ax.set_ylabel("log10 CFU/mL")
    ax.set_ylim(-3.3, 3.3)  # fixed span so tiny regrowth is not visually exaggerated
    ax2 = ax.twinx()
    ax2.plot(d, df["uv.turbidity_ntu"], color=GREY, label="Outlet turbidity", ls="--")
    ax2.set_ylabel("NTU")
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    ax.set_title("Water quality (treated water and storage regrowth)")

    ax = axes[2]
    for col, lab in [("mmf.dp_bar", "Multimedia"), ("cartridge_5um.dp_bar", "5 \u00b5m cartridge"),
                     ("candle_05um.dp_bar", "0.5 \u00b5m candle"), ("uf.tmp_bar", "UF TMP")]:
        if col in df:
            ax.plot(d, df[col], label=lab, marker=".", ms=2, ls="none")
    ax.set_ylabel("Pressure drop (bar)")
    ax.legend(ncol=4, fontsize=8)
    ax.set_title("Filter loading (resets = backwash / replacement events)")

    ax = axes[3]
    ax.plot(d, df["carbon.saturation"], color=BLUE, label="Carbon saturation")
    ax.set_ylabel("Carbon saturation")
    ax2 = ax.twinx()
    ax2.plot(d, df["uv.dose_mj_cm2"], color=ORANGE, marker=".", ms=2, ls="none", label="UV dose")
    ax2.set_ylabel("UV dose (mJ/cm\u00b2)")
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    ax.set_xlabel("Day")
    ax.set_title("Carbon bed and UV dose")
    for a in axes:
        a.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def fig_sensitivity(sdf, metric_label="Metric"):
    s = sdf.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(s) + 1.5))
    y = np.arange(len(s))
    base = s["metric_base"].iloc[0]
    ax.barh(y, s["metric_high"] - base, left=base, color=ORANGE, label="+ change")
    ax.barh(y, s["metric_low"] - base, left=base, color=BLUE, alpha=0.8, label="- change")
    ax.axvline(base, color="k", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(s["parameter"], fontsize=8)
    ax.set_xlabel(metric_label)
    ax.legend(fontsize=8)
    ax.set_title("Sensitivity (one-at-a-time, +/-25%, clipped to the sensible range)")
    fig.tight_layout()
    return fig
