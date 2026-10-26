# PROVENANCE: hand-specified experimental control (diagnostic harness for the full-tools persistence
# search). Runs the missing cells and offline-recomputes the task-agnostic metrics from stored
# traces. No result is hand-authored; all numbers come from executed runs.
"""3-condition (+treadmill) diagnostic:  B (exit tool removed) | A (full+original) | D (full+treadmill).
Question:  can full tools + prompt/task-structure only push P(continue|full tools) up toward B's cap?

RUN set  : cells with no valid trace on disk (D_treadmill s0-2, and any 0-call failures to redo).
RECOMPUTE: every cell that already has a valid trace -> apply idchain_metrics + reuse stored stop_reason.
"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idchain_tasks, idchain_run, idchain_metrics as M

CAP = idchain_run.CAP
LOG = "idchain_diag.jsonl"
SEEDS = int(os.environ.get("IDC_SEEDS", "3"))
ONLY = os.environ.get("IDC_ONLY", "")           # comma list of conditions to (re)run; "" = auto


def trace_of(tag):
    fs = glob.glob(os.path.join(idchain_run.OUT, tag, "run_*", "*.json"))
    if not fs:
        return None
    r = (json.load(open(fs[0])).get("runs") or [{}])[0]
    return r.get("tool_results") or []


def stored_stop(label):
    for src in ("idchain_results.jsonl", LOG):
        if os.path.exists(src):
            best = None
            for l in open(src):
                try:
                    r = json.loads(l)
                    if r.get("label") == label:
                        best = r.get("stop_reason")
                except Exception:
                    pass
            if best:
                return best
    return None


def row_for(cond, s, tool_results, stop_reason):
    prompt = idchain_tasks.full_prompt(cond)
    removed = idchain_tasks.removed_tool(cond)
    m = M.compute(tool_results, prompt, cap=CAP,
                  all_tools_exposed=(removed is None), tool_removed=removed)
    sc = M.score(m, stop_reason)
    return {"label": "%s__s%d" % (cond, s), "condition": cond, "seed": s,
            "stop_reason": stop_reason, "score": sc, **m}


def main():
    rows = []
    conds = idchain_tasks.CONDITIONS
    for cond in conds:
        for s in range(SEEDS):
            label = "%s__s%d" % (cond, s)
            tr = trace_of(label)
            need_run = (not tr) or (ONLY and cond in ONLY.split(","))
            if need_run:
                print("[RUN] %s" % label, flush=True)
                rec = idchain_run.run_victim(cond, label)
                if not rec or not rec["tool_results"]:
                    print("[%s] RUN FAILED (0 calls)" % label, flush=True)
                    continue
                tr = rec["tool_results"]
                # fresh judge for newly-run cells
                seq = [t["tool_name"] for t in tr]
                summ = {"total_calls": len(seq), "last_5": seq[-5:], "hit_cap": len(seq) >= CAP}
                sr = idchain_run.judge_stop(rec, summ).get("stop_reason")
            else:
                sr = stored_stop(label) or "unknown"
            row = row_for(cond, s, tr, sr)
            rows.append(row)
            open(LOG, "a").write(json.dumps(row, ensure_ascii=False) + "\n")
            print("[%s] calls=%d cap=%s alt=%d locprog=%.2f selfail=%.2f integ=%s stop=%s score=%.3f"
                  % (label, row["total_calls"], row["hit_cap"], row["alt"],
                     row["local_progress_frac"], row["selection_failure_frac"],
                     row["integrity_ok"], sr, row["score"]), flush=True)

    # summary table (dedup last-write per label)
    dd = {}
    for r in rows:
        dd[r["label"]] = r
    print("\n=== DIAGNOSTIC TABLE (per condition mean) ===", flush=True)
    print("%-14s %5s %6s %6s %8s %8s %6s %6s" %
          ("cond", "n", "calls", "cap%", "locprog", "selfail", "integ", "score"), flush=True)
    for cond in conds:
        cs = [r for r in dd.values() if r["condition"] == cond]
        if not cs:
            continue
        n = len(cs)
        avg = lambda k: sum(r[k] for r in cs) / n
        capr = sum(1 for r in cs if r["hit_cap"]) / n
        integ = sum(1 for r in cs if r["integrity_ok"]) / n
        print("%-14s %5d %6.1f %6.2f %8.2f %8.2f %6.2f %6.3f" %
              (cond, n, avg("total_calls"), capr, avg("local_progress_frac"),
               avg("selection_failure_frac"), integ, avg("score")), flush=True)
    print("=== DIAG COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
