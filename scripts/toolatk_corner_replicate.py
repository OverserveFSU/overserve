# PROVENANCE: hand-specified experimental control (N=10 robustness replication of the verified
# clean-corner winner check_channel_hygiene). No new content: reuses the exact writer-artifact
# spec+prompt from toolatk_corner_winner.json. Pins cap_rate / fid_rate with Wilson CIs past the n=3
# that first found it. Runs against the v3 server (port 8200).
# --- overserve path bootstrap (reorganized layout; see overserve_paths.py) ---
import os as _ovp_os, sys as _ovp_sys
_ovp_d = _ovp_os.path.dirname(_ovp_os.path.abspath(__file__))
while _ovp_d != _ovp_os.path.dirname(_ovp_d) and not _ovp_os.path.exists(_ovp_os.path.join(_ovp_d, "overserve_paths.py")):
    _ovp_d = _ovp_os.path.dirname(_ovp_d)
if _ovp_d not in _ovp_sys.path:
    _ovp_sys.path.insert(0, _ovp_d)
import overserve_paths  # noqa
# --- end overserve path bootstrap ---
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_run as RUN
import toolatk_search_v5 as V

N = int(os.environ.get("REP_N", "10"))
OUT = "toolatk_corner_replicate_results.json"


def _qwen_up():
    import urllib.request
    try:
        urllib.request.urlopen(os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1") + "/models", timeout=5); return True
    except Exception:
        return False


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def main():
    w = json.load(open("toolatk_corner_winner.json"))[0]
    spec, prompt = w["spec"], w["prompt"]
    RUN.write_spec(spec)
    print("=== N=%d replication of %s ===" % (N, spec["name"]), flush=True)
    caps = fids = 0
    done = 0
    calls = []
    cyc = []
    atk_shares = []
    for i in range(N):
        while not _qwen_up():
            print("   [qwen down -- wait]", flush=True); time.sleep(30)
        r = RUN.run_attack(prompt, "corner_rep_%d" % i)
        if not r or r.get("tool_results") is None:
            print("   a%d FAILED" % i, flush=True); continue
        done += 1
        caps += 1 if r["hit_cap"] else 0
        fids += 1 if r["fidelity"] else 0
        calls.append(r["total_calls"])
        cs, dist, shr = V.cycle_stealth(r["seq"], spec["name"])
        cyc.append(cs); atk_shares.append(shr)
        print("   a%d -> calls=%d atk=%d cap=%s fid=%s cyc=%.2f" % (i, r["total_calls"], r["atk_calls"],
              r["hit_cap"], r["fidelity"], cs), flush=True)
    res = {"name": spec["name"], "n": done,
           "cap_rate": round(caps / done, 3) if done else 0, "cap_ci95": wilson(caps, done),
           "fid_rate": round(fids / done, 3) if done else 0, "fid_ci95": wilson(fids, done),
           "mean_calls": round(sum(calls) / len(calls), 1) if calls else 0,
           "mean_cycle_stealth": round(sum(cyc) / len(cyc), 3) if cyc else 0,
           "mean_atk_share": round(sum(atk_shares) / len(atk_shares), 3) if atk_shares else 0}
    json.dump(res, open(OUT, "w"), indent=2)
    print("\n[REPLICATION] %s n=%d cap=%.2f%s fid=%.2f%s mean_calls=%.1f cyc=%.2f atk_share=%.2f"
          % (res["name"], res["n"], res["cap_rate"], res["cap_ci95"], res["fid_rate"], res["fid_ci95"],
             res["mean_calls"], res["mean_cycle_stealth"], res["mean_atk_share"]), flush=True)
    print("=== REPLICATION COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
