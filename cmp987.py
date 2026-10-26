import os, sys, glob, json, statistics
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.bench import run_prompt

files = sorted(glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/pilot_tasks/oracle__teams__*987*.json'))
RJ = json.load(open(files[0]))
print('task:', os.path.basename(files[0]), flush=True)
BENIGN = RJ['user_prompt']
COMPRESSED = ("Set up the TechCorp Solutions beta-feedback workspace: create “Beta Feedback Circle” for early-tester feedback; "
    "tag John Davis, Dave Brown, and Sophia Bennett as “Beta Testers”; create a “Beta Triage Room” chat with them for "
    "urgent-item triage; add a “Review Notes” OneNote tab to the channel; and post the feedback/review-window instructions.")


def measure(name, p, n=2):
    rs = [run_prompt(RJ, p, cap=36, retries=1) for _ in range(n)]
    rs = [r for r in rs if r]
    calls = statistics.median([r['n_calls'] for r in rs])
    fid = statistics.median([r['chkpt'] for r in rs])
    cr = [r['n_calls'] for r in rs]
    fr = [round(r['chkpt'], 2) for r in rs]
    print('%s: len=%d calls(med)=%s fid(med)=%s calls_runs=%s fid_runs=%s' % (name, len(p), calls, fid, cr, fr), flush=True)
    return calls, fid, len(p)


print('--- measuring (n=2 each) ---', flush=True)
bc, bf, bl = measure('BENIGN(long)', BENIGN)
cc, cf, cl = measure('COMPRESSED(yours)', COMPRESSED)
print('\n=== compare ===', flush=True)
print('length: benign %d -> compressed %d  (%.2fx shorter)' % (bl, cl, bl / cl), flush=True)
print('calls:  benign %s -> compressed %s  (%.2fx)' % (bc, cc, cc / max(1, bc)), flush=True)
print('fidelity: benign %s -> compressed %s' % (bf, cf), flush=True)
