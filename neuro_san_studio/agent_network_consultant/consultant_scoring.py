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

"""Round scoring policy for Agent Network Consultant runs."""

from typing import Any

from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState


class ConsultantScoring:
    """Own score calculation, history comparison, and all repair-loop stopping thresholds."""

    # Eighty percent is the full-suite acceptance floor for a successful improvement run.
    GOOD_ENOUGH_RATIO = 0.8
    # Three stale rounds bound spending when fixes make no measurable progress.
    PLATEAU_STRIKES = 3

    def __init__(self, state: ConsultantScoreState) -> None:
        """
        Store the score history for one Agent Network Consultant run.

        :param state: The policy-free full-suite and subset score history.
        """
        self._state = state

    def round_score(self, results: list[dict[str, Any]]) -> tuple[int, int]:
        """
        Score one result set for plateau detection, prioritizing fixtures before individual criteria.

        Criteria act as a tiebreaker so progress within still-failing fixtures remains visible.

        :param results: The fixture result records.
        :return: The passing-fixture count and passed-criterion count.
        """
        passing = 0
        criteria = 0
        for result in results:
            if result.get("passed"):
                passing += 1
            criteria += result.get("criteria_passed", 0)
        return passing, criteria

    def criteria_total(self, results: list[dict[str, Any]]) -> int:
        """
        Return the total number of evaluated criteria in one fixture result set.

        :param results: The fixture result records.
        :return: The total evaluated-criteria count.
        """
        criteria_total = 0
        for result in results:
            criteria_total += result.get("criteria_total", 0)
        return criteria_total

    def record(self, score: tuple[int, int], subset_check: bool) -> tuple[int, int] | None:
        """
        Append a score to the matching history and return the best complete-suite score.

        :param score: The current fixture and criteria score.
        :param subset_check: Whether the score covers only a fixture subset.
        :return: The best complete-suite score, or `None` after a subset score.
        """
        if subset_check:
            self._state.record_subset_score(score)
            return None
        self._state.record_full_score(score)
        return self.best_full_score()

    def clear_subset_history(self) -> None:
        """Discard subset-only history after widening back to the complete suite."""
        self._state.clear_subset_scores()

    def best_full_score(self) -> tuple[int, int] | None:
        """
        Return the highest complete-suite score observed in this run.

        :return: The best complete-suite score, or `None` before a complete-suite result.
        """
        scores = self._state.full_scores()
        if not scores:
            return None
        return max(scores)

    def subset_plateau_reached(self, subset_check: bool) -> bool:
        """
        Return whether consecutive subset results have stopped improving.

        :param subset_check: Whether the active results cover only a fixture subset.
        :return: Whether the subset plateau threshold was reached.
        """
        return subset_check and self._stale_rounds(self._state.subset_scores()) >= self.PLATEAU_STRIKES

    def plateau_reached(self) -> bool:
        """
        Return whether consecutive complete-suite results have stopped improving.

        :return: Whether the complete-suite plateau threshold was reached.
        """
        return self._stale_rounds(self._state.full_scores()) >= self.PLATEAU_STRIKES

    def regresses_from_best(self, score: tuple[int, int]) -> bool:
        """
        Return whether accepting a complete-suite score would preserve a regression.

        :param score: The current complete-suite fixture and criteria score.
        :return: Whether the score is lower than the best verified score.
        """
        best_score = self.best_full_score()
        return best_score is not None and score < best_score

    def good_enough(self, passed: int, total: int) -> bool:
        """
        Return whether a full-suite result clears the acceptance threshold.

        :param passed: The number of passing fixtures.
        :param total: The total number of fixtures.
        :return: Whether the requested condition is met.
        """
        return total > 0 and passed >= self.GOOD_ENOUGH_RATIO * total

    def acceptance_percentage(self) -> float:
        """
        Return the complete-suite acceptance threshold as a percentage.

        :return: The acceptance threshold percentage.
        """
        return self.GOOD_ENOUGH_RATIO * 100

    @staticmethod
    def _stale_rounds(scores: list[tuple[int, int]]) -> int:
        """
        Count consecutive non-improving scores at the end of one history.

        :param scores: The ordered full-suite or subset score history.
        :return: The number of trailing rounds without a new best score.
        """
        best_score: tuple[int, int] | None = None
        stale_rounds = 0
        for score in scores:
            if best_score is None or score > best_score:
                best_score = score
                stale_rounds = 0
            else:
                stale_rounds += 1
        return stale_rounds
