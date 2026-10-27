#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export ATK_PORT=8200 ATK_CAP=40 ATK_ROLLOUTS=3 ATK_GEN=5 ATK_CANDS=4 ATK_BUDGET=30
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
DEADLINE=$(( $(date +%s) + 10*3600 )); WATCH=toolatk_watch_corner.log
echo "[$(date)] CORNER SUPERVISOR START" >> $WATCH
ensure(){ ss -ltn 2>/dev/null|grep -q ':8200 ' || { ATK_PORT=8200 nohup $PY mcp_attack_server_v3.py >> atk_server_v3.out 2>&1 & sleep 3; }; }
# also guard the teams gym fd exhaustion: restart if seed-database starts 500ing
gymok(){ [ "$(curl -s -m8 -o /dev/null -w '%{http_code}' -X POST http://localhost:8002/api/seed-database -H 'Content-Type: application/json' -d '{"database_id":"hb","name":"h","description":"h","sql_content":"SELECT 1;"}')" = "200" ]; }
a=0
while true; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE" >> $WATCH; break; }
  grep -q "CORNER COMPLETE" toolatk_corner.out 2>/dev/null && { echo "[$(date)] complete" >> $WATCH; break; }
  ensure
  gymok || { echo "[$(date)] teams gym seed 500 -> docker restart" >> $WATCH; docker restart eog-teams >/dev/null 2>&1; sleep 10; }
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null|grep -q '"id"'; do echo "[$(date)] qwen down" >> $WATCH; sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  [ "$(date +%s)" -ge "$DEADLINE" ] && break
  a=$((a+1)); echo "[$(date)] launch attempt $a (evals=$(wc -l < toolatk_lineage_corner.jsonl 2>/dev/null||echo 0))" >> $WATCH
  $PY toolatk_corner.py >> toolatk_corner.out 2>&1
  echo "[$(date)] exit=$? evals=$(wc -l < toolatk_lineage_corner.jsonl 2>/dev/null||echo 0)" >> $WATCH
  [ "$a" -ge 15 ] && break; sleep 10
done
echo "[$(date)] CORNER SUPERVISOR DONE" >> $WATCH
