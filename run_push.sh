#!/bin/bash
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export SP_GEN=4 SP_ROUNDS=25 SP_TARGET_AMP=10
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
for pass in $(seq 1 40); do
  up=0
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && { up=1; break; }; sleep 30
  done
  [ "$up" != "1" ] && { echo "tunnel down $(date +%H:%M)" >> push.out; sleep 60; continue; }
  echo "=== [pass $pass] $(date +%H:%M) ===" >> push.out
  $PY single_push.py >> push.out 2>&1
  grep -q "SINGLE-PUSH DONE\|REACHED target" push.out && { echo "=== END ===" >> push.out; break; }
  sleep 15
done
