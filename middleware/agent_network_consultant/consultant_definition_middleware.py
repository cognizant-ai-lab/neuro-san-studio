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

"""Agent Network Consultant loading that preserves diagnostic source context."""

import json
from collections.abc import Mapping
from collections.abc import MutableSequence
from copy import deepcopy
from typing import Any
from typing import override

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter

from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.consultant_text import ConsultantText
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor


class ConsultantDefinitionMiddleware(AgentNetworkDefinitionMiddleware):
    """Load the target network without changing the shared Designer middleware."""

    @override
    def __init__(self, sly_data: dict[str, Any], progress_reporter: AgentProgressReporter | None = None) -> None:
        """
        Initialize Agent Network Consultant loading and its pending diagnostic source.

        :param sly_data: Shared runtime data used by the network middleware.
        :param progress_reporter: Optional reporter used for agent-network progress.
        """
        super().__init__(sly_data, progress_reporter)
        self._pending_diagnostic_config: dict[str, Any] | None = None

    @override
    async def _resolve_network_def(self) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        Resolve the network and retain its source path for surgical persistence.

        :return: The resulting mapping.
        """
        network_def = await super()._resolve_network_def()
        hocon_file = self.sly_data.get(AGENT_NETWORK_HOCON_FILE)
        if hocon_file and network_def:
            source_file = self._resolve_hocon_path(hocon_file)
            if source_file:
                self.sly_data.update({ConsultantState.AGENT_NETWORK_SOURCE_FILE: source_file})
        return network_def

    @override
    def format_definition_prompt(self, network_def: dict[str, Any]) -> str:
        """
        Expose a complete redacted definition to the diagnosing agent.

        :param network_def: The resolved agent-network definition.
        :return: The resulting text.
        """
        retained_context = self.sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT)
        if isinstance(retained_context, Mapping):
            context = self._current_diagnostic_context(retained_context, network_def)
        else:
            context = self._redact_sensitive_values(deepcopy(network_def))
        definition = json.dumps(context, indent=2)
        return f"## Current Agent Network Diagnostic Context\n\n```json\n{definition}\n```"

    @classmethod
    def _current_diagnostic_context(
        cls,
        retained_context: Mapping[str, Any],
        network_def: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Overlay current editable fields on the retained full-network diagnostic context.

        :param retained_context: The redacted source context captured when the HOCON file was loaded.
        :param network_def: The current resolved definition, including edits from completed tool calls.
        :return: A fresh redacted context containing the latest instructions and descriptions.
        """
        context: dict[str, Any] = {}
        for key, value in retained_context.items():
            context.update({key: deepcopy(value)})
        retained_tools = retained_context.get("tools")
        if not isinstance(retained_tools, MutableSequence):
            return cls._redact_sensitive_values(context)

        current_tools: list[Any] = []
        for raw_agent in retained_tools:
            if not isinstance(raw_agent, Mapping):
                current_tools.append(deepcopy(raw_agent))
                continue
            current_tools.append(cls._current_diagnostic_agent(raw_agent, network_def))
        context.update({"tools": current_tools})
        return cls._redact_sensitive_values(context)

    @staticmethod
    def _current_diagnostic_agent(
        retained_agent: Mapping[str, Any],
        network_def: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Overlay one agent's current editable fields on its retained source context.

        :param retained_agent: The source-aligned agent context captured during loading.
        :param network_def: The current resolved definition, including completed tool edits.
        :return: A fresh agent context containing the latest editable fields.
        """
        agent: dict[str, Any] = {}
        for key, value in retained_agent.items():
            agent.update({key: deepcopy(value)})
        agent_name = ConsultantText.text_value(agent.get("name"))
        current_agent = network_def.get(agent_name, {}) if agent_name is not None else {}
        if not isinstance(current_agent, Mapping):
            return agent
        instructions = ConsultantText.text_value(current_agent.get("instructions"))
        if instructions is not None:
            agent.update({"instructions": instructions})
        description = ConsultantText.text_value(current_agent.get("description"))
        function = agent.get("function")
        if description is not None and isinstance(function, Mapping):
            current_function: dict[str, Any] = {}
            for key, value in function.items():
                current_function.update({key: deepcopy(value)})
            current_function.update({"description": description})
            agent.update({"function": current_function})
        return agent

    @override
    async def _hocon_to_definition(self, network_hocon_file: str | None) -> dict[str, Any] | None:
        """
        Load a definition and retain its source config until the shared stripping pass.

        :param network_hocon_file: The optional registries-relative HOCON file name.
        :return: The resulting mapping.
        """
        config = await self._hocon_to_config(network_hocon_file)
        if config is None:
            return None
        network_def = await self._config_to_network_def(config, network_hocon_file)
        if network_def is not None:
            self._pending_diagnostic_config = config
        return network_def

    @override
    async def _strip_common_instructions(self, network_def: dict[str, Any]) -> dict[str, Any]:
        """
        Run the shared Designer stripping pass once and retain state from its result.

        :param network_def: The normalized agent-network definition.
        :return: The definition after the shared common-instruction stripping pass.
        """
        stripped_definition = await super()._strip_common_instructions(network_def)
        if self._pending_diagnostic_config is not None:
            config = self._pending_diagnostic_config
            self._pending_diagnostic_config = None
            self.sly_data.update(
                {
                    ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: self._build_diagnostic_context(
                        config, stripped_definition
                    ),
                    ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(
                        stripped_definition
                    ),
                }
            )
        return stripped_definition

    @classmethod
    def _build_diagnostic_context(cls, config: dict[str, Any], network_def: dict[str, Any]) -> dict[str, Any]:
        """
        Build the redacted full-network context shown to diagnosing agents.

        :param config: The parsed network configuration.
        :param network_def: The resolved agent-network definition.
        :return: The resulting mapping.
        """
        omitted_root_keys = {
            "aaosa_call",
            "aaosa_command",
            "aaosa_instructions",
            "demo_mode",
            "instructions_prefix",
            "pii_patterns",
            "tools",
        }
        context: dict[str, Any] = {}
        for key, value in config.items():
            if key not in omitted_root_keys:
                context.update({key: deepcopy(value)})
        aaosa_parameters = (config.get("aaosa_call") or {}).get("parameters")
        diagnostic_agents: list[Any] = []
        for raw_agent in config.get("tools", []):
            if not isinstance(raw_agent, Mapping):
                diagnostic_agents.append(deepcopy(raw_agent))
                continue
            agent = deepcopy(raw_agent)
            function = agent.get("function")
            if isinstance(function, Mapping) and function.get("parameters") == aaosa_parameters:
                function.pop("parameters", None)
            agent_name = ConsultantText.text_value(agent.get("name"))
            if agent_name is not None and agent_name in network_def and "instructions" in agent:
                agent.update({"instructions": network_def.get(agent_name, {}).get("instructions", "")})
            diagnostic_agents.append(agent)
        context.update({"tools": diagnostic_agents})
        return cls._redact_sensitive_values(context)

    @classmethod
    def _redact_sensitive_values(cls, value: Any, key_name: str = "") -> Any:
        """
        Recursively redact secret-bearing keys and recognizable credential values.

        :param value: The value to validate, redact, or return.
        :param key_name: The containing key used to detect sensitive values.
        :return: The resulting value.
        """
        if SensitiveDataRedactor.is_sensitive_key(key_name):
            return SensitiveDataRedactor.REDACTION
        if isinstance(value, Mapping):
            redacted_mapping: dict[Any, Any] = {}
            for key, item in value.items():
                redacted_mapping.update({key: cls._redact_sensitive_values(item, str(key))})
            return redacted_mapping
        if isinstance(value, MutableSequence):
            redacted_sequence: list[Any] = []
            for item in value:
                redacted_sequence.append(cls._redact_sensitive_values(item, key_name))
            return redacted_sequence
        text_value = ConsultantText.text_value(value)
        if text_value is not None and SensitiveDataRedactor.redact_text(text_value) != text_value:
            return SensitiveDataRedactor.REDACTION
        return value
