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

from coded_tools.experimental.decision_prescriptor.standardizer import Standardizer


class TestStandardizer(TestCase):
    """
    Tests for the context standardizer.
    """

    def test_produces_zero_mean_unit_scale(self):
        """The network's inputs must not be dominated by a feature's units."""
        values = np.array([[1000.0, 0.1], [2000.0, 0.2], [3000.0, 0.3]])
        standardized = Standardizer(values).transform(values)
        np.testing.assert_allclose(standardized.mean(axis=0), [0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(standardized.std(axis=0), [1.0, 1.0], atol=1e-12)

    def test_constant_feature_is_left_at_zero(self):
        """A feature with no spread must not divide by zero."""
        values = np.array([[5.0, 1.0], [5.0, 2.0]])
        standardized = Standardizer(values).transform(values)
        np.testing.assert_allclose(standardized[:, 0], [0.0, 0.0])
