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
Abstract base class for persistent-memory store backends.

Every call reads and writes disk directly, guarded by a per-key lock.
Subclasses choose the on-disk layout and how fine-grained the locks are.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC
from abc import abstractmethod
from collections import OrderedDict
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Awaitable
from typing import Callable
from typing import ClassVar
from typing import Optional
from typing import TypedDict


class SearchResult(TypedDict):
    """One keyword-ranked hit returned by :py:meth:`TopicStore.search_topics`."""

    topic: str
    content: str
    score: float


class TopicStore(ABC):
    """
    Shared base for the file-backed stores. Holds the root directory and
    the per-key lock cache; subclasses implement the actual file layout.
    """

    # Per-agent memory is a flat dict: topic -> content.
    AgentMemory = dict[str, str]

    _MAX_LOCKS: ClassVar[int] = 256

    def __init__(self, root_path: str) -> None:
        self.logger: Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._root: Path = Path(root_path).expanduser().resolve()
        self._locks: OrderedDict[tuple[str, ...], asyncio.Lock] = OrderedDict()
        self._locks_guard: asyncio.Lock = asyncio.Lock()
        self.logger.info("Initialised. Root path: %s", self._root)

    async def get_topic(
        self,
        namespace: str,
        topic: str,
        post_read: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    ) -> Optional[str]:
        """
        Read one topic, or ``None`` if absent.

        If ``post_read`` is given, it runs under the same lock. When it
        returns new content, that new content is saved and returned instead.
        Errors are logged and the original is kept.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param post_read: Optional callback run under the lock with the loaded
                          content; a non-empty different return value is
                          written back and returned.
        :return: The topic's content (possibly rewritten), or ``None`` if absent.
        """
        async with await self._lock_for(self._lock_key(namespace, topic)):
            content: Optional[str] = await self._read_topic(namespace, topic)
            if content is None or post_read is None:
                return content
            replacement: Optional[str] = await self._run_post_access(namespace, topic, content, post_read)
            return replacement if replacement is not None else content

    async def list_topics(self, namespace: str) -> list[str]:
        """
        Return the agent's topic names, sorted.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: Sorted list of topic names.
        """
        async with await self._lock_for(self._list_lock_key(namespace)):
            bucket: dict[str, str] = await self._read_bucket(namespace)
            return sorted(bucket.keys())

    async def search_topics(
        self,
        namespace: str,
        query: str,
        limit: int = 5,
        post_read_factory: Optional[Callable[[str], Callable[[str], Awaitable[Optional[str]]]]] = None,
    ) -> list[SearchResult]:
        """
        Rank topics by keyword match against ``query``.

        ``post_read_factory``, if given, returns a per-topic callback that
        runs under the write lock — same rewrite rules as ``get_topic``.

        :param namespace:         ``"<network>.<agent>"`` key.
        :param query:             Free-text search string.
        :param limit:             Max number of hits to return.
        :param post_read_factory: Optional factory returning a per-topic
                                  post-read callback (same semantics as
                                  ``get_topic``'s ``post_read``).
        :return: List of ``SearchResult`` dicts, best first.
        """
        async with await self._lock_for(self._list_lock_key(namespace)):
            bucket: dict[str, str] = await self._read_bucket(namespace)
        results: list[SearchResult] = self._keyword_rank(bucket, query, limit)
        if post_read_factory is None:
            return results
        return await self._rewrite_search_results(namespace, results, post_read_factory)

    async def _rewrite_search_results(
        self,
        namespace: str,
        results: list[SearchResult],
        post_read_factory: Callable[[str], Callable[[str], Awaitable[Optional[str]]]],
    ) -> list[SearchResult]:
        """
        Run per-topic ``post_read`` callbacks under the write lock and rewrite hits in place.

        :param namespace:         ``"<network>.<agent>"`` key.
        :param results:           Search hits to (possibly) rewrite in place.
        :param post_read_factory: Factory returning a per-topic post-read callback.
        :return: The same ``results`` list, with ``content`` fields updated.
        """
        for entry in results:
            topic: str = str(entry.get("topic") or "")
            if not topic:
                continue
            post_read: Callable[[str], Awaitable[Optional[str]]] = post_read_factory(topic)
            if post_read is None:
                continue
            async with await self._lock_for(self._lock_key(namespace, topic)):
                current: Optional[str] = await self._read_topic(namespace, topic)
                if current is None:
                    continue
                replacement: Optional[str] = await self._run_post_access(namespace, topic, current, post_read)
                entry["content"] = replacement if replacement is not None else current
        return results

    async def set_topic(
        self,
        namespace: str,
        topic: str,
        content: str,
        post_write: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    ) -> None:
        """
        Create or overwrite a topic. ``post_write`` runs under the same lock.

        :param namespace:  ``"<network>.<agent>"`` key.
        :param topic:      Topic name.
        :param content:    New content for the topic.
        :param post_write: Optional callback run under the lock after writing;
                           a non-empty different return value is written back.
        """
        async with await self._lock_for(self._lock_key(namespace, topic)):
            await self._write_topic(namespace, topic, content)
            await self._run_post_write(namespace, topic, content, post_write)

    async def append_to_topic(
        self,
        namespace: str,
        topic: str,
        content: str,
        post_write: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
    ) -> str:
        """
        Append a timestamped line to the topic and return the new full content.

        Creates the topic if missing. ``post_write`` runs under the same lock.

        :param namespace:  ``"<network>.<agent>"`` key.
        :param topic:      Topic name.
        :param content:    Line to append (will be timestamped).
        :param post_write: Optional callback run under the lock after writing;
                           a non-empty different return value is written back.
        :return: The full post-append content (possibly rewritten).
        """
        stamp: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line: str = f"[{stamp}] {content}"
        async with await self._lock_for(self._lock_key(namespace, topic)):
            existing: Optional[str] = await self._read_topic(namespace, topic)
            new_content: str = f"{existing}\n{line}" if existing else line
            await self._write_topic(namespace, topic, new_content)
            replacement: Optional[str] = await self._run_post_write(namespace, topic, new_content, post_write)
            return replacement if replacement is not None else new_content

    async def _run_post_write(
        self,
        namespace: str,
        topic: str,
        written_content: str,
        post_write: Optional[Callable[[str], Awaitable[Optional[str]]]],
    ) -> Optional[str]:
        """
        Write-path shim over :py:meth:`_run_post_access`.

        :param namespace:       ``"<network>.<agent>"`` key.
        :param topic:           Topic name.
        :param written_content: Content just written to disk.
        :param post_write:      Optional callback to run; ``None`` no-ops.
        :return: Replacement content if the callback rewrote it, else ``None``.
        """
        if post_write is None:
            return None
        return await self._run_post_access(namespace, topic, written_content, post_write)

    async def _run_post_access(
        self,
        namespace: str,
        topic: str,
        observed_content: str,
        callback: Callable[[str], Awaitable[Optional[str]]],
    ) -> Optional[str]:
        """
        Run ``callback`` under the caller's lock; rewrite if it returns a non-empty different string.

        Exceptions are logged and swallowed.

        :param namespace:        ``"<network>.<agent>"`` key.
        :param topic:            Topic name.
        :param observed_content: Content currently on disk, passed to the callback.
        :param callback:         Async callback; may return a replacement string or ``None``.
        :return: The replacement content if rewritten, else ``None``.
        """
        try:
            replacement: Optional[str] = await callback(observed_content)
        # Callback is best-effort — any error (network, summarizer SDK, etc.)
        # must not lose the content that is already on disk.
        except Exception:  # pylint: disable=broad-except
            self.logger.warning(
                "Post-access callback failed for topic '%s'. Keeping original content.",
                topic,
                exc_info=True,
            )
            return None
        if not replacement or replacement == observed_content:
            return None
        await self._write_topic(namespace, topic, replacement)
        return replacement

    async def delete_topic(self, namespace: str, topic: str) -> bool:
        """
        Delete ``topic``; return ``True`` if something was removed.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if the topic existed and was deleted.
        """
        async with await self._lock_for(self._lock_key(namespace, topic)):
            return await self._remove_topic(namespace, topic)

    @abstractmethod
    async def load_all(self, namespace: str) -> AgentMemory:
        """
        Load every topic for the agent. Admin/debug only.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full ``{topic: content}`` dict.
        """

    @abstractmethod
    async def save_all(self, namespace: str, memory: AgentMemory) -> None:
        """
        Persist the full agent memory. Admin/debug only.

        :param namespace: ``"<network>.<agent>"`` key.
        :param memory:    Full ``{topic: content}`` dict to persist.
        """

    @abstractmethod
    async def _read_topic(self, namespace: str, topic: str) -> Optional[str]:
        """
        Read one topic from disk.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's content, or ``None`` if absent.
        """

    @abstractmethod
    async def _write_topic(self, namespace: str, topic: str, content: str) -> None:
        """
        Atomically persist one topic.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param content:   New content.
        """

    @abstractmethod
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Remove one topic from disk; return ``True`` if deleted.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if a topic was actually removed.
        """

    @abstractmethod
    async def _read_bucket(self, namespace: str) -> dict[str, str]:
        """
        Return the full ``{topic: content}`` dict for this agent.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full memory dict.
        """

    @abstractmethod
    def _lock_key(self, namespace: str, topic: str) -> tuple[str, ...]:
        """
        Lock-cache key for single-topic ops.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: Key identifying the lock for this topic.
        """

    @abstractmethod
    def _list_lock_key(self, namespace: str) -> tuple[str, ...]:
        """
        Lock-cache key for list/search ops.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: Key identifying the lock for agent-wide reads.
        """

    @staticmethod
    def _split_namespace(namespace: str) -> tuple[str, str]:
        """
        Split ``"<network>.<agent>"``; missing halves fall back to ``"unknown"``.

        The middleware sanitises both halves before building this key, so
        the store trusts the input to be filesystem-safe.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: ``(network, agent)`` tuple.
        """
        if not namespace:
            return ("unknown", "unknown")
        network, _, agent = namespace.partition(".")
        return (network or "unknown", agent or "unknown")

    async def _lock_for(self, key: tuple[str, ...]) -> asyncio.Lock:
        """
        Return (creating if needed) the ``asyncio.Lock`` for ``key``, LRU-capped at ``_MAX_LOCKS``.

        :param key: Lock-cache key from ``_lock_key`` / ``_list_lock_key``.
        :return: The ``asyncio.Lock`` for this key.
        """
        async with self._locks_guard:
            lock: Optional[asyncio.Lock] = self._locks.get(key)
            if lock is not None:
                self._locks.move_to_end(key)
                return lock
            lock = asyncio.Lock()
            self._locks[key] = lock
            self._evict_cold_locks()
            return lock

    def _evict_cold_locks(self) -> None:
        """
        Trim the LRU cache to ``_MAX_LOCKS``. Only evicts unheld locks; must hold ``_locks_guard``.
        """
        if len(self._locks) <= self._MAX_LOCKS:
            return
        for candidate in list(self._locks.keys()):
            if len(self._locks) <= self._MAX_LOCKS:
                return
            if not self._locks[candidate].locked():
                del self._locks[candidate]

    @staticmethod
    def _keyword_rank(
        bucket: dict[str, str],
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        """
        Score topics by query-word hits / query-word count; return top ``limit``, sorted desc.

        :param bucket: ``{topic: content}`` dict to rank.
        :param query:  Free-text query; split on whitespace, lowercased.
        :param limit:  Max number of hits to return.
        :return: List of ``SearchResult`` dicts, best first.
        """
        words: set[str] = {word for word in query.lower().split() if word}
        if not words:
            return []
        scored: list[tuple[float, str, str]] = []
        for topic, content in bucket.items():
            haystack: str = content.lower()
            hits: int = sum(1 for word in words if word in haystack)
            if hits == 0:
                continue
            score: float = round(hits / len(words), 4)
            scored.append((score, topic, content))
        scored.sort(key=lambda triple: triple[0], reverse=True)
        return [SearchResult(topic=topic, content=content, score=score) for score, topic, content in scored[:limit]]
