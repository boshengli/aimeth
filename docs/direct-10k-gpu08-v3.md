# Direct 10K GPU08 population run · v3

Frozen 2026-10-01 for one exploratory mathematical population run. This supersedes neither earlier attempts nor the M2 organization proposals; it preserves them as separate evidence.

- Population: 100 groups × 100 analysis workers, 4 observers per group, 100 group chiefs, and 1 global chief (10,501 logical roles); two cycles, 21,002 planned call slots, and a maximum of 16 in-flight API requests.
- Organization: SLCW phased V1 adaptation for unforced incompressible Navier–Stokes on R³ with smooth rapidly decaying divergence-free initial data. Candidate claims remain unverified. No one-agent success gate or small-population ladder.
- Model: the locally validated DeepSeek-V4-Flash-0731 checkpoint and SGLang Hopper image, served only on GPU08 loopback. Use the empirically successful `SGLANG_OPT_FP8_WO_A_GEMM=1` setting and a job-specific node-local Triton cache. One smoke request does not validate throughput, mathematical quality, or population effects.
- Compute: one exclusive Slurm allocation for all eight H20 GPUs, 32 CPUs, all node memory, up to 8h30m. Model readiness is bounded at 30 minutes; population execution uses its frozen 8-hour deadline. The model is not silently switched if startup or inference fails.
- Runtime controls: 16 concurrent calls, 120-second request timeout, 1,024 output tokens per attempt, phase-specific input caps, transactional token/call budget, receipt-first durable recording, checkpoints every 1,000 reserved calls and phase boundaries, no hidden request retry, and stop after five consecutive transport failures. Mathematical disagreement, proof gaps, or failure to converge are recorded rather than treated as technical stops.
- Evidence: exact source commit, input manifest, configuration, model and container identities, Slurm allocation, realized requests/responses, usage, receipts, checkpoints, and failures. Private response/event payloads stay under the restricted cluster run root; the report exposes redacted evidence and hashes.
- Inference limit: this is one population run on one task instance, not an independent replicate. It can establish execution and characterize this run only; it cannot establish architecture superiority or a verified Navier–Stokes result.

Source: `examples/slcw-direct-10k-gpu08-v3.json`; batch entry: `cluster/direct-10k-gpu08-v3.sbatch`. Slurm submission is permitted only after an owned GPU08 allocation is visible and the pinned model/image identities match the local GPU smoke record.
