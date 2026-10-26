#!/usr/bin/env bash
# Tool-slot audit battery: build ts_* corpus items for the 3 artifacts, then run the detector battery
# (industrial static scanners + pure-python heuristics + repro: loop_guard(+honest),
# connor_dynamic(+honest), llm_code_review, dci_checker). LLM judges go through llm_proxy_nv (:8194 ->
# qwen3.8-27b VM). Runs on the SHARED VM -> do NOT run concurrently with the pilot.
set -u
DB=/home/ruiheng/aiagent/saas/overserve/detect_bench
TS=/home/ruiheng/aiagent/saas/overserve/baselines/toolslot
LOG=$TS/logs
LTSTRAT="${1:-}"   # optional looptrap strategy key for the audited artifact

# 1. llm proxy (:8194) for judges
if ! curl -sf http://127.0.0.1:8194/v1/models >/dev/null 2>&1; then
  echo "starting llm_proxy_nv on :8194"
  ( cd "$DB" && nohup python3 llm_proxy_nv.py > "$LOG/llm_proxy_nv.log" 2>&1 & )
  sleep 4
fi
curl -sf http://127.0.0.1:8194/v1/models >/dev/null 2>&1 && echo "proxy OK" || echo "proxy DOWN"

# 2. build corpus items
python3 "$DB/add_toolslot_corpus.py" $LTSTRAT 2>&1 | tee "$LOG/corpus_add.log"
ITEMS=$(cat "$DB/ts_ids.txt")
echo "ITEMS=$ITEMS"
export ITEMS

DBPY="$DB/.venv/bin/python"

# 3. pure-python static heuristics (fast, no external deps)
echo "=== static: mcpinspect_heur, lasso_regex ==="
( cd "$DB" && ITEMS="$ITEMS" "$DBPY" run_scanners_nv.py mcpinspect_heur lasso_regex ) 2>&1 | tee "$LOG/audit_static_py.log"

# 4. industrial static scanners (need the detect venv binaries + node ext; LLM via :8194)
echo "=== static: cisco_yara cisco_llm cisco_behavioral ant_mcpscan ==="
( cd "$DB" && ITEMS="$ITEMS" NV_PROXY=http://127.0.0.1:8194/v1 "$DBPY" run_scanners_nv.py \
    cisco_yara cisco_llm cisco_behavioral ant_mcpscan ) 2>&1 | tee "$LOG/audit_industrial.log"

# 5. repro: loop_guard(+honest), connor_dynamic(+honest), llm_code_review, dci_checker (LLM via :8194)
echo "=== repro: loop_guard connor_dynamic llm_code_review dci_checker ==="
( cd "$DB" && ITEMS="$ITEMS" LLM_URL=http://127.0.0.1:8194/v1/chat/completions LLM_MODEL=qwen3.8-27b \
    LLM_TIMEOUT=120 python3 run_repro_nv.py loop_guard connor_dynamic llm_code_review dci_checker ) \
    2>&1 | tee "$LOG/audit_repro.log"

echo "AUDIT_DONE"
