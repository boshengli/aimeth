# Direct 10K GPU08 population run · v8

V7 preserved a stable serving path but not complete outputs: 17/17 server requests were HTTP 200, while 16 generations reached finish_reason=length (14 with empty final content, 2 with visible invalid-JSON truncated text) and only one worker response was accepted. V8 changes the DeepSeek-V4 generation mode from thinking to chat to test whether the configured reasoning budget was consuming the full output allowance before final content appeared.

- Population and organization: unchanged 100 groups × 100 workers, 4 observers per group, 100 group chiefs, 1 global chief; two cycles, 21,002 call slots. No single-Agent gate or reduced-population ladder.
- Model/runtime: pinned local DeepSeek-V4-Flash-0731 on GPU08, all eight H20 GPUs, loopback-only SGLang.
- Generation mode: DSV4 native chat mode; request option thinking=false. This is a new model-generation condition and run ID.
- Output cap: 3,072 tokens; request timeout 1,200 seconds; concurrency 16.
- Population deadline: 165 hours (Slurm job limit 165h30m), within the Res_libs reservation if started 2026-10-01.
- Recovery: node-local SQLite plus five-minute rolling consistent backups and atomic receipts to the private shared run directory.
- This mode change is an engineering hypothesis. Any accepted response remains mathematically unverified; do not interpret it as evidence of architecture effect.
