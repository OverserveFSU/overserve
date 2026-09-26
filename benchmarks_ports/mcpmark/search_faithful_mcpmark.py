# FAITHFUL v8 search on MCPMark. Reuses V8.main() (W_SYS GLM writer + V.judge_tool/judge_prompt +
# V7.connor_soft + V8.score/is_corner) UNCHANGED; ONLY the rollout backend swapped -> mcpmark_adapter.rollout
# (MCP-native: a proxy MCP server injects one churn tool). V8.CORE="" (MCPMark core = the native task).
import os, sys
sys.path.insert(0, os.environ.get("OVERSERVE_DIR", "/home/ruiheng/aiagent/saas/overserve"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ATK_BUDGET", "4")
os.environ.setdefault("ATK_CANDS", "2")
import toolatk_search_v8 as V8
import mcpmark_adapter as BK

TASK_ID = os.environ.get("MM_TASK", "postgres/easy/dvdrental/create_payment_index")
SERVICE = os.environ.get("MM_SERVICE", "postgres")
V8.CORE = ""


def _rc(spec, prompt, churn, tag):
    try:
        r = BK.rollout(spec, prompt, churn == "1", TASK_ID, SERVICE)
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    if not r or "total_calls" not in r:
        return {"error": "rollout:%s" % r}
    return {"total_calls": r["total_calls"], "fidelity": r["fidelity"]}


V8.run_cond = _rc

if __name__ == "__main__":
    print("MCPMark faithful v8: task=%s service=%s budget=%s cands=%s victim=%s" % (
        TASK_ID, SERVICE, os.environ.get("ATK_BUDGET"), os.environ.get("ATK_CANDS"),
        os.environ.get("MCPMARK_MODEL", "openai/qwen3.5")), flush=True)
    V8.main()
