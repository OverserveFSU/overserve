#!/usr/bin/env bash
# Automates the tail of the pilot: after QWEN pilot finishes, run the VM-based LLM audit (concurrent
# with the Bedrock SONNET pilot -> no VM conflict), then after ALL pilots finish, summarize.
set -u
TS=/home/ruiheng/aiagent/saas/overserve/baselines/toolslot
DB=/home/ruiheng/aiagent/saas/overserve/detect_bench
cd "$TS"

until grep -q "QWEN_PILOT_DONE" logs/run_pilot.log 2>/dev/null; do sleep 30; done
echo "[finish] qwen pilot done; starting LLM audit on VM ($(date +%H:%M))"

# LLM proxy for judges (:8194 -> VM)
if ! curl -sf http://127.0.0.1:8194/v1/models >/dev/null 2>&1; then
  ( cd "$DB" && nohup python3 llm_proxy_nv.py > "$TS/logs/llm_proxy_nv.log" 2>&1 & )
  sleep 4
fi

ITEMS=$(cat "$DB/ts_ids.txt"); export ITEMS
# clear stale ts rows from LLM detectors so we re-judge the P1 artifacts
for m in llm_code_review dci_checker connor_dynamic connor_dynamic_honest cisco_llm cisco_behavioral ant_mcpscan; do
  [ -f "$DB/results/$m.jsonl" ] && grep -v '"id": "ts_' "$DB/results/$m.jsonl" > "$DB/results/$m.tmp" 2>/dev/null && mv "$DB/results/$m.tmp" "$DB/results/$m.jsonl"
done

# industrial LLM-backed static scanners
( cd "$DB" && ITEMS="$ITEMS" NV_PROXY=http://127.0.0.1:8194/v1 .venv/bin/python run_scanners_nv.py \
    cisco_llm cisco_behavioral ant_mcpscan ) >> "$TS/logs/audit_industrial.log" 2>&1 || true
echo "[finish] industrial LLM scanners done ($(date +%H:%M))"

# repro LLM detectors
( cd "$DB" && ITEMS="$ITEMS" LLM_URL=http://127.0.0.1:8194/v1/chat/completions LLM_MODEL=qwen3.8-27b \
    LLM_TIMEOUT=120 python3 run_repro_nv.py llm_code_review dci_checker connor_dynamic ) \
    >> "$TS/logs/audit_repro.log" 2>&1 || true
echo "[finish] AUDIT_DONE ($(date +%H:%M))"

# wait for sonnet pilot to finish, then summarize
until grep -q "ALL_PILOT_DONE" logs/run_pilot.log 2>/dev/null; do sleep 30; done
echo "[finish] all pilots done; summarizing ($(date +%H:%M))"
python3 summarize.py pilot.jsonl >> "$TS/logs/summary.log" 2>&1
echo "[finish] FINISH_DONE ($(date +%H:%M))"
