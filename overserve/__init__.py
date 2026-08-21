"""OverServe — Denial-of-Efficiency via Action-Budget Amplification in SaaS Agents.

A trainable, query-only prompt rewrite that makes a tool-using SaaS agent OVERSERVE: issue far
more tool calls for the same, verifier-passing outcome — stealthily and fidelity-preserving.

Public API:
    from overserve import seed_iter, large_scale, token_measure
    from overserve.fusion import fuse, generate
    from overserve.score import eval_seed
    from overserve.agent_fit import run_agent_fitness
"""
from . import config, llm, agent_fit, bench, fusion, score, seed_iter, large_scale, token_measure

__all__ = ["config", "llm", "agent_fit", "bench", "fusion", "score",
           "seed_iter", "large_scale", "token_measure"]
__version__ = "0.1.0"
