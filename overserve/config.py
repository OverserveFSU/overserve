"""Central configuration for OverServe.

Everything the attack needs to locate — the victim agent, the advanced LLMs, the benchmark
tasks, the seed pool — is resolved here, from environment variables with sensible defaults.
Nothing else in the package hard-codes a path or a model id.
"""
import os

# --------------------------------------------------------------------------------------------
# Victim: the tool-using SaaS agent under test (EnterpriseOps-Gym / Teams-admin, qwen3.5).
# The agent is driven by EOG's evaluate.py; agent_fit.py shells out to it.
# --------------------------------------------------------------------------------------------
EOG_HOME = os.environ.get("EOG_HOME", "/home/ruiheng/aiagent/saas/EnterpriseOps-Gym")
EOG_PYTHON = os.environ.get("EOG_PYTHON", f"{EOG_HOME}/.venv/bin/python")
EOG_LLM_CFG = os.environ.get("EOG_LLM_CFG", f"{EOG_HOME}/conf/llm/qwen35.json")
# The repo qwen config points at a dead tunnel; override the endpoint to the live vLLM tunnel.
EOG_LLM_ENDPOINT = os.environ.get("EOG_LLM_ENDPOINT", "http://127.0.0.1:8192/v1")

# Benchmark tasks + the full 70-tool inventory the agent is exposed to.
PILOT_TASKS = os.environ.get("OVERSERVE_PILOT", f"{EOG_HOME}/eog_attack_kit/pilot_tasks")
ALLTOOLS_JSON = os.environ.get("OVERSERVE_ALLTOOLS",
                               f"{EOG_HOME}/eog_attack_kit/alltools_task/alltools_fitness.json")

# --------------------------------------------------------------------------------------------
# Advanced LLMs (OpenAI-compatible, via OpenRouter):
#   - FUSION model: rewrites a real task in a seed's amplification style, and scores stealth.
#   - GENERATOR model: proposes NEW amplification strategies from empirical feedback (the trainable loop).
# --------------------------------------------------------------------------------------------
OPENROUTER_URL = os.environ.get("OPENROUTER_URL", "https://openrouter.ai/api/v1") + "/chat/completions"
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
FUSION_MODEL = os.environ.get("OVERSERVE_FUSION_MODEL", "deepseek/deepseek-v4-flash-0731")
GENERATOR_MODEL = os.environ.get("OVERSERVE_GENERATOR_MODEL", "anthropic/claude-sonnet-4")

# --------------------------------------------------------------------------------------------
# Bundled data + run knobs.
# --------------------------------------------------------------------------------------------
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
SEED_POOL = os.environ.get("OVERSERVE_SEED_POOL", os.path.join(_PKG_DIR, "..", "data", "seed_pool.json"))

CAP = int(os.environ.get("OVERSERVE_CAP", 36))        # max agent turns per run (bounds cost)
SEED = int(os.environ.get("OVERSERVE_SEED", 0))       # RNG seed for reproducible sampling


def require_key():
    """Fail loudly if the advanced-LLM key is missing (fusion + generation need it)."""
    if not OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set — fusion and seed generation need it.")
