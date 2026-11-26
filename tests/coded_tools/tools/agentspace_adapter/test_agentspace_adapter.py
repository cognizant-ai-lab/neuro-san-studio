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

import asyncio
import threading
from typing import Any
from unittest import TestCase
from unittest.mock import patch

import pytest

# Optional SDKs must be checked before importing the tool, as in the arxiv retriever tests.
pytest.importorskip("google.cloud.discoveryengine_v1", reason="optional tool dependency is not installed")
pytest.importorskip("google.api_core.client_options", reason="optional tool dependency is not installed")

# The tool import follows the optional dependency checks.
# pylint: disable=wrong-import-position
from coded_tools.tools.agentspace_adapter.agentspace_adapter import AgentSpaceSearch  # noqa: E402


class TestAgentSpaceSearch(TestCase):
    """Regression tests for AgentSpaceSearch async execution."""

    @staticmethod
    def invoke_in_worker(args: dict[str, Any], sly_data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Simulate synchronous work that updates session state and reports its thread."""
        sly_data.update(session_path="test-session")
        return threading.get_ident(), args

    def test_async_invoke(self) -> None:
        """Run invoke off the event loop, preserving arguments, return values, and session updates."""
        tool = AgentSpaceSearch()
        args = {"inquiry": "test"}
        sly_data: dict[str, Any] = {}
        with patch.object(tool, "invoke", side_effect=self.invoke_in_worker) as invoke:
            worker_thread, result = asyncio.run(tool.async_invoke(args, sly_data))
        self.assertNotEqual(worker_thread, threading.get_ident())
        self.assertIs(result, args)
        invoke.assert_called_once_with(args, sly_data)
        call_args, call_sly_data = invoke.call_args.args
        self.assertIs(call_args, args)
        self.assertIs(call_sly_data, sly_data)
        self.assertEqual(sly_data.get("session_path"), "test-session")

    def test_async_invoke_propagates_exception(self) -> None:
        """Propagate the original synchronous exception to the async caller."""
        tool = AgentSpaceSearch()
        error = RuntimeError("tool failed")
        with patch.object(tool, "invoke", side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                asyncio.run(tool.async_invoke({}, {}))
        self.assertIs(raised.exception, error)
