#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 ATK_PORT=8200 REP_N=10
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
WATCH=toolatk_corner_rep.log
ss -ltn 2>/dev/null|grep -q ':8200 ' || { ATK_PORT=8200 nohup $PY mcp_attack_server_v3.py >> atk_server_v3.out 2>&1 & sleep 3; }
gymok(){ [ "$(curl -s -m8 -o /dev/null -w '%{http_code}' -X POST http://localhost:8002/api/seed-database -H 'Content-Type: application/json' -d '{"database_id":"hb","name":"h","description":"h","sql_content":"SELECT 1;"}')" = "200" ]; }
for a in 1 2 3; do
  grep -q "REPLICATION COMPLETE" toolatk_corner_replicate.out 2>/dev/null && break
  gymok || { echo "[$(date)] teams gym 500 -> restart" >> $WATCH; docker restart eog-teams >/dev/null 2>&1; sleep 10; }
  echo "[$(date)] run attempt $a" >> $WATCH
  $PY toolatk_corner_replicate.py >> toolatk_corner_replicate.out 2>&1
  echo "[$(date)] exit=$?" >> $WATCH
  sleep 5
done
echo "[$(date)] REP SUPERVISOR DONE" >> $WATCH
