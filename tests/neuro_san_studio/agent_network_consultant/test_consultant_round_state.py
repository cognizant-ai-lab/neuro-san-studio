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

"""Tests for encapsulated Consultant fixture-round state."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState


class TestConsultantRoundState(TestCase):
    """Verify fixture-round transitions through the public state interface."""

    def test_results_derive_failures_without_exposing_the_stored_list(self) -> None:
        """Derive failures and protect stored result collections from caller mutation."""
        state = ConsultantRoundState()
        results = [
            {"fixture": "passing.hocon", "passed": True},
            {"fixture": "failing.hocon", "passed": False},
        ]

        state.record_results(results)
        returned_results = state.results()
        returned_results.clear()

        self.assertEqual(state.result_count(), 2)
        self.assertEqual(state.failure_count(), 1)
        self.assertEqual(state.passing_count(), 1)

    def test_schedules_current_failures_for_a_subset_round(self) -> None:
        """Create the next fixture selection from the current failures."""
        state = ConsultantRoundState()
        state.record_results([{"fixture": "failing.hocon", "passed": False}])

        state.schedule_failure_retests()
        state.begin_round()

        self.assertEqual(state.fixture_selection(), ["failing.hocon"])
        self.assertTrue(state.is_subset_check())
