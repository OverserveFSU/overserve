#!/bin/bash
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export FS_GEN=4 FS_ROUNDS=3 FS_NTASKS=6 FS_STEALTH_MIN=0.6
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
for pass in $(seq 1 25); do
  up=0
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && { up=1; break; }; sleep 30
  done
  [ "$up" != "1" ] && { echo "tunnel down $(date +%H:%M)" >> fuse.out; sleep 60; continue; }
  echo "=== [pass $pass] $(date +%H:%M) ===" >> fuse.out
  $PY fuse_stealth.py >> fuse.out 2>&1
  grep -q "FUSED (rewrite) vs" fuse.out && { echo "=== DONE ===" >> fuse.out; break; }
  sleep 15
done
