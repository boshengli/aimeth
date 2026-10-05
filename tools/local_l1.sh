#!/bin/bash
# Local wave L1: ARC-AGI-2 pilot-40, local DeepSeek-V4-Flash-0731 (SGLang TP4 on gpu08, reasoning_effort low),
# budget per task instance: 8 calls, 262,144 completion tokens, 32,768 per call (single_long: one call, 245,760).
# Same backend for every arm, so arms are paired task by task. No money is spent (local model).
cd /data/libs/aimeth/rt/src
PY=/data/libs/aimeth/envs/dev/bin/python
R=/data/libs/aimeth/rt/runs
T=/data/libs/aimeth/rt/tasks/arc2-pilot40.json
A=/data/libs/aimeth/data/arc-agi/arc2/data/evaluation
M="--provider local_dsv4 --model deepseek-v4-flash-0731"
for KO in none no_cheap well_mixed; do
  setsid nohup $PY -B tools/rt_devorg.py --tasks $T --arc-dir $A $M --calls 8 --tokens 262144 --per-call 32768 \
    --knockout $KO --workers 8 --llm-start 8 --llm-cap 16 --out $R/L1-devorg-$KO.jsonl >> $R/L1-devorg-$KO.log 2>&1 < /dev/null &
done
for ARM in independent independent_cheap self_repair; do
  setsid nohup $PY -B tools/rt_run.py arc $ARM --tasks $T --arc-dir $A $M --n 8 --max-tokens 32768 --reps 1 \
    --workers 8 --llm-start 8 --llm-cap 8 --out $R/L1-$ARM.jsonl >> $R/L1-$ARM.log 2>&1 < /dev/null &
done
setsid nohup $PY -B tools/rt_run.py arc independent --tasks $T --arc-dir $A $M --n 1 --max-tokens 245760 --reps 1 \
  --workers 8 --llm-start 8 --llm-cap 8 --out $R/L1-single_long.jsonl >> $R/L1-single_long.log 2>&1 < /dev/null &
