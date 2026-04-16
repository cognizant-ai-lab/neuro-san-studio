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

from typing import Any

from neuro_san.internals.validation.network.keyword_network_validator import KeywordNetworkValidator

from middleware.agent_network_designer.validation.agent_network_validation_middleware import (
    AgentNetworkValidationMiddleware,
)


class AgentNetworkInstructionsValidationMiddleware(AgentNetworkValidationMiddleware):
    """
    Middleware that validates agent instructions after each agent turn.

    Runs keyword validation against the current network definition stored
    in sly_data to detect missing or incomplete agent instructions.
    If validation errors are found, a `HumanMessage` containing the errors
    is injected into the conversation and control returns to the model so it can self-correct.
    """

    def no_network_error_message(self) -> str:
        """Return the error message when no agent network definition is found."""

        return "Error: No agent network found. Cannot edit or create instructions."

    def validation_label(self) -> str:
        """Return a label for log messages (e.g. 'Structure', 'Instructions')."""
        return "Instructions"

    async def validate(self, network_def: dict[str, Any]) -> list[str]:
        """
        Run validators against the network definition.

        :param network_def: The agent network definition to validate
        :return: A list of error strings (empty if valid)
        """
        return KeywordNetworkValidator().validate(network_def)

    def format_error(self, error_list: list[str]) -> str:
        """
        Format the list of validation errors into a message string.

        :param error_list: Non-empty list of error strings
        :return: Formatted error message
        """
        return "Error(s):\n" + "\n".join(error_list)
