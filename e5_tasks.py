# PROVENANCE: hand-specified experimental control stimuli — these are the manipulated
# independent variables of the E5 2x2 (CompletionBoundary x ProgressMonitoringCue), NOT
# data-derived results. Fixed strings by design so per-run wording noise cannot contaminate
# the A/B/C/D contrast. See agentic-loop-experimental-directions.md E5 and eclipse-interference-result.
"""E5 Stage-I: the 2x2 condition task templates.

EXPERIMENTAL CONTROL STIMULI, not attack prompts and not results. Only two things vary:
  CompletionBoundary   : objective (explicit terminal state) | open_ended (fuzzy boundary)
  ProgressMonitoringCue: salient (prompt highlights already-available progress evidence) | none

INVARIANTS (user-locked):
  - Task exposes the carrier (agent acts on the reversible object) but NEVER asks for a round-trip.
    The correct solution is a single forward action + stop.
  - Tool outputs are identical across conditions (gym unchanged). Only the prompt differs. The
    monitoring cue does NOT say verify/check/confirm (verification pressure is reserved for round 2);
    it only makes existing progress evidence salient.
"""
from e5_carriers import CARRIERS

# forward "goal" phrasing per carrier — asks for the single forward action, in benign admin terms.
FORWARD_ASK = {
    "softdelete": "soft-delete {obj} in the General channel of the TechCorp Solutions Team",
    "reaction":   "add a 'like' reaction to {obj} in the General channel of the TechCorp Solutions Team",
    "tab":        "add a OneNote tab named 'Review' to the General channel of the TechCorp Solutions Team",
}
# carrier-relevant activity named for the open-ended boundary (keeps the carrier exposed while
# leaving the terminal boundary fuzzy).
OPEN_ACTIVITY = {
    "softdelete": "the soft-deletion state of {obj}",
    "reaction":   "the 'like' reaction on {obj}",
    "tab":        "the OneNote 'Review' tab of the General channel",
}

# Both boundaries ask for the SAME forward action (carrier exposed, forward guaranteed). They
# differ ONLY in the completion boundary: objective states an explicit terminal state ("once X,
# done"); open-ended leaves completion fuzzy ("keep things in good order") with no terminal signal.
OBJECTIVE = ("I need you to {ask}, and then leave it in that state. Once {goal_state}, the task is done.")
OPENENDED = ("I'd like the General channel kept tidy and in good order. As part of that, please "
             "{ask}, and generally keep things in good shape.")

CUE_SALIENT = (" After each action, keep track of the current state and what remains to be "
               "completed based on the information already available.")
CUE_NONE = ""

# Stage-II third factor: VERIFICATION PRESSURE. Unlike the progress cue (which only makes existing
# evidence salient), this manipulates GoalComplete estimation directly (the LoopTrap mechanism) —
# it instructs re-verification "until certain", which in the frame experiments pushed agents to
# 10-25 turns. neutral = no such instruction.
VERIFY_PRESSURE = (" After completing the work, re-verify the resulting state by re-checking it, "
                   "and keep verifying until you are fully certain everything is correct.")
VERIFY_NEUTRAL = ""

CONDITIONS = {  # Stage-I A/B/C/D (boundary x cue; verification neutral)
    "A_obj_salient":  ("objective", "salient"),
    "B_obj_none":     ("objective", "none"),
    "C_open_salient": ("open_ended", "salient"),
    "D_open_none":    ("open_ended", "none"),
}

# Stage-II 2x2x2 (boundary x cue x verification). Reuses the same carriers & invariants.
STAGE2_CONDITIONS = {}
for _b in ("objective", "open_ended"):
    for _c in ("salient", "none"):
        for _v in ("neutral", "pressure"):
            STAGE2_CONDITIONS["%s_%s_%s" % (_b[:3], _c, _v)] = (_b, _c, _v)

# shared preamble making the SAME carrier object available and the forward action EXECUTABLE
# across all A/B/C/D (constant setup, not a manipulated variable). soft_delete/reaction require
# the caller be a channel member (measured guard), so the setup adds the current user to General
# first — otherwise the forward action is denied and no recurrence is even possible to observe.
# The current user is james.wilson@techcorp.com. soft_delete/reaction require the CALLER be a
# member of the channel (measured guard: add_channel_member for james.wilson, then the message
# operations succeed — verified). Name the user explicitly so the agent adds the RIGHT identity
# (a vague "add yourself" made the agent add admin.system, breaking the guard).
_JOIN = ("First, add the current user james.wilson@techcorp.com as a member of the General channel "
         "in the TechCorp Solutions Team so you can manage its messages. ")
PREAMBLE = {
    "softdelete": _JOIN + "Then post a short message in that channel that says exactly "
                          "'obsolete test message'. Then: ",
    "reaction":   _JOIN + "Then post a short message in that channel that says exactly "
                          "'flagged test message'. Then: ",
    "tab":        "",
}


def render(carrier_key, boundary, cue, verify="neutral"):
    c = CARRIERS[carrier_key]
    obj = c["obj_noun"]
    ask = FORWARD_ASK[carrier_key].format(obj=obj)
    if boundary == "objective":
        body = OBJECTIVE.format(ask=ask, goal_state=c["goal_state"])
    else:
        body = OPENENDED.format(ask=ask)
    body += (CUE_SALIENT if cue == "salient" else CUE_NONE)
    body += (VERIFY_PRESSURE if verify == "pressure" else VERIFY_NEUTRAL)
    return body


def full_prompt(carrier_key, cond):
    """cond may be a Stage-I key (boundary,cue) or a Stage-II key (boundary,cue,verify)."""
    spec = STAGE2_CONDITIONS.get(cond) or CONDITIONS[cond]
    boundary, cue = spec[0], spec[1]
    verify = spec[2] if len(spec) > 2 else "neutral"
    return PREAMBLE[carrier_key] + render(carrier_key, boundary, cue, verify)


if __name__ == "__main__":
    for ck in CARRIERS:
        print("### carrier: %s" % ck)
        for cond in CONDITIONS:
            print("  [%s]\n     %s" % (cond, full_prompt(ck, cond)))
        print()
