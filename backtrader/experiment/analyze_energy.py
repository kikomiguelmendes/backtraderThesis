"""
Aggregates CodeCarbon energy data from energy_runnext.csv
and produces a summary table + energy_summary.csv.

Usage:
    python analyze_energy.py [--input energy_runnext.csv] [--baseline baseline_runnext.csv]
"""

import csv
import os
import argparse
import math
from scipy.stats import mannwhitneyu

KWH_TO_J = 3_600_000


def load_runs(path):
    runs = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            runs.append({
                "duration_s": float(row["duration_s"]),
                "cpu_energy_J": float(row["cpu_energy_kWh"]) * KWH_TO_J,
                "energy_consumed_J": float(row["energy_consumed_kWh"]) * KWH_TO_J,
            })
    return runs


def mean(values):
    return sum(values) / len(values)


def std(values):
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def main():
    _out_dir = os.environ.get("BT_OUTPUT_DIR", ".")
    parser = argparse.ArgumentParser(description="Summarise CodeCarbon energy per run.")
    parser.add_argument("--input", default=os.path.join(_out_dir, "energy_runnext.csv"))
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--output", default=os.path.join(_out_dir, "energy_summary.csv"))
    args = parser.parse_args()

    print(f"\nParsing {args.input} ...")
    runs = load_runs(args.input)
    n = len(runs)

    cpu_j = [r["cpu_energy_J"] for r in runs]
    total_j = [r["energy_consumed_J"] for r in runs]
    durations = [r["duration_s"] for r in runs]

    mean_cpu = mean(cpu_j)
    std_cpu = std(cpu_j)
    mean_total = mean(total_j)
    std_total = std(total_j)
    mean_dur = mean(durations)

    print(f"\n--- Energy summary ({n} runs) ---")
    print(f"  Mean duration:        {mean_dur:.4f} s")
    print(f"  Mean CPU energy:      {mean_cpu:.6f} J  (std: {std_cpu:.6f})")
    print(f"  Mean total energy:    {mean_total:.6f} J  (std: {std_total:.6f})")

    baseline_runs = None
    if args.baseline:
        print(f"\nParsing baseline {args.baseline} ...")
        baseline_runs = load_runs(args.baseline)
        base_cpu_j = [r["cpu_energy_J"] for r in baseline_runs]
        base_total_j = [r["energy_consumed_J"] for r in baseline_runs]

        base_mean_cpu = mean(base_cpu_j)
        base_mean_total = mean(base_total_j)

        pct_reduction_cpu = (base_mean_cpu - mean_cpu) / base_mean_cpu * 100
        pct_reduction_total = (base_mean_total - mean_total) / base_mean_total * 100

        stat_cpu, p_cpu = mannwhitneyu(base_cpu_j, cpu_j, alternative="greater")
        stat_total, p_total = mannwhitneyu(base_total_j, total_j, alternative="greater")

        alpha = 0.05
        h2_rejected_cpu = p_cpu < alpha
        h2_rejected_total = p_total < alpha

        print(f"\n--- Comparison against baseline ---")
        print(f"  CPU energy reduction:     {pct_reduction_cpu:+.2f}%")
        print(f"  Total energy reduction:   {pct_reduction_total:+.2f}%")
        print(f"\n  Mann-Whitney U (CPU):     U={stat_cpu:.1f}, p={p_cpu:.4f}  "
              f"→ H2_0 {'REJECTED' if h2_rejected_cpu else 'NOT REJECTED'} (α=0.05)")
        print(f"  Mann-Whitney U (total):   U={stat_total:.1f}, p={p_total:.4f}  "
              f"→ H2_0 {'REJECTED' if h2_rejected_total else 'NOT REJECTED'} (α=0.05)")

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "run", "duration_s", "cpu_energy_J", "energy_consumed_J"
        ])
        for i, r in enumerate(runs, 1):
            w.writerow([
                i,
                round(r["duration_s"], 6),
                round(r["cpu_energy_J"], 8),
                round(r["energy_consumed_J"], 8),
            ])
        w.writerow(["mean", round(mean_dur, 6), round(mean_cpu, 8), round(mean_total, 8)])
        w.writerow(["std", "-", round(std_cpu, 8), round(std_total, 8)])
        if baseline_runs:
            w.writerow([])
            w.writerow(["metric", "cpu_energy", "total_energy"])
            w.writerow(["pct_reduction", round(pct_reduction_cpu, 4), round(pct_reduction_total, 4)])
            w.writerow(["mann_whitney_p", round(p_cpu, 6), round(p_total, 6)])
            w.writerow(["h2_rejected", h2_rejected_cpu, h2_rejected_total])

    print(f"\nSummary written to {args.output}")


if __name__ == "__main__":
    main()