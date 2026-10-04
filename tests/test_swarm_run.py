import contextlib
import io
import json
from types import ModuleType, SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aimeth_runtime.store import Store
from aimeth_swarm.design import default_config
from aimeth_swarm.run import execute, token_counter, verify_imports, wire_call


class SwarmRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "local"
        self.output = Path(self.tmp.name) / "output"
        self.config = {**default_config(), "population_id": "swarm-run-fixture",
                       "groups": 1, "workers_per_group": 4, "observers_per_group": 2,
                       "cycles": 2, "max_inflight": 2, "max_output_tokens": 64,
                       "wall_seconds": 60}

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()), patch("aimeth_swarm.run.signal.signal"):
            return execute(self.config, self.root, self.output, synthetic=True)

    def test_completed_resume_does_not_redispatch_or_increase_reservations(self):
        first = self.execute()
        self.assertEqual(first["finished_phases"], 8)
        self.assertFalse(first["halted"])
        self.assertEqual(first["budget"]["reserved_calls"], 16)
        with patch("aimeth_swarm.run.wire_call", side_effect=AssertionError("Completed call was redispatched")):
            resumed = self.execute()
        self.assertEqual(resumed["budget"], first["budget"])
        self.assertEqual(resumed["final_global_candidates"], first["final_global_candidates"])

    def test_cross_phase_source_hash_tampering_is_rejected(self):
        self.execute()
        with Store(self.root / "journal.sqlite") as store:
            row = store.db.execute("SELECT manifest FROM runs WHERE run_id=?",
                                   (self.config["population_id"] + ".c0.observer.b0000",)).fetchone()
            manifest = json.loads(row["manifest"])
            verify_imports(store, manifest)
            source = next(iter(manifest["lineage_imports"].values()))[0]
            source["source_hash"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "cross-phase source evidence"):
                verify_imports(store, manifest)

    def test_failed_worker_is_preserved_and_observer_receives_missing_source(self):
        self.config["cycles"] = 1
        observed = []

        def transport(claim, config, synthetic):
            if claim["agent_id"] == "g000.w000":
                return {"error": {"category": "fixture_timeout", "http_status": None}}
            if claim["agent_id"] == "g000.o00":
                observed.append(json.loads(claim["request"]["messages"][-1]["content"].split("\n", 1)[1]))
            return wire_call(claim, config, synthetic)

        with patch("aimeth_swarm.run.wire_call", side_effect=transport):
            summary = self.execute()
        self.assertFalse(summary["halted"])
        self.assertEqual(summary["finished_phases"], 4)
        self.assertEqual(summary["budget"]["reserved_calls"], 8)
        self.assertEqual(summary["budget"]["unknown_usage_attempts"], 1)
        self.assertEqual(len(observed), 1)
        failed = next(item for item in observed[0]["incoming"] if item["agent_id"] == "g000.w000")
        self.assertEqual(failed["execution_status"], "failed")
        self.assertIn("No usable content", failed["content"])
        self.assertTrue(failed["source_event"])
        self.assertEqual(len(failed["source_hash"]), 64)
        with Store(self.root / "journal.sqlite") as store:
            receipt = store.db.execute("SELECT payload FROM events WHERE event_id=?",
                                       (failed["source_event"],)).fetchone()
            self.assertEqual(json.loads(receipt["payload"])["receipt"]["error"]["category"], "fixture_timeout")
        self.assertTrue(summary["final_global_candidates"])
        self.assertEqual(summary["mathematical_verification"], "not performed; all candidates unverified")

    def test_deepseek_v4_without_hf_template_uses_frozen_sglang_encoder(self):
        messages = [{"role": "user", "content": "test prompt"}]
        calls = []
        tokenizer = SimpleNamespace(chat_template=None,
                                    encode=lambda text, add_special_tokens=False: [1, 2, 3, 4])
        transformers = ModuleType("transformers")
        transformers.AutoTokenizer = SimpleNamespace(from_pretrained=lambda *a, **k: tokenizer)
        encoder = ModuleType("sglang.srt.entrypoints.openai.encoding_dsv4")
        def encode_messages(actual_messages, *, thinking_mode):
            calls.append((actual_messages, thinking_mode))
            return "server-equivalent rendered prompt"
        encoder.encode_messages = encode_messages
        modules = {
            "transformers": transformers,
            "sglang": ModuleType("sglang"),
            "sglang.srt": ModuleType("sglang.srt"),
            "sglang.srt.entrypoints": ModuleType("sglang.srt.entrypoints"),
            "sglang.srt.entrypoints.openai": ModuleType("sglang.srt.entrypoints.openai"),
            "sglang.srt.entrypoints.openai.encoding_dsv4": encoder,
        }
        config = {"token_count_encoder": "sglang-dsv4-native-v1", "thinking_mode": "thinking"}
        with patch.dict("sys.modules", modules):
            count = token_counter("/model", False, config)
        self.assertEqual(count(messages), 4)
        self.assertEqual(calls, [(messages, "thinking")])

    def test_missing_template_without_frozen_native_encoder_fails_before_dispatch(self):
        tokenizer = SimpleNamespace(chat_template=None)
        transformers = ModuleType("transformers")
        transformers.AutoTokenizer = SimpleNamespace(from_pretrained=lambda *a, **k: tokenizer)
        with patch.dict("sys.modules", {"transformers": transformers}):
            with self.assertRaisesRegex(ValueError, "no Hugging Face chat_template"):
                token_counter("/model", False, {"token_count_encoder": "huggingface-chat-template"})


if __name__ == "__main__":
    unittest.main()
