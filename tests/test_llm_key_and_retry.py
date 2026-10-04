import os
import tempfile
import unittest
from unittest.mock import patch

from aimeth_bio.llm_client import _key


class NoWaitLimiter:
    def __init__(self, *args):
        self.outcomes = []

    def acquire(self):
        return None

    def release(self, outcome):
        self.outcomes.append(outcome)


class KeyAndRetryTest(unittest.TestCase):
    def test_environment_key_takes_precedence(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only-secret"}):
            self.assertEqual(_key("DEEPSEEK_API_KEY"), "test-only-secret")

    def test_deepseek_429_is_retried_but_unknown_is_not(self):
        from aimeth_rt import llm as module

        rate = {"ok": False, "http_status": 429, "error": '{"error":{"code":"rate_limit"}}'}
        success = {"ok": True, "receipt_id": "ok", "usage": {"prompt_tokens": 1,
                                                                      "completion_tokens": 1}}
        with tempfile.TemporaryDirectory() as td, \
                patch.object(module, "Limiter", NoWaitLimiter), \
                patch.object(module, "chat", side_effect=[rate, success]) as chat:
            client = module.LLM(td, start=1, cap=1)
            result = client.call("deepseek", "deepseek-flash", [], workload="test", max_tokens=4)
            self.assertTrue(result["ok"])
            self.assertEqual(chat.call_count, 2)
            self.assertEqual(client.stats["rate_limited"], 1)

        with tempfile.TemporaryDirectory() as td, \
                patch.object(module, "Limiter", NoWaitLimiter), \
                patch.object(module, "chat", return_value={"ok": False, "outcome": "unknown"}) as chat:
            client = module.LLM(td, start=1, cap=1)
            client.call("deepseek", "deepseek-flash", [], workload="test", max_tokens=4)
            self.assertEqual(chat.call_count, 1)
            self.assertEqual(client.stats["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
