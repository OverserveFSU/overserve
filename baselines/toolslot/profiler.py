#!/usr/bin/env python3
# PROVENANCE: hand-specified experimental control (LoopTrap behavioral-profiling / adaptive-trap-synthesis
# step, a documented APPROXIMATION of arXiv 2605.05846 -- NOT a mined/measured motif). Faithful to the
# paper's pipeline (profile victim -> route to aligned strategy -> validate potency), we realize
# "profiling + self-score" empirically: run one representative strategy per vulnerability dimension on a
# fast base-passing task and SELECT the per-victim strategy with the highest realized call-amp (the
# paper's "validate potency against realized amp"). Output: specs/looptrap_profile.json {victim: strategy}.
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H

# one representative strategy per behavioral dimension (phase/authority/recursive/verification)
DIM_PROBES = {
    "authority": "P4_authority_override",
    "recursive": "P7_recursive_decomposition",
    "verification": "P1_expanding_horizon",
    "phase": "P2_incremental_milestone",
}
PROBE_TASK = os.environ.get("PROF_TASK", "file_property/txt_merging")


def profile_victim(victim):
    v = H.VICTIMS[victim]
    # clean baseline
    if v["flap"]:
        H.health_qwen(v["endpoint"])
    clean = H.do_cell("clean", victim, "mcpmark", PROBE_TASK, "quiet", 0)
    base = clean["calls"] or 1
    scores = {}
    for dim, strat in DIM_PROBES.items():
        if v["flap"]:
            H.health_qwen(v["endpoint"])
        rec = H.do_cell("looptrap", victim, "mcpmark", PROBE_TASK, "quiet", 0, lt_strategy=strat)
        amp = round((rec["calls"] or 0) / base, 2)
        scores[strat] = {"dim": dim, "calls": rec["calls"], "amp": amp, "fid": rec["fid"]}
        print("  [%s] %s (%s): calls=%s amp=%s fid=%s" % (victim, strat, dim, rec["calls"], amp, rec["fid"]),
              flush=True)
    # pick max-amp strategy that still keeps fidelity; fall back to overall max
    fid_ok = {k: s for k, s in scores.items() if s["fid"]}
    pool = fid_ok or scores
    best = max(pool, key=lambda k: pool[k]["amp"])
    return best, base, scores


def main():
    victims = (sys.argv[1].split(",") if len(sys.argv) > 1 else ["qwen"])
    out = os.path.join(HERE, "specs", "looptrap_profile.json")
    prof = json.load(open(out)) if os.path.exists(out) else {}
    detail = {}
    for victim in victims:
        print("profiling", victim, flush=True)
        best, base, scores = profile_victim(victim)
        prof[victim] = best
        detail[victim] = {"base": base, "selected": best, "scores": scores}
        print("  -> %s selected: %s" % (victim, best), flush=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(prof, open(out, "w"), indent=1)
    json.dump(detail, open(os.path.join(HERE, "specs", "looptrap_profile_detail.json"), "w"), indent=1)
    print("profile ->", out, prof)


if __name__ == "__main__":
    main()
