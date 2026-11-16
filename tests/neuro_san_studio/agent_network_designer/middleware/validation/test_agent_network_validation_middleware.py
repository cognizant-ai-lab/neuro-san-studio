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
from unittest import mock
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from neuro_san_studio.agent_network_designer.common.constants import AGENT_NETWORK_DEFINITION
from neuro_san_studio.agent_network_designer.middleware.validation.agent_network_validation_middleware import (
    AgentNetworkValidationMiddleware,
)

# The logger the middleware logs on, named after the class of the instance.
MIDDLEWARE_LOGGER: str = "AgentNetworkValidationMiddleware"
# What the patched subclass hooks return.
NO_NETWORK_MESSAGE: str = "There is no network yet."
FORMATTED_ERRORS: str = "Two problems were found."
VALIDATION_ERRORS: list[str] = ["first problem", "second problem"]
NETWORK_DEF: dict[str, Any] = {
    "front_man": {
        "instructions": "Route each request to the right helper.",
        "description": "Answers customer requests.",
        "tools": [],
    },
}


class TestAgentNetworkValidationMiddleware(IsolatedAsyncioTestCase):
    """
    Tests for the after-agent hook that every validation middleware inherits.

    The base class is built directly, with its four subclass hooks patched, so these tests cover what
    the hook does with their answers: ask the model for a network when there is none, send the
    formatted errors back to the model, or let the agent finish when the network is valid.
    """

    def setUp(self) -> None:
        """
        Patch the subclass hooks with mocks the tests can set up and check.
        """
        self.validate: AsyncMock = self._patch("validate", AsyncMock(return_value=[]))
        self.format_error: MagicMock = self._patch("format_error", MagicMock(return_value=FORMATTED_ERRORS))
        self._patch("no_network_error_message", MagicMock(return_value=NO_NETWORK_MESSAGE))
        self._patch("validation_label", MagicMock(return_value="Test"))

    def _patch(self, name: str, replacement: Any) -> Any:
        """
        Replace a method of the base class for the rest of the test.

        :param name: The name of the method to replace
        :param replacement: The mock that takes its place
        :return: The replacement, so a test can set it up or check its calls
        """
        patcher: Any = mock.patch.object(AgentNetworkValidationMiddleware, name, new=replacement)
        patcher.start()
        self.addCleanup(patcher.stop)
        return replacement

    def _assert_sent_back_to_model(self, result: dict[str, Any] | None, content: str) -> None:
        """
        Check that the hook answered with one human message and a jump back to the model.

        :param result: What aafter_agent returned
        :param content: The text the message must hold
        """
        self.assertIsNotNone(result)
        self.assertEqual(result.get("jump_to"), "model")
        messages: list[Any] = result.get("messages")
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, content)

    async def test_missing_definition_asks_the_model_for_a_network(self) -> None:
        """
        With no definition in sly_data, the hook sends the no-network message back to the model and
        validates nothing.
        """
        middleware: AgentNetworkValidationMiddleware = AgentNetworkValidationMiddleware(sly_data={})

        result: dict[str, Any] | None = await middleware.aafter_agent({}, None)

        self._assert_sent_back_to_model(result, NO_NETWORK_MESSAGE)
        self.validate.assert_not_awaited()

    async def test_empty_definition_counts_as_missing(self) -> None:
        """
        An empty definition gets the same answer as a missing one.
        """
        middleware: AgentNetworkValidationMiddleware = AgentNetworkValidationMiddleware(
            sly_data={AGENT_NETWORK_DEFINITION: {}}
        )

        result: dict[str, Any] | None = await middleware.aafter_agent({}, None)

        self._assert_sent_back_to_model(result, NO_NETWORK_MESSAGE)
        self.validate.assert_not_awaited()

    async def test_errors_go_back_to_the_model_in_one_message(self) -> None:
        """
        The errors are formatted into one human message that sends the agent back to the model, and
        that message is logged as an error.
        """
        self.validate.return_value = list(VALIDATION_ERRORS)
        middleware: AgentNetworkValidationMiddleware = AgentNetworkValidationMiddleware(
            sly_data={AGENT_NETWORK_DEFINITION: deepcopy(NETWORK_DEF)}
        )

        with self.assertLogs(MIDDLEWARE_LOGGER, level="ERROR") as captured:
            result: dict[str, Any] | None = await middleware.aafter_agent({}, None)

        self._assert_sent_back_to_model(result, FORMATTED_ERRORS)
        self.format_error.assert_called_once_with(VALIDATION_ERRORS)
        self.assertEqual(captured.output, [f"ERROR:{MIDDLEWARE_LOGGER}:{FORMATTED_ERRORS}"])

    async def test_valid_definition_lets_the_agent_finish(self) -> None:
        """
        A definition with no errors returns None, so the agent ends its turn normally.
        """
        middleware: AgentNetworkValidationMiddleware = AgentNetworkValidationMiddleware(
            sly_data={AGENT_NETWORK_DEFINITION: deepcopy(NETWORK_DEF)}
        )

        result: dict[str, Any] | None = await middleware.aafter_agent({}, None)

        self.assertIsNone(result)
        self.format_error.assert_not_called()

    async def test_validate_gets_the_definition_held_in_sly_data(self) -> None:
        """
        The hook validates the definition object that sly_data holds, not a copy.
        """
        definition: dict[str, Any] = deepcopy(NETWORK_DEF)
        middleware: AgentNetworkValidationMiddleware = AgentNetworkValidationMiddleware(
            sly_data={AGENT_NETWORK_DEFINITION: definition}
        )

        await middleware.aafter_agent({}, None)

        self.validate.assert_awaited_once()
        self.assertIs(self.validate.await_args.args[0], definition)

    def test_hook_can_jump_back_to_the_model(self) -> None:
        """
        The hook declares the model as a place it can jump to. Without that, the agent graph has no
        edge for the jump_to the hook returns.
        """
        jump_targets: Any = getattr(AgentNetworkValidationMiddleware.aafter_agent, "__can_jump_to__", None)

        self.assertEqual(jump_targets, ["model"])
