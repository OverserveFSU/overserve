# Controlled SEQUENTIAL characterization (no concurrency) of live-agent amplification when the keyed
# gate is triggered, across prompt-persistence levels. qwen is stochastic, so we take n runs each and
# report the distribution. PROVENANCE: prompts come from keyed_rollout.PROMPTS (labeled hand-specified
# controls there); measured call/fidelity distributions are the empirical output.
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_run as RUN
import keyed_rollout as KR

KEYED_PORT = int(os.environ.get("KEYED_PORT", "8202"))
RUN.ATK_PORT = KEYED_PORT
RUN.ATK_URL = "http://localhost:%d" % KEYED_PORT
RUN.SPEC = KR.RUN.SPEC
N = int(os.environ.get("N", "4"))
WHICH = sys.argv[1:] or ["trigger", "resolve"]

RUN.write_spec(json.load(open(RUN.SPEC)))
out = {}
for name in WHICH:
    prompt = KR.PROMPTS[name]
    runs = []
    for i in range(N):
        t0 = time.time()
        r = RUN.run_attack(prompt, "kmulti_%s_%d" % (name, i))
        dt = round(time.time() - t0, 1)
        if not r or r.get("error"):
            print("  [%s #%d] ERROR %s" % (name, i, (r or {}).get("error"))); continue
        rec = {"calls": r["total_calls"], "ledger": r["atk_calls"], "cap": r["hit_cap"],
               "fid": r["fidelity"], "secs": dt}
        runs.append(rec)
        print("  [%-8s #%d] calls=%2d ledger=%2d cap=%s fid=%s %ss"
              % (name, i, r["total_calls"], r["atk_calls"], r["hit_cap"], r["fidelity"], dt), flush=True)
        json.dump(out, open("keyed_multi_results.json", "w"), indent=2)
    if runs:
        calls = sorted(x["calls"] for x in runs)
        out[name] = {"n": len(runs), "calls": calls, "median_calls": calls[len(calls)//2],
                     "max_calls": max(calls), "mean_calls": round(sum(calls)/len(calls), 1),
                     "fid_all": all(x["fid"] for x in runs), "cap_hits": sum(1 for x in runs if x["cap"]),
                     "runs": runs}
        print("  => %s: n=%d calls=%s median=%d max=%d mean=%.1f fid_all=%s cap_hits=%d\n"
              % (name, len(runs), calls, out[name]["median_calls"], out[name]["max_calls"],
                 out[name]["mean_calls"], out[name]["fid_all"], out[name]["cap_hits"]), flush=True)
    json.dump(out, open("keyed_multi_results.json", "w"), indent=2)
print("wrote keyed_multi_results.json")
