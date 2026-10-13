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

"""Tests for encapsulated Agent Network Consultant fixture-round state."""

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

    def test_stores_an_isolated_fixture_selection(self) -> None:
        """Retain the fixture selection supplied by the orchestration policy."""
        state = ConsultantRoundState()
        fixture_names = ["failing.hocon"]

        state.set_fixture_selection(fixture_names)
        fixture_names.append("later.hocon")
        state.begin_round()

        self.assertEqual(state.fixture_selection(), ["failing.hocon"])
        self.assertTrue(state.is_subset_check())

    def test_explicit_initial_selection_retains_the_discovered_suite_total(self) -> None:
        """Track a caller-selected first round without presenting the selected count as the suite size."""
        state = ConsultantRoundState()
        state.set_fixture_selection(["selected.hocon"], 5)

        state.begin_round()
        state.record_results([{"fixture": "selected.hocon", "passed": False}])

        self.assertTrue(state.is_subset_check())
        self.assertEqual(state.fixture_selection(), ["selected.hocon"])
        self.assertEqual(state.total_fixture_count(), 5)

    def test_returns_an_isolated_copy_of_success_ratio_overrides(self) -> None:
        """Keep stricter fixture ratios with the rest of the active round state."""
        state = ConsultantRoundState()
        state.remember_success_ratio_overrides(["fixture.hocon"], "3/3")

        ratios = state.success_ratio_overrides()
        ratios.clear()

        self.assertEqual(state.success_ratio_overrides(), {"fixture.hocon": "3/3"})
        self.assertTrue(state.has_success_ratio_overrides())
