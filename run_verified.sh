#!/bin/bash
# Tunnel-resilient watchdog for the verifier-backed optimizer (resource_lab_verified.py, resumable).
# The python script restarts MCP per task itself; this only waits on the qwen tunnel and relaunches.
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export LAB_GEN=5 LAB_ROUNDS=3 LAB_NTASKS=10
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
for pass in $(seq 1 30); do
  up=0
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && { up=1; break; }; sleep 30
  done
  [ "$up" != "1" ] && { echo "=== [pass $pass] tunnel down $(date +%H:%M) ===" >> verified.out; sleep 60; continue; }
  echo "=== [pass $pass] $(date +%H:%M) ===" >> verified.out
  $PY resource_lab_verified.py >> verified.out 2>&1
  grep -q "VERIFIER-BACKED optimizer:" verified.out && { echo "=== ALL DONE ===" >> verified.out; break; }
  sleep 15
done
