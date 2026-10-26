"""Phase 0c-prep: DERIVE the writer motif table (guard Γ / effect Δ literals) purely from the
MEASURED data — measured_motifs.json (gym state-diff) + observed_guards.json (archived isError).
No literal is authored by hand; each carries the measured fact it came from.

Derivation rules (all applied to measured values):
  - INSERT into table T (row count up)        -> effect exists(Type(T), ?new)          [minted]
  - toggle column (before/after null<->val or 0<->1):
        predicate = pred(col); polarity from AFTER value  -> effect  pred(obj)=±
        the BEFORE value is the precondition               -> guard   pred(obj)=(before polarity)
  - attr column (str<->str)                    -> effect attr(obj, col)                 [α-ignored]
  - each entity arg the call REQUIRED          -> guard exists(Type(argkey), ?var)      [consumed]

Output: measured_writers.json  { tool: {op, guard:[lit...], effect:[lit...], obj, evidence} }
A literal is [pred, [args...], polarity]  (same shape recurrence_search.unify expects).
"""
import json, re

M = json.load(open("measured_motifs.json"))
G = json.load(open("observed_guards.json")) if __import__("os").path.exists("observed_guards.json") else {}

# table -> object Type (singular-ized, mechanical)
TABLE_TYPE = {"channels": "Channel", "channel_messages": "Message", "channel_members": "Membership",
              "teamwork_tags": "Tag", "teams_channel_tabs": "Tab", "chats": "Chat",
              "chat_members": "ChatMember", "groups": "Group", "teams_users": "User"}
# arg key -> Type + canonical variable (so tools sharing an object unify)
ARG_TYPE = {"teamId": "Team", "team_id": "Team", "channelId": "Channel", "chatId": "Chat",
            "messageId": "Message", "groupId": "Group", "userId": "User",
            "user_odata_bind": "User", "webinar_id": "Webinar", "membershipId": "Membership"}
VAR = {"Team": "?t", "Channel": "?c", "Message": "?m", "Chat": "?ch", "Group": "?g",
       "User": "?u", "Membership": "?mem", "Webinar": "?w"}


def pred_of(col):
    """column name -> predicate name, mechanically: strip is_ prefix and _datetime/_at suffix."""
    p = re.sub(r"^is_", "", col)
    p = re.sub(r"_(datetime|at)$", "", p)
    return p


def is_toggle(before, after):
    """boolean/presence toggle if one side is null/0 and the other isn't."""
    def empty(v):
        return v is None or v == 0 or v == "0"
    return empty(before) != empty(after)


def polarity(v):
    """the 'present/true' side is positive."""
    return not (v is None or v == 0 or v == "0")


def lit(pred, args, pos=True):
    return [pred, list(args), pos]


def derive(tool, m):
    op, guard, effect, ev = "READ", [], [], {}
    args = m.get("args_used") or {}
    obj_var = None

    # guards from required entity args (consumed preconditions)
    for k in args:
        t = ARG_TYPE.get(k)
        if t:
            guard.append(lit("exists", [t, VAR[t]], True))
            if obj_var is None or t in ("Message", "Channel", "Chat"):
                obj_var = (t, VAR[t])

    # effects from measured row-count inserts (CREATE)
    for tbl, v in (m.get("delta_rowcount") or {}).items():
        if v["after"] > v["before"] and tbl in TABLE_TYPE:
            t = TABLE_TYPE[tbl]
            nv = "?new_%s" % t.lower()
            effect.append(lit("exists", [t, nv], True))
            op = "CREATE"; ev.setdefault("effect", []).append("INSERT %s (%d->%d)" % (tbl, v["before"], v["after"]))
            if obj_var is None:
                obj_var = (t, nv)

    # effects + guards from measured column changes (UPDATE / toggle)
    for tbl, cols in (m.get("delta_columns") or {}).items():
        t = TABLE_TYPE.get(tbl, "Obj")
        v = obj_var[1] if obj_var and obj_var[0] == t else VAR.get(t, "?x")
        for col, (before, after) in cols.items():
            if col in ("last_modified_datetime", "updated_at"):   # bookkeeping, ignore
                continue
            op = "UPDATE"
            if is_toggle(before, after):
                p = pred_of(col)
                effect.append(lit(p, [v], polarity(after)))
                guard.append(lit(p, [v], polarity(before)))      # BEFORE value = precondition
                ev.setdefault("effect", []).append("%s.%s toggle %r->%r" % (tbl, col, before, after))
            else:
                effect.append(lit("attr", [v, col], True))       # α-ignored attribute
                ev.setdefault("effect", []).append("%s.%s attr %r->%r" % (tbl, col, str(before)[:20], str(after)[:20]))

    # observed guards (archive-wide isError) as evidence (not turned into literals unless a known
    # state guard; kept as provenance so a human can audit).
    og = list((G.get(tool) or {}).keys())
    if og:
        ev["guard_observed"] = og[:3]

    # dedup literals
    def uniq(ls):
        seen, out = set(), []
        for l in ls:
            k = (l[0], tuple(l[1]), l[2])
            if k not in seen:
                seen.add(k); out.append(l)
        return out
    return {"op": op, "guard": uniq(guard), "effect": uniq(effect),
            "obj": obj_var[0] if obj_var else None, "evidence": ev,
            "measured_ok": m.get("success")}


if __name__ == "__main__":
    writers = {tool: derive(tool, m) for tool, m in M.items() if m.get("success")}
    json.dump(writers, open("measured_writers.json", "w"), indent=1, ensure_ascii=False)
    print("derived %d writer motifs from measurement -> measured_writers.json\n" % len(writers))
    def fmt(l): return ("" if l[2] else "!") + "%s(%s)" % (l[0], ",".join(l[1]))
    for tool, w in writers.items():
        print("%-30s %-6s  Γ: %-42s  Δ: %s" % (
            tool, w["op"],
            " ^ ".join(fmt(x) for x in w["guard"]) or "-",
            " ^ ".join(fmt(x) for x in w["effect"]) or "-"))
