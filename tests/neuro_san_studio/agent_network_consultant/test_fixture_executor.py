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

"""Tests for one fixture's execution and verdict reporting."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.fixture_executor import FixtureExecutor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestFixtureExecutor(TestCase):
    """Verify per-fixture acceptance-criterion reporting."""

    def setUp(self) -> None:
        """Create one fixture executor with trace collection disabled."""
        trace_collector = ThinkingTraceCollector("run-one", basis_directory="")
        self.executor = FixtureExecutor("example.hocon", trace_collector)

    def test_report_names_every_failure_and_the_total_but_not_the_passing_text(self) -> None:
        """Include every failed criterion and omit passing criterion text."""
        scorecard = [("contains 'actions'", 1, 1), ("contains 'KPIs'", 0, 1)]

        message = self.executor.scorecard_message(AssertionError("first failure"), scorecard)

        self.assertIn("1 of 2 acceptance criteria failing", message)
        self.assertIn("contains 'KPIs'", message)
        self.assertNotIn("contains 'actions'", message)

    def test_falls_back_to_the_raw_cause_when_nothing_was_recorded(self) -> None:
        """Retain the driver's original error when no scorecard entries exist."""
        self.assertEqual(self.executor.scorecard_message(AssertionError("raw"), []), "raw")
