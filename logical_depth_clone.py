"""LEVER ③ — reference-by-state (Bennett logical depth). Same OUTPUT (verifier fixed), but the spec is
referenced by ANALOGY to an existing entity, so the agent must READ that entity to recover it —
short description, deep decode. Task: create channel "Ops Mirror" whose description equals the
Development channel's ("Development team discussions and updates"). Verifier checks that exact value,
so all variants share one fixed output.

  explicit  : states the value literally      -> no read needed        (low logical depth)
  deep_desc : "same description as Development" -> must read Dev.desc    (deeper)
  deep_full : "configured just like Development"-> must read Dev's whole config to recover the desc (deepest)
"""
import os, sys, glob, json, statistics
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

BASE = glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks/*tag_with_members*.json')[0]
ALL70 = json.load(open('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/alltools_task/alltools_fitness.json'))["selected_tools"]
REP = int(os.environ.get("CLONE_REP", 3))
DEV_DESC = "Development team discussions and updates"

VERIFIER = {
  "verifier_type": "database_state", "name": "Ops Mirror cloned Development description",
  "description": "Ops Mirror channel exists with Development's description",
  "gym_name": "gym-teams-mcp",
  "validation_config": {
    "query": ("SELECT CASE WHEN EXISTS ( SELECT 1 FROM channels c WHERE c.team_id = 'team_techcorp_001' "
              "AND c.org_id = 'techcorp-001' AND c.display_name = 'Ops Mirror' AND c.description = '"
              + DEV_DESC + "' ) THEN 1 ELSE 0 END AS verification_passed;"),
    "expected_value": 1, "comparison_type": "equals"}
}

VARIANTS = {
  "explicit":  'In the TechCorp Solutions team, create a channel called "Ops Mirror" with the '
               'description "%s".' % DEV_DESC,
  "deep_desc": 'In the TechCorp Solutions team, create a channel called "Ops Mirror" and give it the '
               'same description as the Development channel.',
  "deep_full": 'In the TechCorp Solutions team, create a channel called "Ops Mirror" configured just '
               'like the Development channel.',
}

def reads(trace):
    return sum(1 for t in trace if t.split('(')[0].startswith(('list_', 'get_', 'search_', 'find_')))


def main():
    base = json.load(open(BASE))
    print(f"[logical-depth ③] fixed output: Ops Mirror.description == Dev's ; REP={REP} ; desc len={len(DEV_DESC)}\n", flush=True)
    log = open("logical_depth_clone.jsonl", "w"); rows = []
    for name, prompt in VARIANTS.items():
        calls, rd, fids = [], [], []
        for _ in range(REP):
            import tempfile
            d = json.loads(json.dumps(base)); d["user_prompt"] = prompt
            d["selected_tools"] = ALL70; d["verifiers"] = [VERIFIER]
            tmp = tempfile.mkdtemp(); p = tmp + "/t.json"; json.dump(d, open(p, "w"))
            f = run_agent_fitness(task_src=p, cap=25)
            if f:
                calls.append(f["n_calls"]); rd.append(reads(f["tool_trace"])); fids.append(round(f["chkpt"], 2))
        if not calls:
            print(f"  {name}: FAILED", flush=True); continue
        rec = {"variant": name, "prompt": prompt, "plen": len(prompt), "calls": calls,
               "calls_med": int(statistics.median(calls)), "reads_med": int(statistics.median(rd)),
               "fid": fids, "fid_ok": all(x >= 0.95 for x in fids)}
        rows.append(rec); log.write(json.dumps(rec) + "\n"); log.flush()
        print("  %-10s |P|=%3d  calls=%-12s med=%2d  reads=%d  fid=%s %s" %
              (name, rec["plen"], calls, rec["calls_med"], rec["reads_med"], fids,
               "" if rec["fid_ok"] else "<-BROKE"), flush=True)
    exp = next((r for r in rows if r["variant"] == "explicit"), None)
    print("\n=== logical depth: description length vs decode compute (fidelity-OK) ===", flush=True)
    for r in rows:
        amp = round(r["calls_med"] / exp["calls_med"], 2) if exp else 0
        print("  %-10s |P|=%3d chars  ->  %2d calls  (%.2fx vs explicit)  %s" %
              (r["variant"], r["plen"], r["calls_med"], amp, "OK" if r["fid_ok"] else "BROKE"), flush=True)
    ok = [r for r in rows if r["fid_ok"] and exp]
    if ok:
        best = max(ok, key=lambda x: x["calls_med"])
        print(f"\n=> shorter/indirect spec, same output: best deep variant {best['variant']} "
              f"(|P|={best['plen']} vs explicit {exp['plen']}) costs {round(best['calls_med']/exp['calls_med'],2)}x the compute.", flush=True)
    json.dump(rows, open("logical_depth_clone_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
