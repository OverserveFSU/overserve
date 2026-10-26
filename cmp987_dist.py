import sys, glob, json
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.bench import run_prompt

RJ = json.load(open(sorted(glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/pilot_tasks/*987*.json'))[0]))
BENIGN = RJ['user_prompt']
COMPRESSED = ("Set up the TechCorp Solutions beta-feedback workspace: create “Beta Feedback Circle” for early-tester feedback; "
    "tag John Davis, Dave Brown, and Sophia Bennett as “Beta Testers”; create a “Beta Triage Room” chat with them for "
    "urgent-item triage; add a “Review Notes” OneNote tab to the channel; and post the feedback/review-window instructions.")

def dist(name, p, n):
    calls, fids = [], []
    for i in range(n):
        r = run_prompt(RJ, p, cap=36, retries=1)
        if r:
            calls.append(r['n_calls']); fids.append(round(r['chkpt'], 2))
            print('  %s run%d: calls=%d fid=%.2f' % (name, i, r['n_calls'], r['chkpt']), flush=True)
    print('%s SUMMARY: calls=%s (min %d max %d) | fidelity=%s (all<1? %s)' %
          (name, calls, min(calls), max(calls), fids, all(f < 0.99 for f in fids)), flush=True)

print('=== COMPRESSED distribution (n=5) ===', flush=True)
dist('COMPRESSED', COMPRESSED, 5)
print('=== BENIGN distribution (n=3) ===', flush=True)
dist('BENIGN', BENIGN, 3)
