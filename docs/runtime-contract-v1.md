# Durable runtime v0.1 — implemented contract

Engineering milestone M1.1, 2026-09-15. M2 remains the organization-design milestone. This document supersedes the runtime-implementation status of M1; it does not alter its archived evidence or the proposed research protocol.

## Scope and guarantees

`aimeth_runtime` is a standard-library, single-host, multiprocess execution core. Logical agents are durable records, not 10,000 OS processes. Each worker owns a SQLite connection. Put the database on local durable storage; do not put it in iCloud, NFS, a shared cluster filesystem, or a container's disposable layer. A cluster deployment should expose one host-local coordinator or introduce a separately validated server database.

The implementation uses explicit `BEGIN IMMEDIATE` transactions, rollback journal `DELETE`, `synchronous=FULL`, foreign keys, and macOS `fullfsync=ON`. SQLite documents the durability modes and filesystem assumptions; successful process-kill tests do not establish tolerance of power loss, faulty storage or an unavailable host. [SQLite transactions](https://sqlite.org/lang_transaction.html), [PRAGMA synchronous](https://sqlite.org/pragma.html#pragma_synchronous), [Python sqlite3](https://docs.python.org/3/library/sqlite3.html).

| Invariant | Implemented behavior | Evidence |
|---|---|---|
| Frozen identity | A run ID maps to one canonical manifest hash. Changing task, model identity, policy, code, sampling, graph, agents or limits requires a new run. The built-in worker checks its actual Python source digest before claiming. | Identity and worker tests |
| Observable trace | Immutable request, response or bounded transport-error record; attempt, agent, round, worker, process, UTC and monotonic timestamps; causal parent IDs and SHA-256 journal chain. | Journal, receipt and request tests |
| One canonical result | A lease token fences each attempt. Identical receipts return the existing event. Conflicting repeats fail. Superseded receipts remain recorded but cannot change canonical state. | Duplicate, expiry and multiprocess tests |
| Atomic result | Accepted receipt, checkpoint, outgoing messages, incoming-message consumption and step success commit together. | SIGKILL inside transaction and after commit |
| Restart | Claims expire, retain an unknown-outcome record and become eligible for a bounded retry; completed steps remain complete. | SIGKILL after claim; restore test |
| Cross-round provenance | A later request contains its own last checkpoint and authorized inbox messages. `sent → bound → canonical receipt` is linked by event IDs and exact content hashes. | Two-round provenance test |
| No silent completion | Empty, malformed or truncated output is recorded without a checkpoint or round advancement. Exhausted/terminal failures block the next round. | Generation, route and retry tests |
| Inspectable export | Online backup, no-overwrite atomic snapshot publication; consistent JSONL events, state tables, verification and artifact hashes from that snapshot. | Backup/restore/export test |

The journal is append-only through this API and SQLite triggers. Its hash chain detects disagreement with a retained tail hash; a privileged attacker able to replace the database and every external anchor can rewrite history. Export tail hashes to reviewed Git records or a separate immutable store when publishing evidence. Verification checks journal/projection consistency, not the truth or completeness of mathematical claims. Retain externally observed prompts, responses, tool calls, verifier output and interventions; no inaccessible model-internal reasoning is required.

## State and delivery semantics

`pending → running → succeeded`, or `running → pending/failed` after a recorded failure/expiry. `max_attempts` bounds all attempts, including timeouts and process deaths. `max_inflight` is shared by all workers of a run. A strict round barrier admits round r+1 only when every configured step in r has a canonical success. An idempotent enqueue cannot materialize half a round.

Each attempt starts with a committed request hash and lease before inference. If a worker dies after the server generated an answer but before local receipt commit, the answer and its cost may be unknown; retry can generate a second server call. We guarantee at most one canonical **local commit**, not exactly-once external inference. Missing usage remains unknown and is counted separately; it is never converted to a claim of zero spend.

`message.bound` means the exact message entered the recorded next-round request. `consumed_event` means that request obtained its canonical result. Neither proves the model understood or used the message. Messages can target a later configured round; sender/recipient edges, per-step count and content length are checked. All candidate material remains unverified.

The included `candidate-broadcast.v1` worker uses the same model for every step and sends a bounded candidate excerpt to configured next-round neighbors. Its full response remains in the receipt/checkpoint. It is a plumbing fixture and a replaceable policy, not the final S/I/L/X organization experiment. The worker currently caps policy configuration at 8 outgoing messages and 8,192 serialized characters per message; the Store API supports other validated quotas. The exact policy and source digest are frozen in each run.

## HTTP adapter and limits

The optional adapter sends a non-streaming OpenAI-compatible chat-completions JSON request to a manifest-frozen endpoint, including `seed`, sampling parameters and output-token limit. It uses an environment credential `AIMETH_API_KEY`, never stores the credential, disables redirects and process-environment proxies, and performs no hidden HTTP retries. Use a trusted local inference network or HTTPS; configure network routing explicitly outside this first adapter.

401/400 and other terminal HTTP errors are retained as terminal attempt failures; 408/429/5xx and connection/timeouts are retryable within `max_attempts`. Error headers/body echoes are not journaled. The adapter limits response bodies to 256 KiB and records an explicit rejection for larger, invalid-JSON or nonfinite responses. Store event payloads are bounded at 2 MiB: callers of the general API must keep evidence below that bound or supply separately archived hashed artifacts; arbitrary attachment ingestion is not implemented. The built-in policy keeps normal receipts bounded.

The socket timeout is not an absolute wall-time deadline for a server that slowly streams bytes. Lease fencing still prevents an expired result from winning; supervision must terminate stuck workers. Store heartbeats are available to integrations, but this bounded-request adapter does not renew leases during a request. There is worker-local exponential backoff, not scheduler-wide Retry-After admission.

## Readiness boundaries

Locally implemented and fault-tested: event persistence, checkpoint recovery, cross-round causal links, bounded worker concurrency, strict generation status, snapshots and trace verification. The 10K check is synthetic and measures this host/storage/software combination, with one sequential mock worker and two rounds; it is not a comparative benchmark or GPU estimate.

Not established: H20/server/container compatibility; Slurm integration; multi-host HA; network partition or real power-loss behavior; long-duration operation; metrics/alerting service; global token/GPU-time reservation; scheduler-wide cancellation/rate limits; source/model attestation by a real inference server; formal proof verification; independent scientific reproduction. A source hash or seed alone does not make stochastic inference reproducible.

M2 can now design policies against concrete event/state/message interfaces. Cluster pilot admission still requires frozen model/task/verifier identities, resource accounting, deployment facts and operational fault tests. Those are separate engineering and scientific gates, not inferred from passing unit tests.
