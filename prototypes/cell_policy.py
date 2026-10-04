"""Deterministic, offline four-module fixtures; no scientific efficacy claim.

The policy owns mutable queues, never the contract's private state. A turn is
validated on detached objects before the pair is swapped. Snapshots are replay
artifacts; this module does not claim crash-safe joint persistence.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from aimeth_runtime.store import Conflict, canonical, digest, identity
from .cell_contract import CellContract, clone, fields


VERSION = "cell-policy-fixture.v0"
MODULES = ("construct", "check", "route", "divide")
BOUND_KEYS = {
    "turns": "max_turns", "module_actions": "max_module_actions",
    "construct_calls": "max_construct_calls", "check_calls": "max_check_calls",
    "route_attempts": "max_route_attempts", "division_attempts": "max_divisions",
    "contract_units": "max_contract_units", "contract_events": "max_contract_events",
    "signal_payload_bytes": "max_total_signal_payload_bytes",
}


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate encoded JSON field")
            result[key] = value
        return result
    result = json.loads(text, object_pairs_hook=unique)
    if canonical(result) != text:
        raise ValueError("Encoded payload must be canonical JSON")
    return result


def predicate(obligation, candidate):
    return hashlib.sha256((obligation["salt"] + ":" + candidate).encode()).hexdigest()


def build_fixture(seed, condition):
    """Fixture builder; target-index generation is never a module input."""
    domain = ["red", "green", "blue", "amber"]
    obligations = []
    for index in range(8):
        item = {"obligation_id": f"ob-{index:03d}", "salt": f"fixture-v0:{seed}:{index}",
                "candidate_domain": domain, "target_sha256": ""}
        item["target_sha256"] = predicate(item, domain[(seed + index) % 4])
        if condition == "unsatisfiable" and index == 7:
            assert all(predicate(item, candidate) != "0" * 64 for candidate in domain)
            item["target_sha256"] = "0" * 64
        obligations.append(item)
    return {"id": "catalog-selection.v0", "obligations": obligations}


def validate_card(card):
    if (card.get("schema_version") != "aimeth.cell-development-pilot.v0"
            or card.get("network_enabled") is not False or card.get("model_calls_allowed") != 0
            or card.get("frozen_v8_changes_allowed") is not False
            or card["contract"]["modules"] != list(MODULES)
            or card["fixture"]["allocated_cases"] != 42
            or card["fixture"]["seeds"] != [0, 1, 2]
            or card["fixture"]["obligations"] != 8
            or card["fixture"]["candidate_domain"] != ["red", "green", "blue", "amber"]):
        raise ValueError("Unsupported or unsafe fixture card")
    for value in card["bounds"].values():
        if type(value) is not int or value <= 0:
            raise ValueError("Fixture bounds must be positive integers")
    arms = {x["id"]: x for x in card["arms"]}
    if set(arms) != {"develop_4_to_16", "fixed_16", "independent_16", "no_division_4"}:
        raise ValueError("Unsupported arm allocation")
    allocation = [(s, a, c["id"]) for s in card["fixture"]["seeds"]
                  for c in card["fixture"]["conditions"] for a in c["allocated_arms"]]
    if len(allocation) != 42 or len(set(allocation)) != 42:
        raise ValueError("Allocation denominator mismatch")
    return allocation


def candidate_key(candidate):
    return candidate["obligation_id"] + ":" + str(candidate["candidate_index"])


def construct_module(view):
    """Only enumerate locally assigned shards; no target digest computation."""
    for oid, owned in sorted(view["owned"].items()):
        if oid in view["locked"] or oid in view["solved"] or owned["cursor"] >= len(owned["shard"]):
            continue
        index = owned["shard"][owned["cursor"]]
        return {"obligation_id": oid, "candidate_index": index,
                "candidate_value": view["known"][oid]["candidate_domain"][index],
                "producer_cell_id": view["cell_id"]}
    return None


def check_module(view):
    item = min(view["unchecked"], key=lambda x: (x["candidate"]["obligation_id"],
                x["candidate"]["candidate_index"], x["message_id"] or ""))
    candidate = item["candidate"]
    public = view["known"][candidate["obligation_id"]]
    observed = predicate(public, candidate["candidate_value"])
    return item, observed, observed == public["target_sha256"]


def route_module(view):
    return sorted(view["outbox"], key=lambda x: (x["obligation_id"], x["candidate_index"], x["message_id"]))[0]


def divide_module(view):
    candidates = [oid for oid, work in view["owned"].items() if oid not in view["solved"]
                  and oid not in view["division_attempted"] and work["cursor"] < len(work["shard"])]
    return sorted(candidates)[-1] if not view["locked"] and len(candidates) >= 2 else None


def empty_cell(known=None, owned=None):
    return {"known": known or {}, "owned": owned or {}, "unchecked": [], "outbox": [],
            "checked": {}, "solved": [], "artifact_access": [], "terminal": {},
            "locks": {}, "division_attempted": [], "processed_messages": [],
            "activity": [], "activity_count": 0, "successful_divisions": 0}


class PolicyFixture:
    def __init__(self, card, *, seed, arm, condition):
        if (seed, arm, condition) not in validate_card(card):
            raise ValueError("Case is not allocated; excluded cases are not passes")
        self.card = clone(card)
        self.seed, self.arm, self.condition = seed, arm, condition
        self.fixture = build_fixture(seed, condition)
        self._public = {x["obligation_id"]: x for x in self.fixture["obligations"]}
        arm_card = next(x for x in card["arms"] if x["id"] == arm)
        n = arm_card["start_cells"]
        names = [f"cell-{i:03d}" for i in range(n)]
        edges = [] if arm == "independent_16" else sorted({(names[i], names[j]) for i in range(n)
                  for j in ((i - 1) % n, (i + 1) % n)})
        cells = {}
        for i, name in enumerate(names):
            indices = [i // 2] if n == 16 else [i, i + 4]
            known = {f"ob-{j:03d}": clone(self._public[f"ob-{j:03d}"]) for j in indices}
            owned = {oid: {"shard": [i % 2, i % 2 + 2] if n == 16 else [0, 1, 2, 3], "cursor": 0}
                     for oid in known}
            cells[name] = empty_cell(known, owned)
        bounds = card["bounds"]
        self.contract = CellContract(modules=list(MODULES), seeds=[{"cell_id": name,
            "expression": dict.fromkeys(MODULES, 1), "memory": {"fixture_id": self.fixture["id"]}}
            for name in names], edges=[list(x) for x in edges], limits={
                "max_population": card["population"]["max_population"],
                "max_units": bounds["max_contract_units"], "max_events": bounds["max_contract_events"],
                "max_neighbours": bounds["max_neighbours"], "max_payload_bytes": bounds["max_payload_bytes"]})
        self.state = {"cells": cells, "edges": [list(x) for x in edges], "artifacts": {},
            "counters": {**dict.fromkeys(BOUND_KEYS, 0), "route_accepted": 0, "route_rejected": 0,
                         "division_accepted": 0, "division_rejected": 0, "terminal_verification_calls": 0},
            "attempt_ledger": [], "constructed_pairs": [], "reserved_allowances": {}, "sweep_ids": names, "sweep_pos": 0,
            "sweeps": 0, "sweep_active": False, "fault_injected": False, "fault_detected": False,
            "stop_reason": None, "terminal": None, "structure_snapshots": [],
            "byte_metrics": {"policy": 0, "contract": 0, "joint": 0,
                             "peak_policy": 0, "peak_contract": 0, "peak_joint": 0}}
        self.events = []
        self.head = digest({"card": digest(card), "fixture": digest(self.fixture), "arm": arm, "seed": seed,
                            "condition": condition, "policy_version": VERSION})
        self.state["structure_snapshots"].append(self._structure(self.state, "genesis"))
        self._update_sizes(self.contract, self.state, self.events, self.head)
        self._validate_joint(self.contract, self.state, self.events, self.head)

    def local_view(self, cell_id, state=None):
        """Whitelisted detached local view; no evaluator map or peer queues."""
        state = self.state if state is None else state
        cell = state["cells"][cell_id]
        return clone({"cell_id": cell_id, "known": cell["known"], "owned": cell["owned"],
            "unchecked": cell["unchecked"], "outbox": cell["outbox"], "solved": cell["solved"],
            "locked": list(cell["locks"]), "division_attempted": cell["division_attempted"],
            "neighbours": sorted(b for a, b in state["edges"] if a == cell_id)})

    def _fits(self, state, cost, release=None):
        held = {key: sum(v.get(key, 0) for rid, v in state["reserved_allowances"].items() if rid != release)
                for key in BOUND_KEYS}
        for key, value in cost.items():
            if state["counters"][key] + held[key] + value > self.card["bounds"][BOUND_KEYS[key]]:
                return key
        return None

    def _division_plan(self, cell_id, state):
        if self.arm != "develop_4_to_16":
            return None
        view = self.local_view(cell_id, state)
        oid = divide_module(view)
        if oid is None or len(view["neighbours"]) >= self.card["bounds"]["max_neighbours"] or len(state["cells"]) >= 16:
            return None
        parent = state["cells"][cell_id]
        child = cell_id + "-d" + str(parent["successful_divisions"])
        transfer_id = "handoff-" + child
        work = parent["owned"][oid]
        body = {"obligation": parent["known"][oid], "shard": work["shard"][work["cursor"]:], "transfer_id": transfer_id}
        payload = {"obligation_id": oid, "statement": canonical(body)}
        route_cost = {"module_actions": 1, "route_attempts": 1, "contract_units": 1, "contract_events": 1,
                      "signal_payload_bytes": len(canonical(payload).encode())}
        total = {**route_cost, "module_actions": 2, "contract_units": 3, "contract_events": 2, "division_attempts": 1}
        if route_cost["signal_payload_bytes"] > self.card["bounds"]["max_payload_bytes"] or self._fits(state, total):
            return None
        return oid, child, transfer_id, payload, route_cost

    def next_action(self, state=None):
        state = self.state if state is None else state
        if state["stop_reason"]:
            return None
        cell_id = state["sweep_ids"][state["sweep_pos"]]
        view = self.local_view(cell_id, state)
        if view["unchecked"]:
            module = "check"
        elif view["outbox"]:
            module = "route"
        elif self._division_plan(cell_id, state):
            module = "divide"
        elif construct_module(view) is not None:
            module = "construct"
        else:
            module = "idle"
        return {"cell_id": cell_id, "module": module}

    def _header(self, events, head, kind, cell_id, module, tick, inputs):
        header = {"sequence": len(events) + 1, "kind": kind, "cell_id": cell_id, "module": module,
                  "tick": tick, "input_sha256": digest(inputs), "previous_hash": head}
        header["event_hash"] = digest(header)
        events.append(header)
        return header["event_hash"]

    def _attempt(self, state, *, module, cell_id, tick, outcome, cost, operation, reason=None, origin="cell"):
        for key, value in cost.items():
            state["counters"][key] += value
        state["attempt_ledger"].append({"sequence": len(state["attempt_ledger"]) + 1,
            "module": module, "cell_id": cell_id, "tick": tick, "origin": origin,
            "outcome": outcome, "reason": reason, "cost": cost, "operation_sha256": digest(operation)})

    def _candidate_valid(self, candidate, obligation):
        fields(candidate, ("obligation_id", "candidate_index", "candidate_value", "producer_cell_id"))
        identity(candidate["producer_cell_id"])
        index = candidate["candidate_index"]
        if (candidate["obligation_id"] != obligation["obligation_id"] or type(index) is not int
                or not 0 <= index < 4 or candidate["candidate_value"] != obligation["candidate_domain"][index]):
            raise ValueError("Candidate does not match its declared domain/obligation")

    def _public_valid(self, obligation):
        fields(obligation, ("obligation_id", "salt", "candidate_domain", "target_sha256"))
        if obligation != self._public.get(obligation["obligation_id"]):
            raise ValueError("Received public obligation differs from frozen fixture")

    def _artifact(self, state, cell_id, artifact_id):
        if artifact_id not in state["cells"][cell_id]["artifact_access"]:
            raise Conflict("Artifact not granted to this cell")
        artifact = state["artifacts"].get(artifact_id)
        if artifact is None or digest(artifact) != artifact_id:
            raise ValueError("Artifact hash mismatch")
        fields(artifact, ("candidate", "obligation", "target_sha256", "observed_sha256", "valid",
                          "checker_cell_id", "policy_event_hash"))
        self._public_valid(artifact["obligation"])
        self._candidate_valid(artifact["candidate"], artifact["obligation"])
        if (type(artifact["valid"]) is not bool or artifact["target_sha256"] != artifact["obligation"]["target_sha256"]
                or not isinstance(artifact["observed_sha256"], str) or len(artifact["observed_sha256"]) != 64):
            raise ValueError("Invalid artifact envelope")
        return clone(artifact)

    def _receive(self, state, entry, sender, message_id):
        receiver = state["cells"][entry["receiver"]]
        oid = entry["obligation_id"]
        if message_id in receiver["processed_messages"]:
            raise Conflict("Policy message already consumed")
        if entry["kind"] == "obligation":
            body = strict_json(entry["payload"]["statement"])
            fields(body, ("obligation", "shard", "transfer_id"))
            self._public_valid(body["obligation"])
            shard = body["shard"]
            if (body["obligation"]["obligation_id"] != oid or not isinstance(shard, list)
                    or not shard or any(type(x) is not int or not 0 <= x < 4 for x in shard)
                    or shard != sorted(set(shard)) or oid in receiver["owned"]
                    or state["cells"][sender]["locks"].get(oid) != body["transfer_id"]):
                raise ValueError("Invalid or conflicting obligation handoff")
            parent_work = state["cells"][sender]["owned"][oid]
            if shard != parent_work["shard"][parent_work["cursor"]:]:
                raise Conflict("Handoff shard changed while locked")
            receiver["known"][oid] = clone(body["obligation"])
            receiver["owned"][oid] = {"shard": shard, "cursor": 0}
            del state["cells"][sender]["owned"][oid]
            del state["cells"][sender]["locks"][oid]
        elif entry["kind"] == "evidence":
            artifact_id = entry["payload"]["artifact_sha256"]
            artifact = self._artifact(state, sender, artifact_id)
            if oid != artifact["candidate"]["obligation_id"]:
                raise ValueError("Evidence obligation mismatch")
            if artifact_id not in receiver["artifact_access"]:
                receiver["artifact_access"].append(artifact_id)
            candidate = artifact["candidate"]
            receiver["known"][oid] = clone(artifact["obligation"])
            if candidate_key(candidate) not in receiver["checked"] and all(candidate_key(x["candidate"]) != candidate_key(candidate) for x in receiver["unchecked"]):
                receiver["unchecked"].append({"candidate": clone(candidate), "message_id": message_id})
        elif entry["kind"] == "candidate":
            candidate = strict_json(entry["payload"]["statement"])
            if oid not in receiver["known"]:
                raise Conflict("Candidate recipient lacks public obligation")
            self._candidate_valid(candidate, receiver["known"][oid])
            receiver["unchecked"].append({"candidate": candidate, "message_id": message_id})
        else:
            raise ValueError("Unsupported policy signal")
        receiver["processed_messages"].append(message_id)

    def _signal(self, contract, sender, entry, tick):
        parent_id = contract.cell(sender)["last_signal_id"]
        return {"message_id": entry["message_id"], "sender": sender, "receiver": entry["receiver"],
            "sender_version": contract.cell(sender)["state_version"],
            "receiver_version": contract.cell(entry["receiver"])["state_version"],
            "kind": entry["kind"], "payload": entry["payload"], "created_tick": tick,
            "expires_tick": tick + self.card["scheduler"]["signal_ttl_ticks"],
            "parent_message_id": parent_id, "parent_message_hash": contract.signal_hash(parent_id) if parent_id else None}

    def _deliver(self, contract, state, sender, entry, tick):
        signal = self._signal(contract, sender, entry, tick)
        event_id = "delivery-" + entry["message_id"]
        proposed_contract, proposed_state = copy.deepcopy(contract), clone(state)
        try:
            proposed_contract.apply_signal(event_id, signal, now=tick)
            self._receive(proposed_state, entry, sender, signal["message_id"])
        except (ValueError, KeyError) as exc:
            return contract, state, signal, event_id, str(exc)
        return proposed_contract, proposed_state, signal, event_id, None

    def _cost(self, module, entry=None):
        result = {"module_actions": 1}
        if module in ("construct", "check"):
            result[module + "_calls"] = 1
        elif module == "divide":
            result.update(division_attempts=1, contract_units=2, contract_events=1)
        elif module == "route":
            result.update(route_attempts=1, contract_units=1, contract_events=1,
                          signal_payload_bytes=len(canonical(entry["payload"]).encode()))
        return result

    def _fault_injection(self, contract, state, events, head, signal, event_id, tick):
        if state["fault_injected"] or self.condition not in ("duplicate_replay", "stale_delivery"):
            return contract, state, head
        sender = signal["sender"]
        state["fault_injected"] = True
        held = clone(signal)
        if self.condition == "stale_delivery":
            held["message_id"] += "-held"
            held["sender_version"] = contract.cell(sender)["state_version"]
            held["receiver_version"] = contract.cell(signal["receiver"])["state_version"]
            event_id += "-held"
            advance = {**held, "message_id": held["message_id"] + "-advance", "kind": "constraint",
                       "payload": {"constraint": "synthetic receiver version advance"}}
            cost = self._cost("route", advance)
            if self._fits(state, cost):
                state["stop_reason"] = "limit:fault_harness"
                return contract, state, head
            head = self._header(events, head, "fault_harness", sender, "route", tick, advance)
            contract.apply_signal(event_id + "-advance", advance, now=tick)
            state["cells"][signal["receiver"]]["processed_messages"].append(advance["message_id"])
            state["counters"]["route_accepted"] += 1
            self._attempt(state, module="route", cell_id=sender, tick=tick, outcome="accepted",
                          cost=cost, operation=advance, origin="fault_harness")
        cost = self._cost("route", held)
        if self._fits(state, cost):
            state["stop_reason"] = "limit:fault_harness"
            return contract, state, head
        head = self._header(events, head, "fault_harness", sender, "route", tick, held)
        before_contract, before_cells = contract.to_json(), digest(state["cells"])
        try:
            contract.apply_signal(event_id, held, now=tick)
        except Conflict as exc:
            reason = str(exc)
            expected = "already applied" if self.condition == "duplicate_replay" else "Stale"
            if expected not in reason or contract.to_json() != before_contract or digest(state["cells"]) != before_cells:
                raise ValueError("Fault injection violated expected rejection semantics")
            cost["contract_units"] = cost["contract_events"] = 0
            state["counters"]["route_rejected"] += 1
            self._attempt(state, module="route", cell_id=sender, tick=tick, outcome="rejected",
                          cost=cost, operation=held, reason=reason, origin="fault_harness")
            state["fault_detected"] = True
        else:
            raise ValueError("Fault injection unexpectedly accepted")
        return contract, state, head

    def step(self):
        if self.state["stop_reason"]:
            return False
        if self._fits(self.state, {"turns": 1}):
            raise Conflict("Turn limit reached without a recorded stopping transition")
        state, contract, events, head = clone(self.state), copy.deepcopy(self.contract), clone(self.events), self.head
        action = self.next_action(state)
        cell_id, module = action["cell_id"], action["module"]
        state["counters"]["turns"] += 1
        tick = state["counters"]["turns"]
        view = self.local_view(cell_id, state)
        head = self._header(events, head, "turn", cell_id, module, tick, view)
        cell = state["cells"][cell_id]
        entry = route_module(view) if module == "route" else None
        reservation_id = entry.get("transfer_id") if entry else None
        cost = self._cost(module, entry) if module != "idle" else {}
        bound = self._fits(state, cost, release=reservation_id)
        if bound:
            state["stop_reason"] = "limit:" + bound
        elif module == "construct":
            candidate = construct_module(view)
            pair = candidate_key(candidate)
            if pair not in state["constructed_pairs"]:
                state["constructed_pairs"].append(pair)
            cell["owned"][candidate["obligation_id"]]["cursor"] += 1
            cell["unchecked"].append({"candidate": candidate, "message_id": None})
            self._attempt(state, module=module, cell_id=cell_id, tick=tick, outcome="accepted", cost=cost, operation=candidate)
        elif module == "check":
            item, observed, valid = check_module(view)
            candidate = item["candidate"]
            cell["unchecked"].remove(item)
            oid = candidate["obligation_id"]
            artifact = {"candidate": candidate, "obligation": clone(cell["known"][oid]),
                "target_sha256": cell["known"][oid]["target_sha256"], "observed_sha256": observed,
                "valid": valid, "checker_cell_id": cell_id, "policy_event_hash": head}
            artifact_id = digest(artifact)
            state["artifacts"][artifact_id] = artifact
            cell["artifact_access"].append(artifact_id)
            cell["checked"][candidate_key(candidate)] = {"valid": valid, "artifact_id": artifact_id}
            if valid:
                cell["terminal"][oid] = artifact_id
                if oid not in cell["solved"]:
                    cell["solved"].append(oid)
                for receiver in view["neighbours"]:
                    cell["outbox"].append({"message_id": "m-" + artifact_id[:24] + "-" + receiver,
                        "receiver": receiver, "kind": "evidence", "payload": {"artifact_sha256": artifact_id},
                        "obligation_id": oid, "candidate_index": candidate["candidate_index"]})
            self._attempt(state, module=module, cell_id=cell_id, tick=tick,
                          outcome="valid" if valid else "invalid", cost=cost, operation={"candidate": candidate, "observed": observed})
        elif module == "divide":
            oid, child, transfer_id, payload, reserved = self._division_plan(cell_id, state)
            contract.divide("birth-" + child, parent_id=cell_id, child_id=child,
                            expected_version=contract.cell(cell_id)["state_version"],
                            parent_state_hash=contract.state_hash(cell_id), now=tick)
            state["cells"][child] = empty_cell()
            cell["successful_divisions"] += 1
            cell["division_attempted"].append(oid)
            cell["locks"][oid] = transfer_id
            cell["outbox"].append({"message_id": transfer_id, "receiver": child, "kind": "obligation",
                "payload": payload, "obligation_id": oid, "candidate_index": -1, "transfer_id": transfer_id})
            state["reserved_allowances"][transfer_id] = reserved
            state["edges"].extend([[cell_id, child], [child, cell_id]])
            state["edges"].sort()
            state["counters"]["division_accepted"] += 1
            self._attempt(state, module=module, cell_id=cell_id, tick=tick, outcome="accepted", cost=cost,
                          operation={"parent_id": cell_id, "child_id": child, "transfer": transfer_id})
        elif module == "route":
            contract, state, signal, event_id, failure = self._deliver(contract, state, cell_id, entry, tick)
            cell = state["cells"][cell_id]
            cell["outbox"].remove(entry)
            if reservation_id:
                state["reserved_allowances"].pop(reservation_id)
            if failure:
                cost["contract_units"] = cost["contract_events"] = 0
                state["counters"]["route_rejected"] += 1
                if reservation_id:
                    cell["locks"].pop(entry["obligation_id"], None)
                head = self._header(events, head, "terminal_rejection_cleanup", cell_id, "route", tick,
                                    {"entry": entry, "reason": failure})
            else:
                state["counters"]["route_accepted"] += 1
            self._attempt(state, module=module, cell_id=cell_id, tick=tick,
                          outcome="rejected" if failure else "accepted", cost=cost, operation=signal, reason=failure)
            if failure is None:
                contract, state, head = self._fault_injection(contract, state, events, head, signal, event_id, tick)
        if module != "idle" and not bound:
            cell = state["cells"][cell_id]
            cell["activity"].append(module)
            cell["activity"] = cell["activity"][-8:]
            cell["activity_count"] += 1
            state["sweep_active"] = True
        state["sweep_pos"] += 1
        if state["sweep_pos"] == len(state["sweep_ids"]):
            state["sweeps"] += 1
            state["structure_snapshots"].append(self._structure(state, "sweep"))
            if not state["sweep_active"]:
                state["stop_reason"] = state["stop_reason"] or "exhausted"
            state["sweep_ids"], state["sweep_pos"], state["sweep_active"] = sorted(state["cells"]), 0, False
        if state["counters"]["turns"] == self.card["bounds"]["max_turns"]:
            state["stop_reason"] = state["stop_reason"] or "limit:turns"
        submitted = {oid for value in state["cells"].values() for oid in value["terminal"]}
        if len(submitted) == 8 or state["stop_reason"]:
            self._terminal(state)
            if len(state["terminal"]["verified_obligations"]) == 8:
                state["stop_reason"] = "success"
        if state["stop_reason"]:
            state["structure_snapshots"].append(self._structure(state, "terminal"))
        self._update_sizes(contract, state, events, head)
        self._validate_joint(contract, state, events, head)
        self.contract, self.state, self.events, self.head = contract, state, events, head
        return True

    def _terminal(self, state):
        if state["terminal"] is not None:
            return
        submitted = {}
        for cell_id, cell in sorted(state["cells"].items()):
            for oid, artifact_id in sorted(cell["terminal"].items()):
                submitted.setdefault(oid, (cell_id, artifact_id))
        accepted = []
        rejected = []
        for oid, (cell_id, artifact_id) in sorted(submitted.items()):
            if state["counters"]["terminal_verification_calls"] >= 32:
                break
            artifact = self._artifact(state, cell_id, artifact_id)
            state["counters"]["terminal_verification_calls"] += 1
            candidate = artifact["candidate"]["candidate_value"]
            public = self._public[oid]
            actual = hashlib.sha256((public["salt"] + ":" + candidate).encode("utf-8")).hexdigest()
            (accepted if actual == public["target_sha256"] else rejected).append(oid)
        state["terminal"] = {"verified_obligations": accepted, "rejected_obligations": rejected,
                             "unresolved_obligations": sorted(set(self._public) - set(accepted))}

    def _structure(self, state, label):
        neighbours = {cell: set() for cell in state["cells"]}
        for a, b in state["edges"]:
            neighbours[a].add(b)
            neighbours[b].add(a)
        remaining, components = set(neighbours), 0
        while remaining:
            todo = [remaining.pop()]
            components += 1
            while todo:
                node = todo.pop()
                fresh = neighbours[node] & remaining
                remaining.difference_update(fresh)
                todo.extend(fresh)
        degrees = {}
        for cell in state["cells"]:
            degree = str(sum(a == cell for a, _ in state["edges"]))
            degrees[degree] = degrees.get(degree, 0) + 1
        births = state["counters"]["division_accepted"]
        return {"label": label, "turn": state["counters"]["turns"], "nodes": len(state["cells"]),
                "directed_edges": len(state["edges"]), "weak_components": components,
                "out_degree_histogram": degrees, "max_lineage_depth": max(x.count("-d") for x in state["cells"]),
                "births": births, "lineage_edge_fraction": 2 * births / len(state["edges"]) if state["edges"] else 0}

    def _envelope(self, contract, state, events, head):
        return {"policy_version": VERSION, "card_sha256": digest(self.card), "fixture_sha256": digest(self.fixture),
            "seed": self.seed, "arm": self.arm, "condition": self.condition,
            "contract_json": contract.to_json(), "policy_state": state, "policy_events": events, "head_hash": head}

    def _validate_joint(self, contract, state, events, head):
        owned_pairs = []
        for cell in state["cells"].values():
            if len(canonical(cell).encode()) > self.card["bounds"]["max_local_policy_bytes"]:
                raise ValueError("Local policy state exceeds byte limit")
            for oid, work in cell["owned"].items():
                owned_pairs.extend((oid, index) for index in work["shard"][work["cursor"]:])
        if len(owned_pairs) != len(set(owned_pairs)):
            raise Conflict("Remaining candidate shard ownership overlaps")
        if contract.summary()["units_used"] != state["counters"]["contract_units"] or contract.summary()["events"] != state["counters"]["contract_events"]:
            raise Conflict("Policy/contract accounting differs")
        if self._fits(state, {}):
            raise Conflict("Policy resource limit exceeded")
        for counter, bound in BOUND_KEYS.items():
            held = sum(value.get(counter, 0) for value in state["reserved_allowances"].values())
            if state["counters"][counter] + held > self.card["bounds"][bound]:
                raise Conflict("Counter exceeds card bound")
        if len(canonical(self._envelope(contract, state, events, head)).encode()) > self.card["bounds"]["max_joint_snapshot_bytes"]:
            raise ValueError("Joint snapshot exceeds byte limit")

    def _update_sizes(self, contract, state, events, head):
        """Canonical serialized sizes, not Python heap size or process RSS."""
        metrics = state["byte_metrics"]
        policy_bytes = len(canonical({k: v for k, v in state.items() if k != "byte_metrics"}).encode())
        contract_bytes = len(contract.to_json().encode())
        metrics.update(policy=policy_bytes, contract=contract_bytes,
                       peak_policy=max(metrics["peak_policy"], policy_bytes),
                       peak_contract=max(metrics["peak_contract"], contract_bytes))
        for _ in range(8):
            count = len(canonical(self._envelope(contract, state, events, head)).encode())
            if metrics["joint"] == count and metrics["peak_joint"] >= count:
                return
            metrics.update(joint=count, peak_joint=max(metrics["peak_joint"], count))
        raise ValueError("Snapshot-size accounting did not stabilize")

    def to_json(self):
        return canonical(self._envelope(self.contract, self.state, self.events, self.head))

    @classmethod
    def from_json(cls, text, card):
        if len(text.encode()) > card["bounds"]["max_joint_snapshot_bytes"]:
            raise ValueError("Joint snapshot exceeds byte limit")
        saved = strict_json(text)
        fields(saved, ("policy_version", "card_sha256", "fixture_sha256", "seed", "arm", "condition",
                       "contract_json", "policy_state", "policy_events", "head_hash"))
        if saved["policy_version"] != VERSION or saved["card_sha256"] != digest(card):
            raise Conflict("Policy/card version mismatch")
        result = cls(card, seed=saved["seed"], arm=saved["arm"], condition=saved["condition"])
        if saved["fixture_sha256"] != digest(result.fixture):
            raise Conflict("Fixture mismatch")
        limit = len(saved["policy_events"])
        while len(result.events) < limit:
            if not result.step():
                raise Conflict("Replay stops before saved event history")
        if result.to_json() != text:
            raise Conflict("Replayed joint state differs from saved snapshot")
        return result

    def run(self):
        started = time.monotonic()
        while self.step():
            pass
        report = self.report()
        report["wall_time_seconds_as_engineering_observation"] = time.monotonic() - started
        return report

    def report(self):
        expected = 7 if self.condition == "unsatisfiable" else 8
        terminal = self.state["terminal"]
        verified = len(terminal["verified_obligations"]) if terminal else 0
        fault_ok = self.state["fault_detected"] if self.condition in ("duplicate_replay", "stale_delivery") else True
        unsat_exhausted = all(work["cursor"] == len(work["shard"]) for cell in self.state["cells"].values()
            for oid, work in cell["owned"].items() if oid == "ob-007") and not any(
                item["candidate"]["obligation_id"] == "ob-007" for cell in self.state["cells"].values()
                for item in cell["unchecked"]) if self.condition == "unsatisfiable" else None
        return {"case_id": f"s{self.seed}-{self.arm}-{self.condition}", "seed": self.seed,
            "arm": self.arm, "condition": self.condition,
            "software_case_pass": verified == expected and fault_ok and unsat_exhausted is not False,
            "scientific_replication": False, "stop_reason": self.state["stop_reason"],
            "verified_obligations": verified, "terminal": terminal, "counters": clone(self.state["counters"]),
            "allocated_limits": clone(self.card["bounds"]), "unused_allowance": {
                counter: self.card["bounds"][bound] - self.state["counters"][counter] for counter, bound in BOUND_KEYS.items()},
            "distinct_constructed_pairs": len(self.state["constructed_pairs"]),
            "byte_metrics": clone(self.state["byte_metrics"]),
            "unsatisfiable_final_shard_exhausted": unsat_exhausted,
            "fault_injected": self.state["fault_injected"], "fault_detected": self.state["fault_detected"],
            "structure": self._structure(self.state, "report"), "activity": {
                cid: {"count": cell["activity_count"], "latest_window_count": len(cell["activity"]),
                      "fractions": {m: cell["activity"].count(m) / 8 for m in MODULES} if len(cell["activity"]) == 8 else None}
                for cid, cell in self.state["cells"].items()},
            "joint_snapshot_bytes": len(self.to_json().encode()), "snapshot_sha256": digest(json.loads(self.to_json()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", default="plans/cell-development-pilot-v0.json")
    parser.add_argument("--output", default="runs/cell-policy-fixture-v0")
    parser.add_argument("--resume", action="store_true", help="Validate and reuse completed cases from the same card/code")
    args = parser.parse_args()
    card = json.loads(Path(args.card).read_text())
    allocated = validate_card(card)
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    allocation_record = {"card_sha256": digest(card), "policy_version": VERSION,
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "allocated_cases": [{"seed": seed, "arm": arm, "condition": condition}
                            for seed, arm, condition in allocated]}
    allocation_path = destination / "allocation.json"
    if allocation_path.exists():
        if not args.resume or json.loads(allocation_path.read_text()) != allocation_record:
            raise Conflict("Existing allocation requires --resume with exactly the same card/code")
    else:
        if any(destination.glob("s*-*.json")):
            raise Conflict("Case files exist without a verifiable allocation")
        allocation_path.write_text(json.dumps(allocation_record, indent=2) + "\n")
    reports = []
    for seed, arm, condition in allocated:
        case_id = f"s{seed}-{arm}-{condition}"
        path = destination / (case_id + ".json")
        snapshot_path = destination / (case_id + ".snapshot.json")
        if path.exists():
            if not args.resume:
                raise FileExistsError("Do not overwrite an existing fixture case")
            existing = json.loads(path.read_text())
            if existing.get("card_sha256") != digest(card):
                raise Conflict("Completed case card identity mismatch")
            if "exception" not in existing:
                saved = snapshot_path.read_text()
                restored = PolicyFixture.from_json(saved, card)
                if restored.report()["snapshot_sha256"] != existing["snapshot_sha256"]:
                    raise Conflict("Completed case does not match its terminal snapshot")
            reports.append(existing)
            continue
        runner = PolicyFixture(card, seed=seed, arm=arm, condition=condition)
        try:
            if snapshot_path.exists():
                if not args.resume:
                    raise Conflict("Orphaned snapshot requires explicit --resume")
                snapshot = snapshot_path.read_text()
                runner = PolicyFixture.from_json(snapshot, card)
                if runner.next_action() is not None:
                    raise Conflict("Only terminal orphaned snapshots can be recovered here")
                report = runner.report()
                report["wall_time_seconds_as_engineering_observation"] = None
                report["recovered_terminal_snapshot"] = True
            else:
                report = runner.run()
                snapshot = runner.to_json()
            restored = PolicyFixture.from_json(snapshot, card)
            report["replay_equal"] = restored.to_json() == snapshot and restored.next_action() == runner.next_action()
            if not snapshot_path.exists():
                snapshot_path.write_text(snapshot)
        except Exception as exc:
            report = {"case_id": case_id, "seed": seed, "arm": arm, "condition": condition,
                      "software_case_pass": False, "exception": type(exc).__name__, "reason": str(exc),
                      "scientific_replication": False}
        report["card_sha256"] = digest(card)
        path.write_text(json.dumps(report, indent=2) + "\n")
        reports.append(report)
    summary = {"policy_version": VERSION, "card_sha256": digest(card), "allocated": len(allocated),
               "reported": len(reports), "software_pass": sum(x["software_case_pass"] for x in reports),
               "replay_equal": sum(x.get("replay_equal", False) for x in reports),
               "exceptions": sum("exception" in x for x in reports),
               "resource_stops": sum(x.get("stop_reason", "").startswith("limit:") for x in reports),
               "cases": reports, "scientific_efficacy_claim": False}
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))


if __name__ == "__main__":
    main()
