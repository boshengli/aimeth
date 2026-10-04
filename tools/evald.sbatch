#!/bin/bash
#SBATCH -J aimeth-evald
#SBATCH -p gpu
#SBATCH -A libs
#SBATCH --reservation=Res_libs
#SBATCH -w gpu08
#SBATCH -c 24
#SBATCH --mem=96G
#SBATCH -t 3-12:00:00
#SBATCH -o /data/libs/aimeth/rt/evald-%j.log
# Sandboxed evaluation service for agent workflows (no network on GPU08; see aimeth_rt/evalq.py).
set -euo pipefail
cd /data/libs/aimeth/rt/src
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
rm -f /data/libs/aimeth/rt/evalq/STOP
echo "start $(date -Is) $(hostname)"
/data/libs/aimeth/envs/dev/bin/python -B -m aimeth_rt.evalq daemon /data/libs/aimeth/rt/evalq \
  /data/libs/aimeth/data/arc-agi/arc1/data/evaluation /data/libs/aimeth/p2-bio/v1 \
  /data/libs/aimeth/p2-bio/runs/calib-v2/gene_info.json 22
echo "end $(date -Is)"
