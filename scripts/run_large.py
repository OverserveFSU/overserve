#!/usr/bin/env python3
"""Run OverServe at scale across many real tasks (resumable)."""
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
from overserve import large_scale

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=10)
    ap.add_argument("--pool", type=int, default=6, help="existing seeds per task")
    ap.add_argument("--gen", type=int, default=4, help="generated seeds per task")
    ap.add_argument("--base", type=int, default=2, help="baseline denoise runs")
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--ckpt", default="overserve_large_results.jsonl")
    a = ap.parse_args()
    large_scale.run(n_tasks=a.tasks, n_pool=a.pool, n_gen=a.gen,
                    n_base=a.base, cap=a.cap, ckpt=a.ckpt)
