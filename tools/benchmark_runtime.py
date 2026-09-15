#!/usr/bin/env python3
"""Single-worker synthetic persistence load; never a model/GPU benchmark."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aimeth_runtime import Store
from aimeth_runtime.runner import code_identity, demo_manifest, work_one


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--agents",type=int,default=10000)
    args=parser.parse_args()
    if args.agents<1: parser.error("agents must be positive")
    if args.db.exists() or args.output.exists(): parser.error("Use new database/output paths to preserve prior evidence")
    start=time.monotonic(); started=datetime.now(timezone.utc).isoformat()
    config=demo_manifest(args.agents,2)
    with Store(args.db) as store:
        store.create_run("synthetic-load",config)
        round_records=[]
        for r in range(2):
            tick=time.monotonic(); store.enqueue_round("synthetic-load",r)
            while work_one(store,"synthetic-load","single-mock-worker") is not None: pass
            round_records.append({"round":r,"elapsed_seconds":time.monotonic()-tick})
            print(json.dumps({"round_completed":r,**round_records[-1]}),flush=True)
        status=store.status("synthetic-load")
        verification=store.verify("synthetic-load")
        pragmas={name:store.db.execute("PRAGMA "+name).fetchone()[0] for name in ("journal_mode","synchronous","fullfsync")}
    elapsed=time.monotonic()-start
    result={"schema_version":"1.0","started_utc":started,"code_identity":code_identity(),
            "environment":{"python":platform.python_version(),"sqlite":sqlite3.sqlite_version,"os":platform.system(),"os_release":platform.release(),"architecture":platform.machine()},
            "design":{"logical_agents":args.agents,"rounds":2,"worker_processes":1,"repetitions":1,"transport":"mock","comparison_arms":0},
            "sqlite_pragmas":pragmas,"status":status,"verification":verification,"rounds":round_records,
            "elapsed_seconds":elapsed,"canonical_steps_per_second":status["steps"]["succeeded"]/elapsed,
            "database_bytes":args.db.stat().st_size,"database_sha256":hashlib.sha256(args.db.read_bytes()).hexdigest(),
            "external_model_calls":0,"cluster_jobs":0,"proof_verified":False,
            "scope":"Single-host synthetic persistence check; no inference, scientific comparison, power-loss or cluster validation"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
