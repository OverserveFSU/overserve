#!/usr/bin/env python3
"""Run OverServe seed-iteration on a single real task."""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from overserve import seed_iter

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--eval0", type=int, default=8, help="existing-pool seeds in round 0")
    ap.add_argument("--gen", type=int, default=6, help="generated seeds per round")
    ap.add_argument("--task-index", type=int, default=0)
    ap.add_argument("--cap", type=int, default=None)
    a = ap.parse_args()
    seed_iter.run(rounds=a.rounds, n_eval0=a.eval0, n_gen=a.gen,
                  task_index=a.task_index, cap=a.cap)
