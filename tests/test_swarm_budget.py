import concurrent.futures
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from aimeth_swarm.budget import Budget


class SwarmBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "budget.sqlite"
        self.settings = dict(calls=2, input_tokens=20, output_tokens=10,
                             deadline=time.time() + 60)

    def open(self, **overrides):
        budget = Budget(self.path, **{**self.settings, **overrides})
        self.addCleanup(budget.close)
        return budget

    def test_restart_preserves_unknown_reservations_and_identity(self):
        first = self.open()
        self.assertTrue(first.reserve("attempt-1", "population", 10, 5))
        first.close()
        resumed = self.open()
        self.assertFalse(resumed.reserve("attempt-1", "population", 10, 5))
        with self.assertRaisesRegex(ValueError, "identity conflict"):
            resumed.reserve("attempt-1", "other", 10, 5)
        resumed.reserve("attempt-2", "population", 10, 5)
        resumed.settle("attempt-2", {"usage": None, "error": "timeout"})
        with self.assertRaisesRegex(ValueError, "budget"):
            resumed.reserve("attempt-3", "population", 1, 1)
        summary = resumed.summary()
        self.assertEqual(summary["reserved_calls"], 2)
        self.assertEqual(summary["unknown_usage_attempts"], 2)
        self.assertEqual(summary["pending_attempts"], 1)
        self.assertEqual(summary["reserved_input_tokens"], 20)
        self.assertEqual(summary["reserved_output_tokens"], 10)

    def test_settlement_is_idempotent_and_does_not_refund(self):
        budget = self.open()
        budget.reserve("a", "run", 20, 10)
        receipt = {"usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}, "error": None}
        budget.settle("a", receipt)
        budget.settle("a", {"error": None, "usage": receipt["usage"]})
        with self.assertRaisesRegex(ValueError, "Conflicting settlement"):
            budget.settle("a", {"usage": None, "error": "timeout"})
        with self.assertRaisesRegex(ValueError, "Unknown reservation"):
            budget.settle("missing", receipt)
        summary = budget.summary()
        self.assertEqual(summary["settled_attempts"], 1)
        self.assertEqual(summary["known_usage_attempts"], 1)
        self.assertEqual(summary["known_total_tokens"], 5)
        self.assertEqual(summary["known_input_tokens"], 3)
        self.assertEqual(summary["known_output_tokens"], 2)
        self.assertEqual(summary["reserved_input_tokens"], 20)
        with self.assertRaisesRegex(ValueError, "budget"):
            budget.reserve("b", "run", 1, 1)

    def test_settings_are_frozen_across_resume_and_public_copy(self):
        budget = self.open()
        budget.settings["calls"] = 100
        self.assertEqual(budget.settings["calls"], 2)
        for field, value in (("calls", 3), ("input_tokens", 21), ("output_tokens", 11),
                             ("deadline", self.settings["deadline"] + 1)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Frozen"):
                Budget(self.path, **{**self.settings, field: value})
        self.open()

    def test_two_owners_cannot_over_admit(self):
        self.open(calls=1)
        ready = threading.Barrier(2)

        def compete(token):
            budget = Budget(self.path, **{**self.settings, "calls": 1})
            try:
                ready.wait(timeout=5)
                try:
                    return budget.reserve(token, "run", 10, 5)
                except ValueError as exc:
                    self.assertIn("budget", str(exc))
                    return False
            finally:
                budget.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, ("a", "b")))
        self.assertEqual(sorted(results), [False, True])
        summary = self.open(calls=1).summary()
        self.assertEqual(summary["reserved_calls"], 1)
        self.assertEqual(summary["reserved_input_tokens"], 10)
        self.assertEqual(summary["reserved_output_tokens"], 5)

    def test_each_cap_and_deadline_reject_without_consuming(self):
        budget = self.open()
        for inputs, outputs in ((21, 1), (0, 11)):
            with self.assertRaisesRegex(ValueError, "budget"):
                budget.reserve("a", "run", inputs, outputs)
        with patch("aimeth_swarm.budget.time.time", return_value=self.settings["deadline"]):
            with self.assertRaisesRegex(ValueError, "deadline"):
                budget.reserve("a", "run", 1, 1)
        self.assertEqual(budget.summary()["reserved_calls"], 0)
        self.assertTrue(budget.reserve("a", "run", 1, 1))
        with patch("aimeth_swarm.budget.time.time", return_value=self.settings["deadline"] + 1):
            self.assertFalse(budget.reserve("a", "run", 1, 1))

    def test_malformed_usage_stays_unknown_and_backup_is_complete(self):
        budget = self.open()
        budget.reserve("a", "run", 1, 1)
        budget.settle("a", {"usage": {"total_tokens": True, "prompt_tokens": -1,
                                      "completion_tokens": "3"}, "error": None})
        snapshot = Path(self.tmp.name) / "snapshot.sqlite"
        with sqlite3.connect(snapshot) as target:
            budget.db.backup(target)
        recovered = Budget(snapshot, **self.settings)
        self.addCleanup(recovered.close)
        self.assertEqual(recovered.summary(), budget.summary())
        self.assertEqual(recovered.summary()["unknown_usage_attempts"], 1)
        self.assertEqual(recovered.summary()["known_total_tokens"], 0)

    def test_invalid_parameters_and_sensitive_receipt_fields_rejected(self):
        for key, value in (("calls", True), ("input_tokens", 0), ("output_tokens", 1.2),
                           ("deadline", float("nan"))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Budget(self.path, **{**self.settings, key: value})
        budget = self.open()
        budget.reserve("a", "run", 0, 1)
        with self.assertRaisesRegex(ValueError, "only usage and error"):
            budget.settle("a", {"usage": None, "authorization": "not-a-real-key"})
        self.assertEqual(budget.summary()["pending_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
