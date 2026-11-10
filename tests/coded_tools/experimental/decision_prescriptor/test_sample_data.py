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

from coded_tools.experimental.decision_prescriptor.sample_data import SampleData


class TestSampleData(TestCase):
    """
    Tests for the bundled example.
    """

    def test_generates_every_declared_field(self):
        """The spec and the rows have to agree or nothing downstream will run."""
        rows = SampleData.generate(num_rows=25)
        spec = SampleData.specification()
        self.assertEqual(len(rows), 25)
        for name in spec.get("context_fields") + spec.get("action_fields") + spec.get("outcome_fields"):
            self.assertIn(name, rows[0])
        self.assertEqual(len(spec.get("maximize")), len(spec.get("outcome_fields")))

    def test_contains_the_intended_conflict(self):
        """
        Senior staffing must genuinely pull margin and delivery risk apart.

        Without a real conflict the example would produce a degenerate front and
        quietly stop demonstrating anything.
        """
        rows = SampleData.generate(num_rows=400)
        staffing = np.array([row.get("senior_staff_ratio") for row in rows])
        margin = np.array([row.get("margin_pct") for row in rows])
        risk = np.array([row.get("delivery_risk") for row in rows])

        self.assertLess(float(np.corrcoef(staffing, margin)[0, 1]), -0.5)
        self.assertLess(float(np.corrcoef(staffing, risk)[0, 1]), -0.5)

    def test_is_reproducible(self):
        """The same seed must give the same example."""
        self.assertEqual(SampleData.generate(10, seed=3), SampleData.generate(10, seed=3))
