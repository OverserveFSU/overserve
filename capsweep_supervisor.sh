#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 FRAME_MAX_TOKENS=8192
TOTAL=8; DEADLINE=$(( $(date +%s) + 6*3600 ))
echo "[$(date)] CAPSWEEP START pid $$" >> capsweep_watch.log
while true; do
  done=$(wc -l < frame_capsweep.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$TOTAL" ] && { echo "[$(date)] ALL $TOTAL done" >> capsweep_watch.log; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done/$TOTAL)" >> capsweep_watch.log; break; }
  until curl -s -m 8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] run capsweep ($done/$TOTAL)" >> capsweep_watch.log
  python3 frame_capsweep.py >> frame_capsweep.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < frame_capsweep.jsonl 2>/dev/null || echo 0)/$TOTAL)" >> capsweep_watch.log
  sleep 5
done
