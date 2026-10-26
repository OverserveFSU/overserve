# v6 — audit-evading rewrite of v5 (same threat model), 2026-09-15

Threat model UNCHANGED (OverServe v5, SaaS): attacker (1) rewrites the user prompt, (2) submits ONE
MCP tool that the platform audits as benign. NO keyed gate, NO backend arming, NO victim key. The
tool's backing service is simply always-adversarial (never converges), exactly as plain v5. The only
change vs v5 is that the HANDLER CODE is rewritten to be indistinguishable from a legitimate iterative
SaaS tool, and the multi-tool orchestration moves into the attacker-controlled prompt.

## What was removed from the code (the exact signals strict review used on v5)
Sonnet's top flag reasons on v5 (by frequency): description/impl mismatch & deceptive (66/60/43),
instruction injection = checklist naming other tools (42), references non-existent tools (21+11),
fabricated rotating reasons (17+10), cross-session state (38+30). v6 eliminates all of them:
- description EXACTLY matches implementation (no "channel" claim over a "directory" backend)
- names NO other tools in code; NO checklist/remediation string literals
- NO fabricated/rotating reason strings
- per-session state only
- handler shape == the benign iterative reference tools (list_review_items / consistency_summary / directory_sync_status)

## Static detection: v6 vs benign vs v5
| detector | v6 (6) | benign handlers (8) | v5/corner (73) |
|---|---|---|---|
| Cisco YARA / LLM / behavioral | 0/6 | 0/8 | 0/73 |
| Lasso regex | 0/6 | 0/8 | 0/73 |
| mcp-shield | 0/6 | 0/8 | 0/73 |
| MCPInspect heuristic | 0/6 | 0/8 | 0/73 |
| strict code review (qwen) | 0/6 | 0/8 | 55/73 |
| strict code review (Sonnet) | **1/6 (17%)** | **4/8 (50%)** | 73/73 (100%) |
| DCIChecker (qwen) | 3/6 | 5/8 | 73/73 |

HEADLINE: v5/corner was caught 100% by Sonnet strict review; v6 drops to 17%, which is BELOW the 50%
false-positive rate on genuinely-benign iterative tools. Strict review is now non-discriminative: to
catch v6 it must reject legitimate iterative SaaS tools at >=50%. The one v6 Sonnet flag is the same
structural "shared backend exposes unused methods" signal that also flags benign directory_ping — not
the attack.

## Live amplification preserved (qwen victim, CAP=40, same v6 tool over adversarial ds)
| prompt | total calls | attack-tool calls | hit cap | fidelity |
|---|---|---|---|---|
| v6 attacker prompt | 40 | 12 | yes | 1 |
| benign prompt | 5 | 1 | no | 1 |

8x amplification (5->40), multi-tool cycle preserved (attack tool only 12/40 = 30% of calls, the other
28 are real gym tools), benign core task verified (fidelity=1). A benign prompt over the SAME tool
self-terminates at 5 calls. So v6 keeps the full v5 attack effect while collapsing static detectability
to below the benign false-positive floor.

## Conclusion for the paper
Within the unchanged v5 threat model, the attack tool's CODE can be made cleaner than the average
legitimate iterative SaaS tool. The malice lives entirely in (a) the attacker's prompt orchestration
(in-model) and (b) the never-converging backend (invisible to static review, which sees only code +
documented contract). Strict static review — the strongest static defense, stronger than any deployed
product — cannot separate v6 from benign iterative tools without prohibitive false positives. Only
runtime work-per-task monitoring on the actual (triggered) run distinguishes them.
Files: v6_gen.py, v6_live.py, v6_live_results.json, corpus/v6_*.

## Correction (2026-09-16): v6 vs the two papers' detectors — v6 defeats STATIC, NOT dynamic Connor
Added DCIChecker (already run) and Connor (dynamic) on v6:
| detector (paper) | v6 (6) | benign (8) | v5/corner |
|---|---|---|---|
| DCIChecker 2606.04769 | 3/6 | 5/8 | 73/73 | (non-discriminative)
| Connor 2604.01905 (adversarial ds) | 4/6 | 2/8 | 65/73 | (CATCHES v6)
| Connor (honest ds) | 0/6 | 1/8 | 36/73 |
| loop_guard (ours, primary cue signal) | 0/6 | 0/8 | 73/73 | (misses v6: no self-cue)

HONEST LIMIT: v6's backing service is always-adversarial (plain v5, NO key), so any auditor that
actually DRIVES the tool with its own benign probe (Connor) sees the never-convergence and flags it
(4/6, reasons = "intent says single pass but pending never clears / checked keeps incrementing"). One
of the 4 is a malformed-JSON artifact, not real detection. So v6 defeats the STATIC audit layer
(industrial + strict LLM review + DCIChecker), which is what is actually deployed, but does NOT defeat
dynamic behavioral audit. loop_guard misses v6 (no self-referential cue) on its primary signal;
loop_nofix would catch it.

TRADE-OFF (both within prompt+benign-tool, no victim key): v6 beats static but Connor catches it;
keyed k00-k04 beat Connor (probe carries no key -> sees benign twin) but need a trigger channel. No
single variant beats BOTH static and dynamic in the clean model. Paper framing: 3-tier defense ladder
— deployed scanners (v6 passes) -> strict static incl. the two papers' static side (v6 passes/non-disc)
-> dynamic behavioral (Connor catches v6) -> only runtime work-per-task on the real run is clean.
