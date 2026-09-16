#!/bin/bash
#SBATCH --job-name=aimeth-contract-calibration
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --signal=B:TERM@60
set -eu
umask 077
: "${AIMETH_CODE_DIR:?}" "${AIMETH_CONFIG:?}" "${AIMETH_LOCAL_ROOT:?}" "${AIMETH_OUTPUT_ROOT:?}"
cd "$AIMETH_CODE_DIR"
exec python3 -m aimeth_pilot.calibration --config "$AIMETH_CONFIG" --local-root "$AIMETH_LOCAL_ROOT" --output-root "$AIMETH_OUTPUT_ROOT"
