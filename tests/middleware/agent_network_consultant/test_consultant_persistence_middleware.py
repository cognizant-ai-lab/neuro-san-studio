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

"""Tests for Consultant-only validation and source-preserving persistence."""

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from neuro_san.interfaces.reservationist import Reservationist

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_consultant.consultant_persistence_middleware import ConsultantPersistenceMiddleware
from middleware.agent_network_consultant.consultant_state import ConsultantState


class TestConsultantPersistenceMiddleware(IsolatedAsyncioTestCase):
    """Verify unchanged definitions bypass validation and source persistence."""

    async def test_after_agent_returns_without_persisting_when_nothing_changed(self) -> None:
        """Record an empty change set and stop before validators or file writes run."""
        network_definition: dict[str, Any] = {
            "front_man": {"description": "Route requests.", "instructions": "Delegate the request."}
        }
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: network_definition,
            AGENT_NETWORK_NAME: "example",
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(network_definition),
        }
        middleware = ConsultantPersistenceMiddleware(
            Reservationist(), sly_data, persist_only_when_modified=True, preserve_source_hocon=True
        )

        result = await middleware.aafter_agent(Mock(), Mock())

        self.assertIsNone(result)
        self.assertEqual({}, sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES))

    async def test_after_agent_rejects_a_network_name_without_the_text_interface(self) -> None:
        """Stop before validation when shared data does not contain a textual network name."""
        network_definition: dict[str, Any] = {
            "front_man": {"description": "Route requests.", "instructions": "Use the updated route."}
        }
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: network_definition,
            AGENT_NETWORK_NAME: 42,
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: {
                "front_man": {"description": "Route requests.", "instructions": "Delegate the request."}
            },
        }
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data, preserve_source_hocon=True)

        with self.assertLogs(level="ERROR") as captured:
            result = await middleware.aafter_agent(Mock(), Mock())

        self.assertIsNone(result)
        self.assertIn(AGENT_NETWORK_NAME, "\n".join(captured.output))
        self.assertEqual(
            {"front_man": {"instructions": "Use the updated route."}},
            sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES),
        )

    async def test_after_agent_reports_a_missing_network_definition(self) -> None:
        """Report the required state key before returning without persistence."""
        sly_data: dict[str, Any] = {AGENT_NETWORK_NAME: "example"}
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data, preserve_source_hocon=True)

        with self.assertLogs(level="ERROR") as captured:
            result = await middleware.aafter_agent(Mock(), Mock())

        self.assertIsNone(result)
        self.assertIn(AGENT_NETWORK_DEFINITION, "\n".join(captured.output))
