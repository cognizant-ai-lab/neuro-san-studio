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

import logging
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.branch_activation import BranchActivation

from coded_tools.tools.coded_tool_agent_caller import CodedToolAgentCaller

logger = logging.getLogger(__name__)


class CallAgent(BranchActivation, CodedTool):
    """
    CodedTool implementation which provides a way to call an agent network.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "tool_args" the arguments for the called agent.
                    "agent_name" the agent that answer the query.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation, and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "selected_agent" the agent that answer the query

        :return:
            In case of successful execution:
                The answer from the agent as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        tool_args: Dict[str, Any] = args.get("tool_args")
        if not tool_args:
            raise ValueError("Error: No tool_args provided.")
        agent_name = args.get("agent_name") or sly_data.get("selected_agent")
        if not agent_name:
            raise ValueError("Error: No 'agent_name' in args or 'selected_agent' in sly_data.")

        logger.debug("tool_args: %s", tool_args)
        logger.debug("agent_name: %s", agent_name)

        # Set up the AgentCallers to use this CodedTool as a basis for calling the agents.
        agent_caller = CodedToolAgentCaller(self, parsing=None, name=agent_name)

        return await agent_caller.call_agent(tool_args=tool_args, sly_data=sly_data)
