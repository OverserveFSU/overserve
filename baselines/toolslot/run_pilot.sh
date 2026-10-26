#!/usr/bin/env bash
# Orchestrates the full tool-slot pilot after the LoopTrap profiler finishes qwen's probes.
# qwen pilot (VM victim) then sonnet pilot (Bedrock). Appends to results/pilot.jsonl.
set -u
cd /home/ruiheng/aiagent/saas/overserve/baselines/toolslot
LOG=logs

# 1. wait for qwen's 4 probes (P2 line) then stop the profiler (sonnet profiling deferred to save time).
until grep -q "P2_incremental" "$LOG/profiler.log" 2>/dev/null; do sleep 10; done
pkill -f "profiler.py" 2>/dev/null; sleep 2

# 2. pick qwen's best strategy (max amp among fid=True probes)
QBEST=$(python3 - <<'PY'
import re
best=None
for l in open("logs/profiler.log"):
    m=re.search(r"\[qwen\] (\S+) \((\w+)\): calls=(\d+) amp=([\d.]+) fid=(\w+)", l)
    if m and m.group(5)=="True":
        a=float(m.group(4))
        if best is None or a>best[1]: best=(m.group(1),a)
print(best[0] if best else "P4_authority_override")
PY
)
echo "qwen LoopTrap strategy = $QBEST"
echo "$QBEST" > specs/qwen_lt_strategy.txt

rm -f results/pilot.jsonl

# 3. qwen full pilot (both benches, 3 methods, quiet/churn, 3 reps, + clean)
echo "=== QWEN PILOT ($(date +%H:%M)) ==="
python3 harness.py --victims qwen --benches mcpmark,eog --mm-tasks file_property/txt_merging \
  --methods ours,a2m,looptrap --conditions quiet,churn --reps 3 --clean \
  --lt-strategy "$QBEST" --out results/pilot.jsonl >> "$LOG/pilot_qwen.log" 2>&1
echo "QWEN_PILOT_DONE ($(date +%H:%M))"

# 4. sonnet full pilot (Bedrock). Reuse qwen-selected LoopTrap strategy (per-victim sonnet profiling
#    deferred to bound Bedrock cost/time; documented).
echo "=== SONNET PILOT ($(date +%H:%M)) ==="
python3 harness.py --victims sonnet --benches mcpmark,eog --mm-tasks file_property/txt_merging \
  --methods ours,a2m,looptrap --conditions quiet,churn --reps 3 --clean \
  --lt-strategy "$QBEST" --out results/pilot.jsonl >> "$LOG/pilot_sonnet.log" 2>&1
echo "SONNET_PILOT_DONE ($(date +%H:%M))"
echo "ALL_PILOT_DONE"
