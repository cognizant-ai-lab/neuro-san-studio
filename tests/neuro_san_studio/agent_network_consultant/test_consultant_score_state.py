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

"""Tests for Agent Network Consultant score history."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState


class TestConsultantScoreState(TestCase):
    """Verify policy-free full-suite and subset score storage."""

    def test_keeps_full_suite_and_subset_scores_independent(self) -> None:
        """Store each score under the coverage scope supplied by the scoring service."""
        state = ConsultantScoreState()

        state.record_full_score((9, 18))
        state.record_subset_score((8, 17))

        self.assertEqual([(9, 18)], state.full_scores())
        self.assertEqual([(8, 17)], state.subset_scores())

    def test_returns_isolated_histories_and_clears_only_subset_scores(self) -> None:
        """Protect recorded scores from caller mutation and preserve full scores during a subset reset."""
        state = ConsultantScoreState()
        state.record_full_score((9, 18))
        state.record_subset_score((8, 17))

        full_scores = state.full_scores()
        subset_scores = state.subset_scores()
        full_scores.clear()
        subset_scores.clear()
        state.clear_subset_scores()

        self.assertEqual([(9, 18)], state.full_scores())
        self.assertEqual([], state.subset_scores())
