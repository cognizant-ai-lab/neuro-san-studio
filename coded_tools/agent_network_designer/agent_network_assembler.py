# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from typing import Any


class AgentNetworkAssembler:
    """
    Interface for a policy class that assembles an agent network from an agent network definition
    """

    def assemble_agent_network(self, network_def: dict[str, Any],
                               top_agent_name: str,
                               agent_network_name: str) -> Any:
        """
        Assemble the agent network from the definition.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension

        :return: Some representation of the agent network
        """
        raise NotImplementedError
