#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export CROSS_ATK_PORT=8201 CROSS_N=5 ATK_CAP=40
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
WATCH=toolatk_cross.log
ss -ltn 2>/dev/null|grep -q ':8201 ' || { ATK_PORT=8201 ATK_SPEC=$(pwd)/toolatk_cross_spec.json nohup $PY mcp_attack_server_v3.py >> atk_server_cross.out 2>&1 & sleep 3; }
for M in "meta-llama/llama-3.3-70b-instruct" "google/gemini-2.5-flash"; do
  echo "[$(date)] cross victim=$M" >> $WATCH
  CROSS_VICTIM_MODEL="$M" $PY toolatk_cross.py >> toolatk_cross.out 2>&1
  safe=$(echo "$M"|tr '/' '_'); cp toolatk_cross_results.json toolatk_cross_results_${safe}.json 2>/dev/null
  echo "[$(date)] done $M exit=$?" >> $WATCH
done
echo "[$(date)] CROSS ALL DONE" >> $WATCH
