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

"""Tests for ``Mem0Store`` — covers user_id resolution, factory wiring, and CRUD.

Live Mem0 API calls are mocked so the suite runs without ``MEM0_API_KEY``.
The store now talks to ``AsyncMemoryClient`` and pushes user_id/agent_id
filtering to the server, so tests assert on the filter payloads as well as
the CRUD outcomes.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

try:
    from middleware.persistent_memory.mem0_store import Mem0Store
    from middleware.persistent_memory.topic_store_factory import TopicStoreFactory
except ImportError:
    pytest.skip("mem0 not installed", allow_module_level=True)


class Mem0StoreTests(TestCase):
    """Mem0Store: user_id resolution, factory wiring, and CRUD lifecycle."""

    _NAMESPACE = "coffee_finder_advanced.UserPreferences"
    _APP_ID = "coffee_finder_advanced"
    _AGENT_ID = "UserPreferences"

    def _make_store(self, user_id: str = "test_user") -> Mem0Store:
        return Mem0Store(sly_data={"user_id": user_id})

    def _mock_client(self, memories: list[dict[str, Any]]) -> MagicMock:
        """Build an AsyncMemoryClient stand-in whose async methods return awaitables."""
        client = MagicMock()
        # ``Mem0Store`` reads via ``search`` (not ``get_all``) because Mem0
        # cloud's list path skips ``infer=False`` writes. Both are stubbed
        # so accidental regressions to ``get_all`` are visible.
        client.search = AsyncMock(return_value={"results": memories})
        client.get_all = AsyncMock(return_value={"results": memories, "next": None})
        client.add = AsyncMock(return_value={})
        client.update = AsyncMock(return_value={})
        client.delete = AsyncMock(return_value={})
        return client

    def test_sly_data_user_id_takes_priority(self) -> None:
        """sly_data["user_id"] is used when present."""
        store = Mem0Store(sly_data={"user_id": "alice"})
        self.assertEqual(store.user_id, "alice")

    def test_env_var_fallback(self) -> None:
        """Falls back to MEM0_DEFAULT_USER_ID env var when sly_data is absent."""
        with patch.dict(os.environ, {"MEM0_DEFAULT_USER_ID": "env_user"}):
            store = Mem0Store()
            self.assertEqual(store.user_id, "env_user")

    def test_default_user_fallback(self) -> None:
        """Returns 'default_user' when both sly_data and env var are absent."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DEFAULT_USER_ID", None)
            store = Mem0Store()
            self.assertEqual(store.user_id, "default_user")

    def test_sly_data_overrides_env_var(self) -> None:
        """sly_data takes priority over MEM0_DEFAULT_USER_ID env var."""
        with patch.dict(os.environ, {"MEM0_DEFAULT_USER_ID": "env_user"}):
            store = Mem0Store(sly_data={"user_id": "sly_user"})
            self.assertEqual(store.user_id, "sly_user")

    def test_empty_sly_data_falls_back(self) -> None:
        """Empty sly_data dict falls back to env var / default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DEFAULT_USER_ID", None)
            store = Mem0Store(sly_data={})
            self.assertEqual(store.user_id, "default_user")

    def test_factory_creates_mem0_store(self) -> None:
        """backend='mem0' yields a Mem0Store instance."""
        store = TopicStoreFactory.create({"backend": "mem0"})
        self.assertIsInstance(store, Mem0Store)

    def test_factory_forwards_sly_data(self) -> None:
        """sly_data passed to create() is stored on Mem0Store."""
        sly: dict[str, Any] = {"user_id": "bob"}
        store = TopicStoreFactory.create({"backend": "mem0"}, sly_data=sly)
        self.assertIsInstance(store, Mem0Store)
        self.assertEqual(store.user_id, "bob")

    def test_factory_sly_data_none_by_default(self) -> None:
        """No sly_data → falls back to default_user."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DEFAULT_USER_ID", None)
            store = TopicStoreFactory.create({"backend": "mem0"})
            self.assertEqual(store.user_id, "default_user")

    def test_read_topic_returns_content(self) -> None:
        """_read_topic returns the memory text for a matching topic."""
        memories = [
            {
                "id": "mem-1",
                "memory": "black coffee, no sugar",
                "metadata": {"topic": "mike"},
            }
        ]
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client(memories)):
            result = asyncio.run(store._read_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertEqual(result, "black coffee, no sugar")

    def test_read_topic_returns_none_when_absent(self) -> None:
        """_read_topic returns None when no entry matches the topic."""
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client([])):
            result = asyncio.run(store._read_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertIsNone(result)

    def test_find_memory_uses_metadata_topic_filter(self) -> None:
        """_find_memory issues a targeted ``search`` with metadata.topic in the AND filter."""
        memories = [
            {"id": "mem-1", "memory": "black coffee", "metadata": {"topic": "mike"}},
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._find_memory(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        client.search.assert_awaited_once()
        kwargs = client.search.await_args.kwargs
        self.assertEqual(
            kwargs.get("filters"),
            {
                "AND": [
                    {"user_id": "test_user"},
                    {"app_id": self._APP_ID},
                    {"agent_id": self._AGENT_ID},
                    {"metadata": {"topic": "mike"}},
                ],
            },
        )
        # Targeted lookup: top_k=1 is enough — server narrows to the one entry.
        self.assertEqual(kwargs.get("top_k"), 1)

    def test_find_memory_returns_none_on_topic_mismatch(self) -> None:
        """If Mem0 ever ignores the metadata filter, a wrong-topic hit is rejected."""
        # Server returned an entry for a different topic — defensive post-check.
        memories = [
            {"id": "mem-9", "memory": "something else", "metadata": {"topic": "alice"}},
        ]
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client(memories)):
            result = asyncio.run(store._find_memory(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertIsNone(result)

    def test_fetch_uses_search_with_compound_filter(self) -> None:
        """_fetch_for_namespace calls ``search`` with the v2 compound identity filter."""
        store = self._make_store()
        client = self._mock_client([])
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._fetch_for_namespace(self._NAMESPACE))  # pylint: disable=protected-access
        client.search.assert_awaited_once()
        client.get_all.assert_not_awaited()
        kwargs = client.search.await_args.kwargs
        self.assertEqual(
            kwargs.get("filters"),
            {
                "AND": [
                    {"user_id": "test_user"},
                    {"app_id": self._APP_ID},
                    {"agent_id": self._AGENT_ID},
                ],
            },
        )
        self.assertTrue(kwargs.get("query"), "search must receive a non-empty query")
        # ``threshold=0`` is required so the call returns the full filter-matched
        # set, not the semantic top-N. ``top_k`` must be high for the same reason.
        self.assertEqual(kwargs.get("threshold"), 0)
        self.assertGreaterEqual(kwargs.get("top_k", 0), 100)

    def test_search_topics_passes_real_query_to_mem0(self) -> None:
        """search_topics sends the LLM query to Mem0 with the semantic gate at its server default."""
        memories = [
            {
                "id": "mem-1",
                "memory": "drinks black coffee, no sugar",
                "metadata": {"topic": "mike"},
                "score": 0.87,
            },
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            results = asyncio.run(store.search_topics(self._NAMESPACE, "black coffee", limit=3))
        client.search.assert_awaited_once()
        kwargs = client.search.await_args.kwargs
        self.assertEqual(kwargs.get("query"), "black coffee")
        self.assertEqual(kwargs.get("top_k"), 3)
        self.assertEqual(
            kwargs.get("filters"),
            {
                "AND": [
                    {"user_id": "test_user"},
                    {"app_id": self._APP_ID},
                    {"agent_id": self._AGENT_ID},
                ],
            },
        )
        # Vector ranking path: ``threshold`` must NOT be pinned to 0 (that
        # would disable the semantic gate and turn this back into list-all).
        self.assertNotEqual(kwargs.get("threshold", None), 0)
        self.assertEqual(
            results,
            [{"topic": "mike", "content": "drinks black coffee, no sugar", "score": 0.87}],
        )

    def test_write_topic_calls_add_with_infer_false(self) -> None:
        """_write_topic.add pins infer=False and passes identity at the top level."""
        store = self._make_store()
        client = self._mock_client([])
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._write_topic(self._NAMESPACE, "mike", "black coffee"))  # pylint: disable=protected-access
        client.add.assert_awaited_once()
        kwargs = client.add.await_args.kwargs
        self.assertEqual(kwargs.get("messages"), "black coffee")
        self.assertIs(kwargs.get("infer"), False)
        self.assertEqual(kwargs.get("user_id"), "test_user")
        self.assertEqual(kwargs.get("app_id"), self._APP_ID)
        self.assertEqual(kwargs.get("agent_id"), self._AGENT_ID)
        # ``add`` takes identity at the top level — passing ``filters=`` here
        # would 400 against /v3/memories/add/.
        self.assertNotIn("filters", kwargs)
        self.assertEqual(kwargs.get("metadata"), {"topic": "mike"})

    def test_write_topic_calls_update_when_existing(self) -> None:
        """_write_topic calls client.update when the topic already exists."""
        memories = [
            {"id": "mem-1", "memory": "old content", "metadata": {"topic": "mike"}},
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._write_topic(self._NAMESPACE, "mike", "new content"))  # pylint: disable=protected-access
        client.update.assert_awaited_once_with(
            memory_id="mem-1",
            text="new content",
            metadata={"topic": "mike"},
        )
        client.add.assert_not_awaited()

    def test_remove_topic_returns_true_when_found(self) -> None:
        """_remove_topic deletes the entry and returns True."""
        memories = [
            {"id": "mem-1", "memory": "black coffee", "metadata": {"topic": "mike"}},
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            result = asyncio.run(store._remove_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertTrue(result)
        client.delete.assert_awaited_once_with(memory_id="mem-1")

    def test_remove_topic_returns_false_when_absent(self) -> None:
        """_remove_topic returns False when the topic does not exist."""
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client([])):
            result = asyncio.run(store._remove_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertFalse(result)

    def test_read_bucket_returns_all_topics(self) -> None:
        """_read_bucket returns all topics for the namespace as a dict."""
        memories = [
            {"id": "1", "memory": "black coffee", "metadata": {"topic": "mike"}},
            {"id": "2", "memory": "latte", "metadata": {"topic": "alice"}},
        ]
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client(memories)):
            result = asyncio.run(store._read_bucket(self._NAMESPACE))  # pylint: disable=protected-access
        self.assertEqual(result, {"mike": "black coffee", "alice": "latte"})
