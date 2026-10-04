"""Check the post-hoc truncation denominators and pilot majority rule."""

import csv
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from aimeth_arc.sensitivity import summarize_truncation


class ArcSensitivityTest(unittest.TestCase):
    def test_nontruncated_denominator_and_strict_failure_majority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "calibration.csv"
            with csv_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["task_id"])
                writer.writeheader()
                writer.writerows({"task_id": f"task-{i:03}"} for i in range(400))
            pilot_path = root / "pilot.json"
            pilot_path.write_text(json.dumps({
                "pilot": [{"task_id": f"task-{i:03}"} for i in range(40)],
                "calibration_csv_sha256": sha256(csv_path.read_bytes()).hexdigest()}))
            scores_path = root / "scores.jsonl"
            with scores_path.open("w") as stream:
                for i in range(400):
                    for provider in ("deepseek", "zhipu"):
                        for sample in range(4):
                            # Task 0: five failed length samples, three successful stops.
                            # Task 1: four failed length samples, four failed stops (tie).
                            length = (i == 0 and (provider == "deepseek" or sample == 0)) or (i == 1 and provider == "deepseek")
                            success = i == 0 and not length
                            stream.write(json.dumps({
                                "request_id": f"{provider}-task-{i:03}-{sample}",
                                "provider": provider, "task_id": f"task-{i:03}",
                                "sample": sample, "finish_reason": "length" if length else "stop",
                                "test_success": success}) + "\n")
            result = summarize_truncation(scores_path, pilot_path, csv_path,
                                           root / "sensitivity.json", root / "sensitivity.csv")
            self.assertEqual(result["providers"]["deepseek"]["length_count"], 8)
            self.assertEqual(result["providers"]["zhipu"]["length_count"], 1)
            self.assertEqual(result["providers"]["zhipu"]["nontruncated_successes"], 3)
            self.assertEqual(result["providers"]["zhipu"]["nontruncated_pass_rate"], 3 / 1599)
            self.assertEqual(result["selected_pilot_length_majority_failure_count"], 1)
            with (root / "sensitivity.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["pooled_length_failed_count"], "5")
            self.assertEqual(rows[0]["length_majority_of_failures"], "True")
            self.assertEqual(rows[1]["length_majority_of_failures"], "False")


if __name__ == "__main__":
    unittest.main()
