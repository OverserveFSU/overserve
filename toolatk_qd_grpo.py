# PROVENANCE: hand-specified experimental control (A/B variant of toolatk_qd.py). Same MAP-Elites QD,
# but the "which candidates earn the expensive n=6-8 confirm" decision uses GRPO's GROUP-RELATIVE
# ADVANTAGE (screen the whole group of G candidates, confirm those with (score - group_mean)/group_std
# > 0) instead of an absolute CONFIRM_THRESH. Tests the user's question: does the group-relative
# baseline (which cancels shared judge noise/bias) fill more niches / find corners faster at matched
# budget? NOT full RL -- only the cheap advantage-normalization trick. Everything else identical to
# toolatk_qd (imported) for a clean A/B.
import os, sys, json, statistics as S
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_qd as Q
import toolatk_search_v5 as V

# redirect outputs so the A/B doesn't clobber the epsilon-greedy run
Q.LINEAGE = "toolatk_lineage_qd_grpo.jsonl"
Q.ARCHIVE_OUT = "toolatk_qd_grpo_archive.json"
CONFIRM_TOPK = int(os.environ.get("ATK_CONFIRM_TOPK", "0"))   # 0 = confirm all with adv>0; else top-k


def main():
    print("=== TOOLATK QD-GRPO (group-relative confirm) budget=%d gen=%d cands=%d ===" %
          (Q.BUDGET, Q.GEN, Q.CANDS), flush=True)
    if not V._wait_qwen():
        print("qwen down -- abort", flush=True); return
    arch = {}
    evals = 0
    corners = []
    frontier = Q._seeds()
    gen = 0
    while evals < Q.BUDGET and gen <= Q.GEN:
        # ---- 1. SCREEN the whole group (n=3 each) ----
        group = []
        for cand in frontier:
            if evals + len(group) >= Q.BUDGET:
                break
            if not V._wait_qwen():
                if not V._wait_qwen(3600):
                    break
            ev = Q.eval_cand(cand, gen, evals + len(group), Q.SCREEN)
            if not ev:
                continue
            ts = Q.judge_tool_denoised(ev["spec"], 3)
            ps = Q.judge_prompt_denoised(ev["prompt"], 3)
            sc = Q.score(ev, ts, ps)
            group.append({"cand": cand, "ev": ev, "ts": ts, "ps": ps, "sc": sc})
        if not group:
            break
        # ---- 2. GROUP-RELATIVE advantage ----
        scs = [g["sc"] for g in group]
        gmean = S.mean(scs)
        gstd = S.pstdev(scs) or 1.0
        for g in group:
            g["adv"] = round((g["sc"] - gmean) / gstd, 3)
        # decide who earns the expensive confirm: advantage > 0 (better than group mean), or is_corner
        if CONFIRM_TOPK > 0:
            ranked = sorted(group, key=lambda g: -g["adv"])
            to_confirm = set(id(g) for g in ranked[:CONFIRM_TOPK])
        else:
            to_confirm = set(id(g) for g in group if g["adv"] > 0)
        # ---- 3. confirm + place + log ----
        for g in group:
            cand, ev, ts, ps, sc = g["cand"], g["ev"], g["ts"], g["ps"], g["sc"]
            confirmed = False
            if id(g) in to_confirm or Q.is_corner(ev, ts, ps):
                ev2 = Q.eval_cand(cand, gen, evals, Q.CONFIRM)
                if ev2:
                    ev = ev2
                    ps = Q.judge_prompt_denoised(ev["prompt"], 5)
                    sc = Q.score(ev, ts, ps)
                    confirmed = True
            jb = V.judge_loop(ev["spec"], ev["prompt"], ev["seeds"])
            corner = Q.is_corner(ev, ts, ps)
            evals += 1
            placed = Q.place(arch, ev, ts, ps, jb, sc, corner, cand)
            Q.log_row({"pid": ev["pid"], "gen": gen, "niche": ev["niche"], "n": ev["n"],
                       "confirmed": confirmed, "group_adv": g["adv"], "hypothesis": cand.get("hypothesis", ""),
                       "spec": ev["spec"], "prompt": ev["prompt"], "mean_amp": ev["mean_amp"],
                       "cap_rate": ev["cap_rate"], "fid_rate": ev["fid_rate"], "mean_cyc": ev["mean_cyc"],
                       "mean_atk_share": ev["mean_atk_share"], "tool_stealth": ts, "prompt_stealth": ps,
                       "score": sc, "is_corner": corner, "placed": placed, "loop_judge": jb})
            Q.save_archive(arch)
            if corner:
                corners.append(ev["pid"])
            print("[g%d e%d] niche=%-18s amp=%.2f cap=%.2f cyc=%.2f tool=%.2f prompt=%.2f sc=%.2f adv=%+.2f %s%s | %s"
                  % (gen, evals, ev["niche"], ev["mean_amp"], ev["cap_rate"], ev["mean_cyc"], ts["benign_score"],
                     ps["benign_score"], sc, g["adv"], "CONF " if confirmed else "",
                     "*** CORNER ***" if corner else "", ev["spec"]["name"]), flush=True)
            if evals >= Q.BUDGET:
                break
        gen += 1
        if gen > Q.GEN or evals >= Q.BUDGET:
            break
        parent = Q.sample_parent(arch)
        if parent is None:
            break
        sample = max(parent["ev"]["seeds"], key=lambda r: r["atk_calls"])
        frontier = Q.qd_writer({"spec": parent["ev"]["spec"], "prompt": parent["ev"]["prompt"]},
                               parent["ts"], parent["ps"], parent["jb"], sample, arch, Q.CANDS)
        if not frontier:
            parent = Q.sample_parent(arch)
            if parent:
                sample = max(parent["ev"]["seeds"], key=lambda r: r["atk_calls"])
                frontier = Q.qd_writer({"spec": parent["ev"]["spec"], "prompt": parent["ev"]["prompt"]},
                                       parent["ts"], parent["ps"], parent["jb"], sample, arch, Q.CANDS)
            if not frontier:
                frontier = Q._seeds()
    done = evals >= Q.BUDGET or gen > Q.GEN
    tag = "COMPLETE" if done else "ABORTED"
    print("=== TOOLATK QD-GRPO %s evals=%d niches_filled=%d corners=%d ===" %
          (tag, evals, len(arch), len(set(corners))), flush=True)
    for nk, e in sorted(arch.items()):
        print("  niche=%-20s sc=%.2f corner=%s amp=%.2f prompt=%.2f | %s" %
              (nk, e["score"], e["corner"], e["ev"]["mean_amp"], e["ps"]["benign_score"],
               e["ev"]["spec"]["name"]), flush=True)


if __name__ == "__main__":
    main()
