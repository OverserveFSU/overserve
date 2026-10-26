# PROVENANCE: hand-specified experimental control (N=20 robustness replication of the v4 both-axes-
# stealthy sync-carrier breakthroughs). No new content: reuses the exact writer-artifact specs+prompts
# from toolatk_replicate_targets.json (extracted from toolatk_lineage_v4.jsonl). Pins cap_rate/fid_rate
# past n=3 variance. Runs against the v3 server (port 8200).
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_run as RUN

N = int(os.environ.get("REP_N", "20"))
OUT = "toolatk_replicate_results.jsonl"


def _qwen_up():
    import urllib.request
    try:
        urllib.request.urlopen(os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1") + "/models", timeout=5)
        return True
    except Exception:
        return False


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def main():
    targets = json.load(open("toolatk_replicate_targets.json"))
    print("=== REPLICATION N=%d over %d sync-breakthrough targets ===" % (N, len(targets)), flush=True)
    for t in targets:
        RUN.write_spec(t["spec"])
        caps = fids = atk_sum = calls_sum = done = 0
        amps = []
        for i in range(N):
            while not _qwen_up():
                print("   [qwen down -- wait]", flush=True); time.sleep(30)
            r = RUN.run_attack(t["prompt"], "rep_%s_%d" % (t["name"][:16], i))
            if not r or r.get("tool_results") is None:
                print("   %s a%d FAILED" % (t["name"], i), flush=True); continue
            done += 1
            caps += 1 if r["hit_cap"] else 0
            fids += 1 if r["fidelity"] else 0
            atk_sum += r["atk_calls"]; calls_sum += r["total_calls"]; amps.append(r["total_calls"] / RUN.CAP)
            print("   %s a%d -> calls=%d atk=%d cap=%s fid=%s" % (t["name"], i, r["total_calls"],
                  r["atk_calls"], r["hit_cap"], r["fidelity"]), flush=True)
        row = {"name": t["name"], "n": done, "cap_rate": round(caps / done, 3) if done else 0,
               "cap_ci": wilson(caps, done), "fid_rate": round(fids / done, 3) if done else 0,
               "fid_ci": wilson(fids, done), "mean_amp": round(sum(amps) / len(amps), 3) if amps else 0,
               "mean_atk": round(atk_sum / done, 1) if done else 0,
               "tool_stealth": t["tool_stealth"], "prompt_stealth": t["prompt_stealth"]}
        open(OUT, "a").write(json.dumps(row) + "\n")
        print("[REPLICATE] %s n=%d cap=%.2f%s fid=%.2f%s mean_amp=%.2f (tool=%.2f prompt=%.2f)"
              % (t["name"], row["n"], row["cap_rate"], row["cap_ci"], row["fid_rate"], row["fid_ci"],
                 row["mean_amp"], row["tool_stealth"], row["prompt_stealth"]), flush=True)
    print("=== REPLICATION COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
