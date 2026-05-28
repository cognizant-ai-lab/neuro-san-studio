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

Stores each topic as one Mem0 memory entry. Identity is encoded as
first-class Mem0 fields, with ``app_id`` and ``agent_id`` kept as
separate dimensions so server-side filters can scope by either:

* ``user_id``  — resolved per call (see :py:meth:`Mem0Store._user_id`).
* ``app_id``   — the agent network name (the "application").
* ``agent_id`` — the agent name within that network.
* ``metadata.topic`` — the topic name; held as metadata because the
  cloud API does not expose a first-class topic-level identifier.

The Mem0 SDK is asymmetric about how identity is passed: ``add()`` takes
``user_id``/``agent_id``/``app_id`` at the **top level**, while
``search`` / ``delete_all`` reject those at the top level and require
them inside ``filters`` (using the v2 ``{"AND": [...]}`` compound form).
Mixing the two patterns yields a 400 from ``/v3/memories/add/``.

Mem0's default ``infer=True`` runs an LLM over the input and may rewrite,
split, or dedupe the stored text. For a topic-keyed store we want the
exact text under each topic, so every ``add`` pins ``infer=False``.

**Read path: ``search`` with the semantic gate disabled.** On Mem0
cloud, ``infer=False`` writes land in the embedding/vector store but do
**not** appear in ``get_all`` results — that endpoint returns only
LLM-extracted "facts." ``search`` hits the vector path and surfaces
``infer=False`` entries. By design ``search`` applies the v2 compound
identity filter server-side **and then** a semantic-similarity cutoff
on top of the embedding match, returning only the top-N most relevant
hits. A topic-keyed store needs the opposite — every entry under a
namespace, not the semantically closest ones — so we pass
``threshold=0`` to disable the semantic gate, leaving only the identity
filter active, paired with a high ``top_k`` so the full set comes back.
This is a deliberate workaround: we are using ``search`` as a "list
all" against the vector path because ``get_all`` cannot see our
``infer=False`` writes.

Errors from the Mem0 client surface as :class:`mem0.exceptions.MemoryError`
subclasses (``AuthenticationError``, ``RateLimitError``,
``MemoryNotFoundError``, ``NetworkError`` …); we catch the base class so
callers see the Mem0-specific type with its ``error_code`` /
``suggestion`` attributes intact.
"""

from __future__ import annotations

import os
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import ClassVar
from typing import override

from mem0 import AsyncMemoryClient  # pylint: disable=import-error
from mem0.exceptions import ConfigurationError as Mem0ConfigurationError  # pylint: disable=import-error
from mem0.exceptions import MemoryError as Mem0Error  # pylint: disable=import-error

from middleware.persistent_memory.topic_store import TopicStore


class Mem0Store(TopicStore):
    """
    One Mem0 memory entry per topic, scoped by user_id and agent_id.

    Inherits the base class's logger and lock cache; no filesystem state
    is needed for this cloud backend.
    """

    _DEFAULT_USER_ID: ClassVar[str] = "default_user"

    # Mem0 cloud's documented server-side cap on the ``top_k`` parameter.
    # For a topic-keyed store this is well above any realistic count; if a
    # namespace ever approaches the cap we'd get a partial read, so
    # ``_fetch_for_namespace`` logs a warning.
    _SEARCH_TOP_K: ClassVar[int] = 1000

    def __init__(self, sly_data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._sly_data: dict[str, Any] | None = sly_data
        self._memory_client: AsyncMemoryClient | None = None
        self._warned_default_user: bool = False

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
    async def _read_topic(self, namespace: str, topic: str) -> str | None:
        """
        Return one topic's content, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's content, or ``None`` if no entry exists.
        """
        match: dict[str, Any] | None = await self._find_memory(namespace, topic)
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
        existing_id: str | None = await self._find_memory_id(namespace, topic)
        await self._upsert(namespace, topic, content, existing_id)

    @override
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Delete one topic entry from Mem0.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if an entry existed and was deleted.
        """
        existing_id: str | None = await self._find_memory_id(namespace, topic)
        if existing_id is None:
            return False
        try:
            await self._client().delete(memory_id=existing_id)
        except Mem0Error:
            self.logger.error(
                "Mem0 delete failed (namespace=%s, topic=%s, memory_id=%s)",
                namespace,
                topic,
                existing_id,
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
        memories: list[dict[str, Any]] = await self._fetch_for_namespace(namespace)
        return {
            m.get("metadata", {}).get("topic", ""): m.get("memory", "")
            for m in memories
            if m.get("metadata", {}).get("topic")
        }

    @override
    async def search_topics(
        self,
        namespace: str,
        query: str,
        limit: int = 5,
        post_read_factory: Callable[[str], Callable[[str], Awaitable[str | None]] | None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Vector-rank topics via Mem0's semantic search.

        Overrides the base-class keyword ranker: passes the LLM-supplied
        ``query`` straight to Mem0's vector path with the identity filter
        active and the semantic gate at its server default. Mem0 ranks
        by embedding similarity; we reshape hits into the standard
        ``{topic, content, score}`` envelope the tool layer expects.

        :param namespace:         ``"<network>.<agent>"`` key.
        :param query:             LLM-supplied search query.
        :param limit:             Max hits to return.
        :param post_read_factory: Optional factory returning a per-topic
                                  post-read callback, same semantics as the
                                  base class.
        :return: List of dicts with ``topic``, ``content``, and ``score`` keys.
        """
        async with await self._lock_for(self._list_lock_key(namespace)):
            client: AsyncMemoryClient = self._client()
            try:
                response: dict[str, Any] = await client.search(
                    query=query,
                    filters=self._identity_filters(namespace),
                    top_k=limit,
                )
            except Mem0Error:
                self.logger.error(
                    "Mem0 vector search failed (namespace=%s)",
                    namespace,
                    exc_info=True,
                )
                raise
            memories: list[dict[str, Any]] = response.get("results", [])
        results: list[dict[str, Any]] = [
            {
                "topic": m.get("metadata", {}).get("topic", ""),
                "content": m.get("memory", ""),
                "score": m.get("score", 0.0),
            }
            for m in memories
            if m.get("metadata", {}).get("topic")
        ]
        if post_read_factory is None:
            return results
        return await self._rewrite_search_results(namespace, results, post_read_factory)

    async def _upsert(
        self,
        namespace: str,
        topic: str,
        content: str,
        existing_id: str | None,
    ) -> None:
        """
        Update an existing Mem0 entry or add a new one.

        ``add`` pins ``infer=False`` to skip the LLM rewrite.

        :param namespace:   ``"<network>.<agent>"`` key.
        :param topic:       Topic name, stored in metadata.
        :param content:     Memory text to persist.
        :param existing_id: Memory ID to update, or ``None`` to add.
        """
        client: AsyncMemoryClient = self._client()
        metadata: dict[str, str] = {"topic": topic}
        try:
            if existing_id is not None:
                await client.update(memory_id=existing_id, text=content, metadata=metadata)
                self.logger.debug("Updated memory %s (topic=%s)", existing_id, topic)
            else:
                # ``add`` takes identity fields at the top level; ``get_all`` /
                # ``search`` / ``delete_all`` require them inside ``filters``.
                # Mixing the two yields a 400 from /v3/memories/add/.
                app_id, agent_id = self._split_namespace(namespace)
                await client.add(
                    messages=content,
                    user_id=self._user_id(),
                    app_id=app_id,
                    agent_id=agent_id,
                    metadata=metadata,
                    infer=False,
                )
                self.logger.debug("Added new memory for topic=%s", topic)
        except Mem0Error:
            self.logger.error(
                "Mem0 upsert failed (namespace=%s, topic=%s)",
                namespace,
                topic,
                exc_info=True,
            )
            raise

    async def _fetch_for_namespace(self, namespace: str) -> list[dict[str, Any]]:
        """
        Fetch all Mem0 memories for this user/app/agent via vector search.

        See the module docstring for why we use ``search`` (with the
        semantic gate disabled via ``threshold=0``) instead of
        ``get_all``: ``get_all`` cannot see ``infer=False`` writes, and
        ``search`` would normally apply the identity filter **and then**
        a semantic-similarity cutoff on top — we want every entry under
        the namespace, not the semantically closest hits, so the cutoff
        is disabled and ``top_k`` is set high.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: List of Mem0 memory dicts in this namespace.
        """
        client: AsyncMemoryClient = self._client()
        # Mem0 ``search`` requires a non-empty query string. The actual value is
        # irrelevant because ``threshold=0`` disables relevance gating — we just
        # need every memory matching the identity filter, ordered however the API
        # returns. "memory content" is an arbitrary placeholder that satisfies the
        # non-empty constraint.
        try:
            response: dict[str, Any] = await client.search(
                query="memory content",
                filters=self._identity_filters(namespace),
                top_k=self._SEARCH_TOP_K,
                threshold=0,
            )
        except Mem0Error:
            self.logger.error(
                "Mem0 search failed (namespace=%s)",
                namespace,
                exc_info=True,
            )
            raise
        results: list[dict[str, Any]] = response.get("results", [])
        if len(results) >= self._SEARCH_TOP_K:
            self.logger.warning(
                "Mem0 search returned %d results — at top_k cap; some entries may be missing.",
                len(results),
            )
        return results

    async def _find_memory(self, namespace: str, topic: str) -> dict[str, Any] | None:
        """
        Return the Mem0 memory dict for ``topic``, or ``None`` if absent.

        Issues a targeted ``search`` with ``metadata.topic`` added to the
        compound identity filter so the server returns only the matching
        entry — avoids pulling the entire namespace for single-topic
        lookups (the previous behavior). The post-fetch topic check is a
        safety net: if Mem0 ever silently ignores the metadata clause and
        hands back a different entry, we return ``None`` rather than
        treating a wrong topic as a hit.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name to locate.
        :return: The memory dict, or ``None`` if no entry matches.
        """
        client: AsyncMemoryClient = self._client()
        try:
            response: dict[str, Any] = await client.search(
                query="memory content",
                filters=self._identity_filters(namespace, topic=topic),
                top_k=1,
                threshold=0,
            )
        except Mem0Error:
            self.logger.error(
                "Mem0 lookup failed (namespace=%s, topic=%s)",
                namespace,
                topic,
                exc_info=True,
            )
            raise
        for memory in response.get("results", []):
            if memory.get("metadata", {}).get("topic") == topic:
                return memory
        return None

    async def _find_memory_id(self, namespace: str, topic: str) -> str | None:
        """
        Return the Mem0 memory ID for ``topic``, or ``None`` if absent.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name to locate.
        :return: The memory ID string, or ``None``.
        """
        match: dict[str, Any] | None = await self._find_memory(namespace, topic)
        return match.get("id") if match else None

    def _identity_filters(self, namespace: str, topic: str | None = None) -> dict[str, Any]:
        """
        Build the Mem0 v2 compound ``filters`` dict for read/delete ops.

        ``user_id``, ``app_id`` (network), and ``agent_id`` (agent name)
        are kept as separate clauses so each is a real Mem0 server-side
        filter dimension — the dashboard and ``delete_users(...)`` admin
        ops can target either independently. When ``topic`` is given, an
        additional ``metadata.topic`` clause is appended so single-topic
        lookups don't pull the whole namespace.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Optional topic name; when present, narrows the
                          filter to that single ``metadata.topic`` value.
        :return: ``filters`` dict suitable for Mem0 v3 list/search/delete.
        """
        app_id, agent_id = self._split_namespace(namespace)
        clauses: list[dict[str, Any]] = [
            {"user_id": self._user_id()},
            {"app_id": app_id},
            {"agent_id": agent_id},
        ]
        if topic is not None:
            clauses.append({"metadata": {"topic": topic}})
        return {"AND": clauses}

    @property
    def user_id(self) -> str:
        """Public read-only accessor for the resolved Mem0 user ID."""
        return self._user_id()

    def _user_id(self) -> str:
        """
        Resolve the Mem0 user ID from per-request ``sly_data``, falling back to
        the ``MEM0_DEFAULT_USER_ID`` environment variable and then ``"default_user"``.

        Per-request ``sly_data`` is preferred so each caller is isolated to their
        own Mem0 scope; the env-var fallback supports server-level defaults and
        local testing.

        :return: The active user ID string.
        """
        if self._sly_data:
            user_id: str | None = self._sly_data.get("user_id")
            if user_id:
                return user_id
        env_user_id: str = os.environ.get("MEM0_DEFAULT_USER_ID", "")
        if env_user_id:
            return env_user_id
        if not self._warned_default_user:
            self.logger.warning(
                "No user_id found in sly_data or MEM0_DEFAULT_USER_ID; "
                "falling back to '%s'. All users will share one memory scope.",
                self._DEFAULT_USER_ID,
            )
            self._warned_default_user = True
        return self._DEFAULT_USER_ID

    def _client(self) -> AsyncMemoryClient:
        """
        Return a cached authenticated ``AsyncMemoryClient``, building one on first use.

        The ``MEM0_API_KEY`` environment variable is read once on first call;
        subsequent calls reuse the same client (and its underlying HTTP
        session).

        :raises mem0.exceptions.ConfigurationError: If ``MEM0_API_KEY`` is
            not set on first call.
        :return: A ready-to-use ``AsyncMemoryClient``.
        """
        if self._memory_client is not None:
            return self._memory_client
        api_key: str | None = os.environ.get("MEM0_API_KEY")
        if not api_key:
            self.logger.error("MEM0_API_KEY environment variable is not set.")
            raise Mem0ConfigurationError(
                message="MEM0_API_KEY environment variable is not set.",
                error_code="CFG_001",
                suggestion="Export MEM0_API_KEY in the environment before starting the server.",
            )
        self._memory_client = AsyncMemoryClient(api_key=api_key)
        return self._memory_client
