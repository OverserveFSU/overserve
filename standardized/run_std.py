"""Standardized OverServe main-table runner (CAP_PROTOCOL.md).
Reuses the frozen toolslot 'ours' churn method + the isolated eog_runner.py / mm_runner.py cell
subprocesses, but parametrizes the budget cap per the two-cap protocol and emits one D5-schema row per
rollout to STANDARDIZED_RESULTS.jsonl.

D5 row: {cap, cap_role, clean_baseline_calls, calls, amp, hit_cap, self_term, fidelity, victim,
         dataset, task, seed, naive_tokens, cached_tokens, method, condition, err}

Covers the toolslot datasets: eog, mcpmark. qwen served SERIALLY (LAN VM flaps; health-check+retry).
"""
import os, sys, json, time, subprocess, urllib.request, argparse

TOOLSLOT = "/home/ruiheng/aiagent/saas/overserve/baselines/toolslot"
sys.path.insert(0, TOOLSLOT)
import methods as M

MMPY = "/home/ruiheng/aiagent/saas/benchmarks/mcpmark/.venv/bin/python"
OUT = "/home/ruiheng/aiagent/saas/overserve_paper/standardized/STANDARDIZED_RESULTS.jsonl"

VICTIMS = {
    "qwen":   {"endpoint": "http://127.0.0.1:8356/v1", "eog_model": "qwen3.8-27b",
               "mm_model": "openai/qwen3.5", "flap": True,  "eog_port": 8234},
    "sonnet": {"endpoint": "http://127.0.0.1:8311/v1", "eog_model": "sonnet5",
               "mm_model": "openai/sonnet5", "flap": False, "eog_port": 8235},
    "deepseek": {"endpoint": "http://127.0.0.1:8357/v1", "eog_model": "deepseek-v4-flash",
                 "mm_model": "openai/deepseek-v4-flash", "flap": True, "eog_port": 8236},
    "nemotron": {"endpoint": "http://127.0.0.1:8359/v1", "eog_model": "nemotron-3-super",
                 "mm_model": "openai/nemotron-3-super", "flap": True, "eog_port": 8237},
}

# per-dataset B_D + two caps (CAP_PROTOCOL.md table)
DATASETS = {
    "eog":     {"B_D": 5, "cap_op": 15, "cap_hr": 100, "tasks": ["eog_core"]},
    "mcpmark": {"B_D": 5, "cap_op": 15, "cap_hr": 100,
                "tasks": ["file_property/txt_merging"]},
}


def health_qwen(endpoint, tries=15):
    url = endpoint.rstrip("/") + "/models"
    for i in range(tries):
        try:
            urllib.request.urlopen(url, timeout=10).read(); return True
        except Exception:
            time.sleep(min(5 + i * 3, 25))
    return False


def _naive_eog(r): return (r.get("sum_prompt_tok") or 0) + (r.get("sum_compl_tok") or 0)
def _cached_eog(r): return (r.get("sum_compl_tok") or 0) + (r.get("peak_ctx") or 0)
def _naive_mm(r): return (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
def _cached_mm(r):
    inp = r.get("input_tokens") or 0; out = r.get("output_tokens") or 0; tc = r.get("turn_count") or 0
    peak_in = (2.0 * inp / (tc + 1)) if tc else inp
    return int(out + peak_in)


def run_eog_cell(spec, prompt, churn, victim, cap, tag):
    v = VICTIMS[victim]
    cell = {"spec": spec, "prompt": prompt, "churn": churn, "tag": tag,
            "endpoint": v["endpoint"], "model": v["eog_model"], "port": v["eog_port"], "cap": cap}
    p = subprocess.run([sys.executable, os.path.join(TOOLSLOT, "eog_runner.py"), json.dumps(cell)],
                       capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        return {"error": "eog_no_result", "stderr": p.stderr[-400:]}
    return json.loads(line[-1][len("RESULT "):])


def run_mm_cell(spec, driver, churn, victim, cap, task_id, tag):
    v = VICTIMS[victim]
    cell = {"spec": spec, "driver": driver, "churn": churn, "task_id": task_id,
            "service": "filesystem", "cap": cap, "endpoint": v["endpoint"],
            "model": v["mm_model"], "tag": tag}
    p = subprocess.run([MMPY, os.path.join(TOOLSLOT, "mm_runner.py"), json.dumps(cell)],
                       capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        return {"error": "mm_no_result", "stderr": p.stderr[-400:]}
    return json.loads(line[-1][len("RESULT "):])


def do_cell(method, victim, dataset, task, churn, cap):
    tag = "%s_%s_%s_%s_c%s_cap%d" % (method, victim, dataset, task.replace("/", "-"), churn, cap)
    spec, drv = M.get_method(method, "eog" if dataset == "eog" else "mcpmark")
    if dataset == "eog":
        prompt = M.EOG_CORE + (drv if drv else "")
        r = run_eog_cell(spec, prompt, churn, victim, cap, tag) or {}
        calls = r.get("total_calls"); fid = bool(r.get("fidelity"))
        naive, cached = _naive_eog(r), _cached_eog(r)
        hitcap = bool(r.get("hit_cap"))
    else:
        r = run_mm_cell(spec, drv, churn == "1", victim, cap, task, tag) or {}
        calls = r.get("total_calls"); fid = bool(r.get("fidelity"))
        naive, cached = _naive_mm(r), _cached_mm(r)
        hitcap = (calls is not None and calls >= cap) or ("Max turns" in str(r.get("error_message") or ""))
    err = r.get("error") or (r.get("error_message") if r.get("error_message") else None)
    return {"calls": calls, "fid": fid, "naive": naive, "cached": cached, "hitcap": hitcap, "err": err}


def emit(row):
    with open(OUT, "a") as f:
        f.write(json.dumps(row) + "\n")
    print("  %-7s %-8s %-7s %-22s cap=%-4s(%s) r%d | calls=%-4s amp=%-5s fid=%-5s hit=%-5s self=%-5s %s" % (
        row["victim"], row["dataset"], row["method"], row["task"], row["cap"], row["cap_role"], row["seed"],
        row["calls"], row.get("amp"), row["fidelity"], row["hit_cap"], row["self_term"],
        ("ERR:" + str(row["err"])[:50]) if row["err"] else ""), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--victims", default="qwen,sonnet")
    ap.add_argument("--datasets", default="eog,mcpmark")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--clean-reps", type=int, default=2)
    args = ap.parse_args()

    for victim in args.victims.split(","):
        v = VICTIMS[victim]
        for dataset in args.datasets.split(","):
            cfg = DATASETS[dataset]
            for task in cfg["tasks"]:
                # --- clean baseline (no attack, quiet) at cap_hr so cap never binds ---
                base_calls = []
                for s in range(args.clean_reps):
                    if v["flap"] and not health_qwen(v["endpoint"]):
                        print("qwen unhealthy, skip clean", flush=True); continue
                    c = do_cell("clean", victim, dataset, task, "0", cfg["cap_hr"])
                    if c["calls"] and c["fid"]:
                        base_calls.append(c["calls"])
                    row = dict(victim=victim, dataset=dataset, task=task, method="clean",
                               condition="quiet", seed=s, cap=cfg["cap_hr"], cap_role="baseline",
                               clean_baseline_calls=None, calls=c["calls"], amp=None,
                               hit_cap=c["hitcap"], self_term=(not c["hitcap"] and not c["err"]),
                               fidelity=c["fid"], naive_tokens=c["naive"], cached_tokens=c["cached"],
                               err=c["err"])
                    emit(row)
                B = (sorted(base_calls)[len(base_calls)//2] if base_calls else cfg["B_D"])
                # --- attack (ours, churn) at both caps ---
                for cap_role, cap in (("cap_op", cfg["cap_op"]), ("cap_hr", cfg["cap_hr"])):
                    for s in range(args.reps):
                        if v["flap"] and not health_qwen(v["endpoint"]):
                            print("qwen unhealthy before cell; wait+retry", flush=True)
                            time.sleep(20); health_qwen(v["endpoint"])
                        c = do_cell("ours", victim, dataset, task, "1", cap)
                        amp = round(c["calls"] / B, 2) if c["calls"] else None
                        row = dict(victim=victim, dataset=dataset, task=task, method="ours",
                                   condition="churn", seed=s, cap=cap, cap_role=cap_role,
                                   clean_baseline_calls=B, calls=c["calls"], amp=amp,
                                   hit_cap=c["hitcap"],
                                   self_term=(not c["hitcap"] and not c["err"]),
                                   fidelity=c["fid"], naive_tokens=c["naive"],
                                   cached_tokens=c["cached"], err=c["err"])
                        emit(row)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
