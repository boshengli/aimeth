#!/bin/bash
cd /data/libs/aimeth/p2-bio/src
A="/data/libs/aimeth/data/callus-xenium-20251101/Gene group2.csv"
B=/data/libs/aimeth/p2-bio/v1
R1=/data/libs/aimeth/p2-bio/runs/calib-v2
R2=/data/libs/aimeth/p2-bio/runs/calib-v2-glm
mkdir -p $R2
setsid nohup /data/libs/aimeth/envs/dev/bin/python -B tools/bio_generate.py $B "$A" $R1 \
  --models deepseek:deepseek-flash:65536:reasoning_effort=medium --samples 2 --workers 6 >> $R1/generate.log 2>&1 < /dev/null &
setsid nohup /data/libs/aimeth/envs/dev/bin/python -B tools/bio_generate.py $B "$A" $R2 \
  --models zhipu_coding:glm-5.3-flash:65536 zhipu_coding:glm-5.3:65536 --samples 4 --workers 8 > $R2/generate.log 2>&1 < /dev/null &
echo launched
