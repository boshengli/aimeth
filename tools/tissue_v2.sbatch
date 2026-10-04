#!/bin/bash
#SBATCH -J aimeth-p1v2-domains
#SBATCH -p gpu
#SBATCH -A libs
#SBATCH --reservation=Res_libs
#SBATCH -w gpu08
#SBATCH -c 32
#SBATCH --mem=240G
#SBATCH -t 20:00:00
#SBATCH -o /data/libs/aimeth/p1-v2-domains/slurm-%j.log
set -euo pipefail
cd /data/libs/aimeth/p1-v2-domains/src
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
echo "start $(date -Is) $(hostname)"
/data/libs/aimeth/envs/dev/bin/python -B tools/run_tissue_v2.py /data/libs/aimeth/p1-v2-domains/out 30
echo "end $(date -Is)"
