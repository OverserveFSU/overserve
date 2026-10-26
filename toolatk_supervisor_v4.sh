#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export ATK_PORT=8200 ATK_CAP=40 ATK_ROLLOUTS=3 ATK_GEN=4 ATK_CANDS=3 ATK_BUDGET=18
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
DEADLINE=$(( $(date +%s) + 9*3600 )); WATCH=toolatk_watch_v4.log
echo "[$(date)] TOOLATK v4 SUPERVISOR START (tool+prompt stealth) budget=$ATK_BUDGET" >> $WATCH
ensure() { ss -ltn 2>/dev/null | grep -q ':8200 ' || { echo "[$(date)] v3 server down->restart" >> $WATCH; ATK_PORT=8200 nohup $PY mcp_attack_server_v3.py >> atk_server_v3.out 2>&1 & sleep 3; }; }
a=0
while true; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE" >> $WATCH; break; }
  grep -q "TOOLATK v4 SEARCH COMPLETE" toolatk_search_v4.out 2>/dev/null && { echo "[$(date)] complete" >> $WATCH; break; }
  ensure
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do echo "[$(date)] qwen down" >> $WATCH; sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  [ "$(date +%s)" -ge "$DEADLINE" ] && break
  a=$((a+1)); echo "[$(date)] launch (attempt $a, evals=$(wc -l < toolatk_lineage_v4.jsonl 2>/dev/null||echo 0))" >> $WATCH
  $PY toolatk_search_v4.py >> toolatk_search_v4.out 2>&1
  echo "[$(date)] exit=$? evals=$(wc -l < toolatk_lineage_v4.jsonl 2>/dev/null||echo 0)" >> $WATCH
  [ "$a" -ge 12 ] && break; sleep 10
done
echo "[$(date)] TOOLATK v4 SUPERVISOR DONE" >> $WATCH
