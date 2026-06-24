# run_comparison.py
#
# Re-runs the full post-processing pipeline from existing energy_runnext.csv
# files. Use this after manually editing a branch's energy_runnext.csv (e.g.
# to remove outlier rows) without re-running the experiments themselves.
#
# Steps performed:
#   1. Regenerate energy_summary.csv for every branch (from energy_runnext.csv)
#   2. Regenerate comparison.csv (from all energy_summary.csv files)
#
# Usage:
#   python run_comparison.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_experiments import analyze_branch, compare_results, DEFAULT_BRANCHES, DEFAULT_BENCHMARK

RESULTS_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

print("Re-running per-branch energy analysis...")
for branch in DEFAULT_BRANCHES:
    runnext = os.path.join(RESULTS_BASE, branch, "energy_runnext.csv")
    if not os.path.exists(runnext):
        print(f"  SKIP {branch}: no energy_runnext.csv found")
        continue
    print(f"  Analyzing {branch}...")
    analyze_branch(branch, DEFAULT_BENCHMARK, RESULTS_BASE)

print("\nGenerating cross-branch comparison...")
compare_results(DEFAULT_BRANCHES, RESULTS_BASE)
