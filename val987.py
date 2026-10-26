import sys, glob, json
sys.path.insert(0, '/home/ruiheng/aiagent/saas/overserve')
from overserve.agent_fit import run_agent_fitness

tasks = sorted(glob.glob('/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/eog_attack_kit/refactored_tasks/t987_*.json'))
print('validating', len(tasks), 'refactored tasks (running each own benign prompt)', flush=True)
for tp in tasks:
    j = json.load(open(tp)); name = j['_meta']['objective']; lvl = j['_meta']['level']
    f = run_agent_fitness(task_src=tp, cap=20)
    if f:
        print('%-18s [%-10s] calls=%2d turns=%2d fidelity=%.2f  verifiers=%d' %
              (name, lvl, f['n_calls'], f['turns'], f['chkpt'], len(j['verifiers'])), flush=True)
    else:
        print('%-18s FAILED (no result)' % name, flush=True)
print('DONE', flush=True)
