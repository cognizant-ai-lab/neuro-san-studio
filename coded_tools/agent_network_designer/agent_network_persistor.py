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

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler


class AgentNetworkPersistor:
    """
    Interface for persisting agent networks.
    This default implementation does nothing.
    """

    def get_assembler(self) -> AgentNetworkAssembler:
        """
        :return: An assembler instance associated with this persistor
        """
        raise NotImplementedError

    async def async_persist(self, obj: Any, file_reference: str = None) -> str:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network hocon string.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return an object describing the location to which the object was persisted
        """
        _ = obj, file_reference
        return None
