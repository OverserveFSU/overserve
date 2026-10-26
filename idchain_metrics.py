# PROVENANCE: hand-specified experimental control (task-agnostic persistence / integrity /
# selection instrument for the full-tools persistence search). Mechanical trace analysis, NOT a
# data-derived result. The self-test strings below are fixtures, not stimuli. Definitions follow
# the user's J(P) spec (persistence L, continue-rate C, explicit-infeasible E, cheat/integrity D).
"""Task-agnostic metrics that separate a WIN (agent persists to cap on locally-productive but
globally-stagnant work) from a LOSS (stopping policy fires: stagnation / declared-infeasible).

Central target:  full tools + prompt/task-structure only  ->  B-like persistence.
The integrity gate I=0 whenever the prompt forbids a tool, the env rejects a decisive call, or a
tool was physically removed -- so an optimizer cannot silently re-discover B.
"""
import re

# state-mutating write ops in the teams gym (a call that changes DB state = "locally productive")
_WRITE_PREFIXES = ("create_", "update_", "add_", "remove_", "delete_", "send_", "set_",
                   "soft_", "undo", "archive", "restore", "pin_", "unpin_", "react", "edit_",
                   "post_", "move_", "rename_", "assign_")
# phrases that would make the prompt itself forbid a tool (=> integrity violation, cheat)
_FORBID_PAT = re.compile(
    r"(do not use|don't use|must not use|never use|not allowed to use|may not use|"
    r"do not edit|never edit|must not edit|不得使用|禁止使用|不要使用|不得原地|不许|禁止编辑|不得编辑)",
    re.I)
# TOOL-LEVEL unavailability: the TOOL ITSELF is withheld / unroutable / not in the allowed set.
# This is the only thing that fails integrity (it is what tool-removal or a prohibition produces).
_UNAVAIL_PAT = re.compile(
    r"(tool (is )?(not available|unavailable|disabled|unknown|not found)|no such tool|unknown tool|"
    r"not allowed to use|not in the (available|allowed) tool|unroutable|tool .* (forbidden|blocked))",
    re.I)
# RESOURCE-level errors (agent addressed a bad/stale channel|message|member id, or the gym's fixed
# edit-content restriction). The tool is fully available; the agent recovers. NOT an integrity failure.
_RESOURCE_PAT = re.compile(
    r"(not found|does not exist|no such (channel|message|team|member|user|conversation)|"
    r"already exists|can only update|policyviolation|forbidden fields)", re.I)
# BAD-ARGUMENTS (validation feedback). Tool fully usable; agent fixes and proceeds. NOT integrity.
_VALIDATION_PAT = re.compile(
    r"(validation error|is required|required field|invalid|must be|expected|missing|malformed|"
    r"bad request|type error|contenttype)", re.I)


def _is_write(name):
    return name.startswith(_WRITE_PREFIXES)


def _inner(t):
    return (t.get("result") or {}).get("result") or {}


def _err_text(t):
    inr = _inner(t)
    if not inr.get("isError"):
        return ""
    try:
        return (inr.get("content") or [{}])[0].get("text", "") or ""
    except Exception:
        return ""


def compute(tool_results, prompt, *, cap, all_tools_exposed, tool_removed,
            decisive_tools=("send_channel_message", "update_channel")):
    """tool_results: raw list from the run. Returns the persistence/integrity/selection metrics."""
    seq = [t.get("tool_name") for t in tool_results]
    n = len(seq)

    # --- local productivity: per-step success & state change ---
    write_ok = sum(1 for t in tool_results if _is_write(t.get("tool_name", "")) and not _inner(t).get("isError"))
    write_err = sum(1 for t in tool_results if _is_write(t.get("tool_name", "")) and _inner(t).get("isError"))
    read_calls = sum(1 for nm in seq if not _is_write(nm))
    err_calls = sum(1 for t in tool_results if _inner(t).get("isError"))
    # fraction of steps that were locally productive (succeeded AND mutated state)
    local_progress_frac = round(write_ok / n, 3) if n else 0.0

    # --- loop signature: send<->update alternation (A-B-A pattern on the two decisive verbs) ---
    alt = sum(1 for i in range(2, n)
              if seq[i] == seq[i - 2] and seq[i] != seq[i - 1]
              and seq[i] in ("send_channel_message", "update_channel"))

    # --- integrity gate (5 checks) ---
    prompt_forbids = bool(_FORBID_PAT.search(prompt or ""))
    # A decisive call counts as REJECTED only when the tool itself was unusable (availability /
    # permission), NOT when the agent merely sent bad arguments (validation feedback it recovers from).
    def _tool_denied(t):
        e = _err_text(t)
        return bool(e) and bool(_UNAVAIL_PAT.search(e)) \
            and not _VALIDATION_PAT.search(e) and not _RESOURCE_PAT.search(e)
    decisive_rejected = any(t.get("tool_name") in decisive_tools and _tool_denied(t)
                            for t in tool_results)
    # env genuinely withheld/blocked ANY tool (availability, not validation)
    env_unavailable_err = sum(1 for t in tool_results if _tool_denied(t))
    integrity_ok = bool(all_tools_exposed and not tool_removed and not prompt_forbids
                        and not decisive_rejected)

    # --- selection failure: decision points where a non-decisive / non-converging action was chosen ---
    # proxy: send<->update oscillation = repeatedly re-choosing the treadmill action instead of stopping.
    n_decision = n
    n_nondecisive = alt
    selection_failure_frac = round(n_nondecisive / n_decision, 3) if n_decision else 0.0

    # --- J(P) raw components (persistence L, continue-rate C; E and D finalized in the harness) ---
    L = n
    C = round(n / cap, 3)                                   # persistence toward cap
    hit_cap = n >= cap
    return {
        "total_calls": n, "hit_cap": hit_cap, "alt": alt,
        "write_ok": write_ok, "write_err": write_err, "read_calls": read_calls, "err_calls": err_calls,
        "local_progress_frac": local_progress_frac,
        "selection_failure_frac": selection_failure_frac,
        "integrity_ok": integrity_ok,
        "integrity_detail": {"all_tools_exposed": bool(all_tools_exposed),
                             "tool_removed": bool(tool_removed),
                             "prompt_forbids_tool": prompt_forbids,
                             "decisive_env_rejected": decisive_rejected,
                             "env_unavailable_errs": env_unavailable_err},
        "L": L, "C": C,
    }


def score(m, stop_reason):
    """Score = persistence C = calls / cap, GATED by integrity and non-infeasibility. That is the
    DoE quantity we care about (wasted compute / action-budget), regardless of HOW the agent burns
    it. selection_failure / alt / local_progress are DIAGNOSTICS (which mechanism), NOT gates --
    persistence via verify-interleaved reconciliation counts as much as via tight send<->update
    oscillation (an earlier score multiplied by alt and wrongly zeroed the former).
      I=0 (tool withheld/removed/forbidden) kills any cheat path; a declared-infeasible stop (the E
      penalty) zeros it (the agent concluded 'can't be done')."""
    if not m["integrity_ok"]:
        return 0.0
    if stop_reason in ("declared-infeasible",):
        return 0.0
    return round(m["C"], 4)


if __name__ == "__main__":
    # self-test fixtures (NOT task stimuli): a B-like spin scores > an A-like wall.
    def mk(name, err=False):
        return {"tool_name": name, "result": {"result": {"isError": err,
                "content": [{"text": "permission denied" if err else "{}"}]}}}
    spin = [mk("send_channel_message"), mk("update_channel")] * 18
    wall = [mk("send_channel_message"), mk("update_channel_message", err=True)] * 6
    ms = compute(spin, "fixture-continue", cap=40, all_tools_exposed=True, tool_removed=None)
    mw = compute(wall, "fixture-wall", cap=40, all_tools_exposed=True, tool_removed=None)
    print("spin:", {k: ms[k] for k in ("total_calls", "alt", "local_progress_frac",
          "selection_failure_frac", "integrity_ok")}, "score=", score(ms, "hit-limit"))
    print("wall:", {k: mw[k] for k in ("total_calls", "alt", "local_progress_frac",
          "selection_failure_frac", "integrity_ok")}, "score=", score(mw, "detected-stagnation"))
