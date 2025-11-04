# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#

from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.file_system_agent_network_persistor import FileSystemAgentNetworkPersistor


class AgentNetworkPersistorFactory:

    @staticmethod
    def create_persistor(persistor_type: str) -> AgentNetworkPersistor:
        """
        Creates a new persistor of the specified type.

        :param persistor_type: The type of persistor to create.
        :return: A new persistor of the specified type.
        """
        persistor: AgentNetworkPersistor = None

        if persistor_type == "filesystem":
            persistor = FileSystemAgentNetworkPersistor()
        if persistor_type == "null":
            persistor = AgentNetworkPersistor()
        else:
            raise ValueError(f"Unknown persistor type: {persistor_type}")

        return persistor
