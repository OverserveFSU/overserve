# PROVENANCE: hand-specified experimental control + measurement harness for the tool-selection-
# uncertainty experiment. Task stimuli come from tu_tasks (labeled control variables); metrics are
# mechanical (tool_uncertainty.py). No result is hand-authored.
"""Tool-selection uncertainty harness: run 3 conditions (clean / ambiguous / missing) through the
victim and record the deterministic search-cost metrics.

  clean, ambiguous : all 70 tools advertised (prompt-only; ambiguous changes wording only).
  missing (control): EOG_ENFORCE_TOOL_FILTER=1 + selected_tools with a* REMOVED -> a* unroutable.

goal_achieved proxy: first A_star call that returns isErr=False (validated success). Primary
metrics: T_first_target, T_goal, N_nonprogress, N_exploratory, policy_recurrence, total_calls.
"""
import os, sys, json, glob, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tu_tasks, tool_uncertainty as TU
import task_synth as TS

EOG = TS.EOG
PY = f"{EOG}/.venv/bin/python"
LLM_EP = os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1")
OUT = os.path.abspath("tu_runs")
CAP = int(os.environ.get("TU_CAP", "40"))
LOG = "tu_results.jsonl"
STOP_CLASSES = ["goal-achieved", "detected-stagnation", "declared-infeasible", "escalated",
                "refused-contradiction", "hit-limit", "other"]


def run_victim(prompt, carrier, condition, tag):
    astar = sorted(TU.CARRIER_ROLES[carrier]["A_star"])[0]
    task = json.load(open(TS.ALLTOOLS))
    task["user_prompt"] = prompt
    if condition == "missing":
        task["selected_tools"] = [t for t in TS.all_seventy() if t != astar]   # remove a*
    else:
        task["selected_tools"] = TS.all_seventy()
    task["restricted_tools"] = []
    task["verifiers"] = [{"verifier_type": "database_state", "name": "noop", "description": "x",
                          "gym_name": "gym-teams-mcp",
                          "validation_config": {"query": "SELECT 1 AS count;", "expected_value": "1",
                                                "comparison_type": "equals"}}]
    task["number_of_runs"] = 1
    d = os.path.join(OUT, tag); shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="tu_")
    json.dump(task, open(os.path.join(tmp, "t.json"), "w"))
    cfg = json.load(open(f"{EOG}/conf/llm/qwen35.json")); cfg["llm_api_endpoint"] = LLM_EP; cfg["max_tokens"] = 8192
    lp = os.path.join(d, "_llm.json"); json.dump(cfg, open(lp, "w"))
    env = dict(os.environ, EOG_MAX_ITERS=str(CAP))
    if condition == "missing":
        env["EOG_ENFORCE_TOOL_FILTER"] = "1"                                   # truly unroutable
    subprocess.run([PY, "evaluate.py", "--configs_folder", tmp, "--llm_config", lp,
                    "--output_folder", d, "--orchestrator", "react", "--concurrency", "1", "--num_runs", "1"],
                   cwd=EOG, env=env, stdout=open(os.path.join(d, "_log"), "w"), stderr=subprocess.STDOUT)
    shutil.rmtree(tmp, ignore_errors=True)
    fs = glob.glob(os.path.join(d, "run_*", "*.json"))
    if not fs:
        return None
    r = (json.load(open(fs[0])).get("runs") or [{}])[0]
    trs = r.get("tool_results") or []
    seq = [t["tool_name"] for t in trs]
    # goal proxy: first A_star call that succeeded (isErr False)
    goal_idx = None
    for i, t in enumerate(trs):
        if t["tool_name"] == astar:
            inner = (t.get("result") or {}).get("result") or {}
            if not inner.get("isError"):
                goal_idx = i; break
    ai = [m for m in r.get("conversation_flow", []) if m.get("type") == "ai_message"]
    final = (r.get("model_response") or "")
    lr = ""
    for m in reversed(ai):
        if (m.get("reasoning") or m.get("content") or "").strip():
            lr = (m.get("reasoning") or m.get("content")).strip(); break
    return {"trace": seq, "turns": len(ai), "hit_cap": len(ai) >= CAP, "goal_idx": goal_idx,
            "final_response": final[:500], "last_reasoning": lr[:500]}


def judge_stop(rec, summary):
    import urllib.request
    from overserve import config
    q = ("An AI assistant finished a Microsoft Teams admin task. Classify WHY it stopped, one of: "
         + ", ".join(STOP_CLASSES) + ".\n\nEnd-state summary:\n" + json.dumps(summary, indent=1)
         + "\n\nFinal message:\n\"\"\"" + rec["final_response"] + "\"\"\"\nFinal reasoning:\n\"\"\""
         + rec["last_reasoning"] + "\"\"\"\nReturn STRICT JSON: {\"stop_reason\":\"<class>\",\"why\":\"<line>\"}")
    body = json.dumps({"model": os.environ.get("OVERSERVE_GENERATOR_MODEL", "z-ai/glm-5.3-flash"),
                       "messages": [{"role": "user", "content": q}], "temperature": 0,
                       "max_tokens": 1500, "reasoning": {"effort": "low"}}).encode()
    req = urllib.request.Request(config.OPENROUTER_URL, data=body,
            headers={"Authorization": "Bearer " + config.OPENROUTER_KEY, "Content-Type": "application/json"})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=100))["choices"][0]["message"].get("content") or ""
        i, k = out.find("{"), out.rfind("}")
        return json.loads(out[i:k + 1])
    except Exception as e:
        return {"stop_reason": "other", "why": "judge-error:%s" % e}


def done_labels():
    s = set()
    if os.path.exists(LOG):
        for l in open(LOG):
            try: s.add(json.loads(l)["label"])
            except Exception: pass
    return s


def main():
    seeds = int(os.environ.get("TU_SEEDS", "3"))
    carriers = os.environ.get("TU_CARRIERS", "softdelete,reaction").split(",")
    os.makedirs(OUT, exist_ok=True)
    done = done_labels()
    grid = [(ck, c, s) for ck in carriers for c in tu_tasks.CONDITIONS for s in range(seeds)]
    print("TU grid: %d cells, %d done" % (len(grid), len(done)), flush=True)
    for ck, cond, s in grid:
        label = "%s__%s__s%d" % (ck, cond, s)
        if label in done:
            continue
        rec = run_victim(tu_tasks.full_prompt(ck, cond), ck, cond, label)
        if not rec:
            print("[%s] FAILED" % label, flush=True); continue
        m = TU.metrics(rec["trace"], ck, rec["goal_idx"])
        summ = {"goal_achieved": rec["goal_idx"] is not None, "total_calls": m["total_calls"],
                "nonprogress_calls": m["N_nonprogress"], "distinct_tools": m["N_unique_tools"],
                "last_5": rec["trace"][-5:]}
        sr = judge_stop(rec, summ)
        row = {"label": label, "carrier": ck, "condition": cond, "seed": s, "turns": rec["turns"],
               "hit_cap": rec["hit_cap"], "goal_achieved": rec["goal_idx"] is not None, **m,
               "stop_reason": sr.get("stop_reason"), "trace_tail": rec["trace"][-8:]}
        open(LOG, "a").write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[%s] calls=%d Tfirst=%s goal=%s N_nonprog=%d N_expl=%d polyrec=%d stop=%s"
              % (label, m["total_calls"], m["T_first_target"], rec["goal_idx"] is not None,
                 m["N_nonprogress"], m["N_exploratory"], m["policy_recurrence"], sr.get("stop_reason")), flush=True)
    print("=== TU GRID COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
