# run_comparison.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_experiments import compare_results, DEFAULT_BRANCHES

RESULTS_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
compare_results(DEFAULT_BRANCHES, RESULTS_BASE)