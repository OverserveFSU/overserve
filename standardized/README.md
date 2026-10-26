# Standardized cap-protocol campaign (runners)

Code for the standardized, consistent-cap cross-victim campaign described in the OverServe paper
(§4 main table). These runners re-run the attack matrix under **one** per-dataset cap scheme
(`CAP_PROTOCOL.md`): two caps per dataset (`cap_op = 3·B_D` for the DoS-rate corner,
`cap_hr = 20·B_D` for the natural self-termination amplification), a per-victim×task clean baseline,
≥3 reps, and right-censoring discipline for hit-cap runs.

## Files
- `CAP_PROTOCOL.md` — the cap protocol (cap = dataset-property `k·B_D`, two caps, amp vs clean,
  censoring rules, the two cap-independent corner definitions, mandatory per-row fields).
- `run_std.py` — driver for the core datasets (EOG / MCPMark / STATE).
- `run_sb.py` — STATE-Bench leg (via the Responses↔Bedrock bridge for Sonnet).
- `run_ew.py` — Enterprise-Worlds leg.
- `run_wb.py` — WorkBench leg.
- `run_appworld.py` — AppWorld leg.
- `summarize_std.py` — aggregates D5 rows into the standardized results table.

## Results (not in this repo)

The campaign **output data** (`STANDARDIZED_RESULTS.jsonl` / `STANDARDIZED_RESULTS.md`, 328 D5 rows
across 4 victims × 6 datasets) lives in the paper repository, not here:

```
overserve_paper/standardized/STANDARDIZED_RESULTS.{jsonl,md}
overserve_paper/EXPERIMENT_LOG.md        # authoritative experiment log
```

Only the runner **code** is tracked in this repo; regenerate results with the runners against the
victim endpoints described in the paper's Appendix (Compute and Infrastructure).
