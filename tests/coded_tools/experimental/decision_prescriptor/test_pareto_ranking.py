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

from coded_tools.experimental.decision_prescriptor.pareto_ranking import ParetoRanking


class TestParetoRanking(TestCase):
    """
    Tests for the dominance relation, the front partition, crowding and survivor selection.

    These pieces are exactly determined, so they are checked against hand-worked examples.
    """

    def test_dominates_requires_strictly_better_somewhere(self):
        """Equal vectors do not dominate each other; being better on one objective does."""
        self.assertTrue(ParetoRanking.dominates(np.array([1.0, 2.0]), np.array([2.0, 3.0])))
        self.assertTrue(ParetoRanking.dominates(np.array([1.0, 2.0]), np.array([1.0, 3.0])))
        self.assertFalse(ParetoRanking.dominates(np.array([1.0, 2.0]), np.array([1.0, 2.0])))
        self.assertFalse(ParetoRanking.dominates(np.array([1.0, 5.0]), np.array([2.0, 3.0])))

    def test_fronts_match_a_hand_worked_example(self):
        """
        Five points whose layering can be checked by eye.

        Points 0, 1 and 2 trade off against one another. Points 3 and 4 are each
        beaten outright by point 2, so they fall to the second front.
        """
        objectives = np.array([[1.0, 5.0], [2.0, 3.0], [3.0, 1.0], [4.0, 6.0], [5.0, 4.0]])
        self.assertEqual(ParetoRanking.fast_non_dominated_sort(objectives), [[0, 1, 2], [3, 4]])

    def test_every_point_is_on_one_front_when_all_are_incomparable(self):
        """A perfectly conflicting set collapses to a single front."""
        objectives = np.array([[0.0, 3.0], [1.0, 2.0], [2.0, 1.0], [3.0, 0.0]])
        self.assertEqual(ParetoRanking.fast_non_dominated_sort(objectives), [[0, 1, 2, 3]])

    def test_empty_population_sorts_to_no_fronts(self):
        """The sort must tolerate an empty population rather than raising."""
        self.assertEqual(ParetoRanking.fast_non_dominated_sort(np.empty((0, 2))), [])

    def test_vectorized_mask_agrees_with_the_reference_sort(self):
        """
        The fast path must return exactly the first front of the reference sort.

        Integer objectives are used so duplicate rows occur often: duplicates are
        the case where a sloppy dominance test wrongly eliminates both copies.
        """
        rng = np.random.default_rng(0)
        for num_objectives in (2, 3, 4):
            objectives = rng.integers(0, 5, size=(50, num_objectives)).astype(float)
            expected = np.zeros(50, dtype=bool)
            expected[ParetoRanking.fast_non_dominated_sort(objectives)[0]] = True
            np.testing.assert_array_equal(expected, ParetoRanking.non_dominated_mask(objectives))

    def test_mask_is_independent_of_chunk_size(self):
        """Chunking is an implementation detail and must not change the answer."""
        objectives = np.random.default_rng(1).random((300, 3))
        np.testing.assert_array_equal(
            ParetoRanking.non_dominated_mask(objectives, chunk_size=512),
            ParetoRanking.non_dominated_mask(objectives, chunk_size=7),
        )

    def test_crowding_extremes_are_infinite(self):
        """The ends of a front must never be discarded, so they score infinity."""
        objectives = np.array([[0.0, 3.0], [1.0, 2.0], [2.0, 1.0], [3.0, 0.0]])
        distances = ParetoRanking.crowding_distance(objectives, [0, 1, 2, 3])
        self.assertTrue(np.isinf(distances[0]))
        self.assertTrue(np.isinf(distances[3]))
        self.assertTrue(np.all(np.isfinite(distances[1:3])))

    def test_evenly_spaced_interior_points_score_equally(self):
        """
        On a uniform front every interior point has the same neighbour gap.

        With two objectives each interior point spans 2 of 4 steps on each axis,
        giving 0.5 per objective and 1.0 in total.
        """
        objectives = np.array([[0.0, 4.0], [1.0, 3.0], [2.0, 2.0], [3.0, 1.0], [4.0, 0.0]])
        distances = ParetoRanking.crowding_distance(objectives, [0, 1, 2, 3, 4])
        np.testing.assert_allclose(distances[1:4], [1.0, 1.0, 1.0])

    def test_small_fronts_are_all_infinite(self):
        """With two or fewer members there is no interior to measure."""
        distances = ParetoRanking.crowding_distance(np.array([[0.0, 1.0], [1.0, 0.0]]), [0, 1])
        self.assertTrue(np.all(np.isinf(distances)))

    def test_constant_objective_contributes_nothing(self):
        """An objective identical across the front separates nobody."""
        objectives = np.array([[0.0, 1.0], [1.0, 1.0], [2.0, 1.0], [3.0, 1.0]])
        distances = ParetoRanking.crowding_distance(objectives, [0, 1, 2, 3])
        self.assertTrue(np.all(np.isfinite(distances[1:3])))

    def test_environmental_selection_prefers_the_first_front(self):
        """Front members must be retained ahead of anything they dominate."""
        objectives = np.array([[0.0, 3.0], [1.0, 2.0], [2.0, 1.0], [9.0, 9.0], [8.0, 8.0]])
        kept = set(ParetoRanking.environmental_selection(objectives, 3).tolist())
        self.assertEqual(kept, {0, 1, 2})

    def test_environmental_selection_returns_exactly_the_requested_count(self):
        """The population size must stay fixed from generation to generation."""
        objectives = np.random.default_rng(2).random((40, 3))
        self.assertEqual(ParetoRanking.environmental_selection(objectives, 12).shape[0], 12)

    def test_select_spread_keeps_the_extremes(self):
        """A readable subset must still show the honest edges of what is achievable."""
        objectives = np.column_stack([np.arange(30.0), 30.0 - np.arange(30.0)])
        chosen = ParetoRanking.select_spread(objectives, 6)
        self.assertEqual(chosen.shape[0], 6)
        self.assertIn(0, chosen.tolist())
        self.assertIn(29, chosen.tolist())

    def test_select_spread_is_a_no_op_when_the_front_already_fits(self):
        """Asking for more points than exist returns them all."""
        objectives = np.array([[0.0, 1.0], [1.0, 0.0]])
        np.testing.assert_array_equal(ParetoRanking.select_spread(objectives, 10), np.array([0, 1]))
