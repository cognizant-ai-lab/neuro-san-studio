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

"""A round's score, which the plateau counter and the best-so-far snapshot both read."""

from typing import Any
from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.network_consultant_orchestrator import PLATEAU_STRIKES


class TestConsultantScoring(TestCase):
    """Verify Consultant scoring detects progress, regression, and plateaus."""

    UNGROUNDED_REPLY = """\
hr_check_vacation_balance_today.hocon: fixed AbsenceManagement
UNGROUNDED: it_password_reset_gsd_ticket.hocon: URLProvider: Includes the GSD URL
UNGROUNDED: legal_ambiguous.hocon: URLProvider: Includes at least one internal URL
"""

    @staticmethod
    def _round(*fixtures: tuple[bool, int, int]) -> list[dict[str, Any]]:
        """
        (passed, criteria_passed, criteria_total) per fixture.

        :param fixtures: The fixture result specifications.
        :return: The collected values.
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
        """
        The intranet_agents_with_tools shape: no fixture flips for three rounds while the network goes from meeting
        4 of 15 criteria to 14. Counting fixtures alone saw nothing.
        """
        rounds = [
            TestConsultantScoring._round((False, 2, 5), (False, 1, 5), (False, 1, 5)),  # 4/15
            TestConsultantScoring._round((False, 4, 5), (False, 3, 5), (False, 3, 5)),  # 10/15
            TestConsultantScoring._round((False, 5, 5), (False, 5, 5), (False, 4, 5)),  # 14/15
        ]
        scores: list[tuple[int, int]] = []
        for round_results in rounds:
            scores.append(ConsultantScoring.round_score(round_results))

        criteria_scores: list[int] = []
        for score in scores:
            criteria_scores.append(score[1])
        self.assertEqual(criteria_scores, [4, 10, 14])
        self.assertLess(scores[0], scores[1])
        self.assertLess(scores[1], scores[2])

        # And so the plateau counter never fires on it.
        best, stale = None, 0
        for score in scores:
            stale = 0 if best is None or score > best else stale + 1
            best = score if best is None else max(best, score)
        self.assertEqual(stale, 0)
        self.assertGreater(PLATEAU_STRIKES, stale)

    def test_a_passing_fixture_outranks_more_criteria_elsewhere(self) -> None:
        """
        Fixtures stay the primary term -- passing them is the goal, not maximising criteria.
        """
        two_passing = TestConsultantScoring._round((True, 3, 3), (True, 3, 3), (False, 0, 9))
        more_criteria = TestConsultantScoring._round((False, 2, 3), (False, 2, 3), (False, 8, 9))

        self.assertEqual(ConsultantScoring.round_score(two_passing), (2, 6))
        self.assertEqual(ConsultantScoring.round_score(more_criteria), (0, 12))
        self.assertGreater(ConsultantScoring.round_score(two_passing), ConsultantScoring.round_score(more_criteria))

    def test_a_genuine_plateau_still_strikes_out(self) -> None:
        """
        The counter must keep working -- the fix is sensitivity, not disabling it.
        """
        stuck = TestConsultantScoring._round((False, 2, 5), (False, 1, 5))
        best, stale = None, 0
        for _ in range(PLATEAU_STRIKES + 1):
            score = ConsultantScoring.round_score(stuck)
            stale = 0 if best is None or score > best else stale + 1
            best = score if best is None else max(best, score)
        self.assertGreaterEqual(stale, PLATEAU_STRIKES)

    def test_a_regression_does_not_count_as_improvement(self) -> None:
        """
        A lower fixture score must not advance the best-so-far snapshot.
        """
        before = TestConsultantScoring._round((True, 5, 5), (False, 3, 5))
        after = TestConsultantScoring._round((False, 4, 5), (False, 3, 5))
        self.assertLess(ConsultantScoring.round_score(after), ConsultantScoring.round_score(before))

    def test_results_without_criteria_counts_still_score(self) -> None:
        """
        Infrastructure errors never reach a verdict and carry no criteria.
        """
        self.assertEqual(
            ConsultantScoring.round_score([{"fixture": "a", "passed": False, "infrastructure_error": True}]),
            (0, 0),
        )

    def test_extract_prefixed_returns_every_ungrounded_line(self) -> None:
        """Extract each ungrounded response line independently."""
        extracted: list[str] = ConsultantScoring.extract_prefixed(self.UNGROUNDED_REPLY, "UNGROUNDED:")
        self.assertEqual(
            extracted,
            [
                "it_password_reset_gsd_ticket.hocon: URLProvider: Includes the GSD URL",
                "legal_ambiguous.hocon: URLProvider: Includes at least one internal URL",
            ],
        )
