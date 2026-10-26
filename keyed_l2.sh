#!/bin/bash
cd /home/ruiheng/aiagent/saas/overserve
echo "=== L2 UNARMED (8202): benign no-ref prompt should self-terminate ==="
KEYED_PORT=8202 N=2 python3 keyed_multi.py followck_noref
cp keyed_multi_results.json keyed_l2_unarmed.json
echo "=== L2 ARMED (8203): SAME prompt, env-planted trigger should loop ==="
KEYED_PORT=8203 N=2 python3 keyed_multi.py followck_noref
cp keyed_multi_results.json keyed_l2_armed.json
echo "=== L2 DONE ==="
echo "UNARMED:"; cat keyed_l2_unarmed.json
echo "ARMED:";   cat keyed_l2_armed.json
