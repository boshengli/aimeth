"""Local transactional snapshot/receipt adapter for the offline cell contract.

One SQLite connection per caller; BEGIN IMMEDIATE serializes writers. This is
not an API submission journal, scheduler or developmental policy.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3

from aimeth_runtime.store import Conflict, canonical, digest, identity
from .cell_contract import CellContract, fields


SCHEMA = (
"CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
"""CREATE TABLE IF NOT EXISTS current_state(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 snapshot TEXT NOT NULL, snapshot_hash TEXT NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS receipts(
 seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
 request TEXT NOT NULL, request_hash TEXT NOT NULL,
 result TEXT NOT NULL, previous_snapshot_hash TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
 previous_receipt_hash TEXT NOT NULL, receipt_hash TEXT NOT NULL)""",
"""CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts
 BEGIN SELECT RAISE(ABORT,'immutable receipt'); END""",
"""CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts
 BEGIN SELECT RAISE(ABORT,'immutable receipt'); END""",
"""CREATE TRIGGER IF NOT EXISTS receipts_no_replace BEFORE INSERT ON receipts
 WHEN EXISTS(SELECT 1 FROM receipts WHERE seq=NEW.seq OR event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'immutable receipt'); END""",
)


class CellJournal:
    """Persist accepted transitions only, with exact-request duplicate retrieval.

    Local filesystem only. A fault_hook(stage) is an offline test injection point.
    Callers must use separate instances/connections across threads or processes.
    """
    def __init__(self, path, *, initial=None, fault_hook=None):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self._fault_hook = fault_hook
        try:
            self._check_schema()
            if self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                raise ValueError("Expected local rollback-journal mode")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA fullfsync=ON")
            with self._tx():
                self._check_schema()
                for statement in SCHEMA:
                    self.db.execute(statement)
                schema = self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                if schema is not None and schema[0] != "cell-journal.v0":
                    raise Conflict("Unsupported cell journal schema")
                row = self.db.execute("SELECT snapshot FROM current_state WHERE singleton=1").fetchone()
                if row is None:
                    if initial is None or not isinstance(initial, CellContract):
                        raise ValueError("A new journal requires a seed CellContract")
                    snapshot = initial.to_json()
                    parsed = json.loads(snapshot)
                    if parsed["events"]:
                        raise ValueError("A new journal starts from seeds, not unreceipted transitions")
                    if self.db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]:
                        raise Conflict("Receipts exist without a current snapshot")
                    self.db.execute("INSERT INTO current_state VALUES(1,?,?)", (snapshot, digest(parsed)))
                    self.db.execute("INSERT OR REPLACE INTO metadata VALUES('schema_version','cell-journal.v0')")
                else:
                    if schema is None:
                        raise Conflict("Existing snapshot has no journal schema")
                    if initial is not None:
                        if not isinstance(initial, CellContract):
                            raise ValueError("Initial state must be a CellContract")
                        supplied = json.loads(initial.to_json())
                        if supplied["events"] or canonical(supplied["initial"]) != canonical(json.loads(row[0])["initial"]):
                            raise Conflict("Seed configuration differs from the recorded journal")
                self._verify_locked()
        except BaseException:
            self.db.close()
            raise

    def _check_schema(self):
        """Reject incompatible existing databases before changing their schema."""
        objects = self.db.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        if not objects:
            return
        tables = {row["name"] for row in objects if row["type"] == "table"}
        if "metadata" not in tables:
            raise Conflict("Existing database has no journal schema")
        schema = self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if schema is None or schema[0] != "cell-journal.v0":
            raise Conflict("Unsupported cell journal schema")
        if not {"current_state", "receipts"}.issubset(tables):
            raise Conflict("Existing journal is missing required tables")

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def _fault(self, stage):
        if self._fault_hook is not None:
            self._fault_hook(stage)

    def _load(self):
        row = self.db.execute("SELECT * FROM current_state WHERE singleton=1").fetchone()
        if row is None:
            raise Conflict("Missing current snapshot")
        contract = CellContract.from_json(row["snapshot"])
        if digest(json.loads(contract.to_json())) != row["snapshot_hash"]:
            raise Conflict("Stored snapshot digest mismatch")
        return contract, row["snapshot_hash"]

    @staticmethod
    def _invoke(contract, event_id, request):
        fields(request, ("kind", "inputs", "now"))
        if request["kind"] == "signal":
            fields(request["inputs"], ("signal", "expression"))
            return contract.apply_signal(event_id, now=request["now"], **request["inputs"])
        if request["kind"] == "division":
            fields(request["inputs"], ("parent_id", "child_id", "expected_version", "parent_state_hash"))
            return contract.divide(event_id, now=request["now"], **request["inputs"])
        raise ValueError("Unknown journal operation")

    @staticmethod
    def _receipt_hash(row):
        return digest({key: value for key, value in dict(row).items() if key != "receipt_hash"})

    @staticmethod
    def _response(row, applied):
        return {"event_id": row["event_id"], "sequence": row["seq"],
                "applied": applied, "result": json.loads(row["result"]),
                "receipt_sha256": row["receipt_hash"], "snapshot_sha256": row["snapshot_hash"]}

    def _mutate(self, event_id, request):
        identity(event_id)
        request_text = canonical(request)
        request = json.loads(request_text)
        request_hash = digest(request)
        with self._tx():
            # Verify the receipt-to-snapshot association before acknowledging
            # a stored result or extending the accepted history.
            self._verify_locked()
            existing = self.db.execute("SELECT * FROM receipts WHERE event_id=?", (event_id,)).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash or existing["request"] != request_text:
                    raise Conflict("Event identity reused with different inputs")
                return self._response(existing, False)
            contract, before = self._load()
            result = self._invoke(contract, event_id, request)
            snapshot = contract.to_json()
            parsed = json.loads(snapshot)
            previous = self.db.execute("SELECT seq,receipt_hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
            row = {"seq": previous["seq"] + 1 if previous else 1, "event_id": event_id,
                   "request": request_text, "request_hash": request_hash, "result": canonical(result),
                   "previous_snapshot_hash": before, "snapshot_hash": digest(parsed),
                   "event_hash": parsed["events"][-1]["event_hash"],
                   "previous_receipt_hash": previous["receipt_hash"] if previous else "0" * 64}
            row["receipt_hash"] = self._receipt_hash(row)
            self.db.execute("INSERT INTO receipts VALUES(:seq,:event_id,:request,:request_hash,:result,"
                            ":previous_snapshot_hash,:snapshot_hash,:event_hash,:previous_receipt_hash,:receipt_hash)", row)
            self._fault("after_receipt_insert")
            self.db.execute("UPDATE current_state SET snapshot=?,snapshot_hash=? WHERE singleton=1",
                            (snapshot, row["snapshot_hash"]))
            self._fault("after_snapshot_write")
            self._fault("before_commit")
            response = self._response(row, True)
        # A failure here models a lost acknowledgement after a successful commit.
        self._fault("after_commit")
        return response

    def apply_signal(self, event_id, signal, *, now, expression=None):
        return self._mutate(event_id, {"kind": "signal", "now": now,
                                      "inputs": {"signal": signal, "expression": expression}})

    def divide(self, event_id, *, parent_id, child_id, expected_version, parent_state_hash, now):
        return self._mutate(event_id, {"kind": "division", "now": now,
            "inputs": dict(parent_id=parent_id, child_id=child_id, expected_version=expected_version,
                           parent_state_hash=parent_state_hash)})

    def cell(self, cell_id):
        return self._load()[0].cell(cell_id)

    def state_hash(self, cell_id):
        return self._load()[0].state_hash(cell_id)

    def summary(self):
        contract, snapshot_hash = self._load()
        return {**contract.summary(), "snapshot_sha256": snapshot_hash}

    def verify(self):
        with self._tx():
            return self._verify_locked()

    def _verify_locked(self):
        final, final_hash = self._load()
        parsed = json.loads(final.to_json())
        replay = CellContract(**parsed["initial"])
        receipts = self.db.execute("SELECT * FROM receipts ORDER BY seq").fetchall()
        if len(receipts) != len(parsed["events"]):
            raise Conflict("Receipt count differs from committed contract events")
        previous_receipt_hash = "0" * 64
        for seq, row in enumerate(receipts, 1):
            request = json.loads(row["request"])
            if (row["seq"] != seq or row["request"] != canonical(request)
                    or row["request_hash"] != digest(request)
                    or row["previous_receipt_hash"] != previous_receipt_hash
                    or row["receipt_hash"] != self._receipt_hash(row)
                    or row["previous_snapshot_hash"] != digest(json.loads(replay.to_json()))):
                raise Conflict("Receipt identity or chain mismatch")
            result = self._invoke(replay, row["event_id"], request)
            current = json.loads(replay.to_json())
            if (row["result"] != canonical(result) or row["snapshot_hash"] != digest(current)
                    or row["event_hash"] != current["events"][-1]["event_hash"]):
                raise Conflict("Receipt differs from replayed transition")
            previous_receipt_hash = row["receipt_hash"]
        if replay.to_json() != final.to_json():
            raise Conflict("Receipt replay does not produce committed snapshot")
        return {"valid": True, "receipts": len(receipts), "snapshot_sha256": final_hash,
                "receipt_head_sha256": previous_receipt_hash}
