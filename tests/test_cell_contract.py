"""Scientific-neutral contract tests; no API, scheduler or model calls."""
import json
import unittest
from unittest.mock import patch

from aimeth_runtime.store import Conflict, digest
from prototypes.cell_contract import CellContract


def population(**limits):
    return CellContract(modules=["construct", "check"], seeds=[
        {"cell_id": name, "expression": {"construct": 1, "check": 0},
         "memory": {"obligation": "fixture"}} for name in ("a", "b", "c")],
        edges=[["a", "b"], ["b", "c"]], limits={"max_population": 5,
        "max_units": 10, "max_events": 10, "max_neighbours": 3,
        "max_payload_bytes": 256, **limits})


def signal(**changes):
    return {"message_id": "m1", "sender": "a", "receiver": "b", "sender_version": 0,
            "receiver_version": 0, "kind": "candidate", "payload": {"statement": "fixture"},
            "parent_message_id": None, "parent_message_hash": None,
            "created_tick": 0, "expires_tick": 5, **changes}


class CellContractTests(unittest.TestCase):
    def assert_rejected_without_change(self, contract, operation):
        before = contract.to_json()
        with self.assertRaises((Conflict, ValueError)):
            operation()
        self.assertEqual(contract.to_json(), before)

    def test_delivery_updates_only_receiver_and_counts_resource(self):
        p = population()
        result = p.apply_signal("e1", signal(), now=1, expression={"construct": .25, "check": .75})
        self.assertEqual(result["state_version"], 1)
        self.assertEqual(result["last_signal_id"], "m1")
        self.assertEqual(p.cell("a")["state_version"], 0)
        self.assertEqual(p.summary()["units_used"], 1)

    def test_stale_sender_and_receiver_versions_are_rejected(self):
        for key in ("sender_version", "receiver_version"):
            with self.subTest(key=key):
                p = population()
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(**{key: 1}), now=1))

    def test_directed_adjacency_rejects_reverse_and_non_neighbour(self):
        for sender, receiver in (("b", "a"), ("a", "c"), ("a", "missing")):
            with self.subTest(edge=(sender, receiver)):
                p = population()
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(sender=sender, receiver=receiver), now=1))

    def test_duplicate_event_and_duplicate_message_cannot_reapply(self):
        p = population()
        p.apply_signal("e1", signal(), now=1)
        self.assert_rejected_without_change(p, lambda: p.apply_signal("e1", signal(), now=1))
        self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", signal(receiver_version=1), now=1))

    def test_expiry_and_future_creation_boundaries(self):
        for now, created in ((5, 0), (1, 2)):
            with self.subTest(now=now, created=created):
                p = population()
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(created_tick=created), now=now))

    def test_parent_chain_requires_previous_receiver_and_exact_hash(self):
        p = population()
        p.apply_signal("e1", signal(), now=1)
        reply = signal(message_id="m2", sender="b", receiver="c", sender_version=1,
                       parent_message_id="m1", parent_message_hash=p.signal_hash("m1"), created_tick=1)
        for bad in ("0" * 64, None):
            self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", {**reply, "parent_message_hash": bad}, now=2))
        self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", {**reply, "sender": "a", "receiver": "b", "sender_version": 0, "receiver_version": 1}, now=2))
        p.apply_signal("e2", reply, now=2)
        self.assertEqual(p.cell("c")["last_signal_id"], "m2")

    def test_reply_cannot_predate_parent_delivery(self):
        p = population()
        p.apply_signal("e1", signal(), now=3)
        reply = signal(message_id="m2", sender="b", receiver="c", sender_version=1,
                       parent_message_id="m1", parent_message_hash=p.signal_hash("m1"), created_tick=2)
        self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", reply, now=3))

    def test_signal_cannot_predate_either_endpoint_birth(self):
        p = population()
        p.divide("birth", parent_id="b", child_id="daughter", expected_version=0,
                 parent_state_hash=p.state_hash("b"), now=10)
        for contract in (p, CellContract.from_json(p.to_json())):
            for sender, receiver, sv, rv in (("daughter", "b", 0, 1), ("b", "daughter", 1, 0)):
                with self.subTest(sender=sender, replayed=contract is not p):
                    before_cells = [contract.cell(name) for name in ("b", "daughter")]
                    before_summary = contract.summary()
                    message = signal(sender=sender, receiver=receiver, sender_version=sv,
                                     receiver_version=rv, created_tick=0, expires_tick=20)
                    self.assert_rejected_without_change(contract, lambda: contract.apply_signal("bad", message, now=11))
                    self.assertEqual([contract.cell(name) for name in ("b", "daughter")], before_cells)
                    self.assertEqual(contract.summary(), before_summary)

    def test_signal_cannot_predate_either_referenced_state_version(self):
        p = population()
        p.apply_signal("first", signal(expires_tick=20), now=10)
        for contract in (p, CellContract.from_json(p.to_json())):
            for sender, receiver, sv, rv in (("b", "c", 1, 0), ("a", "b", 0, 1)):
                with self.subTest(sender=sender, replayed=contract is not p):
                    before_cells = [contract.cell(name) for name in (sender, receiver)]
                    before_summary = contract.summary()
                    message = signal(message_id="m2", sender=sender, receiver=receiver,
                                     sender_version=sv, receiver_version=rv,
                                     created_tick=0, expires_tick=20)
                    self.assert_rejected_without_change(contract, lambda: contract.apply_signal("bad", message, now=11))
                    self.assertEqual([contract.cell(name) for name in (sender, receiver)], before_cells)
                    self.assertEqual(contract.summary(), before_summary)

    def test_legitimate_delayed_signal_keeps_creation_tick_and_replays(self):
        p = population()
        p.divide("birth", parent_id="b", child_id="daughter", expected_version=0,
                 parent_state_hash=p.state_hash("b"), now=1)
        for contract in (p, CellContract.from_json(p.to_json())):
            message = signal(sender="daughter", receiver="b", receiver_version=1, created_tick=1)
            contract.apply_signal("delayed", message, now=4)
            snapshot = json.loads(contract.to_json())
            self.assertEqual(snapshot["events"][-1]["inputs"]["signal"]["created_tick"], 1)
            self.assertEqual(snapshot["events"][-1]["now"], 4)
            self.assertEqual(contract.summary()["units_used"], 3)
            restored = CellContract.from_json(contract.to_json())
            self.assertEqual(restored.to_json(), contract.to_json())
            self.assertEqual(restored.cell("b"), contract.cell("b"))

    def test_replay_rejects_backdated_message_even_with_consistent_hashes(self):
        p = population()
        p.divide("birth", parent_id="b", child_id="daughter", expected_version=0,
                 parent_state_hash=p.state_hash("b"), now=1)
        p.apply_signal("delayed", signal(sender="daughter", receiver="b", receiver_version=1,
                                          created_tick=1), now=4)
        snapshot = json.loads(p.to_json())
        event = snapshot["events"][-1]
        event["inputs"]["signal"]["created_tick"] = 0
        del event["event_hash"]
        event["event_hash"] = digest(event)
        snapshot["head_hash"] = event["event_hash"]
        with self.assertRaisesRegex(Conflict, "predates endpoint"):
            CellContract.from_json(json.dumps(snapshot))

    def test_unknown_parent_signal_is_rejected(self):
        p = population()
        self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(
            parent_message_id="absent", parent_message_hash="a" * 64), now=1))

    def test_closed_payload_schema_and_byte_bound(self):
        invalid = [signal(kind="unknown"), signal(payload={"statement": "x", "extra": 1}),
                   signal(payload={"statement": "x" * 300}),
                   signal(kind="resource_request", payload={"units": True}),
                   signal(kind="evidence", payload={"artifact_sha256": "bad"})]
        for item in invalid:
            with self.subTest(item=item["kind"]):
                p = population()
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e", item, now=1))

    def test_all_five_signal_types_are_accepted_with_valid_payloads(self):
        payloads = {"candidate": {"statement": "x"}, "constraint": {"constraint": "x"},
                    "evidence": {"artifact_sha256": "a" * 64},
                    "obligation": {"obligation_id": "o1", "statement": "x"},
                    "resource_request": {"units": 2}}
        for kind, payload in payloads.items():
            with self.subTest(kind=kind):
                p = population()
                p.apply_signal("e", signal(kind=kind, payload=payload), now=1)
                self.assertEqual(p.summary()["events"], 1)

    def test_expression_rejects_missing_nonfinite_boolean_and_out_of_range(self):
        for expression in ({"construct": 1}, {"construct": float("nan"), "check": 0},
                           {"construct": True, "check": 0}, {"construct": 1.1, "check": 0}):
            with self.subTest(expression=expression):
                p = population()
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(), now=1, expression=expression))

    def test_division_inherits_exact_snapshot_and_sets_lineage(self):
        p = population()
        before = p.cell("b")
        child = p.divide("d1", parent_id="b", child_id="child", expected_version=0,
                         parent_state_hash=p.state_hash("b"), now=1)
        self.assertEqual(child["parent_id"], "b")
        self.assertEqual(child["state_version"], 0)
        self.assertEqual(child["expression"], before["expression"])
        self.assertEqual(child["memory"], before["memory"])
        self.assertEqual(p.cell("b")["state_version"], 1)
        self.assertEqual(p.summary()["units_used"], 2)
        p.apply_signal("e", signal(sender="b", receiver="child", sender_version=1, created_tick=1), now=2)

    def test_division_rejects_stale_hash_and_duplicate_child(self):
        p = population()
        old_hash = p.state_hash("b")
        p.apply_signal("e", signal(), now=1)
        self.assert_rejected_without_change(p, lambda: p.divide("d", parent_id="b", child_id="child", expected_version=1, parent_state_hash=old_hash, now=2))
        self.assert_rejected_without_change(p, lambda: p.divide("d", parent_id="b", child_id="a", expected_version=1, parent_state_hash=p.state_hash("b"), now=2))

    def test_population_resource_and_neighbour_caps_do_not_partially_mutate(self):
        for limits in ({"max_population": 3}, {"max_units": 1}, {"max_neighbours": 1}):
            with self.subTest(limits=limits):
                p = population(**limits)
                self.assert_rejected_without_change(p, lambda: p.divide("d", parent_id="b", child_id="child", expected_version=0, parent_state_hash=p.state_hash("b"), now=1))

    def test_resource_and_event_exhaustion_reject_further_delivery(self):
        for limits in ({"max_units": 1}, {"max_events": 1}):
            with self.subTest(limits=limits):
                p = population(**limits)
                p.apply_signal("e1", signal(), now=1)
                self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", signal(message_id="m2", receiver_version=1), now=2))

    def test_returned_state_is_a_detached_copy(self):
        p = population()
        view = p.cell("a")
        view["expression"]["construct"] = 0
        view["memory"]["obligation"] = "changed"
        self.assertEqual(p.cell("a")["expression"]["construct"], 1)
        self.assertEqual(p.cell("a")["memory"]["obligation"], "fixture")

    def test_replay_restores_lineage_resources_and_duplicate_protection(self):
        p = population()
        p.apply_signal("e", signal(), now=1)
        p.divide("d", parent_id="b", child_id="child", expected_version=1, parent_state_hash=p.state_hash("b"), now=2)
        restored = CellContract.from_json(p.to_json())
        self.assertEqual(restored.to_json(), p.to_json())
        self.assertEqual(restored.cell("child"), p.cell("child"))
        self.assertEqual(restored.summary(), p.summary())
        self.assert_rejected_without_change(restored, lambda: restored.apply_signal("e", signal(), now=2))
        restored.apply_signal("next", signal(message_id="m2", sender="child", receiver="b", receiver_version=2, created_tick=2), now=3)
        self.assertEqual(restored.summary()["units_used"], 4)

    def test_replay_detects_payload_hash_and_envelope_damage(self):
        p = population()
        p.apply_signal("e", signal(), now=1)
        for part in ("payload", "hash", "units"):
            value = json.loads(p.to_json())
            if part == "payload":
                value["events"][0]["inputs"]["signal"]["payload"]["statement"] = "tampered"
            elif part == "hash":
                value["head_hash"] = "0" * 64
            else:
                value["events"][0]["cost_units"] = 0
            with self.subTest(part=part), self.assertRaises(Conflict):
                CellContract.from_json(json.dumps(value))
        with self.assertRaises(ValueError):
            CellContract.from_json('{"schema_version":"x","schema_version":"y"}')

    def test_time_and_integer_types_are_strict(self):
        p = population()
        p.apply_signal("e1", signal(), now=2)
        for now in (True, -1, 1):
            self.assert_rejected_without_change(p, lambda: p.apply_signal("e2", signal(message_id="m2", receiver_version=1), now=now))

    def test_snapshot_bound_rejects_transition_before_mutating_state(self):
        p = population()
        before = p.to_json()
        with patch("prototypes.cell_contract.MAX_SNAPSHOT_BYTES", len(before.encode()) + 10):
            self.assert_rejected_without_change(p, lambda: p.apply_signal("e", signal(), now=1))
            restored = CellContract.from_json(p.to_json())
            self.assertEqual(restored.to_json(), before)


if __name__ == "__main__":
    unittest.main()
