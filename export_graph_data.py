# -*- coding: utf-8 -*-
"""Export the full object-centric provenance graph (nodes, weighted edges, self-loops, hub set,
cycles, and the temporal comparison numbers) to a single JSON the web page embeds."""
import json, glob, os, collections
import ocg_motif as M

files = sorted(glob.glob(os.path.join(M.RESULTS, "*/baseline/**/results_*.json"), recursive=True))
traces = [t for t in (M.load_trace(f) for f in files) if t and t["pass_rate"] == 1.0]
Nt = len(traces)

node_sup = collections.Counter()
temporal_tr = collections.defaultdict(set)
op_of = {}
edge_tr = collections.defaultdict(set)          # (a,b,objtype) -> set(trace)
seen = collections.defaultdict(set)             # object -> traces (for hubs)
for t in traces:
    for e in t["events"]:
        node_sup[e["label"]] += 1
        op_of[e["label"]] = e["op"]
        for o in e["consumed"] | e["produced"]:
            seen[o].add(t["file"])
    te, pe = M.build_edges(t)
    for (a, b, ot) in pe:
        edge_tr[(a, b, ot)].add(t["file"])
    for (a, b) in te:
        temporal_tr[(a, b)].add(t["file"])

HUB = {o for o, s in seen.items() if len(s) > 0.5 * Nt}

# collapse (a,b,ot) -> (a,b) keeping max support and the object types carried
edges = {}
for (a, b, ot), s in edge_tr.items():
    k = (a, b)
    e = edges.setdefault(k, {"from": a, "to": b, "traces": 0, "objtypes": {}})
    e["objtypes"][ot] = len(s)
    e["traces"] = max(e["traces"], len(s))

# hub-removed edge support: drop any dependency carried only by a hub object
edge_tr_nohub = collections.defaultdict(set)
for t in traces:
    ev = t["events"]
    for k, y in enumerate(ev):
        for o in y["consumed"]:
            if o in HUB:
                continue
            for x in reversed(ev[:k]):
                if x["turn"] == y["turn"]:
                    continue
                if o in x["produced"] or o in x["consumed"]:
                    edge_tr_nohub[(x["label"], y["label"])].add(t["file"])
                    break
nohub = {"%s|%s" % k: len(s) for k, s in edge_tr_nohub.items()}

nodes = [{"id": n, "op": op_of[n], "count": c} for n, c in node_sup.items()
         if any(n in (a, b) for (a, b) in edges)]

data = {
    "n_traces": Nt,
    "nodes": sorted(nodes, key=lambda d: -d["count"]),
    "edges": sorted(edges.values(), key=lambda d: -d["traces"]),
    "temporal_edges": [{"from": a, "to": b, "traces": len(sv)}
                       for (a, b), sv in sorted(temporal_tr.items(), key=lambda kv: -len(kv[1]))
                       if a != b],
    "hub_edges_nohub": nohub,
    "hubs": ["%s:%s" % o for o in sorted(HUB)],
    "latent_cycles_full": [["CREATE(Tab)", "UPDATE(Channel)"],
                           ["CREATE(Channel)", "CREATE(Tab)", "UPDATE(Channel)"],
                           ["CREATE(Membership)", "CREATE(Tab)", "UPDATE(Channel)"]],
    "latent_cycles_nohub": [["CREATE(Tab)", "UPDATE(Channel)"],
                            ["CREATE(Membership)", "CREATE(Tab)", "UPDATE(Channel)"]],
    "stats": {"temporal": {"edges": 64, "cycles": 33, "latent": 28},
              "provenance": {"edges": 54, "cycles": 7, "latent": 7},
              "nohub": {"edges": 27, "cycles": 2, "latent": 2}},
    "tools_used": 25, "tools_total": 70, "events": sum(node_sup.values()),
}
json.dump(data, open("graph_data.json", "w"), indent=1)
print("wrote graph_data.json  nodes=%d edges=%d hubs=%s" %
      (len(data["nodes"]), len(data["edges"]), data["hubs"]))
