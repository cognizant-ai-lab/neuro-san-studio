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
Abstract base class and shared types for persistent-memory store backends.

``BaseMemoryStore`` is a one-file-per-topic ABC that owns locking, atomic
writes, path handling, and the CRUD+search+list machinery. Subclasses pick
a serialisation format by implementing :py:meth:`_serialise` and
:py:meth:`_deserialise` and setting ``_EXTENSION``.

The backend factory lives next door in
:py:mod:`coded_tools.tools.persistent_memory.memory_store_factory`.
"""

import asyncio
import json
import logging
import os
import re
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import fields
from pathlib import Path
from typing import Any
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


# Namespace is always a 3-tuple: (agent_network_name, agent_name, topic).
# Kept as a plain tuple rather than a dataclass so it is hashable and cheap to
# pass around. Backends destructure it themselves.
Namespace = tuple[str, str, str]


@dataclass
class MemoryItem:
    """
    Normalised item returned by every store backend.

    :param key:   The entry's key within its namespace.
    :param value: The stored payload. Shape is controlled by the tool layer, not
                  the store — currently ``{"content": "..."}``.
    :param score: Optional similarity / relevance score returned by ``search``.
                  ``None`` for lookups that do not produce a score.
    """

    key: str
    value: dict[str, Any]
    score: Optional[float] = None


@dataclass
class MemoryStoreConfig:
    """
    Configuration for a memory store backend.

    :param backend:   Backend identifier. See ``VALID_BACKENDS`` in the factory.
    :param root_path: Root directory for file-based backends.
    """

    backend: str = "file_system"
    root_path: str = "./memory"

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "MemoryStoreConfig":
        """
        Build a ``MemoryStoreConfig`` from a plain dict, ignoring unknown keys.

        :param data: A dict read from HOCON ``tool_config`` or from a JSON env var.
                     ``None`` and ``{}`` both yield a default config.
        :return:     A populated ``MemoryStoreConfig``.
        """
        if not data:
            return cls()

        known_fields: set[str] = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in known_fields}
        return cls(**kwargs)

    @classmethod
    def resolve(cls, hocon_dict: Optional[dict[str, Any]]) -> "MemoryStoreConfig":
        """
        Resolve the final config by layering env overrides on top of HOCON.

        Precedence (later wins):
            1. ``hocon_dict`` — the ``store_config`` block read from HOCON.
            2. ``MEMORY_STORE_CONFIG`` — a JSON object env var, shallow-merged
               over the HOCON dict. Useful for swapping whole backends at
               deploy time without editing HOCON.
            3. Individual ``MEMORY_*`` env vars — field-level overrides. The
               most surgical layer; a single var can point the tool at a new
               Postgres URL or S3 bucket while everything else stays HOCON.
        """
        merged: dict[str, Any] = dict(hocon_dict or {})

        env_json: Optional[str] = os.environ.get("MEMORY_STORE_CONFIG")
        if env_json:
            try:
                parsed: Any = json.loads(env_json)
            except json.JSONDecodeError as error:
                logger.warning(
                    "MEMORY_STORE_CONFIG is not valid JSON; ignoring. (%s)", error
                )
            else:
                if isinstance(parsed, dict):
                    merged.update(parsed)
                else:
                    logger.warning(
                        "MEMORY_STORE_CONFIG must be a JSON object; got %s. Ignoring.",
                        type(parsed).__name__,
                    )

        # Individual vars win over MEMORY_STORE_CONFIG so a deployer can pin a
        # single field without rebuilding the whole JSON blob.
        env_field_map: dict[str, str] = {
            "MEMORY_BACKEND":   "backend",
            "MEMORY_ROOT_PATH": "root_path",
        }
        for env_name, field_name in env_field_map.items():
            value: Optional[str] = os.environ.get(env_name)
            if value is not None and value != "":
                merged[field_name] = value

        return cls.from_dict(merged)


# Only characters safe on every mainstream filesystem. Anything else in a
# namespace component becomes an underscore — prevents path-traversal or
# unexpected directory behaviour.
_SAFE_PATH_COMPONENT: re.Pattern = re.compile(r"[^A-Za-z0-9._-]+")


def sanitise_path_component(part: str) -> str:
    """Replace unsafe filesystem characters with underscores."""
    return _SAFE_PATH_COMPONENT.sub("_", str(part)) or "_"


def keyword_rank(
    entries: list[tuple[str, dict[str, Any]]],
    query: str,
    limit: int,
) -> list[MemoryItem]:
    """
    Rank ``entries`` by how many query words appear in each entry's ``content``.

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


class BaseMemoryStore(ABC):
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

    def __init__(self, root_path: str) -> None:
        self._root: Path = Path(root_path).expanduser().resolve()
        self._locks: dict[Namespace, asyncio.Lock] = {}
        # Guards ``self._locks`` itself — per-namespace locks are created
        # lazily and must not race when inserting into the dict.
        self._locks_guard: asyncio.Lock = asyncio.Lock()
        logger.info(
            "%s initialised. Root path: %s", self.__class__.__name__, self._root
        )

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
        return keyword_rank(list(entries.items()), query, limit)

    async def list(self, namespace: Namespace) -> list[str]:
        """Return every key currently stored under ``namespace``, sorted."""
        async with await self._lock_for(namespace):
            entries: dict[str, dict[str, Any]] = await self._read_file(namespace)
        return sorted(entries.keys())

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
        """Return the asyncio lock guarding writes to ``namespace``, lazily creating it."""
        async with self._locks_guard:
            lock: Optional[asyncio.Lock] = self._locks.get(namespace)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[namespace] = lock
        return lock

    def _path_for(self, namespace: Namespace) -> Path:
        """
        Resolve ``<root>/<network>/<agent>/<topic>.<extension>``.

        The last namespace component (topic) is the filename so each topic's
        whole memory lives in a single readable file.
        """
        parts: list[str] = [sanitise_path_component(part) for part in namespace]
        return self._root.joinpath(*parts[:-1], f"{parts[-1]}.{self._EXTENSION}")

    async def _read_file(self, namespace: Namespace) -> dict[str, dict[str, Any]]:
        """Read and deserialise the topic's file. Missing/unreadable file → empty dict."""
        path: Path = self._path_for(namespace)
        if not path.exists():
            return {}
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
                content: str = await handle.read()
        except OSError as error:
            logger.error(
                "%s: failed to read %s: %s", self.__class__.__name__, path, error
            )
            return {}
        return self._deserialise(content)

    async def _write_file(
        self, namespace: Namespace, entries: dict[str, dict[str, Any]]
    ) -> None:
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
            logger.error(
                "%s: failed to write %s: %s", self.__class__.__name__, path, error
            )
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise
