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

"""Tests for encapsulated Consultant score state."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState


class TestConsultantScoreState(TestCase):
    """Verify full-suite and subset score histories remain independent."""

    def test_subset_stagnation_does_not_advance_the_full_suite_plateau(self) -> None:
        """Keep repeated subset scores isolated from full-suite plateau state."""
        state = ConsultantScoreState()

        self.assertIsNone(state.update((0, 1), True))
        self.assertIsNone(state.update((0, 1), True))

        self.assertTrue(state.subset_plateau_reached(1, True))
        self.assertFalse(state.plateau_reached(1))

    def test_best_hocon_retains_its_iteration(self) -> None:
        """Return the source snapshot with the iteration that produced it."""
        state = ConsultantScoreState()

        state.remember_best_hocon("tools = []", 4)

        self.assertEqual(state.best_hocon(), ("tools = []", 4))
