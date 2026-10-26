"""State-transition analysis layer (the gate between tool-cycle CANDIDATES and task synthesis).

A tool-call cycle is ONLY a candidate. This layer checks the OFFLINE, environment-level NECESSARY
conditions for state-recurrent non-progress. It cannot decide whether the real agent will loop —
that is S_agent, observable only by running the agent (SustainedRecurrence@k). So:

  offline (here)  = NECESSARY conditions, computed from measured Γ/Δ (+ a verifier spec for Φ)
  online (run)    = SUFFICIENT / decisive: does the agent actually re-enter and not self-terminate

Two independent recurrence mechanisms are checked:
  1. tool-level state recurrence   — α(F_C(S)) ≈ α(S) from measured Δ alone (catches reversible
                                     pairs; benign monotone tools yield none, as measured).
  2. constraint interference       — Φ-flatness: a benign-tool cycle where advancing one verifier
                                     clause writes an object attribute another clause reads
                                     (mutual coupling). NECESSARY for "no progress". Needs a
                                     verifier spec (produced later by task synthesis / the LLM);
                                     here we only DETECT the structural coupling from measured
                                     write-sets — we do not assert an attack.

Nothing here is hand-authored: TOOL_WRITES is read off measured_motifs.json; the cycle semantics
come from recurrence_search's measured WRITERS. A verifier spec is an INPUT, never baked in.
"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recurrence_search as R   # measured WRITERS + F_C composition + alpha check


def tool_writes():
    """measured (table[.column]) write-set per tool, straight from measured_motifs.json."""
    d = json.load(open("measured_motifs.json"))
    out = {}
    for t, m in d.items():
        if not m.get("success"):
            continue
        w = set()
        for tbl, v in (m.get("delta_rowcount") or {}).items():
            if v["after"] > v["before"]:
                w.add(tbl)                                  # row-level create
        for tbl, cols in (m.get("delta_columns") or {}).items():
            for c in cols:
                if c in ("last_modified_datetime", "updated_at"):
                    continue
                w.add("%s.%s" % (tbl, c))
        out[t] = w
    return out


TOOL_WRITES = tool_writes()


# ---------------------------------------------------------------- mechanism 1: tool-level recurrence
def analyze_cycle(cycle):
    """Offline necessary conditions for a tool-cycle from measured Δ alone.
    Returns re-entry + alpha-recurrence (α(F_C(S))≈α(S)) using recurrence_search's measured net_effect."""
    hard, cond, minted = R.net_effect(cycle)
    alpha_recurs = (not hard) and (not minted)             # abstract state returns, nothing minted
    # re-entry: the composed effect must re-satisfy the entry guard (Γ_C(F_C)=1). For a pure toggle
    # pair this holds; net_effect's `hard` already flags a seed literal left at the wrong value.
    reentry = not hard
    return {"alpha_recurs": alpha_recurs, "reentry": reentry,
            "minted_objects": minted, "conditional_literals": cond}


def tool_level_candidates(writers=None):
    """All measured tool-cycles that pass mechanism-1 (state-recurrent, nothing minted)."""
    W = writers if writers is not None else R.WRITERS
    old = R.WRITERS
    R.WRITERS = W
    E = R.build_H()
    cyc = R.simple_cycles(set(W), set(E))
    passed = [c for c in cyc if analyze_cycle(c)["alpha_recurs"]]
    R.WRITERS = old
    return passed, len(E), len(cyc)


# ---------------------------------------------------------------- mechanism 2: constraint interference
# A verifier spec (INPUT, from task synthesis / LLM) is a list of clauses; each clause names the
# object ATTRIBUTES it reads and the tool that ADVANCES it. Interference = advancing one clause
# writes an attribute another clause reads.
#   clause = {"id": "V1", "reads": ["channels.description", "teams_channel_tabs"],
#             "advanced_by": "update_channel"}
def interference(verifier_spec):
    """Detect mutual coupling between verifier clauses via MEASURED tool write-sets.
    Returns the coupling edges (clause_i advanced by tool that writes an attr clause_j reads) and
    whether a mutual (i<->j) coupling exists — the NECESSARY structural condition for Φ-flatness.
    Does NOT prove absence of a joint fixed point (that needs semantics / the real run)."""
    clauses = {c["id"]: c for c in verifier_spec}
    edges = []                                             # (advancing_clause, tool, broken_clause, shared_attr)
    for ci in clauses.values():
        tool = ci.get("advanced_by")
        writes = TOOL_WRITES.get(tool, set())
        for cj in clauses.values():
            if cj["id"] == ci["id"]:
                continue
            shared = writes & set(cj.get("reads", []))
            for a in shared:
                edges.append((ci["id"], tool, cj["id"], a))
    # mutual coupling: exists i,j with i->j and j->i
    pair = collections.defaultdict(set)
    for a, _, b, _ in edges:
        pair[a].add(b)
    mutual = [(i, j) for i in pair for j in pair[i] if i < j and i in pair.get(j, set())]
    return {"coupling_edges": edges, "mutual_pairs": mutual,
            "interference": bool(mutual)}


if __name__ == "__main__":
    print("=== mechanism 1: tool-level state recurrence (measured Δ, offline) ===")
    BENIGN_EXCLUDE = {"soft_delete_channel_message", "undo_soft_delete_channel_message"}
    benign = {k: v for k, v in R.WRITERS.items() if k not in BENIGN_EXCLUDE}
    for label, W in [("benign-only", benign), ("all(+reversible)", R.WRITERS)]:
        passed, ne, nc = tool_level_candidates(W)
        print("  %-18s edges=%2d cycles=%2d  state-recurrent candidates=%d %s"
              % (label, ne, nc, len(passed), [list(c) for c in passed]))

    print("\n=== mechanism 2: constraint interference (needs a verifier spec INPUT) ===")
    print("  (spec is produced later by task synthesis / the LLM; shown here on a sample input to")
    print("   validate the detector against MEASURED write-sets — not an asserted attack)")
    sample = json.loads(os.environ.get("SPEC", "[]"))
    if sample:
        r = interference(sample)
        for e in r["coupling_edges"]:
            print("    %s --(%s writes %s)--> breaks %s" % (e[0], e[1], e[3], e[2]))
        print("  mutual interference: %s  pairs=%s" % (r["interference"], r["mutual_pairs"]))
    else:
        print("  (no SPEC given; pass SPEC='[{...}]' to exercise the detector)")
