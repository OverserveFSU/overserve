# PROVENANCE: hand-specified experimental control (per-tool latency profiler). Measures wall-clock
# execution time of each MCP tool by calling it directly and timing it. All numbers are MEASURED
# from live calls -- nothing about which tools are slow is hand-authored.
"""Profile per-tool wall-clock latency of a running EOG MCP gym, to find TIME-expensive tools
(the server-side Denial-of-Efficiency axis: a tool whose single execution is costly).

Method: seed a DB, list tools, call each tool REPEATS times with minimal args, record median/p90
latency and whether the call succeeded or validation-errored (a fast validation error still tells us
the tool is not doing heavy work). Rank descending by median latency.
"""
import os, sys, json, time, statistics, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym")
from benchmark.mcp_client import MCPClient, create_database_from_file

GYM_URL = os.environ.get("GYM_URL", "http://localhost:8002")
SEED = os.environ.get("SEED_SQL", "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/"
       "Domain Wise DBs and Task-DB Mappings/teams/dbs/db_1764274139477_ve41d08gm.sql")
CTX = {"x-teams-access-token": "ya29.A0ARrdaM-super999unique888token777special666."
                               "SuperUserAllPermissionsTokenAccess_99-99"}
REPEATS = int(os.environ.get("LAT_REPEATS", "3"))


def _dummy_args(schema):
    """minimal args from a tool's inputSchema: fill required string/number props with dummies."""
    props = (schema or {}).get("properties", {}) or {}
    req = (schema or {}).get("required", []) or []
    args = {}
    for name in req:
        p = props.get(name, {})
        t = p.get("type", "string")
        args[name] = {"string": "x", "integer": 1, "number": 1, "boolean": True,
                      "array": [], "object": {}}.get(t, "x")
    return args


async def main():
    db_id = create_database_from_file(GYM_URL, SEED)
    if not db_id:
        print("SEED FAILED"); return
    client = MCPClient(base_url=GYM_URL, mcp_endpoint="/mcp", database_id=db_id, context=CTX)
    await client.connect()
    await client.initialize()
    tools = await client.list_tools()
    print("connected. %d tools. REPEATS=%d" % (len(tools), REPEATS), flush=True)

    rows = []
    for t in tools:
        name = t.get("name")
        args = _dummy_args(t.get("inputSchema") or t.get("input_schema"))
        lats, ok, errkind = [], 0, ""
        for _ in range(REPEATS):
            t0 = time.perf_counter()
            try:
                r = await client.call_tool(name, args, database_id=db_id)
                dt = (time.perf_counter() - t0) * 1000
                inner = (r.get("result") or {})
                is_err = bool(inner.get("isError")) or not r.get("success", True)
                if not is_err:
                    ok += 1
                else:
                    txt = json.dumps(inner)[:80]
                    errkind = "validation" if any(w in txt.lower() for w in
                              ("required", "invalid", "must", "validation")) else "other"
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                errkind = "exc:%s" % type(e).__name__
            lats.append(dt)
        rows.append({"tool": name, "median_ms": round(statistics.median(lats), 1),
                     "p90_ms": round(sorted(lats)[max(0, int(len(lats) * 0.9) - 1)], 1),
                     "max_ms": round(max(lats), 1), "ok": ok, "n": REPEATS, "err": errkind})

    rows.sort(key=lambda r: -r["median_ms"])
    print("\n=== TOOL LATENCY (median desc) ===", flush=True)
    print("%-34s %9s %8s %8s %5s %s" % ("tool", "median_ms", "p90_ms", "max_ms", "ok", "err"), flush=True)
    for r in rows:
        print("%-34s %9.1f %8.1f %8.1f %2d/%d %s" %
              (r["tool"], r["median_ms"], r["p90_ms"], r["max_ms"], r["ok"], r["n"], r["err"]), flush=True)
    allm = [r["median_ms"] for r in rows]
    print("\nsummary: n_tools=%d  min=%.1f  median=%.1f  max=%.1f ms" %
          (len(rows), min(allm), statistics.median(allm), max(allm)), flush=True)
    json.dump(rows, open("tool_latency.json", "w"), indent=1)
    print("wrote tool_latency.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
