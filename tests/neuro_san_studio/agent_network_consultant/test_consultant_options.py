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

"""Tests for Agent Network Consultant option data."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions


class TestConsultantOptions(TestCase):
    """Verify option defaults and caller-selected values."""

    def test_defaults_describe_the_standard_consultant_run(self) -> None:
        """Expose stable defaults without embedding workflow decisions in the data class."""
        options = ConsultantOptions()

        self.assertEqual("normal", options.test_level)
        self.assertEqual("stop", options.ungrounded)
        self.assertEqual(ConsultantOptions.DEFAULT_MAX_ITERATIONS, options.max_iterations)
        self.assertEqual(ConsultantOptions.CONFIDENT_SUCCESS_RATIO, options.success_ratio)

    def test_retains_caller_selected_values(self) -> None:
        """Carry inputs without interpreting them as workflow policy."""
        fixture_names = ["one.hocon"]
        options = ConsultantOptions(
            use_case="Create a network",
            test_level="max",
            only_fixtures=fixture_names,
            max_iterations=4,
        )

        self.assertEqual("Create a network", options.use_case)
        self.assertEqual("max", options.test_level)
        self.assertIs(fixture_names, options.only_fixtures)
        self.assertEqual(4, options.max_iterations)
