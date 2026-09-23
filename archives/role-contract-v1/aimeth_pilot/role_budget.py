"""Atomic request-byte/output reservations and a separately labelled usage stop."""
import json
import math
import sqlite3
import time

from aimeth_runtime.store import canonical, positive


class RoleBudget:
    def __init__(self, path, *, calls, output_tokens, input_bytes, request_bytes,
                 observed_token_stop, deadline):
        for key, value in [('calls', calls), ('output_tokens', output_tokens),
                           ('input_bytes', input_bytes), ('request_bytes', request_bytes),
                           ('observed_token_stop', observed_token_stop)]:
            positive(value, key)
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
            raise ValueError('Finite absolute deadline required')
        self.settings = dict(calls=calls, output_tokens=output_tokens, input_bytes=input_bytes,
                             request_bytes=request_bytes, observed_token_stop=observed_token_stop, deadline=deadline)
        self.deadline = deadline
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS reservations (token TEXT PRIMARY KEY, run_id TEXT NOT NULL, output_cap INTEGER NOT NULL, input_bytes INTEGER NOT NULL, receipt TEXT)')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT value FROM settings WHERE id=1').fetchone()
            if row and row[0] != canonical(self.settings):
                raise ValueError('Frozen budget changed')
            self.db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (canonical(self.settings),))
            self.db.commit()
        except BaseException:
            self.db.rollback(); self.db.close(); raise

    def reserve(self, token, run_id, output_cap, request_size):
        positive(output_cap, 'output_cap'); positive(request_size, 'request_size')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT run_id,output_cap,input_bytes FROM reservations WHERE token=?', (token,)).fetchone()
            if row:
                if row != (run_id, output_cap, request_size):
                    raise ValueError('Reservation identity conflict')
                self.db.commit(); return False
            summary = self.summary()
            if (summary['reserved_calls'] >= self.settings['calls']
                    or summary['reserved_output_tokens'] + output_cap > self.settings['output_tokens']
                    or summary['reserved_input_bytes'] + request_size > self.settings['input_bytes']
                    or request_size > self.settings['request_bytes']
                    or summary['known_total_tokens'] >= self.settings['observed_token_stop']
                    or time.time() >= self.deadline):
                raise ValueError('Admission budget or deadline exceeded')
            self.db.execute('INSERT INTO reservations VALUES(?,?,?,?,NULL)', (token, run_id, output_cap, request_size))
            self.db.commit(); return True
        except BaseException:
            self.db.rollback(); raise

    def settle(self, token, receipt):
        value = canonical(receipt)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT receipt FROM reservations WHERE token=?', (token,)).fetchone()
            if row is None:
                raise ValueError('Unknown reservation')
            if row[0] is not None and row[0] != value:
                raise ValueError('Conflicting settlement')
            self.db.execute('UPDATE reservations SET receipt=? WHERE token=?', (value, token))
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise

    def reconcile(self, store, run_id):
        """A committed journal receipt survives a crash before ledger settlement."""
        for event in store.events(run_id):
            if event['kind'] not in ('attempt.received', 'attempt.late_received'):
                continue
            token = event['attempt_id']
            if not self.db.execute('SELECT 1 FROM reservations WHERE token=?', (token,)).fetchone():
                continue  # Local admission rejection never dispatched a request.
            receipt = event['payload']['receipt']; response = receipt.get('response')
            self.settle(token, {'usage': response.get('usage') if isinstance(response, dict) else None,
                                'error': receipt.get('error')})

    def summary(self):
        rows = self.db.execute('SELECT output_cap,input_bytes,receipt FROM reservations').fetchall()
        usages = [json.loads(r[2]).get('usage') if r[2] else None for r in rows]
        valid = [u for u in usages if isinstance(u, dict) and type(u.get('total_tokens')) is int and u['total_tokens'] >= 0]
        return {'reserved_calls': len(rows), 'reserved_output_tokens': sum(r[0] for r in rows),
                'reserved_input_bytes': sum(r[1] for r in rows),
                'known_total_tokens': sum(u['total_tokens'] for u in valid),
                'unknown_usage_attempts': len(rows)-len(valid), 'settings': self.settings,
                'hard_input_token_cap': False, 'hard_input_request_byte_cap': True,
                'observed_token_stop_can_overshoot_by_inflight_requests': True, 'attributable_gpu_hours': None}
