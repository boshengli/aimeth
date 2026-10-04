"""Finite synthetic implementation checks; no model calls or efficacy tests."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from aimeth_runtime.store import Conflict, canonical
from prototypes.cell_policy import (PolicyFixture, build_fixture, construct_module,
                                   strict_json, validate_card)


CARD = json.loads((Path(__file__).resolve().parents[1] / "plans/cell-development-pilot-v0.json").read_text())


def case(arm="develop_4_to_16", condition="satisfiable", **bounds):
    card = copy.deepcopy(CARD)
    card["bounds"].update(bounds)
    return PolicyFixture(card, seed=0, arm=arm, condition=condition)


class CellPolicyTests(unittest.TestCase):
    def test_exact_42_case_allocation_and_exclusions(self):
        allocation = validate_card(CARD)
        self.assertEqual(len(allocation), 42)
        self.assertFalse(any(arm == "independent_16" and condition in ("duplicate_replay", "stale_delivery")
                             for _, arm, condition in allocation))
        with self.assertRaises(ValueError):
            case("independent_16", "stale_delivery")

    def test_local_views_are_detached_and_do_not_expose_peer_or_evaluator_state(self):
        p = case()
        view = p.local_view("cell-000")
        self.assertEqual(set(view["known"]), {"ob-000", "ob-004"})
        self.assertFalse({"cells", "artifacts", "terminal", "target_index", "seed"} & set(view))
        view["owned"].clear()
        self.assertEqual(len(p.local_view("cell-000")["owned"]), 2)

    def test_construct_enumerates_shard_without_target_shortcut(self):
        p = case()
        view = p.local_view("cell-000")
        view["known"]["ob-000"]["target_sha256"] = "f" * 64
        first = construct_module(view)
        self.assertEqual((first["candidate_index"], first["candidate_value"]), (0, "red"))
        view["owned"]["ob-000"]["cursor"] = 1
        self.assertEqual(construct_module(view)["candidate_index"], 1)

    def test_fixed_and_independent_shards_are_disjoint_and_productive(self):
        for arm in ("fixed_16", "independent_16"):
            p = case(arm)
            shards = {}
            for cell in p.state["cells"].values():
                for oid, work in cell["owned"].items():
                    shards.setdefault(oid, []).extend(work["shard"])
            self.assertEqual(set(shards), {f"ob-{i:03d}" for i in range(8)})
            self.assertTrue(all(sorted(indices) == [0, 1, 2, 3] for indices in shards.values()))
            self.assertEqual(len(p.state["edges"]), 0 if arm == "independent_16" else 32)

    def test_division_locks_then_delivered_handoff_transfers_exact_ownership(self):
        p = case()
        p.step()
        self.assertEqual(p.state["cells"]["cell-000"]["locks"], {"ob-004": "handoff-cell-000-d0"})
        self.assertEqual(p.state["cells"]["cell-000-d0"]["owned"], {})
        self.assertEqual(p.contract.cell("cell-000-d0")["memory"], p.contract.cell("cell-000")["memory"])
        for _ in range(4):
            p.step()
        self.assertNotIn("ob-004", p.state["cells"]["cell-000"]["owned"])
        self.assertEqual(p.state["cells"]["cell-000-d0"]["owned"]["ob-004"], {"shard": [0, 1, 2, 3], "cursor": 0})
        self.assertNotIn("handoff-cell-000-d0", p.state["reserved_allowances"])

    def test_newborns_enter_only_the_next_sweep(self):
        p = case()
        for _ in range(4):
            p.step()
        self.assertEqual([e["cell_id"] for e in p.events], [f"cell-{i:03d}" for i in range(4)])
        self.assertEqual(len(p.state["cells"]), 8)
        self.assertIn("cell-000-d0", p.state["sweep_ids"])

    def test_division_requires_reserved_budget_for_handoff(self):
        p = case(max_module_actions=1)
        self.assertEqual(p.next_action()["module"], "construct")
        p.run()
        self.assertEqual(p.state["counters"]["division_accepted"], 0)
        self.assertEqual(p.state["counters"]["module_actions"], 1)
        self.assertEqual(p.state["stop_reason"], "limit:module_actions")

    def test_rejected_handoff_retains_parent_work_and_records_cleanup(self):
        p = case()
        for _ in range(4):
            p.step()
        contract_before = p.contract.to_json()
        original = p._signal
        def stale(*args):
            signal = original(*args)
            signal["receiver_version"] += 1
            return signal
        with patch.object(p, "_signal", side_effect=stale):
            p.step()
        self.assertEqual(p.contract.to_json(), contract_before)
        self.assertIn("ob-004", p.state["cells"]["cell-000"]["owned"])
        self.assertFalse(p.state["cells"]["cell-000"]["locks"])
        self.assertEqual(p.state["cells"]["cell-000-d0"]["owned"], {})
        self.assertEqual(p.state["attempt_ledger"][-1]["outcome"], "rejected")
        self.assertEqual(p.state["attempt_ledger"][-1]["cost"]["contract_units"], 0)
        self.assertEqual(p.events[-1]["kind"], "terminal_rejection_cleanup")

    def test_artifact_access_requires_an_accepted_grant(self):
        p = case()
        with self.assertRaises(Conflict):
            p._artifact(p.state, "cell-000", "a" * 64)

    def test_negative_check_retains_artifact_without_broadcast(self):
        p = case("independent_16")
        while not p.state["cells"]["cell-002"]["checked"]:
            p.step()
        negative = p.state["cells"]["cell-002"]["checked"]["ob-001:0"]
        self.assertFalse(negative["valid"])
        artifact = p._artifact(p.state, "cell-002", negative["artifact_id"])
        self.assertFalse(artifact["valid"])
        self.assertNotEqual(artifact["observed_sha256"], artifact["target_sha256"])
        self.assertFalse(p.state["cells"]["cell-002"]["outbox"])

    def test_canonical_payload_parser_rejects_duplicates_and_noncanonical_text(self):
        for text in ('{"a":1,"a":2}', '{"b": 2, "a": 1}'):
            with self.assertRaises(ValueError):
                strict_json(text)
        self.assertEqual(strict_json('{"a":1}'), {"a": 1})

    def test_midrun_replay_restores_ownership_ledger_and_next_action(self):
        p = case()
        for _ in range(9):
            p.step()
        restored = PolicyFixture.from_json(p.to_json(), p.card)
        self.assertEqual(restored.to_json(), p.to_json())
        self.assertEqual(restored.next_action(), p.next_action())
        for _ in range(5):
            p.step()
            restored.step()
        self.assertEqual(restored.to_json(), p.to_json())

    def test_replay_rejects_policy_state_and_event_tampering(self):
        p = case()
        p.step()
        for field in ("state", "event"):
            saved = json.loads(p.to_json())
            if field == "state":
                saved["policy_state"]["counters"]["module_actions"] = 0
            else:
                saved["policy_events"][0]["module"] = "construct"
            with self.subTest(field=field), self.assertRaises(Conflict):
                PolicyFixture.from_json(canonical(saved), p.card)

    def test_turn_limit_is_a_replayable_terminal_state(self):
        p = case(max_turns=2)
        report = p.run()
        self.assertEqual(report["stop_reason"], "limit:turns")
        self.assertEqual(PolicyFixture.from_json(p.to_json(), p.card).to_json(), p.to_json())

    def test_joint_validation_failure_does_not_commit_detached_contract(self):
        p = case()
        before = p.to_json()
        with patch.object(p, "_validate_joint", side_effect=ValueError("synthetic snapshot failure")):
            with self.assertRaises(ValueError):
                p.step()
        self.assertEqual(p.to_json(), before)

    def test_named_counters_and_snapshot_sizes_match_reality(self):
        p = case()
        for _ in range(9):
            p.step()
        report = p.report()
        ledger = p.state["attempt_ledger"]
        self.assertEqual(sum(x["cost"]["module_actions"] for x in ledger), report["counters"]["module_actions"])
        self.assertEqual(sum(x["cost"].get("contract_units", 0) for x in ledger), p.contract.summary()["units_used"])
        self.assertEqual(report["byte_metrics"]["joint"], len(p.to_json().encode()))
        self.assertEqual(report["byte_metrics"]["contract"], len(p.contract.to_json().encode()))

    def test_duplicate_and_stale_injections_are_rejected_and_replayable(self):
        for condition in ("duplicate_replay", "stale_delivery"):
            with self.subTest(condition=condition):
                p = case(condition=condition)
                while not p.state["fault_detected"]:
                    self.assertTrue(p.step())
                failures = [x for x in p.state["attempt_ledger"] if x["origin"] == "fault_harness" and x["outcome"] == "rejected"]
                self.assertEqual(len(failures), 1)
                self.assertEqual(failures[0]["cost"]["contract_units"], 0)
                self.assertEqual(p.state["counters"]["route_rejected"], 1)
                self.assertEqual(PolicyFixture.from_json(p.to_json(), p.card).to_json(), p.to_json())

    def test_sat_and_unsat_outcomes_across_four_arms_seed_zero(self):
        for condition in ("satisfiable", "unsatisfiable"):
            for arm in ("develop_4_to_16", "fixed_16", "independent_16", "no_division_4"):
                with self.subTest(condition=condition, arm=arm):
                    p = case(arm, condition)
                    report = p.run()
                    self.assertEqual(report["verified_obligations"], 7 if condition == "unsatisfiable" else 8)
                    if condition == "unsatisfiable":
                        self.assertTrue(report["unsatisfiable_final_shard_exhausted"])
                        self.assertEqual(report["terminal"]["unresolved_obligations"], ["ob-007"])
                    self.assertLessEqual(report["counters"]["terminal_verification_calls"], 32)
                    self.assertEqual(report["allocated_limits"], CARD["bounds"])
                    self.assertGreater(report["distinct_constructed_pairs"], 0)
                    self.assertFalse(report["scientific_replication"])


if __name__ == "__main__":
    unittest.main()
