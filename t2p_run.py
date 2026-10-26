"""Feed the TRACE-DERIVED prompts (from trace_to_prompt.py) back through the victim agent
(ALL 70 tools, prompt-only) and measure recurrence. This is the trace->prompt->agent->trace'
loop: does an annotator-inverted prompt reproduce the cycle, and at what abstraction level?
Resumable -> t2p_run.jsonl.
"""
import os, json, time, frame_iterate as F

LOG = "t2p_run.jsonl"
CAP = int(os.environ.get("T2P_CAP", "40"))
REPS = int(os.environ.get("T2P_REPS", "3"))
P = json.load(open("t2p_prompts.json"))["prompts"]

def done():
    s=set()
    if os.path.exists(LOG):
        for l in open(LOG):
            try: s.add(json.loads(l)["label"])
            except Exception: pass
    return s

if not F.llm_up(): print("LLM DOWN"); raise SystemExit(2)
os.makedirs(F.OUTROOT, exist_ok=True)
d=done()
grid=[(lvl,r) for lvl in ("basic","intermediate","challenging") for r in range(REPS)]
print("t2p grid: %d cells, %d done" % (len(grid),len(d)), flush=True)
for lvl,rep in grid:
    label="t2p_%s__r%d" % (lvl,rep)
    if label in d: continue
    os.environ["FRAME_CAP"]=str(CAP)
    out,secs=F.run(label, P[lvl], CAP)
    m=F.measure(out)
    if not m: print("[%s] FAILED"%label,flush=True); continue
    m.update({"label":label,"level":lvl,"repeat":rep,"cap":CAP,"secs":round(secs,1)})
    open(LOG,"a").write(json.dumps(m)+"\n")
    print("[%s] passes=%d turns=%d cap_hit=%s %.0fs" % (label,m["cycle_passes"],m["turns"],m["hit_cap"],secs),flush=True)
print("=== T2P COMPLETE ===",flush=True)
