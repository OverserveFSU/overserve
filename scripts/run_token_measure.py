#!/usr/bin/env python3
"""Measure token amplification of a chosen best attack (naive + cached)."""
# --- overserve path bootstrap (reorganized layout; see overserve_paths.py) ---
import os as _ovp_os, sys as _ovp_sys
_ovp_d = _ovp_os.path.dirname(_ovp_os.path.abspath(__file__))
while _ovp_d != _ovp_os.path.dirname(_ovp_d) and not _ovp_os.path.exists(_ovp_os.path.join(_ovp_d, "overserve_paths.py")):
    _ovp_d = _ovp_os.path.dirname(_ovp_d)
if _ovp_d not in _ovp_sys.path:
    _ovp_sys.path.insert(0, _ovp_d)
import overserve_paths  # noqa
# --- end overserve path bootstrap ---
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
