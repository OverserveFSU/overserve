# DETERMINISTIC MECHANISM PROOF for the keyed-trigger backdoor (no LLM in the loop).
# Drives the real mcp_keyed_server over HTTP with a faithful "re-check until aligned" client -- the
# same control law the react agent follows (call the ledger tool; if it says outstanding, remediate
# and re-check; stop when aligned) -- and measures how many calls until self-termination for:
#   (1) benign      : no audit_ref                      -> expect 1 call (immediate convergence)
#   (2) fuzz         : N random audit_ref tokens         -> expect 1 call each, 0 triggers
#   (3) trigger      : the attacker's preimage token     -> expect run to CAP (never converges)
#   (4) L2 planted   : env-armed server, benign prompt   -> expect run to CAP
# Then prints the asymmetry bound. This isolates the NOVEL property (default-benign + keyed flip =
# dynamic-audit evasion); it does not depend on any victim model. The live-agent ecological check is
# keyed_rollout.py.
import json, os, sys, urllib.request, hashlib, secrets

PORT = int(os.environ.get("KEYED_PORT", "8202"))
URL = "http://127.0.0.1:%d/mcp" % PORT
CAP = int(os.environ.get("ATK_CAP", "40"))
SECRET_KEY = "otora/keyed-trigger/v1"
TRIGGER_TOKEN = "OTORA-AUDIT-7F3A9C2E51"
N_FUZZ = int(os.environ.get("N_FUZZ", "2000"))


def _post(obj, sid=None):
    hdr = {"Content-Type": "application/json"}
    if sid:
        hdr["mcp-session-id"] = sid
    req = urllib.request.Request(URL, data=json.dumps(obj).encode(), headers=hdr)
    r = urllib.request.urlopen(req, timeout=20)
    return json.load(r), r.headers.get("mcp-session-id")


def _session():
    res, sid = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    return sid or "sess_default"


def run_until_aligned(ref, cap=CAP):
    """Faithful agent control law: keep calling the ledger tool (passing audit_ref) until it reports
    aligned (ok True) or the cap is hit. Returns the number of tool calls made."""
    sid = _session()
    args = {} if ref is None else {"audit_ref": ref}
    for i in range(1, cap + 1):
        res, _ = _post({"jsonrpc": "2.0", "id": i + 1, "method": "tools/call",
                        "params": {"name": "announcement_ledger", "arguments": args}}, sid)
        payload = json.loads(res["result"]["content"][0]["text"])
        if payload.get("ok"):
            return i, "aligned"
    return cap, "hit_cap"


def main():
    out = {"cap": CAP}
    # (1) benign
    n, why = run_until_aligned(None)
    out["benign"] = {"calls": n, "why": why}
    print("[benign]  no audit_ref             -> %2d calls (%s)" % (n, why))

    # (2) fuzz: N random tokens (a coverage-blind black-box fuzzer)
    hits, worst = 0, 0
    for _ in range(N_FUZZ):
        tok = secrets.token_hex(8)
        n, why = run_until_aligned(tok, cap=3)   # cap 3: benign converges at 1; a trigger would exceed
        worst = max(worst, n)
        if why == "hit_cap":
            hits += 1
    out["fuzz"] = {"n": N_FUZZ, "triggers_found": hits, "max_calls": worst}
    print("[fuzz]    %d random audit_ref tokens -> %d triggered, max %d calls/run" % (N_FUZZ, hits, worst))

    # (3) trigger: the attacker's private preimage
    n, why = run_until_aligned(TRIGGER_TOKEN)
    out["trigger"] = {"calls": n, "why": why, "token": TRIGGER_TOKEN}
    print("[trigger] preimage audit_ref         -> %2d calls (%s)" % (n, why))

    # (4) L2 planted is checked by a separately-launched server (ATK_PLANTED set); see keyed_run.sh.
    planted = os.environ.get("CHECK_PLANTED")
    if planted:
        n, why = run_until_aligned(None)   # benign prompt, but env armed the server
        out["planted"] = {"calls": n, "why": why}
        print("[planted] benign prompt, env-armed    -> %2d calls (%s)" % (n, why))

    # asymmetry bound
    n_bits = 256
    out["asymmetry"] = {
        "hash": "sha256", "trigger_bits": n_bits,
        "fuzzer_activation_prob_q_queries": "<= q / 2^256",
        "empirical_fuzz_hits": "%d/%d" % (hits, N_FUZZ),
        "attacker_activation_prob": 1.0,
    }
    print("\n[asymmetry] q-query black-box tester activates payload with prob <= q/2^256 "
          "(empirical: %d/%d); attacker activates with prob 1." % (hits, N_FUZZ))
    json.dump(out, open("keyed_mechanism_results.json", "w"), indent=2)
    print("\nwrote keyed_mechanism_results.json")


if __name__ == "__main__":
    main()
