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

"""Track instruction fields changed by Agent Network Consultant."""

from collections.abc import Mapping
from typing import Any
from typing import ClassVar

from neuro_san_studio.agent_network_consultant.consultant_text import ConsultantText


class ConsultantInstructionChanges:
    """Compare editable agent fields without coupling the shared writer to the Consultant."""

    EDITABLE_FIELDS: ClassVar[tuple[str, ...]] = ("instructions", "description")

    @classmethod
    def snapshot(cls, network_definition: dict[str, Any]) -> dict[str, dict[str, str]]:
        """
        Copy the editable string fields from an agent-network definition.

        :param network_definition: The resolved agent-network definition.
        :return: The resulting mapping.
        """
        snapshot: dict[str, dict[str, str]] = {}
        for agent_name, agent in network_definition.items():
            if not isinstance(agent, Mapping):
                continue
            fields: dict[str, str] = {}
            for field in cls.EDITABLE_FIELDS:
                value = ConsultantText.text_value(agent.get(field))
                if value is not None:
                    fields.update({field: value})
            if fields:
                snapshot.update({agent_name: fields})
        return snapshot

    @classmethod
    def between(
        cls,
        original_fields: dict[str, dict[str, str]],
        network_definition: dict[str, Any],
    ) -> dict[str, dict[str, str]]:
        """
        Return only editable string fields that differ from the original snapshot.

        :param original_fields: The editable fields captured before execution.
        :param network_definition: The resolved agent-network definition.
        :return: The resulting mapping.
        """
        changes: dict[str, dict[str, str]] = {}
        for agent_name, agent in network_definition.items():
            if not isinstance(agent, Mapping):
                continue
            original_agent: dict[str, str] = original_fields.get(agent_name, {})
            changed_fields: dict[str, str] = {}
            for field in cls.EDITABLE_FIELDS:
                value = ConsultantText.text_value(agent.get(field))
                if value is not None and value != original_agent.get(field):
                    changed_fields.update({field: value})
            if changed_fields:
                changes.update({agent_name: changed_fields})
        return changes
