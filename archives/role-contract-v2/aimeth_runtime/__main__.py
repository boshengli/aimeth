"""CLI for durable local agent runs; live inference requires an explicit flag."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from .runner import demo_manifest, validate_worker, work_one
from .store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "enqueue", "work", "recover", "status", "verify", "export", "demo"):
        p = sub.add_parser(name)
        p.add_argument("run_id")
        if name == "init": p.add_argument("manifest", type=Path)
        if name == "enqueue": p.add_argument("round_index", type=int)
        if name == "export": p.add_argument("destination", type=Path)
        if name == "demo":
            p.add_argument("--agents", type=int, default=4)
            p.add_argument("--rounds", type=int, default=2)
        if name == "work":
            p.add_argument("--worker-id", default=f"worker-{os.getpid()}")
            p.add_argument("--allow-model-calls", action="store_true")
            p.add_argument("--max-steps", type=int, default=100)
    p = sub.add_parser("backup"); p.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        with Store(args.db) as store:
            name = args.command
            if name == "init": result = {"fingerprint": store.create_run(args.run_id, json.loads(args.manifest.read_text()))}
            elif name == "enqueue": result = {"enqueued": store.enqueue_round(args.run_id, args.round_index)}
            elif name == "recover": result = {"expired_attempts_recovered": store.recover(args.run_id)}
            elif name == "verify": result = store.verify(args.run_id)
            elif name == "status": result = store.status(args.run_id)
            elif name == "backup": result = store.backup(args.destination)
            elif name == "export": result = store.export(args.run_id, args.destination)
            elif name == "work":
                if args.max_steps < 1: raise ValueError("max-steps must be positive")
                validate_worker(store.manifest(args.run_id), args.allow_model_calls)
                worked = 0
                while worked < args.max_steps and work_one(store, args.run_id, args.worker_id, allow_model_calls=args.allow_model_calls) is not None:
                    worked += 1
                result = {"worked_attempts": worked, **store.status(args.run_id)}
            else:
                if args.agents < 1 or args.rounds < 1: raise ValueError("agents and rounds must be positive")
                start = time.monotonic()
                store.create_run(args.run_id, demo_manifest(args.agents, args.rounds))
                for r in range(args.rounds):
                    store.enqueue_round(args.run_id, r)
                    while work_one(store, args.run_id, "demo") is not None: pass
                result = {**store.status(args.run_id), "verification": store.verify(args.run_id),
                          "elapsed_seconds": time.monotonic()-start, "model_calls": 0,
                          "scope": "Synthetic local persistence test; no model, GPU or mathematics evaluated"}
            print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
