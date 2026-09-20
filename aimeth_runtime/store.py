"""Single-host transactional event journal, fenced work, checkpoints and outbox."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid


class Conflict(ValueError):
    """An identity, immutable input, or lease disagrees with durable state."""


class NotReady(ValueError):
    """A round cannot open before its predecessor completes successfully."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def positive(value, name, maximum=None):
    if type(value) is not int or value < 1 or (maximum and value > maximum):
        raise ValueError(f"{name} must be a positive integer" + (f" <= {maximum}" if maximum else ""))


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value):
        raise ValueError("Identifiers must contain 1–100 ASCII letters, digits, dots, underscores or hyphens")


def validate_manifest(manifest):
    if manifest.get("schema_version") != "1.0":
        raise ValueError("Unsupported run manifest version")
    canonical(manifest)
    for key in ("model", "task", "policy", "code"):
        if not isinstance(manifest.get("identities", {}).get(key), str) or not manifest["identities"][key]:
            raise ValueError(f"Missing {key} identity")
    agents = manifest.get("agents")
    if not isinstance(agents, list) or not agents or len(agents) != len(set(agents)):
        raise ValueError("Agents must be a nonempty unique list")
    for agent in agents:
        identity(agent)
    for key in ("rounds", "max_attempts", "max_inflight", "max_output_tokens", "max_messages_per_step", "max_message_chars"):
        positive(manifest.get(key), key)
    if type(manifest.get("seed")) is not int:
        raise ValueError("A sampling master seed is required")
    if not isinstance(manifest.get("model_name"), str) or not manifest["model_name"]:
        raise ValueError("A model name is required")
    messages = manifest.get("base_messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Frozen base_messages are required")
    for message in messages:
        if message.get("role") not in ("system", "user", "assistant") or not isinstance(message.get("content"), str):
            raise ValueError("Invalid base message")
    per_agent = manifest.get("agent_base_messages")
    if per_agent is not None:
        if not isinstance(per_agent, dict) or set(per_agent) != set(agents):
            raise ValueError("Per-agent messages must cover exactly the declared agents")
        for messages_for_agent in per_agent.values():
            if not isinstance(messages_for_agent, list) or not messages_for_agent:
                raise ValueError("Per-agent messages must be nonempty lists")
            for message in messages_for_agent:
                if (not isinstance(message, dict) or set(message) != {"role", "content"}
                        or message["role"] not in ("system", "user", "assistant")
                        or not isinstance(message["content"], str)):
                    raise ValueError("Invalid per-agent message")
    if manifest.get("context_mode", "recorded.v1") not in ("recorded.v1", "none.v1"):
        raise ValueError("Unknown request context mode")
    if manifest.get("context_mode") == "none.v1" and (manifest["rounds"] != 1 or any(manifest.get("round_edges", {}).values())):
        raise ValueError("Context omission is restricted to one-step, edgeless diagnostics")
    if manifest.get("transport", {}).get("kind") not in ("mock", "openai"):
        raise ValueError("Declare mock or openai transport in the manifest")
    if manifest["transport"]["kind"]=="openai":
        from urllib.parse import urlsplit
        endpoint=manifest["transport"].get("endpoint","")
        parts=urlsplit(endpoint)
        if parts.scheme not in ("http","https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Freeze a credential-free HTTP(S) endpoint")
        timeout=manifest["transport"].get("timeout_seconds")
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=3600:
            raise ValueError("Freeze timeout_seconds in (0, 3600]")
    for parameter in ("temperature", "top_p"):
        value = manifest.get(parameter)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid {parameter}")
    if not 0 <= manifest["temperature"] <= 2 or not 0 < manifest["top_p"] <= 1:
        raise ValueError("Sampling parameters out of range")
    options = manifest.get("request_options", {})
    if not isinstance(options, dict) or set(options) - {"chat_template_kwargs", "response_format", "thinking"}:
        raise ValueError("Only declared provider-format options may extend a request")
    if any(not isinstance(value, dict) for value in options.values()) or len(canonical(options)) > 2048:
        raise ValueError("Provider options must be bounded JSON objects")
    agent_set = set(agents)
    graph = manifest.get("round_edges")
    if not isinstance(graph, dict) or set(graph) != {str(i) for i in range(manifest["rounds"])}:
        raise ValueError("Declare directed round_edges for every source round")
    for edges in graph.values():
        if not isinstance(edges, list):
            raise ValueError("Edges must be a list")
        seen = set()
        for edge in edges:
            if not isinstance(edge, list) or len(edge) != 2 or any(x not in agent_set for x in edge) or edge[0] == edge[1]:
                raise ValueError("Invalid directed communication edge")
            if tuple(edge) in seen:
                raise ValueError("Duplicate communication edge")
            seen.add(tuple(edge))
    def check_secrets(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in {"api_key", "authorization", "password", "access_token", "secret"}:
                    raise ValueError("Credentials belong in the environment, not a run manifest")
                check_secrets(child)
        elif isinstance(value, list):
            for child in value:
                check_secrets(child)
    check_secrets(manifest)


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, manifest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, run_id TEXT NOT NULL REFERENCES runs,
 kind TEXT NOT NULL, agent_id TEXT, step_id TEXT, attempt_id TEXT, round_index INTEGER,
 worker_id TEXT, utc TEXT NOT NULL, monotonic_ns INTEGER NOT NULL, process_id INTEGER NOT NULL,
 parents TEXT NOT NULL, payload TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
 event_key TEXT NOT NULL, UNIQUE(run_id,event_key));
CREATE INDEX IF NOT EXISTS events_run_seq ON events(run_id,seq);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable journal'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable journal'); END;
CREATE TABLE IF NOT EXISTS steps(
 run_id TEXT NOT NULL REFERENCES runs, step_id TEXT NOT NULL, agent_id TEXT NOT NULL, round_index INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','running','succeeded','failed')),
 request TEXT NOT NULL, request_hash TEXT NOT NULL, created_event TEXT NOT NULL REFERENCES events(event_id),
 attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_until REAL, canonical_event TEXT REFERENCES events(event_id),
 PRIMARY KEY(run_id,step_id), UNIQUE(run_id,agent_id,round_index));
CREATE INDEX IF NOT EXISTS pending_steps ON steps(run_id,status,round_index,step_id);
CREATE TABLE IF NOT EXISTS attempts(
 token TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL, number INTEGER NOT NULL,
 worker_id TEXT NOT NULL, status TEXT NOT NULL, deadline REAL NOT NULL, started_event TEXT NOT NULL REFERENCES events(event_id),
 receipt_hash TEXT, receipt_event TEXT REFERENCES events(event_id),
 FOREIGN KEY(run_id,step_id) REFERENCES steps, UNIQUE(run_id,step_id,number));
CREATE TABLE IF NOT EXISTS checkpoints(
 run_id TEXT NOT NULL, agent_id TEXT NOT NULL, round_index INTEGER NOT NULL, step_id TEXT NOT NULL,
 state TEXT NOT NULL, state_hash TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES events(event_id),
 PRIMARY KEY(run_id,agent_id,round_index), FOREIGN KEY(run_id,step_id) REFERENCES steps);
CREATE TRIGGER IF NOT EXISTS checkpoints_no_update BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT,'immutable checkpoint'); END;
CREATE TRIGGER IF NOT EXISTS checkpoints_no_delete BEFORE DELETE ON checkpoints BEGIN SELECT RAISE(ABORT,'immutable checkpoint'); END;
CREATE TABLE IF NOT EXISTS messages(
 message_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs, sender TEXT NOT NULL, recipient TEXT NOT NULL,
 source_round INTEGER NOT NULL, target_round INTEGER NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL,
 sent_event TEXT NOT NULL REFERENCES events(event_id), bound_step TEXT, bound_event TEXT REFERENCES events(event_id),
 consumed_event TEXT REFERENCES events(event_id));
CREATE INDEX IF NOT EXISTS message_inbox ON messages(run_id,target_round,recipient);
CREATE TRIGGER IF NOT EXISTS message_content_immutable
 BEFORE UPDATE OF message_id,run_id,sender,recipient,source_round,target_round,content,content_hash,sent_event ON messages
 BEGIN SELECT RAISE(ABORT,'immutable message'); END;
CREATE TRIGGER IF NOT EXISTS messages_no_delete BEFORE DELETE ON messages BEGIN SELECT RAISE(ABORT,'immutable message'); END;
"""


class Store:
    """One connection per thread/process. Use local durable storage, never a shared network mount."""
    def __init__(self, path, *, clock=time.time):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        self._manifests = {}
        self._edge_indexes = {}
        self.clock = clock
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        # Rollback journal avoids shared-memory WAL assumptions and the WAL-reset bug in affected SQLite builds.
        mode = self.db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if mode != "delete":
            raise ValueError("Expected rollback-journal mode")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA fullfsync=ON")
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES('schema_version','1')")
        if self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] != "1":
            raise ValueError("Unsupported database schema")

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def _run(self, run_id):
        if run_id in self._manifests:
            return self._manifests[run_id]
        row = self.db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        self._manifests[run_id] = json.loads(row["manifest"])
        return self._manifests[run_id]

    def manifest(self, run_id):
        return json.loads(canonical(self._run(run_id)))

    def _event(self, run_id, kind, payload, *, key, parents=(), agent=None, step=None, attempt=None, round_index=None, worker=None):
        text = canonical(payload)
        if len(text.encode()) > 2 * 1024 * 1024:
            raise ValueError("Event payload exceeds 2 MiB; use a separately hashed artifact")
        parents = list(dict.fromkeys(parents))
        for parent in parents:
            row = self.db.execute("SELECT run_id FROM events WHERE event_id=?", (parent,)).fetchone()
            if row is None or row[0] != run_id:
                raise Conflict("Event parent is missing or belongs to another run")
        previous = self.db.execute("SELECT event_hash FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 1", (run_id,)).fetchone()
        record = dict(event_id=str(uuid.uuid4()), run_id=run_id, kind=kind, agent_id=agent, step_id=step,
                      attempt_id=attempt, round_index=round_index, worker_id=worker,
                      utc=datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(), monotonic_ns=time.monotonic_ns(),
                      process_id=os.getpid(), parents=parents, payload=payload,
                      prev_hash=previous[0] if previous else "0" * 64, event_key=key)
        event_hash = digest(record)
        columns = list(record) + ["event_hash"]
        stored = {**record, "parents":canonical(parents), "payload":text, "event_hash":event_hash}
        self.db.execute(f"INSERT INTO events({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", [stored[c] for c in columns])
        return record["event_id"]

    def create_run(self, run_id, manifest):
        identity(run_id)
        validate_manifest(manifest)
        fingerprint = digest(manifest)
        with self._tx():
            prior = self.db.execute("SELECT fingerprint FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise Conflict("Run identity already exists with a different frozen manifest")
                return fingerprint
            self.db.execute("INSERT INTO runs VALUES(?,?,?)", (run_id, fingerprint, canonical(manifest)))
            self._event(run_id, "run.created", {"fingerprint":fingerprint, "manifest":manifest}, key="run.created")
        return fingerprint

    def enqueue_round(self, run_id, round_index):
        with self._tx():
            config = self._run(run_id)
            if type(round_index) is not int or not 0 <= round_index < config["rounds"]:
                raise ValueError("Round index outside frozen run")
            existing = self.db.execute("SELECT COUNT(*) FROM steps WHERE run_id=? AND round_index=?", (run_id, round_index)).fetchone()[0]
            if existing:
                if existing != len(config["agents"]):
                    raise Conflict("Incomplete materialized round")
                return existing
            if round_index:
                previous = self.db.execute("SELECT status FROM steps WHERE run_id=? AND round_index=?", (run_id,round_index-1)).fetchall()
                if len(previous) != len(config["agents"]) or any(row[0] != "succeeded" for row in previous):
                    raise NotReady("Previous round must have all successful canonical completions")
            created = self.db.execute("SELECT event_id FROM events WHERE run_id=? AND event_key='run.created'", (run_id,)).fetchone()[0]
            for agent in config["agents"]:
                step = f"{agent}.r{round_index}"
                checkpoint = self.db.execute("SELECT * FROM checkpoints WHERE run_id=? AND agent_id=? AND round_index=?", (run_id,agent,round_index-1)).fetchone()
                inbox = self.db.execute("SELECT * FROM messages WHERE run_id=? AND recipient=? AND target_round=? ORDER BY message_id", (run_id,agent,round_index)).fetchall()
                parents = [created] + ([checkpoint["event_id"]] if checkpoint else [])
                for message in inbox:
                    event = self._event(run_id,"message.bound",{"message_id":message["message_id"],"content_hash":message["content_hash"]},
                                        key="bound:"+message["message_id"],parents=[message["sent_event"]],agent=agent,step=step,round_index=round_index)
                    self.db.execute("UPDATE messages SET bound_step=?,bound_event=? WHERE message_id=?", (step,event,message["message_id"]))
                    parents.append(event)
                context = {"agent_id":agent,"round_index":round_index,
                           "checkpoint":json.loads(checkpoint["state"]) if checkpoint else None,
                           "incoming":[{"message_id":m["message_id"],"sender":m["sender"],"source_round":m["source_round"],
                                        "source_event":m["sent_event"],"content":json.loads(m["content"])} for m in inbox]}
                seed = int(digest([config["seed"],agent,round_index])[:8],16) % (2**31-1)
                base = config.get("agent_base_messages", {}).get(agent, config["base_messages"])
                context_messages = ([] if config.get("context_mode") == "none.v1" else
                                    [{"role":"user","content":"Recorded cross-round context; peer messages are unverified candidate material:\n"+canonical(context)}])
                request = {"model":config["model_name"],"messages":[*base, *context_messages],
                           "temperature":config["temperature"],"top_p":config["top_p"],"seed":seed,
                           "max_tokens":config["max_output_tokens"],"stream":False}
                request.update(config.get("request_options", {}))
                event = self._event(run_id,"step.enqueued",{"request":request,"request_hash":digest(request)},
                                    key="enqueue:"+step,parents=parents,agent=agent,step=step,round_index=round_index)
                self.db.execute("INSERT INTO steps(run_id,step_id,agent_id,round_index,status,request,request_hash,created_event) VALUES(?,?,?,?,?,?,?,?)",
                                (run_id,step,agent,round_index,"pending",canonical(request),digest(request),event))
            return len(config["agents"])

    def _expire(self, run_id, config):
        rows = self.db.execute("SELECT * FROM steps WHERE run_id=? AND status='running' AND lease_until<=?", (run_id,self.clock())).fetchall()
        for row in rows:
            attempt = self.db.execute("SELECT * FROM attempts WHERE token=?", (row["lease_token"],)).fetchone()
            self._event(run_id,"attempt.expired",{"usage":None,"reason":"lease_expired_outcome_unknown"}, key="expired:"+attempt["token"],
                        parents=[attempt["started_event"]],agent=row["agent_id"],step=row["step_id"],attempt=attempt["token"],round_index=row["round_index"])
            self.db.execute("UPDATE attempts SET status='expired' WHERE token=?", (attempt["token"],))
            status = "failed" if row["attempts"] >= config["max_attempts"] else "pending"
            self.db.execute("UPDATE steps SET status=?,lease_token=NULL,lease_until=NULL WHERE run_id=? AND step_id=?", (status,run_id,row["step_id"]))
        return len(rows)

    def recover(self, run_id):
        with self._tx():
            return self._expire(run_id,self._run(run_id))

    def claim(self, run_id, worker_id, lease_seconds=60):
        identity(worker_id)
        if isinstance(lease_seconds,bool) or not isinstance(lease_seconds,(int,float)) or not math.isfinite(lease_seconds) or lease_seconds<=0:
            raise ValueError("Lease duration must be finite and positive")
        with self._tx():
            config=self._run(run_id)
            self._expire(run_id,config)
            if self.db.execute("SELECT COUNT(*) FROM steps WHERE run_id=? AND status='running'",(run_id,)).fetchone()[0]>=config["max_inflight"]:
                return None
            row=self.db.execute("SELECT * FROM steps WHERE run_id=? AND status='pending' ORDER BY round_index,step_id LIMIT 1",(run_id,)).fetchone()
            if row is None:
                return None
            token=str(uuid.uuid4())
            deadline=self.clock()+lease_seconds
            number=row["attempts"]+1
            event=self._event(run_id,"attempt.started",{"request_hash":row["request_hash"],"lease_until":deadline,"attempt_number":number},
                              key="attempt:"+token,parents=[row["created_event"]],agent=row["agent_id"],step=row["step_id"],attempt=token,round_index=row["round_index"],worker=worker_id)
            self.db.execute("INSERT INTO attempts(token,run_id,step_id,number,worker_id,status,deadline,started_event) VALUES(?,?,?,?,?,'running',?,?)",
                            (token,run_id,row["step_id"],number,worker_id,deadline,event))
            self.db.execute("UPDATE steps SET status='running',attempts=?,lease_token=?,lease_until=? WHERE run_id=? AND step_id=?",(number,token,deadline,run_id,row["step_id"]))
            return {"token":token,"run_id":run_id,"step_id":row["step_id"],"agent_id":row["agent_id"],"round_index":row["round_index"],"attempt_number":number,"request":json.loads(row["request"]),"lease_until":deadline}

    def heartbeat(self, token, lease_seconds=60):
        if isinstance(lease_seconds,bool) or not isinstance(lease_seconds,(int,float)) or not math.isfinite(lease_seconds) or lease_seconds<=0:
            raise ValueError("Invalid lease duration")
        with self._tx():
            a=self.db.execute("SELECT * FROM attempts WHERE token=?",(token,)).fetchone()
            if a is None:
                raise KeyError(token)
            s=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_id=?",(a["run_id"],a["step_id"])).fetchone()
            if s["lease_token"]!=token or s["status"]!="running" or s["lease_until"]<=self.clock():
                raise Conflict("Expired or superseded lease")
            deadline=max(s["lease_until"],self.clock()+lease_seconds)
            self.db.execute("UPDATE steps SET lease_until=? WHERE run_id=? AND step_id=?",(deadline,a["run_id"],a["step_id"]))
            self.db.execute("UPDATE attempts SET deadline=? WHERE token=?",(deadline,token))
            self._event(a["run_id"],"attempt.heartbeat",{"lease_until":deadline},key="heartbeat:"+str(uuid.uuid4()),parents=[a["started_event"]],attempt=token,step=a["step_id"],worker=a["worker_id"])
            return deadline

    def _outgoing(self, config, step, outgoing):
        if not isinstance(outgoing,list) or len(outgoing)>config["max_messages_per_step"]:
            raise ValueError("Outgoing message quota exceeded")
        index_key=(step["run_id"],step["round_index"])
        if index_key not in self._edge_indexes:
            self._edge_indexes[index_key]={tuple(e) for e in config["round_edges"][str(step["round_index"])]}
        edges=self._edge_indexes[index_key]
        seen=set()
        for m in outgoing:
            recipient=m.get("recipient")
            target=m.get("target_round")
            if (step["agent_id"],recipient) not in edges:
                raise Conflict("Sender/recipient communication edge is not authorized")
            if type(target) is not int or not step["round_index"]<target<config["rounds"]:
                raise Conflict("A message must target a later configured round")
            if (recipient,target) in seen:
                raise Conflict("At most one message per recipient/target round per step")
            seen.add((recipient,target))
            if len(canonical(m.get("content")))>config["max_message_chars"]:
                raise ValueError("Message content exceeds quota")

    def complete(self, token, response, state, outgoing=()):
        return self._finish(token,{"response":response,"state":state,"outgoing":list(outgoing)},None,True)

    def fail(self, token, error, *, retryable=True):
        return self._finish(token,{"error":error,"usage":None},"transport_failed",retryable)

    def _finish(self, token, receipt, failure, retryable):
        receipt_hash=digest(receipt)
        with self._tx():
            attempt=self.db.execute("SELECT * FROM attempts WHERE token=?",(token,)).fetchone()
            if attempt is None:
                raise KeyError(token)
            if attempt["receipt_hash"]:
                if attempt["receipt_hash"]!=receipt_hash:
                    raise Conflict("The same attempt returned different receipts")
                return {"event_id":attempt["receipt_event"],"accepted":attempt["status"]=="succeeded","duplicate":True}
            run_id=attempt["run_id"]
            config=self._run(run_id)
            self._expire(run_id,config)
            step=self.db.execute("SELECT * FROM steps WHERE run_id=? AND step_id=?",(run_id,attempt["step_id"])).fetchone()
            active=step["status"]=="running" and step["lease_token"]==token and step["lease_until"]>self.clock()
            generation="not_received"
            if not failure:
                try:
                    choice=receipt["response"]["choices"][0]
                    content=choice["message"]["content"]
                    generation=choice.get("finish_reason") or "unknown"
                    if not isinstance(content,str) or not content.strip():
                        failure="empty_or_invalid_content"
                    elif generation!="stop":
                        failure="incomplete_generation"
                    elif not isinstance(receipt["state"],dict):
                        failure="invalid_checkpoint"
                    else:
                        self._outgoing(config,step,receipt["outgoing"])
                except (KeyError,IndexError,TypeError,AttributeError):
                    failure="invalid_response"
                except ValueError:
                    failure="invalid_checkpoint_or_outgoing"
            accepted=active and not failure
            event=self._event(run_id,"attempt.received" if active else "attempt.late_received",
                              {"receipt":receipt,"receipt_hash":receipt_hash,"transport_status":"failed" if "error" in receipt else "ok",
                               "generation_status":generation,"accepted":accepted,"failure":failure,"retryable":retryable,"proof_verification_status":"unverified"},
                              key="receipt:"+token,parents=[attempt["started_event"]],agent=step["agent_id"],step=step["step_id"],attempt=token,round_index=step["round_index"],worker=attempt["worker_id"])
            status="succeeded" if accepted else ("failed" if active else "expired")
            self.db.execute("UPDATE attempts SET status=?,receipt_hash=?,receipt_event=? WHERE token=?",(status,receipt_hash,event,token))
            if not active:
                return {"event_id":event,"accepted":False,"duplicate":False}
            if accepted:
                saved=self._event(run_id,"checkpoint.saved",{"state_hash":digest(receipt["state"]),"state":receipt["state"]},key="checkpoint:"+step["step_id"],parents=[event],agent=step["agent_id"],step=step["step_id"],attempt=token,round_index=step["round_index"])
                self.db.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?)",(run_id,step["agent_id"],step["round_index"],step["step_id"],canonical(receipt["state"]),digest(receipt["state"]),saved))
                for index,message in enumerate(receipt["outgoing"]):
                    message_id=digest([run_id,step["step_id"],index,message])
                    sent=self._event(run_id,"message.sent",{"message_id":message_id,"recipient":message["recipient"],"target_round":message["target_round"],"content_hash":digest(message["content"]),"content":message["content"]},key="message:"+message_id,parents=[event],agent=step["agent_id"],step=step["step_id"],attempt=token,round_index=step["round_index"])
                    self.db.execute("INSERT INTO messages(message_id,run_id,sender,recipient,source_round,target_round,content,content_hash,sent_event) VALUES(?,?,?,?,?,?,?,?,?)",
                                    (message_id,run_id,step["agent_id"],message["recipient"],step["round_index"],message["target_round"],canonical(message["content"]),digest(message["content"]),sent))
                self.db.execute("UPDATE messages SET consumed_event=? WHERE run_id=? AND bound_step=?",(event,run_id,step["step_id"]))
                next_status="succeeded"
            else:
                next_status="pending" if retryable and step["attempts"]<config["max_attempts"] else "failed"
            self.db.execute("UPDATE steps SET status=?,lease_token=NULL,lease_until=NULL,canonical_event=? WHERE run_id=? AND step_id=?",
                            (next_status,event if accepted else None,run_id,step["step_id"]))
            return {"event_id":event,"accepted":accepted,"duplicate":False}

    def observe(self, run_id, key, kind, payload, parents=()):
        if not kind.startswith("observation."):
            raise ValueError("External observations must use observation.* event types")
        with self._tx():
            self._run(run_id)
            prior=self.db.execute("SELECT * FROM events WHERE run_id=? AND event_key=?",(run_id,key)).fetchone()
            if prior:
                if prior["kind"]!=kind or prior["payload"]!=canonical(payload) or prior["parents"]!=canonical(list(dict.fromkeys(parents))):
                    raise Conflict("Observation key reused for different evidence")
                return prior["event_id"]
            return self._event(run_id,kind,payload,key=key,parents=parents)

    def events(self, run_id):
        for row in self.db.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq",(run_id,)):
            record=dict(row)
            record["parents"]=json.loads(record["parents"])
            record["payload"]=json.loads(record["payload"])
            yield record

    def status(self, run_id):
        config=self._run(run_id)
        counts={s:0 for s in ("pending","running","succeeded","failed")}
        counts.update(dict(self.db.execute("SELECT status,COUNT(*) FROM steps WHERE run_id=? GROUP BY status",(run_id,)).fetchall()))
        attempts=self.db.execute("SELECT COUNT(*) FROM attempts WHERE run_id=?",(run_id,)).fetchone()[0]
        known_tokens=0; unknown_usage_attempts=0
        for a in self.db.execute("SELECT receipt_event FROM attempts WHERE run_id=?",(run_id,)):
            event=self.db.execute("SELECT payload FROM events WHERE event_id=?",(a[0],)).fetchone() if a[0] else None
            response=json.loads(event[0])["receipt"].get("response",{}) if event else {}
            usage=response.get("usage") if isinstance(response,dict) else None
            total=usage.get("total_tokens") if isinstance(usage,dict) else None
            if type(total) is int and total>=0: known_tokens+=total
            else: unknown_usage_attempts+=1
        return {"run_id":run_id,"fingerprint":digest(config),"planned_total_steps":len(config["agents"])*config["rounds"],
                "materialized_steps":sum(counts.values()),"steps":counts,"attempts":attempts,
                "known_total_tokens":known_tokens,"unknown_usage_attempts":unknown_usage_attempts,
                "complete":counts["succeeded"]==len(config["agents"])*config["rounds"],
                "events":self.db.execute("SELECT COUNT(*) FROM events WHERE run_id=?",(run_id,)).fetchone()[0],
                "messages":self.db.execute("SELECT COUNT(*) FROM messages WHERE run_id=?",(run_id,)).fetchone()[0],
                "checkpoints":self.db.execute("SELECT COUNT(*) FROM checkpoints WHERE run_id=?",(run_id,)).fetchone()[0]}

    def verify(self, run_id):
        self.db.execute("BEGIN")
        try:
            if self.db.execute("PRAGMA quick_check").fetchone()[0]!="ok" or self.db.execute("PRAGMA foreign_key_check").fetchone():
                raise Conflict("SQLite integrity check failed")
            events=list(self.events(run_id)); by_id={}; previous="0"*64
            if not events:
                raise KeyError(run_id)
            for record in events:
                expected={k:v for k,v in record.items() if k not in ("seq","event_hash")}
                if record["prev_hash"]!=previous or digest(expected)!=record["event_hash"]:
                    raise Conflict("Journal hash chain mismatch")
                if any(parent not in by_id for parent in record["parents"]):
                    raise Conflict("Journal has an invalid causal parent")
                previous=record["event_hash"];by_id[record["event_id"]]=record
            config=json.loads(self.db.execute("SELECT manifest FROM runs WHERE run_id=?",(run_id,)).fetchone()[0])
            saved=self.db.execute("SELECT fingerprint FROM runs WHERE run_id=?",(run_id,)).fetchone()[0]
            if digest(config)!=saved or events[0]["payload"].get("manifest")!=config:
                raise Conflict("Frozen run identity changed")
            steps={r["step_id"]:r for r in self.db.execute("SELECT * FROM steps WHERE run_id=?",(run_id,))}
            attempts={r["token"]:r for r in self.db.execute("SELECT * FROM attempts WHERE run_id=?",(run_id,))}
            checkpoints={r["step_id"]:r for r in self.db.execute("SELECT * FROM checkpoints WHERE run_id=?",(run_id,))}
            messages={r["message_id"]:r for r in self.db.execute("SELECT * FROM messages WHERE run_id=?",(run_id,))}
            expected_counts={"step.enqueued":len(steps),"attempt.started":len(attempts),"checkpoint.saved":len(checkpoints),"message.sent":len(messages)}
            for kind,count in expected_counts.items():
                if sum(e["kind"]==kind for e in events)!=count:
                    raise Conflict("Projection/event membership mismatch: "+kind)
            attempts_by_step={}; receipts_by_attempt={}
            for a in attempts.values(): attempts_by_step.setdefault(a["step_id"],[]).append(a)
            for e in events:
                if e["kind"] in ("attempt.received","attempt.late_received"): receipts_by_attempt.setdefault(e["attempt_id"],[]).append(e)
            for row in steps.values():
                created=by_id[row["created_event"]]
                if created["kind"]!="step.enqueued" or created["step_id"]!=row["step_id"] or created["agent_id"]!=row["agent_id"] or created["round_index"]!=row["round_index"]:
                    raise Conflict("Step identity changed")
                if digest(json.loads(row["request"]))!=row["request_hash"] or created["payload"]["request_hash"]!=row["request_hash"]:
                    raise Conflict("Task request changed")
                local_attempts=attempts_by_step.get(row["step_id"],[])
                if row["attempts"]!=len(local_attempts): raise Conflict("Attempt count changed")
                if row["canonical_event"]:
                    completion=by_id[row["canonical_event"]]
                    if completion["step_id"]!=row["step_id"] or not completion["payload"].get("accepted"):
                        raise Conflict("Invalid canonical completion")
                if (row["status"]=="succeeded")!=(row["canonical_event"] is not None) or (row["status"]=="succeeded")!=(row["step_id"] in checkpoints):
                    raise Conflict("Canonical completion/status/checkpoint mismatch")
                if row["status"]=="running":
                    lease=attempts.get(row["lease_token"])
                    if not lease or lease["status"]!="running" or lease["step_id"]!=row["step_id"] or lease["deadline"]!=row["lease_until"]:
                        raise Conflict("Active lease changed")
                elif row["lease_token"] is not None or row["lease_until"] is not None:
                    raise Conflict("Inactive step has a lease")
                if row["status"] in ("pending","failed"):
                    latest=max(local_attempts,key=lambda a:a["number"]) if local_attempts else None
                    if latest is None: expected_status="pending"
                    else:
                        if latest["status"] not in ("expired","failed"): raise Conflict("Inactive step has an active/completed attempt")
                        retryable=by_id[latest["receipt_event"]]["payload"]["retryable"] if latest["status"]=="failed" else True
                        expected_status="pending" if retryable and row["attempts"]<config["max_attempts"] else "failed"
                    if row["status"]!=expected_status: raise Conflict("Retry state changed")
            for a in attempts.values():
                started=by_id[a["started_event"]]
                if started["kind"]!="attempt.started" or started["attempt_id"]!=a["token"] or started["step_id"]!=a["step_id"] or started["worker_id"]!=a["worker_id"] or started["payload"]["attempt_number"]!=a["number"]:
                    raise Conflict("Attempt identity changed")
                receipts=receipts_by_attempt.get(a["token"],[])
                if len(receipts)!=int(a["receipt_event"] is not None): raise Conflict("Receipt membership changed")
                if receipts:
                    receipt=receipts[0]
                    if receipt["event_id"]!=a["receipt_event"] or digest(receipt["payload"]["receipt"])!=a["receipt_hash"] or receipt["payload"]["receipt_hash"]!=a["receipt_hash"]:
                        raise Conflict("Receipt changed")
                    expected="succeeded" if receipt["payload"]["accepted"] else ("expired" if receipt["kind"]=="attempt.late_received" else "failed")
                    if a["status"]!=expected: raise Conflict("Attempt status changed")
                elif a["status"] not in ("running","expired"):
                    raise Conflict("Unrecorded attempt outcome")
            for row in checkpoints.values():
                event=by_id[row["event_id"]]; step=steps[row["step_id"]]
                if digest(json.loads(row["state"]))!=row["state_hash"] or event["payload"]["state_hash"]!=row["state_hash"]:
                    raise Conflict("Checkpoint changed")
                if event["kind"]!="checkpoint.saved" or event["step_id"]!=row["step_id"] or event["agent_id"]!=row["agent_id"] or event["round_index"]!=row["round_index"] or event["parents"]!=[step["canonical_event"]]:
                    raise Conflict("Checkpoint provenance changed")
                receipt=by_id[step["canonical_event"]]["payload"]["receipt"]
                if digest(receipt["state"])!=row["state_hash"]: raise Conflict("Checkpoint differs from receipt")
            for row in messages.values():
                sent=by_id[row["sent_event"]]
                if digest(json.loads(row["content"]))!=row["content_hash"] or sent["payload"]["content_hash"]!=row["content_hash"]:
                    raise Conflict("Message changed")
                if sent["kind"]!="message.sent" or sent["agent_id"]!=row["sender"] or sent["round_index"]!=row["source_round"] or sent["payload"]["message_id"]!=row["message_id"] or sent["payload"]["recipient"]!=row["recipient"] or sent["payload"]["target_round"]!=row["target_round"]:
                    raise Conflict("Message route changed")
                if row["bound_event"]:
                    bound=by_id[row["bound_event"]]; target=steps[row["bound_step"]]
                    if bound["kind"]!="message.bound" or bound["step_id"]!=row["bound_step"] or bound["parents"]!=[row["sent_event"]] or target["agent_id"]!=row["recipient"] or target["round_index"]!=row["target_round"]:
                        raise Conflict("Message binding changed")
                    if row["bound_event"] not in by_id[target["created_event"]]["parents"]:
                        raise Conflict("Message provenance missing from request")
                    context=json.loads(json.loads(target["request"])["messages"][-1]["content"].split("\n",1)[1])
                    match=[m for m in context["incoming"] if m["message_id"]==row["message_id"]]
                    if len(match)!=1 or digest(match[0]["content"])!=row["content_hash"]:
                        raise Conflict("Message absent from recorded request")
                    if row["consumed_event"]!=target["canonical_event"]:
                        raise Conflict("Message consumption changed")
                elif row["bound_step"] or row["consumed_event"]:
                    raise Conflict("Unbound message was consumed")
            result={"status":"verified","events":len(events),"tail_hash":previous,"scientific_validity_checked":False}
            self.db.execute("COMMIT")
            return result
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def backup(self, destination):
        destination=Path(destination).resolve()
        destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=destination.with_name(destination.name+"."+uuid.uuid4().hex+".tmp")
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        try:
            target=sqlite3.connect(temporary)
            try:
                self.db.backup(target)
                if target.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                    raise Conflict("Backup integrity failed")
            finally:
                target.close()
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            os.link(temporary,destination)  # Atomic publication, refuses to overwrite an existing checkpoint file.
            fd=os.open(destination.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path":str(destination),"sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}

    def export(self, run_id, destination):
        destination=Path(destination)
        destination.mkdir(parents=True,exist_ok=False,mode=0o700)
        # Export from a consistent SQLite backup; the live writer may continue independently.
        self.backup(destination/"snapshot.sqlite")
        with Store(destination/"snapshot.sqlite") as snapshot:
            verification=snapshot.verify(run_id)
            (destination/"events.jsonl").write_text("".join(canonical(e)+"\n" for e in snapshot.events(run_id)))
            tables={table:[dict(r) for r in snapshot.db.execute(f"SELECT * FROM {table} WHERE run_id=?",(run_id,))] for table in ("runs","steps","attempts","checkpoints","messages")}
            (destination/"state.json").write_text(canonical(tables)+"\n")
            (destination/"verification.json").write_text(canonical(verification)+"\n")
        artifacts=[]
        for p in sorted(destination.iterdir()):
            if p.is_file():
                artifacts.append({"id":p.name,"path":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
        (destination/"manifest.json").write_text(canonical({"schema_version":"1.0","run_id":run_id,"artifacts":artifacts})+"\n")
        return verification
