#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve/detect_bench
echo "[bedrock-watch] polling amazonapi.txt token (every 30s, up to 4h)..."
for i in $(seq 1 480); do
  st=$(cd /home/ruiheng/aiagent/saas/overserve && BEDROCK_KEY_FILE=/home/ruiheng/aiagent/saas/amazonapi.txt BEDROCK_MODEL=us.openai.gpt-5.6-terra timeout 40 python3 bedrock_test.py 2>&1 | grep -oE "HTTP [0-9]+" | head -1)
  if [ "$st" = "HTTP 200" ]; then echo "[bedrock-watch] token LIVE -> running cross-validation"; break; fi
  sleep 30
done
st=$(cd /home/ruiheng/aiagent/saas/overserve && BEDROCK_KEY_FILE=/home/ruiheng/aiagent/saas/amazonapi.txt BEDROCK_MODEL=us.openai.gpt-5.6-terra timeout 40 python3 bedrock_test.py 2>&1 | grep -oE "HTTP [0-9]+" | head -1)
[ "$st" != "HTTP 200" ] && { echo "[bedrock-watch] token never refreshed in window; ABORT"; exit 1; }
python3 bedrock_detect.py
echo "[bedrock-watch] DONE"
