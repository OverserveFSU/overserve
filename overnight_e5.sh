#!/bin/bash
# Two-stage autonomous E5: Stage-I full grid (confirm negative) -> if reentry stays ~0, Stage-II
# with verification-pressure factor. Flap-tolerant, resumable, all metrics logged.
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 E5_CAP=40
LOG=overnight_e5.log

run_grid () {  # $1=results_file $2=total $3..=env
  local RF=$1 TOTAL=$2; shift 2
  local DEADLINE=$(( $(date +%s) + 10*3600 ))
  while true; do
    local done=$(wc -l < "$RF" 2>/dev/null || echo 0)
    [ "$done" -ge "$TOTAL" ] && { echo "[$(date)] $RF ALL $TOTAL done" >> $LOG; return 0; }
    [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] $RF DEADLINE ($done/$TOTAL)" >> $LOG; return 1; }
    until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
    echo "[$(date)] $RF $done/$TOTAL -> run" >> $LOG
    env "$@" LOG_TO="$RF" python3 e5_run.py >> e5_run.out 2>&1
    sleep 5
  done
}

# --- Stage I: 3 carriers x 4 cond x 5 seed = 60 ---
echo "[$(date)] STAGE I START" >> $LOG
rm -f e5_results.jsonl e5_run.out
E5_CARRIERS=softdelete,reaction,tab E5_SEEDS=5 E5_STAGE=1 run_grid e5_results.jsonl 60
cp e5_results.jsonl e5_stage1.jsonl
RE=$(python3 -c "import json;print(sum(json.loads(l).get('R_reentry',0) for l in open('e5_results.jsonl')))" 2>/dev/null||echo 0)
echo "[$(date)] STAGE I done, total reentry=$RE" >> $LOG

# --- Stage II: 2 toggle carriers x 8 cond x 3 seed = 48 (verification pressure factor) ---
echo "[$(date)] STAGE II START (verification pressure)" >> $LOG
rm -f e5_results.jsonl
E5_CARRIERS=softdelete,reaction E5_SEEDS=3 E5_STAGE=2 run_grid e5_results.jsonl 48
cp e5_results.jsonl e5_stage2.jsonl
RE2=$(python3 -c "import json;print(sum(json.loads(l).get('R_reentry',0) for l in open('e5_results.jsonl')))" 2>/dev/null||echo 0)
echo "[$(date)] STAGE II done, total reentry=$RE2" >> $LOG
echo "[$(date)] OVERNIGHT E5 COMPLETE (stage1 reentry=$RE, stage2 reentry=$RE2)" >> $LOG
