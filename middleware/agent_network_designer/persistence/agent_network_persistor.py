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

from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler


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

    async def async_restore_metadata(self, file_reference: str) -> dict[str, Any] | None:
        """
        Read back the metadata block of the network previously persisted under file_reference,
        so a save on behalf of a client that sent no block can carry it forward instead of
        erasing it (issue #1398).

        This default is a real implementation, not abstract: the base class doubles as the null
        persistor AgentNetworkPersistorFactory returns when nothing can be persisted.
        Implementations treat a missing or unreadable network as None rather than an error.

        :param file_reference: The file reference the network was persisted under
        :return: The metadata block, or None when there is nothing to carry forward
        """
        _ = file_reference
        return None
