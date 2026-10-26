"""Score the cycle-probe prompts with the existing OverServe stealth monitor.

Anchors are included so the number means something: a real benign benchmark prompt (upper) and
a known explicit-workload attack rider (lower). Same monitor, same prompt, same model as every
earlier OverServe stealth number, so these are comparable with the archived results.
"""
import sys, os, json, glob, statistics, re
sys.path.insert(0, "/home/ruiheng/aiagent/saas/overserve")
from overserve import config
from overserve.llm import stealth_score

REPS = int(os.environ.get("STEALTH_REPS", "3"))

# the two probe prompts, read straight out of the probe script so they cannot drift
src = open("cycle_probe.py").read()
ns = {}
exec("TASKS={" + re.search(r"TASKS = \{(.*?)\n\}\n", src, re.S).group(1) + "}", ns)
T = ns["TASKS"]

R = "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/results"
benign = json.load(open(sorted(glob.glob(R + "/opt2/baseline/**/results_*.json",
                                         recursive=True))[0]))["benchmark_config"]["user_prompt"]
attack = json.load(open(sorted(glob.glob(R + "/opt2/winner/**/results_*.json",
                                         recursive=True))[0]))["benchmark_config"]["user_prompt"]

CASES = [
    ("ANCHOR benign baseline", benign),
    ("ANCHOR explicit rider (opt2/winner)", attack),
    ("struct-tab-update  (mined cycle)", T["struct-tab-update"]),
    ("interf-tabsync     (failed design)", T["interf-tabsync"]),
    ("ctrl2-idchain      (control)", T["ctrl2-idchain"]),
    ("interf2-idchain    (the one that cycles)", T["interf2-idchain"]),
]

print("monitor: %s   reps=%d\n" % (config.FUSION_MODEL, REPS))
print("%-42s %-22s %s" % ("prompt", "scores", "median"))
out = []
for name, p in CASES:
    ss = [stealth_score(p) for _ in range(REPS)]
    med = statistics.median(ss)
    out.append({"name": name, "scores": ss, "median": med, "chars": len(p)})
    print("%-42s %-22s %.2f" % (name, " ".join("%.2f" % x for x in ss), med))
json.dump(out, open("stealth_check.json", "w"), indent=1)
print("\n-> stealth_check.json")
