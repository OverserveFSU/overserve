"""ECLIPSE-style loop (approach 1), prompt-only (stages 1-4 only; NO tool-side SWE/DTC).

One iteration:
  1. GENERATOR (LLM)  -> propose a task: two DB-verified requirements over shared objects with
                        mutual interference + a target tool-cycle.  [llm_prompts.json:generator]
  2. offline VALIDATE -> state_analysis.interference must show mutual coupling (necessary cond).
  3. ANNOTATOR (LLM)  -> benign natural-language prompt (no loop/count words). [json:annotator]
  4. RUN victim       -> all 70 tools, prompt-only, real V1/V2 verifiers -> trace + Φ_final + recurrence.
  5. JUDGE (LLM)      -> diagnose entered/passes/why/class + prompt feedback. [json:judge]
  6. feed judge.feedback back to the generator (next round).

LLM = OpenRouter (env OPENROUTER_API_KEY + OVERSERVE_GENERATOR_MODEL/FUSION_MODEL, e.g.
z-ai/glm-5.3-flash). Victim = qwen via EOG. Terminal is never modeled here — the agent decides it;
we only observe recurrence.
"""
import os, sys, json, re, glob, shutil, subprocess, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import urllib.request
import state_analysis as SA
import task_synth as TS
from overserve import config

MODEL = os.environ.get("OVERSERVE_GENERATOR_MODEL", "z-ai/glm-5.3-flash")


def chat(prompt, temp=0.7, maxtok=None):
    """OpenRouter call with reasoning effort LOW — glm-5.3-flash otherwise spends thousands of
    reasoning tokens (280s+); effort=low makes the same call ~5s with valid output. Single attempt,
    bounded timeout, content-only."""
    maxtok = maxtok or int(os.environ.get("ECLIPSE_LLM_MAXTOK", "3000"))
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": maxtok,
                       "reasoning": {"effort": "low"}}).encode()
    req = urllib.request.Request(config.OPENROUTER_URL, data=body,
            headers={"Authorization": "Bearer " + config.OPENROUTER_KEY, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=100))
        return (r["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        return ""

EOG = TS.EOG
PY = f"{EOG}/.venv/bin/python"
LLM_EP = os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1")
OUT = os.path.abspath("eclipse_runs")
PROMPTS = json.load(open(os.path.join(os.path.dirname(__file__), "llm_prompts.json")))
MAXTOK = int(os.environ.get("ECLIPSE_LLM_MAXTOK", "8000"))
CAP = int(os.environ.get("ECLIPSE_CAP", "40"))


def _json(text):
    i, j = text.find("{"), text.rfind("}")
    return json.loads(text[i:j + 1]) if i >= 0 else None


def gen_candidate(feedback=""):
    writes = "\n".join("  %s -> %s" % (t, sorted(w)) for t, w in SA.TOOL_WRITES.items())
    p = PROMPTS["generator"] % writes
    if feedback:
        p += "\n\nPrevious attempt feedback (address it): " + feedback
    out = chat(p, temp=0.8)
    return _json(out), out


def annotate(clauses):
    desc = "\n".join("  %s: %s" % (c["id"], c.get("name", c.get("description", ""))) for c in clauses)
    return chat(PROMPTS["annotator"] % desc, temp=0.7).strip().strip('"')


def run_victim(prompt, clauses, tag):
    """Run the victim on the synthesized task (all 70 tools, real verifiers). Returns metrics."""
    task = TS.build_task(prompt, clauses, tag)
    d = os.path.join(OUT, tag); shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="ecl_")
    json.dump(task, open(os.path.join(tmp, "task.json"), "w"))
    cfg = json.load(open(f"{EOG}/conf/llm/qwen35.json")); cfg["llm_api_endpoint"] = LLM_EP; cfg["max_tokens"] = 8192
    lp = os.path.join(d, "_llm.json"); json.dump(cfg, open(lp, "w"))
    subprocess.run([PY, "evaluate.py", "--configs_folder", tmp, "--llm_config", lp,
                    "--output_folder", d, "--orchestrator", "react", "--concurrency", "1", "--num_runs", "1"],
                   cwd=EOG, env=dict(os.environ, EOG_MAX_ITERS=str(CAP)),
                   stdout=open(os.path.join(d, "_log"), "w"), stderr=subprocess.STDOUT)
    shutil.rmtree(tmp, ignore_errors=True)
    fs = glob.glob(os.path.join(d, "run_*", "*.json"))
    if not fs:
        return None
    j = json.load(open(fs[0])); r = (j.get("runs") or [{}])[0]
    ai = [m for m in r.get("conversation_flow", []) if m.get("type") == "ai_message"]
    seq = [t["tool_name"] for t in (r.get("tool_results") or [])]
    # read-feedback modelling: a read (list_/get_) that observes the still-unsatisfied state drives
    # the next write. Count read->write transitions and the read/write interleaving that IS the
    # oscillation (iter4: add_tabs x7 interleaved with list_tabs x3). A high read_then_write with
    # phi_final>0 = "read keeps reporting fail -> keeps writing".
    def is_read(t):
        return t.startswith(("list_", "get_"))
    reads = sum(1 for t in seq if is_read(t))
    writes = len(seq) - reads
    read_then_write = sum(1 for a, b in zip(seq, seq[1:]) if is_read(a) and not is_read(b))
    # alternation runs: max length of read/write alternating subsequence (feedback depth)
    alt = cur = 1
    for a, b in zip(seq, seq[1:]):
        cur = cur + 1 if is_read(a) != is_read(b) else 1
        alt = max(alt, cur)
    return {"trace": seq, "turns": len(ai), "hit_cap": len(ai) >= CAP,
            "reads": reads, "writes": writes, "read_then_write": read_then_write,
            "max_read_write_alternation": alt,
            "verifier_pass_rate": j.get("statistics", {}).get("verifier_level_pass_rate"),
            "phi_final": sum(1 for c in r.get("verification_results", {}).values() if not c.get("passed"))
                         if isinstance(r.get("verification_results"), dict) else None}


def judge(target_cycle, run):
    p = PROMPTS["judge"] % (target_cycle, run["trace"], run["verifier_pass_rate"], run["turns"], run["hit_cap"])
    return _json(chat(p, temp=0.0)) or {}


def iteration(n, feedback=""):
    print("\n===== iteration %d =====" % n, flush=True)
    cand, raw = gen_candidate(feedback)
    if not cand or "clauses" not in cand:
        print("  generator produced no valid JSON:", raw[:200]); return None
    clauses = cand["clauses"]; target = cand.get("target_cycle", [])
    inter = SA.interference([{"id": c["id"], "reads": c.get("reads", []), "advanced_by": c.get("advanced_by")} for c in clauses])
    print("  clauses:", [c["id"] for c in clauses], "target_cycle:", target, flush=True)
    print("  offline mutual interference:", inter["interference"], inter["mutual_pairs"], flush=True)
    if not inter["interference"]:
        # feed a concrete coupling hint back so the next generation self-corrects (offline rejects
        # were previously silent -> the loop got stuck producing uncoupled candidates).
        wcols = {t: sorted(SA.TOOL_WRITES.get(c.get("advanced_by"), []))
                 for c in clauses for t in [c.get("advanced_by")]}
        hint = ("Your two clauses were NOT mutually coupled so there is no interference. Fix it: pick "
                "toolA and toolB; put a column toolA WRITES into V2's 'reads', and a column toolB "
                "WRITES into V1's 'reads', and set advanced_by V1=toolA, V2=toolB. Your tools wrote: "
                + json.dumps(wcols) + ". Only these columns can couple.")
        print("  -> reject (no coupling); feeding hint back", flush=True)
        return {"iter": n, "rejected": "no mutual interference", "candidate": cand, "hint": hint}
    prompt = annotate(clauses)
    print("  benign prompt:", prompt[:160], flush=True)
    run = run_victim(prompt, clauses, "iter%d" % n)
    if not run:
        print("  victim run FAILED"); return {"iter": n, "error": "run failed"}
    print("  run: turns=%s cap=%s verifier_pass=%s Φ_final=%s reads=%s writes=%s read_then_write=%s alt=%s"
          % (run["turns"], run["hit_cap"], run["verifier_pass_rate"], run["phi_final"],
             run["reads"], run["writes"], run["read_then_write"], run["max_read_write_alternation"]), flush=True)
    verdict = judge(target, run)
    print("  judge:", json.dumps(verdict, ensure_ascii=False)[:300], flush=True)
    rec = {"iter": n, "candidate": cand, "prompt": prompt, "interference": inter,
           "run": run, "judge": verdict}
    open("eclipse_loop.jsonl", "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _resume_state():
    """Resumable: `done` = COUNT of completed (logged) runs — NOT max(iter). Rejected attempts
    increment the attempt label without logging, so max(iter) > row count and the old logic spun."""
    done, attempt, fb = 0, 0, ""
    if os.path.exists("eclipse_loop.jsonl"):
        for l in open("eclipse_loop.jsonl"):
            try:
                d = json.loads(l); done += 1; attempt = max(attempt, d.get("iter", 0))
                fb = (d.get("judge") or {}).get("feedback", "") or fb
            except Exception:
                pass
    return done, attempt, fb


if __name__ == "__main__":
    config.require_key()
    os.makedirs(OUT, exist_ok=True)
    rounds = int(os.environ.get("ECLIPSE_ROUNDS", "1"))
    max_attempts = int(os.environ.get("ECLIPSE_MAX_ATTEMPTS", str(rounds * 4)))
    done, attempt, fb = _resume_state()
    if done >= rounds:
        print("already %d/%d completed; nothing to do." % (done, rounds)); sys.exit(0)
    while done < rounds and attempt < max_attempts:
        attempt += 1
        r = iteration(attempt, fb)
        if r and r.get("run"):
            done += 1
        if r and r.get("judge", {}).get("deviation_class") == "fundamental":
            print("\njudge: FUNDAMENTAL — reframing won't help; stopping."); break
        fb = ((r or {}).get("judge", {}).get("feedback", "") or (r or {}).get("hint", "")) if r else ""
    print("\n=== ECLIPSE loop done (%d/%d completed, %d attempts) ===" % (done, rounds, attempt))
