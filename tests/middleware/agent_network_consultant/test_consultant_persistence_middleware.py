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

"""Tests for Agent Network Consultant validation and source-preserving persistence."""

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from neuro_san.interfaces.reservationist import Reservationist
from pyhocon.exceptions import ConfigException
from pyparsing import ParseBaseException

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox
from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_consultant.consultant_persistence_middleware import ConsultantPersistenceMiddleware
from middleware.agent_network_consultant.source_preserving_hocon_editor import SourcePreservingHoconEditor
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState


class TestConsultantPersistenceMiddleware(IsolatedAsyncioTestCase):
    """Verify Consultant-owned validation and source-preserving persistence."""

    @staticmethod
    def _changed_middleware(failure_count: int = 0) -> tuple[ConsultantPersistenceMiddleware, dict[str, Any]]:
        """
        Create middleware with one pending instruction change.

        :param failure_count: The existing consecutive persistence-failure count.
        :return: The configured middleware and its shared state.
        """
        original_definition: dict[str, Any] = {
            "front_man": {"description": "Route requests.", "instructions": "Delegate the request."}
        }
        changed_definition: dict[str, Any] = {
            "front_man": {"description": "Route requests.", "instructions": "Use the updated route."}
        }
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: changed_definition,
            AGENT_NETWORK_NAME: "example",
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(original_definition),
            ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: failure_count,
            ConsultantState.AGENT_NETWORK_SOURCE_FILE: "registries/example.hocon",
        }
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)
        return middleware, sly_data

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
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)

        with (
            patch.object(middleware, "_validate_network", new=AsyncMock()) as validate,
            patch.object(SourcePreservingHoconEditor, "update_file") as update_file,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.assertEqual({}, sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES))
        validate.assert_not_awaited()
        update_file.assert_not_called()

    async def test_after_agent_rejects_a_network_name_without_the_text_interface(self) -> None:
        """Stop before validation when shared data does not contain a usable network name."""
        network_definition: dict[str, Any] = {
            "front_man": {"description": "Route requests.", "instructions": "Use the updated route."}
        }
        invalid_names: tuple[Any, Any] = (42, "")
        for invalid_name in invalid_names:
            with self.subTest(invalid_name=invalid_name):
                sly_data: dict[str, Any] = {
                    AGENT_NETWORK_DEFINITION: network_definition,
                    AGENT_NETWORK_NAME: invalid_name,
                    ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: {
                        "front_man": {"description": "Route requests.", "instructions": "Delegate the request."}
                    },
                }
                middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)

                with self.assertLogs(level="ERROR") as captured:
                    result = await middleware.aafter_agent({}, None)

                self.assertIsNone(result)
                self.assertIn(AGENT_NETWORK_NAME, "\n".join(captured.output))
                self.assertEqual(
                    {"front_man": {"instructions": "Use the updated route."}},
                    sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES),
                )

    async def test_after_agent_reports_a_missing_network_definition(self) -> None:
        """Report an absent or malformed definition before returning without persistence."""
        invalid_definitions: tuple[Any, Any] = (None, ["not", "a", "mapping"])
        for invalid_definition in invalid_definitions:
            with self.subTest(invalid_definition=invalid_definition):
                sly_data: dict[str, Any] = {
                    AGENT_NETWORK_NAME: "example",
                    AGENT_NETWORK_DEFINITION: invalid_definition,
                    ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: {},
                }
                middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)

                with self.assertLogs(level="ERROR") as captured:
                    result = await middleware.aafter_agent({}, None)

                self.assertIsNone(result)
                self.assertIn(AGENT_NETWORK_DEFINITION, "\n".join(captured.output))

    async def test_after_agent_requires_the_original_editable_field_snapshot(self) -> None:
        """Stop before validation or persistence when the source-aligned editable snapshot is unavailable."""
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: {
                "front_man": {"description": "Route requests.", "instructions": "Updated instructions."}
            },
            AGENT_NETWORK_NAME: "example",
        }
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)
        with (
            patch.object(middleware, "_validate_network", new=AsyncMock()) as validate,
            patch.object(SourcePreservingHoconEditor, "update_file") as update_file,
            self.assertLogs(level="ERROR") as captured,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.assertIn(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS, "\n".join(captured.output))
        self.assertEqual({}, sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES))
        validate.assert_not_awaited()
        update_file.assert_not_called()

    async def test_after_agent_ignores_a_nontext_diagnostic_coded_tool_name(self) -> None:
        """Leave malformed diagnostic names for validators to report instead of treating them as set members."""
        middleware, sly_data = self._changed_middleware()
        sly_data.update(
            {
                ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: {
                    "tools": [{"class": "coded_tools.example.Example", "name": []}]
                }
            }
        )
        toolbox_tools: dict[str, dict[str, Any]] = {}
        with (
            patch.object(GetSubnetwork, "get_subnetwork_names", new=AsyncMock(return_value=[])),
            patch.object(GetMcpTool, "get_mcp_servers", new=AsyncMock(return_value=[])),
            patch.object(GetMcpTool, "sly_data_http_header_urls", return_value=[]),
            patch.object(GetToolbox, "get_toolbox_info", new=AsyncMock(return_value=toolbox_tools)),
            patch.object(SourcePreservingHoconEditor, "update_file", return_value='{"tools": []}') as update_file,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.assertEqual({}, toolbox_tools)
        update_file.assert_called_once()

    async def test_after_agent_accepts_an_existing_coded_tool(self) -> None:
        """Accept a target network's existing coded tool without adding it to Designer's toolbox."""
        original_definition: dict[str, Any] = {
            "front_man": {
                "description": "Route requests.",
                "instructions": "Delegate the request.",
                "tools": ["employee_lookup"],
            },
            "employee_lookup": {
                "class": "employee_lookup.EmployeeLookup",
                "description": "Look up an employee.",
            },
        }
        changed_definition: dict[str, Any] = {
            "front_man": {
                "description": "Route requests.",
                "instructions": "Use the updated route.",
                "tools": ["employee_lookup"],
            },
            "employee_lookup": {
                "class": "employee_lookup.EmployeeLookup",
                "description": "Look up an employee.",
            },
        }
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: changed_definition,
            AGENT_NETWORK_NAME: "example",
            ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT: {
                "tools": [{"class": "employee_lookup.EmployeeLookup", "name": "employee_lookup"}]
            },
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(original_definition),
            ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: 0,
            ConsultantState.AGENT_NETWORK_SOURCE_FILE: "registries/example.hocon",
        }
        middleware = ConsultantPersistenceMiddleware(Reservationist(), sly_data)
        toolbox_tools: dict[str, dict[str, Any]] = {}
        with (
            patch.object(GetSubnetwork, "get_subnetwork_names", new=AsyncMock(return_value=[])),
            patch.object(GetMcpTool, "get_mcp_servers", new=AsyncMock(return_value=[])),
            patch.object(GetMcpTool, "sly_data_http_header_urls", return_value=[]),
            patch.object(GetToolbox, "get_toolbox_info", new=AsyncMock(return_value=toolbox_tools)),
            patch.object(SourcePreservingHoconEditor, "update_file", return_value='{"tools": []}') as update_file,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.assertEqual({"employee_lookup": {}}, toolbox_tools)
        update_file.assert_called_once()

    async def test_after_agent_counts_repeated_source_edit_failures(self) -> None:
        """Record each structured source-edit failure without inspecting its log message."""
        middleware, sly_data = self._changed_middleware()
        validation = AsyncMock(return_value=([], []))
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file", side_effect=ValueError("unsupported source")),
        ):
            for expected_count in range(1, 4):
                with self.assertRaisesRegex(ValueError, "unsupported source"):
                    await middleware.aafter_agent({}, None)
                self.assertEqual(
                    expected_count,
                    sly_data.get(ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT),
                )

    async def test_after_agent_rejects_a_malformed_persistence_failure_count(self) -> None:
        """Reject malformed middleware state instead of coercing it into an integer counter."""
        middleware, sly_data = self._changed_middleware()
        sly_data.update({ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: "2"})
        validation = AsyncMock(return_value=([], []))
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file", side_effect=ValueError("unsupported source")),
            self.assertRaisesRegex(TypeError, "persistence failure count must be an integer"),
        ):
            await middleware.aafter_agent({}, None)

    async def test_after_agent_resets_source_edit_failures_after_success(self) -> None:
        """Publish the source text and reset all persistence state after a successful edit."""
        middleware, sly_data = self._changed_middleware(failure_count=2)
        validation = AsyncMock(return_value=([], []))
        updated_text: str = '{"tools": []}'
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file", return_value=updated_text) as update_file,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        update_file.assert_called_once_with(
            "registries/example.hocon",
            {"front_man": {"instructions": "Use the updated route."}},
            {"front_man": {"description": "Route requests.", "instructions": "Delegate the request."}},
        )
        self.assertEqual(updated_text, sly_data.get(AGENT_NETWORK_HOCON_TEXT))
        self.assertEqual({}, sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES))
        self.assertEqual(
            {
                "front_man": {
                    "description": "Route requests.",
                    "instructions": "Use the updated route.",
                }
            },
            sly_data.get(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS),
        )
        self.assertEqual(0, sly_data.get(ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT))

    async def test_after_agent_returns_validation_feedback_without_persisting(self) -> None:
        """Return an actionable model retry while validation failures remain."""
        middleware, _ = self._changed_middleware()
        validation = AsyncMock(return_value=(["missing front man"], ["instructions are empty"]))
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file") as update_file,
            self.assertLogs("ConsultantPersistenceMiddleware", level="INFO") as captured,
        ):
            result: dict[str, Any] | None = await middleware.aafter_agent({}, None)

        self.assertIsNotNone(result)
        self.assertEqual("model", (result or {}).get("jump_to"))
        messages: list[Any] = (result or {}).get("messages", [])
        self.assertEqual(1, len(messages))
        message_text: str = str(messages[0])
        self.assertIn("STRUCTURAL_CHANGE_REQUIRED", message_text)
        self.assertIn("write_all_instructions", message_text)
        self.assertNotIn("agent_network_editor", message_text)
        self.assertNotIn("agent_network_instructions_editor", message_text)
        self.assertIn("requesting an Agent Network Consultant repair", "\n".join(captured.output))
        update_file.assert_not_called()

    async def test_after_agent_logs_terminal_validation_exhaustion_as_error(self) -> None:
        """Log terminal validation exhaustion at error level and do not write the source."""
        with patch.dict("os.environ", {"AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS": "0"}):
            middleware, _ = self._changed_middleware()
        validation = AsyncMock(return_value=(["invalid structure"], []))
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file") as update_file,
            self.assertLogs("ConsultantPersistenceMiddleware", level="ERROR") as captured,
        ):
            result = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.assertIn("ERROR", "\n".join(captured.output))
        self.assertIn("Reached max validation attempts (0)", "\n".join(captured.output))
        update_file.assert_not_called()

    async def test_after_agent_counts_parser_failures_as_stuck_patches(self) -> None:
        """Count supported parser failures while preserving their original exception types."""
        failures: tuple[Exception, Exception] = (
            ConfigException("invalid HOCON"),
            ParseBaseException("invalid syntax"),
        )
        for failure in failures:
            failure_type: type[Exception] = type(failure)
            with self.subTest(failure=failure):
                middleware, sly_data = self._changed_middleware()
                validation = AsyncMock(return_value=([], []))
                with (
                    patch.object(middleware, "_validate_network", new=validation),
                    patch.object(SourcePreservingHoconEditor, "update_file", side_effect=failure),
                    self.assertRaises(failure_type),
                ):
                    await middleware.aafter_agent({}, None)

                self.assertEqual(
                    1,
                    sly_data.get(ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT),
                )

    async def test_after_agent_does_not_count_file_system_failures_as_stuck_patches(self) -> None:
        """Keep ordinary file-system failures outside the unsupported-source retry counter."""
        middleware, sly_data = self._changed_middleware()
        validation = AsyncMock(return_value=([], []))
        with (
            patch.object(middleware, "_validate_network", new=validation),
            patch.object(SourcePreservingHoconEditor, "update_file", side_effect=OSError("disk unavailable")),
            self.assertRaisesRegex(OSError, "disk unavailable"),
        ):
            await middleware.aafter_agent({}, None)

        self.assertEqual(0, sly_data.get(ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT))
