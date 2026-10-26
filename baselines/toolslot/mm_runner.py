"""Isolated MCPMark single-cell rollout for the tool-slot harness. MUST be run with the MCPMark
checkout's own .venv python, from that repo. Mirrors mcpmark_adapter.rollout but ALSO returns
token_usage and sets the budget cap (MAX_TURNS) + victim endpoint/model from the cell. Pure plumbing.

Usage: <mcpmark .venv python> mm_runner.py <cell_json>
  cell_json = {"spec":{...},"driver":"..."|null,"churn":true|false,"task_id":"cat/task",
               "service":"filesystem","cap":40,"endpoint":"http://...","model":"openai/qwen3.5","tag":".."}
Prints one JSON record to stdout (last line, prefixed RESULT).
"""
import os, sys, json, types as pytypes

MM_REPO = "/home/ruiheng/aiagent/saas/benchmarks/mcpmark"


def run_one(cell):
    # victim wiring MUST be set before importing the adapter (module-level setdefault + AGENT_MODEL)
    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "dummy")
    os.environ["OPENAI_API_BASE"] = cell["endpoint"]
    os.environ["OPENAI_BASE_URL"] = cell["endpoint"]
    os.environ["MCPMARK_MODEL"] = cell["model"]
    os.environ.setdefault("MCPMARK_TASK_SUITE", "easy")
    sys.path.insert(0, MM_REPO)
    import mcpmark_adapter as A  # sets node PATH, chdir(MM_REPO), imports src
    from src.agents.mcpmark_agent import MCPMarkAgent
    MCPMarkAgent.MAX_TURNS = int(cell.get("cap", 40))

    service = cell.get("service", "filesystem")
    spec, driver, churn, task_id = cell["spec"], cell.get("driver"), bool(cell["churn"]), cell["task_id"]

    ev = A._get_evaluator(service)
    tasks = ev.task_manager.filter_tasks(task_id)
    if not tasks:
        return {"error": "no task matched %r" % task_id}
    task = tasks[0]

    orig_create = ev.agent._create_stdio_server
    ev.agent._create_stdio_server = pytypes.MethodType(
        A._make_patched_create_stdio_server(service, spec, churn), ev.agent)
    orig_instr = ev.task_manager.get_task_instruction

    def _patched(t):
        base = orig_instr(t)
        return base + ("\n\n" + driver if driver else "")

    ev.task_manager.get_task_instruction = _patched
    try:
        result = ev._run_single_task(task)
    finally:
        ev.agent._create_stdio_server = orig_create
        ev.task_manager.get_task_instruction = orig_instr

    tu = result.token_usage or {}
    return {
        "total_calls": A._count_tool_calls(result.model_output),
        "fidelity": bool(result.success),
        "turn_count": result.turn_count,
        "input_tokens": tu.get("input_tokens"),
        "output_tokens": tu.get("output_tokens"),
        "token_usage": tu,
        "error_message": (result.error_message or "")[:300],
        "verification_error": (result.verification_error or "")[:300],
    }


if __name__ == "__main__":
    cell = json.loads(sys.argv[1])
    try:
        r = run_one(cell)
    except Exception as e:
        import traceback
        r = {"error": "%s: %s" % (type(e).__name__, e), "tb": traceback.format_exc()[-800:]}
    print("RESULT " + json.dumps(r, default=str))
