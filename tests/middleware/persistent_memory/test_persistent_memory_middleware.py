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
from unittest.mock import AsyncMock

from middleware.persistent_memory.persistent_memory_middleware import PersistentMemoryMiddleware
from tests.middleware.persistent_memory.base import MemoryTestBase


class PersistentMemoryMiddlewareRegistrationTests(MemoryTestBase):
    """Middleware registers exactly one tool, named ``persistent_memory``."""

    def test_registers_single_named_tool(self) -> None:
        """One dispatcher tool is exposed with the right name and tag."""
        mw = self.make_middleware()
        self.assertEqual(len(mw.tools), 1)
        self.assertEqual(mw.tools[0].name, PersistentMemoryMiddleware.MEMORY_TOOL_NAME)
        self.assertIn("langchain_tool", mw.tools[0].tags or [])


class PersistentMemoryMiddlewareOriginParsingTests(MemoryTestBase):
    """``origin_str`` is parsed into ``(network, agent)`` with index suffixes stripped."""

    def test_parses_network_and_agent_stripping_index_suffix(self) -> None:
        """Numeric ``-N`` suffixes are stripped from both segments."""
        network, agent = PersistentMemoryMiddleware._parse_origin_str(  # pylint: disable=protected-access
            "persistent_memory.MemoryAssistant-1.dispatch"
        )
        self.assertEqual(network, "persistent_memory")
        self.assertEqual(agent, "MemoryAssistant")


class PersistentMemoryMiddlewareDispatchTests(MemoryTestBase):
    """Dispatch forwards to ``PersistentMemoryTool`` and the result hits disk."""

    def test_end_to_end_create_then_search(self) -> None:
        """A create via the dispatcher is searchable via the same dispatcher."""
        mw = self.make_middleware()
        tool_fn = mw.tools[0]
        create_result = asyncio.run(
            tool_fn.coroutine(operation="create", topic="coffee", content="black")  # pylint: disable=not-callable
        )
        self.assertEqual(create_result.get("result", {}).get("status"), "created")
        search_result = asyncio.run(
            tool_fn.coroutine(operation="search", query="black")  # pylint: disable=not-callable
        )
        topics = [r.get("topic") for r in search_result.get("result", {}).get("results", [])]
        self.assertIn("coffee", topics)


class PersistentMemoryMiddlewareSummarizerTests(MemoryTestBase):
    """Summarizer fires from the tool after oversized writes."""

    def test_summarizes_when_topic_exceeds_max_size(self) -> None:
        """A topic larger than ``max_topic_size`` is replaced with its summary."""
        mw = self.make_middleware(max_topic_size=20)
        # pylint: disable=protected-access
        mw._summarizer.summarize_topic = AsyncMock(return_value="SHORT")  # type: ignore[attr-defined]

        asyncio.run(
            mw.tools[0].coroutine(operation="create", topic="t", content="x" * 50)  # pylint: disable=not-callable
        )

        mw._summarizer.summarize_topic.assert_awaited_once()  # type: ignore[attr-defined]
        disk: dict = json.loads((Path(self._tmp) / "test_net" / "test_agent" / "memory.json").read_text())
        self.assertEqual(disk.get("t"), "SHORT")
