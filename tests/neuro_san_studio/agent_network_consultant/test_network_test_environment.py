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

"""Tests for the scoped Network Consultant fixture environment."""

import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.network_test_environment import NetworkTestEnvironment


class TestNetworkTestEnvironment(TestCase):
    """Verify direct-test settings are isolated and caller-owned values survive unchanged."""

    def test_scope_restores_missing_values_and_removes_thinking_directory(self) -> None:
        """Remove temporary values and files after a scope created every required default."""
        with tempfile.TemporaryDirectory() as project_root:
            with patch.dict(os.environ, {}, clear=True):
                with NetworkTestEnvironment(project_root):
                    thinking_directory = os.environ.get("AGENT_TEST_THINKING_BASIS", "")
                    self.assertEqual(
                        os.path.join(project_root, "registries", "manifest.hocon"),
                        os.environ.get("AGENT_MANIFEST_FILE"),
                    )
                    self.assertEqual("coded_tools", os.environ.get("AGENT_TOOL_PATH"))
                    self.assertTrue(os.path.isdir(thinking_directory))

                self.assertFalse(os.environ)
                self.assertFalse(os.path.exists(thinking_directory))

    def test_scope_preserves_existing_values(self) -> None:
        """Leave every operator-provided value unchanged during and after the fixture run."""
        existing: dict[str, str] = {
            "AGENT_MANIFEST_FILE": "custom/manifest.hocon",
            "AGENT_TOOL_PATH": "custom_tools",
            "AGENT_TOOLBOX_INFO_FILE": "custom/toolbox.hocon",
            "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE": "custom/designer_toolbox.hocon",
            "AGENT_TEST_THINKING_BASIS": "custom/thinking",
        }
        with patch.dict(os.environ, existing, clear=True):
            with NetworkTestEnvironment():
                for name, value in existing.items():
                    self.assertEqual(value, os.environ.get(name))

            for name, value in existing.items():
                self.assertEqual(value, os.environ.get(name))

    def test_scope_restores_environment_after_an_exception(self) -> None:
        """Restore caller state and delete temporary thinking files when fixture execution raises."""
        with tempfile.TemporaryDirectory() as project_root:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "fixture failed"):
                    with NetworkTestEnvironment(project_root):
                        thinking_directory = os.environ.get("AGENT_TEST_THINKING_BASIS", "")
                        raise RuntimeError("fixture failed")

                self.assertFalse(os.environ)
                self.assertFalse(os.path.exists(thinking_directory))
