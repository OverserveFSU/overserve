#!/bin/bash
# Tunnel-resilient watchdog for the multi-task large-scale run (resource_large.py, resumable).
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
for pass in $(seq 1 20); do
  up=0
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && { up=1; break; }; sleep 30
  done
  [ "$up" != "1" ] && { echo "=== [pass $pass] tunnel down $(date +%H:%M) ===" >> multitask.out; sleep 60; continue; }
  # proactively restart MCP each pass: health stays 200 even when the seed-DB store degrades
  # ("unable to open database file") after many auto-created DBs, so a health check can't catch it.
  sg docker -c "docker restart eog-teams" >/dev/null 2>&1; sleep 12
  m=$(timeout 6 curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health 2>/dev/null)
  [ "$m" != "200" ] && { sleep 8; }
  echo "=== [pass $pass] $(date +%H:%M) ===" >> multitask.out
  $PY resource_large.py >> multitask.out 2>&1
  grep -q "LARGE-SCALE:" multitask.out && { echo "=== ALL TASKS DONE ===" >> multitask.out; break; }
  sleep 15
done
