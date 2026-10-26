"""Capture the full OPERATION TRACE for each refactored task: run its own benign prompt on the victim
agent and record the ordered tool-call sequence + calls/turns/fidelity/tokens. Resumable (skip files
already in bench_traces.jsonl). One record per task -> bench_traces.jsonl."""
import os, sys, glob, json
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

TASKS = "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks"
OUT = "bench_traces.jsonl"

files = sorted(f for f in glob.glob(f"{TASKS}/*.json") if not os.path.basename(f).startswith("_"))
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)["file"])
        except Exception: pass
print(f"{len(files)} tasks, {len(done)} already captured", flush=True)
out = open(OUT, "a")
for fp in files:
    fn = os.path.basename(fp)
    if fn in done: continue
    j = json.load(open(fp)); meta = j.get("_meta", {})
    f = run_agent_fitness(task_src=fp, cap=20)
    rec = {"file": fn, "objective": meta.get("objective"), "level": meta.get("level"),
           "source": meta.get("source"), "prompt": j["user_prompt"],
           "calls": (f["n_calls"] if f else 0), "turns": (f["turns"] if f else 0),
           "fidelity": (round(f["chkpt"], 2) if f else 0),
           "tokens_naive": (f["tokens"] if f else 0), "tokens_cached": (f["tokens_cached"] if f else 0),
           "trace": (f["tool_trace"] if f else [])}
    out.write(json.dumps(rec) + "\n"); out.flush()
    print("%-44s calls=%2d fid=%s | %s" % (fn[:44], rec["calls"], rec["fidelity"],
          " -> ".join(rec["trace"][:6]) + (" ..." if len(rec["trace"]) > 6 else "")), flush=True)
print("DONE ->", OUT, flush=True)
