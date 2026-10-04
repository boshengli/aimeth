#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RUN_DIR="runs/p2-controls-v1"
LOCK_DIR="$RUN_DIR/launcher.lockdir"
mkdir -p "$RUN_DIR/receipts"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY is unavailable in the launcher environment" >&2
  exit 2
fi
if [[ -e "$LOCK_DIR" ]]; then
  echo "phase-B launcher lock exists; inspect its PID before resuming" >&2
  exit 3
fi
mkdir "$LOCK_DIR"
printf '%s\n' "$$" > "$LOCK_DIR/pid"
cleanup() { rm -rf "$LOCK_DIR"; }
trap cleanup EXIT INT TERM

ARMS=(independent self_repair single_long vote orchestrator_worker debate evolution)
COMMON=(--provider deepseek --model deepseek-flash --model-max-tokens 131072
        --budget-calls 8 --budget-tokens 262144 --workers 4 --llm-start 2 --llm-cap 8
        --execute-paid --seed 1000 --k 4 --m 3 --population-size 8
        --eval-transport ssh --remote-target libs@172.16.30.19
        --evalq /data/libs/aimeth/rt/runs/p2-controls-v1/evalq)

for arm in "${ARMS[@]}"; do
  python3 tools/rt_run.py arc "$arm" \
    --tasks plans/arc2-pilot40-v1.json \
    --arc-archive /Volumes/Expand/0023-AIMeth_scratch/datasets/arc-agi-data.tgz \
    --arc-dir /data/libs/aimeth/data/arc-agi/arc2/data/evaluation \
    --reasoning-effort low --out "$RUN_DIR/arc2-${arm}.jsonl" "${COMMON[@]}"
  python3 tools/rt_run.py bio "$arm" \
    --bio-prompt-manifest "$RUN_DIR/callus-public-prompts-v1.json" \
    --reasoning-effort medium --out "$RUN_DIR/callus-${arm}.jsonl" "${COMMON[@]}"
done

python3 tools/verify_p2_controls_run.py --run-dir "$RUN_DIR"
