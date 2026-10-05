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

"""Tests for Network Consultant instruction-field change tracking."""

from unittest import TestCase

from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges


class TestConsultantInstructionChanges(TestCase):
    """Verify change tracking remains limited to editable instruction fields."""

    def test_between_returns_only_changed_editable_fields(self) -> None:
        """
        Ignore unchanged fields and structural differences.
        """
        original = {
            "greeter": {
                "instructions": "Say hello.",
                "description": "Greets users.",
            }
        }
        definition = {
            "greeter": {
                "instructions": "Greet the user warmly.",
                "description": "Greets users.",
                "tools": ["clock"],
            }
        }

        changes = ConsultantInstructionChanges.between(original, definition)

        self.assertEqual(changes, {"greeter": {"instructions": "Greet the user warmly."}})

    def test_between_returns_no_changes_for_an_unchanged_snapshot(self) -> None:
        """
        Treat an unchanged network as a persistence no-op.
        """
        definition = {"greeter": {"instructions": "Say hello.", "description": "Greets users."}}
        original = ConsultantInstructionChanges.snapshot(definition)

        self.assertFalse(ConsultantInstructionChanges.between(original, definition))

    def test_snapshot_ignores_values_without_the_text_interface(self) -> None:
        """Exclude non-text editable values from the persistence snapshot."""
        definition = {"greeter": {"instructions": ["Say hello."], "description": 42}}

        snapshot = ConsultantInstructionChanges.snapshot(definition)

        self.assertEqual(snapshot, {})
