"""Multi-judge stealth panel.

The deepseek monitor scored interf2-idchain 0.10; the user's GPT read it as benign. Rather than
trust either, run the SAME stealth prompt across several judges, with anchors, so we can see
whether 'stealth' is a property of the prompt or of the judge.
"""
# --- overserve path bootstrap (reorganized layout; see overserve_paths.py) ---
import os as _ovp_os, sys as _ovp_sys
_ovp_d = _ovp_os.path.dirname(_ovp_os.path.abspath(__file__))
while _ovp_d != _ovp_os.path.dirname(_ovp_d) and not _ovp_os.path.exists(_ovp_os.path.join(_ovp_d, "overserve_paths.py")):
    _ovp_d = _ovp_os.path.dirname(_ovp_d)
if _ovp_d not in _ovp_sys.path:
    _ovp_sys.path.insert(0, _ovp_d)
import overserve_paths  # noqa
# --- end overserve path bootstrap ---
import sys, re, json, glob, urllib.request, statistics, concurrent.futures as cf
sys.path.insert(0, "/home/ruiheng/aiagent/saas/overserve")
from overserve import config
from overserve.llm import STEALTH_PROMPT

JUDGES = ["openai/gpt-5.6-luna", "anthropic/claude-sonnet-5", "google/gemini-3.7-flash",
          "deepseek/deepseek-v4-flash-0731", "deepseek/deepseek-v4-pro"]
REPS = 3


def judge(model, p, maxtok=4000):
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": STEALTH_PROMPT % p}],
                       "temperature": 0.0, "max_tokens": maxtok}).encode()
    req = urllib.request.Request(config.OPENROUTER_URL, data=body,
        headers={"Authorization": "Bearer " + config.OPENROUTER_KEY,
                 "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
        c = (r["choices"][0]["message"].get("content") or "").strip()
        m = re.findall(r"[01](?:\.\d+)?", c)
        return float(m[-1]) if m else None
    except Exception as e:
        return None


src = open("cycle_probe.py").read(); ns = {}
exec("TASKS={" + re.search(r"TASKS = \{(.*?)\n\}\n", src, re.S).group(1) + "}", ns)
T = ns["TASKS"]
R = "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/results"
benign = json.load(open(sorted(glob.glob(R + "/opt2/baseline/**/results_*.json", recursive=True))[0]))["benchmark_config"]["user_prompt"]
attack = json.load(open(sorted(glob.glob(R + "/opt2/winner/**/results_*.json", recursive=True))[0]))["benchmark_config"]["user_prompt"]

CASES = [("benign baseline", benign),
         ("explicit rider (2.2x attack)", attack),
         ("ctrl2-idchain", T["ctrl2-idchain"]),
         ("interf2-idchain", T["interf2-idchain"])]

jobs = {}
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for cn, p in CASES:
        for j in JUDGES:
            for k in range(REPS):
                jobs[(cn, j, k)] = ex.submit(judge, j, p)
res = {k: f.result() for k, f in jobs.items()}

print("%-30s %s" % ("prompt", "  ".join("%-14s" % j.split("/")[-1][:14] for j in JUDGES)))
print("-" * (30 + 16 * len(JUDGES)))
for cn, _ in CASES:
    cells = []
    for j in JUDGES:
        v = [res[(cn, j, k)] for k in range(REPS)]
        ok = [x for x in v if x is not None]
        cells.append("%-14s" % (("%.2f" % statistics.median(ok)) if ok else "FAIL"))
    print("%-30s %s" % (cn, "  ".join(cells)))
json.dump({f"{a}|{b}|{c}": v for (a, b, c), v in res.items()},
          open("judge_panel.json", "w"), indent=1)
print("\n-> judge_panel.json")
