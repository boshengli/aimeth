import json
from pathlib import Path
import tempfile
import unittest

from tools.analyze_p2_controls import ARMS, analyze


class AnalysisTest(unittest.TestCase):
    def test_paired_analysis_keeps_ungraded_task_at_zero(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run = root / "run"
            graded = run / "graded"
            graded.mkdir(parents=True)
            arc = root / "arc.json"
            bio = root / "bio.json"
            arc.write_text(json.dumps({"tasks": [{"task_id": "a"}, {"task_id": "b"}]}))
            bio.write_text(json.dumps([{"task_id": "c"}, {"task_id": "d"}]))
            for family, kind, ids in (("arc2", "arc", ("a", "b")),
                                      ("callus", "bio", ("c", "d"))):
                for arm in ARMS:
                    rows = []
                    for index, task_id in enumerate(ids):
                        final = ({"solved": bool(index)} if kind == "arc" else
                                 {"pattern_r": 0.4 + index / 10, "cell_r": 0.2 + index / 10})
                        if arm == "vote" and task_id == ids[0]:
                            final = None
                        rows.append({"arm": arm, "kind": kind, "task_id": task_id, "final": final,
                                     "calls_used": 8, "completion_tokens": 100})
                    (graded / f"{family}-{arm}.graded.jsonl").write_text(
                        "".join(json.dumps(row) + "\n" for row in rows))
            result = analyze(run, arc, bio, replicates=200, seed=17)
            vote_arc = next(x for x in result["summary"] if x["family"] == "arc2" and x["arm"] == "vote")
            self.assertEqual(vote_arc["ungraded_or_no_final"], 1)
            self.assertEqual(vote_arc["mean_score_failures_as_zero"], 0.5)
            self.assertEqual(vote_arc["paired_difference_vs_independent"], 0.0)
            self.assertTrue((run / "analysis/paired-summary.json").exists())


if __name__ == "__main__":
    unittest.main()
