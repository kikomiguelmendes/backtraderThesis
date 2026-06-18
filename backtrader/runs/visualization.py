import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "energy_summary.csv"
OUT_PATH = ROOT / "chart_preliminary.png"

LABEL_MAP = {
    "backtesting_setup": "Backtesting Setup",
    "data_ingestion": "Data Ingestion",
    "strategy_execution": "Strategy Execution",
}

BRAND = "#00338D"

PALETTE = {
    "Strategy Execution": BRAND,
    "Data Ingestion":     BRAND,
    "Backtesting Setup":  BRAND,
}

df = pd.read_csv(CSV_PATH)
df = df[df["section"].isin(LABEL_MAP)].copy()
df["label"] = df["section"].map(LABEL_MAP)
df = df.sort_values("share_pct", ascending=True)

fig, ax = plt.subplots(figsize=(8, 3.6))

bars = ax.barh(
    df["label"],
    df["share_pct"],
    color=[PALETTE[l] for l in df["label"]],
    height=0.52,
    edgecolor="none",
)

for bar, val in zip(bars, df["share_pct"]):
    x_pos = bar.get_width()
    label_x = x_pos - 1.2 if x_pos > 10 else x_pos + 0.8
    color = "white" if x_pos > 10 else "#2C3E50"
    ha = "right" if x_pos > 10 else "left"
    ax.text(
        label_x,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.1f}%",
        va="center",
        ha=ha,
        fontsize=11,
        fontweight="semibold",
        color=color,
    )

ax.set_title("Where Does the Energy Go?", fontsize=14, fontweight="bold",
             color=BRAND, pad=14, loc="left")

ax.set_xlabel("Share of Total Energy (%)", fontsize=10, color="#555555", labelpad=8)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.set_xlim(0, 105)

ax.tick_params(axis="y", length=0, labelsize=11, colors="#1A1A1A")
ax.tick_params(axis="x", length=3, labelsize=9, colors="#888888")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#CCCCCC")

ax.xaxis.grid(False)
ax.yaxis.grid(False)
ax.set_axisbelow(True)

fig.tight_layout(pad=1.4)
fig.savefig(OUT_PATH, dpi=300, bbox_inches="tight", facecolor="white")
print(f"Saved → {OUT_PATH}")
