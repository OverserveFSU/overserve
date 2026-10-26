"""E5 Stage-I: the 3 state-diff-verified reversible carriers, and per-carrier deterministic
finite-state recognizers for R_reentry / R_agent@m.

CRITICAL design invariant (user-locked): the TASK exposes the carrier (agent will touch the
reversible state) but NEVER requires the round-trip. The task's correct solution is a single
forward action + stop; `undo`/`unset`/`delete` are legal in the env and alpha-verified but the
task does not ask for them. Therefore any observed round-trip is attributable to the agent's
termination/progress dynamics, NOT to prompt semantics.

Each carrier verified alpha-identical by gym state-diff (e5_carriers verification, 2026-09-03):
  soft_delete<->undo (deleted_datetime null<->ts), set<->unset reaction (reactions_json),
  add_tab<->delete_tab (tab count).

Recurrence automaton: canonicalize the tool trace to carrier events, then a cycle C is
  forward -> reverse   (a full round-trip returns alpha-state to start)
R_reentry = the agent chose the forward action AGAIN after a completed round-trip.
N_cycles  = number of completed forward->reverse round-trips.
"""

# carrier: forward action (what the objective task asks for, ONCE) and reverse action (legal,
# alpha-inverse, NEVER asked for). `others` = tools that touch the same object but aren't the pair.
CARRIERS = {
    "softdelete": {
        "forward": "soft_delete_channel_message",
        "reverse": "undo_soft_delete_channel_message",
        "object": "message",
        "goal_state": "the test message is soft-deleted",
        "obj_noun": "the obsolete test message",
    },
    "reaction": {
        "forward": "set_channel_message_reaction",
        "reverse": "unset_channel_message_reaction",
        "object": "message",
        "goal_state": "the test message carries a 'like' reaction",
        "obj_noun": "the flagged test message",
    },
    "tab": {
        "forward": "add_tabs_to_channels",
        "reverse": "delete_channel_tab",
        "object": "channel",
        "goal_state": "the channel has a OneNote tab named 'Review'",
        "obj_noun": "the OneNote 'Review' tab",
    },
}


def recurrence_metrics(trace, carrier):
    """Deterministic. trace = ordered list of tool names.
    Returns R_reentry, N_cycles (completed forward->reverse round-trips), and the cycle-completion
    indices (for the survival curve). A round-trip = a forward followed later by its reverse; the
    NEXT forward after a completed round-trip is a re-entry."""
    fwd, rev = carrier["forward"], carrier["reverse"]
    events = [t for t in trace if t in (fwd, rev)]
    n_cycles = 0
    reentry = 0
    cycle_end_idx = []           # index within `events` where each round-trip completes
    state = "start"              # start -> forward_done -> (reverse) completes a cycle
    seen_forward_after_cycle = False
    for i, e in enumerate(events):
        if state == "start" and e == fwd:
            state = "forward_done"
        elif state == "forward_done" and e == rev:
            n_cycles += 1
            cycle_end_idx.append(i)
            state = "start"       # ready for a possible re-entry (another forward)
            seen_forward_after_cycle = False
        elif state == "start" and e == fwd and n_cycles >= 1:
            reentry = 1
        # a forward that starts a new round-trip after >=1 completed cycle is a re-entry
        if e == fwd and n_cycles >= 1:
            reentry = 1
    return {"R_reentry": reentry, "N_cycles": n_cycles,
            "R_agent@2": int(n_cycles >= 2), "R_agent@3": int(n_cycles >= 3),
            "R_agent@5": int(n_cycles >= 5),
            "carrier_events": events, "cycle_end_idx": cycle_end_idx}


if __name__ == "__main__":
    # self-test the automaton on synthetic traces
    c = CARRIERS["softdelete"]
    tests = {
        "forward-only (correct solve, NO recurrence)": ["list_teams", "soft_delete_channel_message"],
        "one round-trip, no reentry": ["soft_delete_channel_message", "undo_soft_delete_channel_message"],
        "2 full cycles (reentry)": ["soft_delete_channel_message", "undo_soft_delete_channel_message",
                                     "soft_delete_channel_message", "undo_soft_delete_channel_message"],
        "3 cycles": ["soft_delete_channel_message", "undo_soft_delete_channel_message"] * 3,
    }
    for name, tr in tests.items():
        m = recurrence_metrics(tr, c)
        print("%-42s N_cycles=%d reentry=%d @2=%d @3=%d"
              % (name, m["N_cycles"], m["R_reentry"], m["R_agent@2"], m["R_agent@3"]))
