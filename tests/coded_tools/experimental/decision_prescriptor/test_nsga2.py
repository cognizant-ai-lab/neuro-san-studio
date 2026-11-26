# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

from unittest import TestCase

import numpy as np

from coded_tools.experimental.decision_prescriptor.nsga2 import Nsga2
from coded_tools.experimental.decision_prescriptor.pareto_ranking import ParetoRanking
from tests.coded_tools.experimental.decision_prescriptor.zdt1_benchmark import Zdt1Benchmark


class TestNsga2(TestCase):
    """
    Tests for the unbounded archive and for the search loop against a benchmark with a known front.

    The search is stochastic, so these tests avoid asserting on any particular
    solution and check convergence against ZDT1's analytic front instead.
    """

    def test_archive_drops_newly_dominated_members(self):
        """A previously archived point must go once something beats it outright."""
        genes = np.array([[0.0], [1.0]])
        objectives = np.array([[1.0, 1.0], [2.0, 2.0]])
        new_genes = np.array([[2.0]])
        new_objectives = np.array([[0.0, 0.0]])

        _, kept = Nsga2.update_archive(genes, objectives, new_genes, new_objectives)
        np.testing.assert_array_equal(kept, np.array([[0.0, 0.0]]))

    def test_archive_deduplicates_identical_objectives(self):
        """Duplicate rows would otherwise accumulate without adding information."""
        genes = np.array([[0.0], [0.0]])
        objectives = np.array([[1.0, 1.0], [1.0, 1.0]])
        _, kept = Nsga2.update_archive(genes, objectives, genes, objectives)
        self.assertEqual(kept.shape[0], 1)

    def test_converges_close_to_the_analytic_zdt1_front(self):
        """
        The recovered front must sit on f2 = 1 - sqrt(f1).

        The budget here is chosen to be genuinely sufficient rather than merely
        enough to pass: across six seeds this configuration converges to a worst
        mean distance of 0.0004, so the 0.01 threshold leaves a wide margin and
        still fails loudly if the search regresses. A shorter run was rejected
        because at 80 generations some seeds have simply not converged yet, and a
        test that tolerated that would be asserting nothing.
        """
        num_genes = 6
        result = Nsga2.evolve(
            Zdt1Benchmark.evaluate,
            np.zeros(num_genes),
            np.ones(num_genes),
            population_size=60,
            generations=120,
            seed=1,
        )
        front = result.get("front_objectives")
        distance = np.abs(front[:, 1] - (1.0 - np.sqrt(front[:, 0]))).mean()
        self.assertLess(distance, 0.01)

    def test_the_front_spans_the_objective_range(self):
        """
        Converging onto one corner of the front would satisfy a distance check
        while being useless as a set of options, so coverage is asserted too.
        """
        num_genes = 6
        result = Nsga2.evolve(
            Zdt1Benchmark.evaluate,
            np.zeros(num_genes),
            np.ones(num_genes),
            population_size=60,
            generations=120,
            seed=1,
        )
        first_objective = result.get("front_objectives")[:, 0]
        self.assertLess(first_objective.min(), 0.1)
        self.assertGreater(first_objective.max(), 0.9)

    def test_hypervolume_history_never_decreases(self):
        """
        The archive's dominated region can only grow, so its measure must too.

        This is the property that broke when progress was measured on the
        population instead: once the first front outgrows the population, crowding
        truncation discards non-dominated solutions and the curve dips.
        """
        num_genes = 6
        for num_objectives, evaluate in (
            (2, Zdt1Benchmark.evaluate),
            (3, lambda pop: np.column_stack([pop[:, 0], pop[:, 1], np.sum(pop[:, 2:] ** 2, axis=1)])),
        ):
            result = Nsga2.evolve(
                evaluate, np.zeros(num_genes), np.ones(num_genes), population_size=40, generations=30, seed=2
            )
            history = result.get("hypervolume_history")
            self.assertEqual(history.shape[0], 30)
            self.assertTrue(
                np.all(np.diff(history) >= -1e-12),
                f"hypervolume decreased with {num_objectives} objectives",
            )

    def test_the_returned_front_is_actually_non_dominated(self):
        """Nothing on the reported front may dominate anything else on it."""
        num_genes = 5
        result = Nsga2.evolve(
            Zdt1Benchmark.evaluate, np.zeros(num_genes), np.ones(num_genes), population_size=30, generations=20, seed=3
        )
        self.assertTrue(np.all(ParetoRanking.non_dominated_mask(result.get("front_objectives"))))

    def test_the_same_seed_reproduces_a_run(self):
        """A decision tool whose output moved between runs would not be usable."""
        num_genes = 5
        bounds = (np.zeros(num_genes), np.ones(num_genes))
        first = Nsga2.evolve(Zdt1Benchmark.evaluate, *bounds, population_size=20, generations=10, seed=42)
        second = Nsga2.evolve(Zdt1Benchmark.evaluate, *bounds, population_size=20, generations=10, seed=42)
        np.testing.assert_allclose(first.get("front_objectives"), second.get("front_objectives"))
