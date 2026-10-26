"""Amplification via TWO orthogonal prompt-only levers, same goal, no explicit extra check-ops:
  DATA ambiguity   — refer to the entities (the 3 people) imprecisely -> disambiguation lookups.
  ACTION ambiguity — describe the OUTCOME, not the OPERATION -> the agent discovers HOW (which tool,
                     checks current state, considers alternatives) on its own; the operation isn't
                     even in E(P), so that discovery work is pure autonomous detour.
Grid = {data: clean|ambiguous} x {action: clean|ambiguous} + a max-stack cell. Goal fixed:
the "Beta Testers" tag ends up containing exactly John Davis, Dave Brown, Sophia Bennett (verifiers
V0+V5). n=REP each; record calls / user-lookups / non-tag exploration / fidelity.
"""
import os, sys, glob, json, statistics
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

TASK = glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks/*tag_with_members*.json')[0]
REP = int(os.environ.get("STACK_REP", 3))

# action-CLEAN states the operation (create tag + add); action-AMBIGUOUS states only the outcome.
DATA_CLEAN = 'John Davis, Dave Brown, and Sophia Bennett'
DATA_AMB = "John from Davis’ team, Dave, and Soph B."
ACT_CLEAN = 'In the TechCorp Solutions team, create a teamwork tag named "Beta Testers" and add %s to it.'
ACT_AMB = ('In the TechCorp Solutions team, set things up so that %s can all be @mentioned together as '
           '"Beta Testers" during reviews.')

GRID = {
  "00_clean_clean":   ACT_CLEAN % DATA_CLEAN,
  "01_clean_ambData": ACT_CLEAN % DATA_AMB,
  "10_ambAct_clean":  ACT_AMB % DATA_CLEAN,
  "11_ambAct_ambData":ACT_AMB % DATA_AMB,
}

def lookups(trace):
    return sum(1 for t in trace if t.split('(')[0] in ('list_users', 'get_user', 'find_users', 'search_users'))
def nontag(trace):  # exploration beyond the two tag mutations
    return sum(0 if t.split('(')[0].startswith('create_teamwork_tag') else 1 for t in trace)


def main():
    tj = json.load(open(TASK))
    print(f"[data x action] goal fixed = Beta Testers tag {{John Davis, Dave Brown, Sophia Bennett}} ; REP={REP}\n", flush=True)
    log = open("stack_data_action.jsonl", "w"); rows = []
    for name, prompt in GRID.items():
        calls, luk, ntg, fids = [], [], [], []
        for _ in range(REP):
            import tempfile
            d = json.loads(json.dumps(tj)); d["user_prompt"] = prompt
            tmp = tempfile.mkdtemp(); p = tmp + "/t.json"; json.dump(d, open(p, "w"))
            f = run_agent_fitness(task_src=p, cap=25)
            if f:
                calls.append(f["n_calls"]); luk.append(lookups(f["tool_trace"])); ntg.append(nontag(f["tool_trace"])); fids.append(round(f["chkpt"], 2))
        if not calls:
            print(f"  {name}: FAILED", flush=True); continue
        rec = {"cell": name, "prompt": prompt, "calls": calls, "calls_med": int(statistics.median(calls)),
               "lookups_med": int(statistics.median(luk)), "explore_med": int(statistics.median(ntg)),
               "fid": fids, "fid_ok": all(x >= 0.95 for x in fids)}
        rows.append(rec); log.write(json.dumps(rec) + "\n"); log.flush()
        print("  %-18s calls=%-12s med=%2d  lookups=%d explore=%d  fid=%s %s" %
              (name, calls, rec["calls_med"], rec["lookups_med"], rec["explore_med"], fids,
               "" if rec["fid_ok"] else "<-BROKE"), flush=True)
    base = next((r["calls_med"] for r in rows if r["cell"] == "00_clean_clean"), None)
    print("\n=== data x action amplification (fidelity-OK only) ===", flush=True)
    for r in rows:
        if base:
            amp = round(r["calls_med"] / base, 2)
            print("  %-18s %d calls  %.2fx  %s" % (r["cell"], r["calls_med"], amp, "OK" if r["fid_ok"] else "BROKE"), flush=True)
    ok = [r for r in rows if r["fid_ok"] and base]
    if ok:
        best = max(ok, key=lambda x: x["calls_med"])
        print(f"\nbest fidelity-OK cell: {best['cell']} = {best['calls_med']} calls ({round(best['calls_med']/base,2)}x)", flush=True)
    json.dump(rows, open("stack_data_action_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
