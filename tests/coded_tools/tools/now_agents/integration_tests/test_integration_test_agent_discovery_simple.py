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

"""Regression tests for simple discovery validation and failure reporting."""

import subprocess
import sys
import unittest
from unittest.mock import patch

import requests

import tests.coded_tools.tools.now_agents.integration_tests.integration_test_agent_discovery_simple as discovery


class TestIntegrationTestAgentDiscoverySimple(unittest.TestCase):
    """Verify discovery outcomes and exceptions without live API calls."""

    def test_main_status_and_dependencies(self) -> None:
        """Fail for missing setup, failed connectivity, or empty discovery."""
        cases = [(False, True, True, 1), (True, False, True, 1), (True, True, False, 1), (True, True, True, 0)]
        for environment, connectivity, agents_found, expected in cases:
            with (
                self.subTest(stages=(environment, connectivity, agents_found)),
                patch.object(discovery, "load_environment", return_value=environment),
                patch.object(discovery, "test_connectivity", return_value=connectivity) as connect,
                patch.object(
                    discovery, "test_agent_discovery", return_value=[{"sys_id": "agent"}] if agents_found else []
                ) as discover,
            ):
                self.assertEqual(discovery.main(), expected)
                self.assertEqual(connect.call_count, int(environment))
                self.assertEqual(discover.call_count, int(environment and connectivity))

    def test_discovery_request_failure(self) -> None:
        """Request failures report a traceback and unsuccessful discovery."""
        with (
            patch.object(discovery.NowAgentAPIGetAgents, "invoke", side_effect=requests.Timeout("discovery timeout")),
            patch.object(discovery.traceback, "print_exc") as trace,
        ):
            self.assertEqual(discovery.test_agent_discovery(), [])
            trace.assert_called_once_with()

    def test_discovery_programming_error_propagates(self) -> None:
        """Programming errors retain their original exception."""
        with (
            patch.object(discovery.NowAgentAPIGetAgents, "invoke", side_effect=RuntimeError("programming error")),
            self.assertRaisesRegex(RuntimeError, "programming error"),
        ):
            discovery.test_agent_discovery()

    def test_cli_failure_status(self) -> None:
        """The actual module entry point must fail when environment setup fails."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; from unittest.mock import patch; "
                "from coded_tools.tools.now_agents.nowagent_api_get_agents import NowAgentAPIGetAgents; "
                "\nwith patch('pathlib.Path.exists', return_value=False):\n"
                "    runpy.run_module('tests.coded_tools.tools.now_agents.integration_tests."
                "integration_test_agent_discovery_simple', run_name='__main__')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("ERROR: .env file not found!", result.stdout)
