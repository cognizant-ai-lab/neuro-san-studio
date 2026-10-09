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

"""Recorded scores for an Agent Network Consultant run."""


class ConsultantScoreState:
    """Store independent full-suite and subset score histories without applying scoring policy."""

    def __init__(self) -> None:
        """Initialize empty full-suite and subset score histories."""
        self._full_scores: list[tuple[int, int]] = []
        self._subset_scores: list[tuple[int, int]] = []

    def record_full_score(self, score: tuple[int, int]) -> None:
        """
        Append one authoritative full-suite score.

        :param score: The current fixture and criteria score.
        """
        self._full_scores.append(score)

    def record_subset_score(self, score: tuple[int, int]) -> None:
        """
        Append one fixture-subset score.

        :param score: The current fixture and criteria score.
        """
        self._subset_scores.append(score)

    def full_scores(self) -> list[tuple[int, int]]:
        """
        Return an isolated copy of the full-suite score history.

        :return: The recorded full-suite scores.
        """
        return list(self._full_scores)

    def subset_scores(self) -> list[tuple[int, int]]:
        """
        Return an isolated copy of the fixture-subset score history.

        :return: The recorded fixture-subset scores.
        """
        return list(self._subset_scores)

    def clear_subset_scores(self) -> None:
        """Discard subset-only scores after widening to the complete suite."""
        self._subset_scores.clear()
