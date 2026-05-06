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

"""
Mem0-cloud memory store backend.

Stores each topic as one memory entry in the Mem0 cloud, tagged with
``network``, ``agent``, and ``topic`` metadata for scoped reads and writes.
``user_id`` is resolved at call time in priority order:
1. ``sly_data["user_id"]`` — per-request value injected by the framework.
2. ``DEFAULT_SLY_DATA`` environment variable (JSON with a ``"user_id"`` key).
3. ``"default_user"`` — fallback when neither is available.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any
from typing import ClassVar
from typing import override

from mem0 import MemoryClient  # pylint: disable=import-error

from middleware.persistent_memory.topic_store import TopicStore


class Mem0Store(TopicStore):
    """
    One Mem0 memory entry per topic, scoped by network, agent, and user.

    Inherits the base class's logger and lock cache; no filesystem state
    is needed for this cloud backend.
    """

    _DEFAULT_USER_ID: ClassVar[str] = "default_user"

    def __init__(self, sly_data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._sly_data: dict[str, Any] | None = sly_data
        self._memory_client: MemoryClient | None = None
        self._client_lock: threading.Lock = threading.Lock()
        self.logger.info("Initialised Mem0 cloud store backend.")

    @override
    def _lock_key(self, namespace: str, topic: str) -> tuple[str, ...]:
        """
        Per-user, per-topic lock — each Mem0 entry is independent and
        Mem0 storage is partitioned by ``user_id``, so unrelated users
        on the same agent/topic must not block each other.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The lock-cache key for this topic.
        """
        return ("mem0", self._user_id(), namespace, topic)

    @override
    def _list_lock_key(self, namespace: str) -> tuple[str, ...]:
        """
        Per-user, per-namespace lock for list and search operations.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The lock-cache key for list/search ops.
        """
        return ("mem0-list", self._user_id(), namespace)

    @override
    async def load_all(self, namespace: str) -> TopicStore.AgentMemory:
        """
        Return every topic for this agent as a ``{topic: content}`` dict.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full ``{topic: content}`` dict.
        """
        return await self._read_bucket(namespace)

    @override
    async def save_all(self, namespace: str, memory: TopicStore.AgentMemory) -> None:
        """
        Persist the full memory dict, deleting topics absent from ``memory``.

        Held under the agent-level list lock so the orphan sweep cannot race
        with a concurrent ``set_topic``.

        :param namespace: ``"<network>.<agent>"`` key.
        :param memory:    Full ``{topic: content}`` dict to persist.
        """
        async with await self._lock_for(self._list_lock_key(namespace)):
            existing = await asyncio.to_thread(self._fetch_for_namespace, namespace)
            existing_by_topic: dict[str, str] = {
                m.get("metadata", {}).get("topic", ""): m.get("id", "")
                for m in existing
                if m.get("metadata", {}).get("topic") and m.get("id")
            }

            # Remove topics that are no longer in the provided memory dict.
            client: MemoryClient = self._client()
            for topic, memory_id in existing_by_topic.items():
                if topic not in memory:
                    await asyncio.to_thread(client.delete, memory_id=memory_id)
                    self.logger.debug("save_all: deleted orphan topic '%s'", topic)

            # Upsert every topic in the provided memory dict.
            for topic, content in memory.items():
                existing_id: str | None = existing_by_topic.get(topic)
                await asyncio.to_thread(self._upsert, namespace, topic, content, existing_id)

    @override
    async def _read_topic(self, namespace: str, topic: str) -> str | None:
        """
        Return one topic's content, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's content, or ``None`` if no entry exists.
        """
        match: dict[str, Any] | None = await asyncio.to_thread(self._find_memory, namespace, topic)
        if not match:
            return None
        return match.get("memory")

    @override
    async def _write_topic(self, namespace: str, topic: str, content: str) -> None:
        """
        Create or overwrite one topic in Mem0.

        Existing entries are updated in place; absent entries are added.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param content:   New content for the topic.
        """
        existing_id: str | None = await asyncio.to_thread(self._find_memory_id, namespace, topic)
        await asyncio.to_thread(self._upsert, namespace, topic, content, existing_id)

    @override
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Delete one topic entry from Mem0.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if an entry existed and was deleted.
        """
        existing_id: str | None = await asyncio.to_thread(self._find_memory_id, namespace, topic)
        if existing_id is None:
            return False
        try:
            await asyncio.to_thread(self._client().delete, memory_id=existing_id)
        except Exception:
            self.logger.error(
                "Mem0 API error deleting topic '%s' in namespace '%s'.",
                topic,
                namespace,
                exc_info=True,
            )
            raise
        return True

    @override
    async def _read_bucket(self, namespace: str) -> dict[str, str]:
        """
        Return the agent's ``{topic: content}`` dict from Mem0.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full memory dict; empty if none yet.
        """
        memories = await asyncio.to_thread(self._fetch_for_namespace, namespace)
        return {
            m.get("metadata", {}).get("topic", ""): m.get("memory", "")
            for m in memories
            if m.get("metadata", {}).get("topic")
        }

    def _upsert(
        self,
        namespace: str,
        topic: str,
        content: str,
        existing_id: str | None,
    ) -> None:
        """
        Update an existing Mem0 entry or add a new one.

        :param namespace:   ``"<network>.<agent>"`` key.
        :param topic:       Topic name, stored in metadata.
        :param content:     Memory text to persist.
        :param existing_id: Memory ID to update, or ``None`` to add.
        """
        network, agent = self._split_namespace(namespace)
        metadata: dict[str, str] = self._build_metadata(network, agent, topic)
        client: MemoryClient = self._client()
        try:
            if existing_id is not None:
                client.update(memory_id=existing_id, text=content, metadata=metadata)
                self.logger.debug("Updated memory %s (topic=%s)", existing_id, topic)
            else:
                client.add(messages=content, user_id=self._user_id(), metadata=metadata)
                self.logger.debug("Added new memory for topic=%s", topic)
        except Exception:
            self.logger.error(
                "Mem0 API error during upsert for topic '%s' in namespace '%s'.",
                topic,
                namespace,
                exc_info=True,
            )
            raise

    def _fetch_for_namespace(self, namespace: str) -> list[dict[str, Any]]:
        """
        Fetch all Mem0 memories that belong to this network and agent.

        Retrieves all memories for the active ``user_id`` and filters in
        Python because the Mem0 API does not support metadata predicates
        in ``get_all``.  This is acceptable for small memory sets (dozens
        to low hundreds) but will degrade at scale; a server-side filter
        or pagination strategy should be considered if sets grow large.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: Filtered list of Mem0 memory dicts.
        """
        network, agent = self._split_namespace(namespace)
        try:
            all_results: list[dict[str, Any]] = (
                self._client().get_all(filters={"user_id": self._user_id()}).get("results", [])
            )
        except Exception:
            self.logger.error(
                "Mem0 API error fetching memories for namespace '%s'.",
                namespace,
                exc_info=True,
            )
            raise
        return [
            m
            for m in all_results
            if m.get("metadata", {}).get("network") == network and m.get("metadata", {}).get("agent") == agent
        ]

    def _find_memory(self, namespace: str, topic: str) -> dict[str, Any] | None:
        """
        Return the Mem0 memory dict for ``topic``, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name to locate.
        :return: The memory dict, or ``None`` if no entry matches.
        """
        for memory in self._fetch_for_namespace(namespace):
            if memory.get("metadata", {}).get("topic") == topic:
                return memory
        return None

    def _find_memory_id(self, namespace: str, topic: str) -> str | None:
        """
        Return the Mem0 memory ID for ``topic``, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name to locate.
        :return: The memory ID string, or ``None``.
        """
        match: dict[str, Any] | None = self._find_memory(namespace, topic)
        return match.get("id") if match else None

    def _user_id(self) -> str:
        """
        Resolve the Mem0 user ID from per-request ``sly_data``, falling back to
        the ``DEFAULT_SLY_DATA`` environment variable and then ``"default_user"``.

        Per-request ``sly_data`` is preferred so each caller is isolated to their
        own Mem0 scope; the env-var fallback supports server-level defaults and
        local testing.

        :return: The active user ID string.
        """
        if self._sly_data:
            user_id: str | None = self._sly_data.get("user_id")
            if user_id:
                return user_id
        raw: str = os.environ.get("DEFAULT_SLY_DATA", "")
        if raw:
            try:
                env_user_id: str | None = json.loads(raw).get("user_id")
                if env_user_id:
                    return env_user_id
            except (json.JSONDecodeError, AttributeError):
                self.logger.warning(
                    "DEFAULT_SLY_DATA is not valid JSON; falling back to '%s'.",
                    self._DEFAULT_USER_ID,
                )
                return self._DEFAULT_USER_ID
        self.logger.warning(
            "No user_id found in sly_data or DEFAULT_SLY_DATA; "
            "falling back to '%s'. All users will share one memory scope.",
            self._DEFAULT_USER_ID,
        )
        return self._DEFAULT_USER_ID

    def _client(self) -> MemoryClient:
        """
        Return a cached authenticated ``MemoryClient``, building one on first use.

        The ``MEM0_API_KEY`` environment variable is read once on first call;
        subsequent calls reuse the same client (and its underlying HTTP
        session).

        :raises ValueError: If ``MEM0_API_KEY`` is not set on first call.
        :return: A ready-to-use ``MemoryClient``.
        """
        if self._memory_client is not None:
            return self._memory_client
        with self._client_lock:
            if self._memory_client is not None:
                return self._memory_client
            api_key: str | None = os.environ.get("MEM0_API_KEY")
            if not api_key:
                raise ValueError("MEM0_API_KEY environment variable is not set.")
            self._memory_client = MemoryClient(api_key=api_key)
            return self._memory_client

    @staticmethod
    def _build_metadata(network: str, agent: str, topic: str) -> dict[str, str]:
        """
        Build the Mem0 metadata dict for a write operation.

        :param network: Agent network name.
        :param agent:   Agent name.
        :param topic:   Topic name.
        :return: Metadata dict with ``network``, ``agent``, and ``topic`` keys.
        """
        return {"network": network, "agent": agent, "topic": topic}
