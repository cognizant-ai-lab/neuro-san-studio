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
``user_id`` is resolved at call time from the ``DEFAULT_SLY_DATA``
environment variable (key ``"user_id"``), falling back to ``"default_user"``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import OrderedDict
from logging import Logger
from typing import Any
from typing import ClassVar
from typing import override

from mem0 import MemoryClient

from middleware.persistent_memory.topic_store import TopicStore


class Mem0Store(TopicStore):
    """
    One Mem0 memory entry per topic, scoped by network, agent, and user.

    The filesystem root used by the file-backed stores is not applicable here;
    ``__init__`` initialises only the lock infrastructure shared with the base
    class without calling ``super().__init__()``.
    """

    _DEFAULT_USER_ID: ClassVar[str] = "default_user"

    def __init__(self, sly_data: dict[str, Any] | None = None) -> None:  # pylint: disable=super-init-not-called
        # Bypass TopicStore.__init__ — no filesystem root is needed for a
        # cloud backend. Initialise only the attributes the base class methods
        # rely on: logger, lock cache, and lock-cache guard.
        self.logger: Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._locks: OrderedDict[tuple[str, ...], asyncio.Lock] = OrderedDict()
        self._locks_guard: asyncio.Lock = asyncio.Lock()
        self._sly_data: dict[str, Any] | None = sly_data
        self.logger.info("Initialised Mem0 cloud store backend.")

    # ------------------------------------------------------------------
    # Lock-key strategy — per-topic (each entry is independent in Mem0)
    # ------------------------------------------------------------------

    @override
    def _lock_key(self, namespace: str, topic: str) -> tuple[str, ...]:
        """
        Per-topic lock — each Mem0 entry is independent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The lock-cache key for this topic.
        """
        return ("mem0", namespace, topic)

    @override
    def _list_lock_key(self, namespace: str) -> tuple[str, ...]:
        """
        Per-namespace lock for list and search operations.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The lock-cache key for list/search ops.
        """
        return ("mem0-list", namespace)

    # ------------------------------------------------------------------
    # Admin / bulk operations
    # ------------------------------------------------------------------

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
        network, agent = self._split_namespace(namespace)
        client = self._client()
        user_id = self._user_id()

        async with await self._lock_for(self._list_lock_key(namespace)):
            existing = self._fetch_for_namespace(client, user_id, network, agent)
            existing_by_topic: dict[str, str] = {
                m["metadata"]["topic"]: m["id"] for m in existing if m.get("metadata", {}).get("topic")
            }

            # Remove topics that are no longer in the provided memory dict.
            for topic, memory_id in existing_by_topic.items():
                if topic not in memory:
                    client.delete(memory_id=memory_id)
                    self.logger.debug("save_all: deleted orphan topic '%s'", topic)

            # Upsert every topic in the provided memory dict.
            for topic, content in memory.items():
                existing_id: str | None = existing_by_topic.get(topic)
                self._upsert(client, user_id, network, agent, topic, content, existing_id)

    # ------------------------------------------------------------------
    # Core read / write / delete
    # ------------------------------------------------------------------

    @override
    async def _read_topic(self, namespace: str, topic: str) -> str | None:
        """
        Return one topic's content, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's content, or ``None`` if no entry exists.
        """
        network, agent = self._split_namespace(namespace)
        client = self._client()
        user_id = self._user_id()
        memories = self._fetch_for_namespace(client, user_id, network, agent)
        for m in memories:
            if m.get("metadata", {}).get("topic") == topic:
                content: str | None = m.get("memory") or None
                return content
        return None

    @override
    async def _write_topic(self, namespace: str, topic: str, content: str) -> None:
        """
        Create or overwrite one topic in Mem0.

        Existing entries are updated in place; absent entries are added.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param content:   New content for the topic.
        """
        network, agent = self._split_namespace(namespace)
        client = self._client()
        user_id = self._user_id()
        existing_id: str | None = self._find_topic_id(client, user_id, network, agent, topic)
        self._upsert(client, user_id, network, agent, topic, content, existing_id)

    @override
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Delete one topic entry from Mem0.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if an entry existed and was deleted.
        """
        network, agent = self._split_namespace(namespace)
        client = self._client()
        user_id = self._user_id()
        existing_id: str | None = self._find_topic_id(client, user_id, network, agent, topic)
        if existing_id is None:
            return False
        client.delete(memory_id=existing_id)
        return True

    @override
    async def _read_bucket(self, namespace: str) -> dict[str, str]:
        """
        Return the agent's ``{topic: content}`` dict from Mem0.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full memory dict; empty if none yet.
        """
        network, agent = self._split_namespace(namespace)
        client = self._client()
        user_id = self._user_id()
        memories = self._fetch_for_namespace(client, user_id, network, agent)
        return {m["metadata"]["topic"]: m.get("memory", "") for m in memories if m.get("metadata", {}).get("topic")}

    # ------------------------------------------------------------------
    # Mem0 cloud helpers
    # ------------------------------------------------------------------

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def _upsert(
        self,
        client: MemoryClient,
        user_id: str,
        network: str,
        agent: str,
        topic: str,
        content: str,
        existing_id: str | None,
    ) -> None:
        """
        Update an existing Mem0 entry or add a new one.

        :param client:      Authenticated ``MemoryClient``.
        :param user_id:     Mem0 user scope.
        :param network:     Agent network name, stored in metadata.
        :param agent:       Agent name, stored in metadata.
        :param topic:       Topic name, stored in metadata.
        :param content:     Memory text to persist.
        :param existing_id: Memory ID to update, or ``None`` to add.
        """
        metadata: dict[str, str] = self._build_metadata(network, agent, topic)
        if existing_id is not None:
            client.update(memory_id=existing_id, text=content, metadata=metadata)
            self.logger.debug("Updated memory %s (topic=%s)", existing_id, topic)
        else:
            client.add(messages=content, user_id=user_id, metadata=metadata)
            self.logger.debug("Added new memory for topic=%s", topic)

    def _fetch_for_namespace(
        self,
        client: MemoryClient,
        user_id: str,
        network: str,
        agent: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch all Mem0 memories that belong to this network and agent.

        Retrieves all memories for ``user_id`` and filters in Python because
        the Mem0 API does not support metadata predicates in ``get_all``.

        :param client:  Authenticated ``MemoryClient``.
        :param user_id: Mem0 user scope.
        :param network: Agent network name to filter on.
        :param agent:   Agent name to filter on.
        :return: Filtered list of Mem0 memory dicts.
        """
        all_results: list[dict[str, Any]] = client.get_all(filters={"user_id": user_id}).get("results", [])
        return [
            m
            for m in all_results
            if m.get("metadata", {}).get("network") == network and m.get("metadata", {}).get("agent") == agent
        ]

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def _find_topic_id(
        self,
        client: MemoryClient,
        user_id: str,
        network: str,
        agent: str,
        topic: str,
    ) -> str | None:
        """
        Return the Mem0 memory ID for ``topic``, or ``None`` if absent.

        :param client:  Authenticated ``MemoryClient``.
        :param user_id: Mem0 user scope.
        :param network: Agent network name.
        :param agent:   Agent name.
        :param topic:   Topic name to locate.
        :return: The memory ID string, or ``None``.
        """
        memories = self._fetch_for_namespace(client, user_id, network, agent)
        for m in memories:
            if m.get("metadata", {}).get("topic") == topic:
                return m.get("id")
        return None

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
                return json.loads(raw).get("user_id") or self._DEFAULT_USER_ID
            except (json.JSONDecodeError, AttributeError):
                pass
        return self._DEFAULT_USER_ID

    def _client(self) -> MemoryClient:
        """
        Build an authenticated ``MemoryClient`` from the ``MEM0_API_KEY`` environment variable.

        :raises EnvironmentError: If ``MEM0_API_KEY`` is not set.
        :return: A ready-to-use ``MemoryClient``.
        """
        api_key: str | None = os.environ.get("MEM0_API_KEY")
        if not api_key:
            raise EnvironmentError("MEM0_API_KEY environment variable is not set.")
        return MemoryClient(api_key=api_key)

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
