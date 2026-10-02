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

"""Regression tests for standalone workflow validation and failure reporting."""

import subprocess
import sys
import unittest
from unittest.mock import patch

import requests

import tests.coded_tools.tools.now_agents.integration_tests.integration_test_full_workflow_e2e as workflow


class TestIntegrationTestFullWorkflowE2e(unittest.TestCase):
    """Verify validation outcomes and exception handling without live API calls."""

    def test_main_status_and_dependencies(self) -> None:
        """Fail for each unsuccessful stage and skip dependent validations."""
        cases = [
            (False, True, True, True, 1),
            (True, False, True, True, 1),
            (True, True, False, True, 1),
            (True, True, True, False, 1),
            (True, True, True, True, 0),
        ]
        for environment, connectivity, discovery, interaction, expected in cases:
            with (
                self.subTest(stages=(environment, connectivity, discovery, interaction)),
                patch.object(workflow, "load_environment", return_value=environment),
                patch.object(workflow, "test_basic_connectivity", return_value=connectivity) as connect,
                patch.object(
                    workflow, "test_agent_discovery", return_value=[{"sys_id": "agent"}] if discovery else []
                ) as discover,
                patch.object(workflow, "test_single_agent_interaction", return_value=interaction) as interact,
            ):
                self.assertEqual(workflow.main(), expected)
                self.assertEqual(connect.call_count, int(environment))
                self.assertEqual(discover.call_count, int(environment and connectivity))
                self.assertEqual(interact.call_count, int(environment and connectivity and discovery))

    def test_discovery_request_failure(self) -> None:
        """Report request failures with a traceback and no discovered agents."""
        with (
            patch.object(workflow.NowAgentAPIGetAgents, "invoke", side_effect=requests.Timeout("discovery timeout")),
            patch.object(workflow.traceback, "print_exc") as trace,
        ):
            self.assertEqual(workflow.test_agent_discovery(), [])
            trace.assert_called_once_with()

    def test_discovery_programming_error_propagates(self) -> None:
        """Unexpected errors must not become empty discovery results."""
        with (
            patch.object(workflow.NowAgentAPIGetAgents, "invoke", side_effect=RuntimeError("programming error")),
            self.assertRaisesRegex(RuntimeError, "programming error"),
        ):
            workflow.test_agent_discovery()

    def test_interaction_request_failure(self) -> None:
        """Report both sending and retrieval request failures with tracebacks."""
        for stage in ("send", "retrieve"):
            with (
                self.subTest(stage=stage),
                patch.object(workflow.NowAgentSendMessage, "invoke", return_value={"metadata": {}}) as send,
                patch.object(workflow.NowAgentRetrieveMessage, "invoke") as retrieve,
                patch.object(workflow.traceback, "print_exc") as trace,
            ):
                if stage == "send":
                    send.side_effect = requests.Timeout("send timeout")
                else:
                    retrieve.side_effect = requests.Timeout("retrieve timeout")
                self.assertFalse(workflow.test_single_agent_interaction([{"sys_id": "agent"}]))
                trace.assert_called_once_with()

    def test_interaction_programming_error_propagates(self) -> None:
        """Unexpected interaction errors keep their original exception."""
        with (
            patch.object(workflow.NowAgentSendMessage, "invoke", side_effect=RuntimeError("programming error")),
            self.assertRaisesRegex(RuntimeError, "programming error"),
        ):
            workflow.test_single_agent_interaction([{"sys_id": "agent"}])

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
                "integration_test_full_workflow_e2e', run_name='__main__')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("OVERALL: 0/4 tests passed", result.stdout)
