# Direct 10K GPU08 population run · v6

V6 is a new 10K population attempt. V5 resolved transport timeouts: all 16 first worker calls returned HTTP 200, but all exhausted the 1,024 completion-token limit before emitting visible final content. V5 is preserved as an engineering failure and is not resumed under changed settings.

- Population: 100 groups × 100 workers, 4 observers per group, 100 group chiefs, 1 global chief; two cycles and 21,002 call slots.
- Model/runtime: the same pinned DeepSeek-V4-Flash-0731 and SGLang image, loopback-only service on GPU08 with all eight H20 GPUs.
- Output cap: 2,048 tokens per response, giving room beyond the 1,024-token reasoning-only response observed in v5. This is a testable runtime hypothesis, not a guarantee of final content.
- Request timeout: 1,200 seconds, based on the measured ~133-second first-batch completion time at 1,024 output tokens and 16 active requests.
- Population deadline: 160 hours (Slurm job limit 160h30m), within the existing `Res_libs` reservation ending 2026-10-08 11:00. The new schedule remains inside that reservation window.
- Checkpointing: node-local SQLite remains authoritative during live work. A five-minute rolling SQLite backup plus atomic receipts copy keeps the two latest generations on the private shared run root, with a final backup on normal/Slurm termination.
- No single-Agent success gate and no smaller-population ladder. Candidate outputs are unverified; proof checking and architecture comparisons remain separate stages.

V5's actual latency, finish reason, token usage, and recovery evidence are in `milestones/m2-8-direct-10k-gpu08-v5-attempt-v1.html`. V6 must be judged by first complete final responses, checkpoint integrity, real throughput, and total execution progress.
