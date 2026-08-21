# OverServe

**Denial-of-Efficiency via Action-Budget Amplification in SaaS Agents.**

A **trainable**, **query-only** prompt rewrite that makes a tool-using SaaS agent *overserve* —
issue far more tool calls for the **same, verifier-passing outcome** — while staying **stealthy**
(reads as an ordinary admin request) and **fidelity-preserving** (goal completion unchanged).

> Prior reasoning-level DoS attacks amplify the **tokens** an agent generates (the cost unit of
> per-token API resale). Production SaaS agents bill **per invocation**, where the load-bearing cost
> is the **number of actions**, not tokens. Rather than making an agent *overthink*, OverServe makes
> it *overserve*.

---

## Headline results (measured)

| metric | value | notes |
|---|---|---|
| matched action amplification | **median 2.1×, up to 4.5×** | tool calls vs the same task's own baseline, 10 real tasks |
| ∆Steps (STA's metric) | **+11.7 avg** (+8…+16) | absolute extra tool-calling steps; STA reports +1…+3.5 |
| total tokens (naive) | 2.33× | "tokens processed", no cache credit |
| real compute (cached) | 1.33× | prefix-caching-aware; the honest GPU cost |
| fidelity | **1.0** | same verifier pass rate as the un-amplified task |
| stealth | high (≈1.0) | LLM monitor rates the rewrite as a legitimate admin task |

Amplification is **cache-immune on the action axis**: caching lowers per-call GPU cost but not the
number of billed actions.

---

## How it works

```
 real benign task ──┐
                    ├─▶ fuse() ─▶ rewritten task ─▶ [VICTIM agent] ─▶ calls / tokens / fidelity
 amplification seed ┘   (deepseek)                    (qwen3.5, EOG)          │
        ▲                                                                     │
        │                                                                     ▼
        └──────────── generate() ◀── feedback (which seeds amplified) ◀── stealth_score()
                      (claude, the TRAINABLE loop)                        (deepseek monitor)
```

1. **fuse** — the fusion model rewrites a real task in a seed strategy's thorough, item-by-item,
   verify-each-step style, keeping the same goal. → `overserve/fusion.py`
2. **score** — run the rewrite on the victim agent; fitness = `matched_amp × stealth`, gated by
   fidelity (must keep the task's own verifier pass rate). → `overserve/score.py`, `agent_fit.py`
3. **generate** (the trainable part) — feed the winning/losing mechanisms to a **strong generator**
   (claude), which proposes new strategies that refine/combine winners and explore new angles. This
   closes the loop at the **seed layer** — the layer proven to matter (GA/GEPA search over tasks or
   the fuse-instruction never beat the initial content; regenerating seeds does). → `fusion.generate`

---

## Layout

```
overserve/
  config.py        all paths + model ids, from env with defaults (the ONLY place they live)
  llm.py           advanced-LLM calls: fusion_llm, generator_llm, stealth_score
  agent_fit.py     run the VICTIM agent on one task -> calls/turns/tokens(naive+cached)/fidelity/coverage
  bench.py         load seed pool / real tasks / 70-tool inventory; run a task with a custom prompt
  fusion.py        the attack core: fuse() + generate() (trainable seed generation)
  score.py         eval_seed(): fuse -> run -> matched_amp x stealth x fidelity
  seed_iter.py     OverServe on ONE task (feedback-driven seed iteration)
  large_scale.py   OverServe across MANY tasks (resumable, checkpointed) -> amplification distribution
  token_measure.py measure a chosen attack's naive/cached token amplification (no re-search)
data/seed_pool.json    75 amplification-strategy seeds
scripts/               thin CLI wrappers (run_seed_iter / run_large / run_token_measure)
```

---

## Setup

OverServe itself needs only the Python **standard library**. It depends on two external things:

1. **The victim agent** — [EnterpriseOps-Gym](../EnterpriseOps-Gym) (EOG), a Teams-admin agent
   benchmark, with its own venv at `$EOG_HOME/.venv`. OverServe shells out to it.
2. **A live qwen3.5 endpoint** — the EOG repo config points at a dead tunnel, so set the endpoint.
3. **An OpenRouter key** — for the fusion model (deepseek) and the generator (claude).

```bash
export EOG_HOME=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1     # live vLLM tunnel for qwen3.5
export OPENROUTER_API_KEY=sk-or-...
```

All knobs (see `config.py`): `OVERSERVE_FUSION_MODEL`, `OVERSERVE_GENERATOR_MODEL`, `OVERSERVE_CAP`,
`OVERSERVE_SEED`, `OVERSERVE_SEED_POOL`, `OVERSERVE_PILOT`, `OVERSERVE_ALLTOOLS`.

---

## Run

```bash
# 1) Single-task attack (feedback-driven seed iteration)
python scripts/run_seed_iter.py --rounds 2 --eval0 8 --gen 6
#    -> overserve_seed_iter.jsonl, overserve_seed_iter_best.json

# 2) Large-scale distribution across N real tasks (resumable)
python scripts/run_large.py --tasks 10
#    -> overserve_large_results.jsonl  (+ a median/mean/range summary)

# 3) Token amplification of the chosen best attack (naive + cached)
python scripts/run_token_measure.py --best overserve_seed_iter_best.json --n 3
#    -> overserve_token_measure.json
```

Or from Python:

```python
from overserve import seed_iter, large_scale, token_measure
best = seed_iter.run(rounds=2)
large_scale.run(n_tasks=10)
token_measure.run(best_path="overserve_seed_iter_best.json", n=3)
```

---

## Notes

- **Reproducibility**: sampling uses `config.SEED`; baselines are denoised (median of n runs). The
  victim agent itself is stochastic, so single-run numbers carry ~15% noise — report medians.
- **Cost control**: every agent run is capped at `CAP` turns.
- **Roles**: victim = qwen3.5 (EOG); fusion + stealth monitor = deepseek; strategy generator = claude.
  Swap any via `config.py` / env.
