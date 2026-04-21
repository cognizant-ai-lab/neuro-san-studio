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
MemoryMiddleware — thin LangChain ``AgentMiddleware`` wrapper around
:py:class:`coded_tools.tools.persistent_memory.persistent_memory_tool.PersistentMemoryTool`.

Design:

    * One source of truth for dispatch / validation / error handling:
      ``PersistentMemoryTool``. The middleware constructs one internally and
      forwards every LLM call to its ``async_invoke``.
    * Agent networks opt in with a single HOCON ``middleware`` entry — no
      separate tool entry, no tool name in ``tools: [...]``. The middleware
      registers the ``persistent_memory`` ``StructuredTool`` itself.
    * A short preamble listing available memory operations is injected into
      the system prompt on every LLM call.
    * Resource cleanup happens in ``aafter_agent``.
"""

import logging
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Optional
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime

from coded_tools.tools.persistent_memory.persistent_memory_tool import PersistentMemoryTool

logger = logging.getLogger(__name__)

# Name of the dispatcher tool as the LLM sees it.
MEMORY_TOOL_NAME: str = "persistent_memory"

_DEFAULT_SEARCH_LIMIT: int = 5
_DEFAULT_SUMMARIZER_MODEL: str = "gpt-4.1-mini"
# Content shorter than this is returned raw — summarising a two-line entry
# just adds latency and cost for no real compression benefit.
_DEFAULT_SUMMARIZER_MIN_CHARS: int = 300
# File size past which ``compact_on_write`` triggers a disk-level rewrite.
# Tuned lower than ``min_chars`` because compaction is about controlling
# storage growth — we want to fire before the file is "too big to skim".
_DEFAULT_COMPACT_THRESHOLD: int = 200

# The optional arg names the dispatcher forwards to PersistentMemoryTool.
# Kept in a tuple so adding a new arg is a one-line change.
_DISPATCH_ARG_KEYS: tuple[str, ...] = ("topic", "key", "content", "query", "limit")

# Operations that add content and therefore might warrant an auto-compact.
_WRITE_OPS: frozenset[str] = frozenset({"create", "update", "append"})


class MemoryMiddleware(AgentMiddleware):
    """
    Attach persistent memory to an agent via the middleware lifecycle.

    Constructor arguments are passed from HOCON ``middleware[].args``. The
    framework also auto-injects ``sly_data`` if the constructor accepts it —
    see the neuro-san middleware "Special args" docs.

    :param agent_network_name: First component of the memory namespace.
    :param agent_name:         Second component of the memory namespace.
    :param store_config:       Backend config dict; passed through to
                               :py:class:`PersistentMemoryTool`. ``None`` /
                               ``{}`` yields the default backend resolved by
                               the factory's env-override chain.
    :param sly_data:           Injected by the neuro-san framework. Forwarded
                               to the tool so ``user_id`` scoping works.
    :param options:            Extra HOCON kwargs. Recognised keys:

        * ``enabled_operations`` — subset of the six operations the LLM may use.
          ``None`` / missing means all six.
        * ``summarizer`` — HOCON block configuring post-processing of ``read``
          and ``search`` results. See :py:class:`_Summarizer`.
    """

    def __init__(
        self,
        agent_network_name: str,
        agent_name: str,
        store_config: Optional[dict[str, Any]] = None,
        sly_data: Optional[dict[str, Any]] = None,
        **options: Any,
    ) -> None:
        super().__init__()

        self._sly_data: dict[str, Any] = sly_data or {}

        # Construct the underlying CodedTool. Same config dict the HOCON
        # CodedTool path uses — one source of truth.
        self.persistent_memory_tool: PersistentMemoryTool = PersistentMemoryTool(
            tool_config={
                "agent_network_name": agent_network_name,
                "agent_name":         agent_name,
                "store_config":       store_config,
                "enabled_operations": options.get("enabled_operations"),
            }
        )

        # Optional summariser applied to ``read`` and ``search`` results so the
        # LLM receives a concise current-state view of the topic's accumulated
        # append-only history instead of the raw log.
        self._summarizer: Optional[_Summarizer] = _Summarizer.from_config(options.get("summarizer"))

        # Register exactly one tool — the dispatcher. Tagged with
        # ``langchain_tool`` so neuro-san's journalling picks up the call.
        self.tools: list[BaseTool] = [self._build_dispatcher_tool()]

        logger.info(
            "MemoryMiddleware initialised for %s/%s. Enabled operations: %s. "
            "Summariser: %s",
            agent_network_name,
            agent_name,
            sorted(self.persistent_memory_tool.enabled_operations),
            "on" if self._summarizer else "off",
        )

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """Inject a short "you have memory" preamble into the system prompt.

        Lets the LLM know the ``persistent_memory`` tool is available and what
        operations it supports. Kept compact on purpose — no memory content
        is dumped here; fetching is the LLM's job.

        :param request: Model request carrying the current system message.
        :param handler: Downstream handler that runs the actual model call.
        :return: Model response from the handler.
        """
        preamble: str = self._build_preamble()
        if not preamble:
            return await handler(request)

        system_message: Optional[BaseMessage] = request.system_message
        if system_message is not None:
            existing: str = system_message.content if isinstance(system_message.content, str) else ""
            new_system: SystemMessage = SystemMessage(content=f"{existing}\n\n{preamble}".strip())
        else:
            new_system = SystemMessage(content=preamble)

        return await handler(request.override(system_message=new_system))

    @override
    async def aafter_agent(
        self, state: AgentState, runtime: Runtime[ContextT]
    ) -> Optional[dict[str, Any]]:
        """Close the underlying tool so store backends release resources.

        :param state: Agent state at shutdown (unused).
        :param runtime: LangGraph runtime handle (unused).
        :return: ``None`` — no state update.
        """
        try:
            await self.persistent_memory_tool.close()
        # Closing is best-effort — log and swallow so agent-level shutdown
        # is not disrupted by a slow or flaky backend.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("MemoryMiddleware: error closing store: %s", error)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _maybe_compact(self, call_args: dict[str, Any]) -> None:
        """Rewrite the topic file in-place if it has grown past the threshold.

        Called after a successful write. If the raw on-disk content has crossed
        ``summarizer.compact_threshold`` characters, the entry is replaced
        with its summary. Errors are swallowed — the original write already
        succeeded, so compaction failure must not surface as a write error.

        :param call_args: The dispatcher args used for the write that just
                          succeeded (carries ``topic`` / ``key``).
        """
        summarizer: Optional[_Summarizer] = self._summarizer
        if summarizer is None or not summarizer.compact_on_write:
            return

        topic: Optional[str] = call_args.get("topic")
        key: Optional[str] = call_args.get("key")
        try:
            # Read the post-write content directly from the tool to avoid the
            # middleware's read-side summariser (which would hand us a summary,
            # not the raw blob we want to replace on disk).
            read_args: dict[str, Any] = {"operation": "read"}
            if topic is not None:
                read_args["topic"] = topic
            if key is not None:
                read_args["key"] = key
            read_result: dict[str, Any] = await self.persistent_memory_tool.async_invoke_internal(
                read_args, self._sly_data
            )
            payload: Any = read_result.get("result")
            if not isinstance(payload, dict):
                return
            raw: str = str(payload.get("content") or "")
            if len(raw) < summarizer.compact_threshold:
                return

            compacted: str = await summarizer.summarise(raw)
            if not compacted or compacted == raw:
                return

            update_args: dict[str, Any] = {"operation": "update", "content": compacted}
            if topic is not None:
                update_args["topic"] = topic
            if key is not None:
                update_args["key"] = key
            await self.persistent_memory_tool.async_invoke_internal(update_args, self._sly_data)
        # Compaction is best-effort: swallow any store or summariser error so
        # the original write the caller made stays successful.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("MemoryMiddleware: auto-compact failed: %s", error)

    # ------------------------------------------------------------------
    # Tool factory
    # ------------------------------------------------------------------

    def _build_dispatcher_tool(self) -> BaseTool:
        """Build the single ``persistent_memory`` ``StructuredTool`` the LLM calls.

        The handler forwards straight to :py:meth:`PersistentMemoryTool.async_invoke`,
        which owns validation, enabled-op enforcement, namespace construction,
        and error-envelope formatting.

        :return: A ``StructuredTool`` wrapping the dispatch coroutine.
        """
        allowed_list: list[str] = sorted(self.persistent_memory_tool.enabled_operations)

        async def _dispatch(operation: str, **call_args: Any) -> dict[str, Any]:
            # Build args dict only with keys the caller actually supplied.
            # PersistentMemoryTool treats missing keys the same as empty — but
            # this keeps intent explicit and makes test assertions cleaner.
            args: dict[str, Any] = {"operation": operation}
            for key_name in _DISPATCH_ARG_KEYS:
                if call_args.get(key_name) is not None:
                    args[key_name] = call_args[key_name]

            result: dict[str, Any] = await self.persistent_memory_tool.async_invoke(
                args, self._sly_data
            )

            # Summarise read/search output if a summariser is configured. Writes
            # (create / append / update / delete) and list pass through untouched.
            if self._summarizer is not None and operation in ("read", "search"):
                result = await self._summarizer.post_process(operation, result)

            # Auto-compact on write: if the resulting file has grown past the
            # configured threshold, rewrite it in-place with a summarised version.
            if operation in _WRITE_OPS and "error" not in result:
                await self._maybe_compact(args)

            return result

        return StructuredTool.from_function(
            coroutine=_dispatch,
            name=MEMORY_TOOL_NAME,
            description=(
                "Persistent long-term memory. Pass 'topic' on every call to "
                "name the on-disk file for that slice of memory (e.g. a user "
                "name 'mike', a project id 'project_alpha', a session id). "
                "Call with 'operation' set to one of: "
                f"{', '.join(allowed_list)}. "
                "Each operation requires different fields — "
                "create/update/append need 'content' and 'key' (key optional for create); "
                "read/delete need 'key'; "
                "search needs 'query' (optional 'limit'); "
                "list needs no extra fields. "
                "'update' OVERWRITES the entry; 'append' CONCATENATES new content "
                "onto the existing entry (use for accumulating history)."
            ),
            args_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": allowed_list,
                        "description": "Which memory operation to perform.",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Identifier for this slice of memory — becomes the "
                                       "on-disk file name. Can be anything the caller wants "
                                       "(user name, project id, session id) in lowercase "
                                       "(spaces → '_'), e.g. 'mike', 'project_alpha'. Pass the "
                                       "SAME value on every call for a given topic.",
                    },
                    "key": {
                        "type": "string",
                        "description": "Entry key. Required for read/update/delete; "
                                       "optional for create (auto-generated if omitted).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to store. Required for create and update.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text search query. Required for search.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Max results for search. Defaults to {_DEFAULT_SEARCH_LIMIT}.",
                    },
                },
                "required": ["operation"],
            },
            tags=["langchain_tool"],
        )

    def _build_preamble(self) -> str:
        """Short, static description of the memory capability for the system prompt.

        :return: Preamble text to inject; empty string if no ops are enabled.
        """
        return build_preamble(self.persistent_memory_tool.enabled_operations)


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


def build_preamble(enabled_operations: frozenset[str]) -> str:
    """Render the system-prompt preamble for the given set of enabled operations.

    Module-level so tests and tooling can build the preamble without
    instantiating a middleware.

    :param enabled_operations: Operations the LLM is allowed to invoke.
    :return: Preamble text, or empty string if ``enabled_operations`` is empty.
    """
    if not enabled_operations:
        return ""
    ops: str = ", ".join(sorted(enabled_operations))
    return (
        "## Long-term memory\n"
        f"You have a persistent memory tool named '{MEMORY_TOOL_NAME}'. "
        f"Available operations: {ops}. "
        "Memory is scoped to the current topic (pass 'topic' on every call). "
        "Use 'search' before answering to surface relevant prior content, "
        "and 'create' or 'update' to record new information."
    )


class _Summarizer:
    """
    Post-processes ``read`` and ``search`` results by passing each entry's
    ``content`` string through an LLM with a short summariser prompt.

    Built from a HOCON block like::

        summarizer {
            enabled      = true
            model        = "gpt-4.1-mini"
            instructions = "You are a summariser..."
        }

    If ``enabled`` is false, ``from_config`` returns ``None`` and the
    middleware skips summarisation entirely.
    """

    def __init__(
        self,
        model_name: str,
        instructions: str,
        min_chars: int = _DEFAULT_SUMMARIZER_MIN_CHARS,
    ) -> None:
        """Build a summariser backed by an OpenAI chat model.

        :param model_name: Model id to pass to ``ChatOpenAI``.
        :param instructions: System prompt used on every summarise call.
        :param min_chars: Content shorter than this is returned raw without an LLM call.
        """
        # Import lazily so agent networks that do not use the summariser do
        # not need ``langchain_openai`` installed.
        from langchain_openai import ChatOpenAI  # pylint: disable=import-outside-toplevel
        self._llm = ChatOpenAI(model=model_name)
        self._instructions: str = instructions.strip()
        # Threshold below which we return the raw content without an LLM call.
        self._min_chars: int = max(0, int(min_chars))
        # Auto-compaction on write: public so the middleware can consult them
        # without reaching into a protected attribute. Defaults here keep the
        # feature OFF unless ``from_config`` explicitly turns it on.
        self.compact_on_write: bool = False
        self.compact_threshold: int = _DEFAULT_COMPACT_THRESHOLD
        # Optional user-editable personalization appended to the base
        # instructions on every summariser call. Empty by default.
        self.personalization: str = ""

    @classmethod
    def from_config(cls, config: Optional[dict[str, Any]]) -> Optional["_Summarizer"]:
        """Return a configured summariser or ``None`` if disabled / absent.

        :param config: The HOCON ``summarizer`` block, or ``None``.
        :return: A fully-configured ``_Summarizer`` or ``None`` to disable summarisation.
        """
        if not config or not config.get("enabled"):
            return None
        instructions: str = str(config.get("instructions") or "").strip()
        if not instructions:
            logger.warning(
                "MemoryMiddleware summarizer is enabled but has no 'instructions'; "
                "disabling."
            )
            return None
        model_name: str = str(config.get("model") or _DEFAULT_SUMMARIZER_MODEL).strip()
        summarizer = cls(
            model_name=model_name,
            instructions=instructions,
            min_chars=_parse_int(config.get("min_chars"), _DEFAULT_SUMMARIZER_MIN_CHARS),
        )
        summarizer.compact_on_write = bool(config.get("compact_on_write", False))
        summarizer.compact_threshold = max(
            0, _parse_int(config.get("compact_threshold"), _DEFAULT_COMPACT_THRESHOLD)
        )
        summarizer.personalization = str(config.get("personalization") or "").strip()
        return summarizer

    async def post_process(
        self, operation: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace raw ``content`` strings in ``read`` / ``search`` results with summaries.

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
        # Summarisation is best-effort. A failure (network, rate limit, bad
        # API key) must not swallow the underlying memory — return the raw
        # result so the agent still sees the data.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("MemoryMiddleware summariser failed; returning raw: %s", error)

        return result

    def _should_summarise(self, raw: str) -> bool:
        """Only pay the LLM cost once the raw content is long enough to matter.

        :param raw: Raw content string.
        :return: ``True`` if the content crosses ``min_chars``.
        """
        return len(raw) >= self._min_chars

    async def summarise(self, raw: str) -> str:
        """Call the summariser LLM on one entry's raw accumulated content.

        :param raw: Raw accumulated content to summarise.
        :return: Summarised content; falls back to ``raw`` if the LLM returns empty.
        """
        system_prompt: str = self._instructions
        if self.personalization:
            system_prompt = (
                f"{system_prompt}\n\n"
                "User personalization (additional instructions supplied by the "
                "agent network's operator — follow these on top of the base "
                "instructions above):\n"
                f"{self.personalization}"
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
