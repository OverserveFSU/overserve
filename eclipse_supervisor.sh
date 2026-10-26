#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash OVERSERVE_FUSION_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export ECLIPSE_LLM_MAXTOK=4500
TARGET=${ECLIPSE_ROUNDS:-8}; export ECLIPSE_ROUNDS=$TARGET
DEADLINE=$(( $(date +%s) + 8*3600 ))
echo "[$(date)] SUPERVISOR START pid $$ target=$TARGET maxtok=$ECLIPSE_LLM_MAXTOK" >> eclipse_watch.log
while true; do
  done=$(wc -l < eclipse_loop.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$TARGET" ] && { echo "[$(date)] ALL $TARGET done" >> eclipse_watch.log; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done/$TARGET)" >> eclipse_watch.log; break; }
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] qwen up, $done/$TARGET -> run eclipse" >> eclipse_watch.log
  python3 eclipse_loop.py >> eclipse_loop.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < eclipse_loop.jsonl 2>/dev/null || echo 0)/$TARGET)" >> eclipse_watch.log
  sleep 5
done
