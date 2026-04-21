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
File-system markdown implementation of ``MemoryStore``.

One markdown file per topic, laid out as::

    <root_path>/<agent_network_name>/<agent_name>/<topic>.md

Inside each file, every memory entry is an H1 section. The heading text is the
entry's key, and the body is the ``content`` field as markdown. Extra
non-``content`` fields, when present, are serialised as a fenced JSON block at
the top of the section::

    # name

    The user's name is Mike.

    # favorite_coffee_order

    ```json
    {"category": "drink"}
    ```

    User prefers black coffee from Henry's.

Shared filesystem machinery (locking, atomic writes, path resolution) lives in
``MemoryStore``; this module only owns the markdown serialisation format.
"""

import json
import logging
import re
from typing import Any

from coded_tools.tools.persistent_memory.memory_item import DEFAULT_KEY
from coded_tools.tools.persistent_memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Re-exported for test modules that import the constant from this file.
# Single source of truth lives in ``memory_item`` — do not redefine it here.
__all__ = ["DEFAULT_KEY", "MarkdownFileStore"]


class MarkdownFileStore(MemoryStore):
    """
    One-markdown-file-per-topic store backend.

    :param root_path: Directory under which all topic files live.
                      Created on first write if it does not exist.
    """

    _EXTENSION: str = "md"

    # Splits the markdown document on H1 heading lines. A regex keeps the split
    # faithful to ``^# ``-at-start-of-line semantics across mixed line endings.
    _SECTION_SPLIT: re.Pattern = re.compile(r"(?m)^# ")

    # Fenced JSON block used for non-``content`` fields within a section.
    _JSON_FENCE_OPEN: str = "```json\n"
    _JSON_FENCE_CLOSE: str = "\n```"

    def _serialise(self, entries: dict[str, dict[str, Any]]) -> str:
        """Render the topic's whole memory as a markdown document.

        Single-entry files (the common "one blob per topic" layout) render as
        plain prose with no ``# key`` heading — the file just contains the
        accumulated content. Multi-entry files fall back to one H1 section per
        key, ordered deterministically for clean diffs.

        :param entries: ``{key: value_dict}`` to render.
        :return: Markdown text ready to write to disk.
        """
        if not entries:
            return ""
        # Headingless layout only when the sole entry is the canonical default
        # key. This keeps the "one blob per topic" case clean while preserving
        # deterministic round-trips for callers that DO use explicit keys.
        if len(entries) == 1:
            only_key: str = next(iter(entries.keys()))
            if only_key == DEFAULT_KEY:
                return self._serialise_body(entries[only_key])
        sections: list[str] = []
        for key in sorted(entries.keys()):
            sections.append(self._serialise_section(key, entries[key]))
        return "\n".join(sections)

    def _deserialise(self, content: str) -> dict[str, dict[str, Any]]:
        """Parse a markdown document produced by :meth:`_serialise` back into ``{key: value_dict}``.

        Tolerates hand-edits: malformed JSON blocks are silently treated as part
        of the ``content`` body so no data is ever lost. A file with no H1
        headings is the "one blob per topic" layout — the whole document is
        returned as a single entry under :attr:`DEFAULT_KEY`.

        :param content: Raw markdown text read from disk.
        :return: ``{key: value_dict}`` parsed from the document.
        """
        if not content.strip():
            return {}

        # re.split keeps everything before the first H1 as ``sections[0]``; that
        # preamble is ignored. Each subsequent element starts just after ``# ``.
        raw_sections: list[str] = self._SECTION_SPLIT.split(content)
        if len(raw_sections) < 2:
            # No H1 headings anywhere — treat the whole file as a single entry.
            return {DEFAULT_KEY: self._parse_section_body(content)}

        result: dict[str, dict[str, Any]] = {}
        for chunk in raw_sections[1:]:
            newline_index: int = chunk.find("\n")
            if newline_index == -1:
                key: str = chunk.strip()
                body: str = ""
            else:
                key = chunk[:newline_index].strip()
                body = chunk[newline_index + 1 :]
            if not key:
                continue
            result[key] = self._parse_section_body(body)
        return result

    @classmethod
    def _serialise_body(cls, value: dict[str, Any]) -> str:
        """Render just the body of an entry (content + optional JSON metadata).

        No heading is emitted. Used for single-entry files.

        :param value: Entry value dict.
        :return: Markdown body text.
        """
        remaining: dict[str, Any] = dict(value)
        content: Any = remaining.pop("content", None)

        lines: list[str] = []
        if remaining:
            meta: str = json.dumps(remaining, ensure_ascii=False, indent=2, sort_keys=True)
            lines.append(f"{cls._JSON_FENCE_OPEN}{meta}{cls._JSON_FENCE_CLOSE}\n")
        if content is not None:
            text: str = str(content).rstrip("\n")
            lines.append(f"{text}\n")
        return "".join(lines)

    @classmethod
    def _serialise_section(cls, key: str, value: dict[str, Any]) -> str:
        """Render one ``(key, value)`` pair as a markdown H1 section.

        The body is the ``content`` field; any other fields are emitted as a
        fenced JSON block above the body. A value with only ``content``
        produces a clean heading-and-prose section.

        :param key: Entry key (becomes the H1 heading).
        :param value: Entry value dict.
        :return: Markdown section text.
        """
        remaining: dict[str, Any] = dict(value)
        content: Any = remaining.pop("content", None)

        lines: list[str] = [f"# {key}\n"]
        if remaining:
            meta: str = json.dumps(remaining, ensure_ascii=False, indent=2, sort_keys=True)
            lines.append(f"\n{cls._JSON_FENCE_OPEN}{meta}{cls._JSON_FENCE_CLOSE}\n")
        if content is not None:
            text: str = str(content)
            lines.append(f"\n{text}\n")
        return "".join(lines)

    @classmethod
    def _parse_section_body(cls, body: str) -> dict[str, Any]:
        """Pull an optional fenced JSON block out of a section body.

        The remaining markdown becomes the ``content`` field.

        :param body: Section body text (everything after the H1 line).
        :return: Parsed value dict.
        """
        value: dict[str, Any] = {}
        trimmed: str = body.lstrip("\n")

        if trimmed.startswith(cls._JSON_FENCE_OPEN):
            rest: str = trimmed[len(cls._JSON_FENCE_OPEN) :]
            close_index: int = rest.find(cls._JSON_FENCE_CLOSE)
            if close_index != -1:
                json_text: str = rest[:close_index]
                remainder: str = rest[close_index + len(cls._JSON_FENCE_CLOSE) :]
                try:
                    parsed: Any = json.loads(json_text)
                except json.JSONDecodeError:
                    logger.warning("MarkdownFileStore: malformed JSON block in section; keeping as prose")
                else:
                    if isinstance(parsed, dict):
                        value.update(parsed)
                        trimmed = remainder.lstrip("\n")

        content: str = trimmed.rstrip("\n").rstrip()
        if content:
            value["content"] = content
        return value
