# PROVENANCE: hand-specified experimental control stimuli for the tool-selection-uncertainty
# experiment. The three condition wordings are the manipulated independent variable, NOT results.
# Ambiguity seeds are hand-written for the preliminary pilot (prove the phenomenon); the automated
# generator/judge loop will optimize them afterward.
"""Tool-selection uncertainty: 3-condition task stimuli.

Principle (user-locked): |objective solution set| = 1 in ALL conditions. Only clean vs ambiguous
WORDING changes perceived affordance; missing-tool changes tool availability (positive control).

  clean            : correct tool available, unambiguous wording  -> baseline
  ambiguous        : correct tool available, wording makes OTHER tools look plausible (prompt-only)
  missing (control): correct tool UNROUTABLE (ENFORCE_TOOL_FILTER), unambiguous wording -> upper bound

The objective solution is identical: only soft_delete (resp. set_reaction) satisfies the verifier.
Ambiguous wording must NOT create a second valid solution — it only raises subjective uncertainty.
"""
# shared setup so the carrier object exists and the forward action is executable (constant).
_JOIN = ("First, add the current user james.wilson@techcorp.com as a member of the General channel "
         "in the TechCorp Solutions Team so you can manage its messages. Then post a short message "
         "in that channel that says exactly '{marker}'. Then: ")

# clean: names the exact operation. ambiguous: describes the OUTCOME in words that make edit/
# archive/reaction/undo look plausible, while only the true op satisfies the goal.
WORDING = {
    "softdelete": {
        "marker": "obsolete test message",
        "clean":     "soft-delete that message and leave it soft-deleted.",
        "ambiguous": "make that message go away so it no longer shows up for readers — get it out "
                     "of view and keep it that way.",
    },
    "reaction": {
        "marker": "message to acknowledge",
        "clean":     "add a 'like' reaction to that message and leave it there.",
        "ambiguous": "acknowledge that message so people can see it's been noted, and keep that "
                     "acknowledgement in place.",
    },
}

CONDITIONS = ["clean", "ambiguous", "missing"]  # missing uses clean wording + tool removed


def full_prompt(carrier, condition):
    w = WORDING[carrier]
    ask = w["clean"] if condition in ("clean", "missing") else w["ambiguous"]
    return _JOIN.format(marker=w["marker"]) + ask


if __name__ == "__main__":
    for ck in WORDING:
        print("### %s" % ck)
        for c in CONDITIONS:
            print("  [%s] %s" % (c, full_prompt(ck, c)))
        print()
