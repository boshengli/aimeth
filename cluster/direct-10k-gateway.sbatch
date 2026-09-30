#!/bin/bash
#SBATCH --job-name=aimeth-10k-gateway
#SBATCH --partition=fatPartition
#SBATCH --account=libs
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:10:00
#SBATCH --signal=B:TERM@180
set -euo pipefail
umask 077
: "${AIMETH_CODE_DIR:?}" "${AIMETH_CONFIG:?}" "${AIMETH_OUTPUT_ROOT:?}"
: "${AIMETH_IMAGE:?}" "${AIMETH_MODEL_DIR:?}" "${AIMETH_API_KEY:?}" "${AIMETH_SOURCE_COMMIT:?}"
AIMETH_LOCAL_ROOT="${AIMETH_LOCAL_ROOT:-/tmp/aimeth-10k-gateway-${SLURM_JOB_ID}}"
mkdir -p "$AIMETH_LOCAL_ROOT" "$AIMETH_OUTPUT_ROOT"
module load singularity/4.3.3
export SINGULARITYENV_AIMETH_API_KEY="$AIMETH_API_KEY"
{
  date -Iseconds
  hostname -f
  printf 'job=%s source=%s\n' "$SLURM_JOB_ID" "$AIMETH_SOURCE_COMMIT"
  sha256sum "$AIMETH_CONFIG" "$AIMETH_MODEL_DIR/tokenizer_config.json"
} > "$AIMETH_OUTPUT_ROOT/launch-identities.txt"
# No GPU is requested by the client job. Provider inference placement is unattested.
exec singularity exec --cleanenv \
  --bind "$AIMETH_CODE_DIR:/opt/aimeth:ro" --bind "$AIMETH_MODEL_DIR:/models/tokenizer:ro" \
  --bind "$AIMETH_CONFIG:/run-config.json:ro" --bind "$AIMETH_LOCAL_ROOT:/run/aimeth" \
  --bind "$AIMETH_OUTPUT_ROOT:/output" \
  --env PYTHONPATH=/opt/aimeth,HF_HOME=/run/aimeth/hf-cache,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,XDG_CACHE_HOME=/run/aimeth/cache \
  "$AIMETH_IMAGE" python3 -m aimeth_swarm.run --config /run-config.json \
  --local-root /run/aimeth/population --output-root /output/population \
  --tokenizer-dir /models/tokenizer --allow-model-calls
