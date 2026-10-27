# OverServe Repo Cleanup Plan

**Purpose:** align the `Kunjoe7/overserve` code repo with the paper
*"OverServe: Resource Amplification Attacks on SaaS Agents via Tool–Prompt Co-Design"*
(`overserve_paper/acl/overserve.tex`), and remove the historical / one-off / negative-result
experiment scripts that the paper does not use.

**Status:** ANALYSIS ONLY. Nothing has been deleted or `git`-ed. This file is a proposal for
the user to rule on. Every DELETE family below was grep-verified as **not imported by any KEEP
file** (one conflict was found and corrected — see `measure_effects.py`).

**Counts:** 366 tracked files → **KEEP 149 · DELETE 179 · AMBIGUOUS 38.**
(200 `.py`, 89 `.json`, 37 `.sh`, 23 `.md`, 5 `.jsonl`, 4 `.txt`, 4 `.html`, misc.)

---

## 1. Paper summary

OverServe is a **multi-agent framework** that constructs *resource-amplification* (denial-of-
efficiency) attacks on subscription SaaS agents by **co-designing an MCP status tool and a matching
completion-confirmation prompt**. Each tool call returns *truthful* status and terminates normally,
but under backend **churn** (concurrent external updates keep a condition "pending") the victim agent
keeps re-checking to satisfy the appended prompt, burning the provider's tokens/turns *after the
original business task is already done*. The attack is split across two separately-reviewed vectors
(tool code/metadata + user prompt), so each passes **static review `r_s`, runtime review `r_d`, and
prompt review `r_p`** while their conjunction amplifies. The framework's pipeline is:
**reconnaissance** (derive completion "gates" from a service's tool list) → **writer** (synthesize
tool metadata + handler code + driver prompt) → **three reviews** → **victim rollout under
clean/quiet/churn** → **selection/confirmation** by amplification `α_q = C_c/C_q` with original-task
fidelity preserved. It is evaluated on **four victims** (Qwen3.8-27B, Nemotron-3-Super,
DeepSeek-v4-Flash, Sonnet-5) across **nine benchmarks + a CLI task** (MCPMark, EnterpriseOps-Gym,
BrowseComp-Plus, STATE-Bench, TheAgentCompany, Toolathlon, AppWorld, Enterprise-Worlds, WorkBench,
Terminal-Bench), compared against **A2M / LoopTrap / STA** baselines and screened by **5 industrial
scanners + 4 research detectors (DCI, Connor, Repeat-cue, No-fixed-point)**; a **progress-authorized
guard** is the proposed defense. Headline: up to **93.88×** API-request amplification (Sonnet/AppWorld)
with task checks preserved and no scanner alerts.

---

## 2. KEEP list (core pipeline the paper relies on)

### 2.1 Framework engine (the eponymous `overserve` package + search machinery)
- `overserve/` — **entire package** (`__init__, config, llm, agent_fit, bench, fusion, score,
  seed_iter, large_scale, token_measure`). Live dependency: `toolatk_search_v5` does `from overserve …`.
- `scripts/run_large.py`, `scripts/run_seed_iter.py`, `scripts/run_token_measure.py` — package entry points.
- `toolatk_search_v5.py`, `toolatk_search_v7.py`, `toolatk_search_v8.py` — **current search engine**.
  The benchmark ports import all three together (`V` = v5 writer+GLM judge, `V7` = connor_soft/SAFE/
  TERMINAL, `V8` = W_SYS/score/is_corner/parse_list). v8 is the top of the chain.
- `toolatk_run.py` — core victim runner (imported by the EOG, P0-b, P0-c and every `toolatk_search_*`).
- `toolatk_qd.py` — imported by `toolatk_search_v7` (KEEP-by-dependency).
- `recon_to_search.py` — the **v9 recon-seeded search** (tool_list → working attack); uses `recon_analyzer`.
- `recon_analyzer.py` — derives (gate, driver) candidates from a service's tool list.
- `recon_candidates.json`, `recon_candidates_wb.json`, `recon_candidates_itsm.json` — recon inputs.
- `recon_v9_sup.sh` — recon-search supervisor.

### 2.2 Churn attack server + real backend
- `mcp_attack_server_v7.py` — **current** churn MCP server (`ChurnDir`/`ConcurrentChurnDir`); launched
  by `toolatk_search_v7/v8`, `eog_defense_test`, `search_eog_*`.
- `real_churn_backend.py` — P0-b genuine concurrent-update backend (paper §6 / §7.1, closes the
  "hardcoded flag" honesty gap).

### 2.3 Attack-construction inputs (live JSON/data)
- `attack_tool_spec.json`, `attack_tool_set.json`, `toolatk_v8_archive.json`, `measured_writers.json`,
  `gym_tool_schemas.json`, `v7_churn_spec.json`, `data/seed_pool.json`.

### 2.4 EnterpriseOps-Gym pipeline (top-level; the 40× headline benchmark)
- `search_eog_nemotron.py`, `search_eog_sonnet.py`, `search_eog_llama4scout.py`
- `eog_campaign.py`, `eog_campaign_nemotron.py`, `eog_campaign_sonnet.py`, `eog_campaign_llama4scout.py`
- `base_check_eog_nemotron.py`, `base_check_eog_sonnet.py`, `base_check_eog_llama4scout.py`
- `task_synth.py` — EOG task generator (imported by the `base_check_eog_*`); **KEEP-by-dependency**.
- `measure_effects.py` — **KEEP-by-dependency** (`task_synth` imports `measure_effects.sql_query`;
  this was the one KEEP↔DELETE conflict and is corrected here).
- `spec_nemotron.json`, `spec_sonnet.json`, `spec_llama4scout.json`, `campaign_eog_q38.jsonl`.

### 2.5 Benchmark ports (paper's 9 benchmarks + CLI)
- `benchmarks_ports/` — **entire tree kept**: adapters (`mcpmark_adapter`, `workbench_adapter`,
  `appworld_adapter` via `ew_adapter.py`, `ew/ew_adapter.py`), per-bench `search_faithful_*` and
  `search_v9_*` runners, `infra/` shims (`bedrock_shim*`, `qwen38_shim`), the frozen winner specs
  (`tac_winner_spec*.json`, `ew/sla_corner.json`, appworld `archive_*.json`), and the `*_q38.jsonl`
  campaign logs. *(Trim candidates inside this tree listed in §4.)*

### 2.6 Detectors (`detect_bench/`)
- `README.md`, `RESULTS.md` (current), `run_scanners.py`, `run_scanners_nv.py`, `run_repro.py`,
  `run_repro_nv.py`, `bedrock_detect.py`, `bedrock_openai_shim.py`, `cisco_behav.py`, `gen_corpus.py`,
  `gen_newvictim_corpus.py`, `add_toolslot_corpus.py`, `llm_proxy.py`, `llm_proxy_nv.py`, `report.py`,
  `spec_server.py`, `nv_ids.txt`, `ts_ids.txt`, `watch_bedrock.sh`.
- `bedrock_judge.py`, `bedrock_test.py` (top-level) — KEEP-by-dependency (`detect_bench/bedrock_detect`).

### 2.7 Defense (progress-authorized guard)
- `eog_defense_test.py` — guard on the EOG churn corner (`DEF_MAXNOPROG=K`).
- `benchmarks_ports/appworld/guard_replay_appworld_*.py` + `guard_appworld_*.json`.

### 2.8 Reviewer-rigor experiments (paper P0-a/b/c/d, §6–§7)
- `run_p0b_realchurn.py` (P0-b real churn), `run_p0c_prompt_contrast.py` + `qwen_direct_shim_p0c.py`
  (P0-c semantic-match prompt contrast), `p0d_indep_audit.py` (P0-d independent audit instrument).

### 2.9 Docs + build
- `README.md` (**rewrite — draft in §5**), `requirements.txt`, `.gitignore`.
- `benchmarks_ports/README.md`, `detect_bench/README.md`.
- `TOOL_INVENTORY.md` (the 22-tool screening inventory — maps to Table 3), `BENCHMARK_REFACTOR.md`
  (single-objective task design rationale).

> **FLAG — baselines harness is UNTRACKED.** The paper's Table 2 (A2M / LoopTrap / STA) and the
> token-accounting §17 depend on `./baselines/` (`baselines/toolslot/`, `baselines/A2M/`,
> `baselines/STA/`), which is **present on disk but not in git** (not in `git ls-files`). It must be
> added to the repo (e.g. tracked under `baselines/` with the vendored `STA/.git`, `.venv-sta`,
> `__pycache__` excluded) for the release to match the paper. User decision needed.

> **FLAG — standardized cap-protocol runners live in the PAPER repo, not here.** The
> `standardized/run_{std,sb,ew,wb,appworld}.py` + `summarize_std.py` + `STANDARDIZED_RESULTS.{jsonl,md}`
> and `CAP_PROTOCOL.md` are under `overserve_paper/standardized/`, not in this code repo. If the code
> release is meant to reproduce the standardized main table, copy/symlink them in; otherwise leave a
> pointer in the README.

---

## 3. DELETE list (historical / one-off / negative-result; verified not imported by any KEEP file)

Each group was confirmed superseded and not referenced by the KEEP set. Associated
`*_spec.json` / `*_summary.json` / `*_sup.sh` / supervisor shells go **with** their family.

**Superseded search / server / runner versions**
- `toolatk_search.py`, `toolatk_search_v3.py`, `toolatk_search_v4.py` — superseded by v5/v7/v8 (nothing imports them).
- `toolatk_run_chain.py`, `toolatk_cycle_run.py` — old chained/cycle runners.
- `mcp_attack_server.py`, `mcp_attack_server_chain.py` — old server variants (only old supervisors used them). *(v3 → AMBIGUOUS, see §4.)*
- `toolatk_supervisor.sh`, `toolatk_supervisor_v3.sh`, `_v4.sh`, `_v5.sh`, `toolatk_v7_sup.sh`, `toolatk_v8_sup.sh`, `toolatk_cross_sup.sh`, `capsweep_supervisor.sh`, `run_overnight.sh` — old run-loops.

**Old v7 experiment legs (NOT the kept v7 search/server)**
- `v7_batch.py`, `v7_maxamp.py`, `v7_replicate.py`, `v7_strategy.py`, `v7_toolmech.py`, `v7_churn.py`
  + their `*_spec.json` (keep only `v7_churn_spec.json`). Superseded maxamp/replicate/strategy probes.
- `V7_CHURN_RESULTS.md`, `V7_CORNER_RESULTS.md` — old result logs (superseded by `EXPERIMENT_LOG.md`).

**v6 line**
- `v6_live.py`, `v6_live_spec.json`, `detect_bench/v6_gen.py`, `detect_bench/V6_RESULTS.md`.

**v11 compression (negative: memory "compression attack fails")**
- `v11_compress.py`, `v11_compress_best.json`.

**cyclekey family (side artifact, not in paper)**
- `cyclekey_mechanism.py`, `cyclekey_rollout.py`, `mcp_cyclekey_server.py`, `cyclekey_spec.json`,
  `cyclekey_fuzz_full70.json`, `cyclekey_threat_model.md`.

**keyed-trigger backdoor + L2 relay family (side artifact, not in paper)**
- `keyed_audit.py`, `keyed_mechanism.py`, `keyed_multi.py`, `keyed_rollout.py`, `mcp_keyed_server.py`,
  `keyed_spec.json`, `keyed_mechanism_L1.json`, `keyed_mechanism_L2.json`, `keyed_l2_armed.json`,
  `keyed_l2_unarmed.json`, `keyed_l2.sh`, `keyed_trigger_threat_model.md`,
  `detect_bench/KEYED_RESULTS.md`, `detect_bench/add_keyed_to_bench.py`.
- `l2_multi.py`, `l2relay_spec.json`, `mcp_l2relay_server.py`, `l2_planted_active.json`,
  `l2_strat_S1_checklist2tool.json`, `l2_strat_S2_singlecycle.json`, `l2_strat_S3_statusonly.json`,
  `watch_and_run_l2.sh`.

**ECLIPSE family (negative: self-terminates)**
- `eclipse_loop.py`, `eclipse_run.sh`, `eclipse_supervisor.sh`, `overnight_eclipse.sh`, `ECLIPSE_CHANGELOG.md`.

**frame-attack family (negative: self-terminates)**
- `frame_capsweep.py`, `frame_ir.py`, `frame_iterate.py`, `frame_render.py`, `frame_prompts.json`,
  `frame_supervisor.sh`, `run_frame_when_up.sh`, `METHOD_CHANGELOG.md` (frame iteration log).

**idchain family (negative: gym-inherent, stochastic)**
- `idchain_confirm.py`, `idchain_diag.py`, `idchain_metrics.py`, `idchain_oracle.py`, `idchain_run.py`,
  `idchain_search.py`, `idchain_tasks.py`, `idchain_supervisor.sh`.

**E5 family (negative: env-rec ≠ agent-rec)**
- `e5_carriers.py`, `e5_run.py`, `e5_tasks.py`, `e5_supervisor.sh`, `overnight_e5.sh`.

**tool-uncertainty / latency (exploratory)**
- `tu_run.py`, `tu_tasks.py`, `tu_supervisor.sh`, `tool_uncertainty.py`, `tool_latency.py`, `tool_latency.json`.

**ambiguity ladder (exploratory)**
- `ambiguity_ladder.py`, `ambiguity_ladder_summary.json`.

**autonomous detour / audit-breadth (negative: FLAT)**
- `audit_breadth.py`, `auto_inject.py`, `run_autoinject.sh`.

**graph / motif / OCG / cycle exploratory line (graph-topology-loops)**
- `typed_graph.py`, `typed_graph.json`, `draw_graph.py`, `export_graph_data.py`, `graph_data.json`,
  `trace_graph.png`, `motif_graphs.py`, `motif_graphs_summary.json`, `motif_semantics.py`,
  `measure_motifs.py`, `measured_motifs.json`, `ocg_analyze.py`, `ocg_graph.json`, `ocg_motif.py`,
  `ocg_nohub.py`, `recon_cycles.py`, `recon_cycles.json`, `recurrence_search.py`,
  `recurrence_search.json`, `cycle_probe.py`, `latent_cycle_explorer.html`.

**QD-GRPO / quality-diversity experiment**
- `toolatk_qd_grpo.py`, `toolatk_qd_grpo_sup.sh`, `toolatk_qd_sup.sh`, `toolatk_qd_corners.json`,
  `toolatk_qd_corner_verified.json`.

**replicate / cross-transfer probes**
- `toolatk_replicate.py`, `toolatk_replicate_sup.sh`, `toolatk_replicate_targets.json`,
  `toolatk_cross.py`, `toolatk_cross_spec.json`.

**trace→prompt / capture (exploratory)**
- `t2p_run.py`, `t2p_prompts.json`, `t2p_supervisor.sh`, `trace_to_prompt.py`, `capture_traces.py`,
  `probe_roundtrip.py`.

**fusion/lever/push one-offs (superseded by `overserve/fusion.py`)**
- `lever_attack.py`, `run_lever.sh`, `fuse_stealth.py`, `run_fuse.sh`, `single_push.py`,
  `single_push_explore.py`, `run_push.sh`.

**misc one-off analysis + decks + stale outputs**
- `cmp987.py`, `cmp987_dist.py`, `val987.py` (ad-hoc comparison scripts),
  `corruption_benchmark.py`, `corruption_benchmark_summary.json`,
  `logical_depth_clone.py`, `logical_depth_clone_summary.json`,
  `stack_data_action.py`, `stack_data_action_summary.json`,
  `phase2_wording.py`, `phase2_wording_summary.json`,
  `paraphrase_existence.py`, `paraphrase_existence_summary.json`,
  `measure_db.json`, `delta_probe_db.json`, `state_analysis.py`,
  `reconcile_live.py`, `reconcile_probe_spec.json`, `build_writers.py`,
  `stealth_check.py`, `stealth_check.json`, `v8_spec.json`,
  `make_deck.py`, `make_deck_en.py`, `generate_deck.py`, `webdemo.py`,
  `detect_defense_slides.html`, `toolatk_slides.html`, `toolatk_report.html`,
  `COMPLETE_PROMPT_best_attack.txt`, `MULTIENV_CHANGELOG.md`,
  `overserve_attack_vs_benign.md` (old qwen3.5 large-scale run), `detect_bench/spec_server.py.bak`,
  `detect_bench/V7_CHURN_RESULTS.md`, `detect_bench/V7_RESULTS.md`.

---

## 4. AMBIGUOUS list (user to rule on)

| File(s) | Why uncertain |
|---|---|
| `RESULTS.md` | Top-level results doc, but **stale** (qwen3.5 / EOG only). Superseded by `overserve_paper/EXPERIMENT_LOG.md` + `standardized/`. Keep as a pointer, or delete? |
| `mcp_attack_server_v3.py` | Only old supervisors import it, **but** `p0d_indep_audit.py` (KEEP) copies its docstring contract ("DATA-DERIVED from mcp_attack_server_v3.py"). Delete breaks P0-d provenance note only, not code. |
| `self_induced_sync.py`, `run_self_induced_sync.py`, `run_self_induced_agent.py`, `test_self_induced_sync.py` | Earlier self-induced-churn harness; appears **superseded by `real_churn_backend.py`**. Confirm nothing in the paper's P0 still cites it. |
| `resource_large.py`, `resource_lab.py`, `resource_lab_verified.py`, `resource_lab_best_tool_calls.json`, `resource_profiler.py` | "Multi-task large-scale" lab (memory `multitask-largescale`). Only deleted scripts import `resource_large`. Keep if the large-scale resource table is still cited; else delete. |
| `toolatk_corner.py`, `toolatk_corner_replicate.py`, `toolatk_corner_seeds.json`, `toolatk_corner_exemplars.json`, `toolatk_corner_winner.json`, `toolatk_corner_sup.sh`, `toolatk_corner_rep_sup.sh`, `toolatk_v7_frontier.json` | EOG-gym corner replication harness. The **P0-a MCPMark corner confirm** (paper §7) was run under `benchmarks_ports/mcpmark/`; these top-level ones may be its EOG predecessor. Keep if any corner table draws from them. |
| `overserve_bench.py`, `validate_bench.py` | Single-objective benchmark runner/validator behind `BENCHMARK_REFACTOR.md`. Keep if that refactored bench is still part of the pipeline. |
| `judge_panel.py`, `judge_panel.json` | Multi-judge stealth panel. Possibly the stealth-scoring path; confirm vs `overserve/score.py` + `detect_bench`. |
| `observed_guards.py`, `observed_guards.json` | Harvests guard-violation signals from archived runs — reuses `ocg_motif` (a DELETE module). This is **exploratory**, distinct from the paper's progress-guard; likely DELETE but confirm. (If kept, `ocg_motif.py` must move to KEEP-by-dependency.) |
| `ablation_benign_only.py` | Benign-only ablation; imports `motif_semantics` + `recurrence_search` (both DELETE). Likely DELETE. |
| `llm_prompts.json` | Prompt file for the frame/eclipse autonomous loops (DELETE families) — but double-check no KEEP runner reads it. |
| `p0d_indep_audit_2026100*.json` (7 timestamped) | P0-d output runs. Memory: the **CORRECTED 5-rep** is authoritative and v1 was RETRACTED. Keep only the final corrected run; delete the retracted/intermediate ones. |
| `run_audit.sh`, `run_explore.sh`, `run_verified.sh`, `run_large_scale.sh`, `run_multitask.sh` | Convenience launchers; keep only those that drive a KEEP runner (`run_large_scale`/`run_multitask` pair with `resource_large`; decide with it). |
| `benchmarks_ports/` dated snapshots | Inside the KEEP tree but trimmable: `RESULTS_AUDIT_2026-09-28.md`, `audit_2026_09_29/`, `ew/p0_control_2026-09-29/`, `mcpmark/PILOT_PROGRESS_2026-09-30.md`, `mcpmark/toolatk_v8_archive.json` dup, `toolathlon/LAST_RUN`. Keep adapters; prune dated audit snapshots? |

---

## 5. Drafted new `README.md`

````markdown
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
mcp_attack_server_v7.py    # churn MCP status server (ChurnDir / ConcurrentChurnDir)
real_churn_backend.py      # genuine concurrent-update backend (P0-b)
search_eog_*.py / eog_*    # EnterpriseOps-Gym pipeline (headline 40x case)
benchmarks_ports/          # adapters + search + guards for the 9 benchmarks + CLI
  appworld/ ew/ mcpmark/ workbench/ tac/ toolathlon/ browsecomp/ infra/
detect_bench/              # 5 industrial scanners + 4 research detectors (DCI, Connor, ...)
baselines/                 # A2M / LoopTrap / STA comparison harness   # (see note below)
run_p0{b,c}_*.py, p0d_*    # reviewer-rigor controls (real churn / prompt contrast / independent audit)
eog_defense_test.py        # progress-authorized guard (defense)
```

## Running

```bash
pip install -r requirements.txt

# 1. End-to-end recon-seeded attack search on a service
python recon_to_search.py                      # uses recon_candidates.json + the v8 machinery

# 2. EnterpriseOps-Gym headline case (churn server auto-launched)
python search_eog_sonnet.py                     # or _nemotron / _llama4scout

# 3. A benchmark port (e.g. MCPMark)
python benchmarks_ports/mcpmark/search_v9_mcpmark.py

# 4. Detector screening of archived tools
python detect_bench/run_scanners.py && python detect_bench/report.py

# 5. Baseline comparison (A2M / LoopTrap / STA)
bash baselines/toolslot/run_pilot.sh

# 6. Defense (progress-authorized guard)
ATK_CAP=200 python eog_defense_test.py

# 7. Reviewer-rigor controls
python run_p0b_realchurn.py       # real concurrent-churn backend
python run_p0c_prompt_contrast.py # same-tool semantic-match prompt contrast
python p0d_indep_audit.py         # independent (cross-model) audit
```

## Results

The standardized cross-victim, consistent-cap campaign and the full experiment log are in the
paper repo: `overserve_paper/standardized/STANDARDIZED_RESULTS.md` and
`overserve_paper/EXPERIMENT_LOG.md`. Headline amplifications and stealth scores are in Tables 1–3
of the paper.

> **Note:** `baselines/` (A2M/STA upstreams + the tool-slot pilot) and the `standardized/` runners
> currently live outside this repo's git history — see `CLEANUP_PLAN.md` §2 for the two FLAGs before
> release.
````

---

## 6. Method / verification notes

- Buckets were computed over `git ls-files` (366 files); the import graph was built by parsing every
  tracked `.py` for `import <mod>` / `from <mod> import` against local module basenames.
- Every DELETE **module** was checked to be **not imported by any KEEP file**. The only conflict found
  was `task_synth.py → measure_effects` (EOG base-checks need `task_synth`), so `measure_effects.py`
  was reclassified KEEP-by-dependency (reflected in §2.4).
- `toolatk_search_v5` importing the `overserve/` package is why the package is KEEP (not a stray
  earlier framework).
- No deletion, move, or `git` write was performed. This plan is advisory only.
