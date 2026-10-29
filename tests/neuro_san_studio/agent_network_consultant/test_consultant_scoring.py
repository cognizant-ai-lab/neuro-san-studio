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

"""Tests for Agent Network Consultant scoring and stopping policy."""

from typing import Any
from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring


class TestConsultantScoring(TestCase):
    """Verify Consultant scoring detects progress, regression, and plateaus."""

    def setUp(self) -> None:
        """Create isolated score state for each policy test."""
        self.scoring = ConsultantScoring(ConsultantScoreState())

    @staticmethod
    def _round(*fixtures: tuple[bool, int, int]) -> list[dict[str, Any]]:
        """
        Build result records from passed, criteria-passed, and criteria-total tuples.

        :param fixtures: The fixture result specifications.
        :return: The fixture result records.
        """
        results: list[dict[str, Any]] = []
        for index, fixture in enumerate(fixtures):
            passed, met, total = fixture
            results.append(
                {
                    "fixture": f"f{index}.hocon",
                    "passed": passed,
                    "criteria_passed": met,
                    "criteria_total": total,
                }
            )
        return results

    def test_progress_within_failing_fixtures_is_visible(self) -> None:
        """Use criteria as a tiebreaker when no fixture changes from failing to passing."""
        first = self.scoring.round_score(self._round((False, 2, 5), (False, 1, 5), (False, 1, 5)))
        second = self.scoring.round_score(self._round((False, 4, 5), (False, 3, 5), (False, 3, 5)))
        third = self.scoring.round_score(self._round((False, 5, 5), (False, 5, 5), (False, 4, 5)))

        self.assertEqual((0, 4), first)
        self.assertLess(first, second)
        self.assertLess(second, third)

    def test_passing_fixtures_outrank_more_criteria_in_failing_fixtures(self) -> None:
        """Keep passing-fixture count as the primary score component."""
        two_passing = self.scoring.round_score(self._round((True, 3, 3), (True, 3, 3), (False, 0, 9)))
        more_criteria = self.scoring.round_score(self._round((False, 2, 3), (False, 2, 3), (False, 8, 9)))

        self.assertEqual((2, 6), two_passing)
        self.assertEqual((0, 12), more_criteria)
        self.assertGreater(two_passing, more_criteria)

    def test_full_suite_history_owns_plateau_and_regression_policy(self) -> None:
        """Keep all full-suite stopping decisions in the scoring service."""
        best = (2, 8)
        worse = (1, 7)
        self.scoring.record(best, False)
        self.scoring.record(worse, False)
        self.scoring.record(worse, False)
        self.scoring.record(worse, False)

        self.assertTrue(self.scoring.regresses_from_best(worse))
        self.assertTrue(self.scoring.plateau_reached())
        self.assertEqual(best, self.scoring.best_full_score())

    def test_subset_history_is_independent_and_can_be_cleared(self) -> None:
        """Do not let subset re-checks alter authoritative full-suite history."""
        self.scoring.record((3, 9), False)
        self.scoring.record((0, 2), True)
        self.scoring.record((0, 2), True)
        self.scoring.record((0, 2), True)
        self.scoring.record((0, 2), True)

        self.assertTrue(self.scoring.subset_plateau_reached(True))
        self.assertFalse(self.scoring.subset_plateau_reached(False))
        self.assertEqual((3, 9), self.scoring.best_full_score())

        self.scoring.clear_subset_history()

        self.assertFalse(self.scoring.subset_plateau_reached(True))

    def test_acceptance_threshold_and_criteria_total_are_centralized(self) -> None:
        """Apply the established eighty-percent floor and count evaluated criteria once."""
        results = self._round((True, 3, 3), (False, 2, 4))

        self.assertTrue(self.scoring.good_enough(4, 5))
        self.assertFalse(self.scoring.good_enough(3, 5))
        self.assertEqual(80.0, self.scoring.acceptance_percentage())
        self.assertEqual(7, self.scoring.criteria_total(results))

    def test_results_without_criteria_counts_still_score(self) -> None:
        """Score infrastructure failures that never produced criteria as zero."""
        results = [{"fixture": "a", "passed": False, "infrastructure_error": True}]

        self.assertEqual((0, 0), self.scoring.round_score(results))
