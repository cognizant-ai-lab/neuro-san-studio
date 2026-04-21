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

``MemoryStore`` is a one-file-per-topic ABC that owns locking, atomic
writes, path handling, and the CRUD+search+list machinery. Subclasses pick
a serialisation format by implementing :py:meth:`_serialise` and
:py:meth:`_deserialise` and setting ``_EXTENSION``.

The backend factory lives next door in
:py:mod:`coded_tools.tools.persistent_memory.memory_store_factory`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC
from abc import abstractmethod
from collections import OrderedDict
from pathlib import Path
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Optional

import aiofiles

from coded_tools.tools.persistent_memory.memory_item import MemoryItem
from coded_tools.tools.persistent_memory.memory_item import Namespace
from coded_tools.tools.persistent_memory.path_component import PathComponent

logger = logging.getLogger(__name__)


class MemoryStore(ABC):
    """
    Abstract one-file-per-topic memory backend.

    Layout: ``<root>/<network>/<agent>/<topic>.<extension>``. Each file holds
    the whole of one topic's memory, serialised by the concrete subclass.

    Concurrency model: an ``asyncio.Lock`` per namespace file. Whole-file
    rewrites (atomic via temp file + ``os.replace``) keep the file consistent
    under crashes. Suitable for single-process neuro-san servers.

    Subclasses supply two hooks — :meth:`_serialise` / :meth:`_deserialise` —
    and set ``_EXTENSION``. All CRUD, locking, and atomic-write machinery is
    provided here.

    :param root_path: Directory under which all topic files live. Created on
                      first write if it does not exist.
    """

    #: File extension without the leading dot. Override in each subclass.
    _EXTENSION: str = ""

    #: Max number of per-namespace locks retained in memory. On overflow we
    #: evict the least-recently-used lock that is not currently held. Keeps
    #: long-running servers from accumulating one ``asyncio.Lock`` per distinct
    #: topic ever touched.
    _MAX_LOCKS: int = 1024

    def __init__(self, root_path: str) -> None:
        self._root: Path = Path(root_path).expanduser().resolve()
        # OrderedDict gives us O(1) LRU reorder via ``move_to_end`` on access,
        # so we can evict cold namespaces without scanning when the cache fills.
        self._locks: OrderedDict[Namespace, asyncio.Lock] = OrderedDict()
        # Guards ``self._locks`` itself — per-namespace locks are created
        # lazily and must not race when inserting into the dict.
        self._locks_guard: asyncio.Lock = asyncio.Lock()
        logger.info("%s initialised. Root path: %s", self.__class__.__name__, self._root)

    async def create(self, namespace: Namespace, key: str, value: dict[str, Any]) -> None:
        """Store a new entry under ``key`` in ``namespace``. Upsert semantics."""
        await self._upsert(namespace, key, value)

    async def update(self, namespace: Namespace, key: str, value: dict[str, Any]) -> None:
        """Overwrite an existing entry at ``key``. Upsert semantics at this layer."""
        # At the store layer, update is identical to create — an upsert. The
        # tool layer enforces "must exist" / "must not exist" semantics.
        await self._upsert(namespace, key, value)

    async def read(self, namespace: Namespace, key: str) -> Optional[MemoryItem]:
        """Return the entry at ``key`` or ``None`` if it does not exist."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
        value: Optional[dict[str, Any]] = entries.get(key)
        if value is None:
            return None
        return MemoryItem(key=key, value=dict(value))

    async def delete(self, namespace: Namespace, key: str) -> None:
        """Remove ``key`` from ``namespace``. No-op if the key is not present."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
            if key in entries:
                entries.pop(key)
                await self._write_file(namespace, entries)

    async def search(self, namespace: Namespace, query: str, limit: int = 5) -> list[MemoryItem]:
        """Keyword-rank the namespace's entries and return the top ``limit``."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
        if not entries:
            return []
        return self._keyword_rank(list(entries.items()), query, limit)

    async def list(self, namespace: Namespace) -> list[str]:
        """Return every key currently stored under ``namespace``, sorted."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
        return sorted(entries.keys())

    async def atomic_update_entry(
        self,
        namespace: Namespace,
        key: str,
        transform: Callable[[Optional[dict[str, Any]]], Awaitable[Optional[dict[str, Any]]]],
    ) -> Optional[dict[str, Any]]:
        """Read ``key``, apply an async ``transform``, write the result atomically.

        Holds the namespace lock across the whole read / transform / write
        cycle so no concurrent writer can interleave between the read and the
        write. Returns the value produced by ``transform`` so callers can tell
        whether a rewrite happened.

        ``transform`` receives the current value (or ``None`` if the key is
        absent). Returning ``None`` signals "no change" — the file is left
        untouched. Returning a dict replaces the entry with that dict.

        Typical use: compaction, where the middleware needs to rewrite a single
        entry with its summarised version under a single lock acquisition.

        :param namespace: Resolved namespace to update in.
        :param key:       Entry key to read / replace.
        :param transform: Async callable receiving the current value and
                          returning the new value (or ``None`` for no change).
        :return:          The new value that was written, or ``None`` if the
                          transform opted out of rewriting.
        """
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
            current: Optional[dict[str, Any]] = entries.get(key)
            # Copy so callers cannot accidentally mutate our in-memory state
            # before deciding what to return.
            new_value: Optional[dict[str, Any]] = await transform(dict(current) if current is not None else None)
            if new_value is None:
                return None
            entries[key] = dict(new_value)
            await self._write_file(namespace, entries)
            return new_value

    async def _upsert(self, namespace: Namespace, key: str, value: dict[str, Any]) -> None:
        """Shared implementation for :meth:`create` and :meth:`update`."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
            entries[key] = dict(value)
            await self._write_file(namespace, entries)

    async def close(self) -> None:
        """No-op: file-based backends open and close files per call."""
        return None

    @abstractmethod
    def _serialise(self, entries: dict[str, dict[str, Any]]) -> str:
        """Render ``{key: value_dict}`` as the backend's on-disk text format."""

    @abstractmethod
    def _deserialise(self, content: str) -> dict[str, dict[str, Any]]:
        """Parse on-disk text back into ``{key: value_dict}``."""

    async def _lock_for(self, namespace: Namespace) -> asyncio.Lock:
        """Return the asyncio lock guarding writes to ``namespace``, lazily creating it.

        Uses an LRU-bounded cache keyed by namespace. On a hit, the entry is
        moved to the most-recent end; on a miss, a fresh lock is created and,
        if the cache has grown past :attr:`_MAX_LOCKS`, the oldest *unlocked*
        entry is evicted. We never evict a held lock — doing so would break
        mutual exclusion for the holder.
        """
        async with self._locks_guard:
            lock: Optional[asyncio.Lock] = self._locks.get(namespace)
            if lock is not None:
                self._locks.move_to_end(namespace)
                return lock
            lock = asyncio.Lock()
            self._locks[namespace] = lock
            self._evict_locked_out()
        return lock

    def _evict_locked_out(self) -> None:
        """Trim the LRU cache back to ``_MAX_LOCKS`` entries.

        Called with ``_locks_guard`` held. Walks from the oldest end and drops
        the first entry whose lock is not currently held, stopping as soon as
        we are back within budget. If every retained lock is in use (extremely
        unlikely under normal load) we simply let the cache overshoot — mutual
        exclusion is worth more than a hard cap.
        """
        if len(self._locks) <= self._MAX_LOCKS:
            return
        # Snapshot keys in LRU order — we must not mutate the OrderedDict
        # while iterating it.
        for candidate in list(self._locks.keys()):
            if len(self._locks) <= self._MAX_LOCKS:
                return
            if not self._locks[candidate].locked():
                del self._locks[candidate]

    def _path_for(self, namespace: Namespace) -> Path:
        """
        Resolve ``<root>/<network>/<agent>/<topic>.<extension>``.

        The last namespace component (topic) is the filename so each topic's
        whole memory lives in a single readable file.
        """
        parts: list[str] = [PathComponent.sanitise(part) for part in namespace]
        return self._root.joinpath(*parts[:-1], f"{parts[-1]}.{self._EXTENSION}")

    @staticmethod
    def _keyword_rank(
        entries: list[tuple[str, dict[str, Any]]],
        query: str,
        limit: int,
    ) -> list[MemoryItem]:
        """Rank ``entries`` by how many query words appear in each entry's ``content``.

        Kept on the base class so concrete backends can override ranking
        (e.g. to plug in a vector or BM25 implementation) without forking
        the surrounding locking / IO machinery.

        :param entries: ``(key, value)`` pairs to score.
        :param query:   Free-text query. Empty query yields no results.
        :param limit:   Maximum number of results to return.
        :return:        ``MemoryItem`` list sorted by descending score.
        """
        query_words: set[str] = {word for word in query.lower().split() if word}
        if not query_words:
            return []

        scored: list[MemoryItem] = []
        for key, value in entries:
            content_text: str = str(value.get("content", "")).lower()
            hits: int = sum(1 for word in query_words if word in content_text)
            if hits == 0:
                continue
            score: float = hits / len(query_words)
            scored.append(MemoryItem(key=key, value=dict(value), score=round(score, 4)))

        scored.sort(key=lambda item: item.score or 0.0, reverse=True)
        return scored[:limit]

    async def _read_file(self, namespace: Namespace) -> dict[str, dict[str, Any]]:
        """Read and deserialise the topic's file. Missing/unreadable file → empty dict."""
        path: Path = self._path_for(namespace)
        if not path.exists():
            return {}
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
                content: str = await handle.read()
        except OSError as error:
            logger.error("%s: failed to read %s: %s", self.__class__.__name__, path, error)
            return {}
        return self._deserialise(content)

    async def _write_file(self, namespace: Namespace, entries: dict[str, dict[str, Any]]) -> None:
        """
        Atomically rewrite the topic's file.

        Writes to a sibling ``.tmp`` file first, then renames — so a crash
        mid-write leaves either the old content or the new content, never a
        partially-written file.
        """
        path: Path = self._path_for(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path = path.with_suffix(path.suffix + ".tmp")
        payload: str = self._serialise(entries)
        try:
            async with aiofiles.open(tmp_path, mode="w", encoding="utf-8") as handle:
                await handle.write(payload)
            os.replace(tmp_path, path)
        except OSError as error:
            logger.error("%s: failed to write %s: %s", self.__class__.__name__, path, error)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                # Best-effort cleanup — the original write already failed and
                # we're about to re-raise. Log at DEBUG so a missing tmp file
                # (e.g. already gone, permission quirk) is observable without
                # drowning production logs.
                except OSError as cleanup_error:
                    logger.debug(
                        "%s: could not remove tmp file %s after failed write: %s",
                        self.__class__.__name__,
                        tmp_path,
                        cleanup_error,
                    )
            raise
