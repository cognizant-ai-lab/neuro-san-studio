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
JSON-file memory store backend.

Stores all of one agent's topics in a single JSON file. All writes to that
agent share one lock, so different agents can still write in parallel.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from typing import ClassVar
from typing import Optional
from typing import override

import aiofiles

from middleware.persistent_memory.topic_store import TopicStore


class JsonFileStore(TopicStore):
    """
    One JSON file per agent.
    """

    DEFAULT_FILE_NAME: ClassVar[str] = "memory"

    _EXTENSION: ClassVar[str] = "json"
    # Collapses anything outside ``[A-Za-z0-9_-]`` (including ``..`` and path
    # separators) to ``_`` so a user-supplied ``file_name`` cannot
    # escape the agent's directory.
    _UNSAFE_FILE_CHARS: ClassVar[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_-]")

    def __init__(self, folder_name: str, file_name: str = DEFAULT_FILE_NAME) -> None:
        super().__init__(folder_name)
        # Accept ``"memory.json"`` / path-like values and reduce to a safe stem.
        raw: str = (file_name or self.DEFAULT_FILE_NAME).strip()
        stem: str = Path(raw).stem or self.DEFAULT_FILE_NAME
        cleaned: str = self._UNSAFE_FILE_CHARS.sub("_", stem).strip("_")
        self._file_name: str = cleaned or self.DEFAULT_FILE_NAME

    def _path_for(self, namespace: str) -> Path:
        """
        Resolve ``<root>/<network>/<agent>/<file_name>.json``.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: Absolute path to the agent's JSON memory file.
        """
        network, agent = self._split_namespace(namespace)
        return self._root / network / agent / f"{self._file_name}.{self._EXTENSION}"

    @override
    def _lock_key(self, namespace: str, topic: str) -> tuple[str, ...]:
        """
        Per-agent lock — the file is shared.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Ignored; the whole file is locked together.
        :return: The lock-cache key for this agent.
        """
        del topic
        return ("json", namespace)

    @override
    def _list_lock_key(self, namespace: str) -> tuple[str, ...]:
        """
        Shares the per-agent lock.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The lock-cache key for list/search ops.
        """
        return ("json", namespace)

    @override
    async def load_all(self, namespace: str) -> TopicStore.AgentMemory:
        """
        Read and parse the agent's JSON file.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full ``{topic: content}`` dict.
        """
        return await self._load_unlocked(namespace)

    @override
    async def save_all(self, namespace: str, memory: TopicStore.AgentMemory) -> None:
        """
        Persist the full memory dict as one JSON file.

        :param namespace: ``"<network>.<agent>"`` key.
        :param memory:    Full ``{topic: content}`` dict to write.
        """
        async with await self._lock_for(self._lock_key(namespace, "")):
            await self._write_unlocked(namespace, memory)

    @override
    async def _read_topic(self, namespace: str, topic: str) -> Optional[str]:
        """
        Return one topic's content, or ``None``.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's content, or ``None`` if absent.
        """
        memory: TopicStore.AgentMemory = await self._load_unlocked(namespace)
        value: Optional[str] = memory.get(topic)
        return value

    @override
    async def _write_topic(self, namespace: str, topic: str, content: str) -> None:
        """
        Read-modify-write the agent's JSON file.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param content:   New content for the topic.
        """
        memory: TopicStore.AgentMemory = await self._load_unlocked(namespace)
        memory[topic] = content
        await self._write_unlocked(namespace, memory)

    @override
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Drop the topic and rewrite the file.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if the topic existed and was removed.
        """
        memory: TopicStore.AgentMemory = await self._load_unlocked(namespace)
        if topic not in memory:
            return False
        memory.pop(topic, None)
        await self._write_unlocked(namespace, memory)
        return True

    @override
    async def _read_bucket(self, namespace: str) -> dict[str, str]:
        """
        Return the agent's ``{topic: content}`` dict.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: A shallow copy of the agent's full memory.
        """
        memory: TopicStore.AgentMemory = await self._load_unlocked(namespace)
        return dict(memory)

    async def _load_unlocked(self, namespace: str) -> TopicStore.AgentMemory:
        """
        Read-and-parse the JSON file; ``{}`` if missing or unreadable.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The parsed ``{topic: content}`` dict, empty on any failure.
        """
        path: Path = self._path_for(namespace)
        if not path.exists():
            return {}
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
                raw: str = await handle.read()
        except (OSError, UnicodeDecodeError):
            self.logger.warning("Failed to read %s", path, exc_info=True)
            return {}
        return self._parse(raw)

    async def _write_unlocked(self, namespace: str, memory: TopicStore.AgentMemory) -> None:
        """
        Atomic write via temp-file + rename.

        :param namespace: ``"<network>.<agent>"`` key.
        :param memory:    Full ``{topic: content}`` dict to persist.
        """
        path: Path = self._path_for(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path = path.with_suffix(path.suffix + ".tmp")
        payload: str = json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            async with aiofiles.open(tmp_path, mode="w", encoding="utf-8") as handle:
                await handle.write(payload)
            os.replace(tmp_path, path)
        except OSError:
            self.logger.error("Failed to write %s", path, exc_info=True)

    def _parse(self, raw: str) -> TopicStore.AgentMemory:
        """
        Parse JSON into flat ``{topic: str}``; tolerates malformed files and legacy shapes.

        :param raw: Raw file contents.
        :return: Parsed ``{topic: content}`` dict; empty on malformed input.
        """
        if not raw.strip():
            return {}
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError as error:
            self.logger.warning("Malformed JSON (%s); treating as empty.", error)
            return {}
        if not isinstance(parsed, dict):
            self.logger.warning(
                "Top-level JSON is %s, expected object. Ignoring.",
                type(parsed).__name__,
            )
            return {}
        normalised: TopicStore.AgentMemory = {}
        for topic, value in parsed.items():
            normalised[str(topic)] = JsonFileStore._coerce_value(value)
        return normalised

    @staticmethod
    def _coerce_value(value: Any) -> str:
        """
        Coerce a stored value to a plain string; accepts legacy ``{"content": ...}``.

        :param value: Raw value pulled from parsed JSON.
        :return: The value as a plain string.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "content" in value:
            return str(value.get("content") or "")
        return str(value)
