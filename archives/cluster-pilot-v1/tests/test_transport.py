from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from aimeth_runtime import Store
from aimeth_runtime.runner import TransportFailure, demo_manifest, http_response, mock_response, work_one


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append({"body": body, "authorization_present": bool(self.headers.get("Authorization")), "path":self.path})
        status = int(self.path[1:]) if self.path[1:].isdigit() else 200
        self.send_response(status)
        if status == 302: self.send_header("Location", "/redirect-target")
        self.end_headers()
        if self.path == "/invalid": content = b"not-json"
        elif self.path == "/large": content = b"x" * (256*1024+1)
        elif self.path == "/nan": content = b'{"result":NaN}'
        else: content = json.dumps(mock_response({"step_id":"fixture"})).encode()
        self.wfile.write(content)


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1",0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def call(self,path):
        return http_response({"request":{"model":"mock","seed":914,"messages":[{"role":"user","content":"synthetic fixture"}]}},
                             {"endpoint":self.endpoint+path,"timeout_seconds":2})

    def test_http_request_sends_seed_and_env_credential_without_journaling_it(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{"AIMETH_API_KEY":"test-fixture-never-a-real-key"}):
            with Store(Path(temp)/"http.sqlite") as store:
                config=demo_manifest(1,1); config["transport"]={"kind":"openai","endpoint":self.endpoint+"/ok","timeout_seconds":2}
                store.create_run("http",config); store.enqueue_round("http",0)
                with self.assertRaises(ValueError): work_one(store,"http","worker")
                self.assertEqual(store.status("http")["attempts"],0)
                self.assertTrue(work_one(store,"http","worker",allow_model_calls=True)["accepted"])
                self.assertIsInstance(Handler.calls[-1]["body"]["seed"],int)
                self.assertTrue(Handler.calls[-1]["authorization_present"])
                self.assertNotIn("test-fixture-never-a-real-key",json.dumps(list(store.events("http"))))
                store.verify("http")

    def test_http_retryable_and_terminal_statuses(self):
        for status,retryable in [(400,False),(401,False),(408,True),(429,True),(500,True),(503,True)]:
            with self.subTest(status=status), self.assertRaises(TransportFailure) as result:
                self.call("/"+str(status))
            self.assertEqual(result.exception.retryable,retryable)
            self.assertEqual(result.exception.details["http_status"],status)

    def test_redirect_is_not_followed(self):
        before=len(Handler.calls)
        with self.assertRaises(TransportFailure): self.call("/302")
        self.assertEqual(len(Handler.calls),before+1)

    def test_invalid_oversized_nonfinite_responses(self):
        for path,category in [("/invalid","invalid_json"),("/large","response_exceeds_256_KiB"),("/nan","invalid_json")]:
            with self.subTest(path=path), self.assertRaises(TransportFailure) as result:
                self.call(path)
            self.assertEqual(result.exception.details["category"],category)

    def test_timeout_classification(self):
        with patch("aimeth_runtime.runner.request.OpenerDirector.open",side_effect=TimeoutError), self.assertRaises(TransportFailure) as result:
            self.call("/ok")
        self.assertTrue(result.exception.retryable)
        self.assertEqual(result.exception.details["category"],"network_or_timeout")


if __name__ == "__main__": unittest.main()
