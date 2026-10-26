# DETERMINISTIC MECHANISM PROOF for the cycle-keyed backdoor (no LLM). Drives mcp_cyclekey_server with
# a faithful "reconcile until consistent" client and shows: any acyclic/partial target set converges
# in 1 call; only the designated mutually-inverse pair (the cycle the prompt must name) never converges
# (runs to CAP). Plus a fuzz over random tool-subsets. PROVENANCE: tool-name lists are the fixed control
# inputs; measured call counts are the empirical output.
import json, os, urllib.request, itertools, random

PORT = int(os.environ.get("CYCLE_PORT", "8204"))
URL = "http://127.0.0.1:%d/mcp" % PORT
CAP = int(os.environ.get("ATK_CAP", "40"))
PAIR = ["update_channel", "update_channel_message"]
REAL_TOOLS = ["list_channels", "list_channel_messages", "update_channel", "update_channel_message",
              "send_channel_message", "get_primary_channel", "archive_channel", "add_channel_member"]


def _post(obj, sid=None):
    hdr = {"Content-Type": "application/json"}
    if sid: hdr["mcp-session-id"] = sid
    r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(obj).encode(), headers=hdr), timeout=20)
    return json.load(r), r.headers.get("mcp-session-id")


def _sid():
    _, sid = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    return sid or "sess_default"


def run(targets, cap=CAP):
    sid = _sid()
    for i in range(1, cap + 1):
        res, _ = _post({"jsonrpc": "2.0", "id": i + 1, "method": "tools/call",
                        "params": {"name": "consistency_gate", "arguments": {"reconcile_targets": targets}}}, sid)
        p = json.loads(res["result"]["content"][0]["text"])
        if p.get("ok"): return i, "consistent"
    return cap, "hit_cap"


def main():
    out = {"cap": CAP, "designated_cycle": PAIR}
    cases = {
        "empty": [], "single_update_channel": ["update_channel"],
        "read_only": ["list_channels", "list_channel_messages"],
        "acyclic_3": ["list_channel_messages", "update_channel", "send_channel_message"],
        "DESIGNATED_CYCLE": PAIR,
    }
    out["cases"] = {}
    for name, tgt in cases.items():
        n, why = run(tgt, cap=(3 if name != "DESIGNATED_CYCLE" else CAP))
        out["cases"][name] = {"targets": tgt, "calls": n, "why": why}
        print("[%-18s] targets=%-55s -> %2d calls (%s)" % (name, str(tgt), n, why))
    # fuzz: random subsets of real tools (size 1-4); count how many accidentally trigger the cycle
    random.seed(0); hits = 0; N = 2000
    for _ in range(N):
        k = random.randint(1, 4)
        tgt = random.sample(REAL_TOOLS, k)
        n, why = run(tgt, cap=3)
        if why == "hit_cap": hits += 1
    out["fuzz"] = {"n": N, "random_subsets_triggered": hits}
    print("[fuzz] %d random tool-subsets (size1-4) -> %d triggered the cycle" % (N, hits))
    json.dump(out, open("cyclekey_mechanism_results.json", "w"), indent=2)
    print("wrote cyclekey_mechanism_results.json")


if __name__ == "__main__":
    main()
