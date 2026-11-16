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

"""Tests for the isolated Agent Network Consultant child environment."""

import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.network_test_environment import NetworkTestEnvironment


class TestNetworkTestEnvironment(TestCase):
    """Verify child configuration never mutates caller-owned environment values."""

    def test_create_returns_defaults_without_changing_the_current_process(self) -> None:
        """Build direct-test defaults only in the returned child mapping."""
        with tempfile.TemporaryDirectory() as project_root:
            mcp_directory = Path(project_root) / "mcp"
            mcp_directory.mkdir()
            mcp_file = mcp_directory / "mcp_info.hocon"
            mcp_file.write_text("{}\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                scope = NetworkTestEnvironment(project_root)
                child_environment = scope.create()
                thinking_directory = scope.owned_thinking_directory()

                self.assertEqual(
                    os.path.join(project_root, "registries", "manifest.hocon"),
                    child_environment.get("AGENT_MANIFEST_FILE"),
                )
                self.assertEqual(os.path.join(project_root, "coded_tools"), child_environment.get("AGENT_TOOL_PATH"))
                self.assertEqual(str(mcp_file), child_environment.get("MCP_SERVERS_INFO_FILE"))
                self.assertEqual(project_root, child_environment.get("PYTHONPATH"))
                self.assertEqual(thinking_directory, child_environment.get("AGENT_TEST_THINKING_BASIS"))
                self.assertIsNotNone(thinking_directory)
                self.assertTrue(os.path.isdir(thinking_directory or ""))
                self.assertFalse(os.environ)

            NetworkTestEnvironment.cleanup_owned_thinking_directory(thinking_directory)
            self.assertFalse(os.path.exists(thinking_directory or ""))
            NetworkTestEnvironment.cleanup_owned_thinking_directory(thinking_directory)

    def test_create_preserves_existing_values_without_owning_their_thinking_directory(self) -> None:
        """Copy every operator-provided value without changing or deleting it."""
        existing: dict[str, str] = {
            "AGENT_MANIFEST_FILE": "custom/manifest.hocon",
            "AGENT_TOOL_PATH": "custom_tools",
            "MCP_SERVERS_INFO_FILE": "custom/mcp.hocon",
            "AGENT_TOOLBOX_INFO_FILE": "custom/toolbox.hocon",
            "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE": "custom/designer_toolbox.hocon",
            "AGENT_TEST_THINKING_BASIS": "custom/thinking",
        }
        with patch.dict(os.environ, existing, clear=True):
            scope = NetworkTestEnvironment()
            child_environment = scope.create()

            for name, value in existing.items():
                self.assertEqual(value, os.environ.get(name))
                self.assertEqual(value, child_environment.get(name))
            self.assertIsNone(scope.owned_thinking_directory())

    def test_cleanup_refuses_an_unverified_directory(self) -> None:
        """Never recursively delete a caller-selected directory outside the owned temporary namespace."""
        with tempfile.TemporaryDirectory() as unverified_directory:
            with self.assertLogs(
                "neuro_san_studio.agent_network_consultant.network_test_environment", level="WARNING"
            ) as captured:
                NetworkTestEnvironment.cleanup_owned_thinking_directory(unverified_directory)

            self.assertTrue(os.path.isdir(unverified_directory))
            self.assertIn("Refusing to remove unverified", "\n".join(captured.output))

    def test_create_failure_leaves_the_current_process_unchanged(self) -> None:
        """Propagate temporary-directory failures without writing process environment values."""
        with tempfile.TemporaryDirectory() as project_root:
            with patch.dict(os.environ, {}, clear=True):
                with (
                    patch(
                        "neuro_san_studio.agent_network_consultant.network_test_environment.tempfile.mkdtemp",
                        side_effect=OSError("creation failed"),
                    ),
                    self.assertRaisesRegex(OSError, "creation failed"),
                ):
                    NetworkTestEnvironment(project_root).create()

                self.assertFalse(os.environ)
