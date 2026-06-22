import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from pathlib import Path

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

RESULTS_DIR = Path(__file__).resolve().parent
CSV_PATH    = RESULTS_DIR / "comparison.csv"

BRAND  = "#37474F"   # dark blue-grey
GREY   = "#AAAAAA"
ORANGE = "#D95F02"   # warm orange for expected marker
BAR_H  = 0.52

BRANCH_LABELS = {
    "baseline":      "Baseline",
    "changes_1":     "Manual Review",
    "changes_2":     "Caching",
    "changes_3":     "Static Analysis",
    "changes_1_2":   "Manual + Caching",
    "changes_1_3":   "Manual + Static Analysis",
    "changes_2_3":   "Caching + Static Analysis",
    "changes_1_2_3": "All Three Combined",
}

df = pd.read_csv(CSV_PATH).set_index("branch")


# ---------------------------------------------------------------------------
# Chart 1 — Individual branch energy reduction
# ---------------------------------------------------------------------------

ind_rows = ["changes_1", "changes_2", "changes_3"]
sig_labels = {
    "changes_1": "p=0.031, significant",
    "changes_2": "p<0.001, significant",
    "changes_3": "p=0.145, not significant",
}

ind = df.loc[ind_rows, ["pct_reduction_total"]].copy()
ind["label"] = [BRANCH_LABELS[b] for b in ind.index]
ind["sig"]   = [sig_labels[b]   for b in ind.index]
ind = ind.sort_values("pct_reduction_total", ascending=True)

fig1, ax1 = plt.subplots(figsize=(9, 3.8))

for i, (branch, row) in enumerate(ind.iterrows()):
    is_ns = branch == "changes_3"
    color = GREY if is_ns else BRAND
    lw    = 1.4  if is_ns else 0
    ls    = "--"  if is_ns else "-"

    ax1.barh(
        row["label"], row["pct_reduction_total"],
        height=BAR_H,
        color=color,
        edgecolor="#777777" if is_ns else "none",
        linewidth=lw, linestyle=ls,
    )

    val = row["pct_reduction_total"]
    inside    = val > 4
    val_x     = val - 0.15 if inside else val + 0.15
    val_ha    = "right"    if inside else "left"
    val_color = "white"    if inside else "#1A1A1A"
    ax1.text(val_x, i, f"{val:.1f}%", va="center", ha=val_ha,
             fontsize=10.5, fontweight="semibold", color=val_color)

    sig      = row["sig"]
    sig_x    = val + 0.5  if inside else 3.2
    sig_color = "#888888" if is_ns  else "#37474F"
    ax1.text(sig_x, i, sig, va="center", ha="left", fontsize=8.5,
             color=sig_color, style="italic" if is_ns else "normal")

ax1.axvline(x=0, color="#888888", linewidth=0.9, linestyle="--", zorder=0)

ax1.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
ax1.set_title("Total Energy Reduction by Technique (% vs Baseline)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax1.set_xlim(0, 22)
ax1.tick_params(axis="y", length=0, labelsize=11, colors="#1A1A1A")
ax1.tick_params(axis="x", length=3, labelsize=9,  colors="#888888")
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)
ax1.spines["left"].set_visible(False)
ax1.spines["bottom"].set_color("#CCCCCC")
ax1.xaxis.grid(False)
ax1.yaxis.grid(False)

fig1.tight_layout(pad=1.5)
out1 = RESULTS_DIR / "chart_individual_branches.png"
fig1.savefig(out1, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {out1}")


# ---------------------------------------------------------------------------
# Chart 2 — Combination results with additivity comparison
# ---------------------------------------------------------------------------

comb_rows = ["changes_1_2", "changes_1_3", "changes_2_3", "changes_1_2_3"]

EFFECT_COLORS = {
    "additive":      "#37474F",
    "subadditive":   "#B85C00",
    "superadditive": "#6A2A6A",
}
EFFECT_LABELS = {
    "additive":      "additive",
    "subadditive":   "sub-additive",
    "superadditive": "super-additive",
}

comb = df.loc[comb_rows, ["pct_reduction_total", "h3_expected_pct", "h3_effect"]].copy()
comb["label"] = [BRANCH_LABELS[b] for b in comb.index]
comb = comb.sort_values("pct_reduction_total", ascending=True)

fig2, ax2 = plt.subplots(figsize=(10, 4.2))

yticks = list(range(len(comb)))

# Observed bars — solid filled
ax2.barh(
    yticks, comb["pct_reduction_total"].values,
    height=BAR_H, color=BRAND, edgecolor="none",
    label="Observed reduction", zorder=2,
)

# Expected bars — outlined only so observed vs expected gap is immediately legible
ax2.barh(
    yticks, comb["h3_expected_pct"].values,
    height=BAR_H,
    color="none", edgecolor=ORANGE, linewidth=1.8, linestyle="--",
    label="Expected (additive sum)", zorder=3,
)

for i, (_, row) in enumerate(comb.iterrows()):
    obs    = row["pct_reduction_total"]
    effect = row["h3_effect"]

    inside = obs > 5
    if inside:
        ax2.text(obs - 0.2, i, f"{obs:.1f}%", va="center", ha="right",
                 fontsize=10, fontweight="semibold", color="white")
    else:
        ax2.text(-0.2, i, f"{obs:.1f}%", va="center", ha="right",
                 fontsize=10, fontweight="semibold", color="#1A1A1A")

    ax2.text(21.8, i, EFFECT_LABELS[effect], va="center", ha="right",
             fontsize=8.5, color=EFFECT_COLORS[effect], style="italic")

ax2.set_yticks(yticks)
ax2.set_yticklabels(comb["label"].values, fontsize=10.5)

ax2.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
ax2.set_title("Observed vs Expected Additive Reduction (% vs Baseline)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax2.set_xlim(-1.5, 22)
ax2.tick_params(axis="y", length=0, colors="#1A1A1A")
ax2.tick_params(axis="x", length=3, labelsize=9, colors="#888888")
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.spines["left"].set_visible(False)
ax2.spines["bottom"].set_color("#CCCCCC")
ax2.xaxis.grid(False)
ax2.yaxis.grid(False)

obs_patch = mpatches.Patch(color=BRAND, label="Observed reduction")
exp_patch = mpatches.Patch(
    facecolor="none", edgecolor=ORANGE, linewidth=1.8,
    linestyle="--", label="Expected (additive sum)"
)
ax2.legend(handles=[obs_patch, exp_patch], frameon=False, fontsize=9, loc="center right")

fig2.tight_layout(pad=1.5)
out2 = RESULTS_DIR / "chart_combinations.png"
fig2.savefig(out2, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {out2}")


# ---------------------------------------------------------------------------
# Chart 3 — All branches absolute energy with uncertainty
# ---------------------------------------------------------------------------

all_rows = ["baseline", "changes_1", "changes_2", "changes_3",
            "changes_1_2", "changes_1_3", "changes_2_3", "changes_1_2_3"]

abso = df.loc[all_rows, ["mean_total_energy_J", "std_total_energy_J"]].copy()
abso["label"]         = [BRANCH_LABELS[b] for b in abso.index]
abso["pct_reduction"] = df.loc[all_rows, "pct_reduction_total"].fillna(0.0)
# sort ascending so highest energy (baseline) ends up at top of barh
abso = abso.sort_values("mean_total_energy_J", ascending=True)

BASELINE_CLR = "#90A4AE"   # distinct cool blue-grey for baseline
ALPHA_MIN, ALPHA_MAX = 0.30, 1.00

non_bl = abso[abso.index != "baseline"]["pct_reduction"]
red_min, red_max = non_bl.min(), non_bl.max()

def reduction_alpha(pct):
    if red_max > red_min:
        return ALPHA_MIN + (ALPHA_MAX - ALPHA_MIN) * (pct - red_min) / (red_max - red_min)
    return ALPHA_MAX

def bar_rgba(branch, pct):
    if branch == "baseline":
        return mcolors.to_rgba(BASELINE_CLR, alpha=1.0)
    return mcolors.to_rgba(BRAND, alpha=reduction_alpha(pct))

fig3, ax3 = plt.subplots(figsize=(10, 5.2))

for i, (branch, row) in enumerate(abso.iterrows()):
    rgba  = bar_rgba(branch, row["pct_reduction"])
    xerr  = row["std_total_energy_J"]
    mean  = row["mean_total_energy_J"]

    ax3.barh(
        row["label"], mean,
        height=BAR_H,
        color=rgba,
        edgecolor="none",
        xerr=xerr,
        error_kw={"elinewidth": 1.2, "ecolor": "#888888", "capsize": 3},
        zorder=2,
    )

    ax3.text(mean + xerr + 4, i, f"{mean:.1f} J",
             va="center", ha="left", fontsize=9, color="#1A1A1A")

ax3.set_xlabel("Total Energy (J)", fontsize=10, color="#555555", labelpad=8)
ax3.set_title("Mean Total Energy Consumption per Branch (J)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax3.set_xlim(0, 840)
ax3.tick_params(axis="y", length=0, labelsize=10, colors="#1A1A1A")
ax3.tick_params(axis="x", length=3, labelsize=9,  colors="#888888")
ax3.spines["top"].set_visible(False)
ax3.spines["right"].set_visible(False)
ax3.spines["left"].set_visible(False)
ax3.spines["bottom"].set_color("#CCCCCC")
ax3.xaxis.grid(False)
ax3.yaxis.grid(False)

baseline_patch = mpatches.Patch(color=BASELINE_CLR, label="Baseline")
lo_patch = mpatches.Patch(color=mcolors.to_rgba(BRAND, alpha=ALPHA_MIN),
                           label="Lower reduction (lighter)")
hi_patch = mpatches.Patch(color=mcolors.to_rgba(BRAND, alpha=ALPHA_MAX),
                           label="Higher reduction (darker)")
ax3.legend(handles=[baseline_patch, lo_patch, hi_patch],
           frameon=False, fontsize=9, loc="lower right")

fig3.tight_layout(pad=1.5)
out3 = RESULTS_DIR / "chart_all_branches_absolute.png"
fig3.savefig(out3, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {out3}")
