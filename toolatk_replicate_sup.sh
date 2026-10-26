#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 ATK_PORT=8200 REP_N=20
PY=/home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python
ss -ltn 2>/dev/null | grep -q ':8200 ' || { ATK_PORT=8200 nohup $PY mcp_attack_server_v3.py >> atk_server_v3.out 2>&1 & sleep 3; }
$PY toolatk_replicate.py >> toolatk_replicate.out 2>&1
echo "[$(date)] REPLICATE DONE" >> toolatk_replicate.out
