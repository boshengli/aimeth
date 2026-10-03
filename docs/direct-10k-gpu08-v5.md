# Direct 10K GPU08 population run · v5

V5 keeps the 10,000-worker plus 501-governance-role organization and the Navier–Stokes task, with no single-Agent success gate and no staged population ladder. It is a new run identity because v4 stopped after 20 client timeouts and is preserved as an engineering failure, not resumed under changed settings.

- Population: 100 groups × 100 workers, 4 observers per group, 100 group chiefs, one global chief; two cycles and 21,002 planned calls.
- Model/runtime: DeepSeek-V4-Flash-0731, the same pinned SGLang Hopper image, GPU08 loopback service, and all eight H20 GPUs.
- Timeout: 600 seconds per request, increased from 120 after the v4 SGLang traces showed generation completing after the clients had timed out. This is a runtime hypothesis to test; it does not claim a mathematical or model-quality improvement.
- Wall-time: 72 hours for the population under one 72h30m Slurm allocation. The GPU partition has no configured MaxTime, and the `Res_libs` reservation ends 2026-10-08; the run stays within that reservation window.
- Checkpointing: continue node-local SQLite writes and phase/every-1,000-call project snapshots; add a five-minute rolling SQLite-backup and receipt-copy sidecar to the private shared run directory, retaining the two latest sidecar generations. A final snapshot is attempted at job exit. This reduces node-loss exposure while avoiding live SQLite writes on network storage.
- Each response and proof candidate remains unverified. The v4 and v5 populations are not independent replicates because they use the same design/task and v4 had no usable responses.

Frozen v4 evidence and the timeout rationale are in `milestones/m2-8-direct-10k-gpu08-v4-attempt-v1.html` and its evidence JSON. This v5 profile still requires runtime confirmation of response latency, checkpoint integrity, actual usage, and completion feasibility.
