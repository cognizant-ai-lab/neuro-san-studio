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

"""Adapt Agent Network Consultant fixture requests to Neuro SAN's test drivers."""

import os
from copy import deepcopy
from typing import Any
from unittest import TestCase

from neuro_san.test.driver.data_driven_agent_test_driver import DataDrivenAgentTestDriver
from neuro_san.test.driver.data_driven_tests_driver import DataDrivenTestsDriver
from neuro_san.test.util.tests_util import TestsUtil

from neuro_san_studio.agent_network_consultant.scorecard_assert_forwarder import ScorecardAssertForwarder


class FixtureDriver:
    """Run one fixture behind a narrow compatibility boundary to Neuro SAN's test package."""

    def __init__(self, fixture_path: str, success_ratio_override: str | None = None) -> None:
        """
        Initialize one Neuro SAN fixture-driver request.

        :param fixture_path: Path to the fixture HOCON file.
        :param success_ratio_override: The optional ratio used for this execution without changing the fixture.
        """
        self._fixture_path = fixture_path
        self._fixture_name = os.path.basename(fixture_path)
        self._success_ratio_override = success_ratio_override
        # Neuro SAN's UnitTestAssertForwarder requires a TestCase that supplies assertion implementations.
        self._asserts = ScorecardAssertForwarder(TestCase())

    def execute(self) -> None:
        """Execute the fixture through the appropriate Neuro SAN test-driver path."""
        if self._success_ratio_override is None:
            driver = DataDrivenAgentTestDriver(self._asserts, test_name=self._fixture_name)
            driver.one_test(self._fixture_path)
            return
        self._execute_with_ratio_override()

    def assertions(self) -> ScorecardAssertForwarder:
        """
        Return the assertion forwarder that recorded this fixture execution.

        :return: The fixture's assertion forwarder.
        """
        return self._asserts

    def _execute_with_ratio_override(self) -> None:
        """
        Execute a parsed fixture with an in-memory success-ratio override.

        Neuro SAN's ``DataDrivenAgentTestDriver.one_test`` currently accepts only a file path. This adapter keeps
        the unavoidable compatibility logic in one place until that public driver supports an in-memory override.
        """
        test_case: dict[str, Any] = TestsUtil.parse_hocon_test_case(None, self._fixture_path)
        test_case.update({"success_ratio": self._success_ratio_override})
        agent = test_case.get("agent")
        self._asserts.assertIsNotNone(agent)
        required_successes, iteration_count = self._ratio_counts()
        test_cases = self._repeated_test_cases(test_case, iteration_count)
        test_driver = DataDrivenTestsDriver(self._asserts, test_name=self._fixture_name)
        test_results = test_driver.run_tests(test_cases, required_successes)
        successful = self._successful_result_count(test_results, required_successes)
        if successful < required_successes:
            ratio_summary = (successful, required_successes, iteration_count)
            self._raise_ratio_failure(test_results, ratio_summary, agent)

    def _ratio_counts(self) -> tuple[int, int]:
        """
        Validate the configured ratio and return its bounded required and total counts.

        :return: The bounded required success count and iteration count.
        """
        ratio = self._success_ratio_override or ""
        self._asserts.assertIn("/", ratio)
        ratio_parts = ratio.split("/")
        iteration_count = max(1, int(ratio_parts[-1]))
        return min(int(ratio_parts[0]), iteration_count), iteration_count

    @staticmethod
    def _repeated_test_cases(test_case: dict[str, Any], iteration_count: int) -> list[dict[str, Any]]:
        """
        Create an isolated test-case mapping for every fixture attempt.

        :param test_case: The parsed fixture test case.
        :param iteration_count: The number of fixture attempts to create.
        :return: Deep copies of the fixture test case.
        """
        test_cases: list[dict[str, Any]] = []
        for _index in range(iteration_count):
            test_cases.append(deepcopy(test_case))
        return test_cases

    @staticmethod
    def _successful_result_count(test_results: list[Any], required_successes: int) -> int:
        """
        Count successful attempts until the fixture threshold is met.

        :param test_results: The captured result for every completed fixture attempt.
        :param required_successes: The number of successful attempts required to pass.
        :return: The observed successful attempt count, capped at the required count.
        """
        successful = 0
        for test_result in test_results:
            if not test_result.get_asserts():
                successful += 1
                if successful >= required_successes:
                    return successful
        return successful

    def _raise_ratio_failure(
        self,
        test_results: list[Any],
        ratio_summary: tuple[int, int, int],
        agent: Any,
    ) -> None:
        """
        Raise the upstream-compatible error from the first failed fixture attempt.

        :param test_results: The captured result for every completed fixture attempt.
        :param ratio_summary: The successful, required, and attempted run counts.
        :param agent: The fixture's configured agent name.
        :raises AssertionError: Raised from the first captured assertion when the ratio was not met.
        """
        for test_result in test_results:
            failures = test_result.get_asserts()
            if failures:
                self._raise_first_ratio_failure(failures[0], ratio_summary, agent)

    def _raise_first_ratio_failure(
        self,
        failure: BaseException,
        ratio_summary: tuple[int, int, int],
        agent: Any,
    ) -> None:
        """
        Raise one ratio failure with the upstream-compatible message.

        :param failure: The first captured fixture assertion.
        :param ratio_summary: The successful, required, and attempted run counts.
        :param agent: The fixture's configured agent name.
        :raises AssertionError: Always raised with the ratio failure as its cause.
        """
        successful, required_successes, iteration_count = ratio_summary
        message = (
            f"\n{successful} of {iteration_count} iterations on agent {agent} were successful.\n"
            f"Need at least {required_successes} to consider {self._fixture_path} test to be successful.\n"
        )
        raise AssertionError(message) from failure
