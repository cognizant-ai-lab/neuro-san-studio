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

from neuro_san.interfaces.reservationist import Reservationist

from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.file_system_agent_network_persistor import FileSystemAgentNetworkPersistor
from coded_tools.agent_network_designer.reservations_agent_network_persistor import ReservationsAgentNetworkPersistor


# pylint: disable=too-few-public-methods
class AgentNetworkPersistorFactory:
    """
    Factory class for AgentNetworkPersistors.
    """

    @staticmethod
    def create_persistor(args: dict[str, Any], write_to_file: bool) -> AgentNetworkPersistor:
        """
        Creates a new persistor of the specified type.

        :param args: The args from the calling CodedTool.
        :param write_to_file: True if the agent network should be written to a file.
        :return: A new AgentNetworkPersistor of the specified type.
        """
        persistor: AgentNetworkPersistor = None
        reservationist: Reservationist = None

        if args:
            reservationist = args.get("reservationist")

        if write_to_file:
            # If the write_to_file flag is True, then that's what we're doing.
            persistor = FileSystemAgentNetworkPersistor()
        elif reservationist:
            # If we have a reservationist as part of the args, use the ReservationsAgentNetworkPersistor
            persistor = ReservationsAgentNetworkPersistor(reservationist)
        else:
            # Fallback null implementation
            persistor = AgentNetworkPersistor()

        return persistor
