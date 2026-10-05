#!/usr/bin/env bash
# Detached L1 launch gate: wait for existing local-model clients and the shared
# evaluator queue to drain, then launch four 8-worker arms (32 requests max).
set -euo pipefail

ROOT=/data/libs/aimeth/rt/src-l1-controls
PY=/data/libs/aimeth/envs/dev/bin/python
RUNS=/data/libs/aimeth/rt/runs
TASKS=/data/libs/aimeth/rt/tasks/arc2-pilot40.json
PUBLIC_ARCHIVE=/data/libs/aimeth/rt/tasks/arc2-eval120-public-l1-v1.tar.gz
ARC_DIR=/data/libs/aimeth/data/arc-agi/arc2/data/evaluation
EVALQ=/data/libs/aimeth/rt/evalq
EXPECTED_TASK_SHA=6db032bf2ea0a17c78895261643089b6132122b1082a084ccdf124f233f89e53
LAUNCH_LOG=$RUNS/L1-controls-launch.log
LOCK=$RUNS/L1-controls-launch.lock

cd "$ROOT"
mkdir -p "$RUNS"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "launch lock exists; refusing duplicate launch" >> "$LAUNCH_LOG"
  exit 0
fi
exec >> "$LAUNCH_LOG" 2>&1
echo "$(date -Is) detached launch gate started; paid API providers are disabled"

if [[ -e "$RUNS/L1-local-controls-run-card.json" ]]; then
  echo "FATAL: L1-local-controls run card already exists; refusing duplicate launch"
  exit 19
fi

actual_task_sha=$(sha256sum "$TASKS" | awk '{print $1}')
if [[ "$actual_task_sha" != "$EXPECTED_TASK_SHA" ]]; then
  echo "FATAL: task manifest SHA-256 mismatch"
  exit 20
fi

# This deterministic export supplies only train pairs and test inputs to the
# generation runners. Hidden predictions remain evaluator-private.
archive_sha=$("$PY" -B tools/build_arc2_public_archive.py \
  --source "$ARC_DIR" --tasks "$TASKS" --out "$PUBLIC_ARCHIVE")
echo "public_archive_sha256=$archive_sha"

# Do not overwrite, resume, or silently duplicate an earlier attempt.
for arm in vote orchestrator_worker debate evolution; do
  for suffix in .jsonl .jsonl.events.jsonl .jsonl.lock .log; do
    if [[ -e "$RUNS/L1-$arm$suffix" ]]; then
      echo "FATAL: prior L1-$arm artifact exists; refusing duplicate execution"
      exit 21
    fi
  done
  if [[ -e "$RUNS/receipts/L1-$arm.jsonl" ]]; then
    echo "FATAL: prior L1-$arm receipt file exists; refusing duplicate execution"
    exit 21
  fi
done

active_local_clients() {
  "$PY" - <<'PY'
from pathlib import Path
count = 0
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        args = (entry / 'cmdline').read_bytes().split(b'\0')
    except OSError:
        continue
    if not any(x in (b'tools/rt_run.py', b'tools/rt_devorg.py') for x in args):
        continue
    if any(args[i] == b'--provider' and args[i + 1] == b'local_dsv4'
           for i in range(len(args) - 1)):
        count += 1
print(count)
PY
}

queue_count() {
  "$PY" - "$EVALQ" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
print(sum(len(list((root / d).glob('*.json'))) for d in ('pending', 'running')))
PY
}

last_state=
while :; do
  clients=$(active_local_clients)
  queued=$(queue_count)
  state="$clients:$queued"
  if [[ "$state" != "$last_state" ]]; then
    echo "$(date -Is) waiting_for_existing_local_clients=$clients evalq_pending_or_running=$queued"
    last_state=$state
  fi
  [[ "$clients" == 0 && "$queued" == 0 ]] && break
  sleep 300
done

if ! squeue -h -n aimeth-dsv4 -o '%T' | grep -qx RUNNING; then
  echo "FATAL: local DeepSeek job is not RUNNING; no arm dispatched"
  exit 22
fi
if ! timeout 3 bash -c '</dev/tcp/gpu08/30500' >/dev/null 2>&1; then
  echo "FATAL: local DeepSeek endpoint unreachable; no arm dispatched"
  exit 23
fi
"$PY" - <<'PY'
from pathlib import Path
import stat, sys
path = Path.home() / '.config/aimeth/api.env'
try:
    mode = stat.S_IMODE(path.stat().st_mode)
    lines = path.read_text().splitlines()
except OSError:
    sys.exit('FATAL: private local key file unavailable')
if mode != 0o600 or not any(line.startswith('LOCAL_DSV4_KEY=') and line.split('=', 1)[1].strip()
                             for line in lines):
    sys.exit('FATAL: local key presence/permissions check failed')
print('local key presence/mode check passed; value not emitted')
PY

source_commit=$(cat "$ROOT/SOURCE_COMMIT")
"$PY" - "$RUNS/L1-local-controls-run-card.json" "$archive_sha" "$source_commit" <<'PY'
import json, os, sys, time
from pathlib import Path
path = Path(sys.argv[1])
data = {
  'run_id': 'L1-local-controls-v1', 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
  'source_commit': sys.argv[3],
  'task_manifest_sha256': '6db032bf2ea0a17c78895261643089b6132122b1082a084ccdf124f233f89e53',
  'public_archive_sha256': sys.argv[2],
  'model': {'provider': 'local_dsv4', 'id': 'deepseek-v4-flash-0731',
            'endpoint': 'http://gpu08:30500/v1/chat/completions',
            'reasoning_effort': 'low', 'thinking': True, 'paid_api_calls': False},
  'budget_per_task': {'calls': 8, 'completion_reasoning_tokens': 262144,
                      'max_tokens_per_call': 32768, 'replicates': 1, 'seed': 1000},
  'arms': ['vote', 'orchestrator_worker', 'debate', 'evolution'],
  'max_concurrent_local_requests': 32, 'workers_per_arm': 8,
  'evalq': '/data/libs/aimeth/rt/evalq'}
tmp = path.with_suffix(path.suffix + '.tmp')
with tmp.open('x') as out:
    json.dump(data, out, indent=2, sort_keys=True)
    out.write('\n'); out.flush(); os.fsync(out.fileno())
os.replace(tmp, path)
PY

for arm in vote orchestrator_worker debate evolution; do
  "$PY" -B tools/rt_run.py arc "$arm" \
    --tasks "$TASKS" --arc-dir "$ARC_DIR" --arc-archive "$PUBLIC_ARCHIVE" \
    --eval-transport local --evalq "$EVALQ" \
    --provider local_dsv4 --model deepseek-v4-flash-0731 \
    --budget-calls 8 --budget-tokens 262144 --model-max-tokens 32768 \
    --seed 1000 --workers 8 --llm-start 8 --llm-cap 8 \
    --state-log "$RUNS/L1-$arm.jsonl.events.jsonl" \
    --receipts "$RUNS/receipts/L1-$arm.jsonl" --out "$RUNS/L1-$arm.jsonl" \
    >> "$RUNS/L1-$arm.log" 2>&1 < /dev/null &
  echo "$(date -Is) launched arm=$arm pid=$!"
done
echo "$(date -Is) four controllers started detached"
