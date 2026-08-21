"""OverServe on a SINGLE real task — the feedback-driven seed-iteration loop.

This is the core contribution: close the loop at the SEED layer. Round 0 evaluates a sample of the
existing strategy pool; each later round feeds the winning/losing mechanisms back to the STRONG
generator, which proposes new strategies; keep the best. (Prior GA/GEPA search over tasks or the
fuse-instruction never beat the initial content — regenerating SEEDS from feedback does.)
"""
import os
import json
import random
import statistics

from . import config
from .bench import load_seed_pool, load_tasks, run_prompt
from .fusion import generate
from .score import eval_seed


def run(rounds=2, n_eval0=8, n_gen=6, cap=None, task_index=0,
        log_path="overserve_seed_iter.jsonl", best_path="overserve_seed_iter_best.json"):
    """Run the seed-iteration attack on one real task.

    rounds   : feedback rounds after round 0
    n_eval0  : existing-pool strategies evaluated in round 0
    n_gen    : new strategies the generator proposes per round
    task_index: which sorted real task to attack
    Returns the best result dict.
    """
    config.require_key()
    cap = config.CAP if cap is None else cap
    random.seed(config.SEED)

    pool = load_seed_pool()
    real_json = json.load(open(load_tasks()[task_index]))
    real_prompt = real_json["user_prompt"]

    # denoised baseline for the eval task (median of 3 clean runs)
    cs = [run_prompt(real_json, real_prompt, cap=cap) for _ in range(3)]
    cs = [c for c in cs if c]
    base = int(statistics.median([c["n_calls"] for c in cs]))
    base_goal = statistics.median([c["chkpt"] for c in cs])
    print(f"[overserve] eval task baseline calls={base} goal={base_goal}", flush=True)

    log = open(log_path, "w")

    def _record(rd, r):
        log.write(json.dumps({"round": rd, **{k: r[k] for k in
                  ('score', 'matched', 'calls', 'stealth', 'fidelity', 'seed')}}) + "\n")
        log.flush()
        print(f"[r{rd}] score={r['score']} amp={r['matched']}x calls={r['calls']} "
              f"stealth={r['stealth']} fid={r['fidelity']} :: {r['seed'][:50]}", flush=True)

    # round 0: even-stride sample of the existing pool
    stride = max(1, len(pool) // n_eval0)
    evaluated = []
    for seed in pool[::stride][:n_eval0]:
        r = eval_seed(real_json, real_prompt, base, base_goal, seed, cap=cap)
        if not r:
            continue
        evaluated.append(r)
        _record(0, r)
    best = max(evaluated, key=lambda x: x["score"])

    # feedback rounds: regenerate seeds from what worked / failed
    for rd in range(1, rounds + 1):
        evaluated.sort(key=lambda x: -x["score"])
        top = evaluated[:4]
        bottom = [e for e in evaluated if e["score"] == 0][:4] or evaluated[-3:]
        new_seeds = generate(top, bottom, n_gen)
        print(f"[r{rd}] generator produced {len(new_seeds)} new seeds", flush=True)
        for seed in new_seeds:
            r = eval_seed(real_json, real_prompt, base, base_goal, seed, cap=cap)
            if not r:
                continue
            evaluated.append(r)
            if r["score"] > best["score"]:
                best = r
            _record(rd, r)

    print("\n=== OverServe (single-task) DONE ===", flush=True)
    print(f"BEST amp={best['matched']}x score={best['score']} (calls {best['calls']}/{base}) "
          f"stealth={best['stealth']} fid={best['fidelity']}", flush=True)
    print("BEST seed:", json.dumps(best["seed"])[:400], flush=True)
    json.dump(best, open(best_path, "w"), indent=1)
    return best


if __name__ == "__main__":
    run(rounds=int(os.environ.get("OVERSERVE_ROUNDS", 2)),
        n_eval0=int(os.environ.get("OVERSERVE_EVAL0", 8)),
        n_gen=int(os.environ.get("OVERSERVE_GEN", 6)))
