#!/usr/bin/env python3
"""Measure token amplification of a chosen best attack (naive + cached)."""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from overserve import token_measure

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--best", default="overserve_seed_iter_best.json")
    ap.add_argument("--task-index", type=int, default=0)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--cap", type=int, default=None)
    a = ap.parse_args()
    token_measure.run(best_path=a.best, task_index=a.task_index, n=a.n, cap=a.cap)
