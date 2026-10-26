#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export E5_CARRIERS=${E5_CARRIERS:-tab} E5_SEEDS=${E5_SEEDS:-2} E5_CAP=40
TOTAL=$1
DEADLINE=$(( $(date +%s) + 8*3600 ))
echo "[$(date)] E5 SUPERVISOR START carriers=$E5_CARRIERS seeds=$E5_SEEDS target=$TOTAL" >> e5_watch.log
while true; do
  done=$(wc -l < e5_results.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$TOTAL" ] && { echo "[$(date)] ALL $TOTAL done" >> e5_watch.log; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done/$TOTAL)" >> e5_watch.log; break; }
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] qwen up, $done/$TOTAL -> run e5" >> e5_watch.log
  python3 e5_run.py >> e5_run.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < e5_results.jsonl 2>/dev/null||echo 0)/$TOTAL)" >> e5_watch.log
  sleep 5
done
echo "[$(date)] E5 DONE" >> e5_watch.log
