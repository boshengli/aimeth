import os
import json
from pathlib import Path
import select
import subprocess
import sys
import threading
import tempfile
import time
import unittest
from unittest.mock import patch

from aimeth_rt.remote_eval import RemoteEvalClient, _REMOTE_PROXY


class RemoteEvalTest(unittest.TestCase):
    def test_proxy_script_is_valid_and_never_receives_model_credential(self):
        compile(_REMOTE_PROXY, "remote_eval_proxy", "exec")
        self.assertNotIn("DEEPSEEK_API_KEY", _REMOTE_PROXY)
        self.assertIn("pending", _REMOTE_PROXY)
        self.assertIn("done", _REMOTE_PROXY)

    def test_proxy_streams_completed_request_while_stdin_remains_open(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("pending", "done", "running", "private"):
                (root / name).mkdir()
            proc = subprocess.Popen([sys.executable, "-c", _REMOTE_PROXY, str(root)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, bufsize=1)

            def evaluator():
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    for pending in (root / "pending").glob("*.json"):
                        request = json.loads(pending.read_text())
                        (root / "done" / pending.name).write_text(json.dumps(
                            {"status": "ok", "train_frac": 1.0}))
                        pending.unlink()
                        return request
                    time.sleep(0.01)
                raise AssertionError("proxy did not enqueue an evaluation request")

            worker = threading.Thread(target=evaluator, daemon=True)
            worker.start()
            try:
                proc.stdin.write(json.dumps({"request_id": "r1", "kind": "arc",
                                            "task_id": "deadbeef", "program": ""}) + "\n")
                proc.stdin.flush()
                readable, _, _ = select.select([proc.stdout], [], [], 3)
                self.assertTrue(readable, "proxy held the result until the SSH input stream closed")
                result = json.loads(proc.stdout.readline())
                self.assertEqual(result["request_id"], "r1")
                self.assertEqual(result["result"]["status"], "ok")
            finally:
                proc.stdin.close()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait(timeout=3)
                worker.join(timeout=1)

    def test_remote_client_uses_one_session_for_visible_run_and_aggregate(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = Path(td) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "ssh"
            fake.write_text("""#!/usr/bin/env python3
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    if req['kind'] == 'aggregate':
        result = {'status':'ok','eval_id':'aggregate','contributor_eval_ids':req['eval_ids'],
                  'agreement_by_test':[2], 'source_best_visible_score':0.5}
    else:
        result = {'status':'ok','eval_id':'e1','train_frac':0.5,'train_all':False}
    print(json.dumps({'request_id':req['request_id'],'result':result}), flush=True)
""")
            fake.chmod(0o755)
            with patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}):
                client = RemoteEvalClient("libs@host", "/private/evalq")
                try:
                    run_result = client.run("arc", "deadbeef", "def transform(g): return g", arc_dir="/allowed/arc")
                    agg_result = client.aggregate("arc", "deadbeef", ["e1", "e2"], "vote")
                finally:
                    client.close()
            self.assertEqual(run_result["eval_id"], "e1")
            self.assertEqual(run_result["train_frac"], 0.5)
            self.assertEqual(agg_result["eval_id"], "aggregate")
            self.assertNotIn("test_preds", agg_result)


if __name__ == "__main__":
    unittest.main()
