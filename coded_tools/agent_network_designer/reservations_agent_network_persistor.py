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

from neuro_san.interfaces.reservation import Reservation
from neuro_san.internals.reservations.reservation_util import ReservationUtil

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler
from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.deployable_agent_network_assembler import DeployableAgentNetworkAssembler


class ReservationsAgentNetworkPersistor(AgentNetworkPersistor):
    """
    AgentNetworkPersistor implementation that saves a temporary network
    using the neuro-san Reservations API
    """

    def __init__(self, args: dict[str, Any], demo_mode: bool):
        """
        Creates a new persistor of the specified type.

        :param args: The arguments from the calling CodedTool.
                    It should contain a Reservationist instance.
        """
        self.args: dict[str, Any] = args
        self.demo_mode: bool = demo_mode

    def get_assembler(self) -> AgentNetworkAssembler:
        """
        :return: An assembler instance associated with this persistor
        """
        return DeployableAgentNetworkAssembler(self.demo_mode)

    async def async_persist(self, obj: dict[str, Any], file_reference: str = None) -> str | list[dict[str, Any]]:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network dictionary spec.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return an object describing the location to which the object was persisted
                If the return value is a string, an error has occurred.
                Otherwise, it is a list of agent reservation dictionaries.
        """
        agent_spec: dict[str, Any] = obj
        # Remove the generated/ prefix
        agent_prefix: str = file_reference.replace("generated/", "")
        # For now
        lifetime_in_seconds: float = 60.0 * 60.0

        reservation: Reservation = None
        error: str = None
        reservation, error = await ReservationUtil.wait_for_one(
            self.args, agent_spec, lifetime_in_seconds, agent_prefix
        )

        if error is not None:
            return error

        agent_reservations: list[dict[str, Any]] = [
            {
                "reservation_id": reservation.get_reservation_id(),
                "lifetime_in_seconds": reservation.get_lifetime_in_seconds(),
                "expiration_time_in_seconds": reservation.get_expiration_time_in_seconds(),
            }
        ]

        return agent_reservations
