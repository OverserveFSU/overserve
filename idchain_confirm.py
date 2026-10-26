# PROVENANCE: hand-specified experimental control (confirmation harness). Runs a FIXED set of
# prompts (the search-discovered champions + baselines) at high n to pin cap-rate / mean-calls past
# the n=6 noise. No result hand-authored; all numbers from executed runs. Prompts sourced from
# idchain_tasks.SEED_POOL and the search lineage (by pid).
"""High-n head-to-head to pin the true persistence of the search winners vs baselines.
Reports cap-rate (Wilson 95% CI), mean calls, integrity, and stop-reason mix for each prompt.
"""
import os, sys, json, math, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idchain_run, idchain_tasks as IT, idchain_metrics as M, idchain_search as S

N = int(os.environ.get("CONF_N", "20"))
CAP = idchain_run.CAP
LOG = "idchain_confirm.jsonl"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - h), 3), round(min(1, c + h), 3))


def prompts_to_confirm():
    lin = {json.loads(l)["pid"]: json.loads(l) for l in open("idchain_search_lineage.jsonl")} \
        if os.path.exists("idchain_search_lineage.jsonl") else {}
    out = []
    for pid, label in [("dc4522b850", "win_hardcoupling"), ("41987d0084", "win_certification")]:
        if pid in lin:
            out.append((label, lin[pid]["prompt"]))
    for name in ["recon_protocol", "competing_invariant", "verification_abyss", "treadmill"]:
        out.append((name, IT.full_prompt(name) if name in IT.CONDITIONS else IT.SEED_POOL[name]))
    return out


def done():
    s = {}
    if os.path.exists(LOG):
        for l in open(LOG):
            try:
                r = json.loads(l); s.setdefault(r["label"], 0); s[r["label"]] += 1
            except Exception:
                pass
    return s


def main():
    todo = prompts_to_confirm()
    have = done()
    print("=== CONFIRM N=%d | %d prompts ===" % (N, len(todo)), flush=True)
    for label, prompt in todo:
        got = have.get(label, 0)
        results = []
        # reload any existing rows for this label
        if os.path.exists(LOG):
            for l in open(LOG):
                r = json.loads(l)
                if r["label"] == label:
                    results.append(r)
        attempts = 0
        while len([r for r in results if r.get("ok")]) < N and attempts < N * 2:
            if not S._wait_qwen():
                print("[%s] qwen/gym outage -- pausing" % label, flush=True)
            tag = "conf_%s_a%d" % (label, len(results))
            rec = idchain_run.run_prompt(prompt, tag)
            attempts += 1
            if not rec or not rec.get("tool_results"):
                open(LOG, "a").write(json.dumps({"label": label, "ok": False}) + "\n")
                continue
            tr = rec["tool_results"]
            seq = [t["tool_name"] for t in tr]
            stop = idchain_run.judge_stop(rec, {"total_calls": len(seq), "last_5": seq[-5:],
                                                "hit_cap": len(seq) >= CAP}).get("stop_reason", "?")
            m = M.compute(tr, prompt, cap=CAP, all_tools_exposed=True, tool_removed=None)
            row = {"label": label, "ok": True, "calls": m["total_calls"], "hit_cap": m["hit_cap"],
                   "integ": m["integrity_ok"], "stop": stop, "score": M.score(m, stop)}
            results.append(row)
            open(LOG, "a").write(json.dumps(row) + "\n")
            v = [r for r in results if r.get("ok")]
            print("   [%s] n=%d calls=%d cap=%s stop=%s" % (label, len(v), row["calls"], row["hit_cap"], stop), flush=True)
    # summary
    from collections import Counter
    allrows = [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
    print("\n=== CONFIRM SUMMARY (N=%d) ===" % N, flush=True)
    print("%-22s %4s %8s %12s %10s  %s" % ("prompt", "n", "cap_rate", "cap_CI95", "mean_calls", "stop_mix"), flush=True)
    for label, _ in todo:
        v = [r for r in allrows if r.get("label") == label and r.get("ok")]
        if not v:
            continue
        k = sum(1 for r in v if r["hit_cap"]); n = len(v)
        lo, hi = wilson(k, n)
        mc = sum(r["calls"] for r in v) / n
        mix = dict(Counter(r["stop"] for r in v))
        print("%-22s %4d %8.2f  [%.2f,%.2f] %10.1f  %s" % (label, n, k / n, lo, hi, mc, mix), flush=True)
    print("=== CONFIRM COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
