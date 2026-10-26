"""Measure the one UNCONDITIONAL executable-recurrence candidate that recurrence_search.py
found:  soft_delete_channel_message  <->  undo_soft_delete_channel_message.

Question 1 (state recurrence): is alpha(F_C(s)) == alpha(s) in the real gym, i.e. does one
                               pass around the cycle leave the database as it was?
Question 2 (guard enforcement): are Gamma(soft_delete)=exists(m) and Gamma(undo)=!exists(m)
                               actually enforced, or can the cycle be spun without them?
Also re-checks archive_channel's guard/effect directly, and whether the MCP surface offers any
way back from archived(c) (the REST API has /unarchive; the 70 MCP tools do not).
"""
import json, sys
import measure_effects as M

d = json.load(open("delta_probe_db.json"))
dbid, tbls = d["db"], d["tables"]
TEAM = "team_techcorp_001"


def step(label, name, args, before):
    r = M.call_tool(dbid, name, args)
    txt = M.text_of(r)
    after = M.snapshot(dbid, tbls)
    dl = M.diff(before, after)
    err = "Error" in txt or "error" in txt.lower()[:40] or "Cannot" in txt
    print("  %-38s %-7s  diff=%s" % (label, "ERR" if err else "ok", dl or "{}"))
    if err:
        print("      -> %s" % txt.replace("\n", " ")[:150])
    return after, txt, dl


snap0 = M.snapshot(dbid, tbls)
ch = M.rows_of(dbid, "SELECT channel_id, display_name FROM channels WHERE team_id='%s' LIMIT 3;" % TEAM)
print("channels in %s: %s" % (TEAM, [(c["channel_id"], c["display_name"]) for c in ch]))
CH = ch[0]["channel_id"]

print("\n=== A. soft_delete / undo_soft_delete round trip ===")
s, txt, _ = step("send_channel_message", "send_channel_message",
                 {"teamId": TEAM, "channelId": CH,
                  "body": {"contentType": "text", "content": "delta probe message"}}, snap0)
try:
    MSG = json.loads(txt)["id"]
except Exception:
    print("could not get message id:", txt[:200]); sys.exit(1)
print("  message id: %s" % MSG)
base = s                                     # alpha(s) : the entry state of the cycle

s, _, _ = step("soft_delete  (1st, guard holds)", "soft_delete_channel_message",
               {"teamId": TEAM, "channelId": CH, "messageId": MSG}, s)
mid = s
s, _, _ = step("soft_delete  (2nd, guard VIOLATED)", "soft_delete_channel_message",
               {"teamId": TEAM, "channelId": CH, "messageId": MSG}, s)
s, _, _ = step("undo_soft_delete (guard holds)", "undo_soft_delete_channel_message",
               {"teamId": TEAM, "channelId": CH, "messageId": MSG}, s)
back = s
s, _, _ = step("undo_soft_delete (2nd, guard VIOLATED)", "undo_soft_delete_channel_message",
               {"teamId": TEAM, "channelId": CH, "messageId": MSG}, s)

print("\n  alpha(F_C(s)) vs alpha(s): %s" % (M.diff(base, back) or "IDENTICAL"))

print("\n  --- spin the cycle 5 more times, checking identity each pass ---")
cur = back
for i in range(5):
    cur, _, _ = step("pass %d: soft_delete" % (i + 2), "soft_delete_channel_message",
                     {"teamId": TEAM, "channelId": CH, "messageId": MSG}, cur)
    cur, _, _ = step("pass %d: undo" % (i + 2), "undo_soft_delete_channel_message",
                     {"teamId": TEAM, "channelId": CH, "messageId": MSG}, cur)
    print("      after pass %d: %s" % (i + 2, M.diff(base, cur) or "IDENTICAL to entry state"))

print("\n=== B. archive_channel guard/effect, and any way back ===")
s = cur
s, txt, _ = step("create_channel", "create_channel",
                 {"teamId": TEAM, "displayName": "Delta Probe Chan",
                  "description": "probe", "membershipType": "standard"}, s)
try:
    NEW = json.loads(txt)["id"]
except Exception:
    NEW = None
    print("   (no channel id)", txt[:150])
if NEW:
    s, _, _ = step("archive (no owner yet)", "archive_channel",
                   {"teamId": TEAM, "channelId": NEW}, s)
    s, _, _ = step("add_channel_member owner", "add_channel_member",
                   {"teamId": TEAM, "channelId": NEW,
                    "user_odata_bind": "https://graph.microsoft.com/v1.0/users('bob.smith')",
                    "roles": ["owner"]}, s)
    s, _, _ = step("archive (owner present)", "archive_channel",
                   {"teamId": TEAM, "channelId": NEW}, s)
    s, _, _ = step("send_channel_message on archived", "send_channel_message",
                   {"teamId": TEAM, "channelId": NEW,
                    "body": {"contentType": "text", "content": "after archive"}}, s)
    s, _, _ = step("add_tabs_to_channels on archived", "add_tabs_to_channels",
                   {"teamId": TEAM, "channelId": NEW, "displayName": "T",
                    "teamsApp_odata_bind": "https://graph.microsoft.com/v1.0/appCatalogs/"
                                           "teamsApps/0d820ecd-def2-4297-adad-78056cde7c79"}, s)
    s, _, _ = step("update_channel on archived", "update_channel",
                   {"teamId": TEAM, "channelId": NEW, "description": "changed after archive"}, s)
    print("  archived flag in DB: %s" %
          M.rows_of(dbid, "SELECT channel_id, is_archived FROM channels WHERE channel_id='%s';" % NEW))
