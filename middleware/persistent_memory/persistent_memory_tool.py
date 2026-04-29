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
The ``persistent_memory`` tool the LLM actually calls.

Each call goes to a handler for that operation, which talks to the store.
If a summarizer was attached, it runs inline while the store lock is held.
"""

from __future__ import annotations

import functools
import logging
from logging import Logger
from typing import Any
from typing import ClassVar
from typing import Optional

from middleware.persistent_memory.topic_store import TopicStore


class PersistentMemoryTool:
    """
    Routes LLM calls to the store, summarizing oversized topics inline.
    """

    ALL_OPERATIONS: ClassVar[frozenset[str]] = frozenset({"create", "read", "append", "delete", "search", "list"})

    _REQUIRED_ARGS: ClassVar[dict[str, tuple[str, ...]]] = {
        "create": ("topic", "content"),
        "read": ("topic",),
        "append": ("topic", "content"),
        "delete": ("topic",),
        "search": ("query",),
        "list": (),
    }

    DEFAULT_SEARCH_LIMIT: ClassVar[int] = 5

    def __init__(
        self,
        tool_config: Optional[dict[str, Any]],
        store: TopicStore,
        summarizer: Optional[Any] = None,
    ) -> None:
        """
        Configure the dispatcher.

        :param tool_config: Config dict assembled by the middleware from the
                            parsed origin path and the HOCON settings.
        :param store:       Pre-built store, injected by the middleware.
        :param summarizer:  Optional summarizer, injected by the middleware.
        """
        self.logger: Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        config: dict[str, Any] = tool_config or {}
        self._namespace_key: str = config.get("namespace_key") or "unknown_network.unknown_agent"

        enabled_ops: Any = config.get("enabled_operations")
        self._enabled_operations: frozenset[str] = frozenset(enabled_ops) if enabled_ops else self.ALL_OPERATIONS

        self._store: TopicStore = store
        self._summarizer: Optional[Any] = summarizer

        self._handlers: dict[str, Any] = self._build_handlers()

        self.logger.info(
            "Initialised for %s with operations: %s",
            self._namespace_key,
            sorted(self._enabled_operations),
        )

    @property
    def enabled_operations(self) -> frozenset[str]:
        """
        Operations this tool accepts from the LLM.
        """
        return self._enabled_operations

    @property
    def namespace_key(self) -> str:
        """
        ``"<network>.<agent>"`` key.
        """
        return self._namespace_key

    async def async_invoke(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Route one LLM call to its handler; return ``{"result": ...}`` or ``{"error": ...}``.

        :param args: Tool-call args from the LLM; must include ``operation``.
        :return: ``{"result": ...}`` envelope on success, ``{"error": ...}`` otherwise.
        """
        operation: str = str(args.get("operation") or "").strip().lower()
        error: Optional[dict[str, Any]] = self._validate_call(operation, args)
        if error is not None:
            return error
        handler = self._handlers[operation]
        try:
            return await handler(args)
        except (ValueError, TypeError, KeyError) as err:
            self.logger.exception("Error during '%s'", operation)
            return self._error(f"Unexpected error during '{operation}': {err}")

    def _build_handlers(self) -> dict[str, Any]:
        """
        Operation → handler dispatch table.

        :return: Dict mapping operation name to its async handler.
        """
        return {
            "create": self._handle_create,
            "read": self._handle_read,
            "append": self._handle_append,
            "delete": self._handle_delete,
            "search": self._handle_search,
            "list": self._handle_list,
        }

    def _validate_call(self, operation: str, args: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Check the operation is known, enabled, and has every required arg.

        :param operation: Operation name from the LLM (already trimmed/lowercased).
        :param args:      Tool-call args from the LLM.
        :return: An ``{"error": ...}`` dict if the call is invalid, else ``None``.
        """
        if not operation or operation not in self.ALL_OPERATIONS:
            return self._error(
                "Missing or unknown operation. Must be one of: " + ", ".join(sorted(self.ALL_OPERATIONS))
            )
        if operation not in self._enabled_operations:
            return self._error(
                f"Operation '{operation}' is not enabled for this agent. "
                f"Enabled: {', '.join(sorted(self._enabled_operations))}"
            )
        for field in self._REQUIRED_ARGS[operation]:
            if not self._get_arg(args, field):
                return self._error(f"Operation '{operation}' requires '{field}'.")
        return None

    async def _handle_create(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Create or overwrite a topic.

        :param args: Tool-call args; requires ``topic`` and ``content``.
        :return: ``{"result": {"status": "created", "topic": ...}}``.
        """
        topic: str = self._get_arg(args, "topic")
        content: str = self._get_arg(args, "content")
        await self._store.set_topic(
            self._namespace_key,
            topic,
            content,
            post_write=self._summarizer_callback(topic),
        )
        return {"result": {"status": "created", "topic": topic}}

    async def _handle_read(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Read a topic's content.

        :param args: Tool-call args; requires ``topic``.
        :return: ``{"result": {"topic", "content"}}`` or an error envelope.
        """
        topic: str = self._get_arg(args, "topic")
        content: Optional[str] = await self._store.get_topic(
            self._namespace_key,
            topic,
            post_read=self._summarizer_callback(topic),
        )
        if content is None:
            return self._error(f"No memory entry found for topic='{topic}'.")
        return {"result": {"topic": topic, "content": content}}

    async def _handle_append(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Append a timestamped line.

        :param args: Tool-call args; requires ``topic`` and ``content``.
        :return: ``{"result": {"status": "appended", "topic": ..., "content": ...}}``
                 where ``content`` is the full post-append (and possibly
                 post-summarization) text.
        """
        topic: str = self._get_arg(args, "topic")
        content: str = self._get_arg(args, "content")
        new_content: str = await self._store.append_to_topic(
            self._namespace_key,
            topic,
            content,
            post_write=self._summarizer_callback(topic),
        )
        return {"result": {"status": "appended", "topic": topic, "content": new_content}}

    async def _handle_delete(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Delete a topic (no-op if missing).

        :param args: Tool-call args; requires ``topic``.
        :return: ``{"result": {"status": "deleted", "topic": ...}}``.
        """
        topic: str = self._get_arg(args, "topic")
        await self._store.delete_topic(self._namespace_key, topic)
        return {"result": {"status": "deleted", "topic": topic}}

    async def _handle_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Keyword-rank this agent's topics against ``query``.

        :param args: Tool-call args; requires ``query``, optional ``limit``.
        :return: ``{"result": {"results": [...]}}`` with ranked hits.
        """
        query: str = self._get_arg(args, "query")
        limit: int = self._parse_limit(args.get("limit"), self.DEFAULT_SEARCH_LIMIT)
        results: list[dict[str, Any]] = await self._store.search_topics(
            self._namespace_key,
            query,
            limit,
            post_read_factory=self._summarizer_callback,
        )
        return {"result": {"results": results}}

    async def _handle_list(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Return all topic names, sorted.

        :param args: Tool-call args; ignored.
        :return: ``{"result": {"topics": [...]}}``.
        """
        del args
        topics: list[str] = await self._store.list_topics(self._namespace_key)
        return {"result": {"topics": topics}}

    def _summarizer_callback(self, topic: str) -> Optional[Any]:
        """
        Build the ``post_write`` / ``post_read`` callback; ``None`` if no summarizer.

        :param topic: Topic name to bind into the callback.
        :return: A callable, or ``None`` if no summarizer is configured.
        """
        if self._summarizer is None:
            return None
        return functools.partial(self._maybe_summarize, topic)

    async def _maybe_summarize(self, topic: str, observed_content: str) -> Optional[str]:
        """
        Summarize iff the summarizer says to; return the new content or ``None``.

        :param topic:            Topic name.
        :param observed_content: Current content seen by the store.
        :return: The new summary if one was produced, else ``None``.
        """
        if not self._summarizer.should_summarize(observed_content):
            return None
        summary: str = await self._summarizer.summarize_topic(topic, observed_content)
        if not summary or summary == observed_content:
            return None
        return summary

    @staticmethod
    def _get_arg(args: dict[str, Any], field: str) -> str:
        """
        Pull a string arg out of the tool call, trimmed. Empty if missing.

        :param args:  Tool-call args from the LLM.
        :param field: Name of the arg to pull.
        :return: The trimmed string value (``""`` if absent or whitespace-only).
        """
        raw_value: Any = args.get(field)
        return "" if raw_value is None else str(raw_value).strip()

    @staticmethod
    def _parse_limit(value: Any, default: int) -> int:
        """
        Best-effort positive-int parse. Returns ``default`` on any failure.

        :param value:   Raw value from the LLM (may be any type).
        :param default: Fallback when parsing fails or value is non-positive.
        :return: Positive int, or ``default``.
        """
        # LLMs can decide to pass 'limit' as None, a string, or garbage.
        # Fall back to the default on every failure so search never raises.
        try:
            parsed: int = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        """
        Uniform error envelope.

        :param message: Human-readable error message.
        :return: ``{"error": message}``.
        """
        return {"error": message}
