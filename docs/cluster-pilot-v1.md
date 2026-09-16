# First institutional cluster calibration · protocol v1

Frozen before population outcomes on 2026-09-16. This is a bounded live integration/calibration experiment on public development mathematics, not a confirmatory organization study or a frontier proof attempt.

The user explicitly requested the existing institutional cluster and prefers DeepSeek/GLM if public APIs are needed. We located the historical two-node deployment task, verified the current institutional gateway model list and a CPU-only Slurm probe on the reserved H20 node. The two-node history is not evidence that all old services are still running or that the gateway maps to those same nodes. GPU02 is currently allocated; existing jobs/services will not be canceled or reconfigured. No public provider is needed for this pilot.

## Frozen plan

- Models: served IDs `deepseek-v4-flash-0731`, `glm-5.3-flash`, accessed through the existing institutional gateway. Backend weight digests and router-to-node mapping are not independently attested. Preserve full response model fields; no cross-model causal inference.
- Population arms S/I/L/X. Reference N=8, group size=4, R=2. S has one agent and 16 sequential calls; others have eight agents and two rounds. Same maximum 16 calls per population.
- Tasks: `integral-rational`, `prime-counterexample` from the public development catalog. Two repeats per task/model/arm = 32 isolated populations, at most 512 requests. Common seeds within paired blocks; model and arm execution order determined by the recorded schedule. No memory shared across runs.
- Temperature 0.6, top_p=1, maximum 512 output tokens, max attempts=1, client concurrency at most 2. Frozen provider options: `chat_template_kwargs.enable_thinking=false` and `response_format.type=json_object`. These are actual recorded request fields, not undocumented prompt edits. Transport calibration showed that the GLM service emitted prose before JSON without structured output; a follow-up transport probe with structured output returned valid JSON. Preserve both probes separately from scored populations.
- Selection: the existing fixed-seed content-blind terminal lottery, K=1. Primary outcome: strict exact-certificate verdict on selected output. No post-hoc extraction of a valid JSON substring. Distinguish wrong certificates, malformed output and technical failure. Ceiling performance on easy public tasks means more difficult tasks are needed; it does not establish equal performance on frontier math.

## Execution and bounds

A CPU-only Slurm client job on the reserved H20 node calls existing inference services. It does not launch a new GPU model, request a separate GPU allocation, or displace existing services. All open journal databases live on node-local `/tmp`; closed run records are copied to the shared experiment directory after each population. Full run copies and quota state are exported at orderly termination. Raw identities/endpoints/credentials remain private.

Durable SQLite admission reserves one call and its full output-token ceiling before every HTTP dispatch. Reservations are idempotent by attempt token and never refunded after unknown outcomes. Whole-experiment limits: 512 calls, 262144 reserved output tokens, 25 minutes coordinator wall time; Slurm job limit 30 minutes. Request body <=16384 UTF-8 bytes, response <=256 KiB, absolute subprocess request deadline <=120 seconds. One coordinator holds a file lock. No automatic retries. Failed or timed-out requests remain charged; unmet populations remain in the planned denominator.

These bounds do not establish equal total token cost, a tokenizer-exact input-token reservation or attributable GPU-hours for shared inference. Input/total usage is recorded when returned, unknown otherwise. Server honoring output limits is observed from receipts; the client cannot undo already executed server work after disconnect. This bounded screening pilot does not claim the full 10K production-budget/supervision gate is complete. A hard node loss still requires recovering durable copies; no multi-host failover is implemented.

The model receives task statements and authorized peer excerpts only. No evaluator code, solutions, filesystem mount or terminal feedback is sent to the inference service. The evaluator runs in the client after terminal selection, without feedback to the scored population. Published tasks are already contaminated controls.

## Outputs and interpretation

Preserve exact requests/responses, event chains, selection ancestry, mathematical verdicts, calls, input/output tokens, elapsed time and all failures. Report counts by model/arm and task, not agent-level significance. Two task families and two repeats are inadequate for generalization or power claims. Keep transport probes outside the scored experiment. Inspect pre-existing allocation and endpoint metadata as current observations, with historical deployment claims separate.

Deliver another versioned HTML with actual job IDs, results, limitations, hashes, code versions and next decisions. The next mathematical step is independently reviewed multi-step PDE tasks and the Navier–Stokes case; 10K expansion requires a calibrated model, harder tasks, input-budget enforcement and throughput evidence.

## Recorded route correction before mathematical outcomes

Initial Slurm job 190041 used the gateway's campus address, which was reachable from the Mac but timed out from gpu08. Its partial database/quota snapshot was preserved and this owned job was canceled. A compute-node probe verified the internal gateway hostname tln02 responds (unauthenticated HTTP 401). The replacement uses a new experiment directory and immutable manifest, not an in-place edit. This is an engineering protocol deviation, excluded from mathematical-success comparisons and retained in failure accounting. The supervisor was also tightened to stop new dispatch and terminate pending child requests on cancellation; no model result informed that change.
