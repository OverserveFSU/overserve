#!/bin/bash
# Overnight: after measure_motifs finishes -> rebuild writers (23 tools) -> fresh full-tool ECLIPSE run.
cd /home/ruiheng/aiagent/saas/overserve
export OPENROUTER_API_KEY=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
export OVERSERVE_GENERATOR_MODEL=z-ai/glm-5.3-flash OVERSERVE_FUSION_MODEL=z-ai/glm-5.3-flash
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 ECLIPSE_LLM_MAXTOK=4500
export ECLIPSE_ROUNDS=10 ECLIPSE_MAX_ATTEMPTS=40
LOG=overnight_eclipse.log
echo "[$(date)] START; waiting for measure_motifs to finish" >> $LOG
until ! pgrep -f "python3 measure_motifs.py" >/dev/null; do sleep 15; done
NT=$(python3 -c "import json;print(len(json.load(open('measured_motifs.json'))))" 2>/dev/null || echo 0)
echo "[$(date)] measure done: $NT tools -> rebuild writers" >> $LOG
python3 build_writers.py >> $LOG 2>&1
NW=$(python3 -c "import json;print(len(json.load(open('measured_writers.json'))))" 2>/dev/null || echo 0)
echo "[$(date)] measured_writers: $NW writers" >> $LOG
# archive the 14-tool eclipse result, start fresh for the full-tool run
[ -f eclipse_loop.jsonl ] && cp eclipse_loop.jsonl eclipse_loop_14tools.jsonl
rm -f eclipse_loop.jsonl eclipse_loop.out
DEADLINE=$(( $(date +%s) + 8*3600 ))
echo "[$(date)] fresh full-tool ECLIPSE run (rounds=$ECLIPSE_ROUNDS)" >> $LOG
while true; do
  done=$(wc -l < eclipse_loop.jsonl 2>/dev/null || echo 0)
  [ "$done" -ge "$ECLIPSE_ROUNDS" ] && { echo "[$(date)] ALL $ECLIPSE_ROUNDS done" >> $LOG; break; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[$(date)] DEADLINE ($done)" >> $LOG; break; }
  until curl -s -m8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; [ "$(date +%s)" -ge "$DEADLINE" ] && break; done
  echo "[$(date)] qwen up, $done/$ECLIPSE_ROUNDS -> run eclipse" >> $LOG
  python3 eclipse_loop.py >> eclipse_loop.out 2>&1
  echo "[$(date)] pass exit=$? ($(wc -l < eclipse_loop.jsonl 2>/dev/null||echo 0)/$ECLIPSE_ROUNDS)" >> $LOG
  sleep 5
done
echo "[$(date)] OVERNIGHT DONE" >> $LOG
