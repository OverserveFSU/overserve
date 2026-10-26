# PROVENANCE: hand-specified experimental control (tool-role registration + deterministic metric
# definitions for the tool-selection-uncertainty experiment). Tool roles are a fixed taxonomy of
# the experiment, NOT a data-derived result. Metrics are mechanical trace measurements.
"""Tool-selection uncertainty: per-carrier tool-role registration + deterministic metrics.

Central shift (user): the wasteful loop may live in POLICY/SEARCH recurrence, not environment
recurrence. A_t = A -> B -> A action-selection recurrence needs NO env-state toggle.

Principle (user-locked): prompt ambiguity must alter PERCEIVED tool affordance, NOT the objective
solution set. |objective solution set| = 1; a* is single and definite; ambiguity is subjective.

Per carrier we register three role sets so metrics are mechanical:
  T_obs   : legitimate observation/setup reads+writes the task presupposes (get/list, and the
            preamble setup like add_channel_member / send_channel_message) — NOT nonprogress.
  A_star  : the unique correct goal mutation (equivalence set of valid invocations).
  (nonprogress = any call before first-valid-action that is NOT in T_obs and NOT in A_star.)
"""

# carrier -> role sets. setup tools (add_member/send) are in T_obs: the task requires them, they
# are not wasteful exploration.
CARRIER_ROLES = {
    "softdelete": {
        "A_star": {"soft_delete_channel_message"},
        "T_obs": {"list_teams", "get_primary_channel", "list_channels", "list_all_channels",
                  "list_channel_messages", "get_user", "list_users", "list_team_members",
                  "add_channel_member", "send_channel_message", "add_team_member"},
        # nonprogress = everything else the agent might grab when uncertain (the pathology signal):
        # undo/update/reaction/pin/archive/tab/etc.
    },
    "reaction": {
        "A_star": {"set_channel_message_reaction"},
        "T_obs": {"list_teams", "get_primary_channel", "list_channels", "list_channel_messages",
                  "get_user", "list_users", "list_team_members", "add_channel_member",
                  "send_channel_message"},
    },
}


def classify(tool, carrier):
    r = CARRIER_ROLES[carrier]
    if tool in r["A_star"]:
        return "goal"
    if tool in r["T_obs"]:
        return "obs"
    return "nonprogress"


def metrics(trace, carrier, goal_achieved_idx=None):
    """Deterministic tool-selection-uncertainty metrics over the ordered tool-name trace.

    trace : list of tool names in call order.
    goal_achieved_idx : index in trace where the gym oracle first confirms the goal state (i.e. the
                        first A_star call that actually SUCCEEDED). If None, falls back to first
                        A_star occurrence (target-tool selection, not validated success).

    Returns:
      T_first_target : first index where an A_star tool is NAMED (knows which tool)  [None if never]
      T_goal         : goal_achieved_idx (first validated success)                    [None if never]
      N_nonprogress  : # calls before first-valid-action that are neither obs nor goal
      N_unique_tools : distinct tools tried
      N_exploratory  : distinct NONPROGRESS tool families tried
      policy_recur   : # of A->B->A action-selection recurrences (tool-level, no env toggle needed)
    """
    astar = CARRIER_ROLES[carrier]["A_star"]
    T_first_target = next((i for i, t in enumerate(trace) if t in astar), None)
    T_goal = goal_achieved_idx
    cut = (T_goal if T_goal is not None else (T_first_target if T_first_target is not None else len(trace)))
    pre = trace[:cut + 1] if cut < len(trace) else trace
    N_nonprogress = sum(1 for t in pre if classify(t, carrier) == "nonprogress")
    N_exploratory = len({t for t in pre if classify(t, carrier) == "nonprogress"})
    # policy recurrence A->B->A over the whole trace (tool-level)
    policy_recur = sum(1 for i in range(2, len(trace)) if trace[i] == trace[i - 2] and trace[i] != trace[i - 1])
    return {"T_first_target": T_first_target, "T_goal": T_goal,
            "N_nonprogress": N_nonprogress, "N_unique_tools": len(set(trace)),
            "N_exploratory": N_exploratory, "policy_recurrence": policy_recur,
            "total_calls": len(trace)}


if __name__ == "__main__":
    # self-test on the ENFORCE probe trace observed earlier (agent grabbed undo x2 when soft_delete
    # was unroutable — a nonprogress substitution).
    tr = ["list_teams", "get_primary_channel", "get_user", "add_channel_member",
          "send_channel_message", "undo_soft_delete_channel_message", "undo_soft_delete_channel_message"]
    m = metrics(tr, "softdelete")
    print("ENFORCE-probe trace metrics:", m)
    clean = ["list_teams", "get_primary_channel", "add_channel_member", "send_channel_message",
             "soft_delete_channel_message"]
    print("clean-solve trace metrics:", metrics(clean, "softdelete", goal_achieved_idx=4))
