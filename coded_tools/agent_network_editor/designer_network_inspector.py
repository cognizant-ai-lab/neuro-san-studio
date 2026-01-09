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

from neuro_san.internals.run_context.interfaces.agent_network_inspector import AgentNetworkInspector
from neuro_san.internals.validation.network.unreachable_nodes_network_validator import UnreachableNodesNetworkValidator


class DesignerNetworkInspector(AgentNetworkInspector):
    """
    AgentNetworkInspector implementation that wraps the internal format of the
    agent network designer and pals.
    """

    def __init__(self, network_def: dict[str, Any]):
        """
        Constructor

        :param network_def: The agent network definition as a dictionary
        """
        self.network_def = network_def

    def get_config(self) -> dict[str, Any]:
        """
        :return: The entire config dictionary given to the instance.
        """
        # 12/05/25: We are only using this for purposes of passing to the ConnectivityReporter,
        #           so just return None
        return None

    def get_agent_tool_spec(self, name: str) -> dict[str, Any]:
        """
        :param name: The name of the agent tool to get out of the registry
        :return: The dictionary representing the spec registered agent
        """
        return self.network_def.get(name)

    def get_name_from_spec(self, agent_spec: dict[str, Any]) -> str:
        """
        :param agent_spec: A single agent to register
        :return: The agent name as per the spec
        """
        return agent_spec.get("name")

    def find_front_man(self) -> str:
        """
        :return: A single tool name to use as the root of the chat agent.
                 This guy will be user facing.  If there are none or > 1,
                 an exception will be raised.
        """
        # The validator stuff uses the same internal network dictionary format
        validator = UnreachableNodesNetworkValidator()
        front_men: set[str] = validator.find_all_top_agents(self.network_def)
        if len(front_men) == 0:
            return None

        front_man: str = list(front_men)[0]
        return front_man
