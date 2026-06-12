import json
import sys
import os


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def compare_outputs(baseline_path, modified_path):
    baseline = load_json(baseline_path)
    modified = load_json(modified_path)

    if len(baseline) != len(modified):
        print(f"FAIL: different number of bars — baseline: {len(baseline)}, modified: {len(modified)}")
        return False

    mismatches = 0
    for i, (b, m) in enumerate(zip(baseline, modified)):
        if abs(b - m) > 1e-6:
            mismatches += 1

    if mismatches == 0:
        print(f"PASS: outputs are identical across {len(baseline)} bars")
        print(f"Final portfolio value: {baseline[-1]:.2f}")
        return True
    mape = sum(abs(b - m) / abs(b) for b, m in zip(baseline, modified) if b != 0) / len(baseline) * 100
    print(f"FAIL: {mismatches} bars differ")
    print(f"MAPE: {mape:.6f}%")
    return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compareOutput.py <baseline.json> <modified.json>")
        sys.exit(1)

    baseline_path = sys.argv[1]
    modified_path = sys.argv[2]

    if not os.path.exists(baseline_path):
        print(f"Error: baseline file not found: {baseline_path}")
        sys.exit(1)

    if not os.path.exists(modified_path):
        print(f"Error: modified file not found: {modified_path}")
        sys.exit(1)

    success = compare_outputs(baseline_path, modified_path)
    sys.exit(0 if success else 1)