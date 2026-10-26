#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
echo "[watcher] waiting for qwen :8192 ..."
for i in $(seq 1 720); do   # up to ~6h at 30s
  code=$(curl -s -m5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
  gym=$(curl -s -m5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/mcp 2>/dev/null)
  if [ "$code" = "200" ] && [ "$gym" != "000" ]; then echo "[watcher] qwen up (http=$code), gym http=$gym — running L2 test"; break; fi
  sleep 30
done
code=$(curl -s -m5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8192/v1/models 2>/dev/null)
if [ "$code" != "200" ]; then echo "[watcher] qwen never came back within window; ABORT"; exit 1; fi
echo "=== L2 multi-strategy live ==="
python3 l2_multi.py UNARMED S1_checklist2tool S2_singlecycle S3_statusonly
echo "=== detect_bench: k04 LLM detectors (static review + connor) ==="
cd /home/ruiheng/aiagent/saas/overserve/detect_bench
ITEMS=k04_l2relay_reconcile_queue python3 run_repro.py llm_code_review dci_checker connor_dynamic 2>&1 | tail -6
echo "=== L2 WATCH DONE ==="
