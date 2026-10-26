#!/bin/bash
# qwen-flap-resilient supervisor for the v7 search. Re-launches until BUDGET evals are logged.
cd /home/ruiheng/aiagent/saas/overserve
export EOG_HOME=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export OPENROUTER_API_KEY=$(tr -d '\n' < /home/ruiheng/aiagent/saas/key.txt)
export ATK_BUDGET=28 ATK_CANDS=4 ATK_SCREEN=2 ATK_CONFIRM=5
for attempt in $(seq 1 12); do
  have=$(wc -l < toolatk_lineage_v7.jsonl 2>/dev/null || echo 0)
  echo "[sup $(date +%H:%M)] attempt $attempt, lineage rows=$have"
  [ "$have" -ge "$ATK_BUDGET" ] && { echo "[sup] budget reached"; break; }
  curl -s -m5 http://127.0.0.1:8192/v1/models -o /dev/null || { echo "[sup] qwen down, wait"; sleep 60; continue; }
  python3 toolatk_search_v7.py >> v7_search.out 2>&1
  sleep 5
done
echo "[sup] done rows=$(wc -l < toolatk_lineage_v7.jsonl 2>/dev/null)"
