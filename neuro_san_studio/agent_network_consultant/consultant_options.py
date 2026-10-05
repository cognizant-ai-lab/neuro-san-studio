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

"""Typed options for one Network Consultant run."""

import re
from typing import NamedTuple

CONFIDENT_SUCCESS_RATIO = "3/3"
DEFAULT_MAX_ITERATIONS = 20


class ConsultantOptions(NamedTuple):
    """Carry the user-selected behavior for one Network Consultant run."""

    use_case: str | None = None
    hocon_file: str | None = None
    direction: str | None = None
    test_level: str = "normal"
    test_guidance: str = ""
    force_generate: bool = False
    ungrounded: str = "stop"
    only_fixtures: list[str] | None = None
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    success_ratio: str = CONFIDENT_SUCCESS_RATIO
    git_versions: bool = False

    def validate(self) -> None:
        """
        Validate the option combinations required by the Consultant workflow.

        :raises ValueError: If an option is malformed or required target context is missing.
        """
        if self.max_iterations < 0:
            raise ValueError(f"--max-iterations must be zero or greater, got {self.max_iterations}.")
        if not re.fullmatch(r"\d+/\d+", self.success_ratio):
            raise ValueError(f"--success-ratio must look like 'N/M' (e.g. '3/3'), got {self.success_ratio!r}.")
        if not self.use_case and not self.hocon_file:
            raise ValueError(
                "Provide --use-case (to create a network) or --hocon-file (to iterate on an existing one)."
            )

    def existing_hocon_file(self) -> str | None:
        """
        Return the requested existing-network reference.

        :return: The HOCON reference, or `None` when a network must be designed.
        """
        return self.hocon_file

    def design_request(self) -> str | None:
        """
        Return the use case supplied for a new network.

        :return: The design request, or `None` when an existing network was selected.
        """
        return self.use_case

    def target_direction(self) -> str:
        """
        Return the explicit direction, the new-network use case, or no additional direction.

        :return: The optional behavior the Consultant must preserve or create.
        """
        return self.direction or self.use_case or ""

    def should_generate_tests(self, fixtures_exist: bool) -> bool:
        """
        Decide whether the test generator must run.

        :param fixtures_exist: Whether reusable fixtures already exist for the target.
        :return: Whether tests should be generated.
        """
        return self.force_generate or not fixtures_exist

    def test_generation_request(self, network_name: str) -> str:
        """
        Build the test-generator request from the selected coverage options.

        :param network_name: The target network name.
        :return: The test-generator request.
        """
        request = f"Generate test cases for {network_name} with {self.test_level} coverage"
        guidance = self.test_guidance.strip()
        if guidance:
            request += f". Focus on: {guidance}"
        return request

    def test_level_name(self) -> str:
        """
        Return the selected test coverage level.

        :return: The coverage level name.
        """
        return self.test_level

    def fixes_disabled(self) -> bool:
        """
        Return whether only one fixture run was requested.

        :return: Whether the iterative fix loop is disabled.
        """
        return self.max_iterations == 0

    def iteration_numbers(self) -> range:
        """
        Return the one-based repair iteration numbers.

        :return: The configured iteration range.
        """
        return range(1, self.max_iterations + 1)

    def iteration_limit(self) -> int:
        """
        Return the configured repair safety limit.

        :return: The maximum number of repair iterations.
        """
        return self.max_iterations

    def fixture_selection(self) -> list[str] | None:
        """
        Return an isolated copy of the requested fixture subset.

        :return: The selected fixture names, or `None` for the complete suite.
        """
        if self.only_fixtures is None:
            return None
        return list(self.only_fixtures)

    def uses_git_versions(self) -> bool:
        """
        Return whether Git snapshots were requested.

        :return: Whether to create Git versions during the run.
        """
        return self.git_versions

    def selected_success_ratio(self) -> str:
        """
        Return the confidence verification ratio.

        :return: The configured success ratio.
        """
        return self.success_ratio

    def ungrounded_policy(self) -> str:
        """
        Return the selected handling for ungrounded criteria.

        :return: The ungrounded-criteria policy.
        """
        return self.ungrounded

    def stops_for_ungrounded(self) -> bool:
        """
        Return whether ungrounded criteria terminate the run.

        :return: Whether the run must stop for ungrounded criteria.
        """
        return self.ungrounded == "stop"
