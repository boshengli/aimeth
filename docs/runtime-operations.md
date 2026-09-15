# Runtime operations

Use Python 3.11+ from the repository root. No third-party Python packages are required. Database, backups and full traces stay in ignored `runs/` on local durable storage. The user has authorized a public GitHub repository for reviewed code, protocol and evidence; private run data is not implicitly public.

## Synthetic first run

```bash
python3 -m aimeth_runtime --db runs/demo.sqlite demo demo --agents 4 --rounds 2
python3 -m aimeth_runtime --db runs/demo.sqlite status demo
python3 -m aimeth_runtime --db runs/demo.sqlite verify demo
python3 -m aimeth_runtime --db runs/demo.sqlite backup runs/demo-backup-v1.sqlite
python3 -m aimeth_runtime --db runs/demo.sqlite export runs/demo-export-v1
python3 tools/verify_artifacts.py runs/demo-export-v1/manifest.json
```

Re-running `demo` with the same code/config/database is idempotent for completed steps. If code/config changed, use a new run ID and database. The example is deterministic synthetic text with no model requests, no proof checking and synthetic zero token counts.

## Explicit control and restart

Generate a manifest tied to the current source:

```bash
mkdir -p runs
python3 -c 'import json; from aimeth_runtime.runner import demo_manifest; print(json.dumps(demo_manifest(4, 2), indent=2))' > runs/manifest.json
python3 -m aimeth_runtime --db runs/pilot.sqlite init pilot runs/manifest.json
python3 -m aimeth_runtime --db runs/pilot.sqlite enqueue pilot 0
python3 -m aimeth_runtime --db runs/pilot.sqlite work pilot --worker-id w1 --max-steps 100
python3 -m aimeth_runtime --db runs/pilot.sqlite enqueue pilot 1
python3 -m aimeth_runtime --db runs/pilot.sqlite work pilot --worker-id w1 --max-steps 100
```

For multiple workers, launch the `work` command in separate processes with different worker IDs, sharing the same **host-local** database. The frozen `max_inflight` applies across them. `work` exits when no claim is available or its step limit is reached; it is not a perpetual scheduler. A coordinator advances rounds after checking complete success.

After an interrupted process, reopen the same database with the same manifest/source. `recover RUN` explicitly expires leases whose recorded deadline has passed; `work` also does this when claiming. Do not force-expire a valid lease: a surviving worker may still return. Inspect `status` and `verify`, then continue pending work. Lease timing assumes a reasonably synchronized local wall clock; a forward/backward clock jump can affect retry timing but token fencing remains authoritative.

Restore a backup by selecting the backup's path (or a copied path) as `--db`; verify it, expire old leases and continue there. Do not run the original and restored database as competing authoritative coordinators for one experiment. A backup taken before a response commit cannot know whether that external request completed; preserve this uncertainty in analysis. Backups and export destinations refuse overwrites. Export is restricted by a mode-0700 directory; review and redact content before sharing.

`verify` reads journal and projections in one transaction and validates integrity/causal relationships. Use a snapshot for large offline checks so lengthy readers do not delay the rollback-journal writer. Export stores all database runs in `snapshot.sqlite`, while its JSONL/state selection concerns the named run: review the entire snapshot before sharing, or keep one run per database. No existing database is destructively repaired.

## Real local inference — deployment gate

Freeze actual weights/tokenizer/task/policy/code identities, replace transport with `{"kind":"openai","endpoint":"http://<trusted-local-server>:<port>/v1/chat/completions","timeout_seconds":120}`, and use the actual server model name. Keep `AIMETH_API_KEY` in the invoking environment if needed. `work --allow-model-calls` is required. This documentation is a recipe; no live server or GPU was invoked for M1.1.

Before cluster use, implement/validate whole-run resource reservations, operational monitoring, job supervision and the M2 policy/evaluator boundary. The manifest's output-token/per-attempt limits and max-inflight do not constitute a complete compute-budget guarantee.

## Validation and records

```bash
python3 -m unittest discover -s tests -v
python3 tools/verify_artifacts.py archives/foundation-v1/foundation-manifest.json
python3 tools/verify_artifacts.py examples/replay/manifest.json
python3 tools/benchmark_runtime.py --db runs/load.sqlite --output runs/load-summary.json --agents 10000
```

The test suite kills three disposable child processes, uses four concurrent workers and serves a temporary loopback HTTP fixture. It contacts no external inference service. The benchmark refuses an existing database, preserves its synthetic journal, records source identity/environment/elapsed time and verifies the final state. Keep reviewed summaries and small synthetic examples in Git; keep production databases and credentials out.
