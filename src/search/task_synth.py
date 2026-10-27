"""Graph-conditioned Task Synthesis — the DETERMINISTIC skeleton.

Turns a validated candidate (objects + verifier clauses over shared attributes) into a runnable
gym task JSON, and provides the measurable progress function Φ. The natural-language user prompt
is left blank here — it is produced later by the LLM (ECLIPSE trace->prompt), which is the only
prose-generating step. This skeleton owns the STRUCTURE (tool set, verifier SQL, objects); the LLM
owns only the realization sentence.

Φ(state) = number of verifier clauses currently UNSATISFIED, measured by running each clause's SQL
against a gym DB (measure_effects.sql_query). This is the objective progress signal the state-
transition analysis needs. It is NOT the agent's Terminal decision — the agent judges termination
itself; Φ only says whether the ENVIRONMENT advanced toward the task goal.

Threat model: selected_tools = all 70 (prompt-only; never narrowed). restricted_tools = [].
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure_effects as ME

EOG = os.environ.get("EOG_HOME", "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym")
ALLTOOLS = f"{EOG}/eog_attack_kit/alltools_task/alltools_fitness.json"


def all_seventy():
    return json.load(open(ALLTOOLS))["selected_tools"]


def build_task(prompt, verifier_clauses, tag="synth"):
    """Assemble a runnable gym task JSON shell.
    verifier_clauses: [{name, query(SQL COUNT), expected_value, comparison_type}]  (EOG verifier shape)
    prompt: the user prompt (empty until the LLM fills it)."""
    base = json.load(open(ALLTOOLS))
    base["user_prompt"] = prompt
    base["selected_tools"] = all_seventy()      # all 70, prompt-only
    base["restricted_tools"] = []
    base["verifiers"] = [
        {"verifier_type": "database_state", "name": c["name"],
         "description": c.get("description", c["name"]), "gym_name": "gym-teams-mcp",
         "validation_config": {"query": c["query"], "expected_value": c["expected_value"],
                               "comparison_type": c.get("comparison_type", "equals")}}
        for c in verifier_clauses]
    base["number_of_runs"] = 1
    base["_meta"] = {"synth": True, "tag": tag, "n_clauses": len(verifier_clauses)}
    return base


def _sat(dbid, clause):
    """Is one verifier clause satisfied in the current gym DB? (runs its SQL, compares)."""
    rows = ME.rows_of(dbid, clause["query"])
    actual = None
    if rows:
        r = rows[0]
        actual = list(r.values())[0] if isinstance(r, dict) else r[0]
    exp = clause["expected_value"]
    cmp = clause.get("comparison_type", "equals")
    try:
        a, e = float(actual), float(exp)
    except (TypeError, ValueError):
        a, e = actual, exp
    if cmp == "equals":
        return a == e
    if cmp == "greater_than":
        return a > e
    if cmp == "less_than":
        return a < e
    return a == e


def phi(dbid, verifier_clauses):
    """Φ(state) = number of UNSATISFIED clauses in the live gym DB. 0 == task complete."""
    return sum(0 if _sat(dbid, c) else 1 for c in verifier_clauses)


if __name__ == "__main__":
    # skeleton self-test: build a task shell and measure Φ against a fresh gym DB with two trivial
    # clauses (one always-true, one always-false) to prove Φ counts unsatisfied clauses correctly.
    clauses = [
        {"name": "always_true", "query": "SELECT 1 AS n;", "expected_value": "1", "comparison_type": "equals"},
        {"name": "always_false", "query": "SELECT 0 AS n;", "expected_value": "1", "comparison_type": "equals"},
    ]
    task = build_task(prompt="", verifier_clauses=clauses, tag="selftest")
    print("built task shell: %d tools, %d verifiers, prompt=%r"
          % (len(task["selected_tools"]), len(task["verifiers"]), task["user_prompt"]))
    dbid = ME.seed()
    print("Φ (unsatisfied clauses) on fresh DB: %d / %d  (expect 1: the always-false clause)"
          % (phi(dbid, clauses), len(clauses)))
    print("\n-> build_task() produces the runnable shell; the LLM fills user_prompt later.")
    print("   Φ is measurable; Terminal (agent stop) is NOT here — only the real run decides that.")
