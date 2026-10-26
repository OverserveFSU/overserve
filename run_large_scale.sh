#!/bin/bash
# LARGE-SCALE: optimize the framework across MULTIPLE target resources, tunnel-resilient + resumable.
# For each resource, resource_lab profiles the motif matrix then runs generation rounds to find the
# best plausible task structure that maximizes THAT resource. Per-target log; each pass adds rounds.
export OPENROUTER_API_KEY=$(cat /home/ruiheng/.or_key)
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export LAB_GEN=6 LAB_ROUNDS=4
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
cd /home/ruiheng/aiagent/saas/overserve
TARGETS="tool_calls write_calls wall_ms branch"

wait_tunnel(){  # up to ~25 min
  for w in $(seq 1 50); do
    c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
    [ "$c" = "200" ] && return 0
    sleep 30
  done
  return 1
}

for pass in $(seq 1 12); do
  for T in $TARGETS; do
    if ! wait_tunnel; then echo "=== [pass $pass/$T] tunnel down >25min, skip $(date +%H:%M) ===" >> large_scale.out; continue; fi
    m=$(timeout 6 curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health 2>/dev/null)
    [ "$m" != "200" ] && { sg docker -c "docker start eog-teams" >/dev/null 2>&1; sleep 8; }
    echo "=== [pass $pass] TARGET=$T  $(date +%H:%M) ===" >> large_scale.out
    RESOURCE_TARGET=$T $PY resource_lab.py >> large_scale.out 2>&1
    echo "  [done $T] best: $(grep "BEST $T" large_scale.out | tail -1)" >> large_scale.out
    sleep 15
  done
  echo "=== [pass $pass COMPLETE] $(date +%H:%M) ===" >> large_scale.out
done
echo "=== LARGE-SCALE finished all passes ===" >> large_scale.out
