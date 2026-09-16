import copy
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from aimeth_runtime import Conflict, NotReady, Store
from aimeth_runtime.runner import demo_manifest, mock_response, validate_worker, work_one


def finish(store, claim, outgoing=()):
    return store.complete(claim["token"], mock_response(claim), {"candidate": claim["step_id"]}, outgoing)


def child_drain(path, ready, index):
    try:
        with Store(path) as store:
            while True:
                claim = store.claim("run", f"worker-{index}", 30)
                if claim:
                    time.sleep(0.002)
                    finish(store, claim)
                elif store.status("run")["complete"]:
                    break
                else:
                    time.sleep(0.01)
        ready.send(None)
    except BaseException as exc:
        ready.send(repr(exc))


def child_crash(path, pipe, phase):
    class PausedStore(Store):
        def _event(self, *args, **kwargs):
            result = super()._event(*args, **kwargs)
            if phase == "inside_commit" and args[1] == "checkpoint.saved":
                pipe.send("inside_transaction")
                time.sleep(60)
            return result
    with PausedStore(path, clock=lambda: 100) as store:
        claim = store.claim("run", "crashing-worker", 5)
        if phase == "after_claim":
            pipe.send("claimed")
        else:
            finish(store, claim, [{"recipient":"a00001", "target_round":1, "content":{"candidate":"x"}}])
            pipe.send("committed_without_ack")
        time.sleep(60)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite"
        self.now = 100.0
        self.store = Store(self.path, clock=lambda: self.now)
        self.config = demo_manifest(2, 2)
        self.store.create_run("run", self.config)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def claim(self):
        self.store.enqueue_round("run", 0)
        return self.store.claim("run", "worker", 5)

    def test_frozen_identity_and_no_secret_manifest(self):
        self.assertEqual(self.store.create_run("run", self.config), self.store.status("run")["fingerprint"])
        changed = copy.deepcopy(self.config); changed["seed"] += 1
        with self.assertRaises(Conflict): self.store.create_run("run", changed)
        changed = copy.deepcopy(self.config); changed["transport"]["api_key"] = "fixture"
        with self.assertRaises(ValueError): self.store.create_run("secret", changed)

    def test_worker_identity_is_checked_before_claim(self):
        config = copy.deepcopy(self.config); config["identities"]["code"] = "different"
        self.store.create_run("changed", config); self.store.enqueue_round("changed", 0)
        with self.assertRaises(Conflict): work_one(self.store, "changed", "worker")
        self.assertEqual(self.store.status("changed")["attempts"], 0)

    def test_round_barrier_and_idempotent_materialization(self):
        with self.assertRaises(NotReady): self.store.enqueue_round("run", 1)
        self.assertEqual(self.store.enqueue_round("run", 0), 2)
        self.assertEqual(self.store.enqueue_round("run", 0), 2)
        self.assertEqual(self.store.status("run")["events"], 3)
        with self.assertRaises(NotReady): self.store.enqueue_round("run", 1)

    def test_atomic_message_checkpoint_and_recorded_next_request(self):
        claim = self.claim()
        output = [{"recipient":"a00001", "target_round":1, "content":{"candidate":"peer"}}]
        finish(self.store, claim, output)
        finish(self.store, self.store.claim("run", "worker", 5))
        self.store.enqueue_round("run", 1)
        second = None
        for _ in range(2):
            next_claim = self.store.claim("run", "worker", 5)
            if next_claim["agent_id"] == "a00001": second = next_claim
            finish(self.store, next_claim)
        context = json.loads(second["request"]["messages"][-1]["content"].split("\n",1)[1])
        self.assertEqual(context["incoming"][0]["content"], {"candidate":"peer"})
        self.assertEqual(context["checkpoint"], {"candidate":"a00001.r0"})
        self.assertIsInstance(second["request"]["seed"], int)
        message = self.store.db.execute("SELECT * FROM messages").fetchone()
        self.assertIsNotNone(message["bound_event"]); self.assertIsNotNone(message["consumed_event"])
        self.assertTrue(self.store.status("run")["complete"])
        self.store.verify("run")

    def test_duplicate_receipt_and_conflicting_repeat(self):
        claim = self.claim(); accepted = finish(self.store, claim)
        duplicate = finish(self.store, claim)
        self.assertTrue(duplicate["duplicate"]); self.assertEqual(accepted["event_id"],duplicate["event_id"])
        with self.assertRaises(Conflict): self.store.complete(claim["token"], mock_response(claim), {"changed":True})
        self.assertEqual(self.store.status("run")["checkpoints"],1)

    def test_expired_worker_cannot_overwrite_new_attempt(self):
        first = self.claim(); self.now += 6
        self.assertEqual(self.store.recover("run"),1)
        second = self.store.claim("run", "replacement", 5)
        self.assertEqual(first["step_id"], second["step_id"])
        self.assertFalse(finish(self.store,first)["accepted"])
        self.assertTrue(finish(self.store,second)["accepted"])
        self.assertEqual(self.store.status("run")["checkpoints"],1)
        self.assertEqual(sum(e["kind"] == "attempt.late_received" for e in self.store.events("run")),1)
        self.store.verify("run")

    def test_heartbeat_and_global_inflight_limit(self):
        config = copy.deepcopy(self.config); config["max_inflight"] = 1
        self.store.create_run("limit",config); self.store.enqueue_round("limit",0)
        first = self.store.claim("limit","worker",5)
        self.assertIsNone(self.store.claim("limit","second",5))
        self.now += 4; self.store.heartbeat(first["token"],5); self.now += 2
        self.assertEqual(self.store.recover("limit"),0)
        self.now += 4
        with self.assertRaises(Conflict): self.store.heartbeat(first["token"],5)
        self.assertEqual(self.store.recover("limit"),1)

    def test_empty_and_truncated_outputs_preserved_but_not_promoted(self):
        first = self.claim(); response = mock_response(first); response["choices"][0]["finish_reason"] = "length"
        self.assertFalse(self.store.complete(first["token"],response,{})["accepted"])
        second = self.store.claim("run","worker",5); response = mock_response(second); response["choices"][0]["message"]["content"] = ""
        self.assertFalse(self.store.complete(second["token"],response,{})["accepted"])
        self.assertEqual(self.store.status("run")["checkpoints"],0)
        receipts = [e for e in self.store.events("run") if e["kind"]=="attempt.received"]
        self.assertEqual([e["payload"]["failure"] for e in receipts], ["incomplete_generation","empty_or_invalid_content"])
        self.store.verify("run")

    def test_retry_exhaustion_and_unknown_usage(self):
        for _ in range(3):
            claim = self.claim(); self.store.fail(claim["token"],{"category":"timeout"})
        status = self.store.status("run")
        self.assertEqual(status["steps"]["failed"],1)
        self.assertEqual(status["unknown_usage_attempts"],3)
        self.assertEqual(status["known_total_tokens"],0)
        with self.assertRaises(NotReady): self.store.enqueue_round("run",1)
        self.store.verify("run")

    def test_invalid_route_is_retained_and_rolls_back_checkpoint(self):
        claim = self.claim()
        result = finish(self.store,claim,[{"recipient":"a00000","target_round":1,"content":"forbidden"}])
        self.assertFalse(result["accepted"])
        self.assertEqual(self.store.status("run")["messages"],0)
        self.assertEqual(self.store.status("run")["checkpoints"],0)
        self.store.verify("run")

    def test_observation_idempotency_and_cross_run_parent_rejection(self):
        e = self.store.observe("run","external-check","observation.verifier",{"valid":False})
        self.assertEqual(e,self.store.observe("run","external-check","observation.verifier",{"valid":False}))
        with self.assertRaises(Conflict): self.store.observe("run","external-check","observation.verifier",{"valid":True})
        self.store.create_run("other",self.config)
        with self.assertRaises(Conflict): self.store.observe("other","x","observation.test",{},[e])

    def test_journal_is_append_only_and_detects_offline_tampering(self):
        with self.assertRaises(sqlite3.IntegrityError): self.store.db.execute("UPDATE events SET kind='changed'")
        self.store.db.execute("DROP TRIGGER events_no_update")
        self.store.db.execute("UPDATE events SET kind='changed'")
        with self.assertRaises(Conflict): self.store.verify("run")

    def test_projection_tampering_detected(self):
        claim = self.claim(); finish(self.store,claim)
        self.store.db.execute("UPDATE steps SET attempts=99")
        with self.assertRaises(Conflict): self.store.verify("run")

    def test_deleted_checkpoint_detected(self):
        claim = self.claim(); finish(self.store,claim)
        self.store.db.execute("DROP TRIGGER checkpoints_no_delete")
        self.store.db.execute("DELETE FROM checkpoints")
        with self.assertRaises(Conflict): self.store.verify("run")

    def test_backup_restore_and_export_from_snapshot(self):
        claim = self.claim(); finish(self.store,claim)
        backup = Path(self.temp.name)/"backup.sqlite"
        self.store.backup(backup)
        with self.assertRaises(FileExistsError): self.store.backup(backup)
        with Store(backup,clock=lambda:100) as restored:
            self.assertEqual(restored.verify("run"),self.store.verify("run"))
            finish(restored,restored.claim("run","restored",5))
            restored.enqueue_round("run",1)
            while True:
                claim = restored.claim("run","restored",5)
                if not claim: break
                finish(restored,claim)
            self.assertTrue(restored.status("run")["complete"])
        destination = Path(self.temp.name)/"export"
        self.store.export("run",destination)
        import hashlib
        for item in json.loads((destination/"manifest.json").read_text())["artifacts"]:
            self.assertEqual(item["sha256"],hashlib.sha256((destination/item["path"]).read_bytes()).hexdigest())

    def test_concurrent_processes_have_one_canonical_result_per_step(self):
        config = demo_manifest(48,1); config["max_inflight"] = 2
        self.store.create_run("parallel",config)
        # Child fixture uses run; isolate into its own database.
        other = Path(self.temp.name)/"parallel.sqlite"
        with Store(other) as store:
            store.create_run("run",config); store.enqueue_round("run",0)
        ctx = mp.get_context("spawn"); children=[]
        for i in range(4):
            parent,child = ctx.Pipe(); process=ctx.Process(target=child_drain,args=(str(other),child,i)); process.start(); children.append((process,parent))
        for process,pipe in children:
            process.join(30)
            if process.is_alive(): process.kill(); process.join(); self.fail("Worker timeout")
            self.assertEqual(process.exitcode,0); self.assertIsNone(pipe.recv())
        with Store(other) as store:
            status=store.status("run"); self.assertEqual(status["checkpoints"],48); self.assertEqual(status["attempts"],48)
            store.verify("run")
            active=0; peak=0
            for e in store.events("run"):
                if e["kind"]=="attempt.started": active+=1; peak=max(peak,active)
                elif e["kind"]=="attempt.received": active-=1
            self.assertLessEqual(peak,2); self.assertEqual(active,0)

    def crash_case(self,phase,committed):
        self.store.enqueue_round("run",0)
        ctx=mp.get_context("spawn"); parent,child=ctx.Pipe()
        process=ctx.Process(target=child_crash,args=(str(self.path),child,phase)); process.start()
        try:
            self.assertTrue(parent.poll(15),"Crash fixture did not reach injection point")
            parent.recv(); os.kill(process.pid,signal.SIGKILL); process.join(10)
            self.assertEqual(process.exitcode,-signal.SIGKILL)
            self.now=110
            self.assertEqual(self.store.recover("run"),0 if committed else 1)
            status=self.store.status("run")
            self.assertEqual(status["checkpoints"],int(committed)); self.assertEqual(status["messages"],int(committed))
            self.store.verify("run")
            while True:
                claim=self.store.claim("run","recovery",10)
                if not claim: break
                finish(self.store,claim)
            self.store.enqueue_round("run",1)
            while True:
                claim=self.store.claim("run","recovery",10)
                if not claim: break
                finish(self.store,claim)
            self.assertTrue(self.store.status("run")["complete"])
            self.store.verify("run")
        finally:
            if process.is_alive(): process.kill(); process.join()

    def test_sigkill_after_claim(self): self.crash_case("after_claim",False)
    def test_sigkill_inside_result_transaction(self): self.crash_case("inside_commit",False)
    def test_sigkill_after_commit_before_ack(self): self.crash_case("after_commit",True)


if __name__ == "__main__": unittest.main()
