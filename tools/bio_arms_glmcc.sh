#!/bin/bash
# P2 bio single-agent controls, second model: glm-5.3 via Claude Code (GLM Coding Plan, official tool), 2 replicates
# (pseudo-task seeds 1000, 1001), 4 calls/task, effort high, thinking budget 32000, max output 65536.
cd /data/libs/aimeth/rt/src
PY=/data/libs/aimeth/envs/dev/bin/python
R=/data/libs/aimeth/rt/runs
for ARM in independent self_repair; do
setsid nohup $PY -B tools/rt_run.py bio $ARM --bench /data/libs/aimeth/p2-bio/v1 \
  --annot "/data/libs/aimeth/data/callus-xenium-20251101/Gene group2.csv" --out $R/bio-$ARM-glmcc.jsonl \
  --provider glm_cc --model glm-5.3 --n 4 --reps 2 --max-tokens 65536 \
  --workers 6 --llm-start 2 --llm-cap 4 >> $R/bio-$ARM-glmcc.log 2>&1 < /dev/null &
done
