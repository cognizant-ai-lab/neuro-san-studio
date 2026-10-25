# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

from copy import deepcopy
from typing import Any
from unittest import IsolatedAsyncioTestCase

from langchain_core.messages import HumanMessage

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from middleware.agent_network_designer.validation.agent_network_instructions_validation_middleware import (
    AgentNetworkInstructionsValidationMiddleware,
)

NO_NETWORK_MESSAGE: str = "Error: No agent network found. Cannot edit or create instructions or description."
# A network where every agent has its own instructions and description, as the designer keeps them: the
# description at the top level of the agent, not under "function".
COMPLETE_NETWORK: dict[str, Any] = {
    "front_man": {
        "instructions": "Route each request to the right helper.",
        "description": "Answers customer requests.",
        "tools": ["helper"],
    },
    "helper": {
        "instructions": "Answer billing questions.",
        "description": "Answers billing questions.",
    },
}


class TestAgentNetworkInstructionsValidationMiddleware(IsolatedAsyncioTestCase):
    """
    Tests for AgentNetworkInstructionsValidationMiddleware.

    The middleware checks that each agent's instructions and description are non-empty text. The designer
    keeps an agent's description at the top level, so the middleware checks a copy of the network with each
    description moved under "function", where neuro-san's keyword validator looks for it.
    """

    @staticmethod
    async def _after_agent(network_def: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Run the middleware's after-agent hook over a network.

        :param network_def: The network to put in sly_data, or None to leave it out
        :return: What aafter_agent returned
        """
        sly_data: dict[str, Any] = {}
        if network_def is not None:
            sly_data[AGENT_NETWORK_DEFINITION] = network_def
        middleware: AgentNetworkInstructionsValidationMiddleware = AgentNetworkInstructionsValidationMiddleware(
            sly_data
        )
        return await middleware.aafter_agent({}, None)

    def _sent_back_to_model(self, result: dict[str, Any] | None) -> str:
        """
        Check that the hook sent one human message back to the model, and return its text.

        :param result: What aafter_agent returned
        :return: The text of the message
        """
        self.assertIsNotNone(result)
        self.assertEqual(result.get("jump_to"), "model")
        messages: list[Any] = result.get("messages")
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], HumanMessage)
        return messages[0].content

    async def test_missing_definition_reports_that_there_is_nothing_to_edit(self) -> None:
        """
        With no definition, the model is told there is no network whose instructions it could write.
        """
        result: dict[str, Any] | None = await self._after_agent(None)

        self.assertEqual(self._sent_back_to_model(result), NO_NETWORK_MESSAGE)

    async def test_complete_network_passes(self) -> None:
        """
        A network where every agent has instructions and a description passes.
        """
        result: dict[str, Any] | None = await self._after_agent(deepcopy(COMPLETE_NETWORK))

        self.assertIsNone(result)

    async def test_reports_blank_instructions(self) -> None:
        """
        Instructions that hold only white space are reported as empty.
        """
        network_def: dict[str, Any] = deepcopy(COMPLETE_NETWORK)
        network_def.get("helper")["instructions"] = "   "

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertEqual(self._sent_back_to_model(result), "Error(s):\nhelper 'instructions' cannot be empty.")

    async def test_reports_an_empty_description(self) -> None:
        """
        An empty top-level description is reported, under the name neuro-san's validator gives it.
        """
        network_def: dict[str, Any] = deepcopy(COMPLETE_NETWORK)
        network_def.get("helper")["description"] = ""

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertEqual(self._sent_back_to_model(result), "Error(s):\nhelper 'function.description' cannot be empty.")

    async def test_reports_instructions_that_are_not_text(self) -> None:
        """
        Instructions that are not a string are reported with the type they have.
        """
        network_def: dict[str, Any] = deepcopy(COMPLETE_NETWORK)
        network_def.get("helper")["instructions"] = 42

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertEqual(self._sent_back_to_model(result), "Error(s):\nhelper 'instructions' must be a str, got int.")

    async def test_reports_each_error_on_its_own_line(self) -> None:
        """
        Errors from different agents follow the heading, one per line, in the order of the agents.
        """
        network_def: dict[str, Any] = deepcopy(COMPLETE_NETWORK)
        network_def.get("front_man")["description"] = ""
        network_def.get("helper")["instructions"] = ""

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertEqual(
            self._sent_back_to_model(result),
            "Error(s):\nfront_man 'function.description' cannot be empty.\nhelper 'instructions' cannot be empty.",
        )

    async def test_validation_leaves_the_definition_unchanged(self) -> None:
        """
        Moving each description under "function" happens on a copy; the definition in sly_data keeps its
        top-level descriptions.
        """
        network_def: dict[str, Any] = deepcopy(COMPLETE_NETWORK)
        middleware: AgentNetworkInstructionsValidationMiddleware = AgentNetworkInstructionsValidationMiddleware(
            {AGENT_NETWORK_DEFINITION: network_def}
        )

        errors: list[str] = await middleware.validate(network_def)

        self.assertEqual(errors, [])
        self.assertEqual(network_def, COMPLETE_NETWORK)
