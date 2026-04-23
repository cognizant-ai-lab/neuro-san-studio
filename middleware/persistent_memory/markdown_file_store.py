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
Markdown-file memory store backend.

Stores each topic as its own ``.md`` file (``# <topic>`` heading + body).
Locks are per-topic, so different topics on the same agent can be written
in parallel.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import ClassVar
from typing import Optional
from typing import override

import aiofiles

from middleware.persistent_memory.topic_store import TopicStore


class MarkdownFileStore(TopicStore):
    """
    One markdown file per topic.
    """

    _EXTENSION: ClassVar[str] = "md"
    # Runs of non-word / non-hyphen chars collapse to ``_`` for filenames.
    _UNSAFE_FILENAME: ClassVar[re.Pattern] = re.compile(r"[^\w\-]")

    @override
    def _lock_key(self, namespace: str, topic: str) -> tuple[str, ...]:
        """
        Per-topic lock.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The lock-cache key for this topic.
        """
        return ("md", namespace, self._sanitise_filename(topic))

    @override
    def _list_lock_key(self, namespace: str) -> tuple[str, ...]:
        """
        Agent-level lock; does not block per-topic writers.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The lock-cache key for list/search ops.
        """
        return ("md-list", namespace)

    @override
    async def load_all(self, namespace: str) -> TopicStore.AgentMemory:
        """
        Load every ``*.md`` file under the agent's directory.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's full ``{topic: content}`` dict.
        """
        base: Path = self._agent_dir(namespace)
        if not base.exists():
            return {}
        return await self._load_agent_dir(base)

    @override
    async def save_all(self, namespace: str, memory: TopicStore.AgentMemory) -> None:
        """
        Write each topic as its own ``.md`` file, deleting orphans.

        :param namespace: ``"<network>.<agent>"`` key.
        :param memory:    Full ``{topic: content}`` dict to persist.
        """
        base: Path = self._agent_dir(namespace)
        base.mkdir(parents=True, exist_ok=True)

        expected: set[str] = {self._sanitise_filename(topic) + f".{self._EXTENSION}" for topic in memory}
        self._remove_orphans(base, expected)
        for topic, content in memory.items():
            await self._write_topic_file(base, topic, content)

    @override
    async def _read_topic(self, namespace: str, topic: str) -> Optional[str]:
        """
        Read one topic's ``.md`` body, or ``None``.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: The topic's body text, or ``None`` if absent or unreadable.
        """
        path: Path = self._topic_path(namespace, topic)
        if not path.exists():
            return None
        parsed: Optional[tuple[str, str]] = await self._load_topic_file(path)
        if parsed is None:
            return None
        _, body = parsed
        return body

    @override
    async def _write_topic(self, namespace: str, topic: str, content: str) -> None:
        """
        Atomically persist one topic as a single ``.md`` file.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :param content:   New content for the topic.
        """
        base: Path = self._agent_dir(namespace)
        base.mkdir(parents=True, exist_ok=True)
        await self._write_topic_file(base, topic, content)

    @override
    async def _remove_topic(self, namespace: str, topic: str) -> bool:
        """
        Unlink the topic's ``.md`` file.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: ``True`` if the file existed and was deleted.
        """
        path: Path = self._topic_path(namespace, topic)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError:
            self.logger.warning("Failed to delete %s", path, exc_info=True)
            return False

    @override
    async def _read_bucket(self, namespace: str) -> dict[str, str]:
        """
        Load every topic for this agent.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: The agent's ``{topic: content}`` dict; empty if none yet.
        """
        base: Path = self._agent_dir(namespace)
        if not base.exists():
            return {}
        return await self._load_agent_dir(base)

    async def _load_agent_dir(self, base: Path) -> dict[str, str]:
        """
        Load every ``.md`` file under one agent directory.

        :param base: Directory holding the agent's ``*.md`` files.
        :return: Parsed ``{topic: content}`` dict.
        """
        topics: dict[str, str] = {}
        for md_file in sorted(base.glob(f"*.{self._EXTENSION}")):
            parsed: Optional[tuple[str, str]] = await self._load_topic_file(md_file)
            if parsed is None:
                continue
            topic, content = parsed
            if topic and content:
                topics[topic] = content
        return topics

    async def _load_topic_file(self, path: Path) -> Optional[tuple[str, str]]:
        """
        Read one ``.md`` file; return ``(topic, body)`` or ``None`` on error.

        :param path: Path to the ``.md`` file.
        :return: ``(topic, body)`` tuple, or ``None`` on read failure.
        """
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
                raw: str = await handle.read()
        except (OSError, UnicodeDecodeError):
            self.logger.warning("Failed to read %s", path, exc_info=True)
            return None
        return self._extract_topic(raw)

    async def _write_topic_file(self, base: Path, topic: str, content: str) -> None:
        """
        Atomic write via temp-file + rename. Body is ``# <topic>\\n\\n<content>\\n``.

        :param base:    Agent's directory.
        :param topic:   Topic name, used for the heading and filename.
        :param content: Body content to write.
        """
        filename: str = self._sanitise_filename(topic) + f".{self._EXTENSION}"
        path: Path = base / filename
        tmp_path: Path = path.with_suffix(path.suffix + ".tmp")
        body: str = f"# {topic}\n\n{content}\n"
        try:
            async with aiofiles.open(tmp_path, mode="w", encoding="utf-8") as handle:
                await handle.write(body)
            os.replace(tmp_path, path)
        except OSError:
            self.logger.error("Failed to write %s", path, exc_info=True)

    def _topic_path(self, namespace: str, topic: str) -> Path:
        """
        Resolve ``<root>/<network>/<agent>/<topic>.md``.

        :param namespace: ``"<network>.<agent>"`` key.
        :param topic:     Topic name.
        :return: Absolute path to the topic's ``.md`` file.
        """
        filename: str = self._sanitise_filename(topic) + f".{self._EXTENSION}"
        return self._agent_dir(namespace) / filename

    def _agent_dir(self, namespace: str) -> Path:
        """
        Resolve ``<root>/<network>/<agent>/``.

        :param namespace: ``"<network>.<agent>"`` key.
        :return: Absolute path to the agent's directory.
        """
        network, agent = self._split_namespace(namespace)
        return self._root / network / agent

    @staticmethod
    def _sanitise_filename(topic: str) -> str:
        """
        Topic → safe lower-case filename stem; empty → ``"untitled"``.

        :param topic: Raw topic name.
        :return: Filename-safe stem (no extension).
        """
        cleaned: str = MarkdownFileStore._UNSAFE_FILENAME.sub("_", topic).strip("_").lower()
        return cleaned or "untitled"

    @staticmethod
    def _extract_topic(raw: str) -> tuple[str, str]:
        """
        Split a markdown file into ``(topic_heading, body)``; expects first ``# <topic>``.

        :param raw: Raw markdown file contents.
        :return: ``(topic, body)`` tuple; empty strings if no heading found.
        """
        lines: list[str] = raw.split("\n")
        topic: str = ""
        body_start: int = 0
        for i, line in enumerate(lines):
            stripped: str = line.strip()
            if stripped.startswith("# "):
                topic = stripped[2:].strip()
                body_start = i + 1
                break
        body: str = "\n".join(lines[body_start:]).strip()
        return topic, body

    def _remove_orphans(self, base: Path, expected: set[str]) -> None:
        """
        Delete ``.md`` files in ``base`` whose names are not in ``expected``.

        :param base:     Agent's directory.
        :param expected: Set of filenames (with extension) to keep.
        """
        if not base.exists():
            return
        for md_file in base.glob("*.md"):
            if md_file.name in expected:
                continue
            try:
                md_file.unlink()
            except OSError:
                self.logger.warning("Failed to remove orphan %s", md_file, exc_info=True)
