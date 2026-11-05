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

from coded_tools.experimental.decision_prescriptor.pareto_report import ParetoReport


class TestParetoReport(TestCase):
    """
    Tests for the HTML report.
    """

    def setUp(self):
        """Build a small front to render."""
        self.front = np.array([[10.0, 0.2, 12.0], [20.0, 0.4, 16.0], [30.0, 0.6, 20.0]])
        self.actions = np.array([[0.9, 0.1], [0.5, 0.5], [0.1, 0.9]])
        self.labels = ["margin_pct", "delivery_risk", "time_to_value_weeks"]
        self.action_labels = ["senior_staff_ratio", "automation_investment"]

    def render(self) -> str:
        """
        :return: A rendered report for the fixture front.
        """
        return ParetoReport.render(
            title="Test front",
            front=self.front,
            dominated=np.array([[5.0, 0.9, 30.0]]),
            actions=self.actions,
            objective_labels=self.labels,
            action_labels=self.action_labels,
            hypervolume_history=[1.0, 2.0, 3.0],
            summary={"Strategies": "3"},
            balanced_index=1,
        )

    def test_report_is_self_contained(self):
        """
        No external stylesheet, script or image may be referenced.

        A report that silently needs the network would render broken for anyone
        reading it from disk, which is the main way these files get read.
        """
        document = self.render()
        for marker in ("http://", "https://", "<script", "@import", "src="):
            self.assertNotIn(marker, document, f"report should not contain {marker!r}")

    def test_every_strategy_reaches_the_table(self):
        """The table is the accessibility path, so it must be complete."""
        document = self.render()
        self.assertEqual(document.count("<tr><th scope='row'>"), self.front.shape[0])

    def test_both_themes_are_defined(self):
        """Dark mode is a selected set of steps, and must survive a theme toggle."""
        document = self.render()
        self.assertIn("prefers-color-scheme: dark", document)
        self.assertIn("[data-theme='dark']", document)
        self.assertIn("--series-1:#2a78d6;", document)

    def test_labels_are_escaped(self):
        """A field name is user-supplied and must not be able to inject markup."""
        document = ParetoReport.render(
            title="<script>alert(1)</script>",
            front=self.front,
            dominated=np.empty((0, 3)),
            actions=self.actions,
            objective_labels=["<b>x</b>", "y", "z"],
            action_labels=self.action_labels,
            hypervolume_history=[1.0],
            summary={},
        )
        self.assertNotIn("<script>alert(1)</script>", document)
        self.assertNotIn("<b>x</b>", document)

    def test_two_objective_reports_render(self):
        """The two-objective path uses a single connected chart and must not break."""
        document = ParetoReport.render(
            title="Two",
            front=np.array([[1.0, 4.0], [2.0, 3.0]]),
            dominated=np.empty((0, 2)),
            actions=np.array([[0.1], [0.2]]),
            objective_labels=["a", "b"],
            action_labels=["act"],
            hypervolume_history=[1.0, 1.5],
            summary={"n": "2"},
            balanced_index=0,
        )
        self.assertIn("<svg", document)
        self.assertIn("front-line", document)
