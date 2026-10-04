"""Transactional local failure tests; all databases live in temporary directories."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from aimeth_runtime.store import Conflict
from prototypes.cell_contract import CellContract
from prototypes.cell_journal import CellJournal


def seed_state():
    return CellContract(modules=["construct", "check"], seeds=[
        {"cell_id": name, "expression": {"construct": 1, "check": 0}, "memory": {}}
        for name in ("a", "b")], edges=[["a", "b"]],
        limits={"max_population": 3, "max_units": 5, "max_events": 5,
                "max_neighbours": 2, "max_payload_bytes": 256})


def message(**changes):
    return {"message_id": "m1", "sender": "a", "receiver": "b", "sender_version": 0,
            "receiver_version": 0, "kind": "candidate", "payload": {"statement": "fixture"},
            "parent_message_id": None, "parent_message_hash": None,
            "created_tick": 0, "expires_tick": 5, **changes}


class CellJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "cells.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def test_committed_signal_survives_close_and_verified_reopen(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            receipt = journal.apply_signal("e1", message(), now=1)
            expected = journal.summary()
            self.assertTrue(receipt["applied"])
        with CellJournal(self.path) as journal:
            self.assertEqual(journal.summary(), expected)
            self.assertEqual(journal.cell("b")["state_version"], 1)
            self.assertEqual(journal.verify()["receipts"], 1)
            self.assertEqual(receipt["snapshot_sha256"], expected["snapshot_sha256"])

    def test_identical_duplicate_returns_receipt_without_reapplication(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            first = journal.apply_signal("e1", message(), now=1)
            second = journal.apply_signal("e1", message(), now=1)
            self.assertFalse(second["applied"])
            self.assertEqual({**first, "applied": False}, second)
            self.assertEqual(journal.summary()["units_used"], 1)
            self.assertEqual(journal.verify()["receipts"], 1)

    def test_older_duplicate_returns_original_receipt_after_later_commits(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            first = journal.apply_signal("e1", message(), now=1)
            journal.apply_signal("e2", message(message_id="m2", receiver_version=1,
                                                created_tick=1), now=2)
            duplicate = journal.apply_signal("e1", message(), now=1)
            self.assertEqual(duplicate, {**first, "applied": False})
            self.assertEqual(duplicate["result"]["state_version"], 1)
            self.assertEqual(journal.cell("b")["state_version"], 2)
            self.assertEqual(journal.summary()["units_used"], 2)
            self.assertEqual(journal.verify()["receipts"], 2)

    def test_reused_event_identity_with_changed_inputs_conflicts(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            before = journal.summary()
            with self.assertRaises(Conflict):
                journal.apply_signal("e1", message(payload={"statement": "changed"}), now=1)
            self.assertEqual(journal.summary(), before)

    def test_stale_version_is_rejected_without_receipt_or_state_change(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            before = journal.summary()
            with self.assertRaises(Conflict):
                journal.apply_signal("e2", message(message_id="m2", created_tick=1), now=2)
            self.assertEqual(journal.summary(), before)
            self.assertEqual(journal.verify()["receipts"], 1)

    def test_division_lineage_and_parent_hash_persist(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.divide("birth", parent_id="a", child_id="child", expected_version=0,
                           parent_state_hash=journal.state_hash("a"), now=1)
        with CellJournal(self.path) as journal:
            self.assertEqual(journal.cell("child")["parent_id"], "a")
            self.assertEqual(journal.cell("a")["state_version"], 1)
            self.assertEqual(journal.summary()["units_used"], 2)
            journal.apply_signal("e", message(sender="a", receiver="child", sender_version=1,
                                               created_tick=1), now=2)
            self.assertTrue(journal.verify()["valid"])

    def test_exceptions_at_all_precommit_boundaries_roll_back_both_records(self):
        for stage in ("after_receipt_insert", "after_snapshot_write", "before_commit"):
            with self.subTest(stage=stage):
                path = Path(self.temp.name) / (stage + ".sqlite")
                def fault(actual):
                    if actual == stage:
                        raise RuntimeError("injected precommit exception")
                with CellJournal(path, initial=seed_state(), fault_hook=fault) as journal:
                    with self.assertRaises(RuntimeError):
                        journal.apply_signal("e1", message(), now=1)
                    self.assertEqual(journal.summary()["units_used"], 0)
                    self.assertEqual(journal.verify()["receipts"], 0)
                with CellJournal(path) as journal:
                    self.assertTrue(journal.apply_signal("e1", message(), now=1)["applied"])
                    self.assertEqual(journal.verify()["receipts"], 1)

    def test_lost_acknowledgement_after_commit_is_resolved_without_duplicate(self):
        def fault(stage):
            if stage == "after_commit":
                raise RuntimeError("lost acknowledgement")
        with CellJournal(self.path, initial=seed_state(), fault_hook=fault) as journal:
            with self.assertRaises(RuntimeError):
                journal.apply_signal("e1", message(), now=1)
        with CellJournal(self.path) as journal:
            self.assertEqual(journal.verify()["receipts"], 1)
            self.assertFalse(journal.apply_signal("e1", message(), now=1)["applied"])
            self.assertEqual(journal.summary()["units_used"], 1)

    def test_process_exit_before_and_after_commit_preserves_atomicity(self):
        code = """
import json, os, sys
from prototypes.cell_journal import CellJournal
def crash(stage):
    if stage == sys.argv[2]:
        os._exit(23)
with CellJournal(sys.argv[1], fault_hook=crash) as journal:
    journal.apply_signal('e1', json.loads(sys.argv[3]), now=1)
"""
        for stage, count in (("after_receipt_insert", 0), ("after_snapshot_write", 0), ("after_commit", 1)):
            with self.subTest(stage=stage):
                path = Path(self.temp.name) / ("process-" + stage + ".sqlite")
                with CellJournal(path, initial=seed_state()):
                    pass
                result = subprocess.run([sys.executable, "-c", code, str(path), stage, json.dumps(message())],
                                        cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 23, result.stderr.decode())
                with CellJournal(path) as journal:
                    self.assertEqual(journal.verify()["receipts"], count)
                    self.assertEqual(journal.summary()["units_used"], count)
                    self.assertEqual(journal.apply_signal("e1", message(), now=1)["applied"], count == 0)
                    self.assertEqual(journal.verify()["receipts"], 1)

    def test_two_connections_use_latest_committed_state(self):
        with CellJournal(self.path, initial=seed_state()) as first, CellJournal(self.path) as second:
            first.apply_signal("e1", message(), now=1)
            with self.assertRaises(Conflict):
                second.apply_signal("e2", message(message_id="m2", created_tick=1), now=2)
            second.apply_signal("e2", message(message_id="m2", receiver_version=1, created_tick=1), now=2)
            self.assertEqual(first.verify()["receipts"], 2)
            self.assertEqual(first.cell("b")["state_version"], 2)

    def test_receipts_are_immutable_through_normal_sql(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            for sql in ("UPDATE receipts SET result='{}'", "DELETE FROM receipts"):
                with self.assertRaises(sqlite3.IntegrityError):
                    journal.db.execute(sql)
            self.assertTrue(journal.verify()["valid"])

    def test_replace_cannot_overwrite_existing_sequence_or_event_identity(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            original = dict(journal.db.execute("SELECT * FROM receipts").fetchone())
            before = journal.summary()
            for changes in ({}, {"seq": 2}, {"event_id": "other"}):
                with self.subTest(changes=changes):
                    row = {**original, **changes, "result": '{"state_version":999}'}
                    columns = list(row)
                    sql = "INSERT OR REPLACE INTO receipts (" + ",".join(columns) + ") VALUES ("
                    sql += ",".join("?" for _ in columns) + ")"
                    with self.assertRaises(sqlite3.IntegrityError):
                        journal.db.execute(sql, [row[column] for column in columns])
                    self.assertEqual(dict(journal.db.execute("SELECT * FROM receipts").fetchone()), original)
                    self.assertEqual(journal.summary(), before)
            self.assertTrue(journal.verify()["valid"])

    def test_live_duplicate_and_new_transition_reject_damaged_receipt(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            before = journal.summary()
            # Model corruption after open, deliberately bypassing immutability.
            journal.db.execute("DROP TRIGGER receipts_no_update")
            journal.db.execute("UPDATE receipts SET result=?", ('{"state_version":999}',))
            with self.assertRaises(Conflict):
                journal.apply_signal("e1", message(), now=1)
            with self.assertRaises(Conflict):
                journal.apply_signal("e2", message(message_id="m2", receiver_version=1,
                                                    created_tick=1), now=2)
            self.assertEqual(journal.summary(), before)
            self.assertEqual(journal.db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 1)

    def test_corrupt_snapshot_prevents_startup(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            journal.db.execute("UPDATE current_state SET snapshot_hash=?", ("0" * 64,))
        with self.assertRaises(Conflict):
            CellJournal(self.path)

    def test_receipt_chain_damage_prevents_startup(self):
        with CellJournal(self.path, initial=seed_state()) as journal:
            journal.apply_signal("e1", message(), now=1)
            # Deliberately bypass the SQL immutability trigger to model file corruption.
            journal.db.execute("DROP TRIGGER receipts_no_update")
            journal.db.execute("UPDATE receipts SET receipt_hash=?", ("0" * 64,))
        with self.assertRaises(Conflict):
            CellJournal(self.path)

    def test_changed_seed_or_unreceipted_initial_history_is_rejected(self):
        with CellJournal(self.path, initial=seed_state()):
            pass
        initial = seed_state()
        initial.apply_signal("outside", message(), now=1)
        with self.assertRaises(Conflict):
            CellJournal(self.path, initial=initial)
        with self.assertRaises(ValueError):
            CellJournal(Path(self.temp.name) / "unreceipted.sqlite", initial=initial)

    def test_new_store_requires_explicit_initial_state(self):
        with self.assertRaises(ValueError):
            CellJournal(self.path)

    def test_failed_initialization_rolls_back_schema_and_can_retry(self):
        with self.assertRaises(ValueError):
            CellJournal(self.path)
        with sqlite3.connect(str(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)
        with CellJournal(self.path, initial=seed_state()) as journal:
            self.assertEqual(journal.verify()["receipts"], 0)

    def test_unsupported_schema_rejection_does_not_change_database(self):
        with sqlite3.connect(str(self.path)) as db:
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("INSERT INTO metadata VALUES('schema_version','cell-journal.v999')")
            db.commit()
            before = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
            before_rows = db.execute("SELECT * FROM metadata").fetchall()
            before_mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        with self.assertRaises(Conflict):
            CellJournal(self.path)
        with sqlite3.connect(str(self.path)) as db:
            self.assertEqual(db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall(), before)
            self.assertEqual(db.execute("SELECT * FROM metadata").fetchall(), before_rows)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], before_mode)


if __name__ == "__main__":
    unittest.main()
