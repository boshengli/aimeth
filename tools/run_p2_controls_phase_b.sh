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
python3 - "$RUN_DIR/callus-public-prompts-v1.json" plans/callus-public-prompt-hashes-v1.json <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest_path, frozen_path = map(Path, sys.argv[1:])
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
frozen = json.loads(frozen_path.read_text())
observed = [(row.get("task_id"), row.get("prompt_sha256")) for row in manifest]
expected = [(row["task_id"], row["prompt_sha256"]) for row in frozen["tasks"]]
if hashlib.sha256(manifest_bytes).hexdigest() != frozen["prompt_manifest_sha256"]:
    raise SystemExit("callus public prompt manifest SHA-256 does not match the frozen run card")
if len(manifest) != 36 or observed != expected:
    raise SystemExit("callus task IDs or prompt hashes do not match the frozen run card")
print("callus prompt manifest hashes verified")
PY
mkdir "$LOCK_DIR"
printf '%s\n' "$$" > "$LOCK_DIR/pid"
cleanup() { rm -rf "$LOCK_DIR"; }
trap cleanup EXIT INT TERM

ARMS=(independent self_repair single_long vote orchestrator_worker debate evolution)
COMMON=(--provider deepseek --model deepseek-flash --model-max-tokens 262144
        --budget-calls 8 --budget-tokens 262144 --workers 4 --llm-start 2 --llm-cap 8
        --execute-paid --finalize-fenced --seed 1000 --k 4 --m 3 --population-size 8
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
