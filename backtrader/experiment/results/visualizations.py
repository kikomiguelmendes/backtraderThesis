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

BRAND        = "#37474F"   # dark blue-grey
GREY         = "#AAAAAA"
ORANGE       = "#D95F02"   # warm orange for expected marker
BASELINE_CLR = "#90A4AE"   # distinct cool blue-grey for baseline
BAR_H        = 0.52

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


def _fmt_p(p):
    if p < 0.001:
        return "p<0.001"
    return f"p={p:.3f}"


def _is_ns(branch):
    return str(df.loc[branch, "h2_rejected_total"]).strip().lower() != "true"


def _sig_label(branch):
    p = df.loc[branch, "p_total"]
    word = "not significant" if _is_ns(branch) else "significant"
    return f"{_fmt_p(p)}, {word}"

# Chart 1 — Individual branch energy reduction

ind_rows = ["changes_3", "changes_2", "changes_1"]

ind = df.loc[ind_rows, ["pct_reduction_total"]].copy()
ind["label"] = [BRANCH_LABELS[b] for b in ind.index]
ind["sig"]   = [_sig_label(b) for b in ind.index]
ind["is_ns"] = [_is_ns(b)     for b in ind.index]

max_ind_pct = ind["pct_reduction_total"].max()

fig1, ax1 = plt.subplots(figsize=(9, 3.8))

for i, (branch, row) in enumerate(ind.iterrows()):
    is_ns = row["is_ns"]
    color = GREY if is_ns else BRAND
    lw    = 1.4 if is_ns else 0
    ls    = "--" if is_ns else "-"

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
    sig_x    = val + 0.5  if inside else max_ind_pct * 0.18
    sig_color = "#888888" if is_ns  else "#37474F"
    ax1.text(sig_x, i, sig, va="center", ha="left", fontsize=8.5,
             color=sig_color, style="italic" if is_ns else "normal")

ax1.axvline(x=0, color="#888888", linewidth=0.9, linestyle="--", zorder=0)

ax1.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
ax1.set_title("Total Energy Reduction by Technique (% vs Baseline)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax1.set_xlim(0, max_ind_pct + 8)
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

# Chart 2 — Combination results with additivity comparison

comb_rows = ["changes_1_2_3", "changes_2_3", "changes_1_3", "changes_1_2"]

EFFECT_COLORS = {
    "Additive":      "#37474F",
    "Sub-additive":  "#B85C00",
    "Super-additive": "#6A2A6A",
}
EFFECT_LABELS = {
    "Additive":      "additive",
    "Sub-additive":  "sub-additive",
    "Super-additive": "super-additive",
}

comb = df.loc[comb_rows, ["pct_reduction_total", "h3_expected_pct", "h3_classification"]].copy()
comb["label"] = [BRANCH_LABELS[b] for b in comb.index]

max_comb_pct = max(comb["pct_reduction_total"].max(), comb["h3_expected_pct"].max())

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
    effect = row["h3_classification"]

    inside = obs > 5
    if inside:
        ax2.text(obs - 0.2, i, f"{obs:.1f}%", va="center", ha="right",
                 fontsize=10, fontweight="semibold", color="white")
    else:
        ax2.text(-0.2, i, f"{obs:.1f}%", va="center", ha="right",
                 fontsize=10, fontweight="semibold", color="#1A1A1A")

    ax2.text(max_comb_pct + 3.5, i, EFFECT_LABELS[effect], va="center", ha="right",
             fontsize=8.5, color=EFFECT_COLORS[effect], style="italic")

ax2.set_yticks(yticks)
ax2.set_yticklabels(comb["label"].values, fontsize=10.5)

ax2.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
ax2.set_title("Observed vs Expected Additive Reduction (% vs Baseline)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax2.set_xlim(-1.5, max_comb_pct + 5)
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

# Chart 3 — RQ3 interaction effect: delta (J) with 95% CI

delta_rows = ["changes_1_2_3", "changes_2_3", "changes_1_3", "changes_1_2"]

delta_df = df.loc[delta_rows, ["h3_delta_J", "h3_ci_lower_J", "h3_ci_upper_J", "h3_classification"]].copy()
delta_df["label"] = [BRANCH_LABELS[b] for b in delta_df.index]

fig4, ax4 = plt.subplots(figsize=(9, 3.8))

yticks4 = list(range(len(delta_df)))

for i, (_, row) in enumerate(delta_df.iterrows()):
    delta = row["h3_delta_J"]
    lo, hi = row["h3_ci_lower_J"], row["h3_ci_upper_J"]
    cls = row["h3_classification"]
    color = EFFECT_COLORS.get(cls, GREY)

    ax4.errorbar(
        delta, i, xerr=[[delta - lo], [hi - delta]],
        fmt="o", color=color, ecolor=color,
        elinewidth=1.6, capsize=4, markersize=6, zorder=3,
    )
    ax4.text(hi + 1, i, f"{EFFECT_LABELS.get(cls, cls)}  (Δ={delta:.2f} J)",
             va="center", ha="left", fontsize=8.5, color=color, style="italic")

ax4.axvline(x=0, color="#888888", linewidth=0.9, linestyle="--", zorder=0)
ax4.set_yticks(yticks4)
ax4.set_yticklabels(delta_df["label"].values, fontsize=10.5)
ax4.set_xlabel("Interaction effect Δ (J), 95% CI   [+ = super-additive, − = sub-additive]",
               fontsize=9.5, color="#555555", labelpad=8)
ax4.set_title("RQ3 — Interaction Effect on Total Energy (Δ = Expected − Observed Combo Mean)",
              fontsize=12, color="#1A1A1A", pad=12, fontweight="semibold")
ax4.tick_params(axis="y", length=0, colors="#1A1A1A")
ax4.tick_params(axis="x", length=3, labelsize=9, colors="#888888")
ax4.spines["top"].set_visible(False)
ax4.spines["right"].set_visible(False)
ax4.spines["left"].set_visible(False)
ax4.spines["bottom"].set_color("#CCCCCC")
ax4.xaxis.grid(False)
ax4.yaxis.grid(False)

xmax = max(abs(delta_df["h3_ci_lower_J"].min()), abs(delta_df["h3_ci_upper_J"].max())) * 1.7
ax4.set_xlim(-xmax, xmax)

fig4.tight_layout(pad=1.5)
out4 = RESULTS_DIR / "chart_combinations.png"
fig4.savefig(out4, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {out4}")
