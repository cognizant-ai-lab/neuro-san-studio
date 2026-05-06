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
"""

from __future__ import annotations

import asyncio
import os

import pytest  # noqa: F401 — importorskip must run before local imports.

pytest.importorskip("mem0")
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

from middleware.persistent_memory.mem0_store import Mem0Store
from middleware.persistent_memory.topic_store_factory import TopicStoreFactory
from tests.middleware.persistent_memory.base import MemoryTestBase


class Mem0StoreTests(MemoryTestBase):
    """Mem0Store: user_id resolution, factory wiring, and CRUD lifecycle."""

    _NAMESPACE = "coffee_finder_advanced.UserPreferences"

    def _make_store(self, user_id: str = "test_user") -> Mem0Store:
        return Mem0Store(sly_data={"user_id": user_id})

    def _mock_client(self, memories: list[dict[str, Any]]) -> MagicMock:
        client = MagicMock()
        client.get_all.return_value = {"results": memories}
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
        os.environ.pop("MEM0_DEFAULT_USER_ID", None)
        store = TopicStoreFactory.create({"backend": "mem0"})
        self.assertEqual(store.user_id, "default_user")

    def test_read_topic_returns_content(self) -> None:
        """_read_topic returns the memory text for a matching topic."""
        memories = [
            {
                "id": "mem-1",
                "memory": "black coffee, no sugar",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
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

    def test_write_topic_calls_add_when_new(self) -> None:
        """_write_topic calls client.add when the topic does not yet exist."""
        store = self._make_store()
        client = self._mock_client([])
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._write_topic(self._NAMESPACE, "mike", "black coffee"))  # pylint: disable=protected-access
        client.add.assert_called_once()
        _, kwargs = client.add.call_args
        self.assertEqual(kwargs.get("user_id") or client.add.call_args[0][1], "test_user")

    def test_write_topic_calls_update_when_existing(self) -> None:
        """_write_topic calls client.update when the topic already exists."""
        memories = [
            {
                "id": "mem-1",
                "memory": "old content",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
            }
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            asyncio.run(store._write_topic(self._NAMESPACE, "mike", "new content"))  # pylint: disable=protected-access
        client.update.assert_called_once_with(
            memory_id="mem-1",
            text="new content",
            metadata={"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
        )

    def test_remove_topic_returns_true_when_found(self) -> None:
        """_remove_topic deletes the entry and returns True."""
        memories = [
            {
                "id": "mem-1",
                "memory": "black coffee",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
            }
        ]
        store = self._make_store()
        client = self._mock_client(memories)
        with patch.object(store, "_client", return_value=client):
            result = asyncio.run(store._remove_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertTrue(result)
        client.delete.assert_called_once_with(memory_id="mem-1")

    def test_remove_topic_returns_false_when_absent(self) -> None:
        """_remove_topic returns False when the topic does not exist."""
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client([])):
            result = asyncio.run(store._remove_topic(self._NAMESPACE, "mike"))  # pylint: disable=protected-access
        self.assertFalse(result)

    def test_read_bucket_returns_all_topics(self) -> None:
        """_read_bucket returns all topics for the namespace as a dict."""
        memories = [
            {
                "id": "1",
                "memory": "black coffee",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
            },
            {
                "id": "2",
                "memory": "latte",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "alice"},
            },
        ]
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client(memories)):
            result = asyncio.run(store._read_bucket(self._NAMESPACE))  # pylint: disable=protected-access
        self.assertEqual(result, {"mike": "black coffee", "alice": "latte"})

    def test_fetch_filters_by_network_and_agent(self) -> None:
        """_fetch_for_namespace excludes entries from other networks/agents."""
        memories = [
            {
                "id": "1",
                "memory": "keep",
                "metadata": {"network": "coffee_finder_advanced", "agent": "UserPreferences", "topic": "mike"},
            },
            {
                "id": "2",
                "memory": "skip",
                "metadata": {"network": "other_network", "agent": "UserPreferences", "topic": "alice"},
            },
            {
                "id": "3",
                "memory": "skip",
                "metadata": {"network": "coffee_finder_advanced", "agent": "OtherAgent", "topic": "bob"},
            },
        ]
        store = self._make_store()
        with patch.object(store, "_client", return_value=self._mock_client(memories)):
            result = store._fetch_for_namespace(self._NAMESPACE)  # pylint: disable=protected-access
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")
