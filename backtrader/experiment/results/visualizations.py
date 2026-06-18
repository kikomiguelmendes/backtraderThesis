import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

RESULTS_DIR = Path(__file__).resolve().parent
CSV_PATH = RESULTS_DIR / "comparison.csv"

BRAND = "#00338D"
GREY  = "#AAAAAA"
BAR_H = 0.52

df = pd.read_csv(CSV_PATH)
df = df.set_index("branch")


# ---------------------------------------------------------------------------
# Chart 1 — Individual branch results
# ---------------------------------------------------------------------------

ind_rows = ["changes_1", "changes_2", "changes_3"]
ind_labels = {
    "changes_1": "Manual Review",
    "changes_2": "Caching",
    "changes_3": "Static Analysis",
}
sig_labels = {
    "changes_1": "p=0.006 (sig.)",
    "changes_2": "p<0.001 (sig.)",
    "changes_3": "p=0.30, n.s.",
}

ind = df.loc[ind_rows, ["pct_reduction_total"]].copy()
ind["label"] = [ind_labels[b] for b in ind.index]
ind["sig"]   = [sig_labels[b] for b in ind.index]
ind = ind.sort_values("pct_reduction_total", ascending=True)

fig1, ax1 = plt.subplots(figsize=(9, 3.8))

for i, (branch, row) in enumerate(ind.iterrows()):
    is_ns = branch == "changes_3"
    color = GREY if is_ns else BRAND
    lw    = 1.4 if is_ns else 0
    ls    = "--" if is_ns else "-"

    bar = ax1.barh(
        row["label"],
        row["pct_reduction_total"],
        height=BAR_H,
        color=color,
        edgecolor="#777777" if is_ns else "none",
        linewidth=lw,
        linestyle=ls,
    )

    val = row["pct_reduction_total"]
    sig = row["sig"]

    inside = val > 4
    val_x     = val - 0.15 if inside else val + 0.15
    val_ha    = "right"    if inside else "left"
    val_color = "white"    if inside else "#1A1A1A"
    ax1.text(val_x, i, f"{val:.1f}%", va="center", ha=val_ha,
             fontsize=10.5, fontweight="semibold", color=val_color)

    # sig annotation: for large bars anchor right after bar; for small bars
    # anchor at a fixed column so it never collides with the value label
    sig_x  = val + 0.5 if inside else 3.2
    sig_color = "#888888" if is_ns else "#2A6A2A"
    ax1.text(sig_x, i, sig, va="center", ha="left", fontsize=8.5,
             color=sig_color, style="italic" if is_ns else "normal")

ax1.set_title(
    "Energy Reduction by Technique\n(% reduction in total energy vs baseline)",
    fontsize=13, fontweight="bold", color=BRAND, pad=12, loc="left",
)
ax1.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
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
# Chart 2 — Combination results
# ---------------------------------------------------------------------------

comb_rows = ["changes_1_2", "changes_1_3", "changes_2_3", "changes_1_2_3"]
comb_labels = {
    "changes_1_2":   "Manual + Caching",
    "changes_1_3":   "Manual + Static Analysis",
    "changes_2_3":   "Caching + Static Analysis",
    "changes_1_2_3": "All Three Combined",
}

comb = df.loc[comb_rows, ["pct_reduction_total", "h3_expected_pct"]].copy()
comb["label"] = [comb_labels[b] for b in comb.index]
comb = comb.sort_values("pct_reduction_total", ascending=True)

fig2, ax2 = plt.subplots(figsize=(9, 4.2))

yticks = range(len(comb))

ax2.barh(
    list(yticks),
    comb["pct_reduction_total"].values,
    height=BAR_H,
    color=BRAND,
    edgecolor="none",
    label="Observed reduction",
    zorder=2,
)

# Expected additive value — diamond marker on a thin line
for i, (_, row) in enumerate(comb.iterrows()):
    exp = row["h3_expected_pct"]
    ax2.plot([exp, exp], [i - BAR_H / 2, i + BAR_H / 2],
             color="#E8523A", linewidth=2.2, zorder=3, solid_capstyle="round")
    ax2.scatter([exp], [i], marker="D", s=52, color="#E8523A",
                zorder=4, linewidths=0)

# Value labels
for i, (_, row) in enumerate(comb.iterrows()):
    obs = row["pct_reduction_total"]
    exp = row["h3_expected_pct"]
    inside = obs > 5
    val_x  = obs - 0.2 if inside else obs + 0.25
    val_ha = "right"   if inside else "left"
    val_c  = "white"   if inside else "#1A1A1A"
    ax2.text(val_x, i, f"{obs:.1f}%", va="center", ha=val_ha,
             fontsize=10, fontweight="semibold", color=val_c)

ax2.set_yticks(list(yticks))
ax2.set_yticklabels(comb["label"].values, fontsize=10.5)

ax2.set_title(
    "Do Techniques Compound?",
    fontsize=13, fontweight="bold", color=BRAND, pad=12, loc="left",
)
ax2.set_xlabel("Energy Reduction (%)", fontsize=10, color="#555555", labelpad=8)
ax2.set_xlim(0, 22)
ax2.tick_params(axis="y", length=0, colors="#1A1A1A")
ax2.tick_params(axis="x", length=3, labelsize=9, colors="#888888")
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.spines["left"].set_visible(False)
ax2.spines["bottom"].set_color("#CCCCCC")
ax2.xaxis.grid(False)
ax2.yaxis.grid(False)

obs_patch = mpatches.Patch(color=BRAND, label="Observed reduction")
exp_line  = plt.Line2D([0], [0], color="#E8523A", linewidth=2,
                        marker="D", markersize=6, label="Expected (additive)")
ax2.legend(handles=[obs_patch, exp_line], frameon=False,
           fontsize=9, loc="lower right")

fig2.tight_layout(pad=1.5)
out2 = RESULTS_DIR / "chart_combinations.png"
fig2.savefig(out2, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {out2}")
