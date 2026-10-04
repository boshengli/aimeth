# Direct 10K GPU08 population run · v7

V7 follows the v6 first-batch result: all 16 requests reached the 2,048-token output cap; one returned visible text, but it was truncated (`finish_reason=length`) and invalid JSON, while 15 had empty final content. The population stopped before the remaining 9,984 workers or governance phase. This is a runtime/output-budget failure, not a mathematical evaluation.

- Population and organization: unchanged 100 groups × 100 workers, 4 observers per group, 100 group chiefs, 1 global chief; two cycles and 21,002 call slots. There is no single-Agent gate or smaller-population ladder.
- Model/runtime: pinned local DeepSeek-V4-Flash-0731 on GPU08, all eight H20 GPUs, loopback-only SGLang service.
- Output cap: 3,072 tokens per response, an engineering hypothesis following the v6 truncation evidence.
- Request timeout: 1,200 seconds; concurrency: 16.
- Population deadline: 165 hours (`--time=165:30:00`), within the `Res_libs` reservation ending 2026-10-08 11:00 Asia/Shanghai when submitted on 2026-10-01 morning.
- Recovery: node-local SQLite remains authoritative during execution; the five-minute sidecar copies rolling consistent checkpoints and atomic receipts to the private shared run directory.
- Evidence: preserve every response receipt, including truncations, failures, and null outcomes. A valid response is not mathematical validation; proof obligations, independent population replicates, and organization-effect evaluation remain separate.

V6 measurements and hashes are in `milestones/m2-8-direct-10k-gpu08-v6-attempt-v1.html`. V7 is a fresh run identity and must not resume or overwrite earlier data.
