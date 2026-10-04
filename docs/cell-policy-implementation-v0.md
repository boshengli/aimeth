# Offline developmental-policy implementation v0

4 October 2026. Work in progress: core implementation and finite verification. This document is updated with actual outputs after execution; it does not represent a completed scientific experiment.

Files: `prototypes/cell_policy.py`, `tests/test_cell_policy.py`. Source card: `plans/cell-development-pilot-v0.json`; the card remains a proposal and is not silently edited by this work.

## Implemented core

The deterministic runner connects the existing cell contract to four local modules: enumerate an owned candidate shard, check a candidate against its public digest predicate, deliver typed evidence or obligations, and divide with an explicit locked handoff. The policy retains separate mutable queues, ownership, artifact access, attempted-operation accounting and a hash-chained input-event journal. It never writes private contract fields. Each normal turn operates on detached contract and policy objects and commits their pair only after bounds and joint serialization validate.

Four arms share the declared ceilings. Development starts with four cells and transfers remaining work to daughters only through accepted parent–child messages. Fixed and independent references start with sixteen cells and non-overlapping parity shards. The independent arm has no communication edges. The matched-start arm has four cells and no division. Newborns join the next sorted round-robin sweep. Initial rings and lineage edges are imposed rules, not emergent geometry.

## Explicit interpretations and limits of this implementation

- A policy event hash covers its immutable input envelope and predecessor hash; check artifacts refer to this hash. Outcomes and state are verified through deterministic joint replay. This avoids a circular definition in which an artifact contains an event hash whose own preimage contains that artifact.
- Duplicate/stale perturbations are explicitly labelled `fault_harness` and consume attempted-action, route and byte allowances. They are not portrayed as selected autonomous cell modules. A stale test includes a valid harness constraint delivery to advance the receiver before presenting the original held signal.
- A rejected delivery first leaves detached contract/policy application unchanged. Terminal outbox cleanup and lock release are then represented by a distinct `terminal_rejection_cleanup` input event. This makes the card's rejection-preservation clause compatible with its separately required failed-handoff cleanup rule.
- Byte observations are canonical serialized bytes, not Python heap use or process RSS. Policy bytes exclude the byte-metric record itself; joint bytes include the complete envelope. Contract bytes measure the full contract JSON. Peak measurements retain the largest observed serialized sizes.
- Joint snapshots are replayable in-memory artifacts. The existing SQLite adapter journals contract transitions only and cannot atomically persist this new mutable policy state; this runner therefore does not reuse that adapter to claim joint durability. Snapshot file writes in the fixture CLI are output artifacts, not crash-safe checkpoints.
- Candidate generation is a fixed enumeration algorithm; checking uses a public predicate. No models, training, morphology, mathematical proofs, 10K execution or intelligence improvement are tested.

## Verification and results

Pending completion of the current execution. The allocation is 42 arm–seed–condition software cases: three seeds; eight satisfiable/unsatisfiable arm pairs and six communication-fault pairs per seed. Independent communication-fault pairs are not allocated, and must not be counted as passes.

Initial seed-0 exploration already exposed a permitted resource stop: `fixed_16` on the unsatisfiable input reached the 128 route-attempt ceiling while retaining seven verified witnesses. This outcome must remain visible alongside exhausted and successful runs; no extra allowance is granted to force completion.
