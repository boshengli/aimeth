#!/bin/bash
#SBATCH --job-name=aimeth-slcw-10k-v6
#SBATCH --partition=gpu
#SBATCH --account=libs
#SBATCH --reservation=Res_libs
#SBATCH --nodelist=gpu08
#SBATCH --gres=gpu:nvidia_h20_96gb:8
#SBATCH --exclusive
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --time=160:30:00
#SBATCH --signal=B:TERM@180

set -euo pipefail
umask 077
: "${AIMETH_CODE_DIR:?}" "${AIMETH_MODEL_DIR:?}" "${AIMETH_IMAGE:?}"
: "${AIMETH_OUTPUT_ROOT:?}" "${AIMETH_SOURCE_COMMIT:?}"
AIMETH_LOCAL_ROOT="${AIMETH_LOCAL_ROOT:-/tmp/aimeth-slcw10k-${SLURM_JOB_ID}}"
AIMETH_TRITON_CACHE="/tmp/aimeth-triton-${SLURM_JOB_ID}"
mkdir -m 700 -p "$AIMETH_LOCAL_ROOT" "$AIMETH_TRITON_CACHE" "$AIMETH_OUTPUT_ROOT"
cd "$AIMETH_CODE_DIR"
module load singularity/4.3.3
server_pid=''
checkpoint_pid=''
cleanup() {
  if [ -n "$checkpoint_pid" ]; then
    kill -TERM "$checkpoint_pid" 2>/dev/null || true
    wait "$checkpoint_pid" 2>/dev/null || true
  fi
  python3 "$AIMETH_CODE_DIR/cluster/checkpoint_population.py" --source-root "$AIMETH_LOCAL_ROOT/population" --output-root "$AIMETH_OUTPUT_ROOT/recovery" >> "$AIMETH_OUTPUT_ROOT/checkpoint-watcher.log" 2>&1 || true
  if [ -n "$server_pid" ]; then
    kill -TERM -- "-$server_pid" 2>/dev/null || kill -TERM "$server_pid" 2>/dev/null || true
    for _ in $(seq 1 60); do
      kill -0 -- "-$server_pid" 2>/dev/null || break
      sleep 1
    done
    kill -KILL -- "-$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 143' TERM INT

# Keep a rolling node-failure recovery copy without putting SQLite writes on shared storage.
python3 "$AIMETH_CODE_DIR/cluster/checkpoint_population.py" --source-root "$AIMETH_LOCAL_ROOT/population" --output-root "$AIMETH_OUTPUT_ROOT/recovery" --watch --interval-seconds 300 > "$AIMETH_OUTPUT_ROOT/checkpoint-watcher.log" 2>&1 &
checkpoint_pid=$!
{
  date -Iseconds
  hostname -f
  printf 'job=%s source=%s population=%s\n' "$SLURM_JOB_ID" "$AIMETH_SOURCE_COMMIT" "slcw10k-20261001-gpu08-v6"
  nvidia-smi --query-gpu=index,name,uuid,memory.total --format=csv
  sha256sum "$AIMETH_IMAGE" "$AIMETH_MODEL_DIR/config.json" "$AIMETH_CODE_DIR/examples/slcw-direct-10k-gpu08-v6.json"
  git -C "$AIMETH_CODE_DIR" rev-parse HEAD 2>/dev/null || true
} > "$AIMETH_OUTPUT_ROOT/launch-identities.txt"

python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(('127.0.0.1',31008))
PY

binds=(--bind "$AIMETH_CODE_DIR:/opt/aimeth:ro"
       --bind "$AIMETH_MODEL_DIR:/models/served:ro"
       --bind "$AIMETH_LOCAL_ROOT:/run/aimeth"
       --bind "$AIMETH_TRITON_CACHE:$AIMETH_TRITON_CACHE"
       --bind "$AIMETH_OUTPUT_ROOT:/output")
envopts=(--env PYTHONPATH=/opt/aimeth,HF_HOME=/run/aimeth/hf-cache,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,XDG_CACHE_HOME=/run/aimeth/cache
         --env SGLANG_OPT_FP8_WO_A_GEMM=1
         --env "TRITON_CACHE_DIR=$AIMETH_TRITON_CACHE")

# Launch the exact locally smoke-tested H20 profile, with a fresh cache for this job.
setsid singularity exec --nv --cleanenv "${binds[@]}" "${envopts[@]}" "$AIMETH_IMAGE" \
  python3 -m sglang.launch_server --model-path /models/served \
  --served-model-name deepseek-v4-flash-0731 --host 127.0.0.1 --port 31008 \
  --tp-size 8 --context-length 32768 --max-running-requests 16 --max-queued-requests 32 \
  --chunked-prefill-size 4096 --mem-fraction-static 0.80 --attention-backend dsv4 \
  --moe-runner-backend marlin --kv-cache-dtype fp8_e4m3 --reasoning-parser deepseek-v4 \
  --disable-cuda-graph > "$AIMETH_OUTPUT_ROOT/server.log" 2>&1 &
server_pid=$!
export AIMETH_SERVER_PID="$server_pid"

python3 - <<'PY'
import json,os,time
from pathlib import Path
from urllib import request
opener=request.build_opener(request.ProxyHandler({}))
deadline=time.monotonic()+1800
while time.monotonic()<deadline:
    try:
        os.kill(int(os.environ['AIMETH_SERVER_PID']),0)
    except ProcessLookupError:
        raise SystemExit('Owned model process exited; inspect preserved server.log')
    try:
        with opener.open('http://127.0.0.1:31008/health',timeout=5) as r:
            if r.status!=200: raise ValueError('not ready')
        with opener.open('http://127.0.0.1:31008/v1/models',timeout=5) as r:
            inventory=json.load(r)
        if 'deepseek-v4-flash-0731' not in [m['id'] for m in inventory['data']]:
            raise SystemExit('Served model ID differs from frozen config')
        Path(os.environ['AIMETH_OUTPUT_ROOT'],'served-models.json').write_text(json.dumps(inventory,indent=2)+'\n')
        break
    except (OSError,ValueError):
        time.sleep(5)
else:
    raise SystemExit('30 minute model-loading limit reached; no population requests sent')
PY

# The full 10K population is the experimental unit; there is no single-agent gate.
singularity exec --cleanenv "${binds[@]}" "${envopts[@]}" "$AIMETH_IMAGE" \
  python3 -m aimeth_swarm.run --config /opt/aimeth/examples/slcw-direct-10k-gpu08-v6.json \
  --local-root /run/aimeth/population --output-root /output/population \
  --tokenizer-dir /models/served --allow-model-calls > "$AIMETH_OUTPUT_ROOT/population.log" 2>&1
