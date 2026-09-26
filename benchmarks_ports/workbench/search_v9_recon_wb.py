# FAITHFUL v9 (recon-seeded) on WorkBench. Same method as EW: LITERAL overserve judges
# (R9.instantiate+INST_SYS via GLM, V8.evaluate/score/is_corner, V7.connor_soft, V.judge_tool/judge_prompt),
# ONLY the rollout backend swapped -> workbench_adapter.rollout (qwen victim). V8.CORE="" (WB core = native task).
import os, sys, json, itertools
sys.path.insert(0, os.environ.get("OVERSERVE_DIR", "/home/ruiheng/aiagent/saas/overserve"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_search_v5 as V, toolatk_search_v7 as V7, toolatk_search_v8 as V8
import recon_to_search as R9
import workbench_adapter as BK

RECON = os.environ.get("RECON_JSON", "/home/ruiheng/aiagent/saas/overserve/recon_candidates_wb.json")
BUDGET = int(os.environ.get("ATK_BUDGET", "6"))
TASK_IDX = int(os.environ.get("WB_TASK", "0"))
LIN = os.environ.get("LINEAGE", "lineage_v9_recon_wb.jsonl")
ARCH = os.environ.get("ARCHIVE", "archive_v9_recon_wb.json")

V8.CORE = ""
def _wb_run_cond(spec, prompt, churn, tag):
    r = BK.rollout(spec, prompt, churn == "1", TASK_IDX)
    if not r or "total_calls" not in r:
        return {"error": "rollout:%s" % r}
    return {"total_calls": r["total_calls"], "fidelity": r["fidelity"]}
V8.run_cond = _wb_run_cond


def main():
    rc = json.load(open(RECON))
    gates = rc.get("gates", []); drivers = rc.get("drivers", [])
    pairs = list(rc.get("top_pairs", []))
    have = {(p.get("gate"), p.get("driver")) for p in pairs}
    for g, d in itertools.product(sorted(gates, key=lambda x: -x.get("stealth", 0)),
                                  sorted(drivers, key=lambda x: -x.get("stealth", 0))):
        if (g["name"], d["name"]) not in have:
            pairs.append({"gate": g["name"], "driver": d["name"], "proposed_tool_name": None})
            have.add((g["name"], d["name"]))
    pairs = pairs[:BUDGET]
    open(LIN, "w").close(); arch = {}
    for i, pair in enumerate(pairs):
        cand = R9.instantiate(pair, gates, drivers)
        if not cand:
            print("[%d] instantiate FAIL %s x %s" % (i, pair.get("gate"), pair.get("driver")), flush=True); continue
        try:
            e = V8.evaluate(cand, 0, i)
        except Exception as ex:
            print("[%d] eval crash %s: %s" % (i, cand.get("name"), str(ex)[:120]), flush=True); continue
        if not e:
            print("[%d] eval None %s" % (i, cand.get("name")), flush=True); continue
        sc = V8.score(e); corner = V8.is_corner(e)
        row = {"pair": {"gate": pair.get("gate"), "driver": pair.get("driver")}, "score": sc, "is_corner": corner,
               **{k: e[k] for k in ("connor", "static", "prompt_stealth", "audit_calls", "audit_fid",
                                    "prod_calls", "prod_fid", "amp")}, "spec": e["spec"], "prompt": e["prompt"]}
        open(LIN, "a").write(json.dumps(row) + "\n"); arch[cand["name"]] = row
        json.dump(list(arch.values()), open(ARCH, "w"), indent=1)
        print("[%d] %-30s (%s x %s) audit=%d(f%s) prod=%d(f%s) amp=%.1f static=%.2f prompt=%.2f connor=%.1f score=%.3f %s" % (
            i, e["spec"]["name"][:30], pair.get("gate", "?")[:16], pair.get("driver", "?")[:16],
            e["audit_calls"], e["audit_fid"], e["prod_calls"], e["prod_fid"], e["amp"], e["static"],
            e["prompt_stealth"], e["connor"], sc, "CORNER" if corner else ""), flush=True)
    print("done; evals=%d corners=%d/%d" % (len(arch), sum(1 for r in arch.values() if r["is_corner"]), len(arch)), flush=True)


if __name__ == "__main__":
    main()
