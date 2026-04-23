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
Middleware that wires persistent memory into an agent.

Builds the store and summarizer from HOCON, registers a single
``persistent_memory`` tool, and adds a short "you have memory" blurb to
the system prompt. All disk I/O happens inside the tool, not here.
"""

from __future__ import annotations

import logging
import re
from logging import Logger
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import ClassVar
from typing import Optional
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool

from middleware.persistent_memory.persistent_memory_tool import PersistentMemoryTool
from middleware.persistent_memory.topic_store import TopicStore
from middleware.persistent_memory.topic_store_factory import TopicStoreFactory
from middleware.persistent_memory.topic_summarizer import TopicSummarizer


class PersistentMemoryMiddleware(AgentMiddleware):
    """
    Wraps ``PersistentMemoryTool`` and plugs it into the agent lifecycle.

    :param origin_str:    When ``True`` (the default), asks the framework to
                          inject the runtime dotted call path at startup.
                          When a string, it is used directly as the origin.
                          In both cases the value is parsed to derive the
                          ``(network, agent)`` memory namespace.
    :param memory_config: HOCON memory settings (store, summarization, and
                          enabled operations). Unknown keys are ignored.
    """

    MEMORY_TOOL_NAME: ClassVar[str] = "persistent_memory"

    _DEFAULT_MAX_TOPIC_SIZE: ClassVar[int] = 1000

    _MEMORY_CONFIG_KEYS: ClassVar[frozenset[str]] = frozenset({"storage", "summarization", "enabled_operations"})
    _SUMMARIZATION_CONFIG_KEYS: ClassVar[frozenset[str]] = frozenset({"max_topic_size", "model", "personalization"})
    _DISPATCH_ARG_KEYS: ClassVar[tuple[str, ...]] = ("topic", "content", "query", "limit")
    _INDEX_SUFFIX_RE: ClassVar[re.Pattern[str]] = re.compile(r"-\d+$")

    # Namespace segments are joined into a filesystem path by the store.
    # Collapse anything outside ``[A-Za-z0-9_-]`` — including ``..``, ``/``,
    # and null bytes — to ``_`` so no ``origin_str`` can escape the root.
    _UNSAFE_PATH_CHARS: ClassVar[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_-]")

    def __init__(
        self,
        origin_str: bool | str = True,
        memory_config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        self.logger: Logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        agent_network_name, agent_name = self._parse_origin_str(origin_str)
        namespace_key: str = f"{agent_network_name}.{agent_name}"

        store_config, summarization_config, enabled_operations_raw = self._parse_memory_config(memory_config)
        enabled_operations: frozenset[str] = self._clean_enabled_operations(enabled_operations_raw, namespace_key)

        max_topic_size, summarization_model, personalization = self._parse_summarization_config(summarization_config)

        # ``JsonFileStore`` defaults + sanitises ``file_name`` on its own;
        # the markdown backend ignores it. See ``JsonFileStore.__init__``.
        self._store: TopicStore = TopicStoreFactory.create(store_config)
        self._summarizer: TopicSummarizer = TopicSummarizer(
            model_name=summarization_model,
            personalization=personalization,
            max_topic_size=max_topic_size,
        )

        self.persistent_memory_tool: PersistentMemoryTool = PersistentMemoryTool(
            tool_config={
                "namespace_key": namespace_key,
                "enabled_operations": enabled_operations,
            },
            store=self._store,
            summarizer=self._summarizer,
        )

        self.tools: list[BaseTool] = [self._build_dispatcher_tool()]

        self.logger.info(
            "Initialised for %s. Enabled operations: %s",
            namespace_key,
            sorted(self.persistent_memory_tool.enabled_operations),
        )

    @property
    def namespace_key(self) -> str:
        """
        ``"<network>.<agent>"`` key.
        """
        return self.persistent_memory_tool.namespace_key

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Add the memory preamble to the system prompt, then hand off to the model.

        :param request: The incoming model request.
        :param handler: Downstream handler that runs the model.
        :return: The handler's response, with the preamble applied upstream.
        """
        preamble: str = self.build_preamble()
        existing: str = request.system_message.content if request.system_message is not None else ""
        new_system: SystemMessage = SystemMessage(content=f"{existing}\n\n{preamble}".strip())
        return await handler(request.override(system_message=new_system))

    async def _dispatch(self, operation: str, **call_args: Any) -> dict[str, Any]:
        """
        Forward one tool call from the LLM down to the tool.

        :param operation: Which memory operation to perform (e.g. 'read', 'append').
        :param call_args: The rest of the tool call's args, passed as-is to the tool.
                          Should include 'topic' for most ops, 'content' for create/append, and 'query' for search.
        :return: The tool's response, or an error dict if something goes wrong.
        """
        args: dict[str, Any] = {"operation": operation}
        for key in self._DISPATCH_ARG_KEYS:
            value: Any = call_args.get(key)
            if value:
                args[key] = value
        return await self.persistent_memory_tool.async_invoke(args)

    def _build_dispatcher_tool(self) -> BaseTool:
        """
        Build the one ``persistent_memory`` tool the LLM sees.

        :return: A LangChain ``StructuredTool`` wrapping ``_dispatch``.
        """
        allowed: list[str] = sorted(self.persistent_memory_tool.enabled_operations)

        return StructuredTool.from_function(
            coroutine=self._dispatch,
            name=self.MEMORY_TOOL_NAME,
            description=(
                "Persistent long-term memory. Pass 'topic' on every call to "
                "name the slice of memory (e.g. 'coffee_preference', 'role'). "
                "Call with 'operation' set to one of: "
                f"{', '.join(allowed)}. "
                "create/append need 'content'; "
                "read/delete need 'topic'; "
                "search needs 'query' (optional 'limit'); "
                "list needs no extra fields. "
                "'append' CONCATENATES a timestamped line onto the existing topic; "
                "to fully replace a topic, call 'delete' then 'create'."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": allowed,
                        "description": "Which memory operation to perform.",
                    },
                    "topic": {
                        "type": "string",
                        "description": (
                            "Topic name — identifies the slice of memory. Required for create/read/append/delete. "
                            "Use a short, plain identifier (letters, digits, hyphens, underscores). "
                            "Do not include path separators, '..', or file extensions."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to store. Required for create/append.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text search query. Required for search.",
                    },
                    "limit": {
                        "type": "string",
                        "description": (
                            f"Max results for search. Defaults to {PersistentMemoryTool.DEFAULT_SEARCH_LIMIT}."
                        ),
                    },
                },
                "required": ["operation"],
            },
            tags=["langchain_tool"],
        )

    def _parse_memory_config(
        self,
        memory_config: Optional[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any], Optional[list[str]]]:
        """
        Split the HOCON memory_config into its three sub-configs. Warns on unknown keys.

        :param memory_config: Raw HOCON ``memory_config`` dict; may be ``None``.
        :return: ``(store_config, summarization_config, enabled_operations)`` tuple.
        """
        config: dict[str, Any] = dict(memory_config or {})
        unknown: set[str] = set(config) - self._MEMORY_CONFIG_KEYS
        if unknown:
            self.logger.warning(
                "Ignoring unknown memory_config keys: %s. Recognised keys: %s.",
                sorted(unknown),
                sorted(self._MEMORY_CONFIG_KEYS),
            )
        store_config: dict[str, Any] = dict(config.get("storage") or {})
        summarization_config: dict[str, Any] = dict(config.get("summarization") or {})
        enabled_operations_raw: Any = config.get("enabled_operations")
        enabled_operations: Optional[list[str]] = (
            list(enabled_operations_raw) if enabled_operations_raw is not None else None
        )
        return (store_config, summarization_config, enabled_operations)

    def _clean_enabled_operations(
        self,
        enabled_operations: Optional[list[str]],
        namespace_key: str,
    ) -> frozenset[str]:
        """
        Normalise the HOCON whitelist, drop unknown ops, warn on typos.

        Omitting ``enabled_operations`` or passing an empty list enables every
        operation. Unknown entries are dropped with a warning. If every entry
        is unknown the config is unusable, so we raise.

        :param enabled_operations: Raw ``enabled_operations`` list from HOCON, or ``None``.
        :param namespace_key: ``"<network>.<agent>"`` key, used in warnings.
        :return: A frozenset of validated operation names.
        """
        if not enabled_operations:
            return PersistentMemoryTool.ALL_OPERATIONS
        cleaned: set[str] = {str(op).strip().lower() for op in enabled_operations if op}
        unknown: set[str] = cleaned - PersistentMemoryTool.ALL_OPERATIONS
        if unknown:
            self.logger.warning(
                "(%s) ignoring unknown operations: %s",
                namespace_key,
                sorted(unknown),
            )
        resolved: frozenset[str] = frozenset(cleaned) & PersistentMemoryTool.ALL_OPERATIONS
        if not resolved:
            raise ValueError(
                f"({namespace_key}) 'enabled_operations' matched no known ops "
                f"(got {sorted(cleaned)}). Valid ops: "
                f"{sorted(PersistentMemoryTool.ALL_OPERATIONS)}."
            )
        return resolved

    def _parse_summarization_config(
        self,
        summarization_config: Optional[dict[str, Any]],
    ) -> tuple[int, str, str]:
        """
        Pull the summarizer settings out of the HOCON block. Warns on unknown keys.

        :param summarization_config: Raw ``summarization`` dict; may be ``None``.
        :return: ``(max_topic_size, model, personalization)`` tuple.
        """
        config: dict[str, Any] = dict(summarization_config or {})
        unknown: set[str] = set(config) - self._SUMMARIZATION_CONFIG_KEYS
        if unknown:
            self.logger.warning(
                "Ignoring unknown summarization keys: %s. Recognised keys: %s.",
                sorted(unknown),
                sorted(self._SUMMARIZATION_CONFIG_KEYS),
            )
        max_topic_size: int = int(config.get("max_topic_size", self._DEFAULT_MAX_TOPIC_SIZE))
        model: str = str(config.get("model", TopicSummarizer.DEFAULT_MODEL))
        personalization: str = str(config.get("personalization", ""))
        return (max_topic_size, model, personalization)

    @classmethod
    def _parse_origin_str(cls, origin_str: bool | str) -> tuple[str, str]:
        """
        Pull the network and agent names out of the framework's dotted origin.

        First segment is the network, second-to-last is the agent; any
        trailing ``-<digits>`` invocation index is stripped. Empty input —
        or a bare ``True`` that the framework never expanded — falls back to
        ``("unknown", "unknown")``.

        :param origin_str: Framework-supplied dotted call path, or ``True``
                           when the framework has not yet expanded the sentinel.
        :return: ``(network, agent)`` tuple.
        """
        if not origin_str or not isinstance(origin_str, str):
            logging.getLogger(f"{__name__}.{cls.__name__}").warning(
                "Empty or unexpanded origin_str; falling back to 'unknown.unknown' namespace."
            )
            return ("unknown", "unknown")
        parts: list[str] = origin_str.split(".")
        network: str = cls._INDEX_SUFFIX_RE.sub("", parts[0])
        agent: str = cls._INDEX_SUFFIX_RE.sub("", parts[-2])
        return (cls._safe_path_segment(network), cls._safe_path_segment(agent))

    @classmethod
    def _safe_path_segment(cls, segment: str) -> str:
        """
        Strip anything that could escape the store root.

        The namespace is joined into a filesystem path by the store, so a
        segment like ``"../etc"`` would land a write outside the memory
        root. Unsafe characters collapse to ``_``; empty or all-unsafe
        input falls back to ``"unknown"``.

        :param segment: Raw segment (network or agent name) from ``origin_str``.
        :return:        A segment safe to use as a path component.
        """
        cleaned: str = cls._UNSAFE_PATH_CHARS.sub("_", segment).strip("_")
        return cleaned or "unknown"

    @classmethod
    def build_preamble(cls) -> str:
        """
        Build the memory blurb for the system prompt.

        :return: The preamble text describing available memory operations.
        """
        return (
            f"You have a '{cls.MEMORY_TOOL_NAME}' tool for facts that must survive "
            "across turns and sessions.\n\n"
            "Rules:\n"
            "- Topic keys and content come from the user — never invent them.\n"
            "- Report only what the tool returns; never fabricate memories.\n"
            "- Every turn, start by calling 'list', then 'search' with relevant words "
            "from the user's message to surface related topics. Use the results as context.\n"
            "- Before writing, check the list. If a topic already covers the subject, use "
            "'append' with that exact key — 'create' OVERWRITES.\n"
            "- 'append' is the default for new or changed facts on an existing subject.\n"
            "- The store summarizer consolidates long topics on its own — do not prune manually.\n"
            "- Only use 'delete' + 'create' when a topic must be replaced wholesale because "
            "the old content is factually wrong."
        )
