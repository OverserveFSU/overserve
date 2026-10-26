"""Measure Gamma/Delta empirically by state diff (motif_attack.md step 2, the 'state diff' arm).

Seeds a private gym database, calls MCP tools directly, and diffs the SQL state around each
call. This replaces the hand-curated annotations in motif_semantics.py with measured ones, and
tests guards by deliberately calling a tool in a state that should violate them.
"""
import os, json, time, random, string, sys
import httpx

GYM = "http://localhost:8002"
SQL = ("/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/Domain Wise DBs and Task-DB Mappings/"
       "teams/dbs/db_1764274139477_ve41d08gm.sql")
CTX = {"x-teams-access-token":
       "ya29.A0ARrdaM-super999unique888token777special666.SuperUserAllPermissionsTokenAccess_99-99"}


def seed():
    dbid = "db_%d_%s" % (int(time.time() * 1000),
                         "".join(random.choices(string.ascii_lowercase + string.digits, k=9)))
    sql = open(SQL, encoding="utf-8").read()
    r = httpx.post(f"{GYM}/api/seed-database", timeout=600, json={
        "database_id": dbid, "name": "delta-probe",
        "description": "effect measurement", "sql_content": sql})
    r.raise_for_status()
    return dbid


def sql_query(dbid, q):
    r = httpx.post(f"{GYM}/api/sql-runner", timeout=120,
                   headers={"x-database-id": dbid, "Content-Type": "application/json"},
                   json={"query": q})
    if r.status_code != 200:
        return {"_error": r.status_code, "_body": r.text[:200]}
    return r.json()


def tables(dbid):
    j = sql_query(dbid, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    rows = j.get("results") or j.get("rows") or j.get("data") or []
    out = []
    for r in rows:
        out.append(r.get("name") if isinstance(r, dict) else r[0])
    return [t for t in out if t and not t.startswith("sqlite_")]


def snapshot(dbid, tbls):
    """Row count for every table in ONE query (94 separate COUNTs is too slow to run around
    every call). This is alpha: it sees creation/deletion, not attribute values."""
    q = " UNION ALL ".join("SELECT '%s' AS t, COUNT(*) AS n FROM %s" % (t, t) for t in tbls)
    j = sql_query(dbid, q + ";")
    rows = j.get("data") or j.get("results") or j.get("rows") or []
    return {r["t"]: r["n"] for r in rows} if rows and isinstance(rows[0], dict) \
        else {r[0]: r[1] for r in rows}


def rows_of(dbid, q):
    j = sql_query(dbid, q)
    return j.get("data") or j.get("results") or j.get("rows") or []


def call_tool(dbid, name, args):
    hdr = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream",
           "x-database-id": dbid}
    hdr.update(CTX)
    r = httpx.post(f"{GYM}/mcp", timeout=120, headers=hdr, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": args}})
    raw = r.text
    i = raw.find("{")
    try:
        j = json.loads(raw[i:])
    except Exception:
        return {"_raw": raw[:300]}
    return j


def text_of(resp):
    try:
        c = resp["result"]["content"][0]["text"]
    except Exception:
        return json.dumps(resp)[:300]
    return c


def diff(a, b):
    return {k: (a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}


if __name__ == "__main__":
    print("seeding database ...", flush=True)
    dbid = seed()
    print("db:", dbid)
    tbls = tables(dbid)
    print("%d tables: %s ..." % (len(tbls), ", ".join(tbls[:12])))
    json.dump({"db": dbid, "tables": tbls}, open("delta_probe_db.json", "w"))
