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
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

EXTERNAL_AGENTS_CATALOG: str = "external_agents_catalog"
DEFAULT_EXTERNAL_AGENTS_FILE: str = os.path.join("middleware", "agent_network_designer", "external_agents.hocon")
TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})


class ExternalAgentsMiddleware(AgentMiddleware):
    """
    Middleware that loads the toggleable external-agent catalog from a HOCON file and, per
    model call, applies the env-var gate for each catalog entry:

    - When a module's `enabled_env_var` is truthy ("1"/"true"/"yes"/"on", case-insensitive):
      its `instructions` are appended to the system prompt and its `tool` is left in
      `ModelRequest.tools`.
    - When the env var is unset or falsy: the module's `tool` is stripped from
      `ModelRequest.tools` so the LLM cannot invoke it, and no prompt text is injected.

    The catalog is loaded once per session and cached in sly_data under the key
    "external_agents_catalog". Env var values are re-evaluated on every model call so a toggle
    flipped mid-session takes effect without restarting the server.
    """

    def __init__(self, sly_data: dict[str, Any]) -> None:
        """
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    "external_agents_catalog": the loaded catalog (populated on first call)
        """
        self.sly_data = sly_data
        self.logger = logging.getLogger(self.__class__.__name__)

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
        catalog: dict[str, Any] | None = self.sly_data.get(EXTERNAL_AGENTS_CATALOG)

        if catalog is None:
            catalog_file: str = os.getenv("EXTERNAL_AGENTS_FILE", DEFAULT_EXTERNAL_AGENTS_FILE)
            self.logger.debug(
                ">>>>>>>>>>>>>>>>>>>Loading External Agents Catalog from '%s'>>>>>>>>>>>>>>>>>>>",
                catalog_file,
            )
            try:
                hocon = AbstractAsyncConfigRestorer(file_purpose="get_external_agents", must_exist=True)
                catalog = await hocon.async_restore(file_reference=catalog_file)
            except FileNotFoundError:
                self.logger.warning("WARNING: External agents catalog file not found: %s. Skipping.", catalog_file)
                return await handler(request)

            self.sly_data[EXTERNAL_AGENTS_CATALOG] = catalog

        enabled_blocks, disabled_tools = self._classify(catalog or {})

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

    def _classify(self, catalog: dict[str, Any]) -> tuple[list[str], set[str]]:
        """
        Walk the catalog and split modules into enabled (whose instructions to inject) and
        disabled (whose tool refs to strip from the request).

        :param catalog: The loaded external-agents catalog
        :return: (list of instruction blocks to append, set of tool refs to drop)
        """
        enabled_blocks: list[str] = []
        disabled_tools: set[str] = set()

        for module_name, module in catalog.items():
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
                disabled_tools.add(tool)

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
