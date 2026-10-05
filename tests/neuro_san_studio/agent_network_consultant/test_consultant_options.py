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

"""Tests for behavioral Network Consultant options."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions


class TestConsultantOptions(TestCase):
    """Verify option behavior without exposing orchestration to option fields."""

    def test_builds_a_guided_test_generation_request(self) -> None:
        """Build a test request containing the selected coverage and trimmed guidance."""
        options = ConsultantOptions(use_case="Create a network", test_level="thorough", test_guidance="  edge cases ")

        request = options.test_generation_request("example")

        self.assertEqual(request, "Generate test cases for example with thorough coverage. Focus on: edge cases")

    def test_validation_accepts_an_existing_target_without_direction(self) -> None:
        """Allow fixture failures to guide an existing-network run when no direction is supplied."""
        options = ConsultantOptions(hocon_file="example.hocon")

        options.validate()

        self.assertEqual("", options.target_direction())

    def test_validation_accepts_zero_max_iterations(self) -> None:
        """Preserve zero as the documented mode that runs tests without attempting repairs."""
        ConsultantOptions(hocon_file="example.hocon", max_iterations=0).validate()

    def test_validation_rejects_negative_max_iterations(self) -> None:
        """Reject an iteration limit that would silently skip the repair loop."""
        options = ConsultantOptions(hocon_file="example.hocon", max_iterations=-1)

        with self.assertRaisesRegex(ValueError, "--max-iterations must be zero or greater"):
            options.validate()

    def test_fixture_selection_returns_an_isolated_list(self) -> None:
        """Prevent callers from mutating the configured fixture selection."""
        options = ConsultantOptions(use_case="Create a network", only_fixtures=["one.hocon"])

        selection = options.fixture_selection()
        selection.append("two.hocon")

        self.assertEqual(options.fixture_selection(), ["one.hocon"])
