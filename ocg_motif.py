"""Object-centric typed execution graph + motif mining over BENIGN EOG traces.

Reads only `*/baseline/**/results_*.json` (unmodified prompts) so the motif library is not
contaminated by attack-induced behaviour.

Two graph variants are built per trace, to separate the two claims motif_attack.md distinguishes:
  * temporal  -- naive directly-follows over turn order (ignores object identity)
  * provenance-- edge only when the consumer binds an object the producer created/observed

The population graph merges per-trace graphs; latent cycles are cycles present in the merged
graph but in no single trace.
"""
import os, sys, json, glob, re, itertools, collections

RESULTS = "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/results"

# ---------------------------------------------------------------- tool schema
# tool -> (operation, primary object type produced/acted on)
TOOL_OP = {
    "list_teams": ("READ", "Team"), "list_channels": ("READ", "Channel"),
    "list_users": ("READ", "User"), "list_groups": ("READ", "Group"),
    "list_teams_apps": ("READ", "App"), "list_team_members": ("READ", "Membership"),
    "list_call_records": ("READ", "CallRecord"), "get_call_record": ("READ", "CallRecord"),
    "create_channel": ("CREATE", "Channel"), "create_chat": ("CREATE", "Chat"),
    "create_teamwork_tag": ("CREATE", "Tag"), "create_user": ("CREATE", "User"),
    "create_call": ("CREATE", "Call"), "create_virtual_event_webinar": ("CREATE", "Webinar"),
    "add_tabs_to_channels": ("CREATE", "Tab"), "add_channel_member": ("CREATE", "Membership"),
    "send_channel_message": ("SEND", "Message"), "send_chat_message": ("SEND", "Message"),
    "update_channel": ("UPDATE", "Channel"), "update_group": ("UPDATE", "Group"),
    "update_user": ("UPDATE", "User"), "provision_channel_email": ("UPDATE", "Channel"),
    "archive_channel": ("UPDATE", "Channel"),
    "publish_virtual_event_webinar": ("UPDATE", "Webinar"),
    "remove_team_member": ("DELETE", "Membership"),
}
# argument key -> object type it binds
ARG_TYPE = {
    "teamid": "Team", "team_id": "Team", "channelid": "Channel", "chatid": "Chat",
    "userid": "User", "user_odata_bind": "User", "groupid": "Group",
    "webinar_id": "Webinar", "membershipid": "Membership",
    "teamsapp_odata_bind": "App",
}
# tool -> object type of the ids appearing in result value[]
LIST_TYPE = {"list_teams": "Team", "list_channels": "Channel", "list_users": "User",
             "list_groups": "Group", "list_teams_apps": "App",
             "list_team_members": "Membership", "list_call_records": "CallRecord"}


def _odata_id(v):
    """https://graph.microsoft.com/v1.0/users('bob.smith') -> bob.smith"""
    seg = v.rstrip("/").split("/")[-1]
    m = re.match(r"^\('?(.*?)'?\)$", seg)
    return m.group(1) if m else seg


def _payload(tr):
    """-> (parsed_json_or_None, raw_text, is_error)"""
    r = tr.get("result") or {}
    inner = r.get("result") or {}
    err = bool(inner.get("isError"))
    try:
        txt = inner["content"][0]["text"]
    except Exception:
        return None, "", err
    try:
        return json.loads(txt), txt, err
    except Exception:
        return None, txt, err


def event_objects(tool, args, parsed):
    """-> (consumed:set[(type,id)], produced:set[(type,id)], names_queried:list[str])"""
    consumed, produced, names = set(), set(), []
    args = args or {}

    def bind(k, v):
        t = ARG_TYPE.get(k.lower())
        if not t or not isinstance(v, str) or not v:
            return
        consumed.add((t, _odata_id(v) if "odata" in k.lower() else v))

    for k, v in args.items():
        bind(k, v)
        if k == "members" and isinstance(v, list):
            for mem in v:
                if isinstance(mem, dict):
                    for mk, mv in mem.items():
                        bind(mk, mv)
        if k == "_filter" and isinstance(v, str):
            names += re.findall(r"'([^']+)'", v)
        if k == "id" and tool == "get_call_record" and isinstance(v, str):
            consumed.add(("CallRecord", v))

    if not isinstance(parsed, dict):
        return consumed, produced, names

    op, ptype = TOOL_OP.get(tool, ("READ", "Unknown"))
    if tool in LIST_TYPE:                                   # READ: observes a set
        for row in (parsed.get("value") or []):
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                produced.add((LIST_TYPE[tool], row["id"]))
    elif isinstance(parsed.get("id"), str):                 # CREATE/SEND/UPDATE: one object
        produced.add((ptype, parsed["id"]))
    return consumed, produced, names


def load_trace(path):
    j = json.load(open(path))
    r = (j.get("runs") or [{}])[0]
    if "conversation_flow" not in r:
        return None
    # turn index per tool call: an ai_message may issue several calls in parallel
    turns, t = [], 0
    for m in r["conversation_flow"]:
        if m.get("type") == "ai_message":
            n = len(m.get("tool_calls") or [])
            if n:
                t += 1
                turns += [t] * n
    trs = r.get("tool_results") or []
    if len(turns) != len(trs):
        return None

    events = []
    for i, tr in enumerate(trs):
        tool = tr["tool_name"]
        parsed, _, err = _payload(tr)
        cons, prod, names = event_objects(tool, tr.get("arguments"), parsed)
        op, ptype = TOOL_OP.get(tool, ("READ", "Unknown"))
        events.append({"i": i, "turn": turns[i], "tool": tool, "op": op, "type": ptype,
                       "label": "%s(%s)" % (op, ptype), "consumed": cons, "produced": prod,
                       "names": names, "error": err})
    return {"file": os.path.relpath(path, RESULTS), "events": events,
            "prompt": j["benchmark_config"].get("user_prompt", ""),
            "pass_rate": j.get("statistics", {}).get("verifier_level_pass_rate"),
            "n_tools": j["benchmark_config"].get("total_tools_available")}


def build_edges(tr):
    """-> (temporal_edges, provenance_edges) as sets of (labelA, labelB[, shared_type])"""
    ev = tr["events"]
    temporal, prov = set(), set()

    by_turn = collections.defaultdict(list)
    for e in ev:
        by_turn[e["turn"]].append(e)
    turn_ids = sorted(by_turn)
    for a, b in zip(turn_ids, turn_ids[1:]):               # consecutive turns only
        for x in by_turn[a]:
            for y in by_turn[b]:
                temporal.add((x["label"], y["label"]))

    # provenance: latest prior event that produced/observed an object this one consumes
    for k, y in enumerate(ev):
        for (ot, oid) in y["consumed"]:
            for x in reversed(ev[:k]):
                if x["turn"] == y["turn"]:
                    continue                                # parallel: no dependency
                if (ot, oid) in x["produced"] or (ot, oid) in x["consumed"]:
                    prov.add((x["label"], y["label"], ot))
                    break
    return temporal, prov


def simple_cycles(adj, max_len=4):
    """Enumerate simple cycles up to max_len over a dict node -> set(node)."""
    out = set()
    nodes = sorted(adj)
    for start in nodes:
        stack = [(start, [start])]
        while stack:
            cur, path = stack.pop()
            for nxt in adj.get(cur, ()):
                if nxt == start and len(path) >= 2:
                    m = min(range(len(path)), key=lambda i: path[i])
                    out.add(tuple(path[m:] + path[:m]))
                elif nxt not in path and len(path) < max_len and nxt > start:
                    stack.append((nxt, path + [nxt]))
    return out


def main():
    files = sorted(glob.glob(os.path.join(RESULTS, "*/baseline/**/results_*.json"), recursive=True))
    traces = [t for t in (load_trace(f) for f in files) if t]
    print("loaded %d benign baseline traces (%d files)" % (len(traces), len(files)))
    ok = [t for t in traces if t["pass_rate"] == 1.0]
    print("  of which fully verifier-passing: %d" % len(ok))
    traces = ok

    ev_all = [e for t in traces for e in t["events"]]
    print("  %d tool events, %d distinct tools, %d distinct node labels"
          % (len(ev_all), len(set(e["tool"] for e in ev_all)), len(set(e["label"] for e in ev_all))))
    print("  errored events: %d" % sum(1 for e in ev_all if e["error"]))

    T_pop, P_pop = set(), set()
    per_trace = []
    for t in traces:
        te, pe = build_edges(t)
        per_trace.append((t, te, pe))
        T_pop |= te
        P_pop |= pe

    print("\n=== population edges ===")
    print("temporal   : %d distinct" % len(T_pop))
    print("provenance : %d distinct (typed by shared object)" % len(P_pop))

    # cycles
    adjT = collections.defaultdict(set)
    for a, b in T_pop:
        if a != b:
            adjT[a].add(b)
    adjP = collections.defaultdict(set)
    for a, b, _ in P_pop:
        if a != b:
            adjP[a].add(b)
    cT, cP = simple_cycles(adjT), simple_cycles(adjP)
    print("\n=== cycles in population graph (len<=4, self-loops excluded) ===")
    print("temporal   : %d" % len(cT))
    print("provenance : %d" % len(cP))

    # which population cycles occur inside a single trace?
    def cycles_of(edges, typed):
        adj = collections.defaultdict(set)
        for e in edges:
            a, b = (e[0], e[1])
            if a != b:
                adj[a].add(b)
        return simple_cycles(adj)

    seenT, seenP = set(), set()
    for t, te, pe in per_trace:
        seenT |= cycles_of(te, False)
        seenP |= cycles_of(pe, True)
    latentT, latentP = cT - seenT, cP - seenP
    print("\n=== latent cycles (in population graph, in NO single trace) ===")
    print("temporal   : %d / %d" % (len(latentT), len(cT)))
    print("provenance : %d / %d" % (len(latentP), len(cP)))

    print("\n--- provenance latent cycles ---")
    for c in sorted(latentP, key=lambda x: (len(x), x))[:25]:
        print("   " + " -> ".join(c) + " -> " + c[0])

    json.dump({"n_traces": len(traces),
               "temporal_edges": sorted(T_pop),
               "prov_edges": sorted(P_pop),
               "cycles_temporal": sorted(cT), "cycles_prov": sorted(cP),
               "latent_temporal": sorted(latentT), "latent_prov": sorted(latentP)},
              open("ocg_graph.json", "w"), indent=1)
    print("\n-> ocg_graph.json")


if __name__ == "__main__":
    main()
