"""Validate the refactored single-objective tasks: run each task's OWN prompt, keep only those whose
benign prompt actually achieves the objective (fidelity == 1.0), and assign the final difficulty
LEVEL from the measured baseline call-count. Writes the benchmark manifest + distribution.

  atomic:     2-4 calls
  structured: 5-8 calls
  compound:   9+ calls
Resumable: appends to bench_measure.jsonl and skips files already measured.
"""
import os, sys, glob, json
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

TASKS = "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks"
MEAS = "bench_measure.jsonl"


def level_of(calls):
    if calls <= 4: return "atomic"
    if calls <= 8: return "structured"
    return "compound"


def main():
    files = sorted(glob.glob(f"{TASKS}/*.json"))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    done = {}
    if os.path.exists(MEAS):
        for l in open(MEAS):
            try:
                r = json.loads(l); done[r["file"]] = r
            except Exception: pass
    print(f"{len(files)} tasks, {len(done)} already measured", flush=True)
    out = open(MEAS, "a")
    for fp in files:
        fn = os.path.basename(fp)
        if fn in done: continue
        j = json.load(open(fp)); meta = j.get("_meta", {})
        f = run_agent_fitness(task_src=fp, cap=20)
        if not f:
            r = {"file": fn, "calls": 0, "fidelity": 0, "level": "FAIL", "declared": meta.get("level"),
                 "objective": meta.get("objective"), "source": meta.get("source")}
        else:
            r = {"file": fn, "calls": f["n_calls"], "turns": f["turns"], "fidelity": round(f["chkpt"], 2),
                 "level": level_of(f["n_calls"]), "declared": meta.get("level"),
                 "objective": meta.get("objective"), "source": meta.get("source"),
                 "n_verifiers": len(j["verifiers"])}
        out.write(json.dumps(r) + "\n"); out.flush()
        print("%-42s calls=%2s fid=%s level=%-10s (declared %s) %s" %
              (fn[:42], r["calls"], r["fidelity"], r["level"], r.get("declared"),
               "OK" if r["fidelity"] == 1.0 else "!! benign did not achieve goal"), flush=True)
    # assemble manifest of VALID tasks (fidelity 1.0)
    rows = [json.loads(l) for l in open(MEAS)]
    valid = [r for r in rows if r.get("fidelity") == 1.0]
    from collections import Counter
    print("\n=== VALID benchmark (fidelity 1.0) ===", flush=True)
    print("total valid:", len(valid), "/", len(rows), flush=True)
    print("level distribution:", dict(Counter(r["level"] for r in valid)), flush=True)
    json.dump(valid, open(os.path.join(TASKS, "_manifest.json"), "w"), indent=1)
    print("manifest ->", os.path.join(TASKS, "_manifest.json"), flush=True)


if __name__ == "__main__":
    main()
