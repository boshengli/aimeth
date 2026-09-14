# Engineering contract v0.1

Status: requirements for the next implementation, not claims of current runner behavior.

## Separation of concerns

```text
Frozen experiment manifest
  -> organization policy (roles, graph, schedule, memory, selection)
  -> durable task/event store and budget admission
  -> bounded inference/tool workers
  -> immutable candidate artifacts
  -> isolated final evaluation
  -> analysis tables and publication figures
```

The organization emits tasks and messages; the scheduler enforces resources without interpreting topology. A logical agent has an identity and a recorded state/history across steps. One completion with a different suffix is a sampling trajectory, not evidence of a complete autonomous research agent.

## Run and attempt identity

- Every run records code commit and dirty diff identity, protocol/task-set versions, model weight identity, tokenizer/chat-template hashes, container digest, tool versions, sampler, master seed, topology policy/realized graph, allowed corpus, evaluator, stopping rules, and budgets.
- Derive an immutable run fingerprint from a canonicalized configuration plus referenced content hashes. A new model, prompt, task, policy, or budget creates a new run. A filesystem model path is insufficient identity.
- Use `(run_id, agent_id, step_id, attempt_id)` for requests. Retries are additional attempts, never additional independent agents or experimental replicates. Preserve late and duplicate responses, but count at most one canonical accepted result per logical step.
- Recovery rejects mismatched fingerprints; it must not skip an ID solely because an older result file contains it.

## Event record

Each append-only event has schema_version, event_id, run_id, agent_id, step_id, attempt_id, UTC wall time, monotonic elapsed time, event_type, parent_event_ids, payload artifact hash, and visible input artifact hashes. Messages also record sender, recipients, graph version, delivery/read status, message truncation, and token cost.

Record requests/responses, tool calls/results, decisions, summaries, errors, retries, budget stops, candidate selection, verifier output and human intervention. Do not require hidden internal model reasoning: record all observable emitted text and actions and clearly disclose unavailable internals. A rewritten retrospective narrative is not an original trace.

Use one writer or an explicitly locked transactional store. Recover incomplete last records without silently discarding evidence. Record flush/checkpoint policy and test kill/resume, duplicate dispatch, timeouts, 429/503, truncated responses, malformed JSON, cancellation, and disk-full behavior before large runs. At-least-once network execution is realistic; guarantee idempotent accounting rather than unsupported exactly-once inference.

## Status is multidimensional

Separate `transport_status`, `generation_finish_reason`, `artifact_validation_status`, and `proof_verification_status`. An HTTP 200 is not a complete response or correct proof. A length-limited answer may contain useful partial results; keep it, label truncation, and apply the predetermined candidate policy.

Store missing usage as null plus a reason. Count retry usage when known; distinguish measured and estimated costs. Context overflow, dropped messages, summarization, and server preemptions can change scientific behavior and require trace records.

## Efficiency calibration

One Slurm allocation with a persistent model server and bounded client admission is the starting architecture for the supplied single-node scenario. Confirm node topology, scheduler policy, and installed serving options before selecting TP/DP. Do not launch 10K GPU jobs for 10K logical states.

Benchmark warm-up separately from measured work. For each concurrency level, supply enough representative requests to sustain that level (an initial design is at least 4× the tested concurrency, adjusted to observed latency and steady state); repeat and randomize order. Report achieved concurrency, prompt/completion token rates, TTFT, p50/p95 latency, wall time, allocation GPU-hours, cache status, memory, preemption, retry/OOM/503, and successful completion fraction.

Short 1K-output-token calibration may not predict long proofs or multi-round communication. Validate representative length distributions and cold/hot prefix conditions; reserve memory for actual context/KV requirements. Prefix caching is a measurable optimization, not a reason to give unequal context to experimental arms.

Budget admission reserves the maximum allowed request usage before dispatch and reconciles actual usage afterward; concurrent requests must not silently overspend. Define timeouts, cancellation, finalization reserve, and already-in-flight overshoot policy in the frozen protocol.

## Reproduction levels

1. **Artifact integrity and analysis replay:** frozen inputs/outputs and hashes reproduce derived tables/figures. The local tool currently checks the hash portion only.
2. **Procedure reproduction:** same code/configuration/model environment can rerun the experiment; nondeterministic realized outputs may differ.
3. **Statistical replication:** fresh runs reproduce an effect with uncertainty, including across selected tasks/models.
4. **Proof verification:** exact formal statements and trusted dependencies recheck, or independent mathematical review closes the proof obligations.

These levels must not be collapsed into “seed fixed, fully reproducible.” The current [vLLM documentation](https://docs.vllm.ai/en/latest/usage/reproducibility/) also limits reproducibility by runtime/hardware and batching behavior; check the deployed version rather than copying latest flags.

## Next implementation acceptance

First fix E01/E02/E04/E05/E09 from the source audit and add meaningful integration fault tests. Then run a small real workload, inspect all failures, and reconcile planned tasks, attempts, completed artifacts, token totals, and job exit status. Only afterward add organization policies and expand scale.
