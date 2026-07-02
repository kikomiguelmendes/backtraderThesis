import os
import sys
import csv
import time
import random
import re
import math
import argparse
import subprocess
import shutil
import importlib.util
import tempfile
import datetime

from scipy.stats import t as t_dist

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Install with: pip install psutil")
    sys.exit(1)

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
IDLE_BASELINE_DURATION_S = 120
CPU_CHECK_INTERVAL_S = 15
CPU_LOAD_TOLERANCE = 10.0  # percentage points above idle baseline

ENERGY_CSV_FIELDS = ["duration_s", "cpu_energy_kWh", "energy_consumed_kWh"]


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


def _log(results_base, branch, run_idx, message):
    """Append one entry to the branch error log, flushed immediately."""
    log_path = os.path.join(results_base, branch, "experiment_errors.log")
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] branch={branch} run={run_idx}: {message}\n")


def measure_idle_cpu():
    """Block for IDLE_BASELINE_DURATION_S seconds and return average CPU load."""
    print(f"Measuring idle CPU baseline over {IDLE_BASELINE_DURATION_S}s...")
    baseline = psutil.cpu_percent(interval=IDLE_BASELINE_DURATION_S)
    print(f"  Idle CPU baseline: {baseline:.1f}%")
    return baseline


def wait_for_cpu(idle_baseline, results_base, branch, run_idx):
    """
    Block until CPU load is within CPU_LOAD_TOLERANCE percentage points of
    idle_baseline. Rechecks every CPU_CHECK_INTERVAL_S seconds. Logs to the
    branch error log if any waiting was necessary.
    """
    wait_start = time.monotonic()
    had_to_wait = False

    while True:
        current = psutil.cpu_percent(interval=1)  # 1-second blocking measurement
        if current <= idle_baseline + CPU_LOAD_TOLERANCE:
            if had_to_wait:
                elapsed = time.monotonic() - wait_start
                msg = (
                    f"CPU load settled to {current:.1f}% after {elapsed:.0f}s "
                    f"(baseline={idle_baseline:.1f}%, tolerance=+{CPU_LOAD_TOLERANCE}%)"
                )
                print(f"  {msg}")
                _log(results_base, branch, run_idx, f"CPU wait resolved: {msg}")
            return

        if not had_to_wait:
            had_to_wait = True
            print(
                f"  CPU load {current:.1f}% exceeds idle baseline "
                f"{idle_baseline:.1f}% + {CPU_LOAD_TOLERANCE}%. Waiting..."
            )
        # cpu_percent(interval=1) already consumed 1s; sleep the remainder
        time.sleep(CPU_CHECK_INTERVAL_S - 1)


def run_single(branch, benchmark, results_base, run_idx, idle_baseline):
    """
    Run the benchmark once for the given branch. Each attempt uses a fresh
    temp directory so that a failed run cannot leave a partial CSV row. Returns
    a dict with the energy row on success, or raises after all retries.
    """
    git(["checkout", branch])

    max_retries = 3
    for attempt in range(max_retries):
        wait_for_cpu(idle_baseline, results_base, branch, run_idx)

        tmp_dir = tempfile.mkdtemp(prefix=f"bt_{branch}_{run_idx}_")
        try:
            env = {**os.environ, "BT_OUTPUT_DIR": tmp_dir}
            subprocess.run(
                [sys.executable, benchmark],
                env=env,
                cwd=REPO_ROOT,
                check=True,
            )

            csv_path = os.path.join(tmp_dir, "energy_runnext.csv")
            with open(csv_path, newline="") as f:
                rows = list(csv.DictReader(f))

            if not rows:
                raise ValueError("energy_runnext.csv is empty after completed run")

            return rows[-1]

        except (subprocess.CalledProcessError, ValueError, OSError) as exc:
            error_msg = str(exc)
            _log(results_base, branch, run_idx, f"Run failed: {error_msg}")

            if attempt < max_retries - 1:
                retry_note = f"attempt {attempt + 1}/{max_retries}, retrying in 30s"
                print(f"  Run failed ({error_msg}), {retry_note}")
                _log(results_base, branch, run_idx, f"Retry: {retry_note}")
                time.sleep(30)
            else:
                print(f"  Run failed after {max_retries} attempts, skipping.")
                raise

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def write_accumulated_results(accumulated, results_base):
    """Write in-memory results to per-branch energy_runnext.csv files."""
    print("\nWriting accumulated energy data...")
    for branch, rows in accumulated.items():
        if not rows:
            print(f"  WARNING: no rows accumulated for branch '{branch}', skipping write")
            continue
        out_path = os.path.join(results_base, branch, "energy_runnext.csv")
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ENERGY_CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Wrote {len(rows)} rows to {out_path}")


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


def _individual_branches(branch):
    """
    Return the individual branch names making up a combination branch, e.g.
    'changes_1_2_3' -> ['changes_1', 'changes_2', 'changes_3']. Returns []
    for 'baseline' or any branch that isn't a multi-index combination.
    """
    if not re.fullmatch(r"changes(_\d+)+", branch):
        return []
    indices = branch.split("_")[1:]
    if len(indices) < 2:
        return []
    return [f"changes_{i}" for i in indices]


def _count_runs(results_base, branch):
    """Number of runs for a branch, counted from its energy_runnext.csv."""
    path = os.path.join(results_base, branch, "energy_runnext.csv")
    with open(path, newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # minus header row


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
        summary["n"] = _count_runs(results_base, branch)
        rows[branch] = summary

    if not rows:
        print("No results to compare.")
        return

    for branch in rows:
        individuals = _individual_branches(branch)
        if not individuals or "baseline" not in rows:
            continue
        if not all(ind in rows for ind in individuals):
            continue

        combo = rows[branch]
        base = rows["baseline"]
        indiv_rows = [rows[ind] for ind in individuals]
        k = len(individuals)

        expected = sum(r.get("pct_reduction_total", 0) for r in indiv_rows)
        observed = combo.get("pct_reduction_total", 0)

        baseline_coef = -(k - 1)
        delta = (
            sum(r["mean_total_energy_J"] for r in indiv_rows)
            + baseline_coef * base["mean_total_energy_J"]
            - combo["mean_total_energy_J"]
        )

        # Independent sample means -> variances add, no covariance terms.
        # Baseline enters delta with coefficient baseline_coef, so error
        # propagation weights its variance term by baseline_coef ** 2.
        var_terms = [combo["std_total_energy_J"] ** 2 / combo["n"]]
        df_denoms = [combo["n"] - 1]
        for r in indiv_rows:
            var_terms.append(r["std_total_energy_J"] ** 2 / r["n"])
            df_denoms.append(r["n"] - 1)
        var_terms.append(baseline_coef ** 2 * base["std_total_energy_J"] ** 2 / base["n"])
        df_denoms.append(base["n"] - 1)

        var_delta = sum(var_terms)
        se = math.sqrt(var_delta)

        # Welch-Satterthwaite approximation for degrees of freedom.
        dof = var_delta ** 2 / sum(v ** 2 / d for v, d in zip(var_terms, df_denoms))

        t_crit = t_dist.ppf(0.975, dof)
        ci_lower = delta - t_crit * se
        ci_upper = delta + t_crit * se

        if ci_lower <= 0 <= ci_upper:
            classification = "Additive"
        elif ci_lower > 0:
            classification = "Super-additive"
        else:
            classification = "Sub-additive"

        rows[branch]["h3_expected_pct"] = round(expected, 4)
        rows[branch]["h3_observed_pct"] = round(observed, 4)
        rows[branch]["h3_difference_pct"] = round(observed - expected, 4)
        rows[branch]["h3_delta_J"] = round(delta, 6)
        rows[branch]["h3_se_J"] = round(se, 6)
        rows[branch]["h3_ci_lower_J"] = round(ci_lower, 6)
        rows[branch]["h3_ci_upper_J"] = round(ci_upper, 6)
        rows[branch]["h3_df"] = round(dof, 3)
        rows[branch]["h3_classification"] = classification

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
        "h3_delta_J",
        "h3_se_J",
        "h3_ci_lower_J",
        "h3_ci_upper_J",
        "h3_df",
        "h3_classification",
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

    check_clean_tree()

    benchmark_mod = load_benchmark_module(args.benchmark)
    n_runs = benchmark_mod.N_RUNS

    total = len(args.branches) * n_runs
    print(f"Benchmarking branches: {args.branches}")
    print(f"Benchmark script:      {args.benchmark}")
    print(f"Runs per branch:       {n_runs}  (total: {total}, shuffled)")
    print(f"Cooldown between runs: {COOLDOWN_S}s")
    print(f"Results directory:     {RESULTS_BASE}\n")

    # Measure idle CPU before any experiment work begins
    idle_baseline = measure_idle_cpu()

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

    # Accumulate all energy rows in memory; nothing is written to the final
    # CSV until every run has completed successfully.
    accumulated = {branch: [] for branch in args.branches}

    for i, (branch, run_idx) in enumerate(run_list, 1):
        print(f"\n{'=' * 60}")
        print(f"  [{i}/{total}]  branch={branch}  run={run_idx}")
        print(f"{'=' * 60}")

        row = run_single(branch, args.benchmark, RESULTS_BASE, run_idx, idle_baseline)
        accumulated[branch].append(row)

        if i < total:
            print(f"  Cooldown {COOLDOWN_S}s...")
            time.sleep(COOLDOWN_S)

    git(["checkout", origin_branch])

    # All runs succeeded — flush the complete CSVs now
    write_accumulated_results(accumulated, RESULTS_BASE)

    print("\nAll runs done. Running per-branch energy analysis...")
    for branch in args.branches:
        print(f"  Analyzing {branch}...")
        analyze_branch(branch, args.benchmark, RESULTS_BASE)

    print("\nGenerating cross-branch comparison...")
    compare_results(args.branches, RESULTS_BASE)


if __name__ == "__main__":
    main()
