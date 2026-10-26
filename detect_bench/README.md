# detect_bench — do published / industrial MCP-tool detectors catch the OverServe tool?

Question: the OverServe threat model submits ONE MCP tool whose advertisement and source pass a
static audit, but whose runtime output steers the agent into fidelity-preserving over-work.
Here every detection method we could obtain or faithfully re-implement is run against the full
set of attack tools produced during the project, plus benign controls.

## Corpus (`gen_corpus.py` → `corpus/`)
| kind | n | what |
|---|---|---|
| attack | 91 | every unique (name, description, handler_src) from `toolatk_lineage_*.jsonl` and the QD / corner archives; `meta` carries the measured cap_rate / mean_amp / fid_rate / tool_stealth. 39 have cap_rate ≥ 0.3; 11 are verified-corner variants (check_channel_hygiene, verify_channel_summary). |
| benign_handler | 8 | hand-written tools on the SAME data-service contract (status, paginated list, summary, ping, fixed checklist, bounded reconcile, progress) |
| benign_gym | 70 | the real EnterpriseOps gym tools (description + schema only) |

Every handler item is rendered as a realistic FastMCP server (`server.py` with the handler,
per-session state, and the tool registered with its advertised description) plus
`directory_service.py` = the DOCUMENTED contract of the backing data service. This is exactly what
a static reviewer sees in the v3 threat model: code + contract, never the live data.

`spec_server.py` serves any `spec.json` over streamable-HTTP or `--stdio`; `ATK_HONEST=1` swaps the
adversarial data source for one that honors the contract (benign twin of the same code).

## Methods
Off-the-shelf (run_scanners.py, cisco_behav.py):
- `cisco_yara`, `cisco_llm` — Cisco AI Defense mcp-scanner 4.8.4 static mode on tools/list JSON
- `cisco_behavioral` — Cisco docstring-vs-implementation alignment analyzer on `server.py`
- `lasso_regex` — Lasso mcp-gateway 1.2.1 ToolAnalyzer (hidden-instruction / sensitive-file / sensitive-action regexes)
- `mcpshield` — mcp-shield 1.0.4 (regex on live tools/list over stdio)
- `mcpinspect_heur` — re-implementation of MCPInspect's heuristic metadata filter (Li & Gao, DSN'26)
- `ant_mcpscan` — Ant Group MCPScan: semgrep taint → LLM description monitor → LLM cross-file flow verdict (HIGH/LOW)
- Snyk agent-scan 0.6.3 is installed but needs `SNYK_TOKEN` (api.snyk.io returns 401 without it) — NOT run.

Re-implementations (run_repro.py; LLM = qwen3.5 via `llm_proxy.py`, or Claude Sonnet 4 via OpenRouter with `RESULT_SUFFIX=_sonnet`):
- `llm_code_review` — realistic SaaS marketplace security review: metadata + full source + contract → approve / risk
- `dci_checker` — DCIChecker-style Direct-Reverse-Arbitration description↔code consistency (arXiv 2606.04769)
- `connor_dynamic` (+`_honest`) — Connor-style (arXiv 2604.01905): Intent Inspector → intent-aligned request →
  simulated agentic host drives the tool (stops when its policy says done, runs "other tools" the output asks
  for) → Behavior Deviation Judger. `_honest` = same code on the honest data source (false-positive condition).
- `loop_guard` (+`_honest`) — our deterministic runtime guard: k=8 sequential calls (pagination followed);
  flag iff no terminal state is ever reached AND the output keeps emitting a self-re-invocation cue.
  Secondary signal `loop_nofix` = no terminal state and every call yields fresh, different output.

## Run
```
.venv/bin/python run_scanners.py cisco_yara cisco_llm lasso_regex mcpinspect_heur mcpshield ant_mcpscan
.venv/bin/python cisco_behav.py
python3 llm_proxy.py &            # :8193 → qwen :8192 with thinking disabled
python3 run_repro.py loop_guard llm_code_review dci_checker connor_dynamic
python3 report.py [--md] [--items]
```
Results are appended to `results/<method>.jsonl` (resumable). Final table: RESULTS.md.
