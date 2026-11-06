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

"""Regression tests for debug discovery validation and failure reporting."""

import subprocess
import sys
import unittest
from unittest.mock import patch

import requests

import tests.coded_tools.tools.now_agents.integration_tests.integration_test_agent_discovery_debug as discovery


class TestIntegrationTestAgentDiscoveryDebug(unittest.TestCase):
    """Verify debug discovery outcomes without live API calls."""

    def test_discovery_outcomes(self) -> None:
        """Only a nonempty agent list without an API error is successful."""
        cases = [
            ({"result": [{"sys_id": "agent"}]}, True),
            ({"result": []}, False),
            ({"error": "HTTP 403", "result": [{"sys_id": "agent"}]}, False),
            ({"result": "invalid"}, False),
            ({}, False),
            ("invalid", False),
        ]
        for response, expected in cases:
            with (
                self.subTest(response=response),
                patch.object(discovery.NowAgentAPIGetAgents, "invoke", return_value=response),
            ):
                self.assertEqual(discovery.test_agents_with_debug(), expected)

    def test_discovery_request_failure(self) -> None:
        """Request failures report a traceback and an unsuccessful result."""
        with (
            patch.object(discovery.NowAgentAPIGetAgents, "invoke", side_effect=requests.Timeout("discovery timeout")),
            patch.object(discovery.traceback, "print_exc") as trace,
        ):
            self.assertFalse(discovery.test_agents_with_debug())
            trace.assert_called_once_with()

    def test_discovery_programming_error_propagates(self) -> None:
        """Unexpected exceptions must not be treated as successful execution."""
        with (
            patch.object(discovery.NowAgentAPIGetAgents, "invoke", side_effect=RuntimeError("programming error")),
            self.assertRaisesRegex(RuntimeError, "programming error"),
        ):
            discovery.test_agents_with_debug()

    def test_cli_failure_status(self) -> None:
        """The actual module entry point must fail on an API error response."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; from unittest.mock import patch; "
                "\nwith patch('dotenv.load_dotenv'), patch('coded_tools.tools.now_agents."
                "nowagent_api_get_agents.NowAgentAPIGetAgents.invoke', return_value={'error': 'HTTP 403'}):\n"
                "    runpy.run_module('tests.coded_tools.tools.now_agents.integration_tests."
                "integration_test_agent_discovery_debug', run_name='__main__')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("ERROR in response: HTTP 403", result.stdout)
