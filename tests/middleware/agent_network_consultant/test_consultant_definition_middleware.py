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

"""Tests for Consultant-specific network definition formatting."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from middleware.agent_network_consultant.consultant_definition_middleware import ConsultantDefinitionMiddleware
from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_consultant.consultant_state import ConsultantState
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_DEFINITION
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE


class TestConsultantDefinitionMiddleware(IsolatedAsyncioTestCase):
    """Verify diagnosing agents receive the retained, redacted network context."""

    def test_format_definition_prompt_prefers_the_diagnostic_context(self) -> None:
        """Render retained diagnostic data instead of the reduced editable definition."""
        diagnostic_context: dict[str, Any] = {
            "metadata": {"api_key": "[REDACTED]"},
            "tools": [{"name": "front_man", "instructions": "Custom instructions."}],
        }
        sly_data: dict[str, Any] = {ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: diagnostic_context}
        middleware = ConsultantDefinitionMiddleware(sly_data=sly_data)

        prompt = middleware.format_definition_prompt({"front_man": {"instructions": "Reduced definition."}})

        self.assertIn('"api_key": "[REDACTED]"', prompt)
        self.assertIn("Custom instructions.", prompt)
        self.assertNotIn("Reduced definition.", prompt)

    async def test_hocon_definition_is_stripped_before_consultant_state_is_retained(self) -> None:
        """Retain diagnostic and editable state from the shared stripper result."""
        sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: "network.hocon"}
        middleware: ConsultantDefinitionMiddleware = ConsultantDefinitionMiddleware(sly_data=sly_data)
        config: dict[str, Any] = {
            "tools": [{"name": "front_man", "instructions": "Generated wrapper. Custom instructions."}]
        }
        loaded: dict[str, Any] = {"front_man": {"instructions": "Generated wrapper. Custom instructions."}}
        stripped: dict[str, Any] = {"front_man": {"instructions": "Custom instructions."}}
        with (
            patch.object(middleware, "_hocon_to_config", AsyncMock(return_value=config)),
            patch.object(middleware, "_config_to_network_def", AsyncMock(return_value=loaded)),
            patch.object(middleware, "_strip_common_instructions", AsyncMock(return_value=stripped)) as strip_mock,
        ):
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertEqual(2, strip_mock.await_count)
        self.assertEqual(loaded, strip_mock.await_args_list[0].args[0])
        self.assertEqual(stripped, sly_data.get(AGENT_NETWORK_DEFINITION))
        context: dict[str, Any] = sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT)
        self.assertEqual("Custom instructions.", context.get("tools")[0].get("instructions"))
        self.assertEqual(
            ConsultantInstructionChanges.snapshot(stripped),
            sly_data.get(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS),
        )

    async def test_hocon_definition_keeps_resolved_non_designer_substitutions(self) -> None:
        """Keep resolved custom substitutions in the Consultant definition and diagnostic context."""
        with TemporaryDirectory() as temporary_directory:
            network_path: Path = Path(temporary_directory) / "network.hocon"
            network_path.write_text(
                'shared_instructions = "Shared substitution text."\n'
                'tools = [{name = "front_man", instructions = ${shared_instructions} "Custom instructions."}]\n',
                encoding="utf-8",
            )
            sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: str(network_path)}
            middleware: ConsultantDefinitionMiddleware = ConsultantDefinitionMiddleware(sly_data=sly_data)

            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        expected: str = "Shared substitution text. Custom instructions."
        definition: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        self.assertEqual(expected, definition.get("front_man").get("instructions"))
        context: dict[str, Any] = sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT)
        self.assertEqual(expected, context.get("tools")[0].get("instructions"))
