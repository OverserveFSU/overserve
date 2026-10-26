"""Phase 0b: MEASURE each writer tool's effect (Δ) and precondition (Γ) in the live gym.

No hand-authored semantics. For every target writer tool we:
  1. seed a fresh gym DB (clean baseline)
  2. build valid arguments from real ids queried out of that DB
  3. snapshot table row-counts, execute the tool via /mcp, snapshot again -> measured Δ
     (which tables gained/lost rows; for the touched object, which columns changed)
  4. take Γ from the archive-wide observed guards (observed_guards.json, Phase 0a) plus the
     entity args the call required (a call needing channelId evidences a precondition on Channel)

Output: measured_motifs.json  { tool: {op, obj, args_used, delta_measured, guard_observed,
                                        success, evidence} }
Every field is measured; nothing is asserted by hand. This REPLACES motif_semantics.py.
"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure_effects as ME

U = lambda uid: "https://graph.microsoft.com/v1.0/users('%s')" % uid
APP_ONENOTE = "https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/0d820ecd-def2-4297-adad-78056cde7c79"
TEAM = "team_techcorp_001"


def q1(db, sql, col):
    r = ME.rows_of(db, sql)
    return r[0][col] if r else None


def general(db):
    return q1(db, "SELECT channel_id FROM channels WHERE team_id='%s' AND display_name='General'" % TEAM, "channel_id")


def a_msg(db, ch):
    return q1(db, "SELECT message_id FROM channel_messages WHERE channel_id='%s' AND deleted_datetime IS NULL LIMIT 1" % ch, "message_id")


# tool -> (op, object-type, builder(db)->args).  builder queries the fresh DB for real ids.
# The builder is measurement setup (drive the tool with real inputs), not a semantic claim.
def build(db, tool):
    ch = general(db)
    if tool == "create_channel":
        return {"teamId": TEAM, "displayName": "M_probe", "description": "measure probe", "membershipType": "standard"}
    if tool == "update_channel":
        return {"teamId": TEAM, "channelId": ch, "description": "measured new description text over fifty chars long here"}
    if tool == "add_channel_member":
        return {"teamId": TEAM, "channelId": ch, "user_odata_bind": U("james.wilson"), "roles": []}
    if tool == "archive_channel":
        ME.call_tool(db, "add_channel_member", {"teamId": TEAM, "channelId": ch, "user_odata_bind": U("james.wilson"), "roles": ["owner"]})
        return {"teamId": TEAM, "channelId": ch}
    if tool == "provision_channel_email":
        return {"teamId": TEAM, "channelId": ch}
    if tool == "send_channel_message":
        ME.call_tool(db, "add_channel_member", {"teamId": TEAM, "channelId": ch, "user_odata_bind": U("james.wilson"), "roles": []})
        return {"teamId": TEAM, "channelId": ch, "body": {"contentType": "text", "content": "measure probe msg"}}
    if tool in ("soft_delete_channel_message", "undo_soft_delete_channel_message"):
        # measured guard: soft_delete needs sender(caller,m) OR owner(caller,c). Make james.wilson
        # a member and the SENDER of a fresh message, so the guard is satisfied.
        ME.call_tool(db, "add_channel_member", {"teamId": TEAM, "channelId": ch, "user_odata_bind": U("james.wilson"), "roles": []})
        sr = ME.call_tool(db, "send_channel_message", {"teamId": TEAM, "channelId": ch, "body": {"contentType": "text", "content": "measure target"}})
        try:
            m = json.loads(ME.text_of(sr))["id"]
        except Exception:
            m = a_msg(db, ch)
        if tool == "undo_soft_delete_channel_message":  # must first delete so undo has a target
            ME.call_tool(db, "soft_delete_channel_message", {"teamId": TEAM, "channelId": ch, "messageId": m})
        return {"teamId": TEAM, "channelId": ch, "messageId": m}
    if tool == "create_teamwork_tag":
        return {"team_id": TEAM, "displayName": "M_tag", "description": "measure"}
    if tool == "add_tabs_to_channels":
        return {"teamId": TEAM, "channelId": ch, "displayName": "M_tab", "teamsApp_odata_bind": APP_ONENOTE}
    if tool == "remove_team_member":
        mid = q1(db, "SELECT membership_id FROM teams_users WHERE team_id='%s' LIMIT 1" % TEAM, "membership_id") \
            or q1(db, "SELECT id FROM team_members WHERE team_id='%s' LIMIT 1" % TEAM, "id")
        return {"teamId": TEAM, "membershipId": mid}
    if tool == "update_user":
        return {"userId": "james.wilson", "jobTitle": "Measured Title"}
    if tool == "update_group":
        gid = q1(db, "SELECT group_id FROM groups LIMIT 1", "group_id")
        return {"groupId": gid, "description": "measured"}
    if tool == "create_chat":
        return {"chatType": "group", "topic": "M_chat",
                "members": [{"user_odata_bind": U("james.wilson"), "roles": ["owner"]},
                            {"user_odata_bind": U("bob.smith"), "roles": ["owner"]}]}
    # ---- coupling-relevant writers (expand from 14 to full feasible writer set) ----
    if tool == "update_channel_tab":
        tid = q1(db, "SELECT tab_id FROM teams_channel_tabs WHERE channel_id='%s' LIMIT 1" % ch, "tab_id")
        return {"teamId": TEAM, "channelId": ch, "tabId": tid, "displayName": "M_tab_renamed"}
    if tool == "delete_channel_tab":
        tid = q1(db, "SELECT tab_id FROM teams_channel_tabs WHERE channel_id='%s' LIMIT 1" % ch, "tab_id")
        return {"teamId": TEAM, "channelId": ch, "tabId": tid}
    if tool in ("update_channel_message", "set_channel_message_reaction", "unset_channel_message_reaction"):
        ME.call_tool(db, "add_channel_member", {"teamId": TEAM, "channelId": ch, "user_odata_bind": U("james.wilson"), "roles": []})
        sr = ME.call_tool(db, "send_channel_message", {"teamId": TEAM, "channelId": ch, "body": {"contentType": "text", "content": "measure target"}})
        try:
            m = json.loads(ME.text_of(sr))["id"]
        except Exception:
            m = a_msg(db, ch)
        if tool == "update_channel_message":
            return {"teamId": TEAM, "channelId": ch, "messageId": m, "body": {"contentType": "text", "content": "edited"}}
        if tool == "unset_channel_message_reaction":
            ME.call_tool(db, "set_channel_message_reaction", {"teamId": TEAM, "channelId": ch, "messageId": m, "reactionType": "like"})
        return {"teamId": TEAM, "channelId": ch, "messageId": m, "reactionType": "like"}
    if tool == "update_team":
        return {"teamId": TEAM, "description": "measured team description update"}
    if tool == "update_teamwork_tag":
        tg = q1(db, "SELECT id FROM teamwork_tags WHERE team_id='%s' LIMIT 1" % TEAM, "id")
        return {"team_id": TEAM, "tag_id": tg, "displayName": "M_tag_renamed"}
    if tool == "add_team_member":
        return {"teamId": TEAM, "user_odata_bind": U("carol.white")}
    if tool == "add_group_owner":
        gid = q1(db, "SELECT group_id FROM groups LIMIT 1", "group_id")
        return {"groupId": gid, "_odata_id": U("james.wilson")}
    return None


TARGETS = ["create_channel", "update_channel", "add_channel_member", "archive_channel",
           "provision_channel_email", "send_channel_message", "soft_delete_channel_message",
           "undo_soft_delete_channel_message", "create_teamwork_tag", "add_tabs_to_channels",
           "remove_team_member", "update_user", "update_group", "create_chat",
           "update_channel_tab", "delete_channel_tab", "update_channel_message",
           "set_channel_message_reaction", "unset_channel_message_reaction",
           "update_team", "update_teamwork_tag", "add_team_member", "add_group_owner"]


def changed_columns(db_before_rows, db_after_rows, key):
    """For update-type effects: which columns differ on the same-key row, WITH before/after values
    so the WRITERS-builder can derive toggle polarity (e.g. deleted_datetime null->ts = set).
    Robust to tables lacking `key` (skip) — the pk column varies across gym tables."""
    if db_before_rows and key not in db_before_rows[0]:
        return {}
    bi = {r[key]: r for r in db_before_rows}
    out = {}
    for r in db_after_rows:
        if key not in r:
            return {}
        b = bi.get(r[key])
        if b:
            for c in r:
                if r[c] != b.get(c):
                    out[c] = [b.get(c), r[c]]
    return out


# tables to watch per object type, so update effects surface at column granularity
WATCH = {"channels": "channel_id", "channel_messages": "message_id", "channel_members": "id",
         "teams_channel_tabs": "tab_id", "teamwork_tags": "id", "groups": "group_id",
         "chats": "chat_id", "chat_members": "id", "teams": "team_id"}


def measure_one(tool):
    db = ME.seed()
    tbls = ME.tables(db)
    args = build(db, tool)
    if not args:
        return {"tool": tool, "error": "no arg builder"}
    snap0 = ME.snapshot(db, tbls)
    watch_before = {t: ME.rows_of(db, "SELECT * FROM %s" % t) for t in WATCH}
    resp = ME.call_tool(db, tool, args)
    txt = ME.text_of(resp)
    err = ("Error" in txt) or ("denied" in txt.lower()) or ("Cannot" in txt) or ("Validation error" in txt)
    snap1 = ME.snapshot(db, tbls)
    rowdiff = ME.diff(snap0, snap1)                       # tables whose COUNT changed (insert/delete)
    coldiff = {}                                          # tables whose rows changed columns (update)
    for t, key in WATCH.items():
        after = ME.rows_of(db, "SELECT * FROM %s" % t)
        cc = changed_columns(watch_before[t], after, key)
        if cc and t not in rowdiff:
            coldiff[t] = cc
    return {"tool": tool, "args_used": args, "success": not err,
            "resp_head": txt[:80].replace("\n", " "),
            "delta_rowcount": {t: {"before": a, "after": b} for t, (a, b) in rowdiff.items()},
            "delta_columns": coldiff}


if __name__ == "__main__":
    only = sys.argv[1:] or TARGETS
    guards = json.load(open("observed_guards.json")) if os.path.exists("observed_guards.json") else {}
    out = {}
    for tool in only:
        m = measure_one(tool)
        m["guard_observed"] = list(guards.get(tool, {}).keys())[:3]
        out[tool] = m
        d = m.get("delta_rowcount", {}); c = m.get("delta_columns", {})
        print("%-32s ok=%-5s Δrows=%s Δcols=%s" % (
            tool, m.get("success"),
            {t: "%d→%d" % (v["before"], v["after"]) for t, v in d.items()} or "{}",
            {t: list(cols) for t, cols in c.items()} or "{}"), flush=True)
    json.dump(out, open("measured_motifs.json", "w"), indent=1, ensure_ascii=False)
    print("\n-> measured_motifs.json (%d tools)" % len(out))
