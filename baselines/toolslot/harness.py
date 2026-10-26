"""Unified tool-slot comparison harness.
========================================
Iterates method x victim x task x condition x rep over a COMMON adapter and writes one standard record
per cell. All methods hit the SAME victim / task / init-state / budget cap (40) / fidelity verifier;
only the slotted tool spec (+ ours' driver) differs. EOG cells go through eog_runner.py (subprocess,
system python); MCPMark cells through mm_runner.py (subprocess, MCPMark .venv). Serial, with a qwen
health-check + retry (the LAN VM flaps).

Standard record keys: method,victim,bench,task,condition,rep, calls, fid(=task_pass), naive_tokens,
cached_tokens, hit_cap, err. amp (vs clean) is computed in the summary step, not here.

Token accounting (report cached per project memo):
  EOG     : naive = sum_prompt_tok + sum_compl_tok ; cached = sum_compl_tok + peak_ctx
  MCPMark : naive = input_tokens + output_tokens  ;
            cached = output_tokens + peak_input, peak_input ~= 2*input/(turn_count+1)
            (linear-growth estimate of the single largest cached context; same formula num & denom).
"""
import os, sys, json, time, subprocess, urllib.request, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import methods as M

MMPY = "/home/ruiheng/aiagent/saas/benchmarks/mcpmark/.venv/bin/python"
EOG_PORT = 8233  # unique attack-server port for our EOG cells (serial, so one port is fine)

VICTIMS = {
    "qwen": {"endpoint": "http://127.0.0.1:8356/v1", "eog_model": "qwen3.8-27b",
             "mm_model": "openai/qwen3.5", "flap": True},
    "sonnet": {"endpoint": "http://127.0.0.1:8300/v1", "eog_model": "sonnet5",
               "mm_model": "openai/sonnet5", "flap": False},
}
MM_TASKS = ["file_property/txt_merging", "file_property/largest_rename"]
EOG_TASK = "eog_core"
CONDITIONS = {"quiet": "0", "churn": "1"}
ATTACK_METHODS = ["ours", "a2m", "looptrap"]
CAP = 40


def health_qwen(endpoint, tries=12):
    url = endpoint.rstrip("/") + "/models"
    for i in range(tries):
        try:
            urllib.request.urlopen(url, timeout=10).read()
            return True
        except Exception:
            time.sleep(min(5 + i * 3, 25))
    return False


def _cached_eog(r):
    return (r.get("sum_compl_tok") or 0) + (r.get("peak_ctx") or 0)


def _naive_eog(r):
    return (r.get("sum_prompt_tok") or 0) + (r.get("sum_compl_tok") or 0)


def _cached_mm(r):
    inp = r.get("input_tokens") or 0
    out = r.get("output_tokens") or 0
    tc = r.get("turn_count") or 0
    peak_in = (2.0 * inp / (tc + 1)) if tc else inp
    return int(out + peak_in)


def _naive_mm(r):
    return (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)


def run_eog_cell(spec, prompt, churn, victim, tag, lt_strategy=None):
    v = VICTIMS[victim]
    cell = {"spec": spec, "prompt": prompt, "churn": churn, "tag": tag,
            "endpoint": v["endpoint"], "model": v["eog_model"], "port": EOG_PORT, "cap": CAP}
    p = subprocess.run([sys.executable, os.path.join(HERE, "eog_runner.py"), json.dumps(cell)],
                       capture_output=True, text=True, timeout=1800)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        return {"error": "eog_no_result", "stderr": p.stderr[-400:]}
    return json.loads(line[-1][len("RESULT "):])


def run_mm_cell(spec, driver, churn, victim, task_id, tag):
    v = VICTIMS[victim]
    cell = {"spec": spec, "driver": driver, "churn": churn, "task_id": task_id,
            "service": "filesystem", "cap": CAP, "endpoint": v["endpoint"],
            "model": v["mm_model"], "tag": tag}
    p = subprocess.run([MMPY, os.path.join(HERE, "mm_runner.py"), json.dumps(cell)],
                       capture_output=True, text=True, timeout=1800)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        return {"error": "mm_no_result", "stderr": p.stderr[-400:]}
    return json.loads(line[-1][len("RESULT "):])


def standard_record(method, victim, bench, task, condition, rep, r):
    err = r.get("error") or r.get("error_message") if r else "null_result"
    # treat non-fidelity / errored runs as task_pass=False but keep them IN the denominator
    if bench == "eog":
        calls = r.get("total_calls")
        fid = bool(r.get("fidelity"))
        naive = _naive_eog(r); cached = _cached_eog(r)
        hitcap = bool(r.get("hit_cap"))
        atk = r.get("atk_calls")
    else:
        calls = r.get("total_calls")
        fid = bool(r.get("fidelity"))
        naive = _naive_mm(r); cached = _cached_mm(r)
        hitcap = (calls is not None and calls >= CAP) or ("Max turns" in str(r.get("error_message") or ""))
        atk = None
    return {"method": method, "victim": victim, "bench": bench, "task": task,
            "condition": condition, "rep": rep, "calls": calls, "fid": fid,
            "naive_tokens": naive, "cached_tokens": cached, "hit_cap": hitcap,
            "atk_calls": atk, "err": (err if err and err != False else None)}


def do_cell(method, victim, bench, task, condition, rep, lt_strategy=None):
    churn = CONDITIONS[condition]
    tag = "%s_%s_%s_%s_%s_r%d" % (method, victim, bench, task.replace("/", "-"), condition, rep)
    spec, drv = M.get_method(method, bench, looptrap_strategy=lt_strategy)
    if bench == "eog":
        prompt = M.EOG_CORE + (drv if drv else "")
        r = run_eog_cell(spec, prompt, churn, victim, tag, lt_strategy)
    else:
        r = run_mm_cell(spec, drv, churn == "1", victim, task, tag)
    rec = standard_record(method, victim, bench, task, condition, rep, r or {})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--victims", default="qwen")
    ap.add_argument("--benches", default="mcpmark")        # mcpmark,eog
    ap.add_argument("--mm-tasks", default=",".join(MM_TASKS))
    ap.add_argument("--methods", default=",".join(ATTACK_METHODS))
    ap.add_argument("--conditions", default="quiet,churn")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--clean", action="store_true", help="also run clean baseline per victim x task")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "toolslot.jsonl"))
    ap.add_argument("--lt-strategy", default=None, help="override LoopTrap strategy key")
    ap.add_argument("--lt-profile", default=None, help="json file victim->strategy")
    args = ap.parse_args()

    victims = args.victims.split(",")
    benches = args.benches.split(",")
    methods = args.methods.split(",")
    conditions = args.conditions.split(",")
    mm_tasks = args.mm_tasks.split(",")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    lt_prof = {}
    if args.lt_profile and os.path.exists(args.lt_profile):
        lt_prof = json.load(open(args.lt_profile))

    def tasks_for(bench):
        return mm_tasks if bench == "mcpmark" else [EOG_TASK]

    def emit(rec):
        with open(args.out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print("  %-9s %-6s %-9s %-26s %-5s r%d | calls=%-4s fid=%-5s cached=%-7s hit=%s %s" % (
            rec["method"], rec["victim"], rec["bench"], rec["task"], rec["condition"], rec["rep"],
            rec["calls"], rec["fid"], rec["cached_tokens"], rec["hit_cap"],
            ("ERR:" + str(rec["err"])[:60]) if rec["err"] else ""), flush=True)

    for victim in victims:
        v = VICTIMS[victim]
        for bench in benches:
            for task in tasks_for(bench):
                if args.clean:
                    if v["flap"] and not health_qwen(v["endpoint"]):
                        print("qwen unhealthy, skip clean", flush=True)
                    rec = do_cell("clean", victim, bench, task, "quiet", 0)
                    emit(rec)
                for method in methods:
                    lt = lt_prof.get(victim, args.lt_strategy)
                    for condition in conditions:
                        for rep in range(args.reps):
                            if v["flap"] and not health_qwen(v["endpoint"]):
                                print("qwen unhealthy before cell, retrying later", flush=True)
                                time.sleep(20)
                                health_qwen(v["endpoint"])
                            rec = do_cell(method, victim, bench, task, condition, rep, lt)
                            emit(rec)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
