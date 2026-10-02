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
from copy import deepcopy
from pathlib import Path
from typing import Any

from pyhocon import ConfigFactory
from pyhocon.config_tree import ConfigQuotedString
from pyhocon.config_tree import ConfigSubstitution
from pyhocon.config_tree import ConfigTree
from pyhocon.config_tree import ConfigValues
from pyhocon.exceptions import ConfigException
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware
from neuro_san_studio.coded_tools.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.middleware.agent_network_consultant.consultant_instruction_changes import (
    ConsultantInstructionChanges,
)


class ConsultantDefinitionMiddleware(AgentNetworkDefinitionMiddleware):
    """Load the target network without changing the shared designer middleware."""

    async def _resolve_network_def(self) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Resolve the network and retain its source path for surgical persistence."""
        network_def = await super()._resolve_network_def()
        hocon_file = self.sly_data.get(AGENT_NETWORK_HOCON_FILE)
        if hocon_file and network_def:
            source_file = self._resolve_hocon_path(hocon_file)
            if source_file:
                self.sly_data.update({ConsultantState.AGENT_NETWORK_SOURCE_FILE: source_file})
        return network_def

    def format_definition_prompt(self, network_def: dict[str, Any]) -> str:
        """Expose a complete redacted definition to the diagnosing agent."""
        context = self.sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT, network_def)
        definition = json.dumps(context, indent=2)
        return f"## Current Agent Network Diagnostic Context\n\n```json\n{definition}\n```"

    async def _hocon_to_definition(self, network_hocon_file: str | None) -> dict[str, Any] | None:
        """Load a definition while retaining unresolved source instruction literals."""
        config = await self._hocon_to_config(network_hocon_file)
        if config is None:
            return None
        network_def = await self._config_to_network_def(config, network_hocon_file)
        if network_def is not None:
            await self._apply_unresolved_instructions(network_def, network_hocon_file)
            self.sly_data.update(
                {
                    ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: self._build_diagnostic_context(
                        config, network_def
                    ),
                    ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(network_def),
                }
            )
        return network_def

    async def _apply_unresolved_instructions(
        self, network_def: dict[str, Any], network_hocon_file: str | None
    ) -> None:
        """Use source literals so shared HOCON substitutions are never copied into an edit."""
        file_reference = self._resolve_hocon_path(network_hocon_file)
        if file_reference is None:
            return
        try:
            unresolved = ConfigFactory.parse_string(
                Path(file_reference).read_text(encoding="utf-8"), basedir=".", resolve=False
            )
            agents = unresolved.get("tools", [])
        except (OSError, ConfigException, ParseException) as error:
            self.logger.warning(
                "WARNING: Could not re-read '%s' unresolved; instructions may contain expanded substitutions. %s",
                file_reference,
                error,
            )
            return

        if not isinstance(agents, list):
            return
        for agent in agents:
            if not isinstance(agent, ConfigTree):
                continue
            agent_name = agent.get("name", None)
            if not isinstance(agent_name, str) or agent_name not in network_def:
                continue
            network_agent = network_def.get(agent_name, {})
            if network_agent.get("instructions") is None:
                continue
            literal = self._literal_without_substitutions(agent.get("instructions", None))
            if literal:
                network_agent.update({"instructions": await self._extract_custom_instructions(literal)})

    @staticmethod
    def _literal_without_substitutions(value: Any) -> str | None:
        """Return only literal text from a possibly substituted HOCON value."""
        if isinstance(value, str):
            return value
        if not isinstance(value, ConfigValues):
            return None
        parts: list[str] = []
        for token in value.tokens:
            if isinstance(token, ConfigSubstitution):
                continue
            if isinstance(token, ConfigQuotedString):
                parts.append(token.value)
            elif isinstance(token, str):
                parts.append(token)
        return "".join(parts).strip() or None

    @classmethod
    def _build_diagnostic_context(cls, config: dict[str, Any], network_def: dict[str, Any]) -> dict[str, Any]:
        """Build the redacted full-network context shown to diagnosing agents."""
        omitted_root_keys = {
            "aaosa_call",
            "aaosa_command",
            "aaosa_instructions",
            "demo_mode",
            "instructions_prefix",
            "pii_patterns",
            "tools",
        }
        context = {key: deepcopy(value) for key, value in config.items() if key not in omitted_root_keys}
        aaosa_parameters = (config.get("aaosa_call") or {}).get("parameters")
        diagnostic_agents = []
        for raw_agent in config.get("tools", []):
            if not isinstance(raw_agent, dict):
                diagnostic_agents.append(deepcopy(raw_agent))
                continue
            agent = deepcopy(raw_agent)
            function = agent.get("function")
            if isinstance(function, dict) and function.get("parameters") == aaosa_parameters:
                function.pop("parameters", None)
            agent_name = agent.get("name")
            if agent_name in network_def and "instructions" in agent:
                agent.update({"instructions": network_def.get(agent_name, {}).get("instructions", "")})
            diagnostic_agents.append(agent)
        context.update({"tools": diagnostic_agents})
        return cls._redact_sensitive_values(context)

    @classmethod
    def _redact_sensitive_values(cls, value: Any, key_name: str = "") -> Any:
        """Recursively redact secret-bearing keys and recognizable credential values."""
        if re.search(r"(?:api[_-]?key|authorization|credential|password|secret|token)", key_name, re.I):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {key: cls._redact_sensitive_values(item, str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._redact_sensitive_values(item, key_name) for item in value]
        if isinstance(value, str) and re.search(
            r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]+|"
            r"xox[baprs]-[A-Za-z0-9-]+|Bearer\s+[A-Za-z0-9._~+/=-]{20,})",
            value,
        ):
            return "[REDACTED]"
        return value

    async def _extract_custom_instructions(self, instructions: str) -> str:
        """Remove shared boilerplate while retaining network-specific instructions."""
        legacy_prefix = r"You are part of a \w+ of assistants\.\s*"
        demo_mode = (
            "You are part of a demo system, so when queried, make up a realistic response as if "
            "you are actually grounded in real data or you are operating a real application API or microservice."
        )
        aaosa = " ".join((await self._get_aaosa_instructions()).split())
        expertise = " ".join((await self._get_expertise_scoping_instructions()).split())
        custom_part = re.sub(r"\s+", " ", instructions.strip())
        custom_part = re.sub(legacy_prefix, "", custom_part).strip()
        custom_part = custom_part.replace(aaosa, "").strip()
        custom_part = custom_part.replace(expertise, "").strip()
        custom_part = custom_part.replace(demo_mode, "").strip()
        return " ".join(custom_part.split())

    async def _get_expertise_scoping_instructions(self) -> str:
        """Load and cache the shared expertise-scoping boilerplate."""
        key = "expertise_scoping_instructions"
        async with await SlyDataLock.get_lock(self.sly_data, f"{key}_lock"):
            cached = self.sly_data.get(key)
            if cached is not None:
                return cached
            path = Path("registries/expertise_scoping_instructions.hocon")
            if not path.exists():
                value = ""
            else:
                config = ConfigFactory.parse_file(path)
                value = config.get(key, "")
            self.sly_data.update({key: value})
            return value
