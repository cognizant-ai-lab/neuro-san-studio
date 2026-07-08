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

"""Tests for the write-per-call ``PersistentMemoryMiddleware``."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from middleware.persistent_memory.persistent_memory_middleware import PersistentMemoryMiddleware
from tests.middleware.persistent_memory.base import MemoryTestBase


class PersistentMemoryMiddlewareTests(MemoryTestBase):
    """Tests for tool registration, origin parsing, dispatch, and summarization."""

    def test_registers_single_named_tool(self) -> None:
        """One dispatcher tool is exposed with the right name and tag."""
        mw = self.make_middleware()
        self.assertEqual(len(mw.tools), 1)
        self.assertEqual(mw.tools[0].name, PersistentMemoryMiddleware.MEMORY_TOOL_NAME)
        self.assertIn("langchain_tool", mw.tools[0].tags or [])

    def test_parses_network_and_agent_stripping_index_suffix(self) -> None:
        """Numeric ``-N`` suffixes are stripped from both segments."""
        network, agent = PersistentMemoryMiddleware._parse_origin_str(  # pylint: disable=protected-access
            "persistent_memory.MemoryAssistant-1.dispatch"
        )
        self.assertEqual(network, "persistent_memory")
        self.assertEqual(agent, "MemoryAssistant")

    def test_end_to_end_create_then_search(self) -> None:
        """A create via the dispatcher is searchable via the same dispatcher."""
        mw = self.make_middleware()
        tool_fn = mw.tools[0]
        create_result = asyncio.run(tool_fn.coroutine(operation="create", topic="coffee", content="black"))
        self.assertEqual(create_result.get("result", {}).get("status"), "created")
        search_result = asyncio.run(tool_fn.coroutine(operation="search", query="black"))
        topics = [r.get("topic") for r in search_result.get("result", {}).get("results", [])]
        self.assertIn("coffee", topics)

    def _make_middleware_with_preamble(self, preamble: Any) -> PersistentMemoryMiddleware:
        """Construct a middleware whose ``memory_config`` carries ``preamble``.

        :param preamble: Value to place under ``memory_config.preamble``.
        :return:         A ready-to-use middleware.
        """
        return PersistentMemoryMiddleware(
            origin_str="test_net.test_agent-1.dispatch",
            memory_config={
                "storage": {"backend": "json_file", "folder_name": self._tmp},
                "preamble": preamble,
            },
        )

    def _run_awrap(self, mw: PersistentMemoryMiddleware) -> str:
        """Run ``awrap_model_call`` with a stub request and return the resulting preamble.

        :param mw: The middleware under test.
        :return:   The trailing preamble applied to the system message.
        """
        captured: dict[str, Any] = {}

        class _StubRequest:
            """Minimal ``ModelRequest`` stand-in capturing the overridden system message."""

            system_message = None

            def override(self, system_message: Any) -> "_StubRequest":
                """Record the overridden system message and return self."""
                captured["system_message"] = system_message
                return self

        async def _handler(_request: Any) -> str:
            """Return a sentinel so the coroutine completes."""
            return "ok"

        asyncio.run(mw.awrap_model_call(_StubRequest(), _handler))  # type: ignore[arg-type]
        return captured["system_message"].content

    def test_preamble_override_used_in_system_message(self) -> None:
        """A non-blank ``preamble`` overrides the built-in default."""
        override = "ROUTING CACHE PREAMBLE"
        mw = self._make_middleware_with_preamble(override)
        applied = self._run_awrap(mw)
        self.assertEqual(applied, override)
        self.assertNotEqual(applied, mw.build_preamble())

    def test_blank_preamble_falls_back_to_default(self) -> None:
        """A blank/whitespace-only ``preamble`` falls back to ``build_preamble()``."""
        mw = self._make_middleware_with_preamble("   ")
        applied = self._run_awrap(mw)
        self.assertEqual(applied, mw.build_preamble())

    def test_non_string_preamble_falls_back_to_default(self) -> None:
        """A non-string ``preamble`` is ignored and does not crash init."""
        mw = self._make_middleware_with_preamble(123)
        applied = self._run_awrap(mw)
        self.assertEqual(applied, mw.build_preamble())

    def test_summarizes_when_topic_exceeds_max_size(self) -> None:
        """A topic larger than ``max_topic_size`` is replaced with its summary."""
        mw = self.make_middleware(max_topic_size=20)
        # pylint: disable=protected-access
        mw._summarizer.summarize_topic = AsyncMock(return_value="SHORT")  # type: ignore[attr-defined]

        asyncio.run(mw.tools[0].coroutine(operation="create", topic="t", content="x" * 50))

        mw._summarizer.summarize_topic.assert_awaited_once()  # type: ignore[attr-defined]
        disk: dict = json.loads((Path(self._tmp) / "test_net" / "test_agent" / "memory.json").read_text())
        self.assertEqual(disk.get("t"), "SHORT")
