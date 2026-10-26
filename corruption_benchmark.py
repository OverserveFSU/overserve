"""INSTRUCTION CORRUPTION BENCHMARK (ImageNet-C paradigm for tool agents).
Fix the ground truth (task graph G); apply a corruption TYPE at increasing SEVERITY; measure the
agent's compute (calls/reads) and FIDELITY (the label-preservation check). Expected shape, like CV:
  low severity  -> robust (same behavior)
  mid severity  -> DEGRADED-BUT-RECOVERS = extra search/inference (our 'detour', compute UP, fid still 1)
  high severity -> FAILURE (fidelity falls off a cliff)
The DoE operating point = the peak compute where fidelity is still 1.0 (just before the cliff).

Use case: tag_with_members. Ground truth G fixed: Beta Testers tag = {John Davis, Dave Brown, Sophia
Bennett}. Corruption type here = ENTITY-REFERENCE clarity (data axis), severity 0..6.
"""
import os, sys, glob, json, statistics
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

TASK = glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks/*tag_with_members*.json')[0]
REP = int(os.environ.get("CORRUPT_REP", 3))
T = 'In the TechCorp Solutions team, create a teamwork tag named "Beta Testers" and add %s to it.'

# severity-controlled corruption of the ENTITY REFERENCES (ground truth = the same 3 people)
SEVERITY = [
  (0, 'John Davis, Dave Brown, and Sophia Bennett'),        # full, explicit
  (1, 'John Davis, Dave Brown, Sophia Bennett'),            # drop connective (mild)
  (2, 'John, Dave, and Sophia Bennett'),                    # 2 of 3 -> first name
  (3, 'John, Dave, and Sophia'),                            # all first names
  (4, "John from Davis' team, Dave, and Soph B."),          # partial / attribute reference
  (5, 'Johnny, Dave, and Soph'),                            # nicknames / abbreviations
  (6, 'the three beta testers'),                            # fully referential (likely past the cliff)
]

def reads(trace):
    return sum(1 for t in trace if t.split('(')[0] in ('list_users', 'get_user', 'find_users', 'search_users'))


def main():
    tj = json.load(open(TASK))
    print(f"[corruption bench] type=entity-reference clarity ; G fixed={{John,Dave,Sophia}} ; REP={REP}\n", flush=True)
    log = open("corruption_benchmark.jsonl", "w"); rows = []
    for sev, ref in SEVERITY:
        prompt = T % ref
        calls, rd, fids = [], [], []
        for _ in range(REP):
            import tempfile
            d = json.loads(json.dumps(tj)); d["user_prompt"] = prompt
            tmp = tempfile.mkdtemp(); p = tmp + "/t.json"; json.dump(d, open(p, "w"))
            f = run_agent_fitness(task_src=p, cap=25)
            if f:
                calls.append(f["n_calls"]); rd.append(reads(f["tool_trace"])); fids.append(round(f["chkpt"], 2))
        if not calls:
            print(f"  S{sev}: FAILED", flush=True); continue
        rec = {"severity": sev, "ref": ref, "calls": calls, "calls_med": int(statistics.median(calls)),
               "reads_med": int(statistics.median(rd)), "fid_med": statistics.median(fids), "fid": fids,
               "fid_ok": statistics.median(fids) >= 0.95}
        rows.append(rec); log.write(json.dumps(rec) + "\n"); log.flush()
        bar = "#" * rec["calls_med"]
        print("  S%d calls=%-11s med=%2d %-14s reads=%d fid=%.2f %s :: %s" %
              (sev, calls, rec["calls_med"], bar, rec["reads_med"], rec["fid_med"],
               "OK " if rec["fid_ok"] else "CLIFF", ref[:40]), flush=True)
    # response curve summary
    print("\n=== corruption response curve ===", flush=True)
    base = rows[0]["calls_med"] if rows else 1
    ok = [r for r in rows if r["fid_ok"]]
    print("severity : compute(calls) : fidelity", flush=True)
    for r in rows:
        print("  S%d      :  %2d (%.2fx)      :  %.2f %s" %
              (r["severity"], r["calls_med"], r["calls_med"] / base, r["fid_med"],
               "" if r["fid_ok"] else "<- FAILURE CLIFF"), flush=True)
    if ok:
        peak = max(ok, key=lambda x: x["calls_med"])
        cliff = next((r["severity"] for r in rows if not r["fid_ok"]), None)
        print(f"\nDoE operating point = S{peak['severity']} (peak compute {peak['calls_med']} = "
              f"{round(peak['calls_med']/base,2)}x, fidelity still 1.0). Failure cliff at "
              f"S{cliff}." if cliff is not None else f"; no cliff reached up to S{rows[-1]['severity']}.", flush=True)
    json.dump(rows, open("corruption_benchmark_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
