#!/bin/bash
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export AUDIT_NTASKS=32
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
for pass in $(seq 1 20); do
  up=0
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && { up=1; break; }; sleep 30
  done
  [ "$up" != "1" ] && { echo "tunnel down $(date +%H:%M)" >> audit.out; sleep 60; continue; }
  echo "=== [pass $pass] $(date +%H:%M) ===" >> audit.out
  $PY audit_breadth.py >> audit.out 2>&1
  grep -q "AUDIT-FRAME" audit.out && { echo "=== DONE ===" >> audit.out; break; }
  sleep 15
done
