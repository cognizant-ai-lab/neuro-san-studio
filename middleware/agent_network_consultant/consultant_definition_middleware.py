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

"""Consultant-only network loading that preserves diagnostic source context."""

import json
import re
from collections.abc import Mapping
from collections.abc import MutableSequence
from copy import deepcopy
from typing import Any
from typing import cast

from typing_extensions import override

from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_consultant.consultant_state import ConsultantState
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware


class ConsultantDefinitionMiddleware(AgentNetworkDefinitionMiddleware):
    """Load the target network without changing the shared designer middleware."""

    @staticmethod
    def _text_value(value: Any) -> str | None:
        """
        Read a value through its text-encoding interface.

        :param value: The candidate text value.
        :return: The normalized text, or `None` when the text interface is unavailable.
        """
        encode = getattr(value, "encode", None)
        if not callable(encode):
            return None
        return cast(str, value)

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
        context = self.sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT, network_def)
        definition = json.dumps(context, indent=2)
        return f"## Current Agent Network Diagnostic Context\n\n```json\n{definition}\n```"

    @override
    async def _hocon_to_definition(self, network_hocon_file: str | None) -> dict[str, Any] | None:
        """
        Load and strip a definition before retaining its diagnostic and editable state.

        :param network_hocon_file: The optional registries-relative HOCON file name.
        :return: The resulting mapping.
        """
        config = await self._hocon_to_config(network_hocon_file)
        if config is None:
            return None
        network_def = await self._config_to_network_def(config, network_hocon_file)
        if network_def is not None:
            network_def = await self._strip_common_instructions(network_def)
            self.sly_data.update(
                {
                    ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: self._build_diagnostic_context(
                        config, network_def
                    ),
                    ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(network_def),
                }
            )
        return network_def

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
        diagnostic_agents = []
        for raw_agent in config.get("tools", []):
            if not isinstance(raw_agent, Mapping):
                diagnostic_agents.append(deepcopy(raw_agent))
                continue
            agent = deepcopy(raw_agent)
            function = agent.get("function")
            if isinstance(function, Mapping) and function.get("parameters") == aaosa_parameters:
                function.pop("parameters", None)
            agent_name = agent.get("name")
            if agent_name in network_def and "instructions" in agent:
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
        if re.search(r"(?:api[_-]?key|authorization|credential|password|secret|token)", key_name, re.I):
            return "[REDACTED]"
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
        text_value = cls._text_value(value)
        if text_value is not None and re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]+|"
            r"xox[baprs]-[A-Za-z0-9-]+|Bearer\s+[A-Za-z0-9._~+/=-]{20,})",
            text_value,
        ):
            return "[REDACTED]"
        return value
