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

"""Current fixture-round state for a Consultant run."""

from typing import Any


class ConsultantRoundState:
    """Manage fixture selection, results, failures, and chart position."""

    def __init__(self) -> None:
        """Initialize an empty fixture round."""
        self._retest_only: list[str] | None = None
        self._total_fixture_count = 0
        self._improvement_iteration = 0
        self._iteration = 0
        self._is_subset_check = False
        self._results: list[dict[str, Any]] = []
        self._failures: list[dict[str, Any]] = []

    def start_iteration(self, iteration: int) -> None:
        """
        Start one numbered repair iteration.

        :param iteration: The one-based iteration number.
        """
        self._iteration = iteration

    def iteration(self) -> int:
        """
        Return the active repair iteration number.

        :return: The active iteration number.
        """
        return self._iteration

    def begin_round(self) -> None:
        """Mark whether the next fixture run is a subset re-check."""
        self._is_subset_check = self._retest_only is not None

    def fixture_selection(self) -> list[str] | None:
        """
        Return an isolated copy of the pending fixture subset.

        :return: The fixture subset, or `None` for the complete suite.
        """
        if self._retest_only is None:
            return None
        return list(self._retest_only)

    def is_subset_check(self) -> bool:
        """
        Return whether the active results came from a fixture subset.

        :return: Whether the current round is a subset check.
        """
        return self._is_subset_check

    def record_results(self, results: list[dict[str, Any]], full_suite: bool = False) -> None:
        """
        Store fixture results and derive current failures.

        :param results: The fixture result records.
        :param full_suite: Whether the result authoritatively covers the complete suite.
        """
        self._results = list(results)
        self._failures = []
        for result in self._results:
            if not result.get("passed"):
                self._failures.append(result)
        if full_suite or not self._is_subset_check:
            self._total_fixture_count = len(self._results)

    def results(self) -> list[dict[str, Any]]:
        """
        Return an isolated list of current fixture results.

        :return: The current fixture results.
        """
        return list(self._results)

    def failures(self) -> list[dict[str, Any]]:
        """
        Return an isolated list of current fixture failures.

        :return: The current fixture failures.
        """
        return list(self._failures)

    def has_failures(self) -> bool:
        """
        Return whether the current fixture run has failures.

        :return: Whether failures remain.
        """
        return bool(self._failures)

    def failure_count(self) -> int:
        """
        Return the current fixture failure count.

        :return: The number of failing fixtures.
        """
        return len(self._failures)

    def result_count(self) -> int:
        """
        Return the current fixture result count.

        :return: The number of fixture results.
        """
        return len(self._results)

    def passing_count(self) -> int:
        """
        Return the passing count against the complete suite size.

        :return: The number of passing fixtures.
        """
        return self._total_fixture_count - len(self._failures)

    def total_fixture_count(self) -> int:
        """
        Return the complete suite size.

        :return: The total fixture count.
        """
        return self._total_fixture_count

    def next_improvement_iteration(self) -> int:
        """
        Advance and return the chart's improvement iteration.

        :return: The next improvement iteration number.
        """
        self._improvement_iteration += 1
        return self._improvement_iteration

    def infrastructure_errors(self) -> list[dict[str, Any]]:
        """
        Return fixture results caused by test infrastructure failures.

        :return: The infrastructure-error results.
        """
        errors: list[dict[str, Any]] = []
        for result in self._results:
            if result.get("infrastructure_error"):
                errors.append(result)
        return errors

    def clear_subset(self) -> None:
        """Clear the pending fixture subset."""
        self._retest_only = None
        self._is_subset_check = False

    def schedule_failure_retests(self) -> None:
        """Schedule every currently failing fixture for the next round."""
        self._retest_only = []
        for failure in self._failures:
            self._retest_only.append(str(failure.get("fixture", "")))
