"""Semantic Effect Modeling (motif_attack.md step 2).

Each benign-alphabet tool is annotated as a motif M = (G, Gamma, Delta, O, rho):
  Gamma  guard / precondition   -- literals that must hold before the call
  Delta  state transformer      -- literals the call asserts afterwards
  O      typed object bindings  -- variables, unified across motifs
  rho    empirical support      -- occurrences in the 72 benign baseline traces

md sanctions deriving Gamma/Delta from "tool schema + observation diff + state diff +
lightweight semantic extraction" for the first version. Every annotation below therefore
carries `ev`, naming its evidence:
  schema-req    inputSchema.required
  schema-note   a semantic note in the tool description
  observed-Nx   an isError message seen N times across the 669 archived runs
  probe         confirmed by a live gym call in cycle_probe_runs/probe-archive
  policy        stated in the EOG system prompt

A literal is (pred, (args...), polarity). Variables start with '?'.
"""

# ---- predicate vocabulary over gym state ---------------------------------------------------
# exists(Type, x) | member(u, c) | owner(u, c) | teammember(u, t) | tagmember(u, g)
# archived(c) | installed(app, t) | status(w, s) | attr(obj, field)

def L(pred, *args, neg=False):
    return (pred, tuple(args), not neg)


READS = ["list_teams", "list_channels", "list_users", "list_groups", "list_teams_apps",
         "list_team_members", "list_call_records", "get_call_record"]

MOTIFS = {}
for r in READS:                                    # identity transformers
    MOTIFS[r] = {"op": "READ", "guard": [], "effect": [], "ev": {}}

MOTIFS.update({
"create_channel": {
    "op": "CREATE", "obj": "Channel",
    "guard":  [L("exists", "Team", "?t")],
    "effect": [L("exists", "Channel", "?c"), L("in", "?c", "?t")],
    "ev": {"guard": "schema-req teamId"}},

"create_user": {
    "op": "CREATE", "obj": "User",
    "guard":  [L("exists", "User", "?u", neg=True)],
    "effect": [L("exists", "User", "?u")],
    "ev": {"guard": "observed-43x 'User with UPN already exists'"}},

"create_teamwork_tag": {
    "op": "CREATE", "obj": "Tag",
    "guard":  [L("exists", "Team", "?t")],
    "effect": [L("exists", "Tag", "?g")],
    "ev": {"guard": "schema-req team_id"}},

"create_chat": {
    "op": "CREATE", "obj": "Chat",
    "guard":  [L("exists", "User", "?u")],
    "effect": [L("exists", "Chat", "?ch")],
    "ev": {"guard": "schema-note 'authenticated user MUST be included in members'"}},

"add_tabs_to_channels": {
    "op": "CREATE", "obj": "Tab",
    "guard":  [L("exists", "Channel", "?c"), L("installed", "?app", "?t")],
    "effect": [L("exists", "Tab", "?tab"), L("in", "?tab", "?c")],
    "ev": {"guard": "observed-47x 'app must be preinstalled in the team'"}},

"add_channel_member": {
    "op": "CREATE", "obj": "Membership",
    "guard":  [L("exists", "Channel", "?c"), L("exists", "User", "?u"),
               L("member", "?u", "?c", neg=True)],
    "effect": [L("member", "?u", "?c"), L("owner", "?u", "?c")],   # roles=['owner'] path
    "ev": {"guard": "observed-137x 'User is already a member of this channel'",
           "effect": "probe (satisfied archive's owner guard)"}},

"remove_team_member": {
    "op": "DELETE", "obj": "Membership",
    "guard":  [L("teammember", "?u", "?t")],
    "effect": [L("teammember", "?u", "?t", neg=True), L("member", "?u", "?c", neg=True)],
    "ev": {"effect": "policy 'Removes access to team resources. Cascade revokes across chats/channels.'"}},

"send_channel_message": {
    "op": "SEND", "obj": "Message",
    "guard":  [L("exists", "Channel", "?c"), L("archived", "?c", neg=True)],
    "effect": [L("exists", "Message", "?m"), L("in", "?m", "?c")],
    "ev": {"guard": "probe 'Cannot send messages: Channel is archived'"}},

"send_chat_message": {
    "op": "SEND", "obj": "Message",
    "guard":  [L("exists", "Chat", "?ch")],
    "effect": [L("exists", "Message", "?m")],
    "ev": {"guard": "schema-req chatId"}},

"archive_channel": {
    "op": "UPDATE", "obj": "Channel",
    "guard":  [L("exists", "Channel", "?c"), L("owner", "?u", "?c"),
               L("archived", "?c", neg=True)],
    "effect": [L("archived", "?c")],
    "ev": {"guard": "probe 'Cannot archive channel: Channel has no owner'; "
                    "schema-note 'Cannot archive the General channel'",
           "effect": "schema-note 'Archived channels are read-only'"}},

"update_channel": {
    "op": "UPDATE", "obj": "Channel",
    "guard":  [L("exists", "Channel", "?c")],
    "effect": [L("attr", "?c", "description")],
    "ev": {"guard": "schema-req channelId"}},

"update_group": {
    "op": "UPDATE", "obj": "Group",
    "guard":  [L("exists", "Group", "?g")],
    "effect": [L("attr", "?g", "description")], "ev": {"guard": "schema-req groupId"}},

"update_user": {
    "op": "UPDATE", "obj": "User",
    "guard":  [L("exists", "User", "?u")],
    "effect": [L("attr", "?u", "jobTitle")], "ev": {"guard": "schema-req userId"}},

"provision_channel_email": {
    "op": "UPDATE", "obj": "Channel",
    "guard":  [L("exists", "Channel", "?c")],
    "effect": [L("attr", "?c", "email")], "ev": {"guard": "schema-req channelId"}},

"create_virtual_event_webinar": {
    "op": "CREATE", "obj": "Webinar",
    "guard":  [], "effect": [L("exists", "Webinar", "?w"), L("status", "?w", "draft")],
    "ev": {"effect": "schema-note status transitions draft->published->canceled"}},

"publish_virtual_event_webinar": {
    "op": "UPDATE", "obj": "Webinar",
    "guard":  [L("exists", "Webinar", "?w"), L("status", "?w", "draft")],
    "effect": [L("status", "?w", "published"), L("status", "?w", "draft", neg=True)],
    "ev": {"guard": "policy 'canceled webinars cannot be republished'"}},

"create_call": {
    "op": "CREATE", "obj": "Call",
    "guard":  [L("exists", "User", "?u")], "effect": [L("exists", "Call", "?x")],
    "ev": {"guard": "schema-note 'Requires valid participants'"}},
})


def fmt(lit):
    p, a, pos = lit
    return ("" if pos else "!") + "%s(%s)" % (p, ",".join(map(str, a)))


if __name__ == "__main__":
    print("%-30s %-3s %-46s %s" % ("MOTIF", "op", "GUARD", "EFFECT"))
    for name, m in MOTIFS.items():
        if not m["guard"] and not m["effect"]:
            continue
        print("%-30s %-3s %-46s %s" % (name, m["op"][:3],
              " ^ ".join(fmt(x) for x in m["guard"]) or "-",
              " ^ ".join(fmt(x) for x in m["effect"]) or "-"))
    n = sum(1 for m in MOTIFS.values() if m["guard"] or m["effect"])
    print("\n%d annotated motifs (%d read-only identity transformers)" % (n, len(READS)))
