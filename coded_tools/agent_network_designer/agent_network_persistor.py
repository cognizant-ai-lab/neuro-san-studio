# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#

class AgentNetworkPersistor:

    async def async_persist(self, obj: str, file_reference: str = None) -> str:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network hocon string.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return an object describing the location to which the object was persisted
        """
        return None
