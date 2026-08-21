"""Benchmark plumbing: load the seed pool, the real tasks, and the 70-tool inventory; run a real
task with an arbitrary prompt under the full tool set."""
import os
import json
import glob
import tempfile

from . import config
from .agent_fit import run_agent_fitness


def load_alltools():
    """The full 70-tool inventory the agent is exposed to (the realistic production surface)."""
    return json.load(open(config.ALLTOOLS_JSON))["selected_tools"]


def load_seed_pool():
    """The bundled amplification-strategy seed pool (75 strategies)."""
    return [s["task"] for s in json.load(open(config.SEED_POOL))]


def load_tasks(n=None):
    """Real benign benchmark tasks (oracle Teams-admin), sorted for reproducibility."""
    files = sorted(glob.glob(f"{config.PILOT_TASKS}/oracle__teams__*.json"))
    return files[:n] if n else files


_ALL70 = None


def run_prompt(real_json, prompt, cap=None, retries=0):
    """Run `real_json` (a real task) but with `prompt` as the user prompt, under all 70 tools.
    Returns the fitness dict from run_agent_fitness (or None)."""
    global _ALL70
    if _ALL70 is None:
        _ALL70 = load_alltools()
    for _ in range(retries + 1):
        d = json.loads(json.dumps(real_json))
        d["selected_tools"] = _ALL70
        d["user_prompt"] = prompt
        tmp = tempfile.mkdtemp(prefix="osbench_")
        p = os.path.join(tmp, "t.json")
        json.dump(d, open(p, "w"))
        f = run_agent_fitness("", task_src=p, cap=cap)
        if f:
            return f
    return None
