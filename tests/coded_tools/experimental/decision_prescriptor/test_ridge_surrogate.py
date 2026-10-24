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

from coded_tools.experimental.decision_prescriptor.ridge_surrogate import RidgeSurrogate


class TestRidgeSurrogate(TestCase):
    """
    Tests for the closed-form predictor.

    The surrogate is checked against the closed-form ridge solution written out
    independently, so the test would catch a sign slip or a missing intercept rather
    than simply re-running the implementation and agreeing with itself.
    """

    def test_matches_an_independently_written_closed_form(self):
        """
        Compare predictions against the ridge solution computed from scratch.

        The reference below repeats the standardization, the unpenalized bias
        column and the solve explicitly, so agreement is evidence about the
        formula rather than a tautology.
        """
        rng = np.random.default_rng(0)
        features = rng.normal(size=(50, 3))
        targets = rng.normal(size=(50, 2))
        alpha = 0.7

        surrogate = RidgeSurrogate(alpha=alpha).fit(features, targets)

        mean = features.mean(axis=0)
        scale = np.where(features.std(axis=0) < 1e-12, 1.0, features.std(axis=0))
        design = np.hstack([(features - mean) / scale, np.ones((features.shape[0], 1))])
        penalty = alpha * np.eye(design.shape[1])
        penalty[-1, -1] = 0.0
        expected = design @ np.linalg.solve(design.T @ design + penalty, design.T @ targets)

        np.testing.assert_allclose(surrogate.predict(features), expected, rtol=1e-9, atol=1e-9)

    def test_recovers_a_clean_linear_relationship(self):
        """With no noise and a linear truth, the fit should be near perfect."""
        rng = np.random.default_rng(1)
        features = rng.uniform(0.0, 1.0, size=(200, 2))
        targets = np.column_stack([3.0 * features[:, 0] - 2.0 * features[:, 1] + 5.0])

        surrogate = RidgeSurrogate(alpha=1e-6).fit(features, targets)
        self.assertGreater(float(surrogate.r_squared(features, targets)[0]), 0.999)

    def test_constant_target_scores_zero_rather_than_dividing_by_zero(self):
        """A target with no variance has no variance to explain."""
        features = np.random.default_rng(2).normal(size=(20, 2))
        targets = np.full((20, 1), 4.0)
        surrogate = RidgeSurrogate(alpha=1.0).fit(features, targets)
        self.assertEqual(float(surrogate.r_squared(features, targets)[0]), 0.0)

    def test_predict_before_fit_is_refused(self):
        """Predicting from an unfitted model would silently return nonsense."""
        with self.assertRaises(RuntimeError):
            RidgeSurrogate().predict(np.zeros((2, 2)))

    def test_negative_alpha_is_refused(self):
        """A negative penalty is not regularization and must not be accepted."""
        with self.assertRaises(ValueError):
            RidgeSurrogate(alpha=-1.0)

    def test_row_count_mismatch_is_reported(self):
        """Mismatched features and targets are a caller error worth naming."""
        with self.assertRaises(ValueError):
            RidgeSurrogate().fit(np.zeros((5, 2)), np.zeros((4, 1)))
