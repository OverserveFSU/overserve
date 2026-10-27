# Setup & Usage

This document explains **what to install, where to put API keys, and which environment variables to
set to run the models**, then gives per-component run commands.

> OverServe uses up to three LLM *roles*: the **victim** agent under attack, the **advanced LLMs**
> that generate/fuse/judge attacks, and (optionally) **Bedrock** models used as frontier victims or
> judges. You configure each role by environment variables — nothing is hard-coded (see
> `overserve/config.py`).

---

## 1. Install

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The engine uses a `src/` layout imported by flat module name. Entry scripts self-bootstrap; for a bare
interpreter put the repo root on the path:

```bash
PYTHONPATH=. python3 -c "import toolatk_search_v8"   # should print nothing (success)
```

---

## 2. Keys & configuration by LLM role

### 2a. Advanced LLMs — attack writer / fusion / stealth judge  (REQUIRED)
These call an **OpenAI-compatible** endpoint (OpenRouter by default), in `overserve/llm.py`.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **yes** | – | Bearer key for the advanced LLMs. `config.require_key()` aborts if unset. |
| `OPENROUTER_URL` | no | `https://openrouter.ai/api/v1` | Base URL (`/chat/completions` is appended). Point this at any OpenAI-compatible gateway. |
| `OVERSERVE_GENERATOR_MODEL` | no | `anthropic/claude-sonnet-4` | The strong model that proposes attack strategies / is the writer+judge. |
| `OVERSERVE_FUSION_MODEL` | no | `deepseek/deepseek-v4-flash-0731` | The model that rewrites a task in a seed's style. |

```bash
export OPENROUTER_API_KEY=$(cat key.txt)          # read from a gitignored file, never inline
export OPENROUTER_URL=https://openrouter.ai/api/v1 # set explicitly if a shim also listens locally
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash   # e.g. use GLM as writer/judge
```

### 2b. Victim agent — the SaaS agent under attack  (REQUIRED to run rollouts)
The victim is any **OpenAI-compatible** chat endpoint (a local vLLM server, a tunnel, or a cloud model).

| Variable | Default | Purpose |
|---|---|---|
| `EOG_LLM_ENDPOINT` | `http://127.0.0.1:8192/v1` | Victim OpenAI-compatible base URL. |
| `EOG_LLM_KEY` | – | Bearer key for the victim endpoint (set even if the server ignores it). |
| `EOG_LLM_MODEL` | – | Victim model id (e.g. `qwen3.8-27b`, `deepseek-v4-flash`, `nemotron-3-super`). |
| `EOG_HOME` / `EOG_PYTHON` / `EOG_LLM_CFG` | paths under `EnterpriseOps-Gym/` | The EOG gym the victim is driven through. |

```bash
export EOG_LLM_ENDPOINT=http://192.168.122.103:8000/v1
export EOG_LLM_KEY=$(cat victim_key.txt)
export EOG_LLM_MODEL=qwen3.8-27b
```

**Qwen note:** disable the thinking channel. Either send
`chat_template_kwargs={"enable_thinking": false}`, or front the server with the bundled proxy
`detectors/llm_proxy.py` (listens on `:8193`, strips thinking, forces the model id, raises
`max_tokens`):

```bash
LLM_UPSTREAM=http://127.0.0.1:8192 python3 detectors/llm_proxy.py &   # then point EOG_LLM_ENDPOINT at :8193
```

**Reasoning victims (deepseek / nemotron):** do NOT inject `enable_thinking`; they emit
`reasoning`+`content` and parse normally. Set `max_output_tokens=16384` to avoid context-window errors.

Per-benchmark ports read their own victim-model variable in addition to the above:
`MCPMARK_MODEL`, `WB_QWEN_MODEL_ID`, `APPWORLD_MAX_STEPS`/`APPWORLD_TASKS`, etc. (see each dir).

### 2c. Bedrock models — frontier victim (Sonnet-5) or GPT judges  (OPTIONAL)
Bedrock is reached through a small **OpenAI-compatible shim** so the rest of the code is unchanged.

1. Put the AWS Bedrock bearer token in a **gitignored** file (e.g. `amazonapi.txt`).
2. Start the shim (see `benchmarks/infra/` and `standardized/`), exporting the token:

```bash
export AWS_BEARER_TOKEN_BEDROCK=$(cat amazonapi.txt)
export AWS_REGION=us-east-1
# start the bedrock OpenAI-compat shim on a unique local port, then point the victim/judge at it:
export EOG_LLM_ENDPOINT=http://127.0.0.1:8300/v1
export EOG_LLM_MODEL=openai/sonnet-5          # route id the shim maps to Bedrock
```

Use the same pattern to run a **GPT judge** (e.g. `gpt-6-astra`) as an independent reviewer: run its
shim on its own port and set `OPENROUTER_URL`/model to that port. Note: `gpt-6-astra` rejects the
`temperature` field — omit it.

### 2d. Run knobs (all optional; sensible defaults)

| Variable | Meaning |
|---|---|
| `ATK_CAP` / `OVERSERVE_CAP` | max agent turns per rollout (bounds cost) |
| `ATK_CHURN` | `1` = production churn (amplify), `0` = quiescent audit (benign) |
| `ATK_BUDGET` / `ATK_CANDS` / `ATK_ROLLOUTS` / `ATK_SCREEN` / `ATK_CONFIRM` | search budget / candidates / rollouts / screen & confirm reps |
| `ATK_PORT` | port for the churn MCP server |
| `OVERSERVE_SEED` / `REPS` | RNG seed / repetitions |

---

## 3. Secrets handling

**Never commit keys.** The following are git-ignored and must be read at runtime from local files:
`key.txt`, `*_key.txt`, `*token*.txt`, `amazonapi.txt`, `PAT.txt`, `*.pem`. Set env vars from them,
e.g. `export OPENROUTER_API_KEY=$(cat key.txt)` — do not paste keys on the command line literally.

---

## 4. Quickstart by component

Minimum to run anything: `OPENROUTER_API_KEY` (§2a) + a victim endpoint (§2b).

```bash
# 0. common setup
source .venv/bin/activate
export OPENROUTER_API_KEY=$(cat key.txt)
export EOG_LLM_ENDPOINT=http://192.168.122.103:8000/v1
export EOG_LLM_KEY=$(cat victim_key.txt)
export EOG_LLM_MODEL=qwen3.8-27b

# 1. recon-seeded attack search (derive gate+driver from a tool list, then search)
python src/recon/recon_to_search.py

# 2. EnterpriseOps-Gym headline case (churn server auto-launched)
ATK_CAP=200 ATK_CHURN=1 EOG_LLM_MODEL=$EOG_LLM_MODEL python scripts/search_eog_sonnet.py

# 3. a benchmark port (MCPMark)
MCPMARK_MODEL=qwen3.8-27b python benchmarks/mcpmark/search_v9_mcpmark.py

# 4. detector screening (start the qwen proxy first for the LLM detectors)
python3 detectors/llm_proxy.py &        # :8193 → qwen, thinking off
python detectors/run_scanners.py && python detectors/report.py

# 5. baseline comparison (A2M / LoopTrap / ours)
bash baselines/toolslot/run_pilot.sh

# 6. defense (progress-authorized guard)
ATK_CAP=200 python defense/eog_defense_test.py

# 7. standardized cap-protocol campaign (see standardized/CAP_PROTOCOL.md)
python standardized/run_std.py
```

Results of the standardized cross-victim campaign and the full experiment log live in the paper repo
(`overserve_paper/standardized/`, `overserve_paper/EXPERIMENT_LOG.md`); runner code is in
`standardized/`.
