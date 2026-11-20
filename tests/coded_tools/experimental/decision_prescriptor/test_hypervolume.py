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

from coded_tools.experimental.decision_prescriptor.hypervolume import Hypervolume


class TestHypervolume(TestCase):
    """
    Tests for the front quality measure, on shapes with a known area.
    """

    def test_two_overlapping_boxes(self):
        """
        Two points against reference (1, 1).

        Each box has area 0.5 and they overlap in a 0.5 by 0.5 square, so the
        union is 0.5 + 0.5 - 0.25 = 0.75.
        """
        front = np.array([[0.0, 0.5], [0.5, 0.0]])
        self.assertAlmostEqual(Hypervolume.compute(front, np.array([1.0, 1.0])), 0.75)

    def test_single_point_is_its_own_box(self):
        """One point at the origin dominates the whole unit square."""
        self.assertAlmostEqual(Hypervolume.compute(np.array([[0.0, 0.0]]), np.array([1.0, 1.0])), 1.0)

    def test_points_outside_the_reference_contribute_nothing(self):
        """A point worse than the reference on any axis adds no volume."""
        self.assertEqual(Hypervolume.compute(np.array([[2.0, 2.0]]), np.array([1.0, 1.0])), 0.0)

    def test_dominated_points_do_not_inflate_the_volume(self):
        """Adding a dominated point must leave the measure unchanged."""
        reference = np.array([1.0, 1.0])
        without = Hypervolume.compute(np.array([[0.0, 0.5], [0.5, 0.0]]), reference)
        with_extra = Hypervolume.compute(np.array([[0.0, 0.5], [0.5, 0.0], [0.8, 0.8]]), reference)
        self.assertAlmostEqual(without, with_extra)

    def test_monte_carlo_estimate_is_close_for_a_known_cube(self):
        """A point at the origin against reference (1, 1, 1) dominates the whole unit cube."""
        samples = np.random.default_rng(0).random((4000, 3))
        volume = Hypervolume.compute(np.array([[0.0, 0.0, 0.0]]), np.ones(3), samples=samples, box_volume=1.0)
        self.assertAlmostEqual(volume, 1.0)

    def test_monte_carlo_path_requires_a_box_volume(self):
        """Supplying samples without their box volume is a programming error."""
        samples = np.random.default_rng(0).random((16, 3))
        with self.assertRaises(ValueError):
            Hypervolume.compute(np.zeros((2, 3)), np.ones(3), samples=samples)
