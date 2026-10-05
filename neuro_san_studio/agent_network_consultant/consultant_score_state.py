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

"""Plateau and best-version state for a Consultant run."""


class ConsultantScoreState:
    """Manage independent full-suite and subset scoring histories."""

    def __init__(self) -> None:
        """Initialize empty score histories and source snapshots."""
        self._best_score: tuple[int, int] | None = None
        self._stale_rounds = 0
        self._subset_best_score: tuple[int, int] | None = None
        self._subset_stale_rounds = 0
        self._best_hocon_text: str | None = None
        self._best_hocon_iteration: int | None = None

    def update(self, score: tuple[int, int], subset_check: bool) -> tuple[bool, tuple[int, int]] | None:
        """
        Update subset or full-suite plateau bookkeeping.

        :param score: The current fixture and criteria score.
        :param subset_check: Whether the score covers only a fixture subset.
        :return: Full-suite improvement and best score, or `None` for a subset round.
        """
        if subset_check:
            if self._subset_best_score is not None and score <= self._subset_best_score:
                self._subset_stale_rounds += 1
            else:
                self._subset_stale_rounds = 0
            self._subset_best_score = score if self._subset_best_score is None else max(score, self._subset_best_score)
            return None

        improved = self._best_score is None or score > self._best_score
        self._stale_rounds = 0 if improved else self._stale_rounds + 1
        self._best_score = score if self._best_score is None else max(score, self._best_score)
        return improved, self._best_score

    def subset_plateau_reached(self, strikes: int, subset_check: bool) -> bool:
        """
        Return whether subset scoring has stopped improving.

        :param strikes: The permitted consecutive stale rounds.
        :param subset_check: Whether the active results cover only a fixture subset.
        :return: Whether the subset plateau threshold was reached.
        """
        return subset_check and self._subset_stale_rounds >= strikes

    def reset_subset(self) -> None:
        """Reset subset-only score history after widening to the complete suite."""
        self._subset_best_score = None
        self._subset_stale_rounds = 0

    def plateau_reached(self, strikes: int) -> bool:
        """
        Return whether full-suite scoring has stopped improving.

        :param strikes: The permitted consecutive stale rounds.
        :return: Whether the full-suite plateau threshold was reached.
        """
        return self._stale_rounds >= strikes

    def remember_best_hocon(self, hocon_text: str, iteration: int) -> None:
        """
        Retain the target source associated with the current best score.

        :param hocon_text: The complete target HOCON source.
        :param iteration: The iteration that produced the source.
        """
        self._best_hocon_text = hocon_text
        self._best_hocon_iteration = iteration

    def best_hocon(self) -> tuple[str | None, int | None]:
        """
        Return the best source snapshot and its iteration.

        :return: The best HOCON text and iteration number.
        """
        return self._best_hocon_text, self._best_hocon_iteration
