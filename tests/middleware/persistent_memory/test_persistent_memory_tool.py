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

"""Dispatch + per-call disk I/O tests for ``PersistentMemoryTool``."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from middleware.persistent_memory.json_file_store import JsonFileStore
from tests.middleware.persistent_memory.base import MemoryTestBase


class PersistentMemoryToolDispatchTests(MemoryTestBase):
    """The six operations persist to disk on every call."""

    def setUp(self) -> None:
        super().setUp()
        self.store: JsonFileStore = JsonFileStore(folder_name=self._tmp)
        self.tool = self.make_tool(store=self.store)

    def _invoke(self, args: dict) -> dict:
        """Run one call synchronously against ``self.tool``."""
        return asyncio.run(self.tool.async_invoke(args))

    def _bucket(self) -> dict[str, str]:
        """Return the on-disk topic bucket (or empty dict)."""
        return asyncio.run(self.store.load_all("test_net.test_agent"))

    def test_create_writes_to_disk_immediately(self) -> None:
        """create persists the topic to disk before returning."""
        result = self._invoke({"operation": "create", "topic": "coffee", "content": "black"})
        self.assertEqual(result.get("result", {}).get("status"), "created")
        self.assertEqual(self._bucket(), {"coffee": "black"})

    def test_read_returns_stored_content(self) -> None:
        """read returns the string previously stored under ``topic``."""
        self._invoke({"operation": "create", "topic": "coffee", "content": "black"})
        result = self._invoke({"operation": "read", "topic": "coffee"})
        self.assertEqual(result.get("result", {}).get("content"), "black")

    def test_append_timestamps_and_concatenates(self) -> None:
        """append adds a timestamped line onto the existing content."""
        self._invoke({"operation": "create", "topic": "orders", "content": "matcha"})
        self._invoke({"operation": "append", "topic": "orders", "content": "latte"})
        content: str = self._bucket().get("orders", "")
        self.assertTrue(content.startswith("matcha"))
        self.assertIn("latte", content)
        self.assertIn("[", content)  # timestamp marker present

    def test_delete_removes_topic(self) -> None:
        """delete drops the topic from disk."""
        self._invoke({"operation": "create", "topic": "x", "content": "v"})
        self._invoke({"operation": "delete", "topic": "x"})
        self.assertNotIn("x", self._bucket())

    def test_search_returns_ranked_results(self) -> None:
        """search ranks by how many query terms appear in the content."""
        self._invoke({"operation": "create", "topic": "t1", "content": "loves coffee"})
        self._invoke({"operation": "create", "topic": "t2", "content": "loves tea"})
        result = self._invoke({"operation": "search", "query": "coffee"})
        topics = [entry.get("topic") for entry in result.get("result", {}).get("results", [])]
        self.assertEqual(topics, ["t1"])

    def test_list_returns_sorted_topics(self) -> None:
        """list returns the agent's topics sorted alphabetically."""
        self._invoke({"operation": "create", "topic": "b", "content": "v"})
        self._invoke({"operation": "create", "topic": "a", "content": "v"})
        result = self._invoke({"operation": "list"})
        self.assertEqual(result.get("result", {}).get("topics"), ["a", "b"])


class PersistentMemoryToolEnabledOperationsTests(MemoryTestBase):
    """The ``enabled_operations`` whitelist constrains the LLM."""

    def test_disabled_operation_returns_error(self) -> None:
        """Calling a disabled operation surfaces a ``not enabled`` error."""
        tool = self.make_tool(enabled_operations=["read", "search"])
        result = asyncio.run(tool.async_invoke({"operation": "create", "topic": "x", "content": "v"}))
        self.assertIn("error", result)
        self.assertIn("not enabled", result.get("error", "").lower())


class PersistentMemoryToolSummarizerTests(MemoryTestBase):
    """Summarizer fires from the tool after oversized writes."""

    def test_summarizer_fires_after_oversized_write(self) -> None:
        """A write past ``max_topic_size`` triggers the summarizer and rewrites disk."""
        store: JsonFileStore = JsonFileStore(folder_name=self._tmp)
        summarizer = AsyncMock()
        summarizer.summarize_topic = AsyncMock(return_value="SHORT")
        tool = self.make_tool(store=store, summarizer=summarizer, max_topic_size=10)
        asyncio.run(tool.async_invoke({"operation": "create", "topic": "t", "content": "x" * 50}))
        summarizer.summarize_topic.assert_awaited_once()
        memory: dict = asyncio.run(store.load_all("test_net.test_agent"))
        self.assertEqual(memory.get("t"), "SHORT")

    def test_summarizer_failure_keeps_original_write(self) -> None:
        """If the summarizer raises, the original write still survives on disk."""
        store: JsonFileStore = JsonFileStore(folder_name=self._tmp)
        summarizer = AsyncMock()
        summarizer.summarize_topic = AsyncMock(side_effect=RuntimeError("boom"))
        tool = self.make_tool(store=store, summarizer=summarizer, max_topic_size=10)
        original: str = "z" * 100
        asyncio.run(tool.async_invoke({"operation": "create", "topic": "t", "content": original}))
        summarizer.summarize_topic.assert_awaited_once()
        memory: dict = asyncio.run(store.load_all("test_net.test_agent"))
        self.assertEqual(memory.get("t"), original)
