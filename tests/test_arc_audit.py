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
                fieldnames = ["task_id", "pooled_pass_at_1"]
                for provider in ("deepseek", "zhipu"):
                    fieldnames.extend(f"{provider}_{field}" for field in (
                        "samples", "pass_at_1", "pass_at_4",
                        "programs_extracted", "execution_ok"))
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                for i in range(400):
                    row = {field: "" if field.endswith("pass_at_1") or field.endswith("pass_at_4")
                           else "0" for field in fieldnames}
                    row["task_id"] = f"task{i:03}"
                    writer.writerow(row)
            (root / "scores.jsonl").write_text("")
            body = {"model": "test", "messages": [
                {"role": "system", "content": "test"},
                {"role": "user", "content": 'Task data:\n{"train":[],"test":[{"input":[[1]]}]}'},
            ]}
            event = {"event": "dispatch_started", "request_id": "deepseek-task000-0",
                     "request_body": body, "reserve_cny": 0.01,
                     "request_sha256": sha256(json.dumps(body, ensure_ascii=False,
                                                          separators=(",", ":")).encode()).hexdigest()}
            path = root / "deepseek-receipts.jsonl"
            path.write_text(json.dumps(event) + "\n")
            zhipu_path = root / "zhipu-receipts.jsonl"
            zhipu_event = {**event, "request_id": "zhipu-task000-0",
                           "request_body": json.loads(json.dumps({**body, "model": "other"}))}
            zhipu_event["request_sha256"] = sha256(json.dumps(
                zhipu_event["request_body"], ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            zhipu_path.write_text(json.dumps(zhipu_event) + "\n")
            self.assertFalse(audit_calibration(root, csv_path, False)["complete"])
            zhipu_event["request_body"]["messages"][0]["content"] = "different"
            zhipu_event["request_sha256"] = sha256(json.dumps(
                zhipu_event["request_body"], ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            zhipu_path.write_text(json.dumps(zhipu_event) + "\n")
            with self.assertRaisesRegex(ValueError, "conditions differ"):
                audit_calibration(root, csv_path, False)
            zhipu_event["request_body"]["messages"][0]["content"] = "test"
            zhipu_event["request_sha256"] = sha256(json.dumps(
                zhipu_event["request_body"], ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            zhipu_path.write_text(json.dumps(zhipu_event) + "\n")
            zhipu_event["request_body"]["messages"][1]["content"] = (
                'Task data:\n{"train":[],"test":[{"input":[[1]],"output":[[2]]}]}')
            zhipu_event["request_sha256"] = sha256(json.dumps(
                zhipu_event["request_body"], ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            zhipu_path.write_text(json.dumps(zhipu_event) + "\n")
            with self.assertRaisesRegex(ValueError, "test output leaked"):
                audit_calibration(root, csv_path, False)
            zhipu_event["request_body"]["messages"][1]["content"] = body["messages"][1]["content"]
            zhipu_event["request_sha256"] = sha256(json.dumps(
                zhipu_event["request_body"], ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            zhipu_path.write_text(json.dumps(zhipu_event) + "\n")
            with csv_path.open(newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
            rows[0]["deepseek_samples"] = "1"
            with csv_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "CSV mismatch"):
                audit_calibration(root, csv_path, False)
            rows[0]["deepseek_samples"] = "0"
            with csv_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            event["request_body"]["model"] = "tampered"
            path.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit_calibration(root, csv_path, False)


if __name__ == "__main__":
    unittest.main()
