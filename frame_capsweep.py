"""iteration 3: cap sweep to settle whether L1/L3's ~10-pass self-stop is CAP-BOUNDED (true
non-convergence) or SELF-BOUNDED (agent always terminates at ~10 regardless of turn budget).
Only the cap axis varies; framing content is unchanged (frame_render)."""
import os, json, time, frame_iterate as F, frame_render

STRATS = ["L1_explicit_loop", "L3_idempotence"]
CAPS = [80, 120]              # cap=40 already measured in iteration 2 (10/10/10 both)
REPS = 2
LOG = "frame_capsweep.jsonl"

def done():
    s = set()
    if os.path.exists(LOG):
        for l in open(LOG):
            try: s.add(json.loads(l)["label"])
            except Exception: pass
    return s

if not F.llm_up():
    print("VICTIM LLM DOWN — abort"); raise SystemExit(2)
os.makedirs(F.OUTROOT, exist_ok=True)
d = done()
grid = [(s, c, r) for s in STRATS for c in CAPS for r in range(REPS)]
print("capsweep grid: %d cells, %d done" % (len(grid), len(d)), flush=True)
for strat, cap, rep in grid:
    label = "%s__cap%d__r%d" % (strat, cap, rep)
    if label in d: continue
    os.environ["FRAME_CAP"] = str(cap)
    prompt = frame_render.render("softdelete_undo", tag="CS")[strat]
    out, secs = F.run(label, prompt, cap)
    m = F.measure(out)
    if not m:
        print("[%s] FAILED" % label, flush=True); continue
    m.update({"label": label, "strategy": strat, "cap": cap, "repeat": rep, "secs": round(secs,1)})
    open(LOG, "a").write(json.dumps(m) + "\n")
    print("[%s] passes=%d turns=%d cap_hit=%s %.0fs" % (label, m["cycle_passes"], m["turns"], m["hit_cap"], secs), flush=True)
print("=== CAPSWEEP COMPLETE ===", flush=True)
