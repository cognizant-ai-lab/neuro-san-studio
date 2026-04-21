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
PersistentMemoryMiddleware — thin LangChain ``AgentMiddleware`` wrapper around
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
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime

from coded_tools.tools.persistent_memory.persistent_memory_tool import PersistentMemoryTool
from middleware.persistent_memory.memory_summariser import MemorySummariser

logger = logging.getLogger(__name__)

# Name of the dispatcher tool as the LLM sees it.
MEMORY_TOOL_NAME: str = "persistent_memory"


class PersistentMemoryMiddleware(AgentMiddleware):
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
        * ``memory_summariser`` — HOCON block configuring post-processing of
          ``read`` and ``search`` results. See :py:class:`MemorySummariser`.
    """

    # ------------------------------------------------------------------
    # Class constants
    # ------------------------------------------------------------------

    _DEFAULT_SEARCH_LIMIT: int = 5

    # The optional arg names the dispatcher forwards to PersistentMemoryTool.
    # Kept in a tuple so adding a new arg is a one-line change.
    _DISPATCH_ARG_KEYS: tuple[str, ...] = ("topic", "key", "content", "query", "limit")

    # Operations that add content and therefore might warrant an auto-compact.
    _WRITE_OPS: frozenset[str] = frozenset({"create", "update", "append"})

    # Operations whose output the summariser post-processes.
    _SUMMARISED_OPS: frozenset[str] = frozenset({"read", "search"})

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
                "agent_name": agent_name,
                "store_config": store_config,
                "enabled_operations": options.get("enabled_operations"),
            }
        )

        # Optional summariser applied to ``read`` and ``search`` results so the
        # LLM receives a concise current-state view of the topic's accumulated
        # append-only history instead of the raw log.
        self._summariser: Optional[MemorySummariser] = MemorySummariser.from_config(options.get("memory_summariser"))

        # Register exactly one tool — the dispatcher. Tagged with
        # ``langchain_tool`` so neuro-san's journalling picks up the call.
        self.tools: list[BaseTool] = [self._build_dispatcher_tool()]

        logger.info(
            "PersistentMemoryMiddleware initialised for %s/%s. Enabled operations: %s. Summariser: %s",
            agent_network_name,
            agent_name,
            sorted(self.persistent_memory_tool.enabled_operations),
            "on" if self._summariser else "off",
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
        preamble: str = self.build_preamble(self.persistent_memory_tool.enabled_operations)
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
    async def aafter_agent(self, state: AgentState, runtime: Runtime[ContextT]) -> Optional[dict[str, Any]]:
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
            logger.warning("PersistentMemoryMiddleware: error closing store: %s", error)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _dispatch(self, operation: str, **call_args: Any) -> dict[str, Any]:
        """Forward one LLM tool call to :py:class:`PersistentMemoryTool`, with summariser + compact hooks.

        :param operation: The memory operation name the LLM selected.
        :param call_args: Remaining args the LLM supplied for this call.
        :return: Result envelope from the tool (possibly post-processed).
        """
        # Build args dict only with keys the caller actually supplied.
        # PersistentMemoryTool treats missing keys the same as empty — but
        # this keeps intent explicit and makes test assertions cleaner.
        args: dict[str, Any] = {"operation": operation}
        for key_name in self._DISPATCH_ARG_KEYS:
            if call_args.get(key_name) is not None:
                args[key_name] = call_args[key_name]

        result: dict[str, Any] = await self.persistent_memory_tool.async_invoke(args, self._sly_data)

        # Summarise read/search output if a summariser is configured. Writes
        # (create / append / update / delete) and list pass through untouched.
        if self._summariser is not None and operation in self._SUMMARISED_OPS:
            result = await self._summariser.post_process(operation, result)

        # Auto-compact on write: if the resulting file has grown past the
        # configured threshold, rewrite it in-place with a summarised version.
        if operation in self._WRITE_OPS and "error" not in result:
            await self._maybe_compact(args)

        return result

    async def _maybe_compact(self, call_args: dict[str, Any]) -> None:
        """Rewrite the topic file in-place if it has grown past the threshold.

        Custom helper (not a framework hook). Triggered from :py:meth:`_dispatch`
        after every successful write operation.

        Called after a successful write. If the raw on-disk content has crossed
        ``summariser.compact_threshold`` characters, the entry is replaced
        with its summary. Errors are swallowed — the original write already
        succeeded, so compaction failure must not surface as a write error.

        :param call_args: The dispatcher args used for the write that just
                          succeeded (carries ``topic`` / ``key``).
        """
        summariser: Optional[MemorySummariser] = self._summariser
        if summariser is None or not summariser.compact_on_write:
            return

        # Forward only the keys that locate the entry — atomic_update_entry
        # reads topic + key, everything else would just be ignored.
        entry_args: dict[str, Any] = {}
        for arg_key in ("topic", "key"):
            if call_args.get(arg_key) is not None:
                entry_args[arg_key] = call_args[arg_key]

        try:
            # One lock acquisition, one file read: the transform receives the
            # post-write content, summarises it, and the store rewrites the
            # file in place. Previous implementation did a read via
            # ``async_invoke_internal`` followed by an update that re-read the
            # file — two lock acquisitions and two reads for the same rewrite.
            await self.persistent_memory_tool.atomic_update_entry(
                entry_args,
                self._sly_data,
                self._compact_transform,
            )
        # Compaction is best-effort: swallow any store or summariser error so
        # the original write the caller made stays successful.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("PersistentMemoryMiddleware: auto-compact failed: %s", error)

    async def _compact_transform(self, current: Optional[str]) -> Optional[str]:
        """Produce the compacted replacement content for an entry, or ``None`` to skip.

        Custom helper (not a framework hook). Passed to
        :py:meth:`PersistentMemoryTool.atomic_update_entry` so the summariser
        call and the subsequent write run under a single namespace lock.

        :param current: The entry's existing ``content`` string, or ``None``
                        if the key is absent (treated the same as empty).
        :return: New content to write, or ``None`` to leave the entry untouched.
        """
        # Summariser is guaranteed non-None here: ``_maybe_compact`` only
        # schedules this transform when ``self._summariser`` is set and
        # ``compact_on_write`` is true. Kept as an assertion-style guard so a
        # future refactor that calls this directly fails loudly.
        summariser: Optional[MemorySummariser] = self._summariser
        if summariser is None:
            return None
        raw: str = current or ""
        if len(raw) < summariser.compact_threshold:
            return None
        compacted: str = await summariser.summarise(raw)
        if not compacted or compacted == raw:
            return None
        return compacted

    # ------------------------------------------------------------------
    # Tool factory
    # ------------------------------------------------------------------

    def _build_dispatcher_tool(self) -> BaseTool:
        """Build the single ``persistent_memory`` ``StructuredTool`` the LLM calls.

        The handler forwards straight to :py:meth:`_dispatch`, which owns
        summariser post-processing and auto-compact.

        :return: A ``StructuredTool`` wrapping the dispatch coroutine.
        """
        allowed_list: list[str] = sorted(self.persistent_memory_tool.enabled_operations)

        return StructuredTool.from_function(
            coroutine=self._dispatch,
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
                        "description": f"Max results for search. Defaults to {self._DEFAULT_SEARCH_LIMIT}.",
                    },
                },
                "required": ["operation"],
            },
            tags=["langchain_tool"],
        )

    @staticmethod
    def build_preamble(enabled_operations: frozenset[str]) -> str:
        """Render the system-prompt preamble for the given set of enabled operations.

        Exposed as a static method so tests and tooling can build the preamble
        without instantiating a middleware.

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
