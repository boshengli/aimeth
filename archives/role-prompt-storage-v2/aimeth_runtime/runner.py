"""Bounded workers and a deliberately simple, frozen demonstration policy."""
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from urllib import error, request
from urllib.parse import urlsplit

from .store import Conflict, canonical


POLICY = "candidate-broadcast.v1"


def code_identity():
    root = Path(__file__).parent
    value = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        value.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + value.hexdigest()


def demo_manifest(agents=4, rounds=2):
    names = [f"a{i:05d}" for i in range(agents)]
    return {
        "schema_version": "1.0", "agents": names, "rounds": rounds,
        "identities": {"model": "deterministic-mock.v1", "task": "synthetic-plumbing.v1",
                       "policy": POLICY, "code": code_identity()},
        "model_name": "mock", "transport": {"kind": "mock"}, "seed": 914,
        "temperature": 0, "top_p": 1, "max_output_tokens": 256,
        "max_attempts": 3, "max_inflight": 4,
        "max_messages_per_step": 1, "max_message_chars": 4096,
        "base_messages": [{"role": "system", "content": "Return a candidate explanation. This is an engineering fixture, not mathematical evidence."}],
        "round_edges": {str(r): [[a, names[(i+1) % agents]] for i,a in enumerate(names)]
                        if agents > 1 and r < rounds-1 else [] for r in range(rounds)},
    }


def mock_response(claim):
    return {"id": "mock-" + claim["step_id"], "model": "mock",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Synthetic candidate for " + claim["step_id"]}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "synthetic": True}


class TransportFailure(Exception):
    def __init__(self, category, retryable, status=None):
        self.details = {"category": category, "http_status": status}
        self.retryable = retryable
        super().__init__(category)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_response(claim, transport):
    """OpenAI-compatible /chat/completions endpoint; no hidden transport retries."""
    endpoint = transport["endpoint"]
    parts = urlsplit(endpoint)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Use an explicit HTTP(S) endpoint without embedded credentials or query parameters")
    timeout = transport["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise ValueError("Set timeout_seconds in (0, 3600]")
    headers = {"Content-Type": "application/json"}
    credential = os.environ.get("AIMETH_API_KEY")
    if credential:
        headers["Authorization"] = "Bearer " + credential
    req = request.Request(endpoint, data=canonical(claim["request"]).encode(), headers=headers, method="POST")
    # Direct local-cluster transport; process proxy variables cannot silently reroute a frozen endpoint.
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(256 * 1024 + 1)
            if len(body) > 256 * 1024:
                raise TransportFailure("response_exceeds_256_KiB", False)
            try:
                return json.loads(body, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            except (ValueError, UnicodeDecodeError):
                raise TransportFailure("invalid_json", False) from None
    except error.HTTPError as exc:
        # Do not journal headers, credentials or an uncontrolled error-body echo.
        status = exc.code
        exc.close()
        raise TransportFailure("http_error", status in (408, 429) or 500 <= status < 600, status) from None
    except (error.URLError, TimeoutError, socket.timeout, ConnectionError):
        raise TransportFailure("network_or_timeout", True) from None


def validate_worker(config, allow_model_calls=False):
    if config["identities"]["code"] != code_identity():
        raise Conflict("Worker code differs from the frozen run; create a new run for code changes")
    if config["identities"]["policy"] != POLICY:
        raise Conflict("This worker only implements the frozen candidate-broadcast.v1 policy")
    if config["max_messages_per_step"]>8 or config["max_message_chars"]>8192:
        raise ValueError("Built-in worker limits: <=8 messages and <=8192 characters per message")
    if config["transport"]["kind"] != "mock" and not allow_model_calls:
        raise ValueError("Live transport requires explicit --allow-model-calls")


class Worker:
    def __init__(self, store, run_id, *, allow_model_calls=False):
        self.store=store; self.run_id=run_id
        self.config=store.manifest(run_id)
        validate_worker(self.config,allow_model_calls)
        self.routes={}
        for r,edges in self.config["round_edges"].items():
            for sender,recipient in edges: self.routes.setdefault((int(r),sender),[]).append(recipient)

    def one(self, worker_id):
        store=self.store; run_id=self.run_id; config=self.config; transport=config["transport"]
        claim = store.claim(run_id, worker_id, lease_seconds=transport.get("timeout_seconds", 30) + 30)
        if claim is None:
            return None
        try:
            response = mock_response(claim) if transport["kind"] == "mock" else http_response(claim, transport)
        except TransportFailure as exc:
            result = store.fail(claim["token"], exc.details, retryable=exc.retryable)
            # A small worker-local backoff; scheduler-wide Retry-After admission is not implemented.
            if exc.retryable:
                time.sleep(min(2 ** (claim["attempt_number"]-1), 8))
            return result
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        state = {"candidate": content, "proof_verification_status": "unverified"}
        # This policy transmits bounded candidate excerpts; the full response stays in the receipt/checkpoint.
        peer_state={"candidate_excerpt":content[:max(0,config["max_message_chars"]-128)] if isinstance(content,str) else None,
                    "proof_verification_status":"unverified"}
        while len(canonical(peer_state))>config["max_message_chars"] and peer_state.get("candidate_excerpt"):
            peer_state["candidate_excerpt"]=peer_state["candidate_excerpt"][:len(peer_state["candidate_excerpt"])//2]
        outgoing = []
        if claim["round_index"] + 1 < config["rounds"]:
            outgoing = [{"recipient": recipient, "target_round": claim["round_index"] + 1, "content": peer_state}
                        for recipient in self.routes.get((claim["round_index"],claim["agent_id"]),[])]
        return store.complete(claim["token"], response, state, outgoing)


def work_one(store, run_id, worker_id, *, allow_model_calls=False):
    key=(run_id,allow_model_calls)
    if not hasattr(store,"_workers"): store._workers={}
    if key not in store._workers: store._workers[key]=Worker(store,run_id,allow_model_calls=allow_model_calls)
    return store._workers[key].one(worker_id)
