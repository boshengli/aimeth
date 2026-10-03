# Computational-cell contract prototype v0

Date: 2026-10-03. Status: **implemented and locally tested, offline only**. This is a state-contract prototype, not an integrated developmental system, population experiment or result supporting self-organization.

## Implemented scope

`prototypes/cell_contract.py` implements one in-memory, single-writer `CellContract`. It reuses `Conflict`, canonical JSON, digest and identifier validation from the existing store. It is deliberately outside `aimeth_runtime/`: the current worker hashes all Python files in that directory, so an additional file there would change its frozen code identity even without an import.

| Entity or operation | Enforced contract |
|---|---|
| Cell | Unique bounded ASCII identity; seeds have null parent and version 0; offspring have a recorded parent; returned views are detached copies |
| Expression | Exactly the declared module identifiers; finite, non-Boolean activation values from 0 to 1; values are independent gates, not necessarily a probability distribution |
| Local memory | Bounded canonical JSON object, inherited by value during division; this version has no memory-edit operation |
| Signal | Five closed payload schemas: candidate, constraint, evidence, obligation and resource request; bounded payload bytes |
| Communication | Recorded directed edge; exact current sender and receiver versions; message creation cannot predate either cell, referenced version or edge; integer logical time; delivery before expiry |
| Message ancestry | An accepted parent signal must have been received by the new sender; exact parent-message hash; child creation cannot predate parent acceptance |
| State update | One accepted signal increments only the receiver version and records its last signal; optional expression update must validate |
| Division | Current parent version and full state hash must match; copy parent expression/memory; new identity and lineage; increment parent version; add reciprocal parent–child edges |
| Bounds | Population, outgoing neighbours, total events, synthetic transition units, memory/payload bytes and complete snapshot size |
| Duplicate handling | Explicit `Conflict` for an already-applied event or message, or an existing child identity; duplicates never consume units or mutate state |
| Recovery | Canonical JSON contains seed configuration plus hash-chained inputs; replay revalidates every operation and checks the complete resulting event and head hash |

Signal acceptance costs one synthetic unit; division costs two. These are local transition counters, **not tokens, GPU seconds, money or measured biological costs**. A resource-request signal does not grant resources. A candidate or evidence signal being accepted does not validate its scientific content or verify that an artifact exists.

The prototype supports a declared population cap up to 10,000, but this is a schema bound, not demonstrated 10K performance. Snapshot checking serializes the accumulated history before each commit; this intentionally simple approach is unsuitable for a production high-throughput population runtime. Accepted state must fit the same 16 MiB snapshot bound used by replay. Resource or snapshot rejection occurs before mutation.

## Minimal local example

Run from the repository root:

```python
from prototypes.cell_contract import CellContract

cells = CellContract(
    modules=["construct", "check"],
    seeds=[{"cell_id": "seed", "expression": {"construct": 1, "check": 0},
            "memory": {"obligation": "synthetic-fixture"}}],
    edges=[],
    limits={"max_population": 2, "max_units": 3, "max_events": 2,
            "max_neighbours": 1, "max_payload_bytes": 256},
)
cells.divide("birth-1", parent_id="seed", child_id="daughter",
             expected_version=0, parent_state_hash=cells.state_hash("seed"), now=1)
cells.apply_signal("delivery-1", {
    "message_id": "m1", "sender": "seed", "receiver": "daughter",
    "sender_version": 1, "receiver_version": 0,
    "kind": "obligation", "payload": {"obligation_id": "o1", "statement": "fixture"},
    "parent_message_id": None, "parent_message_hash": None,
    "created_tick": 1, "expires_tick": 4,
}, now=2)
restored = CellContract.from_json(cells.to_json())
assert restored.summary() == cells.summary()
assert restored.cell("daughter")["parent_id"] == "seed"
```

This constructs a lineage and delivers a synthetic signal. The caller supplies the division decision and expression changes; no model infers a development rule. Thus the example cannot be interpreted as spontaneous differentiation or emergence.

## Verification record

Command:

```sh
python3 -m unittest discover -s tests -p 'test_cell_contract.py' -v
```

Observed locally on 2026-10-03 using Python 3.9.6: **20 tests passed in 0.011 seconds**. Test-method count is reported; several methods include additional parameterized subcases. These tests cover valid delivery and all five schemas; stale state; reversed/non-neighbour edges; repeated events and messages; expiry/future timestamps; incorrect, absent or temporally impossible parent messages; bounded and invalid expression/payloads; lineage and exact inheritance; changed parent hashes; population/resource/event/neighbour limits; detached state views; replay and continued execution; tampered snapshots; and snapshot-budget rejection without partial mutation.

The current runtime identity and the identity reconstructed from tracked HEAD runtime sources were both:

```text
sha256:f0c5edfdfb130cf62bd339b464024626117b35677a5cc0da67b591bf1bd1f29c
```

No existing runtime source, worker entry point, v8 configuration, API request, scheduler job or cluster state was changed by this prototype work. This check establishes unchanged local runtime sources; it does not independently inspect a remote v8 deployment.

## Limits and next integration points

1. **Durability and concurrency:** snapshots are returned as strings; no file is written and no process lock or database transaction is provided. Connect validated transitions to the existing transactional journal with crash-safe checkpoint persistence before claiming production recovery. Hashes detect unintended corruption; they are not signatures against a party that can rewrite both history and hashes.
2. **Development and costs:** implement and freeze the module update, division eligibility, topology adaptation and scheduler rules; replace synthetic units with the bounded resource ledger needed by a new experiment. No existing frozen run should import this prototype retroactively.
3. **Scientific evaluation:** connect isolated tasks, independent verification and population-level experimental allocation. Current tests validate software contracts only. They do not demonstrate mathematics, throughput, functional improvement, cellular differentiation or self-organization.

The contract intentionally uses current-version delivery. Delayed responses after either endpoint changes state are rejected rather than queued or reconciled. Integration must specify whether this conservative policy is retained or replaced by a separately versioned asynchronous policy.

## Temporal consistency correction · 2026-10-03

Independent review reproduced a root signal whose creation predates its sender's birth, and another whose creation predates the sender version it claims. The original 20-test validation above did not cover these cases. The finding remains recorded in `manuscripts/aimeth/prototype-review-v0.md`; its reviewed file hashes identify the earlier implementation.

The corrected contract tracks cell birth ticks, current-version establishment ticks and directed-edge creation ticks. Initial cells, version zero and initial edges exist from tick zero. Division establishes the new cell, the parent's new version and both lineage edges at its recorded tick; accepted delivery establishes the receiver's new version at its delivery tick. These indexes are derived from the seed configuration and hash-chained events on every replay, without adding redundant mutable fields to saved snapshots.

Both endpoint versions identify snapshots already established when a signal was created, and the directed edge must also exist then. A creation time before any of these bounds is rejected before resource charging or state mutation. The supplied `created_tick` is preserved: a signal created at tick 1 and delivered at tick 4 remains a valid delayed signal if the referenced states and edge are unchanged and expiry permits delivery. Creation exactly at an establishment tick is permitted; recorded event order distinguishes the already applied transitions. This prototype does not separately record a message-preparation event, so it does not claim sub-tick creation-time attestation.

Four regression tests cover both endpoints' birth/version bounds before and after replay, a valid delayed signal at the boundary, and rejection of an impossible history even when its hashes are internally consistent. Two pre-existing successful-delivery fixtures now use creation times at or after the preceding division. The snapshot envelope remains `cell-contract.v0`; valid historical events retain their format, while histories containing the previously accepted impossible chronology are now rejected rather than silently repaired. No scheduler, model calls, resource policy or frozen v8 source is changed by this correction.

Post-fix validation: `python3 -B -m unittest discover -s tests -p 'test_cell_contract.py' -v` using Python 3.9.6 completed with exit code 0: **24 tests passed in 0.013 seconds**. The full captured output and tested source hashes are saved in `manuscripts/aimeth/prototype-fix-validation-v0.txt`. This supersedes the earlier 20-test result for the corrected implementation; the prior result and independent review remain historical records.
