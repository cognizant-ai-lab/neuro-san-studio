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

from coded_tools.experimental.decision_prescriptor.prescriptor_evaluator import PrescriptorEvaluator
from coded_tools.experimental.decision_prescriptor.prescriptor_network import PrescriptorNetwork


class TestPrescriptorEvaluator(TestCase):
    """
    Tests for the bridge between a policy and the objectives the search minimizes.
    """

    @staticmethod
    def constant_outcomes(features: np.ndarray) -> np.ndarray:
        """
        A stand-in surrogate that predicts 3 and 7 whatever it is given.

        :param features: Raw (context, action) rows.
        :return: Two outcome columns, one row per feature row.
        """
        return np.column_stack([np.full(features.shape[0], 3.0), np.full(features.shape[0], 7.0)])

    def test_maximized_outcomes_are_negated_for_minimization(self):
        """
        The search minimizes, so a maximized outcome must arrive negated.

        Getting this backwards would produce a front that is confidently the worst
        available set of options, which is the kind of error a chart makes look
        authoritative.
        """
        network = PrescriptorNetwork(1, 1, np.zeros(1), np.ones(1))
        context = np.zeros((4, 1))
        weights = np.zeros((1, network.num_weights))

        evaluate = PrescriptorEvaluator(network, context, context, self.constant_outcomes, [True, False])
        np.testing.assert_allclose(evaluate(weights), [[-3.0, 7.0]])

    def test_mismatched_context_views_are_refused(self):
        """Mixing the standardized and raw views would corrupt every prediction."""
        network = PrescriptorNetwork(1, 1, np.zeros(1), np.ones(1))
        with self.assertRaises(ValueError):
            PrescriptorEvaluator(network, np.zeros((4, 1)), np.zeros((5, 1)), self.constant_outcomes, [True])
