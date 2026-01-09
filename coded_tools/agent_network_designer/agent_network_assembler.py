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


# pylint: disable=too-few-public-methods
class AgentNetworkAssembler:
    """
    Interface for a policy class that assembles an agent network from an agent network definition
    """

    def assemble_agent_network(
        self, network_def: dict[str, Any], top_agent_name: str, agent_network_name: str, sample_queries: list[str]
    ) -> Any:
        """
        Assemble the agent network from the definition.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network

        :return: Some representation of the agent network
        """
        raise NotImplementedError
