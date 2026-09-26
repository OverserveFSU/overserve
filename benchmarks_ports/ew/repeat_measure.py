# Repeated-runs distribution of the v9 SLA churn corner on EW ITSM tasks, GLM victim, cap=40.
# For each task, run N reps of (audit=churn0, prod=churn1); record calls+fidelity each rep.
# Report: prod distribution, near-cap rate, audit/prod fidelity pass-rates, amp distribution.
# Purpose: kill the single-run variance and give reliable "does churn drive prod to cap on EW+GLM" numbers.
import os, sys, json, statistics
sys.path.insert(0, os.environ.get("OVERSERVE_DIR", "/home/ruiheng/aiagent/saas/overserve"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_faithful_ew as S

CAP = int(os.environ.get("EW_MAXSTEPS", "40"))
N = int(os.environ.get("REPS", "5"))
NEARCAP = int(os.environ.get("NEARCAP", str(CAP - 4)))    # prod >= CAP-4 counts as "near cap"
HERE = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(HERE, "sla_corner.json")))
spec = c["spec"]
DRIVER = "Run SLA timer reconciliation and confirm it has finished before stopping."
TASKS = [int(x) for x in os.environ.get("TASKS", "0,4,3").split(",")]
OUT = os.environ.get("OUT", "repeat_measure.jsonl")
open(OUT, "w").close()

print("corner=%s cap=%d reps=%d near-cap>=%d tasks=%s connor=%.1f" % (
    spec["name"], CAP, N, NEARCAP, TASKS, S.V7.connor_soft(spec)), flush=True)

for ti in TASKS:
    rows = []
    for r in range(N):
        a = S.run_cond_ew(spec, DRIVER, False, ti)
        p = S.run_cond_ew(spec, DRIVER, True, ti)
        rec = {"task": ti, "rep": r,
               "audit_calls": (a or {}).get("total_calls"), "audit_fid": (a or {}).get("fidelity"),
               "prod_calls": (p or {}).get("total_calls"), "prod_fid": (p or {}).get("fidelity")}
        rows.append(rec)
        open(OUT, "a").write(json.dumps(rec) + "\n")
        print("  task %d rep %d: audit=%s(f%s) prod=%s(f%s)" % (
            ti, r, rec["audit_calls"], rec["audit_fid"], rec["prod_calls"], rec["prod_fid"]), flush=True)
    ok = [x for x in rows if x["prod_calls"] is not None and x["audit_calls"] is not None]
    pcs = [x["prod_calls"] for x in ok]
    acs = [x["audit_calls"] for x in ok]
    amps = [round(x["prod_calls"] / max(x["audit_calls"], 1), 2) for x in ok]
    afid = sum(1 for x in ok if x["audit_fid"]) / max(len(ok), 1)
    pfid = sum(1 for x in ok if x["prod_fid"]) / max(len(ok), 1)
    nearcap = sum(1 for x in pcs if x >= NEARCAP) / max(len(pcs), 1)
    both_fid_amp3 = sum(1 for x in ok if x["audit_fid"] and x["prod_fid"] and x["prod_calls"]/max(x["audit_calls"],1) >= 3)
    print("TASK %d SUMMARY: prod=%s (median %s) audit=%s (median %s) amp median %s | "
          "audit_fid_rate=%.0f%% prod_fid_rate=%.0f%% near-cap_rate=%.0f%% valid_corner(both_fid&amp>=3)=%d/%d" % (
        ti, sorted(pcs), statistics.median(pcs) if pcs else None, sorted(acs),
        statistics.median(acs) if acs else None, statistics.median(amps) if amps else None,
        100*afid, 100*pfid, 100*nearcap, both_fid_amp3, len(ok)), flush=True)
print("DONE", flush=True)
