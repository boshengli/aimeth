# Independent review of the offline cell journal

3 October 2026 · Review version 0 · Findings against commit `00064b30940581632b5951a2e2860f3ef96efb42`

Reviewed `prototypes/cell_journal.py`, `tests/test_cell_journal.py`, and `docs/cell-journal-prototype-v0.md`. Reproductions used temporary local SQLite databases only. This record precedes any corrective implementation and must remain as the historical review.

**Verdict:** the ordinary adapter calls and injected process-exit tests support local transactional state/receipt atomicity and exact-request retry after lost acknowledgement. Two additional, reproducible integrity/schema defects remain. Neither result concerns exactly-once remote inference or provider billing: no remote API dispatch exists in this adapter.

## P2 — Ordinary SQL replacement bypasses receipt immutability, and duplicate retrieval returns the damaged result

Locations: `SCHEMA` receipt triggers, lines 27–30; `_mutate` duplicate branch, lines 147–151.

The update/delete triggers reject `UPDATE` and `DELETE`, but the actual connection accepts `INSERT OR REPLACE` for an existing receipt. No trigger was dropped, no hash was recomputed, and no storage file was edited. This contradicts the stated normal-SQL immutability contract. The duplicate branch then checks only the request text/hash and returns the altered result without checking the receipt hash or its association with the committed snapshot.

Reproduction using the existing test fixtures:

```python
import json
from tests.test_cell_journal import seed_state, message
from prototypes.cell_journal import CellJournal

# path is a new file inside a TemporaryDirectory.
with CellJournal(path, initial=seed_state()) as journal:
    first = journal.apply_signal("e1", message(), now=1)
    row = dict(journal.db.execute("SELECT * FROM receipts").fetchone())
    changed = json.loads(row["result"])
    changed["state_version"] = 999
    row["result"] = json.dumps(changed)
    columns = list(row)
    journal.db.execute(
        "INSERT OR REPLACE INTO receipts (" + ",".join(columns) + ") VALUES ("
        + ",".join("?" for _ in columns) + ")",
        [row[column] for column in columns])
    duplicate = journal.apply_signal("e1", message(), now=1)
    # Observed: first result version 1; duplicate result version 999;
    # actual snapshot version 1; duplicate applied False.
    journal.verify()  # Conflict: Receipt identity or chain mismatch.
```

`verify()` and reopening detect the mismatch, but that detection occurs after the already-open duplicate path can deliver a false result. The state transition itself was not reapplied; the problem is the integrity of the acknowledged result.

**Fix:** reject any insert that would replace an existing receipt sequence or event identity, including ordinary `REPLACE` statements, rather than relying only on update/delete triggers. Validate an existing receipt before returning it as a successful retry; validation must cover the result/hash and its place in the committed transition history, not only the unchanged request. For this bounded prototype, performing the existing full replay verification inside the transaction is an acceptable simple implementation. Add tests for replacement by sequence and event identity, corrupted duplicate-result retrieval, and a valid retry of an older receipt after later transitions. This is a local consistency guarantee, not authentication against an actor able to rewrite every record and validation rule.

## P2 — Rejected unsupported-schema databases are modified before validation

Location: initialization, lines 52–60.

The constructor runs journal pragmas and `executescript(SCHEMA)` before checking the schema marker. The subsequent transaction rollback cannot undo those earlier schema writes. A database containing only a metadata table with `schema_version=cell-journal.v999` was rejected with `Unsupported cell journal schema`, but it acquired the `current_state` and `receipts` tables plus both immutability triggers. Before opening, `sqlite_master` contained only the metadata table; after the rejected open it contained all five objects. The unsupported marker itself remained unchanged.

This is a reproducible rejected-open side effect, not a hypothetical migration requirement. Opening an incompatible database should not install this version's objects into it. Changing journal mode before compatibility checks can also modify persistent database settings; the reproduction above establishes the schema changes directly.

**Fix:** inspect an existing database's schema marker before journal-mode changes or DDL. Bootstrap only a demonstrably new/empty supported database, and perform schema creation plus seed initialization in an explicit transaction that is not implicitly committed by `executescript`. Reject an unsupported or unrelated nonempty database without changing its schema/data. Add a regression comparing `sqlite_master` and the marker before/after rejection; retain successful fresh initialization and supported reopen tests.

## Verification and limits

Executed `python3 -B -m unittest discover -s tests -p 'test_cell_journal.py' -v`: **14 methods passed in 0.543 seconds**. This independent run reproduced the adapter's tested process-exit recovery and valid exact-request idempotency paths. It did not duplicate the root task's separate 38-test combined run, benchmark concurrent throughput, simulate power loss, or call any network/API/cluster service. Temporary reproduction databases were cleaned up on completion.

No other demonstrated bug was found in accepted-operation transaction boundaries, the precommit rollback checks, or the lost-acknowledgement retry path within the reviewed scope. An event's logical time remains part of its exact request; retrying with a new time should conflict. The existing acknowledgement tests are local SQL transition tests, not evidence about remote API retries, hidden reasoning, billing, or scientific capability.

## Reviewed source hashes

| File | SHA-256 |
|---|---|
| `prototypes/cell_journal.py` | `4546c1cc1fa99cba0ca4243bb95d6eda715cd4060b53fd3fe2041132366e8aac` |
| `tests/test_cell_journal.py` | `1e9b66343b2dd01f67c81e7137ffcb022c5c3faf37a681cee69f990432dfb386` |
| `docs/cell-journal-prototype-v0.md` | `35d19aec80ca22323d2ab909a5c348104d88a4a3c17984711749604baf20c9aa` |
