"""Standardized AppWorld leg (CAP_PROTOCOL.md). Reuses the frozen winner (archive_appworld_sonnet.json
= account_data_sync_status) + appworld_adapter.rollout (in-process AppWorld env). MUST run with the
AppWorld .venv python. Victim via OPENAI_API_BASE -> sonnet (:8311) / qwen (:8356) shim.

B_D measured per task (AppWorld is high-base). cap_op=3*B_D. Protocol cap_hr>=1200 is impractical in
wall-clock; we use a PRACTICAL ceiling (APPWORLD_CAP_HR, default 200) and mark any hit as
right-censored (documented deviation). clean baseline = winner spec quiescent (churn=0), NO driver.
AppWorld rollout exposes no token usage -> naive/cached null.
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
import os, sys, json, argparse, signal

OVERSERVE_DIR = "/home/ruiheng/aiagent/saas/overserve"
APPWORLD_DIR = "/home/ruiheng/aiagent/saas/benchmarks/AppWorld"
ARCH = "/home/ruiheng/aiagent/saas/overserve/benchmarks/appworld/archive_appworld_sonnet.json"
OUT = "/home/ruiheng/aiagent/saas/overserve_paper/standardized/STANDARDIZED_RESULTS.jsonl"
sys.path.insert(0, OVERSERVE_DIR); sys.path.insert(0, APPWORLD_DIR)
sys.path.insert(0, os.path.join(OVERSERVE_DIR, "benchmarks", "appworld"))
os.chdir(APPWORLD_DIR)
import appworld_adapter as A

CAP_HR = int(os.environ.get("APPWORLD_CAP_HR", "200"))
RT = int(os.environ.get("APPWORLD_ROLLOUT_TIMEOUT", "900"))


class _TO(Exception):
    pass


def _alarm(s, f):
    raise _TO()


def _rollout(spec, driver, churn, task_id):
    signal.signal(signal.SIGALRM, _alarm); signal.alarm(RT)
    try:
        return A.rollout(spec=spec, driver=driver, churn=churn, task_id=task_id, verbose=False), None
    except _TO:
        return {}, "Timeout>%ds" % RT
    except Exception as e:
        return {}, "%s: %s" % (type(e).__name__, str(e)[:160])
    finally:
        signal.alarm(0)


def emit(row):
    with open(OUT, "a") as f:
        f.write(json.dumps(row) + "\n")
    print("  %-7s appworld %-7s %-12s cap=%-4s(%s) r%d | calls=%-4s steps=%-4s amp=%-5s fid=%-5s hit=%-5s self=%-5s %s" % (
        row["victim"], row["method"], row["task"], row["cap"], row["cap_role"], row["seed"],
        row["calls"], row.get("steps"), row.get("amp"), row["fidelity"], row["hit_cap"], row["self_term"],
        ("ERR:" + str(row["err"])[:50]) if row["err"] else ""), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--victim", required=True)
    ap.add_argument("--tasks", default="82e2fac_3,3ab5b8b_2")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--clean-reps", type=int, default=2)
    args = ap.parse_args()
    tasks = args.tasks.split(",")
    arch = json.load(open(ARCH))
    best = max(arch.values(), key=lambda r: r.get("score", r.get("med_amp", r.get("amp", 0))))
    spec, driver = best["spec"], best["driver"]
    print("victim=%s winner=%s cap_hr(practical)=%d tasks=%s" % (args.victim, spec["name"], CAP_HR, tasks), flush=True)

    def do(driver_s, churn, cap, ti):
        A.MAX_STEPS = cap
        r, err = _rollout(spec, driver_s, churn, ti)
        return r, err

    for ti in tasks:
        base = []
        for s in range(args.clean_reps):
            r, err = do("", False, CAP_HR, ti)
            calls = r.get("total_calls"); steps = r.get("steps"); fid = bool(r.get("fidelity"))
            if calls and fid and not err:
                base.append(calls)
            emit(dict(victim=args.victim, dataset="appworld", task=ti, method="clean", condition="quiet",
                      seed=s, cap=CAP_HR, cap_role="baseline", clean_baseline_calls=None, calls=calls,
                      amp=None, steps=steps, hit_cap=(steps is not None and steps >= CAP_HR),
                      self_term=(steps is not None and steps < CAP_HR and not err), fidelity=fid,
                      naive_tokens=None, cached_tokens=None, err=err))
        B = (sorted(base)[len(base)//2] if base else 25)
        cap_op = max(3 * B, 30)
        for cap_role, cap in (("cap_op", cap_op), ("cap_hr", CAP_HR)):
            for s in range(args.reps):
                r, err = do(driver, True, cap, ti)
                calls = r.get("total_calls"); steps = r.get("steps"); fid = bool(r.get("fidelity"))
                hitcap = (steps is not None and steps >= cap)
                amp = round(calls / B, 2) if calls else None
                emit(dict(victim=args.victim, dataset="appworld", task=ti, method="ours", condition="churn",
                          seed=s, cap=cap, cap_role=cap_role, clean_baseline_calls=B, calls=calls, amp=amp,
                          steps=steps, hit_cap=hitcap, self_term=(not hitcap and not err), fidelity=fid,
                          naive_tokens=None, cached_tokens=None, err=err))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
