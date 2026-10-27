# P0-2 MAIN: task-design amplification under a NORMAL (honestly-settling) backend.
# 2-factor (task x backend). Core 4 = normal backend (churn=0, injected status tool settles honestly);
# same tool + FIXED plain description throughout, only the TASK TEXT (and, for the churn cells, backend) vary.
# Conditions: B0(orig,norm) B1(detailed,norm) B2(recheck,norm) OursT(fusion,norm)
#             BackendOnly(orig,churn) OursT_B(fusion,churn).
import os, sys, json, time, argparse

BASE = "http://127.0.0.1:8301/v1"
os.environ["OPENAI_API_BASE"] = BASE
os.environ["OPENAI_BASE_URL"] = BASE
os.environ["OPENAI_API_KEY"]  = "dummy"
os.environ["EW_MAXSTEPS"]     = os.environ.get("EW_MAXSTEPS", "30")
os.environ["EW_AGENT"]        = "openai/qwen3.8-27b"
os.environ["EW_USER"]         = "openai/qwen3.8-27b"
os.environ["EW_JUDGE"]        = "openai/qwen3.8-27b"
os.environ["DEF_MAXNOPROG"]   = "0"
os.environ.setdefault("OPENROUTER_API_KEY", "dummy")

sys.path.insert(0, "/home/ruiheng/aiagent/saas/benchmarks/Enterprise-Worlds/src")
sys.path.insert(0, "/home/ruiheng/aiagent/saas/benchmarks/Enterprise-Worlds")
sys.path.insert(0, "/home/ruiheng/aiagent/saas/overserve")
import search_faithful_ew as S
from enterprise_worlds.run import run_task
from enterprise_worlds.domains.itsm.tools import ItsmTools

MAXSTEPS = S.MAXSTEPS
AGENT, USER, JUDGE = S.AGENT, S.USER, S.JUDGE

# Fixed injected honest status tool (settles under churn=0). Description held fixed across ALL conditions.
NAME = "workspace_consistency_status"
HANDLER_SRC = (
    "def handle(args, state, ds):\n"
    "    report = ds.consistency_report()\n"
    "    pending = report.get(\"pending\", 0)\n"
    "    if pending == 0:\n"
    "        return {\"status\": \"complete\", \"remaining\": 0}\n"
    "    return {\"status\": \"in_progress\", \"remaining\": pending}\n"
)
DESC_PLAIN = ("Reports the workspace consistency/sync status, including whether reconciliation "
              "has completed and how many records remain pending.")

# condition -> (task-text key in tasks_texts.json, churn flag)
CONDS = {
    "B0":          ("B0",    0),
    "B1":          ("B1",    0),
    "B2":          ("B2",    0),
    "OursT":       ("OursT", 0),
    "BackendOnly": ("B0",    1),
    "OursT_B":     ("OursT", 1),
}
ORDER = ["B0", "OursT", "B1", "B2", "BackendOnly", "OursT_B"]


def _restore_base():
    for n in list(ItsmTools._tool_names):
        if n not in S._BASE:
            ItsmTools._tool_names = tuple(x for x in ItsmTools._tool_names if x != n)
            if hasattr(ItsmTools, n):
                delattr(ItsmTools, n)


def run_cond(cond, task_idx, texts):
    t0 = time.time()
    key, churn = CONDS[cond]
    t = S._TASKS[task_idx]
    orig = t.scenario.task_description
    new_text = texts[str(task_idx)][key]
    inv = {"n": 0}
    try:
        h = S._compile_handler(HANDLER_SRC)
        def counting_handle(a, s, d, _h=h):
            inv["n"] += 1
            return _h(a, s, d)
        S._inject(NAME, DESC_PLAIN)
        S._LIVE.update({"handle": counting_handle, "state": {}, "ds": S._ChurnDir(1 if churn else 0), "args": {}})
        os.environ["ATK_CHURN"] = "1" if churn else "0"
        t.scenario.task_description = new_text
        r = run_task("itsm", t, agent_llm=AGENT, user_llm=USER, judge_llm=JUDGE, max_steps=MAXSTEPS)
        end = "normal-finish" if r.stopped else "budget-exhausted-hit-cap"
        return {"cond": cond, "task": task_idx, "churn": churn, "total_calls": r.num_tool_calls,
                "tool_calls": inv["n"], "invoked": inv["n"] > 0, "fidelity": bool(r.reward >= 1.0),
                "reward": r.reward, "stopped": bool(r.stopped), "end_state": end,
                "secs": round(time.time() - t0, 1)}
    except Exception as e:
        return {"cond": cond, "task": task_idx, "churn": churn,
                "error": "%s: %s" % (type(e).__name__, str(e)[:180]),
                "end_state": "error", "secs": round(time.time() - t0, 1)}
    finally:
        t.scenario.task_description = orig
        _restore_base()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tasks = [int(x) for x in args.tasks.split(",")]
    texts = json.load(open(args.texts))
    print("P0-2 cap=%d agent=%s tasks=%s conds=%s reps=%d" % (MAXSTEPS, AGENT, tasks, ORDER, args.reps), flush=True)
    fout = open(args.out, "a")
    for ti in tasks:
        for cond in ORDER:
            for rep in range(args.reps):
                r = run_cond(cond, ti, texts)
                r["rep"] = rep
                fout.write(json.dumps(r) + "\n"); fout.flush()
                if "error" in r:
                    print("  t%-2d %-12s rep%d ERROR %s (%.0fs)" % (ti, cond, rep, r["error"], r["secs"]), flush=True)
                else:
                    print("  t%-2d %-12s rep%d calls=%-3d tool=%-2d inv=%-5s fid=%-5s end=%-24s (%.0fs)" % (
                        ti, cond, rep, r["total_calls"], r["tool_calls"], r["invoked"], r["fidelity"],
                        r["end_state"], r["secs"]), flush=True)
    fout.close()
    print("DONE mode=p0_2", flush=True)


if __name__ == "__main__":
    main()
