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

from coded_tools.experimental.decision_prescriptor.genetic_operators import GeneticOperators


class TestGeneticOperators(TestCase):
    """
    Tests for tournament selection, crossover and mutation.
    """

    def test_tournament_prefers_the_lower_rank(self):
        """With one solution on the first front and one behind it, the first front always wins."""
        ranks = np.array([0, 1])
        crowding = np.array([0.0, np.inf])
        winners = GeneticOperators.binary_tournament(ranks, crowding, 200, np.random.default_rng(0))
        # Index 1 can only win a tournament against itself.
        self.assertGreater(np.count_nonzero(winners == 0), np.count_nonzero(winners == 1))

    def test_crossover_children_stay_inside_the_bounds(self):
        """A child outside the bounds would describe an infeasible prescriptor."""
        rng = np.random.default_rng(1)
        lower, upper = np.zeros(4), np.ones(4)
        children = GeneticOperators.sbx_crossover(rng.random((50, 4)), rng.random((50, 4)), lower, upper, rng)
        self.assertTrue(np.all(children >= lower))
        self.assertTrue(np.all(children <= upper))

    def test_mutation_stays_inside_the_bounds_and_changes_something(self):
        """Mutation must explore, but never leave the feasible box."""
        rng = np.random.default_rng(2)
        population = rng.random((50, 4))
        lower, upper = np.zeros(4), np.ones(4)
        mutated = GeneticOperators.polynomial_mutation(population, lower, upper, rng)
        self.assertTrue(np.all(mutated >= lower))
        self.assertTrue(np.all(mutated <= upper))
        self.assertFalse(np.array_equal(mutated, population))

    def test_operators_are_reproducible_from_a_seed(self):
        """The same seed must breed the same children."""
        parents = np.random.default_rng(3).random((10, 3))
        bounds = (np.zeros(3), np.ones(3))
        first = GeneticOperators.sbx_crossover(parents, parents[::-1], *bounds, np.random.default_rng(4))
        second = GeneticOperators.sbx_crossover(parents, parents[::-1], *bounds, np.random.default_rng(4))
        np.testing.assert_array_equal(first, second)
