#!/bin/bash
#SBATCH --job-name=aimeth-contract2
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --time=00:35:00
set -eu
umask 077
cd "$AIMETH_CODE_DIR"
python3 -m aimeth_pilot.role_contract_v2 --config "$AIMETH_CONFIG" \
  --fixtures examples/role-contract-contexts-v1.json \
  --local-root "$AIMETH_LOCAL_ROOT" --output-root "$AIMETH_OUTPUT_ROOT"
