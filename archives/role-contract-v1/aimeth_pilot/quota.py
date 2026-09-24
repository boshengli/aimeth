"""Conservative durable reservations: dispatched/unknown attempts never refund."""
import json
import sqlite3
import time

class Quota:
    def __init__(self, path, *, calls, output_tokens, deadline):
        self.db=sqlite3.connect(str(path),timeout=30)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS reservations (token TEXT PRIMARY KEY, run_id TEXT, output_cap INTEGER, receipt TEXT)')
        settings=json.dumps([calls,output_tokens,deadline])
        row=self.db.execute('SELECT value FROM settings WHERE id=1').fetchone()
        if row and row[0]!=settings:raise ValueError('Cannot change frozen experiment quota')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(settings,));self.db.commit()
        self.calls=calls;self.output_tokens=output_tokens;self.deadline=deadline
    def reserve(self, token, run_id, cap):
        if type(cap) is not int or cap<1:raise ValueError('Positive output reservation required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT run_id,output_cap FROM reservations WHERE token=?',(token,)).fetchone()
            if prior:
                if prior!=(run_id,cap):raise ValueError('Reservation identity conflict')
                self.db.commit();return False
            count,total=self.db.execute('SELECT COUNT(*),COALESCE(SUM(output_cap),0) FROM reservations').fetchone()
            if count>=self.calls or total+cap>self.output_tokens or time.time()>=self.deadline:
                raise ValueError('Experiment quota exhausted or deadline reached')
            self.db.execute('INSERT INTO reservations VALUES(?,?,?,NULL)',(token,run_id,cap));self.db.commit();return True
        except BaseException:
            self.db.rollback();raise
    def settle(self,token,receipt):
        text=json.dumps(receipt,sort_keys=True,allow_nan=False)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT receipt FROM reservations WHERE token=?',(token,)).fetchone()
            if row is None:raise ValueError('Unknown reservation')
            if row[0] is not None and row[0]!=text:raise ValueError('Conflicting receipt')
            self.db.execute('UPDATE reservations SET receipt=? WHERE token=?',(text,token));self.db.commit()
        except BaseException:self.db.rollback();raise
    def summary(self):
        rows=self.db.execute('SELECT output_cap,receipt FROM reservations').fetchall()
        usages=[json.loads(r[1]).get('usage') if r[1] else None for r in rows]
        known=[u for u in usages if isinstance(u,dict) and type(u.get('total_tokens')) is int]
        return {'reserved_calls':len(rows),'reserved_output_tokens':sum(r[0] for r in rows),
                'known_total_tokens':sum(u['total_tokens'] for u in known),
                'unknown_usage_attempts':len(rows)-len(known),'calls_cap':self.calls,
                'output_cap':self.output_tokens,'deadline':self.deadline,
                'input_token_cap_enforced':False,'dedicated_gpu_hours':None}
