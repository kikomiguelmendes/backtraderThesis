import os
import sys
import csv
import time
import random
import argparse
import subprocess
import shutil
import importlib.util

"""
tutorial run:
python run_experiments.py --benchmark $(pwd)/backtrader/experiment/tutorialRun.py
"""

EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(EXPERIMENT_DIR))
DEFAULT_BRANCHES = ["baseline", "changes_1", "changes_2", "changes_3", "changes_1_2", "changes_1_3", "changes_2_3", "changes_1_2_3"]
DEFAULT_BENCHMARK = os.path.join(EXPERIMENT_DIR, "maxStressRun.py")
RESULTS_BASE = os.path.join(EXPERIMENT_DIR, "results")

COOLDOWN_S = 60

def git(args, **kwargs):
    return subprocess.run(["git"] + args, cwd=REPO_ROOT, check=True, **kwargs)

def save_hardware_info(results_base):
    from codecarbon import EmissionsTracker

    tracker = EmissionsTracker(measure_power_secs=1, log_level="error", save_to_file=False)
    tracker.start()
    tracker.stop()
    d = tracker.final_emissions_data

    path = os.path.join(results_base, "hardware.txt")
    with open(path, "w") as f:
        f.write(f"os:                {d.os}\n")
        f.write(f"python_version:    {d.python_version}\n")
        f.write(f"codecarbon_version:{d.codecarbon_version}\n")
        f.write(f"cpu_model:         {d.cpu_model}\n")
        f.write(f"cpu_count:         {d.cpu_count}\n")
        f.write(f"ram_total_size_gb: {d.ram_total_size}\n")
        f.write(f"gpu_model:         {d.gpu_model}\n")
        f.write(f"gpu_count:         {d.gpu_count}\n")
        f.write(f"country:           {d.country_name}\n")
        f.write(f"region:            {d.region}\n")
        f.write(f"cloud_provider:    {d.cloud_provider}\n")
        f.write(f"cloud_region:      {d.cloud_region}\n")
    print(f"  Hardware info saved to {path}")

def check_clean_tree():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    if result.stdout.strip():
        print("ERROR: working tree has uncommitted changes. Stash or commit before running.")
        print(result.stdout)
        sys.exit(1)

def load_benchmark_module(path):
    """Import benchmark file to read its N_RUNS constant."""
    spec = importlib.util.spec_from_file_location("benchmark", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def save_run_order(run_list, seed, results_base):
    path = os.path.join(results_base, "run_order.csv")
    
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", seed])
        writer.writerow([])
        writer.writerow(["position", "branch", "run_idx"])
        for i, (branch, run_idx) in enumerate(run_list, 1):
            writer.writerow([i, branch, run_idx])
    print(f"  Run order saved to {path}  (seed={seed})")


def run_single(branch, benchmark, out_dir):
    git(["checkout", branch])
    env = {**os.environ, "BT_OUTPUT_DIR": out_dir}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            subprocess.run(
                [sys.executable, benchmark],
                env=env,
                cwd=REPO_ROOT,
                check=True,
            )
            return
        except subprocess.CalledProcessError as e:
            if attempt < max_retries - 1:
                print(f"  Run failed with {e}, retrying in 30s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(30)
            else:
                print(f"  Run failed after {max_retries} attempts, skipping.")
                raise

def analyze_branch(branch, benchmark, results_base):
    out_dir = os.path.join(results_base, branch)
    runnext_file = os.path.join(out_dir, "energy_runnext.csv")
    summary_file = os.path.join(out_dir, "energy_summary.csv")
    baseline_file = os.path.join(results_base, "baseline", "energy_runnext.csv")

    if not os.path.exists(runnext_file):
        print(f"  WARNING: no energy file for branch '{branch}', skipping analysis")
        return

    analysis_script = os.path.join(os.path.dirname(benchmark), "analyze_energy.py")
    cmd = [sys.executable, analysis_script, "--input", runnext_file, "--output", summary_file]
    
    if branch != "baseline" and os.path.exists(baseline_file):
        cmd += ["--baseline", baseline_file]
    
    subprocess.run(cmd, check=True)

def compare_results(branches, results_base):
    rows = {}
    for branch in branches:
        summary_path = os.path.join(results_base, branch, "energy_summary.csv")
        if not os.path.exists(summary_path):
            print(f"  WARNING: no summary found for branch '{branch}' at {summary_path}")
            continue

        summary = {"branch": branch}
        with open(summary_path, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                key = row[0]
                if key == "mean":
                    summary["mean_duration_s"] = float(row[1])
                    summary["mean_cpu_energy_J"] = float(row[2])
                    summary["mean_total_energy_J"] = float(row[3])
                elif key == "std":
                    summary["std_cpu_energy_J"] = float(row[2])
                    summary["std_total_energy_J"] = float(row[3])
                elif key == "pct_reduction":
                    summary["pct_reduction_cpu"] = float(row[1])
                    summary["pct_reduction_total"] = float(row[2])
                elif key == "mann_whitney_p":
                    summary["p_cpu"] = float(row[1])
                    summary["p_total"] = float(row[2])
                elif key == "h2_rejected":
                    summary["h2_rejected_cpu"] = row[1]
                    summary["h2_rejected_total"] = row[2]
        rows[branch] = summary

    if not rows:
        print("No results to compare.")
        return

    b1 = rows.get("changes_1", {}).get("pct_reduction_cpu", 0)
    b2 = rows.get("changes_2", {}).get("pct_reduction_cpu", 0)
    b3 = rows.get("changes_3", {}).get("pct_reduction_cpu", 0)

    combinations = {
        "changes_1_2":   b1 + b2,
        "changes_1_3":   b1 + b3,
        "changes_2_3":   b2 + b3,
        "changes_1_2_3": b1 + b2 + b3,
    }

    for branch, expected in combinations.items():
        if branch in rows:
            observed = rows[branch].get("pct_reduction_cpu", 0)
            diff = observed - expected
            if abs(diff) < 0.5:
                effect = "additive"
            elif diff > 0:
                effect = "superadditive"
            else:
                effect = "subadditive"
            rows[branch]["h3_expected_pct"] = round(expected, 4)
            rows[branch]["h3_observed_pct"] = round(observed, 4)
            rows[branch]["h3_difference_pct"] = round(diff, 4)
            rows[branch]["h3_effect"] = effect

    comparison_path = os.path.join(results_base, "comparison.csv")
    fieldnames = [
        "branch",
        "mean_duration_s",
        "mean_cpu_energy_J",
        "std_cpu_energy_J",
        "mean_total_energy_J",
        "std_total_energy_J",
        "pct_reduction_cpu",
        "pct_reduction_total",
        "p_cpu",
        "p_total",
        "h2_rejected_cpu",
        "h2_rejected_total",
        "h3_expected_pct",
        "h3_observed_pct",
        "h3_difference_pct",
        "h3_effect",
    ]
    with open(comparison_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows.values())

    print(f"Comparison written to {comparison_path}")
    
def main():
    parser = argparse.ArgumentParser(
        description="Run benchmarks across all architecture branches."
    )
    parser.add_argument(
        "--branches",
        nargs="+",
        default=DEFAULT_BRANCHES,
        metavar="BRANCH",
        help="Branches to benchmark (default: %(default)s)",
    )
    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        metavar="PATH",
        help="Benchmark script to run (default: maxStressRun.py)",
    )
    args = parser.parse_args()

    check_clean_tree() # stop with uncommited changes

    benchmark_mod = load_benchmark_module(args.benchmark)
    n_runs = benchmark_mod.N_RUNS

    total = len(args.branches) * n_runs
    print(f"Benchmarking branches: {args.branches}")
    print(f"Benchmark script:      {args.benchmark}")
    print(f"Runs per branch:       {n_runs}  (total: {total}, shuffled)")
    print(f"Cooldown between runs: {COOLDOWN_S}s")
    print(f"Results directory:     {RESULTS_BASE}\n")

    # Clean up stale results from previous runs
    for branch in args.branches:
        shutil.rmtree(os.path.join(RESULTS_BASE, branch), ignore_errors=True)
    for filename in ["comparison.csv", "hardware.txt", "run_order.csv"]:
        path = os.path.join(RESULTS_BASE, filename)
        if os.path.exists(path):
            os.remove(path)

    # Create output dirs upfront (needed since runs are interleaved)
    os.makedirs(RESULTS_BASE, exist_ok=True)
    for branch in args.branches:
        os.makedirs(os.path.join(RESULTS_BASE, branch), exist_ok=True)

    save_hardware_info(RESULTS_BASE)

    origin_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()

    # Sync all branches to their remote state
    for branch in args.branches:
        git(["fetch", "origin", branch])
        git(["checkout", branch])
        git(["merge", "--ff-only", f"origin/{branch}"])

    # Build and shuffle the full run list
    seed = random.randrange(sys.maxsize)
    random.seed(seed)
    run_list = [
        (branch, run_idx)
        for branch in args.branches
        for run_idx in range(1, n_runs + 1)
    ]
    random.shuffle(run_list)
    save_run_order(run_list, seed, RESULTS_BASE)

    for i, (branch, run_idx) in enumerate(run_list, 1):
        out_dir = os.path.join(RESULTS_BASE, branch)
        print(f"\n{'=' * 60}")
        print(f"  [{i}/{total}]  branch={branch}  run={run_idx}")
        print(f"{'=' * 60}")
        run_single(branch, args.benchmark, out_dir)

        if i < total:
            print(f"  Cooldown {COOLDOWN_S}s...")
            time.sleep(COOLDOWN_S)

    git(["checkout", origin_branch])

    print("\nAll runs done. Running per-branch energy analysis...")
    for branch in args.branches:
        print(f"  Analyzing {branch}...")
        analyze_branch(branch, args.benchmark, RESULTS_BASE)

    print("\nGenerating cross-branch comparison...")
    compare_results(args.branches, RESULTS_BASE)

if __name__ == "__main__":
    main()