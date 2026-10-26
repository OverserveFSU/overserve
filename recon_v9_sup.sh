#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_HOME=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export OPENROUTER_API_KEY=$(tr -d '\n' < /home/ruiheng/aiagent/saas/key.txt) ATK_CAP=40 ATK_BUDGET=8
for attempt in $(seq 1 8); do
  rows=$(wc -l < toolatk_lineage_v9.jsonl 2>/dev/null || echo 0)
  echo "[sup $(date +%H:%M)] attempt $attempt rows=$rows"
  [ "$rows" -ge "$ATK_BUDGET" ] && { echo "[sup] budget reached"; break; }
  curl -s -m5 http://127.0.0.1:8192/v1/models -o /dev/null || { sleep 60; continue; }
  python3 recon_to_search.py >> v9.out 2>&1
  sleep 5
done
echo "[sup] done rows=$(wc -l < toolatk_lineage_v9.jsonl 2>/dev/null)"
