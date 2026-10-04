#!/bin/bash
#SBATCH -J aimeth-p2-evald
#SBATCH -p gpu
#SBATCH -A libs
#SBATCH --reservation=Res_libs
#SBATCH -w gpu08
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 3-12:00:00
#SBATCH -o /data/libs/aimeth/rt/runs/p2-controls-v1/evald-%j.log
# CPU-only visible-check worker for the API-backed P2 pilot; requests no GPU.
set -euo pipefail
SOURCE=/data/libs/aimeth/rt/runs/p2-controls-v1/source
ROOT=/data/libs/aimeth/rt/runs/p2-controls-v1/evalq
cd "$SOURCE"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p "$ROOT"
rm -f "$ROOT/STOP"
echo "start $(date -Is) $(hostname) cpu-only"
/data/libs/aimeth/envs/dev/bin/python -B -m aimeth_rt.evalq daemon \
  "$ROOT" \
  /data/libs/aimeth/data/arc-agi/arc2/data/evaluation \
  /data/libs/aimeth/p2-bio/v1 \
  /data/libs/aimeth/p2-bio/runs/calib-v2/gene_info.json \
  8
echo "end $(date -Is)"
