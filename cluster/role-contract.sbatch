#!/bin/bash
#SBATCH --job-name=aimeth-contract
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --time=00:35:00
set -eu
umask 077
cd "$AIMETH_CODE_DIR"
mkdir -p "$AIMETH_OUTPUT_ROOT"
{
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  hostname
  nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits || true
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits || true
} > "$AIMETH_OUTPUT_ROOT/resource-inventory-private.txt" 2>&1
python3 -m aimeth_pilot.role_contract --config "$AIMETH_CONFIG" \
  --fixtures examples/role-contract-contexts-v1.json \
  --local-root "$AIMETH_LOCAL_ROOT" --output-root "$AIMETH_OUTPUT_ROOT"
