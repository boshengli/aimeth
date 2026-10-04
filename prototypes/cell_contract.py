"""Offline, single-writer computational-cell contract; not a runtime policy.

Uses the runtime's canonical JSON/identity helpers without changing its code
identity. Resource units below are synthetic transition units, not API tokens.
"""
import json
import math
import re

from aimeth_runtime.store import Conflict, canonical, digest, identity


MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024


def clone(value):
    return json.loads(canonical(value))


def integer(value, name, minimum=0, maximum=1_000_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Unexpected or missing fields")


def sha256(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected SHA-256 digest")


class CellContract:
    """Bounded in-memory transitions with validated replay and explicit duplicates.

    No durable storage, locks, network, models, scheduler or scientific evaluator.
    Callers must persist snapshots atomically before relying on recovery.
    """
    def __init__(self, *, modules, seeds, edges, limits):
        fields(limits, ("max_population", "max_units", "max_events", "max_neighbours", "max_payload_bytes"))
        for name, maximum in (("max_population", 10_000), ("max_units", 1_000_000_000),
                              ("max_events", 10_000), ("max_neighbours", 64),
                              ("max_payload_bytes", 65_536)):
            integer(limits[name], name, 1, maximum)
        if not isinstance(modules, list) or not 1 <= len(modules) <= 32:
            raise ValueError("Provide 1–32 module identifiers")
        for module in modules:
            identity(module)
        if len(set(modules)) != len(modules):
            raise ValueError("Duplicate modules")
        if not isinstance(seeds, list) or not 1 <= len(seeds) <= limits["max_population"]:
            raise ValueError("Invalid seed population")
        self._modules = list(modules)
        self._limits = clone(limits)
        self._cells = {}
        for seed in seeds:
            fields(seed, ("cell_id", "expression", "memory"))
            identity(seed["cell_id"])
            self._expression(seed["expression"])
            if not isinstance(seed["memory"], dict):
                raise ValueError("Memory must be a JSON object")
            self._bounded(seed["memory"])
            if seed["cell_id"] in self._cells:
                raise Conflict("Duplicate seed identity")
            self._cells[seed["cell_id"]] = {**clone(seed), "parent_id": None,
                "state_version": 0, "last_signal_id": None}
        self._edges = set()
        if not isinstance(edges, list):
            raise ValueError("Edges must be a list")
        for edge in edges:
            if (not isinstance(edge, list) or len(edge) != 2
                    or any(not isinstance(x, str) or x not in self._cells for x in edge)
                    or edge[0] == edge[1] or tuple(edge) in self._edges):
                raise ValueError("Invalid or duplicate directed edge")
            self._edges.add(tuple(edge))
        if any(sum(a == cell for a, _ in self._edges) > limits["max_neighbours"] for cell in self._cells):
            raise ValueError("Neighbour limit exceeded")
        # Reconstruct these indexes from the seed state and event history.
        self._birth_ticks = {cell: 0 for cell in self._cells}
        self._version_ticks = {cell: 0 for cell in self._cells}
        self._edge_ticks = {edge: 0 for edge in self._edges}
        self._initial = clone(dict(modules=modules, seeds=seeds, edges=edges, limits=limits))
        self._events, self._event_ids, self._signals = [], set(), {}
        self._signal_ticks = {}
        self._units, self._tick = 0, -1
        self._head = digest(self._initial)
        self.to_json()  # Seed state must fit the same replay bound as later states.

    def _bounded(self, value):
        if len(canonical(value).encode("utf-8")) > self._limits["max_payload_bytes"]:
            raise ValueError("Payload or memory exceeds byte limit")

    def _expression(self, expression):
        fields(expression, self._modules)
        for value in expression.values():
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Expression must be finite activation values in [0, 1]")

    def cell(self, cell_id):
        return clone(self._cells[cell_id])

    def state_hash(self, cell_id):
        return digest(self._cells[cell_id])

    def summary(self):
        return {"population": len(self._cells), "units_used": self._units,
                "events": len(self._events), "last_tick": self._tick,
                "checkpoint_sha256": self._head}

    def signal_hash(self, message_id):
        return digest(self._signals[message_id])

    def _ready(self, event_id, now, cost):
        identity(event_id)
        integer(now, "now")
        if event_id in self._event_ids:
            raise Conflict("Event already applied")
        if now < self._tick:
            raise Conflict("Event time precedes recorded state")
        if len(self._events) >= self._limits["max_events"]:
            raise Conflict("Event limit exhausted")
        if self._units + cost > self._limits["max_units"]:
            raise Conflict("Resource limit exhausted")

    def _record(self, event_id, kind, inputs, now, cost):
        event = {"event_id": event_id, "kind": kind, "inputs": clone(inputs),
                 "now": now, "cost_units": cost, "previous_hash": self._head}
        event["event_hash"] = digest(event)
        self._snapshot_json(self._events + [event], event["event_hash"])
        self._events.append(event)
        self._event_ids.add(event_id)
        self._head, self._tick = event["event_hash"], now
        self._units += cost

    def _payload(self, kind, payload):
        schemas = {"candidate": ("statement",), "constraint": ("constraint",),
                   "evidence": ("artifact_sha256",),
                   "obligation": ("obligation_id", "statement"),
                   "resource_request": ("units",)}
        if not isinstance(kind, str) or kind not in schemas:
            raise ValueError("Unknown signal kind")
        fields(payload, schemas[kind])
        self._bounded(payload)
        for key in ("statement", "constraint"):
            if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
                raise ValueError("Signal text must be nonempty")
        if "obligation_id" in payload:
            identity(payload["obligation_id"])
        if kind == "evidence":
            sha256(payload["artifact_sha256"])
        if kind == "resource_request":
            integer(payload["units"], "requested units", 1)

    def apply_signal(self, event_id, signal, *, now, expression=None):
        """Validate delivery and commit one receiver update for one resource unit."""
        self._ready(event_id, now, 1)
        fields(signal, ("message_id", "sender", "receiver", "sender_version", "receiver_version",
                        "kind", "payload", "parent_message_id", "parent_message_hash",
                        "created_tick", "expires_tick"))
        for key in ("message_id", "sender", "receiver"):
            identity(signal[key])
        if signal["message_id"] in self._signals:
            raise Conflict("Signal already applied")
        for key in ("sender_version", "receiver_version", "created_tick", "expires_tick"):
            integer(signal[key], key)
        sender, receiver = signal["sender"], signal["receiver"]
        if (sender, receiver) not in self._edges:
            raise Conflict("Delivery outside directed neighbourhood")
        if (signal["sender_version"] != self._cells[sender]["state_version"]
                or signal["receiver_version"] != self._cells[receiver]["state_version"]):
            raise Conflict("Stale sender or receiver state")
        if not signal["created_tick"] <= now < signal["expires_tick"]:
            raise Conflict("Signal is future-dated or expired")
        earliest_creation = max(self._birth_ticks[sender], self._birth_ticks[receiver],
                                self._version_ticks[sender], self._version_ticks[receiver],
                                self._edge_ticks[(sender, receiver)])
        if signal["created_tick"] < earliest_creation:
            raise Conflict("Signal predates endpoint identity, state version or edge")
        self._payload(signal["kind"], signal["payload"])
        parent_id = signal["parent_message_id"]
        if parent_id is None:
            if signal["parent_message_hash"] is not None:
                raise ValueError("Root signal cannot have parent hash")
        else:
            identity(parent_id)
            sha256(signal["parent_message_hash"])
            parent = self._signals.get(parent_id)
            if (parent is None or parent["receiver"] != sender
                    or digest(parent) != signal["parent_message_hash"]
                    or self._signal_ticks[parent_id] > signal["created_tick"]):
                raise Conflict("Parent signal is absent, unrelated or mismatched")
        updated = self.cell(receiver)
        if expression is not None:
            self._expression(expression)
            updated["expression"] = clone(expression)
        updated["state_version"] += 1
        updated["last_signal_id"] = signal["message_id"]
        # All validation precedes mutation. This is not a cross-process transaction.
        inputs = {"signal": clone(signal), "expression": clone(expression)}
        self._record(event_id, "signal", inputs, now, 1)
        self._cells[receiver] = updated
        self._version_ticks[receiver] = now
        self._signals[signal["message_id"]] = clone(signal)
        self._signal_ticks[signal["message_id"]] = now
        return self.cell(receiver)

    def divide(self, event_id, *, parent_id, child_id, expected_version, parent_state_hash, now):
        """Inherit a recorded parent snapshot and add reciprocal lineage edges."""
        self._ready(event_id, now, 2)
        identity(parent_id)
        identity(child_id)
        integer(expected_version, "expected_version")
        sha256(parent_state_hash)
        if parent_id not in self._cells or child_id in self._cells:
            raise Conflict("Absent parent or duplicate child")
        parent = self.cell(parent_id)
        if parent["state_version"] != expected_version or self.state_hash(parent_id) != parent_state_hash:
            raise Conflict("Parent snapshot changed")
        if len(self._cells) >= self._limits["max_population"]:
            raise Conflict("Population cap reached")
        if sum(a == parent_id for a, _ in self._edges) >= self._limits["max_neighbours"]:
            raise Conflict("Parent neighbourhood is full")
        child = {"cell_id": child_id, "parent_id": parent_id, "state_version": 0,
                 "expression": clone(parent["expression"]), "memory": clone(parent["memory"]),
                 "last_signal_id": None}
        inputs = dict(parent_id=parent_id, child_id=child_id, expected_version=expected_version,
                      parent_state_hash=parent_state_hash)
        self._record(event_id, "division", inputs, now, 2)
        parent["state_version"] += 1
        self._cells[parent_id], self._cells[child_id] = parent, child
        self._birth_ticks[child_id] = now
        self._version_ticks[parent_id] = self._version_ticks[child_id] = now
        self._edges.update(((parent_id, child_id), (child_id, parent_id)))
        self._edge_ticks[(parent_id, child_id)] = self._edge_ticks[(child_id, parent_id)] = now
        return self.cell(child_id)

    def _snapshot_json(self, events, head):
        text = canonical({"schema_version": "cell-contract.v0", "initial": self._initial,
                          "events": events, "head_hash": head})
        if len(text.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Snapshot exceeds 16 MiB")
        return text

    def to_json(self):
        return self._snapshot_json(self._events, self._head)

    @classmethod
    def from_json(cls, text):
        """Replay a saved envelope; hashes detect damage, not malicious rewriting."""
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise ValueError("Snapshot exceeds 16 MiB")
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON field")
                result[key] = value
            return result
        value = json.loads(text, object_pairs_hook=unique_object)
        fields(value, ("schema_version", "initial", "events", "head_hash"))
        if value["schema_version"] != "cell-contract.v0":
            raise ValueError("Unknown snapshot schema")
        fields(value["initial"], ("modules", "seeds", "edges", "limits"))
        result = cls(**value["initial"])
        if not isinstance(value["events"], list) or len(value["events"]) > result._limits["max_events"]:
            raise ValueError("Invalid event list")
        for event in value["events"]:
            fields(event, ("event_id", "kind", "inputs", "now", "cost_units", "previous_hash", "event_hash"))
            if event["kind"] == "signal":
                fields(event["inputs"], ("signal", "expression"))
                result.apply_signal(event["event_id"], now=event["now"], **event["inputs"])
            elif event["kind"] == "division":
                fields(event["inputs"], ("parent_id", "child_id", "expected_version", "parent_state_hash"))
                result.divide(event["event_id"], now=event["now"], **event["inputs"])
            else:
                raise ValueError("Unknown event kind")
            if canonical(result._events[-1]) != canonical(event):
                raise Conflict("Replayed event differs from saved event")
        if result._head != value["head_hash"]:
            raise Conflict("Checkpoint hash mismatch")
        return result
