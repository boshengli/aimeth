import json
import unittest

from aimeth_rt.control_arms import ARMS, Budget, BudgetLedger, run_control_arm


TASK = {"train": [{"input": [[1]], "output": [[2]]}],
        "test": [{"input": [[3]], "output": [[9]]}]}
PROMPT = [{"role": "system", "content": "Callus task"},
          {"role": "user", "content": "Only authorized visible measurements"}]
PROGRAM = "def transform(grid):\n    return [[x + 1 for x in row] for row in grid]"


class FakeLLM:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def call(self, provider, model, messages, *, workload, max_tokens, extra=None, tag=None):
        record = {"provider": provider, "model": model, "messages": messages,
                  "workload": workload, "max_tokens": max_tokens, "tag": tag or {}}
        self.calls.append(record)
        if self.response:
            return dict(self.response)
        if "orchestrator_plan" in workload:
            content = json.dumps({"plans": ["count and recolor", "preserve geometry",
                                             "compare object size", "check symmetry"]})
        elif "orchestrator_assign" in workload:
            content = "Revise the leading visible-check program."
        else:
            content = PROGRAM
        return {"ok": True, "outcome": "ok", "receipt_id": f"r{len(self.calls)}",
                "content": content, "finish_reason": "stop",
                "usage": {"completion_tokens": min(3, max_tokens), "prompt_tokens": 5}}


class FakeEval:
    def __init__(self, perfect=False):
        self.calls = []
        self.perfect = perfect

    def run(self, kind, task_id, program, **kwargs):
        self.calls.append((kind, task_id, program))
        score = 1.0 if self.perfect else 0.5
        return {"status": "ok", "eval_id": f"e{len(self.calls)}", "train_frac": score,
                "train_all": self.perfect,
                "train": [{"ok": self.perfect, "error": None, "got": [[2]]}]}

    def aggregate(self, kind, task_id, eval_ids, mode):
        return {"status": "ok", "eval_id": "aggregate-1", "contributor_eval_ids": eval_ids,
                "agreement_by_test": [len(eval_ids)], "source_best_visible_score": 0.5,
                "source_mean_visible_score": 0.5}


def run(arm, *, perfect=False, budget=None, seed=2, model_max_tokens=16):
    llm, ev = FakeLLM(), FakeEval(perfect)
    result = run_control_arm(
        arm, "arc", "task-1", TASK, PROMPT, llm, ev,
        budget or Budget(8, 32_768), provider="deepseek", model="deepseek-flash",
        model_max_tokens=model_max_tokens, extra={"reasoning_effort": "low"},
        seed=seed, k=4, m=3, tag={"run": "test"})
    return result, llm, ev


class ControlArmsTest(unittest.TestCase):
    def test_all_arms_share_one_model_and_obey_calls_and_completion_token_caps(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                budget = Budget(8, 32_768)
                result, llm, _ = run(arm, budget=budget)
                self.assertLessEqual(result["calls_used"], budget.calls)
                self.assertLessEqual(result["completion_reasoning_tokens_used"], budget.tokens)
                self.assertEqual({c["model"] for c in llm.calls}, {"deepseek-flash"})
                self.assertTrue(llm.calls)
                self.assertTrue(all(c["max_tokens"] <= 4_096 for c in llm.calls))
                self.assertTrue(all(c["tag"]["task_id"] == "task-1" for c in llm.calls))

    def test_every_agent_prompt_excludes_arc_test_output(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                _, llm, _ = run(arm)
                joined = "\n".join(json.dumps(c["messages"]) for c in llm.calls)
                self.assertNotIn('"output": [[9]]', joined)
                self.assertNotIn('"output":[[9]]', joined)

    def test_single_long_uses_one_call_capped_by_model_output_limit(self):
        result, llm, _ = run("single_long", budget=Budget(8, 262_144), model_max_tokens=131_072)
        self.assertEqual(result["calls_used"], 1)
        self.assertEqual(llm.calls[0]["max_tokens"], 131_072)

    def test_train_perfect_stops_arc_sampling(self):
        for arm in ARMS:
            with self.subTest(arm=arm):
                result, llm, _ = run(arm, perfect=True)
                self.assertEqual(result["stop_reason"], "arc_train_perfect")
                self.assertLessEqual(result["calls_used"], 2 if arm == "orchestrator_worker" else 1)
                self.assertLessEqual(len(llm.calls), result["calls_used"])

    def test_self_repair_uses_reasoning_fallback(self):
        llm = FakeLLM({"ok": True, "outcome": "ok", "receipt_id": "fallback",
                       "content": "", "reasoning_content": "```python\n" + PROGRAM + "\n```",
                       "finish_reason": "stop", "usage": {"completion_tokens": 3}})
        result = run_control_arm("self_repair", "arc", "task-1", TASK, PROMPT, llm,
                                 FakeEval(), Budget(8, 32), provider="deepseek",
                                 model="deepseek-flash", model_max_tokens=16)
        self.assertEqual(result["steps"][0]["code_source"], "reasoning_fallback")

    def test_fixed_seed_evolution_replay_is_deterministic(self):
        first, *_ = run("evolution", seed=77)
        second, *_ = run("evolution", seed=77)
        self.assertEqual(first, second)

    def test_unknown_outcome_reserves_the_full_requested_output_cap(self):
        llm = FakeLLM({"ok": False, "outcome": "unknown", "receipt_id": "unknown",
                       "usage": None})
        ledger = BudgetLedger(Budget(2, 8), "deepseek", "deepseek-flash", 16, llm)
        ledger.call("worker", PROMPT, 4)
        self.assertEqual(ledger.used_tokens, 4)
        ledger.call("worker", PROMPT, 4)
        self.assertEqual(ledger.used_tokens, 8)
        self.assertIsNone(ledger.call("worker", PROMPT, 4))
        self.assertEqual(len(llm.calls), 2)

    def test_not_sent_call_does_not_consume_budget(self):
        llm = FakeLLM({"ok": False, "outcome": "not_sent", "receipt_id": "none"})
        ledger = BudgetLedger(Budget(1, 8), "deepseek", "deepseek-flash", 16, llm)
        self.assertIsNone(ledger.call("worker", PROMPT, 8))
        self.assertEqual(ledger.used_calls, 0)
        self.assertEqual(ledger.used_tokens, 0)

    def test_invalid_budget_rejected(self):
        for calls, tokens in ((0, 1), (1, -1), (True, 1)):
            with self.subTest(calls=calls, tokens=tokens), self.assertRaises(ValueError):
                Budget(calls, tokens)


if __name__ == "__main__":
    unittest.main()
