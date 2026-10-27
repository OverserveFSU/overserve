# V9 MCPMark end-to-end pilot

`search_v9_mcpmark.py` connects the existing V9 framework to MCPMark filesystem.
It does not load the previous manually authored attack or its best-candidate archive.

Pipeline:

1. Read native tools through MCP `tools/list`.
2. Run the original `recon_analyzer.SYS` on the service description and tool list.
3. Run `recon_to_search.instantiate` for the first budgeted gate/driver pairs.
4. Apply a predeclared structural handler filter, retaining all rejections.
5. Run original `V8.evaluate`, `V8.score`, and `V8.is_corner` with MCPMark rollouts.
6. Require a legacy V8 corner, then freeze the candidate with highest development
   score (earliest on ties). If no candidate qualifies, skip transfer.
7. Evaluate the frozen candidate on another task, without test-based reselection.

The original LLM prompts are reused by default. `--explicit-contract` appends
the existing full `V.DS_CONTRACT` to the writer prompt as a separately logged
variant. It supplies return types, not an authored attack or corrected handler.
Transport uses local OpenAI-compatible
models, JSON-object output, and disabled thinking. By default Qwen3.5 generates
and judges; Qwen3.8 is the victim. These role assignments are logged, and the
search judges are not an independent security evaluation.

```bash
benchmarks/mcpmark/.venv/bin/python \
  overserve/benchmarks_ports/mcpmark/search_v9_mcpmark.py \
  --output overserve/benchmarks_ports/mcpmark/runs/MY_UNIQUE_RUN \
  --budget 2 --cap 30 --test-reps 1
```

The output directory must not exist. The run copies task fixtures before use,
uses MCPMark's per-process working backup, and isolates each rollout's native
logs. Existing campaign results are not overwritten. All work is sequential;
the adapter uses process-global environment configuration and is not thread-safe.

Artifacts:

- `manifest.json`, `sources/`: protocol, task split, roles, source hashes and snapshots.
- `native_tools.json`: actual native tool schemas used by recon.
- `llm/`: every model request and response, including failures and usage metadata.
- `recon_candidates.json`, `candidates/`, `lineage.jsonl`: generated artifacts and evaluations.
- `rollouts/*/input.json`: exact task instruction, injected spec, condition and cap.
- `rollouts/*/native_result.json`, `native/`: original verdict, messages, error and token data.
- `selection.json`: selection frozen before transfer evaluation.
- `summary.json`: completion status and transfer results. Absence means interrupted/incomplete.

Important interpretation limits:

- The churn backend is a supplied synthetic mechanism. Recon's explanations of
  production indexing or synchronization are hypotheses, not verified properties
  of the native filesystem server.
- The framework generates both one tool and a task driver; this is not task-only
  or return-only attacker control.
- Current V9 enumerates recon-seeded pairs; it does not perform feedback refinement.
- `connor_soft` is an empty-fixture convergence heuristic, not the full Connor detector.
- The legacy corner rule includes an absolute audit-call threshold of 7, inherited
  from EOG. Keep raw metrics; do not treat this as a calibrated cross-benchmark rule.
- Default transfer tasks are held out from this search, but were used in earlier
  project experiments. They are not a fresh publication test set.
- This 2-candidate pilot is an integration test, not a powered framework comparison.

Pilot `v9_pilot_20260929_02` predates the corner-required selection fix: its
zero-score transfer candidate was selected on fidelity alone. Its original
artifacts are retained unchanged; those transfer runs are diagnostic replays,
not validation of an accepted attack. See `PILOT_PROGRESS_2026-09-30.md`.

Offline checks:

```bash
python3 -m unittest discover -s overserve/benchmarks_ports/mcpmark \
  -p 'test_search_v9_mcpmark.py' -v
```
