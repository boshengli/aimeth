import json
import unittest

from aimeth_swarm.design import counts, default_config, phase_agents, prompt, roster, worker_peers


class SwarmDesignTests(unittest.TestCase):
    def test_full_10k_roster_and_call_slots(self):
        config = default_config()
        agents = roster(config)
        self.assertEqual(len(agents), 10501)
        self.assertEqual(len({a["agent_id"] for a in agents}), 10501)
        self.assertEqual({phase: len(phase_agents(config, phase))
                          for phase in ("worker", "observer", "chief", "global")},
                         {"worker": 10000, "observer": 400, "chief": 100, "global": 1})
        self.assertEqual(counts(config)["planned_call_slots"], 21002)
        self.assertFalse(counts(config)["single_agent_success_required"])
        self.assertFalse(counts(config)["small_population_success_required"])
        self.assertEqual(config["max_inflight"], 16)

    def test_sender_sampling_is_replayable_and_lattice_local(self):
        config = default_config()
        workers = phase_agents(config, "worker")
        by_id = {a["agent_id"]: a for a in workers}
        sampled = 0
        for agent in workers:
            peers = worker_peers(config, agent, 0)
            self.assertEqual(peers, worker_peers(dict(config), dict(agent), 0))
            self.assertEqual(len(peers), len(set(peers)))
            if peers:
                sampled += 1
                row, column = divmod(agent["index"], 10)
                expected = (int(row > 0) + int(row < 9) +
                            int(column > 0) + int(column < 9))
                self.assertEqual(len(peers), expected)
            for peer_id in peers:
                peer = by_id[peer_id]
                self.assertEqual(agent["group"], peer["group"])
                row, column = divmod(agent["index"], 10)
                peer_row, peer_column = divmod(peer["index"], 10)
                self.assertEqual(abs(row-peer_row) + abs(column-peer_column), 1)
        self.assertGreater(sampled, 2500)
        self.assertLess(sampled, 3500)

    def test_governance_prompt_preserves_minority_and_source_records(self):
        config = default_config()
        source = {"source_run": "cycle0-worker", "source_event": "receipt-17",
                  "source_hash": "a" * 64,
                  "content": {"candidate": "A competing route", "dissent": ["The bound is not uniform."]}}
        for phase in ("worker", "observer", "chief", "global"):
            messages = prompt(config, phase_agents(config, phase)[0], 1, [source])
            context = json.loads(messages[-1]["content"].split("\n", 1)[1])
            self.assertEqual(context["incoming"], [source])
            self.assertEqual(context["proof_verification_status"], "unverified")
            self.assertIn("minority", messages[0]["content"])
            self.assertIn("source_event", messages[0]["content"])
            self.assertIn("obligations", messages[0]["content"])
            self.assertIn("unverified", messages[0]["content"])
        with self.assertRaises(ValueError):
            prompt(config, phase_agents(config, "worker")[0], 1, [{"content": "unattributed"}])


if __name__ == "__main__":
    unittest.main()
