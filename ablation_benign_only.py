"""Ablation: how far is the benign-only motif library from admitting an executable recurrence?

md's setting mines motifs ONLY from successful benign traces. The benign corpus exercises 25 of
the gym's 70 tools. This adds back, one at a time, motifs the environment offers but no benign
trace used, and reports when H stops being acyclic.
"""
import collections
import motif_semantics as S
import recurrence_search as R
from motif_semantics import L

# tools present in the gym but absent from the 25-tool benign alphabet
UNSEEN = {
"add_team_member": {
    "op": "CREATE", "obj": "Membership",
    "guard":  [L("exists", "User", "?u"), L("exists", "Team", "?t"),
               L("teammember", "?u", "?t", neg=True)],
    "effect": [L("teammember", "?u", "?t")],
    "ev": {"guard": "observed-1x 'User not found'; schema-note 'Validate email and user existence'"}},
"delete_channel_tab": {
    "op": "DELETE", "obj": "Tab",
    "guard":  [L("exists", "Tab", "?tab")],
    "effect": [L("exists", "Tab", "?tab", neg=True)],
    "ev": {"effect": "schema-note 'Permanently removes tab'"}},
"soft_delete_channel_message": {
    "op": "DELETE", "obj": "Message",
    "guard":  [L("exists", "Message", "?m")],
    "effect": [L("exists", "Message", "?m", neg=True)],
    "ev": {"effect": "tool name / schema"}},
"undo_soft_delete_channel_message": {
    "op": "CREATE", "obj": "Message",
    "guard":  [L("exists", "Message", "?m", neg=True)],
    "effect": [L("exists", "Message", "?m")],
    "ev": {"effect": "tool name / schema"}},
}


def report(extra_names):
    S.MOTIFS.update({k: UNSEEN[k] for k in extra_names})
    R.WRITERS = {k: v for k, v in S.MOTIFS.items() if v["guard"] or v["effect"]}
    E = R.build_H()
    cyc = R.simple_cycles(set(R.WRITERS), set(E))
    ex = []
    for c in cyc:
        hard, cond, fresh = R.net_effect(c)
        if not hard and not fresh:
            ex.append((c, bool(cond)))
    return E, cyc, ex


base_writers = dict(R.WRITERS)
print("%-46s %6s %6s %6s" % ("MOTIF LIBRARY", "edges", "cycles", "exec"))
E, c, x = report([])
print("%-46s %6d %6d %6d" % ("benign-only (25-tool alphabet)", len(E), len(c), len(x)))

for name in UNSEEN:
    S.MOTIFS.clear(); S.MOTIFS.update(base_writers)
    for r in S.READS: S.MOTIFS.setdefault(r, {"op": "READ", "guard": [], "effect": [], "ev": {}})
    E, c, x = report([name])
    print("%-46s %6d %6d %6d" % ("  + " + name, len(E), len(c), len(x)))
    for cc, k in x:
        print("      EXECUTABLE%s: %s" % (" (conditional)" if k else "",
                                          " -> ".join(cc) + " -> " + cc[0]))

S.MOTIFS.clear(); S.MOTIFS.update(base_writers)
for r in S.READS: S.MOTIFS.setdefault(r, {"op": "READ", "guard": [], "effect": [], "ev": {}})
E, c, x = report(list(UNSEEN))
print("%-46s %6d %6d %6d" % ("  + all four unseen motifs", len(E), len(c), len(x)))
for cc, k in x:
    print("      EXECUTABLE%s: %s" % (" (conditional)" if k else "",
                                      " -> ".join(cc) + " -> " + cc[0]))
