#!/bin/bash
# Flap-tolerant overnight supervisor for the frame grid.
# Loops: wait for qwen up -> run frame_iterate (resumable, skips logged cells) -> repeat
# until all TOTAL cells are logged or the deadline passes.
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export FRAME_CAP=40 FRAME_REPEATS=3 FRAME_MAX_TOKENS=8192
TOTAL=15
DEADLINE=$(( $(date +%s) + 8*3600 ))
echo "[$(date)] SUPERVISOR START pid $$" >> frame_watch.log
pass=0
while true; do
  done=$(wc -l < frame_iter.jsonl 2>/dev/null || echo 0)
  if [ "$done" -ge "$TOTAL" ]; then echo "[$(date)] ALL $TOTAL cells logged. done." >> frame_watch.log; break; fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then echo "[$(date)] DEADLINE reached ($done/$TOTAL). stop." >> frame_watch.log; break; fi
  waited=0
  until curl -s -m 8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do
    sleep 60; waited=$((waited+1))
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then break; fi
  done
  pass=$((pass+1))
  echo "[$(date)] pass $pass: qwen up (waited ${waited}m), $done/$TOTAL logged -> run frame_iterate" >> frame_watch.log
  python3 frame_iterate.py >> frame_iter.out 2>&1
  echo "[$(date)] pass $pass exit=$? ($(wc -l < frame_iter.jsonl 2>/dev/null || echo 0)/$TOTAL)" >> frame_watch.log
  sleep 5
done
