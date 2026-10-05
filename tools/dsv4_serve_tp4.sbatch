#!/bin/bash -l
#SBATCH -J aimeth-dsv4
#SBATCH -p gpu
#SBATCH -A libs
#SBATCH --reservation=Res_libs
#SBATCH -w gpu08
#SBATCH --gres=gpu:nvidia_h20_96gb:4
#SBATCH -c 32
#SBATCH --mem=400G
#SBATCH -t 2-23:00:00
#SBATCH -o /data/libs/dsv4-runtime/logs/%x-%j.out
# Local DeepSeek-V4-Flash-0731 (cluster shared read-only assets, /home/approved/dsv4) for AIMeth workloads.
# Adapted from /home/approved/dsv4/scripts/05_serve_profile.sbatch: TP4 on 4 GPUs of gpu08, API-key mode on port ${PORT}.
set -euo pipefail
SIF=/home/approved/dsv4/containers/sglang-dsv4-hopper.sif
MODEL_DIR=/home/approved/dsv4/models/DeepSeek-V4-Flash-0731
SCRIPTS_DIR=/home/approved/dsv4/scripts
PATCH_DIR=/home/approved/dsv4/scripts/sglang_patch
RUNTIME_ROOT=/data/libs/dsv4-runtime
PORT="${PORT:-30500}"
CACHE_DIR=$RUNTIME_ROOT/cache; LOG_DIR=$RUNTIME_ROOT/logs; RUN_DIR=$RUNTIME_ROOT/run; SCRATCH_DIR=$RUNTIME_ROOT/scratch
hostname > "$RUNTIME_ROOT/backend_node.$PORT"
export SINGULARITYENV_HOME=/root SINGULARITYENV_FLASHINFER_WORKSPACE_BASE=/cache
export SINGULARITYENV_HF_HOME=/cache/huggingface SINGULARITYENV_TRANSFORMERS_OFFLINE=1 SINGULARITYENV_HF_HUB_OFFLINE=1
export SINGULARITYENV_XDG_CACHE_HOME=/cache/xdg SINGULARITYENV_FLASHINFER_WORKSPACE_DIR=/cache/flashinfer
export SINGULARITYENV_TORCHINDUCTOR_CACHE_DIR=/cache/torchinductor SINGULARITYENV_PYTHONPATH=/scripts SINGULARITYENV_DSV4_CACHE=/cache
module load singularity/4.3.3
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
singularity exec --nv --cleanenv --no-home \
  --bind "$MODEL_DIR:/models/dsv4:ro" --bind "$SCRIPTS_DIR:/scripts:ro" \
  --bind "$PATCH_DIR/protocol.py:/sgl-workspace/sglang/python/sglang/srt/entrypoints/openai/protocol.py:ro" \
  --bind "$CACHE_DIR:/cache:rw" --bind "$CACHE_DIR:/root:rw" --bind "$LOG_DIR:/logs:rw" \
  --bind "$RUN_DIR:/run/dsv4:rw" --bind "$SCRATCH_DIR:/scratch/dsv4:rw" \
  "$SIF" sglang serve --model-path /models/dsv4 --trust-remote-code --tp 4 \
  --context-length 262144 --moe-runner-backend marlin --swa-full-tokens-ratio 0.1 --chunked-prefill-size 4096 \
  --mem-fraction-static 0.85 --weight-loader-prefetch-checkpoints --weight-loader-prefetch-num-threads 8 \
  --max-running-requests 96 --reasoning-parser deepseek-v4 --served-model-name deepseek-v4-flash-0731 \
  --host 0.0.0.0 --port "$PORT" --api-key "$(cat $RUNTIME_ROOT/secrets/api_key)"
