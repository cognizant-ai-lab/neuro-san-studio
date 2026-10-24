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

from coded_tools.experimental.decision_prescriptor.prescriptor_network import PrescriptorNetwork


class TestPrescriptorNetwork(TestCase):
    """
    Tests for the evolved policy network.
    """

    def setUp(self):
        """Build a small network shared by the tests below."""
        self.network = PrescriptorNetwork(
            context_dim=2, action_dim=3, action_lower=np.zeros(3), action_upper=np.array([1.0, 5.0, 0.5])
        )

    def test_weight_count_matches_the_layer_shapes(self):
        """2*4 + 4 + 4*3 + 3 = 27."""
        self.assertEqual(self.network.num_weights, 27)

    def test_actions_always_land_inside_the_bounds(self):
        """
        Feasibility must hold by construction, including for extreme weights.

        If it did not, the search would spend effort on candidates that could
        never be carried out.
        """
        rng = np.random.default_rng(0)
        context = rng.normal(size=(40, 2)) * 100.0
        lower, upper = self.network.get_action_bounds()
        for scale in (1.0, 50.0):
            actions = self.network.actions(rng.normal(size=27) * scale, context)
            self.assertTrue(np.all(actions >= lower - 1e-12))
            self.assertTrue(np.all(actions <= upper + 1e-12))

    def test_zero_weights_prescribe_the_middle_of_the_range(self):
        """With every weight at zero the logistic output is 0.5, the centre of each bound."""
        actions = self.network.actions(np.zeros(27), np.ones((2, 2)))
        np.testing.assert_allclose(actions, [[0.5, 2.5, 0.25], [0.5, 2.5, 0.25]])

    def test_wrong_weight_length_is_refused(self):
        """A silent reshape here would scramble the policy."""
        with self.assertRaises(ValueError):
            self.network.actions(np.zeros(5), np.zeros((3, 2)))

    def test_inverted_bounds_are_refused(self):
        """An upper bound below its lower bound describes no feasible action."""
        with self.assertRaises(ValueError):
            PrescriptorNetwork(1, 1, np.array([1.0]), np.array([0.0]))
