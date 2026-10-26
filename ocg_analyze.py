"""Second pass: edge support, cross-trace composition evidence, object-binding consistency,
and length-2/3 motif table. Answers: are the latent provenance cycles genuinely COMPOSED from
fragments in different benign traces, and do they close over a consistent object?"""
import json, glob, os, collections, itertools
import ocg_motif as M

files = sorted(glob.glob(os.path.join(M.RESULTS, "*/baseline/**/results_*.json"), recursive=True))
traces = [t for t in (M.load_trace(f) for f in files) if t and t["pass_rate"] == 1.0]

# ---- edge -> {trace: count}, and the concrete object ids that carry it
edge_sup = collections.defaultdict(collections.Counter)   # (a,b,type) -> Counter(trace)
edge_obj = collections.defaultdict(collections.Counter)   # (a,b,type) -> Counter(object id)
node_sup = collections.Counter()
tool_of  = collections.defaultdict(collections.Counter)   # label -> Counter(tool)

for t in traces:
    ev = t["events"]
    for e in ev:
        node_sup[e["label"]] += 1
        tool_of[e["label"]][e["tool"]] += 1
    for k, y in enumerate(ev):
        for (ot, oid) in y["consumed"]:
            for x in reversed(ev[:k]):
                if x["turn"] == y["turn"]:
                    continue
                if (ot, oid) in x["produced"] or (ot, oid) in x["consumed"]:
                    key = (x["label"], y["label"], ot)
                    edge_sup[key][t["file"]] += 1
                    edge_obj[key][oid] += 1
                    break

print("=== node labels (%d) ===" % len(node_sup))
for lab, n in node_sup.most_common():
    print("  %-22s %4d   tools: %s" % (lab, n, ",".join(k for k, _ in tool_of[lab].most_common(3))))

print("\n=== length-2 motifs = provenance edges, by trace support ===")
print("  %-22s %-22s %-11s %5s %5s" % ("FROM", "TO", "SHARED", "#tr", "#occ"))
rows = sorted(edge_sup.items(), key=lambda kv: -len(kv[1]))
for (a, b, ot), c in rows:
    print("  %-22s %-22s %-11s %5d %5d" % (a, b, ot, len(c), sum(c.values())))

# ---- typed cycles with object-binding consistency
adj = collections.defaultdict(set)
for (a, b, ot) in edge_sup:
    if a != b:
        adj[a].add((b, ot))

def typed_cycles(max_len=4):
    out = {}
    for start in sorted(adj):
        stack = [(start, [start], [])]
        while stack:
            cur, path, ots = stack.pop()
            for (nxt, ot) in adj.get(cur, ()):
                if nxt == start and len(path) >= 2:
                    key = tuple(path); out.setdefault(key, []).append(tuple(ots + [ot]))
                elif nxt not in path and len(path) < max_len and nxt > start:
                    stack.append((nxt, path + [nxt], ots + [ot]))
    return out

cyc = typed_cycles()
print("\n=== provenance cycles: composition evidence ===")
for path, otsets in sorted(cyc.items(), key=lambda kv: len(kv[0])):
    edges = list(zip(path, path[1:] + path[:1]))
    for ots in sorted(set(otsets)):
        supports = [edge_sup[(a, b, ot)] for (a, b), ot in zip(edges, ots)]
        trs = [set(s) for s in supports]
        shared_all = set.intersection(*trs) if trs else set()
        union = set().union(*trs) if trs else set()
        # object unification: is there ONE object id carrying every edge of the cycle?
        objsets = [set(edge_obj[(a, b, ot)]) for (a, b), ot in zip(edges, ots)]
        uni = set.intersection(*objsets) if objsets else set()
        print("\n  " + " -> ".join(path) + " -> " + path[0])
        print("    shared-object types along cycle: %s" % list(ots))
        for ((a, b), ot), s in zip(zip(edges, ots), supports):
            print("      %-22s -%s-> %-22s  %d traces" % (a, ot, b, len(s)))
        print("    在同一条 trace 里同时出现全部边: %s (%d 条)" % (bool(shared_all), len(shared_all)))
        print("    贡献 trace 总数(并集): %d  => %s" % (
            len(union), "跨 trace 组合" if not shared_all else "单条 trace 内已存在"))
        print("    能被同一个具体对象贯穿(object unification): %s%s" % (
            bool(uni), (" e.g. %s" % list(uni)[:2]) if uni else ""))
