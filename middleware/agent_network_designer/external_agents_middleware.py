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

import logging
import os
from pathlib import Path
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from neuro_san.internals.utils.external_agent_parsing import ExternalAgentParsing
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache

# Relative to the repository root, like every other default path in this project
# (the server is expected to be started from the top of the repo — see run.py).
DEFAULT_EXTERNAL_AGENTS_FILE: str = str(Path("middleware", "agent_network_designer", "external_agents.hocon"))
TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})


class ExternalAgentsMiddleware(AgentMiddleware):
    """
    Middleware that loads the toggleable external-agent catalog from a HOCON file and
    applies the env-var gate for each catalog entry:

    - When a module's `enabled_env_var` is truthy ("1"/"true"/"yes"/"on", case-insensitive):
      its `instructions` are appended to the system prompt and its `tool` is left in
      `ModelRequest.tools`.
    - When the env var is unset or falsy: the module's `tool` is stripped from
      `ModelRequest.tools` so the LLM is never offered it, AND any tool call naming it
      anyway is denied at execution time by awrap_tool_call(). Stripping alone only
      changes what is *advertised*: the agent executor is built once with the full
      static tool list, so it would happily execute a stripped tool's name replayed
      from earlier chat history, hallucinated, or steered by prompt injection.

    The catalog is loaded once per process and shared via SharedProcessCache (see
    ProcessGlobals entry 7); an edited catalog file — or a changed EXTERNAL_AGENTS_FILE —
    is picked up on the next call through the path + modification-time fingerprint.
    Env-var toggle values are re-evaluated on every model and tool call, so a toggle
    flipped mid-session takes effect without restarting the server.

    The catalog is the only source of knowledge about which tools are toggleable — the
    designer's hocon must statically declare every external agent it can ever talk to, so
    this gate can only strip tools, never add them. If the catalog cannot be loaded, the
    middleware therefore fails CLOSED: the model call is refused with an actionable error
    instead of proceeding with disabled tools still reachable.
    """

    @staticmethod
    def _load_external_agents_catalog() -> dict[str, Any]:
        """
        SharedProcessCache loader: read and parse the external-agents catalog.

        Runs in a worker thread (reached through aget()), so the blocking file read
        and HOCON parse stay off the event loop.

        :return: The parsed catalog dictionary ({} for an empty file — loaders must
                never return None, the cache's miss sentinel).
        :raises ValueError: when the catalog cannot be read or parsed. Nothing is
                published on a raise, so the next call retries — an operator can fix
                the file and recover without restarting the server.
        """
        catalog_file: str = os.getenv("EXTERNAL_AGENTS_FILE", DEFAULT_EXTERNAL_AGENTS_FILE)
        try:
            # An empty env var (EXTERNAL_AGENTS_FILE="", the docker-compose/k8s idiom
            # for "unset") makes restore() return None before its must_exist check
            # ever runs. Treating that as an empty catalog would silently disable the
            # gate, so reject it here and let the fail-closed error below explain.
            if not catalog_file:
                raise ValueError("EXTERNAL_AGENTS_FILE is set to an empty string")
            restorer = AbstractAsyncConfigRestorer(file_purpose="get_external_agents", must_exist=True)
            catalog: dict[str, Any] = restorer.restore(file_reference=catalog_file)
        except (OSError, ValueError, ParseException) as error:
            # OSError covers FileNotFoundError / PermissionError / IsADirectoryError;
            # ValueError is raised for unsupported file extensions and is what current
            # neuro-san re-wraps HOCON/JSON parse failures into; ParseException stays
            # in the tuple defensively for neuro-san versions that surface pyhocon's
            # exception directly. Fail CLOSED: without the catalog we cannot know
            # which toggleable tools to strip, and proceeding would leave disabled
            # external agents (e.g. /middleware_manager) invokable even though their
            # toggle is off. A loud, actionable error beats a silent security
            # downgrade.
            raise ValueError(
                f"External agents catalog could not be loaded from '{catalog_file}': {error}. "
                "Tool gating cannot be applied without it, so the designer refuses to run. "
                "Fix (or unset) the EXTERNAL_AGENTS_FILE environment variable, or restore the "
                "default catalog file, and start the server from the top of the repository."
            ) from error
        return catalog or {}

    @staticmethod
    def _catalog_fingerprint() -> tuple[str, int | None]:
        """
        SharedProcessCache fingerprint: the resolved catalog path plus its
        modification time, so both an edited file and a changed EXTERNAL_AGENTS_FILE
        register as a miss and trigger a reload. Cheap and never raises, per the
        fingerprint contract.
        """
        catalog_file: str = os.getenv("EXTERNAL_AGENTS_FILE", DEFAULT_EXTERNAL_AGENTS_FILE)
        return catalog_file, SharedProcessCache.stat_modification_time_ns(catalog_file)

    # Process-wide cache of the parsed catalog (see ProcessGlobals entry 7). The
    # catalog is static server-side configuration: caching it per process replaces
    # the previous per-session sly_data cache, which re-read and re-parsed the file
    # for every new designer conversation. Access goes through the class by name
    # (not cls) so a hypothetical subclass shares the one cache instead of
    # splitting it.
    _shared_catalog_cache: SharedProcessCache[dict[str, Any]] = SharedProcessCache(
        loader=_load_external_agents_catalog,
        fingerprint=_catalog_fingerprint,
    )

    def __init__(self, sly_data: dict[str, Any]) -> None:
        """
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.
                No longer used by this middleware (the catalog moved to a
                process-wide cache); the parameter stays because MiddlewareFactory
                wires it in per the "sly_data": true arg in
                registries/agent_network_designer.hocon.
        """
        self.sly_data = sly_data
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def clear_shared_catalog_for_testing(cls):
        """
        Reset the process-wide catalog cache. For test isolation only.

        Production code must never call this: the cache is deliberately
        load-once-per-process with fingerprint-based refresh. Tests call it (via
        tests/conftest.py's ProcessGlobals reset) so a catalog loaded under one
        test's EXTERNAL_AGENTS_FILE state cannot leak into later tests.
        """
        ExternalAgentsMiddleware._shared_catalog_cache.clear_for_testing()

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Filter disabled tools out of the request and append enabled modules' workflow-step
        instructions to the system prompt before the model call.
        """
        catalog: dict[str, Any] = await ExternalAgentsMiddleware._shared_catalog_cache.aget()

        enabled_blocks, disabled_tools = self._classify(catalog)

        new_tools = self._filter_tools(request.tools, disabled_tools) if disabled_tools else None
        new_system_message = (
            self._extend_system_message(request.system_message, enabled_blocks) if enabled_blocks else None
        )

        if new_tools is None and new_system_message is None:
            return await handler(request)

        overrides: dict[str, Any] = {}
        if new_tools is not None:
            overrides["tools"] = new_tools
        if new_system_message is not None:
            overrides["system_message"] = new_system_message

        self.logger.debug(
            ">>>>>>>>>>>>>>>>>>>External Agents: dropped %d tool(s), injected %d block(s)>>>>>>>>>>>>>>>>>>>",
            len(disabled_tools),
            len(enabled_blocks),
        )
        return await handler(request.override(**overrides))

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """
        Enforce the env-var gate at tool-execution time.

        Narrowing ModelRequest.tools in awrap_model_call() only changes what is
        advertised to the model: the agent executor is still built with the full
        static tool list, so a tool call naming a stripped tool would otherwise
        still execute. This hook closes that gap by denying any call to a
        currently disabled module tool with an error ToolMessage the model can
        read and recover from.

        The disabled set is recomputed from the env vars here rather than recorded
        per tool call id (as neuro-san's LlmConfigToolSelectorMiddleware does for
        its model-driven selection): this gate is a deployment toggle over a
        static catalog, so current env state — not what was advertised on the call
        that produced the tool call — is the source of truth. A toggle flipped off
        between the model call and execution is denied, which is the stricter,
        intended reading.

        :param request: The ToolCallRequest describing the tool call to execute
        :param handler: Async callback that actually executes the tool call
        :return: The ToolMessage or Command from the tool call, or an error
                ToolMessage when the tool's module is currently toggled off.
        """
        tool_name: str | None = request.tool_call.get("name")

        catalog: dict[str, Any] = await ExternalAgentsMiddleware._shared_catalog_cache.aget()
        _, disabled_tools = self._classify(catalog)

        if tool_name in disabled_tools:
            self.logger.warning("Denying tool call for disabled external agent '%s'.", tool_name)
            call_id: str | None = request.tool_call.get("id")
            return ToolMessage(
                content=f"Error: tool '{tool_name}' is disabled on this deployment and was not executed.",
                # ToolMessage requires a string tool_call_id, but providers may
                # omit ids from tool calls (ToolCall.id is Optional). Preserve an
                # empty-string id so the message still matches its tool call.
                tool_call_id=call_id if call_id is not None else "unknown",
                name=tool_name,
                status="error",
            )

        return await handler(request)

    def _classify(self, catalog: dict[str, Any]) -> tuple[list[str], set[str]]:
        """
        Walk the catalog and split modules into enabled (whose instructions to inject) and
        disabled (whose tool refs to strip from the request).

        The catalog's `tool` field is the human-readable external-agent reference (e.g.
        "/middleware_manager") — the same form a user writes in a designer's `tools` array.
        Inside `ModelRequest.tools`, neuro-san exposes that same agent under its safe name
        (e.g. "__middleware_manager"), per ExternalAgentParsing.get_safe_agent_name and
        LangChainOpenAIFunctionTool.from_function_json. We translate here so the disabled
        set matches what the LLM actually sees on `BaseTool.name`.

        :param catalog: The loaded external-agents catalog
        :return: (list of instruction blocks to append, set of safe tool names to drop)
        """
        enabled_blocks: list[str] = []
        disabled_tools: set[str] = set()

        for module_name, module in catalog.items():
            if not isinstance(module, dict):
                # A custom catalog with a scalar top-level entry (e.g. "version": "1")
                # must degrade to a warning, not an AttributeError on every model call.
                self.logger.warning(
                    "External-agent module '%s' is not a mapping (got %s); skipping.",
                    module_name,
                    type(module).__name__,
                )
                continue

            env_var: str = module.get("enabled_env_var", "")
            tool: str = module.get("tool", "")
            if not env_var or not tool:
                self.logger.warning(
                    "External-agent module '%s' is missing `enabled_env_var` or `tool`; skipping.",
                    module_name,
                )
                continue

            if self._is_truthy(os.getenv(env_var)):
                instructions: str = (module.get("instructions") or "").strip()
                if instructions:
                    enabled_blocks.append(instructions)
            else:
                disabled_tools.add(ExternalAgentParsing.get_safe_agent_name(tool))

        return enabled_blocks, disabled_tools

    def _filter_tools(self, tools: list[Any], disabled_tools: set[str]) -> list[Any]:
        """
        Return a new tools list with every entry whose name matches a disabled tool removed.

        Tools may arrive as BaseTool instances (have a `.name` attribute) or as dicts (where
        the name lives under a "name" key, possibly nested in a "function" object for the
        OpenAI tool-schema shape). Anything we can't identify is left in place — better to
        leak an unknown entry than to silently drop a tool we should have kept.

        :param tools: The original tools list from the model request
        :param disabled_tools: Tool refs to drop
        :return: Filtered tools list
        """
        kept: list[Any] = []
        for entry in tools:
            name: str | None = self._extract_tool_name(entry)
            if name is not None and name in disabled_tools:
                continue
            kept.append(entry)
        return kept

    @staticmethod
    def _extract_tool_name(entry: Any) -> str | None:
        """
        Pull a tool name out of a tools-list entry. Supports BaseTool, plain dicts, and the
        nested function-schema dict shape (`{"function": {"name": ...}}`).
        """
        name = getattr(entry, "name", None)
        if isinstance(name, str):
            return name
        if isinstance(entry, dict):
            direct = entry.get("name")
            if isinstance(direct, str):
                return direct
            function = entry.get("function")
            if isinstance(function, dict):
                nested = function.get("name")
                if isinstance(nested, str):
                    return nested
        return None

    def _extend_system_message(self, system_message: BaseMessage | None, enabled_blocks: list[str]) -> SystemMessage:
        """
        Build a new SystemMessage with the enabled modules' instruction blocks appended.
        """
        addendum: str = "## Additional External Agents (toggled on)\n\n" + "\n".join(enabled_blocks)
        if system_message is None:
            return SystemMessage(content=addendum)
        original: str = system_message.content if isinstance(system_message.content, str) else ""
        return SystemMessage(content=f"{original}\n\n{addendum}")

    @staticmethod
    def _is_truthy(value: str | None) -> bool:
        """
        Treat the env var as enabled when set to a recognized truthy string.
        """
        if value is None:
            return False
        return value.strip().lower() in TRUTHY_VALUES
