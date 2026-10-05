#!/bin/bash
# P2 wave 1 on ARC-AGI-2 evaluation (120 tasks), deepseek-flash, reasoning_effort low, token budget 131,072 completion tokens per task.
# Arms: single long call (1 x 131072) | independent (4 x 32768, select by training pairs) | self_repair (4 x 32768).
cd /data/libs/aimeth/rt/src
PY=/data/libs/aimeth/envs/dev/bin/python
R=/data/libs/aimeth/rt/runs
A=/data/libs/aimeth/data/arc-agi/arc2/data/evaluation
COMMON="--tasks ALL --arc-dir $A --provider deepseek --model deepseek-flash --reps 1 --workers 30 --llm-start 15 --llm-cap 30"
setsid nohup $PY -B tools/rt_run.py arc independent $COMMON --n 1 --max-tokens 131072 --budget-cny 85 \
  --out $R/w1-arc2-single131k-ds.jsonl >> $R/w1-arc2-single131k-ds.log 2>&1 < /dev/null &
setsid nohup $PY -B tools/rt_run.py arc independent $COMMON --n 4 --max-tokens 32768 --budget-cny 145 \
  --out $R/w1-arc2-indep4x32k-ds.jsonl >> $R/w1-arc2-indep4x32k-ds.log 2>&1 < /dev/null &
setsid nohup $PY -B tools/rt_run.py arc self_repair $COMMON --n 4 --max-tokens 32768 --budget-cny 150 \
  --out $R/w1-arc2-repair4x32k-ds.jsonl >> $R/w1-arc2-repair4x32k-ds.log 2>&1 < /dev/null &
