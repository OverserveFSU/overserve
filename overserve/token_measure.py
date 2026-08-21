"""Measure the TOKEN amplification of a chosen attack, without re-running the search.

Given a best result JSON (from seed_iter, holding the `fused` prompt), run the real task's baseline
and the fused attack n times each and report calls / naive-token / cached-token amplification. Naive
= total tokens processed (prior-work convention); cached = real compute under prefix caching.
"""
import os
import json
import statistics

from . import config
from .bench import load_tasks, run_prompt


def _med(rows, key):
    return statistics.median([r[key] for r in rows])


def run(best_path="overserve_seed_iter_best.json", task_index=0, n=3, cap=None,
        out_path="overserve_token_measure.json"):
    cap = config.CAP if cap is None else cap
    best = json.load(open(best_path))
    fused = best["fused"]
    real_json = json.load(open(load_tasks()[task_index]))
    real_prompt = real_json["user_prompt"]
    print(f"[token] baseline len={len(real_prompt)} | fused len={len(fused)} | cap={cap} n={n}", flush=True)

    def batch(label, prompt):
        rows = []
        for i in range(n):
            r = run_prompt(real_json, prompt, cap=cap)
            if not r:
                print(f"  {label} run{i}: FAIL", flush=True)
                continue
            rows.append(r)
            print(f"  {label} run{i}: calls={r['n_calls']} turns={r['turns']} "
                  f"naive={r['tokens']} cached={r['tokens_cached']} exec_ms={r.get('exec_ms')} "
                  f"goal={r['chkpt']}", flush=True)
        return rows

    base = batch("BASE", real_prompt)
    atk = batch("ATK ", fused)

    def summ(rows):
        exec_rows = [r for r in rows if r.get("exec_ms") is not None]
        return dict(calls=_med(rows, "n_calls"), turns=_med(rows, "turns"),
                    naive=_med(rows, "tokens"), cached=_med(rows, "tokens_cached"),
                    exec_ms=(_med(exec_rows, "exec_ms") if exec_rows else None),
                    goal=_med(rows, "chkpt"))
    B, A = summ(base), summ(atk)
    print("\n=== AMPLIFICATION (median of %d) ===" % n)
    print(f"           calls  turns     naive_tok   cached_tok      exec_ms  goal")
    print(f"  BASE   {B['calls']:>5} {B['turns']:>5}   {B['naive']:>10}  {B['cached']:>9}  {str(B['exec_ms']):>11}  {B['goal']}")
    print(f"  ATTACK {A['calls']:>5} {A['turns']:>5}   {A['naive']:>10}  {A['cached']:>9}  {str(A['exec_ms']):>11}  {A['goal']}")
    print(f"\n  call_amp   = {A['calls']/max(1,B['calls']):.2f}x")
    print(f"  NAIVE amp  = {A['naive']/max(1,B['naive']):.2f}x   (total tokens processed)")
    print(f"  cached amp = {A['cached']/max(1,B['cached']):.2f}x   (real compute w/ prefix caching)")
    if B['exec_ms'] and A['exec_ms']:
        print(f"  LATENCY amp= {A['exec_ms']/max(1,B['exec_ms']):.2f}x   (wall-clock, EOG execution_time_ms)")
    print(f"  naive/cached overstate: BASE {B['naive']/max(1,B['cached']):.1f}x  "
          f"ATTACK {A['naive']/max(1,A['cached']):.1f}x")
    json.dump({"base": B, "attack": A, "base_runs": base, "attack_runs": atk},
              open(out_path, "w"), indent=1)
    print(f"\nTOKEN DONE -> {out_path}", flush=True)
    return {"base": B, "attack": A}


if __name__ == "__main__":
    run(best_path=os.environ.get("OVERSERVE_BEST", "overserve_seed_iter_best.json"),
        n=int(os.environ.get("OVERSERVE_N", 3)))
