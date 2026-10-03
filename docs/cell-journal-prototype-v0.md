# Offline computational-cell journal prototype v0

Date: 2026-10-03. Status: **implemented and locally tested**. This small adapter adds SQLite persistence to the existing offline cell contract. It does not implement a developmental policy, API dispatcher, cluster scheduler or scientific evaluator.

Files: `prototypes/cell_journal.py`, `tests/test_cell_journal.py`. The existing `prototypes/cell_contract.py` is reused without modification by this work package.

## Transaction contract

Each accepted operation runs under `BEGIN IMMEDIATE` on one local SQLite database. The adapter loads and replays the current contract snapshot, validates the proposed signal or division, inserts an immutable transition receipt, and replaces the current snapshot **within the same transaction**. `COMMIT` is the acceptance boundary. No in-memory contract instance is cached across requests, so another connection's committed version is consulted before applying an update.

The database uses rollback-journal mode (`DELETE`), `synchronous=FULL` and `fullfsync=ON`, following the existing runtime's local transaction pattern. It is intended for a local filesystem and a single writer at a time. Each thread/process needs its own adapter connection; this package is not a shared-network-filesystem service.

| Situation | Behaviour |
|---|---|
| New journal | Requires an explicit seed-only `CellContract`; historical unreceipted transitions cannot be imported as journalled work |
| Valid new signal or division | Records one receipt and one updated snapshot atomically |
| Same event ID and identical inputs | Returns the existing receipt with `applied: false`; no state update or resource consumption |
| Same event ID with changed inputs | Raises `Conflict`; no replacement or hidden retry |
| Stale version, parent hash or other contract violation | Raises the underlying contract error; leaves receipts and snapshot unchanged |
| Exception before commit | Rolls back both receipt and snapshot changes |
| Process exit before commit | SQLite recovery restores the previous committed state in the tested local conditions |
| Commit succeeded but acknowledgement was lost | Reopening verifies the committed state; resending the identical operation retrieves its stored receipt |
| Corrupted snapshot or receipt chain | Startup fails integrity validation rather than continuing from unverified state |

Request identity includes the operation, logical time and full inputs. A recovery retry must retain the original inputs and time. Supplying a new time under the same event ID is a conflict, not an idempotent retry.

Receipts preserve the sequence, event identity, canonical request and its hash, resulting cell state, previous/current snapshot hashes, contract-event hash and a receipt-chain hash. The `snapshot_sha256` covers the complete snapshot; the contract's `checkpoint_sha256` is its event-chain head. These are distinct digests with different scopes. Receipt update/delete triggers prevent ordinary SQL overwrites. Hashes detect inconsistent content but are not cryptographic authentication against a party able to rewrite the entire database.

## Startup and recovery verification

On each open, the adapter validates the snapshot with `CellContract.from_json`, reconstructs a fresh seed contract, replays every stored receipt and compares requests, results, event hashes, receipt links and intermediate snapshot hashes. The final replay must exactly match the committed snapshot. The number of receipts must equal the number of accepted contract events.

`verify()` repeats this check under a writer-excluding transaction. `cell()`, `state_hash()` and `summary()` expose validated current state. The public mutation methods mirror the contract's `apply_signal()` and `divide()` methods; their return value includes `applied`, the original result, receipt identity and snapshot hash.

The fault hook has four explicit test points: `after_receipt_insert`, `after_snapshot_write`, `before_commit` and `after_commit`. It is provided for local failure injection, not production scheduling.

## Recorded verification

Environment: local Python 3.9.6. Databases for every test were created inside `TemporaryDirectory` and removed on completion. No API, network, model or scheduler calls were made by these tests.

Adapter-only command and observed output:

```text
python3 -m unittest discover -s tests -p 'test_cell_journal.py' -v
...
Ran 14 tests in 0.526s

OK
```

The 14 test methods cover committed reopen; identical and conflicting duplicates; stale versions; persistent division lineage; exceptions at three precommit boundaries; lost acknowledgement after commit; process exits; two-connection state visibility; SQL receipt immutability; corrupted snapshot/receipt rejection; and seed/history validation. Parameterized subcases are not counted as additional test methods.

The process-exit test launches a real subprocess and calls `os._exit(23)` at each specified point, bypassing Python cleanup:

| Exit point | Receipts and synthetic units found after reopening | Next identical operation |
|---|---|---|
| After receipt insertion, before snapshot write | 0 receipts / 0 units | Applied once |
| After snapshot write, before commit | 0 receipts / 0 units | Applied once |
| After commit, before acknowledgement | 1 receipt / 1 unit | Existing receipt returned; not reapplied |

Combined contract-plus-journal verification used the current contract, including the subsequently added logical-time provenance checks:

```text
python3 -m unittest discover -s tests -p 'test_cell_*.py' -v
...
Ran 38 tests in 0.443s

OK
```

This is **24 contract tests + 14 journal tests**, not 38 independent scientific experiments. The current `aimeth_runtime` code identity was independently reconstructed from tracked HEAD and matched the working sources:

```text
sha256:f0c5edfdfb130cf62bd339b464024626117b35677a5cc0da67b591bf1bd1f29c
unchanged_from_HEAD: true
```

## Boundaries and remaining integration

- Resource accounting remains the cell contract's synthetic units: one accepted signal costs one unit and a division costs two. No token, monetary, GPU or wall-clock budget is enforced here.
- The database records accepted transitions. Rejected proposals and attempted deliveries are returned as errors; it does not yet provide the full attempted/failed/unknown scientific-run ledger. That ledger remains necessary before population comparisons.
- Full-history snapshots and replay are deliberately simple and expensive. This prototype has no demonstrated 10K throughput, concurrent-writer scaling, queueing, asynchronous response reconciliation or database migration path.
- Tests demonstrate local process-exit recovery at specified boundaries, not survival of arbitrary power loss, filesystem corruption, remote storage failures or coordinated malicious edits.
- Idempotency applies to these **local transitions**. It makes no claim about exactly-once remote API inference or billing.
- No code path in the frozen worker was changed or connected to this adapter, and no v8 configuration or remote job was inspected or modified. Current unknown v8 telemetry remains unknown.

The next integration decision is to connect validated transitions and an attempted-event ledger to a newly versioned offline runner, then freeze concrete development rules and bounded experimental inputs. This journal is an engineering prerequisite with verified local behaviour; it provides no evidence that a population self-organizes or improves task capability.
