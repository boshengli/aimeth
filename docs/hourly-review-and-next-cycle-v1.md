# Hourly review and next-cycle operating plan · v1

Date: 2026-10-01 (Asia/Shanghai)  
Scope: project review cadence, active direct-10K run oversight, efficiency changes, and next-cycle preparation.

## Operating rule

An active hourly heartbeat reviews the project goal and records a compact, timestamped review. It reads the registered control state (`PROJECT.yaml`, `STATUS.md`, `DECISIONS.md`, and the active task), then checks the latest run evidence and Slurm state through the authorized cluster route. A review distinguishes observed state from inference and proposal. If nothing material changed, it records a concise no-change result without creating a new report or user notification.

The automation is attached to the current AIMeth task, hourly, and configured to notify only on failed runs. It is a review mechanism; it does not change a frozen run profile or submit a duplicate job.

## Efficiency policy

1. Use one source-of-truth live receipt/checkpoint per review; derive counts and rates from it rather than repeating ad hoc scans or copying the same facts into multiple narratives.
2. Keep runtime acceptance, JSON/schema validity, role/task compliance, and mathematical proof status as separate fields. Do not turn parser success into scientific success.
3. Reuse the already validated direct-10K roster, model-serving path, recovery sidecar, and report template. Do not repeat smoke or single-Agent probes as prerequisites.
4. Investigate only material deltas: stalled throughput, error/timeout changes, checkpoint integrity, rising malformed-output rate, governance phase transitions, resource risk, or an explicit protocol deviation.
5. Minimize duplicated prose while keeping immutable snapshots, raw-receipt hashes, failed attempts, independent run IDs, and required scientific validation.

These are process changes and measurement rules. No architecture effect, mathematical discovery, or production-grade recovery guarantee is inferred from them.

## Active-run handling

The last recorded live evidence is v8 / Slurm 235511 at 2026-10-01 10:27 Asia/Shanghai: RUNNING on GPU08 with 8×H20; 70 runtime-accepted worker receipts, 55 valid requested JSON objects, 15 non-JSON responses, 16 requests in flight, 9,914 pending, and SQLite integrity `ok`. These are a timestamped observation, not a claim about current state. The immutable HTML launch snapshot is earlier (10:21; 34 receipts).

While v8 remains active, preserve its frozen configuration and continue its authorized 10K run. Hourly reviews may flag a material operational issue; they do not change the run, requeue failed calls, or launch a second population without an explicit recorded execution decision. Preserve all call outcomes, non-JSON content, unattempted denominator, token usage, checkpoint identity, and governance handoffs.

## Next-cycle preparation

Prepare, but do not submit, the next-cycle run card while v8 is active. When v8 reaches a terminal or planned analysis boundary:

- Audit all receipts from the immutable private checkpoint. Report server completion, runtime acceptance, JSON/schema validity, role/task compliance, and proof evaluation separately.
- Attribute time and token cost per attempted worker and per accepted/schema-valid output; estimate throughput from elapsed wall time and settled attempts, with in-flight work reported separately.
- Audit governance messages as actual consumed inputs, not merely sent messages; check observer/chief participation and cross-round causal links.
- Choose only a bounded engineering change supported by the audit. Keep the same task, population, and evaluation when possible; assign a new run ID for any changed generation condition. If a research factor or estimand changes, freeze a new protocol and do not pool outcomes.
- Preserve direct 10K execution. No single-Agent success, smaller-population ladder, or positive mathematical result is an entry condition.
- Before any confirmatory architecture comparison, freeze model/checkpoint, task instances, prompt set, organization policy, stopping rule, proof evaluator, resource quota, and independent-population replication plan. Keep current engineering attempts out of confirmatory estimates.

## Hourly record fields

Append one record to a private, append-only review log: timestamp and timezone; run/job identity; scheduler state/node/GPU allocation; settled, accepted, schema-valid, in-flight, pending, and failed counts; token usage and elapsed time; checkpoint ID/hash and integrity result; governance phase; material change or `no_change`; interpretation limits; next action; source evidence locations. Never put credentials, private response bodies, or reference solutions in the public repository.

## Readiness

- Hourly goal review: configured in the Codex app; live delivery to be confirmed by its first scheduled run.
- Current v8 execution: active at the last timestamped evidence; refresh state before operational decisions.
- Next-cycle design: ready to prepare; parameter selection awaits a full v8 evidence audit.
- Confirmatory architecture comparison: not ready; independent populations and a frozen evaluation protocol are still required.
- Mathematical result: not established; response validity and proof verification remain outstanding.
