"""Checks that the independent ARC audit catches a changed request body."""

import csv
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aimeth_arc.audit import audit_calibration


class ArcAuditTests(unittest.TestCase):
    def test_request_hash_must_match_receipt(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            csv_path = root / "scores.csv"
            with csv_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["task_id"])
                writer.writeheader()
                writer.writerows({"task_id": f"task{i:03}"} for i in range(400))
            (root / "scores.jsonl").write_text("")
            body = {"model": "test", "messages": []}
            event = {"event": "dispatch_started", "request_id": "deepseek-task000-0",
                     "request_body": body, "reserve_cny": 0.01,
                     "request_sha256": sha256(json.dumps(body, ensure_ascii=False,
                                                          separators=(",", ":")).encode()).hexdigest()}
            path = root / "deepseek-receipts.jsonl"
            path.write_text(json.dumps(event) + "\n")
            (root / "zhipu-receipts.jsonl").write_text("")
            self.assertFalse(audit_calibration(root, csv_path, False)["complete"])
            event["request_body"]["model"] = "tampered"
            path.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit_calibration(root, csv_path, False)


if __name__ == "__main__":
    unittest.main()
