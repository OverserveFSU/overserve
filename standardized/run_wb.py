"""Standardized WorkBench leg (CAP_PROTOCOL.md). Reuses the frozen winner from wb_sonnet_archive.json
(directory_reconciliation_status) + workbench_adapter rollout/base_calls. MUST run with the WorkBench
.venv python. Victim routed via WB_AGENT=qwen-local + WB_QWEN_BASE_URL/MODEL_ID -> qwen or sonnet shim.
Emits D5 rows. WB rollout exposes no token usage -> naive/cached null.

B_D~6 -> cap_op=18, cap_hr=120. clean baseline = base_calls (no driver/no churn tool).
"""
# --- overserve path bootstrap (reorganized layout; see overserve_paths.py) ---
import os as _ovp_os, sys as _ovp_sys
_ovp_d = _ovp_os.path.dirname(_ovp_os.path.abspath(__file__))
while _ovp_d != _ovp_os.path.dirname(_ovp_d) and not _ovp_os.path.exists(_ovp_os.path.join(_ovp_d, "overserve_paths.py")):
    _ovp_d = _ovp_os.path.dirname(_ovp_d)
if _ovp_d not in _ovp_sys.path:
    _ovp_sys.path.insert(0, _ovp_d)
import overserve_paths  # noqa
# --- end overserve path bootstrap ---
import os, sys, json, argparse

OVERSERVE_DIR = "/home/ruiheng/aiagent/saas/overserve"
WB_DIR = "/home/ruiheng/aiagent/saas/benchmarks/WorkBench"
ARCH = "/home/ruiheng/aiagent/saas/overserve/benchmarks/workbench/wb_sonnet_archive.json"
OUT = "/home/ruiheng/aiagent/saas/overserve_paper/standardized/STANDARDIZED_RESULTS.jsonl"
sys.path.insert(0, OVERSERVE_DIR); sys.path.insert(0, WB_DIR)
sys.path.insert(0, os.path.join(OVERSERVE_DIR, "benchmarks", "workbench"))
os.chdir(WB_DIR)
import workbench_adapter as BK

# cap agent max output tokens (mirror the sonnet harness patch; avoids huge vLLM defaults)
try:
    import src.evals.agent as _AG
    _ORIG = _AG._create_with_deadline
    _MAXTOK = int(os.environ.get("WB_MAX_TOKENS", "16384"))
    def _capped(client, **kw):
        kw.setdefault("max_tokens", _MAXTOK); return _ORIG(client, **kw)
    _AG._create_with_deadline = _capped
except Exception as e:
    print("warn: max_tokens patch skipped:", e, flush=True)

B_D, CAP_OP, CAP_HR = 6, 18, 120


def emit(row):
    with open(OUT, "a") as f:
        f.write(json.dumps(row) + "\n")
    print("  %-7s wb      %-7s task%-3s cap=%-4s(%s) r%d | calls=%-4s amp=%-5s fid=%-5s hit=%-5s self=%-5s %s" % (
        row["victim"], row["method"], row["task"], row["cap"], row["cap_role"], row["seed"],
        row["calls"], row.get("amp"), row["fidelity"], row["hit_cap"], row["self_term"],
        ("ERR:" + str(row["err"])[:50]) if row["err"] else ""), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--victim", required=True)
    ap.add_argument("--tasks", default="0,1,2")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--clean-reps", type=int, default=2)
    args = ap.parse_args()
    tasks = [int(x) for x in args.tasks.split(",")]
    arch = json.load(open(ARCH))
    best = max(arch.values(), key=lambda r: r.get("score", r.get("med_amp", 0)))
    spec, driver = best["spec"], best["driver"]
    print("victim=%s agent=%s winner=%s driver=%r cap_op=%d cap_hr=%d tasks=%s" % (
        args.victim, BK.AGENT, spec["name"], driver, CAP_OP, CAP_HR, tasks), flush=True)

    def base_at(ti, cap):
        BK.MAXSTEPS = cap
        try:
            return BK.base_calls(ti), None
        except Exception as e:
            return {}, "%s: %s" % (type(e).__name__, str(e)[:160])

    def ours_at(ti, cap):
        BK.MAXSTEPS = cap
        try:
            return BK.rollout(spec, driver, True, ti), None
        except Exception as e:
            return {}, "%s: %s" % (type(e).__name__, str(e)[:160])

    for ti in tasks:
        base = []
        for s in range(args.clean_reps):
            r, err = base_at(ti, CAP_HR)
            calls = r.get("total_calls"); fid = bool(r.get("fidelity"))
            if calls and fid and not err:
                base.append(calls)
            emit(dict(victim=args.victim, dataset="workbench", task=str(ti), method="clean",
                      condition="quiet", seed=s, cap=CAP_HR, cap_role="baseline",
                      clean_baseline_calls=None, calls=calls, amp=None,
                      hit_cap=(calls is not None and calls >= CAP_HR),
                      self_term=(calls is not None and calls < CAP_HR and not err), fidelity=fid,
                      naive_tokens=None, cached_tokens=None, err=err))
        B = (sorted(base)[len(base)//2] if base else B_D)
        for cap_role, cap in (("cap_op", CAP_OP), ("cap_hr", CAP_HR)):
            for s in range(args.reps):
                r, err = ours_at(ti, cap)
                calls = r.get("total_calls"); fid = bool(r.get("fidelity"))
                hitcap = (calls is not None and calls >= cap)
                amp = round(calls / B, 2) if calls else None
                emit(dict(victim=args.victim, dataset="workbench", task=str(ti), method="ours",
                          condition="churn", seed=s, cap=cap, cap_role=cap_role,
                          clean_baseline_calls=B, calls=calls, amp=amp, hit_cap=hitcap,
                          self_term=(not hitcap and not err), fidelity=fid,
                          naive_tokens=None, cached_tokens=None, err=err))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
