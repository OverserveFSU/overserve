#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
export EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1
export FRAME_CAP=40 FRAME_REPEATS=3 FRAME_MAX_TOKENS=8192
echo "[$(date)] waiting for qwen @8192 ..." >> frame_watch.log
until curl -s -m 8 http://127.0.0.1:8192/v1/models 2>/dev/null | grep -q '"id"'; do sleep 60; done
echo "[$(date)] qwen UP -> launching frame grid" >> frame_watch.log
python3 frame_iterate.py >> frame_iter.out 2>&1
echo "[$(date)] frame grid COMPLETE" >> frame_watch.log
