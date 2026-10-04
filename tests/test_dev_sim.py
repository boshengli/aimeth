import unittest
import numpy as np
from aimeth_dev.sim import Params, run, init_state, step_once, lesion, G
from aimeth_dev.metrics import permutation_z, summarize


class DevSimTests(unittest.TestCase):
    def test_deterministic_given_seed(self):
        p = Params(steps=60)
        a, _ = run(p, 7)
        b, _ = run(p, 7)
        self.assertTrue(np.array_equal(a.alive, b.alive))
        self.assertTrue(np.allclose(a.x, b.x))

    def test_cell_ceiling_respected(self):
        p = Params(steps=200, max_cells=300)
        s, _ = run(p, 3)
        self.assertLessEqual(int(s.alive.sum()), 300)

    def test_daughters_inherit_clone_and_empty_sites_are_clean(self):
        p = Params(steps=80)
        s, _ = run(p, 2)
        self.assertTrue((s.clone[s.alive] >= 0).all())
        self.assertTrue((s.clone[~s.alive] == -1).all())
        self.assertTrue(np.all(s.x[~s.alive] == 0))
        founders = int((Params().seed_radius * 2 + 1) ** 2)
        self.assertLessEqual(len(np.unique(s.clone[s.alive])), founders)

    def test_fixed_population_never_divides(self):
        p = Params(steps=50, condition="fixed_population")
        s, _ = run(p, 1, fixed_n=500)
        self.assertEqual(int(s.alive.sum()), 500)
        self.assertEqual(s.births, 0)

    def test_lesion_removes_right_half(self):
        p = Params(steps=150)
        s, _ = run(p, 4)
        before = int(s.alive.sum())
        lesion(s, "right")
        self.assertLess(int(s.alive.sum()), before)
        self.assertEqual(s.deaths, before - int(s.alive.sum()))

    def test_large_model_calls_respect_refractory(self):
        p = Params(steps=120, call_refractory=10**6)
        s, _ = run(p, 5)
        # with an effectively infinite refractory each lineage line can fire at most once
        self.assertLessEqual(s.expensive_calls, s.births + int(np.pi * Params().seed_radius ** 2 + 20))

    def test_permutation_null_detects_clustering(self):
        alive = np.ones((30, 30), bool)
        labels = np.zeros((30, 30), int)
        labels[:, 15:] = 1
        z = permutation_z(labels, alive, np.random.default_rng(0), 50)["z"]
        self.assertGreater(z, 10)
        rnd = np.random.default_rng(1).integers(0, 2, (30, 30))
        z0 = permutation_z(rnd, alive, np.random.default_rng(0), 50)["z"]
        self.assertLess(abs(z0), 4)

    def test_summary_keys(self):
        p = Params(steps=100)
        s, _ = run(p, 1)
        m = summarize(s, p, np.random.default_rng(0), 20)
        for k in ("organizer", "demand_coverage", "expensive_calls_per_1000_cell_steps", "clone_coherence"):
            self.assertIn(k, m)


if __name__ == "__main__":
    unittest.main()
