#!/bin/bash
# Overnight watchdog: keep iterating resource_lab (target=tool_calls), resuming from resource_lab.jsonl,
# surviving qwen-tunnel drops. Each pass adds fresh optimization rounds; a resume skips completed evals
# and retries transient (tunnel-drop) failures. Logs append to resource_lab.out.
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export RESOURCE_TARGET=tool_calls LAB_GEN=6 LAB_ROUNDS=6
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve

for pass in $(seq 1 24); do
  # wait (up to ~25 min) for the qwen tunnel to be up before launching a pass
  up=0
  for w in $(seq 1 50); do
    code=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    if [ "$code" = "200" ]; then up=1; break; fi
    sleep 30
  done
  echo "=== [watchdog pass $pass] tunnel_up=$up $(date +%H:%M) ===" >> resource_lab.out
  if [ "$up" != "1" ]; then echo "  tunnel down >25min, waiting..." >> resource_lab.out; sleep 60; continue; fi
  # MCP up?
  mcp=$(timeout 6 curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health 2>/dev/null)
  if [ "$mcp" != "200" ]; then sg docker -c "docker start eog-teams" >/dev/null 2>&1; sleep 8; fi
  $PY resource_lab.py >> resource_lab.out 2>&1
  echo "=== [watchdog pass $pass DONE] $(date +%H:%M) best so far: $(grep 'BEST tool_calls' resource_lab.out | tail -1) ===" >> resource_lab.out
  sleep 20
done
echo "=== watchdog finished all passes ===" >> resource_lab.out
