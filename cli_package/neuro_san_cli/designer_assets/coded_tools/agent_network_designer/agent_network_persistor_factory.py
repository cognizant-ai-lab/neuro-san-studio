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
    def create_persistor(args: dict[str, Any], write_to_file: bool, demo_mode: bool) -> AgentNetworkPersistor:
        """
        Creates a new persistor of the specified type.

        :param args: The args from the calling CodedTool.
        :param write_to_file: True if the agent network should be written to a file.
        :param demo_mode: Whether to include demo mode instructions for agents
        :return: A new AgentNetworkPersistor of the specified type.
        """
        persistor: AgentNetworkPersistor = None
        reservationist: Reservationist = None

        if args:
            reservationist = args.get("reservationist")

        if write_to_file:
            # If the write_to_file flag is True, then that's what we're doing.
            persistor = FileSystemAgentNetworkPersistor(demo_mode)
        elif reservationist:
            # If we have a reservationist as part of the args, use the ReservationsAgentNetworkPersistor
            persistor = ReservationsAgentNetworkPersistor(args, demo_mode)
        else:
            # Fallback null implementation
            persistor = AgentNetworkPersistor()

        return persistor
