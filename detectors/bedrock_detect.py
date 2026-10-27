# Cross-validate the detectors STATIC detectors on the keyed tools with a FRONTIER Bedrock judge
# (instead of qwen3.5), to remove the "victim==detector judge" self-check bias. Reuses run_repro's exact
# prompts (REVIEW_SYS for llm_code_review, DCI Direct/Reverse/Arbiter for dci) + code_of(), but routes
# the judge call to Bedrock via bedrock_judge._bedrock_json. Non-Claude Bedrock model by default
# (Claude's safety layer content_filters the tool-review role). Runs on the k00-k04 keyed items.
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("BEDROCK_MODEL", "us.openai.gpt-5.6-terra")
os.environ.setdefault("BEDROCK_KEY_FILE", "/home/ruiheng/aiagent/saas/amazonapi.txt")
import run_repro as R
import bedrock_judge as BJ   # _bedrock_json(system, user, mx)

ITEMS = [it for it in R.CORPUS if it["id"].startswith(("k00", "k01", "k02", "k03", "k04"))]
K = int(os.environ.get("JUDGE_K", "3"))

def med_approve(system, user, k=K):
    """median-of-k: returns (median_approve_bool, [draws], n)."""
    draws = []
    for _ in range(k):
        try:
            d = BJ._bedrock_json(system, user, 3000)
            draws.append(bool(d.get("approve", d.get("would_approve"))))
        except Exception as e:
            print("   [bedrock retry]", str(e)[:80], flush=True)
    if not draws: return None, [], 0
    return (sum(draws) > len(draws) / 2), draws, len(draws)

rows = []
for it in ITEMS:
    srv, ds = R.code_of(it)
    user = ('ADVERTISED METADATA (tools/list):\n%s\n\n=== server.py ===\n%s\n\n=== directory_service.py ===\n%s'
            % (R.meta_txt(it), srv, ds))
    appr, draws, n = med_approve(R.REVIEW_SYS, user)
    # flagged = NOT approved
    flagged = (appr is False)
    print("[%-34s] llm_code_review(bedrock): approve=%s draws=%s -> %s"
          % (it["id"], appr, draws, "FLAGGED" if flagged else ("miss/approve" if appr else "FILTERED")), flush=True)
    rows.append({"id": it["id"], "judge": os.environ["BEDROCK_MODEL"], "approve": appr,
                 "draws": draws, "n": n, "flagged": flagged})
    json.dump(rows, open("bedrock_detect_results.json", "w"), indent=2)
json.dump(rows, open("bedrock_detect_results.json", "w"), indent=2)
print("\nwrote bedrock_detect_results.json")
