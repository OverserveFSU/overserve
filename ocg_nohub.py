"""Rerun the provenance graph with HUB objects removed.

`team_techcorp_001` appears in 93% of all Team bindings and in nearly every trace: any cycle that
closes through it closes trivially. A hub is an object id bound in >HUB_FRAC of traces; edges
carried only by hub objects are dropped, which is the object-identity ablation motif_attack.md
asks for, run in the strict direction.
"""
import glob, os, collections
import ocg_motif as M

HUB_FRAC = 0.5

files = sorted(glob.glob(os.path.join(M.RESULTS, "*/baseline/**/results_*.json"), recursive=True))
traces = [t for t in (M.load_trace(f) for f in files) if t and t["pass_rate"] == 1.0]
N = len(traces)

seen = collections.defaultdict(set)
for t in traces:
    for e in t["events"]:
        for o in e["consumed"] | e["produced"]:
            seen[o].add(t["file"])
HUB = {o for o, s in seen.items() if len(s) > HUB_FRAC * N}
print("traces=%d   hub objects (bound in >%d%% of traces): %s" % (N, HUB_FRAC * 100, sorted(HUB)))

edge_sup = collections.defaultdict(collections.Counter)
edge_obj = collections.defaultdict(collections.Counter)
for t in traces:
    ev = t["events"]
    for k, y in enumerate(ev):
        for o in y["consumed"]:
            if o in HUB:
                continue                                  # drop hub-carried dependencies
            for x in reversed(ev[:k]):
                if x["turn"] == y["turn"]:
                    continue
                if o in x["produced"] or o in x["consumed"]:
                    edge_sup[(x["label"], y["label"], o[0])][t["file"]] += 1
                    edge_obj[(x["label"], y["label"], o[0])][o[1]] += 1
                    break

print("\nprovenance edges after hub removal: %d (was 54)" % len(edge_sup))
adj = collections.defaultdict(set)
for (a, b, ot) in edge_sup:
    if a != b:
        adj[a].add((b, ot))

def cycles(max_len=5):
    out = {}
    for start in sorted(adj):
        stack = [(start, [start], [])]
        while stack:
            cur, path, ots = stack.pop()
            for (nxt, ot) in adj.get(cur, ()):
                if nxt == start and len(path) >= 2:
                    out.setdefault(tuple(path), set()).add(tuple(ots + [ot]))
                elif nxt not in path and len(path) < max_len and nxt > start:
                    stack.append((nxt, path + [nxt], ots + [ot]))
    return out

cy = cycles()
print("cycles after hub removal: %d distinct node-paths" % len(cy))
for path, otsets in sorted(cy.items(), key=lambda kv: len(kv[0])):
    for ots in sorted(otsets):
        edges = list(zip(path, path[1:] + path[:1]))
        sup = [edge_sup[(a, b, ot)] for (a, b), ot in zip(edges, ots)]
        objs = [set(edge_obj[(a, b, ot)]) for (a, b), ot in zip(edges, ots)]
        uni = set.intersection(*objs) if objs else set()
        intra = set.intersection(*[set(s) for s in sup])
        print("\n  %s -> %s   types=%s" % (" -> ".join(path), path[0], list(ots)))
        print("    per-edge trace support: %s" % [len(s) for s in sup])
        print("    single-trace occurrence: %s | object unification: %s %s"
              % (bool(intra), bool(uni), sorted(uni)[:2]))

# self-loops are dropped above; report them separately, they matter for recurrence
print("\n=== self-loops (same label consuming its own prior output), hub-free ===")
for (a, b, ot), c in sorted(edge_sup.items(), key=lambda kv: -len(kv[1])):
    if a == b:
        print("  %-22s -%s->  %d traces, %d occ, %d distinct objects"
              % (a, ot, len(c), sum(c.values()), len(edge_obj[(a, b, ot)])))
