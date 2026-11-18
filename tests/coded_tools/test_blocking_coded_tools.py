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

"""Exercise blocking tools' async entry points without their optional SDK dependencies."""

import ast
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from typing import Callable
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock


class TestBlockingCodedTools(IsolatedAsyncioTestCase):
    """Check worker-thread execution and the delegation contract for each affected tool."""

    TOOL_PATHS = (
        "coded_tools/tools/now_agents/nowagent_api_retrieve_message.py",
        "coded_tools/tools/now_agents/nowagent_api_send_message.py",
        "coded_tools/tools/now_agents/nowagent_api_get_agents.py",
        "coded_tools/industry/news_sentiment_analysis/web_scraping_technician.py",
        "coded_tools/industry/airline_policy/webpage_reader.py",
        "coded_tools/tools/visual_question_answering/vqa.py",
        "neuro_san_studio/coded_tools/wikimedia_media_search.py",
        "coded_tools/tools/agentforce/agentforce_api.py",
        "coded_tools/tools/agentspace_adapter/agentspace_adapter.py",
    )

    @staticmethod
    def load_async_invoke(relative_path: str) -> Callable[..., Any]:
        """Load the real async method without importing optional SDKs or configuring services."""
        path = Path(__file__).resolve().parents[2] / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        method = next(
            node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_invoke"
        )
        # Compile the unchanged method body; postponed annotations avoid requiring SDK types.
        module = ast.Module(
            body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method],
            type_ignores=[],
        )
        namespace: dict[str, Any] = {"asyncio": asyncio}
        exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)  # pylint: disable=exec-used
        return namespace.get("async_invoke")

    @staticmethod
    def worker_thread_id(_args: dict[str, Any], _sly_data: dict[str, Any]) -> int:
        """Report which thread executes the synchronous call."""
        return threading.get_ident()

    async def test_invoke_runs_outside_event_loop_thread(self) -> None:
        """Blocking work must execute on a different thread from the event loop."""
        for path in self.TOOL_PATHS:
            with self.subTest(tool=path):
                invoke = Mock(side_effect=self.worker_thread_id)
                tool = SimpleNamespace(invoke=invoke)
                worker_thread = await self.load_async_invoke(path)(tool, {}, {})
                self.assertNotEqual(worker_thread, threading.get_ident())
                invoke.assert_called_once_with({}, {})

    async def test_result_and_shared_arguments_are_preserved(self) -> None:
        """Await completion and preserve result identity and writes to the caller's sly data."""
        for path in self.TOOL_PATHS:
            with self.subTest(tool=path):
                args = {"inquiry": "test"}
                sly_data: dict[str, Any] = {}
                invoke = Mock(side_effect=self.update_session)
                tool = SimpleNamespace(invoke=invoke)
                self.assertIs(await self.load_async_invoke(path)(tool, args, sly_data), args)
                invoke.assert_called_once_with(args, sly_data)
                call_args, call_sly_data = invoke.call_args.args
                self.assertIs(call_args, args)
                self.assertIs(call_sly_data, sly_data)
                self.assertEqual(sly_data.get("session_path"), "test-session")

    @staticmethod
    def update_session(args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate a synchronous tool that updates the caller's session state."""
        sly_data.update(session_path="test-session")
        return args

    async def test_invoke_exceptions_propagate(self) -> None:
        """Errors in worker threads must still reach the caller."""
        for path in self.TOOL_PATHS:
            with self.subTest(tool=path):
                error = RuntimeError("tool failed")
                tool = SimpleNamespace(invoke=Mock(side_effect=error))
                with self.assertRaises(RuntimeError) as raised:
                    await self.load_async_invoke(path)(tool, {}, {})
                self.assertIs(raised.exception, error)
