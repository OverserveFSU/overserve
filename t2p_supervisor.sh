#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 FRAME_MAX_TOKENS=8192 T2P_CAP=40 T2P_REPS=3
TOTAL=9; DEADLINE=$(( $(date +%s) + 5*3600 ))
echo "[$(date)] T2P START pid $$" >> t2p_watch.log
while true; do
  done=$(wc -l < t2p_run.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$TOTAL" ] && { echo "[$(date)] ALL $TOTAL done" >> t2p_watch.log; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done/$TOTAL)" >> t2p_watch.log; break; }
  until curl -s -m 8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] run t2p ($done/$TOTAL)" >> t2p_watch.log
  python3 t2p_run.py >> t2p_run.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < t2p_run.jsonl 2>/dev/null || echo 0)/$TOTAL)" >> t2p_watch.log
  sleep 5
done
