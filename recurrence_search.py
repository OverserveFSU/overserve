"""Motif Compatibility Graph + Recurrent Cycle Search + Executability Checking
(motif_attack.md steps 3-5).

Edge rule (md):   (M_i,M_j) in E  iff  exists theta:
                  TypeCompatible ^ Delta_i |= theta(Gamma_j) ^ ObjectConsistent ^ TemporalConsistent
NOT "they shared an object", which is the statistical version md explicitly says to upgrade from.

Executable recurrence (md):  exists s:  Gamma_C(s) ^ alpha(F_C(s)) = alpha(s)
The abstraction alpha keeps existence/relation/status literals and ignores attribute VALUES
(so attr(c,description) is idempotent under alpha, an object created inside the cycle is not).
"""
import os, itertools, collections, json

# Phase 0c: source the motif guard/effect literals from MEASUREMENT (measured_writers.json,
# produced by build_writers.py from gym state-diff + observed isError) instead of the hand-authored
# motif_semantics.py. The literal shape is [pred, [args], polarity] in JSON; convert to the tuples
# (pred, (args...), bool) that unify() expects. Set MOTIF_SOURCE=hand to compare against the old
# hand-authored table.
_SRC = os.environ.get("MOTIF_SOURCE", "measured")


def fmt(lit):
    p, a, pos = lit
    return ("" if pos else "!") + "%s(%s)" % (p, ",".join(map(str, a)))


def _load_measured(path="measured_writers.json"):
    raw = json.load(open(path))
    out = {}
    for tool, w in raw.items():
        g = [(l[0], tuple(l[1]), bool(l[2])) for l in w.get("guard", [])]
        e = [(l[0], tuple(l[1]), bool(l[2])) for l in w.get("effect", [])]
        out[tool] = {"op": w.get("op"), "guard": g, "effect": e, "ev": w.get("evidence", {})}
    return out


if _SRC == "hand":
    from motif_semantics import MOTIFS
    SRC_MOTIFS = MOTIFS
else:
    SRC_MOTIFS = _load_measured()

WRITERS = {k: v for k, v in SRC_MOTIFS.items() if v["guard"] or v["effect"]}


def unify(lit_a, lit_b, sub):
    """Unify two literals (same predicate, arity, polarity) extending substitution `sub`."""
    pa, aa, sa = lit_a
    pb, ab, sb = lit_b
    if pa != pb or len(aa) != len(ab) or sa != sb:
        return None
    s = dict(sub)
    for x, y in zip(aa, ab):
        vx, vy = str(x).startswith("?"), str(y).startswith("?")
        if vx and vy:
            if s.get(x, y) != y and s.get(y, x) != x:
                return None
            s[x] = y
        elif vx:
            if s.get(x, y) != y: return None
            s[x] = y
        elif vy:
            if s.get(y, x) != x: return None
            s[y] = x
        elif x != y:
            return None
    return s


def entails(delta, gamma):
    """Delta |= theta(Gamma): some guard literal is ESTABLISHED by an effect literal, and no
    guard literal is CONTRADICTED by one. Returns theta or None."""
    for eff in delta:
        for g in gamma:
            s = unify(eff, g, {})
            if s is None:
                continue
            # contradiction check under this theta
            bad = False
            for e2 in delta:
                for g2 in gamma:
                    if e2[0] == g2[0] and e2[2] != g2[2] and unify((e2[0], e2[1], True),
                                                                  (g2[0], g2[1], True), s):
                        bad = True
            if not bad:
                return s
    return None


def build_H():
    E = {}
    for i, mi in WRITERS.items():
        for j, mj in WRITERS.items():
            th = entails(mi["effect"], mj["guard"])
            if th is not None:
                E[(i, j)] = th
    return E


def net_effect(cycle):
    """alpha(F_C(s)) vs alpha(s): seed the state from the FIRST motif's guard (the entry
    condition Gamma_C), apply each Delta in cycle order, then compare against that seed.
    Returns (changed_literals, minted_objects); both empty == alpha-identity.

    Comparing "what is still asserted at the end" instead of "what CHANGED" is wrong: a
    delete/undo pair ends with the literal asserted, exactly as it started, and is identity.
    """
    state, minted = {}, []
    for (p, a, pos) in WRITERS[cycle[0]]["guard"]:          # alpha(s): the entry state
        if p != "attr":
            state[(p, a)] = pos
    seed = dict(state)
    for name in cycle:
        m = WRITERS[name]
        # An object is MINTED (monotone) only if its variable is unconstrained by the motif's
        # own guard: create_channel binds ?c in the effect alone -> a fresh channel each pass,
        # whereas undo_soft_delete guards on !exists(?m) and merely RESTORES an existing one.
        guarded = {x for (_, ga, _) in m["guard"] for x in ga}
        for (p, a, pos) in m["effect"]:
            if p == "attr":
                continue                      # alpha ignores attribute values -> idempotent
            if p == "exists" and pos and not (set(a) & guarded):
                minted.append((p, a))
            state[(p, a)] = pos
    # A literal in the seed that ends at a different value is a HARD violation of
    # alpha(F_C(s))=alpha(s). A literal the cycle touches that the entry condition never
    # constrained is only a CONDITIONAL violation: the pass is identity exactly when that
    # literal already held the value the cycle leaves it at (e.g. remove_team_member cascades
    # !member(u,c); harmless if u held no channel membership, monotone stripping if it did).
    hard = {k: v for k, v in state.items() if k in seed and seed[k] != v}
    cond = {k: v for k, v in state.items() if k not in seed}
    return hard, cond, minted


def simple_cycles(nodes, edges, max_len=4):
    adj = collections.defaultdict(set)
    for (a, b) in edges:
        if a != b:
            adj[a].add(b)
    out = set()
    for start in sorted(nodes):
        stack = [(start, [start])]
        while stack:
            cur, path = stack.pop()
            for nxt in adj.get(cur, ()):
                if nxt == start and len(path) >= 2:
                    out.add(tuple(path))
                elif nxt not in path and len(path) < max_len and nxt > start:
                    stack.append((nxt, path + [nxt]))
    return out


if __name__ == "__main__":
    E = build_H()
    print("=== Motif Compatibility Graph H ===")
    print("%d writer motifs, %d edges satisfying  Delta_i |= theta(Gamma_j)\n" % (len(WRITERS), len(E)))
    for (a, b), th in sorted(E.items()):
        print("  %-30s -> %-30s  theta=%s" % (a, b, {k: v for k, v in th.items()} or "{}"))

    # ---- self-loops: is a motif re-enterable on the SAME object binding?
    print("\n=== re-entrancy of each motif on its own object (Delta_i |= Gamma_i ?) ===")
    for i, m in WRITERS.items():
        if not m["guard"]:
            continue
        blocked = []
        for (p, a, pos) in m["effect"]:
            for (gp, ga, gpos) in m["guard"]:
                if p == gp and pos != gpos and unify((p, a, True), (gp, ga, True), {}) is not None:
                    blocked.append("%s vs %s" % (fmt((p, a, pos)), fmt((gp, ga, gpos))))
        print("  %-30s %s" % (i, ("SELF-BLOCKING: " + "; ".join(blocked)) if blocked
                              else "re-enterable on same binding"))

    # ---- cycles + executability
    cyc = simple_cycles(set(WRITERS), set(E))
    print("\n=== cycles in H (len<=4): %d ===" % len(cyc))
    execu = []
    for c in sorted(cyc, key=len):
        hard, cond, fresh = net_effect(c)
        ident = not hard and not fresh
        print("\n  %s -> %s" % (" -> ".join(c), c[0]))
        print("    seed literals changed (hard): %s" % (
            ", ".join(fmt((p, a, v)) for (p, a), v in hard.items()) or "(none)"))
        print("    unconstrained literals touched (conditional): %s" % (
            ", ".join(fmt((p, a, v)) for (p, a), v in cond.items()) or "(none)"))
        print("    objects minted in cycle: %s" % (
            ", ".join("%s%s" % (p, a) for (p, a) in fresh) or "(none)"))
        print("    alpha(F_C(s)) == alpha(s) ?  %s%s" % (
            ident, "  (conditional on the literals above)" if ident and cond else ""))
        if ident:
            execu.append((c, bool(cond)))
    print("\n=== EXECUTABLE RECURRENCE CANDIDATES: %d ===" % len(execu))
    for c, conditional in execu:
        print("   %-62s %s" % (" -> ".join(c) + " -> " + c[0],
                               "CONDITIONAL" if conditional else "UNCONDITIONAL"))
    json.dump({"edges": [list(k) for k in E], "cycles": [list(c) for c in cyc],
               "executable": [{"cycle": list(c), "conditional": k} for c, k in execu]},
              open("recurrence_search.json", "w"), indent=1)
