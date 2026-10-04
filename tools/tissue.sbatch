#!/bin/bash
#SBATCH -J aimeth-p1-tissue
#SBATCH -p gpu
#SBATCH -A libs
#SBATCH --reservation=Res_libs
#SBATCH -w gpu08
#SBATCH -c 24
#SBATCH --mem=96G
#SBATCH -t 12:00:00
#SBATCH -o /data/libs/aimeth/p1-tissue-v1/slurm-%j.log
set -euo pipefail
cd /data/libs/aimeth/p1-tissue-v1/src
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
echo "start $(date -Is) $(hostname)"
/data/libs/aimeth/envs/dev/bin/python -B tools/run_tissue.py /data/libs/aimeth/p1-tissue-v1/out 20
echo "end $(date -Is)"
