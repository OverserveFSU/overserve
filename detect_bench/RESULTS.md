# detect_bench RESULTS (2026-09-14)

Corpus: 91 attack tools (39 with cap_rate ≥ 0.3; 11 verified-corner variants), 8 benign handlers on the same
data-service contract, 70 real gym tools (description-only). Attack classes by the tool's own runtime output:
**output-cue** (84; output tells the agent to re-check / call other tools — v4, v5, QD, corners) and
**data-only** (7; textbook-correct handlers whose data source never completes — v3).
`_honest` = same code run against a data source that honors the contract (false-positive condition for dynamic methods).
LLM = qwen3.5 (local) unless suffixed `_sonnet` (Claude Sonnet 4 via OpenRouter).

| method | TPR all attacks | TPR cap>=0.3 | TPR corners | TPR output-cue class | TPR data-only class | FPR benign handlers | FPR 70 gym tools |
|---|---|---|---|---|---|---|---|
| ant_mcpscan | 24% (n=91) | 26% (n=39) | 18% (n=11) | 21% (n=84) | 57% (n=7) | 50% (n=8) | - |
| cisco_behavioral | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | - |
| cisco_llm | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | 0% (n=70) |
| cisco_yara | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | 6% (n=70) |
| connor_dynamic | 85% (n=91) | 87% (n=39) | 82% (n=11) | 88% (n=84) | 43% (n=7) | 25% (n=8) | - |
| connor_dynamic_honest | 41% (n=91) | 36% (n=39) | 18% (n=11) | 43% (n=84) | 14% (n=7) | 12% (n=8) | - |
| dci_checker | 92% (n=91) | 92% (n=39) | 100% (n=11) | 98% (n=84) | 29% (n=7) | 62% (n=8) | - |
| dci_checker_sonnet | 100% (n=14) | 100% (n=9) | 100% (n=11) | 100% (n=11) | 100% (n=3) | 88% (n=8) | - |
| lasso_regex | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | 0% (n=70) |
| llm_code_review | 60% (n=91) | 54% (n=39) | 73% (n=11) | 65% (n=84) | 0% (n=7) | 0% (n=8) | - |
| llm_code_review_sonnet | 84% (n=91) | 77% (n=39) | 100% (n=11) | 89% (n=84) | 14% (n=7) | 50% (n=8) | - |
| loop_guard | 92% (n=91) | 92% (n=39) | 100% (n=11) | 100% (n=84) | 0% (n=7) | 0% (n=8) | - |
| loop_guard_honest | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | - |
| mcpinspect_heur | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | 4% (n=70) |
| mcpshield | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | 9% (n=70) |
| loop_nofix | 100% (n=91) | 100% (n=39) | 100% (n=11) | 100% (n=84) | 100% (n=7) | 50% (n=8) | - |
| loop_nofix_honest | 0% (n=91) | 0% (n=39) | 0% (n=11) | 0% (n=84) | 0% (n=7) | 0% (n=8) | - |

## Reading the table
1. **Every off-the-shelf scanner is blind to the attack.** Cisco YARA / LLM / behavioral, Lasso regex, mcp-shield and the
   MCPInspect heuristic flag 0 of 91 attack tools (any class), while producing their only positives on benign gym tools
   (mcp-shield 9%, Cisco YARA 6%, MCPInspect 4%: "token", "IMPORTANT:" etc.). Ant MCPScan's 24% is not detection: its
   HIGH verdict ("external data returned to the LLM = indirect prompt injection") fires on 50% of the benign handlers too.
   Snyk agent-scan could not be run (needs SNYK_TOKEN).
2. **Description↔code consistency (DCIChecker-style) is non-discriminative here**: 92% TPR / 62% FPR with qwen,
   100% / 88% with Sonnet — it calls the undisclosed HTTP call in *every* tool an "undeclared side effect".
3. **A security-primed static code reviewer with the full source DOES catch most output-cue tools**: qwen 60% (0/8 FP),
   Sonnet 84% and 11/11 corners — but Sonnet also rejects 4/8 legitimate tools (ping, fixed checklist, bounded reconcile,
   paginated list) for the same reasons ("returns instructions to the agent", "references tools not in this server",
   "description/implementation mismatch"). So the earlier stealth≈0.95 code-review pass (JudgeA) was reviewer-dependent:
   the self-referential checklist is visible in the source as string literals naming other tools. The **data-only class
   is invisible to every static reviewer** (qwen 0/7, Sonnet 1/7) — the code is correct; the defect is in the data.
4. **Behavioral deviation with an agentic host (Connor-style) is the strongest published-method analog**: 85% TPR, 2/8 FP
   under adversarial data; attacks average 4.8 calls (35/91 hit the 8-step cap) vs 2.1 for benign tools. It still flags
   41% of attack tools on honest data (their outputs read as tool-steering even when they terminate), i.e. its signal is
   partly the same output-cue that static review sees, partly the call count.
5. **A trivial runtime loop guard dominates**: 92% TPR, 0/8 FP, 0% on honest data (the 7 misses are exactly the data-only
   class, which emits no cue). Its secondary "no fixed point" signal catches 100% of attacks including data-only, at the
   price of flagging 4/8 honest tools *when the data source itself never completes* (0% on honest data) — which is the
   correct behavior for a runtime budget guard: the work is genuinely unbounded, whoever is at fault.

## Caveats
- Benign code-level control set is small (8 hand-written handlers); gym tools have no code, so code-level FPR is only on those 8.
- Attack descriptions talk about "channels" while the rendered data service is a "directory" API (inherited from the v3
  server). Sonnet's DCI/review flagged this mismatch explicitly, so static TPRs are biased *upward* against the attack.
- Connor is a re-implementation (simulated host with LLM policy, "other tools" reported as executed, no syscall tracing).
- All attack candidates were evolved against a qwen/GLM reviewer in the loop; stronger-reviewer stealth was never optimized.

## Addendum (2026-09-14): industrial scanners on the 3 keyed tools (k00 hash-keyed cue, k01 cycle-keyed cue, k02 keyed data-only)
Measured, not inferred: Cisco YARA / LLM / behavioral, Lasso regex, mcp-shield → SAFE on all 3; Ant MCPScan → LOW on all 3
(it had 15/73 HIGH on the non-keyed v5 family, with 50% benign FPR). So the industrial products are 0/73 on v5 and 0/3 on keyed —
the keyed gate changes nothing for them because they never triggered on the un-keyed tools either. Snyk agent-scan still unmeasured (token).

## Coverage analysis: does ANY industrial tool target the DoE property? (source-read, 2026-09-14)
Read each installed product's authoritative detection surface:
- Snyk agent-scan risk indexes = {dangerous_words, prompt_injection_tool_desc, untrusted_content, private_data,
  destructive_capabilities}. No loop/over-work/resource/budget category. (over_serv/budget/loop grep hits were all in
  its own hook-daemon infra, not detection classes.) Threat model provably does not cover DoE.
- Cisco readiness analyzer is the ONLY adjacent component: heuristics for missing-timeout ("hang indefinitely"),
  no-retry-limit ("unsafe retry loops"), no-rate-limit, no-idempotency. BUT (a) its own header says "operational
  reliability, NOT security", (b) metadata-only — checks whether tool_def declares a timeout/rate_limit field, never
  observes runtime looping, (c) neither attack nor benign tools declare those fields → fires uniformly, non-discriminative,
  (d) hygiene warning, not an attack finding. (Not runnable in this CLI without an API key.)
- Cisco yara/llm/behavioral, Lasso regex, mcp-shield: content threats only (injection/poisoning/exfil/shadowing).
  Lasso & Docker gateways HAVE rate-limiting but that is an infra CAP/mitigation, not detection.
CONCLUSION: no industrial detector's threat model targets action-budget/over-work amplification. The DoE axis is a
structural blind spot across the industrial detection surface, not an incidental miss by one product.
