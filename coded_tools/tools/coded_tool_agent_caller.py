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

import json
import logging
from typing import Any

from neuro_san.internals.graph.activations.branch_activation import BranchActivation

from coded_tools.experimental.mdap_decomposer.agent_caller import AgentCaller
from coded_tools.experimental.mdap_decomposer.solver_parsing import SolverParsing


class CodedToolAgentCaller(AgentCaller):
    """
    AgentCaller implementation that uses a BranchActivation from a CodedTool for calling an agent
    """

    def __init__(self, branch_activation: BranchActivation, parsing: SolverParsing = None, name: str = None):
        """
        Constructor

        :param branch_activation: The BranchActivation (CodedTool) used to call the agents.
                                  This ends up being the reference back to the CodedTool
                                  that is also derived from BranchActivation that wants to do
                                  the calling out to an agent internal to the network.
        :param parsing: The SolverParsing instance to use (if any) to extract the final answer
        :param name: The name of the agent
        """
        self.branch_activation: BranchActivation = branch_activation
        self.solver_parsing: SolverParsing = parsing
        self.name: str = name

    def get_name(self) -> str:
        """
        Get the name of the agent

        :return: The name of the agent
        """
        return self.name

    async def call_agent(self, tool_args: dict[str, Any], sly_data: dict[str, Any] = None) -> str:
        """
        Call a single agent with given text, return its response.
        :param tool_args: A dictionary of arguments to pass to the agent
        :param sly_data: A dictionary of private data to pass to the agent
        :return: The text of the response
        """

        use_name: str = self.get_name()
        logging.debug("call_agent(%s) sending args: %s", use_name, json.dumps(tool_args, indent=4))

        if sly_data is None:
            # No sly_data to pass on.
            sly_data = {}

        # Call my agent.
        # This is the magic hook back into the neuro-san framework that allows us to
        # invoke another agent (within the same network or not) from within a CodedTool.
        resp: str = await self.branch_activation.use_tool(use_name, tool_args, sly_data=sly_data)

        logging.debug("call_agent(%s): received %s chars", use_name, len(resp))
        if self.solver_parsing is not None:
            resp = self.solver_parsing.extract_final(resp)

        return resp
