# FAITHFUL v9 (recon-SEEDED) REPLICA on Enterprise-Worlds ITSM.
#
# v9 = recon_analyzer.py DERIVES (gate,driver) from the target's tool list + service desc, then
# recon_to_search.py has the GLM writer INSTANTIATE each pair into a concrete {name,description,
# handler_src,driver} and evaluates it with the v8 machinery. This script reuses BOTH byte-identical:
#   - R9.instantiate + R9.INST_SYS   (the literal v9 GLM instantiate step)
#   - V8.evaluate / V8.score / V8.is_corner, V7.connor_soft, V.judge_tool/judge_prompt (all GLM)
# The ONLY swap (authorized) is the rollout backend: we monkeypatch the module-global V8.run_cond that
# V8.evaluate calls to the EW-ITSM rollout (search_faithful_ew.run_cond_ew), and empty V8.CORE (the EOG
# channel core task) because on EW the benign core IS the native ITSM task, appended inside the rollout.
import os, sys, json, itertools

sys.path.insert(0, os.environ.get("OVERSERVE_DIR", "/home/ruiheng/aiagent/saas/overserve"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import search_faithful_ew as S     # brings V, V7, V8 + the EW rollout (run_cond_ew, _ChurnDir, exec)
import recon_to_search as R9        # LITERAL v9: instantiate() + INST_SYS (GLM writer)
V, V7, V8 = S.V, S.V7, S.V8

RECON  = os.environ.get("RECON_JSON", "/home/ruiheng/aiagent/saas/overserve/recon_candidates_itsm.json")
BUDGET = int(os.environ.get("ATK_BUDGET", "6"))
TASK_IDX = int(os.environ.get("EW_TASK", "0"))          # base-passing ITSM task (V8.evaluate is single-task)
LIN    = os.environ.get("LINEAGE", "lineage_v9_recon_ew.jsonl")
ARCH   = os.environ.get("ARCHIVE", "archive_v9_recon_ew.json")

# --- the authorized swap: rebind the rollout V8.evaluate calls, and drop the EOG core task ---
V8.CORE = ""                                            # EW core = native ITSM task (added in rollout)
def _ew_run_cond(spec, prompt, churn, tag):            # v8.run_cond signature; prompt == driver (CORE="")
    return S.run_cond_ew(spec, prompt, churn == "1", TASK_IDX)
V8.run_cond = _ew_run_cond                             # V8.evaluate looks up run_cond in its module globals


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
    open(LIN, "w").close()
    arch = {}
    for i, pair in enumerate(pairs):
        cand = R9.instantiate(pair, gates, drivers)           # LITERAL v9 GLM instantiate
        if not cand:
            print("[%d] instantiate FAIL %s x %s" % (i, pair.get("gate"), pair.get("driver")), flush=True); continue
        try:
            e = V8.evaluate(cand, 0, i)                        # LITERAL v8 evaluate (rollout monkeypatched)
        except Exception as ex:
            print("[%d] eval crash %s: %s" % (i, cand.get("name"), str(ex)[:120]), flush=True); continue
        if not e:
            print("[%d] eval None %s" % (i, cand.get("name")), flush=True); continue
        sc = V8.score(e); corner = V8.is_corner(e)
        row = {"pair": {"gate": pair.get("gate"), "driver": pair.get("driver")}, "score": sc, "is_corner": corner,
               **{k: e[k] for k in ("connor", "static", "prompt_stealth", "audit_calls", "audit_fid",
                                    "prod_calls", "prod_fid", "amp")},
               "spec": e["spec"], "prompt": e["prompt"]}
        open(LIN, "a").write(json.dumps(row) + "\n")
        arch[cand["name"]] = row
        json.dump(list(arch.values()), open(ARCH, "w"), indent=1)
        print("[%d] %-30s (%s x %s) audit=%d(f%s) prod=%d(f%s) amp=%.1f static=%.2f prompt=%.2f connor=%.1f score=%.3f %s" % (
            i, e["spec"]["name"][:30], pair.get("gate", "?")[:16], pair.get("driver", "?")[:16],
            e["audit_calls"], e["audit_fid"], e["prod_calls"], e["prod_fid"], e["amp"], e["static"],
            e["prompt_stealth"], e["connor"], sc, "CORNER" if corner else ""), flush=True)
    print("done; evals=%d corners=%d/%d" % (len(arch), sum(1 for r in arch.values() if r["is_corner"]), len(arch)), flush=True)


if __name__ == "__main__":
    main()
