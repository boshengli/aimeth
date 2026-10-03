"""Durable admission accounting for a bounded, single-coordinator swarm.

Reservations are never refunded: a process failure cannot establish whether a
request reached the provider. Input counts must be supplied by the coordinator;
this ledger enforces their sum and does not claim to verify tokenization.
"""

import json
import math
import sqlite3
import time


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _usage(receipt):
    usage = receipt.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    values = []
    for key in ("total_tokens", "prompt_tokens", "completion_tokens"):
        count = usage.get(key)
        known = type(count) is int and count >= 0
        values.extend((int(known), count if known else 0))
    return values


class Budget:
    """A SQLite ledger with constant-time, transactional admission counters.

    ``reserve`` returns False only for an identical previous reservation; callers
    must not dispatch that attempt again. Admission refusal raises ValueError.
    Use one Budget connection per coordinator thread. SQLite serializes separate
    connections, but this is not a distributed/network-filesystem database.
    """

    def __init__(self, path, *, calls, input_tokens, output_tokens, deadline):
        settings = {
            "calls": _integer(calls, "calls", 1),
            "input_tokens": _integer(input_tokens, "input_tokens", 1),
            "output_tokens": _integer(output_tokens, "output_tokens", 1),
        }
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise ValueError("deadline must be a finite absolute timestamp")
        settings["deadline"] = float(deadline)
        self._settings = settings
        self.db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS reservations (
                token TEXT PRIMARY KEY, run_id TEXT NOT NULL,
                input_count INTEGER NOT NULL, output_cap INTEGER NOT NULL,
                receipt TEXT)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS counters (
                id INTEGER PRIMARY KEY CHECK(id=1),
                reserved_calls INTEGER NOT NULL,
                reserved_input_tokens INTEGER NOT NULL,
                reserved_output_tokens INTEGER NOT NULL,
                settled_attempts INTEGER NOT NULL,
                known_usage_attempts INTEGER NOT NULL,
                known_total_tokens INTEGER NOT NULL,
                known_input_usage_attempts INTEGER NOT NULL,
                known_input_tokens INTEGER NOT NULL,
                known_output_usage_attempts INTEGER NOT NULL,
                known_output_tokens INTEGER NOT NULL)""")
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT value FROM settings WHERE id=1").fetchone()
            encoded = _canonical(settings)
            if row is not None and row[0] != encoded:
                raise ValueError("Frozen budget settings changed")
            self.db.execute("INSERT OR IGNORE INTO settings VALUES(1,?)", (encoded,))
            self.db.execute("INSERT OR IGNORE INTO counters VALUES(1,0,0,0,0,0,0,0,0,0,0)")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise

    @property
    def settings(self):
        return dict(self._settings)

    def reserve(self, token, run_id, input_count, output_cap):
        _identity(token, "token")
        _identity(run_id, "run_id")
        _integer(input_count, "input_count")
        _integer(output_cap, "output_cap", 1)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute(
                "SELECT run_id,input_count,output_cap FROM reservations WHERE token=?",
                (token,),
            ).fetchone()
            if old is not None:
                if old != (run_id, input_count, output_cap):
                    raise ValueError("Reservation identity conflict")
                self.db.commit()
                return False
            calls, inputs, outputs = self.db.execute(
                "SELECT reserved_calls,reserved_input_tokens,reserved_output_tokens FROM counters WHERE id=1"
            ).fetchone()
            if (calls + 1 > self._settings["calls"]
                    or inputs + input_count > self._settings["input_tokens"]
                    or outputs + output_cap > self._settings["output_tokens"]
                    or time.time() >= self._settings["deadline"]):
                raise ValueError("Admission budget or deadline exceeded")
            self.db.execute("INSERT INTO reservations VALUES(?,?,?,?,NULL)",
                            (token, run_id, input_count, output_cap))
            self.db.execute("""UPDATE counters SET reserved_calls=reserved_calls+1,
                reserved_input_tokens=reserved_input_tokens+?,
                reserved_output_tokens=reserved_output_tokens+? WHERE id=1""",
                            (input_count, output_cap))
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def settle(self, token, receipt):
        _identity(token, "token")
        if not isinstance(receipt, dict) or set(receipt) - {"usage", "error"}:
            raise ValueError("Receipt accepts only usage and error fields")
        value = _canonical(receipt)
        usage = _usage(receipt)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT receipt FROM reservations WHERE token=?", (token,)).fetchone()
            if old is None:
                raise ValueError("Unknown reservation")
            if old[0] is not None:
                if old[0] != value:
                    raise ValueError("Conflicting settlement")
                self.db.commit()
                return
            self.db.execute("UPDATE reservations SET receipt=? WHERE token=?", (value, token))
            self.db.execute("""UPDATE counters SET
                settled_attempts=settled_attempts+1,
                known_usage_attempts=known_usage_attempts+?,
                known_total_tokens=known_total_tokens+?,
                known_input_usage_attempts=known_input_usage_attempts+?,
                known_input_tokens=known_input_tokens+?,
                known_output_usage_attempts=known_output_usage_attempts+?,
                known_output_tokens=known_output_tokens+? WHERE id=1""", usage)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def summary(self):
        cursor = self.db.execute("SELECT * FROM counters WHERE id=1")
        result = dict(zip((item[0] for item in cursor.description), cursor.fetchone()))
        del result["id"]
        result["pending_attempts"] = result["reserved_calls"] - result["settled_attempts"]
        for known, unknown in (("known_usage_attempts", "unknown_usage_attempts"),
                               ("known_input_usage_attempts", "unknown_input_usage_attempts"),
                               ("known_output_usage_attempts", "unknown_output_usage_attempts")):
            result[unknown] = result["reserved_calls"] - result[known]
        result["settings"] = self.settings
        result["input_token_accounting"] = "caller_supplied"
        result["reservations_refunded"] = False
        return result

    def close(self):
        self.db.close()
