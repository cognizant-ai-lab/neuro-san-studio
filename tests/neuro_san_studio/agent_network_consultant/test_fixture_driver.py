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

"""Tests for the Neuro SAN fixture-driver compatibility boundary."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.fixture_driver import FixtureDriver


class TestFixtureDriver(TestCase):
    """Verify fixture-driver overrides do not change source fixture files."""

    def test_success_ratio_override_is_applied_in_memory(self) -> None:
        """Run the requested number of attempts without changing the fixture file."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "example.hocon"
            fixture_text = '{"agent": "example", "success_ratio": "1/1", "interactions": []}'
            fixture.write_text(fixture_text, encoding="utf-8")
            successful_result = Mock()
            successful_result.get_asserts.return_value = []
            driver = FixtureDriver(str(fixture), "3/3")

            with patch(
                "neuro_san_studio.agent_network_consultant.fixture_driver.DataDrivenTestsDriver.run_tests",
                return_value=[successful_result, successful_result, successful_result],
            ) as run_tests:
                driver.execute()

            test_cases, required_successes = run_tests.call_args.args
            self.assertEqual(3, len(test_cases))
            self.assertEqual(3, required_successes)
            for test_case in test_cases:
                self.assertEqual("3/3", test_case.get("success_ratio"))
            self.assertEqual(fixture_text, fixture.read_text(encoding="utf-8"))
