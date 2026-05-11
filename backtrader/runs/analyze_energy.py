"""
Aggregates CodeCarbon per-section energy data from energy_sections.csv
and produces a summary table + energy_summary.csv.

Usage:
    python analyze_energy.py [--sections energy_sections.csv]
"""

import csv
import os
import argparse
from collections import defaultdict

SECTIONS = ["notifications", "data_feed", "cheat_on_open", "broker", "strategy_next"]
TOTAL_KEY = "_runnext"
KWH_TO_J = 3_600_000


def parse_sections(path):
    section_duration = defaultdict(float)
    section_cpu_kwh = defaultdict(float)
    section_total_kwh = defaultdict(float)
    section_count = defaultdict(int)

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["section"]
            section_duration[name] += float(row["duration_s"])
            section_cpu_kwh[name] += float(row["cpu_energy_kWh"])
            section_total_kwh[name] += float(row["energy_consumed_kWh"])
            section_count[name] += 1

    return section_duration, section_cpu_kwh, section_total_kwh, section_count


def main():
    _out_dir = os.environ.get("BT_OUTPUT_DIR", ".")
    parser = argparse.ArgumentParser(description="Summarise CodeCarbon section energy.")
    parser.add_argument("--sections", default=os.path.join(_out_dir, "energy_sections.csv"))
    parser.add_argument("--output", default=os.path.join(_out_dir, "energy_summary.csv"))
    args = parser.parse_args()

    print(f"\nParsing {args.sections} ...")
    section_duration, section_cpu_kwh, section_total_kwh, section_count = parse_sections(args.sections)

    runnext_j = section_cpu_kwh.get(TOTAL_KEY, 0.0) * KWH_TO_J
    runnext_t = section_duration.get(TOTAL_KEY, 0.0)
    sections_j = sum(section_cpu_kwh.get(s, 0.0) * KWH_TO_J for s in SECTIONS)
    overhead_j = runnext_j - sections_j
    total_j = runnext_j if runnext_j > 0 else sections_j
    total_t = runnext_t if runnext_t > 0 else sum(section_duration.get(s, 0.0) for s in SECTIONS)

    print("\n--- Energy per section (CPU, via RAPL/CodeCarbon) ---")
    print(
        f"  {'Section':<20} {'Time (s)':>10} {'Energy (J)':>12} {'Energy (mWh)':>14} {'Share':>8}"
    )
    print("  " + "-" * 68)
    for section in SECTIONS:
        t = section_duration.get(section, 0.0)
        j = section_cpu_kwh.get(section, 0.0) * KWH_TO_J
        mwh = j * 1000 / 3600
        pct = (j / total_j * 100) if total_j > 0 else 0.0
        print(f"  {section:<20} {t:>10.4f} {j:>12.6f} {mwh:>14.8f} {pct:>7.2f}%")
    overhead_mwh = overhead_j * 1000 / 3600
    overhead_pct = (overhead_j / total_j * 100) if total_j > 0 else 0.0
    print(f"  {'overhead':<20} {'-':>10} {overhead_j:>12.6f} {overhead_mwh:>14.8f} {overhead_pct:>7.2f}%")
    print("  " + "-" * 68)
    total_mwh = total_j * 1000 / 3600
    print(
        f"  {'_runnext (total)':<20} {total_t:>10.4f} {total_j:>12.6f} {total_mwh:>14.8f} {'100.00%':>8}"
    )

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["section", "total_time_s", "energy_J", "energy_mWh", "share_pct", "count"])
        for section in SECTIONS:
            t = section_duration.get(section, 0.0)
            j = section_cpu_kwh.get(section, 0.0) * KWH_TO_J
            mwh = j * 1000 / 3600
            pct = (j / total_j * 100) if total_j > 0 else 0.0
            n = section_count.get(section, 0)
            w.writerow([section, round(t, 6), round(j, 8), round(mwh, 10), round(pct, 4), n])
        w.writerow(["overhead", "-", round(overhead_j, 8), round(overhead_mwh, 10), round(overhead_pct, 4), "-"])
        n_total = section_count.get(TOTAL_KEY, 0)
        w.writerow([TOTAL_KEY, round(total_t, 6), round(total_j, 8), round(total_mwh, 10), 100.0, n_total])

    print(f"\nSummary written to {args.output}")


if __name__ == "__main__":
    main()
