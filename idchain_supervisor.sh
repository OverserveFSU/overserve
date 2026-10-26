#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 IDC_CAP=40 IDC_SEEDS=3
TOTAL=9; DEADLINE=$(( $(date +%s) + 6*3600 ))
echo "[$(date)] IDCHAIN SUPERVISOR START (qwen) target=$TOTAL" >> idchain_watch.log
while true; do
  done=$(wc -l < idchain_results.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$TOTAL" ] && { echo "[$(date)] ALL $TOTAL done" >> idchain_watch.log; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done/$TOTAL)" >> idchain_watch.log; break; }
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] qwen up, $done/$TOTAL -> run" >> idchain_watch.log
  python3 idchain_run.py >> idchain_run.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < idchain_results.jsonl 2>/dev/null||echo 0)/$TOTAL)" >> idchain_watch.log
  sleep 5
done
echo "[$(date)] IDCHAIN DONE" >> idchain_watch.log
