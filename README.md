# OverServe

**Resource Amplification Attacks on SaaS Agents via Tool–Prompt Co-Design.**

OverServe is a multi-agent framework that constructs *denial-of-efficiency* attacks against
subscription-billed SaaS agents. It **co-designs an MCP status tool and a matching completion
prompt**: every tool call returns truthful status and terminates normally, but under backend
**churn** (concurrent external updates keep a condition "pending") the victim agent keeps
re-checking to satisfy the prompt — burning the provider's tokens and tool-call budget *after*
the original business task is already complete. The attack is split across two separately-reviewed
vectors (tool code/metadata and user prompt), so each passes review while their conjunction
amplifies. See the paper for details.

> Research artifact for an academic paper on SaaS-agent resource safety. Run only in isolated
> environments with test data and fixed execution limits (see *Ethical Considerations* in the paper).

## Attack mechanism

1. **Reconnaissance** — read a service's tool list and derive completion "gates": conditions a
   truthful status tool could honestly never report `done` under live activity
   (`recon_analyzer.py` → `recon_candidates*.json`).
2. **Writer** — synthesize tool metadata + handler code + a one-sentence *driver* prompt
   (`overserve/` package; `toolatk_search_v5/v7/v8.py`, `recon_to_search.py`).
3. **Three reviews** — static code `r_s`, runtime completion `r_d`, prompt benignness `r_p`
   (thresholds 0.8 / pass-within-2-calls / 0.7).
4. **Victim rollout** under **clean / quiet / churn**; the churn backend is
   `mcp_attack_server_v7.py` (gym) or `real_churn_backend.py` (genuine concurrent updates).
5. **Selection** by amplification `α_q = C_c / C_q` with original-task fidelity preserved.

## Repo layout

```
overserve/              # framework package (unchanged): llm, config, fusion, score, seed_iter, large_scale, token_measure
src/
  search/               # search engine: toolatk_search_v5/v7/v8, toolatk_run, toolatk_qd (+ task_synth, measure_effects deps)
  recon/                # recon_to_search, recon_analyzer, recon_candidates*.json, gym_tool_schemas.json
  attack_server/        # mcp_attack_server_v7 (+ v3), real_churn_backend, + their spec json
benchmarks/             # per-benchmark ports: appworld/ ew/ mcpmark/ workbench/ tac/ toolathlon/ browsecomp/ infra/
detectors/              # 5 industrial scanners + 4 research detectors (DCI, Connor, ...) + bedrock helpers
baselines/toolslot/     # A2M / LoopTrap / ours comparison harness (Table 2)
defense/                # eog_defense_test.py (progress-authorized guard)
standardized/           # standardized cap-protocol campaign runners + CAP_PROTOCOL.md
scripts/                # entry runners: search_eog_*, eog_campaign*, base_check_eog*, run_p0{b,c}*, p0d_*, resource_*, run_*.py/.sh
data/                   # kept archive/spec json + seed_pool.json (package data)
docs/                   # project docs (BENCHMARK_REFACTOR, TOOL_INVENTORY, CLEANUP_PLAN)
overserve_paths.py      # sys.path bootstrap for the src/ layout (added to path by entry scripts)
sitecustomize.py        # auto-loads the bootstrap when the repo root is on sys.path (e.g. PYTHONPATH=.)
README.md
```

### How imports resolve

The engine lives under `src/` but is imported by flat module name (e.g. `import toolatk_search_v5`).
`overserve_paths.py` puts `src/search`, `src/recon` and `src/attack_server` (and the repo root, for the
`overserve` package) on `sys.path`. Entry scripts self-bootstrap (they locate the repo root and
`import overserve_paths`), so running them directly works. For a bare interpreter from the repo root,
put the root on the path so `sitecustomize.py` loads the bootstrap:

```bash
PYTHONPATH=. python3 -c "import toolatk_search_v5"   # engine smoke test
```

## Configuration

**See [`SETUP.md`](SETUP.md) for the full setup: where to put API keys and which environment
variables configure each model.** In short, three LLM roles are set via env vars (nothing is
hard-coded — see `overserve/config.py`):

- **Advanced LLMs** (attack writer / fusion / stealth judge) — OpenAI-compatible, OpenRouter by default:
  set `OPENROUTER_API_KEY` (required), optionally `OPENROUTER_URL`, `OVERSERVE_GENERATOR_MODEL`,
  `OVERSERVE_FUSION_MODEL`.
- **Victim agent** (the SaaS agent under attack) — any OpenAI-compatible endpoint:
  set `EOG_LLM_ENDPOINT`, `EOG_LLM_KEY`, `EOG_LLM_MODEL` (qwen: disable `enable_thinking`, or front it
  with `detectors/llm_proxy.py`; deepseek/nemotron: standard parse + `max_output_tokens=16384`).
- **Bedrock** (frontier victim Sonnet-5 / GPT judges) — via an OpenAI-compatible shim fed
  `AWS_BEARER_TOKEN_BEDROCK` from a git-ignored token file.

Secrets are read at runtime from git-ignored files (`key.txt`, `*_key.txt`, `amazonapi.txt`, …) —
never commit them. Run knobs: `ATK_CAP`/`OVERSERVE_CAP`, `ATK_CHURN` (1=amplify, 0=quiescent audit),
`ATK_BUDGET`, `REPS`, … (full table in `SETUP.md`).

## Running

```bash
pip install -r requirements.txt

# 1. End-to-end recon-seeded attack search on a service
python src/recon/recon_to_search.py                   # (engine path set up automatically)

# 2. EnterpriseOps-Gym headline case (churn server auto-launched)
python scripts/search_eog_sonnet.py                   # or _nemotron / _llama4scout

# 3. A benchmark port (e.g. MCPMark)
python benchmarks/mcpmark/search_v9_mcpmark.py

# 4. Detector screening of archived tools
python detectors/run_scanners.py && python detectors/report.py

# 5. Baseline comparison (A2M / LoopTrap / ours)
bash baselines/toolslot/run_pilot.sh

# 6. Defense (progress-authorized guard)
ATK_CAP=200 python defense/eog_defense_test.py

# 7. Reviewer-rigor controls
python scripts/run_p0b_realchurn.py       # real concurrent-churn backend
python scripts/run_p0c_prompt_contrast.py # same-tool semantic-match prompt contrast
python scripts/p0d_indep_audit.py         # independent (cross-model) audit

# 8. Standardized cap-protocol campaign
python standardized/run_std.py            # see standardized/CAP_PROTOCOL.md
```

## Baselines note

`baselines/toolslot/` is the self-contained harness that runs the **A2M** (verbatim return-value
port), **LoopTrap** (reimplementation), and **OverServe** methods for the Table 2 comparison. The
upstream **A2M** (`Lilaizhen/A2M`) and **STA** (`LiQiiiii/Sponge-Tool-Attack`) repositories are
*vendored clones* (each with its own `.git`) and are **git-ignored** — clone them from the URLs cited
in the paper; our STA adaptation lives in `baselines/STA/overserve_port/` inside that clone.

## Results

The standardized cross-victim, consistent-cap campaign and the full experiment log live in the
paper repo: `overserve_paper/standardized/STANDARDIZED_RESULTS.md` and
`overserve_paper/EXPERIMENT_LOG.md`. Headline amplifications and stealth scores are in Tables 1–3
of the paper. Runner code for regenerating the standardized table is in `standardized/`.
