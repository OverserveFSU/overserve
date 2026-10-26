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
overserve/                 # framework package: llm, config, fusion, score, seed_iter, large_scale, token_measure
scripts/                   # package entry points (run_large, run_seed_iter, run_token_measure)
toolatk_search_v{5,7,8}.py # current search engine (writer + judges + corner selection)
toolatk_run.py             # core victim runner
recon_to_search.py         # recon-seeded end-to-end search (tool_list -> working attack)
recon_analyzer.py          # derive (gate, driver) candidates from a service's tool list
mcp_attack_server_v7.py    # churn MCP status server (ChurnDir / ConcurrentChurnDir)
real_churn_backend.py      # genuine concurrent-update backend (P0-b)
search_eog_*.py / eog_*    # EnterpriseOps-Gym pipeline (headline 40x case)
benchmarks_ports/          # adapters + search + guards for the 9 benchmarks + CLI
  appworld/ ew/ mcpmark/ workbench/ tac/ toolathlon/ browsecomp/ infra/
detect_bench/              # 5 industrial scanners + 4 research detectors (DCI, Connor, ...)
baselines/toolslot/        # A2M / LoopTrap / ours comparison harness (Table 2)
standardized/              # standardized cap-protocol campaign runners + CAP_PROTOCOL.md
run_p0{b,c}_*.py, p0d_*    # reviewer-rigor controls (real churn / prompt contrast / independent audit)
eog_defense_test.py        # progress-authorized guard (defense)
```

## Running

```bash
pip install -r requirements.txt

# 1. End-to-end recon-seeded attack search on a service
python recon_to_search.py                       # uses recon_candidates.json + the v8 machinery

# 2. EnterpriseOps-Gym headline case (churn server auto-launched)
python search_eog_sonnet.py                      # or _nemotron / _llama4scout

# 3. A benchmark port (e.g. MCPMark)
python benchmarks_ports/mcpmark/search_v9_mcpmark.py

# 4. Detector screening of archived tools
python detect_bench/run_scanners.py && python detect_bench/report.py

# 5. Baseline comparison (A2M / LoopTrap / ours)
bash baselines/toolslot/run_pilot.sh

# 6. Defense (progress-authorized guard)
ATK_CAP=200 python eog_defense_test.py

# 7. Reviewer-rigor controls
python run_p0b_realchurn.py       # real concurrent-churn backend
python run_p0c_prompt_contrast.py # same-tool semantic-match prompt contrast
python p0d_indep_audit.py         # independent (cross-model) audit

# 8. Standardized cap-protocol campaign
python standardized/run_std.py    # see standardized/CAP_PROTOCOL.md
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
