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
LLM-backed summariser used by ``PersistentMemoryMiddleware`` to post-process
``read`` / ``search`` results and, optionally, to auto-compact memory files
on write.
"""

from __future__ import annotations

import logging
from typing import Any
from typing import Optional

from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

# Optional dependency: only agent networks that turn the summariser on need
# ``langchain_openai`` installed. If it is missing we leave ``ChatOpenAI`` as
# ``None`` and surface a clear error at ``MemorySummariser`` construction
# time, rather than at import time for every agent network.
try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - exercised only in minimal envs
    ChatOpenAI = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class MemorySummariser:
    """
    Post-processes ``read`` and ``search`` results by passing each entry's
    ``content`` string through an LLM with a short summariser prompt.

    Built from a HOCON block like::

        memory_summariser {
            enabled      = true
            model        = "gpt-4.1-mini"
            instructions = "You are a summariser..."
        }

    If ``enabled`` is false, ``from_config`` returns ``None`` and the
    middleware skips summarisation entirely.

    Lifecycle note: ``compact_on_write``, ``compact_threshold``, and
    ``personalisation`` are public attributes that are only mutated by
    ``from_config`` immediately after construction. After that point they
    are treated as read-only and are safe to read concurrently. A single
    summariser instance is owned by the middleware that constructed it;
    do not share one instance across unrelated middleware and then mutate
    its attributes.
    """

    _DEFAULT_MODEL: str = "gpt-4.1-mini"
    # Content shorter than this is returned raw — summarising a two-line entry
    # just adds latency and cost for no real compression benefit.
    _DEFAULT_MIN_CHARS: int = 300
    # File size past which ``compact_on_write`` triggers a disk-level rewrite.
    # Tuned lower than ``_DEFAULT_MIN_CHARS`` because compaction is about
    # controlling long-term storage growth — we want to fire before the file
    # is "too big to skim", which is earlier than the point at which a
    # single read payload is worth summarising.
    _DEFAULT_COMPACT_THRESHOLD: int = 200

    def __init__(
        self,
        model_name: str,
        instructions: str,
        min_chars: int = _DEFAULT_MIN_CHARS,
    ) -> None:
        """Build a summariser backed by an OpenAI chat model.

        :param model_name: Model id to pass to ``ChatOpenAI``.
        :param instructions: System prompt used on every summarise call.
        :param min_chars: Content shorter than this is returned raw without an LLM call.
        """
        if ChatOpenAI is None:
            raise RuntimeError(
                "langchain_openai is not installed; it is required to use the "
                "memory summariser. Install it with `pip install langchain-openai` "
                "or disable the summariser (set `memory_summariser.enabled = false` "
                "in HOCON)."
            )
        self._llm = ChatOpenAI(model=model_name)
        self._instructions: str = instructions.strip()
        # Threshold below which we return the raw content without an LLM call.
        self._min_chars: int = max(0, int(min_chars))
        # Auto-compaction on write: public so the middleware can consult them
        # without reaching into a protected attribute. Defaults here keep the
        # feature OFF unless ``from_config`` explicitly turns it on.
        self.compact_on_write: bool = False
        self.compact_threshold: int = self._DEFAULT_COMPACT_THRESHOLD
        # Optional user-editable personalisation appended to the base
        # instructions on every summariser call. Empty by default.
        self.personalisation: str = ""

    @classmethod
    def from_config(cls, config: Optional[dict[str, Any]]) -> Optional["MemorySummariser"]:
        """Return a configured summariser or ``None`` if disabled / absent.

        :param config: The HOCON ``memory_summariser`` block, or ``None``.
        :return: A fully-configured ``MemorySummariser`` or ``None`` to disable summarisation.
        """
        if not config or not config.get("enabled"):
            return None
        instructions: str = str(config.get("instructions") or "").strip()
        if not instructions:
            logger.warning("Memory summariser is enabled but has no 'instructions'; disabling.")
            return None
        model_name: str = str(config.get("model") or cls._DEFAULT_MODEL).strip()
        summariser = cls(
            model_name=model_name,
            instructions=instructions,
            min_chars=cls._parse_int(config.get("min_chars"), cls._DEFAULT_MIN_CHARS),
        )
        summariser.compact_on_write = bool(config.get("compact_on_write", False))
        summariser.compact_threshold = max(
            0, cls._parse_int(config.get("compact_threshold"), cls._DEFAULT_COMPACT_THRESHOLD)
        )
        summariser.personalisation = str(config.get("personalisation") or "").strip()
        return summariser

    async def summarise(self, raw: str) -> str:
        """Call the summariser LLM on one entry's raw accumulated content.

        Custom helper (not a framework hook) — the single entry point the
        middleware uses for both on-read summarisation and on-write compaction.

        :param raw: Raw accumulated content to summarise.
        :return: Summarised content; falls back to ``raw`` if the LLM returns empty.
        """
        system_prompt: str = self._instructions
        if self.personalisation:
            system_prompt = (
                f"{system_prompt}\n\n"
                "User personalisation (additional instructions supplied by the "
                "agent network's operator — follow these on top of the base "
                "instructions above):\n"
                f"{self.personalisation}"
            )
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=raw),
        ]
        response: Any = await self._llm.ainvoke(messages)
        content: Any = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip() or raw
        # Some chat models return a list of content blocks — stringify safely.
        return str(content).strip() or raw

    async def post_process(self, operation: str, result: dict[str, Any]) -> dict[str, Any]:
        """Replace raw ``content`` strings in ``read`` / ``search`` results with summaries.

        Custom helper (not a framework hook). Called by the middleware after a
        read/search has returned so the LLM sees a compact current-state view
        instead of the raw append-only log.

        Errors fall back to the raw result so a broken LLM never hides the
        stored memory.

        :param operation: The operation whose result is being processed.
        :param result: The raw result envelope from ``PersistentMemoryTool``.
        :return: The same envelope with content fields potentially summarised.
        """
        payload: Any = result.get("result")
        if not isinstance(payload, dict):
            return result

        try:
            if operation == "read":
                raw: str = str(payload.get("content") or "")
                if self._should_summarise(raw):
                    payload["content"] = await self.summarise(raw)
            elif operation == "search":
                entries: Any = payload.get("results")
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        raw_entry: str = str(entry.get("content") or "")
                        if self._should_summarise(raw_entry):
                            entry["content"] = await self.summarise(raw_entry)
        # Summarisation is best-effort. A failure from the LLM SDK (network,
        # rate limit, auth, bad response shape) must not swallow the
        # underlying memory — return the raw result so the agent still sees
        # the data. We catch the concrete error families the LLM path can
        # raise; truly unexpected errors propagate.
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
            logger.warning("Memory summariser failed; returning raw: %s", error)

        return result

    def _should_summarise(self, raw: str) -> bool:
        """Only pay the LLM cost once the raw content is long enough to matter.

        :param raw: Raw content string.
        :return: ``True`` if the content crosses ``min_chars``.
        """
        return len(raw) >= self._min_chars

    @staticmethod
    def _parse_int(value: Any, default: int) -> int:
        """Coerce a HOCON-provided value to int.

        :param value: Raw HOCON value (may be ``None``, a string, or an int).
        :param default: Fallback when ``value`` is ``None`` or unparsable.
        :return: Parsed int or ``default``.
        """
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
