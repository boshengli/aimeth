import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aimeth_rt.remote_eval import RemoteEvalClient, _REMOTE_PROXY


class RemoteEvalTest(unittest.TestCase):
    def test_proxy_script_is_valid_and_never_receives_model_credential(self):
        compile(_REMOTE_PROXY, "remote_eval_proxy", "exec")
        self.assertNotIn("DEEPSEEK_API_KEY", _REMOTE_PROXY)
        self.assertIn("pending", _REMOTE_PROXY)
        self.assertIn("done", _REMOTE_PROXY)

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
