#!/usr/bin/env bash
# Offline grading/audit only. Never starts or resumes a model request.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RUN="runs/p2-controls-v1"
REMOTE="/data/libs/aimeth/rt/runs/p2-controls-v1"
TARGET="libs@172.16.30.19"
ARMS=(independent self_repair single_long vote orchestrator_worker debate evolution)

LOCK_PID="$RUN/launcher.lockdir/pid"
if [[ -f "$LOCK_PID" ]] && kill -0 "$(cat "$LOCK_PID")" 2>/dev/null; then
  echo "controller still appears live; wait for it to stop before grading" >&2
  exit 3
fi

# This is local bookkeeping only. Started-but-unsettled tasks become unknown,
# and never-started tasks become not_started; neither category is resubmitted.
python3 -B tools/finalize_p2_incomplete.py --run-dir "$RUN" \
  --arc-manifest plans/arc2-pilot40-v1.json \
  --bio-manifest "$RUN/callus-public-prompts-v1.json"

ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ForwardAgent=no "$TARGET" \
  "mkdir -p '$REMOTE/incoming' '$REMOTE/graded'"
for arm in "${ARMS[@]}"; do
  scp -q "$RUN/arc2-${arm}.jsonl" "$RUN/callus-${arm}.jsonl" "$TARGET:$REMOTE/incoming/"
done

ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ForwardAgent=no "$TARGET" 'bash -s' <<'REMOTE_GRADE'
set -euo pipefail
BASE=/data/libs/aimeth/rt/runs/p2-controls-v1
SRC="$BASE/postrun-source"
PY=/data/libs/aimeth/envs/dev/bin/python
ARMS=(independent self_repair single_long vote orchestrator_worker debate evolution)
for arm in "${ARMS[@]}"; do
  "$PY" -B "$SRC/tools/rt_grade.py" \
    "$BASE/incoming/arc2-${arm}.jsonl" "$BASE/evalq" \
    --arc-dir /data/libs/aimeth/data/arc-agi/arc2/data/evaluation \
    > "$BASE/graded/arc2-${arm}.graded.jsonl"
  "$PY" -B "$SRC/tools/rt_grade.py" \
    "$BASE/incoming/callus-${arm}.jsonl" "$BASE/evalq" \
    --bench /data/libs/aimeth/p2-bio/v1 \
    > "$BASE/graded/callus-${arm}.graded.jsonl"
done
REMOTE_GRADE

mkdir -p "$RUN/graded"
for arm in "${ARMS[@]}"; do
  scp -q "$TARGET:$REMOTE/graded/arc2-${arm}.graded.jsonl" "$RUN/graded/"
  scp -q "$TARGET:$REMOTE/graded/callus-${arm}.graded.jsonl" "$RUN/graded/"
done

python3 -B tools/verify_p2_controls_run.py --run-dir "$RUN" \
  --arc-manifest plans/arc2-pilot40-v1.json \
  --bio-manifest "$RUN/callus-public-prompts-v1.json"
python3 -B tools/analyze_p2_controls.py --run-dir "$RUN" \
  --arc-manifest plans/arc2-pilot40-v1.json \
  --bio-manifest "$RUN/callus-public-prompts-v1.json" \
  --bootstrap-replicates 10000 --seed 1000
