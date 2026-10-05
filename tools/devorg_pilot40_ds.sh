#!/bin/bash
# DevOrg-ARC v0 pilot: 40 ARC-AGI-2 tasks (arc2-pilot40.json, sha256 rule frozen 21:55 before any devorg run),
# deepseek-flash low effort, budget 8 calls / 262,144 completion tokens / 32,768 per call (same as T-20261004-002 phase B).
cd /data/libs/aimeth/rt/src
setsid nohup /data/libs/aimeth/envs/dev/bin/python -B tools/rt_devorg.py --tasks /data/libs/aimeth/rt/tasks/arc2-pilot40.json \
  --arc-dir /data/libs/aimeth/data/arc-agi/arc2/data/evaluation --out /data/libs/aimeth/rt/runs/devorg-pilot40-ds.jsonl \
  --calls 8 --tokens 262144 --per-call 32768 --knockout none --workers 20 --llm-start 20 --llm-cap 40 --budget-cny 130 \
  >> /data/libs/aimeth/rt/runs/devorg-pilot40-ds.log 2>&1 < /dev/null &
