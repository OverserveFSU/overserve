#!/bin/bash
# Autonomous overnight supervisor for the malicious-tool DoS actor-critic search.
# Keeps the attack MCP server alive, waits out qwen :8192 flaps, and (re)runs toolatk_search.py
# until it prints SEARCH COMPLETE or the deadline passes. All candidates are writer-agent artifacts
# logged to toolatk_lineage.jsonl; this script only orchestrates (METHOD, not content).
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export ATK_PORT=8199 ATK_CAP=40 ATK_ROLLOUTS=3 ATK_GEN=4 ATK_CANDS=3 ATK_BUDGET=18
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
DEADLINE=$(( $(date +%s) + 9*3600 ))
WATCH=toolatk_watch.log
echo "[$(date)] TOOLATK SUPERVISOR START budget=$ATK_BUDGET gen=$ATK_GEN deadline=+9h" >> $WATCH

ensure_attack_server() {
  if ! ss -ltn 2>/dev/null | grep -q ':8199 '; then
    echo "[$(date)] attack server down -> restarting" >> $WATCH
    nohup $PY mcp_attack_server.py >> atk_server.out 2>&1 &
    sleep 3
  fi
}

attempt=0
while true; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE reached" >> $WATCH; break; }
  grep -q "TOOLATK SEARCH COMPLETE" toolatk_search.out 2>/dev/null && { echo "[$(date)] search complete" >> $WATCH; break; }
  ensure_attack_server
  # wait for qwen
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do
    echo "[$(date)] qwen down -- waiting" >> $WATCH; sleep 60
    [ "$(date +%s)" -ge "$DEADLINE" ] && break
  done
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE reached" >> $WATCH; break; }
  attempt=$((attempt+1))
  echo "[$(date)] qwen up -- launching search (attempt $attempt, evals so far=$(wc -l < toolatk_lineage.jsonl 2>/dev/null || echo 0))" >> $WATCH
  $PY toolatk_search.py >> toolatk_search.out 2>&1
  code=$?
  echo "[$(date)] search exited code=$code (evals=$(wc -l < toolatk_lineage.jsonl 2>/dev/null || echo 0))" >> $WATCH
  [ "$attempt" -ge 12 ] && { echo "[$(date)] max attempts" >> $WATCH; break; }
  sleep 10
done
echo "[$(date)] TOOLATK SUPERVISOR DONE (evals=$(wc -l < toolatk_lineage.jsonl 2>/dev/null || echo 0))" >> $WATCH
