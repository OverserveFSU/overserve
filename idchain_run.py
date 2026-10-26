# PROVENANCE: hand-specified experimental control + measurement harness for the interf2-idchain
# mechanism test. Task stimuli from idchain_tasks (labeled control variables); D_FP oracle and
# metrics are mechanical. No result is hand-authored.
"""interf2-idchain 3-condition harness: run each condition through the victim, reconstruct the
fixed-point-distance trajectory D_FP(s_t) via idchain_oracle, and log the mechanism metrics.

Central question: can prompt-induced action uncertainty make an EXISTING fixed point behaviorally
hard to reach?  A converges (D_FP->0), B (fixed point removed) recurs, C tests whether ambiguous
wording pushes D_FP toward the B-like non-converging trajectory while the fixed point still exists.
"""
import os, sys, json, glob, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idchain_tasks, idchain_oracle
import task_synth as TS

EOG = TS.EOG
PY = f"{EOG}/.venv/bin/python"
LLM_EP = os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1")
OUT = os.path.abspath("idchain_runs")
CAP = int(os.environ.get("IDC_CAP", "40"))
LOG = "idchain_results.jsonl"
STOP_CLASSES = ["goal-achieved", "detected-stagnation", "declared-infeasible", "escalated",
                "refused-contradiction", "hit-limit", "other"]


def run_victim(condition, tag):
    return run_prompt(idchain_tasks.full_prompt(condition), tag,
                      remove=idchain_tasks.removed_tool(condition))


def run_prompt(prompt, tag, remove=None):
    """Run the victim on an ARBITRARY prompt. remove=None => all 70 tools (the search always
    keeps full tools; integrity is enforced by the scorer, never by withholding here)."""
    task = json.load(open(TS.ALLTOOLS))
    task["user_prompt"] = prompt
    tools = TS.all_seventy()
    if remove:
        tools = [t for t in tools if t != remove]
    task["selected_tools"] = tools
    task["restricted_tools"] = []
    task["verifiers"] = [{"verifier_type": "database_state", "name": "noop", "description": "x",
                          "gym_name": "gym-teams-mcp",
                          "validation_config": {"query": "SELECT 1 AS count;", "expected_value": "1",
                                                "comparison_type": "equals"}}]
    task["number_of_runs"] = 1
    d = os.path.join(OUT, tag); shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="idc_")
    json.dump(task, open(os.path.join(tmp, "t.json"), "w"))
    cfg = json.load(open(f"{EOG}/conf/llm/qwen35.json")); cfg["llm_api_endpoint"] = LLM_EP; cfg["max_tokens"] = 8192
    lp = os.path.join(d, "_llm.json"); json.dump(cfg, open(lp, "w"))
    env = dict(os.environ, EOG_MAX_ITERS=str(CAP))
    if remove:
        env["EOG_ENFORCE_TOOL_FILTER"] = "1"                          # truly unroutable
    subprocess.run([PY, "evaluate.py", "--configs_folder", tmp, "--llm_config", lp,
                    "--output_folder", d, "--orchestrator", "react", "--concurrency", "1", "--num_runs", "1"],
                   cwd=EOG, env=env, stdout=open(os.path.join(d, "_log"), "w"), stderr=subprocess.STDOUT)
    shutil.rmtree(tmp, ignore_errors=True)
    fs = glob.glob(os.path.join(d, "run_*", "*.json"))
    if not fs:
        return None
    r = (json.load(open(fs[0])).get("runs") or [{}])[0]
    trs = r.get("tool_results") or []
    ai = [m for m in r.get("conversation_flow", []) if m.get("type") == "ai_message"]
    final = (r.get("model_response") or "")
    lr = ""
    for m in reversed(ai):
        if (m.get("reasoning") or m.get("content") or "").strip():
            lr = (m.get("reasoning") or m.get("content")).strip(); break
    return {"tool_results": trs, "seq": [t["tool_name"] for t in trs], "turns": len(ai),
            "hit_cap": len(ai) >= CAP, "final_response": final[:500], "last_reasoning": lr[:500]}


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
    seeds = int(os.environ.get("IDC_SEEDS", "3"))
    os.makedirs(OUT, exist_ok=True)
    done = done_labels()
    grid = [(c, s) for c in idchain_tasks.CONDITIONS for s in range(seeds)]
    print("idchain grid: %d cells, %d done" % (len(grid), len(done)), flush=True)
    for cond, s in grid:
        label = "%s__s%d" % (cond, s)
        if label in done:
            continue
        rec = run_victim(cond, label)
        if not rec:
            print("[%s] FAILED" % label, flush=True); continue
        oc = idchain_oracle.reconstruct(rec["tool_results"])
        seq = rec["seq"]
        # send<->update alternation (the post->update->post loop signature)
        alt = sum(1 for i in range(2, len(seq))
                  if seq[i] == seq[i - 2] and seq[i] != seq[i - 1]
                  and seq[i] in ("send_channel_message", "update_channel"))
        summ = {"reached_fixed_point": oc["reached_fixed_point"], "D_FP_final": oc["D_FP_final"],
                "total_calls": len(seq), "hit_cap": rec["hit_cap"], "last_5": seq[-5:]}
        sr = judge_stop(rec, summ)
        row = {"label": label, "condition": cond, "seed": s, "turns": rec["turns"],
               "hit_cap": rec["hit_cap"], "total_calls": len(seq),
               "reached_fixed_point": oc["reached_fixed_point"], "first_fp_step": oc["first_fp_step"],
               "D_FP_final": oc["D_FP_final"], "D_FP_series": oc["D_FP_series"],
               "send_update_alt": alt, "stop_reason": sr.get("stop_reason"), "seq": seq}
        open(LOG, "a").write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[%s] calls=%d reached_FP=%s first_fp=%s D_FP_final=%d alt=%d cap=%s stop=%s"
              % (label, len(seq), oc["reached_fixed_point"], oc["first_fp_step"], oc["D_FP_final"],
                 alt, rec["hit_cap"], sr.get("stop_reason")), flush=True)
    print("=== IDCHAIN GRID COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
