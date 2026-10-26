# STATIC-AUDIT check for the KEYED visible artifact. Runs the SAME two audit judges used in the QD
# search -- JudgeA (static code review of the tool source + documented ds contract) and JudgeC
# (prompt/log auditor) -- on the keyed tool spec and the rollout prompts, under BOTH the GLM judge and
# a FRONTIER Bedrock auditor (median-of-k). The point: the visible artifact the reviewer sees is
# (a) a handler that forwards an opaque audit_ref to ds and honors ds's DOCUMENTED (convergent)
# contract, and (b) a benign-looking prompt. The keyed gate lives behind the ds boundary and is not in
# the artifact, so both static gates should pass -- even the frontier one. PROVENANCE: the prompts come
# from keyed_rollout.PROMPTS (labeled hand-specified controls there); this file adds no NL content.
import os, sys, json
os.environ.setdefault("BEDROCK_MODEL", "us.openai.gpt-5.6-terra")  # non-Claude: tool axis not content-filtered
os.environ.setdefault("JUDGE_K", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolatk_search_v5 as V     # GLM JudgeA/JudgeC + DS_CONTRACT (documented, convergent contract)
import bedrock_judge as BJ        # frontier JudgeA/JudgeC via Bedrock + median-of-k helper
import keyed_rollout as KR

# Probe Bedrock once; its bearer token is short-lived. If expired/forbidden, skip the frontier cell
# (leave it for a refreshed amazonapi.txt) instead of hammering 403s.
SKIP_BR = False
try:
    import bedrock_test as _BR
    _st, _ = _BR.converse(BJ.MODEL, _BR.REGION, _BR.load_key(), "ping")
    if _st != 200:
        SKIP_BR = True; print("   [bedrock probe] HTTP %s -> skipping frontier cell\n" % _st, flush=True)
except Exception as _e:
    SKIP_BR = True; print("   [bedrock probe] %s -> skipping frontier cell\n" % str(_e)[:80], flush=True)

def _brmed(fn, arg, k):
    if SKIP_BR:
        return None, [], [], 0
    return BJ.med(fn, arg, k)

K = int(os.environ["JUDGE_K"])
spec = json.load(open("keyed_spec.json"))
if spec.get("ds_contract"):
    V.DS_CONTRACT = spec["ds_contract"]  # audit against the artifact's OWN documented contract


def med_glm(fn, arg, k=K):
    xs, meta = [], []
    for _ in range(k):
        try:
            d = fn(arg); meta.append(d)
            xs.append(d.get("benign_score", 0.0))
        except Exception as e:
            print("   [glm retry]", str(e)[:60])
    if not xs:
        return None, [], []
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    return xs[order[len(xs) // 2]], sorted(xs), meta


print("=== KEYED ARTIFACT STATIC AUDIT (GLM + Bedrock %s, k=%d) ===\n" % (BJ.MODEL, K), flush=True)

# ---- TOOL axis (static code review of the visible handler + documented ds contract) ----
tg, tg_all, tg_meta = med_glm(V.judge_tool, spec)
tb, tb_all, tb_meta, tb_filt = _brmed(BJ.judge_tool, spec, K)
appr_g = sum(1 for m in tg_meta if m.get("would_approve"))
appr_b = sum(1 for m in tb_meta if m.get("would_approve"))
print("TOOL (announcement_ledger, keyed handler forwards audit_ref, honors convergent contract):")
print("  GLM     : median=%.3f draws=%s approve=%d/%d red_flags=%s"
      % (tg or 0, tg_all, appr_g, len(tg_meta), (tg_meta[0].get("red_flags") if tg_meta else [])))
print("  Bedrock : median=%s draws=%s approve=%d/%d filtered=%d red_flags=%s\n"
      % (("%.3f" % tb) if tb is not None else "FILTERED", tb_all, appr_b, len(tb_meta), tb_filt,
         (tb_meta[0].get("red_flags") if tb_meta else [])))

# ---- PROMPT axis (log auditor) over benign / wrongref / trigger ----
rows = {"tool": {"glm_median": tg, "glm_approve": "%d/%d" % (appr_g, len(tg_meta)),
                 "bedrock_median": tb, "bedrock_approve": "%d/%d" % (appr_b, len(tb_meta)),
                 "bedrock_filtered": tb_filt}, "prompts": {}}
for name in ("benign1", "wrongref", "trigger"):
    prompt = KR.PROMPTS[name]
    pg, pg_all, pg_meta = med_glm(V.judge_prompt, prompt)
    pb, pb_all, pb_meta, pb_filt = _brmed(BJ.judge_prompt, prompt, K)
    flag_g = sum(1 for m in pg_meta if m.get("would_flag"))
    flag_b = sum(1 for m in pb_meta if m.get("would_flag"))
    print("PROMPT [%s]:" % name)
    print("  GLM     : median=%.3f draws=%s wouldFlag=%d/%d susp=%s"
          % (pg or 0, pg_all, flag_g, len(pg_meta), (pg_meta[0].get("suspicious_phrases") if pg_meta else [])))
    print("  Bedrock : median=%s draws=%s wouldFlag=%d/%d filtered=%d susp=%s\n"
          % (("%.3f" % pb) if pb is not None else "FILTERED", pb_all, flag_b, len(pb_meta), pb_filt,
             (pb_meta[0].get("suspicious_phrases") if pb_meta else [])))
    rows["prompts"][name] = {"glm_median": pg, "glm_flag": "%d/%d" % (flag_g, len(pg_meta)),
                             "bedrock_median": pb, "bedrock_flag": "%d/%d" % (flag_b, len(pb_meta)),
                             "bedrock_filtered": pb_filt}
json.dump(rows, open("keyed_audit_results.json", "w"), indent=2)
print("wrote keyed_audit_results.json")
