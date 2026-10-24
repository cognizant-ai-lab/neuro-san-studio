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

from langchain_core.messages import HumanMessage

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox
from middleware.agent_network_designer.validation.agent_network_structure_validation_middleware import (
    AgentNetworkStructureValidationMiddleware,
)

# What the stubbed editor caches hold: one served network, one MCP server and one toolbox tool.
SERVED_NETWORK: str = "/basic/music_nerd"
MCP_SERVER: str = "https://mcp.example.com/mcp"
TOOLBOX_TOOL: str = "web_fetch"
TOOLBOX_INFO: dict[str, Any] = {
    TOOLBOX_TOOL: {
        "class": "neuro_san_studio.coded_tools.web_fetch.WebFetch",
        "description": "Fetches a web page.",
    },
}
NO_NETWORK_MESSAGE: str = (
    "Error: No agent network found. Please create a new agent network using `create_new_network` tool"
)
FIX_REQUEST: str = "\n\nUse your tools to fix the errors."
# A valid network that uses each kind of tool: another agent, a toolbox tool, a served network and an MCP
# server. An agent without instructions is a toolbox agent.
VALID_NETWORK: dict[str, Any] = {
    "front_man": {
        "instructions": "Route each request to the right helper.",
        "description": "Answers customer requests.",
        "tools": ["helper", TOOLBOX_TOOL, SERVED_NETWORK, MCP_SERVER],
    },
    "helper": {
        "instructions": "Answer billing questions.",
        "description": "Answers billing questions.",
        "tools": [],
    },
    TOOLBOX_TOOL: {
        "description": "Fetches a web page.",
    },
}
# The errors the validators report for the problems the tests add to VALID_NETWORK.
MISSING_AGENT_ERROR: str = "Agent 'front_man' references non-existent agent(s) in tools: 'ghost'"
UNKNOWN_TOOLBOX_ERROR: str = "Toolbox agent 'image_maker' has no matching tool in toolbox."
UNKNOWN_NETWORK_ERROR: str = "Agent 'front_man' references an unrecognized URL or path tool '/not_served'."


class TestAgentNetworkStructureValidationMiddleware(IsolatedAsyncioTestCase):
    """
    Tests for AgentNetworkStructureValidationMiddleware.

    The middleware checks the network's structure, its toolbox agents and its references to served
    networks and MCP servers, against the editor's caches of the served networks, the MCP servers and
    the toolbox. The tests stub those caches and check which problems reach the model, and how.
    """

    def setUp(self) -> None:
        """
        Stub the editor caches the middleware validates against.
        """
        self.subnetwork_names: AsyncMock = self._start(
            mock.patch.object(GetSubnetwork, "get_subnetwork_names", new=AsyncMock(return_value=[SERVED_NETWORK]))
        )
        # The middleware adds to the list it gets, so each call returns a new one.
        self.mcp_servers: AsyncMock = self._start(
            mock.patch.object(GetMcpTool, "get_mcp_servers", new=AsyncMock(side_effect=self._mcp_server_list))
        )
        self.toolbox_info: AsyncMock = self._start(
            mock.patch.object(GetToolbox, "get_toolbox_info", new=AsyncMock(return_value=TOOLBOX_INFO))
        )

    def _start(self, patcher: Any) -> Any:
        """
        Start a patcher and stop it when the test ends.

        :param patcher: A unittest.mock patcher
        :return: The object the patcher put in place
        """
        replacement: Any = patcher.start()
        self.addCleanup(patcher.stop)
        return replacement

    @staticmethod
    def _mcp_server_list() -> list[str]:
        """
        Answer a call to the stubbed get_mcp_servers.

        :return: A new list holding the one configured MCP server
        """
        return [MCP_SERVER]

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
        middleware: AgentNetworkStructureValidationMiddleware = AgentNetworkStructureValidationMiddleware(sly_data)
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

    async def test_missing_definition_asks_for_a_new_network(self) -> None:
        """
        With no definition, the model is told to create one with the editor's create_new_network tool.
        """
        result: dict[str, Any] | None = await self._after_agent(None)

        self.assertEqual(self._sent_back_to_model(result), NO_NETWORK_MESSAGE)

    async def test_valid_network_passes(self) -> None:
        """
        A network whose agents, toolbox tool, served network and MCP server all check out passes, and it
        is checked against each of the three caches.
        """
        result: dict[str, Any] | None = await self._after_agent(deepcopy(VALID_NETWORK))

        self.assertIsNone(result)
        self.subnetwork_names.assert_awaited_once()
        self.mcp_servers.assert_awaited_once()
        self.toolbox_info.assert_awaited_once()

    async def test_reports_a_tool_that_is_not_an_agent(self) -> None:
        """
        A tool name that no agent in the network has is reported.
        """
        network_def: dict[str, Any] = deepcopy(VALID_NETWORK)
        network_def.get("front_man").get("tools").append("ghost")

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertIn(MISSING_AGENT_ERROR, self._sent_back_to_model(result))

    async def test_reports_a_toolbox_agent_that_is_not_in_the_toolbox(self) -> None:
        """
        An agent without instructions is a toolbox agent, and one the toolbox does not have is reported.
        """
        network_def: dict[str, Any] = deepcopy(VALID_NETWORK)
        network_def.get("front_man").get("tools").append("image_maker")
        network_def["image_maker"] = {"description": "Draws pictures."}

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertIn(UNKNOWN_TOOLBOX_ERROR, self._sent_back_to_model(result))

    async def test_reports_a_network_that_is_not_served(self) -> None:
        """
        A reference to a network the server does not serve is reported.
        """
        network_def: dict[str, Any] = deepcopy(VALID_NETWORK)
        network_def.get("front_man").get("tools").append("/not_served")

        result: dict[str, Any] | None = await self._after_agent(network_def)

        self.assertIn(UNKNOWN_NETWORK_ERROR, self._sent_back_to_model(result))

    async def test_reports_every_problem_in_one_message(self) -> None:
        """
        Problems found by different checks reach the model together, one bullet each, followed by the
        request to fix them.
        """
        network_def: dict[str, Any] = deepcopy(VALID_NETWORK)
        front_man_tools: list[str] = network_def.get("front_man").get("tools")
        front_man_tools.append("ghost")
        front_man_tools.append("image_maker")
        front_man_tools.append("/not_served")
        network_def["image_maker"] = {"description": "Draws pictures."}

        result: dict[str, Any] | None = await self._after_agent(network_def)

        content: str = self._sent_back_to_model(result)
        self.assertTrue(content.startswith("Errors detected:\n- "))
        self.assertTrue(content.endswith(FIX_REQUEST))
        self.assertIn(f"- {MISSING_AGENT_ERROR}", content)
        self.assertIn(f"- {UNKNOWN_TOOLBOX_ERROR}", content)
        self.assertIn(f"- {UNKNOWN_NETWORK_ERROR}", content)

    def test_errors_are_listed_as_bullets(self) -> None:
        """
        Each error gets its own bullet, and the message ends by asking the model to fix them.
        """
        middleware: AgentNetworkStructureValidationMiddleware = AgentNetworkStructureValidationMiddleware({})

        message: str = middleware.format_error(["first problem", "second problem"])

        self.assertEqual(message, f"Errors detected:\n- first problem\n- second problem{FIX_REQUEST}")
