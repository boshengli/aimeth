#!/bin/bash
#SBATCH --job-name=aimeth-local-smoke
#SBATCH --partition=gpu
#SBATCH --account=libs
#SBATCH --reservation=Res_libs
#SBATCH --nodelist=gpu08
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256G
#SBATCH --gres=gpu:nvidia_h20_96gb:8
#SBATCH --time=00:30:00
#SBATCH --output=/data/libs/aimeth/gpu08-local-smoke-20260930-v3/deepseek/slurm-%j.out
#SBATCH --error=/data/libs/aimeth/gpu08-local-smoke-20260930-v3/deepseek/slurm-%j.err
set -euo pipefail
umask 077
: "${AIMETH_MODEL_PROFILE:?set deepseek or glm}"
: "${AIMETH_MODEL_DIR:?set a verified local model directory}"
: "${AIMETH_IMAGE:?set a read-only Singularity image}"
: "${AIMETH_RUN_ROOT:?set the private per-run output directory}"
: "${AIMETH_SERVE_NAME:?set the served model name}"
mkdir -p "$AIMETH_RUN_ROOT"
AIMETH_TRITON_CACHE="/tmp/aimeth-triton-${SLURM_JOB_ID}"
mkdir -m 700 -p "$AIMETH_TRITON_CACHE"
printf "%s\n" "$AIMETH_TRITON_CACHE" > "$AIMETH_RUN_ROOT/triton-cache-path.txt"
module load singularity/4.3.3
hostname > "$AIMETH_RUN_ROOT/hostname.txt"
date -u +%FT%TZ > "$AIMETH_RUN_ROOT/start-utc.txt"
scontrol show job "$SLURM_JOB_ID" > "$AIMETH_RUN_ROOT/slurm-job.txt"
nvidia-smi -q > "$AIMETH_RUN_ROOT/nvidia-smi.txt"
singularity --version > "$AIMETH_RUN_ROOT/singularity-version.txt"
sha256sum "$AIMETH_IMAGE" > "$AIMETH_RUN_ROOT/container.sha256"

case "$AIMETH_MODEL_PROFILE" in
  deepseek)
    server=(python3 -m sglang.launch_server --model-path "$AIMETH_MODEL_DIR" --served-model-name "$AIMETH_SERVE_NAME" --tp-size 8 --context-length 32768 --max-running-requests 1 --max-queued-requests 1 --chunked-prefill-size 4096 --mem-fraction-static 0.80 --attention-backend dsv4 --moe-runner-backend marlin --kv-cache-dtype fp8_e4m3 --reasoning-parser deepseek-v4 --host 127.0.0.1 --port 18000 --disable-cuda-graph)
    ;;
  glm)
    server=(vllm serve "$AIMETH_MODEL_DIR" --served-model-name "$AIMETH_SERVE_NAME" --tensor-parallel-size 8 --max-model-len 8192 --max-num-seqs 1 --max-num-batched-tokens 512 --gpu-memory-utilization 0.80 --kv-cache-dtype bfloat16 --reasoning-parser glm47 --host 127.0.0.1 --port 18000 --enforce-eager)
    ;;
  *) echo "unknown model profile" >&2; exit 2 ;;
esac
setsid singularity exec --env SGLANG_OPT_FP8_WO_A_GEMM=1 --env "TRITON_CACHE_DIR=$AIMETH_TRITON_CACHE" --nv --bind "$AIMETH_MODEL_DIR:$AIMETH_MODEL_DIR:ro" --bind "$AIMETH_TRITON_CACHE:$AIMETH_TRITON_CACHE:rw" "$AIMETH_IMAGE" "${server[@]}" > "$AIMETH_RUN_ROOT/server.log" 2>&1 &
server_pid=$!
cleanup() {
  kill -TERM -- "-$server_pid" 2>/dev/null || true
  for _ in $(seq 1 60); do
    kill -0 -- "-$server_pid" 2>/dev/null || break
    sleep 1
  done
  kill -KILL -- "-$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  date -u +%FT%TZ > "$AIMETH_RUN_ROOT/stop-utc.txt"
}
trap cleanup EXIT TERM INT
export AIMETH_API_BASE=http://127.0.0.1:18000/v1
python3 "$AIMETH_RUN_ROOT/gpu08_model_smoke_probe_v3.py" | tee "$AIMETH_RUN_ROOT/probe.stdout.json"
