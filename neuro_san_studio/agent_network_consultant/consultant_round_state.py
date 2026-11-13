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

"""Current fixture-round state for an Agent Network Consultant run."""

from typing import Any


class ConsultantRoundState:
    """Manage the active fixture round and its pending failure re-check.

    A full-suite round establishes the authoritative fixture count. A subset check runs only fixtures that failed
    the preceding round, so its results must not replace the complete-suite count.
    """

    def __init__(self) -> None:
        """Initialize an empty fixture round."""
        self._retest_only: list[str] | None = None
        self._total_fixture_count = 0
        self._iteration = 0
        self._is_subset_check = False
        self._results: list[dict[str, Any]] = []
        self._failures: list[dict[str, Any]] = []
        self._success_ratio_overrides: dict[str, str] = {}

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

    def set_fixture_selection(
        self,
        fixture_names: list[str] | None,
        total_fixture_count: int | None = None,
    ) -> None:
        """
        Store the fixtures supplied by the caller for the next round.

        :param fixture_names: The fixture basenames to run, or `None` for the complete suite.
        :param total_fixture_count: The discovered complete-suite size, when already known.
        """
        self._retest_only = None if fixture_names is None else list(fixture_names)
        if total_fixture_count is not None:
            self._total_fixture_count = total_fixture_count

    def fixture_selection(self) -> list[str] | None:
        """
        Return an isolated copy of the fixtures pending a failure re-check.

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
        if full_suite or not self._is_subset_check or self._total_fixture_count == 0:
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

    def success_ratio_overrides(self) -> dict[str, str]:
        """
        Return an isolated copy of fixture execution overrides.

        :return: Success ratios keyed by fixture basename.
        """
        return dict(self._success_ratio_overrides)

    def has_success_ratio_overrides(self) -> bool:
        """
        Return whether confidence handling selected stricter fixture ratios.

        :return: Whether any in-memory success-ratio overrides are active.
        """
        return bool(self._success_ratio_overrides)

    def remember_success_ratio_overrides(self, fixture_names: list[str], ratio: str) -> None:
        """
        Retain stricter ratios for subsequent executions of selected fixtures.

        :param fixture_names: Fixture basenames selected for stricter verification.
        :param ratio: The success ratio to use for those fixture executions.
        """
        for fixture_name in fixture_names:
            self._success_ratio_overrides.update({fixture_name: ratio})
