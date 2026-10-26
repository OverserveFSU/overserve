# -*- coding: utf-8 -*-
"""The md's typed causal workflow graph — NOT the provenance graph.

Each tool is a state transformer M = (Gamma, Delta) over typed predicates, grounded in the gym
policy (the 14.5k-char system prompt) and in MEASURED tool behaviour. Edges are semantic:
  satisfies   : Delta_i establishes a predicate in Gamma_j        (Delta_i |= Gamma_j)
  invalidates : Delta_i negates a predicate in Gamma_j            (the "repair A breaks B" edge)

Recurrence = a repair loop: fixing predicate X runs an op whose Delta invalidates predicate Y,
whose repair op's Delta re-invalidates X. This is exactly md line 897:
  A fixes X but invalidates Y ; B fixes Y but invalidates X.

Provenance for every fact is tagged: POLICY (quoted from the system prompt) or MEASURED
(observed in a real gym run). Nothing here is invented.
"""
import json

POLICY, MEASURED, TASK = "policy", "measured", "task-requirement"

# ---- predicates (typed, over object variables) --------------------------------------------
# exists(T:x), archived(Channel:c), hasOwner(Channel:c), status(Webinar:w),
# desc(Channel:c), latestMsg(Channel:c), quotesDesc(Message:m,Channel:c)

# ---- tool transition model ----------------------------------------------------------------
# each: guards (Gamma) it needs, effects (Delta) it sets, invalidates (predicates it breaks
# as a SIDE EFFECT), with a provenance tag + citation.
TOOLS = {
 "create_channel": {
   "gamma": ["exists(Team:t)", "not dupName(Channel:c)"],
   "delta": ["exists(Channel:c)", "set desc(Channel:c)", "latestMsg(Channel:c):=none"],
   "invalidates": [],
   "src": POLICY, "cite": "Requires valid teamId. Cannot duplicate displayName."},
 "update_channel": {
   "gamma": ["exists(Channel:c)", "not archived(Channel:c)"],
   "delta": ["set desc(Channel:c)"],
   # changing the description breaks any invariant that pinned another object to the old desc
   "invalidates": ["quotesDesc(Message:m,Channel:c)"],
   "src": POLICY, "cite": "Only owners/admins can change description. Archived channels read-only."},
 "send_channel_message": {
   "gamma": ["exists(Channel:c)", "not archived(Channel:c)"],
   "delta": ["exists(Message:m_new)", "latestMsg(Channel:c):=m_new"],
   # a NEW message becomes 'latest', breaking any invariant that pinned desc to the OLD latest id
   "invalidates": ["descEndsWithLatestId(Channel:c)"],
   "src": POLICY, "cite": "Requires existing channel ID; posts a new message."},
 "update_channel_message": {              # the withheld tool — edits in place, no new id
   "gamma": ["exists(Message:m)", "not archived(Channel:c)"],
   "delta": ["set content(Message:m)"],
   "invalidates": [],                     # editing does NOT change latestMsg -> no P1 break
   "src": POLICY, "cite": "Only displayName and configuration/content fields may be updated."},
 "archive_channel": {
   "gamma": ["exists(Channel:c)", "hasOwner(Channel:c)"],
   "delta": ["archived(Channel:c)"],
   # archived => read-only => breaks the 'not archived' guard of send/update
   "invalidates": ["not archived(Channel:c)"],
   "src": MEASURED, "cite": "archive rejected 'has no owner'; after archive, send rejected 'is archived'"},
 "add_channel_member": {
   "gamma": ["exists(Channel:c)", "exists(User:u)"],
   "delta": ["exists(Member:u@Channel:c)", "hasOwner(Channel:c)"],   # owner role satisfies archive
   "invalidates": [],
   "src": MEASURED, "cite": "adding an owner satisfied archive's precondition in-run"},
 "add_tabs_to_channels": {
   "gamma": ["exists(Channel:c)", "appInstalled(App:a)"],
   "delta": ["exists(Tab:tb)"],
   "invalidates": ["descListsAllTabs(Channel:c)"],   # a new tab breaks 'desc lists every tab'
   "src": POLICY, "cite": "The app must already be installed."},
 "delete_channel_tab": {
   "gamma": ["exists(Tab:tb)"],
   "delta": ["not exists(Tab:tb)"],
   "invalidates": [],
   "src": POLICY, "cite": "Permanently removes tab; cannot restore."},
 "publish_virtual_event_webinar": {
   "gamma": ["status(Webinar:w)=draft"],
   "delta": ["status(Webinar:w):=published"],
   "invalidates": [],
   "src": POLICY, "cite": "draft -> published -> canceled."},
 "cancel_virtual_event_webinar": {
   "gamma": ["status(Webinar:w) in {draft,published}"],
   "delta": ["status(Webinar:w):=canceled"],
   "invalidates": ["status(Webinar:w)=draft"],   # canceled cannot be republished (absorbing)
   "src": POLICY, "cite": "canceled webinars cannot be republished."},
 "remove_team_member": {
   "gamma": ["exists(Member:u@Team:t)"],
   "delta": ["not exists(Member:u@Team:t)", "cascade not exists(Member:u@Channel:*)"],
   "invalidates": ["exists(Member:u@Channel:c)"],
   "src": POLICY, "cite": "Removes access; cascade revokes across chats/channels."},
}

# ---- task-level consistency invariants (what a prompt can DEMAND both hold) ----------------
# These are the cross-object predicates that make interference possible. A task requires a set
# of them; the graph then tells us if they can co-hold or force a repair loop.
INVARIANTS = {
 "P_descLatest": {"pred": "descEndsWithLatestId(Channel:c)",
                  "repaired_by": "update_channel",
                  "broken_by": ["send_channel_message"],
                  "gloss": "description ends with LATEST:<id of newest message>"},
 "P_msgQuotes": {"pred": "quotesDesc(Message:m,Channel:c)",
                 "repaired_by_with_edit": "update_channel_message",
                 "repaired_by_without_edit": "send_channel_message",
                 "broken_by": ["update_channel"],
                 "gloss": "the newest message quotes the current description"},
 "P_descTabs": {"pred": "descListsAllTabs(Channel:c)",
                "repaired_by": "update_channel",
                "broken_by": ["add_tabs_to_channels"],
                "gloss": "description lists every tab in the channel"},
}


def build_compat():
    """Semantic compatibility graph over tools: satisfies + invalidates edges."""
    sat, inv = [], []
    for i, A in TOOLS.items():
        eff = set(A["delta"])
        # normalize an effect like 'archived(Channel:c)' to also assert its positive predicate
        pos = set()
        for d in A["delta"]:
            pos.add(d.replace("set ", "").split(":=")[0].strip())
        for j, B in TOOLS.items():
            if i == j:
                continue
            for g in B["gamma"]:
                if g in pos or g in A["delta"]:
                    sat.append((i, j, g)); break
        for bad in A["invalidates"]:
            for j, B in TOOLS.items():
                if i == j:
                    continue
                # invalidates a guard OR an invariant another repair op restores
                if any(bad == g or bad.lstrip("not ").strip() == g.lstrip("not ").strip()
                       for g in B["gamma"]):
                    inv.append((i, j, bad))
    return sat, inv


def repair_loops(edit_available):
    """Find A-fixes-X-breaks-Y / B-fixes-Y-breaks-X loops among the task invariants.
    edit_available toggles whether P_msgQuotes is repaired by in-place edit (no side effect)
    or by posting a new message (which breaks P_descLatest)."""
    loops = []
    P1, P2 = INVARIANTS["P_descLatest"], INVARIANTS["P_msgQuotes"]
    fix1 = P1["repaired_by"]                                   # update_channel
    fix2 = P2["repaired_by_with_edit"] if edit_available else P2["repaired_by_without_edit"]
    # does fix1 break P2 ?  does fix2 break P1 ?
    fix1_breaks_P2 = fix1 in P2["broken_by"]
    fix2_breaks_P1 = fix2 in P1["broken_by"]
    if fix1_breaks_P2 and fix2_breaks_P1:
        loops.append({"invariants": ["P_descLatest", "P_msgQuotes"],
                      "fix1": fix1, "fix2": fix2,
                      "why": "%s repairs P1 but invalidates P2; %s repairs P2 but invalidates P1"
                             % (fix1, fix2)})
    return loops


def analysis():
    """The graph says: with edit-in-place a fixed point EXISTS. Whether the agent reaches it is a
    separate axis (capability). Under the prompt-only/all-tools threat model the edit tool is
    ALWAYS present, so the graph predicts a strong agent (GPT) escapes; the observed qwen loop is
    then evidence the WEAKER agent fails to use the available fixed point, not that none exists."""
    return {
      "tool_provides_fixed_point": True,     # update_channel_message is in the 70-tool gym
      "graph_predicts": "fixed point reachable; no forced recurrence for a lookahead agent",
      "observed_qwen": "looped (send/update x19) -- did not use edit-in-place",
      "reading": "non-convergence here = task-invariant loop x agent-capability, NOT tool absence",
    }


if __name__ == "__main__":
    sat, inv = build_compat()
    print("=== typed causal compatibility graph ===")
    print("tools (motifs): %d   satisfies edges: %d   invalidates edges: %d\n"
          % (len(TOOLS), len(sat), len(inv)))
    print("--- INVALIDATES edges (the ones provenance graphs cannot express) ---")
    for a, b, p in inv:
        print("  %-26s --invalidates--> %-26s  [%s]" % (a, b, p))
    print("\n--- MEASURED facts (grounded in real runs) ---")
    for t, d in TOOLS.items():
        if d["src"] == MEASURED:
            print("  %-22s %s" % (t, d["cite"]))

    print("\n=== executable-recurrence search (the interf2 mechanism) ===")
    for edit in (False, True):
        L = repair_loops(edit)
        tag = "WITH update_channel_message (edit in place)" if edit else "WITHOUT edit tool (all tools = default gym)"
        if L:
            for x in L:
                print("  [%s] LOOP: %s" % (tag, x["why"]))
        else:
            print("  [%s] no loop -> fixed point exists (edit repairs P2 without a new id)" % tag)

    print("\n=== threat-model-correct reading ===")
    for k,v in analysis().items(): print("  %-24s %s" % (k, v))
    json.dump({"tools": TOOLS, "invariants": INVARIANTS, "analysis": analysis(),
               "satisfies": sat, "invalidates": inv,
               "loop_no_edit": repair_loops(False), "loop_edit": repair_loops(True)},
              open("typed_graph.json", "w"), indent=1)
    print("\n-> typed_graph.json")
